# RBC Calibration Autoresearch

This document is the consolidated reference for the bounded autoresearch layer
of the RBC metabolic calibration project. It merges two previously separate
notes:

1. **Autoresearch Program** — the operational contract for hypothesis-driven
   bounded experiments (what to read, what to report, what to keep).
2. **Autosearch Architecture** — the LangGraph state machine, mutation
   boundaries, persistent memory layer, and CLI surface.

The two sections are complementary: the **Program** tells operators how to
run one experiment, while the **Architecture** tells engineers how the
bounded runner is wired. Both align with [`CALIBRATION_ORCHESTRATION.md`](CALIBRATION_ORCHESTRATION.md)
and use the triage guidance in [`CURVE_TRIAGE.md`](CURVE_TRIAGE.md).

---

# Part I — Autoresearch Program

## 1. Objective

You are optimizing the outer-loop calibration strategy for the RBC metabolic
model. Your job is to improve calibration quality through bounded,
eval-driven experiments. Optimize the configuration around the scientific
engine. **Do not rewrite the scientific engine unless the human explicitly
opens that scope.**

## 2. Primary metric

- Optimize `aggregate_score` from `eval_summary.json`.
- **Lower is better.**
- A candidate is not acceptable if it improves `aggregate_score` by
  sacrificing protected monitor metrics or violating the mutation policy.

## 3. Read before every run

- `AGENTS.md`
- `AgentOps/AUTORESEARCH.md` (this file)
- `config/autoresearch_mutation_policy.yaml`
- the selected policy template
- the selected benchmark manifest
- the latest `eval_summary.json` and relevant TSV history for the same manifest

## 4. Authoritative execution surface

- **Calibrator:** `src/MM_calibration.py`
- **Eval harness:** `scripts/run_calibration_eval.py`
- **Policy templates:** `config/*.json`
- **Fast benchmark gate:** `config/rbc_calibration_benchmarks.json`
- **Promotion benchmark gate:** `config/rbc_calibration_promotion_benchmarks.json`
- **Output root:** `Simulations/brodbar/autoresearch/`

## 5. Default mode

- Run in **config-only mutation mode**.
- Create candidate files under `config/generated/`.
- Treat committed templates in `config/` as read-only inputs.
- Never edit source code, reaction files, experimental data, or benchmark
  outputs in place.

## 6. Default experiment loop

1. State one hypothesis in one sentence.
2. Choose a single template policy and a single template manifest.
3. Copy them to candidate files under `config/generated/`.
4. Apply only the mutations allowed by
   `config/autoresearch_mutation_policy.yaml`.
5. Keep the mutation narrow. Prefer one cluster of knobs per run.
6. Run the fixed eval harness:

   ```bash
   python scripts/run_calibration_eval.py \
     --policy <candidate_policy> \
     --manifest <candidate_manifest>
   ```
7. Read the new `eval_summary.json` in the generated run directory.
8. Compare the new result to the best prior run for the same manifest.
9. Keep the candidate only if it improves benchmark evidence without
   violating protected metrics or guardrails.
10. Record a concise triage note with the exact configuration and rationale.

## 7. Required reporting after every run

Report all of the following:

- hypothesis
- exact policy path
- exact manifest path
- exact command run
- exact `target_scope`
- exact `param_scope`
- exact `optimization_strategy`
- `aggregate_score`
- `mean_final_loss`
- `mean_improvement_pct`
- `best_case`
- `worst_case`
- `status`
- notable protected metric changes
- recommendation: keep, discard, or queue for promotion

## 8. Protected metrics and scientific guardrails

- Preserve protected monitor metrics when adding or widening scopes.
- Compare before and after using benchmark artifacts, not a single figure.
- Prefer the narrowest parameter scope that tests the hypothesis.
- Avoid opening broad compensator parameters before the core mismatch is
  understood.
- Report scope changes explicitly whenever `target_scope`, `param_scope`,
  `parameter_classes`, or `stage_plan` differ from the template.
- Treat a local win that fails the promotion benchmark as non-promotable.

## 9. Keep and discard rules

### Keep a candidate only when all are true

- it respects `config/autoresearch_mutation_policy.yaml`,
- it improves `aggregate_score` for the same manifest or produces a clearly
  better protected-metric profile at equivalent score,
- it does not create an obvious regression in ATP, adenylate, extracellular,
  or other protected monitor behavior,
- the result can be explained by the stated hypothesis.

### Discard a candidate when any is true

- it edits files or fields outside the mutation policy,
- it depends on broad scope expansion without explicit approval,
- it wins only on a short horizon while failing the longer-horizon or
  ATP-guarded cases,
- it improves one case while materially worsening the weighted benchmark
  outcome,
- it cannot be justified from the benchmark artifacts.

## 10. Promotion rule

- Use the fast benchmark suite for search.
- Use `config/rbc_calibration_promotion_benchmarks.json` only as a promotion
  gate.
- Do not auto-promote a fast-benchmark winner without running the promotion
  suite.
- Do not mutate the promotion manifest unless the human explicitly opens
  that scope.

## 11. Prohibited actions

- Do not edit `src/MM_calibration.py`, `src/equadiff_brodbar.py`,
  `RBC/Rxn_RBC.txt`, experimental data files, or Streamlit app files in
  default mode.
- Do not edit prior `results.tsv`, `eval_summary.json`, or
  `calibration_report.json` files by hand.
- Do not change metric directionality. Lower `aggregate_score` remains
  better.
- Do not broaden mutation scope after a weak result just to chase a score.
- Do not claim promotion readiness without evidence from the promotion
  benchmark.

## 12. Preferred search posture

- Start from existing policy templates.
- Mutate one hypothesis at a time.
- Favor reproducible improvements over clever but brittle wins.
- Use ATP-guarded and longer-horizon cases to reject compensatory solutions.
- Treat the scientific core as stable until the human explicitly authorizes
  deeper mutation.

---

# Part II — Autosearch Architecture

This part defines the architectural boundaries, structure, and implementation
details for the agent-driven calibration strategy orchestration layer (the
**Autosearch Runner**).

This design draws inspiration from `Hermes-Agent` (structured decomposition,
memory, tool-driven orchestration) and `ShinkaEvolve` (bounded evolutionary
search, keep/discard logic), while remaining strictly within the existing
scientific benchmarks of the RBC Metabolic Model.

## 13. Motivation

The RBC calibration process relies on manually defined policies and
manifests. The bounded autosearch runner iteratively mutates calibration
strategies (policies/manifests), executes the existing benchmark harness,
and promotes or discards the results based on rigorous evaluation logic.

## 14. Boundary Definitions

To ensure the scientific core remains uncorrupted by automated search loops,
we establish three distinct mutation boundaries:

### 14.1 `SCIENTIFIC_FROZEN` (Immutable)

- **What:** The base ODE model, scientific equations, fixed reaction
  mappings, and source experimental data.
- **Files:** `src/equadiff_brodbar.py`, `src/MM_calibration.py` (core logic),
  `RBC/Rxn_RBC.txt`, `src/*.xlsx`, and prior benchmark outputs/artifacts.
- **Rule:** The orchestrator **cannot** read, write, or mutate these files.
  They are mathematically and scientifically frozen from the perspective of
  the orchestration agent.

### 14.2 `AUTOSEARCH_BOUNDED` (Orchestration Target)

- **What:** The configuration templates and generated candidate payloads.
- **Files:** `config/policy_*.json`, `config/rbc_calibration_benchmarks.json`,
  and outputs under `config/generated/`.
- **Rule:** The orchestrator reads base templates from `config/` and creates
  mutated candidates **only** inside `config/generated/`. Mutation rules are
  strictly regulated by `config/autoresearch_mutation_policy.yaml`.

### 14.3 `AUTOSEARCH_SAFE` (Execution & State)

- **What:** The execution scripts, benchmark harness inputs/outputs, and
  the orchestration state/registry memory.
- **Files:** `scripts/run_calibration_job.py`,
  `scripts/run_calibration_eval.py`, `eval_summary.json`, and the
  orchestration runner `scripts/run_bounded_autosearch.py`.
- **Rule:** The orchestrator interacts actively with these interfaces to
  launch jobs, read results, evaluate success, and archive search history.

## 15. LangGraph State Machine

The bounded runner uses a reusable RoBoCop runtime layer in
`services/robocop/runtime.py`. The CLI entrypoint in
`scripts/run_bounded_autosearch.py` owns the validated proposer, evaluator,
decision, and archive logic, but graph construction and invocation now live
behind a reusable RoBoCop runtime seam.

The compiled LangGraph `StateGraph` remains the single bounded cycle:

```text
START → load_request_context → propose_candidate → evaluate_candidate → derive_decision → archive_result → END
```

To better match the overnight `autoresearch` spirit from Karpathy's repo,
the CLI runner wraps that bounded graph in a **session loop**:

```text
session(start)
  → iteration 1: bounded graph
  → iteration 2: bounded graph (using promoted Keep candidate as the next base policy)
  → iteration N: bounded graph
  → session summary
```

This preserves the scientific safety boundary because each iteration still
mutates only bounded config files, but it adds the key autonomous behavior
that matters for overnight runs:

- repeated bounded experiments in one invocation,
- Keep/Discard advancement instead of one-off mutation,
- a persistent session summary you can inspect in the morning.

### 15.1 State Schema (`SearchState` / `RoBoCopState`)

The shared state flowing through all nodes is a `TypedDict` with these
fields:

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

### 15.2 Node Descriptions

1. **`load_request_context` (Runtime Context)**
   - Normalizes workflow identity under RoBoCop.
   - Attaches non-blocking LangSmith trace status (`configured`,
     `env_disabled`, `missing_api_key`, or `langsmith_not_installed`).
   - Establishes the runtime seam without changing scientific execution.

2. **`propose_candidate` (Mutation)**
   - Reads the base policy JSON and the mutation policy YAML.
   - Applies a single bounded mutation from the `mutation_space` defined in
     the base policy, selecting a value that differs from the current base
     setting to avoid no-op mutations.
   - Writes the candidate policy and manifest to `config/generated/`.
   - Constructs a job spec JSON for the evaluator.
   - Outputs: `candidate_policy_path`, `candidate_manifest_path`,
     `job_spec_path`, `mutation_summary`.

3. **`evaluate_candidate` (Benchmark Runner)**
   - Constructs a subprocess call to `scripts/run_calibration_job.py` with
     the job spec.
   - Passes `--dry-run` when appropriate.
   - Parses the structured JSON payload from stdout.
   - Outputs: `run_dir`, `job_payload`.

4. **`derive_decision` (Result Triage)**
   - Skips verification during dry runs (returns `Keep` with null metrics).
   - For real runs: reads `eval_summary.json` from the run directory.
   - Extracts `aggregate_score` and `mean_final_loss`.
   - Applies the current time-aware feasibility rule through the validated
     decision logic.
   - Extracts `artifact_refs` from the `run_registry_record` payload when
     available.
   - Outputs: `aggregate_score`, `mean_final_loss`, `decision`, `reason`,
     `benchmark_summary`, `artifact_refs`.

5. **`archive_result` (Persistent Memory)**
   - Constructs a unified decision record from the full accumulated state.
   - Writes a local `autosearch_decision.json` to the run directory (for
     real runs only).
   - Returns archive output paths into shared state so traces can surface
     archive-specific metadata.
   - **Appends a single JSON line** to the global memory ledger at
     `Simulations/brodbar/autoresearch/agent_orchestration/autosearch_memory.jsonl`.
   - Every run — dry or real, pass or fail — writes exactly one line to the
     global ledger.

## 16. LangSmith Tracing Boundary

LangSmith tracing is attached additively through
`services/robocop/tracing.py`.

- Tracing is enabled only when environment configuration is present.
- The bounded runner remains functional when tracing is disabled or
  unconfigured.
- Trace metadata is intended for orchestration observability and does not
  replace scientific outputs or artifact contracts.

The current trace payload is designed to carry:

- workflow type and workflow name,
- candidate id,
- base policy and manifest references,
- candidate and job-spec paths,
- mutation summary,
- run directory,
- evaluator status,
- evaluator return code,
- benchmark status,
- completion status,
- decision category and outcome,
- time-aware runtime and coverage fields when available,
- archive output paths when available.

This tracing layer has been validated against a real LangSmith project with
a non-dry bounded cycle. The workflow run and explicit node traces appear
in LangSmith, and the root workflow metadata carries the expected candidate,
mutation, completion, benchmark, decision, and time-aware fields. A small
follow-up enrichment adds node-specific tags and metadata so individual
node traces expose clearer evaluation, decision, and archive context.

## 17. Persistent Memory Layer

### 17.1 Global Ledger

The append-only JSONL log at:

```text
Simulations/brodbar/autoresearch/agent_orchestration/autosearch_memory.jsonl
```

serves as the durable memory of all autosearch experiments. Each JSON line
contains the full decision record schema:

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

### 17.2 Local Decision File

For real (non-dry) runs that produce a `run_dir`, a copy of the decision
record is also written as `autosearch_decision.json` inside the run
directory for co-location with other benchmark artifacts.

## 18. CLI Usage

```bash
# Dry run (validates mutation, job spec, and evaluation delegation
# without running calibration)
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

### 18.1 Session semantics

- `--max-iterations` bounds how many bounded graph cycles run in one session.
- `--loop-budget-seconds` limits the full overnight session wall clock
  separately from per-candidate evaluator budgets.
- When an iteration returns `Keep`, the generated candidate policy becomes
  the **promoted base policy** for the next iteration, which is the
  config-space analogue of Karpathy's "advance the branch if it improved".
- Every session writes a session summary JSON under:

```text
Simulations/brodbar/autoresearch/agent_orchestration/sessions/
```

## 19. Future Extensibility

The current implementation supports multi-iteration sessions at the
CLI/orchestration layer while keeping each graph invocation single-cycle
and bounded. Remaining extensions include:

- **LLM-driven proposer** that queries the memory ledger and Context7 to
  reason over past trial histories before proposing new mutations.
- **Dynamic verification thresholds** retrieved from database baselines
  instead of the current static MVP threshold.
- **RoBoCop integration** for natural-language benchmark triage and
  explanation.
- The boundary between `SCIENTIFIC_FROZEN` and `AUTOSEARCH_BOUNDED` allows
  swapping in more complex AI logic without risking the integrity of
  underlying chemical equations or data structures.

