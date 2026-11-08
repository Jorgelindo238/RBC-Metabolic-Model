"""Independent likelihood/13-constraint, injection and executed-replay checks."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from scipy.stats import lognorm
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from fla_joint_calibration import JointRHS, unpack
from rbc_glut_only_transport import equadiff_glut_only
from run_glut_only_free_replay import sha, close, write
from run_protected_joint import check_seal, verify_inputs

POOLS = ("EGLC", "GLC", "LAC", "ELAC", "ATP", "ADP", "AMP", "PEP", "G6P", "F6P", "B23PG")


def independently_score(prediction, target):
    residual = np.log(target)-np.log(prediction)
    m2 = float(np.mean(residual**2))
    variance = 2*m2/(np.sqrt(1+m2)+1)
    nll = float(-lognorm.logpdf(target, s=np.sqrt(variance), scale=prediction*np.exp(-variance/2)).sum())
    rmse = np.array([np.sqrt(sum(float(v*v) for v in row)/len(row)) for row in (prediction-target)])
    errors = np.r_[rmse, np.abs(prediction[POOLS.index("PEP")]-target[POOLS.index("PEP")])]
    return nll, errors


def verify(out):
    count = 0
    def require(ok, message):
        nonlocal count
        count += 1
        if not ok: raise ValueError(message)
    f = verify_inputs(out)
    d = f["design"]
    obs = json.loads((out/"observations.json").read_text())
    s = json.loads((out/"summary.json").read_text())
    for name, digest in json.loads((out/"manifest.json").read_text())["output_sha256"].items():
        require(sha(out/name) == digest, "changed output:"+name)
    from openpyxl import load_workbook
    book = load_workbook(ROOT/f["parent_design"]["source_workbook"], read_only=True, data_only=False)
    try:
        rows = list(book[f["parent_design"]["source_sheet"]].iter_rows(values_only=True))
        require(list(rows[0][1:15]) == obs["time"], "source days changed")
        for row in rows[1:]:
            if row[0] in obs["values"]:
                for source, value in zip(row[1:15], obs["values"][row[0]]): require(source == value, "source cell changed")
    finally: book.close()
    time = np.array(obs["time"])
    mask = (time > 1) & (time <= d["training_end_day"])
    t = time[mask]
    target = np.array([obs["values"][p] for p in POOLS])[:, mask]
    require(t.tolist() == [4., 8.] and target.size == 22, "wrong training observations")
    base = ROOT/f["parent_design"]["source_archive"]
    numerical = json.loads((base/"execution_design.json").read_text())["design"]
    with np.load(base/"J1_J10/glut_real_candidate_ultrastrict/replay.npz") as a:
        names = a["pool_names"].tolist()
        ref = a["states"][[names.index(p) for p in POOLS]][:, np.searchsorted(a["time"], t)]
        require(np.array_equal(a["initial"], f["initial"]), "baseline initialization mismatch")
    for pool, values in obs["values"].items(): require(f["initial"][names.index(pool)] == values[0], "measured J1 changed")
    _, reference = independently_score(ref, target)
    allowance = d["guard_numerical_atol_mM"]+d["guard_numerical_rtol"]*reference
    fitting_limits = reference+d["fitting_allowance_fraction"]*allowance
    audit_limits = reference+allowance
    require(np.allclose(reference, f["guards"]["reference_errors_mM"], atol=1e-12, rtol=1e-12), "reference errors changed")
    require(np.allclose(fitting_limits, f["guards"]["fit_limits_mM"], atol=1e-12, rtol=1e-12), "fitting limits changed")
    require(np.allclose(audit_limits, f["guards"]["audit_limits_mM"], atol=1e-12, rtol=1e-12), "audit limits changed")
    labels = {}
    control_nll = None
    for fit in s["fits"]:
        folder = out/"fits"/fit["label"]
        check_seal(folder)
        trace = [json.loads(line) for line in (folder/"trace.jsonl").read_text().splitlines()]
        require(len(trace) == fit["actual_objective_integrations"], "call count changed")
        require(len(trace) <= d["optimizer"]["secondary_cumulative_actual_integrations"], "budget exceeded")
        require(trace[0]["log_factors"] == [0.]*6, "missing real control")
        eligible = []
        for i, row in enumerate(trace, 1):
            require(row["call"] == i, "trace ordering")
            if not row["valid"]: continue
            nll, errors = independently_score(np.array(row["predictions"]), target)
            require(abs(nll-row["score"]["negative_log_likelihood"]) < 1e-7, "normalized likelihood")
            require(np.allclose(errors, list(row["guards"]["errors_mM"].values()), atol=1e-12, rtol=1e-12), "constraint errors")
            passed = bool(np.all(errors <= fitting_limits))
            require(passed == row["guards"]["passed"], "13-constraint verdict")
            if passed: eligible.append(row)
            if row["log_factors"] == [0.]*6: control_nll = nll
        best = min(eligible, key=lambda r: r["score"]["negative_log_likelihood"])
        require(best["log_factors"] == fit["selected_log_factors"], "nonminimal/infeasible fit selection")
        parameters, kinetics, factors = unpack(fit["selected_log_factors"], f["parameters"], f["candidate"]["glucose_kinetics"],
            f["resolved_capacities"], f["parent_design"]["factor_bounds"])
        require(parameters == fit["parameters"] and kinetics == fit["glucose_kinetics"] and factors == fit["factors"], "parameter scope")
        with np.load(folder/"fit_replay.npz") as a:
            require(np.array_equal(a["accepted_states"][:, 0], f["initial"]), "fitted initial state changed")
            require(np.array_equal(a["sample_time"], t) and np.array_equal(a["observed"], target), "fitting data changed")
            nll, errors = independently_score(a["prediction"], target)
            require(np.all(errors <= fitting_limits), "selected fitting replay violates guards")
            require(abs(nll-fit["training_score"]["negative_log_likelihood"]) < 1e-7, "selected score")
        labels[fit["label"]] = fit
    best = min(s["fits"], key=lambda r: r["training_score"]["negative_log_likelihood"])
    expected = [0.]*6 if control_nll-best["training_score"]["negative_log_likelihood"] < d["minimum_training_NLL_gain"] else best["selected_log_factors"]
    require(s["selection_attempts"][0]["log_factors"] == expected, "global training-only selection")
    if len(s["selection_attempts"]) > 1:
        require(not s["selection_attempts"][0]["accepted"] and s["selected"]["selected_log_factors"] == [0.]*6, "invalid fallback")
    labels[s["selected"]["label"]] = s["selected"]
    for audit in s["audits"]:
        folder = out/"audits"/(audit["label"]+f"_J{int(audit['end_day'])}")
        check_seal(folder)
        selected = labels[audit["label"]]
        rhs = JointRHS(selected["parameters"], selected["glucose_kinetics"])
        pair, guard_flags, numeric_flags = [], [], []
        for result in audit["results"]:
            with np.load(folder/f"J1_J{int(audit['end_day'])}"/f"glut_real_candidate_{result['profile']}/replay.npz") as a:
                require(np.array_equal(a["initial"], f["initial"]) and np.array_equal(a["accepted_states"][:, 0], f["initial"]), "audit J1 changed")
                require(a["accepted_time"][-1] == audit["end_day"] and np.all(a["states"][-1] == f["initial"][-1]), "truncated horizon or changed pH")
                minimum = min(a["states"][:113].min(), a["accepted_states"][:113].min())
                integrals = {}
                for order in (4, 8):
                    minimum = min(minimum, a[f"q{order}_states"][:113].min())
                    for kind in ("raw", "executed"):
                        rates, weights, cells = (a[f"q{order}_{kind}_rates"], a[f"q{order}_weights"], a[f"q{order}_intervals"])
                        require(np.all(np.isfinite(rates)), "nonfinite rates")
                        restored = np.vstack([np.bincount(cells, weights=weights*rate, minlength=len(a["boundaries"])-1) for rate in rates])
                        require(bool(close(restored, a[f"{kind}{order}"], numerical, "quadrature").all()), "quadrature reconstruction")
                        integrals[order, kind] = restored
                index = np.searchsorted(a["time"], a["boundaries"])
                comparisons = [close(np.diff(a["states"][:113, index]), a["matrix"]@integrals[8, "executed"], numerical, "quadrature"),
                    close(integrals[4, "raw"], integrals[8, "raw"], numerical, "quadrature"),
                    close(integrals[4, "executed"], integrals[8, "executed"], numerical, "quadrature")]
                passed = bool(all(c.all() for c in comparisons) and minimum >= -1e-10
                              and result["raw_closure_max"] <= 1e-7 and result["executed_closure_max"] <= 1e-7)
                require(minimum == result["minimum_checked_mM"] and passed == result["numerical_pass"], "numerical integrity flag")
                numeric_flags.append(passed)
                if audit["end_day"] >= d["training_end_day"]:
                    prediction = a["states"][[rhs.names.index(p) for p in POOLS]][:, np.searchsorted(a["time"], t)]
                    _, errors = independently_score(prediction, target)
                    guard_flags.append(bool(np.all(errors <= audit_limits)))
                    recorded = next(r for r in audit["training_guards"] if r["profile"] == result["profile"])
                    require(guard_flags[-1] == recorded["passed"], "original-path 13-guard verdict")
                for pool in POOLS: require(float(a["states"][rhs.names.index(pool), -1]) == result["endpoint"][pool], "endpoint")
                for j in np.unique(np.linspace(0, len(a["q8_nodes"])-1, 7).astype(int)):
                    time0, state = a["q8_nodes"][j], a["q8_states"][:, j]
                    raw, executed, _ = rhs.rates(time0, state)
                    require(np.array_equal(raw, a["q8_raw_rates"][:, j]) and np.array_equal(executed, a["q8_executed_rates"][:, j]), "sampled stored/live rates")
                    original = equadiff_glut_only(time0, state, glucose_kinetics=selected["glucose_kinetics"], hematocrit=.58,
                        custom_params=selected["parameters"], positivity_policy="reaction_consistent", curve_fit_strength=0.,
                        reaction_availability_threshold=.001, ph_policy="clamped_diagnostic")
                    require(np.array_equal(original, rhs(time0, state)), "sampled original/fast RHS")
                if result["profile"] == "ultrastrict":
                    with np.load(folder/"fast_parity.npz") as fast:
                        require(np.array_equal(fast["time"], a["time"]), "parity time grid")
                        require(np.allclose(fast["states"][:113], a["states"][:113], rtol=.01, atol=1e-5), "whole-trajectory fast/full parity")
                pair.append((a["states"][:113].copy(), a["raw8"].copy(), a["executed8"].copy()))
        convergence = all(close(pair[0][j], pair[1][j], numerical, "comparison").all() for j in range(3))
        require(all(guard_flags) == audit["guard_pass"], "audit guard summary")
        require(bool(all(numeric_flags) and convergence and audit["fast_full_parity"]) == audit["numerical_pass"], "audit numerical summary")
    final = s["selection_attempts"][-1]
    require(final["log_factors"] == s["selected"]["selected_log_factors"], "selected/audited identity")
    final_audits = [a for a in s["audits"] if a["label"] == final["label"]]
    accepted = all(a["numerical_pass"] and a["guard_pass"] for a in final_audits) and final_audits[-1]["end_day"] == 46
    require(bool(accepted) == s["accepted_numeric_and_training_guards"], "final acceptance")
    require(s["total_objective_integrations"] == sum(r["actual_objective_integrations"] for r in s["fits"]), "total call count")
    for field in ("production_promoted", "initial_states_changed", "source_values_changed", "kinetic_box_expanded", "late_observations_used_in_selection"):
        require(s[field] is False, "scope:"+field)
    return {"verified": True, "checks": count, "fits": len(s["fits"]), "constraints": 13,
        "original_path_replays": 2*len(s["audits"]), "training_guard_acceptance": s["accepted_numeric_and_training_guards"],
        "selected_is_control": s["selected_is_control"], "physiological_validation": False,
        "live_RHS_coverage": "seven_saved_quadrature_states_per_replay_not_all_optimizer_integrations_reexecuted"}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--receipt", type=Path)
    args = p.parse_args()
    with threadpool_limits(limits=1): result = verify(args.archive.resolve())
    if args.receipt:
        if args.receipt.exists(): raise ValueError("fresh receipt required")
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        write(args.receipt, result)
    print(json.dumps(result, indent=2))
