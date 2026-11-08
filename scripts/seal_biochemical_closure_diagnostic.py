"""Seal the completed targeted campaign while retaining all historical archives."""

import hashlib
import json
from pathlib import Path
import shutil
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from parse import parse
from rbc_biochemical_extensions import biochemical_matrix

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "output/biochemical_closure_2026_10_06"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    final = BASE / "final_manifest.json"
    snapshots = BASE / "executed_local_sources"
    if final.exists() or snapshots.exists():
        raise FileExistsError("Preserve the existing sealed campaign")
    verification = json.loads((BASE / "independent_verification.json").read_text())
    if verification["biological_calibration"] or verification["OPLAH_deleted"] or verification["global_promotion"]:
        raise ValueError("This archive cannot promote a biological fit or delete OPLAH")
    for path, expected in json.loads((BASE / "fixed_context/manifest.json").read_text())["input_sha256"].items():
        if sha(Path(path)) != expected:
            raise ValueError(f"Executed input changed: {path}")
    if sha(ROOT / "scripts/verify_biochemical_closure_diagnostic.py") != verification["verifier_sha256"]:
        raise ValueError("Verifier changed")
    if sha(BASE / "qa_results.xml") != verification["QA_sha256"]:
        raise ValueError("QA receipt changed")
    previous = ROOT / "output/rbc_gem_network_audit_2026_10_06"
    old = json.loads((previous / "final_manifest.json").read_text())
    for name, expected in old["archive_sha256"].items():
        if sha(previous / name) != expected:
            raise ValueError(f"Historical archive changed: {name}")
    protected = ("RBC/Rxn_RBC.txt", "src/parse.py", "src/equadiff_brodbar.py", "src/rbc_stoichiometry.py",
                 "src/reaction_positivity.py", "src/rbc_gem_network.py", "config/fla_working_reference.json")
    for name in protected:
        if sha(ROOT / name) != old["local_source_sha256"][name]:
            raise ValueError(f"Historical scientific input changed: {name}")
    names, reactions, matrix = biochemical_matrix("vcse_folate")
    catalogue = parse(str(BASE / "Rxn_RBC_biochemical_compartmented.txt"), strict=True)
    if catalogue is None or len(catalogue["react_name"]) != 112:
        raise ValueError("Historical parser rejected the extended catalogue")
    for index, reaction in enumerate(reactions):
        column = catalogue["react_name"].index(reaction)
        actual = {n: catalogue["S"][row, column] for row, n in enumerate(catalogue["int_met"])
                  if catalogue["S"][row, column]}
        actual.update({n: catalogue["ext"][row, column] for row, n in enumerate(catalogue["ext_met"])
                       if catalogue["ext"][row, column]})
        expected = {n: matrix[row, index] for row, n in enumerate(names) if matrix[row, index]}
        if actual != expected:
            raise ValueError(f"Second-parser mismatch: {reaction}")
    files = [*protected, "src/rbc_biochemical_extensions.py", "config/fla_biochemical_closure_diagnostic.json",
             "qa/test_rbc_biochemical_extensions.py", "scripts/audit_biochemical_closure_sources.py",
             "scripts/run_biochemical_closure_diagnostic.py", "scripts/verify_biochemical_closure_diagnostic.py",
             "scripts/seal_biochemical_closure_diagnostic.py", "tasks/fla_biochemical_closure_2026_10_06.md",
             "tasks/fla_current_tasks.md", "fla_progress_log.md", "manuscript.md"]
    hashes = {}
    for name in files:
        source = ROOT / name
        destination = snapshots / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        hashes[name] = sha(source)
        if sha(destination) != hashes[name]:
            raise ValueError("Snapshot differs from executed source")
    outputs = {path.relative_to(BASE).as_posix(): sha(path) for path in sorted(BASE.rglob("*"))
               if path.is_file() and path != final}
    manifest = {"status": "complete", "parent_archive_sha256": sha(previous / "final_manifest.json"),
                "protected_historical_inputs_unchanged": True, "biological_calibration": False,
                "second_parser_extended_catalogue_verified": True,
                "external_pools": len(catalogue["ext_met"]), "extended_catalogue_columns": len(reactions),
                "global_promotion": False, "OPLAH_deleted": False,
                "QA_passed": verification["QA_passed"], "QA_skipped": verification["QA_skipped"],
                "independent_checks_passed": verification["independent_checks_passed"],
                "local_source_sha256": hashes, "archive_sha256": outputs}
    final.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"archive_files_sealed": len(outputs), "local_sources_preserved": len(files),
                      "protected_historical_inputs_unchanged": True}, indent=2))


if __name__ == "__main__":
    main()
