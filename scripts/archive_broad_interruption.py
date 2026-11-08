"""Seal an explicitly interrupted optimizer attempt, without inventing a fit."""

import argparse
import json
from pathlib import Path

from run_protected_joint import verify_inputs
from run_glut_only_free_replay import sha, write

ROOT = Path(__file__).resolve().parents[1]


def archive(out, replacement):
    if (out/"manifest.json").exists(): raise ValueError("archive already sealed")
    f = verify_inputs(out)
    fits = []
    for path in sorted((out/"fits").glob("*/trace.jsonl")):
        lines = path.read_text().splitlines()
        rows, tail = [], False
        for i, line in enumerate(lines):
            try: rows.append(json.loads(line))
            except json.JSONDecodeError:
                if i != len(lines)-1: raise
                tail = True
        if any(row["call"] != i for i, row in enumerate(rows, 1)):
            raise ValueError("noncontiguous original trace")
        completed = (path.parent/"result.json").exists()
        eligible = [r for r in rows if r["valid"] and r["guards"]["passed"]]
        fits.append({"label": path.parent.name, "completed_fit": completed,
            "completed_logged_objective_integrations": len(rows), "incomplete_tail_preserved": tail,
            "best_feasible_NLL": min(r["score"]["negative_log_likelihood"] for r in eligible)})
    replacement_result = replacement/"fits/restoration/result.json"
    r = json.loads(replacement_result.read_text())
    if not r["training_guards"]["passed"]: raise ValueError("replacement fitting guards not passed")
    status = {"state": "interrupted_not_converged_not_a_completed_calibration", "fits": fits,
        "completed_logged_objective_integrations": sum(r["completed_logged_objective_integrations"] for r in fits),
        "possible_unlogged_inflight_integration": True,
        "reason": "stagnant_SLSQP_superseded_by_separate_strictly_guard_feasible_numerical_restoration",
        "replacement_archive": replacement.relative_to(ROOT).as_posix(),
        "replacement_full_horizon_validation_required": True, "original_traces_or_limits_modified": False,
        "no_optimizer_convergence_claim": True, "production_promoted": False}
    write(out/"interruption_summary.json", status)
    inputs = {**f["input_sha256"], Path(__file__).relative_to(ROOT).as_posix(): sha(Path(__file__)),
              replacement_result.relative_to(ROOT).as_posix(): sha(replacement_result)}
    write(out/"manifest.json", {"archive_state": status["state"], "input_sha256": inputs,
        "output_sha256": {p.relative_to(out).as_posix(): sha(p) for p in sorted(out.rglob("*")) if p.is_file()}})
    return status


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--replacement", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(archive(args.archive.resolve(), args.replacement.resolve()), indent=2))
