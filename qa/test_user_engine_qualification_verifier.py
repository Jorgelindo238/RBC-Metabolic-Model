"""Independent verifier must reject tampered and numerically invalid evidence."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('engine_verifier', ROOT / 'scripts/verify_user_engine_qualification.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def write(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')


def seal(folder):
    write(folder / 'manifest.json', {p.relative_to(folder).as_posix(): verifier.digest(p)
          for p in folder.rglob('*') if p.is_file() and p.name != 'manifest.json'})


@pytest.fixture
def evidence(tmp_path):
    source, out = tmp_path / 'source', tmp_path / 'out'
    source.mkdir()
    out.mkdir()
    dates = [1., 4., 8., 11., 15.]
    states = np.array([[1., .9, .8, .7, .6], [7.2] * 5])
    write(source / 'execution_design.json', {'initial': [1., 7.2], 'kinetics': {'k': 1.}, 'numeric': {'hematocrit': .58}})
    write(source / 'cases.json', {'controls': [{'id': 'working_center', 'parameters': {'vmax': 1.}}]})
    write(out / 'engine_request.json', {'parameters': {'vmax': 1.}, 'kinetics': {'k': 1.}, 'negative_tolerance_mM': -1e-10})
    write(out / 'data_contract.json', {'geometry': {'hematocrit': .58},
          'initial_state': {'values': [{'value': 1.}, {'value': 7.2}]},
          'channels': [{'name': 'ATP', 'values': [1.] * 5}]})
    for profile in ('strict', 'ultrastrict'):
        old = source / 'controls/working_center/joint' / profile
        old.mkdir(parents=True)
        new = out / profile
        new.mkdir()
        arrays = {'pool_names': np.array(['ATP']), 'initial': np.array([1., 7.2]),
                  'time': dates, 'states': states}
        for prefix in ('accepted', 'q4', 'q8'):
            arrays[prefix + '_time'], arrays[prefix + '_states'] = dates, states
        for folder in (old, new):
            np.savez_compressed(folder / 'trajectory_evidence.npz', **arrays)
        write(new / 'result.json', {'status': 'completed_unqualified', 'activation_allowed': False,
              'biologically_validated': False, 'sample_times': dates,
              'states_at_samples': {'ATP': states[0].tolist(), 'PHI': states[1].tolist()},
              'measured_locked': {'ATP': 1.}, 'residuals': [
                  {'pool': 'ATP', 'time': dates[i], 'observed_mM': 1., 'residual_mM': float(states[0, i] - 1.)}
                  for i in range(1, 5)]})
    seal(source)
    write(out / 'protocol.json', {'source': str(source), 'source_manifest_sha256': verifier.digest(source / 'manifest.json'),
          'comparison_atol_mM': 1e-5, 'comparison_rtol': .01})
    seal(out)
    return out


def test_valid_fixture_is_software_parity_only(evidence):
    result = verifier.verify(evidence)
    assert result['historical_parity_pass']
    assert not result['general_user_engine_qualified']
    assert not result['biological_validation']


def test_unsealed_modification_rejected(evidence):
    (evidence / 'engine_request.json').write_text('{}')
    with pytest.raises(AssertionError, match='checksum'):
        verifier.verify(evidence)


def test_changed_parameter_rejected_even_if_resealed(evidence):
    p = evidence / 'engine_request.json'
    value = verifier.read(p)
    value['parameters']['vmax'] = 2.
    write(p, value)
    seal(evidence)
    with pytest.raises(AssertionError):
        verifier.verify(evidence)


@pytest.mark.parametrize('kind', ['negative_quadrature', 'trajectory_mismatch', 'early_time', 'initial_changed'])
def test_invalid_array_rejected(evidence, kind):
    p = evidence / 'strict/trajectory_evidence.npz'
    with np.load(p) as z:
        arrays = {k: z[k].copy() for k in z.files}
    if kind == 'negative_quadrature':
        arrays['q8_states'][0, 2] = -1e-4
    elif kind == 'trajectory_mismatch':
        arrays['states'][0, 2] = 5.
    elif kind == 'early_time':
        arrays['accepted_time'][0] = .5
    else:
        arrays['initial'][0] = 2.
    np.savez_compressed(p, **arrays)
    seal(evidence)
    with pytest.raises(AssertionError):
        verifier.verify(evidence)
