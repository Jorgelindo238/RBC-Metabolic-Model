# AgentOps

AgentOps is the operational cockpit for Codex on the airbc / RoBoCop repository.
It should make the next useful action obvious without forcing the agent to reread
long historical notes.

## Read order

Always read:
- `AgentOps/Tasks.md` for the current objective, next action, blockers, and active workstreams.
- `AgentOps/OperatingManual.md` for execution, validation, security, git, and reporting rules.

Read when relevant:
- `AgentOps/Memory.md` for durable lessons and failure patterns.
- `AgentOps/Playbooks.md` for recurring workflows.
- `AgentOps/CalibrationOps.md` for RoBoCop calibration, autoresearch, LangGraph, LangSmith, and DeepAgents planning.
- `AgentOps/Archive.md` only when a historical decision or scientific run history is needed.

## Operating principle

Keep this folder useful for a high-reasoning coding agent:
- short active instructions
- explicit next actions
- stable rules separated from history
- scientific guardrails separated from product notes
- archive material out of the default context path

## Current platform shape

- Product identity: `airbc`
- Product domains:
  - `airbc.org` for marketing
  - `app.airbc.org` for web
  - `api.airbc.org` for the core API
  - `calibration-api.airbc.org` for the Hetzner calibration worker
- Main repo: `Jorgelindo238/RBC-Metabolic-Model`
- Main branch: `main`

## Quick routing

For production/deployment work:
- read `Tasks.md`
- use the production smoke playbook in `Playbooks.md`
- keep secrets out of Git

For UI/product work:
- read `Tasks.md`
- read the relevant product memory in `Memory.md`
- validate with build/typecheck/browser when possible

For calibration/RoBoCop work:
- read `CalibrationOps.md`
- use `Playbooks.md`
- preserve the deterministic scientific core

For old run history:
- search `Archive.md`
- only then inspect generated artifacts under `Simulations/` if needed
