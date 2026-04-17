import argparse
import json
from pathlib import Path

try:
    from scripts.run_registry import project_run_registry_record_to_calibration_runs_row_from_path
except ImportError:
    from run_registry import project_run_registry_record_to_calibration_runs_row_from_path


def project_registry_record_file_to_calibration_runs_row(registry_record_path: str | Path) -> dict:
    return project_run_registry_record_to_calibration_runs_row_from_path(Path(registry_record_path))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Project a calibration_run_registry_record JSON file into a calibration_runs row payload.'
    )
    parser.add_argument(
        'registry_record_path',
        help='Path to a calibration_run_registry_record JSON file.',
    )
    parser.add_argument(
        '--pretty',
        action='store_true',
        help='Pretty-print the projected row payload.',
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    row_payload = project_registry_record_file_to_calibration_runs_row(args.registry_record_path)
    if args.pretty:
        print(json.dumps(row_payload, indent=2))
        return
    print(json.dumps(row_payload))


if __name__ == '__main__':
    main()
