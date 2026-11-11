"""Stateless bounded finite differences for the existing executed RHS."""

import numpy as np
from scipy.sparse import csc_matrix
from scipy.optimize._numdiff import approx_derivative,group_columns


class BoundedJacobian:
    """Do not grow persistent FD factors on insensitive columns.

    SciPy 1.17.1 supplies the sparse finite-difference implementation. This
    adapter bounds its explicit sampling steps; it never clips model states.
    """

    def __init__(self,rhs,*,minimum_step,relative_step=np.sqrt(np.finfo(float).eps),maximum_step=1e-5):
        if not 0<minimum_step<=maximum_step or not np.isfinite([minimum_step,relative_step,maximum_step]).all() or relative_step<=0:
            raise ValueError("finite ordered Jacobian step bounds required")
        self.rhs=rhs
        self.minimum_step,self.relative_step,self.maximum_step=minimum_step,relative_step,maximum_step
        structure=csc_matrix(rhs.jacobian_sparsity)
        self.sparsity=(structure,group_columns(structure))
        self.calls,self.rhs_calls=0,0
        self.largest_step=0.

    def __call__(self,t,x):
        x=np.asarray(x,float)
        if not np.isfinite(x).all():
            raise ValueError("nonfinite Jacobian base state")
        h=np.clip(self.relative_step*np.abs(x),self.minimum_step,self.maximum_step)
        if not np.isfinite(x+h).all() or np.any(x+h==x):
            raise ValueError("bounded Jacobian perturbation is not representable")
        self.calls+=1
        self.largest_step=max(self.largest_step,float(h.max()))
        def evaluate(y):
            if not np.isfinite(y).all():
                raise ValueError("nonfinite bounded Jacobian sample")
            self.rhs_calls+=1
            return self.rhs(t,y)
        return approx_derivative(evaluate,x,method="2-point",abs_step=h,sparsity=self.sparsity)

    def diagnostics(self):
        return {"implementation":"scipy.optimize._numdiff.approx_derivative, fixed 2-point sparse steps",
                "jacobian_calls":self.calls,"RHS_samples":self.rhs_calls,"minimum_step_mM":self.minimum_step,
                "maximum_step_mM":self.maximum_step,"largest_requested_step_mM":self.largest_step,
                "persistent_step_growth":False,"states_clipped":False}
