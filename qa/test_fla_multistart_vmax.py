"""Multistart Vmax-only SLSQP driver: budget, cache, constraint signs, resume,
derivative check, failure handling, seeds and Vmax-only identity.

No model ODE is integrated here: the driver receives an injected analytic
evaluator; the sealed-archive tests only read JSON/NPZ files.
"""
import ast
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
from fla_multistart_vmax import (BudgetExhausted, EvaluationStore, MultistartSearch, ResumeMismatch, admissible,
                                 constraint_jacobian, constraint_vector, feasible, joint_seeds, select_finalists,
                                 vector_key)

SIDES = ['A:lower', 'A:upper']
GUARDS = ['MSE:X', 'MSE:Y', 'date_gain:J4']
RESERVE = np.array([0.02, 0.02, 0.0])
LOWER, UPPER = np.full(3, -1.0), np.full(3, 1.0)
PREVIOUS = ROOT / 'output/corrected_vmax_2026_11_12'


class Fake:
    """Analytic stand-in for the scored ODE row; never integrates anything."""

    def __init__(self, curvature=0.0, invalid=None):
        self.curvature, self.invalid, self.jobs, self.calls = curvature, invalid, [], 0

    def values(self, x):
        sides = np.array([1 - x[0] - 0.5 * x[1] + 0.1 * np.sum(x ** 2) + self.curvature * (x[2] - 0.5) ** 2, -5.0])
        return sides, np.array([x[0] - 0.4, x[1] - 0.6, -0.5])

    def __call__(self, jobs):
        self.calls += 1
        rows = []
        for job in jobs:
            self.jobs.append(job)
            x = np.array(job['log_factors'])
            if self.invalid and self.invalid(x):
                rows.append({**job, 'valid': False, 'error': 'fake support failure'})
                continue
            s, g = self.values(x)
            rows.append({**job, 'valid': True,
                         'absolute': {'objective': float(np.max(s)), 'sides': dict(zip(SIDES, map(float, s)))},
                         'feasibility_guards': dict(zip(GUARDS, map(float, g))),
                         'reserved_guards_pass': bool(np.all(g <= -0.5 * RESERVE))})
        return rows


def config(**override):
    base = {'start_order': ['a', 'b'], 'start_evaluation_limits': {'a': 100, 'b': 100},
            'distinct_ode_evaluation_limit': 200, 'difference_step_log': 0.006, 'check_step_log': 0.003,
            'check_leading_groups': 2, 'check_binding_guards': 2, 'check_rtol': 0.25, 'check_atol_per_log': 1e-6,
            'optimizer_reserve_multiplier': 1.0, 'minimum_step_objective_gain': 1e-6,
            'slsqp': {'ftol': 1e-10, 'maxiter': 15}, 'max_segments_per_start': 4, 'failure_radius_fraction': 0.5,
            'minimum_box_radius_log': 1e-4, 'stagnation_iterations': 2}
    base.update(override)
    return base


START_A = {'name': 'a', 'vector': [0.0, 0.0, 0.5], 'stage': 'replay'}
START_B = {'name': 'b', 'vector': [-0.5, 0.2, 0.0], 'stage': 'seed'}


def run(fake, starts=(START_A, START_B), rows=(), expected=None, on_event=None, **override):
    cfg = config(**override)
    store = EvaluationStore(fake, limit=cfg['distinct_ode_evaluation_limit'],
                            start_limits=cfg['start_evaluation_limits'], rows=rows)
    search = MultistartSearch(store, lower=LOWER, upper=UPPER, side_names=SIDES, guard_names=GUARDS,
                              reserve=RESERVE, search=cfg, expected_events=expected, on_event=on_event)
    return store, search.run(list(starts))


# ---------------------------------------------------------------- budget/cache
def test_cache_hits_do_not_consume_budget():
    fake = Fake()
    store = EvaluationStore(fake, limit=5, start_limits={'a': 5})
    v = [[0.1, 0.0, 0.0], [0.2, 0.0, 0.0], [0.3, 0.0, 0.0]]
    store.request(v, 'slsqp', 'a')
    store.request(v + v, 'slsqp', 'a')
    assert len(fake.jobs) == 3 and store.used['a'] == 3 and store.new_evaluations == 3
    assert [r['attempt'] for r in store.rows] == [1, 2, 3]


def test_budget_refuses_whole_batch_before_launching():
    fake = Fake()
    store = EvaluationStore(fake, limit=10, start_limits={'a': 4})
    store.request([[0.1, 0.0, 0.0], [0.2, 0.0, 0.0], [0.3, 0.0, 0.0]], 'gradient', 'a')
    with pytest.raises(BudgetExhausted) as error:
        store.request([[0.4, 0.0, 0.0], [0.5, 0.0, 0.0]], 'gradient', 'a')
    assert error.value.scope == 'a' and len(fake.jobs) == 3 and fake.calls == 1
    full = EvaluationStore(Fake(), limit=2, start_limits={'a': 2})
    full.request([[0.1, 0.0, 0.0], [0.2, 0.0, 0.0]], 'gradient', 'a')
    with pytest.raises(BudgetExhausted):
        full.request([[0.3, 0.0, 0.0]], 'gradient', 'a')


def test_start_limits_cannot_exceed_global_and_trace_cannot_exceed_budget():
    with pytest.raises(ValueError):
        EvaluationStore(Fake(), limit=3, start_limits={'a': 2, 'b': 2})
    rows = Fake()([{'attempt': i + 1, 'log_factors': [0.01 * i, 0.0, 0.0], 'stage': 'slsqp', 'start': 'a'}
                   for i in range(3)])
    with pytest.raises(ValueError):
        EvaluationStore(Fake(), limit=10, start_limits={'a': 2}, rows=rows)


def test_duplicate_or_renumbered_trace_rows_are_refused():
    rows = Fake()([{'attempt': 1, 'log_factors': [0.0, 0.0, 0.0], 'stage': 'replay', 'start': 'a'}])
    with pytest.raises(ValueError):
        EvaluationStore(Fake(), limit=5, start_limits={'a': 5}, rows=rows + [{**rows[0], 'attempt': 2}])
    with pytest.raises(ValueError):
        EvaluationStore(Fake(), limit=5, start_limits={'a': 5}, rows=[{**rows[0], 'attempt': 2}])


def test_small_start_budget_stops_and_keeps_feasible_incumbent():
    fake = Fake()
    store, result = run(fake, start_evaluation_limits={'a': 4, 'b': 100})
    a = result['starts'][0]
    assert a['stop_reason'] == 'budget_a' and store.used['a'] == 4
    assert a['best_attempt'] == a['start_attempt'] == 1
    assert sum(job['start'] == 'a' for job in fake.jobs) == 4
    assert feasible(result['incumbent'])


# ------------------------------------------------------------ constraint signs
def test_constraint_vector_and_jacobian_use_slsqp_nonnegative_convention():
    c = constraint_vector(2.0, [1.5, -1.0], [-0.03, 0.01, -0.5], RESERVE)
    assert np.allclose(c, [0.5, 3.0, 0.01, -0.03, 0.5])
    js, jg = np.array([[1.0, 2.0, 3.0], [0.0, 0.0, 0.0]]), np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0, 0, 0.0]])
    j = constraint_jacobian(js, jg, [0, 2])
    assert j.shape == (5, 3)
    assert np.allclose(j[0], [-1.0, -3.0, 1.0]) and np.allclose(j[2], [-1.0, 0.0, 0.0])
    assert np.allclose(j[2:, -1], 0.0)


def test_search_respects_hard_guards_with_reserve_and_improves():
    fake = Fake()
    store, result = run(fake)
    best = result['incumbent']
    x = np.array(best['log_factors'])
    s, g = fake.values(x)
    assert feasible(best) and np.all(g <= -0.5 * RESERVE)
    assert best['absolute']['objective'] < 1.025 - 0.5
    assert x[0] <= 0.4 - 0.5 * RESERVE[0] + 1e-12
    assert best['stage'] in ('replay', 'seed', 'slsqp')
    assert all(np.all(LOWER <= r['log_factors']) and np.all(np.array(r['log_factors']) <= UPPER) for r in store.rows)


def test_objective_is_the_epigraph_variable_not_a_penalty(monkeypatch):
    import fla_multistart_vmax as module
    calls, real = [], module.minimize

    def spy(fun, z0, **kwargs):
        calls.append((fun, np.array(z0), kwargs))
        return real(fun, z0, **kwargs)

    monkeypatch.setattr(module, 'minimize', spy)
    run(Fake())
    assert calls
    for fun, z0, kwargs in calls:
        z = np.linspace(-0.3, 0.3, len(z0))
        z[-1] = 7.5
        expected = np.zeros(len(z0))
        expected[-1] = 1.0
        assert fun(z) == 7.5 and np.array_equal(kwargs['jac'](z), expected)
        assert kwargs['method'] == 'SLSQP' and kwargs['bounds'][-1] == (None, None)
        assert len(kwargs['constraints']) == 1 and kwargs['constraints'][0]['type'] == 'ineq'


def test_infeasible_rows_never_update_the_incumbent():
    store, result = run(Fake())
    for event in result['events']:
        if event['event'] == 'objective' and (event['incumbent_updated'] or event['start_best_updated']):
            assert feasible(store.rows[event['attempt'] - 1])
    assert any(e['event'] == 'objective' and not e['feasible'] for e in result['events']) or \
        all(feasible(r) for r in store.rows if r['stage'] == 'slsqp')


def test_infeasible_start_is_recorded_not_optimized():
    bad = {'name': 'b', 'vector': [0.5, 0.0, 0.0], 'stage': 'seed'}
    store, result = run(Fake(), starts=(START_A, bad))
    b = result['starts'][1]
    assert b['status'] == 'infeasible_start' and b['segments'] == [] and store.used['b'] == 1
    assert result['incumbent']['start'] == 'a'


def test_registered_start_order_is_enforced():
    with pytest.raises(ValueError):
        run(Fake(), starts=(START_B, START_A))


# ------------------------------------------------------------------- resume
def test_full_replay_from_trace_needs_no_integration():
    store, result = run(Fake())

    def forbidden(jobs):
        raise AssertionError('resume must not integrate cached vectors')

    store2, result2 = run(forbidden, rows=store.rows, expected=result['events'])
    assert result2['events'] == result['events'] and store2.new_evaluations == 0
    assert result2['incumbent']['attempt'] == result['incumbent']['attempt']


def test_interrupted_run_resumes_to_the_same_path():
    store, result = run(Fake())
    k = len(store.rows) // 2
    fake = Fake()
    store2, result2 = run(fake, rows=store.rows[:k], expected=result['events'][:10])
    assert result2['events'] == result['events']
    assert store2.new_evaluations == len(store.rows) - k == len(fake.jobs)
    assert [r['log_factors'] for r in store2.rows] == [r['log_factors'] for r in store.rows]


def test_resume_detects_a_diverging_checkpoint():
    store, result = run(Fake())
    events = [dict(e) for e in result['events']]
    events[3] = {**events[3], 'attempt': -1}
    with pytest.raises(ResumeMismatch):
        run(Fake(), rows=store.rows, expected=events)


def test_checkpoint_hook_sees_every_event():
    seen = []
    _, result = run(Fake(), on_event=lambda search: seen.append(len(search.events)))
    assert seen == list(range(1, len(result['events']) + 1))


# ----------------------------------------------- derivatives and failures
def test_jacobian_columns_are_secants_at_the_registered_step():
    store, result = run(Fake())
    by_id = {r['attempt']: r for r in store.rows}
    record = result['jacobians'][0]
    anchor = np.array(by_id[record['anchor_attempt']]['log_factors'])
    for key, entry in record['columns'].items():
        i = int(key)
        probe = np.array(by_id[entry['attempt']]['log_factors'])
        assert abs(abs(entry['step_log']) - 0.006) < 1e-12
        assert np.array_equal(np.delete(probe, i), np.delete(anchor, i))
        s0 = np.array(list(by_id[record['anchor_attempt']]['absolute']['sides'].values()))
        sp = np.array(list(by_id[entry['attempt']]['absolute']['sides'].values()))
        assert np.array_equal(np.array(record['side_jacobian'])[:, i], (sp - s0) / entry['step_log'])


def test_derivative_check_runs_once_per_start_at_half_step():
    store, result = run(Fake())
    checks = [j for j in result['jacobians'] if 'check' in j]
    assert sorted(j['start'] for j in checks) == ['a', 'b']
    for record in checks:
        for entry in record['check']['groups'].values():
            assert abs(abs(entry['step_log']) - 0.003) < 1e-12 and entry['passed']
    assert sum(r['stage'] == 'gradient_check' for r in store.rows) == 4


def test_failed_derivative_check_freezes_the_coordinate():
    store, result = run(Fake(curvature=50.0), check_leading_groups=3)
    a = result['starts'][0]
    assert any(2 in f['coordinates'] and '0.006/0.003' in f['reason'] for f in a['frozen'])
    for row in store.rows:
        if row['start'] == 'a' and row['stage'] == 'slsqp':
            assert row['log_factors'][2] == 0.5


def test_failed_forward_probe_uses_reverse_step():
    fake = Fake(invalid=lambda x: 0.005 < x[0] < 0.007)
    store, result = run(fake)
    first = result['jacobians'][0]
    assert abs(first['columns']['0']['step_log'] + 0.006) < 1e-12
    assert any(r['stage'] == 'gradient_reverse' for r in store.rows)
    assert any(r['stage'] == 'gradient' and not r['valid'] for r in store.rows)


def test_invalid_integration_is_never_scored_and_shrinks_the_box():
    fake = Fake(invalid=lambda x: x[0] > 0.2)
    store, result = run(fake)
    invalid = [r for r in store.rows if not r['valid']]
    assert invalid and all('absolute' not in r for r in invalid)
    a = result['starts'][0]
    assert any(s.get('ended_by') == 'probe_failure' for s in a['segments'])
    assert result['incumbent']['valid'] and result['incumbent']['log_factors'][0] <= 0.2
    restarts = [s for s in a['segments'] if s.get('ended_by') == 'probe_failure']
    assert all(0 < s['new_radius_log'] for s in restarts)


# ------------------------------------------------------------------- seeds
def test_seeds_are_deterministic_bounded_and_respect_bounds():
    jo = np.array([[-1.0, 0.5, 0.2], [0.0, 0.0, 0.0]])
    jg = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 0.0]])
    anchor = [1.0, 0.0, -1.0]
    kwargs = dict(objective_jacobian=jo, side_names=SIDES, active_side='A:lower', guard_jacobian=jg,
                  guard_slack=[0.01, 0.2, 0.5], radius=0.05, guard_count=2, random_seed=20261112, tolerance=1e-12)
    first, second = joint_seeds(anchor, LOWER, UPPER, **kwargs), joint_seeds(anchor, LOWER, UPPER, **kwargs)
    assert first == second and len(first) == 3
    for seed in first:
        if seed['vector'] is None:
            continue
        v = np.array(seed['vector'])
        assert np.all(LOWER <= v) and np.all(v <= UPPER)
        assert np.max(np.abs(v - anchor)) <= 0.05 + 1e-15
        assert v[0] <= 1.0 and v[2] >= -1.0
    descent = first[0]
    assert descent['direction'][0] == 0.0
    other = joint_seeds(anchor, LOWER, UPPER, **{**kwargs, 'random_seed': 1})
    assert other[2]['vector'] != first[2]['vector']


# ------------------------------------------------------- finalists/admission
def test_finalists_need_feasible_gain_and_are_unique_and_capped():
    rows = Fake()([{'attempt': i + 1, 'log_factors': v, 'stage': 'slsqp', 'start': 'a'}
                   for i, v in enumerate([[0.0, 0.0, 0.0], [0.3, 0.0, 0.0], [0.2, 0.0, 0.0], [0.395, 0.0, 0.0]])])
    assert not feasible(rows[3])  # best objective but inside the reserve: never a finalist
    reference = rows[0]
    summaries = [{'best_row': rows[1]}, {'best_row': rows[1]}, {'best_row': rows[2]},
                 {'best_row': rows[3]}, {'best_row': None}, {'best_row': reference}]
    finalists = select_finalists(summaries, reference, gain=1e-6, maximum=5)
    assert [r['attempt'] for r in finalists] == [2, 3]
    assert len(select_finalists(summaries, reference, gain=1e-6, maximum=1)) == 1


def test_admission_needs_both_profiles_and_paired_convergence():
    ok = {'valid': True, 'reserved_guards_pass': True}
    assert admissible({'strict': ok, 'ultrastrict': ok}, True)
    assert not admissible({'strict': ok, 'ultrastrict': ok}, False)
    assert not admissible({'strict': ok, 'ultrastrict': {'valid': True, 'reserved_guards_pass': False}}, True)
    assert not admissible({}, True)
    assert not admissible({'strict': ok}, True)
    assert not admissible({'ultrastrict': ok}, True)


# ------------------------------------------------- sealed inputs, no ODE
def sealed():
    f = json.loads((PREVIOUS / 'execution_design.json').read_text())
    rows = {r['attempt']: r for r in map(json.loads, (PREVIOUS / 'trace.jsonl').read_text().splitlines())}
    return f, rows, json.loads((PREVIOUS / 'sensitivity_round3.json').read_text())


def test_registered_configuration_matches_the_dispatch():
    from run_multistart_vmax import CONFIG, CODE, check_invariants
    cfg = json.loads(CONFIG.read_text())
    f, rows, _ = sealed()
    check_invariants(cfg, f, rows[35])
    s, v = cfg['search'], cfg['validation']
    assert s['distinct_ode_evaluation_limit'] == 240 and sum(s['start_evaluation_limits'].values()) <= 240
    assert s['start_order'][:2] == ['candidate35', 'working_centre'] and len(s['start_order']) == 5
    assert (s['difference_step_log'], s['check_step_log']) == (0.006, 0.003)
    assert v['max_integrations'] <= 12 and 2 * v['max_finalists'] <= 12 and cfg['workers'] <= 3
    assert cfg['previous_selected_attempt'] == 35 and not cfg['production_promotion_allowed']
    assert all(p.exists() for p in CODE)


def test_sealed_seeds_and_probes_change_only_grouped_vmax():
    from run_vmax_requalification import historical_metrics
    from run_pgk_ndpk_profile import reserve_for
    from fla_vmax_requalification import exact_parameters, within_original_box
    f, rows, sensitivity = sealed()
    obs = json.loads((PREVIOUS / 'observations.json').read_text())
    panel, references = historical_metrics(f, obs)
    reserve = reserve_for(references['strict'], panel, f)
    row = rows[35]
    groups = f['design']['groups']
    lo, hi = np.log([f['design']['factor_bounds'][k] for k in groups]).T
    sides, guards = list(row['absolute']['sides']), list(row['feasibility_guards'])
    assert sensitivity['guard_names'] == guards and len(guards) == 84 and len(reserve) == 84
    s = np.array(list(row['absolute']['sides'].values()))
    g = np.array(list(row['feasibility_guards'].values()))
    cfg = json.loads((ROOT / 'config/fla_multistart_vmax_2026_11_12.json').read_text())['seeds']
    seeds = joint_seeds(row['log_factors'], lo, hi, objective_jacobian=sensitivity['objective_jacobian'],
                        side_names=sides, active_side=sides[int(np.argmax(s))],
                        guard_jacobian=sensitivity['guard_jacobian'], guard_slack=-reserve - g,
                        radius=cfg['radius_log'], guard_count=cfg['guard_relief_count'],
                        random_seed=cfg['random_seed'], tolerance=cfg['at_bound_tolerance_log'])
    x = np.array(row['log_factors'])
    vectors = [np.array(seed['vector']) for seed in seeds if seed['vector'] is not None]
    vectors += [x + np.eye(14)[i] * (0.006 if x[i] + 0.006 <= hi[i] else -0.006) for i in range(14)]
    for v in vectors:
        assert within_original_box(f, v)
        p = exact_parameters(f, v)
        changed = {k for k in p if p[k] != f['parameters'][k]}
        assert all(k.startswith('vmax_') for k in changed)
        for a, b in (('vmax_VAK', 'vmax_VAK_rev'), ('vmax_VNDPK', 'vmax_VNDPK_rev')):
            assert np.isclose(p[a] / f['parameters'][a], p[b] / f['parameters'][b], rtol=1e-12, atol=0)
    for seed in seeds:
        if seed['vector'] is not None:
            v = np.array(seed['vector'])
            assert np.all(v >= lo) and np.all(v <= hi) and np.max(np.abs(v - x)) <= cfg['radius_log'] + 1e-15


# ---------------------------------------------------- runner file helpers
def test_trace_loader_moves_a_truncated_tail(tmp_path):
    from run_multistart_vmax import load_trace
    (tmp_path / 'trace.jsonl').write_text('{"attempt": 1}\n{"attempt": 2}\n{"attem', encoding='utf-8')
    assert load_trace(tmp_path) == [{'attempt': 1}, {'attempt': 2}]
    assert (tmp_path / 'trace.jsonl').read_text(encoding='utf-8') == '{"attempt": 1}\n{"attempt": 2}\n'
    assert (tmp_path / 'trace_truncated_tail.txt').read_text(encoding='utf-8') == '{"attem'


def test_interrupted_folder_is_kept_aside_not_deleted(tmp_path):
    from run_multistart_vmax import completed, orphan
    f, rows, _ = sealed()
    folder = tmp_path / 'search' / '007'
    folder.mkdir(parents=True)
    (folder / 'parameters.json').write_text('{}', encoding='utf-8')
    assert completed(folder, f, rows[35]['log_factors']) is None
    orphan(tmp_path, folder)
    assert not folder.exists() and (tmp_path / 'search' / '007.orphan1' / 'parameters.json').exists()
    record = json.loads((tmp_path / 'orphans.jsonl').read_text(encoding='utf-8'))
    assert record == {'folder': 'search/007', 'moved_to': 'search/007.orphan1'}


def test_replay_reproduction_tolerance():
    from run_multistart_vmax import reproduce
    archived = {'attempt': 35, 'prediction_mM': [[1.0, 2.0]]}
    row = {'attempt': 1, 'valid': True, 'reserved_guards_pass': True, 'prediction_mM': [[1.0, 2.0 + 1e-13]]}
    tolerance = {'atol_mM': 1e-12, 'rtol': 1e-9}
    out = reproduce(row, archived, tolerance)
    assert out['pass'] and not out['bitwise_equal']
    assert not reproduce({**row, 'prediction_mM': [[1.0, 2.1]]}, archived, tolerance)['pass']
    assert not reproduce({'attempt': 1, 'valid': False}, archived, tolerance)['pass']


def test_driver_module_imports_no_model_code():
    tree = ast.parse((ROOT / 'src/fla_multistart_vmax.py').read_text(encoding='utf-8'))
    modules = {a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    modules |= {n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert modules <= {'json', 'numpy', 'scipy'}


def test_vector_key_is_bitwise():
    assert vector_key([0.1, 0.2]) == vector_key(np.array([0.1, 0.2]))
    assert vector_key([0.1, 0.2]) != vector_key([0.1, np.nextafter(0.2, 1.0)])
    with pytest.raises(ValueError):
        vector_key([np.nan])
