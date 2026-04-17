"""
Simulation Page - Run RBC Metabolic Simulations
"""

import streamlit as st
import pandas as pd
import sys
from pathlib import Path
import time

# Import backend modules
sys.path.append(str(Path(__file__).parent.parent))
from core.simulation_engine import SimulationEngine, export_results_csv
from core.plotting import plot_metabolites_interactive, plot_summary_statistics, plot_ph_profile
from core.bohr_plotting import plot_bohr_overview, plot_bohr_summary_cards, create_bohr_interpretation_text
from core.data_loader import validate_data_files, get_data_summary
from core.auth import init_session_state, check_page_auth, get_user_name, get_user_id, AuthManager
from core.styles import apply_global_styles, render_page_header

st.set_page_config(
    page_title="Simulation - RBC Model",
    page_icon="🚀",
    layout="wide"
)

# Apply global styles
apply_global_styles()

# Initialize and check authentication
init_session_state()
if not check_page_auth():
    st.stop()

render_page_header(
    "Simulation Workspace",
    "Configure mechanistic RBC storage simulations, compare built-in or uploaded experimental contexts, and study perturbation-driven behavior.",
    "🧪"
)

# Check for custom uploaded data
if 'uploaded_data_active' in st.session_state and st.session_state.get('uploaded_data_active'):
    st.success(f"""
    ✅ **Using Custom Uploaded Data**  
    📁 File: {st.session_state.get('uploaded_filename', 'Unknown')}  
    📊 {len(st.session_state.get('uploaded_data', pd.DataFrame()))} timepoints, {len(st.session_state.get('uploaded_data', pd.DataFrame()).columns)-1} metabolites
    """)
    st.caption("💡 Go to Data Upload page to change data source")

st.markdown("---")

# Sidebar configuration
with st.sidebar:
    st.markdown("### Workspace")
    st.info("""
    **Current page:** Simulation
    
    Use this workspace to define the simulation horizon,
    choose the experimental context, and launch a storage run
    before moving into flux or pathway analysis.
    """)
    
    st.markdown("---")
    
    st.header("⚙️ Simulation Parameters")
    
    # Time configuration
    st.subheader("⏱️ Time Settings")
    t_max = st.slider(
        "Simulation Duration (days)",
        min_value=1,
        max_value=72,
        value=42,
        help="Total simulation time in days"
    )
    
    # Curve fitting
    st.subheader("📈 Curve Fitting")
    curve_fit_strength = st.slider(
        "Fitting Strength (%)",
        min_value=0,
        max_value=100,
        value=0,
        help="0% = Pure Michaelis-Menten kinetics with calibrated parameters (recommended)\n100% = Blend with experimental curves"
    )
    
    st.info(f"""
    **Current Setting:**
    - Pure MM: {100 - curve_fit_strength}%
    - Experimental: {curve_fit_strength}%
    """)
    
    # Initial conditions
    st.subheader("🔬 Initial Conditions")
    ic_source = st.selectbox(
        "Data Source",
        ["JA Final (Recommended)", "Bordbar Experimental", "Custom"],
        help="Source for initial metabolite concentrations"
    )
    
    # pH Perturbation
    st.subheader("🧪 pH Perturbation")
    st.caption("⚗️ Simulate extracellular pH changes (acidosis, alkalosis, custom)")
    ph_perturbation = st.selectbox(
        "Perturbation Type",
        ["None", "Acidosis", "Alkalosis", "Step", "Ramp"],
        help="Type of pH perturbation to apply during simulation"
    )
    
    ph_severity = None
    ph_target = None
    ph_duration = None
    
    if ph_perturbation in ["Acidosis", "Alkalosis"]:
        ph_severity = st.select_slider(
            "Severity",
            options=["Mild", "Moderate", "Severe"],
            value="Moderate",
            help="Severity of pH perturbation"
        )
    elif ph_perturbation == "Step":
        ph_target = st.slider(
            "Target pH",
            min_value=6.5,
            max_value=7.8,
            value=7.0,
            step=0.1,
            help="Target pH for step perturbation"
        )
    elif ph_perturbation == "Ramp":
        col1, col2 = st.columns(2)
        with col1:
            ph_target = st.slider(
                "Target pH",
                min_value=6.5,
                max_value=7.8,
                value=7.0,
                step=0.1,
                help="Final pH value"
            )
        with col2:
            ph_duration = st.slider(
                "Duration (h)",
                min_value=1,
                max_value=12,
                value=6,
                help="Duration of pH ramp"
            )
    
    # Advanced settings
    with st.expander("🔧 Advanced Solver Settings"):
        solver_method = st.selectbox(
            "Solver Method",
            ["RK45", "BDF", "LSODA"],
            help="Numerical integration method"
        )
        rtol = st.number_input(
            "Relative Tolerance",
            value=1e-6,
            format="%.2e",
            help="Relative error tolerance"
        )
        atol = st.number_input(
            "Absolute Tolerance",
            value=1e-8,
            format="%.2e",
            help="Absolute error tolerance"
        )

# Main content area
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📋 Configuration Summary")
    
    # Display configuration
    ph_info = "None"
    if ph_perturbation != "None":
        if ph_severity:
            ph_info = f"{ph_perturbation} ({ph_severity})"
        elif ph_target:
            if ph_duration:
                ph_info = f"{ph_perturbation} (pH → {ph_target} over {ph_duration}h)"
            else:
                ph_info = f"{ph_perturbation} (pH → {ph_target})"
        else:
            ph_info = ph_perturbation
    
    st.markdown(f"""
    **Simulation Configuration:**
    - ⏱️ **Duration:** {t_max} days
    - 📈 **Curve Fitting:** {curve_fit_strength}% strength
    - 🔬 **Initial Conditions:** {ic_source}
    - 🧪 **pH Perturbation:** {ph_info}
    - 🔧 **Solver:** {solver_method}
    - 🎯 **Tolerances:** rtol={rtol:.2e}, atol={atol:.2e}
    """)
    
    st.markdown("---")
    
    # Status messages
    st.subheader("🚀 Simulation Control")
    
    if st.button("▶️ Start Simulation", type="primary", width="stretch"):
        # Validate data files
        file_status = validate_data_files()
        missing_files = [name for name, exists in file_status.items() if not exists]
        
        if missing_files:
            st.error(f"❌ Missing required data files: {', '.join(missing_files)}")
            st.info("Please ensure all data files are in the project root directory")
        else:
            # Run simulation
            with st.spinner("🔄 Running simulation..."):
                # Progress bar
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                def update_progress(progress, message):
                    progress_bar.progress(progress)
                    status_text.text(message)
                
                # Create engine and run
                engine = SimulationEngine()
                results = engine.run_simulation(
                    t_max=t_max,
                    curve_fit_strength=curve_fit_strength/100,
                    ic_source=ic_source,
                    solver_method=solver_method,
                    rtol=rtol,
                    atol=atol,
                    ph_perturbation_type=ph_perturbation,
                    ph_severity=ph_severity if ph_perturbation in ["Acidosis", "Alkalosis"] else "Moderate",
                    ph_target=ph_target if ph_perturbation in ["Step", "Ramp"] else 7.0,
                    ph_duration=ph_duration if ph_perturbation == "Ramp" else 6,
                    progress_callback=update_progress
                )
                
                # Check results
                if results and results.get('success', False):
                    st.session_state['simulation_results'] = results
                    st.session_state['simulation_done'] = True
                    
                    st.success(f"✅ Simulation completed in {results['duration']:.1f} seconds!")
                else:
                    error_msg = results.get('error', 'Unknown error') if results else 'No results returned'
                    st.error(f"❌ Simulation failed: {error_msg}")
                    
                progress_bar.empty()
                status_text.empty()

with col2:
    st.subheader("📊 Expected Outputs")
    
    st.markdown("""
    **Upon completion, you will receive:**
    
    ✅ **Metabolite Dynamics**
    - 114 metabolite concentrations over time
    - Interactive plots
    
    ✅ **Flux Analysis**
    - Reaction flux distributions
    - Pathway heatmaps
    
    ✅ **Comparison Data**
    - Experimental vs simulated
    - Goodness-of-fit metrics
    
    ✅ **Export Options**
    - CSV data files
    - PDF reports
    - Complete ZIP archive
    """)
    
    st.markdown("---")
    
    st.success("""
    **💡 Tip:**
    
    Start with default parameters for your first simulation. 
    They are based on physiological values from Bordbar et al. (2015).
    """)

# Information section
st.markdown("---")
st.subheader("ℹ️ About This Simulation")

tab1, tab2, tab3 = st.tabs(["📖 Model Info", "⚙️ Parameters", "🎓 Tutorial"])

with tab1:
    st.markdown("""
    ### RBC Metabolic Model
    
    This simulation implements the comprehensive red blood cell metabolic model 
    from **Bordbar et al. (2015)**.
    
    **Key Features:**
    - **114 metabolites** including intracellular and extracellular species
    - **Multiple pathways:** Glycolysis, Pentose Phosphate Pathway, Nucleotide metabolism, etc.
    - **Experimental validation:** Fitted to time-series metabolomics data
    - **pH dynamics:** Includes intracellular pH modeling
    
    **References:**
    - Bordbar A, et al. (2015). "iAB-RBC-283: A proteomically derived knowledge-base 
      of erythrocyte metabolism that can be used to simulate its physiological and 
      patho-physiological states." BMC Systems Biology, 9:82.
    """)

with tab2:
    st.markdown("""
    ### Parameter Guide
    
    **Simulation Duration:**
    - Standard: 42 days (captures full dynamics)
    - Short: 12-24 days (quick tests)
    - Extended: 48-72 days (long-term behavior)
    
    **Curve Fitting Strength:**
    - 0%: Pure mechanistic model (MM kinetics only)
    - 50%: Balanced hybrid approach
    - 100%: Maximum experimental data integration
    
    **Solver Methods:**
    - **RK45:** General-purpose, explicit Runge-Kutta (recommended)
    - **BDF:** For stiff systems, implicit method
    - **LSODA:** Automatic stiffness detection
    """)

with tab3:
    st.markdown("""
    ### Quick Tutorial
    
    **Step 1: Choose Duration**
    - Use slider to set simulation time
    - Default 42h captures key dynamics
    
    **Step 2: Set Fitting Strength**
    - 100% for best experimental match
    - Lower values for mechanistic insights
    
    **Step 3: Select Initial Conditions**
    - "JA Final" recommended (physiological)
    - "Bordbar" for paper replication
    
    **Step 4: Run Simulation**
    - Click "Start Simulation"
    - Wait for completion (~30-60 seconds)
    - Explore outputs in Flux Analysis or Pathway Visualization
    
    **Step 5: Analyze & Export**
    - View interactive plots
    - Download data (CSV, PDF, ZIP)
    - Compare with experimental data
    """)

# Display results if simulation completed
if st.session_state.get('simulation_done', False):
    st.markdown("---")
    st.header("📊 Simulation Results")
    
    results = st.session_state.get('simulation_results')
    
    if results:
        # Quick stats
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Time Points", results['n_points'])
        with col2:
            st.metric("Metabolites", results['n_metabolites'])
        with col3:
            st.metric("Duration", f"{results['duration']:.1f}s")
        with col4:
            st.metric("Solver", results['solver'])
        
        # pH Perturbation info and profile
        if 'ph_perturbation' in results and results['ph_perturbation']['type'] != "None":
            ph_info = results['ph_perturbation']
            st.info(f"🧪 **pH Perturbation Active:** {ph_info['description']}")
            
            # Plot pH profile
            with st.expander("📉 View pH Perturbation Profile", expanded=False):
                ph_fig = plot_ph_profile(ph_info, results['t'][-1])
                if ph_fig:
                    st.plotly_chart(ph_fig, use_container_width=True)
            
            # Bohr Effect Analysis (only when pH perturbation is active)
            if 'bohr_effect' in results and results['bohr_effect'] is not None:
                st.markdown("---")
                st.subheader("🫁 Bohr Effect Analysis")
                st.caption("*Impact of pH changes on oxygen binding and delivery*")
                
                bohr_data = results['bohr_effect']
                
                # Summary cards
                bohr_summary = plot_bohr_summary_cards(bohr_data)
                if bohr_summary:
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        P50_mean = bohr_summary['P50']['mean']
                        P50_change = bohr_summary['P50']['change']
                        delta_color = "inverse" if P50_change < 0 else "normal"
                        st.metric(
                            "Mean P50", 
                            f"{P50_mean:.1f} mmHg",
                            f"{P50_change:+.1f} mmHg",
                            delta_color=delta_color
                        )
                        st.caption("Half-saturation pressure")
                    
                    with col2:
                        sat_art = bohr_summary['saturation']['arterial']
                        st.metric(
                            "Arterial O₂ Sat", 
                            f"{sat_art:.1f}%"
                        )
                        st.caption("Pulmonary capillaries")
                    
                    with col3:
                        extraction = bohr_summary['saturation']['extraction']
                        st.metric(
                            "O₂ Extraction", 
                            f"{extraction:.1f}%"
                        )
                        st.caption("Tissue delivery")
                    
                    with col4:
                        BPG_mean = bohr_summary['BPG']['mean']
                        st.metric(
                            "2,3-BPG", 
                            f"{BPG_mean:.2f} mM"
                        )
                        st.caption("Allosteric regulator")
                
                # Comprehensive Bohr visualization
                with st.expander("📊 View Detailed Bohr Effect Analysis", expanded=True):
                    bohr_fig = plot_bohr_overview(bohr_data)
                    if bohr_fig:
                        st.plotly_chart(bohr_fig, use_container_width=True)
                    
                    # Clinical interpretation
                    st.markdown("### 🔬 Clinical Interpretation")
                    interpretation = create_bohr_interpretation_text(bohr_summary, ph_info['type'])
                    st.markdown(interpretation)
                    
                    # Download Bohr data
                    st.markdown("### 💾 Export Bohr Metrics")
                    import pandas as pd
                    df_bohr = pd.DataFrame(bohr_data)
                    csv_bohr = df_bohr.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Bohr Effect Data (CSV)",
                        data=csv_bohr,
                        file_name=f"bohr_effect_{ph_info['type'].lower()}.csv",
                        mime="text/csv",
                        help="Download P50, O2 saturation, pH, and BPG data"
                    )
        
        st.markdown("---")
        
        # Metabolite selection and plotting
        st.subheader("📈 Interactive Visualization")
        
        # Show available experimental data
        if 'experimental_data' in results and results['experimental_data']['metabolites']:
            exp_metabolites = results['experimental_data']['metabolites']
            with st.expander(f"ℹ️ Experimental Data Available ({len(exp_metabolites)} metabolites)"):
                st.info("📊 **Experimental data from Bordbar et al.** is displayed for all matching metabolites (case-insensitive name matching).")
                st.caption("Metabolites with experimental data:")
                # Display in columns for compact view
                cols = st.columns(4)
                for i, metab in enumerate(sorted(exp_metabolites)):
                    cols[i % 4].markdown(f"- `{metab}`")
        
        # Select metabolites to plot
        # Add pHi if pH perturbation is active
        if 'ph_perturbation' in results and results['ph_perturbation']['type'] != "None":
            default_metabolites = ['EGLC', 'ELAC', 'ATP', 'ADP', 'PHI', 'GLC']
        else:
            default_metabolites = ['EGLC', 'ELAC', 'ATP', 'ADP', 'GLC', 'LAC']
        available_metabolites = [m for m in default_metabolites if m in results['metabolite_names']]
        
        # Display mode selection
        col_mode1, col_mode2 = st.columns([3, 1])
        with col_mode1:
            selected_metabolites = st.multiselect(
                "Select Metabolites to Plot",
                options=results['metabolite_names'],
                default=available_metabolites[:5] if available_metabolites else results['metabolite_names'][:5],
                help="Choose metabolites to visualize"
            )
        with col_mode2:
            display_mode = st.radio(
                "Display Mode",
                ["Separate Plots", "Combined"],
                index=0,
                help="Separate plots for different concentration ranges"
            )
        
        if selected_metabolites:
            if display_mode == "Separate Plots":
                # Create individual plots for each metabolite
                st.info(f"📊 Displaying {len(selected_metabolites)} metabolites on separate plots")
                
                # Use columns for compact display (2 plots per row)
                for i in range(0, len(selected_metabolites), 2):
                    cols = st.columns(2)
                    
                    for j, col in enumerate(cols):
                        if i + j < len(selected_metabolites):
                            metabolite = selected_metabolites[i + j]
                            with col:
                                from core.plotting import plot_single_metabolite_comparison
                                fig = plot_single_metabolite_comparison(results, metabolite)
                                if fig:
                                    st.plotly_chart(fig, use_container_width=True)
            else:
                # Original combined plot
                st.warning("⚠️ Combined mode: Metabolites with very different concentrations may not be visible")
                fig = plot_metabolites_interactive(results, selected_metabolites, show_experimental=True)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        # Export section
        st.subheader("📥 Export Results")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # CSV export
            csv_data = export_results_csv(results)
            st.download_button(
                label="📄 Download CSV",
                data=csv_data,
                file_name="simulation_results.csv",
                mime="text/csv",
                width="stretch"
            )
        
        with col2:
            # Summary statistics
            if st.button("📊 Show Summary Statistics", width="stretch"):
                fig_summary = plot_summary_statistics(results)
                if fig_summary:
                    st.plotly_chart(fig_summary, use_container_width=True)

# Footer
st.markdown("---")
st.caption("💡 Need help? Check the Documentation or start with default parameters!")
