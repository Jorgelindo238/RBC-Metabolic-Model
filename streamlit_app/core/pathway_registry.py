"""Canonical pathway registry for the RBC metabolic network.

This module builds a registry-backed graph from the model reaction source
(`RBC/Rxn_RBC.txt`) and the executable ODE source (`src/equadiff_brodbar.py`),
then enriches it with reaction labels / metadata from
`reaction_info_complete.py`.

The result is a single source of truth for Pathway Visualization and the
Pathway replay/network-state projection used by the web app.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha1
from math import cos, hypot, pi, sin
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

try:  # Optional at runtime, but available in this workspace.
    import networkx as nx
except Exception:  # pragma: no cover - graceful fallback for minimal envs
    nx = None

from parse import parse as parse_reaction_file

from .reaction_info_complete import REACTION_INFO_COMPLETE


ROOT_DIR = Path(__file__).resolve().parents[2]
RXN_FILE = ROOT_DIR / "RBC" / "Rxn_RBC.txt"
EQ_FILE = ROOT_DIR / "src" / "equadiff_brodbar.py"
REACTION_INFO_FILE = ROOT_DIR / "streamlit_app" / "core" / "reaction_info_complete.py"

PATHWAY_REGISTRY_VERSION = "rbc-pathway-registry-v3"

PATHWAY_COLORS: Dict[str, str] = {
    "Glycolysis": "#e74c3c",
    "Pentose Phosphate": "#9b59b6",
    "Rapoport-Luebering": "#f39c12",
    "Nucleotide Salvage": "#1abc9c",
    "Energy": "#34495e",
    "Redox": "#2ecc71",
    "Amino Acid": "#7f8c8d",
    "Transport": "#3498db",
    "Anaplerotic": "#16a085",
    "Other": "#95a5a6",
}

PATHWAY_LEGEND = [{"label": label, "color": color} for label, color in PATHWAY_COLORS.items()]

COMPACT_OVERVIEW_PRIORITY: Dict[str, List[str]] = {
    "Glycolysis": ["G6P", "F6P", "PEP", "PYR", "B23PG", "GLC"],
    "Pentose Phosphate": ["R5P", "G6P", "RU5P", "X5P", "NADPH", "GL6P"],
    "Rapoport-Luebering": ["B23PG", "B13PG", "PEP"],
    "Nucleotide Salvage": ["IMP", "INO", "HYPX", "XAN", "GMP", "ADE", "GUA"],
    "Energy": ["ATP", "ADP", "AMP"],
    "Redox": ["NADPH", "NADP", "NADH", "NAD"],
    "Amino Acid": ["GLU", "GLY", "SER", "ALA", "CYS", "MET"],
    "Transport": ["GLC", "GLN", "ADO", "URT", "XMP", "PRPP"],
    "Anaplerotic": ["OAA", "MAL", "CIT", "AKG"],
    "Other": ["MAL", "CIT", "GLU"],
}

# A compact compatibility map for the 18 drift items between the parser output
# and the helper metadata. Most entries are identity mappings; the registry
# keeps parser/ODE ids as canonical and only uses the alias when looking up
# helper labels/sections.
REACTION_METADATA_ALIASES: Dict[str, str] = {
    "VGDA": "VGDA",
    "VGMPK": "VGMPK",
    "VNDPK": "VNDPK",
    "VOPLAH": "VOPLAH",
    "VPEP_PASE": "VPEP_PASE",
    "VPHGDH": "VPHGDH",
    "VPRPPASe": "VPRPPASE",
    "VSHMT": "VSHMT",
    "Vnucleo_GMP": "Vnucleo_GMP",
    "VACLY": "VACLY",
    "VACO": "VACO",
    "VASL": "VASL",
    "VASS": "VASS",
    "VASTA": "VASTA",
    "VGENASP": "VGENASP",
    "VGPX": "VGPX",
    "VPC": "VPC",
    "VPRPPASE": "VPRPPASE",
    "Vpolyam": "Vpolyam",
}

FALLBACK_REACTION_LABELS: Dict[str, str] = {
    "VGDA": "Guanine Deaminase",
    "VGMPK": "GMP Kinase",
    "VNDPK": "Nucleoside Diphosphate Kinase",
    "VOPLAH": "5-Oxoprolinase",
    "VPEP_PASE": "PEP Phosphatase",
    "VPHGDH": "Phosphoglycerate Dehydrogenase",
    "VSHMT": "Serine Hydroxymethyltransferase",
    "Vnucleo_GMP": "GMP Nucleosidase",
    "VACO": "Aconitase + ICDH",
}

FALLBACK_REACTION_METADATA: Dict[str, Dict[str, Any]] = {
    "VACO": {
        "name": "Aconitase + ICDH",
        "reaction": "CIT + NADP => AKG + NADPH",
        "substrates": ["CIT", "NADP"],
        "products": ["AKG", "NADPH"],
    }
}

SECTION_TO_PATHWAY: Dict[str, str] = {
    "glycolysis": "Glycolysis",
    "pentose phosphate": "Pentose Phosphate",
    "pentose phosphate pathway": "Pentose Phosphate",
    "rapoport-luebering": "Rapoport-Luebering",
    "nucleotide salvage": "Nucleotide Salvage",
    "purine metabolism": "Nucleotide Salvage",
    "amino acid metabolism": "Amino Acid",
    "amino acid": "Amino Acid",
    "redox and cofactor metabolites": "Redox",
    "redox": "Redox",
    "transport reactions": "Transport",
    "transport": "Transport",
    "anaplerotic": "Anaplerotic",
    "other": "Other",
}

PATHWAY_GROUP_CENTERS: Dict[str, Tuple[float, float]] = {
    "Glycolysis": (1.8, 6.3),
    "Pentose Phosphate": (3.3, 7.1),
    "Rapoport-Luebering": (2.8, 5.3),
    "Transport": (0.9, 4.2),
    "Nucleotide Salvage": (5.7, 4.5),
    "Energy": (5.2, 8.3),
    "Redox": (6.6, 7.5),
    "Amino Acid": (8.2, 5.7),
    "Anaplerotic": (4.8, 3.2),
    "Other": (7.4, 2.8),
}

OVERVIEW_ANCHORS: Dict[str, Tuple[float, float]] = {
    # Glycolysis
    "GLC": (1.0, 10.0),
    "G6P": (1.0, 9.0),
    "F6P": (1.0, 8.0),
    "B13PG": (1.5, 5.5),
    "B23PG": (2.5, 5.5),
    "PEP": (1.5, 2.5),
    "PYR": (1.5, 1.5),
    "LAC": (1.5, 0.5),
    # Pentose phosphate
    "GL6P": (3.0, 9.0),
    "RU5P": (3.0, 7.0),
    "R5P": (3.5, 6.0),
    "X5P": (2.5, 6.0),
    "S7P": (3.0, 5.0),
    "E4P": (3.5, 4.0),
    # Energy
    "ATP": (5.0, 9.0),
    "ADP": (5.0, 8.0),
    "AMP": (5.0, 7.0),
    # Redox
    "NAD": (6.0, 9.0),
    "NADH": (6.0, 8.0),
    "NADP": (7.0, 9.0),
    "NADPH": (7.0, 8.0),
    # Nucleotide salvage
    "IMP": (5.0, 3.0),
    "INO": (5.0, 2.0),
    "HYPX": (5.0, 1.0),
    "XAN": (6.0, 1.0),
    "ADE": (6.0, 2.0),
    "GUA": (6.0, 3.0),
    # Amino acids
    "GLY": (8.0, 7.0),
    "SER": (8.0, 6.0),
    "ALA": (8.0, 5.0),
}


@dataclass(frozen=True)
class PathwayRegistryNode:
    id: str
    label: str
    x: float
    y: float
    pathway: str
    compartment: str = "cytosol"


@dataclass(frozen=True)
class PathwayRegistryEdge:
    source: str
    target: str
    enzyme: str
    reversible: bool
    color: str
    pathway: str


@dataclass(frozen=True)
class PathwayRegistryReactionNode:
    id: str
    label: str
    x: float
    y: float
    enzyme: str
    source: str
    target: str
    reversible: bool
    pathway: str
    color: str


@dataclass(frozen=True)
class PathwayRegistryCompactOverviewItem:
    pathway: str
    color: str
    node_count: int
    connector_metabolite: Optional[str]
    bridge_pathways: List[str]
    bridge_summary: str
    top_metabolites: List[str]


@dataclass(frozen=True)
class PathwayRegistry:
    version: str
    title: str
    source: str
    nodes: List[PathwayRegistryNode]
    edges: List[PathwayRegistryEdge]
    reaction_nodes: List[PathwayRegistryReactionNode]
    compact_overview: List[PathwayRegistryCompactOverviewItem]
    legend: List[Dict[str, str]]
    stats: Dict[str, int]
    pathway_groups: Dict[str, List[str]]


@dataclass(frozen=True)
class ReactionRecord:
    id: str
    label: str
    equation: str
    substrates: List[str]
    products: List[str]
    reversible: bool
    pathway: str
    source: str
    target: str
    color: str


def _normalize_pathway_name(raw: str | None) -> str:
    if not raw:
        return "Other"
    cleaned = raw.strip().lower()
    for key, value in SECTION_TO_PATHWAY.items():
        if key in cleaned:
            return value
    if "transport" in cleaned:
        return "Transport"
    if "cofactor" in cleaned or "redox" in cleaned:
        return "Redox"
    if "anaplerotic" in cleaned or "tca" in cleaned:
        return "Anaplerotic"
    return "Other"


def _pathway_color(pathway: str) -> str:
    return PATHWAY_COLORS.get(pathway, PATHWAY_COLORS["Other"])


def _stable_jitter(name: str, radius: float = 0.22) -> Tuple[float, float]:
    digest = sha1(name.encode("utf-8")).hexdigest()
    angle = int(digest[:8], 16) / 0xFFFFFFFF * 2.0 * pi
    magnitude = radius * (0.45 + (int(digest[8:12], 16) / 0xFFFF) * 0.55)
    return cos(angle) * magnitude, sin(angle) * magnitude


def _parse_equation_side(side: str) -> List[str]:
    items: List[str] = []
    for chunk in side.split("+"):
        token = re.sub(r"^\s*\d+(?:\.\d+)?\s*", "", chunk.strip())
        token = token.strip()
        if token:
            items.append(token)
    return items


def _parse_reaction_equation(equation: str) -> Tuple[List[str], List[str], bool]:
    normalized = (
        equation.replace("⇌", "=")
        .replace("↔", "=")
        .replace("⇆", "=")
        .replace("→", "=>")
        .replace("←", "<=")
    )

    if "=>" in normalized:
        left, right = normalized.split("=>", 1)
        reversible = False
    elif "<=" in normalized:
        right, left = normalized.split("<=", 1)
        reversible = False
    elif "=" in normalized:
        left, right = normalized.split("=", 1)
        reversible = True
    else:  # fallback for malformed text
        left, right, reversible = normalized, "", True

    substrates = _parse_equation_side(left.strip())
    products = _parse_equation_side(right.strip())
    return substrates, products, reversible


def _reaction_display_name(reaction_id: str, metadata: Mapping[str, Any] | None) -> str:
    if metadata and metadata.get("name"):
        return str(metadata["name"])
    if reaction_id in FALLBACK_REACTION_LABELS:
        return FALLBACK_REACTION_LABELS[reaction_id]
    if reaction_id.startswith("VE") and len(reaction_id) > 2:
        return f"{reaction_id[2:]} transport"
    return reaction_id.lstrip("V") or reaction_id


def _load_reaction_info_sections() -> Dict[str, str]:
    """Read reaction_info_complete.py comments to recover pathway groupings."""
    section_by_key: Dict[str, str] = {}
    current_section = "Other"
    text = REACTION_INFO_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()

    for raw_line in text:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            header = line.lstrip("#").strip()
            header = _normalize_pathway_name(header)
            if header != "Other" or "other" in line.lower():
                current_section = header
            continue
        match = re.match(r"^['\"]?([A-Za-z0-9_]+)['\"]?\s*:\s*\{", line)
        if match:
            section_by_key[match.group(1)] = current_section

    return section_by_key


@lru_cache(maxsize=1)
def _load_parsed_model() -> Dict[str, Any]:
    return parse_reaction_file(str(RXN_FILE))


@lru_cache(maxsize=1)
def _load_rxn_catalog() -> List[Tuple[str, str, List[str], List[str], bool]]:
    """Return the reaction catalog from Rxn_RBC.txt in file order."""
    model = _load_parsed_model()
    ordered_names = list(model["react_name"])
    raw_map: Dict[str, str] = {}

    in_cat = False
    for raw_line in RXN_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.upper().startswith("-CAT"):
            in_cat = True
            continue
        if line.startswith("-") and in_cat:
            break
        if in_cat and ":" in line:
            name, equation = line.split(":", 1)
            raw_map[name.strip()] = equation.strip()

    catalog: List[Tuple[str, str, List[str], List[str], bool]] = []
    for reaction_id in ordered_names:
        equation = raw_map.get(reaction_id, reaction_id)
        substrates, products, reversible = _parse_reaction_equation(equation)
        catalog.append((reaction_id, equation, substrates, products, reversible))

    return catalog


@lru_cache(maxsize=1)
def _load_equadiff_reaction_names() -> List[str]:
    """Extract flux keys from equadiff_brodbar.py in declaration order."""
    text = EQ_FILE.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"flux_dict\s*=\s*\{(.*?)\n\s*\}\s*\n\s*_flux\.add_timepoint", text, re.S)
    if not match:
        raise RuntimeError("Could not locate flux_dict block in equadiff_brodbar.py")
    block = match.group(1)
    return re.findall(r"'([A-Za-z0-9_]+)'\s*:", block)


@lru_cache(maxsize=1)
def _load_reaction_section_map() -> Dict[str, str]:
    return _load_reaction_info_sections()


def _resolve_metadata_name(reaction_id: str) -> str:
    return REACTION_METADATA_ALIASES.get(reaction_id, reaction_id)


def _build_reaction_records() -> List[ReactionRecord]:
    reaction_section_map = _load_reaction_section_map()
    raw_catalog = {reaction_id: (equation, substrates, products, reversible) for reaction_id, equation, substrates, products, reversible in _load_rxn_catalog()}
    parser_order = [reaction_id for reaction_id, *_ in _load_rxn_catalog()]
    equadiff_order = _load_equadiff_reaction_names()

    # Keep parser order, then append any equadiff-only reactions so the ODE
    # source stays fully represented.
    ordered_ids: List[str] = []
    seen: set[str] = set()
    for reaction_id in parser_order + equadiff_order:
        if reaction_id not in seen:
            ordered_ids.append(reaction_id)
            seen.add(reaction_id)

    records: List[ReactionRecord] = []
    for reaction_id in ordered_ids:
        metadata_name = _resolve_metadata_name(reaction_id)
        metadata = (
            REACTION_INFO_COMPLETE.get(metadata_name)
            or REACTION_INFO_COMPLETE.get(reaction_id)
            or FALLBACK_REACTION_METADATA.get(reaction_id)
        )

        if reaction_id in raw_catalog:
            equation, substrates, products, reversible = raw_catalog[reaction_id]
        elif metadata:
            equation = str(metadata.get("reaction", ""))
            substrates = [str(item) for item in metadata.get("substrates", [])]
            products = [str(item) for item in metadata.get("products", [])]
            reversible = any(token in equation for token in ("⇌", "↔", "⇆", "="))
        else:
            equation = reaction_id
            substrates = []
            products = []
            reversible = True

        section_name = reaction_section_map.get(metadata_name) or reaction_section_map.get(reaction_id)
        pathway = _normalize_pathway_name(section_name)
        if pathway == "Other":
            if reaction_id.startswith("VE"):
                pathway = "Transport"
            elif reaction_id in {
                "VACLY",
                "VPC",
                "VGENASP",
                "VACO",
            }:
                pathway = "Anaplerotic"
            elif reaction_id in {
                "VGPX",
            }:
                pathway = "Redox"
            elif reaction_id in {
                "VASL",
                "VASS",
                "VASTA",
                "Vpolyam",
            }:
                pathway = "Amino Acid"
            elif reaction_id in {
                "VGDA",
                "VGMPK",
                "VNDPK",
                "VOPLAH",
                "VPEP_PASE",
                "VPHGDH",
                "VSHMT",
                "Vnucleo_GMP",
            }:
                pathway = "Nucleotide Salvage" if reaction_id in {"VGDA", "VGMPK", "VNDPK", "Vnucleo_GMP"} else "Amino Acid"

        color = _pathway_color(pathway)
        display_name = _reaction_display_name(reaction_id, metadata)
        source = substrates[0] if substrates else (reaction_id.split(":")[0] if ":" in reaction_id else reaction_id)
        target = products[0] if products else (substrates[-1] if substrates else reaction_id)

        records.append(
            ReactionRecord(
                id=reaction_id,
                label=display_name,
                equation=equation,
                substrates=substrates,
                products=products,
                reversible=reversible,
                pathway=pathway,
                source=source,
                target=target,
                color=color,
            )
        )

    return records


def _dominant_pathway_for_metabolite(
    metabolite_id: str,
    metabolite_compartment: str,
    reaction_by_id: Mapping[str, ReactionRecord],
    metabolite_connections: Mapping[str, List[str]],
) -> str:
    if metabolite_compartment == "extracellular":
        transport_votes = sum(
            1 for rxn_id in metabolite_connections.get(metabolite_id, []) if reaction_by_id[rxn_id].pathway == "Transport"
        )
        if transport_votes:
            return "Transport"

    votes = Counter(reaction_by_id[rxn_id].pathway for rxn_id in metabolite_connections.get(metabolite_id, []))
    if not votes:
        if metabolite_compartment == "extracellular":
            return "Transport"
        return "Other"
    top = votes.most_common()
    top_count = top[0][1]
    tied = sorted(pathway for pathway, count in top if count == top_count)
    return tied[0]


def _stable_group_center(pathway: str, metabolite_id: str) -> Tuple[float, float]:
    base_x, base_y = PATHWAY_GROUP_CENTERS.get(pathway, PATHWAY_GROUP_CENTERS["Other"])
    jitter_x, jitter_y = _stable_jitter(metabolite_id, radius=0.28)
    return base_x + jitter_x, base_y + jitter_y


def _layout_registry(
    metabolites: List[PathwayRegistryNode],
    reaction_records: List[ReactionRecord],
    metabolite_to_group: Mapping[str, str],
) -> Dict[str, Tuple[float, float]]:
    if nx is None:
        # Deterministic fallback if networkx is unavailable.
        positions: Dict[str, Tuple[float, float]] = {}
        for node in metabolites:
            if node.id in OVERVIEW_ANCHORS:
                positions[node.id] = OVERVIEW_ANCHORS[node.id]
            else:
                positions[node.id] = _stable_group_center(metabolite_to_group.get(node.id, node.pathway), node.id)
        for reaction in reaction_records:
            coords = [positions.get(metabolite_id) for metabolite_id in reaction.substrates + reaction.products]
            coords = [coord for coord in coords if coord is not None]
            if coords:
                xs = [coord[0] for coord in coords]
                ys = [coord[1] for coord in coords]
                positions[reaction.id] = (sum(xs) / len(xs), sum(ys) / len(ys))
            else:
                positions[reaction.id] = _stable_group_center(reaction.pathway, reaction.id)
        return positions

    graph = nx.Graph()
    for node in metabolites:
        graph.add_node(node.id, kind="metabolite", pathway=node.pathway)
    for reaction in reaction_records:
        graph.add_node(reaction.id, kind="reaction", pathway=reaction.pathway)
        for metabolite_id in reaction.substrates + reaction.products:
            graph.add_edge(reaction.id, metabolite_id, weight=1.0)

    seed_positions: Dict[str, Tuple[float, float]] = {}
    fixed_nodes: List[str] = []

    for node in metabolites:
        if node.id in OVERVIEW_ANCHORS:
            seed_positions[node.id] = OVERVIEW_ANCHORS[node.id]
            fixed_nodes.append(node.id)
        else:
            seed_positions[node.id] = _stable_group_center(metabolite_to_group.get(node.id, node.pathway), node.id)

    for reaction in reaction_records:
        connected = [seed_positions.get(metabolite_id) for metabolite_id in reaction.substrates + reaction.products]
        connected = [coord for coord in connected if coord is not None]
        if connected:
            xs = [coord[0] for coord in connected]
            ys = [coord[1] for coord in connected]
            seed_positions[reaction.id] = (sum(xs) / len(xs), sum(ys) / len(ys))
        else:
            seed_positions[reaction.id] = _stable_group_center(reaction.pathway, reaction.id)

    layout = nx.spring_layout(
        graph,
        pos=seed_positions,
        fixed=fixed_nodes,
        seed=13,
        k=0.85,
        iterations=280,
        weight="weight",
        dim=2,
    )

    xs = [coord[0] for coord in layout.values()]
    ys = [coord[1] for coord in layout.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1e-6)
    span_y = max(max_y - min_y, 1e-6)
    scale = min(8.8 / span_x, 8.8 / span_y)

    normalized: Dict[str, Tuple[float, float]] = {}
    for node_id, (x, y) in layout.items():
        normalized[node_id] = (
            0.6 + (x - min_x) * scale,
            0.6 + (y - min_y) * scale,
        )

    return normalized


def _partner_pathways_for_metabolite(
    metabolite_id: str,
    pathway: str,
    metabolite_connections: Mapping[str, List[str]],
    reaction_by_id: Mapping[str, ReactionRecord],
) -> Counter:
    partner_counts: Counter = Counter()
    for reaction_id in metabolite_connections.get(metabolite_id, []):
        reaction = reaction_by_id.get(reaction_id)
        if not reaction:
            continue
        partner_pathway = reaction.pathway
        if partner_pathway and partner_pathway != pathway:
            partner_counts[partner_pathway] += 1
    if len(partner_counts) > 1 and "Other" in partner_counts:
        partner_counts.pop("Other", None)
    return partner_counts


def _rank_compact_metabolites(
    pathway: str,
    members: List[str],
    metabolite_connections: Mapping[str, List[str]],
    reaction_by_id: Mapping[str, ReactionRecord],
) -> List[Tuple[str, Counter, Tuple[int, int, int]]]:
    ranked: List[Tuple[str, Counter, Tuple[int, int, int]]] = []
    for order, metabolite_id in enumerate(members):
        partner_counts = _partner_pathways_for_metabolite(metabolite_id, pathway, metabolite_connections, reaction_by_id)
        effective_counts = partner_counts if partner_counts else Counter()
        partner_diversity = len(effective_counts)
        partner_volume = sum(effective_counts.values())
        degree = len(metabolite_connections.get(metabolite_id, []))
        ranked.append((metabolite_id, partner_counts, (partner_diversity, partner_volume, degree - order)))
    return sorted(ranked, key=lambda item: item[2], reverse=True)


def _build_compact_overview(
    pathway_groups: Mapping[str, List[str]],
    metabolite_connections: Mapping[str, List[str]],
    reaction_by_id: Mapping[str, ReactionRecord],
) -> List[PathwayRegistryCompactOverviewItem]:
    compact_overview: List[PathwayRegistryCompactOverviewItem] = []

    for pathway in PATHWAY_COLORS.keys():
        members = list(pathway_groups.get(pathway, []))
        if not members:
            continue

        ranked = _rank_compact_metabolites(pathway, members, metabolite_connections, reaction_by_id)
        preferred = next((candidate for candidate in COMPACT_OVERVIEW_PRIORITY.get(pathway, []) if candidate in members), None)
        if preferred:
            selected = next((item for item in ranked if item[0] == preferred), None)
        else:
            selected = ranked[0] if ranked else None

        if selected is None:
            continue

        connector_metabolite, partner_counts, _ = selected
        partner_pathways = [pathway_name for pathway_name, _ in partner_counts.most_common()]
        top_metabolites = [metabolite_id for metabolite_id, _, _ in ranked[:3]]

        if partner_pathways:
            bridge_target = partner_pathways[0]
            if len(partner_pathways) > 1:
                bridge_summary = f"{connector_metabolite} bridges {pathway} ↔ {bridge_target} and {partner_pathways[1]}"
            else:
                bridge_summary = f"{connector_metabolite} bridges {pathway} ↔ {bridge_target}"
        else:
            bridge_summary = f"{connector_metabolite} is the main internal hub in {pathway}"

        compact_overview.append(
            PathwayRegistryCompactOverviewItem(
                pathway=pathway,
                color=_pathway_color(pathway),
                node_count=len(members),
                connector_metabolite=connector_metabolite,
                bridge_pathways=partner_pathways[:3],
                bridge_summary=bridge_summary,
                top_metabolites=top_metabolites,
            )
        )

    return compact_overview


@lru_cache(maxsize=1)
def build_canonical_pathway_registry() -> PathwayRegistry:
    parsed_model = _load_parsed_model()
    reaction_records = _build_reaction_records()

    int_metabolites = list(parsed_model["int_met"])
    ext_metabolites = list(parsed_model["ext_met"])

    # Build metabolite nodes with provisional pathway assignments from the
    # connected reactions. External metabolites default to Transport.
    reaction_by_id = {reaction.id: reaction for reaction in reaction_records}
    metabolite_connections: Dict[str, List[str]] = defaultdict(list)
    for reaction in reaction_records:
        for metabolite_id in reaction.substrates + reaction.products:
            metabolite_connections[metabolite_id].append(reaction.id)

    metabolite_pathway_map: Dict[str, str] = {}
    metabolite_compartment_map: Dict[str, str] = {}
    for metabolite_id in int_metabolites:
        metabolite_compartment_map[metabolite_id] = "cytosol"
    for metabolite_id in ext_metabolites:
        metabolite_compartment_map[metabolite_id] = "extracellular"

    for metabolite_id in int_metabolites + ext_metabolites:
        pathway = _dominant_pathway_for_metabolite(
            metabolite_id,
            metabolite_compartment_map.get(metabolite_id, "cytosol"),
            reaction_by_id,
            metabolite_connections,
        )
        metabolite_pathway_map[metabolite_id] = pathway

    # Override a few known metabolites so the overview remains legible.
    for metabolite_id, pathway in {
        "GLC": "Glycolysis",
        "G6P": "Glycolysis",
        "F6P": "Glycolysis",
        "B13PG": "Glycolysis",
        "B23PG": "Rapoport-Luebering",
        "PEP": "Glycolysis",
        "PYR": "Glycolysis",
        "LAC": "Glycolysis",
        "GL6P": "Pentose Phosphate",
        "RU5P": "Pentose Phosphate",
        "R5P": "Pentose Phosphate",
        "X5P": "Pentose Phosphate",
        "S7P": "Pentose Phosphate",
        "E4P": "Pentose Phosphate",
        "ATP": "Energy",
        "ADP": "Energy",
        "AMP": "Energy",
        "NAD": "Redox",
        "NADH": "Redox",
        "NADP": "Redox",
        "NADPH": "Redox",
        "IMP": "Nucleotide Salvage",
        "INO": "Nucleotide Salvage",
        "HYPX": "Nucleotide Salvage",
        "XAN": "Nucleotide Salvage",
        "ADE": "Nucleotide Salvage",
        "GUA": "Nucleotide Salvage",
        "GLY": "Amino Acid",
        "SER": "Amino Acid",
        "ALA": "Amino Acid",
    }.items():
        if metabolite_id in metabolite_pathway_map:
            metabolite_pathway_map[metabolite_id] = pathway

    layout = _layout_registry(
        metabolites=[
            PathwayRegistryNode(
                id=metabolite_id,
                label=metabolite_id,
                x=0.0,
                y=0.0,
                pathway=metabolite_pathway_map.get(metabolite_id, "Other"),
                compartment=metabolite_compartment_map.get(metabolite_id, "cytosol"),
            )
            for metabolite_id in int_metabolites + ext_metabolites
        ],
        reaction_records=reaction_records,
        metabolite_to_group=metabolite_pathway_map,
    )

    nodes: List[PathwayRegistryNode] = []
    for metabolite_id in int_metabolites + ext_metabolites:
        x, y = layout[metabolite_id]
        nodes.append(
            PathwayRegistryNode(
                id=metabolite_id,
                label=metabolite_id,
                x=x,
                y=y,
                pathway=metabolite_pathway_map.get(metabolite_id, "Other"),
                compartment=metabolite_compartment_map.get(metabolite_id, "cytosol"),
            )
        )

    reaction_nodes: List[PathwayRegistryReactionNode] = []
    edges: List[PathwayRegistryEdge] = []
    pathway_groups: Dict[str, List[str]] = defaultdict(list)

    for reaction in reaction_records:
        x, y = layout[reaction.id]
        reaction_nodes.append(
            PathwayRegistryReactionNode(
                id=reaction.id,
                label=reaction.label,
                x=x,
                y=y,
                enzyme=reaction.id,
                source=reaction.source,
                target=reaction.target,
                reversible=reaction.reversible,
                pathway=reaction.pathway,
                color=reaction.color,
            )
        )

        edges.append(
            PathwayRegistryEdge(
                source=reaction.source,
                target=reaction.target,
                enzyme=reaction.id,
                reversible=reaction.reversible,
                color=reaction.color,
                pathway=reaction.pathway,
            )
        )

    for node in nodes:
        pathway_groups[node.pathway].append(node.id)

    for pathway, members in pathway_groups.items():
        members.sort()

    compact_overview = _build_compact_overview(pathway_groups, metabolite_connections, reaction_by_id)

    stats = {
        "nodes": len(nodes),
        "edges": len(edges),
        "reactions": len(reaction_nodes),
        "pathways": len(pathway_groups),
    }

    return PathwayRegistry(
        version=PATHWAY_REGISTRY_VERSION,
        title="RBC Metabolic Network",
        source="Rxn_RBC.txt + equadiff_brodbar.py + reaction_info_complete.py",
        nodes=nodes,
        edges=edges,
        reaction_nodes=reaction_nodes,
        compact_overview=compact_overview,
        legend=list(PATHWAY_LEGEND),
        stats=stats,
        pathway_groups=dict(pathway_groups),
    )


def get_pathway_layout() -> Dict[str, Tuple[float, float]]:
    registry = build_canonical_pathway_registry()
    return {node.id: (node.x, node.y) for node in registry.nodes}


def get_pathway_reactions() -> List[PathwayRegistryEdge]:
    return list(build_canonical_pathway_registry().edges)


def build_pathway_network_payload(
    concentrations: Optional[Mapping[str, float]] = None,
    fluxes: Optional[Mapping[str, float]] = None,
) -> Dict[str, Any]:
    registry = build_canonical_pathway_registry()
    concentrations = concentrations or {}
    fluxes = fluxes or {}

    nodes: List[Dict[str, Any]] = []
    for node in registry.nodes:
        concentration = float(concentrations.get(node.id, 0.0))
        pathway_color = _pathway_color(node.pathway)
        if concentration > 0:
            intensity = min(concentration / 2.0, 1.0)
            color = f"rgba({int(255 * intensity)}, {int(120 + 80 * (1 - intensity))}, {int(255 * (1 - intensity))}, 0.9)"
            size = 15 + min(concentration * 10.0, 18.0)
        else:
            color = pathway_color
            size = 14.0
        nodes.append(
            {
                "id": node.id,
                "label": node.label,
                "pathway": node.pathway,
                "x": node.x,
                "y": node.y,
                "compartment": node.compartment,
                "concentration": concentration,
                "size": size,
                "color": color,
            }
        )

    edges: List[Dict[str, Any]] = []
    for edge in registry.edges:
        flux = fluxes.get(edge.enzyme)
        flux_value = float(flux) if flux is not None else None
        edges.append(
            {
                "source": edge.source,
                "target": edge.target,
                "enzyme": edge.enzyme,
                "reversible": edge.reversible,
                "color": edge.color,
                "pathway": edge.pathway,
                "flux": flux_value,
            }
        )

    reaction_nodes: List[Dict[str, Any]] = []
    for reaction in registry.reaction_nodes:
        flux = fluxes.get(reaction.enzyme)
        flux_value = float(flux) if flux is not None else None
        magnitude = abs(flux_value) if flux_value is not None else 0.0
        if flux_value is not None:
            intensity = min(magnitude / 25.0, 1.0)
            color = f"rgba({int(255 * intensity)}, {int(220 * (1 - intensity))}, {int(255 * (1 - intensity))}, 0.95)"
            size = 11 + min(magnitude / 18.0, 8.0)
        else:
            color = reaction.color
            size = 11.0
        reaction_nodes.append(
            {
                "id": reaction.id,
                "label": reaction.label,
                "enzyme": reaction.enzyme,
                "source": reaction.source,
                "target": reaction.target,
                "reversible": reaction.reversible,
                "pathway": reaction.pathway,
                "x": reaction.x,
                "y": reaction.y,
                "size": size,
                "color": color,
                "flux": flux_value,
            }
        )

    dominant_pathway = max(
        (
            {"pathway": pathway, "node_count": len(members)}
            for pathway, members in registry.pathway_groups.items()
        ),
        key=lambda item: item["node_count"],
        default={"pathway": None, "node_count": 0},
    )

    return {
        "registryVersion": registry.version,
        "sourceOfTruth": registry.source,
        "title": registry.title,
        "legend": registry.legend,
        "stats": registry.stats,
        "dominantPathway": dominant_pathway["pathway"],
        "pathwayGroups": registry.pathway_groups,
        "compactOverview": [
            {
                "pathway": item.pathway,
                "color": item.color,
                "nodeCount": item.node_count,
                "connectorMetabolite": item.connector_metabolite,
                "bridgePathways": item.bridge_pathways,
                "bridgeSummary": item.bridge_summary,
                "topMetabolites": item.top_metabolites,
            }
            for item in registry.compact_overview
        ],
        "nodes": nodes,
        "edges": edges,
        "reactionNodes": reaction_nodes,
    }
