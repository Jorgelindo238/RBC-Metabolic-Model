# Corrected-engine Vmax-only absolute ATP/ADP search protocol

Status: PROTOCOL AND CODE PREPARED 2026-11-10; CAMPAIGN NOT EXECUTED. Runner,
verifier, decision module and 27 targeted tests exist. Config:
`config/fla_vmax_corrected_search_2026_11_10.json`. Planned fresh archive:
`output/vmax_corrected_search_2026_11_10/` (must not exist before launch).

Successor to `tasks/fla_vmax_requalification_results_2026_11_09.md`. All
sealed or partial archives stay untouched; none is rerun or overwritten.

## Question

With the qualified optional numerical recipe now used INSIDE the search
(not only in the final audit), can a local Vmax-only search in the original
boxes move the J15 ATP/ADP predictions materially toward the inherited
absolute windows while every dated guard still passes?

This is a bounded feasibility test with a registered futility rule. It is
not global identification, a held-out validation or a promotion pass.

## Why a successor is justified, and its known limit

The 2026-11-07 absolute search integrated its 80 attempts with the loose fit
profile (rtol 2e-5, atol 1e-8). Five attempts were rejected numerically and
round 1-3 used only 13 of 14 derivatives. The requalification showed those
rejects were solver artefacts: all sixteen recovered. Sensitivities and
line-search decisions that treated them as failures are therefore not valid
search evidence and are recomputed here.

Registered expectation, stated before execution: the old campaign lowered
the worst-side gap from 12.45368 to 12.08916 log units in four rounds
(0.36452 of the 12.09 required). The binding side is ADP:lower (12.089);
ATP:lower is 9.039. At the working center PGK sits on its lower factor
bound 0.5 and NDPK on its upper bound 2.0. A same-box local search is NOT
expected to reach the windows. Its value is (a) clean sensitivities,
(b) a correctly searched comparator, (c) a registered decision on whether
Vmax-only in the original box is exhausted.

## Frozen contract

Unchanged and verified by hash against the numerical parent
`output/vmax_requalification_2026_11_09/` before any integration:

- exact 55 Sheet1 J1 values and all latent initial states;
- 770 observation cells, 14 dates, alias status of B13PG/B23PG, P2G/P3G;
- every Km and every nontarget parameter (literal baseline dictionary);
- 14 factor groups / 17 Vmax and the original factor boxes; HK ceiling 5.0;
  AK and NDPK forward/reverse pairs and PGM_ENO keep their shared factors;
- network gem_corrected -> redox_gssg_abc, RBC-GEM commit
  43fd381d9eb8a8a4079629012362312960e1c009, OPLAH retained;
- hematocrit 0.58, phase volumes, transport laws, clamped pH diagnostic;
- positivity policy reaction_consistent, availability threshold 1e-3 mM,
  physical-state rejection tolerance -1e-10 mM;
- absolute J15 windows ATP [0.75707361, 1.27058099] mM and ADP
  [0.31579781215841685, 0.5854817010799304] mM. These are the inherited
  engineering windows, not assay uncertainty.

Forbidden: Km changes, bound expansion, new parameters or groups, threshold
selection by fit, clipping, state repair or reset, source rescaling, teacher
forcing, ATP injection, pseudocounts, fit-based retries, J46 integration,
production-default or solver-default promotion.

## Numerical engine

Require SciPy 1.17.1 at runtime (system Python 3.14; the repository `venv`
carries 1.16.3 and must not be used). Public Radau, max_step 0.05 day,
bounded fine finite-difference Jacobian.

| Use | rtol | atol (mM) | Jacobian minimum step (mM) |
| --- | --- | --- | --- |
| Search and controls (strict) | 1e-8 | 1e-12 | 1e-15 |
| Final audit only (ultrastrict) | 1e-9 | 1e-13 | 1e-16 |

Search evaluations use the certified compiled (joint) backend. The recipe
stays opt-in for this campaign and changes no default.

## Step 1: Controls (2 integrations)

Integrate the fixed half-step reference and the working center (absolute
attempt 76) with the strict search engine. Both must pass the concentration
contract and reproduce the J4/J8/J11/J15 values of the sealed strict/joint
requalification controls within the inherited comparison tolerances
(1e-5 mM absolute, 1% relative). The working center must still pass the
original reserved guards. Stop the campaign if any control fails; do not
continue to Step 2 and do not repair.

Guard caps and the reference for dated adenylate ratios remain the OLD
historical full control under
`output/absolute_vmax_2026_11_07/audits/corrected_reference/`: its strict
replay for every search evaluation, and the matching legacy profile for
each audit profile, exactly as in the requalification. Caps are not
recomputed from the new solver. The reserve is unchanged:
10% of baseline guard slack for LP proposals, at least half of it for
accepted points.

## Step 2: Recomputed sensitivities at the center (14 integrations)

One forward difference per group in log-factor space, step 0.006; the step
is reversed for a coordinate that would leave its box (NDPK at the upper
bound). Report, before any proposal is evaluated:

- the 4 x 14 Jacobian of the absolute sides (ATP/ADP, lower/upper);
- the Jacobian of every dated guard and dated-gain constraint;
- which constraints are within the reserve of activity at the center;
- the count of valid derivatives. The registered expectation is 14/14.
  Any invalid derivative is preserved with species, time and minima and
  its coordinate is frozen for that round; it is never retried.

These sensitivities are local finite differences at one point. They do not
establish identifiability.

## Step 3: Guarded trust-region rounds

Unchanged algorithm and constants from the 2026-11-04 / 2026-11-07 runs:
minimax LP over the four absolute sides subject to linearized guards with
reserve; initial radius 0.2, maximum 0.3, growth 1.25 on acceptance, halving
otherwise; backtracking fractions 1, 0.5, 0.25, 0.125, 0.0625; minimum
objective gain 1e-6. Only actual ODE evaluations can be accepted. Four
rounds. Round 1 reuses the Step 2 differences; rounds 2-4 recompute them at
the accepted anchor.

Budget: at most 80 search integrations in total (2 controls + 4 x 14
differences + 4 x 5 backtracks = 78), the same cap as both predecessors.
No budget increase during the run. A round without an accepted point halves
the radius and keeps its anchor; its differences are then served from the
cache and cost no new integration. A round with no valid derivative ends
the search.

Every attempt keeps its sealed solver diagnostics with per-species minima on
all four supports and its fit-date states. A numerically rejected attempt
additionally keeps its whole recorded trajectory and is never admitted.
Full flux evidence is produced only for the audited point in Step 4.

Registered comparators, read from sealed archives and NOT reintegrated:
working center and recovered candidate_13 / candidate_14 of the
requalification campaign.

Objective, unchanged: for each pool the larger of log(lower/prediction) and
log(prediction/upper) at J15, maximized over ATP and ADP. A nonpositive
adenylate is an explicit observation-domain failure, not scored.

## Step 4: Audit of the selected point (at most 2 integrations)

Select the lowest worst-side gap among actually evaluated, reserve-feasible
rows. If it is the working center itself, no audit is run. Otherwise
integrate it once strict and once ultrastrict with full evidence: accepted,
dense and order-4/order-8 quadrature supports, daily executed balances,
native raw/executed rate projection at the nine registered checkpoints, and
the paired-profile comparison. Score both profiles against the unchanged
guard reference.

## Registered decision rules

Evaluated on the audited point, worst profile, in this order:

1. `numerical_failure`: any audit gate or the paired comparison fails.
   Center retained.
2. `metabolic_guard_failure`: any original guard, zero-band, dated-gain
   (>= 0.1% at each of J4/J8/J11/J15) or reserve check fails. Center retained.
3. `absolute_target_attained`: worst-side gap <= 0 in both profiles with all
   guards. Reported as attainment under working windows, never as biological
   validation. Requires a separate user decision before any promotion.
4. `improved_center`: guard-admissible and worst-profile gap strictly below
   the center's 12.089180125660619, and worst dated adenylate ratio not
   above the center's 0.9344634013067057. Becomes the next working center
   only; no default changes.
5. `no_improvement`: otherwise. Center retained.

Futility rule, independent of 4/5: if the final worst-profile gap is still
above 11.089180125660619 (less than one log unit gained), the campaign is
additionally classified `original_box_local_search_exhausted`. In that case
no further same-box Vmax-only search is launched. The next step is a
decision submitted to the user between reversible alternatives that this
protocol deliberately does not open, for example: a registered widening of
the PGK/NDPK boxes, the latent GDP/GTP initialization contract, executed
ATP-consumer attribution J8-J15, or the availability-gate formulation.
Reaching neither rule's threshold is not evidence of global infeasibility.

Report ATP and ADP gaps separately in every table; an ATP rise paid for by
an ADP fall (as for candidate_13) is not progress on the joint objective.

## Independent verification and closeout

A separate verifier reconstructs from raw archives, without importing the
runner's decisions: input hashes and parameter identity (only the 17
registered Vmax may differ from baseline), every score and guard value,
the finite-difference Jacobians, each LP witness, the acceptance sequence,
the selection, the audit balances/quadratures/native checkpoints and the
final classification. Failed or rejected trajectories stay quarantined with
their evidence. Seal every folder; write the archive manifest last.

Files written 2026-11-10 (their hashes are frozen into the archive at
launch, so any later edit requires a new dated successor):

- `src/fla_vmax_corrected_search.py` (plan check and registered decisions);
- `scripts/run_vmax_corrected_search.py` (reuses `lp_step`, `scored`,
  `record_stepper`, `BoundedJacobian`, `exact_parameters`, `run_one`;
  no new scientific logic);
- `scripts/verify_vmax_corrected_search.py`;
- `qa/test_fla_vmax_corrected_search.py`.

Pre-launch evidence, outside any campaign archive: 27 targeted tests pass;
the scoring and the independent rescoring agree on both sealed controls;
one scratch strict integration of the fixed reference (about 21 s) was
bitwise identical to the sealed requalification control and was deleted.
The trust-region loop, the audit stage and the round verifier have NOT been
exercised end to end; their first execution is the campaign itself.

Launch, from `scripts/` with the system Python (SciPy 1.17.1):

    python run_vmax_corrected_search.py --out ../output/vmax_corrected_search_2026_11_10
    python run_vmax_corrected_search.py --out ../output/vmax_corrected_search_2026_11_10 --audit
    python verify_vmax_corrected_search.py --out ../output/vmax_corrected_search_2026_11_10 --report ../output/vmax_corrected_search_decision_2026_11_10

Still to write after closeout: results report `tasks/fla_vmax_corrected_search_results_2026_11_10.md`
  and a new top entry in `fla_progress_log.md` after closeout.

Targeted tests must pass before the archive is created. The full repository
suite has not been run for this preparation.
