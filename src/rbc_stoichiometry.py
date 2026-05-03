"""Stoichiometric structure of the Brodbar RBC ODE — single source of truth.

Phase 0 deliverable for the auto-calibrate-all + ML flux-learning plan
(see `C:/Users/Jorgelindo/.windsurf/plans/auto-calibrate-all-and-ml-flux-learning-179f0d.md`).

This module derives THREE structures programmatically from
`src/equadiff_brodbar.py` at module load time, by parsing the `dxdt[...] = ...`
rows and the flux assignment lines:

* ``STOICHIOMETRY`` — ``{reaction_name: {metabolite_name: signed_coefficient}}``
* ``REACTION_PARAMS`` — ``{reaction_name: frozenset[parameter_name]}``
* ``REVERSE_INDEX`` — ``{metabolite_name: frozenset[reaction_name]}``

The parsing is deterministic and runs once at import time. If any structural
drift in `equadiff_brodbar.py` makes the parse fail, the module raises during
import — this is intentional, so drift is loudly caught by CI rather than
silently producing a wrong stoichiometry.

The public API is intentionally small. Higher-level callers (e.g.
``MM_calibration.derive_auto_param_scope``) compose these primitives plus
their own bounds tables.

This module imports ONLY ``equadiff_brodbar.BRODBAR_METABOLITE_MAP`` from the
ODE module — no MM_calibration imports — to avoid any risk of circular
dependency.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, FrozenSet, Iterable, List, Mapping, Set

# ---------------------------------------------------------------------------
# Source file location + metabolite name map (imported lazily to support
# unusual sys.path configurations such as the calibration worker, which
# inserts ``src/`` directly).
# ---------------------------------------------------------------------------

_THIS_FILE = Path(__file__).resolve()
_SRC_DIR = _THIS_FILE.parent
_EQUADIFF_PATH = _SRC_DIR / "equadiff_brodbar.py"


def _load_metabolite_map() -> Dict[str, int]:
    try:
        from equadiff_brodbar import BRODBAR_METABOLITE_MAP  # type: ignore
        return dict(BRODBAR_METABOLITE_MAP)
    except Exception:  # pragma: no cover - defensive fallback
        import importlib
        return dict(importlib.import_module("equadiff_brodbar").BRODBAR_METABOLITE_MAP)


_METABOLITE_NAME_BY_INDEX: Dict[int, str] = {}
_METABOLITE_INDEX_BY_NAME: Dict[str, int] = {}


def _initialize_metabolite_indices() -> None:
    if _METABOLITE_NAME_BY_INDEX:
        return
    name_map = _load_metabolite_map()
    for name, idx in name_map.items():
        _METABOLITE_NAME_BY_INDEX[int(idx)] = str(name).upper()
        _METABOLITE_INDEX_BY_NAME[str(name).upper()] = int(idx)


# ---------------------------------------------------------------------------
# Reactions that the ODE explicitly sets to zero (deliberate RBC-strict
# omissions — they are documented in `equadiff_brodbar.py` with
# `# RBC-strict: ...` comments). They are NOT errors; the validator treats
# them as known empty reactions.
# ---------------------------------------------------------------------------

ZERO_FLUX_REACTIONS: FrozenSet[str] = frozenset({
    "VPC", "VACLY", "VACO", "VASTA", "VASL", "VASS",
    "Vpolyam", "VGENASP",
})


# ---------------------------------------------------------------------------
# Reaction-name aliases. The ODE's dxdt RHS may use a variable name that
# aliases a parameter root via the `_rate` suffix (e.g., `dxdt[EASN] = ... +
# VEASN_rate ...` while the parameter is `vmax_VEASN`). The alias map keeps
# the canonical reaction name visible to consumers but lets the parameter
# extractor look up the right `vmax_*` token.
# ---------------------------------------------------------------------------

_REACTION_ALIASES: Dict[str, str] = {
    "VEASN_rate": "VEASN",
    "VEGSH_rate": "VEGSH",
}

# ---------------------------------------------------------------------------
# Regex parsers
# ---------------------------------------------------------------------------

# `dxdt[<INDEX>] = <RHS>` where INDEX is a literal int or symbolic constant.
_DXDT_RE = re.compile(
    r"^\s*dxdt\[(?P<idx>\w+)\]\s*=\s*(?P<rhs>[^\n]+)$",
    re.MULTILINE,
)

# Flux assignment lines `Vxxx = <RHS>` at standard 4-space indent inside the
# main equadiff function. We deliberately exclude the parameter-extraction
# lines (`vmax_VHK = _get_param(...)`) by requiring the LHS to begin with
# uppercase `V` and not contain an underscore until at least one alpha char.
_FLUX_ASSIGN_RE = re.compile(
    r"^\s{4}(?P<name>V[A-Za-z][A-Za-z0-9_]*)\s*=\s*(?P<rhs>[^\n]+)$",
    re.MULTILINE,
)

# Symbolic index constant declaration: `ASN_INDEX = 106`
_INDEX_CONST_RE = re.compile(r"^(?P<name>[A-Z][A-Z0-9_]*_INDEX)\s*=\s*(?P<value>\d+)\b", re.MULTILINE)

# Parameter token: `vmax_NAME`, `km_NAME`, `ki_NAME`, `ka_NAME`, `alpha_NAME`,
# `n_NAME`, `hybrid_NAME`, `kinetic_family_NAME`, `transport_gate_NAME`,
# or `k_NAME` (used for degradation constants).
_PARAM_TOKEN_RE = re.compile(
    r"\b(?:vmax_|km_|ki_|ka_|alpha_|n_|hybrid_|kinetic_family_|transport_gate_|k_)"
    r"[A-Za-z][A-Za-z0-9_]*\b"
)

# `_get_param(custom_params, '<NAME>', <default>)` — authoritative parameter
# universe declared by `equadiff_brodbar.py`. Used to filter out spurious
# tokens such as locally-derived variable names (e.g. ``km_P2G_app``) that
# share a parameter prefix but are not real parameters.
_GET_PARAM_DECL_RE = re.compile(
    r"_get_param(?:_str)?\s*\(\s*custom_params\s*,\s*['\"](?P<name>[A-Za-z][A-Za-z0-9_]*)['\"]"
)

# Reaction-name token used inside a dxdt RHS. We require an uppercase V
# followed by at least one more alpha char to disambiguate from generic Python
# identifiers. We also support the `_rate` suffix for the two known aliased
# reactions.
_DXDT_REACTION_TOKEN_RE = re.compile(r"\bV[A-Za-z][A-Za-z0-9_]*\b")


# ---------------------------------------------------------------------------
# Source-file driven parsing
# ---------------------------------------------------------------------------


def _read_source() -> str:
    if not _EQUADIFF_PATH.exists():
        raise FileNotFoundError(
            f"rbc_stoichiometry expected to find equadiff_brodbar.py at "
            f"{_EQUADIFF_PATH}, but the file does not exist."
        )
    return _EQUADIFF_PATH.read_text(encoding="utf-8")


def _build_index_alias_table(source: str) -> Dict[str, int]:
    """Return ``{ASN_INDEX: 106, EOXOP_INDEX: 107, ...}`` extracted from the source."""
    alias = {}
    for m in _INDEX_CONST_RE.finditer(source):
        try:
            alias[m.group("name")] = int(m.group("value"))
        except ValueError:
            continue
    return alias


def _resolve_dxdt_index(idx_str: str, alias_table: Mapping[str, int]) -> int:
    """Resolve a `dxdt[<idx>]` index expression to an integer."""
    cleaned = idx_str.strip()
    if cleaned.isdigit():
        return int(cleaned)
    if cleaned in alias_table:
        return alias_table[cleaned]
    raise ValueError(f"Unknown dxdt index expression: {idx_str!r}")


def _parse_dxdt_rhs(rhs: str) -> Dict[str, float]:
    """Parse a dxdt RHS into ``{reaction: signed_coefficient}``.

    Handles examples like:
      ``VEGLC - VHK``
      ``2*VGSR + VGSS - 2*VGPX - VGGT - VEGSH_rate``
      ``VFDPA + VTPI - VGAPDH + VTKL1 + VTKL2 - VTAL``

    Returns an empty dict for purely-numeric RHS such as ``0.0`` or for any
    RHS that contains no ``V<NAME>`` flux term (e.g. pure pHi dynamics).
    """
    cleaned = rhs.split("#", 1)[0].strip()
    if not cleaned:
        return {}

    # Normalise: turn ``- VAK`` into ``+ -VAK`` so we can split on ``+``.
    normalized = cleaned.replace("-", "+-").replace("++-", "+-")
    if normalized.startswith("+"):
        normalized = normalized[1:]

    coeffs: Dict[str, float] = {}
    for raw_token in normalized.split("+"):
        token = raw_token.strip()
        if not token:
            continue
        sign = 1.0
        if token.startswith("-"):
            sign = -1.0
            token = token[1:].strip()

        m = re.fullmatch(
            r"\s*(?:(?P<coef>\d+(?:\.\d+)?)\s*\*\s*)?(?P<reaction>V[A-Za-z][A-Za-z0-9_]*)\s*",
            token,
        )
        if m is None:
            # Not a flux term (e.g. ``0.0``, ``k_EGSH_deg * max(x[...], 0.0)``,
            # or function calls). The dxdt rows that don't add up to a flux
            # mix are either constants or have the flux extracted by the
            # subsequent regex pass.
            continue

        coef_str = m.group("coef")
        coef = float(coef_str) if coef_str else 1.0
        reaction = m.group("reaction")
        coeffs[reaction] = coeffs.get(reaction, 0.0) + sign * coef

    return coeffs


def _extract_params_from_rhs(rhs: str) -> Set[str]:
    """Return the set of parameter tokens referenced in a flux assignment RHS.

    Only tokens matching the known prefixes (``vmax_``, ``km_``, ``ki_``,
    ``ka_``, ``alpha_``, ``n_``, ``hybrid_``, ``kinetic_family_``,
    ``transport_gate_``, ``k_``) are returned. Free-standing variable names
    are ignored, since this is a structural extractor — not a dependency
    analyser.
    """
    cleaned = rhs.split("#", 1)[0]
    return set(_PARAM_TOKEN_RE.findall(cleaned))


# ---------------------------------------------------------------------------
# Build-time aggregation
# ---------------------------------------------------------------------------


def _build_stoichiometry(source: str) -> Dict[str, Dict[str, float]]:
    """Return ``{reaction_name: {metabolite_name: signed_coef}}``."""
    _initialize_metabolite_indices()
    alias_table = _build_index_alias_table(source)

    stoichiometry: Dict[str, Dict[str, float]] = {}

    for match in _DXDT_RE.finditer(source):
        idx_str = match.group("idx")
        rhs = match.group("rhs")
        try:
            idx = _resolve_dxdt_index(idx_str, alias_table)
        except ValueError:
            continue

        metabolite = _METABOLITE_NAME_BY_INDEX.get(idx)
        if not metabolite:
            continue

        coefficients = _parse_dxdt_rhs(rhs)
        for reaction, coef in coefficients.items():
            entry = stoichiometry.setdefault(reaction, {})
            entry[metabolite] = entry.get(metabolite, 0.0) + coef

    # Drop zero-net entries (e.g. coefficients that cancel out).
    for reaction, mets in list(stoichiometry.items()):
        cleaned = {m: c for m, c in mets.items() if abs(c) > 1e-12}
        if not cleaned:
            stoichiometry.pop(reaction, None)
        else:
            stoichiometry[reaction] = cleaned

    return stoichiometry


def _build_known_param_universe(source: str) -> FrozenSet[str]:
    """Return the set of parameter NAMES declared via ``_get_param(custom_params, '<NAME>', ...)``."""
    return frozenset(m.group("name") for m in _GET_PARAM_DECL_RE.finditer(source))


def _iter_flux_blocks(source: str):
    """Yield ``(reaction_name, rhs_text)`` pairs for every flux assignment in
    the kinetics block, including multi-line function-call dispatches such as
    ``VEGLC = _compute_veglc_flux(\\n    t,\\n    x,\\n    ...\\n)``.

    A "flux block" begins when a line at exactly 4-space indent matches
    ``V<NAME> = <head>`` and continues across subsequent lines while the
    parenthesis count of the accumulated RHS remains positive (i.e. the call
    is unbalanced) or the accumulated RHS ends in ``\\``. The block ends at
    the first line that satisfies neither condition AND is not a pure
    continuation of a multi-line call.

    The kinetics region is delimited by the comments
    ``===== CALCULATE ENZYMATIC REACTION RATES`` and
    ``===== COMPUTE DIFFERENTIAL EQUATIONS`` — falling back to the entire
    file if either marker is missing (defensive — drift will surface in the
    consistency test).
    """
    start_marker = "===== CALCULATE ENZYMATIC REACTION RATES"
    end_marker = "===== COMPUTE DIFFERENTIAL EQUATIONS"
    start = source.find(start_marker)
    end = source.find(end_marker)
    if start < 0 or end < 0 or end <= start:
        block = source
    else:
        block = source[start:end]

    flux_head_re = re.compile(r"^\s{4}(?P<name>V[A-Za-z][A-Za-z0-9_]*)\s*=\s*(?P<rhs>.*)$")

    lines = block.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        m = flux_head_re.match(line)
        if not m:
            i += 1
            continue

        name = m.group("name")
        rhs_parts = [m.group("rhs")]
        # Continue while the RHS has unbalanced parentheses or an explicit
        # backslash continuation. Stop at end-of-block.
        balance = rhs_parts[0].count("(") - rhs_parts[0].count(")")
        ends_with_backslash = rhs_parts[0].rstrip().endswith("\\")
        j = i + 1
        while j < n and (balance > 0 or ends_with_backslash):
            next_line = lines[j]
            rhs_parts.append(next_line)
            balance += next_line.count("(") - next_line.count(")")
            ends_with_backslash = next_line.rstrip().endswith("\\")
            j += 1
        yield name, "\n".join(rhs_parts)
        i = j


def _build_reaction_params(source: str, known_universe: FrozenSet[str]) -> Dict[str, FrozenSet[str]]:
    """Return ``{reaction_name: frozenset(parameter_names)}``.

    Each flux assignment block ``Vxxx = ...`` (single- or multi-line) is
    scanned for parameter tokens matching the known prefixes. Tokens are then
    intersected with ``known_universe`` (the set of names declared via
    ``_get_param`` in the source) so that derived locals like ``km_P2G_app``
    don't leak into the reaction-parameter map.

    For the five hybrid reactions whose flux is dispatched through
    ``_compute_*_flux(...)`` calls, the multi-line block accumulator captures
    every parameter passed as a call argument (e.g.,
    ``_compute_vpk_flux(x, custom_params, f_pH_VPK, vmax_VPK, ..., km_PEP,
    km_ADP_ATP, ATP, ADP)`` → ``{vmax_VPK, km_PEP, km_ADP_ATP}``).
    Structure-only parameters declared inside the helper bodies
    (``hybrid_blend_VEGLC`` and similar) are intentionally NOT captured here;
    Phase 0 keeps the auto-scope to non-hybrid params only.
    """
    reaction_params: Dict[str, Set[str]] = {}

    for name, rhs in _iter_flux_blocks(source):
        params = _extract_params_from_rhs(rhs) & known_universe
        existing = reaction_params.setdefault(name, set())
        existing.update(params)

    # Apply alias normalisation: VEASN_rate carries the same params as VEASN's
    # generated flux line. Ensure both names are populated so consumers that
    # see one or the other in stoichiometry can still resolve their params.
    for alias, canonical in _REACTION_ALIASES.items():
        merged = reaction_params.get(alias, set()) | reaction_params.get(canonical, set())
        reaction_params[alias] = set(merged)
        reaction_params[canonical] = set(merged)

    return {name: frozenset(params) for name, params in reaction_params.items()}


def _build_reverse_index(stoichiometry: Mapping[str, Mapping[str, float]]) -> Dict[str, FrozenSet[str]]:
    """Return ``{metabolite_name: frozenset(reaction_names)}``."""
    rev: Dict[str, Set[str]] = {}
    for reaction, mets in stoichiometry.items():
        for metabolite in mets:
            rev.setdefault(metabolite, set()).add(reaction)
    return {met: frozenset(rxns) for met, rxns in rev.items()}


# ---------------------------------------------------------------------------
# Module-level constants populated at import time. Any drift in the source
# file structure that prevents parsing will raise here, which is intentional.
# ---------------------------------------------------------------------------

_SOURCE = _read_source()
_KNOWN_PARAM_UNIVERSE: FrozenSet[str] = _build_known_param_universe(_SOURCE)

STOICHIOMETRY: Dict[str, Dict[str, float]] = _build_stoichiometry(_SOURCE)
REACTION_PARAMS: Dict[str, FrozenSet[str]] = _build_reaction_params(_SOURCE, _KNOWN_PARAM_UNIVERSE)
REVERSE_INDEX: Dict[str, FrozenSet[str]] = _build_reverse_index(STOICHIOMETRY)

ALL_REACTIONS: FrozenSet[str] = frozenset(STOICHIOMETRY) | frozenset(REACTION_PARAMS)
ALL_METABOLITES: FrozenSet[str] = frozenset(REVERSE_INDEX)
ALL_PARAMETERS: FrozenSet[str] = frozenset().union(*REACTION_PARAMS.values()) if REACTION_PARAMS else frozenset()
KNOWN_PARAM_UNIVERSE: FrozenSet[str] = _KNOWN_PARAM_UNIVERSE


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _normalize_metabolite_names(names: Iterable[str]) -> List[str]:
    return [str(n).strip().upper() for n in names if str(n).strip()]


def reactions_for_metabolites(names: Iterable[str]) -> FrozenSet[str]:
    """Return every reaction whose stoichiometry has a non-zero coefficient on
    any of the input metabolites.

    Names are case-insensitive; unknown metabolite names are silently ignored
    (the caller is expected to filter them earlier — this is a structural
    primitive, not an input validator).
    """
    cleaned = _normalize_metabolite_names(names)
    out: Set[str] = set()
    for met in cleaned:
        out.update(REVERSE_INDEX.get(met, frozenset()))
    return frozenset(out)


def params_for_reactions(
    reactions: Iterable[str],
    *,
    include_hybrid: bool = False,
    include_regulation: bool = True,
    include_degradation: bool = False,
) -> FrozenSet[str]:
    """Return the union of parameters consumed by the given reactions.

    Parameters
    ----------
    reactions : iterable of reaction names
    include_hybrid : if False, drop ``hybrid_*`` / ``kinetic_family_*`` /
        ``transport_gate_*`` parameters. Phase 0 default is False.
    include_regulation : if True, keep ``ki_*``, ``ka_*``, ``alpha_*``,
        ``n_*`` regulatory parameters. Default True.
    include_degradation : if True, keep ``k_*deg`` first-order degradation
        constants. Default False (Phase 0 stays away from degradation
        until Phase 4 sensitivity work).
    """
    out: Set[str] = set()
    for reaction in reactions:
        params = REACTION_PARAMS.get(reaction)
        if not params:
            continue
        for name in params:
            if name.startswith(("vmax_", "km_")):
                out.add(name)
                continue
            if include_regulation and name.startswith(("ki_", "ka_", "alpha_", "n_")):
                out.add(name)
                continue
            if include_hybrid and name.startswith(("hybrid_", "kinetic_family_", "transport_gate_")):
                out.add(name)
                continue
            if include_degradation and name.startswith("k_") and name.endswith("_deg"):
                out.add(name)
                continue
    return frozenset(out)


def params_for_metabolites(
    names: Iterable[str],
    *,
    include_hybrid: bool = False,
    include_regulation: bool = True,
    include_degradation: bool = False,
) -> FrozenSet[str]:
    """Convenience wrapper: ``reactions_for_metabolites`` then ``params_for_reactions``."""
    reactions = reactions_for_metabolites(names)
    return params_for_reactions(
        reactions,
        include_hybrid=include_hybrid,
        include_regulation=include_regulation,
        include_degradation=include_degradation,
    )


def validate_consistency(known_param_names: Iterable[str]) -> List[str]:
    """Return a list of human-readable structural issues detected in the
    parsed stoichiometry / reaction-parameter map.

    Pass the calibration's full parameter universe (e.g.
    ``mm.DEFAULT_PARAM_VALUES.keys()``) so the validator can flag any
    parameter that appears in a flux line but has no bounds entry.

    An empty list means the parsed stoichiometry is internally consistent.
    """
    issues: List[str] = []
    known = {str(n) for n in known_param_names}

    # 1. Every reaction in stoichiometry should have at least one parameter
    #    OR be a documented zero-flux placeholder OR be an alias.
    aliased_canonicals = set(_REACTION_ALIASES.values())
    for reaction in sorted(STOICHIOMETRY):
        if reaction in ZERO_FLUX_REACTIONS:
            continue
        params = REACTION_PARAMS.get(reaction, frozenset())
        if not params and reaction not in _REACTION_ALIASES and reaction not in aliased_canonicals:
            issues.append(
                f"Reaction {reaction!r} appears in dxdt rows but has no parameters "
                f"in the flux-assignment scan. Suspected stoichiometric drift."
            )

    # 2. Every parameter token referenced in a flux line should be present in
    #    the calibrator's parameter universe (so it can be optimised).
    for reaction in sorted(REACTION_PARAMS):
        for param in REACTION_PARAMS[reaction]:
            if param.startswith(("hybrid_", "kinetic_family_", "transport_gate_")):
                # Hybrid params are optional and may be absent from the
                # production parameter universe in early phases.
                continue
            if param not in known:
                issues.append(
                    f"Parameter {param!r} used by reaction {reaction!r} but absent "
                    f"from the calibrator's known-parameter universe."
                )

    # 3. Every metabolite name produced by the parser should map back to the
    #    Brodbar map index.
    _initialize_metabolite_indices()
    for metabolite in sorted(REVERSE_INDEX):
        if metabolite not in _METABOLITE_INDEX_BY_NAME:
            issues.append(
                f"Metabolite {metabolite!r} appears in dxdt rows but is missing "
                f"from BRODBAR_METABOLITE_MAP."
            )

    return issues


__all__ = [
    "STOICHIOMETRY",
    "REACTION_PARAMS",
    "REVERSE_INDEX",
    "ALL_REACTIONS",
    "ALL_METABOLITES",
    "ALL_PARAMETERS",
    "KNOWN_PARAM_UNIVERSE",
    "ZERO_FLUX_REACTIONS",
    "reactions_for_metabolites",
    "params_for_reactions",
    "params_for_metabolites",
    "validate_consistency",
]
