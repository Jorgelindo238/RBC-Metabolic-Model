import time
from pathlib import Path

try:
    from scripts.run_registry_support import (
        RunRegistryContractError,
        find_case,
        parse_run_timestamp,
        read_json,
        repo_relative,
        unique_non_empty,
    )
except ImportError:
    from run_registry_support import (
        RunRegistryContractError,
        find_case,
        parse_run_timestamp,
        read_json,
        repo_relative,
        unique_non_empty,
    )

REGISTRY_CONTRACT_TYPE = 'calibration_run_registry_record'
REGISTRY_CONTRACT_VERSION = 2
SOURCE_CONTRACT_TYPE = 'calibration_run_artifact_manifest'
CALIBRATION_RUNS_ROW_EXCLUDED_FIELDS = (
    'contract_type',
    'contract_version',
    'source_artifact_contract_type',
    'source_artifact_contract_version',
    'storage',
)
QUERYABLE_SUMMARY_KEYS = (
    'aggregate_score',
    'mean_final_loss',
    'mean_improvement_pct',
    'best_case',
    'worst_case',
    'time_aware_score',
)


def build_case_ref(case: dict) -> dict:
    artifacts = case.get('artifacts', {})
    return {
        'name': case.get('name'),
        'score': case.get('score'),
        'final_loss': case.get('final_loss'),
        'elapsed_seconds': case.get('elapsed_seconds'),
        'case_completion_status': case.get('case_completion_status'),
        'case_time_budget_exceeded': case.get('case_time_budget_exceeded'),
        'report_path': artifacts.get('calibration_report', {}).get('path'),
        'best_params_json_path': artifacts.get('best_params_json', {}).get('path'),
        'results_tsv_path': artifacts.get('results_tsv', {}).get('path'),
    }


def build_run_registry_record(manifest: dict, manifest_path: Path | None = None) -> dict:
    if manifest.get('contract_type') != SOURCE_CONTRACT_TYPE:
        raise RunRegistryContractError(
            f"Expected contract_type '{SOURCE_CONTRACT_TYPE}' in completed-run manifest"
        )

    run = manifest.get('run')
    outputs = manifest.get('outputs')
    artifacts = manifest.get('artifacts')
    if not isinstance(run, dict) or not isinstance(outputs, dict) or not isinstance(artifacts, dict):
        raise RunRegistryContractError('Completed-run manifest is missing required sections')

    summary = outputs.get('summary', {})
    cases = outputs.get('cases', [])
    job = manifest.get('job') or {}
    job_metadata = job.get('metadata', {}) if isinstance(job.get('metadata'), dict) else {}
    run_completion_status = run.get('completion_status')
    if not isinstance(cases, list):
        cases = []
    stage_plan = run.get('stage_plan')
    if not isinstance(stage_plan, list):
        stage_plan = []
    target_scopes = unique_non_empty(
        [stage.get('target_scope') for stage in stage_plan if isinstance(stage, dict)]
        + [case.get('target_scope') for case in cases if isinstance(case, dict)]
    )
    param_scopes = unique_non_empty(
        [stage.get('param_scope') for stage in stage_plan if isinstance(stage, dict)]
        + [case.get('param_scope') for case in cases if isinstance(case, dict)]
    )

    run_dir = run.get('run_dir')
    run_id = Path(run_dir).name if run_dir else None
    canonical_run_label = ' / '.join(
        part for part in (job.get('job_name'), run.get('policy_name'), run.get('timestamp')) if part
    )
    best_case = find_case(cases, summary.get('best_case'))
    worst_case = find_case(cases, summary.get('worst_case'))
    manifest_ref = repo_relative(manifest_path) if manifest_path is not None else None
    workspace_id = job_metadata.get('workspace_id')
    created_by_user_id = job_metadata.get('created_by_user_id')
    agent_session_id = job_metadata.get('agent_session_id')
    visibility = job_metadata.get('visibility')
    run_origin = job_metadata.get('run_origin')

    return {
        'contract_type': REGISTRY_CONTRACT_TYPE,
        'contract_version': REGISTRY_CONTRACT_VERSION,
        'source_artifact_contract_type': manifest.get('contract_type'),
        'source_artifact_contract_version': manifest.get('contract_version'),
        'run_id': run_id,
        'canonical_run_label': canonical_run_label or run_id,
        'run_timestamp': run.get('timestamp'),
        'run_timestamp_utc': parse_run_timestamp(run.get('timestamp')),
        'registry_recorded_at': manifest.get('generated_at') or time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'status': run.get('status'),
        'benchmark_status': run.get('benchmark_status'),
        'completion_status': run_completion_status,
        'job_name': job.get('job_name'),
        'hypothesis': job.get('hypothesis'),
        'job_version': job.get('job_version'),
        'campaign': job_metadata.get('campaign'),
        'tags': job.get('tags', []),
        'job_metadata': job_metadata,
        'workspace_id': workspace_id,
        'created_by_user_id': created_by_user_id,
        'agent_session_id': agent_session_id,
        'visibility': visibility,
        'run_origin': run_origin,
        'policy_name': run.get('policy_name'),
        'policy_path': job.get('policy_path'),
        'manifest_name': run.get('manifest_name'),
        'manifest_path': job.get('manifest_path'),
        'optimization_strategy': run.get('optimization_strategy'),
        'parameter_classes': run.get('parameter_classes'),
        'target_scope': target_scopes[0] if len(target_scopes) == 1 else None,
        'target_scopes': target_scopes,
        'param_scope': param_scopes[0] if len(param_scopes) == 1 else None,
        'param_scopes': param_scopes,
        'aggregate_score': summary.get('aggregate_score'),
        'mean_final_loss': summary.get('mean_final_loss'),
        'mean_improvement_pct': summary.get('mean_improvement_pct'),
        'best_case': summary.get('best_case'),
        'worst_case': summary.get('worst_case'),
        'time_aware_score': summary.get('time_aware_score'),
        'case_count': outputs.get('case_count'),
        'completed_cases': outputs.get('completed_cases'),
        'total_cases': outputs.get('total_cases'),
        'elapsed_seconds': run.get('elapsed_seconds'),
        'time_budget_seconds': run.get('time_budget_seconds'),
        'case_time_budget_seconds': run.get('case_time_budget_seconds'),
        'timeout_policy': run.get('timeout_policy'),
        'coverage_ratio': run.get('coverage_ratio'),
        'coverage_weight_ratio': run.get('coverage_weight_ratio'),
        'timed_out': run.get('timed_out'),
        'crashed': run.get('crashed'),
        'stop_reason': run.get('stop_reason'),
        'run_dir': run_dir,
        'artifact_manifest_path': manifest_ref,
        'artifact_refs': {
            'completed_run_manifest_path': manifest_ref,
            'eval_summary_path': artifacts.get('eval_summary', {}).get('path'),
            'policy_snapshot_path': manifest.get('inputs', {}).get('policy_snapshot', {}).get('path'),
            'manifest_snapshot_path': manifest.get('inputs', {}).get('manifest_snapshot', {}).get('path'),
            'best_case_report_path': best_case.get('artifacts', {}).get('calibration_report', {}).get('path') if best_case else None,
            'worst_case_report_path': worst_case.get('artifacts', {}).get('calibration_report', {}).get('path') if worst_case else None,
            'case_refs': [build_case_ref(case) for case in cases if isinstance(case, dict)],
        },
        'trace_context': {
            'tags': unique_non_empty(
                list(job.get('tags', []))
                + ['calibration', 'registry_record', str(run.get('status') or '')]
                + [str(run.get('policy_name') or ''), str(run.get('manifest_name') or ''), str(run_completion_status or '')]
            ),
            'metadata': {
                key: summary.get(key) for key in QUERYABLE_SUMMARY_KEYS
            } | {
                'run_id': run_id,
                'canonical_run_label': canonical_run_label or run_id,
                'policy_name': run.get('policy_name'),
                'manifest_name': run.get('manifest_name'),
                'artifact_manifest_path': manifest_ref,
                'benchmark_status': run.get('benchmark_status'),
                'completion_status': run_completion_status,
            },
        },
        'chat_context': {
            'assistant': 'RoBoCop',
            'canonical_run_label': canonical_run_label or run_id,
            'hypothesis': job.get('hypothesis'),
            'scientific_context': {
                'target_scope': target_scopes[0] if len(target_scopes) == 1 else None,
                'param_scope': param_scopes[0] if len(param_scopes) == 1 else None,
                'optimization_strategy': run.get('optimization_strategy'),
            },
            'summary_metrics': {key: summary.get(key) for key in QUERYABLE_SUMMARY_KEYS},
            'runtime_context': {
                'elapsed_seconds': run.get('elapsed_seconds'),
                'time_budget_seconds': run.get('time_budget_seconds'),
                'case_time_budget_seconds': run.get('case_time_budget_seconds'),
                'coverage_ratio': run.get('coverage_ratio'),
                'coverage_weight_ratio': run.get('coverage_weight_ratio'),
                'completion_status': run_completion_status,
            },
            'figure_context': {
                'best_case': summary.get('best_case'),
                'worst_case': summary.get('worst_case'),
                'best_case_report_path': best_case.get('artifacts', {}).get('calibration_report', {}).get('path') if best_case else None,
                'worst_case_report_path': worst_case.get('artifacts', {}).get('calibration_report', {}).get('path') if worst_case else None,
            },
        },
        'storage': {
            'registry_backend': 'supabase_row',
            'queryable_fields': [
                'run_id',
                'canonical_run_label',
                'run_timestamp',
                'status',
                'job_name',
                'workspace_id',
                'created_by_user_id',
                'agent_session_id',
                'visibility',
                'run_origin',
                'policy_name',
                'manifest_name',
                'optimization_strategy',
                'target_scope',
                'param_scope',
                'aggregate_score',
                'mean_final_loss',
                'mean_improvement_pct',
                'best_case',
                'worst_case',
                'time_aware_score',
                'completed_cases',
                'total_cases',
                'elapsed_seconds',
                'time_budget_seconds',
                'coverage_ratio',
                'coverage_weight_ratio',
                'completion_status',
                'case_count',
                'run_dir',
                'artifact_manifest_path',
            ],
            'recommended_json_fields': ['tags', 'job_metadata', 'trace_context', 'chat_context'],
            'artifact_source_of_truth': 'completed_run_manifest',
            'artifact_fields': ['artifact_refs'],
        },
    }


def project_run_registry_record_to_calibration_runs_row(registry_record: dict) -> dict:
    if not isinstance(registry_record, dict):
        raise RunRegistryContractError('Run registry record must be a JSON object')
    if registry_record.get('contract_type') != REGISTRY_CONTRACT_TYPE:
        raise RunRegistryContractError(
            f"Expected contract_type '{REGISTRY_CONTRACT_TYPE}' in run registry record"
        )
    if registry_record.get('contract_version') != REGISTRY_CONTRACT_VERSION:
        raise RunRegistryContractError(
            f"Expected contract_version '{REGISTRY_CONTRACT_VERSION}' in run registry record"
        )

    return {
        key: value
        for key, value in registry_record.items()
        if key not in CALIBRATION_RUNS_ROW_EXCLUDED_FIELDS
    }


def build_run_registry_record_from_path(manifest_path: Path) -> dict:
    resolved_manifest_path = manifest_path.resolve()
    manifest = read_json(resolved_manifest_path)
    return build_run_registry_record(manifest, manifest_path=resolved_manifest_path)


def project_run_registry_record_to_calibration_runs_row_from_path(registry_record_path: Path) -> dict:
    resolved_registry_record_path = registry_record_path.resolve()
    registry_record = read_json(resolved_registry_record_path)
    return project_run_registry_record_to_calibration_runs_row(registry_record)
