"""
RBC Metabolic Model - Streamlit Web Application
Main Entry Point

Author: Jorgelindo da Veiga
Based on: Bordbar et al. (2015) Experimental Data
"""

import streamlit as st
from pathlib import Path
import sys

# Add streamlit_app to path for core.* imports
sys.path.insert(0, str(Path(__file__).parent))
from core.auth import init_session_state, get_user_name, get_user_email, AuthManager
from core.styles import apply_global_styles, render_gradient_divider, render_metric_card, render_feature_card, render_info_box, render_footer

# Page configuration
st.set_page_config(
    page_title="RBC Metabolic Model",
    page_icon="🩸",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "RBC Metabolic Model - Interactive simulation platform for red blood cell metabolism"
    }
)

# Apply global styles
apply_global_styles()

# Initialize auth session
init_session_state()

# Main header with gradient text
st.markdown('<h1 class="hero-header">🩸 RBC Metabolic Model</h1>', unsafe_allow_html=True)
st.markdown('<p class="hero-subtitle">Mechanistic simulation, validation, and calibration workspace for red blood cell metabolism under storage and perturbation conditions</p>', unsafe_allow_html=True)

# Authentication status widget
col_left, col_center, col_right = st.columns([1, 2, 1])

with col_center:
    if st.session_state.get("authenticated", False):
        # User is logged in
        user_name = get_user_name() or "User"
        user_email = get_user_email() or ""
        
        st.success(f"✅ Logged in as **{user_name}**")
        
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            if st.button("🧪 Simulation", width="stretch", type="primary"):
                st.switch_page("pages/1_Simulation.py")
        
        with col_b:
            if st.session_state.get("is_admin", False):
                if st.button("⚙️ Admin", width="stretch"):
                    st.switch_page("pages/6_Admin.py")
            else:
                st.button("⚙️ Admin", width="stretch", disabled=True, 
                         help="Admin access only")
        
        with col_c:
            if st.button("🚪 Logout", width="stretch"):
                auth = AuthManager()
                auth.sign_out()
                st.session_state.authenticated = False
                st.session_state.user = None
                st.session_state.user_profile = None
                st.session_state.is_admin = False
                st.rerun()
    else:
        # User is not logged in
        st.info("👋 Please log in to access simulations and analysis tools")
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            if st.button("🔑 Login", width="stretch", type="primary"):
                st.switch_page("pages/0_Login.py")
        
        with col_b:
            if st.button("📝 Sign Up", width="stretch"):
                st.switch_page("pages/0_Login.py")

# Hero section with gradient divider
render_gradient_divider()

col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    st.markdown("""
    <div class="welcome-card">
        <h3 style="color: #B91C1C; margin-top: 0;">Mechanistic RBC Research Workspace</h3>
        <p style="color: #4B5563; line-height: 1.7;">
            Use this platform to explore <strong>red blood cell metabolism</strong> through a mechanistic model grounded in
            <strong>Bordbar et al. (2015)</strong>, with tools for simulation, experimental comparison, and parameter refinement.
        </p>
        <p style="color: #4B5563; margin-bottom: 0;"><strong>Core workflows in this workspace:</strong></p>
        <ul style="color: #4B5563; margin-top: 0.5rem;">
            <li>Run storage-condition simulations across configurable time horizons</li>
            <li>Compare modeled trajectories against built-in or uploaded experimental datasets</li>
            <li>Inspect pathway fluxes, pH responses, and oxygen-related behavior</li>
            <li>Calibrate kinetic parameters for targeted research questions</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

render_gradient_divider()

# Features section with modern cards
st.markdown('<p class="section-header">Research Workflows</p>', unsafe_allow_html=True)

col1, col2, col3 = st.columns(3, gap="medium")

with col1:
    st.markdown("""
    <div class="feature-card">
        <h4>Simulation Workspace</h4>
        <p style="color: #4B5563; font-size: 0.95rem; line-height: 1.6;">
            Configure RBC storage simulations with explicit control over time horizon,
            data source, pH perturbation scenario, and numerical solver settings.
        </p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="feature-card">
        <h4>Data and Validation</h4>
        <p style="color: #4B5563; font-size: 0.95rem; line-height: 1.6;">
            Inspect metabolite trajectories, pathway fluxes, uploaded datasets,
            and fit quality using interactive plots and exportable analytical views.
        </p>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div class="feature-card">
        <h4>Calibration and Interpretation</h4>
        <p style="color: #4B5563; font-size: 0.95rem; line-height: 1.6;">
            Explore pathway structure, interpret oxygen and pH behavior,
            and run targeted calibration workflows to improve agreement with observed data.
        </p>
    </div>
    """, unsafe_allow_html=True)

render_gradient_divider()

# Model statistics with custom metric cards
st.markdown('<p class="section-header">Platform Snapshot</p>', unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4, gap="medium")

with col1:
    st.markdown("""
    <div class="metric-card">
        <div class="value">42</div>
        <div class="label">Day Horizon</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="metric-card">
        <div class="value">~200</div>
        <div class="label">Reactions</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div class="metric-card">
        <div class="value">8</div>
        <div class="label">Pathways</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown("""
    <div class="metric-card">
        <div class="value">14</div>
        <div class="label">Timepoints</div>
    </div>
    """, unsafe_allow_html=True)

render_gradient_divider()

# Quick start guide
st.markdown('<p class="section-header">Getting Started</p>', unsafe_allow_html=True)

with st.expander("**1️⃣ Run a baseline storage simulation**", expanded=False):
    st.markdown("""
    1. Open the **Simulation** page from the sidebar
    2. Keep the default settings for a first-pass RBC storage run
    3. Start the simulation and wait for the trajectory to complete
    4. Review the resulting metabolite and flux outputs
    5. Export data for downstream analysis if needed
    """)

with st.expander("**2️⃣ Validate model behavior against data**", expanded=False):
    st.markdown("""
    1. Use **Data Upload** to load your experimental dataset
    2. Return to **Simulation** or **Flux Analysis** to compare model behavior
    3. Inspect pathway activity, metabolite trends, and fit quality
    4. Use exported tables and figures for research review
    """)

with st.expander("**3️⃣ Move into advanced model analysis**", expanded=False):
    st.markdown("""
    - Use **Pathway Visualization** to inspect the network state over time
    - Use **Parameter Calibration** for interactive exploratory fitting
    - Use perturbation settings to study pH-driven storage responses
    """)

st.markdown("---")

# Sidebar navigation
with st.sidebar:
    st.markdown("---")
    
    # Login button - Gray, first when not authenticated
    if not st.session_state.get("authenticated", False):
        if st.button("🔑 Login", width="stretch", key="sidebar_login"):
            st.switch_page("pages/0_Login.py")
    
    # Home button - always visible
    if st.button("🏠 Home", width="stretch", key="sidebar_home"):
        st.switch_page("app.py")
    
    # Main pages - only when authenticated
    if st.session_state.get("authenticated", False):
        if st.button("🧪 Simulation", width="stretch", key="sidebar_simulation"):
            st.switch_page("pages/1_Simulation.py")
        
        if st.button("🔬 Flux Analysis", width="stretch", key="sidebar_flux"):
            st.switch_page("pages/2_Flux_Analysis.py")
        
        if st.button("🎯 Parameter Calibration", width="stretch", key="sidebar_calibration"):
            st.switch_page("pages/5_Parameter_Calibration.py")
        
        if st.button("🗺️ Pathway Visualization", width="stretch", key="sidebar_visualization"):
            st.switch_page("pages/7_Pathway_Visualization.py")
        
        # Data Upload button - Green (primary)
        if st.button("📤 Data Upload", width="stretch", type="primary", key="sidebar_upload"):
            st.switch_page("pages/4_Data_Upload.py")
    
    st.markdown("---")
    
    # Admin access
    if st.session_state.get("authenticated", False):
        if st.session_state.get("is_admin", False):
            if st.button("⚙️ Admin", width="stretch", key="sidebar_admin"):
                st.switch_page("pages/6_Admin.py")
        else:
            st.caption("⚙️ Admin (admins only)")
    
    st.markdown("---")
    
    st.markdown("### 📚 About")
    st.markdown("""
    <div class="info-box">
        <strong style="color: #B91C1C;">RBC Metabolic Model v2.0</strong><br><br>
        Mechanistic red blood cell metabolism workspace based on the
        Bordbar et al. (2015) reconstruction, with support for simulation,
        validation, pathway interpretation, and exploratory calibration.<br><br>
        <strong>Included capabilities:</strong>
        <ul style="margin: 0.5rem 0 0 0; padding-left: 1.2rem;">
            <li>Storage-condition simulation</li>
            <li>Experimental dataset comparison</li>
            <li>Pathway and flux exploration</li>
            <li>Calibration-oriented analysis</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### 🔗 Resources")
    st.markdown("""
    - [Original Article](https://www.cell.com/action/showPdf?pii=S2405-4712%2815%2900149-0)
    - Project documentation is available in the repository workspace
    - Use Data Upload to validate against your own experimental series
    """)
    
    st.markdown("### 💡 Tips")
    st.success("""
    **New to the workspace?**
    
    Start with the default Simulation settings,
    then use Flux Analysis or Pathway Visualization
    to interpret the resulting RBC storage trajectory.
    """)
    
    st.markdown("---")
    st.caption("Developed by Jorgelindo da Veiga • 2026")

# Footer with gradient
render_footer()
