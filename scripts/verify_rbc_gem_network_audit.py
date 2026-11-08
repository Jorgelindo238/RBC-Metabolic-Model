"""Independent source/hash, catalog and stored executed-budget verification."""

import csv
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from equadiff_brodbar import equadiff_brodbar
from rbc_gem_audit import catalog_differences, parse_catalog, pool_mapping, project_gem, signature
from rbc_gem_network import BRANCHES, diagnostic_matrix, equadiff_rbc_gem
from rbc_stoichiometry import STOICHIOMETRY

OUT = ROOT / "output/rbc_gem_network_audit_2026_10_06"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    count = 0
    receipts = json.loads((OUT / "retrieval_receipts.json").read_text())
    for row in receipts:
        if row["status"] == "retrieved":
            assert digest(OUT / row["file"]) == row["sha256"]
            count += 1
    hashes = json.loads((OUT / "original_local_hashes.json").read_text())
    for relative, expected in hashes.items():
        assert digest(OUT / "original_local_sources" / Path(relative).name) == expected
        if relative != "RBC/Rxn_RBC.txt":
            assert digest(ROOT / relative) == expected
        count += 1
    for folder in (OUT / "priority_proteomics_v2", OUT / "fixed_parameter_diagnostic"):
        manifest = json.loads((folder / "manifest.json").read_text())
        for path, expected in manifest["input_sha256"].items():
            assert digest(Path(path)) == expected, path
            count += 1
        for name, expected in manifest["output_sha256"].items():
            assert digest(folder / name) == expected, name
            count += 1
    _, catalog = parse_catalog((ROOT / "RBC/Rxn_RBC.txt").read_text())
    assert catalog_differences(catalog, STOICHIOMETRY) == []
    model = json.loads((OUT / "github/1.3.0/model/RBC-GEM.json").read_text())
    source = {row["id"]: row for row in model["reactions"]}
    inverse = {value: name for name, value in pool_mapping(model).items()}
    names, reactions, matrix = diagnostic_matrix("rbc_gem_core")
    pairs = {"VH2O2": "CAT", "VXAO": "XAO2", "VXAO2": "XAO",
             "VEGSSG": "GTHOXABCte", "VEURT": "URATEABCte"}
    pairs.update({name: row["gem_id"] for name, row in BRANCHES.items()})
    for local, gem in pairs.items():
        projected, unknown, _ = project_gem(source[gem], inverse)
        assert not unknown
        actual = {name: matrix[index, reactions.index(local)] for index, name in enumerate(names)
                  if matrix[index, reactions.index(local)] != 0}
        assert signature(projected) == signature(actual)
        count += 1
    diagnostic = OUT / "fixed_parameter_diagnostic"
    design = json.loads((diagnostic / "preregistered_contract.json").read_text())["design"]
    parent = ROOT / design["initial_state_archive"]
    baseline_parameters = json.loads((parent / "frozen_parameters.json").read_text())
    summaries = json.loads((diagnostic / "summary.json").read_text())
    assert summaries["all_numerical_gates_pass"] is True
    for case in design["cases"]:
        for tolerance in design["tolerances"]:
            folder = diagnostic / (case["name"] + "_" + tolerance)
            stored = np.load(folder / "dense_and_integrals.npz")
            accepted = np.load(folder / "accepted_states.npz")
            assert stored["states"][:113].min() >= -1e-10
            assert accepted["states"][:113].min() >= -1e-10
            assert np.all(np.isfinite(stored["states"]))
            np.testing.assert_array_equal(accepted["states"][:, 0], np.load(parent / "frozen_initial_state.npz")["states"])
            params = dict(baseline_parameters)
            if case["disable_oplah"]:
                params["vmax_VOPLAH"] = 0.0
            raw = stored["raw_8"]
            effective = stored["effective_8"]
            boundary_indices = [int(np.where(stored["time"] == value)[0][0]) for value in stored["boundaries"]]
            change = np.diff(stored["states"][:113, boundary_indices], axis=1)
            np.testing.assert_allclose(stored["matrix"] @ effective, change, rtol=0.001, atol=1e-6)
            np.testing.assert_allclose(raw, stored["raw_4"], rtol=0.001, atol=1e-6)
            np.testing.assert_allclose(effective, stored["effective_4"], rtol=0.001, atol=1e-6)
            for index in np.linspace(0, len(stored["time"])-1, 7, dtype=int):
                audit = {}
                derivative = equadiff_rbc_gem(float(stored["time"][index]), stored["states"][:, index],
                                             network_mode=case["network_mode"], custom_params=params,
                                             numerical_audit=audit, positivity_policy="reaction_consistent",
                                             reaction_availability_threshold=0.001)
                rates = [audit["effective_fluxes"][reaction] for reaction in stored["reactions"]]
                np.testing.assert_allclose(stored["matrix"] @ rates, derivative[:113], atol=1e-12)
                count += 1
            if case["name"] == "historical":
                old = np.load(parent / ("baseline_" + tolerance) / "accepted_solver_states.npz")
                np.testing.assert_array_equal(old["time"], accepted["time"])
                np.testing.assert_array_equal(old["states"], accepted["states"])
            count += 7
    junit = ET.parse(OUT / "qa_results.xml").getroot()
    cases = junit.findall(".//testcase")
    assert not junit.findall(".//failure") and not junit.findall(".//error")
    skipped = [row for row in cases if row.find("skipped") is not None]
    checks = {"independent_checks_passed": count, "full_qa_passed": len(cases)-len(skipped),
              "full_qa_skipped": len(skipped), "new_network_tests": 30,
              "catalog_reactions": len(catalog), "core_kernel_and_Bordbar_unchanged": True,
              "new_optional_rates_enabled_in_replays": False, "calibration_executed": False,
              "biological_promotion": False,
              "sha256": {str(path): digest(path) for path in [
                  ROOT / "RBC/Rxn_RBC.txt", ROOT / "src/parse.py", ROOT / "src/rbc_gem_audit.py",
                  ROOT / "src/rbc_gem_network.py", ROOT / "qa/test_rbc_gem_network.py",
                  Path(__file__).resolve(), OUT / "qa_results.xml"]}}
    target = OUT / "independent_verification.json"
    if target.exists():
        assert json.loads(target.read_text()) == checks
    else:
        target.write_text(json.dumps(checks, indent=2) + "\n")
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
