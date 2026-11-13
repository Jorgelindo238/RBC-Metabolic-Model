"""Successor Vmax-only sensitivity/search with qualified recorded Radau."""
import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import json
import sys

import numpy as np
import scipy
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from run_vmax_requalification import historical_metrics, compare_files
from run_pgk_ndpk_profile import read, write, sha, verify_archive, rhs_for, scored, reserve_for
from fla_vmax_requalification import exact_parameters, within_original_box
from fla_stepper_diagnostics import record_stepper
from fla_bounded_jacobian import BoundedJacobian
from fla_integration_diagnostics import audit_recorded_solution
from fla_temporal_vmax import lp_step


def vector_step(x, hi, step):
    x = np.asarray(x, float)
    return np.where(x + step <= hi, step, -step)


def evaluate(folder, f, vector, names, profile='strict', backend='joint', flux_audit=False):
    folder = Path(folder)
    folder.mkdir(parents=True)
    plan = f['requalification_plan']
    parameters = exact_parameters(f, vector)
    if not within_original_box(f, vector):
        raise ValueError('Original Vmax box violated')
    write(folder / 'parameters.json', parameters)
    try:
        rhs = rhs_for(f, parameters, f['temporal']['network'], backend)
        jac = BoundedJacobian(rhs, minimum_step=plan['jacobian_minimum_step_mM'][profile])
        with threadpool_limits(1):
            arrays, diagnostics = record_stepper(rhs, f['initial'], 15, f['temporal']['fit_days'],
                {**plan['profiles'][profile], 'jac': jac}, f['numeric']['negative_tolerance_mM'], plan['method'])
            diagnostics['bounded_jacobian'] = jac.diagnostics()
            np.savez_compressed(folder / 'trajectory_evidence.npz', **arrays)
            write(folder / 'diagnostics.json', diagnostics)
            if not diagnostics['concentration_gate_pass']:
                result = {'valid': False, 'error': 'recorded physical-support gate failed'}
            else:
                indices = np.searchsorted(arrays['time'], f['temporal']['fit_days'])
                assert np.array_equal(arrays['time'][indices], f['temporal']['fit_days'])
                result = {'valid': True, 'prediction_mM': arrays['states'][np.ix_(
                    [rhs.names.index(n) for n in names], indices)].tolist()}
                if flux_audit:
                    other = rhs_for(f, parameters, f['temporal']['network'], 'full' if backend == 'joint' else 'joint')
                    evidence, stats = audit_recorded_solution(rhs, arrays, diagnostics, f['numeric'],
                                                               lambda t, x: other.rates(t, x)[:2])
                    np.savez_compressed(folder / 'flux_evidence.npz', **evidence)
                    write(folder / 'flux_checks.json', stats)
                    result['valid'] = stats['numerical_pass']
    except (ValueError, RuntimeError, FloatingPointError, OverflowError) as error:
        result = {'valid': False, 'error': str(error)}
    write(folder / 'result.json', result)
    return result


def execute(out):
    source = ROOT / 'output/vmax_requalification_2026_11_09'
    if out.exists():
        raise ValueError('Fresh successor directory required')
    verify_archive(source)
    f = read(source / 'execution_design.json')
    if scipy.__version__ != f['requalification_plan']['scipy_version']:
        raise ValueError('Qualified SciPy version required')
    if not read(source / 'control_gate.json')['pass']:
        raise ValueError('Qualified reference certificate required')
    obs = read(source / 'observations.json')
    panel, references = historical_metrics(f, obs)
    plan, design = f['temporal'], f['design']
    lo, hi = np.log([design['factor_bounds'][k] for k in design['groups']]).T
    reserve = reserve_for(references['strict'], panel, f)
    out.mkdir(parents=True)
    write(out / 'execution_design.json', f)
    write(out / 'observations.json', obs)
    write(out / 'historical_reference_metrics.json', references)
    write(out / 'protocol.json', {'source': str(source), 'source_manifest_sha256': sha(source / 'manifest.json'),
        'maximum_search_attempts': 80, 'rounds': 4, 'workers': 3, 'validation_integrations': 2,
        'objective': 'inherited absolute ATP/ADP J15 minimax', 'guards_rebased': False,
        'sensitivity_step_log': plan['difference_step_log'], 'initial_center': f['profile_center'],
        'solver': f['requalification_plan'], 'production_promotion_allowed': False,
        'code_sha256': {str(p.relative_to(ROOT)): sha(p) for p in [Path(__file__),
            ROOT / 'scripts/verify_corrected_vmax.py', ROOT / 'src/fla_temporal_vmax.py',
            ROOT / 'src/fla_absolute_vmax.py', ROOT / 'src/fla_bounded_jacobian.py',
            ROOT / 'src/fla_stepper_diagnostics.py', ROOT / 'src/fla_integration_diagnostics.py']}})
    cache, trace, steps = {}, [], []

    def feasible(row):
        return row['valid'] and row['reserved_guards_pass']

    with ProcessPoolExecutor(max_workers=3) as pool, (out / 'trace.jsonl').open('x', encoding='utf-8') as stream:
        def batch(vectors, stage):
            vectors = [tuple(np.clip(v, lo, hi)) for v in vectors]
            pending = [v for v in dict.fromkeys(vectors) if v not in cache]
            if len(trace) + len(pending) > 80:
                raise ValueError('Registered search limit exceeded')
            jobs = []
            for offset, v in enumerate(pending):
                number = len(trace) + offset + 1
                folder = out / 'search' / f'{number:03d}'
                jobs.append((v, number, folder, pool.submit(evaluate, folder, f, v, panel['names'])))
            for v, number, folder, future in jobs:
                result = future.result()
                row = {'attempt': number, 'stage': stage, 'log_factors': list(v), **result}
                if row['valid']:
                    try:
                        row.update(scored(row['prediction_mM'], references['strict'], panel, f))
                    except ValueError as error:
                        row.update(valid=False, error=str(error))
                trace.append(row)
                cache[v] = row
                stream.write(json.dumps(row, allow_nan=False) + '\n')
                stream.flush()
                print(f'{number:03d} {stage}: valid={row["valid"]} feasible={feasible(row)}', flush=True)
            return [cache[v] for v in vectors]

        current = batch([f['profile_center']], 'working_center')[0]
        if not feasible(current):
            raise ValueError('Working centre fails unchanged guards; stop before optimization')
        start = current
        radius = plan['initial_radius_log']
        for iteration in range(4):
            x = np.array(current['log_factors'])
            h = vector_step(x, hi, plan['difference_step_log'])
            diffs = batch(x + np.diag(h), f'round{iteration+1}_sensitivity')
            r0 = np.array(list(current['absolute']['sides'].values()))
            g0 = np.array(list(current['feasibility_guards'].values()))
            jr, jg = np.zeros((len(r0), len(x))), np.zeros((len(g0), len(x)))
            good, sensitivities = [], {}
            for i, row in enumerate(diffs):
                if not row['valid']:
                    continue
                dx = row['log_factors'][i] - x[i]
                if dx == 0:
                    continue
                good.append(i)
                jr[:, i] = (np.array(list(row['absolute']['sides'].values())) - r0) / dx
                jg[:, i] = (np.array(list(row['feasibility_guards'].values())) - g0) / dx
                sensitivities[list(design['groups'])[i]] = {
                    'attempt': row['attempt'], 'step_log': dx,
                    'd_concentration_d_log_factor': ((np.array(row['prediction_mM']) - current['prediction_mM']) / dx).tolist()}
            write(out / f'sensitivity_round{iteration+1}.json', {'anchor_attempt': current['attempt'],
                  'pool_names': panel['names'], 'days': panel['days'], 'groups': sensitivities,
                  'objective_sides': list(current['absolute']['sides']), 'objective_jacobian': jr.tolist(),
                  'guard_names': list(current['feasibility_guards']), 'guard_jacobian': jg.tolist()})
            a, b = lo.copy(), hi.copy()
            missing = list(set(range(len(x))) - set(good))
            a[missing] = b[missing] = x[missing]
            proposal = lp_step(x, a, b, radius, r0, jr, g0, jg, reserve) if good else None
            step = {'round': iteration+1, 'anchor_attempt': current['attempt'], 'valid_derivatives': len(good),
                    'radius': radius, 'proposal': proposal, 'accepted': None}
            if proposal and proposal['predicted_objective'] < current['absolute']['objective']:
                candidates = batch([x + alpha*np.array(proposal['delta']) for alpha in plan['line_search_fractions']],
                                   f'round{iteration+1}_backtrack')
                passed = [r for r in candidates if feasible(r) and
                          r['absolute']['objective'] < current['absolute']['objective'] - plan['minimum_step_objective_gain']]
                if passed:
                    current = min(passed, key=lambda r: r['absolute']['objective'])
                    step['accepted'] = current['attempt']
            steps.append(step)
            write(out / 'search_progress.json', {'steps': steps, 'selected_attempt': current['attempt']})
            print(f'ROUND {iteration+1}: gap={current["absolute"]["objective"]:.9g}, accepted={step["accepted"]}', flush=True)
            radius = min(plan['maximum_radius_log'], radius*1.25) if step['accepted'] else radius*.5
        write(out / 'search_result.json', {'start': start, 'selected': current, 'steps': steps, 'attempts': len(trace)})
        jobs = {p: pool.submit(evaluate, out / 'validation' / p, f, current['log_factors'], panel['names'],
                              p, 'full', True) for p in ('strict', 'ultrastrict')}
        validated = {}
        for profile, job in jobs.items():
            row = job.result()
            if row['valid']:
                row.update(scored(row['prediction_mM'], references[profile], panel, f))
            validated[profile] = row
            print(f'Validation {profile}: valid={row["valid"]}', flush=True)
    pair = compare_files(out / 'validation/strict/flux_evidence.npz', out / 'validation/ultrastrict/flux_evidence.npz', f)
    admissible = pair['pass'] and all(feasible(r) for r in validated.values())
    write(out / 'summary.json', {'search_attempts': len(trace), 'validation': validated, 'paired': pair,
          'admitted_under_inherited_guards': admissible, 'selected_attempt': current['attempt'],
          'absolute_targets_reached': admissible and all(r['absolute']['target_pass'] for r in validated.values()),
          'optimization_executed': True, 'Km_changed': False, 'initial_changed': False,
          'production_promoted': False, 'global_optimality': False})
    verify_archive(source)
    write(out / 'manifest.json', {p.relative_to(out).as_posix(): sha(p) for p in out.rglob('*') if p.is_file()})
    print(f'FINISHED: admitted={admissible}; selected={current["attempt"]}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT / 'output/corrected_vmax_2026_11_12')
    with threadpool_limits(1):
        execute(parser.parse_args().out)
