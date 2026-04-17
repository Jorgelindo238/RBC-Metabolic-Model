"""
Core modules for RBC simulation backend

This package provides the backend functionality for the Streamlit web application.
Import modules directly: from core.auth import AuthManager
"""

# Expose key modules for easier imports
from .styles import (
    apply_global_styles,
    apply_login_styles,
    render_gradient_divider,
    render_page_header,
    render_metric_card,
    render_feature_card,
    render_info_box,
    render_footer,
    COLORS
)

from .auth import (
    AuthManager,
    init_session_state,
    require_auth,
    check_page_auth,
    get_user_name,
    get_user_email,
    get_user_id
)

__all__ = [
    # Styles
    'apply_global_styles',
    'apply_login_styles', 
    'render_gradient_divider',
    'render_page_header',
    'render_metric_card',
    'render_feature_card',
    'render_info_box',
    'render_footer',
    'COLORS',
    # Auth
    'AuthManager',
    'init_session_state',
    'require_auth',
    'check_page_auth',
    'get_user_name',
    'get_user_email',
    'get_user_id',
]
