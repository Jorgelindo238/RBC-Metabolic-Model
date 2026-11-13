"""Integrity and explicit defaults; injected RHS/solver, no integration."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import fla_effective_parameters as effective
import fla_user_engine_v2 as engine
from test_fla_user_engine import contract, request, NAMES, LAYOUT


def inputs():
    params = effective.resolve({'vmax_VHK': .1}, source='unit-test explicit seed')
    return contract(), request(parameters=params['values']), params


def prepared():
    c, r, p = inputs()
    return engine.prepare(c, r, pool_names=NAMES, compartments=LAYOUT, effective_parameters=p)


def fake_solver(rhs, span, initial, *, t_eval, **settings):
    return SimpleNamespace(success=True, t=np.array(t_eval), y=np.repeat(initial[:, None], len(t_eval), axis=1))


def test_resolution_preserves_overrides_and_dependent_defaults():
    overrides = {'vmax_VEADE': .123, 'km_AMP': .91, 'km_GTP': .32, 'km_LAC': .75, 'km_EGLC': 2.}
    p = effective.resolve(overrides, source='test')
    assert len(p['values']) == 283
    assert all(p['values'][k] == v for k, v in overrides.items())
    for alias, original in [('vmax_VEADE_fwd', 'vmax_VEADE'), ('vmax_VEADE_rev', 'vmax_VEADE'),
                            ('km_AMP_NT', 'km_AMP'), ('km_GTP_VADSS', 'km_GTP'),
                            ('hybrid_km_ELAC', 'km_LAC'), ('transport_gate_km_VEGLC', 'km_EGLC')]:
        assert p['values'][alias] == overrides[original]
        assert p['provenance'][alias]['origin'] == 'kernel_default'
    assert effective.validate(p)


@pytest.mark.parametrize('overrides', [{'typo': 1}, {'vmax_VHK': float('nan')}, {'vmax_VHK': True},
                                      {'vmax_VHK': '1'}, {'kinetic_family_VPK': 'teacher_curve_x'},
                                      {'kinetic_family_VPK': ' mm '}])
def test_invalid_parameter_input_refused(overrides):
    with pytest.raises(ValueError):
        effective.resolve(overrides, source='test')


@pytest.mark.parametrize('field', ['values', 'provenance', 'source_hashes', 'fingerprint'])
def test_effective_contract_tamper_rejected(field):
    p = inputs()[2]
    if field == 'fingerprint':
        p[field] = 'bad'
    else:
        p[field].clear()
    assert not effective.validate(p)


def test_missing_key_blocks_preparation():
    c, r, p = inputs()
    r = deepcopy(r)
    del r['parameters']['km_ATP']
    with pytest.raises(ValueError):
        engine.prepare(c, r, pool_names=NAMES, compartments=LAYOUT, effective_parameters=p)


def test_prepared_has_no_mutable_aliases():
    c, r, p = inputs()
    a = engine.prepare(c, r, pool_names=NAMES, compartments=LAYOUT, effective_parameters=p)
    c['channels'][0]['values'][0] = 99
    r['parameters']['vmax_VHK'] = 99
    a.payload['engine_request']['kinetics']['conductance'] = 99
    assert engine.validate(a)['valid']
    assert a.payload['engine_request']['parameters']['vmax_VHK'] == .1
    with pytest.raises(FrozenInstanceError):
        a.payload_json = '{}'


@pytest.mark.parametrize('field', ['data_contract', 'engine_request', 'pool_names', 'compartments',
                                  'effective_parameters', 'source_hashes', 'engine_version'])
def test_every_payload_component_is_fingerprinted(field):
    a = prepared()
    value = a.payload
    value[field] = None
    b = replace(a, payload_json=json.dumps(value))
    assert not engine.validate(b)['valid']


@pytest.mark.parametrize('value', [None, {}, 'bad', 5])
def test_malformed_prepared_never_raises(value):
    assert not engine.validate(value)['valid']
    assert engine.run(value, rhs_factory=None, solver=None)['status'] == 'invalid_prepared'


def test_semantics_rechecked_even_with_recomputed_hash():
    a = prepared()
    payload = a.payload
    payload['data_contract']['initial_state']['values'][0]['value'] = 5
    b = engine.PreparedRun(effective.canonical(payload), effective.fingerprint(payload))
    assert not engine.validate(b)['valid']


def test_run_remains_unqualified_and_does_not_optimize():
    result = engine.run(prepared(), rhs_factory=lambda **k: lambda t, x: x * 0, solver=fake_solver)
    assert result['status'] == 'completed_unqualified'
    assert not result['activation_allowed']
    assert result['parameters_unchanged']


@pytest.mark.parametrize('target', ['parameters', 'kinetics'])
def test_rhs_internal_copy_mutation_is_rejected(target):
    def factory(**kwargs):
        rhs = SimpleNamespace(parameters=deepcopy(kwargs['parameters']), kinetics=deepcopy(kwargs['kinetics']))
        getattr(rhs, target)[next(iter(getattr(rhs, target)))] = 123.
        return rhs
    result = engine.run(prepared(), rhs_factory=factory, solver=fake_solver)
    assert result['status'] == 'contract_violation'


def test_bad_factory_is_rejected_before_solver():
    def factory(**kwargs):
        kwargs['kinetics']['conductance'] = float('nan')
        return lambda t, x: x
    def forbidden(*args, **kwargs):
        pytest.fail('Solver must not run after factory contract violation')
    assert engine.run(prepared(), rhs_factory=factory, solver=forbidden)['status'] == 'contract_violation'


def test_mutation_during_solver_is_rejected():
    def factory(**kwargs):
        return SimpleNamespace(parameters=deepcopy(kwargs['parameters']), kinetics=deepcopy(kwargs['kinetics']))
    def solver(rhs, *args, **kwargs):
        rhs.parameters['km_ATP'] = float('nan')
        return fake_solver(rhs, *args, **kwargs)
    assert engine.run(prepared(), rhs_factory=factory, solver=solver)['status'] == 'contract_violation'


def test_source_drift_is_rejected(monkeypatch):
    a = prepared()
    monkeypatch.setattr(engine, '_source_hashes', lambda: {'different': 'version'})
    assert not engine.validate(a)['valid']


@pytest.mark.parametrize('section,key,value', [
    ('kinetics', 'conductance', .09), ('solver', 'rtol', 1e-9),
    (None, 'network_mode', 'redox'), (None, 'threshold_mM', .0001),
])
def test_run_definition_changes_fingerprint(section, key, value):
    c, r, p = inputs()
    a = engine.prepare(c, r, pool_names=NAMES, compartments=LAYOUT, effective_parameters=p)
    (r[section] if section else r)[key] = value
    b = engine.prepare(c, r, pool_names=NAMES, compartments=LAYOUT, effective_parameters=p)
    assert a.fingerprint != b.fingerprint


def test_provenance_and_origin_change_fingerprint():
    c, r, p = inputs()
    a = engine.prepare(c, r, pool_names=NAMES, compartments=LAYOUT, effective_parameters=p)
    c['time']['origin']['description'] = 'different laboratory origin'
    c['geometry']['provenance']['source'] = 'different record'
    b = engine.prepare(c, r, pool_names=NAMES, compartments=LAYOUT, effective_parameters=p)
    assert a.fingerprint != b.fingerprint
