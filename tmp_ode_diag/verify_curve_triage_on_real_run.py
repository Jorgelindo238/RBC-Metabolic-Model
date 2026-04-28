"""Quick verification that curve_triage produces the right verdict when
given the per-case calibration_report.json from the real autonomous campaign run.
"""
import json
from pathlib import Path
from services.robocop.curve_triage import triage_calibration_report

run_dir = Path("Simulations/brodbar/autoresearch/20260427_192029_auto_core_upstream_probe_1777332024854711700")
for case in run_dir.iterdir():
    if not case.is_dir():
        continue
    rep_path = case / "calibration_report.json"
    if not rep_path.exists():
        continue
    report = json.loads(rep_path.read_text())
    v = triage_calibration_report(report)
    d = v.to_dict() if hasattr(v, "to_dict") else v.__dict__
    print(f"=== {case.name} (final_loss={report.get('final_loss'):.4f}) ===")
    print(f"  verdict:                {d.get('verdict')}")
    print(f"  protected_anchor_status:{d.get('protected_anchor_status')}")
    print(f"  atp_status: {d.get('atp_status')}  amp_status: {d.get('amp_status')}  adp_status: {d.get('adp_status')}  b23pg_status: {d.get('b23pg_status')}")
    print(f"  amp_nrmse:  {d.get('amp_nrmse')}")
    triggers = d.get("discard_triggers") or []
    print(f"  discard_triggers ({len(triggers)}):")
    for t in triggers:
        print(f"    - {t}")
    print()
