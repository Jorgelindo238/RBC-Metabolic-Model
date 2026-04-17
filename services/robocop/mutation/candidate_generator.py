"""
Bounded candidate-generator v2 for the RoBoCop Mutation Agent.

Mutation strategy layers (explicit, auditable):
  1. Rich history extraction — scores, configs, fingerprints from memory
  2. Parent selection — reuse successful past configs as mutation seeds
  3. Multi-field mutation — bounded 1-2 field changes, history-guided
  4. Novelty filtering — reject near-duplicate proposals
  5. Candidate ranking — score by history support + novelty + parent adjacency

Ownership boundary:
  - RoBoCop owns orchestration, evaluation, decision, archival.
  - This module owns only the proposal strategy.
  - ShinkaEvolve may later evolve the propose_mutation() function body.

The function signature is the stable contract. Everything downstream
(file I/O, job spec, evaluate, verify, archive) is unchanged.
"""

import json
import random
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from typing import Any, Optional


AUTORESEARCH_MEMORY_PATH = Path(
    "Simulations/brodbar/autoresearch/agent_orchestration/autosearch_memory.jsonl"
)

MAX_MUTATED_FIELDS = 2
MULTI_FIELD_PROBABILITY = 0.35
EXPLORATION_BONUS = 0.5
NOVELTY_LOOKBACK = 10
SCORE_WEIGHT = 0.02


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class MutationProposal:
    """Result of a mutation proposal. Backward-compatible single-field attrs
    plus a mutations dict for multi-field support."""
    field: Optional[str] = None
    previous_value: Any = None
    new_value: Any = None
    allowed_values: Optional[list] = dataclass_field(default=None)
    selection_basis: str = "No mutation proposed."
    mutations: dict = dataclass_field(default_factory=dict)
    num_fields_mutated: int = 0


@dataclass
class _HistoryEntry:
    """Aggregated history for a single (field, value) pair."""
    keeps: int = 0
    discards: int = 0
    best_score: Optional[float] = None
    last_seen_idx: int = -1


@dataclass
class _HistoryState:
    """Full parsed history from the memory ledger."""
    field_value_map: dict = dataclass_field(default_factory=dict)
    parent_configs: list = dataclass_field(default_factory=list)
    recent_fingerprints: list = dataclass_field(default_factory=list)
    total_records: int = 0


# ---------------------------------------------------------------------------
# Memory loading
# ---------------------------------------------------------------------------

def load_memory(memory_path: Optional[Path] = None) -> list[dict]:
    """Load past decision records from the append-only JSONL memory ledger."""
    path = memory_path or AUTORESEARCH_MEMORY_PATH
    if not path.exists():
        return []
    records = []
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return records


# ---------------------------------------------------------------------------
# Phase 1: Rich history extraction
# ---------------------------------------------------------------------------

def _extract_rich_history(memory: list[dict]) -> _HistoryState:
    """Parse memory into structured history with scores, parents, fingerprints."""
    state = _HistoryState(total_records=len(memory))

    for idx, record in enumerate(memory):
        sig = record.get("mutation_significance")
        if not isinstance(sig, dict) or not sig.get("mutation_applied"):
            continue

        changed_field = sig.get("changed_field")
        new_val = sig.get("new_value")
        decision = record.get("orchestrator_decision") or record.get("decision")
        agg_score = record.get("aggregate_score")

        if changed_field is None or new_val is None:
            continue

        fv_key = (changed_field, str(new_val))
        if fv_key not in state.field_value_map:
            state.field_value_map[fv_key] = _HistoryEntry()

        entry = state.field_value_map[fv_key]
        entry.last_seen_idx = idx
        if decision == "Keep":
            entry.keeps += 1
        elif decision == "Discard":
            entry.discards += 1
        if isinstance(agg_score, (int, float)):
            if entry.best_score is None or agg_score < entry.best_score:
                entry.best_score = agg_score

        if decision == "Keep" and isinstance(agg_score, (int, float)):
            state.parent_configs.append({
                "idx": idx,
                "score": agg_score,
                "changed_field": changed_field,
                "new_value": new_val,
                "mutation_summary": record.get("mutation_summary", ""),
            })

        fp_mutations = {changed_field: new_val}
        fp = _build_fingerprint(fp_mutations)
        state.recent_fingerprints.append(fp)

    state.parent_configs.sort(key=lambda p: p["score"])
    return state


# ---------------------------------------------------------------------------
# Phase 2: Parent selection
# ---------------------------------------------------------------------------

def _select_parent(history: _HistoryState) -> Optional[dict]:
    """Pick a successful parent config biased toward best aggregate_score."""
    parents = history.parent_configs
    if not parents:
        return None
    if len(parents) == 1:
        return parents[0]
    top_half = parents[: max(1, len(parents) // 2)]
    return random.choice(top_half)


# ---------------------------------------------------------------------------
# Phase 3: Scoring helpers
# ---------------------------------------------------------------------------

def _score_entry(entry: _HistoryEntry, total_records: int) -> float:
    """Score a (field, value) pair from history. Higher = more promising."""
    if entry.keeps == 0 and entry.discards == 0:
        return EXPLORATION_BONUS

    score = entry.keeps * 1.0 - entry.discards * 0.3

    if isinstance(entry.best_score, (int, float)) and entry.best_score > 0:
        score += max(0.0, (50.0 - entry.best_score) * SCORE_WEIGHT)

    if total_records > 0 and entry.last_seen_idx >= 0:
        recency = entry.last_seen_idx / total_records
        score += recency * 0.1

    return score


def _score_untried() -> float:
    """Score for an untried (field, value) pair."""
    return EXPLORATION_BONUS + random.uniform(0, 0.1)


# ---------------------------------------------------------------------------
# Phase 4: Novelty filtering
# ---------------------------------------------------------------------------

def _build_fingerprint(mutations: dict) -> str:
    """Deterministic fingerprint for a set of mutations."""
    parts = sorted(f"{k}={v}" for k, v in mutations.items())
    return "|".join(parts)


def _is_novel(fingerprint: str, recent_fps: list[str], lookback: int) -> bool:
    """Check if a fingerprint is novel against recent history."""
    window = recent_fps[-lookback:] if lookback < len(recent_fps) else recent_fps
    return fingerprint not in window


# ---------------------------------------------------------------------------
# Phase 5: Candidate generation and ranking
# ---------------------------------------------------------------------------

@dataclass
class _ScoredCandidate:
    mutations: dict
    score: float
    basis: str
    primary_field: str
    primary_value: Any


def _generate_single_field_candidates(
    base_run: dict,
    mutation_space: dict,
    history: _HistoryState,
) -> list[_ScoredCandidate]:
    """Generate all single-field mutation candidates with scores."""
    candidates = []
    for field_name, allowed_values in mutation_space.items():
        current = base_run.get(field_name)
        for value in allowed_values:
            if value == current:
                continue
            fv_key = (field_name, str(value))
            entry = history.field_value_map.get(fv_key)
            if entry:
                score = _score_entry(entry, history.total_records)
                basis = f"history(K={entry.keeps},D={entry.discards},best={entry.best_score})"
            else:
                score = _score_untried()
                basis = "untried"
            candidates.append(_ScoredCandidate(
                mutations={field_name: value},
                score=score,
                basis=basis,
                primary_field=field_name,
                primary_value=value,
            ))
    return candidates


def _generate_multi_field_candidates(
    base_run: dict,
    mutation_space: dict,
    history: _HistoryState,
    parent: Optional[dict],
) -> list[_ScoredCandidate]:
    """Generate bounded 2-field mutation candidates.
    Sources: parent-guided combinations + top history-supported pairs."""
    candidates = []
    fields = list(mutation_space.keys())
    if len(fields) < 2:
        return candidates

    if parent:
        parent_field = parent.get("changed_field")
        parent_value = parent.get("new_value")
        if parent_field in mutation_space:
            for other_field in fields:
                if other_field == parent_field:
                    continue
                current_other = base_run.get(other_field)
                other_values = [v for v in mutation_space[other_field] if v != current_other]
                if not other_values:
                    continue
                other_val = random.choice(other_values)
                combo_score = 0.0
                fv1 = (parent_field, str(parent_value))
                fv2 = (other_field, str(other_val))
                e1 = history.field_value_map.get(fv1)
                e2 = history.field_value_map.get(fv2)
                combo_score += _score_entry(e1, history.total_records) if e1 else _score_untried()
                combo_score += _score_entry(e2, history.total_records) if e2 else _score_untried()
                combo_score *= 0.85
                candidates.append(_ScoredCandidate(
                    mutations={parent_field: parent_value, other_field: other_val},
                    score=combo_score,
                    basis=f"parent-guided({parent_field}={parent_value})+{other_field}={other_val}",
                    primary_field=parent_field,
                    primary_value=parent_value,
                ))
                if len(candidates) >= 5:
                    break

    top_singles = sorted(
        history.field_value_map.items(),
        key=lambda x: _score_entry(x[1], history.total_records),
        reverse=True,
    )[:4]
    for i, ((f1, v1_str), _) in enumerate(top_singles):
        for (f2, v2_str), _ in top_singles[i + 1:]:
            if f1 == f2:
                continue
            v1 = _try_parse_value(v1_str)
            v2 = _try_parse_value(v2_str)
            if f1 not in mutation_space or f2 not in mutation_space:
                continue
            if v1 not in mutation_space.get(f1, []) or v2 not in mutation_space.get(f2, []):
                continue
            if v1 == base_run.get(f1) and v2 == base_run.get(f2):
                continue
            e1 = history.field_value_map.get((f1, v1_str))
            e2 = history.field_value_map.get((f2, v2_str))
            combo_score = 0.0
            combo_score += _score_entry(e1, history.total_records) if e1 else 0.0
            combo_score += _score_entry(e2, history.total_records) if e2 else 0.0
            combo_score *= 0.8
            candidates.append(_ScoredCandidate(
                mutations={f1: v1, f2: v2},
                score=combo_score,
                basis=f"top-pair({f1}={v1},{f2}={v2})",
                primary_field=f1,
                primary_value=v1,
            ))

    return candidates


def _try_parse_value(s: str) -> Any:
    """Try to recover the original type from a stringified value."""
    if s in ("True", "true"):
        return True
    if s in ("False", "false"):
        return False
    try:
        if "." in s:
            return float(s)
        return int(s)
    except (ValueError, TypeError):
        return s


def _rank_and_filter(
    candidates: list[_ScoredCandidate],
    recent_fps: list[str],
) -> list[_ScoredCandidate]:
    """Rank candidates by score, apply novelty filter, add jitter for diversity."""
    for c in candidates:
        fp = _build_fingerprint(c.mutations)
        if not _is_novel(fp, recent_fps, NOVELTY_LOOKBACK):
            c.score -= 1.5
            c.basis += " [novelty-penalized]"
        c.score += random.uniform(0, 0.08)

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates


# ---------------------------------------------------------------------------
# Main proposal function
# ---------------------------------------------------------------------------

# EVOLVE-BLOCK-START
def propose_mutation(
    base_run: dict,
    mutation_space: dict,
    memory: Optional[list[dict]] = None,
) -> MutationProposal:
    """
    RoBoCop-native Mutation Agent v2.

    Strategy layers:
    1. Extract rich history (scores, parents, fingerprints) from memory.
    2. Select a parent from past Keep outcomes (best aggregate_score).
    3. Generate single-field candidates (history-scored + exploration).
    4. Generate bounded 2-field candidates (parent-guided + top-pair).
    5. Apply novelty filter against recent proposals.
    6. Rank all candidates and pick the best.
    7. Return MutationProposal with backward-compatible primary field
       plus full mutations dict for multi-field support.
    """
    if not mutation_space:
        return MutationProposal(selection_basis="No mutation space defined.")

    history = _extract_rich_history(memory) if memory else _HistoryState()
    parent = _select_parent(history)

    singles = _generate_single_field_candidates(base_run, mutation_space, history)
    multis = []
    if random.random() < MULTI_FIELD_PROBABILITY or parent:
        multis = _generate_multi_field_candidates(
            base_run, mutation_space, history, parent,
        )

    all_candidates = singles + multis
    if not all_candidates:
        return MutationProposal(
            selection_basis="No non-trivial mutation available in mutation_space.",
        )

    ranked = _rank_and_filter(all_candidates, history.recent_fingerprints)
    top_tier = [c for c in ranked if c.score >= ranked[0].score - 0.2]
    chosen = random.choice(top_tier) if len(top_tier) > 1 else ranked[0]

    primary_field = chosen.primary_field
    primary_prev = base_run.get(primary_field)
    primary_new = chosen.primary_value

    n = len(chosen.mutations)
    if n == 1:
        basis_detail = f"v2-single|{chosen.basis}"
    else:
        parts = [f"{k}:{base_run.get(k)}->{v}" for k, v in chosen.mutations.items()]
        basis_detail = f"v2-multi({n})|{chosen.basis}|changes={','.join(parts)}"

    field_list = list(mutation_space.get(primary_field, []))

    return MutationProposal(
        field=primary_field,
        previous_value=primary_prev,
        new_value=primary_new,
        allowed_values=field_list if field_list else None,
        selection_basis=basis_detail,
        mutations=chosen.mutations,
        num_fields_mutated=n,
    )
# EVOLVE-BLOCK-END
