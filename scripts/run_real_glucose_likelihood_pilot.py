"""Prepare original Bordbar cells, then fit a reversible conditional GLUT pilot."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
CONFIG = ROOT / "config/fla_real_glucose_pilot.json"


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False)+"\n", encoding="utf-8")


def prepare(out):
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter
    if out.exists():
        raise ValueError("fresh experimental pilot directory required")
    design = json.loads(CONFIG.read_text())
    source = ROOT / design["workbook"]
    if sha(source) != design["source_sha256"]:
        raise ValueError("original concentration workbook changed")
    workbook = load_workbook(source, read_only=True, data_only=False)
    try:
        sheet = workbook[design["sheet"]]
        rows = list(sheet.iter_rows(values_only=True))
        time = list(rows[0][1:15])
        if time[0] != 1 or time[-1] != 46 or len(time) != 14:
            raise ValueError("original source time vector required")
        entries, j1, cells = {}, {}, []
        for index, row in enumerate(rows[1:], 2):
            if not isinstance(row[0], str) or not isinstance(row[1], (int, float)):
                continue
            j1[row[0]] = row[1]
            if row[0] in ("GLC", "EGLC", "LAC", "ELAC"):
                entries[row[0]] = list(row[1:15])
                for column, value in enumerate(row[1:15], 2):
                    cells.append({"pool": row[0], "day": time[column-2], "value": value,
                                  "source_cell": f"Sheet1!{get_column_letter(column)}{index}"})
        if len(j1) != 55 or set(entries) != {"GLC", "EGLC", "LAC", "ELAC"}:
            raise ValueError("exact55 initialization and four source channels required")
    finally:
        workbook.close()
    seed = json.loads((ROOT / design["seed_context"]).read_text())
    data = {"time": time, **entries, "source_cells": cells, "all55_exact_J1": j1,
            "kinetics": seed["kinetics"]["glucose"], "J1_preserved": True}
    protected = [CONFIG, Path(__file__), source, ROOT / design["seed_context"], ROOT / "src/fla_real_glucose_pilot.py",
        ROOT / "src/fla_profiled_observation_noise.py", ROOT / "src/rbc_distinct_volume_transport.py",
        ROOT / "src/equadiff_brodbar.py", ROOT / "qa/test_real_glucose_likelihood.py"]
    out.mkdir(parents=True)
    write(out / "execution_design.json", {"design": design, "input_sha256":
        {p.relative_to(ROOT).as_posix(): sha(p) for p in protected}, "source_uncertainty": "normalization_and_aggregation_lineage_unverified",
        "kinetic_candidate_changes_authorized_by_user": True})
    write(out / "source_observations.json", data)
    write(out / "source_seal.json", {"execution_design.json": sha(out / "execution_design.json"),
                                     "source_observations.json": sha(out / "source_observations.json")})
    return {"prepared": True, "source_values": len(cells), "exact_J1_values": len(j1), "kinetic_fits": 0}


def run(out):
    from scipy.optimize import minimize
    from fla_real_glucose_pilot import predict_glucose, training_score
    if (out / "manifest.json").exists():
        raise ValueError("do not overwrite fitted pilot")
    frozen = json.loads((out / "execution_design.json").read_text())
    design = frozen["design"]
    data = json.loads((out / "source_observations.json").read_text())
    for name, digest in json.loads((out / "source_seal.json").read_text()).items():
        if sha(out / name) != digest:
            raise ValueError("prepared original observations changed")
    fits = []
    for case in design["free_cases"]:
        names = ["effective_clearance"] + (["km_e"] if case.endswith("and_km_e") else [])
        bounds = [(np.log(design["bounds"][n][0]), np.log(design["bounds"][n][1])) for n in names]
        for start, vector in enumerate(design["starts"]):
            trace = []
            def unpack(x):
                values = np.exp(x)
                return values[0], values[1] if len(values) == 2 else data["kinetics"]["km_e"]
            def cost(x):
                clearance, km = unpack(x)
                result = predict_glucose(data, design, clearance, km)
                score = training_score(data, design, result)
                trace.append({"effective_clearance": float(clearance), "km_e": float(km), **score})
                return score["negative_log_likelihood"]
            solution = minimize(cost, np.log(vector[:len(names)]), method="L-BFGS-B", jac="3-point",
                                bounds=bounds, options=design["optimizer"])
            clearance, km = unpack(solution.x)
            strict = predict_glucose(data, design, clearance, km, profile="strict")
            ultra = predict_glucose(data, design, clearance, km)
            cross = predict_glucose(data, design, clearance, km, method="DOP853")
            prediction = ultra["predicted_EGLC"]
            observed = np.asarray(data["EGLC"])
            mask = np.asarray(data["time"]) > design["training_end_day"]
            numerical = bool(np.allclose(strict["predicted_EGLC"], prediction, atol=1e-6, rtol=1e-6)
                             and np.allclose(cross["predicted_EGLC"], prediction, atol=1e-6, rtol=1e-6))
            fit = {"case": case, "start_index": start, "parameters": {"effective_clearance": float(clearance), "km_e": float(km)},
                "optimizer_success": bool(solution.success), "optimizer_message": str(solution.message),
                "objective_calls": len(trace), "training_dispersion": training_score(data, design, ultra), "trace": trace,
                "holdout_RMSE_mM": float(np.sqrt(np.mean((prediction[mask]-observed[mask])**2))),
                "holdout_relative_RMSE": float(np.sqrt(np.mean(((prediction[mask]-observed[mask])/observed[mask])**2))),
                "endpoint_predicted_mM": float(prediction[-1]), "endpoint_observed_mM": float(observed[-1]),
                "numerical_pass": numerical, "predictions": prediction.tolist(), "driver_at_samples": ultra["driver_at_samples"].tolist(),
                "conditional_geometry_candidates": [{"hematocrit": h, "GLUT_conductance_cell_basis": float(clearance*(1-h)/h),
                    "constructor_vmax_equivalent": float(clearance*(1-h)/h*km)} for h in design["hematocrit_conversion_scenarios"]],
                "full_RBC_validation": False, "physiological_activity_identified": False}
            np.savez_compressed(out / f"{case}_start{start}.npz", time=ultra["time"], predicted=prediction,
                                strict=strict["predicted_EGLC"], DOP853=cross["predicted_EGLC"], observed=observed)
            write(out / f"{case}_start{start}.json", fit)
            fits.append(fit)
            print(f"{case} start{start}: {fit['parameters']} NLL={fit['training_dispersion']['negative_log_likelihood']:.4f}", flush=True)
    chosen = [min([f for f in fits if f["case"] == c], key=lambda f: f["training_dispersion"]["negative_log_likelihood"])
              for c in design["free_cases"]]
    summary = {"experimental_conditional_fits": len(fits), "all_numerical_pass": all(f["numerical_pass"] for f in fits),
        "all_optimizer_success": all(f["optimizer_success"] for f in fits), "selected_by_training_only": chosen,
        "candidate_parameters_changed": True, "production_parameters_changed": False, "ATP_inference": False,
        "full_RBC_ODE_replays": 0, "source_data_rescaled": False, "heldout_GLC_used_as_input": False,
        "interpretation": "real_nominal_concentration_conditional_transport_pilot_not_whole_network_calibration"}
    write(out / "summary.json", summary)
    for name, digest in frozen["input_sha256"].items():
        if sha(ROOT / name) != digest:
            raise ValueError("experimental pilot input changed")
    write(out / "manifest.json", {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()})
    return {k: summary[k] for k in ("experimental_conditional_fits", "all_numerical_pass", "all_optimizer_success", "production_parameters_changed")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", type=Path)
    parser.add_argument("--run", type=Path)
    args = parser.parse_args()
    if bool(args.prepare) == bool(args.run):
        parser.error("choose --prepare or --run")
    print(json.dumps(prepare(args.prepare.resolve()) if args.prepare else run(args.run.resolve()), indent=2))
