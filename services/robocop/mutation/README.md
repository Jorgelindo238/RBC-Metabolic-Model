# RoBoCop Mutation Agent v2 — Bounded Candidate Generator

## What This Module Does

`candidate_generator.py` contains the mutation proposal logic for the RoBoCop bounded autosearch system. It decides **which fields to mutate** and **what values to set**, informed by the history of past decisions.

## v2 Strategy Layers

The generator uses five explicit, auditable strategy layers:

### 1. Rich History Extraction
Parses the `autosearch_memory.jsonl` ledger into structured data:
- Per `(field, value)` pair: keep count, discard count, best aggregate_score, recency
- Parent configs: full records from Keep outcomes with numeric scores
- Recent fingerprints: deterministic mutation signatures for novelty checking

### 2. Parent Selection
Picks a successful past config (Keep outcome with best aggregate_score) as a seed for mutation. Biased toward the top-scoring half of parents.

### 3. Candidate Generation (single + multi-field)
- **Single-field:** Scores every `(field, non-current-value)` pair using history support + exploration bonus for untried values.
- **Multi-field (max 2):** Two sources:
  - **Parent-guided:** Reuse the parent's successful field + combine with another field
  - **Top-pair:** Combine the two highest-scoring single-field values from history
- Multi-field candidates are score-discounted (0.8-0.85x) to avoid runaway combinatorics.
- Multi-field probability: 35% base, always attempted when a parent is available.

### 4. Novelty Filtering
Penalizes candidates whose fingerprint matches recent proposals (last 10 in memory). Fingerprints use deterministic `field=value` format for exact matching.

### 5. Candidate Ranking
All candidates (single + multi) are ranked by composite score with small random jitter for diversity. The top tier (within 0.2 of best) is sampled uniformly.

## Ownership Boundaries

| Owner | Responsibilities |
|---|---|
| **RoBoCop** (`run_bounded_autosearch.py`) | Orchestration, mutation_space constraints, evaluation trigger, keep/discard decision, archival, memory ledger |
| **This module** (`candidate_generator.py`) | Bounded mutation proposal: which fields, which values, informed by history |
| **ShinkaEvolve** (Phase C, future) | Evolving the `propose_mutation()` function body to discover better strategies |

## Output Contract

`propose_mutation()` returns a `MutationProposal` with:
- `field` / `previous_value` / `new_value` / `allowed_values` — backward-compatible primary mutation
- `mutations: dict` — all field changes (supports multi-field)
- `num_fields_mutated: int` — 1 or 2
- `selection_basis: str` — auditable explanation of why this mutation was chosen

The downstream pipeline (file I/O, job spec, evaluate, verify, archive) is unchanged. `mutation_significance` in the archive tracks the primary field for contract compatibility.

## Future ShinkaEvolve Seam

The `propose_mutation()` function body is wrapped with `EVOLVE-BLOCK-START` / `EVOLVE-BLOCK-END`. The internal structure (history extraction, parent selection, candidate generation, novelty, ranking) provides clear hooks for ShinkaEvolve to optimize when integrated in Phase C.
