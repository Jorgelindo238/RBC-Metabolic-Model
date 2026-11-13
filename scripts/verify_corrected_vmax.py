"""Independent recorded-array, guard, sensitivity and finalist checks. No ODE."""
import argparse
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from run_pgk_ndpk_profile import read, write, sha, verify_archive, scored
from run_vmax_requalification import historical_metrics, compare_files
from fla_vmax_requalification import exact_parameters, within_original_box
from fla_integration_diagnostics import inspect_support
from fla_agentic_vmax_replay import within


def verify(out, receipt):
    if receipt.exists():
        raise ValueError('Fresh receipt required')
    verify_archive(out)
    f, protocol = read(out / 'execution_design.json'), read(out / 'protocol.json')
    source = Path(protocol['source'])
    verify_archive(source)
    assert sha(source / 'manifest.json') == protocol['source_manifest_sha256']
    assert f == read(source / 'execution_design.json')
    assert read(out / 'observations.json') == read(source / 'observations.json')
    for path, digest in protocol['code_sha256'].items():
        assert sha(ROOT / path) == digest, 'Executable changed during campaign'
    panel, references = historical_metrics(f, read(out / 'observations.json'))
    import json
    trace = [json.loads(line) for line in (out / 'trace.jsonl').read_text().splitlines()]
    assert 1 <= len(trace) <= protocol['maximum_search_attempts']
    support_count = 0

    def check(folder, vector, profile):
        nonlocal support_count
        assert within_original_box(f, vector)
        p = read(folder / 'parameters.json')
        assert p == exact_parameters(f, vector)
        assert all(k.startswith('vmax_') for k in p if p[k] != f['parameters'][k])
        with np.load(folder / 'trajectory_evidence.npz') as z:
            assert np.array_equal(z['initial'], f['initial'])
            physical_ok = True
            for prefix in ('accepted', '', 'q4', 'q8'):
                tk, xk = (prefix + '_time', prefix + '_states') if prefix else ('time', 'states')
                if tk not in z:
                    physical_ok = False
                    continue
                assert np.min(z[tk]) >= 1 and np.max(z[tk]) <= 15
                report = inspect_support(z[tk], z[xk][:-1], z['pool_names'].tolist(), f['numeric']['negative_tolerance_mM'])
                physical_ok &= report['pass']
                assert np.array_equal(z[xk][-1], np.full(len(z[tk]), 7.2))
                support_count += len(z[tk])
            result = read(folder / 'result.json')
            if not result['valid']:
                return None
            assert physical_ok
            ids = np.searchsorted(z['time'], panel['days'])
            assert np.array_equal(z['time'][ids], panel['days'])
            prediction = z['states'][np.ix_([z['pool_names'].tolist().index(n) for n in panel['names']], ids)]
            assert np.array_equal(prediction, result['prediction_mM'])
        return scored(prediction, references[profile], panel, f)

    for row in trace:
        score = check(out / 'search' / f'{row["attempt"]:03d}', row['log_factors'], 'strict')
        if row['valid']:
            assert score is not None
            for key in ('absolute', 'feasibility_guards', 'reserved_guards_pass'):
                assert score[key] == row[key]
    sensitivity_entries = 0
    by_id = {r['attempt']: r for r in trace}
    for path in sorted(out.glob('sensitivity_round*.json')):
        sensitivity = read(path)
        anchor = by_id[sensitivity['anchor_attempt']]
        for key, entry in sensitivity['groups'].items():
            row = by_id[entry['attempt']]
            idx = list(f['design']['groups']).index(key)
            step = row['log_factors'][idx] - anchor['log_factors'][idx]
            assert step == entry['step_log']
            expected = (np.array(row['prediction_mM']) - anchor['prediction_mM']) / step
            assert np.array_equal(expected, entry['d_concentration_d_log_factor'])
            sensitivity_entries += 1
    selected = read(out / 'search_result.json')['selected']
    assert selected == by_id[selected['attempt']]
    summary = read(out / 'summary.json')
    recomputed = {}
    balance_count = 0
    for profile in ('strict', 'ultrastrict'):
        folder = out / 'validation' / profile
        score = check(folder, selected['log_factors'], profile)
        recomputed[profile] = score
        if score is None:
            continue
        for key in ('absolute', 'feasibility_guards', 'reserved_guards_pass'):
            assert score[key] == summary['validation'][profile][key]
        with np.load(folder / 'flux_evidence.npz') as z:
            ids = np.searchsorted(z['time'], z['boundaries'])
            delta = np.diff(z['states'][:113, ids], axis=1)
            assert within(delta, z['matrix'] @ z['executed8'], f['numeric'], 'quadrature').all()
            balance_count += delta.size
            for kind in ('raw', 'executed'):
                integrals = {}
                for order in (4, 8):
                    rates, weights, bins = z[f'q{order}_{kind}_rates'], z[f'q{order}_weights'], z[f'q{order}_intervals']
                    integrals[order] = np.array([np.sum(rates[:, bins == k] * weights[bins == k], axis=1)
                                                for k in range(len(z['boundaries'])-1)]).T
                    assert np.allclose(integrals[order], z[f'{kind}{order}'], atol=1e-12, rtol=1e-12)
                assert within(integrals[4], integrals[8], f['numeric'], 'quadrature').all()
    paired = compare_files(out / 'validation/strict/flux_evidence.npz', out / 'validation/ultrastrict/flux_evidence.npz', f)
    assert paired == summary['paired']
    admitted = paired['pass'] and all(s and s['reserved_guards_pass'] for s in recomputed.values())
    assert bool(admitted) == summary['admitted_under_inherited_guards']
    receipt.mkdir(parents=True)
    result = {'verified': True, 'search_attempts': len(trace), 'sensitivity_entries': sensitivity_entries,
              'support_points_checked': support_count, 'daily_balances': balance_count,
              'admitted_under_inherited_guards': bool(admitted), 'production_promoted': False,
              'source_manifest_sha256': sha(out / 'manifest.json')}
    write(receipt / 'verification.json', result)
    print(result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('out', type=Path)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    verify(args.out, args.receipt)
