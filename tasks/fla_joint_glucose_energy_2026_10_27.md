# Joint glucose-energy-adenylate calibration

Date: 2026-10-27. User authorizes the proposed joint calibration. This is a new, reversible exploratory campaign, not a change to the older blocked physiological protocol or platform defaults.

## Question and frozen context

Can coordinated kinetic changes improve the joint nominal glucose/lactate and adenylate observations when every concentration is predicted by the free RBC ODE? The preceding GLUT-only candidate reduced glucose trajectory errors but left glucose accumulation and near-zero ATP. Small isolated/coupled perturbations had already failed; they are not rerun as a new calibration.

Use `config/fla_joint_glucose_energy.json`, exact55 original Sheet1 J1 values from `src/Data_Bordbar_et_al_exp.xlsx`, and unchanged latent initialization/other frozen kinetics. Preparation independently reopened the workbook and checked all770 concentration cells against the preceding sealed inventory. In particular, neither historical XLS initialization nor a redox-pool prior replaces J1. Keep H0.58 borrowed phase geometry, native VELAC, clamped diagnostic pHi7.2, reaction_consistent execution and0.001mM threshold. OPLAH remains present. No source rescaling, new reaction, MCT activation, teacher forcing, observation reset or artificial ATP source.

## Kinetic block

Six log-factor coordinates adjust nine primitive kinetic quantities (GLUT conductance plus eight Vmax values), leaving all affinities and unmeasured initial pools unchanged. These groups reduce exploratory degrees of freedom; grouping different enzymes is a diagnostic restriction, not evidence for a common enzyme complex or shared biological capacity.

| Coordinate | Changed quantities | Factor range relative to frozen seed |
| --- | --- | --- |
| GLUT_conductance | Reversible GLUT conductance only | 0.1-4 relative to learned GLUT |
| investment | VHK and VPFK Vmax together | 0.02-1 |
| AK_capacity | Adenylate kinase forward/reverse Vmax together | 0.001-2 |
| GAPDH_PGK_capacity | VGAPDH and VPGK Vmax together | 0.25-16 |
| PK_capacity | VPK Vmax | 0.25-32 |
| PEP_PASE_capacity | Competing VPEP_PASE Vmax | 0.001-1 |

HK cannot exceed its retained5.0 ceiling. Scaling both AK directions preserves the existing forward/reverse capacity ratio; it does not validate the phenomenological AK equilibrium law. Bounds are declared exploratory search limits, not physiological priors, confidence intervals or validated active capacities. Neither proteomic abundance nor source-relative signal is converted into Km. Historical purine controls, VAMPD1 activity-decay hypothesis and unverified NAD=NADH=1mM remain fixed diagnostic assumptions.

Three deterministic starting points distinguish learned GLUT, the previous reversible GLUT seed conductance and coordinated energy changes. They use the same new reversible GLUT family; the phase-native law is retained separately as an archived comparator, not silently equated to this conductance. Every start has the same search space and objective. Continuation at J10 retains each start's own lowest valid J4 point, without selecting by later predictions.

Continuation means a parameter warm-start only. Every ODE integration starts from the exact frozen J1 state, not the previous J4 endpoint or an observed state at J4/J8.

## Joint observation likelihood

Only EGLC/GLC/LAC/ELAC/ATP/ADP/AMP at actual post-J1 source times enter the likelihood. J1 is exact initialization, not seven extra residuals. At the J4 stage there are seven observations, one per pool. At J10 there are14 observations at J4/J8; no experimental J10 endpoint is invented. This small sample does not support six independently identified kinetic coordinates or a flexible observation covariance.

Use a mean-preserving lognormal observation model, with one shared total relative residual dispersion across all seven pools and source times. With positive observation y, ODE mean mu and d=log(y)-log(mu), the full likelihood contribution is `0.5*(d+v/2)^2/v + log(y) + 0.5*log(2*pi*v)`. Profile `v=2*mean(d^2)/(sqrt(1+mean(d^2))+1)`. Retain normalizers. The shared variance prevents a separately fitted ATP variance from absorbing failure in that pool. It is total residual dispersion including model/source/assay discrepancy, not known analytical precision, and does not validate nominal units or free/total pool mappings.

Conditional independence and common log variance are explicit working assumptions, not measured temporal/inter-pool covariance. Report each pool's absolute/log errors alongside the pooled objective. Do not supply a synthetic CV, zero floor, imputed concentration or unsupported assay uncertainty. Concentration-derived flux teachers are correlated transformations of these same observations, so they are not counted again as independent likelihood terms. Flux supervision in this pass is physical executed-network accounting, not noise-free pointwise labels.

## Execution and numerical audit

- [x] Implement isolated source-extracted fitting RHS and six-coordinate parameterization.
- [x] Pass21 focused tests: all100 native/executed reaction rates and full RHS exactly match the existing adapter at five fixed/random/boundary contexts; scalar MM boundaries, group scope, shared likelihood arithmetic and conservative Jacobian support are checked.
- [x] Reopen the original770 source cells; preserve all55 measured J1 and frozen latent entries; seal new code/config/source before fitting.
- [x] Pass final full QA1298/two existing skips/six existing Optuna warnings in179.16seconds, including three separate workflow controls for future-source isolation, actual integration caps and signed budget reversals. The earlier1295-passed receipt is retained. Existing Python3.14/Pydantic startup warning persists.
- [x] Fit all three starts on J1-J4: all optimizers converge, using147/231/354 actual objective integrations (732 total). Selected coordinated-energy NLL14.541840 versus the other starts14.541842/15.140510; the first two are effectively tied, not evidence of a uniquely best biological constant set. The learned-GLUT start needs the separately recorded secondary budget. Original full-adapter strict/ultrastrict and source-extracted/full-path checks pass. J4 ATP0.280234mM versus learned-GLUT-only0.001863 and nominal1.079765; this is improvement, not restoration.
- [x] After the selected J4 numerical gate passes, complete all three J1-J10 continuations. All converge, using119/119/154 objective integrations (392 total); selected learned-GLUT start NLL35.611361, effectively tied with coordinated-energy35.611362, versus seed-start35.893100. Original full-path strict/ultrastrict and fast/full trajectory checks pass. J10 endpoint ATP0.078564mM is a prediction, not an observed J10 assay. All optimization stages total1124 actual objective integrations.
- [x] After the selected J10 numerical gate passes, replay the same candidate freely to J46 without using J11-J46 for kinetic selection. Original full-path strict/ultrastrict and fast/full state checks pass. Numerical success does not rescue late ATP, intracellular glucose or PEP.
- [x] Verify archive reconstruction:2556 checks pass, including all33 protected inputs and45 archived output hashes. Final full QA1298 passed/two skipped. Report fit/transfer failures explicitly; no biological promotion.

Fitting uses the exact rate-expression prefix extracted from the trusted local kernel AST, before its historical derivative/audit work. It retains original helper bodies and a scalar MM finite test with the same arithmetic. No historical source file or global function is monkey-patched. A conservative Jacobian support is derived from source state reads and all participating reaction pools, including both signs and helper branches; unknown whole-state operations fall back to all columns. This is not sparsity inferred from sampled numerical zeros. Unit checks probe finite-difference support, but final dense/reference-path replay is the decisive safeguard.

L-BFGS-B uses a fixed0.002 log-factor one-sided finite difference respecting bounds and strict BDF. Memoization avoids identical integrations; actual integration counts include every Jacobian perturbation. Primary cap250 per start/stage and a separate cumulative600-call restart only on optimizer failure are engineering limits, not a project-wide budget rule. Optimizer success, budget exhaustion, bound hits, terminal point and lowest valid evaluated point are recorded separately. No convergence or biological success is inferred from selecting an uneventful last iterate. Three numerical worker processes execute the starts; these are not agent-created tasks.

The selected point is the lowest valid training NLL among all evaluated points, including finite-difference probes, not necessarily the optimizer terminal point. Record that distinction explicitly. Unsuccessful optimizers remain unsuccessful even if an improved candidate can be audited. Candidate selection never uses late source errors. Poor biology does not masquerade as a numerical failure, and a failed numerical gate stops horizon extension.

For selected candidates, use the original `rbc_glut_only_transport.py` adapter, all113 concentration pools and100 raw/executed rates. Retain complete Gauss4/8 node/state/weight/rate evidence, daily matrix balances, strict/ultrastrict comparisons and seven guard-pool reaction attributions. Compare source-extracted and original whole-network trajectories as well as sampled RHS/rates. The numerical threshold is not fitted. Native rates along a limited trajectory are not a no-limiter counterfactual.

## Results and decision

Complete: six optimizer fits, all converged;1124 actual objective integrations, all valid, including Jacobian perturbations. Five fits converge within the250-call primary cap; the learned-GLUT J4 start exhausts250 and converges after104 additional integrations under the600 cumulative cap. This is not1124 independently audited full-path quadrature replays: there are six original-adapter selected-candidate audit integrations, plus selected-point fitting-path replays. All source values, initial states, affinities and production defaults remain unchanged.

Numerical acceptance passes117507/117507 strict/ultrastrict state/rate-integral comparisons,12882 daily executed-balance checks and11400 comparisons each for native/executed Gauss4/8 quadrature. Checked concentration minima are0mM in all six full replays; raw/executed closure maxima0mM/day. This is checked positivity, not an interval proof between nodes. The source-extracted fitting RHS and original full-path trajectories agree within the declared limits. Archive verification passes2556 reconstruction/sampled-live-RHS checks; it does not re-execute all optimization trajectories or independently validate biology.

Decision: accept the numerical execution, reject the candidate as a new biological working reference. Early energy partition improves, but long-term ATP remains depleted and an untrained measured pool, PEP, regresses severely. No readiness override or automatic promotion follows from a low training NLL or an excellent extracellular glucose endpoint.

### Training likelihood and fitted capacities

The same nominal observations and source times enter each within-horizon comparison. NLL is descriptive conditional fit, not evidence that the added parameters are independently identified or a likelihood-ratio significance test.

| Training horizon | Observations | Phase-native NLL | GLUT-only NLL | Selected joint NLL | Joint total residual CV |
| --- | ---: | ---: | ---: | ---: | ---: |
| J1-J4 | 7, at J4 | 43.341066 | 40.823325 | 14.541840 | 0.804187 |
| J1-J10 | 14, at J4/J8 | 93.714744 | 91.356916 | 35.611361 | 1.223270 |

The two best starts are effectively tied at each horizon. The J10 selected start is learned_GLUT; its final conductance is0.0448414170/day. Shared residual CV1.22327 is122.3% total residual dispersion, NOT experimental assay precision or permission to tolerate these biological errors. Initial pools and unmodeled discrepancy contribute to this quantity.

| Primitive quantity | Previous frozen value | Selected J10-fit value |
| --- | ---: | ---: |
| GLUT conductance, /day | 0.0272733183 | 0.0448414170 |
| vmax_VHK | 5.000000 | 0.351874 |
| vmax_VPFK | 2.549431 | 0.179416 |
| vmax_VAK | 3.417627 | 0.003417627 |
| vmax_VAK_rev | 0.317443 | 0.000317443 |
| vmax_VGAPDH | 6.389868, native default | 1.597467 |
| vmax_VPGK | 40.022631 | 10.005658 |
| vmax_VPK | 0.713423 | 0.178356 |
| vmax_VPEP_PASE | 8.949949 | 0.008949949 |

Vmax values retain the cell-normalized model rate units. Four coordinates reach their declared lower limits: AK_capacity0.001, GAPDH_PGK_capacity0.25, PK_capacity0.25 and PEP_PASE_capacity0.001. These boundary solutions are not identified physiological capacities. All affinities and other model parameters stay frozen.

### Early improvement is not sustained prediction

The J4-trained candidate reaches ATP0.280234mM at J4, compared with GLUT-only0.001863 and nominal1.079765. This historical stage must not be confused with the final J10-trained candidate. With the latter's single fixed parameter set, ATP is0.152875 at J4,0.112545 at J8 and0.000021290 at J46, versus nominal1.079765/1.272527/0.469757mM.

Final J10-trained candidate, ultrastrict original-path replay to J46:

| Pool, mM in its declared compartment | Nominal J46 | Previous GLUT-only | Joint candidate |
| --- | ---: | ---: | ---: |
| EGLC | 12.915000 | 15.387647 | 12.930681 |
| GLC | 0.826365 | 6.204097 | 7.365007 |
| LAC | 6.462934 | 0.158752 | 0.049733 |
| ELAC | 28.363716 | 21.720082 | 19.908172 |
| ATP | 0.469757 | 0.000016919 | 0.000021290 |
| ADP | 0.165503 | 0.000001706 | 0.000000254 |
| AMP | 0.221310 | 1.063145 | 0.932696 |
| PEP, not fitted | 0.011204 | 0.000146 | 4.942643 |

EGLC's endpoint error is only0.015681mM, but this does not establish correct glucose utilization. In cell-basis integrals, VEGLC imports8.986058mM and HK consumes2.744338, leaving GLC accumulation6.241721. At H0.58, nominal source increments imply import8.997414 and HK9.294335mM, with intracellular GLC change-0.296921. These requirements remain conditional on the observation/geometry contract, not independent measured fluxes.

| Pool | GLUT-only RMSE, all13 post-J1 points | Joint RMSE, same points |
| --- | ---: | ---: |
| EGLC | 1.224563 | 1.414239 |
| GLC | 3.431573 | 4.347856 |
| LAC | 4.710397 | 4.747305 |
| ELAC | 4.261139 | 6.173086 |
| ATP | 0.862619 | 0.829556 |
| ADP | 0.539022 | 0.398647 |
| AMP | 1.407628 | 1.113983 |

Thus modest adenylate trajectory-error gains coexist with worse glucose/lactate errors versus the GLUT-only candidate. With each model's own early-fitted dispersion frozen, late J11-J46 NLL is1736.490 for the joint candidate versus581.936 for GLUT-only. This is an exposed internal predictive-score comparison, not an external validation or evidence that assay variance changed. Only early data were fitted; this failure is not a proof that no parameter set or longer-window calibration could fit the network.

### Off-objective regression and executed ATP expenditure

Secondary reporting compares all48 non-objective source-channel representations individually. These are not48 independent assays; exact duplicate aliases and unresolved independence remain flagged. No off-objective result or late source value was used to select the candidate.

PEP RMSE over all13 postinitial points worsens0.019981 ->3.187252mM, and J46 PEP is4.942643 versus nominal0.011204mM. The failure is already visible on training days alone: J4/J8 PEP RMSE0.027824 ->1.123899mM, so protecting PEP need not leak later observations into fitting. Early G6P RMSE improves1.402464 ->0.944753, although full-period G6P worsens0.595678 ->0.616120mM. PYR improves2.918737 ->1.910762mM over the full period. All144 comparator/pool rows remain available; no aggregate independent-channel count or cherry-picked whole-network success is claimed.

Executed ATP production/consumption below integrate positive and negative signed reaction contributions BEFORE netting; they are not microscopic forward/reverse gross enzyme exchange. Native rates along a limited trajectory are not a no-limiter counterfactual.

| J1-J46 ATP budget, mM cell basis | GLUT-only | Joint |
| --- | ---: | ---: |
| Positive executed contributions | 5.871436 | 10.854335 |
| Negative executed contributions, magnitude | 6.804411 | 11.787306 |
| Net executed increment | -0.932975 | -0.932971 |

About4.983mM additional ATP production is offset by approximately the same additional consumption. Dominant net ATP expenditures in the joint replay include VNDPK3.163899, VHK2.744338, VPRPPASe1.593547, VPFK1.335535 and VRKa0.999975mM. OPLAH remains active and consumes0.393717mM. This is signed flux accounting, not evidence that suppressing one term will recover that quantity of ATP after feedback.

After J4, native PGK along the joint trajectory integrates6.842341mM, while executed PGK integrates0.723325. Its native-minus-executed availability allocation is3.319691mM to B13PG and2.799325 to ADP. It is limited at all sampled post-J4 quadrature nodes; no threshold is selected by fit. Earlier GLUT-only allocation was0.253434/10.956176mM. Improved ADP partition has therefore not removed depleted-pool execution limits.

Several frozen initial coordinates are unmeasured: RIB/PRPP/GTP/GDP/ADO/ADESUC/NAD/NADH are1mM; R5P is1.611091mM from the prior latent context. IMP is different: its measured J1 value0.124119mM is preserved, not a1mM latent assumption. RIB has the exact sole balance `dRIB/dt=-VRKa` in this model. The final candidate spends0.999902mM ATP through VRKa by J4, almost the entire unmeasured initial1mM RIB. This is a concrete initial-demand assumption, not an inferred ribose concentration or proof of the ATP effect of reducing RIB. It motivates a subsequent separately declared latent-pool test, not an unrecorded initialization change in this run.

## Deliverables and safeguards

Scientific archive: `output/joint_glucose_energy_calibration_2026_10_27/`. Read-only verifier: `scripts/verify_joint_glucose_energy.py`; receipt `output/joint_glucose_energy_validation_2026_10_27/archive_verification.json`. Secondary comparison/candidate export: `output/joint_glucose_energy_validation_2026_10_27/comparison/`, including all per-pool errors, executed budgets, volume bases, PGK availability windows and the non-promoted candidate. Restore the old reference by not enabling the exported overrides; no production file was replaced.

An additional arithmetic check uses SciPy's lognormal density for late NLL and reaction-wise dot products for signed ATP production/consumption. Differences from the report are2.3e-13 and less than4e-15 respectively. This checks arithmetic, not physiological truth. All33 new-campaign inputs and45 outputs pass their scientific seal. Full QA1298 passed, two existing source-dependent skips, six existing Optuna warnings in179.16seconds; the earlier1295-passed run is retained separately. The existing Python3.14/Pydantic warning persists.

Final focused rerun after the reporting edits:24 passed in14.08seconds, receipt `qa_focused_final.xml`. A final hash pass checks151 protected entries across the new campaign, preceding GLUT-only archive and secondary comparison, with no mismatch. Project documents stay editable outside these scientific seals.

## Next execution

Do not promote this candidate or merely enlarge the kinetic box. The next calibration should be a protected successor on the same J1-J10 source times, initialization and six kinetic coordinates: include PEP/G6P observations and predeclare component-wise non-regression against the archived GLUT-only control for the nine monitored pools. Calculate guard reference errors on J4/J8 only; do not use J11-J46 to choose constants or guard limits. A numerical-comparison allowance is an engineering tolerance, not invented assay precision. The control remains an admissible fallback; if no improving feasible candidate is found, report that result without relaxing guards. Replay to J46 only as internal temporal transfer after numerical checks. This directly addresses the demonstrated subset-objective regression.

Only after that controlled objective comparison should a separately recorded RIB(0) latent-initialization feasibility test be considered, preserving all55 measured J1 values and explicitly labeling any search range as diagnostic rather than a physiological prior. Track VRKa, PRPPASe, NDPK and the complete adenylate/PEP budgets; no promised ATP rescue or automatic physiological inference. Source-pool/normalization, covariance, donor and acid/base readiness remain unresolved.

## Reproduction

```powershell
python scripts/run_joint_glucose_energy.py --prepare output/joint_glucose_energy_new
python scripts/run_joint_glucose_energy.py --run output/joint_glucose_energy_new --workers 3
python scripts/verify_joint_glucose_energy.py --archive output/joint_glucose_energy_calibration_2026_10_27
```
