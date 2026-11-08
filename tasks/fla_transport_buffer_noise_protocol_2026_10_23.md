# Three-seed conditional carrier-buffer noise challenge

Date: 2026-10-23. User authorizes the preregistered noise robustness stage following clean recovery.

## Frozen inputs and purpose

The October6 preparation supplies concentration CV0.005, pH SD0.005, seeds2718/31415/1618, bounds, three starts,100 actual objective integrations/start and acceptance limits. The October23 clean campaign supplies the exact objective, stages, solver and prediction checks. Neither earlier archive nor its hashed code/config is changed.

`config/fla_transport_buffer_noise.json` declares the remaining distribution, dependence and initialization conventions. A separate prepare command writes the full design, six random panels and their checksums before the run command can fit parameters. These conventions complete the noise design now; only the amplitudes/seeds and original fitting protocol were frozen in the earlier preparation. No outcome-driven tuning or seed selection is allowed.

This is an isolated, correctly specified, five-state synthetic transport/buffer problem. It has no ATP, metabolism, AE1, gas, carbonate or biological calibration. Original mM observations, exact55 Bordbar J1 and biological kinetics remain unchanged.

## Observation model

For noninitial concentrations, with independent standard normal analytical errors z:

```text
sigma_log^2 = log(1 + CV^2)
C_observed = C_true * exp(sigma_log*z - sigma_log^2/2)
pH_observed = pH_true + SD*z
```

The lognormal construction is mean-preserving and nonnegative. Conditional analytical errors are independent across channel and time, despite conservation-related underlying concentrations. This is an assumed synthetic assay model, not inferred experimental covariance. No clipping, projection onto a mass-balance constraint, redraw or smoothing is applied to the noisy observations. Invalid panels stop execution.

Initial LAC and ELAC are exact known context and are not noised or estimated. Initial pHe remains exact known context, with an independent noisy pHe assay. Initial pHi is exact known oracle context in conductance/conductance-buffer stages, but is estimated in the access/pHi stage; all observed initial pH assays are noisy. A noisy assay of a known initial coordinate contributes a constant residual, not an extra learned parameter. When pHi is estimated, its true initial value is never passed to the objective as the candidate value; only the declared start or current optimizer coordinate is used. This does not challenge uncertainty in initial LAC/ELAC/pHe, which would require another design.

NumPy PCG64 with SeedSequence([seed, frozen_scenario_index]) generates one four-channel panel for each of two contexts and three seeds. The time grid is the sorted union of sparse training,81 dense training samples, and four sparse holdout samples:87 time points. Shared panel entries are identical across starts, stages, observation plans and training schedules. The dense/sparse comparison uses the same random values at shared times; dense-only time samples add synthetic information.

## Fitting and assessment

Use the unchanged clean-stage free-coordinate sets: conductance alone; conductance/beta_e; access_i/pHi0 with the other inputs known. Stage/observation plans, two time grids, two contexts, three seeds and three starts give216 fits and72 three-start comparison groups. Fixed affinities remain synthetic oracle context, not biological evidence.

Retain clean design weights1mM and0.02pH; do not replace them with noise likelihood weights during this challenge. These are heuristic design weights, not the lognormal/Gaussian likelihood or a claim of statistical efficiency. Retain the same log/linear parameter coordinates, BDF profiles, differentiation step, stopping rules, bounds and100 actual objective calls including Jacobian evaluations. No extra budget, restart or best-seed selection. Budget-exhausted fits retain their recorded lowest-cost evaluated point for prediction, but are still optimizer failures.

Optimization ends at7.0417days. Later samples cannot enter the training objective or parameter selection. Full-horizon uninterrupted predictions through20.9583days are scored against untouched latent truth using the exact clean criteria: parameter relative error<=0.05, initial-pHi absolute error<=0.01 and all-coordinate scaled holdout RMSE<=0.05. Also report error against noisy observed training/holdout panels under the observed channel plan. Prediction agreement with observations, latent prediction, parameter accuracy and optimizer success are separate outcomes. Fluxes reconstructed from parent concentrations are not new independent measurements and are not added to the objective.

Keep all three starts, including failures, in within-panel agreement and descriptive medians. Seed dispersion is summarized from the median estimate over all starts for each panel/scope; this is not choosing the best start. Count216 optimization runs, not216 independent noisy datasets. The independent random panels number six; each context has only three seeds. No population confidence interval or donor-validation claim is supported.

## Numerical and negative controls

Check every fitted trajectory with strict/ultrastrict unforced prediction, nonnegative checked lactate coordinates, amount/acid/extent closure and accepted-step flux quadrature. Retain numerical failures rather than calling them parameter success. An unexpected invalid forward trajectory stops with a diagnostic rather than returning a finite penalty.

For each panel, select sparse both-pH access/pHi start0 by design, regardless of success, and apply both frozen accessibility/Km/pHi transformations. Twelve negative controls test the unknown-affinity equivalent family. Noise in concentrations/pHe cannot remove an exact equivalence of those predictions. No unique unknown-Km solution is claimed. The independently coded scalar DOP853 audit cross-checks all216 saved fitted trajectories and recomputes parameter/holdout arithmetic; this is computational validation, not independent biology.

## Artifacts and reproduction

Separate authoring modules: `src/fla_transport_buffer_noise.py`, `scripts/run_transport_buffer_noise.py`, `scripts/audit_transport_buffer_noise.py`, `qa/test_transport_buffer_noise.py`.

```powershell
python scripts/run_transport_buffer_noise.py --prepare output/transport_buffer_noisy_recovery_new
python scripts/run_transport_buffer_noise.py --run output/transport_buffer_noisy_recovery_new
python scripts/run_transport_buffer_noise.py --verify output/transport_buffer_noisy_recovery_new
```

Each run requires a fresh archive. The prepared random-panel seal is retained beneath the final completed-archive seal. Execution evidence is `output/transport_buffer_noisy_recovery_2026_10_23/`; validation is outside its seal under `output/transport_buffer_noisy_recovery_validation_2026_10_23/`. Results and next decisions are recorded separately after the campaign, without rewriting this protocol or the prepared noise.
