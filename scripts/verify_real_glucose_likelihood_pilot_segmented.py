"""Reopen original cells, replay learned conditional kinetics and check flux budgets."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from openpyxl import load_workbook
from openpyxl.utils.cell import coordinate_to_tuple

from run_real_glucose_likelihood_pilot_segmented import ROOT, sha, write
sys.path.insert(0, str(ROOT / "src"))
from fla_real_glucose_pilot_segmented import predict_glucose, training_score, glucose_driver
from rbc_distinct_volume_transport import glut_import


def verify(archive, out):
    if out.exists():
        raise ValueError("fresh real-pilot verification directory required")
    frozen = json.loads((archive / "execution_design.json").read_text())
    design = frozen["design"]
    for name, digest in frozen["input_sha256"].items():
        if sha(ROOT / name) != digest:
            raise ValueError("protected source/kinetics changed: "+name)
    for name, digest in json.loads((archive / "manifest.json").read_text()).items():
        if sha(archive / name) != digest:
            raise ValueError("fitted pilot output changed: "+name)
    data = json.loads((archive / "source_observations.json").read_text())
    workbook = load_workbook(ROOT / design["workbook"], read_only=True, data_only=False)
    try:
        source = list(workbook[design["sheet"]].iter_rows(values_only=True))
        j1 = {row[0]: row[1] for row in source[1:] if isinstance(row[0], str) and isinstance(row[1], (int, float))}
        if j1 != data["all55_exact_J1"]:
            raise ValueError("original55 J1 coordinates changed")
        for row in data["source_cells"]:
            r, c = coordinate_to_tuple(row["source_cell"].split("!")[1])
            if source[r-1][c-1] != row["value"]:
                raise ValueError("source cell reconstruction failed")
    finally:
        workbook.close()
    reports = []
    for file in sorted(archive.glob("*_start*.json")):
        fit = json.loads(file.read_text())
        p = fit["parameters"]
        r = predict_glucose(data, design, p["effective_clearance"], p["km_e"], method="DOP853")
        score = training_score(data, design, r)
        if (not np.allclose(r["predicted_EGLC"], fit["predictions"], atol=1e-6, rtol=1e-6)
                or not np.isclose(score["negative_log_likelihood"], fit["training_dispersion"]["negative_log_likelihood"], atol=1e-4, rtol=1e-5)):
            raise ValueError("candidate prediction/likelihood replay failed")
        nodes, weights = np.polynomial.legendre.leggauss(8)
        driver = glucose_driver(data["time"], data["GLC"], design["training_end_day"])
        integral = 0.0
        sol = r["solution"]
        for left, right in zip(sol.t[:-1], sol.t[1:]):
            times = .5*(left+right)+.5*(right-left)*nodes
            values = [glut_import(driver(t), float(sol.sol(t)[0]), conductance=p["effective_clearance"],
                                 km_i=data["kinetics"]["km_i"], km_e=p["km_e"]) for t in times]
            integral += .5*(right-left)*float(np.dot(weights, values))
        depletion = data["EGLC"][0]-r["predicted_EGLC"][-1]
        if not np.isclose(integral, depletion, atol=1e-6, rtol=1e-6):
            raise ValueError("conditional extracellular flux/extent budget failed")
        reports.append({"fit": file.name, "source_and_replay_verified": True,
                        "extracellular_depletion_integral_mM": integral, "ODE_depletion_mM": float(depletion),
                        "crosscheck_NLL": score["negative_log_likelihood"]})
    if len(reports) != 6:
        raise ValueError("all six experimental conditional fits required")
    out.mkdir(parents=True)
    report = {"verified": True, "source_values": len(data["source_cells"]), "exact_J1_values": len(j1), "fits": reports,
        "all_source_and_flux_checks_pass": True, "full_RBC_validation": False,
        "input_sha256": {p.relative_to(ROOT).as_posix(): sha(p) for p in [Path(__file__), *archive.iterdir()] if p.is_file()}}
    write(out / "verification.json", report)
    return {"verified": True, "source_values": len(data["source_cells"]), "exact_J1_values": len(j1),
            "conditional_fits_replayed": len(reports), "full_RBC_validation": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(verify(args.archive.resolve(), args.out.resolve()), indent=2))
