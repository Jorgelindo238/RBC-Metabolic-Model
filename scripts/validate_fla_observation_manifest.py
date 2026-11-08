"""Validate custom absolute/relative metabolomics JSON before calibration."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from fla_calibration_observations import validate_collection
from run_glut_only_free_replay import write, sha


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True); p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    if a.out.exists(): raise ValueError("fresh validation output required")
    source = json.loads(a.manifest.read_text(encoding="utf-8"))
    result = validate_collection(source["series"])
    result.update(source_path=str(a.manifest.resolve()), source_sha256=sha(a.manifest))
    a.out.parent.mkdir(parents=True, exist_ok=True); write(a.out, result)
    print(json.dumps({"series": len(result["series"]), "groups": len(result["groups"]), "status": result["status"]}, indent=2))
