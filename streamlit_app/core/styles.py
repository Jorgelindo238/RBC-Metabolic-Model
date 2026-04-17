"""
Shared Styles Module - Centralized CSS and Theme Configuration
All pages should import from here to maintain consistent styling.

Author: Jorgelindo da Veiga
"""
import streamlit as st

# =============================================================================
# COLOR PALETTE - Fade Red Gradient Theme
# =============================================================================
COLORS = {
    "red_50": "#FEF2F2",
    "red_100": "#FEE2E2",
    "red_200": "#FECACA",
    "red_300": "#FCA5A5",
    "red_400": "#F87171",
    "red_500": "#EF4444",
    "red_600": "#DC2626",
    "red_700": "#B91C1C",
    "red_800": "#991B1B",
    "red_900": "#7F1D1D",
    "gray_50": "#F9FAFB",
    "gray_100": "#F3F4F6",
    "gray_600": "#4B5563",
    "gray_800": "#1F2937",
    "green_500": "#28a745",
    "green_600": "#34ce57",
}

# =============================================================================
# GLOBAL CSS - Applied to all pages
# =============================================================================
GLOBAL_CSS = """
<style>
    /* Hide default Streamlit navigation */
    [data-testid="stSidebarNav"] {
        display: none;
    }
    
    /* Root variables for consistent theming */
    :root {
        --red-50: #FEF2F2;
        --red-100: #FEE2E2;
        --red-200: #FECACA;
        --red-300: #FCA5A5;
        --red-400: #F87171;
        --red-500: #EF4444;
        --red-600: #DC2626;
        --red-700: #B91C1C;
        --red-800: #991B1B;
        --red-900: #7F1D1D;
        --gray-50: #F9FAFB;
        --gray-100: #F3F4F6;
        --gray-600: #4B5563;
        --gray-800: #1F2937;
    }
    
    /* Hero header with gradient text */
    .hero-header {
        font-size: 3.25rem;
        font-weight: 800;
        background: linear-gradient(135deg, #991B1B 0%, #7F1D1D 50%, #5F1515 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        text-align: center;
        margin-bottom: 0.5rem;
        letter-spacing: -0.03em;
    }
    
    .hero-subtitle {
        font-size: 1.15rem;
        color: var(--gray-600);
        text-align: center;
        margin: 0 auto 2.25rem auto;
        font-weight: 400;
        line-height: 1.7;
        max-width: 760px;
    }
    
    /* Modern feature cards */
    .feature-card {
        background: linear-gradient(145deg, #FFFFFF 0%, #FFF7F7 100%);
        padding: 1.75rem;
        border-radius: 16px;
        border: 1px solid #F3D4D4;
        box-shadow: 0 10px 24px -16px rgba(127, 29, 29, 0.35);
        height: 100%;
        transition: all 0.25s ease;
    }
    
    .feature-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 16px 28px -18px rgba(127, 29, 29, 0.4);
        border-color: #E7BABA;
    }
    
    .feature-card h4 {
        color: var(--red-700);
        font-weight: 700;
        margin-bottom: 0.75rem;
    }
    
    /* Metric cards with gradient */
    .metric-card {
        background: linear-gradient(135deg, #991B1B 0%, #7F1D1D 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
        text-align: center;
        box-shadow: 0 14px 24px -16px rgba(127, 29, 29, 0.55);
    }
    
    .metric-card .value {
        font-size: 2.5rem;
        font-weight: 800;
        line-height: 1;
    }
    
    .metric-card .label {
        font-size: 0.875rem;
        opacity: 0.9;
        margin-top: 0.5rem;
        font-weight: 500;
    }
    
    /* Glass morphism welcome card */
    .welcome-card {
        background: linear-gradient(135deg, rgba(255, 250, 250, 0.96) 0%, rgba(254, 242, 242, 0.92) 100%);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(127, 29, 29, 0.08);
        border-left: 6px solid var(--red-700);
        border-radius: 20px;
        padding: 2rem;
        margin: 1rem 0;
        box-shadow: 0 16px 28px -24px rgba(127, 29, 29, 0.4);
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #FCFCFD 0%, #FFF5F5 100%);
        border-right: 1px solid rgba(127, 29, 29, 0.06);
    }
    
    /* Button styling */
    .stButton > button {
        border-radius: 10px;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(220, 38, 38, 0.25);
    }
    
    /* Divider with gradient */
    .gradient-divider {
        height: 3px;
        background: linear-gradient(90deg, transparent 0%, var(--red-300) 50%, transparent 100%);
        border: none;
        margin: 2rem 0;
        border-radius: 2px;
    }
    
    /* Section headers */
    .section-header {
        font-size: 1.5rem;
        font-weight: 700;
        color: var(--gray-800);
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    /* Info boxes */
    .info-box {
        background: linear-gradient(135deg, var(--red-50) 0%, white 100%);
        border-left: 4px solid var(--red-500);
        padding: 1rem 1.25rem;
        border-radius: 0 12px 12px 0;
        margin: 1rem 0;
    }
    
    /* Footer styling */
    .footer {
        text-align: center;
        padding: 2rem;
        color: var(--gray-600);
        background: linear-gradient(180deg, transparent 0%, var(--red-50) 100%);
        border-radius: 20px 20px 0 0;
        margin-top: 2rem;
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        background: linear-gradient(90deg, var(--red-50) 0%, white 100%);
        border-radius: 10px;
        font-weight: 600;
    }
    
    /* Page title styling */
    .page-title {
        font-size: 2rem;
        font-weight: 700;
        color: var(--red-700);
        margin-bottom: 0.35rem;
        letter-spacing: -0.02em;
    }
    
    .page-subtitle {
        font-size: 1rem;
        color: var(--gray-600);
        margin-bottom: 1.5rem;
        line-height: 1.65;
        max-width: 860px;
    }
</style>
"""

# =============================================================================
# LOGIN PAGE CSS - Specific styling for login/signup
# =============================================================================
LOGIN_CSS = """
<style>
    /* Hide default Streamlit navigation */
    [data-testid="stSidebarNav"] {
        display: none;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        background-color: rgba(220, 38, 38, 0.1);
        border-radius: 10px;
        padding-left: 24px;
        padding-right: 24px;
    }
    .stTabs [aria-selected="true"] {
        background-color: rgba(220, 38, 38, 0.2);
    }
    
    /* Login card styling */
    .login-container {
        max-width: 400px;
        margin: 0 auto;
        padding: 2rem;
        background: white;
        border-radius: 16px;
        box-shadow: 0 10px 40px rgba(220, 38, 38, 0.1);
    }
</style>
"""


def apply_global_styles():
    """Apply global CSS styles to the current page."""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def apply_login_styles():
    """Apply login-specific CSS styles."""
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)


def render_gradient_divider():
    """Render a gradient divider."""
    st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)


def render_page_header(title: str, subtitle: str = "", icon: str = ""):
    """
    Render a consistent page header.
    
    Parameters:
    -----------
    title : str
        Page title
    subtitle : str
        Optional subtitle/description
    icon : str
        Optional emoji icon
    """
    if icon:
        st.markdown(f'<h1 class="page-title">{icon} {title}</h1>', unsafe_allow_html=True)
    else:
        st.markdown(f'<h1 class="page-title">{title}</h1>', unsafe_allow_html=True)
    
    if subtitle:
        st.markdown(f'<p class="page-subtitle">{subtitle}</p>', unsafe_allow_html=True)


def render_metric_card(value: str, label: str):
    """
    Render a styled metric card.
    
    Parameters:
    -----------
    value : str
        The metric value to display
    label : str
        The label for the metric
    """
    st.markdown(f"""
    <div class="metric-card">
        <div class="value">{value}</div>
        <div class="label">{label}</div>
    </div>
    """, unsafe_allow_html=True)


def render_feature_card(title: str, content: str, icon: str = ""):
    """
    Render a styled feature card.
    
    Parameters:
    -----------
    title : str
        Card title
    content : str
        Card content/description
    icon : str
        Optional emoji icon
    """
    title_with_icon = f"{icon} {title}" if icon else title
    st.markdown(f"""
    <div class="feature-card">
        <h4>{title_with_icon}</h4>
        <p style="color: #4B5563; font-size: 0.95rem; line-height: 1.6;">
            {content}
        </p>
    </div>
    """, unsafe_allow_html=True)


def render_info_box(content: str, title: str = ""):
    """
    Render a styled info box.
    
    Parameters:
    -----------
    content : str
        Box content (can include HTML)
    title : str
        Optional title
    """
    if title:
        st.markdown(f"""
        <div class="info-box">
            <strong style="color: #B91C1C;">{title}</strong><br><br>
            {content}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="info-box">
            {content}
        </div>
        """, unsafe_allow_html=True)


def render_footer(text: str = "Ready to explore RBC metabolism?"):
    """Render a styled footer."""
    st.markdown(f"""
    <div class="footer">
        <p style="font-size: 1.1rem; font-weight: 600; color: #B91C1C; margin-bottom: 0.5rem;">{text}</p>
        <p style="margin: 0;">👈 Select a page from the sidebar to get started!</p>
    </div>
    """, unsafe_allow_html=True)
