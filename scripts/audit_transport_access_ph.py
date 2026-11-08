"""Build or reconstruct the accessible-pool/pH contract without ODE fitting."""

import argparse
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys

import numpy as np
import openpyxl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fla_jbc_data import read_workbook
from fla_transport_access_ph import buffered_rates, clamped_reservoirs, export_bound, lactate_drive, readiness

CONFIG = ROOT / "config/fla_transport_access_ph_contract.json"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def csv_rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def json_write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def previous_integrity(previous):
    manifest = json.loads((previous / "manifest.json").read_text())
    count = 0
    for base, key in ((ROOT, "input_sha256"), (previous, "output_sha256")):
        for name, expected in manifest[key].items():
            require(sha(base / name) == expected, "previous sealed evidence changed: " + name)
            count += 1
    return count


def calculate():
    config = json.loads(CONFIG.read_text())
    previous = ROOT / config["previous_archive"]
    old_checks = previous_integrity(previous)
    old_design = json.loads((ROOT / "config/fla_distinct_volume_transport.json").read_text())
    source = ROOT / old_design["jbc_workbook"]
    require(sha(source) == old_design["jbc_sha256"], "JBC source changed")
    _, _, observations = read_workbook(source)
    lookup = {(r["sheet"] + "!" + r["source_cell"]): r for r in observations}
    records = csv_rows(previous / "source_preparation/phase_observations_pairing_sensitivity.csv")
    require(len(records) == 144 and len({r["pairing_id"] for r in records}) == 6, "incomplete six-pairing screen")
    checks = old_checks
    bounds, directions = [], []
    design = config["diagnostic_design"]
    for r in records:
        for pool in ("GLC", "EGLC", "LAC", "ELAC"):
            require(float(r[pool + "_phase_mM"]) == lookup[r[pool + "_source_cell"]]["value"], "original concentration changed")
            checks += 1
        hrow = lookup["assay!" + r["hematocrit_source_cell"]]
        require(float(r["hematocrit"]) == hrow["value"], "geometry changed")
        require(r["pairing_verified"] == "False" and not r["donor_id"], "invented donor")
        checks += 2
        li, le = float(r["LAC_phase_mM"]), float(r["ELAC_phase_mM"])
        key = {"pairing_id": r["pairing_id"], "endo_key": r["endo_trajectory_key"], "assay_key": r["assay_trajectory_key"],
               "source_day": float(r["source_day"]), "LAC_source_cell": r["LAC_source_cell"], "ELAC_source_cell": r["ELAC_source_cell"],
               "LAC_observed_mM": li, "ELAC_observed_mM": le}
        for rho in design["lactate_accessibility_ratio_i_over_e"]:
            bound = export_bound(li, le, rho)
            require(math.isclose(bound, math.log10(rho * li / le), abs_tol=1e-14), "independent bound failed")
            checks += 1
            bounds.append({**key, "accessibility_ratio_i_over_e": rho, "delta_pH_export_upper_bound": bound,
                           "measured_pH": False, "activity_mapping_verified": False})
            for delta in design["pHi_minus_pHe"]:
                drive = lactate_drive(li, le, accessibility_ratio=rho, delta_pH=delta)
                direction = "export" if drive > 0 else "import" if drive < 0 else "equilibrium"
                require((drive > 0) == (delta < bound), "directional inequality failed")
                # Fixed rho and delta enter only through delta - log10(rho) for the sign.
                same = lactate_drive(li, le, accessibility_ratio=1, delta_pH=delta - math.log10(rho))
                require(math.isclose(drive / rho, same, rel_tol=1e-12, abs_tol=1e-12), "access/pH confounding identity failed")
                checks += 2
                directions.append({**key, "accessibility_ratio_i_over_e": rho, "delta_pH": delta,
                                   "effective_delta_pH": delta - math.log10(rho), "normalized_drive_mM": drive,
                                   "direction": direction, "status": "conditional_algebra_not_measured_or_fitted"})
    ph_rows = []
    for r in observations:
        if r["temperature_C"] == 4 and r["channel_id"] in ("assay!Y", "assay!Z"):
            ph_rows.append({"source_cell": r["sheet"] + "!" + r["source_cell"], "source_day": r["source_day"],
                "positional_block": r["replicate_block_index"], "value": r["value"], "original_label": r["exact_source_label"],
                "storage_temperature_C": 4, "measurement_or_report_temperature_C": 37 if r["channel_id"] == "assay!Y" else 22,
                "measurement_or_report": "measured_37C_per_supplement" if r["channel_id"] == "assay!Y" else "reported_22C_channel_method_unresolved",
                "pHi_assignment": False, "pHe_at4C_assignment": False})
    require(len(ph_rows) == 48 and all(r["value"] is not None for r in ph_rows), "pH channel coverage")
    checks += 1
    counterfactuals = []
    campaign = json.loads((previous / "fixed_context_v2/summary.json").read_text())
    for case in campaign["results"]:
        if not case["case"].startswith("phase_glut_mct"):
            continue
        h = case["hematocrit"]
        with np.load(previous / "fixed_context_v2" / (case["case"] + "_" + case["tolerance"]) / "replay.npz") as a:
            idx = list(a["reactions"]).index("VELAC")
            integrated = float(a["executed8"][idx].sum())
            require(math.isclose(integrated, case["executed_transport_integrals_cell_mM"]["VELAC"], abs_tol=1e-12), "executed integral mismatch")
            names = list(a["pool_names"])
            change = a["states"][names.index("ELAC"), -1] - a["states"][names.index("ELAC"), 0]
            require(math.isclose((1 - h) * change, h * integrated, rel_tol=1e-5, abs_tol=1e-7), "external lactate amount closure")
            checks += 2
        q = h * integrated
        ri, re = clamped_reservoirs(q, source_i_bag=0, source_e_bag=0)
        require(ri == q and re == -q, "clamped MCT-only reservoir signs")
        checks += 1
        for bi, be in itertools.product(design["beta_i_mM_per_L_cells_per_pH"], design["beta_e_mM_per_L_supernatant_per_pH"]):
            dpi, dpe = buffered_rates(q, hct=h, beta_i=bi, beta_e=be, source_i_bag=0, source_e_bag=0)
            residual = -h * bi * dpi - (1 - h) * be * dpe
            require(abs(residual) < 1e-12, "acid-equivalent closure")
            require(dpi < 0 < dpe, "import must acidify cells and alkalinize medium")
            checks += 2
            counterfactuals.append({"case": case["case"], "tolerance": case["tolerance"], "hematocrit": h,
                "executed_MCT_integral_cell_mM": integrated, "MCT_proton_integral_mmol_per_L_bag": q,
                "beta_i_mM_per_L_cells_per_pH": bi, "beta_e_mM_per_L_supernatant_per_pH": be,
                "frozen_flux_delta_pHi": dpi, "frozen_flux_delta_pHe": dpe,
                "clamped_intracellular_reservoir_acid_mmol_per_L_bag": ri,
                "clamped_extracellular_reservoir_acid_mmol_per_L_bag": re,
                "acid_closure_residual_mmol_per_L_bag": residual,
                "status": "MCT_only_frozen_integral_counterfactual_not_free_pH_prediction"})
    status = readiness(config)
    require(status["missing"] and not status["free_pH_prediction_authorized"], "unsupported free prediction allowed")
    zero = [r["delta_pH_export_upper_bound"] for r in bounds if r["source_day"] == 0 and r["accessibility_ratio_i_over_e"] == 1]
    phi = [r["frozen_flux_delta_pHi"] for r in counterfactuals]
    phe = [r["frozen_flux_delta_pHe"] for r in counterfactuals]
    summary = {"verified_algebra_and_source_checks": checks, "previous_seal_hash_checks": old_checks,
        "pairing_records": len(records), "accessibility_bounds": len(bounds), "conditional_directions": len(directions),
        "pH_source_records": len(ph_rows), "frozen_integral_buffer_counterfactuals": len(counterfactuals),
        "source_day0_equal_mapping_bound_range": [min(zero), max(zero)],
        "frozen_flux_delta_pHi_range": [min(phi), max(phi)], "frozen_flux_delta_pHe_range": [min(phe), max(phe)],
        "local_transport_prerequisites": status, "new_ODE_replays": 0, "optimizer_trials": 0,
        "measured_initial_state_changed": False, "production_defaults_changed": False, "biological_promotion": False}
    return {"accessibility_bounds.csv": bounds, "conditional_directions.csv": directions,
            "source_pH_channels.csv": ph_rows, "executed_MCT_buffer_counterfactuals.csv": counterfactuals}, summary


def build(out):
    require(not out.exists(), "use a new archive directory; existing evidence is immutable")
    tables, summary = calculate()
    out.mkdir(parents=True)
    for name, rows in tables.items():
        write_csv(out / name, rows)
    json_write(out / "contract.json", json.loads(CONFIG.read_text()))
    json_write(out / "summary.json", summary)
    literature = [
        {"source": "Swietach et al.2010", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC3036193/",
         "doi": "10.1113/jphysiol.2010.197392", "evidence": "Primary full-text search extract and institutional PDF methods/intro read; direct PMC reopening encountered recaptcha.",
         "context": "Resting pHi and intrinsic buffering depend on medium; AE1 recovery and Hb buffering examined at37C, with25C flow cytometry. Paper uses75% cell water for its own conversion, not a measurement for our storage cohort.",
         "transfer": "mechanism and context only; no automatic4C pH, water fraction or beta assignment"},
        {"source": "Jennings2013/2014", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC4042536/",
         "evidence": "Full-text Methods/Modeling read.",
         "context": "Washed RBC experiments at37C estimate65-69 mmol/L-cells/pH and model the four Jacobs-Stewart steps with water volumes.",
         "transfer": "65 is a context-labeled sensitivity anchor, not a SAGM4C prior"},
        {"source": "Guppy et al.1992", "url": "https://pubmed.ncbi.nlm.nih.gov/1519370/",
         "evidence": "Primary abstract/search result read.",
         "context": "Storage suspension pH and glycolytic pH dependence vary with temperature.",
         "transfer": "supports requiring temperature-specific metadata, not a universal correction"}
    ]
    json_write(out / "literature_context.json", literature)
    report = """# Accessible transport pools and pH/buffer contract

This is a successor diagnostic contract, not a calibration, a new ODE replay or a physiological pH estimate. Original concentrations, exact J1, frozen kinetics, historical defaults and the previous sealed campaign remain unchanged. No uFBA observation normalization is applied.

## Observation-to-activity operator

For an uncorrected extractable observation C on its declared phase litre, define a_mM = gamma*f*C/(w*r). f is the accessible free substrate fraction, w the aqueous fraction of that phase, r the analytical recovery fraction and gamma the activity coefficient (activity represented on a1mM standard). Already recovery-corrected measurements must use r=1 with supporting processing evidence. For lactate, the selected substrate is free L-lactate anion; total lactate speciation cannot be assumed without its acid dissociation contract. Missing values remain null. No single-cell volume is required to read mM; converting a packed-cell extract to accessible aqueous concentration is a different operation.

Hematocrit sets amount coupling, not membrane chemical equilibrium. Let lambda_i and lambda_e be the above effective activity scales and rho=lambda_i/lambda_e. Conditional MCT export requires:

```text
pHi - pHe < log10(LAC/ELAC) + log10(rho)
effective_delta_pH = pHi - pHe - log10(rho)
```

Only this combination determines direction in the reduced drive. Directionality alone cannot separately identify free fractions, recovery, cell water and pH. Glucose equilibrium likewise requires lambda_Gi*GLC=lambda_Ge*EGLC. The old effective Km/conductance values cannot silently become free-activity parameters: their coordinate and extent basis need rederivation or independently supported values before activation. The diagnostic rho and delta grid is deliberately not fitted or labeled physiological.

## Acid-equivalent bookkeeping

For fixed Vi=H Vbag and Ve=(1-H)Vbag, signed J_H is proton export in mmol/L-bag/day, taken from the EXECUTED MCT flux, J_H=H*j_MCT. Positive s_i/s_e are other acid sources on the same bag basis:

```text
d pHi/dt = -(s_i-J_H)/(H*beta_i)
d pHe/dt = -(s_e+J_H)/((1-H)*beta_e)
-H*beta_i*d pHi/dt -(1-H)*beta_e*d pHe/dt = s_i+s_e
```

beta_i is per litre packed cells; beta_e per litre supernatant. Positive export alkalinizes cells and acidifies medium; import does the opposite. Local beta equations are not a complete global titration model when pH, temperature, Hb oxygenation, CO2 or composition vary. Hb/phosphate/bicarbonate terms must either be included in a supported effective total capacity or modeled explicitly with intrinsic capacity, never counted twice. Explicit carbonate requires carbon conservation, CA, AE1/Cl/HCO3 coupling, gas boundary and sampling/hemolysis terms. AE1 is not a standalone proton pump. No fixed proton count per LDH/ATP reaction is inferred from biochemical names or from this carbon-only stoichiometric projection.

Clamped pH requires reservoir acid terms R_i=J_H-s_i and R_e=-J_H-s_e. The reported ledger includes MCT only, not an invented complete metabolic acid balance. Applying archived flux integrals to constant capacities gives a frozen-flux counterfactual; changing pH would change fluxes and requires a new coupled replay. It is not a pH prediction.

## Source and code findings

The original assay!Y and assay!Z values for4C storage are exported with exact locators, but carry37C-measurement and22C-reported contexts respectively. Neither is a pHi measurement nor a justified4C pHe assignment. There is no universal temperature conversion in this contract. All six donor-sheet permutations remain hypotheses and are retained equally.

The historical kernel's native pHi equation is empirical. Its perturbation branch uses an intracellular buffer constant30 and pH-gradient terms without a complete two-compartment proton/carbon inventory; comments reference minute/hour conversion inside a day-based ODE. MCT proton coupling is absent. Therefore these terms are not adopted here or added to the new ledger. This audit identifies missing contracts, not an authorized production patch to historical behavior.

Primary context: [Swietach2010](https://pmc.ncbi.nlm.nih.gov/articles/PMC3036193/) supports Hb/AE1 and medium-dependent buffering; [Jennings](https://pmc.ncbi.nlm.nih.gov/articles/PMC4042536/) provides37C capacity/volume context; [Guppy1992](https://pubmed.ncbi.nlm.nih.gov/1519370/) supports temperature dependence. The beta_i grid30/65/85 combines the historical anchor and literature-context anchors. beta_e1/10/30 is synthetic. None is a measured SAGM4C capacity. Literature retrieval/transfer limitations are recorded in literature_context.json.

## Executed checks

"""
    report += f"Reconstructed {summary['pairing_records']} original pairing records, {summary['accessibility_bounds']} accessibility bounds, {summary['conditional_directions']} directional counterfactuals, {summary['pH_source_records']} source pH cells and {summary['frozen_integral_buffer_counterfactuals']} frozen-integral buffer ledgers. {summary['verified_algebra_and_source_checks']} source/algebra/archive checks passed. The equal-mapping source-day0 export bounds remain {summary['source_day0_equal_mapping_bound_range']}.\n\n"
    report += f"MCT-only frozen-integral delta_pHi range: {summary['frozen_flux_delta_pHi_range']}; delta_pHe range: {summary['frozen_flux_delta_pHe_range']}. These are not simulated or measured pH changes. ATP outcomes are unchanged because no new ODE replay ran.\n\n"
    report += "## Remaining prerequisites\n\n"
    report += "\n".join("- " + name for name in summary["local_transport_prerequisites"]["missing"])
    report += "\n\nNext: establish source processing and temperature-compatible pHi/pHe or an independently supported acid/base observation model; then preregister a synthetic coupled carrier/buffer recovery test at fixed geometry before any biological fit. The local prerequisite inventory does not replace existing biological readiness, donor linkage, uncertainty or absolute-accuracy gates.\n"
    (out / "decision_report.md").write_text(report, encoding="utf-8")
    protected = [CONFIG, Path(__file__), ROOT / "src/fla_transport_access_ph.py", ROOT / "qa/test_transport_access_ph.py",
                 ROOT / old_design_path(), ROOT / "src/fla_jbc_data.py", ROOT / "src/equadiff_brodbar.py",
                 ROOT / "config/fla_working_reference.json", ROOT / json.loads((ROOT / old_design_path()).read_text())["jbc_workbook"],
                 ROOT / json.loads(CONFIG.read_text())["previous_archive"] / "manifest.json"]
    json_write(out / "manifest.json", {
        "input_sha256": {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p) for p in protected},
        "output_sha256": {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()},
        "preserves_previous_seal": True})
    return verify(out)


def old_design_path():
    return "config/fla_distinct_volume_transport.json"


def verify(out):
    manifest = json.loads((out / "manifest.json").read_text())
    for base, key in ((ROOT, "input_sha256"), (out, "output_sha256")):
        for name, expected in manifest[key].items():
            require(sha(base / name) == expected, "sealed input/output changed: " + name)
    tables, summary = calculate()
    for name, rows in tables.items():
        stored = csv_rows(out / name)
        expected = [{k: str(v) for k, v in r.items()} for r in rows]
        require(stored == expected, "reconstruction mismatch: " + name)
    require(json.loads((out / "summary.json").read_text()) == summary, "summary reconstruction mismatch")
    return {"verified": True, **summary}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if bool(args.out) == bool(args.verify):
        parser.error("supply exactly one of --out or --verify")
    print(json.dumps(build(args.out.resolve()) if args.out else verify(args.verify.resolve()), indent=2))
