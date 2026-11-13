"""Read-only, allowlisted registry of VERIFIED reference profiles.

No filesystem browsing, no uploads, no verifier or ODE execution in a request.
A profile is returned only after the proof chain

    receipt (verified, selected id)  ->  campaign manifest (sha256)  ->  release file (sha256)

holds. Missing, corrupt, blocked and unsupported artifacts become explicit
unavailable states; nothing is invented. Absolute local paths are never
returned. Reference profiles are distinct from user datasets and from user
calibrations; ``activation_allowed: false`` in the artifact is a prohibition
that this registry reports and never overrides.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

VIEW_SCHEMA = "airbc.reference_profile_view/1"
SUPPORTED_OBJECTIVES = ("extracellular_first/2",)
PROFILE_ID_PATTERN = re.compile(r"^[a-z0-9_]{1,64}$")

# Allowlist: identifiers map to RELATIVE artifact locations under the project root.
REGISTRY: Dict[str, Dict[str, str]] = {
    "extracellular_release_2026_11_12": {
        "title": "Provisional extracellular reference (historical archived table)",
        "campaign": "output/extracellular_release_2026_11_12",
        "release": "release/provisional_extracellular_reference.json",
        "receipt": "output/extracellular_release_verification_2026_11_12/verification.json",
    },
}

ACTIVATION_POLICY = (
    "Activation is forbidden by the artifact (activation_allowed: false). A user click, even with matching "
    "dataset/engine/contract identities, cannot override it. Preview only."
)


def default_root() -> Path:
    override = os.environ.get("AIRBC_REFERENCE_ROOT")
    return Path(override) if override else Path(__file__).resolve().parents[3]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if root.resolve() not in path.parents:
        raise ValueError("artifact location escapes the project root")
    return path


def _unavailable(profile_id: str, state: str, reason: str, **extra: Any) -> Dict[str, Any]:
    return {"schema": VIEW_SCHEMA, "profile_id": profile_id, "state": state, "reason": reason,
            "available": False, "activation": {"allowed": False, "policy": ACTIVATION_POLICY}, **extra}


def check_profile_id(profile_id: str) -> bool:
    return bool(PROFILE_ID_PATTERN.match(profile_id or "")) and profile_id in REGISTRY


def _species_rows(release: Dict[str, Any]) -> List[Dict[str, Any]]:
    keep = ("species", "compartment", "day", "observed", "predicted", "absolute_error", "working_band",
            "normalized_residual", "unit", "release_channel")
    return [{k: row.get(k) for k in keep} for row in release.get("species_by_date_strict", [])]


def _score_summary(score: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(score, dict):
        return None
    per = score.get("per_channel", {})
    return {
        "objective_version": score.get("version"),
        "utility": score.get("primary"),
        "mean_normalized_rmse": score.get("mean_normalized_rmse"),
        "worst_normalized_rmse": score.get("worst_normalized_rmse"),
        "worst_channel": score.get("worst_channel"),
        "dated_rms": score.get("dated_rms"),
        "scored_channels": score.get("scored_channels"),
        "unscored_channels": score.get("unscored_channels"),
        "channels": {c: {"normalized_rmse": v.get("normalized_rmse"), "zero_band_days": v.get("zero_band_days"),
                         "normalized_residuals": v.get("normalized_residuals"),
                         "absolute_errors": v.get("absolute_errors_mM")} for c, v in per.items()},
        "focus": score.get("focus"),
    }


def _view(profile_id: str, entry: Dict[str, str], release: Dict[str, Any], fingerprints: Dict[str, str],
          receipt: Dict[str, Any]) -> Dict[str, Any]:
    scores = release.get("scores_by_profile", {})
    return {
        "schema": VIEW_SCHEMA,
        "profile_id": profile_id,
        "title": entry["title"],
        "state": "available",
        "available": True,
        "kind": "reference_profile",  # never a user dataset, never a user calibration
        "status": release["status"],
        "objective_version": release.get("release_objective_version"),
        "selected_id": release.get("selected_id"),
        "selected_kind": release.get("selected_kind"),
        "fallback_id": release.get("fallback_id"),
        "improved_over_fallback": release.get("improved_over_fallback"),
        "qualification_context": release.get("qualification_context"),
        "scope": {
            "applicable_dataset": release.get("applicable_dataset"),
            "observations_sha256": release.get("observations_sha256"),
            "cohort": release.get("cohort"),
            "horizon_days": release.get("horizon_days"),
            "geometry": release.get("geometry"),
            "initial_state": release.get("initial_state"),
            "unit_status": release.get("unit_status"),
            "scale": release.get("scale"),
            "J46": release.get("J46"),
        },
        "scores": {p: _score_summary(s) for p, s in scores.items()},
        "focus_protection": release.get("focus_protection"),
        "species_by_date": _species_rows(release),
        "vmax_values": release.get("vmax_values"),
        "limitations": release.get("limitations", []),
        "flags": {
            "activation_allowed": False,
            "default_replacement": False,
            "biologically_validated": False,
            "complete_rbc_calibration": False,
        },
        "activation": {"allowed": False, "policy": ACTIVATION_POLICY,
                       "artifact_policy": release.get("activation_policy")},
        "receipt": {
            "verified": True,
            "receipt_sha256": fingerprints["receipt"],
            "manifest_sha256": fingerprints["manifest"],
            "release_sha256": fingerprints["release"],
            "new_ode_evaluations": receipt.get("new_ode_evaluations"),
            "support_points_checked": receipt.get("support_points_checked"),
            "jacobian_columns_rebuilt": receipt.get("jacobian_columns_rebuilt"),
            "exported_vmax_values_checked": receipt.get("exported_vmax_values_checked"),
            "new_finalists": receipt.get("new_finalists"),
            "new_daily_balances_verified": receipt.get("new_daily_balances_verified"),
            "fallback_qualification": receipt.get("fallback_qualification"),
        },
    }


def load_profile(profile_id: str, root: Optional[Path] = None) -> Dict[str, Any]:
    """Return a verified display view or an explicit unavailable state. Never raises on artifacts."""
    if not check_profile_id(profile_id):
        return _unavailable(profile_id if PROFILE_ID_PATTERN.match(profile_id or "") else "invalid",
                            "unknown_profile", "not in the reference allowlist")
    root = (root or default_root())
    entry = REGISTRY[profile_id]
    try:
        campaign = _inside(root, entry["campaign"])
        receipt_path = _inside(root, entry["receipt"])
        manifest_path = _inside(campaign, "manifest.json")
        release_path = _inside(campaign, entry["release"])
    except ValueError:
        return _unavailable(profile_id, "corrupt", "artifact location is not under the project root")
    if not receipt_path.exists() or not manifest_path.exists() or not release_path.exists():
        return _unavailable(profile_id, "missing",
                            "local scientific artifacts are not present in this installation (they are kept out of Git)")
    try:
        receipt = _read_json(receipt_path)
        manifest = _read_json(manifest_path)
        release = _read_json(release_path)
    except (OSError, ValueError):
        return _unavailable(profile_id, "corrupt", "an artifact is unreadable or not valid JSON")
    if not isinstance(receipt, dict) or not isinstance(manifest, dict) or not isinstance(release, dict):
        return _unavailable(profile_id, "corrupt", "an artifact has an unexpected structure")
    try:
        fingerprints = {"receipt": _sha256(receipt_path), "manifest": _sha256(manifest_path),
                        "release": _sha256(release_path)}
    except OSError:
        return _unavailable(profile_id, "corrupt", "an artifact could not be read")
    if receipt.get("verified") is not True:
        return _unavailable(profile_id, "corrupt", "the verification receipt does not report verified: true")
    if receipt.get("source_manifest_sha256") != fingerprints["manifest"]:
        return _unavailable(profile_id, "corrupt", "receipt does not bind the current campaign manifest")
    if manifest.get(entry["release"]) != fingerprints["release"]:
        return _unavailable(profile_id, "corrupt", "manifest does not bind the current release file")
    status = str(release.get("status", ""))
    if status.startswith("blocked") or release.get("selected") is None and "selected_id" not in release:
        return _unavailable(profile_id, "blocked", "the release is a blocked receipt, not a profile",
                            release_status=status, next_task=release.get("next_task"))
    if release.get("release_objective_version") not in SUPPORTED_OBJECTIVES or status != "provisional_extracellular_reference":
        return _unavailable(profile_id, "unsupported", "release schema or status not supported by this viewer",
                            release_status=status)
    if receipt.get("selected_id") != release.get("selected_id") or receipt.get("release_status") != status:
        return _unavailable(profile_id, "corrupt", "receipt and release disagree on the selected identity")
    if release.get("activation_allowed") is not False:
        return _unavailable(profile_id, "unsupported", "a reference profile must carry activation_allowed: false")
    if any(release.get(k) is not False for k in ("default_replacement", "biologically_validated", "complete_rbc_calibration")):
        return _unavailable(profile_id, "unsupported", "the artifact exceeds the provisional reference scope")
    try:
        return _view(profile_id, entry, release, fingerprints, receipt)
    except (AttributeError, TypeError, ValueError):
        return _unavailable(profile_id, "corrupt", "profile display fields have an unexpected structure")


def list_profiles(root: Optional[Path] = None) -> Dict[str, Any]:
    """Summaries of every allowlisted profile with its real state (empty-safe)."""
    items = []
    for profile_id, entry in REGISTRY.items():
        view = load_profile(profile_id, root)
        items.append({"profile_id": profile_id, "title": entry["title"], "state": view["state"],
                      "reason": view.get("reason"), "status": view.get("status"),
                      "selected_id": view.get("selected_id"),
                      "receipt_sha256": view.get("receipt", {}).get("receipt_sha256"),
                      "activation_allowed": False})
    return {"schema": "airbc.reference_profile_list/1", "profiles": items}
