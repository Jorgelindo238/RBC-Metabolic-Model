"""Audit VADSS saturation and fixed-state shape levers after VAMPD1 decay.

This diagnostic uses the already computed full-ODE trajectory. It does not
rerun the ODE or optimize parameters. Experimental IMP endpoints define the
primary integrated VADSS teacher on three predeclared storage windows.
"""

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


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
DEFAULT_SOURCE = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "vampd1_storage_decay_full_ode_J1_J46"
    / "J1_J46_timeseries.csv"
)
DEFAULT_ANCHOR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "vmax_vampd1_vaprt_zero_screen_J1_J46"
    / "summary.json"
)
DEFAULT_OUT_DIR = ROOT / "output" / "vadss_saturation_vampd1_decay"
SOURCE_LABEL = "VAMPD1_storage_decay"
WINDOWS = ((1.0, 11.0), (11.0, 22.0), (22.0, 46.0))
LEGACY_KM = {"IMP": 0.231, "ASP": 0.200958, "GTP": 0.5}
VMAX_SCALE_GRID = tuple(np.geomspace(0.2, 1.2, 33))
KM_SCALE_GRID = tuple(np.geomspace(0.02, 2.0, 41))
for path in (str(SRC), str(SCRIPTS)):
    if path not in sys.path:
        sys.path.insert(0, path)

from evaluate_brodbar_candidate_full_panel import _load_brodbar_panel  # noqa: E402
from fla_integrated_flux import (  # noqa: E402
    IntegratedFluxTarget,
    build_integrated_flux_targets,
    integrated_flux_nrmse,
)
from screen_amp_nucleotidase_fixed_purine import _build_anchor  # noqa: E402


def michaelis_fraction(values: Sequence[float], km: float) -> np.ndarray:
    values_array = np.asarray(values, dtype=float)
    if km <= 0.0 or np.any(values_array < 0.0):
        raise ValueError("Michaelis inputs must be nonnegative and km must be positive")
    return values_array / (float(km) + values_array)


def reweighted_vadss_flux(
    *,
    imp: Sequence[float],
    asp: Sequence[float],
    gtp: Sequence[float],
    vmax: float,
    km_imp: float,
    km_asp: float,
    km_gtp: float,
) -> np.ndarray:
    if vmax < 0.0:
        raise ValueError("vmax must be nonnegative")
    return (
        float(vmax)
        * michaelis_fraction(imp, km_imp)
        * michaelis_fraction(asp, km_asp)
        * michaelis_fraction(gtp, km_gtp)
    )


def _window_integrals(time: np.ndarray, rate: np.ndarray) -> np.ndarray:
    result = []
    for start, end in WINDOWS:
        mask = (time >= start - 1e-10) & (time <= end + 1e-10)
        result.append(float(np.trapezoid(rate[mask], time[mask])))
    return np.asarray(result, dtype=float)


def _sensitivity_diagnostics(
    *,
    time: np.ndarray,
    imp: np.ndarray,
    asp: np.ndarray,
    gtp: np.ndarray,
    vmax: float,
    substrate: str,
    km: float,
) -> dict[str, Any]:
    epsilon = 1e-4

    def outputs(local_vmax: float, local_km: float) -> np.ndarray:
        kms = dict(LEGACY_KM)
        kms[substrate] = local_km
        return _window_integrals(
            time,
            reweighted_vadss_flux(
                imp=imp,
                asp=asp,
                gtp=gtp,
                vmax=local_vmax,
                km_imp=kms["IMP"],
                km_asp=kms["ASP"],
                km_gtp=kms["GTP"],
            ),
        )

    base = outputs(vmax, km)
    jacobian = np.column_stack(
        [
            (outputs(vmax * np.exp(epsilon), km) - outputs(vmax * np.exp(-epsilon), km))
            / (2.0 * epsilon),
            (outputs(vmax, km * np.exp(epsilon)) - outputs(vmax, km * np.exp(-epsilon)))
            / (2.0 * epsilon),
        ]
    )
    normalized = jacobian / np.maximum(np.abs(base), 0.05)[:, None]
    singular_values = np.linalg.svd(normalized, compute_uv=False)
    rank = int(np.sum(singular_values > singular_values[0] * 1e-8))
    condition = float(singular_values[0] / singular_values[-1])
    return {
        "parameterization": f"log(vmax_VADSS), log(km_{substrate}_VADSS)",
        "window_integral_jacobian": normalized.tolist(),
        "singular_values": singular_values.tolist(),
        "rank": rank,
        "condition_number": condition,
        "identifiable": bool(rank == 2 and condition < 100.0),
    }


def build_joint_vadss_targets(
    frame: pd.DataFrame,
    exp_time: np.ndarray,
    curves: Mapping[str, np.ndarray],
    candidate_rate: np.ndarray,
) -> tuple:
    total_curve = sum(
        np.asarray(curves[name], dtype=float) for name in ("ATP", "ADP", "AMP")
    )
    total_known_rate = (
        frame["VAK2"].to_numpy(dtype=float)
        - frame["VSAM"].to_numpy(dtype=float)
        + frame["VADSL"].to_numpy(dtype=float)
        + frame["VAPRT"].to_numpy(dtype=float)
    )
    vampd1_targets = build_integrated_flux_targets(
        measurement_time=exp_time,
        measurement_values=total_curve,
        dense_time=frame["time_day"].to_numpy(dtype=float),
        known_rate=total_known_rate,
        model_unknown_rate=frame["VAMPD1"].to_numpy(dtype=float),
        unknown_stoichiometric_coefficient=-1.0,
        windows=WINDOWS,
    )
    imp_other_rate = (
        frame["VHGPRT1"].to_numpy(dtype=float)
        - frame["VIMPH"].to_numpy(dtype=float)
        - frame["Vnucleo2"].to_numpy(dtype=float)
    )
    time = frame["time_day"].to_numpy(dtype=float)
    imp_values = np.asarray(curves["IMP"], dtype=float)
    result = []
    for vampd1_target, (start, end) in zip(vampd1_targets, WINDOWS):
        start_index = np.flatnonzero(np.isclose(exp_time, start, rtol=0.0, atol=1e-10))
        end_index = np.flatnonzero(np.isclose(exp_time, end, rtol=0.0, atol=1e-10))
        if start_index.size != 1 or end_index.size != 1:
            raise ValueError("VADSS window boundaries must be directly measured")
        observed_change = float(imp_values[end_index[0]] - imp_values[start_index[0]])
        mask = (time >= start - 1e-10) & (time <= end + 1e-10)
        known_integral = float(np.trapezoid(imp_other_rate[mask], time[mask]))
        known_integral += float(vampd1_target.required_unknown_flux_integral_mM)
        model_integral = float(np.trapezoid(candidate_rate[mask], time[mask]))
        required = known_integral - observed_change
        result.append(
            IntegratedFluxTarget(
                start_day=start,
                end_day=end,
                observed_state_change_mM=observed_change,
                known_flux_integral_mM=known_integral,
                required_unknown_flux_integral_mM=required,
                model_unknown_flux_integral_mM=model_integral,
                residual_mM=model_integral - required,
            )
        )
    return tuple(result)


def _map_family(
    *,
    frame: pd.DataFrame,
    exp_time: np.ndarray,
    curves: Mapping[str, np.ndarray],
    base_vmax: float,
    substrate: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    states = {
        name: frame[name].to_numpy(dtype=float) for name in ("IMP", "ASP", "GTP")
    }
    rows: list[dict[str, Any]] = []
    for vmax_scale in VMAX_SCALE_GRID:
        for km_scale in KM_SCALE_GRID:
            kms = dict(LEGACY_KM)
            kms[substrate] *= float(km_scale)
            flux = reweighted_vadss_flux(
                imp=states["IMP"],
                asp=states["ASP"],
                gtp=states["GTP"],
                vmax=base_vmax * float(vmax_scale),
                km_imp=kms["IMP"],
                km_asp=kms["ASP"],
                km_gtp=kms["GTP"],
            )
            targets = build_joint_vadss_targets(frame, exp_time, curves, flux)
            rows.append(
                {
                    "substrate": substrate,
                    "vmax_scale": float(vmax_scale),
                    "vmax_VADSS": float(base_vmax * vmax_scale),
                    "km_scale": float(km_scale),
                    "km_value": float(kms[substrate]),
                    "integrated_flux_nrmse": integrated_flux_nrmse(targets),
                    "window_integrals_mM": [
                        target.model_unknown_flux_integral_mM for target in targets
                    ],
                    "required_window_integrals_mM": [
                        target.required_unknown_flux_integral_mM for target in targets
                    ],
                }
            )
    selected = min(rows, key=lambda row: row["integrated_flux_nrmse"])
    selected["identifiability"] = _sensitivity_diagnostics(
        time=frame["time_day"].to_numpy(dtype=float),
        imp=states["IMP"],
        asp=states["ASP"],
        gtp=states["GTP"],
        vmax=float(selected["vmax_VADSS"]),
        substrate=substrate,
        km=float(selected["km_value"]),
    )
    return rows, selected


def _plot(
    frame: pd.DataFrame,
    factors: Mapping[str, np.ndarray],
    family_rows: Sequence[Mapping[str, Any]],
    selected: Mapping[str, Mapping[str, Any]],
    out_path: Path,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13.5, 9.0), constrained_layout=True)
    time = frame["time_day"].to_numpy(dtype=float)
    for name, color in (("IMP", "#d1495b"), ("ASP", "#2a9d8f"), ("GTP", "#457b9d")):
        axes[0, 0].plot(time, factors[name], label=name, color=color, lw=2)
    axes[0, 0].set_title("VADSS Michaelis saturation factors")
    axes[0, 0].set_ylabel("Saturation fraction")
    axes[0, 0].legend()

    axes[0, 1].plot(time, frame["VADSS"], color="#333333", lw=2)
    axes[0, 1].set_title("Full-ODE VADSS flux")
    axes[0, 1].set_ylabel("mM/day")

    rows = pd.DataFrame(family_rows)
    for substrate, local in rows.groupby("substrate"):
        pivot = local.pivot(index="km_scale", columns="vmax_scale", values="integrated_flux_nrmse")
        best_by_km = pivot.min(axis=1)
        axes[1, 0].plot(best_by_km.index, best_by_km.values, label=substrate, lw=2)
    axes[1, 0].set_xscale("log")
    axes[1, 0].set_title("Best fixed-state score at each Km scale")
    axes[1, 0].set_xlabel("Km scale versus legacy")
    axes[1, 0].set_ylabel("Integrated VADSS teacher nRMSE")
    axes[1, 0].legend()

    labels = list(selected)
    scores = [selected[name]["integrated_flux_nrmse"] for name in labels]
    axes[1, 1].bar(labels, scores, color=["#d1495b", "#2a9d8f", "#457b9d"])
    axes[1, 1].set_title("Best two-parameter family")
    axes[1, 1].set_ylabel("Integrated VADSS teacher nRMSE")
    for axis in axes.flat:
        axis.grid(alpha=0.2)
        if axis is not axes[1, 0]:
            axis.set_xlabel("Storage day" if axis in axes[0, :] else "Substrate")
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def run(source: Path, anchor: Path, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    all_frame = pd.read_csv(source)
    frame = all_frame.loc[all_frame["candidate"] == SOURCE_LABEL].copy()
    if frame.empty:
        raise ValueError(f"candidate {SOURCE_LABEL!r} is absent from {source}")
    exp_time, curves, *_ = _load_brodbar_panel()
    _state, params, seed_path, _anchor_vmax = _build_anchor(anchor)
    base_vmax = float(params["vmax_VADSS"])
    states = {
        name: frame[name].to_numpy(dtype=float) for name in ("IMP", "ASP", "GTP")
    }
    factors = {
        name: michaelis_fraction(states[name], LEGACY_KM[name])
        for name in ("IMP", "ASP", "GTP")
    }
    reconstructed = base_vmax * factors["IMP"] * factors["ASP"] * factors["GTP"]
    max_reconstruction_error = float(
        np.max(np.abs(reconstructed - frame["VADSS"].to_numpy(dtype=float)))
    )
    if max_reconstruction_error > 1e-10:
        raise AssertionError("VADSS fixed-state reconstruction is not exact")

    baseline_targets = build_joint_vadss_targets(
        frame, exp_time, curves, frame["VADSS"].to_numpy(dtype=float)
    )
    family_rows: list[dict[str, Any]] = []
    selected: dict[str, dict[str, Any]] = {}
    for substrate in ("IMP", "ASP", "GTP"):
        rows, winner = _map_family(
            frame=frame,
            exp_time=exp_time,
            curves=curves,
            base_vmax=base_vmax,
            substrate=substrate,
        )
        family_rows.extend(rows)
        selected[substrate] = winner
    best_substrate = min(
        selected, key=lambda name: selected[name]["integrated_flux_nrmse"]
    )
    best = selected[best_substrate]
    baseline_score = integrated_flux_nrmse(baseline_targets)
    improvement = (baseline_score - best["integrated_flux_nrmse"]) / baseline_score

    collapse = {
        name: {
            "day1_fraction": float(values[0]),
            "day46_fraction": float(values[-1]),
            "day46_to_day1_ratio": float(values[-1] / max(values[0], 1e-15)),
        }
        for name, values in factors.items()
    }
    summary = {
        "contract_type": "fixed_state_joint_adenylate_IMP_VADSS_saturation_audit",
        "contract_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "optimization_performed": False,
        "parameters_promoted": False,
        "source_timeseries": str(source.resolve()),
        "source_anchor": str(anchor.resolve()),
        "seed_params_path": str(seed_path.resolve()),
        "legacy_parameters": {
            "vmax_VADSS": base_vmax,
            **{f"km_{name}": value for name, value in LEGACY_KM.items()},
        },
        "maximum_flux_reconstruction_error": max_reconstruction_error,
        "saturation_collapse": collapse,
        "baseline_integrated_flux_nrmse": baseline_score,
        "teacher_definition": (
            "VAMPD1 window integrals are first inferred from measured ATP+ADP+AMP; "
            "those teacher integrals are then inserted into the measured IMP balance "
            "to infer VADSS window integrals"
        ),
        "baseline_windows": [target.to_dict() for target in baseline_targets],
        "best_by_substrate": selected,
        "best_substrate": best_substrate,
        "best_fixed_state_candidate": best,
        "best_score_improvement_fraction": float(improvement),
        "decision": (
            "advance enzyme-specific km_GTP_VADSS plus vmax_VADSS to a small full-ODE "
            "feasibility screen; do not alter shared km_GTP"
            if best_substrate == "GTP"
            and improvement >= 0.2
            and bool(best["identifiability"]["identifiable"])
            else "do not open VADSS kinetics; investigate GTP regeneration and network ownership"
        ),
    }
    pd.DataFrame(family_rows).drop(
        columns=["window_integrals_mM", "required_window_integrals_mM"]
    ).to_csv(out_dir / "vadss_fixed_state_family_map.csv", index=False)
    pd.DataFrame(
        {
            "time_day": frame["time_day"],
            "IMP": states["IMP"],
            "ASP": states["ASP"],
            "GTP": states["GTP"],
            "VADSS": frame["VADSS"],
            "IMP_saturation": factors["IMP"],
            "ASP_saturation": factors["ASP"],
            "GTP_saturation": factors["GTP"],
        }
    ).to_csv(out_dir / "vadss_saturation_trace.csv", index=False)
    _plot(
        frame,
        factors,
        family_rows,
        selected,
        out_dir / "vadss_saturation_audit.png",
    )
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    report = (
        "# VADSS saturation audit after VAMPD1 storage decay\n\n"
        f"- Legacy VADSS integrated-teacher nRMSE: `{baseline_score:.5f}`.\n"
        f"- Dominant fixed-state family: `{best_substrate}`.\n"
        f"- Best mapped point: `vmax={best['vmax_VADSS']:.6g}`, "
        f"`km_{best_substrate}_VADSS={best['km_value']:.6g}`.\n"
        f"- Mapped nRMSE: `{best['integrated_flux_nrmse']:.5f}` "
        f"(`{100.0 * improvement:.1f}%` improvement).\n"
        f"- Local rank/condition: `{best['identifiability']['rank']}` / "
        f"`{best['identifiability']['condition_number']:.5g}`.\n"
        f"- GTP saturation J1 to J46: `{collapse['GTP']['day1_fraction']:.5f}` to "
        f"`{collapse['GTP']['day46_fraction']:.5f}`.\n\n"
        f"{summary['decision']}\n"
    )
    (out_dir / "decision_report.md").write_text(report, encoding="utf-8")
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--anchor", type=Path, default=DEFAULT_ANCHOR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    summary = run(args.source, args.anchor, args.out_dir)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
