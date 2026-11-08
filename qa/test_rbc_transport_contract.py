"""Source-only transport audit and reference-volume conservation checks."""

import copy
import importlib.util
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("transport_contract_audit", ROOT / "scripts/audit_rbc_transport_contract.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


@pytest.mark.parametrize("q", [-2.0, 0.0, 3.0])
@pytest.mark.parametrize("volumes", [(0.6, 0.4, 0.0, 0.0), (0.2, 1.3, 0.02, -0.01), (0.8, 0.2, -0.03, 0.03)])
def test_amount_conservation_including_variable_volume(q, volumes):
    vi, ve, dvi, dve = volumes
    ci, ce = 2.0, 8.0
    di, de = M.amount_transport_derivatives(q, ci, ce, vi, ve, dvi, dve)
    assert vi * di + ci * dvi == pytest.approx(-q)
    assert ve * de + ce * dve == pytest.approx(q)
    assert vi * di + ci * dvi + ve * de + ce * dve == pytest.approx(0, abs=1e-14)


@pytest.mark.parametrize("h", [0.548, 0.6, 0.764])
def test_phase_to_bag_geometry_does_not_equate_concentration_slopes(h):
    ci, ce = 1.0, 20.0
    yi, ye = M.phase_to_bag(ci, ce, h)
    assert yi / h == pytest.approx(ci)
    assert ye / (1 - h) == pytest.approx(ce)
    di, de = M.amount_transport_derivatives(h, ci, ce, h, 1 - h)
    assert di == pytest.approx(-1)
    assert de == pytest.approx(h / (1 - h))
    assert h * di == pytest.approx(-(1 - h) * de)


@pytest.mark.parametrize("h", [0, 1, -0.1, 1.1, math.nan, math.inf, True])
def test_invalid_hematocrit_rejected(h):
    with pytest.raises(ValueError):
        M.phase_to_bag(1.0, 2.0, h)


@pytest.mark.parametrize("vol", [0, -1, math.nan, math.inf, True])
def test_invalid_volume_rejected(vol):
    with pytest.raises(ValueError):
        M.amount_transport_derivatives(1, 1, 1, vol, 1)


@pytest.mark.parametrize("q,ci,ce", [(math.nan, 1, 1), (1, -1, 1), (1, 1, math.inf), (True, 1, 1)])
def test_invalid_rates_and_concentrations_rejected(q, ci, ce):
    with pytest.raises(ValueError):
        M.amount_transport_derivatives(q, ci, ce, 0.6, 0.4)


@pytest.mark.parametrize("key", ["production_enabled", "normalization_enabled", "optimization_enabled"])
def test_audit_cannot_enable_production(key):
    config = copy.deepcopy(M.read_json(M.CONFIG))
    config[key] = True
    with pytest.raises(ValueError):
        M.validate_config(config)


def test_jbc_selected_cells_match_original_workbook():
    rows, stats = M.inspect_jbc(M.read_json(M.CONFIG))
    assert len(rows) == 876
    assert sum(r["channel_id"] == "assay!D" for r in rows) == 126
    hct = [r for r in stats if r["channel_id"] == "assay!D"]
    assert min(r["minimum"] for r in hct) == 0.548
    assert max(r["maximum"] for r in hct) == 0.764
    assert next(r for r in hct if r["temperature_C"] == 4)["n"] == 24
    assert all(not r["donor_id"] and r["training_enabled"] == "False" for r in rows)


def test_local_source_is_preserved_not_relabelled_bag_basis():
    result = M.inspect_sheet1()
    assert result["header"] == "Conc / mM"
    assert result["reported_days"] == [1, 4, 8, 11, 15, 18, 22, 25, 29, 32, 36, 38, 43, 46]
    assert {r["channel"] for r in result["channels"]} == {"GLC", "EGLC", "LAC", "ELAC"}
    assert all(not r["denominator_verified"] for r in result["channels"])


def test_pinned_gem_glucose_lactate_and_boundaries():
    versions = []
    for v in ("1.2.0", "1.3.0"):
        base = M.NETWORK / "github" / v
        versions.append(M.inspect_gem(base / "model/RBC-GEM.json"))
    assert M.comparable_transports(versions[0]) == M.comparable_transports(versions[1])
    assert sum(a != b for a, b in zip(*versions)) == 11
    reactions = {r["id"]: r for r in versions[1]}
    assert reactions["GLC_Dt"]["stoichiometry"] == {"glc__D_c": -1, "glc__D_e": 1}
    assert reactions["L_LACt2"]["stoichiometry"] == {"h_c": -1, "h_e": 1, "lac__L_c": -1, "lac__L_e": 1}
    assert len([r for r in versions[1] if r["lactate_transport"]]) == 12
    assert reactions["PYR_LLACtex"]["positive_flux_lactate_direction"] == "import"
    assert reactions["LLAC_Cltex"]["positive_flux_lactate_direction"] == "export"
    assert reactions["EX_glc__D_e"]["stoichiometry"] == {"glc__D_e": -1}
    assert reactions["EX_lac__L_e"]["stoichiometry"] == {"lac__L_e": -1}


def test_no_automatic_donor_or_ph_or_proteomic_conversion():
    config = M.read_json(M.CONFIG)
    assert config["validation_policy"]["donor_ids_from_positional_blocks"] is False
    assert config["validation_policy"]["validation_split_created"] is False
    for key in ("gem_bounds_are_vmax", "automatic_proteomic_vmax_conversion", "automatic_ph_input", "automatic_gem_boundary_reservoir"):
        assert config["prospective_kinetics"][key] is False
