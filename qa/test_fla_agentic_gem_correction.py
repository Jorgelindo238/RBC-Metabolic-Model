import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fla_agentic_gem_correction import GemCorrectionRHS, MODES
from fla_joint_calibration import JointRHS
from rbc_gem_audit import pool_mapping, project_gem
from rbc_glut_only_transport import equadiff_glut_only


KINETICS = {"conductance": .026, "km_i": 3.49, "km_e": 23.5}
PARAMETERS = {"vmax_VOPLAH": .15}
H, THRESHOLD = .63, .002


def state():
    x = np.ones(114)
    x[-1] = 7.2
    return x


def adapter(mode="native", backend="joint", parameters=PARAMETERS):
    return GemCorrectionRHS(parameters, KINETICS, mode=mode, backend=backend,
                            hematocrit=H, threshold=THRESHOLD)


def original(x, audit):
    return equadiff_glut_only(1., x, custom_params=PARAMETERS, glucose_kinetics=KINETICS,
                             hematocrit=H, reaction_availability_threshold=THRESHOLD,
                             numerical_audit=audit)


@pytest.mark.parametrize("low", [0., .0003, .5])
@pytest.mark.parametrize("backend", ["joint", "full"])
def test_exact_native_rollback(low, backend):
    rhs, x = adapter(backend=backend), state()
    x[rhs.names.index("ATP")] = x[rhs.names.index("O2")] = low
    if backend == "joint":
        native = JointRHS(PARAMETERS, KINETICS, hematocrit=H, threshold=THRESHOLD)
        assert rhs.matrix is native.matrix
        np.testing.assert_array_equal(rhs.jacobian_sparsity, native.jacobian_sparsity)
        expected_d, expected_rates = native(1., x), native.rates(1., x)
    else:
        audit = {}
        expected_d = original(x, audit)
        expected_rates = [[audit[key][r] for r in rhs.reactions]
                          for key in ("raw_fluxes", "effective_fluxes", "availability_factors")]
    for actual, expected in zip((rhs(1., x), *rhs.rates(1., x)), (expected_d, *expected_rates)):
        assert actual.tobytes() == np.asarray(expected).tobytes()


@pytest.mark.parametrize("mode", MODES)
def test_only_declared_columns_change_and_raw_laws_are_identical(mode):
    native, corrected, x = adapter(), adapter(mode), state()
    assert corrected.names == native.names and corrected.reactions == native.reactions
    assert corrected.parameters == native.parameters and corrected.kinetics == native.kinetics
    changed = np.flatnonzero(np.any(corrected.matrix != native.matrix, axis=0))
    assert {native.reactions[j] for j in changed} == set(MODES[mode])
    assert not corrected.matrix.flags.writeable
    for pool in ("ATP", "O2", "GSSG"):
        x[native.names.index(pool)] = .0003
    raw, executed, _ = corrected.rates(1., x)
    raw_native, executed_native, _ = native.rates(1., x)
    np.testing.assert_array_equal(raw, raw_native)
    unchanged = np.setdiff1d(np.arange(len(raw)), changed)
    np.testing.assert_array_equal(executed[unchanged], executed_native[unchanged])
    assert executed[native.reactions.index("VOPLAH")] > 0.
    np.testing.assert_array_equal(corrected(1., x), np.r_[corrected.matrix @ executed, 0.])


def test_pinned_projection_and_phase_amounts():
    path = ROOT / "output/rbc_gem_network_audit_2026_10_06/github/1.3.0/model/RBC-GEM.json"
    model = json.loads(path.read_bytes())
    inverse = {v: k for k, v in pool_mapping(model).items()}
    reactions = {r["id"]: r for r in model["reactions"]}
    rhs = adapter("redox_gssg_abc")
    for local, gem, scale in [("VH2O2", "CAT", .5), ("VXAO", "XAO2", 1.),
                              ("VXAO2", "XAO", 1.), ("VEGSSG", "GTHOXABCte", 1.)]:
        j = rhs.reactions.index(local)
        projection, missing, _ = project_gem(reactions[gem], inverse)
        assert not missing and rhs.rate_volumes[j] == H
        expected = [H * scale * projection.get(pool, 0.) for pool in rhs.names]
        np.testing.assert_allclose(rhs.volumes * rhs.matrix[:, j], expected, atol=1e-15, rtol=0.)
    for local, pair in [("VEGSSG", ("GSSG", "EGSSG")), ("VEGSSG", ("ATP", "ADP"))]:
        j = rhs.reactions.index(local)
        indices = [rhs.names.index(p) for p in pair]
        assert abs((rhs.volumes * rhs.matrix[:, j])[indices].sum()) < 1e-15


@pytest.mark.parametrize("backend", ["joint", "full"])
@pytest.mark.parametrize("fraction", [0., .2, 1., 2.])
def test_o2_and_atp_gate_entire_forward_reactions(backend, fraction):
    rhs, x = adapter("redox_gssg_abc", backend), state()
    for pool in ("ATP", "O2"):
        x[rhs.names.index(pool)] = fraction * THRESHOLD
    raw, executed, factors = rhs.rates(1., x)
    for r in ("VXAO", "VXAO2", "VEGSSG"):
        j = rhs.reactions.index(r)
        assert raw[j] > 0 and factors[j] == pytest.approx(min(1., fraction))
        assert executed[j] == pytest.approx(raw[j] * min(1., fraction))
    assert factors[rhs.reactions.index("VH2O2")] == 1.


def test_sparse_pattern_covers_added_dependencies_and_full_backend_matches():
    joint, full, x = adapter("redox_gssg_abc"), adapter("redox_gssg_abc", "full"), state()
    for pool in ("ATP", "O2", "GSSG", "H2O2"):
        x[joint.names.index(pool)] = .5 * THRESHOLD
    for fast, original_rate in zip((*joint.rates(1., x), joint(1., x)),
                                   (*full.rates(1., x), full(1., x))):
        np.testing.assert_allclose(fast, original_rate, atol=1e-12, rtol=1e-12)
    derivative = joint(1., x)
    for i in range(len(x)):
        perturbed = x.copy()
        perturbed[i] += 1e-7
        changed = np.abs(joint(1., perturbed) - derivative) > 1e-12
        assert np.all(joint.jacobian_sparsity[changed, i]), joint.names[i] if i < 113 else "pH"


@pytest.mark.parametrize("backend", ["joint", "full"])
def test_negative_forward_rate_cannot_turn_abc_into_an_atp_source(backend):
    rhs = adapter("redox_gssg_abc", backend, {"vmax_VEGSSG": -.01})
    with pytest.raises(ValueError, match="irreversible"):
        rhs.rates(1., state())


@pytest.mark.parametrize("options", [{"mode": "rbc_gem_core"}, {"backend": "other"}, {"threshold": 0.}])
def test_reject_invalid_options(options):
    with pytest.raises(ValueError):
        GemCorrectionRHS(PARAMETERS, KINETICS, **options)
