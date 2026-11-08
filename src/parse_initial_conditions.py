"""
Python equivalent of the parse_initcond_ja.m MATLAB function.
This module handles parsing initial conditions from Excel files.
"""
import os
import numpy as np
import pandas as pd
from pathlib import Path

# Get src directory for data file paths
_THIS_FILE = Path(__file__).resolve()
_SRC_DIR = _THIS_FILE.parent  # This file is in src/
_DATA_FILE = _SRC_DIR / "Data_Bordbar_et_al_exp.xlsx"

INITIALIZATION_POLICIES = {
    "legacy_experimental_alias",
    "compartment_strict_generic",
    "compartment_strict_historical",
}

from equadiff_brodbar import NUM_BASE_METABOLITES, H2O2_INDEX, PHI_INDEX


def _named_values_from_frame(frame, *, name_column=0, value_column=1):
    values = {}
    for name, value in zip(frame.iloc[:, name_column], frame.iloc[:, value_column]):
        if pd.isna(name) or pd.isna(value):
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        values[str(name).strip().upper()] = numeric
    return values


def _resolve_historical_path(file_path):
    path = Path(file_path)
    if path.exists():
        return path
    candidate = _SRC_DIR / path.name
    return candidate if candidate.exists() else path


def build_initial_conditions(
    model_metabolites,
    file_path,
    *,
    initialization_policy="legacy_experimental_alias",
):
    """Build model-ordered initial values and record each value's provenance."""
    if initialization_policy not in INITIALIZATION_POLICIES:
        raise ValueError(
            f"Unknown initialization policy {initialization_policy!r}; expected one of "
            f"{sorted(INITIALIZATION_POLICIES)}"
        )

    experimental = pd.read_excel(_DATA_FILE, engine="openpyxl")
    experimental_values = _named_values_from_frame(experimental)
    historical_values = {}
    if initialization_policy == "compartment_strict_historical":
        historical_path = _resolve_historical_path(file_path)
        historical = pd.read_excel(historical_path, sheet_name=0, header=None)
        historical_values = _named_values_from_frame(historical)

    x0 = np.ones(len(model_metabolites), dtype=float)
    provenance = {}
    for index, model_metabolite in enumerate(model_metabolites):
        name = str(model_metabolite).strip().upper()
        value = 1.0
        source = "generic_1mM"
        if name in historical_values:
            value = historical_values[name]
            source = "historical_exact"
        if name in experimental_values:
            value = experimental_values[name]
            source = "brodbar_exact"
        elif initialization_policy == "legacy_experimental_alias":
            if name.startswith("E") and name[1:] in experimental_values:
                value = experimental_values[name[1:]]
                source = f"legacy_compartment_alias:{name[1:]}"
            elif not name.startswith("E") and f"E{name}" in experimental_values:
                value = experimental_values[f"E{name}"]
                source = f"legacy_compartment_alias:E{name}"
        x0[index] = max(float(value), 1e-6)
        provenance[name] = source
    return x0, provenance


def parse_initial_conditions(
    model,
    file_path,
    initialization_policy="legacy_experimental_alias",
):
    """
    Python equivalent of parse_initcond_ja.m MATLAB function.
    Parses initial conditions from experimental data using correct model metabolite order.
    
    Parameters:
    -----------
    model : dict
        The metabolic model from parse.py
    file_path : str
        Path to the Excel file with initial conditions (not used, experimental data is used instead)
        
    Returns:
    --------
    x0 : numpy.ndarray
        Vector of initial conditions for all metabolites
    x0_name : list
        List of metabolite names corresponding to x0 values
    """
    print("Using initial conditions from experimental data (Data_Bordbar_et_al_exp.xlsx)")
    print("Mapping to actual model metabolite order")
    
    # Load experimental data - use first experimental time point as initial conditions
    try:
        df = pd.read_excel(_DATA_FILE, engine='openpyxl')
        exp_data = _named_values_from_frame(df)
        
        print(f"Loaded {len(exp_data)} experimental initial values from first time point")
        
    except Exception as e:
        print(f"ERROR loading experimental data: {e}")
        # Fallback to default values (base metabolites + pHi)
        n_with_phi = NUM_BASE_METABOLITES + 1
        x0 = np.ones(n_with_phi)
        x0[H2O2_INDEX] = 0.0001  # H2O2
        x0[PHI_INDEX] = 7.2      # pHi
        x0_names = [f"x{i}" for i in range(n_with_phi)]
        return x0, x0_names
    
    # Use model metabolite order if available
    if model and 'metab' in model:
        model_metabolites = model['metab']
        print(f"Using model with {len(model_metabolites)} metabolites")
    else:
        print("No model provided, using default metabolite order")
        model_metabolites = [f"x{i}" for i in range(NUM_BASE_METABOLITES)]
    
    # Create initial conditions vector matching model order.
    x0, provenance = build_initial_conditions(
        model_metabolites,
        file_path,
        initialization_policy=initialization_policy,
    )
    x0_names = model_metabolites.copy()
    mapped_count = sum(source != "generic_1mM" for source in provenance.values())
    alias_count = sum(
        source.startswith("legacy_compartment_alias") for source in provenance.values()
    )
    print(
        f"Initialized {mapped_count} model positions with policy "
        f"{initialization_policy} ({alias_count} compartment aliases)"
    )
    
    # Ensure we have enough metabolites for Brodbar model (base + pHi)
    expected_size = NUM_BASE_METABOLITES + 1
    if len(x0) < expected_size:
        print(f"Extending from {len(x0)} to {expected_size} metabolites ({NUM_BASE_METABOLITES} base + pHi)")
        x0_extended = np.ones(expected_size)
        x0_extended[:len(x0)] = x0
        x0 = x0_extended
        
        # Extend names
        x0_names_extended = [f"x{i}" for i in range(expected_size)]
        x0_names_extended[:len(x0_names)] = x0_names
        x0_names = x0_names_extended
    
    # Set special metabolites
    x0[H2O2_INDEX] = max(x0[H2O2_INDEX], 0.0001)  # H2O2 (part of base metabolites)
    x0[PHI_INDEX] = 7.2                             # pHi (dynamic metabolite)
    
    # Clean the vector
    x0 = np.nan_to_num(x0, nan=0.001, posinf=1.0, neginf=0.001)
    x0 = np.maximum(x0, 1e-6)
    
    print(f"Created initial conditions vector with {len(x0)} metabolites using experimental data")
    
    return x0, x0_names


if __name__ == "__main__":
    # Example usage
    from parse import parse
    
    model = parse(os.path.join("RBC", "Rxn_RBC.txt"))
    if model:
        x0, x0_name = parse_initial_conditions(model, "Initial_conditions_JA_Final.xls")
        print(f"Loaded initial conditions for {len(x0_name)} metabolites")
