"""Independent array-level parity and physical-support verification; no integration."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_archive(folder):
    assert read(folder / 'manifest.json') == {
        p.relative_to(folder).as_posix(): digest(p) for p in folder.rglob('*')
        if p.is_file() and p.name != 'manifest.json'}, 'Archive checksum mismatch'


def verify(folder):
    check_archive(folder)
    protocol = read(folder / 'protocol.json')
    source = Path(protocol['source'])
    check_archive(source)
    assert digest(source / 'manifest.json') == protocol['source_manifest_sha256']
    design = read(source / 'execution_design.json')
    contract = read(folder / 'data_contract.json')
    request = read(folder / 'engine_request.json')
    original = next(c for c in read(source / 'cases.json')['controls'] if c['id'] == 'working_center')
    assert request['parameters'] == original['parameters']
    assert request['kinetics'] == design['kinetics']
    assert contract['geometry']['hematocrit'] == design['numeric']['hematocrit']
    assert [v['value'] for v in contract['initial_state']['values']] == design['initial']
    dates = np.array([1., 4., 8., 11., 15.])
    reports = {}
    for profile in ('strict', 'ultrastrict'):
        result = read(folder / profile / 'result.json')
        assert result['status'] == 'completed_unqualified'
        assert result['activation_allowed'] is False and result['biologically_validated'] is False
        actual = np.load(folder / profile / 'trajectory_evidence.npz', allow_pickle=False)
        old = np.load(source / 'controls/working_center/joint' / profile / 'trajectory_evidence.npz', allow_pickle=False)
        assert np.array_equal(actual['pool_names'], old['pool_names'])
        assert np.array_equal(actual['initial'], old['initial'])
        checks = {}
        for prefix in ('accepted', '', 'q4', 'q8'):
            tk, xk = (prefix + '_time', prefix + '_states') if prefix else ('time', 'states')
            t, x = actual[tk], actual[xk]
            assert np.isfinite(t).all() and np.isfinite(x).all() and t.min() >= 1 and t.max() <= 15
            assert np.all(np.diff(t) >= 0)
            assert x[:-1].min() >= request['negative_tolerance_mM']
            assert np.array_equal(x[-1], np.full(len(t), 7.2))
            checks[prefix or 'dense'] = {'count': len(t), 'minimum_mM': float(x[:-1].min())}
        idx = [int(np.flatnonzero(actual['time'] == t)[0]) for t in dates]
        refidx = [int(np.flatnonzero(old['time'] == t)[0]) for t in dates]
        a, b = actual['states'][:, idx], old['states'][:, refidx]
        allowed = protocol['comparison_atol_mM'] + protocol['comparison_rtol'] * np.abs(b)
        assert np.all(np.abs(a - b) <= allowed), 'Historical trajectory mismatch'
        assert np.array_equal(a[:, 0], actual['initial'])
        assert result['sample_times'] == dates.tolist()
        names = actual['pool_names'].tolist() + ['PHI']
        assert np.array_equal(a, np.array([result['states_at_samples'][n] for n in names]))
        for r in result['residuals']:
            assert r['time'] in dates[1:]
            ch = next(c for c in contract['channels'] if c['name'] == r['pool'])
            k = dates.tolist().index(r['time'])
            assert r['observed_mM'] == ch['values'][k]
            assert r['residual_mM'] == a[names.index(r['pool']), k] - r['observed_mM']
        reports[profile] = {'pass': True, 'compared_values': a.size,
            'maximum_absolute_difference_mM': float(np.max(np.abs(a - b))), 'supports': checks,
            'measured_J1_locked': len(result['measured_locked']), 'scored_points': len(result['residuals'])}
    return {'historical_parity_pass': True, 'biological_validation': False,
            'general_user_engine_qualified': False, 'profiles': reports}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    if args.receipt.exists():
        raise ValueError('Fresh verification receipt required')
    report = verify(args.folder)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
