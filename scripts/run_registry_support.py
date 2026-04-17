import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class RunRegistryContractError(ValueError):
    pass


def read_json(path: Path) -> dict:
    try:
        with open(path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError as exc:
        raise RunRegistryContractError(f'JSON file does not exist: {path}') from exc
    except json.JSONDecodeError as exc:
        raise RunRegistryContractError(f'Invalid JSON in {path}: {exc.msg}') from exc
    if not isinstance(data, dict):
        raise RunRegistryContractError(f'Expected JSON object in {path}')
    return data


def repo_relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def parse_run_timestamp(timestamp: str | None) -> str | None:
    if not timestamp:
        return None
    try:
        parsed = time.strptime(timestamp, '%Y%m%d_%H%M%S')
    except ValueError:
        return None
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', parsed)


def unique_non_empty(values: list) -> list:
    seen = []
    for value in values:
        if value is None or value == '':
            continue
        if value not in seen:
            seen.append(value)
    return seen


def find_case(cases: list[dict], case_name: str | None) -> dict | None:
    for case in cases:
        if case.get('name') == case_name:
            return case
    return None
