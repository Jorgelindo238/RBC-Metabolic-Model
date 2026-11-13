"""Integrity envelope around the preserved v1 engine. Opt-in, not qualified."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import fla_user_engine as legacy
from fla_effective_parameters import canonical, fingerprint, validate as validate_parameters

ENGINE_VERSION = 'fla-user-engine-2026.11.12-v2'


@dataclass(frozen=True)
class PreparedRun:
    # Canonical JSON is immutable; property access returns a detached copy.
    payload_json: str
    fingerprint: str

    @property
    def payload(self):
        return json.loads(self.payload_json)


def _source_hashes():
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__), Path(legacy.__file__))}


def _prepare_payload(payload):
    if payload['engine_version'] != ENGINE_VERSION or payload['source_hashes'] != _source_hashes():
        raise ValueError('Engine version or source changed')
    effective = payload['effective_parameters']
    if not validate_parameters(effective):
        raise ValueError('Incomplete, altered or stale effective parameter contract')
    request = payload['engine_request']
    if canonical(request['parameters']) != canonical(effective['values']):
        raise ValueError('Request parameters differ from effective parameter contract')
    return legacy.prepare(payload['data_contract'], request,
                          pool_names=payload['pool_names'], compartments=payload['compartments'])


def prepare(data_contract, engine_request, *, pool_names, compartments, effective_parameters):
    payload = {'engine_version': ENGINE_VERSION, 'data_contract': data_contract,
               'engine_request': engine_request, 'pool_names': list(pool_names),
               'compartments': compartments, 'effective_parameters': effective_parameters,
               'source_hashes': _source_hashes()}
    # Serialize before validating: neither the caller nor returned properties alias inputs.
    encoded = canonical(payload)
    _prepare_payload(json.loads(encoded))
    return PreparedRun(encoded, fingerprint(payload))


def validate(prepared):
    try:
        if not isinstance(prepared, PreparedRun):
            raise ValueError('PreparedRun required')
        payload = prepared.payload
        if fingerprint(payload) != prepared.fingerprint:
            raise ValueError('Prepared payload fingerprint mismatch')
        _prepare_payload(payload)
        return {'valid': True, 'engine_version': ENGINE_VERSION}
    except (ValueError, TypeError, KeyError, AttributeError, IndexError, OSError, RecursionError) as error:
        return {'valid': False, 'engine_version': ENGINE_VERSION, 'reason': str(error)}


def run(prepared, *, rhs_factory, solver):
    validation = validate(prepared)
    if not validation['valid']:
        return {'status': 'invalid_prepared', 'validation': validation, 'activation_allowed': False,
                'biologically_validated': False, 'engine_version': ENGINE_VERSION}
    snapshot = _prepare_payload(prepared.payload)
    baseline = canonical({'parameters': snapshot.parameters, 'kinetics': snapshot.kinetics})
    captured = {}

    def guarded_factory(**kwargs):
        captured['arguments'] = kwargs
        rhs = rhs_factory(**kwargs)
        captured['rhs'] = rhs
        check_rhs()
        return rhs

    def check_rhs():
        arguments = captured['arguments']
        actual = canonical({k: arguments[k] for k in ('parameters', 'kinetics')})
        rhs = captured.get('rhs')
        # Production RHS copies its parameters, so inspect that copy as well.
        stored = canonical({k: getattr(rhs, k, arguments[k]) for k in ('parameters', 'kinetics')})
        if actual != baseline or stored != baseline:
            raise ValueError('RHS parameters or kinetics changed')

    result = legacy.run(snapshot, rhs_factory=guarded_factory, solver=solver)
    try:
        if captured:
            check_rhs()
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as error:
        result = {'status': 'contract_violation', 'reason': str(error)}
    return {**result, 'engine_version': ENGINE_VERSION, 'fingerprint': prepared.fingerprint,
            'qualification': 'not_qualified', 'activation_allowed': False, 'biologically_validated': False}
