"""Build a reproducible technical state audit of the RBC model and FLA workflow."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
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
DEFAULT_SEED_PARAMS = (
    ROOT
    / "Simulations"
    / "brodbar"
    / "hermes"
    / "vpep_vpk_coupled_mild_feedback_46d_n20"
    / "seed_fixed_params.json"
)
DEFAULT_OUT_DIR = ROOT / "output" / "model_fla_state_audit_2026_08_11"
BRODBAR_DATA = SRC_DIR / "Data_Bordbar_et_al_exp.xlsx"
HISTORICAL_INITIALS = SRC_DIR / "Initial_conditions_JA_Final.xls"
CANDIDATE_COMPARISON = ROOT / "output" / "fla_candidate_comparison" / "fla_candidate_comparison.csv"

for path in (str(ROOT), str(SRC_DIR), str(SCRIPT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import rbc_stoichiometry as STOICH  # noqa: E402
from equadiff_brodbar import (  # noqa: E402
    BRODBAR_METABOLITE_MAP,
    MODEL_NETWORK_VERSION,
    NUM_BASE_METABOLITES,
)
from MM_calibration import EXP_TO_MODEL, load_initial_conditions  # noqa: E402
from parse_initial_conditions import build_initial_conditions  # noqa: E402
from evaluate_brodbar_candidate_full_panel import (  # noqa: E402
    _load_brodbar_panel,
    _load_params,
    _nrmse,
    _simulate,
)


CASE_LEGACY = "legacy_network__legacy_initialization"
CASE_SAM = "corrected_SAM__legacy_initialization"
CASE_STRICT = "corrected_SAM__strict_historical_initialization"
SELECTED_METABOLITES = (
    "EGLC",
    "GLC",
    "G6P",
    "F6P",
    "ATP",
    "B23PG",
    "PEP",
    "LAC",
    "ELAC",
)
NON_INDEPENDENT_OBSERVATIONS = {"B13PG", "P2G"}


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
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _metabolite_order() -> list[str]:
    names = [""] * (NUM_BASE_METABOLITES + 1)
    for name, index in BRODBAR_METABOLITE_MAP.items():
        if index < len(names):
            names[index] = name
    return names


def _duplicate_experimental_rows() -> list[dict[str, Any]]:
    raw = pd.read_excel(BRODBAR_DATA, engine="openpyxl")
    names = raw.iloc[:, 0].astype(str).str.strip().str.upper().tolist()
    values = raw.iloc[:, 1:].to_numpy(dtype=float)
    duplicates = []
    for left in range(len(names)):
        for right in range(left + 1, len(names)):
            if np.allclose(values[left], values[right], rtol=0.0, atol=0.0):
                duplicates.append(
                    {
                        "left": names[left],
                        "right": names[right],
                        "maximum_absolute_difference": 0.0,
                    }
                )
    return duplicates


def _initialization_inventory() -> dict[str, Any]:
    metabolites = _metabolite_order()
    inventory: dict[str, Any] = {}
    for policy in (
        "legacy_experimental_alias",
        "compartment_strict_generic",
        "compartment_strict_historical",
    ):
        values, provenance = build_initial_conditions(
            metabolites,
            HISTORICAL_INITIALS,
            initialization_policy=policy,
        )
        counts = Counter(provenance.values())
        inventory[policy] = {
            "source_counts": dict(sorted(counts.items())),
            "compartment_aliases": {
                metabolite: source
                for metabolite, source in provenance.items()
                if source.startswith("legacy_compartment_alias")
            },
            "generic_states": sorted(
                metabolite
                for metabolite, source in provenance.items()
                if source == "generic_1mM"
            ),
            "minimum_initial_value_mM": float(np.min(values)),
            "maximum_initial_value_mM": float(np.max(values)),
        }
    return inventory


def _model_inventory() -> dict[str, Any]:
    connected = set(STOICH.ALL_METABOLITES)
    states = [name for name in _metabolite_order() if name]
    consistency_errors = STOICH.validate_consistency(STOICH.KNOWN_PARAM_UNIVERSE)
    return {
        "dynamic_state_count": len(states),
        "base_metabolite_count": int(NUM_BASE_METABOLITES),
        "measured_row_count": 55,
        "supported_calibration_target_count": len(EXP_TO_MODEL),
        "stoichiometric_reaction_count": len(STOICH.STOICHIOMETRY),
        "reaction_or_rate_count": len(STOICH.ALL_REACTIONS),
        "injectable_parameter_count": len(STOICH.ALL_PARAMETERS),
        "known_zero_flux_reactions": sorted(STOICH.ZERO_FLUX_REACTIONS),
        "states_without_parsed_reaction": sorted(set(states) - connected),
        "stoichiometry_consistency_errors": consistency_errors,
        "sam_stoichiometry": STOICH.STOICHIOMETRY.get("VSAM", {}),
        "explicit_degradation_reactions": {
            name: STOICH.STOICHIOMETRY.get(name, {})
            for name in ("VEGSH_deg", "VEGSSG_deg")
        },
    }


def _case_params(seed: Mapping[str, Any], sam_mode: str) -> dict[str, Any]:
    params = dict(seed)
    params["sam_adenylate_stoichiometry"] = sam_mode
    return params


def _score_case(
    *,
    label: str,
    sol: Any,
    time_exp: np.ndarray,
    curves: Mapping[str, np.ndarray],
    index_map: Mapping[str, int],
    supported_targets: set[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = []
    for metabolite, experimental in curves.items():
        model_values = np.interp(
            time_exp,
            np.asarray(sol.t, dtype=float),
            np.asarray(sol.y[index_map[metabolite]], dtype=float),
        )
        rmse, nrmse, endpoint_error = _nrmse(model_values, experimental)
        rows.append(
            {
                "case": label,
                "metabolite": metabolite,
                "supported_calibration_target": metabolite in supported_targets,
                "independent_observation": metabolite not in NON_INDEPENDENT_OBSERVATIONS,
                "rmse": rmse,
                "nrmse": nrmse,
                "endpoint_relative_error": endpoint_error,
                "experimental_initial_mM": float(experimental[0]),
                "experimental_final_mM": float(experimental[-1]),
                "model_initial_mM": float(model_values[0]),
                "model_final_mM": float(model_values[-1]),
            }
        )
    supported = [
        row
        for row in rows
        if row["supported_calibration_target"] and row["independent_observation"]
    ]
    by_name = {str(row["metabolite"]): row for row in rows}
    adenylate_indices = [BRODBAR_METABOLITE_MAP[name] for name in ("ATP", "ADP", "AMP")]
    initial_adenylate = float(np.sum(sol.y[adenylate_indices, 0]))
    final_adenylate = float(np.sum(sol.y[adenylate_indices, -1]))
    summary = {
        "case": label,
        "mean_supported_nrmse": float(np.mean([row["nrmse"] for row in supported])),
        "median_supported_nrmse": float(np.median([row["nrmse"] for row in supported])),
        "supported_nrmse_gt_1_count": sum(float(row["nrmse"]) > 1.0 for row in supported),
        "supported_target_count": len(supported),
        "minimum_state_mM": float(np.min(sol.y)),
        "adenylate_retention_ratio": final_adenylate / max(initial_adenylate, 1e-30),
        "selected_metrics": {
            metabolite: by_name[metabolite]
            for metabolite in SELECTED_METABOLITES
            if metabolite in by_name
        },
    }
    return summary, rows


def _calibration_snapshot() -> list[dict[str, Any]]:
    if not CANDIDATE_COMPARISON.exists():
        return []
    frame = pd.read_csv(CANDIDATE_COMPARISON)
    keep = [
        "label",
        "accepted",
        "EGLC_nrmse",
        "EGLC_endpoint_error",
        "GLC_nrmse",
        "LAC_nrmse",
        "ELAC_nrmse",
        "VEGLC_flux_nrmse",
        "VELAC_flux_nrmse",
        "VLDH_flux_nrmse",
    ]
    return frame[keep].replace({np.nan: None}).to_dict(orient="records")


def _plot(
    *,
    summaries: Sequence[Mapping[str, Any]],
    metric_rows: Sequence[Mapping[str, Any]],
    solutions: Mapping[str, Any],
    time_exp: np.ndarray,
    curves: Mapping[str, np.ndarray],
    calibration_rows: Sequence[Mapping[str, Any]],
    initialization_inventory: Mapping[str, Any],
    out_path: Path,
) -> None:
    labels = [str(row["case"]) for row in summaries]
    short_labels = ["legacy", "SAM corrected", "strict JA+Brodbar"]
    colors = ["#64748b", "#15803d", "#b45309"]
    fig, axes = plt.subplots(2, 3, figsize=(16, 9), constrained_layout=True)
    x = np.arange(len(labels))
    width = 0.36
    axes[0, 0].bar(
        x - width / 2,
        [row["mean_supported_nrmse"] for row in summaries],
        width,
        color=colors,
        label="mean",
    )
    axes[0, 0].bar(
        x + width / 2,
        [row["median_supported_nrmse"] for row in summaries],
        width,
        color=colors,
        alpha=0.45,
        label="median",
    )
    axes[0, 0].set_xticks(x, short_labels, rotation=15, ha="right")
    axes[0, 0].set_title("Whole-panel supported-target nRMSE")
    axes[0, 0].legend(frameon=False)

    metric_frame = pd.DataFrame(metric_rows)
    selected = ["EGLC", "GLC", "G6P", "F6P", "ATP", "B23PG", "LAC", "ELAC"]
    mx = np.arange(len(selected))
    for case_index, (label, color) in enumerate(zip(labels, colors)):
        local = metric_frame.loc[metric_frame["case"] == label].set_index("metabolite")
        axes[0, 1].bar(
            mx + (case_index - 1) * 0.25,
            [float(local.loc[name, "nrmse"]) for name in selected],
            0.24,
            color=color,
            label=short_labels[case_index],
        )
    axes[0, 1].set_xticks(mx, selected, rotation=25, ha="right")
    axes[0, 1].set_yscale("log")
    axes[0, 1].set_title("Selected metabolite nRMSE")
    axes[0, 1].legend(frameon=False, fontsize=7)

    for label, color, short in zip(labels, colors, short_labels):
        sol = solutions[label]
        axes[0, 2].plot(sol.t, sol.y[BRODBAR_METABOLITE_MAP["ATP"]], color=color, label=short)
    axes[0, 2].scatter(time_exp, curves["ATP"], color="#111827", s=18, label="Brodbar")
    axes[0, 2].set_yscale("symlog", linthresh=1e-4)
    axes[0, 2].set_title("ATP over 46 days")
    axes[0, 2].legend(frameon=False, fontsize=7)

    if calibration_rows:
        candidate_labels = [str(row["label"]) for row in calibration_rows]
        cx = np.arange(len(candidate_labels))
        axes[1, 0].bar(cx - 0.18, [row["EGLC_nrmse"] for row in calibration_rows], 0.36, label="EGLC")
        axes[1, 0].bar(cx + 0.18, [row["GLC_nrmse"] for row in calibration_rows], 0.36, label="GLC")
        axes[1, 0].set_xticks(cx, candidate_labels, rotation=28, ha="right", fontsize=7)
        axes[1, 0].set_yscale("log")
        axes[1, 0].set_title("Transport fit versus intracellular transfer")
        axes[1, 0].legend(frameon=False)

    policies = list(initialization_inventory)
    source_types = ["brodbar_exact", "historical_exact", "generic_1mM"]
    bottom = np.zeros(len(policies), dtype=float)
    policy_labels = ["legacy", "strict generic", "strict historical"]
    for source, color in zip(source_types, ("#2563eb", "#15803d", "#cbd5e1")):
        values = [
            initialization_inventory[policy]["source_counts"].get(source, 0)
            for policy in policies
        ]
        axes[1, 1].bar(policy_labels, values, bottom=bottom, color=color, label=source)
        bottom += np.asarray(values, dtype=float)
    alias_values = [
        sum(
            count
            for source, count in initialization_inventory[policy]["source_counts"].items()
            if source.startswith("legacy_compartment_alias")
        )
        for policy in policies
    ]
    axes[1, 1].bar(policy_labels, alias_values, bottom=bottom, color="#dc2626", label="compartment alias")
    axes[1, 1].set_title("Initial-state provenance")
    axes[1, 1].legend(frameon=False, fontsize=7)

    issue_labels = ["duplicated row pairs", "SAM AMP coproduct", "hidden GSH degradation", "compartment aliases"]
    before = [2, 1, 1, 5]
    after = [2, 0, 0, 0]
    ix = np.arange(len(issue_labels))
    axes[1, 2].bar(ix - 0.18, before, 0.36, color="#b91c1c", label="before audit")
    axes[1, 2].bar(ix + 0.18, after, 0.36, color="#15803d", label="after correction/policy")
    axes[1, 2].set_xticks(ix, issue_labels, rotation=25, ha="right", fontsize=8)
    axes[1, 2].set_title("Resolved versus unresolved structural issues")
    axes[1, 2].legend(frameon=False, fontsize=7)

    for axis in axes.flat:
        axis.grid(axis="y", alpha=0.22)
        axis.set_ylabel("score or count")
    axes[0, 2].set_xlabel("Time (day)")
    fig.suptitle("AIRBC model and Flux Learning Analysis state audit")
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _write_report(path: Path, summary: Mapping[str, Any]) -> None:
    cases = {str(row["case"]): row for row in summary["configuration_summaries"]}
    legacy = cases[CASE_LEGACY]
    corrected = cases[CASE_SAM]
    strict = cases[CASE_STRICT]
    inventory = summary["model_inventory"]
    initialization = summary["initialization_inventory"]
    aliases = initialization["legacy_experimental_alias"]["compartment_aliases"]
    duplicate_text = ", ".join(
        f"{row['left']}/{row['right']}" for row in summary["experimental_duplicates"]
    ) or "none"
    selected_legacy = legacy["selected_metrics"]
    lines = [
        "# AIRBC model and Flux Learning Analysis state audit",
        "",
        "## Technical summary",
        "",
        "The model is not yet ready for a global kinetic calibration. FLA has successfully isolated a transport law that fits extracellular glucose, but every whole-model transfer exposes large intracellular glucose, glycolytic, PPP, or energy defects. The current evidence supports continuing with staged structural attribution and latent-state estimation rather than increasing the optimizer budget.",
        "",
        "Two network corrections are now active: SAM synthesis no longer creates a spurious AMP coproduct, and extracellular GSH/GSSG degradation is represented by explicit reactions visible to FLA. Compartment-aware initialization policies are implemented but not promoted because the strict historical replay is a diagnostic prior, not a jointly guarded state estimate.",
        "",
        "## Model scope and observability",
        "",
        f"- Dynamic states: `{inventory['dynamic_state_count']}` (`{inventory['base_metabolite_count']}` biochemical states plus pHi).",
        f"- Parsed reactions/rates: `{inventory['reaction_or_rate_count']}`; stoichiometric reactions: `{inventory['stoichiometric_reaction_count']}`.",
        f"- Injectable kinetic parameters exposed to the structural map: `{inventory['injectable_parameter_count']}`.",
        f"- Brodbar concentration rows: `55`; supported calibration targets: `{inventory['supported_calibration_target_count']}`; independent supported targets in the aggregate audit: `{legacy['supported_target_count']}`.",
        f"- Exact duplicated experimental rows: `{duplicate_text}`. B13PG and P2G are quarantined as non-independent observations; B23PG and P3G remain the respective representatives.",
        f"- States without a parsed active reaction: `{', '.join(inventory['states_without_parsed_reaction'])}`. Most are deliberate RBC-strict constants or pH bookkeeping states.",
        "",
        "Only net pool derivatives are directly identifiable for most intracellular metabolites. For example, measured G6P, GO6P, F6P, ATP, and B23PG constrain reaction sums, not unique constituent fluxes. The GL6P(0)-V6PGD ridge spans 320-fold in the existing audit, demonstrating that kinetic and initial-state parameters cannot be learned independently without additional constraints.",
        "",
        "## Fixed 46-day configuration comparison",
        "",
        "| Configuration | Mean nRMSE | Median nRMSE | Targets > 1 | Adenylate retention |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in summary["configuration_summaries"]:
        lines.append(
            f"| `{row['case']}` | {row['mean_supported_nrmse']:.4f} | "
            f"{row['median_supported_nrmse']:.4f} | {row['supported_nrmse_gt_1_count']} | "
            f"{row['adenylate_retention_ratio']:.4f} |"
        )
    lines.extend(
        [
            "",
            "The corrected SAM stoichiometry is evaluated as a structural correction, not selected because it improves an objective. Its effect must remain separated from kinetic fitting. The strict historical initialization tests data provenance and compartment handling; it is not a replacement for the constrained seven-state PPP initialization already developed.",
            "",
            "## Current calibration performance",
            "",
            f"- Legacy-reference EGLC nRMSE: `{selected_legacy['EGLC']['nrmse']:.4f}`; GLC nRMSE: `{selected_legacy['GLC']['nrmse']:.4f}`.",
            f"- Legacy-reference G6P/F6P nRMSE: `{selected_legacy['G6P']['nrmse']:.4f}` / `{selected_legacy['F6P']['nrmse']:.4f}`.",
            f"- Legacy-reference ATP/B23PG nRMSE: `{selected_legacy['ATP']['nrmse']:.4f}` / `{selected_legacy['B23PG']['nrmse']:.4f}`.",
            "- The best local transport candidate reaches EGLC nRMSE near `0.10` and endpoint error near `2.3%`, but leaves intracellular GLC near `12.4 mM` versus `0.826 mM` experimentally.",
            "- Opening VHK, ATP affinities, VPGI/VPFK, VELAC/VLDH, VPEP_PASE/VPK, or isolated redox controls improved local objectives but failed transfer guards. No global kinetic set has been promoted.",
            "- The retained V6PGD `0.900x` point is a PPP diagnostic operating point only. It improves the GO6P/F6P joint score by about `3.55%` but retains large absolute G6P/F6P errors.",
            "",
            "## FLA maturity",
            "",
            "### What is working",
            "",
            "- Experimental concentration curves are converted into smoothed derivative teachers with explicit direction conventions.",
            "- Native model fluxes are replayed with curve fitting disabled, so teacher matching cannot silently alter the ODE.",
            "- Calibration is staged by reaction family, uses reversible hypotheses, and requires concentration, endpoint, slope, flux, positivity, redox, and full-panel guards.",
            "- Exact pool-balance reconstruction has repeatedly distinguished kinetic defects from initial-state and network defects.",
            "",
            "### What limits calibration",
            "",
            "- No replicate variances are available, so teacher confidence is heuristic and derivative uncertainty is not propagated into the loss.",
            "- B13PG/B23PG and P2G/P3G are pointwise-identical row pairs. Their source labels must be verified before either pair is used as two independent constraints or reaction-level teachers.",
            "- Brodbar is the only training dataset used systematically; Michel and Bardyn are not yet integrated into a joint or hierarchical objective.",
            "- Fifty-nine states lack direct Brodbar measurements, and the historical default used arbitrary `1 mM` values plus five cross-compartment aliases.",
            "- Internal derivative teachers identify net balances but are sometimes treated too close to reaction-level teachers. Rank and null-space information must gate which constants are opened.",
            "- The objective is evaluated over 46 days even when distinct mechanisms dominate J1-J3, J3-J10, and J10-J46; a single scalar loss can hide temporal compensation.",
            "- The optional ML warm-start predicts parameter seeds from synthetic trajectories, but it has not yet demonstrated held-out improvement over an equal-budget mechanistic search.",
            "",
            "## Network and initialization corrections",
            "",
            "1. `VSAM` now follows `MET + ATP -> ADOMET + Pi + PPi`; AMP is not a coproduct. The previous behavior remains available through `sam_adenylate_stoichiometry=legacy_amp_coproduct`.",
            "2. `VEGSH_deg` and `VEGSSG_deg` are explicit reactions. Their degradation constants and competing transport fluxes are now visible to stoichiometric reachability and FLA.",
            f"3. The legacy initializer contains `{len(aliases)}` cross-compartment aliases: `{', '.join(f'{key}<-{value.split(chr(58), 1)[1]}' for key, value in aliases.items())}`.",
            "4. `compartment_strict_generic` and `compartment_strict_historical` are available as reversible policies. Neither is globally promoted; latent states should be estimated under measured-state locks and transfer guards.",
            "",
            "## Prioritized calibration strategy",
            "",
            "1. Re-audit ATP production and consumption in the fixed 3x `vmax_VDPGM` QSS-B13PG branch. Keep every other initial state and kinetic constant fixed.",
            "2. Quantify VPGK-versus-VDPGM partitioning and the timing of ATP collapse before opening any coupled upstream parameter.",
            "3. Preserve the curated-data observation contract: B13PG is latent; B23PG is the BPG observation; P2G/P3G do not define two independent reaction teachers.",
            "4. Preserve temporal ownership and cumulative guards. A later block cannot compensate for a failed earlier block.",
            "5. Keep transport parameters frozen until hematocrit, compartment-volume scaling, and historical time-unit conversion are documented.",
            "6. Treat the SVD/QR sensitivity basis as an attribution map, not a simultaneous optimization scope. Add profile likelihood only after a one-factor point passes.",
            "7. Fit Brodbar with uncertainty-weighted teachers, then reserve Michel and Bardyn for locked external validation. If protocols differ, use shared kinetic constants plus dataset-specific initial states and observation scaling.",
            "8. Bootstrap concentration curves or use replicate-informed smoothing to produce teacher-flux confidence bands; weight flux residuals by uncertainty rather than a fixed reaction confidence alone.",
            "9. Validate the ML warm-start only after the mechanistic parameter scope is identifiable, using held-out synthetic cases and equal optimization budgets.",
            "",
            "## Decision",
            "",
            "Do not launch a broader Optuna calibration. Retain 3x (`vmax_VDPGM = 4.49158`) as the solver-robust diagnostic Pareto anchor, without promotion, and return to ATP sustainability attribution.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_audit(
    *,
    seed_params_path: Path,
    out_dir: Path,
    dense_points: int,
    method: str,
    rtol: float,
    atol: float,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    seed = _load_params(seed_params_path)
    time_exp, curves, _, index_map, unmapped = _load_brodbar_panel()
    supported_targets = set(EXP_TO_MODEL)
    states = {
        CASE_LEGACY: np.asarray(load_initial_conditions("legacy_experimental_alias"), dtype=float),
        CASE_SAM: np.asarray(load_initial_conditions("legacy_experimental_alias"), dtype=float),
        CASE_STRICT: np.asarray(load_initial_conditions("compartment_strict_historical"), dtype=float),
    }
    params = {
        CASE_LEGACY: _case_params(seed, "legacy_amp_coproduct"),
        CASE_SAM: _case_params(seed, "biochemical_transfer"),
        CASE_STRICT: _case_params(seed, "biochemical_transfer"),
    }
    solutions: dict[str, Any] = {}
    summaries = []
    metric_rows = []
    for label in (CASE_LEGACY, CASE_SAM, CASE_STRICT):
        print(f"[model-fla-audit] replaying {label}", flush=True)
        solution = _simulate(
            x0=states[label],
            params=params[label],
            time_exp=time_exp,
            dense_points=dense_points,
            method=method,
            rtol=rtol,
            atol=atol,
        )
        solutions[label] = solution
        case_summary, case_rows = _score_case(
            label=label,
            sol=solution,
            time_exp=time_exp,
            curves=curves,
            index_map=index_map,
            supported_targets=supported_targets,
        )
        summaries.append(case_summary)
        metric_rows.extend(case_rows)
    model_inventory = _model_inventory()
    initialization_inventory = _initialization_inventory()
    calibration_rows = _calibration_snapshot()
    experimental_duplicates = _duplicate_experimental_rows()
    pd.DataFrame(metric_rows).to_csv(out_dir / "configuration_metabolite_metrics.csv", index=False)
    pd.DataFrame(summaries).to_csv(out_dir / "configuration_summary.csv", index=False)
    pd.DataFrame(calibration_rows).to_csv(out_dir / "fla_candidate_snapshot.csv", index=False)
    _plot(
        summaries=summaries,
        metric_rows=metric_rows,
        solutions=solutions,
        time_exp=time_exp,
        curves=curves,
        calibration_rows=calibration_rows,
        initialization_inventory=initialization_inventory,
        out_path=out_dir / "model_fla_state_overview.png",
    )
    summary = {
        "contract_type": "airbc_model_fla_state_audit",
        "contract_version": 1,
        "model_network_version": MODEL_NETWORK_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "kinetic_optimization_performed": False,
        "parameters_promoted": False,
        "initial_conditions_promoted": False,
        "seed_params_path": str(seed_params_path),
        "comparison_horizon_days": [float(time_exp[0]), float(time_exp[-1])],
        "configuration_order": [CASE_LEGACY, CASE_SAM, CASE_STRICT],
        "model_inventory": model_inventory,
        "initialization_inventory": initialization_inventory,
        "experimental_duplicates": experimental_duplicates,
        "non_independent_observations": sorted(NON_INDEPENDENT_OBSERVATIONS),
        "unmapped_experimental_rows": unmapped,
        "configuration_summaries": summaries,
        "calibration_snapshot": calibration_rows,
        "network_changes": {
            "sam_amp_coproduct_removed_by_default": True,
            "sam_legacy_revert_available": True,
            "extracellular_glutathione_degradation_explicit": True,
            "initialization_policies_added": True,
            "strict_initialization_promoted": False,
        },
        "decision": "defer broad kinetic optimization and continue staged structural attribution",
        "next_step": "audit ATP production-consumption and VPGK-versus-VDPGM partitioning in the fixed 3x QSS-B13PG branch",
        "artifact_paths": {
            "summary": str(out_dir / "model_fla_state_summary.json"),
            "report": str(out_dir / "model_fla_state_report.md"),
            "configuration_metrics": str(out_dir / "configuration_metabolite_metrics.csv"),
            "configuration_summary": str(out_dir / "configuration_summary.csv"),
            "candidate_snapshot": str(out_dir / "fla_candidate_snapshot.csv"),
            "plot": str(out_dir / "model_fla_state_overview.png"),
        },
    }
    (out_dir / "model_fla_state_summary.json").write_text(
        json.dumps(_jsonable(summary), indent=2), encoding="utf-8"
    )
    _write_report(out_dir / "model_fla_state_report.md", summary)
    print(
        json.dumps(
            {
                "summary": summary["artifact_paths"]["summary"],
                "report": summary["artifact_paths"]["report"],
                "decision": summary["decision"],
                "next_step": summary["next_step"],
            },
            indent=2,
        ),
        flush=True,
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit the AIRBC model and FLA state")
    parser.add_argument("--seed-params", type=Path, default=DEFAULT_SEED_PARAMS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--dense-points", type=int, default=451)
    parser.add_argument("--method", default="BDF")
    parser.add_argument("--rtol", type=float, default=3e-4)
    parser.add_argument("--atol", type=float, default=1e-6)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_audit(
        seed_params_path=args.seed_params,
        out_dir=args.out_dir,
        dense_points=args.dense_points,
        method=args.method,
        rtol=args.rtol,
        atol=args.atol,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
