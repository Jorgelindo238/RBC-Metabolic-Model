"""Read-only check of the source cells used by the coupled energy test."""

import argparse
import hashlib
import json
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/"src/Data_Bordbar_et_al_exp.xlsx"
REPLAY = ROOT/"output/vsam_pgk_j46_2026_11_04"


def audit():
    obs = json.loads((REPLAY/"observations.json").read_text())
    book = load_workbook(SOURCE, read_only=True, data_only=False)
    try:
        rows = list(book["Sheet1"].iter_rows(values_only=True))
    finally:
        book.close()
    channels = {r[0]: (i, list(r[1:15])) for i, r in enumerate(rows[1:], 2) if r[0] in obs["values"]}
    if list(rows[0][1:15]) != obs["time"] or {k: v[1] for k, v in channels.items()} != obs["values"]:
        raise ValueError("original observations or sampling support differ from archived replay")
    pairs = [("B13PG", "B23PG"), ("P2G", "P3G")]
    if any(channels[a][1] != channels[b][1] for a, b in pairs):
        raise ValueError("source alias assumption is no longer supported")
    return {"source": SOURCE.relative_to(ROOT).as_posix(), "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            "sheet": "Sheet1", "matching_numeric_cells": 770, "source_days": obs["time"],
            "source_rows": {p: channels[p][0] for p in ("B13PG", "B23PG", "P2G", "P3G", "ATP", "ADP", "AMP")},
            "exact_duplicate_pairs": pairs, "independent_B13PG_observation": False,
            "B23PG_P3G_nominal_labels_not_confirmed_identities": True, "adenylate_free_total_confirmed": False,
            "source_denominator_confirmed": False, "B13PG_J1_nominal_mM": channels["B13PG"][1][0],
            "preserve_all_J1_values": True, "JBC_used_in_fit": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--receipt", type=Path, required=True)
    a = p.parse_args()
    if a.receipt.exists():
        raise ValueError("fresh identity receipt required")
    result = audit()
    a.receipt.parent.mkdir(parents=True, exist_ok=True)
    a.receipt.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
