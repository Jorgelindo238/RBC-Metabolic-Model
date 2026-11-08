"""Independent coverage, finite-difference, selection and executed-ODE verification."""

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
from rbc_coverage_extensions import BRANCHES
from rbc_gem_audit import pool_mapping, project_gem
from rbc_glut_only_transport import equadiff_glut_only
from run_protected_joint import verify_inputs, check_seal
from run_glut_only_free_replay import write, sha, close


def verify(out):
    count = 0
    def require(ok, reason):
        nonlocal count
        count += 1
        if not ok: raise ValueError(reason)
    f = verify_inputs(out); d = f["design"]
    s = json.loads((out/"summary.json").read_text()); obs = json.loads((out/"observations.json").read_text())
    for name, h in json.loads((out/"manifest.json").read_text())["output_sha256"].items(): require(sha(out/name) == h, "output hash:"+name)
    parent = ROOT/d["parent_archive"]
    old_f = json.loads((parent/"execution_design.json").read_text())
    chosen = json.loads((parent/"fits"/d["baseline_label"]/"result.json").read_text())
    require(f["parameters"] == chosen["parameters"] and f["kinetics"] == chosen["glucose_kinetics"] and f["initial"] == old_f["initial"], "baseline context changed")
    rhs0 = JointRHS(f["parameters"], f["kinetics"])
    book = load_workbook(ROOT/f["parent_design"]["source_workbook"], read_only=True, data_only=False)
    try:
        rows = list(book[f["parent_design"]["source_sheet"]].iter_rows(values_only=True))
        require(list(rows[0][1:15]) == obs["time"], "source time changed")
        for row in rows[1:]:
            if row[0] in obs["values"]:
                for source, value in zip(row[1:15], obs["values"][row[0]]): require(source == value, "original source cell changed")
    finally: book.close()
    for p, values in obs["values"].items(): require(f["initial"][rhs0.names.index(p)] == values[0], "measured J1 changed")
    time = np.array(obs["time"]); use = (time > 1)&(time <= d["horizon_day"])
    times = time[use]; target = np.array([obs["values"][p] for p in POOLS])[:, use]
    require(times.tolist() == d["times"], "nonoriginal sensitivity times")
    adenylates = [POOLS.index(p) for p in ("ATP", "ADP", "AMP")]
    denom = np.array(f["scales"]["absolute"])[:, None]+f["scales"]["relative"]*target
    def diagnostic(pred, recorded):
        log = np.log(pred[adenylates]/target[adenylates])
        working = np.mean(((pred-target)/denom)**2, axis=1)
        require(np.allclose(log.ravel(), recorded["adenylate_log_residuals"], rtol=1e-12, atol=1e-12), "log residual")
        require(abs(np.mean(log**2)-recorded["adenylate_log_mean"]) < 1e-10, "adenylate diagnostic")
        require(np.allclose(working, [recorded["working_MSE"][p] for p in POOLS], rtol=1e-12, atol=1e-12), "working residual")
    probe_rows = {}
    with np.load(out/"probes/baseline/trajectory.npz") as a: fixed = a["sample_states"].copy()
    for folder in sorted((out/"probes").iterdir()):
        check_seal(folder); r = json.loads((folder/"result.json").read_text()); probe_rows[r["label"]] = r
        if not r["valid"]: continue
        p = dict(f["parameters"])
        if r["parameter"] is not None:
            p[r["parameter"]] = f["resolved_parameters"][r["parameter"]]["value"]*float(np.exp(r["log_offset"]))
        rhs = JointRHS(p, f["kinetics"])
        with np.load(folder/"trajectory.npz") as a:
            require(np.array_equal(a["accepted_states"][:, 0], f["initial"]) and a["accepted_time"][-1] == 15., "probe initial or endpoint")
            require(np.array_equal(a["time"], times) and np.array_equal(a["observed"], target), "probe observations")
            require(np.array_equal(a["prediction"], np.array(r["predictions"])), "probe predictions")
            diagnostic(a["prediction"], r["diagnostics"])
            require(r["minimum_checked_mM"] >= -1e-10 and r["initial_exact"], "probe positivity")
            for j, t in enumerate(times):
                raw, executed, factors = rhs.rates(t, a["sample_states"][:, j])
                require(np.array_equal(raw, a["sample_raw_rates"][:, j]) and np.array_equal(executed, a["sample_executed_rates"][:, j])
                        and np.array_equal(factors, a["sample_availability"][:, j]), "saved/live sample rates")
                raw, executed, _ = rhs.rates(t, fixed[:, j])
                require(np.array_equal(raw, a["fixed_state_raw_rates"][:, j]) and np.array_equal(executed, a["fixed_state_executed_rates"][:, j]), "fixed-state derivatives")
    require(len(probe_rows) == s["actual_fast_integrations"] == 1+4*len(d["parameters"]), "actual probe count")
    columns = []
    for p, c in s["columns"].items():
        values = [np.array(probe_rows[p+"__"+key]["predictions"]) for key in ("plus", "minus", "half_plus", "half_minus")]
        full = ((np.log(values[0][adenylates])-np.log(values[1][adenylates]))/(2*d["log_step"])).ravel()
        half = ((np.log(values[2][adenylates])-np.log(values[3][adenylates]))/d["log_step"]).ravel()
        require(np.allclose(half, c["log_adenylate_derivative"], rtol=1e-12, atol=1e-12), "central derivative")
        require(np.allclose(full, c["full_log_derivative"], rtol=1e-12, atol=1e-12), "full-step derivative")
        relative = np.linalg.norm(full-half)/np.linalg.norm(half) if np.linalg.norm(half) else (0. if np.linalg.norm(full-half) == 0 else None)
        require((relative is None and c["relative_two_step_disagreement"] is None) or
            (relative is not None and c["relative_two_step_disagreement"] is not None and abs(relative-c["relative_two_step_disagreement"]) < 1e-9), "two-step stability")
        columns.append(half)
    base = s["baseline"]["diagnostics"]
    with np.load(parent/"audits"/(d["baseline_label"]+"_J15")/"J1_J15/glut_real_candidate_ultrastrict/replay.npz") as a:
        names = a["pool_names"].tolist()
        old = a["states"][[names.index(p) for p in ("ATP", "ADP", "AMP")]][:, np.searchsorted(a["time"], times)]
    baseline_noise = np.linalg.norm(np.log(np.array(s["baseline"]["predictions"])[adenylates]/old))
    require(abs(baseline_noise-s["baseline_fast_original_log_discrepancy_norm"]) < 1e-12, "baseline numerical signal")
    eligible = []
    def admission(diag):
        energy = all(diag["adenylate_log_MSE"][p] <= base["adenylate_log_MSE"][p]*(1+d["individual_adenylate_regression_fraction"])+1e-8 for p in ("ATP", "ADP", "AMP"))
        protect = all(diag["working_MSE"][p] <= base["working_MSE"][p]+d["protected_allowance_fraction"]*(1+base["working_MSE"][p]) for p in POOLS if p not in ("ATP", "ADP", "AMP"))
        gain = base["adenylate_log_mean"]-diag["adenylate_log_mean"]
        return energy, protect, gain, gain >= d["minimum_fractional_adenylate_log_gain"]*base["adenylate_log_mean"]
    for row in s["ranking"]:
        c = s["columns"][row["parameter"]]
        vector = np.array(c["log_adenylate_derivative"])
        gradient = float(2*np.array(base["adenylate_log_residuals"])@vector/len(vector))
        direction = -1 if gradient > 0 else 1
        expected_label = row["parameter"]+("__minus" if direction < 0 else "__plus")
        diag = probe_rows[expected_label]["diagnostics"]
        energy, protect, gain, gain_pass = admission(diag)
        stable = c["relative_two_step_disagreement"] is not None and c["relative_two_step_disagreement"] <= d["maximum_two_step_disagreement"]
        signal = np.linalg.norm(vector)*d["log_step"] >= max(d["minimum_log_response_norm"], d["numerical_signal_multiplier"]*baseline_noise)
        accepted = bool(energy and protect and gain_pass and stable and signal)
        require(row["direction"] == direction and row["probe_label"] == expected_label, "selected direction")
        require(abs(gain-row["actual_adenylate_log_gain"]) < 1e-10 and accepted == row["eligible_for_subset"], "subset admission")
        if accepted: eligible.append(row)
    eligible.sort(key=lambda r:r["actual_adenylate_log_gain"], reverse=True)
    selected = []
    for row in eligible:
        v = np.array(s["columns"][row["parameter"]]["log_adenylate_derivative"])
        cosines = []
        for old_row in selected:
            w = np.array(s["columns"][old_row["parameter"]]["log_adenylate_derivative"])
            cosines.append(abs(float(v@w)/(np.linalg.norm(v)*np.linalg.norm(w))))
        if not cosines or max(cosines) < d["maximum_subset_cosine"]: selected.append(row)
        if len(selected) >= d["maximum_subset_size"]: break
    require(selected == s["proposed_subset"], "correlated/unstable subset promoted")
    with np.load(out/"sensitivity.npz") as a:
        require(np.allclose(np.column_stack(columns), a["adenylate_log_jacobian"], rtol=1e-12, atol=1e-12), "Jacobian injection")
        singular = np.linalg.svd(a["adenylate_log_jacobian"], compute_uv=False)
        require(np.allclose(singular, a["singular_values"], rtol=1e-12, atol=1e-12), "SVD spectrum")
    check_seal(out/"coverage")
    cov = json.loads((out/"coverage/summary.json").read_text())
    model = json.loads((ROOT/d["gem_archive"]/"github/1.3.0/model/RBC-GEM.json").read_text())
    inverse = {v:k for k, v in pool_mapping(model).items()}
    for branch in BRANCHES.values():
        r = next(r for r in model["reactions"] if r["id"] == branch["gem_id"])
        projected, missing, _ = project_gem(r, inverse)
        require(not missing and projected == branch["stoichiometry"], "GEM branch projection")
    for r in cov["balance_relaxations"]:
        with np.load(out/"coverage"/f"{r['label']}_J{int(r['end_day'])}.npz") as a:
            z, e = a["extents"], a["adjustments"]
            columns0 = []
            for name in r["branches_enabled_in_stoichiometric_relaxation"]:
                v = np.zeros(len(rhs0.names))
                for pool, coefficient in BRANCHES[name]["stoichiometry"].items(): v[rhs0.names.index(pool)] = coefficient
                columns0.append(v)
            matrix = np.column_stack([rhs0.matrix, *columns0]) if columns0 else rhs0.matrix
            require(np.array_equal(a["matrix"], matrix[[rhs0.names.index(p) for p in r["pools"]]]), "coverage matrix injection")
            require(not r["branches_enabled_in_ODE"], "invented active network kinetics")
            require(np.max(np.abs(a["matrix"]@z-np.diff(a["observed"]+e, axis=1))) < 1e-6, "coverage LP primal")
            require(np.all(e[:, 0] == 0) and np.all(np.abs(e) <= r["minimum_working_error_multiplier"]*a["errors"]+1e-7), "coverage LP envelope")
            require(not np.any(a["matrix"][r["pools"].index("CITR")]), "CITR silently closed")
            for reaction in r["forward_reactions"]: require(z[r["reaction_names"].index(reaction)].min() >= -1e-7, "LP direction")
    numerical = json.loads((ROOT/f["parent_design"]["source_archive"]/"execution_design.json").read_text())["design"]
    selections = {r["label"]:r for r in s["original_audit_inputs"]}
    validated = []
    for a0 in s["audits"]:
        selected = selections[a0["label"]]; rhs = JointRHS(selected["parameters"], selected["glucose_kinetics"])
        source_probe = probe_rows[a0["label"]]
        p = dict(f["parameters"]); parameter = source_probe["parameter"]
        p[parameter] = f["resolved_parameters"][parameter]["value"]*float(np.exp(source_probe["log_offset"]))
        require(selected["parameters"] == p and selected["glucose_kinetics"] == f["kinetics"], "original audit parameter scope")
        folder = out/"audits"/(a0["label"]+"_J15"); check_seal(folder)
        pair, flags, admitted = [], [], []
        for result in a0["results"]:
            with np.load(folder/"J1_J15"/("glut_real_candidate_"+result["profile"])/"replay.npz") as a:
                require(np.array_equal(a["accepted_states"][:, 0], f["initial"]), "original J1 changed")
                minimum = min(a["states"][:113].min(), a["accepted_states"][:113].min())
                integrals = {}
                for order in (4, 8):
                    minimum = min(minimum, a[f"q{order}_states"][:113].min())
                    for kind in ("raw", "executed"):
                        rates, weights, cells = a[f"q{order}_{kind}_rates"], a[f"q{order}_weights"], a[f"q{order}_intervals"]
                        integrals[order, kind] = np.vstack([np.bincount(cells, weights=weights*v, minlength=len(a["boundaries"])-1) for v in rates])
                        require(close(integrals[order, kind], a[f"{kind}{order}"], numerical, "quadrature").all(), "quadrature weights")
                ix = np.searchsorted(a["time"], a["boundaries"])
                flags0 = [close(np.diff(a["states"][:113, ix]), a["matrix"]@integrals[8, "executed"], numerical, "quadrature"),
                    close(integrals[4, "raw"], integrals[8, "raw"], numerical, "quadrature"),
                    close(integrals[4, "executed"], integrals[8, "executed"], numerical, "quadrature")]
                valid = bool(all(v.all() for v in flags0) and minimum >= -1e-10 and result["raw_closure_max"] <= 1e-7 and result["executed_closure_max"] <= 1e-7)
                require(valid == result["numerical_pass"], "original numerical flag"); flags.append(valid)
                prediction = a["states"][[a["pool_names"].tolist().index(p) for p in POOLS]][:, np.searchsorted(a["time"], times)]
                log_errors = np.log(prediction[adenylates]/target[adenylates])
                original_diag = {"adenylate_log_MSE": dict(zip(("ATP", "ADP", "AMP"), np.mean(log_errors**2, axis=1))),
                    "working_MSE": dict(zip(POOLS, np.mean(((prediction-target)/denom)**2, axis=1))), "adenylate_log_mean": float(np.mean(log_errors**2))}
                energy, protect, gain, gain_pass = admission(original_diag)
                recorded = next(r for r in s["original_admissibility"][a0["label"]] if r["profile"] == result["profile"])
                require((energy, protect, gain_pass) == (recorded["individual_adenylate_pass"], recorded["protected_working_pass"], recorded["gain_pass"])
                        and abs(gain-recorded["actual_adenylate_log_gain"]) < 1e-10, "original admission")
                admitted.append(energy and protect and gain_pass)
                for j in np.unique(np.linspace(0, len(a["q8_nodes"])-1, 7).astype(int)):
                    t, x = a["q8_nodes"][j], a["q8_states"][:, j]
                    raw, executed, _ = rhs.rates(t, x)
                    require(np.array_equal(raw, a["q8_raw_rates"][:, j]) and np.array_equal(executed, a["q8_executed_rates"][:, j]), "original/live rates")
                    native = equadiff_glut_only(t, x, glucose_kinetics=selected["glucose_kinetics"], hematocrit=.58, custom_params=selected["parameters"],
                        positivity_policy="reaction_consistent", curve_fit_strength=0., reaction_availability_threshold=.001, ph_policy="clamped_diagnostic")
                    require(np.array_equal(native, rhs(t, x)), "original/fast RHS")
                with np.load(folder/"fast_parity.npz") as fast:
                    if result["profile"] == "ultrastrict": require(np.allclose(fast["states"][:113], a["states"][:113], rtol=.01, atol=1e-5), "full parity")
                pair.append((a["states"][:113].copy(), a["raw8"].copy(), a["executed8"].copy()))
        convergence = all(close(pair[0][j], pair[1][j], numerical, "comparison").all() for j in range(3))
        require(bool(all(flags) and convergence and a0["fast_full_parity"]) == a0["numerical_pass"], "audit summary")
        if a0["numerical_pass"] and all(admitted): validated += [r for r in s["proposed_subset"] if r["probe_label"] == a0["label"]]
    require(sorted(r["parameter"] for r in validated) == sorted(r["parameter"] for r in s["validated_single_levers"]), "unverified levers selected")
    require(not s["active_new_ODE_branches"] and not s["optimizer_run"] and not s["production_promoted"] and not s["joint_subset_tested"], "scope overclaim")
    require(s["all_original_audits_numerical_pass"] == all(a["numerical_pass"] for a in s["audits"]), "overall audit flag")
    return {"verified": True, "checks": count, "fast_integrations": len(probe_rows), "valid_fast_integrations": s["valid_fast_integrations"],
        "original_replays": 2*len(s["audits"]), "new_active_ODE_branches": [], "biological_calibration": False,
        "all_fast_ODEs_independently_reintegrated": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True); p.add_argument("--receipt", type=Path, required=True)
    a = p.parse_args()
    if a.receipt.exists(): raise ValueError("fresh receipt required")
    with threadpool_limits(1): result = verify(a.archive.resolve())
    a.receipt.parent.mkdir(parents=True, exist_ok=True); write(a.receipt, result)
    print(json.dumps(result, indent=2))
