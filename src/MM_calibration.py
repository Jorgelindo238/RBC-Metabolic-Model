"""
ML-based MM recalibration for the RBC metabolic model.

Supports:
- legacy calibration
- vmax_only
- km_only
- vmax_then_km
- km_then_vmax
- joint_vmax_km
- staged_full
- explicit stage_plan execution
"""

import sys
import os
import json
import time
import argparse
import csv
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp
from scipy.interpolate import PchipInterpolator

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from equadiff_brodbar import (
    equadiff_brodbar,
    BRODBAR_METABOLITE_MAP,
    NUM_BASE_METABOLITES,
    _compute_veglc_flux,
    _compute_velac_flux,
    _compute_vldh_flux,
)
from parse_initial_conditions import parse_initial_conditions

# Phase 0: stoichiometric reachability for auto-param-scope. Imported defensively
# so any parser drift in rbc_stoichiometry never breaks calibration; auto-scope
# simply degrades to the existing curated profile when this import fails.
try:
    import rbc_stoichiometry as _rbc_stoichiometry  # type: ignore
    _RBC_STOICHIOMETRY_AVAILABLE = True
except Exception:  # pragma: no cover - defensive
    _rbc_stoichiometry = None  # type: ignore[assignment]
    _RBC_STOICHIOMETRY_AVAILABLE = False

try:
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    HAS_OPTUNA = True
except ImportError:
    HAS_OPTUNA = False
    from scipy.optimize import differential_evolution

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# =============================================================================
# CONFIG
# =============================================================================

DATA_DIR = Path(__file__).parent
OUT_DIR = Path(__file__).parent.parent / "Simulations" / "brodbar" / "calibration"

LEGACY_RESULTS_TSV_FIELDS = [
    "timestamp",
    "stage",
    "target_scope",
    "param_scope",
    "baseline_target_loss",
    "candidate_target_loss",
    "joint_loss",
    "extracellular_loss",
    "glycolysis_loss",
    "endpoint_nrmse",
    "status",
    "description",
]

RESULTS_TSV_FIELDS = [
    "timestamp",
    "stage",
    "target_scope",
    "param_scope",
    "baseline_target_loss",
    "candidate_target_loss",
    "joint_loss",
    "rank_loss",
    "experimental_fit_loss",
    "teacher_student_loss",
    "teacher_student_weight",
    "guardrail_loss",
    "regularization_loss",
    "physiological_penalty_loss",
    "legacy_total_loss",
    "glycolysis_energy_loss",
    "nucleotide_purine_loss",
    "amino_redox_side_loss",
    "extracellular_loss",
    "glycolysis_loss",
    "endpoint_nrmse",
    "status",
    "description",
]

FIT_FIRST_REGULARIZATION_WEIGHT = 0.0
FIT_FIRST_PHYSIOLOGICAL_WEIGHT = 0.0
FIT_PRIORITY_ABS_GAIN = 0.0
FIT_PRIORITY_REL_GAIN = 0.0
HARD_GUARDRAIL_MULTIPLIER = 3.0
HARD_ENDPOINT_REGRESSION = 0.75
JOINT_TIE_TOLERANCE = 0.02
DEFAULT_TEACHER_CURVE_METABOLITES = ["ATP", "ADP", "EGLC", "PYR", "PEP", "LAC"]
DEFAULT_TEACHER_DENSE_POINTS = 200
DEFAULT_TEACHER_STUDENT_WEIGHT = 0.0
DEFAULT_TEACHER_FOCUS_WEIGHT = 1.0
DEFAULT_TRANSPORT_TEACHER_FOCUS_METABOLITES = ["EGLC", "ELAC", "LAC"]

EXP_TO_MODEL = {
    "GLC": 0, "G6P": 1, "F6P": 2, "GO6P": 4,
    "F16BP": 11, "P3G": 14, "B23PG": 15,
    "P2G": 16, "PEP": 17, "PYR": 18, "LAC": 19, "MAL": 20,
    "CIT": 22, "ADE": 25, "INO": 27, "HYPX": 28, "XAN": 29, "URT": 30,
    "ATP": 35, "ADP": 36, "AMP": 37, "GMP": 40, "IMP": 42,
    "SAH": 51, "ARG": 53, "CITR": 55, "ASP": 56, "SER": 57,
    "ALA": 58, "GLU": 60, "GLN": 61, "OXOP": 65,
    "GSH": 70, "GSSG": 71,
    "EGLC": 85, "ELAC": 87, "EADE": 89, "EINO": 90,
    "EGLN": 91, "EGLU": 92, "ECYS": 93,
    "EURT": 97, "EXAN": 99, "EHYPX": 100, "EMAL": 101,
    "EFUM": 102, "ECIT": 103,
    "ASN": 106, "EOXOP": 107, "ESER": 108, "EARG": 109,
    "EGSSG": 110, "EGSH": 111, "EASN": 112,
}

EXTRACELLULAR_TARGET_METABOLITES = {name for name in EXP_TO_MODEL if name.startswith("E")}
ENERGETICS_TARGET_METABOLITES = {"ATP", "ADP", "AMP"}
GLYCOLYSIS_TARGET_METABOLITES = {
    "EGLC", "GLC", "G6P", "F6P", "F16BP",
    "P3G", "B23PG", "P2G", "PEP", "PYR", "LAC", "ELAC",
}
GLYCOLYSIS_TERMINAL_TARGET_METABOLITES = {"EGLC", "GLC", "P2G", "PEP", "PYR", "LAC", "ELAC"}
GLYCOLYSIS_EXTRACELLULAR_TARGET_METABOLITES = (
    GLYCOLYSIS_TARGET_METABOLITES | EXTRACELLULAR_TARGET_METABOLITES | ENERGETICS_TARGET_METABOLITES
)
CORE_GLYCOLYSIS_ENERGY_TARGET_METABOLITES = {
    "EGLC", "GLC", "G6P", "F6P", "F16BP", "P3G", "B23PG",
    "P2G", "PEP", "PYR", "LAC", "ELAC", "ATP", "ADP", "AMP",
}
NUCLEOTIDE_PURINE_TARGET_METABOLITES = {
    "ADE", "INO", "HYPX", "XAN", "URT", "GMP", "IMP",
    "EADE", "EINO", "EURT", "EXAN", "EHYPX",
}
AMINO_REDOX_SIDE_TARGET_METABOLITES = {
    "GO6P", "MAL", "CIT", "SAH", "ARG", "CITR", "ASP", "SER", "ALA", "GLU", "GLN", "OXOP",
    "GSH", "GSSG", "ASN",
    "EGLN", "EGLU", "ECYS", "EMAL", "EFUM", "ECIT", "EOXOP", "ESER", "EARG",
    "EGSSG", "EGSH", "EASN",
}
ALL_SUPPORTED_TARGET_METABOLITES = set(EXP_TO_MODEL)
PRIMARY_TARGET_SCOPE_METABOLITES = {
    "glycolysis_extracellular": CORE_GLYCOLYSIS_ENERGY_TARGET_METABOLITES | {"IMP"},
}

PATHWAY_TARGET_GROUPS = {
    "glycolysis_energy": GLYCOLYSIS_EXTRACELLULAR_TARGET_METABOLITES,
    "core_glycolysis_energy": CORE_GLYCOLYSIS_ENERGY_TARGET_METABOLITES,
    "nucleotide_purine": NUCLEOTIDE_PURINE_TARGET_METABOLITES,
    "amino_redox_side": AMINO_REDOX_SIDE_TARGET_METABOLITES,
}
PATHWAY_PHASE_OBJECTIVE_NAMES = {
    1: "glycolysis_energy",
    2: "nucleotide_purine",
    3: "amino_redox_side",
}
PATHWAY_MONITOR_REGRESSION_LIMITS = {
    "glycolysis_energy": 0.25,
    "nucleotide_purine": 0.35,
    "amino_redox_side": 0.35,
    "extracellular": 0.25,
    "glycolysis": 0.25,
}

HIGH_WEIGHT_METABOLITES = {"GLC", "G6P", "LAC", "PYR", "EGLC", "ELAC"}

CRITICAL_WEIGHT_METABOLITES = {
    "ATP": 30.0,
    "ADP": 30.0,
    "AMP": 20.0,
    "IMP": 15.0,
    "B23PG": 8.0,
    "GSH": 5.0,
    "GSSG": 5.0,
    "PEP": 5.0,
    "GLC": 3.0,
    "LAC": 3.0,
    "P2G": 3.0,
}

TARGET_SCOPE_WEIGHT_OVERRIDES = {
    "glycolysis_terminal": {
        "EGLC": 8.0,
        "ELAC": 8.0,
        "GLC": 4.0,
        "LAC": 4.0,
        "PYR": 3.0,
        "PEP": 3.0,
        "P2G": 3.0,
    },
    "glycolysis_extracellular": {
        "EGLC": 14.0,
        "ELAC": 9.0,
        "GLC": 7.0,
        "G6P": 6.0,
        "ATP": 45.0,
        "ADP": 45.0,
        "AMP": 24.0,
        "IMP": 18.0,
        "LAC": 12.0,
        "F6P": 4.0,
        "F16BP": 4.0,
        "PYR": 12.0,
        "PEP": 10.0,
        "P2G": 4.0,
        "EURT": 4.0,
        "EFUM": 3.0,
        "EGLN": 2.5,
        "EOXOP": 2.5,
        "EADE": 2.5,
        "EARG": 2.5,
    },
    "glycolysis_energy": {
        "EGLC": 8.0,
        "ELAC": 8.0,
        "GLC": 6.0,
        "G6P": 6.0,
        "ATP": 30.0,
        "ADP": 30.0,
        "AMP": 20.0,
        "IMP": 15.0,
        "LAC": 5.0,
        "F6P": 4.0,
        "F16BP": 4.0,
        "PYR": 4.0,
        "PEP": 3.0,
        "P2G": 3.0,
    },
    "core_glycolysis_energy": {
        "EGLC": 14.0,
        "ELAC": 9.0,
        "GLC": 7.0,
        "G6P": 6.0,
        "ATP": 45.0,
        "ADP": 45.0,
        "AMP": 24.0,
        "IMP": 18.0,
        "B23PG": 8.0,
        "LAC": 12.0,
        "F6P": 4.0,
        "F16BP": 4.0,
        "P3G": 4.0,
        "PYR": 12.0,
        "PEP": 10.0,
        "P2G": 4.0,
    },
    "nucleotide_purine": {
        "IMP": 5.0,
        "GMP": 5.0,
        "AMP": 6.0,
        "EADE": 4.0,
        "EURT": 4.0,
        "EXAN": 3.0,
        "HYPX": 3.0,
        "ADE": 3.0,
        "INO": 2.5,
        "URT": 3.0,
    },
    "amino_redox_side": {
        "GSH": 6.0,
        "GSSG": 6.0,
        "GLU": 4.0,
        "GLN": 3.0,
        "EOXOP": 3.0,
        "EGLN": 3.0,
        "ECIT": 3.0,
        "EFUM": 3.0,
    },
    "all_supported": {
        "EGLC": 8.0,
        "ELAC": 8.0,
        "GLC": 6.0,
        "G6P": 6.0,
        "ATP": 30.0,
        "ADP": 30.0,
        "AMP": 20.0,
        "IMP": 15.0,
        "GMP": 5.0,
        "GSH": 6.0,
        "GSSG": 6.0,
        "GLU": 4.0,
        "EURT": 4.0,
        "EADE": 4.0,
        "EOXOP": 3.0,
    },
}

TARGET_SCOPE_ENDPOINT_METABOLITES = {
    "glycolysis_terminal": {"EGLC", "ELAC"},
    "glycolysis_extracellular": {"EGLC", "ELAC", "GLC", "LAC", "ATP", "ADP", "AMP", "IMP"},
    "glycolysis_energy": {"EGLC", "ELAC", "GLC", "LAC", "ATP", "ADP", "AMP", "IMP"},
    "core_glycolysis_energy": {"EGLC", "ELAC", "GLC", "LAC", "ATP", "ADP", "AMP", "IMP", "B23PG"},
    "all_supported": {"EGLC", "ELAC", "GLC", "LAC", "ATP", "ADP", "AMP", "IMP"},
}
TARGET_SCOPE_ENDPOINT_WEIGHTS = {
    "glycolysis_terminal": 3.0,
    "glycolysis_extracellular": 4.0,
    "glycolysis_energy": 4.0,
    "core_glycolysis_energy": 4.0,
    "all_supported": 3.0,
}

NRMSE_CAP = 50.0
SOLVE_CACHE_SIZE = 16


# AGENT_EDITABLE_START: target_routing
def resolve_target_scope_metabolites(target_scope):
    if target_scope == "all":
        return ALL_SUPPORTED_TARGET_METABOLITES
    if target_scope == "extracellular":
        return EXTRACELLULAR_TARGET_METABOLITES
    if target_scope == "glycolysis":
        return GLYCOLYSIS_TARGET_METABOLITES
    if target_scope == "glycolysis_terminal":
        return GLYCOLYSIS_TERMINAL_TARGET_METABOLITES
    if target_scope == "glycolysis_extracellular":
        return GLYCOLYSIS_EXTRACELLULAR_TARGET_METABOLITES
    if target_scope == "core_glycolysis_energy":
        return CORE_GLYCOLYSIS_ENERGY_TARGET_METABOLITES
    raise ValueError(f"Unsupported target_scope: {target_scope}")


def resolve_primary_target_names(target_scope, target_names=None):
    normalized_targets = normalize_name_list(target_names)
    scoped_primary_targets = PRIMARY_TARGET_SCOPE_METABOLITES.get(target_scope)
    if scoped_primary_targets is None:
        return normalized_targets

    if normalized_targets is None:
        return sorted(scoped_primary_targets)

    filtered = [name for name in normalized_targets if name in scoped_primary_targets]
    return filtered or normalized_targets


def resolve_phase_target_names(objective_name, target_names=None):
    phase_targets = PATHWAY_TARGET_GROUPS[objective_name]
    normalized_targets = normalize_name_list(target_names)
    if normalized_targets is None:
        return sorted(phase_targets)
    filtered = [name for name in normalized_targets if name in phase_targets]
    return filtered


def use_pathway_phase_objectives(target_scope):
    return target_scope == "glycolysis_extracellular"


def infer_custom_data_calibration_profile(target_metabolites):
    normalized_targets = {
        str(name).strip().upper()
        for name in (normalize_name_list(target_metabolites) or [])
        if str(name).strip()
    }
    energetic_targets = sorted(normalized_targets & ENERGETICS_TARGET_METABOLITES)
    extracellular_targets = sorted(normalized_targets & EXTRACELLULAR_TARGET_METABOLITES)
    glycolysis_targets = sorted(normalized_targets & GLYCOLYSIS_TARGET_METABOLITES)
    purine_targets = sorted(
        normalized_targets & set(PATHWAY_TARGET_GROUPS.get("nucleotide_purine", []))
    )

    if extracellular_targets:
        return {
            "profile_name": "glycolysis_extracellular_energy",
            "target_scope": "glycolysis_extracellular",
            "optimization_strategy": "vmax_then_km",
            "atp_focus": bool(energetic_targets),
            "atp_floor": 0.15,
            "adp_floor": 0.05,
            "amp_floor": 0.04,
            "imp_floor": 0.02,
            "adenylate_target": 0.65,
            "atp_penalty_weight": 10.0,
            "amp_penalty_weight": 6.0,
            "imp_penalty_weight": 5.0,
            "pool_penalty_weight": 12.0,
            "curve_fit_strength": 0.0,
            "parameter_additions": [
                "vmax_VAK",
                "vmax_VAK_rev",
                "vmax_VAK2",
                "vmax_VAMPD1",
                "vmax_VAPRT",
                "vmax_VADSL",
            ],
            "signals": {
                "energetic": energetic_targets,
                "extracellular": extracellular_targets,
                "glycolysis": glycolysis_targets,
                "purine": purine_targets,
            },
            "rationale": (
                "Extracellular targets are present, so use the "
                "glycolysis_extracellular objective bundle with ATP-aware penalties "
                "and a Vmax-first stage plan."
            ),
        }

    if energetic_targets:
        return {
            "profile_name": "core_glycolysis_energy_atp",
            "target_scope": "core_glycolysis_energy",
            "optimization_strategy": "vmax_then_km",
            "atp_focus": True,
            "atp_floor": 0.15,
            "adp_floor": 0.05,
            "amp_floor": 0.04,
            "imp_floor": 0.02,
            "adenylate_target": 0.65,
            "atp_penalty_weight": 10.0,
            "amp_penalty_weight": 6.0,
            "imp_penalty_weight": 5.0,
            "pool_penalty_weight": 12.0,
            "curve_fit_strength": 0.0,
            "parameter_additions": [
                "vmax_VAK",
                "vmax_VAK_rev",
                "vmax_VAK2",
                "vmax_VAMPD1",
                "vmax_VAPRT",
                "vmax_VADSL",
            ],
            "signals": {
                "energetic": energetic_targets,
                "extracellular": extracellular_targets,
                "glycolysis": glycolysis_targets,
                "purine": purine_targets,
            },
            "rationale": (
                "ATP/ADP/AMP targets are present without extracellular anchors, so "
                "keep the calibration on the core glycolysis-energy bundle with "
                "ATP-aware penalties and a Vmax-first stage plan."
            ),
        }

    if purine_targets:
        return {
            "profile_name": "purine_transport_refinement",
            "target_scope": "core_glycolysis_energy",
            "optimization_strategy": "core_km_then_purine_transport",
            "atp_focus": False,
            "atp_floor": 0.15,
            "adp_floor": 0.05,
            "amp_floor": 0.04,
            "imp_floor": 0.02,
            "adenylate_target": 0.65,
            "atp_penalty_weight": 10.0,
            "amp_penalty_weight": 6.0,
            "imp_penalty_weight": 5.0,
            "pool_penalty_weight": 12.0,
            "curve_fit_strength": 0.0,
            "parameter_additions": [
                "vmax_VAK",
                "vmax_VAK_rev",
                "vmax_VAK2",
                "vmax_VAMPD1",
                "vmax_VAPRT",
                "vmax_VADSL",
            ],
            "signals": {
                "energetic": energetic_targets,
                "extracellular": extracellular_targets,
                "glycolysis": glycolysis_targets,
                "purine": purine_targets,
            },
            "rationale": (
                "Purine-heavy custom data benefits from a core glycolysis-energy "
                "anchor followed by the dedicated purine transport refinement stage."
            ),
        }

    if glycolysis_targets:
        return {
            "profile_name": "glycolysis_core",
            "target_scope": "glycolysis",
            "optimization_strategy": "vmax_then_km",
            "atp_focus": False,
            "atp_floor": 0.15,
            "adp_floor": 0.05,
            "adenylate_target": 0.65,
            "atp_penalty_weight": 8.0,
            "pool_penalty_weight": 10.0,
            "curve_fit_strength": 0.0,
            "parameter_additions": [],
            "signals": {
                "energetic": energetic_targets,
                "extracellular": extracellular_targets,
                "glycolysis": glycolysis_targets,
                "purine": purine_targets,
            },
            "rationale": (
                "Upper- and lower-glycolysis data are present without a stronger "
                "energy/extracellular signal, so keep the calibration anchored to "
                "the glycolysis core with a Vmax-first pass."
            ),
        }

    return {
        "profile_name": "broad_compatibility",
        "target_scope": "all",
        "optimization_strategy": "vmax_then_km",
        "atp_focus": False,
        "atp_floor": 0.15,
        "adp_floor": 0.05,
        "amp_floor": 0.04,
        "imp_floor": 0.02,
        "adenylate_target": 0.65,
        "atp_penalty_weight": 10.0,
        "amp_penalty_weight": 6.0,
        "imp_penalty_weight": 5.0,
        "pool_penalty_weight": 12.0,
        "curve_fit_strength": 0.0,
        "parameter_additions": [],
        "signals": {
            "energetic": energetic_targets,
            "extracellular": extracellular_targets,
            "glycolysis": glycolysis_targets,
            "purine": purine_targets,
        },
        "rationale": (
            "No strong monitoring-relevant anchor was detected, so keep the default "
            "broad compatibility calibration profile."
        ),
    }


# AGENT_EDITABLE_END: target_routing
# =============================================================================
# PARAMETER PHASES
# =============================================================================

PHASE1_BASE_PARAMS = {
    "vmax_VHK": (0.267472, 0.2, 5.0),
    "vmax_VPFK": (0.391893, 0.8, 5.0),
    "vmax_VFDPA": (1.156751, 0.5, 10.0),
    "vmax_VPK": (0.936322, 0.1, 50.0),
    "vmax_VPGK": (4.690379, 0.5, 50.0),
    "vmax_VPGM": (1.170854, 0.1, 50.0),
    "vmax_VLDH": (0.284952, 0.1, 50.0),
    "vmax_VEGLC": (1.077000, 0.1, 3.5),
    "vmax_VELAC": (0.580000, 0.05, 10.0),
    "vmax_VENOPGM": (5.515612, 2.0, 50.0),
    "vmax_VDPGM": (2.5, 0.1, 5.0),
    "vmax_V23DPGP": (3.0, 0.5, 30.0),
    "ka_F16BP_PK": (0.005, 0.0005, 0.1),
    "alpha_F16BP_PK": (10.0, 1.0, 100.0),
    "vmax_VPEP_PASE": (0.1, 0.01, 10.0),
    "km_GLC_HK": (0.05, 0.005, 5.0),
    "km_G6P": (0.146, 0.01, 5.0),
    "km_F6P": (0.207, 0.01, 5.0),
    "km_F16BP": (0.094, 0.005, 5.0),
    "km_B13PG": (1.013, 0.001, 5.0),
    "km_P3G": (0.134, 0.01, 5.0),
    "km_P2G": (0.134, 0.01, 5.0),
    "km_PEP": (0.175, 0.01, 5.0),
    "km_ADP_ATP": (1.0, 0.05, 10.0),
    "km_PYR": (0.697, 0.01, 5.0),
    "km_LAC": (49.862494, 0.05, 150.0),
    "km_NAD_NADH": (1.0, 0.05, 20.0),
    "km_NADH_NAD": (1.0, 0.001, 20.0),
    "km_ATP_HK": (0.5, 0.05, 2.0),
    "km_ATP_PFK": (0.1, 0.01, 1.0),
    "km_GLC_transport": (5.0, 1.0, 20.0),
    "km_EGLC": (49.5, 0.05, 60.0),
    "ki_ATP_PK": (2.5, 0.5, 10.0),
    "ki_PYR_PK": (1.0, 0.1, 5.0),
}

PHASE1_HYBRID_TRANSPORT_PARAMS = {
    "hybrid_blend_VEGLC": (0.0, 0.0, 1.0),
    "hybrid_import_hill_VEGLC": (1.0, 0.5, 4.0),
    "hybrid_export_hill_VEGLC": (1.0, 0.5, 6.0),
    "hybrid_reverse_scale_VEGLC": (1.0, 0.1, 3.0),
    "transport_gate_km_VEGLC": (10.0, 0.5, 80.0),
    "transport_gate_hill_VEGLC": (1.0, 0.5, 5.0),
    "hybrid_blend_VELAC": (0.0, 0.0, 1.0),
    "hybrid_efflux_hill_VELAC": (1.0, 0.5, 4.0),
    "hybrid_backpressure_hill_VELAC": (1.0, 0.5, 6.0),
    "hybrid_backpressure_scale_VELAC": (0.0, 0.0, 3.0),
    "hybrid_km_ELAC": (49.862494, 1.0, 180.0),
    "hybrid_lac_retention_strength_VELAC": (0.0, 0.0, 1.0),
    "hybrid_lac_retention_hill_VELAC": (1.0, 0.5, 6.0),
    "hybrid_lac_retention_km_scale_VELAC": (1.0, 0.25, 4.0),
    "hybrid_blend_VLDH": (0.0, 0.0, 1.0),
    "hybrid_forward_hill_VLDH": (1.0, 0.5, 6.0),
    "hybrid_reverse_hill_VLDH": (1.0, 0.5, 6.0),
    "hybrid_reverse_scale_VLDH": (0.0, 0.0, 3.0),
}

PHASE1_HYBRID_DOWNSTREAM_PARAMS = {
    "hybrid_blend_VPK": (0.0, 0.0, 1.0),
    "hybrid_pep_hill_VPK": (1.0, 0.5, 4.0),
    "hybrid_adp_hill_VPK": (1.0, 0.5, 4.0),
    "hybrid_atp_backpressure_scale_VPK": (1.0, 0.1, 3.0),
    "hybrid_pyr_backpressure_scale_VPK": (1.0, 0.1, 3.0),
    "hybrid_blend_VENOPGM": (0.0, 0.0, 1.0),
    "hybrid_substrate_hill_VENOPGM": (1.0, 0.5, 4.0),
    "hybrid_backpressure_hill_VENOPGM": (1.0, 0.5, 4.0),
    "hybrid_backpressure_scale_VENOPGM": (1.0, 0.1, 3.0),
}

PHASE1_HYBRID_PARAMS = {**PHASE1_HYBRID_TRANSPORT_PARAMS, **PHASE1_HYBRID_DOWNSTREAM_PARAMS}

PHASE1_PARAMS = {**PHASE1_BASE_PARAMS, **PHASE1_HYBRID_PARAMS}

PHASE2_PARAMS = {
    "vmax_VAMPD1": (0.538065, 0.001, 0.1),
    "vmax_VADSS": (0.3, 0.01, 5.0),
    "vmax_VIMPH": (0.2, 0.01, 5.0),
    "vmax_VRKa": (0.4, 0.01, 3.0),
    "vmax_VPRPPASe": (0.5, 0.05, 3.0),
    "vmax_VAK": (0.8, 0.05, 8.0),
    "vmax_VAK2": (0.5, 0.01, 5.0),
    "vmax_VHGPRT1": (0.645581, 0.01, 6.0),
    "vmax_VHGPRT2": (0.25, 0.001, 1.0),
    "vmax_Vnucleo2": (0.15, 0.005, 2.0),
    "vmax_VGMPS": (0.379205, 0.01, 4.0),
    "vmax_VPNPase1": (0.25, 0.1, 1.0),
    "vmax_VXAO": (0.2, 0.1, 1.0),
    "vmax_VXAO2": (0.15, 0.05, 3.0),
    "vmax_VEXAN": (0.15, 0.001, 0.5),
    "vmax_VEURT": (0.15, 0.001, 1.0),
    "vmax_VEINO": (0.0001, 0.0001, 0.003),
    "vmax_VADA": (0.3, 0.01, 1.0),
    "vmax_VGMPK": (0.15, 0.01, 5.0),
    "vmax_VAPRT": (1.088, 0.1, 10.0),
    "vmax_VADSL": (0.4, 0.01, 5.0),
    "vmax_VNDPK": (1.0, 0.01, 10.0),
    "vmax_VNDPK_rev": (1.0, 0.01, 10.0),
    "vmax_VAK_rev": (0.5, 0.01, 5.0),
    "vmax_Vnucleo_GMP": (0.15, 0.01, 0.5),
    "vmax_VGDA": (0.15, 0.01, 0.5),
    "km_ATP": (0.569, 0.05, 5.0),
    "km_AMP": (0.283, 0.05, 3.0),
}

PHASE3_PARAMS = {
    "vmax_VGDH": (0.5, 0.01, 2.0),
    "vmax_VGDH_rev": (0.1, 0.01, 5.0),
    "vmax_VALATA": (0.35, 0.01, 2.0),
    "vmax_VASPTA": (0.4, 0.01, 4.0),
    "vmax_VGLNS": (0.4, 0.01, 4.0),
    "vmax_VEGLN": (0.001, 0.01, 2.0),
    "vmax_VEGLU": (0.001, 0.0001, 2.0),
    "vmax_VGSR": (1.0, 0.05, 10.0),
    "vmax_VGPX": (1.079815, 0.05, 10.0),
    "vmax_VME": (0.3, 0.01, 3.0),
    "vmax_VFUM": (0.5, 0.01, 5.0),
    "vmax_VMLD": (0.4, 0.01, 4.0),
    "vmax_VECIT": (0.25, 0.005, 2.5),
    "vmax_VASPTA_rev": (0.2, 0.01, 5.0),
    "vmax_VALATA_rev": (0.15, 0.05, 0.5),
    "vmax_VSHMT": (0.1, 0.01, 1.0),
    "vmax_VPHGDH": (0.1, 0.05, 0.5),
    "vmax_VOPLAH": (0.15, 0.01, 5.0),
    "km_GSSG": (1.0, 0.01, 5.0),
    "km_GLU": (0.289, 0.01, 3.0),
    "vmax_VEADE_fwd": (0.01, 0.0001, 0.001),
    "vmax_VEADE_rev": (0.01, 0.001, 1.0),
    "vmax_VEHYPX": (0.002, 0.01, 3.0),
    "vmax_VEFUM": (0.2, 0.001, 5.0),
    "vmax_VEMAL": (0.001, 0.0001, 1.0),
    "vmax_VGSS": (0.4, 0.01, 3.0),
    "vmax_VGGT": (0.3, 0.01, 3.0),
    "vmax_VGGCT": (0.25, 0.01, 3.0),
    "vmax_VEOXOP": (0.15, 0.01, 3.0),
    "vmax_VESER": (0.15, 0.01, 2.0),
    "vmax_VEARG": (0.05, 0.001, 1.0),
    "vmax_VEGSSG": (0.01, 0.001, 0.5),
    "vmax_VEGSH": (0.01, 0.001, 0.5),
    "vmax_VASNG": (0.15, 0.01, 2.0),
    "vmax_VEASN": (0.05, 0.001, 1.0),
    "vmax_VECYS": (0.0005, 0.0001, 0.5),
    "k_EGSH_deg": (0.1, 0.01, 1.0),
    "k_EGSSG_deg": (0.05, 0.01, 1.0),
}

PHASE_MAP = {1: PHASE1_PARAMS, 2: PHASE2_PARAMS, 3: PHASE3_PARAMS}
PHASE_NAMES = {
    1: "Core Glycolysis & Transport",
    2: "Nucleotide Metabolism",
    3: "Amino Acids, Redox & Transport",
}

DEFAULT_PARAM_VALUES = {
    pname: default
    for phase_params in PHASE_MAP.values()
    for pname, (default, _, _) in phase_params.items()
}

DEFAULT_PARAM_BOUNDS = {
    pname: bounds
    for phase_params in PHASE_MAP.values()
    for pname, bounds in phase_params.items()
}


# =============================================================================
# AUTO PARAM SCOPE (Phase 0 of the auto-calibrate-all + ML flux-learning plan)
# =============================================================================
#
# Plan reference:
#   C:/Users/Jorgelindo/.windsurf/plans/auto-calibrate-all-and-ml-flux-learning-179f0d.md
#
# Purpose: when a user uploads custom data with N metabolites (potentially with
# no explicit `params_to_optimize`), automatically pick a sensible parameter
# scope that covers every reaction stoichiometrically reachable from the
# uploaded metabolites, intersected with the calibrator's known parameter
# universe.
#
# Phase 0 deliberately keeps the scope to vmax + km parameters (plus the
# regulation params already inside PHASE1_BASE_PARAMS as the "kernel"). Hybrid
# structure parameters (Hill exponents, allosteric Ki/Ka/alpha) are only
# included when ``include_hybrid=True`` — they are reserved for Phase F of the
# plan after identifiability work lands. The "degenerate-at-canonical-IC"
# pruning step described in the plan is also deferred to Phase E (Phase 0
# returns the structurally-reachable set as-is).

# The kernel is the always-included set of parameters that anchor the
# physiological core of the calibration even when the upload has no
# extracellular signals. Equal to PHASE1_BASE_PARAMS by design — when that
# dict changes, the kernel changes with it.
AUTO_SCOPE_KERNEL: frozenset = frozenset(PHASE1_BASE_PARAMS.keys())


def _normalize_metabolite_name_set(names) -> set:
    """Return a UPPER-cased, stripped set of names (or empty set)."""
    if not names:
        return set()
    if isinstance(names, str):
        names = [names]
    return {str(n).strip().upper() for n in names if str(n).strip()}


def derive_auto_param_scope(
    uploaded_metabolites,
    *,
    always_include_kernel: bool = True,
    include_kms: bool = True,
    include_regulation: bool = True,
    include_hybrid: bool = False,
) -> list:
    """Return a sorted list of calibratable parameter names whose reactions
    affect the uploaded metabolites' stoichiometric neighbourhood.

    The result is the union of:
      1. Stoichiometrically-reachable parameters: every reaction with non-zero
         stoichiometry on any uploaded metabolite contributes its vmax / km
         (and optionally regulation / hybrid) parameters.
      2. The auto-scope kernel (``PHASE1_BASE_PARAMS`` keys), included
         unconditionally when ``always_include_kernel`` is True.

    The result is always intersected with ``DEFAULT_PARAM_VALUES`` (the
    calibrator's authoritative parameter universe), so every returned name has
    a valid ``(default, lo, hi)`` triple in ``DEFAULT_PARAM_BOUNDS``.

    Parameters
    ----------
    uploaded_metabolites
        Iterable of metabolite names (case-insensitive). Names not recognised
        by ``BRODBAR_METABOLITE_MAP`` are silently ignored — the caller is
        expected to filter inputs upstream (the adapter does this).
    always_include_kernel
        If True (default), always include ``PHASE1_BASE_PARAMS`` keys.
    include_kms
        If False, drop ``km_*`` parameters (vmax-only auto-scope).
    include_regulation
        If True (default), keep ``ki_*`` / ``ka_*`` / ``alpha_*`` / ``n_*``
        parameters when reachable. Phase 0 keeps these on because they shape
        existing flux laws (e.g. PK F16BP allosteric activation).
    include_hybrid
        If True, also include ``hybrid_*`` / ``kinetic_family_*`` /
        ``transport_gate_*`` parameters. Phase 0 default is False; structure
        learning is deferred to Phase F of the plan.

    Returns
    -------
    list[str]
        Sorted list of parameter names suitable for use as keys of the web
        adapter's ``params_to_optimize`` dict. Empty list if rbc_stoichiometry
        is unavailable (defensive: the caller is expected to fall back to its
        existing scope-resolution path in that case).
    """
    if not _RBC_STOICHIOMETRY_AVAILABLE or _rbc_stoichiometry is None:
        return []

    uploaded = _normalize_metabolite_name_set(uploaded_metabolites)
    candidates: set = set()

    if uploaded:
        try:
            reachable = _rbc_stoichiometry.params_for_metabolites(
                uploaded,
                include_hybrid=include_hybrid,
                include_regulation=include_regulation,
                include_degradation=False,
            )
        except Exception:
            reachable = frozenset()
        candidates.update(reachable)

    if always_include_kernel:
        candidates.update(AUTO_SCOPE_KERNEL)

    if not include_kms:
        candidates = {n for n in candidates if not n.startswith("km_")}

    # Final filter: only return parameters that have a registered
    # (default, lo, hi) triple — guarantees the caller can safely ask the
    # optimiser to vary every returned name.
    filtered = {n for n in candidates if n in DEFAULT_PARAM_VALUES}

    return sorted(filtered)


def auto_scope_with_bounds(
    uploaded_metabolites,
    *,
    base_params=None,
    always_include_kernel: bool = True,
    include_kms: bool = True,
    include_regulation: bool = True,
    include_hybrid: bool = False,
) -> dict:
    """Convenience wrapper: ``{name: (initial, lo, hi)}`` for the auto-scope.

    The ``initial`` value is taken from ``base_params`` when provided,
    otherwise from the ``PHASE_MAP`` default. Lower / upper bounds always
    come from ``DEFAULT_PARAM_BOUNDS`` so the optimiser sees a consistent
    feasible region regardless of the user's seed.
    """
    names = derive_auto_param_scope(
        uploaded_metabolites,
        always_include_kernel=always_include_kernel,
        include_kms=include_kms,
        include_regulation=include_regulation,
        include_hybrid=include_hybrid,
    )

    base_params = base_params or {}
    out: dict = {}
    for name in names:
        bounds = DEFAULT_PARAM_BOUNDS.get(name)
        if bounds is None:
            continue
        default, lo, hi = bounds
        initial = base_params.get(name, default)
        try:
            initial_f = float(initial)
        except (TypeError, ValueError):
            initial_f = float(default)
        # Clip the initial guess into the bounds so downstream samplers don't
        # immediately reject it.
        initial_clipped = float(min(max(initial_f, lo), hi))
        out[name] = (initial_clipped, float(lo), float(hi))
    return out


TRANSPORT_ONLY_PARAM_NAMES = {
    "vmax_VEGLC",
    "vmax_VELAC",
    "vmax_VEXAN",
    "vmax_VEURT",
    "vmax_VEINO",
    "vmax_VEADE_fwd",
    "vmax_VEADE_rev",
    "vmax_VEHYPX",
    "vmax_VEMAL",
    "vmax_VEFUM",
    "vmax_VECIT",
    "vmax_VEGLN",
    "vmax_VEGLU",
    "vmax_VEOXOP",
    "vmax_VESER",
    "vmax_VEARG",
    "vmax_VEGSSG",
    "vmax_VEGSH",
    "vmax_VEASN",
    "vmax_VECYS",
}
EADE_FOCUS_PARAM_NAMES = {"vmax_VAPRT", "vmax_VEADE_fwd", "vmax_VEADE_rev"}
HYBRID_GLUCOSE_LACTATE_PARAM_NAMES = set(PHASE1_HYBRID_TRANSPORT_PARAMS)
HYBRID_DOWNSTREAM_PK_ENO_PARAM_NAMES = set(PHASE1_HYBRID_DOWNSTREAM_PARAMS)
HYBRID_GLUCOSE_LACTATE_PLUS_DOWNSTREAM_PARAM_NAMES = (
    HYBRID_GLUCOSE_LACTATE_PARAM_NAMES | HYBRID_DOWNSTREAM_PK_ENO_PARAM_NAMES
)
HYBRID_TRANSPORT_PARAM_NAMES = {
    "hybrid_blend_VEGLC",
    "hybrid_import_hill_VEGLC",
    "hybrid_export_hill_VEGLC",
    "hybrid_reverse_scale_VEGLC",
    "transport_gate_km_VEGLC",
    "transport_gate_hill_VEGLC",
    "hybrid_blend_VELAC",
    "hybrid_efflux_hill_VELAC",
    "hybrid_backpressure_hill_VELAC",
    "hybrid_backpressure_scale_VELAC",
    "hybrid_km_ELAC",
}

GLYCOLYSIS_FOCUS_PARAM_NAMES = set(PHASE1_BASE_PARAMS)
CORE_KM_ANCHOR_PARAM_NAMES = {
    "km_F6P",
    "km_F16BP",
    "km_PEP",
    "km_PYR",
    "km_LAC",
    "km_EGLC",
}
CORE_KM_SHAPE_PARAM_NAMES = {
    "km_G6P",
    "km_P3G",
    "km_P2G",
    "km_GLC_transport",
    "km_ADP_ATP",
    "km_ATP_HK",
    "km_ATP_PFK",
    "km_NAD_NADH",
    "km_NADH_NAD",
}
CORE_KM_PARAM_NAMES = CORE_KM_ANCHOR_PARAM_NAMES | CORE_KM_SHAPE_PARAM_NAMES
CORE_LOWER_GLYCOLYSIS_PROBE_PARAM_NAMES = {
    "km_P3G",
    "km_P2G",
    "km_PEP",
    "km_PYR",
    "km_ADP_ATP",
    "vmax_VPGK",
    "vmax_VPGM",
    "vmax_VENOPGM",
    "vmax_VPK",
}
CORE_UPSTREAM_GLYCOLYSIS_PROBE_PARAM_NAMES = {
    "km_GLC_HK",
    "km_G6P",
    "km_F6P",
    "km_ATP_HK",
    "km_ATP_PFK",
    "vmax_VHK",
    "vmax_VPFK",
}
PURINE_TRANSPORT_NARROW_PARAM_NAMES = {
    "vmax_VPNPase1",
    "vmax_VXAO",
    "vmax_VXAO2",
    "vmax_VEXAN",
    "vmax_VEURT",
    "vmax_VAPRT",
}

GLYCOLYSIS_TERMINAL_PARAM_NAMES = {
    "vmax_VEGLC",
    "vmax_VELAC",
    "vmax_VHK",
    "vmax_VPGK",
    "vmax_VPK",
    "vmax_VLDH",
    "vmax_VENOPGM",
    "vmax_VPEP_PASE",
    "km_GLC_HK",
    "km_P2G",
    "km_PEP",
    "km_ADP_ATP",
    "km_PYR",
    "km_LAC",
    "km_NADH_NAD",
    "km_GLC_transport",
    "km_EGLC",
    "ki_ATP_PK",
    "ki_PYR_PK",
}
GLYCOLYSIS_TERMINAL_PARAM_NAMES |= HYBRID_GLUCOSE_LACTATE_PLUS_DOWNSTREAM_PARAM_NAMES
GLYCOLYSIS_TERMINAL_PARAMS = {name: PHASE1_PARAMS[name] for name in GLYCOLYSIS_TERMINAL_PARAM_NAMES}
GLYCOLYSIS_TERMINAL_PARAMS["vmax_VELAC"] = (0.580000, 0.2, 10.0)
GLYCOLYSIS_TERMINAL_PARAMS["vmax_VPEP_PASE"] = (0.1, 0.01, 2.0)
HYBRID_GLUCOSE_LACTATE_PARAMS = {
    name: PHASE1_PARAMS[name] for name in HYBRID_GLUCOSE_LACTATE_PARAM_NAMES
}
HYBRID_DOWNSTREAM_PK_ENO_PARAMS = {
    name: PHASE1_PARAMS[name] for name in HYBRID_DOWNSTREAM_PK_ENO_PARAM_NAMES
}
HYBRID_GLUCOSE_LACTATE_PLUS_DOWNSTREAM_PARAMS = {
    name: PHASE1_PARAMS[name] for name in HYBRID_GLUCOSE_LACTATE_PLUS_DOWNSTREAM_PARAM_NAMES
}

EXTRACELLULAR_COUPLED_PARAM_NAMES = {
    "vmax_VEGLC",
    "vmax_VELAC",
    "vmax_VXAO",
    "vmax_VXAO2",
    "vmax_VEXAN",
    "vmax_VEURT",
    "vmax_VAPRT",
    "vmax_VEADE_fwd",
    "vmax_VEADE_rev",
    "vmax_VADSL",
    "vmax_VGLNS",
    "vmax_VEGLN",
    "vmax_VOPLAH",
    "vmax_VGGCT",
    "vmax_VEOXOP",
    "vmax_VFUM",
    "vmax_VEFUM",
    "vmax_VEARG",
}
GLYCOLYSIS_EXTRACELLULAR_PARAM_NAMES = GLYCOLYSIS_FOCUS_PARAM_NAMES | EXTRACELLULAR_COUPLED_PARAM_NAMES
GLYCOLYSIS_EXTRACELLULAR_PARAM_NAMES |= HYBRID_GLUCOSE_LACTATE_PLUS_DOWNSTREAM_PARAM_NAMES


# =============================================================================
# TAXONOMY
# =============================================================================

PARAM_CLASS_VMAX = "vmax"
PARAM_CLASS_KM = "km"
PARAM_CLASS_HYBRID = "hybrid"
PARAM_CLASS_REGULATION = "regulation"
PARAM_CLASS_TRANSPORT = "transport"
PARAM_CLASS_DEGRADATION = "degradation"
PARAM_CLASS_EFFECTIVE_MISC = "effective_misc"

IDENTIFIABLE_CORE = "core"
IDENTIFIABLE_CAUTION = "caution"
STRUCTURAL_COMPENSATION_RISK = "compensation_risk"

TRANSPORT_PARAM_NAMES = {
    "vmax_VEGLC",
    "vmax_VELAC",
    "vmax_VEXAN",
    "vmax_VEURT",
    "vmax_VEINO",
    "vmax_VEADE_fwd",
    "vmax_VEADE_rev",
    "vmax_VEHYPX",
    "vmax_VEMAL",
    "vmax_VEFUM",
    "vmax_VECIT",
    "vmax_VEGLN",
    "vmax_VEGLU",
    "vmax_VEOXOP",
    "vmax_VESER",
    "vmax_VEARG",
    "vmax_VEGSSG",
    "vmax_VEGSH",
    "vmax_VEASN",
    "vmax_VECYS",
    "km_EGLC",
    "km_LAC",
    "km_GLC_transport",
    *HYBRID_TRANSPORT_PARAM_NAMES,
}

DEGRADATION_PARAM_NAMES = {"k_EGSH_deg", "k_EGSSG_deg"}

REGULATION_PARAM_NAMES = {
    "ki_ATP_PK",
    "ki_PYR_PK",
    "ka_F16BP_PK",
    "alpha_F16BP_PK",
    "n_F16BP_PK",
    "km_ADP_ATP",
    "km_NAD_NADH",
    "km_NADH_NAD",
    "km_NADP_NADPH",
    "km_NADPH_NADP",
}

EFFECTIVE_MISC_PARAM_NAMES = {
    "vmax_V23DPGP",
    "vmax_VPEP_PASE",
    "vmax_VNDPK_rev",
    "vmax_VAK_rev",
    "vmax_Vnucleo_GMP",
}

IDENTIFIABLE_CORE_PARAM_NAMES = {
    "vmax_VHK",
    "vmax_VPFK",
    "vmax_VPGK",
    "vmax_VPK",
    "vmax_VLDH",
    "vmax_VEGLC",
    "vmax_VELAC",
    "km_GLC_HK",
    "km_F6P",
    "km_F16BP",
    "km_B13PG",
    "km_PEP",
    "km_PYR",
    "km_EGLC",
    "km_LAC",
}

IDENTIFIABLE_CAUTION_PARAM_NAMES = {
    "km_ADP_ATP",
    "km_NAD_NADH",
    "km_NADH_NAD",
    "ki_ATP_PK",
    "ki_PYR_PK",
    "ka_F16BP_PK",
    "alpha_F16BP_PK",
    "vmax_VEXAN",
    "vmax_VEURT",
    "vmax_VEINO",
    "vmax_VEADE_fwd",
    "vmax_VEADE_rev",
    "vmax_VEGLN",
    "vmax_VEGLU",
    "vmax_VEOXOP",
    "vmax_VEARG",
    "vmax_VEFUM",
    *HYBRID_GLUCOSE_LACTATE_PLUS_DOWNSTREAM_PARAM_NAMES,
}

OPTIMIZATION_STRATEGY_CHOICES = {
    "legacy",
    "hybrid_only",
    "vmax_only",
    "km_only",
    "core_km_then_purine_transport",
    "vmax_then_km",
    "km_then_vmax",
    "joint_vmax_km",
    "staged_full",
}

OPTIMIZATION_STRATEGY_TEMPLATES = {
    "hybrid_only": [
        {"name": "hybrid_only", "parameter_classes": [PARAM_CLASS_HYBRID]},
    ],
    "vmax_only": [
        {"name": "vmax_only", "parameter_classes": [PARAM_CLASS_VMAX]},
    ],
    "km_only": [
        {"name": "km_only", "parameter_classes": [PARAM_CLASS_KM]},
    ],
    "core_km_then_purine_transport": [
        {
            "name": "core_km_anchor",
            "phases": [1],
            "target_scope": "core_glycolysis_energy",
            "param_scope": "core_km",
            "parameter_classes": [PARAM_CLASS_KM],
            "include_params": sorted(CORE_KM_ANCHOR_PARAM_NAMES),
        },
        {
            "name": "core_km_shape_energy",
            "phases": [1],
            "target_scope": "core_glycolysis_energy",
            "param_scope": "core_km",
            "parameter_classes": [PARAM_CLASS_KM],
            "include_params": sorted(CORE_KM_SHAPE_PARAM_NAMES),
        },
        {
            "name": "purine_transport_refine",
            "phases": [2],
            "target_scope": "glycolysis_extracellular",
            "param_scope": "purine_transport_narrow",
            "parameter_classes": [PARAM_CLASS_VMAX],
            "include_params": sorted(PURINE_TRANSPORT_NARROW_PARAM_NAMES),
        },
    ],
    "vmax_then_km": [
        {"name": "vmax_stage", "parameter_classes": [PARAM_CLASS_VMAX]},
        {"name": "km_stage", "parameter_classes": [PARAM_CLASS_KM]},
    ],
    "km_then_vmax": [
        {"name": "km_stage", "parameter_classes": [PARAM_CLASS_KM]},
        {"name": "vmax_stage", "parameter_classes": [PARAM_CLASS_VMAX]},
    ],
    "joint_vmax_km": [
        {"name": "joint_vmax_km", "parameter_classes": [PARAM_CLASS_VMAX, PARAM_CLASS_KM]},
    ],
    "staged_full": [
        {
            "name": "stage_a_vmax_core",
            "parameter_classes": [PARAM_CLASS_VMAX],
            "identifiability_levels": [IDENTIFIABLE_CORE],
        },
        {
            "name": "stage_b_km_core",
            "parameter_classes": [PARAM_CLASS_KM],
            "identifiability_levels": [IDENTIFIABLE_CORE],
        },
        {
            "name": "stage_c_joint_core",
            "parameter_classes": [PARAM_CLASS_VMAX, PARAM_CLASS_KM],
            "identifiability_levels": [IDENTIFIABLE_CORE, IDENTIFIABLE_CAUTION],
        },
        {
            "name": "stage_d_regulation_fine",
            "parameter_classes": [PARAM_CLASS_REGULATION],
            "identifiability_levels": [IDENTIFIABLE_CAUTION],
        },
    ],
}


def normalize_name_list(values):
    if values is None:
        return None
    if isinstance(values, str):
        values = [v.strip() for v in values.split(",") if v.strip()]
    return [str(v) for v in values]


def get_parameter_classes(param_name):
    classes = set()
    if param_name.startswith("vmax_"):
        classes.add(PARAM_CLASS_VMAX)
    if param_name.startswith("km_"):
        classes.add(PARAM_CLASS_KM)
    if param_name.startswith("hybrid_"):
        classes.add(PARAM_CLASS_HYBRID)
    if param_name.startswith("hybrid_km_"):
        classes.add(PARAM_CLASS_KM)
    if param_name.startswith(("ki_", "ka_", "alpha_", "n_")) or param_name in REGULATION_PARAM_NAMES:
        classes.add(PARAM_CLASS_REGULATION)
    if (
        param_name in TRANSPORT_PARAM_NAMES
        or "transport" in param_name
        or param_name.startswith("vmax_VE")
    ):
        classes.add(PARAM_CLASS_TRANSPORT)
    if param_name in DEGRADATION_PARAM_NAMES:
        classes.add(PARAM_CLASS_DEGRADATION)
    if param_name in EFFECTIVE_MISC_PARAM_NAMES or not classes:
        classes.add(PARAM_CLASS_EFFECTIVE_MISC)
    return classes


def get_parameter_identifiability(param_name):
    if param_name in IDENTIFIABLE_CORE_PARAM_NAMES:
        return IDENTIFIABLE_CORE
    if param_name in IDENTIFIABLE_CAUTION_PARAM_NAMES:
        return IDENTIFIABLE_CAUTION
    return STRUCTURAL_COMPENSATION_RISK


def build_parameter_taxonomy():
    all_names = sorted(DEFAULT_PARAM_VALUES)
    taxonomy = {
        "classes": {
            PARAM_CLASS_VMAX: [],
            PARAM_CLASS_KM: [],
            PARAM_CLASS_HYBRID: [],
            PARAM_CLASS_REGULATION: [],
            PARAM_CLASS_TRANSPORT: [],
            PARAM_CLASS_DEGRADATION: [],
            PARAM_CLASS_EFFECTIVE_MISC: [],
        },
        "identifiability": {
            IDENTIFIABLE_CORE: [],
            IDENTIFIABLE_CAUTION: [],
            STRUCTURAL_COMPENSATION_RISK: [],
        },
    }
    for name in all_names:
        for cls in get_parameter_classes(name):
            taxonomy["classes"][cls].append(name)
        taxonomy["identifiability"][get_parameter_identifiability(name)].append(name)
    return taxonomy


def filter_param_dict(
    param_dict,
    parameter_classes=None,
    identifiability_levels=None,
    include_params=None,
    exclude_params=None,
):
    allowed_classes = set(normalize_name_list(parameter_classes) or [])
    allowed_ident = set(normalize_name_list(identifiability_levels) or [])
    include_names = set(normalize_name_list(include_params) or [])
    exclude_names = set(normalize_name_list(exclude_params) or [])

    filtered = {}
    for name, bounds in param_dict.items():
        if include_names and name not in include_names:
            continue
        if name in exclude_names:
            continue
        if allowed_classes and get_parameter_classes(name).isdisjoint(allowed_classes):
            continue
        if allowed_ident and get_parameter_identifiability(name) not in allowed_ident:
            continue
        filtered[name] = bounds
    return filtered


# =============================================================================
# DATA
# =============================================================================

def load_experimental_data(experimental_data=None):
    if experimental_data is not None:
        exp_names = [str(n).strip().upper() for n in experimental_data.get("metabolites", [])]
        exp_values = np.asarray(experimental_data.get("values", []), dtype=float)
        time_exp = np.asarray(experimental_data.get("time_points", []), dtype=float)
        if exp_values.ndim != 2:
            raise ValueError("experimental_data.values must be a 2D matrix [metabolite, timepoint]")
        if len(exp_names) != exp_values.shape[0]:
            raise ValueError(
                "experimental_data.metabolites must align with the first axis of experimental_data.values"
            )
        if time_exp.size != exp_values.shape[1]:
            raise ValueError(
                "experimental_data.time_points must align with the second axis of experimental_data.values"
            )
        name_to_row = {n: i for i, n in enumerate(exp_names)}
        return time_exp, exp_values, name_to_row

    df = pd.read_excel(DATA_DIR / "Data_Bordbar_et_al_exp.xlsx")
    exp_names = [str(n).strip().upper() for n in df.iloc[:, 0].tolist()]
    exp_values = df.iloc[:, 1:].values.astype(float)
    time_exp = np.array([float(c) for c in df.columns[1:]])
    name_to_row = {n: i for i, n in enumerate(exp_names)}
    return time_exp, exp_values, name_to_row


def normalize_teacher_target_weights(weight_map):
    if weight_map is None:
        return {}
    if not isinstance(weight_map, dict):
        raise ValueError("teacher_target_weights must be a dictionary mapping metabolite names to non-negative weights.")

    normalized = {}
    for raw_name, raw_weight in weight_map.items():
        name = str(raw_name).strip().upper()
        if not name:
            continue
        weight = float(raw_weight)
        if weight < 0.0:
            raise ValueError(f"Teacher target weight for {name} must be >= 0.")
        normalized[name] = weight
    return normalized


def resolve_teacher_loss_weights(
    teacher_student_weight=DEFAULT_TEACHER_STUDENT_WEIGHT,
    teacher_curve_weight=None,
    teacher_flux_weight=None,
):
    legacy_weight = float(teacher_student_weight or 0.0)
    split_active = teacher_curve_weight is not None or teacher_flux_weight is not None
    resolved_curve_weight = legacy_weight if teacher_curve_weight is None else float(teacher_curve_weight)
    resolved_flux_weight = legacy_weight if teacher_flux_weight is None else float(teacher_flux_weight)
    if resolved_curve_weight < 0.0:
        raise ValueError("teacher_curve_weight must be >= 0.")
    if resolved_flux_weight < 0.0:
        raise ValueError("teacher_flux_weight must be >= 0.")
    return {
        "legacy_weight": legacy_weight,
        "curve_weight": resolved_curve_weight,
        "flux_weight": resolved_flux_weight,
        "split_active": bool(split_active),
    }


def build_teacher_curve_dataset(
    experimental_data=None,
    target_metabolites=None,
    t_max=46.0,
    dense_points=DEFAULT_TEACHER_DENSE_POINTS,
    out_path=None,
    dataset_label="teacher_curve_dataset",
    teacher_target_weights=None,
    teacher_focus_metabolites=None,
    teacher_focus_weight=DEFAULT_TEACHER_FOCUS_WEIGHT,
):
    time_exp, exp_values, name_to_row = load_experimental_data(experimental_data)
    selected = normalize_name_list(target_metabolites) or DEFAULT_TEACHER_CURVE_METABOLITES
    normalized_target_weights = normalize_teacher_target_weights(teacher_target_weights)
    focus_names = set(normalize_name_list(teacher_focus_metabolites) or [])
    focus_weight = float(teacher_focus_weight)
    if focus_weight < 0.0:
        raise ValueError("teacher_focus_weight must be >= 0.")

    active_mask = (
        np.isfinite(time_exp)
        & (time_exp >= (1.0 - 1e-9))
        & (time_exp <= (float(t_max) + 1e-9))
    )
    active_timepoints = np.asarray(time_exp[active_mask], dtype=float)
    if active_timepoints.size < 2:
        raise ValueError("Teacher curve dataset requires at least two experimental time points within the calibration window.")

    dense_timepoints = np.linspace(1.0, float(t_max), int(max(25, dense_points)))
    teacher_curves = {}
    retained_targets = []

    for name in selected:
        if name not in name_to_row:
            continue
        exp_series = np.asarray(exp_values[name_to_row[name], active_mask], dtype=float)
        interpolator = PchipInterpolator(active_timepoints, exp_series)
        dense_values = interpolator(dense_timepoints)
        retained_targets.append(name)
        teacher_curves[name] = {
            "experimental_timepoints": active_timepoints.tolist(),
            "experimental_values": exp_series.tolist(),
            "dense_values": dense_values.tolist(),
            "method": "pchip",
        }

    if not retained_targets:
        raise ValueError("No requested metabolites were available for teacher curve dataset generation.")

    effective_weights = {}
    for name in retained_targets:
        weight = float(normalized_target_weights.get(name, 1.0))
        if name in focus_names:
            weight *= focus_weight
        effective_weights[name] = weight

    payload = {
        "contract_type": "teacher_curve_dataset",
        "contract_version": 1,
        "dataset_label": str(dataset_label).strip() or "teacher_curve_dataset",
        "teacher_mode": "pure_curve_fit_teacher",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source_experimental_path": str(DATA_DIR / "Data_Bordbar_et_al_exp.xlsx"),
        "t_max": float(t_max),
        "target_metabolites": retained_targets,
        "teacher_target_weights": effective_weights,
        "teacher_focus_metabolites": sorted(name for name in retained_targets if name in focus_names),
        "teacher_focus_weight": float(focus_weight),
        "dense_timepoints": dense_timepoints.tolist(),
        "teacher_curves": teacher_curves,
    }

    if out_path is not None:
        out_file = Path(out_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return payload


def load_teacher_curve_dataset(teacher_dataset_path):
    if teacher_dataset_path is None:
        return None

    dataset_path = Path(teacher_dataset_path)
    if not dataset_path.is_absolute():
        dataset_path = (Path.cwd() / dataset_path).resolve()
    if not dataset_path.exists():
        raise FileNotFoundError(f"Teacher dataset not found: {dataset_path}")

    with open(dataset_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    supported_contracts = {"teacher_curve_dataset", "teacher_flux_dataset"}
    if not isinstance(payload, dict) or payload.get("contract_type") not in supported_contracts:
        raise ValueError(f"Unsupported teacher dataset format: {dataset_path}")

    payload["_dataset_path"] = str(dataset_path)
    return payload


def load_initial_conditions():
    n_with_phi = NUM_BASE_METABOLITES + 1
    metabolite_list = [""] * n_with_phi
    for name, idx in BRODBAR_METABOLITE_MAP.items():
        if idx < n_with_phi:
            metabolite_list[idx] = name
    model = {"metab": metabolite_list}
    x0, _ = parse_initial_conditions(model, str(DATA_DIR / "Initial_conditions_JA_Final.xls"))
    return x0


# =============================================================================
# PARAMETER SELECTION
# =============================================================================

def get_phase_params(phase_num, param_scope="all"):
    phase_params = PHASE_MAP[phase_num]
    if param_scope == "all":
        return phase_params
    if param_scope == "transport_only":
        return {name: bounds for name, bounds in phase_params.items() if name in TRANSPORT_ONLY_PARAM_NAMES}
    if param_scope == "eade_focus":
        return {name: bounds for name, bounds in phase_params.items() if name in EADE_FOCUS_PARAM_NAMES}
    if param_scope == "glycolysis_mm":
        return {name: bounds for name, bounds in phase_params.items() if name in GLYCOLYSIS_FOCUS_PARAM_NAMES}
    if param_scope == "core_km":
        if phase_num != 1:
            return {}
        return {name: bounds for name, bounds in phase_params.items() if name in CORE_KM_PARAM_NAMES}
    if param_scope == "core_lower_glycolysis_probe":
        if phase_num != 1:
            return {}
        return {name: bounds for name, bounds in phase_params.items() if name in CORE_LOWER_GLYCOLYSIS_PROBE_PARAM_NAMES}
    if param_scope == "core_upstream_glycolysis_probe":
        if phase_num != 1:
            return {}
        return {name: bounds for name, bounds in phase_params.items() if name in CORE_UPSTREAM_GLYCOLYSIS_PROBE_PARAM_NAMES}
    if param_scope == "glycolysis_terminal":
        if phase_num != 1:
            return {}
        return GLYCOLYSIS_TERMINAL_PARAMS
    if param_scope == "glycolysis_extracellular":
        return {name: bounds for name, bounds in phase_params.items() if name in GLYCOLYSIS_EXTRACELLULAR_PARAM_NAMES}
    if param_scope == "extracellular_coupled":
        return {name: bounds for name, bounds in phase_params.items() if name in EXTRACELLULAR_COUPLED_PARAM_NAMES}
    if param_scope == "purine_transport_narrow":
        return {name: bounds for name, bounds in phase_params.items() if name in PURINE_TRANSPORT_NARROW_PARAM_NAMES}
    if param_scope == "hybrid_glucose_lactate":
        if phase_num != 1:
            return {}
        return HYBRID_GLUCOSE_LACTATE_PARAMS
    if param_scope == "hybrid_downstream_pk_eno":
        if phase_num != 1:
            return {}
        return HYBRID_DOWNSTREAM_PK_ENO_PARAMS
    if param_scope == "hybrid_glucose_lactate_plus_downstream":
        if phase_num != 1:
            return {}
        return HYBRID_GLUCOSE_LACTATE_PLUS_DOWNSTREAM_PARAMS
    raise ValueError(f"Unsupported param_scope: {param_scope}")


# AGENT_EDITABLE_START: stage_planning
def get_phase_params_filtered(
    phase_num,
    param_scope="all",
    parameter_classes=None,
    identifiability_levels=None,
    include_params=None,
    exclude_params=None,
):
    base = get_phase_params(phase_num, param_scope=param_scope)
    return filter_param_dict(
        base,
        parameter_classes=parameter_classes,
        identifiability_levels=identifiability_levels,
        include_params=include_params,
        exclude_params=exclude_params,
    )


def adjust_bounds_for_strategy(param_name, bounds, parameter_classes=None):
    default, lo, hi = bounds
    classes = get_parameter_classes(param_name)
    requested = set(normalize_name_list(parameter_classes) or [])

    if not requested:
        return (default, lo, hi)

    if PARAM_CLASS_KM in classes and PARAM_CLASS_KM in requested:
        center = max(default, 1e-8)
        return (default, max(lo, center / 10.0), min(hi, center * 10.0))

    if PARAM_CLASS_REGULATION in classes and PARAM_CLASS_REGULATION in requested:
        center = max(default, 1e-8)
        return (default, max(lo, center / 5.0), min(hi, center * 5.0))

    if PARAM_CLASS_DEGRADATION in classes and PARAM_CLASS_DEGRADATION in requested:
        center = max(default, 1e-8)
        return (default, max(lo, center / 3.0), min(hi, center * 3.0))

    if PARAM_CLASS_HYBRID in classes and PARAM_CLASS_HYBRID in requested:
        if "blend" in param_name:
            return (default, max(lo, 0.0), min(hi, 0.75))
        if "hill" in param_name:
            return (default, max(lo, 0.5), min(hi, 3.0))
        if "scale" in param_name:
            center = max(default, 1e-8)
            return (default, max(lo, center / 5.0), min(hi, max(center * 2.0, 0.5)))
        if param_name.startswith("hybrid_km_"):
            center = max(default, 1e-8)
            return (default, max(lo, center / 10.0), min(hi, center * 2.5))

    return (default, lo, hi)


def build_stage_phase_params(stage_config, default_param_scope):
    stage_phase_map = {}
    param_scope = stage_config.get("param_scope", default_param_scope)
    parameter_classes = stage_config.get("parameter_classes")
    identifiability_levels = stage_config.get("identifiability_levels")
    include_params = stage_config.get("include_params")
    exclude_params = stage_config.get("exclude_params")

    for phase_num in stage_config["phases"]:
        filtered = get_phase_params_filtered(
            phase_num,
            param_scope=param_scope,
            parameter_classes=parameter_classes,
            identifiability_levels=identifiability_levels,
            include_params=include_params,
            exclude_params=exclude_params,
        )
        filtered = {
            name: adjust_bounds_for_strategy(name, bounds, parameter_classes=parameter_classes)
            for name, bounds in filtered.items()
        }
        stage_phase_map[phase_num] = filtered
    return stage_phase_map


def normalize_stage_config(stage, default_cfg):
    stage = dict(stage)

    if "phases" not in stage and "phase_order" in stage:
        stage["phases"] = stage["phase_order"]
    if "identifiability_levels" not in stage and "identifiability_filter" in stage:
        stage["identifiability_levels"] = stage["identifiability_filter"]

    stage.setdefault("name", f"stage_{default_cfg['index']}")
    stage.setdefault("phases", list(default_cfg["phases"]))
    stage.setdefault("param_scope", default_cfg["param_scope"])
    stage.setdefault("target_scope", default_cfg["target_scope"])
    stage.setdefault("parameter_classes", default_cfg["parameter_classes"])
    stage.setdefault("identifiability_levels", None)
    stage.setdefault("include_params", None)
    stage.setdefault("exclude_params", None)
    stage.setdefault("n_trials", default_cfg["n_trials"])
    stage.setdefault("global_trials", default_cfg["global_trials"])
    stage.setdefault("atp_focus", default_cfg["atp_focus"])
    stage.setdefault("atp_floor", default_cfg["atp_floor"])
    stage.setdefault("adp_floor", default_cfg["adp_floor"])
    stage.setdefault("amp_floor", default_cfg["amp_floor"])
    stage.setdefault("imp_floor", default_cfg["imp_floor"])
    stage.setdefault("adenylate_target", default_cfg["adenylate_target"])
    stage.setdefault("atp_penalty_weight", default_cfg["atp_penalty_weight"])
    stage.setdefault("amp_penalty_weight", default_cfg["amp_penalty_weight"])
    stage.setdefault("imp_penalty_weight", default_cfg["imp_penalty_weight"])
    stage.setdefault("pool_penalty_weight", default_cfg["pool_penalty_weight"])
    stage.setdefault("curve_fit_strength", default_cfg["curve_fit_strength"])
    stage.setdefault("seed", default_cfg["seed"])
    stage.setdefault("teacher_dataset_path", default_cfg["teacher_dataset_path"])
    stage.setdefault("teacher_student_weight", default_cfg["teacher_student_weight"])
    stage.setdefault("teacher_curve_weight", default_cfg.get("teacher_curve_weight"))
    stage.setdefault("teacher_flux_weight", default_cfg.get("teacher_flux_weight"))
    stage.setdefault("teacher_target_weights", default_cfg["teacher_target_weights"])
    stage.setdefault("teacher_focus_metabolites", default_cfg["teacher_focus_metabolites"])
    stage.setdefault("teacher_focus_weight", default_cfg["teacher_focus_weight"])
    stage.setdefault("reject_eglc_final_increase_frac", default_cfg.get("reject_eglc_final_increase_frac"))
    stage.setdefault("reject_elac_final_drop_frac", default_cfg.get("reject_elac_final_drop_frac"))

    stage["phases"] = [int(p) for p in stage["phases"]]
    stage["parameter_classes"] = normalize_name_list(stage.get("parameter_classes"))
    stage["identifiability_levels"] = normalize_name_list(stage.get("identifiability_levels"))
    stage["include_params"] = normalize_name_list(stage.get("include_params"))
    stage["exclude_params"] = normalize_name_list(stage.get("exclude_params"))
    if stage.get("teacher_dataset_path") is not None:
        stage["teacher_dataset_path"] = str(stage["teacher_dataset_path"])
    teacher_weight_cfg = resolve_teacher_loss_weights(
        teacher_student_weight=stage.get("teacher_student_weight", 0.0),
        teacher_curve_weight=stage.get("teacher_curve_weight"),
        teacher_flux_weight=stage.get("teacher_flux_weight"),
    )
    stage["teacher_student_weight"] = teacher_weight_cfg["legacy_weight"]
    stage["teacher_curve_weight"] = teacher_weight_cfg["curve_weight"]
    stage["teacher_flux_weight"] = teacher_weight_cfg["flux_weight"]
    stage["teacher_weight_split_active"] = teacher_weight_cfg["split_active"]
    stage["teacher_target_weights"] = normalize_teacher_target_weights(stage.get("teacher_target_weights"))
    stage["teacher_focus_metabolites"] = normalize_name_list(stage.get("teacher_focus_metabolites"))
    stage["teacher_focus_weight"] = float(stage.get("teacher_focus_weight", DEFAULT_TEACHER_FOCUS_WEIGHT))
    if stage.get("reject_eglc_final_increase_frac") is not None:
        stage["reject_eglc_final_increase_frac"] = float(stage["reject_eglc_final_increase_frac"])
    if stage.get("reject_elac_final_drop_frac") is not None:
        stage["reject_elac_final_drop_frac"] = float(stage["reject_elac_final_drop_frac"])

    return stage


def resolve_stage_plan(
    optimization_strategy,
    phases,
    param_scope,
    target_scope,
    n_trials,
    global_trials,
    seed,
    parameter_classes=None,
    atp_focus=False,
    atp_floor=0.15,
    adp_floor=0.05,
    amp_floor=0.04,
    imp_floor=0.02,
    adenylate_target=0.65,
    atp_penalty_weight=10.0,
    amp_penalty_weight=6.0,
    imp_penalty_weight=5.0,
    pool_penalty_weight=12.0,
    curve_fit_strength=0.0,
    teacher_dataset_path=None,
    teacher_student_weight=DEFAULT_TEACHER_STUDENT_WEIGHT,
    teacher_curve_weight=None,
    teacher_flux_weight=None,
    teacher_target_weights=None,
    teacher_focus_metabolites=None,
    teacher_focus_weight=DEFAULT_TEACHER_FOCUS_WEIGHT,
    reject_eglc_final_increase_frac=None,
    reject_elac_final_drop_frac=None,
    stage_plan=None,
):
    default_cfg = {
        "index": 1,
        "phases": list(phases),
        "param_scope": param_scope,
        "target_scope": target_scope,
        "parameter_classes": parameter_classes,
        "n_trials": n_trials,
        "global_trials": global_trials,
        "seed": seed,
        "atp_focus": atp_focus,
        "atp_floor": atp_floor,
        "adp_floor": adp_floor,
        "amp_floor": amp_floor,
        "imp_floor": imp_floor,
        "adenylate_target": adenylate_target,
        "atp_penalty_weight": atp_penalty_weight,
        "amp_penalty_weight": amp_penalty_weight,
        "imp_penalty_weight": imp_penalty_weight,
        "pool_penalty_weight": pool_penalty_weight,
        "curve_fit_strength": curve_fit_strength,
        "teacher_dataset_path": teacher_dataset_path,
        "teacher_student_weight": teacher_student_weight,
        "teacher_curve_weight": teacher_curve_weight,
        "teacher_flux_weight": teacher_flux_weight,
        "teacher_target_weights": normalize_teacher_target_weights(teacher_target_weights),
        "teacher_focus_metabolites": normalize_name_list(teacher_focus_metabolites),
        "teacher_focus_weight": float(teacher_focus_weight),
        "reject_eglc_final_increase_frac": reject_eglc_final_increase_frac,
        "reject_elac_final_drop_frac": reject_elac_final_drop_frac,
    }

    if stage_plan is None:
        if optimization_strategy == "legacy" and parameter_classes is None:
            raw_plan = [{"name": "legacy"}]
        else:
            raw_plan = OPTIMIZATION_STRATEGY_TEMPLATES.get(optimization_strategy)
            if raw_plan is None:
                raise ValueError(f"Unsupported optimization_strategy: {optimization_strategy}")
    else:
        raw_plan = stage_plan

    resolved = []
    for idx, raw_stage in enumerate(raw_plan, start=1):
        cfg = dict(default_cfg)
        cfg["index"] = idx
        stage = normalize_stage_config(raw_stage, cfg)
        stage["phase_params"] = build_stage_phase_params(stage, stage["param_scope"])
        stage["selected_param_names"] = sorted({p for d in stage["phase_params"].values() for p in d})
        resolved.append(stage)
    return resolved


# AGENT_EDITABLE_END: stage_planning
# =============================================================================
# OBJECTIVE
# =============================================================================

class ObjectiveFunction:
    def __init__(
        self,
        x0,
        time_exp,
        exp_values,
        name_to_row,
        t_max=46,
        target_scope="all",
        target_names=None,
        objective_name=None,
        endpoint_target_names=None,
        endpoint_weight=None,
        atp_focus=False,
        atp_floor=0.15,
        adp_floor=0.05,
        amp_floor=0.04,
        imp_floor=0.02,
        adenylate_target=0.65,
        atp_penalty_weight=10.0,
        amp_penalty_weight=6.0,
        imp_penalty_weight=5.0,
        pool_penalty_weight=12.0,
        curve_fit_strength=0.0,
        teacher_dataset=None,
        teacher_student_weight=DEFAULT_TEACHER_STUDENT_WEIGHT,
        teacher_curve_weight=None,
        teacher_flux_weight=None,
        teacher_target_weights=None,
        teacher_focus_metabolites=None,
        teacher_focus_weight=DEFAULT_TEACHER_FOCUS_WEIGHT,
    ):
        self.x0 = x0
        self.time_exp = time_exp
        self.exp_values = exp_values
        self.name_to_row = name_to_row
        self.t_max = t_max
        self.target_scope = target_scope
        self.objective_name = objective_name or target_scope
        self.atp_focus = atp_focus
        self.atp_floor = atp_floor
        self.adp_floor = adp_floor
        self.amp_floor = amp_floor
        self.imp_floor = imp_floor
        self.adenylate_target = adenylate_target
        self.atp_penalty_weight = atp_penalty_weight
        self.amp_penalty_weight = amp_penalty_weight
        self.imp_penalty_weight = imp_penalty_weight
        self.pool_penalty_weight = pool_penalty_weight
        self.curve_fit_strength = curve_fit_strength
        teacher_weight_cfg = resolve_teacher_loss_weights(
            teacher_student_weight=teacher_student_weight,
            teacher_curve_weight=teacher_curve_weight,
            teacher_flux_weight=teacher_flux_weight,
        )
        self.teacher_student_weight = teacher_weight_cfg["legacy_weight"]
        self.teacher_curve_weight = teacher_weight_cfg["curve_weight"]
        self.teacher_flux_weight = teacher_weight_cfg["flux_weight"]
        self.teacher_weight_split_active = teacher_weight_cfg["split_active"]
        self.teacher_target_weight_overrides = normalize_teacher_target_weights(teacher_target_weights)
        self.teacher_focus_metabolites = set(normalize_name_list(teacher_focus_metabolites) or [])
        self.teacher_focus_weight = float(teacher_focus_weight if teacher_focus_weight is not None else DEFAULT_TEACHER_FOCUS_WEIGHT)
        if self.teacher_focus_weight < 0.0:
            raise ValueError("teacher_focus_weight must be >= 0.")
        self.dynamic_eps = 1e-6
        self.level_weight = 1.0
        self.slope_weight = 0.35
        self.curve_endpoint_weight = 0.50
        self.fold_weight = 0.30
        self.regularization_rank_weight = FIT_FIRST_REGULARIZATION_WEIGHT
        self.physiological_rank_weight = FIT_FIRST_PHYSIOLOGICAL_WEIGHT

        if target_scope not in {"all", "extracellular", "glycolysis", "glycolysis_terminal", "glycolysis_extracellular", "core_glycolysis_energy"}:
            raise ValueError(f"Unsupported target_scope: {target_scope}")

        raw_time_exp = np.asarray(time_exp, dtype=float)
        self.active_exp_mask = (
            np.isfinite(raw_time_exp)
            & (raw_time_exp >= (1.0 - 1e-9))
            & (raw_time_exp <= (self.t_max + 1e-9))
        )
        self.active_time_exp = raw_time_exp[self.active_exp_mask]
        if self.active_time_exp.size == 0:
            raise ValueError(
                f"No experimental time points available within the supported calibration window "
                f"[1, {self.t_max}]"
            )

        self.t_eval_dense = np.linspace(1, t_max, 200)
        self.t_eval_fast = np.sort(np.unique(np.concatenate(([1], self.active_time_exp))))

        self.target_names = []
        self.target_indices = []
        self.target_exp = []
        self.target_weights = []

        selected_target_names = set(target_names) if target_names is not None else resolve_target_scope_metabolites(target_scope)
        scope_weight_overrides = TARGET_SCOPE_WEIGHT_OVERRIDES.get(
            self.objective_name,
            TARGET_SCOPE_WEIGHT_OVERRIDES.get(self.target_scope, {}),
        )
        self.scope_weight_overrides = scope_weight_overrides

        for ename, midx in EXP_TO_MODEL.items():
            if ename not in selected_target_names:
                continue
            if ename not in name_to_row:
                continue

            row = name_to_row[ename]
            self.target_names.append(ename)
            self.target_indices.append(midx)
            self.target_exp.append(exp_values[row, self.active_exp_mask])

            if ename in CRITICAL_WEIGHT_METABOLITES:
                w = CRITICAL_WEIGHT_METABOLITES[ename]
            elif ename in HIGH_WEIGHT_METABOLITES:
                w = 2.0
            else:
                w = 1.0
            if ename in scope_weight_overrides:
                w = max(w, scope_weight_overrides[ename])
            self.target_weights.append(w)

        if not self.target_names:
            raise ValueError(f"No experimental targets found for target_scope='{self.target_scope}'")

        self.target_exp = np.array(self.target_exp)
        self.target_weights = np.array(self.target_weights)
        self.n_targets = len(self.target_names)

        self.screen_exp_positions = np.unique(
            np.linspace(0, self.target_exp.shape[1] - 1, min(5, self.target_exp.shape[1]), dtype=int)
        )
        self.screen_time_exp = self.active_time_exp[self.screen_exp_positions]
        self.target_exp_screen = self.target_exp[:, self.screen_exp_positions]

        resolved_endpoint_target_names = (
            set(endpoint_target_names)
            if endpoint_target_names is not None
            else TARGET_SCOPE_ENDPOINT_METABOLITES.get(
                self.objective_name,
                TARGET_SCOPE_ENDPOINT_METABOLITES.get(self.target_scope, set()),
            )
        )

        self.endpoint_weight = (
            endpoint_weight
            if endpoint_weight is not None
            else TARGET_SCOPE_ENDPOINT_WEIGHTS.get(
                self.objective_name,
                TARGET_SCOPE_ENDPOINT_WEIGHTS.get(self.target_scope, 0.0),
            )
        )

        self.endpoint_mask = np.array(
            [name in resolved_endpoint_target_names for name in self.target_names],
            dtype=bool,
        )

        self.norm_factors = np.maximum(np.mean(np.abs(self.target_exp), axis=1), 0.01)

        self.atp_idx = 35
        self.adp_idx = 36
        self.amp_idx = 37
        self.imp_idx = EXP_TO_MODEL["IMP"]
        self.init_adenylate_pool = float(max(x0[self.atp_idx] + x0[self.adp_idx] + x0[self.amp_idx], 1e-8))

        self.exp_pool_trajectory = None
        if "ATP" in name_to_row and "ADP" in name_to_row and "AMP" in name_to_row:
            atp_exp = exp_values[name_to_row["ATP"], self.active_exp_mask]
            adp_exp = exp_values[name_to_row["ADP"], self.active_exp_mask]
            amp_exp = exp_values[name_to_row["AMP"], self.active_exp_mask]
            self.exp_pool_trajectory = atp_exp + adp_exp + amp_exp

        self.screen_pool_trajectory = None
        if self.exp_pool_trajectory is not None:
            self.screen_pool_trajectory = self.exp_pool_trajectory[self.screen_exp_positions]

        self.nad_idx = 75
        self.nadh_idx = 76
        self.nadp_idx = 77
        self.nadph_idx = 78
        self.init_nad_pool = float(x0[self.nad_idx] + x0[self.nadh_idx])
        self.init_nadp_pool = float(x0[self.nadp_idx] + x0[self.nadph_idx])

        self.target_caps = np.full(self.n_targets, NRMSE_CAP, dtype=float)
        if self.atp_focus:
            atp_like_mask = np.isin(self.target_names, ["ATP", "ADP", "AMP"])
            self.target_caps[atp_like_mask] = 50.0

        self.teacher_dataset_label = None
        self.teacher_dataset_path = None
        self.teacher_target_weight_map = {}
        self.teacher_target_names = []
        self.teacher_target_indices = np.array([], dtype=int)
        self.teacher_curve_values = None
        self.teacher_target_weights = np.array([], dtype=float)
        self.teacher_norm_factors = np.array([], dtype=float)
        self.teacher_target_caps = np.array([], dtype=float)
        self.teacher_flux_names = []
        self.teacher_flux_values = None
        self.teacher_flux_weights = np.array([], dtype=float)
        self.teacher_flux_norm_factors = np.array([], dtype=float)
        self.teacher_flux_caps = np.array([], dtype=float)
        self.teacher_flux_weight_map = {}
        self.teacher_timepoints = None
        self.teacher_loss_mode = "inactive"
        self.teacher_curve_loss_active = False
        self.teacher_flux_loss_active = False
        self._configure_teacher_dataset(teacher_dataset)

        self.default_param_values = DEFAULT_PARAM_VALUES

        self.t_eval_screen = np.sort(np.unique(np.concatenate(([1], self.active_time_exp[self.screen_exp_positions]))))
        self.t_eval_report = np.sort(np.unique(np.concatenate((self.t_eval_fast, [t_max]))))
        self.exp_eval_indices = np.searchsorted(self.t_eval_fast, self.active_time_exp)
        self.screen_eval_indices = np.searchsorted(self.t_eval_screen, self.active_time_exp[self.screen_exp_positions])
        self.report_exp_indices = np.searchsorted(self.t_eval_report, self.active_time_exp)
        self.report_final_index = int(np.searchsorted(self.t_eval_report, self.t_max))

        self._solve_cache = {}
        self.n_calls = 0
        self.best_loss = float("inf")
        self.best_params = None
        self.best_loss_breakdown = None

    @staticmethod
    def _params_cache_key(custom_params):
        if not custom_params:
            return ()
        normalized_items = []
        for pname, pval in custom_params.items():
            if isinstance(pval, (int, float, np.integer, np.floating)):
                normalized_items.append((pname, float(pval)))
            else:
                normalized_items.append((pname, str(pval)))
        return tuple(sorted(normalized_items))

    def _weight_for_metabolite(self, metabolite_name):
        if metabolite_name in CRITICAL_WEIGHT_METABOLITES:
            weight = CRITICAL_WEIGHT_METABOLITES[metabolite_name]
        elif metabolite_name in HIGH_WEIGHT_METABOLITES:
            weight = 2.0
        else:
            weight = 1.0
        if metabolite_name in self.scope_weight_overrides:
            weight = max(weight, self.scope_weight_overrides[metabolite_name])
        return float(weight)

    def _configure_teacher_dataset(self, teacher_dataset):
        self.t_eval_dense = np.linspace(1, self.t_max, DEFAULT_TEACHER_DENSE_POINTS)
        if teacher_dataset is None:
            return

        curve_supervision_active = self.teacher_curve_weight > 0.0 or (
            not self.teacher_weight_split_active and self.teacher_student_weight > 0.0
        )
        flux_supervision_active = self.teacher_flux_weight > 0.0 or (
            not self.teacher_weight_split_active and self.teacher_student_weight > 0.0
        )
        if not curve_supervision_active and not flux_supervision_active:
            return

        if not isinstance(teacher_dataset, dict):
            raise ValueError("teacher_dataset must be a dictionary payload or None.")

        raw_timepoints = np.asarray(teacher_dataset.get("dense_timepoints", []), dtype=float)
        if raw_timepoints.size == 0:
            raise ValueError("teacher_dataset.dense_timepoints must be a non-empty array.")

        active_mask = (
            np.isfinite(raw_timepoints)
            & (raw_timepoints >= (1.0 - 1e-9))
            & (raw_timepoints <= (self.t_max + 1e-9))
        )
        teacher_timepoints = raw_timepoints[active_mask]
        if teacher_timepoints.size < 2:
            raise ValueError("Teacher dataset contains fewer than two active time points inside the calibration window.")

        teacher_curves = teacher_dataset.get("teacher_curves", {})
        teacher_flux_curves = teacher_dataset.get("reaction_flux_curves", {})
        selected_names = normalize_name_list(teacher_dataset.get("target_metabolites")) or DEFAULT_TEACHER_CURVE_METABOLITES
        dataset_target_weights = normalize_teacher_target_weights(teacher_dataset.get("teacher_target_weights"))
        dataset_focus_metabolites = set(normalize_name_list(teacher_dataset.get("teacher_focus_metabolites")) or [])
        dataset_focus_weight = float(teacher_dataset.get("teacher_focus_weight", DEFAULT_TEACHER_FOCUS_WEIGHT))
        if dataset_focus_weight < 0.0:
            raise ValueError("teacher_dataset.teacher_focus_weight must be >= 0.")

        curve_values = []
        target_weights = []
        norm_factors = []
        target_caps = []
        retained_names = []
        retained_indices = []
        effective_weight_map = {}
        flux_values = []
        flux_weights = []
        flux_norm_factors = []
        flux_caps = []
        flux_names = []
        flux_weight_map = {}

        if curve_supervision_active:
            for metabolite_name in selected_names:
                if metabolite_name not in EXP_TO_MODEL:
                    continue
                curve_entry = teacher_curves.get(metabolite_name)
                if not isinstance(curve_entry, dict):
                    continue
                dense_values = np.asarray(curve_entry.get("dense_values", []), dtype=float)
                if dense_values.size != raw_timepoints.size:
                    raise ValueError(
                        f"Teacher dataset dense_values for {metabolite_name} do not align with dense_timepoints."
                    )
                active_values = dense_values[active_mask]
                retained_names.append(metabolite_name)
                retained_indices.append(EXP_TO_MODEL[metabolite_name])
                curve_values.append(active_values)
                effective_weight = self._weight_for_metabolite(metabolite_name)
                effective_weight *= float(dataset_target_weights.get(metabolite_name, 1.0))
                effective_weight *= float(self.teacher_target_weight_overrides.get(metabolite_name, 1.0))
                if metabolite_name in dataset_focus_metabolites:
                    effective_weight *= dataset_focus_weight
                if metabolite_name in self.teacher_focus_metabolites:
                    effective_weight *= self.teacher_focus_weight
                target_weights.append(effective_weight)
                effective_weight_map[metabolite_name] = float(effective_weight)
                norm_factors.append(float(max(np.mean(np.abs(active_values)), 0.01)))
                cap = 50.0 if self.atp_focus and metabolite_name in {"ATP", "ADP", "AMP"} else NRMSE_CAP
                target_caps.append(float(cap))

        if flux_supervision_active:
            reaction_to_metabolite = {}
            for reaction_name, reaction_entry in teacher_flux_curves.items():
                if not isinstance(reaction_entry, dict):
                    continue
                dense_values = np.asarray(reaction_entry.get("dense_values", []), dtype=float)
                if dense_values.size != raw_timepoints.size:
                    raise ValueError(
                        f"Teacher flux dense_values for {reaction_name} do not align with dense_timepoints."
                    )
                active_values = dense_values[active_mask]
                source_metabolite = reaction_entry.get("source_metabolite")
                effective_weight = 1.0
                if isinstance(source_metabolite, str) and source_metabolite:
                    effective_weight = self._weight_for_metabolite(source_metabolite)
                    effective_weight *= float(dataset_target_weights.get(source_metabolite, 1.0))
                    effective_weight *= float(self.teacher_target_weight_overrides.get(source_metabolite, 1.0))
                    if source_metabolite in dataset_focus_metabolites:
                        effective_weight *= dataset_focus_weight
                    if source_metabolite in self.teacher_focus_metabolites:
                        effective_weight *= self.teacher_focus_weight
                    reaction_to_metabolite[reaction_name] = source_metabolite
                flux_names.append(str(reaction_name))
                flux_values.append(active_values)
                flux_weights.append(float(effective_weight))
                flux_weight_map[str(reaction_name)] = float(effective_weight)
                flux_norm_factors.append(float(max(np.mean(np.abs(active_values)), 0.01)))
                flux_caps.append(float(NRMSE_CAP))

        if not retained_names and not flux_names:
            raise ValueError("Teacher dataset does not contain any compatible curve or flux targets for calibration.")

        self.teacher_dataset_label = teacher_dataset.get("dataset_label") or teacher_dataset.get("contract_type")
        self.teacher_dataset_path = teacher_dataset.get("_dataset_path")
        self.teacher_target_weight_map = effective_weight_map
        self.teacher_target_names = retained_names
        self.teacher_target_indices = np.asarray(retained_indices, dtype=int)
        self.teacher_curve_values = np.asarray(curve_values, dtype=float) if curve_values else None
        self.teacher_target_weights = np.asarray(target_weights, dtype=float)
        self.teacher_norm_factors = np.asarray(norm_factors, dtype=float)
        self.teacher_target_caps = np.asarray(target_caps, dtype=float)
        self.teacher_flux_names = flux_names
        self.teacher_flux_values = np.asarray(flux_values, dtype=float) if flux_values else None
        self.teacher_flux_weights = np.asarray(flux_weights, dtype=float)
        self.teacher_flux_norm_factors = np.asarray(flux_norm_factors, dtype=float)
        self.teacher_flux_caps = np.asarray(flux_caps, dtype=float)
        self.teacher_flux_weight_map = flux_weight_map
        self.teacher_timepoints = np.asarray(teacher_timepoints, dtype=float)
        self.teacher_curve_loss_active = self.teacher_curve_values is not None
        self.teacher_flux_loss_active = self.teacher_flux_values is not None
        self.teacher_loss_mode = (
            "curve_and_flux_teacher"
            if self.teacher_curve_values is not None and self.teacher_flux_values is not None
            else "pure_flux_teacher"
            if self.teacher_flux_values is not None
            else "pure_curve_fit_teacher"
        )
        self.t_eval_dense = self.teacher_timepoints

    def _simulated_teacher_flux_values(self, custom_params, y_dense):
        if self.teacher_flux_values is None or not self.teacher_flux_names:
            return None

        params = self.default_param_values.copy()
        if custom_params:
            params.update(custom_params)

        sim_flux_values = []
        for reaction_name in self.teacher_flux_names:
            reaction_series = []
            for idx, t in enumerate(self.teacher_timepoints):
                x = y_dense[:, idx]
                if reaction_name == "VEGLC":
                    reaction_series.append(
                        _compute_veglc_flux(
                            float(t),
                            x,
                            custom_params,
                            float(params["vmax_VEGLC"]),
                            float(params["km_EGLC"]),
                            float(params["km_GLC_transport"]),
                        )
                    )
                elif reaction_name == "VELAC":
                    reaction_series.append(
                        _compute_velac_flux(
                            float(t),
                            x,
                            custom_params,
                            float(params["vmax_VELAC"]),
                            float(params["km_LAC"]),
                        )
                    )
                elif reaction_name == "VLDH":
                    reaction_series.append(
                        _compute_vldh_flux(
                            x,
                            custom_params,
                            float(t),
                            1.0,
                            float(params["vmax_VLDH"]),
                            float(params["km_PYR"]),
                            float(params["km_LAC"]),
                            float(params["km_NADH_NAD"]),
                            float(params["km_NAD_NADH"]),
                            float(x[self.nad_idx]),
                            float(x[self.nadh_idx]),
                        )
                    )
                else:
                    raise ValueError(f"Unsupported teacher flux reaction target: {reaction_name}")
            sim_flux_values.append(reaction_series)
        return np.asarray(sim_flux_values, dtype=float)

    def _teacher_student_loss(self, custom_params):
        teacher_supervision_active = (
            self.teacher_student_weight > 0.0
            or self.teacher_curve_weight > 0.0
            or self.teacher_flux_weight > 0.0
        )
        if (
            self.teacher_curve_values is None
            and self.teacher_flux_values is None
        ) or not teacher_supervision_active:
            return {
                "curve_loss": 0.0,
                "flux_loss": 0.0,
                "curve_weight_sum": 0.0,
                "flux_weight_sum": 0.0,
                "combined_loss": 0.0,
                "weighted_loss": 0.0,
            }

        sol_dense = self._cached_solve(custom_params, mode="dense")
        if not sol_dense.success:
            return {
                "curve_loss": float("inf"),
                "flux_loss": float("inf"),
                "curve_weight_sum": 0.0,
                "flux_weight_sum": 0.0,
                "combined_loss": float("inf"),
                "weighted_loss": float("inf"),
            }

        y_dense = np.maximum(sol_dense.y, 0.0)
        curve_loss = 0.0
        flux_loss = 0.0
        curve_weight_sum = 0.0
        flux_weight_sum = 0.0

        if self.teacher_curve_values is not None and self.teacher_target_indices.size > 0:
            sim_teacher = y_dense[self.teacher_target_indices]
            rmse = np.sqrt(np.mean((sim_teacher - self.teacher_curve_values) ** 2, axis=1))
            nrmses = np.minimum(rmse / self.teacher_norm_factors, self.teacher_target_caps)
            curve_weight_sum = float(np.sum(self.teacher_target_weights))
            if curve_weight_sum > 0.0:
                curve_loss = float(np.average(nrmses, weights=self.teacher_target_weights))

        if self.teacher_flux_values is not None and self.teacher_flux_names:
            sim_flux = self._simulated_teacher_flux_values(custom_params, y_dense)
            rmse_flux = np.sqrt(np.mean((sim_flux - self.teacher_flux_values) ** 2, axis=1))
            nrmses_flux = np.minimum(rmse_flux / self.teacher_flux_norm_factors, self.teacher_flux_caps)
            flux_weight_sum = float(np.sum(self.teacher_flux_weights))
            if flux_weight_sum > 0.0:
                flux_loss = float(np.average(nrmses_flux, weights=self.teacher_flux_weights))

        if curve_weight_sum <= 0.0 and flux_weight_sum <= 0.0:
            combined_loss = 0.0
        elif curve_weight_sum <= 0.0:
            combined_loss = flux_loss
        elif flux_weight_sum <= 0.0:
            combined_loss = curve_loss
        else:
            combined_loss = float(
                np.average(
                    np.asarray([curve_loss, flux_loss], dtype=float),
                    weights=np.asarray([curve_weight_sum, flux_weight_sum], dtype=float),
                )
            )

        if self.teacher_weight_split_active:
            weighted_loss = (
                self.teacher_curve_weight * curve_loss
                + self.teacher_flux_weight * flux_loss
            )
        else:
            weighted_loss = self.teacher_student_weight * combined_loss

        return {
            "curve_loss": float(curve_loss),
            "flux_loss": float(flux_loss),
            "curve_weight_sum": float(curve_weight_sum),
            "flux_weight_sum": float(flux_weight_sum),
            "combined_loss": float(combined_loss),
            "weighted_loss": float(weighted_loss),
        }

    def _cached_solve(self, custom_params, mode="fast"):
        cache_key = (mode, self._params_cache_key(custom_params))
        cached = self._solve_cache.get(cache_key)
        if cached is not None:
            return cached

        if mode == "fast":
            t_eval = self.t_eval_report
            rtol, atol = 1e-5, 1e-7
        elif mode == "screen":
            t_eval = self.t_eval_report
            rtol, atol = 1e-5, 1e-7
        elif mode == "report":
            t_eval = self.t_eval_report
            rtol, atol = 1e-5, 1e-7
        elif mode == "dense":
            t_eval = self.t_eval_dense
            rtol, atol = 1e-5, 1e-7
        else:
            raise ValueError(f"Unsupported solve mode: {mode}")

        sol = solve_ivp(
            lambda t, y: equadiff_brodbar(t, y, custom_params=custom_params, curve_fit_strength=self.curve_fit_strength),
            (1, self.t_max),
            self.x0,
            method="LSODA",
            t_eval=t_eval,
            rtol=rtol,
            atol=atol,
        )

        self._solve_cache[cache_key] = sol
        if len(self._solve_cache) > SOLVE_CACHE_SIZE:
            oldest_key = next(iter(self._solve_cache))
            self._solve_cache.pop(oldest_key, None)

        return sol

    def _level_loss(self, sim_targets, target_exp):
        rmse = np.sqrt(np.mean((sim_targets - target_exp) ** 2, axis=1))
        nrmses = np.minimum(rmse / self.norm_factors, self.target_caps)
        loss = np.average(nrmses, weights=self.target_weights)
        return float(self.level_weight * loss)

    def _target_loss(self, sim_targets, target_exp):
        return self._level_loss(sim_targets, target_exp)

    def _slope_loss(self, sim_targets, target_exp, timepoints):
        if sim_targets.shape[1] < 2 or len(timepoints) < 2:
            return 0.0

        dt = np.diff(timepoints)
        if dt.size == 0:
            return 0.0

        sim_slopes = np.diff(sim_targets, axis=1) / dt[None, :]
        exp_slopes = np.diff(target_exp, axis=1) / dt[None, :]
        rmse = np.sqrt(np.mean((sim_slopes - exp_slopes) ** 2, axis=1))
        nrmses = np.minimum(rmse / self.norm_factors, self.target_caps)
        loss = np.average(nrmses, weights=self.target_weights)
        return float(self.slope_weight * loss)

    def _endpoint_loss(self, sim_targets, target_exp):
        endpoint_errors = np.abs(sim_targets[:, -1] - target_exp[:, -1]) / self.norm_factors
        loss = self.curve_endpoint_weight * np.average(endpoint_errors, weights=self.target_weights)

        if self.endpoint_weight > 0.0 and np.any(self.endpoint_mask):
            loss += self.endpoint_weight * np.average(
                endpoint_errors[self.endpoint_mask],
                weights=self.target_weights[self.endpoint_mask],
            )

        return float(loss)

    def _fold_change_loss(self, sim_targets, target_exp):
        sim_start = sim_targets[:, 0]
        sim_end = sim_targets[:, -1]
        exp_start = target_exp[:, 0]
        exp_end = target_exp[:, -1]

        sim_log_fold = np.log((sim_end + self.dynamic_eps) / (sim_start + self.dynamic_eps))
        exp_log_fold = np.log((exp_end + self.dynamic_eps) / (exp_start + self.dynamic_eps))
        fold_errors = np.minimum(np.abs(sim_log_fold - exp_log_fold), self.target_caps)
        loss = np.average(fold_errors, weights=self.target_weights)
        return float(self.fold_weight * loss)

    def _composite_loss(self, sim_targets, target_exp, timepoints):
        level_loss = self._level_loss(sim_targets, target_exp)
        slope_loss = self._slope_loss(sim_targets, target_exp, timepoints)
        endpoint_loss = self._endpoint_loss(sim_targets, target_exp)
        fold_loss = self._fold_change_loss(sim_targets, target_exp)

        total_loss = level_loss + slope_loss + endpoint_loss + fold_loss
        breakdown = {
            "level_loss": float(level_loss),
            "slope_loss": float(slope_loss),
            "endpoint_loss": float(endpoint_loss),
            "fold_loss": float(fold_loss),
        }
        return float(total_loss), breakdown

    def _loss_inputs_for_mode(self, y, mode):
        if mode == "screen":
            return y[self.target_indices][:, self.screen_eval_indices], self.target_exp_screen, self.screen_time_exp, self.screen_eval_indices, self.screen_pool_trajectory
        if mode == "fast":
            return y[self.target_indices][:, self.exp_eval_indices], self.target_exp, self.active_time_exp, self.exp_eval_indices, self.exp_pool_trajectory
        if mode == "report":
            return y[self.target_indices][:, self.report_exp_indices], self.target_exp, self.active_time_exp, self.report_exp_indices, self.exp_pool_trajectory
        raise ValueError(f"Unsupported loss mode: {mode}")

    def _evaluate_total_loss(self, custom_params, mode):
        sol = self._cached_solve(custom_params, mode=mode)
        if not sol.success:
            return None, None, None

        y = np.maximum(sol.y, 0.0)
        sim_targets, target_exp, timepoints, exp_eval_indices, exp_pool_trajectory = self._loss_inputs_for_mode(y, mode)
        experimental_fit_loss, breakdown = self._composite_loss(sim_targets, target_exp, timepoints)
        teacher_loss_terms = self._teacher_student_loss(custom_params)
        teacher_student_loss = float(teacher_loss_terms["weighted_loss"])
        if not np.isfinite(teacher_student_loss):
            return None, None, None
        fit_loss = experimental_fit_loss + teacher_student_loss
        regularization_loss = self._regularization_loss(custom_params)
        physiological_penalty_loss = self._penalty_loss(y, exp_eval_indices, exp_pool_trajectory)
        guardrail_loss = regularization_loss + physiological_penalty_loss
        rank_loss = fit_loss
        legacy_total_loss = fit_loss + guardrail_loss
        breakdown = {
            **breakdown,
            "experimental_fit_loss": float(experimental_fit_loss),
            "teacher_student_loss": float(teacher_student_loss),
            "teacher_student_weight": float(
                self.teacher_student_weight
                if not self.teacher_weight_split_active
                else (self.teacher_curve_weight + self.teacher_flux_weight)
            ),
            "teacher_curve_loss": float(teacher_loss_terms["curve_loss"]),
            "teacher_flux_loss": float(teacher_loss_terms["flux_loss"]),
            "teacher_curve_weight": float(self.teacher_curve_weight),
            "teacher_flux_weight": float(self.teacher_flux_weight),
            "teacher_curve_weight_sum": float(teacher_loss_terms["curve_weight_sum"]),
            "teacher_flux_weight_sum": float(teacher_loss_terms["flux_weight_sum"]),
            "teacher_combined_loss": float(teacher_loss_terms["combined_loss"]),
            "teacher_weight_split_active": bool(self.teacher_weight_split_active),
            "teacher_loss_mode": self.teacher_loss_mode,
            "teacher_student_targets": list(self.teacher_target_names),
            "teacher_target_weights": dict(self.teacher_target_weight_map),
            "teacher_flux_targets": list(self.teacher_flux_names),
            "teacher_flux_weights": dict(self.teacher_flux_weight_map),
            "teacher_focus_metabolites": sorted(self.teacher_focus_metabolites),
            "teacher_focus_weight": float(self.teacher_focus_weight),
            "teacher_dataset_label": self.teacher_dataset_label,
            "teacher_dataset_path": self.teacher_dataset_path,
            "fit_loss": float(fit_loss),
            "guardrail_loss": float(guardrail_loss),
            "regularization_loss": float(regularization_loss),
            "physiological_penalty_loss": float(physiological_penalty_loss),
            "rank_loss": float(rank_loss),
            "legacy_total_loss": float(legacy_total_loss),
            "regularization_rank_weight": float(self.regularization_rank_weight),
            "physiological_rank_weight": float(self.physiological_rank_weight),
            "total_loss": float(rank_loss),
        }
        return float(rank_loss), breakdown, y

    # AGENT_EDITABLE_START: fit_penalty_hierarchy
    def objective_weights(self):
        return {
            "level_weight": float(self.level_weight),
            "slope_weight": float(self.slope_weight),
            "curve_endpoint_weight": float(self.curve_endpoint_weight),
            "fold_weight": float(self.fold_weight),
            "scope_endpoint_weight": float(self.endpoint_weight),
            "teacher_student_weight": float(self.teacher_student_weight),
            "teacher_curve_weight": float(self.teacher_curve_weight),
            "teacher_flux_weight": float(self.teacher_flux_weight),
            "teacher_weight_split_active": bool(self.teacher_weight_split_active),
            "regularization_rank_weight": float(self.regularization_rank_weight),
            "physiological_rank_weight": float(self.physiological_rank_weight),
        }

    def loss_breakdown(self, custom_params, mode="fast"):
        total_loss, breakdown, _ = self._evaluate_total_loss(custom_params, mode=mode)
        if breakdown is None:
            return None
        return breakdown

    def fit_loss(self, custom_params, mode="fast"):
        breakdown = self.loss_breakdown(custom_params, mode=mode)
        if breakdown is None:
            return float("inf")
        return float(breakdown["fit_loss"])

    def _regularization_loss(self, custom_params):
        if not custom_params:
            return 0.0

        class_base_weights = {
            PARAM_CLASS_VMAX: 0.005,
            PARAM_CLASS_KM: 0.010,
            PARAM_CLASS_REGULATION: 0.020,
            PARAM_CLASS_TRANSPORT: 0.010,
            PARAM_CLASS_DEGRADATION: 0.030,
            PARAM_CLASS_EFFECTIVE_MISC: 0.020,
        }
        ident_mult = {
            IDENTIFIABLE_CORE: 1.0,
            IDENTIFIABLE_CAUTION: 1.5,
            STRUCTURAL_COMPENSATION_RISK: 2.0,
        }

        reg = 0.0
        for pname, pval in custom_params.items():
            default = self.default_param_values.get(pname)
            if default is None or pval <= 0 or default <= 0:
                continue
            log_ratio = np.log10(pval / default)
            classes = get_parameter_classes(pname)
            base_weight = max(class_base_weights.get(cls, 0.005) for cls in classes)
            mult = ident_mult.get(get_parameter_identifiability(pname), 1.0)
            reg += base_weight * mult * (log_ratio ** 2)

        return float(reg)

    def _penalty_loss(self, y, exp_eval_indices, exp_pool_trajectory):
        total_penalty = 0.0

        if self.atp_focus:
            atp = y[self.atp_idx]
            adp = y[self.adp_idx]
            amp = y[self.amp_idx]
            imp = y[self.imp_idx]

            min_atp = float(np.min(atp))
            min_adp = float(np.min(adp))
            min_amp = float(np.min(amp))
            min_imp = float(np.min(imp))
            final_pool_ratio = float((atp[-1] + adp[-1] + amp[-1]) / self.init_adenylate_pool)

            atp_floor_pen = max(0.0, (self.atp_floor - min_atp) / max(self.atp_floor, 1e-8))
            adp_floor_pen = max(0.0, (self.adp_floor - min_adp) / max(self.adp_floor, 1e-8))
            amp_floor_pen = max(0.0, (self.amp_floor - min_amp) / max(self.amp_floor, 1e-8))
            imp_floor_pen = max(0.0, (self.imp_floor - min_imp) / max(self.imp_floor, 1e-8))
            pool_pen = max(0.0, (self.adenylate_target - final_pool_ratio) / max(self.adenylate_target, 1e-8))

            total_penalty += self.atp_penalty_weight * (atp_floor_pen + 0.5 * adp_floor_pen)
            total_penalty += self.amp_penalty_weight * amp_floor_pen
            total_penalty += self.imp_penalty_weight * imp_floor_pen
            total_penalty += self.pool_penalty_weight * pool_pen

            if exp_pool_trajectory is not None:
                sim_pool = (atp + adp + amp)[exp_eval_indices]
                pool_norm = max(np.mean(exp_pool_trajectory), 0.1)
                pool_traj_rmse = np.sqrt(np.mean((sim_pool - exp_pool_trajectory) ** 2))
                total_penalty += 5.0 * (pool_traj_rmse / pool_norm)

        if self.init_nad_pool > 0.01:
            nad_pool_final = float(y[self.nad_idx, -1] + y[self.nadh_idx, -1])
            total_penalty += 3.0 * (abs(nad_pool_final - self.init_nad_pool) / self.init_nad_pool)

        if self.init_nadp_pool > 0.01:
            nadp_pool_final = float(y[self.nadp_idx, -1] + y[self.nadph_idx, -1])
            total_penalty += 3.0 * (abs(nadp_pool_final - self.init_nadp_pool) / self.init_nadp_pool)

        return float(total_penalty)

    # AGENT_EDITABLE_END: fit_penalty_hierarchy
    def screen(self, custom_params):
        try:
            total_loss, _, _ = self._evaluate_total_loss(custom_params, mode="fast")
            if total_loss is None:
                return 100.0
            return total_loss
        except Exception:
            return 100.0

    def endpoint_nrmse(self, custom_params):
        sol = self._cached_solve(custom_params, mode="report")
        if not np.any(self.endpoint_mask):
            return 0.0
        if not sol.success:
            return float("inf")
        y = np.maximum(sol.y, 0.0)
        endpoint_values = y[self.target_indices, self.report_final_index]
        endpoint_errors = np.abs(endpoint_values - self.target_exp[:, -1]) / self.norm_factors
        return float(np.average(endpoint_errors[self.endpoint_mask], weights=self.target_weights[self.endpoint_mask]))

    def __call__(self, custom_params):
        self.n_calls += 1
        try:
            total_loss, breakdown, _ = self._evaluate_total_loss(custom_params, mode="fast")
            if total_loss is None:
                return 100.0

            if total_loss < self.best_loss:
                self.best_loss = total_loss
                self.best_params = {} if not custom_params else custom_params.copy()
                self.best_loss_breakdown = dict(breakdown)

            return total_loss
        except Exception:
            return 100.0

    def detailed_report(self, custom_params):
        sol = self._cached_solve(custom_params, mode="report")
        if not sol.success:
            return []
        y = np.maximum(sol.y, 0.0)

        report = []
        for i, (ename, midx) in enumerate(zip(self.target_names, self.target_indices)):
            sim_at_exp = y[midx, self.report_exp_indices]
            rmse = np.sqrt(np.mean((sim_at_exp - self.target_exp[i]) ** 2))
            nrmse = rmse / self.norm_factors[i]
            report.append({
                "name": ename,
                "idx": midx,
                "rmse": rmse,
                "nrmse": nrmse,
                "exp_mean_abs": float(np.mean(np.abs(self.target_exp[i]))),
                "norm_factor": float(self.norm_factors[i]),
                "sim_final": y[midx, self.report_final_index],
                "exp_final": self.target_exp[i, -1],
            })
        return sorted(report, key=lambda r: r["nrmse"], reverse=True)


# =============================================================================
# OPTIMIZERS
# =============================================================================

def should_use_log_sampling(param_name, lo, hi):
    if lo <= 0:
        return False
    if PARAM_CLASS_HYBRID in get_parameter_classes(param_name):
        return False
    return True


def optimize_optuna(objective, phase_params, fixed_params, n_trials=200, study_name=None, seed=42):
    def optuna_objective(trial):
        custom_params = fixed_params.copy()
        for pname, (_, lo, hi) in phase_params.items():
            val = trial.suggest_float(pname, lo, hi, log=should_use_log_sampling(pname, lo, hi))
            custom_params[pname] = val
        screen_loss = objective.screen(custom_params)
        trial.report(screen_loss, 0)
        if screen_loss >= 100.0 or trial.should_prune():
            raise optuna.TrialPruned()
        final_loss = objective(custom_params)
        trial.report(final_loss, 1)
        if trial.should_prune():
            raise optuna.TrialPruned()
        return final_loss

    sampler = optuna.samplers.TPESampler(
        seed=seed,
        n_startup_trials=min(30, max(1, n_trials // 4)),
        multivariate=True,
    )
    pruner = optuna.pruners.MedianPruner(
        n_startup_trials=min(10, max(1, n_trials // 5)),
        n_warmup_steps=0,
        interval_steps=1,
    )

    study = optuna.create_study(
        direction="minimize",
        sampler=sampler,
        pruner=pruner,
        study_name=study_name or "mm_calibration",
    )

    seed_trial = {}
    for pname, (default, lo, hi) in phase_params.items():
        loaded_val = fixed_params.get(pname, default)
        seed_trial[pname] = float(np.clip(loaded_val, lo, hi))
    study.enqueue_trial(seed_trial)

    study.optimize(optuna_objective, n_trials=n_trials, show_progress_bar=True)
    return study.best_params, study.best_value, study


def optimize_de(objective, phase_params, fixed_params, max_iter=150):
    param_names = list(phase_params.keys())
    bounds = [(lo, hi) for _, (_, lo, hi) in phase_params.items()]

    def de_objective(x):
        custom_params = fixed_params.copy()
        for i, pname in enumerate(param_names):
            custom_params[pname] = x[i]
        return objective(custom_params)

    result = differential_evolution(
        de_objective,
        bounds,
        maxiter=max_iter,
        popsize=20,
        strategy="best1bin",
        mutation=(0.5, 1.5),
        recombination=0.8,
        seed=42,
        tol=1e-6,
        polish=True,
        workers=1,
    )

    best = {pname: result.x[i] for i, pname in enumerate(param_names)}
    return best, result.fun, result


# =============================================================================
# OBJECTIVE BUILDERS
# =============================================================================

# AGENT_EDITABLE_START: objective_builders
def build_objective(
    x0,
    time_exp,
    exp_values,
    name_to_row,
    t_max=46,
    target_scope="all",
    target_names=None,
    objective_name=None,
    endpoint_target_names=None,
    endpoint_weight=None,
    atp_focus=False,
    atp_floor=0.15,
    adp_floor=0.05,
    amp_floor=0.04,
    imp_floor=0.02,
    adenylate_target=0.65,
    atp_penalty_weight=10.0,
    amp_penalty_weight=6.0,
    imp_penalty_weight=5.0,
    pool_penalty_weight=12.0,
    curve_fit_strength=0.0,
    teacher_dataset=None,
    teacher_student_weight=DEFAULT_TEACHER_STUDENT_WEIGHT,
    teacher_curve_weight=None,
    teacher_flux_weight=None,
    teacher_target_weights=None,
    teacher_focus_metabolites=None,
    teacher_focus_weight=DEFAULT_TEACHER_FOCUS_WEIGHT,
):
    return ObjectiveFunction(
        x0,
        time_exp,
        exp_values,
        name_to_row,
        t_max=t_max,
        target_scope=target_scope,
        target_names=target_names,
        objective_name=objective_name,
        endpoint_target_names=endpoint_target_names,
        endpoint_weight=endpoint_weight,
        atp_focus=atp_focus,
        atp_floor=atp_floor,
        adp_floor=adp_floor,
        amp_floor=amp_floor,
        imp_floor=imp_floor,
        adenylate_target=adenylate_target,
        atp_penalty_weight=atp_penalty_weight,
        amp_penalty_weight=amp_penalty_weight,
        imp_penalty_weight=imp_penalty_weight,
        pool_penalty_weight=pool_penalty_weight,
        curve_fit_strength=curve_fit_strength,
        teacher_dataset=teacher_dataset,
        teacher_student_weight=teacher_student_weight,
        teacher_curve_weight=teacher_curve_weight,
        teacher_flux_weight=teacher_flux_weight,
        teacher_target_weights=teacher_target_weights,
        teacher_focus_metabolites=teacher_focus_metabolites,
        teacher_focus_weight=teacher_focus_weight,
    )


def build_primary_objective(
    x0,
    time_exp,
    exp_values,
    name_to_row,
    target_scope,
    t_max=46,
    atp_focus=False,
    atp_floor=0.15,
    adp_floor=0.05,
    amp_floor=0.04,
    imp_floor=0.02,
    adenylate_target=0.65,
    atp_penalty_weight=10.0,
    amp_penalty_weight=6.0,
    imp_penalty_weight=5.0,
    pool_penalty_weight=12.0,
    curve_fit_strength=0.0,
    teacher_dataset=None,
    teacher_student_weight=DEFAULT_TEACHER_STUDENT_WEIGHT,
    teacher_curve_weight=None,
    teacher_flux_weight=None,
    teacher_target_weights=None,
    teacher_focus_metabolites=None,
    teacher_focus_weight=DEFAULT_TEACHER_FOCUS_WEIGHT,
    target_names=None,
):
    resolved_target_names = resolve_primary_target_names(target_scope, target_names=target_names)
    return build_objective(
        x0,
        time_exp,
        exp_values,
        name_to_row,
        t_max=t_max,
        target_scope=target_scope,
        target_names=resolved_target_names,
        atp_focus=atp_focus,
        atp_floor=atp_floor,
        adp_floor=adp_floor,
        amp_floor=amp_floor,
        imp_floor=imp_floor,
        adenylate_target=adenylate_target,
        atp_penalty_weight=atp_penalty_weight,
        amp_penalty_weight=amp_penalty_weight,
        imp_penalty_weight=imp_penalty_weight,
        pool_penalty_weight=pool_penalty_weight,
        curve_fit_strength=curve_fit_strength,
        teacher_dataset=teacher_dataset,
        teacher_student_weight=teacher_student_weight,
        teacher_curve_weight=teacher_curve_weight,
        teacher_flux_weight=teacher_flux_weight,
        teacher_target_weights=teacher_target_weights,
        teacher_focus_metabolites=teacher_focus_metabolites,
        teacher_focus_weight=teacher_focus_weight,
    )


def build_phase_objectives(
    x0,
    time_exp,
    exp_values,
    name_to_row,
    target_scope,
    t_max=46,
    atp_focus=False,
    atp_floor=0.15,
    adp_floor=0.05,
    amp_floor=0.04,
    imp_floor=0.02,
    adenylate_target=0.65,
    atp_penalty_weight=10.0,
    amp_penalty_weight=6.0,
    imp_penalty_weight=5.0,
    pool_penalty_weight=12.0,
    curve_fit_strength=0.0,
    teacher_dataset=None,
    teacher_student_weight=DEFAULT_TEACHER_STUDENT_WEIGHT,
    teacher_curve_weight=None,
    teacher_flux_weight=None,
    teacher_target_weights=None,
    teacher_focus_metabolites=None,
    teacher_focus_weight=DEFAULT_TEACHER_FOCUS_WEIGHT,
    target_names=None,
):
    phase_objectives = {}
    if use_pathway_phase_objectives(target_scope):
        for phase_num, objective_name in PATHWAY_PHASE_OBJECTIVE_NAMES.items():
            resolved_target_names = resolve_phase_target_names(objective_name, target_names=target_names)
            if not resolved_target_names:
                print(f"  Skipping phase objective '{objective_name}': no targets available after scope filtering")
                continue
            try:
                phase_objectives[phase_num] = build_objective(
                    x0,
                    time_exp,
                    exp_values,
                    name_to_row,
                    t_max=t_max,
                    target_scope="all",
                    target_names=resolved_target_names,
                    objective_name=objective_name,
                    atp_focus=atp_focus,
                    atp_floor=atp_floor,
                    adp_floor=adp_floor,
                    amp_floor=amp_floor,
                    imp_floor=imp_floor,
                    adenylate_target=adenylate_target,
                    atp_penalty_weight=atp_penalty_weight,
                    amp_penalty_weight=amp_penalty_weight,
                    imp_penalty_weight=imp_penalty_weight,
                    pool_penalty_weight=pool_penalty_weight,
                    curve_fit_strength=curve_fit_strength,
                    teacher_dataset=teacher_dataset,
                    teacher_student_weight=teacher_student_weight,
                    teacher_curve_weight=teacher_curve_weight,
                    teacher_flux_weight=teacher_flux_weight,
                    teacher_target_weights=teacher_target_weights,
                    teacher_focus_metabolites=teacher_focus_metabolites,
                    teacher_focus_weight=teacher_focus_weight,
                )
            except ValueError as exc:
                print(f"  Skipping phase objective '{objective_name}': {exc}")
    return phase_objectives


def build_monitor_objectives(
    x0,
    time_exp,
    exp_values,
    name_to_row,
    target_scope,
    t_max=46,
    curve_fit_strength=0.0,
    teacher_dataset=None,
    teacher_student_weight=DEFAULT_TEACHER_STUDENT_WEIGHT,
    teacher_curve_weight=None,
    teacher_flux_weight=None,
    teacher_target_weights=None,
    teacher_focus_metabolites=None,
    teacher_focus_weight=DEFAULT_TEACHER_FOCUS_WEIGHT,
):
    monitor_objectives = {}
    if target_scope in {"glycolysis_extracellular", "all", "core_glycolysis_energy"}:
        for scope_name in ("glycolysis_energy", "nucleotide_purine", "amino_redox_side"):
            try:
                monitor_objectives[scope_name] = build_objective(
                    x0,
                    time_exp,
                    exp_values,
                    name_to_row,
                    t_max=t_max,
                    target_scope="all",
                    target_names=PATHWAY_TARGET_GROUPS[scope_name],
                    objective_name=scope_name,
                    curve_fit_strength=curve_fit_strength,
                    teacher_dataset=teacher_dataset,
                    teacher_student_weight=teacher_student_weight,
                    teacher_curve_weight=teacher_curve_weight,
                    teacher_flux_weight=teacher_flux_weight,
                    teacher_target_weights=teacher_target_weights,
                    teacher_focus_metabolites=teacher_focus_metabolites,
                    teacher_focus_weight=teacher_focus_weight,
                )
            except ValueError as exc:
                print(f"  Skipping monitor objective '{scope_name}': {exc}")
        for scope_name, target_scope_name in (("extracellular", "extracellular"), ("glycolysis", "glycolysis")):
            try:
                monitor_objectives[scope_name] = ObjectiveFunction(
                    x0, time_exp, exp_values, name_to_row,
                    t_max=t_max, target_scope=target_scope_name, curve_fit_strength=curve_fit_strength,
                    teacher_dataset=teacher_dataset,
                    teacher_student_weight=teacher_student_weight,
                    teacher_curve_weight=teacher_curve_weight,
                    teacher_flux_weight=teacher_flux_weight,
                    teacher_target_weights=teacher_target_weights,
                    teacher_focus_metabolites=teacher_focus_metabolites,
                    teacher_focus_weight=teacher_focus_weight,
                )
            except ValueError as exc:
                print(f"  Skipping monitor objective '{scope_name}': {exc}")
    return monitor_objectives


def build_objective_bundle(
    x0,
    time_exp,
    exp_values,
    name_to_row,
    target_scope,
    t_max=46,
    atp_focus=False,
    atp_floor=0.15,
    adp_floor=0.05,
    amp_floor=0.04,
    imp_floor=0.02,
    adenylate_target=0.65,
    atp_penalty_weight=10.0,
    amp_penalty_weight=6.0,
    imp_penalty_weight=5.0,
    pool_penalty_weight=12.0,
    curve_fit_strength=0.0,
    teacher_dataset=None,
    teacher_student_weight=DEFAULT_TEACHER_STUDENT_WEIGHT,
    teacher_curve_weight=None,
    teacher_flux_weight=None,
    teacher_target_weights=None,
    teacher_focus_metabolites=None,
    teacher_focus_weight=DEFAULT_TEACHER_FOCUS_WEIGHT,
    target_names=None,
):
    primary = build_primary_objective(
        x0, time_exp, exp_values, name_to_row,
        target_scope=target_scope,
        t_max=t_max,
        atp_focus=atp_focus,
        atp_floor=atp_floor,
        adp_floor=adp_floor,
        amp_floor=amp_floor,
        imp_floor=imp_floor,
        adenylate_target=adenylate_target,
        atp_penalty_weight=atp_penalty_weight,
        amp_penalty_weight=amp_penalty_weight,
        imp_penalty_weight=imp_penalty_weight,
        pool_penalty_weight=pool_penalty_weight,
        curve_fit_strength=curve_fit_strength,
        teacher_dataset=teacher_dataset,
        teacher_student_weight=teacher_student_weight,
        teacher_curve_weight=teacher_curve_weight,
        teacher_flux_weight=teacher_flux_weight,
        teacher_target_weights=teacher_target_weights,
        teacher_focus_metabolites=teacher_focus_metabolites,
        teacher_focus_weight=teacher_focus_weight,
        target_names=target_names,
    )
    phase_objectives = build_phase_objectives(
        x0, time_exp, exp_values, name_to_row,
        target_scope=target_scope,
        t_max=t_max,
        atp_focus=atp_focus,
        atp_floor=atp_floor,
        adp_floor=adp_floor,
        amp_floor=amp_floor,
        imp_floor=imp_floor,
        adenylate_target=adenylate_target,
        atp_penalty_weight=atp_penalty_weight,
        amp_penalty_weight=amp_penalty_weight,
        imp_penalty_weight=imp_penalty_weight,
        pool_penalty_weight=pool_penalty_weight,
        curve_fit_strength=curve_fit_strength,
        teacher_dataset=teacher_dataset,
        teacher_student_weight=teacher_student_weight,
        teacher_curve_weight=teacher_curve_weight,
        teacher_flux_weight=teacher_flux_weight,
        teacher_target_weights=teacher_target_weights,
        teacher_focus_metabolites=teacher_focus_metabolites,
        teacher_focus_weight=teacher_focus_weight,
        target_names=target_names,
    )
    monitor_objectives = build_monitor_objectives(
        x0, time_exp, exp_values, name_to_row,
        target_scope=target_scope,
        t_max=t_max,
        curve_fit_strength=curve_fit_strength,
        teacher_dataset=teacher_dataset,
        teacher_student_weight=teacher_student_weight,
        teacher_curve_weight=teacher_curve_weight,
        teacher_flux_weight=teacher_flux_weight,
        teacher_target_weights=teacher_target_weights,
        teacher_focus_metabolites=teacher_focus_metabolites,
        teacher_focus_weight=teacher_focus_weight,
    )
    monitor_regression_limits = get_monitor_regression_limits(target_scope)

    return {
        "primary": primary,
        "phase_objectives": phase_objectives,
        "monitor_objectives": monitor_objectives,
        "monitor_regression_limits": monitor_regression_limits,
    }


# AGENT_EDITABLE_END: objective_builders
# AGENT_EDITABLE_START: diagnostics_reporting
def evaluate_monitor_metrics(primary_objective, monitor_objectives, params):
    primary_breakdown = primary_objective.loss_breakdown(params, mode="fast")
    if primary_breakdown is None:
        metrics = {
            "target": float("inf"),
            "experimental_fit_loss": float("inf"),
            "teacher_student_loss": float("inf"),
            "teacher_student_weight": float(primary_objective.teacher_student_weight),
            "teacher_curve_loss": float("inf"),
            "teacher_flux_loss": float("inf"),
            "teacher_curve_weight": float(primary_objective.teacher_curve_weight),
            "teacher_flux_weight": float(primary_objective.teacher_flux_weight),
            "endpoint_nrmse": float("inf"),
            "joint": float("inf"),
            "rank_loss": float("inf"),
            "guardrail_loss": float("inf"),
            "regularization_loss": float("inf"),
            "physiological_penalty_loss": float("inf"),
            "legacy_total_loss": float("inf"),
        }
    else:
        metrics = {
            "target": float(primary_breakdown["fit_loss"]),
            "experimental_fit_loss": float(primary_breakdown.get("experimental_fit_loss", primary_breakdown["fit_loss"])),
            "teacher_student_loss": float(primary_breakdown.get("teacher_student_loss", 0.0)),
            "teacher_student_weight": float(primary_breakdown.get("teacher_student_weight", 0.0)),
            "teacher_curve_loss": float(primary_breakdown.get("teacher_curve_loss", 0.0)),
            "teacher_flux_loss": float(primary_breakdown.get("teacher_flux_loss", 0.0)),
            "teacher_curve_weight": float(primary_breakdown.get("teacher_curve_weight", 0.0)),
            "teacher_flux_weight": float(primary_breakdown.get("teacher_flux_weight", 0.0)),
            "endpoint_nrmse": float(primary_objective.endpoint_nrmse(params)),
            "joint": float(primary_breakdown["rank_loss"]),
            "rank_loss": float(primary_breakdown["rank_loss"]),
            "guardrail_loss": float(primary_breakdown["guardrail_loss"]),
            "regularization_loss": float(primary_breakdown["regularization_loss"]),
            "physiological_penalty_loss": float(primary_breakdown["physiological_penalty_loss"]),
            "legacy_total_loss": float(primary_breakdown["legacy_total_loss"]),
        }
        sol = primary_objective._cached_solve(params, mode="fast")
        if getattr(sol, "success", False):
            y = np.maximum(sol.y, 0.0)
            for metabolite_name in ("EGLC", "ELAC", "ATP", "LAC", "GLC"):
                metabolite_idx = EXP_TO_MODEL.get(metabolite_name)
                if metabolite_idx is not None and metabolite_idx < y.shape[0]:
                    metrics[f"final_{metabolite_name}"] = float(y[metabolite_idx, -1])
    for scope_name, scope_objective in monitor_objectives.items():
        metrics[scope_name] = float(scope_objective.fit_loss(params))
    return metrics


def _evaluate_extracellular_final_gate(
    incumbent_metrics,
    candidate_metrics,
    max_eglc_final_increase_frac=None,
    max_elac_final_drop_frac=None,
):
    if max_eglc_final_increase_frac is None or max_elac_final_drop_frac is None:
        return None

    incumbent_eglc = incumbent_metrics.get("final_EGLC")
    candidate_eglc = candidate_metrics.get("final_EGLC")
    incumbent_elac = incumbent_metrics.get("final_ELAC")
    candidate_elac = candidate_metrics.get("final_ELAC")

    values = (incumbent_eglc, candidate_eglc, incumbent_elac, candidate_elac)
    if not all(isinstance(v, (int, float)) and np.isfinite(v) for v in values):
        return None

    if incumbent_eglc <= 1e-12 or incumbent_elac <= 1e-12:
        return None

    eglc_increase_frac = (candidate_eglc - incumbent_eglc) / incumbent_eglc
    elac_drop_frac = (incumbent_elac - candidate_elac) / incumbent_elac

    if (
        eglc_increase_frac > max_eglc_final_increase_frac
        and elac_drop_frac > max_elac_final_drop_frac
    ):
        return (
            "rejected by EGLC/ELAC gate "
            f"(EGLC {incumbent_eglc:.4f}->{candidate_eglc:.4f}, +{eglc_increase_frac*100:.1f}%; "
            f"ELAC {incumbent_elac:.4f}->{candidate_elac:.4f}, -{elac_drop_frac*100:.1f}%)"
        )
    return None


def accept_monitor_metrics(
    incumbent_metrics,
    candidate_metrics,
    monitor_regression_limits=None,
    max_endpoint_regression=0.15,
    max_eglc_final_increase_frac=None,
    max_elac_final_drop_frac=None,
):
    fit_delta = candidate_metrics["target"] - incumbent_metrics["target"]
    if fit_delta > 1e-9:
        return False, f"fit {incumbent_metrics['target']:.4f}->{candidate_metrics['target']:.4f}"

    gate_reason = _evaluate_extracellular_final_gate(
        incumbent_metrics,
        candidate_metrics,
        max_eglc_final_increase_frac=max_eglc_final_increase_frac,
        max_elac_final_drop_frac=max_elac_final_drop_frac,
    )
    if gate_reason is not None:
        return False, gate_reason

    fit_gain = incumbent_metrics["target"] - candidate_metrics["target"]
    if fit_gain > 1e-9:
        return True, f"accepted on pure fit objective ({incumbent_metrics['target']:.4f}->{candidate_metrics['target']:.4f})"

    if abs(fit_gain) <= 1e-9:
        incumbent_joint = float(incumbent_metrics.get("joint", incumbent_metrics["target"]))
        candidate_joint = float(candidate_metrics.get("joint", candidate_metrics["target"]))
        if candidate_joint > incumbent_joint + JOINT_TIE_TOLERANCE:
            return False, f"rank {incumbent_joint:.4f}->{candidate_joint:.4f}"

    return True, "accepted on fit-only tie"


def get_monitor_regression_limits(target_scope):
    if target_scope in {"glycolysis_extracellular", "all"}:
        return PATHWAY_MONITOR_REGRESSION_LIMITS.copy()
    if target_scope == "core_glycolysis_energy":
        return {
            "glycolysis_energy": PATHWAY_MONITOR_REGRESSION_LIMITS["glycolysis_energy"],
            "glycolysis": PATHWAY_MONITOR_REGRESSION_LIMITS["glycolysis"],
            "extracellular": PATHWAY_MONITOR_REGRESSION_LIMITS["extracellular"],
        }
    return {}


def format_metric_summary(metrics, metric_keys):
    parts = []
    for metric_name in metric_keys:
        if metric_name in metrics:
            parts.append(f"{metric_name}={metrics[metric_name]:.4f}")
    return ", ".join(parts)


def format_metric_changes(before_metrics, after_metrics, metric_keys):
    parts = []
    for metric_name in metric_keys:
        if metric_name in before_metrics and metric_name in after_metrics:
            parts.append(f"{metric_name} {before_metrics[metric_name]:.4f} -> {after_metrics[metric_name]:.4f}")
    return ", ".join(parts)


def total_objective_calls(*objective_groups):
    total = 0
    seen_ids = set()
    pending = list(objective_groups)

    while pending:
        group = pending.pop()

        if group is None:
            continue

        if isinstance(group, dict):
            pending.extend(group.values())
            continue

        if isinstance(group, (list, tuple, set)):
            pending.extend(group)
            continue

        n_calls = getattr(group, "n_calls", None)
        if isinstance(n_calls, (int, float)):
            obj_id = id(group)
            if obj_id not in seen_ids:
                seen_ids.add(obj_id)
                total += int(n_calls)

    return total


# =============================================================================
# TSV HELPERS
# =============================================================================

def ensure_results_tsv_schema(results_file):
    if not results_file.exists():
        return
    with open(results_file, newline="") as f:
        rows = list(csv.reader(f, delimiter="\t"))
    if not rows:
        return

    header = rows[0]
    if header == RESULTS_TSV_FIELDS:
        return

    migrated_rows = []
    for raw in rows[1:]:
        if not raw:
            continue
        if len(raw) == len(RESULTS_TSV_FIELDS):
            row_map = {field: raw[i] for i, field in enumerate(RESULTS_TSV_FIELDS)}
        elif header == LEGACY_RESULTS_TSV_FIELDS and len(raw) == len(LEGACY_RESULTS_TSV_FIELDS):
            legacy_map = {field: raw[i] for i, field in enumerate(LEGACY_RESULTS_TSV_FIELDS)}
            row_map = {field: "" for field in RESULTS_TSV_FIELDS}
            for field in LEGACY_RESULTS_TSV_FIELDS:
                row_map[field] = legacy_map.get(field, "")
        else:
            row_map = {field: raw[i] if i < len(raw) else "" for i, field in enumerate(header)}
            row_map = {field: row_map.get(field, "") for field in RESULTS_TSV_FIELDS}
        migrated_rows.append(row_map)

    with open(results_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RESULTS_TSV_FIELDS, delimiter="\t")
        writer.writeheader()
        writer.writerows(migrated_rows)


def append_results_row(out_dir, row):
    results_file = out_dir / "results.tsv"
    ensure_results_tsv_schema(results_file)
    file_exists = results_file.exists()
    with open(results_file, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RESULTS_TSV_FIELDS, delimiter="\t")
        if not file_exists:
            writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in RESULTS_TSV_FIELDS})
    return results_file


# =============================================================================
# VISUALS
# =============================================================================

def plot_comparison(objective, params, title_suffix="", save_path=None):
    sol = objective._cached_solve(params, mode="dense")
    if not sol.success:
        print(f"  Skipping plot {title_suffix}: calibrated solve failed ({sol.message})")
        return
    y = np.maximum(sol.y, 0.0)

    sol_def = objective._cached_solve(None, mode="dense")
    if not sol_def.success:
        print(f"  Skipping plot {title_suffix}: default solve failed ({sol_def.message})")
        return
    y_def = np.maximum(sol_def.y, 0.0)

    plot_mets = [
        ("GLC", 0), ("LAC", 19), ("ATP", 35), ("ADP", 36),
        ("B23PG", 15), ("EGLC", 85), ("ELAC", 87), ("GSH", 70),
        ("GSSG", 71), ("GLU", 60), ("HYPX", 28), ("IMP", 42),
        ("MAL", 20), ("ADE", 25), ("PYR", 18), ("ALA", 58),
    ]

    fig, axes = plt.subplots(4, 4, figsize=(20, 16))
    fig.suptitle(f"MM Calibration Results {title_suffix}", fontsize=14, fontweight="bold")
    axes = axes.flatten()

    for i, (mname, midx) in enumerate(plot_mets):
        ax = axes[i]
        exp_key = mname.upper()
        if exp_key in objective.name_to_row:
            row = objective.name_to_row[exp_key]
            ax.scatter(
                objective.time_exp,
                objective.exp_values[row, :],
                color="black",
                s=40,
                zorder=5,
                label="Experimental",
                marker="o",
            )
        ax.plot(sol_def.t, y_def[midx], color="red", linewidth=1, alpha=0.5, linestyle="--", label="Default")
        ax.plot(sol.t, y[midx], color="blue", linewidth=2, label="Calibrated")
        ax.set_title(f"{mname} (idx {midx})", fontsize=10)
        ax.set_xlabel("Time (days)", fontsize=8)
        ax.set_ylabel("mM", fontsize=8)
        ax.legend(fontsize=6, loc="best")
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  Plot saved: {save_path}")
    plt.close(fig)


# =============================================================================
# MAIN
# =============================================================================

def run_calibration(
    phases=None,
    n_trials=200,
    load_params=None,
    target_scope="all",
    param_scope="all",
    generate_plots=True,
    atp_focus=False,
    atp_floor=0.15,
    adp_floor=0.05,
    amp_floor=0.04,
    imp_floor=0.02,
    adenylate_target=0.65,
    atp_penalty_weight=10.0,
    amp_penalty_weight=6.0,
    imp_penalty_weight=5.0,
    pool_penalty_weight=12.0,
    global_trials=None,
    seed=42,
    t_max=46,
    curve_fit_strength=0.0,
    out_dir=None,
    optimization_strategy="legacy",
    parameter_classes=None,
    stage_plan=None,
    target_metabolites=None,
    experimental_data=None,
    research_data_mode=None,
    active_dataset_id=None,
    active_dataset_label=None,
    teacher_dataset_path=None,
    teacher_student_weight=DEFAULT_TEACHER_STUDENT_WEIGHT,
    teacher_curve_weight=None,
    teacher_flux_weight=None,
    teacher_target_weights=None,
    teacher_focus_metabolites=None,
    teacher_focus_weight=DEFAULT_TEACHER_FOCUS_WEIGHT,
    dump_trajectories=False,
):
    if phases is None:
        phases = [1, 2, 3]
    if global_trials is not None and global_trials < 0:
        raise ValueError("global_trials must be >= 0")
    if t_max <= 1:
        raise ValueError("t_max must be > 1")
    if stage_plan is None and optimization_strategy not in OPTIMIZATION_STRATEGY_CHOICES:
        raise ValueError(f"Unsupported optimization_strategy: {optimization_strategy}")

    resolved_global_trials = max(1, n_trials // 2) if global_trials is None else global_trials
    resolved_out_dir = Path(out_dir) if out_dir is not None else OUT_DIR

    resolved_stage_plan = resolve_stage_plan(
        optimization_strategy=optimization_strategy,
        phases=phases,
        param_scope=param_scope,
        target_scope=target_scope,
        n_trials=n_trials,
        global_trials=resolved_global_trials,
        seed=seed,
        parameter_classes=parameter_classes,
        atp_focus=atp_focus,
        atp_floor=atp_floor,
        adp_floor=adp_floor,
        adenylate_target=adenylate_target,
        atp_penalty_weight=atp_penalty_weight,
        pool_penalty_weight=pool_penalty_weight,
        curve_fit_strength=curve_fit_strength,
        teacher_dataset_path=teacher_dataset_path,
        teacher_student_weight=teacher_student_weight,
        teacher_curve_weight=teacher_curve_weight,
        teacher_flux_weight=teacher_flux_weight,
        teacher_target_weights=teacher_target_weights,
        teacher_focus_metabolites=teacher_focus_metabolites,
        teacher_focus_weight=teacher_focus_weight,
        stage_plan=stage_plan,
    )
    teacher_weight_cfg = resolve_teacher_loss_weights(
        teacher_student_weight=teacher_student_weight,
        teacher_curve_weight=teacher_curve_weight,
        teacher_flux_weight=teacher_flux_weight,
    )

    print("=" * 70)
    print("RBC Metabolic Model — ML-based MM Recalibration")
    print(f"Optimizer: {'optuna TPE (Bayesian)' if HAS_OPTUNA else 'scipy DE (fallback)'}")
    print(f"Phases: {phases}")
    print(f"Trials per phase: {n_trials}")
    if len(phases) > 1:
        print(f"Global refinement trials: {resolved_global_trials}")
    print(f"Target scope: {target_scope}")
    print(f"Parameter scope: {param_scope}")
    print(f"Optimization strategy: {optimization_strategy}")
    if target_metabolites is not None:
        print(f"Requested target metabolites: {normalize_name_list(target_metabolites)}")
    if parameter_classes is not None:
        print(f"Requested parameter classes: {normalize_name_list(parameter_classes)}")
    print(f"Resolved stages: {[stage['name'] for stage in resolved_stage_plan]}")
    print(f"Seed: {seed}")
    print(f"Calibration horizon: 1-{t_max} days")
    if curve_fit_strength > 0.0:
        print(f"Curve-fit curriculum strength: {curve_fit_strength}")
    if teacher_dataset_path and (
        teacher_weight_cfg["legacy_weight"] > 0.0
        or teacher_weight_cfg["curve_weight"] > 0.0
        or teacher_weight_cfg["flux_weight"] > 0.0
    ):
        if teacher_weight_cfg["split_active"]:
            print(
                "Teacher-student loss: ON "
                f"(curve weight={teacher_weight_cfg['curve_weight']}, "
                f"flux weight={teacher_weight_cfg['flux_weight']}, "
                f"dataset={teacher_dataset_path})"
            )
        else:
            print(f"Teacher-student loss: ON (weight={teacher_student_weight}, dataset={teacher_dataset_path})")
    if teacher_focus_metabolites:
        print(
            "Teacher focus: "
            f"{normalize_name_list(teacher_focus_metabolites)} "
            f"(focus weight={teacher_focus_weight})"
        )
    print(f"Plots: {'enabled' if generate_plots else 'skipped'}")
    if atp_focus:
        print(
            "ATP focus: ON "
            f"(ATP floor={atp_floor}, ADP floor={adp_floor}, AMP floor={amp_floor}, IMP floor={imp_floor}, "
            f"adenylate target={adenylate_target})"
        )
    print("=" * 70)

    requested_target_metabolites = normalize_name_list(target_metabolites)
    data_mode = research_data_mode or ("custom_user_data_mode" if experimental_data is not None else "default_bordbar_mode")
    data_source = active_dataset_label or ("custom user data" if data_mode == "custom_user_data_mode" else "Bordbar reference dataset")

    print("\n[1/4] Loading data...")
    print(f"  Experimental source: {data_source}")
    time_exp, exp_values, name_to_row = load_experimental_data(experimental_data)
    if requested_target_metabolites is None and experimental_data is not None:
        requested_target_metabolites = list(name_to_row.keys())
    x0 = load_initial_conditions()
    print(f"  Experimental: {len(name_to_row)} metabolites, {len(time_exp)} timepoints")
    print(f"  Time range: {time_exp[0]}-{time_exp[-1]} days")

    teacher_dataset = load_teacher_curve_dataset(teacher_dataset_path)
    if teacher_dataset is not None:
        print(
            "  Teacher dataset: "
            f"{teacher_dataset.get('dataset_label', 'teacher_curve_dataset')} "
            f"({len(teacher_dataset.get('target_metabolites', []))} metabolites)"
        )

    resolved_out_dir.mkdir(parents=True, exist_ok=True)

    global_bundle = build_objective_bundle(
        x0, time_exp, exp_values, name_to_row,
        target_scope=target_scope,
        t_max=t_max,
        atp_focus=atp_focus,
        atp_floor=atp_floor,
        adp_floor=adp_floor,
        amp_floor=amp_floor,
        imp_floor=imp_floor,
        adenylate_target=adenylate_target,
        atp_penalty_weight=atp_penalty_weight,
        amp_penalty_weight=amp_penalty_weight,
        imp_penalty_weight=imp_penalty_weight,
        pool_penalty_weight=pool_penalty_weight,
        curve_fit_strength=curve_fit_strength,
        teacher_dataset=teacher_dataset,
        teacher_student_weight=teacher_student_weight,
        teacher_curve_weight=teacher_curve_weight,
        teacher_flux_weight=teacher_flux_weight,
        teacher_target_weights=teacher_target_weights,
        teacher_focus_metabolites=teacher_focus_metabolites,
        teacher_focus_weight=teacher_focus_weight,
        target_names=requested_target_metabolites,
    )
    global_primary = global_bundle["primary"]
    global_phase_objectives = global_bundle["phase_objectives"]
    global_monitor_objectives = global_bundle["monitor_objectives"]
    global_monitor_regression_limits = global_bundle["monitor_regression_limits"]
    protected_metric_keys = list(global_monitor_objectives.keys()) + ["endpoint_nrmse"]

    current_params = {}
    if load_params:
        with open(load_params, "r") as f:
            current_params = json.load(f)
        if "vmax_VEADE" in current_params:
            legacy_vmax_veade = current_params.pop("vmax_VEADE")
            current_params.setdefault("vmax_VEADE_fwd", legacy_vmax_veade)
            current_params.setdefault("vmax_VEADE_rev", legacy_vmax_veade)
        print(f"  Loaded {len(current_params)} params from {load_params}")

        all_bounds = {}
        for phase_params in PHASE_MAP.values():
            all_bounds.update(phase_params)
        clipped_count = 0
        for pname in list(current_params.keys()):
            if pname in all_bounds:
                _, lo, hi = all_bounds[pname]
                old_val = current_params[pname]
                current_params[pname] = float(np.clip(old_val, lo, hi))
                if current_params[pname] != old_val:
                    clipped_count += 1
        if clipped_count > 0:
            print(f"  Clipped {clipped_count} params to updated bounds")

    current_metrics = evaluate_monitor_metrics(global_primary, global_monitor_objectives, current_params if current_params else {})
    baseline_loss = current_metrics["target"]
    baseline_loss_breakdown = global_primary.loss_breakdown(current_params if current_params else {}, mode="fast")
    print(f"\n  Baseline loss (nRMSE): {baseline_loss:.4f}")
    if protected_metric_keys:
        print(f"  Baseline protected metrics: {format_metric_summary(current_metrics, protected_metric_keys)}")

    results_tsv = append_results_row(
        resolved_out_dir,
        {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "stage": "baseline",
            "target_scope": target_scope,
            "param_scope": param_scope,
            "baseline_target_loss": baseline_loss,
            "candidate_target_loss": baseline_loss,
            "joint_loss": current_metrics.get("joint", ""),
            "rank_loss": current_metrics.get("rank_loss", ""),
            "experimental_fit_loss": current_metrics.get("experimental_fit_loss", ""),
            "teacher_student_loss": current_metrics.get("teacher_student_loss", ""),
            "teacher_student_weight": current_metrics.get("teacher_student_weight", ""),
            "guardrail_loss": current_metrics.get("guardrail_loss", ""),
            "regularization_loss": current_metrics.get("regularization_loss", ""),
            "physiological_penalty_loss": current_metrics.get("physiological_penalty_loss", ""),
            "legacy_total_loss": current_metrics.get("legacy_total_loss", ""),
            "glycolysis_energy_loss": current_metrics.get("glycolysis_energy", ""),
            "nucleotide_purine_loss": current_metrics.get("nucleotide_purine", ""),
            "amino_redox_side_loss": current_metrics.get("amino_redox_side", ""),
            "extracellular_loss": current_metrics.get("extracellular", ""),
            "glycolysis_loss": current_metrics.get("glycolysis", ""),
            "endpoint_nrmse": current_metrics.get("endpoint_nrmse", ""),
            "status": "baseline",
            "description": load_params or "default",
        },
    )

    if generate_plots:
        plot_comparison(global_primary, current_params, "(Baseline)", save_path=str(resolved_out_dir / "baseline.png"))

    print("\n[2/4] Running optimization phases...")
    all_results = {}
    global_refinement_results = {}
    stage_reports = []
    stage_bundles = []
    optimized_phase_count = 0

    for stage_index, stage in enumerate(resolved_stage_plan, start=1):
        stage_name = stage["name"]
        stage_param_scope = stage["param_scope"]
        stage_parameter_classes = stage.get("parameter_classes")
        stage_identifiability = stage.get("identifiability_levels")
        stage_n_trials = int(stage.get("n_trials", n_trials))
        stage_global_trials = int(stage.get("global_trials", resolved_global_trials))
        stage_seed = int(stage.get("seed", seed))
        stage_start_loss = current_metrics["target"]
        stage_teacher_dataset = teacher_dataset
        stage_teacher_dataset_path = stage.get("teacher_dataset_path")
        if stage_teacher_dataset_path and (
            teacher_dataset is None
            or str(stage_teacher_dataset_path) != str(teacher_dataset.get("_dataset_path", teacher_dataset_path))
        ):
            stage_teacher_dataset = load_teacher_curve_dataset(stage_teacher_dataset_path)

        stage_bundle = build_objective_bundle(
            x0, time_exp, exp_values, name_to_row,
            target_scope=stage["target_scope"],
            t_max=t_max,
            atp_focus=bool(stage["atp_focus"]),
            atp_floor=float(stage["atp_floor"]),
            adp_floor=float(stage["adp_floor"]),
            amp_floor=float(stage["amp_floor"]),
            imp_floor=float(stage["imp_floor"]),
            adenylate_target=float(stage["adenylate_target"]),
            atp_penalty_weight=float(stage["atp_penalty_weight"]),
            amp_penalty_weight=float(stage["amp_penalty_weight"]),
            imp_penalty_weight=float(stage["imp_penalty_weight"]),
            pool_penalty_weight=float(stage["pool_penalty_weight"]),
            curve_fit_strength=float(stage["curve_fit_strength"]),
            teacher_dataset=stage_teacher_dataset,
            teacher_student_weight=float(stage.get("teacher_student_weight", teacher_student_weight)),
            teacher_curve_weight=stage.get("teacher_curve_weight", teacher_curve_weight),
            teacher_flux_weight=stage.get("teacher_flux_weight", teacher_flux_weight),
            teacher_target_weights=stage.get("teacher_target_weights", teacher_target_weights),
            teacher_focus_metabolites=stage.get("teacher_focus_metabolites", teacher_focus_metabolites),
            teacher_focus_weight=float(stage.get("teacher_focus_weight", teacher_focus_weight)),
        )
        stage_bundles.append(stage_bundle)

        stage_primary = stage_bundle["primary"]
        stage_phase_objectives = stage_bundle["phase_objectives"]

        stage_phase_labels = []
        stage_global_label = None

        print(f"\n{'#' * 70}")
        print(f"Stage {stage_index}: {stage_name}")
        print(f"  Stage target scope: {stage['target_scope']}")
        print(f"  Param scope: {stage_param_scope}")
        print(f"  Parameter classes: {stage_parameter_classes or 'all'}")
        print(f"  Identifiability: {stage_identifiability or 'all'}")
        print(f"  Trials per phase: {stage_n_trials}")
        print(f"  Global refinement trials: {stage_global_trials}")
        print(f"{'#' * 70}")

        for phase_num in stage["phases"]:
            phase_params = stage["phase_params"].get(phase_num, {})
            phase_name = PHASE_NAMES[phase_num]
            phase_objective = stage_phase_objectives.get(phase_num, stage_primary)

            phase_label = f"phase{phase_num}" if stage_name == "legacy" else f"{stage_name}.phase{phase_num}"
            phase_plot_name = f"phase{phase_num}.png" if stage_name == "legacy" else f"{stage_name}_phase{phase_num}.png"

            if not phase_params:
                print(f"\n{'=' * 60}")
                print(f"  Phase {phase_num}: {phase_name}")
                print(f"  Skipping (no parameters selected for stage '{stage_name}')")
                continue

            print(f"\n{'=' * 60}")
            print(f"  Phase {phase_num}: {phase_name}")
            print(f"  Objective: {phase_objective.objective_name} ({phase_objective.n_targets} targets)")
            print(f"  Optimizing {len(phase_params)} parameters...")
            print(f"  Parameters: {list(phase_params.keys())}")
            optimized_phase_count += 1

            t_start = time.time()
            pre_phase_params = current_params.copy()
            pre_phase_metrics = current_metrics.copy()

            if HAS_OPTUNA:
                best, best_val, _ = optimize_optuna(
                    phase_objective,
                    phase_params,
                    current_params,
                    n_trials=stage_n_trials,
                    study_name=f"{stage_name}_phase{phase_num}_{phase_objective.objective_name}",
                    seed=stage_seed,
                )
            else:
                best, best_val, _ = optimize_de(
                    phase_objective,
                    phase_params,
                    current_params,
                    max_iter=max(100, stage_n_trials // 3),
                )

            elapsed = time.time() - t_start

            candidate_params = pre_phase_params.copy()
            candidate_params.update(best)
            candidate_metrics = evaluate_monitor_metrics(global_primary, global_monitor_objectives, candidate_params)

            accepted, acceptance_reason = accept_monitor_metrics(
                pre_phase_metrics,
                candidate_metrics,
                monitor_regression_limits=global_monitor_regression_limits,
                max_eglc_final_increase_frac=stage.get("reject_eglc_final_increase_frac"),
                max_elac_final_drop_frac=stage.get("reject_elac_final_drop_frac"),
            )

            if accepted:
                current_params = candidate_params
                current_metrics = candidate_metrics

            new_loss = current_metrics["target"]

            print(f"\n  Phase {phase_num} Results:")
            print(f"    Time: {elapsed:.1f}s ({elapsed/60:.1f} min)")
            print(f"    Best phase-objective loss: {best_val:.4f}")
            print(f"    Cumulative loss: {new_loss:.4f}")
            print(f"    Improvement: {baseline_loss:.4f} -> {new_loss:.4f} ({(1-new_loss/baseline_loss)*100:.1f}%)")
            print(f"    Status: {'accepted' if accepted else 'discarded'}")
            print(f"    Decision: {acceptance_reason}")
            if protected_metric_keys:
                print(f"    Protected metrics: {format_metric_changes(pre_phase_metrics, candidate_metrics, protected_metric_keys)}")

            print("\n    Optimized parameters:")
            for pname, pval in sorted(best.items()):
                default = phase_params[pname][0]
                ratio_text = "n/a" if abs(default) < 1e-12 else f"{(pval / default):.2f}x"
                print(f"      {pname:25s}: {default:.6f} -> {pval:.6f} ({ratio_text})")

            if generate_plots:
                plot_comparison(global_primary, current_params, f"(After {phase_label})", save_path=str(resolved_out_dir / phase_plot_name))

            append_results_row(
                resolved_out_dir,
                {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "stage": phase_label,
                    "target_scope": stage["target_scope"],
                    "param_scope": stage_param_scope,
                    "baseline_target_loss": pre_phase_metrics["target"],
                    "candidate_target_loss": candidate_metrics["target"],
                    "joint_loss": candidate_metrics.get("joint", ""),
                    "rank_loss": candidate_metrics.get("rank_loss", ""),
                    "experimental_fit_loss": candidate_metrics.get("experimental_fit_loss", ""),
                    "teacher_student_loss": candidate_metrics.get("teacher_student_loss", ""),
                    "teacher_student_weight": candidate_metrics.get("teacher_student_weight", ""),
                    "guardrail_loss": candidate_metrics.get("guardrail_loss", ""),
                    "regularization_loss": candidate_metrics.get("regularization_loss", ""),
                    "physiological_penalty_loss": candidate_metrics.get("physiological_penalty_loss", ""),
                    "legacy_total_loss": candidate_metrics.get("legacy_total_loss", ""),
                    "glycolysis_energy_loss": candidate_metrics.get("glycolysis_energy", ""),
                    "nucleotide_purine_loss": candidate_metrics.get("nucleotide_purine", ""),
                    "amino_redox_side_loss": candidate_metrics.get("amino_redox_side", ""),
                    "extracellular_loss": candidate_metrics.get("extracellular", ""),
                    "glycolysis_loss": candidate_metrics.get("glycolysis", ""),
                    "endpoint_nrmse": candidate_metrics.get("endpoint_nrmse", ""),
                    "status": "keep" if accepted else "discard",
                    "description": acceptance_reason,
                },
            )

            all_results[phase_label] = {
                "stage_name": stage_name,
                "phase_num": phase_num,
                "phase_name": phase_name,
                "target_scope": stage["target_scope"],
                "param_scope": stage_param_scope,
                "parameter_classes": stage_parameter_classes,
                "identifiability_levels": stage_identifiability,
                "params": best,
                "loss": best_val,
                "candidate_loss": candidate_metrics["target"],
                "cumulative_loss": new_loss,
                "elapsed_s": elapsed,
                "accepted": accepted,
                "acceptance_reason": acceptance_reason,
                "candidate_metrics": candidate_metrics,
                "retained_metrics": current_metrics,
            }
            stage_phase_labels.append(phase_label)

        all_stage_params = {}
        for phase_num in stage["phases"]:
            all_stage_params.update(stage["phase_params"].get(phase_num, {}))

        if stage_global_trials > 0 and all_stage_params:
            stage_global_label = "global_refinement" if stage_name == "legacy" else f"{stage_name}.global_refinement"
            global_plot_name = "global_refinement.png" if stage_name == "legacy" else f"{stage_name}_global_refinement.png"

            print(f"\n{'=' * 60}")
            print("  Global Refinement Phase")
            print(f"  Joint optimization of {len(all_stage_params)} parameters ({stage_global_trials} trials)...")

            t_start = time.time()
            pre_global_params = current_params.copy()
            pre_global_metrics = current_metrics.copy()

            if HAS_OPTUNA:
                best, best_val, _ = optimize_optuna(
                    stage_primary,
                    all_stage_params,
                    current_params,
                    n_trials=stage_global_trials,
                    study_name=f"{stage_name}_global_refinement",
                    seed=stage_seed,
                )
            else:
                best, best_val, _ = optimize_de(
                    stage_primary,
                    all_stage_params,
                    current_params,
                    max_iter=max(1, stage_global_trials // 3),
                )

            elapsed = time.time() - t_start

            candidate_params = pre_global_params.copy()
            candidate_params.update(best)
            candidate_metrics = evaluate_monitor_metrics(global_primary, global_monitor_objectives, candidate_params)

            accepted, acceptance_reason = accept_monitor_metrics(
                pre_global_metrics,
                candidate_metrics,
                monitor_regression_limits=global_monitor_regression_limits,
                max_eglc_final_increase_frac=stage.get("reject_eglc_final_increase_frac"),
                max_elac_final_drop_frac=stage.get("reject_elac_final_drop_frac"),
            )

            if accepted:
                current_params.update(best)
                current_metrics = candidate_metrics
                print(f"\n  Global Refinement Results:")
                print(f"    Time: {elapsed:.1f}s ({elapsed/60:.1f} min)")
                print(
                    f"    Loss: {pre_global_metrics['target']:.4f} -> {candidate_metrics['target']:.4f} "
                    f"({(1-candidate_metrics['target']/pre_global_metrics['target'])*100:+.1f}%)"
                )
                print(f"    Decision: {acceptance_reason}")
            else:
                print(f"\n  Global refinement discarded ({pre_global_metrics['target']:.4f} -> {candidate_metrics['target']:.4f})")
                print(f"    Decision: {acceptance_reason}")
                print("    Keeping pre-refinement parameters.")

            if protected_metric_keys:
                print(f"    Protected metrics: {format_metric_changes(pre_global_metrics, candidate_metrics, protected_metric_keys)}")

            if generate_plots:
                plot_comparison(global_primary, current_params, f"(After {stage_global_label})", save_path=str(resolved_out_dir / global_plot_name))

            append_results_row(
                resolved_out_dir,
                {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "stage": stage_global_label,
                    "target_scope": stage["target_scope"],
                    "param_scope": stage_param_scope,
                    "baseline_target_loss": pre_global_metrics["target"],
                    "candidate_target_loss": candidate_metrics["target"],
                    "joint_loss": candidate_metrics.get("joint", ""),
                    "rank_loss": candidate_metrics.get("rank_loss", ""),
                    "experimental_fit_loss": candidate_metrics.get("experimental_fit_loss", ""),
                    "teacher_student_loss": candidate_metrics.get("teacher_student_loss", ""),
                    "teacher_student_weight": candidate_metrics.get("teacher_student_weight", ""),
                    "guardrail_loss": candidate_metrics.get("guardrail_loss", ""),
                    "regularization_loss": candidate_metrics.get("regularization_loss", ""),
                    "physiological_penalty_loss": candidate_metrics.get("physiological_penalty_loss", ""),
                    "legacy_total_loss": candidate_metrics.get("legacy_total_loss", ""),
                    "glycolysis_energy_loss": candidate_metrics.get("glycolysis_energy", ""),
                    "nucleotide_purine_loss": candidate_metrics.get("nucleotide_purine", ""),
                    "amino_redox_side_loss": candidate_metrics.get("amino_redox_side", ""),
                    "extracellular_loss": candidate_metrics.get("extracellular", ""),
                    "glycolysis_loss": candidate_metrics.get("glycolysis", ""),
                    "endpoint_nrmse": candidate_metrics.get("endpoint_nrmse", ""),
                    "status": "keep" if accepted else "discard",
                    "description": acceptance_reason,
                },
            )

            global_refinement_results[stage_global_label] = {
                "stage_name": stage_name,
                "target_scope": stage["target_scope"],
                "param_scope": stage_param_scope,
                "parameter_classes": stage_parameter_classes,
                "identifiability_levels": stage_identifiability,
                "params": best,
                "loss": best_val,
                "candidate_loss": candidate_metrics["target"],
                "cumulative_loss": current_metrics["target"],
                "elapsed_s": elapsed,
                "accepted": accepted,
                "acceptance_reason": acceptance_reason,
                "candidate_metrics": candidate_metrics,
                "retained_metrics": current_metrics,
            }

        stage_end_loss = current_metrics["target"]
        stage_reports.append(
            {
                "name": stage_name,
                "target_scope": stage["target_scope"],
                "param_scope": stage_param_scope,
                "parameter_classes": stage_parameter_classes,
                "identifiability_levels": stage_identifiability,
                "include_params": stage.get("include_params"),
                "exclude_params": stage.get("exclude_params"),
                "selected_params": stage["selected_param_names"],
                "phase_labels": stage_phase_labels,
                "global_refinement_label": stage_global_label,
                "n_trials": stage_n_trials,
                "global_trials": stage_global_trials,
                "atp_focus": stage["atp_focus"],
                "curve_fit_strength": stage["curve_fit_strength"],
                "teacher_dataset_path": stage.get("teacher_dataset_path"),
                "teacher_student_weight": stage.get("teacher_student_weight", teacher_student_weight),
                "teacher_curve_weight": stage.get("teacher_curve_weight", teacher_curve_weight),
                "teacher_flux_weight": stage.get("teacher_flux_weight", teacher_flux_weight),
                "reject_eglc_final_increase_frac": stage.get("reject_eglc_final_increase_frac"),
                "reject_elac_final_drop_frac": stage.get("reject_elac_final_drop_frac"),
                "start_loss": stage_start_loss,
                "end_loss": stage_end_loss,
                "accepted": bool(stage["selected_param_names"]) and stage_end_loss <= stage_start_loss + 1e-12,
            }
        )

    if optimized_phase_count == 0:
        raise ValueError(
            f"No parameters selected for phases={phases}, param_scope='{param_scope}', "
            f"and optimization_strategy='{optimization_strategy}'"
        )

    print("\n[3/4] Final evaluation...")
    current_metrics = evaluate_monitor_metrics(global_primary, global_monitor_objectives, current_params)
    final_loss = current_metrics["target"]
    print(f"  Final loss (nRMSE): {final_loss:.4f}")
    print(f"  Improvement: {baseline_loss:.4f} -> {final_loss:.4f} ({(1-final_loss/baseline_loss)*100:.1f}%)")
    if protected_metric_keys:
        print(f"  Final protected metrics: {format_metric_summary(current_metrics, protected_metric_keys)}")

    report = global_primary.detailed_report(current_params)
    print("\n  Per-metabolite nRMSE (top 15 worst):")
    for r in report[:15]:
        flag = " ***" if r["nrmse"] > 1.0 else ""
        print(
            f"    {r['name']:8s}: nRMSE={r['nrmse']:.3f}  RMSE={r['rmse']:.4f}  "
            f"sim={r['sim_final']:.4f}  exp={r['exp_final']:.4f}{flag}"
        )

    if generate_plots:
        plot_comparison(global_primary, current_params, "(Final Calibrated)", save_path=str(resolved_out_dir / "final_calibrated.png"))

    print("\n[4/4] Saving results...")

    params_file = resolved_out_dir / "best_params.json"
    if final_loss <= baseline_loss:
        with open(params_file, "w") as f:
            json.dump(current_params, f, indent=2)
        print(f"  Parameters: {params_file}")
    else:
        regressed_file = resolved_out_dir / "last_run_params.json"
        with open(regressed_file, "w") as f:
            json.dump(current_params, f, indent=2)
        print(f"  WARNING: Loss regressed ({baseline_loss:.4f} -> {final_loss:.4f})")
        print(f"  NOT overwriting {params_file}")
        print(f"  Regressed params saved to: {regressed_file}")

    append_results_row(
        resolved_out_dir,
        {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "stage": "final",
            "target_scope": target_scope,
            "param_scope": param_scope,
            "baseline_target_loss": baseline_loss,
            "candidate_target_loss": final_loss,
            "joint_loss": current_metrics.get("joint", ""),
            "rank_loss": current_metrics.get("rank_loss", ""),
            "experimental_fit_loss": current_metrics.get("experimental_fit_loss", ""),
            "teacher_student_loss": current_metrics.get("teacher_student_loss", ""),
            "teacher_student_weight": current_metrics.get("teacher_student_weight", ""),
            "guardrail_loss": current_metrics.get("guardrail_loss", ""),
            "regularization_loss": current_metrics.get("regularization_loss", ""),
            "physiological_penalty_loss": current_metrics.get("physiological_penalty_loss", ""),
            "legacy_total_loss": current_metrics.get("legacy_total_loss", ""),
            "glycolysis_energy_loss": current_metrics.get("glycolysis_energy", ""),
            "nucleotide_purine_loss": current_metrics.get("nucleotide_purine", ""),
            "amino_redox_side_loss": current_metrics.get("amino_redox_side", ""),
            "extracellular_loss": current_metrics.get("extracellular", ""),
            "glycolysis_loss": current_metrics.get("glycolysis", ""),
            "endpoint_nrmse": current_metrics.get("endpoint_nrmse", ""),
            "status": "keep" if final_loss <= baseline_loss else "discard",
            "description": str(results_tsv),
        },
    )

    final_loss_breakdown = global_primary.loss_breakdown(current_params, mode="fast")
    has_extracellular_final_gate = any(
        stage.get("reject_eglc_final_increase_frac") is not None
        or stage.get("reject_elac_final_drop_frac") is not None
        for stage in resolved_stage_plan
    )

    report_file = resolved_out_dir / "calibration_report.json"
    with open(report_file, "w") as f:
        json.dump(
            {
                "data_mode": data_mode,
                "experimental_data_source": data_source,
                "active_dataset_id": active_dataset_id,
                "active_dataset_label": active_dataset_label,
                "baseline_loss": baseline_loss,
                "final_loss": final_loss,
                "improvement_pct": (1 - final_loss / baseline_loss) * 100,
                "n_trials_per_phase": n_trials,
                "optimizer": "optuna_TPE" if HAS_OPTUNA else "scipy_DE",
                "seed": seed,
                "t_max": t_max,
                "time_unit_assumption": "days",
                "curve_fit_strength": curve_fit_strength,
                "teacher_dataset_path": teacher_dataset.get("_dataset_path") if teacher_dataset is not None else None,
                "teacher_dataset_label": teacher_dataset.get("dataset_label") if teacher_dataset is not None else None,
                "teacher_target_metabolites": teacher_dataset.get("target_metabolites") if teacher_dataset is not None else [],
                "teacher_target_weights": global_primary.teacher_target_weight_map if teacher_dataset is not None else {},
                "teacher_focus_metabolites": sorted(global_primary.teacher_focus_metabolites) if teacher_dataset is not None else [],
                "teacher_focus_weight": float(global_primary.teacher_focus_weight) if teacher_dataset is not None else DEFAULT_TEACHER_FOCUS_WEIGHT,
                "teacher_student_weight": teacher_student_weight,
                "teacher_curve_weight": float(global_primary.teacher_curve_weight),
                "teacher_flux_weight": float(global_primary.teacher_flux_weight),
                "target_scope": target_scope,
                "param_scope": param_scope,
                "optimization_strategy": optimization_strategy,
                "parameter_classes": normalize_name_list(parameter_classes),
                "objective_weights": global_primary.objective_weights(),
                "objective_hierarchy": {
                    "primary_metric": "fit_loss",
                    "secondary_metrics": ["diagnostic_only"],
                    "ranking_formula": (
                        "rank_loss = experimental_fit_loss + teacher_curve_weight * teacher_curve_loss + teacher_flux_weight * teacher_flux_loss"
                        if teacher_dataset is not None and (
                            global_primary.teacher_weight_split_active
                            or global_primary.teacher_curve_weight > 0.0
                            or global_primary.teacher_flux_weight > 0.0
                        )
                        else "rank_loss = experimental_fit_loss + teacher_student_weight * teacher_student_loss"
                        if teacher_dataset is not None and teacher_student_weight > 0.0
                        else "rank_loss = fit_loss"
                    ),
                    "acceptance_policy": (
                        "pure-fit acceptance with optional EGLC/ELAC final-state rejection gate; candidates are kept when fit improves "
                        "or ties with a better rank_loss, unless the configured final-state gate rejects them; regularization and "
                        "physiological penalties are still reported but no longer drive ranking"
                        if has_extracellular_final_gate
                        else "pure-fit acceptance; candidates are kept when fit improves or ties with a better rank_loss; "
                        "regularization and physiological penalties are still reported but no longer drive ranking"
                    ),
                },
                "baseline_loss_breakdown": baseline_loss_breakdown,
                "best_loss_breakdown": global_primary.best_loss_breakdown,
                "final_loss_breakdown": final_loss_breakdown,
                "resolved_stage_plan": resolved_stage_plan,
                "requested_target_metabolites": requested_target_metabolites,
                "target_metabolites": global_primary.target_names,
                "monitor_metrics": current_metrics,
                "results_tsv": str(results_tsv),
                "phases": all_results,
                "global_refinements": global_refinement_results,
                "stage_reports": stage_reports,
                "stages": stage_reports,
                "parameter_taxonomy": build_parameter_taxonomy(),
                "optimized_params": current_params,
                "per_metabolite": [r for r in report],
            },
            f,
            indent=2,
            default=str,
        )
    print(f"  Report: {report_file}")

    py_file = resolved_out_dir / "best_params.py"
    with open(py_file, "w") as f:
        f.write("# Optimized MM parameters from ML calibration\n")
        f.write(f"# Baseline nRMSE: {baseline_loss:.4f}\n")
        f.write(f"# Final nRMSE:    {final_loss:.4f}\n")
        f.write(f"# Improvement:    {(1-final_loss/baseline_loss)*100:.1f}%\n\n")
        f.write("CALIBRATED_PARAMS = {\n")
        for pname, pval in sorted(current_params.items()):
            if isinstance(pval, (int, float, np.integer, np.floating)) and not isinstance(pval, bool):
                rendered_value = f"{float(pval):.8f}"
            else:
                rendered_value = repr(pval)
            f.write(f"    '{pname}': {rendered_value},\n")
        f.write("}\n")
    print(f"  Python dict: {py_file}")

    print(f"\n{'=' * 70}")
    print("Calibration complete!")
    print(
        "Total objective evaluations: "
        f"{total_objective_calls(global_primary, global_phase_objectives, global_monitor_objectives, stage_bundles)}"
    )
    print(f"Final nRMSE: {final_loss:.4f}")
    print(f"{'=' * 70}")

    trajectory_csv_path = None
    if dump_trajectories:
        print("\n[4/4] Dumping trajectory CSV...")
        try:
            sol = global_primary._cached_solve(current_params, mode="dense")
            if sol.success:
                y = np.maximum(sol.y, 0.0)
                t = sol.t

                # Map ODE state indices to metabolite names via BRODBAR_METABOLITE_MAP.
                # Size the column list to the actual ODE state dimension (may exceed
                # NUM_BASE_METABOLITES if auxiliary states like phi/volume are present).
                n_states = y.shape[0]
                metabolite_columns = [f"state_{i}" for i in range(n_states)]
                for name, idx in BRODBAR_METABOLITE_MAP.items():
                    if 0 <= idx < n_states:
                        metabolite_columns[idx] = name
                df_full_metabolites = pd.DataFrame(y.T, columns=metabolite_columns)
                df_full_metabolites.insert(0, 'Time (days)', t)

                metabolites_dir = resolved_out_dir / "metabolites"
                metabolites_dir.mkdir(parents=True, exist_ok=True)
                trajectory_csv_path = metabolites_dir / "all_metabolites.csv"
                df_full_metabolites.to_csv(trajectory_csv_path, index=False)
                print(f"  Trajectory CSV saved to: {trajectory_csv_path}")
            else:
                print(f"  WARNING: Failed to solve ODE for trajectory dump: {sol.message}")
        except Exception as e:
            print(f"  WARNING: Failed to dump trajectory CSV: {e}")

    return current_params, final_loss, trajectory_csv_path


# AGENT_EDITABLE_END: diagnostics_reporting
# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ML-based MM recalibration")
    parser.add_argument("--phases", type=str, default="1,2,3", help="Comma-separated phase numbers")
    parser.add_argument("--n-trials", type=int, default=150, help="Optimization trials per phase")
    parser.add_argument(
        "--global-trials",
        type=int,
        default=None,
        help="Global refinement trials after stage phases (default: n_trials // 2; set 0 to skip)",
    )
    parser.add_argument("--load-params", type=str, default=None, help="Path to JSON file with initial parameters")
    parser.add_argument(
        "--target-scope",
        type=str,
        default="all",
        choices=["all", "extracellular", "glycolysis", "glycolysis_terminal", "glycolysis_extracellular", "core_glycolysis_energy"],
        help="Calibration target scope",
    )
    parser.add_argument(
        "--param-scope",
        type=str,
        default="all",
        choices=["all", "transport_only", "eade_focus", "glycolysis_mm", "core_km", "core_lower_glycolysis_probe", "glycolysis_terminal", "extracellular_coupled", "glycolysis_extracellular", "purine_transport_narrow", "hybrid_glucose_lactate", "hybrid_downstream_pk_eno", "hybrid_glucose_lactate_plus_downstream"],
        help="Parameter scope",
    )
    parser.add_argument("--skip-plots", action="store_true", help="Skip comparison plots")
    parser.add_argument("--atp-focus", action="store_true", help="Enable ATP-focused penalties")
    parser.add_argument("--atp-floor", type=float, default=0.15, help="Minimum ATP floor target")
    parser.add_argument("--adp-floor", type=float, default=0.05, help="Minimum ADP floor target")
    parser.add_argument("--amp-floor", type=float, default=0.04, help="Minimum AMP floor target")
    parser.add_argument("--imp-floor", type=float, default=0.02, help="Minimum IMP floor target")
    parser.add_argument("--adenylate-target", type=float, default=0.65, help="Target final adenylate pool retention ratio")
    parser.add_argument("--atp-penalty-weight", type=float, default=10.0, help="Penalty weight for ATP/ADP floor violations")
    parser.add_argument("--amp-penalty-weight", type=float, default=6.0, help="Penalty weight for AMP floor violations")
    parser.add_argument("--imp-penalty-weight", type=float, default=5.0, help="Penalty weight for IMP floor violations")
    parser.add_argument("--pool-penalty-weight", type=float, default=12.0, help="Penalty weight for adenylate pool retention violation")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--t-max", type=float, default=46.0, help="Calibration horizon in days")
    parser.add_argument("--curve-fit-strength", type=float, default=0.0, help="Curve-fit curriculum strength")
    parser.add_argument("--teacher-dataset-path", type=str, default=None, help="Optional JSON teacher curve dataset path")
    parser.add_argument(
        "--teacher-student-weight",
        type=float,
        default=DEFAULT_TEACHER_STUDENT_WEIGHT,
        help="Optional weight for dense teacher-student curve loss",
    )
    parser.add_argument(
        "--teacher-curve-weight",
        type=float,
        default=None,
        help="Optional explicit weight for teacher curve supervision; defaults to teacher-student weight when omitted",
    )
    parser.add_argument(
        "--teacher-flux-weight",
        type=float,
        default=None,
        help="Optional explicit weight for teacher flux supervision; defaults to teacher-student weight when omitted",
    )
    parser.add_argument(
        "--teacher-focus-metabolites",
        type=str,
        default=None,
        help="Optional comma-separated teacher metabolites to emphasize, e.g. EGLC,ELAC,LAC",
    )
    parser.add_argument(
        "--teacher-focus-weight",
        type=float,
        default=DEFAULT_TEACHER_FOCUS_WEIGHT,
        help="Multiplicative weight applied to focused teacher metabolites",
    )
    parser.add_argument("--out-dir", type=str, default=None, help="Optional output directory")
    parser.add_argument(
        "--optimization-strategy",
        type=str,
        default="legacy",
        choices=sorted(OPTIMIZATION_STRATEGY_CHOICES),
        help="Explicit optimization strategy",
    )
    parser.add_argument(
        "--parameter-classes",
        type=str,
        default=None,
        help="Optional comma-separated parameter classes to restrict optimization, e.g. vmax,km,hybrid,transport",
    )
    parser.add_argument(
        "--stage-plan-file",
        type=str,
        default=None,
        help="Optional JSON file containing an explicit stage_plan array",
    )

    args = parser.parse_args()
    phases = [int(p) for p in args.phases.split(",") if p.strip()]

    stage_plan = None
    if args.stage_plan_file:
        with open(args.stage_plan_file, "r") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict) and "stage_plan" in loaded:
            stage_plan = loaded["stage_plan"]
        elif isinstance(loaded, list):
            stage_plan = loaded
        else:
            raise ValueError("stage_plan file must be a JSON array or a JSON object with a 'stage_plan' field")

    run_calibration(
        phases=phases,
        n_trials=args.n_trials,
        global_trials=args.global_trials,
        load_params=args.load_params,
        target_scope=args.target_scope,
        param_scope=args.param_scope,
        generate_plots=not args.skip_plots,
        atp_focus=args.atp_focus,
        atp_floor=args.atp_floor,
        adp_floor=args.adp_floor,
        amp_floor=args.amp_floor,
        imp_floor=args.imp_floor,
        adenylate_target=args.adenylate_target,
        atp_penalty_weight=args.atp_penalty_weight,
        amp_penalty_weight=args.amp_penalty_weight,
        imp_penalty_weight=args.imp_penalty_weight,
        pool_penalty_weight=args.pool_penalty_weight,
        seed=args.seed,
        t_max=args.t_max,
        curve_fit_strength=args.curve_fit_strength,
        teacher_dataset_path=args.teacher_dataset_path,
        teacher_student_weight=args.teacher_student_weight,
        teacher_curve_weight=args.teacher_curve_weight,
        teacher_flux_weight=args.teacher_flux_weight,
        teacher_focus_metabolites=normalize_name_list(args.teacher_focus_metabolites),
        teacher_focus_weight=args.teacher_focus_weight,
        out_dir=args.out_dir,
        optimization_strategy=args.optimization_strategy,
        parameter_classes=args.parameter_classes,
        stage_plan=stage_plan,
    )
