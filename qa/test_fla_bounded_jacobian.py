from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from fla_bounded_jacobian import BoundedJacobian


def test_zero_sensitivity_columns_never_grow_the_sampling_step():
    class Constant:
        jacobian_sparsity=np.ones((4,4),bool)
        def __call__(self,t,x):
            assert np.isfinite(x).all() and np.max(np.abs(x))<2
            return np.ones(4)
    j=BoundedJacobian(Constant(),minimum_step=1e-9)
    for _ in range(400):
        assert np.array_equal(j(0,np.ones(4)).toarray(),np.zeros((4,4)))
    assert j.diagnostics()["largest_requested_step_mM"]<=1e-5
    assert not j.diagnostics()["persistent_step_growth"]


def test_executed_linear_rhs_jacobian_and_input_are_unchanged():
    matrix=np.array([[-2.,1.],[2.,-1.]])
    class Linear:
        jacobian_sparsity=np.ones((2,2),bool)
        def __call__(self,t,x):return matrix@x
    x=np.array([.1,.3]);before=x.copy()
    j=BoundedJacobian(Linear(),minimum_step=1e-9)
    assert np.allclose(j(1.,x).toarray(),matrix,atol=1e-7)
    assert np.array_equal(x,before)


@pytest.mark.parametrize("step",[0.,-1.,np.inf])
def test_invalid_steps_rejected(step):
    with pytest.raises(ValueError):BoundedJacobian(None,minimum_step=step)
