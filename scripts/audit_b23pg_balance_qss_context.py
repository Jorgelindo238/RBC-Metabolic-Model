"""Audit the exact B23PG balance in revert and QSS-B13PG contexts."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
SCRIPT_DIR = ROOT / "scripts"
SCREEN_DIR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "b13pg_constrained_initialization_screen_J1_J10"
)
REFINEMENT_DIR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "v6pgd_constrained_transition_refinement_46d"
)
DEFAULT_OUT_DIR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "b23pg_balance_qss_b13pg_context_J1_J3"
)
BRODBAR_DATA = SRC_DIR / "Data_Bordbar_et_al_exp.xlsx"

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from equadiff_brodbar import BRODBAR_METABOLITE_MAP, MODEL_NETWORK_VERSION  # noqa: E402
from MM_calibration import load_initial_conditions  # noqa: E402
from profile_glycolysis_flux_bottlenecks import (  # noqa: E402
    _jsonable,
    _load_params,
    _simulate_and_track,
)
from audit_atp_transition_v6pgd_ppp_context import (  # noqa: E402
    CANDIDATE_LABEL,
    _candidate_params,
    _state_with_saved_latent,
)


REVERT_LABEL = "duplicated_data_revert"
QSS_LABEL = "qss_1.000x"
B23PG_TERMS = {"VDPGM": 1.0, "V23DPGP": -1.0}
WINDOWS = (
    ("J1_J1.1", 1.0, 1.1),
    ("J1.1_J1.3", 1.1, 1.3),
    ("J1.3_J1.6", 1.3, 1.6),
    ("J1.6_J2", 1.6, 2.0),
    ("J2_J3", 2.0, 3.0),
)
TRACKED_STATES = ("B13PG", "B23PG", "P3G", "P2G", "ATP")
STATE_INDICES = {
    name: int(BRODBAR_METABOLITE_MAP[name]) for name in TRACKED_STATES
}


def _integral(values: np.ndarray, time: np.ndarray) -> float:
    return float(np.trapezoid(np.asarray(values, dtype=float), np.asarray(time, dtype=float)))


def _raw_balance(fluxes: Mapping[str, np.ndarray]) -> np.ndarray:
    missing = [name for name in B23PG_TERMS if name not in fluxes]
    if missing:
        raise KeyError(f"FluxTracker is missing B23PG reactions: {missing}")
    return sum(
        coefficient * np.asarray(fluxes[name], dtype=float)
        for name, coefficient in B23PG_TERMS.items()
    )


def _teacher() -> tuple[np.ndarray, np.ndarray, PchipInterpolator]:
    frame = pd.read_excel(BRODBAR_DATA, engine="openpyxl")
    names = frame.iloc[:, 0].astype(str).str.strip().str.upper()
    row = frame.loc[names == "B23PG"].iloc[:, 1:]
    if len(row) != 1:
        raise RuntimeError(f"Expected one B23PG row, found {len(row)}")
    time = np.asarray([float(value) for value in frame.columns[1:]], dtype=float)
    values = row.iloc[0].to_numpy(dtype=float)
    return time, values, PchipInterpolator(time, values)


def _build_state_contract() -> tuple[dict[str, np.ndarray], dict[str, Any], Path]:
    refinement_summary = json.loads(
        (REFINEMENT_DIR / "summary.json").read_text(encoding="utf-8")
    )
    diagnostic_candidates = json.loads(
        (REFINEMENT_DIR / "diagnostic_candidates.json").read_text(encoding="utf-8")
    )
    initialization = json.loads(
        (SCREEN_DIR / "diagnostic_initializations.json").read_text(encoding="utf-8")
    )
    seed_path = Path(refinement_summary["seed_params_path"])
    params = _candidate_params(_load_params(seed_path))
    base = _state_with_saved_latent(
        np.asarray(load_initial_conditions(), dtype=float),
        diagnostic_candidates["candidates"][CANDIDATE_LABEL]["latent_initial_states"],
    )
    states: dict[str, np.ndarray] = {}
    for label in (REVERT_LABEL, QSS_LABEL):
        state = base.copy()
        values = initialization["candidates"][label]
        state[STATE_INDICES["B13PG"]] = float(values["B13PG"])
        state[STATE_INDICES["B23PG"]] = float(values["B23PG"])
        states[label] = state
    return states, params, seed_path


def _replay(
    *,
    label: str,
    state: np.ndarray,
    params: Mapping[str, Any],
    time: np.ndarray,
    teacher: PchipInterpolator,
    closure_tolerance: float,
    method: str,
    rtol: float,
    atol: float,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    sol, fluxes, derivatives = _simulate_and_track(
        params=params,
        t_eval=time,
        method=method,
        rtol=rtol,
        atol=atol,
        x0_override=state,
    )
    b23pg = np.asarray(sol.y[STATE_INDICES["B23PG"]], dtype=float)
    production = np.asarray(fluxes["VDPGM"], dtype=float)
    drainage = np.asarray(fluxes["V23DPGP"], dtype=float)
    net = _raw_balance(fluxes)
    derivative = np.asarray(derivatives[STATE_INDICES["B23PG"]], dtype=float)
    closure = float(np.max(np.abs(net - derivative)))
    if closure > float(closure_tolerance):
        raise RuntimeError(f"B23PG closure failed for {label}: {closure:.6g}")
    teacher_concentration = np.asarray(teacher(time), dtype=float)
    teacher_derivative = np.asarray(teacher.derivative()(time), dtype=float)
    required_production = teacher_derivative + drainage
    required_drainage = production - teacher_derivative
    frame = pd.DataFrame(
        {
            "candidate": label,
            "time_day": time,
            "B23PG": b23pg,
            "B23PG_teacher": teacher_concentration,
            "B23PG_teacher_derivative": teacher_derivative,
            "VDPGM": production,
            "V23DPGP": drainage,
            "B23PG_model_net": net,
            "B23PG_ode_derivative": derivative,
            "B23PG_closure_error": net - derivative,
            "teacher_required_VDPGM_given_model_V23DPGP": required_production,
            "teacher_required_V23DPGP_given_model_VDPGM": required_drainage,
            "VDPGM_supply_residual": production - required_production,
            "V23DPGP_drainage_residual": drainage - required_drainage,
        }
    )
    for name, index in STATE_INDICES.items():
        frame[name] = np.asarray(sol.y[index], dtype=float)
    teacher_change = float(teacher_concentration[-1] - teacher_concentration[0])
    model_change = float(b23pg[-1] - b23pg[0])
    production_integral = _integral(production, time)
    drainage_integral = _integral(drainage, time)
    required_production_integral = _integral(required_production, time)
    metrics = {
        "candidate": label,
        "B13PG_initial_mM": float(sol.y[STATE_INDICES["B13PG"], 0]),
        "B23PG_initial_mM": float(b23pg[0]),
        "B23PG_final_mM": float(b23pg[-1]),
        "B23PG_model_change_mM": model_change,
        "B23PG_teacher_change_mM": teacher_change,
        "VDPGM_integral_mM": production_integral,
        "V23DPGP_integral_mM": drainage_integral,
        "model_net_integral_mM": _integral(net, time),
        "teacher_net_integral_mM": _integral(teacher_derivative, time),
        "teacher_required_VDPGM_integral_mM": required_production_integral,
        "VDPGM_supply_fraction_of_teacher_requirement": production_integral
        / max(required_production_integral, 1e-30),
        "VDPGM_supply_deficit_mM": max(0.0, required_production_integral - production_integral),
        "max_B23PG_closure_error": closure,
    }
    return frame, metrics


def _window_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    all_time = frame["time_day"].to_numpy(dtype=float)
    for name, start, end in WINDOWS:
        mask = (all_time >= start - 1e-12) & (all_time <= end + 1e-12)
        local = frame.loc[mask]
        time = local["time_day"].to_numpy(dtype=float)
        rows.append(
            {
                "candidate": str(frame["candidate"].iloc[0]),
                "window": name,
                "VDPGM_integral_mM": _integral(local["VDPGM"], time),
                "V23DPGP_integral_mM": _integral(local["V23DPGP"], time),
                "model_net_integral_mM": _integral(local["B23PG_model_net"], time),
                "teacher_net_integral_mM": _integral(local["B23PG_teacher_derivative"], time),
                "required_VDPGM_integral_mM": _integral(
                    local["teacher_required_VDPGM_given_model_V23DPGP"], time
                ),
            }
        )
    return rows


def _plot(frames: Mapping[str, pd.DataFrame], out_path: Path) -> None:
    colors = {REVERT_LABEL: "#111827", QSS_LABEL: "#b45309"}
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    for label, frame in frames.items():
        time = frame["time_day"]
        color = colors[label]
        axes[0, 0].plot(time, frame["B23PG"], color=color, label=label)
        axes[0, 1].plot(time, frame["VDPGM"], color=color, label=f"{label}: VDPGM")
        axes[0, 1].plot(time, frame["V23DPGP"], color=color, linestyle=":", label=f"{label}: V23DPGP")
        axes[1, 0].plot(time, frame["B23PG_model_net"], color=color, label=label)
        axes[1, 1].plot(time, frame["VDPGM_supply_residual"], color=color, label=label)
    reference = frames[REVERT_LABEL]
    axes[0, 0].plot(reference["time_day"], reference["B23PG_teacher"], "k--", label="B23PG teacher")
    axes[1, 0].plot(reference["time_day"], reference["B23PG_teacher_derivative"], "k--", label="teacher derivative")
    axes[1, 1].axhline(0.0, color="#64748b", linewidth=1)
    axes[0, 0].set_title("B23PG concentration")
    axes[0, 1].set_title("Production and drainage")
    axes[1, 0].set_title("Model versus teacher net balance")
    axes[1, 1].set_title("VDPGM supply residual")
    for axis in axes.flat:
        axis.grid(alpha=0.25)
        axis.set_xlabel("Time (day)")
        axis.legend(frameon=False, fontsize=7)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def run_audit(
    *,
    out_dir: Path,
    timepoints: int,
    method: str,
    rtol: float,
    atol: float,
    closure_tolerance: float,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    states, params, seed_path = _build_state_contract()
    _, _, teacher = _teacher()
    time = np.linspace(1.0, 3.0, int(timepoints))
    frames: dict[str, pd.DataFrame] = {}
    metrics: dict[str, dict[str, Any]] = {}
    windows: list[dict[str, Any]] = []
    for label in (REVERT_LABEL, QSS_LABEL):
        print(f"[b23pg-audit] replaying {label}", flush=True)
        frame, row = _replay(
            label=label,
            state=states[label],
            params=params,
            time=time,
            teacher=teacher,
            closure_tolerance=closure_tolerance,
            method=method,
            rtol=rtol,
            atol=atol,
        )
        frames[label] = frame
        metrics[label] = row
        windows.extend(_window_rows(frame))
    revert = metrics[REVERT_LABEL]
    qss = metrics[QSS_LABEL]
    lost_supply = float(revert["VDPGM_integral_mM"]) - float(qss["VDPGM_integral_mM"])
    production_loss_fraction = lost_supply / max(float(revert["VDPGM_integral_mM"]), 1e-30)
    drainage_change = float(qss["V23DPGP_integral_mM"]) - float(revert["V23DPGP_integral_mM"])
    classification = (
        "VDPGM_supply_limited_by_B13PG_context"
        if production_loss_fraction > 0.5 and abs(drainage_change) < abs(lost_supply)
        else "mixed_production_and_drainage_defect"
    )
    pd.concat(frames.values(), ignore_index=True).to_csv(
        out_dir / "b23pg_timeseries.csv", index=False
    )
    pd.DataFrame(windows).to_csv(out_dir / "b23pg_window_balances.csv", index=False)
    _plot(frames, out_dir / "b23pg_balance_attribution.png")
    summary = {
        "contract_type": "fixed_kinetic_b23pg_balance_audit",
        "contract_version": 1,
        "model_network_version": MODEL_NETWORK_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "kinetic_optimization_performed": False,
        "parameters_promoted": False,
        "initial_conditions_promoted": False,
        "seed_params_path": str(seed_path),
        "fixed_kinetic_context": {"vmax_V6PGD": float(params["vmax_V6PGD"])},
        "balance_equation": "dB23PG/dt = VDPGM - V23DPGP",
        "candidate_metrics": metrics,
        "production_loss_revert_to_qss_mM": lost_supply,
        "production_loss_fraction": production_loss_fraction,
        "drainage_change_revert_to_qss_mM": drainage_change,
        "classification": classification,
        "decision": "do not open V23DPGP; first restore identifiable B13PG-to-VDPGM supply without reintroducing the duplicated B13PG stock",
        "next_step": "use the temporal and identifiability contracts to determine whether VDPGM kinetics or a coupled latent-state combination is observable in J1-J3",
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "report": str(out_dir / "decision_report.md"),
            "timeseries": str(out_dir / "b23pg_timeseries.csv"),
            "windows": str(out_dir / "b23pg_window_balances.csv"),
            "plot": str(out_dir / "b23pg_balance_attribution.png"),
        },
    }
    (out_dir / "summary.json").write_text(
        json.dumps(_jsonable(summary), indent=2), encoding="utf-8"
    )
    report = [
        "# J1-J3 B23PG balance audit",
        "",
        "No kinetic constant or initial state was optimized or promoted.",
        "",
        "## Exact balance",
        "",
        "`dB23PG/dt = VDPGM - V23DPGP` closed pointwise in both branches.",
        "",
        "## Attribution",
        "",
        f"- Revert VDPGM integral: `{revert['VDPGM_integral_mM']:.6g} mM`; QSS: `{qss['VDPGM_integral_mM']:.6g} mM`.",
        f"- Removing duplicated B13PG stock removes `{100.0 * production_loss_fraction:.2f}%` of J1-J3 VDPGM supply.",
        f"- V23DPGP integral changes by only `{drainage_change:.6g} mM` between contexts.",
        f"- QSS VDPGM supplies `{100.0 * qss['VDPGM_supply_fraction_of_teacher_requirement']:.2f}%` of the production required by the B23PG teacher given model drainage.",
        "",
        "## Decision",
        "",
        f"Classification: **`{classification}`**.",
        "",
        str(summary["decision"]),
    ]
    (out_dir / "decision_report.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"classification": classification, "summary": str(out_dir / "summary.json")}, indent=2))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--timepoints", type=int, default=401)
    parser.add_argument("--method", default="BDF")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    parser.add_argument("--closure-tolerance", type=float, default=1e-12)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_audit(
        out_dir=args.out_dir,
        timepoints=args.timepoints,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
        closure_tolerance=args.closure_tolerance,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
