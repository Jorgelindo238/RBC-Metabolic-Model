"""Source-preserving guarded-fit comparison and unpromoted candidate export."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from fla_joint_calibration import GROUPS
from fla_protected_calibration import POOLS, score, training_data, assess
from run_glut_only_free_replay import sha, write
from report_joint_glucose_energy import signed_budget


def summarize_regressions(metrics):
    result={}
    for scope,pools in (("protected_nine",[p for p in metrics if p in POOLS]),
                        ("other46_audit_only",[p for p in metrics if p not in POOLS])):
        result[scope]={"channel_count":len(pools)}
        for period,key in (("training","training_RMSE_delta_vs_control_mM"),
                           ("all_postinitial","all_RMSE_delta_vs_control_mM")):
            worse=sorted((p for p in pools if metrics[p][key]>0),key=lambda p:metrics[p][key],reverse=True)
            result[scope][period]={"raw_positive_delta_channels":len(worse),
                "largest_ten_RMSE_increases_mM":{p:metrics[p][key] for p in worse[:10]}}
    result["interpretation"]="raw_RMSE_deltas_not_independent_assay_counts_or_late_acceptance_rules"
    return result


def check_selection(summary,frozen,control_score):
    best=min(summary["fits"],key=lambda r:r["training_score"]["negative_log_likelihood"])
    gain=control_score-best["training_score"]["negative_log_likelihood"]
    first=summary["selection_attempts"][0]
    expected=([0.]*6 if gain<frozen["design"]["minimum_training_NLL_gain"] else best["selected_log_factors"])
    if first["log_factors"]!=expected:
        raise ValueError("first audit candidate does not follow the frozen training-only selection")
    attempts=summary["selection_attempts"]
    if len(attempts)>1 and (len(attempts)!=2 or attempts[0]["accepted"] or attempts[1]["log_factors"]!=[0.]*6):
        raise ValueError("fallback decision inconsistent with frozen audit gate")
    if attempts[-1]["log_factors"]!=summary["selected"]["selected_log_factors"]:
        raise ValueError("final candidate differs from the audited selection")
    return {"checked":True,"best_training_fit_label":best["label"],"training_NLL_gain_vs_control":gain,
            "minimum_gain_required":frozen["design"]["minimum_training_NLL_gain"],
            "audit_fallback_used":len(attempts)>1,"late_residuals_consulted":False}


def report(archive,out):
    if out.exists(): raise ValueError("fresh comparison directory required")
    f=json.loads((archive/"execution_design.json").read_text())
    s=json.loads((archive/"summary.json").read_text())
    obs=json.loads((archive/"observations.json").read_text())
    times,target=training_data(obs,f["design"]["training_end_day"])
    base=ROOT/f["parent_design"]["source_archive"]
    parent=ROOT/f["design"]["parent_archive"]
    selected=s["selected"]
    candidates=[("GLUT_control",base/"J1_J46/glut_real_candidate_ultrastrict/replay.npz"),
        ("rejected_seven_pool_fit",parent/"audits/selected_training_J10_replay_J46/J1_J46/glut_real_candidate_ultrastrict/replay.npz")]
    path=archive/"audits"/(selected["label"]+"_J46")/"J1_J46/glut_real_candidate_ultrastrict/replay.npz"
    if path.exists(): candidates.append(("protected_selection",path))
    comparisons=[]
    all_times=np.array(obs["time"])
    post=all_times>1
    control_metrics=None
    hashes={}
    for label,path in candidates:
        hashes[path.relative_to(ROOT).as_posix()]=sha(path)
        with np.load(path) as a:
            names=a["pool_names"].tolist()
            state=a["states"]
            pool_metrics={}
            for pool,source in obs["values"].items():
                y=np.asarray(source)[post]
                prediction=state[names.index(pool),np.searchsorted(a["time"],all_times[post])]
                early=all_times[post]<=10
                pool_metrics[pool]={"training_RMSE_mM":float(np.sqrt(np.mean((prediction[early]-y[early])**2))),
                    "all_postinitial_RMSE_mM":float(np.sqrt(np.mean((prediction-y)**2))),
                    "late_J11_J46_RMSE_mM":float(np.sqrt(np.mean((prediction[~early]-y[~early])**2))),
                    "endpoint_mM":float(prediction[-1]),"nominal_endpoint_mM":float(y[-1]),
                    "hard_training_guarded":pool in POOLS,"known_duplicate_alias":pool in ("B13PG","P2G"),
                    "assay_independence_established":False}
                if pool in POOLS:
                    pool_metrics[pool]["training_observations_mM"]=y[early].tolist()
                    pool_metrics[pool]["training_predictions_mM"]=prediction[early].tolist()
            early_pred=state[[names.index(p) for p in POOLS]][:,np.searchsorted(a["time"],times)]
            checked=assess(early_pred,target,f["guards"],phase="audit")
            weights=a["q8_weights"]
            executed=a["q8_executed_rates"]
            reactions=a["reactions"].tolist()
            totals=a["executed8"].sum(axis=1)
            budgets={}
            for pool in ("GLC","ATP","ADP","AMP","RIB","PRPP","PEP"):
                row=a["matrix"][names.index(pool)]
                contributions=row*totals
                budgets[pool]={**signed_budget(row,executed,weights),
                    "net_integrated_mM":float(contributions.sum()),
                    "endpoint_change_mM":float(state[names.index(pool),-1]-state[names.index(pool),0]),
                    "signed_reaction_contributions_mM":{r:float(v) for r,v in zip(reactions,contributions) if v!=0}}
            if control_metrics is None: control_metrics=pool_metrics
            for pool,metrics in pool_metrics.items():
                metrics["training_RMSE_delta_vs_control_mM"]=metrics["training_RMSE_mM"]-control_metrics[pool]["training_RMSE_mM"]
                metrics["all_RMSE_delta_vs_control_mM"]=metrics["all_postinitial_RMSE_mM"]-control_metrics[pool]["all_postinitial_RMSE_mM"]
            comparisons.append({"case":label,"all55_pool_metrics":pool_metrics,
                "nine_pool_training_score":score(early_pred,target),"nine_pool_training_guards":checked,
                "executed_budgets":budgets,"training_times":times.tolist(),
                "regression_summary":summarize_regressions(pool_metrics),
                "kinetic_parameters_selected_using_late_errors":False})
    trace=[json.loads(line) for line in (archive/"fits/control/trace.jsonl").read_text().splitlines()]
    control_score=next(r["score"]["negative_log_likelihood"] for r in trace if r["log_factors"]==[0.]*6)
    selection=check_selection(s,f,control_score)
    candidate={"status":"protected_training_candidate_not_physiologically_validated",
        "source_archive":archive.relative_to(ROOT).as_posix(),"source_summary_sha256":sha(archive/"summary.json"),
        "is_control_fallback":s["selected_is_control"],"numerical_and_training_guards_pass":s["accepted_numeric_and_training_guards"],
        "initial_context":f["parent_design"]["initial_context"],"initial_states_changed":False,
        "parameter_overrides":{name:selected["parameters"][name] for group in GROUPS.values() for name in group},
        "glucose_kinetics":selected["glucose_kinetics"],"hematocrit":.58,"pH_policy":"clamped_diagnostic",
        "positivity_policy":"reaction_consistent","availability_threshold_mM":.001,
        "native_VELAC_changed":False,"production_promoted":False,"guarded_pools":list(POOLS)}
    result={"comparisons":comparisons,"guard_contract":f["guards"],"selected_label":selected["label"],
        "selected_factors":selected["factors"],"total_objective_integrations":s["total_objective_integrations"],
        "selection_verification":selection,
        "fit_statuses":[{key:r[key] for key in ("label","optimizer_success","actual_objective_integrations","feasible_evaluations")} for r in s["fits"]],
        "training_guard_scope":"nine_pool_RMSE_over_J4_J8_not_pointwise_or_long_term_nonregression",
        "other_source_channels":46,"all55_source_channels_independent":False,
        "biological_promotion":False,"initial_state_changed":False}
    out.mkdir(parents=True)
    write(out/"comparison.json",result)
    write(out/"candidate.json",candidate)
    sources=[Path(__file__),ROOT/"scripts/report_joint_glucose_energy.py",ROOT/"src/fla_protected_calibration.py",
             archive/"execution_design.json",archive/"summary.json",archive/"observations.json",archive/"fits/control/trace.jsonl"]
    hashes.update({p.relative_to(ROOT).as_posix():sha(p) for p in sources})
    write(out/"manifest.json",{"input_sha256":hashes,
        "output_sha256":{p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()}})
    return {"comparisons":len(comparisons),"source_pool_rows":55*len(comparisons),"selected_is_control":s["selected_is_control"],
            "candidate_promoted":False}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(report(args.archive.resolve(),args.out.resolve()),indent=2))
