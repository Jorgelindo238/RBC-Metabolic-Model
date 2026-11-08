"""Separate solver convergence, availability sensitivity and biological fit."""

import numpy as np


def threshold_context(frozen, threshold):
    if not np.isfinite(threshold) or threshold <= 0:
        raise ValueError("positive finite availability threshold required")
    return {**frozen,"numeric":{**frozen["numeric"],"availability_threshold_mM":float(threshold)}}


def element_comparison(a,b,atol,rtol):
    a,b=np.asarray(a,float),np.asarray(b,float)
    if a.shape!=b.shape or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("aligned finite comparison arrays required")
    if not np.isfinite([atol,rtol]).all() or atol<=0 or rtol<0:
        raise ValueError("positive absolute and nonnegative relative comparison tolerance required")
    delta=np.abs(a-b)
    limit=atol+rtol*np.maximum(np.abs(a),np.abs(b))
    ok=delta<=limit
    return {"pass":bool(ok.all()),"passed":int(ok.sum()),"total":int(ok.size),
            "max_difference":float(delta.max(initial=0)),"max_tolerance_ratio":float((delta/limit).max(initial=0))}


def compare_replays(a,b,numeric,plan,days):
    if not np.array_equal(a["time"],b["time"]) or not np.array_equal(a["pool_names"],b["pool_names"]):
        raise ValueError("identical replay support and species order required")
    inherited={k:element_comparison(a[k],b[k],numeric["comparison_atol_mM"],numeric["comparison_rtol"])
               for k in ("states","raw8","executed8")}
    names=a["pool_names"].tolist()
    indices=np.searchsorted(a["time"],days)
    if not np.array_equal(a["time"][indices],days):
        raise ValueError("actual registered sample dates required")
    selection=np.ix_([names.index(p) for p in plan["focus_pools"]],indices)
    focus=element_comparison(a["states"][selection],b["states"][selection],plan["focus_atol_mM"],plan["focus_rtol"])
    executed=element_comparison(a["executed8"],b["executed8"],plan["executed_integral_atol_mM"],plan["executed_integral_rtol"])
    return {"pass":bool(all(v["pass"] for v in inherited.values()) and focus["pass"] and executed["pass"]),
            "inherited":inherited,"focused_nucleotides":focus,"focused_executed_integrals":executed}


def plateau_decision(levels,solver_checks,adjacent,required):
    if len(levels)<required+1 or required<1:
        raise ValueError("enough ordered levels and positive pair count required")
    tail=levels[-required-1:]
    valid=all(solver_checks[level]["numerical_pass"] and solver_checks[level]["comparison"]["pass"] for level in tail)
    pairs=[(levels[i],levels[i+1]) for i in range(len(levels)-required-1,len(levels)-1)]
    passed=all(all(adjacent[a+"__"+b][profile]["pass"] for profile in ("strict","ultrastrict")) for a,b in pairs)
    return {"registered_plateau":bool(valid and passed),"required_final_pairs":required,
            "final_levels":tail,"solver_valid_on_tail":bool(valid),"adjacent_comparisons_pass":bool(passed),
            "threshold_selected_by_fit":False,"threshold_promoted":False}
