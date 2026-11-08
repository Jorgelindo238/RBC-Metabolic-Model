import csv
import io
import json
from pathlib import Path
import sys

import numpy as np
import pytest
from threadpoolctl import threadpool_limits

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_agentic_atp_consumption import (
    BASE, DEST, KINDS, LABELS, METRICS, WINDOWS, artifacts, build, directional_daily, limiter_loss,
    matched_delta, projected, read, window_id,
)


def test_split_before_integrating_does_not_erase_turnover():
    daily = directional_daily(np.array([[3., -3., 8., -4.]]), np.full(4, .5),
                              np.array([0, 0, 1, 1]), 2)
    np.testing.assert_array_equal(daily[:, 0], [[1.5, 4.], [1.5, 2.]])
    np.testing.assert_array_equal(projected(np.array([-1.]), daily[:, :, 0])[:, 0], [1.5, 1.5, 0.])
    np.testing.assert_array_equal(projected(np.array([-1.]), daily[:, :, 1])[:, 0], [2., 4., -2.])


def test_limiter_assigns_ties_and_excludes_negative_direction():
    indices, loss = limiter_loss(np.array([-1., -1., 1.]),
                                np.array([[.5, .8, .9], [.5, .2, .9], [.1, .1, .1]]),
                                np.array([2., 2., -10.]), np.array([1., .4, -1.]), np.ones(3))
    np.testing.assert_array_equal(indices, [0, 1])
    np.testing.assert_allclose(loss, [.5, 2.1])


def test_unmatched_late_window_is_rejected():
    with pytest.raises(ValueError, match="nonmatched comparison"):
        matched_delta({"J1_J2": {}}, {"J4_J8": {}})


@pytest.fixture(scope="module")
def delivery():
    if DEST.exists():
        with (DEST / "reaction_ledger.csv").open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        return read(DEST / "summary.json"), read(DEST / "priority_vmax_groups.json"), rows
    with threadpool_limits(1):
        contents = artifacts(*build())
    return (json.loads(contents["summary.json"]), json.loads(contents["priority_vmax_groups.json"]),
            list(csv.DictReader(io.StringIO(contents["reaction_ledger.csv"]))))


def test_archive_support_exact_initial_and_no_late_factorial(delivery):
    summary, _, rows = delivery
    assert summary["source_identity"]["matching_numeric_cells"] == 770
    assert summary["exact_J1_source_values"] == 55
    assert summary["all_initial_states_exact"] == 114
    assert summary["new_ODE_integrations"] == 0 and not summary["optimizer_run"]
    assert len(summary["replay_sha256"]) == 8
    assert len(rows) == 4400
    for label in LABELS:
        for profile in ("strict", "ultrastrict"):
            windows = summary["cases"][label][profile]
            assert list(windows) == [window_id(*w) for w in (WINDOWS if label == "half_step" else WINDOWS[:2])]
            if label != "half_step":
                delta = summary["matched_deltas_vs_half_step"][label][profile]
                assert list(delta["windows"]) == list(windows)
                assert not delta["sealed_J4_guard"]["pass"]
    assert not summary["coupled_admitted_in_sealed_J4_comparison"]


def test_csv_reconstructs_every_quantity_and_executed_only_closes(delivery):
    summary, _, rows = delivery
    partition = {}
    for r in rows:
        key = tuple(r[k] for k in ("case", "profile", "window", "kind"))
        partition.setdefault(key, []).append(r)
    assert len(partition) == 44
    for (case, profile, tag, kind), rr in partition.items():
        assert len({r["reaction"] for r in rr}) == len(rr) == 100
        for metric in METRICS:
            actual = summary["cases"][case][profile][tag][kind][metric]
            for term in ("production", "consumption", "net"):
                key = f"{term}_mM"
                assert sum(float(r[f"{metric}_{key}"]) for r in rr) == pytest.approx(actual[key], abs=1e-12)
            if kind == "executed":
                assert abs(actual["closure_residual_mM"]) < 1e-5
    j2 = summary["cases"]["half_step"]["ultrastrict"]["J2_J4"]
    assert abs(j2["raw"]["H"]["state_delta_minus_raw_net_mM"]) > .5
    assert abs(j2["executed"]["H"]["closure_residual_mM"]) < 1e-6


def test_transfer_hydrolysis_and_pool_exit_are_distinct(delivery):
    _, _, rows = delivery
    rs = {r["reaction"]: r for r in rows if (r["case"], r["profile"], r["window"], r["kind"]) ==
          ("half_step", "ultrastrict", "J1_J2", "executed")}
    for reaction, coefficients, mechanism in [
        ("VAK", (1, 0, 0), "adenylate_redistribution"),
        ("VNDPK", (-1, -.5, 0), "guanylate_phosphate_transfer"),
        ("VPRPPASe", (-1, -1, 0), "pyrophosphoryl_transfer_to_PRPP"),
        ("VOPLAH", (-1, -.5, 0), "hydrolysis_coupled_biosynthesis"),
        ("VSAM", (-1, -1, -1), "adenylate_moiety_exit_to_SAM"),
        ("VAMPD1", (0, 0, -1), "AMP_exit_no_direct_H_cost"),
    ]:
        row = rs[reaction]
        assert tuple(float(row[f"{q}_coefficient"]) for q in ("ATP", "H", "A")) == coefficients
        assert row["mechanism"] == mechanism


def test_stock_drawdown_and_compensation_are_reconstructed(delivery):
    summary, _, _ = delivery
    base = summary["cases"]["half_step"]["ultrastrict"]
    rib = base["J1_J2"]["stock_ledgers"]["RIB"]
    assert rib["start_mM"] == 1 and rib["end_mM"] < .003
    assert rib["net_drawdown_fraction_of_outflow"] == pytest.approx(1.)
    assert rib["net_terms_mM"]["VRKa"] == pytest.approx(-.9973709, abs=1e-7)
    b13pg = base["J1_J2"]["stock_ledgers"]["B13PG"]
    assert b13pg["net_drawdown_fraction_of_outflow"] > .85
    gtp = base["J15_J46"]["stock_ledgers"]["GTP"]
    assert gtp["net_drawdown_fraction_of_outflow"] > .99
    assert base["J15_J46"]["executed"]["ATP"]["end_mM"] == pytest.approx(1.7828518e-5)
    assert base["J2_J4"]["positive_limiter_loss_extent_mM"]["VPGK"]["B13PG"] > 1.
    for label in LABELS[1:]:
        alt = summary["cases"][label]["ultrastrict"]
        diff = summary["matched_deltas_vs_half_step"][label]["ultrastrict"]["windows"]
        for tag in diff:
            for kind in KINDS:
                d = diff[tag][kind]["ATP"]
                assert d["net_mM"] == pytest.approx(d["production_mM"] - d["consumption_mM"])
                assert d["added_production_offset_by_added_consumption_mM"] == max(
                    0., min(d["production_mM"], d["consumption_mM"]))
                assert d["end_mM"] == pytest.approx(alt[tag][kind]["ATP"]["end_mM"] - base[tag][kind]["ATP"]["end_mM"])


def test_machine_readable_groups_are_vmax_only_and_match_csv(delivery):
    _, groups, rows = delivery
    fixed = groups["fixed"]
    params = read(BASE / "execution_design.json")["cases"]["joint_half"]["parameters"]
    assert fixed["all_Km"] and fixed["exact55_J1"] and fixed["all_latents_and_pH_J1"]
    assert fixed["OPLAH"] == params["vmax_VOPLAH"]
    assert groups["bounds_are_engineering_starts_not_priors"]
    by_id = {g["id"]: g for g in groups["groups"]}
    assert {g["id"] for g in by_id.values() if g["tier"] == "primary"} == {"ribose_investment", "guanylate_transfer"}
    ndpk = by_id["guanylate_transfer"]
    assert ndpk["coordinate"] == "shared_multiplier"
    assert {p["key"] for p in ndpk["parameters"]} == {"vmax_VNDPK", "vmax_VNDPK_rev"}
    assert "ribose_investment" in by_id["purine_PRPP_alternate"]["initial_screen_excludes_groups"]
    reference = {(r["window"], r["reaction"]): r for r in rows
                 if (r["case"], r["profile"], r["kind"]) == ("half_step", "ultrastrict", "executed")}
    for g in by_id.values():
        lo, hi = g["multiplier_bounds"]
        assert 0 < lo < hi == 1
        for p in g["parameters"]:
            assert p["key"].startswith("vmax_") and p["key"] != "vmax_VOPLAH"
            assert p["bounds"] == [p["value"] * lo, p["value"]]
            for tag, support in g["executed_ultrastrict_support"].items():
                assert support == {k: float(reference[tag, p["reaction"]][k]) for k in support}
