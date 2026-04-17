# RoBoCop Runtime

## Purpose

`services/robocop/` is the home of RoBoCop's reusable orchestration runtime surface.

In this phase, RoBoCop owns:
- a minimal LangGraph orchestration skeleton
- a minimal LangSmith-compatible tracing layer
- reusable runtime helpers that wrap the existing bounded search flow without replacing evaluator, manifest, registry, or archive truth
- node-aware trace metadata and tag helpers that make workflow and per-node observability explicit

## Current structure

- `runtime.py`
  - builds the first reusable RoBoCop LangGraph workflow
  - defines the explicit orchestration skeleton:
    - `load_request_context`
    - `propose_candidate`
    - `evaluate_candidate`
    - `derive_decision`
    - `archive_result`
- `tracing.py`
  - provides additive LangSmith tracing helpers
  - enables tracing only when the environment is configured
- `trace_context.py`
  - builds the trace metadata, node-specific tags, and compact state snapshots shared by the runtime
- `mutation/`
  - contains the bounded RoBoCop Mutation Agent v2 candidate generator

## Current boundary

The runtime layer does not replace:
- `scripts/run_calibration_eval.py`
- `scripts/run_calibration_job.py`
- `scripts/calibration_artifacts.py`
- `scripts/run_registry.py`
- the append-only autosearch decision ledger

Those remain the source-of-truth layers for scientific evaluation, completed-run manifests, registry projections, and archive records.

## LangSmith enablement

Tracing is non-blocking and environment-gated.

Expected environment variables:
- `LANGSMITH_TRACING=true` or `LANGCHAIN_TRACING_V2=true`
- `LANGSMITH_API_KEY=...`
- optional `LANGSMITH_PROJECT=robocop`
- optional `LANGSMITH_ENDPOINT=...`
- optional `LANGSMITH_WORKSPACE_ID=...` for org-scoped API keys

If tracing is not configured, RoBoCop continues to run normally without emitting LangSmith traces.

The traced bounded workflow has now been verified both in dry-run mode and against a real bounded cycle. LangSmith shows:
- the root workflow run
- explicit node traces for `load_request_context`, `propose_candidate`, `evaluate_candidate`, `derive_decision`, and `archive_result`
- root metadata for candidate identity, mutation summary, completion status, benchmark status, decision category/outcome, and time-aware fields
- per-node metadata/tag enrichment for evaluation, decision, and archive-specific context on subsequent traced runs

## Why this seam exists now

RoBoCop already has:
- a bounded Mutation Agent
- a validated evaluator path
- time-aware completion and archive contracts

This runtime layer makes the orchestration structure explicit and creates the clean seam needed for later:
- more explicit Decision Agent logic
- more explicit Archivist Agent logic
- LangChain tool attachment
- future Shinka-backed bounded mutation upgrades
