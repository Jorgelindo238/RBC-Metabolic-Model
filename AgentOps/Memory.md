# AgentOps Memory

Durable lessons that should influence future Codex sessions. Keep this file
compact and action-oriented.

## Persistent rules

### 1. Verify before declaring success

Never declare important work complete without the most direct validation that is
realistically available. State what was proven, inferred, or blocked.

### 2. Authentication is a first-class dependency

Protected UI flows require a real signed-in session, safe test credentials, or
an approved bypass. Do not promise browser validation before auth is available.

### 3. Active dataset state is not the same as upload parsing

Research upload parsing only proves a file can be read. A dataset is active only
when the shared Research state drives downstream modules.

### 4. One Research dataset should drive every Research module

Data Upload, Calibration, Simulation, Flux Analysis, Pathway Visualization, and
RoBoCop context should all reflect the same active dataset when one is selected.

### 5. Scientific core must not be duplicated

`src/MM_calibration.py` is the canonical calibration path. Avoid parallel
calibration logic unless it is an adapter into that core.

### 6. ODE truth is separate from calibration fit

A better calibration score can still fail the full pure ODE. Promotion requires
pure-ODE survival on protected metabolites.

### 7. ATP/ADP are protected hard targets

Many runs improve extracellular or fit metrics while ATP/ADP still collapse.
Treat those candidates as informative unless pure-ODE energy behavior survives.

### 8. Timeouts, crashes, partials, and completes are different states

Do not collapse all incomplete runs into one failure bucket. Preserve status and
artifact evidence.

### 9. Strategy racing should learn only from physiological verdicts

Cache/warm-start custom-data calibration only when the winner passed triage and
pure-ODE checks, not just because the score improved.

### 10. Pure-ODE reruns need isolated artifacts

Seed and candidate pure-ODE artifacts must be isolated so comparisons do not mix
contexts or overwrite evidence.

### 11. If a seam reproduces the same solution repeatedly, move on

Repeated identical follow-ups indicate local saturation. Change the hypothesis
instead of squeezing the same pocket.

### 12. Extracellular wins need protected-core checks

Better `EGLC`, `ELAC`, or `LAC` behavior is valuable, but not enough if `ATP`,
`ADP`, `PEP`, or `PYR` become biologically worse.

### 13. Calibration objectives must stay scoped

Do not silently widen a target scope back to all metabolites. Phase objectives
should intersect requested/custom targets with the actual pathway group.

### 14. Custom-data profile routing matters

Extracellular custom data should use extracellular/glycolysis profiles.
ATP/ADP-only datasets should use energy/adenylate-aware profiles.

### 15. `vmax_then_km` is the preferred custom-data default

Use a disciplined Vmax-first pass before tightening Km values unless the user or
planner has a better reason.

### 16. New response fields should be additive

Preserve existing web/API contracts where possible. Add `triage`,
`combined_triage`, provenance, or result fields without breaking legacy clients.

### 17. NumPy/scientific outputs need explicit serialization

Convert arrays, scalars, and NaN/inf-sensitive values before returning JSON.

### 18. Browser hydration requires stable server snapshots

Avoid `Date.now()`, random IDs, locale-sensitive timestamps, extension-mutated
attributes, or client-only persisted state that differs from SSR output.

### 19. Stale dev servers can mask the real code path

Restart local dev servers when a UI fix appears missing. Verify the running app
is serving the edited files.

### 20. Product messaging should not imply false blockers

If Simulation can run with Bordbar defaults, say calibration is optional rather
than required.

### 21. RoBoCop must mirror provenance

RoBoCop should state active dataset, fallback/default status, calibration source,
result state, and selected module context rather than giving generic advice.

### 22. RoBoCop should stay contextual, not visually dominant

On scientific pages, the data/workspace is primary. RoBoCop acts as a discreet
interpreter.

### 23. Monitoring is inventory-first

Bag Repository, Quality Forecast, and Alerts should share persisted bag identity
and avoid becoming disconnected localStorage islands.

### 24. Supabase service-role keys are not management tokens

Remote Supabase provisioning needs a real Supabase access token or remote DB
password. A service-role JWT is not enough for CLI management operations.

### 25. LangSmith traces must be useful, not merely present

Root traces are not enough for complex workflows. Include node/tool metadata,
candidate IDs, run dirs, verdicts, and decisions.

### 26. DeepAgents is a supervisor candidate, not a scientific replacement

If introduced, DeepAgents should plan, delegate, manage memory, and explain
campaign decisions while deterministic tools perform calibration, triage,
pure-ODE replay, and acceptance checks.

### 27. Legacy Hermes names are technical debt

The local `hermes-agent/` checkout is no longer active. Remaining `Hermes` names
in symbols or artifact paths should be migrated deliberately with tests.

### 28. Keep generated/runtime files out of Git

Do not stage credentials, Vercel local state, build artifacts, logs, caches,
SQLite runtime data, or generated simulation/calibration outputs unless a later
decision explicitly promotes one.

### 29. Python 3.14 migration is deferred

Do not move production to Python 3.14 until the scientific dependency stack is
updated and validated. The old `numpy<2.0.0` constraint is the known blocker.

### 30. Trajectory CSVs are the contract for `pure_ode_replay`

`services/robocop/pure_ode_triage` (and any DeepAgents triage that depends on
it) requires `<run_dir>/<case>/metabolites/all_metabolites.csv`. Real autosearch
runs must keep `dump_trajectories=True` plumbed through `run_calibration()` and
the eval/job/autosearch scripts, and must keep `trajectory_csv_path` in
`eval_summary.json`. If you change the column scheme, preserve the property
that `len(columns) == y.shape[0]` and that protected anchors (ATP, ADP, AMP,
IMP, B23PG, GSH, EGLC, ELAC, LAC) are reachable by name.

### 31. AgentOps should remain a cockpit

Use:
- `Tasks.md` for active state
- `OperatingManual.md` for rules
- `Playbooks.md` for workflows
- `CalibrationOps.md` for calibration/RoBoCop operations
- `Archive.md` for history

Do not let active files become long notebooks again.
