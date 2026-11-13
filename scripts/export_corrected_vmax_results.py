"""Export derived sensitivities/candidate tables outside the sealed campaign."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def execute(source, out):
    if out.exists():
        raise ValueError('Fresh analysis directory required')
    design = read(source / 'execution_design.json')
    result = read(source / 'search_result.json')
    start, selected = result['start'], result['selected']
    out.mkdir(parents=True)
    with (out / 'sensitivities.csv').open('x', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['round', 'anchor_attempt', 'group', 'pool', 'day', 'step_log', 'd_mM_d_log_factor'])
        for path in sorted(source.glob('sensitivity_round*.json')):
            s = read(path)
            for group, entry in s['groups'].items():
                for i, pool in enumerate(s['pool_names']):
                    for j, day in enumerate(s['days']):
                        writer.writerow([path.stem, s['anchor_attempt'], group, pool, day, entry['step_log'],
                                         entry['d_concentration_d_log_factor'][i][j]])
    before = read(source / 'search' / f'{start["attempt"]:03d}' / 'parameters.json')
    after = read(source / 'search' / f'{selected["attempt"]:03d}' / 'parameters.json')
    with (out / 'selected_vmax.csv').open('x', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['group', 'parameter', 'working_center', 'candidate', 'change_percent'])
        for group, names in design['design']['groups'].items():
            for name in names:
                writer.writerow([group, name, before[name], after[name], 100 * (after[name] / before[name] - 1)])
    with (out / 'concentrations_by_day.csv').open('x', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['pool', 'day', 'observed_mM', 'working_center_mM', 'candidate_mM'])
        s = read(source / 'sensitivity_round1.json')
        observations = read(source / 'observations.json')
        for i, pool in enumerate(s['pool_names']):
            for j, day in enumerate(s['days']):
                writer.writerow([pool, day, observations['values'][pool][observations['time'].index(day)],
                                 start['prediction_mM'][i][j], selected['prediction_mM'][i][j]])
    manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()}
    manifest['source_manifest_sha256'] = hashlib.sha256((source / 'manifest.json').read_bytes()).hexdigest()
    (out / 'provenance.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'Exported sensitivities, 17 Vmax and 55 dated channels to {out}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    execute(args.source, args.out)
