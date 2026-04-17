"""RoBoCop Research Chat API — LLM-backed assistant for Research modules"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
import json
from services.openai_service import openai_service, build_direct_simulation_metabolite_response
from config import is_openai_configured

router = APIRouter(prefix="/robocop", tags=["robocop"])


class RoBoCopChatRequest(BaseModel):
    """Request for RoBoCop chat assistance"""
    context: Dict[str, Any] = Field(..., description="Research module context")
    message: str = Field(..., description="User message")
    conversationHistory: Optional[List[Dict[str, Any]]] = Field(None, description="Previous messages")


class RoBoCopChatResponse(BaseModel):
    """Response from RoBoCop chat"""
    message: str
    contextReferences: List[str]
    confidence: str  # 'high' | 'medium' | 'low'
    suggestedFollowUps: Optional[List[str]] = None


def _to_serializable(obj):
    """Recursively convert numpy types to Python native types for JSON."""
    if hasattr(obj, 'tolist'):  # numpy array
        return obj.tolist()
    if hasattr(obj, 'item'):  # numpy scalar
        return obj.item()
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_serializable(i) for i in obj]
    return obj


def _handle_simulation_provenance(context: Dict, refs: List[str]) -> List[str]:
    """Generate concise provenance statements for simulation answers."""
    responses: List[str] = []
    mode = context.get('researchDataMode') or context.get('research_data_mode')
    dataset_applied = bool(context.get('datasetApplied') if context.get('datasetApplied') is not None else context.get('dataset_applied'))
    dataset_label = (
        context.get('activeDatasetLabel')
        or context.get('active_dataset_label')
        or (context.get('activeDataset') or {}).get('label')
        or 'Bordbar reference dataset'
    )
    dataset_fallback_reason = context.get('datasetFallbackReason') or context.get('dataset_fallback_reason')
    calibration_source = context.get('calibrationSource') or context.get('customParamsSource') or context.get('custom_params_source') or 'defaults'
    calibration_active = bool(
        context.get('calibrationApplied')
        if context.get('calibrationApplied') is not None
        else context.get('calibratedParametersActive')
        if context.get('calibratedParametersActive') is not None
        else calibration_source != 'defaults'
    )

    if mode == 'custom_user_data_mode':
        if dataset_applied:
            count = len(context.get('datasetAppliedMetabolites') or context.get('dataset_applied_metabolites') or [])
            responses.append(f"Custom user data from {dataset_label} was applied.")
            responses.append(f"Mapped metabolites applied: {count}.")
            refs.extend(['researchDataMode', 'activeDatasetLabel', 'datasetApplied'])
        else:
            responses.append(
                f"Custom user data mode was active, but the run fell back to Bordbar defaults"
                f"{f' ({dataset_fallback_reason})' if dataset_fallback_reason else ''}."
            )
            refs.extend(['researchDataMode', 'datasetFallbackReason'])
    else:
        responses.append("Bordbar reference dataset was used.")
        refs.append('researchDataMode')

    if calibration_active:
        if calibration_source == 'provided':
            responses.append("Latest calibration parameters were applied.")
        elif calibration_source == 'auto_loaded':
            responses.append("Calibration parameters were auto-loaded from the saved research state.")
        else:
            responses.append("Calibration parameters were active.")
        refs.append('calibrationSource')
    else:
        responses.append("Default Bordbar parameters were retained.")

    return responses


@router.post("/research/chat", response_model=RoBoCopChatResponse)
async def research_chat(request: RoBoCopChatRequest):
    """
    Chat with RoBoCop about Research module results.
    
    Now powered by OpenAI when configured, with grounded fallback responses.
    Falls back to rule-based responses if OpenAI is not configured.
    """
    try:
        context = request.context
        direct_answer = build_direct_simulation_metabolite_response(request.message, context)
        if direct_answer is not None:
            return RoBoCopChatResponse(
                message=direct_answer["message"],
                contextReferences=direct_answer["contextReferences"],
                confidence=direct_answer["confidence"],
                suggestedFollowUps=direct_answer.get("suggestedFollowUps")
            )

        # Try OpenAI first if configured
        if is_openai_configured():
            response = await openai_service.generate_response(
                message=request.message,
                context=context,
                conversation_history=request.conversationHistory
            )
            
            return RoBoCopChatResponse(
                message=response["message"],
                contextReferences=response["contextReferences"],
                confidence=response["confidence"],
                suggestedFollowUps=response.get("suggestedFollowUps")
            )
        
        # Fallback to rule-based responses
        message = request.message.lower()
        
        # Extract module type
        module_type = context.get('moduleType', 'unknown')
        module_title = context.get('moduleTitle', 'Unknown Module')
        
        # Generate response based on module type and message content
        response_parts = []
        context_refs = []
        follow_ups = []
        
        # Module-specific responses (simplified fallback)
        if module_type == 'simulation':
            response_parts.extend(_handle_simulation_chat(context, message, context_refs))
            follow_ups.extend([
                "Which metabolites show the most dramatic changes?",
                "How does pH perturbation affect the results?",
                "What solver would you recommend for this scenario?",
            ])
        elif module_type == 'flux-analysis':
            response_parts.extend(_handle_flux_chat(context, message, context_refs))
            follow_ups.extend([
                "Which pathways are most active?",
                "Is this using my uploaded data or Bordbar?",
                "Was the latest calibration applied?",
            ])
        elif module_type == 'pathway-visualization':
            response_parts.extend(_handle_pathway_chat(context, message, context_refs))
            if context.get('playbackReady') and context.get('playbackFrameIndex') is not None:
                playback_time = context.get('playbackTimepoint')
                frame_label = f"frame {context.get('playbackFrameIndex') + 1}/{context.get('playbackFrameCount')}"
                if playback_time is not None:
                    frame_label += f" at t={float(playback_time):.2f} days"
                follow_ups.extend([
                    f"What does {frame_label} represent?",
                    "Which metabolites are accumulating here?",
                    "What is the dominant pathway at this timepoint?",
                    "Is this replay coming from my uploaded data or Bordbar?",
                ])
            else:
                follow_ups.extend([
                    "Which pathways are most represented?",
                    "What does the network provenance say?",
                    "Is this using my uploaded data or Bordbar?",
                ])
        elif module_type in ('calibration', 'calibration-registry'):
            response_parts.extend(_handle_calibration_chat(context, message, context_refs))
            follow_ups.extend([
                "What does the selected optimization strategy mean?",
                "Which parameters are currently selected?",
                "Is this using my uploaded data or Bordbar?",
            ])
        else:
            response_parts.append(f"I'm analyzing your {module_title} results.")
            response_parts.append("What specific aspect would you like to explore?")
        
        # Combine response
        full_response = "\n\n".join(response_parts)
        
        return RoBoCopChatResponse(
            message=full_response,
            contextReferences=context_refs,
            confidence="medium",
            suggestedFollowUps=follow_ups if len(follow_ups) > 0 else None
        )
        
    except Exception as e:
        import traceback
        error_msg = f"Error in research_chat: {str(e)}\n{traceback.format_exc()}"
        print(f"[ERROR] {error_msg}")
        raise HTTPException(status_code=500, detail=str(e))


def _handle_simulation_chat(context: Dict, message: str, refs: List[str]) -> List[str]:
    """Generate simulation-specific chat responses"""
    responses = []
    message_lower = message.lower()

    responses.extend(_handle_simulation_provenance(context, refs))
    
    # Time range info
    time_range = context.get('outputs', {}).get('timeRange', {})
    if time_range:
        responses.append(f"The simulation ran for {time_range.get('end', 0):.0f} days with {time_range.get('n_points', 0)} data points.")
        refs.append('timeRange')
    
    # Trends
    if any(keyword in message_lower for keyword in ('trend', 'change', 'what happened')):
        trends = context.get('summary', {}).get('notableTrends', [])
        if trends:
            high_changes = [t for t in trends if t.get('magnitude') == 'high']
            if high_changes:
                changes_desc = []
                for t in high_changes[:3]:
                    changes_desc.append(f"{t['metabolite']} {t['direction']} significantly")
                responses.append(f"Notable changes: {', '.join(changes_desc)}.")
                refs.append('notableTrends')
            else:
                responses.append("Most metabolites remained relatively stable throughout the simulation.")
        else:
            responses.append("I don't see specific trend data for this simulation.")

    # Parameters
    if any(keyword in message_lower for keyword in ('parameter', 'settings')):
        params = context.get('parameters', {})
        if params:
            ph_type = params.get('ph_perturbation_type', 'None')
            if ph_type != 'None':
                responses.append(
                    f"The simulation included {ph_type} perturbation ({params.get('ph_severity', 'unknown')} severity)."
                )
            else:
                responses.append("No pH perturbation was applied.")
            responses.append(
                f"Used {params.get('solver_method', 'unknown')} solver with curve fit strength of {params.get('curve_fit_strength', 0)}."
            )
            refs.append('parameters')

    selected_metabolites = context.get('selectedMetabolites') or []
    if selected_metabolites:
        responses.append(f"Selected metabolite focus: {', '.join(selected_metabolites[:5])}.")
        refs.append('selectedMetabolites')

    # Metabolites
    if 'metabolite' in message_lower or 'which' in message_lower:
        metabolites = context.get('outputs', {}).get('metabolites', {})
        key_mets = metabolites.get('keyMetabolites', []) if metabolites else []
        if key_mets:
            responses.append(f"Key metabolites tracked: {', '.join(key_mets[:5])}.")
            refs.append('metabolites')
    
    return responses


def _handle_calibration_chat(context: Dict, message: str, refs: List[str]) -> List[str]:
    """Generate calibration-specific chat responses"""
    responses = []
    message_lower = message.lower()

    mode = context.get('researchDataMode') or context.get('research_data_mode')
    dataset_applied = bool(context.get('datasetApplied') if context.get('datasetApplied') is not None else context.get('dataset_applied'))
    dataset_label = (
        context.get('activeDatasetLabel')
        or context.get('active_dataset_label')
        or (context.get('activeDataset') or {}).get('label')
        or 'Bordbar reference dataset'
    )
    dataset_fallback_reason = context.get('datasetFallbackReason') or context.get('dataset_fallback_reason')
    inputs = context.get('inputs', {})
    selected_parameters = inputs.get('selectedParameters') or []
    selected_families = inputs.get('selectedParameterFamilies') or []
    strategy_label = (
        inputs.get('strategyLabel')
        or inputs.get('selectedOptimizationStrategy')
        or inputs.get('optimizationStrategy')
        or 'unknown strategy'
    )
    strategy_value = inputs.get('selectedOptimizationStrategy') or inputs.get('optimizationStrategy') or 'unknown'
    selection_mode = (
        'recommended subset'
        if inputs.get('isRecommendedSubset')
        else 'advanced canonical inventory'
        if inputs.get('hasAdvancedSelection')
        else 'canonical selection'
    )
    taxonomy_source = inputs.get('canonicalTaxonomySource') or 'MM_calibration'
    taxonomy_version = inputs.get('canonicalTaxonomyVersion') or 'mm_calibration_v1'
    calibration_applied = bool(
        context.get('calibrationApplied')
        if context.get('calibrationApplied') is not None
        else context.get('calibratedParametersActive')
        if context.get('calibratedParametersActive') is not None
        else False
    )
    calibration_source = (
        context.get('calibrationSource')
        or context.get('customParamsSource')
        or context.get('custom_params_source')
        or 'defaults'
    )
    calibration_status = (
        context.get('calibrationStatus')
        or context.get('calibration_status')
        or ('failed' if context.get('calibrationFailed') or context.get('calibration_failed') else None)
        or (
            'completed'
            if context.get('calibrationCompleted')
            or context.get('calibration_completed')
            or context.get('calibrationResultAvailable')
            or context.get('calibration_result_available')
            else None
        )
        or 'setup_only'
    )
    calibration_result_available = calibration_status == 'completed'
    calibration_result_summary = context.get('resultSummary') or context.get('result_summary')
    calibration_error = context.get('calibrationError') or context.get('calibration_error')
    fit_metrics = context.get('fitMetrics') or context.get('fit_metrics') or {}
    parameter_changes = (
        context.get('parameterChanges')
        or context.get('parameter_changes')
        or context.get('initialVsFinalComparison')
        or context.get('initial_vs_final_comparison')
        or []
    )

    if mode == 'custom_user_data_mode':
        if dataset_applied:
            responses.append(f"Custom user data from {dataset_label} is active for calibration.")
        else:
            responses.append(
                f"Custom user data mode is active, but calibration fell back to Bordbar defaults"
                f"{f' ({dataset_fallback_reason})' if dataset_fallback_reason else ''}."
            )
    else:
        responses.append("Bordbar reference data is active for calibration.")

    if selected_parameters:
        responses.append(f"Selected parameters: {', '.join(selected_parameters[:8])}.")
    if selected_families:
        responses.append(f"Parameter families: {', '.join(selected_families)}.")

    responses.append(f"Optimization strategy: {strategy_label} ({strategy_value}).")
    responses.append(f"Selection scope: {selection_mode}.")
    responses.append(f"Canonical taxonomy: {taxonomy_source} {taxonomy_version}.")
    if calibration_applied:
        if calibration_source == 'provided':
            responses.append("Calibration: latest calibration applied.")
        elif calibration_source == 'auto_loaded':
            responses.append("Calibration: auto-loaded calibration active.")
        else:
            responses.append("Calibration: calibration active.")
    else:
        responses.append("Calibration: default Bordbar parameters retained.")

    responses.append(f"Calibration state: {calibration_status.replace('_', ' ')}.")

    if calibration_status == 'running':
        responses.append("The run is still in progress, so this context only covers the setup so far.")
    elif calibration_status == 'failed':
        responses.append("The calibration failed before a completed result was produced.")
        if calibration_error:
            responses.append(f"Failure detail: {calibration_error}")
            refs.append('calibrationError')
    elif not calibration_result_available:
        responses.append("Calibration result is not available yet; this is the current setup state.")

    registry_comparison = context.get('registryComparison') or context.get('registry_comparison') or {}
    if context.get('moduleType') == 'calibration-registry' or registry_comparison:
        registry_summary = (
            context.get('registryResultSummary')
            or context.get('registry_result_summary')
            or context.get('resultSummary')
            or context.get('result_summary')
        )
        if isinstance(registry_summary, str) and registry_summary.strip():
            responses.append(f"Historical registry summary: {registry_summary.strip()}")
            refs.append('registryResultSummary')

        comparison_summary = (
            registry_comparison.get('comparisonSummary')
            or registry_comparison.get('comparison_summary')
            or (context.get('summary') or {}).get('comparisonLane')
        )
        if isinstance(comparison_summary, str) and comparison_summary.strip():
            responses.append(f"Comparison lanes: {comparison_summary.strip()}")
            refs.append('registryComparison.comparisonSummary')

        lead_record = registry_comparison.get('leadRecord') or registry_comparison.get('lead_record') or {}
        if isinstance(lead_record, dict) and lead_record:
            lead_label = (
                lead_record.get('label')
                or lead_record.get('runId')
                or lead_record.get('run_id')
                or 'lead record'
            )
            lead_bits = []
            benchmark_status = (
                lead_record.get('benchmarkStatus')
                or lead_record.get('benchmark_status')
                or lead_record.get('status')
            )
            completion_status = (
                lead_record.get('completionStatus')
                or lead_record.get('completion_status')
            )
            if isinstance(benchmark_status, str) and benchmark_status.strip():
                lead_bits.append(benchmark_status.replace('_', ' '))
            if isinstance(completion_status, str) and completion_status.strip():
                lead_bits.append(completion_status.replace('_', ' '))
            if lead_bits:
                responses.append(f"Lead record: {lead_label} ({' / '.join(lead_bits)}).")
            else:
                responses.append(f"Lead record: {lead_label}.")
            refs.append('registryComparison.leadRecord')

        groups = registry_comparison.get('groups') or registry_comparison.get('comparison_groups') or []
        if isinstance(groups, list) and groups:
            group_bits = []
            for group in groups[:3]:
                if not isinstance(group, dict):
                    continue
                label = group.get('label') or group.get('name') or group.get('status') or 'group'
                count = group.get('count') or group.get('runCount') or group.get('run_count')
                if isinstance(count, (int, float)):
                    group_bits.append(f"{label} ({int(count)})")
                else:
                    group_bits.append(str(label))
            if group_bits:
                responses.append(f"Visible comparison lanes: {', '.join(group_bits)}.")
                refs.append('registryComparison.groups')

        summary = context.get('summary', {})
        if isinstance(summary, dict):
            comparison_lane = summary.get('comparisonLane')
            top_comparisons = summary.get('topComparisons')
            if isinstance(comparison_lane, str) and comparison_lane.strip():
                responses.append(f"Comparison lane: {comparison_lane.strip()}.")
                refs.append('summary.comparisonLane')
            elif isinstance(top_comparisons, list) and top_comparisons:
                responses.append("Historical comparisons are grouped into the visible benchmark lanes.")
                refs.append('summary.topComparisons')

        refs.extend([
            'registryComparison',
            'registryResultSummary',
            'summary.comparisonLane',
        ])
        return responses

    outputs = context.get('outputs', {})
    if calibration_result_available and outputs:
        refs.append('fitMetrics')
        r_squared = outputs.get('rSquared', 0)
        responses.append(f"The calibration achieved an R² of {r_squared:.3f}, indicating {'excellent' if r_squared > 0.9 else 'good' if r_squared > 0.7 else 'moderate'} fit.")
        refs.append('outputs')

        if isinstance(fit_metrics, dict) and isinstance(fit_metrics.get('improvementPct'), (int, float)):
            responses.append(f"Objective improvement was {float(fit_metrics['improvementPct']):.1f}% relative to the starting point.")

        run_duration = context.get('runDurationSeconds') or context.get('run_duration_seconds')
        if isinstance(run_duration, (int, float)):
            responses.append(f"Run duration was approximately {float(run_duration):.1f} seconds.")

        iterations = outputs.get('iterations', 0)
        max_iter = inputs.get('maxIterations', 0)
        if iterations < max_iter:
            responses.append(f"Optimization converged in {iterations} iterations.")
        else:
            responses.append(f"Optimization reached the maximum {max_iter} iterations without full convergence.")

        summary = context.get('summary', {})
        top_changes = summary.get('topChanges', []) or parameter_changes
        if top_changes:
            changes = []
            for change in top_changes[:3]:
                param = change.get('param', 'unknown')
                pct = change.get('percentChange', 0)
                changes.append(f"{param} changed by {pct:.1f}%")
            responses.append(f"Largest parameter changes: {', '.join(changes)}.")
            refs.append('summary')
        if isinstance(calibration_result_summary, str) and calibration_result_summary.strip():
            responses.append(calibration_result_summary.strip())
            refs.append('resultSummary')
    elif calibration_status == 'running':
        refs.append('calibrationStatus')
        refs.append('inputs.selectedParameters')
        refs.append('inputs.selectedOptimizationStrategy')
        refs.append('inputs.strategyLabel')
    else:
        refs.extend([
            'researchDataMode',
            'datasetApplied',
            'inputs.selectedParameters',
            'inputs.selectedParameterFamilies',
            'inputs.selectedOptimizationStrategy',
            'inputs.strategyLabel',
            'inputs.canonicalTaxonomySource',
            'inputs.canonicalTaxonomyVersion',
            'calibrationApplied',
            'calibrationSource',
            'calibrationStatus',
        ])

    refs.extend([
        'researchDataMode',
        'datasetApplied',
        'inputs.selectedParameters',
        'inputs.selectedParameterFamilies',
        'inputs.selectedOptimizationStrategy',
        'inputs.strategyLabel',
        'inputs.canonicalTaxonomySource',
        'inputs.canonicalTaxonomyVersion',
        'calibrationApplied',
        'calibrationSource',
    ])

    return responses


def _handle_flux_chat(context: Dict, message: str, refs: List[str]) -> List[str]:
    """Generate flux analysis-specific chat responses"""
    responses = []

    flux_status = context.get('fluxStatus') or context.get('flux_status') or ('completed' if context.get('fluxResultAvailable') or context.get('flux_result_available') else 'setup_only')
    mode = context.get('researchDataMode') or context.get('research_data_mode') or 'default_bordbar_mode'
    dataset_label = (
        context.get('activeDatasetLabel')
        or context.get('active_dataset_label')
        or (context.get('activeDataset') or {}).get('label')
        or 'Bordbar reference dataset'
    )
    dataset_applied = bool(context.get('datasetApplied') if context.get('datasetApplied') is not None else context.get('dataset_applied'))
    dataset_fallback_reason = context.get('datasetFallbackReason') or context.get('dataset_fallback_reason')
    calibration_applied = bool(
        context.get('calibrationApplied')
        if context.get('calibrationApplied') is not None
        else context.get('calibratedParametersActive')
        if context.get('calibratedParametersActive') is not None
        else False
    )
    calibration_source = context.get('calibrationSource') or context.get('customParamsSource') or context.get('custom_params_source') or 'defaults'
    selected_pathway = (context.get('inputs') or {}).get('selectedPathway') or 'all'
    applied_count = len((context.get('inputs') or {}).get('appliedConcentrationMetabolites') or context.get('datasetAppliedMetabolites') or [])
    provenance_bits = []

    if mode == 'custom_user_data_mode':
        if dataset_applied:
            provenance_bits.append(f"custom user data from {dataset_label}")
        else:
            provenance_bits.append(
                f"custom user data mode with Bordbar fallback"
                f"{f' ({dataset_fallback_reason})' if dataset_fallback_reason else ''}"
            )
    else:
        provenance_bits.append("Bordbar reference data")

    if calibration_applied:
        if calibration_source == 'provided':
            provenance_bits.append('latest calibration applied')
        elif calibration_source == 'auto_loaded':
            provenance_bits.append('auto-loaded calibration')
        else:
            provenance_bits.append('calibration active')
    else:
        provenance_bits.append('default Bordbar parameters')

    responses.append(f"Flux provenance: {'; '.join(provenance_bits)}.")
    refs.extend(['researchDataMode', 'datasetApplied', 'calibrationApplied', 'calibrationSource'])
    responses.append(f"Selected pathway: {selected_pathway}.")
    refs.append('inputs.selectedPathway')

    outputs = context.get('outputs', {})
    summary = context.get('summary', {})
    dominant = summary.get('dominantPathway', 'unknown')
    if flux_status == 'completed' and outputs:
        responses.append(f"The {dominant} pathway shows the highest activity.")
        refs.append('summary')

        top_reactions = summary.get('topReactions', [])
        if top_reactions:
            reactions = []
            for r in top_reactions[:3]:
                name = r.get('reaction', 'unknown')
                flux = r.get('flux', 0)
                reactions.append(f"{name} ({flux:.2e})")
            responses.append(f"Top reactions by flux: {', '.join(reactions)}.")
            refs.append('summary.topReactions')

        total_flux = outputs.get('totalFlux', 0)
        responses.append(f"Total metabolic flux: {total_flux:.2e} arbitrary units.")
        refs.append('outputs.totalFlux')
    elif flux_status == 'running':
        responses.append("Flux estimation is still running, so only the setup context is available so far.")
        if applied_count:
            responses.append(f"{applied_count} concentration overrides have been applied to the snapshot.")
    elif flux_status == 'failed':
        responses.append("Flux estimation failed before a completed result was produced.")
        if context.get('fluxError') or context.get('flux_error'):
            responses.append(f"Failure detail: {context.get('fluxError') or context.get('flux_error')}")
            refs.append('fluxError')
    else:
        responses.append("Flux result is not available yet; this is the current setup state.")

    return responses


def _handle_pathway_chat(context: Dict, message: str, refs: List[str]) -> List[str]:
    """Generate pathway visualization-specific chat responses"""
    responses = []

    mode = context.get('researchDataMode') or context.get('research_data_mode') or 'default_bordbar_mode'
    dataset_label = (
        context.get('activeDatasetLabel')
        or context.get('active_dataset_label')
        or (context.get('activeDataset') or {}).get('label')
        or 'Bordbar reference dataset'
    )
    calibration_applied = bool(
        context.get('calibrationApplied')
        if context.get('calibrationApplied') is not None
        else context.get('calibratedParametersActive')
        if context.get('calibratedParametersActive') is not None
        else False
    )
    calibration_source = context.get('calibrationSource') or context.get('customParamsSource') or context.get('custom_params_source') or 'defaults'
    pathway_status = context.get('pathwayStatus') or context.get('pathway_status') or ('completed' if context.get('pathwayResultAvailable') or context.get('pathway_result_available') else 'setup_only')
    result_summary = context.get('resultSummary') or context.get('result_summary')
    playback_ready = bool(
        context.get('playbackReady')
        if context.get('playbackReady') is not None
        else context.get('playback_ready')
        if context.get('playback_ready') is not None
        else False
    )
    playback_index = context.get('playbackFrameIndex')
    playback_count = context.get('playbackFrameCount') or 0
    playback_timepoint = context.get('playbackTimepoint')
    selected_timepoint_summary = context.get('selectedTimepointSummary') or context.get('selected_timepoint_summary')
    replay_source = context.get('replaySource') or context.get('replay_source')
    network_state_summary = context.get('networkStateSummary') or context.get('network_state_summary')
    dominant_pathway = context.get('dominantPathway') or context.get('dominant_pathway')
    dominant_signal = context.get('dominantSignal') or context.get('dominant_signal')
    top_accumulating = context.get('topAccumulatingMetabolites') or context.get('top_accumulating_metabolites') or []
    top_depleting = context.get('topDepletingMetabolites') or context.get('top_depleting_metabolites') or []
    summary = context.get('summary') or {}
    outputs = context.get('outputs') or {}
    network_stats = outputs.get('networkStats') or {}
    nodes = network_stats.get('nodes', 0)
    edges = network_stats.get('edges', 0)
    pathways = network_stats.get('pathways') or []
    key_pathways = summary.get('keyPathways') or []
    key_signals = summary.get('keySignals') or []
    pathway_error = context.get('pathwayError') or context.get('pathway_error')

    if mode == 'custom_user_data_mode':
        responses.append(f"Custom user data is active in the research workspace ({dataset_label}).")
    else:
        responses.append("Bordbar reference context is active in the research workspace.")

    if calibration_applied:
        if calibration_source == 'provided':
            responses.append("Latest calibration parameters are active.")
        elif calibration_source == 'auto_loaded':
            responses.append("Calibration parameters were auto-loaded from the saved research state.")
        else:
            responses.append("Calibration parameters are active.")
    else:
        responses.append("Default Bordbar parameters are still in effect.")

    responses.append(f"Pathway state: {str(pathway_status).replace('_', ' ')}.")
    responses.append(f"Network size: {nodes} nodes, {edges} edges across {len(pathways)} pathway groups.")

    if playback_ready and playback_index is not None:
        if selected_timepoint_summary:
            responses.append(f"Current replay: {selected_timepoint_summary}.")
        else:
            playback_line = f"Playback frame {playback_index + 1}/{playback_count}"
            if playback_timepoint is not None:
                playback_line += f" at t={float(playback_timepoint):.2f} days"
            responses.append(f"Current replay: {playback_line}.")
        if replay_source:
            responses.append(f"Replay source: {replay_source}.")
        if network_state_summary:
            responses.append(f"Network state: {network_state_summary}.")
        if dominant_pathway:
            responses.append(f"Dominant pathway: {dominant_pathway}.")
        if isinstance(dominant_signal, dict) and dominant_signal.get('label') is not None:
            value = float(dominant_signal.get('value', 0))
            pathway = dominant_signal.get('pathway')
            signal_line = f"Dominant signal: {dominant_signal.get('label')} {value:+.2e}"
            if pathway:
                signal_line += f" ({pathway})"
            responses.append(signal_line + ".")
        if top_accumulating:
            accum_parts = []
            for shift in top_accumulating[:3]:
                metabolite = shift.get('metabolite', 'unknown')
                delta = shift.get('delta', 0)
                accum_parts.append(f"{metabolite} {float(delta):+.2e}")
            responses.append(f"Accumulating: {', '.join(accum_parts)}.")
        if top_depleting:
            deplete_parts = []
            for shift in top_depleting[:3]:
                metabolite = shift.get('metabolite', 'unknown')
                delta = shift.get('delta', 0)
                deplete_parts.append(f"{metabolite} {float(delta):.2e}")
            responses.append(f"Depleting: {', '.join(deplete_parts)}.")
    elif pathway_status == 'running':
        responses.append("The pathway replay is still loading, so only the setup context is available so far.")
    else:
        responses.append("The pathway map is showing a static network snapshot rather than a replay frame.")

    if result_summary and isinstance(result_summary, str):
        responses.append(result_summary)

    if key_pathways:
        responses.append(f"Key pathways: {', '.join(key_pathways[:3])}.")

    if key_signals:
        responses.append(f"Context signals: {', '.join([str(signal) for signal in key_signals[:3]])}.")

    if pathway_status == 'failed':
        responses.append("The pathway map failed before a completed result was produced.")
        if pathway_error:
            responses.append(f"Failure detail: {pathway_error}")
            refs.append('pathwayError')
    elif pathway_status == 'running':
        responses.append("The pathway map is still loading, so only the setup context is available so far.")
    else:
        responses.append("The pathway map is ready for interpretation.")

    refs.extend([
        'researchDataMode',
        'datasetApplied',
        'calibrationApplied',
        'calibrationSource',
        'pathwayStatus',
        'playbackReady',
        'playbackFrameIndex',
        'playbackFrameCount',
        'playbackTimepoint',
        'selectedTimepointSummary',
        'replaySource',
        'networkStateSummary',
        'dominantPathway',
        'dominantSignal',
        'topAccumulatingMetabolites',
        'topDepletingMetabolites',
        'resultSummary',
        'summary',
        'outputs.networkStats',
        'summary.keyPathways',
        'summary.keySignals',
    ])

    return responses


def _handle_sensitivity_chat(context: Dict, message: str, refs: List[str]) -> List[str]:
    """Generate sensitivity analysis-specific chat responses"""
    responses = []
    
    summary = context.get('summary', {})
    if summary:
        # Overall fit
        fit = summary.get('overallFit', 'unknown')
        responses.append(f"The model shows {fit} agreement with the reference data.")
        refs.append('summary')
        
        # Most discrepant metabolites
        discrepancies = summary.get('mostDiscrepancies', [])
        if discrepancies:
            responses.append(f"Largest discrepancies found in: {', '.join(discrepancies)}.")
        
        # Average error
        avg_error = summary.get('averageError', 0)
        responses.append(f"Average RMSE across metabolites: {avg_error:.3f}.")
    
    return responses


def _determine_confidence(context: Dict, message: str) -> str:
    """Determine confidence level for the response"""
    module_type = context.get('moduleType', 'unknown')
    
    # High confidence for well-structured modules
    if module_type in ['simulation', 'calibration', 'sensitivity-analysis']:
        return 'high'
    
    # Medium for others
    if module_type in ['flux-analysis', 'data-upload']:
        return 'medium'
    
    # Low for pathway visualization (less numerical)
    if module_type == 'pathway-visualization':
        return 'low'
    
    return 'medium'
