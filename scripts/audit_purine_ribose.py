"""Sealed-trajectory purine/ribose budgets and pinned GEM projection. No ODE."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

from audit_glucose_carbon import ROOT, CASES, DAYS, sha, verify_manifest, save_csv

sys.path.insert(0, str(ROOT / "src"))
from rbc_gem_audit import EXTERNAL_POOLS, pool_mapping, project_gem

GEM_DIR = ROOT / "output/rbc_gem_network_audit_2026_10_06"
POOLS = ("INO", "EINO", "ADO", "EADO", "HYPX", "EHYPX", "RIB", "R1P", "R5P", "PRPP",
         "IMP", "ADESUC", "ATP", "ADP", "AMP", "GTP", "GDP", "GMP", "GUA", "XMP")
MATCHES = {
    "VPNPase1": ["PUNP5"], "VRKb": ["PPM"], "VRKa": ["RBK"],
    "VPRPPASe": ["PRPPS"], "VHGPRT1": ["HXPRT"], "VHGPRT2": ["GUAPRT"],
    "Vnucleo2": ["NTDIMP"], "VADSS": ["ADSS"], "VADSL": ["ADSL1"],
    "VNDPK": ["NDPK1"], "VEINO": ["INSt"], "Vnucleo_GMP": ["NTDGMP", "PUNP3"],
}
# Independent identities, transcribed explicitly rather than derived from A.
IDENTITIES = {
    "INO": {"VADA":1, "Vnucleo2":1, "VEINO":-1, "VPNPase1":-1},
    "R1P": {"VPNPase1":1, "Vnucleo_GMP":1, "VRKb":-1},
    "R5P": {"VR5PI":1, "VRKb":1, "VRKa":1, "VTKL1":-1, "VPRPPASe":-1},
    "RIB": {"VRKa":-1},
    "PRPP": {"VPRPPASe":1, "VAPRT":-1, "VHGPRT1":-1, "VHGPRT2":-1},
    "IMP": {"VHGPRT1":1, "VAMPD1":1, "VADSS":-1, "VIMPH":-1, "Vnucleo2":-1},
    "ADESUC": {"VADSS":1, "VADSL":-1},
    "GTP": {"VNDPK":1, "VADSS":-1},
}


def gross_integrals(rates, weights):
    if rates.ndim != 2 or weights.shape != (rates.shape[1],):
        raise ValueError("aligned rates and weights required")
    if not np.isfinite(rates).all() or not np.isfinite(weights).all() or np.any(weights < 0):
        raise ValueError("finite rates and nonnegative weights required")
    return rates @ weights, np.maximum(rates,0) @ weights, np.maximum(-rates,0) @ weights


def gem_comparison(names, reactions, matrix, h):
    path = GEM_DIR / "github/1.3.0/model/RBC-GEM.json"
    receipts = json.loads((GEM_DIR / "retrieval_receipts.json").read_text())
    receipt = next(r for r in receipts if r["file"] == "github/1.3.0/model/RBC-GEM.json")
    if sha(path) != receipt["sha256"] or not receipt["git_blob_verified"]:
        raise ValueError("GEM differs from pinned retrieval")
    model = json.loads(path.read_text())
    lookup = {r["id"]:r for r in model["reactions"]}
    inverse = {v:k for k,v in pool_mapping(model).items()}
    volumes = np.array([1-h if p in EXTERNAL_POOLS else h for p in names])
    rows = []
    for reaction, ids in MATCHES.items():
        combined = {}
        for gid in ids:
            for p,c in lookup[gid]["metabolites"].items():
                combined[p] = combined.get(p,0)+c
        combined = {p:c for p,c in combined.items() if c}
        projected, unmodeled, currency = project_gem({"metabolites":combined}, inverse)
        j = reactions.index(reaction)
        native = matrix[:,j]*volumes/h
        target = np.array([projected.get(p,0) for p in names])
        rows.append(dict(reaction=reaction, gem_ids=ids, projected_match=bool(
            not unmodeled and np.allclose(native,target,rtol=0,atol=1e-12)),
            unmodeled=unmodeled, omitted_currency=currency, full_gem_stoichiometry=combined,
            bounds={gid:[lookup[gid]["lower_bound"],lookup[gid]["upper_bound"]] for gid in ids},
            native_stoichiometry={p:float(c) for p,c in zip(names,native) if abs(c)>1e-12}))
    return rows, receipt


def run(out):
    if out.exists():
        raise ValueError("fresh output required")
    parent = ROOT / "output/glucose_carbon_audit_2026_11_11"
    verify_manifest(parent)
    previous = json.loads((parent/"summary.json").read_text())
    for rel,digest in previous["input_sha256"].items():
        if sha(ROOT/rel) != digest:
            raise ValueError(f"source changed: {rel}")
    h = previous["hematocrit"]
    levels, ledger, accounts, comparisons = [], [], [], []
    closures, independent, matrices = [], [], []
    input_hashes = dict(previous["input_sha256"])
    for p in (Path(__file__), ROOT/"scripts/audit_glucose_carbon.py", ROOT/"src/rbc_gem_audit.py",
              ROOT/"src/equadiff_brodbar.py", GEM_DIR/"retrieval_receipts.json",
              GEM_DIR/"github/1.3.0/model/RBC-GEM.json", parent/"manifest.json"):
        input_hashes[p.relative_to(ROOT).as_posix()] = sha(p)
    for case,base in CASES.items():
        for profile in ("strict","ultrastrict"):
            path = ROOT/base/"joint"/profile/"flux_evidence.npz"
            result_path = path.parent/"result.json"
            if not json.loads(result_path.read_text())["numerical_pass"]:
                raise ValueError("quarantined trajectory")
            input_hashes[result_path.relative_to(ROOT).as_posix()] = sha(result_path)
            with np.load(path) as a:
                names, reactions = a["pool_names"].tolist(), a["reactions"].tolist()
                matrix, time, x = a["matrix"], a["time"], a["states"]
                rates, weights, intervals = a["q8_executed_rates"], a["q8_weights"], a["q8_intervals"]
            if not matrices:
                comparisons, gem_receipt = gem_comparison(names,reactions,matrix,h)
            elif not np.array_equal(matrix,matrices[0]):
                raise ValueError("case matrices differ")
            matrices.append(matrix)
            for day in DAYS:
                ids = np.flatnonzero(time==day)
                if len(ids)!=1:
                    raise ValueError("exact archived day required")
                for p in POOLS:
                    c = float(x[names.index(p),ids[0]])
                    levels.append(dict(case=case,profile=profile,day=day,pool=p,mM=c,
                        mmol_per_L_bag=c*(1-h if p in EXTERNAL_POOLS else h)))
            for start,end in ((1,4),(4,8),(8,11),(11,15),(1,15)):
                mask = (intervals>=start-1)&(intervals<end-1)
                net,forward,reverse = gross_integrals(rates[:,mask],weights[mask])
                v = dict(zip(reactions,net))
                k0,k1 = np.searchsorted(time,[start,end])
                common = dict(case=case,profile=profile,start=start,end=end)
                for p in POOLS:
                    i = names.index(p)
                    volume = 1-h if p in EXTERNAL_POOLS else h
                    delta = volume*(x[i,k1]-x[i,k0])
                    predicted = volume*(matrix[i]@net)
                    closures.append(float(abs(delta-predicted)))
                    for j in np.flatnonzero(matrix[i]):
                        c = volume*matrix[i,j]
                        ledger.append(dict(**common,pool=p,reaction=reactions[j],net_mmol_per_L_bag=c*net[j],
                            production_mmol_per_L_bag=max(c,0)*forward[j]+max(-c,0)*reverse[j],
                            consumption_mmol_per_L_bag=max(-c,0)*forward[j]+max(c,0)*reverse[j]))
                    if p in IDENTITIES:
                        explicit = h*sum(c*v[r] for r,c in IDENTITIES[p].items())
                        independent.append(float(abs(delta-explicit)))
                    accounts.append(dict(**common,quantity="delta_"+p,mmol_per_L_bag=float(delta)))
                # Signed net decomposition, not molecular lineage or closed-cycle throughput.
                values = {"INO_import_net":-h*v["VEINO"],
                          "INO_from_ADA":h*v["VADA"], "INO_from_IMP":h*v["Vnucleo2"],
                          "INO_to_R1P":h*v["VPNPase1"],
                          "R1P_from_GMP":h*v["Vnucleo_GMP"], "R1P_to_R5P":h*v["VRKb"],
                          "R5P_from_RIB":h*v["VRKa"], "R5P_from_RU5P":h*v["VR5PI"],
                          "R5P_to_PRPP":h*v["VPRPPASe"], "R5P_to_TKL1_net":h*v["VTKL1"],
                          "PRPP_to_HGPRT1":h*v["VHGPRT1"], "PRPP_to_HGPRT2":h*v["VHGPRT2"],
                          "PRPP_to_APRT":h*v["VAPRT"],
                          "IMP_from_AMPD":h*v["VAMPD1"], "IMP_to_ADSS":h*v["VADSS"],
                          "ADESUC_to_AMP":h*v["VADSL"],
                          "ATP_to_ADP_RK":h*v["VRKa"], "ATP_to_AMP_PRPPS":h*v["VPRPPASe"],
                          "ATP_to_ADP_NDPK_net":h*v["VNDPK"], "GTP_to_GDP_ADSS":h*v["VADSS"],
                          "NDPK_minus_ADSS_GTP_storage":h*(v["VNDPK"]-v["VADSS"]),
                          "RK_PRPPS_NDPK_net_ATP_consumed":h*(v["VRKa"]+v["VPRPPASe"]+v["VNDPK"]),
                          "RK_PRPPS_ADSS_phosphoryl_demand":h*(v["VRKa"]+2*v["VPRPPASe"]+v["VADSS"])}
                for quantity,value in values.items():
                    accounts.append(dict(**common,quantity=quantity,mmol_per_L_bag=float(value)))
    passed = max(closures)<1e-7 and max(independent)<1e-7 and all(r["projected_match"] for r in comparisons)
    summary = dict(passed=passed,new_integrations=0,parameters_changed=False,production_promoted=False,
        balance_checks=len(closures),max_closure_error=max(closures),independent_identity_checks=len(independent),
        max_identity_error=max(independent),gem_projected_matches=sum(r["projected_match"] for r in comparisons),
        gem_retrieval=gem_receipt,hematocrit=h,hematocrit_status=previous["hematocrit_status"],
        units="mmol/L bag; phosphoryl demand in mmol bond equivalents/L bag, not free energy",
        limitations=["Gross means sign-separated NET reaction rates, not forward/reverse molecular exchange.",
                    "Source terms are local bookkeeping, not ultimate carbon lineage.",
                    "GEM projected equivalence does not validate native kinetics or omitted phosphate balances.",
                    "ADSS GTP cost is not added to NDPK ATP cost as a second ATP expense."],input_sha256=input_hashes)
    out.mkdir(parents=True)
    for name,rows in (("levels",levels),("ledger",ledger),("accounts",accounts)):
        save_csv(out/f"{name}.csv",rows)
    (out/"gem_comparison.json").write_text(json.dumps(comparisons,indent=2),encoding="utf-8")
    (out/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    (out/"manifest.json").write_text(json.dumps({p.name:sha(p) for p in out.iterdir()},indent=2))
    if not passed:
        raise ValueError("audit failed; retain evidence")
    print(json.dumps({k:v for k,v in summary.items() if k not in ("input_sha256","gem_retrieval")},indent=2))


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    run(p.parse_args().out.resolve())
