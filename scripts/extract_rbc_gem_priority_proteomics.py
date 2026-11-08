"""Extract priority longitudinal abundances without converting them to kinetics."""

import csv
import hashlib
import json
import math
from pathlib import Path
import re

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/rbc_gem_network_audit_2026_10_06/priority_proteomics_v2"
PRIOR = ROOT / "output/palsson_proteomics_review_2026_10_06"
GENES = frozenset("HK1 GPI PFKL PFKM PFKP ALDOA TPI1 GAPDH PGK1 BPGM PGAM1 PGAM2 ENO1 PKLR PKM LDHA LDHB "
                  "G6PD PGLS PGD RPIA RPE TKT TALDO1 AK1 ADK AMPD3 HPRT1 GMPR GMPR2 GSR GCLC GCLM GSS "
                  "ARG1 ACYP1 ACYP2 ADPGK OPLAH ASRGL1 GDA GLUD1 MTR MTHFR ACLY ACO1 IDH1 ME1 MDH1 "
                  "CYB5R3 CYB5A CYB5B BLVRB PRDX2 TXN TXNRD1 NAXD NAXE NAMPT NMNAT3 NADK NADK2 "
                  "ABCC1 ABCC4 ABCG2 ATP1A1 ATP1B1 ATP2B4 ATP11C TMEM30A PCMT1 SLC4A1 SLC2A1 SLC16A1".split())


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    OUT.mkdir(exist_ok=False)
    source = PRIOR / "retrieved_sources/pcbi.1012109.s008.xlsx"
    expected = "e951fe9c4a5bb94913a10e6c31296ca59c7ddb7aa430cd6d70c9946944f86f45"
    assert sha(source) == expected
    with (PRIOR / "human_protein_copy_numbers.csv").open(newline="") as stream:
        deep = [row for row in csv.DictReader(stream) if row["gene"] in GENES]
    uniprot_to_genes = {}
    for row in deep:
        uniprot_to_genes.setdefault(row["uniprot_id"], set()).add(row["gene"])
    workbook = load_workbook(source, read_only=True, data_only=True)
    counts, selected, header_order = {}, {}, {}
    try:
        proteins = list(workbook["Table A"].iter_rows(values_only=True))
        keys = proteins[0]
        for row in proteins[1:]:
            gene, accession = row[keys.index("genes")], row[keys.index("uniprot")]
            if gene in GENES and accession:
                uniprot_to_genes.setdefault(accession, set()).add(gene)
        donors = list(workbook["Table F"].iter_rows(values_only=True))
        donor_ids = [row[0] for row in donors[1:]]
        assert len(donor_ids) == len(set(donor_ids)) == 616
        with (OUT / "donor_metadata.csv").open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["source_sheet_row", *donors[0]])
            writer.writerows([index, *row] for index, row in enumerate(donors[1:], 2))
        samples = None
        for sheet_name, unit in (("Table D", "nmol protein / gDW sample"), ("Table E", "copies/cell")):
            sheet = workbook[sheet_name]
            iterator = sheet.iter_rows(values_only=True)
            header = next(iterator)
            labels = list(header[1:])
            if samples is None:
                samples = labels
            assert set(samples) == set(labels) and len(set(labels)) == len(labels) == 1848
            header_order[sheet_name] = labels
            parsed = []
            for label in labels:
                match = re.fullmatch(r"(S\d+)_D(10|23|42)", label)
                assert match is not None and match[1] in donor_ids
                parsed.append((match[1], int(match[2])))
            assert len(set(parsed)) == 616 * 3
            path = OUT / (sheet_name.replace(" ", "_") + "_priority_observations.csv")
            rows = missing = zeros = 0
            found = {}
            with path.open("w", newline="") as stream:
                fields = ["sheet", "source_row", "source_column", "uniprot", "candidate_genes",
                          "sample_id", "donor_id", "storage_day", "reported_value", "reported_unit",
                          "missing", "estimated_abundance", "training_enabled"]
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                for source_row, row in enumerate(iterator, 2):
                    accession = row[0]
                    if accession not in uniprot_to_genes:
                        continue
                    assert accession not in found
                    found[accession] = sorted(uniprot_to_genes[accession])
                    for index, (label, pair, value) in enumerate(zip(labels, parsed, row[1:]), 2):
                        if value is not None:
                            assert not isinstance(value, bool) and isinstance(value, (int, float))
                            assert math.isfinite(value) and value >= 0
                        writer.writerow({"sheet": sheet_name, "source_row": source_row, "source_column": index,
                                         "uniprot": accession, "candidate_genes": "|".join(found[accession]),
                                         "sample_id": label, "donor_id": pair[0], "storage_day": pair[1],
                                         "reported_value": value, "reported_unit": unit, "missing": value is None,
                                         "estimated_abundance": True, "training_enabled": False})
                        rows += 1
                        missing += value is None
                        zeros += value == 0
            counts[sheet_name] = {"selected_proteins": len(found), "observations": rows,
                                  "missing": missing, "reported_zero": zeros, "unit": unit}
            selected[sheet_name] = found
        assert selected["Table D"] == selected["Table E"]
        with (OUT / "Deep_Red_priority_copy_numbers.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(deep[0]))
            writer.writeheader()
            writer.writerows(deep)
        summary = {"source_sha256": expected, "selected_gene_request": sorted(GENES),
                   "counts": counts, "selected": selected["Table E"], "donors": 616,
                   "samples": 1848, "no_gDW_to_mM_conversion": True,
                   "sample_columns_in_different_positions": sum(a != b for a, b in zip(
                       header_order["Table D"], header_order["Table E"])),
                   "join_policy": "Explicit sample_id keys, never source-column position across tables",
                   "missing_values_imputed": False, "kinetic_parameters_generated": False,
                   "training_enabled": False,
                   "warning": "Table D and E are two representations of the same estimate, not independent assays."}
        (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    finally:
        workbook.close()
    manifest = {"input_sha256": {str(source): expected,
                                  str(PRIOR / "human_protein_copy_numbers.csv"): sha(PRIOR / "human_protein_copy_numbers.csv"),
                                  str(Path(__file__).resolve()): sha(Path(__file__).resolve())},
                "output_sha256": {path.name: sha(path) for path in OUT.iterdir() if path.is_file()}}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"counts": counts, "donors": 616, "not_in_S6": sorted(
        GENES - {gene for genes in selected["Table E"].values() for gene in genes})}, indent=2))


if __name__ == "__main__":
    main()
