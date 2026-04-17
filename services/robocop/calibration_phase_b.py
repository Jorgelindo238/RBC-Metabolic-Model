from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
MM_CALIBRATION_PATH = REPO_ROOT / "src" / "MM_calibration.py"
MAIN_PY_PATH = REPO_ROOT / "src" / "main.py"
DEFAULT_PHASE_B_ROOT = REPO_ROOT / "Simulations" / "brodbar" / "hermes" / "phase_b"
DEFAULT_MAIN_METABOLITES_DIR = REPO_ROOT / "Simulations" / "brodbar" / "metabolites"
DEFAULT_MAIN_FLUXES_DIR = REPO_ROOT / "Simulations" / "brodbar" / "fluxes"
FOCUS_METABOLITES = ["ATP", "ADP", "AMP", "IMP", "EGLC", "ELAC", "PYR", "PEP", "LAC"]


def _resolve_repo_path(value: str | None) -> Path | None:
    if value is None or not str(value).strip():
        return None
    path = Path(str(value).strip())
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def _repo_relative_str(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path)


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_optional_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _tail_text(text: str | None, limit: int = 20) -> list[str]:
    if not text:
        return []
    lines = [line for line in str(text).splitlines() if line.strip()]
    return lines[-limit:]


def _load_stage_plan_document(stage_plan_path: Path) -> dict[str, Any]:
    payload = _read_json(stage_plan_path)
    if not isinstance(payload.get("stage_plan"), list) or not payload["stage_plan"]:
        raise ValueError(f"Stage plan document at {stage_plan_path} is missing a non-empty stage_plan array.")
    return payload


def _phase_list(stage_plan_doc: dict[str, Any]) -> list[int]:
    phases: set[int] = set()
    for stage in stage_plan_doc.get("stage_plan", []):
        for phase in stage.get("phases", []):
            phases.add(int(phase))
    return sorted(phases) or [1]


def _seed_report_path(stage_plan_doc: dict[str, Any], args: dict[str, Any]) -> Path:
    explicit = _resolve_repo_path(args.get("seedReportPath"))
    if explicit is not None:
        return explicit
    seed_params = _resolve_repo_path(stage_plan_doc.get("seed_params_path"))
    if seed_params is None:
        raise FileNotFoundError("seed_params_path is missing from the stage plan and no seedReportPath was provided.")
    report_path = seed_params.parent / "calibration_report.json"
    if not report_path.exists():
        raise FileNotFoundError(f"Seed calibration report not found: {report_path}")
    return report_path


def _seed_params_path(stage_plan_doc: dict[str, Any]) -> Path:
    seed_params = _resolve_repo_path(stage_plan_doc.get("seed_params_path"))
    if seed_params is None or not seed_params.exists():
        raise FileNotFoundError(f"Seed params file not found: {seed_params}")
    return seed_params


def _build_phase_b_paths(stage_plan_path: Path, args: dict[str, Any]) -> dict[str, Path]:
    root = _resolve_repo_path(args.get("phaseBRootPath")) or DEFAULT_PHASE_B_ROOT
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = root / f"phase_b_{timestamp}_{stage_plan_path.stem}"
    calibration_dir = base / "candidate_calibration"
    seed_ode_dir = base / "seed_ode"
    candidate_ode_dir = base / "candidate_ode"
    base.mkdir(parents=True, exist_ok=True)
    calibration_dir.mkdir(parents=True, exist_ok=True)
    seed_ode_dir.mkdir(parents=True, exist_ok=True)
    candidate_ode_dir.mkdir(parents=True, exist_ok=True)
    return {
        "run_root": base,
        "calibration_dir": calibration_dir,
        "seed_ode_dir": seed_ode_dir,
        "candidate_ode_dir": candidate_ode_dir,
        "decision_path": base / "phase_b_decision.json",
    }


def _build_calibration_command(stage_plan_doc: dict[str, Any], stage_plan_path: Path, candidate_out_dir: Path, seed_params_path: Path, args: dict[str, Any]) -> list[str]:
    phases = ",".join(str(phase) for phase in _phase_list(stage_plan_doc))
    first_stage = stage_plan_doc["stage_plan"][0]
    command = [
        sys.executable,
        str(MM_CALIBRATION_PATH),
        "--load-params",
        _repo_relative_str(seed_params_path),
        "--phases",
        phases,
        "--stage-plan-file",
        _repo_relative_str(stage_plan_path),
        "--out-dir",
        _repo_relative_str(candidate_out_dir),
    ]
    target_scope = stage_plan_doc.get("target_scope") or first_stage.get("target_scope")
    if target_scope:
        command.extend(["--target-scope", str(target_scope)])
    optimization_strategy = stage_plan_doc.get("optimization_strategy")
    if optimization_strategy:
        command.extend(["--optimization-strategy", str(optimization_strategy)])
    param_scope = first_stage.get("param_scope")
    if param_scope:
        command.extend(["--param-scope", str(param_scope)])
    n_trials = first_stage.get("n_trials")
    if n_trials is not None:
        command.extend(["--n-trials", str(int(n_trials))])
    global_trials = first_stage.get("global_trials")
    if global_trials is not None:
        command.extend(["--global-trials", str(int(global_trials))])
    seed = first_stage.get("seed")
    if seed is not None:
        command.extend(["--seed", str(int(seed))])
    parameter_classes = first_stage.get("parameter_classes")
    if parameter_classes:
        if isinstance(parameter_classes, list):
            parameter_classes = ",".join(str(item) for item in parameter_classes if str(item).strip())
        command.extend(["--parameter-classes", str(parameter_classes)])
    if bool(first_stage.get("atp_focus")):
        command.append("--atp-focus")
    scalar_flags = [
        ("atp_floor", "--atp-floor"),
        ("adp_floor", "--adp-floor"),
        ("amp_floor", "--amp-floor"),
        ("imp_floor", "--imp-floor"),
        ("adenylate_target", "--adenylate-target"),
        ("atp_penalty_weight", "--atp-penalty-weight"),
        ("amp_penalty_weight", "--amp-penalty-weight"),
        ("imp_penalty_weight", "--imp-penalty-weight"),
        ("pool_penalty_weight", "--pool-penalty-weight"),
        ("curve_fit_strength", "--curve-fit-strength"),
        ("t_max", "--t-max"),
    ]
    for key, flag in scalar_flags:
        value = first_stage.get(key)
        if value is not None:
            command.extend([flag, str(value)])
    if bool(args.get("skipCalibrationPlots", True)):
        command.append("--skip-plots")
    return command


def _build_main_command(params_path: Path, args: dict[str, Any]) -> list[str]:
    model = str(args.get("mainModel") or "brodbar")
    return [
        sys.executable,
        str(MAIN_PY_PATH),
        "--model",
        model,
        "--load-params",
        _repo_relative_str(params_path),
    ]


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
        "stdout_tail": _tail_text(completed.stdout),
        "stderr_tail": _tail_text(completed.stderr),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _copy_if_exists(source: Path, dest: Path) -> str | None:
    if not source.exists():
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    return str(dest)


def _capture_main_outputs(dest_dir: Path) -> dict[str, str | None]:
    artifacts = {
        "all_metabolites_csv": _copy_if_exists(
            DEFAULT_MAIN_METABOLITES_DIR / "all_metabolites.csv",
            dest_dir / "all_metabolites.csv",
        ),
        "metabolites_pdf": _copy_if_exists(
            DEFAULT_MAIN_METABOLITES_DIR / "Metabolites_Results_brodbar_Bordbar2015.pdf",
            dest_dir / "Metabolites_Results_brodbar_Bordbar2015.pdf",
        ),
        "flux_pdf": _copy_if_exists(
            DEFAULT_MAIN_FLUXES_DIR / "Flux_Analysis_Report.pdf",
            dest_dir / "Flux_Analysis_Report.pdf",
        ),
    }
    return artifacts


def _read_ode_summary(csv_path: Path) -> dict[str, Any]:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    metabolites: dict[str, Any] = {}
    for name in FOCUS_METABOLITES:
        values: list[float] = []
        for row in rows:
            raw = row.get(name)
            if raw in (None, ""):
                continue
            try:
                values.append(float(raw))
            except Exception:
                continue
        if not values:
            metabolites[name] = {"available": False}
            continue
        start = float(values[0])
        end = float(values[-1])
        max_value = float(max(values))
        min_value = float(min(values))
        delta = end - start
        pct_delta = (delta / start * 100.0) if abs(start) > 1e-12 else None
        shape = "flat"
        if end <= max(1e-9, 0.05 * max(start, 1e-9)):
            shape = "collapse"
        elif delta > 0.05 * max(abs(start), 1.0):
            shape = "rising"
        elif delta < -0.05 * max(abs(start), 1.0):
            shape = "falling"
        metabolites[name] = {
            "available": True,
            "start": round(start, 6),
            "end": round(end, 6),
            "min": round(min_value, 6),
            "max": round(max_value, 6),
            "delta": round(delta, 6),
            "pct_delta": round(pct_delta, 3) if pct_delta is not None else None,
            "shape": shape,
        }
    return {"csvPath": str(csv_path), "timepointCount": len(rows), "metabolites": metabolites}


def _report_rows_by_name(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("name", "")).upper(): row
        for row in report.get("per_metabolite", [])
        if isinstance(row, dict) and row.get("name")
    }


def _read_results_tsv_summary(results_path: Path | None) -> dict[str, Any]:
    if results_path is None or not results_path.exists():
        return {}
    with results_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if not rows:
        return {}
    baseline_row = next((row for row in rows if str(row.get("stage", "")).strip().lower() == "baseline"), rows[0])
    final_row = next((row for row in reversed(rows) if str(row.get("stage", "")).strip().lower() == "final"), rows[-1])
    return {
        "path": str(results_path),
        "row_count": len(rows),
        "baseline_stage": baseline_row.get("stage"),
        "final_stage": final_row.get("stage"),
        "baseline_target_loss": _safe_optional_float(baseline_row.get("baseline_target_loss")),
        "baseline_candidate_target_loss": _safe_optional_float(baseline_row.get("candidate_target_loss")),
        "final_baseline_target_loss": _safe_optional_float(final_row.get("baseline_target_loss")),
        "final_candidate_target_loss": _safe_optional_float(final_row.get("candidate_target_loss")),
        "final_rank_loss": _safe_optional_float(final_row.get("rank_loss")),
        "final_joint_loss": _safe_optional_float(final_row.get("joint_loss")),
        "final_guardrail_loss": _safe_optional_float(final_row.get("guardrail_loss")),
        "final_endpoint_nrmse": _safe_optional_float(final_row.get("endpoint_nrmse")),
        "final_status": final_row.get("status"),
    }


def _report_context(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_scope": report.get("target_scope"),
        "param_scope": report.get("param_scope"),
        "optimization_strategy": report.get("optimization_strategy"),
        "seed": report.get("seed"),
        "t_max": report.get("t_max"),
        "curve_fit_strength": report.get("curve_fit_strength"),
        "data_mode": report.get("data_mode"),
    }


def _contexts_match(seed_report: dict[str, Any], candidate_report: dict[str, Any]) -> bool:
    keys = ["target_scope", "data_mode"]
    for key in keys:
        seed_value = seed_report.get(key)
        candidate_value = candidate_report.get(key)
        if seed_value is not None and candidate_value is not None and seed_value != candidate_value:
            return False
    numeric_keys = ["t_max", "curve_fit_strength"]
    for key in numeric_keys:
        seed_value = _safe_optional_float(seed_report.get(key))
        candidate_value = _safe_optional_float(candidate_report.get(key))
        if seed_value is None or candidate_value is None:
            continue
        if abs(seed_value - candidate_value) > 1e-9:
            return False
    return True


def _compare_fit(
    seed_report: dict[str, Any],
    candidate_report: dict[str, Any],
    protected_metabolites: list[str],
    candidate_results_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidate_results_summary = candidate_results_summary or {}
    historical_seed_loss = _safe_float(seed_report.get("final_loss"))
    historical_candidate_loss = _safe_float(candidate_report.get("final_loss"))
    candidate_context_baseline_loss = (
        candidate_results_summary.get("baseline_target_loss")
        if candidate_results_summary.get("baseline_target_loss") is not None
        else _safe_float(candidate_report.get("baseline_loss"))
    )
    candidate_context_final_loss = (
        candidate_results_summary.get("final_candidate_target_loss")
        if candidate_results_summary.get("final_candidate_target_loss") is not None
        else historical_candidate_loss
    )
    absolute_gain = candidate_context_baseline_loss - candidate_context_final_loss
    relative_gain = absolute_gain / max(abs(candidate_context_baseline_loss), 1.0)
    historical_delta = historical_seed_loss - historical_candidate_loss
    contexts_match = _contexts_match(seed_report, candidate_report)
    seed_rows = _report_rows_by_name(seed_report)
    candidate_rows = _report_rows_by_name(candidate_report)
    per_metabolite = {}
    for name in protected_metabolites:
        seed_row = seed_rows.get(name.upper(), {})
        candidate_row = candidate_rows.get(name.upper(), {})
        seed_nrmse = _safe_float(seed_row.get("nrmse"), default=None) if seed_row else None
        candidate_nrmse = _safe_float(candidate_row.get("nrmse"), default=None) if candidate_row else None
        if seed_nrmse is None or candidate_nrmse is None:
            continue
        status = "context_mismatch"
        if contexts_match:
            status = "same"
            if candidate_nrmse < seed_nrmse - 0.02:
                status = "better"
            elif candidate_nrmse > seed_nrmse + 0.02:
                status = "worse"
        per_metabolite[name.upper()] = {
            "seed_nrmse": round(seed_nrmse, 6),
            "candidate_nrmse": round(candidate_nrmse, 6),
            "status": status,
        }
    return {
        "comparison_basis": "candidate_within_run_baseline_vs_candidate_final",
        "candidate_results_summary": candidate_results_summary,
        "seed_context": _report_context(seed_report),
        "candidate_context": _report_context(candidate_report),
        "contexts_match": contexts_match,
        "historical_seed_final_loss": round(historical_seed_loss, 6) if historical_seed_loss is not None else None,
        "candidate_within_run_baseline_loss": round(candidate_context_baseline_loss, 6) if candidate_context_baseline_loss is not None else None,
        "candidate_within_run_final_loss": round(candidate_context_final_loss, 6) if candidate_context_final_loss is not None else None,
        "historical_candidate_final_loss": round(historical_candidate_loss, 6) if historical_candidate_loss is not None else None,
        "historical_vs_candidate_delta": round(historical_delta, 6) if historical_delta is not None else None,
        "absolute_gain": round(absolute_gain, 6) if absolute_gain is not None else None,
        "relative_gain": round(relative_gain, 6) if relative_gain is not None else None,
        "meaningful_improvement": absolute_gain > max(0.05, 0.01 * max(abs(candidate_context_baseline_loss), 1.0)),
        "protected_fit_status": per_metabolite,
    }


def _compare_pure_ode(seed_ode: dict[str, Any], candidate_ode: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    seed_meta = seed_ode.get("metabolites", {})
    candidate_meta = candidate_ode.get("metabolites", {})

    for name in FOCUS_METABOLITES:
        seed_row = seed_meta.get(name, {})
        candidate_row = candidate_meta.get(name, {})
        status = "same"
        note = ""
        if name in {"ATP", "ADP"}:
            seed_collapse = seed_row.get("shape") == "collapse"
            candidate_collapse = candidate_row.get("shape") == "collapse"
            if seed_collapse and not candidate_collapse:
                status = "better"
                note = "collapse_removed"
            elif not seed_collapse and candidate_collapse:
                status = "worse"
                note = "new_collapse"
            elif candidate_collapse:
                status = "still_weak"
                note = "still_collapsed"
        elif name == "EGLC":
            seed_pct = _safe_float(seed_row.get("pct_delta"), 0.0)
            candidate_pct = _safe_float(candidate_row.get("pct_delta"), 0.0)
            if candidate_pct < seed_pct - 1.0:
                status = "better"
                note = "steeper"
            elif candidate_pct > seed_pct + 1.0:
                status = "worse"
                note = "shallower"
            elif candidate_pct > -15.0:
                status = "still_weak"
                note = "still_shallow"
        elif name == "ELAC":
            seed_end = _safe_float(seed_row.get("end"), 0.0)
            candidate_end = _safe_float(candidate_row.get("end"), 0.0)
            if candidate_end > seed_end + 0.5:
                status = "better"
                note = "stronger_export"
            elif candidate_end < seed_end - 0.5:
                status = "worse"
                note = "weaker_export"
        elif name == "PYR":
            seed_ratio = _safe_float(seed_row.get("max"), 0.0) / max(_safe_float(seed_row.get("end"), 0.0), 1e-9)
            candidate_ratio = _safe_float(candidate_row.get("max"), 0.0) / max(_safe_float(candidate_row.get("end"), 0.0), 1e-9)
            if candidate_ratio < seed_ratio - 0.25:
                status = "better"
                note = "smaller_spike"
            elif candidate_ratio > seed_ratio + 0.25:
                status = "worse"
                note = "larger_spike"
        elif name == "LAC":
            seed_end = _safe_float(seed_row.get("end"), 0.0)
            candidate_end = _safe_float(candidate_row.get("end"), 0.0)
            seed_shape = seed_row.get("shape")
            candidate_shape = candidate_row.get("shape")
            if candidate_end > seed_end + 0.2:
                status = "better"
                note = "more_accumulation"
            elif candidate_end < seed_end - 0.2:
                status = "worse"
                note = "less_accumulation"
            elif candidate_shape == "falling":
                status = "still_weak"
                note = "falls_late"
        result[name] = {
            "seed": seed_row,
            "candidate": candidate_row,
            "status": status,
            "note": note,
        }
    return result


def _classify_decision(fit_summary: dict[str, Any], pure_ode_delta: dict[str, Any], protected_metabolites: list[str]) -> tuple[str, str]:
    meaningful_fit_gain = bool(fit_summary.get("meaningful_improvement"))
    pure_worse = any(item.get("status") == "worse" for item in pure_ode_delta.values())
    pure_better = any(item.get("status") == "better" for item in pure_ode_delta.values())
    still_weak = any(item.get("status") == "still_weak" for item in pure_ode_delta.values())
    protected_fit_worse = any(
        item.get("status") == "worse"
        for name, item in fit_summary.get("protected_fit_status", {}).items()
        if name in {met.upper() for met in protected_metabolites}
    )
    atp_ok = pure_ode_delta.get("ATP", {}).get("status") not in {"worse", "still_weak"}
    adp_ok = pure_ode_delta.get("ADP", {}).get("status") not in {"worse", "still_weak"}
    eglc_ok = pure_ode_delta.get("EGLC", {}).get("status") not in {"worse", "still_weak"}

    if meaningful_fit_gain and not pure_worse and not protected_fit_worse and atp_ok and adp_ok and eglc_ok:
        return "promote", "Candidate improved fit materially and preserved the protected pure-ODE checks."
    if (meaningful_fit_gain and not pure_worse) or pure_better:
        return "informative", "Candidate improved part of the fit story, but the pure ODE still needs manual scientific review."
    if still_weak and meaningful_fit_gain:
        return "informative", "Candidate improved fit in-run, but protected pure-ODE weaknesses still require manual review."
    return "discard", "Candidate did not improve fit enough or only reproduced an already weak/saturated basin."


def execute_phase_b(args: dict[str, Any]) -> dict[str, Any]:
    stage_plan_path = _resolve_repo_path(args.get("stagePlanPath"))
    if stage_plan_path is None or not stage_plan_path.exists():
        raise FileNotFoundError(f"Stage plan not found: {stage_plan_path}")

    stage_plan_doc = _load_stage_plan_document(stage_plan_path)
    seed_params_path = _seed_params_path(stage_plan_doc)
    seed_report_path = _seed_report_path(stage_plan_doc, args)
    protected_metabolites = [str(item) for item in stage_plan_doc.get("protect") or ["ATP", "ADP", "EGLC", "ELAC", "LAC"]]
    paths = _build_phase_b_paths(stage_plan_path, args)

    calibration_command = _build_calibration_command(
        stage_plan_doc=stage_plan_doc,
        stage_plan_path=stage_plan_path,
        candidate_out_dir=paths["calibration_dir"],
        seed_params_path=seed_params_path,
        args=args,
    )
    calibration_result = _run_command(calibration_command)
    if calibration_result["returncode"] != 0:
        raise RuntimeError(
            f"Calibration execution failed with exit code {calibration_result['returncode']}: "
            + " | ".join(calibration_result["stderr_tail"])
        )

    candidate_report_path = paths["calibration_dir"] / "calibration_report.json"
    candidate_params_path = paths["calibration_dir"] / "best_params.json"
    if not candidate_report_path.exists() or not candidate_params_path.exists():
        raise FileNotFoundError(
            f"Expected candidate artifacts were not produced in {paths['calibration_dir']}"
        )

    run_seed_main = bool(args.get("runSeedMain", True))
    seed_main_result = None
    seed_ode_artifacts = {"all_metabolites_csv": args.get("seedOdeCsvPath"), "metabolites_pdf": None, "flux_pdf": None}
    if run_seed_main:
        seed_main_result = _run_command(_build_main_command(seed_params_path, args))
        if seed_main_result["returncode"] != 0:
            raise RuntimeError(
                f"Seed main.py execution failed with exit code {seed_main_result['returncode']}: "
                + " | ".join(seed_main_result["stderr_tail"])
            )
        seed_ode_artifacts = _capture_main_outputs(paths["seed_ode_dir"])

    candidate_main_result = _run_command(_build_main_command(candidate_params_path, args))
    if candidate_main_result["returncode"] != 0:
        raise RuntimeError(
            f"Candidate main.py execution failed with exit code {candidate_main_result['returncode']}: "
            + " | ".join(candidate_main_result["stderr_tail"])
        )
    candidate_ode_artifacts = _capture_main_outputs(paths["candidate_ode_dir"])

    seed_ode_csv_path = _resolve_repo_path(args.get("seedOdeCsvPath"))
    if seed_ode_csv_path is None:
        seed_ode_csv_path = Path(str(seed_ode_artifacts["all_metabolites_csv"]))
    candidate_ode_csv_path = Path(str(candidate_ode_artifacts["all_metabolites_csv"]))
    if not seed_ode_csv_path.exists() or not candidate_ode_csv_path.exists():
        raise FileNotFoundError("Seed or candidate all_metabolites.csv is missing for Phase B comparison.")

    seed_report = _read_json(seed_report_path)
    candidate_report = _read_json(candidate_report_path)
    seed_ode_summary = _read_ode_summary(seed_ode_csv_path)
    candidate_ode_summary = _read_ode_summary(candidate_ode_csv_path)
    candidate_results_summary = _read_results_tsv_summary(paths["calibration_dir"] / "results.tsv")
    fit_summary = _compare_fit(seed_report, candidate_report, protected_metabolites, candidate_results_summary)
    pure_ode_delta = _compare_pure_ode(seed_ode_summary, candidate_ode_summary)
    decision, reason = _classify_decision(fit_summary, pure_ode_delta, protected_metabolites)

    decision_record = {
        "contract_type": "hermes_calibration_phase_b_decision",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "reason": reason,
        "stage_plan_path": _repo_relative_str(stage_plan_path),
        "seed_params_path": _repo_relative_str(seed_params_path),
        "candidate_params_path": _repo_relative_str(candidate_params_path),
        "seed_report_path": _repo_relative_str(seed_report_path),
        "candidate_report_path": _repo_relative_str(candidate_report_path),
        "seed_ode_csv_path": _repo_relative_str(seed_ode_csv_path),
        "candidate_ode_csv_path": _repo_relative_str(candidate_ode_csv_path),
        "fit_summary": fit_summary,
        "pure_ode_delta": pure_ode_delta,
        "protected_metabolites": protected_metabolites,
        "calibration_command": calibration_command,
        "seed_main_command": _build_main_command(seed_params_path, args) if run_seed_main else None,
        "candidate_main_command": _build_main_command(candidate_params_path, args),
    }
    paths["decision_path"].write_text(json.dumps(decision_record, indent=2), encoding="utf-8")

    return {
        "status": "completed",
        "decision": decision,
        "reason": reason,
        "runRoot": str(paths["run_root"]),
        "decisionPath": str(paths["decision_path"]),
        "seedArtifacts": {
            "reportPath": str(seed_report_path),
            "paramsPath": str(seed_params_path),
            "odeCsvPath": str(seed_ode_csv_path),
            "mainArtifacts": seed_ode_artifacts,
        },
        "candidateArtifacts": {
            "reportPath": str(candidate_report_path),
            "paramsPath": str(candidate_params_path),
            "odeCsvPath": str(candidate_ode_csv_path),
            "mainArtifacts": candidate_ode_artifacts,
        },
        "fitSummary": fit_summary,
        "pureOdeDelta": pure_ode_delta,
        "calibrationExecution": {
            "command": calibration_command,
            "returncode": calibration_result["returncode"],
            "stdoutTail": calibration_result["stdout_tail"],
            "stderrTail": calibration_result["stderr_tail"],
        },
        "seedMainExecution": {
            "command": _build_main_command(seed_params_path, args) if run_seed_main else None,
            "returncode": seed_main_result["returncode"] if seed_main_result else None,
            "stdoutTail": seed_main_result["stdout_tail"] if seed_main_result else [],
            "stderrTail": seed_main_result["stderr_tail"] if seed_main_result else [],
        },
        "candidateMainExecution": {
            "command": _build_main_command(candidate_params_path, args),
            "returncode": candidate_main_result["returncode"],
            "stdoutTail": candidate_main_result["stdout_tail"],
            "stderrTail": candidate_main_result["stderr_tail"],
        },
    }
