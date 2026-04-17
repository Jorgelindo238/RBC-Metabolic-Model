from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
MM_CALIBRATION_PATH = REPO_ROOT / "src" / "MM_calibration.py"
EQUADIFF_BRODBAR_PATH = REPO_ROOT / "src" / "equadiff_brodbar.py"
MM_CALIBRATION_EDIT_MODE = "full_file"

AGENT_EDITABLE_START_PREFIX = "# AGENT_EDITABLE_START:"
AGENT_EDITABLE_END_PREFIX = "# AGENT_EDITABLE_END:"


def _resolve_repo_path(value: str | Path) -> Path:
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def _same_path(left: Path, right: Path) -> bool:
    return left.resolve() == right.resolve()


def extract_editable_zones_from_text(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    zones: list[dict[str, Any]] = []
    active_name: str | None = None
    active_marker_line: int | None = None

    for line_no, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if line.startswith(AGENT_EDITABLE_START_PREFIX):
            zone_name = line.split(":", 1)[1].strip()
            if not zone_name:
                raise ValueError(f"Missing zone name for editable start marker at line {line_no}.")
            if active_name is not None:
                raise ValueError(
                    f"Nested editable zone start at line {line_no} while zone '{active_name}' is still open."
                )
            active_name = zone_name
            active_marker_line = line_no
            continue

        if line.startswith(AGENT_EDITABLE_END_PREFIX):
            zone_name = line.split(":", 1)[1].strip()
            if not zone_name:
                raise ValueError(f"Missing zone name for editable end marker at line {line_no}.")
            if active_name is None or active_marker_line is None:
                raise ValueError(f"Editable zone end marker at line {line_no} has no matching start marker.")
            if zone_name != active_name:
                raise ValueError(
                    f"Editable zone end marker '{zone_name}' at line {line_no} does not match open zone '{active_name}'."
                )
            zones.append(
                {
                    "name": active_name,
                    "start_line": active_marker_line + 1,
                    "end_line": line_no - 1,
                    "start_marker_line": active_marker_line,
                    "end_marker_line": line_no,
                }
            )
            active_name = None
            active_marker_line = None

    if active_name is not None:
        raise ValueError(f"Editable zone '{active_name}' is missing an end marker.")

    return zones


def extract_editable_zones(path: str | Path) -> list[dict[str, Any]]:
    resolved_path = _resolve_repo_path(path)
    return extract_editable_zones_from_text(resolved_path.read_text(encoding="utf-8"))


def compute_changed_spans(before_text: str, after_text: str) -> list[dict[str, Any]]:
    before_lines = before_text.splitlines()
    after_lines = after_text.splitlines()
    matcher = difflib.SequenceMatcher(a=before_lines, b=after_lines)
    spans: list[dict[str, Any]] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        spans.append(
            {
                "tag": tag,
                "before_start_line": i1 + 1,
                "before_end_line": i2,
                "after_start_line": j1 + 1,
                "after_end_line": j2,
            }
        )

    return spans


def _span_is_within_zones(start_line: int, end_line: int, zones: list[dict[str, Any]]) -> bool:
    if end_line < start_line:
        return True
    for zone in zones:
        if start_line >= int(zone["start_line"]) and end_line <= int(zone["end_line"]):
            return True
    return False


def _zone_names_for_span(start_line: int, end_line: int, zones: list[dict[str, Any]]) -> list[str]:
    if end_line < start_line:
        return []
    names: list[str] = []
    for zone in zones:
        zone_start = int(zone["start_line"])
        zone_end = int(zone["end_line"])
        if start_line <= zone_end and end_line >= zone_start:
            names.append(str(zone["name"]))
    return names


def validate_agent_edit(
    file_path: str | Path,
    before_text: str,
    after_text: str,
    *,
    editable_file_path: str | Path | None = None,
    frozen_file_paths: list[str | Path] | None = None,
) -> dict[str, Any]:
    editable_path = _resolve_repo_path(editable_file_path or MM_CALIBRATION_PATH)
    frozen_paths = [_resolve_repo_path(path) for path in (frozen_file_paths or [EQUADIFF_BRODBAR_PATH])]
    candidate_path = _resolve_repo_path(file_path)

    policy = {
        "editable_file_path": str(editable_path),
        "frozen_file_paths": [str(path) for path in frozen_paths],
        "editable_mode": MM_CALIBRATION_EDIT_MODE,
        "marker_start_prefix": AGENT_EDITABLE_START_PREFIX,
        "marker_end_prefix": AGENT_EDITABLE_END_PREFIX,
    }

    if any(_same_path(candidate_path, frozen_path) for frozen_path in frozen_paths):
        return {
            "allowed": False,
            "file_path": str(candidate_path),
            "policy": policy,
            "editable_zones": [],
            "changed_spans": compute_changed_spans(before_text, after_text),
            "violations": [
                {
                    "kind": "frozen_file",
                    "message": f"{candidate_path.name} is frozen in the first agent-editable rollout.",
                }
            ],
        }

    if not _same_path(candidate_path, editable_path):
        return {
            "allowed": False,
            "file_path": str(candidate_path),
            "policy": policy,
            "editable_zones": [],
            "changed_spans": compute_changed_spans(before_text, after_text),
            "violations": [
                {
                    "kind": "non_editable_file",
                    "message": "Only MM_calibration.py is agent-editable in the first rollout.",
                }
            ],
        }

    changed_spans = compute_changed_spans(before_text, after_text)
    if MM_CALIBRATION_EDIT_MODE == "full_file":
        before_lines = before_text.splitlines()
        after_lines = after_text.splitlines()
        full_zone = {
            "name": "full_file",
            "start_line": 1,
            "end_line": max(len(after_lines), 1),
            "start_marker_line": None,
            "end_marker_line": None,
        }
        return {
            "allowed": True,
            "file_path": str(candidate_path),
            "policy": policy,
            "editable_zones": [full_zone],
            "changed_spans": changed_spans,
            "violations": [],
        }

    before_zones = extract_editable_zones_from_text(before_text)
    after_zones = extract_editable_zones_from_text(after_text)
    violations: list[dict[str, Any]] = []

    for span in changed_spans:
        before_start = int(span["before_start_line"])
        before_end = int(span["before_end_line"])
        after_start = int(span["after_start_line"])
        after_end = int(span["after_end_line"])

        if before_end >= before_start and not _span_is_within_zones(before_start, before_end, before_zones):
            violations.append(
                {
                    "kind": "outside_editable_zone",
                    "phase": "before",
                    "message": "The patch touches locked source lines outside any editable zone.",
                    "span": span,
                    "overlapping_zones": _zone_names_for_span(before_start, before_end, before_zones),
                }
            )

        if after_end >= after_start and not _span_is_within_zones(after_start, after_end, after_zones):
            violations.append(
                {
                    "kind": "outside_editable_zone",
                    "phase": "after",
                    "message": "The proposed result writes lines outside any editable zone.",
                    "span": span,
                    "overlapping_zones": _zone_names_for_span(after_start, after_end, after_zones),
                }
            )

    return {
        "allowed": not violations,
        "file_path": str(candidate_path),
        "policy": policy,
        "editable_zones": after_zones,
        "changed_spans": changed_spans,
        "violations": violations,
    }
