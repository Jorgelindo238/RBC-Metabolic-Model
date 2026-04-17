from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
from pathlib import Path
from statistics import mean
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FLUX_CSV_PATH = REPO_ROOT / "Simulations" / "brodbar" / "fluxes" / "reaction_fluxes.csv"
DEFAULT_ODE_CSV_PATH = REPO_ROOT / "Simulations" / "brodbar" / "metabolites" / "all_metabolites.csv"
DEFAULT_CALIBRATION_ROOT = REPO_ROOT / "Simulations" / "brodbar" / "calibration"
DEFAULT_FLUX_LEARNING_ROOT = REPO_ROOT / "Simulations" / "brodbar" / "hermes" / "flux_learning"

SUPPORTED_REACTIONS = ["VEGLC", "VELAC", "VLDH", "VPK", "VENOPGM"]

REACTION_TARGET_METABOLITES: dict[str, list[str]] = {
    "VEGLC": ["EGLC", "GLC"],
    "VELAC": ["ELAC", "LAC"],
    "VLDH": ["PYR", "LAC", "ELAC"],
    "VPK": ["ATP", "ADP", "PEP", "PYR"],
    "VENOPGM": ["PEP", "P2G", "PYR"],
}

REACTION_STATE_INPUTS: dict[str, list[str]] = {
    "VEGLC": ["EGLC", "GLC"],
    "VELAC": ["ELAC", "LAC"],
    "VLDH": ["PYR", "LAC", "NADH", "NAD"],
    "VPK": ["PEP", "ADP", "ATP", "PYR"],
    "VENOPGM": ["P2G", "PEP"],
}

REACTION_CANDIDATE_FAMILIES: dict[str, list[str]] = {
    "VEGLC": ["hybrid_asymmetric_transport", "mm_bidirectional"],
    "VELAC": ["hybrid_reversible_transport", "mm_efflux"],
    "VLDH": ["redox_backpressure_hill", "reversible_redox_gate"],
    "VPK": ["substrate_hill_energy_backpressure", "energy_gate_mm_blend"],
    "VENOPGM": ["substrate_hill_product_backpressure", "product_gate_mm_blend"],
}

REACTION_EXISTING_PARAM_SCOPES: dict[str, str] = {
    "VEGLC": "hybrid_glucose_lactate",
    "VELAC": "hybrid_glucose_lactate",
    "VLDH": "hybrid_glucose_lactate",
    "VPK": "hybrid_downstream_pk_eno",
    "VENOPGM": "hybrid_downstream_pk_eno",
}

REACTION_HYBRID_PARAMS: dict[str, list[str]] = {
    "VEGLC": [
        "hybrid_blend_VEGLC",
        "hybrid_import_hill_VEGLC",
        "hybrid_export_hill_VEGLC",
        "hybrid_reverse_scale_VEGLC",
    ],
    "VELAC": [
        "hybrid_blend_VELAC",
        "hybrid_efflux_hill_VELAC",
        "hybrid_backpressure_hill_VELAC",
        "hybrid_backpressure_scale_VELAC",
        "hybrid_km_ELAC",
        "hybrid_lac_retention_strength_VELAC",
        "hybrid_lac_retention_hill_VELAC",
        "hybrid_lac_retention_km_scale_VELAC",
    ],
    "VLDH": [
        "hybrid_blend_VLDH",
        "hybrid_forward_hill_VLDH",
        "hybrid_reverse_hill_VLDH",
        "hybrid_reverse_scale_VLDH",
    ],
    "VPK": [
        "hybrid_blend_VPK",
        "hybrid_pep_hill_VPK",
        "hybrid_adp_hill_VPK",
        "hybrid_atp_backpressure_scale_VPK",
        "hybrid_pyr_backpressure_scale_VPK",
    ],
    "VENOPGM": [
        "hybrid_blend_VENOPGM",
        "hybrid_substrate_hill_VENOPGM",
        "hybrid_backpressure_hill_VENOPGM",
        "hybrid_backpressure_scale_VENOPGM",
    ],
}


def _resolve_repo_path(value: Any, default: Path | None = None) -> Path | None:
    if value is None or not str(value).strip():
        return default
    path = Path(str(value).strip())
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _slugify(text: str) -> str:
    chars = []
    for char in text.lower():
        if char.isalnum():
            chars.append(char)
        else:
            chars.append("_")
    slug = "".join(chars).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or "artifact"


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _normalize_reactions(values: Any) -> list[str]:
    normalized: list[str] = []
    for value in values or []:
        name = str(value).strip().upper()
        if name in SUPPORTED_REACTIONS and name not in normalized:
            normalized.append(name)
    return normalized


def _select_reactions(raw_reactions: Any) -> list[str]:
    selected = _normalize_reactions(raw_reactions)
    return selected or list(SUPPORTED_REACTIONS)


def _report_by_metabolite(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in report.get("per_metabolite", []) or []:
        if isinstance(row, dict) and row.get("name"):
            result[str(row["name"]).upper()] = row
    return result


def _series_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "available": False,
            "start": None,
            "end": None,
            "min": None,
            "max": None,
            "mean_abs": None,
            "sign_changes": 0,
            "near_zero_fraction": None,
            "peak_index": None,
        }
    peak_index = max(range(len(values)), key=lambda idx: abs(values[idx]))
    sign_changes = 0
    previous_sign = 0
    for value in values:
        sign = 0 if abs(value) < 1e-12 else (1 if value > 0 else -1)
        if sign != 0 and previous_sign != 0 and sign != previous_sign:
            sign_changes += 1
        if sign != 0:
            previous_sign = sign
    near_zero = sum(1 for value in values if abs(value) < 1e-6)
    return {
        "available": True,
        "start": values[0],
        "end": values[-1],
        "min": min(values),
        "max": max(values),
        "mean_abs": mean(abs(value) for value in values),
        "sign_changes": sign_changes,
        "near_zero_fraction": near_zero / len(values),
        "peak_index": peak_index,
    }


def _summarize_ode_profiles(rows: list[dict[str, str]], metabolites: list[str]) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for metabolite in metabolites:
        values = []
        for row in rows:
            numeric = _coerce_float(row.get(metabolite))
            if numeric is not None:
                values.append(numeric)
        if not values:
            profiles[metabolite] = {"available": False}
            continue
        start = values[0]
        end = values[-1]
        peak = max(values)
        trough = min(values)
        pct_drop = None
        if abs(start) > 1e-12:
            pct_drop = (end - start) / start
        profiles[metabolite] = {
            "available": True,
            "start": start,
            "end": end,
            "min": trough,
            "max": peak,
            "delta": end - start,
            "pct_drop": pct_drop,
        }
    return profiles


def _build_matched_rows(
    ode_rows: list[dict[str, str]],
    flux_rows: list[dict[str, str]],
    selected_reactions: list[str],
) -> list[dict[str, Any]]:
    if not ode_rows or not flux_rows:
        return []

    ode_time_key = next(iter(ode_rows[0].keys()))
    flux_time_key = next(iter(flux_rows[0].keys()))

    flux_timepoints: list[tuple[float, dict[str, str]]] = []
    for row in flux_rows:
        hours = _coerce_float(row.get(flux_time_key))
        if hours is None:
            continue
        flux_timepoints.append((hours / 24.0, row))
    flux_timepoints.sort(key=lambda item: item[0])
    if not flux_timepoints:
        return []

    state_metabolites: list[str] = []
    for reaction in selected_reactions:
        for metabolite in REACTION_STATE_INPUTS.get(reaction, []):
            if metabolite not in state_metabolites:
                state_metabolites.append(metabolite)
        for metabolite in REACTION_TARGET_METABOLITES.get(reaction, []):
            if metabolite not in state_metabolites:
                state_metabolites.append(metabolite)

    matched_rows: list[dict[str, Any]] = []
    flux_index = 0
    for ode_row in ode_rows:
        ode_time_days = _coerce_float(ode_row.get(ode_time_key))
        if ode_time_days is None:
            continue
        while flux_index + 1 < len(flux_timepoints) and flux_timepoints[flux_index + 1][0] <= ode_time_days:
            flux_index += 1
        best_index = flux_index
        if flux_index + 1 < len(flux_timepoints):
            current_delta = abs(flux_timepoints[flux_index][0] - ode_time_days)
            next_delta = abs(flux_timepoints[flux_index + 1][0] - ode_time_days)
            if next_delta < current_delta:
                best_index = flux_index + 1
        flux_days, flux_row = flux_timepoints[best_index]
        matched_rows.append(
            {
                "time_days": ode_time_days,
                "time_hours": flux_days * 24.0,
                "states": {
                    metabolite: _coerce_float(ode_row.get(metabolite))
                    for metabolite in state_metabolites
                    if metabolite in ode_row
                },
                "fluxes": {
                    reaction: _coerce_float(flux_row.get(reaction))
                    for reaction in selected_reactions
                    if reaction in flux_row
                },
            }
        )
    return matched_rows


def _detect_failure_modes(
    reaction: str,
    report_map: dict[str, dict[str, Any]],
    ode_profiles: dict[str, dict[str, Any]],
    flux_summary: dict[str, Any],
) -> tuple[str, list[str]]:
    notes: list[str] = []
    dominant = "hybrid_signal_detected"

    if reaction == "VEGLC":
        eglc = ode_profiles.get("EGLC", {})
        eglc_nrmse = float(report_map.get("EGLC", {}).get("nrmse", 0.0) or 0.0)
        if eglc.get("available") and eglc.get("pct_drop") is not None and eglc["pct_drop"] > -0.2:
            dominant = "shallow_transport_draw"
            notes.append("EGLC remains too shallow over the long horizon.")
        if eglc_nrmse >= 0.05:
            notes.append("EGLC still contributes measurable fit pressure.")
    elif reaction == "VELAC":
        elac = ode_profiles.get("ELAC", {})
        lac = ode_profiles.get("LAC", {})
        if elac.get("available") and elac.get("delta", 0.0) <= 0.0:
            dominant = "weak_export_accumulation"
            notes.append("ELAC is not accumulating strongly enough.")
        if lac.get("available") and lac.get("end", 0.0) < 3.0:
            notes.append("LAC final level stays soft relative to the export axis.")
    elif reaction == "VLDH":
        pyr = ode_profiles.get("PYR", {})
        lac = ode_profiles.get("LAC", {})
        if pyr.get("available") and pyr.get("max", 0.0) > 1.5 * max(pyr.get("end", 1e-9), 1e-9):
            dominant = "pyruvate_redox_mismatch"
            notes.append("PYR shows a large transient spike relative to its final level.")
        if lac.get("available") and lac.get("end", 0.0) < 4.5:
            notes.append("LAC final accumulation remains weaker than desired.")
    elif reaction == "VPK":
        atp = ode_profiles.get("ATP", {})
        adp = ode_profiles.get("ADP", {})
        pep = ode_profiles.get("PEP", {})
        if atp.get("available") and atp.get("end", 0.0) < 0.01:
            dominant = "energy_coupled_backpressure"
            notes.append("ATP still collapses at the end of the horizon.")
        if adp.get("available") and adp.get("end", 0.0) < 0.01:
            notes.append("ADP still collapses toward zero.")
        if pep.get("available") and pep.get("max", 0.0) > 0.5:
            notes.append("PEP retains a visible backpressure signature.")
    elif reaction == "VENOPGM":
        pep = ode_profiles.get("PEP", {})
        if pep.get("available") and pep.get("max", 0.0) > 0.5:
            dominant = "product_backpressure"
            notes.append("PEP retains a delayed hump consistent with product backpressure.")

    if flux_summary.get("sign_changes", 0) > 3:
        notes.append("Flux changes sign repeatedly and may need a reversible or gated family.")
    if flux_summary.get("near_zero_fraction", 0.0) > 0.75:
        notes.append("Flux spends most of the horizon near zero, suggesting a highly gated regime.")
    if not notes:
        notes.append("Teacher signal is weakly informative but still usable for hybrid family ranking.")
    return dominant, notes


def _priority_score(
    reaction: str,
    report_map: dict[str, dict[str, Any]],
    flux_summary: dict[str, Any],
) -> float:
    target_errors = [
        float(report_map.get(name, {}).get("nrmse", 0.0) or 0.0)
        for name in REACTION_TARGET_METABOLITES.get(reaction, [])
    ]
    error_score = mean(target_errors) if target_errors else 0.0
    mobility_bonus = min(float(flux_summary.get("mean_abs", 0.0) or 0.0), 5.0) / 5.0
    sign_penalty = min(flux_summary.get("sign_changes", 0), 4) * 0.05
    return round(error_score + 0.25 * mobility_bonus + sign_penalty, 4)


def build_flux_teacher_dataset(args: dict[str, Any]) -> dict[str, Any]:
    report_path = _resolve_repo_path(args.get("reportPath"))
    if report_path is None or not report_path.exists():
        raise FileNotFoundError("reportPath is required for flux teacher dataset generation.")
    ode_csv_path = _resolve_repo_path(args.get("odeCsvPath"), DEFAULT_ODE_CSV_PATH)
    flux_csv_path = _resolve_repo_path(args.get("fluxCsvPath"), DEFAULT_FLUX_CSV_PATH)
    if ode_csv_path is None or not ode_csv_path.exists():
        raise FileNotFoundError(f"ODE CSV not found: {ode_csv_path}")
    if flux_csv_path is None or not flux_csv_path.exists():
        raise FileNotFoundError(f"Flux CSV not found: {flux_csv_path}")

    selected_reactions = _select_reactions(args.get("reactions"))
    run_label = str(args.get("datasetName") or report_path.parent.name).strip() or "flux_teacher_dataset"
    flux_learning_root = _resolve_repo_path(args.get("fluxLearningRootPath"), DEFAULT_FLUX_LEARNING_ROOT)
    if flux_learning_root is None:
        raise ValueError("Unable to resolve flux learning root path.")
    dataset_dir = flux_learning_root / "datasets"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dataset_path = _resolve_repo_path(args.get("outPath"))
    if dataset_path is None:
        dataset_path = dataset_dir / f"{timestamp}_{_slugify(run_label)}.json"

    report = _load_json(report_path)
    ode_rows = _read_csv_rows(ode_csv_path)
    flux_rows = _read_csv_rows(flux_csv_path)
    matched_rows = _build_matched_rows(ode_rows, flux_rows, selected_reactions)
    report_map = _report_by_metabolite(report)

    ode_profiles = _summarize_ode_profiles(
        ode_rows,
        sorted({name for reaction in selected_reactions for name in REACTION_TARGET_METABOLITES.get(reaction, [])}),
    )

    per_reaction: list[dict[str, Any]] = []
    for reaction in selected_reactions:
        reaction_fluxes = [
            row["fluxes"].get(reaction)
            for row in matched_rows
            if row["fluxes"].get(reaction) is not None
        ]
        numeric_fluxes = [float(value) for value in reaction_fluxes if value is not None]
        flux_summary = _series_summary(numeric_fluxes)
        dominant_failure_mode, notes = _detect_failure_modes(reaction, report_map, ode_profiles, flux_summary)
        target_error_rows = {
            metabolite: {
                "nrmse": report_map.get(metabolite, {}).get("nrmse"),
                "rmse": report_map.get(metabolite, {}).get("rmse"),
            }
            for metabolite in REACTION_TARGET_METABOLITES.get(reaction, [])
        }
        per_reaction.append(
            {
                "reaction": reaction,
                "target_metabolites": REACTION_TARGET_METABOLITES.get(reaction, []),
                "state_inputs": REACTION_STATE_INPUTS.get(reaction, []),
                "candidate_families": REACTION_CANDIDATE_FAMILIES.get(reaction, []),
                "existing_param_scope": REACTION_EXISTING_PARAM_SCOPES.get(reaction),
                "available_hybrid_parameters": REACTION_HYBRID_PARAMS.get(reaction, []),
                "target_errors": target_error_rows,
                "ode_profiles": {
                    metabolite: ode_profiles.get(metabolite, {"available": False})
                    for metabolite in REACTION_TARGET_METABOLITES.get(reaction, [])
                },
                "flux_summary": flux_summary,
                "teacher_signal": {
                    "dominant_failure_mode": dominant_failure_mode,
                    "priority_score": _priority_score(reaction, report_map, flux_summary),
                    "notes": notes,
                },
            }
        )

    per_reaction.sort(key=lambda item: item["teacher_signal"]["priority_score"], reverse=True)
    dataset_payload = {
        "contract_type": "hermes_flux_teacher_dataset",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready_for_teacher_review",
        "dataset_name": run_label,
        "source_artifacts": {
            "report_path": str(report_path),
            "ode_csv_path": str(ode_csv_path),
            "flux_csv_path": str(flux_csv_path),
            "best_params_path": str(report_path.parent / "best_params.json"),
        },
        "selected_reactions": selected_reactions,
        "matched_timepoint_count": len(matched_rows),
        "top_priority_reactions": [item["reaction"] for item in per_reaction[:3]],
        "matched_rows": matched_rows,
        "per_reaction": per_reaction,
    }
    _ensure_parent(dataset_path)
    dataset_path.write_text(json.dumps(dataset_payload, indent=2), encoding="utf-8")
    return {
        "status": "completed",
        "datasetPath": str(dataset_path),
        "dataset": dataset_payload,
        "topPriorityReactions": [item["reaction"] for item in per_reaction[:3]],
    }


def _proposal_for_reaction(reaction_entry: dict[str, Any]) -> dict[str, Any]:
    reaction = reaction_entry["reaction"]
    dominant_failure_mode = reaction_entry["teacher_signal"]["dominant_failure_mode"]
    selected_family = reaction_entry["candidate_families"][0]
    if reaction == "VEGLC" and dominant_failure_mode == "shallow_transport_draw":
        selected_family = "hybrid_asymmetric_transport"
    elif reaction == "VELAC" and dominant_failure_mode == "weak_export_accumulation":
        selected_family = "hybrid_reversible_transport"
    elif reaction == "VLDH":
        selected_family = "redox_backpressure_hill"
    elif reaction == "VPK":
        selected_family = "substrate_hill_energy_backpressure"
    elif reaction == "VENOPGM":
        selected_family = "substrate_hill_product_backpressure"

    proposal = {
        "reaction": reaction,
        "priority_score": reaction_entry["teacher_signal"]["priority_score"],
        "teacher_signal": reaction_entry["teacher_signal"],
        "target_metabolites": reaction_entry["target_metabolites"],
        "required_state_inputs": reaction_entry["state_inputs"],
        "candidate_families": reaction_entry["candidate_families"],
        "selected_family": selected_family,
        "existing_param_scope": reaction_entry["existing_param_scope"],
        "available_hybrid_parameters": reaction_entry["available_hybrid_parameters"],
        "rationale": (
            f"{reaction} is prioritized because Hermes sees {dominant_failure_mode} "
            f"against target metabolites {', '.join(reaction_entry['target_metabolites'])}."
        ),
        "recommended_teacher_objective": {
            "mode": "pure_flux_curve_teacher",
            "fit_targets": reaction_entry["target_metabolites"],
            "fit_flux": reaction,
        },
        "recommended_student_objective": {
            "mode": "hybrid_mm_student",
            "reaction": reaction,
            "selected_family": selected_family,
            "calibration_scope": reaction_entry["existing_param_scope"],
            "include_params": reaction_entry["available_hybrid_parameters"],
        },
    }
    return proposal


def _combined_scope(proposals: list[dict[str, Any]]) -> str:
    scopes = {proposal["existing_param_scope"] for proposal in proposals if proposal.get("existing_param_scope")}
    if scopes == {"hybrid_glucose_lactate"}:
        return "hybrid_glucose_lactate"
    if scopes == {"hybrid_downstream_pk_eno"}:
        return "hybrid_downstream_pk_eno"
    return "hybrid_glucose_lactate_plus_downstream"


def propose_hybrid_model(args: dict[str, Any]) -> dict[str, Any]:
    dataset_path = _resolve_repo_path(args.get("datasetPath"))
    dataset_payload: dict[str, Any]
    dataset_result: dict[str, Any] | None = None
    if dataset_path is None:
        dataset_result = build_flux_teacher_dataset(args)
        dataset_path = Path(dataset_result["datasetPath"])
        dataset_payload = dataset_result["dataset"]
    else:
        if not dataset_path.exists():
            raise FileNotFoundError(f"Teacher dataset not found: {dataset_path}")
        dataset_payload = _load_json(dataset_path)

    selected_reactions = _select_reactions(args.get("reactions")) or dataset_payload.get("selected_reactions", [])
    reaction_entries = [
        entry
        for entry in dataset_payload.get("per_reaction", [])
        if entry.get("reaction") in selected_reactions
    ]
    reaction_entries.sort(key=lambda item: item["teacher_signal"]["priority_score"], reverse=True)
    top_k = max(1, min(int(args.get("topK", 3) or 3), len(reaction_entries) or 1))
    selected_entries = reaction_entries[:top_k]
    proposals = [_proposal_for_reaction(entry) for entry in selected_entries]

    proposed_scope = _combined_scope(proposals)
    include_params: list[str] = []
    for proposal in proposals:
        for parameter in proposal["available_hybrid_parameters"]:
            if parameter not in include_params:
                include_params.append(parameter)

    best_params_path = dataset_payload.get("source_artifacts", {}).get("best_params_path", "")
    stage_plan_request = {
        "seedParamsPath": best_params_path,
        "hypothesis": "Teacher-student hybrid proposal from flux learning",
        "targetScope": str(args.get("targetScope") or "glycolysis_extracellular"),
        "optimizationStrategy": "hybrid_only",
        "protect": ["ATP", "ADP", "EGLC", "ELAC", "PYR", "PEP", "LAC"],
        "generatedBy": str(args.get("generatedBy") or "hermes_flux_learning"),
        "teacherFocusMetabolites": ["EGLC", "ELAC", "LAC"],
        "teacherFocusWeight": float(args.get("teacherFocusWeight", 4.0) or 4.0),
        "stages": [
            {
                "name": "teacher_student_hybrid_followup",
                "phases": [1],
                "paramScope": proposed_scope,
                "targetScope": str(args.get("targetScope") or "glycolysis_extracellular"),
                "includeParams": include_params,
                "nTrials": int(args.get("nTrials", 8) or 8),
                "globalTrials": int(args.get("globalTrials", 0) or 0),
                "seed": int(args.get("seed", 29) or 29),
                "curveFitStrength": float(args.get("curveFitStrength", 0.1) or 0.1),
                "tMax": float(args.get("tMax", 42.0) or 42.0),
                "teacherFocusMetabolites": ["EGLC", "ELAC", "LAC"],
                "teacherFocusWeight": float(args.get("teacherFocusWeight", 4.0) or 4.0),
            }
        ],
    }

    flux_learning_root = _resolve_repo_path(args.get("fluxLearningRootPath"), DEFAULT_FLUX_LEARNING_ROOT)
    if flux_learning_root is None:
        raise ValueError("Unable to resolve flux learning root path.")
    proposal_dir = flux_learning_root / "proposals"
    proposal_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    proposal_name = str(args.get("proposalName") or dataset_payload.get("dataset_name") or "hybrid_flux_model")
    proposal_path = _resolve_repo_path(args.get("outPath"))
    if proposal_path is None:
        proposal_path = proposal_dir / f"{timestamp}_{_slugify(proposal_name)}.json"

    proposal_payload = {
        "contract_type": "hermes_hybrid_flux_model_proposal",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready_for_review",
        "dataset_path": str(dataset_path),
        "top_k": top_k,
        "selected_reactions": [proposal["reaction"] for proposal in proposals],
        "proposals": proposals,
        "recommended_stage_plan_request": stage_plan_request,
        "system_hypothesis": (
            "Use the teacher flux dataset to rank reactions by curve pressure, then distill the "
            "highest-pressure reactions into hybrid Michaelis-Menten families with interpretable gates."
        ),
    }
    _ensure_parent(proposal_path)
    proposal_path.write_text(json.dumps(proposal_payload, indent=2), encoding="utf-8")

    return {
        "status": "completed",
        "datasetPath": str(dataset_path),
        "proposalPath": str(proposal_path),
        "proposal": proposal_payload,
        "datasetResult": dataset_result,
    }


def coordinate_flux_learning(args: dict[str, Any]) -> dict[str, Any]:
    proposal_result = propose_hybrid_model(args)
    proposal_payload = proposal_result["proposal"]
    dataset_payload = proposal_result["datasetResult"]["dataset"] if proposal_result.get("datasetResult") else _load_json(Path(proposal_result["datasetPath"]))
    return {
        "status": "completed",
        "datasetPath": proposal_result["datasetPath"],
        "proposalPath": proposal_result["proposalPath"],
        "selectedReactions": proposal_payload["selected_reactions"],
        "recommendedStagePlanRequest": proposal_payload["recommended_stage_plan_request"],
        "dataset": dataset_payload,
        "proposal": proposal_payload,
    }
