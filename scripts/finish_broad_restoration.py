"""Continue a sealed restoration fit through the unchanged full-ODE auditor."""

import argparse
import json
from pathlib import Path

from run_protected_joint import verify_inputs, check_seal
from run_glut_only_free_replay import sha, write
from run_broad_protected_joint import run

ROOT = Path(__file__).resolve().parents[1]


def finish(out):
    verify_inputs(out)
    fit = out/"fits/restoration"
    check_seal(fit)
    control = json.loads((fit/"trace.jsonl").read_text().splitlines()[0])
    if control["log_factors"] != [0.]*6 or not control["guards"]["passed"]:
        raise ValueError("restoration lacks its real evaluated control")
    # The generic campaign selector reads this reference, not a second fit.
    folder = out/"fits/control"
    folder.mkdir(exist_ok=True)
    path = folder/"trace.jsonl"
    if path.exists():
        if [json.loads(line) for line in path.read_text().splitlines()] != [control]:
            raise ValueError("control reference differs from the actual first restoration solve")
    else:
        path.write_text(json.dumps(control, allow_nan=False)+"\n", encoding="utf-8")
    provenance = out/"continuation_provenance.json"
    if not provenance.exists():
        write(provenance, {"script": Path(__file__).relative_to(ROOT).as_posix(), "script_sha256": sha(Path(__file__)),
            "control_reference_is_copy_not_new_integration": True,
            "source_trace_sha256": sha(fit/"trace.jsonl"), "new_objective_integrations_in_adapter": 0})
    return run(out, 1, True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(finish(args.archive.resolve()), indent=2))
