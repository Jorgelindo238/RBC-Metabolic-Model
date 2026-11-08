"""Archive the supplied JBC cells separately from the frozen Bordbar calibration."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import shutil
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import load_workbook
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fla_jbc_data import read_workbook, schedule, SCHEDULES

CONFIG = ROOT / "config/fla_jbc_data_ingestion.json"
DEFAULT_OUT = ROOT / "output/jbc_supplements_ingestion_2026_10_06"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path, rows):
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def verify_parent(archive):
    contract = json.loads((archive / "preregistered_contract.json").read_text())
    final = json.loads((archive / "final_verification.json").read_text())
    if not final.get("independent_archive_checks_pass") or final.get("biological_contract_changed") is not False:
        raise ValueError("verified unchanged parent required")
    for path, expected in {**contract["input_sha256"], **final.get("supporting_code_sha256", {})}.items():
        if digest(path) != expected:
            raise ValueError("parent input changed: " + path)
    for path, expected in final.get("output_sha256", {}).items():
        if digest(archive / path) != expected:
            raise ValueError("parent output changed: " + path)


def validate_design(design):
    if (design != json.loads(CONFIG.read_text()) or type(design.get("schema_version")) is not int
            or any(design[key] is not False for key in design if key.endswith("_allowed") or key == "production_training_enabled")):
        raise ValueError("only the isolated source-preserving ingestion is supported")
    return design


def source_conflicts():
    return [
        {"id": "ATP_compartment", "evidence": "assay!C1 ATP (endo); PDF p13 Fig S7 ATP (exo)",
         "action": "retain workbook header; candidate ATP held pending author clarification"},
        {"id": "ATP_pool_form", "evidence": "PDF p2 CellTiter-Glo; free/bound recovery and concentration denominator unspecified",
         "action": "do not identify measured ATP with free kinetic substrate automatically"},
        {"id": "DPG_not_measured", "evidence": "PDF p2 mentions a kit but also explicitly says not measured; p4 estimated profile; no workbook channel",
         "action": "exclude B23PG from independent JBC observations"},
        {"id": "hexose_6_phosphate_identity", "evidence": "endo!O1 glucose-6-phosphate; PDF p5 Table S1 Hexose 6-phosphate with two HMDB IDs",
         "action": "retain workbook identity but hold G6P operator; do not silently split G6P/F6P"},
        {"id": "phosphoglycerate_pool", "evidence": "endo phosphoglycerate pool",
         "action": "candidate P2G+P3G observation only; no individual pool reconstruction"},
        {"id": "volume_denominator", "evidence": "workbook mM, hematocrit and bag weight; no explicit endo/exo normalization equation recovered",
         "action": "no hematocrit, total-bag, cell-volume or recovery rescaling"},
        {"id": "replicate_identity", "evidence": "PDF p2 three donors and split units; workbook three time-reset blocks without donor IDs",
         "action": "retain positional index; no verified cross-sheet or cross-temperature donor pairing"},
        {"id": "different_37C_schedules", "evidence": "assay includes day14; endo/exo stop at day7",
         "action": "no row-number join, extrapolation or artificial alignment"},
        {"id": "duplicate_hemoglobin_headers", "evidence": "assay!E1 and assay!R1 same label, different values",
         "action": "retain distinct column IDs; do not deduplicate or assume same assay"},
        {"id": "RBC_count_unit", "evidence": "assay!K2 10e12/L; calculated cell-number and cell-volume headers",
         "action": "retain source notation; no implicit power-of-ten correction or derived volume"},
        {"id": "not_flux_or_redox", "evidence": "LDH U/L, pH analyzer at37C (PDF p2), nicotinamide and S-adenosylmethioninamine channels",
         "action": "not VLDH, pHi, NAD or ADOMET; no redox anchors inferred"},
        {"id": "zero_and_calibration_limits", "evidence": "182 extracellular zeros; PDF Tables S1/S2 linear ranges and LLOD in mg/L",
         "action": "retain zero as reported, censoring unresolved; no log-epsilon, sample covariance or unverified mg/L-to-mM LLOD"},
    ]


def summarize(observations):
    groups = defaultdict(list)
    for item in observations:
        groups[(item["channel_id"], item["temperature_C"], item["source_day"])].append(item)
    result = []
    for (channel, temp, day), rows in groups.items():
        values = [row["value"] for row in rows if row["value"] is not None]
        result.append({"channel_id": channel, "temperature_C": temp, "source_day": day,
                       "source_unit": rows[0]["source_unit"], "n_reported": len(values),
                       "mean_reported": statistics.mean(values) if values else None,
                       "SD_between_positional_blocks": statistics.stdev(values) if len(values) > 1 else None,
                       "covariance_or_accuracy_limit": "not_estimated", "training_enabled": False})
    return result


def model_coverage(channels, kernel):
    tree = ast.parse(Path(kernel).read_text(encoding="utf-8"))
    registry = next(ast.literal_eval(node.value) for node in ast.walk(tree)
                    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name)
                    and t.id == "BRODBAR_METABOLITE_MAP" for t in node.targets))
    result = []
    for pool, index in sorted(registry.items(), key=lambda item: item[1]):
        if index >= 113:
            continue
        candidates = [c for c in channels if pool in c["candidate_model_pools"].split("|")]
        result.append({"model_pool": pool, "state_index": index,
                       "candidate_channel_ids": "|".join(c["channel_id"] for c in candidates),
                       "coverage": "candidate_pooled_member" if any("|" in c["candidate_model_pools"] for c in candidates)
                                   else "candidate_source_observation" if candidates else "unobserved_in_JBC",
                       "model_observation_contract_verified": False, "training_enabled": False})
    return result


def verify(out):
    """Independently compare every exported cell/key against the original worksheet."""
    contract = json.loads((out / "preregistered_contract.json").read_text())
    for path, expected in contract["input_sha256"].items():
        if digest(path) != expected:
            raise ValueError("ingestion input changed: " + path)
    if (out / "final_verification.json").exists():
        final = json.loads((out / "final_verification.json").read_text())
        for path, expected in final["output_sha256"].items():
            if digest(out / path) != expected:
                raise ValueError("ingestion output changed: " + path)
    design = contract["design"]
    verify_parent(ROOT / design["parent_archive"])
    wb = load_workbook(design["workbook"], read_only=False, data_only=False)
    try:
        expected_cells = {(sheet.title, cell.coordinate) for sheet in wb for row in sheet.iter_rows(min_row=3)
                          if isinstance(row[1].value, (int, float)) for cell in row[2:]}
        keys, count = set(), 0
        with (out / "observations_long.csv").open(newline="", encoding="utf-8") as stream:
            for item in csv.DictReader(stream):
                sheet = wb[item["sheet"]]
                cell = sheet[item["source_cell"]]
                key = (sheet.title, cell.coordinate)
                if key in keys or key not in expected_cells:
                    raise ValueError("duplicate or non-source observation")
                keys.add(key)
                row = cell.row
                block_start = max(r for r in range(3, row+1) if sheet.cell(r, 1).value is not None)
                source_label = sheet.cell(block_start, 1).value
                temperature = int(source_label.split(" degrees C")[0])
                replicate = sum(sheet.cell(r, 2).value == 0 for r in range(block_start, row+1))
                expected_value = "" if cell.value is None else float(cell.value)
                actual_value = "" if item["value"] == "" else float(item["value"])
                if (actual_value != expected_value or float(item["source_day"]) != sheet.cell(row, 2).value
                        or float(item["temperature_C"]) != temperature or int(item["replicate_block_index"]) != replicate
                        or item["source_temperature_label"] != source_label or item["temperature_source_cell"] != f"A{block_start}"
                        or item["exact_source_label"] != sheet.cell(1, cell.column).value
                        or item["source_unit"] != sheet.cell(2, cell.column).value
                        or float(item["storage_day_from_documented_origin"]) != sheet.cell(row, 2).value + 1
                        or item["training_enabled"] != "False" or item["source_volume_conversion_applied"] != "False"):
                    raise ValueError("source cell/key mismatch: " + str(key))
                count += 1
        if keys != expected_cells:
            raise ValueError("incomplete source-cell coverage")
    finally:
        wb.close()
    return {"independent_source_cell_checks": count, "all_cells_and_keys_match_original": True,
            "parent_archive_unchanged": True, "biological_contract_changed": False}


def run(out, design):
    validate_design(design)
    parent = ROOT / design["parent_archive"]
    verify_parent(parent)
    if out.exists():
        raise ValueError("fresh output directory required; preserve existing evidence")
    channels, samples, observations = read_workbook(design["workbook"])
    reader = PdfReader(design["supplement"])
    if len(reader.pages) != 23:
        raise ValueError("expected 23-page JBC supplement")
    evidence = [{"pdf_page": page, "text": reader.pages[page-1].extract_text()}
                for page in (2, 4, 5, 6, 13)]
    input_paths = [CONFIG, Path(__file__), ROOT / "src/fla_jbc_data.py", ROOT / "qa/test_fla_jbc_data.py",
                   Path(design["workbook"]), Path(design["supplement"]), ROOT / "src/Data_Bordbar_et_al_exp.xlsx",
                   ROOT / "src/equadiff_brodbar.py", ROOT / "config/fla_working_reference.json",
                   parent / "preregistered_contract.json", parent / "final_verification.json",
                   parent / "source_inventory.json"]
    out.mkdir(parents=True)
    (out / "source_files").mkdir()
    for key in ("workbook", "supplement"):
        shutil.copyfile(design[key], out / "source_files" / Path(design[key]).name)
    write_json(out / "preregistered_contract.json", {"design": design,
               "created_utc": datetime.now(timezone.utc).isoformat(),
               "input_sha256": {str(p.resolve()): digest(p) for p in input_paths}})
    write_csv(out / "channel_inventory.csv", channels)
    write_csv(out / "sample_inventory.csv", samples)
    write_csv(out / "observations_long.csv", observations)
    write_csv(out / "summary_statistics.csv", summarize(observations))
    write_csv(out / "model_coverage.csv", model_coverage(channels, ROOT / "src/equadiff_brodbar.py"))
    write_json(out / "sampling_schedule.json", {sheet: {str(t): schedule(sheet, t) for t in SCHEDULES}
                                                for sheet in ("endo", "exo", "assay")})
    write_json(out / "pdf_evidence.json", evidence)
    write_json(out / "source_conflicts.json", source_conflicts())
    sources = json.loads((parent / "source_inventory.json").read_text())
    entry = next(item for item in sources if item["source_id"] == design["source_id"])
    entry.update(numeric_import_status="supplied original workbook imported with exact cells; no volume conversion",
                 evidence="supplied workbook endo/exo/assay; local PDF p2, p4, p5, p6, p13",
                 day_definition="source_day zero is one day after storage began (PDF p2); stored source days unchanged",
                 duration="endo/exo: about21 days at4/13/22C and7 days at37C; assay37C additionally day14",
                 source_files={key: design[key] for key in ("workbook", "supplement")},
                 model_observation_contract_verified=False,
                 days="see sampling_schedule.json; never round or merge temperature schedules",
                 usable_as="candidate external absolute trajectories; identity/volume/covariance mapping outstanding")
    write_json(out / "source_inventory_update.json", sources)
    counts = {"channels_by_sheet": dict(Counter(c["sheet"] for c in channels)),
              "samples_by_sheet": dict(Counter(s["sheet"] for s in samples)),
              "observations_by_sheet": dict(Counter(o["sheet"] for o in observations)),
              "observations_total": len(observations),
              "missing": sum(o["is_missing"] for o in observations),
              "zero": sum(o["is_zero"] for o in observations),
              "negative_concentrations": sum(o["source_unit"] == "mM" and o["value"] is not None and o["value"] < 0 for o in observations)}
    summary = {**counts, "source_access_blocker_resolved": True, "biological_calibration_ready": False,
               "redox_states_directly_measured": False, "flux_teachers_generated": False,
               "ode_runs": 0, "optimization_runs": 0, "model_or_J1_changes": False,
               "historical_readiness_contract_changed": False, "parent_source_inventory_overwritten": False}
    write_json(out / "summary.json", summary)
    report = """# Donnees JBC : import independant et limites d'utilisation

Source : Yurkovich et al., DOI 10.1074/jbc.M117.804914. Les deux fichiers fournis sont copies sans modification dans `source_files/` et leurs empreintes sont conservees.

## Donnees effectivement recuperees

- 47 canaux endo, 23 exo, 26 dosages/physiologie : 96 canaux, pas 96 metabolites distincts.
- 123 lignes endo, 123 exo, 126 assay : 11 886 valeurs numeriques, aucune manquante ni concentration negative; 182 zeros exo conserves tels quels.
- Quatre temperatures (4, 13, 22, 37 C), trois blocs de trajectoires par temperature. Le PDF decrit trois donneurs avec unites divisees, mais les identifiants individuels et leur appariement dans les feuilles ne sont pas explicites.
- A 4 C : jours source 0, 1.0417, 3, 7.0417, 10, 14.0417, 17, 20.9583. Le premier prelevement est un jour apres le debut du stockage (PDF p2). Une colonne derivee source_day+1 est conservee separement; cela ne definit pas l'origine de Sheet1 Bordbar.
- A 37 C : metabolomique jusqu'au jour source7, dosages jusqu'au jour14. Pas de jointure par numero de ligne, extrapolation ou arrondi des temps.

## Apport pour FLA et le deficit ATP

Les valeurs ATP, ADP, AMP, EGLC, ELAC, GLC, LAC, GO6P, F16BP, PEP, GSH/GSSG et autres pools sont disponibles comme observations candidates. Elles pourront contraindre des trajectoires et tester le partage adenylate dans un autre jeu de donnees. Ce sont des concentrations, non des flux mesures. Les couples NAD/NADH et NADP/NADPH, B13PG et les sept pools PPP latents ne sont pas observes; nicotinamide n'est pas NAD. Aucune inference redox ou correction de l'ATP n'est executee.

Le pool phosphoglycerate reste une observation candidate P2G+P3G; il n'est pas partage artificiellement. Le glucose-6-phosphate du classeur est a clarifier face au libelle hexose-6-phosphate et aux deux identifiants de Table S1. Le 6-phosphogluconate est GO6P, pas le lactone GL6P. S-adenosylmethioninamine n'est pas automatiquement ADOMET. LDH U/L est une activite enzymatique, pas VLDH; le pH mesure a37C n'est pas une mesure pHi.

## Reserves conservees

Le classeur appelle ATP endo tandis que Fig S7 l'appelle exo. La definition libre/total et le rendement d'extraction ATP restent a documenter. Le supplement mentionne un kit 2,3-DPG mais precise aussi que ce metabolite n'a pas ete mesure; le profil est estime pour la modelisation (p4), et aucune colonne ne le contient. Il est donc exclu des observations independantes.

Les mM originaux sont conserves sans conversion hematocrite/volume globulaire/volume de poche. L'hematocrite et les autres metriques sont archives comme donnees de physiologie, sans inventer une equation de normalisation. Les deux colonnes hemoglobine homonymes restent distinctes. Tables S1/S2 donnent des etalonnages et seuils en mg/L, pas une covariance biologique ou une limite d'erreur predictive. Les zeros ne sont pas remplaces par epsilon; leur statut sous seuil reste inconnu. La moyenne et l'ecart-type entre blocs sont descriptifs, pas des poids de calibration ni une covariance appariee.

## Decision et prochaine etape

L'acces au supplement numerique JBC est resolu. La calibration Bordbar, les 55 valeurs exactes J1, les IC redox, les cinetiques, reaction_consistent/tolerances et les archives historiques sont inchanges. Aucun ODE, flux teacher, fitting, modification du reseau ou promotion n'est lance. Le contrat biologique historique reste bloque.

Priorite : confirmer les definitions de pool et les equations de normalisation, en particulier ATP et hexose-6-phosphate, puis preparer un test externe distinct a4C avec le bon operateur d'observation. Ne pas utiliser cette cohorte comme preuve de normalisation de Sheet1 ni comme remplacement automatique de ses IC. Le benchmark synthetique d'identifiabilite redox reste une etape separee.

Fichiers : `observations_long.csv` (valeurs et cellules originales), `channel_inventory.csv` (correspondances candidates), `sample_inventory.csv`, `sampling_schedule.json`, `summary_statistics.csv`, `model_coverage.csv`, `source_conflicts.json`, `pdf_evidence.json`, `source_inventory_update.json`, `summary.json`.
"""
    (out / "decision_report.md").write_text(report, encoding="utf-8")
    receipt = verify(out)
    write_json(out / "independent_verification.json", receipt)
    seal(out)
    return summary


def seal(out):
    receipt = verify(out)
    write_json(out / "final_verification.json", {**receipt, "independent_archive_checks_pass": True,
               "output_sha256": {str(p.relative_to(out)): digest(p) for p in sorted(out.rglob("*"))
                                  if p.is_file() and p.name != "final_verification.json"}})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--seal-after-qa", type=Path)
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify(args.verify), indent=2))
    elif args.seal_after_qa:
        seal(args.seal_after_qa)
        print("archive resealed after QA; original outputs rechecked")
    else:
        print(json.dumps(run(args.out, json.loads(CONFIG.read_text())), indent=2))
