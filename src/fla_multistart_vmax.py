"""Constrained multistart Vmax-only search (SLSQP on an epigraph). No ODE here.

The caller injects ``evaluate_many(jobs) -> rows``: it integrates (or reuses a
completed folder for) each requested log-factor vector and returns a scored
row in the format of ``scripts/run_corrected_vmax.py``. This module owns

- the distinct-evaluation budget and the bitwise vector cache;
- forward finite-difference Jacobians (step reversed at the upper bound), the
  0.006/0.003 check of the leading groups, and freezing of coordinates whose
  derivative is unavailable or inconsistent;
- the SLSQP problem: minimise t subject to t - side_k(x) >= 0 (inherited
  absolute ATP/ADP J15 log minimax) and -reserve_i - g_i(x) >= 0 (hard guards,
  same signs as ``fla_temporal_vmax.lp_step``), inside the original box;
- failure handling: an invalid integration is never scored; it aborts the
  SLSQP segment and halves the box radius around the start's best feasible
  point (failed probes constrain the next steps);
- incumbent rules: only valid, reserved-guard-feasible rows requested by the
  optimizer (start, line search or iterate), never finite-difference probes,
  and only with an objective gain above the inherited threshold;
- deterministic seeds from bounded joint directions and finalist selection.

Replaying the same rows reproduces the same SLSQP path without integration;
that is how a campaign resumes.
"""

import json

import numpy as np
from scipy.optimize import minimize

STAGES = ("replay", "seed", "slsqp", "gradient", "gradient_reverse", "gradient_check")


class BudgetExhausted(Exception):
    def __init__(self, scope, requested):
        super().__init__(f"registered evaluation budget reached ({scope}, {requested} requested)")
        self.scope, self.requested = scope, requested


class ProbeFailure(Exception):
    def __init__(self, vector, row):
        super().__init__(f"invalid integration at attempt {row.get('attempt')}: {row.get('error')}")
        self.vector, self.row = np.asarray(vector, float), row


class FreezeRequest(Exception):
    def __init__(self, coordinates, reason):
        super().__init__(f"{reason}: {coordinates}")
        self.coordinates, self.reason = list(coordinates), reason


class ResumeMismatch(Exception):
    pass


def vector_key(vector):
    a = np.asarray(vector, dtype=float)
    if a.ndim != 1 or not np.isfinite(a).all():
        raise ValueError("finite one-dimensional log-factor vector required")
    return tuple(float(v) for v in a)


def plain(value):
    return json.loads(json.dumps(value, allow_nan=False))


def feasible(row):
    return bool(row.get("valid") and row.get("reserved_guards_pass"))


def row_values(row, side_names, guard_names):
    sides, guards = row["absolute"]["sides"], row["feasibility_guards"]
    if list(sides) != list(side_names) or list(guards) != list(guard_names):
        raise ValueError("objective sides or guard names/order changed")
    return (np.array([sides[k] for k in side_names], dtype=float),
            np.array([guards[k] for k in guard_names], dtype=float))


def constraint_vector(t, sides, guards, margin):
    """SLSQP inequality convention (>= 0): epigraph rows, then hard guard rows."""
    return np.r_[t - np.asarray(sides, float), -np.asarray(margin, float) - np.asarray(guards, float)]


def constraint_jacobian(side_jacobian, guard_jacobian, free):
    free = np.asarray(free, dtype=int)
    js, jg = np.asarray(side_jacobian, float)[:, free], np.asarray(guard_jacobian, float)[:, free]
    return np.vstack((np.column_stack((-js, np.ones(len(js)))),
                      np.column_stack((-jg, np.zeros(len(jg))))))


class EvaluationStore:
    """Distinct-vector budget, bitwise cache and attempt ledger."""

    def __init__(self, evaluate_many, *, limit, start_limits, rows=()):
        if sum(start_limits.values()) > limit:
            raise ValueError("start limits exceed the global limit")
        self._evaluate_many = evaluate_many
        self.limit = int(limit)
        self.start_limits = dict(start_limits)
        self.cache, self.rows = {}, []
        self.used = {name: 0 for name in self.start_limits}
        self.new_evaluations = 0
        for row in rows:
            self._admit(row, len(self.rows) + 1)

    def _admit(self, row, attempt):
        if row["attempt"] != attempt:
            raise ValueError("non-consecutive attempt numbering")
        if row["stage"] not in STAGES or row["start"] not in self.used:
            raise ValueError("unknown stage or start")
        k = vector_key(row["log_factors"])
        if k in self.cache:
            raise ValueError("duplicate vector in trace")
        self.cache[k] = row
        self.rows.append(row)
        self.used[row["start"]] += 1
        if len(self.rows) > self.limit or self.used[row["start"]] > self.start_limits[row["start"]]:
            raise ValueError("trace exceeds the registered budget")

    def request(self, vectors, stage, start):
        if stage not in STAGES:
            raise ValueError("unknown stage")
        keys = [vector_key(v) for v in vectors]
        pending = [k for k in dict.fromkeys(keys) if k not in self.cache]
        if pending:
            # Refuse the whole batch before launching anything.
            if len(self.rows) + len(pending) > self.limit:
                raise BudgetExhausted("global", len(pending))
            if self.used[start] + len(pending) > self.start_limits[start]:
                raise BudgetExhausted(start, len(pending))
            jobs = [{"attempt": len(self.rows) + i + 1, "log_factors": list(k), "stage": stage, "start": start}
                    for i, k in enumerate(pending)]
            rows = self._evaluate_many(jobs)
            if len(rows) != len(jobs):
                raise RuntimeError("evaluator returned a different number of rows")
            for job, row in zip(jobs, rows):
                if (row["attempt"], row["stage"], row["start"]) != (job["attempt"], stage, start) \
                        or vector_key(row["log_factors"]) != vector_key(job["log_factors"]):
                    raise RuntimeError("evaluator returned a different job")
                self._admit(row, job["attempt"])
                self.new_evaluations += 1
        return [self.cache[k] for k in keys]


def joint_seeds(anchor, lower, upper, *, objective_jacobian, side_names, active_side,
                guard_jacobian, guard_slack, radius, guard_count, random_seed, tolerance):
    """At most three deterministic seeds along bounded joint directions.

    Directions: descent of the active objective side, relief of the
    ``guard_count`` most binding guards, and one reproducible uniform draw.
    Components pushing a coordinate already at a bound outward are zeroed;
    the direction is scaled to ``radius`` in the max norm and clipped to the
    original box. Seeds are proposals only, never admissible before replay.
    """
    x, lo, hi = (np.asarray(v, float) for v in (anchor, lower, upper))
    jo, jg = np.asarray(objective_jacobian, float), np.asarray(guard_jacobian, float)
    if jo.shape != (len(side_names), len(x)) or jg.shape != (len(guard_slack), len(x)):
        raise ValueError("stored Jacobian shape mismatch")
    a = list(side_names).index(active_side)
    binding = np.argsort(np.asarray(guard_slack, float), kind="stable")[:guard_count]
    relief = -sum(jg[k] / max(np.linalg.norm(jg[k]), np.finfo(float).tiny) for k in binding)
    rng = np.random.default_rng(random_seed)
    directions = [("seed_objective_descent", -jo[a]), ("seed_guard_relief", relief),
                  ("seed_random", rng.uniform(-1.0, 1.0, len(x)))]
    seeds = []
    for name, d in directions:
        d = np.array(d, float)
        d[(x <= lo + tolerance) & (d < 0)] = 0.0
        d[(x >= hi - tolerance) & (d > 0)] = 0.0
        scale = np.max(np.abs(d)) if np.isfinite(d).all() else 0.0
        if scale == 0:
            seeds.append({"name": name, "status": "degenerate_direction", "vector": None, "direction": None})
            continue
        d = d / scale
        seeds.append({"name": name, "status": "constructed", "direction": d.tolist(),
                      "vector": np.clip(x + radius * d, lo, hi).tolist(),
                      "binding_guards": [int(k) for k in binding] if name == "seed_guard_relief" else None})
    return seeds


class MultistartSearch:
    """Deterministic driver. Raises nothing for budget exhaustion; reports it."""

    def __init__(self, store, *, lower, upper, side_names, guard_names, reserve, search,
                 expected_events=None, on_event=None):
        self.store = store
        self.lower, self.upper = np.asarray(lower, float), np.asarray(upper, float)
        self.side_names, self.guard_names = list(side_names), list(guard_names)
        self.reserve = np.asarray(reserve, float)
        if self.reserve.shape != (len(self.guard_names),) or np.any(self.reserve < 0):
            raise ValueError("one nonnegative reserve per guard required")
        self.s = search
        self.margin = self.reserve * float(search["optimizer_reserve_multiplier"])
        self.gain = float(search["minimum_step_objective_gain"])
        self.expected = expected_events
        self.on_event = on_event
        self.events, self.jacobians = [], []
        self.incumbent = None
        self.global_stop = None

    # -- bookkeeping -------------------------------------------------------
    def _emit(self, event):
        event = plain(event)
        i = len(self.events)
        if self.expected is not None and i < len(self.expected) and self.expected[i] != event:
            raise ResumeMismatch(f"event {i} differs from the checkpoint")
        self.events.append(event)
        if self.on_event:
            self.on_event(self)

    def _values(self, row):
        return row_values(row, self.side_names, self.guard_names)

    def _consider(self, row, state, segment, source):
        ok = feasible(row)
        start_updated = global_updated = False
        objective = row["absolute"]["objective"] if row.get("valid") else None
        if ok:
            if state["best"] is None or objective < state["best"]["absolute"]["objective"] - self.gain:
                state["best"], start_updated = row, True
            if self.incumbent is None or objective < self.incumbent["absolute"]["objective"] - self.gain:
                self.incumbent, global_updated = row, True
        self._emit({"event": "objective", "start": state["name"], "segment": segment, "source": source,
                    "attempt": row["attempt"], "valid": bool(row.get("valid")), "feasible": ok,
                    "objective": objective, "start_best_updated": start_updated,
                    "incumbent_updated": global_updated,
                    "incumbent_attempt": self.incumbent["attempt"] if self.incumbent else None})

    # -- derivatives -------------------------------------------------------
    def _steps(self, x, free, step):
        h = {}
        for i in free:
            hi = step if x[i] + step <= self.upper[i] else -step
            if not self.lower[i] <= x[i] + hi <= self.upper[i]:
                raise FreezeRequest([i], "no in-box difference step")
            h[i] = hi
        return h

    def _probe(self, x, i, h):
        v = x.copy()
        v[i] = x[i] + h
        return v

    def _jacobian(self, state, x, anchor):
        name, free = state["name"], list(state["free"])
        s0, g0 = self._values(anchor)
        step = float(self.s["difference_step_log"])
        h = self._steps(x, free, step)
        rows = dict(zip(free, self.store.request([self._probe(x, i, h[i]) for i in free], "gradient", name)))
        reversed_ = [i for i in free if not rows[i]["valid"] and self.lower[i] <= x[i] - h[i] <= self.upper[i]]
        if reversed_:
            again = self.store.request([self._probe(x, i, -h[i]) for i in reversed_], "gradient_reverse", name)
            for i, row in zip(reversed_, again):
                if row["valid"]:
                    rows[i] = row
        unavailable = [i for i in free if not rows[i]["valid"]]
        js, jg = np.zeros((len(s0), len(x))), np.zeros((len(g0), len(x)))
        record = {"start": name, "anchor_attempt": anchor["attempt"], "free": free, "columns": {}}
        for i in free:
            if i in unavailable:
                continue
            dx = rows[i]["log_factors"][i] - x[i]
            sp, gp = self._values(rows[i])
            js[:, i], jg[:, i] = (sp - s0) / dx, (gp - g0) / dx
            record["columns"][str(i)] = {"attempt": rows[i]["attempt"], "step_log": dx}
        record["unavailable"] = unavailable
        check_failed = []
        if not state["checked"] and not unavailable:
            state["checked"] = True
            check_failed, record["check"] = self._check(state, x, anchor, js, jg, rows)
        record["side_jacobian"], record["guard_jacobian"] = js.tolist(), jg.tolist()
        self.jacobians.append(plain(record))
        self._emit({"event": "jacobian", "start": name, "anchor_attempt": anchor["attempt"],
                    "index": len(self.jacobians) - 1, "unavailable": unavailable, "check_failed": check_failed})
        if unavailable:
            raise FreezeRequest(unavailable, "derivative unavailable after forward and reverse probes")
        if check_failed:
            raise FreezeRequest(check_failed, "0.006/0.003 derivative check failed")
        return js, jg

    def _check(self, state, x, anchor, js, jg, rows):
        s0, g0 = self._values(anchor)
        active = int(np.argmax(s0))
        free = list(state["free"])
        lead = sorted(free, key=lambda i: (-abs(js[active, i]), i))[:int(self.s["check_leading_groups"])]
        binding = [int(k) for k in np.argsort(-self.margin - g0, kind="stable")[:int(self.s["check_binding_guards"])]]
        ratio = float(self.s["check_step_log"]) / float(self.s["difference_step_log"])
        probes = [self._probe(x, i, (rows[i]["log_factors"][i] - x[i]) * ratio) for i in lead]
        small = self.store.request(probes, "gradient_check", state["name"])
        rtol, atol = float(self.s["check_rtol"]), float(self.s["check_atol_per_log"])
        report, failed = {"active_side": self.side_names[active], "binding_guards": [self.guard_names[k] for k in binding],
                          "groups": {}}, []
        for i, row in zip(lead, small):
            entry = {"attempt": row["attempt"], "step_log": row["log_factors"][i] - x[i]}
            if not row["valid"]:
                entry.update(passed=False, reason="check probe invalid")
            else:
                sp, gp = self._values(row)
                dx = entry["step_log"]
                d3 = np.r_[(sp[active] - s0[active]) / dx, (gp[binding] - g0[binding]) / dx]
                d6 = np.r_[js[active, i], jg[binding, i]]
                tol = rtol * np.maximum(np.abs(d6), np.abs(d3)) + atol
                entry.update(passed=bool(np.all(np.abs(d6 - d3) <= tol)), d006=d6.tolist(), d003=d3.tolist())
            if not entry["passed"]:
                failed.append(i)
            report["groups"][str(i)] = entry
        return failed, report

    # -- one SLSQP segment ---------------------------------------------------
    def _segment(self, state, segment, box_lo, box_hi):
        name, free = state["name"], np.array(state["free"], dtype=int)
        base = np.array(state["best"]["log_factors"], float)

        def full(z):
            x = base.copy()
            x[free] = np.asarray(z, float)[:-1]
            return np.clip(x, box_lo, box_hi)

        def row_at(z, source):
            x = full(z)
            row = self.store.request([x], "slsqp", name)[0]
            k = vector_key(x)
            if k not in state["seen"]:
                state["seen"].add(k)
                self._consider(row, state, segment, source)
            if not row["valid"]:
                raise ProbeFailure(x, row)
            return row, x

        def constraints(z):
            row, _ = row_at(z, "constraint")
            s, g = self._values(row)
            return constraint_vector(float(z[-1]), s, g, self.margin)

        def constraints_jacobian(z):
            row, x = row_at(z, "jacobian")
            js, jg = self._jacobian(state, x, row)
            return constraint_jacobian(js, jg, free)

        def callback(intermediate_result):
            row, _ = row_at(intermediate_result.x, "iterate")
            state["iterations"] += 1
            improved = state["best"]["attempt"] != state["best_at_iterate"]
            state["best_at_iterate"] = state["best"]["attempt"]
            state["stall"] = 0 if improved else state["stall"] + 1
            self._emit({"event": "iterate", "start": name, "segment": segment, "iteration": state["iterations"],
                        "attempt": row["attempt"], "t": float(intermediate_result.x[-1]),
                        "start_best_attempt": state["best"]["attempt"], "stall": state["stall"]})
            if state["stall"] >= int(self.s["stagnation_iterations"]):
                state["stop"] = "stagnation"
                raise StopIteration

        n = len(free) + 1
        e_last = np.zeros(n)
        e_last[-1] = 1.0
        z0 = np.r_[base[free], state["best"]["absolute"]["objective"]]
        bounds = [(float(box_lo[i]), float(box_hi[i])) for i in free] + [(None, None)]
        result = minimize(lambda z: float(z[-1]), z0, jac=lambda z: e_last.copy(), method="SLSQP", bounds=bounds,
                          constraints=[{"type": "ineq", "fun": constraints, "jac": constraints_jacobian}],
                          options={"ftol": float(self.s["slsqp"]["ftol"]), "maxiter": int(self.s["slsqp"]["maxiter"])},
                          callback=callback)
        names = [f"epigraph:{k}" for k in self.side_names] + self.guard_names
        multipliers = np.asarray(getattr(result, "multipliers", np.zeros(len(names))), float)
        top = [(names[k], float(multipliers[k])) for k in np.argsort(-np.abs(multipliers), kind="stable")[:10]
               if multipliers[k] != 0]
        return {"status": int(result.status), "message": str(result.message), "nit": int(result.nit),
                "largest_multipliers": top}

    # -- one start -----------------------------------------------------------
    def _run_start(self, spec):
        name = spec["name"]
        state = {"name": name, "best": None, "free": list(range(len(self.lower))), "checked": False,
                 "seen": set(), "iterations": 0, "stall": 0, "best_at_iterate": None, "stop": None}
        summary = {"name": name, "origin": spec.get("origin"), "stage": spec["stage"], "status": None,
                   "start_attempt": None, "segments": [], "frozen": [], "stop_reason": None}
        if spec.get("vector") is None:
            summary.update(status="not_constructed", stop_reason=spec.get("status", "no_vector"))
            self._emit({"event": "start", "start": name, "status": summary["status"]})
            return summary
        if self.global_stop:
            summary.update(status="not_started", stop_reason=self.global_stop)
            self._emit({"event": "start", "start": name, "status": summary["status"]})
            return summary
        try:
            row = self.store.request([spec["vector"]], spec["stage"], name)[0]
        except BudgetExhausted as error:
            summary.update(status="not_started", stop_reason=f"budget_{error.scope}")
            if error.scope == "global":
                self.global_stop = "global_budget"
            self._emit({"event": "start", "start": name, "status": summary["status"]})
            return summary
        state["seen"].add(vector_key(row["log_factors"]))
        summary["start_attempt"] = row["attempt"]
        self._consider(row, state, 0, "start")
        if not feasible(row):
            summary.update(status="infeasible_start", stop_reason="start not valid or not reserved-feasible")
            self._emit({"event": "start", "start": name, "status": summary["status"]})
            return self._close(summary, state)
        summary["status"] = "optimized"
        self._emit({"event": "start", "start": name, "status": "feasible_start", "attempt": row["attempt"]})
        state["best_at_iterate"] = row["attempt"]
        box_lo, box_hi = self.lower.copy(), self.upper.copy()
        for segment in range(1, int(self.s["max_segments_per_start"]) + 1):
            if not state["free"]:
                summary["stop_reason"] = "no_free_coordinates"
                break
            record = {"segment": segment, "free": list(state["free"]), "box_radius_log": None
                      if np.array_equal(box_lo, self.lower) and np.array_equal(box_hi, self.upper)
                      else float(np.max(box_hi - box_lo) / 2)}
            try:
                record.update(self._segment(state, segment, box_lo, box_hi))
                summary["stop_reason"] = state["stop"] or f"slsqp_exit_{record['status']}"
                summary["segments"].append(record)
                break
            except FreezeRequest as error:
                state["free"] = [i for i in state["free"] if i not in error.coordinates]
                summary["frozen"].append({"segment": segment, "coordinates": error.coordinates, "reason": error.reason})
                record["ended_by"] = "freeze"
            except ProbeFailure as error:
                centre = np.array(state["best"]["log_factors"], float)
                radius = float(self.s["failure_radius_fraction"]) * float(np.max(np.abs(error.vector - centre)))
                record.update(ended_by="probe_failure", failed_attempt=error.row["attempt"], new_radius_log=radius)
                if radius < float(self.s["minimum_box_radius_log"]):
                    summary["segments"].append(record)
                    summary["stop_reason"] = "probe_failure_radius_exhausted"
                    break
                box_lo = np.maximum(self.lower, centre - radius)
                box_hi = np.minimum(self.upper, centre + radius)
            except BudgetExhausted as error:
                record["ended_by"] = f"budget_{error.scope}"
                summary["segments"].append(record)
                summary["stop_reason"] = f"budget_{error.scope}"
                if error.scope == "global":
                    self.global_stop = "global_budget"
                break
            summary["segments"].append(record)
            self._emit({"event": "segment_restart", "start": name, "segment": segment,
                        "ended_by": record["ended_by"], "free": state["free"]})
        else:
            summary["stop_reason"] = "segment_limit"
        return self._close(summary, state)

    def _close(self, summary, state):
        best = state["best"]
        summary.update(best_attempt=best["attempt"] if best else None,
                       best_objective=best["absolute"]["objective"] if best else None,
                       distinct_evaluations=self.store.used[state["name"]],
                       best_row=best)
        self._emit({"event": "start_end", "start": state["name"], "status": summary["status"],
                    "stop_reason": summary["stop_reason"], "best_attempt": summary["best_attempt"],
                    "distinct_evaluations": summary["distinct_evaluations"]})
        return summary

    def run(self, starts):
        names = [s["name"] for s in starts]
        if names != list(self.s["start_order"]):
            raise ValueError("starts must follow the registered order")
        results = [self._run_start(spec) for spec in starts]
        self._emit({"event": "search_end", "incumbent_attempt": self.incumbent["attempt"] if self.incumbent else None,
                    "global_stop": self.global_stop, "distinct_evaluations": len(self.store.rows)})
        if self.expected is not None and len(self.events) < len(self.expected):
            raise ResumeMismatch("checkpoint has more events than the replay")
        return {"starts": results, "incumbent": self.incumbent, "events": self.events,
                "jacobians": self.jacobians, "distinct_evaluations": len(self.store.rows),
                "per_start": dict(self.store.used), "global_stop": self.global_stop}


def select_finalists(start_results, reference_row, *, gain, maximum):
    """Best feasible row of each start that beats the reference by more than ``gain``."""
    reference = reference_row["absolute"]["objective"]
    unique = {}
    for summary in start_results:
        row = summary.get("best_row")
        if row is None or not feasible(row) or row["absolute"]["objective"] >= reference - gain:
            continue
        unique.setdefault(vector_key(row["log_factors"]), row)
    ranked = sorted(unique.values(), key=lambda r: (r["absolute"]["objective"], r["attempt"]))
    return ranked[:int(maximum)]


def admissible(validated, paired_pass):
    return bool(paired_pass and set(validated) == {"strict", "ultrastrict"}
                and all(feasible(r) for r in validated.values()))
