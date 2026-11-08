"""Profile glycolytic flux bottlenecks before the next Brodbar FLA pass.

The script is deliberately diagnostic-only. It replays saved parameter sets,
uses the ODE's native FluxTracker to recover the exact reaction rates, and
reconciles those rates against the metabolite balance equations. No parameter
optimization or promotion is performed.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp, trapezoid


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
DEFAULT_OUT_DIR = ROOT / "output" / "fla_preoptimization_glycolysis_profile"

for path in (str(ROOT), str(SRC_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from MM_calibration import load_experimental_data, load_initial_conditions  # noqa: E402
from equadiff_brodbar import BRODBAR_METABOLITE_MAP, equadiff_brodbar  # noqa: E402
from flux_visualization import FluxTracker  # noqa: E402


DEFAULT_CANDIDATES = {
    "global_baseline": ROOT / "Simulations" / "brodbar" / "calibration" / "best_params.json",
    "veglc_gate": (
        ROOT
        / "Simulations"
        / "brodbar"
        / "hermes"
        / "transport_gate_eglc_elac_46d_n32_endpoint16"
        / "best_params.json"
    ),
    "vhk_atp": (
        ROOT
        / "Simulations"
        / "brodbar"
        / "hermes"
        / "glucose_utilization_vhk_atp_46d_n16_upper5"
        / "candidate_params.json"
    ),
    "veglc_feedback": (
        ROOT
        / "Simulations"
        / "brodbar"
        / "hermes"
        / "veglc_import_feedback_vhk_atp_seed_46d_n28"
        / "candidate_params.json"
    ),
}

REFERENCE_CANDIDATE = "vhk_atp"

STATE_NAMES = (
    "EGLC",
    "ELAC",
    "GLC",
    "G6P",
    "F6P",
    "F16BP",
    "DHCP",
    "GA3P",
    "B13PG",
    "B23PG",
    "P3G",
    "P2G",
    "PEP",
    "PYR",
    "LAC",
    "ATP",
    "ADP",
    "NAD",
    "NADH",
)

MAIN_FLUXES = (
    "VEGLC",
    "VHK",
    "VPGI",
    "VPFK",
    "VFDPA",
    "VGAPDH",
    "VPGK",
    "VPGM",
    "VENOPGM",
    "VPK",
    "VLDH",
    "VELAC",
)

# Coefficients reproduce the corresponding dxdt expressions in equadiff_brodbar.
POOL_BALANCE_TERMS: dict[str, tuple[tuple[str, float], ...]] = {
    "GLC": (("VEGLC", 1.0), ("VHK", -1.0)),
    "G6P": (("VHK", 1.0), ("VPGI", -1.0), ("VG6PDH", -1.0)),
    "F6P": (("VPGI", 1.0), ("VPFK", -1.0), ("VTKL2", 1.0), ("VTAL", 1.0)),
    "F16BP": (("VPFK", 1.0), ("VFDPA", -1.0)),
    "DHCP": (("VFDPA", 1.0), ("VTPI", -1.0)),
    "GA3P": (
        ("VFDPA", 1.0),
        ("VTPI", 1.0),
        ("VGAPDH", -1.0),
        ("VTKL1", 1.0),
        ("VTKL2", 1.0),
        ("VTAL", -1.0),
    ),
    "B13PG": (("VGAPDH", 1.0), ("VPGK", -1.0), ("VDPGM", -1.0)),
    "B23PG": (("VDPGM", 1.0), ("V23DPGP", -1.0)),
    "P3G": (("VPGK", 1.0), ("VPGM", -1.0), ("V23DPGP", 1.0), ("VPHGDH", -1.0)),
    "P2G": (("VPGM", 1.0), ("VENOPGM", -1.0)),
    "PEP": (("VENOPGM", 1.0), ("VPK", -1.0), ("VPEP_PASE", -1.0)),
    "PYR": (
        ("VPK", 1.0),
        ("VLDH", -1.0),
        ("VEPYR", -1.0),
        ("VME", 1.0),
        ("VALATA", 1.0),
        ("VPEP_PASE", 1.0),
    ),
    "LAC": (("VLDH", 1.0), ("VELAC", -1.0)),
    "NADH": (
        ("VGAPDH", 1.0),
        ("VMLD", 1.0),
        ("VIMPH", 1.0),
        ("VPHGDH", 1.0),
        ("VLDH", -1.0),
    ),
    "ATP": (
        ("VPGK", 1.0),
        ("VPK", 1.0),
        ("VAK", 1.0),
        ("VHK", -1.0),
        ("VPFK", -1.0),
        ("VAK2", -1.0),
        ("VGLNS", -1.0),
        ("VGLUCYS", -1.0),
        ("VGSS", -1.0),
        ("VSAM", -1.0),
        ("VRKa", -1.0),
        ("VPRPPASe", -1.0),
        ("VGMPS", -1.0),
        ("VGMPK", -1.0),
        ("VNDPK", -1.0),
        ("VOPLAH", -1.0),
    ),
}

OUTLET_REACTIONS: dict[str, tuple[str, ...]] = {
    "GLC": ("VHK",),
    "G6P": ("VPGI", "VG6PDH"),
    "F6P": ("VPFK",),
    "F16BP": ("VFDPA",),
    "DHCP": ("VTPI",),
    "GA3P": ("VGAPDH",),
    "B13PG": ("VPGK", "VDPGM"),
    "B23PG": ("V23DPGP",),
    "P3G": ("VPGM", "VPHGDH"),
    "P2G": ("VENOPGM",),
    "PEP": ("VPK", "VPEP_PASE"),
    "PYR": ("VLDH", "VEPYR"),
    "LAC": ("VELAC",),
    "NADH": ("VLDH",),
}

DOWNSTREAM_LEVERS = {
    "G6P": "vmax_VPGI",
    "F6P": "vmax_VPFK",
    "F16BP": "vmax_VFDPA",
    "DHCP": "vmax_VTPI",
    "GA3P": "vmax_VGAPDH",
    "B13PG": "vmax_VPGK",
    "B23PG": "vmax_V23DPGP",
    "P3G": "vmax_VPGM",
    "P2G": "vmax_VENOPGM",
    "PEP": "vmax_VPK",
    "PYR": "vmax_VLDH",
    "LAC": "vmax_VELAC",
    "NADH": "vmax_VLDH",
}

SUBSTRATE_FACTOR_BY_POOL = {
    "G6P": "VPGI_G6P",
    "F6P": "VPFK_F6P",
    "F16BP": "VFDPA_F16BP",
    "GA3P": "VGAPDH_GA3P",
    "B13PG": "VPGK_B13PG",
    "P3G": "VPGM_P3G",
    "P2G": "VENOPGM_P2G",
    "PEP": "VPK_PEP",
    "PYR": "VLDH_PYR",
}

AFFINITY_LEVER_BY_POOL = {
    "G6P": "km_G6P",
    "F6P": "km_F6P",
    "F16BP": "km_F16BP",
    "GA3P": "km_GA3P",
    "B13PG": "km_B13PG",
    "P3G": "km_P3G",
    "P2G": "km_P2G",
    "PEP": "km_PEP",
    "PYR": "km_PYR",
}

# Defaults are copied from equadiff_brodbar and are used only when a saved
# candidate omits a kinetic parameter.
VMAX_DEFAULTS = {
    "VEGLC": 1.077000,
    "VHK": 0.267472,
    "VPGI": 0.204493,
    "VPFK": 0.391893,
    "VFDPA": 1.156751,
    "VTPI": 15.0,
    "VGAPDH": 6.389868,
    "VPGK": 4.690379,
    "VPGM": 1.170854,
    "VENOPGM": 5.515612,
    "VPK": 0.936322,
    "VLDH": 0.284952,
    "VELAC": 0.58,
    "VG6PDH": 0.408870,
    "VDPGM": 2.5,
    "V23DPGP": 3.0,
    "VPHGDH": 0.1,
    "VPEP_PASE": 0.1,
    "VEPYR": 0.3,
}

SENSITIVITY_CASES = {
    "lower_vpep_pase_x0.1": ("vmax_VPEP_PASE", 0.1),
    "raise_vpfk_x2": ("vmax_VPFK", 2.0),
    "raise_vpk_x2": ("vmax_VPK", 2.0),
}


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return value


def _load_params(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    out: dict[str, Any] = {}
    for name, value in payload.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            out[str(name)] = float(value)
        elif isinstance(value, str):
            out[str(name)] = value
    return out


def _parse_candidate_specs(specs: Sequence[str] | None) -> dict[str, Path]:
    if not specs:
        return dict(DEFAULT_CANDIDATES)
    out: dict[str, Path] = {}
    for spec in specs:
        if "=" not in spec:
            raise ValueError(f"Candidate must use label=path syntax: {spec!r}")
        label, raw_path = spec.split("=", 1)
        label = label.strip()
        if not label:
            raise ValueError(f"Candidate label is empty: {spec!r}")
        path = Path(raw_path.strip())
        if not path.is_absolute():
            path = ROOT / path
        out[label] = path
    return out


def _time_mean(values: np.ndarray, time: np.ndarray, mask: np.ndarray | None = None) -> float:
    values = np.asarray(values, dtype=float)
    time = np.asarray(time, dtype=float)
    if mask is not None:
        values = values[mask]
        time = time[mask]
    if values.size == 0:
        return float("nan")
    if values.size == 1 or math.isclose(float(time[-1]), float(time[0])):
        return float(values[0])
    return float(trapezoid(values, time) / (time[-1] - time[0]))


def _vmax(params: Mapping[str, Any], reaction: str) -> float:
    return float(params.get(f"vmax_{reaction}", VMAX_DEFAULTS.get(reaction, float("nan"))))


def _simulate_and_track(
    *,
    params: Mapping[str, Any],
    t_eval: np.ndarray,
    method: str,
    rtol: float,
    atol: float,
    x0_override: np.ndarray | None = None,
) -> tuple[Any, dict[str, np.ndarray], np.ndarray]:
    x0 = np.asarray(
        load_initial_conditions() if x0_override is None else x0_override,
        dtype=float,
    )
    params_dict = dict(params)
    sol = solve_ivp(
        lambda t, y: equadiff_brodbar(
            float(t),
            np.asarray(y, dtype=float),
            custom_params=params_dict,
            curve_fit_strength=0.0,
        ),
        (float(t_eval[0]), float(t_eval[-1])),
        x0,
        method=method,
        t_eval=np.asarray(t_eval, dtype=float),
        rtol=float(rtol),
        atol=float(atol),
    )
    if not sol.success:
        raise RuntimeError(sol.message)
    if not np.all(np.isfinite(sol.y)):
        raise RuntimeError("Nonfinite solver state cannot be used as FLA evidence")
    sol.raw_minimum_state_mM = float(np.min(sol.y))
    sol.negative_state_sample_count = int(np.count_nonzero(sol.y < 0.0))
    sol.y[:] = np.maximum(sol.y, 0.0)

    tracker = FluxTracker()
    derivatives = []
    for t, state in zip(sol.t, sol.y.T):
        derivatives.append(
            equadiff_brodbar(
                float(t),
                np.asarray(state, dtype=float),
                custom_params=params_dict,
                curve_fit_strength=0.0,
                flux_tracker=tracker,
            )
        )
    fluxes = {name: np.asarray(values, dtype=float) for name, values in tracker.fluxes.items()}
    return sol, fluxes, np.asarray(derivatives, dtype=float).T


def _experimental_curves(t_max: float) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    time_exp, exp_values, name_to_row = load_experimental_data()
    mask = (time_exp >= 1.0 - 1e-9) & (time_exp <= float(t_max) + 1e-9)
    time = np.asarray(time_exp[mask], dtype=float)
    curves = {
        name: np.asarray(exp_values[row, mask], dtype=float)
        for name, row in name_to_row.items()
        if name in STATE_NAMES
    }
    return time, curves


def _trajectory_rows(
    *,
    label: str,
    source_path: Path,
    sol: Any,
    derivatives: np.ndarray,
    exp_time: np.ndarray,
    exp_curves: Mapping[str, np.ndarray],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name in STATE_NAMES:
        if name not in BRODBAR_METABOLITE_MAP:
            continue
        idx = int(BRODBAR_METABOLITE_MAP[name])
        exp_values = exp_curves.get(name)
        for column, t in enumerate(sol.t):
            row = {
                "candidate": label,
                "params_path": str(source_path),
                "time_day": float(t),
                "metabolite": name,
                "concentration": float(sol.y[idx, column]),
                "ode_derivative": float(derivatives[idx, column]),
                "experimental": float("nan"),
            }
            if exp_values is not None and exp_time.size:
                row["experimental"] = float(np.interp(float(t), exp_time, exp_values))
            rows.append(row)
    return rows


def _flux_rows(
    *,
    label: str,
    source_path: Path,
    time: np.ndarray,
    fluxes: Mapping[str, np.ndarray],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for reaction, values in fluxes.items():
        for t, value in zip(time, values):
            rows.append(
                {
                    "candidate": label,
                    "params_path": str(source_path),
                    "time_day": float(t),
                    "reaction": reaction,
                    "flux": float(value),
                }
            )
    return rows


def _pool_rows(
    *,
    label: str,
    source_path: Path,
    sol: Any,
    fluxes: Mapping[str, np.ndarray],
    derivatives: np.ndarray,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pool, terms in POOL_BALANCE_TERMS.items():
        idx = int(BRODBAR_METABOLITE_MAP[pool])
        signed_terms = np.zeros(sol.t.size, dtype=float)
        inflow = np.zeros(sol.t.size, dtype=float)
        outflow = np.zeros(sol.t.size, dtype=float)
        for reaction, coefficient in terms:
            contribution = float(coefficient) * np.asarray(fluxes[reaction], dtype=float)
            signed_terms += contribution
            inflow += np.maximum(contribution, 0.0)
            outflow += np.maximum(-contribution, 0.0)
        for column, t in enumerate(sol.t):
            rows.append(
                {
                    "candidate": label,
                    "params_path": str(source_path),
                    "time_day": float(t),
                    "pool": pool,
                    "concentration": float(sol.y[idx, column]),
                    "inflow": float(inflow[column]),
                    "outflow": float(outflow[column]),
                    "net_flux_balance": float(signed_terms[column]),
                    "ode_derivative": float(derivatives[idx, column]),
                    "balance_residual": float(derivatives[idx, column] - signed_terms[column]),
                }
            )
    return rows


def summarize_fluxes(
    *,
    label: str,
    time: np.ndarray,
    fluxes: Mapping[str, np.ndarray],
    params: Mapping[str, Any],
) -> list[dict[str, Any]]:
    early = time <= min(15.0, float(time[-1]))
    late = time >= min(30.0, float(time[-1]))
    rows: list[dict[str, Any]] = []
    for reaction, values in fluxes.items():
        values = np.asarray(values, dtype=float)
        vmax = _vmax(params, reaction)
        mean_abs = _time_mean(np.abs(values), time)
        rows.append(
            {
                "candidate": label,
                "reaction": reaction,
                "mean_flux": _time_mean(values, time),
                "mean_abs_flux": mean_abs,
                "early_mean_flux": _time_mean(values, time, early),
                "late_mean_flux": _time_mean(values, time, late),
                "min_flux": float(np.min(values)),
                "max_flux": float(np.max(values)),
                "integrated_flux": float(trapezoid(values, time)),
                "vmax": vmax,
                "mean_abs_flux_over_vmax": (
                    float(mean_abs / vmax) if np.isfinite(vmax) and vmax > 0.0 else float("nan")
                ),
            }
        )
    return rows


def summarize_pools(
    *,
    pool_timeseries: pd.DataFrame,
    flux_summary: pd.DataFrame,
    params_by_candidate: Mapping[str, Mapping[str, Any]],
    exp_time: np.ndarray,
    exp_curves: Mapping[str, np.ndarray],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (candidate, pool), frame in pool_timeseries.groupby(["candidate", "pool"], sort=False):
        frame = frame.sort_values("time_day")
        time = frame["time_day"].to_numpy(dtype=float)
        concentration = frame["concentration"].to_numpy(dtype=float)
        mean_inflow = _time_mean(frame["inflow"].to_numpy(dtype=float), time)
        mean_outflow = _time_mean(frame["outflow"].to_numpy(dtype=float), time)
        initial = float(concentration[0])
        final = float(concentration[-1])
        delta = final - initial
        integrated_net_flux = float(
            trapezoid(frame["net_flux_balance"].to_numpy(dtype=float), time)
        )
        integrated_ode_derivative = float(
            trapezoid(frame["ode_derivative"].to_numpy(dtype=float), time)
        )
        outlet_reactions = OUTLET_REACTIONS.get(
            pool,
            tuple(reaction for reaction, coefficient in POOL_BALANCE_TERMS[pool] if coefficient < 0.0),
        )
        outlet_flux = float(
            sum(
                flux_summary.loc[
                    (flux_summary["candidate"] == candidate)
                    & (flux_summary["reaction"] == reaction),
                    "mean_abs_flux",
                ].iloc[0]
                for reaction in outlet_reactions
            )
        )
        outlet_vmax_values = np.asarray(
            [_vmax(params_by_candidate[candidate], rxn) for rxn in outlet_reactions], dtype=float
        )
        outlet_vmax = (
            float(np.sum(outlet_vmax_values))
            if outlet_vmax_values.size and np.all(np.isfinite(outlet_vmax_values))
            else float("nan")
        )
        outlet_utilization = (
            outlet_flux / outlet_vmax
            if np.isfinite(outlet_vmax) and outlet_vmax > 0.0
            else float("nan")
        )
        exp_final = float("nan")
        if pool in exp_curves and exp_time.size:
            exp_final = float(np.interp(float(time[-1]), exp_time, exp_curves[pool]))
        imbalance_fraction = (mean_inflow - mean_outflow) / max(mean_inflow, 1e-12)
        fold_change = final / max(abs(initial), 1e-6)
        accumulation_scale = max(abs(initial), abs(exp_final) if np.isfinite(exp_final) else 0.0, 0.01)
        normalized_accumulation = max(delta, 0.0) / accumulation_scale
        utilization_term = min(max(outlet_utilization, 0.0), 2.0) if np.isfinite(outlet_utilization) else 0.0
        restriction_score = (
            max(imbalance_fraction, 0.0)
            * math.log1p(max(normalized_accumulation, 0.0))
            * (0.5 + utilization_term)
        )
        rows.append(
            {
                "candidate": candidate,
                "pool": pool,
                "initial_concentration": initial,
                "final_concentration": final,
                "experimental_final": exp_final,
                "delta_concentration": delta,
                "fold_change": fold_change,
                "integrated_net_flux": integrated_net_flux,
                "integrated_ode_derivative": integrated_ode_derivative,
                "net_flux_closure_error": integrated_net_flux - delta,
                "ode_closure_error": integrated_ode_derivative - delta,
                "mean_inflow": mean_inflow,
                "mean_outflow": mean_outflow,
                "imbalance_fraction": imbalance_fraction,
                "outlet_reactions": "+".join(outlet_reactions),
                "outlet_mean_abs_flux": outlet_flux,
                "outlet_vmax_sum": outlet_vmax,
                "outlet_utilization": outlet_utilization,
                "mean_abs_balance_residual": _time_mean(
                    np.abs(frame["balance_residual"].to_numpy(dtype=float)), time
                ),
                "restriction_score": restriction_score,
            }
        )
    return pd.DataFrame(rows)


def _kinetic_factor_rows(
    *,
    candidate: str,
    sol: Any,
    params: Mapping[str, Any],
) -> list[dict[str, Any]]:
    p = params
    x = sol.y
    glc = np.maximum(x[BRODBAR_METABOLITE_MAP["GLC"]], 0.0)
    g6p = np.maximum(x[BRODBAR_METABOLITE_MAP["G6P"]], 0.0)
    f6p = np.maximum(x[BRODBAR_METABOLITE_MAP["F6P"]], 0.0)
    f16bp = np.maximum(x[BRODBAR_METABOLITE_MAP["F16BP"]], 0.0)
    ga3p = np.maximum(x[BRODBAR_METABOLITE_MAP["GA3P"]], 0.0)
    b13pg = np.maximum(x[BRODBAR_METABOLITE_MAP["B13PG"]], 0.0)
    p3g = np.maximum(x[BRODBAR_METABOLITE_MAP["P3G"]], 0.0)
    p2g = np.maximum(x[BRODBAR_METABOLITE_MAP["P2G"]], 0.0)
    pep = np.maximum(x[BRODBAR_METABOLITE_MAP["PEP"]], 0.0)
    pyr = np.maximum(x[BRODBAR_METABOLITE_MAP["PYR"]], 0.0)
    atp = np.maximum(x[BRODBAR_METABOLITE_MAP["ATP"]], 1e-6)
    adp = np.maximum(x[BRODBAR_METABOLITE_MAP["ADP"]], 1e-6)
    nad = np.maximum(x[BRODBAR_METABOLITE_MAP["NAD"]], 1e-6)
    nadh = np.maximum(x[BRODBAR_METABOLITE_MAP["NADH"]], 1e-6)

    def mm(values: np.ndarray, km: float) -> np.ndarray:
        return values / (float(km) + values + 1e-30)

    factors = {
        "VHK_GLC": mm(glc, float(p.get("km_GLC_HK", 0.05))),
        "VHK_ATP": mm(atp, float(p.get("km_ATP_HK", 0.5))),
        "VPGI_G6P": mm(g6p, float(p.get("km_G6P", 0.146))),
        "VPFK_F6P": mm(f6p, float(p.get("km_F6P", 0.207))),
        "VPFK_ATP": mm(atp, float(p.get("km_ATP_PFK", 0.1))),
        "VFDPA_F16BP": mm(f16bp, float(p.get("km_F16BP", 0.094))),
        "VGAPDH_GA3P": mm(ga3p, float(p.get("km_GA3P", 0.02))),
        "VGAPDH_NAD_ratio": mm(nad / nadh, float(p.get("km_NAD_NADH", 1.0))),
        "VPGK_B13PG": mm(b13pg, float(p.get("km_B13PG", 1.013344))),
        "VPGK_ADP_ratio": mm(adp / atp, float(p.get("km_ADP_ATP", 1.0))),
        "VPGM_P3G": mm(p3g, float(p.get("km_P3G", 0.134))),
        "VENOPGM_P2G": mm(p2g, float(p.get("km_P2G", 0.134))),
        "VPK_PEP": mm(pep, float(p.get("km_PEP", 0.175))),
        "VPK_ADP_ratio": mm(adp / atp, float(p.get("km_ADP_ATP", 1.0))),
        "VPK_ATP_inhibition": 1.0 / (1.0 + atp / float(p.get("ki_ATP_PK", 2.5))),
        "VPK_PYR_inhibition": 1.0 / (1.0 + pyr / float(p.get("ki_PYR_PK", 1.0))),
        "VLDH_PYR": mm(pyr, float(p.get("km_PYR", 0.697))),
        "VLDH_NADH_ratio": mm(nadh / nad, float(p.get("km_NADH_NAD", 1.0))),
    }
    rows: list[dict[str, Any]] = []
    late = sol.t >= min(30.0, float(sol.t[-1]))
    for factor, values in factors.items():
        rows.append(
            {
                "candidate": candidate,
                "kinetic_factor": factor,
                "mean_factor": _time_mean(values, sol.t),
                "late_mean_factor": _time_mean(values, sol.t, late),
                "min_factor": float(np.min(values)),
                "final_factor": float(values[-1]),
            }
        )
    return rows


def select_downstream_lever(
    pool_summary: pd.DataFrame,
    kinetic_factors: pd.DataFrame,
    reference: str,
    *,
    affinity_threshold: float = 0.6,
) -> tuple[str, pd.DataFrame]:
    ranking = pool_summary[
        (pool_summary["candidate"] == reference)
        & (pool_summary["pool"].isin(DOWNSTREAM_LEVERS))
    ].copy()
    reference_factors = kinetic_factors[kinetic_factors["candidate"] == reference].set_index(
        "kinetic_factor"
    )
    recommended_parameters = []
    substrate_factors = []
    for pool in ranking["pool"]:
        parameter = DOWNSTREAM_LEVERS[pool]
        factor_name = SUBSTRATE_FACTOR_BY_POOL.get(pool)
        factor_value = float("nan")
        if factor_name is not None and factor_name in reference_factors.index:
            factor_value = float(reference_factors.loc[factor_name, "late_mean_factor"])
            if factor_value < float(affinity_threshold):
                parameter = AFFINITY_LEVER_BY_POOL[pool]
        recommended_parameters.append(parameter)
        substrate_factors.append(factor_value)
    ranking["late_substrate_factor"] = substrate_factors
    ranking["recommended_parameter"] = recommended_parameters
    ranking = ranking.sort_values(
        ["restriction_score", "outlet_utilization"], ascending=[False, False]
    ).reset_index(drop=True)
    if ranking.empty:
        raise RuntimeError(f"No downstream pools available for {reference!r}")
    return str(ranking.iloc[0]["recommended_parameter"]), ranking


def diagnose_structural_lever(
    *,
    symptom_lever: str,
    reference: str,
    trajectory: pd.DataFrame,
    flux_summary: pd.DataFrame,
) -> dict[str, Any]:
    reference_states = trajectory[trajectory["candidate"] == reference]

    def endpoint(metabolite: str, column: str) -> float:
        frame = reference_states[reference_states["metabolite"] == metabolite].sort_values("time_day")
        return float(frame.iloc[-1][column])

    def mean_abs_flux(reaction: str) -> float:
        row = flux_summary[
            (flux_summary["candidate"] == reference) & (flux_summary["reaction"] == reaction)
        ].iloc[0]
        return float(row["mean_abs_flux"])

    atp_final = endpoint("ATP", "concentration")
    atp_exp_final = endpoint("ATP", "experimental")
    atp_ratio = atp_final / max(atp_exp_final, 1e-12) if np.isfinite(atp_exp_final) else float("nan")
    vpk = mean_abs_flux("VPK")
    vpep_pase = mean_abs_flux("VPEP_PASE")
    total_pep_drain = vpk + vpep_pase
    pk_share = vpk / max(total_pep_drain, 1e-12)
    pep_pase_share = vpep_pase / max(total_pep_drain, 1e-12)

    recommendation = {
        "symptom_ranked_lever": symptom_lever,
        "recommended_parameter": symptom_lever,
        "recommended_direction": "decrease" if symptom_lever.startswith("km_") else "increase",
        "mechanism": "highest-ranked accumulating pool",
        "ATP_final": atp_final,
        "ATP_experimental_final": atp_exp_final,
        "ATP_final_ratio_to_experimental": atp_ratio,
        "VPK_mean_abs_flux": vpk,
        "VPEP_PASE_mean_abs_flux": vpep_pase,
        "PEP_to_VPK_share": pk_share,
        "PEP_to_VPEP_PASE_share": pep_pase_share,
    }
    if np.isfinite(atp_ratio) and atp_ratio < 0.2 and pep_pase_share > 0.75:
        recommendation.update(
            {
                "recommended_parameter": "vmax_VPEP_PASE",
                "recommended_direction": "decrease",
                "mechanism": (
                    "ATP collapse with dominant ADP-independent PEP phosphatase bypass; "
                    "F6P accumulation is treated as a downstream energy symptom"
                ),
            }
        )
    return recommendation


def _sensitivity_row(
    *,
    case: str,
    parameter: str,
    multiplier: float,
    sol: Any,
    fluxes: Mapping[str, np.ndarray],
    exp_time: np.ndarray,
    exp_curves: Mapping[str, np.ndarray],
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "case": case,
        "parameter": parameter,
        "multiplier": float(multiplier),
    }
    for metabolite in ("EGLC", "GLC", "G6P", "F6P", "PEP", "PYR", "LAC", "ATP"):
        idx = int(BRODBAR_METABOLITE_MAP[metabolite])
        final = float(sol.y[idx, -1])
        experimental = float("nan")
        if metabolite in exp_curves and exp_time.size:
            experimental = float(np.interp(float(sol.t[-1]), exp_time, exp_curves[metabolite]))
        row[f"{metabolite}_final"] = final
        row[f"{metabolite}_experimental_final"] = experimental
        row[f"{metabolite}_endpoint_error"] = (
            abs(final - experimental) / max(abs(experimental), 0.01)
            if np.isfinite(experimental)
            else float("nan")
        )
    for reaction in (
        "VEGLC",
        "VHK",
        "VPGI",
        "VPFK",
        "VPGK",
        "VPK",
        "VPEP_PASE",
        "VLDH",
        "VELAC",
        "VAK",
    ):
        row[f"{reaction}_mean_abs_flux"] = _time_mean(np.abs(fluxes[reaction]), sol.t)
    pep_drain = row["VPK_mean_abs_flux"] + row["VPEP_PASE_mean_abs_flux"]
    row["PEP_to_VPK_share"] = row["VPK_mean_abs_flux"] / max(pep_drain, 1e-12)
    row["PEP_to_VPEP_PASE_share"] = row["VPEP_PASE_mean_abs_flux"] / max(pep_drain, 1e-12)
    row["ATP_production_mean"] = sum(
        _time_mean(np.asarray(fluxes[reaction], dtype=float), sol.t)
        for reaction in ("VPGK", "VPK", "VAK")
    )
    row["ATP_consumption_mean"] = sum(
        _time_mean(np.asarray(fluxes[reaction], dtype=float), sol.t)
        for reaction in (
            "VHK",
            "VPFK",
            "VAK2",
            "VGLNS",
            "VGLUCYS",
            "VGSS",
            "VSAM",
            "VRKa",
            "VPRPPASe",
            "VGMPS",
            "VGMPK",
            "VNDPK",
            "VOPLAH",
        )
    )
    row["ATP_net_mean"] = row["ATP_production_mean"] - row["ATP_consumption_mean"]
    return row


def run_fixed_sensitivity_probes(
    *,
    reference_params: Mapping[str, Any],
    reference_sol: Any,
    reference_fluxes: Mapping[str, np.ndarray],
    t_eval: np.ndarray,
    exp_time: np.ndarray,
    exp_curves: Mapping[str, np.ndarray],
    method: str,
    rtol: float,
    atol: float,
) -> pd.DataFrame:
    rows = [
        _sensitivity_row(
            case="reference",
            parameter="none",
            multiplier=1.0,
            sol=reference_sol,
            fluxes=reference_fluxes,
            exp_time=exp_time,
            exp_curves=exp_curves,
        )
    ]
    for case, (parameter, multiplier) in SENSITIVITY_CASES.items():
        params = dict(reference_params)
        if parameter not in params:
            reaction = parameter.removeprefix("vmax_")
            params[parameter] = _vmax(params, reaction)
        params[parameter] = float(params[parameter]) * float(multiplier)
        print(
            f"[profile] fixed sensitivity {case}: {parameter} x {multiplier:g}",
            flush=True,
        )
        sol, fluxes, _ = _simulate_and_track(
            params=params,
            t_eval=t_eval,
            method=method,
            rtol=rtol,
            atol=atol,
        )
        rows.append(
            _sensitivity_row(
                case=case,
                parameter=parameter,
                multiplier=multiplier,
                sol=sol,
                fluxes=fluxes,
                exp_time=exp_time,
                exp_curves=exp_curves,
            )
        )
    return pd.DataFrame(rows)


def _plot_profile(
    *,
    trajectory: pd.DataFrame,
    flux_timeseries: pd.DataFrame,
    flux_summary: pd.DataFrame,
    pool_summary: pd.DataFrame,
    ranking: pd.DataFrame,
    reference: str,
    out_path: Path,
) -> None:
    plt.rcParams.update({"font.size": 9, "axes.titlesize": 11, "axes.labelsize": 9})
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    palette = {
        "VEGLC": "#2563eb",
        "VHK": "#0f766e",
        "VPGI": "#d97706",
        "VPFK": "#9333ea",
        "VPK": "#be123c",
        "VLDH": "#4d7c0f",
        "VELAC": "#374151",
    }

    ax = axes[0, 0]
    selected_fluxes = ("VEGLC", "VHK", "VPGI", "VPFK", "VPK", "VLDH", "VELAC")
    frame = flux_timeseries[flux_timeseries["candidate"] == reference]
    for reaction in selected_fluxes:
        series = frame[frame["reaction"] == reaction].sort_values("time_day")
        ax.plot(
            series["time_day"],
            series["flux"],
            label=reaction,
            color=palette[reaction],
            linewidth=2.0,
        )
    ax.set_title("Selected glycolytic fluxes")
    ax.set_xlabel("Brodbar storage time (day)")
    ax.set_ylabel("Flux (mM / model-time unit)")
    ax.grid(alpha=0.22)
    ax.legend(ncol=2, frameon=False, fontsize=8)

    ax = axes[0, 1]
    state_colors = {
        "GLC": "#2563eb",
        "G6P": "#d97706",
        "PEP": "#9333ea",
        "PYR": "#be123c",
        "LAC": "#0f766e",
    }
    frame = trajectory[trajectory["candidate"] == reference]
    for metabolite, color in state_colors.items():
        series = frame[frame["metabolite"] == metabolite].sort_values("time_day")
        scale = max(float(series["concentration"].iloc[0]), 0.01)
        ax.plot(
            series["time_day"],
            series["concentration"] / scale,
            label=metabolite,
            color=color,
            linewidth=2.0,
        )
    ax.axhline(1.0, color="#6b7280", linestyle="--", linewidth=1.0)
    ax.set_title("Intracellular pools relative to day 1")
    ax.set_xlabel("Brodbar storage time (day)")
    ax.set_ylabel("Concentration / initial concentration")
    ax.set_yscale("log")
    ax.grid(alpha=0.22)
    ax.legend(ncol=2, frameon=False, fontsize=8)

    ax = axes[1, 0]
    current_flux = flux_summary[
        (flux_summary["candidate"] == reference) & (flux_summary["reaction"].isin(MAIN_FLUXES))
    ].copy()
    order = {reaction: idx for idx, reaction in enumerate(MAIN_FLUXES)}
    current_flux["order"] = current_flux["reaction"].map(order)
    current_flux = current_flux.sort_values("order")
    colors = [palette.get(reaction, "#64748b") for reaction in current_flux["reaction"]]
    ax.bar(current_flux["reaction"], current_flux["mean_abs_flux"], color=colors, edgecolor="#1f2937")
    ax.set_title("Time-weighted mean pathway throughput")
    ax.set_ylabel("Mean absolute flux")
    ax.tick_params(axis="x", rotation=55)
    ax.grid(axis="y", alpha=0.22)

    ax = axes[1, 1]
    pep_routes = flux_summary[
        (flux_summary["candidate"] == reference)
        & (flux_summary["reaction"].isin(("VPK", "VPEP_PASE")))
    ].set_index("reaction")
    route_names = ("VPK", "VPEP_PASE")
    route_values = np.asarray([float(pep_routes.loc[name, "mean_abs_flux"]) for name in route_names])
    route_shares = route_values / max(float(np.sum(route_values)), 1e-12)
    ax.barh(
        route_names,
        route_values,
        color=("#be123c", "#d97706"),
        edgecolor="#334155",
    )
    for index, (value, share) in enumerate(zip(route_values, route_shares)):
        ax.text(value, index, f"  {100.0 * share:.1f}%", va="center", fontsize=9)
    ax.set_title("PEP routing: ATP-producing PK vs phosphatase bypass")
    ax.set_xlabel("Time-weighted mean absolute flux")
    ax.grid(axis="x", alpha=0.22)

    fig.suptitle(
        f"Pre-optimization glycolysis flux profile: {reference}",
        fontsize=15,
        fontweight="bold",
    )
    fig.text(
        0.01,
        0.01,
        "PEP route shares compare ATP-producing VPK with the ADP-independent phosphatase bypass. "
        "The profile is diagnostic and does not establish causal control.",
        fontsize=8,
        color="#374151",
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.96))
    fig.savefig(out_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _plot_candidate_comparison(
    *,
    pool_summary: pd.DataFrame,
    out_path: Path,
) -> None:
    selected = pool_summary[
        pool_summary["pool"].isin(("GLC", "G6P", "F6P", "PEP", "PYR", "LAC"))
    ].copy()
    candidates = list(dict.fromkeys(selected["candidate"].tolist()))
    pools = ("GLC", "G6P", "F6P", "PEP", "PYR", "LAC")
    x = np.arange(len(pools), dtype=float)
    width = 0.8 / max(len(candidates), 1)
    colors = ("#64748b", "#2563eb", "#d97706", "#0f766e")
    fig, ax = plt.subplots(figsize=(12, 5.8))
    for index, candidate in enumerate(candidates):
        values = []
        for pool in pools:
            row = selected[(selected["candidate"] == candidate) & (selected["pool"] == pool)].iloc[0]
            scale = max(abs(float(row["initial_concentration"])), 0.01)
            values.append(float(row["delta_concentration"]) / scale)
        offset = (index - (len(candidates) - 1) / 2.0) * width
        ax.bar(
            x + offset,
            values,
            width=width,
            label=candidate,
            color=colors[index % len(colors)],
            edgecolor="#1f2937",
        )
    ax.axhline(0.0, color="#111827", linewidth=1.0)
    ax.set_xticks(x)
    ax.set_xticklabels(pools)
    ax.set_ylabel("Change from day 1 / initial concentration")
    ax.set_yscale("symlog", linthresh=0.25)
    ax.set_title("Intracellular pool changes across saved hypotheses (signed symlog scale)")
    ax.grid(axis="y", alpha=0.22)
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _format_float(value: Any, digits: int = 3) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "NA"
    if not np.isfinite(number):
        return "NA"
    return f"{number:.{digits}f}"


def _write_report(
    *,
    out_path: Path,
    reference: str,
    recommended_lever: str,
    ranking: pd.DataFrame,
    pool_summary: pd.DataFrame,
    flux_summary: pd.DataFrame,
    kinetic_factors: pd.DataFrame,
    structural_diagnosis: Mapping[str, Any],
    sensitivity: pd.DataFrame,
    max_balance_residual: float,
    max_ode_closure_error: float,
    max_net_flux_closure_error: float,
    t_max: float,
) -> None:
    top = ranking.iloc[0]
    glc = pool_summary[(pool_summary["candidate"] == reference) & (pool_summary["pool"] == "GLC")].iloc[0]
    g6p = pool_summary[(pool_summary["candidate"] == reference) & (pool_summary["pool"] == "G6P")].iloc[0]
    key_fluxes = flux_summary[
        (flux_summary["candidate"] == reference)
        & (flux_summary["reaction"].isin(("VEGLC", "VHK", "VPGI", "VPFK", "VPK", "VLDH", "VELAC")))
    ].set_index("reaction")
    factor_frame = kinetic_factors[kinetic_factors["candidate"] == reference].set_index("kinetic_factor")
    sensitivity_rows = []
    for _, row in sensitivity.iterrows():
        sensitivity_rows.append(
            "| {case} | {atp} | {glc} | {f6p} | {lactate} | {pk_share} | {eglc_error} |".format(
                case=row["case"],
                atp=_format_float(row["ATP_final"], 5),
                glc=_format_float(row["GLC_final"]),
                f6p=_format_float(row["F6P_final"]),
                lactate=_format_float(row["LAC_final"]),
                pk_share=_format_float(row["PEP_to_VPK_share"]),
                eglc_error=_format_float(row["EGLC_endpoint_error"]),
            )
        )
    ranking_rows = []
    for _, row in ranking.head(6).iterrows():
        ranking_rows.append(
            "| {pool} | {lever} | {score} | {imbalance} | {utilization} | {substrate} | {delta} |".format(
                pool=row["pool"],
                lever=row["recommended_parameter"],
                score=_format_float(row["restriction_score"]),
                imbalance=_format_float(row["imbalance_fraction"]),
                utilization=_format_float(row["outlet_utilization"]),
                substrate=_format_float(row["late_substrate_factor"]),
                delta=_format_float(row["delta_concentration"]),
            )
        )

    flux_rows = []
    for reaction in ("VEGLC", "VHK", "VPGI", "VPFK", "VPK", "VLDH", "VELAC"):
        row = key_fluxes.loc[reaction]
        flux_rows.append(
            "| {reaction} | {mean} | {early} | {late} | {fraction} |".format(
                reaction=reaction,
                mean=_format_float(row["mean_flux"]),
                early=_format_float(row["early_mean_flux"]),
                late=_format_float(row["late_mean_flux"]),
                fraction=_format_float(row["mean_abs_flux_over_vmax"]),
            )
        )

    report = f"""# Pre-optimization glycolysis flux diagnostic

## Technical summary

The 46-day Brodbar replay identifies **{top['pool']} accumulation** as the strongest downstream symptom in the current `{reference}` hypothesis. The deeper structural signal is an energy-bypass imbalance: ATP ends at {_format_float(structural_diagnosis['ATP_final'], 5)} mM versus {_format_float(structural_diagnosis['ATP_experimental_final'])} mM experimentally, while {_format_float(100.0 * structural_diagnosis['PEP_to_VPEP_PASE_share'], 1)}% of mean PEP drainage uses `VPEP_PASE` instead of ATP-producing `VPK`.

The recommended single-parameter pre-optimization probe is therefore **`{recommended_lever}` in the `{structural_diagnosis['recommended_direction']}` direction**. This is a diagnostic recommendation, not a promoted calibration result.

Intracellular GLC changes from {_format_float(glc['initial_concentration'])} to {_format_float(glc['final_concentration'])} mM while its mean inflow/outflow imbalance is {_format_float(glc['imbalance_fraction'])}. The downstream {top['pool']} pool has a restriction score of {_format_float(top['restriction_score'])}, an outlet-utilization proxy of {_format_float(top['outlet_utilization'])}, and a concentration change of {_format_float(top['delta_concentration'])} mM.

## The restriction appears downstream of glucose transport

The transport gate supplies enough glucose to reproduce extracellular depletion, but the internal pathway does not maintain matched throughput. The sequence of time-weighted fluxes below shows where throughput drops between glucose entry, phosphorylation, lower glycolysis, pyruvate production, and lactate export.

| Reaction | Mean flux | Early mean | Late mean | Mean abs flux / Vmax |
| --- | ---: | ---: | ---: | ---: |
{chr(10).join(flux_rows)}

## Ranked downstream hypotheses

The restriction score combines positive pool accumulation, mean inflow/outflow imbalance, and utilization of the pool's modeled outlet capacity. GLC itself is excluded from the downstream lever choice because `vmax_VHK` is already fixed at its tested global ceiling in the reference candidate.

| Pool | Single lever | Score | Imbalance fraction | Outlet utilization | Late substrate factor | Delta concentration |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(ranking_rows)}

## Fixed one-factor sensitivity separates symptom from driver

Three deterministic perturbations were replayed without fitting. They compare a direct reduction of the ATP-bypassing PEP phosphatase with increases in the symptomatic `VPFK` step and the ATP-producing `VPK` step.

| Case | ATP final | GLC final | F6P final | LAC final | PEP-to-VPK share | EGLC endpoint error |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(sensitivity_rows)}

## Scope and definitions

- Dataset and horizon: Brodbar, day 1 through day {_format_float(t_max, 0)}.
- Reference hypothesis: `{reference}` (`VEGLC` depletion gate with `vmax_VHK = 5.0` and lowered `km_ATP_HK`).
- Flux source: native `FluxTracker` replay of `equadiff_brodbar`, with `curve_fit_strength = 0.0`.
- Flux units: mM per model-time unit. The Brodbar replay time axis is interpreted as days; legacy ODE comments still contain hour labels.
- Restriction score: descriptive ranking only. It does not prove parameter identifiability or causal control.

## Methodology and robustness checks

Each saved parameter set was reinjected into the pure ODE and solved on the same 46-day grid. Fluxes were then recomputed from every solved state by the same ODE function used during integration. For each glycolytic pool, signed reaction contributions were reconciled against the ODE derivative.

The largest mean absolute instantaneous balance residual was `{_format_float(max_balance_residual, 6)}`. The largest ODE-derivative integral closure error was `{_format_float(max_ode_closure_error, 6)}` mM, while the raw reaction-balance closure error was `{_format_float(max_net_flux_closure_error, 6)}` mM. Differences between the latter two near depleted pools quantify the model's non-negativity damping.

Selected kinetic factors in the reference replay:

- VHK ATP factor, late mean: `{_format_float(factor_frame.loc['VHK_ATP', 'late_mean_factor'])}`.
- VPGI G6P factor, late mean: `{_format_float(factor_frame.loc['VPGI_G6P', 'late_mean_factor'])}`.
- VPK PEP factor, late mean: `{_format_float(factor_frame.loc['VPK_PEP', 'late_mean_factor'])}`.
- VPK ATP-inhibition factor, late mean: `{_format_float(factor_frame.loc['VPK_ATP_inhibition', 'late_mean_factor'])}`.
- VLDH NADH/NAD factor, late mean: `{_format_float(factor_frame.loc['VLDH_NADH_ratio', 'late_mean_factor'])}`.

## Limitations and uncertainty

The score is based on one simulated trajectory and local kinetic occupancy. It does not account for correlated parameter changes, formal control coefficients, or uncertainty in intracellular Brodbar measurements. A high score can therefore indicate a missing reaction, incorrect stoichiometry, or cofactor coupling rather than only an underestimated Vmax.

## Recommended next step

Run a narrow, reversible FLA pass on **`{recommended_lever}` only in the `{structural_diagnosis['recommended_direction']}` direction**, while keeping the mild `VEGLC` feedback structure and `VHK/km_ATP_HK` fixed. Preserve hard guards on the `EGLC` endpoint and slope, `VEGLC` teacher flux, and the `GLC`, `ATP`, `LAC`, `ELAC`, `VELAC`, and `VLDH` trajectories. Do not promote the result until a full Brodbar-panel replay passes.

## Further questions

- Does the selected lever reduce GLC without merely transferring accumulation to the next glycolytic pool?
- Does ATP recovery explain any improvement in VHK throughput?
- Is the intracellular LAC deficit caused by VLDH redox drive, excessive VELAC export, or a missing lactate-retention mechanism?
"""
    out_path.write_text(report, encoding="utf-8")


def run_profile(
    *,
    out_dir: Path,
    candidate_specs: Sequence[str] | None,
    reference_candidate: str,
    t_max: float,
    timepoints: int,
    early_timepoints: int,
    early_window: float,
    method: str,
    rtol: float,
    atol: float,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    candidates = _parse_candidate_specs(candidate_specs)
    if reference_candidate not in candidates:
        raise KeyError(f"Reference candidate {reference_candidate!r} is not in {sorted(candidates)}")
    for path in candidates.values():
        if not path.exists():
            raise FileNotFoundError(path)

    regular_time = np.linspace(1.0, float(t_max), int(timepoints))
    early_span = min(max(float(early_window), 0.0), max(float(t_max) - 1.0, 0.0))
    if int(early_timepoints) > 0 and early_span > 0.0:
        early_offsets = np.geomspace(1e-6, early_span, int(early_timepoints))
        t_eval = np.unique(np.concatenate(([1.0], 1.0 + early_offsets, regular_time)))
    else:
        t_eval = regular_time
    exp_time, exp_curves = _experimental_curves(float(t_max))
    params_by_candidate: dict[str, dict[str, Any]] = {}
    trajectory_rows: list[dict[str, Any]] = []
    flux_rows: list[dict[str, Any]] = []
    pool_rows: list[dict[str, Any]] = []
    flux_summary_rows: list[dict[str, Any]] = []
    kinetic_factor_rows: list[dict[str, Any]] = []
    reference_sol = None
    reference_fluxes: dict[str, np.ndarray] | None = None

    for label, source_path in candidates.items():
        print(f"[profile] simulating {label}: {source_path}", flush=True)
        params = _load_params(source_path)
        params_by_candidate[label] = params
        sol, fluxes, derivatives = _simulate_and_track(
            params=params,
            t_eval=t_eval,
            method=method,
            rtol=rtol,
            atol=atol,
        )
        if label == reference_candidate:
            reference_sol = sol
            reference_fluxes = fluxes
        trajectory_rows.extend(
            _trajectory_rows(
                label=label,
                source_path=source_path,
                sol=sol,
                derivatives=derivatives,
                exp_time=exp_time,
                exp_curves=exp_curves,
            )
        )
        flux_rows.extend(
            _flux_rows(label=label, source_path=source_path, time=sol.t, fluxes=fluxes)
        )
        pool_rows.extend(
            _pool_rows(
                label=label,
                source_path=source_path,
                sol=sol,
                fluxes=fluxes,
                derivatives=derivatives,
            )
        )
        flux_summary_rows.extend(
            summarize_fluxes(label=label, time=sol.t, fluxes=fluxes, params=params)
        )
        kinetic_factor_rows.extend(_kinetic_factor_rows(candidate=label, sol=sol, params=params))

    trajectory = pd.DataFrame(trajectory_rows)
    flux_timeseries = pd.DataFrame(flux_rows)
    pool_timeseries = pd.DataFrame(pool_rows)
    flux_summary = pd.DataFrame(flux_summary_rows)
    kinetic_factors = pd.DataFrame(kinetic_factor_rows)
    pool_summary = summarize_pools(
        pool_timeseries=pool_timeseries,
        flux_summary=flux_summary,
        params_by_candidate=params_by_candidate,
        exp_time=exp_time,
        exp_curves=exp_curves,
    )
    symptom_lever, ranking = select_downstream_lever(
        pool_summary,
        kinetic_factors,
        reference_candidate,
    )
    structural_diagnosis = diagnose_structural_lever(
        symptom_lever=symptom_lever,
        reference=reference_candidate,
        trajectory=trajectory,
        flux_summary=flux_summary,
    )
    if reference_sol is None or reference_fluxes is None:
        raise RuntimeError(f"Reference simulation {reference_candidate!r} was not retained")
    sensitivity = run_fixed_sensitivity_probes(
        reference_params=params_by_candidate[reference_candidate],
        reference_sol=reference_sol,
        reference_fluxes=reference_fluxes,
        t_eval=t_eval,
        exp_time=exp_time,
        exp_curves=exp_curves,
        method=method,
        rtol=rtol,
        atol=atol,
    )
    recommended_lever = str(structural_diagnosis["recommended_parameter"])

    paths = {
        "trajectory_csv": out_dir / "glycolysis_state_trajectories.csv",
        "flux_timeseries_csv": out_dir / "glycolysis_flux_timeseries.csv",
        "pool_timeseries_csv": out_dir / "glycolysis_pool_balances.csv",
        "flux_summary_csv": out_dir / "glycolysis_flux_summary.csv",
        "pool_summary_csv": out_dir / "glycolysis_pool_summary.csv",
        "kinetic_factors_csv": out_dir / "glycolysis_kinetic_factors.csv",
        "ranking_csv": out_dir / "downstream_bottleneck_ranking.csv",
        "sensitivity_csv": out_dir / "fixed_one_factor_sensitivity.csv",
        "profile_png": out_dir / "glycolysis_flux_profile.png",
        "comparison_png": out_dir / "glycolysis_candidate_comparison.png",
        "report_md": out_dir / "preoptimization_flux_diagnostic_report.md",
        "summary_json": out_dir / "summary.json",
    }
    trajectory.to_csv(paths["trajectory_csv"], index=False)
    flux_timeseries.to_csv(paths["flux_timeseries_csv"], index=False)
    pool_timeseries.to_csv(paths["pool_timeseries_csv"], index=False)
    flux_summary.to_csv(paths["flux_summary_csv"], index=False)
    pool_summary.to_csv(paths["pool_summary_csv"], index=False)
    kinetic_factors.to_csv(paths["kinetic_factors_csv"], index=False)
    ranking.to_csv(paths["ranking_csv"], index=False)
    sensitivity.to_csv(paths["sensitivity_csv"], index=False)

    _plot_profile(
        trajectory=trajectory,
        flux_timeseries=flux_timeseries,
        flux_summary=flux_summary,
        pool_summary=pool_summary,
        ranking=ranking,
        reference=reference_candidate,
        out_path=paths["profile_png"],
    )
    _plot_candidate_comparison(pool_summary=pool_summary, out_path=paths["comparison_png"])

    max_balance_residual = float(pool_summary["mean_abs_balance_residual"].max())
    max_ode_closure_error = float(np.max(np.abs(pool_summary["ode_closure_error"])))
    max_net_flux_closure_error = float(np.max(np.abs(pool_summary["net_flux_closure_error"])))
    _write_report(
        out_path=paths["report_md"],
        reference=reference_candidate,
        recommended_lever=recommended_lever,
        ranking=ranking,
        pool_summary=pool_summary,
        flux_summary=flux_summary,
        kinetic_factors=kinetic_factors,
        structural_diagnosis=structural_diagnosis,
        sensitivity=sensitivity,
        max_balance_residual=max_balance_residual,
        max_ode_closure_error=max_ode_closure_error,
        max_net_flux_closure_error=max_net_flux_closure_error,
        t_max=t_max,
    )

    summary = {
        "contract_type": "fla_preoptimization_glycolysis_flux_profile",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "optimization_performed": False,
        "parameters_promoted": False,
        "t_max": float(t_max),
        "timepoints": int(t_eval.size),
        "regular_timepoints": int(timepoints),
        "early_timepoints": int(early_timepoints),
        "early_window": float(early_span),
        "reference_candidate": reference_candidate,
        "candidate_params": {label: str(path) for label, path in candidates.items()},
        "recommended_single_downstream_lever": recommended_lever,
        "recommended_direction": structural_diagnosis["recommended_direction"],
        "mechanistic_diagnosis": structural_diagnosis,
        "fixed_one_factor_sensitivity": sensitivity.to_dict(orient="records"),
        "top_ranked_pool": str(ranking.iloc[0]["pool"]),
        "top_restriction_score": float(ranking.iloc[0]["restriction_score"]),
        "max_mean_abs_balance_residual": max_balance_residual,
        "max_abs_ode_closure_error": max_ode_closure_error,
        "max_abs_net_flux_closure_error": max_net_flux_closure_error,
        "top_ranking": ranking.head(6).to_dict(orient="records"),
        "artifact_paths": {name: str(path) for name, path in paths.items()},
    }
    paths["summary_json"].write_text(json.dumps(_jsonable(summary), indent=2), encoding="utf-8")
    print(json.dumps(_jsonable(summary), indent=2), flush=True)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Profile Brodbar glycolysis flux bottlenecks before FLA optimization."
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--candidate",
        action="append",
        dest="candidate_specs",
        help="Candidate label=path. Repeat to compare multiple saved parameter sets.",
    )
    parser.add_argument("--reference-candidate", default=REFERENCE_CANDIDATE)
    parser.add_argument("--t-max", type=float, default=46.0)
    parser.add_argument("--timepoints", type=int, default=181)
    parser.add_argument("--early-timepoints", type=int, default=80)
    parser.add_argument("--early-window", type=float, default=1.0)
    parser.add_argument("--method", default="LSODA")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_profile(
        out_dir=args.out_dir,
        candidate_specs=args.candidate_specs,
        reference_candidate=args.reference_candidate,
        t_max=args.t_max,
        timepoints=args.timepoints,
        early_timepoints=args.early_timepoints,
        early_window=args.early_window,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
    )


if __name__ == "__main__":
    main()
