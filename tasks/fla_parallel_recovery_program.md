# FLA Parallel Calibration Recovery Program

Date: 2026-09-08
Status: latest three-agent dispatch blocked by usage quota; local review completed, no kinetic promotion.

Current decision and next execution are in `tasks/fla_model_review_2026_09_08.md` and the active handoff at the top of `tasks/fla_current_tasks.md`. The five-workstream table below records the earlier 2026-09-04 organization, not five currently running agents. The latest dispatch used at most three agents, with no completed agent reports.

Validation policy is now revision 3: raw balance closure and pre-clipping minima are mandatory, reset-assisted runs are not continuous validation, and absolute protected-target limits must be declared before fitting. Those limits remain unset. Structural parser schema 2 restores V6PGD/V23DPGP; affected historical teacher/rank artifacts require regeneration.

## Objective

Recover a predictive RBC storage model by separating four questions that the current sequential calibration has partially conflated:

1. Are experimental quantities expressed on compatible concentration or amount bases?
2. Can the current reaction network satisfy all measured conservation constraints simultaneously?
3. Which kinetic combinations are identifiable from the available time series?
4. Does a fitted model predict held-out times, datasets, and supplementation conditions?

One-factor FLA screens remain useful for attribution. They are no longer sufficient evidence for global parameter promotion.

## Parallel Workstreams

| Workstream | Agent | Deliverable | Promotion question |
|---|---|---|---|
| Data units and compartment scaling | Gauss | Executable ADE/EADE scaling audit | Are intracellular and extracellular teachers commensurate? |
| Network structure | Avicenna | Ranked structural audit | Which missing or misdirected reactions make the teachers incompatible? |
| Validation architecture | Rawls | Non-invasive validation-v2 module and tests | What evidence is required for diagnosis, retention, and promotion? |
| Calibration methodology | Dirac | Replacement/hybrid FLA strategy | When should parameter tuning stop and structure learning begin? |
| External generalization | Pascal | Brodbar/Bardyn/Michel protocol | Can the model predict another dataset and a supplementation intervention? |

The parent task owns integration, conflict resolution, final code review, and any change to the active ODE.

## Decision Ladder

### Gate 0: Data and unit contract

- Every target must declare compartment, concentration/amount basis, normalization, time unit, volume factor, interpolation policy, replicate count, and uncertainty status.
- Intracellular plus extracellular conservation teachers may be used only after an explicit amount conversion.
- A scale inferred from ADE/EADE cannot be validated against the same ADE/EADE trajectory.
- Duplicated or non-independent measurements remain excluded from independent objective terms.

Failure at Gate 0 blocks kinetic optimization for the affected pathway.

### Gate 1: Structural feasibility

- Reconstruct every target balance from the exact ODE reaction terms.
- Compare independently derived teacher fluxes for shared reactions.
- Require compatible signs and integrated magnitudes within declared measurement and interpolation uncertainty.
- Check pool ownership, source/sink completeness, reversibility, compartment exchange, degradation, and numerical floors.

If independent teachers remain incompatible, test reversible network hypotheses before changing kinetic constants.

### Gate 2: Identifiability

- Estimate local sensitivity rank for each proposed parameter group and dataset block.
- Reject groups with collinear sensitivities, boundary-only optima, or unbounded profile likelihoods.
- Treat latent initial states, kinetic constants, volume/scaling constants, and structural switches as separate inference classes.
- Open only identifiable combinations; report non-identifiable directions explicitly.

### Gate 3: Calibration

- Use joint pathway-level parameter groups rather than serial global promotion of one-factor screens.
- Fit concentration trajectories, derivatives/teacher fluxes, endpoints, and conservation residuals as separate objective channels.
- Weight by measurement uncertainty where available; otherwise run an explicit weight-sensitivity ensemble.
- Use multiple shooting or blockwise state continuity for long-horizon fits so the early transient does not dominate all later gradients.
- Maintain a Pareto set rather than collapsing incompatible objectives into one opaque scalar score.

### Gate 4: Internal validation

- Use forward-chaining temporal blocks: train through an earlier block and score later blocks without refitting.
- Numerical validity and exact balances are hard gates, not objective penalties.
- Protected-metabolite deterioration, full-panel deterioration, and model-complexity cost are reported separately.
- A diagnostic hypothesis may be retained when locally informative; parameter promotion requires all cumulative temporal gates.

### Gate 5: External and intervention validation

- Freeze structure, shared parameters, preprocessing, and thresholds before opening Bardyn or Michel outcomes.
- Use at least one dataset only for external validation.
- Preserve Bardyn supplementation as an intervention-prediction test rather than another calibration target whenever metadata permit.
- Report transfer failure as model evidence, not as permission to refit the test set.

## Provisional Success Criteria

These thresholds are frozen for the parallel review and may be revised once, with written justification, before the next optimization campaign:

- exact reconstructed balance error at or below `1e-7 mM/day`;
- no negative state beyond `-1e-10 mM` before the model's declared floor policy;
- no incompatible sign requirement between independent teachers after uncertainty and scaling analysis;
- at least `20%` improvement in the primary pathway trajectory objective and `15%` in its teacher-flux objective;
- endpoint and slope errors both improve for every primary target;
- no protected target nRMSE worsens by more than `10%`;
- whole-panel mean and median nRMSE worsen by no more than `5%`;
- the selected point is invariant to the declared strict-solver replay;
- the candidate improves a held-out temporal block and at least one held-out dataset or intervention condition;
- added structural complexity must improve predictive evidence, not only training error.

## Immediate Hypothesis Set

| ID | Hypothesis | Reversible test | Expected discriminating signal |
|---|---|---|---|
| H0 | Current network with diagnostic VAPRT suppression | Existing branch | Fits total adenylate but conserves ADE+EADE incorrectly |
| H1 | ADE/EADE amount scaling resolves the conflict | Fixed scaling grid, no fitting | Independent VAPRT teachers become sign- and magnitude-compatible |
| H2 | Extracellular adenine has an unmodeled loss | Optional `VEADE_loss` branch | ADE+EADE falls without adding AMP or consuming PRPP |
| H3 | Adenylate pool lacks an exit route | Optional measured-pathway sink only | Positive APRT becomes compatible with total adenylate without violating IMP |
| H4 | PRPP initialization or production ownership is wrong | Fixed-state/source feasibility map | APRT and HGPRT demands fit the available PRPP amount budget |
| H5 | Sparse-derivative FLA is too brittle | Joint smoothing plus multiple shooting | Teacher compatibility and parameter profiles stabilize across interpolation policies |

## Stop Rules

- Stop kinetic optimization immediately when a candidate relies on mutually incompatible teacher fluxes.
- Stop opening new parameters when the active sensitivity block is rank deficient.
- Stop promoting one-factor candidates that improve only a local target or only the training horizon.
- Stop treating numerical floors as biochemical steady states.
- Stop using Bardyn or Michel as tuning sets once assigned to external validation.
- Replace or augment the network when all plausible parameter values fail a structurally feasible teacher contract.

## Integration Deliverable

After all agents report, produce one synthesis containing:

- accepted and rejected findings with supporting artifacts;
- a validation-v2 API review and integration decision;
- one frozen data/structure experiment matrix;
- one calibration method selected for the next campaign;
- explicit compute budget and stopping conditions;
- the smallest reversible core-model change, if any;
- updated tasks, progress log, and manuscript methodology.
