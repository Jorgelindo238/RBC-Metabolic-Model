"""Replay the historical centre through the successor; never optimize or promote."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import scipy
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from fla_user_engine import prepare, run, default_model_layout, default_rhs_factory
from fla_stepper_diagnostics import record_stepper
from fla_bounded_jacobian import BoundedJacobian


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_manifest(folder):
    expected = read(folder / 'manifest.json')
    actual = {p.relative_to(folder).as_posix(): sha(p) for p in folder.rglob('*')
              if p.is_file() and p != folder / 'manifest.json'}
    if actual != expected:
        raise ValueError('Source archive manifest mismatch')


def build_inputs(source):
    f, obs = read(source / 'execution_design.json'), read(source / 'observations.json')
    case = next(c for c in read(source / 'cases.json')['controls'] if c['id'] == 'working_center')
    # Explicit historical structural convention; keep archived overrides identical.
    names, layout = default_model_layout('biochemical_transfer')
    days = [1., 4., 8., 11., 15.]
    channels = [{'name': n, 'compartment': layout[n], 'kind': 'absolute', 'unit': 'mM',
                 'values': [values[obs['time'].index(t)] for t in days]}
                for n, values in obs['values'].items()]
    contract = {
        'schema_version': 'airbc.user_calibration_data/1',
        'dataset': {'dataset_id': 'historical-bordbar-curated-comparator', 'cohort_id': 'historical-only',
                    'subject': {'kind': 'declared_group', 'id': 'unknown-donor-curated-table'}},
        'time': {'unit': 'day', 'origin': {'kind': 'historical_storage_day'}, 'points': days},
        'geometry': {'hematocrit': f['numeric']['hematocrit'], 'provenance': {
            'kind': 'borrowed', 'source': f['numeric']['hematocrit_status']}},
        'channels': channels,
        'initial_state': {'policy': 'user_declared_table', 'time': 1., 'values': [
            {'name': n, 'value': value, 'unit': 'pH' if n == 'PHI' else 'mM',
             'compartment': layout[n], 'status': 'measured' if n in obs['values'] else 'latent_declared',
             'source': str(source / ('observations.json' if n in obs['values'] else 'execution_design.json'))
                       + ('; historical comparator, biological provenance unresolved' if n not in obs['values'] else '')}
            for n, value in zip(names, f['initial'])]}}
    request = {'parameters': case['parameters'], 'parameters_source': str(source / 'cases.json'),
               'kinetics': f['kinetics'], 'network_mode': f['structure_modes'][f['temporal']['network']],
               'backend': 'joint', 'threshold_mM': f['requalification_plan']['threshold_mM'],
               'negative_tolerance_mM': f['numeric']['negative_tolerance_mM']}
    return f, contract, request, names, layout


def execute(source, out):
    if out.exists():
        raise ValueError('Fresh output directory required; no archive overwrites')
    verify_manifest(source)
    f, contract, request, names, layout = build_inputs(source)
    plan = f['requalification_plan']
    if scipy.__version__ != plan['scipy_version']:
        raise ValueError('Runtime differs from sealed reference')
    prepared = {}
    for profile, settings in plan['profiles'].items():
        prepared[profile] = prepare(contract, {**request, 'solver': {'method': plan['method'], **settings}},
                                    pool_names=names, compartments=layout)
    out.mkdir(parents=True)
    write(out / 'data_contract.json', contract)
    write(out / 'engine_request.json', request)
    write(out / 'protocol.json', {'source': str(source), 'profiles': plan['profiles'],
        'jacobian_minimum_step_mM': plan['jacobian_minimum_step_mM'], 'scipy_version': scipy.__version__,
        'comparison_atol_mM': f['numeric']['comparison_atol_mM'], 'comparison_rtol': f['numeric']['comparison_rtol'],
        'method': plan['method'], 'optimization': False, 'promotion': False,
        'scope': 'historical comparator parity only; not biological validation',
        'parameter_completeness': 'archived overrides; remaining kernel defaults are not yet explicit',
        'sam_layout': 'biochemical_transfer (historical kernel convention)',
        'source_manifest_sha256': sha(source / 'manifest.json'),
        'code_sha256': {str(p.relative_to(ROOT)): sha(p) for p in [Path(__file__),
            ROOT / 'scripts/verify_user_engine_qualification.py', ROOT / 'src/fla_user_engine.py',
            ROOT / 'src/fla_stepper_diagnostics.py', ROOT / 'src/fla_bounded_jacobian.py']}})
    for profile, p in prepared.items():
        folder = out / profile
        folder.mkdir()

        def solver(rhs, t_span, y0, *, t_eval, method, **settings):
            # This adapter qualifies only the archived J1 recipe, not arbitrary origins.
            if t_span != (1., 15.):
                raise ValueError('Historical qualification adapter requires J1-J15')
            jac = BoundedJacobian(rhs, minimum_step=plan['jacobian_minimum_step_mM'][profile])
            arrays, diagnostics = record_stepper(rhs, y0, t_span[1], t_eval,
                {**settings, 'jac': jac}, p.negative_tolerance_mM, method)
            diagnostics['bounded_jacobian'] = jac.diagnostics()
            np.savez_compressed(folder / 'trajectory_evidence.npz', **arrays)
            write(folder / 'diagnostics.json', diagnostics)
            idx = [int(np.flatnonzero(arrays['time'] == t)[0]) for t in t_eval
                   if np.any(arrays['time'] == t)]
            return SimpleNamespace(success=diagnostics['concentration_gate_pass'],
                message='recorded physical-support gate', t=arrays['time'][idx], y=arrays['states'][:, idx])

        print(f'Starting {profile} historical replay', flush=True)
        with threadpool_limits(1):
            result = run(p, rhs_factory=default_rhs_factory, solver=solver)
        write(folder / 'result.json', result)
        print(f'{profile}: {result["status"]}', flush=True)
    verify_manifest(source)
    write(out / 'manifest.json', {p.relative_to(out).as_posix(): sha(p) for p in out.rglob('*') if p.is_file()})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=ROOT / 'output/vmax_requalification_2026_11_09')
    parser.add_argument('--out', type=Path, default=ROOT / 'output/user_engine_qualification_2026_11_12')
    args = parser.parse_args()
    execute(args.source, args.out)
