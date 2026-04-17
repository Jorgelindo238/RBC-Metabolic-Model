"""
RBC Metabolic Model Simulation - Main Entry Point

Python equivalent of the protocole_RBC_JA2020.m MATLAB script.
This module orchestrates the complete Red Blood Cell metabolic simulation workflow.

Features:
---------
- Multi-model support (brodbar, original, refactored variants)
- Experimental data integration from Excel files
- Pure Michaelis-Menten kinetic modeling
- 114 metabolites (113 base + pHi dynamics)
- Comprehensive visualization and PDF export
- Command-line interface for easy configuration

Requirements:
-------------
- numpy, pandas, matplotlib, scipy
- Excel data files: Data_Bordbar_et_al_exp.xlsx, Initial_conditions_JA_Final.xls
- Reaction network definition: RBC/Rxn_RBC.txt

Author: Jorgelindo da Veiga
Based on: Bordbar et al. (2015) RBC metabolic model
"""
import os
import time
import argparse
from collections import Counter
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Get src directory for data file paths
_THIS_FILE = Path(__file__).resolve()
_SRC_DIR = _THIS_FILE.parent  # This file is in src/
_DATA_FILE = _SRC_DIR / "Data_Bordbar_et_al_exp.xlsx"
_IC_FILE = _SRC_DIR / "Initial_conditions_JA_Final.xls"

# Import custom modules
from parse import parse
from parse_initial_conditions import parse_initial_conditions
from solver import solver
from visualization import plot_metabolite_results, export_to_pdf
from flux_visualization import FluxTracker, generate_all_flux_plots, create_flux_pdf_report

# Import pH perturbation modules
try:
    from ph_perturbation import (PhPerturbation, create_step_perturbation,
                                 create_ramp_perturbation, get_acidosis_scenario,
                                 get_alkalosis_scenario)
    from equadiff_brodbar import enable_pH_modulation, disable_pH_modulation
    PH_MODULES_AVAILABLE = True
except ImportError:
    PH_MODULES_AVAILABLE = False
    print("Warning: pH perturbation modules not available")

# Import the Brodbar model equations
try:
    from equadiff_brodbar import equadiff_brodbar
    BRODBAR_AVAILABLE = True
except ImportError:
    print("Warning: equadiff_brodbar module not found. Brodbar model will not be available.")
    BRODBAR_AVAILABLE = False

REFACTORED_AVAILABLE = False


def _make_unique_metabolite_names(names):
    """Generate stable unique metabolite column names for trajectory export."""
    counts = Counter()
    unique_names = []
    for idx, raw_name in enumerate(names):
        base_name = str(raw_name).strip() if raw_name is not None else ""
        if not base_name:
            base_name = f"METAB_{idx}"
        counts[base_name] += 1
        unique_name = base_name if counts[base_name] == 1 else f"{base_name}_{counts[base_name]}"
        unique_names.append(unique_name)
    return unique_names


def main():
    """
    Main function that runs the RBC (Red Blood Cell) metabolic model simulation.
    
    This function orchestrates the complete simulation workflow:
    1. Parses command-line arguments for model selection and configuration
    2. Loads experimental data from Excel files
    3. Sets up initial conditions from experimental values
    4. Runs ODE integration using scipy's solve_ivp
    5. Generates visualization plots for all metabolites
    6. Exports results to PDF format
    
    Command-line Arguments:
    -----------------------
    --model : str, optional
        Model variant to use: 'brodbar' (default, recommended), 'original' (has issues), 
        or 'refactored' (experimental)
    --author : str, optional
        Author name for PDF output (default: 'Jorgelindo da Veiga')
    
    Model Details:
    --------------
    - Simulates 114 metabolites (113 base metabolites + pHi)
    - Integration time: t=1 to t=42 days (RBC storage conditions)
    - Uses experimental data from Data_Bordbar_et_al_exp.xlsx
    - Implements pure Michaelis-Menten kinetics
    
    Outputs:
    --------
    - PNG plots for each metabolite group saved to Simulations/{model}/ directory
    - Comprehensive PDF report: Results_Metabolic_Model_{model}_Bordbar2015.pdf
    - Console output showing simulation progress and performance metrics
    
    Equivalent to:
    --------------
    protocole_RBC_JA2020.m (original MATLAB implementation)
    
    Raises:
    -------
    SystemExit
        If critical files are missing or integration fails
    
    Examples:
    ---------
    Run with default brodbar model:
        python src/main.py
    
    Run with specific model and author:
        python src/main.py --model brodbar --author "John Doe"
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run RBC metabolic model simulation with optional pH perturbation")
    parser.add_argument('--model', choices=['original', 'brodbar', 'refactored'], default='brodbar',
                        help='Choose which model to use (brodbar recommended, original has dimension issues, refactored experimental)')
    parser.add_argument('--author', type=str, default='Jorgelindo da Veiga',
                        help='Author name to include in PDF output')
    parser.add_argument('--curve-fit', type=float, default=0.0, metavar='STRENGTH',
                        help='Curve fitting strength: 0.0=pure MM kinetics (default), 0.5=50%% blend, 1.0=full curve fitting')
    parser.add_argument('--load-params', type=str, default=None,
                        help='Path to JSON file with calibrated parameters (e.g. Simulations/brodbar/calibration/best_params.json)')
    parser.add_argument('--no-auto-load-params', action='store_true',
                        help='Disable implicit loading of Simulations/brodbar/calibration/best_params.json and use default parameters unless --load-params is set')
    
    # pH perturbation arguments
    parser.add_argument('--ph-perturbation', type=str, choices=['none', 'acidosis', 'alkalosis', 'step', 'ramp'], 
                        default='none', help='Type of pH perturbation to apply')
    parser.add_argument('--ph-severity', type=str, choices=['mild', 'moderate', 'severe'], 
                        default='moderate', help='Severity of acidosis/alkalosis (mild/moderate/severe)')
    parser.add_argument('--ph-target', type=float, default=7.0,
                        help='Target pH for step perturbation (default: 7.0)')
    parser.add_argument('--ph-start', type=float, default=2.0,
                        help='Start time for pH perturbation in hours (default: 2.0)')
    parser.add_argument('--ph-duration', type=float, default=6.0,
                        help='Duration of pH ramp in hours (default: 6.0)')
    
    args = parser.parse_args()
    
    model_type = args.model
    author_name = args.author
    curve_fit_strength = args.curve_fit
    
    # Load calibrated parameters with explicit source control
    # Priority: --load-params > auto-load (unless disabled) > defaults
    import json
    custom_params = None
    params_source = 'defaults'
    _default_cal_path = Path("Simulations/brodbar/calibration/best_params.json")
    def _load_json_params(path):
        """Load JSON params, handling UTF-16 or UTF-8 encoding."""
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                return json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            with open(path, 'r', encoding='utf-16') as f:
                return json.load(f)

    if args.load_params:
        custom_params = _load_json_params(args.load_params)
        params_source = 'file'
        print(f"Loaded {len(custom_params)} calibrated parameters from {args.load_params}")
    elif model_type == 'brodbar' and (not args.no_auto_load_params) and _default_cal_path.exists():
        custom_params = _load_json_params(_default_cal_path)
        params_source = 'auto_loaded'
        print(f"Auto-loaded {len(custom_params)} calibrated parameters from {_default_cal_path}")
        print("  (use --no-auto-load-params for reproducible default baselines)")
    elif model_type == 'brodbar' and args.no_auto_load_params:
        print("Using default Brodbar parameters (--no-auto-load-params set)")
    
    # Validate curve fitting strength
    if curve_fit_strength < 0.0 or curve_fit_strength > 2.0:
        print(f"Warning: curve-fit strength {curve_fit_strength} is outside recommended range [0.0, 1.0]")
        if curve_fit_strength < 0:
            curve_fit_strength = 0.0
        elif curve_fit_strength > 2.0:
            curve_fit_strength = 2.0
        print(f"  Adjusted to: {curve_fit_strength}")
    
    # Check if requested models are available
    if model_type == 'brodbar' and not BRODBAR_AVAILABLE:
        print("Error: Brodbar model requested but not available. Falling back to original model.")
        model_type = 'original'
    elif model_type == 'refactored' and not REFACTORED_AVAILABLE:
        print("Error: Refactored model requested but not available. Falling back to original model.")
        model_type = 'original'
    
    # Configure pH perturbation if requested
    ph_perturbation = None
    if args.ph_perturbation != 'none' and PH_MODULES_AVAILABLE and model_type == 'brodbar':
        print(f"\n{'='*70}")
        print("pH PERTURBATION CONFIGURATION")
        print(f"{'='*70}")

        # Internal simulation time is in days; CLI pH timing inputs remain in hours.
        ph_start_days = args.ph_start / 24.0
        ph_duration_days = args.ph_duration / 24.0
        
        if args.ph_perturbation == 'acidosis':
            target_map = {'mild': 7.2, 'moderate': 7.0, 'severe': 6.8}
            duration_map_h = {'mild': 4.0, 'moderate': 6.0, 'severe': 8.0}
            target_pH = target_map.get(args.ph_severity, 7.0)
            duration_h = duration_map_h.get(args.ph_severity, 6.0)
            ph_perturbation = create_ramp_perturbation(
                pH_initial=7.4,
                pH_final=target_pH,
                t_start=ph_start_days,
                duration=duration_h / 24.0,
            )
            print(f"[OK] Acidosis scenario ({args.ph_severity}) over {duration_h:.1f}h")
        elif args.ph_perturbation == 'alkalosis':
            target_map = {'mild': 7.6, 'moderate': 7.7, 'severe': 7.8}
            duration_map_h = {'mild': 4.0, 'moderate': 6.0, 'severe': 8.0}
            target_pH = target_map.get(args.ph_severity, 7.7)
            duration_h = duration_map_h.get(args.ph_severity, 6.0)
            ph_perturbation = create_ramp_perturbation(
                pH_initial=7.4,
                pH_final=target_pH,
                t_start=ph_start_days,
                duration=duration_h / 24.0,
            )
            print(f"[OK] Alkalosis scenario ({args.ph_severity}) over {duration_h:.1f}h")
        elif args.ph_perturbation == 'step':
            ph_perturbation = create_step_perturbation(
                pH_target=args.ph_target,
                t_start=ph_start_days
            )
            print(f"[OK] Step perturbation: pH 7.4 -> {args.ph_target} at t={args.ph_start}h")
        elif args.ph_perturbation == 'ramp':
            ph_perturbation = create_ramp_perturbation(
                pH_initial=7.4,
                pH_final=args.ph_target,
                t_start=ph_start_days,
                duration=ph_duration_days
            )
            print(f"[OK] Ramp perturbation: pH 7.4 -> {args.ph_target} over {args.ph_duration}h")
        
        if ph_perturbation:
            print(f"   {ph_perturbation.get_description()}")
            print(f"{'='*70}\n")
    elif args.ph_perturbation != 'none' and model_type != 'brodbar':
        print(f"\nWarning: pH perturbation only available with brodbar model. Ignoring --ph-perturbation.\n")
    
    print(f"Starting RBC metabolic model simulation using {model_type} model...")
    if curve_fit_strength > 0:
        print(f"  Curve fitting: {curve_fit_strength*100:.0f}% strength")
        print(f"    0% = Pure Michaelis-Menten kinetics")
        print(f"    {curve_fit_strength*100:.0f}% = Blending MM with experimental curves")
    else:
        print(f"  Curve fitting: OFF (pure Michaelis-Menten kinetics)")
    
    if ph_perturbation:
        print(f"  pH perturbation: {args.ph_perturbation} ({args.ph_severity if args.ph_perturbation in ['acidosis', 'alkalosis'] else 'custom'})")
    print(f"  Parameter source: {params_source}")
    
    start_time = time.time()
    
    # Create Simulations directory for results if it doesn't exist
    Path("Simulations").mkdir(parents=True, exist_ok=True)
    
    # Process the experimental data with curve fitting
    print("Processing experimental data...")
    # Load experimental data only from Data_Bordbar_et_al_exp.xlsx
    try:
        import pandas as pd
        df = pd.read_excel(_DATA_FILE)
        
        # Extract metabolite names and data
        meta_names2 = df.iloc[:, 0].tolist()  # First column contains metabolite names
        metabolites2 = df.iloc[:, 1:].values  # Keep original shape: metabolites as rows, time points as columns
        
        # Create time points array from column headers
        tempsexp2 = np.array([float(col) for col in df.columns[1:]])
        
        print(f"Loaded experimental data: {len(meta_names2)} metabolites, {len(tempsexp2)} time points")
        
        # No first dataset - only use Data_Bordbar_et_al_exp.xlsx
        meta_names1, metabolites1, tempsexp1 = [], None, None
        
    except Exception as e:
        print(f"Error: Could not load experimental data from Data_Bordbar_et_al_exp.xlsx: {e}")
        meta_names1, metabolites1, tempsexp1 = [], None, None
        meta_names2, metabolites2, tempsexp2 = [], None, None
    
    # Note: Initial conditions are now handled directly in parse_initial_conditions.py
    # which loads experimental data from Data_Bordbar_et_al_exp.xlsx
    
    # Parse the reaction network (only for original model)
    # Brodbar model uses equations directly from equadiff_brodbar.py
    model = None
    if model_type != 'brodbar':
        print("Parsing reaction network...")
        reaction_file_paths = [
            os.path.join("RBC", "Rxn_RBC.txt"),
            os.path.join("..", "RBC", "Rxn_RBC.txt"),
            "Rxn_RBC.txt",
            os.path.join("src", "Rxn_RBC.txt")
        ]
        
        for path in reaction_file_paths:
            if os.path.exists(path):
                print(f"Found reaction file at: {path}")
                model = parse(path)
                break
        
        if model is None:
            print("Error: Could not find reaction network file. Searched paths:")
            for path in reaction_file_paths:
                print(f"  - {path} (exists: {os.path.exists(path)})")
            return
    else:
        # Brodbar model: create metabolite list from BRODBAR_METABOLITE_MAP
        from equadiff_brodbar import (BRODBAR_METABOLITE_MAP, NUM_BASE_METABOLITES, 
                                         NUM_TOTAL_METABOLITES, PHI_INDEX, PHE_INDEX, H2O2_INDEX)
        
        # Invert the map to get metabolite names ordered by index
        # Create list for NUM_BASE_METABOLITES + 1 metabolites (base + pHi)
        # pHe will be added dynamically if present in x after integration
        n_with_phi = NUM_BASE_METABOLITES + 1  # base metabolites + pHi
        metabolite_list = [''] * n_with_phi
        for name, idx in BRODBAR_METABOLITE_MAP.items():
            if idx < n_with_phi:
                metabolite_list[idx] = name
        
        model = {'metab': metabolite_list}
        print(f"Created Brodbar metabolite list: {len(model['metab'])} metabolites")
    
    # Parse initial conditions
    print("Setting up initial conditions...")
    # Use absolute path for initial conditions file
    x0 = None
    if _IC_FILE.exists():
        print(f"Found initial conditions file at: {_IC_FILE}")
        try:
            x0, _ = parse_initial_conditions(model, str(_IC_FILE))
        except Exception as e:
            print(f"Error parsing {_IC_FILE}: {e}")
    
    if x0 is None:
        print("Warning: Could not parse initial conditions from file. Using defaults...")
        # Create default initial conditions for the model
        if model_type == 'brodbar':
            from equadiff_brodbar import (NUM_BASE_METABOLITES, PHI_INDEX, H2O2_INDEX)
            n_with_phi = NUM_BASE_METABOLITES + 1
            x0 = np.ones(n_with_phi)  # Default to 1 for all metabolites (base + pHi)
            x0[H2O2_INDEX] = 0.0001  # H2O2
            x0[PHI_INDEX] = 7.2    # pHi
        elif model_type == 'refactored':
            # Will use default_ic() later
            pass
        else:
            print("Error: No initial conditions available for original model")
            return
    # Note: parse_initial_conditions already prints status messages
   
    # Show some key metabolite initial conditions
    print("Key metabolite initial conditions:")
    print(f"  Total metabolites: {len(x0)}")
    if model_type == 'brodbar':
        from equadiff_brodbar import BRODBAR_METABOLITE_MAP

        for metabolite_name in ["EGLC", "ELAC", "GLC", "ATP", "LAC"]:
            idx = BRODBAR_METABOLITE_MAP.get(metabolite_name)
            if idx is not None and idx < len(x0):
                print(f"  {metabolite_name} (x[{idx}]): {x0[idx]:.3f} mM")
    else:
        if len(x0) > 62:
            print(f"  EGLC (x[62]): {x0[62]:.3f} mM")
        if len(x0) > 68:
            print(f"  ELAC (x[68]): {x0[68]:.3f} mM")
        if len(x0) > 24:
            print(f"  GLC (x[24]): {x0[24]:.3f} mM")
        if len(x0) > 3:
            print(f"  ATP (x[3]): {x0[3]:.3f} mM")
        if len(x0) > 36:
            print(f"  LAC (x[36]): {x0[36]:.3f} mM")
    
    # For Brodbar model, ensure we have exactly NUM_BASE_METABOLITES+1 metabolites (base + pHi)
    if model_type == 'brodbar':
        from equadiff_brodbar import (NUM_BASE_METABOLITES, PHI_INDEX, PHE_INDEX, H2O2_INDEX)
        n_with_phi = NUM_BASE_METABOLITES + 1
        if len(x0) < n_with_phi:
            print(f"Extending initial conditions from {len(x0)} to {n_with_phi} metabolites...")
            x0_extended = np.ones(n_with_phi)
            x0_extended[:len(x0)] = x0
            x0_extended[H2O2_INDEX] = 0.0001  # H2O2 (if not already set)
            x0_extended[PHI_INDEX] = 7.2    # pHi
            x0 = x0_extended
    elif model_type != 'refactored':
        # For original model, add extra metabolites
        if len(x0) < 108:
            print("Adding H2O2 and pHi metabolites to initial conditions...")
            x0 = np.append(x0, [0.0001, 7.2])  # H2O2, pHi

    # Set time range for simulation
    # For Brodbar data, the first experimental point is at t=1 (not t=0).
    # Start integration at t=1 to ensure the initial simulation point aligns with the first experimental value.
    # Time unit is days.
    time_range = [1, 42]

    # Run the numerical integration
    print(f"Solving system of {len(model['metab'])} differential equations...")
    try:
        if model_type == 'brodbar':
            from scipy.integrate import solve_ivp
            from equadiff_brodbar import (
                equadiff_brodbar,
                _load_experimental_first_values,
                enable_flux_tracking,
                disable_flux_tracking,
                enable_bohr_tracking,
                disable_bohr_tracking,
                enable_pH_modulation,
                disable_pH_modulation,
            )

            # Load experimental data once before integration (performance optimization)
            print("Loading experimental data for conservation pools...")
            _load_experimental_first_values()

            # Ensure x0 has correct number of metabolites
            num_metabolites = NUM_TOTAL_METABOLITES if ph_perturbation else NUM_BASE_METABOLITES + 1
            target_size = num_metabolites
            if len(x0) != target_size:
                print(f"Adjusting initial conditions from {len(x0)} to {target_size} metabolites")
                if len(x0) < target_size:
                    x0_extended = np.ones(target_size)
                    x0_extended[:len(x0)] = x0
                    x0_extended[H2O2_INDEX] = max(x0_extended[H2O2_INDEX], 0.0001)  # Ensure H2O2 is set
                    x0_extended[PHI_INDEX] = 7.2  # pHi initial
                    if target_size == NUM_TOTAL_METABOLITES:
                        x0_extended[PHE_INDEX] = 7.4  # pHe initial (will be overridden by perturbation)
                    x0 = x0_extended
                else:
                    x0 = x0[:target_size]

            # Clean initial conditions to prevent NaN/Inf
            x0 = np.nan_to_num(x0, nan=1e-6, posinf=1e6, neginf=1e-6)
            x0 = np.maximum(x0, 1e-6)  # Ensure all values are positive

            # Use initial conditions directly from parse_initial_conditions.py
            # No remapping needed - the parse_initial_conditions already handles proper mapping
            print("Using initial conditions directly from parse_initial_conditions.py (no remapping)")

            print(f"Starting integration with {len(x0)} initial conditions")
            print(f"Initial condition range: {x0.min():.6e} - {x0.max():.6e}")

            # Enable pH modulation if perturbation is configured
            if ph_perturbation:
                print("Enabling pH-dependent enzyme modulation...")
                enable_pH_modulation(ph_perturbation)

            # Enable flux tracking
            print("Enabling flux tracking for all reactions...")
            flux_tracker = FluxTracker()
            enable_flux_tracking(flux_tracker)

            # Enable Bohr effect tracking if pH modulation is active
            bohr_tracker = None
            if ph_perturbation:
                print("Enabling Bohr effect tracking (P50, O2 saturation, delivery)...")
                bohr_tracker = {}  # Will be populated by equadiff_brodbar
                if enable_bohr_tracking(bohr_tracker):
                    print("[OK] Bohr effect tracking enabled")
                else:
                    print("⚠ Bohr effect tracking unavailable")
                    bohr_tracker = None

            # Use default RK45 solver with standard settings
            # Tighter max_step for low curve fit to prevent negative concentrations
            t_max_sim = time_range[1] - time_range[0]
            max_step = t_max_sim / 500 if curve_fit_strength < 0.3 else t_max_sim / 150
            print(f"Integrating with RK45 solver (max_step={max_step:.4f})...")

            solution = solve_ivp(
                lambda t, y: equadiff_brodbar(
                    t,
                    y,
                    thermo_constraints=None,
                    custom_params=custom_params,
                    curve_fit_strength=curve_fit_strength,
                ),
                t_span=time_range,
                y0=x0,
                method='RK45',
                t_eval=np.linspace(time_range[0], time_range[1], 75),
                max_step=max_step,
            )

            # Post-processing: clamp residual negative concentrations
            if solution.success:
                solution.y[:NUM_BASE_METABOLITES] = np.maximum(solution.y[:NUM_BASE_METABOLITES], 0.0)

            # Disable flux tracking, Bohr tracking, and pH modulation
            disable_flux_tracking()
            if bohr_tracker is not None:
                disable_bohr_tracking()
            if ph_perturbation:
                disable_pH_modulation()

            if solution.success:
                t = solution.t
                x = solution.y.T
                print(f"Integration completed with {len(t)} time points")
                print(f"Tracked {len(flux_tracker.times)} flux timepoints with {len(flux_tracker.reaction_names)} reactions")
                if ph_perturbation:
                    print(f"pH perturbation applied: {args.ph_perturbation}")
            else:
                print(f"Integration failed: {solution.message}")
                return

        elif model_type == 'refactored':
            print("Using refactored model equations")
            core_params = CoreParams()
            rbc_model = RBCEq(core_params)
            
            # Use refactored initial conditions
            x0_refactored = default_ic()
            
            # Create time evaluation points
            t_eval = np.linspace(time_range[0], time_range[1], 50)
            
            solution = rbc_model.integrate(
                t_span=time_range,
                x0=x0_refactored,
                t_eval=t_eval
            )
            
            if solution.success:
                t = solution.t
                x = solution.y.T
                print(f"Refactored model integration completed with {len(t)} time points")
            else:
                raise Exception("Refactored model integration failed")
        else:
            print("Using original model equations")
            t, x = solver(x0, time_range, model)
    except Exception as e:
        print(f"Error during numerical integration: {e}")
        return
    
    # Create output directories with subdirectories for metabolites and fluxes
    output_dir = f"Simulations/{model_type}"
    metabolites_dir = f"{output_dir}/metabolites"
    fluxes_dir = f"{output_dir}/fluxes"
    Path(metabolites_dir).mkdir(parents=True, exist_ok=True)
    Path(fluxes_dir).mkdir(parents=True, exist_ok=True)
    
    # Save metabolite concentrations including pH values
    if model_type == 'brodbar' and x.shape[1] > PHI_INDEX:
        import pandas as pd
        metabolite_data = {'Time (days)': t}
        
        # Add pHi and pHe if available
        metabolite_data['pHi'] = x[:, PHI_INDEX]
        if x.shape[1] > PHE_INDEX:
            metabolite_data['pHe'] = x[:, PHE_INDEX]
        else:
            metabolite_data['pHe'] = 7.4  # Constant if not tracked
        
        df_metabolites = pd.DataFrame(metabolite_data)
        metabolite_csv_path = f"{metabolites_dir}/pH_metabolites.csv"
        df_metabolites.to_csv(metabolite_csv_path, index=False)
        print(f"[OK] pH metabolite data saved to: {metabolite_csv_path}")

    # Plot the metabolite results
    print(f"Generating metabolite plots in {metabolites_dir}...")
    try:
        # Adjust model['metab'] to match actual x dimensions
        if model_type == 'brodbar':
            actual_metabolites = x.shape[1]
            if len(model['metab']) != actual_metabolites:
                print(f"Adjusting model['metab'] from {len(model['metab'])} to {actual_metabolites} metabolites")
                if actual_metabolites == len(model['metab']) + 1:
                    # Add pHe if it's in x but not in model['metab']
                    model['metab'].append('PHE')
                elif actual_metabolites == len(model['metab']) - 1:
                    # Remove pHe if it's in model['metab'] but not in x
                    model['metab'] = model['metab'][:actual_metabolites]
        
        # NOTE: Reordering disabled to prevent duplicate metabolite plotting
        # The x array is already in the correct order (model['metab'] order)
        # from equadiff_brodbar.py and parse_initial_conditions.py
        print(f"[OK] Using x directly (shape: {x.shape}) with {len(model['metab'])} metabolite names")

        if model_type == 'brodbar':
            import pandas as pd

            metabolite_columns = _make_unique_metabolite_names(model['metab'])
            df_full_metabolites = pd.DataFrame(x, columns=metabolite_columns)
            df_full_metabolites.insert(0, 'Time (days)', t)
            full_metabolite_csv_path = f"{metabolites_dir}/all_metabolites.csv"
            df_full_metabolites.to_csv(full_metabolite_csv_path, index=False)
            print(f"[OK] Full ODE metabolite trajectories saved to: {full_metabolite_csv_path}")

        plot_metabolite_results(t, x, model, meta_names1, meta_names2,
                               metabolites1, metabolites2,
                               tempsexp1, tempsexp2,
                               save_path=metabolites_dir)
        print("[OK] Metabolite plots generated successfully")
    except Exception as e:
        print(f"Warning: Metabolite plot generation failed: {e}")
        print("Continuing without metabolite plots...")
    
    # Generate flux visualizations if flux tracking is available
    if model_type == 'brodbar' and 'flux_tracker' in locals() and flux_tracker is not None:
        print(f"\nGenerating flux visualizations in {fluxes_dir}...")
        try:
            generate_all_flux_plots(flux_tracker, output_dir)
            print("[OK] Flux plots generated successfully")
            
            # Create flux PDF report
            try:
                create_flux_pdf_report(flux_tracker, output_dir)
            except Exception as e:
                print(f"Warning: Flux PDF report generation failed: {e}")
        except Exception as e:
            print(f"Warning: Flux visualization failed: {e}")
            print("Continuing without flux plots...")
    
    # Save and visualize Bohr effect data if available
    if model_type == 'brodbar' and 'bohr_tracker' in locals() and bohr_tracker is not None and len(bohr_tracker.get('time', [])) > 0:
        print(f"\nSaving Bohr effect data...")
        try:
            import pandas as pd
            bohr_dir = f"{output_dir}/bohr_effect"
            Path(bohr_dir).mkdir(parents=True, exist_ok=True)
            
            # Convert Bohr tracker to DataFrame
            df_bohr = pd.DataFrame(bohr_tracker)
            bohr_csv_path = f"{bohr_dir}/bohr_metrics.csv"
            df_bohr.to_csv(bohr_csv_path, index=False)
            print(f"[OK] Bohr effect metrics saved to: {bohr_csv_path}")
            print(f"  Tracked: P50, O2 saturation (arterial/venous), O2 delivery")
            print(f"  Time points: {len(df_bohr)}")
            
            print(f"  (Bohr visualization available in Streamlit app)")
        except Exception as e:
            print(f"Warning: Bohr effect data processing failed: {e}")
    
    # Export metabolites to PDF with author information and model type
    output_filename = f"Metabolites_Results_{model_type}_Bordbar2015.pdf"
    data_source = f"RBC Model ({model_type.capitalize()}) - {author_name}"
    
    # Export metabolites to PDF with author information and model type
    try:
        export_to_pdf(save_path=metabolites_dir, 
                     output_filename=output_filename, 
                     data_source=data_source)
        print(f"[OK] Metabolites PDF exported: {os.path.join(metabolites_dir, output_filename)}")
    except Exception as e:
        print(f"Warning: Metabolites PDF export failed: {e}")
    
    # Calculate and display execution time
    end_time = time.time()
    duration = end_time - start_time
    print(f"\n{'='*50}")
    print("[OK] Simulation completed successfully!")
    print(f"  Model: {model_type}")
    print(f"  Time points: {len(t)}")
    print(f"  Duration: {int(duration // 60)} minutes and {duration % 60:.1f} seconds")
    print(f"  Output directory: Simulations/{model_type}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
