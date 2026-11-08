"""Read-only source, constrained-selection, guard and executed-flux verification."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np
from scipy.stats import lognorm

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from fla_joint_calibration import JointRHS, unpack
from rbc_glut_only_transport import equadiff_glut_only
from run_glut_only_free_replay import sha, close
from run_protected_joint import check_seal

POOLS=("EGLC","GLC","LAC","ELAC","ATP","ADP","AMP","PEP","G6P")


def independently_score(pred,y):
    p=np.asarray(pred)
    residual=np.log(y)-np.log(p)
    m2=float(np.mean(residual**2))
    v=2*(np.sqrt(1+m2)-1)
    nll=float(-lognorm.logpdf(y,s=np.sqrt(v),scale=p*np.exp(-v/2)).sum())
    rms=np.array([np.sqrt(sum(float(d*d) for d in (row-actual))/len(row)) for row,actual in zip(p,y)])
    return nll,rms


def verify(out):
    count=0
    def require(ok,message):
        nonlocal count
        count+=1
        if not ok: raise ValueError(message)
    f=json.loads((out/"execution_design.json").read_text())
    d=f["design"]
    obs=json.loads((out/"observations.json").read_text())
    s=json.loads((out/"summary.json").read_text())
    for name,h in f["input_sha256"].items(): require(sha(ROOT/name)==h,"input hash:"+name)
    for name,h in json.loads((out/"manifest.json").read_text())["output_sha256"].items():
        require(sha(out/name)==h,"output hash:"+name)
    from openpyxl import load_workbook
    book=load_workbook(ROOT/f["parent_design"]["source_workbook"],read_only=True,data_only=False)
    try:
        rows=list(book[f["parent_design"]["source_sheet"]].iter_rows(values_only=True))
        require(list(rows[0][1:15])==obs["time"],"source times changed")
        for row in rows[1:]:
            if row[0] in obs["values"]:
                for value,actual in zip(row[1:15],obs["values"][row[0]]): require(value==actual,"original concentration changed")
    finally: book.close()
    time=np.asarray(obs["time"])
    mask=(time>1)&(time<=d["training_end_day"])
    t=time[mask]
    target=np.array([obs["values"][p] for p in POOLS])[:,mask]
    require(t.tolist()==d["training_times"],"nonoriginal/future training samples")
    base=ROOT/f["parent_design"]["source_archive"]
    with np.load(base/"J1_J10"/d["reference_case"]/"replay.npz") as a:
        names=a["pool_names"].tolist()
        pred=a["states"][[names.index(p) for p in POOLS]][:,np.searchsorted(a["time"],t)]
        reference=independently_score(pred,target)[1]
        require(np.array_equal(a["initial"],f["initial"]),"baseline initial state mismatch")
    for p,values in obs["values"].items(): require(f["initial"][names.index(p)]==values[0],"measured J1 changed")
    guard=f["guards"]
    allowance=d["guard_numerical_atol_mM"]+d["guard_numerical_rtol"]*reference
    fit_limits=reference+d["fitting_allowance_fraction"]*allowance
    audit_limits=reference+allowance
    require(np.allclose(reference,guard["reference_RMSE_mM"],atol=1e-12,rtol=1e-12),"guard reference mismatch")
    require(np.allclose(fit_limits,guard["fit_limit_RMSE_mM"],atol=1e-12,rtol=1e-12),"fit limits changed")
    require(np.allclose(audit_limits,guard["audit_limit_RMSE_mM"],atol=1e-12,rtol=1e-12),"audit limits changed")
    labels={}
    for fit in s["fits"]:
        folder=out/"fits"/fit["label"]
        check_seal(folder)
        trace=[json.loads(line) for line in (folder/"trace.jsonl").read_text().splitlines()]
        require(len(trace)==fit["actual_objective_integrations"],"integration count mismatch")
        require(len(trace)<=d["optimizer"]["secondary_cumulative_actual_integrations"],"integration cap exceeded")
        require(trace[0]["log_factors"]==[0.]*6,"missing control fallback evaluation")
        eligible=[]
        for i,row in enumerate(trace,1):
            require(row["call"]==i,"missing or reordered trace")
            if not row["valid"]: continue
            nll,rms=independently_score(row["predictions"],target)
            require(abs(nll-row["score"]["negative_log_likelihood"])<1e-7,"full nine-channel likelihood mismatch")
            require(np.allclose(rms,[row["score"]["RMSE_mM"][p] for p in POOLS],atol=1e-12,rtol=1e-12),"training RMS mismatch")
            passed=bool(np.all(rms<=fit_limits))
            require(passed==row["guards"]["passed"],"guard verdict mismatch")
            if passed: eligible.append(row)
        best=min(eligible,key=lambda r:r["score"]["negative_log_likelihood"])
        require(best["log_factors"]==fit["selected_log_factors"],"infeasible or nonminimal candidate selected")
        p,k,factors=unpack(fit["selected_log_factors"],f["parameters"],f["candidate"]["glucose_kinetics"],
                           f["resolved_capacities"],f["parent_design"]["factor_bounds"])
        require(p==fit["parameters"] and k==fit["glucose_kinetics"] and factors==fit["factors"],"changed parameter scope")
        with np.load(folder/"fit_replay.npz") as a:
            require(np.array_equal(a["accepted_states"][:,0],f["initial"]),"fit initial state changed")
            require(np.array_equal(a["observed"],target) and np.array_equal(a["sample_time"],t),"fit used other observations")
            nll,rms=independently_score(a["prediction"],target)
            require(np.all(rms<=fit_limits),"selected fitting replay violates guards")
            require(abs(nll-fit["training_score"]["negative_log_likelihood"])<1e-7,"selected NLL mismatch")
        labels[fit["label"]]=fit
    labels[s["selected"]["label"]]=s["selected"]
    numerical=json.loads((base/"execution_design.json").read_text())["design"]
    for audit in s["audits"]:
        folder=out/"audits"/(audit["label"]+f"_J{int(audit['end_day'])}")
        check_seal(folder)
        selected=labels.get(audit["label"])
        if selected is None:
            # A rejected first selection is still one of the completed fit labels.
            raise ValueError("audit kinetic identity not available")
        rhs=JointRHS(selected["parameters"],selected["glucose_kinetics"])
        pair=[]
        guard_flags=[]
        for r in audit["results"]:
            with np.load(folder/f"J1_J{int(audit['end_day'])}"/f"glut_real_candidate_{r['profile']}/replay.npz") as a:
                require(np.array_equal(a["initial"],f["initial"]) and np.array_equal(a["accepted_states"][:,0],f["initial"]),"audit J1 changed")
                require(a["accepted_time"][-1]==audit["end_day"],"truncated original-path replay")
                require(np.all(a["states"][-1]==f["initial"][-1]),"pH clamp changed")
                minimum=min(a["states"][:113].min(),a["accepted_states"][:113].min())
                integrals={}
                for order in (4,8):
                    minimum=min(minimum,a[f"q{order}_states"][:113].min())
                    for kind in ("raw","executed"):
                        rates=a[f"q{order}_{kind}_rates"]
                        weights=a[f"q{order}_weights"]
                        cells=a[f"q{order}_intervals"]
                        require(np.all(np.isfinite(rates)),"nonfinite stored rates")
                        restored=np.vstack([np.bincount(cells,weights=weights*v,minlength=len(a["boundaries"])-1) for v in rates])
                        require(bool(close(restored,a[f"{kind}{order}"],numerical,"quadrature").all()),"quadrature reconstruction failed")
                        integrals[order,kind]=restored
                require(minimum==r["minimum_checked_mM"],"stored minimum mismatch")
                ix=np.searchsorted(a["time"],a["boundaries"])
                checks=[close(np.diff(a["states"][:113,ix]),a["matrix"]@integrals[8,"executed"],numerical,"quadrature"),
                        close(integrals[4,"raw"],integrals[8,"raw"],numerical,"quadrature"),
                        close(integrals[4,"executed"],integrals[8,"executed"],numerical,"quadrature")]
                passed=bool(all(c.all() for c in checks) and minimum>=-1e-10 and r["raw_closure_max"]<=1e-7 and r["executed_closure_max"]<=1e-7)
                require(passed==r["numerical_pass"],"original-path numerical flag mismatch")
                if audit["end_day"]>=d["training_end_day"]:
                    pred=a["states"][[rhs.names.index(p) for p in POOLS]][:,np.searchsorted(a["time"],t)]
                    _,rms=independently_score(pred,target)
                    guard_flags.append(bool(np.all(rms<=audit_limits)))
                    recorded=next(g for g in audit["training_guards"] if g["profile"]==r["profile"])
                    require(guard_flags[-1]==recorded["passed"],"full-path guard verdict mismatch")
                for pool in POOLS:
                    require(float(a["states"][rhs.names.index(pool),-1])==r["endpoint"][pool],"endpoint mismatch")
                for q in np.unique(np.linspace(0,len(a["q8_nodes"])-1,7).astype(int)):
                    tt,x=a["q8_nodes"][q],a["q8_states"][:,q]
                    live={}
                    derivative=equadiff_glut_only(tt,x,glucose_kinetics=selected["glucose_kinetics"],hematocrit=.58,
                        custom_params=selected["parameters"],positivity_policy="reaction_consistent",curve_fit_strength=0.,
                        reaction_availability_threshold=.001,ph_policy="clamped_diagnostic",numerical_audit=live)
                    raw,executed,_=rhs.rates(tt,x)
                    require(np.array_equal(raw,a["q8_raw_rates"][:,q]),"sampled raw flux parity failed")
                    require(np.array_equal(executed,a["q8_executed_rates"][:,q]),"sampled executed flux parity failed")
                    require(np.array_equal(derivative,rhs(tt,x)),"original/fast RHS mismatch")
                if r["profile"]=="ultrastrict":
                    with np.load(folder/"fast_parity.npz") as fast:
                        require(np.array_equal(fast["time"],a["time"]),"fast parity grid changed")
                        parity=bool(np.allclose(fast["states"][:113],a["states"][:113],rtol=.01,atol=1e-5))
                        require(parity and audit["fast_full_parity"],"fast/full trajectory parity failed")
                pair.append((a["states"][:113].copy(),a["raw8"].copy(),a["executed8"].copy()))
        convergence=all(close(pair[0][i],pair[1][i],numerical,"comparison").all() for i in range(3))
        require(bool(convergence)==(audit["convergence_checks_passed"]==audit["convergence_checks_total"]),"convergence mismatch")
        require(all(guard_flags)==audit["guard_pass"],"audit guard summary mismatch")
    require(s["total_objective_integrations"]==sum(r["actual_objective_integrations"] for r in s["fits"]),"total evaluations mismatch")
    require(s["production_promoted"] is False and s["initial_states_changed"] is False and s["kinetic_box_expanded"] is False,"scope changed")
    return {"verified":True,"checks":count,"fits":len(s["fits"]),"original_path_replays":2*len(s["audits"]),
        "training_guard_acceptance":s["accepted_numeric_and_training_guards"],"selected_is_control":s["selected_is_control"],
        "physiological_validation":False,"late_guard_or_parameter_selection":False,
        "live_RHS_sampling":"seven_saved_quadrature_states_per_replay_not_all_optimizer_integrations_reexecuted"}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive",type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(verify(args.archive.resolve()),indent=2))
