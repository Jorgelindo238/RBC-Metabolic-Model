import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACT_TYPE = 'calibration_run_artifact_manifest'
CONTRACT_VERSION = 2
MANIFEST_FILENAME = 'completed_run_manifest.json'
JOB_FIELDS = (
    'job_name',
    'hypothesis',
    'job_version',
    'job_path',
    'policy_path',
    'manifest_path',
    'baseline_run_dir',
    'promotion_manifest_path',
    'time_budget_seconds',
    'case_time_budget_seconds',
    'timeout_policy',
    'tags',
    'metadata',
)


class ArtifactContractError(ValueError):
    pass


def read_json(path: Path) -> dict:
    try:
        with open(path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError as exc:
        raise ArtifactContractError(f'JSON file does not exist: {path}') from exc
    except json.JSONDecodeError as exc:
        raise ArtifactContractError(f'Invalid JSON in {path}: {exc.msg}') from exc
    if not isinstance(data, dict):
        raise ArtifactContractError(f'Expected JSON object in {path}')
    return data


def repo_relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def resolve_path(value, base_dir: Path | None = None) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (base_dir or ROOT) / path
    return path.resolve()


def build_artifact_ref(path: Path, artifact_type: str, required: bool = True) -> dict:
    exists = path.exists()
    if required and not exists:
        raise ArtifactContractError(f'Missing required artifact: {path}')

    payload = {
        'type': artifact_type,
        'path': repo_relative(path),
        'exists': exists,
    }
    if exists and path.is_file():
        payload['size_bytes'] = path.stat().st_size
    return payload


def normalize_job(job_spec: dict | None) -> dict | None:
    if not job_spec:
        return None
    return {field: job_spec[field] for field in JOB_FIELDS if field in job_spec}


def resolve_report_path(run_dir: Path, case_summary: dict) -> Path:
    report_path = case_summary.get('report_path')
    if report_path:
        return resolve_path(report_path, base_dir=run_dir)
    return (run_dir / case_summary['name'] / 'calibration_report.json').resolve()


def build_case_record(run_dir: Path, case_summary: dict) -> dict:
    report_path = resolve_report_path(run_dir, case_summary)
    report = read_json(report_path)
    case_dir = report_path.parent

    return {
        'name': case_summary['name'],
        'description': case_summary.get('description', ''),
        'weight': case_summary.get('weight'),
        'score': case_summary.get('score'),
        'score_breakdown': case_summary.get('score_breakdown', {}),
        'optimization_strategy': case_summary.get(
            'optimization_strategy',
            report.get('optimization_strategy'),
        ),
        'parameter_classes': case_summary.get(
            'parameter_classes',
            report.get('parameter_classes'),
        ),
        'target_scope': report.get('target_scope'),
        'param_scope': report.get('param_scope'),
        'seed': report.get('seed'),
        't_max': report.get('t_max'),
        'baseline_loss': report.get('baseline_loss'),
        'final_loss': case_summary.get('final_loss', report.get('final_loss')),
        'improvement_pct': case_summary.get('improvement_pct', report.get('improvement_pct')),
        'monitor_metrics': case_summary.get('monitor_metrics') or report.get('monitor_metrics', {}),
        'elapsed_seconds': case_summary.get('elapsed_seconds'),
        'case_completion_status': case_summary.get('case_completion_status', 'completed'),
        'case_budget_seconds': case_summary.get('case_budget_seconds'),
        'case_time_budget_exceeded': case_summary.get('case_time_budget_exceeded', False),
        'artifacts': {
            'calibration_report': build_artifact_ref(report_path, 'calibration_report'),
            'best_params_json': build_artifact_ref(case_dir / 'best_params.json', 'best_params_json'),
            'best_params_py': build_artifact_ref(
                case_dir / 'best_params.py',
                'best_params_python',
                required=False,
            ),
            'results_tsv': build_artifact_ref(
                case_dir / 'results.tsv',
                'case_results_tsv',
                required=False,
            ),
        },
    }


def build_completed_run_manifest(run_dir: Path, job_spec: dict | None = None) -> dict:
    resolved_run_dir = run_dir.resolve()
    summary_path = resolved_run_dir / 'eval_summary.json'
    summary = read_json(summary_path)
    cases = [build_case_record(resolved_run_dir, case) for case in summary.get('case_results', [])]

    return {
        'contract_type': CONTRACT_TYPE,
        'contract_version': CONTRACT_VERSION,
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'job': normalize_job(job_spec),
        'run': {
            'run_dir': repo_relative(resolved_run_dir),
            'timestamp': summary.get('timestamp'),
            'policy_name': summary.get('policy_name'),
            'manifest_name': summary.get('manifest_name'),
            'manifest_description': summary.get('manifest_description', ''),
            'optimization_strategy': summary.get('optimization_strategy'),
            'parameter_classes': summary.get('parameter_classes'),
            'stage_plan': summary.get('stage_plan', []),
            'status': summary.get('status'),
            'benchmark_status': summary.get('benchmark_status'),
            'completion_status': summary.get('completion_status'),
            'elapsed_seconds': summary.get('elapsed_seconds'),
            'time_budget_seconds': summary.get('time_budget_seconds'),
            'case_time_budget_seconds': summary.get('case_time_budget_seconds'),
            'timeout_policy': summary.get('timeout_policy'),
            'completed_cases': summary.get('completed_cases'),
            'total_cases': summary.get('total_cases'),
            'coverage_ratio': summary.get('coverage_ratio'),
            'coverage_weight_ratio': summary.get('coverage_weight_ratio'),
            'timed_out': summary.get('timed_out'),
            'crashed': summary.get('crashed'),
            'stop_reason': summary.get('stop_reason'),
        },
        'inputs': {
            'policy_snapshot': build_artifact_ref(
                resolved_run_dir / 'policy_snapshot.json',
                'policy_snapshot',
            ),
            'manifest_snapshot': build_artifact_ref(
                resolved_run_dir / 'manifest_snapshot.json',
                'manifest_snapshot',
            ),
        },
        'outputs': {
            'summary': summary.get('summary', {}),
            'case_count': len(cases),
            'completed_cases': summary.get('completed_cases'),
            'total_cases': summary.get('total_cases'),
            'coverage_ratio': summary.get('coverage_ratio'),
            'coverage_weight_ratio': summary.get('coverage_weight_ratio'),
            'cases': cases,
        },
        'artifacts': {
            'eval_summary': build_artifact_ref(summary_path, 'eval_summary'),
        },
    }


def materialize_completed_run_manifest(run_dir: Path, job_spec: dict | None = None) -> dict:
    resolved_run_dir = run_dir.resolve()
    manifest = build_completed_run_manifest(resolved_run_dir, job_spec=job_spec)
    manifest_path = resolved_run_dir / MANIFEST_FILENAME
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    return {
        'completed_run_manifest_path': repo_relative(manifest_path),
        'completed_run_manifest': manifest,
    }
