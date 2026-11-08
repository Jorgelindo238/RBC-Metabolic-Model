"""Independent certificate lower bounds, source metrics and report provenance."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from run_glut_only_free_replay import write, sha


def verify(archive, report):
    count = 0
    def require(ok, reason):
        nonlocal count
        count += 1
        if not ok: raise ValueError(reason)
    f = json.loads((archive/"execution_design.json").read_text())
    s = json.loads((archive/"summary.json").read_text())
    obs = json.loads((archive/"observations.json").read_text())
    c = json.loads((report/"comparison.json").read_text())
    for folder in (archive, report):
        manifest = json.loads((folder/"manifest.json").read_text())
        for name, digest in manifest.get("input_sha256", {}).items(): require(sha(ROOT/name) == digest, "input hash:"+name)
        for name, digest in manifest["output_sha256"].items(): require(sha(folder/name) == digest, "output hash:"+name)
    for name, digest in f["input_sha256"].items(): require(sha(ROOT/name) == digest, "frozen input:"+name)
    balances = json.loads((archive/"balances/results.json").read_text())
    certificate_count, max_gap = 0, 0.
    for result in c["balance_certificates"]:
        original = next(r for r in balances if r["scope"] == result["scope"] and r["end_day"] == result["end_day"])
        with np.load(archive/"balances"/f"{result['scope']}_J{int(result['end_day'])}.npz") as a:
            m, y, errors, t = a["matrix"], a["observed"], a["scales"], a["time"]
            forward = [original["reaction_names"].index(r) for r in original["forward_direction_subset"]]
            signed = [j for j in range(m.shape[1]) if j not in forward]
            lower_bounds = []
            for cert in result["certificates"]:
                w = np.array([cert["coefficients"].get(p, 0.) for p in original["pools"]])
                row = w@m
                if cert["kind"] == "constant": require(np.max(np.abs(row)) < 1e-10, "false invariant")
                else:
                    require(np.max(np.abs(row[signed]), initial=0) < 1e-10, "false signed-column cancellation")
                    sign = 1 if cert["kind"] == "nonincreasing" else -1
                    require(np.max(sign*row[forward], initial=0) <= 1e-10, "false monotonicity")
                signal = w@y
                band = np.abs(w)@errors; band[0] = 0
                lower = 0.
                for i in range(len(t)-1):
                    for j in range(i+1, len(t)):
                        change = signal[j]-signal[i]
                        needed = abs(change) if cert["kind"] == "constant" else max(0., sign*change)
                        den = band[i]+band[j]
                        if den: lower = max(lower, needed/den)
                require(abs(lower-cert["minimum_working_multiplier_lower_bound"]) < 1e-10, "certificate bound")
                require(np.allclose(signal, cert["source_combination"], rtol=0, atol=1e-12), "certificate source data")
                lower_bounds.append(lower); certificate_count += 1
            # A feasible primal witness plus an equal analytic lower bound proves
            # this relaxation optimum, without assuming uniqueness of the witness.
            z, e, multiplier = a["extents"], a["adjustments"], original["minimum_working_error_multiplier"]
            require(np.max(np.abs(m@z-np.diff(y+e, axis=1))) < 1e-6, "LP primal witness")
            require(np.all(np.abs(e) <= multiplier*errors+1e-7) and np.all(e[:, 0] == 0) and (y+e).min() >= -1e-7, "LP witness band/J1")
            require(all(z[j].min() >= -1e-7 for j in forward), "LP witness direction")
            gap = abs(multiplier-max(lower_bounds)); max_gap = max(max_gap, gap)
            require(gap < 1e-7 and result["relaxation_optimum_certified"], "unproved LP optimum")
    labels = {r["label"]: r for r in s["fits"]}
    max_budget_difference = 0.
    for item in c["full_evaluation"]:
        fit = labels[item["label"]]
        end = item["evaluation_end_day"]
        path = archive/"audits"/(fit["label"]+f"_J{int(end)}")/f"J1_J{int(end)}/glut_real_candidate_ultrastrict/replay.npz"
        with np.load(path) as a:
            names = a["pool_names"].tolist()
            time = np.array(obs["time"]); post = (time > 1)&(time <= end)
            for p, values in obs["values"].items():
                predicted = a["states"][names.index(p), np.searchsorted(a["time"], time[post])]
                delta = predicted-np.array(values)[post]
                recorded = item["all55_metrics"][p]
                for key, use in (("J4_J8_RMSE_mM", time[post] <= 10),
                    ("training_RMSE_mM", time[post] <= fit["end_day"]), ("available_postinitial_RMSE_mM", np.ones(len(delta), bool))):
                    actual = float(np.sqrt(sum(float(v)**2 for v in delta[use])/int(use.sum())))
                    require(abs(actual-recorded[key]) < 1e-10, "pool RMSE:"+p)
                require(recorded["endpoint_mM"] == predicted[-1] and recorded["nominal_endpoint_mM"] == values[int(post.sum())], "endpoint:"+p)
            for p, recorded in item["executed_budgets"].items():
                values = a["matrix"][names.index(p), :, None]*a["q8_executed_rates"]
                production = float(np.sum(np.maximum(values, 0)*a["q8_weights"]))
                consumption = float(-np.sum(np.minimum(values, 0)*a["q8_weights"]))
                differences = [abs(production-recorded["production_mM"]), abs(consumption-recorded["consumption_mM"]),
                               abs(production-consumption-recorded["net_integrated_mM"])]
                max_budget_difference = max(max_budget_difference, max(differences))
                require(max(differences) < 1e-9, "executed signed budget:"+p)
    require(c["working_scales_are_not_assay_SD"] and c["relative_contract_is_not_yet_generic_relative_ODE_fit"]
            and not c["production_promoted"], "report overclaim")
    return {"passed": True, "checks": count, "analytic_certificates": certificate_count,
        "independently_certified_relaxation_optima": len(c["balance_certificates"]), "maximum_LP_primal_bound_gap": max_gap,
        "source_pool_comparisons": 55*len(c["full_evaluation"]), "maximum_budget_difference_mM": max_budget_difference,
        "verifier_sha256": sha(Path(__file__)), "biological_validation": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True); p.add_argument("--report", type=Path, required=True)
    p.add_argument("--receipt", type=Path, required=True)
    a = p.parse_args()
    if a.receipt.exists(): raise ValueError("fresh receipt required")
    result = verify(a.archive.resolve(), a.report.resolve())
    write(a.receipt, result); print(json.dumps(result, indent=2))
