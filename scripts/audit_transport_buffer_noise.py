"""Scalar-integrator and arithmetic cross-check for all saved noisy fits."""

import argparse
import json
from pathlib import Path

import numpy as np

from audit_transport_buffer_clean_recovery import digest, scalar_prediction, ROOT


def audit(archive, out):
    if out.exists():
        raise ValueError("new noise validation directory required")
    config = json.loads((ROOT / "output/transport_buffer_synthetic_preparation_2026_10_06/preregistered_design.json").read_text())["design"]
    cases = []
    for file in sorted(archive.glob("*_start*.json")):
        fit = json.loads(file.read_text())
        scenario = next(s for s in config["scenarios"] if s["name"] == fit["scenario"])
        with np.load(archive / fit["prediction_file"]) as a:
            predicted = scalar_prediction(config, scenario, fit["parameters"], a["time"])
            stored = a["ultrastrict_states"]
            check = bool(np.all(np.abs(predicted-stored) <= config["numerical_atol"]+config["numerical_rtol"]*np.abs(stored)))
            for name, value in fit["parameters"].items():
                truth = scenario["initial"][2] if name == "phi0" else config["truth"][name]
                error = abs(value-truth) if name == "phi0" else abs(value-truth)/truth
                if not np.isclose(error, fit["parameter_errors"][name], atol=1e-14, rtol=1e-10):
                    raise ValueError("parameter-error arithmetic disagrees")
            mask = a["time"] > config["training_end_day"]
            s = config["sensitivity_scaling"]
            scale = np.array([s["concentration_mM"]]*2+[s["pH_units"]]*2)
            delta = (stored[:4, mask]-a["reference_states"][:4, mask])/scale[:, None]
            rmse = float(np.sqrt(np.sum(delta**2)/delta.size))
            if not np.isclose(rmse, fit["holdout_scaled_RMSE_all_states"], atol=1e-15, rtol=1e-12):
                raise ValueError("holdout arithmetic disagrees")
            cases.append({"fit_file": file.name, "scalar_DOP853_pass": check,
                          "max_abs_state_difference": float(np.max(np.abs(predicted-stored))),
                          "parameter_and_holdout_arithmetic_pass": True})
    if len(cases) != 216 or not all(c["scalar_DOP853_pass"] for c in cases):
        raise ValueError("scalar verification failed or incomplete")
    report = {"fits_cross_checked": len(cases), "scalar_integrations": len(cases), "all_pass": True,
        "max_abs_state_difference": max(c["max_abs_state_difference"] for c in cases), "cases": cases,
        "scope": "independent_scalar_rate_and_integrator_not_independent_biological_validation",
        "input_sha256": {str(p.relative_to(ROOT)).replace("\\", "/"): digest(p)
                         for p in [Path(__file__), Path(__file__).with_name("audit_transport_buffer_clean_recovery.py"),
                                   *sorted(archive.iterdir())] if p.is_file()}}
    out.mkdir(parents=True)
    (out / "scalar_crosscheck.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    return {k: report[k] for k in ("fits_cross_checked", "scalar_integrations", "all_pass", "max_abs_state_difference")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.archive.resolve(), args.out.resolve()), indent=2))
