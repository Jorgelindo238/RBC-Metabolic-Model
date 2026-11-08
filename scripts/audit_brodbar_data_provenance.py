"""Create an executable provenance contract for the curated Brodbar workbook."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "src" / "Data_Bordbar_et_al_exp.xlsx"
DEFAULT_OUT_DIR = ROOT / "output" / "brodbar_data_provenance_2026_08_11"
INITIAL_COMMIT = "7cfcadcc18c7886fad55f83d39234aed4bc545b6"
PRIMARY_PUBLICATION = {
    "citation": "Bordbar et al., Transfusion 2016;56:852-862",
    "doi": "10.1111/trf.13460",
    "url": "https://pubmed.ncbi.nlm.nih.gov/26749434/",
    "reported_design": "20 SAGM RBC units, quantitative metabolomics over 42 days at 3-4 day intervals",
}
FLUX_REANALYSIS = {
    "citation": "Qi, Roback and Voit, Metabolites 2017;7:12",
    "doi": "10.3390/metabo7020012",
    "url": "https://www.mdpi.com/2218-1989/7/2/12",
    "relevance": "distinguishes measured glycolytic pools from latent pools in flux reconstruction",
}


def _duplicate_pairs(frame: pd.DataFrame) -> list[dict[str, Any]]:
    names = frame.iloc[:, 0].astype(str).str.strip().str.upper().tolist()
    values = frame.iloc[:, 1:].to_numpy(dtype=float)
    pairs = []
    for left in range(len(names)):
        for right in range(left + 1, len(names)):
            if np.array_equal(values[left], values[right]):
                pairs.append({"left": names[left], "right": names[right]})
    return pairs


def _workbook_metadata(path: Path) -> dict[str, Any]:
    workbook = load_workbook(path, read_only=True)
    props = workbook.properties
    return {
        "creator": props.creator,
        "last_modified_by": props.lastModifiedBy,
        "created": props.created.isoformat() if props.created else None,
        "modified": props.modified.isoformat() if props.modified else None,
        "title": props.title,
        "description": props.description,
    }


def _git_blob(ref: str) -> bytes:
    return subprocess.check_output(["git", "show", ref], cwd=ROOT)


def _git_evidence() -> dict[str, Any]:
    initial_bytes = _git_blob(f"{INITIAL_COMMIT}:Data_Brodbar_et_al_exp.xlsx")
    initial = pd.read_excel(BytesIO(initial_bytes))
    history = subprocess.check_output(
        [
            "git",
            "log",
            "--all",
            "--follow",
            "--format=%H%x09%ad%x09%s",
            "--date=iso",
            "--",
            "src/Data_Bordbar_et_al_exp.xlsx",
        ],
        cwd=ROOT,
        text=True,
    ).strip().splitlines()
    return {
        "initial_import_commit": INITIAL_COMMIT,
        "initial_import_pairs": _duplicate_pairs(initial),
        "initial_import_columns": [str(value) for value in initial.columns],
        "history": history,
        "duplicates_present_at_first_repository_import": True,
    }


def build_provenance(path: Path = DATA_PATH) -> dict[str, Any]:
    frame = pd.read_excel(path, engine="openpyxl")
    times = np.asarray([float(value) for value in frame.columns[1:]], dtype=float)
    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    pairs = _duplicate_pairs(frame)
    pair_names = {frozenset((row["left"], row["right"])) for row in pairs}
    expected = {
        frozenset(("B13PG", "B23PG")),
        frozenset(("P2G", "P3G")),
    }
    return {
        "source_file": str(path),
        "sha256": sha256,
        "shape": [int(frame.shape[0]), int(frame.shape[1] - 1)],
        "timepoints_days": times.tolist(),
        "workbook_metadata": _workbook_metadata(path),
        "exact_duplicate_pairs": pairs,
        "expected_duplicate_pairs_present": expected.issubset(pair_names),
        "git_evidence": _git_evidence(),
        "publication_evidence": {
            "likely_primary_time_course": PRIMARY_PUBLICATION,
            "related_flux_reanalysis": FLUX_REANALYSIS,
            "design_match": "The 3-4 day sampling cadence and SAGM storage match Bordbar et al. 2016.",
            "unresolved_mismatch": "The publication reports 42 days, whereas the curated workbook is labeled through day 46.",
        },
        "data_classification": "curated_model_input_not_traceable_raw_measurements",
        "duplicate_interpretation": {
            "B13PG_B23PG": {
                "status": "B13PG is a non-independent proxy for the BPG/2,3-BPG signal",
                "confidence": "high within this repository; source-level analytical annotation still required",
                "observation_policy": "retain B23PG; treat B13PG as latent and never as an independent teacher",
            },
            "P2G_P3G": {
                "status": "consistent with an analytically grouped 2/3-phosphoglycerate feature",
                "confidence": "moderate because the exact source data dictionary is absent",
                "observation_policy": "do not use P2G and P3G as two reaction-specific teachers; retain one descriptive signal only",
            },
        },
        "training_policy": {
            "independent_state_targets_excluded": ["B13PG", "P2G"],
            "reaction_level_teachers_excluded": ["B13PG", "P2G", "P3G"],
            "representative_descriptive_rows": ["B23PG", "P3G"],
            "raw_rows_preserved": True,
        },
        "resolution": "duplicates classified and quarantined; exact upstream raw-table lineage remains unresolved",
    }


def run_audit(*, path: Path, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = build_provenance(path)
    payload.update(
        {
            "contract_type": "brodbar_curated_data_provenance",
            "contract_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    (out_dir / "provenance.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    report = [
        "# Brodbar curated-data provenance audit",
        "",
        "## Finding",
        "",
        "The local workbook is a curated model-input table, not a traceable export of raw replicate measurements.",
        "",
        f"- Workbook SHA-256: `{payload['sha256']}`.",
        f"- Rows x time points: `{payload['shape'][0]} x {payload['shape'][1]}`.",
        f"- Exact duplicated pairs: `{', '.join(row['left'] + '/' + row['right'] for row in payload['exact_duplicate_pairs'])}`.",
        "- Both duplicate pairs were already present at the first repository import; they were not introduced by recent FLA work.",
        "- Sampling cadence is compatible with Bordbar et al. 2016, but the local day-46 endpoint conflicts with the reported 42-day design.",
        "",
        "## Observation contract",
        "",
        "- B13PG is latent; B23PG is the retained BPG observation.",
        "- P2G and P3G must not be used as two independent reaction-specific teachers. P3G may remain as one descriptive representative of the grouped signal.",
        "- Source-level analytical annotation and replicate data are still required before publication.",
        "",
        "## Sources",
        "",
        f"- [{PRIMARY_PUBLICATION['citation']}]({PRIMARY_PUBLICATION['url']})",
        f"- [{FLUX_REANALYSIS['citation']}]({FLUX_REANALYSIS['url']})",
    ]
    (out_dir / "provenance_report.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"classification": payload["data_classification"], "report": str(out_dir / "provenance_report.md")}, indent=2))
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA_PATH)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_audit(path=args.data, out_dir=args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
