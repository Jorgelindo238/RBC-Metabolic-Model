"""Independent receipt for the corrected-engine Vmax-only absolute search.

Recomputes scores, guards, finite-difference Jacobians, LP proposals, the
acceptance sequence, the selection and the registered classification from the
archived evidence. It does not import the runner's decision module.
"""

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.optimize import linprog
from threadpoolctl import threadpool_limits

from run_vmax_requalification import (ROOT,check_seal,exact_parameters,folder_for,historical_metrics,read,require,
    seal,sha,verify_archive,verify_inputs,within_original_box,write,write_csv)
from fla_reaction_threshold import compare_replays
from verify_recorded_integrations import check_saved_supports
from verify_absolute_vmax import reconstruct
from verify_vmax_requalification import verify_replay

TOL=dict(rtol=1e-12,atol=1e-12)


def rescore(x,reference,panel,f):
    """Guards, half-reserve admission, absolute sides and worst dated ratio from raw states."""
    names,days=list(panel["names"]),list(panel["days"])
    base=np.array(reference["prediction_mM"])
    guards,sides=reconstruct(np.asarray(x,float),base,panel["target"],panel["bands"],names,days,f["design"],f["temporal"])
    g0,_=reconstruct(base,base,panel["target"],panel["bands"],names,days,f["design"],f["temporal"])
    reserve=np.array([0 if k.startswith("date_gain:") else -v*f["temporal"]["reserve_fraction"] for k,v in g0.items()])
    aden=[names.index(p) for p in ("ATP","ADP","AMP")]
    ratio=np.mean(np.log(np.asarray(x)[aden]/panel["target"][aden])**2,axis=0)/np.mean(np.log(base[aden]/panel["target"][aden])**2,axis=0)
    return {"guards":guards,"sides":sides,"gap":max(sides.values()),"reserve":reserve,"worst_ratio":float(ratio.max()),
            "admitted":bool(np.all(np.array(list(guards.values()))<=-.5*reserve))}


def verify_attempt(out,f,row,panel,reference,counts,minima):
    plan=f["corrected_search_plan"]
    profile=plan["search_profile"]
    folder=out/"search"/f"attempt_{row['attempt']:03d}"
    check_seal(folder)
    parameters=exact_parameters(f,row["log_factors"])
    require({k for k in parameters if parameters[k]!=f["parameters"][k]}<=set(f["resolved_capacities"]),"non-Vmax parameter changed")
    require(within_original_box(f,row["log_factors"]) and row["inside_original_box"],"out-of-box search point")
    d=read(folder/"diagnostics.json")
    settings=plan["profiles"][profile]
    require(d["method"]==plan["method"] and d["scipy_version"]==plan["scipy_version"] and d["rtol"]==settings["rtol"]
            and d["atol_mM"]==settings["atol"] and d["max_step_days"]==settings["max_step"],"uncertified search recipe")
    require(d["negative_tolerance_mM"]==f["numeric"]["negative_tolerance_mM"],"negative tolerance relaxed")
    jac=d["bounded_jacobian"]
    require(jac["minimum_step_mM"]==plan["jacobian_minimum_step_mM"][profile] and jac["largest_requested_step_mM"]<=jac["maximum_step_mM"]
            and not jac["states_clipped"],"finite-difference recipe changed")
    gate=bool(d["complete_exact_J1"] and d["clamped_pH_unchanged"] and len(d["supports"])==4 and all(s["pass"] for s in d["supports"].values()))
    require(gate==d["concentration_gate_pass"],"concentration gate changed")
    for support,s in d["supports"].items():
        worst=s["worst_finite"]
        minima.append([row["attempt"],row["stage"],support,worst["pool"] if worst else None,worst["minimum_mM"] if worst else None,
                       worst["minimum_day"] if worst else None,sum(p["below_policy_count"] for p in s["per_species"]),s["nonfinite_count"]])
    counts["search_records"]+=1
    if not gate:
        require(not row["valid"] and not (folder/"fit_states.npz").exists(),"rejected states admitted to the search")
        with np.load(folder/"trajectory_evidence.npz") as a:
            require(np.array_equal(a["initial"],f["initial"]),"J1 changed")
            _,saved=check_saved_supports(a,d,a["pool_names"].tolist(),f["numeric"]["negative_tolerance_mM"])
            require(not saved,"quarantined trajectory does not reproduce its rejection")
        counts["quarantined"]+=1
        return None
    with np.load(folder/"fit_states.npz") as a:
        require(np.array_equal(a["initial"],f["initial"]) and a["time"].tolist()==plan["fit_days"],"J1 or fit dates changed")
        x=a["states"][[a["pool_names"].tolist().index(p) for p in panel["names"]]]
    if not row["valid"]:
        require(row["error"].startswith("observation domain") and np.any(x[panel["adenylates"]]<=0),"unexplained invalid row")
        return None
    require(np.array_equal(x,np.array(row["prediction_mM"])),"recorded prediction differs from saved states")
    s=rescore(x,reference,panel,f)
    require(list(s["guards"])==list(row["feasibility_guards"]) and np.allclose(list(s["guards"].values()),list(row["feasibility_guards"].values()),**TOL),
            "guard values changed")
    require(list(s["sides"])==list(row["absolute"]["sides"]) and np.allclose(list(s["sides"].values()),list(row["absolute"]["sides"].values()),**TOL),
            "absolute sides changed")
    require(abs(s["gap"]-row["absolute"]["objective"])<1e-12 and row["absolute"]["target_pass"]==(s["gap"]<=0),"absolute gap changed")
    require(s["admitted"]==row["reserved_guards_pass"] and abs(s["worst_ratio"]-row["objective"])<1e-10,"reserve admission or dated ratio changed")
    counts["guard_values"]+=len(s["guards"])
    return s


def verify_rounds(out,f,rows,scores,result,counts):
    plan,d=f["corrected_search_plan"],f["design"]
    lo,hi=np.log([d["factor_bounds"][k] for k in d["groups"]]).T
    by={r["attempt"]:r for r in rows}
    ok=lambda r:scores.get(r["attempt"]) is not None and scores[r["attempt"]]["admitted"]
    current,radius=by[2],plan["initial_radius_log"]
    reserve=scores[2]["reserve"]
    for index,step in enumerate(result["steps"]):
        sens=read(out/"fit"/f"sensitivity_round{index+1}.json")
        require(step["round"]==index+1==sens["round"] and sens["anchor"]==current["attempt"],"round order or anchor changed")
        x=np.array(current["log_factors"])
        h=np.where(x+plan["difference_step_log"]<=hi,plan["difference_step_log"],-plan["difference_step_log"])
        diffs=[by[a] for a in sens["difference_attempts"]]
        require(len(diffs)==len(x) and all(np.array_equal(np.array(r["log_factors"]),np.clip(x+np.eye(len(x))[i]*h[i],lo,hi)) for i,r in enumerate(diffs)),
                "sensitivity points are not the registered differences")
        s0=scores[current["attempt"]]
        r0,g0=np.array(list(s0["sides"].values())),np.array(list(s0["guards"].values()))
        jr,jg,good=np.zeros((len(r0),len(x))),np.zeros((len(g0),len(x))),[]
        for i,r in enumerate(diffs):
            s=scores.get(r["attempt"])
            if s is None or r["log_factors"][i]==x[i]:continue
            dx=r["log_factors"][i]-x[i]
            jr[:,i]=(np.array(list(s["sides"].values()))-r0)/dx
            jg[:,i]=(np.array(list(s["guards"].values()))-g0)/dx
            good.append(i)
        require(good==sens["valid_coordinates"] and np.allclose(jr,sens["side_jacobian"],rtol=1e-9,atol=1e-9)
                and np.allclose(jg,sens["guard_jacobian"],rtol=1e-9,atol=1e-9),"finite-difference Jacobian changed")
        counts["jacobian_entries"]+=jr.size+jg.size
        if not good:
            require(step.get("status")=="no_valid_direction" and index==len(result["steps"])-1,"empty direction not terminal")
            break
        require(step["radius"]==radius and step["anchor"]==current["attempt"] and step["valid_derivatives"]==len(good),"round bookkeeping changed")
        a,b=lo.copy(),hi.copy()
        missing=sorted(set(range(len(x)))-set(good))
        a[missing]=b[missing]=x[missing]
        A=np.vstack((np.column_stack((jr,-np.ones(len(r0)))),np.column_stack((jg,np.zeros(len(g0))))))
        rhs=np.r_[-r0,-g0-reserve]
        box=list(zip(np.maximum(a-x,-radius),np.minimum(b-x,radius)))
        solution=linprog(np.r_[np.zeros(len(x)),1.],A_ub=A,b_ub=rhs,bounds=box+[(None,None)],method="highs")
        proposal=step["linearized_proposal"]
        require((proposal is None)==(not solution.success),"LP feasibility changed")
        accepted=None
        if proposal is not None:
            delta=np.array(proposal["delta"])
            require(abs(solution.x[-1]-proposal["predicted_objective"])<1e-7,"LP optimum changed")
            require(np.max(A@np.r_[delta,proposal["predicted_objective"]]-rhs)<=1e-7
                    and all(l-1e-9<=v<=u+1e-9 for v,(l,u) in zip(delta,box)),"recorded LP witness violates its constraints")
            counts["LP_witnesses"]+=1
            if proposal["predicted_objective"]<s0["gap"]:
                tried=[by[t] for t in step["candidate_attempts"]]
                expected=[np.clip(x+alpha*delta,lo,hi) for alpha in plan["line_search_fractions"]]
                require(len(tried)==len(expected) and all(np.array_equal(np.array(r["log_factors"]),e) for r,e in zip(tried,expected)),
                        "backtracking points changed")
                passed=[r for r in tried if ok(r) and scores[r["attempt"]]["gap"]<=s0["gap"]-plan["minimum_step_objective_gain"]]
                if passed:
                    accepted=min(passed,key=lambda r:(scores[r["attempt"]]["gap"],r["attempt"]))["attempt"]
            else:
                require("candidate_attempts" not in step,"backtracking without predicted improvement")
        require(step["accepted"]==accepted,"acceptance decision changed")
        if accepted:current=by[accepted]
        radius=min(plan["maximum_radius_log"],radius*1.25) if accepted else radius*.5
    admitted=[r for r in rows if ok(r)]
    return min(admitted,key=lambda r:(scores[r["attempt"]]["gap"],r["attempt"]))


def decide(numerical,paired,scores,inside,plan,is_center):
    gap=ratio=None
    if is_center:
        category="no_improvement"
    elif not all(numerical.values()) or len(numerical)!=2 or not paired:
        category="numerical_failure"
    elif any(s is None for s in scores.values()) or not inside or not all(s["admitted"] for s in scores.values()):
        category="metabolic_guard_failure"
    else:
        gap,ratio=max(s["gap"] for s in scores.values()),max(s["worst_ratio"] for s in scores.values())
        category=("absolute_target_attained" if gap<=0 else "improved_center"
                  if gap<plan["center_worst_profile_absolute_gap"] and ratio<=plan["center_worst_dated_ratio"] else "no_improvement")
    final=gap if category in ("absolute_target_attained","improved_center") else plan["center_worst_profile_absolute_gap"]
    return category,gap,ratio,bool(final>plan["futility_gap_threshold"])


def verify(out,report):
    require(not report.exists() and not report.is_relative_to(out),"fresh external receipt required")
    verify_archive(out)
    f=verify_inputs(out)
    plan=f["corrected_search_plan"]
    require(plan==read(ROOT/"config/fla_vmax_corrected_search_2026_11_10.json"),"registered plan changed")
    require(not any(plan[k] for k in ("bounds_expanded","Km_changed","fit_based_retries","production_promotion_allowed","J46_replayed")),"scope opened")
    obs=read(out/"observations.json");f["observations_for_verification"]=obs
    panel,historical=historical_metrics(f,obs)
    check_seal(out/"fit")
    result=read(out/"fit/result.json")
    rows=[json.loads(s) for s in (out/"fit/trace.jsonl").read_text().splitlines()]
    require([r["attempt"] for r in rows]==list(range(1,len(rows)+1)) and len(rows)==result["actual_attempts"]<=plan["maximum_search_attempts"],
            "attempt ledger or budget changed")
    require(len({tuple(r["log_factors"]) for r in rows})==len(rows),"a vector was integrated twice")
    require(len(list((out/"search").iterdir()))==len(rows),"unrecorded search integration")
    require(rows[0]["log_factors"]==[0.]*len(f["profile_center"]) and rows[1]["log_factors"]==f["profile_center"],"controls are not the registered vectors")
    counts={"search_records":0,"quarantined":0,"guard_values":0,"jacobian_entries":0,"LP_witnesses":0,"records":0,
            "daily_balances_passed":0,"daily_balances_total":0,"quadrature_values":0,"native_rate_checkpoints":0}
    minima,audit_minima,observed,budgets=[],[],[],[]
    reference=historical[plan["search_profile"]]
    scores={r["attempt"]:verify_attempt(out,f,r,panel,reference,counts,minima) for r in rows}
    gate=read(out/"control_gate.json")
    parent=ROOT/plan["numerical_parent"]
    agree=True
    for key,row in zip(("fixed_reference","working_center"),rows):
        folder=parent/"controls"/key/"joint"/plan["search_profile"]
        check_seal(folder)
        if not row["valid"]:
            agree=False;continue
        with np.load(folder/"flux_evidence.npz") as a:
            old=a["states"][np.ix_([a["pool_names"].tolist().index(p) for p in panel["names"]],np.searchsorted(a["time"],panel["days"]))]
        new=np.array(row["prediction_mM"])
        within=np.abs(new-old)<=f["numeric"]["comparison_atol_mM"]+f["numeric"]["comparison_rtol"]*np.maximum(np.abs(new),np.abs(old))
        require(bool(within.all())==gate["comparisons"][key]["pass"],"control comparison changed")
        agree&=bool(within.all())
    center_ok=scores[2] is not None and scores[2]["admitted"]
    require(gate["pass"]==bool(agree and center_ok)==result["control_gate_pass"],"control gate changed")
    table,classification=[],None
    if gate["pass"]:
        selected=verify_rounds(out,f,rows,scores,result,counts)
        require(selected["attempt"]==result["selected"]["attempt"] and result["selected_is_working_center"]==(selected["attempt"]==2),"selection changed")
        summary=read(out/"summary.json")
        require(summary["selected_attempt"]==selected["attempt"],"audited point is not the selected point")
        is_center=selected["attempt"]==2
        numerical,audited,paired={}, {}, False
        if is_center:
            require(not (out/"candidates").exists() and summary["new_audit_integrations"]==0,"unregistered audit integration")
        else:
            case=read(out/"cases.json")["candidates"][0]
            require(case["log_factors"]==selected["log_factors"] and case["parameters"]==exact_parameters(f,case["log_factors"]),"audited vector changed")
            data={}
            for p in plan["audit_profiles"]:
                r,a=verify_replay(folder_for(out,case,plan["search_backend"],p),f,case,plan["search_backend"],p,counts,audit_minima,observed,budgets)
                require(r==summary["statuses"][p],"audit status changed")
                numerical[p]=r["numerical_pass"]
                audited[p]=None
                if a is not None:
                    data[p]=a
                    x=a["states"][np.ix_([a["pool_names"].tolist().index(k) for k in panel["names"]],np.searchsorted(a["time"],panel["days"]))]
                    if np.all(x[panel["adenylates"]]>0):
                        audited[p]=rescore(x,historical[p],panel,f)
                        recorded=summary["scores"][p]
                        require(recorded is not None and abs(recorded["absolute"]["objective"]-audited[p]["gap"])<1e-12
                                and recorded["reserved_guards_pass"]==audited[p]["admitted"],"audit score changed")
                        counts["guard_values"]+=len(audited[p]["guards"])
                    else:
                        require(summary["scores"][p] is None,"score emitted outside the observation domain")
            paired=len(data)==2 and compare_replays(data["strict"],data["ultrastrict"],f["numeric"],f["threshold_plan"],panel["days"])["pass"]
            require(bool(paired)==bool(summary["paired"]["pass"]),"paired profile decision changed")
            require(summary["new_audit_integrations"]==len(numerical)<=plan["maximum_audit_integrations"],"audit budget changed")
        category,gap,ratio,exhausted=decide(numerical,paired,audited,within_original_box(f,selected["log_factors"]),plan,is_center)
        c=summary["classification"]
        require(c["category"]==category and c["original_box_local_search_exhausted"]==exhausted
                and c["working_center_retained"]==(category not in ("absolute_target_attained","improved_center"))
                and not c["production_promoted"] and not summary["guard_reference_recomputed"],"registered classification changed")
        classification={"category":category,"audited_worst_profile_gap":gap,"audited_worst_dated_ratio":ratio,
                        "original_box_local_search_exhausted":exhausted,"working_center_retained":c["working_center_retained"]}
    for r in rows:
        s=scores[r["attempt"]]
        late=dict(zip(("ATP","ADP"),np.array(r["prediction_mM"])[[panel["names"].index(p) for p in ("ATP","ADP")],panel["days"].index(15)])) if "prediction_mM" in r else {}
        table.append([r["attempt"],r["stage"],r["valid"],s["admitted"] if s else None,s["gap"] if s else None,
                      s["sides"]["ATP:lower"] if s else None,s["sides"]["ADP:lower"] if s else None,s["worst_ratio"] if s else None,
                      late.get("ATP"),late.get("ADP"),";".join(k for k,v in s["guards"].items() if v>0) if s else r.get("error")])
    report.mkdir(parents=True)
    write_csv(report/"search_attempts.csv",["attempt","stage","valid","reserve_admitted","worst_side_gap","ATP_lower_gap","ADP_lower_gap",
              "worst_dated_ratio","ATP_J15_mM","ADP_J15_mM","failed_guards_or_error"],table)
    write_csv(report/"search_minima_by_support.csv",["attempt","stage","support","worst_pool","minimum_mM","minimum_day","below_policy_count","nonfinite_count"],minima)
    if audit_minima:write_csv(report/"audit_minima_by_species.csv",["case","backend","profile","support","pool","minimum_mM","minimum_day","below_policy_count","nonfinite_count"],audit_minima)
    groups=list(f["design"]["groups"])
    write_csv(report/"searched_factors.csv",["attempt",*groups],[[r["attempt"],*np.exp(r["log_factors"]).tolist()] for r in rows])
    if budgets:write_csv(report/"ATP_budgets.csv",["case","backend","profile","period","production_mM","consumption_mM","net_mM","NDPK_net_positive_mM","NDPK_net_negative_mM"],budgets)
    receipt={"verified":True,"control_gate_pass":gate["pass"],"counts":counts,"classification":classification,
             "selected_attempt":result.get("selected",{}).get("attempt"),"bounds_expanded":False,"Km_initials_changed":False,
             "guard_caps_recomputed":False,"production_promoted":False,"J46_replayed":False,
             "source_seal_sha256":sha(out/"source_seal.json"),"archive_manifest_sha256":sha(out/"manifest.json"),"verifier_sha256":sha(Path(__file__))}
    write(report/"verification.json",receipt);seal(report);check_seal(report)
    return receipt


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--out",type=Path,required=True);p.add_argument("--report",type=Path,required=True)
    a=p.parse_args()
    with threadpool_limits(1):print(verify(a.out.resolve(),a.report.resolve()))
