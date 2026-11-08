"""Fixed two-factor screen with original ODE, matched tolerances and all55 guards."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
import json
from pathlib import Path
import sys

import numpy as np
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fla_adenylate_sensitivity import ADENYLATES, perturb
from fla_joint_calibration import JointRHS
from rbc_glut_only_transport import equadiff_glut_only
from run_broad_protected_joint import audit
from run_glut_only_free_replay import close, sha, write
from run_protected_joint import check_seal, seal, verify_inputs

CONFIG = ROOT / "config/fla_vsam_pgk_screen.json"
JOINT = ("joint_full", "joint_half")
CONTROL = ("baseline", "VSAM_down", "PGK_down")


def read(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def working_scales(target, design):
    target = np.asarray(target, float)
    require(np.isfinite(target).all() and np.all(target >= 0), "finite nonnegative observations required")
    bands = (design["absolute_scale_fraction"] * np.median(target, axis=1)[:, None]
             + design["relative_scale_fraction"] * target)
    require(np.all(bands > 0), "undefined scale; no implicit detection limit")
    return bands


def score(prediction, target, bands, pools):
    prediction = np.asarray(prediction)
    require(prediction.shape == target.shape == bands.shape and np.isfinite(prediction).all(), "invalid sampled trajectory")
    aden = [pools.index(p) for p in ADENYLATES]
    x, y = prediction[aden], target[aden]
    require(np.all(x > 0) and np.all(y > 0), "log adenylates require positive values; no pseudocount")
    log_error = np.log(x / y)
    error = prediction - target
    return {"RMSE_mM": np.sqrt(np.mean(error**2, axis=1)).tolist(),
            "working_MSE": np.mean((error/bands)**2, axis=1).tolist(),
            "adenylate_log_MSE": np.mean(log_error**2, axis=1).tolist(),
            "adenylate_log_mean": float(np.mean(log_error**2)),
            "adenylate_log_error": log_error.tolist(),
            "adenylate_total_mM": x.sum(axis=0).tolist(),
            "energy_charge": ((x[0] + .5*x[1])/x.sum(axis=0)).tolist()}


def guard(metrics, baseline, pools, days, d):
    base = np.array(baseline["working_MSE"])
    off = np.array(metrics["working_MSE"]) - base > d["working_MSE_allowance_fraction"]*(1+base)
    per = np.array(metrics["adenylate_log_MSE"]) > (1+d["individual_adenylate_log_MSE_allowance_fraction"])*np.array(baseline["adenylate_log_MSE"])+1e-8
    point = (np.abs(metrics["adenylate_log_error"]) - np.abs(baseline["adenylate_log_error"]) >
             np.log1p(d["pointwise_adenylate_error_ratio_allowance"]))
    base_loss = baseline["adenylate_log_mean"]
    gain = base_loss - metrics["adenylate_log_mean"]
    return {"all55_failures": [p for p, failed in zip(pools, off) if failed],
            "adenylate_mean_failures": [p for p, failed in zip(ADENYLATES, per) if failed],
            "adenylate_point_failures": [{"pool": ADENYLATES[i], "day": days[j]} for i, j in np.argwhere(point)],
            "gain": gain, "gain_percent": 100*gain/base_loss if base_loss else None,
            "pass": bool(not (off.any() or per.any() or point.any()) and gain > 0 and
                         gain >= d["minimum_gain_fraction_of_baseline"]*base_loss)}


def contrast(baseline, sam, pgk, joint):
    return np.asarray(joint) - np.asarray(sam) - np.asarray(pgk) + np.asarray(baseline)


def verify_manifest(folder):
    for name, digest in read(folder / "manifest.json")["output_sha256"].items():
        require(sha(folder / name) == digest, f"changed archived artifact: {folder/name}")


def prepare(out):
    require(not out.exists(), "fresh successor archive required")
    d = read(CONFIG)
    source, validation = ROOT/d["sensitivity_archive"], ROOT/d["validation_archive"]
    parent = verify_inputs(source)
    check_seal(validation)
    verify_manifest(source)
    require(read(validation/"verification.json")["verified"], "unverified sensitivity parent")
    require(read(validation/"report_final_verification.json")["verified"], "unverified parent report")
    old = ROOT/parent["design"]["parent_archive"]
    previous = read(source/"summary.json")
    inputs = {r["label"]: r for r in previous["original_audit_inputs"]}
    levers = {r["parameter"]: r for r in read(validation/"comparison/next_single_levers.json")["levers"]}
    require(set(levers) == set(d["parameters"]) and all(r["direction"] == -1 for r in levers.values()), "unexpected parent lever scope")
    require(previous["active_new_ODE_branches"] == [] and not previous["joint_subset_tested"], "unexpected active network or parent joint run")
    d["training_end_day"] = parent["design"]["training_end_day"]  # Historical guard diagnostics only.
    require(d["horizon_day"] == parent["design"]["horizon_day"] and d["sample_days"] == parent["design"]["times"], "changed time contract")
    step = parent["design"]["log_step"]
    cases = {}
    for label, fractions in d["step_fractions"].items():
        parameters = dict(parent["parameters"])
        offsets = [-step*x for x in fractions]
        for p, offset in zip(d["parameters"], offsets):
            if offset:
                parameters = perturb(parameters, p, levers[p]["baseline_value"], offset)
        cases[label] = {"label": label, "selected_log_factors": offsets, "parameters": parameters,
                        "glucose_kinetics": parent["kinetics"]}
    original = old/"fits"/parent["design"]["baseline_label"]/"result.json"
    require(cases["baseline"]["parameters"] == read(original)["parameters"], "baseline parameters changed")
    reuse = {"baseline": old/"audits"/(parent["design"]["baseline_label"]+"_J15")}
    for label, p in zip(CONTROL[1:], d["parameters"]):
        name = levers[p]["source_probe"]
        require(cases[label]["parameters"] == inputs[name]["parameters"] and
                cases[label]["parameters"][p] == levers[p]["tested_value"], "single-lever reuse mismatch")
        reuse[label] = source/"audits"/(name+"_J15")
    paths = [CONFIG, Path(__file__), ROOT/"qa/test_vsam_pgk_screen.py", source/"manifest.json",
             source/"execution_design.json", source/"observations.json", original,
             validation/"files_seal.json", validation/"report_final_verification.json",
             validation/"comparison/next_single_levers.json"]
    for folder in reuse.values():
        check_seal(folder)
        paths += [folder/"files_seal.json"]
        require(read(folder/"audit_summary.json")["numerical_pass"], "control audit not passed")
    paths += [ROOT/p for p in parent["input_sha256"]]
    f = {k: parent[k] for k in ("initial", "kinetics", "guards", "parent_design", "parameters")}
    f.update(design=d, cases=cases, baseline_capacities={p: levers[p]["baseline_value"] for p in d["parameters"]},
             reuse={k: v.relative_to(ROOT).as_posix() for k, v in reuse.items()},
             input_sha256={p.relative_to(ROOT).as_posix(): sha(p) for p in paths})
    out.mkdir(parents=True)
    write(out/"execution_design.json", f)
    write(out/"observations.json", read(source/"observations.json"))
    write(out/"source_seal.json", {p: sha(out/p) for p in ("execution_design.json", "observations.json")})
    return f


def run_case(out, f, label):
    with threadpool_limits(1):
        return audit(out, f, f["cases"][label], f["design"]["horizon_day"])


def reconstruct(out, f):
    d, obs = f["design"], read(out/"observations.json")
    pools = list(obs["values"])
    days = d["sample_days"]
    require(len(pools) == 55 and len(obs["time"]) == 14, "55 original source channels required")
    target = np.array([[obs["values"][p][obs["time"].index(t)] for t in days] for p in pools])
    bands = working_scales(target, d)
    numerical = read(ROOT/f["parent_design"]["source_archive"]/"execution_design.json")["design"]
    cases, detail, flux = {}, [], []
    qcounts = {"daily_balances": 0, "raw_quadrature": 0, "executed_quadrature": 0,
               "cross_tolerance": 0, "live_rate_checkpoints": 0}
    for label in (*CONTROL, *JOINT):
        folder = ROOT/f["reuse"][label] if label in f["reuse"] else out/"audits"/(label+"_J15")
        check_seal(folder)
        audit_result = read(folder/"audit_summary.json")
        parameters = f["cases"][label]["parameters"]
        rhs = JointRHS(parameters, f["kinetics"])
        pair, flags, rows = [], [], {}
        for profile in d["profiles"]:
            path = folder/"J1_J15"/("glut_real_candidate_"+profile)
            evidence = read(path/"result.json")
            with np.load(path/"replay.npz") as a:
                names, reactions = a["pool_names"].tolist(), a["reactions"].tolist()
                require(np.array_equal(a["matrix"], rhs.matrix) and reactions == list(rhs.reactions), "network changed")
                require(np.array_equal(a["accepted_states"][:, 0], f["initial"]) and
                        all(f["initial"][names.index(p)] == obs["values"][p][0] for p in pools), "exact J1 changed")
                i = np.searchsorted(a["time"], days)
                require(np.array_equal(a["time"][i], days), "actual observation times required")
                prediction = a["states"][[names.index(p) for p in pools]][:, i]
                metrics = score(prediction, target, bands, pools)
                integral = {}
                for order in (4, 8):
                    for kind in ("raw", "executed"):
                        cells, weights = a[f"q{order}_intervals"], a[f"q{order}_weights"]
                        integral[order, kind] = np.array([np.bincount(cells, weights=weights*v, minlength=14)
                                                          for v in a[f"q{order}_{kind}_rates"]])
                        require(close(integral[order, kind], a[f"{kind}{order}"], numerical, "quadrature").all(), "quadrature reconstruction failed")
                states = a["states"][:113]
                cuts = np.searchsorted(a["time"], a["boundaries"])
                balance = close(np.diff(states[:, cuts]), a["matrix"]@integral[8, "executed"], numerical, "quadrature")
                minimum = float(min(states.min(), a["accepted_states"][:113].min(), a["q4_states"][:113].min(), a["q8_states"][:113].min()))
                comparisons = {"daily_balances": balance,
                               **{k+"_quadrature": close(integral[4, k], integral[8, k], numerical, "quadrature") for k in ("raw", "executed")}}
                for k, v in comparisons.items():
                    qcounts[k] += int(v.sum()) if label in JOINT else 0
                valid = bool(all(v.all() for v in comparisons.values()) and minimum >= numerical["negative_tolerance_mM"]
                             and max(evidence["raw_closure_max"], evidence["executed_closure_max"]) <= numerical["closure_atol_mM_per_day"])
                require(valid == evidence["numerical_pass"], "recomputed numerical flag differs")
                for j in np.linspace(0, len(a["q8_nodes"])-1, 7).astype(int):
                    t, x = a["q8_nodes"][j], a["q8_states"][:, j]
                    native = {}
                    derivative = equadiff_glut_only(t, x, glucose_kinetics=f["kinetics"], custom_params=parameters,
                        hematocrit=numerical["hematocrit"], positivity_policy="reaction_consistent", curve_fit_strength=0.,
                        reaction_availability_threshold=numerical["availability_threshold_mM"], ph_policy="clamped_diagnostic", numerical_audit=native)
                    for key, kind in (("raw_fluxes", "raw"), ("effective_fluxes", "executed")):
                        require(np.array_equal([native[key][r] for r in reactions], a[f"q8_{kind}_rates"][:, j]), "live flux or parameter mismatch")
                    require(np.array_equal(derivative, rhs(t, x)), "original/fast RHS mismatch")
                    qcounts["live_rate_checkpoints"] += 1
                budgets = {}
                weights = a["q8_weights"]
                for p in ADENYLATES:
                    terms = a["matrix"][names.index(p), :, None]*a["q8_executed_rates"]
                    budgets[p] = {"production_mM": float(np.sum(np.maximum(terms, 0)*weights)),
                                  "consumption_mM": float(-np.sum(np.minimum(terms, 0)*weights)),
                                  "net_by_reaction_mM": dict(zip(reactions, (terms@weights).tolist())),
                                  "delta_state_mM": float(states[names.index(p), -1]-states[names.index(p), 0])}
                raw, executed = integral[8, "raw"], integral[8, "executed"]
                for r, vr, ve in zip(reactions, raw.sum(axis=1), executed.sum(axis=1)):
                    flux.append([label, profile, r, float(vr), float(ve)])
                pair.append((states.copy(), raw, executed))
                flags.append(valid)
                rows[profile] = {"prediction_mM": prediction.tolist(), "minimum_checked_mM": minimum,
                                 "metrics": metrics, "executed_adenylate_budgets": budgets}
        cross = [close(x, y, numerical, "comparison") for x, y in zip(*pair)]
        if label in JOINT:
            qcounts["cross_tolerance"] += sum(int(v.sum()) for v in cross)
        with np.load(folder/"fast_parity.npz") as fast:
            parity = np.allclose(fast["states"][:113], pair[1][0], rtol=.01, atol=1e-5)
        numeric = bool(all(flags) and all(v.all() for v in cross) and parity and audit_result["fast_full_parity"])
        require(numeric == audit_result["numerical_pass"], "original audit flag changed")
        cases[label] = {"numerical_pass": numeric, "profiles": rows, "archive_reused": label in CONTROL,
                        "tested_capacities": {p: parameters.get(p, f["baseline_capacities"][p]) for p in d["parameters"]}}
    references, interactions = {}, {}
    for profile in d["profiles"]:
        base = cases["baseline"]["profiles"][profile]["metrics"]
        for label, case in cases.items():
            row = case["profiles"][profile]
            row["guards"] = guard(row["metrics"], base, pools, days, d)
            for i, p in enumerate(pools):
                rmse, work = row["metrics"]["RMSE_mM"][i], row["metrics"]["working_MSE"][i]
                detail.append([label, profile, p, p in ("B13PG", "P2G"), rmse, rmse-base["RMSE_mM"][i],
                               work, p in row["guards"]["all55_failures"], *row["prediction_mM"][i]])
        references[profile] = min((label for label in CONTROL if label == "baseline" or
                                   (cases[label]["numerical_pass"] and cases[label]["profiles"][profile]["guards"]["pass"])),
                                  key=lambda label: cases[label]["profiles"][profile]["metrics"]["adenylate_log_mean"])
        best = cases[references[profile]]["profiles"][profile]["metrics"]["adenylate_log_mean"]
        for label in JOINT:
            row = cases[label]["profiles"][profile]
            increment = best-row["metrics"]["adenylate_log_mean"]
            row["increment_over_best_control"] = increment
            row["increment_pass"] = increment >= d["minimum_increment_over_admissible_single_fraction_of_baseline"]*base["adenylate_log_mean"]
        corners = [cases[label]["profiles"][profile] for label in (*CONTROL, "joint_full")]
        interactions[profile] = {"mean_log_MSE_contrast": float(contrast(*(r["metrics"]["adenylate_log_mean"] for r in corners))),
                                 "all55_concentration_contrast_mM": contrast(*(r["prediction_mM"] for r in corners)).tolist(),
                                 "interpretation": "difference_of_differences_at_full_step_not_statistical_synergy"}
    eligible = [label for label in JOINT if cases[label]["numerical_pass"] and all(r["guards"]["pass"] and r["increment_pass"]
                                                                                for r in cases[label]["profiles"].values())]
    chosen = min(eligible, key=lambda label: cases[label]["profiles"]["ultrastrict"]["metrics"]["adenylate_log_mean"]) if eligible else None
    return {"pool_order": pools, "sample_days": days, "nominal_mM": target.tolist(), "engineering_scales_mM": bands.tolist(),
            "cases": cases, "best_admissible_control": references, "full_step_interaction": interactions,
            "eligible_joint_cases": eligible, "conditional_joint_candidate": chosen, "verification_counts": qcounts,
            "new_original_ODE_replays": 4, "new_fast_parity_replays": 2, "reused_original_ODE_replays": 6,
            "optimizer_run": False, "production_promoted": False, "biological_calibration": False}, detail, flux


def write_csv(path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)


def run(out):
    f = prepare(out)
    print("Frozen five-point screen: 6 reused original replays, 4 new original replays", flush=True)
    with ProcessPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(run_case, out, f, label) for label in JOINT]
        for job in as_completed(jobs):
            result = job.result()
            print(f"{result['label']} original audits complete: {result['numerical_pass']}", flush=True)
    with threadpool_limits(1):
        result, rows, flux = reconstruct(out, verify_inputs(out))
    write(out/"summary.json", result)
    write_csv(out/"all55_metrics.csv", ["case", "profile", "pool", "source_alias", "RMSE_mM", "delta_RMSE_mM", "working_MSE",
                                        "working_guard_failed", "J4_mM", "J8_mM", "J11_mM", "J15_mM"], rows)
    write_csv(out/"flux_integrals.csv", ["case", "profile", "reaction", "raw_integral", "executed_integral"], flux)
    write(out/"manifest.json", {"output_sha256": {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob("*")) if p.is_file()}})
    return {"joint_candidate": result["conditional_joint_candidate"], "case_profile_pool_rows": len(rows),
            "original_replays": 4, "verification_counts": result["verification_counts"]}


def verify(out, receipt):
    require(not receipt.exists() and not receipt.is_relative_to(out), "fresh external receipt required")
    verify_manifest(out)
    f = verify_inputs(out)
    with threadpool_limits(1):
        result, rows, flux = reconstruct(out, f)
    require(result == read(out/"summary.json"), "reconstructed summary changed")
    for filename, expected in (("all55_metrics.csv", rows), ("flux_integrals.csv", flux)):
        with (out/filename).open(newline="", encoding="utf-8") as stream:
            reader = csv.reader(stream)
            next(reader)
            require(list(reader) == [[str(x) for x in row] for row in expected], "reconstructed CSV changed")
    result = {"verified": True, "case_profile_pool_rows": len(rows), "flux_integral_rows": len(flux),
              "verification_counts": result["verification_counts"], "new_ODE_integrations_in_verifier": 0,
              "archive_manifest_sha256": sha(out/"manifest.json"), "biological_calibration": False}
    receipt.parent.mkdir(parents=True, exist_ok=True)
    write(receipt, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--verify-receipt", type=Path)
    args = parser.parse_args()
    folder = args.out.resolve()
    print(json.dumps(verify(folder, args.verify_receipt.resolve()) if args.verify_receipt else run(folder), indent=2))
