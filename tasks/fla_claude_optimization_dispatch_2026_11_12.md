# Claude dispatch: constrained multistart Vmax optimization

Use `.claude/skills/airbc-vmax-calibration/SKILL.md` as project-specific guidance.
No third-party skill installation is needed. Explicitly read it if this Claude
session does not automatically discover project skills.

## Verified Starting Point

Read `tasks/fla_corrected_vmax_results_2026_11_12.md`, `tasks/fla_current_tasks.md`,
`scripts/run_corrected_vmax.py`, `scripts/verify_corrected_vmax.py` and the sealed
archive `output/corrected_vmax_2026_11_12/`. Candidate35 passed84 inherited guards,
but ATP/ADP J15 gains are only0.1238%/0.1902%. Four local LP rounds have finished;
do not rerun that same campaign and describe it as a new optimizer.

## Authorized Implementation Tranche

Prepare a successor for a genuinely constrained nonlinear, multistart Vmax-only
search, reusing existing model/scoring/qualified numerical code. Prefer the
existing SciPy stack (for example SLSQP with consistently cached objective and
constraint Jacobians) rather than a new optimization dependency. Inspect local
availability before choosing. Keep minimax epigraph handling and nonlinear
guard signs consistent; do not silently replace hard constraints with penalties.

1. Start from candidate35 and the qualified working centre; create at most three
   additional reproducible seeds from bounded joint directions. Only a replayed
   feasible seed may compete as a final candidate; do not call random starts
   admissible before evaluation. Infeasible intermediate proposals may be
   inspected, but cannot update the incumbent.
2. Same14 groups/17 Vmax, original boxes, Km/J1/transport/geometry/threshold,
   J4/J8/J11/J15 and84 feasibility guards including reserve. Historical guard
   reference is immutable. No AK/NDPK ungrouping, reaction change or latent
   reinitialization in this tranche. Same absolute ATP/ADP J15 objective.
3. Retain accepted/dense/quadrature evidence, fixed-source manifests, caching,
   deterministic starts, incremental checkpoints and resumability. No fabricated
   loss for solver failures. Explain how failed probes constrain the step.
   Check leading finite differences at0.006 and0.003 in the optimizer's gradient
   preparation, not as a separate open-ended diagnostic campaign.
4. Register a maximum of240 distinct search ODE evaluations and at most12
   full-backend validation integrations; cache hits do not consume that count.
   Stop on budget, numerical qualification failure or declared stagnation,
   retaining the best feasible incumbent. Up to3 numerical processes, no agents.
   Do not claim optimality or guaranteed biological recovery.
5. Finalist(s): strict/ultrastrict full-backend replay and independent guard,
   convergence, executed-flux quadrature and daily-balance verification. Export
   concentrations by date, objective and constraint traces, Vmax and seed status.

## Tools Boundary for This Desktop Handoff

Read/Grep/Glob/Edit/Write only. Do not invoke shell, run code/tests/integrations,
servers or optimizers, spawn agents, install packages, commit/push, or change
permissions. Codex will review and run tests and the actual numerical campaign
through its own execution tools after this code delivery. State this split
explicitly, rather than claiming the optimization was launched by writing code.

Deliver implementation, focused tests including budget/cache/constraint signs/
resume/no-nonVmax-change checks, preregistered protocol, exact execution entry
points and estimated maximum integrations. Do not redesign Calibration/Monitoring
in parallel. Stop after this bounded delivery and await Codex review.
