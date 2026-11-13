"""Independent check of a multistart Vmax campaign from recorded files. No ODE.

  python scripts/verify_multistart_vmax.py output/multistart_vmax_2026_11_12 \
      --receipt output/multistart_vmax_verification_2026_11_12
"""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from run_pgk_ndpk_profile import read, write, sha, verify_archive, scored, reserve_for
from run_vmax_requalification import historical_metrics, compare_files
from fla_vmax_requalification import exact_parameters, within_original_box
from fla_integration_diagnostics import inspect_support
from fla_agentic_vmax_replay import within
from fla_multistart_vmax import admissible, feasible, joint_seeds, row_values, select_finalists, vector_key

CONFIG = ROOT / 'config/fla_multistart_vmax_2026_11_12.json'
OPTIMIZER_SOURCES = {'start', 'constraint', 'jacobian', 'iterate'}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def plain(value):
    return json.loads(json.dumps(value, allow_nan=False))


def rescore(result, reference, panel, f):
    row = dict(result)
    if row['valid']:
        try:
            row.update(scored(row['prediction_mM'], reference, panel, f))
        except ValueError as error:
            row.update(valid=False, error=str(error))
    return plain(row)


class Supports:
    def __init__(self, f, panel):
        self.f, self.panel, self.count = f, panel, 0

    def check(self, folder, vector):
        """Recorded evidence of one integration; returns result.json (prediction re-extracted)."""
        f = self.f
        require(within_original_box(f, vector), 'vector outside the original box')
        p = read(folder / 'parameters.json')
        require(p == exact_parameters(f, vector), 'parameters differ from the Vmax-only injection')
        require(all(k.startswith('vmax_') for k in p if p[k] != f['parameters'][k]), 'non-Vmax parameter changed')
        result = read(folder / 'result.json')
        if not (folder / 'trajectory_evidence.npz').exists():
            require(not result['valid'], 'valid result without recorded trajectory evidence')
            return result
        with np.load(folder / 'trajectory_evidence.npz') as z:
            require(np.array_equal(z['initial'], f['initial']), 'initial state changed')
            physical = True
            for prefix in ('accepted', '', 'q4', 'q8'):
                tk, xk = (prefix + '_time', prefix + '_states') if prefix else ('time', 'states')
                if tk not in z:
                    physical = False
                    continue
                require(np.min(z[tk]) >= 1 and np.max(z[tk]) <= 15, 'support outside J1-J15')
                report = inspect_support(z[tk], z[xk][:-1], z['pool_names'].tolist(), f['numeric']['negative_tolerance_mM'])
                physical &= report['pass']
                require(np.array_equal(z[xk][-1], np.full(len(z[tk]), 7.2)), 'clamped pH changed')
                self.count += len(z[tk])
            if not result['valid']:
                return result
            require(physical, 'valid result on failing physical supports')
            ids = np.searchsorted(z['time'], self.panel['days'])
            require(np.array_equal(z['time'][ids], self.panel['days']), 'dated support missing')
            prediction = z['states'][np.ix_([z['pool_names'].tolist().index(n) for n in self.panel['names']], ids)]
            require(np.array_equal(prediction, result['prediction_mM']), 'recorded prediction differs from evidence')
        return result


def check_events(events, by_id, gain):
    incumbent, start_best, updates = None, {}, 0
    for event in events:
        if event['event'] != 'objective':
            continue
        require(event['source'] in OPTIMIZER_SOURCES, 'incumbent candidate from a non-optimizer request')
        row = by_id[event['attempt']]
        ok = feasible(row)
        require(event['feasible'] == ok and event['valid'] == bool(row['valid']), 'event feasibility differs')
        objective = row['absolute']['objective'] if row['valid'] else None
        require(event['objective'] == objective, 'event objective differs')
        better = ok and (incumbent is None or objective < incumbent['absolute']['objective'] - gain)
        require(event['incumbent_updated'] == better, 'incumbent update rule violated')
        if better:
            incumbent, updates = row, updates + 1
        best = start_best.get(event['start'])
        better_start = ok and (best is None or objective < best['absolute']['objective'] - gain)
        require(event['start_best_updated'] == better_start, 'start-best update rule violated')
        if better_start:
            start_best[event['start']] = row
        require(event['incumbent_attempt'] == (incumbent['attempt'] if incumbent else None), 'incumbent pointer differs')
    return incumbent, start_best, updates


def check_jacobians(jacobians, by_trace_key, by_id, lower, upper, cfg, side_names, guard_names, reserve):
    s = cfg['search']
    checked_starts = Counter()
    for record in jacobians:
        anchor = by_id[record['anchor_attempt']]
        x = np.array(anchor['log_factors'])
        s0, g0 = row_values(anchor, side_names, guard_names)
        js, jg = np.array(record['side_jacobian']), np.array(record['guard_jacobian'])
        for key, entry in record['columns'].items():
            i = int(key)
            row = by_id[entry['attempt']]
            v = np.array(row['log_factors'])
            dx = v[i] - x[i]
            require(dx == entry['step_log'] and abs(abs(dx) - s['difference_step_log']) < 1e-12, 'difference step differs')
            require(np.array_equal(np.delete(v, i), np.delete(x, i)), 'probe moved more than one coordinate')
            if dx < 0:
                forward = x.copy()
                forward[i] = x[i] + s['difference_step_log']
                forward_row = by_trace_key.get(vector_key(forward))
                require(x[i] + s['difference_step_log'] > upper[i] or (forward_row is not None and not forward_row['valid']),
                        'backward difference without upper bound or failed forward probe')
            sp, gp = row_values(row, side_names, guard_names)
            require(np.array_equal(js[:, i], (sp - s0) / dx) and np.array_equal(jg[:, i], (gp - g0) / dx),
                    'Jacobian column not reproduced bitwise')
        for i in set(range(len(x))) - {int(k) for k in record['columns']}:
            require(not js[:, i].any() and not jg[:, i].any(), 'unavailable column carries values')
        if 'check' in record:
            checked_starts[record['start']] += 1
            report = record['check']
            active = side_names.index(report['active_side'])
            margin = reserve * s['optimizer_reserve_multiplier']
            binding = [int(k) for k in np.argsort(-margin - g0, kind='stable')[:s['check_binding_guards']]]
            require(report['binding_guards'] == [guard_names[k] for k in binding], 'binding guards differ')
            lead = sorted(record['free'], key=lambda i: (-abs(js[active, i]), i))[:s['check_leading_groups']]
            require(sorted(int(k) for k in report['groups']) == sorted(lead), 'leading groups differ')
            for key, entry in report['groups'].items():
                i = int(key)
                row = by_id[entry['attempt']]
                dx = row['log_factors'][i] - x[i]
                require(dx == entry['step_log'] and abs(abs(dx) - s['check_step_log']) < 1e-12
                        and np.sign(dx) == np.sign(record['columns'][key]['step_log']), 'check step differs')
                if not row['valid']:
                    require(entry['passed'] is False, 'invalid check probe accepted')
                    continue
                sp, gp = row_values(row, side_names, guard_names)
                d3 = np.r_[(sp[active] - s0[active]) / dx, (gp[binding] - g0[binding]) / dx]
                d6 = np.r_[js[active, i], jg[binding, i]]
                passed = bool(np.all(np.abs(d6 - d3) <= s['check_rtol'] * np.maximum(np.abs(d6), np.abs(d3))
                                     + s['check_atol_per_log']))
                require(np.array_equal(d3, entry['d003']) and np.array_equal(d6, entry['d006']) and passed == entry['passed'],
                        'derivative check not reproduced')
    require(all(n == 1 for n in checked_starts.values()), 'more than one derivative check in a start')
    return len(jacobians), sum(checked_starts.values())


def check_validation(out, f, panel, references, item, supports, cfg):
    validated, balances = {}, 0
    for profile in cfg['validation']['profiles']:
        folder = out / 'validation' / item['label'] / profile
        result = supports.check(folder, item['log_factors'])
        validated[profile] = rescore(result, references[profile], panel, f)
        if not validated[profile]['valid']:
            continue
        with np.load(folder / 'flux_evidence.npz') as z:
            ids = np.searchsorted(z['time'], z['boundaries'])
            delta = np.diff(z['states'][:113, ids], axis=1)
            require(within(delta, z['matrix'] @ z['executed8'], f['numeric'], 'quadrature').all(), 'daily balance fails')
            balances += delta.size
            for kind in ('raw', 'executed'):
                integrals = {}
                for order in (4, 8):
                    rates, weights, bins = z[f'q{order}_{kind}_rates'], z[f'q{order}_weights'], z[f'q{order}_intervals']
                    integrals[order] = np.array([np.sum(rates[:, bins == k] * weights[bins == k], axis=1)
                                                 for k in range(len(z['boundaries']) - 1)]).T
                    require(np.allclose(integrals[order], z[f'{kind}{order}'], atol=1e-12, rtol=1e-12), 'quadrature differs')
                require(within(integrals[4], integrals[8], f['numeric'], 'quadrature').all(), 'order 4/8 disagree')
    pair = compare_files(out / 'validation' / item['label'] / 'strict' / 'flux_evidence.npz',
                         out / 'validation' / item['label'] / 'ultrastrict' / 'flux_evidence.npz', f)
    return validated, pair, balances


def verify(out, receipt):
    require(not receipt.exists(), 'fresh receipt required')
    verify_archive(out)
    cfg = read(out / 'config.json')
    require(cfg == read(CONFIG), 'config differs from the registered file')
    protocol = read(out / 'protocol.json')
    for path, digest in protocol['code_sha256'].items():
        require(sha(ROOT / path) == digest, f'{path} changed after the campaign')
    source, previous = ROOT / cfg['numerical_source'], ROOT / cfg['previous_campaign']
    verify_archive(source)
    verify_archive(previous)
    require(sha(source / 'manifest.json') == protocol['source_manifest_sha256'], 'source archive changed')
    require(sha(previous / 'manifest.json') == protocol['previous_manifest_sha256'], 'previous campaign changed')
    f, obs = read(out / 'execution_design.json'), read(out / 'observations.json')
    require(f == read(source / 'execution_design.json') and obs == read(source / 'observations.json'), 'inputs differ')
    panel, references = historical_metrics(f, obs)
    summary = read(out / 'summary.json')
    for flag in ('Km_changed', 'initial_changed', 'bounds_changed', 'guards_rebased', 'production_promoted',
                 'global_optimality', 'biological_validation'):
        require(summary[flag] is False, f'{flag} must be false')

    s = cfg['search']
    trace = [json.loads(line) for line in (out / 'trace.jsonl').read_text(encoding='utf-8').splitlines()]
    require([r['attempt'] for r in trace] == list(range(1, len(trace) + 1)), 'attempt numbering')
    require(len(trace) <= s['distinct_ode_evaluation_limit'], 'global budget exceeded')
    per_start = Counter(r['start'] for r in trace)
    require(all(per_start[k] <= s['start_evaluation_limits'][k] for k in per_start), 'start budget exceeded')
    keys = [vector_key(r['log_factors']) for r in trace]
    require(len(set(keys)) == len(keys), 'a vector was integrated twice')
    by_id, by_key = {r['attempt']: r for r in trace}, dict(zip(keys, trace))
    supports = Supports(f, panel)
    for row in trace:
        result = supports.check(out / 'search' / f'{row["attempt"]:03d}', row['log_factors'])
        expected = {k: row[k] for k in ('attempt', 'log_factors', 'stage', 'start')}
        require({**expected, **rescore(result, references['strict'], panel, f)} == row, 'trace row not reproduced')

    previous_trace = {r['attempt']: r for r in
                      (json.loads(line) for line in (previous / 'trace.jsonl').read_text().splitlines())}
    selected = previous_trace[cfg['previous_selected_attempt']]
    centre = previous_trace[cfg['previous_working_centre_attempt']]
    reproduction = read(out / 'replay_reproduction.json')
    tolerance = cfg['replay_reproduction']
    for name, archived, attempt in (('candidate35', selected, 1), ('working_centre', centre, 2)):
        row = by_id[attempt]
        require(row['start'] == name and row['stage'] == 'replay' and row['log_factors'] == archived['log_factors'],
                'replay rows must be attempts 1 and 2')
        a, b = np.array(row['prediction_mM']), np.array(archived['prediction_mM'])
        ok = bool(np.all(np.abs(a - b) <= tolerance['atol_mM'] + tolerance['rtol'] * np.abs(b))) and feasible(row)
        require(reproduction[name]['pass'] == ok and reproduction[name]['bitwise_equal'] == bool(np.array_equal(a, b)),
                'replay reproduction not reproduced')
    if summary.get('stop') == 'numerical_qualification_failure':
        require(not all(r['pass'] for r in reproduction.values()) and not (out / 'search_result.json').exists(),
                'qualification stop inconsistent')
        receipt.mkdir(parents=True)
        result = {'verified': True, 'stop': 'numerical_qualification_failure', 'search_evaluations': len(trace),
                  'production_promoted': False, 'source_manifest_sha256': sha(out / 'manifest.json')}
        write(receipt / 'verification.json', result)
        print(result)
        return
    require(all(r['pass'] for r in reproduction.values()), 'search ran without replay qualification')

    groups = list(f['design']['groups'])
    lower, upper = np.log([f['design']['factor_bounds'][k] for k in groups]).T
    reserve = reserve_for(references['strict'], panel, f)
    side_names, guard_names = list(selected['absolute']['sides']), list(selected['feasibility_guards'])
    sensitivity = read(previous / cfg['previous_sensitivity'])
    s35, g35 = row_values(selected, side_names, guard_names)
    sd = cfg['seeds']
    seeds = joint_seeds(selected['log_factors'], lower, upper, objective_jacobian=sensitivity['objective_jacobian'],
                        side_names=side_names, active_side=side_names[int(np.argmax(s35))],
                        guard_jacobian=sensitivity['guard_jacobian'], guard_slack=-reserve - g35,
                        radius=sd['radius_log'], guard_count=sd['guard_relief_count'],
                        random_seed=sd['random_seed'], tolerance=sd['at_bound_tolerance_log'])
    require(json.loads(json.dumps(seeds)) == read(out / 'seeds.json'), 'seeds not reproduced')
    for seed in seeds:
        if seed['vector'] is not None:
            require(within_original_box(f, seed['vector']), 'seed outside the box')
            exact_parameters(f, seed['vector'])

    search_result = read(out / 'search_result.json')
    events = search_result['events']
    require(events == read(out / 'checkpoint.json')['events'], 'checkpoint and final event log differ')
    incumbent, start_best, updates = check_events(events, by_id, s['minimum_step_objective_gain'])
    require(incumbent is not None and incumbent['attempt'] == search_result['incumbent']['attempt']
            == summary['incumbent_attempt'], 'final incumbent differs')
    for start in search_result['starts']:
        best = start_best.get(start['name'])
        require((best['attempt'] if best else None) == start['best_attempt'], 'start best differs')
        if start['start_attempt'] is not None:
            require(by_id[start['start_attempt']]['start'] in s['start_order'], 'unknown start row')
    require(search_result['distinct_evaluations'] == len(trace) == summary['search_distinct_evaluations'],
            'evaluation count differs')
    jacobians = read(out / 'jacobians.json')
    n_jacobians, n_checks = check_jacobians(jacobians, by_key, by_id, lower, upper, cfg, side_names, guard_names, reserve)

    finalists = select_finalists(search_result['starts'], by_id[1], gain=s['minimum_step_objective_gain'],
                                 maximum=cfg['validation']['max_finalists'])
    recorded = summary['finalists']
    require([r['attempt'] for r in finalists] == [r['attempt'] for r in recorded], 'finalists differ')
    require(2 * len(recorded) == summary['validation_integrations'] <= cfg['validation']['max_integrations'],
            'validation budget exceeded')
    balances, passing = 0, []
    for item in recorded:
        validated, pair, count = check_validation(out, f, panel, references, item, supports, cfg)
        balances += count
        for profile, row in validated.items():
            for key in ('valid', 'absolute', 'reserved_guards_pass', 'day_ratios', 'gain_by_day'):
                require(row.get(key) == item['validation'][profile][key], f'validation {key} differs')
        require(plain(pair) == item['paired'], 'paired convergence differs')
        ok = admissible(validated, pair['pass'])
        require(ok == item['admissible'], 'admissibility differs')
        if ok:
            passing.append((validated['strict']['absolute']['objective'], item['attempt'], item['label']))
    chosen = min(passing)[2] if passing else None
    require(chosen == (summary['selected']['label'] if summary['selected'] else None), 'selected finalist differs')
    require(summary['admitted_under_inherited_guards'] == (chosen is not None), 'admission flag differs')

    with (out / 'exports/objective_trace.csv').open(encoding='utf-8', newline='') as stream:
        exported = list(csv.DictReader(stream))
    require([int(r['attempt']) for r in exported] == [r['attempt'] for r in trace], 'objective export incomplete')
    for r, row in zip(exported, trace):
        if row['valid']:
            require(float(r['objective']) == row['absolute']['objective'], 'objective export differs')

    receipt.mkdir(parents=True)
    result = {'verified': True, 'search_evaluations': len(trace), 'per_start': dict(per_start),
              'support_points_checked': supports.count, 'daily_balances': balances, 'events': len(events),
              'incumbent_updates': updates, 'incumbent_attempt': incumbent['attempt'],
              'jacobians': n_jacobians, 'derivative_checks': n_checks, 'finalists': len(recorded),
              'selected': chosen, 'admitted_under_inherited_guards': chosen is not None,
              'production_promoted': False, 'source_manifest_sha256': sha(out / 'manifest.json')}
    write(receipt / 'verification.json', result)
    print(result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('out', type=Path)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    verify(args.out, args.receipt)
