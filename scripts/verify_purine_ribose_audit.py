"""Independent saved-ledger/state checks without importing the audit runner."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(out, report):
    require(not report.exists(),"fresh receipt required")
    summary=json.loads((out/"summary.json").read_text())
    for rel,digest in json.loads((out/"manifest.json").read_text()).items():
        require(sha(out/rel)==digest,f"modified output {rel}")
    for rel,digest in summary["input_sha256"].items():
        require(sha(ROOT/rel)==digest,f"modified input {rel}")
    with (out/"ledger.csv").open() as f:
        ledger=list(csv.DictReader(f))
    with (out/"accounts.csv").open() as f:
        accounts=list(csv.DictReader(f))
    with (out/"levels.csv").open() as f:
        levels=list(csv.DictReader(f))
    level_lookup={(r["case"],r["profile"],r["day"],r["pool"]):float(r["mmol_per_L_bag"]) for r in levels}
    totals={}
    for r in ledger:
        key=tuple(r[k] for k in ("case","profile","start","end","pool"))
        net,prod,cons=(float(r[k+"_mmol_per_L_bag"]) for k in ("net","production","consumption"))
        require(prod>=0 and cons>=0 and abs(net-prod+cons)<1e-10,"signed ledger inconsistent")
        totals[key]=totals.get(key,0)+net
    errors=[]
    for key,net in totals.items():
        c,p,s,e,pool=key
        delta=level_lookup[c,p,e,pool]-level_lookup[c,p,s,pool]
        errors.append(abs(delta-net))
    require(len(errors)==1000 and max(errors)<1e-7,"pool closure failed")
    lookup={(r["case"],r["profile"],r["start"],r["end"],r["quantity"]):float(r["mmol_per_L_bag"]) for r in accounts}
    linkage_errors=[]
    for key,value in lookup.items():
        c,p,s,e,q=key
        if q != "ATP_to_ADP_NDPK_net":
            continue
        get=lambda name:lookup[c,p,s,e,name]
        linkage_errors.append(abs(value-get("GTP_to_GDP_ADSS")-get("delta_GTP")))
        linkage_errors.append(abs(get("IMP_to_ADSS")-get("ADESUC_to_AMP")-get("delta_ADESUC")))
        linkage_errors.append(abs(get("INO_import_net")+get("delta_EINO")))
    require(len(linkage_errors)==150 and max(linkage_errors)<1e-7,"cycle linkage failed")
    # Reconstruct every reported level directly from source NPZ, independently.
    source_errors=[]
    for rel in summary["input_sha256"]:
        if not rel.endswith("flux_evidence.npz"):
            continue
        path=ROOT/rel
        case={"working_center":"control","balanced_forward_lowered":"ak_only"}.get(path.parents[2].name,path.parents[2].name)
        with np.load(path) as a:
            names=a["pool_names"].tolist()
            for r in levels:
                if (r["case"],r["profile"])!=(case,path.parent.name):
                    continue
                pool=r["pool"]
                k=np.flatnonzero(a["time"]==float(r["day"]))
                require(len(k)==1,"missing exact source day")
                actual=float(a["states"][names.index(pool),k[0]])
                volume=1-summary["hematocrit"] if pool in ("EINO","EADO","EHYPX") else summary["hematocrit"]
                source_errors.append(abs(actual*volume-float(r["mmol_per_L_bag"])))
                require(abs(actual-float(r["mM"]))<1e-12,"phase concentration differs")
    require(len(source_errors)==1000 and max(source_errors)<1e-12,"source levels differ")
    receipt=dict(passed=True,new_integrations=0,ledger_rows=len(ledger),pool_closures=len(errors),
        max_pool_error=max(errors),cycle_identities=len(linkage_errors),max_cycle_error=max(linkage_errors),
        source_level_checks=len(source_errors),max_source_error=max(source_errors),
        scope="Source hashes, signed ledger, archived levels, NDPK/ADSS/INO linkages; GEM comparison is not re-curated",
        audit_manifest_sha256=sha(out/"manifest.json"),verifier_sha256=sha(Path(__file__)))
    report.mkdir(parents=True)
    (report/"verification.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    (report/"manifest.json").write_text(json.dumps({"verification.json":sha(report/"verification.json")},indent=2))
    print(json.dumps(receipt,indent=2))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    a=p.parse_args()
    verify(a.out.resolve(),a.report.resolve())
