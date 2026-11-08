# Protected joint calibration

Date: 2026-11-02. User requests protection of PEP/G6P and the other monitored pools before any new kinetic lever. This execution resumes the project after the earlier pause; it is not automatic work during that pause.

## Frozen question and scope

The October27 seven-pool fit was numerically consistent but biologically rejected: it allowed PEP to regress to4.942643mM at J46 while ATP remained2.128972e-5mM. The present successor asks whether the same six-coordinate kinetic box can improve a nine-pool likelihood WITHOUT worsening any of the nine training RMSEs beyond a predeclared numerical allowance. No new Vmax/Km coordinate, latent initialization, reaction, pH law or ATP source is opened.

Protect EGLC, GLC, LAC, ELAC, ATP, ADP, AMP, PEP and G6P at actual source J4/J8. Every ODE starts from exact Sheet1 J1, including all55 measured initial entries and unchanged latent pools. Reopen and compare all770 original workbook values. Preserve native VELAC, diagnostic clamped pHi7.2, H0.58 borrowed geometry and reaction_consistent threshold0.001mM. OPLAH remains present. Source normalization, free/total pool meaning, donor identity and acid/base readiness are not solved by optimization.

Hard guards apply to these nine pools' two-point training RMSEs, not every individual measurement or all55 observed channels. The other46 source-channel representations are audited separately, including duplicate aliases. No statement of whole-network or long-term non-regression is implied.

## Preregistered guard contract

Reference is the archived GLUT-only ultrastrict J1-J10 replay, not the rejected joint fit. Only its predictions at J4/J8 and the matching original source concentrations define the reference errors. For pool i, `R_i=sqrt(mean((prediction_i-source_i)^2))`.

Numerical allowance is `a_i=1e-5mM+1e-4*R_i`. The fitting cap is `R_i+0.25*a_i`; original-path verification uses `R_i+a_i`, reserving75% of the allowance for solver/replay differences. These are engineering tolerances, NOT assay uncertainty, biological accuracy limits or permission to inflate residual noise. They are frozen before optimization and never tuned to the result.

| Pool | Reference training RMSE, mM |
| --- | ---: |
| EGLC | 0.935593733 |
| GLC | 0.846808239 |
| LAC | 0.882554477 |
| ELAC | 2.040660167 |
| ATP | 1.179141826 |
| ADP | 0.987604262 |
| AMP | 2.012606186 |
| PEP | 0.027823825 |
| G6P | 1.402464037 |

These reference errors are not acceptable biological targets simply because they define a fallback. In particular, a nearly depleted-ATP comparator is not a calibrated model.

## Objective and execution

Use the full normalized mean-preserving lognormal likelihood with one shared profiled TOTAL residual variance across nine channels and two training times (18 observations). Common log variance and conditional independence are assumptions, not measured assay precision/covariance. J1 is initialization, not an extra residual. Derived flux teachers are not double-counted as independent measurements. NLL on nine channels cannot be directly compared with the earlier seven-channel NLL; rescore comparators on the same18 observations instead.

SLSQP enforces nine normalized inequality constraints `(fit_cap_i-current_RMSE_i)/R_i>=0`. Cost, constraints and their one-sided0.002-log-factor Jacobians share each cached ODE solve. Actual integration counts include all finite-difference evaluations and the control solve. Three starts are the feasible control, the rejected October27 J10 vector and their log-space midpoint. The kinetic bounds and exact six factors are inherited unchanged from the earlier configuration.

Every fit includes the control as a real evaluated feasible fallback. The selected fitting point minimizes training NLL among valid guard-feasible evaluations, including finite-difference probes, irrespective of whether an optimizer stops successfully. Optimizer status and selected-point feasibility are reported separately. Primary250 and cumulative secondary600 actual-integration caps per start remain engineering limits; a restart follows optimizer failure, not poor biology. A training NLL gain smaller than1e-4 is not called improvement: retain the control. No late concentration or late error is used for candidate or guard selection.

Write every evaluation immediately to a JSONL trace. Completed fits are individually sealed. Explicit `--resume` can reuse matching completed fits or continue intact partial fit traces with cumulative call accounting; it does not grant convergence to an interrupted optimizer. A partial full-path audit is preserved and requires a successor rather than overwrite. All old scientific archives remain immutable.

After fitting, audit the chosen parameter set in the original full RHS at J4, J10 and J46, strict/ultrastrict, in that order. J4 is a short numerical screen, not an unseen observation test. At J10 and J46, recheck all nine constraints at J4/J8 ONLY in both profiles. The long replay does not grant use of later observations for acceptance. Retain all113 concentration trajectories,100 raw/executed reactions, full Gauss4/8 quadrature nodes, signed budgets and source-extracted/full-path state parity. If a candidate fails numerical or early guard verification, retain it as failed evidence and audit the fixed control fallback without relaxing thresholds. Numerical/guard acceptance does not automatically promote a biological model.

## Progress

- [x] Read the live handoff and October27 rejected campaign.
- [x] Implement a separate nine-pool constrained likelihood and candidate selection; no old source file edited.
- [x] Pass21 focused tests: per-pool regression vetoes, reserved replay margin, future-data isolation, full density normalizers, feasible fallback, invalid data rejection, evaluation caching, cumulative budget and completed-fit resume.
- [x] Reopen770 original values, preserve55 measured J1 and freeze source/guard/code hashes before fitting.
- [x] Complete full QA:1319 passed, two existing source-dependent skips, six existing Optuna warnings in205.84seconds. Existing Python3.14/Pydantic startup warning persists. Receipt: `output/protected_joint_validation_2026_11_02/qa_results.xml`.
- [x] Execute three constrained fits and retain actual status, feasible evaluations and fallback decisions: all converge,871 actual objective integrations,240 feasible evaluations.
- [x] Audit the selected candidate in six original-ODE strict/ultrastrict replays and assess all55 source channels separately. Nine early guards pass; this does not protect late errors or the other46 channels.
- [x] Verify reconstructed source cells, likelihood, constrained selection, guards and executed-flux budgets:4705 primary checks and846 secondary hash/arithmetic checks pass. Final QA1322 passed/two skipped/six existing warnings in155.20seconds, including three reporting tests. Receipt: `output/protected_joint_validation_2026_11_02/qa_results_final.xml`; earlier1319-passed run preserved.

## Results

Scientific archive: `output/protected_joint_calibration_2026_11_02/`; protocol `config/fla_protected_joint.json`; runner/verifier `scripts/run_protected_joint.py` and `scripts/verify_protected_joint.py`. Secondary report/export: `output/protected_joint_validation_2026_11_02/comparison/`, generated by `scripts/report_protected_joint.py`. The candidate is reusable but explicitly unpromoted. No production default is overwritten.

### Fitting and selection

| Start | Actual objective integrations | Feasible evaluations | Final optimizer success | Best feasible NLL |
| --- | ---: | ---: | --- | ---: |
| control | 208 | 39 | yes | 31.876074524 |
| rejected_joint | 261 | 63 | yes | 31.876074595 |
| midpoint | 402 | 138 | yes | 31.876082692 |

The latter two starts required the declared secondary restart after250 actual calls. All counts include finite-difference perturbations and the initial control. There are871 total calls and no invalid evaluation. The selected point comes from the `control` START, but is NOT the unchanged control or a fallback: its six factors differ from zero-log control. For that fit, the lowest feasible point is a finite-difference probe rather than its optimizer terminal point; both identities are preserved. Close costs across starts do not establish global optimality or parameter identifiability.

The nine-channel training NLL improves92.3381 ->31.8761 versus the real GLUT-only control. The rejected seven-pool candidate rescored on the SAME18 values gives35.7333 and fails four early guards. The new common total residual CV is1.22878, not analytical precision. Factors relative to the frozen kinetic context are GLUT0.85278995, investment0.02, AK0.001, GAPDH/PGK1.11059294, PK0.80781831 and PEP phosphatase0.61233450. Investment and AK hit their lower search bounds. GLUT conductance is0.0232584116/day; both affinities stay fixed.

### Guarded training errors

Values below use the final original-path ultrastrict J1-J46 replay at J4/J8. They are not errors fitted to late observations.

| Pool | GLUT-only RMSE, mM | Protected RMSE, mM |
| --- | ---: | ---: |
| EGLC | 0.935593733 | 0.664494274 |
| GLC | 0.846808239 | 0.660213632 |
| LAC | 0.882554477 | 0.840378228 |
| ELAC | 2.040660167 | 1.998906824 |
| ATP | 1.179141826 | 1.076974936 |
| ADP | 0.987604262 | 0.415910526 |
| AMP | 2.012606186 | 1.255293897 |
| PEP | 0.027823825 | 0.027827014 |
| G6P | 1.402464037 | 0.207126071 |

Eight errors decrease strictly. PEP increases3.18958e-6mM, within the fixed fitting/audit numerical allowances; it is maintained within tolerance, NOT improved. It is the active fitting constraint. Aggregating J4/J8 also does not guarantee pointwise improvement: GLC J8 worsens from1.127451 to2.106306mM against nominal1.212157, despite the improved two-point GLC RMSE. PEP similarly improves at J4 but worsens at J8. No pointwise non-regression claim is made.

### Original-path numerical acceptance

All six full-adapter J4/J10/J46 replays pass. Strict/ultrastrict comparisons117507/117507, executed daily balances12882/12882, raw/executed Gauss4/8 comparisons11400/11400 each. Source-extracted/full trajectories pass parity. Minimum concentration across all saved accepted, dense and quadrature states is0mM; this is not a continuous-interval positivity proof. Original770 values,55 measured J1 and all latent initial states are unchanged. Both J10/J46 replay profiles pass all nine early guards. There is no fallback or late-residual candidate selection.

Read-only primary verification passes4705 checks: source/input/output hashes, independent likelihood arithmetic, per-fit feasible selection, guards, quadrature and seven sampled live original/fast RHS states per replay. It does not re-execute every optimizer trajectory or validate physiology. Secondary verification passes846 checks across new/parent/comparison seals,165 pool/comparator rows and21 signed pool budgets. Independent SciPy full-density NLL differences are at most1.42e-14; signed-budget differences3.55e-15mM. Maximum integrated-budget versus endpoint discrepancy2.02e-7mM. Receipts: `archive_verification.json` and `secondary_arithmetic_verification.json` in the validation directory.

### Long-horizon and other-pool failure

J46 predictions remain EGLC17.151448 versus nominal12.915000, GLC6.291967 versus0.826365, ATP2.139943e-5 versus0.469757, LAC0.129211 versus6.462934 and ELAC19.374754 versus28.363716mM. ATP J4/J8 is0.126445/0.084701 versus1.079765/1.272527mM. This is not ATP rescue. PEP J46 is0.00013585 rather than the rejected candidate's4.942643mM, but remains below nominal0.011204mM.

On all13 postinitial observations, PEP RMSE0.0199814 ->0.0215310mM worsens modestly, while G6P0.595678 ->0.115187 improves. EGLC, GLC, LAC and ELAC full-period errors worsen; early protection is not long-term protection. These later data were inspected only after selection and are historically exposed internal evaluation, not independent validation.

Among46 audit-only source channels,17 have a raw positive training-RMSE delta and22 have a raw positive full-period delta versus control. These are descriptive counts of representations, not independent assays or significance tests; tiny numerical differences are not assigned biological meaning. The largest early increases include F6P0.254513 ->0.715042 and B23PG0.403227 ->0.550146mM. Thus even early whole-panel non-regression is NOT achieved. Known duplicate aliases B13PG/P2G are flagged, not counted as independent evidence.

Executed J1-J46 ATP positive contributions7.999860 and negative8.932831mM leave-0.932971mM net loss. Positive and negative contributions are integrated before netting, not interpreted as microscopic exchange. Main net ATP expenditures include NDPK3.268288, PRPP synthesis1.595348, ribokinase0.999975, HK0.760960 and PFK0.400772mM; OPLAH is retained0.393887. Glucose import5.929641 minus HK0.760960 leaves5.168681mM accumulation. Reducing the investment factor is therefore not equivalent to restoring glucose utilization or ATP production.

### Decision and next task

Accept the numerical execution and nine-channel training-guard contract, retain the candidate for reversible diagnostics, but reject biological/reference promotion. Exact source and initialization are preserved, kinetic bounds have not expanded, and the ATP deficit persists.

Before another optimization, perform a fixed-parameter, saved-executed-flux attribution of the early F6P and B23PG regressions and PEP's active constraint, comparing GLUT-only and the protected candidate. Use actual J4/J8 discrepancies and exact stoichiometry to propose a duplicate-aware broader guard contract; do not use late errors to reselect this campaign. This now precedes the previously proposed RIB(0) test. Keep RIB/redox initialization, OPLAH, affinities and all kinetic coordinates fixed during that audit. No new calibration or latent test is launched in this execution.

## Reproduction

```powershell
python scripts/run_protected_joint.py --prepare output/protected_joint_new
python scripts/run_protected_joint.py --run output/protected_joint_new --workers 3
# Only if the preceding fitting execution was interrupted:
python scripts/run_protected_joint.py --run output/protected_joint_new --workers 3 --resume
python scripts/verify_protected_joint.py --archive output/protected_joint_calibration_2026_11_02
python scripts/report_protected_joint.py --archive output/protected_joint_calibration_2026_11_02 --out output/protected_joint_validation_new/comparison
```
