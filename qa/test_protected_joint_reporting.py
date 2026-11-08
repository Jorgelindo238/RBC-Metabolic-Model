import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from report_protected_joint import check_selection, summarize_regressions


def selection_fixture():
    vector=[-.1]*6
    summary={"fits":[{"label":"best","selected_log_factors":vector,"training_score":{"negative_log_likelihood":3.}},
                      {"label":"other","selected_log_factors":[-.2]*6,"training_score":{"negative_log_likelihood":4.}}],
        "selection_attempts":[{"log_factors":vector,"accepted":True}],
        "selected":{"selected_log_factors":vector}}
    return summary,{"design":{"minimum_training_NLL_gain":.0001}}


def test_summary_distinguishes_audit_channels_from_guards():
    rows={p:{"training_RMSE_delta_vs_control_mM":delta,"all_RMSE_delta_vs_control_mM":late}
          for p,delta,late in (("PEP",-.1,2.),("G6P",-.2,-.1),("RIB",.3,.4))}
    s=summarize_regressions(rows)
    assert s["protected_nine"]["training"]["raw_positive_delta_channels"]==0
    assert s["protected_nine"]["all_postinitial"]["largest_ten_RMSE_increases_mM"]=={"PEP":2.}
    assert s["other46_audit_only"]["training"]["largest_ten_RMSE_increases_mM"]=={"RIB":.3}


def test_training_selection_check_rejects_wrong_ranking():
    s,f=selection_fixture()
    assert check_selection(s,f,9.)["training_NLL_gain_vs_control"]==6.
    s["selection_attempts"][0]["log_factors"]=[-.2]*6
    with pytest.raises(ValueError,match="training-only"):
        check_selection(s,f,9.)


def test_control_fallback_needs_failed_audit():
    s,f=selection_fixture()
    original=copy.deepcopy(s)
    s["selection_attempts"].append({"log_factors":[0.]*6,"accepted":True})
    s["selected"]["selected_log_factors"]=[0.]*6
    with pytest.raises(ValueError,match="fallback"):
        check_selection(s,f,9.)
    s["selection_attempts"][0]["accepted"]=False
    assert check_selection(s,f,9.)["audit_fallback_used"]
    original["selection_attempts"][0]["log_factors"]=[0.]*6
    original["selected"]["selected_log_factors"]=[0.]*6
    assert check_selection(original,f,3.)["checked"]
