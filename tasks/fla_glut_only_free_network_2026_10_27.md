# GLUT-only candidate in the free RBC network

Date: 2026-10-27. User authorizes the recorded next execution.

## Question

Does the experimental conditional GLUT candidate retain its glucose benefit when intracellular GLC is released as a predicted ODE state, rather than supplied by the measured time course? Does it worsen lactate or the adenylate partition? This is a fixed-parameter diagnostic, not a new optimizer or biological promotion.

## Prespecified execution

Use `config/fla_glut_only_free_replay.json` and the separately stored candidate `config/fla_glucose_real_candidate.json`. A new opt-in adapter, `src/rbc_glut_only_transport.py`, delegates exactly to the previous phase-native model when disabled. When enabled it replaces only raw VEGLC with the reversible GLUT law evaluated at current ODE GLC/EGLC, then recomputes reaction-consistent execution of the whole signed reaction vector. All other raw reaction laws, including VELAC, are unchanged at the same state. Their trajectories/fluxes may respond dynamically to altered concentrations; they are not artificially frozen.

Retain all113 concentration pools plus the existing pHi coordinate,100 reaction columns, exact55 nominal measured J1 entries and all frozen latent coordinates/kinetic context. The reference context is the existing distinct-phase-volume diagnostic with H0.58 and pHi clamped to its exact initial value. The clamp is a pre-existing diagnostic reservoir assumption, not a free physiological pH prediction. Do not activate MCT, import a measured pH37/pH22 as pHi4C, change native lactate transport, or force any measured concentration.

Three cases isolate effects: phase-native reference; reversible GLUT at seed conductance0.0879655887/day; reversible GLUT at learned conductance0.0272733183/day. Both GLUT cases retain Km_i3.49137424 and Km_e23.50088375. H0.58 is a borrowed working geometry, not matched donor metadata. No source conversion, uFBA, water fraction or source-day shift is applied.

Run each case with strict/ultrastrict BDF, first J1-J4, then J1-J10 and J1-J46 only after all cases/profiles at the preceding horizon pass numerical checks. Each replay integrates uninterrupted from the same J1 initialization. The gate concerns numerical validity and does not assert biological adequacy; poor source-data fits remain reported, not silently rejected or optimized away. Eighteen integrations are planned if all three stages pass.

Guards: checked concentration positivity; raw/executed stoichiometric RHS closure; accepted-step Gauss4/8 flux quadrature; daily executed reaction-integral/state-increment closure; strict/ultrastrict state and raw/executed integral agreement. Preserve each quadrature node, state, weight, interval and raw/executed reaction rate. The availability threshold remains0.001mM. The GLUT constitutive law uses the same nonnegative-substrate extension as the archived reversible adapter for numerical trial states, with complete-reaction availability limiting. No state or concentration derivative is independently clipped.

## Source comparison and interpretation

Source observations come from the previously verified770-cell local inventory and immutable original workbook lineage. All55 source J1 values must exactly match the frozen initialization. Compare EGLC, GLC, LAC, ELAC, ATP, ADP and AMP only at actual post-initial source times. J10 has no observed endpoint in the table: the available points through J10 are J4/J8, not an invented interpolated J10 measurement. For J46 also report J29-J46 late-source-point RMSE, preserving the historically exposed/internal status of that comparison.

Save all100 raw/executed reaction integrals and reconstruct each guard pool's signed reaction contributions. GLC accumulation/depletion can then be separated into VEGLC import and VHK consumption, and ATP production/consumption attributed without treating compensation as measured flux. Source identities, denominator/free-pool uncertainty and prior biochemical simplifications are not resolved by numerical closure. A fitted conditional rate is not automatically an independently identified active enzyme capacity.

## Joint nominal glucose observation audit

An additional source-only audit checks an independent constraint implied by the executed network: GLC has only VEGLC input and VHK consumption. With constant phase fraction H, transport cancels in the bag inventory, giving `integral(VHK) = -(H*delta_GLC + (1-H)*delta_EGLC)/H`. VHK is nonnegative in this kinetic context. The exact nominal source points consequently cannot be imposed as independent hard flux labels when this required integral is negative.

At H0.58, J1-J4 requires -0.0801209mM cell-basis HK integral, and J29-J32 requires -0.1540574. Across all physical constant H, the first interval requires H<=0.395985, while the later interval requires H>=0.814877; the exact pointwise intersection is empty. This is a conditional inventory inconsistency, not proof of biological impossibility or justification to add an unsupported glucose source. Variable phase volumes, observation uncertainty, source aggregation/normalization and pool meaning remain alternatives; no source value is changed.

For scale only, at H0.58 the extra external depletion needed to put the nominal HK integral exactly at zero would be0.110643/0.212746mM in these intervals. These are algebraic discrepancy magnitudes, not corrections applied to observations or estimates of assay noise. A joint observation likelihood can accommodate residuals while enforcing nonnegative executed HK; concentration-derived teachers are not separate independent evidence.

Evidence: `output/glut_only_free_network_validation_2026_10_27/observation_audit/joint_glucose_observation_audit.json`; source-reconstructing command `scripts/audit_joint_glucose_observations.py`. Two regression tests check consistent and opposed-geometry examples. No ODE, source rescaling, reaction addition, uncertainty floor or biological promotion is performed by this audit.

## Results and verification

All18 planned integrations completed: three cases x two tolerances x J4/J10/J46. Every preceding numerical stage passed before horizon extension. All352521 strict/ultrastrict state/integral comparisons pass. Daily executed balances pass38646/38646 checks; raw and executed Gauss4/8 comparisons each pass34200/34200. Minimum over saved accepted/dense/quadrature concentration states is0.0mM in all18 replays; no negative GLUT substrate extension occurs at checked quadrature nodes. This is checked positivity, not an interval-arithmetic proof between nodes. Raw/executed RHS closure maxima are0.0mM/day. Both strict and ultrastrict phase-native J4 reference times/states reproduce the previous archive bitwise.

The read-only verifier passes1914 checks, reconstructing hashes, integrals, source metrics and reaction attributions. Seven stored quadrature states per replay are checked against the live RHS and native non-VEGLC reaction laws. This does not substitute for independent physiological validation or a separately implemented whole-network solver. Receipt: `output/glut_only_free_network_validation_2026_10_27/archive_verification.json`.

Ultrastrict endpoints below are predictions, in the declared source coordinates (mM). J10 has no experimental endpoint in the source.

| Horizon | Case | EGLC | GLC | ATP |
| --- | --- | ---: | ---: | ---: |
| J4 | Phase-native reference | 21.892592 | 0.896525 | 0.000756350 |
| J4 | Reversible GLUT seed | 21.340378 | 1.156508 | 0.000701833 |
| J4 | Learned GLUT | 23.993020 | 0.081253 | 0.001862615 |
| J10 | Phase-native reference | 17.503819 | 4.034659 | 0.000110341 |
| J10 | Reversible GLUT seed | 16.884046 | 4.346869 | 0.000109137 |
| J10 | Learned GLUT | 21.743718 | 1.608273 | 0.000122499 |
| J46 | Phase-native reference | 12.509023 | 7.645483 | 0.000016775 |
| J46 | Reversible GLUT seed | 10.533405 | 8.939585 | 0.000016774 |
| J46 | Learned GLUT | 15.387647 | 6.204097 | 0.000016919 |

Nominal source J4 is EGLC25.24, GLC1.275821 and ATP1.079765mM. The learned candidate improves EGLC at this endpoint but worsens GLC; its small ATP increase is not restoration. At J46, compare all guard pools:

| Pool | Nominal source J46 | Phase-native reference | Learned GLUT |
| --- | ---: | ---: | ---: |
| EGLC | 12.915000 | 12.509023 | 15.387647 |
| GLC | 0.826365 | 7.645483 | 6.204097 |
| LAC | 6.462934 | 0.165110 | 0.158752 |
| ELAC | 28.363716 | 21.881117 | 21.720082 |
| ATP | 0.469757 | 0.000016775 | 0.000016919 |
| ADP | 0.165503 | 0.000001517 | 0.000001706 |
| AMP | 0.221310 | 1.071110 | 1.063145 |

Fit metrics use the same actual13 post-J1 source points per pool, without uncertainty weights or generated measurements. They are descriptive nominal RMSE, not a joint likelihood or independent flux observations.

| Pool | Reference RMSE J4-J46 | Learned RMSE J4-J46 | Reference RMSE J29-J46 | Learned RMSE J29-J46 |
| --- | ---: | ---: | ---: | ---: |
| EGLC | 3.444393 | 1.224563 | 2.435803 | 1.667415 |
| GLC | 5.361098 | 3.431573 | 6.509748 | 4.601485 |
| LAC | 4.704072 | 4.710397 | 6.018566 | 6.027067 |
| ELAC | 4.196288 | 4.261139 | 5.318441 | 5.427831 |
| ATP | 0.862730 | 0.862619 | 0.594888 | 0.594887 |
| ADP | 0.539073 | 0.539022 | 0.367501 | 0.367501 |
| AMP | 1.421060 | 1.407628 | 0.895900 | 0.884875 |

Thus the conditional candidate retains a lower whole-trajectory glucose error, but worsens the J46 EGLC endpoint versus the phase-native reference, slightly worsens lactate errors and does not solve adenylate partition or energy. Conditional-pilot and free-network RMSE must not be conflated: GLC was a measured/frozen input in the former, but is predicted here. The native reference's apparently good EGLC endpoint is also insufficient because its intracellular glucose and ATP are grossly inconsistent with nominal observations.

### Executed glucose and energy attribution

At H0.58 the nominal J1-J46 source increments imply8.997414mM cell-basis glucose import and9.294335mM integrated HK consumption under the specified two-reaction GLC balance. These are conditional balance-implied quantities, not independently observed fluxes or extra likelihood terms.

The reference executes VEGLC9.291397 and VHK2.769200mM, leaving GLC accumulation6.522197mM. The learned candidate executes VEGLC7.206876 and VHK2.126065mM, leaving GLC accumulation5.080811mM. Decreasing transport consequently reduces storage of intracellular glucose without recovering glucose utilization. VHK Vmax is already5.0 in the frozen context; another isolated increase of transport or VHK is not the justified next test.

The saved J46 ultrastrict quadrature distinguishes native rates evaluated along the limited trajectory from actually executed rates:

| Reaction | Reference native integral J4-J46 | Reference executed integral J4-J46 | Learned native integral J4-J46 | Learned executed integral J4-J46 |
| --- | ---: | ---: | ---: | ---: |
| VHK | 0.237630 | 0.046040 | 0.300153 | 0.108633 |
| VPFK | 0.180190 | 0.029764 | 0.197153 | 0.052387 |
| VGAPDH | 5.146090 | 4.946467 | 5.127117 | 4.946393 |
| VPGK | 11.248187 | 0.080478 | 11.358594 | 0.148984 |
| VPK | 0.084783 | 0.002824 | 0.187779 | 0.027344 |

PGK's positive-direction consumers are B13PG and ADP. ADP is the minimum-availability consumer at100% of quadrature-weighted time after J4 in the reference, and99.0862% for the learned candidate. Reconstructing `executed_PGK = native_PGK * clip(min(B13PG,ADP)/0.001,0,1)` matches all these saved rates exactly. The reference native-minus-executed PGK integral after J4 is11.167709mM. This attributes the availability factor along a given trajectory; it does not claim that removing positivity limitation would produce this ATP, or identify which parameter causally controls ADP depletion. Earlier threshold tests and B13PG/adenylate audits already document this issue; do not select a more favorable threshold by fit or repeat those tests as new evidence. VAK2 is adenosine kinase, not reverse adenylate kinase.

### Verification and decision

Initial11 adapter tests pass, covering disabled reference parity, single-reaction replacement, reverse/zero boundaries, amount closure, input immutability, rejection of forcing/legacy modes and candidate provenance. Two new source-inventory tests pass. Final full QA:1274 passed, two existing source-dependent skips, six existing Optuna warnings in125.89seconds; existing Python3.14/Pydantic startup warning persists. JUnit: `output/glut_only_free_network_validation_2026_10_27/qa_results_final.xml`. The earlier1272-passed run is preserved separately.

Numerical replay is accepted within the declared context; biological calibration is not. Keep the learned GLUT as a reversible experimental candidate, not a new production default. No optimizer, J1 change, source rescaling, new reaction, MCT activation, free-pH prediction or readiness override occurred. Original candidate/conditional archives remain intact.

## Next execution

Move from the conditional EGLC objective to a joint free-network concentration likelihood for EGLC/GLC/LAC/ELAC/ATP/ADP/AMP, with executed reaction-integral diagnostics and exact J1. Use actual source sampling, explicit total residual dispersion/covariance assumptions and no double-counting of concentration-derived teachers. Assess conditional feasibility on J1-J4, then J10 before J46, allowing coordinated energy/adenylate kinetic changes only in a separately declared reversible candidate. Carry reference and learned-GLUT starts; preserve the existing threshold and do not blindly reopen already exhausted single-parameter screens. Decide the kinetic block/bounds from the previous coupled energy evidence and identifiability, not from transport RMSE alone. Increase optimizer budget when convergence evidence warrants it. This is a proposed exploratory calibration, not source-lineage resolution or physiological promotion; source-pool/normalization, independent uncertainty, donor and acid/base constraints remain open.

## Reproduction

```powershell
python scripts/run_glut_only_free_replay.py --out output/glut_only_free_network_new
python scripts/verify_glut_only_free_replay.py --archive output/glut_only_free_network_2026_10_27
```

The archive seals executed code, source inputs, numerical design and outputs. Its verifier reconstructs stored quadrature integrals with weighted bin sums, daily balances, minima, source-point errors and reaction attributions; sampled live RHS/rates and preservation of other native reaction laws are checked at seven saved quadrature states per replay. This is not an independently implemented full-network solver or a re-execution of every stored quadrature node. The full fixed-context decision and prior archives remain separately auditable; no production defaults or source measurements are overwritten.
