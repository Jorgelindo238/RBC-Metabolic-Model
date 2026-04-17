"""
Teacher-flux workbench for hybrid kinetics distillation.

This module does three things for a small set of reactions:
1. Build dense pure-fit teacher curves directly from experimental data.
2. Convert those teacher curves into explicit reaction-flux targets.
3. Distill simple MM / Hill-style kinetics against the recovered teacher flux.
"""

from __future__ import annotations

import argparse
import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator
from scipy.optimize import least_squares


_THIS_FILE = Path(__file__).resolve()
_SRC_DIR = _THIS_FILE.parent
_ROOT_DIR = _SRC_DIR.parent
_DATA_FILE = _SRC_DIR / "Data_Bordbar_et_al_exp.xlsx"
_DEFAULT_OUTPUT_ROOT = _ROOT_DIR / "Simulations" / "brodbar" / "hermes" / "teacher_flux"

_METABOLITE_TO_REACTION = {
    "EGLC": "VEGLC",
    "ELAC": "VELAC",
}

_REACTION_TO_SIGN = {
    "VEGLC": -1.0,  # dxdt[EGLC] = -VEGLC
    "VELAC": 1.0,   # dxdt[ELAC] = +VELAC
}

_BALANCE_REACTION_RULES = {
    "LAC": {
        "reaction": "VLDH",
        "auxiliary_reaction": "VELAC",
        "derivative_scale": 1.0,   # dxdt[LAC] = VLDH - VELAC
        "auxiliary_scale": 1.0,
    },
}


def mm(value: np.ndarray, km: float, hill_coef: float = 1.0) -> np.ndarray:
    value = np.maximum(np.asarray(value, dtype=float), 0.0)
    km = max(float(km), 1e-9)
    hill_coef = max(float(hill_coef), 1e-6)
    if abs(hill_coef - 1.0) < 1e-12:
        return value / (km + value)
    value_pow = np.power(value, hill_coef)
    km_pow = km ** hill_coef
    return value_pow / (km_pow + value_pow)


def _load_sheet1(data_path: Path = _DATA_FILE) -> Tuple[np.ndarray, pd.DataFrame]:
    df = pd.read_excel(data_path, sheet_name="Sheet1")
    if "Conc / mM" not in df.columns:
        raise ValueError(f"Unsupported experimental sheet format in {data_path}")
    time_cols = [col for col in df.columns if col != "Conc / mM"]
    timepoints = np.asarray([float(col) for col in time_cols], dtype=float)
    return timepoints, df


def extract_experimental_curve(metabolite_name: str, data_path: Path = _DATA_FILE) -> Dict[str, object]:
    timepoints, df = _load_sheet1(data_path)
    row = df[df["Conc / mM"].astype(str).str.upper() == metabolite_name.upper()]
    if row.empty:
        raise KeyError(f"Metabolite {metabolite_name} not found in {data_path}")
    values = row.iloc[0, 1:].to_numpy(dtype=float)
    return {
        "metabolite": metabolite_name.upper(),
        "timepoints": timepoints.tolist(),
        "values": values.tolist(),
    }


def _load_auxiliary_flux_series(flux_csv_path: Path, reaction_name: str) -> Tuple[np.ndarray, np.ndarray]:
    flux_df = pd.read_csv(flux_csv_path)
    time_col = _detect_time_column(flux_df)
    if reaction_name not in flux_df.columns:
        raise KeyError(f"Reaction {reaction_name} not found in auxiliary flux file {flux_csv_path}")
    return (
        flux_df[time_col].to_numpy(dtype=float),
        flux_df[reaction_name].to_numpy(dtype=float),
    )


def build_teacher_flux_dataset(
    metabolite_names: Iterable[str] = ("EGLC", "ELAC"),
    *,
    dense_points: int = 200,
    data_path: Path = _DATA_FILE,
    auxiliary_flux_csv_path: Path | None = None,
    out_path: Path | None = None,
) -> Dict[str, object]:
    metabolite_names = [name.upper() for name in metabolite_names]
    timepoints, _ = _load_sheet1(data_path)
    dense_timepoints = np.linspace(float(timepoints[0]), float(timepoints[-1]), int(dense_points))

    teacher_curves: Dict[str, Dict[str, object]] = {}
    reaction_flux_curves: Dict[str, Dict[str, object]] = {}

    for metabolite_name in metabolite_names:
        curve = extract_experimental_curve(metabolite_name, data_path=data_path)
        pchip = PchipInterpolator(np.asarray(curve["timepoints"], dtype=float), np.asarray(curve["values"], dtype=float))
        dense_values = pchip(dense_timepoints)
        dense_derivative = pchip.derivative()(dense_timepoints)

        teacher_curves[metabolite_name] = {
            "source": "experimental_pchip",
            "timepoints": curve["timepoints"],
            "values": curve["values"],
            "dense_values": dense_values.tolist(),
            "dense_derivative": dense_derivative.tolist(),
        }

        reaction_name = _METABOLITE_TO_REACTION.get(metabolite_name)
        if reaction_name is not None:
            flux_values = _REACTION_TO_SIGN[reaction_name] * dense_derivative
            reaction_flux_curves[reaction_name] = {
                "source_metabolite": metabolite_name,
                "source": "experimental_pchip_derivative",
                "dense_values": flux_values.tolist(),
            }

        balance_rule = _BALANCE_REACTION_RULES.get(metabolite_name)
        if balance_rule is not None:
            if auxiliary_flux_csv_path is None:
                raise ValueError(
                    f"Metabolite {metabolite_name} requires auxiliary_flux_csv_path to reconstruct "
                    f"{balance_rule['reaction']} teacher flux"
                )
            aux_time, aux_values = _load_auxiliary_flux_series(
                Path(auxiliary_flux_csv_path),
                str(balance_rule["auxiliary_reaction"]),
            )
            aux_interp = np.interp(dense_timepoints, aux_time, aux_values)
            flux_values = (
                float(balance_rule["derivative_scale"]) * dense_derivative
                + float(balance_rule["auxiliary_scale"]) * aux_interp
            )
            reaction_flux_curves[str(balance_rule["reaction"])] = {
                "source_metabolite": metabolite_name,
                "source": "experimental_pchip_balance_reconstruction",
                "auxiliary_flux_csv_path": str(auxiliary_flux_csv_path),
                "auxiliary_reaction": str(balance_rule["auxiliary_reaction"]),
                "dense_values": flux_values.tolist(),
            }

    payload = {
        "contract_type": "teacher_flux_dataset",
        "contract_version": 1,
        "dataset_label": "teacher_flux_" + "_".join(name.lower() for name in metabolite_names),
        "data_path": str(data_path),
        "auxiliary_flux_csv_path": str(auxiliary_flux_csv_path) if auxiliary_flux_csv_path is not None else None,
        "target_metabolites": metabolite_names,
        "dense_timepoints": dense_timepoints.tolist(),
        "teacher_curves": teacher_curves,
        "reaction_flux_curves": reaction_flux_curves,
    }

    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        plot_teacher_flux_dataset(payload, out_path.with_suffix(".png"))

    return payload


@lru_cache(maxsize=16)
def load_teacher_flux_dataset(dataset_path: str | Path) -> Dict[str, object]:
    dataset_path = Path(dataset_path)
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    if payload.get("contract_type") != "teacher_flux_dataset":
        raise ValueError(f"Unsupported teacher flux dataset: {dataset_path}")
    payload["_dataset_path"] = str(dataset_path)
    return payload


def evaluate_teacher_flux_at_time(dataset: Dict[str, object], reaction_name: str, t: float) -> float:
    reaction_curves = dataset.get("reaction_flux_curves", {})
    curve = reaction_curves.get(reaction_name)
    if not isinstance(curve, dict):
        raise KeyError(f"Reaction {reaction_name} not present in teacher flux dataset")
    dense_timepoints = np.asarray(dataset["dense_timepoints"], dtype=float)
    dense_values = np.asarray(curve["dense_values"], dtype=float)
    clipped_t = float(np.clip(float(t), dense_timepoints[0], dense_timepoints[-1]))
    return float(np.interp(clipped_t, dense_timepoints, dense_values))


def plot_teacher_flux_dataset(dataset: Dict[str, object], plot_path: Path) -> None:
    dense_timepoints = np.asarray(dataset["dense_timepoints"], dtype=float)
    teacher_curves = dataset.get("teacher_curves", {})
    reaction_flux_curves = dataset.get("reaction_flux_curves", {})

    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    axes = axes.flatten()

    for idx, metabolite_name in enumerate(dataset.get("target_metabolites", [])):
        curve = teacher_curves.get(metabolite_name, {})
        if idx >= len(axes):
            break
        ax = axes[idx]
        ax.plot(curve.get("timepoints", []), curve.get("values", []), "o", label=f"{metabolite_name} experimental")
        ax.plot(dense_timepoints, curve.get("dense_values", []), "-", label=f"{metabolite_name} teacher fit")
        reaction_name = _METABOLITE_TO_REACTION.get(metabolite_name)
        if reaction_name in reaction_flux_curves:
            ax2 = ax.twinx()
            ax2.plot(dense_timepoints, reaction_flux_curves[reaction_name].get("dense_values", []), "--", color="tab:red", label=f"{reaction_name} teacher flux")
            ax2.set_ylabel("flux")
        ax.set_title(metabolite_name)
        ax.set_xlabel("time (days)")
        ax.set_ylabel("concentration")
        ax.legend(loc="upper right", fontsize=8)

    plot_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)


def write_teacher_override_params(
    seed_params_path: Path,
    dataset_path: Path,
    out_path: Path,
    reactions: Iterable[str] = ("VEGLC", "VELAC"),
) -> Dict[str, object]:
    seed_params = json.loads(Path(seed_params_path).read_text(encoding="utf-8"))
    seed_params["teacher_flux_dataset_path"] = str(dataset_path)
    for reaction_name in reactions:
        seed_params[f"kinetic_family_{reaction_name}"] = "teacher_curve_flux"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(seed_params, indent=2), encoding="utf-8")
    return seed_params


def _detect_time_column(df: pd.DataFrame) -> str:
    for candidate in ("time", "Time", "Time (days)", "Time (hours)"):
        if candidate in df.columns:
            return candidate
    return str(df.columns[0])


def _align_states_to_flux_times(state_df: pd.DataFrame, flux_df: pd.DataFrame, state_names: Iterable[str]) -> Dict[str, np.ndarray]:
    state_time = state_df[_detect_time_column(state_df)].to_numpy(dtype=float)
    flux_time = flux_df[_detect_time_column(flux_df)].to_numpy(dtype=float)
    aligned = {}
    for name in state_names:
        aligned[name] = np.interp(flux_time, state_time, state_df[name].to_numpy(dtype=float))
    aligned["time"] = flux_time
    return aligned


def _fit_candidate_model(
    target_flux: np.ndarray,
    predict_fn,
    x0: np.ndarray,
    lower_bounds: np.ndarray,
    upper_bounds: np.ndarray,
) -> Dict[str, object]:
    result = least_squares(
        lambda params: predict_fn(params) - target_flux,
        x0=x0,
        bounds=(lower_bounds, upper_bounds),
        max_nfev=5000,
    )
    fitted = predict_fn(result.x)
    rmse = float(np.sqrt(np.mean((fitted - target_flux) ** 2)))
    norm = float(max(np.mean(np.abs(target_flux)), 1e-6))
    return {
        "success": bool(result.success),
        "rmse": rmse,
        "nrmse": float(rmse / norm),
        "params": [float(x) for x in result.x],
        "message": result.message,
        "predicted_flux": fitted.tolist(),
    }


def distill_teacher_flux_kinetics(
    *,
    state_csv_path: Path,
    flux_csv_path: Path,
    out_dir: Path,
    base_params_path: Path | None = None,
) -> Dict[str, object]:
    state_df = pd.read_csv(state_csv_path)
    flux_df = pd.read_csv(flux_csv_path)
    state_time_col = _detect_time_column(state_df)
    flux_time_col = _detect_time_column(flux_df)

    aligned = _align_states_to_flux_times(state_df, flux_df, ["GLC", "EGLC", "LAC", "ELAC", "PYR", "NAD", "NADH"])
    report = {
        "contract_type": "teacher_flux_distillation_report",
        "contract_version": 1,
        "state_csv_path": str(state_csv_path),
        "flux_csv_path": str(flux_csv_path),
        "reactions": {},
    }

    # VEGLC candidates
    veglc_target = flux_df["VEGLC"].to_numpy(dtype=float)
    eglc = aligned["EGLC"]
    glc = aligned["GLC"]

    def veglc_mm_bidirectional(params: np.ndarray) -> np.ndarray:
        vmax, km_eglc, km_glc = params
        return vmax * (mm(eglc, km_eglc) - mm(glc, km_glc))

    def veglc_hill_transport(params: np.ndarray) -> np.ndarray:
        vmax, km_eglc, km_glc, h_imp, h_exp, reverse_scale = params
        return vmax * (mm(eglc, km_eglc, h_imp) - reverse_scale * mm(glc, km_glc, h_exp))

    veglc_candidates = {
        "mm_bidirectional": _fit_candidate_model(
            veglc_target,
            veglc_mm_bidirectional,
            np.asarray([1.0, 25.0, 1.0], dtype=float),
            np.asarray([1e-6, 0.1, 1e-3], dtype=float),
            np.asarray([10.0, 120.0, 20.0], dtype=float),
        ),
        "hybrid_asymmetric_transport": _fit_candidate_model(
            veglc_target,
            veglc_hill_transport,
            np.asarray([1.0, 25.0, 1.0, 1.0, 1.0, 1.0], dtype=float),
            np.asarray([1e-6, 0.1, 1e-3, 0.5, 0.5, 0.0], dtype=float),
            np.asarray([10.0, 120.0, 20.0, 5.0, 5.0, 3.0], dtype=float),
        ),
    }
    veglc_best_name = min(veglc_candidates, key=lambda name: veglc_candidates[name]["nrmse"])
    report["reactions"]["VEGLC"] = {
        "best_family": veglc_best_name,
        "candidates": veglc_candidates,
        "recommended_params": {
            "kinetic_family_VEGLC": veglc_best_name,
            **(
                {
                    "vmax_VEGLC": veglc_candidates[veglc_best_name]["params"][0],
                    "km_EGLC": veglc_candidates[veglc_best_name]["params"][1],
                    "km_GLC_transport": veglc_candidates[veglc_best_name]["params"][2],
                }
                if veglc_best_name == "mm_bidirectional"
                else {
                    "kinetic_family_VEGLC": "hybrid_asymmetric_transport",
                    "vmax_VEGLC": veglc_candidates[veglc_best_name]["params"][0],
                    "km_EGLC": veglc_candidates[veglc_best_name]["params"][1],
                    "km_GLC_transport": veglc_candidates[veglc_best_name]["params"][2],
                    "hybrid_import_hill_VEGLC": veglc_candidates[veglc_best_name]["params"][3],
                    "hybrid_export_hill_VEGLC": veglc_candidates[veglc_best_name]["params"][4],
                    "hybrid_reverse_scale_VEGLC": veglc_candidates[veglc_best_name]["params"][5],
                    "hybrid_blend_VEGLC": 1.0,
                }
            ),
        },
    }

    # VELAC candidates
    velac_target = flux_df["VELAC"].to_numpy(dtype=float)
    lac = aligned["LAC"]
    elac = aligned["ELAC"]

    def velac_mm_efflux(params: np.ndarray) -> np.ndarray:
        vmax, km_lac = params
        return vmax * mm(lac, km_lac)

    def velac_hybrid_reversible(params: np.ndarray) -> np.ndarray:
        vmax, km_lac, km_elac, h_eff, h_back, back_scale, retention_strength, retention_hill, retention_scale = params
        retention_guard = 1.0 - retention_strength + retention_strength * mm(
            lac,
            max(km_lac * retention_scale, 1e-6),
            retention_hill,
        )
        return vmax * (
            mm(lac, km_lac, h_eff) * retention_guard
            - back_scale * mm(elac, km_elac, h_back)
        )

    velac_candidates = {
        "mm_efflux": _fit_candidate_model(
            velac_target,
            velac_mm_efflux,
            np.asarray([1.0, 20.0], dtype=float),
            np.asarray([1e-6, 0.1], dtype=float),
            np.asarray([20.0, 150.0], dtype=float),
        ),
        "hybrid_reversible_transport": _fit_candidate_model(
            velac_target,
            velac_hybrid_reversible,
            np.asarray([1.0, 20.0, 20.0, 1.0, 1.0, 0.1, 0.1, 1.0, 1.0], dtype=float),
            np.asarray([1e-6, 0.1, 0.1, 0.5, 0.5, 0.0, 0.0, 0.5, 0.25], dtype=float),
            np.asarray([20.0, 150.0, 150.0, 5.0, 5.0, 2.0, 1.0, 5.0, 2.0], dtype=float),
        ),
    }
    velac_best_name = min(velac_candidates, key=lambda name: velac_candidates[name]["nrmse"])
    report["reactions"]["VELAC"] = {
        "best_family": velac_best_name,
        "candidates": velac_candidates,
        "recommended_params": (
            {
                "kinetic_family_VELAC": "mm_efflux",
                "vmax_VELAC": velac_candidates[velac_best_name]["params"][0],
                "km_LAC": velac_candidates[velac_best_name]["params"][1],
            }
            if velac_best_name == "mm_efflux"
            else {
                "kinetic_family_VELAC": "hybrid_reversible_transport",
                "vmax_VELAC": velac_candidates[velac_best_name]["params"][0],
                "km_LAC": velac_candidates[velac_best_name]["params"][1],
                "hybrid_km_ELAC": velac_candidates[velac_best_name]["params"][2],
                "hybrid_efflux_hill_VELAC": velac_candidates[velac_best_name]["params"][3],
                "hybrid_backpressure_hill_VELAC": velac_candidates[velac_best_name]["params"][4],
                "hybrid_backpressure_scale_VELAC": velac_candidates[velac_best_name]["params"][5],
                "hybrid_lac_retention_strength_VELAC": velac_candidates[velac_best_name]["params"][6],
                "hybrid_lac_retention_hill_VELAC": velac_candidates[velac_best_name]["params"][7],
                "hybrid_lac_retention_km_scale_VELAC": velac_candidates[velac_best_name]["params"][8],
                "hybrid_blend_VELAC": 1.0,
            }
        ),
    }

    # VLDH candidates
    vldh_target = flux_df["VLDH"].to_numpy(dtype=float)
    pyr = aligned["PYR"]
    lac = aligned["LAC"]
    nad = aligned["NAD"]
    nadh = aligned["NADH"]
    nadh_ratio = np.maximum(nadh / (nad + 1e-6), 0.0)
    nad_ratio = np.maximum(nad / (nadh + 1e-6), 0.0)

    def vldh_mm_forward(params: np.ndarray) -> np.ndarray:
        vmax, km_pyr, km_nadh_nad = params
        return vmax * mm(pyr, km_pyr) * mm(nadh_ratio, km_nadh_nad)

    def vldh_hybrid_reversible(params: np.ndarray) -> np.ndarray:
        vmax, km_pyr, km_lac, km_nadh_nad, km_nad_nadh, h_fwd, h_rev, reverse_scale = params
        return vmax * (
            mm(pyr, km_pyr, h_fwd) * mm(nadh_ratio, km_nadh_nad)
            - reverse_scale * mm(lac, km_lac, h_rev) * mm(nad_ratio, km_nad_nadh)
        )

    vldh_candidates = {
        "mm_forward": _fit_candidate_model(
            vldh_target,
            vldh_mm_forward,
            np.asarray([0.5, 0.5, 1.0], dtype=float),
            np.asarray([1e-6, 1e-3, 1e-3], dtype=float),
            np.asarray([20.0, 20.0, 20.0], dtype=float),
        ),
        "hybrid_reversible_redox": _fit_candidate_model(
            vldh_target,
            vldh_hybrid_reversible,
            np.asarray([0.5, 0.5, 1.0, 1.0, 1.0, 1.0, 1.0, 0.1], dtype=float),
            np.asarray([1e-6, 1e-3, 1e-3, 1e-3, 1e-3, 0.5, 0.5, 0.0], dtype=float),
            np.asarray([20.0, 20.0, 200.0, 20.0, 20.0, 5.0, 5.0, 3.0], dtype=float),
        ),
    }
    vldh_best_name = min(vldh_candidates, key=lambda name: vldh_candidates[name]["nrmse"])
    report["reactions"]["VLDH"] = {
        "best_family": vldh_best_name,
        "candidates": vldh_candidates,
        "recommended_params": (
            {
                "kinetic_family_VLDH": "mm_forward",
                "vmax_VLDH": vldh_candidates[vldh_best_name]["params"][0],
                "km_PYR": vldh_candidates[vldh_best_name]["params"][1],
                "km_NADH_NAD": vldh_candidates[vldh_best_name]["params"][2],
            }
            if vldh_best_name == "mm_forward"
            else {
                "kinetic_family_VLDH": "hybrid_reversible_redox",
                "vmax_VLDH": vldh_candidates[vldh_best_name]["params"][0],
                "km_PYR": vldh_candidates[vldh_best_name]["params"][1],
                "km_LAC": vldh_candidates[vldh_best_name]["params"][2],
                "km_NADH_NAD": vldh_candidates[vldh_best_name]["params"][3],
                "km_NAD_NADH": vldh_candidates[vldh_best_name]["params"][4],
                "hybrid_forward_hill_VLDH": vldh_candidates[vldh_best_name]["params"][5],
                "hybrid_reverse_hill_VLDH": vldh_candidates[vldh_best_name]["params"][6],
                "hybrid_reverse_scale_VLDH": vldh_candidates[vldh_best_name]["params"][7],
                "hybrid_blend_VLDH": 1.0,
            }
        ),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "teacher_flux_distillation_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if base_params_path is not None:
        base_params = json.loads(Path(base_params_path).read_text(encoding="utf-8"))
        recommended_params = dict(base_params)
        for reaction_payload in report["reactions"].values():
            recommended_params.update(reaction_payload.get("recommended_params", {}))
        (out_dir / "teacher_flux_recommended_params.json").write_text(
            json.dumps(recommended_params, indent=2),
            encoding="utf-8",
        )

    # Comparison plot
    fig, axes = plt.subplots(3, 1, figsize=(12, 11), constrained_layout=True)
    axes[0].plot(aligned["time"], veglc_target, label="VEGLC teacher flux", linewidth=2)
    for name, candidate in veglc_candidates.items():
        axes[0].plot(aligned["time"], candidate["predicted_flux"], "--", label=f"VEGLC {name}")
    axes[0].set_title("VEGLC flux distillation")
    axes[0].set_xlabel(flux_time_col)
    axes[0].set_ylabel("flux")
    axes[0].legend(fontsize=8)

    axes[1].plot(aligned["time"], velac_target, label="VELAC teacher flux", linewidth=2)
    for name, candidate in velac_candidates.items():
        axes[1].plot(aligned["time"], candidate["predicted_flux"], "--", label=f"VELAC {name}")
    axes[1].set_title("VELAC flux distillation")
    axes[1].set_xlabel(flux_time_col)
    axes[1].set_ylabel("flux")
    axes[1].legend(fontsize=8)

    axes[2].plot(aligned["time"], vldh_target, label="VLDH teacher flux", linewidth=2)
    for name, candidate in vldh_candidates.items():
        axes[2].plot(aligned["time"], candidate["predicted_flux"], "--", label=f"VLDH {name}")
    axes[2].set_title("VLDH flux distillation")
    axes[2].set_xlabel(flux_time_col)
    axes[2].set_ylabel("flux")
    axes[2].legend(fontsize=8)

    fig.savefig(out_dir / "teacher_flux_distillation_compare.png", dpi=150)
    plt.close(fig)

    return report


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Teacher-flux builder and distillation workbench")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build-dataset", help="Build a pure-fit teacher flux dataset from experimental curves")
    build_parser.add_argument("--metabolites", default="EGLC,ELAC")
    build_parser.add_argument("--dense-points", type=int, default=200)
    build_parser.add_argument("--out", required=True)

    params_parser = subparsers.add_parser("make-params", help="Create a params JSON that replaces VEGLC/VELAC kinetics with teacher fluxes")
    params_parser.add_argument("--seed-params", required=True)
    params_parser.add_argument("--dataset", required=True)
    params_parser.add_argument("--out", required=True)
    params_parser.add_argument("--reactions", default="VEGLC,VELAC")

    distill_parser = subparsers.add_parser("distill", help="Fit MM/Hill kinetics against teacher flux traces")
    distill_parser.add_argument("--states", required=True)
    distill_parser.add_argument("--fluxes", required=True)
    distill_parser.add_argument("--out-dir", required=True)
    distill_parser.add_argument("--base-params")

    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    if args.command == "build-dataset":
        metabolites = [name.strip() for name in args.metabolites.split(",") if name.strip()]
        payload = build_teacher_flux_dataset(
            metabolites,
            dense_points=args.dense_points,
            out_path=Path(args.out),
        )
        print(json.dumps({
            "dataset_label": payload["dataset_label"],
            "out_path": args.out,
            "targets": payload["target_metabolites"],
        }, indent=2))
        return

    if args.command == "make-params":
        reactions = [name.strip() for name in args.reactions.split(",") if name.strip()]
        payload = write_teacher_override_params(
            Path(args.seed_params),
            Path(args.dataset),
            Path(args.out),
            reactions=reactions,
        )
        print(json.dumps({
            "out_path": args.out,
            "reactions": reactions,
            "teacher_flux_dataset_path": payload["teacher_flux_dataset_path"],
        }, indent=2))
        return

    if args.command == "distill":
        report = distill_teacher_flux_kinetics(
            state_csv_path=Path(args.states),
            flux_csv_path=Path(args.fluxes),
            out_dir=Path(args.out_dir),
            base_params_path=Path(args.base_params) if args.base_params else None,
        )
        print(json.dumps({
            "out_dir": args.out_dir,
            "best_families": {name: payload["best_family"] for name, payload in report["reactions"].items()},
        }, indent=2))
        return


if __name__ == "__main__":
    main()
