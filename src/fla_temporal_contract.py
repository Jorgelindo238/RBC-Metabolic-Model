"""Sequential temporal-block contract for Flux Learning Analysis."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

import numpy as np


@dataclass(frozen=True)
class TemporalBlock:
    name: str
    start_day: float
    end_day: float
    role: str
    concentration_targets: tuple[str, ...]
    flux_targets: tuple[str, ...]
    open_parameter_families: tuple[str, ...]
    protected_targets: tuple[str, ...]


TEMPORAL_BLOCKS = (
    TemporalBlock(
        name="J1_J3_initialization_energy",
        start_day=1.0,
        end_day=3.0,
        role="latent-state and Rapoport-Luebering/adenylate attribution",
        concentration_targets=("B23PG", "ATP", "ADP", "AMP", "G6P", "GO6P", "F6P"),
        flux_targets=("VGAPDH", "VPGK", "VDPGM", "V23DPGP", "VHK", "VPFK"),
        open_parameter_families=("latent_initial_states",),
        protected_targets=("EGLC", "GLC", "LAC", "ELAC", "PEP"),
    ),
    TemporalBlock(
        name="J3_J10_glycolytic_relay",
        start_day=3.0,
        end_day=10.0,
        role="match upper-to-lower glycolytic relay after initialization transient",
        concentration_targets=("GLC", "G6P", "F6P", "F16BP", "PEP", "PYR", "LAC", "ATP"),
        flux_targets=("VHK", "VPGI", "VG6PDH", "VPFK", "VGAPDH", "VPGK", "VPGM", "VENOPGM", "VPK", "VLDH"),
        open_parameter_families=("identified_glycolytic_kinetics",),
        protected_targets=("B23PG", "EGLC", "ELAC", "GSH", "GSSG"),
    ),
    TemporalBlock(
        name="J10_J46_transport_storage",
        start_day=10.0,
        end_day=46.0,
        role="storage transport, lactate export, and long-horizon preservation",
        concentration_targets=("EGLC", "ELAC", "GLC", "LAC", "ATP", "GSH", "GSSG"),
        flux_targets=("VEGLC", "VELAC", "VLDH", "VEGSH_rate", "VEGSSG"),
        open_parameter_families=("identified_transport_kinetics",),
        protected_targets=("G6P", "F6P", "B23PG", "PEP", "ADP", "AMP"),
    ),
)

NON_INDEPENDENT_STATE_TARGETS = frozenset({"B13PG", "P2G"})
REACTION_TEACHER_EXCLUSIONS = frozenset({"B13PG", "P2G", "P3G"})


def block_mask(time: Sequence[float], block: TemporalBlock) -> np.ndarray:
    values = np.asarray(time, dtype=float)
    return (values >= block.start_day - 1e-12) & (values <= block.end_day + 1e-12)


def validate_blocks(blocks: Sequence[TemporalBlock] = TEMPORAL_BLOCKS) -> None:
    if not blocks:
        raise ValueError("At least one temporal block is required")
    if blocks[0].start_day != 1.0 or blocks[-1].end_day != 46.0:
        raise ValueError("FLA temporal blocks must span J1-J46")
    for previous, current in zip(blocks, blocks[1:]):
        if previous.end_day != current.start_day:
            raise ValueError(f"Temporal gap or overlap between {previous.name} and {current.name}")
    for block in blocks:
        if block.start_day >= block.end_day:
            raise ValueError(f"Invalid bounds for {block.name}")
        forbidden = set(block.concentration_targets) & NON_INDEPENDENT_STATE_TARGETS
        if forbidden:
            raise ValueError(f"Non-independent concentration targets in {block.name}: {sorted(forbidden)}")


def promotion_contract() -> list[dict[str, Any]]:
    validate_blocks()
    out = []
    prior: list[str] = []
    for block in TEMPORAL_BLOCKS:
        out.append(
            {
                **asdict(block),
                "required_prior_blocks": prior.copy(),
                "promotion_requirements": [
                    "improve declared block objective",
                    "pass protected-target guards",
                    "retain all prior-block guards",
                    "pass J1-J46 whole-panel replay before global promotion",
                ],
            }
        )
        prior.append(block.name)
    return out


def sequential_promotion_allowed(
    assessments: Mapping[str, Mapping[str, bool]],
) -> tuple[bool, str | None]:
    for block in TEMPORAL_BLOCKS:
        local = assessments.get(block.name)
        if local is None:
            return False, f"missing assessment for {block.name}"
        failed = sorted(name for name, passed in local.items() if not bool(passed))
        if failed:
            return False, f"{block.name} failed: {', '.join(failed)}"
    return True, None


validate_blocks()
