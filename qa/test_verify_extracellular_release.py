"""Adversarial tests of the extracellular release VERIFIER (no ODE, synthetic evidence).

Each tampering must be rejected from the evidence itself, whatever success
booleans a campaign recorded (content-level checks are independent of resealed
manifests).
"""
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
from verify_extracellular_release import (Components, export_verdict, flux_verdict, incumbent_verdict,
                                          jacobian_verdict, seed_verdict, trajectory_verdict)
from fla_extracellular_release import channel_mse, focus_caps

DAYS = [4, 8, 11, 15]


# ------------------------------------------------------------- supports
def evidence(q8_negative=False, drop=None):
    t = np.array([1.0, 4.0, 8.0, 11.0, 15.0])
    states = np.vstack([np.linspace(1.0, 0.5, 5), np.linspace(2.0, 1.0, 5), np.full(5, 7.2)])
    z = {'initial': np.array([1.0, 2.0]), 'pool_names': np.array(['A', 'B'])}
    for prefix in ('accepted', '', 'q4', 'q8'):
        tk, xk = (prefix + '_time', prefix + '_states') if prefix else ('time', 'states')
        z[tk], z[xk] = t.copy(), states.copy()
    if q8_negative:
        z['q8_time'] = np.array([1.0, 9.0, 15.0])
        z['q8_states'] = np.array([[1.0, -1e-3, 0.5], [2.0, 1.5, 1.0], [7.2, 7.2, 7.2]])
    if drop:
        del z[drop + '_time'], z[drop + '_states']
    return z


def result(valid=True):
    prediction = np.vstack([np.linspace(1.0, 0.5, 5)[1:], np.linspace(2.0, 1.0, 5)[1:]])
    return {'valid': True, 'prediction_mM': prediction.tolist()} if valid else {'valid': False, 'error': 'gate'}


KW = dict(initial=[1.0, 2.0], negative_tolerance=-1e-10, days=DAYS, names=('A', 'B'))


def test_clean_supports_accept_a_valid_attempt():
    verdict = trajectory_verdict(result(), evidence(), **KW)
    assert verdict['class'] == 'accepted_valid' and verdict['points'] == 20
    assert set(verdict['supports'].values()) == {'pass'}


def test_negative_q8_support_rejects_despite_positive_dated_predictions():
    with pytest.raises(AssertionError, match='physical support'):
        trajectory_verdict(result(), evidence(q8_negative=True), **KW)
    assert trajectory_verdict(result(valid=False), evidence(q8_negative=True), **KW)['class'] == 'rejected_physical'


def test_missing_support_or_evidence_cannot_back_a_valid_result():
    with pytest.raises(AssertionError):
        trajectory_verdict(result(), evidence(drop='q4'), **KW)
    with pytest.raises(AssertionError):
        trajectory_verdict(result(), None, **KW)
    assert trajectory_verdict(result(valid=False), None, **KW)['class'] == 'rejected_no_evidence'


def test_changed_initial_state_or_ph_is_rejected():
    z = evidence()
    z['initial'] = np.array([1.0, 2.1])
    with pytest.raises(AssertionError, match='initial'):
        trajectory_verdict(result(), z, **KW)
    z = evidence()
    z['q4_states'][-1, 2] = 7.3
    with pytest.raises(AssertionError, match='pH'):
        trajectory_verdict(result(), z, **KW)


# ------------------------------------------------------------ Jacobians
A = np.array([[2.0, -1.0], [0.5, 3.0], [1.0, 1.0]])


def row(attempt, x, valid=True):
    return {'attempt': attempt, 'log_factors': list(map(float, x)), 'valid': valid}


def vector(r):
    return A @ np.array(r['log_factors'])


def honest_record():
    x = np.array([0.1, -0.2])
    rows = {1: row(1, x)}
    record = {'anchor_attempt': 1, 'anchor_vector': x.tolist(), 'free': [0, 1], 'columns': {}, 'check': {},
              'jacobian': np.zeros((3, 2))}
    for i, attempt in ((0, 2), (1, 3)):
        v = x.copy()
        v[i] = x[i] + 0.006
        rows[attempt] = row(attempt, v)
        dx = v[i] - x[i]
        record['columns'][str(i)] = {'attempt': attempt, 'step_log': dx}
        record['jacobian'][:, i] = (vector(rows[attempt]) - vector(rows[1])) / dx
    v = x.copy()
    v[0] = x[0] + 0.003
    rows[4] = row(4, v)
    d3 = (vector(rows[4])[0] - vector(rows[1])[0]) / (v[0] - x[0])
    record['check']['0'] = {'attempt': 4, 'step_log': v[0] - x[0], 'passed': True,
                            'd006': float(record['jacobian'][0, 0]), 'd003': float(d3)}
    record['jacobian'] = record['jacobian'].tolist()
    return record, rows


def resolver(rows):
    by_vec = {tuple(r['log_factors']): r for r in rows.values()}

    def resolve(ref, by_vector=False):
        if by_vector:
            return by_vec.get(tuple(map(float, ref)))
        assert ref in rows, 'unknown'
        return rows[ref]
    return resolve


SPEC = {'difference_step_log': 0.006, 'check_step_log': 0.003, 'check_rtol': 0.25, 'check_atol': 1e-6}
UPPER = np.array([1.0, 1.0])


def test_honest_jacobian_is_rebuilt():
    record, rows = honest_record()
    assert jacobian_verdict(record, resolver(rows), vector, SPEC, UPPER) == 2


def test_falsified_and_resealed_jacobian_column_is_rejected():
    record, rows = honest_record()
    record['jacobian'][1][0] *= 1.001
    with pytest.raises(AssertionError, match='column'):
        jacobian_verdict(record, resolver(rows), vector, SPEC, UPPER)


def test_falsified_probe_step_is_rejected():
    record, rows = honest_record()
    rows[2]['log_factors'][0] = 0.1 + 0.007
    record['columns']['0']['step_log'] = rows[2]['log_factors'][0] - 0.1
    with pytest.raises(AssertionError, match='step'):
        jacobian_verdict(record, resolver(rows), vector, SPEC, UPPER)


def test_moved_companion_coordinate_is_rejected():
    record, rows = honest_record()
    rows[2]['log_factors'][1] += 1e-9
    with pytest.raises(AssertionError, match='companion'):
        jacobian_verdict(record, resolver(rows), vector, SPEC, UPPER)


def test_unjustified_reverse_step_is_rejected():
    record, rows = honest_record()
    x = np.array([0.1, -0.2])
    v = x.copy()
    v[0] = x[0] - 0.006
    rows[2] = row(2, v)
    record['columns']['0']['step_log'] = v[0] - x[0]
    record['jacobian'] = np.array(record['jacobian'])
    record['jacobian'][:, 0] = (vector(rows[2]) - vector(rows[1])) / (v[0] - x[0])
    record['jacobian'] = record['jacobian'].tolist()
    record['check'] = {}
    with pytest.raises(AssertionError, match='reverse'):
        jacobian_verdict(record, resolver(rows), vector, SPEC, UPPER)


def test_falsified_half_step_check_is_rejected():
    record, rows = honest_record()
    record['check']['0']['d003'] *= 1.5
    with pytest.raises(AssertionError, match='half-step'):
        jacobian_verdict(record, resolver(rows), vector, SPEC, UPPER)


def test_frozen_column_with_values_is_rejected():
    record, rows = honest_record()
    del record['columns']['1']
    with pytest.raises(AssertionError, match='frozen'):
        jacobian_verdict(record, resolver(rows), vector, SPEC, UPPER)


# ------------------------------------------------------------- flux
def flux_evidence():
    t = np.linspace(0.0, 2.0, 9)
    boundaries = np.array([0.0, 1.0, 2.0])
    states = np.vstack([1.0 + t, np.full_like(t, 2.0)])
    z = {'time': t, 'boundaries': boundaries, 'states': states, 'matrix': np.array([[1.0], [0.0]])}
    for order in (4, 8):
        bins = np.repeat([0, 1], order)
        z[f'q{order}_intervals'] = bins
        z[f'q{order}_weights'] = np.full(2 * order, 1.0 / order)
        for kind in ('raw', 'executed'):
            z[f'q{order}_{kind}_rates'] = np.ones((1, 2 * order))
            z[f'{kind}{order}'] = np.array([[1.0, 1.0]])
    return z


NUMERIC = {'quadrature_atol_mM': 1e-6, 'quadrature_rtol': 1e-3}


def test_consistent_flux_evidence_counts_new_balances():
    assert flux_verdict(flux_evidence(), NUMERIC, pools=2) == 4


def test_falsified_stored_integral_is_rejected():
    z = flux_evidence()
    z['executed8'] = np.array([[1.0, 1.2]])
    with pytest.raises(AssertionError):
        flux_verdict(z, NUMERIC, pools=2)


def test_falsified_daily_balance_is_rejected():
    z = flux_evidence()
    z['states'] = z['states'].copy()
    z['states'][0, -1] += 0.01
    with pytest.raises(AssertionError, match='balance'):
        flux_verdict(z, NUMERIC, pools=2)


def test_falsified_rates_break_the_order4_order8_agreement():
    z = flux_evidence()
    z['q4_raw_rates'] = np.full((1, 8), 1.1)
    z['raw4'] = np.array([[1.1, 1.1]])
    with pytest.raises(AssertionError, match='4/8'):
        flux_verdict(z, NUMERIC, pools=2)


# ------------------------------------------------------ seeds, incumbent
def toy_panel():
    return {'names': ('EGLC', 'ELAC'), 'days': DAYS,
            'target': np.array([[10.0, 9.0, 8.0, 7.0], [1.0, 2.0, 3.0, 4.0]]),
            'bands': np.array([[1.0] * 4, [0.5] * 4])}


def seed_components():
    panel = toy_panel()
    fallback = panel['target'] + 0.1
    caps = focus_caps(fallback, panel, ['EGLC', 'ELAC'], 1e-5, 0.01)
    return Components(panel, ['EGLC', 'ELAC'], channel_mse(fallback, panel, ['EGLC', 'ELAC']), None, [],
                      np.zeros(0), np.ones(0), 1e9, caps), fallback


def seed(prediction, x):
    return {'attempt': 7, 'group': 'restoration', 'stage': 'restoration', 'valid': True,
            'reserved_guards_pass': True, 'log_factors': x, 'prediction_mM': np.asarray(prediction).tolist(),
            'feasibility_guards': {}}


def test_focus_inadmissible_seed_is_rejected_even_if_guard_feasible():
    components, fallback = seed_components()
    lo, hi = np.array([-1.0, -1.0]), np.array([1.0, 1.0])
    good = seed(fallback, [0.5, 0.5])
    assert seed_verdict([good], [np.zeros(2)], components, lo, hi, 0.01) == 1
    bad = seed(fallback + np.array([[0.5] * 4, [0.0] * 4]), [0.5, 0.5])  # EGLC worse than the cap
    with pytest.raises(AssertionError, match='focus'):
        seed_verdict([bad], [np.zeros(2)], components, lo, hi, 0.01)
    with pytest.raises(AssertionError, match='separated'):
        seed_verdict([seed(fallback, [0.001, 0.0])], [np.zeros(2)], components, lo, hi, 0.01)
    with pytest.raises(AssertionError, match='guards'):
        seed_verdict([{**good, 'reserved_guards_pass': False}], [np.zeros(2)], components, lo, hi, 0.01)


class Stub:
    def score(self, r):
        return {'primary': r['u']}

    def admissible(self, r):
        return bool(r['valid'] and r['ok'])


def test_incumbent_rules_are_recomputed_from_rows():
    rows = {1: {'valid': True, 'ok': True, 'u': 0.0}, 2: {'valid': True, 'ok': False, 'u': -5.0},
            3: {'valid': True, 'ok': True, 'u': -0.5}}
    events = [{'event': 'objective', 'start': 's', 'attempt': 1, 'valid': True, 'admissible': True, 'primary': 0.0,
               'start_best_updated': True, 'incumbent_updated': True},
              {'event': 'objective', 'start': 's', 'attempt': 2, 'valid': True, 'admissible': False, 'primary': -5.0,
               'start_best_updated': False, 'incumbent_updated': False},
              {'event': 'objective', 'start': 's', 'attempt': 3, 'valid': True, 'admissible': True, 'primary': -0.5,
               'start_best_updated': True, 'incumbent_updated': True}]
    assert incumbent_verdict(events, rows.get, Stub(), 1e-3) == 2
    forged = json.loads(json.dumps(events))
    forged[1].update(admissible=True, incumbent_updated=True, start_best_updated=True)
    with pytest.raises(AssertionError):
        incumbent_verdict(forged, rows.get, Stub(), 1e-3)


# ------------------------------------------------------------- export
def test_tampered_exported_vmax_is_rejected():
    from fla_vmax_requalification import exact_parameters
    from run_extracellular_release import canonical_sha
    f = json.loads((ROOT / 'output/vmax_requalification_2026_11_09/execution_design.json').read_text())
    selected = json.loads((ROOT / 'output/corrected_vmax_2026_11_12/search_result.json').read_text())['selected']
    vector = selected['log_factors']
    p = exact_parameters(f, vector)
    members = [k for m in f['design']['groups'].values() for k in m]
    release = {'log_group_factors': dict(zip(f['design']['groups'], vector)),
               'vmax_values': {k: p[k] for k in members}, 'parameters_sha256': canonical_sha(p),
               'non_vmax_parameters_changed': False}
    assert export_verdict(release, f, vector) == 17
    tampered = json.loads(json.dumps(release))
    tampered['vmax_values']['vmax_VPK'] *= 1.01
    with pytest.raises(AssertionError, match='vmax_VPK'):
        export_verdict(tampered, f, vector)
    extra = json.loads(json.dumps(release))
    extra['vmax_values']['km_ATP_HK'] = 1.0
    with pytest.raises(AssertionError, match='set'):
        export_verdict(extra, f, vector)
    shifted = json.loads(json.dumps(release))
    shifted['log_group_factors']['PK'] += 1e-6
    with pytest.raises(AssertionError, match='log factors'):
        export_verdict(shifted, f, vector)
