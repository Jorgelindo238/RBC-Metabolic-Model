"""Fail-closed BDF evidence with species/time diagnostics before rejection."""

import numpy as np
from scipy.integrate import solve_ivp

from fla_balance_audit import accepted_step_quadrature,integrate_intervals
from fla_agentic_vmax_replay import within


class ConcentrationRejected(ValueError):
    def __init__(self,diagnostics):
        super().__init__("recorded integration failed concentration policy")
        self.diagnostics=diagnostics


def inspect_support(time,states,names,negative_tolerance):
    t,x=np.asarray(time,float),np.asarray(states,float)
    if x.ndim!=2 or x.shape!=(len(names),len(t)) or not len(t) or not np.isfinite(t).all() or (np.diff(t)<0).any():
        raise ValueError("aligned ordered support and species states required")
    per_species=[]
    finite=np.isfinite(x)
    for i,pool in enumerate(names):
        good=np.flatnonzero(finite[i])
        j=int(good[np.argmin(x[i,good])]) if good.size else None
        nonfinite=np.flatnonzero(~finite[i])
        bad=np.flatnonzero((finite[i] & (x[i]<negative_tolerance)) | ~finite[i])
        per_species.append({"pool":pool,"minimum_mM":float(x[i,j]) if j is not None else None,
            "minimum_day":float(t[j]) if j is not None else None,"minimum_index":j,
            "negative_count":int((finite[i] & (x[i]<0)).sum()),
            "below_policy_count":int((finite[i] & (x[i]<negative_tolerance)).sum()),
            "nonfinite_count":int(nonfinite.size),
            "first_policy_violation_day":float(t[bad[0]]) if bad.size else None,
            "first_nonfinite_day":float(t[nonfinite[0]]) if nonfinite.size else None})
    available=[p for p in per_species if p["minimum_mM"] is not None]
    worst=min(available,key=lambda p:p["minimum_mM"]) if available else None
    events=[(p["first_policy_violation_day"],p["pool"]) for p in per_species if p["first_policy_violation_day"] is not None]
    first=min(events) if events else None
    return {"pass":bool(finite.all() and all(p["below_policy_count"]==0 for p in per_species)),
            "point_count":len(t),"per_species":per_species,"worst_finite":worst,
            "first_sampled_policy_violation":{"day":first[0],"pool":first[1]} if first else None,
            "nonfinite_count":int((~finite).sum())}


class RHSProbe:
    def __init__(self,rhs,names):
        self.rhs,self.names=rhs,names
        self.calls=0
        self.minimum=None
        self.worst_state=None
        self.last_state=None
        self.last_day=None
        self.error=None

    def __call__(self,t,x):
        self.calls+=1
        self.last_state=np.asarray(x,float).copy()
        self.last_day=float(t)
        physical=np.asarray(x)[:len(self.names)]
        if np.isfinite(physical).any():
            i=int(np.argmin(np.where(np.isfinite(physical),physical,np.inf)))
            value=float(physical[i])
            if self.minimum is None or value<self.minimum["value_mM"]:
                self.minimum={"day":float(t),"pool":self.names[i],"value_mM":value}
                self.worst_state=np.asarray(x,float).copy()
        try:
            return self.rhs(t,x)
        except (ValueError,RuntimeError,FloatingPointError,OverflowError) as error:
            self.error={"day":float(t),"type":type(error).__name__,"message":str(error)}
            raise


def record_integration(rhs,initial,end,days,profile,negative_tolerance):
    initial=np.asarray(initial,float)
    if initial.shape!=(114,) or initial[-1]!=7.2 or not np.isfinite(initial).all():
        raise ValueError("finite frozen clamped-pH RBC state required")
    probe=RHSProbe(rhs,list(rhs.names))
    arrays={"pool_names":np.array(rhs.names),"initial":initial.copy()}
    report={"concentration_gate_pass":False,"negative_tolerance_mM":negative_tolerance,
            "supports":{},"method":"BDF","rtol":float(profile["rtol"]),"atol_mM":float(profile["atol"]),
            "max_step_days":float(profile["max_step"]) if "max_step" in profile else None,
            "internal_RHS_is_not_accepted_state_evidence":True}
    sol=None
    try:
        sol=solve_ivp(probe,(1.,float(end)),initial.copy(),method="BDF",dense_output=True,
                      jac_sparsity=rhs.jacobian_sparsity,**profile)
        arrays.update(accepted_time=sol.t,accepted_states=sol.y)
        report["solver"]={"success":bool(sol.success),"status":int(sol.status),"message":sol.message,
            "end_day":float(sol.t[-1]),"nfev":int(sol.nfev),"njev":int(sol.njev),"nlu":int(sol.nlu),
            "accepted_steps":int(len(sol.t)-1)}
        time=np.unique(np.r_[np.linspace(1.,end,301),np.arange(1.,end+1.),days])
        time=time[time<=sol.t[-1]]
        arrays.update(time=time,states=sol.sol(time))
        supports={"accepted":(sol.t,sol.y),"dense":(time,arrays["states"])}
        complete=bool(sol.success and sol.t[-1]==end and np.array_equal(sol.y[:,0],initial))
        report["complete_exact_J1"]=complete
        if complete:
            arrays["boundaries"]=np.arange(1.,end+1.)
            for order in (4,8):
                grid=accepted_step_quadrature(sol.t,arrays["boundaries"],order=order)
                x=sol.sol(grid.nodes)
                arrays.update({f"q{order}_time":grid.nodes,f"q{order}_states":x,
                               f"q{order}_weights":grid.weights,f"q{order}_intervals":grid.interval_indices})
                supports[f"quadrature{order}"]=(grid.nodes,x)
        for key,(t,x) in supports.items():
            report["supports"][key]=inspect_support(t,x[:len(rhs.names)],list(rhs.names),negative_tolerance)
        ph_fixed=all(np.array_equal(x[-1],np.full(x.shape[1],initial[-1])) for t,x in supports.values())
        report["clamped_pH_unchanged"]=bool(ph_fixed)
        report["concentration_gate_pass"]=bool(complete and ph_fixed and all(s["pass"] for s in report["supports"].values()))
    except (ValueError,RuntimeError,FloatingPointError,OverflowError) as error:
        report["exception"]={"type":type(error).__name__,"message":str(error)}
    report["internal_RHS"]={"calls":probe.calls,"worst_finite_proposal":probe.minimum,"exception":probe.error,
                             "last_day":probe.last_day}
    if probe.worst_state is not None:
        arrays["internal_worst_state"]=probe.worst_state
    if probe.last_state is not None:
        arrays["internal_last_state"]=probe.last_state
    return sol,arrays,report


def require_concentration_contract(report):
    if not report["concentration_gate_pass"]:
        raise ConcentrationRejected(report)


def forensic_rates(rhs,arrays,report):
    witnesses={}
    for support,summary in report["supports"].items():
        worst=summary["worst_finite"]
        if worst is None:
            continue
        field={"accepted":"accepted_states","dense":"states","quadrature4":"q4_states","quadrature8":"q8_states"}[support]
        state=arrays[field][:,worst["minimum_index"]]
        if not np.isfinite(state).all():
            witnesses[support]={"available":False,"reason":"nonfinite witness state"}
            continue
        try:
            raw,executed,_=rhs.rates(worst["minimum_day"],state)
            i=rhs.names.index(worst["pool"])
            contribution=rhs.matrix[i]*executed
            active=np.flatnonzero(np.abs(contribution)>0)
            order=active[np.argsort(-np.abs(contribution[active]))][:10]
            witnesses[support]={"available":True,"pool":worst["pool"],"day":worst["minimum_day"],
                "concentration_mM":worst["minimum_mM"],"raw_derivative":float(rhs.matrix[i]@raw),
                "executed_derivative":float(contribution.sum()),
                "executed_consumption":float(-np.minimum(contribution,0).sum()),
                "largest_signed_contributions":{rhs.reactions[j]:float(contribution[j]) for j in order}}
        except (ValueError,RuntimeError,FloatingPointError,OverflowError) as error:
            witnesses[support]={"available":False,"reason":str(error)}
    return witnesses


def audit_recorded_solution(rhs,arrays,report,numeric,native_rates):
    require_concentration_contract(report)
    result={k:arrays[k] for k in ("time","states","accepted_time","accepted_states","boundaries","pool_names")}
    result.update(matrix=rhs.matrix,reactions=np.array(rhs.reactions))
    for order in (4,8):
        time,states=arrays[f"q{order}_time"],arrays[f"q{order}_states"]
        rates=[rhs.rates(t,x)[:2] for t,x in zip(time,states.T)]
        raw,executed=(np.asarray([r[i] for r in rates]).T for i in range(2))
        grid=accepted_step_quadrature(arrays["accepted_time"],arrays["boundaries"],order=order)
        for kind,values in (("raw",raw),("executed",executed)):
            result[f"{kind}{order}"]=integrate_intervals(values,grid)
            result[f"q{order}_{kind}_rates"]=values
        result.update({f"q{order}_weights":grid.weights,f"q{order}_intervals":grid.interval_indices})
        if order==8:
            chosen=np.linspace(0,len(time)-1,9).astype(int)
            for j in chosen:
                r0,r1=native_rates(time[j],states[:,j])
                if not np.allclose(r0,raw[:,j],rtol=1e-12,atol=1e-12) or not np.allclose(r1,executed[:,j],rtol=1e-12,atol=1e-12):
                    raise ValueError("original/fast rate projection mismatch")
            result.update(live_time=time[chosen],live_states=states[:,chosen],live_raw=raw[:,chosen],live_executed=executed[:,chosen])
    indices=np.searchsorted(arrays["time"],arrays["boundaries"])
    delta=np.diff(arrays["states"][:113,indices],axis=1)
    balance=within(delta,rhs.matrix@result["executed8"],numeric,"quadrature")
    checks={"daily_balance":balance,**{k+"_quadrature":within(result[k+"4"],result[k+"8"],numeric,"quadrature") for k in ("raw","executed")}}
    stats={"numerical_pass":bool(all(c.all() for c in checks.values())),
           "checks":{k:{"passed":int(v.sum()),"total":int(v.size)} for k,v in checks.items()},
           "max_daily_balance_residual_mM":float(np.max(np.abs(delta-rhs.matrix@result["executed8"]))) }
    return result,stats
