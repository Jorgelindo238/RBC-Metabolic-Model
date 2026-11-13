"""Extracellular-first Vmax-only release (objective extracellular_first/2).

Inventory, matched replays, seed restoration, search, qualification and export.
Sealed archives are read, never modified. Every new ODE goes through
run_corrected_vmax.evaluate (qualified strict Radau, bounded Jacobian, recorded
accepted/dense/quadrature evidence); qualification uses the full backend,
strict and ultrastrict, with flux audit.

Entry points (run by Codex):
  python scripts/run_extracellular_release.py --out output/extracellular_release_2026_11_12
  python scripts/run_extracellular_release.py --out output/extracellular_release_2026_11_12 --resume
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
import hashlib
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
from run_multistart_vmax import completed, orphan, load_trace
from fla_vmax_requalification import exact_parameters
from rbc_gem_audit import EXTERNAL_POOLS
from fla_extracellular_release import (BudgetExhausted, ContextStore, EventLog, ReleaseSearch, channel_mse,
                                       context_fingerprint, extracellular_channels, feasible, focus_caps,
                                       local_import_closure, rank_key, release_admissible, release_gradient,
                                       release_score, restore_seeds, row_id, select_release, transitive_evidence,
                                       unit_status)

CONFIG = ROOT / 'config/fla_extracellular_release_2026_11_12.json'
CODE = [Path(__file__), ROOT / 'scripts/verify_extracellular_release.py', ROOT / 'src/fla_extracellular_release.py',
        CONFIG, ROOT / 'tasks/fla_extracellular_release_protocol_2026_11_12.md',
        ROOT / 'qa/test_fla_extracellular_release.py', ROOT / 'scripts/run_multistart_vmax.py',
        ROOT / 'src/rbc_gem_audit.py']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def check_invariants(cfg, f):
    inv, groups = cfg['invariants'], f['design']['groups']
    require(cfg['release_objective_version'] == 'extracellular_first/2', 'objective version must be /2')
    require(len(groups) == inv['groups'] and sum(map(len, groups.values())) == inv['capacities'], '14/17 required')
    for name, members in inv['paired_groups_unchanged'].items():
        require(groups[name] == members, f'{name} grouping changed')
    require(f['temporal']['fit_days'] == inv['fit_days'], 'dates changed')
    require(inv['guards_excluded'] == [] and all(inv[k] is False for k in inv if k.endswith('_changed') or
                                                 k == 'guards_rebased'), 'scientific invariant flag changed')
    b = cfg['budget']
    require(b['new_ode_global'] == 240 and b['restoration_and_replays'] + b['search'] == 240
            and b['restoration_and_replays'] <= 80 and b['qualification_integrations'] <= 12, 'budget contract')
    require(cfg['matched_replays']['limit'] <= b['restoration_and_replays'], 'matched replays exceed restoration budget')
    require(sum(cfg['search']['start_limits'].values()) <= b['search'], 'start limits exceed search budget')
    require(2 * cfg['qualification']['max_candidates'] <= b['qualification_integrations'], 'qualification budget')
    require(cfg['search']['difference_step_log'] == 0.006 and cfg['search']['check_step_log'] == 0.003, 'steps')
    require(cfg['guards']['optimizer_reserve_multiplier'] == 1.0, 'inherited full reserve')
    require(cfg['workers'] <= 3 and cfg['restoration']['target_seeds'] <= 3, 'workers/seeds')
    require(cfg['release_objective']['minimum_utility_gain'] == 'log1p(0.001)', 'registered utility threshold')
    r = cfg['release']
    require(not r['default_replacement'] and not r['activation_allowed'] and not r['biologically_validated'],
            'no activation, replacement or validation claim')


def execution_sources():
    """Transitive local import closure of the evaluator, hashed (kernel/RHS/transport/positivity/solver)."""
    closure = local_import_closure(ROOT / 'scripts/run_corrected_vmax.py', [ROOT / 'scripts', ROOT / 'src'])
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in closure}


def load_sources(cfg):
    """Sealed inputs, current context, campaign evidence, cached rows and unqualified hints.

    Archived rows enter the cache ONLY when the campaign itself recorded hashes for
    the whole current transitive closure and they are equal. Otherwise the rows are
    unqualified screening hints and matched replays are budgeted.
    """
    source = ROOT / cfg['numerical_source']
    verify_archive(source)
    f = read(source / 'execution_design.json')
    obs = read(source / 'observations.json')
    require(read(source / 'control_gate.json')['pass'], 'qualified control certificate required')
    require(scipy.__version__ == cfg['scipy_version'] == f['requalification_plan']['scipy_version'], 'SciPy version')
    check_invariants(cfg, f)
    sources = execution_sources()
    context = context_fingerprint(design_sha256=canonical_sha(f), observations_sha256=canonical_sha(obs),
                                  sources_sha256=sources, profile=cfg['context']['search_profile'],
                                  backend=cfg['context']['search_backend'], scipy_version=scipy.__version__)
    campaigns, imported, hints = [], [], []
    for item in cfg['compatible_campaigns']:
        archive = ROOT / item['archive']
        verify_archive(archive)
        receipt = read(ROOT / item['receipt'])
        evidence = transitive_evidence(sources, read(archive / 'protocol.json')['code_sha256'])
        inputs_equal = read(archive / 'execution_design.json') == f and read(archive / 'observations.json') == obs
        receipt_ok = bool(receipt['verified'] and receipt['source_manifest_sha256'] == sha(archive / 'manifest.json'))
        qualified = bool(evidence['qualified'] and inputs_equal and receipt_ok)
        rows = [json.loads(line) for line in (archive / 'trace.jsonl').read_text().splitlines()]
        campaigns.append({'id': item['id'], 'archive': item['archive'], 'manifest_sha256': sha(archive / 'manifest.json'),
                          'rows': len(rows), 'inputs_equal': inputs_equal, 'receipt_verified': receipt_ok,
                          'cache_qualified': qualified, 'missing_source_evidence': evidence['missing'],
                          'changed_sources': evidence['changed']})
        for row in rows:
            entry = {**{k: v for k, v in row.items() if k != 'attempt'}, 'attempt': None,
                     'source_id': f'{item["id"]}:{row["attempt"]}'}
            if qualified:
                imported.append({**entry, 'context': context})
            else:
                hints.append(entry)
    return source, f, obs, context, sources, campaigns, imported, hints


def qualified_references(cfg, f, panel, references):
    """Sealed, audited fallbacks (historical qualification receipts, not re-run here)."""
    out = []
    for item in cfg['qualified_references']:
        archive = ROOT / item['archive']
        if item['kind'] == 'control_gate':
            gate = read(archive / 'control_gate.json')
            numeric = gate['pass'] and all(v for k, v in gate['numerical'].items() if k.startswith('working_center/full/'))
            paired = gate['comparisons']['working_center/full/paired']['pass']
            profiles = {p: gate['working_center_scores'][k] for p, k in item['profiles'].items()}
            vector = f[item['vector']]
            receipts = {'control_gate': sha(archive / 'control_gate.json'), 'manifest': sha(archive / 'manifest.json')}
        else:
            summary = read(archive / 'summary.json')
            require(summary['selected_attempt'] == item['attempt'], 'qualified attempt changed')
            numeric = all(summary['validation'][p]['valid'] for p in ('strict', 'ultrastrict'))
            paired = summary['paired']['pass']
            profiles = summary['validation']
            vector = read(archive / 'search_result.json')['selected']['log_factors']
            receipts = {'summary': sha(archive / 'summary.json'), 'manifest': sha(archive / 'manifest.json')}
        out.append({'id': item['id'], 'kind': 'fallback', 'log_factors': vector, 'qualified': bool(numeric and paired),
                    'qualification_context': 'historical sealed receipt',
                        'profiles': {p: {'prediction_mM': (profiles[p]['metrics']['prediction_mM']
                                                          if item['kind'] == 'control_gate'
                                                          else profiles[p]['prediction_mM']),
                                     'reserved_guards_pass': profiles[p]['reserved_guards_pass'],
                                     'valid': True} for p in ('strict', 'ultrastrict')},
                    'receipts': receipts})
    return out


def make_evaluator(out, f, panel, references, pool, stream):
    def evaluate_many(jobs):
        launched = []
        for job in jobs:
            folder = out / 'runs' / f'{job["attempt"]:03d}'
            done = completed(folder, f, job['log_factors'])
            if done is None:
                if folder.exists():
                    orphan(out, folder)
                done = pool.submit(evaluate, folder, f, job['log_factors'], panel['names'])
            launched.append((job, done))
        rows = []
        for job, item in launched:
            result = dict(item if isinstance(item, dict) else item.result())
            if result['valid']:
                try:
                    result.update(scored(result['prediction_mM'], references['strict'], panel, f))
                except ValueError as error:
                    result.update(valid=False, error=str(error))
            text = json.dumps({**job, **result}, allow_nan=False)
            stream.write(text + '\n')
            stream.flush()
            os.fsync(stream.fileno())
            row = json.loads(text)
            print(f'{row["attempt"]:03d} {row["group"]}/{row["label"]}/{row["stage"]}: valid={row["valid"]} '
                  f'feasible={feasible(row)}', flush=True)
            rows.append(row)
        return rows
    return evaluate_many


def drift_check(replay, archived, numeric):
    """Matched replay versus archived row, inherited comparison atol + rtol*max(|a|,|b|)."""
    if not replay['valid']:
        return {'pass': False, 'reason': 'replay invalid', 'source_id': archived['source_id']}
    a, b = np.array(replay['prediction_mM']), np.array(archived['prediction_mM'])
    limit = numeric['comparison_atol_mM'] + numeric['comparison_rtol'] * np.maximum(np.abs(a), np.abs(b))
    return {'pass': bool(np.all(np.abs(a - b) <= limit)), 'bitwise_equal': bool(np.array_equal(a, b)),
            'max_abs_difference': float(np.max(np.abs(a - b))), 'source_id': archived['source_id'],
            'attempt': replay['attempt']}


def directions(cfg, f, panel, channels, anchor_mse, anchors, guard_names):
    """``anchors``: current-context rows {'candidate35': row, 'working_centre': row}."""
    spec = cfg['restoration']
    names = list(f['design']['groups'])
    sens = {k: read(ROOT / v) for k, v in spec['sensitivity_sources'].items()}
    archived = {'candidate35': cfg['qualified_references'][1]['attempt'], 'working_centre': 1}
    for key, s in sens.items():
        require(list(s['groups']) == names and s['guard_names'] == guard_names, 'stored Jacobian layout differs')
        require(s['anchor_attempt'] == archived[key], 'stored Jacobian anchor differs')
    rng = np.random.default_rng(spec['random_seed'])
    random_direction = rng.uniform(-1.0, 1.0, len(names))
    built = []
    for name in spec['directions']:
        key = 'working_centre' if name.endswith('working_centre') else 'candidate35'
        anchor, s = anchors[key], sens[key]
        if name.startswith('release_descent'):
            d = -release_gradient(s, anchor['prediction_mM'], panel, channels, anchor_mse)
        elif name.startswith('focus_descent'):
            d = -release_gradient(s, anchor['prediction_mM'], panel, cfg['release_objective']['focus_channels'], anchor_mse)
        elif name.startswith('guard_relief'):
            jg = np.array(s['guard_jacobian'])
            g = np.array([anchor['feasibility_guards'][k] for k in guard_names])
            d = -sum(jg[k] / max(np.linalg.norm(jg[k]), np.finfo(float).tiny) for k in np.argsort(-g, kind='stable')[:3])
        else:
            d = random_direction
        built.append({'name': name, 'anchor_row': anchor, 'anchor_label': key,
                      'guard_jacobian': s['guard_jacobian'], 'direction': np.asarray(d, float).tolist()})
    return built


def qualify(out, f, panel, references, candidates, pool, q):
    jobs = {}
    for c in candidates:
        for profile in q['profiles']:
            folder = out / 'qualification' / c['id'] / profile
            done = completed(folder, f, c['log_factors'])
            if done is None:
                if folder.exists():
                    orphan(out, folder)
                done = pool.submit(evaluate, folder, f, c['log_factors'], panel['names'], profile, q['backend'],
                                   q['flux_audit'])
            jobs[c['id'], profile] = done
    for c in candidates:
        profiles = {}
        for profile in q['profiles']:
            item = jobs[c['id'], profile]
            r = dict(item if isinstance(item, dict) else item.result())
            if r['valid']:
                try:
                    r.update(scored(r['prediction_mM'], references[profile], panel, f))
                except ValueError as error:
                    r.update(valid=False, error=str(error))
            profiles[profile] = r
        pair = compare_files(out / 'qualification' / c['id'] / 'strict' / 'flux_evidence.npz',
                             out / 'qualification' / c['id'] / 'ultrastrict' / 'flux_evidence.npz', f)
        c['profiles'] = {p: {k: r.get(k) for k in ('valid', 'error', 'prediction_mM', 'reserved_guards_pass')}
                         for p, r in profiles.items()}
        c['paired'] = pair
        c['qualified'] = bool(pair['pass'] and all(r['valid'] for r in profiles.values()))
        c['qualification_context'] = 'this campaign, current sources'
    return candidates


def finish_candidate(c, panel, channels, anchor_mse, worst_cap, caps=None, units=None):
    """Release scores for every qualified profile of ONE vector (both profiles must pass)."""
    c['scores'] = {}
    ok = c['qualified']
    for p, r in c['profiles'].items():
        if not r.get('valid'):
            ok = False
            continue
        c['scores'][p] = release_score(r['prediction_mM'], panel, channels, anchor_mse, units=units)
        ok = ok and release_admissible(r, c['scores'][p], worst_cap, caps)
    c['admissible'] = bool(ok and set(c['scores']) == {'strict', 'ultrastrict'})
    c['score'] = c['scores'].get('strict')
    return c


def write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)


def export_release(out, cfg, f, obs, panel, channels, decision, references, context, campaigns, units, caps,
                   drift=None):
    chosen = decision['selected']
    (out / 'release').mkdir(parents=True, exist_ok=True)
    policy = cfg['release']['activation_policy']
    if chosen is None:
        write(out / 'release/provisional_extracellular_reference.json',
              {'status': decision['status'], 'reason': decision['reason'], 'selected': None, 'unit_status': units,
               'drift': drift, 'activation_allowed': False, 'activation_policy': policy, 'default_replacement': False,
               'next_task': decision.get('next_task', 'qualify a compatible vector under the current sources')})
        return
    p = exact_parameters(f, chosen['log_factors'])
    strict = chosen['profiles']['strict']['prediction_mM']
    species = []
    for i, name in enumerate(panel['names']):
        for j, day in enumerate(panel['days']):
            band = float(panel['bands'][i, j])
            y, x = float(panel['target'][i, j]), float(strict[i][j])
            species.append({'species': name, 'compartment': 'extracellular' if name in EXTERNAL_POOLS else 'intracellular',
                            'day': day, 'observed': y, 'predicted': x, 'absolute_error': abs(x - y),
                            'unit': 'mM (' + units['status'] + ')', 'working_band': band,
                            'normalized_residual': (x - y) / band if band > 0 else None,
                            'release_channel': name in channels})
    guards = scored(strict, references['strict'], panel, f)
    release = {
        'status': cfg['release']['status_name'], 'release_objective_version': cfg['release_objective_version'],
        'selected_id': chosen['id'], 'selected_kind': chosen['kind'],
        'qualification_context': chosen.get('qualification_context'),
        'improved_over_fallback': decision['improved_over_fallback'], 'fallback_id': decision['fallback_id'],
        'log_group_factors': dict(zip(f['design']['groups'], chosen['log_factors'])),
        'vmax_values': {k: p[k] for members in f['design']['groups'].values() for k in members},
        'parameters_sha256': canonical_sha(p), 'non_vmax_parameters_changed': False,
        'observations_sha256': canonical_sha(obs),
        'applicable_dataset': 'only the archived curated table identified by observations_sha256; '
                              'not transferable to user datasets',
        'cohort': 'single curated table; donor unknown; donors not merged; no per-donor validation',
        'unit_status': units, 'scale': cfg['release_objective']['scale'],
        'initial_state': '55 measured J1 values exact; latent pools explicitly labelled; R5P historical comparator only',
        'geometry': 'H = 0.58 borrowed, not a matched donor measurement', 'horizon_days': cfg['release']['horizon_days'],
        'J46': cfg['release']['J46'], 'solver': f['requalification_plan'], 'context_fingerprint': context,
        'scores_by_profile': chosen['scores'], 'focus_protection': caps, 'drift_checks': drift,
        'species_by_date_strict': species,
        'guards_strict': {'feasibility_guards': guards['feasibility_guards'],
                          'reserved_guards_pass': guards['reserved_guards_pass']},
        'qualification': {'paired': chosen.get('paired', {'pass': True, 'source': 'sealed receipt'}),
                          'receipts': chosen.get('receipts', {})},
        'limitations': ['ATP/ADP absolute J15 targets NOT met (ATP J15 about 9e-5 mM vs window from 0.757 mM)',
                        'early ATP/ADP collapse unexplained; adenylate observation contract open',
                        'latent stocks without measured values or bounds', 'borrowed geometry, single unknown donor',
                        'unit mM is a historical model assumption, not recorded in the source archive',
                        'working bands are not assay SD; no relative-to-mM conversion'],
        'compatible_campaigns': campaigns,
        'activation_allowed': False, 'activation_policy': policy, 'eligibility': None,
        'default_replacement': False, 'biologically_validated': False, 'complete_rbc_calibration': False}
    write(out / 'release/provisional_extracellular_reference.json', release)
    write_csv(out / 'release/species_by_date.csv', list(species[0]), [list(s.values()) for s in species])


def execute(out, resume):
    cfg = read(CONFIG)
    source, f, obs, context, sources, campaigns, imported, hints = load_sources(cfg)
    units = unit_status(obs)
    panel, references = historical_metrics(f, obs)
    channels = extracellular_channels(panel['names'], EXTERNAL_POOLS)
    focus = cfg['release_objective']['focus_channels']
    require(len(channels) == cfg['release_objective']['expected_channel_count'], 'extracellular channel registry changed')
    require(all(c in channels for c in focus), 'focus channels missing')
    groups = list(f['design']['groups'])
    lower, upper = np.log([f['design']['factor_bounds'][k] for k in groups]).T
    reserve = reserve_for(references['strict'], panel, f)
    margin = reserve * cfg['guards']['optimizer_reserve_multiplier']
    scale = np.maximum(reserve, cfg['guards']['constraint_scale_floor'])
    refs = qualified_references(cfg, f, panel, references)
    anchor_ref = next(r for r in refs if r['id'] == 'working_centre')
    guard_names = list(scored(anchor_ref['profiles']['strict']['prediction_mM'], references['strict'], panel, f)
                       ['feasibility_guards'])
    require(len(guard_names) == cfg['invariants']['feasibility_guards'] == len(reserve), '84 guards required')
    anchor_mse = channel_mse(anchor_ref['profiles']['strict']['prediction_mM'], panel, channels)
    for r in refs:
        finish_candidate(r, panel, channels, anchor_mse, float('inf'), units=units)
    fallbacks = sorted((r for r in refs if r['qualified'] and r['admissible']), key=lambda r: (*rank_key(r['score']), r['id']))
    tolerance = cfg['release_objective']['worst_cap_relative_tolerance']
    worst_cap = fallbacks[0]['score']['worst_normalized_rmse'] * (1 + tolerance) if fallbacks else None
    numeric = f['numeric']
    caps = (focus_caps(fallbacks[0]['profiles']['strict']['prediction_mM'], panel, focus,
                       numeric['comparison_atol_mM'], numeric['comparison_rtol']) if fallbacks else None)
    for r in refs:
        finish_candidate(r, panel, channels, anchor_mse, worst_cap if worst_cap is not None else float('inf'), caps, units)

    def score_row(row):
        return release_score(row['prediction_mM'], panel, channels, anchor_mse, units=units)

    def admit(row):
        return bool(worst_cap is not None and row['valid'] and release_admissible(row, score_row(row), worst_cap, caps))

    inventory = []
    for row in imported + hints:
        entry = {'source_id': row['source_id'], 'cache_qualified': row.get('context') == context,
                 'valid': row['valid'], 'reserved_guards_pass': feasible(row), 'unit_status': units['status']}
        if row['valid'] and worst_cap is not None:
            s = score_row(row)
            entry.update(primary=s['primary'], mean_normalized_rmse=s['mean_normalized_rmse'],
                         worst_normalized_rmse=s['worst_normalized_rmse'], worst_channel=s['worst_channel'],
                         focus={c: s['focus'][c] for c in focus}, release_admissible=admit(row))
        inventory.append(entry)
    code = {p.relative_to(ROOT).as_posix(): sha(p) for p in CODE}
    if resume:
        require(out.exists() and not (out / 'manifest.json').exists(), 'resumable unsealed campaign required')
        protocol = read(out / 'protocol.json')
        require(protocol['code_sha256'] == code and protocol['execution_sources_sha256'] == sources
                and read(out / 'config.json') == cfg, 'code, execution sources or config changed: no resume')
        rows = load_trace(out)
        expected = read(out / 'checkpoint.json')['events'] if (out / 'checkpoint.json').exists() else None
    else:
        require(not out.exists(), 'Fresh successor directory required')
        out.mkdir(parents=True)
        write(out / 'config.json', cfg)
        write(out / 'execution_design.json', f)
        write(out / 'observations.json', obs)
        write(out / 'protocol.json', {'release_objective_version': cfg['release_objective_version'], 'context': context,
              'execution_sources_sha256': sources, 'source_manifest_sha256': sha(source / 'manifest.json'),
              'campaigns': campaigns, 'channels': channels, 'unit_status': units, 'focus_protection': caps,
              'budget': cfg['budget'], 'code_sha256': code})
        write(out / 'inventory.json', {'campaigns': campaigns, 'unit_status': units, 'qualified_references':
              [{k: v for k, v in r.items() if k != 'profiles'} for r in refs], 'rows': inventory,
              'incompatible_sources_listed_not_ranked': cfg['incompatible_sources_listed_not_ranked']})
        rows, expected = [], None

    def checkpoint(log):
        write(out / 'checkpoint.json.tmp', {'events': log.events})
        os.replace(out / 'checkpoint.json.tmp', out / 'checkpoint.json')

    log = EventLog(expected, checkpoint)
    stop, seeds, records, starts, search, new, drift = None, [], [], [], None, [], []
    b, s = cfg['budget'], cfg['search']
    with ProcessPoolExecutor(max_workers=cfg['workers']) as pool, \
            (out / 'trace.jsonl').open('a' if resume else 'x', encoding='utf-8') as stream:
        store = ContextStore(make_evaluator(out, f, panel, references, pool, stream), context=context,
                             limits={'restoration': b['restoration_and_replays'], 'search': b['search']},
                             label_limits=s['start_limits'], rows=rows, imported=imported)
        if worst_cap is None:
            stop = 'blocked_no_qualified_fallback'
        else:
            # Matched replays: both fallback vectors always (drift check), plus the best
            # archived screening hints when the archive cache is not qualified.
            archived = {r['source_id']: r for r in imported + hints}
            plan = [archived[k] for k in cfg['matched_replays']['always']]
            ranked = sorted((r for r in hints if r['valid'] and admit(r)),
                            key=lambda r: (*rank_key(score_row(r)), r['source_id']))
            seen = {tuple(r['log_factors']) for r in plan}
            for r in ranked:
                if len(plan) >= cfg['matched_replays']['limit']:
                    break
                if tuple(r['log_factors']) not in seen:
                    plan.append(r)
                    seen.add(tuple(r['log_factors']))
            replays = {}
            for r in plan:
                replays[r['source_id']] = store.request([r['log_factors']], 'matched_replay', 'restoration',
                                                        'matched_replay')[0]
            drift = [drift_check(replays[r['source_id']], r, numeric) for r in plan]
            log.emit({'event': 'matched_replays', 'drift': drift})
            if not all(d['pass'] for d in drift[:len(cfg['matched_replays']['always'])]):
                stop = 'blocked_source_drift'
            else:
                current = [r for r in replays.values()] + imported
                candidates = [r for r in current if admit(r)]
                if not candidates:
                    stop = 'no_release_admissible_current_row'
                else:
                    anchor = min(candidates, key=lambda r: (*rank_key(score_row(r)), str(row_id(r))))
                    log.emit({'event': 'release_anchor', 'id': row_id(anchor), 'primary': score_row(anchor)['primary']})
                    anchors = {'candidate35': replays[cfg['matched_replays']['always'][0]],
                               'working_centre': replays[cfg['matched_replays']['always'][1]]}
                    seeds, records = restore_seeds(store, directions(cfg, f, panel, channels, anchor_mse, anchors,
                                                                     guard_names),
                                                   lower=lower, upper=upper, guard_names=guard_names, margin=margin,
                                                   scale=scale, spec=cfg['restoration'], emit=log.emit, admit=admit)
                    search = ReleaseSearch(store, lower=lower, upper=upper, guard_names=guard_names, margin=margin,
                                           scale=scale, worst_cap=worst_cap, scorer=score_row, spec=s,
                                           gain=float(np.log1p(cfg['release_objective']['minimum_relative_utility'])),
                                           log=log, caps=caps)
                    for name, row in [('release_anchor', anchor)] + [(f'seed_{k + 1}', r) for k, r in enumerate(seeds)]:
                        starts.append(search.run_start(name, row))
        log.emit({'event': 'search_end', 'stop': stop, 'new_evaluations': len(store.rows)})
        log.finish()
        write(out / 'search_result.json', {'starts': starts, 'restoration': records, 'drift': drift,
              'seeds': [row_id(r) for r in seeds], 'events': log.events})
        write(out / 'jacobians.json', search.jacobians if search else [])
        if search is not None:
            fallback_primary = fallbacks[0]['score']['primary']
            best = {}
            for st in starts:
                if st['best_vector'] is not None and st['best_primary'] < fallback_primary - search.gain:
                    best.setdefault(tuple(st['best_vector']), st)
            ranked = sorted(best.values(), key=lambda st: (st['best_primary'], str(st['best_attempt'])))
            new = [{'id': f'new_{k + 1}', 'kind': 'new', 'origin': st['name'], 'source': st['best_attempt'],
                    'log_factors': list(st['best_vector'])} for k, st in enumerate(ranked[:cfg['qualification']['max_candidates']])]
            qualify(out, f, panel, references, new, pool, cfg['qualification'])
            for c in new:
                finish_candidate(c, panel, channels, anchor_mse, worst_cap, caps, units)
    if stop == 'blocked_source_drift':
        decision = {'status': 'blocked_source_drift', 'selected': None,
                    'reason': 'a fallback matched replay differs from its archive beyond inherited comparison tolerance',
                    'next_task': 'requalify the fallbacks under the current execution sources'}
    else:
        decision = select_release(refs + new, gain=cfg['release_objective']['minimum_relative_utility'])
    export_release(out, cfg, f, obs, panel, channels, decision, references, context, campaigns, units, caps, drift)
    summary = {'stop': stop or 'completed', 'release_objective_version': cfg['release_objective_version'],
               'new_ode_evaluations': len(store.rows), 'by_group': store.used, 'invalid_by_group': store.invalid,
               'by_label': store.by_label, 'cache_qualified_rows': len(imported), 'unqualified_hint_rows': len(hints),
               'drift': drift, 'unit_status': units, 'focus_protection': caps,
               'seeds_admitted': [row_id(r) for r in seeds],
               'restoration': [{k: v for k, v in r.items() if k != 'trials'} for r in records],
               'starts': [{k: v for k, v in st.items() if k != 'best_vector'} for st in starts],
               'qualification_integrations': 2 * len(new),
               'candidates': [{k: c.get(k) for k in ('id', 'kind', 'qualified', 'admissible', 'origin', 'source')}
                              | {'primary': c['score']['primary'] if c.get('score') else None,
                                 'worst': c['score']['worst_normalized_rmse'] if c.get('score') else None}
                              for c in refs + new],
               'release_status': decision['status'],
               'selected_id': decision['selected']['id'] if decision['selected'] else None,
               'improved_over_fallback': decision.get('improved_over_fallback', False),
               'ATP_ADP_targets_met': False, 'Km_changed': False, 'initial_changed': False, 'bounds_changed': False,
               'guards_rebased': False, 'activation_allowed': False, 'default_replacement': False,
               'biologically_validated': False}
    write(out / 'summary.json', summary)
    verify_archive(source)
    for item in cfg['compatible_campaigns']:
        verify_archive(ROOT / item['archive'])
    write(out / 'manifest.json', {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob('*')) if p.is_file()})
    print(f'FINISHED: release={decision["status"]} selected={summary["selected_id"]} '
          f'new_ode={len(store.rows)}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT / 'output/extracellular_release_2026_11_12')
    parser.add_argument('--resume', action='store_true')
    arguments = parser.parse_args()
    with threadpool_limits(1):
        execute(arguments.out, arguments.resume)
