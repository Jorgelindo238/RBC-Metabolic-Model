"""Reconstruct source columns, saved budgets, initial states and redox ledgers."""

import csv
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fla_working_reference import load_working_reference, reference_options
from rbc_biochemical_extensions import BRANCHES, NEW_POOLS, REDOX_GROUPS, biochemical_matrix, equadiff_biochemical, extension_rates
from rbc_gem_audit import parse_catalog
from reaction_positivity import limit_signed_fluxes

BASE = ROOT / "output/biochemical_closure_2026_10_06"
OUT = BASE / "fixed_context"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    receipt = BASE / "independent_verification.json"
    if receipt.exists():
        raise FileExistsError("Preserve the existing verification receipt")
    count = 0
    def require(condition, message):
        nonlocal count
        if not condition:
            raise ValueError(message)
        count += 1
    manifest = json.loads((OUT / "manifest.json").read_text())
    for path, expected in manifest["input_sha256"].items():
        require(sha(Path(path)) == expected, f"Changed campaign input: {path}")
    for name, expected in manifest["output_sha256"].items():
        require(sha(OUT / name) == expected, f"Changed campaign output: {name}")
    parent = ROOT / "output/rbc_gem_network_audit_2026_10_06"
    old_seal = json.loads((parent / "final_manifest.json").read_text())
    for name, expected in old_seal["archive_sha256"].items():
        require(sha(parent / name) == expected, f"Changed parent archive: {name}")
    source = json.loads((BASE / "source_audit.json").read_text())
    require(source["corrected_VCSE_carbon_residual"] == 0, "CSE carbon")
    require(all(value == 0 for value in source["VCSE_composite_atom_residual"].values()), "Full composite CSE atoms")
    require(source["GEM_METHBCYTBR_charge_residual"] == 1, "Source metHb charge caveat")
    require(source["GEM_METHBCYTBR_reduced_electron_equivalent_residual"] == -1, "Source metHb electron caveat")
    require(source["OPLAH_Deep_Red_source_rows"][0]["uniprot_id"] == "O14841", "OPLAH conflict identity")
    for item in source["UniProt_retrieval"]:
        require(item["retrieved"], "Primary chemistry source unavailable")
        require(sha(BASE / f"primary_sources/UniProt_{item['uniprot']}.json") == item["sha256"], "Primary source hash")
    uniprot = json.loads((BASE / "primary_sources/UniProt_P42898.json").read_text())
    require(any(p["directionType"] == "right-to-left" for c in uniprot["comments"]
                if c["commentType"] == "CATALYTIC ACTIVITY" for p in c.get("physiologicalReactions", [])),
            "Human MTHFR forward physiological orientation")
    gem = json.loads((parent / "github/1.3.0/model/RBC-GEM.json").read_text())
    gem_reactions = {r["id"]: r for r in gem["reactions"]}
    names, reactions, matrix = biochemical_matrix("vcse_folate")
    mapping = {"SER": "ser__L_c", "THF": "thf_c", "GLY": "gly_c", "MLTHF": "mlthf_c",
               "NADH": "nadh_c", "NAD": "nad_c", "CYB5OX": "ficytb5_c", "CYB5RED": "focytb5_c",
               "NADP": "nadp_c", "NADPH": "nadph_c", "TXNOX": "trdxox_c", "TXNRED": "trdxrd_c",
               "PRDXRED": "prdx2crd_c", "PRDXSO": "prdx2cso_c", "PRDXOX": "prdx2cox_c", "H2O2": "h2o2_c"}
    inverse = {v: k for k, v in mapping.items()}
    for local, external in (("VSHMT", "GHMT2"), ("VCYB5R", "FCYTOB5OXR"), ("VTRXR", "TRDRy"),
                            ("VPRDX_PEROX", "PRDX2OX1"), ("VPRDX_RESOLVE", "PRDX2SOR"), ("VPRDX_REDUCE", "PRDX2TRDXRD")):
        projected = {inverse[m]: v for m, v in gem_reactions[external]["metabolites"].items()
                     if m not in ("h_c", "h2o_c")}
        actual = {n: matrix[i, reactions.index(local)] for i, n in enumerate(names) if matrix[i, reactions.index(local)]}
        require(actual == projected, f"Source column mismatch: {local}")
    column = matrix[:, reactions.index("VMETHB_RED")]
    require(sum(column[names.index(n)] * w for n, w in {"CYB5RED": 1, "HBFE2": 1}.items()) == 0,
            "Corrected one-heme-site electron transfer")
    contract = json.loads((OUT / "preregistered_contract.json").read_text())
    design = contract["design"]
    seed = ROOT / design["initial_state_archive"]
    initial = np.load(seed / "frozen_initial_state.npz")["states"]
    params = json.loads((seed / "frozen_parameters.json").read_text())
    ref = load_working_reference(ROOT / design["working_reference"])
    controls = ref["validation_before_calibration"]
    records = []
    def close(a, b, kind="quadrature"):
        return np.abs(a-b) <= controls[kind + "_atol_mM"] + controls[kind + "_rtol"] * np.maximum(abs(a), abs(b))
    for case in [*design["cases"], *contract["synthetic_cases"]]:
        synthetic = case["name"].startswith("synthetic_")
        pair = []
        for tolerance in design["tolerances"]:
            folder = OUT / (case["name"] + "_" + tolerance)
            data = np.load(folder / "dense_and_integrals.npz")
            accepted = np.load(folder / "accepted_states.npz")
            pool_names = tuple(data["pool_names"])
            reaction_names = tuple(data["reactions"])
            s = data["matrix"]
            if synthetic:
                expected_matrix = matrix[:, [reactions.index(r) for r in case["reactions"]]]
                require(np.array_equal(accepted["states"][:, 0], case["initial"]), "Synthetic initial state")
            else:
                _, _, expected_matrix = biochemical_matrix(case["mode"])
                require(len(contract["measured_pools"]) == 55, "55 measured channels")
                for pool in contract["measured_pools"]:
                    require(accepted["states"][pool_names.index(pool), 0] == initial[names.index(pool)], "Exact measured J1")
                for index in range(114):
                    if index == 47 and case["methyl_fraction"] is not None:
                        require(accepted["states"][47, 0] + accepted["states"][pool_names.index("MLTHF"), 0] == initial[47],
                                "Conditional latent folate total")
                    else:
                        require(accepted["states"][index if index < 113 else -1, 0] == initial[index], "Frozen historical entry")
                require(np.all(accepted["states"][113:, 0][[i for i in range(len(NEW_POOLS)) if NEW_POOLS[i] != "MLTHF"]] == 0),
                        "Declared null-probe C4/redox initial values")
                require(np.all(data["effective_8"][[reaction_names.index(r) for r in BRANCHES]] == 0),
                        "New biological rates must be inactive")
            require(np.array_equal(s, expected_matrix), "Recorded matrix")
            require(np.isfinite(accepted["states"]).all() and np.isfinite(data["states"]).all(), "Finite raw states")
            require(min(accepted["states"][:124].min(), data["states"][:124].min()) >= controls["negative_state_tolerance_mM"],
                    "Raw checked positivity")
            for kind in ("raw", "effective"):
                require(close(data[kind + "_4"], data[kind + "_8"]).all(), "Rate quadrature")
            boundaries = data["boundaries"]
            index = [int(np.flatnonzero(np.isclose(data["time"], day, rtol=0, atol=1e-12))[0]) for day in boundaries]
            increments = np.diff(data["states"][:124, index], axis=1)
            require(close(increments, s @ data["effective_8"]).all(), "Independent integrated pool budgets")
            for pools in (("NAD", "NADH"), ("NADP", "NADPH"), ("CYB5OX", "CYB5RED"), ("HBFE3", "HBFE2"),
                          ("TXNOX", "TXNRED"), ("PRDXRED", "PRDXSO", "PRDXOX")):
                rows = [pool_names.index(n) for n in pools]
                total = data["states"][rows].sum(0)
                require(np.max(abs(total-total[0])) <= 1e-7, f"Pool conservation: {pools}")
            if "MTHF" in pool_names:
                rows = [pool_names.index(n) for n in ("THF", "MTHF", "MLTHF")]
                total = data["states"][rows].sum(0)
                require(np.max(abs(total-total[0])) <= 1e-7, "Separate folate conservation")
            for sample in np.linspace(0, data["time"].size - 1, 7, dtype=int):
                point, time = data["states"][:, sample], float(data["time"][sample])
                if synthetic:
                    native = extension_rates(point, pool_names, case["kinetics"])
                    raw = np.array([native[r] for r in reaction_names])
                    effective, _ = limit_signed_fluxes(point, raw, s, threshold=ref["profile"]["reaction_availability_threshold_mM"])
                    dx = s @ effective
                else:
                    options, _ = reference_options(ref, ultrastrict=tolerance == "ultrastrict")
                    audit = {}
                    dx = equadiff_biochemical(time, point, network_mode=case["mode"], oplah_policy=case["oplah_policy"],
                                              custom_params=params, numerical_audit=audit, **options)[:-1]
                    raw = np.array([audit["raw_fluxes"][r] for r in reaction_names])
                    effective, _ = limit_signed_fluxes(point[:-1], raw, s, threshold=ref["profile"]["reaction_availability_threshold_mM"])
                require(np.allclose(dx, s @ effective, rtol=0, atol=1e-13), "Independent executed limiter replay")
            if synthetic:
                weights = ({"NADH": 2, "CYB5RED": 1, "HBFE2": 1} if case["name"] == "synthetic_metHb"
                           else {"NADPH": 2, "TXNRED": 2, "PRDXRED": 2, "H2O2": -2})
                ledger = sum(data["states"][pool_names.index(n)] * w for n, w in weights.items())
                require(np.max(abs(ledger-ledger[0])) <= 1e-7, "Synthetic electron ledger")
                donor = "NADH" if case["name"] == "synthetic_metHb" else "NADPH"
                oxidants = ("CYB5OX", "HBFE3") if donor == "NADH" else ("TXNOX", "PRDXOX", "H2O2")
                bound = sum(data["states"][pool_names.index(n), 0] for n in oxidants) / (2 if donor == "NADH" else 1)
                consumption = data["states"][pool_names.index(donor), 0] - data["states"][pool_names.index(donor), -1]
                require(0 < consumption <= bound + 1e-8, "Finite oxidant-bound donor consumption")
                require(np.all(data["states"][pool_names.index("ATP")] == 0), "No synthetic ATP source")
            else:
                oplah = data["effective_8"][reaction_names.index("VOPLAH")]
                require(np.all(oplah == 0) if case["oplah_policy"] == "diagnostic_off" else oplah.sum() > 0,
                        "OPLAH retained unless named countertest")
            result = json.loads((folder / "result.json").read_text())
            require(result["numerical_pass"], "Runner numerical gate")
            pair.append(data)
            records.append({"case": folder.name, "ATP": result["ATP_endpoint"],
                            "ADP": result["ADP_endpoint"], "AMP": result["AMP_endpoint"]})
        left, right = pair
        common, li, ri = np.intersect1d(left["time"], right["time"], return_indices=True)
        require(common.size >= 601, "Common verification grid")
        require(close(left["states"][:124, li], right["states"][:124, ri], "comparison").all(), "Independent common-grid convergence")
        for kind in ("raw", "effective"):
            require(close(left[kind + "_8"], right[kind + "_8"], "comparison").all(), "Independent integral convergence")
    # Export the same matrix with explicit internal/external declarations.
    old_sections, _ = parse_catalog((ROOT / "RBC/Rxn_RBC.txt").read_text())
    external = set(old_sections["METEXT"])
    reversible = set(old_sections["ENZREV"]) - {"VCSE"}
    lines = ["# Opt-in extended diagnostic. All new rates require explicit kinetics.",
             "# OPLAH retained; HBFE pools use single heme sites; currency protons/water omitted.",
             "# Historical arrow declarations do not validate kinetic reversibility.",
             "-ENZREV", " ".join(r for r in reactions if r in reversible),
             "-ENZIRREV", " ".join(r for r in reactions if r not in reversible),
             "-METINT", " ".join(n for n in names if n not in external),
             "-METEXT", " ".join(n for n in names if n in external), "-CAT"]
    def terms(column, sign):
        return " + ".join(("" if abs(v) == 1 else f"{abs(v):g} ") + n
                          for n, v in zip(names, column) if v * sign > 0)
    for index, reaction in enumerate(reactions):
        arrow = "=" if reaction in reversible else "=>"
        lines.append(f"{reaction} : {terms(matrix[:, index], -1)} {arrow} {terms(matrix[:, index], 1)}")
    text = "\n".join(lines) + "\n"
    sections, catalogue = parse_catalog(text)
    require(set(sections["METEXT"]) == external, "External pool declarations")
    for index, reaction in enumerate(reactions):
        expected = {n: matrix[i, index] for i, n in enumerate(names) if matrix[i, index]}
        require(catalogue[reaction] == expected, f"Extended catalogue column: {reaction}")
    destination = BASE / "Rxn_RBC_biochemical_compartmented.txt"
    require(not destination.exists(), "Preserve generated catalogue")
    destination.write_text(text)
    tree = ET.parse(BASE / "qa_results.xml")
    suites = list(tree.getroot().iter("testsuite"))
    total = sum(int(s.attrib["tests"]) for s in suites)
    skips = sum(int(s.attrib.get("skipped", 0)) for s in suites)
    require(sum(int(s.attrib.get(k, 0)) for s in suites for k in ("errors", "failures")) == 0, "QA failures")
    summary = json.loads((OUT / "summary.json").read_text())
    require(summary["all_numerical_gates_pass"], "Campaign convergence gate")
    result = {"independent_checks_passed": count, "free_Bordbar_replays": 10, "synthetic_redox_replays": 4,
              "QA_passed": total-skips, "QA_skipped": skips,
              "new_biological_redox_kinetics_activated": False, "OPLAH_deleted": False,
              "biological_calibration": False, "global_promotion": False,
              "verification_scope": "stored budgets, source columns, seven live RHS/limiter samples per replay, common stored grids; not independent recomputation of Gauss-node integrands",
              "endpoint_records": records, "verifier_sha256": sha(Path(__file__).resolve()),
              "QA_sha256": sha(BASE / "qa_results.xml"), "compartmented_catalogue_sha256": sha(destination)}
    receipt.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("independent_checks_passed", "free_Bordbar_replays",
                                                 "synthetic_redox_replays", "QA_passed", "QA_skipped")}, indent=2))


if __name__ == "__main__":
    main()
