"""Inventory existing source channels and cohort risk without merging or fitting."""

from __future__ import annotations

import argparse
import ast
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/fla_common_manifest.json"
DEFAULT_OUT = ROOT / "output/fla_common_manifest_2026_10_06"
POLICY_KEYS = (
    "data_fusion_allowed", "normalization_allowed", "teacher_generation_allowed",
    "ode_execution_allowed", "optimization_allowed", "initial_state_changes_allowed",
    "production_training_enabled", "readiness_override_allowed",
)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def unique(rows, key):
    keys = [key(row) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate registry or source key")


def validate_config(config):
    if type(config.get("schema_version")) is not int or config["schema_version"] != 1 or config.get("purpose") != "source_observation_cohort_inventory_only":
        raise ValueError("inventory schema/purpose required")
    if any(config.get("policy", {}).get(key) is not False for key in POLICY_KEYS):
        raise ValueError("inventory cannot authorize fusion, training or model changes")
    for name, key in (("sources", "source_id"), ("datasets", "dataset_id"), ("cohorts", "cohort_id")):
        unique(config[name], lambda row: row[key])
    identifiers = [identifier for row in config["sources"] for identifier in row["identifiers"]]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("publication aliases cannot create duplicate studies")
    sources = {row["source_id"] for row in config["sources"]}
    cohorts = {row["cohort_id"] for row in config["cohorts"]}
    for row in config["datasets"]:
        if row["source_id"] not in sources or row["cohort_id"] not in cohorts:
            raise ValueError("orphan dataset source/cohort")
    for relation in config["relationships"]:
        if relation["left"] not in sources or relation["right"] not in sources:
            raise ValueError("orphan source relationship")
    return config


def resolve_inside(root, relative):
    path = (root / relative.replace("\\", "/")).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("manifest path escapes declared root")
    return path


def verify_seals(config, root):
    inputs = {}
    for seal in config["seals"]:
        base = resolve_inside(root, seal["root"])
        receipt = resolve_inside(base, seal["receipt"])
        inputs[receipt.relative_to(root).as_posix()] = sha(receipt)
        hashes = read_json(receipt)[seal["key"]]
        if not hashes:
            raise ValueError("empty upstream seal")
        for name, expected in hashes.items():
            path = resolve_inside(base, name)
            actual = sha(path)
            if actual != expected:
                raise ValueError(f"upstream hash mismatch: {path}")
            inputs[path.relative_to(root).as_posix()] = actual
    return inputs


def model_identity(root):
    tree = ast.parse((root / "src/equadiff_brodbar.py").read_text(encoding="utf-8-sig"))
    mapping = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "BRODBAR_METABOLITE_MAP" for t in node.targets):
            mapping = ast.literal_eval(node.value)
    if not isinstance(mapping, dict):
        raise ValueError("missing literal ODE pool registry")
    catalogue = (root / "RBC/Rxn_RBC.txt").read_text(encoding="utf-8").splitlines()
    start = catalogue.index("-METEXT") + 1
    external = set()
    for line in catalogue[start:]:
        if line.startswith("-"):
            break
        if line.strip() and not line.startswith("#"):
            external.update(line.split())
    if not external or not external <= mapping.keys():
        raise ValueError("invalid external pool registry")
    return mapping, external


def base_channel(dataset, local_id, label, kind, evidence):
    return {
        "observation_id": f"{dataset['dataset_id']}::{local_id}",
        "dataset_id": dataset["dataset_id"], "source_id": dataset["source_id"],
        "cohort_id": dataset["cohort_id"], "source_channel_id": local_id,
        "source_label": label, "measurement_kind": kind, "unit": "unknown",
        "compartment": "unresolved", "candidate_operator": "",
        "operator_status": "unresolved", "numeric_value_count": 0,
        "reported_zero_count": 0, "sample_count": 0, "source_days": "",
        "temperature_C": "", "source_locator": evidence,
        "representation_group": "", "duplicate_series_group": "",
        "availability": "inventoried_not_authorized", "intended_role": dataset["role"],
        "exposure": dataset["exposure"], "blockers": ";".join(dataset["blockers"]),
        "independent_validation_eligible": False, "training_enabled": False,
    }


def finite_nonnegative(value):
    if isinstance(value, bool):
        raise ValueError("boolean is not a measurement")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError("nonfinite or negative source value")
    return number


def read_standardized(dataset, root, mapping, external):
    path = root / dataset["path"]
    records = read_csv(path)
    unique(records, lambda row: row["Metabolite"])
    times = [key for key in records[0] if key != "Metabolite"]
    days = [float(key) for key in times]
    if any(b <= a for a, b in zip(days, days[1:])):
        raise ValueError("unordered source schedule")
    rows = []
    for index, record in enumerate(records, 2):
        label = record["Metabolite"].strip().upper()
        values = [finite_nonnegative(record[key]) for key in times]
        row = base_channel(dataset, str(index), label, "standardized_concentration_scale_unverified", f"{dataset['path']}:CSV row {index}")
        row.update(numeric_value_count=len(values), sample_count=len(values), reported_zero_count=values.count(0),
                   source_days=json.dumps(days), candidate_operator=label if label in mapping else "",
                   operator_status="model_label_only_source_pool_unverified" if label in mapping else "unmapped",
                   compartment="extracellular" if label in external else "intracellular" if label in mapping else "unresolved")
        if dataset["dataset_id"].startswith("bardyn_") and all(abs(value - 1.) <= 1e-12 for value in values):
            row["availability"] = "excluded_suspected_constant_one_placeholder"
        rows.append(row)
    samples = [{"sample_id": f"{dataset['dataset_id']}::column:{key}", "dataset_id": dataset["dataset_id"],
                "cohort_id": dataset["cohort_id"], "source_sample_id": key, "donor_id": "",
                "donor_identity_status": "aggregate_or_unknown", "source_day": key,
                "storage_day": "", "temperature_C": "", "replicate_block": "",
                "pairing_status": "unverified", "split_assignment": "not_assigned"} for key in times]
    return rows, samples


def read_bordbar(dataset, root, mapping, external):
    from openpyxl import load_workbook

    path = root / dataset["path"]
    receipt = read_json(root / "output/bordbar_source_units_time_audit_2026_10_06/workbook_receipt.json")
    if sha(path) != receipt["sha256"]:
        raise ValueError("historical measured workbook changed")
    workbook = load_workbook(path, read_only=True, data_only=False)
    try:
        records = list(workbook["Sheet1"].iter_rows(values_only=True))
    finally:
        workbook.close()
    if records[0][0] != "Conc / mM":
        raise ValueError("unexpected primary header")
    days = [float(day) for day in records[0][1:]]
    if len(records) - 1 != 55 or len(days) != 14 or days[0] != 1 or days[-1] != 46:
        raise ValueError("exact55/time contract drift")
    unique(records[1:], lambda row: row[0])
    signatures, rows = {}, []
    for index, record in enumerate(records[1:], 2):
        label = str(record[0]).strip().upper()
        values = tuple(finite_nonnegative(value) for value in record[1:])
        signatures.setdefault(values, []).append(label)
        row = base_channel(dataset, f"Sheet1!A{index}", label, "nominal_absolute_concentration", f"{dataset['path']}:Sheet1!B{index}:O{index}")
        if label not in mapping:
            raise ValueError("unmapped historical measured row")
        row.update(unit="nominal mM; denominator unverified", compartment="extracellular" if label in external else "intracellular",
                   candidate_operator=label, operator_status="historical_mapping_not_source_identity_validation",
                   numeric_value_count=len(values), sample_count=len(values), reported_zero_count=values.count(0),
                   source_days=json.dumps(days), availability="historical_use_only_no_new_biological_authorization")
        rows.append(row)
    duplicates = {label: "|".join(labels) for labels in signatures.values() if len(labels) > 1 for label in labels}
    for row in rows:
        row["duplicate_series_group"] = duplicates.get(row["source_label"], "")
    samples = [{"sample_id": f"{dataset['dataset_id']}::J{day:g}", "dataset_id": dataset["dataset_id"],
                "cohort_id": dataset["cohort_id"], "source_sample_id": f"J{day:g}", "donor_id": "",
                "donor_identity_status": "aggregation_unresolved", "source_day": day,
                "storage_day": "", "temperature_C": "", "replicate_block": "",
                "pairing_status": "unverified", "split_assignment": "historical_development"} for day in days]
    return rows, samples


def read_jbc(dataset, root):
    base = root / dataset["path"]
    channels = read_csv(base / "channel_inventory.csv")
    inventory = read_csv(base / "sample_inventory.csv")
    cells = read_csv(base / "observations_long.csv")
    unique(channels, lambda row: row["channel_id"])
    unique(inventory, lambda row: row["sample_id"])
    unique(cells, lambda row: (row["sample_id"], row["channel_id"]))
    samples_by_id = {row["sample_id"]: row for row in inventory}
    channels_by_id = {row["channel_id"]: row for row in channels}
    grouped = {key: [] for key in channels_by_id}
    expected_keys = {(sample["sample_id"], channel["channel_id"])
                     for sample in inventory for channel in channels if sample["sheet"] == channel["sheet"]}
    if {(cell["sample_id"], cell["channel_id"]) for cell in cells} != expected_keys:
        raise ValueError("incomplete or unexpected JBC sample/channel coverage")
    for cell in cells:
        sample = samples_by_id[cell["sample_id"]]
        channel = channels_by_id[cell["channel_id"]]
        if sample["sheet"] != cell["sheet"] or channel["sheet"] != cell["sheet"]:
            raise ValueError("cross-sheet positional join forbidden")
        if cell["source_cell"] != channel["excel_column"] + sample["excel_row"]:
            raise ValueError("source cell identity mismatch")
        for key in ("source_day", "temperature_C", "replicate_block_index"):
            if cell[key] != sample[key]:
                raise ValueError("source sample metadata mismatch")
        if cell["is_missing"] != "False":
            raise ValueError("unexpected missing JBC value")
        value = float(cell["value"])
        if not math.isfinite(value):
            raise ValueError("nonfinite JBC value")
        grouped[cell["channel_id"]].append(cell)
    rows = []
    for channel in channels:
        local = grouped[channel["channel_id"]]
        row = base_channel(dataset, channel["channel_id"], channel["exact_source_label"], channel["channel_kind"],
                           f"{dataset['path']}/source_files/jbc.M117.804914-1.xlsx:{channel['sheet']}!{channel['excel_column']}; observations_long.csv source_cell")
        row.update(unit=channel["source_unit"], compartment=channel["compartment"],
                   candidate_operator=channel["candidate_operator"], operator_status=channel["mapping_status"],
                   numeric_value_count=len(local), sample_count=len(local),
                   reported_zero_count=sum(float(cell["value"]) == 0 for cell in local),
                   source_days=json.dumps(sorted({float(cell["source_day"]) for cell in local})),
                   temperature_C=json.dumps(sorted({float(cell["temperature_C"]) for cell in local})))
        rows.append(row)
    samples = [{"sample_id": f"{dataset['dataset_id']}::{row['sample_id']}", "dataset_id": dataset["dataset_id"],
                "cohort_id": dataset["cohort_id"], "source_sample_id": row["sample_id"], "donor_id": row["donor_id"],
                "donor_identity_status": "positional_block_not_identified_donor", "source_day": row["source_day"],
                "storage_day": row["storage_day_from_documented_origin"], "temperature_C": row["temperature_C"],
                "replicate_block": row["replicate_block_index"], "pairing_status": "cross_sheet_and_temperature_unverified",
                "split_assignment": "not_assigned"} for row in inventory]
    if any(row["donor_id"] for row in samples):
        raise ValueError("unexpected JBC donor ID requires contract revision")
    return rows, samples


def read_s6(dataset, root):
    base = root / dataset["path"]
    donors = read_csv(base / "donor_metadata.csv")
    unique(donors, lambda row: row["Sample Index"])
    donor_ids = {row["Sample Index"] for row in donors}
    rows, sample_meta, variant_keys = [], {}, []
    for table in ("D", "E"):
        cells = read_csv(base / f"Table_{table}_priority_observations.csv")
        unique(cells, lambda row: (row["uniprot"], row["sample_id"]))
        groups, keys = {}, set()
        for cell in cells:
            if cell["donor_id"] not in donor_ids or cell["sample_id"] != f"{cell['donor_id']}_D{cell['storage_day']}":
                raise ValueError("S6 donor/sample linkage mismatch")
            if cell["missing"] != "False":
                raise ValueError("unexpected missing selected S6 cell")
            finite_nonnegative(cell["reported_value"])
            keys.add((cell["uniprot"], cell["sample_id"]))
            groups.setdefault(cell["uniprot"], []).append(cell)
            meta = (cell["donor_id"], cell["storage_day"])
            if cell["sample_id"] in sample_meta and sample_meta[cell["sample_id"]] != meta:
                raise ValueError("inconsistent S6 sample metadata")
            sample_meta[cell["sample_id"]] = meta
        variant_keys.append(keys)
        for accession, local in sorted(groups.items()):
            first = local[0]
            row = base_channel(dataset, f"Table {table}!{accession}", first["candidate_genes"], "estimated_protein_abundance", f"{dataset['path']}/Table_{table}_priority_observations.csv; original Table {table} row {first['source_row']}")
            if len({cell["reported_unit"] for cell in local}) != 1:
                raise ValueError("mixed protein units")
            row.update(unit=first["reported_unit"], candidate_operator=f"enzyme:{accession}",
                       operator_status="protein_estimate_not_active_enzyme_or_metabolite",
                       numeric_value_count=len(local), sample_count=len(local),
                       reported_zero_count=sum(float(cell["reported_value"]) == 0 for cell in local),
                       source_days=json.dumps(sorted({float(cell["storage_day"]) for cell in local})),
                       representation_group=f"gem_s6::{accession}")
            rows.append(row)
    if variant_keys[0] != variant_keys[1]:
        raise ValueError("D/E must represent the same protein/sample keys")
    samples = [{"sample_id": f"{dataset['dataset_id']}::{key}", "dataset_id": dataset["dataset_id"],
                "cohort_id": dataset["cohort_id"], "source_sample_id": key, "donor_id": donor,
                "donor_identity_status": "source_ID_not_cross_study_global_ID", "source_day": day,
                "storage_day": day, "temperature_C": "", "replicate_block": "",
                "pairing_status": "D_E_same_estimate_by_sample_ID", "split_assignment": "not_assigned"}
               for key, (donor, day) in sorted(sample_meta.items())]
    return rows, samples


def read_deep_red(dataset, root):
    records = read_csv(root / dataset["path"])
    unique(records, lambda row: row["uniprot_id"])
    rows = []
    for record in records:
        for variant, column, letter in (("F", "copy_number_per_cell_F", "F"), ("G", "multi_anchor_copy_number_per_cell_G", "G")):
            value = finite_nonnegative(record[column])
            row = base_channel(dataset, f"{record['uniprot_id']}:{variant}", record["gene"], "alternative_copy_number_calibration", f"Supplementary Table 1 - FINAL.xlsx:{record['sheet']}!{letter}{record['source_row']}; {dataset['path']}")
            row.update(unit="estimated copies/cell", candidate_operator=f"enzyme:{record['uniprot_id']}",
                       operator_status="protein_estimate_not_active_enzyme_or_metabolite",
                       numeric_value_count=1, reported_zero_count=int(value == 0), sample_count=0,
                       representation_group=f"deep_red::{record['uniprot_id']}")
            rows.append(row)
    return rows, []


def build(config, root):
    validate_config(config)
    mapping, external = model_identity(root)
    observations, samples = [], []
    for dataset in config["datasets"]:
        reader = dataset["reader"]
        if reader == "bordbar":
            result = read_bordbar(dataset, root, mapping, external)
        elif reader == "standardized":
            result = read_standardized(dataset, root, mapping, external)
        elif reader == "jbc":
            result = read_jbc(dataset, root)
        elif reader == "s6":
            result = read_s6(dataset, root)
        elif reader == "deep_red":
            result = read_deep_red(dataset, root)
        elif reader == "metadata_only":
            result = [], []
        else:
            raise ValueError("unknown reader")
        observations.extend(result[0])
        samples.extend(result[1])
    unique(observations, lambda row: row["observation_id"])
    unique(samples, lambda row: row["sample_id"])
    summary = []
    for dataset in config["datasets"]:
        local = [row for row in observations if row["dataset_id"] == dataset["dataset_id"]]
        subjects = [row for row in samples if row["dataset_id"] == dataset["dataset_id"]]
        summary.append({"dataset_id": dataset["dataset_id"], "source_id": dataset["source_id"],
                        "channel_representations": len(local), "numeric_values_represented": sum(row["numeric_value_count"] for row in local),
                        "sample_records": len(subjects), "identified_donors": len({row["donor_id"] for row in subjects if row["donor_id"]}),
                        "excluded_placeholder_channels": sum(row["availability"].startswith("excluded_") for row in local),
                        "independent_validation_eligible": False, "training_enabled": False})
    return observations, samples, summary


def write_csv(path, rows):
    if not rows:
        raise ValueError("empty output table")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def make_report(config, summary, seal_count):
    lines = ["# Common source, observation and cohort manifest", "", "Inventory complete; scientific integration remains blocked. No fusion, rescaling, teacher generation, ODE or optimization.", "",
             "Counts describe exported channel representations and source cells, not independent experiments. Deep Red F/G and S6 D/E are alternative representations of their respective estimates.", "",
             "| Dataset | Channel representations | Numeric source values | Sample records | Identified donor IDs | Excluded placeholders |",
             "|---|---:|---:|---:|---:|---:|"]
    for row in summary:
        lines.append(f"| {row['dataset_id']} | {row['channel_representations']} | {row['numeric_values_represented']} | {row['sample_records']} | {row['identified_donors']} | {row['excluded_placeholder_channels']} |")
    lines += ["", "## Source Roles And Missing Evidence", ""]
    for source in config["sources"]:
        link = f"[{source['source_id']}]({source['url']})" if source.get("url") else source["source_id"]
        lines.append(f"- {link}: {source['role']}. Evidence: `{source['metadata_evidence']}`.")
    lines += ["", "## Readiness And Independence", "",
              "- The local Sheet1 source has exact B13PG/B23PG and P2G/P3G duplicate trajectories. These are flags for analytical pool identity/lineage, not proof of physiological equality. Keep all 55 J1 entries unchanged.",
              "- JBC has positional replicate blocks, not verified donor IDs; do not pair endo/exo/assay or temperatures by position. The documented +1-day storage coordinate is retained separately, never applied to the historical workbook.",
              "- JBC ATP, hexose-6-phosphate, phosphoglycerate sums, volume denominators and zero censoring require observation contracts. Predicted 2,3-DPG is not an experimental channel; LDH activity, analyzer pH and nicotinamide are not VLDH, pHi or NAD.",
              "- S6 D/E join by sample ID, not column position; both are one abundance estimate in different units. Deep Red F/G are alternative calibrations, not independent assays. No kcat, active fraction, volume conversion or Vmax is inferred here.",
              "- The atlas PMID/DOI refer to one preprint. No individual atlas observation or donor ID is available in this manifest. Its reported donor total is metadata, not imported sample coverage.",
              "- Bardyn/Michel have prior exploratory exposure. They remain useful external transfer diagnostics, but are not declared pristine holdouts. No currently imported panel is certified independent validation.",
              "- All cohort pairs default to independence unverified. Specific source-lineage/overlap risks are listed in `relationships.csv`; absence of an edge is not proof of independence.",
              "- Split unit: identified donor (all repeated days/paired conditions together). JBC requires verified donor pairing first; aggregate/unknown-cohort panels cannot support donor-level splits. No train/test partition is fabricated.",
              "", "## Dataset-Specific Blocks", ""]
    for dataset in config["datasets"]:
        lines.append(f"- {dataset['dataset_id']}: {', '.join(dataset['blockers'])}.")
    lines += ["", "## Coverage Boundary", "",
              "The channel inventory covers the local metabolic panels, imported JBC workbook and full human Deep Red F/G export, plus the 62-protein S6 priority extraction. It is not full S6 proteome coverage or an atlas metabolomic import. Other Deep Red workbook species/assays and HTML PTM/interactome resources remain resource-level evidence in `resources.csv`; their analytical grain is not promoted to kinetic observations.",
              "", "## Integrity And Next Step", "", f"Upstream sealed files checked: {seal_count}. Inputs and protected model/data files are hashed before and after this build; outputs have a separate seal. Historical archives are never rewritten.",
              "", "Next: resolve the source-specific concentration/volume and pool-identity contracts (local Sheet1 and JBC first), obtain atlas sample/cohort linkage, and only then define prospective held-out observables. This manifest does not override existing biological-readiness gates.", ""]
    return "\n".join(lines)


def run(out, *, root=ROOT, config_path=CONFIG):
    config = validate_config(read_json(config_path))
    if out.exists():
        raise FileExistsError("refuse to overwrite an existing manifest; use --verify or a fresh --out")
    out = out.resolve()
    if not out.is_relative_to((root / "output").resolve()):
        raise ValueError("output must be a fresh workspace output directory")
    if any(out.is_relative_to((root / seal["root"]).resolve()) for seal in config["seals"]):
        raise ValueError("cannot write inside an upstream archive")
    inputs = verify_seals(config, root)
    seal_count = len(inputs)
    for relative in config["protected_paths"]:
        inputs[relative] = sha(root / relative)
    for source in config["sources"]:
        relative = source["metadata_evidence"]
        inputs[relative] = sha(root / relative)
    for dataset in config["datasets"]:
        if dataset.get("path") and (root / dataset["path"]).is_file():
            inputs[dataset["path"]] = sha(root / dataset["path"])
    inputs[config_path.relative_to(root).as_posix()] = sha(config_path)
    inputs[Path(__file__).resolve().relative_to(root).as_posix()] = sha(Path(__file__).resolve())
    # Explicitly retain the older source receipts used by the live Sheet1 comparison.
    receipt = "output/bordbar_source_units_time_audit_2026_10_06/workbook_receipt.json"
    inputs[receipt] = sha(root / receipt)
    observations, samples, summary = build(config, root)
    if any(sha(root / relative) != expected for relative, expected in inputs.items()):
        raise ValueError("input changed during manifest build")
    resources = [{"path": relative, "sha256": expected, "role": "source_or_evidence_input",
                  "training_enabled": False} for relative, expected in sorted(inputs.items())]
    out.mkdir(parents=True, exist_ok=False)
    write_csv(out / "observations.csv", observations)
    write_csv(out / "samples.csv", samples)
    write_csv(out / "datasets.csv", summary)
    write_csv(out / "cohorts.csv", config["cohorts"])
    write_csv(out / "relationships.csv", config["relationships"])
    write_csv(out / "resources.csv", resources)
    write_json(out / "registry.json", config)
    payload = {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
               "status": "inventory_complete_integration_not_ready", "policy": config["policy"],
               "summary": summary, "upstream_sealed_file_count": seal_count,
               "independence_default": "unverified_even_when_no_explicit_relationship",
               "split_policy": "no_assignment_until_donor_linkage_and_exposure_contract",
               "input_sha256": inputs, "protected_inputs_unchanged": True,
               "ode_runs": 0, "optimization_runs": 0, "teachers_generated": 0}
    write_json(out / "summary.json", payload)
    (out / "decision_report.md").write_text(make_report(config, summary, seal_count), encoding="utf-8")
    write_json(out / "manifest.json", {"input_sha256": inputs, "output_sha256": {
        path.name: sha(path) for path in sorted(out.iterdir()) if path.is_file()}})
    return payload


def verify(out, *, root=ROOT):
    seal = read_json(out / "manifest.json")
    for relative, expected in seal["input_sha256"].items():
        if sha(resolve_inside(root, relative)) != expected:
            raise ValueError(f"input changed: {relative}")
    for relative, expected in seal["output_sha256"].items():
        if sha(resolve_inside(out, relative)) != expected:
            raise ValueError(f"output changed: {relative}")
    config = validate_config(read_json(out / "registry.json"))
    verify_seals(config, root)
    observations, samples, summary = build(config, root)
    for name, expected in (("observations.csv", observations), ("samples.csv", samples), ("datasets.csv", summary),
                           ("cohorts.csv", config["cohorts"]), ("relationships.csv", config["relationships"])):
        actual = read_csv(out / name)
        serialized = [{key: "" if value is None else str(value) for key, value in row.items()} for row in expected]
        if actual != serialized:
            raise ValueError(f"source reconstruction differs: {name}")
    payload = read_json(out / "summary.json")
    if payload["summary"] != summary or payload["policy"] != config["policy"]:
        raise ValueError("summary/registry inconsistency")
    if any(payload.get(key) != 0 for key in ("ode_runs", "optimization_runs", "teachers_generated")):
        raise ValueError("inventory execution counters must remain zero")
    if payload.get("status") != "inventory_complete_integration_not_ready":
        raise ValueError("inventory cannot promote scientific readiness")
    return {"verified": True, "source_channels_reconstructed": len(observations),
            "samples_reconstructed": len(samples), "input_hashes_checked": len(seal["input_sha256"]),
            "output_hashes_checked": len(seal["output_sha256"]), "scientific_integration_ready": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    result = verify(args.verify) if args.verify else run(args.out)
    print(json.dumps(result if args.verify else {"status": result["status"], "summary": result["summary"]}, indent=2))


if __name__ == "__main__":
    main()
