"""Preserve primary chemistry evidence and audit the targeted GEM coefficients."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from rbc_biochemical_extensions import biochemical_matrix


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / "output/biochemical_closure_2026_10_06")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(exist_ok=False)
    source_dir = out / "primary_sources"
    source_dir.mkdir()
    prior = ROOT / "output/rbc_gem_network_audit_2026_10_06"
    gem_path = prior / "github/1.3.0/model/RBC-GEM.json"
    final = json.loads((prior / "final_manifest.json").read_text())
    for name, expected in final["archive_sha256"].items():
        if sha(prior / name) != expected:
            raise ValueError(f"Parent archive changed: {name}")
    model = json.loads(gem_path.read_text())
    reactions = {r["id"]: r for r in model["reactions"]}
    metabolites = {m["id"]: m for m in model["metabolites"]}
    selected = ("CYSTL1", "2ABUTENT", "2IMBUTDA", "GHMT2", "FCYTOB5OXR", "METHBCYTBR",
                "TRDRy", "PRDX2OX1", "PRDX2SOR", "PRDX2TRDXRD")
    evidence = {"pinned_GEM_sha256": sha(gem_path), "reactions": {r: reactions[r] for r in selected},
                "metabolites": {m: metabolites[m] for r in selected for m in reactions[r]["metabolites"]}}
    (source_dir / "pinned_GEM_targeted_evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    receipts, catalytic = [], {}
    for accession in ("P32929", "P42898", "Q99707", "P00387", "O14841"):
        url = f"https://rest.uniprot.org/uniprotkb/{accession}.json"
        receipt = {"uniprot": accession, "url": url}
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "AIRBC-source-audit/1.0"})
            with urllib.request.urlopen(request, timeout=45) as response:
                payload = response.read(2_000_001)
                receipt["http_status"] = response.status
            if len(payload) > 2_000_000:
                raise ValueError("Unexpectedly large source")
            data = json.loads(payload)
            if data["primaryAccession"] != accession:
                raise ValueError("Accession mismatch")
            path = source_dir / f"UniProt_{accession}.json"
            path.write_bytes(payload)
            receipt.update({"retrieved": True, "sha256": sha(path)})
            catalytic[accession] = [c for c in data.get("comments", [])
                                    if c["commentType"] in ("CATALYTIC ACTIVITY", "FUNCTION", "COFACTOR")]
        except Exception as error:
            receipt.update({"retrieved": False, "error": str(error)})
        receipts.append(receipt)
    (source_dir / "retrieval_receipts.json").write_text(json.dumps(receipts, indent=2) + "\n")
    (source_dir / "UniProt_catalytic_annotations.json").write_text(json.dumps(catalytic, indent=2) + "\n")
    composite = {}
    for reaction in ("CYSTL1", "2ABUTENT", "2IMBUTDA"):
        for name, coefficient in reactions[reaction]["metabolites"].items():
            composite[name] = composite.get(name, 0) + coefficient
    composite = {name: value for name, value in composite.items() if value}
    def atoms(formula):
        counts = {}
        for atom, count in re.findall(r"([A-Z][a-z]?)(\d*)", formula):
            counts[atom] = counts.get(atom, 0) + int(count or 1)
        return counts
    atom_residual = {}
    for name, coefficient in composite.items():
        for atom, count in atoms(metabolites[name]["formula"]).items():
            atom_residual[atom] = atom_residual.get(atom, 0) + coefficient * count
    if any(atom_residual.values()):
        raise ValueError("GEM composite CSE formula imbalance")
    names, rxns, matrix = biochemical_matrix("vcse_folate")
    cse = matrix[:, rxns.index("VCSE")]
    carbon = sum(cse[names.index(n)] * c for n, c in {"CYSTHIO": 7, "CYS": 3, "AKB": 4}.items())
    if carbon != 0:
        raise ValueError("Corrected VCSE carbon imbalance")
    gem_methb = reactions["METHBCYTBR"]["metabolites"]
    charge_residual = sum(value * metabolites[name]["charge"] for name, value in gem_methb.items())
    electron_residual = gem_methb["focytb5_c"] + gem_methb["hb_c"]
    with (ROOT / "output/palsson_proteomics_review_2026_10_06/human_protein_copy_numbers.csv").open(newline="") as stream:
        oplah = [row for row in csv.DictReader(stream) if row["gene"] == "OPLAH"]
    summary = {"parent_archive_files_verified": len(final["archive_sha256"]),
               "VCSE_composite_GEM_reaction": composite, "VCSE_composite_atom_residual": atom_residual,
               "corrected_VCSE_carbon_residual": carbon,
               "GEM_METHBCYTBR_charge_residual": charge_residual,
               "GEM_METHBCYTBR_reduced_electron_equivalent_residual": electron_residual,
               "corrected_metHb_basis": "one Fe heme site; one cytochrome electron per site; not Hb tetramer",
               "OPLAH_Deep_Red_source_rows": oplah,
               "OPLAH_policy": "retained by default; named diagnostic_off countertest only",
               "missing_activity_or_pool_evidence_imputed": False,
               "biological_redox_kinetics_available": False,
               "MTHFR_MTR_presence_in_mature_RBC_established": False,
               "UniProt_retrieval": receipts}
    (out / "source_audit.json").write_text(json.dumps(summary, indent=2) + "\n")
    # This catalogue belongs to the extended diagnostic registry, not the old 113-pool parser.
    def terms(column, sign):
        parts = []
        for name, value in zip(names, column):
            if value * sign > 0:
                amount = abs(value)
                parts.append(("" if amount == 1 else f"{amount:g} ") + name)
        return " + ".join(parts)
    lines = ["# GENERATED diagnostic matrix; not the historical production catalogue.",
             "# OPLAH retained. HBFE pools are heme-site mM. H/H2O/Pi/PPi/CO2 omitted.",
             "# Arrows encode signs only, not kinetic reversibility. New kinetics disabled unless explicit.",
             "-ENZIRREV", " ".join(rxns), "-METINT", " ".join(names), "-CAT"]
    for index, reaction in enumerate(rxns):
        lines.append(f"{reaction} : {terms(matrix[:, index], -1)} => {terms(matrix[:, index], 1)}")
    (out / "Rxn_RBC_biochemical_diagnostic.txt").write_text("\n".join(lines) + "\n")
    print(json.dumps({key: summary[key] for key in ("parent_archive_files_verified",
        "corrected_VCSE_carbon_residual", "GEM_METHBCYTBR_charge_residual",
        "GEM_METHBCYTBR_reduced_electron_equivalent_residual")}, indent=2))


if __name__ == "__main__":
    main()
