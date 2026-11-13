"""Expand archived defaults and check fixed-state rate parity, without integration."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from fla_effective_parameters import resolve, source_hashes
from fla_agentic_gem_correction import GemCorrectionRHS
from qualify_user_engine import verify_manifest, read, write, sha


def execute(out):
    if out.exists():
        raise ValueError('Fresh output directory required')
    source = ROOT / 'output/vmax_requalification_2026_11_09'
    verify_manifest(source)
    f = read(source / 'execution_design.json')
    params = next(c['parameters'] for c in read(source / 'cases.json')['controls'] if c['id'] == 'working_center')
    contract = resolve(params, source=str(source / 'cases.json') + '#working_center')
    rows = []
    for backend in ('joint', 'full'):
        kwargs = {'mode': f['structure_modes'][f['temporal']['network']], 'backend': backend,
                  'hematocrit': f['numeric']['hematocrit'], 'threshold': f['numeric']['availability_threshold_mM']}
        old = GemCorrectionRHS(params, f['kinetics'], **kwargs)
        new = GemCorrectionRHS(contract['values'], f['kinetics'], **kwargs)
        for profile in ('strict', 'ultrastrict'):
            with np.load(source / 'controls/working_center/joint' / profile / 'trajectory_evidence.npz') as z:
                for day in (1., 4., 8., 11., 15.):
                    state = z['states'][:, np.flatnonzero(z['time'] == day)[0]]
                    before, after = old.rates(day, state), new.rates(day, state)
                    checks = {name: bool(np.array_equal(a, b)) for name, a, b in
                              zip(('raw', 'executed', 'availability'), before, after)}
                    checks['derivative'] = bool(np.array_equal(old(day, state), new(day, state)))
                    if not all(checks.values()):
                        raise ValueError(f'Parameter expansion changed dynamics: {backend}/{profile}/{day}')
                    rows.append({'backend': backend, 'profile': profile, 'day': day, **checks})
    verify_manifest(source)
    assert contract['source_hashes'] == source_hashes()
    out.mkdir(parents=True)
    write(out / 'effective_parameters.json', contract)
    write(out / 'receipt.json', {'fixed_state_parity_pass': True, 'checkpoints': rows,
          'supplied_count': len(params), 'explicit_count': len(contract['values']),
          'new_integrations': 0, 'optimization': False, 'biological_validation': False,
          'source_manifest_sha256': sha(source / 'manifest.json'), 'source_hashes': source_hashes(),
          'script_sha256': sha(Path(__file__))})
    write(out / 'manifest.json', {p.name: sha(p) for p in out.iterdir() if p.is_file()})
    print(f'PASS: {len(params)} overrides -> {len(contract["values"])} explicit entries; {len(rows)} fixed-state checkpoints')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT / 'output/effective_parameters_2026_11_12')
    execute(parser.parse_args().out)
