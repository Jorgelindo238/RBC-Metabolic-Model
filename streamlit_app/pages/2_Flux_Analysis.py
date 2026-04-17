"""
Metabolic Flux Analysis Page
============================

Interactive visualization of metabolic fluxes with heatmap and detailed views.

Features:
- Flux distribution at initial, midpoint, and final timepoints
- Interactive heatmap (click to view flux details)
- Detailed flux analysis with substrate/product concentrations
- CSV export of flux data

Author: Jorgelindo da Veiga
Date: 2025-11-17
"""

import streamlit as st
import sys
import numpy as np
from pathlib import Path

# Add streamlit_app to path for core.* imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.flux_plotting import (
    create_flux_heatmap,
    create_flux_distribution_combined,
    create_flux_detail_view,
    export_flux_data_csv,
    create_flux_comparison_plot,
    create_flux_deviation_heatmap,
    create_experimental_flux_summary,
    create_flux_timeseries_plot
)
from core.flux_estimator import FluxEstimator, compute_flux_from_uploaded_data
from core.auth import init_session_state, check_page_auth
from core.styles import apply_global_styles, render_page_header

# Page configuration
st.set_page_config(
    page_title="Flux Analysis - RBC Model",
    page_icon="🔬",
    layout="wide"
)

# Apply global styles
apply_global_styles()

# Initialize and check authentication
init_session_state()
if not check_page_auth():
    st.stop()

# Title
render_page_header(
    "Flux Analysis",
    "Inspect pathway activity, compare reaction-level behavior across time, and review flux patterns from simulated or uploaded experimental contexts.",
    "🔬"
)

# Check if simulation results exist
has_simulation = (
    'simulation_results' in st.session_state and 
    st.session_state.simulation_results is not None
)

# Initialize flux_data as None
flux_data = None
results = None

if has_simulation:
    results = st.session_state.simulation_results
    
    # Check if flux data is available
    if 'flux_data' in results and results['flux_data'] is not None:
        flux_data = results['flux_data']
        
        # Check flux data validity
        if 'times' not in flux_data or 'fluxes' not in flux_data:
            flux_data = None
        elif len(flux_data.get('times', [])) == 0 or len(flux_data.get('fluxes', {})) == 0:
            flux_data = None

# Display simulation status
if flux_data:
    st.success(f"✅ Loaded simulation flux data: {len(flux_data['times'])} time points, {len(flux_data['fluxes'])} reactions")
else:
    st.info("ℹ️ No simulation flux data available. You can still analyze fluxes from uploaded custom data below.")

# Instructions at the top
st.markdown("---")
with st.expander("How to Use Flux Analysis", expanded=False):
    st.markdown("""
    ### Simulated Flux Analysis
    1. **Flux Distributions**: Compare pathway activities and top 20 reactions at initial, midpoint, and final timepoints
    2. **Flux Balance Analysis**: 
       - Use the sidebar to select a specific reaction
       - View detailed flux dynamics over time
       - Analyze substrate and product concentrations
       - Access statistical summaries
    3. **Flux Heatmap**: 
       - Overview of all fluxes over time grouped by metabolic pathway
       - Colors indicate normalized flux intensity (red = high, blue = low)
       - Quick visual identification of metabolic patterns
    
    ### Custom Dataset Flux Analysis (NEW!)
    4. **Experimental-Derived Fluxes**:
       - Upload your experimental data on the **📤 Data Upload** page
       - Compute fluxes from metabolite concentrations using Michaelis-Menten kinetics
       - Compare simulated vs experimental-derived fluxes
       - Identify deviations between model predictions and experimental data
    
    5. **Export**: Download flux data as CSV for further analysis
    
    **Pathways Tracked:**
    - 🔹 Glycolysis
    - 🔹 Pentose Phosphate Pathway
    - 🔹 Transport
    - 🔹 Nucleotide Metabolism
    - 🔹 Amino Acid Metabolism
    - 🔹 Redox Reactions
    - 🔹 2,3-BPG Shunt
    - 🔹 Other Reactions
    """)

# Initialize selected_reaction
selected_reaction = "None"

# Only show simulation-based analysis if flux_data exists
if flux_data:
    # Sidebar: Flux selection for detail view
    st.sidebar.title("🎯 Flux Selection")
    st.sidebar.markdown("Select a reaction to view detailed analysis")
    
    # Get all reaction names sorted
    all_reactions = sorted(flux_data['fluxes'].keys())
    
    # Reaction selector
    selected_reaction = st.sidebar.selectbox(
        "Select Reaction:",
        options=["None"] + all_reactions,
        help="Choose a reaction to view detailed time course and substrate/product dynamics"
    )
    
    # Export button in sidebar
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 💾 Export Data")
    if st.sidebar.button("📥 Download Flux Data (CSV)"):
        csv_data = export_flux_data_csv(flux_data)
        st.sidebar.download_button(
            label="💾 Save CSV File",
            data=csv_data,
            file_name="metabolic_fluxes.csv",
            mime="text/csv"
        )
        st.sidebar.success("✓ CSV ready for download!")
    
    # Main content
    st.markdown("---")
    
    # Section 1: Flux Distributions at Key Timepoints
    st.header("📊 Flux Distribution Analysis")
    st.caption("Compare pathway activities and top reactions at different timepoints")
    
    tab1, tab2, tab3 = st.tabs(["📌 Initial", "⏱️ Midpoint", "🏁 Final"])
    
    with tab1:
        with st.spinner("Generating initial timepoint distribution..."):
            fig_initial = create_flux_distribution_combined(flux_data, 'initial')
            st.plotly_chart(fig_initial, use_container_width=True)
    
    with tab2:
        with st.spinner("Generating midpoint distribution..."):
            fig_midpoint = create_flux_distribution_combined(flux_data, 'midpoint')
            st.plotly_chart(fig_midpoint, use_container_width=True)
    
    with tab3:
        with st.spinner("Generating final timepoint distribution..."):
            fig_final = create_flux_distribution_combined(flux_data, 'final')
            st.plotly_chart(fig_final, use_container_width=True)
    
    # Section 2: Detailed Flux Analysis (when reaction selected)
    if selected_reaction != "None":
        st.markdown("---")
        st.header(f"📈 Flux Balance Analysis: {selected_reaction}")
        st.caption(f"Comprehensive view of {selected_reaction} flux dynamics")
        
        with st.spinner(f"Analyzing {selected_reaction}..."):
            # Prepare metabolite results with simulation times
            metabolite_results = {
                'metabolite_names': results.get('metabolite_names', []),
                'concentrations': results.get('x', None),
                'sim_times': results.get('t', flux_data['times'])  # Use full simulation times
            }
            
            detail_fig = create_flux_detail_view(selected_reaction, flux_data, metabolite_results)
            st.plotly_chart(detail_fig, use_container_width=True)
        
        # Export button for this specific flux
        st.markdown("### 💾 Export This Flux")
        col1, col2 = st.columns([1, 3])
        with col1:
            import pandas as pd
            df_single = pd.DataFrame({
                'Time_days': flux_data['times'],
                f'{selected_reaction}_flux': flux_data['fluxes'][selected_reaction]
            })
            csv_single = df_single.to_csv(index=False)
            st.download_button(
                label=f"📥 Download {selected_reaction} Data",
                data=csv_single,
                file_name=f"flux_{selected_reaction}.csv",
                mime="text/csv"
            )
    
    # Section 3: Flux Heatmap
    st.markdown("---")
    st.header("🔥 Flux Heatmap Overview")
    st.caption("Normalized flux intensities for top reactions by variance, grouped by metabolic pathway (optimized for display)")
    
    with st.spinner("Generating flux heatmap..."):
        # Prepare metabolite results for detail view
        metabolite_results = {
            'metabolite_names': results.get('metabolite_names', []),
            'concentrations': results.get('x', None)
        }
        
        heatmap_fig = create_flux_heatmap(flux_data, metabolite_results)
        
        # Display heatmap
        st.plotly_chart(heatmap_fig, use_container_width=True)

# Section 4: Custom Dataset Flux Comparison
st.markdown("---")
st.header("📊 Custom Dataset Flux Analysis")

# Check if custom data is available
has_custom_data = (
    'uploaded_data' in st.session_state and 
    st.session_state.get('uploaded_data_active', False) and
    st.session_state['uploaded_data'] is not None
)

if has_custom_data:
    custom_df = st.session_state['uploaded_data']
    
    st.success(f"✅ Custom dataset available: {len(custom_df)} timepoints, {len(custom_df.columns)-1} metabolites")
    
    # Option to compute fluxes from custom data
    if st.button("🔬 Compute Fluxes from Custom Dataset", type="primary"):
        with st.spinner("Estimating fluxes from metabolite concentrations..."):
            try:
                # Compute experimental-derived fluxes
                exp_flux_data = compute_flux_from_uploaded_data(custom_df, time_col='Time')
                
                # Store in session state
                st.session_state['experimental_flux_data'] = exp_flux_data
                
                st.success(f"✅ Computed {len(exp_flux_data['fluxes'])} reaction fluxes from experimental data!")
            except Exception as e:
                st.error(f"❌ Error computing fluxes: {str(e)}")
    
    # Display comparison if experimental fluxes are computed
    if 'experimental_flux_data' in st.session_state and st.session_state['experimental_flux_data']:
        exp_flux_data = st.session_state['experimental_flux_data']
        
        st.markdown("---")
        
        # Check if we have simulation data for comparison
        if flux_data:
            # Create tabs for different views (with comparison)
            tab_compare, tab_deviation, tab_exp_only = st.tabs([
                "📈 Flux Comparison", 
                "📊 Deviation Analysis",
                "🔬 Experimental Fluxes Only"
            ])
            
            with tab_compare:
                st.subheader("Simulated vs Experimental-Derived Fluxes")
                st.caption("Compare fluxes from ODE simulation against those estimated from your experimental metabolite concentrations")
                
                # Reaction selector for comparison
                common_rxns = list(set(flux_data['fluxes'].keys()) & set(exp_flux_data['fluxes'].keys()))
                
                if common_rxns:
                    selected_rxns = st.multiselect(
                        "Select reactions to compare:",
                        options=sorted(common_rxns),
                        default=sorted(common_rxns)[:6],
                        max_selections=10,
                        help="Select up to 10 reactions for detailed comparison"
                    )
                    
                    if selected_rxns:
                        with st.spinner("Generating comparison plot..."):
                            comparison_fig = create_flux_comparison_plot(
                                flux_data, exp_flux_data, reactions=selected_rxns
                            )
                            st.plotly_chart(comparison_fig, use_container_width=True)
                else:
                    st.warning("No common reactions found between simulated and experimental data.")
            
            with tab_deviation:
                st.subheader("Flux Deviation Analysis")
                st.caption("Identify which reactions show the largest discrepancies between simulation and experiment")
                
                with st.spinner("Analyzing flux deviations..."):
                    deviation_fig = create_flux_deviation_heatmap(flux_data, exp_flux_data)
                    st.plotly_chart(deviation_fig, use_container_width=True)
                
                # Show summary statistics
                st.markdown("### Summary Statistics")
                col1, col2, col3 = st.columns(3)
                
                common_rxns = list(set(flux_data['fluxes'].keys()) & set(exp_flux_data['fluxes'].keys()))
                
                if common_rxns:
                    deviations = []
                    for rxn in common_rxns:
                        sim_mean = np.mean(np.abs(flux_data['fluxes'][rxn]))
                        exp_mean = np.mean(np.abs(exp_flux_data['fluxes'][rxn]))
                        if exp_mean > 1e-10:
                            dev = abs((sim_mean - exp_mean) / exp_mean * 100)
                            deviations.append(dev)
                    
                    with col1:
                        st.metric("Mean Deviation", f"{np.mean(deviations):.1f}%")
                    with col2:
                        st.metric("Max Deviation", f"{np.max(deviations):.1f}%")
                    with col3:
                        st.metric("Reactions Compared", len(common_rxns))
            
            with tab_exp_only:
                st.subheader("Experimental-Derived Fluxes")
                st.caption("View fluxes computed solely from your uploaded experimental data")
                
                # Sub-tabs for time series vs distribution view
                exp_view_type = st.radio(
                    "View type:",
                    options=["📈 Flux Curves Over Time", "📊 Distribution at Timepoint"],
                    horizontal=True,
                    key="exp_view_type"
                )
                
                if exp_view_type == "📈 Flux Curves Over Time":
                    # Get all available reactions
                    all_exp_reactions = sorted(exp_flux_data['fluxes'].keys())
                    
                    # Reaction selector
                    selected_exp_rxns = st.multiselect(
                        "Select reactions to plot:",
                        options=all_exp_reactions,
                        default=all_exp_reactions[:5] if len(all_exp_reactions) >= 5 else all_exp_reactions,
                        max_selections=15,
                        help="Select up to 15 reactions to visualize their flux over time",
                        key="exp_rxn_selector_with_sim"
                    )
                    
                    if selected_exp_rxns:
                        with st.spinner("Generating flux time series..."):
                            timeseries_figs = create_flux_timeseries_plot(exp_flux_data, selected_exp_rxns)
                            for fig in timeseries_figs:
                                st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("Please select at least one reaction to visualize.")
                else:
                    exp_timepoint = st.selectbox(
                        "Select timepoint:",
                        options=['initial', 'midpoint', 'final'],
                        index=2
                    )
                    
                    with st.spinner("Generating experimental flux summary..."):
                        exp_summary_fig = create_experimental_flux_summary(exp_flux_data, timepoint=exp_timepoint)
                        st.plotly_chart(exp_summary_fig, use_container_width=True)
                
                # Export experimental fluxes
                st.markdown("### 💾 Export Experimental Fluxes")
                exp_csv = export_flux_data_csv(exp_flux_data)
                st.download_button(
                    label="📥 Download Experimental Flux Data (CSV)",
                    data=exp_csv,
                    file_name="experimental_derived_fluxes.csv",
                    mime="text/csv"
                )
        else:
            # No simulation data - only show experimental fluxes
            st.info("ℹ️ Run a simulation to compare with experimental-derived fluxes.")
            
            # Create tabs for different views
            tab_timeseries, tab_distribution = st.tabs([
                "📈 Flux Curves Over Time",
                "📊 Flux Distribution"
            ])
            
            with tab_timeseries:
                st.subheader("🔬 Flux Dynamics Over Days")
                st.caption("Select reactions to visualize their flux changes over time")
                
                # Get all available reactions
                all_exp_reactions = sorted(exp_flux_data['fluxes'].keys())
                
                # Reaction selector
                selected_exp_rxns = st.multiselect(
                    "Select reactions to plot:",
                    options=all_exp_reactions,
                    default=all_exp_reactions[:5] if len(all_exp_reactions) >= 5 else all_exp_reactions,
                    max_selections=15,
                    help="Select up to 15 reactions to visualize their flux over time",
                    key="exp_rxn_selector_no_sim"
                )
                
                if selected_exp_rxns:
                    with st.spinner("Generating flux time series..."):
                        timeseries_figs = create_flux_timeseries_plot(exp_flux_data, selected_exp_rxns)
                        for fig in timeseries_figs:
                            st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("Please select at least one reaction to visualize.")
            
            with tab_distribution:
                st.subheader("🔬 Experimental-Derived Flux Distribution")
                st.caption("View fluxes computed from your uploaded experimental data at a specific timepoint")
                
                exp_timepoint = st.selectbox(
                    "Select timepoint:",
                    options=['initial', 'midpoint', 'final'],
                    index=2,
                    key="exp_timepoint_no_sim"
                )
                
                with st.spinner("Generating experimental flux summary..."):
                    exp_summary_fig = create_experimental_flux_summary(exp_flux_data, timepoint=exp_timepoint)
                    st.plotly_chart(exp_summary_fig, use_container_width=True)
            
            # Export experimental fluxes
            st.markdown("### 💾 Export Experimental Fluxes")
            exp_csv = export_flux_data_csv(exp_flux_data)
            st.download_button(
                label="📥 Download Experimental Flux Data (CSV)",
                data=exp_csv,
                file_name="experimental_derived_fluxes.csv",
                mime="text/csv",
                key="download_exp_no_sim"
            )

else:
    st.info("""
    👉 **No custom dataset loaded.** 
    
    To compare simulated fluxes with experimental data:
    1. Go to the **📤 Data Upload** page
    2. Upload your experimental metabolite concentration data
    3. Map columns to model metabolites
    4. Return here to compute and compare fluxes
    """)
    
    if st.button("🔗 Go to Data Upload"):
        st.switch_page("pages/4_Data_Upload.py")

# Debug info (only in development)
if st.sidebar.checkbox("Show Debug Info", value=False):
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🐛 Debug Information")
    
    if flux_data:
        st.sidebar.write(f"Time points: {len(flux_data['times'])}")
        st.sidebar.write(f"Reactions tracked: {len(flux_data['fluxes'])}")
        st.sidebar.write(f"Simulation duration: {flux_data['times'][-1]:.1f} days")
        if results:
            st.sidebar.write(f"Total metabolites: {results.get('n_metabolites', 'N/A')}")
    else:
        st.sidebar.write("No simulation data loaded")
    
    if has_custom_data:
        st.sidebar.write("---")
        st.sidebar.write("**Custom Data:**")
        st.sidebar.write(f"Timepoints: {len(st.session_state['uploaded_data'])}")
        st.sidebar.write(f"Metabolites: {len(st.session_state['uploaded_data'].columns) - 1}")
    
    if 'experimental_flux_data' in st.session_state and st.session_state['experimental_flux_data']:
        st.sidebar.write("---")
        st.sidebar.write("**Experimental Fluxes:**")
        st.sidebar.write(f"Reactions: {len(st.session_state['experimental_flux_data']['fluxes'])}")
