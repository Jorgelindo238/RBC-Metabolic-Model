"""Compare recent Brodbar FLA diagnostic candidates.

The script reads summary JSON files produced by the FLA runners and builds a
compact decision table plus a few comparison plots for the current candidate
set.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "output" / "fla_candidate_comparison"

DEFAULT_CANDIDATES = (
    {
        "label": "VEGLC gate seed",
        "summary": ROOT / "Simulations" / "brodbar" / "hermes" / "glucose_utilization_vhk_atp_46d_n16_upper5" / "summary.json",
        "section": "seed",
    },
    {
        "label": "VHK only upper5",
        "summary": ROOT / "Simulations" / "brodbar" / "hermes" / "glucose_utilization_vhk_only_46d_n14_upper5" / "summary.json",
        "section": "best_candidate",
    },
    {
        "label": "VHK + km_ATP_HK",
        "summary": ROOT / "Simulations" / "brodbar" / "hermes" / "glucose_utilization_vhk_atp_46d_n16_upper5" / "summary.json",
        "section": "best_candidate",
    },
    {
        "label": "VHK + VPGI/VPFK",
        "summary": ROOT / "Simulations" / "brodbar" / "hermes" / "glucose_utilization_vhk_pgi_pfk_46d_n14_upper5" / "summary.json",
        "section": "best_candidate",
    },
    {
        "label": "VELAC/VLDH",
        "summary": ROOT / "Simulations" / "brodbar" / "hermes" / "lactate_focused_velac_vldh_46d_n36" / "summary.json",
        "section": "best_candidate",
    },
    {
        "label": "VEGLC cap/feedback",
        "summary": ROOT
        / "Simulations"
        / "brodbar"
        / "hermes"
        / "veglc_import_feedback_vhk_atp_seed_46d_n28"
        / "summary.json",
        "section": "best_candidate",
    },
)


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return [_jsonable(v) for v in value.tolist()]
    if isinstance(value, (np.integer, np.floating)):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Path):
        return str(value)
    return value


def _load_summary(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _metric(payload: Mapping[str, Any], metabolite: str, field: str) -> float:
    return float(payload["metrics"][metabolite][field])


def _flux(payload: Mapping[str, Any], reaction: str) -> float:
    details = payload.get("teacher_flux_details", {})
    if not isinstance(details, Mapping) or reaction not in details:
        return float("nan")
    return float(details[reaction]["nrmse"])


def build_rows() -> list[dict[str, Any]]:
    rows = []
    for candidate in DEFAULT_CANDIDATES:
        summary_path = Path(candidate["summary"])
        if not summary_path.exists():
            continue
        summary = _load_summary(summary_path)
        section = str(candidate["section"])
        payload = summary[section]
        row = {
            "label": str(candidate["label"]),
            "summary_path": str(summary_path.relative_to(ROOT)),
            "section": section,
            "accepted": bool(summary.get("accepted")) if section == "best_candidate" else False,
            "loss": float(payload.get("loss", np.nan)),
            "EGLC_nrmse": _metric(payload, "EGLC", "nrmse"),
            "EGLC_endpoint_error": _metric(payload, "EGLC", "endpoint_error"),
            "ELAC_nrmse": _metric(payload, "ELAC", "nrmse"),
            "ELAC_endpoint_error": _metric(payload, "ELAC", "endpoint_error"),
            "GLC_nrmse": _metric(payload, "GLC", "nrmse"),
            "GLC_endpoint_error": _metric(payload, "GLC", "endpoint_error"),
            "LAC_nrmse": _metric(payload, "LAC", "nrmse"),
            "LAC_endpoint_error": _metric(payload, "LAC", "endpoint_error"),
            "PYR_nrmse": _metric(payload, "PYR", "nrmse"),
            "PYR_endpoint_error": _metric(payload, "PYR", "endpoint_error"),
            "VEGLC_flux_nrmse": _flux(payload, "VEGLC"),
            "VELAC_flux_nrmse": _flux(payload, "VELAC"),
            "VLDH_flux_nrmse": _flux(payload, "VLDH"),
            "params_json": json.dumps(payload.get("params", {}), sort_keys=True),
        }
        for metabolite in ("EGLC", "ELAC", "GLC", "LAC", "PYR"):
            row[f"{metabolite}_final"] = float(payload["sim_final"][metabolite])
            row[f"{metabolite}_exp_final"] = float(payload["exp_final"][metabolite])
        rows.append(row)
    return rows


def _plot(rows: list[dict[str, Any]], out_path: Path) -> None:
    labels = [row["label"] for row in rows]
    x = np.arange(len(labels))
    fig, axes = plt.subplots(2, 2, figsize=(15, 9), constrained_layout=True)

    ax = axes[0, 0]
    ax.bar(x, [row["GLC_nrmse"] for row in rows], color="#2563eb")
    ax.set_title("Internal GLC nRMSE")
    ax.set_xticks(x, labels, rotation=25, ha="right")
    ax.set_ylabel("nRMSE")
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[0, 1]
    width = 0.35
    ax.bar(x - width / 2, [row["ELAC_nrmse"] for row in rows], width=width, color="#0f766e", label="ELAC")
    ax.bar(x + width / 2, [row["LAC_nrmse"] for row in rows], width=width, color="#f59e0b", label="LAC")
    ax.set_title("Lactate concentration nRMSE")
    ax.set_xticks(x, labels, rotation=25, ha="right")
    ax.set_ylabel("nRMSE")
    ax.legend(frameon=False)
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1, 0]
    flux_width = 0.25
    ax.bar(x - flux_width, [row["VEGLC_flux_nrmse"] for row in rows], width=flux_width, color="#2563eb", label="VEGLC")
    ax.bar(x, [row["VELAC_flux_nrmse"] for row in rows], width=flux_width, color="#7c3aed", label="VELAC")
    ax.bar(x + flux_width, [row["VLDH_flux_nrmse"] for row in rows], width=flux_width, color="#db2777", label="VLDH")
    ax.set_title("Teacher flux nRMSE")
    ax.set_xticks(x, labels, rotation=25, ha="right")
    ax.set_ylabel("nRMSE")
    ax.legend(frameon=False)
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1, 1]
    ax.bar(x, [row["EGLC_endpoint_error"] for row in rows], color="#16a34a")
    ax.set_title("EGLC endpoint error")
    ax.set_xticks(x, labels, rotation=25, ha="right")
    ax.set_ylabel("relative error")
    ax.grid(True, axis="y", alpha=0.25)

    fig.suptitle("Recent Brodbar FLA diagnostic candidates")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare recent FLA candidates")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    csv_path = out_dir / "fla_candidate_comparison.csv"
    png_path = out_dir / "fla_candidate_comparison.png"
    manifest_path = out_dir / "manifest.json"
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    _plot(rows, png_path)
    manifest = {
        "contract_type": "fla_candidate_comparison",
        "contract_version": 1,
        "rows": rows,
        "artifact_paths": {
            "csv": str(csv_path),
            "plot": str(png_path),
            "manifest": str(manifest_path),
        },
    }
    manifest_path.write_text(json.dumps(_jsonable(manifest), indent=2), encoding="utf-8")
    print(json.dumps(_jsonable(manifest), indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
