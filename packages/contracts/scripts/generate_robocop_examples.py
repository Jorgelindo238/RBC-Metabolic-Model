"""Generate canonical example payloads for the custom-data-plan and
calibration-triage contracts.

Running this script writes two files under ``config/generated/``:

* ``custom_data_plan.example.json`` — the planner's output for a realistic
  measured-metabolite list with a dangerous compensator selected.
* ``calibration_triage.example.json`` — the triage verdict for a synthetic
  calibration report that matches the same measured list.

The files are regenerated in place and must stay byte-identical to the
planner/triage module output; any drift is a contract change.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.robocop.custom_dataset_planner import build_custom_data_plan  # noqa: E402
from services.robocop.curve_triage import triage_calibration_report  # noqa: E402
from services.robocop.pure_ode_triage import triage_pure_ode_trajectories  # noqa: E402

EXAMPLES = ROOT / "config" / "generated"
EXAMPLES.mkdir(parents=True, exist_ok=True)


def _build_plan_example() -> dict:
    plan = build_custom_data_plan(
        measured_metabolites=[
            "EGLC", "GLC", "ELAC", "LAC", "PYR",
            "ATP", "ADP", "AMP",
            "B23PG", "GSH", "GSSG",
            "G6P", "F6P", "PEP",
        ],
        selected_params=[
            "vmax_VHK",
            "vmax_VPFK",
            "vmax_VPK",
            "vmax_VEGLC",
            "vmax_VELAC",
            "vmax_VPEP_PASE",
        ],
        requested_strategy=None,
    )
    return plan.to_dict()


def _build_triage_example() -> dict:
    report = {
        "baseline_loss": 1.85,
        "final_loss": 0.62,
        "improvement_pct": 66.5,
        "per_metabolite": [
            {"name": "EGLC", "nrmse": 0.18, "rmse": 0.82, "sim_final": 3.1, "exp_final": 3.3, "norm_factor": 4.5},
            {"name": "GLC", "nrmse": 0.22, "rmse": 0.05, "sim_final": 0.24, "exp_final": 0.28, "norm_factor": 0.22},
            {"name": "ELAC", "nrmse": 0.15, "rmse": 0.32, "sim_final": 2.1, "exp_final": 2.0, "norm_factor": 2.1},
            {"name": "LAC", "nrmse": 0.19, "rmse": 0.17, "sim_final": 0.88, "exp_final": 0.95, "norm_factor": 0.9},
            {"name": "PYR", "nrmse": 0.31, "rmse": 0.04, "sim_final": 0.12, "exp_final": 0.15, "norm_factor": 0.13},
            {"name": "ATP", "nrmse": 0.21, "rmse": 0.3, "sim_final": 1.35, "exp_final": 1.4, "norm_factor": 1.4},
            {"name": "ADP", "nrmse": 0.24, "rmse": 0.04, "sim_final": 0.16, "exp_final": 0.2, "norm_factor": 0.18},
            {"name": "AMP", "nrmse": 0.32, "rmse": 0.01, "sim_final": 0.04, "exp_final": 0.06, "norm_factor": 0.05},
            {"name": "B23PG", "nrmse": 0.29, "rmse": 1.2, "sim_final": 3.9, "exp_final": 4.2, "norm_factor": 4.1},
            {"name": "GSH", "nrmse": 0.17, "rmse": 0.13, "sim_final": 2.05, "exp_final": 2.1, "norm_factor": 2.1},
            {"name": "GSSG", "nrmse": 0.2, "rmse": 0.005, "sim_final": 0.03, "exp_final": 0.035, "norm_factor": 0.035},
            {"name": "G6P", "nrmse": 0.26, "rmse": 0.02, "sim_final": 0.08, "exp_final": 0.1, "norm_factor": 0.09},
            {"name": "F6P", "nrmse": 0.41, "rmse": 0.008, "sim_final": 0.02, "exp_final": 0.03, "norm_factor": 0.022},
            {"name": "PEP", "nrmse": 0.38, "rmse": 0.003, "sim_final": 0.008, "exp_final": 0.012, "norm_factor": 0.01},
        ],
    }
    verdict = triage_calibration_report(
        report,
        measured_metabolites=[
            "EGLC", "GLC", "ELAC", "LAC", "PYR",
            "ATP", "ADP", "AMP",
            "B23PG", "GSH", "GSSG",
            "G6P", "F6P", "PEP",
        ],
        optimized_params=[
            "vmax_VHK",
            "vmax_VPFK",
            "vmax_VPK",
            "vmax_VEGLC",
            "vmax_VELAC",
            "vmax_VPEP_PASE",
        ],
    )
    return verdict.to_dict()


def _build_pure_ode_triage_example() -> dict:
    times = [0.0, 8.4, 16.8, 25.2, 33.6, 42.0]
    trajectories = {
        "ATP":   [1.60, 1.58, 1.55, 1.50, 1.45, 1.40],
        "ADP":   [0.20, 0.19, 0.18, 0.17, 0.16, 0.15],
        "AMP":   [0.09, 0.085, 0.08, 0.075, 0.072, 0.070],
        "IMP":   [0.05, 0.048, 0.045, 0.042, 0.040, 0.038],
        "EGLC":  [5.0, 4.7, 4.3, 3.8, 3.3, 2.8],
        "ELAC":  [0.10, 0.35, 0.70, 1.05, 1.40, 1.75],
        "LAC":   [1.0, 1.2, 1.4, 1.6, 1.8, 2.0],
        "PYR":   [0.05, 0.06, 0.07, 0.065, 0.06, 0.055],
        "PEP":   [0.01, 0.012, 0.013, 0.012, 0.011, 0.010],
        "B23PG": [4.8, 4.7, 4.6, 4.5, 4.4, 4.3],
        "GSH":   [2.1, 2.05, 2.0, 1.95, 1.9, 1.85],
        "GSSG":  [0.03, 0.032, 0.035, 0.038, 0.04, 0.042],
    }
    verdict = triage_pure_ode_trajectories(times, trajectories)
    return verdict.to_dict()


def _dump(path: Path, payload: dict) -> None:
    serialised = json.dumps(payload, indent=2, sort_keys=False)
    path.write_text(serialised + "\n", encoding="utf-8")


def main() -> None:
    _dump(EXAMPLES / "custom_data_plan.example.json", _build_plan_example())
    _dump(EXAMPLES / "calibration_triage.example.json", _build_triage_example())
    _dump(EXAMPLES / "pure_ode_triage.example.json", _build_pure_ode_triage_example())
    print("wrote custom_data_plan.example.json")
    print("wrote calibration_triage.example.json")
    print("wrote pure_ode_triage.example.json")


if __name__ == "__main__":
    main()
