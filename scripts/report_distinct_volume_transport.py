"""Report every fixed case without choosing a donor pairing or kinetic winner."""

import argparse
import csv
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import openpyxl


def report(out):
    context = out / "fixed_context_v2"
    summary = json.loads((context / "summary.json").read_text())
    final = [r for r in summary["results"] if r["tolerance"] == "ultrastrict"]
    rows = []
    for r in final:
        rows.append({"case": r["case"], "hematocrit": r["hematocrit"], **r["endpoint"],
                     "VEGLC_integral_cell_mM": r["executed_transport_integrals_cell_mM"]["VEGLC"],
                     "VELAC_integral_cell_mM": r["executed_transport_integrals_cell_mM"]["VELAC"],
                     "minimum_checked_mM": r["minimum_checked_mM"], "numerical_pass": r["numerical_pass"]})
    with (out / "fixed_endpoints.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with (out / "source_preparation/phase_observations_pairing_sensitivity.csv").open(newline="", encoding="utf-8") as stream:
        paired = list(csv.DictReader(stream))
    bounds = []
    for r in paired:
        li, le = float(r["LAC_phase_mM"]), float(r["ELAC_phase_mM"])
        if li <= 0 or le <= 0:
            raise ValueError("positive lactate required for logarithmic directionality screen")
        bounds.append({"pairing_id": r["pairing_id"], "endo_key": r["endo_trajectory_key"],
                       "assay_key": r["assay_trajectory_key"], "source_day": float(r["source_day"]),
                       "LAC_source_cell": r["LAC_source_cell"], "ELAC_source_cell": r["ELAC_source_cell"],
                       "delta_pH_export_upper_bound": math.log10(li / le),
                       "interpretation": "positive_reduced_MCT_export_requires_pHi_minus_pHe_below_bound",
                       "measured_pH": False, "free_activity_mapping_verified": False})
    with (out / "conditional_mct_directionality_bounds.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(bounds[0]))
        writer.writeheader()
        writer.writerows(bounds)
    t0_bounds = [r["delta_pH_export_upper_bound"] for r in bounds if r["source_day"] == 0]
    fig, axes = plt.subplots(2, 3, figsize=(13, 7.5), constrained_layout=True)
    colors = {"D3": "#16836b", "D11": "#be6a30", "D19": "#bd3671"}
    root = Path(__file__).resolve().parents[1]
    wb = openpyxl.load_workbook(root / "src/Data_Bordbar_et_al_exp.xlsx", read_only=True, data_only=True)
    nominal_rows = list(wb["Sheet1"].values)
    wb.close()
    nominal = {r[0]: r[1:] for r in nominal_rows[1:]}
    source_days = np.array(nominal_rows[0][1:])
    for ax, pool in zip(axes.flat, ("ATP", "GLC", "EGLC", "LAC", "ELAC", "ADP")):
        for r in final:
            replay = np.load(context / (r["case"] + "_ultrastrict") / "replay.npz")
            names = list(replay["pool_names"])
            h = r["hematocrit"]
            color = "#353d40" if h is None else colors[r["case"].split("_")[-1]]
            ls = "--" if "glut_mct" in r["case"] else "-"
            label = "Common-coordinate control" if h is None else f"{'GLUT/MCT' if 'glut_mct' in r['case'] else 'Native'} H={h:.3f}"
            ax.plot(replay["time"], replay["states"][names.index(pool)], color=color, linestyle=ls, lw=1.6, label=label)
        mask = source_days <= 4
        ax.scatter(source_days[mask], np.array(nominal[pool])[mask], color="#326eaf", marker="x", s=32,
                   label="Nominal Sheet1; basis not source-verified", zorder=4)
        ax.set_title(pool, fontsize=12)
        ax.set_xlabel("Nominal model day", fontsize=9)
        ax.set_ylabel("mM; working phase basis", fontsize=9)
        ax.grid(alpha=.18)
    axes.flat[2].legend(fontsize=7, loc="best", frameon=False)
    fig.suptitle("Fixed-parameter J1-J4 diagnostic: distinct volumes and reversible carriers\nBorrowed Hct scenarios; pH clamped; not JBC prediction or biological calibration", fontsize=12)
    fig.savefig(out / "fixed_trajectories.png", dpi=170)
    plt.close(fig)
    controls = [r for r in final if "common_volume" in r["case"]]
    native = [r for r in final if r["case"].startswith("phase_native")]
    carriers = [r for r in final if r["case"].startswith("phase_glut_mct")]
    text = ["# Fixed-context results", "", "All comparisons use clamped pH and the same exact initial state; no fitting or source concentration rescaling.", "",
            f"Replays: {len(summary['results'])}. Numerical campaign pass: {summary['numerical_pass']}.",
            f"Pool/rate quadrature checks: {sum(r['quadrature_checks_passed'] for r in summary['results'])}/{sum(r['quadrature_checks_total'] for r in summary['results'])}.",
            f"Strict/ultrastrict checks: {sum(r['checks_passed'] for r in summary['convergence'])}/{sum(r['checks_total'] for r in summary['convergence'])}.",
            f"Minimum checked concentration: {min(r['minimum_checked_mM'] for r in summary['results']):.12g} mM.", "",
            f"Nominal ATP J4: common-coordinate clamped control {controls[0]['endpoint']['ATP']:.10g} mM; distinct-volume native range {min(r['endpoint']['ATP'] for r in native):.10g}-{max(r['endpoint']['ATP'] for r in native):.10g}; reversible-carrier range {min(r['endpoint']['ATP'] for r in carriers):.10g}-{max(r['endpoint']['ATP'] for r in carriers):.10g}.", "",
            "These values do not restore the nominal Sheet1 ATP endpoint (about1.079765 mM). No Hct or carrier law is promoted by endpoint loss. The pH-clamped diagnostic does not rule out supported pH-dependent or coupled redox mechanisms.", "",
            "At equal clamped pH the reversible law produces net lactate import in this frozen context, not the historical irreversible efflux. This is a gradient/pH diagnostic, not evidence that biological MCT is invalid. An explicit source-compatible pH gradient is necessary before promoting the lactate law.", "",
            f"Conditional directionality screen for all six Yurkovich pairings: positive reduced-MCT export requires pHi-pHe < log10(LAC/ELAC). At source day0 the bounds span {min(t0_bounds):.6g} to {max(t0_bounds):.6g}. These are not pH measurements or inferred physiological pH; they assume comparable accessible concentration coordinates and a single effective MCT export. See conditional_mct_directionality_bounds.csv.", "",
            "See fixed_endpoints.csv for every ATP/ADP/AMP/glucose/lactate endpoint and executed transport integral, and fixed_trajectories.png for the uninterrupted trajectories.", "",
            "Next: donor-linkage/source-basis evidence and a supported acid/base contract before free MCT-pH prediction, followed by a restricted identifiable redox/energy test. No immediate blind increase of optimizer budget is supported."]
    (out / "fixed_results.md").write_text("\n".join(text) + "\n", encoding="utf-8")
    return {"replays": len(summary["results"]), "numerical_pass": summary["numerical_pass"], "ATP_native_range": [min(r["endpoint"]["ATP"] for r in native), max(r["endpoint"]["ATP"] for r in native)],
            "ATP_carrier_range": [min(r["endpoint"]["ATP"] for r in carriers), max(r["endpoint"]["ATP"] for r in carriers)]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    print(json.dumps(report(parser.parse_args().out), indent=2))
