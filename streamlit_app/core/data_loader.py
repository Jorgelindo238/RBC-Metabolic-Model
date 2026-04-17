"""
Data Loader - Load experimental data with Streamlit caching
"""
import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Add src to path for imports - calculate from this file's actual location
# __file__ is in streamlit_app/core/data_loader.py
# So parent = core, parent.parent = streamlit_app, parent.parent.parent = project root
this_file = Path(__file__).resolve()
project_root = this_file.parent.parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

def load_experimental_data():
    """
    Load experimental data from Bordbar et al. OR uploaded custom data.
    In validation mode, returns Bordbar data (custom data handled separately).
    Returns DataFrame with metabolite time series
    """
    # Check mode
    mode = st.session_state.get('uploaded_data_mode', '')
    uploaded_active = st.session_state.get('uploaded_data_active', False)
    
    # In "validation only" mode, always return Bordbar data
    # Custom data will be handled separately for comparison
    if uploaded_active and mode == "Use for validation only":
        return _load_experimental_data_cached()
    
    # In "Replace" mode, use custom data
    if uploaded_active and mode == "Replace experimental data":
        if 'uploaded_data' in st.session_state:
            return st.session_state['uploaded_data'].copy()
    
    # Default: load Bordbar data
    return _load_experimental_data_cached()

@st.cache_data(ttl=3600)
def _load_experimental_data_cached():
    """Cached version of experimental data loading from file."""
    try:
        data_path = src_path / "Data_Bordbar_et_al_exp.xlsx"
        df = pd.read_excel(data_path, engine='openpyxl')
        return df
    except Exception as e:
        st.error(f"Error loading experimental data: {e}")
        return None

def load_custom_validation_data():
    """
    Load custom uploaded data for validation/comparison.
    Returns DataFrame or None if not available.
    """
    mode = st.session_state.get('uploaded_data_mode', '')
    uploaded_active = st.session_state.get('uploaded_data_active', False)
    
    if uploaded_active and mode == "Use for validation only":
        if 'uploaded_data' in st.session_state:
            return st.session_state['uploaded_data'].copy()
    
    return None

@st.cache_data(ttl=3600)
def load_fitted_parameters():
    """
    Load polynomial-logarithmic fitted parameters for curve fitting
    Returns DataFrame with coefficients (a, b, c, d, e) for each metabolite
    """
    try:
        data_path = project_root / "Data_Bordbar_et_al_exp_fitted_params.csv"
        df = pd.read_csv(data_path)
        return df
    except Exception as e:
        st.error(f"Error loading fitted parameters: {e}")
        return None

@st.cache_data(ttl=3600)
def load_initial_conditions(source="JA Final"):
    """
    Load initial conditions for metabolites
    
    Parameters:
    -----------
    source : str
        "JA Final" - from Initial_conditions_JA_Final.xls
        "Bordbar" - from Data_Bordbar_et_al_exp.xlsx first timepoint
    
    Returns:
    --------
    dict : metabolite_name -> concentration (mM)
    """
    try:
        if source == "JA Final":
            ic_path = project_root / "Initial_conditions_JA_Final.xls"
            df = pd.read_excel(ic_path, engine='xlrd')
            # Assuming columns: Metabolite, Concentration
            if 'Metabolite' in df.columns and 'Concentration' in df.columns:
                return dict(zip(df['Metabolite'], df['Concentration']))
            else:
                # Try first two columns
                return dict(zip(df.iloc[:, 0], df.iloc[:, 1]))
        
        elif source == "Bordbar":
            exp_data = load_experimental_data()
            if exp_data is not None:
                # Get first timepoint for each metabolite
                ic_dict = {}
                for col in exp_data.columns:
                    if col != 'Time':
                        ic_dict[col] = exp_data[col].iloc[0]
                return ic_dict
    
    except Exception as e:
        st.error(f"Error loading initial conditions: {e}")
        return {}

@st.cache_data
def get_metabolite_list():
    """
    Get list of all metabolites in the model
    Returns list of metabolite names
    """
    try:
        from equadiff_brodbar import BRODBAR_METABOLITE_MAP
        return list(BRODBAR_METABOLITE_MAP.keys())
    except Exception as e:
        st.warning(f"Could not load metabolite list: {e}")
        return []

@st.cache_data
def get_data_summary():
    """
    Get summary statistics of experimental data
    Returns dict with summary info
    """
    exp_data = load_experimental_data()
    if exp_data is None:
        return {}
    
    summary = {
        'n_metabolites': len(exp_data.columns) - 1,  # excluding Time
        'n_timepoints': len(exp_data),
        'time_range': (exp_data['Time'].min(), exp_data['Time'].max()) if 'Time' in exp_data.columns else (0, 0),
        'metabolites': list(exp_data.columns[exp_data.columns != 'Time'])
    }
    
    return summary

def validate_data_files():
    """
    Check if all required data files exist OR if uploaded data is available
    Returns dict with file availability status
    """
    # Check if custom uploaded data is available in session_state
    if 'uploaded_data_active' in st.session_state and st.session_state.get('uploaded_data_active'):
        # Custom data is available - all files are considered "valid"
        return {
            'experimental_data': True,
            'fitted_params': True,  # Will use uploaded data instead
            'initial_conditions': True  # Will use uploaded data first timepoint
        }
    
    # Otherwise check physical files in src directory
    required_files = {
        'experimental_data': src_path / "Data_Bordbar_et_al_exp.xlsx",
        'fitted_params': src_path / "Data_Bordbar_et_al_exp_fitted_params.csv",
        'initial_conditions': src_path / "Initial_conditions_JA_Final.xls"
    }
    
    status = {}
    for name, path in required_files.items():
        status[name] = path.exists()
    
    return status
