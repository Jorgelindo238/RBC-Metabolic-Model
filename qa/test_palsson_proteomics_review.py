"""Parsing protein evidence never executes HTML or establishes kinetic priors."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_palsson_proteomics_sources import CONFIG, GENES_TO_REACTIONS, parse_plotly, parse_table


def test_html_duplicate_columns_and_links_are_preserved():
    content = '<script>raise dangerous()</script><table><tr><th>Gene</th><th>Gene</th></tr><tr><td><a href="x">GAPDH</a></td><td>modified<br>site</td></tr></table>'
    headers, rows = parse_table(content)
    assert headers == ["Gene", "Gene"]
    assert rows == [["GAPDH", "modified\nsite"]]


@pytest.mark.parametrize("content", ["<script>x</script>", "<table></table>",
    "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td></tr></table>",
    "<table><table></table></table>"])
def test_incomplete_html_not_silently_repaired(content):
    with pytest.raises((ValueError, TypeError)):
        parse_table(content)


def test_plotly_payload_without_js_execution():
    content = 'untrusted(); Plotly.newPlot("plot",[{"type":"scatter3d","x":[0,null,1]}],{"title":"source"},{"responsive":true});'
    data = parse_plotly(content)
    assert data["data"][0]["x"] == [0, None, 1]
    assert data["javascript_executed"] is False


@pytest.mark.parametrize("content", ["alert(1)", 'Plotly.newPlot(window.exec(),[],{})',
                                     'Plotly.newPlot("p",{},[])', 'Plotly.newPlot("p",[{"x":NaN}],{})'])
def test_plotly_requires_finite_literal_json(content):
    with pytest.raises(ValueError):
        parse_plotly(content)


def test_shared_catalyst_not_independent_protein_measurements():
    assert GENES_TO_REACTIONS["TKT"] == "VTKL1|VTKL2"
    assert GENES_TO_REACTIONS["BPGM"] == "VDPGM|V23DPGP"
    assert GENES_TO_REACTIONS["PFKL"] == GENES_TO_REACTIONS["PFKM"] == GENES_TO_REACTIONS["PFKP"] == "VPFK"


@pytest.mark.parametrize("gene", ["BLVRB", "SLC4A1", "PCMT1"])
def test_new_mechanisms_are_not_inserted_into_kernel(gene):
    assert "explicit_current" in GENES_TO_REACTIONS[gene]


def test_review_config_keeps_all_calibration_switches_off():
    config = json.loads(CONFIG.read_text())
    for key in ("initial_conditions_changed", "kinetics_changed", "network_changed",
                "optimization_allowed", "proteomic_priors_activated"):
        assert config[key] is False
    assert all(source["palsson_coauthor"] is True for source in config["sources"])


def test_existing_preprint_is_not_a_second_independent_dataset():
    config = json.loads(CONFIG.read_text())
    assert sum(source["id"].startswith("Issaian") for source in config["sources"]) == 1
    assert "same REDS" in next(s for s in config["sources"] if s["id"] == "Nemkov_2024_PFK")["limitations"]
