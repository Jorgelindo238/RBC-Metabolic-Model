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

from equadiff_brodbar import NUM_BASE_METABOLITES, H2O2_INDEX, PHI_INDEX


def parse_initial_conditions(model, file_path):
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
        exp_metabolites = df.iloc[:, 0].tolist()  # First column (metabolite names)
        exp_values = df.iloc[:, 1].tolist()      # Second column (first time point values)
        
        exp_data = {}
        for name, value in zip(exp_metabolites, exp_values):
            if pd.notna(name) and pd.notna(value):
                exp_data[str(name).strip().upper()] = float(value)  # Store in uppercase for matching
        
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
    
    # Create initial conditions vector matching model order
    x0 = np.ones(len(model_metabolites))  # Default to 1.0
    x0_names = model_metabolites.copy()
    
    # Map experimental values to correct model positions
    mapped_count = 0
    for i, model_met in enumerate(model_metabolites):
        model_met_upper = model_met.upper()
        
        # Try exact match first
        if model_met_upper in exp_data:
            x0[i] = max(exp_data[model_met_upper], 1e-6)
            mapped_count += 1
        else:
            # Try with/without E prefix for extracellular metabolites
            if model_met_upper.startswith('E'):
                # Try without E prefix
                base_name = model_met_upper[1:]
                if base_name in exp_data:
                    x0[i] = max(exp_data[base_name], 1e-6)
                    mapped_count += 1
            else:
                # Try with E prefix
                e_name = 'E' + model_met_upper
                if e_name in exp_data:
                    x0[i] = max(exp_data[e_name], 1e-6)
                    mapped_count += 1
                # Also try the base name directly
                elif model_met_upper in exp_data:
                    x0[i] = max(exp_data[model_met_upper], 1e-6)
                    mapped_count += 1
    
    print(f"Successfully mapped {mapped_count} experimental values to model positions")
    
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
