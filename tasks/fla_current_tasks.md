# FLA Current Tasks

Last updated: 2026-11-04

## Active Handoff (Supersedes Historical Next Steps Below)

CURRENT PASS: fixed GAPDH/AK coupling J1-J4 screen completed. Report
`tasks/fla_b13pg_ak_coupled_results_2026_11_04.md`. Reopened770 Sheet1 cells:
B13PG/B23PG and P2G/P3G exact aliases, adenylate form/denominator unresolved.
Preserved all J1 values and excluded B13PG/P2G from independent scoring.
Six original replays with GAPDHx1.5 and both AK capacitiesx0.5, isolated and
combined, plus two reused controls. PGK fixed. Coupled later executed PGK
increases0.202344 ->0.287589mM and ATP J4 0.023747 ->0.056615mM versus nominal
1.079765. Log-error gain51.21%, mostly AK-only50.66%; ADP still0.033320mM.
No perturbed case passes off-target guards. Coupled fails G6P/F6P/PEP and
others even ignoring ambiguous P3G. Six original profiles, three fast-parity
replays,103839 cross-tolerance comparisons and21 tests pass. No wider search,
J46 extension or promotion. Next assess downstream throughput and demand
compensation rather than increasing the same two levers.

PREVIOUS PASS: frozen-flux J1-J4 energy feasibility completed. Report
`tasks/fla_j1_j4_energy_results_2026_11_04.md`. Five scenarios, both original
half-step profiles. No scenario fits the ATP/ADP/AMP unit bands, even with
the PGK raw ceiling removed. J4 H maximum0.193544mM versus nominal1.616392;
best band multiplier14.6962, limited by AMP/PRPP. PGK raw/executed H gap
1.050879mM attributed to B13PG; fixed neighboring fluxes leave only0.000134751mM
additional B13PG consumption. ADP cannot increase under these directions.
Conditional rejection, not global kinetic impossibility. Yurkovich4C:72
source rows checked, ATP/ADP signals rise in the three sheet-specific blocks;
no cross-sheet join, charge or ATP anchor. Reproduce600 ledger rows and30
certified LPs,16 targeted tests. No new ODE, kinetic selection or refit.
Next: reconcile observation definitions and a justified coupled upstream
supply/adenylate partition hypothesis before any wider search.

PREVIOUS PASS: fixed VSAM/PGK half-step J46 replay completed. Report
`tasks/fla_vsam_pgk_j46_results_2026_11_04.md`. Two new original profiles,
two archived controls, no forcing/refit. All55 guards pass J4-J15, J18-J46
and J4-J46 at both tolerances. Ultrastrict log-adenylate error reductions
0.382965%/0.259646%/0.290459%, respectively. Twenty late raw RMSEs rise within
allowances. ATP J46 1.782852e-5 versus reference1.774790e-5 and nominal
0.469757mM. The late balance erodes most of the small J15 ATP advantage.
10170 daily balances,9000 raw/9000 executed quadrature and46403 convergence
comparisons pass. Verified330 metric rows/1540 source-time rows and34 targeted
tests. Preserve the half-step as a conditional comparator; do not widen the
search on this modest result. No biological validation or default change.
Archives `output/vsam_pgk_j46_2026_11_04/` and
`output/vsam_pgk_j46_comparison_2026_11_04/`. J46 is historically exposed.

PREVIOUS PASS: small VSAM/PGK fixed interaction screen completed. Report
`tasks/fla_vsam_pgk_screen_2026_11_04.md`, archive
`output/vsam_pgk_screen_2026_11_04/`. Five points, four new original replays,
two fast-parity and six reused original controls. Both joint settings pass
numerically; only joint half passes all55 engineering guards, individual
adenylate and timewise tests, and improvement over the admissible control at
both tolerances. Tested VSAM0.19518001458970666/PGK39.17685218740367; conditional
comparator only. Mean log gain0.3830%; full joint0.7586% fails AMP. VSAM-only
now fails AMP and PGK-only ADP J4 under the stronger contract, not a change
to their historical admission. Half-step ATP J15=8.390680e-5 versus baseline
8.335252e-5 and nominal1.0138273mM; no rescue. Raw RMSE rises in16/55 ultrastrict
channels within the working allowance. Four-corner interaction nearly additive.
No optimizer, source/initial-state change, active new branch or promotion.
Thirty targeted tests pass; verification rebuilds550 channel rows and1000
reaction rows in `output/vsam_pgk_screen_validation_2026_11_04/`.

The proposed matched free J46 replay is completed above. Branch kinetics,
ARGSUC inventory and CITR/pool/volume provenance remain unresolved before
activation of new coverage reactions.

PREVIOUS PASS COMPLETED: network/observation coverage contract
and adenylate sensitivity. Report `tasks/fla_coverage_adenylate_sensitivity_2026_11_03.md`;
sealed archive `output/coverage_adenylate_sensitivity_2026_11_03/`; verified
comparison/receipts `output/coverage_adenylate_sensitivity_validation_2026_11_03/`.
All101 fixed-IC J1-J15 probes valid (25 positive parameters, four offsets each).
Two individually original-validated levers: VSAM0.2 ->0.19047619 and
VPGK40.14432755 ->38.23269291. Aggregate log-adenylate gains0.5385%/0.2229%,
NOT ATP rescue; PGK-down slightly worsens ATP J15. No combined activation,
optimizer or production promotion. Local12x25 sensitivity rank12 leaves at
least13 unresolved directions;45 highly correlated column pairs.

Coverage contract now records optional citrate lyase/arginase, ZERO defaults,
no guessed constants, exact rollback and OPLAH retained. Eight LP scenarios
plus two separate signed-ARGSL follow-ups reduce J15/J46 necessary engineering
multipliers1.661963/2.804155 ->0.344415/0.479320, but do not prove ODE existence.
ARGSL is structural-only, latent ARGSUC stock unconstrained; CITR remains
static. ASS1 is detected in Deep Red but absent from pinned GEM, requiring
curation. Source normalization/pool ambiguity is not resolved by adding columns.
No new branch was active in real-data ODE runs; full physical coherence remains
open. Original4 replays pass76338 convergence/6328 daily-balance checks;
primary3045/secondary1708 checks and1433 QA tests pass (two existing skips).
All770 source cells/55 exact J1/latent ICs and baseline configuration unchanged.

The proposed joint screen from `comparison/next_single_levers.json` is now
completed above. Recompute sensitivities if new coverage branches are activated.
Historical statuses below refer to predecessors and must not be resumed as the
current task.

PREVIOUS PASS: priority objective reformulation COMPLETED. Report
`tasks/fla_objective_reformulation_2026_11_03.md`; archive
`output/fla_objective_reformulation_2026_11_03/`; comparison/readiness in
`output/fla_objective_reformulation_validation_2026_11_03/comparison/`.
Eight converged fits,208 actual objective integrations, seven original audit
pairs pass278617 convergence checks/32770 daily balances. Primary2299 and
secondary1444 checks; six LP optima certified by21 analytic certificates;
770 source cells/55 J1 exact. QA1411 passed/two skips. Old13 caps are explicitly
diagnostics for ALL three refitted objectives, not changed in old archives.
Normalized mean better retains F6P; naked minimax trades F6P error0.156857 ->
339.304 for small AMP gain343.776 ->339.304, so reject it as default. No
biological calibration: J46 ATP about1.8e-5mM, GLC about6.96mM. HK reaches
0.1 search floor. No production promotion or all-time non-regression claim.

ULTIMATE USER GOAL: automated source-aware calibration for other groups' raw
and/or relative intra/extracellular data. Three-type observation operators,
cohort separation, manifest-validation CLI and synthetic JSON example exist;
generic raw import/relative ODE fitting are NOT complete. Readiness distinguishes
numerical checks from biological success. PREVIOUS NEXT (addressed above): source/GEM-informed coverage
audit of constant CIT+0.724138ECIT, ARG+0.724138EARG and CITR versus varying
nominal data; separate missing dynamics from normalization/binding/volume/cohort
effects before another optimization. No artificial sinks. Then sensitivity-directed
adenylate parameter selection, not another HK/PFK-only search. Exact ICs,
pH/native VELAC/Hct/OPLAH/threshold unchanged. No jobs are running.

Historical predecessor status follows; do not resume it as the current task.

Session status: reversible VHK/VPFK dissociation COMPLETED on2026-11-03. Report `tasks/fla_hk_pfk_split_2026_11_03.md`; archive `output/hk_pfk_split_2026_11_03/`; opt-in export `output/hk_pfk_split_validation_2026_11_03/comparison/candidate.json`. All four starts converge (paired17/31, split69/45 calls),162 objective integrations plus nine fixed screens. Same22-value NLL96.615834 ->91.366945; best paired96.615785 is a numerical tie with parent. Selected HK0.16266445/PFK0.64493577mM/day, all other constants unchanged. All13 original J4/J8 guards and six original strict/ultrastrict J4/J10/J46 numerical audits pass (117507 comparisons,12882 daily balances). Primary1123/secondary1754/report228 checks;770 source cells/55 J1 and all latents exact; QA1379 passed/two skips,42 focused tests. Early G6P/F6P improve strongly; ATP J46 remains1.77345e-5mM, GLC worsens6.100110 ->6.896167 and EGLC15.596004 ->16.825361mM. No physiological/default promotion or all-time non-regression claim. Sixteen unguarded representations worsen early versus parent. NEXT PROPOSED, NOT RUN: register progressive J1-J15 fitting with actual J11/J15 and explicit glucose/lactate temporal protection before opening more groups; exposed late data are not blind validation. Paired rollback remains intact; RIB/redox/pH/MCT/threshold/OPLAH remain unchanged. No optimization is running.

Parent delivered archive `output/broad_protected_joint_restoration_2026_11_03/`; report `tasks/fla_broad_protected_joint_2026_11_03.md`. Same22-value NLL99.7764 ->96.6158, all13 unchanged guards pass. Six original-path audits,1152 primary+801 secondary checks; QA1363 passed/two skipped. Feasibility restoration, NOT optimum convergence or biological calibration: ATP J46=1.72524e-5 versus nominal0.469757mM. Earlier SLSQP archive remains INTERRUPTED (764 completed logged calls); nine-call restoration is a separate completed successor. Exact55 J1, latents, geometry/pH/threshold/native VELAC/OPLAH/affinities/defaults unchanged. RIB/redox/pH/MCT remain closed.

Strategic objective: develop a RBC-GEM-informed reduced dynamic ODE model, using reconciled metabolomics and uncertain proteomic capacity priors through FLA. Source roles, validation boundaries and deliverables: `tasks/fla_project_objectives_2026_10_06.md`. This is a development target, not a claim that the current ODE is already an exact validated reduction.

- [x] Verify the four proposed reference roles. PMID41846981 is the same March2026 population-atlas preprint as the proposed validation source, not a second independent study; Issaian2025 has a published Blood2026 version. The cited Bordbar2015 fasting-state study does not establish local Sheet1 storage provenance.
- [x] Build and verify the common source/observation/cohort inventory: `output/fla_common_manifest_2026_10_06/`, report `tasks/fla_common_manifest_2026_10_06.md`. Ten sources/eight datasets/seven cohort groups;8097 channel representations,2249 sample records. Verify174 input/nine output hashes and reconstruct tables. QA76 passed/one existing source-file-dependent skip; no fusion, ODE or fitting. F/G and D/E remain paired representations, not independent measurements.
- [x] Audit distinct glucose/lactate reference litres and pinned GEM transport. Report: `tasks/fla_transport_contract_2026_10_06.md`; source archive: `output/fla_transport_contract_2026_10_06_v3/`. Recheck876 JBC source cells, including126 hematocrit values (4C:24, range0.574-0.702), and preserve four local Sheet1 rows. GEM encodes reversible GLC_Dt, lactate/proton L_LACt2 and11 other lactate routes. Published uFBA2017 normalizes both pools per total bag; that convention is not automatically assigned to either local workbook. QA64 passed; no rescaling, donor assignment, ODE or fitting.
- [x] Execute the user-selected distinct-phase branch without uFBA: `config/fla_distinct_volume_transport.json`, `src/rbc_distinct_volume_transport.py`, report `tasks/fla_distinct_volume_transport_2026_10_06.md`, archive `output/distinct_phase_transport_2026_10_06/`. Select cell/supernatant mM coordinates and stable372 sample/36 trajectory keys; prepare all six4C endo/assay pairings (144 records) without asserting donor identity. Run14 fixed J1-J4 strict/ultrastrict cases with Hct0.580/0.574/0.632. All13146 quadrature and240191 convergence comparisons pass; minimum checked concentration0. Full QA1076 passed/two skipped. Exact initialization, source values, historical defaults and readiness remain unchanged.
- [x] Establish and execute the accessible-pool/pHi-pHe/buffer contract before calibration: `config/fla_transport_access_ph_contract.json`, `src/fla_transport_access_ph.py`, report `tasks/fla_transport_access_ph_contract_2026_10_06.md`, sealed archive `output/transport_access_ph_contract_2026_10_06/`. Reconstruct48 original4C-storage pH channel cells without assigning37C/22C readings to4C pHi/pHe. Check576 accessibility-dependent bounds,2880 directional counterfactuals and54 executed-MCT integral buffer ledgers. All7392 source/algebra/archive checks pass; full QA1161 passed/two skipped. Accessibility and pH are confounded in direction through delta_pH-log10(rho); the data do not independently identify either. No new ODE, pH estimate, source rescaling or optimization.
- [x] Complete targeted source-processing audit and preregister the synthetic carrier/buffer recovery design: report `tasks/fla_transport_source_and_benchmark_2026_10_06.md`; sealed archives `output/transport_source_processing_2026_10_06/` and `output/transport_buffer_synthetic_preparation_2026_10_06/`. All126 pH37/pH22 pairs match the manufacturer ABL90 correction within rounding, a strong derived-channel inference but not author-confirmed provenance. Do not count these as independent likelihoods or extrapolate to4C. Execute72 synthetic forward integrations, including strict/ultrastrict conservation checks, four exact unknown-Km/accessibility/pHi symmetry controls and12 conditional sensitivity designs. No recovery fit or biological replay. Full QA1197 passed/two skipped; source values, exact J1, kinetics and readiness unchanged.
- [x] Execute clean staged recovery under the frozen October6 protocol. All72 fits pass numerical/parameter/holdout criteria across two contexts, sparse/dense timing, six stage/observation scopes and three starts. All24 multistart groups agree. Actual objective calls, including Jacobian perturbations, total2613 and never exceed65/100 per fit. Four unknown-Km equivalent-family controls pass. Separate scalar DOP853 audit cross-checks all72 fitted BDF trajectories (maximum absolute state discrepancy3.31e-8). Full QA1214 passed/two skipped. This is conditional clean toy recovery, not simultaneous four-parameter identifiability, noise robustness, an ATP result or biological readiness.
- [x] Execute the preregistered noise challenge (CV0.005/pH SD0.005/seeds2718/31415/1618), six shared panels sealed before fitting. All216 fits pass numerical checks;214 converge, two exhaust100 calls. Parameter accuracy78/216, latent holdout102/216, complete recovery66/216;72/72 multistart groups agree but only22/72 pass complete recovery for all starts. There are9198 actual objective calls,21 bound-hit fits and12 passed equivalent-family controls. Independent scalar audit passes216 trajectories (max difference3.95e-8). Full QA1232 passed/two skipped. Sparse access/pHi is fragile without pHi; dense both-pH passes all six panels in that conditional stage, but denser synthetic assays do not imply experimental interpolation creates information. No biological promotion.
- [x] Compare current cost with matched likelihood on all216 sealed pairs. Parameter recovery78->135; latent prediction102->123; complete recovery66->117, with54 gained/three lost complete pairs. All216 matched optimizers converge; independent scalar audit passes. Targeted larger-budget reruns of the two previous failures converge in115/110 calls under a500-call cap, but remain inaccurate. All12 unknown-Km likelihood controls preserve their ambiguity. Archive `output/transport_likelihood_comparison_2026_10_23/`.
- [x] Execute a first conditional experimental GLUT pilot on original Bordbar EGLC with training-only GLC input, J1-J25 training and J29-J46 historically exposed comparison. Profile total residual dispersion instead of borrowing the synthetic CV. First unsegmented archive fails some numerical checks and is retained; explicit input-knot successor completes all six fits and passes source/prediction/flux verification. Simple candidate at borrowed H0.58: conductance0.0272733183 versus seed0.0879655887, conditional late EGLC RMSE1.1491mM versus11.8116 seed control. Open Km_e improves late RMSE0.8068mM but hits500 and is not identified. Preserve exact55 J1, all56 original source values and production defaults. Full final QA1261 passed/two skipped.
- [x] Execute opt-in GLUT-only whole-network replay using `config/fla_glucose_real_candidate.json`, with native VELAC and clamped diagnostic pH unchanged. All18 fixed-context integrations and352521 convergence comparisons pass; minimum checked concentration0mM. Both reference J4 tolerance profiles reproduce archived accepted time/states bitwise. Preserve113 concentration pools,100 raw/executed reactions and complete quadrature-node evidence. Whole-trajectory EGLC/GLC nominal RMSE improves3.444393/5.361098 ->1.224563/3.431573mM, but J46 EGLC worsens and ATP remains depleted; no biological promotion. Source-only glucose audit finds two intervals requiring negative nominal HK at H0.58 and no common exact constant-H solution, so derived teachers cannot be hard independent labels. Full QA1274 passed/two skipped; verifier1914 checks. No source/initial-state change or optimizer.
- [x] Complete joint free-network seven-pool calibration: six factors, three starts, J4 then J10 parameter continuation from exact J1. All six fits converge;1124 actual objective/Jacobian integrations, none invalid. Selected training NLL40.823325->14.541840 on seven J4 observations and91.356916->35.611361 on14 J4/J8 observations versus GLUT-only. Source770 cells/55 J1 preserved. All117507 convergence,12882 executed daily-balance and11400 each native/executed quadrature comparisons pass; checked minima0mM. Verifier2556 checks; final QA1298 passed/two skipped. J4-trained ATP0.280234 is not the final J10-fit prediction: final ATPJ4/J8/J46=0.152875/0.112545/0.000021290mM. Four capacities hit lower bounds, residual CV1.22327 includes model error, and PEP RMSE0.019981->3.187252mM. No biological promotion. Additional ATP production5.871436->10.854335 is compensated by consumption6.804411->11.787306mM. Full evidence/report `tasks/fla_joint_glucose_energy_2026_10_27.md`.
- [x] Complete protected same-coordinate J1-J10 successor for EGLC/GLC/LAC/ELAC/ATP/ADP/AMP/PEP/G6P. Actual J4/J8 RMSE caps are frozen from GLUT-only, with numerical allowance1e-5mM+1e-4*reference_RMSE and25% fitting/75% replay reservation. Three starts converge in208/261/402 calls. Nine guards pass in fitting and original J10/J46 replays; no control fallback. Selected point is from the control START, not the unchanged comparator. All117507 convergence comparisons,12882 daily balances and11400 each raw/executed quadrature checks pass; checked minima0mM. Verify770 source values/55 J1,4705 primary and846 secondary checks. Final QA1322 passed/two skipped. G6P early RMSE1.402464 ->0.207126, PEP0.027823825 ->0.027827014 within numerical allowance, ATP1.179142 ->1.076975mM. No source/latent/box/default change or promotion.
- [x] Explain F6P/B23PG early regressions and PEP's active constraint from four saved J1-J10 strict/ultrastrict executed-flux archives. F6P J1-J4 consumption by PFK1.067734 ->0.116466mM explains+0.951269mM contribution, partly offset by falling PGI/PPP inputs. B23PG J4-J8 DPGM0.574717 ->0.065738 while phosphatase1.968504 ->1.985787; raw DPGM change-1.119700 plus modifier+0.610721 gives executed-0.508979mM. PGK loss attribution shifts91.27% ADP in control ->100% B13PG in candidate. PEP J8 absolute error0.002325 ->0.037856 despite maintained two-point RMSE. Exact four balances close; no network coefficient correction indicated here, no new simulation or optimization. Archive/report/QA are in the active handoff above; failed partial predecessors retained.
- [x] Implement/test the proposed eleven-pool RMSE contract plus pointwise PEP J4/J8 in `src/fla_broad_protected_calibration.py`:24 focused tests and full QA1361 passed/two skipped. All13 references exactly match the sealed proposal;54 inputs are frozen. Existing nine-pool candidate fails both added RMSEs and PEP J8, control remains feasible. Same engineering allowance/25% fitting margin, exact55 J1, latents, six-coordinate bounds, geometry, pH, threshold, native VELAC and OPLAH. B13PG/P2G aliases excluded;22 source likelihood values are not independent assays,44 representations remain audit-only.
- [x] Execute the user-authorized broader search and numerical follow-up. Initial SLSQP:two unsuccessful fits65/144 calls, control-start interrupted after555 logged calls without feasible improvement; immutable manifest explicitly says interrupted/nonconverged, not completed calibration. Three local LP-proposed actual evaluations also fail. Separate minimum-L1 inward restoration with h1e-4/trust0.005/reserve5% finds all13 guards passed in nine objective calls, NLL99.776418 ->96.615834. All six original-RHS J4/J10/J46 strict/ultrastrict audits pass117507 comparisons,12882 daily balances and11400 each quadrature checks; minimum checked0mM. Verify1152 primary+801 secondary checks and preserve exact source/J1/latents/box/defaults. No biological promotion or global-infeasibility/optimality claim.
- [ ] NEXT PROPOSED, not launched: preregister a reversible separation of the current VHK/VPFK capacity pairing, preserving existing primitive bounds and all13 training constraints. The guarded restored candidate uses investment0.39580749 but leaves ATP badly depleted, whereas aggressive paired reductions previously worsened F6P. This motivates testing the pairing, not a proven causal rescue or an already authorized extra coordinate. Keep current candidate/control archives and exact55 J1, redox/RIB/pH/MCT/threshold/OPLAH unchanged; assess all44 remaining source representations and executed energy balances. Do not simply increase budget, weaken guards, delete OPLAH or promote a lower-cost infeasible vector.
- [ ] Deferred mechanism test, not yet run: reversible RIB(0) latent-initialization feasibility remains behind the proposed VHK/VPFK coupling test. RIB stays unmeasured and fixed at1mM, sole balance dRIB=-VRKa; restored-candidate J1-J46 RKa ATP cost0.999176mM. Preserve55 measured J1; any range is diagnostic, not measured. Restored ATP production5.775129/consumption6.708104mM remains compensatory; no direct ATP rescue from changing RIB is promised. Earlier nine-pool budgets remain historical evidence, not this candidate's current values. Keep other latents, adenylates, PEP, F6P, B23PG and OPLAH monitored and unchanged unless separately authorized.
- [ ] In parallel, support observation-to-accessible-pool scales and temperature-compatible pHi/pHe/buffer/gas/AE1 contracts. Fourteen local prerequisites remain unresolved and do not replace existing biological readiness. Request original concentration-processing equations, sample/donor linkage and ABL90 channel derivation; pHe alone cannot break the demonstrated toy symmetry when intracellular Km is also unknown. Do not fit MCT capacity or pH to force ELAC export. Earlier fixed-kinetic geometry/native/reversible diagnostics gave ATP J4 near0.0007mM versus nominal1.079765; the new joint kinetic candidate does not resolve those acid/base contracts. After acid/base validation, return to restricted identifiable redox/energy diagnostics.
- [ ] Resolve source-specific observation contracts for local Sheet1 and JBC, prioritizing EGLC/ELAC, ATP-ADP-AMP, P2G+P3G and the exact B13PG/B23PG duplicate. Confirm concentration denominator, pool form, time origin and donor pairing without guessed conversions. Obtain atlas methods/data and donor linkage before reserving untouched validation subjects/conditions; Bardyn/Michel remain exposed exploratory transfer panels. Then rebuild augmented balance/identifiability and active-capacity contracts; no readiness override.

Review: `tasks/fla_model_review_2026_09_08.md`. Evidence: `output/fla_review_2026_09_08/evidence.json`.

Historical completed execution (superseded for current handoff): reversible C4/folate/redox closure in `src/rbc_biochemical_extensions.py` and `output/biochemical_closure_2026_10_06/`. Report: `tasks/fla_biochemical_closure_2026_10_06.md`. OPLAH retained by default. The historical kernel/catalogue, Bordbar J1, threshold and readiness remain unchanged. Structural corrections do not restore ATP; new biological redox kinetics remain inactive.

- [x] Implement explicit AKB, distinct MTHF/MLTHF and finite redox acceptor/regeneration states. Verify CSE composite chemistry from pinned GEM and UniProt/Rhea; correct one-heme-site electron accounting rather than copying the GEM metHb coefficient uncritically.
- [x] Require explicit latent-pool initialization and every new kinetic input; forbid implicit folate conversion, partial redox chains, forcing and legacy clipping. Pass 30 new tests including 372 zero-boundary probes; full QA: 982 passed, two skipped.
- [x] Complete ten fixed-context Bordbar J1-J4 strict/ultrastrict replays and four separately labeled synthetic redox replays. All 11480 budget/quadrature and 2142136 convergence comparisons pass; minimum checked concentration zero. Independent verification passes 2377 checks. Combined methyl-only ATP J4 remains 0.000754701 mM versus nominal1.079765. No biological redox activation, MTHFR fitting or OPLAH deletion.
- [ ] Rebuild the augmented FLA observation/balance and identifiability contract before reusing any teacher or extending calibration. Support available heme/CYB5/TXN/PRDX/redox initial pools and kinetics, downstream AKB fate, and explicit proton/oxygen/repair/shared-capacity mechanisms; audit limiter sensitivity in the new small-pool context before physiological activation.

- [x] Audit ODE, FLA/data, and validation/platform locally after the three requested agents failed on usage quota.
- [x] Fix structural parsing of V6PGD and V23DPGP; all 113 concentration balances close on eight positive test states (maximum 7.11e-15 mM/day).
- [x] Require raw balance closure, pre-clipping minima, continuous unforced replay and predeclared absolute target limits in validation policy revision 3.
- [x] Reject truncated/nonfinite CSV evidence and nonfinite integrated teachers.
- [x] Correct reset diagnostics: continuity is reported, not optimized; ATP elapsed-time fraction is 2.37% free versus 26.53% reset, not a sensitivity result.
- [x] Re-audit cached adenylate balance: numerical/raw discrepancy integrates to about +0.01099 mM, not an experimental flux.
- [x] Correct ATP/ADP counterfactual and reversible-net-group interpretations; update manuscript methods and inventory.
- [x] Regenerate PPP/Rapoport-Luebering teachers, ranks, nullspaces and parameter reachability under schema 2. Four measured balances have rank 4; none independently identifies an individual reaction flux. Seven latent PPP pools remain unobserved.
- [x] Audit identical frozen kinetics/initialization on unforced standard/strict BDF J1-J46 replays. Strict quadrature passes all 565 pool/quantity checks, but raw closure and non-negativity fail; no optimization or promotion.
- [x] Implement opt-in `positivity_policy="reaction_consistent"` with the legacy default unchanged. One signed-consumer availability factor scales each complete net reaction; no independent concentration derivative clipping/sanitization is permitted. Explicit native/effective flux evidence remains available.
- [x] Pass 22 new regression tests (including exact snapshot round-trip) and 339 zero-boundary probes on the frozen initial and archived depleted B13PG/ADP contexts. Verify saved legacy RHS parity before launching fixed-parameter replays.
- [x] Complete 12 fixed-context replays: J1-J3/J1-J10/J1-J46, legacy/reaction-consistent, standard/strict BDF. Exact round-trip initialization reproduces the entire archived legacy strict J46 accepted time/state arrays bit-for-bit. Runner: `scripts/test_reaction_positivity_fixed_context.py`; final evidence: `output/reaction_positivity_fixed_2026_10_05_roundtrip/`. Preliminary CSV-default-precision outputs and their executed runner remain preserved, but are superseded for the decision.
- [x] Repeat declared quadrature and standard/strict comparisons. Reaction-consistent strict runs pass all 452 pool/quantity quadrature checks per horizon, have no negative accepted concentrations, and have exact executed reaction balance closure. Standard runs fail 8 J10 and 16 J46 quadrature checks. At J46, five effective-balance and two reaction-rate-change integral comparisons fail standard/strict tolerance, although all 116 pool/group state-change comparisons pass.
- [x] Adopt reaction-consistent + strict BDF as the provisional working reference in `config/fla_working_reference.json`, loaded via `src/fla_working_reference.py`. All new work in the active campaign uses this explicit profile. Legacy is retained for historical replay; the kernel and older API/runner defaults are not silently migrated. This is numerical adoption, not promotion of the archived kinetic context.
- [x] Pass 23 new profile/threshold/comparison regression tests and all 567 QA tests. Verify 1017 zero-boundary probes across the three predeclared thresholds, archived legacy RHS compatibility, and bit-identical accepted time/state arrays for the new strict working replay versus the preceding reaction-consistent replay.
- [x] Complete six fixed-kinetic J1-J46 replays at thresholds 1e-4, 1e-3, 1e-2 mM, each strict/ultrastrict. All 978 convergence comparisons pass at every threshold; each replay passes 452 pool/quantity plus 300 individual reaction/quantity quadrature checks. No accepted or sampled dense concentration is negative. Runner: `scripts/verify_fla_working_reference.py`; evidence: `output/fla_working_reference_verification_2026_10_05/`.
- [x] Review threshold sensitivity separately from solver convergence. Ultrastrict ATP endpoints are 1.58795e-6 / 1.64866e-5 / 1.40143e-4 mM; executed VPGK integrals are 0.645152 / 0.670233 / 0.939334 mM. The threshold strongly changes depleted-pool kinetics and is not a validated physiological mechanism. No selection by predictive loss or optimization; keep 1e-3 mM provisionally. All input/context hashes remain unchanged.
- [x] Complete executed B13PG/ATP/ADP/B23PG attribution with strict and ultrastrict J1-J46 replays reproducing verified solver arrays bit-for-bit. All 215 quadrature and 215 cross-tolerance attribution checks pass. Runner: `scripts/audit_b13pg_atp_executed_fluxes.py`; evidence: `output/b13pg_atp_executed_audit_2026_10_05/`. Actual-sign reaction contributions include reversible AK/NDPK; native rates remain same-trajectory counterfactuals. All 587 QA tests pass.
- [x] Localize changing numerical limiter action: B13PG accounts for all PGK reduction at J1-J3; ADP accounts for 95.68% at J3-J10 and all at J10-J46. PGK receives 88.52% of early B13PG drainage but 0.334% late. VHK/VPFK account for 75.45% of early ATP consumption; VAK accounts for 73.54% of ADP consumption. These accounting shares are not experimental control coefficients or causal interventions.
- [x] Identify the unobserved redox initialization issue: NAD/NADH start at 1 mM each without corresponding workbook rows; the native GAPDH redox factor falls 0.320279 -> 0.018580 over J1-J3. Six of 13 measured ATP intervals require negative conditional PGK with all other simulated terms fixed; a PGK-only fixed-neighbor hypothesis is insufficient, not proof of whole-model infeasibility. No kinetic lever or threshold is fitted.
- [x] Implement the J1-J4 adenylate/redox contract and pass 18 targeted tests. Separate total adenylates, partition/energy charge, exact AMP/purine terms, and the conserved latent redox totals. Historical redox inputs are diagnostic anchors, not verified biological priors.
- [x] Complete four predeclared NAD/NADH initialization diagnostics, each strict/ultrastrict at fixed kinetics and threshold. All eight cases pass 223 quadrature checks each; all 1344 convergence checks pass, with no negative checked states. Independent explicit equations reconcile 224 window budgets. Evidence: `output/adenylate_redox_feasibility_2026_10_05/`; runner: `scripts/build_adenylate_redox_feasibility.py`; all 605 QA tests pass. No automatic VAK/PGK/DPGM promotion or artificial ATP source.
- [x] Separate total-pool and partition mismatch: baseline J4 total 2.627505 vs 2.692228 nominal mM, but ATP/ADP nearly vanish and AMP accumulates. Fixed-neighbor conditional VAK requirements disagree (3.029876 /1.414010 /-0.137132 mM). The four source-traceable redox IC scenarios do not restore J4 endpoints; this does not establish full redox-domain or coupled-network infeasibility.
- [x] Prepare a separate evidence-backed readiness configuration/guard without changing archived hashed sources. Recheck evidence and endpoint limits on every assessment; require matching redox volume and free-available/total-extractable pool definitions, documented covariance estimand/effectives, valid correlations at all scales, and supported baseline initialization. Native `--require-ready` returns 2 while evidence is missing. All 657 QA tests pass, including 52 new tests; JUnit is stored in the v2 preparation directory.
- [x] Audit local source cells and workbook metadata with one read-only agent and independent workbook receipt. The `cellbb.txt` import connection is a concrete but unverified lead. Bordbar/SAGM and Qi/ADSOL cohorts are distinct; no uncertainty or normalization is borrowed. Evidence requirements: `tasks/fla_data_evidence_requirements.md`.
- [x] Prepare, but do not execute, 19 coupled energy configurations /38 strict-ultrastrict replays: HK/PFK downward-only at HK<=5.0, AK forward/reverse capacities together, GAPDH/PGK together. Include one-sided/central response and paired interactions, full executed budgets, frozen ICs/threshold, no optimizer or best-case selection.
- [x] Prepare an isolated synthetic FLA recovery benchmark with known transport capacities, production PCHIP teachers/executed kernel rates, pointwise versus interval supervision, dense/sparse/controlled-noise observations, three starts and a temporal holdout. The biological readiness gate and 38 coupled energy replays remain unchanged. Pass 29 targeted tests; manuscript method 2.26 records the scope and limits.
- [x] Complete the synthetic campaign: 13 conditional fits /28 continuous J1-J46 strict-ultrastrict replays, all numerical checks pass. Oracle recovers exact capacities; dense-clean methods pass declared synthetic checks. Dense-noisy pointwise glucose capacity error is 65.48% versus 3.621% integrated; sparse-noisy improvements are not uniform. Pass 92 independent archive checks and all 686 QA tests. Preserve absolute/mean-relative as well as excursion metrics for all 113 pools. Evidence: `output/fla_synthetic_recovery_2026_10_05_v2/`; preliminary additive-noise attempt remains superseded and intact.
- [x] Preregister the separate dense teacher-resolution/smoothing diagnostic: 90 conditional fits over clean plus five paired synthetic noise seeds; four uniform grids, observation-aligned Gauss cells, raw interval increments and a labeled legacy objective. Repair two machine-precision duplicate clean timestamps before noise (689 -> 687); preserve the interrupted preflight and all parent artifacts.
- [x] Complete the 32 preselected strict/ultrastrict J1-J46 ODE replays: all numerical gates pass, with minimum checked concentration +8.15775e-7 mM. Pass 458 independent checks and all 714 QA tests; export 3680 pool/flux/period metrics and inspected PNG/PDF comparisons. Evidence: `output/fla_teacher_resolution_2026_10_05_v2/`. No experimental objective or biological lever changed.
- [x] Distinguish teacher quadrature, timestamp conditioning and smoothing bias. Five-seed median glucose capacity error is 38.72% for legacy 401, 0.2386% raw aligned, 0.5604% smoothed aligned and 2.684% intervals. Three-seed median EGLC holdout excursion error is 56.38% /0.1958% /0.5128% /3.698%. Original parent clean errors are independently reproduced; the 687-time control shows a separate timestamp-conditioning effect. These remain conditional synthetic results, not biological recovery.
- [x] Preregister and complete the 90 sparse conditional fits at J1/J4/J8/J11/J15/J18/J22, with five paired 0.5%-CV seeds and the same frozen truth/methods/starts as the dense study. Pass 21 targeted tests; no timestamp aggregation is needed, and the three shared sparse parent noise draws reproduce exactly. Runner: `scripts/run_fla_sparse_teacher_resolution.py`; design: `config/fla_sparse_teacher_resolution.json`.
- [x] Complete the 32 predeclared sparse strict/ultrastrict J1-J46 replays: all numerical gates pass, minimum checked concentration +8.230065e-7 mM. Pass 477 independent checks and all 735 QA tests; inspect three PNG/PDF figure pairs and retain all 3680 metrics in `output/fla_sparse_teacher_resolution_2026_10_05/`. Dense/sparse noise draws are not matched, and no biological or default-policy change is made.
- [x] Distinguish sparse parameter recovery from free prediction. Median glucose capacity errors over five seeds are 1.3815% historical /1.3345% raw aligned /1.0992% smoothed aligned /0.9725% raw intervals; median EGLC holdout errors over three preselected seeds are 1.111% /1.097% /0.7814% /1.303%. A 401-point teacher is already resolved here. The seven-time proxy misses early synthetic GLC/LAC transients; no general teacher or objective superiority follows.
- [x] Preregister fixed-capacity free-ODE validation of raw versus smoothed-input intervals: clean plus all five sparse seeds, raw increments unchanged, no new fits. Twelve capacity pairs represent 16 new integrations and eight reused verified integrations. Config/runner: `config/fla_smoothed_interval_replay.json`, `scripts/run_fla_smoothed_interval_replay.py`; method 2.29 records the scope.
- [x] Complete all 16 new strict/ultrastrict J1-J46 integrations, retaining eight copied verified integrations: twelve capacity pairs, no refits or forcing. All numerical gates pass; minimum checked concentration +8.231786e-7 mM and executed transport closure zero. Independent verification passes 815 checks; all 765 QA tests pass (30 targeted new tests). Evidence: `output/fla_smoothed_interval_replay_2026_10_05/`; completed after interruption on 2026-10-06.
- [x] Verify all 2760 pool/flux/period metrics, 1380 paired rows, 230 five-seed summaries and 168 endpoint-derived executed transport integrals. Median noisy EGLC error improves 1.3034% -> 0.9634% (4/5 seeds); ELAC 0.08034% -> 0.07683% (3/5), but worst ELAC worsens 0.13416% -> 0.15870%. Clean EGLC worsens 0.10752% -> 0.33133%. Preserve the initial roundoff-only dense-anchor verification failure; raw accepted ICs remain bit-identical and no solver tolerance changes.
- [x] Keep raw intervals as the comparator and smoothed inputs as an optional synthetic hypothesis, not a default or promoted biological method. Whole-pool worst noisy mean-normalized error falls 6.9034% -> 5.7469% (GTP); this is not an experimental tolerance. Inspect both PNG figure pairs; update manuscript methods 2.29/results 3.31/discussion and the progress log. No new biological optimization is authorized by this result.
- [x] Complete the user-approved read-only Bordbar source/units/time audit: 770 finite nonnegative concentration cells, five identical Git snapshots, exact current calibration/extracellular-loader parity and preserved source/configuration hashes. Evidence: `output/bordbar_source_units_time_audit_2026_10_06/`; runner/verifier: `scripts/audit_bordbar_source_units_time.py`, `scripts/verify_bordbar_source_units_time_audit.py`.
- [x] Localize `cellbb` to Feuil1's 44 five-coefficient curves, not Sheet1's raw concentration lineage. Qualify 42/46 wording using the primary 45-day reanalysis: J1-J46 is 45 elapsed days; +1 origin remains unverified, J38 unchanged. Document total-bag-volume normalization as a primary-source lead, not an applied conversion. Preserve HTML-only supplement responses, all observations and all four sealed synthetic archives.
- [x] Pass 25 new targeted tests, all 790 QA tests and 227 independent audit checks. Update manuscript methods 2.30/results 3.32 and evidence requirements. The thirteen readiness checks remain unmet and the 38 coupled energy replays remain unauthorized.
- [x] Following explicit user authorization, preregister a **separate conditional exploratory** J1-J4 energy sensitivity branch. It does not execute or authorize the blocked historical biological protocol. Config/runner: `config/fla_exploratory_energy_sensitivity.json`; `scripts/run_exploratory_energy_sensitivity.py`.
- [x] Enforce all 55 exact Sheet1 J1 values, including zeros, while preserving every unmeasured frozen pool. Explicitly restore archived QSS B13PG 0.000176677669 -> nominal source 3.584045211 mM and ECYS/EINO 1e-6 -> 0; duplicates remain non-independent. Keep NAD=NADH=1 mM, other kinetics/network and strict/ultrastrict reaction_consistent profile fixed. No historical XLS initialization or platform-default migration.
- [x] Pass 33 new targeted tests and all 823 QA tests. Prepared deterministic diagnostic stencil: eleven baseline/single-group cases plus eight paired cases, 38 integrations. No optimizer, fitted ICs, artificial ATP, observation forcing/reset or candidate promotion.
- [x] Complete all 38 conditional exploratory replays. All 8474 quadrature and 6384 cross-tolerance checks pass; minimum checked concentration zero, with no negative stored values. Independently verify 6445 checks after visual refinement and all response features; all 823 QA tests pass. Export/inspect two PNG/PDF figure pairs; preserve initial versions before the legend-only refinement. Evidence: `output/exploratory_energy_sensitivity_J1_J4_2026_10_06/`; historical 13-check biological readiness guard remains unchanged.
- [x] Interpret conditional responses without ranking/promoting parameters: HK/PFK downward and AK downward slightly raise J4 ATP; GAPDH/PGK upward raises ATP and lowers AMP but slightly lowers ADP. All 19 strict probe endpoints remain ATP 0.000685896-0.000837634, ADP 0.0000684698-0.0000990709 and AMP 2.592957-2.594368 nominal mM. The local neighborhood does not restore the nominal J4 partition; this is not proof of whole-network infeasibility. No J10/J46 extension or optimizer launched.
- [x] Complete the user-approved pool-definition audit, published-source inventory and reversible latent-inference preparation. Reconstruct all 770 local cells and extract 101 Nishino model-reference entries with exact page/label provenance; distinguish ATP free/total and model priors from measured anchors. Evidence: `output/fla_latent_inference_preparation_2026_10_06/`; protocol: `tasks/fla_latent_inference_protocol.md`.
- [x] Keep all 55 exact nominal J1 entries, all latent ICs, kinetics, threshold and historical archives unchanged. Audit one phenomenological ATP state, absent Pi/Mg states, duplicate signals and the 53-channel matrix rank 50/nullity 50; this is not dynamic latent identifiability. Public JBC supplement returned HTML status 203, not Excel; no observations fabricated/imported.
- [x] Implement isolated absolute-anchor/relative/paired-observation and redox-parameterization primitives; reject unverified normalization, wrong ratio kinds, nonpositive log signals and measured-state overwrites. All 863 QA tests pass, including 40 new tests. Helpers are not wired into calibration/API; no simulation, latent estimation or biological optimization executed.
- [x] Recover and import the supplied original JBC workbook and 23-page supplement into a separate sealed archive: `output/jbc_supplements_ingestion_2026_10_06/`. Verify all 11,886 numeric source cells and their keys, 96 channels (47 endo/23 exo/26 assay), four temperatures and three positional replicate blocks. No rescaling, teachers, ODE or fitting; all 900 QA tests pass, including 37 new targeted tests.
- [x] Preserve JBC-specific exact sampling schedules and the documented day-zero origin, the extra assay-only day14 at37C, duplicate hemoglobin headers and 182 extracellular zeros. Record ATP endo/exo caption conflict, free/total ambiguity, hexose-6-phosphate identity, pooled phosphoglycerate and predicted/not-measured 2,3-DPG. No direct NAD(H)/NADP(H) measurements.
- [x] Review recent Palsson coauthored RBC publications and preserve the six supplied Deep Red files without executing their HTML/JavaScript. Inventory 21 sheets, 3799 human protein rows, 940 phosphopeptide/site rows, 4061 cysteine rows and 558 interactome nodes. Download and checksum-verify RBC-GEM S6; inspect its 11 sheets. All 24 targeted source-review tests pass; no model or calibration change.
- [x] Extract source-preserving priority enzyme rows from RBC-GEM S6 TablesD/E with TableF metadata: 62 proteins, 616 donors, 1848 D10/D23/D42 samples and 114576 values per representation. Preserve zeros, estimated-abundance assumptions and source cells. Join by sample ID: 163 D/E column positions differ. No training import or capacity conversion.
- [x] Independently reopen S6 and verify all 229152 D/E values, their exact source/sample/time/unit keys and 17864 TableF metadata cells. Preserve extraction manifests and seal executed code/documents with the complete network/replay archive.
- [x] Retrieve pinned RBC-GEM 1.2.0/1.3.0 sources and S1/S2/S5/S7. Compare all 100 executed reactions: 82 projected equivalents, 13 unmatched, five unresolved identities and 47 closed unmatched candidates. Preserve all compartments and unknown species.
- [x] Synchronize Rxn_RBC.txt with all 100 historical ODE columns/113 pools, including 11 missing equations, corrected SAM/VEGLC and explicit CYT chemostat semantics. Fix coefficient/source/sink parsing in src/parse.py; do not confuse historical parity with biochemical conservation.
- [x] Add an opt-in RBC-GEM diagnostic adapter: CAT/XAO coefficients, coupled ATP-dependent GSSG/urate export, reversible OPLAH-off hypothesis and five explicit but inactive branches. Keep the historical kernel, working reference, threshold, kinetics and exact Bordbar J1 unchanged.
- [x] Complete eight fixed-context free J1-J4 strict/ultrastrict replays; all numerical gates pass, historical arrays reproduce exactly. Core ATP J4 is 0.000766419 versus nominal 1.079765 mM: structural corrections do not restore ATP. All 952 QA tests pass, two source-dependent tests skip; independent verification passes 207 checks.
- [ ] Establish physiological initial pools and downstream fate for the corrected AKB/distinct folate variant, and close CYT/methylation before biological promotion. Reconcile RBC-GEM OPLAH exclusion with its detection in Deep Red2026; activity at storage temperature is not established by either annotation alone.
- [ ] Audit shared AK1/HPRT1/GSR capacities and explicit redox acceptor cycles before activating candidate branches. Complete cohort-overlap and source/complex/active-fraction reconciliation before deriving uncertain capacity priors or running biological calibration.
- [ ] Reconcile the two Deep Red copy-number calibrations and the 3775 article versus 3799 supplied rows; verify isoforms, complexes, active fraction, temperature and volume before proposing soft Vmax priors. Protein abundance alone does not identify Km or latent redox concentrations.
- [ ] Confirm JBC observation-pool identities and volume equations (especially ATP and hexose-6-phosphate), donor IDs/cross-sheet pairing and cohort independence before external prediction or uncertainty-weighted flux reconstruction. JBC access is resolved, not Sheet1 lineage or normalization.
- [ ] Obtain applicable redox pool definitions/volume bases, prior support and observation covariance, plus paired longitudinal antioxidant-control signals before using new biological observations.
- [ ] Separately authorize a synthetic dynamic identifiability/recovery benchmark for four initial redox coordinates at fixed kinetics and actual sampling times; do not replace this test with matrix rank or run a biological fit yet.
- [ ] Recover the actual original concentration export feeding Sheet1, source row/assay IDs, donor/replicate measurements, exact sampling vector and normalization script. Request cellbb.txt separately for coefficient lineage; it cannot alone close the concentration-source gap.
- [ ] Resolve source normalization, time origin, observation uncertainty, absolute accuracy requirements and supported redox prior bounds before a coupled investment-adenylate-GAPDH/PGK dynamic sensitivity screen.
- [ ] Freeze absolute accuracy limits and measured-data/time-origin contracts; they are intentionally unset and block promotion.
- [ ] Only after this: dynamic sensitivity screen, continuity-constrained training, continuous J1-J46 and external validation.

Latest readiness decision: the numerical simulation diagnostic passes, but biological readiness remains blocked in six scientific domains (13 explicit guard checks). Baseline initialization and the working profile are unchanged; no historical redox prior or fitted kinetic hypothesis is promoted. The coupled J1-J4 protocol is prepared, not executed. The source audit is complete and distinguishes coefficient import from concentration lineage. Next obtain the original Sheet1 concentration export/normalization/time/replicate evidence from its source owner, and justify endpoint tolerances and redox bounds with the correct pool definition. No numerical values are fabricated to enable optimization. Latest source evidence: `output/bordbar_source_units_time_audit_2026_10_06/decision_report.md`. Current preparation: `output/adenylate_redox_readiness_2026_10_05_v2/decision_report.md`; earlier readiness iterations remain preserved. Simulation evidence remains `output/adenylate_redox_feasibility_2026_10_05/decision_report.md`.

Conditional exploratory follow-up: user-approved steps 1-3 are now complete in `output/exploratory_energy_sensitivity_J1_J4_2026_10_06/decision_report.md`. This branch restores the exact nominal J1 table and preserves unmeasured ICs; it does not replace the earlier initialization snapshots or authorize the original biological protocol. Local group/paired responses are numerically resolved for the ATP/ADP/AMP endpoints but far too small to restore them. Broader feasibility probes, J10/J46 transfer and fitting remain subsequent separately scoped decisions; no automatic extension, source normalization or model promotion.

Latent-inference follow-up: the three requested preparation tasks are complete in `output/fla_latent_inference_preparation_2026_10_06/decision_report.md`. This is a source/observation contract, not an ATP correction. First block is NAD/NADH and NADP/NADPH totals/fractions at fixed kinetics; bounds, covariance and accuracy requirements remain unset. Initial-state inference and synthetic ODE recovery have not run. Measured J1, old readiness blockers and production defaults remain unchanged.

JBC follow-up: the user-supplied numerical supplement is now available in `output/jbc_supplements_ingestion_2026_10_06/decision_report.md`; earlier HTML retrieval failure remains historical evidence, not the current access status. The source-preserving import is deliberately separate from Bordbar training and the sealed latent-inference protocol. Candidate measurements can support future source-specific adenylate/glycolysis/PPP tests, but do not directly determine missing redox initial states or justify cross-cohort absolute anchoring. Next resolve source observation contracts and plan a separate4C test; no calibration is enabled automatically.

Proteomics follow-up: `tasks/fla_proteomics_source_review_2026_10_06.md` records the targeted recent-source search, local file audit and staged capacity-prior strategy. Evidence: `output/palsson_proteomics_review_2026_10_06/`, including the original 82.6 MB RBC-GEM S6 workbook and the corrected bibliography query in `evidence_extension_v2/`. The G6PD study remains explicitly a preprint. S6 sample values are not yet imported into training; interactions/PTM signals are not measured catalytic activity. Missing original JBC Downloads files were checked against byte-identical archived copies; no historical manifest was rewritten. Biological readiness remains blocked and exact Bordbar J1 is unchanged.

RBC-GEM follow-up: `tasks/fla_rbc_gem_network_audit_2026_10_06.md` supersedes the earlier S6 extraction next step, not the biological readiness decision. Source-only observations are now extracted in `output/rbc_gem_network_audit_2026_10_06/priority_proteomics_v2/`; D/E are two representations of the same estimate, not independent observations. The corrected catalogue is a historical projection; the new `src/rbc_gem_network.py` adapter is opt-in and no core hypothesis is promoted. Fixed-parameter diagnostics remain in `fixed_parameter_diagnostic/`. Next close the documented biochemical identities/OPLAH conflict and audit shared enzyme/redox mechanisms; no optimizer is launched.

No new kinetic candidate is promoted. VAMPD1 decay and VADSS-specific GTP affinity remain rejected global hypotheses. The current purine anchor is diagnostic, not the platform default. Old cached validation decisions do not satisfy the new contract automatically.

Current numerical-reference evidence: `output/fla_working_reference_verification_2026_10_05/decision_report.md`, `summary.json`, `threshold_sensitivity.csv` and `qa_results.xml`. Reaction-consistent + strict BDF is the explicit provisional working reference; legacy remains available for historical replay. Numerical convergence is established for this frozen context and declared comparison tolerances, not biological calibration or threshold invariance. The historical audits below remain preserved as earlier evidence.

Current executed-flux attribution: `output/b13pg_atp_executed_audit_2026_10_05/decision_report.md`, raw arrays, signed reaction/window budgets, consumer-limiter allocation, measured interval requirements and inspected PNG/PDF exports. Independent explicit-equation checks reconcile 272 terms and 64 allocated-loss sums against the preceding archive within 7.11e-15 mM. ATP falls 0.932992 -> 0.00132197 mM over J1-J3; production/consumption integrate to 3.354344/4.286015 mM. Numerical closure is not predictive calibration. No model network, kinetic constant, initial condition or availability threshold changed.

Latest evidence: `output/ppp_numerical_audit_2026_10_05/decision_report.md`, `summary.json` and `preregistered_contract.json`; runner `scripts/audit_ppp_constraints_and_numerics.py`. The frozen replay context is the archived, unpromoted VAMPD1 storage-decay branch, not a new best model. Strict integrated damping adds +0.0114236 mM to ATP+ADP+AMP (+0.00887729 ADP, +0.00254635 ATP), +0.00397148 GO6P and +0.019655 B13PG. Derivative clipping is inactive. Strict raw accepted minima include B13PG -1.07350e-5 mM and ADP -1.15022e-6 mM; floors do not ensure positivity. These numerical terms must not enter experimental flux supervision. The remaining free ATP error is much larger than its numerical correction. Verification: 522 QA tests passed; six existing Optuna warnings and the existing Python 3.14/Pydantic startup warning.

Positivity follow-up: `output/reaction_positivity_fixed_2026_10_05_roundtrip/decision_report.md` supersedes the numerical-policy next step above. At J46 strict, the reaction-consistent minimum is +8.1473e-7 mM, closure 3.56e-15 mM/day, and nonreaction adenylate source approximately zero rather than +0.0114236 mM. ATP remains 1.64866e-5 mM versus 0.469757 mM. GLC/ELAC postinitial nRMSE worsen (6.5893 -> 7.0489 and 0.36958 -> 0.39719), despite G6P/B23PG improvements. No policy or kinetic candidate is globally promoted. `legacy` remains the default; opt in via the ODE keyword, not by adding a numeric kinetic parameter. Verification: 544 QA tests passed, six existing Optuna warnings and the existing Pydantic startup warning.

## Current State

The active methodology is Flux Learning Analysis (FLA): infer teacher fluxes from experimental concentration curves, calibrate kinetic constants against concentration and flux objectives, then reinject learned constants into the ODE for pure simulation.

Brodbar remains the primary training dataset. Michel and Bardyn are validation/transfer datasets.

The executable network is `airbc-rbc-2026.09.04`; the structural parser schema is revision 2 (2026-09-08). New campaigns should use the corrected SAM stoichiometry and explicit extracellular glutathione degradation fluxes, while persisting the network version, parser revision/hash, initialization policy, transport family, and latent-state artifact provenance.

## Model And FLA Audit (2026-08-11)

- [x] Inventory the executable ODE, parsed stoichiometry, measured targets, latent states, and FLA artifacts.
- [x] Correct SAM synthesis so `MET + ATP -> ADOMET + Pi + PPi` does not also create AMP; retain an explicit legacy replay option.
- [x] Expose extracellular GSH/GSSG degradation as named reactions visible to FLA and structural reachability.
- [x] Add reversible initialization policies: legacy aliases, compartment-strict generic, and compartment-strict historical.
- [x] Run three fixed-parameter 46-day replays separating the network correction from the initialization effect.
- [x] Quarantine B13PG and P2G from independent aggregate weighting because B13PG/B23PG and P2G/P3G are exact duplicated row pairs.
- [x] Update the FLA manuscript methodology, limitations, and whole-model audit results.

Audit decision: do not broaden the kinetic optimization. The corrected network is the default for new runs, but strict historical initialization is diagnostic only and no kinetic or initial-state candidate was promoted.

Primary audit artifacts:

- `output/model_fla_state_audit_2026_08_11/model_fla_state_report.md`
- `output/model_fla_state_audit_2026_08_11/model_fla_state_summary.json`
- `output/model_fla_state_audit_2026_08_11/model_fla_state_overview.png`

## Current Best Hypothesis

Keep as a diagnostic hypothesis, not a global promotion:

- `VEGLC` transport gate from `Simulations/brodbar/hermes/transport_gate_eglc_elac_46d_n32_endpoint16/best_params.json`

This candidate fixes extracellular glucose depletion:

- `EGLC` final: `13.21 mM` vs Brodbar `12.92 mM`
- `EGLC` nRMSE: `0.101`

But it breaks internal balance:

- `GLC` final: about `12.40 mM` vs Brodbar `0.826 mM`
- `LAC` final: about `0.166 mM` vs Brodbar `6.463 mM`

## Completed In This Work Block

- [x] Full Brodbar panel evaluation of the `VEGLC` transport gate candidate.
- [x] Lactate-focused pass: `VELAC + VLDH`.
- [x] Glucose-utilization pass: `vmax_VHK + km_GLC_HK`.
- [x] Expanded `vmax_VHK` to the global upper bound `5.0`.
- [x] Tested `VHK + km_ATP_HK`.
- [x] Tested `VHK + VPGI/VPFK`.
- [x] Built a compact comparison table/figure across recent FLA diagnostic candidates.
- [x] Ran the bridge pass seeded from `VHK + km_ATP_HK`, then opened `VELAC/VLDH`.
- [x] Tested controlled `VEGLC` import cap/feedback around `transport_depletion_gate`.
- [x] Profiled native glycolytic fluxes and pool balances before the next optimization.
- [x] Compared fixed one-factor probes for `VPEP_PASE`, `VPFK`, and `VPK`.
- [x] Selected decreasing `vmax_VPEP_PASE` as the next single open downstream lever.
- [x] Ran the decrease-only `vmax_VPEP_PASE` FLA pass with fixed mild `VEGLC` feedback and fixed `VHK/km_ATP_HK`.
- [x] Replayed the resulting candidate across all 55 mapped Brodbar metabolites.
- [x] Rejected the local optimum after PEP/G6P and mean-panel regressions.
- [x] Added a hard PEP-trajectory guard to the `VPEP_PASE` runner.
- [x] Tested the constrained two-parameter `VPEP_PASE` decrease plus `VPK` increase pass.
- [x] Replayed the best coupled point across all 55 mapped Brodbar metabolites.
- [x] Rejected the coupled candidate because PEP/G6P guards failed and the focused GLC/ATP thresholds were not met.
- [x] Updated `fla_progress_log.md` with all decisions and artifact paths.
- [x] Profiled native ATP/ADP/redox controls over 46 days before opening another optimization.
- [x] Ran the narrow mono-parameter `km_ATP_HK` FLA pass with ATP/PEP/G6P/GLC/LAC/EGLC/ELAC and flux guards.
- [x] Replayed the best `km_ATP_HK` point on the full 55-metabolite Brodbar panel.
- [x] Rejected promotion because the focused GLC guard failed, despite full-panel mean nRMSE improvement.

## Candidate Ranking

1. Best partial glucose-utilization diagnostic:
   - `Simulations/brodbar/hermes/glucose_utilization_vhk_atp_46d_n16_upper5`
   - Parameters: `vmax_VHK = 5.0`, `km_ATP_HK = 0.06014413339486139`
   - `GLC` nRMSE: `8.281 -> 6.302`
   - Not promoted because `GLC` remains far too high.

2. Rejected glucose-lactate bridge diagnostic:
   - `Simulations/brodbar/hermes/vhk_atp_lactate_bridge_velac_vldh_46d_n24`
   - Seeded from `VHK + km_ATP_HK`, then opened `VELAC/VLDH`.
   - Improves `ELAC` nRMSE: `0.323 -> 0.210`.
   - Improves teacher fluxes: `VELAC` `0.518 -> 0.383`, `VLDH` `0.670 -> 0.583`.
   - Barely improves `GLC`: `6.302 -> 6.217`.
   - Worsens internal `LAC`: `0.950 -> 1.027`; rejected by guardrail.

3. Rejected `VEGLC` import cap/feedback diagnostic:
   - `Simulations/brodbar/hermes/veglc_import_feedback_vhk_atp_seed_46d_n28`
   - Seeded from `VHK + km_ATP_HK`, then activated `transport_depletion_gate_import_feedback`.
   - Best loss: `35.955 -> 34.252`.
   - `GLC` improves: `6.301 -> 5.111`, but below the required 20% improvement.
   - `EGLC` endpoint breaks: `0.0028 -> 0.1386`; final `12.95 -> 14.71 mM`, experimental `12.92 mM`.
   - `EGLC` slope and `VEGLC` teacher-flux guards fail.

4. Useful but weaker:
   - `Simulations/brodbar/hermes/glucose_utilization_vhk_only_46d_n14_upper5`
   - Parameter: `vmax_VHK = 5.0`
   - `GLC` nRMSE: `8.281 -> 7.023`

5. Disfavored for now:
   - `Simulations/brodbar/hermes/glucose_utilization_vhk_pgi_pfk_46d_n14_upper5`
   - It improves `GLC` less than `VHK + km_ATP_HK` and worsens `ELAC` / `VELAC` guardrails.

## Next Recommended Tasks

- [x] Run one narrow energy-affinity FLA pass with only `km_ATP_HK` open around the current mild-feedback seed.
  - Search: `0.05 .. 0.120288`, centered at `0.0601441`, with 12 trials plus one local refinement.
  - Best candidate: `km_ATP_HK = 0.120164`.
  - ATP endpoint: `5.58e-5 -> 8.70e-5 mM`.
  - G6P nRMSE: `12.946 -> 11.198`; PEP nRMSE: `0.275 -> 0.256`.
  - GLC nRMSE regressed: `5.929 -> 6.320`; focused guard failed.
  - Full panel mean nRMSE improved `8.102 -> 7.899`, median remained unchanged, with 7 improved, 1 regressed, and 47 similar.
  - Final decision: reject promotion; keep the original seed in `promoted_or_seed_params.json`.

- [x] Produce the 46-day ATP/ADP/redox diagnostic replay and decision artifacts:
  - `output/fla_energy_redox_control_profile/energy_redox_control_report.md`
  - `output/fla_energy_redox_control_profile/energy_redox_control_profile.png`
  - `output/fla_energy_redox_control_profile/energy_redox_late_controls.png`
  - `output/fla_energy_redox_control_profile/energy_redox_control_ranking.csv`

- [x] Evaluate `km_NADH_NAD` as a separate redox-only hypothesis.
  - Kept `km_ATP_HK` locked at the mild-feedback seed value `0.06014413339486139`.
  - Searched `km_NADH_NAD = 4.59219 .. 18.3688` over 46 days with 12 trials plus one local refinement.
  - Best diagnostic point: `km_NADH_NAD = 6.85357`; focused loss `47.5597 -> 47.2488`.
  - VLDH teacher nRMSE barely changed `0.670315 -> 0.669906`, below the required 2% gain.
  - ATP endpoint fell `5.5814e-5 -> 4.6458e-5 mM`; PEP nRMSE regressed `0.2746 -> 0.3005`.
  - Full panel passed non-inferiority (`8.10169 -> 8.09747` mean nRMSE), but the focused ATP/PEP/redox gate failed.
  - Final decision: reject promotion and retain the original seed.

- [x] Run a directed feasibility screen for `km_ATP_PFK` alone before any Optuna pass.
  - Reset both `km_ATP_HK = 0.06014413339486139` and `km_NADH_NAD = 9.184380136644775` to the mild-feedback seed.
  - Probed `0.90x`, `0.75x`, and `0.50x` below the seed `km_ATP_PFK = 0.03302569060009802`.
  - The `0.90x` point passed all guards and slightly improved loss, PEP, GLC, LAC, and VLDH, but no direct target improved by the required 1%.
  - The `0.75x` and `0.50x` points violated the G6P endpoint guard and worsened GLC; focused loss rose to `55.08` and `301.84`.
  - Decision: do not run Optuna and do not promote any `km_ATP_PFK` value.
  - Do not co-open ATP-affinity and redox parameters.

- [x] Diagnose the ATP-production drive through `km_ADP_ATP` before opening another capacity parameter.
  - Keep `km_ATP_HK`, `km_ATP_PFK`, and `km_NADH_NAD` at the mild-feedback seed.
  - Screened `0.90x` and `0.75x`; stopped before `0.50x` after transfer guards failed.
  - At `0.90x`, late ATP production rose `4.6%` without guard failure, but GLC improved only `0.56%`.
  - At `0.75x`, late ATP production rose `21.1%` and ATP endpoint `19.0%`, primarily through VPGK.
  - ATP consumption rose `21.0%` in parallel, late net ATP flux became more negative, and G6P/P3G endpoint guards failed.
  - Decision: abort before Optuna; retain the seed unchanged.

- [x] Attribute the compensating ATP-consumption increase before selecting another kinetic lever.
  - Replay only the seed and the diagnostic `km_ADP_ATP 0.75x` point with all other parameters fixed.
  - Exact closure achieved: maximum ATP-consumption reconstruction error `0.0`.
  - VHK explains `48.6%` and VPFK `41.6%` of the induced late consumption; together they explain `90.2%`.
  - VNDPK is a distant third at `7.5%`; all other sinks each explain less than `1%`.
  - The same reactions already dominate seed consumption: VHK `48.1%`, VPFK `41.8%`, VNDPK `7.4%`.
  - Pool check: GLC improves modestly, G6P worsens, F6P remains severely elevated, and F16BP improves slightly.
  - Decision: do not open another sink parameter; review the coupled VHK/VPFK ATP-demand relay structurally.

- [x] Audit investment-phase flux matching without optimization.
  - Compare seed and `km_ADP_ATP 0.75x` native fluxes through `VHK`, `VPGI`, `VG6PDH`, `VPFK`, `VTKL2`, and `VTAL`.
  - Reconstruct the exact `dG6P/dt = VHK - VPGI - VG6PDH` and `dF6P/dt = VPGI + VTKL2 + VTAL - VPFK` balances.
  - Quantify early, mid, and late mismatches against measured GLC, G6P, F6P, and F16BP trajectories.
  - Decide whether the next intervention is a kinetic coupling change or an ODE structural correction; do not open a parameter before this distinction is resolved.
  - Maximum pointwise closure error: `3.55e-15 mM/day`; the coded balances are exact to machine precision.
  - Seed G6P output/input: `0.045` at J1-J2, `3.382` at J10-J20, and `2.877` at J40-J46. The model first overfills and then drains G6P, but remains above Brodbar.
  - Seed F6P output/input: `0.680`, `0.399`, and `0.471`; F6P accumulates in every window while the measured pool declines.
  - `VTKL2 + VTAL` provide `98.2%` of early F6P input and `47-48%` of the mid/late input. The F6P defect is not a VPGI/VPFK-only problem.
  - The `km_ADP_ATP 0.75x` point raises late VHK, G6P output, F6P input, and VPFK by about `21%` together; it scales throughput without restoring matching.
  - Decision: retain the current G6P/F6P stoichiometric balances and move to a reversible kinetic-directionality hypothesis for non-oxidative PPP return.

- [x] Implement a reversible, feature-flagged `VTKL2/VTAL` directionality diagnostic before optimization.
  - Preserve the current irreversible MM formulation as the default/revert path.
  - Add a fixed, explicitly selectable reversible or product-feedback formulation for `VTKL2` and `VTAL`; do not fit its constants in the first pass.
  - Replay the same mild-feedback seed for 46 days and reconstruct G6P/F6P balances with native fluxes.
  - Require exact pointwise balance closure and compare early/mid/late F6P PPP-return share, output/input ratios, and GLC/G6P/F6P/F16BP trajectories.
  - Retain strong ATP, PEP, EGLC, ELAC, GLC, G6P, F6P, F16BP, VEGLC, VELAC, and VLDH safeguards.
  - Open kinetic constants only if a fixed reversible formulation improves F6P without transferring the defect to G6P, ATP, or PEP.
  - Added optional `reversible_saturation_difference` families for `VTKL2` and `VTAL`; the historical one-way MM rates remain the default and setting the blends to zero is an exact revert path.
  - Replayed seed, reversible VTKL2, reversible VTAL, and both reversible over 46 days with every kinetic constant fixed.
  - Maximum G6P/F6P pointwise closure error: `3.55e-15 mM/day`, including native non-negativity damping.
  - F6P nRMSE improved by `9.9%`, `40.2%`, and `84.1%`, respectively, but every reversible case transferred error to protected pools or teacher fluxes.
  - Reversible VTAL was the narrowest failure: G6P endpoint and F16BP endpoint guards failed; late F6P output/input rose `0.458 -> 1.118` and F6P ended at `0.00426 mM` versus `0.00703 mM` experimentally.
  - Reversible VTKL2 failed ATP, G6P, PEP, ELAC, VELAC, and VLDH safeguards; the double-reversible case failed G6P, F16BP, PEP, ELAC, VELAC, and VLDH safeguards.
  - Decision: reject the fixed reversible hypothesis, retain the irreversible seed, and do not optimize a reverse scale or blend.

- [x] Audit the complete PPP before introducing another kinetic family.
  - Reconstruct exact native balances for G6P, GL6P, GO6P, RU5P, R5P, X5P, E4P, S7P, GA3P, and F6P.
  - Compare every PPP pool having Brodbar measurements against its experimental trajectory and experimental finite-difference flux teacher where identifiable.
  - Attribute early, mid, and late carbon routing through `VG6PDH`, `VPGLS`, `V6PGD`, `VR5PI`, `VR5PE`, `VTKL1`, `VTKL2`, and `VTAL`.
  - Determine whether the next fixed structural probe should attenuate forward PPP return, add product feedback without reverse flux, or use a thermodynamically constrained reversible law.
  - Do not open a PPP kinetic constant until this pool-level audit identifies the reaction and time window responsible for the transfer defect.
  - Exact pointwise closure was obtained for all ten balances across all four fixed directionality cases: maximum error `0.0 mM/day`.
  - Only `G6P`, `GO6P`, and `F6P` are directly measured; their derivatives identify net pool balances but not unique reaction fluxes.
  - Seed net-teacher nRMSE: G6P `23.944`, GO6P `2.819`, F6P `50.886`; F6P flux-sign agreement is only `11.9%`.
  - Seed early PPP return to F6P is `2.983 mM/day`; the measured F6P teacher is only `+0.00929 mM/day` in J1-J2 and becomes negative thereafter.
  - The seven latent PPP pools were found to use a generic `1 mM` initialization fallback, confounding the early kinetic attribution.

- [x] Replay historical JA values for the seven latent PPP initial conditions at fixed kinetics.
  - Changed only GL6P, RU5P, R5P, X5P, E4P, S7P, and GA3P initial states; all measured initial states and kinetic constants stayed fixed.
  - Historical initialization reduced early PPP F6P return `2.983 -> 0.234 mM/day`.
  - F6P concentration nRMSE improved `27.045 -> 21.758` (`19.5%`) and F6P net-teacher nRMSE improved `50.886 -> 14.868` (`70.8%`).
  - The standalone change failed G6P, ATP, PEP, LAC, ELAC, VELAC, and VLDH guards and is not promoted globally.
  - It exposed the oxidative defect: in J1-J2, `VPGLS = 0.0787` versus `V6PGD = 0.2084 mM/day`; GO6P output/input is `2.65`, while the measured net teacher is only `-0.0112 mM/day`.
  - Decision: keep both initialization paths reversible and screen `vmax_V6PGD` before returning to VTAL feedback.

- [x] Run a directed `vmax_V6PGD` feasibility screen under historical latent-PPP initialization.
  - Hold every other kinetic constant at the mild-feedback seed and keep irreversible VTKL2/VTAL rates.
  - Probe fixed downward points around the early teacher ratio: `0.60x`, `0.50x`, `0.43x`, and `0.35x` of seed `vmax_V6PGD = 10.0`.
  - Primary target: reduce J1-J2 GO6P drainage toward `dGO6P/dt = -0.0112 mM/day`, improve GO6P net-teacher nRMSE by at least 20%, and improve GO6P concentration nRMSE by at least 5%.
  - Require exact ten-pool PPP closure and monitor G6P/F6P concentration plus net teachers.
  - Strong safeguards: NADP/NADPH, GLC, F16BP, ATP, PEP, LAC, EGLC, ELAC, VEGLC, VELAC, and VLDH.
  - Compare candidates against both the current production seed and the historical-initialization diagnostic reference.
  - Do not run Optuna or promote the historical initialization unless a fixed V6PGD point resolves GO6P without reproducing the transfer failures.
  - Maximum ten-pool closure error was `0.0 mM/day`; no optimization or parameter promotion occurred.
  - Teacher-flux nRMSE improved monotonically by `40.1%`, `50.1%`, `57.1%`, and `65.2%`, respectively.
  - GO6P concentration nRMSE improved by only `0.27%`, `0.40%`, `0.53%`, and `0.75%`; even `0.35x` ended at `2.18e-5 mM` versus `0.00893 mM` experimentally.
  - The `0.50x`, `0.43x`, and `0.35x` points passed incremental guards relative to the historical-initialization reference, but every point failed production transfer guards for ATP, ELAC, G6P, LAC, NADPH, PEP, VELAC, and VLDH.
  - At J1, the historical-initialization seed gives `VPGLS = 0.000313` and `V6PGD = 4.32514 mM/day`; matching the J1-J2 mean teacher proxy requires `V6PGD = 0.011478`, a capacity scale near `0.002654x` or `vmax_V6PGD = 0.02654`.
  - Decision: reject the tested isolated V6PGD points and retain all production defaults.

- [x] Run a short initial-rate boundary screen before another 46-day PPP replay.
  - Keep the historical latent-PPP initialization, irreversible VTKL2/VTAL, and every kinetic constant except `vmax_V6PGD` fixed.
  - Probe `0.010x`, `0.005x`, `0.002654x`, and `0.001x` over J1-J2, explicitly bracketing the early-mean teacher-matched scale.
  - Require correct GO6P derivative sign, finite GO6P retention, improved GO6P concentration and teacher errors, and exact ten-pool closure.
  - Track VPGLS/V6PGD routing, G6P, F6P, RU5P, NADP, and NADPH to determine whether the required scale is a plausible fixed capacity or evidence for a state-dependent gate/feedback law.
  - Extend only an early-window feasible point to 46 days and reapply all production transfer guards; otherwise reject fixed-capacity V6PGD and audit GO6P affinity or VPGLS/V6PGD coupling.
  - The `0.002654x` point matched the J1-J2 mean teacher at the initial state but changed GO6P flux sign by J1.058 as VPGLS increased; it is not dynamically feasible.
  - A refinement at `0.0125x`, `0.015x`, `0.020x`, `0.030x`, and `0.050x` identified `0.020x` as the narrowest point with 100% GO6P teacher-sign agreement.
  - At `0.020x`, J1-J2 teacher nRMSE improved `94.6%`, concentration nRMSE improved `81.2%`, GO6P stayed positive, redox remained valid, and ten-pool closure was exact.
  - The fixed point was therefore extended to 46 days under historical latent-PPP initialization.
  - On 46 days, `0.020x` improved early/full GO6P teacher errors by `97.8%/97.6%` and GO6P concentration nRMSE by `62.7%`, with no incremental guard failure.
  - It still failed nine production-transfer guards because the historical initialization retained its ATP, ELAC, G6P, LAC, NADPH, PEP, VELAC, and VLDH defects.
  - Decision: retain `vmax_V6PGD = 0.20` as a diagnostic candidate only; do not promote it or the historical initialization.

- [x] Deconfound V6PGD kinetics from latent-PPP initialization in one controlled 46-day transfer replay.
  - Compare the unchanged current production seed against `vmax_V6PGD = 0.20` under the same current generic latent-PPP initialization.
  - Change exactly one kinetic constant and no initial condition; preserve irreversible VTKL2/VTAL.
  - Reapply GO6P/G6P/F6P concentration and net-teacher criteria plus ATP, PEP, GLC, LAC, EGLC, ELAC, VEGLC, VELAC, VLDH, NADP, and NADPH guards.
  - If the parameter transfers safely, keep it as a current-initialization PPP candidate for the next coupled audit; otherwise reject fixed V6PGD and move to an initialization-aware or state-dependent VPGLS/V6PGD law.
  - Contract verified: both cases used current generic latent-PPP initialization; the candidate changed only `vmax_V6PGD: 10.0 -> 0.20`, with no initial-state change.
  - Maximum ten-pool closure error was `0.0 mM/day`; no optimization or parameter promotion occurred.
  - At J1, current `GL6P = 1.0 mM` gives `VPGLS = 3.7374 mM/day`; reducing V6PGD to `0.0865 mM/day` reverses the GO6P balance to `+3.6509 mM/day` versus teacher `-0.0112`.
  - GO6P concentration nRMSE regressed `0.9919 -> 8.3928`; net-teacher nRMSE regressed `2.8193 -> 21.0330`; J1-J2 mean model flux became `+1.1795 mM/day`.
  - NADPH time-mean ratio was the only peripheral guard failure (`0.04633 -> 0.01464 mM`); G6P improved slightly while F6P, ELAC, VELAC, and VLDH changed only marginally.
  - Matching the J1-J2 mean teacher at the initial state requires V6PGD scale `0.86669x` (`vmax_V6PGD = 8.6669`) under current initialization, versus `0.002654x` under historical GL6P initialization.
  - Decision: reject transfer of `vmax_V6PGD = 0.20`; retain the production seed and treat GL6P initialization and V6PGD capacity as structurally confounded.

- [x] Map the `GL6P(0)-vmax_V6PGD` identifiability ridge before another kinetic calibration.
  - Use fixed, reversible diagnostic grids only; do not run Optuna or promote an initial condition.
  - Span GL6P initial values from the historical `7.62e-6 mM` to the generic `1 mM` and V6PGD capacity from the historical-context candidate `0.20` to the current-context J1 match near `8.67`.
  - First evaluate the exact J1 balance `dGO6P/dt = VPGLS(GL6P) - V6PGD(GO6P, NADP)` and retain only combinations bracketing the Brodbar teacher.
  - Replay retained combinations over J1-J2 and score GO6P concentration/teacher shape, G6P, F6P, RU5P, NADP, NADPH, and ten-pool closure.
  - Decide whether one transferable parameter region exists; otherwise replace the generic latent initialization with an estimated/quasi-steady initialization layer before further PPP kinetic learning.
  - Evaluated a `61 x 81` exact J1 grid and replayed 20 teacher-matched ridge points in both current-other-latent and historical-other-latent backgrounds (`40` J1-J2 simulations).
  - Exact J1 teacher was `-0.0113983 mM/day`; required `vmax_V6PGD` rose from `0.02708` at historical GL6P to `8.66745` at generic GL6P, a `320.1-fold` ridge span.
  - Fine dynamic minimum was identical in both backgrounds: `GL6P(0) = 0.0013 mM`, `vmax_V6PGD = 0.148336`.
  - This point fit GO6P concentration well (`nRMSE 0.0456`) but missed its flux shape (`teacher nRMSE 1.515-1.517`, sign agreement `74.1%`), so it failed the predeclared GO6P shape gate.
  - G6P remained severely mismatched (`nRMSE 17.36-17.37`); F6P depended strongly on the other latent states (`nRMSE 18.21` current versus `0.881` historical).
  - Redox remained valid and maximum ten-pool closure error was `0.0 mM/day` for all 40 replays.
  - Decision: no cross-background compatible ridge region exists; do not promote any pair or calibrate V6PGD alone.

- [x] Build and diagnose a constrained latent-PPP initialization layer at fixed kinetics.
  - Keep all experimentally measured J1 states fixed and retain the production kinetic seed, including `vmax_V6PGD = 10.0`.
  - Estimate only GL6P, RU5P, R5P, X5P, E4P, S7P, and GA3P initial states using bounded quasi-steady residuals for their exact PPP balances plus the measured G6P, GO6P, and F6P teachers.
  - Preserve explicit revert paths for both generic `1 mM` and historical JA initializations; generate a diagnostic initialization artifact only, not a production promotion.
  - Compare generic, historical, and constrained initializations over J1-J2 first, with ten-pool closure, positivity, NADP/NADPH, and measured-pool shape gates.
  - Extend to 46 days only if the constrained initialization improves G6P, GO6P, and F6P jointly without transferring error to ATP, PEP, lactate, or extracellular teachers.
  - Solved three bounded multistart formulations: latent quasi-steady, balanced teacher, and teacher-priority; only the seven latent states changed and every measured state remained locked.
  - Measured-teacher sensitivity rank was `2/3`: G6P is exactly insensitive to all seven latent initial states, GO6P depends only on GL6P, and F6P depends on X5P/E4P/S7P/GA3P.
  - Fixed seed kinetics make the GO6P teacher theoretically infeasible: even saturating GL6P gives maximum `dGO6P/dt = -0.2140 mM/day` versus teacher `-0.01140`.
  - Latent-QSS initialization improved F6P concentration nRMSE `22.884 -> 0.860` and teacher nRMSE `718.956 -> 25.947`, but GO6P worsened to `0.984` concentration nRMSE and `61.132` teacher nRMSE.
  - Teacher-weighted solutions further improved F6P (`0.486-0.487` concentration nRMSE) but pushed GL6P to its `2 mM` bound and worsened GO6P to `2.639` concentration nRMSE and `101.79` teacher nRMSE.
  - All cases preserved positivity/redox and exact ten-pool closure (`0.0 mM/day`), but none passed the joint measured-pool gate; no 46-day replay or promotion was produced.
  - Decision: an initialization-only solution does not exist at the production PPP capacities.

- [x] Run a fixed, narrow V6PGD feasibility screen coupled to the constrained initialization solver.
  - Keep every other kinetic constant fixed and test only `vmax_V6PGD` scales near the analytical boundary: `0.97x`, `0.9532x`, `0.93x`, `0.91x`, and `0.90x`.
  - Re-solve the same bounded seven-state initialization problem independently at each fixed capacity; do not run Optuna or promote parameters/states.
  - Treat G6P as a non-inferiority guard rather than an initialization target because its J1 sensitivity to all seven latent states is exactly zero.
  - Require joint GO6P/F6P concentration and teacher improvement, latent residual reduction, redox validity, positivity, and exact ten-pool closure over J1-J2.
  - The theoretical saturation boundary is `vmax_V6PGD = 9.53165` (`0.95317x`); points below it test whether a finite bounded GL6P solution becomes dynamically feasible.
  - Extend only a fully guarded fixed point to 46 days; if none passes, test the alternative minimal lever `vmax_VPGLS` upward around its analytical `+4.93%` saturation threshold.
  - Re-solved all three constrained formulations independently at `0.97x`, `0.9532x`, `0.93x`, `0.91x`, and `0.90x`; only `vmax_V6PGD` changed.
  - Only `0.90x` made the GO6P teacher feasible within the finite `GL6P <= 2 mM` bound. The balanced solution gave `GL6P(0) = 1.68787 mM` and passed all J1-J2 gates.
  - Relative to its same-mode seed, J1-J2 nRMSE improved by `30.8%/9.17%` for GO6P concentration/teacher and `7.72%/8.86%` for F6P concentration/teacher; the latent residual nRMS fell `1.16%`.
  - The guarded 46-day replay passed ATP, PEP, GLC, LAC, EGLC, ELAC, positivity, redox, and exact closure non-inferiority gates. Full-horizon GO6P/F6P joint score improved `34.636 -> 33.407`.
  - Absolute global errors remain large and F6P concentration worsened slightly over 46 days (`20.666 -> 21.076` nRMSE); retain `vmax_V6PGD = 9.0` plus the balanced initialization as a diagnostic candidate only, with no promotion.

- [x] Refine the finite-bound V6PGD transition around the retained `0.90x` diagnostic candidate.
  - Keep the balanced constrained-initialization formulation and every other kinetic constant fixed.
  - Test a narrow deterministic grid spanning `0.895x`, `0.900x`, `0.9025x`, `0.905x`, and `0.9075x`; include the `1.0x` balanced seed as the unchanged reference.
  - Rank primarily on full-horizon GO6P/F6P concentration plus teacher score, not J1-J2 alone, while preserving G6P non-inferiority and the ATP, PEP, GLC, LAC, EGLC, ELAC, positivity, redox, and closure guards.
  - Use the screen only to establish robustness and select a diagnostic operating point; do not promote kinetics or latent initial states while G6P and F6P absolute errors remain high.
  - Re-solved the balanced seven-state initialization and replayed all five points plus the unchanged balanced seed over 46 days.
  - `0.895x` minimized the unconstrained full score (`32.630`) but failed the J1-J2 gate because F6P concentration worsened `6.25%` and its teacher improved only `4.96%`.
  - `0.900x` was the only point passing every local and full-horizon guard; its joint GO6P/F6P score was `33.407`, a `3.55%` improvement versus balanced seed `34.636`.
  - Higher points progressively lost the GO6P benefit; `0.9075x` worsened the joint score by `1.20%` and placed GL6P(0) near its upper bound at `1.9815 mM`.
  - Decision: retain `0.900x` only as the robust diagnostic operating point. Production kinetics and initialization remain unchanged.

- [x] Audit the residual 46-day F6P accumulation at the retained `0.900x` diagnostic point before opening another PPP kinetic lever.
  - Keep `vmax_V6PGD = 9.0`, the balanced constrained initialization, and all other kinetics fixed; compare against the balanced seed using the saved full-horizon trajectories.
  - Reconstruct F6P input/output attribution through `VPGI`, `VPFK`, `VTKL2`, and `VTAL` over J1-J2, days 2-10, 10-20, 20-30, and 30-46.
  - Quantify when the simulated F6P trajectory diverges from Brodbar, the cumulative contribution of each reaction, and whether the retained V6PGD point changes the imbalance or only the initial transient.
  - Track the coupled G6P, GA3P, E4P, S7P, ATP, and PFK-driving states to distinguish an initialization artifact from insufficient VPFK drainage or non-oxidative PPP return.
  - Produce a fixed-parameter structural decision only; do not calibrate VPFK, VPGI, VTKL2, or VTAL in this audit.
  - Reconstructed `dF6P/dt = VPGI + VTKL2 + VTAL - VPFK` from the saved seed and `0.900x` trajectories with maximum error `4.44e-16 mM/day`.
  - Candidate F6P divergence begins at day `5.10` versus `5.15` for seed; the V6PGD correction does not delay the defect.
  - After J2, non-oxidative PPP return supplies `46.9%` of F6P input and PGI supplies the remainder; both are material sources rather than a single dominant input defect.
  - F6P occupancy of PFK averages `85.6%`, inferred PFK modulation remains `1.000`, but ATP occupancy averages only `2.20%` after J2 and falls below `1%` after day 20.
  - Actual VPFK remains below teacher-required drainage by a post-J2 weighted mean `0.03686 mM/day`; classify the accumulation as ATP-limited VPFK drainage, not insufficient `vmax_VPFK` or latent initialization.
  - Decision: do not reopen VPFK, VPGI, VTKL2, VTAL, or PFK affinity. Trace ATP production and consumption in this exact PPP context first.

- [x] Reconstruct the J1-J10 ATP production-consumption transition in the retained `vmax_V6PGD = 9.0` balanced PPP context.
  - Replay only the balanced seed and retained `0.900x` point over J1-J10 with complete ATP flux tracking; keep all kinetics and initial states fixed to their diagnostic contracts.
  - Reconstruct the exact ATP balance by individual producer and consumer, with windows J1-J2, days 2-4, 4-6, 6-8, and 8-10.
  - Locate the ATP collapse relative to F6P divergence, quantify whether VPGK/VPK production fails before VHK/VPFK demand, and compare candidate-minus-seed cumulative contributions.
  - Track ADP, AMP, PEP, B13PG, PYR, F16BP, GLC, G6P, and F6P plus VPGK, VPK, VAK, VHK, VPFK, and the remaining ATP sinks.
  - Use this as a fixed-parameter causal audit only. Do not reopen `km_ATP_PFK`, `vmax_VPFK`, or another energy parameter until the J1-J10 source of ATP collapse is assigned.
  - Replayed the saved balanced seed and `0.900x` states at `0.005-day` resolution; reconstructed the raw ATP balance plus native low-pool damping with maximum closure error `7.11e-15 mM/day`.
  - Candidate ATP peaks at `1.7415 mM` on day `1.08`, then crosses `km_ATP_PFK` on day `2.51` and `0.01 mM` on day `2.72`, preceding F6P divergence by `2.59 days`.
  - ATP production loses half of its initial-window level on day `1.275`; total demand follows on day `1.305`. The transition is nearly synchronous but production declines first.
  - B13PG collapses from `3.5840 mM` at J1 to `9.37e-5 mM` by J1.3 and `1.03e-5 mM` at ATP collapse; VPGK utilization is then only `0.00295` despite preserved ADP/ATP drive.
  - VPK remains at `0.611` utilization and supplies `52.4%` of ATP production at collapse, but only partially compensates. VHK supplies `78.3%` of residual ATP demand; VPFK has already fallen to `8.2%`.
  - Decision: attribute ATP collapse to exhaustion of the VPGK/B13PG production pulse plus persistent VHK-dominated demand. The V6PGD point delays ATP collapse slightly versus seed (`2.51` vs `2.44 days`) and does not create the defect.

- [x] Audit the exact J1-J3 B13PG production-drainage balance in the retained PPP context.
  - Keep the balanced seed and `vmax_V6PGD = 9.0` diagnostic contracts fixed; reuse or replay the dense J1-J3 trajectories without calibration.
  - Reconstruct `dB13PG/dt = VGAPDH - VPGK - VDPGM` with native low-pool damping and windows J1-J1.1, 1.1-1.3, 1.3-1.6, 1.6-2.0, and 2.0-3.0.
  - Quantify depletion of the experimental B13PG initial stock, cumulative VGAPDH replacement, VPGK ATP yield, and VDPGM diversion into the Rapoport-Luebering shunt.
  - Track GA3P, NAD/NADH drive, ADP/ATP drive, P3G, B23PG, ATP, and VHK demand to distinguish an initial-stock transient from insufficient sustained GAPDH supply or excessive PGK/shunt drainage.
  - Produce a structural decision before changing `vmax_VGAPDH`, `vmax_VPGK`, `vmax_VDPGM`, B13PG initialization, or ATP-demand kinetics.
  - Replayed the balanced seed and retained `vmax_V6PGD = 9.0` point over J1-J3 at `0.001-day` resolution; exact effective B13PG closure error was `0.0 mM/day` in both cases.
  - Provenance audit found that the B13PG and B23PG workbook curves are pointwise identical, including their shared J1 value `3.584045 mM`; B23PG is an active calibration target but B13PG is not.
  - In the retained candidate, B13PG falls below `1%` of its initial stock on day `1.270` and below the native `1e-3 mM` damping threshold on day `1.275`.
  - Integrated J1-J3 VGAPDH input is `0.62170 mM` versus total drainage `4.21056 mM`, so GAPDH replaces only `14.77%` of drainage.
  - VPGK carries `89.92%` of integrated drainage and yields `3.78610 mM` ATP; VDPGM diverts `10.08%` (`0.42446 mM`) through the Rapoport-Luebering branch.
  - GA3P occupancy remains near saturation, while the GAPDH NAD/NADH drive falls from `0.3203` at J1 to about `0.0195` over J2-J3; sustained GAPDH supply is therefore redox-limited after the initial pulse.
  - Decision: reclassify B13PG(0) as a non-independent latent initialization. Do not identify PGK/GAPDH kinetics from the current ATP pulse and do not promote any parameter or initial state.

- [x] Build a reversible constrained B13PG initial-state diagnostic at fixed kinetics.
  - Keep B23PG locked to its Brodbar measurement and retain the saved balanced PPP seed and `vmax_V6PGD = 9.0` diagnostic contexts.
  - Treat only B13PG(0) as latent; preserve `3.584045 mM` as the explicit duplicated-data revert branch.
  - Construct bounded initialization candidates from the exact J1 balance and short-horizon B13PG/ATP consistency, without changing `vmax_VGAPDH`, `vmax_VPGK`, `vmax_VDPGM`, or ATP-demand kinetics.
  - Replay J1-J3 first and require exact B13PG/ATP closure, positivity, redox validity, B23PG non-interference, and removal of the artificial VPGK pulse.
  - Extend guarded candidates to J1-J10 only to test whether ATP production becomes sustainable; do not promote an initialization until extracellular and full-panel guards are checked.
  - Solved the unique exact J1 root `B13PG(0) = 1.76677669e-4 mM`, only `4.92956e-5` of the duplicated `3.584045 mM` revert value.
  - Screened fixed root scales `0.25x`, `0.5x`, `1x`, `2x`, `4x`, and `8x` with B23PG(0) locked exactly and no kinetic changes.
  - The QSS root closed B13PG exactly (`0.0 mM/day` replay error), preserved positivity and NAD/NADH conservation, and removed `99.82%` of stock-supported B13PG drainage.
  - VPGK ATP yield fell from `3.7950` to `0.6080 mM` over J1-J3, confirming that most early ATP production was supported by the duplicated B13PG stock.
  - B23PG nRMSE worsened `0.05626 -> 0.12663` (`2.25x`) because VDPGM supply fell from `0.42427` to `0.02825 mM`; ATP nRMSE worsened `0.75688 -> 0.91673` and ATP crossed `0.01 mM` on day `2.075` rather than `2.725`.
  - No candidate passed the B23PG non-interference gate, so none was extended to J1-J10. The explicit revert branch remains available and no initial state was promoted.
  - Decision: reject B13PG-only initialization as a guarded replacement. At fixed kinetics, the duplicated stock artificially supports both VPGK ATP production and VDPGM supply to measured B23PG.

- [x] Audit the exact B23PG production-drainage balance in the J1 QSS-B13PG context.
  - Compare the duplicated-data revert branch against the exact `B13PG(0) = 1.76677669e-4 mM` root at fixed kinetics and locked B23PG(0).
  - Reconstruct `dB23PG/dt = VDPGM - V23DPGP`, including native damping if active, over the same J1-J3 windows.
  - Quantify how much of the B23PG teacher trajectory is supported by the duplicated B13PG stock, and separate insufficient VDPGM supply from excessive V23DPGP drainage.
  - Track B13PG, B23PG, P3G, ATP, VPGK, VDPGM, and V23DPGP; do not open `vmax_VDPGM`, `vmax_V23DPGP`, or either initial state before structural attribution.
  - Exact closure was `0.0 mM/day` in both branches. Removing the duplicated B13PG stock removed `93.34%` of integrated VDPGM supply, while integrated V23DPGP changed by only `-0.03079 mM`.
  - In the QSS context, VDPGM supplied only `3.74%` of the production required by the B23PG teacher given model drainage.
  - Decision: classify the defect as `VDPGM_supply_limited_by_B13PG_context`; hold V23DPGP and test an identifiable VDPGM-supply lever without restoring duplicated B13PG stock.

- [x] Resolve the source provenance of the duplicated B13PG/B23PG and P2G/P3G rows to the limit allowed by available files.
  - Keep P2G outside independent objective weighting until the original table or publication confirms the labels.
  - Do not use the two identical trajectories as separate constraints on VPGM and VENOPGM.
  - The duplicates were present at the first repository import. The 55-by-14 workbook is classified as a curated model-input table, not a traceable raw-replicate export.
  - Retain B23PG as the BPG observation and treat B13PG as latent. Retain P3G only as a descriptive representative; exclude P2G/P3G from reaction-specific teacher assignment.
  - Exact analytical annotation and replicate-level provenance remain a publication blocker.

- [x] Audit concentration-volume and time-unit scaling for every extracellular transport balance before another transport calibration.
  - The network contains 26 paired compartment transports with equal-and-opposite concentration coefficients, equivalent to amount conservation only under equal effective volumes.
  - At hematocrit 0.60, an intracellular-equivalent teacher would be `2/3` of the current extracellular derivative teacher; no hematocrit or compartment-volume metadata justify promoting this correction.
  - Historical source labels changed from hours to days without a traceable ODE-rate conversion. Treat current constants as empirical per-model-day values and freeze transport refitting until scaling metadata are resolved.

- [x] Formalize sequential FLA temporal ownership.
  - J1-J3 owns initialization, energy, and Rapoport-Luebering attribution; J3-J10 owns the glycolytic relay; J10-J46 owns transport and storage preservation.
  - A later block cannot compensate for a failed earlier block. Every candidate must retain prior-block gates and pass a final J1-J46 replay.
  - Seed mean nRMSE values are `6.1763`, `4.4476`, and `1.5302` respectively; G6P is worst in the first two blocks and GLC in the last.

- [x] Build the pre-calibration structural/practical identifiability mask.
  - Corrected the reaction-parameter parser so numeric reaction names such as `V23DPGP` and `V6PGD` are included; the map now exposes 109 parametrized reactions and 201 parameters.
  - Direct local flux sensitivities were evaluated in both duplicated-data and QSS-B13PG contexts, then reduced by blockwise SVD/QR screening.
  - The local bases are attribution maps, not simultaneous optimization scopes. The executable next-run mask contains only `vmax_VDPGM`; J3-J10 and J10-J46 remain closed.
  - Keep `vmax_V23DPGP` and `km_B23PG` fixed. Keep transport parameters fixed until volume/time scaling is resolved.

- [x] Run a one-dimensional, reversible `vmax_VDPGM` screen in the QSS-B13PG context.
  - Use J1-J3 as the primary window and keep B23PG(0), B13PG(0), V23DPGP kinetics, PPP initialization, and all other kinetics fixed.
  - Score B23PG concentration, teacher-required VDPGM supply, ATP, B13PG, P3G, and exact balances. Reject any point that restores the artificial ATP pulse or harms cumulative guards.
  - Extend only a passing point through J3-J10 and then J10-J46; do not optimize downstream blocks concurrently.
  - Screened deterministic multipliers `0.5x, 1x, 2x, 4x, 8x, 16x, 32x`; only `vmax_VDPGM` changed and no Optuna search was used.
  - `2x-32x` passed J1-J3. Only `2x` and `4x` preserved the cumulative J1-J10 guards; `8x-32x` failed on F6P.
  - Both `2x` and `4x` passed J1-J46 concentration, positivity, redox, exact-balance, and 55-metabolite aggregate guards.
  - Retain `2x-4x` as a diagnostic bracket with `2x` (`vmax_VDPGM = 2.99439`) as the conservative anchor. Do not promote: ATP still collapses near day `2.1`, B23PG remains imperfect, and the data do not select a unique point.
  - VDPGM remains responsive at `32x`; J1-J3 integrated supply increased `44.5%` from `16x` to `32x`, despite mean B13PG occupancy `0.00402` and GAPDH redox drive `0.0499`.

- [x] Refine the guarded `vmax_VDPGM` Pareto interval between `2x` and `4x`.
  - Keep the complete QSS-B13PG, V23DPGP, PPP, and sequential temporal contracts unchanged.
  - Use a deterministic grid such as `2.0x, 2.5x, 3.0x, 3.5x, 4.0x`; rank jointly on B23PG trajectory/slope/endpoint and the F6P, GLC, ELAC regression margins.
  - Preserve `2x` as the conservative anchor and do not open another parameter. Stop if no interior point improves the Pareto compromise.
  - Any retained point remains diagnostic until ATP sustainability and parameter uncertainty are resolved.
  - Replayed `2x, 2.5x, 3x, 3.5x, 4x` over J1-J3, J1-J10, and J1-J46; every point passed all cumulative guards.
  - Ranked three B23PG objectives (trajectory, endpoint, slope) against J46 F6P, GLC, and ELAC nRMSE using a predeclared min-max normalized Pareto distance.
  - `3x` was the interior knee: ideal distance `0.77357`, improving `21.35%` over the best `2x/4x` anchor, above the predeclared `5%` threshold.
  - The strict-solver replay (`rtol=1e-5`, `atol=1e-8`) retained the same `3x` point with `21.11%` improvement.
  - Retain `vmax_VDPGM = 4.49158` (`3x`) as the diagnostic Pareto anchor. Do not promote it: ATP remains unsustainable and this solver check is not biological validation.

- [x] Stop DPGM capacity refinement and return to ATP sustainability in the fixed `3x` diagnostic context.
  - Compare the QSS-B13PG seed and `vmax_VDPGM = 4.49158` with exact J1-J3 ATP production/consumption attribution.
  - Quantify how much ATP is lost through reduced VPGK partitioning versus the unchanged upstream GAPDH/redox supply.
  - Keep `3x` diagnostic only and do not open a coupled parameter until the ATP deficit is assigned under the new BPG branch.
  - Exact ATP and B13PG closures passed at `3.55e-15` and `0` mM/day, respectively.
  - Integrated J1-J3 VGAPDH supply and its redox drive changed by only `+0.0048%` and `+0.0050%`; upstream supply is effectively fixed.
  - The VPGK drainage share fell from `95.58%` to `88.00%`; integrated VPGK fell `7.98%` while VDPGM rose `171.08%`.
  - Reduced VPGK accounted for `99.52%` of the gross ATP-production loss. ATP consumption then fell `1.14%`, primarily through VNDPK, VHK, VRKa, and VPFK.
  - ATP crossed `0.01 mM` at day `2.066` versus `2.073` for the seed. The `3x` branch remains diagnostic only.

- [x] Reconstruct the ATP-teacher-required VPGK and upstream VGAPDH trajectories in the fixed `3x` QSS-B13PG branch.
  - Smooth the measured Brodbar ATP trajectory under the existing temporal/provenance contract; its derivative is inferred, not independently observed.
  - Compute `VPGK_required = dATP_teacher/dt + ATP_consumption - VPK - VAK`, using native reaction-resolved ATP consumption.
  - Compute `VGAPDH_required = dB13PG/dt + VPGK_required + VDPGM`, with B13PG latent and bounded by QSS/positivity constraints.
  - Compare required versus native fluxes by temporal window and against current rate-law ceilings before opening any upstream kinetic lever.
  - The J1-J3 ATP teacher is weakly resolved: only day 1 lies inside the block and the next observation is day 4. PCHIP and linear J1-J4 derivatives nevertheless gave VPGK integrals within `0.014%`.
  - PCHIP/QSS reconstruction required integrated VPGK `2.835x` native and integrated VGAPDH `2.646x` native.
  - `VPGK_required` ranged from `-0.2293` to `7.6708 mM/day` and became negative at day `1.453`; an irreversible VPGK cannot satisfy the ATP teacher pointwise while VPK, VAK, and ATP demand remain frozen.
  - The current VPGK hard ceiling (`40.023`) was not exceeded, but fixed-state support would require a median/p95 `vmax_VPGK` of `63.48/170.42`, revealing strong state coupling.
  - QSS `VGAPDH_required` reached `7.9339 mM/day`, exceeding the current hard ceiling `6.3899` from day 1; its fixed-state median/p95 Vmax requirement was `10.29/24.96`.
  - QSS and native-latent B13PG derivative policies gave essentially identical upstream requirements. Do not open VPGK, VGAPDH, redox, or ATP-demand parameters from this ATP-only inversion.

- [x] Audit the joint ATP-ADP-AMP teacher balances and adenylate-kinase directionality in the fixed `3x` branch.
  - Reconstruct PCHIP net teachers for ATP, ADP, AMP, and their total adenylate pool with explicit uncertainty due to the J1-J4 sampling interval.
  - Close each native ODE balance reaction by reaction, including VAK/VAK2, NDPK, ATP-investment reactions, and corrected SAM adenylate transfer.
  - Determine whether the negative ATP-only `VPGK_required` interval is caused by adenylate-kinase directionality, incompatible sparse teacher derivatives, or a missing/incorrect adenylate sink/source.
  - Do not optimize kinetics until the three measured adenylate curves admit a mutually consistent flux reconstruction.
  - Exact native ATP, ADP, AMP, VAK-split, and total-pool closures passed at `0`, `0`, `0`, `0`, and `3.55e-15 mM/day`.
  - The PCHIP teacher total decreased `0.10187 mM` over J1-J3, whereas the native total increased `0.46368 mM`; the integrated missing total-pool correction was `-0.56481 mM` and numerical damping contributed only `+0.00072 mM`.
  - VAK cancels exactly from the total balance. Native VAK was forward (`2 ADP -> AMP + ATP`) for `100%` of J1-J3, while the joint reconstruction required reverse VAK for `100%`; only `92.7%` of the required trajectory lay within the current reverse/forward hard bounds.
  - ATP-, ADP-, and AMP-derived VAK estimates disagreed strongly (`1.8659 mM/day` mean spread), proving that no isolated VAK trajectory can reconcile the three teachers while total-pool ownership remains native.
  - VAPRT dominated native pool creation (`+0.53882 mM`), followed by VADSL (`+0.09548`) and VAK2 (`+0.01561`); VAMPD1 and VSAM removed `0.15553` and `0.03143 mM`.
  - VAPRT alone would require a negative integrated flux (`-0.02599 mM`) and was nonnegative for only `8.8%` of J1-J3. Eliminating VAPRT is therefore necessary but insufficient; a residual sink is required.

- [x] Run a reversible fixed-kinetic `VAPRT = 0` diagnostic, then quantify the residual `VAMPD1` sink requirement.
  - Keep the fixed `3x` QSS-B13PG state, VAK/VAK_rev, VAK2, VSAM, VADSL, and every glycolytic/PPP parameter unchanged.
  - First suppress VAPRT without optimization and replay J1-J3; reconstruct ATP, ADP, AMP, and total-pool balances exactly.
  - If the total still exceeds the teacher, calculate the VAMPD1 trajectory/capacity required to close the residual; do not fit it yet.
  - Protect IMP, ADE, PRPP, ATP, ADP, AMP, total adenylate, and the VAK directionality diagnostic. Keep VSAM as a secondary alternative because it perturbs ATP and ADOMET directly.
  - Only `vmax_VAPRT` changed, from `4.08799` to `0`; no optimization was used.
  - ATP, ADP, AMP, IMP, ADE, PRPP, ADOMET, VAK split, and total adenylate balances closed at machine precision; all states remained nonnegative.
  - Total-adenylate nRMSE improved `0.30122 -> 0.00824`; AMP improved `6.5547 -> 5.1441`, IMP `0.42329 -> 0.26983`, and ADE `4.4120 -> 0.14011`. ATP and ADP remained within the `10%` non-inferiority guards.
  - The VAPRT=0 total change was `-0.07310 mM` versus the PCHIP teacher `-0.10187 mM`, leaving a small residual AMP-deaminase sink.
  - VAMPD1 required `0.18163 mM` integrated versus `0.15355 mM` native, an additional `0.02807 mM`. The required trajectory was positive everywhere but stayed below the current `vmax_VAMPD1 = 0.08301` for only `11.2%` of J1-J3.
  - Fixed-state required `vmax_VAMPD1` median/p95/max were `0.10295/0.10397/0.10399`, approximately `1.24-1.25x` the seed.
  - A strict replay (`rtol=1e-5`, `atol=1e-8`) preserved the classification and p95 target (`0.10398`). Retain VAPRT=0 diagnostically, not as a promoted whole-model parameter.

- [x] Screen `vmax_VAMPD1` narrowly and deterministically under the fixed `VAPRT = 0` diagnostic.
  - Keep QSS-B13PG, `vmax_VDPGM = 3x`, VAK/VAK_rev, VAK2, VSAM, VADSL, and all glycolytic/PPP parameters fixed.
  - Replay multipliers `1.0x, 1.1x, 1.2x, 1.25x, 1.3x, 1.4x, 1.5x` relative to `vmax_VAMPD1 = 0.0830092`; do not use Optuna.
  - Select the smallest capacity that improves total-adenylate trajectory/slope/endpoint and AMP while preserving ATP, ADP, IMP, ADE, PRPP, ADOMET, positivity, exact balances, and VAK directionality.
  - Run J1-J3 first. Extend only guarded points to J1-J10 and J1-J46 before any parameter promotion.
  - The deterministic J1-J3 screen retained `1.1x, 1.2x, 1.25x, 1.3x`; `1.4x` and `1.5x` over-corrected at least one predeclared target. All four retained points passed J1-J10.
  - Standard J1-J46 retained `1.1x, 1.2x, 1.25x`; `1.3x` failed only the VAK directionality guard. The strict replay retained `1.1x, 1.2x`; `1.25x` also crossed the same VAK guard by a small margin.
  - The predeclared smallest-capacity rule selected `1.1x`, corresponding to `vmax_VAMPD1 = 0.0913101` from the `0.0830092` seed. The selection, but not the upper admissible boundary, was solver-invariant.
  - At J1-J46, `1.1x` improved total-adenylate nRMSE `0.33313 -> 0.24452`, slope nRMSE `1.12329 -> 1.11315`, endpoint error `0.39026 -> 0.20607`, AMP nRMSE `5.31243 -> 4.90597`, IMP nRMSE `1.00544 -> 0.99646`, and VAMPD1 teacher-flux nRMSE `0.87426 -> 0.86660`.
  - ATP and ADP changed by less than `0.001%`; the full-panel mean nRMSE changed by only `+0.261%`, and median nRMSE improved by `0.029%`. Exact closures remained near `2.0e-15 mM/day`, and every state remained nonnegative.
  - Strict J1-J46 replay reproduced the selected total nRMSE (`0.24481`), endpoint error (`0.20689`), AMP nRMSE (`4.90742`), and panel mean (`8.01422`). Retain `1.1x` only as a reversible diagnostic anchor; promote neither VAPRT suppression nor VAMPD1 capacity yet.

- [x] Audit the exact IMP balance and purine transfer under fixed `VAPRT = 0`, `vmax_VAMPD1 = 1.1x` before promotion.
  - Compare the VAPRT-zero `1.0x` seed with the `1.1x` anchor over J1-J3, J1-J10, and J1-J46 without changing kinetics.
  - Reconstruct `dIMP/dt = VHGPRT1 + VAMPD1 - VADSS - VIMPH - Vnucleo2` pointwise and attribute the teacher residual to each source and sink.
  - Track ADE and PRPP ownership, VAK sign transitions, and the near-depletion of PRPP (`5.3e-6 mM`) and ADOMET (`2.0e-5 mM`) at J46.
  - Decide whether hard VAPRT suppression is structurally credible across storage or whether APRT requires a bounded or time-dependent activity law. Do not open or promote another kinetic parameter during this audit.
  - Exact IMP, ADE, and PRPP reconstructions closed within `3.10e-16 mM/day`; the strict-screen replay reproduced the same classification.
  - Under `VAMPD1 = 1.1x`, the actual J1-J46 VAMPD1 integral was `3.76275 mM`, versus `3.84357 mM` required by the IMP teacher. The remaining `0.08082 mM` deficit is small relative to the APRT contradiction and does not justify a further VAMPD1 increase.
  - IMP nRMSE improved only `1.00544 -> 0.99646`; the modeled IMP change was `-0.11050 mM` versus `-0.02971 mM` experimentally. Other purine trajectories remained poor, including ADE `4.64480`, EADE `4.34949`, HYPX `4.99860`, and INO `6.61959` nRMSE at the anchor.
  - Because `d(ADE+EADE)/dt = -VAPRT` in the current model, the observed pair directly required `+0.99211 mM` integrated APRT and was positive for `100%` of J1-J46. Hard `VAPRT = 0` instead conserved the modeled pair exactly while the teacher decreased `0.99211 mM`.
  - The total-adenylate teacher required `-0.34019 mM` integrated APRT under the same anchor and changed sign by temporal block. The two independent APRT teachers disagreed by `1.33229 mM`; positive APRT alone cannot satisfy both.
  - PRPP production integrated only `0.12595 mM`, versus `0.92344 mM` consumed by VHGPRT1 and `0.20720 mM` by VHGPRT2 before any APRT consumption. Restoring approximately `0.992 mM` of APRT is infeasible under the current PRPP ownership.
  - Reject hard VAPRT suppression as a promotable global mechanism, but do not restore native APRT. Preserve `VAPRT = 0` and `VAMPD1 = 1.1x` only as an attribution branch.

- [ ] Resolve ADE/EADE compartment scaling, then test an optional extracellular adenine-loss branch against bounded APRT at fixed kinetics.
  - Reuse the existing transport-scaling contract to express intracellular ADE and extracellular EADE on a common amount basis across a plausible hematocrit/extracellular-volume range.
  - Recompute the direct `VAPRT^T = -d(ADE^T + s_E EADE^T)/dt` profile and its compatibility with the total-adenylate and IMP-derived teachers for every declared scale; do not fit the scale from these same targets.
  - If the teacher conflict persists across plausible scaling, add a reversible option for explicit extracellular adenine loss, `dEADE/dt = VEADE - VEADE_loss`, leaving the current network as the default/revert path.
  - Compare fixed `VAPRT = 0`, bounded positive APRT, and APRT plus EADE-loss hypotheses without kinetic optimization. Guard total adenylate, IMP, ADE, EADE, PRPP, ATP, ADP, AMP, VAK directionality, and the full Brodbar panel.
  - Do not promote a network change until the source-data units, extracellular volume convention, and loss identifiability are documented.

- [ ] If the narrow `VPEP_PASE` pass is insufficient, use `VPFK` only as a secondary conditional lever:
  - `F6P` is the largest accumulation symptom.
  - fixed `VPFK x2` clears `F6P` and improves `LAC`, but does not restore ATP-producing PEP routing.

- [ ] After any candidate improves `GLC` substantially, rerun full Brodbar panel evaluation.

- [ ] Only after Brodbar passes, validate on Michel and Bardyn.

- [ ] Update `manuscript.md` with the FLA iterative calibration results:
  - transport gate success for `EGLC`
  - internal `GLC/LAC` failure revealed by full-panel replay
  - bottleneck search through `VELAC/VLDH`, `VHK`, `km_ATP_HK`, and `VPGI/VPFK`

## Resume Pointer

Start next session by reading:

- `fla_progress_log.md`
- `tasks/fla_current_tasks.md`

Then inspect:

- `Simulations/brodbar/hermes/imp_purine_transfer_vampd1_1p1_vaprt_zero_J1_J46/decision_report.md`
- `Simulations/brodbar/hermes/imp_purine_transfer_vampd1_1p1_vaprt_zero_J1_J46/summary.json`
- `Simulations/brodbar/hermes/imp_purine_transfer_vampd1_1p1_vaprt_zero_J1_J46/window_attribution.csv`
- `Simulations/brodbar/hermes/imp_purine_transfer_vampd1_1p1_vaprt_zero_J1_J46/imp_purine_transfer_audit.png`
- `Simulations/brodbar/hermes/imp_purine_transfer_vampd1_1p1_vaprt_zero_J1_J46/solver_robustness/summary.json`

- `Simulations/brodbar/hermes/vmax_vampd1_vaprt_zero_screen_J1_J46/decision_report.md`
- `Simulations/brodbar/hermes/vmax_vampd1_vaprt_zero_screen_J1_J46/summary.json`
- `Simulations/brodbar/hermes/vmax_vampd1_vaprt_zero_screen_J1_J46/candidate_metrics.csv`
- `Simulations/brodbar/hermes/vmax_vampd1_vaprt_zero_screen_J1_J46/vmax_vampd1_screen.png`
- `Simulations/brodbar/hermes/vmax_vampd1_vaprt_zero_screen_J1_J46/solver_robustness/summary.json`
- `Simulations/brodbar/hermes/vaprt_zero_vampd1_requirement_3x_qss_J1_J3/summary.json`

- `Simulations/brodbar/hermes/vmax_vdpgm_qss_b13pg_pareto_refinement_J1_J46/decision_report.md`
- `Simulations/brodbar/hermes/vmax_vdpgm_qss_b13pg_pareto_refinement_J1_J46/summary.json`
- `Simulations/brodbar/hermes/vmax_vdpgm_qss_b13pg_pareto_refinement_J1_J46/pareto_metrics.csv`
- `Simulations/brodbar/hermes/vmax_vdpgm_qss_b13pg_pareto_refinement_J1_J46/vmax_vdpgm_pareto_refinement.png`
- `Simulations/brodbar/hermes/vmax_vdpgm_qss_b13pg_pareto_refinement_J1_J46/solver_robustness/decision_report.md`

- `Simulations/brodbar/hermes/vmax_vdpgm_qss_b13pg_screen_J1_J46/decision_report.md`
- `Simulations/brodbar/hermes/vmax_vdpgm_qss_b13pg_screen_J1_J46/summary.json`
- `Simulations/brodbar/hermes/vmax_vdpgm_qss_b13pg_screen_J1_J46/candidate_metrics.csv`
- `Simulations/brodbar/hermes/vmax_vdpgm_qss_b13pg_screen_J1_J46/vmax_vdpgm_screen.png`

- `Simulations/brodbar/hermes/b23pg_balance_qss_b13pg_context_J1_J3/decision_report.md`
- `Simulations/brodbar/hermes/b23pg_balance_qss_b13pg_context_J1_J3/summary.json`
- `output/brodbar_data_provenance_2026_08_11/provenance_report.md`
- `output/transport_scaling_audit_2026_08_11/decision_report.md`
- `output/fla_temporal_contract_2026_08_11/decision_report.md`
- `output/fla_identifiability_mask_2026_08_11/decision_report.md`
- `output/fla_identifiability_mask_2026_08_11/parameter_identifiability_mask.csv`

- `output/model_fla_state_audit_2026_08_11/model_fla_state_report.md`
- `output/model_fla_state_audit_2026_08_11/model_fla_state_summary.json`
- `output/model_fla_state_audit_2026_08_11/model_fla_state_overview.png`

- `Simulations/brodbar/hermes/ppp_initial_condition_diagnostic_46d/decision_report.md`
- `Simulations/brodbar/hermes/ppp_initial_condition_diagnostic_46d/summary.json`
- `Simulations/brodbar/hermes/vmax_v6pgd_feasibility_46d/decision_report.md`
- `Simulations/brodbar/hermes/vmax_v6pgd_feasibility_46d/summary.json`
- `Simulations/brodbar/hermes/vmax_v6pgd_feasibility_46d/vmax_v6pgd_feasibility.png`
- `Simulations/brodbar/hermes/vmax_v6pgd_initial_rate_boundary_J1_J2/summary.json`
- `Simulations/brodbar/hermes/vmax_v6pgd_initial_rate_refinement_J1_J2/summary.json`
- `Simulations/brodbar/hermes/vmax_v6pgd_0.020_transfer_46d/decision_report.md`
- `Simulations/brodbar/hermes/vmax_v6pgd_0.020_transfer_46d/summary.json`
- `Simulations/brodbar/hermes/vmax_v6pgd_0.020_current_init_transfer_46d/decision_report.md`
- `Simulations/brodbar/hermes/vmax_v6pgd_0.020_current_init_transfer_46d/summary.json`
- `Simulations/brodbar/hermes/vmax_v6pgd_0.020_current_init_transfer_46d/vmax_v6pgd_feasibility.png`
- `Simulations/brodbar/hermes/gl6p_v6pgd_identifiability_J1_J2/decision_report.md`
- `Simulations/brodbar/hermes/gl6p_v6pgd_identifiability_J1_J2/summary.json`
- `Simulations/brodbar/hermes/gl6p_v6pgd_identifiability_J1_J2/gl6p_v6pgd_identifiability_map.png`
- `Simulations/brodbar/hermes/gl6p_v6pgd_identifiability_J1_J2/gl6p_v6pgd_ridge_replays.png`
- `Simulations/brodbar/hermes/constrained_ppp_initialization_J1_J2/decision_report.md`
- `Simulations/brodbar/hermes/constrained_ppp_initialization_J1_J2/summary.json`
- `Simulations/brodbar/hermes/constrained_ppp_initialization_J1_J2/constrained_initialization_replays.png`
- `Simulations/brodbar/hermes/constrained_ppp_initialization_J1_J2/constrained_initial_states.png`
- `Simulations/brodbar/hermes/v6pgd_constrained_initialization_screen_J1_J2/decision_report.md`
- `Simulations/brodbar/hermes/v6pgd_constrained_initialization_screen_J1_J2/summary.json`
- `Simulations/brodbar/hermes/v6pgd_constrained_initialization_screen_J1_J2/v6pgd_constrained_screen.png`
- `Simulations/brodbar/hermes/v6pgd_constrained_transition_refinement_46d/decision_report.md`
- `Simulations/brodbar/hermes/v6pgd_constrained_transition_refinement_46d/summary.json`
- `Simulations/brodbar/hermes/v6pgd_constrained_transition_refinement_46d/v6pgd_transition_refinement.png`
- `Simulations/brodbar/hermes/f6p_accumulation_v6pgd_0.900_audit_46d/decision_report.md`
- `Simulations/brodbar/hermes/f6p_accumulation_v6pgd_0.900_audit_46d/summary.json`
- `Simulations/brodbar/hermes/f6p_accumulation_v6pgd_0.900_audit_46d/f6p_accumulation_attribution.png`
- `Simulations/brodbar/hermes/atp_transition_v6pgd_0.900_ppp_context_J1_J10/decision_report.md`
- `Simulations/brodbar/hermes/atp_transition_v6pgd_0.900_ppp_context_J1_J10/summary.json`
- `Simulations/brodbar/hermes/atp_transition_v6pgd_0.900_ppp_context_J1_J10/atp_transition_attribution.png`
- `Simulations/brodbar/hermes/b13pg_balance_v6pgd_0.900_ppp_context_J1_J3/decision_report.md`
- `Simulations/brodbar/hermes/b13pg_balance_v6pgd_0.900_ppp_context_J1_J3/summary.json`
- `Simulations/brodbar/hermes/b13pg_balance_v6pgd_0.900_ppp_context_J1_J3/initialization_provenance.json`
- `Simulations/brodbar/hermes/b13pg_balance_v6pgd_0.900_ppp_context_J1_J3/b13pg_balance_provenance.png`
- `Simulations/brodbar/hermes/b13pg_constrained_initialization_screen_J1_J10/decision_report.md`
- `Simulations/brodbar/hermes/b13pg_constrained_initialization_screen_J1_J10/summary.json`
- `Simulations/brodbar/hermes/b13pg_constrained_initialization_screen_J1_J10/diagnostic_initializations.json`
- `Simulations/brodbar/hermes/b13pg_constrained_initialization_screen_J1_J10/b13pg_initialization_screen.png`
- `Simulations/brodbar/hermes/complete_ppp_fla_audit_46d/decision_report.md`
- `Simulations/brodbar/hermes/complete_ppp_fla_audit_46d/summary.json`
- `Simulations/brodbar/hermes/reversible_ppp_directionality_diagnostic_46d/decision_report.md`
- `Simulations/brodbar/hermes/reversible_ppp_directionality_diagnostic_46d/summary.json`
- `Simulations/brodbar/hermes/reversible_ppp_directionality_diagnostic_46d/reversible_ppp_directionality.png`
- `Simulations/brodbar/hermes/investment_phase_flux_matching_46d/decision_report.md`
- `Simulations/brodbar/hermes/investment_phase_flux_matching_46d/summary.json`
- `Simulations/brodbar/hermes/atp_consumption_sink_attribution_46d/decision_report.md`
- `Simulations/brodbar/hermes/atp_consumption_sink_attribution_46d/summary.json`
- `Simulations/brodbar/hermes/km_adp_atp_production_screen_46d/decision_report.md`
- `Simulations/brodbar/hermes/km_adp_atp_production_screen_46d/summary.json`
- `Simulations/brodbar/hermes/km_atp_pfk_feasibility_mild_feedback_46d/decision_report.md`
- `Simulations/brodbar/hermes/km_atp_pfk_feasibility_mild_feedback_46d/summary.json`
- `Simulations/brodbar/hermes/km_nadh_nad_narrow_mild_feedback_46d/decision_report.md`
- `Simulations/brodbar/hermes/km_nadh_nad_narrow_mild_feedback_46d/summary.json`
- `Simulations/brodbar/hermes/glucose_utilization_vhk_atp_46d_n16_upper5/summary.json`
- `Simulations/brodbar/hermes/vhk_atp_lactate_bridge_velac_vldh_46d_n24/summary.json`
- `Simulations/brodbar/hermes/veglc_import_feedback_vhk_atp_seed_46d_n28/summary.json`
- `output/fla_candidate_comparison/fla_candidate_comparison.csv`
- `output/fla_preoptimization_glycolysis_profile/summary.json`
- `output/fla_preoptimization_glycolysis_profile/preoptimization_flux_diagnostic_report.md`
- `output/fla_preoptimization_glycolysis_profile/fixed_one_factor_sensitivity.csv`
- `Simulations/brodbar/hermes/vpep_pase_downward_vhk_atp_mild_feedback_46d_n20/summary.json`
- `Simulations/brodbar/hermes/vpep_pase_downward_vhk_atp_mild_feedback_46d_n20/decision_report.md`
- `output/brodbar_vpep_pase_downward_full_panel/manifest.json`
- `Simulations/brodbar/hermes/vpep_vpk_coupled_mild_feedback_46d_n20/summary.json`
- `Simulations/brodbar/hermes/vpep_vpk_coupled_mild_feedback_46d_n20/decision_report.md`
- `output/brodbar_vpep_vpk_coupled_full_panel/manifest.json`
- `Simulations/brodbar/hermes/transport_gate_eglc_elac_46d_n32_endpoint16/best_params.json`
