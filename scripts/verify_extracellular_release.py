"""Independent check of an extracellular release campaign (extracellular_first/2). No ODE.

Every claim is re-derived from recorded files, never from the runner's booleans:
physical supports of every attempt (accepted, dense, q4, q8), every Jacobian
column and half-step check, incumbent/start-best rules, seed admission
(84 guards, global cap, EGLC/ELAC focus caps, separation), source/context of
every referenced row, NEW finalists' raw/executed quadrature integrals and daily
balances, and the exported Vmax values of the single selected vector.

  python scripts/verify_extracellular_release.py output/extracellular_release_2026_11_12 \
      --receipt output/extracellular_release_verification_2026_11_12
"""
import argparse
from collections import Counter
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
from rbc_gem_audit import EXTERNAL_POOLS
from fla_extracellular_release import (activation_permitted, channel_mse, extracellular_channels, feasible,
                                       focus_caps, normalized_distance, release_admissible, release_score,
                                       select_release, unit_status, vector_key)
from run_extracellular_release import (CONFIG, canonical_sha, drift_check, finish_candidate, load_sources,
                                       qualified_references)

SUPPORTS = ('accepted', '', 'q4', 'q8')
FOCUS_KEYS = ('normalized_rmse', 'abs_J15_residual', 'abs_slope_error')


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


# ---------------------------------------------------------------- supports
def trajectory_verdict(result, evidence, *, initial, negative_tolerance, days, names, horizon=(1, 15)):
    """Inspect accepted/dense/q4/q8 supports of ONE attempt; never trust dated predictions alone.

    ``evidence``: mapping of the trajectory_evidence.npz arrays, or None if absent.
    Returns {'class', 'supports', 'points'}; raises AssertionError on any contradiction.
    """
    if evidence is None:
        require(not result['valid'], 'valid result without recorded trajectory evidence')
        return {'class': 'rejected_no_evidence', 'supports': {}, 'points': 0}
    require(np.array_equal(evidence['initial'], initial), 'initial state changed')
    pools = [str(p) for p in evidence['pool_names']]
    supports, points, physical = {}, 0, True
    for prefix in SUPPORTS:
        tk, xk = (prefix + '_time', prefix + '_states') if prefix else ('time', 'states')
        label = prefix or 'dense'
        if tk not in evidence or xk not in evidence:
            supports[label] = 'missing'
            physical = False
            continue
        t, x = np.asarray(evidence[tk], float), np.asarray(evidence[xk], float)
        require(x.ndim == 2 and x.shape == (len(pools) + 1, len(t)) and len(t) > 0, f'{label} support shape')
        require(np.isfinite(t).all() and not (np.diff(t) < 0).any(), f'{label} support times unordered')
        require(t.min() >= horizon[0] and t.max() <= horizon[1], f'{label} support outside the horizon')
        require(np.array_equal(x[-1], np.full(len(t), 7.2)), f'{label} clamped pH changed')
        try:
            report = inspect_support(t, x[:-1], pools, negative_tolerance)
        except ValueError as error:
            raise AssertionError(f'{label} support malformed: {error}') from error
        supports[label] = 'pass' if report['pass'] else 'fail'
        physical &= report['pass']
        points += len(t)
    if not result['valid']:
        return {'class': 'rejected_physical' if not physical else 'rejected_other', 'supports': supports,
                'points': points}
    require(physical, 'valid result on a failing or missing physical support')
    t = np.asarray(evidence['time'], float)
    ids = np.searchsorted(t, days)
    require(np.array_equal(t[ids], days), 'dated support missing')
    prediction = np.asarray(evidence['states'])[np.ix_([pools.index(n) for n in names], ids)]
    require(np.array_equal(prediction, result['prediction_mM']), 'recorded prediction differs from evidence')
    return {'class': 'accepted_valid', 'supports': supports, 'points': points}


def check_folder(folder, f, panel, vector):
    require(within_original_box(f, vector), 'vector outside the original box')
    p = read(folder / 'parameters.json')
    require(p == exact_parameters(f, vector), 'parameters differ from the Vmax-only injection')
    require(all(k.startswith('vmax_') for k in p if p[k] != f['parameters'][k]), 'non-Vmax parameter changed')
    result = read(folder / 'result.json')
    path = folder / 'trajectory_evidence.npz'
    kwargs = dict(initial=f['initial'], negative_tolerance=f['numeric']['negative_tolerance_mM'],
                  days=panel['days'], names=panel['names'])
    if not path.exists():
        return result, trajectory_verdict(result, None, **kwargs)
    with np.load(path) as z:
        return result, trajectory_verdict(result, {k: z[k] for k in z.files}, **kwargs)


# -------------------------------------------------------- flux (finalists)
def flux_verdict(evidence, numeric, pools=113):
    """Rebuild raw/executed order-4/8 integrals and daily balances from rates and weights."""
    z = evidence
    ids = np.searchsorted(z['time'], z['boundaries'])  # same indexing as verify_corrected_vmax
    delta = np.diff(np.asarray(z['states'])[:pools, ids], axis=1)
    require(within(delta, np.asarray(z['matrix']) @ np.asarray(z['executed8']), numeric, 'quadrature').all(),
            'daily species balance fails')
    for kind in ('raw', 'executed'):
        integrals = {}
        for order in (4, 8):
            rates, weights, bins = (np.asarray(z[f'q{order}_{kind}_rates']), np.asarray(z[f'q{order}_weights']),
                                    np.asarray(z[f'q{order}_intervals']))
            integrals[order] = np.array([np.sum(rates[:, bins == k] * weights[bins == k], axis=1)
                                         for k in range(len(z['boundaries']) - 1)]).T
            require(np.allclose(integrals[order], z[f'{kind}{order}'], atol=1e-12, rtol=1e-12),
                    f'{kind} order-{order} integral does not match its rates and weights')
        require(within(integrals[4], integrals[8], numeric, 'quadrature').all(), f'{kind} order 4/8 disagree')
    return int(delta.size)


# ------------------------------------------------------ release components
class Components:
    """Independent re-implementation of the search vector [U, guards, global caps, focus caps]."""

    def __init__(self, panel, channels, anchor_mse, units, guard_names, margin, scale, worst_cap, caps):
        self.panel, self.channels, self.anchor_mse, self.units = panel, channels, anchor_mse, units
        self.guard_names, self.margin, self.scale = guard_names, margin, scale
        self.worst_cap, self.caps = worst_cap, caps or {}

    def score(self, row):
        return release_score(row['prediction_mM'], self.panel, self.channels, self.anchor_mse, units=self.units)

    def admissible(self, row):
        return bool(row['valid'] and release_admissible(row, self.score(row), self.worst_cap, self.caps))

    def vector(self, row):
        s = self.score(row)
        g = np.array([row['feasibility_guards'][k] for k in self.guard_names], float)
        mse = np.array([s['per_channel'][c]['normalized_mse'] for c in s['scored_channels']])
        cap = self.worst_cap ** 2
        focus = [(self.caps[c]['cap'][k] ** 2 - s['focus'][c][k] ** 2) / self.caps[c]['cap'][k] ** 2
                 for c in sorted(self.caps) for k in FOCUS_KEYS]
        return np.r_[s['primary'], -(g + self.margin) / self.scale, (cap - mse) / cap, focus]


def jacobian_verdict(record, resolve, vector, spec, upper):
    """Rebuild every column at its actual signed step; check companions, unavailable and half steps."""
    anchor = resolve(record['anchor_attempt'])
    x = np.array(anchor['log_factors'], float)
    require(list(x) == record['anchor_vector'], 'Jacobian anchor vector differs from its row')
    v0 = vector(anchor)
    jac = np.array(record['jacobian'], float)
    require(jac.shape == (len(v0), len(x)), 'Jacobian shape differs')
    step = float(spec['difference_step_log'])
    for key, entry in record['columns'].items():
        i = int(key)
        probe = resolve(entry['attempt'])
        v = np.array(probe['log_factors'], float)
        dx = v[i] - x[i]
        require(dx == entry['step_log'] and abs(abs(dx) - step) < 1e-12, 'difference step falsified')
        require(np.array_equal(np.delete(v, i), np.delete(x, i)), 'probe moved a companion coordinate')
        if dx < 0 and x[i] + step <= upper[i]:
            forward = x.copy()
            forward[i] = x[i] + step
            require(resolve(forward, by_vector=True) is not None and not resolve(forward, by_vector=True)['valid'],
                    'reverse step without a failed forward probe or an upper bound')
        require(np.allclose(jac[:, i], (vector(probe) - v0) / dx, rtol=1e-12, atol=1e-15),
                'Jacobian column not reproduced')
    for i in set(range(len(x))) - {int(k) for k in record['columns']}:
        require(not jac[:, i].any(), 'unavailable or frozen column carries values')
    for key, entry in record.get('check', {}).items():
        i = int(key)
        row = resolve(entry['attempt'])
        dx = row['log_factors'][i] - x[i]
        require(dx == entry['step_log'] and abs(abs(dx) - float(spec['check_step_log'])) < 1e-12
                and np.sign(dx) == np.sign(record['columns'][key]['step_log']), 'half-step check falsified')
        if not row['valid']:
            require(entry['passed'] is False, 'invalid half-step probe accepted')
            continue
        d3, d6 = (vector(row)[0] - v0[0]) / dx, jac[0, i]
        passed = abs(d6 - d3) <= float(spec['check_rtol']) * max(abs(d6), abs(d3)) + float(spec['check_atol'])
        require(np.isclose(entry['d003'], d3, rtol=1e-12, atol=1e-15) and entry['d006'] == d6
                and entry['passed'] == bool(passed), 'half-step check not reproduced')
    return len(record['columns'])


def incumbent_verdict(events, resolve, components, gain):
    """Recompute start-best and global incumbent updates from the rows themselves."""
    incumbent, start_best, updates = None, {}, 0
    for e in (e for e in events if e['event'] == 'objective'):
        row = resolve(e['attempt'])
        ok = components.admissible(row)
        primary = components.score(row)['primary'] if row['valid'] else None
        require(e['valid'] == bool(row['valid']) and e['admissible'] == ok, 'event admissibility differs')
        require(e['primary'] == primary, 'event utility differs')
        best = start_best.get(e['start'])
        better_start = ok and (best is None or primary < best - gain)
        better = ok and (incumbent is None or primary < incumbent - gain)
        require(e['start_best_updated'] == better_start and e['incumbent_updated'] == better, 'update rule violated')
        if better_start:
            start_best[e['start']] = primary
        if better:
            incumbent, updates = primary, updates + 1
    return updates


def seed_verdict(seeds, anchors, components, lower, upper, separation):
    for k, seed in enumerate(seeds):
        require(seed['group'] == 'restoration' and seed['stage'] in ('restoration', 'phase_one'),
                'seed not produced by restoration')
        require(feasible(seed), 'seed fails the 84 reserved guards')
        require(components.admissible(seed), 'seed fails the global cap or EGLC/ELAC focus protection')
        others = list(anchors) + [np.array(s['log_factors']) for s in seeds[:k]]
        require(min(normalized_distance(seed['log_factors'], o, lower, upper) for o in others) >= separation,
                'seed not separated')
    return len(seeds)


def export_verdict(release, f, vector):
    """The exported Vmax values themselves must equal the injected parameters of ONE vector."""
    groups = f['design']['groups']
    p = exact_parameters(f, vector)
    require(list(release['log_group_factors']) == list(groups)
            and list(release['log_group_factors'].values()) == list(vector), 'exported log factors differ')
    members = [k for m in groups.values() for k in m]
    require(sorted(release['vmax_values']) == sorted(members), 'exported Vmax set differs')
    for k in members:
        require(release['vmax_values'][k] == p[k], f'exported {k} differs from the injected parameter')
    require(release['parameters_sha256'] == canonical_sha(p), 'parameter hash differs')
    require(release['non_vmax_parameters_changed'] is False, 'non-Vmax change declared')
    return len(members)


# -------------------------------------------------------------------- main
def verify(out, receipt):
    require(not receipt.exists(), 'fresh receipt required')
    verify_archive(out)
    cfg = read(out / 'config.json')
    require(cfg == read(CONFIG) and cfg['release_objective_version'] == 'extracellular_first/2', 'config differs')
    protocol = read(out / 'protocol.json')
    for path, digest in protocol['code_sha256'].items():
        require(sha(ROOT / path) == digest, f'{path} changed after the campaign')
    source, f, obs, context, sources, campaigns, imported, hints = load_sources(cfg)
    require(sources == protocol['execution_sources_sha256'], 'transitive execution sources changed after the campaign')
    require(context == protocol['context'] and campaigns == protocol['campaigns'], 'simulation context differs')
    units = unit_status(obs)
    require(units == protocol['unit_status'], 'unit status differs')
    panel, references = historical_metrics(f, obs)
    channels = extracellular_channels(panel['names'], EXTERNAL_POOLS)
    require(channels == protocol['channels'] and len(channels) == cfg['release_objective']['expected_channel_count'],
            'extracellular channel registry differs')
    groups = list(f['design']['groups'])
    lower, upper = np.log([f['design']['factor_bounds'][k] for k in groups]).T
    summary = read(out / 'summary.json')
    for flag in ('Km_changed', 'initial_changed', 'bounds_changed', 'guards_rebased', 'activation_allowed',
                 'default_replacement', 'biologically_validated', 'ATP_ADP_targets_met'):
        require(summary[flag] is False, f'{flag} must be false')

    # Trace, budgets and physical supports of every attempt.
    b = cfg['budget']
    trace = [json.loads(line) for line in (out / 'trace.jsonl').read_text(encoding='utf-8').splitlines()]
    require([r['attempt'] for r in trace] == list(range(1, len(trace) + 1)), 'attempt numbering')
    by_group, by_label = Counter(r['group'] for r in trace), Counter(r['label'] for r in trace)
    require(by_group['restoration'] <= b['restoration_and_replays'] and by_group['search'] <= b['search']
            and len(trace) <= b['new_ode_global'], 'budget exceeded')
    require(by_label['matched_replay'] <= cfg['matched_replays']['limit'], 'matched replay limit exceeded')
    require(all(by_label[k] <= v for k, v in cfg['search']['start_limits'].items()), 'start budget exceeded')
    cached = {vector_key(r['log_factors']): r for r in imported}
    keys = [vector_key(r['log_factors']) for r in trace]
    require(len(set(keys)) == len(keys) and not set(keys) & set(cached), 'a qualified cached vector was integrated again')
    classes, points = Counter(), 0
    for row in trace:
        require(row['context'] == context, 'row from another context')
        result, verdict = check_folder(out / 'runs' / f'{row["attempt"]:03d}', f, panel, row['log_factors'])
        classes[verdict['class']] += 1
        points += verdict['points']
        expected = {k: row[k] for k in ('attempt', 'log_factors', 'stage', 'group', 'label', 'context')}
        require({**expected, **rescore(result, references['strict'], panel, f)} == row, 'trace row not reproduced')
    require(summary['invalid_by_group'] == {g: sum(1 for r in trace if r['group'] == g and not r['valid'])
                                            for g in ('restoration', 'search')}, 'failed attempts not accounted')
    by_id, by_vec = {r['attempt']: r for r in trace}, {vector_key(r['log_factors']): r for r in trace}
    qualified_imports = {r['source_id']: r for r in imported}

    def resolve(ref, by_vector=False):
        if by_vector:
            key = vector_key(ref)
            return by_vec.get(key) or cached.get(key)
        if isinstance(ref, int):
            require(ref in by_id, f'unknown attempt {ref}')
            return by_id[ref]
        require(ref in qualified_imports, f'{ref} is not context-qualified imported evidence')
        return qualified_imports[ref]

    # Fallbacks, allowances and the release components.
    refs = qualified_references(cfg, f, panel, references)
    anchor_mse = channel_mse(refs[0]['profiles']['strict']['prediction_mM'], panel, channels)
    for r in refs:
        finish_candidate(r, panel, channels, anchor_mse, float('inf'), units=units)
    fallbacks = sorted((r for r in refs if r['qualified'] and r['admissible']),
                       key=lambda r: (r['score']['primary'], r['score']['worst_normalized_rmse'], r['id']))
    caps = (focus_caps(fallbacks[0]['profiles']['strict']['prediction_mM'], panel,
                       cfg['release_objective']['focus_channels'], f['numeric']['comparison_atol_mM'],
                       f['numeric']['comparison_rtol']) if fallbacks else None)
    require(plain(caps) == protocol['focus_protection'] == summary['focus_protection'], 'focus allowances differ')
    cap = (fallbacks[0]['score']['worst_normalized_rmse'] * (1 + cfg['release_objective']['worst_cap_relative_tolerance'])
           if fallbacks else float('inf'))
    for r in refs:
        finish_candidate(r, panel, channels, anchor_mse, cap, caps, units)
    reserve = reserve_for(references['strict'], panel, f)
    guard_names = list(scored(refs[0]['profiles']['strict']['prediction_mM'], references['strict'], panel, f)
                       ['feasibility_guards'])
    components = Components(panel, channels, anchor_mse, units, guard_names,
                            reserve * cfg['guards']['optimizer_reserve_multiplier'],
                            np.maximum(reserve, cfg['guards']['constraint_scale_floor']), cap, caps)
    gain = float(np.log1p(cfg['release_objective']['minimum_relative_utility']))

    # Matched replays, seeds, Jacobians, incumbent.
    search = read(out / 'search_result.json')
    require(search['events'] == read(out / 'checkpoint.json')['events'], 'checkpoint and event log differ')
    archived = {r['source_id']: r for r in imported + hints}
    replayed = {vector_key(r['log_factors']): r for r in trace if r['stage'] == 'matched_replay'}
    replayed.update(cached)
    for d in search['drift']:
        a = archived[d['source_id']]
        require(plain(drift_check(replayed[vector_key(a['log_factors'])], a, f['numeric'])) == d, 'drift check differs')
    seeds = [resolve(i) for i in search['seeds']]
    anchors = [np.array(archived[k]['log_factors']) for k in cfg['matched_replays']['always']]
    seed_verdict(seeds, anchors, components, lower, upper, cfg['restoration']['minimum_normalized_separation'])
    for record in search['restoration']:
        if record['status'] == 'feasible_seed':
            require(record['seed_attempt'] in search['seeds'], 'restoration record names a non-admitted seed')
    columns = sum(jacobian_verdict(record, resolve, components.vector, cfg['search'], upper)
                  for record in read(out / 'jacobians.json'))
    updates = incumbent_verdict(search['events'], resolve, components, gain)
    for start in search['starts']:
        if start['best_attempt'] is not None:
            best = resolve(start['best_attempt'])
            require(components.admissible(best) and list(best['log_factors']) == start['best_vector'],
                    'start best is not an admissible row')

    # NEW finalists: supports, independent flux rebuild, pairing; then selection.
    new, balances = [], 0
    for item in (c for c in summary['candidates'] if c['kind'] == 'new'):
        vector = next((s['best_vector'] for s in search['starts'] if s['name'] == item['origin']), None)
        require(vector is not None, 'qualification candidate without a search origin')
        folder = out / 'qualification' / item['id']
        profiles = {}
        for p in cfg['qualification']['profiles']:
            result, verdict = check_folder(folder / p, f, panel, vector)
            points += verdict['points']
            profiles[p] = rescore(result, references[p], panel, f)
            if profiles[p]['valid']:
                with np.load(folder / p / 'flux_evidence.npz') as z:
                    balances += flux_verdict({k: z[k] for k in z.files}, f['numeric'])
        pair = compare_files(folder / 'strict' / 'flux_evidence.npz', folder / 'ultrastrict' / 'flux_evidence.npz', f)
        c = {'id': item['id'], 'kind': 'new', 'origin': item['origin'], 'source': item['source'], 'log_factors': vector,
             'paired': pair, 'qualified': bool(pair['pass'] and all(p['valid'] for p in profiles.values())),
             'profiles': {p: {k: r.get(k) for k in ('valid', 'error', 'prediction_mM', 'reserved_guards_pass')}
                          for p, r in profiles.items()}}
        new.append(finish_candidate(c, panel, channels, anchor_mse, cap, caps, units))
    require(2 * len(new) == summary['qualification_integrations'] <= b['qualification_integrations'],
            'qualification budget exceeded')
    release = read(out / 'release/provisional_extracellular_reference.json')
    if summary['stop'] == 'blocked_source_drift':
        require(release['status'] == 'blocked_source_drift' and release['selected'] is None, 'drift not blocked')
        decision = {'status': 'blocked_source_drift', 'selected': None}
    else:
        decision = select_release(refs + new, gain=cfg['release_objective']['minimum_relative_utility'])
    require(decision['status'] == summary['release_status'] == release['status'], 'release status differs')
    require(release['activation_allowed'] is False and 'activation_policy' in release, 'activation not forbidden')
    explicit = {'explicit': True, 'dataset_sha256': canonical_sha(obs), 'engine_context': context,
                'contract_fingerprint': 'any'}
    require(activation_permitted(release, explicit)['allowed'] is False, 'provisional release could be activated')
    exported = 0
    if decision['selected'] is not None:
        chosen = decision['selected']
        require(release['selected_id'] == chosen['id'] == summary['selected_id'], 'selected vector differs')
        exported = export_verdict(release, f, chosen['log_factors'])
        strict = chosen['profiles']['strict']['prediction_mM']
        for entry in release['species_by_date_strict']:
            i, j = panel['names'].index(entry['species']), panel['days'].index(entry['day'])
            require(entry['predicted'] == strict[i][j], 'species curve not from the single selected vector')
            require(units['status'] in entry['unit'], 'unit status missing from export')
        require(release['unit_status'] == units and plain(release['scores_by_profile']) == plain(chosen['scores']),
                'release scores or unit status differ')
        require(release['biologically_validated'] is False and release['complete_rbc_calibration'] is False,
                'release overstates its status')
    receipt.mkdir(parents=True)
    result = {'verified': True, 'objective': 'extracellular_first/2', 'new_ode_evaluations': len(trace),
              'by_group': dict(by_group), 'attempt_classes': dict(classes), 'support_points_checked': points,
              'jacobian_columns_rebuilt': columns, 'incumbent_updates': updates,
              'cache_qualified_rows': len(imported), 'unqualified_hints': len(hints), 'seeds_admitted': len(seeds),
              'new_finalists': len(new), 'qualification_integrations': 2 * len(new),
              'new_daily_balances_verified': balances,
              'fallback_qualification': 'historical sealed receipts, not re-verified here' if decision['selected'] is not None
              and decision['selected']['kind'] == 'fallback' else None,
              'exported_vmax_values_checked': exported, 'release_status': decision['status'],
              'unit_status': units['status'],
              'selected_id': decision['selected']['id'] if decision['selected'] else None,
              'activation_allowed': False, 'source_manifest_sha256': sha(out / 'manifest.json')}
    write(receipt / 'verification.json', result)
    print(result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('out', type=Path)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    verify(args.out, args.receipt)
