# CalibrationOps

Operational reference for RoBoCop calibration, bounded autoresearch, triage,
LangGraph/LangSmith, and the future DeepAgents supervisor.

## Non-negotiable boundary

The agent may orchestrate experiments, but the deterministic scientific core
remains the source of truth.

- `src/MM_calibration.py`: canonical calibration orchestration core.
- `src/equadiff_brodbar.py`: ODE/scientific model core; protect unless scope is explicitly opened.
- `src/main.py`: official pure-ODE replay path.
- Generated stage plans, manifests, reports, and ledgers are the preferred mutation surfaces.

## Current RoBoCop calibration stack

Implemented capabilities:
- dataset-aware custom-data planner
- programmatic curve triage
- pure-ODE triage
- combined triage
- strategy racing
- dataset fingerprint memory
- bounded teacher-flux rescue for supported reactions
- worker-backed calibration execution
- minimal RL triage environment
- outbound Telegram alerts for long-running sessions

Production constraint:
- the web path depends on `CALIBRATION_API_BASE_URL` and `CALIBRATION_API_SHARED_SECRET` pointing to the Hetzner worker.

## Bounded autosearch loop

The current LangGraph loop is:

```text
START
  -> load_request_context
  -> propose_candidate
  -> evaluate_candidate
  -> derive_decision
  -> archive_result
  -> END
```

The loop mutates bounded policy/manifest/config surfaces, delegates evaluation
to the existing calibration runners, then archives a keep/discard decision.

Keep the runner bounded:
- explicit iteration budget
- explicit wall-clock budget
- explicit candidate artifact paths
- explicit decision records

## LangSmith tracing

LangSmith is optional and additive.

Use it to trace:
- candidate id
- seed id
- dataset id
- job id
- run directory
- triage verdict
- pure-ODE verdict
- combined verdict
- final keep/discard decision

If tracing is not configured, calibration behavior must remain unchanged.

## Curve triage principles

A lower score is not enough. A candidate must preserve physiological meaning.

Core protected anchors:
- `EGLC`
- `ELAC`
- `LAC`
- `ATP`
- `ADP`
- `AMP`
- `B23PG`
- redox/glutathione signals when in scope

Discard when:
- global loss improves only by compensatory degradation
- `EGLC` rises when it should deplete
- `ELAC` falls when it should accumulate
- ATP/ADP collapse worsens under pure ODE
- a narrow follow-up reproduces the same retained solution
- a candidate improves fit but fails the pure-ODE biological gate

## Calibration search posture

Preferred order:
1. stabilize extracellular glucose/lactate anchors
2. protect energy/adenylate behavior
3. open lower-glycolysis and outlet seams narrowly
4. widen only after local seam saturation is proven
5. treat hybrid kinetics as neutral wrappers before broad calibration

Avoid:
- opening broad compensatory transport sets prematurely
- repeatedly squeezing a saturated local pocket
- promoting fit-only wins without pure-ODE validation
- rewriting ODE topology without a staged migration plan

## Hybrid kinetics direction

Hybrid kinetics may be useful, but must enter safely:
- zero-math refactor first
- neutral defaults that reproduce the current model
- tiny reaction subset first
- parameter reporting and calibration support before broad search
- pure-ODE replay after every candidate worth considering

Priority reaction families:
- transport/outlet: `VEGLC`, `VELAC`, `VLDH`
- lower glycolysis: `VPK`, `VENOPGM`
- adenylate coupling: `VAK`, `VAK2`, `VNDPK`

## DeepAgents direction

Decision:
- DeepAgents is now the RoBoCop campaign supervisor candidate.
- It does not replace the deterministic scientific engine.

Target architecture:
- DeepAgents: planner, campaign supervisor, subagents, memory, high-level decisions.
- LangGraph: durable state transitions and runtime.
- LangSmith: traceability and audit.
- RoBoCop tools: calibration, strategy race, pure-ODE replay, triage, teacher-flux rescue, archive.
- `src/MM_calibration.py`: scientific truth source.

Prototype rules (still in force during the offline phase):
- offline first
- no production dependency at first
- no free-form scientific file mutation
- all writes through explicit bounded tools
- compare DeepAgents recommendations to the existing LangGraph runner before promotion

Implemented prototype files:
- `services/robocop/agentic/robocop_deep_agent.py` (`build_robocop_deep_agent`)
- `services/robocop/agentic/tools.py` (8 bounded tools + per-subagent ACL)
- `services/robocop/agentic/prompts.py`
- `services/robocop/agentic/subagents.py`
- `services/robocop/agentic/offline_runner.py`
- `services/robocop/agentic/compare_with_langgraph.py`
- `services/robocop/agentic/README.md`
- `requirements-agentic.txt`
- `qa/robocop/test_agentic_package.py`
- `qa/conftest.py`

Implemented safe tools (read-only or dry-run in this phase):
- `read_session_memory` (read-only)
- `summarize_campaign` (read-only)
- `run_curve_triage` (read-only, wraps `services/robocop/curve_triage.py`)
- `run_pure_ode_replay` (read-only, wraps `services/robocop/pure_ode_triage.py`)
- `run_combined_triage` (read-only)
- `run_strategy_race` (dry-run wrapper; real execution stays in `scripts/run_bounded_autosearch.py`)
- `run_teacher_flux_rescue` (dry-run wrapper)
- `append_recommendation` (write-only to `Simulations/robocop_agentic/recommendations.jsonl`)

## Current known scientific posture

Important lessons from recent campaigns:
- ATP/ADP remain the hardest protected targets.
- Pure calibration fit can improve while pure ODE energy behavior worsens.
- Glucose/lactate pockets can saturate locally; repeated identical follow-ups should stop.
- A phase-2 purine/adenylate seam can open gains after glucose basin saturation, but still needs pure-ODE survival.
- Hybrid downstream seams are live but so far produce small true-ODE moves.

## Promotion rule

Promote only if:
1. calibration fit improves,
2. protected pure-ODE behavior survives or improves,
3. the result reruns cleanly,
4. artifacts and decision records are complete,
5. the mechanistic interpretation remains credible.

Otherwise classify as:
- `informative` when it teaches a seam direction but is not safe as a seed
- `discard` when it regresses protected behavior, crashes, times out without usable artifacts, or reproduces a saturated basin
