import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.project_calibration_runs_row import project_registry_record_file_to_calibration_runs_row
from scripts.run_registry_support import read_json

CALIBRATION_RUNS_TABLE_NAME = 'calibration_runs'
CALIBRATION_RUNS_OPERATION = 'upsert'


import os
import json
import urllib.request
import urllib.error

def load_run_registry_record(registry_record_path: str | Path) -> dict:
    return read_json(Path(registry_record_path).resolve())


def project_calibration_runs_row_payload(registry_record_path: str | Path) -> dict:
    return project_registry_record_file_to_calibration_runs_row(registry_record_path)


def prepare_calibration_runs_upsert_request(registry_record_path: str | Path) -> dict:
    return {
        'table': CALIBRATION_RUNS_TABLE_NAME,
        'operation': CALIBRATION_RUNS_OPERATION,
        'row': project_calibration_runs_row_payload(registry_record_path),
    }


def upsert_calibration_runs_row(registry_record_path: str | Path) -> dict:
    """
    Physically executes the upsert operation against the Supabase REST API.
    Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables.
    """
    url = os.environ.get('SUPABASE_URL')
    service_key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    
    if not url or not service_key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment variables")
        
    endpoint = f"{str(url).rstrip('/')}/rest/v1/{CALIBRATION_RUNS_TABLE_NAME}"
    payload = project_calibration_runs_row_payload(registry_record_path)
    
    data = json.dumps(payload).encode('utf-8')
    
    req = urllib.request.Request(endpoint, data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('apikey', str(service_key))
    req.add_header('Authorization', f'Bearer {str(service_key)}')
    req.add_header('Prefer', 'resolution=merge-duplicates')
    
    try:
        with urllib.request.urlopen(req) as response:
            if response.status in (200, 201, 204):
                return {"status": "success", "run_id": payload.get('run_id')}
            else:
                body = response.read().decode('utf-8')
                raise RuntimeError(f"Failed to upsert row: {response.status} {body}")
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        raise RuntimeError(f"HTTP Error {e.code}: {body}")
    except Exception as e:
        raise RuntimeError(f"Error connecting to Supabase: {str(e)}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python calibration_runs_persistence.py <path_to_registry_record_json>")
        sys.exit(1)
        
    record_path = sys.argv[1]
    print(f"Upserting {record_path} to Supabase...")
    try:
        result = upsert_calibration_runs_row(record_path)
        print("Success:", result)
    except Exception as e:
        print("Error:", e)
        sys.exit(1)
