"""Extend, without rewriting, the sealed source review and retrieved S6 file."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree

from openpyxl import load_workbook

from audit_palsson_proteomics_sources import DEFAULT_OUT, ROOT, fetch, sha, verify, write_csv, write_json

QUERY = 'AUTH:Palsson AND FIRST_PDATE:[2023-01-01 TO 2026-10-06] AND (erythrocyte OR RBC OR red blood)'


def author_is_bernhard_palsson(item):
    return any(author.get("lastName") == "Palsson" and
               (author.get("initials", "") in {"BO", "B"} or "Bernhard" in author.get("firstName", ""))
               for author in item.get("authorList", {}).get("author", []))


def run(parent=DEFAULT_OUT):
    verify(parent)
    out = parent / "evidence_extension_v2"
    if out.exists():
        raise ValueError("preserve the previous extension")
    out.mkdir()
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?format=json&resultType=core&pageSize=100&query=" + quote(QUERY)
    receipt = fetch(url, out / "recent_author_search.json")
    if not receipt["success"]:
        raise ValueError("primary bibliography query failed")
    data = json.loads((out / "recent_author_search.json").read_text())
    if data.get("hitCount", 0) > 100:
        raise ValueError("bibliography requires pagination")
    bibliography = [{"id": item["id"], "source": item["source"], "title": item["title"],
                     "doi": item.get("doi", ""), "pmcid": item.get("pmcid", ""),
                     "first_publication_date": item.get("firstPublicationDate", ""),
                     "author_string": item.get("authorString", ""),
                     "bernhard_palsson_author_confirmed": author_is_bernhard_palsson(item),
                     "new_independent_dataset": "requires_manual_cohort_and_preprint_audit"}
                    for item in data.get("resultList", {}).get("result", []) if author_is_bernhard_palsson(item)]
    for pmid in ("42224377", "40072998", "38964323", "42007445"):
        evidence_path = out / f"publication_{pmid}.json"
        r = fetch("https://www.ebi.ac.uk/europepmc/webservices/rest/search?format=json&resultType=core&query=" +
                  quote(f"EXT_ID:{pmid} AND SRC:MED"), evidence_path)
        if not r["success"]:
            raise ValueError("required publication metadata unavailable")
        item = json.loads(evidence_path.read_text())["resultList"]["result"][0]
        if not author_is_bernhard_palsson(item):
            raise ValueError("Palsson authorship not verified")
    write_csv(out / "recent_bibliography.csv", bibliography)
    workbook = load_workbook(parent / "retrieved_sources/pcbi.1012109.s008.xlsx", read_only=True, data_only=False)
    tables = []
    try:
        for sheet in workbook:
            top = list(sheet.iter_rows(min_row=1, max_row=6, max_col=min(sheet.max_column, 12), values_only=True))
            tables.append({"sheet": sheet.title, "rows": sheet.max_row, "columns": sheet.max_column,
                           "first_six_rows_first_twelve_columns": top,
                           "numerical_sample_values_imported": False})
    finally:
        workbook.close()
    write_json(out / "RBC_GEM_S6_workbook_inventory.json", tables)
    protein_path = parent / "human_protein_copy_numbers.csv"
    import csv
    with protein_path.open(newline="", encoding="utf-8") as stream:
        proteins = list(csv.DictReader(stream))
    counts = {"listed_proteins": len(proteins), "positive_copy_number_F": sum(float(r["copy_number_per_cell_F"]) > 0 for r in proteins),
              "zero_copy_number_F": sum(float(r["copy_number_per_cell_F"]) == 0 for r in proteins)}
    fractions = []
    for row in proteins:
        if row["gene"] in {"HK1", "GAPDH", "PGK1", "G6PD", "PGD", "SLC4A1", "PCMT1"}:
            f, g = float(row["copy_number_per_cell_F"]), float(row["multi_anchor_copy_number_per_cell_G"])
            fractions.append({"gene": row["gene"], "source_row": row["source_row"], "copy_F": f, "copy_G": g,
                              "F_over_G": f/g if g else None})
    write_json(out / "copy_number_checks.json", {**counts, "examples": fractions,
               "two_calibrations_not_a_confidence_interval": True})
    supplement_links = []
    for pmc in ("PMC11925312", "PMC13084699"):
        tree = ElementTree.parse(parent / "retrieved_sources" / (pmc + ".xml"))
        for node in tree.getroot().iter("supplementary-material"):
            supplement_links.append({"pmcid": pmc, "id": node.get("id"),
                                     "label_and_caption": " ".join(node.itertext()).strip()[:1500],
                                     "links": [value for element in node.iter() for key, value in element.attrib.items()
                                               if key.endswith("href")]})
    write_json(out / "primary_supplement_links.json", supplement_links)
    write_json(out / "query_correction.json", {"original_attempt": "AUTH_LAST_NAME and AUTH_NAME returned zero; preserve failed searches, not biological findings",
               "used_query": QUERY, "hits": data["hitCount"],
               "confirmed_bernhard_author_hits": sum(row["bernhard_palsson_author_confirmed"] for row in bibliography),
               "exhaustive_literature_review_claimed": False, "receipt": receipt})
    write_json(out / "manifest.json", {"input_sha256": {str(p.resolve()): sha(p) for p in [Path(__file__),
               parent / "manifest.json", parent / "retrieved_sources/pcbi.1012109.s008.xlsx", protein_path]},
               "output_sha256": {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob("*")) if p.is_file()},
               "model_changed": False})
    print(json.dumps({"bibliography_hits": data["hitCount"], "protein_counts": counts,
                      "RBC_GEM_S6_sheets": len(tables), "prior_activated": False}, indent=2))


if __name__ == "__main__":
    run()
