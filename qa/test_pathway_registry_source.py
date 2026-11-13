"""Read-only display-registry regression checks. No ODE is executed."""

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT, ROOT / "src", ROOT / "streamlit_app"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from streamlit_app.core import pathway_registry as registry


def test_tracker_audit_and_quote_style_do_not_change_declared_names():
    source = '''
raise AssertionError("source must never execute")
def tracker():
    flux_dict = {"VHK": compute(), 'VELAC': missing_value}
    if reaction_audit is not None:
        flux_dict.update(reaction_audit["effective_fluxes"])
    _flux.add_timepoint(t, flux_dict)
'''
    assert registry._extract_declared_flux_names(source) == ["VHK", "VELAC"]


@pytest.mark.parametrize("source", [
    "other = {'VHK': 1}",
    "flux_dict = {}; flux_dict = {}",
    "flux_dict = build_fluxes()",
    "flux_dict = {dynamic_key: 1}",
    "flux_dict = {'VHK': 1, **extra}",
    "flux_dict = {'VHK': 1, 'VHK': 2}",
])
def test_ambiguous_or_dynamic_declarations_fail_closed(source):
    with pytest.raises(RuntimeError):
        registry._extract_declared_flux_names(source)


def test_current_ode_tracker_and_network_are_readable():
    names = registry._load_equadiff_reaction_names()
    assert names[0] == "VHK"
    assert names[-1] == "VEGSH_deg"
    assert {"VAK", "VOPLAH", "VEGLC", "VELAC"} <= set(names)
    assert len(names) == len(set(names))
    payload = registry.build_pathway_network_payload()
    assert payload["nodes"]
    assert payload["edges"]
    assert payload["reactionNodes"]
