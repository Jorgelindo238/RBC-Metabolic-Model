"""Independent arithmetic checks for the saved-flux F6P/B23PG/PEP audit."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def verify(out):
    checks = 0
    def require(condition, message):
        nonlocal checks
        checks += 1
        if not condition:
            raise ValueError(message)
    def near(actual, expected, message):
        require(bool(np.isclose(actual, expected, atol=1e-11, rtol=1e-11)), message)
    def table(name):
        with (out/(name+".csv")).open(newline="", encoding="utf-8") as stream:
            return list(csv.DictReader(stream))
    manifest = json.loads((out/"manifest.json").read_text())
    for key, base in (("input_sha256", ROOT), ("output_sha256", out)):
        for name, digest in manifest[key].items():
            with (base/name).open("rb") as stream:
                require(hashlib.file_digest(stream, "sha256").hexdigest() == digest, "hash:"+name)
    contract = json.loads((out/"execution_contract.json").read_text())
    config = contract["config"]
    parent = ROOT/config["parent_archive"]
    f = json.loads((parent/"execution_design.json").read_text())
    s = json.loads((parent/"summary.json").read_text())
    obs = json.loads((parent/"observations.json").read_text())
    base = ROOT/f["parent_design"]["source_archive"]
    summary = json.loads((out/"summary.json").read_text())
    for key in ("new_ODE_integrations", "new_optimizer_calls"):
        require(summary[key] == 0 and contract[key] == 0, "unexpected new simulation/fitting")
    for key in ("parameters_changed", "initial_states_changed", "source_values_changed", "production_promoted"):
        require(summary[key] is False, "changed scope:"+key)
    require(contract["capacity_parameters"]["protected"] == s["selected"]["parameters"], "candidate kinetics changed")
    pool_rows, reaction_rows, loss_rows = table("pool_budgets"), table("reaction_budgets"), table("limiter_attribution")
    guard_predictions = {}
    for case in ("control", "protected"):
        for profile in config["profiles"]:
            path = (base/"J1_J10"/f"glut_real_candidate_{profile}"/"replay.npz" if case == "control" else
                parent/"audits"/(s["selected"]["label"]+"_J10")/"J1_J10"/f"glut_real_candidate_{profile}"/"replay.npz")
            with np.load(path) as a:
                names, reactions = a["pool_names"].tolist(), a["reactions"].tolist()
                require(np.array_equal(a["initial"], f["initial"]), "J1 changed")
                if profile == "ultrastrict":
                    sample = [int(np.flatnonzero(a["time"] == t)[0]) for t in f["design"]["training_times"]]
                    guard_predictions[case] = {pool: a["states"][names.index(pool), sample]
                        for pool in f["design"]["pools"]+["F6P", "B23PG"]}
                for row in (r for r in pool_rows if r["case"] == case and r["profile"] == profile):
                    start, end = float(row["start_day"]), float(row["end_day"])
                    i = names.index(row["pool"])
                    mask = (a["q8_nodes"] > start) & (a["q8_nodes"] < end)
                    signed = a["matrix"][i, :, None]*a["q8_executed_rates"][:, mask]
                    production = sum(float(np.dot(np.maximum(v, 0), a["q8_weights"][mask])) for v in signed)
                    consumption = sum(float(np.dot(np.maximum(-v, 0), a["q8_weights"][mask])) for v in signed)
                    near(production, float(row["production_mM"]), "signed production")
                    near(consumption, float(row["consumption_mM"]), "signed consumption")
                    near(production-consumption, float(row["executed_net_mM"]), "signed net")
                    j, k = (int(np.flatnonzero(a["time"] == t)[0]) for t in (start, end))
                    change = a["states"][i, k]-a["states"][i, j]
                    near(change, float(row["state_change_mM"]), "endpoint change")
                    near(change-(production-consumption), float(row["closure_residual_mM"]), "closure receipt")
                for row in (r for r in reaction_rows if r["case"] == case and r["profile"] == profile):
                    i, j = names.index(row["pool"]), reactions.index(row["reaction"])
                    mask = (a["q8_nodes"] > float(row["start_day"])) & (a["q8_nodes"] < float(row["end_day"]))
                    for kind in ("raw", "executed"):
                        amount = a["matrix"][i, j]*np.dot(a[f"q8_{kind}_rates"][j, mask], a["q8_weights"][mask])
                        near(amount, float(row[kind+"_mM"]), "reaction integral")
                    near(float(row["executed_mM"])-float(row["raw_mM"]), float(row["modifier_mM"]), "limiter modifier")
                for order in (4, 8):
                    for reaction in config["limiter_reactions"]:
                        j = reactions.index(reaction)
                        raw = a[f"q{order}_raw_rates"][j]
                        executed = a[f"q{order}_executed_rates"][j]
                        column = a["matrix"][:, j]
                        consuming = ((column[:, None] < 0) & (raw[None, :] > 0)) | ((column[:, None] > 0) & (raw[None, :] < 0))
                        availability = np.clip(a[f"q{order}_states"][:len(names)]/.001, 0, 1)
                        factor = np.where(consuming, availability, 1.).min(axis=0)
                        active = consuming & (factor[None, :] < 1) & np.isclose(availability, factor[None, :], rtol=1e-10, atol=1e-12)
                        count = active.sum(axis=0)
                        splits = np.divide(active.astype(float), count, out=np.zeros_like(availability), where=count > 0)
                        for row in (r for r in loss_rows if r["case"] == case and r["profile"] == profile
                                    and int(r["order"]) == order and r["reaction"] == reaction):
                            _, start, end = next(w for w in config["windows"] if w[0] == row["window"])
                            mask = (a[f"q{order}_nodes"] > start) & (a[f"q{order}_nodes"] < end)
                            w = a[f"q{order}_weights"][mask]
                            total = np.dot(np.abs(raw-executed)[mask], w)
                            amount = np.dot((splits[names.index(row["limiting_pool"])]*np.abs(raw-executed))[mask], w)
                            near(total, float(row["total_absolute_rate_loss_mM"]), "absolute execution loss")
                            near(amount, float(row["loss_mM"]), "minimum-consumer allocation")
    for name, keys, quantities in (("reaction", ("pool", "reaction", "window"), ("raw_mM", "executed_mM", "modifier_mM")),
                                   ("pool", ("pool", "window"), ("state_change_mM", "executed_net_mM", "raw_net_mM"))):
        rows = reaction_rows if name == "reaction" else pool_rows
        for delta in table(name+"_deltas"):
            members = [r for r in rows if r["profile"] == "ultrastrict" and all(r[k] == delta[k] for k in keys)]
            require(len(members) == 2, "comparison alignment")
            base_row = next(r for r in members if r["case"] == "control")
            new_row = next(r for r in members if r["case"] == "protected")
            for key in quantities:
                near(float(new_row[key])-float(base_row[key]), float(delta[key+"_delta"]), "difference accounting")
    proposal = json.loads((out/"proposed_guard_contract.json").read_text())
    require(proposal["status"].startswith("proposal_only"), "guards retroactively activated")
    require(proposal["future_likelihood_channels"] == f["design"]["pools"]+["F6P", "B23PG"], "unexpected guard scope")
    errors = {}
    sample = [obs["time"].index(t) for t in f["design"]["training_times"]]
    for row in proposal["RMSE_guards"]:
        pool = row["pool"]
        target = np.array(obs["values"][pool])[sample]
        before, after = (guard_predictions[c][pool]-target for c in ("control", "protected"))
        errors[pool] = (before, after)
        base_rmse, new_rmse = (float(np.linalg.norm(v)/np.sqrt(len(v))) for v in (before, after))
        allowance = f["design"]["guard_numerical_atol_mM"]+f["design"]["guard_numerical_rtol"]*base_rmse
        near(row["reference_RMSE_mM"], base_rmse, "proposed reference RMSE")
        near(row["candidate_RMSE_mM"], new_rmse, "proposed candidate RMSE")
        near(row["fit_limit_mM"], base_rmse+f["design"]["fitting_allowance_fraction"]*allowance, "proposed fitting allowance")
        near(row["audit_limit_mM"], base_rmse+allowance, "proposed audit allowance")
        require(row["candidate_pass"] == (new_rmse <= base_rmse+allowance), "proposed guard verdict")
    for row in proposal["pointwise_guards"]:
        index = f["design"]["training_times"].index(row["day"])
        before, after = (abs(v[index]) for v in errors[row["pool"]])
        allowance = f["design"]["guard_numerical_atol_mM"]+f["design"]["guard_numerical_rtol"]*before
        near(row["reference_absolute_error_mM"], before, "pointwise reference")
        near(row["candidate_absolute_error_mM"], after, "pointwise candidate")
        near(row["fit_limit_mM"], before+f["design"]["fitting_allowance_fraction"]*allowance, "pointwise fitting limit")
        near(row["audit_limit_mM"], before+allowance, "pointwise audit limit")
        require(row["candidate_pass"] == (after <= before+allowance), "pointwise guard verdict")
    for alias, canonical in config["source_aliases"].items():
        require(obs["values"][alias] == obs["values"][canonical], "source alias")
        require(alias not in proposal["future_likelihood_channels"], "double-counted alias")
    for row in table("PFK_capacity_state_split"):
        near(float(row["capacity_at_control_states_mM"])+float(row["state_response_remainder_mM"]),
             float(row["raw_integral_delta_mM"]), "PFK capacity-state accounting")
    return {"verified": True, "checks": checks, "new_ODE_integrations": 0, "new_optimizer_calls": 0,
        "archive_replays_audited": 4, "physiological_validation": False,
        "coverage": "all_exported_pool_reaction_and_limiter_amounts_not_an_independent_ODE_solver"}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--receipt", type=Path)
    args = p.parse_args()
    result = verify(args.archive.resolve())
    if args.receipt:
        if args.receipt.exists():
            raise ValueError("verification receipt already exists")
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
