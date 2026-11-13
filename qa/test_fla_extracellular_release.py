"""Extracellular release successor (extracellular_first/2): scoring, focus protection,
context/transitive cache, restoration, search, selection, units and activation.
Written for Codex; no model ODE is integrated here (injected analytic evaluators;
sealed archives are only read)."""
import ast
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
from fla_extracellular_release import (BudgetExhausted, ContextStore, EventLog, ReleaseSearch, ResumeMismatch,
                                       activation_permitted, broyden, channel_mse, context_fingerprint,
                                       extracellular_channels, feasible, focus_caps, focus_metrics, focus_ok,
                                       local_import_closure, normalized_distance, project_step, release_admissible,
                                       release_gradient, release_score, restore_seeds, select_release,
                                       transitive_evidence, unit_status, violation)

SOURCE = ROOT / 'output/vmax_requalification_2026_11_09'
CFG = json.loads((ROOT / 'config/fla_extracellular_release_2026_11_12.json').read_text())


def toy_panel():
    names = ('EGLC', 'EINO', 'EZERO', 'ELAC')
    target = np.array([[10.0, 9.0, 8.0, 7.0], [0.0, 0.0, 0.1, 0.2], [0.0] * 4, [1.0, 2.0, 3.0, 4.0]])
    bands = np.array([[1.0] * 4, [0.0, 0.0, 0.02, 0.04], [0.0] * 4, [0.5] * 4])
    return {'names': names, 'days': [4, 8, 11, 15], 'target': target, 'bands': bands}


CH = ['EGLC', 'EINO', 'EZERO', 'ELAC']


# ------------------------------------------------------------------ utility
def test_channels_come_from_the_external_registry():
    from rbc_gem_audit import EXTERNAL_POOLS
    names = list(json.loads((SOURCE / 'observations.json').read_text())['values'])
    channels = extracellular_channels(names, EXTERNAL_POOLS)
    assert len(channels) == CFG['release_objective']['expected_channel_count'] == 19
    assert 'EGLC' in channels and 'ELAC' in channels and 'GLC' not in channels and 'LAC' not in channels


def test_exact_fit_of_candidate_and_anchor_is_finite_and_accepted():
    panel = toy_panel()
    exact = panel['target'].copy()
    anchor = channel_mse(exact, panel, CH)          # anchor fits every defined channel exactly
    assert anchor['EGLC'] == 0.0 and anchor['EZERO'] is None
    score = release_score(exact, panel, CH, anchor)
    assert score['primary'] == 0.0 and score['scored_channels'] == ['EGLC', 'EINO', 'ELAC']
    off = exact + np.array([[1.0] * 4, [0.0] * 4, [0.0] * 4, [0.0] * 4])
    worse = release_score(off, panel, CH, anchor)
    assert np.isfinite(worse['primary']) and worse['primary'] == pytest.approx(0.5 * np.log1p(1.0) / 3)
    better = release_score(exact, panel, CH, channel_mse(off, panel, CH))
    assert better['primary'] == pytest.approx(-0.5 * np.log1p(1.0) / 3)


def test_all_zero_band_channel_is_reported_not_scored():
    panel = toy_panel()
    prediction = panel['target'] + np.array([[0.0] * 4, [0.01, 0.02, 0.0, 0.0], [0.3] * 4, [0.0] * 4])
    score = release_score(prediction, panel, CH, channel_mse(panel['target'], panel, CH))
    assert score['unscored_channels'] == ['EZERO']
    assert score['per_channel']['EZERO']['absolute_errors_mM'] == pytest.approx([0.3] * 4)
    eino = score['per_channel']['EINO']
    assert eino['zero_band_days'] == [4, 8] and eino['normalized_residuals'][:2] == [None, None]
    assert eino['absolute_errors_mM'][:2] == pytest.approx([0.01, 0.02])


def test_one_near_perfect_channel_cannot_dominate():
    panel = toy_panel()
    anchor = channel_mse(panel['target'] + np.array([[1e-6] * 4, [0.0] * 4, [0.0] * 4, [0.5] * 4]), panel, CH)
    exact_eglc = panel['target'] + np.array([[0.0] * 4, [0.0] * 4, [0.0] * 4, [0.5] * 4])
    gain = release_score(exact_eglc, panel, CH, anchor)['primary']
    assert -1e-10 < gain <= 0.0  # log1p: removing a 1e-12 MSE is worth ~nothing, not -infinity


def test_utility_gradient_is_finite_and_matches_finite_differences_even_at_exact_fit():
    panel = toy_panel()
    rng = np.random.default_rng(3)
    sens = {'pool_names': list(panel['names']), 'days': panel['days'],
            'groups': {f'G{k}': {'d_concentration_d_log_factor': rng.normal(size=(4, 4)).tolist()} for k in range(3)}}
    for x0 in (panel['target'] + np.array([[1.0, 0.5, 0.2, 0.4], [0.0, 0.0, 0.03, 0.05], [0.0] * 4, [0.1] * 4]),
               panel['target'].copy()):
        anchor = channel_mse(x0, panel, CH)
        g = release_gradient(sens, x0, panel, CH, anchor)
        assert np.isfinite(g).all()
        for k, entry in enumerate(sens['groups'].values()):
            h = 1e-6
            d = np.array(entry['d_concentration_d_log_factor'])
            plus = release_score(x0 + h * d, panel, CH, anchor)['primary']
            minus = release_score(x0 - h * d, panel, CH, anchor)['primary']
            assert g[k] == pytest.approx((plus - minus) / (2 * h), rel=1e-4, abs=1e-6)


# ------------------------------------------------------------- focus guard
def test_focus_allowances_follow_the_inherited_comparison_formula():
    panel = toy_panel()
    fallback = panel['target'] + 0.5
    caps = focus_caps(fallback, panel, ['EGLC', 'ELAC'], 1e-5, 0.01)
    delta = 1e-5 + 0.01 * np.abs(fallback[0])
    assert caps['EGLC']['allowance']['abs_J15_residual'] == pytest.approx(delta[-1])
    assert caps['EGLC']['allowance']['abs_slope_error'] == pytest.approx((delta[0] + delta[-1]) / 11)
    assert caps['EGLC']['allowance']['normalized_rmse'] == pytest.approx(np.sqrt(np.mean(delta ** 2)))
    base = focus_metrics(fallback, panel, 'EGLC')
    assert caps['EGLC']['cap']['normalized_rmse'] == pytest.approx(base['normalized_rmse'] + np.sqrt(np.mean(delta ** 2)))


def test_focus_regression_is_rejected_despite_a_better_mean():
    panel = toy_panel()
    fallback = panel['target'] + np.array([[0.1] * 4, [0.0, 0.0, 0.05, 0.08], [0.0] * 4, [0.05] * 4])
    anchor = channel_mse(fallback, panel, CH)
    caps = focus_caps(fallback, panel, ['EGLC', 'ELAC'], 1e-5, 0.01)
    candidate = panel['target'] + np.array([[0.4] * 4, [0.0] * 4, [0.0] * 4, [0.05] * 4])  # EINO exact, EGLC worse
    score = release_score(candidate, panel, CH, anchor)
    assert score['primary'] < 0  # the mean utility improves
    row = {'valid': True, 'reserved_guards_pass': True}
    assert not focus_ok(score, caps) and not release_admissible(row, score, 1e9, caps)
    assert release_admissible(row, release_score(fallback, panel, CH, anchor), 1e9, caps)


# ------------------------------------------------- provenance and caching
def test_unit_status_is_assumed_unless_recorded():
    obs = json.loads((SOURCE / 'observations.json').read_text())
    assert unit_status(obs)['status'] == 'assumed_mM_historical_model_convention'
    assert unit_status({**obs, 'units': {p: 'mM' for p in obs['values']}})['status'] == 'source_recorded_mM'
    assert 'mM as archived' not in json.dumps(CFG['release_objective']['units'])


def test_dependency_drift_disqualifies_cache_even_with_unchanged_evaluator(tmp_path):
    (tmp_path / 'scripts').mkdir()
    (tmp_path / 'src').mkdir()
    entry, dep, deeper = tmp_path / 'scripts/entry.py', tmp_path / 'src/kernel.py', tmp_path / 'src/positivity.py'
    entry.write_text('import numpy\nfrom kernel import rhs\n', encoding='utf-8')
    dep.write_text('from positivity import clip\ndef rhs(): return 1\n', encoding='utf-8')
    deeper.write_text('def clip(x): return x\n', encoding='utf-8')
    closure = local_import_closure(entry, [tmp_path / 'scripts', tmp_path / 'src'])
    assert sorted(p.name for p in closure) == ['entry.py', 'kernel.py', 'positivity.py']
    import hashlib

    def hashes():
        return {p.relative_to(tmp_path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in local_import_closure(entry, [tmp_path / 'scripts', tmp_path / 'src'])}

    recorded = hashes()
    assert transitive_evidence(hashes(), recorded)['qualified']
    deeper.write_text('def clip(x): return max(x, 0)\n', encoding='utf-8')
    evidence = transitive_evidence(hashes(), recorded)
    assert not evidence['qualified'] and evidence['changed'] == ['src/positivity.py']
    assert hashes()['scripts/entry.py'] == recorded['scripts/entry.py']  # evaluator wrapper unchanged
    only_wrapper = {'scripts\\entry.py': recorded['scripts/entry.py']}
    assert transitive_evidence(hashes(), only_wrapper)['missing'] == ['src/kernel.py', 'src/positivity.py']
    a = context_fingerprint(design_sha256='d', observations_sha256='o', sources_sha256=recorded, profile='strict',
                            backend='joint', scipy_version='1.17.1')
    b = context_fingerprint(design_sha256='d', observations_sha256='o', sources_sha256=hashes(), profile='strict',
                            backend='joint', scipy_version='1.17.1')
    assert a != b


def test_cache_from_another_context_is_never_reused():
    imported = [{'log_factors': [0.0, 0.0], 'attempt': None, 'source_id': 'old:1', 'context': 'A', 'valid': True}]
    with pytest.raises(ValueError):
        ContextStore(Linear(np.eye(2), [-1, -1]), context='B', limits={'restoration': 5, 'search': 5}, imported=imported)
    fake = Linear(np.eye(2), [-1, -1])
    store = ContextStore(fake, context='A', limits={'restoration': 5, 'search': 5}, imported=imported)
    assert store.request([[0.0, 0.0]], 'restoration', 'restoration', 'd')[0]['source_id'] == 'old:1'
    assert fake.jobs == [] and store.used['restoration'] == 0


def test_archived_campaigns_lack_transitive_evidence_so_rows_are_hints_only():
    from run_extracellular_release import execution_sources
    sources = execution_sources()
    assert 'scripts/run_corrected_vmax.py' in sources and len(sources) > 5
    assert 'src/fla_agentic_gem_correction.py' in sources and 'src/reaction_positivity.py' in sources
    for archive in ('output/corrected_vmax_2026_11_12', 'output/multistart_vmax_2026_11_12'):
        recorded = json.loads((ROOT / archive / 'protocol.json').read_text())['code_sha256']
        evidence = transitive_evidence(sources, recorded)
        # these campaigns recorded the evaluate wrapper but not the RHS/positivity kernel
        assert not evidence['qualified'] and 'src/fla_agentic_gem_correction.py' in evidence['missing']


# ------------------------------------------------------------------- store
def guards_row(job, guards, valid=True):
    row = {**job, 'valid': valid}
    if valid:
        row.update(feasibility_guards=dict(guards), reserved_guards_pass=bool(max(guards.values()) <= -0.005))
    return row


class Linear:
    """g(x) = A x + c, two guards; invalid where ``invalid(x)``."""

    def __init__(self, a, c, invalid=None):
        self.a, self.c, self.invalid, self.jobs = np.array(a, float), np.array(c, float), invalid, []

    def guards(self, x):
        return dict(zip(['G1', 'G2'], (self.a @ np.asarray(x) + self.c).tolist()))

    def __call__(self, jobs):
        self.jobs += jobs
        return [guards_row(job, self.guards(np.array(job['log_factors'])),
                           not (self.invalid and self.invalid(np.array(job['log_factors'])))) for job in jobs]


def test_group_and_label_budgets_refuse_before_launching():
    fake = Linear(np.eye(2), [-1, -1])
    store = ContextStore(fake, context='A', limits={'restoration': 2, 'search': 3}, label_limits={'s1': 1})
    store.request([[0.1, 0.0]], 'matched_replay', 'restoration', 'matched_replay')
    store.request([[0.2, 0.0]], 'restoration', 'restoration', 'd')
    with pytest.raises(BudgetExhausted):
        store.request([[0.3, 0.0]], 'phase_one', 'restoration', 'd')
    store.request([[0.4, 0.0]], 'search', 'search', 's1')
    with pytest.raises(BudgetExhausted):
        store.request([[0.5, 0.0]], 'search', 'search', 's1')
    assert len(fake.jobs) == 3 and store.used == {'restoration': 2, 'search': 1}


def test_failed_attempts_are_accounted_separately():
    fake = Linear(np.eye(2), [-1, -1], invalid=lambda x: x[0] > 0.25)
    store = ContextStore(fake, context='A', limits={'restoration': 5, 'search': 5})
    store.request([[0.1, 0.0], [0.3, 0.0]], 'restoration', 'restoration', 'd')
    assert store.invalid == {'restoration': 1, 'search': 0}


# -------------------------------------------------------------- restoration
LO, HI = np.array([-1.0, -1.0]), np.array([1.0, 1.0])
SPEC = {'target_seeds': 3, 'radius_log': 0.3, 'backtracking_fractions': [1.0, 0.5, 0.25], 'phase_one_iterations': 4,
        'max_evaluations_per_direction': 10, 'minimum_normalized_separation': 0.01}
MARGIN, SCALE = np.array([0.01, 0.01]), np.array([0.01, 0.01])


def anchor_row(fake, x):
    return {'attempt': None, 'source_id': 'anchor', 'log_factors': list(x), 'valid': True,
            'feasibility_guards': fake.guards(x), 'reserved_guards_pass': True}


def run_restore(fake, anchor, jacobian, direction, spec=SPEC, admit=None, limit=20):
    store = ContextStore(fake, context='A', limits={'restoration': limit, 'search': 1})
    return store, *restore_seeds(store, [{'name': 'd', 'anchor_row': anchor, 'guard_jacobian': jacobian,
                                          'direction': direction}], lower=LO, upper=HI, guard_names=['G1', 'G2'],
                                 margin=MARGIN, scale=SCALE, spec=spec, emit=lambda e: None, admit=admit)


def test_projection_restores_linear_feasibility_without_ode():
    d, info = project_step([0.3, 0.0], np.zeros(2), LO, HI, np.array([-0.1, -0.5]), np.eye(2), MARGIN, 0.3, SCALE)
    assert d[0] <= 0.09 + 1e-7 and info['linear_max_scaled_violation'] <= 1e-6


def test_backtracking_admits_a_replayed_feasible_separated_seed():
    fake = Linear(np.eye(2), [-0.1, -0.5])
    _, seeds, records = run_restore(fake, anchor_row(fake, [0.0, 0.0]), np.eye(2).tolist(), [1.0, 0.0])
    assert len(seeds) == 1 and feasible(seeds[0]) and records[0]['status'] == 'feasible_seed'
    assert normalized_distance(seeds[0]['log_factors'], [0.0, 0.0], LO, HI) >= SPEC['minimum_normalized_separation']


def test_negligible_or_duplicate_seed_is_not_a_basin():
    fake = Linear(np.eye(2), [-0.1, -0.5])
    _, seeds, records = run_restore(fake, anchor_row(fake, [0.0, 0.0]), np.eye(2).tolist(), [1.0, 1.0],
                                    spec={**SPEC, 'radius_log': 0.001})
    assert seeds == [] and fake.jobs == [] and records[0]['status'] == 'not_restored'


def test_phase_one_uses_real_replays_and_broyden_updates():
    fake = Linear(np.eye(2), [-0.01, -0.5])
    _, seeds, _ = run_restore(fake, anchor_row(fake, [-0.3, 0.0]), (-np.eye(2)).tolist(), [1.0, 0.0],
                              spec={**SPEC, 'radius_log': 0.6, 'backtracking_fractions': [1.0]})
    stages = [j['stage'] for j in fake.jobs]
    assert 'phase_one' in stages and stages.count('restoration') == 1
    assert len(seeds) == 1 and feasible(seeds[0])


def test_phase_one_never_steps_from_an_invalid_integration():
    fake = Linear(np.eye(2), [-0.1, -0.5], invalid=lambda x: x[0] > 0.0)
    _, seeds, _ = run_restore(fake, anchor_row(fake, [0.0, 0.0]), np.eye(2).tolist(), [1.0, 0.0])
    assert seeds == [] and not any(j['stage'] == 'phase_one' for j in fake.jobs)


def test_focus_protection_can_reject_a_guard_feasible_seed():
    fake = Linear(np.eye(2), [-0.1, -0.5])
    _, seeds, records = run_restore(fake, anchor_row(fake, [0.0, 0.0]), np.eye(2).tolist(), [1.0, 0.0],
                                    admit=lambda row: False)
    assert seeds == [] and records[0]['status'] in ('guard_feasible_but_release_inadmissible', 'not_restored')


def test_restoration_budget_is_shared_and_reported():
    fake = Linear(np.eye(2), [0.5, 0.5])
    store = ContextStore(fake, context='A', limits={'restoration': 4, 'search': 1})
    anchor = anchor_row(fake, [0.0, 0.0])
    items = [{'name': f'd{k}', 'anchor_row': anchor, 'guard_jacobian': np.eye(2).tolist(), 'direction': [1.0, 0.1 * k]}
             for k in range(3)]
    seeds, records = restore_seeds(store, items, lower=LO, upper=HI, guard_names=['G1', 'G2'], margin=MARGIN,
                                   scale=SCALE, spec=SPEC, emit=lambda e: None)
    assert seeds == [] and store.used['restoration'] <= 4
    assert any(r['status'] == 'restoration_budget_exhausted' for r in records)


def test_violation_and_broyden_helpers():
    assert violation([-0.1, 0.02], [0.01, 0.01]) == pytest.approx(0.03 ** 2)
    j = broyden(np.zeros((2, 2)), np.array([1.0, 0.0]), np.array([2.0, 3.0]))
    assert np.allclose(j @ np.array([1.0, 0.0]), [2.0, 3.0])


# ------------------------------------------------------------------- search
class Quadratic:
    def __init__(self):
        self.jobs = []

    def __call__(self, jobs):
        self.jobs += jobs
        out = []
        for job in jobs:
            x = np.array(job['log_factors'])
            g = {'G1': x[0] - 0.4, 'G2': x[1] - 0.6}
            out.append({**job, 'valid': True, 'feasibility_guards': g, 'reserved_guards_pass': bool(max(g.values()) <= -0.005),
                        'mse': (x[0] - 1) ** 2 + (x[1] - 1) ** 2})
        return out


def scorer(row):
    mse = row['mse']
    return {'primary': 0.5 * float(np.log1p(mse) - np.log1p(2.0)), 'scored_channels': ['C'],
            'per_channel': {'C': {'normalized_mse': mse, 'normalized_rmse': float(np.sqrt(mse))}}}


def search_spec():
    return {'difference_step_log': 0.006, 'check_step_log': 0.003, 'check_leading_groups': 2, 'check_rtol': 0.25,
            'check_atol': 1e-6, 'slsqp': {'ftol': 1e-10, 'maxiter': 15}, 'max_segments_per_start': 3,
            'failure_radius_fraction': 0.5, 'minimum_box_radius_log': 1e-4, 'stagnation_iterations': 2}


def test_search_improves_utility_under_hard_guards_and_worst_cap():
    store = ContextStore(Quadratic(), context='A', limits={'restoration': 1, 'search': 120},
                         label_limits={'release_anchor': 120})
    start = store.request([[0.0, 0.0]], 'search', 'search', 'release_anchor')[0]
    log = EventLog()
    search = ReleaseSearch(store, lower=LO, upper=HI, guard_names=['G1', 'G2'], margin=MARGIN, scale=SCALE,
                           worst_cap=np.sqrt(2.0), scorer=scorer, spec=search_spec(), gain=np.log1p(1e-3), log=log)
    summary = search.run_start('release_anchor', start)
    best = search.incumbent
    assert feasible(best) and best['log_factors'][0] <= 0.4 - 0.005 + 1e-12
    assert scorer(best)['primary'] < scorer(start)['primary'] - np.log1p(1e-3)
    assert summary['best_attempt'] == best['attempt'] and store.used['search'] <= 120


def test_search_label_budget_stops_the_start():
    store = ContextStore(Quadratic(), context='A', limits={'restoration': 1, 'search': 120}, label_limits={'seed_1': 3})
    start = store.request([[0.0, 0.0]], 'search', 'search', 'seed_1')[0]
    search = ReleaseSearch(store, lower=LO, upper=HI, guard_names=['G1', 'G2'], margin=MARGIN, scale=SCALE,
                           worst_cap=np.sqrt(2.0), scorer=scorer, spec=search_spec(), gain=1e-6, log=EventLog())
    assert search.run_start('seed_1', start)['stop_reason'] == 'budget_seed_1' and store.by_label['seed_1'] <= 3


def test_event_log_detects_a_diverging_resume():
    log = EventLog(expected=[{'event': 'a'}])
    with pytest.raises(ResumeMismatch):
        log.emit({'event': 'b'})


# ------------------------------------------------- selection and activation
def candidate(cid, kind, primary, worst, qualified=True, admissible=True):
    return {'id': cid, 'kind': kind, 'qualified': qualified, 'admissible': admissible, 'log_factors': [0.0],
            'score': {'primary': primary, 'worst_normalized_rmse': worst}}


def test_fallback_is_kept_without_a_qualified_utility_gain():
    d = select_release([candidate('wc', 'fallback', 0.0, 10.0), candidate('c35', 'fallback', -0.01, 10.0),
                        candidate('n1', 'new', -0.0105, 10.0), candidate('n2', 'new', -0.5, 11.0),
                        candidate('n3', 'new', -0.6, 9.0, qualified=False),
                        candidate('n4', 'new', -0.7, 9.0, admissible=False)], gain=1e-3)
    assert d['selected']['id'] == 'c35' and d['improved_over_fallback'] is False


def test_qualified_improvement_replaces_fallback():
    d = select_release([candidate('wc', 'fallback', 0.0, 10.0), candidate('n1', 'new', -0.2, 9.5)], gain=1e-3)
    assert d['selected']['id'] == 'n1' and d['improved_over_fallback'] and d['fallback_id'] == 'wc'


def test_no_qualified_candidate_gives_an_explicit_blocked_status():
    d = select_release([candidate('wc', 'fallback', 0.0, 10.0, qualified=False), candidate('n1', 'new', -1.0, 1.0)],
                       gain=1e-3)
    assert d['status'] == 'blocked_no_qualified_candidate' and d['selected'] is None


def test_provisional_release_cannot_be_activated_even_by_an_explicit_click():
    release = {'status': 'provisional_extracellular_reference', 'activation_allowed': False}
    click = {'explicit': True, 'dataset_sha256': 'd', 'engine_context': 'e', 'contract_fingerprint': 'c'}
    assert activation_permitted(release, click)['allowed'] is False
    eligible = {'activation_allowed': True, 'eligibility': {'dataset_sha256': 'd', 'engine_context': 'e',
                                                             'contract_fingerprint': 'c'}}
    assert activation_permitted(eligible, click)['allowed'] is True
    assert activation_permitted(eligible, {**click, 'dataset_sha256': 'other'})['allowed'] is False
    assert activation_permitted(eligible, {**click, 'explicit': False})['allowed'] is False


# ------------------------------------------------ sealed inputs (read only)
def sealed():
    from run_vmax_requalification import historical_metrics
    f = json.loads((SOURCE / 'execution_design.json').read_text())
    obs = json.loads((SOURCE / 'observations.json').read_text())
    panel, references = historical_metrics(f, obs)
    return f, obs, panel, references


def test_registered_configuration_and_invariants():
    from run_extracellular_release import CODE, check_invariants
    f, *_ = sealed()
    check_invariants(CFG, f)
    assert CFG['release_objective_version'] == 'extracellular_first/2'
    assert CFG['release_objective']['minimum_utility_gain'] == 'log1p(0.001)'
    assert CFG['budget'] == {'new_ode_global': 240, 'restoration_and_replays': 80, 'search': 160,
                             'qualification_integrations': 12}
    for key in ('Km_changed', 'initial_changed'):
        bad = json.loads(json.dumps(CFG))
        bad['invariants'][key] = True
        with pytest.raises(ValueError):
            check_invariants(bad, f)
    assert not CFG['release']['activation_allowed'] and 'click' in CFG['release']['activation_policy']
    assert all(p.exists() for p in CODE)


def references_with_scores():
    from run_extracellular_release import finish_candidate, qualified_references
    from rbc_gem_audit import EXTERNAL_POOLS
    f, obs, panel, references = sealed()
    refs = qualified_references(CFG, f, panel, references)
    channels = extracellular_channels(panel['names'], EXTERNAL_POOLS)
    anchor = channel_mse(refs[0]['profiles']['strict']['prediction_mM'], panel, channels)
    units = unit_status(obs)
    for r in refs:
        finish_candidate(r, panel, channels, anchor, float('inf'), units=units)
    return f, obs, panel, references, refs, channels, units


def test_qualified_references_need_both_profiles():
    _, _, _, _, refs, _, units = references_with_scores()
    assert [r['id'] for r in refs] == ['working_centre', 'candidate35']
    for r in refs:
        assert r['qualified'] and set(r['scores']) == {'strict', 'ultrastrict'} and r['admissible']
        assert r['scores']['strict']['unit_status'] == units
    assert refs[0]['score']['primary'] == 0.0


def test_single_vector_export_with_unit_status_and_forbidden_activation(tmp_path):
    from run_extracellular_release import export_release
    from fla_vmax_requalification import exact_parameters
    f, obs, panel, references, refs, channels, units = references_with_scores()
    caps = focus_caps(refs[0]['profiles']['strict']['prediction_mM'], panel, ['EGLC', 'ELAC'],
                      f['numeric']['comparison_atol_mM'], f['numeric']['comparison_rtol'])
    decision = select_release(refs, gain=1e-3)
    export_release(tmp_path, CFG, f, obs, panel, channels, decision, references, 'ctx', [], units, caps, [])
    release = json.loads((tmp_path / 'release/provisional_extracellular_reference.json').read_text())
    chosen = decision['selected']
    p = exact_parameters(f, chosen['log_factors'])
    assert release['vmax_values'] == {k: p[k] for m in f['design']['groups'].values() for k in m}
    strict = chosen['profiles']['strict']['prediction_mM']
    for entry in release['species_by_date_strict']:
        i, j = panel['names'].index(entry['species']), panel['days'].index(entry['day'])
        assert entry['predicted'] == strict[i][j] and 'assumed' in entry['unit']
    assert release['unit_status']['status'] == 'assumed_mM_historical_model_convention'
    assert 'not transferable' in release['applicable_dataset']
    assert activation_permitted(release, {'explicit': True})['allowed'] is False
    assert not release['default_replacement'] and not release['biologically_validated']
    assert any('ATP/ADP' in item for item in release['limitations'])
    blocked = tmp_path / 'blocked'
    export_release(blocked, CFG, f, obs, panel, channels, {'status': 'blocked_source_drift', 'selected': None,
                   'reason': 'test'}, references, 'ctx', [], units, caps, [])
    receipt = json.loads((blocked / 'release/provisional_extracellular_reference.json').read_text())
    assert receipt['selected'] is None and receipt['activation_allowed'] is False


def test_restoration_directions_change_only_grouped_vmax():
    from run_extracellular_release import directions
    from fla_vmax_requalification import exact_parameters, within_original_box
    f, obs, panel, references, refs, channels, units = references_with_scores()
    trace = [json.loads(l) for l in (ROOT / 'output/corrected_vmax_2026_11_12/trace.jsonl').read_text().splitlines()]
    rows = {r['attempt']: r for r in trace}
    anchors = {'candidate35': rows[35], 'working_centre': rows[1]}
    anchor = channel_mse(rows[1]['prediction_mM'], panel, channels)
    built = directions(CFG, f, panel, channels, anchor, anchors, list(rows[35]['feasibility_guards']))
    assert [d['name'] for d in built] == CFG['restoration']['directions']
    lo, hi = np.log([f['design']['factor_bounds'][k] for k in f['design']['groups']]).T
    for d in built:
        x = np.array(d['anchor_row']['log_factors'])
        step = np.array(d['direction']) / max(np.max(np.abs(d['direction'])), 1e-300) * CFG['restoration']['radius_log']
        v = np.clip(x + step, lo, hi)
        assert within_original_box(f, v)
        p = exact_parameters(f, v)
        assert all(k.startswith('vmax_') for k in p if p[k] != f['parameters'][k])
        for a, b in (('vmax_VAK', 'vmax_VAK_rev'), ('vmax_VNDPK', 'vmax_VNDPK_rev')):
            assert np.isclose(p[a] / f['parameters'][a], p[b] / f['parameters'][b], rtol=1e-12, atol=0)


def test_module_imports_no_model_code():
    tree = ast.parse((ROOT / 'src/fla_extracellular_release.py').read_text(encoding='utf-8'))
    modules = {a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    modules |= {n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert modules <= {'ast', 'hashlib', 'json', 'numpy', 'pathlib', 'scipy'}
