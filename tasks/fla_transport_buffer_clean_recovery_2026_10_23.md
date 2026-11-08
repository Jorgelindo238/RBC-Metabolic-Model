# FLA clean carrier-buffer recovery: resumed execution

Date: 2026-10-23. User requested resumption at the saved October6 checkpoint.

## Scope

Execute the previously frozen clean synthetic recovery protocol, not a biological calibration. Preserve the original five-state toy, preparation archive, source concentrations, exact55 nominal J1, all latent biological ICs, historical ODE/kinetics and strict reaction-consistent provisional reference. No uFBA normalization or physiological pH is introduced. No memory update, donor assignment, biological replay or parameter promotion is performed in this session.

The source of truth is `output/transport_buffer_synthetic_preparation_2026_10_06/preregistered_design.json` and its `recovery_protocol.md`. Its read-only verifier passes before and after execution. The new code lives separately in `src/fla_transport_buffer_recovery.py` and `scripts/run_transport_buffer_recovery.py`; it imports the original reaction RHS without editing any prior sealed code.

## Executed design

All observations are noiseless constructed toy trajectories. Only the JBC4C sampling times are reused, not measured concentrations, pH, donor labels or biological uncertainty. Sparse training uses days0,1.0417,3,7.0417; dense training uses81 synthetic samples through7.0417. Predictions continue without reset through20.9583days. The optimizer integrates only the training horizon and never receives later observations or a derived-flux likelihood.

| Stage | Estimated coordinates | Known synthetic context | Observation plans | Fits |
| --- | --- | --- | --- | ---: |
| Oracle | Conductance | All other inputs, including pHi0 | LAC/ELAC | 12 |
| Buffer | Conductance, beta_e | Accessibility, affinities, pHi0 and other inputs | LAC/ELAC+pHe; LAC/ELAC+pHi+pHe | 24 |
| Access/pHi | access_i, pHi0 | Conductance, buffers, affinities and other inputs | LAC/ELAC; plus pHe; plus both pH | 36 |

Counts include two initial import/export contexts, sparse/dense schedules and the three frozen start vectors projected onto each stage's free parameters. Fixed Km is known constructed context here, not newly supported biological evidence. Unknown initial pHi is always overwritten by the estimated coordinate in the access/pHi stage; a regression test changes hidden scenario pHi and requires identical residuals.

Positive parameters use logarithmic coordinates; pHi0 is linear. Bounded SciPy least-squares uses3-point finite differences, the frozen first step1e-4, x_scale1 and ftol/xtol/gtol1e-10. These implementation choices are written in the execution records; no post-outcome restart or retuning occurs. Residual scales are1mM and0.02pH as frozen design weights, not experimental covariance. The100-evaluation limit counts every actual objective integration, including finite-difference calls that SciPy's nfev excludes. Budget exhaustion is an explicit non-success, not an accepted optimizer result.

The optimizer objective includes each requested concentration/pH channel under this deterministic design; LAC and ELAC remain conservation-related rather than independent stochastic evidence. No concentration-derived teacher is counted as independent. Future noisy fits need a declared covariance/observation model rather than assuming this deterministic objective establishes statistical independence.

## Results

All72 fits pass optimizer, numerical, parameter-recovery and untouched later-time prediction checks. All24 three-start groups pass the declared parameter agreement limits. Actual objective integrations total2613; the maximum per fit is65, below100. Final validation adds144 strict/ultrastrict full-horizon integrations, and the four equivalent-family controls use eight integrations. The original72 preparation integrations are a different, preserved campaign and are not counted as new fits.

| Quantity | Worst clean error | Frozen acceptance limit |
| --- | ---: | ---: |
| Conductance, relative | 2.71e-9 | 0.05 |
| beta_e, relative | 2.40e-9 | 0.05 |
| access_i, relative | 1.52e-8 | 0.05 |
| pHi0, absolute pH | 6.96e-9 | 0.01 |
| Holdout scaled RMSE, all four predicted coordinates | 1.74e-7 | 0.05 |

Very small errors reflect a noiseless, correctly specified, low-dimensional inverse problem with other inputs known. They are not biological precision estimates or evidence that the corresponding parameters can be learned from experimental data at this accuracy.

All fitted trajectories pass declared strict/ultrastrict state/flux agreement, checked nonnegative lactate states, amount/acid/extent closure, and accepted-step Gauss4/8 flux/extent consistency. No concentration clipping, state resets, pH reservoirs, invalid-trajectory finite penalties or ATP source is used. The toy contains no ATP or metabolism.

Four negative controls start from the recovered sparse both-pH fit with the first prespecified start, not a favorable winner. Simultaneously rescaling access_i and Km_i by0.5/2 and shifting pHi0 bylog10(c) preserves LAC, ELAC, pHe and flux while shifting pHi. These show why allowing unknown Km retains an equivalent family. No unknown-Km optimizer is used to claim uniqueness, and pHe alone does not break this exact toy symmetry. Observed pHi or independent affinity/activity support changes that inference.

Conditional concentration-only access_i/pHi0 recovery does not contradict the earlier four-unknown sparse sensitivity limitation: this stage frees only two parameters, fixing conductance, buffer and affinities. Simultaneous four-parameter recovery, global identifiability, robustness to noise and full-RBC calibration remain untested by this result.

## Cross-check and verification

`scripts/audit_transport_buffer_clean_recovery.py` independently codes the scalar extent equation using the analytic concentration/pH conservation relations and integrates it with DOP853 at rtol1e-11/atol1e-13. This does not call the five-state RHS or reduced-carrier implementation. All72 fitted trajectories agree with the saved ultrastrict BDF results within the original numerical limits; maximum absolute difference over all five coordinates is3.3074e-8. Parameter-error and holdout-RMSE arithmetic are also separately recomputed. This is a computational cross-check, not independent biological evidence or new recovery from a different biological mechanism.

New focused regression suite plus prior preparation suite:53 passed, including17 new tests for clean recovery, real-call limits, initialization leakage, temporal separation, exact saved queries and separation of fit/prediction from parameter correctness. Full QA:1214 passed, two existing source-dependent skips and six existing Optuna experimental warnings in84.54seconds. The pre-existing Python3.14/Pydantic startup warning remains. JUnit: `output/transport_buffer_clean_recovery_validation_2026_10_23/qa_results.xml`.

The successor archive verifies hashes of all preparation inputs/outputs, the executed new code/tests and protected biological inputs. Its verifier reconstructs fit metrics, source initialization, stored amount/acid closure, group agreement and summary; it does not rerun all2613 optimization integrations. The independent scalar audit is stored outside the scientific seal alongside JUnit validation.

## Reproduction

```powershell
python scripts/run_transport_buffer_recovery.py --verify output/transport_buffer_clean_recovery_2026_10_23
python -m pytest qa/test_transport_buffer_recovery.py qa/test_transport_buffer_preparation.py -q
```

New runs require fresh output directories:

```powershell
python scripts/run_transport_buffer_recovery.py --out output/transport_buffer_clean_recovery_new
python scripts/audit_transport_buffer_clean_recovery.py --archive output/transport_buffer_clean_recovery_2026_10_23 --out output/transport_buffer_scalar_crosscheck_new
```

Main evidence: `output/transport_buffer_clean_recovery_2026_10_23/summary.json`,72 per-fit JSON/NPZ pairs,24 multistart groups, four equivalent-family files, execution-design/input hashes and output manifest. Cross-check: `output/transport_buffer_clean_recovery_validation_2026_10_23/scalar_audit/scalar_crosscheck.json`. No dependencies installed.

## Next execution and boundaries

Next is the preregistered noisy synthetic comparison: concentration CV0.005, pH SD0.005, seeds2718/31415/1618, the same starts/bounds/budgets and temporal holdout. Specify the noise distribution, correlation and initial-observation handling before generating data; freeze common scenario realizations across observation-plan comparisons. Report failed fits and inaccurate parameters even when trajectories look good. Do not tune noise or choose a favorable seed after observing outcomes.

A simultaneous four-unknown fixed-Km stress test would be a separately declared extension, not a retroactive interpretation of these conditional stages. Original concentration-processing denominators, free/accessibility mapping, donor linkage, temperature-compatible pHi/pHe/buffer/gas/AE1 inputs and biological absolute-accuracy/covariance contracts remain unresolved. The old ATP deficit is unchanged and cannot be repaired by this ATP-free toy. No production default, biological readiness or calibration scope is promoted.
