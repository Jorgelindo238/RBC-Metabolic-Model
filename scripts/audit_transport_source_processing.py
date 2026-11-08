"""Read-only source audit: normalization gaps and candidate ABL90 pH lineage."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import urllib.request

import openpyxl
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
JBC = ROOT / "output/jbc_supplements_ingestion_2026_10_06/source_files/jbc.M117.804914-1.xlsx"
SUPP = JBC.with_name("jbc.M117.804914-2.pdf")
BORD = ROOT / "src/Data_Bordbar_et_al_exp.xlsx"
SOURCES = {
    "ABL90_IFU.pdf": "https://www.ruh.nhs.uk/pathology/documents/poct/SOP_Radiometer_ABL90_Flex_IFU_Instructions.pdf",
    "Yurkovich2017_main.pdf": "https://escholarship.org/content/qt0sr6z0s2/qt0sr6z0s2_noSplash_6333de8b1ea4fabcf42d26fe47bd95c7.pdf?t=ruozkr"
}


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def ph22_candidate(ph37, *, coefficient=.0147):
    return ph37 + 15 * (coefficient + .0065 * (ph37 - 7.4))


def calculate():
    wb = openpyxl.load_workbook(JBC, data_only=False)
    bw = openpyxl.load_workbook(BORD, data_only=False)
    try:
        formula_cells = [{"sheet": s.title, "cell": c.coordinate, "formula": c.value}
                         for s in wb for row in s for c in row if c.data_type == "f"]
        bord_formulas = [c.coordinate for row in bw["Sheet1"] for c in row if c.data_type == "f"]
        table = []
        for row in wb["assay"].iter_rows(min_row=3):
            y, z = row[24], row[25]
            if y.value is None:
                continue
            for c in (y, z):
                if c.data_type == "f" or isinstance(c.value, bool) or not isinstance(c.value, (int, float)):
                    raise ValueError("unusable source pH cell")
            prediction = ph22_candidate(y.value)
            residual = z.value - prediction
            # Both source values are displayed to three decimals. Input rounding propagates.
            rounding = .0005 * (1 + 1 + 15 * .0065)
            table.append({"pH37_source_cell": "assay!" + y.coordinate, "pH22_source_cell": "assay!" + z.coordinate,
                "pH37_reported": y.value, "pH22_reported": z.value, "ABL90_candidate_pH22": prediction,
                "residual_pH": residual, "rounding_bound_pH": rounding,
                "compatible_with_rounding": abs(residual) <= rounding + 1e-12,
                "previous_analyzer_0146_candidate": ph22_candidate(y.value, coefficient=.0146),
                "independent_measurement_verified": False, "use_as_4C_pHe": False})
        if len(table) != 126 or not all(r["compatible_with_rounding"] for r in table):
            raise ValueError("candidate correction/source rounding relation changed")
        summary = {"JBC_pH_pairs": len(table), "compatible_pairs": sum(r["compatible_with_rounding"] for r in table),
            "maximum_candidate_residual_pH": max(abs(r["residual_pH"]) for r in table),
            "rounding_bound_pH": table[0]["rounding_bound_pH"],
            "JBC_formula_count": len(formula_cells), "JBC_defined_names": list(wb.defined_names),
            "Bordbar_Sheet1_formula_count": len(bord_formulas),
            "pH22_status": "strong_candidate_ABL90_derived_value_inference_not_author_confirmed",
            "pH22_independent_likelihood_allowed": False, "pH4_extrapolation_allowed": False,
            "cell_water_fraction_established": False, "endo_denominator_established": False,
            "analyte_recovery_fraction_established": False, "source_observations_changed": False,
            "biological_readiness_changed": False}
        inventory = {"JBC_sheets": wb.sheetnames, "JBC_formulas": formula_cells,
            "assay_headers": [{"cell": c.coordinate, "label": c.value, "unit": wb["assay"].cell(2, c.column).value}
                              for c in wb["assay"][1] if c.value is not None],
            "Bordbar_Sheet1_formulas": bord_formulas,
            "Bordbar_named_ranges": {k: v.attr_text for k, v in bw.defined_names.items()}}
        return table, summary, inventory
    finally:
        wb.close()
        bw.close()


def pdf_inventory(path):
    reader = PdfReader(path)
    words = ("normaliz", "recovery", "hematocrit", "22", "pH", "internal standard", "reconstitut")
    matches = []
    for i, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        hits = [word for word in words if word.lower() in text.lower()]
        if hits:
            matches.append({"pdf_page": i, "search_terms_present": hits})
    return {"pdf_pages": len(reader.pages), "keyword_page_index": matches,
            "note": "Keyword presence/absence is routing evidence, not proof of a normalization formula."}


def fetch_pdf(url, path):
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "AIRBC-source-audit/1.0"})
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read(20_000_001)
            if len(body) > 20_000_000 or not body.startswith(b"%PDF-"):
                raise ValueError("not a bounded PDF response")
        # Downloading an unmodified source, not authoring a document.
        path.write_bytes(body)
        receipt = pdf_inventory(path)
        return {"url": url, "downloaded": True, "sha256": sha(path), **receipt}
    except Exception as error:
        return {"url": url, "downloaded": False, "error": str(error), "TLS_verification_disabled": False}


def build(out, fetch):
    if out.exists():
        raise ValueError("use a fresh archive directory")
    table, summary, inventory = calculate()
    out.mkdir(parents=True)
    with (out / "pH_temperature_lineage.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(table[0]))
        writer.writeheader()
        writer.writerows(table)
    write_json(out / "summary.json", summary)
    write_json(out / "workbook_inventory.json", inventory)
    write_json(out / "supplement_page_index.json", pdf_inventory(SUPP))
    receipts = {name: fetch_pdf(url, out / name) if fetch else {"url": url, "downloaded": False, "not_requested": True}
                for name, url in SOURCES.items()}
    write_json(out / "retrieval_receipts.json", receipts)
    evidence = [
        {"id": "pH_temperature_candidate", "location": "ABL90 IFU ch11 p276, PDF page296; original assay!Y/Z126 pairs",
         "finding": "Published ABL90 equation matches126 paired values within two-channel rounding. Strong derived-channel hypothesis, not provenance certification.",
         "action": "Treat as one potentially shared observation group; do not count pH22 as independent pH information or extrapolate to4C.", "url": SOURCES["ABL90_IFU.pdf"]},
        {"id": "extraction", "location": "user-supplied supplement PDF p2",
         "finding": "Separate pellet/fluid extraction and isotope standards; quantitative calibration tables pp5-6. Final phase denominator, correction factors and free-water mapping remain unspecified in audited material.",
         "action": "Request the sample-specific amount-to-concentration processing export; standards do not establish100% recovery."},
        {"id": "local_Bordbar", "location": "src/Data_Bordbar_et_al_exp.xlsx Sheet1 and Feuil1 named ranges",
         "finding": "Sheet1 numeric concentrations have no formulas. cellbb names a coefficient import on Feuil1, not the original concentration normalization.",
         "action": "Keep J1 and all55 concentrations unchanged; request the original measurement/normalization export rather than just cellbb.txt."},
        {"id": "main_methods", "location": "Yurkovich main article PDF p7, Experimental procedures",
         "finding": "Read via institutional primary PDF. Analytical modes/calibration and model flux normalization are different operations; no direct per-cell-water operator is established here.",
         "action": "Do not import uFBA concentration conventions into the selected cell/supernatant branch.", "url": SOURCES["Yurkovich2017_main.pdf"]}
    ]
    write_json(out / "evidence_and_actions.json", evidence)
    report = f"""# Targeted transport source-processing audit

## New finding

All126 original pH37/pH22 pairs agree with the documented ABL90 candidate correction within rounding:

```text
pH22 = pH37 +15*(0.0147+0.0065*(pH37-7.40))
```

Maximum absolute residual is {summary['maximum_candidate_residual_pH']:.9f}; the bound propagated from two three-decimal observations is {summary['rounding_bound_pH']:.9f}. This is a strong INFERENCE of calculated-channel provenance, not an author-confirmed processing chain. Matching cannot establish that these are independent measurements. The manufacturer equation is documented in [ABL90 Instructions for Use](https://www.ruh.nhs.uk/pathology/documents/poct/SOP_Radiometer_ABL90_Flex_IFU_Instructions.pdf), ch11 p276 (PDF page296). It does not verify storage-medium applicability at4C, pHi or actual gas/buffer boundaries. No4C values are generated.

## Still unresolved

The source workbook contains no formulas/named processing ranges. The supplied supplement describes separated extraction and internal standards, but not a complete original amount-to-final-mM equation, aqueous/free-pool mapping or analyte-specific recovery factors. Quantitative assay calibration is not proof of free substrate availability. Original extraction volumes are not new cellular volume measurements. The local Bordbar Sheet1 contains numeric concentration observations, while cellbb concerns imported curve coefficients on Feuil1; no concentration normalization lineage is inferred from it.

Required source-owner export: sample/donor keys, compartment and amount denominator, Hct and aliquot processing factors, assay calibration/recovery already applied, and ABL90 software version/input temperature/channel derivation. Reserve pH37 and candidate-derived pH22 in one evidence group until provenance is confirmed. Existing gas and hemolysis channels are leads, not a closed acid/base contract.

## Boundaries

This audit changes no source values, ODE, parameters, initial state, donor split or scientific-readiness guard. Primary web PDF methods and manufacturer equations were read; local download success/failures and checksums are recorded separately. Public PMC/PubMed direct openings encountered access challenges; failures do not imply absent methods. The synthetic carrier/buffer design is independent of these source concentrations and will not use pH22 as a second independent likelihood.
"""
    (out / "decision_report.md").write_text(report, encoding="utf-8")
    inputs = [JBC, SUPP, BORD, Path(__file__), ROOT / "src/fla_transport_access_ph.py",
              ROOT / "src/equadiff_brodbar.py", ROOT / "config/fla_working_reference.json",
              ROOT / "output/transport_access_ph_contract_2026_10_06/manifest.json"]
    write_json(out / "manifest.json", {"input_sha256": {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p) for p in inputs},
        "output_sha256": {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()}})
    return verify(out)


def verify(out):
    seal = json.loads((out / "manifest.json").read_text())
    for base, key in ((ROOT, "input_sha256"), (out, "output_sha256")):
        for name, expected in seal[key].items():
            if sha(base / name) != expected:
                raise ValueError("sealed evidence changed: " + name)
    table, summary, inventory = calculate()
    with (out / "pH_temperature_lineage.csv").open(newline="", encoding="utf-8") as f:
        if list(csv.DictReader(f)) != [{k: str(v) for k, v in r.items()} for r in table]:
            raise ValueError("pH source reconstruction failed")
    if json.loads((out / "summary.json").read_text()) != summary or json.loads((out / "workbook_inventory.json").read_text()) != inventory:
        raise ValueError("workbook reconstruction failed")
    if json.loads((out / "supplement_page_index.json").read_text()) != pdf_inventory(SUPP):
        raise ValueError("PDF index reconstruction failed")
    return {"verified": True, **summary}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    if bool(args.out) == bool(args.verify) or (args.verify and args.fetch):
        parser.error("choose --out [--fetch] or --verify")
    print(json.dumps(build(args.out.resolve(), args.fetch) if args.out else verify(args.verify.resolve()), indent=2))
