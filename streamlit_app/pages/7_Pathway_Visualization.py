"""
Advanced Pathway Visualization Page
KEGG-style interactive metabolic maps

Author: Jorgelindo da Veiga
Date: 2025-11-22
"""

import streamlit as st
import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Add streamlit_app to path for core.* imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.auth import init_session_state, check_page_auth
from core.simulation_engine import SimulationEngine
from core.pathway_visualization import (
    MetabolicNetworkVisualizer,
    create_3d_metabolite_heatmap,
    create_hierarchical_clustering
)
from core.styles import apply_global_styles, render_page_header

# Page config
st.set_page_config(
    page_title="Pathway Visualization",
    page_icon="🗺️",
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
    "RBC Metabolic Atlas",
    "Explore pathway-level structure, time-dependent state changes, and metabolite relationships across the RBC network.",
    "🗺️"
)
st.markdown("---")

# Tabs for different visualizations
tab1, tab2, tab3, tab4 = st.tabs([
    "📍 KEGG-Style Map",
    "🎬 Animated Pathway",
    "📊 3D Heatmap",
    "🌳 Clustering"
])

# Sidebar - Simulation controls
with st.sidebar:
    st.header("Simulation Context")
    
    run_new_sim = st.checkbox("Run new simulation", value=False)
    
    if run_new_sim:
        t_max = st.slider("Simulation Time (days)", 1, 72, 7)
        ic_source = st.selectbox(
            "Initial Conditions",
            ["Bordbar", "JA Final", "Averages"]
        )
        
        if st.button("🚀 Run Simulation", type="primary", use_container_width=True):
            with st.spinner("Running simulation..."):
                engine = SimulationEngine()
                results = engine.run_simulation(
                    t_max=t_max,
                    ic_source=ic_source
                )
                
                if 'error' not in results:
                    # Convert to DataFrame
                    time_hours = results['t'] * 24.0
                    data = {'time': time_hours}
                    for i, name in enumerate(results['metabolite_names']):
                        data[name] = results['x'][:, i]
                    
                    st.session_state.sim_data = pd.DataFrame(data)
                    st.success(f"✅ Simulation complete! {len(time_hours)} timepoints")
                else:
                    st.error(f"Simulation failed: {results['error']}")
    
    else:
        st.info("Using cached simulation data or run a new one above")
    
    st.markdown("---")
    
    # Metabolite selection
    st.header("🎯 Metabolite Selection")
    
    # Corrected metabolite names based on actual model
    metabolite_presets = {
        "Glycolysis": ['GLC', 'G6P', 'F6P', 'B13PG', 'B23PG', 'PEP', 'PYR', 'LAC'],
        "Energy": ['ATP', 'ADP', 'AMP', 'NAD', 'NADH', 'NADP', 'NADPH'],
        "PPP": ['G6P', 'GL6P', 'RU5P', 'R5P', 'X5P', 'S7P', 'E4P'],
        "Nucleotides": ['IMP', 'INO', 'HYPX', 'XAN', 'ADE', 'GUA'],
        "Amino Acids": ['GLY', 'SER', 'ALA']
    }
    
    preset = st.selectbox("Preset Group", list(metabolite_presets.keys()))
    selected_metabolites = metabolite_presets[preset]
    
    # Filter to only available metabolites in simulation data
    if 'sim_data' in st.session_state and not st.session_state.sim_data.empty:
        available_metabs = [m for m in selected_metabolites if m in st.session_state.sim_data.columns]
        missing_metabs = [m for m in selected_metabolites if m not in st.session_state.sim_data.columns]
        
        selected_metabolites = available_metabs
        
        if missing_metabs:
            st.caption(f"⚠️ Unavailable: {', '.join(missing_metabs)}")
        st.caption(f"✅ Selected: {', '.join(selected_metabolites)}")
    else:
        st.caption(f"Selected: {', '.join(selected_metabolites)}")

# Get or create simulation data
if 'sim_data' not in st.session_state:
    # Run a quick default simulation
    with st.spinner("Loading default simulation..."):
        engine = SimulationEngine()
        results = engine.run_simulation(t_max=7)
        
        if 'error' not in results:
            time_hours = results['t'] * 24.0
            data = {'time': time_hours}
            for i, name in enumerate(results['metabolite_names']):
                data[name] = results['x'][:, i]
            st.session_state.sim_data = pd.DataFrame(data)

sim_data = st.session_state.get('sim_data', pd.DataFrame())

# CRITICAL: Filter selected_metabolites to only those available in sim_data
if not sim_data.empty:
    selected_metabolites = [m for m in selected_metabolites if m in sim_data.columns]
    if not selected_metabolites:
        st.error("⚠️ No valid metabolites selected! Please choose a different preset.")
        st.stop()

# Tab 1: KEGG-Style Static Map
with tab1:
    st.header("📍 KEGG-Style Metabolic Network")
    st.markdown("""
    Interactive metabolic pathway map showing:
    - **Nodes**: Metabolites (size/color = concentration)
    - **Edges**: Enzymatic reactions
    - **Colors**: Pathway membership (Red=Glycolysis, Purple=PPP, Orange=Rapoport-Luebering)
    """)
    
    if not sim_data.empty:
        col1, col2 = st.columns([3, 1])
        
        with col2:
            # Time selection
            time_points = sim_data['time'].values
            selected_time_idx = st.slider(
                "Select Timepoint",
                0, len(time_points)-1, len(time_points)-1,
                format="%.1f hours"
            )
            selected_time = time_points[selected_time_idx]
            
            st.metric("Time", f"{selected_time:.1f} hours")
            
            # Show key metabolites
            st.subheader("Key Metabolites")
            key_metabs = ['ATP', 'ADP', 'G6P', 'LAC']
            for metab in key_metabs:
                if metab in sim_data.columns:
                    value = sim_data[metab].iloc[selected_time_idx]
                    st.metric(metab, f"{value:.3f} mM")
        
        with col1:
            # Create pathway map
            visualizer = MetabolicNetworkVisualizer()
            
            # Get data for selected timepoint
            data_at_time = sim_data[sim_data['time'] == selected_time]
            
            fig = visualizer.create_static_pathway_map(
                metabolite_data=data_at_time,
                title=f"RBC Metabolic Network (t={selected_time:.1f}h)"
            )
            
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No simulation data available. Run a simulation first!")

# Tab 2: Animated Pathway
with tab2:
    st.header("🎬 Animated Metabolic Pathway")
    st.markdown("""
    Watch metabolite concentrations change over time in the pathway network.
    Use the **Play** button and **slider** to control the animation.
    """)
    
    if not sim_data.empty:
        # Animation settings
        col1, col2 = st.columns([3, 1])
        
        with col2:
            frame_step = st.slider(
                "Animation Speed (frame skip)",
                1, 10, 3,
                help="Higher = faster but less smooth"
            )
            
            st.info(f"Total frames: {len(sim_data) // frame_step}")
        
        with col1:
            with st.spinner("Creating animation..."):
                visualizer = MetabolicNetworkVisualizer()
                fig = visualizer.create_animated_pathway(
                    simulation_results=sim_data,
                    frame_step=frame_step
                )
                
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No simulation data available. Run a simulation first!")

# Tab 3: 3D Heatmap
with tab3:
    st.header("📊 3D Metabolite Heatmap")
    st.markdown("""
    3D surface plot showing metabolite concentration evolution:
    - **X-axis**: Time
    - **Y-axis**: Metabolites
    - **Z-axis / Color**: Concentration
    """)
    
    if not sim_data.empty:
        # Create 3D heatmap
        fig = create_3d_metabolite_heatmap(
            simulation_results=sim_data,
            metabolites=selected_metabolites
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Download data
        st.subheader("📥 Export Data")
        
        # Prepare export
        export_data = sim_data[['time'] + selected_metabolites].copy()
        
        csv = export_data.to_csv(index=False)
        st.download_button(
            "💾 Download CSV",
            csv,
            "metabolite_timeseries.csv",
            "text/csv"
        )
    else:
        st.warning("No simulation data available. Run a simulation first!")

# Tab 4: Clustering
with tab4:
    st.header("🌳 Hierarchical Clustering")
    st.markdown("""
    Cluster metabolites based on their temporal correlation patterns.
    Metabolites with similar dynamics are grouped together.
    """)
    
    if not sim_data.empty:
        # Create clustering
        fig = create_hierarchical_clustering(
            simulation_results=sim_data,
            metabolites=selected_metabolites
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Interpretation
        st.info("""
        **Interpretation:**
        - **Lower branches**: More similar metabolites
        - **Height**: Dissimilarity measure
        - **Groups**: Metabolites with coordinated regulation
        """)
    else:
        st.warning("No simulation data available. Run a simulation first!")

# Footer
st.markdown("---")
st.caption("""
**Visualization Features:**
- 🗺️ KEGG-style pathway layout
- 🎬 Temporal animations
- 📊 Multi-dimensional views
- 🔍 Interactive exploration

*Based on Bordbar et al. (2015) RBC model*
""")
