from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from services.robocop.calibration_edit_flow import apply_agent_edit
from services.robocop.calibration_phase_b import execute_phase_b


REPO_ROOT = Path(__file__).resolve().parents[2]


def _resolve_repo_path(value: str | Path) -> Path:
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def _run_command(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "stdout_tail": [line for line in completed.stdout.splitlines() if line.strip()][-20:],
        "stderr_tail": [line for line in completed.stderr.splitlines() if line.strip()][-20:],
    }


def _restore_file(file_path: Path, original_text: str) -> dict[str, Any]:
    file_path.write_text(original_text, encoding="utf-8")
    return {
        "restored": True,
        "file_path": str(file_path),
        "reason": "Patch was reverted after gated validation.",
    }


def execute_patch_proposal_loop(args: dict[str, Any]) -> dict[str, Any]:
    file_path_raw = args.get("filePath")
    proposed_text = args.get("proposedText")
    stage_plan_path = args.get("stagePlanPath")

    if not isinstance(file_path_raw, str) or not file_path_raw.strip():
        raise ValueError("filePath is required.")
    if not isinstance(proposed_text, str):
        raise ValueError("proposedText is required.")
    if not isinstance(stage_plan_path, str) or not stage_plan_path.strip():
        raise ValueError("stagePlanPath is required.")

    file_path = _resolve_repo_path(file_path_raw)
    original_text = file_path.read_text(encoding="utf-8")
    keep_on_decision = {str(item).strip().lower() for item in (args.get("keepOnDecision") or ["promote"])}

    apply_result = apply_agent_edit(
        file_path=file_path,
        proposed_text=proposed_text,
        create_backup=bool(args.get("createBackup", False)),
    )
    if not apply_result.get("applied"):
        return {
            "status": "rejected" if apply_result.get("status") == "rejected" else apply_result.get("status", "rejected"),
            "decision": "rejected",
            "reason": apply_result.get("reason"),
            "applyResult": apply_result,
            "compileCheck": None,
            "phaseBResult": None,
            "revert": {
                "restored": False,
                "reason": "No source edit was written, so no revert was needed.",
            },
        }

    compile_targets = [str(file_path)]
    extra_compile_targets = args.get("pyCompileTargets") or []
    for item in extra_compile_targets:
        compile_targets.append(str(_resolve_repo_path(item)))
    compile_command = [sys.executable, "-m", "py_compile", *compile_targets]
    compile_check = _run_command(compile_command)

    if compile_check["returncode"] != 0:
        revert = _restore_file(file_path, original_text)
        return {
            "status": "compile_failed",
            "decision": "discard",
            "reason": "The proposed patch failed py_compile and was reverted.",
            "applyResult": apply_result,
            "compileCheck": compile_check,
            "phaseBResult": None,
            "revert": revert,
        }

    phase_b_result: dict[str, Any] | None = None
    try:
        phase_b_result = execute_phase_b(
            {
                "stagePlanPath": stage_plan_path,
                "phaseBRootPath": args.get("phaseBRootPath"),
                "seedReportPath": args.get("seedReportPath"),
                "seedOdeCsvPath": args.get("seedOdeCsvPath"),
                "mainModel": args.get("mainModel"),
                "runSeedMain": args.get("runSeedMain", True),
                "skipCalibrationPlots": args.get("skipCalibrationPlots", True),
            }
        )
    except Exception as exc:
        revert = _restore_file(file_path, original_text)
        return {
            "status": "phase_b_failed",
            "decision": "discard",
            "reason": f"Scientific validation failed after the patch was applied: {exc}",
            "applyResult": apply_result,
            "compileCheck": compile_check,
            "phaseBResult": None,
            "revert": revert,
        }

    decision = str(phase_b_result.get("decision", "discard")).lower()
    if decision not in keep_on_decision:
        revert = _restore_file(file_path, original_text)
        return {
            "status": "completed_reverted",
            "decision": decision,
            "reason": (
                "The patch passed the gate and scientific validation, "
                f"but decision '{decision}' is not in keepOnDecision, so it was reverted."
            ),
            "applyResult": apply_result,
            "compileCheck": compile_check,
            "phaseBResult": phase_b_result,
            "revert": revert,
        }

    return {
        "status": "completed_kept",
        "decision": decision,
        "reason": f"The patch passed policy validation and scientific validation with decision '{decision}', so it was kept.",
        "applyResult": apply_result,
        "compileCheck": compile_check,
        "phaseBResult": phase_b_result,
        "revert": {
            "restored": False,
            "reason": "Patch was kept after scientific validation.",
        },
    }
