"""Read-only reference-profile registry and API. Written, NOT executed by the author.

All artifacts are synthetic, created in tmp_path only (test fixtures are never
written to output/ and never shipped). No ODE, no verifier script is run.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for path in (PROJECT_ROOT, PROJECT_ROOT / "apps" / "api", PROJECT_ROOT / "streamlit_app", PROJECT_ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from fastapi import HTTPException  # noqa: E402

from apps.api.routers import calibration as router_module  # noqa: E402
from apps.api.services import reference_profiles as registry  # noqa: E402

PID = "extracellular_release_2026_11_12"
ENTRY = registry.REGISTRY[PID]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def release_doc(**override):
    doc = {
        "status": "provisional_extracellular_reference",
        "release_objective_version": "extracellular_first/2",
        "selected_id": "working_centre", "selected_kind": "fallback", "fallback_id": "working_centre",
        "improved_over_fallback": False, "qualification_context": "historical sealed receipt",
        "applicable_dataset": "only the archived curated table; not transferable to user datasets",
        "observations_sha256": "obs", "cohort": "single curated table; donor unknown",
        "unit_status": {"status": "assumed_mM_historical_model_convention", "evidence": "no unit field"},
        "scale": "working band", "geometry": "H = 0.58 borrowed", "initial_state": "55 measured J1 values",
        "horizon_days": [1, 15], "J46": "not used",
        "scores_by_profile": {"strict": {"version": "extracellular_first/2", "primary": 0.0,
                                         "mean_normalized_rmse": 44.7, "worst_normalized_rmse": 633.1,
                                         "worst_channel": "EINO", "per_channel": {}, "focus": {"EGLC": {}}}},
        "species_by_date_strict": [{"species": "EGLC", "compartment": "extracellular", "day": 4, "observed": 1.0,
                                    "predicted": 1.1, "absolute_error": 0.1, "working_band": 0.5,
                                    "normalized_residual": 0.2, "unit": "mM (assumed_mM_historical_model_convention)",
                                    "release_channel": True}],
        "vmax_values": {"vmax_VHK": 0.1}, "limitations": ["ATP/ADP absolute J15 targets NOT met"],
        "activation_allowed": False, "activation_policy": "forbidden", "default_replacement": False,
        "biologically_validated": False, "complete_rbc_calibration": False,
    }
    doc.update(override)
    return doc


def build(root: Path, release=None, receipt_override=None, manifest_override=None):
    campaign = root / ENTRY["campaign"]
    release_path = campaign / ENTRY["release"]
    release_path.parent.mkdir(parents=True, exist_ok=True)
    release_path.write_text(json.dumps(release or release_doc()), encoding="utf-8")
    manifest = {ENTRY["release"]: sha(release_path)}
    manifest.update(manifest_override or {})
    (campaign / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    receipt_path = root / ENTRY["receipt"]
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    rel = release or release_doc()
    receipt = {"verified": True, "source_manifest_sha256": sha(campaign / "manifest.json"),
               "selected_id": rel.get("selected_id"), "release_status": rel.get("status"),
               "new_ode_evaluations": 38, "support_points_checked": 1162575, "jacobian_columns_rebuilt": 56,
               "exported_vmax_values_checked": 17, "new_finalists": 0, "new_daily_balances_verified": 0}
    receipt.update(receipt_override or {})
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    return campaign, release_path, receipt_path


def test_verified_chain_returns_a_scoped_read_only_view_without_paths(tmp_path):
    build(tmp_path)
    view = registry.load_profile(PID, tmp_path)
    assert view["state"] == "available" and view["available"] is True and view["kind"] == "reference_profile"
    assert view["scope"]["unit_status"]["status"] == "assumed_mM_historical_model_convention"
    assert view["scope"]["horizon_days"] == [1, 15] and "not transferable" in view["scope"]["applicable_dataset"]
    assert view["activation"]["allowed"] is False and view["flags"]["activation_allowed"] is False
    assert view["flags"]["biologically_validated"] is False
    assert view["receipt"]["receipt_sha256"] == sha(tmp_path / ENTRY["receipt"])
    assert view["species_by_date"][0]["species"] == "EGLC"
    text = json.dumps(view)
    assert str(tmp_path) not in text and str(tmp_path.resolve()) not in text and "output/" not in text


def test_missing_local_archive_is_an_explicit_empty_state(tmp_path):
    view = registry.load_profile(PID, tmp_path)
    assert view["state"] == "missing" and view["available"] is False
    listing = registry.list_profiles(tmp_path)
    assert listing["profiles"][0]["state"] == "missing" and listing["profiles"][0]["activation_allowed"] is False


def test_release_tampered_after_sealing_is_corrupt(tmp_path):
    _, release_path, _ = build(tmp_path)
    doc = json.loads(release_path.read_text(encoding="utf-8"))
    doc["vmax_values"]["vmax_VHK"] = 0.2
    release_path.write_text(json.dumps(doc), encoding="utf-8")
    assert registry.load_profile(PID, tmp_path)["state"] == "corrupt"


def test_manifest_tampered_after_receipt_is_corrupt(tmp_path):
    campaign, _, _ = build(tmp_path)
    manifest = json.loads((campaign / "manifest.json").read_text(encoding="utf-8"))
    manifest["extra"] = "x"
    (campaign / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert registry.load_profile(PID, tmp_path)["state"] == "corrupt"


def test_unverified_receipt_or_identity_mismatch_is_corrupt(tmp_path):
    build(tmp_path, receipt_override={"verified": False})
    assert registry.load_profile(PID, tmp_path)["state"] == "corrupt"
    build(tmp_path, receipt_override={"selected_id": "candidate35"})
    assert registry.load_profile(PID, tmp_path)["state"] == "corrupt"


def test_unreadable_json_is_corrupt(tmp_path):
    _, release_path, _ = build(tmp_path)
    (tmp_path / ENTRY["receipt"]).write_text("{not json", encoding="utf-8")
    assert registry.load_profile(PID, tmp_path)["state"] == "corrupt"


def test_blocked_release_is_not_a_profile(tmp_path):
    blocked = {"status": "blocked_source_drift", "selected": None, "reason": "drift", "activation_allowed": False,
               "next_task": "requalify the fallbacks"}
    build(tmp_path, release=blocked)
    view = registry.load_profile(PID, tmp_path)
    assert view["state"] == "blocked" and view["available"] is False and view["next_task"] == "requalify the fallbacks"


def test_unsupported_objective_or_activatable_release_is_refused(tmp_path):
    build(tmp_path, release=release_doc(release_objective_version="extracellular_first/1"))
    assert registry.load_profile(PID, tmp_path)["state"] == "unsupported"
    build(tmp_path, release=release_doc(activation_allowed=True))
    assert registry.load_profile(PID, tmp_path)["state"] == "unsupported"


@pytest.mark.parametrize("bad", ["../etc/passwd", "..%2F..%2Fsecrets", "/abs/path", "C:\\x", "", "EXTRACELLULAR",
                                 "unknown_profile"])
def test_allowlist_rejects_paths_and_unknown_ids(tmp_path, bad):
    build(tmp_path)
    assert registry.check_profile_id(bad) is False
    view = registry.load_profile(bad, tmp_path)
    assert view["state"] == "unknown_profile" and view["available"] is False
    if bad and not registry.PROFILE_ID_PATTERN.match(bad):
        assert bad not in json.dumps(view)  # path-like input is never echoed back


def test_router_lists_and_returns_profiles_and_404s_unknown_ids(tmp_path, monkeypatch):
    build(tmp_path)
    monkeypatch.setenv("AIRBC_REFERENCE_ROOT", str(tmp_path))
    listing = asyncio.run(router_module.get_reference_profiles())
    assert listing["profiles"][0]["state"] == "available"
    view = asyncio.run(router_module.get_reference_profile(PID))
    assert view["available"] is True and view["activation"]["allowed"] is False
    with pytest.raises(HTTPException) as error:
        asyncio.run(router_module.get_reference_profile("../output"))
    assert error.value.status_code == 404 and "output" not in json.dumps(error.value.detail)


def test_clean_installation_without_artifacts_answers_empty_not_error(tmp_path, monkeypatch):
    monkeypatch.setenv("AIRBC_REFERENCE_ROOT", str(tmp_path))
    view = asyncio.run(router_module.get_reference_profile(PID))
    assert view["state"] == "missing" and "Git" in view["reason"]


def test_registry_module_runs_nothing():
    import ast
    tree = ast.parse((PROJECT_ROOT / "apps/api/services/reference_profiles.py").read_text(encoding="utf-8"))
    modules = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    modules |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert modules <= {"__future__", "hashlib", "json", "os", "re", "pathlib", "typing"}


@pytest.mark.parametrize('malformed', [{'scores_by_profile': []}, {'species_by_date_strict': ['bad-row']}])
def test_valid_proof_chain_does_not_allow_malformed_view_fields(tmp_path, malformed):
    build(tmp_path, release=release_doc(**malformed))
    assert registry.load_profile(PID, tmp_path)['state'] == 'corrupt'


@pytest.mark.parametrize('flag', ['default_replacement', 'biologically_validated', 'complete_rbc_calibration'])
def test_provisional_scope_cannot_be_silently_overstated(tmp_path, flag):
    build(tmp_path, release=release_doc(**{flag: True}))
    assert registry.load_profile(PID, tmp_path)['state'] == 'unsupported'
