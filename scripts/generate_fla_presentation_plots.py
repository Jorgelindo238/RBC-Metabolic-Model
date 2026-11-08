"""Generate presentation plots for Flux Learning Analysis (FLA).

The default run creates Brodbar concentration panels and extracellular
teacher-flux panels. A custom dataset can be passed as JSON with:

{
  "exp_time": [1, 4, ...],
  "exp_data": {"EGLC": [25.3, 24.1, ...], "ELAC": [...]}
}
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
DEFAULT_OUT_DIR = ROOT / "output" / "fla_presentation"
BRODBAR_DATA_PATH = SRC_DIR / "Data_Bordbar_et_al_exp.xlsx"

for path in (str(ROOT), str(SRC_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from extracellular_teacher_flux import (  # noqa: E402
    EXTRACELLULAR_TEACHER_METABOLITES,
    EXTRACELLULAR_TEACHER_FLUX_RULES,
    build_bordbar_extracellular_teacher_flux_dataset,
    build_extracellular_teacher_flux_dataset,
)
from flux_inference import infer_user_fluxes  # noqa: E402
import rbc_stoichiometry as rs  # noqa: E402


TRAINING_REACTIONS = {"VEGLC", "VELAC"}


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


def _normalize_name(name: Any) -> str:
    return str(name).strip().upper()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", str(value).strip().lower()).strip("_")
    return slug or "dataset"


def _load_bordbar() -> tuple[np.ndarray, dict[str, np.ndarray], list[str]]:
    df = pd.read_excel(BRODBAR_DATA_PATH, sheet_name="Sheet1")
    if "Conc / mM" not in df.columns:
        raise ValueError(f"Unsupported Brodbar sheet format: {BRODBAR_DATA_PATH}")
    time_cols = [col for col in df.columns if col != "Conc / mM"]
    time = np.asarray([float(col) for col in time_cols], dtype=float)
    curves: dict[str, np.ndarray] = {}
    order: list[str] = []
    for _, row in df.iterrows():
        name = _normalize_name(row["Conc / mM"])
        if not name:
            continue
        curves[name] = np.asarray([float(row[col]) for col in time_cols], dtype=float)
        order.append(name)
    return time, curves, order


def _load_custom_dataset(path: Path) -> tuple[np.ndarray, dict[str, np.ndarray], list[str], dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    exp_time = payload.get("exp_time") or payload.get("time") or payload.get("timepoints")
    exp_data = payload.get("exp_data") or payload.get("data") or payload.get("metabolites")
    if not isinstance(exp_time, list) or not isinstance(exp_data, dict):
        raise ValueError("Custom JSON must contain exp_time and exp_data fields.")
    time = np.asarray([float(v) for v in exp_time], dtype=float)
    curves: dict[str, np.ndarray] = {}
    order: list[str] = []
    for raw_name, raw_values in exp_data.items():
        name = _normalize_name(raw_name)
        values = np.asarray([float(v) for v in raw_values], dtype=float)
        if values.size != time.size:
            raise ValueError(f"Custom series for {name} does not align with exp_time.")
        curves[name] = values
        order.append(name)
    metadata = {
        "source_path": str(path),
        "label": payload.get("label") or payload.get("active_dataset_label") or Path(path).stem,
    }
    return time, curves, order, metadata


def _load_standardized_csv(path: Path) -> tuple[np.ndarray, dict[str, np.ndarray], list[str], dict[str, Any]]:
    df = pd.read_csv(path)
    if "Metabolite" not in df.columns:
        raise ValueError(f"Standardized CSV must contain a Metabolite column: {path}")
    time_cols = [col for col in df.columns if col != "Metabolite"]
    time = np.asarray([float(col) for col in time_cols], dtype=float)
    curves: dict[str, np.ndarray] = {}
    order: list[str] = []
    for _, row in df.iterrows():
        name = _normalize_name(row["Metabolite"])
        if not name:
            continue
        values = np.asarray([float(row[col]) for col in time_cols], dtype=float)
        if not np.all(np.isfinite(values)):
            continue
        curves[name] = values
        order.append(name)
    metadata = {
        "source_path": str(path),
        "label": Path(path).stem,
    }
    return time, curves, order, metadata


def _dense_curve(time: np.ndarray, values: np.ndarray, dense_points: int = 250) -> tuple[np.ndarray, np.ndarray]:
    dense_time = np.linspace(float(time[0]), float(time[-1]), int(dense_points))
    if time.size >= 2:
        fit = PchipInterpolator(time, values)
        return dense_time, np.asarray(fit(dense_time), dtype=float)
    return time, values


def _plot_concentration_pages(
    *,
    time: np.ndarray,
    curves: Mapping[str, np.ndarray],
    metabolite_order: Sequence[str],
    out_dir: Path,
    prefix: str,
    title: str,
    per_page: int = 16,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / f"{prefix}_concentration_curves.pdf"
    png_paths: list[str] = []
    names = [name for name in metabolite_order if name in curves]
    page_count = int(math.ceil(len(names) / per_page))

    with PdfPages(pdf_path) as pdf:
        for page_idx in range(page_count):
            page_names = names[page_idx * per_page : (page_idx + 1) * per_page]
            rows, cols = 4, 4
            fig, axes = plt.subplots(rows, cols, figsize=(15, 10), constrained_layout=True)
            axes_flat = axes.flatten()
            for ax, name in zip(axes_flat, page_names):
                values = np.asarray(curves[name], dtype=float)
                dense_time, dense_values = _dense_curve(time, values)
                ax.plot(dense_time, dense_values, color="#2563eb", linewidth=1.8)
                ax.scatter(time, values, color="#111827", s=18, zorder=3)
                ax.set_title(name, fontsize=10, fontweight="bold")
                ax.set_xlabel("Storage time (days)", fontsize=8)
                ax.set_ylabel("mM", fontsize=8)
                ax.grid(True, alpha=0.25)
                ax.tick_params(labelsize=8)
            for ax in axes_flat[len(page_names) :]:
                ax.axis("off")
            fig.suptitle(f"{title} - concentration curves ({page_idx + 1}/{page_count})", fontsize=14)
            pdf.savefig(fig)
            png_path = out_dir / f"{prefix}_concentrations_page_{page_idx + 1:02d}.png"
            fig.savefig(png_path, dpi=180)
            png_paths.append(str(png_path))
            plt.close(fig)

    return {
        "pdf": str(pdf_path),
        "png_pages": png_paths,
        "metabolite_count": len(names),
        "page_count": page_count,
    }


def _plot_flux_pages(
    *,
    teacher_dataset: Mapping[str, Any],
    out_dir: Path,
    prefix: str,
    title: str,
    training_reactions: set[str] = TRAINING_REACTIONS,
    per_page: int = 12,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    dense_time = np.asarray(teacher_dataset["dense_timepoints"], dtype=float)
    reaction_flux_curves = teacher_dataset.get("reaction_flux_curves", {})
    names = sorted(reaction_flux_curves)
    pdf_path = out_dir / f"{prefix}_teacher_flux_curves.pdf"
    png_paths: list[str] = []
    page_count = int(math.ceil(len(names) / per_page))

    with PdfPages(pdf_path) as pdf:
        for page_idx in range(page_count):
            page_names = names[page_idx * per_page : (page_idx + 1) * per_page]
            rows, cols = 4, 3
            fig, axes = plt.subplots(rows, cols, figsize=(15, 11), constrained_layout=True)
            axes_flat = axes.flatten()
            for ax, reaction in zip(axes_flat, page_names):
                entry = reaction_flux_curves[reaction]
                values = np.asarray(entry.get("dense_values", []), dtype=float)
                source_metabolite = entry.get("source_metabolite", "")
                diagnostics = entry.get("diagnostics", {}) if isinstance(entry, dict) else {}
                confidence = diagnostics.get("confidence")
                color = "#dc2626" if reaction in training_reactions else "#059669"
                ax.plot(dense_time, values, color=color, linewidth=1.9)
                ax.axhline(0.0, color="#6b7280", linewidth=0.8, linestyle="--")
                label = "training" if reaction in training_reactions else "available"
                title_text = f"{reaction} from {source_metabolite} ({label})"
                if isinstance(confidence, (int, float)):
                    title_text += f"\nconfidence={confidence:.2f}"
                ax.set_title(title_text, fontsize=9, fontweight="bold")
                ax.set_xlabel("Storage time (days)", fontsize=8)
                ax.set_ylabel("mM/day", fontsize=8)
                ax.grid(True, alpha=0.25)
                ax.tick_params(labelsize=8)
            for ax in axes_flat[len(page_names) :]:
                ax.axis("off")
            fig.suptitle(f"{title} - experimental teacher fluxes ({page_idx + 1}/{page_count})", fontsize=14)
            pdf.savefig(fig)
            png_path = out_dir / f"{prefix}_teacher_fluxes_page_{page_idx + 1:02d}.png"
            fig.savefig(png_path, dpi=180)
            png_paths.append(str(png_path))
            plt.close(fig)

    return {
        "pdf": str(pdf_path),
        "png_pages": png_paths,
        "reaction_count": len(names),
        "page_count": page_count,
        "training_reactions": sorted(training_reactions.intersection(names)),
        "available_reactions": sorted(set(names) - training_reactions),
    }


def _plot_training_flux_focus(
    *,
    teacher_dataset: Mapping[str, Any],
    out_dir: Path,
    prefix: str,
    title: str,
) -> str | None:
    dense_time = np.asarray(teacher_dataset["dense_timepoints"], dtype=float)
    teacher_curves = teacher_dataset.get("teacher_curves", {})
    reaction_flux_curves = teacher_dataset.get("reaction_flux_curves", {})
    pairs = [("EGLC", "VEGLC"), ("ELAC", "VELAC")]
    if not all(met in teacher_curves and rxn in reaction_flux_curves for met, rxn in pairs):
        return None

    fig, axes = plt.subplots(2, 2, figsize=(13, 7), constrained_layout=True)
    for row, (metabolite, reaction) in enumerate(pairs):
        curve = teacher_curves[metabolite]
        flux = reaction_flux_curves[reaction]
        exp_time = np.asarray(curve["timepoints"], dtype=float)
        exp_values = np.asarray(curve["values"], dtype=float)
        dense_values = np.asarray(curve["dense_values"], dtype=float)
        flux_values = np.asarray(flux["dense_values"], dtype=float)

        axes[row, 0].plot(dense_time, dense_values, color="#2563eb", linewidth=2.0)
        axes[row, 0].scatter(exp_time, exp_values, color="#111827", s=22, zorder=3)
        axes[row, 0].set_title(f"{metabolite} experimental concentration", fontweight="bold")
        axes[row, 0].set_xlabel("Storage time (days)")
        axes[row, 0].set_ylabel("mM")
        axes[row, 0].grid(True, alpha=0.25)

        axes[row, 1].plot(dense_time, flux_values, color="#dc2626", linewidth=2.0)
        axes[row, 1].axhline(0.0, color="#6b7280", linewidth=0.8, linestyle="--")
        axes[row, 1].set_title(f"{reaction} teacher flux used for ODE training", fontweight="bold")
        axes[row, 1].set_xlabel("Storage time (days)")
        axes[row, 1].set_ylabel("mM/day")
        axes[row, 1].grid(True, alpha=0.25)

    fig.suptitle(title, fontsize=15)
    out_dir.mkdir(parents=True, exist_ok=True)
    png_path = out_dir / f"{prefix}_training_flux_focus_veglc_velac.png"
    fig.savefig(png_path, dpi=200)
    plt.close(fig)
    return str(png_path)


def _build_general_inferred_flux_dataset(
    *,
    time: np.ndarray,
    curves: Mapping[str, np.ndarray],
    dense_points: int,
    label: str,
    data_path: Path,
    out_path: Path,
) -> dict[str, Any]:
    dense_time = np.linspace(float(time[0]), float(time[-1]), int(dense_points))
    inferred = infer_user_fluxes(
        curves,
        time,
        rs.STOICHIOMETRY,
        time_grid=dense_time,
    )
    teacher_curves: dict[str, dict[str, Any]] = {}
    for name, values in inferred["curves"].items():
        values = np.asarray(values, dtype=float)
        teacher_curves[str(name)] = {
            "source": "standardized_csv_pchip",
            "timepoints": time.tolist(),
            "values": np.asarray(curves[str(name)], dtype=float).tolist() if str(name) in curves else [],
            "dense_values": values.tolist(),
            "dense_derivative": np.asarray(inferred["derivatives"][name], dtype=float).tolist(),
        }

    reaction_flux_curves = {}
    for reaction, values in inferred["fluxes"].items():
        confidence = inferred["confidence"].get(reaction, {})
        reaction_flux_curves[str(reaction)] = {
            "source_metabolite": "multi_balance",
            "source": "stoichiometric_flux_inference",
            "dense_values": np.asarray(values, dtype=float).tolist(),
            "diagnostics": confidence,
        }

    payload = {
        "contract_type": "fla_inferred_flux_dataset",
        "contract_version": 1,
        "dataset_label": f"inferred_flux_{_slugify(label)}",
        "data_path": str(data_path),
        "target_metabolites": list(inferred["metabolites"]),
        "dense_timepoints": dense_time.tolist(),
        "teacher_curves": teacher_curves,
        "reaction_flux_curves": reaction_flux_curves,
        "diagnostics": inferred["diagnostics"],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(_jsonable(payload), indent=2), encoding="utf-8")
    return payload


def _build_dataset_flux_payload(
    *,
    time: np.ndarray,
    curves: Mapping[str, np.ndarray],
    order: Sequence[str],
    label: str,
    source_path: Path,
    out_path: Path,
    dense_points: int,
) -> tuple[dict[str, Any], str]:
    extracellular_targets = [
        name
        for name in order
        if _normalize_name(name) in EXTRACELLULAR_TEACHER_FLUX_RULES
    ]
    if extracellular_targets:
        payload = build_extracellular_teacher_flux_dataset(
            curves,
            time,
            metabolite_names=extracellular_targets,
            dense_points=dense_points,
            dataset_label=f"teacher_flux_{_slugify(label)}",
            data_path=source_path,
            out_path=out_path,
            strict=False,
        )
        return payload, "extracellular_direct_balance"

    payload = _build_general_inferred_flux_dataset(
        time=time,
        curves=curves,
        dense_points=dense_points,
        label=label,
        data_path=source_path,
        out_path=out_path,
    )
    return payload, "stoichiometric_general_inference"


def _write_index(out_dir: Path, manifest: Mapping[str, Any]) -> str:
    lines = [
        "# FLA presentation assets",
        "",
        f"Generated at: {manifest['generated_at']}",
        "",
        "## Brodbar experimental concentrations",
        "",
        f"- PDF: `{manifest['brodbar']['concentrations']['pdf']}`",
        f"- Metabolites plotted: {manifest['brodbar']['concentrations']['metabolite_count']}",
        "",
        "## Brodbar experimental teacher fluxes",
        "",
        f"- PDF: `{manifest['brodbar']['teacher_fluxes']['pdf']}`",
        f"- Reactions plotted: {manifest['brodbar']['teacher_fluxes']['reaction_count']}",
        f"- Current training reactions: {', '.join(manifest['brodbar']['teacher_fluxes']['training_reactions'])}",
        "",
    ]
    focus = manifest["brodbar"].get("training_flux_focus_png")
    if focus:
        lines.extend(["## Current ODE training focus", "", f"- PNG: `{focus}`", ""])
    custom_datasets = manifest.get("custom_datasets") or []
    if custom_datasets:
        lines.extend(["## Custom / external datasets", ""])
        for item in custom_datasets:
            lines.extend(
                [
                    f"### {item['label']}",
                    "",
                    f"- Concentration PDF: `{item['concentrations']['pdf']}`",
                    f"- Flux PDF: `{item['teacher_fluxes']['pdf']}`",
                    f"- Flux method: `{item['flux_method']}`",
                    f"- Reactions plotted: {item['teacher_fluxes']['reaction_count']}",
                    "",
                ]
            )
    else:
        lines.extend(
            [
                "## Custom / external datasets",
                "",
                "No custom JSON/CSV dataset was provided in this run. Use `--custom-json` or `--custom-csv` to generate the same assets for external data.",
                "",
            ]
        )
    path = out_dir / "presentation_assets.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def generate_assets(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    custom_json: Path | None = None,
    custom_csvs: Sequence[Path] | None = None,
    dense_points: int = 250,
) -> dict[str, Any]:
    out_dir = Path(out_dir)
    brodbar_dir = out_dir / "brodbar"
    custom_dir = out_dir / "custom"
    out_dir.mkdir(parents=True, exist_ok=True)

    time, curves, order = _load_bordbar()
    brodbar_concentrations = _plot_concentration_pages(
        time=time,
        curves=curves,
        metabolite_order=order,
        out_dir=brodbar_dir,
        prefix="brodbar",
        title="Brodbar experimental metabolomics",
    )
    brodbar_teacher_dataset_path = brodbar_dir / "brodbar_extracellular_teacher_flux_dataset.json"
    brodbar_teacher_dataset = build_bordbar_extracellular_teacher_flux_dataset(
        metabolite_names=EXTRACELLULAR_TEACHER_METABOLITES,
        dense_points=dense_points,
        out_path=brodbar_teacher_dataset_path,
        dataset_label="teacher_flux_bordbar_all_extracellular",
    )
    brodbar_fluxes = _plot_flux_pages(
        teacher_dataset=brodbar_teacher_dataset,
        out_dir=brodbar_dir,
        prefix="brodbar",
        title="Brodbar FLA",
    )
    brodbar_focus_png = _plot_training_flux_focus(
        teacher_dataset=brodbar_teacher_dataset,
        out_dir=brodbar_dir,
        prefix="brodbar",
        title="FLA training focus: Brodbar EGLC/ELAC",
    )

    manifest: dict[str, Any] = {
        "contract_type": "fla_presentation_assets",
        "contract_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "out_dir": str(out_dir),
        "brodbar": {
            "data_path": str(BRODBAR_DATA_PATH),
            "concentrations": brodbar_concentrations,
            "teacher_flux_dataset": str(brodbar_teacher_dataset_path),
            "teacher_fluxes": brodbar_fluxes,
            "training_flux_focus_png": brodbar_focus_png,
        },
        "custom": None,
        "custom_datasets": [],
    }

    if custom_json is not None:
        custom_time, custom_curves, custom_order, custom_metadata = _load_custom_dataset(Path(custom_json))
        custom_csvs = [*(custom_csvs or []), Path(custom_json)]

    for dataset_path in custom_csvs or []:
        dataset_path = Path(dataset_path)
        if dataset_path.suffix.lower() == ".json":
            custom_time, custom_curves, custom_order, custom_metadata = _load_custom_dataset(dataset_path)
        else:
            custom_time, custom_curves, custom_order, custom_metadata = _load_standardized_csv(dataset_path)
        label = str(custom_metadata["label"])
        slug = _slugify(label)
        dataset_dir = custom_dir / slug
        custom_concentrations = _plot_concentration_pages(
            time=custom_time,
            curves=custom_curves,
            metabolite_order=custom_order,
            out_dir=dataset_dir,
            prefix=slug,
            title=f"Experimental metabolomics: {label}",
        )
        custom_flux_dataset_path = dataset_dir / f"{slug}_fla_flux_dataset.json"
        custom_flux_dataset, flux_method = _build_dataset_flux_payload(
            time=custom_time,
            curves=custom_curves,
            order=custom_order,
            label=label,
            source_path=dataset_path,
            out_path=custom_flux_dataset_path,
            dense_points=dense_points,
        )
        custom_fluxes = _plot_flux_pages(
            teacher_dataset=custom_flux_dataset,
            out_dir=dataset_dir,
            prefix=slug,
            title=f"FLA: {label}",
        )
        custom_focus_png = _plot_training_flux_focus(
            teacher_dataset=custom_flux_dataset,
            out_dir=dataset_dir,
            prefix=slug,
            title=f"FLA training focus: {label}",
        )
        entry = {
            **custom_metadata,
            "slug": slug,
            "flux_method": flux_method,
            "concentrations": custom_concentrations,
            "teacher_flux_dataset": str(custom_flux_dataset_path),
            "teacher_fluxes": custom_fluxes,
            "training_flux_focus_png": custom_focus_png,
        }
        manifest["custom_datasets"].append(entry)
        if manifest["custom"] is None:
            manifest["custom"] = entry

    manifest_path = out_dir / "manifest.json"
    manifest["manifest_path"] = str(manifest_path)
    manifest["index_path"] = _write_index(out_dir, manifest)
    manifest_path.write_text(json.dumps(_jsonable(manifest), indent=2), encoding="utf-8")
    return manifest


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate FLA presentation plots")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--custom-json", type=Path)
    parser.add_argument("--custom-csv", type=Path, action="append", default=[])
    parser.add_argument("--dense-points", type=int, default=250)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    manifest = generate_assets(
        out_dir=args.out_dir,
        custom_json=args.custom_json,
        custom_csvs=args.custom_csv,
        dense_points=args.dense_points,
    )
    print(
        json.dumps(
            {
                "manifest_path": manifest["manifest_path"],
                "index_path": manifest["index_path"],
                "brodbar_concentration_pdf": manifest["brodbar"]["concentrations"]["pdf"],
                "brodbar_teacher_flux_pdf": manifest["brodbar"]["teacher_fluxes"]["pdf"],
                "training_flux_focus_png": manifest["brodbar"]["training_flux_focus_png"],
                "custom_generated": len(manifest.get("custom_datasets") or []),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
