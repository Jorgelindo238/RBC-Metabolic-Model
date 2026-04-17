"""
OpenAI service for RoBoCop chat responses
"""

import json
import re
from typing import Dict, Any, List, Optional
from openai import AsyncOpenAI
from config import settings, is_openai_configured


SIMULATION_CONCENTRATION_KEYWORDS = (
    "final",
    "concentration",
    "value",
    "level",
    "end",
    "last",
    "start",
    "trend",
    "change",
    "increase",
    "decrease",
    "maximum",
    "minimum",
    "max",
    "min",
    "how much",
)

SIMULATION_PROVENANCE_KEYWORDS = (
    "bordbar",
    "custom",
    "dataset",
    "data",
    "calibration",
    "applied",
    "loaded",
    "provenance",
    "fallback",
)

FLUX_PROVENANCE_KEYWORDS = (
    "bordbar",
    "custom",
    "dataset",
    "data",
    "calibration",
    "applied",
    "loaded",
    "provenance",
    "fallback",
    "pathway",
    "flux",
    "result",
    "summary",
)


def _format_number(value: Any) -> str:
    """Format numeric values for user-facing responses."""
    if value is None:
        return "unknown"

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return str(value)

    if numeric_value.is_integer():
        return str(int(numeric_value))

    return f"{numeric_value:.6g}"


def _get_simulation_metabolite_profiles(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return all metabolite profiles from the simulation context."""
    metabolites = context.get("outputs", {}).get("metabolites", {})
    profiles = metabolites.get("profiles", [])
    if isinstance(profiles, list):
        return [profile for profile in profiles if isinstance(profile, dict)]
    return []


def _get_simulation_metabolite_names(context: Dict[str, Any]) -> List[str]:
    """Return metabolite names available in the simulation context."""
    metabolites = context.get("outputs", {}).get("metabolites", {})
    names = metabolites.get("names", [])
    if isinstance(names, list):
        return [name for name in names if isinstance(name, str)]

    profiles = _get_simulation_metabolite_profiles(context)
    return [
        profile.get("metabolite")
        for profile in profiles
        if isinstance(profile.get("metabolite"), str)
    ]


def _get_simulation_provenance_lines(context: Dict[str, Any]) -> List[str]:
    """Return concise provenance lines for simulation answers."""
    lines: List[str] = []
    mode = context.get("researchDataMode") or context.get("research_data_mode")
    dataset_applied = bool(context.get("datasetApplied") if context.get("datasetApplied") is not None else context.get("dataset_applied"))
    default_fallback_used = bool(context.get("defaultFallbackUsed") if context.get("defaultFallbackUsed") is not None else context.get("dataset_fallback_reason"))
    dataset_label = (
        context.get("activeDatasetLabel")
        or context.get("active_dataset_label")
        or (context.get("activeDataset") or {}).get("label")
        or "Bordbar reference dataset"
    )
    dataset_fallback_reason = context.get("datasetFallbackReason") or context.get("dataset_fallback_reason")
    calibration_applied = bool(
        context.get("calibrationApplied")
        if context.get("calibrationApplied") is not None
        else context.get("calibratedParametersActive")
        if context.get("calibratedParametersActive") is not None
        else context.get("custom_params_source") not in (None, "defaults")
    )
    calibration_source = (
        context.get("calibrationSource")
        or context.get("customParamsSource")
        or context.get("custom_params_source")
        or "defaults"
    )
    applied_count = len(context.get("datasetAppliedMetabolites") or context.get("dataset_applied_metabolites") or [])

    if mode == "custom_user_data_mode":
      if dataset_applied:
        lines.append(f"Data mode: custom user data ({dataset_label})")
        lines.append(f"Dataset applied: {applied_count} mapped metabolites")
      else:
        lines.append(f"Data mode: custom user data ({dataset_label})")
        lines.append(
            "Dataset fallback used"
            + (f" ({dataset_fallback_reason})" if dataset_fallback_reason else "")
        )
    else:
        lines.append("Data mode: Bordbar reference")
        lines.append("Dataset applied: Bordbar default flow")

    if calibration_applied:
        if calibration_source == "provided":
            lines.append("Calibration: latest calibration applied")
        elif calibration_source == "auto_loaded":
            lines.append("Calibration: auto-loaded from saved research state")
        else:
            lines.append("Calibration: applied")
    else:
        lines.append("Calibration: default Bordbar parameters retained")

    if default_fallback_used and mode == "custom_user_data_mode" and not dataset_applied:
        lines.append("Fallback provenance: custom data was not applied, so the solver used Bordbar defaults")

    return lines


def _get_calibration_provenance_lines(context: Dict[str, Any]) -> List[str]:
    """Return concise provenance lines for calibration answers."""
    lines: List[str] = []
    summary = context.get("summary", {})
    mode = context.get("researchDataMode") or context.get("research_data_mode")
    dataset_applied = bool(
        context.get("datasetApplied")
        if context.get("datasetApplied") is not None
        else context.get("dataset_applied")
    )
    dataset_label = (
        context.get("activeDatasetLabel")
        or context.get("active_dataset_label")
        or (context.get("activeDataset") or {}).get("label")
        or "Bordbar reference dataset"
    )
    dataset_fallback_reason = context.get("datasetFallbackReason") or context.get("dataset_fallback_reason")
    inputs = context.get("inputs", {})
    selected_parameters = inputs.get("selectedParameters") or []
    selected_families = inputs.get("selectedParameterFamilies") or []
    strategy_label = (
        inputs.get("strategyLabel")
        or inputs.get("selectedOptimizationStrategy")
        or inputs.get("optimizationStrategy")
        or "unknown strategy"
    )
    strategy_value = inputs.get("selectedOptimizationStrategy") or inputs.get("optimizationStrategy") or "unknown"
    selection_mode = (
        "recommended subset"
        if inputs.get("isRecommendedSubset")
        else "advanced canonical inventory"
        if inputs.get("hasAdvancedSelection")
        else "canonical selection"
    )
    taxonomy_source = inputs.get("canonicalTaxonomySource") or "MM_calibration"
    taxonomy_version = inputs.get("canonicalTaxonomyVersion") or "mm_calibration_v1"
    calibration_applied = bool(
        context.get("calibrationApplied")
        if context.get("calibrationApplied") is not None
        else context.get("calibratedParametersActive")
        if context.get("calibratedParametersActive") is not None
        else False
    )
    calibration_source = (
        context.get("calibrationSource")
        or context.get("customParamsSource")
        or context.get("custom_params_source")
        or "defaults"
    )
    calibration_status = _get_calibration_status(context)
    calibration_result_available = calibration_status == "completed"

    if mode == "custom_user_data_mode":
        if dataset_applied:
            lines.append(f"Data mode: custom user data ({dataset_label})")
        else:
            lines.append(f"Data mode: custom user data ({dataset_label})")
            lines.append(
                "Dataset fallback used"
                + (f" ({dataset_fallback_reason})" if dataset_fallback_reason else "")
            )
    else:
        lines.append("Data mode: Bordbar reference")

    if selected_parameters:
        lines.append(f"Selected parameters: {len(selected_parameters)}")
    if selected_families:
        lines.append(f"Parameter families: {', '.join(selected_families)}")
    lines.append(f"Optimization strategy: {strategy_label} ({strategy_value})")
    lines.append(f"Selection scope: {selection_mode}")
    lines.append(f"Canonical taxonomy: {taxonomy_source} {taxonomy_version}")
    if calibration_applied:
        if calibration_source == "provided":
            lines.append("Calibration: latest calibration applied")
        elif calibration_source == "auto_loaded":
            lines.append("Calibration: auto-loaded calibration active")
        else:
            lines.append("Calibration: calibration active")
    else:
        lines.append("Calibration: default Bordbar parameters retained")
    lines.append(f"Calibration state: {calibration_status.replace('_', ' ')}")

    registry_comparison = context.get("registryComparison") or context.get("registry_comparison") or {}
    if context.get("moduleType") == "calibration-registry" or registry_comparison:
        registry_summary = (
            context.get("registryResultSummary")
            or context.get("registry_result_summary")
            or context.get("resultSummary")
            or context.get("result_summary")
        )
        if isinstance(registry_summary, str) and registry_summary.strip():
            lines.append(f"Registry summary: {registry_summary.strip()}")

        comparison_summary = (
            registry_comparison.get("comparisonSummary")
            or registry_comparison.get("comparison_summary")
            or (summary.get("comparisonLane") if isinstance(summary, dict) else None)
        )
        if isinstance(comparison_summary, str) and comparison_summary.strip():
            lines.append(f"Comparison lanes: {comparison_summary.strip()}")

        lead_record = registry_comparison.get("leadRecord") or registry_comparison.get("lead_record") or {}
        if isinstance(lead_record, dict) and lead_record:
            lead_label = (
                lead_record.get("label")
                or lead_record.get("runId")
                or lead_record.get("run_id")
                or "lead record"
            )
            lead_bits = []
            benchmark_status = (
                lead_record.get("benchmarkStatus")
                or lead_record.get("benchmark_status")
                or lead_record.get("status")
            )
            completion_status = (
                lead_record.get("completionStatus")
                or lead_record.get("completion_status")
            )
            if isinstance(benchmark_status, str) and benchmark_status.strip():
                lead_bits.append(benchmark_status.replace("_", " "))
            if isinstance(completion_status, str) and completion_status.strip():
                lead_bits.append(completion_status.replace("_", " "))
            if lead_bits:
                lines.append(f"Lead record: {lead_label} ({' / '.join(lead_bits)})")
            else:
                lines.append(f"Lead record: {lead_label}")

        groups = registry_comparison.get("groups") or registry_comparison.get("comparison_groups") or []
        if isinstance(groups, list) and groups:
            group_bits: List[str] = []
            for group in groups[:3]:
                if not isinstance(group, dict):
                    continue
                label = group.get("label") or group.get("name") or group.get("status") or "group"
                count = group.get("count") or group.get("runCount") or group.get("run_count")
                if isinstance(count, (int, float)):
                    group_bits.append(f"{label} ({int(count)})")
                else:
                    group_bits.append(str(label))
            if group_bits:
                lines.append(f"Visible comparison lanes: {', '.join(group_bits)}")

        lines.append("Registry result: historical benchmark ledger rather than a calibration fit.")
        return {
            "message": "\n".join(lines),
            "contextReferences": refs + [
                "registryComparison",
                "registryResultSummary",
                "registryComparison.leadRecord",
                "registryComparison.groups",
                "summary.comparisonLane",
            ],
            "confidence": "high",
            "suggestedFollowUps": [
                "Which comparison lane is the lead record in?",
                "How do the historical benchmark lanes differ?",
                "What does the registry summary suggest?",
                "Should I inspect a specific historical run?",
            ],
        }

    if calibration_result_available:
        fit_metrics = _get_calibration_fit_metrics(context)
        if isinstance(fit_metrics.get("rSquared"), (int, float)):
            line = f"Calibration result: R²={float(fit_metrics['rSquared']):.3f}"
            if isinstance(fit_metrics.get("improvementPct"), (int, float)):
                line += f", improvement {float(fit_metrics['improvementPct']):.1f}%"
            lines.append(line)
        result_summary = context.get("resultSummary") or context.get("result_summary")
        if isinstance(result_summary, str) and result_summary.strip():
            lines.append(f"Result summary: {result_summary.strip()}")
    elif calibration_status == "running":
        lines.append("Calibration is currently running.")
    elif calibration_status == "failed":
        lines.append("Calibration failed before producing a completed result.")
    else:
        lines.append("Calibration result: not yet available")

    return lines


def _get_calibration_status(context: Dict[str, Any]) -> str:
    status = context.get("calibrationStatus") or context.get("calibration_status")
    if status in {"setup_only", "running", "completed", "failed"}:
        return str(status)

    if context.get("calibrationFailed") or context.get("calibration_failed"):
        return "failed"

    if (
        context.get("calibrationCompleted")
        or context.get("calibration_completed")
        or context.get("calibrationResultAvailable")
        or context.get("calibration_result_available")
    ):
        return "completed"

    if context.get("calibrationError") or context.get("calibration_error"):
        return "failed"

    return "setup_only"


def _get_calibration_fit_metrics(context: Dict[str, Any]) -> Dict[str, Any]:
    fit_metrics = context.get("fitMetrics") or context.get("fit_metrics")
    if isinstance(fit_metrics, dict) and fit_metrics:
        return fit_metrics

    outputs = context.get("outputs", {})
    summary = context.get("summary", {})
    derived: Dict[str, Any] = {}

    objective_value = outputs.get("objectiveValue")
    if isinstance(objective_value, (int, float)):
        derived["objectiveValue"] = float(objective_value)

    r_squared = outputs.get("rSquared")
    if isinstance(r_squared, (int, float)):
        derived["rSquared"] = float(r_squared)

    iterations = outputs.get("iterations")
    if isinstance(iterations, (int, float)):
        derived["iterations"] = int(iterations)

    improvement = summary.get("improvement")
    if isinstance(improvement, (int, float)):
        derived["improvementPct"] = float(improvement)

    run_duration = context.get("runDurationSeconds") or context.get("run_duration_seconds")
    if isinstance(run_duration, (int, float)):
        derived["runDurationSeconds"] = float(run_duration)

    return derived


def _get_calibration_parameter_changes(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    parameter_changes = (
        context.get("parameterChanges")
        or context.get("parameter_changes")
        or context.get("initialVsFinalComparison")
        or context.get("initial_vs_final_comparison")
    )
    if isinstance(parameter_changes, list) and parameter_changes:
        return [change for change in parameter_changes if isinstance(change, dict)]

    outputs = context.get("outputs", {})
    optimized_parameters = outputs.get("optimizedParameters") or outputs.get("optimized_parameters") or {}
    initial_parameters = outputs.get("initialParameters") or outputs.get("initial_params") or {}
    if not isinstance(optimized_parameters, dict) or not isinstance(initial_parameters, dict):
        return []

    derived: List[Dict[str, Any]] = []
    for param, optimized in optimized_parameters.items():
        initial = initial_parameters.get(param)
        if not isinstance(optimized, (int, float)) or not isinstance(initial, (int, float)) or initial == 0:
            continue
        change = float(optimized) - float(initial)
        derived.append(
            {
                "param": param,
                "initial": float(initial),
                "optimized": float(optimized),
                "change": change,
                "percentChange": (change / float(initial)) * 100.0,
            }
        )

    derived.sort(key=lambda item: abs(float(item.get("percentChange", 0.0))), reverse=True)
    return derived


def _get_flux_status(context: Dict[str, Any]) -> str:
    status = context.get("fluxStatus") or context.get("flux_status")
    if status in {"setup_only", "running", "completed", "failed"}:
        return str(status)

    if context.get("fluxFailed") or context.get("flux_failed") or context.get("fluxError") or context.get("flux_error"):
        return "failed"

    if (
        context.get("fluxCompleted")
        or context.get("flux_completed")
        or context.get("fluxResultAvailable")
        or context.get("flux_result_available")
    ):
        return "completed"

    return "setup_only"


def _get_flux_provenance_lines(context: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    mode = context.get("researchDataMode") or context.get("research_data_mode")
    dataset_applied = bool(
        context.get("datasetApplied")
        if context.get("datasetApplied") is not None
        else context.get("dataset_applied")
    )
    dataset_label = (
        context.get("activeDatasetLabel")
        or context.get("active_dataset_label")
        or (context.get("activeDataset") or {}).get("label")
        or "Bordbar reference dataset"
    )
    dataset_fallback_reason = context.get("datasetFallbackReason") or context.get("dataset_fallback_reason")
    calibration_applied = bool(
        context.get("calibrationApplied")
        if context.get("calibrationApplied") is not None
        else context.get("calibratedParametersActive")
        if context.get("calibratedParametersActive") is not None
        else context.get("custom_params_source") not in (None, "defaults")
    )
    calibration_source = (
        context.get("calibrationSource")
        or context.get("customParamsSource")
        or context.get("custom_params_source")
        or "defaults"
    )
    selected_pathway = (context.get("inputs") or {}).get("selectedPathway") or "all"
    applied_count = len((context.get("inputs") or {}).get("appliedConcentrationMetabolites") or context.get("datasetAppliedMetabolites") or [])

    if mode == "custom_user_data_mode":
        if dataset_applied:
            lines.append(f"Data mode: custom user data ({dataset_label})")
            lines.append(f"Dataset applied: {applied_count} mapped metabolites")
        else:
            lines.append(f"Data mode: custom user data ({dataset_label})")
            lines.append(
                "Dataset fallback used"
                + (f" ({dataset_fallback_reason})" if dataset_fallback_reason else "")
            )
    else:
        lines.append("Data mode: Bordbar reference")
        lines.append("Dataset applied: Bordbar default flow")

    if calibration_applied:
        if calibration_source == "provided":
            lines.append("Calibration: latest calibration applied")
        elif calibration_source == "auto_loaded":
            lines.append("Calibration: auto-loaded from saved research state")
        else:
            lines.append("Calibration: applied")
    else:
        lines.append("Calibration: default Bordbar parameters retained")

    lines.append(f"Selected pathway: {selected_pathway}")
    return lines


def _get_flux_result_lines(context: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    flux_status = _get_flux_status(context)
    outputs = context.get("outputs", {})
    summary = context.get("summary", {})

    if flux_status == "completed" and outputs:
        dominant = summary.get("dominantPathway", "unknown")
        lines.append(f"Dominant pathway: {dominant}")

        top_reactions = summary.get("topReactions", [])
        if top_reactions:
            reactions = []
            for r in top_reactions[:3]:
                if not isinstance(r, dict):
                    continue
                name = r.get("reaction", "unknown")
                flux = r.get("flux", 0)
                try:
                    reactions.append(f"{name} ({float(flux):.2e})")
                except (TypeError, ValueError):
                    reactions.append(f"{name} ({flux})")
            if reactions:
                lines.append(f"Top reactions by flux: {', '.join(reactions)}")

        total_flux = outputs.get("totalFlux")
        if isinstance(total_flux, (int, float)):
            lines.append(f"Total metabolic flux: {float(total_flux):.2e} arbitrary units")
    elif flux_status == "running":
        lines.append("Flux estimation is still running; only setup provenance is available so far")
    elif flux_status == "failed":
        lines.append("Flux estimation failed before a completed result was produced")
        flux_error = context.get("fluxError") or context.get("flux_error")
        if isinstance(flux_error, str) and flux_error.strip():
            lines.append(f"Failure detail: {flux_error.strip()}")
    else:
        lines.append("Flux result is not available yet")

    return lines


def _get_flux_context_references(context: Dict[str, Any], message_lower: str) -> List[str]:
    refs: List[str] = []
    if any(keyword in message_lower for keyword in ("bordbar", "custom", "dataset", "data", "calibration", "applied", "loaded", "provenance", "fallback")):
        refs.extend([
            "researchDataMode",
            "datasetApplied",
            "datasetFallbackReason",
            "calibrationApplied",
            "calibrationSource",
        ])
    if any(keyword in message_lower for keyword in ("pathway", "dominant", "flux", "result", "summary", "interpret")):
        refs.extend([
            "fluxStatus",
            "resultSummary",
            "summary",
            "summary.dominantPathway",
            "summary.topReactions",
            "outputs.totalFlux",
            "outputs.fluxes",
        ])
    return refs


def _build_grounded_flux_fallback_response(
    message: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Return a grounded flux response when the model answer is empty."""
    message_lower = message.lower()
    lines: List[str] = []
    refs: List[str] = []

    provenance_lines = _get_flux_provenance_lines(context)
    if provenance_lines:
        lines.extend(provenance_lines)
        refs.extend([
            "researchDataMode",
            "activeDatasetLabel",
            "datasetApplied",
            "calibrationApplied",
            "calibrationSource",
            "fluxStatus",
        ])

    result_lines = _get_flux_result_lines(context)
    if result_lines:
        lines.extend(result_lines)
        refs.extend([
            "summary",
            "summary.dominantPathway",
            "summary.topReactions",
            "outputs.totalFlux",
            "outputs.fluxes",
        ])

    if any(keyword in message_lower for keyword in ("pathway", "flux", "result", "summary", "interpret", "dominant")):
        refs.extend(_get_flux_context_references(context, message_lower))

    if not lines:
        lines.append("I have the flux context, but not enough detail to summarize the result.")

    follow_ups = [
        "Which pathways are most active?",
        "Is this using my uploaded data or Bordbar?",
        "Was the latest calibration applied?",
        "What does the dominant pathway imply biologically?",
    ]

    return {
        "message": "\n\n".join(lines),
        "contextReferences": sorted(set(refs)),
        "confidence": "medium",
        "suggestedFollowUps": follow_ups,
    }


def _find_requested_metabolites(message: str, context: Dict[str, Any]) -> List[str]:
    """Match metabolite names mentioned in the user message."""
    message_lower = message.lower()
    names = _get_simulation_metabolite_names(context)
    matched: List[str] = []

    for name in sorted(set(names), key=len, reverse=True):
        if not name:
            continue
        pattern = rf"\b{re.escape(name)}\b"
        if re.search(pattern, message, flags=re.IGNORECASE):
            matched.append(name)

    return matched


def build_direct_simulation_metabolite_response(
    message: str,
    context: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Return a deterministic answer for direct metabolite concentration questions."""
    if context.get("moduleType") != "simulation":
        return None

    message_lower = message.lower()
    requested_metabolites = _find_requested_metabolites(message, context)

    if not requested_metabolites:
        return None

    if not any(keyword in message_lower for keyword in SIMULATION_CONCENTRATION_KEYWORDS):
        return None

    profiles = _get_simulation_metabolite_profiles(context)
    profile_by_name = {
        str(profile.get("metabolite", "")).lower(): profile
        for profile in profiles
        if profile.get("metabolite")
    }

    lines: List[str] = []
    refs = ["outputs.metabolites.profiles", "outputs.metabolites.finalValues"]

    for metabolite in requested_metabolites:
        profile = profile_by_name.get(metabolite.lower())
        if not profile:
            continue

        final_value = profile.get("final")
        if final_value is None:
            continue

        initial_value = profile.get("initial")
        delta_value = profile.get("delta")
        percent_change = profile.get("percentChange")
        minimum_value = profile.get("minimum")
        maximum_value = profile.get("maximum")
        direction = profile.get("direction")
        percent_change_text = (
            f"{float(percent_change):.1f}%"
            if isinstance(percent_change, (int, float))
            else "n/a"
        )

        lines.append(
            (
                f"{metabolite} final concentration is {_format_number(final_value)}. "
                f"It started at {_format_number(initial_value)}, "
                f"changed by {_format_number(delta_value)} "
                f"({percent_change_text}), "
                f"with a range of {_format_number(minimum_value)} to {_format_number(maximum_value)}. "
                f"Direction: {direction}."
            )
        )

    if not lines:
        return None

    follow_ups = [
        "Which metabolite changed the most overall?",
        "What does this mean for energy stress in the run?",
        "How do the other metabolites compare at the end of the simulation?",
    ]

    return {
        "message": "\n".join(lines),
        "contextReferences": refs,
        "confidence": "high",
        "suggestedFollowUps": follow_ups,
    }


def _build_grounded_simulation_fallback_response(
    message: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Return a grounded simulation response when the model answer is empty."""
    message_lower = message.lower()
    lines: List[str] = []
    refs: List[str] = []
    provenance_lines = _get_simulation_provenance_lines(context)

    if provenance_lines:
        lines.extend(provenance_lines)
        refs.extend(
            [
                "researchDataMode",
                "activeDatasetLabel",
                "datasetApplied",
                "calibrationSource",
            ]
        )

    time_range = context.get("outputs", {}).get("timeRange", {})
    if time_range:
        lines.append(
            f"The simulation ran for {_format_number(time_range.get('end'))} days across "
            f"{_format_number(time_range.get('n_points'))} data points."
        )
        refs.append("outputs.timeRange")

    params = context.get("parameters", {})
    if params:
        solver = params.get("solver_method", "unknown")
        ph_type = params.get("ph_perturbation_type", "None")
        if ph_type and ph_type != "None":
            lines.append(
                f"It used the {solver} solver with a {ph_type} pH perturbation "
                f"({params.get('ph_severity', 'unknown')} severity)."
            )
        else:
            lines.append(f"It used the {solver} solver with baseline pH conditions.")
        refs.append("parameters")

    selected_metabolites = context.get("selectedMetabolites") or []
    if selected_metabolites:
        lines.append(
            f"Selected metabolites in view: {', '.join(selected_metabolites[:5])}."
        )
        refs.append("selectedMetabolites")

    trends = context.get("summary", {}).get("notableTrends", [])
    if trends:
        high_changes = [trend for trend in trends if trend.get("magnitude") == "high"]
        if high_changes:
            trend_bits = [
                f"{trend.get('metabolite', 'unknown')} {trend.get('direction', 'changed')}"
                for trend in high_changes[:3]
            ]
            lines.append(f"Strongest stress signals: {', '.join(trend_bits)}.")
        else:
            lines.append("Most tracked key metabolites remained relatively stable.")
        refs.append("summary.notableTrends")

    if any(keyword in message_lower for keyword in ("glc", "lac", "atp", "adp", "b23pg", "nadh", "gsh", "pyr", "metabolite")):
        metabolites = context.get("outputs", {}).get("metabolites", {})
        key_metabolites = metabolites.get("keyMetabolites", [])
        if key_metabolites:
            lines.append(f"Key metabolites tracked: {', '.join(key_metabolites[:5])}.")
            refs.append("outputs.metabolites.keyMetabolites")

    if not lines:
        lines.append("I have the simulation context, but I need a more specific question to ground a response.")

    return {
        "message": "\n\n".join(lines),
        "contextReferences": refs,
        "confidence": "medium",
        "suggestedFollowUps": [
            "Which metabolites show the strongest changes?",
            "How should I interpret the solver and pH settings?",
            "What changed most between the start and end of the simulation?",
        ],
    }


def _build_grounded_calibration_fallback_response(
    message: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Return a grounded calibration response when the model answer is empty."""
    inputs = context.get("inputs", {})
    outputs = context.get("outputs", {})
    summary = context.get("summary", {})
    provenance_lines = _get_calibration_provenance_lines(context)

    lines: List[str] = []
    refs: List[str] = []

    if provenance_lines:
        lines.extend(provenance_lines)
        refs.extend(
            [
                "researchDataMode",
                "activeDatasetLabel",
                "datasetApplied",
                "inputs.selectedParameters",
                "inputs.selectedParameterFamilies",
                "inputs.selectedOptimizationStrategy",
                "inputs.strategyLabel",
                "inputs.canonicalTaxonomySource",
                "calibrationStatus",
                "resultSummary",
            ]
        )

    target_metabolites = inputs.get("targetMetabolites") or []
    if target_metabolites:
        lines.append(f"Target metabolites: {', '.join(target_metabolites[:5])}.")
        refs.append("inputs.targetMetabolites")

    calibration_status = _get_calibration_status(context)
    calibration_result_available = calibration_status == "completed"
    calibration_error = context.get("calibrationError") or context.get("calibration_error")

    if calibration_status == "running":
        lines.append("Calibration is currently running; only the setup context is available so far.")
    elif calibration_status == "failed":
        lines.append("Calibration failed before a completed result was produced.")
        if isinstance(calibration_error, str) and calibration_error.strip():
            lines.append(f"Failure detail: {calibration_error.strip()}")
            refs.append("calibrationError")
    elif calibration_result_available and inputs.get("selectedParameters"):
        lines.append(
            f"The calibration optimized {_format_number(len(inputs.get('selectedParameters') or []))} parameters."
        )
        refs.append("inputs.selectedParameters")
    else:
        lines.append("Calibration setup is ready, but no result has been produced yet.")

    if calibration_result_available:
        refs.append("fitMetrics")
        objective_value = outputs.get("objectiveValue")
        if objective_value is not None:
            lines.append(f"The final objective value is {_format_number(objective_value)}.")
            refs.append("outputs.objectiveValue")

        r_squared = outputs.get("rSquared")
        if r_squared is not None:
            lines.append(f"Model fit quality is R²={float(r_squared):.3f}.")
            refs.append("outputs.rSquared")

        improvement = summary.get("improvement")
        if improvement is not None:
            lines.append(f"Objective improvement is {float(improvement):.1f}% relative to the starting point.")
            refs.append("summary.improvement")

        run_duration = context.get("runDurationSeconds") or context.get("run_duration_seconds")
        if isinstance(run_duration, (int, float)):
            lines.append(f"Run duration was approximately {float(run_duration):.1f} seconds.")
            refs.append("runDurationSeconds")

        top_changes = summary.get("topChanges") or _get_calibration_parameter_changes(context)
        if top_changes:
            change_bits: List[str] = []
            for change in top_changes[:3]:
                if not isinstance(change, dict):
                    continue

                param = change.get("param", "unknown")
                change_value = change.get("change")
                percent_change = change.get("percentChange")
                change_text = _format_number(change_value)
                if isinstance(percent_change, (int, float)):
                    pct_text = f"{percent_change:+.1f}%"
                else:
                    pct_text = "n/a"

                change_bits.append(f"{param} {change_text} ({pct_text})")

            if change_bits:
                lines.append(f"Largest parameter shifts: {', '.join(change_bits)}.")
                refs.append("summary.topChanges")
        elif outputs.get("optimizedParameters") and outputs.get("initialParameters"):
            derived_changes = _get_calibration_parameter_changes(context)
            if derived_changes:
                change_bits = []
                for change in derived_changes[:3]:
                    param = change.get("param", "unknown")
                    delta = change.get("change")
                    percent_delta = change.get("percentChange")
                    change_bits.append(
                        f"{param} {_format_number(delta)} ({float(percent_delta):+.1f}%)"
                    )

                lines.append(f"Largest parameter shifts: {', '.join(change_bits)}.")
                refs.append("outputs.optimizedParameters")

        result_summary = context.get("resultSummary") or context.get("result_summary")
        if isinstance(result_summary, str) and result_summary.strip():
            lines.append(result_summary.strip())

    if not lines:
        lines.append("I have the calibration context, but not enough detail to summarize the fit.")

    return {
        "message": "\n\n".join(lines),
        "contextReferences": refs,
        "confidence": "high" if lines else "low",
        "suggestedFollowUps": [
            "Which parameters had the biggest impact on the fit?",
            "How well did the model converge?",
            "What does the R² value tell us about the model quality?",
            "Would different optimization methods help?",
        ],
    }


class OpenAIService:
    """Service for interacting with OpenAI API"""
    
    def __init__(self):
        if is_openai_configured():
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        else:
            self.client = None
    
    async def generate_response(
        self,
        message: str,
        context: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Generate a response from OpenAI based on user message and context
        """
        print(f"[DEBUG] generate_response called")
        print(f"[DEBUG] client exists: {self.client is not None}")

        direct_answer = build_direct_simulation_metabolite_response(message, context)
        if direct_answer is not None:
            return direct_answer

        if not self.client:
            if context.get("moduleType") == "simulation":
                return _build_grounded_simulation_fallback_response(message, context)

            if context.get("moduleType") == "flux-analysis":
                return _build_grounded_flux_fallback_response(message, context)

            if context.get("moduleType") == "pathway-visualization":
                return _build_grounded_pathway_fallback_response(message, context)

            if context.get("moduleType") in ("calibration", "calibration-registry"):
                return _build_grounded_calibration_fallback_response(message, context)

            return {
                "message": "OpenAI is not configured. Please set OPENAI_API_KEY environment variable.",
                "contextReferences": [],
                "confidence": "low",
                "suggestedFollowUps": [],
                "error": "openai_not_configured"
            }
        
        try:
            # Build the system prompt with context
            system_prompt = self._build_system_prompt(context)
            
            # Build conversation messages
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": self._build_user_prompt(message, context)}
            ]
            
            # Add conversation history if provided
            if conversation_history:
                # Insert history before the current user message
                messages = messages[:1] + conversation_history + messages[1:]
            
            # Call OpenAI API
            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                # Newer chat models reject max_tokens; max_completion_tokens is the supported cap.
                max_completion_tokens=settings.openai_max_tokens,
                temperature=settings.openai_temperature
            )
            
            answer = response.choices[0].message.content
            context_refs = self._extract_context_references(message, context)
            follow_ups = self._generate_follow_ups(context, message)

            if not isinstance(answer, str) or not answer.strip():
                if context.get("moduleType") == "simulation":
                    return _build_grounded_simulation_fallback_response(message, context)
                if context.get("moduleType") == "flux-analysis":
                    return _build_grounded_flux_fallback_response(message, context)
                if context.get("moduleType") == "pathway-visualization":
                    return _build_grounded_pathway_fallback_response(message, context)
                if context.get("moduleType") in ("calibration", "calibration-registry"):
                    return _build_grounded_calibration_fallback_response(message, context)

                return {
                    "message": "The model returned an empty answer. I still received your research context, but I could not produce a grounded response.",
                    "contextReferences": context_refs,
                    "confidence": "low",
                    "suggestedFollowUps": follow_ups,
                    "error": "empty_model_response"
                }

            return {
                "message": answer,
                "contextReferences": context_refs,
                "confidence": "high" if answer else "low",
                "suggestedFollowUps": follow_ups
            }
            
        except Exception as e:
            return {
                "message": f"Error generating response: {str(e)}",
                "contextReferences": [],
                "confidence": "low",
                "suggestedFollowUps": [],
                "error": str(e)
            }
    
    def _build_system_prompt(self, context: Dict[str, Any]) -> str:
        """Build system prompt with context"""
        module_type = context.get('moduleType', 'unknown')
        module_title = context.get('moduleTitle', 'Unknown Module')
        
        base_prompt = f"""You are RoBoCop, an expert scientific assistant for the {module_title} module.

Your role is to help researchers understand their results by providing clear, accurate, and grounded interpretations. Always base your answers on the actual data provided in the context.

Key guidelines:
- Be concise but thorough
- Reference specific data points when possible
- Explain biological/chemical implications
- Suggest next steps when appropriate
- Stay grounded in the provided context"""
        
        # Add module-specific instructions
        if module_type == 'simulation':
            base_prompt += """

For Simulation results:
- Focus on metabolite trends and patterns
- selectedMetabolites are only the current chart focus, not the only available data
- Use outputs.metabolites.profiles and outputs.metabolites.finalValues to answer questions about any metabolite
- If the user asks for a specific metabolite concentration, read the final value from the profile data
- Do not say a metabolite is unavailable if it appears in the full profile table
- Explain whether the run used Bordbar defaults or custom user data
- Mention the active dataset label when present
- Explain whether calibration was auto-loaded, provided, or default Bordbar parameters
- Mention the fallback reason if custom data could not be applied
- Explain pH perturbation effects if present
- Highlight key biological insights
- Consider time-dependent changes"""
        
        elif module_type == 'calibration':
            base_prompt += """

For Calibration results:
- Explain the current calibration setup when no result is available
- Clearly distinguish setup only, running, completed, and failed calibration states
- State whether the run is using Bordbar/reference data or custom uploaded data
- State whether a previous calibration is auto-loaded, freshly provided, or default Bordbar
- Mention the selected parameters and canonical parameter families
- Mention the selected optimization strategy family by name
- Explain whether the current selection is the recommended subset or the advanced canonical inventory
- When a result exists, focus on parameter optimization outcomes, model fit quality (R² values), important parameter changes, result summary, and convergence behavior"""

        elif module_type == 'flux-analysis':
            base_prompt += """

For Flux Analysis:
- Explain whether the result is setup-only, running, completed, or failed
- State whether the active dataset is Bordbar/reference or custom uploaded data
- Mention whether the latest calibration was applied or auto-loaded
- Ground interpretation in the dominant pathways and top fluxes actually present in the context
- If no completed result exists yet, do not invent flux interpretation
- If a completed result exists, explain the dominant pathway, top reactions, and what the flux balance suggests biologically"""
        elif module_type == 'pathway-visualization':
            base_prompt += """

For Pathway Visualization:
- Explain whether the pathway network is setup-only, loading, completed, or failed
- State whether the current research context is Bordbar/reference or custom user data
- Mention whether the latest calibration is active, auto-loaded, or defaults remain in place
- If playback is active, interpret the current frame/timepoint rather than treating the map as static
- Mention the dominant pathway, dominant signal, and any accumulating/depleting metabolites when present
- Ground answers in the actual network size, key pathway groups, result summary, and replay source
- If the network is still loading, do not invent pathway interpretation
- If the network is ready, explain the most represented pathways and what the map implies structurally"""
        
        return base_prompt
    
    def _build_user_prompt(self, message: str, context: Dict[str, Any]) -> str:
        """Build user prompt with context"""
        context_str = json.dumps(context, indent=2, default=str)
        
        return f"""User Question: {message}

Research Context:
{context_str}

Please provide a detailed analysis answering the user's question based on the provided context."""
    
    def _extract_context_references(self, message: str, context: Dict[str, Any]) -> List[str]:
        """Extract relevant context references based on message content"""
        refs = []
        message_lower = message.lower()
        
        # Simple keyword-based reference extraction
        if 'trend' in message_lower or 'change' in message_lower:
            if 'summary' in context and 'notableTrends' in context['summary']:
                refs.append('notableTrends')
        
        if 'parameter' in message_lower or 'setting' in message_lower:
            if 'parameters' in context:
                refs.append('parameters')
        if context.get("moduleType") in ('calibration', 'calibration-registry'):
            if any(keyword in message_lower for keyword in ('strategy', 'method')):
                refs.append('inputs.selectedOptimizationStrategy')
                refs.append('inputs.strategyLabel')
            if any(keyword in message_lower for keyword in ('family', 'taxonomy', 'canonical')):
                refs.append('inputs.selectedParameterFamilies')
                refs.append('inputs.canonicalTaxonomySource')
            if any(keyword in message_lower for keyword in ('fail', 'error')):
                refs.append('calibrationError')
            if any(keyword in message_lower for keyword in ('bordbar', 'custom', 'dataset', 'data', 'setup', 'provenance')):
                refs.append('researchDataMode')
                refs.append('datasetApplied')
            if any(keyword in message_lower for keyword in ('calibration', 'applied', 'loaded', 'result', 'setup', 'provenance', 'running', 'failed', 'completed')):
                refs.append('calibrationApplied')
                refs.append('calibrationSource')
                refs.append('calibrationStatus')
            if any(keyword in message_lower for keyword in ('result', 'fit', 'r2', 'r²', 'converge', 'improvement', 'loss', 'change')):
                refs.append('calibrationResultAvailable')
                refs.append('outputs.rSquared')
                refs.append('fitMetrics')
                refs.append('parameterChanges')
                refs.append('resultSummary')
        if context.get("moduleType") == 'flux-analysis':
            if any(keyword in message_lower for keyword in ('bordbar', 'custom', 'dataset', 'data', 'setup', 'provenance', 'fallback')):
                refs.append('researchDataMode')
                refs.append('datasetApplied')
                refs.append('calibrationApplied')
                refs.append('calibrationSource')
            if any(keyword in message_lower for keyword in ('pathway', 'dominant', 'flux', 'result', 'summary', 'interpret')):
                refs.append('fluxStatus')
                refs.append('resultSummary')
                refs.append('summary')
                refs.append('summary.dominantPathway')
                refs.append('summary.topReactions')
                refs.append('outputs.totalFlux')
                refs.append('outputs.fluxes')
        if context.get("moduleType") == 'pathway-visualization':
            if any(keyword in message_lower for keyword in ('bordbar', 'custom', 'dataset', 'data', 'setup', 'provenance', 'fallback')):
                refs.append('researchDataMode')
                refs.append('datasetApplied')
                refs.append('calibrationApplied')
                refs.append('calibrationSource')
            if any(keyword in message_lower for keyword in ('playback', 'frame', 'timepoint', 'replay', 'current state', 'current frame')):
                refs.extend([
                    'playbackReady',
                    'playbackFrameIndex',
                    'playbackFrameCount',
                    'playbackTimepoint',
                    'selectedTimepointSummary',
                    'replaySource',
                ])
            if any(keyword in message_lower for keyword in ('dominant', 'signal', 'accumulat', 'deplet')):
                refs.extend([
                    'networkStateSummary',
                    'dominantPathway',
                    'dominantSignal',
                    'topAccumulatingMetabolites',
                    'topDepletingMetabolites',
                ])
            if any(keyword in message_lower for keyword in ('pathway', 'network', 'node', 'edge', 'graph', 'result', 'summary', 'interpret')):
                refs.append('pathwayStatus')
                refs.append('resultSummary')
                refs.append('summary')
                refs.append('summary.keyPathways')
                refs.append('summary.keySignals')
                refs.append('outputs.networkStats')

        if 'metabolite' in message_lower:
            if 'outputs' in context and 'metabolites' in context['outputs']:
                metabolites = context['outputs']['metabolites']
                if 'profiles' in metabolites or 'finalValues' in metabolites:
                    refs.append('outputs.metabolites.profiles')
                else:
                    refs.append('metabolites')

        if any(keyword in message_lower for keyword in SIMULATION_PROVENANCE_KEYWORDS):
            refs.append('provenance')
        
        if 'time' in message_lower or 'duration' in message_lower:
            if 'outputs' in context and 'timeRange' in context['outputs']:
                refs.append('timeRange')
        
        return refs
    
    def _generate_follow_ups(self, context: Dict[str, Any], current_message: str) -> List[str]:
        """Generate relevant follow-up questions"""
        module_type = context.get('moduleType', 'unknown')
        
        if module_type == 'simulation':
            return [
                "Which metabolites show the most dramatic changes?",
                "How does pH perturbation affect the results?",
                "What biological processes are most active?",
                "Should I investigate any specific metabolites further?"
            ]
        elif module_type == 'flux-analysis':
            flux_status = _get_flux_status(context)
            if flux_status == 'completed':
                return [
                    "Which pathways are most active?",
                    "What are the top flux-driving reactions?",
                    "Is this based on my uploaded data or Bordbar?",
                    "Was the latest calibration applied?",
                ]
            if flux_status == 'running':
                return [
                    "What provenance is already available?",
                    "Which pathway is likely to dominate?",
                    "Is my uploaded dataset active here?",
                    "Was the latest calibration applied?",
                ]
            if flux_status == 'failed':
                return [
                    "Why did flux estimation fail?",
                    "What should I inspect next?",
                    "Is my uploaded dataset still active?",
                    "How can I rerun this on Bordbar defaults?",
                ]
            return [
                "Is this using my uploaded data or Bordbar?",
                "Which pathways are most active?",
                "Was the latest calibration applied?",
                "What should I estimate next?",
            ]
        elif module_type == 'pathway-visualization':
            pathway_status = str(context.get('pathwayStatus') or context.get('pathway_status') or 'setup_only')
            playback_ready = bool(
                context.get("playbackReady")
                if context.get("playbackReady") is not None
                else context.get("playback_ready")
                if context.get("playback_ready") is not None
                else False
            )
            playback_index = context.get("playbackFrameIndex") if context.get("playbackFrameIndex") is not None else context.get("playback_frame_index")
            playback_count = context.get("playbackFrameCount") or context.get("playback_frame_count") or 0
            playback_timepoint = context.get("playbackTimepoint") if context.get("playbackTimepoint") is not None else context.get("playback_timepoint")
            dominant_pathway = context.get("dominantPathway") or context.get("dominant_pathway")
            if pathway_status == 'completed':
                if playback_ready and playback_index is not None:
                    playback_line = f"frame {int(playback_index) + 1}/{int(playback_count) if playback_count else int(playback_index) + 1}"
                    if playback_timepoint is not None:
                        playback_line += f" at t={float(playback_timepoint):.2f} days"
                    dominant_prompt = (
                        f"What is happening in {dominant_pathway} at this replay state?"
                        if dominant_pathway
                        else "Which pathway is most active at this replay state?"
                    )
                    data_prompt = (
                        "Which metabolites are accumulating here?"
                        if context.get('researchDataMode') == 'custom_user_data_mode'
                        else 'What is changing most in this replay?'
                    )
                    provenance_prompt = (
                        "Is this replay coming from my uploaded data or Bordbar?"
                        if context.get('researchDataMode') == 'custom_user_data_mode'
                        else 'Is this replay using Bordbar reference data?'
                    )
                    return [
                        f"What does {playback_line} represent?",
                        dominant_prompt,
                        data_prompt,
                        provenance_prompt,
                    ]
                return [
                    "Which pathways are most represented?",
                    "What does the network provenance say?",
                    "Is this using my uploaded data or Bordbar?",
                    "What does the map suggest structurally?",
                ]
            if pathway_status == 'running':
                return [
                    "What provenance is already available?",
                    "Which pathway group is likely to be largest?",
                    "Is my uploaded dataset active here?",
                    "Was the latest calibration applied?",
                ]
            if pathway_status == 'failed':
                return [
                    "Why did the pathway map fail?",
                    "What should I inspect next?",
                    "Is my uploaded dataset still active?",
                    "How can I rerun this on Bordbar defaults?",
                ]
            return [
                "Is this using my uploaded data or Bordbar?",
                "Which pathways are most represented?",
                "Was the latest calibration applied?",
                "What should I inspect next?",
            ]
        elif module_type == 'calibration':
            calibration_status = _get_calibration_status(context)
            if calibration_status == 'running':
                return [
                    "What parameters are currently selected?",
                    "Is the calibration still running?",
                    "What optimization strategy is active?",
                    "Is this the recommended subset or the advanced canonical inventory?",
                ]
            if calibration_status == 'failed':
                return [
                    "Why did this calibration fail?",
                    "What should I inspect next?",
                    "Can I rerun with a different strategy?",
                    "Is the current setup using Bordbar or uploaded data?",
                ]
            if calibration_status != 'completed':
                return [
                    "What parameters are currently selected?",
                    "What optimization strategy is active?",
                    "Is this using Bordbar or my uploaded data?",
                    "Is this the recommended subset or the advanced canonical inventory?",
                ]
            return [
                "Which parameters had the biggest impact on the fit?",
                "How well did the model converge?",
                "What does the R² value tell us about the model quality?",
                "Would different optimization methods help?"
            ]
        else:
            return [
                "What are the key findings from this analysis?",
                "Are there any unexpected patterns in the data?",
                "What should I investigate next?",
                "How do these results compare to expectations?"
            ]


# Global service instance
openai_service = OpenAIService()


def _get_pathway_status(context: Dict[str, Any]) -> str:
    status = context.get("pathwayStatus") or context.get("pathway_status")
    if status in {"setup_only", "running", "completed", "failed"}:
        return str(status)

    if context.get("pathwayFailed") or context.get("pathway_failed") or context.get("pathwayError") or context.get("pathway_error"):
        return "failed"

    if context.get("pathwayCompleted") or context.get("pathway_completed") or context.get("pathwayResultAvailable") or context.get("pathway_result_available"):
        return "completed"

    return "setup_only"


def _get_pathway_playback_lines(context: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    status = _get_pathway_status(context)
    playback_ready = bool(
        context.get("playbackReady")
        if context.get("playbackReady") is not None
        else context.get("playback_ready")
        if context.get("playback_ready") is not None
        else False
    )
    playback_index = context.get("playbackFrameIndex") if context.get("playbackFrameIndex") is not None else context.get("playback_frame_index")
    playback_count = context.get("playbackFrameCount") or context.get("playback_frame_count") or 0
    playback_timepoint = context.get("playbackTimepoint") if context.get("playbackTimepoint") is not None else context.get("playback_timepoint")
    selected_timepoint_summary = context.get("selectedTimepointSummary") or context.get("selected_timepoint_summary")
    replay_source = context.get("replaySource") or context.get("replay_source")
    network_state_summary = context.get("networkStateSummary") or context.get("network_state_summary")
    dominant_pathway = context.get("dominantPathway") or context.get("dominant_pathway")
    dominant_signal = context.get("dominantSignal") or context.get("dominant_signal") or {}
    top_accumulating = context.get("topAccumulatingMetabolites") or context.get("top_accumulating_metabolites") or []
    top_depleting = context.get("topDepletingMetabolites") or context.get("top_depleting_metabolites") or []

    if selected_timepoint_summary:
        lines.append(f"Replay state: {selected_timepoint_summary}")
    elif playback_ready and playback_index is not None:
        playback_line = f"Playback frame {int(playback_index) + 1}/{int(playback_count) if playback_count else int(playback_index) + 1}"
        if playback_timepoint is not None:
            playback_line += f" at t={float(playback_timepoint):.2f} days"
        lines.append(playback_line)
    elif status == "running":
        lines.append("Playback: replay is still loading")
    else:
        lines.append("Playback: static network snapshot")

    if replay_source:
        lines.append(f"Replay source: {replay_source}")

    if network_state_summary:
        lines.append(f"Network state: {network_state_summary}")

    if dominant_pathway:
        lines.append(f"Dominant pathway: {dominant_pathway}")

    if isinstance(dominant_signal, dict) and dominant_signal.get("label") is not None:
        value = dominant_signal.get("value", 0)
        signal_line = f"Dominant signal: {dominant_signal.get('label')} {float(value):+.2e}"
        if dominant_signal.get("pathway"):
            signal_line += f" ({dominant_signal.get('pathway')})"
        lines.append(signal_line)

    if isinstance(top_accumulating, list) and top_accumulating:
        accum_parts = []
        for shift in top_accumulating[:3]:
            if isinstance(shift, dict):
                metabolite = shift.get("metabolite", "unknown")
                delta = float(shift.get("delta", 0))
                accum_parts.append(f"{metabolite} {delta:+.2e}")
        if accum_parts:
            lines.append(f"Accumulating: {', '.join(accum_parts)}")

    if isinstance(top_depleting, list) and top_depleting:
        deplete_parts = []
        for shift in top_depleting[:3]:
            if isinstance(shift, dict):
                metabolite = shift.get("metabolite", "unknown")
                delta = float(shift.get("delta", 0))
                deplete_parts.append(f"{metabolite} {delta:.2e}")
        if deplete_parts:
            lines.append(f"Depleting: {', '.join(deplete_parts)}")

    return lines


def _get_pathway_provenance_lines(context: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    mode = context.get("researchDataMode") or context.get("research_data_mode")
    dataset_label = (
        context.get("activeDatasetLabel")
        or context.get("active_dataset_label")
        or (context.get("activeDataset") or {}).get("label")
        or "Bordbar reference dataset"
    )
    calibration_applied = bool(
        context.get("calibrationApplied")
        if context.get("calibrationApplied") is not None
        else context.get("calibratedParametersActive")
        if context.get("calibratedParametersActive") is not None
        else False
    )
    calibration_source = (
        context.get("calibrationSource")
        or context.get("customParamsSource")
        or context.get("custom_params_source")
        or "defaults"
    )
    status = _get_pathway_status(context)
    summary = context.get("summary") or {}
    outputs = context.get("outputs") or {}
    stats = outputs.get("networkStats") or {}

    if mode == "custom_user_data_mode":
        lines.append(f"Data mode: custom user data ({dataset_label})")
    else:
        lines.append("Data mode: Bordbar reference")

    if calibration_applied:
        if calibration_source == "provided":
            lines.append("Calibration: latest calibration active")
        elif calibration_source == "auto_loaded":
            lines.append("Calibration: auto-loaded calibration active")
        else:
            lines.append("Calibration: calibration active")
    else:
        lines.append("Calibration: default Bordbar parameters retained")

    lines.append(f"Pathway state: {status.replace('_', ' ')}")
    lines.append(
        f"Network size: {_format_number(stats.get('nodes'))} nodes, {_format_number(stats.get('edges'))} edges"
    )

    lines.extend(_get_pathway_playback_lines(context))

    if isinstance(summary.get("keyPathways"), list) and summary.get("keyPathways"):
        lines.append(f"Key pathways: {', '.join(summary.get('keyPathways')[:3])}")

    return lines


def _build_grounded_pathway_fallback_response(message: str, context: Dict[str, Any]) -> Dict[str, Any]:
    refs: List[str] = []
    lines: List[str] = []

    status = _get_pathway_status(context)
    summary = context.get("summary") or {}
    outputs = context.get("outputs") or {}
    stats = outputs.get("networkStats") or {}
    result_summary = context.get("resultSummary") or context.get("result_summary")
    playback_ready = bool(
        context.get("playbackReady")
        if context.get("playbackReady") is not None
        else context.get("playback_ready")
        if context.get("playback_ready") is not None
        else False
    )
    playback_index = context.get("playbackFrameIndex") if context.get("playbackFrameIndex") is not None else context.get("playback_frame_index")
    playback_count = context.get("playbackFrameCount") or context.get("playback_frame_count") or 0
    playback_timepoint = context.get("playbackTimepoint") if context.get("playbackTimepoint") is not None else context.get("playback_timepoint")

    lines.extend(_get_pathway_provenance_lines(context))

    if status == "completed":
        lines.append(
            f"The network map contains {_format_number(stats.get('nodes'))} nodes and {_format_number(stats.get('edges'))} edges."
        )
        if isinstance(summary.get("keyPathways"), list) and summary.get("keyPathways"):
            lines.append(f"The most represented pathways are {', '.join(summary.get('keyPathways')[:3])}.")
        if isinstance(result_summary, str) and result_summary.strip():
            lines.append(result_summary.strip())
        refs.extend([
            "outputs.networkStats",
            "summary.keyPathways",
            "resultSummary",
            "playbackReady",
            "playbackFrameIndex",
            "playbackFrameCount",
            "playbackTimepoint",
            "selectedTimepointSummary",
            "networkStateSummary",
            "dominantPathway",
            "dominantSignal",
            "topAccumulatingMetabolites",
            "topDepletingMetabolites",
            "replaySource",
        ])
    elif status == "running":
        lines.append("The pathway network is still loading, so only the setup context is available so far.")
        refs.extend([
            "pathwayStatus",
            "playbackReady",
            "playbackFrameIndex",
            "playbackFrameCount",
            "playbackTimepoint",
            "selectedTimepointSummary",
        ])
    elif status == "failed":
        lines.append("The pathway visualization failed before a completed result was produced.")
        pathway_error = context.get("pathwayError") or context.get("pathway_error")
        if isinstance(pathway_error, str) and pathway_error.strip():
            lines.append(f"Failure detail: {pathway_error.strip()}")
            refs.append("pathwayError")
    else:
        lines.append("The pathway network is ready, but no completed result has been produced yet.")
        refs.extend([
            "pathwayStatus",
            "playbackReady",
            "selectedTimepointSummary",
        ])

    return {
        "message": "\n\n".join(lines),
        "contextReferences": refs or [
            "researchDataMode",
            "calibrationApplied",
            "calibrationSource",
            "playbackReady",
            "playbackFrameIndex",
            "playbackFrameCount",
            "playbackTimepoint",
            "selectedTimepointSummary",
            "networkStateSummary",
            "outputs.networkStats",
            "summary.keyPathways",
        ],
        "confidence": "high" if status == "completed" else "medium",
        "suggestedFollowUps": [
            f"What does frame {int(playback_index) + 1}/{int(playback_count) if playback_count else int(playback_index) + 1} represent?"
            if playback_ready and playback_index is not None
            else "Which pathways are most represented?",
            "Which metabolites are accumulating here?" if playback_ready and playback_index is not None else "What does the network provenance say?",
            "What is the dominant pathway at this timepoint?" if playback_ready and playback_index is not None else "Is this using my uploaded data or Bordbar?",
            "Is this replay coming from my uploaded data or Bordbar?" if playback_ready and playback_index is not None else "Was the latest calibration applied?",
        ],
    }
