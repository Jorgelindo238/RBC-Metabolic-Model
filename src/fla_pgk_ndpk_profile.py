"""Fixed two-factor profiles and executed adenylate/guanylate accounting."""

import numpy as np

POOLS = ("ATP", "ADP", "AMP", "GDP", "GTP", "GMP")
PERIODS = (("J1_J4", 0, 3), ("J4_J8", 3, 7), ("J8_J15", 7, 14))


def profile_cases(f):
    plan, d = f["pgk_ndpk"], f["design"]
    groups = list(d["groups"])
    center = np.asarray(f["profile_center"], float)
    if center.shape != (len(groups),) or not np.isfinite(center).all():
        raise ValueError("finite frozen center required")
    a,b = groups.index("PGK"),groups.index("NDPK")
    cases = [{"id":"fixed_reference", "log_factors":[0.]*len(groups), "control":True, "inside_previous_box":True}]
    for i,p in enumerate(plan["PGK_factors"]):
        for j,n in enumerate(plan["NDPK_factors"]):
            if not np.isfinite([p,n]).all() or min(p,n)<=0:
                raise ValueError("positive finite profile factors required")
            x = center.copy()
            x[[a,b]] = np.log([p,n])
            inside = d["factor_bounds"]["PGK"][0]<=p<=d["factor_bounds"]["PGK"][1] and d["factor_bounds"]["NDPK"][0]<=n<=d["factor_bounds"]["NDPK"][1]
            cases.append({"id":f"p{i}_n{j}", "log_factors":x.tolist(), "control":False,
                          "PGK_factor":p,"NDPK_factor":n,"inside_previous_box":bool(inside)})
    if len({tuple(c["log_factors"]) for c in cases})!=len(cases):
        raise ValueError("duplicate registered profile vectors")
    if len(cases)>plan["maximum_screen_attempts"]:
        raise ValueError("profile budget exceeded")
    return cases


def audit_roles(rows, f):
    grid = [r for r in rows if not r["control"]]
    valid = [r for r in grid if r["valid"]]
    if not valid:
        raise ValueError("no valid profile point")
    groups = list(f["design"]["groups"])
    p0,n0 = np.exp(np.array(f["profile_center"])[[groups.index("PGK"),groups.index("NDPK")]])
    guarded = [r for r in valid if r["inside_previous_box"] and r["reserved_guards_pass"]]
    best = min(guarded,key=lambda r:r["absolute"]["objective"]) if guarded else None
    p = next(r for r in grid if r["PGK_factor"]==f["pgk_ndpk"]["PGK_lower_probe"] and np.isclose(r["NDPK_factor"],n0))
    n = next(r for r in grid if np.isclose(r["PGK_factor"],p0) and r["NDPK_factor"]==f["pgk_ndpk"]["NDPK_upper_probe"])
    return {"best_guarded_in_box":best["id"] if best else None,
            "PGK_lower_alone":p["id"],"NDPK_upper_alone":n["id"],
            "best_absolute_any_valid":min(valid,key=lambda r:r["absolute"]["objective"])["id"]}


def ndpk_column(matrix, names, reactions):
    column = np.asarray(matrix)[[names.index(p) for p in POOLS],reactions.index("VNDPK")]
    if not np.array_equal(column,[-1,1,0,-1,1,0]):
        raise ValueError("NDPK nucleotide-transfer column changed")
    return dict(zip(POOLS,column.tolist()))


def executed_ledger(arrays):
    names,reactions = arrays["pool_names"].tolist(),arrays["reactions"].tolist()
    matrix = arrays["matrix"]
    column = ndpk_column(matrix,names,reactions)
    time,states,bounds = arrays["time"],arrays["states"],arrays["boundaries"]
    ids = np.searchsorted(time,bounds)
    if not np.array_equal(time[ids],bounds) or not np.array_equal(bounds,np.arange(1,16)):
        raise ValueError("exact daily J1-J15 support required")
    weights,cells,rates = arrays["q8_weights"],arrays["q8_intervals"],arrays["q8_executed_rates"]
    ia,jn = names.index("ATP"),reactions.index("VNDPK")
    by_pool = matrix[[names.index(p) for p in POOLS]]
    result = {"NDPK_column":column,"periods":{}}
    for label,lo,hi in PERIODS:
        integral = arrays["executed8"][:,lo:hi].sum(axis=1)
        contribution = by_pool*integral[None,:]
        observed = states[[names.index(p) for p in POOLS],ids[hi]]-states[[names.index(p) for p in POOLS],ids[lo]]
        use = (cells>=lo)&(cells<hi)
        atp = matrix[ia,:,None]*rates[:,use]
        period = {"pools":{}, "ATP_production_mM":float(np.maximum(atp,0).sum(axis=0)@weights[use]),
                  "ATP_consumption_mM":float(-np.minimum(atp,0).sum(axis=0)@weights[use]),
                  "NDPK_net_positive_direction_mM":float(np.maximum(rates[jn,use],0)@weights[use]),
                  "NDPK_net_negative_direction_mM":float(np.maximum(-rates[jn,use],0)@weights[use])}
        for i,p in enumerate(POOLS):
            period["pools"][p] = {"delta_state_mM":float(observed[i]),"executed_delta_mM":float(contribution[i].sum()),
                                  "balance_residual_mM":float(observed[i]-contribution[i].sum()),
                                  "signed_reactions_mM":dict(zip(reactions,contribution[i].tolist()))}
        result["periods"][label] = period
    return result
