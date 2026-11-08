"""Post-hoc availability accounting on sealed original-rate trajectories only."""

import argparse
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

from run_pgk_ndpk_profile import (ROOT,check_seal,parameters_for,read,require,rhs_for,seal,sha,verify_archive,verify_inputs,write,write_csv)
from reaction_positivity import limit_signed_fluxes


def rate_explanation(x,raw,executed,matrix,names,reactions,threshold):
    expected,factors=limit_signed_fluxes(np.asarray(x)[:len(names)],raw,matrix,threshold=threshold)
    require(np.allclose(expected,executed,rtol=1e-12,atol=1e-12),"executed rates are not explained by the declared limiter")
    result=[]
    availability=np.clip(np.asarray(x)[:len(names)]/threshold,0,1)
    for reaction in ("VPGK","VPK","VNDPK"):
        j=reactions.index(reaction)
        consuming=(matrix[:,j]<0) if raw[j]>0 else (matrix[:,j]>0) if raw[j]<0 else np.zeros(len(names),bool)
        limited=[names[i] for i in np.flatnonzero(consuming & (availability<1) & np.isclose(availability,factors[j],rtol=1e-10,atol=1e-15))]
        result.append({"reaction":reaction,"raw_rate":float(raw[j]),"executed_rate":float(executed[j]),
                       "availability_factor":float(factors[j]),"limiting_pools":limited,
                       "limiting_concentrations_mM":{p:float(x[names.index(p)]) for p in limited}})
    return result


def audit(out,report):
    require(not report.exists() and not report.is_relative_to(out),"fresh external post-hoc audit required")
    verify_archive(out)
    f=verify_inputs(out)
    summary=read(out/"audit_summary.json")
    points,integrals=[],[]
    center_id=read(out/"screen/result.json")["center_id"]
    cases={r["id"]:r for r in read(out/"cases.json")}
    scaling=[]
    for case_id,location in summary["locations"].items():
        profile="ultrastrict"
        if not summary["results"][case_id]["profiles"][profile]["completed"]:
            continue
        folder=Path(location["folder"])/profile
        check_seal(folder)
        parameters=parameters_for(f,cases[case_id]["log_factors"])
        rhs=rhs_for(f,parameters,f["temporal"]["network"],"full")
        with np.load(folder/"replay.npz") as a:
            times=[1,4,8,11,15]
            ids=np.searchsorted(a["time"],times)
            require(np.array_equal(a["time"][ids],times),"exact sampled states required")
            names,reactions=a["pool_names"].tolist(),a["reactions"].tolist()
            for j,day in zip(ids,times):
                x=a["states"][:,j]
                raw,executed,_=rhs.rates(day,x)
                for r in rate_explanation(x,raw,executed,a["matrix"],names,reactions,f["numeric"]["availability_threshold_mM"]):
                    points.append([case_id,day,r["reaction"],r["raw_rate"],r["executed_rate"],r["availability_factor"],
                        ";".join(r["limiting_pools"]),";".join(f"{k}={v:.17g}" for k,v in r["limiting_concentrations_mM"].items())])
                if case_id==center_id and day==15:
                    k=reactions.index("VNDPK")
                    for factor in (.5,1.,2.):
                        probe=dict(parameters)
                        for key in ("vmax_VNDPK","vmax_VNDPK_rev"):
                            probe[key]*=factor
                        prhs=rhs_for(f,probe,f["temporal"]["network"],"full")
                        v0,v1,_=prhs.rates(day,x)
                        require(np.isclose(v0[k],factor*raw[k],rtol=1e-12,atol=1e-12) and np.isclose(v1[k],factor*executed[k],rtol=1e-12,atol=1e-12),"common NDPK scaling changed the fixed-state direction")
                        scaling.append({"common_factor":factor,"raw_VNDPK":float(v0[k]),"executed_VNDPK":float(v1[k])})
            for label,lo,hi in (("J1_J4",0,3),("J4_J8",3,7),("J8_J15",7,14)):
                use=(a["q8_intervals"]>=lo)&(a["q8_intervals"]<hi)
                w=a["q8_weights"][use]
                for reaction in ("VPGK","VPK","VNDPK"):
                    k=reactions.index(reaction)
                    raw=a["q8_raw_rates"][k,use]
                    executed=a["q8_executed_rates"][k,use]
                    require(np.all(np.abs(executed)<=np.abs(raw)+1e-12),"limiter amplified a reaction")
                    a0=float(np.abs(raw)@w)
                    a1=float(np.abs(executed)@w)
                    limited=(np.abs(raw)>1e-14)&(np.abs(executed)<(1-1e-12)*np.abs(raw))
                    integrals.append([case_id,label,reaction,float(raw@w),float(executed@w),a0,a1,a1/a0 if a0>0 else None,float(w[limited].sum()/w.sum())])
    report.mkdir(parents=True)
    write_csv(report/"sampled_availability.csv",["case","day","reaction","same_state_raw_rate","executed_rate","availability_factor","limiting_pools","limiting_concentrations_mM"],points)
    write_csv(report/"integrated_availability.csv",["case","period","reaction","same_state_raw_net_integral_mM","executed_net_integral_mM","raw_abs_integral_mM","executed_abs_integral_mM","executed_fraction_of_raw_abs","time_fraction_limited"],integrals)
    result={"verified":True,"posthoc":True,"new_ODE_simulations":0,"new_fixed_state_NDPK_rate_probes":len(scaling),
            "fixed_state_common_scaling":scaling,"availability_threshold_mM":f["numeric"]["availability_threshold_mM"],
            "locked_initial_GDP_GTP_mM":{p:f["initial"][rhs.names.index(p)] for p in ("GDP","GTP")},
            "GDP_GTP_are_latent":True,"same_state_raw_integrals_are_not_unlimited_ODE_predictions":True,
            "threshold_changed":False,"parameters_promoted":False,
            "source_sha256":{Path(__file__).relative_to(ROOT).as_posix():sha(Path(__file__)),
                              (out/"manifest.json").relative_to(ROOT).as_posix():sha(out/"manifest.json")}}
    write(report/"verification.json",result)
    seal(report)
    check_seal(report)
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    args=p.parse_args()
    with threadpool_limits(1):
        print(audit(args.out.resolve(),args.report.resolve()))
