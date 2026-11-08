"""Read-only source/pool audit and reversible latent-inference preparation."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from audit_bordbar_source_units_time import workbook_evidence
from fla_latent_inference import balance_identifiability
from reaction_positivity import rbc_reaction_matrix
from run_fla_sparse_teacher_resolution import verify_archive_inputs

CONFIG = ROOT / "config/fla_latent_inference_preparation.json"
DEFAULT_OUT = ROOT / "output/fla_latent_inference_preparation_2026_10_06"
ALIASES = {"F1,6-BP": "F16BP", "DHAP": "DHCP", "HX": "HYPX", "L_GC": "GLUCYS",
           "S7P": "S7P", "1,3-BPG": "B13PG", "2PG": "P2G", "3PG": "P3G",
           "glutamate": "GLU", "glycine": "GLY", "cycteine": "CYS", "cysteine": "CYS"}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False)+"\n", encoding="utf-8")


def validate_design(design):
    expected = json.loads(CONFIG.read_text())
    if design != expected or type(design.get("schema_version")) is not int:
        raise ValueError("exact preparation-only design required")
    return design


def parse_reference_rows(pdf_path):
    reader = PdfReader(pdf_path)
    if len(reader.pages) != 37 or "Initial and steady-state concentrations" not in reader.pages[33].extract_text():
        raise ValueError("expected Nishino section 5 pages 34-36 required")
    rows = []
    pattern = re.compile(r"^(.+?)\s+((?:\d[\d.\s]*[Ee]\s*[-+\u2212]\s*\d+)|0\.00)\s*$")
    for page_index in (33, 34, 35):
        for line in reader.pages[page_index].extract_text().splitlines():
            match = pattern.match(line.strip())
            if not match:
                continue
            label, number = match.groups()
            value = float(re.sub(r"\s+", "", number).replace("\u2212", "-"))
            canonical = re.sub(r"\s+", "", label).replace("+", "-")
            compartment = "extracellular" if "extracellular" in label else "intracellular_or_complex"
            free_or_total = "free" if "(free)" in canonical else "total" if "(total)" in canonical else "unspecified"
            base = canonical.replace("(extracellular)", "").replace("(free)", "").replace("(total)", "")
            mapped = ALIASES.get(base, base)
            if compartment == "extracellular":
                mapped = "E"+mapped
            rows.append({"reference_row_id": len(rows)+1, "source_id": "Nishino_2009_model_reference",
                         "pdf_page": page_index+1, "exact_source_label": label, "canonical_label": canonical,
                         "value_M": value, "value_mM_dimensional_only": value*1000,
                         "compartment": compartment, "pool_form": free_or_total,
                         "candidate_model_pool": mapped, "day": None,
                         "role": "model_reference_point_not_measured_anchor", "applicable_bound": None,
                         "volume_compatibility_verified": False, "applied_to_model": False})
    if len(rows) < 100:
        raise ValueError("incomplete concentration-table extraction")
    return rows


def kernel_audit(path):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    registry, expressions = {}, {}
    mode = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "BRODBAR_METABOLITE_MAP":
                    registry = ast.literal_eval(node.value)
                if isinstance(target, ast.Name) and target.id == "TRANSPORT_VOLUME_SCALING_MODE":
                    mode = ast.literal_eval(node.value)
                if isinstance(target, ast.Name) and target.id in {"VGAPDH", "VPGK", "VAK"}:
                    expressions[target.id] = {"line": node.lineno, "expression": ast.unparse(node.value)}
                if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id == "dxdt":
                    index = ast.literal_eval(target.slice) if isinstance(target.slice, ast.Constant) else None
                    if index in (13, 15, 35, 36, 37, 75, 76, 77, 78):
                        expressions[f"dxdt[{index}]"] = {"line": node.lineno, "expression": ast.unparse(node.value)}
    forms = [name for name in registry if any(token in name.upper() for token in ("MGATP", "ATP_FREE", "ATP_TOTAL", "OXYHB", "DEOXYHB"))]
    return {"state_registry": registry, "transport_volume_scaling_mode": mode, "explicit_ATP_binding_states": forms,
            "ATP_free_total_observation_mapping_implemented": bool(forms), "explicit_Pi_state": "Pi" in registry or "PI" in registry,
            "explicit_Mg_state": "Mg" in registry or "MG" in registry, "expressions": expressions,
            "conclusion": "ATP is one phenomenological state; no verified free/total or extraction observation operator",
            "network_changed": False}


def fetch_supplement(item, directory):
    receipt = {**item, "attempted": True, "validated_excel": False, "local_observations_imported": False}
    try:
        request = urllib.request.Request(item["url"], headers={"User-Agent": "airbc-scientific-source-audit/1.0"})
        with urllib.request.urlopen(request, timeout=20) as response:
            blob = response.read(15_000_001)
            receipt.update(status=response.status, content_type=response.headers.get("Content-Type"), final_url=response.url)
        if len(blob) > 15_000_000:
            raise ValueError("supplement exceeds audit size limit")
        raw = directory / (item["filename"]+".raw_response.bin")
        raw.write_bytes(blob)
        receipt.update(raw_response_path=raw.name, sha256=digest(raw), size_bytes=len(blob))
        if not blob.startswith(b"PK"):
            receipt["limitation"] = "response is not an Excel ZIP; not interpreted as data"
            return receipt
        workbook = load_workbook(BytesIO(blob), read_only=True, data_only=False)
        cells = []
        for sheet in workbook:
            for row in sheet:
                for cell in row:
                    if cell.value is not None:
                        cells.append({"sheet": sheet.title, "cell": cell.coordinate, "value": str(cell.value),
                                      "type": cell.data_type, "measurement_classification": "pending_table_interpretation"})
        receipt.update(validated_excel=True, sheets=workbook.sheetnames, nonempty_cell_count=len(cells),
                       limitation="raw cells archived; units/days/measured-versus-predicted mapping not automatically inferred")
        workbook.close()
        pd.DataFrame(cells).to_csv(directory / "Yurkovich_raw_supplement_cells.csv", index=False)
    except Exception as error:
        receipt["limitation"] = f"retrieval/validation failed: {type(error).__name__}: {error}"
    return receipt


def report(out, evidence, sources, references, audit, structure, readiness, downloads):
    get = lambda label: next(row["value_mM_dimensional_only"] for row in references if row["canonical_label"] == label)
    nad, nadh, nadp, nadph = [get(label) for label in ("NAD", "NADH", "NADP", "NADPH")]
    lines = ["# Audit des pools et preparation de l'inference FLA", "",
        "Statut : preparation terminee, aucune nouvelle simulation ni estimation biologique. Tous les etats J1 et toutes les cinetiques sont preserves.", "",
        "## Conclusions prioritaires", "",
        "1. ATP est un seul etat phenomenologique. Aucun etat ATP libre/MgATP/ATP lie a Hb ni operateur d'observation libre-total n'est implemente. Ne pas comparer ou substituer automatiquement des definitions differentes.",
        "2. Sheet1 porte une etiquette mM, pas une preuve de volume cytosolique. La piste uFBA utilise mmol/L de poche. Aucun facteur hematocrite/eau cellulaire n'est applique.",
        "3. B13PG/B23PG et P2G/P3G sont des signaux exactement dupliques. Ils ne constituent pas quatre observations independantes. Leur identification upstream reste ouverte; aucune repartition arbitraire.",
        "4. Les valeurs du supplement Nishino sont des references du modele, pas des ancrages absolus mesures de la cohorte Bordbar aux jours 1-5.",
        "5. Le seuil numerique reaction_consistent reste fixe. Plusieurs petites valeurs redox bibliographiques sont sous 1e-3 mM : les facteurs de disponibilite doivent etre audites, et non interpretes comme regulation biologique.", "",
        "## References redox : conversion dimensionnelle uniquement", "",
        "| Pool | Supplement Nishino (mM) | Etat J1 courant (mM) |", "|---|---:|---:|",
        *[f"| {label} | {value:.9g} | {readiness['frozen_redox'][label]:.9g} |" for label, value in zip(("NAD", "NADH", "NADP", "NADPH"), (nad, nadh, nadp, nadph))], "",
        f"ATP libre={get('ATP(free)'):.6g} mM; ATP total={get('ATP(total)'):.6g} mM. Ce rapport n'est pas un facteur universel de conversion.",
        f"NAD total de reference={nad+nadh:.9g} mM, fraction NADH={nadh/(nad+nadh):.9g}; NADP total={nadp+nadph:.9g} mM, fraction NADPH={nadph/(nadp+nadph):.9g}. Aucune borne ni distribution statistique n'est deduite de ces points.", "",
        "## Inventaire des sources", "",
        f"Classeur local : {evidence['shape'][0]} pools x {evidence['shape'][1]} jours; {evidence['missing_concentration_count']} cellules manquantes dans les lignes presentes. Les pools absents du classeur restent distincts des cellules manquantes.",
        "Voir source_inventory.csv et nishino_model_reference.csv pour les contextes, jours, formes et roles. Les figures Nishino ne sont pas numerisees; les concentrations experimentales absolues correspondantes ne sont pas inventees.", ""]
    for source in sources:
        lines += [f"### {source['source_id']}", source.get("context", ""),
                  f"Type : {source['measurement_type']}. Utilisation : {source['usable_as']}.",
                  f"[Source primaire]({source['url']})", ""]
    lines += ["## Ambiguite des flux", "",
        f"{structure['measured_balance_count']} canaux retenus apres exclusion des doublons : rang {structure['rank']}, {structure['reaction_count']} reactions, nullite {structure['flux_nullity']}.",
        "Cette analyse concerne les flux a partir de bilans de pools; elle n'etablit pas l'identifiabilite dynamique des concentrations initiales. Les teachers derives des memes concentrations ne sont pas des observations independantes.", "",
        "## Protocole prepare", "",
        "Lire inference_protocol.md : premier bloc NAD total/fraction reduite et NADP total/fraction reduite; cinetiques fixes; tous les 55 etats nominaux J1 verrouilles; autres pools latents inchanges. Aucun ajustement d'ATP, B13PG ou B23PG mesure.",
        "Le premier calcul a autoriser serait un test synthetique d'identifiabilite, pas un fit biologique. Les bornes, erreurs d'observation et limites absolues restent nulles dans la configuration tant que leur evidence manque.", "",
        "## Pieces encore requises", "",
        *[f"- {item}" for item in readiness["blockers"]], "",
        "## Recuperation du supplement JBC", "",
        *[f"- Excel valide : {item['validated_excel']}; {item.get('limitation', '')}" for item in downloads], "",
        "## Reversibilite et preuves", "",
        "L'archive parente, le classeur, les PDF, les sources du modele et les configurations sont verifies par SHA256 avant/apres. Les helpers d'observation sont isoles dans src/fla_latent_inference.py et ne sont pas branches sur la calibration/API.",
        "Reproduction : python scripts/prepare_fla_latent_inference.py --out <nouveau_dossier> ; ajouter --fetch-supplements pour retenter l'acces externe. Verification : meme script --verify <dossier>. Aucun fichier existant n'est ecrase."]
    (out / "decision_report.md").write_text("\n".join(lines)+"\n", encoding="utf-8")


def run(out=DEFAULT_OUT, *, fetch=False):
    out = Path(out).resolve()
    if out.exists():
        raise FileExistsError("fresh preparation archive required")
    design = validate_design(json.loads(CONFIG.read_text()))
    parent = ROOT / design["parent_archive"]
    verify_archive_inputs(parent)
    verify_archive_inputs(ROOT / design["source_audit"])
    paths = [CONFIG, ROOT / design["workbook"], ROOT / design["working_reference"], Path(design["nishino_main"]),
             Path(design["nishino_supplement"]), ROOT / "src/equadiff_brodbar.py", ROOT / "src/rbc_stoichiometry.py",
             ROOT / "src/reaction_positivity.py", ROOT / "src/fla_latent_inference.py", Path(__file__).resolve(),
             ROOT / "scripts/audit_bordbar_source_units_time.py", ROOT / "scripts/run_fla_sparse_teacher_resolution.py",
             parent / "frozen_initial_state.npz", parent / "frozen_parameters.json", parent / "final_verification.json",
             ROOT / "qa/test_fla_latent_inference_preparation.py",
             ROOT / "src/Initial_conditions_JA_Final.xls"]
    hashes = {str(path.resolve()): digest(path) for path in paths}
    evidence, ledger, days, values = workbook_evidence(ROOT / design["workbook"])
    audit = kernel_audit(ROOT / "src/equadiff_brodbar.py")
    names, reactions, matrix = rbc_reaction_matrix()
    measured = evidence["labels"]
    independent = [p for p in measured if p not in design["independent_channels_excluded"]]
    structure = balance_identifiability(matrix, [names.index(pool) for pool in independent])
    structure["individually_identifiable_reactions"] = [reactions[i] for i in structure["individually_identifiable_columns"]]
    references = parse_reference_rows(design["nishino_supplement"])
    for row in references:
        pool = row["candidate_model_pool"]
        row["model_state_exists"] = pool in audit["state_registry"]
        row["present_in_Sheet1"] = pool in measured
        row["mapping_status"] = "candidate_alias_requires_pool_context_review" if row["model_state_exists"] else "no_direct_state_match"
        if row["pool_form"] in ("free", "total"):
            row["mapping_status"] = "free_total_ambiguous_do_not_apply"
    initial = np.load(parent / "frozen_initial_state.npz", allow_pickle=False)
    initial_names, state = initial["names"].tolist(), initial["states"]
    for i, pool in enumerate(measured):
        if state[initial_names.index(pool)] != values[i, 0]:
            raise ValueError("parent is not exact nominal Sheet1 J1")
    frozen_redox = {p: float(state[initial_names.index(p)]) for p in ("NAD", "NADH", "NADP", "NADPH")}
    readiness = {"preparation_complete": True, "biological_inference_ready": False, "ode_integrations_performed": 0,
                 "latent_estimation_performed": False, "kinetic_optimization_performed": False,
                 "parameters_promoted": False, "frozen_redox": frozen_redox,
                 "blockers": ["Definition ATP/ADP/AMP mesuree et operateur libre-total non verifies",
                    "Volume/normalisation et lignage original de Sheet1 non verifies",
                    "Identification originale des signaux B13PG/B23PG et P2G/P3G non verifiee",
                    "Bornes redox applicables et covariance d'observation non disponibles",
                    "Limites absolues de prediction non preregisterees",
                    "Identifiabilite dynamique non testee; le rang des bilans n'est pas ce test",
                    "Donnees relatives originales et ancrages apparies absents pour les sources externes"]}
    out.mkdir(parents=True)
    write_json(out / "preregistered_contract.json", {"created_at": datetime.now(timezone.utc).isoformat(),
        "design": design, "input_sha256": hashes, "biological_contract_changed": False, "optimization_performed": False})
    write_json(out / "workbook_evidence.json", evidence)
    pd.DataFrame(ledger).to_csv(out / "local_pool_inventory.csv", index=False)
    pd.DataFrame([{"pool": pool, "sheet": "Sheet1", "cell": f"{chr(66+j)}{i+2}", "model_day": float(day),
        "nominal_mM": float(values[i,j]), "volume_basis_verified": False,
        "independent_channel": pool in independent, "applied_source_conversion": False}
        for i, pool in enumerate(measured) for j, day in enumerate(days)]).to_csv(out / "local_observation_inventory.csv", index=False)
    pd.DataFrame(design["sources"]).to_csv(out / "source_inventory.csv", index=False)
    write_json(out / "source_inventory.json", design["sources"])
    pd.DataFrame(references).to_csv(out / "nishino_model_reference.csv", index=False)
    write_json(out / "kernel_pool_audit.json", audit)
    write_json(out / "balance_identifiability.json", structure)
    write_json(out / "readiness.json", readiness)
    downloads = []
    if fetch:
        downloads = [fetch_supplement(item, out) for item in design["supplement_downloads"]]
    else:
        downloads = [{**item, "attempted": False, "validated_excel": False, "limitation": "not requested in this run"}
                     for item in design["supplement_downloads"]]
    write_json(out / "download_receipts.json", downloads)
    protocol = ROOT / "tasks/fla_latent_inference_protocol.md"
    (out / "inference_protocol.md").write_bytes(protocol.read_bytes())
    hashes[str(protocol.resolve())] = digest(protocol)
    write_json(out / "preregistered_contract.json", {"created_at": datetime.now(timezone.utc).isoformat(),
        "design": design, "input_sha256": hashes, "biological_contract_changed": False, "optimization_performed": False})
    report(out, evidence, design["sources"], references, audit, structure, readiness, downloads)
    if any(digest(path) != value for path, value in hashes.items()):
        raise ValueError("a frozen source changed during preparation")
    verify_archive_inputs(parent)
    verify_archive_inputs(ROOT / design["source_audit"])
    write_json(out / "final_verification.json", {"independent_archive_checks_pass": True, "biological_contract_changed": False,
        "input_preservation_pass": True, "parent_archives_verified": True,
        "output_sha256": {str(path.relative_to(out)): digest(path) for path in out.rglob("*") if path.is_file()}})
    return verify(out)


def verify(out):
    out = Path(out).resolve()
    contract = verify_archive_inputs(out)
    design = validate_design(contract["design"])
    verify_archive_inputs(ROOT / design["parent_archive"])
    verify_archive_inputs(ROOT / design["source_audit"])
    evidence, _, days, values = workbook_evidence(ROOT / design["workbook"])
    cells = pd.read_csv(out / "local_observation_inventory.csv", float_precision="round_trip")
    np.testing.assert_array_equal(cells.nominal_mM.to_numpy(), values.ravel())
    assert cells.shape[0] == values.size == 770
    np.testing.assert_array_equal(cells.model_day.to_numpy(), np.tile(days, len(evidence["labels"])))
    expected = pd.DataFrame(parse_reference_rows(design["nishino_supplement"]))
    actual = pd.read_csv(out / "nishino_model_reference.csv", float_precision="round_trip")
    np.testing.assert_array_equal(actual.value_M.to_numpy(), expected.value_M.to_numpy())
    assert actual.exact_source_label.tolist() == expected.exact_source_label.tolist()
    assert set(tuple(sorted(pair.values())) for pair in evidence["exact_duplicate_pairs"]) == {("B13PG", "B23PG"), ("P2G", "P3G")}
    readiness = json.loads((out / "readiness.json").read_text())
    assert readiness["ode_integrations_performed"] == 0 and readiness["latent_estimation_performed"] is False
    assert readiness["biological_inference_ready"] is False
    result = {"archive_hashes_pass": True, "source_cells_reconstructed": len(cells), "reference_rows_reconstructed": len(actual),
              "independent_dynamic_identifiability_claimed": False, "ode_integrations_performed": 0}
    print(result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--fetch-supplements", action="store_true")
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    verify(args.verify) if args.verify else run(args.out, fetch=args.fetch_supplements)
