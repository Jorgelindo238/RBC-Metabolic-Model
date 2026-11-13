"""Explicit, source-pinned parameter resolution. No kernel import or execution."""
import ast
import hashlib
import json
import math
from pathlib import Path

SRC = Path(__file__).resolve().parent
SOURCES = ('equadiff_brodbar.py', 'fla_joint_calibration.py', 'fla_agentic_gem_correction.py',
           'rbc_distinct_volume_transport.py', 'rbc_glut_only_transport.py', 'reaction_positivity.py',
           'fla_effective_parameters.py')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def source_hashes():
    return {name: hashlib.sha256((SRC / name).read_bytes()).hexdigest() for name in SOURCES}


def catalogue():
    tree = ast.parse((SRC / 'equadiff_brodbar.py').read_text(encoding='utf-8-sig'))
    entries = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in ('_get_param', '_get_param_str')):
            continue
        if len(node.args) != 3 or not isinstance(node.args[1], ast.Constant):
            raise ValueError('Unreviewed dynamic parameter access')
        key = node.args[1].value
        item = {'kind': node.func.id, 'expression': ast.unparse(node.args[2]), 'node': node.args[2],
                'lines': [node.lineno]}
        if key in entries:
            prior = entries[key]
            if (prior['kind'], prior['expression']) != (item['kind'], item['expression']):
                raise ValueError(f'Conflicting defaults for {key}')
            prior['lines'].append(node.lineno)
        else:
            entries[key] = item
    return entries


def resolve(overrides, *, source):
    """Caller must explicitly request expansion; supplied values are never altered.

    Includes inactive-branch parameters, not a claim of identifiability.
    Hardcoded expression constants remain pinned by source hashes, not fitted.
    """
    if not isinstance(overrides, dict) or not isinstance(source, str) or not source.strip():
        raise ValueError('Parameter mapping and provenance source required')
    entries = catalogue()
    if set(overrides) - set(entries):
        raise ValueError(f'Unknown parameters: {sorted(set(overrides) - set(entries))}')
    values, provenance, visiting = {}, {}, set()
    aliases = {'km_eglc': 'km_EGLC', 'km_lac': 'km_LAC'}

    def expression(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return get(aliases.get(node.id, node.id))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == '_get_param':
            return get(node.args[1].value)
        raise ValueError(f'Unreviewed default expression: {ast.unparse(node)}')

    def get(key):
        if key in values:
            return values[key]
        if key in visiting or key not in entries:
            raise ValueError(f'Cyclic or unknown default dependency: {key}')
        visiting.add(key)
        entry = entries[key]
        value = overrides[key] if key in overrides else expression(entry['node'])
        if entry['kind'] == '_get_param_str':
            if not isinstance(value, str) or not value or value != value.strip() or value.startswith('teacher_curve'):
                raise ValueError(f'Invalid or teacher-forced string parameter: {key}')
        elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f'Finite numeric parameter required: {key}')
        values[key] = value
        provenance[key] = {'origin': 'supplied' if key in overrides else 'kernel_default',
                           'source': source if key in overrides else 'equadiff_brodbar.py',
                           'lines': entry['lines'], 'default_expression': entry['expression']}
        visiting.remove(key)
        return value

    for key in entries:
        get(key)
    body = {'version': 'effective-parameters/1', 'values': values, 'provenance': provenance,
            'source_hashes': source_hashes(), 'input_source': source,
            'input_overrides': overrides.copy(), 'hardcoded_constants_policy': 'pinned_source_not_fitted'}
    return {**body, 'fingerprint': fingerprint(body)}


def validate(contract):
    """Fail closed on missing entries, provenance edits or source drift."""
    try:
        body = {k: v for k, v in contract.items() if k != 'fingerprint'}
        if fingerprint(body) != contract['fingerprint']:
            return False
        expected = resolve(contract['input_overrides'], source=contract['input_source'])
        return canonical(expected) == canonical(contract)
    except (TypeError, ValueError, KeyError, AttributeError, OSError, RecursionError):
        return False
