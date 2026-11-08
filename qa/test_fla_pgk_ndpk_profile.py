from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from fla_pgk_ndpk_profile import POOLS, audit_roles, executed_ledger, ndpk_column, profile_cases


def example():
    return {"design":{"groups":{"HK":["h"],"PGK":["p"],"NDPK":["n","nr"]},
                      "factor_bounds":{"PGK":[.5,1.5],"NDPK":[.1,2]}},
            "profile_center":[.1,np.log(.5),np.log(2)],
            "pgk_ndpk":{"PGK_factors":[.25,.5,1,1.5],"NDPK_factors":[.1,1,2,4],
                        "PGK_lower_probe":.25,"NDPK_upper_probe":4,"maximum_screen_attempts":17}}


def test_counterfactuals_are_labelled_without_changing_old_bounds():
    f=example()
    cases=profile_cases(f)
    assert len(cases)==17 and sum(c["inside_previous_box"] for c in cases)==10
    assert f["design"]["factor_bounds"]=={"PGK":[.5,1.5],"NDPK":[.1,2]}
    for c in cases[1:]:
        assert c["log_factors"][0]==.1
        assert np.exp(c["log_factors"][1:])==pytest.approx([c["PGK_factor"],c["NDPK_factor"]])


def test_audit_roles_never_admit_an_out_of_box_best_point():
    f=example()
    rows=profile_cases(f)
    for i,r in enumerate(rows):
        r.update(valid=True,reserved_guards_pass=True,absolute={"objective":-i})
    roles=audit_roles(rows,f)
    chosen=next(r for r in rows if r["id"]==roles["best_guarded_in_box"])
    assert chosen["inside_previous_box"]
    assert roles["best_absolute_any_valid"]!=roles["best_guarded_in_box"]


def fixture():
    matrix=np.array([-1,1,0,-1,1,0.])[:,None]
    boundaries=np.arange(1.,16.)
    initial=np.full(6,50.)
    return {"pool_names":np.array(POOLS),"reactions":np.array(["VNDPK"]),"matrix":matrix,
            "time":boundaries,"boundaries":boundaries,"states":initial[:,None]+matrix@(2*np.arange(15.))[None,:],
            "executed8":np.full((1,14),2.),"q8_weights":np.ones(14),"q8_intervals":np.arange(14),
            "q8_executed_rates":np.full((1,14),2.)}


def test_executed_ledger_exact_transfer_and_nucleotide_conservation():
    ledger=executed_ledger(fixture())
    late=ledger["periods"]["J8_J15"]
    assert late["ATP_production_mM"]==0 and late["ATP_consumption_mM"]==14
    assert late["NDPK_net_positive_direction_mM"]==14 and late["NDPK_net_negative_direction_mM"]==0
    p=late["pools"]
    assert all(abs(x["balance_residual_mM"])<1e-12 for x in p.values())
    assert sum(p[k]["executed_delta_mM"] for k in ("ATP","ADP","AMP"))==0
    assert sum(p[k]["executed_delta_mM"] for k in ("GTP","GDP","GMP"))==0
    assert p["ATP"]["executed_delta_mM"]+p["GTP"]["executed_delta_mM"]==0


def test_reverse_net_flux_produces_atp_not_consumption():
    a=fixture()
    a["q8_executed_rates"]*=-1
    a["executed8"]*=-1
    a["states"]=100-a["states"]
    late=executed_ledger(a)["periods"]["J8_J15"]
    assert late["ATP_production_mM"]==14 and late["ATP_consumption_mM"]==0
    assert late["NDPK_net_negative_direction_mM"]==14


def test_changed_ndpk_stoichiometry_is_not_silently_accepted():
    a=fixture()
    a["matrix"][0,0]=-2
    with pytest.raises(ValueError,match="column changed"):
        ndpk_column(a["matrix"],list(POOLS),["VNDPK"])


def test_duplicate_profile_is_rejected():
    f=example()
    f["pgk_ndpk"]["PGK_factors"]=[.5,.5]
    with pytest.raises(ValueError,match="duplicate"):
        profile_cases(f)
