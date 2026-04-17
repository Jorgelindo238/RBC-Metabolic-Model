import importlib.util
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.project_calibration_runs_row import project_registry_record_file_to_calibration_runs_row

SCHEMAS = ROOT / 'packages' / 'contracts' / 'schemas'
EXAMPLES = ROOT / 'config' / 'generated'
SQL_DRAFT = ROOT / 'packages' / 'contracts' / 'sql' / 'calibration-runs.draft.sql'
SERVICE_STUB = ROOT / 'services' / 'scientific-runtime' / 'calibration_runs_persistence.py'
PAIRS = [
    ('calibration_job', SCHEMAS / 'calibration-job.schema.json', EXAMPLES / 'calibration_job.example.json'),
    ('calibration_runs_row', SCHEMAS / 'calibration-runs-row.schema.json', EXAMPLES / 'calibration_runs_row.example.json'),
    ('completed_run_manifest', SCHEMAS / 'completed-run-manifest.schema.json', EXAMPLES / 'completed_run_manifest.example.json'),
    ('run_registry_record', SCHEMAS / 'run-registry-record.schema.json', EXAMPLES / 'run_registry_record.example.json'),
]


def load_json(path: Path) -> dict:
    with open(path, 'r', encoding='utf-8') as handle:
        return json.load(handle)


def validate_example(label: str, schema_path: Path, example_path: Path) -> None:
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    example = load_json(example_path)
    errors = sorted(validator.iter_errors(example), key=lambda error: list(error.absolute_path))
    if errors:
        first = errors[0]
        path = '.'.join(str(part) for part in first.absolute_path) or '<root>'
        raise SystemExit(f'{label} failed validation at {path}: {first.message}')
    print(f'{label}: ok')


def validate_calibration_runs_projection() -> None:
    row_schema = load_json(SCHEMAS / 'calibration-runs-row.schema.json')
    registry_example = load_json(EXAMPLES / 'run_registry_record.example.json')
    row_example = load_json(EXAMPLES / 'calibration_runs_row.example.json')
    registry_example_path = EXAMPLES / 'run_registry_record.example.json'

    grouped_fields = []
    column_groups = row_schema.get('x-supabase', {}).get('column_groups', {})
    for columns in column_groups.values():
        grouped_fields.extend(columns)

    if len(grouped_fields) != len(set(grouped_fields)):
        raise SystemExit('calibration_runs_row column groups contain duplicate field assignments')

    property_fields = set(row_schema.get('properties', {}).keys())
    if set(grouped_fields) != property_fields:
        raise SystemExit(
            'calibration_runs_row column groups do not exactly cover the row schema properties'
        )

    source_registry_contract = row_schema.get('x-supabase', {}).get('source_registry_contract', {})
    if source_registry_contract.get('contract_type') != registry_example.get('contract_type'):
        raise SystemExit('calibration_runs_row source contract type does not match run_registry_record')
    if source_registry_contract.get('contract_version') != registry_example.get('contract_version'):
        raise SystemExit('calibration_runs_row source contract version does not match run_registry_record')

    derived_row = project_registry_record_file_to_calibration_runs_row(registry_example_path)
    if derived_row != row_example:
        raise SystemExit(
            'calibration_runs_row example is not an exact projection of run_registry_record.example.json'
        )

    print('calibration_runs_row_column_groups: ok')
    print('calibration_runs_row_projection: ok')


def extract_sql_table_columns(sql_text: str) -> list[str]:
    in_table_definition = False
    columns: list[str] = []

    for line in sql_text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith('create table if not exists public.calibration_runs'):
            in_table_definition = True
            continue
        if not in_table_definition:
            continue
        if stripped == ');':
            break
        if not stripped or stripped.startswith('--'):
            continue
        match = re.match(r'^([a-z_]+)\s+', stripped)
        if not match:
            continue
        column_name = match.group(1)
        if column_name in {'constraint', 'primary', 'foreign', 'unique', 'check'}:
            continue
        columns.append(column_name)

    return columns


def validate_calibration_runs_sql_draft() -> None:
    row_schema = load_json(SCHEMAS / 'calibration-runs-row.schema.json')
    row_example = load_json(EXAMPLES / 'calibration_runs_row.example.json')
    sql_text = SQL_DRAFT.read_text(encoding='utf-8')

    sql_columns = extract_sql_table_columns(sql_text)
    if not sql_columns:
        raise SystemExit('calibration_runs SQL draft does not define any table columns')
    if len(sql_columns) != len(set(sql_columns)):
        raise SystemExit('calibration_runs SQL draft contains duplicate column definitions')

    property_fields = set(row_schema.get('properties', {}).keys())
    example_fields = set(row_example.keys())
    sql_fields = set(sql_columns)

    if sql_fields != property_fields:
        raise SystemExit('calibration_runs SQL draft columns do not exactly match the row schema properties')
    if sql_fields != example_fields:
        raise SystemExit('calibration_runs SQL draft columns do not exactly match calibration_runs_row.example.json')

    print('calibration_runs_sql_draft_columns: ok')


def load_service_stub_module():
    spec = importlib.util.spec_from_file_location('calibration_runs_persistence_stub', SERVICE_STUB)
    if spec is None or spec.loader is None:
        raise SystemExit('Could not load calibration_runs_persistence service stub')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_calibration_runs_service_stub() -> None:
    row_schema = load_json(SCHEMAS / 'calibration-runs-row.schema.json')
    registry_example_path = EXAMPLES / 'run_registry_record.example.json'
    registry_example = load_json(registry_example_path)
    row_example = load_json(EXAMPLES / 'calibration_runs_row.example.json')
    service_stub = load_service_stub_module()

    loaded_registry = service_stub.load_run_registry_record(registry_example_path)
    if loaded_registry != registry_example:
        raise SystemExit('calibration_runs service stub does not load the registry example correctly')

    projected_row = service_stub.project_calibration_runs_row_payload(registry_example_path)
    if projected_row != row_example:
        raise SystemExit('calibration_runs service stub does not project the expected row payload')

    prepared_request = service_stub.prepare_calibration_runs_upsert_request(registry_example_path)
    expected_request = {
        'table': row_schema.get('x-supabase', {}).get('table_name'),
        'operation': 'upsert',
        'row': row_example,
    }
    if prepared_request != expected_request:
        raise SystemExit('calibration_runs service stub does not prepare the expected future upsert request')

    print('calibration_runs_service_stub: ok')


for label, schema_path, example_path in PAIRS:
    validate_example(label, schema_path, example_path)


validate_calibration_runs_projection()
validate_calibration_runs_sql_draft()
validate_calibration_runs_service_stub()
