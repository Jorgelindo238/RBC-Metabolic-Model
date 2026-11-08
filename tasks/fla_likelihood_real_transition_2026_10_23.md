# Likelihood comparison and first conditional experimental transport fit

Date: 2026-10-23. User authorizes changing candidate kinetic constants as needed and makes optimizer budget secondary to progress toward real calibration.

## Executed paired likelihood comparison

Reuse the six exact sealed noisy panels and all216 archived current-cost fits; run216 new matched-likelihood fits with identical scopes, starts, bounds,100-call primary budget, solver and truth/holdout limits. No new noise or best-seed selection. Configuration: `config/fla_transport_likelihood_comparison.json`. Archive: `output/transport_likelihood_comparison_2026_10_23/`. Reusing the baseline is explicit:216 new fits, not432 newly executed fits.

The new observation likelihood is mean-preserving lognormal for positive concentration observations and additive Gaussian for pH. Known exact initial concentrations have no stochastic likelihood term. Initial pH policy is unchanged; hidden initial pHi is never supplied when estimated. The residual is `(log(y)-log(mu)+v/2)/sqrt(v)` with v=log(1+CV^2), or `(y-mu)/SD` for pH. `src/fla_observation_likelihood.py` also returns the complete negative log likelihood including normalizers. Missing noise inputs, nonpositive included log concentrations and nonfinite values raise; no synthetic CV default, zero imputation or clipping. Zeros in future experimental data need an explicit assay/censoring/zero model.

| Endpoint | Previous cost | Matched likelihood | Gained pairs | Lost pairs |
| --- | ---: | ---: | ---: | ---: |
| Optimizer success | 214/216 | 216/216 | 2 | 0 |
| Parameter recovery | 78/216 | 135/216 | 63 | 6 |
| Latent holdout prediction | 102/216 | 123/216 | 24 | 3 |
| Complete recovery | 66/216 | 117/216 | 54 | 3 |

Matched recovery passes all-start parameter/holdout/complete criteria in45/41/39 of72 panel/scope groups, versus26/34/22 previously. All72 groups agree across starts. There are8273 matched objective integrations. Sparse conductance/buffer recovery improves from0/6 to4/6 context/seed panels for either pH plan; dense improves from3/6 to6/6. Sparse access/pHi still fails without pHi, and dense concentration-only access/pHi remains weak. The likelihood helps substantially but is not a general identifiability cure, and three seeds/context give descriptive results, not population confidence intervals.

The user-approved budget extension is a separate secondary experiment, selected ONLY by optimizer failure, not by true parameter error or heldout score. Rerun either method's primary failures from their original starts with500 calls, then2000 only if still unconverged. Only two current-cost cases need extension; they converge in115/110 calls but still fail parameters and prediction. The2000-call stage is not needed. The original100-call results are never replaced. This directly distinguishes a budget limitation from a stable inaccurate optimum.

All216 matched fitted trajectories pass strict/ultrastrict, checked positivity, acid/amount/extent and flux-quadrature criteria. Independently coded scalar DOP853 and arithmetic checks pass all216, maximum absolute state discrepancy3.4434e-8. The12 archived unknown-Km controls also retain equal concentration/pHe likelihood; no new control ODE integrations are claimed. Unknown affinity/activity/pHi families are not resolved by choosing a different residual function.

Independent audit: `output/transport_likelihood_comparison_validation_2026_10_23/scalar_audit/scalar_crosscheck.json`. The comparison verifier reconstructs pair/group metrics and confirms that secondary selection depends on optimizer failure only. No source values or original archives are modified.

## Transition to actual concentrations

To move beyond synthetic recovery in the same session, construct a conditional GLUT pilot from original `src/Data_Bordbar_et_al_exp.xlsx:Sheet1` EGLC/GLC observations. Retain all56 source cells for GLC/EGLC/LAC/ELAC and all55 exact J1 coordinates with original locators. No normalization, inferred intracellular water, uFBA or donor assignment. The user-selected packed-cell/supernatant convention remains a working hypothesis, not certified source preprocessing.

The pilot predicts EGLC with measured intracellular GLC as a declared input. Training uses source days1-25; EGLC J1 is exact fixed initialization, and the seven later training EGLC samples supply the likelihood. PCHIP uses only training GLC samples and then holds the J25 input constant through J46. No heldout GLC or EGLC enters optimization or input construction. The later comparison is internal and historically exposed, not independent prospective validation. GLC is not predicted and its assay/input error is not propagated.

The fitted law is dE/dt=-a*(E-G)/(1+E/Km_e+G/Km_i), with a=H/(1-H)*k. Fixed Km_i and seed Km_e come from the archived reversible GLUT constructor. Test a alone, then a and Km_e, with three declared starts and up to4000 function calls in the numerical successor. Original data—not toy parameters—determine these candidates. Geometry scenarios0.574/0.58/0.632 convert a into conditional cell-basis k; they do not identify a matched Bordbar hematocrit. The corresponding constructor Vmax=k*Km_e is not automatically interchangeable with the historical native transport family's Vmax.

Experimental residual dispersion is profiled from training rather than set to the synthetic CV. For d=log(y)-log(mu), the exact stationary variance is v=2*mean(d^2)/(sqrt(1+mean(d^2))+1). Full lognormal normalizers are retained. `src/fla_profiled_observation_noise.py` rejects a zero-variance boundary rather than inventing a floor. This working dispersion includes model discrepancy, uncertain GLC input and assay error; it is NOT a separately measured analytical CV. Independent residuals are a working approximation, not verified experimental covariance. No ATP or MCT/pH parameter is inferred by this glucose-only pilot.

## Numerical successor and preservation

The first real-data pilot is preserved in `output/real_glucose_likelihood_pilot_2026_10_23/`. Its unsegmented adaptive solver failed some cross-integrator comparisons, and one optimizer termination was abnormal. Those fitted values are preliminary, not numerically promoted. Do not overwrite or describe that archive as passing verification.

A successor explicitly ends/restarts integration at every training input knot and the training cutoff, keeping the same physical state continuous. This prevents an adaptive solver from skipping known PCHIP-input structure; it is not state resetting or measurement forcing of EGLC. Strict/ultrastrict tolerances are tightened, finite-difference relative step declared, and optimization budget increased. The fixes are numerical changes, not relaxed accuracy requirements. Separate source/code/contract: `src/fla_real_glucose_pilot_segmented.py`, `config/fla_real_glucose_pilot_segmented.json`, `scripts/run_real_glucose_likelihood_pilot_segmented.py`. Archive: `output/real_glucose_likelihood_pilot_segmented_2026_10_23/`.

The successor completes all six fits with optimizer success and strict/ultrastrict/DOP853 agreement. Independent verification reopens all56 original concentration cells and55 exact J1 entries, re-integrates all six candidates and checks the extracellular transport integral against ODE depletion. Record: `output/real_glucose_likelihood_pilot_segmented_validation_2026_10_23/verification.json`. Original and repaired campaigns remain distinct; only the verified successor supplies candidates.

| Real-data conditional case | Effective clearance/day | Km_e, nominal mM | Profiled total residual CV | J29-J46 RMSE, nominal mM | Predicted EGLC J46 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Seed control at H0.58 | 0.1214763 | 23.50088 | not fitted | 11.8116 | 1.90112 |
| Clearance learned, Km_e fixed | 0.03766315 | 23.50088 | 0.0205150 | 1.14909 | 11.70122 |
| Clearance and Km_e learned | 0.02296759 | 500, upper bound | 0.0198732 | 0.80683 | 12.31106 |

Observed nominal EGLC J46 is12.915. Training contains only seven noninitial EGLC observations; selection within each case uses training NLL, not these later outcomes. The seed-control row is the same conditional one-pool model, not the earlier full-RBC baseline. The seed effective clearance is H/(1-H)*0.08796558869207803; its displayed rounded value is explanatory only.

At H0.58 the simpler fitted case implies cell-basis GLUT conductance0.027273318260890734/day instead of0.08796558869207803/day. Its constructor-equivalent Vmax is0.64094708, but this number cannot be blindly injected into a different native transport law. The source-based candidate is exported to `config/fla_glucose_real_candidate.json` with an explicit GLUT-only future scope. H0.574/0.632 give alternative conductances0.02795210/0.02193044: the data identify a conditional phase-weighted clearance, not a donor-independent cell conductance without geometry support.

Opening Km_e improves the later nominal RMSE but pushes two starts to500; the third stops near325.6 with a similarly flat training objective. The fitted clearance and affinity trade off. These observations do not identify a physiological500mM affinity and do not justify expanding that bound automatically. Retain the simpler fixed-affinity candidate for the first whole-network test, while preserving all opened-affinity fits for later profiling. No candidate has yet passed full-RBC replay or biological accuracy criteria.

The real-data pilot does not use pH or lactate forcing, infer missing ATP pools, alter measured J1, or claim the2% profiled dispersion is assay precision. In particular, the improvement obtained with known GLC input need not survive when GLC is released to the full glycolytic ODE. That is the immediate test, not a conclusion from this conditional fit.

## Software validation

First objective/profiled-noise tests:25 passed. Final focused likelihood/real/segmented tests:29 passed. Full final QA1261 passed, two existing source-dependent skips and six existing Optuna warnings in87.20seconds; pre-existing Python3.14/Pydantic startup warning remains. JUnit: `output/transport_likelihood_real_transition_validation_2026_10_23/qa_results.xml`. A preliminary full run before the segmented repair passed1257 tests and is not substituted for the final run. No dependencies installed.

The matched synthetic comparison's archive verifier and independent scalar audit pass. The first real archive intentionally retains its failed numerical diagnostic; the segmented successor passes original-cell, candidate-prediction, profiled-NLL and external flux/extent verification. Do not conflate these checks with statistical identification or independent clinical/biological validation. Candidate constants changed; production defaults did not.

## Boundaries and next execution

Candidate kinetic constants are editable under the user's current instruction; the previous100-call limit is no longer a general project cap. Source measurements and exact J1 are data, not kinetic constants to adjust. No synthetic transport estimate is copied into the biological ODE. The conditional pilot is real-data parameter learning, but it is not free whole-network prediction: GLC is externally supplied, source normalization is conditional, and ATP/ELAC/LAC are not simulated.

Next should be a reversible glucose-only candidate injection and fixed-context whole-network replay, retaining native lactate transport while MCT pHi/pHe support remains unresolved. Prefer the simpler verified candidate if the opened extracellular affinity reaches its bound or is poorly identified. Check EGLC, GLC, LAC, ELAC, ATP/ADP/AMP and executed flux budgets before long-horizon multivariate optimization. Further synthetic expansions are not the main deliverable now. FLA-derived teachers share source concentrations and must not be counted as independent observations.
