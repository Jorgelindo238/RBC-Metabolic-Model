"""Immutable replay registry and explicit numerical/metabolic decisions."""

import json

import numpy as np

from fla_agentic_vmax_search import inject_vmax_only


def exact_parameters(f,vector):
    x=np.asarray(vector,float)
    groups=f["design"]["groups"]
    if x.shape!=(len(groups),) or not np.isfinite(x).all():
        raise ValueError("literal finite source vector required")
    p=inject_vmax_only(f["parameters"],groups,x)
    changed={k for k in p if p[k]!=f["parameters"][k]}
    if not changed<=set(f["resolved_capacities"]) or p["vmax_VHK"]>5:
        raise ValueError("non-Vmax, closed capacity or HK ceiling changed")
    return p


def within_original_box(f,vector):
    factors=np.exp(np.asarray(vector,float))
    bounds=np.array([f["design"]["factor_bounds"][k] for k in f["design"]["groups"]])
    return bool(np.all(factors>=bounds[:,0]-1e-12) and np.all(factors<=bounds[:,1]+1e-12))


def rejected_registry(f,sources,maximum):
    unique={}
    for source_id,rows in sources:
        for row in rows:
            if row["valid"]:
                continue
            if row.get("error")!="negative or nonfinite checked concentration":
                raise ValueError("unregistered rejection type")
            vector=list(row["log_factors"])
            parameters=exact_parameters(f,vector)
            key=json.dumps(parameters,sort_keys=True,allow_nan=False,separators=(",",":"))
            occurrence={"source":source_id,"attempt":row["attempt"],"source_case":row.get("id"),
                        "stage":row.get("stage"),"original_error":row["error"]}
            if key not in unique:
                if not within_original_box(f,vector):
                    raise ValueError("requalification cannot expand old bounds")
                unique[key]={"id":f"candidate_{len(unique)+1:02d}","role":"candidate",
                             "log_factors":vector,"parameters":parameters,"occurrences":[]}
            unique[key]["occurrences"].append(occurrence)
    if not unique or len(unique)>maximum:
        raise ValueError("requalification registry size invalid")
    return list(unique.values())


def classify_candidate(numerical_pass,comparison_pass,scores,inside_box):
    if not all(numerical_pass.values()) or not comparison_pass:
        return {"category":"numerical_failure","absolute_J15_targets_reached":False,"rankable":False}
    defined=all(s is not None for s in scores.values())
    guards=bool(defined and inside_box and all(s["reserved_guards_pass"] for s in scores.values()))
    absolute=bool(defined and all(s["absolute"]["target_pass"] for s in scores.values()))
    return {"category":"admissible_under_relative_guards" if guards else "metabolic_guard_failure",
            "absolute_J15_targets_reached":absolute,"rankable":guards,
            "observation_domain_valid":defined,"inside_original_box":bool(inside_box)}
