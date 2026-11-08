"""Carbon/folate/redox budgets and strict reversible initialization contracts."""

import json
from pathlib import Path
import sys

import numpy as np
import pytest
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from equadiff_brodbar import equadiff_brodbar
from rbc_biochemical_extensions import (BRANCHES, NEW_POOLS, REDOX_GROUPS, biochemical_matrix,
                                       build_initial_state, equadiff_biochemical, extension_rates)
from reaction_positivity import limit_signed_fluxes


def initial(mode="vcse_folate", methyl=0.1):
    old = np.r_[np.full(113, 0.2), 7.2]
    added = {name: 0.1 for name in NEW_POOLS if name != "MLTHF"}
    partition = {"MTHF": methyl, "MLTHF": 0.2 - methyl} if mode != "vcse_c4" else None
    return build_initial_state(old, mode=mode, added_initial=added, folate_partition=partition)


def kinetics(reactions=None):
    return {name: {"vmax": 0.2, **{"km_" + s: 0.1 for s in BRANCHES[name]["substrates"]}}
            for name in (BRANCHES if reactions is None else reactions)}


@pytest.mark.parametrize("policy", ["legacy", "reaction_consistent"])
def test_historical_forwarding_identical(policy):
    x = np.r_[np.full(113, 0.2), 7.2]
    np.testing.assert_array_equal(equadiff_biochemical(1, x, positivity_policy=policy),
                                  equadiff_brodbar(1, x, positivity_policy=policy))


def test_expanded_initial_preserves_old_values_and_folate_total():
    x = initial()
    assert len(x) == 125 and x[-1] == 7.2
    assert x[47] == 0.1 and x[114] == 0.1
    assert np.all(np.delete(x[:113], 47) == 0.2)
    names, _, matrix = biochemical_matrix("vcse_folate")
    assert matrix.shape == (124, 112) and not matrix.flags.writeable
    assert names[113:] == NEW_POOLS


@pytest.mark.parametrize("partition", [None, {}, {"MTHF": 0.1}, {"MTHF": 0.2, "MLTHF": 0.2},
                                        {"MTHF": float("nan"), "MLTHF": 0},
                                        {"MTHF": -0.1, "MLTHF": 0.3}])
def test_folate_partition_must_be_explicit_finite_and_preserve_total(partition):
    with pytest.raises(ValueError):
        build_initial_state(np.r_[np.full(113, 0.2), 7.2], mode="vcse_folate",
                            added_initial={name: 0 for name in NEW_POOLS if name != "MLTHF"},
                            folate_partition=partition)


def test_added_pool_initials_required_and_original_state_unmodified():
    old = np.r_[np.full(113, 0.2), 7.2]
    before = old.copy()
    with pytest.raises(ValueError):
        build_initial_state(old, mode="vcse_c4", added_initial={})
    build_initial_state(old, mode="vcse_c4", added_initial={n: 0 for n in NEW_POOLS if n != "MLTHF"})
    np.testing.assert_array_equal(old, before)


def test_carbon_and_nitrogen_closed_cse_column_not_akg():
    names, reactions, matrix = biochemical_matrix("vcse_folate")
    column = matrix[:, reactions.index("VCSE")]
    assert column[names.index("AKG")] == 0
    for weights in ({"CYSTHIO": 7, "CYS": 3, "AKB": 4},
                    {"CYSTHIO": 2, "CYS": 1, "NH4": 1}):
        assert sum(column[names.index(n)] * value for n, value in weights.items()) == 0


def test_folates_not_directly_aliased_and_total_conserved():
    names, reactions, matrix = biochemical_matrix("vcse_folate")
    assert matrix[names.index("MTHF"), reactions.index("VSHMT")] == 0
    assert matrix[names.index("MLTHF"), reactions.index("VSHMT")] == 1
    assert matrix[names.index("MTHF"), reactions.index("VMESE")] == -1
    np.testing.assert_array_equal(matrix[[names.index(n) for n in ("THF", "MTHF", "MLTHF")]].sum(0), 0)
    assert not any(extension_rates(initial()[:-1], names).values())


@pytest.mark.parametrize("group", REDOX_GROUPS)
def test_complete_redox_module_required(group):
    names, _, _ = biochemical_matrix("vcse_folate")
    with pytest.raises(ValueError, match="complete"):
        extension_rates(initial()[:-1], names, kinetics(group[:1]))


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True])
def test_invalid_new_kinetics_rejected(value):
    rates = kinetics()
    rates["VMTHFR"]["vmax"] = value
    names, _, _ = biochemical_matrix("vcse_folate")
    with pytest.raises(ValueError):
        extension_rates(initial()[:-1], names, rates)


def test_mthfr_requires_folate_split_and_explicit_kms():
    names, _, _ = biochemical_matrix("vcse_c4")
    with pytest.raises(ValueError):
        extension_rates(initial("vcse_c4")[:-1], names, kinetics(("VMTHFR",)))
    names, _, _ = biochemical_matrix("vcse_folate")
    with pytest.raises(ValueError):
        extension_rates(initial()[:-1], names, {"VMTHFR": {"vmax": 0.1}})
    invalid = kinetics(("VMTHFR",))
    invalid["VMTHFR"]["km_NADPH"] = 0
    with pytest.raises(ValueError):
        extension_rates(initial()[:-1], names, invalid)


def test_redox_electron_ledgers_and_pool_totals():
    names, reactions, matrix = biochemical_matrix("vcse_folate")
    groups = [(REDOX_GROUPS[0], {"NADH": 2, "CYB5RED": 1, "HBFE2": 1}),
              (REDOX_GROUPS[1], {"NADPH": 2, "TXNRED": 2, "PRDXRED": 2, "H2O2": -2})]
    for group, weights in groups:
        for reaction in group:
            assert sum(matrix[names.index(n), reactions.index(reaction)] * w
                       for n, w in weights.items()) == 0
    for pools in (("CYB5OX", "CYB5RED"), ("HBFE3", "HBFE2"), ("TXNOX", "TXNRED"),
                  ("PRDXRED", "PRDXSO", "PRDXOX"), ("NAD", "NADH"), ("NADP", "NADPH")):
        np.testing.assert_array_equal(matrix[[names.index(n) for n in pools]].sum(0), 0)


@pytest.mark.parametrize("mode", ["vcse_c4", "folate_split", "vcse_folate"])
def test_all_zero_boundaries_are_invariant_under_executed_reactions(mode):
    x = initial(mode)
    active = kinetics() if mode != "vcse_c4" else kinetics(tuple(BRANCHES)[1:])
    for index in range(124):
        point = x.copy()
        point[index] = 0
        audit = {}
        dx = equadiff_biochemical(1, point, network_mode=mode, extension_kinetics=active,
                                 numerical_audit=audit)
        assert dx[index] >= -1e-14, (mode, index)
        names, reactions, matrix = biochemical_matrix(mode)
        np.testing.assert_allclose(dx[:-1], matrix @ [audit["effective_fluxes"][r] for r in reactions], atol=1e-14)


def test_oplah_retained_default_and_off_is_named_countertest():
    x, keep, off = initial(), {}, {}
    equadiff_biochemical(1, x, network_mode="vcse_folate", numerical_audit=keep)
    equadiff_biochemical(1, x, network_mode="vcse_folate", oplah_policy="diagnostic_off", numerical_audit=off)
    assert keep["raw_fluxes"]["VOPLAH"] > 0
    assert off["raw_fluxes"]["VOPLAH"] == 0
    assert keep["oplah_policy"] == "retained"


def test_tracker_gets_extended_effective_rates_and_input_is_not_mutated():
    class Capture:
        def add_timepoint(self, time, fluxes):
            self.fluxes = fluxes
    x, before, capture, audit = initial(), initial(), Capture(), {}
    equadiff_biochemical(1, x, network_mode="vcse_folate", extension_kinetics=kinetics(),
                         flux_tracker=capture, numerical_audit=audit)
    np.testing.assert_array_equal(x, before)
    assert all(capture.fluxes[r] == audit["effective_fluxes"][r] for r in BRANCHES)


@pytest.mark.parametrize("options", [{"positivity_policy": "legacy"}, {"curve_fit_strength": 0.1}])
def test_legacy_and_forcing_rejected(options):
    with pytest.raises(ValueError):
        equadiff_biochemical(1, initial(), network_mode="vcse_folate", **options)


@pytest.mark.parametrize("group", REDOX_GROUPS)
def test_synthetic_redox_chain_is_bounded_by_available_acceptors(group):
    names, reactions, matrix = biochemical_matrix("vcse_folate")
    selected = matrix[:, [reactions.index(r) for r in group]]
    x = np.zeros(len(names))
    for name in ("NADH", "NADPH", "CYB5OX", "HBFE3", "TXNOX", "PRDXOX", "H2O2"):
        x[names.index(name)] = 0.1
    def rhs(t, states):
        rates = extension_rates(states, names, kinetics(group))
        effective, _ = limit_signed_fluxes(states, np.array([rates[r] for r in group]), selected, threshold=0.001)
        return selected @ effective
    solution = solve_ivp(rhs, (0, 2), x, method="BDF", rtol=1e-8, atol=1e-10, dense_output=True)
    assert solution.success and solution.y.min() >= -1e-10
    assert solution.sol(np.linspace(0, 2, 101)).min() >= -1e-10
    if group == REDOX_GROUPS[0]:
        donor = names.index("NADH")
        bound = (x[names.index("CYB5OX")] + x[names.index("HBFE3")]) / 2
    else:
        donor = names.index("NADPH")
        bound = sum(x[names.index(n)] for n in ("TXNOX", "PRDXOX", "H2O2"))
    assert 0 < x[donor] - solution.y[donor, -1] <= bound + 1e-8
    assert np.all(solution.y[names.index("ATP")] == 0)


def test_pinned_gem_methemoglobin_column_has_an_electron_accounting_mismatch():
    path = ROOT / "output/rbc_gem_network_audit_2026_10_06/github/1.3.0/model/RBC-GEM.json"
    if not path.exists():
        pytest.skip("Pinned local source unavailable")
    model = json.loads(path.read_text())
    source = next(r for r in model["reactions"] if r["id"] == "METHBCYTBR")
    assert source["metabolites"]["focytb5_c"] == -2
    assert source["metabolites"]["hb_c"] == 1
    assert sum(source["metabolites"].get(n, 0) * w for n, w in {"focytb5_c": 1, "hb_c": 1}.items()) == -1
