"""Cross-check saved clean fits with an independently coded scalar extent ODE."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def scalar_prediction(config, scenario, parameters, time):
    p = {**config["truth"], **{k: v for k, v in parameters.items() if k != "phi0"}}
    initial = np.array(scenario["initial"], dtype=float)
    initial[2] = parameters.get("phi0", initial[2])
    ratio = config["geometry"]["hematocrit"] / (1-config["geometry"]["hematocrit"])

    # Conservation reduces the five-state system to one reaction extent.
    def rate(t, state):
        z = state[0]
        li, le = p["access_i"]*(initial[0]-z), p["access_e"]*(initial[1]+ratio*z)
        phi, phe = initial[2]+z/p["beta_i"], initial[3]-ratio*z/p["beta_e"]
        drive = li*10**(p["ph_reference"]-phi)-le*10**(p["ph_reference"]-phe)
        return [p["conductance"]*drive/(1+li/p["km_i"]+le/p["km_e"])]

    sol = solve_ivp(rate, config["horizon_day"], [0.0], method="DOP853", rtol=1e-11, atol=1e-13, dense_output=True)
    if not sol.success or sol.t[-1] != config["horizon_day"][-1]:
        raise ValueError("scalar cross-check integration incomplete")
    z = sol.sol(time)[0]
    return np.vstack([initial[0]-z, initial[1]+ratio*z, initial[2]+z/p["beta_i"],
                      initial[3]-ratio*z/p["beta_e"], z])


def audit(archive, out):
    if out.exists():
        raise ValueError("use a fresh cross-check directory")
    config = json.loads((ROOT / "output/transport_buffer_synthetic_preparation_2026_10_06/preregistered_design.json").read_text())["design"]
    cases = []
    for path in sorted(archive.glob("*_start*.json")):
        fit = json.loads(path.read_text())
        scenario = next(s for s in config["scenarios"] if s["name"] == fit["scenario"])
        with np.load(archive / fit["prediction_file"]) as a:
            predicted = scalar_prediction(config, scenario, fit["parameters"], a["time"])
            stored = a["ultrastrict_states"]
            numerical = bool(np.all(np.abs(predicted-stored) <= config["numerical_atol"] + config["numerical_rtol"]*np.abs(stored)))
            errors = {}
            for name, value in fit["parameters"].items():
                expected = scenario["initial"][2] if name == "phi0" else config["truth"][name]
                errors[name] = abs(value-expected) if name == "phi0" else abs(value-expected)/expected
            if not all(np.isclose(errors[n], fit["parameter_errors"][n], atol=1e-14, rtol=1e-10) for n in errors):
                raise ValueError("independent parameter-error arithmetic disagrees")
            holdout = a["time"] > config["training_end_day"]
            s = config["sensitivity_scaling"]
            scaling = np.array([s["concentration_mM"]]*2+[s["pH_units"]]*2)
            delta = (stored[:4, holdout]-a["reference_states"][:4, holdout])/scaling[:, None]
            rmse = float(np.sqrt(np.sum(delta**2)/delta.size))
            if not np.isclose(rmse, fit["holdout_scaled_RMSE_all_states"], rtol=1e-12, atol=1e-15):
                raise ValueError("independent holdout arithmetic disagrees")
            cases.append({"fit_file": path.name, "scalar_DOP853_vs_five_state_BDF_pass": numerical,
                          "max_abs_state_difference": float(np.max(np.abs(predicted-stored))),
                          "max_abs_state_difference_by_coordinate": np.max(np.abs(predicted-stored), axis=1).tolist(),
                          "parameter_arithmetic_verified": True, "holdout_arithmetic_verified": True})
    if len(cases) != 72 or not all(c["scalar_DOP853_vs_five_state_BDF_pass"] for c in cases):
        raise ValueError("incomplete or failed scalar cross-check")
    report = {"fits_cross_checked": len(cases), "scalar_integrations": len(cases), "all_pass": True,
              "max_abs_state_difference": max(c["max_abs_state_difference"] for c in cases), "cases": cases,
              "scope": "independent_scalar_rate_and_integrator_not_independent_biological_validation",
              "input_sha256": {str(p.relative_to(ROOT)).replace("\\", "/"): digest(p)
                               for p in [Path(__file__), *sorted(archive.iterdir())] if p.is_file()}}
    out.mkdir(parents=True)
    (out / "scalar_crosscheck.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    return {k: report[k] for k in ("fits_cross_checked", "scalar_integrations", "all_pass", "max_abs_state_difference")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.archive.resolve(), args.out.resolve()), indent=2))
