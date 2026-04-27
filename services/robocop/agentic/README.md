# RoBoCop DeepAgents supervisor (offline prototype)

> Status: prototype, **offline-only**. Not used by the production web,
> API, or worker paths. Recommendations are advisory until the parity
> gate against the existing LangGraph runner passes on a fixture set.

This directory implements the deferred "DeepAgents RoBoCop supervisor"
direction declared in:

- `AgentOps/Tasks.md` - "DeepAgents RoBoCop supervisor" workstream
- `AgentOps/CalibrationOps.md` - "DeepAgents direction"
- `AgentOps/Playbooks.md` - "DeepAgents RoBoCop prototype"

It is built on `langchain-ai/deepagents` (`create_deep_agent`), which
returns a compiled LangGraph graph. The deterministic scientific core
(`src/MM_calibration.py`, `src/equadiff_brodbar.py`, `src/main.py`)
remains the source of truth.

## Boundary contract

- The supervisor must **never** mutate `src/`, `config/`, `api/`,
  `apps/`, or production calibration artifacts.
- Tools are an explicit allow-list defined in `tools.py`.
- Mutating tools (currently only `append_recommendation`) write under
  `Simulations/robocop_agentic/` only.
- `run_strategy_race` and `run_teacher_flux_rescue` are **dry-run** in
  the prototype: they return the plan a real run would execute. Real
  execution stays in `scripts/run_bounded_autosearch.py`.
- The supervisor's final assistant message is a JSON object with
  `comparison_to_langgraph_required: true`. Promotion requires running
  `compare_with_langgraph.py` on a real LangGraph decision and getting
  agreement.

## Files

- `prompts.py` - supervisor + subagent system prompts. Encodes the
  promotion gate, protected anchors, and discard triggers from
  `AgentOps/CalibrationOps.md`.
- `tools.py` - `build_tool_registry()` returning the LangChain tool
  list, plus `SUBAGENT_TOOL_ACL` for subagent allow-lists.
- `subagents.py` - `planner`, `triage_analyst`, and `archivist`
  subagent dicts in the `deepagents` `SubAgent` shape.
- `robocop_deep_agent.py` - `build_robocop_deep_agent(...)` wraps
  `deepagents.create_deep_agent`.
- `offline_runner.py` - CLI entrypoint that runs a single supervisor
  invocation and writes a result JSON under
  `Simulations/robocop_agentic/runs/<timestamp>/`.
- `compare_with_langgraph.py` - parity gate that compares an offline
  result to a LangGraph autosearch decision JSON.

## Install (local only)

```powershell
pip install -r requirements.txt
```

The agentic deps (`deepagents`, `langchain`, `langchain-openai`) are
pinned in the root `requirements.txt` under the explicit
"RoBoCop Agentic Supervisor" section. The production deployment
manifests (`api/requirements.txt`,
`apps/calibration-worker/requirements.txt`,
`apps/research-api/requirements.txt`,
`apps/monitoring-api/requirements.txt`) are self-contained and do
NOT pull from the root `requirements.txt`, so the agentic stack
remains isolated from production runtime images.

## Required environment

- `OPENAI_API_KEY` - the prototype defaults to `openai:gpt-5.5`
  via `init_chat_model` resolution.
- Optional: `ROBOCOP_DEEPAGENT_MODEL=openai:gpt-5.4` (or any
  `provider:model` id supported by `deepagents`/`langchain` chat
  models).
- Optional LangSmith tracing (already set up by
  `services/robocop/tracing.py`):
  - `LANGSMITH_TRACING=true`
  - `LANGSMITH_API_KEY=...`
  - `LANGSMITH_PROJECT=robocop` (or any project name)

## Usage

### Offline single-shot run

```powershell
python -m services.robocop.agentic.offline_runner `
  --goal "Triage Phase 5b purine_transport best params" `
  --session-path Simulations/brodbar/calibration/purine_phase5b_bordbar_ic/best_params.json
```

The result JSON is written to
`Simulations/robocop_agentic/runs/<utc-timestamp>/result.json` and the
final assistant text is parsed (best-effort) into a `structured_recommendation`.

### Parity check against LangGraph

```powershell
python -m services.robocop.agentic.compare_with_langgraph `
  --agentic-result   Simulations/robocop_agentic/runs/<stamp>/result.json `
  --langgraph-decision Simulations/.../session_<id>.json
```

Exit code is `0` on agreement, `1` on disagreement. The full report is
written under `Simulations/robocop_agentic/comparisons/<utc-timestamp>/comparison.json`.

## Promotion criteria

Per `AgentOps/CalibrationOps.md` and `AgentOps/Playbooks.md`:

- The prototype graduates from "advisory" to "supervisor candidate"
  only after **multiple agreements** with the LangGraph runner on a
  fixture set, with **zero** `keep` recommendations that LangGraph
  would have classified as `discard` or `informative`.
- LangSmith traces must show the planner / triage_analyst / archivist
  subagents under the supervisor root with useful metadata
  (candidate id, run dir, verdict).
- `qa/robocop` continues to pass.

## What is intentionally NOT included

- No `execute` shell tool. The supervisor never spawns ad-hoc shell
  commands; the only subprocess it can spawn is
  `scripts/run_bounded_autosearch.py` via the bounded
  `run_bounded_autosearch_subprocess` tool, and only when
  `allow_mutations=True`.
- No `write_file` / `edit_file` outside the agentic sandbox. The
  default deepagents filesystem backend is in-memory state and has no
  read/write access to repo files.
- No DeepAgents CLI (`deepagents deploy`).
- No write access to the canonical `autosearch_decisions.jsonl`
  ledger - the autonomous runner writes to a separate
  `Simulations/robocop_agentic/campaign_decisions.jsonl`.

## Path 3: autonomous campaign runner

`scripts/run_agentic_autosearch.py` is the autonomous sibling of
`scripts/run_bounded_autosearch.py`. The deterministic runner is
unchanged and remains the source of truth.

The autonomous runner:

- builds the supervisor with `allow_mutations=True` and a
  `CampaignBudget` (iteration cap, wall-clock cap, USD cap, tool-call
  cap, anchor-regression threshold);
- loops the supervisor up to `--max-iterations` times;
- each iteration the supervisor calls
  `run_bounded_autosearch_subprocess(spec)` exactly once, runs triage
  on the result, and writes a verdict via `append_campaign_decision`;
- stops on any of: budget exhausted, kill-switch file present
  (`Simulations/robocop_agentic/STOP`), or supervisor recommended
  `keep`.

Hard caps inside the subprocess tool itself (`max_iterations<=3`,
`loop_budget_seconds<=1800`) are independent of the campaign budget.
Asking for more does not raise the cap.

### Run the autonomous campaign

```powershell
python -m scripts.run_agentic_autosearch `
  --campaign-id phase6_purine_amp_repair `
  --base-policy   <repo-relative seed policy JSON> `
  --base-manifest <repo-relative seed manifest JSON> `
  --max-iterations 3 `
  --max-wall-seconds 1800 `
  --max-usd 3.00
```

Kill switch:

```powershell
New-Item Simulations\robocop_agentic\STOP -ItemType File -Force
```

Artifacts:

- `Simulations/robocop_agentic/campaign_runs/<campaign_id>_<utc>/iter_<n>/result.json`
- `Simulations/robocop_agentic/campaign_runs/<campaign_id>_<utc>/iter_<n>/messages.json`
- `Simulations/robocop_agentic/campaign_runs/<campaign_id>_<utc>/campaign_summary.json`
- ledger entry per iteration in `Simulations/robocop_agentic/campaign_decisions.jsonl`
