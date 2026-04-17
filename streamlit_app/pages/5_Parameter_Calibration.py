"""
Parameter Calibration Page
Interactive calibration of model parameters against experimental data

Author: Jorgelindo da Veiga
Date: 2025-11-22
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
from pathlib import Path

# Add streamlit_app to path for core.* imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.parameter_calibration import ParameterCalibrator, CalibrationResult
from core.simulation_engine import SimulationEngine
from core.auth import init_session_state, check_page_auth
from core.styles import apply_global_styles, render_page_header

st.set_page_config(
    page_title="Parameter Calibration - RBC Model",
    page_icon="🎯",
    layout="wide"
)

# Apply global styles
apply_global_styles()

# Initialize and check authentication
init_session_state()
if not check_page_auth():
    st.stop()

# Page header
render_page_header(
    "Parameter Calibration",
    "Use this interactive workspace for exploratory calibration runs against reference or uploaded data before promoting changes into broader benchmark campaigns.",
    "🎯"
)

# Tabs
tab1, tab2, tab3 = st.tabs(["📊 Calibration Setup", "🔬 Results & Analysis", "📚 Help"])

with tab1:
    st.header("Calibration Configuration")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("1️⃣ Experimental Data")
        
        # Load experimental data
        data_source = st.selectbox(
            "Data Source",
            ["Bordbar et al. (2015)", "Upload Custom Data"]
        )
        
        if data_source == "Bordbar et al. (2015)":
            st.success("✅ Using built-in experimental data")
            # Load default data
            try:
                # Load and transpose Bordbar data
                _src = Path(__file__).resolve().parent.parent.parent / "src"
                df_raw = pd.read_excel(_src / "Data_Bordbar_et_al_exp.xlsx")
                
                # First column contains metabolite names, rest are time points
                metabolite_names = df_raw['Conc / mM'].values
                time_points = [col for col in df_raw.columns if col != 'Conc / mM']
                
                # Transpose: rows = time points, columns = metabolites
                exp_data = df_raw.set_index('Conc / mM').T
                exp_data.index.name = 'time'
                exp_data = exp_data.reset_index()
                exp_data['time'] = exp_data['time'].astype(float)
                
                st.dataframe(exp_data.head(), use_container_width=True)
                st.caption(f"📊 {len(exp_data)} time points, {len(metabolite_names)} metabolites")
            except Exception as e:
                st.error(f"Could not load experimental data: {str(e)}")
                exp_data = None
        else:
            uploaded_file = st.file_uploader("Upload CSV/Excel file", type=['csv', 'xlsx'])
            if uploaded_file:
                try:
                    if uploaded_file.name.endswith('.csv'):
                        exp_data = pd.read_csv(uploaded_file)
                    else:
                        exp_data = pd.read_excel(uploaded_file)
                    st.success(f"✅ Loaded {len(exp_data)} data points")
                    st.dataframe(exp_data.head(), use_container_width=True)
                except Exception as e:
                    st.error(f"Error loading file: {str(e)}")
                    exp_data = None
            else:
                exp_data = None
        
        st.markdown("---")
        
        st.subheader("2️⃣ Target Metabolites")
        
        if exp_data is not None:
            available_metabolites = [col for col in exp_data.columns if col != 'time']
            
            target_metabolites = st.multiselect(
                "Select metabolites to calibrate against",
                options=available_metabolites,
                default=available_metabolites[:3] if len(available_metabolites) >= 3 else available_metabolites,
                help="Choose which metabolites to use for calibration"
            )
        else:
            target_metabolites = []
            st.info("Load experimental data first")
    
    with col2:
        st.subheader("3️⃣ Parameters to Optimize")
        
        st.markdown("Select enzyme parameters to calibrate:")
        
        # Common enzyme parameters with reasonable bounds
        # Names must match equadiff_brodbar.py _get_param keys exactly
        # Values: (default, lower_bound, upper_bound) from equadiff_brodbar.py
        parameter_presets = {
            "Glycolysis": {
                "vmax_VHK": (0.267472, 0.027, 2.675),
                "vmax_VPGI": (0.204493, 0.020, 2.045),
                "vmax_VPFK": (0.391893, 0.039, 3.919),
                "vmax_VPK": (0.936322, 0.094, 9.363),
                "vmax_VLDH": (0.284952, 0.028, 2.850)
            },
            "Pentose Phosphate": {
                "vmax_VG6PDH": (0.408870, 0.041, 4.089),
                "vmax_VPGLS": (4.111138, 0.411, 41.111),
                "vmax_V6PGD": (10.0, 1.0, 100.0)
            },
            "Rapoport-Luebering": {
                "vmax_VDPGM": (10.0, 1.0, 100.0),
                "vmax_V23DPGP": (12.0, 1.2, 120.0)
            }
        }
        
        selected_preset = st.selectbox(
            "Parameter Preset",
            options=list(parameter_presets.keys()) + ["Custom"]
        )
        
        if selected_preset != "Custom":
            params_to_optimize = parameter_presets[selected_preset]
            
            # Display parameters with editable bounds
            st.markdown(f"**{selected_preset} Parameters:**")
            
            updated_params = {}
            for param_name, (init, lower, upper) in params_to_optimize.items():
                with st.expander(f"🔧 {param_name}"):
                    col_init, col_lower, col_upper = st.columns(3)
                    
                    with col_init:
                        new_init = st.number_input(
                            "Initial", 
                            value=init,
                            format="%.3f",
                            key=f"init_{param_name}"
                        )
                    with col_lower:
                        new_lower = st.number_input(
                            "Lower", 
                            value=lower,
                            format="%.3f",
                            key=f"lower_{param_name}"
                        )
                    with col_upper:
                        new_upper = st.number_input(
                            "Upper", 
                            value=upper,
                            format="%.3f",
                            key=f"upper_{param_name}"
                        )
                    
                    updated_params[param_name] = (new_init, new_lower, new_upper)
            
            params_to_optimize = updated_params
        else:
            st.info("Custom parameter selection coming soon!")
            params_to_optimize = {}
        
        st.markdown("---")
        
        st.subheader("4️⃣ Optimization Settings")
        
        optimization_method = st.selectbox(
            "Optimization Algorithm",
            ["differential_evolution", "minimize", "least_squares"],
            help="Differential evolution is global and robust but slower"
        )
        
        max_iterations = st.number_input(
            "Maximum Iterations",
            min_value=10,
            max_value=10000,
            value=1000,
            step=100
        )
        
        confidence_level = st.slider(
            "Confidence Level",
            min_value=0.80,
            max_value=0.99,
            value=0.95,
            step=0.01,
            format="%.2f"
        )

        fast_mode = st.checkbox(
            "⚡ Fast mode (skip CI + sensitivity)",
            value=True,
            help="Recommended for iterative runs. Disables expensive confidence-interval and sensitivity calculations."
        )

        max_sim_warnings = st.number_input(
            "Max simulation warning messages",
            min_value=0,
            max_value=50,
            value=3,
            step=1,
            help="Limits warning spam when some trial simulations fail during optimization."
        )
    
    st.markdown("---")
    
    # Calibration button
    col_button1, col_button2, col_button3 = st.columns([1, 1, 1])
    
    with col_button2:
        calibrate_button = st.button(
            "🚀 Run Calibration",
            type="primary",
            use_container_width=True,
            disabled=(exp_data is None or len(target_metabolites) == 0 or len(params_to_optimize) == 0)
        )
    
    if calibrate_button:
        with st.spinner("🔄 Calibrating parameters... This may take a few minutes."):
            try:
                # Canonical calibration time unit is days (same as SimulationEngine and Bordbar columns)
                exp_data_cal = exp_data.copy()
                exp_data_cal['time'] = pd.to_numeric(exp_data_cal['time'], errors='coerce')
                exp_data_cal = exp_data_cal.dropna(subset=['time']).sort_values('time').reset_index(drop=True)
                time_points_days = exp_data_cal['time'].values.astype(float)
                if len(time_points_days) == 0:
                    raise ValueError("No valid numeric time points found in experimental data")
                st.info(
                    f"📅 Calibration time unit: days (min={time_points_days.min():.1f}, max={time_points_days.max():.1f})"
                )
                
                # Setup simulation function
                engine = SimulationEngine()
                sim_warning_state = {'count': 0}
                
                def simulation_function(params):
                    """Wrapper for simulation with custom parameters.
                    
                    Args:
                        params: Dict of parameter overrides, e.g. {'vmax_VHK': 0.3, ...}
                               Keys must match equadiff_brodbar _get_param names.
                    """
                    try:
                        # SimulationEngine and calibration both use days
                        t_max_days = float(np.max(time_points_days))
                        
                        # Run simulation with custom parameters injected into ODE
                        result_dict = engine.run_simulation(
                            t_max=t_max_days,
                            ic_source="Bordbar",
                            solver_method="RK45",
                            custom_params=params,
                            autoload_calibrated_params=False
                        )
                        
                        # Check for errors
                        if 'error' in result_dict:
                            raise Exception(result_dict['error'])
                        
                        # Convert dict to DataFrame
                        time_days = result_dict['t']
                        
                        # Build DataFrame with time + metabolites
                        data = {'time': time_days}
                        metabolite_names = result_dict['metabolite_names']
                        
                        for i, metab_name in enumerate(metabolite_names):
                            data[metab_name] = result_dict['x'][:, i]
                        
                        result_df = pd.DataFrame(data)
                        
                        return result_df
                        
                    except Exception as e:
                        warning_count = sim_warning_state['count']
                        if warning_count < int(max_sim_warnings):
                            st.warning(f"⚠️ Simulation failed: {str(e)}")
                        elif warning_count == int(max_sim_warnings):
                            st.warning("⚠️ Additional simulation failure warnings suppressed.")
                        sim_warning_state['count'] = warning_count + 1

                        # Return dummy data to allow continuation
                        dummy_df = pd.DataFrame({
                            'time': time_points_days,
                            **{met: np.ones(len(time_points_days)) for met in target_metabolites}
                        })
                        return dummy_df
                
                # Create calibrator
                calibrator = ParameterCalibrator(
                    simulation_function=simulation_function,
                    experimental_data=exp_data_cal,
                    target_metabolites=target_metabolites,
                    time_points=time_points_days,
                    time_unit='days'
                )
                
                # Base parameters: start with empty dict (defaults are in equadiff_brodbar)
                base_params = {}
                
                # Run calibration
                result = calibrator.calibrate(
                    params_to_optimize=params_to_optimize,
                    base_params=base_params,
                    method=optimization_method,
                    max_iterations=max_iterations,
                    confidence_level=confidence_level,
                    compute_confidence_intervals=not fast_mode,
                    compute_sensitivity=not fast_mode
                )
                
                # Store result in session state
                st.session_state.calibration_result = result
                
                st.success(f"✅ Calibration completed! R² = {result.r_squared:.4f}")
                
            except Exception as e:
                st.error(f"❌ Calibration failed: {str(e)}")
                st.exception(e)

with tab2:
    st.header("Calibration Results")
    
    if 'calibration_result' not in st.session_state:
        st.info("👈 Run calibration first in the 'Calibration Setup' tab")
    else:
        result: CalibrationResult = st.session_state.calibration_result
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)

        if "skipped" in result.message.lower():
            st.info(f"⚡ Fast mode summary: {result.message}")
        
        with col1:
            st.metric("R² Score", f"{result.r_squared:.4f}")
        with col2:
            st.metric("Objective Value", f"{result.objective_value:.2e}")
        with col3:
            st.metric("Iterations", result.iterations)
        with col4:
            status_icon = "✅" if result.success else "❌"
            st.metric("Status", f"{status_icon} {result.success}")
        
        st.markdown("---")
        
        # Parameter comparison table
        st.subheader("📊 Parameter Values")
        
        param_comparison = []
        for param_name in result.optimized_params.keys():
            initial = result.initial_params[param_name]
            optimized = result.optimized_params[param_name]
            ci_lower, ci_upper = result.confidence_intervals[param_name]
            sensitivity = result.sensitivity[param_name]
            change_pct = ((optimized - initial) / initial) * 100
            
            param_comparison.append({
                "Parameter": param_name,
                "Initial": f"{initial:.4f}",
                "Optimized": f"{optimized:.4f}",
                "Change (%)": f"{change_pct:+.1f}%",
                "CI Lower": f"{ci_lower:.4f}",
                "CI Upper": f"{ci_upper:.4f}",
                "Sensitivity": f"{sensitivity:.3f}"
            })
        
        df_params = pd.DataFrame(param_comparison)
        st.dataframe(df_params, use_container_width=True)
        
        # Visualizations
        st.markdown("---")
        st.subheader("📈 Visualizations")
        
        # Parameter changes bar chart
        fig_params = go.Figure()
        
        for param_name in result.optimized_params.keys():
            initial = result.initial_params[param_name]
            optimized = result.optimized_params[param_name]
            ci_lower, ci_upper = result.confidence_intervals[param_name]
            
            fig_params.add_trace(go.Bar(
                name=param_name,
                x=['Initial', 'Optimized'],
                y=[initial, optimized],
                error_y=dict(
                    type='data',
                    array=[0, ci_upper - optimized],
                    arrayminus=[0, optimized - ci_lower]
                )
            ))
        
        fig_params.update_layout(
            title="Parameter Values: Initial vs Optimized",
            xaxis_title="",
            yaxis_title="Parameter Value",
            barmode='group',
            height=400
        )
        
        st.plotly_chart(fig_params, use_container_width=True)
        
        # Sensitivity analysis
        fig_sensitivity = go.Figure(go.Bar(
            x=list(result.sensitivity.values()),
            y=list(result.sensitivity.keys()),
            orientation='h',
            marker=dict(color='lightblue')
        ))
        
        fig_sensitivity.update_layout(
            title="Parameter Sensitivity",
            xaxis_title="Normalized Sensitivity",
            yaxis_title="Parameter",
            height=300
        )
        
        st.plotly_chart(fig_sensitivity, use_container_width=True)
        
        # Export results
        st.markdown("---")
        st.subheader("💾 Export Results")
        
        col_exp1, col_exp2 = st.columns(2)
        
        with col_exp1:
            # Export as CSV
            csv_data = df_params.to_csv(index=False)
            st.download_button(
                label="📥 Download Parameters CSV",
                data=csv_data,
                file_name="calibrated_parameters.csv",
                mime="text/csv"
            )
        
        with col_exp2:
            # Export as JSON
            import json
            json_data = json.dumps({
                "optimized_params": result.optimized_params,
                "confidence_intervals": {k: list(v) for k, v in result.confidence_intervals.items()},
                "sensitivity": result.sensitivity,
                "r_squared": result.r_squared,
                "objective_value": result.objective_value
            }, indent=2)
            
            st.download_button(
                label="📥 Download Full Results JSON",
                data=json_data,
                file_name="calibration_results.json",
                mime="application/json"
            )

with tab3:
    st.header("📚 Help & Documentation")
    
    st.markdown("""
    ### What is Parameter Calibration?
    
    Parameter calibration automatically adjusts enzyme kinetic parameters to best match experimental data.
    This improves model accuracy and predictive power.
    
    ### Optimization Methods
    
    **Differential Evolution (Recommended)**
    - Global optimization algorithm
    - Robust and reliable
    - Slower but finds better optima
    - Use for: Initial calibration, complex problems
    
    **Local Minimization (L-BFGS-B)**
    - Fast local optimization
    - Requires good initial guess
    - Use for: Fine-tuning, quick iterations
    
    **Least Squares**
    - Specialized for sum-of-squares problems
    - Fast and efficient
    - Use for: Linear-like problems
    
    ### Interpreting Results
    
    **R² Score**: Goodness of fit (0-1, higher is better)
    - > 0.9: Excellent fit
    - 0.7-0.9: Good fit
    - < 0.7: Poor fit (consider more data or parameters)
    
    **Confidence Intervals**: Uncertainty in parameter estimates
    - Narrow intervals = high confidence
    - Wide intervals = more data needed
    
    **Sensitivity**: How much each parameter affects the fit
    - High sensitivity = important parameter
    - Low sensitivity = may not need calibration
    
    ### Best Practices
    
    1. Start with good initial guesses
    2. Use reasonable bounds (0.1x - 10x of initial)
    3. Calibrate 3-5 parameters at a time
    4. Validate on independent data
    5. Check biological plausibility of results
    
    ### Troubleshooting
    
    **Calibration fails**:
    - Check data quality and format
    - Widen parameter bounds
    - Reduce number of parameters
    - Try different optimization method
    
    **Poor R² score**:
    - Model may not capture all biology
    - Consider adding more parameters
    - Check experimental data quality
    - May need model structure changes
    """)
