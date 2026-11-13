"""Extracellular-first release: scoring, context-safe store, seed restoration,
constrained Vmax-only search and single-vector release selection. No ODE here.

Release objective ``extracellular_first/2`` (registered in
config/fla_extracellular_release_2026_11_12.json; supersedes /1, which was never run):

- channels: panel observation names that are keys of the model's external-pool
  registry (``rbc_gem_audit.EXTERNAL_POOLS``), not a name-prefix rule;
- per channel: band-normalized MSE over the dated points whose inherited working
  band is positive; zero-band points are reported in the archived numeric unit
  and never divided by; channels without any positive band are listed and left
  to their absolute-error guards;
- utility: U = mean_c 0.5*[log1p(MSE_c) - log1p(MSE_anchor_c)]. The added 1 is
  an explicit dimensionless utility scale, not an assay variance or fitted
  parameter. Exact agreement (MSE_c = 0) is finite and accepted;
- focus protections: EGLC/ELAC normalized RMSE, |J15 residual| and |J4-J15
  secant-slope error| may not exceed the qualified fallback's values plus an
  allowance derived from the inherited comparison atol/rtol;
- a global worst-channel cap is kept as such (it is not per-species non-regression).

The inherited 84 multidate guards and their reserve stay hard constraints.
Invalid integrations are never scored; restoration ranks by guard violation
only and still needs a real replay to admit a seed.
"""

import ast
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

RELEASE_VERSION = "extracellular_first/2"
STAGES = ("matched_replay", "restoration", "phase_one", "search", "gradient", "gradient_reverse", "gradient_check")


class BudgetExhausted(Exception):
    def __init__(self, scope, requested):
        super().__init__(f"registered evaluation budget reached ({scope}, {requested} requested)")
        self.scope, self.requested = scope, requested


class ProbeFailure(Exception):
    def __init__(self, vector, row):
        super().__init__(f"invalid integration at attempt {row.get('attempt')}")
        self.vector, self.row = np.asarray(vector, float), row


class FreezeRequest(Exception):
    def __init__(self, coordinates, reason):
        super().__init__(f"{reason}: {coordinates}")
        self.coordinates, self.reason = list(coordinates), reason


class ResumeMismatch(Exception):
    pass


def plain(value):
    return json.loads(json.dumps(value, allow_nan=False))


def vector_key(vector):
    a = np.asarray(vector, dtype=float)
    if a.ndim != 1 or not np.isfinite(a).all():
        raise ValueError("finite one-dimensional log-factor vector required")
    return tuple(float(v) for v in a)


def context_fingerprint(*, design_sha256, observations_sha256, sources_sha256, profile, backend, scipy_version):
    """Identity of a complete simulation context; a cached row is reused only on equality.

    ``sources_sha256``: {relative path: sha256} of the TRANSITIVE local import closure
    of the evaluator (kernel, RHS, transport, positivity, solver, scoring), not only
    the evaluate wrapper.
    """
    text = json.dumps({"design": design_sha256, "observations": observations_sha256,
                       "sources": dict(sorted(sources_sha256.items())), "profile": profile, "backend": backend,
                       "scipy": scipy_version}, sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()


def local_import_closure(entry, roots):
    """Repo-local modules reachable from ``entry`` by static imports (ast; nothing is imported)."""
    roots = [Path(r) for r in roots]
    seen, stack = [], [Path(entry)]
    while stack:
        path = stack.pop()
        if path in seen:
            continue
        seen.append(path)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        names += [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module and n.level == 0]
        for name in names:
            for root in roots:
                candidate = root / (name.split(".")[0] + ".py")
                if candidate.exists():
                    stack.append(candidate)
                    break
    return sorted(seen)


def transitive_evidence(current, recorded):
    """Compare current closure hashes with hashes a campaign ITSELF recorded.

    Missing or different evidence makes cache reuse unqualified (replay instead).
    """
    recorded = {k.replace("\\", "/"): v for k, v in recorded.items()}
    missing = sorted(k for k in current if k not in recorded)
    changed = sorted(k for k in current if k in recorded and recorded[k] != current[k])
    return {"qualified": not missing and not changed, "missing": missing, "changed": changed}


def unit_status(observations):
    """Units are 'source_recorded' only if the archive itself records them."""
    units = observations.get("units") if isinstance(observations, dict) else None
    if isinstance(units, dict) and units and all(v == "mM" for v in units.values()):
        return {"status": "source_recorded_mM", "evidence": "observations.json units field"}
    return {"status": "assumed_mM_historical_model_convention",
            "evidence": "observations.json stores numeric arrays without a unit field; mM is the historical model "
                        "convention, not a source-verified unit; working bands are not assay SD"}


def activation_permitted(release, request=None):
    """A release with activation_allowed false is a prohibition: no explicit click overrides it."""
    if not isinstance(release, dict) or release.get("activation_allowed") is not True:
        return {"allowed": False, "reason": "release forbids activation (activation_allowed is not true)"}
    request = request or {}
    for key in ("dataset_sha256", "engine_context", "contract_fingerprint"):
        if not request.get(key) or request.get(key) != release.get("eligibility", {}).get(key):
            return {"allowed": False, "reason": f"{key} unknown or different"}
    if request.get("explicit") is not True:
        return {"allowed": False, "reason": "explicit user action required"}
    return {"allowed": True, "reason": "eligible release, identities match, explicit action"}


def feasible(row):
    return bool(row.get("valid") and row.get("reserved_guards_pass"))


def row_id(row):
    """New attempts are numbered; imported sealed evidence keeps its source id."""
    return row["attempt"] if row.get("attempt") is not None else row["source_id"]


class EventLog:
    """Append-only event log; on resume each regenerated event must match the checkpoint."""

    def __init__(self, expected=None, on_event=None):
        self.events, self.expected, self.on_event = [], expected, on_event

    def emit(self, event):
        event = plain(event)
        i = len(self.events)
        if self.expected is not None and i < len(self.expected) and self.expected[i] != event:
            raise ResumeMismatch(f"event {i} differs from the checkpoint")
        self.events.append(event)
        if self.on_event:
            self.on_event(self)

    def finish(self):
        if self.expected is not None and len(self.events) < len(self.expected):
            raise ResumeMismatch("checkpoint has more events than the replay")


def normalized_distance(a, b, lower, upper):
    return float(np.max(np.abs(np.asarray(a, float) - np.asarray(b, float)) / (np.asarray(upper) - np.asarray(lower))))


# ------------------------------------------------------------------ scoring
def extracellular_channels(names, external_pools):
    return [n for n in names if n in external_pools]


def channel_mse(prediction, panel, channels):
    """Band-normalized MSE per channel (None when no positive band)."""
    x, y, b = np.asarray(prediction, float), np.asarray(panel["target"]), np.asarray(panel["bands"])
    if x.shape != y.shape or not np.isfinite(x).all():
        raise ValueError("invalid concentration panel")
    names = list(panel["names"])
    out = {}
    for c in channels:
        i = names.index(c)
        mask = b[i] > 0
        out[c] = float(np.mean(((x[i, mask] - y[i, mask]) / b[i, mask]) ** 2)) if mask.any() else None
    return out


def focus_metrics(prediction, panel, channel):
    """Normalized RMSE, |J15 residual| and |J4-J15 secant-slope error| of one channel."""
    x, y, b = np.asarray(prediction, float), np.asarray(panel["target"]), np.asarray(panel["bands"])
    i, days = list(panel["names"]).index(channel), list(panel["days"])
    mask = b[i] > 0
    span = days[-1] - days[0]
    return {"normalized_rmse": float(np.sqrt(np.mean(((x[i, mask] - y[i, mask]) / b[i, mask]) ** 2))),
            "abs_J15_residual": float(abs(x[i, -1] - y[i, -1])),
            "abs_slope_error": float(abs((x[i, -1] - x[i, 0]) / span - (y[i, -1] - y[i, 0]) / span))}


def focus_caps(fallback_prediction, panel, channels, atol, rtol):
    """Caps = fallback metric + allowance, with delta_d = atol + rtol*|x_fallback,d|.

    Allowances (from the inherited element comparison atol + rtol*max(|a|,|b|), taken
    at the fallback so they do not depend on the candidate):
      RMSE:  sqrt(mean_d (delta_d / band_d)^2) over positive-band dates (RMS triangle bound)
      J15:   delta_J15
      slope: (delta_J4 + delta_J15) / (J15 - J4)
    """
    x, b = np.asarray(fallback_prediction, float), np.asarray(panel["bands"])
    days = list(panel["days"])
    caps = {}
    for c in channels:
        i = list(panel["names"]).index(c)
        mask = b[i] > 0
        if not mask.any():
            raise ValueError(f"focus channel {c} has no positive band")
        delta = atol + rtol * np.abs(x[i])
        allowance = {"normalized_rmse": float(np.sqrt(np.mean((delta[mask] / b[i, mask]) ** 2))),
                     "abs_J15_residual": float(delta[-1]),
                     "abs_slope_error": float((delta[0] + delta[-1]) / (days[-1] - days[0]))}
        base = focus_metrics(x, panel, c)
        caps[c] = {"fallback": base, "allowance": allowance,
                   "cap": {k: base[k] + allowance[k] for k in base}}
    return caps


def release_score(prediction, panel, channels, anchor_mse, focus=("EGLC", "ELAC"), units=None):
    x, y, b = np.asarray(prediction, float), np.asarray(panel["target"]), np.asarray(panel["bands"])
    names, days = list(panel["names"]), list(panel["days"])
    mse = channel_mse(x, panel, channels)
    per = {}
    for c in channels:
        i = names.index(c)
        mask = b[i] > 0
        per[c] = {"observed_mM": y[i].tolist(), "prediction_mM": x[i].tolist(),
                  "absolute_errors_mM": np.abs(x[i] - y[i]).tolist(),
                  "scored_days": [d for d, m in zip(days, mask) if m],
                  "zero_band_days": [d for d, m in zip(days, mask) if not m],
                  "normalized_residuals": [float((x[i, j] - y[i, j]) / b[i, j]) if mask[j] else None
                                           for j in range(len(days))],
                  "normalized_mse": mse[c],
                  "normalized_rmse": None if mse[c] is None else float(np.sqrt(mse[c]))}
    scored = [c for c in channels if mse[c] is not None and anchor_mse.get(c) is not None]
    if not scored:
        raise ValueError("no scored extracellular channel")
    rmse = np.array([per[c]["normalized_rmse"] for c in scored])
    primary = float(np.mean([0.5 * (np.log1p(mse[c]) - np.log1p(anchor_mse[c])) for c in scored]))
    dated = []
    for j in range(len(days)):
        r = [per[c]["normalized_residuals"][j] for c in scored if per[c]["normalized_residuals"][j] is not None]
        dated.append(float(np.sqrt(np.mean(np.square(r)))) if r else None)
    span = days[-1] - days[0]
    diagnostics = {}
    for c in focus:
        if c not in names:
            continue
        i = names.index(c)
        diagnostics[c] = {"J15_residual_mM": float(x[i, -1] - y[i, -1]),
                          "J15_normalized_residual": per[c]["normalized_residuals"][-1] if c in per else None,
                          "slope_predicted_mM_per_day": float((x[i, -1] - x[i, 0]) / span),
                          "slope_observed_mM_per_day": float((y[i, -1] - y[i, 0]) / span),
                          **(focus_metrics(x, panel, c) if (b[i] > 0).any() else {})}
    worst = int(np.argmax(rmse))
    return {"version": RELEASE_VERSION, "unit_status": units, "channels": list(channels), "scored_channels": scored,
            "unscored_channels": [c for c in channels if c not in scored], "per_channel": per,
            "primary": primary, "mean_normalized_rmse": float(np.mean(rmse)),
            "worst_normalized_rmse": float(rmse[worst]), "worst_channel": scored[worst],
            "dated_rms": dated, "focus": diagnostics}


def release_gradient(sensitivity, prediction, panel, channels, anchor_mse):
    """Chain rule on STORED concentration sensitivities (no ODE): d primary / d log factor.

    ``sensitivity``: a sealed sensitivity_round*.json (groups -> d_concentration_d_log_factor,
    pool_names, days). Groups without a stored column get a zero component.
    """
    names, days = list(panel["names"]), list(panel["days"])
    if list(sensitivity["pool_names"]) != names or list(sensitivity["days"]) != days:
        raise ValueError("stored sensitivity panel differs")
    x, y, b = np.asarray(prediction, float), np.asarray(panel["target"]), np.asarray(panel["bands"])
    mse = channel_mse(x, panel, channels)
    scored = [c for c in channels if mse[c] is not None and anchor_mse.get(c) is not None]
    gradient = []
    for group, entry in sensitivity["groups"].items():
        dx = np.asarray(entry["d_concentration_d_log_factor"], float)
        total = 0.0
        for c in scored:
            i = names.index(c)
            mask = b[i] > 0
            dmse = float(np.mean(2 * (x[i, mask] - y[i, mask]) / b[i, mask] ** 2 * dx[i, mask]))
            total += 0.5 * dmse / (1.0 + mse[c])  # d/dx 0.5*log1p(MSE): finite at MSE = 0
        gradient.append(total / len(scored))
    return np.array(gradient)


def focus_ok(score, caps):
    return all(score["focus"][c][k] <= caps[c]["cap"][k] for c in caps for k in caps[c]["cap"])


def release_admissible(row, score, worst_cap, caps=None):
    """84 reserved guards, GLOBAL worst-channel cap, and EGLC/ELAC focus protections."""
    return bool(feasible(row) and all(score["per_channel"][c]["normalized_rmse"] <= worst_cap
                                      for c in score["scored_channels"]) and focus_ok(score, caps or {}))


def rank_key(score):
    return (score["primary"], score["worst_normalized_rmse"])


# ------------------------------------------------------- context-safe store
class ContextStore:
    """Budget per stage group, bitwise cache keyed by (context, vector)."""

    def __init__(self, evaluate_many, *, context, limits, label_limits=None, rows=(), imported=()):
        self._evaluate_many = evaluate_many
        self.context = context
        self.limits = dict(limits)
        self.label_limits = dict(label_limits or {})
        self.by_label = {}
        self.cache, self.rows, self.trace_keys = {}, [], set()
        self.used = {g: 0 for g in self.limits}
        self.invalid = {g: 0 for g in self.limits}
        self.new_evaluations = 0
        for row in imported:
            if row.get("context") != context or row.get("attempt") is not None or not row.get("source_id"):
                raise ValueError("imported evidence must carry this context and a source id")
            self.cache.setdefault((context, vector_key(row["log_factors"])), row)
        for row in rows:
            self._admit(row, len(self.rows) + 1)

    def _admit(self, row, attempt):
        if row["attempt"] != attempt or row.get("context") != self.context:
            raise ValueError("non-consecutive attempt or foreign context")
        if row["group"] not in self.limits or row["stage"] not in STAGES:
            raise ValueError("unknown group or stage")
        k = (self.context, vector_key(row["log_factors"]))
        if k in self.trace_keys:
            raise ValueError("duplicate vector in trace")
        self.trace_keys.add(k)
        self.cache[k] = row
        self.rows.append(row)
        self.used[row["group"]] += 1
        self.by_label[row["label"]] = self.by_label.get(row["label"], 0) + 1
        self.invalid[row["group"]] += 0 if row["valid"] else 1
        if self.used[row["group"]] > self.limits[row["group"]] or \
                self.by_label[row["label"]] > self.label_limits.get(row["label"], float("inf")):
            raise ValueError("trace exceeds the registered budget")

    def lookup(self, vector):
        return self.cache.get((self.context, vector_key(vector)))

    def request(self, vectors, stage, group, label):
        if stage not in STAGES or group not in self.limits:
            raise ValueError("unknown stage or group")
        keys = [vector_key(v) for v in vectors]
        pending = [k for k in dict.fromkeys(keys) if (self.context, k) not in self.cache]
        if pending:
            if self.used[group] + len(pending) > self.limits[group]:
                raise BudgetExhausted(group, len(pending))
            if self.by_label.get(label, 0) + len(pending) > self.label_limits.get(label, float("inf")):
                raise BudgetExhausted(label, len(pending))
            jobs = [{"attempt": len(self.rows) + i + 1, "log_factors": list(k), "stage": stage, "group": group,
                     "label": label, "context": self.context} for i, k in enumerate(pending)]
            rows = self._evaluate_many(jobs)
            if len(rows) != len(jobs):
                raise RuntimeError("evaluator returned a different number of rows")
            for job, row in zip(jobs, rows):
                if any(row[k] != job[k] for k in ("attempt", "stage", "group", "label", "context")) \
                        or vector_key(row["log_factors"]) != vector_key(job["log_factors"]):
                    raise RuntimeError("evaluator returned a different job")
                self._admit(row, job["attempt"])
                self.new_evaluations += 1
        return [self.cache[(self.context, k)] for k in keys]


# --------------------------------------------------------------- restoration
def project_step(desired, x, lower, upper, g0, jg, margin, radius, scale):
    """Closest step to ``desired`` satisfying the LINEAR guard model (no ODE).

    min ||d - desired||^2  s.t.  (g0 + jg d + margin)/scale <= 0, box, |d|_inf <= radius.
    The result is a proposal; feasibility is decided only by a replay.
    """
    x, desired = np.asarray(x, float), np.asarray(desired, float)
    g0, jg, margin, scale = (np.asarray(v, float) for v in (g0, jg, margin, scale))
    lo, hi = np.maximum(np.asarray(lower) - x, -radius), np.minimum(np.asarray(upper) - x, radius)
    start = np.clip(desired, lo, hi)
    result = minimize(lambda d: 0.5 * float(np.sum((d - desired) ** 2)), start, jac=lambda d: d - desired,
                      method="SLSQP", bounds=list(zip(lo, hi)),
                      constraints=[{"type": "ineq", "fun": lambda d: -(g0 + jg @ d + margin) / scale,
                                    "jac": lambda d: -jg / scale[:, None]}],
                      options={"ftol": 1e-12, "maxiter": 200})
    d = np.clip(result.x, lo, hi)
    return d, {"success": bool(result.success), "message": str(result.message),
               "linear_max_scaled_violation": float(np.max((g0 + jg @ d + margin) / scale))}


def violation(guards, margin):
    """Phase-I ranking only: never used as a biochemical loss."""
    return float(np.sum(np.maximum(np.asarray(guards, float) + np.asarray(margin, float), 0.0) ** 2))


def broyden(jg, dx, dg):
    dx, dg = np.asarray(dx, float), np.asarray(dg, float)
    denominator = float(dx @ dx)
    return jg if denominator == 0 else jg + np.outer(dg - jg @ dx, dx) / denominator


def outward_zeroed(d, x, lower, upper, tolerance=1e-12):
    d = np.array(d, float)
    d[(x <= lower + tolerance) & (d < 0)] = 0.0
    d[(x >= upper - tolerance) & (d > 0)] = 0.0
    return d


def restore_seeds(store, directions, *, lower, upper, guard_names, margin, scale, spec, emit, admit=None):
    """Backtracking along projected joint directions, then Phase-I if needed.

    ``directions``: list of dicts {name, anchor_row, guard_jacobian, direction}.
    Returns (seeds, records). A seed is admitted only from a replayed row that is
    reserved-feasible and separated from anchors and earlier seeds.
    """
    lower, upper = np.asarray(lower, float), np.asarray(upper, float)
    admit = admit or feasible  # release admission (focus protections) may be stricter than guard feasibility
    anchors = [np.array(d["anchor_row"]["log_factors"], float) for d in directions]
    seeds, records = [], []
    separation = float(spec["minimum_normalized_separation"])

    def separated(v):
        others = anchors + [np.array(s["log_factors"], float) for s in seeds]
        return min(normalized_distance(v, o, lower, upper) for o in others) >= separation

    def guards_of(row):
        return np.array([row["feasibility_guards"][k] for k in guard_names], float)

    for item in directions:
        if len(seeds) >= int(spec["target_seeds"]):
            break
        x0 = np.array(item["anchor_row"]["log_factors"], float)
        g0, jg = guards_of(item["anchor_row"]), np.array(item["guard_jacobian"], float)
        record = {"name": item["name"], "anchor_attempt": row_id(item["anchor_row"]),
                  "anchor_label": item.get("anchor_label"), "trials": [], "status": None}
        records.append(record)
        d = outward_zeroed(item["direction"], x0, lower, upper)
        if not np.isfinite(d).all() or np.max(np.abs(d)) == 0:
            record["status"] = "degenerate_direction"
            emit({"event": "restoration", "name": item["name"], "status": record["status"]})
            continue
        d = float(spec["radius_log"]) * d / np.max(np.abs(d))
        step, projection = project_step(d, x0, lower, upper, g0, jg, margin, float(spec["radius_log"]), scale)
        record["projection"] = projection
        used, accepted, trials = 0, None, []
        try:
            for alpha in spec["backtracking_fractions"]:
                v = np.clip(x0 + alpha * step, lower, upper)
                if not separated(v):
                    record["trials"].append({"alpha": alpha, "status": "not_separated"})
                    break
                if used >= int(spec["max_evaluations_per_direction"]):
                    break
                row = store.request([v], "restoration", "restoration", item["name"])[0]
                used += 1
                trials.append(row)
                record["trials"].append({"alpha": alpha, "attempt": row_id(row), "valid": row["valid"],
                                         "feasible": feasible(row),
                                         "violation": violation(guards_of(row), margin) if row["valid"] else None})
                if admit(row):
                    accepted = row
                    break
            valid = [r for r in trials if r["valid"]]
            if accepted is None and valid and int(spec["phase_one_iterations"]) > 0:
                current = min(valid, key=lambda r: (violation(guards_of(r), margin), str(row_id(r))))
                xt, gt, j_est = np.array(current["log_factors"], float), guards_of(current), jg
                for k in range(int(spec["phase_one_iterations"])):
                    if used >= int(spec["max_evaluations_per_direction"]):
                        break
                    dk, info = project_step(np.zeros_like(xt), xt, lower, upper, gt, j_est, margin,
                                            float(spec["radius_log"]), scale)
                    v = np.clip(xt + dk, lower, upper)
                    if not np.any(v != xt) or not separated(v):
                        record["trials"].append({"phase_one": k + 1, "status": "no_separated_step"})
                        break
                    row = store.request([v], "phase_one", "restoration", item["name"])[0]
                    used += 1
                    entry = {"phase_one": k + 1, "attempt": row_id(row), "valid": row["valid"],
                             "feasible": feasible(row), "linear_violation": info["linear_max_scaled_violation"]}
                    record["trials"].append(entry)
                    if not row["valid"]:
                        entry["violation"] = None
                        break  # no derivative or step from an invalid integration
                    g_new = guards_of(row)
                    entry["violation"] = violation(g_new, margin)
                    j_est = broyden(j_est, v - xt, g_new - gt)
                    xt, gt = v, g_new
                    if feasible(row):
                        accepted = row
                        break
        except BudgetExhausted:
            record["status"] = "restoration_budget_exhausted"
            emit({"event": "restoration", "name": item["name"], "status": record["status"]})
            break
        if accepted is not None and separated(np.array(accepted["log_factors"], float)) and admit(accepted):
            seeds.append(accepted)
            record.update(status="feasible_seed", seed_attempt=row_id(accepted))
        elif accepted is not None and not admit(accepted):
            record["status"] = "guard_feasible_but_release_inadmissible"
        else:
            record["status"] = record["status"] or "not_restored"
        record["evaluations"] = used
        emit({"event": "restoration", "name": item["name"], "status": record["status"],
              "seed_attempt": record.get("seed_attempt")})
    return seeds, records


# -------------------------------------------------------------------- search
class ReleaseSearch:
    """SLSQP on the release primary with scaled hard guards and worst-channel caps."""

    def __init__(self, store, *, lower, upper, guard_names, margin, scale, worst_cap, scorer, spec, gain, log,
                 caps=None):
        self.store, self.lower, self.upper = store, np.asarray(lower, float), np.asarray(upper, float)
        self.guard_names, self.margin, self.scale = list(guard_names), np.asarray(margin, float), np.asarray(scale, float)
        self.worst_cap, self.scorer, self.s, self.gain = float(worst_cap), scorer, spec, float(gain)
        self.caps = caps or {}
        self._emit = log.emit
        self.jacobians, self.incumbent, self.incumbent_score = [], None, None
        self.channels = None

    def values(self, row):
        """[objective, constraints...] with SLSQP >= 0 convention."""
        score = self.scorer(row)
        if self.channels is None:
            self.channels = list(score["scored_channels"])
        if score["scored_channels"] != self.channels:
            raise ValueError("scored channel set changed")
        g = np.array([row["feasibility_guards"][k] for k in self.guard_names], float)
        mse = np.array([score["per_channel"][c]["normalized_mse"] for c in self.channels])
        cap = self.worst_cap ** 2
        # Focus protections in smooth squared form: metric^2 <= cap^2, scaled by cap^2.
        focus = [(self.caps[c]["cap"][k] ** 2 - score["focus"][c][k] ** 2) / self.caps[c]["cap"][k] ** 2
                 for c in sorted(self.caps) for k in ("normalized_rmse", "abs_J15_residual", "abs_slope_error")]
        return np.r_[score["primary"], -(g + self.margin) / self.scale, (cap - mse) / cap, focus]

    def _consider(self, row, state, source):
        ok, objective = False, None
        if row["valid"]:
            score = self.scorer(row)
            objective = score["primary"]
            ok = release_admissible(row, score, self.worst_cap, self.caps)
        updated = {"start": False, "incumbent": False}
        if ok:
            if state["best"] is None or objective < state["best_objective"] - self.gain:
                state["best"], state["best_objective"], updated["start"] = row, objective, True
            if self.incumbent is None or objective < self.incumbent_score - self.gain:
                self.incumbent, self.incumbent_score, updated["incumbent"] = row, objective, True
        self._emit({"event": "objective", "start": state["name"], "source": source, "attempt": row_id(row),
                    "valid": bool(row["valid"]), "admissible": ok, "primary": objective,
                    "start_best_updated": updated["start"], "incumbent_updated": updated["incumbent"]})

    def _jacobian(self, state, x, anchor):
        name, free = state["name"], list(state["free"])
        v0 = self.values(anchor)
        step = float(self.s["difference_step_log"])
        h = {}
        for i in free:
            h[i] = step if x[i] + step <= self.upper[i] else -step
            if not self.lower[i] <= x[i] + h[i] <= self.upper[i]:
                raise FreezeRequest([i], "no in-box difference step")

        def probe(i, delta):
            v = x.copy()
            v[i] = x[i] + delta
            return v

        rows = dict(zip(free, self.store.request([probe(i, h[i]) for i in free], "gradient", "search", name)))
        back = [i for i in free if not rows[i]["valid"] and self.lower[i] <= x[i] - h[i] <= self.upper[i]]
        if back:
            for i, row in zip(back, self.store.request([probe(i, -h[i]) for i in back], "gradient_reverse", "search", name)):
                if row["valid"]:
                    rows[i] = row
        unavailable = [i for i in free if not rows[i]["valid"]]
        jac = np.zeros((len(v0), len(x)))
        record = {"start": name, "anchor_attempt": row_id(anchor), "anchor_vector": x.tolist(),
                  "free": free, "columns": {}, "unavailable": unavailable}
        for i in free:
            if i in unavailable:
                continue
            dx = rows[i]["log_factors"][i] - x[i]
            jac[:, i] = (self.values(rows[i]) - v0) / dx
            record["columns"][str(i)] = {"attempt": row_id(rows[i]), "step_log": dx}
        failed = []
        if not state["checked"] and not unavailable:
            state["checked"] = True
            lead = sorted(free, key=lambda i: (-abs(jac[0, i]), i))[:int(self.s["check_leading_groups"])]
            small = self.store.request([probe(i, (rows[i]["log_factors"][i] - x[i]) * float(self.s["check_step_log"])
                                              / step) for i in lead], "gradient_check", "search", name)
            record["check"] = {}
            for i, row in zip(lead, small):
                dx = row["log_factors"][i] - x[i]
                entry = {"attempt": row_id(row), "step_log": dx, "passed": False}
                if row["valid"]:
                    d3 = (self.values(row)[0] - v0[0]) / dx
                    d6 = jac[0, i]
                    entry.update(d006=float(d6), d003=float(d3), passed=bool(
                        abs(d6 - d3) <= float(self.s["check_rtol"]) * max(abs(d6), abs(d3)) + float(self.s["check_atol"])))
                if not entry["passed"]:
                    failed.append(i)
                record["check"][str(i)] = entry
        row_norms = np.linalg.norm(jac[1:], axis=1)
        record["constraint_scaling"] = {"max_row_norm": float(np.max(row_norms, initial=0.0)),
                                        "min_nonzero_row_norm": float(np.min(row_norms[row_norms > 0], initial=0.0))}
        record["jacobian"] = jac.tolist()
        self.jacobians.append(plain(record))
        self._emit({"event": "jacobian", "start": name, "index": len(self.jacobians) - 1,
                    "unavailable": unavailable, "check_failed": failed})
        if unavailable:
            raise FreezeRequest(unavailable, "derivative unavailable after forward and reverse probes")
        if failed:
            raise FreezeRequest(failed, "0.006/0.003 derivative check failed")
        return jac

    def _segment(self, state, box_lo, box_hi):
        name, free = state["name"], np.array(state["free"], dtype=int)
        base = np.array(state["best"]["log_factors"], float)

        def full(z):
            x = base.copy()
            x[free] = z
            return np.clip(x, box_lo, box_hi)

        def row_at(z, source):
            x = full(z)
            row = self.store.lookup(x) or self.store.request([x], "search", "search", name)[0]
            k = vector_key(x)
            if k not in state["seen"]:
                state["seen"].add(k)
                self._consider(row, state, source)
            if not row["valid"]:
                raise ProbeFailure(x, row)
            return row, x

        def objective(z):
            return float(self.values(row_at(z, "objective")[0])[0])

        def gradient(z):
            row, x = row_at(z, "gradient")
            return self._jacobian(state, x, row)[0, free]

        def constraints(z):
            return self.values(row_at(z, "constraint")[0])[1:]

        def constraints_jacobian(z):
            row, x = row_at(z, "constraint_jacobian")
            return self._jacobian(state, x, row)[1:][:, free]

        def callback(intermediate_result):
            state["iterations"] += 1
            improved = row_id(state["best"]) != state["best_at_iterate"]
            state["best_at_iterate"] = row_id(state["best"])
            state["stall"] = 0 if improved else state["stall"] + 1
            self._emit({"event": "iterate", "start": name, "iteration": state["iterations"],
                        "start_best_attempt": row_id(state["best"]), "stall": state["stall"]})
            if state["stall"] >= int(self.s["stagnation_iterations"]):
                state["stop"] = "stagnation"
                raise StopIteration

        result = minimize(objective, base[free], jac=gradient, method="SLSQP",
                          bounds=[(float(box_lo[i]), float(box_hi[i])) for i in free],
                          constraints=[{"type": "ineq", "fun": constraints, "jac": constraints_jacobian}],
                          options={"ftol": float(self.s["slsqp"]["ftol"]), "maxiter": int(self.s["slsqp"]["maxiter"])},
                          callback=callback)
        return {"status": int(result.status), "message": str(result.message), "nit": int(result.nit)}

    def run_start(self, name, row):
        state = {"name": name, "best": None, "best_objective": None, "free": list(range(len(self.lower))),
                 "checked": False, "seen": {vector_key(row["log_factors"])}, "iterations": 0, "stall": 0,
                 "best_at_iterate": row_id(row), "stop": None}
        summary = {"name": name, "start_attempt": row_id(row), "segments": [], "frozen": [], "stop_reason": None}
        self._consider(row, state, "start")
        if state["best"] is None:
            summary["stop_reason"] = "start_not_release_admissible"
        else:
            box_lo, box_hi = self.lower.copy(), self.upper.copy()
            for segment in range(1, int(self.s["max_segments_per_start"]) + 1):
                if not state["free"]:
                    summary["stop_reason"] = "no_free_coordinates"
                    break
                record = {"segment": segment, "free": list(state["free"])}
                try:
                    record.update(self._segment(state, box_lo, box_hi))
                    summary["segments"].append(record)
                    summary["stop_reason"] = state["stop"] or f"slsqp_exit_{record['status']}"
                    break
                except FreezeRequest as error:
                    state["free"] = [i for i in state["free"] if i not in error.coordinates]
                    summary["frozen"].append({"coordinates": error.coordinates, "reason": error.reason})
                    record["ended_by"] = "freeze"
                except ProbeFailure as error:
                    centre = np.array(state["best"]["log_factors"], float)
                    radius = float(self.s["failure_radius_fraction"]) * float(np.max(np.abs(error.vector - centre)))
                    record.update(ended_by="probe_failure", failed_attempt=row_id(error.row), new_radius_log=radius)
                    if radius < float(self.s["minimum_box_radius_log"]):
                        summary["segments"].append(record)
                        summary["stop_reason"] = "probe_failure_radius_exhausted"
                        break
                    box_lo, box_hi = np.maximum(self.lower, centre - radius), np.minimum(self.upper, centre + radius)
                except BudgetExhausted as error:
                    record["ended_by"] = f"budget_{error.scope}"
                    summary["segments"].append(record)
                    summary["stop_reason"] = f"budget_{error.scope}"
                    break
                summary["segments"].append(record)
                self._emit({"event": "segment_restart", "start": name, "ended_by": record["ended_by"]})
            else:
                summary["stop_reason"] = "segment_limit"
        summary.update(best_attempt=row_id(state["best"]) if state["best"] else None,
                       best_vector=state["best"]["log_factors"] if state["best"] else None,
                       best_primary=state["best_objective"])
        self._emit({"event": "start_end", "start": name, "stop_reason": summary["stop_reason"],
                    "best_attempt": summary["best_attempt"]})
        return summary


# ------------------------------------------------------------------ release
def select_release(candidates, *, gain):
    """Pick ONE complete qualified vector; never combine curves of different vectors.

    ``candidates``: dicts {id, kind ('fallback'|'new'), qualified, admissible,
    score (strict), log_factors}. The fallback is the best qualified admissible
    fallback; a new candidate replaces it only with a primary gain above
    log1p(gain) and no worse worst channel.
    """
    fallbacks = sorted((c for c in candidates if c["kind"] == "fallback" and c["qualified"] and c["admissible"]),
                       key=lambda c: (*rank_key(c["score"]), c["id"]))
    if not fallbacks:
        return {"status": "blocked_no_qualified_candidate", "selected": None,
                "reason": "no qualified admissible fallback; qualify the working centre or candidate35 first"}
    fallback = fallbacks[0]
    better = sorted((c for c in candidates if c["kind"] == "new" and c["qualified"] and c["admissible"]
                     and c["score"]["primary"] < fallback["score"]["primary"] - np.log1p(gain)
                     and c["score"]["worst_normalized_rmse"] <= fallback["score"]["worst_normalized_rmse"]),
                    key=lambda c: (*rank_key(c["score"]), c["id"]))
    chosen = better[0] if better else fallback
    return {"status": "provisional_extracellular_reference", "selected": chosen,
            "fallback_id": fallback["id"], "improved_over_fallback": bool(better)}
