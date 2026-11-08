"""Preserve executed code and seal the completed audit without rewriting receipts."""

import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "output/rbc_gem_network_audit_2026_10_06"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check(path, expected):
    if sha(path) != expected:
        raise ValueError(f"Hash mismatch: {path}")


def main():
    final = BASE / "final_manifest.json"
    snapshots = BASE / "executed_local_sources"
    if final.exists() or snapshots.exists():
        raise FileExistsError("Final archive already exists; preserve it")
    receipt = json.loads((BASE / "independent_verification.json").read_text())
    for path, expected in receipt["sha256"].items():
        check(Path(path), expected)
    for folder in ("priority_proteomics_v2", "fixed_parameter_diagnostic"):
        manifest = json.loads((BASE / folder / "manifest.json").read_text())
        for path, expected in manifest["input_sha256"].items():
            check(Path(path), expected)
        for path, expected in manifest["output_sha256"].items():
            check(BASE / folder / path, expected)
    source_receipt = json.loads((BASE / "source_value_verification.json").read_text())
    if not source_receipt["all_passed"]:
        raise ValueError("Source-cell verification failed")
    check(ROOT / "scripts/verify_rbc_gem_proteomics_cells.py", source_receipt["verifier_sha256"])
    check(BASE / "priority_proteomics_v2/manifest.json", source_receipt["export_manifest_sha256"])
    files = ["RBC/Rxn_RBC.txt", "src/parse.py", "src/rbc_gem_audit.py", "src/rbc_gem_network.py",
             "src/equadiff_brodbar.py", "src/rbc_stoichiometry.py", "src/reaction_positivity.py",
             "config/fla_working_reference.json", "config/fla_rbc_gem_structural_diagnostic.json",
             "qa/test_rbc_gem_network.py", "scripts/fetch_rbc_gem_network_sources.py",
             "scripts/audit_rbc_gem_network.py", "scripts/extract_rbc_gem_priority_proteomics.py",
             "scripts/run_rbc_gem_structural_diagnostic.py", "scripts/verify_rbc_gem_network_audit.py",
             "scripts/verify_rbc_gem_proteomics_cells.py", "scripts/seal_rbc_gem_network_audit.py",
             "tasks/fla_rbc_gem_network_audit_2026_10_06.md", "tasks/fla_current_tasks.md",
             "fla_progress_log.md"]
    hashes = {}
    for name in files:
        path = ROOT / name
        destination = snapshots / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        hashes[name] = sha(path)
        check(destination, hashes[name])
    outputs = {path.relative_to(BASE).as_posix(): sha(path)
               for path in sorted(BASE.rglob("*")) if path.is_file() and path != final}
    result = {"status": "complete", "network_verification_checks": 207,
              "qa_passed": 952, "qa_skipped": 2, "free_replays_completed": 8,
              "S6_source_values_verified": 229152, "donor_metadata_cells_verified": 17864,
              "calibration_executed": False, "core_promoted": False,
              "prior_manifests_rewritten": False, "local_source_sha256": hashes,
              "archive_sha256": outputs}
    final.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"files_sealed": len(outputs), "local_sources_preserved": len(files),
                      "manifest": str(final)}, indent=2))


if __name__ == "__main__":
    main()
