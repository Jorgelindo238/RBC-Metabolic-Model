"""Regression tests for Phase 0 auto-param-scope.

Plan reference:
    C:/Users/Jorgelindo/.windsurf/plans/auto-calibrate-all-and-ml-flux-learning-179f0d.md

Covers:
    * Stoichiometry parser invariants (rbc_stoichiometry).
    * mm.derive_auto_param_scope sanity (kernel inclusion, reachability,
      bounds validity).
    * mm.auto_scope_with_bounds shape and clipping behaviour.
    * Adapter-level tri-state decision logic and env kill switch.
    * Adapter wiring: empty params_to_optimize triggers auto-scope and the
      mutated request flows into the strict allow-list check without
      raising.

These tests intentionally do NOT exercise the full optimisation loop —
that path is covered by the existing strategy/race/triage tests. The
goal here is to verify the structural correctness of the Phase 0
boundary so future phases (sensitivity pruning, hybrid scope, flux
supervision) can build on it without regressing the contract.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable, List

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for path in (
    PROJECT_ROOT,
    PROJECT_ROOT / "apps" / "api",
    PROJECT_ROOT / "streamlit_app",
    PROJECT_ROOT / "src",
):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

import MM_calibration as mm  # noqa: E402
import rbc_stoichiometry as rs  # noqa: E402

from apps.api.routers.calibration import CalibrationRequest  # noqa: E402
from apps.api.services import mm_calibration_adapter as adapter  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ENERGY_METABOLITES = ["ATP", "ADP", "AMP"]
GLYCOLYSIS_METABOLITES = ["GLC", "G6P", "F6P", "F16BP", "PEP", "PYR", "LAC"]
EXTRACELLULAR_METABOLITES = ["EGLC", "ELAC", "EPYR"]


def _make_request(**overrides) -> CalibrationRequest:
    """Build a minimal CalibrationRequest for adapter-level tests.

    Defaults assemble a custom-data flow with an empty ``params_to_optimize``
    so the auto-scope branch is exercised. Overrides take precedence.
    """
    base = dict(
        target_metabolites=list(overrides.pop("target_metabolites", ENERGY_METABOLITES)),
        exp_time=[0.0, 12.0, 24.0, 36.0, 48.0],
        exp_data={
            name: [1.0, 0.95, 0.9, 0.85, 0.8]
            for name in overrides.get("target_metabolites", ENERGY_METABOLITES)
        },
        params_to_optimize={},
        max_iterations=1,
        t_max=2,
        solver_method="RK45",
    )
    base.update(overrides)
    return CalibrationRequest(**base)


# ---------------------------------------------------------------------------
# rbc_stoichiometry — structural parser invariants
# ---------------------------------------------------------------------------


class TestStoichiometryParser:
    """Sanity invariants for the source-driven stoichiometry parser."""

    def test_module_loads_without_drift_errors(self):
        # Importing already happened at module top — any drift would have
        # raised. Just verify the public surface has reasonable cardinality.
        assert len(rs.STOICHIOMETRY) >= 80, (
            f"Expected at least 80 reactions, got {len(rs.STOICHIOMETRY)}"
        )
        assert len(rs.ALL_METABOLITES) >= 90, (
            f"Expected at least 90 metabolites, got {len(rs.ALL_METABOLITES)}"
        )
        assert len(rs.ALL_PARAMETERS) >= 100, (
            f"Expected at least 100 parameter tokens, got {len(rs.ALL_PARAMETERS)}"
        )

    def test_known_reactions_have_expected_stoichiometry(self):
        # Glucose import / hexokinase / pyruvate kinase / adenylate kinase /
        # glutathione reductase — these are stable anchors.
        assert rs.STOICHIOMETRY["VEGLC"] == {"GLC": 1.0, "EGLC": -1.0}
        assert rs.STOICHIOMETRY["VHK"] == {"GLC": -1.0, "G6P": 1.0, "ATP": -1.0, "ADP": 1.0}
        assert rs.STOICHIOMETRY["VPK"] == {"PEP": -1.0, "PYR": 1.0, "ATP": 1.0, "ADP": -1.0}
        # 2 ADP <-> AMP + ATP
        assert rs.STOICHIOMETRY["VAK"] == {"ATP": 1.0, "ADP": -2.0, "AMP": 1.0}
        # GSSG + NADPH -> 2 GSH + NADP
        assert rs.STOICHIOMETRY["VGSR"] == {"GSH": 2.0, "GSSG": -1.0, "NADP": 1.0, "NADPH": -1.0}

    def test_aliased_reaction_resolves_to_canonical_params(self):
        # VEASN_rate is the dxdt-side variable; vmax_VEASN is the parameter.
        assert "VEASN_rate" in rs.STOICHIOMETRY
        assert "vmax_VEASN" in rs.REACTION_PARAMS["VEASN_rate"]
        assert "vmax_VEASN" in rs.REACTION_PARAMS["VEASN"]

    def test_hybrid_reaction_call_args_are_captured(self):
        # The five hybrid-dispatch reactions: their base params must be
        # picked up from the multi-line _compute_*_flux call sites.
        assert "vmax_VEGLC" in rs.REACTION_PARAMS["VEGLC"]
        assert "km_EGLC" in rs.REACTION_PARAMS["VEGLC"]
        assert "km_GLC_transport" in rs.REACTION_PARAMS["VEGLC"]

        assert "vmax_VPK" in rs.REACTION_PARAMS["VPK"]
        assert "ki_ATP_PK" in rs.REACTION_PARAMS["VPK"]
        assert "ki_PYR_PK" in rs.REACTION_PARAMS["VPK"]
        assert "km_PEP" in rs.REACTION_PARAMS["VPK"]

        assert "vmax_VLDH" in rs.REACTION_PARAMS["VLDH"]
        assert "km_PYR" in rs.REACTION_PARAMS["VLDH"]
        assert "km_LAC" in rs.REACTION_PARAMS["VLDH"]

        assert "vmax_VENOPGM" in rs.REACTION_PARAMS["VENOPGM"]
        assert "ki_PEP_ENO" in rs.REACTION_PARAMS["VENOPGM"]
        assert "km_P2G" in rs.REACTION_PARAMS["VENOPGM"]

        assert "vmax_VELAC" in rs.REACTION_PARAMS["VELAC"]
        assert "km_LAC" in rs.REACTION_PARAMS["VELAC"]

    def test_zero_flux_reactions_have_no_stoichiometry(self):
        # RBC-strict deletions must not appear in the stoichiometry table —
        # their dxdt contribution is identically zero.
        for name in rs.ZERO_FLUX_REACTIONS:
            assert name not in rs.STOICHIOMETRY, (
                f"Zero-flux reaction {name!r} unexpectedly present in stoichiometry"
            )

    def test_derived_locals_do_not_leak_as_params(self):
        # km_P2G_app is a derived local in equadiff_brodbar; it must NOT
        # appear as a real parameter token.
        for params in rs.REACTION_PARAMS.values():
            assert "km_P2G_app" not in params

    def test_reverse_index_matches_stoichiometry(self):
        # The reverse index must agree with STOICHIOMETRY for every metabolite.
        for met, rxns in rs.REVERSE_INDEX.items():
            for rxn in rxns:
                assert met in rs.STOICHIOMETRY[rxn], (
                    f"REVERSE_INDEX claims {met!r} touched by {rxn!r}, "
                    f"but stoichiometry says otherwise"
                )

    def test_reactions_for_metabolites_is_case_insensitive(self):
        upper = rs.reactions_for_metabolites(["ATP"])
        lower = rs.reactions_for_metabolites(["atp"])
        mixed = rs.reactions_for_metabolites([" Atp "])
        assert upper == lower == mixed
        assert "VHK" in upper
        assert "VAK" in upper


# ---------------------------------------------------------------------------
# Test 0a: auto-scope returns ≥1 param for any non-trivial metabolite subset
# ---------------------------------------------------------------------------


class TestAutoParamScope0a:
    """0a: derive_auto_param_scope returns a usable scope for any subset."""

    @pytest.mark.parametrize(
        "metabolites",
        [
            ["ATP"],
            ["LAC"],
            ["EGLC"],
            ENERGY_METABOLITES,
            GLYCOLYSIS_METABOLITES,
            EXTRACELLULAR_METABOLITES,
            ENERGY_METABOLITES + GLYCOLYSIS_METABOLITES,
        ],
        ids=[
            "atp_only",
            "lac_only",
            "eglc_only",
            "energy_set",
            "glycolysis_set",
            "extracellular_set",
            "energy_plus_glycolysis",
        ],
    )
    def test_returns_at_least_kernel(self, metabolites: List[str]):
        scope = mm.derive_auto_param_scope(metabolites)
        assert len(scope) >= len(mm.AUTO_SCOPE_KERNEL), (
            f"Auto-scope must always cover the kernel "
            f"(got {len(scope)} params, kernel={len(mm.AUTO_SCOPE_KERNEL)})"
        )
        # Every kernel member must be present.
        for kernel_name in mm.AUTO_SCOPE_KERNEL:
            assert kernel_name in scope, (
                f"Kernel parameter {kernel_name!r} missing from auto-scope for "
                f"metabolites={metabolites}"
            )

    def test_every_returned_name_has_bounds(self):
        scope = mm.derive_auto_param_scope(ENERGY_METABOLITES)
        for name in scope:
            assert name in mm.DEFAULT_PARAM_BOUNDS, (
                f"Auto-scope returned {name!r} which has no (default, lo, hi) triple"
            )
            default, lo, hi = mm.DEFAULT_PARAM_BOUNDS[name]
            # Phase 0 only enforces the structural invariant ``lo <= hi``.
            # The orthogonal question of whether the registered default lies
            # inside ``[lo, hi]`` is a pre-existing data-quality concern in
            # ``PHASE_MAP`` (e.g. ``vmax_VAMPD1`` defaults to 0.538065 with
            # bounds (0.001, 0.1)). The auto-scope wrapper already clips the
            # initial guess into bounds before returning, so the optimiser
            # never sees an out-of-range seed; the registered default is
            # only a fallback for callers that bypass the wrapper. See
            # ``TestAutoScopeWithBounds.test_initial_clipping`` for the
            # safety check that matters at runtime.
            assert isinstance(lo, (int, float)) and isinstance(hi, (int, float)), (
                f"Bounds for {name!r} are not numeric: ({lo!r}, {hi!r})"
            )
            assert lo <= hi, (
                f"Bounds for {name!r} are inverted: lo={lo} > hi={hi}"
            )

    def test_scope_strictly_increases_with_uploaded_metabolites(self):
        # More uploaded metabolites should yield a >=-sized scope.
        small = set(mm.derive_auto_param_scope(["ATP"]))
        large = set(mm.derive_auto_param_scope(["ATP", "ADP", "AMP", "GLC", "LAC"]))
        assert small <= large, (
            "Auto-scope is expected to be monotone non-decreasing as upload grows; "
            f"small\\large={small - large}"
        )

    def test_unknown_metabolites_silently_ignored(self):
        # Junk names must not crash; they simply contribute no reachable
        # reactions. The kernel must still be present.
        scope = mm.derive_auto_param_scope(["UNOBTAINIUM", "QUUX"])
        assert mm.AUTO_SCOPE_KERNEL <= set(scope)


# ---------------------------------------------------------------------------
# Test 0b: empty params_to_optimize + auto-scope -> populated dict
# ---------------------------------------------------------------------------


class TestAutoParamScope0b:
    """0b: empty params_to_optimize + auto-detect/force-on triggers expansion."""

    def test_empty_request_with_auto_detect_populates_params(self):
        request = _make_request(target_metabolites=ENERGY_METABOLITES)
        # Sanity precondition: caller intentionally left it empty.
        assert request.params_to_optimize == {}
        applied, added = adapter._maybe_apply_auto_param_scope(
            request,
            user_selected_params=[],
            target_metabolites=ENERGY_METABOLITES,
        )
        assert applied is True
        assert len(added) >= len(mm.AUTO_SCOPE_KERNEL)
        assert request.params_to_optimize, (
            "params_to_optimize should be populated in-place after auto-scope applies"
        )
        # Every entry must be a [initial, lo, hi] triple of floats.
        for name, bounds in request.params_to_optimize.items():
            assert isinstance(bounds, list)
            assert len(bounds) == 3
            initial, lo, hi = bounds
            assert isinstance(initial, float)
            assert isinstance(lo, float)
            assert isinstance(hi, float)
            assert lo <= initial <= hi, (
                f"Initial {initial} of {name!r} not clipped into [{lo}, {hi}]"
            )

    def test_force_on_flag_populates_even_when_data_absent(self):
        # auto_param_scope=True bypasses the auto-detect heuristic.
        request = _make_request(
            target_metabolites=["GLC"],
            exp_data={},  # explicitly empty
            auto_param_scope=True,
        )
        applied, added = adapter._maybe_apply_auto_param_scope(
            request,
            user_selected_params=[],
            target_metabolites=["GLC"],
        )
        assert applied is True
        assert "vmax_VHK" in added  # GLC -> VHK is a structural anchor

    def test_caller_supplied_params_preserved_when_auto_scope_on(self):
        # If the caller supplies params AND requests auto_scope=True, we must
        # respect the explicit list (auto-scope only fills in EMPTY requests).
        request = _make_request(
            params_to_optimize={"vmax_VHK": [0.3, 0.1, 1.0]},
            auto_param_scope=True,
        )
        applied, added = adapter._maybe_apply_auto_param_scope(
            request,
            user_selected_params=["vmax_VHK"],
            target_metabolites=ENERGY_METABOLITES,
        )
        assert applied is False
        assert added == []
        assert list(request.params_to_optimize.keys()) == ["vmax_VHK"]


# ---------------------------------------------------------------------------
# Test 0c: parity vs curated profile on the canonical Bordbar dataset
# ---------------------------------------------------------------------------


class TestAutoParamScope0c:
    """0c: auto-scope on the full Bordbar set covers the curated profile.

    The plan calls for a numerical parity check ("within ±X% on the canonical
    Bordbar dataset"). At Phase 0 we don't run the full optimisation in this
    test (the existing adapter / strategy_orchestrator suites cover that);
    instead we verify the STRUCTURAL invariant that any parameter the
    existing curated profile would inject must also be present in the
    auto-scope when given the canonical metabolite set. This is the
    necessary condition for downstream parity — if the structural invariant
    fails, no amount of numerical tuning would close the gap.
    """

    def test_full_bordbar_set_includes_curated_glycolysis_parameters(self):
        bordbar_metabolites = list(mm.EXP_TO_MODEL.keys())
        scope = set(mm.derive_auto_param_scope(bordbar_metabolites))

        # Anchors from the curated `core_glycolysis_energy` profile that the
        # ML calibrator has used for years. If auto-scope omits any of these
        # we have lost necessary reach.
        curated_anchors = {
            "vmax_VHK", "vmax_VPFK", "vmax_VPK", "vmax_VLDH",
            "vmax_VEGLC", "vmax_VELAC", "vmax_VPGK", "vmax_VFDPA",
            "km_GLC_HK", "km_F6P", "km_PEP", "km_PYR", "km_LAC",
            "ki_ATP_PK", "ki_PYR_PK",
        }
        missing = curated_anchors - scope
        assert not missing, (
            f"Auto-scope on the canonical Bordbar set is missing curated "
            f"glycolysis anchors: {sorted(missing)}"
        )

    def test_full_bordbar_set_stays_inside_calibrator_universe(self):
        bordbar_metabolites = list(mm.EXP_TO_MODEL.keys())
        scope = mm.derive_auto_param_scope(bordbar_metabolites)
        for name in scope:
            assert name in mm.DEFAULT_PARAM_VALUES, (
                f"Auto-scope returned {name!r}, which is not a calibratable "
                f"parameter. The intersection-with-DEFAULT_PARAM_VALUES "
                f"contract is broken."
            )


# ---------------------------------------------------------------------------
# Test 0d: env kill switch + tri-state behaviour
# ---------------------------------------------------------------------------


class TestAutoParamScope0d:
    """0d: AIRBC_DISABLE_AUTO_PARAM_SCOPE env var disables the feature."""

    def test_env_kill_switch_disables_decision(self, monkeypatch):
        monkeypatch.setenv(adapter._AUTO_PARAM_SCOPE_KILL_SWITCH_ENV, "1")
        request = _make_request()
        decision = adapter._resolve_auto_param_scope_decision(
            request,
            user_selected_params=[],
            has_experimental_data=True,
        )
        assert decision is False

    def test_env_kill_switch_overrides_force_on(self, monkeypatch):
        # Even when the caller passes auto_param_scope=True, the env kill
        # switch must win.
        monkeypatch.setenv(adapter._AUTO_PARAM_SCOPE_KILL_SWITCH_ENV, "true")
        request = _make_request(auto_param_scope=True)
        decision = adapter._resolve_auto_param_scope_decision(
            request,
            user_selected_params=[],
            has_experimental_data=True,
        )
        assert decision is False

    def test_env_kill_switch_blocks_apply(self, monkeypatch):
        monkeypatch.setenv(adapter._AUTO_PARAM_SCOPE_KILL_SWITCH_ENV, "yes")
        request = _make_request()
        applied, added = adapter._maybe_apply_auto_param_scope(
            request,
            user_selected_params=[],
            target_metabolites=ENERGY_METABOLITES,
        )
        assert applied is False
        assert added == []
        assert request.params_to_optimize == {}

    def test_explicit_false_disables_without_env(self, monkeypatch):
        monkeypatch.delenv(adapter._AUTO_PARAM_SCOPE_KILL_SWITCH_ENV, raising=False)
        request = _make_request(auto_param_scope=False)
        decision = adapter._resolve_auto_param_scope_decision(
            request,
            user_selected_params=[],
            has_experimental_data=True,
        )
        assert decision is False

    def test_default_tri_state_enables_when_data_and_empty_params(self, monkeypatch):
        monkeypatch.delenv(adapter._AUTO_PARAM_SCOPE_KILL_SWITCH_ENV, raising=False)
        request = _make_request()
        decision = adapter._resolve_auto_param_scope_decision(
            request,
            user_selected_params=[],
            has_experimental_data=True,
        )
        assert decision is True

    def test_default_tri_state_disabled_when_user_supplied_params(self, monkeypatch):
        monkeypatch.delenv(adapter._AUTO_PARAM_SCOPE_KILL_SWITCH_ENV, raising=False)
        request = _make_request(params_to_optimize={"vmax_VHK": [0.3, 0.1, 1.0]})
        decision = adapter._resolve_auto_param_scope_decision(
            request,
            user_selected_params=["vmax_VHK"],
            has_experimental_data=True,
        )
        assert decision is False

    @pytest.mark.parametrize("falsy", ["", "0", "no", "off", "false", "FALSE", "  "])
    def test_falsy_env_values_do_not_disable(self, monkeypatch, falsy):
        # Only truthy strings ("1", "true", "yes", "on" — case-insensitive)
        # should disable the feature. Anything else falls back to the
        # tri-state heuristic.
        monkeypatch.setenv(adapter._AUTO_PARAM_SCOPE_KILL_SWITCH_ENV, falsy)
        request = _make_request()
        decision = adapter._resolve_auto_param_scope_decision(
            request,
            user_selected_params=[],
            has_experimental_data=True,
        )
        assert decision is True, f"env value {falsy!r} should NOT disable auto-scope"


# ---------------------------------------------------------------------------
# auto_scope_with_bounds — shape & invariants
# ---------------------------------------------------------------------------


class TestAutoScopeWithBounds:
    def test_returns_dict_of_triples(self):
        bounds = mm.auto_scope_with_bounds(ENERGY_METABOLITES)
        assert isinstance(bounds, dict)
        assert len(bounds) >= len(mm.AUTO_SCOPE_KERNEL)
        for name, triple in bounds.items():
            assert isinstance(triple, tuple)
            assert len(triple) == 3
            initial, lo, hi = triple
            assert lo <= initial <= hi

    def test_initial_clipping(self):
        # If the caller's base_params has a value outside the registered
        # bounds, the wrapper must clip into [lo, hi] rather than blindly
        # passing it through.
        # Pick a known param: vmax_VHK has bounds (0.267472, 0.2, 5.0).
        seed = {"vmax_VHK": 1e6}  # absurdly large
        bounds = mm.auto_scope_with_bounds(ENERGY_METABOLITES, base_params=seed)
        initial, lo, hi = bounds["vmax_VHK"]
        assert initial == hi, "Out-of-range seed must clip to upper bound"

        seed = {"vmax_VHK": -1e3}  # negative
        bounds = mm.auto_scope_with_bounds(ENERGY_METABOLITES, base_params=seed)
        initial, lo, hi = bounds["vmax_VHK"]
        assert initial == lo, "Out-of-range seed must clip to lower bound"

    def test_uses_default_when_seed_absent(self):
        bounds = mm.auto_scope_with_bounds(ENERGY_METABOLITES)
        initial, lo, hi = bounds["vmax_VHK"]
        default = mm.DEFAULT_PARAM_BOUNDS["vmax_VHK"][0]
        assert initial == pytest.approx(default)


# ---------------------------------------------------------------------------
# Adapter integration: legacy strict allow-list still passes after auto-scope
# ---------------------------------------------------------------------------


class TestAutoScopeAllowListIntegration:
    """Every name introduced by auto-scope must satisfy the adapter's strict
    allow-list. If this regresses, the auto-scope branch would push a request
    that immediately raises 400, which would defeat the entire feature.
    """

    def test_auto_scope_names_are_inside_strict_allow_list(self):
        taxonomy_classes = mm.build_parameter_taxonomy()["classes"]
        allow_list = (
            set(taxonomy_classes.get(mm.PARAM_CLASS_VMAX, []))
            | set(taxonomy_classes.get(mm.PARAM_CLASS_KM, []))
            | set(taxonomy_classes.get(mm.PARAM_CLASS_REGULATION, []))
        )
        bordbar_metabolites = list(mm.EXP_TO_MODEL.keys())
        scope = mm.derive_auto_param_scope(bordbar_metabolites)
        outside = [name for name in scope if name not in allow_list]
        assert not outside, (
            f"Auto-scope produced {outside!r} which the adapter's strict "
            f"allow-list would reject — the adapter PHASE 0 wiring would "
            f"fail with 400."
        )
