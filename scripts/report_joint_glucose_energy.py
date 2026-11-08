"""Secondary read-only comparison, off-target errors and reusable candidate export."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from fla_joint_calibration import COORDINATES, GROUPS, POOLS, joint_score
from run_glut_only_free_replay import sha, write


def signed_budget(row, rates, weights):
    contributions=np.asarray(row)[:,None]*np.asarray(rates)
    weights=np.asarray(weights)
    return {"production_mM":float(np.sum(np.maximum(contributions,0)*weights)),
            "consumption_mM":float(-np.sum(np.minimum(contributions,0)*weights))}


def summarize(archive,out):
    if out.exists():
        raise ValueError("fresh secondary comparison directory required")
    summary=json.loads((archive/"summary.json").read_text())
    frozen=json.loads((archive/"execution_design.json").read_text())
    data=json.loads((archive/"observations.json").read_text())
    time=np.array(data["time"])
    design=frozen["design"]
    baseline=ROOT/design["source_archive"]
    training=[]
    for end in sorted({f["training_end_day"] for f in summary["fits"]}):
        mask=(time>1)&(time<=end)
        target=np.array([data["values"][p] for p in POOLS])[:,mask]
        for case in ("phase_native_reference","glut_seed_control","glut_real_candidate"):
            path=baseline/f"J1_J{int(end)}"/f"{case}_ultrastrict/replay.npz"
            with np.load(path) as a:
                names=a["pool_names"].tolist()
                prediction=a["states"][[names.index(p) for p in POOLS]][:,np.searchsorted(a["time"],time[mask])]
                training.append({"training_end_day":end,"case":case,"kinetics_fitted_in_this_campaign":False,
                    "score":joint_score(prediction,target)})
        for fit in (f for f in summary["fits"] if f["training_end_day"]==end):
            training.append({"training_end_day":end,"case":fit["label"],"kinetics_fitted_in_this_campaign":True,
                "score":fit["training_score"],"factors":fit["factors"],"bound_hits":fit["bound_hits"],
                "optimizer_success":fit["optimizer_success"],"actual_objective_integrations":fit["actual_objective_integrations"]})
    predictions=[]
    candidate=summary["selected"]
    last=candidate["training_end_day"]
    sources=[]
    for case in ("phase_native_reference","glut_real_candidate"):
        sources.append((case,baseline/"J1_J46"/f"{case}_ultrastrict/replay.npz"))
    audited46=next((a for a in summary["audits"] if a["replay_end_day"]==46),None)
    if audited46:
        sources.append(("joint_candidate",archive/"audits"/f"selected_training_J{int(last)}_replay_J46"/
                        "J1_J46/glut_real_candidate_ultrastrict/replay.npz"))
    off_targets=[]
    for case,path in sources:
        with np.load(path) as a:
            names=a["pool_names"].tolist()
            reaction_names=a["reactions"].tolist()
            mask=(time>1)
            observed=np.array([data["values"][p] for p in POOLS])[:,mask]
            predicted=a["states"][[names.index(p) for p in POOLS]][:,np.searchsorted(a["time"],time[mask])]
            early=(time[mask]<=last)
            training_score=joint_score(predicted[:,early],observed[:,early])
            log_variance=(candidate["training_score"]["log_variance"] if case=="joint_candidate"
                          else training_score["log_variance"])
            # Variance remains fixed at the early training estimate for late scoring.
            residual=np.log(observed[:,~early])-np.log(predicted[:,~early])
            nll=float(np.sum(.5*(residual+log_variance/2)**2/log_variance+np.log(observed[:,~early])
                             +.5*np.log(2*np.pi*log_variance)))
            balances={}
            totals=a["executed8"].sum(axis=1)
            for pool in ("GLC","ATP","ADP","AMP","RIB","PRPP","GTP","GDP"):
                i=names.index(pool)
                terms=a["matrix"][i]*totals
                balances[pool]={"endpoint_increment_mM":float(a["states"][i,-1]-a["states"][i,0]),
                    "integrated_executed_net_mM":float(terms.sum()),
                    **signed_budget(a["matrix"][i],a["q8_executed_rates"],a["q8_weights"]),
                    "reaction_contributions_mM":{r:float(v) for r,v in zip(reaction_names,terms) if v!=0}}
            pgk=reaction_names.index("VPGK")
            consumers=np.flatnonzero(a["matrix"][:,pgk]<0)
            availability=np.clip(a["q8_states"][consumers]/.001,0,1)
            factors=availability.min(axis=0)
            limited=factors<1-1e-12
            ties=availability==factors[None,:]
            shares=ties/ties.sum(axis=0)
            pgk_windows={}
            for label,use in (("J1_J46",np.ones(len(factors),dtype=bool)),("J4_J46",a["q8_nodes"]>4)):
                w=a["q8_weights"][use]
                raw=a["q8_raw_rates"][pgk,use]
                executed=a["q8_executed_rates"][pgk,use]
                losses=(raw-executed)*w
                pgk_windows[label]={"native_integral_mM":float(np.dot(raw,w)),
                    "executed_integral_mM":float(np.dot(executed,w)),
                    "limited_quadrature_weight_fraction":float(w[limited[use]].sum()/w.sum()),
                    "native_minus_executed_allocation_mM":{names[i]:float(np.dot(shares[j,use],losses))
                                                             for j,i in enumerate(consumers)},
                    "scope":"trajectory_specific_numerical_availability_allocation_ties_split_not_causal_or_no_limiter_counterfactual"}
            predictions.append({"case":case,"endpoint_mM":{p:float(a["states"][names.index(p),-1]) for p in POOLS},
                "all_noninitial_RMSE_mM":dict(zip(POOLS,np.sqrt(np.mean((predicted-observed)**2,axis=1)).tolist())),
                "late_RMSE_mM":dict(zip(POOLS,np.sqrt(np.mean((predicted[:,~early]-observed[:,~early])**2,axis=1)).tolist())),
                "late_NLL_at_own_fixed_training_variance":nll,"training_log_variance":log_variance,
                "full_path_training_score":training_score,
                "late_times":time[mask][~early].tolist(),"executed_budgets":balances,
                "PGK_availability_windows":pgk_windows,
                "executed_reaction_integrals_native_basis_mM":dict(zip(reaction_names,totals.tolist())),
                "reaction_rate_volume_fractions":dict(zip(reaction_names,a["reaction_volumes"].tolist())),
                "rate_basis_note":"cell_basis_except_explicit_supernatant_degradation_reactions_as_in_frozen_contract"})
            for pool,values in data["values"].items():
                if pool in POOLS:
                    continue
                pred=a["states"][names.index(pool),np.searchsorted(a["time"],time[mask])]
                obs=np.array(values)[mask]
                off_targets.append({"case":case,"pool":pool,"RMSE_all_postinitial_mM":float(np.sqrt(np.mean((pred-obs)**2))),
                    "RMSE_late_mM":float(np.sqrt(np.mean((pred[~early]-obs[~early])**2))),
                    "endpoint_predicted_mM":float(pred[-1]),"endpoint_observed_mM":float(obs[-1]),
                    "known_exact_duplicate_alias":pool in ("B13PG","P2G"),
                    "assay_independence_established":False,
                    "used_to_select_candidate":False})
    seeds={name:candidate["parameters"][name] for group in GROUPS.values() for name in group}
    export={"status":"conditional_exploratory_candidate_not_production_default",
        "source_archive":str(archive.relative_to(ROOT)),"source_summary_sha256":sha(archive/"summary.json"),
        "training_end_day":last,"selected_start":candidate["label"],"initial_context":design["initial_context"],
        "initial_state_changes":False,"base_frozen_parameters_path":design["initial_context"]+"/frozen_parameters.json",
        "parameter_overrides":seeds,"glucose_kinetics":candidate["glucose_kinetics"],
        "hematocrit":.58,"pH_policy":"clamped_diagnostic","positivity_policy":"reaction_consistent",
        "availability_threshold_mM":.001,"native_VELAC_changed":False,
        "training_residual_variance":candidate["training_score"]["log_variance"],
        "numerical_pass":summary["all_numerical_pass"],
        "validated_replay_end_day":max((a["replay_end_day"] for a in summary["audits"] if a["numerical_pass"]),default=None),
        "use_requires_numerical_pass":True,
        "biological_parameters_identified":False,"production_promoted":False}
    report={"training_comparisons":training,"full_J46_comparisons":predictions,
        "nominal_source_J46_mM":{p:data["values"][p][-1] for p in POOLS},
        "off_target_source_channels":off_targets,"off_target_scope":"48_channel_representations_not48_independent_assays",
        "temporal_scope":"exposed_internal_late_points_not_independent_validation",
        "off_target_channels_entered_fit_or_selection":False,"candidate_promoted":False}
    report["frozen_initial_pool_context"]={p:{"initial_mM":frozen["initial"][names.index(p)],
        "source_channel_present":p in data["values"],"changed_in_this_campaign":False}
        for p in ("RIB","R5P","PRPP","GTP","GDP","ADO","IMP","ADESUC","NAD","NADH","B13PG","B23PG")}
    out.mkdir(parents=True)
    write(out/"comparison.json",report)
    write(out/"candidate.json",export)
    paths=[Path(__file__),archive/"summary.json",archive/"execution_design.json",archive/"observations.json"]
    paths += [p for _,p in sources]
    write(out/"manifest.json",{"input_sha256":{p.relative_to(ROOT).as_posix():sha(p) for p in paths},
        "output_sha256":{p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()}})
    return {"training_comparisons":len(training),"J46_cases":len(predictions),"off_target_rows":len(off_targets),"candidate_promoted":False}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(summarize(args.archive.resolve(),args.out.resolve()),indent=2))
