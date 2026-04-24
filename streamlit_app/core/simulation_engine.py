"""

Simulation Engine - Wrapper for RBC metabolic simulations

Integrates with existing src/ code for Streamlit interface

"""

import streamlit as st

import numpy as np

from scipy.integrate import solve_ivp

import time

from pathlib import Path

import sys

import json
import traceback

from typing import Any, Dict, List, Optional, Tuple



# Add src to path - calculate from this file's actual location

# __file__ is in streamlit_app/core/simulation_engine.py

# So parent = core, parent.parent = streamlit_app, parent.parent.parent = project root

this_file = Path(__file__).resolve()

project_root = this_file.parent.parent.parent

src_path = project_root / "src"

if str(src_path) not in sys.path:

    sys.path.insert(0, str(src_path))





class SimpleFluxTracker:

    """Simple flux tracker compatible with equadiff_brodbar."""

    def __init__(self):

        self.times = []

        self.fluxes = {}



    def add_timepoint(self, t: float, flux_dict: dict):

        """Add flux values for a specific timepoint."""

        self.times.append(t)

        for reaction, flux in flux_dict.items():

            if reaction not in self.fluxes:

                self.fluxes[reaction] = []

            self.fluxes[reaction].append(flux)





def _normalize_dataset_metabolite(name: Any) -> str:

    return str(name).strip().upper()





def _build_dataset_experimental_payload(active_dataset: dict | None) -> dict:

    if not active_dataset:

        return {

            "time_points": [],

            "metabolites": [],

            "values": [],

        }



    mapped_series = {

        _normalize_dataset_metabolite(key): value

        for key, value in (active_dataset.get("mapped_series_by_metabolite") or {}).items()

    }

    mapped_metabolites = active_dataset.get("mapped_metabolites") or list(mapped_series.keys())

    metabolites: List[str] = []

    values: List[List[float]] = []



    for metabolite in mapped_metabolites:

        normalized = _normalize_dataset_metabolite(metabolite)

        series = mapped_series.get(normalized)

        if series is None:

            continue

        metabolites.append(normalized)

        values.append([float(value) for value in series])



    return {

        "time_points": [float(value) for value in active_dataset.get("time_points", [])],

        "metabolites": metabolites,

        "values": values,

    }





def _apply_dataset_to_initial_conditions(

    x0: np.ndarray,

    active_dataset: dict | None,

):

    if not active_dataset:

        return x0, [], None



    mapped_series = {

        _normalize_dataset_metabolite(key): value

        for key, value in (active_dataset.get("mapped_series_by_metabolite") or {}).items()

    }

    if not mapped_series:

        return x0, [], "uploaded dataset had no mapped metabolites"



    x0 = np.array(x0, dtype=float, copy=True)

    applied: List[str] = []

    skipped: List[str] = []



    for metabolite, series in mapped_series.items():

        if not series:

            continue



        normalized = _normalize_dataset_metabolite(metabolite)

        idx = BRODBAR_METABOLITE_MAP.get(normalized)

        if idx is None or idx >= len(x0):

            skipped.append(normalized)

            continue



        x0[idx] = max(float(series[0]), 1e-6)

        applied.append(normalized)



    if not applied:

        reason = "uploaded dataset did not map onto a simulation state"

        if skipped:

            reason = f"{reason} ({len(skipped)} unmapped)"

        return x0, [], reason



    return x0, applied, None





# Import existing modules

try:

    from equadiff_brodbar import (equadiff_brodbar, BRODBAR_METABOLITE_MAP,

                                  _load_experimental_first_values,

                                  NUM_BASE_METABOLITES, NUM_TOTAL_METABOLITES,

                                  PHI_INDEX, PHE_INDEX)

    from parse_initial_conditions import parse_initial_conditions

    from ph_perturbation import (PhPerturbation, create_step_perturbation,

                                 create_ramp_perturbation, get_acidosis_scenario,

                                 get_alkalosis_scenario)

    SIMULATION_AVAILABLE = True

    PH_MODULES_AVAILABLE = True

except ImportError:

    SIMULATION_AVAILABLE = False

    PH_MODULES_AVAILABLE = False

    import traceback

    error_details = traceback.format_exc()

    st.error(f"❌ Could not import simulation modules:\n```python\n{error_details}\n```")



    # Show debugging info

    st.info(f"""🔍 **Path Debug Info:**

- This file: `{this_file}`

- Project root: `{project_root}`

- Src path: `{src_path}`

- Src exists: `{src_path.exists()}`

- equadiff_brodbar.py exists: `{(src_path / 'equadiff_brodbar.py').exists()}`

    """)



    st.warning("""💡 **Common Fixes:**

1. Make sure you're in the correct venv

2. Check that all dependencies are installed: `pip install -r requirements.txt`

3. Verify src/ modules don't have import errors

    """)





class SimulationEngine:

    """

    RBC Metabolic Model Simulation Engine for Streamlit

    """



    def __init__(self):

        self.results = None

        self.status = "idle"

        self.error_message = None



    def run_simulation(self,

                      t_max=42,

                      curve_fit_strength=0.0,

                      ic_source="JA Final",

                      solver_method="RK45",

                      rtol=1e-6,

                      atol=1e-8,

                      ph_perturbation_type="None",

                      ph_severity="Moderate",

                      ph_target=7.0,

                      ph_duration=6,

                      progress_callback=None,

                      custom_params=None,

                      research_data_mode="default_bordbar_mode",

                      active_dataset=None,

                      active_dataset_id=None,

                      active_dataset_label=None,

                      autoload_calibrated_params=True):

        """

        Run RBC metabolic simulation



        Parameters:

        -----------

        t_max : float

            Maximum simulation time (days)

        curve_fit_strength : float

            Curve fitting strength (0.0 to 1.0)

        ic_source : str

            Initial conditions source

        solver_method : str

            ODE solver method ('RK45', 'BDF', 'LSODA')

        rtol, atol : float

            Relative and absolute tolerances

        progress_callback : callable

            Function(progress, message) for progress updates

        custom_params : dict, optional

            Dictionary of custom parameter values for optimization.

            Format: {'vmax_VELAC': 0.65, 'km_LAC': 0.8, ...}

            If None, uses default model parameters.

        autoload_calibrated_params : bool

            If True, auto-load Simulations/brodbar/calibration/best_params.json

            when custom_params is None. Set False for reproducible default baselines.



        Returns:

        --------

        dict : Simulation results

        """



        if not SIMULATION_AVAILABLE:

            return {"error": "Simulation modules not available"}

        if float(t_max) <= 1:

            return {
                "error": "Simulation duration t_max must be greater than 1 day; use at least 2 days.",
                "success": False,
            }



        try:

            self.status = "running"

            start_time = time.time()

            params_source = 'provided' if custom_params is not None else 'defaults'



            # Auto-load calibrated parameters if none provided and explicitly enabled

            if custom_params is None and autoload_calibrated_params:

                cal_path = project_root / "Simulations" / "brodbar" / "calibration" / "best_params.json"

                if cal_path.exists():

                    try:

                        with open(cal_path, 'r', encoding='utf-8-sig') as f:

                            custom_params = json.load(f)

                    except (json.JSONDecodeError, UnicodeDecodeError):

                        with open(cal_path, 'r', encoding='utf-16') as f:

                            custom_params = json.load(f)

                    params_source = 'auto_loaded'

                    if progress_callback:

                        progress_callback(0.05, f"Auto-loaded {len(custom_params)} calibrated MM parameters")

            elif custom_params is None and progress_callback:

                progress_callback(0.05, "Using default MM parameters (autoload disabled)")



            # Load experimental first values for conservation pools (same as main.py)

            try:

                _load_experimental_first_values()

            except Exception:

                pass  # Non-critical, model will use defaults



            # Update progress

            if progress_callback:

                progress_callback(0.1, "Loading experimental data...")



            # Load the Bordbar reference dataset directly like CLI does.

            # The custom dataset, when present, will be applied as a separate

            # active research input rather than replacing this reference load in-place.

            try:

                import pandas as pd

                data_file = src_path / "Data_Bordbar_et_al_exp.xlsx"

                df = pd.read_excel(data_file)



                # Extract metabolite names and data (same as CLI main.py)

                reference_metabolites = df.iloc[:, 0].tolist()  # First column = metabolite names

                metabolites_data = df.iloc[:, 1:].values  # Remaining columns = concentrations

                reference_time = np.array([float(col) for col in df.columns[1:]])  # Column headers = time points



                # Keep original shape: (n_metabolites, n_timepoints) like CLI

                # This is the format expected by visualization

                reference_values = metabolites_data



                if progress_callback:

                    progress_callback(0.15, f"Loaded {len(reference_metabolites)} Bordbar reference metabolites")



            except Exception as e:

                if progress_callback:

                    progress_callback(0.15, f"Warning: Could not load experimental data: {e}")

                reference_metabolites = []

                reference_values = np.array([])

                reference_time = np.array([])



            # Load custom validation data if available

            custom_val_metabolites = []

            custom_val_values = np.array([])

            custom_val_time = np.array([])



            # Check for custom validation data in session state

            mode = st.session_state.get('uploaded_data_mode', '')

            uploaded_active = st.session_state.get('uploaded_data_active', False)



            if uploaded_active and mode == "Use for validation only":

                if 'uploaded_data' in st.session_state:

                    custom_df = st.session_state['uploaded_data']



                    if custom_df is not None and not custom_df.empty:

                        # Extract time and metabolite data

                        if 'Time' in custom_df.columns:

                            custom_val_time = custom_df['Time'].values

                            custom_val_metabolites = [col for col in custom_df.columns if col != 'Time']



                            # Build values array (n_metabolites, n_timepoints)

                            custom_val_values = np.array([custom_df[met].values for met in custom_val_metabolites])



                            if progress_callback:

                                progress_callback(0.17, f"Loaded {len(custom_val_metabolites)} custom metabolites for validation")



            active_dataset_payload = _build_dataset_experimental_payload(active_dataset)

            dataset_applied = False

            dataset_fallback_reason = None

            dataset_applied_metabolites = []



            if research_data_mode == "custom_user_data_mode":

                if active_dataset_payload["metabolites"]:

                    custom_val_time = np.array(active_dataset_payload["time_points"], dtype=float)

                    custom_val_metabolites = list(active_dataset_payload["metabolites"])

                    custom_val_values = np.array(active_dataset_payload["values"], dtype=float)

                    dataset_applied = True

                    if progress_callback:

                        progress_callback(

                            0.18,

                            f"Loaded {len(custom_val_metabolites)} mapped metabolites from the active custom dataset",

                        )

                else:

                    dataset_fallback_reason = "Custom dataset was active but no mapped metabolites were available"



            if progress_callback:

                progress_callback(0.2, "Setting up initial conditions...")



            # Create model structure for Bordbar

            n_with_phi = NUM_BASE_METABOLITES + 1  # base metabolites + pHi

            metabolite_list = [''] * n_with_phi

            for name, idx in BRODBAR_METABOLITE_MAP.items():

                if idx < n_with_phi:

                    metabolite_list[idx] = name

            model = {'metab': metabolite_list}



            # Parse initial conditions

            ic_file = src_path / "Initial_conditions_JA_Final.xls"

            x0, _ = parse_initial_conditions(model, str(ic_file))

            n_metabolites = len(x0)



            if progress_callback:

                progress_callback(0.25, "Configuring pH perturbation...")



            # Configure pH perturbation if requested

            ph_perturbation = None

            if ph_perturbation_type != "None" and PH_MODULES_AVAILABLE:

                # Internal simulation time axis is days. UI controls expose hours,

                # so convert user-facing pH timing inputs to days here.

                ph_start_days = 2.0 / 24.0

                ph_duration_days = float(ph_duration) / 24.0

                try:

                    if ph_perturbation_type == "Acidosis":

                        acidosis_targets = {"Mild": 7.2, "Moderate": 7.0, "Severe": 6.8}

                        pH_final = acidosis_targets.get(ph_severity, 7.0)

                        ph_perturbation = create_ramp_perturbation(

                            pH_initial=7.4,

                            pH_final=pH_final,

                            t_start=ph_start_days,

                            duration=ph_duration_days

                        )

                        if progress_callback:

                            progress_callback(0.28, f"pH: Acidosis ({ph_severity}, duration={ph_duration:.1f}h)")

                    elif ph_perturbation_type == "Alkalosis":

                        alkalosis_targets = {"Mild": 7.6, "Moderate": 7.7, "Severe": 7.8}

                        pH_final = alkalosis_targets.get(ph_severity, 7.7)

                        ph_perturbation = create_ramp_perturbation(

                            pH_initial=7.4,

                            pH_final=pH_final,

                            t_start=ph_start_days,

                            duration=ph_duration_days

                        )

                        if progress_callback:

                            progress_callback(0.28, f"pH: Alkalosis ({ph_severity}, duration={ph_duration:.1f}h)")

                    elif ph_perturbation_type == "Step":

                        ph_perturbation = create_step_perturbation(

                            pH_target=ph_target,

                            t_start=ph_start_days

                        )

                        if progress_callback:

                            progress_callback(0.28, f"pH: Step to {ph_target} at {ph_start_days*24.0:.1f}h")

                    elif ph_perturbation_type == "Ramp":

                        ph_perturbation = create_ramp_perturbation(

                            pH_initial=7.4,

                            pH_final=ph_target,

                            t_start=ph_start_days,

                            duration=ph_duration_days

                        )

                        if progress_callback:

                            progress_callback(0.28, f"pH: Ramp to {ph_target} over {ph_duration:.1f}h")



                    if ph_perturbation:

                        if progress_callback:

                            progress_callback(0.3, "pH perturbation configured")

                except Exception as e:

                    if progress_callback:

                        progress_callback(0.3, f"Warning: pH setup failed - {str(e)}")

                    ph_perturbation = None



            # Add pHe to initial conditions if pH perturbation is active

            if ph_perturbation:

                # System needs NUM_TOTAL_METABOLITES: base + pHi + pHe

                # x0 currently has base+1 metabolites (base + pHi)

                # Add pHe at physiological value (7.4)

                x0 = np.append(x0, 7.4)

                n_metabolites = len(x0)

                if progress_callback:

                    progress_callback(0.3, f"Added pHe to initial conditions ({n_metabolites} metabolites)")



            if research_data_mode == "custom_user_data_mode":

                x0, dataset_applied_metabolites, overlay_reason = _apply_dataset_to_initial_conditions(

                    x0,

                    active_dataset,

                )

                if dataset_applied_metabolites:

                    dataset_applied = True

                    if progress_callback:

                        progress_callback(

                            0.305,

                            f"Applied {len(dataset_applied_metabolites)} custom dataset metabolites to initial conditions",

                        )

                else:

                    dataset_applied = False

                    dataset_fallback_reason = dataset_fallback_reason or overlay_reason or "Custom dataset could not be applied to initial conditions"



            # Setup Bohr effect tracking if pH perturbation is active (thread-safe, no globals)

            bohr_data = None

            bohr_effect_obj = None

            if ph_perturbation and PH_MODULES_AVAILABLE:

                try:

                    from bohr_effect import BohrEffect

                    bohr_effect_obj = BohrEffect()

                    bohr_data = {key: [] for key in [

                        'time', 'pHi', 'pHe', 'BPG_mM', 'P50_mmHg',

                        'sat_arterial', 'sat_venous', 'O2_extracted_fraction',

                        'O2_arterial_mL_per_dL', 'O2_venous_mL_per_dL'

                    ]}

                    if progress_callback:

                        progress_callback(0.32, "✓ Bohr effect tracking enabled")

                except Exception as e:

                    if progress_callback:

                        progress_callback(0.32, f"⚠️ Bohr tracking unavailable: {e}")

                    bohr_data = None

                    bohr_effect_obj = None



            # Setup flux tracking for all simulations (thread-safe, no globals)

            flux_tracker = None

            try:

                flux_tracker = SimpleFluxTracker()

                if progress_callback:

                    progress_callback(0.33, "✓ Flux tracking enabled")

            except Exception as e:

                if progress_callback:

                    progress_callback(0.33, f"⚠️ Flux tracking unavailable: {e}")

                flux_tracker = None



            if progress_callback:

                progress_callback(0.35, f"Starting integration ({n_metabolites} metabolites)...")



            # Time span — start at t=1 to match experimental data (same as main.py)

            t_span = (1, t_max)

            t_eval = np.linspace(1, t_max, 75)  # 75 time points



            # Create ODE function wrapper with curve fitting strength

            # Verify curve_fitting_data availability

            if curve_fit_strength > 0:

                try:

                    from curve_fitting_data import CURVE_FIT_PARAMS

                    if progress_callback:

                        progress_callback(0.35, f"✓ Curve fitting module loaded ({len(CURVE_FIT_PARAMS)} metabolites)")

                except ImportError as e:

                    if progress_callback:

                        progress_callback(0.35, f"⚠️ Curve fitting unavailable: {e}")



            def ode_func(t, x):

                return equadiff_brodbar(t, x, thermo_constraints=None,

                                       custom_params=custom_params,

                                       curve_fit_strength=curve_fit_strength,

                                       flux_tracker=flux_tracker,

                                       ph_perturbation=ph_perturbation,

                                       bohr_effect=bohr_effect_obj,

                                       bohr_tracker=bohr_data)



            if progress_callback:

                progress_callback(0.4, f"Integrating with {solver_method} solver...")



            # Limit max step size to prevent overshooting concentrations below zero.

            # Tighter steps for low curve fit (pure MM kinetics are stiffer).

            if curve_fit_strength < 0.3:

                max_step = t_max / 500  # ~0.084 days for 42-day sim

            else:

                max_step = t_max / 150  # ~0.28 days



            # Solve ODE system

            sol = solve_ivp(

                ode_func,

                t_span,

                x0,

                method=solver_method,

                t_eval=t_eval,

                rtol=rtol,

                atol=atol,

                max_step=max_step,

                dense_output=True

            )



            if not sol.success:

                raise RuntimeError(f"Integration failed: {sol.message}")



            # Post-processing: clamp any residual negative concentrations to zero

            # (derivative damping in equadiff_brodbar prevents most, this catches stragglers)

            sol.y[:NUM_BASE_METABOLITES] = np.maximum(sol.y[:NUM_BASE_METABOLITES], 0.0)



            if progress_callback:

                progress_callback(0.8, "Processing results...")



            # Get metabolite names in correct index order (not dictionary order!)

            # This is CRITICAL: sol.y columns are ordered by index 0-N, not by dict insertion order

            # Same logic as CLI main.py which builds metabolite_list correctly

            n_with_phi = NUM_BASE_METABOLITES + 1

            metabolite_names = [''] * n_with_phi

            for name, idx in BRODBAR_METABOLITE_MAP.items():

                if idx < n_with_phi:

                    metabolite_names[idx] = name



            # Add PHE to metabolite names if pH perturbation was active

            if ph_perturbation and n_metabolites == NUM_TOTAL_METABOLITES:

                metabolite_names.append('PHE')  # Extracellular pH



            # Calculate duration

            duration = time.time() - start_time



            # No global cleanup needed - all tracking objects are local to this call



            if progress_callback:

                progress_callback(1.0, "Simulation completed!")



            # Prepare results

            self.results = {

                't': sol.t,

                'x': np.asarray(sol.y, dtype=float).T,  # Normalize solve_ivp output to a numeric matrix

                'metabolite_names': metabolite_names,

                'n_points': len(sol.t),

                'n_metabolites': n_metabolites,

                'duration': duration,

                'success': True,

                'solver': solver_method,

                'curve_fit_strength': curve_fit_strength,

                'custom_params_source': params_source,

                'research_data_mode': research_data_mode,

                'active_dataset_id': active_dataset_id,

                'active_dataset_label': active_dataset_label,

                'dataset_applied': dataset_applied,

                'dataset_fallback_reason': dataset_fallback_reason,

                'dataset_applied_metabolites': dataset_applied_metabolites,

                'ph_perturbation': {

                    'type': ph_perturbation_type,

                    'severity': ph_severity if ph_perturbation_type in ["Acidosis", "Alkalosis"] else None,

                    'target': ph_target if ph_perturbation_type in ["Step", "Ramp"] else None,

                    'duration': ph_duration if ph_perturbation_type == "Ramp" else None,

                    'description': ph_perturbation.get_description() if ph_perturbation else "None"

                },

                'bohr_effect': bohr_data if bohr_data and len(bohr_data.get('time', [])) > 0 else None,

                'flux_data': {'times': flux_tracker.times, 'fluxes': flux_tracker.fluxes} if flux_tracker and len(flux_tracker.times) > 0 else None,

                'experimental_data': {

                    'source': 'custom_upload' if dataset_applied else 'bordbar_reference',

                    'time': custom_val_time if dataset_applied and len(custom_val_metabolites) > 0 else reference_time,

                    'metabolites': custom_val_metabolites if dataset_applied and len(custom_val_metabolites) > 0 else reference_metabolites,

                    'values': custom_val_values if dataset_applied and len(custom_val_metabolites) > 0 else reference_values

                },

                'reference_data': {

                    'source': 'bordbar_reference',

                    'time': reference_time,

                    'metabolites': reference_metabolites,

                    'values': reference_values

                },

                'custom_validation_data': {

                    'time': custom_val_time,

                    'metabolites': custom_val_metabolites,

                    'values': custom_val_values

                } if len(custom_val_metabolites) > 0 else None

            }



            self.status = "completed"

            return self.results



        except Exception as e:

            self.status = "error"

            self.error_message = str(e)
            traceback.print_exc()

            if progress_callback:

                progress_callback(1.0, f"Error: {str(e)}")

            return {"error": str(e), "success": False}



    def get_results(self):

        """Get last simulation results"""

        return self.results



    def get_status(self):

        """Get current simulation status"""

        return self.status





@st.cache_data(show_spinner=False)

def run_cached_simulation(t_max, curve_fit_strength, ic_source, solver_method, rtol, atol):

    """

    Run simulation with Streamlit caching

    Cached based on parameters for faster repeat runs

    """

    engine = SimulationEngine()

    results = engine.run_simulation(

        t_max=t_max,

        curve_fit_strength=curve_fit_strength,

        ic_source=ic_source,

        solver_method=solver_method,

        rtol=rtol,

        atol=atol

    )

    return results





def get_metabolite_data(results, metabolite_name):

    """

    Extract time series for a specific metabolite



    Parameters:

    -----------

    results : dict

        Simulation results

    metabolite_name : str

        Name of metabolite



    Returns:

    --------

    tuple : (time_array, concentration_array)

    """

    if not results or 'error' in results:

        return None, None



    try:

        idx = results['metabolite_names'].index(metabolite_name)

        return results['t'], results['x'][:, idx]

    except (ValueError, KeyError):

        return None, None





def export_results_csv(results):

    """

    Export simulation results to CSV format



    Returns:

    --------

    str : CSV formatted string

    """

    import io



    if not results or 'error' in results:

        return ""



    output = io.StringIO()



    # Header

    output.write("Time," + ",".join(results['metabolite_names']) + "\n")



    # Data rows

    for i, t in enumerate(results['t']):

        row = [str(t)] + [str(results['x'][i, j]) for j in range(results['n_metabolites'])]

        output.write(",".join(row) + "\n")



    return output.getvalue()
