from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from services.robocop.calibration_edit_policy import validate_agent_edit


REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve_repo_path(value: str | Path) -> Path:
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def apply_agent_edit(
    file_path: str | Path,
    proposed_text: str,
    *,
    create_backup: bool = False,
) -> dict[str, Any]:
    resolved_file_path = _resolve_repo_path(file_path)
    if not resolved_file_path.exists():
        raise FileNotFoundError(f"Editable source file not found: {resolved_file_path}")

    current_text = resolved_file_path.read_text(encoding="utf-8")
    validation = validate_agent_edit(
        file_path=resolved_file_path,
        before_text=current_text,
        after_text=proposed_text,
    )

    result: dict[str, Any] = {
        "file_path": str(resolved_file_path),
        "validation": validation,
        "status": "rejected",
        "applied": False,
        "no_change": False,
        "before_sha256": _sha256_text(current_text),
        "after_sha256": _sha256_text(proposed_text),
    }

    if not validation["allowed"]:
        result["reason"] = "Validation failed; no source edit was written."
        return result

    if proposed_text == current_text:
        result["status"] = "no_change"
        result["applied"] = False
        result["no_change"] = True
        result["reason"] = "Proposed text matches the current file; nothing was written."
        return result

    backup_path: str | None = None
    if create_backup:
        backup = resolved_file_path.with_suffix(resolved_file_path.suffix + ".agent.bak")
        backup.write_text(current_text, encoding="utf-8")
        backup_path = str(backup)

    resolved_file_path.write_text(proposed_text, encoding="utf-8")
    result["status"] = "applied"
    result["applied"] = True
    result["reason"] = "Validation passed and the bounded source edit was written."
    result["bytes_written"] = len(proposed_text.encode("utf-8"))
    if backup_path is not None:
        result["backup_path"] = backup_path
    return result
