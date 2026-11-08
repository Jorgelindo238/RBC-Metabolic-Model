"""Read-only reconstruction of joint inference, source cells and executed budgets."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fla_joint_calibration import POOLS, COORDINATES, JointRHS, unpack
from rbc_glut_only_transport import equadiff_glut_only
from run_glut_only_free_replay import sha, close


def independent_likelihood(predicted, observed):
    d = np.log(np.asarray(observed))-np.log(np.asarray(predicted))
    m2 = float(np.sum(d**2)/d.size)
    # Independent algebraic root, with a stable positive m2 range in these fits.
    v = 2*(np.sqrt(1+m2)-1)
    value = np.sum((d+v/2)**2/(2*v)+np.log(observed)+.5*np.log(2*np.pi*v))
    return float(value)


def verify(out):
    checks = 0
    def require(ok, message):
        nonlocal checks
        checks += 1
        if not ok:
            raise ValueError(message)
    frozen = json.loads((out / "execution_design.json").read_text())
    d = frozen["design"]
    for p,h in frozen["input_sha256"].items():
        require(sha(ROOT/p)==h, f"input seal failed:{p}")
    for p,h in json.loads((out / "manifest.json").read_text())["output_sha256"].items():
        require(sha(out/p)==h, f"output seal failed:{p}")
    from openpyxl import load_workbook
    book = load_workbook(ROOT / d["source_workbook"],read_only=True,data_only=False)
    try:
        rows = list(book[d["source_sheet"]].iter_rows(values_only=True))
        observed = json.loads((out / "observations.json").read_text())
        require(list(rows[0][1:15])==observed["time"], "original sample days changed")
        for row in rows[1:]:
            if row[0] in observed["values"]:
                for value,expected in zip(row[1:15],observed["values"][row[0]]):
                    require(value==expected, "original concentration cell changed")
    finally:
        book.close()
    initial = np.array(frozen["initial"])
    require(np.array_equal(initial,np.load(ROOT/d["initial_context"]/"frozen_initial_state.npz")["states"]),"frozen IC changed")
    summary = json.loads((out / "summary.json").read_text())
    times = np.asarray(observed["time"])
    for fit in summary["fits"]:
        folder = out/f"fit_J{int(fit['training_end_day'])}"/fit["label"]
        trace = json.loads((folder/"trace.json").read_text())
        require(len(trace)==fit["actual_objective_integrations"],"objective integration count mismatch")
        require(len(trace)<=d["optimizer"]["secondary_maxfun"],"actual integration cap exceeded")
        mask=(times>1)&(times<=fit["training_end_day"])
        target=np.array([observed["values"][p] for p in POOLS])[:,mask]
        require(times[mask].tolist()==fit["source_times"],"non-source or future points fitted")
        valid=[]
        for row in trace:
            if not row["valid"]:
                require(row["objective_penalty"]==1e12,"undisclosed failed integration penalty")
                continue
            predicted=np.array(row["predictions"])
            nll=independent_likelihood(predicted,target)
            require(abs(nll-row["score"]["negative_log_likelihood"])<1e-8,"full likelihood arithmetic mismatch")
            valid.append(row)
        best=min(valid,key=lambda r:r["score"]["negative_log_likelihood"])
        require(best["log_factors"]==fit["selected_log_factors"],"training selection mismatch")
        params,kinetics,factors=unpack(fit["selected_log_factors"],frozen["parameters"],frozen["candidate"]["glucose_kinetics"],
                                     frozen["resolved_capacities"],d["factor_bounds"])
        require(params==fit["parameters"] and kinetics==fit["glucose_kinetics"] and factors==fit["factors"],"kinetic reinjection mismatch")
        with np.load(folder/"fit_replay.npz") as a:
            require(np.array_equal(a["accepted_states"][:,0],initial),"fit J1 reset")
            require(np.array_equal(a["observed"],target),"fit observations changed")
            require(np.allclose(a["prediction"],best["predictions"],rtol=1e-7,atol=1e-9),"selected fit replay mismatch")
            require(abs(independent_likelihood(a["prediction"],target)-fit["training_score"]["negative_log_likelihood"])<1e-8,
                    "fit likelihood record mismatch")
    numerical=[]
    for audit in summary["audits"]:
        prefix=out/"audits"/f"selected_training_J{int(audit['training_end_day'])}_replay_J{int(audit['replay_end_day'])}"
        stage=[f for f in summary["fits"] if f["training_end_day"]==audit["training_end_day"]]
        selected=min(stage,key=lambda r:r["training_score"]["negative_log_likelihood"])
        rhs=JointRHS(selected["parameters"],selected["glucose_kinetics"])
        pair=[]
        design=json.loads((ROOT/d["source_archive"]/"execution_design.json").read_text())["design"]
        for r in audit["results"]:
            path=prefix/f"J1_J{int(r['end_day'])}"/f"glut_real_candidate_{r['profile']}/replay.npz"
            with np.load(path) as a:
                require(np.array_equal(a["accepted_states"][:,0],initial),"audited initial state changed")
                require(a["accepted_time"][-1]==r["end_day"],"truncated audited replay")
                require(np.all(a["states"][-1]==initial[-1]),"diagnostic pH clamp changed")
                minimum=min(a["accepted_states"][:113].min(),a["states"][:113].min())
                integrals={}
                for order in (4,8):
                    minimum=min(minimum,a[f"q{order}_states"][:113].min())
                    for kind in ("raw","executed"):
                        rates=a[f"q{order}_{kind}_rates"]
                        weights=a[f"q{order}_weights"]
                        cells=a[f"q{order}_intervals"]
                        restored=np.vstack([np.bincount(cells,weights=weights*v,minlength=len(a["boundaries"])-1) for v in rates])
                        require(bool(close(restored,a[f"{kind}{order}"],design,"quadrature").all()),"saved quadrature reconstruction failed")
                        integrals[order,kind]=restored
                require(minimum==r["minimum_checked_mM"] and minimum>=-1e-10,"minimum or positivity failure")
                idx=np.searchsorted(a["time"],a["boundaries"])
                require(bool(close(np.diff(a["states"][:113,idx]),a["matrix"]@integrals[8,"executed"],design,"quadrature").all()),
                        "executed whole-pool increment budget failed")
                for pool in POOLS:
                    i=rhs.names.index(pool)
                    require(float(a["states"][i,-1])==r["endpoint"][pool],"endpoint record mismatch")
                    contributions=a["matrix"][i]*a["executed8"].sum(axis=1)
                    for reaction,value in r["executed_pool_contributions_mM"][pool].items():
                        require(abs(contributions[rhs.reactions.index(reaction)]-value)<1e-12,"guard-pool attribution mismatch")
                    mask=(times>1)&(times<=r["end_day"])
                    delta=a["states"][i,np.searchsorted(a["time"],times[mask])]-np.array(observed["values"][pool])[mask]
                    require(abs(np.sqrt(np.mean(delta**2))-r["source_fit_metrics"][pool]["nominal_RMSE_mM"])<1e-12,"source error mismatch")
                for q in np.unique(np.linspace(0,len(a["q8_nodes"])-1,7).astype(int)):
                    t,x=a["q8_nodes"][q],a["q8_states"][:,q]
                    live={}
                    original=equadiff_glut_only(t,x,glucose_kinetics=selected["glucose_kinetics"],hematocrit=.58,
                        custom_params=selected["parameters"],positivity_policy="reaction_consistent",curve_fit_strength=0.,
                        reaction_availability_threshold=.001,ph_policy="clamped_diagnostic",numerical_audit=live)
                    raw,executed,_=rhs.rates(t,x)
                    require(np.array_equal(raw,a["q8_raw_rates"][:,q]),"fast/native raw reaction parity failed")
                    require(np.array_equal(executed,a["q8_executed_rates"][:,q]),"fast/native executed rate parity failed")
                    require(np.array_equal(original,rhs(t,x)),"fast/native RHS parity failed")
                pair.append((a["states"][:113].copy(),a["raw8"].copy(),a["executed8"].copy()))
        passed=all(close(pair[0][i],pair[1][i],design,"comparison").all() for i in range(3))
        require(bool(passed)==all(r["numerical_pass"] for r in audit["results"]),"cross-tolerance numerical discrepancy")
        numerical.append(audit["numerical_pass"])
    require(all(numerical)==summary["all_numerical_pass"],"summary numerical gate mismatch")
    require(summary["production_promoted"] is False and summary["initial_state_changed"] is False,"unexpected promotion/IC change")
    require(summary["total_objective_integrations"]==sum(f["actual_objective_integrations"] for f in summary["fits"]),"total calls mismatch")
    return {"verified":True,"checks":checks,"fits":len(summary["fits"]),"audited_replays":2*len(summary["audits"]),
        "all_numerical_pass":summary["all_numerical_pass"],"physiological_validation":False,
        "live_RHS_scope":"seven_quadrature_states_per_full_replay_not_all_optimization_integrations_reexecuted"}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive",type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(verify(args.archive.resolve()),indent=2))
