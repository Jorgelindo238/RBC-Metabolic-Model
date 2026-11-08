"""Independent report, LP-certificate and original protein-cell checks."""

import argparse
import csv
import json
from pathlib import Path
import sys

import numpy as np
from openpyxl import load_workbook
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from run_glut_only_free_replay import sha, write
from run_protected_joint import verify_inputs, check_seal


def verify(archive, validation):
    count = 0

    def check(condition, label):
        nonlocal count
        count += 1
        if not condition:
            raise ValueError(label)

    def close(actual, expected, label, *, rtol=1e-10, atol=1e-12):
        check(np.allclose(actual, expected, rtol=rtol, atol=atol), label)

    def manifest(folder):
        m = json.loads((folder / "manifest.json").read_text())
        for relative, digest in m.get("input_sha256", {}).items():
            check(sha(ROOT / relative) == digest, f"input:{relative}")
        for relative, digest in m["output_sha256"].items():
            check(sha(folder / relative) == digest, f"output:{relative}")

    frozen = verify_inputs(archive)
    followup, report = validation / "asl_followup", validation / "comparison"
    for folder in (archive, followup, report):
        manifest(folder)
    main = json.loads((archive / "summary.json").read_text())
    coverage = json.loads((archive / "coverage/summary.json").read_text())
    extra = json.loads((followup / "summary.json").read_text())
    result = json.loads((report / "comparison.json").read_text())
    obs = json.loads((archive / "observations.json").read_text())
    times = np.array(obs["time"])
    mask = (times > 1) & (times <= 15)
    parent = ROOT / frozen["design"]["parent_archive"]
    baseline_label = frozen["design"]["baseline_label"]
    baseline = parent / "audits" / (baseline_label + "_J15")
    paths = {"baseline": baseline / "J1_J15/glut_real_candidate_ultrastrict/replay.npz"}
    paths.update({a["label"]: archive / "audits" / (a["label"] + "_J15") /
                  "J1_J15/glut_real_candidate_ultrastrict/replay.npz" for a in main["audits"]})
    reference_rmse = {}
    metric_rows, budget_rows = 0, 0
    for row in result["original_comparisons"]:
        path = paths[row["label"]]
        check_seal(path.parents[2])
        with np.load(path) as a:
            names, reactions = a["pool_names"].tolist(), a["reactions"].tolist()
            indices = np.searchsorted(a["time"], times[mask])
            close(a["time"][indices], times[mask], "actual observation times", atol=0, rtol=0)
            for pool, values in obs["values"].items():
                p = a["states"][names.index(pool), indices]
                rmse = float(np.sqrt(np.mean((p - np.array(values)[mask]) ** 2)))
                m = row["all55_metrics"][pool]
                close(p, m["predictions"], "source predictions")
                close([rmse, p[-1]], [m["RMSE_mM"], m["J15_mM"]], "source metrics")
                if row["label"] == "baseline":
                    reference_rmse[pool] = rmse
                close(rmse-reference_rmse[pool], m["RMSE_change_vs_baseline_mM"], "metric delta")
                metric_rows += 1
            for pool, b in row["budgets"].items():
                stoich = a["matrix"][names.index(pool)]
                for key, rate in (("executed", "q8_executed_rates"),
                                  ("raw_on_executed_trajectory", "q8_raw_rates")):
                    terms = stoich[:, None] * a[rate]
                    production = np.sum(np.where(terms > 0, terms, 0) * a["q8_weights"])
                    consumption = -np.sum(np.where(terms < 0, terms, 0) * a["q8_weights"])
                    close([production, consumption], [b[key]["production_mM"], b[key]["consumption_mM"]], "signed budget")
                integrated = np.sum(a["executed8"], axis=1) * stoich
                close(integrated.sum(), b["net_executed_integral_mM"], "net budget")
                close(a["states"][names.index(pool), -1] - a["states"][names.index(pool), 0],
                      b["state_change_mM"], "state difference")
                check({r: float(v) for r, v in zip(reactions, integrated) if v != 0} ==
                      b["reaction_contributions_mM"], "reaction contributions")
                budget_rows += 1
    with np.load(archive / "sensitivity.npz") as a:
        jac, names = a["adenylate_log_jacobian"], a["parameter_names"].tolist()
        singular = np.linalg.svd(jac, compute_uv=False)
        close(singular, result["singular_values"], "singular values")
        rank = int(np.sum(singular > singular[0] * 1e-6))
        check(rank == result["local_rank"] and len(names)-rank == result["local_nullity_lower_bound"], "local rank/nullity")
        check(jac.shape == (12, 25), "four-time adenylate sensitivity dimensions")
    certificates, certified_minima = 0, []
    cases = [(archive / "coverage" / f"{r['label']}_J{int(r['end_day'])}.npz", r)
             for r in coverage["balance_relaxations"]]
    cases += [(followup / f"J{int(r['end_day'])}.npz", r) for r in extra["results"]]
    for path, r in cases:
        forward_names = r.get("forward_reactions")
        if forward_names is None:
            forward_names = next(x["forward_reactions"] for x in coverage["balance_relaxations"]
                                 if x["label"] == "both_candidates" and x["end_day"] == r["end_day"])
        forward = np.array([name in forward_names for name in r["reaction_names"]])
        with np.load(path) as a:
            m, y, sigma, t = (a[k] for k in ("matrix", "observed", "errors", "time"))
            z, e = a["extents"], a["adjustments"]
            multiplier = r["minimum_working_error_multiplier"]
            check(np.max(np.abs(m @ z - np.diff(y + e, axis=1))) <= 1e-6, "LP primal balance")
            check(np.all(e[:, 0] == 0), "LP exact J1")
            check(np.all(y + e >= -1e-7), "LP nonnegative adjusted observations")
            check(np.all(np.abs(e) <= multiplier*sigma + 1e-7), "LP engineering error bands")
            check(np.all(z[forward] >= -1e-7), "LP forward cone")
            lower = 0.
            for c in r["certificates"]:
                w = np.array([c["coefficients"].get(p, 0.) for p in r["pools"]])
                combination = w @ m
                close(combination, c["matrix_combination"], "certificate matrix row")
                check(np.max(np.abs(combination[~forward]), initial=0) <= 1e-11, "certificate signed annihilation")
                if c["kind"] == "constant":
                    check(np.max(np.abs(combination), initial=0) <= 1e-11, "constant certificate")
                    sign = 0
                elif c["kind"] == "nonincreasing":
                    check(np.max(combination[forward], initial=0) <= 1e-11, "decreasing certificate")
                    sign = 1
                elif c["kind"] == "nondecreasing":
                    check(np.min(combination[forward], initial=0) >= -1e-11, "increasing certificate")
                    sign = -1
                else:
                    raise ValueError("unknown certificate kind")
                values, scales = w @ y, np.abs(w) @ sigma
                scales[0] = 0
                bound = 0.
                for i in range(len(t)-1):
                    for j in range(i+1, len(t)):
                        delta = values[j] - values[i]
                        violation = abs(delta) if sign == 0 else max(0., sign*delta)
                        denominator = scales[i] + scales[j]
                        if denominator == 0:
                            check(violation <= 1e-11, "zero band contradiction")
                        else:
                            bound = max(bound, violation/denominator)
                close(bound, c["minimum_working_multiplier_lower_bound"], "analytic lower bound")
                lower = max(lower, bound)
                certificates += 1
            close(lower, multiplier, "primal/analytic optimum agreement", atol=1e-7)
            certified_minima.append({"file": path.relative_to(ROOT).as_posix(), "multiplier": multiplier,
                                     "primal_lower_bound_gap": multiplier-lower})
    copies = ROOT / "output/palsson_proteomics_review_2026_10_06/human_protein_copy_numbers.csv"
    workbook = ROOT / "output/palsson_proteomics_review_2026_10_06/source_files/Supplementary Table 1 - FINAL.xlsx"
    with copies.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    book = load_workbook(workbook, read_only=True, data_only=False)
    protein_checks = []
    try:
        for gene in ("ACLY", "ARG1", "ASL", "ASS1", "ANKH"):
            found = [r for r in rows if r["gene"] == gene]
            check(len(found) == 1, "unique protein source row")
            r = found[0]
            cells = next(book[r["sheet"]].iter_rows(min_row=int(r["source_row"]), max_row=int(r["source_row"]), max_col=7, values_only=True))
            check(r["uniprot_id"] in cells and gene in cells, "original protein identity")
            close([float(r["copy_number_per_cell_F"]), float(r["multi_anchor_copy_number_per_cell_G"])],
                  [cells[5], cells[6]], "original F/G copy numbers", atol=0, rtol=0)
            protein_checks.append({"gene": gene, "source_row": int(r["source_row"]),
                                   "F": cells[5], "G": cells[6], "active_capacity_inferred": False})
    finally:
        book.close()
    levers = json.loads((report / "next_single_levers.json").read_text())
    for lever in levers["levers"]:
        value = frozen["resolved_parameters"][lever["parameter"]]["value"]
        close(value, lever["baseline_value"], "lever baseline")
        close(value*np.exp(lever["direction"]*frozen["design"]["log_step"]), lever["tested_value"], "lever probe")
    check({r["parameter"] for r in levers["levers"]} == {"vmax_VSAM", "vmax_VPGK"}, "validated single levers")
    for flag in ("activation_with_new_coverage_branches_tested", "combined_activation_tested", "new_optimization_run", "production_promoted"):
        check(levers[flag] is False, flag)
    check(main["active_new_ODE_branches"] == [] and extra["used_for_parameter_selection"] is False, "no hidden branch activation")
    for folder in (archive, followup, report):
        manifest(folder)
    return {"verified": True, "checks": count, "source_metric_rows": metric_rows,
            "signed_pool_budget_pairs": budget_rows, "analytic_certificates": certificates,
            "certified_LP_minima": certified_minima, "original_protein_cells": protein_checks,
            "verification_source_sha256": sha(Path(__file__)),
            "protein_workbook_sha256": sha(workbook), "protein_csv_sha256": sha(copies),
            "all_fast_ODEs_independently_reintegrated": False, "biological_calibration": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--validation", type=Path, required=True)
    p.add_argument("--receipt", type=Path, required=True)
    args = p.parse_args()
    if args.receipt.exists():
        raise ValueError("fresh verification receipt required")
    with threadpool_limits(1):
        result = verify(args.archive.resolve(), args.validation.resolve())
    write(args.receipt, result)
    print(json.dumps({k: v for k, v in result.items() if k in ("verified", "checks", "source_metric_rows", "signed_pool_budget_pairs", "analytic_certificates")}, indent=2))
