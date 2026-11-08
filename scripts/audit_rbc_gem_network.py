"""Compare all executable reactions and export source-backed structural candidates."""

import csv
import hashlib
import json
from pathlib import Path
import sys

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rbc_gem_audit import catalog_differences, compare_network, parse_catalog
from rbc_stoichiometry import STOICHIOMETRY

OUT = ROOT / "output/rbc_gem_network_audit_2026_10_06"
ANALYSIS = OUT / "comparison_v2"
PRIORITIES = {
    "redox_stoichiometry": ("CAT", "XAO", "XAO2"),
    "arginase": ("ARGN",),
    "xanthine_salvage": ("XPPT",),
    "citrate_cytosolic": ("ACONT", "ICDHy", "ACITL"),
    "cystathionine_identity": ("CYSTL1", "CYSTL2", "CYSTS"),
    "folate_identity": ("GHMT2", "MTHFD", "MTHFC"),
    "methemoglobin": ("FCYTOB5OXR", "METHBCYTBR", "FMNRy", "METHBFMNR"),
    "thioredoxin_peroxiredoxin": ("TRDRy", "PRDX2TRDXRD", "PRDX2PX"),
    "nad_salvage_repair": ("NMNS", "NMNAT", "NADHXD", "NADHXE"),
    "alternative_glutathione_redox": ("GTHOx", "GTHOy"),
    "adenylate_partition": ("ADK1", "ADNK1", "AMPDA", "NTD7", "NTD8"),
    "energy_maintenance": ("ATPM", "NaKt", "ATPS4r"),
}


def save(name, value):
    (ANALYSIS / name).write_text(json.dumps(value, indent=2) + "\n")


def table(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def main():
    target = ANALYSIS / "network_comparison.json"
    if target.exists():
        raise FileExistsError("preserve the completed comparison")
    ANALYSIS.mkdir(exist_ok=False)
    model = json.loads((OUT / "github/1.3.0/model/RBC-GEM.json").read_text())
    published = json.loads((OUT / "github/1.2.0/model/RBC-GEM.json").read_text())
    comparison = compare_network(model, STOICHIOMETRY)
    sections, old = parse_catalog((OUT / "original_local_sources/Rxn_RBC.txt").read_text())
    comparison["original_catalog_differences"] = catalog_differences(old, STOICHIOMETRY)
    comparison["original_missing_declarations"] = sorted(set(old).difference(
        sections["ENZREV"] + sections["ENZIRREV"]))
    comparison["ode_reactions"] = len(STOICHIOMETRY)
    comparison["gem_counts"] = {"current": {key: len(model[key]) for key in ("reactions", "metabolites", "genes")},
                                "published": {key: len(published[key]) for key in ("reactions", "metabolites", "genes")}}
    old_reactions = {row["id"]: row for row in published["reactions"]}
    new_reactions = {row["id"]: row for row in model["reactions"]}
    comparison["version_changes"] = {
        "added": sorted(set(new_reactions).difference(old_reactions)),
        "removed": sorted(set(old_reactions).difference(new_reactions)),
        "stoichiometry_changed": [name for name in sorted(set(old_reactions) & set(new_reactions))
                                  if old_reactions[name]["metabolites"] != new_reactions[name]["metabolites"]],
        "gpr_changed": [name for name in sorted(set(old_reactions) & set(new_reactions))
                        if old_reactions[name]["gene_reaction_rule"] != new_reactions[name]["gene_reaction_rule"]],
    }
    save("network_comparison.json", comparison)
    evidence = {row["reactions"]: row for row in table(OUT / "github/1.3.0/data/curation/reactions_evidence.tsv")}
    priorities = {}
    for group, names in PRIORITIES.items():
        priorities[group] = {name: {"model_present": name in new_reactions,
                                   "model": new_reactions.get(name), "curation": evidence.get(name)}
                             for name in names}
    save("priority_reaction_evidence.json", priorities)
    with (ANALYSIS / "closed_unmatched_candidates.csv").open("w", newline="", encoding="utf-8") as stream:
        names = ["gem_id", "name", "gpr", "subsystem", "projected", "omitted_currency", "references"]
        writer = csv.DictWriter(stream, fieldnames=names, extrasaction="ignore")
        writer.writeheader()
        for row in comparison["closed_unmatched_candidates"]:
            writer.writerow({key: json.dumps(value) if isinstance(value, (dict, list)) else value
                             for key, value in row.items()})
    inventories = {}
    for filename in ("pcbi.1012109.s004.xlsx", "pcbi.1012109.s007.xlsx"):
        workbook = load_workbook(OUT / "supplements" / filename, read_only=True, data_only=True)
        try:
            inventories[filename] = [{"sheet": sheet.title, "rows": sheet.max_row, "columns": sheet.max_column,
                                      "preview": [list(row) for row in sheet.iter_rows(max_row=5, max_col=12,
                                                                                    values_only=True)]}
                                     for sheet in workbook]
        finally:
            workbook.close()
    save("supplement_workbook_inventory.json", inventories)
    for path in (ROOT / "src/equadiff_brodbar.py", ROOT / "src/reaction_positivity.py",
                 ROOT / "src/rbc_stoichiometry.py", ROOT / "src/Data_Bordbar_et_al_exp.xlsx"):
        hashes = json.loads((OUT / "original_local_hashes.json").read_text())
        relative = path.relative_to(ROOT).as_posix()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == hashes[relative]
    summary = {"ode_reactions": len(STOICHIOMETRY), "mapped_pools": len(comparison["pool_mapping"]),
               "projected_equivalences": sum(row["status"] == "projected_equivalent" for row in comparison["comparisons"]),
               "single_reaction_unmatched": sum(row["status"] == "no_single_reaction_match" for row in comparison["comparisons"]),
               "pool_identity_unresolved": sum(row["status"] == "pool_identity_unresolved" for row in comparison["comparisons"]),
               "closed_unmatched_candidates": len(comparison["closed_unmatched_candidates"]),
               "original_catalog_differences": len(comparison["original_catalog_differences"]),
               "gem_counts": comparison["gem_counts"], "version_changes": comparison["version_changes"],
               "scope": "Projected equivalence omits declared currency only; not biochemical or kinetic validation."}
    save("summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
