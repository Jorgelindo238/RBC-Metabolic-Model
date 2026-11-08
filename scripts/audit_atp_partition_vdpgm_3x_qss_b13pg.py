"""Attribute ATP sustainability changes caused by the retained 3x VDPGM branch."""

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
SRC_DIR = ROOT / "src"
SCRIPT_DIR = ROOT / "scripts"
DEFAULT_OUT_DIR = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "atp_partition_vdpgm_3x_qss_b13pg_J1_J3"
)

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from equadiff_brodbar import BRODBAR_METABOLITE_MAP, MODEL_NETWORK_VERSION  # noqa: E402
from audit_atp_transition_v6pgd_ppp_context import (  # noqa: E402
    ATP_CONSUMPTION,
    ATP_PRODUCTION,
    _build_timeseries as _build_atp_timeseries,
    _first_sustained_below,
    _integral,
    _time_mean,
)
from audit_b13pg_balance_v6pgd_ppp_context import (  # noqa: E402
    _effective_balance as _effective_b13pg_balance,
    _mm,
    _param,
    _raw_b13pg_balance,
)
from audit_b23pg_balance_qss_context import QSS_LABEL, _build_state_contract  # noqa: E402
from profile_glycolysis_flux_bottlenecks import (  # noqa: E402
    _jsonable,
    _simulate_and_track,
)
from screen_vmax_vdpgm_qss_b13pg import _candidate_params as _vdpgm_params  # noqa: E402


SEED_LABEL = "qss_vdpgm_seed"
CANDIDATE_LABEL = "qss_vdpgm_3.000x"
MULTIPLIER = 3.0
WINDOWS = (
    ("J1_J1.1", 1.0, 1.1),
    ("J1.1_J1.3", 1.1, 1.3),
    ("J1.3_J1.6", 1.3, 1.6),
    ("J1.6_J2", 1.6, 2.0),
    ("J2_J3", 2.0, 3.0),
    ("J1_J3", 1.0, 3.0),
)
EXTRA_STATES = ("GA3P", "NAD", "NADH", "B23PG", "P3G", "P2G")
EXTRA_INDICES = {
    name: int(BRODBAR_METABOLITE_MAP[name]) for name in EXTRA_STATES
}


def _changed_parameters(
    seed: Mapping[str, Any], candidate: Mapping[str, Any]
) -> list[str]:
    return sorted(
        key
        for key in set(seed) | set(candidate)
        if seed.get(key) != candidate.get(key)
    )


def _build_contract() -> tuple[np.ndarray, dict[str, Any], dict[str, Any], Path]:
    states, seed_params, seed_path = _build_state_contract()
    candidate_params, reported_seed, reported_changed = _vdpgm_params(
        seed_params, MULTIPLIER
    )
    changed = _changed_parameters(seed_params, candidate_params)
    if (
        changed != ["vmax_VDPGM"]
        or reported_changed != changed
        or not np.isclose(reported_seed, float(seed_params["vmax_VDPGM"]))
    ):
        raise RuntimeError(
            "VDPGM ATP attribution contract failed: "
            f"changed={changed}, reported={reported_changed}"
        )
    return (
        np.asarray(states[QSS_LABEL], dtype=float),
        dict(seed_params),
        candidate_params,
        seed_path,
    )


def _replay(
    *,
    label: str,
    state: np.ndarray,
    params: Mapping[str, Any],
    time: np.ndarray,
    method: str,
    rtol: float,
    atol: float,
    closure_tolerance: float,
) -> tuple[pd.DataFrame, dict[str, float]]:
    sol, fluxes, derivatives = _simulate_and_track(
        params=params,
        t_eval=time,
        method=method,
        rtol=rtol,
        atol=atol,
        x0_override=state,
    )
    frame, atp_closure = _build_atp_timeseries(
        label=label,
        sol=sol,
        fluxes=fluxes,
        derivatives=derivatives,
        params=params,
        closure_tolerance=closure_tolerance,
    )

    b13pg = frame["B13PG"].to_numpy(dtype=float)
    b13_raw = _raw_b13pg_balance(fluxes)
    b13_net, b13_damping = _effective_b13pg_balance(b13_raw, b13pg)
    b13_derivative = np.asarray(
        derivatives[int(BRODBAR_METABOLITE_MAP["B13PG"]), :], dtype=float
    )
    b13_closure = float(np.max(np.abs(b13_net - b13_derivative)))
    if b13_closure > float(closure_tolerance):
        raise RuntimeError(f"B13PG closure failed for {label}: {b13_closure:.6g}")

    vgapdh = np.asarray(fluxes["VGAPDH"], dtype=float)
    vpgk = np.asarray(fluxes["VPGK"], dtype=float)
    vdpgm = np.asarray(fluxes["VDPGM"], dtype=float)
    total_drain = vpgk + vdpgm
    nad = np.maximum(
        np.asarray(sol.y[EXTRA_INDICES["NAD"], :], dtype=float), 1e-6
    )
    nadh = np.maximum(
        np.asarray(sol.y[EXTRA_INDICES["NADH"], :], dtype=float), 1e-6
    )
    redox_drive = _mm(
        nad / (nadh + 1e-6), _param(params, "km_NAD_NADH", 1.0)
    )
    frame["VGAPDH"] = vgapdh
    frame["VDPGM"] = vdpgm
    frame["B13PG_total_drainage"] = total_drain
    frame["VPGK_partition_share"] = np.divide(
        vpgk, total_drain, out=np.zeros_like(vpgk), where=np.abs(total_drain) > 1e-30
    )
    frame["VDPGM_partition_share"] = np.divide(
        vdpgm, total_drain, out=np.zeros_like(vdpgm), where=np.abs(total_drain) > 1e-30
    )
    frame["VGAPDH_NAD_NADH_drive"] = redox_drive
    frame["B13PG_raw_net_flux"] = b13_raw
    frame["B13PG_effective_net_flux"] = b13_net
    frame["B13PG_damping_adjustment"] = b13_damping
    frame["B13PG_ode_derivative"] = b13_derivative
    frame["B13PG_closure_error"] = b13_net - b13_derivative
    for name, index in EXTRA_INDICES.items():
        frame[name] = np.asarray(sol.y[index, :], dtype=float)
    return frame, {
        **atp_closure,
        "max_abs_B13PG_closure_error": b13_closure,
    }


def _window_mask(frame: pd.DataFrame, start: float, end: float) -> np.ndarray:
    time = frame["time_day"].to_numpy(dtype=float)
    return (time >= start - 1e-12) & (time <= end + 1e-12)


def _window_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for window, start, end in WINDOWS:
        mask = _window_mask(frame, start, end)
        local = frame.loc[mask]
        time = local["time_day"].to_numpy(dtype=float)
        production = {
            name: _integral(local[name].to_numpy(dtype=float), time)
            for name in ATP_PRODUCTION
        }
        consumption = {
            name: _integral(local[name].to_numpy(dtype=float), time)
            for name in ATP_CONSUMPTION
        }
        vpgk = production["VPGK"]
        vdpgm = _integral(local["VDPGM"].to_numpy(dtype=float), time)
        b13_drain = vpgk + vdpgm
        atp = local["ATP"].to_numpy(dtype=float)
        row: dict[str, Any] = {
            "candidate": str(frame["candidate"].iloc[0]),
            "window": window,
            "start_day": start,
            "end_day": end,
            "ATP_start_mM": float(atp[0]),
            "ATP_end_mM": float(atp[-1]),
            "ATP_change_mM": float(atp[-1] - atp[0]),
            "ATP_production_integral": sum(production.values()),
            "ATP_consumption_integral": sum(consumption.values()),
            "ATP_effective_net_integral": _integral(
                local["ATP_net_flux"].to_numpy(dtype=float), time
            ),
            "VGAPDH_integral": _integral(local["VGAPDH"], time),
            "VPGK_integral": vpgk,
            "VDPGM_integral": vdpgm,
            "B13PG_total_drainage_integral": b13_drain,
            "VPGK_partition_share": vpgk / max(abs(b13_drain), 1e-30),
            "VDPGM_partition_share": vdpgm / max(abs(b13_drain), 1e-30),
            "VGAPDH_redox_drive_mean": _time_mean(
                local["VGAPDH_NAD_NADH_drive"].to_numpy(dtype=float), time
            ),
            "B13PG_mean_mM": _time_mean(local["B13PG"].to_numpy(dtype=float), time),
            "ATP_integral_to_pool_change_error": _integral(
                local["ATP_net_flux"].to_numpy(dtype=float), time
            )
            - float(atp[-1] - atp[0]),
        }
        for reaction, value in production.items():
            row[f"{reaction}_integral"] = value
        for reaction, value in consumption.items():
            row[f"{reaction}_integral"] = value
        rows.append(row)
    return rows


def _reaction_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    mask = _window_mask(frame, 1.0, 3.0)
    local = frame.loc[mask]
    time = local["time_day"].to_numpy(dtype=float)
    rows: list[dict[str, Any]] = []
    for role, names, sign in (
        ("producer", ATP_PRODUCTION, 1.0),
        ("consumer", ATP_CONSUMPTION, -1.0),
    ):
        for name in names:
            integral = _integral(local[name].to_numpy(dtype=float), time)
            rows.append(
                {
                    "candidate": str(frame["candidate"].iloc[0]),
                    "reaction": name,
                    "role": role,
                    "integrated_flux_J1_J3": integral,
                    "signed_ATP_contribution_J1_J3": sign * integral,
                }
            )
    return rows


def _delta_rows(windows: pd.DataFrame) -> pd.DataFrame:
    numeric = [
        name
        for name in windows.columns
        if name not in {"candidate", "window"}
        and pd.api.types.is_numeric_dtype(windows[name])
    ]
    rows: list[dict[str, Any]] = []
    for window, _, _ in WINDOWS:
        seed = windows.loc[
            (windows["candidate"] == SEED_LABEL) & (windows["window"] == window)
        ].iloc[0]
        candidate = windows.loc[
            (windows["candidate"] == CANDIDATE_LABEL)
            & (windows["window"] == window)
        ].iloc[0]
        row: dict[str, Any] = {"window": window}
        for name in numeric:
            row[f"delta_{name}"] = float(candidate[name] - seed[name])
            if name.endswith("integral") or name.endswith("mean_mM"):
                row[f"relative_delta_{name}"] = float(
                    (candidate[name] - seed[name]) / max(abs(seed[name]), 1e-30)
                )
        rows.append(row)
    return pd.DataFrame(rows)


def _reaction_delta_attribution(reactions: pd.DataFrame) -> dict[str, Any]:
    seed = reactions.loc[reactions["candidate"] == SEED_LABEL].set_index("reaction")
    candidate = reactions.loc[
        reactions["candidate"] == CANDIDATE_LABEL
    ].set_index("reaction")
    consumer_rows: list[dict[str, Any]] = []
    for reaction in ATP_CONSUMPTION:
        seed_flux = float(seed.loc[reaction, "integrated_flux_J1_J3"])
        candidate_flux = float(candidate.loc[reaction, "integrated_flux_J1_J3"])
        consumer_rows.append(
            {"reaction": reaction, "consumption_relief_mM": seed_flux - candidate_flux}
        )
    total_relief = sum(row["consumption_relief_mM"] for row in consumer_rows)
    for row in consumer_rows:
        row["fraction_of_consumption_relief"] = row[
            "consumption_relief_mM"
        ] / max(abs(total_relief), 1e-30)
    consumer_rows.sort(key=lambda row: abs(row["consumption_relief_mM"]), reverse=True)
    return {
        "total_ATP_consumption_relief_J1_J3_mM": total_relief,
        "consumer_reaction_changes": consumer_rows,
    }


def _summary_metrics(frame: pd.DataFrame, windows: pd.DataFrame) -> dict[str, Any]:
    time = frame["time_day"].to_numpy(dtype=float)
    atp = frame["ATP"].to_numpy(dtype=float)
    severe_day = _first_sustained_below(
        time, atp, threshold=0.01, duration=0.02
    )
    total = windows.loc[windows["window"] == "J1_J3"].iloc[0]
    return {
        "ATP_initial_mM": float(atp[0]),
        "ATP_final_mM": float(atp[-1]),
        "ATP_minimum_mM": float(np.min(atp)),
        "ATP_below_0.01_mM_day": severe_day,
        "ATP_production_integral_J1_J3": float(total["ATP_production_integral"]),
        "ATP_consumption_integral_J1_J3": float(total["ATP_consumption_integral"]),
        "VPGK_integral_J1_J3": float(total["VPGK_integral"]),
        "VDPGM_integral_J1_J3": float(total["VDPGM_integral"]),
        "VGAPDH_integral_J1_J3": float(total["VGAPDH_integral"]),
        "VPGK_partition_share_J1_J3": float(total["VPGK_partition_share"]),
        "VDPGM_partition_share_J1_J3": float(total["VDPGM_partition_share"]),
        "VGAPDH_redox_drive_mean_J1_J3": float(total["VGAPDH_redox_drive_mean"]),
        "B13PG_mean_mM_J1_J3": float(total["B13PG_mean_mM"]),
    }


def _classify(seed: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    def rel(name: str) -> float:
        return float(
            (candidate[name] - seed[name]) / max(abs(float(seed[name])), 1e-30)
        )

    production_delta = float(
        candidate["ATP_production_integral_J1_J3"]
        - seed["ATP_production_integral_J1_J3"]
    )
    vpgk_delta = float(
        candidate["VPGK_integral_J1_J3"] - seed["VPGK_integral_J1_J3"]
    )
    vdpgm_delta = float(
        candidate["VDPGM_integral_J1_J3"] - seed["VDPGM_integral_J1_J3"]
    )
    gates = {
        "VGAPDH_supply_change_within_5pct": abs(rel("VGAPDH_integral_J1_J3")) <= 0.05,
        "GAPDH_redox_drive_change_within_5pct": abs(
            rel("VGAPDH_redox_drive_mean_J1_J3")
        )
        <= 0.05,
        "VDPGM_integral_increases": vdpgm_delta > 0.0,
        "VPGK_integral_decreases": vpgk_delta < 0.0,
        "ATP_production_decreases": production_delta < 0.0,
    }
    if all(gates.values()):
        classification = "VDPGM diversion lowers VPGK ATP yield at fixed upstream supply"
    elif gates["VDPGM_integral_increases"] and not gates[
        "VGAPDH_supply_change_within_5pct"
    ]:
        classification = "coupled upstream supply and VPGK/VDPGM partition response"
    else:
        classification = "VDPGM partition is not the dominant ATP-production change"
    return {
        "classification": classification,
        "classification_gates": gates,
        "relative_changes_J1_J3": {
            "VGAPDH": rel("VGAPDH_integral_J1_J3"),
            "VGAPDH_redox_drive": rel("VGAPDH_redox_drive_mean_J1_J3"),
            "VPGK": rel("VPGK_integral_J1_J3"),
            "VDPGM": rel("VDPGM_integral_J1_J3"),
            "ATP_production": rel("ATP_production_integral_J1_J3"),
            "ATP_consumption": rel("ATP_consumption_integral_J1_J3"),
        },
        "absolute_changes_J1_J3": {
            "VPGK_integral": vpgk_delta,
            "VDPGM_integral": vdpgm_delta,
            "ATP_production_integral": production_delta,
            "ATP_consumption_integral": float(
                candidate["ATP_consumption_integral_J1_J3"]
                - seed["ATP_consumption_integral_J1_J3"]
            ),
        },
        "VPGK_fraction_of_ATP_production_loss": (
            -vpgk_delta / max(-production_delta, 1e-30)
            if production_delta < 0.0 and vpgk_delta < 0.0
            else None
        ),
    }


def _plot(frames: Mapping[str, pd.DataFrame], out_path: Path) -> None:
    colors = {SEED_LABEL: "#111827", CANDIDATE_LABEL: "#b45309"}
    fig, axes = plt.subplots(3, 2, figsize=(13, 12), constrained_layout=True)
    for label, frame in frames.items():
        time = frame["time_day"]
        color = colors[label]
        axes[0, 0].plot(time, frame["ATP"], color=color, label=label)
        axes[0, 1].plot(time, frame["ATP_production_flux"], color=color, label=label)
        axes[0, 1].plot(time, frame["ATP_consumption_flux"], color=color, ls="--")
        axes[1, 0].plot(time, frame["VPGK"], color=color, label=label)
        axes[1, 1].plot(time, frame["VDPGM"], color=color, label=label)
        axes[2, 0].plot(time, frame["VGAPDH"], color=color, label=label)
        axes[2, 1].plot(time, frame["VPGK_partition_share"], color=color, label=label)
    axes[0, 0].set_title("ATP pool")
    axes[0, 1].set_title("ATP production (solid) and consumption (dashed)")
    axes[1, 0].set_title("ATP-producing B13PG drain: VPGK")
    axes[1, 1].set_title("Rapoport-Luebering diversion: VDPGM")
    axes[2, 0].set_title("Upstream B13PG supply: VGAPDH")
    axes[2, 1].set_title("VPGK share of B13PG drainage")
    for axis in axes.flat:
        axis.set_xlabel("Day")
        axis.grid(alpha=0.2)
    axes[0, 0].set_ylabel("mM")
    for axis in (axes[0, 1], axes[1, 0], axes[1, 1], axes[2, 0]):
        axis.set_ylabel("mM/day")
    axes[2, 1].set_ylabel("fraction")
    axes[0, 0].legend(frameon=False)
    fig.suptitle("ATP attribution at fixed QSS-B13PG: VDPGM seed versus 3x")
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _report(summary: Mapping[str, Any]) -> str:
    result = summary["attribution"]
    relative = result["relative_changes_J1_J3"]
    seed = summary["metrics"][SEED_LABEL]
    candidate = summary["metrics"][CANDIDATE_LABEL]
    relief = summary["reaction_attribution"]["consumer_reaction_changes"]
    top_relief = ", ".join(
        f"{row['reaction']} ({100.0 * row['fraction_of_consumption_relief']:.1f}%)"
        for row in relief[:4]
    )
    return "\n".join(
        [
            "# Audit ATP et partition VPGK/VDPGM, J1-J3",
            "",
            "## Contrat",
            "",
            "- Etat initial QSS-B13PG identique dans les deux branches.",
            "- Toutes les cinetiques sont fixes; seul `vmax_VDPGM` passe du seed a 3x.",
            "- Les bilans ATP et B13PG sont reconstruits depuis les flux natifs de l'ODE.",
            "",
            "## Resultat",
            "",
            f"- Classification: **{result['classification']}**.",
            f"- Variation integree VGAPDH: {100.0 * relative['VGAPDH']:.3f}%.",
            f"- Variation du controle redox GAPDH: {100.0 * relative['VGAPDH_redox_drive']:.3f}%.",
            f"- Variation integree VPGK: {100.0 * relative['VPGK']:.3f}%.",
            f"- Variation integree VDPGM: {100.0 * relative['VDPGM']:.3f}%.",
            f"- Variation de production ATP: {100.0 * relative['ATP_production']:.3f}%.",
            f"- Variation de consommation ATP: {100.0 * relative['ATP_consumption']:.3f}%.",
            f"- La perte VPGK explique {100.0 * result['VPGK_fraction_of_ATP_production_loss']:.2f}% de la baisse de production ATP.",
            f"- Principales baisses compensatoires de consommation: {top_relief}.",
            f"- ATP final seed / 3x: {seed['ATP_final_mM']:.6g} / {candidate['ATP_final_mM']:.6g} mM.",
            f"- Jour ATP < 0.01 mM seed / 3x: {seed['ATP_below_0.01_mM_day']} / {candidate['ATP_below_0.01_mM_day']}.",
            "",
            "## Decision",
            "",
            "Le point 3x reste un diagnostic B23PG, pas une calibration globale. Aucun nouveau parametre ne doit etre ouvert avant d'avoir reconstruit, depuis l'ATP experimental et la consommation native, le VPGK requis puis le VGAPDH requis sous ce partage VDPGM.",
            "",
        ]
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--points", type=int, default=2001)
    parser.add_argument("--method", default="BDF")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    parser.add_argument("--closure-tolerance", type=float, default=1e-7)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.points < 11:
        raise ValueError("--points must be at least 11")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    state, seed_params, candidate_params, seed_path = _build_contract()
    time = np.linspace(1.0, 3.0, args.points)
    frames: dict[str, pd.DataFrame] = {}
    closures: dict[str, Any] = {}
    for label, params in (
        (SEED_LABEL, seed_params),
        (CANDIDATE_LABEL, candidate_params),
    ):
        frames[label], closures[label] = _replay(
            label=label,
            state=state,
            params=params,
            time=time,
            method=args.method,
            rtol=args.rtol,
            atol=args.atol,
            closure_tolerance=args.closure_tolerance,
        )
    timeseries = pd.concat(frames.values(), ignore_index=True)
    windows = pd.DataFrame(
        [row for frame in frames.values() for row in _window_rows(frame)]
    )
    reactions = pd.DataFrame(
        [row for frame in frames.values() for row in _reaction_rows(frame)]
    )
    deltas = _delta_rows(windows)
    metrics = {
        label: _summary_metrics(frame, windows.loc[windows["candidate"] == label])
        for label, frame in frames.items()
    }
    attribution = _classify(metrics[SEED_LABEL], metrics[CANDIDATE_LABEL])
    reaction_attribution = _reaction_delta_attribution(reactions)
    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "model_network_version": MODEL_NETWORK_VERSION,
        "seed_params_path": str(seed_path.resolve()),
        "state_contract": "same qss_1.000x B13PG/B23PG state for both branches",
        "changed_parameters": _changed_parameters(seed_params, candidate_params),
        "vmax_VDPGM_seed": float(seed_params["vmax_VDPGM"]),
        "vmax_VDPGM_candidate": float(candidate_params["vmax_VDPGM"]),
        "vmax_VDPGM_multiplier": MULTIPLIER,
        "solver": {
            "method": args.method,
            "rtol": args.rtol,
            "atol": args.atol,
            "points": args.points,
        },
        "closures": closures,
        "metrics": metrics,
        "attribution": attribution,
        "reaction_attribution": reaction_attribution,
        "decision": "retain 3x as a B23PG diagnostic only; do not open a kinetic lever",
        "next_step": "reconstruct ATP-teacher-required VPGK and then VGAPDH in the fixed 3x branch",
    }
    timeseries.to_csv(args.out_dir / "timeseries_J1_J3.csv", index=False)
    windows.to_csv(args.out_dir / "window_balance_and_partition.csv", index=False)
    reactions.to_csv(args.out_dir / "atp_reaction_attribution_J1_J3.csv", index=False)
    deltas.to_csv(args.out_dir / "candidate_minus_seed_deltas.csv", index=False)
    (args.out_dir / "summary.json").write_text(
        json.dumps(_jsonable(summary), indent=2), encoding="utf-8"
    )
    (args.out_dir / "report.md").write_text(_report(summary), encoding="utf-8")
    _plot(frames, args.out_dir / "atp_partition_vdpgm_3x_J1_J3.png")
    print(json.dumps(_jsonable(summary), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
