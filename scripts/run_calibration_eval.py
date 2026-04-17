import argparse
import csv
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from MM_calibration import run_calibration


# Keep TSV schema stable for backward compatibility.
RESULT_FIELDS = [
    'timestamp',
    'policy_name',
    'manifest_name',
    'aggregate_score',
    'mean_final_loss',
    'mean_improvement_pct',
    'best_case',
    'worst_case',
    'status',
    'run_dir',
]

TIMEOUT_POLICIES = ('continue', 'stop_after_case')


def read_json(path: Path) -> dict:
    with open(path, 'r') as f:
        return json.load(f)


def ensure_parent(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)


def append_results_row(results_tsv: Path, row: dict):
    ensure_parent(results_tsv)
    file_exists = results_tsv.exists()
    with open(results_tsv, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS, delimiter='\t')
        if not file_exists:
            writer.writeheader()
        writer.writerow({field: row.get(field, '') for field in RESULT_FIELDS})


def read_best_score(results_tsv: Path, manifest_name: Optional[str] = None):
    if not results_tsv.exists():
        return None
    with open(results_tsv, newline='') as f:
        reader = csv.DictReader(f, delimiter='\t')
        scores = []
        for row in reader:
            if manifest_name and row.get('manifest_name') != manifest_name:
                continue
            try:
                scores.append(float(row['aggregate_score']))
            except (KeyError, TypeError, ValueError):
                continue
    if not scores:
        return None
    return min(scores)


def get_policy_stage_plan(policy: dict) -> Optional[list]:
    stage_plan = policy.get('stage_plan')
    if isinstance(stage_plan, list) and stage_plan:
        return stage_plan
    return None


def get_base_strategy(policy: dict) -> str:
    return policy.get('base_run', {}).get('optimization_strategy', 'legacy')


def build_empty_summary() -> dict:
    return {
        'aggregate_score': None,
        'mean_final_loss': None,
        'mean_improvement_pct': None,
        'best_case': None,
        'worst_case': None,
    }


def summarize_progress(case_results: list, manifest_cases: list[dict]) -> dict:
    total_cases = len(manifest_cases)
    completed_cases = len(case_results)
    total_weight = sum(float(case.get('weight', 1.0)) for case in manifest_cases)
    completed_weight = sum(float(case.get('weight', 1.0)) for case in case_results)
    coverage_ratio = completed_cases / total_cases if total_cases else 0.0
    coverage_weight_ratio = completed_weight / total_weight if total_weight else 0.0
    completed_case_names = [case.get('name') for case in case_results if case.get('name')]
    remaining_case_names = [
        case.get('name')
        for case in manifest_cases
        if case.get('name') and case.get('name') not in completed_case_names
    ]
    return {
        'completed_cases': completed_cases,
        'total_cases': total_cases,
        'completed_weight': completed_weight,
        'total_weight': total_weight,
        'coverage_ratio': coverage_ratio,
        'coverage_weight_ratio': coverage_weight_ratio,
        'completed_case_names': completed_case_names,
        'remaining_case_names': remaining_case_names,
    }


def compute_time_aware_score(
    aggregate_score: Optional[float],
    elapsed_seconds: float,
    time_budget_seconds: Optional[float],
    coverage_ratio: float,
    completion_status: str,
) -> tuple[Optional[float], dict]:
    runtime_penalty = 0.0
    budget_ratio = None
    if time_budget_seconds is not None and time_budget_seconds > 0:
        budget_ratio = elapsed_seconds / time_budget_seconds
        runtime_penalty = max(0.0, budget_ratio - 1.0) * 5.0

    coverage_penalty = max(0.0, 1.0 - coverage_ratio) * 20.0
    completion_penalties = {
        'completed': 0.0,
        'partial': 6.0,
        'timed_out': 10.0,
        'crashed': 25.0,
    }
    completion_penalty = completion_penalties.get(completion_status, 0.0)

    if aggregate_score is None:
        return None, {
            'runtime_penalty': runtime_penalty,
            'coverage_penalty': coverage_penalty,
            'completion_penalty': completion_penalty,
            'budget_ratio': budget_ratio,
        }

    return (
        float(aggregate_score) + runtime_penalty + coverage_penalty + completion_penalty,
        {
            'runtime_penalty': runtime_penalty,
            'coverage_penalty': coverage_penalty,
            'completion_penalty': completion_penalty,
            'budget_ratio': budget_ratio,
        },
    )


def build_eval_summary_payload(
    *,
    timestamp: str,
    policy: dict,
    manifest: dict,
    case_results: list,
    elapsed_seconds: float,
    completion_status: str,
    benchmark_status: str,
    base_strategy: str,
    time_budget_seconds: Optional[float],
    case_time_budget_seconds: Optional[float],
    timeout_policy: str,
    stop_reason: Optional[str],
    error_payload: Optional[dict],
    in_progress: bool,
) -> dict:
    progress = summarize_progress(case_results, manifest.get('cases', []))
    summary = summarize_cases(case_results) if case_results else build_empty_summary()
    time_aware_score, time_aware_score_components = compute_time_aware_score(
        aggregate_score=summary.get('aggregate_score'),
        elapsed_seconds=elapsed_seconds,
        time_budget_seconds=time_budget_seconds,
        coverage_ratio=progress['coverage_ratio'],
        completion_status=completion_status,
    )
    summary['time_aware_score'] = time_aware_score
    summary['score_basis'] = (
        'full_manifest_weighted_mean'
        if completion_status == 'completed'
        else 'partial_completed_case_weighted_mean'
    )
    case_time_budget_exceeded = any(
        bool(case.get('case_time_budget_exceeded'))
        for case in case_results
    )
    time_budget_exceeded = (
        time_budget_seconds is not None and elapsed_seconds >= time_budget_seconds
    )
    status = benchmark_status if completion_status == 'completed' else completion_status
    return {
        'timestamp': timestamp,
        'policy_name': policy['policy_name'],
        'manifest_name': manifest['manifest_name'],
        'manifest_description': manifest.get('description') or manifest.get('notes', ''),
        'optimization_strategy': base_strategy,
        'parameter_classes': policy.get('base_run', {}).get('parameter_classes'),
        'stage_plan': get_policy_stage_plan(policy),
        'status': status,
        'benchmark_status': benchmark_status,
        'completion_status': completion_status,
        'in_progress': in_progress,
        'elapsed_seconds': elapsed_seconds,
        'time_budget_seconds': time_budget_seconds,
        'case_time_budget_seconds': case_time_budget_seconds,
        'timeout_policy': timeout_policy,
        'completed_cases': progress['completed_cases'],
        'total_cases': progress['total_cases'],
        'completed_weight': progress['completed_weight'],
        'total_weight': progress['total_weight'],
        'coverage_ratio': progress['coverage_ratio'],
        'coverage_weight_ratio': progress['coverage_weight_ratio'],
        'completed_case_names': progress['completed_case_names'],
        'remaining_case_names': progress['remaining_case_names'],
        'timed_out': completion_status == 'timed_out',
        'crashed': completion_status == 'crashed',
        'stopped_early': completion_status != 'completed',
        'time_budget_exceeded': time_budget_exceeded,
        'case_time_budget_exceeded': case_time_budget_exceeded,
        'stop_reason': stop_reason,
        'error': error_payload,
        'summary': summary,
        'time_aware_score_components': time_aware_score_components,
        'case_results': [
            {
                'name': case['name'],
                'description': case.get('description', ''),
                'weight': case['weight'],
                'score': case['score'],
                'score_breakdown': case['score_breakdown'],
                'report_path': case['report_path'],
                'effective_run_kwargs': case['effective_run_kwargs'],
                'optimization_strategy': case['report'].get(
                    'optimization_strategy',
                    case['effective_run_kwargs'].get('optimization_strategy', base_strategy),
                ),
                'parameter_classes': case['report'].get(
                    'parameter_classes',
                    case['effective_run_kwargs'].get('parameter_classes'),
                ),
                'final_loss': case['report']['final_loss'],
                'improvement_pct': case['report']['improvement_pct'],
                'monitor_metrics': case['report'].get('monitor_metrics', {}),
                'elapsed_seconds': case.get('elapsed_seconds'),
                'case_completion_status': case.get('case_completion_status', 'completed'),
                'case_budget_seconds': case.get('case_budget_seconds'),
                'case_time_budget_exceeded': case.get('case_time_budget_exceeded', False),
            }
            for case in case_results
        ],
    }


def write_eval_summary(run_root: Path, payload: dict):
    with open(run_root / 'eval_summary.json', 'w') as f:
        json.dump(payload, f, indent=2)


def merge_run_config(policy: dict, overrides: dict, out_dir: Path):
    base_run = dict(policy.get('base_run', {}))
    merged = dict(base_run)
    merged.update(overrides)
    merged['out_dir'] = str(out_dir)

    # Pass top-level stage plan through to run_calibration when present,
    # unless explicitly overridden by the case.
    if 'stage_plan' not in merged:
        policy_stage_plan = get_policy_stage_plan(policy)
        if policy_stage_plan is not None:
            merged['stage_plan'] = policy_stage_plan

    return merged


def apply_guardrails(run_kwargs: dict, policy: dict):
    guardrails = policy.get('guardrails', {}) or {}

    if guardrails.get('require_generate_plots_false', False):
        run_kwargs['generate_plots'] = False

    t_max = run_kwargs.get('t_max')
    min_t_max = guardrails.get('min_t_max')
    max_t_max = guardrails.get('max_t_max')
    if t_max is not None:
        if min_t_max is not None and float(t_max) < float(min_t_max):
            raise ValueError(f"t_max={t_max} violates min_t_max={min_t_max}")
        if max_t_max is not None and float(t_max) > float(max_t_max):
            raise ValueError(f"t_max={t_max} violates max_t_max={max_t_max}")

    curve_fit_strength = run_kwargs.get('curve_fit_strength')
    max_curve_fit_strength = guardrails.get('max_curve_fit_strength')
    if curve_fit_strength is not None and max_curve_fit_strength is not None:
        if float(curve_fit_strength) > float(max_curve_fit_strength):
            raise ValueError(
                f"curve_fit_strength={curve_fit_strength} violates "
                f"max_curve_fit_strength={max_curve_fit_strength}"
            )

    allowed_strategies = guardrails.get('allowed_optimization_strategies')
    strategy = run_kwargs.get('optimization_strategy', 'legacy')
    if allowed_strategies and strategy not in allowed_strategies:
        raise ValueError(
            f"optimization_strategy='{strategy}' not allowed by guardrails: {allowed_strategies}"
        )

    return run_kwargs


def metabolite_scale_weight(per_metabolite_row: dict, scoring: dict):
    exp_mean_abs = float(
        per_metabolite_row.get(
            'exp_mean_abs',
            per_metabolite_row.get('norm_factor', 0.0),
        )
    )
    scale_rules = scoring.get('scale_weight_rules', [])
    for rule in scale_rules:
        max_exp_mean_abs = rule.get('max_exp_mean_abs')
        if max_exp_mean_abs is None or exp_mean_abs <= float(max_exp_mean_abs):
            return float(rule.get('weight', 1.0))
    return 1.0


def compute_robust_target_loss(case_report: dict, scoring: dict):
    per_metabolite = case_report.get('per_metabolite', [])
    if not per_metabolite:
        return None
    nrmse_cap = float(scoring.get('robust_nrmse_cap', 10.0))
    weighted_nrmses = []
    for row in per_metabolite:
        weighted_nrmses.append(
            min(float(row.get('nrmse', 0.0)), nrmse_cap)
            * metabolite_scale_weight(row, scoring)
        )
    top_k = int(scoring.get('robust_top_k', 0))
    if top_k > 0:
        weighted_nrmses = sorted(weighted_nrmses, reverse=True)[:top_k]
    if not weighted_nrmses:
        return None
    return sum(weighted_nrmses) / len(weighted_nrmses)


def count_discarded_stages_or_phases(case_report: dict) -> Tuple[int, int]:
    stage_reports = case_report.get('stage_reports')
    if isinstance(stage_reports, list) and stage_reports:
        total = len(stage_reports)
        accepted = sum(1 for stage in stage_reports if stage.get('accepted', True))
        return accepted, total

    phases = case_report.get('phases', {})
    if isinstance(phases, dict) and phases:
        total = 0
        accepted = 0
        for phase_data in phases.values():
            total += 1
            if phase_data.get('accepted'):
                accepted += 1
        return accepted, total

    return 0, 0


def compute_case_score(case_report: dict, scoring: dict):
    monitor_metrics = case_report.get('monitor_metrics', {})
    score_breakdown = {}

    final_loss_weight = float(scoring.get('final_loss_weight', scoring.get('target_loss_weight', 1.0)))
    final_loss_component = final_loss_weight * float(case_report['final_loss'])
    score_breakdown['final_loss_component'] = final_loss_component
    score = final_loss_component

    robust_target_loss = compute_robust_target_loss(case_report, scoring)
    if robust_target_loss is not None:
        robust_target_component = float(scoring.get('robust_target_weight', 0.0)) * robust_target_loss
        score_breakdown['robust_target_loss'] = robust_target_loss
        score_breakdown['robust_target_component'] = robust_target_component
        score += robust_target_component

    endpoint_component = float(scoring.get('endpoint_weight', 0.0)) * float(
        monitor_metrics.get('endpoint_nrmse', 0.0)
    )
    score_breakdown['endpoint_component'] = endpoint_component
    score += endpoint_component

    for metric_name, metric_weight in scoring.get('monitor_weights', {}).items():
        metric_component = float(metric_weight) * float(monitor_metrics.get(metric_name, 0.0))
        score_breakdown[f'{metric_name}_component'] = metric_component
        score += metric_component

    accepted_count, total_count = count_discarded_stages_or_phases(case_report)
    discarded = max(total_count - accepted_count, 0)
    discard_component = float(scoring.get('discard_penalty', 0.0)) * discarded
    score_breakdown['discard_component'] = discard_component
    score += discard_component

    score_breakdown['total_score'] = score
    return score, score_breakdown


def evaluate_case(case: dict, policy: dict, run_root: Path, scoring: dict):
    case_dir = run_root / case['name']
    run_kwargs = merge_run_config(policy, case.get('run_overrides', {}), case_dir)
    run_kwargs = apply_guardrails(run_kwargs, policy)

    case_started_at = time.monotonic()
    run_calibration(**run_kwargs)
    elapsed_seconds = time.monotonic() - case_started_at

    report_path = case_dir / 'calibration_report.json'
    if not report_path.exists():
        raise FileNotFoundError(f"Expected calibration report not found: {report_path}")

    report = read_json(report_path)
    score, score_breakdown = compute_case_score(report, scoring)

    return {
        'name': case['name'],
        'description': case.get('description', ''),
        'weight': float(case.get('weight', 1.0)),
        'score': score,
        'score_breakdown': score_breakdown,
        'report': report,
        'report_path': str(report_path),
        'effective_run_kwargs': run_kwargs,
        'elapsed_seconds': elapsed_seconds,
        'case_completion_status': 'completed',
    }


def summarize_cases(case_results: list):
    if not case_results:
        raise ValueError("Manifest contains no cases to evaluate.")

    total_weight = sum(case['weight'] for case in case_results)
    weighted_score = sum(case['score'] * case['weight'] for case in case_results) / max(total_weight, 1e-12)
    mean_final_loss = sum(float(case['report']['final_loss']) for case in case_results) / len(case_results)
    mean_improvement_pct = sum(float(case['report']['improvement_pct']) for case in case_results) / len(case_results)
    best_case = min(case_results, key=lambda case: case['score'])
    worst_case = max(case_results, key=lambda case: case['score'])

    return {
        'aggregate_score': weighted_score,
        'mean_final_loss': mean_final_loss,
        'mean_improvement_pct': mean_improvement_pct,
        'best_case': best_case['name'],
        'worst_case': worst_case['name'],
    }


def main():
    parser = argparse.ArgumentParser(description='Fixed eval harness for RBC calibration outer-loop autoresearch')
    parser.add_argument('--policy', type=str, default=str(ROOT / 'config' / 'rbc_autoresearch_policy.json'))
    parser.add_argument('--manifest', type=str, default=str(ROOT / 'config' / 'rbc_calibration_benchmarks.json'))
    parser.add_argument('--time-budget-seconds', type=float, default=None)
    parser.add_argument('--case-time-budget-seconds', type=float, default=None)
    parser.add_argument('--timeout-policy', choices=TIMEOUT_POLICIES, default='stop_after_case')
    args = parser.parse_args()

    if args.time_budget_seconds is not None and args.time_budget_seconds <= 0:
        raise ValueError('time_budget_seconds must be positive when provided')
    if args.case_time_budget_seconds is not None and args.case_time_budget_seconds <= 0:
        raise ValueError('case_time_budget_seconds must be positive when provided')

    policy_path = Path(args.policy).resolve()
    manifest_path = Path(args.manifest).resolve()
    policy = read_json(policy_path)
    manifest = read_json(manifest_path)

    timestamp = time.strftime('%Y%m%d_%H%M%S')
    run_root = ROOT / 'Simulations' / 'brodbar' / 'autoresearch' / f"{timestamp}_{policy['policy_name']}"
    run_root.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(policy_path, run_root / 'policy_snapshot.json')
    shutil.copyfile(manifest_path, run_root / 'manifest_snapshot.json')

    run_started_at = time.monotonic()
    case_results = []
    completion_status = 'partial'
    benchmark_status = 'not_comparable'
    stop_reason = None
    error_payload = None
    case_results = []

    base_strategy = get_base_strategy(policy)
    write_eval_summary(
        run_root,
        build_eval_summary_payload(
            timestamp=timestamp,
            policy=policy,
            manifest=manifest,
            case_results=case_results,
            elapsed_seconds=time.monotonic() - run_started_at,
            completion_status=completion_status,
            benchmark_status=benchmark_status,
            base_strategy=base_strategy,
            time_budget_seconds=args.time_budget_seconds,
            case_time_budget_seconds=args.case_time_budget_seconds,
            timeout_policy=args.timeout_policy,
            stop_reason=stop_reason,
            error_payload=error_payload,
            in_progress=True,
        ),
    )

    manifest_cases = manifest.get('cases', [])
    for case in manifest_cases:
        elapsed_before_case = time.monotonic() - run_started_at
        if (
            args.time_budget_seconds is not None
            and elapsed_before_case >= args.time_budget_seconds
        ):
            completion_status = 'timed_out'
            stop_reason = (
                f"time_budget_seconds exceeded before starting case '{case['name']}'"
            )
            break

        print(f"\n=== Running case: {case['name']} ===")
        try:
            case_result = evaluate_case(
                case=case,
                policy=policy,
                run_root=run_root,
                scoring=manifest.get('scoring', {}),
            )
        except Exception as exc:
            completion_status = 'crashed'
            stop_reason = f"case '{case['name']}' raised {type(exc).__name__}"
            error_payload = {
                'case_name': case['name'],
                'error_type': type(exc).__name__,
                'message': str(exc),
            }
            write_eval_summary(
                run_root,
                build_eval_summary_payload(
                    timestamp=timestamp,
                    policy=policy,
                    manifest=manifest,
                    case_results=case_results,
                    elapsed_seconds=time.monotonic() - run_started_at,
                    completion_status=completion_status,
                    benchmark_status='not_comparable',
                    base_strategy=base_strategy,
                    time_budget_seconds=args.time_budget_seconds,
                    case_time_budget_seconds=args.case_time_budget_seconds,
                    timeout_policy=args.timeout_policy,
                    stop_reason=stop_reason,
                    error_payload=error_payload,
                    in_progress=False,
                ),
            )
            raise

        case_result['case_budget_seconds'] = args.case_time_budget_seconds
        case_result['case_time_budget_exceeded'] = (
            args.case_time_budget_seconds is not None
            and case_result['elapsed_seconds'] > args.case_time_budget_seconds
        )
        case_results.append(case_result)

        elapsed_after_case = time.monotonic() - run_started_at
        case_stop_reason = None
        case_completion_status = 'partial'
        if (
            args.case_time_budget_seconds is not None
            and case_result['elapsed_seconds'] > args.case_time_budget_seconds
            and args.timeout_policy == 'stop_after_case'
        ):
            case_completion_status = 'timed_out'
            case_stop_reason = (
                f"case_time_budget_seconds exceeded by case '{case['name']}'"
            )
        elif (
            args.time_budget_seconds is not None
            and elapsed_after_case >= args.time_budget_seconds
            and args.timeout_policy == 'stop_after_case'
            and len(case_results) < len(manifest_cases)
        ):
            case_completion_status = 'timed_out'
            case_stop_reason = (
                f"time_budget_seconds exceeded after completing case '{case['name']}'"
            )

        write_eval_summary(
            run_root,
            build_eval_summary_payload(
                timestamp=timestamp,
                policy=policy,
                manifest=manifest,
                case_results=case_results,
                elapsed_seconds=elapsed_after_case,
                completion_status=case_completion_status,
                benchmark_status='not_comparable',
                base_strategy=base_strategy,
                time_budget_seconds=args.time_budget_seconds,
                case_time_budget_seconds=args.case_time_budget_seconds,
                timeout_policy=args.timeout_policy,
                stop_reason=case_stop_reason,
                error_payload=None,
                in_progress=case_completion_status == 'partial',
            ),
        )

        if case_stop_reason is not None:
            completion_status = case_completion_status
            stop_reason = case_stop_reason
            break

    elapsed_seconds = time.monotonic() - run_started_at
    if completion_status not in ('timed_out', 'crashed'):
        completion_status = 'completed'

    results_tsv = ROOT / Path(manifest['results_tsv'])
    if completion_status == 'completed':
        summary = summarize_cases(case_results)
        best_prior_score = read_best_score(results_tsv, manifest_name=manifest.get('manifest_name'))
        if best_prior_score is None:
            benchmark_status = 'baseline'
        elif summary['aggregate_score'] <= best_prior_score:
            benchmark_status = 'keep'
        else:
            benchmark_status = 'discard'
    else:
        benchmark_status = 'not_comparable'

    summary_payload = build_eval_summary_payload(
        timestamp=timestamp,
        policy=policy,
        manifest=manifest,
        case_results=case_results,
        elapsed_seconds=elapsed_seconds,
        completion_status=completion_status,
        benchmark_status=benchmark_status,
        base_strategy=base_strategy,
        time_budget_seconds=args.time_budget_seconds,
        case_time_budget_seconds=args.case_time_budget_seconds,
        timeout_policy=args.timeout_policy,
        stop_reason=stop_reason,
        error_payload=error_payload,
        in_progress=False,
    )
    write_eval_summary(run_root, summary_payload)

    append_results_row(
        results_tsv,
        {
            'timestamp': timestamp,
            'policy_name': policy['policy_name'],
            'manifest_name': manifest['manifest_name'],
            'aggregate_score': summary_payload['summary']['aggregate_score'],
            'mean_final_loss': summary_payload['summary']['mean_final_loss'],
            'mean_improvement_pct': summary_payload['summary']['mean_improvement_pct'],
            'best_case': summary_payload['summary']['best_case'],
            'worst_case': summary_payload['summary']['worst_case'],
            'status': summary_payload['status'],
            'run_dir': str(run_root),
        },
    )

    print('\n=== RBC outer-loop evaluation summary ===')
    print(f"policy: {policy['policy_name']}")
    print(f"optimization_strategy: {base_strategy}")
    if get_policy_stage_plan(policy):
        print(f"stage_plan: {len(get_policy_stage_plan(policy))} stages")
    if summary_payload['summary']['aggregate_score'] is not None:
        print(f"aggregate_score: {summary_payload['summary']['aggregate_score']:.6f}")
    else:
        print('aggregate_score: n/a')
    if summary_payload['summary']['mean_final_loss'] is not None:
        print(f"mean_final_loss: {summary_payload['summary']['mean_final_loss']:.6f}")
    else:
        print('mean_final_loss: n/a')
    if summary_payload['summary']['mean_improvement_pct'] is not None:
        print(f"mean_improvement_pct: {summary_payload['summary']['mean_improvement_pct']:.3f}")
    else:
        print('mean_improvement_pct: n/a')
    print(f"best_case: {summary_payload['summary']['best_case']}")
    print(f"worst_case: {summary_payload['summary']['worst_case']}")
    print(f"completion_status: {summary_payload['completion_status']}")
    print(f"benchmark_status: {summary_payload['benchmark_status']}")
    print(f"coverage_ratio: {summary_payload['coverage_ratio']:.3f}")
    print(f"elapsed_seconds: {summary_payload['elapsed_seconds']:.2f}")
    print(f"time_aware_score: {summary_payload['summary']['time_aware_score']}")
    print(f"status: {summary_payload['status']}")
    print(f"run_dir: {run_root}")


if __name__ == '__main__':
    main()