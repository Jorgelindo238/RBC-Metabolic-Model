"""Source, nested-scope, thirteen-guard and original executed-flux verification."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from fla_joint_calibration import JointRHS
from rbc_glut_only_transport import equadiff_glut_only
from verify_broad_protected_joint import independently_score, POOLS
from run_protected_joint import verify_inputs, check_seal
from run_glut_only_free_replay import sha, close, write


def verify(out):
    count = 0
    def require(ok, message):
        nonlocal count
        count += 1
        if not ok: raise ValueError(message)
    f = verify_inputs(out)
    parent = ROOT/f["design"]["parent_archive"]
    prior = json.loads((parent/"execution_design.json").read_text())
    prior_summary = json.loads((parent/"summary.json").read_text())
    obs = json.loads((out/"observations.json").read_text())
    s = json.loads((out/"summary.json").read_text())
    require(f["guards"] == prior["guards"] and f["initial"] == prior["initial"], "changed guard limits or initial state")
    require(f["parameters"] == prior_summary["selected"]["parameters"] and f["kinetics"] == prior_summary["selected"]["glucose_kinetics"], "changed frozen context")
    require(f["primitive_factor_bounds"] == prior["parent_design"]["factor_bounds"]["investment"]
            and f["primitive_capacities"] == {p: prior["resolved_capacities"][p] for p in ("vmax_VHK", "vmax_VPFK")}, "changed original capacity envelope")
    require(obs == json.loads((parent/"observations.json").read_text()), "source values changed")
    for name, h in json.loads((out/"manifest.json").read_text())["output_sha256"].items(): require(sha(out/name) == h, "output hash:"+name)
    times = np.array(obs["time"])
    mask = (times > 1) & (times <= f["design"]["training_end_day"])
    t = times[mask]
    target = np.array([obs["values"][p] for p in POOLS])[:, mask]
    require(t.tolist() == [4., 8.] and target.size == 22, "nonoriginal fitting observations")
    fit_limits = np.array(f["guards"]["fit_limits_mM"])
    audit_limits = np.array(f["guards"]["audit_limits_mM"])
    labels = {}
    def parameters_for(x, mode):
        x = np.array(x)
        require(len(x) == (1 if mode == "paired" else 2), "free dimension changed")
        bounds = np.log(f["primitive_factor_bounds"])
        require(bool(np.all(x >= bounds[0]-1e-12) and np.all(x <= bounds[1]+1e-12)), "primitive bounds expanded")
        expanded = np.repeat(x, 2) if mode == "paired" else x
        result = dict(f["parameters"])
        for name, value in zip(("vmax_VHK", "vmax_VPFK"), expanded): result[name] = f["primitive_capacities"][name]*float(np.exp(value))
        return result
    screen = json.loads((out/"screen/results.json").read_text())
    require(len(screen) == len(f["design"]["screen_offsets"]), "missing fixed screen case")
    check_seal(out/"screen")
    for row in screen:
        if not row["valid"]: continue
        nll, errors = independently_score(np.array(row["predictions"]), target)
        require(abs(nll-row["score"]["negative_log_likelihood"]) < 1e-7, "screen likelihood")
        require(bool(np.all(errors <= fit_limits)) == row["guards"]["passed"], "screen guards")
        with np.load(out/"screen"/(row["label"]+".npz")) as a:
            require(np.array_equal(a["accepted_states"][:, 0], f["initial"]) and np.array_equal(a["sample_time"], t), "screen initial/time changed")
    for fit in s["fits"]:
        folder = out/"fits"/fit["label"]
        check_seal(folder)
        rows = [json.loads(line) for line in (folder/"trace.jsonl").read_text().splitlines()]
        require(len(rows) == fit["actual_objective_integrations"] <= f["design"]["optimizer"]["secondary_cumulative_actual_integrations"], "actual objective count")
        expected_seed = [f["seed_log_investment"]]*(1 if fit["mode"] == "paired" else 2)
        require(rows[0]["log_factors"] == expected_seed and rows[0]["guards"]["passed"], "missing parent fallback")
        eligible = []
        for i, row in enumerate(rows, 1):
            require(row["call"] == i, "trace ordering")
            if not row["valid"]: continue
            parameters_for(row["log_factors"], fit["mode"])
            nll, errors = independently_score(np.array(row["predictions"]), target)
            require(abs(nll-row["score"]["negative_log_likelihood"]) < 1e-7, "fit likelihood")
            passed = bool(np.all(errors <= fit_limits))
            require(passed == row["guards"]["passed"], "13 fitting guards")
            if passed: eligible.append(row)
        best = min(eligible, key=lambda r:r["score"]["negative_log_likelihood"])
        require(best["log_factors"] == fit["selected_log_factors"], "nonminimal feasible fit choice")
        require(parameters_for(best["log_factors"], fit["mode"]) == fit["parameters"], "non-HK/PFK parameter changed")
        require(fit["glucose_kinetics"] == f["kinetics"], "transport constants changed")
        with np.load(folder/"fit_replay.npz") as a:
            require(np.array_equal(a["accepted_states"][:, 0], f["initial"]), "fitting J1 changed")
            require(np.array_equal(a["observed"], target) and np.array_equal(a["sample_time"], t), "fitting data/time changed")
            nll, errors = independently_score(a["prediction"], target)
            require(np.all(errors <= fit_limits) and abs(nll-fit["training_score"]["negative_log_likelihood"]) < 1e-7, "fitting replay")
        labels[fit["label"]] = fit
    paired = min((r for r in s["fits"] if r["mode"] == "paired"), key=lambda r:r["training_score"]["negative_log_likelihood"])
    split = min((r for r in s["fits"] if r["mode"] == "split"), key=lambda r:r["training_score"]["negative_log_likelihood"])
    require(paired == s["best_paired"] and split == s["best_split"], "nested model ranking")
    parent_nll = screen[0]["score"]["negative_log_likelihood"]
    paired_fit_nll = paired["training_score"]["negative_log_likelihood"]
    paired_nll = paired_fit_nll if parent_nll-paired_fit_nll >= f["design"]["minimum_NLL_gain"] else parent_nll
    gain = paired_nll-split["training_score"]["negative_log_likelihood"]
    require(abs(gain-s["split_training_NLL_gain_vs_best_paired_found"]) < 1e-7, "split benefit calculation")
    # All new original-path evidence, including a changed paired short comparator.
    numerical = json.loads((ROOT/f["parent_design"]["source_archive"]/"execution_design.json").read_text())["design"]
    for audit in s["audits"]:
        selected = labels[audit["label"]]
        rhs = JointRHS(selected["parameters"], selected["glucose_kinetics"])
        folder = out/"audits"/(audit["label"]+f"_J{int(audit['end_day'])}")
        check_seal(folder)
        pair, guard_flags, numeric_flags = [], [], []
        for result in audit["results"]:
            with np.load(folder/f"J1_J{int(audit['end_day'])}"/f"glut_real_candidate_{result['profile']}/replay.npz") as a:
                require(np.array_equal(a["initial"], f["initial"]) and np.array_equal(a["accepted_states"][:, 0], f["initial"]), "audit initial changed")
                require(a["accepted_time"][-1] == audit["end_day"] and np.all(a["states"][-1] == f["initial"][-1]), "audit truncation/pH")
                minimum = min(a["states"][:113].min(), a["accepted_states"][:113].min())
                restored = {}
                for order in (4, 8):
                    minimum = min(minimum, a[f"q{order}_states"][:113].min())
                    for kind in ("raw", "executed"):
                        rates, weights, cells = a[f"q{order}_{kind}_rates"], a[f"q{order}_weights"], a[f"q{order}_intervals"]
                        require(np.all(np.isfinite(rates)), "nonfinite rates")
                        amount = np.vstack([np.bincount(cells, weights=weights*v, minlength=len(a["boundaries"])-1) for v in rates])
                        require(close(amount, a[f"{kind}{order}"], numerical, "quadrature").all(), "quadrature weights")
                        restored[order, kind] = amount
                ix = np.searchsorted(a["time"], a["boundaries"])
                tests = [close(np.diff(a["states"][:113, ix]), a["matrix"]@restored[8, "executed"], numerical, "quadrature"),
                    close(restored[4, "raw"], restored[8, "raw"], numerical, "quadrature"),
                    close(restored[4, "executed"], restored[8, "executed"], numerical, "quadrature")]
                numeric = bool(all(v.all() for v in tests) and minimum >= -1e-10
                               and result["raw_closure_max"] <= 1e-7 and result["executed_closure_max"] <= 1e-7)
                require(minimum == result["minimum_checked_mM"] and numeric == result["numerical_pass"], "audit numerical flag")
                numeric_flags.append(numeric)
                if audit["end_day"] >= 10:
                    prediction = a["states"][[rhs.names.index(p) for p in POOLS]][:, np.searchsorted(a["time"], t)]
                    _, errors = independently_score(prediction, target)
                    guard_flags.append(bool(np.all(errors <= audit_limits)))
                    recorded = next(g for g in audit["training_guards"] if g["profile"] == result["profile"])
                    require(guard_flags[-1] == recorded["passed"], "original13 guards")
                for j in np.unique(np.linspace(0, len(a["q8_nodes"])-1, 7).astype(int)):
                    time0, state = a["q8_nodes"][j], a["q8_states"][:, j]
                    raw, executed, _ = rhs.rates(time0, state)
                    require(np.array_equal(raw, a["q8_raw_rates"][:, j]) and np.array_equal(executed, a["q8_executed_rates"][:, j]), "saved/live raw executed rates")
                    original = equadiff_glut_only(time0, state, glucose_kinetics=selected["glucose_kinetics"], hematocrit=.58,
                        custom_params=selected["parameters"], positivity_policy="reaction_consistent", curve_fit_strength=0.,
                        reaction_availability_threshold=.001, ph_policy="clamped_diagnostic")
                    require(np.array_equal(original, rhs(time0, state)), "original/fast RHS")
                if result["profile"] == "ultrastrict":
                    with np.load(folder/"fast_parity.npz") as fast:
                        require(np.allclose(fast["states"][:113], a["states"][:113], rtol=.01, atol=1e-5), "full trajectory parity")
                pair.append((a["states"][:113].copy(), a["raw8"].copy(), a["executed8"].copy()))
        convergence = all(close(pair[0][j], pair[1][j], numerical, "comparison").all() for j in range(3))
        require(bool(all(numeric_flags) and convergence and audit["fast_full_parity"]) == audit["numerical_pass"], "numerical summary")
        require(all(guard_flags) == audit["guard_pass"], "guard summary")
    if s["selected_is_parent"]:
        require(s["selected"]["parameters"] == f["parameters"] and prior_summary["accepted_numeric_and_training_guards"], "invalid parent reuse")
    else:
        require(parameters_for(s["selected"]["selected_log_factors"], s["selected"]["mode"]) == s["selected"]["parameters"], "selection scope")
    if s["selected_is_split"]: require(gain >= f["design"]["minimum_NLL_gain"], "split selected without resolved gain")
    require(s["selection_attempts"][-1]["label"] == s["selected"]["label"]
            and s["selection_attempts"][-1]["accepted"] == s["accepted_numeric_and_training_guards"], "final acceptance bookkeeping")
    if not s["selected_is_parent"]:
        selected_audits = [a for a in s["audits"] if a["label"] == s["selected"]["label"]]
        require(sorted(a["end_day"] for a in selected_audits) == [4., 10., 46.]
                and all(a["numerical_pass"] and a["guard_pass"] for a in selected_audits), "missing complete accepted audit")
    require(s["fit_objective_integrations"] == sum(r["actual_objective_integrations"] for r in s["fits"]), "total fit count")
    for name in ("all_other_parameters_changed", "primitive_bounds_expanded", "guard_caps_changed", "source_values_changed",
                 "initial_states_changed", "late_data_used_in_selection", "production_promoted", "paired_global_optimality_proved"):
        require(s[name] is False, "scope:"+name)
    return {"verified": True, "checks": count, "fits": len(s["fits"]), "new_original_path_replays": 2*len(s["audits"]),
        "reused_parent_full_audits": s["selected_is_parent"], "selected_is_split": s["selected_is_split"],
        "constraints_unchanged": 13, "physiological_validation": False,
        "live_RHS_coverage": "seven_saved_states_per_new_replay_not_all_optimizer_trajectories_reexecuted"}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True); p.add_argument("--receipt", type=Path)
    args = p.parse_args()
    with threadpool_limits(limits=1): result = verify(args.archive.resolve())
    if args.receipt:
        if args.receipt.exists(): raise ValueError("fresh verification receipt required")
        args.receipt.parent.mkdir(parents=True, exist_ok=True); write(args.receipt, result)
    print(json.dumps(result, indent=2))
