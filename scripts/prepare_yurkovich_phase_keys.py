"""Select explicit working phase bases and retain uncertainty of donor joins."""

import csv
import hashlib
import itertools
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fla_jbc_data import read_workbook

CONFIG = ROOT / "config/fla_distinct_volume_transport.json"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def prepare(out):
    config = json.loads(CONFIG.read_text())
    source = ROOT / config["jbc_workbook"]
    if sha(source) != config["jbc_sha256"]:
        raise ValueError("JBC source hash mismatch")
    if config["ufba_normalization_applied"] is not False or config["normalization"]["rescale_source_concentrations"] is not False:
        raise ValueError("this phase preparation preserves original concentrations")
    channels, samples, observations = read_workbook(source)
    keys = []
    for s in samples:
        trajectory = f"JBC2017::{s['sheet']}::T{s['temperature_C']}::B{s['replicate_block_index']}"
        keys.append({**s, "trajectory_key": trajectory, "working_sample_key": f"{trajectory}::t{s['source_day']}",
                     "candidate_unit_key": f"JBC2017::P{s['replicate_block_index']:02d}",
                     "candidate_key_status": "ordinal_hypothesis_not_verified_donor",
                     "validation_split_key": config["keys"]["validation_split_key"]})
    source_rows = {(r["channel_id"], r["temperature_C"], r["replicate_block_index"], r["source_day"]): r for r in observations}
    def row(channel, block, day):
        return source_rows[channel, 4, block, day]
    days = sorted({s["source_day"] for s in samples if s["sheet"] == "assay" and s["temperature_C"] == 4})
    prepared = []
    for permutation in itertools.permutations((1, 2, 3)):
        pairing_id = "endo_to_assay_" + "".join(map(str, permutation))
        for endo_block, assay_block in enumerate(permutation, 1):
            for day in days:
                h = row("assay!D", assay_block, day)
                entry = {"pairing_id": pairing_id, "primary_working_pairing": permutation == (1, 2, 3),
                    "temperature_C": 4, "source_day": day, "storage_day": day + 1,
                    "endo_trajectory_key": f"JBC2017::endo::T4::B{endo_block}",
                    "assay_trajectory_key": f"JBC2017::assay::T4::B{assay_block}",
                    "donor_id": "", "pairing_verified": False,
                    "normalization_status": "user_selected_phase_basis_not_source_verified",
                    "hematocrit": h["value"], "hematocrit_source_cell": h["source_cell"],
                    "Vi_over_Ve": h["value"] / (1 - h["value"]), "training_enabled": False}
                for name, channel, block, volume in (("GLC", "endo!L", endo_block, h["value"]),
                    ("LAC", "endo!AE", endo_block, h["value"]),
                    ("EGLC", "assay!Q", assay_block, 1 - h["value"]),
                    ("ELAC", "assay!T", assay_block, 1 - h["value"])):
                    observed = row(channel, block, day)
                    entry[name + "_phase_mM"] = observed["value"]
                    entry[name + "_source_cell"] = observed["sheet"] + "!" + observed["source_cell"]
                    entry[name + "_amount_per_L_bag"] = volume * observed["value"]
                prepared.append(entry)
    hct = [{"scenario_key": f"JBC2017::assay::T4::B{block}", "source_cell": row("assay!D", block, 0)["source_cell"],
            "hematocrit": row("assay!D", block, 0)["value"], "source_day": 0,
            "status": "borrowed_geometry_scenario_not_Bordbar_donor_metadata"} for block in (1, 2, 3)]
    out.mkdir(parents=True, exist_ok=False)
    write_csv(out / "sample_keys.csv", keys)
    write_csv(out / "phase_observations_pairing_sensitivity.csv", prepared)
    (out / "hematocrit_scenarios.json").write_text(json.dumps(hct, indent=2) + "\n")
    result = {"source_samples": len(keys), "phase_records": len(prepared), "pairings": 6,
              "primary_pairing": [1, 2, 3], "donor_ids_verified": 0,
              "concentration_values_rescaled": False, "ufba_applied": False,
              "source_basis_verified": False, "validation_split_created": False}
    (out / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    print(json.dumps(prepare(parser.parse_args().out), indent=2))
