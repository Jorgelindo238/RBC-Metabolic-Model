# Autosearch Architecture

This document defines the architectural boundaries, structure, and implementation details for the agent-driven calibration strategy orchestration layer (the "Autosearch Runner").

This design draws inspiration from `Hermes-Agent` (structured decomposition, memory, tool-driven orchestration) and `ShinkaEvolve` (bounded evolutionary search, keep/discard logic), while remaining strictly within the existing scientific benchmarks of the RBC Metabolic Model.

## Current Status Note

As of `2026-04-17`, this document still describes the Bordbar-focused bounded autosearch runner accurately, but it is no longer the whole orchestration story.

The repo now also contains a product-plane custom-data orchestration layer with:

- dataset-aware planning
- calibration-report triage
- pure-ODE triage
- combined verdict logic
- worker-side `strategy_race`
- dataset fingerprint memory
- bounded teacher-flux rescue for supported reactions

Those newer product-plane components live under `services/robocop/` and `apps/api/services/`, while this document remains the reference for the original bounded autosearch runner around policy and manifest mutation.

## Motivation
The RBC calibration process relies on manually defined policies and manifests. The bounded autosearch runner iteratively mutates calibration strategies (policies/manifests), executes the existing benchmark harness, and promotes or discards the results based on rigorous evaluation logic.

## Boundary Definitions

To ensure the scientific core remains uncorrupted by automated search loops, we establish three distinct mutation boundaries:

### 1. `SCIENTIFIC_FROZEN` (Immutable)
- **What:** The base ODE model, scientific equations, fixed reaction mappings, and source experimental data.
- **Files:** `src/equadiff_brodbar.py`, `src/MM_calibration.py` (core logic), `RBC/Rxn_RBC.txt`, `src/*.xlsx`, and prior benchmark outputs/artifacts.
- **Rule:** The orchestrator CANNOT read, write, or mutate these files. They are mathematically and scientifically frozen from the perspective of the orchestration agent.

### 2. `AUTOSEARCH_BOUNDED` (Orchestration Target)
- **What:** The configuration templates and generated candidate payloads.
- **Files:** `config/policy_*.json`, `config/rbc_calibration_benchmarks.json`, and outputs under `config/generated/`.
- **Rule:** The orchestrator reads base templates from `config/` and creates mutated candidates ONLY inside `config/generated/`. Mutation rules are strictly regulated by `config/autoresearch_mutation_policy.yaml`.

### 3. `AUTOSEARCH_SAFE` (Execution & State)
- **What:** The execution scripts, benchmark harness inputs/outputs, and the orchestration state/registry memory.
- **Files:** `scripts/run_calibration_job.py`, `scripts/run_calibration_eval.py`, `eval_summary.json`, and the orchestration runner `scripts/run_bounded_autosearch.py`.
- **Rule:** The orchestrator interacts actively with these interfaces to launch jobs, read results, evaluate success, and archive search history.

## LangGraph State Machine

The bounded runner now uses a reusable RoBoCop runtime layer in `services/robocop/runtime.py`. The CLI entrypoint in `scripts/run_bounded_autosearch.py` still owns the validated proposer, evaluator, decision, and archive logic, but graph construction and invocation now live behind a reusable RoBoCop runtime seam.

The compiled LangGraph `StateGraph` remains the single bounded cycle:

```text
START → load_request_context → propose_candidate → evaluate_candidate → derive_decision → archive_result → END
```

To better match the overnight `autoresearch` spirit from Karpathy’s repo, the CLI runner now wraps that bounded graph in a **session loop**:

```text
session(start)
  → iteration 1: bounded graph
  → iteration 2: bounded graph (using promoted Keep candidate as the next base policy)
  → iteration N: bounded graph
  → session summary
```

This preserves the scientific safety boundary because each iteration still mutates only bounded config files, but it adds the key autonomous behavior that matters for overnight runs:

- repeated bounded experiments in one invocation
- Keep/Discard advancement instead of one-off mutation
- a persistent session summary you can inspect in the morning

### State Schema (`SearchState` / `RoBoCopState`)

The shared state flowing through all nodes is a `TypedDict` with these fields:

| Field | Type | Set By |
|---|---|---|
| `base_policy_path` | `str` | Caller (initial state) |
| `base_manifest_path` | `str` | Caller (initial state) |
| `mutation_policy_path` | `str` | Caller (initial state) |
| `dry_run` | `bool` | Caller (initial state) |
| `iteration` | `int` | Caller (initial state) |
| `workflow_type` | `str` | caller / `load_request_context` |
| `workflow_name` | `str` | caller / `load_request_context` |
| `orchestration_runtime` | `str` | `load_request_context` |
| `trace_status` | `dict` | `load_request_context` |
| `candidate_policy_path` | `str` | `propose_candidate` |
| `candidate_manifest_path` | `str` | `propose_candidate` |
| `job_spec_path` | `str` | `propose_candidate` |
| `mutation_summary` | `str` | `propose_candidate` |
| `mutation_significance` | `dict` | `propose_candidate` |
| `run_dir` | `str` | `evaluate_candidate` |
| `job_payload` | `dict` | `evaluate_candidate` |
| `execution_command` | `list[str]` | `evaluate_candidate` |
| `evaluator_status` | `str` | `evaluate_candidate` |
| `evaluator_returncode` | `int` | `evaluate_candidate` |
| `eval_summary_path` | `str` | `evaluate_candidate` |
| `completed_run_manifest_path` | `str` | `evaluate_candidate` |
| `aggregate_score` | `float` | `derive_decision` |
| `time_aware_score` | `float` | `derive_decision` |
| `mean_final_loss` | `float` | `derive_decision` |
| `benchmark_summary` | `dict` | `derive_decision` |
| `artifact_refs` | `dict` | `derive_decision` |
| `benchmark_status` | `str` | `derive_decision` |
| `completion_status` | `str` | `derive_decision` |
| `decision_category` | `str` | `derive_decision` |
| `decision` | `str` | `derive_decision` |
| `reason` | `str` | `derive_decision` |
| `decision_record_path` | `str` | `archive_result` |
| `local_decision_path` | `str` | `archive_result` |

### Node Descriptions

1. **`load_request_context` (Runtime Context)**
   - Normalizes workflow identity under RoBoCop.
   - Attaches non-blocking LangSmith trace status (`configured`, `env_disabled`, `missing_api_key`, or `langsmith_not_installed`).
   - Establishes the runtime seam without changing scientific execution.

2. **`propose_candidate` (Mutation)**
   - Reads the base policy JSON and the mutation policy YAML.
   - Applies a single bounded mutation from the `mutation_space` defined in the base policy, selecting a value that differs from the current base setting to avoid no-op mutations.
   - Writes the candidate policy and manifest to `config/generated/`.
   - Constructs a job spec JSON for the evaluator.
   - Outputs: `candidate_policy_path`, `candidate_manifest_path`, `job_spec_path`, `mutation_summary`.

3. **`evaluate_candidate` (Benchmark Runner)**
   - Constructs a subprocess call to `scripts/run_calibration_job.py` with the job spec.
   - Passes `--dry-run` when appropriate.
   - Parses the structured JSON payload from stdout.
   - Outputs: `run_dir`, `job_payload`.

4. **`derive_decision` (Result Triage)**
   - Skips verification during dry runs (returns `Keep` with null metrics).
   - For real runs: reads `eval_summary.json` from the run directory.
   - Extracts `aggregate_score` and `mean_final_loss`.
   - Applies the current time-aware feasibility rule through the validated decision logic.
   - Extracts `artifact_refs` from the `run_registry_record` payload when available.
   - Outputs: `aggregate_score`, `mean_final_loss`, `decision`, `reason`, `benchmark_summary`, `artifact_refs`.

5. **`archive_result` (Persistent Memory)**
   - Constructs a unified decision record from the full accumulated state.
   - Writes a local `autosearch_decision.json` to the run directory (for real runs only).
   - Returns archive output paths into shared state so traces can surface archive-specific metadata.
   - **Appends a single JSON line** to the global memory ledger at `Simulations/brodbar/autoresearch/agent_orchestration/autosearch_memory.jsonl`.
   - Every run—dry or real, pass or fail—writes exactly one line to the global ledger.

## LangSmith Tracing Boundary

LangSmith tracing is now attached additively through `services/robocop/tracing.py`.

- Tracing is enabled only when environment configuration is present.
- The bounded runner remains functional when tracing is disabled or unconfigured.
- Trace metadata is intended for orchestration observability and does not replace scientific outputs or artifact contracts.

The current trace payload is designed to carry:

- workflow type and workflow name
- candidate id
- base policy and manifest references
- candidate and job-spec paths
- mutation summary
- run directory
- evaluator status
- evaluator return code
- benchmark status
- completion status
- decision category and outcome
- time-aware runtime and coverage fields when available
- archive output paths when available

This tracing layer has now been validated against a real LangSmith project with a non-dry bounded cycle. The workflow run and explicit node traces appear in LangSmith, and the root workflow metadata carries the expected candidate, mutation, completion, benchmark, decision, and time-aware fields. A small follow-up enrichment now adds node-specific tags and metadata so individual node traces expose clearer evaluation, decision, and archive context.

## Persistent Memory Layer

### Global Ledger

The append-only JSONL log at:

```
Simulations/brodbar/autoresearch/agent_orchestration/autosearch_memory.jsonl
```

serves as the durable memory of all autosearch experiments. Each JSON line contains the full decision record schema:

```json
{
  "timestamp": "ISO 8601 UTC",
  "candidate_id": "derived from candidate policy filename",
  "iteration": 1,
  "dry_run": true,
  "base_policy_path": "config/policy_vmax_then_km.json",
  "base_manifest_path": "config/rbc_calibration_benchmarks.json",
  "candidate_policy_path": "config/generated/policy_candidate_<ts>.json",
  "candidate_manifest_path": "config/generated/manifest_candidate_<ts>.json",
  "mutation_summary": "Mutated atp_focus from False to True",
  "decision": "Keep | Discard",
  "reason": "human-readable decision justification",
  "run_dir": "path to completed run directory or DRY_RUN",
  "aggregate_score": null,
  "mean_final_loss": null,
  "benchmark_summary": null,
  "artifact_refs": null
}
```

### Local Decision File

For real (non-dry) runs that produce a `run_dir`, a copy of the decision record is also written as `autosearch_decision.json` inside the run directory for co-location with other benchmark artifacts.

## CLI Usage

```bash
# Dry run (validates mutation, job spec, and evaluation delegation without running calibration)
python scripts/run_bounded_autosearch.py \
  --base-policy config/policy_vmax_only.json \
  --base-manifest config/rbc_core_km_only_benchmarks.json \
  --dry-run

# Real bounded cycle
python scripts/run_bounded_autosearch.py \
  --base-policy config/policy_vmax_only.json \
  --base-manifest config/rbc_core_km_only_benchmarks.json

# Multi-iteration overnight-style session
python scripts/run_bounded_autosearch.py \
  --base-policy config/policy_vmax_then_km.json \
  --base-manifest config/rbc_calibration_benchmarks.json \
  --max-iterations 12 \
  --loop-budget-seconds 28800 \
  --case-time-budget-seconds 3600 \
  --timeout-policy continue
```

### Session semantics

- `--max-iterations` bounds how many bounded graph cycles run in one session.
- `--loop-budget-seconds` limits the full overnight session wall clock separately from per-candidate evaluator budgets.
- When an iteration returns `Keep`, the generated candidate policy becomes the **promoted base policy** for the next iteration, which is the config-space analogue of Karpathy’s “advance the branch if it improved”.
- Every session writes a session summary JSON under:

```text
Simulations/brodbar/autoresearch/agent_orchestration/sessions/
```

## Future Extensibility

The current implementation now supports multi-iteration sessions at the CLI/orchestration layer while keeping each graph invocation single-cycle and bounded. Remaining extensions include:

- **LLM-driven proposer** that queries the memory ledger and Context7 to reason over past trial histories before proposing new mutations.
- **Dynamic verification thresholds** retrieved from database baselines instead of the current static MVP threshold.
- **RoBoCop integration** for natural-language benchmark triage and explanation.
- The boundary between `SCIENTIFIC_FROZEN` and `AUTOSEARCH_BOUNDED` allows swapping in more complex AI logic without risking the integrity of underlying chemical equations or data structures.
