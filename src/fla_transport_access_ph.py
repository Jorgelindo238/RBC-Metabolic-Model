"""Observation-to-activity and acid-equivalent contracts, outside the ODE path."""

from dataclasses import dataclass
import math
from numbers import Real


def finite(value, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError("finite numeric input required")
    if positive and value <= 0:
        raise ValueError("positive input required")
    return float(value)


def fraction(value, *, positive=False):
    value = finite(value, positive=positive)
    if value < 0 or value > 1:
        raise ValueError("fraction outside [0, 1]")
    return value


@dataclass(frozen=True)
class PoolAccess:
    # Recovery describes an uncorrected observation only; never correct it twice.
    free_fraction: float
    aqueous_fraction: float
    recovery_fraction: float
    activity_coefficient: float

    def __post_init__(self):
        fraction(self.free_fraction)
        fraction(self.aqueous_fraction, positive=True)
        fraction(self.recovery_fraction, positive=True)
        finite(self.activity_coefficient, positive=True)

    @property
    def scale(self):
        return (self.activity_coefficient * self.free_fraction
                / (self.aqueous_fraction * self.recovery_fraction))

    def activity_mM(self, observed_mM):
        observed = finite(observed_mM)
        if observed < 0:
            raise ValueError("negative concentration")
        return observed * self.scale


def export_bound(li, le, accessibility_ratio):
    """Positive-lactate domain: export iff delta_pH < this conditional bound."""
    return math.log10(finite(li, positive=True)) - math.log10(finite(le, positive=True)) + math.log10(finite(accessibility_ratio, positive=True))


def lactate_drive(li, le, *, accessibility_ratio, delta_pH):
    li, le = finite(li), finite(le)
    if min(li, le) < 0:
        raise ValueError("negative lactate pool")
    rho = finite(accessibility_ratio, positive=True)
    delta = finite(delta_pH)
    if abs(delta) > 14:
        raise ValueError("pH difference outside diagnostic domain")
    # Divide by the positive extracellular accessibility and intracellular H activity.
    return rho * li - le * 10 ** delta


def buffered_rates(q_export_bag, *, hct, beta_i, beta_e, source_i_bag, source_e_bag):
    """Local fixed-geometry capacity balance; all acid extents per L bag/day.

    This excludes double-counting explicit carbonate with effective total beta.
    Sources must include any separately modeled acid/base and boundary processes.
    """
    h = fraction(hct, positive=True)
    if h == 1:
        raise ValueError("nonzero extracellular volume required")
    bi, be = finite(beta_i, positive=True), finite(beta_e, positive=True)
    q, si, se = map(finite, (q_export_bag, source_i_bag, source_e_bag))
    return -(si - q) / (h * bi), -(se + q) / ((1 - h) * be)


def clamped_reservoirs(q_export_bag, *, source_i_bag, source_e_bag):
    q, si, se = map(finite, (q_export_bag, source_i_bag, source_e_bag))
    return q - si, -q - se


def readiness(contract):
    """Local prerequisite inventory, not a replacement for biological readiness."""
    missing = []
    if contract["concentration_basis"]["source_processing_verified"] is not True:
        missing.append("source_processing_and_observation_denominators")
    for pool in ("GLC", "EGLC", "LAC", "ELAC"):
        record = contract["accessible_pools"][pool]
        try:
            PoolAccess(**{k: record[k] for k in ("free_fraction", "aqueous_fraction", "recovery_fraction", "activity_coefficient")})
            supported = isinstance(record["evidence"], str) and bool(record["evidence"].strip())
        except (TypeError, ValueError, KeyError):
            supported = False
        if not supported:
            missing.append("accessible_pool_" + pool)
    for name, compartment in (("pHi", "intracellular"), ("pHe", "extracellular")):
        r = contract["pH_inputs"][name]
        try:
            valid = (0 <= finite(r["value"]) <= 14 and r["temperature_C"] == contract["simulation_temperature_C"]
                     and r["compartment"] == compartment and isinstance(r["evidence"], str) and bool(r["evidence"].strip()))
        except (TypeError, ValueError, KeyError):
            valid = False
        if not valid:
            missing.append(name + "_temperature_matched_observation_or_supported_model")
    b = contract["buffering"]
    try:
        finite(b["beta_i_mM_per_L_cells_per_pH"], positive=True)
        finite(b["beta_e_mM_per_L_supernatant_per_pH"], positive=True)
        supported = (b["temperature_C"] == contract["simulation_temperature_C"]
                     and isinstance(b["evidence"], str) and bool(b["evidence"].strip())
                     and b["representation"] in ("effective_total_capacity", "explicit_CO2_plus_intrinsic_capacity"))
    except (TypeError, ValueError, KeyError):
        supported = False
    if not supported:
        missing.append("temperature_matched_buffer_capacities_and_nonduplicated_representation")
    for section, keys in (("buffering", ("Hb_oxygenation_and_CO2_boundary_contract", "metabolic_proton_stoichiometry_contract", "AE1_Cl_HCO3_contract", "gas_exchange_sampling_hemolysis_contract")),
                          ("kinetics", ("affinity_and_capacity_coordinate_contract", "alternative_lactate_routes_and_shared_capacity_contract"))):
        for key in keys:
            value = contract[section][key]
            if not isinstance(value, str) or not value.strip():
                missing.append(key)
    return {"prerequisite_inventory_complete": not missing, "missing": missing,
            "free_pH_prediction_authorized": False, "optimization_authorized": False,
            "note": "Evidence references require scientific review; this inventory never grants biological readiness."}
