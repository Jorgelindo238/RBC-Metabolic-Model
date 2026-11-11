from pathlib import Path
import sys

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from fla_bounded_jacobian import BoundedJacobian


def test_resolved_step_for_a_tiny_quadratic_substrate():
    class Quadratic:
        jacobian_sparsity=np.ones((1,1),bool)
        def __call__(self,t,x):return -1e9*x*x
    x=np.array([2e-11])
    exact=-2e9*x[0]
    coarse=BoundedJacobian(Quadratic(),minimum_step=1e-9)(0.,x).toarray()[0,0]
    fine=BoundedJacobian(Quadratic(),minimum_step=1e-15)(0.,x).toarray()[0,0]
    assert abs((coarse-exact)/exact)>10
    assert abs((fine-exact)/exact)<1e-4
