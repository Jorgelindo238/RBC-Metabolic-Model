"""Pinned-source stoichiometry, reversible execution and zero-boundary contracts."""

import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from equadiff_brodbar import equadiff_brodbar, NUM_BASE_METABOLITES
from flux_visualization import FluxTracker
from rbc_gem_audit import (catalog_differences, compare_network, parse_catalog, pool_mapping,
                           project_gem, signature)
from rbc_gem_network import BRANCHES, branch_rates, diagnostic_matrix, equadiff_rbc_gem
from rbc_stoichiometry import STOICHIOMETRY

ARCHIVE = ROOT / "output/rbc_gem_network_audit_2026_10_06"


def state():
    return np.r_[np.full(NUM_BASE_METABOLITES, 0.2), 7.2]


@pytest.fixture(scope="module")
def gem():
    return json.loads((ARCHIVE / "github/1.3.0/model/RBC-GEM.json").read_text())


def test_catalog_declares_and_reconstructs_every_executable_reaction():
    sections, reactions = parse_catalog((ROOT / "RBC/Rxn_RBC.txt").read_text())
    assert catalog_differences(reactions, STOICHIOMETRY) == []
    assert set(sections["ENZREV"]).isdisjoint(sections["ENZIRREV"])
    assert len(sections["ENZREV"] + sections["ENZIRREV"]) == len(reactions) == 100
    assert set(sections["ENZREV"] + sections["ENZIRREV"]) == set(reactions)
    assert len(set(sections["METINT"] + sections["METEXT"])) == 113


def test_existing_parser_reads_complete_catalog_without_adding_metabolites():
    from parse import parse
    model = parse(str(ROOT / "RBC/Rxn_RBC.txt"), strict=True)
    assert model is not None
    assert len(model["react_name"]) == 100
    assert len(model["int_met"] + model["ext_met"]) == 113
    for reaction in model["react_name"]:
        index = model["react_name"].index(reaction)
        actual = {name: model["S"][row, index] for row, name in enumerate(model["int_met"])
                  if model["S"][row, index] != 0}
        actual.update({name: model["ext"][row, index] for row, name in enumerate(model["ext_met"])
                       if model["ext"][row, index] != 0})
        assert actual == STOICHIOMETRY[reaction]


@pytest.mark.parametrize("term,expected", [
    ("H2O2 + 2 GSH", [("H2O2", 1), ("GSH", 2)]),
    ("2GSH + H2O2", [("GSH", 2), ("H2O2", 1)]),
    (".5 O2", [("O2", 0.5)]), ("", []),
])
def test_parser_coefficients_and_empty_sink_side(term, expected):
    from parse import parse_equation_side
    assert [(row["met"], row["coeff"]) for row in parse_equation_side(term)] == expected


def test_parser_accumulates_repeated_species_and_cancels_both_sides(tmp_path):
    from parse import parse
    path = tmp_path / "network.txt"
    path.write_text("-ENZIRREV\nV1\n-METINT\nA B\n-METEXT\nE\n-CAT\nV1 : A + A + B => A + E\n")
    model = parse(str(path), strict=True)
    np.testing.assert_array_equal(model["S"][:, 0], [-1, -1])
    np.testing.assert_array_equal(model["ext"][:, 0], [1])


@pytest.mark.parametrize("mode", ["legacy", "reaction_consistent"])
def test_historical_forwarding_is_bit_identical(mode):
    x, parameters = state(), {"vmax_VHK": 0.7}
    x[13] = 2e-5
    expected = equadiff_brodbar(1.0, x, custom_params=parameters, positivity_policy=mode)
    actual = equadiff_rbc_gem(1.0, x, custom_params=parameters, positivity_policy=mode)
    np.testing.assert_array_equal(expected, actual)


def test_correction_matrix_matches_pinned_gem_reactions(gem):
    names, reactions, matrix = diagnostic_matrix("rbc_gem_core")
    inverse = {value: name for name, value in pool_mapping(gem).items()}
    source = {row["id"]: row for row in gem["reactions"]}
    pairs = {"VH2O2": "CAT", "VXAO": "XAO2", "VXAO2": "XAO",
             "VEGSSG": "GTHOXABCte", "VEURT": "URATEABCte"}
    pairs.update({name: row["gem_id"] for name, row in BRANCHES.items()})
    for local, external in pairs.items():
        projected, unknown, _ = project_gem(source[external], inverse)
        assert unknown == {}
        actual = {name: matrix[index, reactions.index(local)] for index, name in enumerate(names)
                  if matrix[index, reactions.index(local)] != 0}
        assert signature(actual) == signature(projected), (local, external)


def test_oxygen_and_atp_deltas_reconcile_at_fixed_state():
    x, before, after = state(), {}, {}
    baseline = equadiff_brodbar(1.0, x, positivity_policy="reaction_consistent", numerical_audit=before)
    changed = equadiff_rbc_gem(1.0, x, network_mode="rbc_gem_core", numerical_audit=after)
    v = before["effective_fluxes"]
    assert changed[35] - baseline[35] == pytest.approx(v["VOPLAH"] - v["VEGSSG"] - v["VEURT"])
    assert changed[79] - baseline[79] == pytest.approx(v["VXAO2"])
    assert changed[80] - baseline[80] == pytest.approx(-0.5*v["VH2O2"] - v["VXAO"] - v["VXAO2"])
    assert after["effective_fluxes"]["VOPLAH"] == 0.0


@pytest.mark.parametrize("mode", ["redox_stoichiometry", "rbc_gem_core"])
def test_all_zero_boundaries_and_executed_flux_closure(mode):
    names, reactions, matrix = diagnostic_matrix(mode)
    kinetics = {name: {"vmax": 0.4, **{"km_" + pool: 0.2 for pool in row["substrates"]}}
                for name, row in BRANCHES.items()}
    for index in range(NUM_BASE_METABOLITES):
        x, audit = state(), {}
        x[index] = 0.0
        derivative = equadiff_rbc_gem(1.0, x, network_mode=mode, branch_kinetics=kinetics,
                                     numerical_audit=audit)
        assert derivative[index] >= -1e-12, index
        rates = [audit["effective_fluxes"][reaction] for reaction in reactions]
        np.testing.assert_allclose(matrix @ rates, derivative[:len(names)], atol=1e-12)
        assert abs(derivative[75] + derivative[76]) < 1e-12
        assert abs(derivative[77] + derivative[78]) < 1e-12


def test_abc_transport_stops_at_zero_atp_as_a_complete_reaction():
    x, audit = state(), {}
    x[35] = 0.0
    equadiff_rbc_gem(1.0, x, network_mode="rbc_gem_core", numerical_audit=audit)
    assert audit["effective_fluxes"]["VEGSSG"] == 0.0
    assert audit["effective_fluxes"]["VEURT"] == 0.0


def test_tracker_receives_executed_not_historical_rates():
    tracker, audit = FluxTracker(), {}
    derivative = equadiff_rbc_gem(1.0, state(), network_mode="rbc_gem_core",
                                 numerical_audit=audit, flux_tracker=tracker)
    names, reactions, matrix = diagnostic_matrix("rbc_gem_core")
    rates = [tracker.fluxes[name][0] for name in reactions]
    np.testing.assert_allclose(matrix @ rates, derivative[:len(names)], atol=1e-12)


@pytest.mark.parametrize("kinetics", [
    {"bad": {}}, {"VARGN": {"vmax": 0.2}},
    {"VARGN": {"vmax": 0.2, "km_ARG": 0.0}},
    {"VARGN": {"vmax": True, "km_ARG": 0.2}},
    {"VARGN": {"vmax": float("nan"), "km_ARG": 0.2}},
    {"VARGN": {"vmax": -0.2, "km_ARG": 0.2}},
    {"VARGN": {"vmax": 0.2, "km_ARG": 0.2, "unused": 1}},
])
def test_undocumented_or_invalid_branch_kinetics_rejected(kinetics):
    names, _, _ = diagnostic_matrix("rbc_gem_core")
    with pytest.raises(ValueError):
        branch_rates(state()[:113], names, kinetics)


@pytest.mark.parametrize("options", [
    {"network_mode": "bad"},
    {"network_mode": "historical", "branch_kinetics": {"VARGN": {}}},
    {"network_mode": "rbc_gem_core", "positivity_policy": "legacy"},
    {"network_mode": "rbc_gem_core", "curve_fit_strength": 0.2},
])
def test_invalid_modes_forcing_and_historical_extension_fail(options):
    with pytest.raises(ValueError):
        equadiff_rbc_gem(1.0, state(), **options)


def test_branches_disabled_without_explicit_kinetics_and_inputs_unmodified():
    x, parameters, audit = state(), {"vmax_VHK": 0.7}, {}
    original = x.copy()
    equadiff_rbc_gem(1.0, x, network_mode="rbc_gem_core", custom_params=parameters, numerical_audit=audit)
    assert all(audit["raw_fluxes"][name] == 0.0 for name in BRANCHES)
    assert parameters == {"vmax_VHK": 0.7}
    np.testing.assert_array_equal(x, original)


def test_comparison_never_hides_unknown_species_or_merges_compartments(gem):
    mapping = pool_mapping(gem)
    assert mapping["GLC"] != mapping["EGLC"]
    assert mapping["GSH"] != mapping["EGSH"]
    assert "METTHF" not in mapping
    comparison = compare_network(gem, {"fake": {"ATP": -1, "unmeasured_acceptor": 1}})
    assert comparison["comparisons"][0]["status"] == "pool_identity_unresolved"
    assert comparison["comparisons"][0]["forward_matches"] == []


@pytest.mark.parametrize("text", ["-CAT\nV1 : A => B\nV1 : B => A", "-CAT\nV1 : A => B => C"])
def test_duplicate_or_invalid_catalog_rejected(text):
    with pytest.raises(ValueError):
        parse_catalog(text)
