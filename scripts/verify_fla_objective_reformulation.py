"""Independent source/residual/guard, necessary-balance and executed-ODE checks."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from openpyxl import load_workbook
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from fla_joint_calibration import JointRHS
from fla_broad_protected_calibration import POOLS
from rbc_glut_only_transport import equadiff_glut_only
from run_protected_joint import verify_inputs, check_seal
from run_glut_only_free_replay import sha, write, close
from verify_broad_protected_joint import independently_score


def verify(out):
    count = 0
    def require(ok, reason):
        nonlocal count
        count += 1
        if not ok: raise ValueError(reason)
    f = verify_inputs(out)
    s = json.loads((out/"summary.json").read_text())
    obs = json.loads((out/"observations.json").read_text())
    for name, h in json.loads((out/"manifest.json").read_text())["output_sha256"].items(): require(sha(out/name) == h, "output hash:"+name)
    parent = json.loads((ROOT/f["design"]["parent_archive"]/"execution_design.json").read_text())
    require(f["initial"] == parent["initial"] and f["parameters"] == parent["parameters"]
            and f["kinetics"] == parent["kinetics"] and f["guards"] == parent["guards"], "changed context or diagnostic caps")
    book = load_workbook(ROOT/f["parent_design"]["source_workbook"], read_only=True, data_only=False)
    try:
        rows = list(book[f["parent_design"]["source_sheet"]].iter_rows(values_only=True))
        require(list(rows[0][1:15]) == obs["time"], "source time changed")
        for row in rows[1:]:
            if row[0] in obs["values"]:
                for source, value in zip(row[1:15], obs["values"][row[0]]): require(source == value, "original source cell changed")
    finally: book.close()
    reference = JointRHS(f["parameters"], f["kinetics"])
    for p, values in obs["values"].items(): require(f["initial"][reference.names.index(p)] == values[0], "measured J1 changed")
    for end, phase in f["phases"].items():
        use = (np.array(obs["time"]) > 1) & (np.array(obs["time"]) <= float(end))
        y = np.array([obs["values"][p] for p in POOLS])[:, use]
        require(phase["times"] == np.array(obs["time"])[use].tolist(), "nonoriginal fit days")
        require(np.array_equal(np.median(y, axis=1)*f["design"]["absolute_scale_fraction"], phase["scales"]["absolute"]), "normalization scale uses nontraining data")
    def check_prediction(prediction, y, end, loss):
        scales = f["phases"][str(int(end))]["scales"]
        r = (prediction-y)/(np.array(scales["absolute"])[:, None]+scales["relative"]*np.abs(y))
        per = np.array([sum(float(v)**2 for v in row)/len(row) for row in r])
        early = prediction[:, :2]-y[:, :2]
        guard_errors = np.r_[np.sqrt(np.mean(early**2, axis=1)), np.abs(early[POOLS.index("PEP")])]
        nll = independently_score(prediction[:, :2], y[:, :2])[0] if np.all(prediction[:, :2] > 0) else None
        value = {"lognormal": nll, "normalized": float(per.mean()), "minimax": float(per.max())}[loss]
        return value, per, bool(np.all(guard_errors <= f["guards"]["fit_limits_mM"]))
    fit_labels = {}
    for fit in s["fits"]:
        folder = out/"fits"/fit["label"]; check_seal(folder)
        rows = [json.loads(line) for line in (folder/"trace.jsonl").read_text().splitlines()]
        require(len(rows) == fit["actual_objective_integrations"] <= f["design"]["optimizer"]["actual_call_cap"], "objective count")
        phase = f["phases"][str(int(fit["end_day"]))]
        y = np.array([obs["values"][p] for p in POOLS])[:, (np.array(obs["time"]) > 1)&(np.array(obs["time"]) <= fit["end_day"])]
        valid = []
        for i, row in enumerate(rows, 1):
            require(row["call"] == i, "trace ordering")
            if not row["valid"]: continue
            value, per, passed = check_prediction(np.array(row["predictions"]), y, fit["end_day"], fit["loss"])
            require(abs(value-row["objective_value"]) < 1e-7, "independent objective")
            require(np.allclose(per, row["metrics"]["channel_MSE"], rtol=1e-12, atol=1e-12), "per-metabolite errors")
            require(row["legacy13"]["passed"] == passed, "diagnostic guards")
            valid.append(row)
        best = min(valid, key=lambda r:r["objective_value"])
        require(best["log_factors"] == fit["selected_log_factors"], "selection used hidden guards or terminal status")
        p = dict(f["parameters"])
        for name, log in zip(("vmax_VHK", "vmax_VPFK"), best["log_factors"]):
            require(np.log(.02)-1e-12 <= log <= 1e-12, "capacity envelope changed")
            p[name] = f["primitive_capacities"][name]*float(np.exp(log))
        require(p == fit["parameters"] and fit["glucose_kinetics"] == f["kinetics"], "non-HK/PFK injection")
        require(fit["legacy13_used_to_filter_selection"] is False, "old guards secretly filter fits")
        with np.load(folder/"fit_replay.npz") as a:
            require(np.array_equal(a["accepted_states"][:, 0], f["initial"]), "fitting J1 changed")
            require(np.array_equal(a["observed"], y) and a["sample_time"].tolist() == phase["times"], "fitting data changed")
            value, _, _ = check_prediction(a["prediction"], y, fit["end_day"], fit["loss"])
            require(abs(value-fit["objective_value"]) < 1e-7, "fitting replay score")
        fit_labels[fit["label"]] = fit
    check_seal(out/"balances")
    balance = json.loads((out/"balances/results.json").read_text())
    for r in balance:
        with np.load(out/"balances"/f"{r['scope']}_J{int(r['end_day'])}.npz") as a:
            require(np.array_equal(a["matrix"], reference.matrix[[reference.names.index(p) for p in r["pools"]]]), "balance matrix changed")
            target = np.array([obs["values"][p] for p in r["pools"]])[:, np.array(obs["time"]) <= r["end_day"]]
            require(np.array_equal(a["observed"], target), "balance source changed")
            z, e, multiplier = a["extents"], a["adjustments"], r["minimum_working_error_multiplier"]
            require(np.max(np.abs(a["matrix"]@z-np.diff(target+e, axis=1))) < 1e-6, "integral LP primal balance")
            require(np.all(e[:, 0] == 0) and (target+e).min() >= -1e-7, "LP reset or negative observations")
            require(np.all(np.abs(e) <= multiplier*a["scales"]+1e-7), "LP adjustment envelope")
            for reaction in f["design"]["forward_direction_subset"]:
                require(z[reference.reactions.index(reaction)].min() >= -1e-7, "LP forward direction")
    numeric_design = json.loads((ROOT/f["parent_design"]["source_archive"]/"execution_design.json").read_text())["design"]
    all_numeric = []
    for audit in s["audits"]:
        selected = fit_labels[audit["label"]]
        rhs = JointRHS(selected["parameters"], selected["glucose_kinetics"])
        folder = out/"audits"/(audit["label"]+f"_J{int(audit['end_day'])}"); check_seal(folder)
        pairs, flags = [], []
        for result in audit["results"]:
            with np.load(folder/f"J1_J{int(audit['end_day'])}/glut_real_candidate_{result['profile']}/replay.npz") as a:
                require(np.array_equal(a["accepted_states"][:, 0], f["initial"]) and np.array_equal(a["initial"], f["initial"]), "original replay J1 changed")
                require(a["accepted_time"][-1] == audit["end_day"], "replay truncated")
                minimum = min(a["states"][:113].min(), a["accepted_states"][:113].min())
                restored = {}
                for order in (4, 8):
                    minimum = min(minimum, a[f"q{order}_states"][:113].min())
                    for kind in ("raw", "executed"):
                        rates, weights, cells = a[f"q{order}_{kind}_rates"], a[f"q{order}_weights"], a[f"q{order}_intervals"]
                        require(np.isfinite(rates).all(), "nonfinite rates")
                        restored[order, kind] = np.vstack([np.bincount(cells, weights=weights*v, minlength=len(a["boundaries"])-1) for v in rates])
                        require(close(restored[order, kind], a[f"{kind}{order}"], numeric_design, "quadrature").all(), "independent quadrature")
                ix = np.searchsorted(a["time"], a["boundaries"])
                checks = [close(np.diff(a["states"][:113, ix]), a["matrix"]@restored[8, "executed"], numeric_design, "quadrature"),
                    close(restored[4, "raw"], restored[8, "raw"], numeric_design, "quadrature"),
                    close(restored[4, "executed"], restored[8, "executed"], numeric_design, "quadrature")]
                flag = bool(all(v.all() for v in checks) and minimum >= -1e-10 and result["raw_closure_max"] <= 1e-7 and result["executed_closure_max"] <= 1e-7)
                require(flag == result["numerical_pass"] and minimum == result["minimum_checked_mM"], "replay numerical flag")
                flags.append(flag)
                for j in np.unique(np.linspace(0, len(a["q8_nodes"])-1, 7).astype(int)):
                    time, state = a["q8_nodes"][j], a["q8_states"][:, j]
                    raw, executed, _ = rhs.rates(time, state)
                    require(np.array_equal(raw, a["q8_raw_rates"][:, j]) and np.array_equal(executed, a["q8_executed_rates"][:, j]), "saved/live rates")
                    native = equadiff_glut_only(time, state, glucose_kinetics=selected["glucose_kinetics"], hematocrit=.58,
                        custom_params=selected["parameters"], positivity_policy="reaction_consistent", curve_fit_strength=0.,
                        reaction_availability_threshold=.001, ph_policy="clamped_diagnostic")
                    require(np.array_equal(native, rhs(time, state)), "original/fast RHS")
                with np.load(folder/"fast_parity.npz") as fast:
                    if result["profile"] == "ultrastrict": require(np.allclose(fast["states"][:113], a["states"][:113], rtol=.01, atol=1e-5), "full parity")
                pairs.append((a["states"][:113].copy(), a["raw8"].copy(), a["executed8"].copy()))
        convergence = all(close(pairs[0][j], pairs[1][j], numeric_design, "comparison").all() for j in range(3))
        numeric = bool(all(flags) and convergence and audit["fast_full_parity"])
        require(numeric == audit["numerical_pass"], "audit summary")
        all_numeric.append(numeric)
    require(all(all_numeric) == s["all_original_numerical_checks_passed"], "overall numerical scope")
    ready = next(r for r in balance if r["end_day"] == 15 and r["scope"] == "eleven_training")["minimum_working_error_multiplier"] <= 1
    require(ready == s["J15_balance_gate_passed"], "J15 gate changed")
    require(s["actual_objective_integrations"] == sum(r["actual_objective_integrations"] for r in s["fits"]), "total calls")
    require(s["legacy13_are_diagnostics_only"] and not s["production_promoted"] and not s["relative_experimental_data_fitted"], "scope")
    return {"verified": True, "checks": count, "fits": len(s["fits"]), "new_original_path_replays": 2*len(s["audits"]),
        "all_original_numeric": all(all_numeric), "relative_contract_tests_not_real_relative_fitting": True,
        "LP_optimality_independently_proved": False, "biological_validation": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True); p.add_argument("--receipt", type=Path, required=True)
    a = p.parse_args()
    if a.receipt.exists(): raise ValueError("fresh verification receipt required")
    with threadpool_limits(1): result = verify(a.archive.resolve())
    a.receipt.parent.mkdir(parents=True, exist_ok=True); write(a.receipt, result)
    print(json.dumps(result, indent=2))
