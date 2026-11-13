"""Constrained multistart Vmax-only SLSQP search with the qualified recorded Radau.

Successor of scripts/run_corrected_vmax.py (sealed campaign
output/corrected_vmax_2026_11_12, untouched). Same network, initial state, Km,
transport, H, threshold, 14 groups/17 capacities, original boxes, J4/J8/J11/J15
guards with reserve and historical reference metrics, same absolute ATP/ADP J15
objective. Every evaluation goes through run_corrected_vmax.evaluate (strict
Radau, bounded Jacobian, accepted/dense/quadrature evidence per attempt).

Entry points (run by Codex, not by the preparing agent):
  python scripts/run_multistart_vmax.py --out output/multistart_vmax_2026_11_12
  python scripts/run_multistart_vmax.py --out output/multistart_vmax_2026_11_12 --resume
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import json
import os
from pathlib import Path
import sys

import numpy as np
import scipy
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from run_corrected_vmax import evaluate
from run_vmax_requalification import historical_metrics, compare_files
from run_pgk_ndpk_profile import read, write, sha, verify_archive, scored, reserve_for
from fla_vmax_requalification import exact_parameters
from fla_absolute_vmax import evaluate_screen
from fla_multistart_vmax import (EvaluationStore, MultistartSearch, admissible, feasible, joint_seeds,
                                 row_values, select_finalists)

CONFIG = ROOT / 'config/fla_multistart_vmax_2026_11_12.json'
CODE = [Path(__file__), ROOT / 'scripts/verify_multistart_vmax.py', ROOT / 'src/fla_multistart_vmax.py', CONFIG,
        ROOT / 'tasks/fla_multistart_vmax_protocol_2026_11_12.md', ROOT / 'qa/test_fla_multistart_vmax.py',
        ROOT / 'scripts/run_corrected_vmax.py', ROOT / 'scripts/run_vmax_requalification.py',
        ROOT / 'scripts/run_pgk_ndpk_profile.py', ROOT / 'src/fla_vmax_requalification.py',
        ROOT / 'src/fla_temporal_vmax.py', ROOT / 'src/fla_absolute_vmax.py', ROOT / 'src/fla_bounded_jacobian.py',
        ROOT / 'src/fla_stepper_diagnostics.py', ROOT / 'src/fla_integration_diagnostics.py']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def code_hashes():
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in CODE}


def check_invariants(cfg, f, row):
    inv, groups = cfg['invariants'], f['design']['groups']
    require(len(groups) == inv['groups'] and sum(map(len, groups.values())) == inv['capacities'],
            '14 groups / 17 capacities required')
    for name, members in inv['paired_groups_unchanged'].items():
        require(groups[name] == members, f'{name} grouping changed')
    require(list(row['absolute']['sides']) == inv['objective_sides'], 'objective sides changed')
    require(len(row['feasibility_guards']) == inv['feasibility_guards'], '84 feasibility guards required')
    require(f['temporal']['fit_days'] == inv['fit_days'], 'guard dates changed')
    require(list(f['absolute_targets']) == ['ATP', 'ADP'] and
            all(t['day'] == 15 for t in f['absolute_targets'].values()), 'absolute J15 ATP/ADP objective changed')
    require(all(inv[k] is False for k in ('guards_rebased', 'bounds_changed', 'Km_changed', 'initial_changed',
                                          'transport_changed', 'threshold_changed', 'latent_reinitialized',
                                          'reaction_changed')), 'scientific invariant flag changed')
    s, v = cfg['search'], cfg['validation']
    require(s['distinct_ode_evaluation_limit'] == 240, 'registered budget is 240 distinct ODE evaluations')
    require(sum(s['start_evaluation_limits'].values()) <= s['distinct_ode_evaluation_limit'], 'start limits too large')
    require(list(s['start_evaluation_limits']) == s['start_order'], 'start order and limits disagree')
    require(s['difference_step_log'] == f['temporal']['difference_step_log'] == 0.006 and s['check_step_log'] == 0.003,
            'difference steps 0.006/0.003 required')
    require(s['optimizer_reserve_multiplier'] == 1.0, 'optimizer guard margin is the inherited full reserve')
    require(s['minimum_step_objective_gain'] == f['temporal']['minimum_step_objective_gain'], 'gain threshold changed')
    require(v['profiles'] == ['strict', 'ultrastrict'] and v['backend'] == 'full' and v['flux_audit'] is True,
            'strict/ultrastrict full-backend validation required')
    require(v['max_integrations'] <= 12 and len(v['profiles']) * v['max_finalists'] <= v['max_integrations'],
            'at most 12 validation integrations')
    require(cfg['workers'] <= 3 and cfg['seeds']['maximum_additional'] <= 3, 'at most 3 workers and 3 seeds')
    require(not cfg['production_promotion_allowed'] and not cfg['global_optimality_claimed']
            and not cfg['biological_validation_claimed'], 'no promotion or optimality claim')


def load_inputs(cfg):
    source, previous = ROOT / cfg['numerical_source'], ROOT / cfg['previous_campaign']
    verify_archive(source)
    verify_archive(previous)
    receipt = read(ROOT / cfg['previous_verification'])
    require(receipt['verified'] and receipt['source_manifest_sha256'] == sha(previous / 'manifest.json'),
            'independent receipt of the previous campaign required')
    f = read(source / 'execution_design.json')
    require(f == read(previous / 'execution_design.json'), 'execution design differs from the sealed source')
    require(read(source / 'control_gate.json')['pass'], 'qualified reference certificate required')
    require(scipy.__version__ == cfg['scipy_version'] == f['requalification_plan']['scipy_version'],
            'qualified SciPy version required')
    obs = read(source / 'observations.json')
    require(obs == read(previous / 'observations.json'), 'observations differ from the sealed source')
    trace = [json.loads(line) for line in (previous / 'trace.jsonl').read_text().splitlines()]
    by_id = {r['attempt']: r for r in trace}
    selected = read(previous / 'search_result.json')['selected']
    require(selected['attempt'] == cfg['previous_selected_attempt'] and selected == by_id[selected['attempt']],
            'candidate35 must be the sealed selected row')
    centre = by_id[cfg['previous_working_centre_attempt']]
    require(centre['stage'] == 'working_center' and centre['log_factors'] == f['profile_center'],
            'working centre row changed')
    sensitivity = read(previous / cfg['previous_sensitivity'])
    require(sensitivity['anchor_attempt'] == selected['attempt'], 'stored Jacobian must be anchored at candidate35')
    check_invariants(cfg, f, selected)
    return source, previous, f, obs, selected, centre, sensitivity


def load_trace(out):
    path = out / 'trace.jsonl'
    if not path.exists():
        return []
    lines = path.read_text(encoding='utf-8').splitlines(keepends=True)
    rows = []
    for i, line in enumerate(lines):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            require(i == len(lines) - 1, 'corrupt trace before its last line')
            with (out / 'trace_truncated_tail.txt').open('a', encoding='utf-8') as tail:
                tail.write(line)
            lines = lines[:i]
            break
    text = ''.join(lines)
    if text and not text.endswith('\n'):
        text += '\n'
    path.write_text(text, encoding='utf-8')
    return rows


def orphan(out, folder):
    """Keep an interrupted integration folder aside; never delete evidence."""
    k = 1
    while folder.with_name(f'{folder.name}.orphan{k}').exists():
        k += 1
    target = folder.with_name(f'{folder.name}.orphan{k}')
    folder.rename(target)
    with (out / 'orphans.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'folder': folder.relative_to(out).as_posix(),
                                 'moved_to': target.relative_to(out).as_posix()}) + '\n')


def completed(folder, f, vector):
    """Reuse a folder whose integration finished before an interruption."""
    if not (folder / 'result.json').exists() or not (folder / 'parameters.json').exists():
        return None
    if read(folder / 'parameters.json') != exact_parameters(f, vector):
        return None
    return read(folder / 'result.json')


def score(result, reference, panel, f):
    row = dict(result)
    if row['valid']:
        try:
            row.update(scored(row['prediction_mM'], reference, panel, f))
        except ValueError as error:
            row.update(valid=False, error=str(error))
    return row


def make_evaluator(out, f, panel, references, pool, stream):
    def evaluate_many(jobs):
        launched = []
        for job in jobs:
            folder = out / 'search' / f'{job["attempt"]:03d}'
            done = completed(folder, f, job['log_factors'])
            if done is None:
                if folder.exists():
                    orphan(out, folder)
                done = pool.submit(evaluate, folder, f, job['log_factors'], panel['names'])
            launched.append((job, done))
        rows = []
        for job, item in launched:
            result = item if isinstance(item, dict) else item.result()
            text = json.dumps({**job, **score(result, references['strict'], panel, f)}, allow_nan=False)
            row = json.loads(text)  # fresh and resumed runs see identical rows
            stream.write(text + '\n')
            stream.flush()
            os.fsync(stream.fileno())
            print(f'{row["attempt"]:03d} {row["start"]}/{row["stage"]}: valid={row["valid"]} '
                  f'feasible={feasible(row)}', flush=True)
            rows.append(row)
        return rows
    return evaluate_many


def checkpointer(out):
    def save(search):
        data = {'events': search.events, 'distinct_evaluations': len(search.store.rows),
                'per_start': search.store.used,
                'incumbent_attempt': search.incumbent['attempt'] if search.incumbent else None}
        temporary = out / 'checkpoint.json.tmp'
        write(temporary, data)
        os.replace(temporary, out / 'checkpoint.json')
    return save


def reproduce(row, archived, tolerance):
    if not row['valid']:
        return {'attempt': row['attempt'], 'archived_attempt': archived['attempt'], 'pass': False,
                'bitwise_equal': False, 'max_abs_difference_mM': None, 'error': row.get('error')}
    a, b = np.array(row['prediction_mM']), np.array(archived['prediction_mM'])
    close = a.shape == b.shape and bool(np.all(np.abs(a - b) <= tolerance['atol_mM'] + tolerance['rtol'] * np.abs(b)))
    return {'attempt': row['attempt'], 'archived_attempt': archived['attempt'], 'pass': close and feasible(row),
            'bitwise_equal': bool(np.array_equal(a, b)), 'max_abs_difference_mM': float(np.max(np.abs(a - b))),
            'reserved_guards_pass': bool(row['reserved_guards_pass'])}


def validate(out, f, panel, references, finalists, pool, v):
    require(len(finalists) * len(v['profiles']) <= v['max_integrations'], 'validation budget exceeded')
    jobs, labels = {}, []
    for rank, row in enumerate(finalists, 1):
        label = f'{rank:02d}_attempt{row["attempt"]:03d}'
        labels.append(label)
        for profile in v['profiles']:
            folder = out / 'validation' / label / profile
            done = completed(folder, f, row['log_factors'])
            if done is None:
                if folder.exists():
                    orphan(out, folder)
                done = pool.submit(evaluate, folder, f, row['log_factors'], panel['names'], profile,
                                   v['backend'], v['flux_audit'])
            jobs[label, profile] = done
    results = []
    for rank, (label, row) in enumerate(zip(labels, finalists), 1):
        validated = {}
        for profile in v['profiles']:
            item = jobs[label, profile]
            validated[profile] = score(item if isinstance(item, dict) else item.result(), references[profile], panel, f)
            print(f'Validation {label} {profile}: valid={validated[profile]["valid"]}', flush=True)
        pair = compare_files(out / 'validation' / label / 'strict' / 'flux_evidence.npz',
                             out / 'validation' / label / 'ultrastrict' / 'flux_evidence.npz', f)
        results.append({'rank': rank, 'label': label, 'attempt': row['attempt'], 'start': row['start'],
                        'log_factors': row['log_factors'], 'search_objective': row['absolute']['objective'],
                        'validation': validated, 'paired': pair, 'admissible': admissible(validated, pair['pass'])})
    return results


def write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)


def export(out, f, panel, store, reserve, side_names, guard_names, replays, centre_row, finalists, starts, seeds):
    groups = f['design']['groups']
    trace = []
    for row in store.rows:
        if row['valid']:
            s, g = row_values(row, side_names, guard_names)
            c = row['absolute']['concentrations_mM']
            trace.append([row['attempt'], row['start'], row['stage'], True, row['absolute']['objective'], c['ATP'],
                          c['ADP'], row['reserved_guards_pass'], float(np.max(g + 0.5 * reserve)), ''])
        else:
            trace.append([row['attempt'], row['start'], row['stage'], False, '', '', '', False, '', row.get('error', '')])
    write_csv(out / 'exports/objective_trace.csv', ['attempt', 'start', 'stage', 'valid', 'objective', 'ATP_J15_mM',
              'ADP_J15_mM', 'reserved_guards_pass', 'max_guard_minus_half_reserve', 'error'], trace)
    write_csv(out / 'exports/constraint_trace.csv', ['attempt', *guard_names],
              [[r['attempt'], *row_values(r, side_names, guard_names)[1].tolist()] for r in store.rows if r['valid']])
    rows = []
    labelled = [('candidate35_replay', 'strict', replays['candidate35']), ('working_centre_replay', 'strict', replays['working_centre'])]
    labelled += [(item['label'], p, item['validation'][p]) for item in finalists for p in item['validation']]
    for label, profile, row in labelled:
        if not row['valid']:
            continue
        for i, pool in enumerate(panel['names']):
            for j, day in enumerate(panel['days']):
                rows.append([label, profile, pool, day, row['prediction_mM'][i][j]])
    write_csv(out / 'exports/concentrations_by_day.csv', ['label', 'profile', 'pool', 'day', 'mM'], rows)
    rows = []
    centre = exact_parameters(f, centre_row['log_factors'])
    c35 = exact_parameters(f, replays['candidate35']['log_factors'])
    for item in finalists:
        p = exact_parameters(f, item['log_factors'])
        for k, (group, members) in enumerate(groups.items()):
            for member in members:
                rows.append([item['label'], group, member, centre[member], c35[member], p[member],
                             item['log_factors'][k], p[member] / centre[member] - 1])
    write_csv(out / 'exports/vmax_by_finalist.csv', ['label', 'group', 'parameter', 'working_centre', 'candidate35',
              'finalist', 'log_group_factor', 'relative_change_vs_centre'], rows)
    write(out / 'exports/seed_status.json', {'seeds': seeds,
          'starts': [{k: v for k, v in s.items() if k != 'best_row'} for s in starts]})


def finish(out, source, previous, summary):
    write(out / 'summary.json', summary)
    verify_archive(source)
    verify_archive(previous)
    write(out / 'manifest.json', {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob('*')) if p.is_file()})


def execute(out, resume):
    cfg = read(CONFIG)
    source, previous, f, obs, selected, centre, sensitivity = load_inputs(cfg)
    panel, references = historical_metrics(f, obs)
    groups = list(f['design']['groups'])
    lo, hi = np.log([f['design']['factor_bounds'][k] for k in groups]).T
    reserve = reserve_for(references['strict'], panel, f)
    side_names, guard_names = list(selected['absolute']['sides']), list(selected['feasibility_guards'])
    base = evaluate_screen(references['strict']['prediction_mM'], references['strict'], panel, f['design'],
                           f['temporal'], f['absolute_targets'])
    require(list(base['feasibility_guards']) == guard_names and len(reserve) == len(guard_names),
            'reserve and guard order differ')
    require(sensitivity['guard_names'] == guard_names and sensitivity['objective_sides'] == side_names,
            'stored Jacobian names differ')
    s35, g35 = row_values(selected, side_names, guard_names)
    sd = cfg['seeds']
    seeds = joint_seeds(selected['log_factors'], lo, hi, objective_jacobian=sensitivity['objective_jacobian'],
                        side_names=side_names, active_side=side_names[int(np.argmax(s35))],
                        guard_jacobian=sensitivity['guard_jacobian'], guard_slack=-reserve - g35,
                        radius=sd['radius_log'], guard_count=sd['guard_relief_count'],
                        random_seed=sd['random_seed'], tolerance=sd['at_bound_tolerance_log'])
    require(len(seeds) <= sd['maximum_additional'], 'at most three additional seeds')
    starts = [{'name': 'candidate35', 'vector': selected['log_factors'], 'stage': 'replay',
               'origin': f'{cfg["previous_campaign"]} attempt {selected["attempt"]}'},
              {'name': 'working_centre', 'vector': centre['log_factors'], 'stage': 'replay',
               'origin': f'{cfg["previous_campaign"]} attempt {centre["attempt"]}'}]
    starts += [{'name': s['name'], 'vector': s['vector'], 'stage': 'seed', 'status': s['status'],
                'origin': f'candidate35 + {sd["radius_log"]} x bounded joint direction'} for s in seeds]
    code = code_hashes()
    if resume:
        require(out.exists() and (out / 'protocol.json').exists() and not (out / 'manifest.json').exists(),
                'resumable unsealed campaign required')
        require(read(out / 'protocol.json')['code_sha256'] == code, 'code changed since the campaign started')
        require(read(out / 'execution_design.json') == f and read(out / 'config.json') == cfg
                and read(out / 'seeds.json') == json.loads(json.dumps(seeds)), 'campaign inputs changed')
        rows = load_trace(out)
        expected = read(out / 'checkpoint.json')['events'] if (out / 'checkpoint.json').exists() else None
    else:
        require(not out.exists(), 'Fresh successor directory required')
        out.mkdir(parents=True)
        write(out / 'execution_design.json', f)
        write(out / 'observations.json', obs)
        write(out / 'historical_reference_metrics.json', references)
        write(out / 'config.json', cfg)
        write(out / 'seeds.json', seeds)
        write(out / 'protocol.json', {'source': cfg['numerical_source'], 'previous_campaign': cfg['previous_campaign'],
              'source_manifest_sha256': sha(source / 'manifest.json'),
              'previous_manifest_sha256': sha(previous / 'manifest.json'),
              'optimizer': cfg['search']['optimizer'], 'objective': cfg['invariants']['objective'],
              'distinct_ode_evaluation_limit': cfg['search']['distinct_ode_evaluation_limit'],
              'start_evaluation_limits': cfg['search']['start_evaluation_limits'],
              'validation_integration_limit': cfg['validation']['max_integrations'], 'workers': cfg['workers'],
              'solver': f['requalification_plan'], 'guards_rebased': False, 'production_promotion_allowed': False,
              'code_sha256': code})
        rows, expected = [], None
    s = cfg['search']
    with ProcessPoolExecutor(max_workers=cfg['workers']) as pool, \
            (out / 'trace.jsonl').open('a' if resume else 'x', encoding='utf-8') as stream:
        store = EvaluationStore(make_evaluator(out, f, panel, references, pool, stream),
                                limit=s['distinct_ode_evaluation_limit'], start_limits=s['start_evaluation_limits'],
                                rows=rows)
        replays = {'candidate35': store.request([selected['log_factors']], 'replay', 'candidate35')[0],
                   'working_centre': store.request([centre['log_factors']], 'replay', 'working_centre')[0]}
        reproduction = {'candidate35': reproduce(replays['candidate35'], selected, cfg['replay_reproduction']),
                        'working_centre': reproduce(replays['working_centre'], centre, cfg['replay_reproduction'])}
        write(out / 'replay_reproduction.json', reproduction)
        flags = {'optimization_executed': False, 'Km_changed': False, 'initial_changed': False,
                 'bounds_changed': False, 'guards_rebased': False, 'production_promoted': False,
                 'global_optimality': False, 'biological_validation': False}
        if not all(r['pass'] for r in reproduction.values()):
            print('STOP: numerical qualification failure (replay reproduction)', flush=True)
            finish(out, source, previous, {'stop': 'numerical_qualification_failure', 'replay_reproduction': reproduction,
                                           'search_distinct_evaluations': len(store.rows), **flags})
            return
        search = MultistartSearch(store, lower=lo, upper=hi, side_names=side_names, guard_names=guard_names,
                                  reserve=reserve, search=s, expected_events=expected, on_event=checkpointer(out))
        result = search.run(starts)
        write(out / 'search_result.json', {**{k: v for k, v in result.items() if k not in ('jacobians',)},
                                           'replay_reproduction': reproduction})
        write(out / 'jacobians.json', result['jacobians'])
        finalists = select_finalists(result['starts'], replays['candidate35'], gain=s['minimum_step_objective_gain'],
                                     maximum=cfg['validation']['max_finalists'])
        validated = validate(out, f, panel, references, finalists, pool, cfg['validation'])
    passing = sorted((v for v in validated if v['admissible']),
                     key=lambda v: (v['validation']['strict']['absolute']['objective'], v['attempt']))
    chosen = passing[0] if passing else None
    reference = replays['candidate35']['absolute']['concentrations_mM']
    summary = {'stop': result['global_stop'] or 'all_starts_finished',
               'search_distinct_evaluations': len(store.rows), 'new_integrations_this_process': store.new_evaluations,
               'per_start': store.used, 'starts': [{k: v for k, v in st.items() if k != 'best_row'} for st in result['starts']],
               'replay_reproduction': reproduction,
               'candidate35_replay': {'attempt': replays['candidate35']['attempt'],
                                      'objective': replays['candidate35']['absolute']['objective'],
                                      'J15_mM': reference},
               'incumbent_attempt': result['incumbent']['attempt'],
               'incumbent_objective': result['incumbent']['absolute']['objective'],
               'finalists': [{k: v for k, v in item.items() if k != 'validation'} |
                             {'validation': {p: {k: r.get(k) for k in ('valid', 'error', 'absolute', 'reserved_guards_pass',
                                                                       'day_ratios', 'gain_by_day')}
                                             for p, r in item['validation'].items()}} for item in validated],
               'validation_integrations': 2 * len(validated),
               'selected': None if chosen is None else {
                   'label': chosen['label'], 'attempt': chosen['attempt'], 'start': chosen['start'],
                   'log_factors': chosen['log_factors'],
                   'strict_objective': chosen['validation']['strict']['absolute']['objective'],
                   'J15_mM': chosen['validation']['strict']['absolute']['concentrations_mM'],
                   'relative_J15_change_vs_candidate35': {
                       k: chosen['validation']['strict']['absolute']['concentrations_mM'][k] / reference[k] - 1
                       for k in reference},
                   'day_ratios_strict': chosen['validation']['strict']['day_ratios']},
               'admitted_under_inherited_guards': chosen is not None,
               'absolute_targets_reached': bool(chosen and all(chosen['validation'][p]['absolute']['target_pass']
                                                               for p in chosen['validation'])),
               **flags, 'optimization_executed': True}
    export(out, f, panel, store, reserve, side_names, guard_names, replays, centre, validated, result['starts'], seeds)
    finish(out, source, previous, summary)
    print(f'FINISHED: evaluations={len(store.rows)}; finalists={len(validated)}; '
          f'selected={chosen["label"] if chosen else None}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT / 'output/multistart_vmax_2026_11_12')
    parser.add_argument('--resume', action='store_true')
    arguments = parser.parse_args()
    with threadpool_limits(1):
        execute(arguments.out, arguments.resume)
