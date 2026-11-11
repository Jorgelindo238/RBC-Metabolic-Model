"""Public SciPy stiff steppers with retained accepted states on RHS failure."""

import numpy as np
import scipy
from scipy.integrate import BDF,Radau,OdeSolution

from fla_balance_audit import accepted_step_quadrature
from fla_integration_diagnostics import RHSProbe,inspect_support


def record_stepper(rhs,initial,end,days,profile,negative_tolerance,method):
    if method not in ("BDF","Radau"):
        raise ValueError("supported public stiff stepper required")
    initial=np.asarray(initial,float)
    if initial.shape!=(114,) or initial[-1]!=7.2 or not np.isfinite(initial).all():
        raise ValueError("finite frozen RBC state required")
    probe=RHSProbe(rhs,list(rhs.names))
    times,states,segments=[1.],[initial.copy()],[]
    solver=None
    failure=None
    message=""
    try:
        solver={"BDF":BDF,"Radau":Radau}[method](probe,1.,initial.copy(),float(end),
            jac_sparsity=rhs.jacobian_sparsity,**profile)
        while solver.status=="running":
            if len(times)>100000:
                raise RuntimeError("accepted-step safety cap exceeded")
            message=solver.step() or ""
            if solver.status=="failed":
                break
            segments.append(solver.dense_output())
            times.append(float(solver.t))
            states.append(solver.y.copy())
    except (ValueError,RuntimeError,FloatingPointError,OverflowError) as error:
        failure={"type":type(error).__name__,"message":str(error)}
    accepted_time=np.array(times)
    accepted_states=np.array(states).T
    complete=bool(failure is None and solver is not None and solver.status=="finished" and times[-1]==end)
    arrays={"initial":initial.copy(),"pool_names":np.array(rhs.names),"accepted_time":accepted_time,"accepted_states":accepted_states}
    report={"method":method,"scipy_version":scipy.__version__,"rtol":float(profile["rtol"]),"atol_mM":float(profile["atol"]),
            "max_step_days":float(profile["max_step"]) if "max_step" in profile else None,
            "negative_tolerance_mM":negative_tolerance,"concentration_gate_pass":False,"supports":{},
            "exception":failure,"complete_exact_J1":complete and bool(np.array_equal(accepted_states[:,0],initial)),
            "internal_RHS_is_not_accepted_state_evidence":True,
            "solver":{"success":complete,"status":solver.status if solver else "initialization_failed","message":message,
                "end_day":times[-1],"nfev":int(solver.nfev) if solver else 0,"njev":int(solver.njev) if solver else 0,
                "nlu":int(solver.nlu) if solver else 0,"accepted_steps":len(times)-1}}
    supports={"accepted":(accepted_time,accepted_states)}
    if segments:
        dense=OdeSolution(accepted_time,segments,alt_segment=method=="BDF")
        grid=np.unique(np.r_[np.linspace(1.,end,301),np.arange(1.,end+1.),days])
        grid=grid[grid<=times[-1]]
        arrays.update(time=grid,states=dense(grid))
        supports["dense"]=(grid,arrays["states"])
        if complete:
            arrays["boundaries"]=np.arange(1.,end+1.)
            for order in (4,8):
                q=accepted_step_quadrature(accepted_time,arrays["boundaries"],order=order)
                x=dense(q.nodes)
                arrays.update({f"q{order}_time":q.nodes,f"q{order}_states":x,
                               f"q{order}_weights":q.weights,f"q{order}_intervals":q.interval_indices})
                supports[f"quadrature{order}"]=(q.nodes,x)
    else:
        arrays.update(time=accepted_time.copy(),states=accepted_states.copy())
        supports["dense"]=(arrays["time"],arrays["states"])
    for key,(t,x) in supports.items():
        report["supports"][key]=inspect_support(t,x[:len(rhs.names)],list(rhs.names),negative_tolerance)
    ph=all(np.array_equal(x[-1],np.full(x.shape[1],initial[-1])) for t,x in supports.values())
    report["clamped_pH_unchanged"]=bool(ph)
    report["concentration_gate_pass"]=bool(complete and ph and len(supports)==4 and all(s["pass"] for s in report["supports"].values()))
    report["internal_RHS"]={"calls":probe.calls,"worst_finite_proposal":probe.minimum,"exception":probe.error,
        "last_day":probe.last_day,"last_nonfinite_pools":[rhs.names[i] for i in range(len(rhs.names)) if probe.last_state is not None and not np.isfinite(probe.last_state[i])]}
    if probe.worst_state is not None:
        arrays["internal_worst_state"]=probe.worst_state
    if probe.last_state is not None:
        arrays["internal_last_state"]=probe.last_state
    return arrays,report
