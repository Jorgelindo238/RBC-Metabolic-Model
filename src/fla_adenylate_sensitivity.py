"""Local parameter effects and conservative subset proposals, not calibration."""

import ast
import copy
from pathlib import Path
import numpy as np

from fla_broad_protected_calibration import POOLS

ADENYLATES = ("ATP", "ADP", "AMP")
PROTECTED = tuple(p for p in POOLS if p not in ADENYLATES)


def resolve_parameters(parameters, source, requested):
    tree = ast.parse(Path(source).read_text(encoding="utf-8-sig"))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "equadiff_brodbar")
    calls = {}
    for node in ast.walk(function):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_get_param"
                and len(node.args) == 3 and isinstance(node.args[1], ast.Constant)):
            key = node.args[1].value
            if key in requested:
                if key in calls: raise ValueError("ambiguous native parameter:"+key)
                calls[key] = node
    result = {}
    for key in requested:
        if key not in calls: raise ValueError("unknown native parameter:"+key)
        value = parameters[key] if key in parameters else ast.literal_eval(calls[key].args[2])
        if isinstance(value, bool) or not np.isfinite(value) or value <= 0: raise ValueError("positive resolved parameter required:"+key)
        result[key] = {"value": float(value), "source": "frozen_override" if key in parameters else "native_literal_default",
                       "native_line": calls[key].lineno}
    return result


def perturb(parameters, name, value, offset):
    if not np.isfinite(value) or value <= 0 or not np.isfinite(offset): raise ValueError("finite positive perturbation required")
    p = copy.deepcopy(parameters)
    p[name] = float(value*np.exp(offset))
    return p


def diagnostics(prediction, target, scales):
    p, y = np.asarray(prediction, float), np.asarray(target, float)
    if p.shape != y.shape or p.shape[0] != len(POOLS) or not np.all(np.isfinite(p)) or np.any(p < 0) or np.any(y <= 0):
        raise ValueError("finite nonnegative predictions and positive aligned observations required")
    a = np.asarray(scales["absolute"])
    standardized = (p-y)/(a[:, None]+scales["relative"]*y)
    ix = [POOLS.index(p) for p in ADENYLATES]
    if np.any(p[ix] <= 0): raise ValueError("log adenylate response undefined at zero; no epsilon added")
    log_error = np.log(p[ix]/y[ix])
    total = p[ix].sum(axis=0)
    nominal_total = y[ix].sum(axis=0)
    ec = (p[ix[0]]+.5*p[ix[1]])/total
    nominal_ec = (y[ix[0]]+.5*y[ix[1]])/nominal_total
    return {"working_MSE": dict(zip(POOLS, np.mean(standardized**2, axis=1).tolist())),
        "adenylate_log_MSE": dict(zip(ADENYLATES, np.mean(log_error**2, axis=1).tolist())),
        "adenylate_log_mean": float(np.mean(log_error**2)), "adenylate_log_residuals": log_error.ravel().tolist(),
        "working_residuals": standardized.ravel().tolist(), "energy_charge": ec.tolist(),
        "nominal_energy_charge": nominal_ec.tolist(), "adenylate_total_mM": total.tolist(),
        "nominal_adenylate_total_mM": nominal_total.tolist(), "derived_metrics_are_independent_observations": False}


def sensitivity_column(plus, minus, plus_half, minus_half, target, scales, step):
    arrays = [np.asarray(a, float) for a in (plus, minus, plus_half, minus_half)]
    if step <= 0 or not np.isfinite(step): raise ValueError("positive logarithmic step required")
    ix = [POOLS.index(p) for p in ADENYLATES]
    if any(np.any(a[ix] <= 0) for a in arrays): raise ValueError("positive adenylates required for log sensitivity")
    full = ((np.log(arrays[0][ix])-np.log(arrays[1][ix]))/(2*step)).ravel()
    half = ((np.log(arrays[2][ix])-np.log(arrays[3][ix]))/step).ravel()
    denominator = np.asarray(scales["absolute"])[:, None]+scales["relative"]*np.asarray(target)
    standardized = ((arrays[2]-arrays[3])/(step*denominator)).ravel()
    norm = float(np.linalg.norm(half))
    difference = float(np.linalg.norm(full-half))
    return {"log_adenylate_derivative": half.tolist(), "working_derivative": standardized.tolist(),
        "full_log_derivative": full.tolist(), "response_norm": norm,
        "relative_two_step_disagreement": difference/norm if norm else (0. if difference == 0 else None)}


def admissibility(diagnostics0, baseline, design):
    target = all(diagnostics0["adenylate_log_MSE"][p] <= baseline["adenylate_log_MSE"][p]*(1+design["individual_adenylate_regression_fraction"])+1e-8 for p in ADENYLATES)
    protected = all(diagnostics0["working_MSE"][p] <= baseline["working_MSE"][p]+design["protected_allowance_fraction"]*(1+baseline["working_MSE"][p]) for p in PROTECTED)
    gain = baseline["adenylate_log_mean"]-diagnostics0["adenylate_log_mean"]
    return {"individual_adenylate_pass": target, "protected_working_pass": protected,
        "actual_adenylate_log_gain": gain,
        "gain_pass": gain >= design["minimum_fractional_adenylate_log_gain"]*baseline["adenylate_log_mean"]}


def select_subset(columns, baseline_diagnostics, baseline_log_noise, design):
    r = np.asarray(baseline_diagnostics["adenylate_log_residuals"])
    eligible, ranking = [], []
    for name, c in columns.items():
        v = np.asarray(c["log_adenylate_derivative"])
        gradient = float(2*r@v/len(r))
        direction = -1 if gradient > 0 else 1
        probe = c["directional_probes"]["minus" if direction < 0 else "plus"]
        d = probe["diagnostics"]
        admission = admissibility(d, baseline_diagnostics, design)
        step_error = c["relative_two_step_disagreement"]
        stable = step_error is not None and step_error <= design["maximum_two_step_disagreement"]
        signal = c["response_norm"]*design["log_step"] >= max(design["minimum_log_response_norm"], design["numerical_signal_multiplier"]*baseline_log_noise)
        row = {"parameter": name, "direction": direction, "projected_log_error_gradient": gradient,
            **admission, "stable_two_step": stable, "above_numerical_signal": signal,
            "eligible_for_subset": bool(stable and signal and admission["individual_adenylate_pass"] and admission["protected_working_pass"] and admission["gain_pass"]),
            "probe_label": probe["label"], "normalized_error_gain_is_not_biological_recovery": True}
        ranking.append(row)
        if row["eligible_for_subset"]: eligible.append(row)
    ranking.sort(key=lambda row:row["actual_adenylate_log_gain"], reverse=True)
    eligible.sort(key=lambda row:row["actual_adenylate_log_gain"], reverse=True)
    selected = []
    for candidate in eligible:
        v = np.asarray(columns[candidate["parameter"]]["log_adenylate_derivative"])
        correlations = []
        for old in selected:
            w = np.asarray(columns[old["parameter"]]["log_adenylate_derivative"])
            correlations.append(abs(float(v@w)/(np.linalg.norm(v)*np.linalg.norm(w))))
        if not correlations or max(correlations) < design["maximum_subset_cosine"]:
            selected.append(candidate)
        if len(selected) >= design["maximum_subset_size"]: break
    return ranking, selected
