from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from run_b13pg_ak_coupled import changed_parameters, mechanism


def test_factorial_uses_only_declared_capacities_and_preserves_ak_ratio():
    base = {"vmax_VGAPDH": 6., "vmax_VAK": 2., "vmax_VAK_rev": .2, "vmax_VPGK": 40.}
    assert changed_parameters(base, base, (1., 1.)) == base
    result = changed_parameters(base, base, (1.5, .5))
    assert result == {"vmax_VGAPDH": 9., "vmax_VAK": 1., "vmax_VAK_rev": .1, "vmax_VPGK": 40.}
    assert result["vmax_VAK"]/result["vmax_VAK_rev"] == base["vmax_VAK"]/base["vmax_VAK_rev"]


def row(gap, pgk, ak, adp):
    return {"budgets": {"J2_J4": {"executed_integrals": {"VGAPDH": gap, "VPGK": pgk}},
                        "J1_J4": {"executed_integrals": {"VAK": ak}}}, "J4_prediction_mM": [adp]}


@pytest.mark.parametrize("values, expected", [((2., 2., .5, 2.), True), ((2., 1., .5, 2.), False),
                                                ((2., 2., .5, 1.), False), ((2., 2., 1., 2.), False)])
def test_mechanism_requires_later_supply_and_adenylate_partition(values, expected):
    assert mechanism(row(*values), row(1., 1., 1., 1.), ["ADP"])["pass"] is expected
