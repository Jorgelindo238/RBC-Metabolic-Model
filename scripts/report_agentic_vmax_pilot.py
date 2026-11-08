"""Extract candidate capacities and executed energy budgets without refitting."""

import argparse
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

from run_agentic_vmax_pilot import ROOT, STRUCTURE, parameters_for, read, require, seal, sha, verify_inputs, verify_manifest, write, write_csv


def signed_budget(path):
    with np.load(path) as a:
        names, reactions = a["pool_names"].tolist(), a["reactions"].tolist()
        ai, di = names.index("ATP"), names.index("ADP")
        matrix = a["matrix"]
        cells = a["q8_intervals"]
        early = cells < 14
        cells, w, v = cells[early], a["q8_weights"][early], a["q8_executed_rates"][:, early]
        result = {}
        for label, lo, hi in (("J1_J4", 0, 3), ("J4_J8", 3, 7), ("J8_J15", 7, 14), ("J1_J15", 0, 14)):
            use = (cells >= lo) & (cells < hi)
            atp = matrix[ai, :, None]*v[:, use]
            h = (matrix[ai]+.5*matrix[di])[:, None]*v[:, use]
            result[label] = {"ATP_production_mM": float(np.maximum(atp, 0.).sum(axis=0)@w[use]),
                             "ATP_consumption_mM": float(-np.minimum(atp, 0.).sum(axis=0)@w[use]),
                             "ATP_signed_by_reaction_mM": dict(zip(reactions, (atp@w[use]).tolist())),
                             "H_signed_by_reaction_mM": dict(zip(reactions, (h@w[use]).tolist()))}
        return result


def report(archive, out):
    require(not out.exists() and not out.is_relative_to(archive), "fresh external decision report required")
    verify_manifest(archive)
    f, obs = verify_inputs(archive), read(archive/"observations.json")
    validation = read(archive/"validation_summary.json")["networks"]
    parent = ROOT/f["design"]["parent_archive"]/"J1_J46/glut_real_candidate_ultrastrict/replay.npz"
    budgets = {"reference": signed_budget(parent)}
    results, rows, vectors = {}, [], {}
    pools = list(obs["values"])
    for mode in STRUCTURE:
        s = read(archive/"search"/mode/"result.json")
        audit = validation[mode]
        vectors[mode] = s["finalist"]["log_factors"]
        results[mode] = {"attempts": s["actual_evaluations"], "invalid": s["failed_evaluations"], "cache_hits": s["cache_hits"],
                         "fit_eligible_count": s["sufficient_gain_guard_eligible_count"], "all_valid_Pareto_points": len(s["all_valid_pareto"]),
                         "J15_admitted": audit["J15_admitted"], "numerical_pass": audit["numerical_pass"], "candidates": {}}
        for tag in ("finalist", "most_adenylate_improvement"):
            item = s[tag]
            p = parameters_for(f, item["log_factors"])
            values = item["callback_result"]["metrics"]["prediction_mM"]
            row = {"evaluation_id": item["evaluation_id"], "relative_adenylate_error": item["adenylate_loss"],
                   "relative_other_error": item["other_loss"], "guard_excess": item["max_guard_excess"],
                   "fit_J4_adenylates_mM": {k: values[pools.index(k)][0] for k in ("ATP", "ADP", "AMP")},
                   "fit_off_target_failures": item["callback_result"]["off_target_failures"],
                   "original_J15_replayed": tag == "finalist"}
            results[mode]["candidates"][tag] = row
            for k in f["resolved_capacities"]:
                rows.append([mode, tag, item["evaluation_id"], k, f["parameters"][k], p[k], p[k]/f["parameters"][k], False])
        budgets[mode] = signed_budget(archive/"audits"/mode/"ultrastrict/replay.npz")
        for period, z in audit["profiles"]["ultrastrict"]["periods"].items():
            m = z["metrics"]["prediction_mM"]
            results[mode][period] = {"relative_adenylate_gain": z["relative_adenylate_gain"],
                                     "other_loss_relative_to_reference": z["other_loss"], "off_target_failures": z["off_target_failures"],
                                     "adenylate_point_failures": z["adenylate_point_failures"],
                                     "ATP_ADP_AMP_mM": {k: m[pools.index(k)] for k in ("ATP", "ADP", "AMP")}}
    out.mkdir(parents=True)
    write(out/"decision.json", {"networks": results, "same_finalist_Vmax_vectors": vectors["native"] == vectors["gem_corrected"],
          "archive_manifest_sha256": sha(archive/"manifest.json"), "no_defaults_changed": True, "global_optimality": False})
    write(out/"executed_ATP_H_budgets.json", budgets)
    write_csv(out/"diagnostic_Vmax.csv", ["network", "role", "evaluation_id", "parameter", "reference_Vmax", "tested_Vmax", "factor", "production_promoted"], rows)
    seal(out)
    return {"reported_Vmax_rows": len(rows), "same_finalist_Vmax_vectors": vectors["native"] == vectors["gem_corrected"]}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    with threadpool_limits(1):
        print(report(args.archive.resolve(), args.out.resolve()))
