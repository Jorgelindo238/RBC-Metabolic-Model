"""Independent source-cell, comparison and executed-budget close-out."""

import argparse
import json
import math
from pathlib import Path
import sys

import numpy as np
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from run_glut_only_free_replay import sha, write


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
    parent = ROOT/f["design"]["parent_archive"]
    ps = json.loads((parent/"summary.json").read_text())
    for folder in (archive, report):
        manifest = json.loads((folder/"manifest.json").read_text())
        for name, digest in manifest.get("input_sha256", {}).items(): require(sha(ROOT/name) == digest, "input hash:"+name)
        for name, digest in manifest["output_sha256"].items(): require(sha(folder/name) == digest, "output hash:"+name)
    for name, digest in f["input_sha256"].items(): require(sha(ROOT/name) == digest, "frozen source hash:"+name)
    parent_f = json.loads((parent/"execution_design.json").read_text())
    require(f["guards"] == parent_f["guards"] and f["initial"] == parent_f["initial"], "guard/initial contract changed")
    require({k for k, v in s["selected"]["parameters"].items() if v != f["parameters"].get(k)} <= {"vmax_VHK", "vmax_VPFK"}, "out of scope parameter")
    require(s["selected"]["glucose_kinetics"] == f["kinetics"], "GLUT changed")
    book = load_workbook(ROOT/f["parent_design"]["source_workbook"], read_only=True, data_only=False)
    source_cells = 0
    try:
        rows = list(book[f["parent_design"]["source_sheet"]].iter_rows(values_only=True))
        require(list(rows[0][1:15]) == obs["time"], "source time changed")
        for row in rows[1:]:
            if row[0] in obs["values"]:
                for value, archived in zip(row[1:15], obs["values"][row[0]]):
                    require(value == archived, "source value changed")
                    source_cells += 1
        require(source_cells == 770, "incomplete source audit")
    finally: book.close()
    paths = {"parent": parent/"audits"/(ps["selected"]["label"]+"_J46")/"J1_J46/glut_real_candidate_ultrastrict/replay.npz"}
    paths["accepted_selection"] = paths["parent"] if s["selected_is_parent"] else archive/"audits"/(s["selected"]["label"]+"_J46")/"J1_J46/glut_real_candidate_ultrastrict/replay.npz"
    time = np.array(obs["time"])
    post = time > 1
    training = time[post] <= 10
    maximum_budget_difference = 0.
    for case in c["full_evaluation"]:
        with np.load(paths[case["case"]]) as a:
            names = a["pool_names"].tolist()
            for pool, values in obs["values"].items():
                require(f["initial"][names.index(pool)] == values[0], "measured J1 changed")
                predicted = a["states"][names.index(pool), np.searchsorted(a["time"], time[post])]
                residuals = predicted-np.array(values)[post]
                recorded = case["all55_metrics"][pool]
                for key, use in (("training_RMSE_mM", training), ("late_RMSE_mM", ~training), ("all_postinitial_RMSE_mM", np.ones(len(residuals), bool))):
                    squared = [float(v)**2 for v in residuals[use]]
                    actual = math.sqrt(math.fsum(squared)/len(squared))
                    require(abs(actual-recorded[key]) < 1e-11, "pool RMSE:"+pool)
                require(recorded["endpoint_mM"] == predicted[-1] and recorded["nominal_endpoint_mM"] == values[-1], "endpoint:"+pool)
            def budget(pool, recorded, use):
                nonlocal maximum_budget_difference
                row = a["matrix"][names.index(pool)]
                values = row[:, None]*a["q8_executed_rates"][:, use]
                weights = a["q8_weights"][use]
                totals = {"production_mM": float(np.sum(weights*np.maximum(values, 0))),
                          "consumption_mM": float(-np.sum(weights*np.minimum(values, 0)))}
                totals["net_integrated_mM"] = float(np.sum(weights*values))
                for key, value in totals.items():
                    delta = abs(value-recorded[key])
                    maximum_budget_difference = max(maximum_budget_difference, delta)
                    require(delta < 1e-9, "independent signed budget:"+pool)
            for pool, recorded in case["executed_budgets"].items(): budget(pool, recorded, np.ones(len(a["q8_nodes"]), bool))
            for key, period in case["period_budgets"].items():
                lo, hi = [float(v[1:]) for v in key.split("_")]
                use = (a["q8_nodes"] > lo) & (a["q8_nodes"] < hi)
                for pool, recorded in period["pool_budgets"].items(): budget(pool, recorded, use)
    raw_gain = s["best_paired"]["training_score"]["negative_log_likelihood"]-s["best_split"]["training_score"]["negative_log_likelihood"]
    require(abs(raw_gain-c["raw_gain_vs_lowest_paired_fit_NLL"]) < 1e-10, "raw paired/split gain")
    require(c["all55_independent"] is False and c["physiological_validation"] is False, "evidence scope")
    return {"passed": True, "checks": count, "exact_source_cells": source_cells,
        "verifier_sha256": sha(Path(__file__)), "report_manifest_sha256": sha(report/"manifest.json"),
        "whole_source_rows": 110, "full_and_period_signed_budgets": 94,
        "maximum_budget_difference_mM": maximum_budget_difference,
        "late_data_used_in_selection": False, "physiological_validation": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True); p.add_argument("--report", type=Path, required=True)
    p.add_argument("--receipt", type=Path, required=True)
    a = p.parse_args()
    if a.receipt.exists(): raise ValueError("fresh receipt required")
    result = verify(a.archive.resolve(), a.report.resolve())
    write(a.receipt, result)
    print(json.dumps(result, indent=2))
