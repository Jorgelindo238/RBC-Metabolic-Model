"""
Streamlit shim — lightweight fake 'streamlit' module so that
streamlit_app/core/*.py can be imported in a pure FastAPI process
without installing the real streamlit package.

Only the surface area actually touched by the core modules is mocked:
  - st.session_state  (empty dict)
  - st.error / st.info / st.warning  (no-ops)
  - st.cache_data / st.cache_resource  (identity decorators)
"""

import types
import sys


def _noop(*args, **kwargs):
    """Silent no-op replacing st.error / st.info / st.warning."""
    pass


def _identity_decorator(*dec_args, **dec_kwargs):
    """Identity decorator replacing @st.cache_data / @st.cache_resource.

    Handles both ``@st.cache_data`` and ``@st.cache_data(show_spinner=False)``
    call styles.
    """
    # Called as @st.cache_data  (no parentheses) → dec_args[0] is the function
    if len(dec_args) == 1 and callable(dec_args[0]) and not dec_kwargs:
        return dec_args[0]
    # Called as @st.cache_data(...)  → return a wrapper that returns the function
    def wrapper(fn):
        return fn
    return wrapper


def install():
    """Register the fake streamlit module in sys.modules.

    Must be called **before** any ``from core.* import ...`` statement
    so that ``import streamlit as st`` inside those modules resolves here.
    """
    if "streamlit" in sys.modules:
        return  # already installed (real or shim)

    mod = types.ModuleType("streamlit")
    mod.session_state = {}
    mod.error = _noop
    mod.info = _noop
    mod.warning = _noop
    mod.cache_data = _identity_decorator
    mod.cache_resource = _identity_decorator
    sys.modules["streamlit"] = mod
