from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from fla_vmax_requalification import classify_candidate,rejected_registry


def example():
    return {"parameters":{"vmax_VHK":.1,"vmax_VAK":1.,"vmax_VAK_rev":.3,"km_ATP":.2},
            "design":{"groups":{"HK":["vmax_VHK"],"AK":["vmax_VAK","vmax_VAK_rev"]},
                      "factor_bounds":{"HK":[.25,4.],"AK":[.05,2.]}},
            "resolved_capacities":["vmax_VHK","vmax_VAK","vmax_VAK_rev"]}


def test_registry_deduplicates_exact_actual_vectors_and_keeps_occurrences():
    f=example();before=deepcopy(f)
    row={"valid":False,"attempt":5,"log_factors":[0.,0.],"error":"negative or nonfinite checked concentration"}
    result=rejected_registry(f,[("a",[row]),("b",[row])],16)
    assert len(result)==1 and len(result[0]["occurrences"])==2 and f==before
    assert result[0]["parameters"]["km_ATP"]==.2


def test_metabolically_rejected_but_numerically_valid_rows_are_not_selected():
    bad={"valid":False,"attempt":1,"log_factors":[0.,0.],"error":"negative or nonfinite checked concentration"}
    result=rejected_registry(example(),[("a",[{"valid":True,"guards_pass":False},bad])],16)
    assert len(result)==1 and result[0]["occurrences"][0]["attempt"]==1


def test_source_vector_outside_box_is_not_clipped_into_a_candidate():
    row={"valid":False,"attempt":1,"log_factors":[2.,0.],"error":"negative or nonfinite checked concentration"}
    with pytest.raises(ValueError,match="expand old bounds"):
        rejected_registry(example(),[("a",[row])],16)


def test_relative_admission_is_not_absolute_atp_rescue():
    scores={p:{"reserved_guards_pass":True,"absolute":{"target_pass":False}} for p in ("strict","ultrastrict")}
    r=classify_candidate({p:True for p in scores},True,scores,True)
    assert r["category"]=="admissible_under_relative_guards" and not r["absolute_J15_targets_reached"]


def test_failed_second_tolerance_prevents_metabolic_admission():
    r=classify_candidate({"strict":True,"ultrastrict":False},False,{},True)
    assert r["category"]=="numerical_failure" and not r["rankable"]


def test_log_domain_failure_is_not_mislabelled_as_integrator_failure():
    r=classify_candidate({"strict":True,"ultrastrict":True},True,{"strict":None,"ultrastrict":None},True)
    assert r["category"]=="metabolic_guard_failure" and not r["observation_domain_valid"]


def test_absolute_target_cannot_override_a_metabolic_guard():
    scores={p:{"reserved_guards_pass":False,"absolute":{"target_pass":True}} for p in ("strict","ultrastrict")}
    r=classify_candidate({p:True for p in scores},True,scores,True)
    assert r["category"]=="metabolic_guard_failure" and not r["rankable"]
    assert r["absolute_J15_targets_reached"]


def test_registry_rejects_an_unknown_failure_reason():
    row={"valid":False,"attempt":1,"log_factors":[0.,0.],"error":"optimizer did not improve"}
    with pytest.raises(ValueError,match="unregistered rejection"):
        rejected_registry(example(),[("a",[row])],16)
