"""Accounting tests, including exact identities against the archived matrix."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from audit_purine_ribose import gross_integrals, IDENTITIES, ROOT


def test_signed_accounting_does_not_hide_reversal():
    net,forward,reverse=gross_integrals(np.array([[2.,-3.]]),np.array([.5,.5]))
    np.testing.assert_allclose(net,[-.5])
    np.testing.assert_allclose(forward,[1.])
    np.testing.assert_allclose(reverse,[1.5])
    np.testing.assert_allclose(net,forward-reverse)


@pytest.mark.parametrize("rates,weights", [([[float('nan')]], [1.]), ([[1.]],[-1.]), ([[1.]], [1.,2.])])
def test_invalid_quadrature(rates,weights):
    with pytest.raises(ValueError):
        gross_integrals(np.array(rates),np.array(weights))


@pytest.mark.parametrize("pool", list(IDENTITIES))
def test_independent_identity_matches_sealed_matrix(pool):
    path=ROOT/"output/ak_pepase_2026_11_11/candidates/ak_balanced_pepase_floor/joint/ultrastrict/flux_evidence.npz"
    if not path.exists():
        pytest.skip("private sealed trajectory unavailable")
    with np.load(path) as a:
        expected=np.array([IDENTITIES[pool].get(r,0.) for r in a["reactions"].tolist()])
        actual=a["matrix"][a["pool_names"].tolist().index(pool)]
    np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-12)
