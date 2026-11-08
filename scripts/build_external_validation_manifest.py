"""Build a conservative observed-target manifest for Bardyn and Michel data."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DEFAULT_OUT_DIR = ROOT / "output" / "external_validation_manifest"
DATASETS = {
    "bardyn_control": ROOT / "tests" / "bardyn_control_standardized.csv",
    "bardyn_supplemented": ROOT / "tests" / "bardyn_supplemented_standardized.csv",
    "michel": ROOT / "tests" / "donnees_michel_standardized.csv",
}
ROLES = {
    "bardyn_control": "external_validation",
    "bardyn_supplemented": "intervention_validation",
    "michel": "external_validation",
}
PURINE_TARGETS = {
    "ATP",
    "ADP",
    "AMP",
    "IMP",
    "ADE",
    "EADE",
    "ADO",
    "EADO",
    "INO",
    "EINO",
    "HYPX",
    "EHYPX",
    "GMP",
    "PRPP",
}
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fla_validation_v2 import TargetDataContract, validate_target_contracts  # noqa: E402


def classify_series(values: Sequence[float], *, placeholder_policy: bool) -> str:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or array.size < 2 or not np.all(np.isfinite(array)):
        return "excluded_missing_or_nonfinite"
    if placeholder_policy and np.allclose(array, 1.0, rtol=0.0, atol=1e-12):
        return "excluded_constant_one_placeholder"
    return "observed"


def _dataset_rows(label: str, path: Path) -> tuple[list[dict[str, Any]], list[TargetDataContract]]:
    frame = pd.read_csv(path)
    if "Metabolite" not in frame:
        raise RuntimeError(f"{path} has no Metabolite column")
    time_columns = [column for column in frame.columns if column != "Metabolite"]
    times = np.asarray([float(column) for column in time_columns], dtype=float)
    placeholder_policy = label.startswith("bardyn_")
    rows: list[dict[str, Any]] = []
    contracts: list[TargetDataContract] = []
    for _, source in frame.iterrows():
        target = str(source["Metabolite"]).strip().upper()
        values = source[time_columns].to_numpy(dtype=float)
        status = classify_series(values, placeholder_policy=placeholder_policy)
        row = {
            "dataset": label,
            "role": ROLES[label],
            "target": target,
            "status": status,
            "is_purine_target": target in PURINE_TARGETS,
            "time_start_day": float(times[0]),
            "time_end_day": float(times[-1]),
            "timepoint_count": int(times.size),
            "minimum": float(np.min(values)) if np.all(np.isfinite(values)) else None,
            "maximum": float(np.max(values)) if np.all(np.isfinite(values)) else None,
            "source_path": str(path.resolve()),
        }
        rows.append(row)
        if status == "observed":
            contracts.append(
                TargetDataContract(
                    target=target,
                    dataset=label,
                    compartment="extracellular" if target.startswith("E") else "intracellular",
                    quantity_basis="concentration",
                    normalization="standardized source value; absolute cross-study scale not assumed",
                    time_unit="day",
                    volume_factor_source="not reported; no cross-compartment sum allowed",
                    interpolation_policy="measured endpoints for primary integrated scores",
                    uncertainty_status="replicate uncertainty not present in standardized CSV",
                    replicate_count=None,
                    role=ROLES[label],
                )
            )
    return rows, contracts


def run(*, out_dir: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    contracts: list[TargetDataContract] = []
    for label, path in DATASETS.items():
        local_rows, local_contracts = _dataset_rows(label, path)
        rows.extend(local_rows)
        contracts.extend(local_contracts)
    valid_contracts, contract_failures = validate_target_contracts(contracts)
    frame = pd.DataFrame(rows)
    summary_rows = []
    purine_availability: dict[str, list[str]] = {}
    for label in DATASETS:
        local = frame.loc[frame["dataset"] == label]
        observed = local.loc[local["status"] == "observed"]
        purines = sorted(observed.loc[observed["is_purine_target"], "target"].tolist())
        purine_availability[label] = purines
        summary_rows.append(
            {
                "dataset": label,
                "role": ROLES[label],
                "row_count": int(len(local)),
                "observed_target_count": int(len(observed)),
                "excluded_placeholder_count": int(
                    np.sum(local["status"] == "excluded_constant_one_placeholder")
                ),
                "purine_targets": ",".join(purines),
            }
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out_dir / "target_provenance.csv", index=False)
    pd.DataFrame(summary_rows).to_csv(out_dir / "dataset_summary.csv", index=False)
    payload = {
        "contract_type": "external_validation_target_manifest",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "training_dataset": "brodbar",
        "datasets": summary_rows,
        "purine_availability": purine_availability,
        "target_contracts_valid": valid_contracts,
        "target_contract_failures": list(contract_failures),
        "placeholder_rule": (
            "Bardyn rows equal to exactly 1.0 at every time are conservatively excluded; "
            "the standardized files do not carry an explicit missing-value flag."
        ),
        "leakage_rule": (
            "Bardyn control and Michel outcomes remain unavailable to fitting; Bardyn supplemented "
            "is reserved for intervention validation."
        ),
        "decision": (
            "external purine validation may use ATP, ADP, AMP, and HYPX only; APRT ownership "
            "cannot be externally identified from the currently standardized Bardyn/Michel panels"
        ),
        "artifact_paths": {
            "summary": str(out_dir / "summary.json"),
            "report": str(out_dir / "decision_report.md"),
            "provenance": str(out_dir / "target_provenance.csv"),
            "dataset_summary": str(out_dir / "dataset_summary.csv"),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    report = [
        "# External validation manifest",
        "",
        "| Dataset | Frozen role | Observed targets | Excluded constant-one rows | Purine targets |",
        "|---|---|---:|---:|---|",
    ]
    for row in summary_rows:
        report.append(
            f"| {row['dataset']} | {row['role']} | {row['observed_target_count']} | "
            f"{row['excluded_placeholder_count']} | {row['purine_targets'] or 'none'} |"
        )
    report.extend(
        [
            "",
            payload["placeholder_rule"],
            "",
            payload["decision"],
            "",
            "Absolute cross-study concentration comparisons require a documented normalization/initialization map. Until then, validation uses within-dataset trajectories and endpoints.",
        ]
    )
    (out_dir / "decision_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps({"datasets": summary_rows, "decision": payload["decision"]}, indent=2))
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)
    run(out_dir=args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
