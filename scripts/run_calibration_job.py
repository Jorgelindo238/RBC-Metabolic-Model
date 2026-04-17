import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
try:
    from scripts.calibration_artifacts import (
        ArtifactContractError,
        materialize_completed_run_manifest,
    )
    from scripts.run_registry import build_run_registry_record
    from scripts.run_registry_support import RunRegistryContractError
except ImportError:
    from calibration_artifacts import ArtifactContractError, materialize_completed_run_manifest
    from run_registry import build_run_registry_record
    from run_registry_support import RunRegistryContractError

ROOT = Path(__file__).resolve().parent.parent
CONFIG_ROOT = ROOT / 'config'
AUTORESEARCH_ROOT = ROOT / 'Simulations' / 'brodbar' / 'autoresearch'
EVAL_SCRIPT = ROOT / 'scripts' / 'run_calibration_eval.py'
REQUIRED_STRING_FIELDS = ('job_name', 'hypothesis', 'policy_path', 'manifest_path')
OPTIONAL_STRING_FIELDS = ('baseline_run_dir', 'promotion_manifest_path')
OPTIONAL_NUMERIC_FIELDS = ('time_budget_seconds', 'case_time_budget_seconds')
TIMEOUT_POLICIES = ('continue', 'stop_after_case')


class JobSpecError(ValueError):
    pass


def emit_json(payload: dict, exit_code: int = 0):
    print(json.dumps(payload, indent=2))
    raise SystemExit(exit_code)


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def read_json(path: Path) -> dict:
    try:
        with open(path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError as exc:
        raise JobSpecError(f'JSON file does not exist: {path}') from exc
    except json.JSONDecodeError as exc:
        raise JobSpecError(f'Invalid JSON in {path}: {exc.msg}') from exc
    if not isinstance(data, dict):
        raise JobSpecError(f'Expected JSON object in {path}')
    return data


def resolve_repo_path(value: str, field_name: str) -> Path:
    raw_path = Path(value)
    resolved = raw_path if raw_path.is_absolute() else ROOT / raw_path
    try:
        resolved = resolved.resolve(strict=True)
    except FileNotFoundError as exc:
        raise JobSpecError(f'{field_name} does not exist: {value}') from exc
    if not is_within(resolved, ROOT):
        raise JobSpecError(f'{field_name} must stay inside the repository: {value}')
    return resolved


def validate_config_json_path(value: str, field_name: str) -> str:
    path = resolve_repo_path(value, field_name)
    if path.suffix.lower() != '.json':
        raise JobSpecError(f'{field_name} must point to a JSON file: {value}')
    if not is_within(path, CONFIG_ROOT):
        raise JobSpecError(f'{field_name} must be under config/: {value}')
    return str(path.relative_to(ROOT))


def validate_optional_run_dir(value: str, field_name: str) -> str:
    path = resolve_repo_path(value, field_name)
    if not path.is_dir():
        raise JobSpecError(f'{field_name} must point to an existing directory: {value}')
    if not is_within(path, AUTORESEARCH_ROOT):
        raise JobSpecError(
            f'{field_name} must stay under Simulations/brodbar/autoresearch/: {value}'
        )
    return str(path.relative_to(ROOT))


def validate_job_spec(job_spec: dict) -> dict:
    normalized = {}
    for field_name in REQUIRED_STRING_FIELDS:
        value = job_spec.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise JobSpecError(f'{field_name} is required and must be a non-empty string')
        normalized[field_name] = value.strip()

    normalized['policy_path'] = validate_config_json_path(normalized['policy_path'], 'policy_path')
    normalized['manifest_path'] = validate_config_json_path(
        normalized['manifest_path'],
        'manifest_path',
    )

    for field_name in OPTIONAL_STRING_FIELDS:
        value = job_spec.get(field_name)
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            raise JobSpecError(f'{field_name} must be a non-empty string when provided')
        if field_name == 'baseline_run_dir':
            normalized[field_name] = validate_optional_run_dir(value.strip(), field_name)
        else:
            normalized[field_name] = validate_config_json_path(value.strip(), field_name)

    for field_name in OPTIONAL_NUMERIC_FIELDS:
        value = job_spec.get(field_name)
        if value is None:
            continue
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise JobSpecError(f'{field_name} must be a positive number when provided')
        if float(value) <= 0:
            raise JobSpecError(f'{field_name} must be a positive number when provided')
        normalized[field_name] = float(value)

    timeout_policy = job_spec.get('timeout_policy')
    if timeout_policy is not None:
        if not isinstance(timeout_policy, str) or timeout_policy not in TIMEOUT_POLICIES:
            raise JobSpecError(
                f"timeout_policy must be one of {TIMEOUT_POLICIES} when provided"
            )
        normalized['timeout_policy'] = timeout_policy

    metadata = job_spec.get('metadata', {})
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise JobSpecError('metadata must be a JSON object when provided')
    normalized['metadata'] = metadata

    tags = job_spec.get('tags', [])
    if tags is None:
        tags = []
    if not isinstance(tags, list) or any(not isinstance(tag, str) or not tag.strip() for tag in tags):
        raise JobSpecError('tags must be an array of non-empty strings when provided')
    normalized['tags'] = [tag.strip() for tag in tags]

    job_version = job_spec.get('job_version', 1)
    if not isinstance(job_version, int) or job_version < 1:
        raise JobSpecError('job_version must be a positive integer when provided')
    normalized['job_version'] = job_version

    return normalized


def load_and_validate_job_spec(job_path: Path) -> dict:
    resolved_job_path = job_path.resolve()
    job_spec = read_json(resolved_job_path)
    normalized = validate_job_spec(job_spec)
    normalized['job_path'] = (
        str(resolved_job_path.relative_to(ROOT))
        if is_within(resolved_job_path, ROOT)
        else str(resolved_job_path)
    )
    return normalized


def find_latest_eval_summary(start_time: float):
    if not AUTORESEARCH_ROOT.exists():
        return None

    candidates = []
    for summary_path in AUTORESEARCH_ROOT.glob('*/eval_summary.json'):
        try:
            if summary_path.stat().st_mtime >= start_time - 1:
                candidates.append(summary_path)
        except FileNotFoundError:
            continue

    if not candidates:
        return None

    latest_path = max(candidates, key=lambda path: path.stat().st_mtime)
    summary = read_json(latest_path)
    return {
        'run_dir': str(latest_path.parent.relative_to(ROOT)),
        'eval_summary_path': str(latest_path.relative_to(ROOT)),
        'eval_summary': summary,
    }


def build_command(job_spec: dict) -> list[str]:
    command = [
        sys.executable,
        str(EVAL_SCRIPT),
        '--policy',
        job_spec['policy_path'],
        '--manifest',
        job_spec['manifest_path'],
    ]
    if job_spec.get('time_budget_seconds') is not None:
        command.extend(['--time-budget-seconds', str(job_spec['time_budget_seconds'])])
    if job_spec.get('case_time_budget_seconds') is not None:
        command.extend(['--case-time-budget-seconds', str(job_spec['case_time_budget_seconds'])])
    if job_spec.get('timeout_policy') is not None:
        command.extend(['--timeout-policy', job_spec['timeout_policy']])
    return command


def run_job(job_spec: dict) -> dict:
    command = build_command(job_spec)
    start_time = time.time()
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )

    payload = {
        'status': 'completed' if completed.returncode == 0 else 'failed',
        'job': job_spec,
        'command': command,
        'returncode': completed.returncode,
        'stdout': completed.stdout,
        'stderr': completed.stderr,
    }

    latest_summary = find_latest_eval_summary(start_time)
    if latest_summary is not None:
        payload.update(latest_summary)
        eval_summary = latest_summary.get('eval_summary', {})
        if isinstance(eval_summary, dict):
            payload['status'] = (
                eval_summary.get('completion_status')
                or eval_summary.get('status')
                or payload['status']
            )
            payload['completion_status'] = eval_summary.get('completion_status')
            payload['benchmark_status'] = eval_summary.get('benchmark_status')
            payload['elapsed_seconds'] = eval_summary.get('elapsed_seconds')
            payload['time_budget_seconds'] = eval_summary.get('time_budget_seconds')
            payload['case_time_budget_seconds'] = eval_summary.get('case_time_budget_seconds')
            payload['timeout_policy'] = eval_summary.get('timeout_policy')
            payload['completed_cases'] = eval_summary.get('completed_cases')
            payload['total_cases'] = eval_summary.get('total_cases')
            payload['coverage_ratio'] = eval_summary.get('coverage_ratio')
            payload['coverage_weight_ratio'] = eval_summary.get('coverage_weight_ratio')
            payload['timed_out'] = eval_summary.get('timed_out')
            payload['crashed'] = eval_summary.get('crashed')
            summary_section = eval_summary.get('summary', {})
            if isinstance(summary_section, dict):
                payload['time_aware_score'] = summary_section.get('time_aware_score')
        try:
            manifest_payload = materialize_completed_run_manifest(
                ROOT / latest_summary['run_dir'],
                job_spec=job_spec,
            )
            payload.update(manifest_payload)
            try:
                payload['run_registry_record'] = build_run_registry_record(
                    manifest_payload['completed_run_manifest'],
                    manifest_path=ROOT / manifest_payload['completed_run_manifest_path'],
                )
            except RunRegistryContractError as exc:
                payload['run_registry_contract_error'] = str(exc)
            except Exception as exc:
                payload['run_registry_contract_error'] = (
                    f'Unexpected run registry error: {type(exc).__name__}: {exc}'
                )
        except ArtifactContractError as exc:
            payload['artifact_contract_error'] = str(exc)

    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('--job', required=True, help='Path to a calibration job JSON spec')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate the job spec and print the delegated evaluator command without executing it',
    )
    return parser.parse_args()


def main():
    args = parse_args()
    job_path = Path(args.job)
    if not job_path.is_absolute():
        job_path = ROOT / job_path

    try:
        job_spec = load_and_validate_job_spec(job_path)
    except JobSpecError as exc:
        emit_json({'status': 'error', 'error': str(exc)}, exit_code=1)

    payload = {
        'status': 'validated',
        'job': job_spec,
        'command': build_command(job_spec),
    }
    if args.dry_run:
        emit_json(payload)

    result = run_job(job_spec)
    if result['returncode'] != 0:
        emit_json(result, exit_code=result['returncode'])
    emit_json(result)


if __name__ == '__main__':
    main()
