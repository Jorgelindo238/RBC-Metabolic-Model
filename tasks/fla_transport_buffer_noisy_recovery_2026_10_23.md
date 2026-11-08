# FLA carrier-buffer noise robustness

Date: 2026-10-23. User requests the preregistered noise challenge after clean conditional recovery.

## Scope and protocol

Test the unchanged clean estimator at concentration CV0.005, pH SD0.005 and seeds2718/31415/1618. Freeze remaining distributions/initialization conventions and the six shared noise panels before fitting. Protocol: `tasks/fla_transport_buffer_noise_protocol_2026_10_23.md`; configuration: `config/fla_transport_buffer_noise.json`. Main archive: `output/transport_buffer_noisy_recovery_2026_10_23/`. The preparation and clean archives remain unchanged and verified.

Six random panels cover two synthetic contexts and three seeds. Each has87 union-grid times. Mean-preserving lognormal concentration noise applies after initialization; additive Gaussian pH noise includes initial assays. Initial concentration and pHe context remain known; initial pHi is hidden whenever it is estimated. Shared values at common times are identical across starts, scopes and schedules. Errors are assumed independent across channel/time conditional on the true physical trajectory, not fitted experimental covariance.

The original1mM/0.02pH cost scales, bounds, starts, finite differences, stopping rules and100 actual-call limit are unchanged. This is a stress test of the existing estimator, not a matched observation-likelihood estimator. Training ends at7.0417days; uninterrupted prediction extends through20.9583. All-state holdout error is measured against latent truth and noisy-observed-plan error is separately recorded. The original parameter/pHi/holdout limits are retained, even if noisy outcomes fail them. No seed, optimizer start or favorable endpoint is selected.

The underlying pHi changes only0.0049522/0.0059142 over training in the export/import contexts, comparable with the0.005 per-assay pH noise. Corresponding pHe changes are0.0444520/0.0530867. These source-independent toy signal ranges explain why oracle truth recovery is a demanding noise challenge; they are not formal identifiability or signal-to-noise confidence bounds. An observed pHi level can still constrain the initial pHi even when its time variation is weak.

Expected coverage:216 fits,72 three-start groups,24 scenario/schedule/stage/plan seed-dispersion panels, and12 equivalent-family controls. The216 runs are not independent datasets. Median estimates over all three starts support descriptive seed comparisons; three seeds per context do not support population confidence intervals.

## Results

All216 planned fits completed without a rerun or budget increase. All216 pass numerical checks;214 report optimizer success and two exhaust the100-call limit. There are9198 actual objective integrations,432 strict/ultrastrict full-horizon fitted validations and24 integrations for12 equivalent-family controls. Parameter accuracy passes78/216, latent holdout prediction102/216, and the complete recovery rule66/216. Twenty-one fitted vectors approach a declared bound. All72 three-start groups agree within the frozen agreement limits, despite many inaccurate estimates: multistart agreement does not establish truth recovery.

For each row below, the denominator is six context/seed panels. A panel passes a column only when all three starts pass it. Panels are shared between rows; these counts are descriptive, not independent replications of a population success rate.

| Estimated coordinates | Timing | Observations | Parameter pass | Latent prediction pass | Complete recovery pass |
| --- | --- | --- | ---: | ---: | ---: |
| Conductance | Sparse | LAC/ELAC | 1/6 | 6/6 | 1/6 |
| Conductance | Dense | LAC/ELAC | 6/6 | 6/6 | 6/6 |
| Conductance/beta_e | Sparse | LAC/ELAC+pHe | 0/6 | 1/6 | 0/6 |
| Conductance/beta_e | Sparse | LAC/ELAC+pHi+pHe | 0/6 | 0/6 | 0/6 |
| Conductance/beta_e | Dense | LAC/ELAC+pHe | 3/6 | 6/6 | 3/6 |
| Conductance/beta_e | Dense | LAC/ELAC+pHi+pHe | 3/6 | 6/6 | 3/6 |
| Access/pHi0 | Sparse | LAC/ELAC | 0/6 | 0/6 | 0/6 |
| Access/pHi0 | Sparse | LAC/ELAC+pHe | 0/6 | 0/6 | 0/6 |
| Access/pHi0 | Sparse | LAC/ELAC+pHi+pHe | 5/6 | 2/6 | 2/6 |
| Access/pHi0 | Dense | LAC/ELAC | 1/6 | 0/6 | 0/6 |
| Access/pHi0 | Dense | LAC/ELAC+pHe | 1/6 | 1/6 | 1/6 |
| Access/pHi0 | Dense | LAC/ELAC+pHi+pHe | 6/6 | 6/6 | 6/6 |

Across all72 scope/panel groups,26 pass parameter accuracy for all starts,34 pass prediction and22 pass complete recovery. Thirty-six runs predict adequately while failing parameter accuracy;12 meet parameter limits but fail the stricter joint latent prediction criterion. These are different endpoints, not contradictory validation decisions. Worst relative errors are0.8282 for conductance,0.5231 for beta_e and1.6667 for access_i; worst pHi0 absolute error is0.5259pH. Worst latent holdout scaled RMSE is13.1168 against the unchanged0.05 limit. These extremes occur across different fits and must not be combined into one parameter vector.

The best tested conditional configuration for access/pHi0 is dense independent observations with both pH channels. Sparse both-pH improves parameter recovery but does not consistently meet the original prediction tolerance. Dense timing does not reliably recover the two conductance/buffer coordinates, even when its trajectories pass prediction. The dense grid represents additional independent synthetic analytical samples, NOT interpolation of existing measurements. Densifying experimental curves or teacher fluxes cannot create this information.

All12 unknown-Km controls pass. Identical concentration/pHe predictions remain identical under their shared noisy observations; noise does not remove that structural family. Current results establish fragility of this existing estimator/design under the specified synthetic noise, not impossibility for every noise-aware estimator or full-network model, and not an experimental pHi requirement established from storage cohorts.

## Numerical and software verification

Full QA completed during execution:1232 passed, two existing source-dependent skips and six existing Optuna experimental warnings in195.95seconds. The pre-existing Python3.14/Pydantic startup warning remains. Focused noise/clean recovery QA:35 passed, including18 new noise tests; the full suite includes the final roundoff-aware bound diagnostic. JUnit: `output/transport_buffer_noisy_recovery_validation_2026_10_23/qa_results.xml`.

Tests cover the frozen noise levels and guards, reproducibility/stream separation, exact noise formulas, initial-observation policy, common schedule entries, holdout and hidden-pHi leakage, bound reporting and three-start grouping. No dependencies installed. Independent scalar DOP853 and parameter/holdout arithmetic cross-checks pass all216 fitted trajectories; maximum absolute five-coordinate discrepancy from ultrastrict BDF is3.9482e-8. Record: `output/transport_buffer_noisy_recovery_validation_2026_10_23/scalar_audit/scalar_crosscheck.json`. Numerical error at this scale does not explain the much larger noisy parameter errors. Neither passing software tests nor a numerically valid noisy fit implies biological parameter readiness.

The completed archive verifier passes all input/output hashes, reconstructs all six noise panels, all216 per-fit metrics,72 group records,24 seed-dispersion descriptions, bound/failure flags and12 equivalent-family controls. It reuses the implementation helpers and does not rerun every optimization call. The scalar audit separately codes the conservation-based rate and uses another integrator, but still tests the same intended toy mechanism rather than independent biology. Earlier clean/source preparation seals remain unchanged.

## Artifacts and reproduction

`scripts/run_transport_buffer_noise.py` separates prepare/run/verify phases. `noise_manifest.json` protects panels before fitting; final `manifest.json` protects the completed archive. Per-fit JSON files retain every objective evaluation and optimizer outcome; NPZ files retain strict/ultrastrict uninterrupted predictions, accepted solver steps and latent references. `multistart_groups.json` and `summary.json` preserve parameter/prediction/optimizer separation and complete seed coverage. `scripts/audit_transport_buffer_noise.py` provides a separately coded scalar-extent cross-check without modifying the old scientific code.

```powershell
python scripts/run_transport_buffer_noise.py --verify output/transport_buffer_noisy_recovery_2026_10_23
python -m pytest qa/test_transport_buffer_noise.py qa/test_transport_buffer_recovery.py -q
```

New campaigns need fresh output directories; never overwrite sealed panels or completed fits. No persistent memory update is authorized/performed. Biological observations, exact55 J1, initial latent biological pools, historical kinetics, OPLAH and the strict reaction-consistent reference are preserved. No full-RBC replay, ATP result or biological calibration/promotion is part of this noise challenge.

## Next decision

Do not respond by increasing optimizer budgets or treating all converged parameters as learned biology. A priority successor experiment is a paired comparison of the current design-weighted cost with the correctly specified synthetic observation likelihood on these SAME sealed panels, starts, bounds, budgets and acceptance limits. This separates estimator weighting from limited data information without selecting a favorable seed or collecting data first. This comparison is proposed, not executed.

For the declared noise model, noninitial concentration residuals can be `(log(Cobs/Cpred)+log(1+CV^2)/2)/sqrt(log(1+CV^2))`, and pH residuals `(pHobs-pHpred)/SD`. Exact known initial concentrations have no noisy likelihood term. Noisy assays of known initial pH remain constant residuals; unknown pHi must still be estimated without truth leakage. Keep parameter and predictive checks separate, and do not add concentration-derived teachers as independent likelihoods. A fair comparison should retain the current objective as its control and freeze all implementation choices before rerunning.

If matched-likelihood recovery remains weak, then inspect parameter profiles and design more informative early sampling or supported independent pHi/activity/affinity measurements. Joint four-unknown recovery and uncertain initial LAC/ELAC/pHe remain separately scoped extensions. None of these synthetic outcomes resolves the biological concentration-denominator, donor, active-pool or4C acid/base evidence gaps, nor the ATP deficit.
