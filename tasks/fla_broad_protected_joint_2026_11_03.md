# Eleven-pool protected optimization

Date: 2026-11-03. User explicitly authorizes optimization after the saved-flux
F6P/B23PG audit. This is a new exploratory successor, not a parent re-selection
or a production-default migration.

## Fixed scientific question

Can the existing six kinetic coordinates improve the joint likelihood while
preserving eleven per-pool training RMSEs and both individual PEP errors?
Protect EGLC/GLC/LAC/ELAC/ATP/ADP/AMP/PEP/G6P/F6P/B23PG on actual J4/J8 only.
There are22 source residuals and13 inequalities, not independent flux-teacher
labels or22 independent assays. J1 is exact initialization, not a residual.
J10 is a simulation horizon without an invented endpoint measurement.

Preserve all770 Sheet1 values, all55 measured J1 entries, all latent pools,
the six-coordinate bounds, native VELAC, diagnostic pH, H0.58 geometry,
reaction_consistent threshold0.001mM, affinities and OPLAH. No extra ATP source,
teacher forcing, observation reset, uFBA normalization or RIB/redox fitting.
The existing paired HK/PFK and GAPDH/PGK coordinates remain paired.

## Frozen broader guards

Activate the proposal from the sealed F6P/B23PG audit in this successor only.
The unchanged GLUT-only ultrastrict J1-J10 replay at J4/J8 defines all eleven
reference RMSEs and PEP's two reference absolute errors. The allowance is
`1e-5mM+1e-4*reference_error`; fitting uses25%, original-path audit100%.
These are engineering replay allowances, not assay uncertainty or acceptable
biological accuracy. Values are rederived and compared with the proposal before
source/guard/code sealing. No outcome-dependent relaxation is allowed.

PEP's separate J4/J8 constraints prevent compensation between its two errors.
The unchanged control remains a real evaluated feasible fallback. Known source
aliases B13PG and P2G are excluded from the likelihood;44 other source-channel
representations remain audit-only. Whole-panel or late-time protection is not
claimed.

## Optimization and audit

Use one shared profiled mean-preserving lognormal total residual dispersion,
retaining full density normalizers. It includes model/source/assay mismatch,
not measured analytical precision. Comparators are rescored on the same22
values; earlier seven/nine-channel scores are not directly comparable.

SLSQP minimizes NLL subject to13 scaled inequalities. Starts are control,
previous nine-pool fit and its log midpoint. Shared cost/constraint/Jacobian
cache avoids duplicated ODE solves; one-sided log step0.002 is retained.
Actual limits include control and derivative integrations:400 primary and1000
cumulative per start, with secondary restart only after unsuccessful termination.
This is a larger engineering budget than the previous250/600 campaign; gains
cannot be attributed to guard changes alone in a matched-budget sense.

Every actual evaluation is flushed to JSONL. Select the lowest valid feasible
training-NLL evaluation, including probes, separately from optimizer terminal
status. A gain below1e-4 retains the control. Completed fits are individually
sealed; explicit resumption preserves counts and does not invent convergence.

Original full-RHS strict/ultrastrict replays follow at J4/J10/J46. At J10/J46,
recheck all13 training-only constraints on J4/J8. Save all113 concentration
states,100 raw/executed reaction rates and accepted-step Gauss4/8 evidence.
Check positivity, daily executed balances, quadrature convergence and full/fast
trajectory parity. A numerical/early-guard failure triggers control fallback,
not cap expansion. J11-J46 remains exposed temporal evaluation, not independent
validation or a candidate-selection endpoint.

## Progress

- [x] Implement an isolated eleven-channel likelihood and13-constraint evaluator.
- [x] Pass24 focused tests, including every pool veto, separate PEP vetoes,
  future/J1 isolation, density normalizers, feasible fallback, caching/resume
  and actual cumulative integration accounting.
- [x] Reverify/seal parents, original data, proposed guards and successor code:
  4705 parent and8508 guard-audit checks pass;54 frozen input hashes match.
- [x] Run three starts and retain actual status:65/144 unsuccessful completed
  fits; control-start stopped after555 completed logged objective calls with
  no new feasible point. No convergence is invented for the interrupted fit.
- [x] Obtain a separate unchanged-cap feasible restoration candidate in nine
  objective integrations, without claiming NLL-optimum convergence.
- [x] Complete its six original-path J4/J10/J46 audits and165 source/comparator rows.
- [x] Pass1152 primary and801 secondary checks; enlarged QA1363 passed/two skipped.

Initial launch receipt (superseded by the final outcome below): three starts
were launched. Full QA1361 passed/two existing skips/six existing Optuna
warnings in80.03seconds (`qa_results_final.xml`); the earlier failed test-only
receipt remains preserved. No completed-fit or gain was claimed at that entry.
Archive `output/broad_protected_joint_calibration_2026_11_03/`;
config `config/fla_broad_protected_joint.json`; runner/verifier
`scripts/run_broad_protected_joint.py` and `scripts/verify_broad_protected_joint.py`.
No source workbook, old sealed script or production model is edited.

## Separate numerical restoration

At restoration launch, the original SLSQP campaign remained unchanged and
running; its later interruption is recorded below. Its near-boundary
control-start trials reach NLL about96.61 but fail one or more strict fitting
caps by small numerical amounts; the two other starts stop unsuccessfully.
Three separately frozen local LP directions, actually integrated, decrease cost
slightly but fail some guards. These three new objective calls are not counted
as SLSQP calls or used to reselect that campaign.

Create an explicit restoration successor,
`output/broad_protected_joint_restoration_2026_11_03/`, before any restoration
ODE call. Snapshot a training-only lower-cost seed with maximum normalized
violation<=1e-5; this is a STARTING-POINT screen, never an acceptance rule.
Keep all13 acceptance caps exactly unchanged. Use at most17 actual objective
calls, at most two linearizations, finite-difference step1e-4 and trust radius
0.005 in the same six log coordinates. Solve a minimum-L1 correction toward an
inner target reserving5% of the original numerical allowance. This is stricter
than the outer fitting cap, not an allowance expansion.

The first restoration uses nine objective integrations and finds a point with
all13 fitting guards passed and NLL96.615834 versus control99.776418. Factors:
GLUT0.96303370, investment0.39580749, AK0.56916353, GAPDH/PGK1.00304070,
PK0.74581723 and PEP phosphatase0.93366367. This is not convergence to an NLL
optimum. Shared total residual CV19.7946 is extremely large and must not be
described as assay precision or evidence of physiological accuracy. ATP J4/J8
remains0.0053358/0.00021184 against nominal1.079765/1.272527mM.

The completed restoration fit is sealed before audit. A continuation adapter
copies its FIRST real control evaluation into the generic selector's expected
reference location; this is neither an invented evaluation nor a second fit.
The initial adapter-path exception is retained in the execution history, no
fit or source is overwritten, and zero new objective calls are added by this
copy. `scripts/finish_broad_restoration.py` records its own source hash and the
source-trace hash in `continuation_provenance.json`. Original full-path J4/J10/
J46 audits and independent verification were required before acceptance and
were subsequently completed as recorded below.

Enlarged QA1363 passed/two existing skips/six existing warnings in
142.95seconds; earlier1361-passed receipt is retained. Restoration's two
additional tests check inward correction and fail-closed incompatible linear
targets. No claim of ATP rescue or original optimizer convergence is made.

## Final outcome

The original SLSQP attempt is sealed as
`interrupted_not_converged_not_a_completed_calibration`, not as an optimized
model. It contains764 completed logged objective integrations (555/65/144);
one additional in-flight integration may have been interrupted and is not
invented in that count. Both failed-fit seals and the entire partial control
trace are retained without modification. No guard-feasible gain was found in
that attempt. Source/guard limits are unchanged. The independent three-point
local diagnostic adds three objective calls; none is accepted.

The delivered candidate is the SEPARATE restoration archive
`output/broad_protected_joint_restoration_2026_11_03/`. It has nine objective
integrations, one accepted correction and no new biological degree of freedom.
The control-reference adapter copies its own first actual evaluation, adding
no objective call. `run_broad_restoration_pipeline.py` provides the one-shot
entry point without exposing that immutable adapter-path exception.

### Training protection

Strict fitting replay RMSEs on actual J4/J8:

| Pool | GLUT-only, mM | Restored candidate, mM |
| --- | ---: | ---: |
| EGLC | 0.935593733 | 0.865188829 |
| GLC | 0.846808239 | 0.846827464 |
| LAC | 0.882554477 | 0.882274545 |
| ELAC | 2.040660167 | 2.040659343 |
| ATP | 1.179141826 | 1.177536383 |
| ADP | 0.987604262 | 0.987319862 |
| AMP | 2.012606186 | 2.012648422 |
| PEP | 0.027823825 | 0.027810861 |
| G6P | 1.402464037 | 1.373740927 |
| F6P | 0.254513435 | 0.254520277 |
| B23PG | 0.403227484 | 0.321444784 |

GLC, AMP and F6P increase slightly within their frozen engineering allowances;
do not call all eleven errors improved. PEP absolute errors at J4/J8 are
0.039261583/0.002327255mM versus control0.039280073/0.002325143. J8 is also
maintained within allowance, not strictly improved. All13 fitting guards and
all13 original-path guards in BOTH J10/J46 profiles pass.

The old nine-pool candidate rescored on the SAME22 values has NLL36.0186 but
fails F6P/B23PG and PEP J8. Its lower cost is not an admissible alternative.
No late concentration was used to select the restored point or tune a limit.

### Original-path and source verification

All six replays pass117507/117507 strict/ultrastrict state/integral comparisons,
12882/12882 executed daily balances and11400/11400 each raw/executed Gauss4/8
comparisons. Full/source-extracted trajectories agree. Minimum across saved
accepted/dense/quadrature concentration states is0mM, not a continuous-time
positivity proof. Source770 values, exact55 J1 and all latent ICs are preserved.

Primary verification passes1152 checks: actual traces,22-value normalized
likelihood,13 unchanged constraints, injection scope, original balances,
quadrature and seven saved live-RHS checkpoints per replay. It is not an
independently coded ODE solver or physiological validation. Secondary checks
pass801 comparisons across seals,165 source/comparator rows,33 signed budgets,
the exact parent seed snapshot and copied control provenance. Maximum independent
NLL difference7.11e-15 and signed-budget difference5.33e-15mM. Parent/child guard
contracts, initial states and biological contexts are exactly equal.

Comparison/export directory:
`output/broad_protected_joint_validation_2026_11_03/comparison/`.
`candidate.json` contains unpromoted parameter overrides and exact initial-context
reference. GLUT conductance0.02626512463/day, VHK Vmax1.97903744 and PFK Vmax
1.00908374mM/day are candidate values, not identified physiological constants.

### Biology and whole-panel limits

ATP J4/J8/J46 is0.0053358/0.00021184/0.000017252mM against nominal
1.079765/1.272527/0.469757. The early increase relative to GLUT-only is not
restored energy. J46 GLC6.100110 versus0.826365, F6P1.164808 versus0.007026,
and B23PG0.00040796 versus0.254317 remain severe mismatches. EGLC15.596004
versus12.915 and ELAC21.670112 versus28.363716 also remain imperfect.

Executed J1-J46 ATP production5.775129 and consumption6.708104mM leave
-0.932975mM net loss. Glucose import7.055997 minus HK2.079174mM leaves
4.976823mM intracellular accumulation. OPLAH remains active; no ATP source or
reaction deletion is used to obtain this result.

On all13 postinitial points, B23PG RMSE0.296518 ->0.284410, GLC3.431573 ->
3.349069, PEP0.019981 ->0.019762 and G6P0.595678 ->0.583112 improve modestly.
EGLC worsens1.224563 ->1.358335mM. Among44 audit-only channel representations,
28 raw training-RMSE differences are positive; the largest is ASP+0.002505mM.
These counts include tiny differences/aliases and are not independent assay
counts or significance tests. The eleven-pool contract does not establish
whole-panel non-regression, later prediction or donor validation.

Decision: retain an inspectable guard-feasible candidate, reject physiological
and production/reference promotion, and do not claim an NLL optimum. The next
proposed biological hypothesis is a reversible separation of the current
VHK/VPFK capacity pairing, inside existing primitive bounds and under the same
13 guards. It is NOT executed here. Current-box global infeasibility, a causal
ATP rescue from that split, or a need to change measured initialization is not
proved. RIB/redox, affinity changes, pH/MCT and threshold fitting remain deferred.

![Original full-ODE comparison](../output/broad_protected_joint_validation_2026_11_03/comparison/concentration_comparison.png)

The figure is visually inspected. The vertical line denotes the J10 horizon,
not a measured J10 endpoint; only J4/J8 enter the fit. No uncertainty bars are
fabricated. Late observations are exposed internal temporal evaluation only.

### Successor reproduction

After preparing a fresh parent and obtaining an appropriate near-boundary
training point, use fresh directories:

```powershell
python scripts/run_broad_restoration_pipeline.py --parent output/broad_protected_fresh --out output/broad_restoration_fresh
python scripts/verify_broad_protected_joint.py --archive output/broad_restoration_fresh --receipt output/broad_restoration_validation_fresh/verification.json
python scripts/report_broad_protected_joint.py --archive output/broad_restoration_fresh --out output/broad_restoration_validation_fresh/comparison
```

The interrupted original archive is immutable and must not be resumed as if
it were a completed optimization. A future run needs a fresh successor.

Final close-out QA1363 passed/two skipped/six existing warnings in119.54seconds
(`qa_results_closeout.xml`);26 focused broad/restoration cases pass in8.60seconds.
All required search, restoration, replay, verifier and test sessions have ended.

## Reproduction

```powershell
python scripts/run_broad_protected_joint.py --prepare output/broad_protected_fresh
python scripts/run_broad_protected_joint.py --run output/broad_protected_fresh --workers 3
python scripts/verify_broad_protected_joint.py --archive output/broad_protected_fresh --receipt output/broad_protected_validation_fresh/verification.json
```
