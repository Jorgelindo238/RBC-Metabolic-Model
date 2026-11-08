# Flux Learning Analysis (FLA) - Progress Log

## 2026-11-07 - Fixed-parameter reaction-threshold sensitivity

Current handoff: `tasks/fla_reaction_threshold_results_2026_11_07.md`.
Six new original replays plus two reused center replays, thresholds
1e-3/1e-4/1e-5/1e-6 mM, all Vmax/Km/J1/network unchanged. Both solver
profiles pass at 1e-4. At 1e-5 strict fails the concentration check while
ultrastrict passes within -1e-10 mM tolerance; both fail at 1e-6. Three
failures preserved, no clipping/retry. No registered threshold plateau.

Lowering the gate does NOT restore energy: J15 ATP/ADP at 1e-4 are
1.05762e-5/3.83872e-8 mM versus 8.98217e-5/1.77478e-6 at 1e-3. Late
guard failures and negative executed ATP balance remain. The 1e-5 replay
is provisional; saved O2 has a tiny negative value within tolerance, not
an ATP negativity finding. 115 targeted tests; five complete trajectories
independently checked (7,910 balances/28,000 quadratures). No new default,
threshold selected by fit, Vmax calibration or J46 run.

Next: instrument concentration-check failures to retain species/time/minima
and solver diagnostics, then assess low-threshold numerical resolution and
positivity. Do not accept failed states or attribute the whole ATP deficit
to the availability gate.

## 2026-11-07 - PGK/NDPK profile and availability bottleneck

Current handoff: `tasks/fla_pgk_ndpk_profile_results_2026_11_07.md`.
Fixed 5x5 grid plus control: 26 ODE attempts, 24 valid/two rejects.
Other twelve Vmax groups, all Km, network and J1 unchanged. Six new
strict/ultrastrict original replays plus four verified reused controls.
Only the center is guard-feasible in the old box. Lower PGK, higher NDPK,
and the joint out-of-box diagnostic improve ADP but worsen ATP and break
PEP/G6P/F6P/AMP and other guards. No absolute target attained/promotion.

Post-hoc original-state audit: at J15 the 0.001 mM availability gate gives
PGK/PK factor 0.00177478 (ADP limited), versus NDPK factor 0.08982165
(ATP limited). J8-J15 executed/raw PGK integral is only 0.436057%.
This is not an unlimited-ODE prediction or proof of causal ATP rescue.
GDP/GTP are latent, locked at J1=1 mM each. Common NDPK scaling cannot
change its fixed-state zero-flux surface. 105 targeted tests pass;
independent ledgers/convergence checks sealed. No J46 simulation.

Next: fixed-parameter reaction-consistent threshold sensitivity
1e-3/1e-4/1e-5/1e-6 mM at both solver tolerances. Test convergence and
balances, do not fit the numerical threshold to biological measurements.
Keep the GDP/GTP initialization contract separate and unchanged.

## 2026-11-07 - Absolute J15 ATP/ADP target under unchanged dated guards

Current handoff: `tasks/fla_absolute_vmax_results_2026_11_07.md`. Fresh
successor with the same 14 groups/17 Vmax, bounds, exact J1, all Km and
dated PEP/G6P/F6P/AMP caps. Absolute J15 intervals reuse the working bands:
ATP 0.75707-1.27058 mM; ADP 0.31580-0.58548 mM. No budget increase:
80 actual attempts, 75 valid/five numerical rejects; selected trial 76.

Four original replays pass numerical and temporal contracts at both
tolerances. Absolute targets NOT reached: ATP 0.00008982 mM and ADP
0.000001775 mM. Adenylate log-error gains versus fixed control are
6.554/6.777/6.637/6.797%, not biological rescue. PGK reaches its lower
factor bound 0.5; NDPK its upper bound 2.0. Executed J8-J15 ATP production
0.00719648 mM versus consumption 0.00744403 mM; NDPK remains a major
consumer. 97 targeted tests; independent absolute/guard reconstruction
passed. No production promotion or J46 run. Next decision: profile active
PGK/NDPK bounds and adenylate-guanylate balances before increasing search.

## 2026-11-04 - Multi-date Vmax optimization with critical-pool guards

Successor to the J4-only pilot; current handoff:
`tasks/fla_temporal_vmax_results_2026_11_04.md`. Fit J4/J8/J11/J15 by
worst-date adenylate log-error ratio with 16 explicit PEP/G6P/F6P/AMP caps.
17 Vmax in 14 groups, same corrected network and exact Sheet1 J1; all Km
and other settings locked. Of 80 ODE attempts, 71 were numerically valid.
Trial 78 passed. A better-scoring half step failed the PEP J15 cap.

Four original replays pass both tolerances and all dated caps. Log-error
gains: 2.816/3.148/2.900/3.078%. ATP J15 remains 0.00008751 mM versus
1.013827 mM nominal. J8-J15 executed consumption still exceeds production.
82 targeted tests; decision archive includes the absolute Vmax, caps and
signed budgets. No production promotion or J46 replay. Next feasibility
question: can an absolute late ATP/ADP target coexist with the same guards?

## 2026-11-04 - Agentic FLA Vmax-only pilot with paired RBC-GEM context

Current handoff: `tasks/fla_agentic_vmax_results_2026_11_04.md`. Three agents:
executed ATP demand (4400 rows/four starts), four executable GEM columns and
bounded Vmax search. Verified the structural archive after the agent usage
interruption:12 replays/4068 amount balances. OPLAH, all Km, exact55 J1,
latents, transport and production defaults unchanged. Manuscript Methods
addendum `manuscript_agentic_fla_addendum.md`; protected old manuscript/handoff
inputs remain untouched.

Matched14-group/17-capacity searches:256 valid J4 ODE attempts/four cache
hits, no admissible improvement or global-optimum claim. Best energy-only
trial ATP~0.589mM at J4. Same diagnostic Pareto vector in both network modes;
original corrected ATP0.248438/0.335377/0.003348mM at J4/J8/J15. Late log-error
gain76.27%, but PEP/G6P/F6P and AMP guards fail. Early demand falls, J4-J8 net
ATP is positive, and J8-J15 PRPP/NDPK and other demand exceed production.

Four new original J15 replays pass76964 convergence checks. Verify256 fitting
scores/6328 balances/22400 quadratures/36 live checkpoints/440 audit rows;
83 targeted tests. Full tested Vmax table and signed budgets in
`output/agentic_vmax_pilot_decision_2026_11_04/`. No production promotion.
Next: multi-date Vmax-only fitting with explicit metabolic and temporal guards,
not another isolated J4 score search. Not yet run.

## 2026-11-04 - Coupled B13PG supply / AK partition falsification

Reopen770 Sheet1 cells and14 times; confirm exact alias pairs, preserve all55
J1 and do not equate ATP to free substrate. JBC remains separate. Half-step
reference plus GAPDHx1.5 and common forward/reverse AKx0.5 factorial, six new
original J1-J4 replays/two reused controls, PGK unchanged. Coupled PGK after
J2 rises0.202344 ->0.287589mM; J4 ATP0.023747 ->0.056615mM, ADP0.004374 ->
0.033320mM, still far below nominal. Most log-error gain comes from AK alone
(50.66% vs coupled51.21%); subadditive contrast. G6P/F6P/PEP and other guards
reject coupling, independently of ambiguous P3G. No candidate promoted.

Six original profiles and three fast parity checks pass;103839 convergence
checks and21 targeted tests. Reconstructed2712 daily balances,4800 quadrature
checks and440 source comparisons across all case/profile pairs. Report
`tasks/fla_b13pg_ak_coupled_results_2026_11_04.md`. No fit, J46 extension or
source/initial-state change.

## 2026-11-04 - Frozen-flux J1-J4 energy feasibility

All other executed extents fixed, five directional PGK/NDPK/PRPPASe scenarios
at both archived tolerances. The 30 LP primal/dual checks and16 targeted tests
pass. PGK loss1.050879mM in H is attributed to B13PG availability, not an ATP
reserve. J4 B13PG residual permits only0.000134751mM more PGK with supply fixed.
PRPP inventory and ADP cap joint H at0.193544 vs nominal1.616392mM, including
when removing the raw PGK ceiling. Best band multiplier14.6962 is certified
by the AMP lower bound. No lever passes; this is not global ODE infeasibility.

Verified72 separate Yurkovich4C signal records, not paired ATP charge or a
calibration anchor. Source/latent J1 exact; dense J1 interpolation roundoff
1.11e-16mM explicitly distinguished. No ODE or new kinetic fit. Report
`tasks/fla_j1_j4_energy_results_2026_11_04.md`, archive
`output/j1_j4_energy_feasibility_2026_11_04/`. Retain structural/source and
coupled upstream-supply questions before wider calibration.

## 2026-11-04 - Unforced VSAM/PGK half-step replay through J46

Two original J1-J46 integrations with only the sealed half-step overrides,
matched against two archived reference profiles. Full measured/latent J1
unchanged. Both tolerance profiles pass all55/adenylate guards in the early,
late and combined windows. Late log-adenylate gain0.259646% in ultrastrict;
whole-window0.290459%. Twenty late raw RMSEs rise within engineering limits.
ATP J46 1.782852e-5 versus reference1.774790e-5 and nominal0.469757mM.
Late executed ATP net balance is about4.74e-7mM more negative, eroding most of
the small J15 advantage. No evidence of energetic recovery.

Pass10170 daily balances,9000 each raw/executed quadrature checks,46403
convergence comparisons and34 targeted tests. Verify36 live checkpoints,
330 pool/window rows and1540 sample rows. Report
`tasks/fla_vsam_pgk_j46_results_2026_11_04.md`. Keep as conditional comparator;
no optimization, active branch, default change, or independent validation.

## 2026-11-04 - Small VSAM/PGK interaction screen completed

Registered five fixed points, exact55 J1/latent states and native network.
Four original joint replays and two fast parity integrations, six reused
original controls. The half-step at VSAM0.19518001458970666 and
PGK39.17685218740367 passes all55 engineering bands, pointwise adenylate
and gain criteria in both tolerances. Mean log-adenylate gain0.3830%.
Full joint gains0.7586% but fails AMP; VSAM-only also fails AMP, PGK-only
fails the new ADP J4 guard. Baseline remains the best admissible control.
Four-corner effect nearly additive. Half-step raises16/55 raw RMSEs at
ultrastrict within allowances, notably AMP and B23PG.

ATP J15 remains8.390680e-5mM versus nominal1.0138273mM. Lower VSAM demand is
offset by reduced PGK production, increased net NDPK demand and other flux
responses. No biological rescue. All6328 new daily balances,5600 each raw and
executed quadrature and76338 cross-tolerance checks pass. Verify550 channel
rows/1000 reaction rows and70 live checkpoints;30 targeted tests pass.
Report `tasks/fla_vsam_pgk_screen_2026_11_04.md`, immutable archive
`output/vsam_pgk_screen_2026_11_04/`, verification/conditional replay override
`output/vsam_pgk_screen_validation_2026_11_04/`. No optimizer, new active branch,
source/IC change or promotion. Next proposed, not run: matched J46 free replay
of the half-step, before any expanded search. J46 is not blind validation.

## 2026-11-03 - Network-observation coverage and adenylate sensitivity completed

User priority executed against conditional J15_normalized baseline; protocol
`tasks/fla_coverage_adenylate_sensitivity_2026_11_03.md`, immutable archive
`output/coverage_adenylate_sensitivity_2026_11_03/`, independent receipts and
three visually inspected figures in
`output/coverage_adenylate_sensitivity_validation_2026_11_03/`.

Pinned GEM1.3.0 commit43fd381d9eb8a8a4079629012362312960e1c009 supports
closed citrate lyase/arginase projections. New isolated CoverageRHS options
require explicit Km/Vmax and default to ZERO; native exact rollback and OPLAH
are retained. Neither option was activated in real-data ODE runs. CITR remains
static; no invented sink or missing-NO shortcut. All55 channels have explicit
roles, not silent removal. Source normalization/pool identities remain conditional.

Eight LPs: historical J15/J46 multipliers1.661963/2.804155, citrate-only or
both0.781803/1.216622, arginase-only unchanged. Projected ranks50/51/52 do not
prove dynamic feasibility. Separate registered ARGSL structural follow-up adds
ARGSUC <-> ARG+FUM and reduces multipliers0.344415/0.479320 at unchanged rank52.
Unmeasured ARGSUC inventory remains relaxed; no ASL rate law/ODE added. Maximal
lower bounds among48 certificates match all ten primal minima (gap<=8.89e-16). Static CITR remains
the lower-bound bottleneck, but nominal variation within engineering bands is
not evidence of activity above unknown assay noise. Constant physical H cannot
conserve nominal amounts in8/13 citrate and5/13 arginine intervals; diagnostic
H is not fitted/measured. Original Deep Red ACLY/ARG1/ASL/ASS1/ANKH rows/F/G
reopened. ASS1 is detected but absent from pinned GEM: retain curation conflict,
not absence/kinetic evidence. Protein abundance does not establish activity4C.

Twenty-five positive parameters, four log finite-difference offsets per parameter,
101 valid actual J1-J15 ODEs; APRT/AMP_NT zero capacities stay closed. Four real
observation times,12 log-adenylate outputs, rank12 at1e-6, at least13 unresolved
local directions and45 highly correlated pairs. Two-step disagreement maximum
0.0106845 below0.25. Strong PRPPASe/shared km_ATP/forward AK effects fail other
pool protections. Selected single levers VSAM0.2 ->0.1904761905 and
PGK40.14432755 ->38.23269291 reduce aggregate log error0.5385%/0.2229%.
Both pass original strict/ultrastrict numerical and admission checks; not a
joint subset or fitted constants. PGK-down slightly lowers ATP J15. VSAM ATP
demand reduction0.00907749mM is compensated by other pathways. ATP remains
about8.3e-5mM at J15 versus nominal1.0138273mM. Other44 raw RMSE increases
18/27 channels respectively, not significance tests or all-pool non-regression.

Four original replays pass76338 convergence,6328 daily-balance and5600 each
raw/executed quadrature checks; checked minima0mM. Primary3045/secondary1708
checks,165 source metric rows/42 signed budgets; all770 cells/55 J1 and latents
exact. Full QA1433 passed/two existing skips/six existing Optuna warnings.
Supplemental verifier first attempted day15.0 filename; corrected integer label
before its first successful receipt, without changing frozen scientific inputs.
Manuscript methods2.53/results3.53 updated. No optimizer, new active branch,
J46 sensitivity selection, joint replay, default promotion or biological rescue.

Next proposed, NOT RUN: small registered two-coordinate VSAM/PGK feasibility
screen with timewise adenylates and all55 source channels. Keep network branches
off until kinetics/temperature/latent-stock contracts are justified; recompute
sensitivities if activated. Full physical network-observation coherence is open.

## 2026-11-03 - Priority objective reformulation for automated research-group calibration

Ultimate goal reaffirmed: groups should calibrate blood-bag/RBC dynamics from
their own absolute or relative intra/extracellular metabolomics. Deliver an
explicit observation-contract core first, not a claim of arbitrary-file ingestion
or automatic absolute mM inference from unresolved relative intensities. Preserve
source/cohort/trajectory keys, unknown donors and phase reference litres.

Protocol `tasks/fla_objective_reformulation_2026_11_03.md`, frozen archive
`output/fla_objective_reformulation_2026_11_03/`.27 new tests pass before freeze;
parent1123 checks verified. Compare NLL/normalized/minimax on identical22 J4/J8
values and two HK/PFK coordinates, two starts each. Old13 caps explicitly
diagnostic for ALL refits. Fixed5%-median/20%-relative scales are engineering,
not assay uncertainty. No clipping/teacher double counting or extra costs.

Execute six necessary LP screens and eight fits, including gated J1-J15 actual44
values. All optimizers converge:52/18 NLL,40/21 normalized,37/16 minimax at J10;
8/16 at J15.208 actual objective integrations including derivatives. HK hits0.1
lower search bound; no parameter identification/global optimum claim.

Exact nominal LP systems fail; eleven-channel multipliers0.016542/0.016779/
0.023310, canonical53 multipliers0.959227/1.661963/2.804155 at J8/J15/J46.
Supplemental certificates explain minima: nonincreasing GLC+0.724138EGLC and
constant CIT+0.724138ECIT. Other imposed invariants: constant CITR and constant
ARG+0.724138EARG. Nominal sources contradict these constraints under current
volume assumptions. Analytic lower bounds match feasible primal LP witnesses.
This proves these relaxation optima only, not kinetic/ODE feasibility or unique
reconstructed trajectories. Do not auto-add drains to fit invariant violations.

Five extra certificate tests and expanded full QA1411 passed/two existing skips/
six existing Optuna warnings in122.68seconds. All seven original strict/ultrastrict
audit pairs now pass278617 convergence comparisons,32770 daily executed balances
and29000 raw/29000 executed quadrature comparisons; checked minima0mM. Independent
primary2299 checks and secondary1444 checks pass. Secondary verifies21 analytic
certificates and all six relaxation optima (max gap2.22e-16),275 pool/comparator
rows and35 signed budgets (max difference9.77e-15mM). Both manifests validate
(real11 channels and synthetic mixed3), not as completed relative ODE calibrations.

Outcome: refitted NLL/normalized/minimax mean working MSE129.687654/37.494381/
68.215816; worst1016.534072/343.776200/339.304298 on identical22 values. The old
guarded split gives mean42.558139/worst346.142575 but has a different constraint
contract, so it is a historical comparator rather than a matched loss ablation.
Minimax barely improves AMP343.776 ->339.304 while worsening F6P0.156857 ->
339.304; reject naked minimax as default. Normalized mean better retains F6P,
but no candidate meets all working targets and all fail a historical diagnostic
guard. No cost alone solves the adenylate partition. J15 continuation also
remains inaccurate; J46 normalized/minimax ATP1.77479e-5/1.79867e-5mM,
GLC6.968671/6.956652 and F6P0.181296/0.757990. No biological promotion.

Automated `readiness.json` explicitly returns numerical success, unmet fit
targets, bound hits and source/model conflicts without declaring calibration.
Three generated PNGs visually inspected. Source/GEM-informed coverage of citrate,
arginine and CITR, with normalization/binding/volume/cohort alternatives, is next;
then sensitivity-directed adenylate parameter selection, not another HK/PFK-only
search. Do not insert sinks to explain conservation failures. Raw time/storage
mapping, assay covariance, censoring, anchored relative uncertainty and full
initialization remain platform adapters; multiple shooting and conditional Vmax
projection are not implemented here. Manuscript methods2.52/results3.52 and
active handoff updated. No network/default/source/IC or persistent-memory-folder
edit, commit/push or dependency install. All needed jobs have ended.

Last updated: 2026-11-03

## Working Concept

Flux Learning Analysis (FLA) is the current calibration methodology for the AIRBC/RBC ODE model. The principle is:

1. Recover teacher fluxes from experimental concentration curves.
2. Use those fluxes to calibrate kinetic constants.
3. Reinject the learned constants into the ODE model.
4. Evaluate the resulting simulation against concentration and flux targets.

This is developed as an analogue to Flux Balance Analysis, but focused on learning executable kinetic parameters for the ODE model.

## Current Main Dataset Strategy

Brodbar remains the main training dataset because it is the most consistent with the current AIRBC model structure.

Michel and Bardyn should be used as validation/transfer datasets, not as naive mixed training data yet.

## Phase A Artifacts

Phase A builds extracellular teacher fluxes from Brodbar extracellular metabolite curves.

Key file:

- `src/extracellular_teacher_flux.py`

Important behavior:

- Converts extracellular concentration derivatives into reaction fluxes.
- Supports `EGLC -> VEGLC` and `ELAC -> VELAC`.
- Also supports the broader extracellular Brodbar panel.
- Includes degradation correction logic for `EGSH` and `EGSSG`.

## Phase B/Transport Learning

Initial transport-only calibration with only `vmax_VEGLC` and `vmax_VELAC` was not sufficient.

Run:

- `Simulations/brodbar/hermes/transport_only_fla_eglc_elac_46d_direct_cost_n12`

Result:

- Best direct loss improved only slightly: `14.97 -> 14.43`
- `EGLC` depletion stayed too low: about `1.71%`
- Candidate was not promoted because it failed the `EGLC` depletion gate.

Conclusion:

- Changing only `vmax_VEGLC` and `vmax_VELAC` cannot fix the Brodbar glucose slope/endpoint.
- The issue is structural in the glucose transport kinetics.

## Tested VEGLC Kinetic Families

The runner `scripts/run_transport_only_fla_eglc_elac.py` now supports:

- `mm_bidirectional`
- `hybrid_asymmetric_transport`
- `transport_depletion_gate`

This is reversible. The global `Simulations/brodbar/calibration/best_params.json` was not overwritten.

Each run writes:

- `seed_params.json`
- `candidate_params.json`
- `promoted_or_seed_params.json`
- `best_params.json` only if accepted
- `summary.json`
- `optimization_trials.csv`
- `best_trajectory_eglc_elac.csv`
- `transport_only_fla_eglc_elac.png`

## Family Pilot Results

Comparison CSV:

- `Simulations/brodbar/hermes/transport_family_eglc_elac_46d_comparison.csv`

### `hybrid_asymmetric_transport`

Run:

- `Simulations/brodbar/hermes/transport_family_hybrid_asymmetric_eglc_elac_46d_n6`

Result:

- Accepted: yes
- Loss: `14.98 -> 13.36`
- `EGLC` depletion: `1.72% -> 12.08%`
- `EGLC` final: `24.90 -> 22.28 mM`, experimental `12.92 mM`

Conclusion:

- Better than `vmax_only`, but not enough for endpoint `EGLC`.

### `transport_depletion_gate` Pilot

Run:

- `Simulations/brodbar/hermes/transport_family_depletion_gate_eglc_elac_46d_n6`

Result:

- Accepted: yes
- Loss: `14.98 -> 12.65`
- `EGLC` depletion: `1.72% -> 10.62%`
- `EGLC` final: `24.90 -> 22.65 mM`, experimental `12.92 mM`

Conclusion:

- Better than `hybrid_asymmetric_transport` under the pilot settings.
- Still insufficient for final `EGLC`.

## Best Current Transport Candidate

Best current candidate is from the stronger `transport_depletion_gate` run with endpoint EGLC reinforced.

Run:

- `Simulations/brodbar/hermes/transport_gate_eglc_elac_46d_n32_endpoint16`

Key command:

```powershell
python -u scripts/run_transport_only_fla_eglc_elac.py --out-dir Simulations/brodbar/hermes/transport_gate_eglc_elac_46d_n32_endpoint16 --params Simulations/brodbar/calibration/best_params.json --veglc-family transport_depletion_gate --n-trials 32 --global-trials 4 --t-max 46 --teacher-dense-points 80 --eglc-slope-weight 4 --eglc-endpoint-weight 16 --elac-endpoint-weight 2 --teacher-flux-weight 3 --eglc-teacher-weight 8 --elac-teacher-weight 3 --min-eglc-depletion-frac 0.05
```

Artifacts:

- `Simulations/brodbar/hermes/transport_gate_eglc_elac_46d_n32_endpoint16/summary.json`
- `Simulations/brodbar/hermes/transport_gate_eglc_elac_46d_n32_endpoint16/best_params.json`
- `Simulations/brodbar/hermes/transport_gate_eglc_elac_46d_n32_endpoint16/seed_params.json`
- `Simulations/brodbar/hermes/transport_gate_eglc_elac_46d_n32_endpoint16/optimization_trials.csv`
- `Simulations/brodbar/hermes/transport_gate_eglc_elac_46d_n32_endpoint16/transport_only_fla_eglc_elac.png`

Result:

- Accepted: yes
- Direct loss: `23.72 -> 7.31`
- `EGLC` depletion: `1.72% -> 47.88%`
- `EGLC` final: `24.90 -> 13.21 mM`, experimental `12.92 mM`
- `ELAC` final: `15.70 -> 19.88 mM`, experimental `28.36 mM`
- `VEGLC` flux nRMSE: `0.945`
- `VELAC` flux nRMSE: `0.527`

Best parameters:

```json
{
  "kinetic_family_VEGLC": "transport_depletion_gate",
  "hybrid_blend_VEGLC": 1.0,
  "vmax_VEGLC": 2.067269073921101,
  "km_EGLC": 23.50088375077599,
  "km_GLC_transport": 3.4913742400037897,
  "hybrid_import_hill_VEGLC": 1.5626476439777552,
  "hybrid_export_hill_VEGLC": 2.6501351192133322,
  "hybrid_reverse_scale_VEGLC": 0.13597358973045603,
  "transport_gate_km_VEGLC": 12.109941368076742,
  "transport_gate_hill_VEGLC": 2.1908880805405633,
  "vmax_VELAC": 1.7248780391917855
}
```

Interpretation:

- This is the first candidate that substantially fixes the Brodbar `EGLC` endpoint and slope.
- `ELAC` remains underproduced/underexported relative to Brodbar, so the next pass should not only focus on glucose.
- Keep this candidate as the current best hypothesis, but do not overwrite the global calibration yet.

## Reversibility

Global baseline parameters remain:

- `Simulations/brodbar/calibration/best_params.json`

The current best candidate is isolated at:

- `Simulations/brodbar/hermes/transport_gate_eglc_elac_46d_n32_endpoint16/best_params.json`

The seed for rollback is also copied at:

- `Simulations/brodbar/hermes/transport_gate_eglc_elac_46d_n32_endpoint16/seed_params.json`

## Full Brodbar Panel Evaluation of VEGLC Candidate

Run:

- `output/brodbar_transport_gate_full_panel`

Script:

- `scripts/evaluate_brodbar_candidate_full_panel.py`

Result:

- Mapped Brodbar metabolites: `55`
- Mean nRMSE: baseline `7.081` -> candidate `7.230`
- Median nRMSE: baseline `0.889` -> candidate `0.915`
- Improved metabolites: `2`
- Regressed metabolites: `2`
- Similar metabolites: `51`

Main improvements:

- `EGLC`: nRMSE `0.404 -> 0.101`; final `24.90 -> 13.21 mM`, experimental `12.92 mM`.
- `ELAC`: nRMSE `0.552 -> 0.330`; final `15.70 -> 19.88 mM`, experimental `28.36 mM`.

Main regressions:

- `GLC`: nRMSE `0.358 -> 8.281`; intracellular glucose accumulates to about `12.40 mM` while Brodbar remains near `0.83 mM`.
- `LAC`: nRMSE `0.216 -> 0.957`; intracellular lactate collapses to about `0.17 mM` while Brodbar ends near `6.46 mM`.

Decision:

- Keep the candidate as a strong `VEGLC` transport hypothesis.
- Do not globally promote it because the full ODE replay breaks internal `GLC/LAC` balance.

## Lactate-Focused FLA Pass After VEGLC Candidate

Run:

- `Simulations/brodbar/hermes/lactate_focused_velac_vldh_46d_n36`

Script:

- `scripts/run_lactate_focused_fla.py`

Method:

- Seeded from `transport_gate_eglc_elac_46d_n32_endpoint16/best_params.json`.
- Kept the `VEGLC` `transport_depletion_gate` candidate fixed.
- Activated reversible/hybrid families for `VELAC` and `VLDH`.
- Optimized `VELAC` and `VLDH` parameters over a 46-day horizon.
- Used direct `VELAC` teacher flux from `ELAC`.
- Built indirect `VLDH` teacher flux from the experimental lactate balance:
  `VLDH_teacher = dLAC_exp/dt + VELAC_teacher`.
- Penalized concentration fit, endpoints, slopes, teacher fluxes, and guardrails on `EGLC`, `GLC`, `LAC`, and `PYR`.

Best candidate:

- Accepted/promoted: no
- Focused loss: seed `11.020` -> candidate `10.565`
- Rejection reason: internal `LAC` nRMSE regressed beyond the guard.

Key metric changes:

- `EGLC`: nRMSE `0.101 -> 0.101`; endpoint preserved.
- `ELAC`: nRMSE `0.330 -> 0.227`; endpoint error `0.299 -> 0.270`.
- `GLC`: nRMSE `8.281 -> 8.245`; still severely wrong.
- `LAC`: nRMSE `0.957 -> 1.029`; still too low and slightly worse.
- `PYR`: nRMSE `2.473 -> 1.670`; improved.
- `VELAC` flux nRMSE: `0.526 -> 0.408`.
- `VLDH` flux nRMSE: `0.680 -> 0.597`.

Best candidate parameter highlights:

```json
{
  "kinetic_family_VELAC": "hybrid_reversible_transport",
  "kinetic_family_VLDH": "hybrid_reversible_redox",
  "vmax_VELAC": 2.8977951058422,
  "km_LAC": 2.27154035346914,
  "hybrid_blend_VELAC": 0.59,
  "vmax_VLDH": 1.5308076567526945,
  "km_PYR": 0.22503964702545765,
  "hybrid_blend_VLDH": 0.59,
  "hybrid_reverse_scale_VLDH": 0.0
}
```

Interpretation:

- `VELAC/VLDH` can improve extracellular lactate and teacher-flux alignment.
- Some explored candidates strongly improve internal `LAC`, but they degrade `ELAC` endpoint and flux fit.
- The internal `GLC` failure is nearly unchanged across the lactate-focused pass, consistent with the equation `dGLC/dt = VEGLC - VHK`.
- The next structural bottleneck is likely glucose phosphorylation/entry handling, not lactate export alone.

## Recommended Next Step

Do not promote the lactate-focused candidate.

## Glucose-Utilization FLA Pass After VEGLC Candidate

Run:

- `Simulations/brodbar/hermes/glucose_utilization_vhk_46d_n24`

Script:

- `scripts/run_glucose_utilization_fla.py`

Method:

- Seeded from `transport_gate_eglc_elac_46d_n32_endpoint16/best_params.json`.
- Kept the `VEGLC` `transport_depletion_gate` candidate fixed.
- Opened only:
  - `vmax_VHK`
  - `km_GLC_HK`
- Used the same Brodbar 46-day horizon.
- Reused direct `VELAC` teacher flux and inferred `VLDH` teacher flux.
- Applied strong guardrails on `EGLC`, `GLC`, `LAC`, `ELAC`, `VELAC`, and `VLDH`.

Best candidate:

- Accepted/promoted: no
- Focused loss: seed `38.356` -> candidate `34.401`
- Rejection reason: internal `GLC` nRMSE did not improve by at least `25%`.

Best candidate parameters:

```json
{
  "vmax_VHK": 3.356007460035566,
  "km_GLC_HK": 0.00975602557649102
}
```

Key metric changes:

- `EGLC`: nRMSE `0.101 -> 0.113`; endpoint error `0.0225 -> 0.0119`, so endpoint remains protected.
- `ELAC`: nRMSE `0.330 -> 0.311`; endpoint error `0.299 -> 0.251`.
- `GLC`: nRMSE `8.281 -> 7.166`; final `12.40 -> 10.97 mM`, experimental `0.826 mM`.
- `LAC`: nRMSE `0.957 -> 0.937`; final `0.166 -> 0.229 mM`, experimental `6.463 mM`.
- `PYR`: nRMSE `2.473 -> 2.370`; endpoint error `1.012 -> 0.797`.
- `VELAC` flux nRMSE: `0.526 -> 0.510`.
- `VLDH` flux nRMSE: `0.680 -> 0.655`.

Interpretation:

- Opening `VHK/km_GLC_HK` helps in the expected direction and does not break the lactate/extracellular guards.
- The best candidate sits at the local upper bound for `vmax_VHK`, indicating that the pass is capacity-limited.
- The improvement in `GLC` is real but incomplete: intracellular glucose remains far too high.
- `km_GLC_HK` is not the main lever in the tested range; `vmax_VHK` dominates.
- This supports the structural diagnosis `dGLC/dt = VEGLC - VHK`, but shows that `VHK` alone is not enough under the current bound.

## Recommended Next Step

Do not promote the VHK-only candidate.

The next pass should keep the accepted `VEGLC` transport gate hypothesis available and test whether the remaining internal glucose accumulation is a simple VHK capacity ceiling or a downstream glycolysis bottleneck:

1. Preserve `EGLC` endpoint/slope with strong guardrails.
2. Run a short expanded-bound VHK test allowing `vmax_VHK` to reach the global upper bound `5.0`.
3. If `GLC` still remains high, open a very small downstream seam: `VHK + VPGI/VPFK` or `VHK + km_ATP_HK`.
4. Keep `VELAC/VLDH` as guardrail fluxes, not as free parameters, during the next glucose-utilization pass.
5. Compare four candidates side by side:
   - `VEGLC` transport gate seed.
   - `VEGLC + VELAC/VLDH` lactate candidate.
   - `VEGLC + VHK` glucose-utilization candidate.
   - `VEGLC + expanded VHK` or `VEGLC + VHK/downstream` candidate.

## Expanded VHK and Downstream Glucose-Utilization Tests

Script:

- `scripts/run_glucose_utilization_fla.py`

The runner now supports multiple parameter modes:

- `vhk_km`: `vmax_VHK + km_GLC_HK`
- `vhk_only`: `vmax_VHK` only
- `vhk_atp`: `vmax_VHK + km_ATP_HK`
- `vhk_pgi_pfk`: `vmax_VHK + vmax_VPGI + vmax_VPFK`

### Expanded `vmax_VHK` Only

Run:

- `Simulations/brodbar/hermes/glucose_utilization_vhk_only_46d_n14_upper5`

Method:

- Kept `VEGLC` transport gate fixed.
- Kept `km_GLC_HK` fixed.
- Opened only `vmax_VHK` up to global upper bound `5.0`.

Best candidate:

- Accepted/promoted: no
- Focused loss: seed `38.356` -> candidate `34.272`
- Best parameter: `vmax_VHK = 5.0`
- Rejection reason: internal `GLC` nRMSE did not improve by at least `25%`.

Key metric changes:

- `EGLC`: nRMSE `0.101 -> 0.114`; endpoint error `0.0225 -> 0.0105`.
- `ELAC`: nRMSE `0.330 -> 0.314`.
- `GLC`: nRMSE `8.281 -> 7.023`; final `12.40 -> 10.77 mM`, experimental `0.826 mM`.
- `LAC`: nRMSE `0.957 -> 0.941`.
- `PYR`: nRMSE `2.473 -> 2.367`.
- `VELAC` flux nRMSE: `0.526 -> 0.510`.
- `VLDH` flux nRMSE: `0.680 -> 0.658`.

Interpretation:

- The optimum hits the global `vmax_VHK` ceiling.
- Expanded VHK improves glucose utilization but still leaves severe intracellular `GLC` accumulation.

### `VHK + km_ATP_HK`

Run:

- `Simulations/brodbar/hermes/glucose_utilization_vhk_atp_46d_n16_upper5`

Method:

- Kept `VEGLC` transport gate fixed.
- Opened `vmax_VHK` up to `5.0`.
- Opened `km_ATP_HK` to test whether ATP affinity limits VHK.

Best candidate:

- Accepted/promoted: no
- Focused loss: seed `38.356` -> candidate `31.644`
- Best parameters:

```json
{
  "vmax_VHK": 5.0,
  "km_ATP_HK": 0.06014413339486139
}
```

Key metric changes:

- `EGLC`: nRMSE `0.101 -> 0.119`; endpoint error `0.0225 -> 0.0028`.
- `ELAC`: nRMSE `0.330 -> 0.323`.
- `GLC`: nRMSE `8.281 -> 6.302`; final `12.40 -> 9.75 mM`, experimental `0.826 mM`.
- `LAC`: nRMSE `0.957 -> 0.950`.
- `PYR`: nRMSE `2.473 -> 2.356`.
- `VELAC` flux nRMSE: `0.526 -> 0.518`.
- `VLDH` flux nRMSE: `0.680 -> 0.670`.

Interpretation:

- This is the best glucose-utilization candidate so far.
- Lowering `km_ATP_HK` helps beyond `vmax_VHK` alone, so ATP affinity is part of the bottleneck.
- The candidate still fails promotion because `GLC` remains far too high.

### `VHK + VPGI/VPFK`

Run:

- `Simulations/brodbar/hermes/glucose_utilization_vhk_pgi_pfk_46d_n14_upper5`

Method:

- Kept `VEGLC` transport gate fixed.
- Opened `vmax_VHK`, `vmax_VPGI`, and `vmax_VPFK`.
- Added explicit conservative bounds for `vmax_VPGI` because it exists in the ODE but not in `PHASE1_PARAMS`.

Best candidate:

- Accepted/promoted: no
- Focused loss: seed `38.356` -> candidate `33.830`
- Best parameters:

```json
{
  "vmax_VHK": 5.0,
  "vmax_VPGI": 0.08284419069850739,
  "vmax_VPFK": 1.050565374185168
}
```

Rejection reasons:

- Internal `GLC` nRMSE did not improve by at least `25%`.
- `ELAC` nRMSE regressed beyond the guard.
- `VELAC` teacher-flux guard failed.

Key metric changes:

- `GLC`: nRMSE `8.281 -> 6.769`; final `12.40 -> 10.50 mM`.
- `ELAC`: nRMSE `0.330 -> 0.385`, worse.
- `LAC`: nRMSE `0.957 -> 0.986`, worse.
- `VELAC` flux nRMSE: `0.526 -> 0.569`, worse.

Interpretation:

- `VPGI/VPFK` does not beat `VHK + km_ATP_HK`.
- It is riskier for extracellular lactate and teacher flux.

## Current Decision

Do not promote any glucose-utilization candidate yet.

Ranked hypotheses:

1. Best partial candidate: `VEGLC gate + vmax_VHK=5.0 + lower km_ATP_HK`.
2. Useful but weaker: `VEGLC gate + vmax_VHK=5.0`.
3. Disfavored for now: `VEGLC gate + VHK/VPGI/VPFK`, because it worsens `ELAC` and `VELAC`.

Next recommended pass:

- Keep the best partial `VHK + km_ATP_HK` result as a diagnostic candidate, not a promoted parameter set.
- Open the glucose-utilization/lactate-production bridge directly: `VHK + km_ATP_HK + VLDH/VELAC` with tight guardrails, or test a controlled `VEGLC` import cap/feedback because the current gate may be importing more glucose than downstream glycolysis can safely process.

## Compact Candidate Comparison

Run:

- `output/fla_candidate_comparison`

Script:

- `scripts/compare_fla_candidates.py`

Artifacts:

- `output/fla_candidate_comparison/fla_candidate_comparison.csv`
- `output/fla_candidate_comparison/fla_candidate_comparison.png`
- `output/fla_candidate_comparison/manifest.json`

Compared candidates:

- `VEGLC` gate seed.
- `VHK only upper5`.
- `VHK + km_ATP_HK`.
- `VHK + VPGI/VPFK`.
- Previous `VELAC/VLDH` lactate candidate.

Key comparison:

| Candidate | GLC nRMSE | ELAC nRMSE | LAC nRMSE | VELAC flux nRMSE | VLDH flux nRMSE |
| --- | ---: | ---: | ---: | ---: | ---: |
| `VEGLC` gate seed | 8.281 | 0.330 | 0.957 | 0.526 | 0.680 |
| `VHK only upper5` | 7.023 | 0.314 | 0.941 | 0.510 | 0.658 |
| `VHK + km_ATP_HK` | 6.302 | 0.323 | 0.950 | 0.518 | 0.670 |
| `VHK + VPGI/VPFK` | 6.769 | 0.385 | 0.986 | 0.569 | 0.713 |
| `VELAC/VLDH` | 8.245 | 0.227 | 1.029 | 0.408 | 0.597 |

Interpretation:

- `VHK + km_ATP_HK` remains the best partial glucose-utilization diagnostic.
- `VELAC/VLDH` remains the best lactate/flux diagnostic, but it does not solve internal glucose and worsens internal lactate.
- `VHK + VPGI/VPFK` remains disfavored because it regresses `ELAC` and teacher-flux guardrails.

## Bridge Pass: `VHK + km_ATP_HK` Seed, Then `VELAC/VLDH`

Run:

- `Simulations/brodbar/hermes/vhk_atp_lactate_bridge_velac_vldh_46d_n24`

Script:

- `scripts/run_lactate_focused_fla.py`

Method:

- Seeded from `Simulations/brodbar/hermes/glucose_utilization_vhk_atp_46d_n16_upper5/candidate_params.json`.
- Kept the `VEGLC` transport gate and the `VHK/km_ATP_HK` diagnostic constants in the seed.
- Opened only `VELAC` and `VLDH` hybrid/reversible parameters.
- Used a 46-day Brodbar horizon.
- Increased teacher-flux pressure on `VELAC/VLDH` while preserving guardrails on `EGLC`, `ELAC`, `GLC`, `LAC`, and `PYR`.

Best candidate:

- Accepted/promoted: no
- Focused loss: seed `10.708` -> candidate `10.178`
- Rejection reason: internal `LAC` nRMSE regressed beyond the guard.

Best parameter highlights:

```json
{
  "vmax_VELAC": 3.725736564654257,
  "km_LAC": 2.9205518830317514,
  "hybrid_blend_VELAC": 0.83,
  "vmax_VLDH": 1.96818127296775,
  "km_PYR": 0.28933668903273124,
  "km_NADH_NAD": 9.919130547576357,
  "km_NAD_NADH": 2.292053729588075,
  "hybrid_blend_VLDH": 0.83,
  "hybrid_reverse_scale_VLDH": 0.0
}
```

Key metric changes:

- `EGLC`: nRMSE `0.119 -> 0.121`; endpoint error `0.0028 -> 0.0014`.
- `ELAC`: nRMSE `0.323 -> 0.210`; final `20.37 -> 21.36 mM`, experimental `28.36 mM`.
- `GLC`: nRMSE `6.302 -> 6.217`; final `9.745 -> 9.744 mM`, experimental `0.826 mM`.
- `LAC`: nRMSE `0.950 -> 1.027`; final `0.203 -> 0.080 mM`, experimental `6.463 mM`.
- `PYR`: nRMSE `2.356 -> 1.580`; endpoint error `0.678 -> 0.212`.
- `VELAC` flux nRMSE: `0.518 -> 0.383`.
- `VLDH` flux nRMSE: `0.670 -> 0.583`.

Interpretation:

- The bridge pass improves extracellular lactate, `VELAC/VLDH` teacher-flux alignment, and pyruvate.
- It leaves intracellular glucose essentially stuck near `9.74 mM`.
- It worsens the already depleted intracellular lactate state.
- This rejects the simple hypothesis that opening lactate export/redox after `VHK + km_ATP_HK` can repair the internal glucose-lactate imbalance.

Decision:

- Do not promote the bridge candidate.
- The next logical test is a controlled `VEGLC` import cap/feedback, because the current `transport_depletion_gate` likely imports more glucose than the internal glycolytic network can process.

## Controlled `VEGLC` Import Cap/Feedback Test

Code changes:

- Added a reversible `VEGLC` kinetic family:
  - `transport_depletion_gate_import_feedback`
- The original `transport_depletion_gate` family is unchanged.
- New parameters:
  - `transport_gate_feedback_strength_VEGLC`
  - `transport_gate_feedback_km_GLC_VEGLC`
  - `transport_gate_feedback_hill_VEGLC`
  - `transport_gate_import_cap_VEGLC`
- Added runner:
  - `scripts/run_veglc_import_feedback_fla.py`

Run:

- `Simulations/brodbar/hermes/veglc_import_feedback_vhk_atp_seed_46d_n28`

Method:

- Seeded from `Simulations/brodbar/hermes/glucose_utilization_vhk_atp_46d_n16_upper5/candidate_params.json`.
- Kept `VHK + km_ATP_HK` fixed from the best glucose-utilization diagnostic.
- Activated `transport_depletion_gate_import_feedback` only for this candidate run.
- Opened only `VEGLC` transport-shape parameters and the new import cap/feedback parameters.
- Used 46-day Brodbar horizon.
- Included concentration targets `EGLC`, `ELAC`, `GLC`, `LAC`, `PYR`.
- Included teacher-flux targets `VEGLC`, `VELAC`, `VLDH`.
- Kept hard guardrails on `EGLC` endpoint/slope and `VEGLC` teacher flux.

Neutral family check:

- The family-neutral seed exactly matched the original seed:
  - seed loss `35.955`
  - family-neutral loss `35.955`
  - `GLC` nRMSE `6.301`
  - `EGLC` endpoint error `0.0028`

Best candidate:

- Accepted/promoted: no
- Focused loss: `35.955 -> 34.252`
- Rejection reasons:
  - internal `GLC` nRMSE did not improve by at least 20%.
  - `EGLC` endpoint guard failed.
  - `EGLC` slope guard failed.
  - `VEGLC` teacher-flux guard failed.

Best parameter highlights:

```json
{
  "vmax_VEGLC": 2.992338857045779,
  "km_EGLC": 24.488039437034622,
  "km_GLC_transport": 2.864930859228081,
  "transport_gate_feedback_strength_VEGLC": 0.8928223639744208,
  "transport_gate_feedback_km_GLC_VEGLC": 8.54922196746391,
  "transport_gate_feedback_hill_VEGLC": 0.6928279794535482,
  "transport_gate_import_cap_VEGLC": 1.3604772878707694
}
```

Key metric changes:

- `EGLC`: nRMSE `0.119 -> 0.116`, but endpoint error `0.0028 -> 0.1386`; final `12.95 -> 14.71 mM`, experimental `12.92 mM`.
- `ELAC`: nRMSE `0.322 -> 0.327`; slight regression.
- `GLC`: nRMSE `6.301 -> 5.111`; final `9.75 -> 7.62 mM`, experimental `0.826 mM`.
- `LAC`: nRMSE `0.950 -> 0.954`; remains depleted.
- `PYR`: nRMSE `2.355 -> 2.321`; slight improvement.
- `VEGLC` flux nRMSE: `0.975 -> 1.279`; teacher-flux guard failed.
- `VELAC` flux nRMSE: `0.518 -> 0.523`; slight regression.
- `VLDH` flux nRMSE: `0.670 -> 0.676`; slight regression.

Interpretation:

- Cap/feedback is mechanically capable of lowering intracellular `GLC`.
- However, whenever the cap/feedback is strong enough to substantially lower `GLC`, it leaves too much extracellular `EGLC`.
- A mild cap can preserve `EGLC`, but the `GLC` improvement is too small for promotion.
- This rejects the hypothesis that a `VEGLC` import cap/feedback alone can reconcile Brodbar extracellular glucose depletion with intracellular glucose control under the current downstream network.

Decision:

- Do not promote the import-feedback candidate.
- Keep the new family and runner as reversible diagnostic tools.
- The next likely structural test should couple a mild `VEGLC` cap/feedback with an explicit downstream sink/search, rather than treating transport alone as the whole solution.

## Session Checkpoint

Last session checkpoint: 2026-06-28

Current memory file:

- `tasks/fla_current_tasks.md`

Current unpromoted diagnostic best:

- `Simulations/brodbar/hermes/glucose_utilization_vhk_atp_46d_n16_upper5`
- Rejected bridge diagnostic: `Simulations/brodbar/hermes/vhk_atp_lactate_bridge_velac_vldh_46d_n24`
- Rejected import-feedback diagnostic: `Simulations/brodbar/hermes/veglc_import_feedback_vhk_atp_seed_46d_n28`

Current mechanistic interpretation:

- `VEGLC` transport gate fixes Brodbar extracellular glucose depletion.
- The gate likely imports more glucose than the internal glycolytic network can process.
- `VHK` capacity and ATP affinity are real bottlenecks, but even `vmax_VHK = 5.0` plus low `km_ATP_HK` leaves intracellular `GLC` far too high.
- `VPGI/VPFK` opening is currently disfavored because it worsens `ELAC` and `VELAC` guardrails.
- `VEGLC` cap/feedback alone lowers `GLC` only by sacrificing `EGLC` endpoint/slope and `VEGLC` teacher-flux fit.

Next concrete move:

1. Couple mild `VEGLC` import feedback with one explicit downstream glucose sink/search.
2. Candidate seam:
   - fixed `VEGLC` import-feedback structure.
   - `VHK/km_ATP_HK`.
   - one downstream pyruvate/lactate production lever, chosen conservatively.
3. Keep hard guards on `EGLC` endpoint/slope and `VEGLC` teacher flux.
4. Do not overwrite `Simulations/brodbar/calibration/best_params.json` until a candidate passes full Brodbar panel replay and validation planning.

## Pre-optimization Glycolysis Flux Bottleneck Profile

Date: 2026-08-04

Purpose:

- Identify one downstream kinetic lever before running another FLA optimization.
- Diagnose the fixed `VEGLC` gate plus `VHK/km_ATP_HK` reference with native ODE fluxes.
- Preserve all current parameter files; this work is diagnostic only.

Implementation:

- Added `scripts/profile_glycolysis_flux_bottlenecks.py`.
- Added focused tests in `qa/test_glycolysis_flux_profile.py`.
- Replayed four unchanged hypotheses over 46 days:
  - global baseline.
  - `VEGLC` depletion gate.
  - fixed `VHK + km_ATP_HK` reference.
  - rejected `VEGLC` import-feedback candidate.
- Used 181 regular time points plus 80 geometric early-time points.
- Replayed every solved state through `equadiff_brodbar` with the native `FluxTracker`.
- Reconciled glycolytic pool balances, kinetic occupancy factors, reaction throughput, and endpoints.
- Ran three fixed one-factor probes without optimization or promotion:
  - `vmax_VPEP_PASE x0.1`.
  - `vmax_VPFK x2`.
  - `vmax_VPK x2`.

Reference diagnosis:

- `EGLC` remains well preserved: final `12.951 mM` vs experimental `12.915 mM`; endpoint error `0.00281`.
- Intracellular `GLC` remains too high: final `9.748 mM` vs `0.826 mM`.
- `F6P` is the largest accumulation symptom: final `1.848 mM` vs `0.007 mM`.
- `LAC` remains too low: final `0.201 mM` vs `6.463 mM`.
- ATP collapses: final `0.000051 mM` vs `0.470 mM`.
- Direct PEP routing is strongly biased away from ATP-producing pyruvate kinase:
  - `VPK`: `6.7%` of mean direct PEP drainage.
  - `VPEP_PASE`: `93.3%` of mean direct PEP drainage.

Fixed-probe interpretation:

- `vmax_VPFK x2` most strongly clears `F6P` and improves `LAC`, but barely lowers `GLC` and leaves the PEP phosphatase bypass dominant.
- `vmax_VPK x2` modestly improves direct PEP routing, but has little effect on ATP or intracellular glucose.
- `vmax_VPEP_PASE x0.1` gives the most mechanistically coherent response:
  - `GLC`: `9.748 -> 9.092 mM`.
  - ATP: `0.000051 -> 0.000105 mM`.
  - PEP-to-`VPK` share: `6.7% -> 17.1%`.
  - `EGLC` endpoint error remains low: `0.00281 -> 0.00304`.
- This probe remains insufficient and is not promoted; it establishes only the direction of the next narrow search.

Decision:

- Treat `F6P/VPFK` as a downstream symptom, not the first structural lever.
- Use decreasing `vmax_VPEP_PASE` as the single open downstream parameter in the next reversible FLA pass.
- Keep mild `VEGLC` feedback and `VHK/km_ATP_HK` fixed.
- Keep hard guards on `EGLC` endpoint/slope, `VEGLC` teacher flux, ATP, `GLC`, `LAC`, `ELAC`, `VELAC`, and `VLDH`.
- No optimization was run and no parameter file was promoted or overwritten.

Artifacts:

- `output/fla_preoptimization_glycolysis_profile/preoptimization_flux_diagnostic_report.md`
- `output/fla_preoptimization_glycolysis_profile/summary.json`
- `output/fla_preoptimization_glycolysis_profile/glycolysis_flux_profile.png`
- `output/fla_preoptimization_glycolysis_profile/glycolysis_candidate_comparison.png`
- `output/fla_preoptimization_glycolysis_profile/fixed_one_factor_sensitivity.csv`

## Downward-only VPEP_PASE FLA with Fixed Mild VEGLC Feedback

Date: 2026-08-04

Run:

- `Simulations/brodbar/hermes/vpep_pase_downward_vhk_atp_mild_feedback_46d_n20`

Method:

- Kept the `VHK + km_ATP_HK` candidate fixed.
- Activated a reversible mild `VEGLC` feedback:
  - strength `0.10`.
  - feedback `km_GLC = 8.5492 mM`.
  - Hill coefficient `0.6928`.
  - import cap `5.0`, effectively inactive over the tested trajectory.
- Opened only `vmax_VPEP_PASE`.
- Used a strict decrease-only bound from `0.01` to `8.941`, around the seed `8.94995`.
- Ran 20 Optuna trials over 46 days with deterministic anchors at `0.5x`, `0.25x`, `0.1x`, `0.05x`, and `0.01x`.
- Added direct Brodbar targets for ATP, F6P, and PEP in addition to the extracellular/glucose/lactate panel.
- Tracked exact native `VPK/VPEP_PASE` routing and teacher fluxes.

Fixed mild-feedback seed:

- `EGLC` endpoint error: `0.0447`.
- `GLC` nRMSE: `5.929`; final `9.210 mM`.
- ATP final: `0.0000558 mM`.
- PEP-to-`VPK` share: `7.4%`.

Focused optimum:

- `vmax_VPEP_PASE = 0.772324`.
- Focused loss: `66.992 -> 60.201`.
- `GLC` nRMSE: `5.929 -> 5.537`; final `9.210 -> 8.587 mM`.
- ATP final: `0.0000558 -> 0.000109 mM`.
- PEP-to-`VPK` share: `7.4% -> 18.3%`.
- `LAC` nRMSE: `0.950 -> 0.929`.
- `EGLC` endpoint error: `0.0447 -> 0.0356`.
- Teacher-flux guards for `VEGLC`, `VELAC`, and `VLDH` passed.

Full Brodbar-panel replay:

- Compared the candidate directly with the fixed mild-feedback seed across 55 mapped metabolites.
- Mean nRMSE regressed: `8.102 -> 8.378`.
- Median nRMSE regressed: `0.915 -> 0.929`.
- 11 metabolites improved, 5 regressed, and 39 remained similar.
- Critical regression:
  - PEP nRMSE `0.275 -> 20.794`.
  - PEP transiently accumulated to approximately `2.6 mM` before returning near the terminal experimental range.
- G6P nRMSE also regressed: `12.946 -> 15.710`.

Decision:

- Reject the candidate after full-panel review.
- Do not promote `vmax_VPEP_PASE = 0.772324`.
- Keep the run as a mechanistic diagnostic.
- Add a hard PEP trajectory guard to future downstream FLA passes.
- Interpretation: decreasing the ADP-independent PEP sink alone improves energetic routing but shifts the bottleneck into PEP/G6P.
- Next hypothesis: jointly decrease `vmax_VPEP_PASE` moderately and increase `VPK` capacity/effective PEP utilization, with hard PEP/G6P/ATP guards.

Artifacts:

- `Simulations/brodbar/hermes/vpep_pase_downward_vhk_atp_mild_feedback_46d_n20/decision_report.md`
- `Simulations/brodbar/hermes/vpep_pase_downward_vhk_atp_mild_feedback_46d_n20/summary.json`
- `Simulations/brodbar/hermes/vpep_pase_downward_vhk_atp_mild_feedback_46d_n20/vpep_pase_downward_fla.png`
- `output/brodbar_vpep_pase_downward_full_panel/manifest.json`
- `output/brodbar_vpep_pase_downward_full_panel/brodbar_full_panel_nrmse_delta_summary.png`

## Coupled VPEP_PASE/VPK FLA Pass

Date: 2026-08-04

Run:

- `Simulations/brodbar/hermes/vpep_vpk_coupled_mild_feedback_46d_n20`

Method:

- Seeded from the fixed mild-feedback state of the previous VPEP_PASE pass.
- Kept mild `VEGLC` feedback, `vmax_VHK = 5.0`, and `km_ATP_HK = 0.0601441` fixed.
- Opened only two directed parameters:
  - `vmax_VPEP_PASE`: decrease-only, `0.5 .. 4.475`.
  - `vmax_VPK`: increase-only, `0.7134 .. 3.5671`.
- Added explicit PEP and G6P targets and trajectory guards.
- Used 20 trials over 46 days, including five mechanistic anchor combinations.

Best local point:

- `vmax_VPEP_PASE = 4.443913`.
- `vmax_VPK = 0.835618`.
- GLC nRMSE: `5.929 -> 5.778`, only `2.5%` improvement.
- ATP final: `0.0000558 -> 0.0000672 mM`, only `20.3%` improvement.
- PEP-to-VPK share: `7.4% -> 11.4%`, below the required `5` percentage-point increase.
- PEP nRMSE: `0.275 -> 1.090`, guard failed.
- G6P nRMSE: `12.946 -> 14.026`, regressed.
- F6P nRMSE improved `27.008 -> 24.589`, but remains very poor.

Full Brodbar-panel replay:

- Compared against the same fixed mild-feedback seed across 55 mapped metabolites.
- Mean nRMSE: `8.102 -> 8.082`, a marginal improvement.
- Median nRMSE: `0.915 -> 0.942`, a regression.
- 6 metabolites improved, 4 regressed, and 45 remained similar.
- The full-panel result does not rescue the focused guard failures.

Decision:

- Reject the coupled candidate.
- Do not promote either parameter.
- Interpretation: manipulating only PEP outlet capacities cannot restore sustained glucose utilization and ATP production. The remaining limitation is likely upstream energy/redox control or ATP/adenylate handling that suppresses late `VHK`, `VPFK`, and `VPK` throughput.
- Next diagnostic: profile native ATP/ADP/redox occupancy around `VHK`, `VPFK`, and `VPK`, then test one constrained energy-affinity lever with PEP/G6P guards.

Artifacts:

- `Simulations/brodbar/hermes/vpep_vpk_coupled_mild_feedback_46d_n20/decision_report.md`
- `Simulations/brodbar/hermes/vpep_vpk_coupled_mild_feedback_46d_n20/summary.json`
- `output/brodbar_vpep_vpk_coupled_full_panel/manifest.json`
- `output/brodbar_vpep_vpk_coupled_full_panel/brodbar_full_panel_nrmse_delta_summary.png`

## Native ATP/ADP/Redox Control Profile Before New Optimization

Date: 2026-08-04 local / 2026-08-05 UTC

Run:

- `output/fla_energy_redox_control_profile`
- Diagnostic profiler: `scripts/profile_energy_redox_controls.py`

Method:

- Replayed the fixed mild-feedback seed and the rejected coupled `VPEP_PASE/VPK` candidate over 46 days.
- Used 181 regular time points plus 80 geometric early-time points.
- Recovered native reaction rates with `FluxTracker` and reconstructed the exact ATP substrate, ADP/ATP, PK inhibition, and LDH redox factors from the ODE terms.
- Decomposed ATP production and consumption directly from the ODE reaction balance.
- No optimization, parameter promotion, or overwrite was performed.

Reference findings for `mild_seed`:

- ATP collapses to `5.5814e-05 mM` at day 46; late mean is `7.2261e-05 mM`.
- NADH remains high at `1.19784 mM` at day 46; late mean is `1.22466 mM`.
- Late HK ATP occupancy is `0.00120` and PFK ATP occupancy is `0.00218`.
- Late PK ATP-inhibition factor is `0.99996`; ATP is not inhibiting PK in the late state.
- Late LDH NADH/NAD drive is `0.1468`; redox supply remains a secondary restriction.
- Late ATP production is `0.012365` versus ATP consumption `0.012453`, giving a small negative net balance of `-8.79e-05`.
- The rejected coupled candidate has the same qualitative diagnosis: HK/PFK ATP occupancies remain near zero, PK ATP inhibition remains inactive, and LDH redox drive remains low.

Interpretation:

- The next limitation is an ATP-pool/adenylate state collapse, not the ATP allosteric inhibition term of `VPK`.
- The profiler ranks `km_ATP_HK` ahead of `km_ATP_PFK` as the first energy-affinity lever because its native late occupancy is lower.
- This is a demand-side lever: decreasing `km_ATP_HK` can increase ATP consumption before it restores glucose throughput. It must therefore be tested in a narrow, reversible neighborhood with an explicit ATP guard.
- `km_NADH_NAD` is retained as a separate redox hypothesis and should not be co-opened in the first pass.

Decision:

- Next execution: open only `km_ATP_HK` around the current mild-feedback seed; keep `km_ATP_PFK`, `ki_ATP_PK`, and `km_NADH_NAD` fixed.
- Preserve hard guards on `PEP`, `G6P`, `ATP`, `EGLC`, `GLC`, `LAC`, `ELAC`, `VEGLC`, `VELAC`, and `VLDH`, followed by the full 55-metabolite Brodbar panel gate.
- Do not promote the diagnostic result itself.

Artifacts:

- `output/fla_energy_redox_control_profile/energy_redox_control_report.md`
- `output/fla_energy_redox_control_profile/summary.json`
- `output/fla_energy_redox_control_profile/energy_redox_control_profile.png`
- `output/fla_energy_redox_control_profile/energy_redox_late_controls.png`
- `output/fla_energy_redox_control_profile/energy_redox_timeseries.csv`
- `output/fla_energy_redox_control_profile/energy_redox_summary.csv`
- `output/fla_energy_redox_control_profile/energy_redox_control_ranking.csv`

## Narrow `km_ATP_HK` FLA Pass With Energy and Flux Guards

Date: 2026-08-05

Run:

- `Simulations/brodbar/hermes/km_atp_hk_narrow_mild_feedback_46d`
- Runner: `scripts/run_km_atp_hk_narrow_fla.py`
- Seed: `Simulations/brodbar/hermes/vpep_vpk_coupled_mild_feedback_46d_n20/seed_fixed_params.json`

Method:

- Opened only `km_ATP_HK`.
- Kept the mild-feedback VEGLC hypothesis, `vmax_VHK`, `vmax_VPEP_PASE`, `vmax_VPK`, `km_ATP_PFK`, `ki_ATP_PK`, and `km_NADH_NAD` fixed.
- Searched the reversible local interval `0.05 .. 0.120288`, centered at `0.0601441`.
- Used 12 trials plus one local refinement over 46 days with LSODA.
- Added focused concentration guards on `ATP`, `PEP`, `G6P`, `GLC`, `LAC`, `EGLC`, and `ELAC`.
- Added teacher-flux guards on `VEGLC`, `VELAC`, and `VLDH`.
- Replayed the best point against all 55 mapped Brodbar metabolites before making the decision.

Best focused point:

- `km_ATP_HK = 0.12016442`.
- Focused loss: `47.5597 -> 46.5557`.
- ATP endpoint: `5.5814e-05 -> 8.6953e-05 mM`.
- G6P nRMSE: `12.946 -> 11.198`.
- PEP nRMSE: `0.275 -> 0.256`.
- GLC nRMSE regressed: `5.929 -> 6.320`.
- GLC guard failed; the candidate did not reach the required 2% focused improvement.

Full Brodbar panel:

- Mean nRMSE: `8.10169 -> 7.89897`.
- Median nRMSE: unchanged at approximately `0.91545`.
- 7 metabolites improved, 1 regressed, and 47 were similar.
- The full-panel non-inferiority gate passed, but this does not override the focused GLC guard.

Decision:

- Reject promotion of `km_ATP_HK = 0.12016442`.
- Keep the original mild-feedback seed in `promoted_or_seed_params.json`.
- Interpretation: reducing effective HK ATP affinity demand improves ATP/PEP/G6P modestly, but it worsens intracellular glucose utilization. ATP-affinity control alone does not resolve the GLC bottleneck.
- Next separate hypothesis: open only `km_NADH_NAD` with `km_ATP_HK` reset to the seed value, retaining the same guards.

Artifacts:

- `Simulations/brodbar/hermes/km_atp_hk_narrow_mild_feedback_46d/decision_report.md`
- `Simulations/brodbar/hermes/km_atp_hk_narrow_mild_feedback_46d/summary.json`
- `Simulations/brodbar/hermes/km_atp_hk_narrow_mild_feedback_46d/km_atp_hk_narrow_fla.png`
- `Simulations/brodbar/hermes/km_atp_hk_narrow_mild_feedback_46d/km_atp_hk_metrics.csv`
- `Simulations/brodbar/hermes/km_atp_hk_narrow_mild_feedback_46d/full_panel/manifest.json`
- `Simulations/brodbar/hermes/km_atp_hk_narrow_mild_feedback_46d/full_panel/brodbar_full_panel_nrmse_delta_summary.png`

## Narrow `km_NADH_NAD` Redox-Only FLA Pass

Date: 2026-08-05

Run:

- `Simulations/brodbar/hermes/km_nadh_nad_narrow_mild_feedback_46d`
- Runner: `scripts/run_km_nadh_nad_narrow_fla.py`
- Seed: `Simulations/brodbar/hermes/vpep_vpk_coupled_mild_feedback_46d_n20/seed_fixed_params.json`

Method:

- Reset and locked `km_ATP_HK = 0.06014413339486139` from the mild-feedback seed.
- Opened only `km_NADH_NAD`, centered at the seed value `9.18438014`.
- Searched the reversible local interval `4.59219007 .. 18.36876027`.
- Used 12 Optuna trials plus one two-sided local refinement over 46 days with LSODA.
- Required a lower focused loss and at least 2% improvement in VLDH teacher nRMSE or LAC nRMSE.
- Retained hard guards on `ATP`, `PEP`, `G6P`, `GLC`, `LAC`, `EGLC`, `ELAC`, `VEGLC`, `VELAC`, and `VLDH`.
- Replayed the best diagnostic point against all 55 mapped Brodbar metabolites before promotion was considered.

Best diagnostic point:

- `km_NADH_NAD = 6.85357323`.
- Focused loss: `47.5597 -> 47.2488`.
- VLDH teacher nRMSE: `0.670315 -> 0.669906`, only a `0.06%` relative improvement.
- VELAC teacher nRMSE: `0.517813 -> 0.516458`.
- LAC nRMSE regressed: `0.950328 -> 0.951854`.
- GLC nRMSE changed only marginally: `5.92926 -> 5.92579`.
- ELAC nRMSE improved: `0.322600 -> 0.299936`.
- ATP endpoint fell: `5.5814e-05 -> 4.6458e-05 mM`, below the 95% floor.
- PEP nRMSE regressed: `0.274601 -> 0.300471`.
- G6P nRMSE regressed: `12.9457 -> 13.0567`.

Full Brodbar panel:

- Mean nRMSE: `8.10169 -> 8.09747`.
- Median nRMSE: `0.915454 -> 0.915455`.
- 3 metabolites improved, 3 regressed, and 49 were similar.
- Main improvements: URT, PYR, and GLU.
- Main regressions: P3G, ASP, and G6P; PEP also moved in the wrong direction.
- The full-panel non-inferiority gate passed, but it cannot override the focused redox/ATP/PEP rejection.

Decision:

- Reject promotion of `km_NADH_NAD = 6.85357323`.
- Keep the original mild-feedback seed in `promoted_or_seed_params.json`; `km_ATP_HK` remained exactly locked.
- Interpretation: decreasing `km_NADH_NAD` can weakly favor the native VLDH redox term and ELAC, but the effect is too small and is paid for by lower ATP and worse PEP/G6P. Redox affinity alone is not the limiting correction.
- Do not co-open `km_NADH_NAD` with `km_ATP_HK`.
- Next controlled step: a small downward feasibility screen of `km_ATP_PFK` alone, with both tested parameters reset to seed. Abort that hypothesis before Optuna if ATP or PEP falls below the existing guards.

Artifacts:

- `Simulations/brodbar/hermes/km_nadh_nad_narrow_mild_feedback_46d/decision_report.md`
- `Simulations/brodbar/hermes/km_nadh_nad_narrow_mild_feedback_46d/summary.json`
- `Simulations/brodbar/hermes/km_nadh_nad_narrow_mild_feedback_46d/km_nadh_nad_narrow_fla.png`
- `Simulations/brodbar/hermes/km_nadh_nad_narrow_mild_feedback_46d/km_nadh_nad_metrics.csv`
- `Simulations/brodbar/hermes/km_nadh_nad_narrow_mild_feedback_46d/km_nadh_nad_flux_metrics.csv`
- `Simulations/brodbar/hermes/km_nadh_nad_narrow_mild_feedback_46d/full_panel/manifest.json`
- `Simulations/brodbar/hermes/km_nadh_nad_narrow_mild_feedback_46d/full_panel/brodbar_full_panel_nrmse_delta_summary.png`

## Directed `km_ATP_PFK` Feasibility Screen

Date: 2026-08-05

Run:

- `Simulations/brodbar/hermes/km_atp_pfk_feasibility_mild_feedback_46d`
- Runner: `scripts/screen_km_atp_pfk_feasibility.py`
- Seed: `Simulations/brodbar/hermes/vpep_vpk_coupled_mild_feedback_46d_n20/seed_fixed_params.json`

Method:

- Diagnostic screen only; no Optuna optimization and no promotion path.
- Opened only `km_ATP_PFK` in the downward direction.
- Locked `km_ATP_HK = 0.06014413339486139` and `km_NADH_NAD = 9.184380136644775` exactly at the mild-feedback seed.
- Replayed `0.90x`, `0.75x`, and `0.50x` of seed `km_ATP_PFK = 0.03302569060009802` over 46 days.
- Retained all ATP/PEP/G6P/GLC/LAC/EGLC/ELAC and VEGLC/VELAC/VLDH guards.
- Defined an ATP/PEP hard stop for sequential screening; all three points remained inside those two specific limits, so the complete dose response was evaluated.

Results:

### `0.90x` (`km_ATP_PFK = 0.02972312`)

- Focused loss: `47.5597 -> 47.4696`.
- ATP endpoint: `5.5814e-05 -> 5.7671e-05 mM`.
- PEP nRMSE: `0.27460 -> 0.26137`.
- GLC nRMSE: `5.92926 -> 5.90382`.
- LAC nRMSE: `0.95033 -> 0.94575`.
- VLDH teacher nRMSE: `0.67031 -> 0.66310`.
- G6P nRMSE changed slightly in the wrong direction: `12.9457 -> 12.9667`.
- No guard violation, but no direct glycolysis target improved by the required 1%; this point is feasible but not sufficiently informative to justify Optuna.

### `0.75x` (`km_ATP_PFK = 0.02476927`)

- Focused loss worsened to `55.0834`.
- ATP endpoint increased to `7.8540e-05 mM` and PEP nRMSE improved to `0.25965`.
- GLC nRMSE regressed to `5.97212`.
- G6P endpoint guard failed despite a lower aggregate G6P nRMSE.

### `0.50x` (`km_ATP_PFK = 0.01651285`)

- Focused loss worsened sharply to `301.843`.
- ATP endpoint increased to `1.6957e-04 mM`.
- PEP nRMSE regressed to `0.28350` and GLC nRMSE to `6.03506`.
- G6P endpoint guard failed again.

Decision:

- Do not optimize or promote `km_ATP_PFK`.
- Retain the mild-feedback seed unchanged.
- Interpretation: PFK ATP affinity can raise the residual ATP pool and shift PEP/LAC, but stronger activation worsens intracellular glucose and the G6P endpoint. The mild response is too small to identify a useful guarded optimum.
- The isolated ATP-affinity and redox family is now exhausted: `km_ATP_HK`, `km_ATP_PFK`, and `km_NADH_NAD` did not produce a promotable correction.
- Next diagnostic should move to ATP production rather than ATP demand: screen `km_ADP_ATP` alone while recording native `VPGK`, `VPK`, and the ATP balance.

Artifacts:

- `Simulations/brodbar/hermes/km_atp_pfk_feasibility_mild_feedback_46d/decision_report.md`
- `Simulations/brodbar/hermes/km_atp_pfk_feasibility_mild_feedback_46d/summary.json`
- `Simulations/brodbar/hermes/km_atp_pfk_feasibility_mild_feedback_46d/km_atp_pfk_feasibility_screen.png`
- `Simulations/brodbar/hermes/km_atp_pfk_feasibility_mild_feedback_46d/screen_metrics.csv`
- `Simulations/brodbar/hermes/km_atp_pfk_feasibility_mild_feedback_46d/screen_trials.csv`

## Directed `km_ADP_ATP` ATP-Production Screen

Date: 2026-08-05

Run:

- `Simulations/brodbar/hermes/km_adp_atp_production_screen_46d`
- Runner: `scripts/screen_km_adp_atp_production.py`
- Seed: `Simulations/brodbar/hermes/vpep_vpk_coupled_mild_feedback_46d_n20/seed_fixed_params.json`

Method:

- Diagnostic screen only; no Optuna optimization or promotion path.
- Opened only the common ATP-production drive `km_ADP_ATP` in the downward direction.
- Locked `km_ATP_HK`, `km_ATP_PFK`, `km_NADH_NAD`, `vmax_VPGK`, and `vmax_VPK` exactly at the mild-feedback seed.
- Reconstructed native `VPGK`, `VPK`, `VAK`, ATP production, ATP consumption, ATP net flux, and the ADP/ATP drive from the same terms used by the ODE.
- Guarded `GLC`, `LAC`, `G6P`, `PEP`, `P3G`, `P2G`, `PYR`, `EGLC`, `ELAC`, and teacher fluxes `VEGLC`, `VELAC`, `VLDH`.
- Planned `0.90x`, `0.75x`, and `0.50x`; the screen stopped at `0.75x` after endpoint transfer guards failed.

Seed ATP balance, days 40-46:

- ATP production: `0.0123651 mM/day`.
- ATP consumption: `0.0124530 mM/day`.
- Net ATP flux: `-8.7917e-05 mM/day`.
- VPGK: `0.0120776 mM/day`.
- VPK: `0.00025257 mM/day`.
- ATP endpoint: `5.5814e-05 mM`.

### `0.90x` (`km_ADP_ATP = 0.23941125`)

- Late ATP production increased `4.6%` to `0.0129332 mM/day`.
- Late ATP consumption increased in parallel to `0.0130212 mM/day`.
- Late net ATP flux remained slightly more negative at `-8.8021e-05 mM/day`.
- ATP endpoint increased to `5.8287e-05 mM`.
- VPGK increased to `0.0126296`; VPK to `0.00027465 mM/day`.
- GLC nRMSE improved only `0.56%`, from `5.92926` to `5.89597`.
- No transfer guard failed, but the direct phenotype gain was below the 1% feasibility threshold.

### `0.75x` (`km_ADP_ATP = 0.19950937`)

- Late ATP production increased `21.1%` to `0.0149727 mM/day`.
- Late ATP consumption increased `21.0%` to `0.0150670 mM/day`.
- Late net ATP flux became more negative: `-9.4297e-05 mM/day`.
- ATP endpoint increased `19.0%` to `6.6446e-05 mM`.
- VPGK increased to `0.0145790`; VPK to `0.00037256 mM/day`.
- GLC nRMSE improved `2.18%`, from `5.92926` to `5.80021`.
- G6P and P3G endpoint transfer guards failed; stronger perturbations were not evaluated.

Decision:

- Abort `km_ADP_ATP` before optimization and retain the seed unchanged.
- Interpretation: lowering `km_ADP_ATP` activates ATP production, predominantly through VPGK, but consumption rises almost one-for-one and the net late ATP balance does not recover. The apparent pool gain is accompanied by G6P/P3G endpoint displacement.
- VPGK and VPK capacity should not be opened next: their late rates remain far below their fixed `vmax` values.
- Next diagnostic: decompose the seed-versus-`0.75x` increase across every ATP-consuming reaction and identify whether one induced sink is responsible.

Artifacts:

- `Simulations/brodbar/hermes/km_adp_atp_production_screen_46d/decision_report.md`
- `Simulations/brodbar/hermes/km_adp_atp_production_screen_46d/summary.json`
- `Simulations/brodbar/hermes/km_adp_atp_production_screen_46d/km_adp_atp_production_screen.png`
- `Simulations/brodbar/hermes/km_adp_atp_production_screen_46d/screen_metrics.csv`
- `Simulations/brodbar/hermes/km_adp_atp_production_screen_46d/native_flux_and_atp_balance.csv`

## ATP-Consumption Sink Attribution

Date: 2026-08-05

Run:

- `Simulations/brodbar/hermes/atp_consumption_sink_attribution_46d`
- Runner: `scripts/profile_atp_consumption_sinks.py`
- Comparison: mild-feedback seed versus `km_ADP_ATP 0.75x` diagnostic point.

Method:

- Replayed both parameter sets over 46 days with identical solver settings and native `FluxTracker` output.
- Verified that `km_ADP_ATP` was the only changed parameter.
- Decomposed the exact ATP-consumption term into all 13 ODE reactions.
- Calculated integrated flux, late mean, endpoint, constitutive share, and share of induced consumption for each sink.
- Linked sinks to measured Brodbar pools and compared nRMSE and endpoint errors.
- ATP-consumption closure error was exactly `0.0` for both replays.

Late ATP-consumption attribution:

| Reaction | Seed share | Candidate share | Induced share | Delta late flux |
|---|---:|---:|---:|---:|
| `VHK` | 48.1% | 48.2% | 48.6% | `+0.00126988` |
| `VPFK` | 41.8% | 41.8% | 41.6% | `+0.00108662` |
| `VNDPK` | 7.4% | 7.4% | 7.5% | `+0.00019695` |
| `VRKa` | 1.1% | 1.1% | 0.8% | `+0.00002057` |
| `VPRPPASe` | 0.7% | 0.7% | 0.7% | `+0.00001778` |

Interpretation:

- VHK and VPFK together explain `90.2%` of the compensating ATP-consumption increase.
- They already explain `89.9%` of constitutive late consumption in the seed; no hidden side-path sink emerges.
- VNDPK is a stable distant third rather than a newly induced dominant sink.
- GLC nRMSE improves `5.92926 -> 5.80021`, but G6P nRMSE worsens `12.9457 -> 13.3895` and final G6P rises `0.08141 -> 0.09986 mM`.
- F6P nRMSE improves `27.0081 -> 25.9179`, but final F6P remains `1.7749 mM` versus `0.00703 mM` experimentally.
- F16BP improves slightly (`0.70998 -> 0.67135` nRMSE).
- The production-side perturbation therefore feeds the ATP-investment phase but does not restore flux matching through the G6P/F6P pools.

Decision:

- Do not optimize another ATP-consuming sink parameter.
- Do not reopen VHK or VPFK individually; both mono-parameter affinity hypotheses were already tested and rejected.
- Prioritize a structural flux-matching audit across `VHK`, `VPGI`, `VG6PDH`, `VPFK`, `VTKL2`, and `VTAL`.
- Reconstruct G6P and F6P balances exactly before deciding between a coupled kinetic hypothesis and an ODE structural correction.

Artifacts:

- `Simulations/brodbar/hermes/atp_consumption_sink_attribution_46d/decision_report.md`
- `Simulations/brodbar/hermes/atp_consumption_sink_attribution_46d/summary.json`
- `Simulations/brodbar/hermes/atp_consumption_sink_attribution_46d/atp_consumption_sink_attribution.png`
- `Simulations/brodbar/hermes/atp_consumption_sink_attribution_46d/atp_consumption_sink_attribution.csv`
- `Simulations/brodbar/hermes/atp_consumption_sink_attribution_46d/atp_sink_associated_pool_metrics.csv`
- `Simulations/brodbar/hermes/atp_consumption_sink_attribution_46d/atp_consumption_sink_timeseries.csv`

## Investment-Phase Flux-Matching Audit

Date: 2026-08-05

Run:

- `Simulations/brodbar/hermes/investment_phase_flux_matching_46d`
- Runner: `scripts/audit_investment_phase_flux_matching.py`
- Comparison: mild-feedback seed versus the saved diagnostic `km_ADP_ATP 0.75x` point.

Method:

- Diagnostic replay only; no optimization, parameter opening, or promotion.
- Verified that `km_ADP_ATP` was the only parameter difference between the two replays.
- Recovered native `VHK`, `VPGI`, `VG6PDH`, `VPFK`, `VTKL2`, and `VTAL` with `FluxTracker`.
- Reconstructed the exact balances point by point:
  - `dG6P/dt = VHK - VPGI - VG6PDH`
  - `dF6P/dt = VPGI + VTKL2 + VTAL - VPFK`
- Quantified input/output matching and concentration change at J1-J2, J10-J20, and J40-J46.
- Compared GLC, G6P, F6P, and F16BP against all available Brodbar measurements.

Balance closure:

- Maximum pointwise flux-versus-ODE derivative error: `3.55e-15 mM/day`.
- Maximum numerical integral residual: `0.0218 mM`, localized to the sharp J1-J2 transient; mid/late residuals were at most `1.27e-4 mM`.
- Conclusion: the implemented G6P/F6P algebra is internally exact. This does not prove biological completeness, but it does not support an algebraic ODE correction.

Seed flux matching:

| Pool | J1-J2 output/input | J10-J20 output/input | J40-J46 output/input |
|---|---:|---:|---:|
| `G6P` | `0.045` | `3.382` | `2.877` |
| `F6P` | `0.680` | `0.399` | `0.471` |

- VHK initially exceeds VPGI + VG6PDH by about 22-fold; G6P rises by `1.914 mM` during J1-J2.
- G6P later drains, but remains too high relative to Brodbar: nRMSE `12.9457`, final `0.08141 mM` versus `0.02389 mM`.
- F6P input exceeds VPFK output in every window. F6P reaches `1.84115 mM` versus `0.00703 mM`; nRMSE is `27.0081`.
- `VTKL2 + VTAL` account for `98.2%` of F6P input during J1-J2 and `47.2%` / `48.0%` during the mid/late windows.
- The dominant F6P mismatch is therefore not restricted to VPGI/VPFK; non-oxidative PPP return is a first-order contributor.

Effect of `km_ADP_ATP 0.75x`:

- GLC nRMSE improves modestly: `5.92926 -> 5.80021`.
- G6P worsens: nRMSE `12.9457 -> 13.3895`; final `0.08141 -> 0.09986 mM`.
- F6P improves only partially: nRMSE `27.0081 -> 25.9179`; final remains `1.77487 mM`.
- Late VHK increases `21.2%`, G6P output `21.9%`, F6P input `21.4%`, and VPFK `20.9%`.
- The perturbation scales the entire investment-phase relay while leaving the output/input mismatch pattern essentially intact.

Decision:

- Retain the current G6P and F6P stoichiometric balance equations.
- Do not reopen an isolated VHK, VPGI, VPFK, or ATP-affinity parameter.
- Prioritize a kinetic-structure diagnostic of the currently irreversible `VTKL2` and `VTAL` rate laws.
- The next implementation must be reversible by feature flag: preserve the current formulation, add one fixed reversible/product-feedback hypothesis, and replay it before any fitting.
- Require exact balance closure and preserve GLC/G6P/F6P/F16BP, ATP/PEP, extracellular, and teacher-flux safeguards.

Artifacts:

- `Simulations/brodbar/hermes/investment_phase_flux_matching_46d/decision_report.md`
- `Simulations/brodbar/hermes/investment_phase_flux_matching_46d/summary.json`
- `Simulations/brodbar/hermes/investment_phase_flux_matching_46d/investment_phase_flux_matching.png`
- `Simulations/brodbar/hermes/investment_phase_flux_matching_46d/investment_phase_window_summary.csv`
- `Simulations/brodbar/hermes/investment_phase_flux_matching_46d/investment_phase_pool_metrics.csv`
- `Simulations/brodbar/hermes/investment_phase_flux_matching_46d/investment_phase_timeseries.csv`

## Reversible PPP Directionality Diagnostic

Date: 2026-08-10

Run:

- `Simulations/brodbar/hermes/reversible_ppp_directionality_diagnostic_46d`
- Runner: `scripts/diagnose_reversible_ppp_directionality.py`
- Seed: `Simulations/brodbar/hermes/vpep_vpk_coupled_mild_feedback_46d_n20/seed_fixed_params.json`

Method:

- Added an optional `reversible_saturation_difference` family independently to `VTKL2` and `VTAL`.
- Preserved the historical irreversible MM family as the default; omitting the feature toggles or setting both blends to zero restores the seed exactly.
- Compared four fixed cases over 46 days: irreversible seed, reversible VTKL2, reversible VTAL, and both reversible.
- Held every kinetic constant fixed; no optimization, promotion, or parameter artifact was produced.
- Reconstructed native G6P/F6P balances after the model's low-concentration derivative damping.
- Applied concentration safeguards to EGLC, ELAC, GLC, G6P, F6P, F16BP, LAC, PEP, and ATP, plus teacher-flux safeguards to VEGLC, VELAC, and VLDH.

Numerical validation:

- Fourteen targeted PPP and balance-reconstruction tests passed.
- A five-day end-to-end smoke replay passed with maximum closure `3.55e-15 mM/day`.
- The full 46-day replay also closed to `3.55e-15 mM/day`.

Results:

| Case | F6P nRMSE improvement | F6P final (mM) | G6P final (mM) | Main failed safeguards |
|---|---:|---:|---:|---|
| `reversible_VTKL2` | `9.9%` | `1.81160` | `0.03006` | ATP, G6P, PEP, ELAC, VELAC, VLDH |
| `reversible_VTAL` | `40.2%` | `0.00426` | `0.14172` | G6P endpoint, F16BP endpoint |
| `reversible_both` | `84.1%` | `0.00079` | `0.07726` | G6P, F16BP, PEP, ELAC, VELAC, VLDH |

- Experimental final F6P is `0.00703 mM`; the irreversible seed ends at `1.84653 mM`.
- Reversible VTAL is negative for `33.3%` of sampled times and changes the late F6P output/input ratio from `0.458` to `1.118`.
- The double-reversible case drives F6P below the data and activates low-concentration damping for `4.8%` of sampled times.
- Reversible VTKL2 is negative for `82.0%` of sampled times and transfers the perturbation strongly into ATP/PEP and lactate fluxes.
- The fixed difference-of-saturations law therefore demonstrates that excessive non-oxidative PPP return contributes to F6P accumulation, but uniform reverse capacity is too strong and insufficiently selective.

Decision:

- Reject all fixed reversible cases and retain the irreversible seed.
- Do not optimize `hybrid_reverse_scale_VTKL2`, `hybrid_reverse_scale_VTAL`, or their blends.
- Before another kinetic family, audit all measured and modeled PPP pools and reconstruct their native balances.
- Use that audit to choose between forward-return attenuation, non-reversing product feedback, and a thermodynamically constrained reversible formulation.

Artifacts:

- `Simulations/brodbar/hermes/reversible_ppp_directionality_diagnostic_46d/decision_report.md`
- `Simulations/brodbar/hermes/reversible_ppp_directionality_diagnostic_46d/summary.json`
- `Simulations/brodbar/hermes/reversible_ppp_directionality_diagnostic_46d/reversible_ppp_directionality.png`
- `Simulations/brodbar/hermes/reversible_ppp_directionality_diagnostic_46d/reversible_ppp_timeseries.csv`
- `Simulations/brodbar/hermes/reversible_ppp_directionality_diagnostic_46d/reversible_ppp_window_summary.csv`
- `Simulations/brodbar/hermes/reversible_ppp_directionality_diagnostic_46d/reversible_ppp_metrics.csv`
- `Simulations/brodbar/hermes/reversible_ppp_directionality_diagnostic_46d/reversible_ppp_case_decisions.csv`

## Complete PPP Flux Learning Audit

Date: 2026-08-10

Run:

- `Simulations/brodbar/hermes/complete_ppp_fla_audit_46d`
- Runner: `scripts/audit_complete_ppp_fla.py`

Method:

- Reconstructed the native balances of G6P, GL6P, GO6P, RU5P, R5P, X5P, E4P, S7P, GA3P, and F6P.
- Included glycolytic connections through VHK, VPGI, VPFK, VFDPA, VTPI, and VGAPDH, plus R5P/purine connections through VRKa, VRKb, and VPRPPASe.
- Replayed the irreversible seed and all three fixed reversible VTKL2/VTAL probes with unchanged kinetic constants.
- Built PCHIP net-flux teachers only for directly measured PPP pools: G6P, GO6P, and F6P.
- Kept individual reaction fluxes explicitly model-attributed because the concentration derivatives identify only net balances.

Validation and identifiability:

- Maximum pointwise closure error across ten pools and four cases: `0.0 mM/day`.
- Brodbar has no direct measurements for GL6P, RU5P, R5P, X5P, E4P, S7P, or GA3P.
- Seed net-teacher nRMSE is `23.9438` for G6P, `2.81933` for GO6P, and `50.8862` for F6P.
- Seed net-flux sign agreement is `71.2%`, `84.2%`, and only `11.9%`, respectively.

Seed routing:

- J1-J2 mean oxidative fluxes: VG6PDH `0.0373`, VPGLS `1.0388`, and V6PGD `1.1667 mM/day`.
- J1-J2 non-oxidative return: VTKL2 `0.9957` plus VTAL `1.9875`, totaling `2.9832 mM/day` into F6P.
- The Brodbar F6P teacher is only `+0.00929 mM/day` in J1-J2 and is negative in the mid and late windows.
- Late F6P turnover remains split between VPGI input `35.6%`, VPFK output `31.4%`, VTAL input `16.5%`, and VTKL2 input `16.5%`.

Initialization finding:

- The pipeline initializes every unmeasured state to `1 mM` before mapping Brodbar data.
- Six latent PPP pools differ from their historical JA values by more than fivefold: GL6P `131234x`, RU5P `23.6x`, R5P `78.7x`, X5P `23.6x`, S7P `13.4x`, and GA3P `131.8x`.
- These defaults produce a dominant J1-J2 transient and confound a direct kinetic conclusion.

Decision:

- Do not alter VTAL or VTKL2 yet.
- First replay the historical JA initial values for only the seven unmeasured PPP pools with all kinetic constants fixed.

Artifacts:

- `Simulations/brodbar/hermes/complete_ppp_fla_audit_46d/decision_report.md`
- `Simulations/brodbar/hermes/complete_ppp_fla_audit_46d/summary.json`
- `Simulations/brodbar/hermes/complete_ppp_fla_audit_46d/ppp_measured_pool_fla.png`
- `Simulations/brodbar/hermes/complete_ppp_fla_audit_46d/ppp_latent_pool_trajectories.png`
- `Simulations/brodbar/hermes/complete_ppp_fla_audit_46d/ppp_flux_routing.png`
- `Simulations/brodbar/hermes/complete_ppp_fla_audit_46d/complete_ppp_initial_condition_audit.csv`

## Historical Latent PPP Initial-Condition Replay

Date: 2026-08-10

Run:

- `Simulations/brodbar/hermes/ppp_initial_condition_diagnostic_46d`
- Runner: `scripts/diagnose_ppp_initial_conditions.py`

Contract:

- Compared the current generic latent initialization with historical JA values over 46 days.
- Changed only GL6P, RU5P, R5P, X5P, E4P, S7P, and GA3P initial concentrations.
- Preserved every measured initial state, every kinetic constant, and irreversible VTKL2/VTAL kinetics.
- Maximum ten-pool closure error: `0.0 mM/day`.

PPP effects:

- Early net PPP return to F6P fell from `2.9832` to `0.2339 mM/day`.
- F6P concentration nRMSE improved `27.0449 -> 21.7577` (`19.5%`).
- F6P net-teacher nRMSE improved `50.8862 -> 14.8679` (`70.8%`).
- G6P concentration nRMSE worsened `12.9391 -> 15.9386`.
- GO6P concentration remained poor (`0.99187 -> 0.99150` nRMSE), while its net-teacher nRMSE worsened `2.8193 -> 20.4663` because the corrected GL6P no longer masks excessive V6PGD drainage.

Transfer guards:

- ATP endpoint fell `5.28e-5 -> 2.60e-5 mM`.
- PEP nRMSE worsened `0.2753 -> 0.3745`.
- ELAC nRMSE worsened `0.3228 -> 0.4756`.
- VELAC teacher nRMSE worsened `0.5159 -> 0.6288`; VLDH worsened `0.6646 -> 0.7742`.
- Historical initialization therefore is not promoted as a standalone correction.

Oxidative PPP attribution:

- Under historical latent initialization at J1-J2, VPGLS is `0.07872` and V6PGD is `0.20843 mM/day`.
- GO6P output/input is `2.648`, producing model drainage around `-0.1284 mM/day` versus the Brodbar teacher near `-0.0112 mM/day`.
- The current generic GL6P value had partially masked this V6PGD excess.

Decision:

- Retain the current initialization as the default revert path and keep the historical initialization as a controlled diagnostic context.
- Before VTAL product feedback, run a fixed downward `vmax_V6PGD` feasibility screen under historical latent initialization.
- Do not optimize or promote unless GO6P flux matching improves without reproducing G6P, energy, or lactate failures.

Artifacts:

- `Simulations/brodbar/hermes/ppp_initial_condition_diagnostic_46d/decision_report.md`
- `Simulations/brodbar/hermes/ppp_initial_condition_diagnostic_46d/summary.json`
- `Simulations/brodbar/hermes/ppp_initial_condition_diagnostic_46d/ppp_initial_condition_diagnostic.png`
- `Simulations/brodbar/hermes/ppp_initial_condition_diagnostic_46d/ppp_initial_condition_measured_metrics.csv`
- `Simulations/brodbar/hermes/ppp_initial_condition_diagnostic_46d/ppp_initial_condition_net_teacher_windows.csv`
- `Simulations/brodbar/hermes/ppp_initial_condition_diagnostic_46d/ppp_initial_condition_routing.csv`

## Directed V6PGD Feasibility Screen

Date: 2026-08-10

Run:

- `Simulations/brodbar/hermes/vmax_v6pgd_feasibility_46d`
- Runner: `scripts/screen_vmax_v6pgd_feasibility.py`

Contract:

- Replayed the current production initialization, the historical latent-PPP initialization, and four fixed V6PGD capacities over 46 days.
- Candidate scales were `0.60x`, `0.50x`, `0.43x`, and `0.35x` of native `vmax_V6PGD = 10.0`.
- Changed only `vmax_V6PGD` in candidate kinetics; retained irreversible VTKL2/VTAL and every other seed parameter.
- Compared each candidate against both the historical-initialization reference and the current production reference.
- Required at least 20% improvement of early and full GO6P teacher errors plus at least 5% improvement of GO6P concentration nRMSE.
- No Optuna study, promoted parameter file, or production initialization change was generated.

Validation:

- Twenty targeted PPP, initialization, and V6PGD-screen tests passed.
- Maximum pointwise closure error across all ten reconstructed PPP pools and six cases: `0.0 mM/day`.

Results:

| V6PGD scale | Early teacher improvement | Full teacher improvement | GO6P concentration improvement | Incremental guards | Production guards |
|---|---:|---:|---:|---|---|
| `0.60x` | `40.1%` | `40.1%` | `0.27%` | G6P endpoint failed | failed |
| `0.50x` | `50.1%` | `50.1%` | `0.40%` | passed | failed |
| `0.43x` | `57.2%` | `57.1%` | `0.53%` | passed | failed |
| `0.35x` | `65.2%` | `65.2%` | `0.75%` | passed | failed |

- Every tested point still depleted GO6P; at `0.35x`, final GO6P was only `2.18e-5 mM` versus `0.00893 mM` experimentally.
- G6P stayed near `15.9-16.0` nRMSE and F6P near `21.6-21.9` nRMSE, so the perturbation did not repair neighboring measured pools.
- Production transfer failures persisted for ATP, ELAC, G6P, LAC, NADPH, PEP, VELAC, and VLDH.
- NADP + NADPH conservation remained numerically stable, with maximum total drift below `9e-13 mM`.

Initial-rate diagnosis:

- At J1 under historical latent initialization, `GL6P = 7.62e-6 mM`, `VPGLS = 0.000313 mM/day`, and seed `V6PGD = 4.32514 mM/day`.
- The Brodbar J1-J2 mean GO6P teacher is `-0.011165 mM/day`; matching this early-window proxy at the initial state requires `V6PGD = VPGLS - teacher = 0.011478 mM/day`.
- This mean-teacher proxy corresponds to a capacity scale `0.002654x` and `vmax_V6PGD = 0.02654`, far below the tested range.

Decision:

- Reject the tested isolated V6PGD hypothesis and retain all production defaults.
- Before another 46-day run, execute a short J1-J2 boundary screen at `0.010x`, `0.005x`, `0.002654x`, and `0.001x`.
- If no point jointly preserves GO6P and its neighboring PPP/redox pools, stop fixed-capacity screening and move to a state-dependent GO6P-affinity or VPGLS/V6PGD coupling diagnosis.

Artifacts:

- `Simulations/brodbar/hermes/vmax_v6pgd_feasibility_46d/decision_report.md`
- `Simulations/brodbar/hermes/vmax_v6pgd_feasibility_46d/summary.json`
- `Simulations/brodbar/hermes/vmax_v6pgd_feasibility_46d/vmax_v6pgd_feasibility.png`
- `Simulations/brodbar/hermes/vmax_v6pgd_feasibility_46d/vmax_v6pgd_assessments.csv`
- `Simulations/brodbar/hermes/vmax_v6pgd_feasibility_46d/vmax_v6pgd_timeseries.csv`

## V6PGD Boundary and 46-Day Transfer

Date: 2026-08-10

Early-window method:

- Added `scripts/screen_vmax_v6pgd_initial_rate_boundary.py` for high-resolution J1-J2 screening under historical latent-PPP initialization.
- Initial boundary: `0.010x`, `0.005x`, `0.002654x`, and `0.001x` of native V6PGD capacity.
- Refinement: `0.0125x`, `0.015x`, `0.020x`, `0.030x`, and `0.050x`.
- Held every other kinetic constant and all initial states fixed; required exact ten-pool closure, positive PPP/redox pools, GO6P concentration improvement, teacher improvement, and teacher-sign agreement.

Early-window result:

- The early-mean teacher-matched scale `0.002654x` reproduced the J1-J2 mean target at the initial state but crossed to positive flux by J1.058 as VPGLS rose.
- `0.010x` improved teacher and concentration errors by `94.5%` and `90.0%`, but retained only `23.4%` sign agreement.
- Refinement found `0.020x` as the narrowest candidate with `100%` sign agreement, `94.6%` teacher improvement, and `81.2%` concentration improvement.
- All ten PPP balances closed exactly and NADP + NADPH drift stayed below `1e-9 mM`.

46-day transfer under historical initialization:

- Replayed the current production reference, the historical-initialization reference, and only `vmax_V6PGD = 0.20` (`0.020x`) for 46 days.
- GO6P early teacher improvement: `97.8%`; full teacher improvement: `97.6%`.
- GO6P concentration nRMSE improved `0.99150 -> 0.36939` (`62.7%`), and net-teacher nRMSE improved `20.4663 -> 0.48879`.
- The candidate passed every incremental guard relative to the historical-initialization reference.
- G6P remained poor (`15.9758` nRMSE) and F6P slightly worsened (`21.7577 -> 22.2853` nRMSE).
- Relative to the current production reference, failures persisted for ATP, ELAC, G6P, LAC, NADPH, PEP, VELAC, and VLDH.

Decision:

- `vmax_V6PGD = 0.20` is a strong GO6P diagnostic candidate but is not promoted.
- The current comparison still confounds its kinetic effect with the historical latent-PPP initial conditions.
- Next run: compare seed versus `vmax_V6PGD = 0.20` under identical current generic latent-PPP initialization over 46 days, changing one kinetic constant and no state.

Artifacts:

- `Simulations/brodbar/hermes/vmax_v6pgd_initial_rate_boundary_J1_J2/decision_report.md`
- `Simulations/brodbar/hermes/vmax_v6pgd_initial_rate_boundary_J1_J2/summary.json`
- `Simulations/brodbar/hermes/vmax_v6pgd_initial_rate_refinement_J1_J2/decision_report.md`
- `Simulations/brodbar/hermes/vmax_v6pgd_initial_rate_refinement_J1_J2/summary.json`
- `Simulations/brodbar/hermes/vmax_v6pgd_0.020_transfer_46d/decision_report.md`
- `Simulations/brodbar/hermes/vmax_v6pgd_0.020_transfer_46d/summary.json`
- `Simulations/brodbar/hermes/vmax_v6pgd_0.020_transfer_46d/vmax_v6pgd_feasibility.png`

## V6PGD Current-Initialization Transfer

Date: 2026-08-10

Run:

- `Simulations/brodbar/hermes/vmax_v6pgd_0.020_current_init_transfer_46d`
- Runner: `scripts/screen_vmax_v6pgd_feasibility.py --scales 0.02 --candidate-initialization current`

Contract:

- Compared the unchanged current production seed against `vmax_V6PGD = 0.20` for 46 days.
- Both cases used the same current generic latent-PPP initial conditions.
- The candidate changed exactly one kinetic constant, `vmax_V6PGD`; no initial state, directionality option, or other parameter changed.
- No Optuna study or promoted parameter artifact was generated.
- Maximum pointwise closure error across all ten PPP pools and both cases was `0.0 mM/day`.

Initial-rate result:

- Current generic `GL6P(0) = 1.0 mM` produces `VPGLS = 3.73740 mM/day` at J1.
- Seed V6PGD is `4.32514 mM/day`, giving `dGO6P/dt = -0.58774 mM/day`.
- With `vmax_V6PGD = 0.20`, V6PGD falls to `0.08650 mM/day` and `dGO6P/dt` reverses to `+3.65090 mM/day`.
- Matching the J1-J2 mean teacher at the initial state requires V6PGD `3.74856 mM/day`, scale `0.86669x`, and `vmax_V6PGD = 8.6669`.

46-day result:

- GO6P concentration nRMSE regressed `0.99187 -> 8.39282` (`-746.2%` relative improvement).
- GO6P net-teacher nRMSE regressed `2.81933 -> 21.03302`; early and full relative improvements were `-643.9%` and `-646.0%`.
- J1-J2 mean GO6P model flux became `+1.17948 mM/day` versus teacher `-0.011165 mM/day`.
- G6P concentration nRMSE improved slightly `12.9391 -> 12.5686`; F6P worsened slightly `27.0449 -> 27.3627`.
- NADPH time mean fell `0.04633 -> 0.01464 mM` and failed its ratio guard.
- ATP, PEP, GLC, LAC, EGLC, ELAC, VEGLC, VELAC, and VLDH remained within the configured relative guards.

Interpretation and decision:

- Reject transfer of `vmax_V6PGD = 0.20` to the current initialization and retain the production seed.
- The exact J1 ridge confirms incompatible capacities for historical and generic GL6P initializations (`0.02708` versus `8.66745`); the earlier `0.02654` and `8.6669` values used the J1-J2 mean teacher proxy.
- V6PGD capacity is therefore not identifiable independently of latent GL6P initialization in the present setup.
- Next diagnostic: map the fixed `GL6P(0)-vmax_V6PGD` teacher-matching ridge, then determine whether latent PPP states need an estimated or quasi-steady initialization layer.

Artifacts:

- `Simulations/brodbar/hermes/vmax_v6pgd_0.020_current_init_transfer_46d/decision_report.md`
- `Simulations/brodbar/hermes/vmax_v6pgd_0.020_current_init_transfer_46d/summary.json`
- `Simulations/brodbar/hermes/vmax_v6pgd_0.020_current_init_transfer_46d/vmax_v6pgd_feasibility.png`
- `Simulations/brodbar/hermes/vmax_v6pgd_0.020_current_init_transfer_46d/vmax_v6pgd_assessments.csv`
- `Simulations/brodbar/hermes/vmax_v6pgd_0.020_current_init_transfer_46d/vmax_v6pgd_timeseries.csv`

## GL6P(0)-V6PGD Identifiability Map

Date: 2026-08-11

Run:

- `Simulations/brodbar/hermes/gl6p_v6pgd_identifiability_J1_J2`
- Runner: `scripts/map_gl6p_v6pgd_identifiability.py`

Contract:

- Built a fixed `61 x 81` initial-rate grid over `GL6P(0) = 7.62e-6 .. 1 mM` and `vmax_V6PGD = 0.01354 .. 10.4009`.
- Used the exact J1 Brodbar GO6P derivative, `-0.0113983 mM/day`; the previously reported `-0.0111650` value is the J1-J2 teacher mean rather than the instantaneous J1 derivative.
- Solved the exact teacher ridge from `dGO6P/dt = VPGLS(GL6P) - V6PGD(GO6P, NADP)` without optimization.
- Replayed 20 points along the ridge over J1-J2 under two backgrounds: all other latent pools current-generic or historical JA.
- Held every kinetic constant except the ridge-defined diagnostic `vmax_V6PGD` fixed; no kinetic or initialization artifact was promoted.

Initial-rate ridge:

- At historical `GL6P(0) = 7.62e-6 mM`, exact J1 matching requires `vmax_V6PGD = 0.02708`.
- At generic `GL6P(0) = 1 mM`, exact J1 matching requires `vmax_V6PGD = 8.66745`.
- The admissible initial-rate ridge therefore spans `320.1-fold`, proving strong structural confounding between latent GL6P initialization and V6PGD capacity.

Dynamic refinement:

- Forty J1-J2 replays were completed with maximum ten-pool closure error `0.0 mM/day`.
- The best composite point in both latent backgrounds was `GL6P(0) = 0.0013 mM`, `vmax_V6PGD = 0.148336`.
- GO6P concentration nRMSE was `0.04566` in the current-other-latent background and `0.04561` in the historical-other-latent background.
- GO6P teacher nRMSE remained `1.5150` and `1.5166`; sign agreement was only `74.1%`, below the required `80%`.
- G6P concentration nRMSE remained `17.36-17.37`.
- F6P concentration nRMSE was `18.21` with current other latent states but `0.881` with historical other latent states, exposing strong dependence on the remaining hidden PPP pools.
- NADP/NADPH positivity and conservation passed for every replay.

Decision:

- No GL6P(0)-V6PGD ridge point passes the GO6P shape gate in both backgrounds.
- Do not calibrate or promote V6PGD independently of latent PPP initialization.
- Replace the generic `1 mM` fallback with a bounded, explicitly reversible initialization layer estimated at fixed kinetics from latent quasi-steady balances and measured G6P/GO6P/F6P teachers.
- Test that initialization over J1-J2 before any 46-day replay or further PPP kinetic learning.

Artifacts:

- `Simulations/brodbar/hermes/gl6p_v6pgd_identifiability_J1_J2/decision_report.md`
- `Simulations/brodbar/hermes/gl6p_v6pgd_identifiability_J1_J2/summary.json`
- `Simulations/brodbar/hermes/gl6p_v6pgd_identifiability_J1_J2/gl6p_v6pgd_identifiability_map.png`
- `Simulations/brodbar/hermes/gl6p_v6pgd_identifiability_J1_J2/gl6p_v6pgd_ridge_replays.png`
- `Simulations/brodbar/hermes/gl6p_v6pgd_identifiability_J1_J2/gl6p_v6pgd_teacher_ridge.csv`
- `Simulations/brodbar/hermes/gl6p_v6pgd_identifiability_J1_J2/gl6p_v6pgd_replay_metrics.csv`

## Constrained Latent PPP Initialization

Date: 2026-08-11

Run:

- `Simulations/brodbar/hermes/constrained_ppp_initialization_J1_J2`
- Runner: `scripts/diagnose_constrained_ppp_initialization.py`

Contract:

- Kept every production kinetic constant fixed, including `vmax_VPGLS = 4.111138` and `vmax_V6PGD = 10.0`.
- Locked all experimentally measured J1 states.
- Estimated only GL6P, RU5P, R5P, X5P, E4P, S7P, and GA3P with positive pool-specific bounds in log concentration space.
- Compared three multistart formulations: latent quasi-steady, balanced latent/teacher, and teacher-priority.
- Preserved generic and historical initializations as explicit revert paths; generated only a diagnostic, non-promoted initialization artifact.

Structural feasibility:

- The measured-teacher sensitivity matrix has rank `2/3`.
- G6P J1 flux is exactly insensitive to all seven latent states.
- GO6P depends only on GL6P; F6P depends on X5P, E4P, S7P, and GA3P in the local sensitivity calculation.
- Exact J1 teachers are G6P `+0.005335`, GO6P `-0.011398`, and F6P `+0.009815 mM/day`.
- At fixed seed kinetics, `dGO6P/dt` ranges from `-4.32510` at GL6P zero to only `-0.214003 mM/day` at saturating GL6P.
- The GO6P teacher is therefore theoretically unreachable by any nonnegative GL6P initialization.

J1-J2 results:

- Generic reference nRMSE values for G6P/GO6P/F6P concentration were `17.638/0.771/22.884`; teacher values were `505.856/43.161/718.956`.
- Historical initialization strongly improved F6P but worsened GO6P; G6P remained essentially unchanged.
- The latent-QSS solution improved F6P concentration nRMSE to `0.860` and teacher nRMSE to `25.947`, but GO6P worsened to `0.984` and `61.132`.
- Balanced and teacher-priority solutions matched the initial F6P teacher closely and improved F6P concentration nRMSE to `0.486-0.487`, but GL6P hit its `2 mM` upper bound and GO6P worsened to `2.639` concentration nRMSE and about `101.79` teacher nRMSE.
- Every replay preserved NADP/NADPH validity and closed all ten PPP balances exactly (`0.0 mM/day`).

Decision:

- Do not extend any constrained initialization to 46 days and do not promote an initialization artifact.
- An initialization-only solution is mathematically infeasible at the fixed production VPGLS/V6PGD capacities.
- The smallest one-parameter route to feasibility is a narrow downward V6PGD screen: theoretical saturation requires `vmax_V6PGD <= 9.53165` (`0.95317x`).
- Next run fixed scales `0.97x`, `0.9532x`, `0.93x`, `0.91x`, and `0.90x`, re-solving the seven-state initialization at each point without Optuna.
- If that fails, test the alternative VPGLS increase around the analytical `+4.93%` saturation threshold.

Artifacts:

- `Simulations/brodbar/hermes/constrained_ppp_initialization_J1_J2/decision_report.md`
- `Simulations/brodbar/hermes/constrained_ppp_initialization_J1_J2/summary.json`
- `Simulations/brodbar/hermes/constrained_ppp_initialization_J1_J2/constrained_initializations.json`
- `Simulations/brodbar/hermes/constrained_ppp_initialization_J1_J2/solver_diagnostics.json`
- `Simulations/brodbar/hermes/constrained_ppp_initialization_J1_J2/constrained_initialization_replays.png`
- `Simulations/brodbar/hermes/constrained_ppp_initialization_J1_J2/constrained_initial_states.png`

## Fixed V6PGD Screen with Constrained PPP Initialization

Date: 2026-08-11

Run:

- `Simulations/brodbar/hermes/v6pgd_constrained_initialization_screen_J1_J2`
- Runner: `scripts/screen_vmax_v6pgd_constrained_initialization.py`

Contract:

- Held every kinetic constant except `vmax_V6PGD` fixed and tested deterministic scales `0.97x`, `0.9532x`, `0.93x`, `0.91x`, and `0.90x`.
- Re-solved the seven positive bounded latent PPP states independently for the latent-QSS, balanced-teacher, and teacher-priority formulations at every fixed capacity.
- Kept measured J1 states locked and treated G6P only as a `2%` non-inferiority guard because its latent-state sensitivity is exactly zero.
- Required at least `5%` improvement in each GO6P/F6P concentration and teacher metric, at least `1%` latent residual reduction, finite interior GL6P, positivity, redox validity, and exact ten-pool closure.
- Performed no Optuna search and promoted neither kinetic parameters nor initial conditions.

J1-J2 screen:

- `0.97x` and `0.9532x` remained theoretically infeasible at saturating GL6P; `0.93x` and `0.91x` became theoretically feasible but were still infeasible inside the finite `GL6P <= 2 mM` bound.
- `0.90x` was the only finite-bound feasible capacity. Its balanced-teacher solution produced `GL6P(0) = 1.687871 mM`, preserved a positive PPP minimum of `1.076e-4 mM`, and closed all ten balances exactly.
- Against the balanced seed, GO6P concentration nRMSE improved `2.6394 -> 1.8262` (`30.8%`) and teacher nRMSE improved `101.7930 -> 92.4551` (`9.17%`).
- F6P concentration nRMSE improved `0.4862 -> 0.4487` (`7.72%`) and teacher nRMSE improved `23.6697 -> 21.5723` (`8.86%`).
- The normalized latent residual fell by `1.16%`; G6P concentration and teacher ratios were `0.9993` and `0.9995` relative to seed.

Guarded 46-day transfer:

- Compared the balanced seed and `vmax_V6PGD = 9.0` using their independently constrained balanced initial states.
- All relative guards passed for ATP, PEP, GLC, LAC, EGLC, ELAC, PPP positivity, NADP/NADPH positivity and conservation, and exact closure.
- Full-horizon GO6P teacher nRMSE improved `11.3571 -> 9.7414`; GO6P concentration changed `0.99137 -> 0.99097`.
- Full-horizon F6P teacher nRMSE improved `1.62147 -> 1.59870`, while F6P concentration worsened slightly `20.6655 -> 21.0756` but remained inside the `5%` non-inferiority guard.
- The joint full-horizon GO6P/F6P concentration-plus-teacher score improved `34.6355 -> 33.4067`.
- Global fit remains poor: GLC nRMSE is `5.717`, ATP `1.014`, and G6P `16.164` for the candidate.

Decision:

- Retain `vmax_V6PGD = 9.0` plus the balanced constrained initialization as a diagnostic PPP candidate only.
- Do not replace the production kinetic seed or production initialization.
- The next run is a narrow robustness/refinement grid around the finite-bound transition: `0.895x`, `0.900x`, `0.9025x`, `0.905x`, and `0.9075x`, ranked primarily on the full-horizon GO6P/F6P score under unchanged transfer guards.

Artifacts:

- `Simulations/brodbar/hermes/v6pgd_constrained_initialization_screen_J1_J2/decision_report.md`
- `Simulations/brodbar/hermes/v6pgd_constrained_initialization_screen_J1_J2/summary.json`
- `Simulations/brodbar/hermes/v6pgd_constrained_initialization_screen_J1_J2/early_replay_metrics.csv`
- `Simulations/brodbar/hermes/v6pgd_constrained_initialization_screen_J1_J2/long_replay_timeseries.csv`
- `Simulations/brodbar/hermes/v6pgd_constrained_initialization_screen_J1_J2/v6pgd_constrained_screen.png`

## V6PGD Finite-Bound Transition Refinement

Date: 2026-08-11

Run:

- `Simulations/brodbar/hermes/v6pgd_constrained_transition_refinement_46d`
- Runner: `scripts/refine_vmax_v6pgd_constrained_transition.py`

Contract:

- Restricted the initialization layer to the balanced-teacher formulation and independently re-solved all seven latent PPP states at each capacity.
- Tested fixed `vmax_V6PGD` scales `0.895x`, `0.900x`, `0.9025x`, `0.905x`, and `0.9075x`, plus the unchanged `1.0x` balanced seed.
- Replayed every case for 46 days and ranked candidates primarily by the complete GO6P/F6P concentration-plus-teacher score.
- Required the previous J1-J2 gate, finite-bound GO6P feasibility, G6P non-inferiority, ATP/PEP/GLC/LAC/EGLC/ELAC transfer guards, PPP positivity, redox conservation, and exact closure.
- Performed no optimization and promoted no parameter or initial condition.

Transition map:

- All refined points were feasible inside the `GL6P <= 2 mM` bound; constrained GL6P(0) increased monotonically from `1.53418 mM` at `0.895x` to `1.98151 mM` at `0.9075x`.
- Full GO6P/F6P scores were `32.6304`, `33.4067`, `33.7913`, `34.4329`, and `35.0501` as V6PGD scale increased across the grid; balanced seed was `34.6355`.
- `0.895x` had the lowest unconstrained full score and improved it by `5.79%`, mainly through GO6P teacher nRMSE `11.3571 -> 8.7643`.
- `0.895x` failed the local gate: J1-J2 F6P concentration worsened by `6.25%`, and F6P teacher improved only `4.96%`, just below the required `5%`.
- `0.9025x` and `0.905x` improved the full score but failed local GO6P-teacher and latent-residual gates.
- `0.9075x` worsened the full score by `1.20%`, and GL6P(0) approached the bound at `1.9815 mM`.

Selected diagnostic point:

- `0.900x` was the only point passing every local and full-horizon guard.
- Its full GO6P/F6P joint score was `33.4067`, a `3.548%` improvement versus balanced seed.
- Full GO6P teacher nRMSE improved `11.3571 -> 9.7414`, while F6P teacher improved `1.62147 -> 1.59870`.
- Absolute trajectories remain structurally poor: GO6P collapses near zero after the initial transient, and F6P rises to about `1.57 mM` versus Brodbar values near `0.01-0.13 mM`.

Decision:

- Confirm `vmax_V6PGD = 9.0` with balanced constrained initialization as the robust diagnostic operating point within the tested transition.
- Do not promote it to the production seed because the absolute G6P/F6P errors remain large.
- Next run a fixed-parameter attribution audit of the residual F6P accumulation through `VPGI`, `VPFK`, `VTKL2`, and `VTAL`, including coupled PPP and PFK-driving states, before opening another kinetic lever.

Artifacts:

- `Simulations/brodbar/hermes/v6pgd_constrained_transition_refinement_46d/decision_report.md`
- `Simulations/brodbar/hermes/v6pgd_constrained_transition_refinement_46d/summary.json`
- `Simulations/brodbar/hermes/v6pgd_constrained_transition_refinement_46d/early_metrics.csv`
- `Simulations/brodbar/hermes/v6pgd_constrained_transition_refinement_46d/full_horizon_metrics.csv`
- `Simulations/brodbar/hermes/v6pgd_constrained_transition_refinement_46d/full_horizon_timeseries.csv`
- `Simulations/brodbar/hermes/v6pgd_constrained_transition_refinement_46d/v6pgd_transition_refinement.png`

## Residual F6P Accumulation Audit at V6PGD 0.900x

Date: 2026-08-11

Run:

- `Simulations/brodbar/hermes/f6p_accumulation_v6pgd_0.900_audit_46d`
- Runner: `scripts/audit_f6p_accumulation_v6pgd_candidate.py`

Contract:

- Reused the saved balanced-seed and retained `vmax_V6PGD = 9.0` full-horizon trajectories; performed no new simulation or optimization.
- Held every kinetic parameter and initial state fixed to its diagnostic contract.
- Reconstructed the exact coded balance `dF6P/dt = VPGI + VTKL2 + VTAL - VPFK` over J1-J2, days 2-10, 10-20, 20-30, and 30-46.
- Calculated the VPFK flux required to follow the Brodbar F6P derivative and compared it with actual VPFK, F6P saturation, ATP saturation, and inferred hidden PFK modulation.

Balance and divergence:

- Maximum raw F6P reconstruction error was `4.44e-16 mM/day`; effective flux matched the ODE derivative exactly.
- Sustained normalized F6P divergence begins at day `5.15` for balanced seed and day `5.10` for the `0.900x` candidate.
- The candidate therefore does not delay the F6P defect and reaches `1.5736 mM` at day 46 versus Brodbar `0.00703 mM`.

Flux attribution:

- During J1-J2, VPFK exceeds teacher-required drainage and F6P falls `0.0691 -> 0.0228 mM`; non-oxidative PPP return supplies `93.7%` of the transient input.
- During days 2-10, total input is `0.13367 mM/day`, actual VPFK is `0.05262`, and teacher-required VPFK is `0.12884`, leaving a `0.07621 mM/day` deficit.
- The VPFK deficit remains positive through every later window: `0.06174`, `0.02413`, and `0.00959 mM/day`.
- Across post-J2 windows, non-oxidative PPP return provides a duration-weighted `46.9%` of F6P input; PGI provides the other `53.1%`.

PFK state diagnosis:

- Post-J2 F6P occupancy of PFK averages `85.6%`, so F6P substrate is saturating rather than limiting.
- Inferred PFK modulation is exactly `1.000`, excluding a hidden pH/allosteric activity loss in the active model configuration.
- Post-J2 ATP occupancy averages only `2.20%`: `9.03%` during days 2-10, `1.23%` during days 10-20, and below `1%` after day 20.
- Actual VPFK remains below teacher-required drainage by a duration-weighted `0.03686 mM/day` after J2.

Decision:

- Attribute residual F6P accumulation to ATP-limited VPFK drainage with material contributions from both PGI and non-oxidative PPP return.
- The retained V6PGD correction improves the GO6P tradeoff but does not repair F6P timing; latent initialization and `vmax_VPFK` are not the primary residual defect.
- Do not reopen VPFK, PFK ATP affinity, VPGI, VTKL2, or VTAL.
- Next reconstruct the exact ATP production-consumption transition over J1-J10 in the retained `0.900x` PPP context, locating ATP collapse relative to F6P divergence before any new kinetic calibration.

Artifacts:

- `Simulations/brodbar/hermes/f6p_accumulation_v6pgd_0.900_audit_46d/decision_report.md`
- `Simulations/brodbar/hermes/f6p_accumulation_v6pgd_0.900_audit_46d/summary.json`
- `Simulations/brodbar/hermes/f6p_accumulation_v6pgd_0.900_audit_46d/f6p_window_attribution.csv`
- `Simulations/brodbar/hermes/f6p_accumulation_v6pgd_0.900_audit_46d/coupled_state_windows.csv`
- `Simulations/brodbar/hermes/f6p_accumulation_v6pgd_0.900_audit_46d/f6p_accumulation_attribution.png`

## J1-J10 ATP Transition in Retained V6PGD/PPP Context

Date: 2026-08-11

Run:

- `Simulations/brodbar/hermes/atp_transition_v6pgd_0.900_ppp_context_J1_J10`
- Runner: `scripts/audit_atp_transition_v6pgd_ppp_context.py`

Contract:

- Replayed the balanced seed and retained `vmax_V6PGD = 9.0` point with their independently saved seven-state PPP initializations.
- Held every other kinetic parameter and all measured initial states fixed; performed no optimization or promotion.
- Used a dense `0.005-day` J1-J10 grid with complete FluxTracker output.
- Reconstructed the exact raw balance `VPGK + VPK + VAK - 13 ATP-consuming reactions` and separately reproduced the native `ATP/1e-3` derivative damping below `1e-3 mM`.
- Maximum effective ATP closure error was `7.11e-15 mM/day`.

Transition timing:

- Candidate ATP rises from `0.93299` to a transient peak `1.74146 mM` at day `1.08`.
- ATP production loses half of its initial-window level at day `1.275`; total consumption loses half at day `1.305`, so production decline precedes demand relief by `0.03 day`.
- ATP crosses `km_ATP_PFK = 0.03303 mM` at day `2.51` and `0.01 mM` at day `2.72`.
- F6P divergence begins at day `5.10`; ATP substrate collapse therefore leads it by `2.59 days`.
- The V6PGD candidate slightly delays ATP collapse relative to balanced seed (`2.51` versus `2.44 days`) and is not the cause of the energy defect.

Pre-collapse balance:

- Integrated production to ATP collapse is `5.74049 mM`; integrated consumption is `6.64638 mM`, giving a raw deficit `-0.90589 mM`.
- Production contributions are VPGK `3.72139`, VAK `1.45540`, and VPK `0.56370 mM`.
- Major cumulative consumers are VHK `2.44872`, VNDPK `1.25503`, VRKa `0.99581`, VPFK `0.99061`, and VPRPPASe `0.44276 mM`.

Mechanistic assignment at ATP collapse:

- B13PG falls from `3.58405 mM` at J1 to `9.37e-5 mM` by J1.3 and `1.03e-5 mM` at day 2.51.
- VPGK utilization is only `0.00295` at collapse despite ADP/ATP drive `0.816`, identifying substrate supply rather than adenylate drive as its limitation.
- VPK remains at `0.611` utilization and contributes `52.4%` of ATP production; VAK contributes `33.4%` and VPGK only `14.2%` at collapse.
- VHK remains `78.3%` of ATP consumption, whereas VPFK has already fallen to `8.2%`.

Decision:

- Attribute ATP collapse to exhaustion of the initial VPGK/B13PG production pulse combined with persistent VHK-dominated demand; VPK partially compensates but cannot close the deficit.
- The sequence is not a primary VPFK affinity/capacity defect and does not justify reopening `km_ATP_PFK` or `vmax_VPFK`.
- Next reconstruct the exact J1-J3 B13PG balance `VGAPDH - VPGK - VDPGM`, including GAPDH redox drive and Rapoport-Luebering diversion, before changing any production or demand parameter.

Artifacts:

- `Simulations/brodbar/hermes/atp_transition_v6pgd_0.900_ppp_context_J1_J10/decision_report.md`
- `Simulations/brodbar/hermes/atp_transition_v6pgd_0.900_ppp_context_J1_J10/summary.json`
- `Simulations/brodbar/hermes/atp_transition_v6pgd_0.900_ppp_context_J1_J10/atp_window_balances.csv`
- `Simulations/brodbar/hermes/atp_transition_v6pgd_0.900_ppp_context_J1_J10/atp_reaction_attribution.csv`
- `Simulations/brodbar/hermes/atp_transition_v6pgd_0.900_ppp_context_J1_J10/candidate_seed_reaction_deltas.csv`
- `Simulations/brodbar/hermes/atp_transition_v6pgd_0.900_ppp_context_J1_J10/atp_transition_attribution.png`

## J1-J3 B13PG Balance and Initialization Provenance Audit

Date: 2026-08-11

Run:

- `Simulations/brodbar/hermes/b13pg_balance_v6pgd_0.900_ppp_context_J1_J3`
- Runner: `scripts/audit_b13pg_balance_v6pgd_ppp_context.py`

Contract:

- Replayed the saved balanced seed and retained `vmax_V6PGD = 9.0` point over J1-J3 with their fixed constrained PPP initializations.
- Reconstructed `dB13PG/dt = VGAPDH - VPGK - VDPGM` and the native low-pool damping exactly, using windows J1-J1.1, J1.1-J1.3, J1.3-J1.6, J1.6-J2, and J2-J3.
- Audited the experimental workbook and historical initialization workbook to determine whether B13PG and B23PG provide independent observations.
- Performed no optimization and promoted neither kinetics nor initial states.

Provenance and closure:

- The B13PG and B23PG experimental curves are pointwise identical, with maximum absolute difference `0.0 mM` and shared J1 value `3.584045 mM`.
- B23PG is mapped as a supported calibration target; B13PG is absent from the target map but still receives the duplicated J1 value during generic experimental initialization.
- The effective B13PG balance closed with maximum error `0.0 mM/day` for seed and candidate.

Production-drainage attribution:

- Candidate B13PG falls below `1%` of its initial value on day `1.270` and below the native damping threshold on day `1.275`.
- From J1 to J3, VGAPDH supplies `0.62170 mM`, while VPGK plus VDPGM drain `4.21056 mM`; the replacement fraction is only `14.77%`.
- VPGK accounts for `89.92%` of drainage and produces `3.78610 mM` ATP. VDPGM accounts for `10.08%`, diverting `0.42446 mM` into the Rapoport-Luebering branch.
- GA3P occupancy remains approximately `0.99`, but the GAPDH NAD/NADH drive decreases from `0.3203` at J1 to `0.0195` over J2-J3. The sustained replacement defect is redox-controlled rather than caused by GA3P scarcity.
- After the duplicated stock is exhausted, VGAPDH replaces `98.5-99.1%` of local drainage, but only at a B13PG pool near `1e-5 mM`; it cannot sustain the initial PGK ATP pulse.

Decision:

- Reclassify B13PG(0) as a non-independent latent initialization and keep B23PG locked to its measured trajectory.
- Do not use the current early VPGK pulse to identify `vmax_VPGK`, `vmax_VGAPDH`, or redox affinities.
- Next build a reversible, bounded B13PG(0)-only initialization diagnostic at fixed kinetics, preserving `3.584045 mM` as the explicit revert branch. Replay J1-J3 before any guarded J1-J10 extension.

Artifacts:

- `Simulations/brodbar/hermes/b13pg_balance_v6pgd_0.900_ppp_context_J1_J3/decision_report.md`
- `Simulations/brodbar/hermes/b13pg_balance_v6pgd_0.900_ppp_context_J1_J3/summary.json`
- `Simulations/brodbar/hermes/b13pg_balance_v6pgd_0.900_ppp_context_J1_J3/b13pg_window_attribution.csv`
- `Simulations/brodbar/hermes/b13pg_balance_v6pgd_0.900_ppp_context_J1_J3/b13pg_transition_timeseries.csv`
- `Simulations/brodbar/hermes/b13pg_balance_v6pgd_0.900_ppp_context_J1_J3/initialization_provenance.json`
- `Simulations/brodbar/hermes/b13pg_balance_v6pgd_0.900_ppp_context_J1_J3/b13pg_balance_provenance.png`

## Reversible B13PG(0)-Only Constrained Initialization Screen

Date: 2026-08-11

Run:

- `Simulations/brodbar/hermes/b13pg_constrained_initialization_screen_J1_J10`
- Runner: `scripts/screen_b13pg_constrained_initialization.py`

Contract:

- Retained the balanced PPP context with fixed `vmax_V6PGD = 9.0` and changed no kinetic constant.
- Varied only B13PG(0); B23PG(0) remained locked to `3.584045 mM`, and every other initial state remained unchanged.
- Preserved the duplicated B13PG value as the explicit revert branch and screened deterministic `0.25x`, `0.5x`, `1x`, `2x`, `4x`, and `8x` scales around the exact J1 quasi-steady root.
- Required exact B13PG and ATP closure, positivity, NAD/NADH validity, B23PG trajectory non-inferiority, and at least `95%` removal of duplicated-stock drainage before any J1-J10 extension.
- Used BDF at `0.005-day` output resolution because the Windows LSODA path was unstable in the submicromolar B13PG regime. No optimization or promotion was performed.

Exact root and pulse removal:

- The unique J1 root is `B13PG(0) = 1.76677669e-4 mM`, only `4.92956e-5` of the duplicated `3.584045 mM` initialization.
- The effective J1 derivative at the root is `-6.35e-15 mM/day`; replay closure is `0.0 mM/day` for B13PG and `2.22e-15 mM/day` for ATP.
- Stock-supported B13PG drainage falls `3.59763 -> 0.006647 mM`, a `99.82%` reduction.
- Integrated J1-J3 VPGK ATP yield falls `3.79502 -> 0.60803 mM`, while VDPGM shunt supply falls `0.42427 -> 0.02825 mM`.

Guard conflict:

- B23PG(0) remains exactly locked, but B23PG day-3 concentration falls from `2.86937` to `2.50318 mM`; B23PG nRMSE worsens `0.05626 -> 0.12663` (`2.25x`).
- ATP nRMSE worsens `0.75688 -> 0.91673` (`1.21x`), and ATP crosses `0.01 mM` on day `2.075` instead of day `2.725` in the revert branch.
- The root passes every short-horizon gate except B23PG trajectory non-inferiority. No candidate qualified for J1-J10 transfer.

Decision:

- Reject B13PG-only initialization as a guarded replacement and retain the duplicated value as the explicit revert branch.
- The duplicated B13PG stock artificially supports two coupled observables: the early VPGK ATP pulse and VDPGM supply to measured B23PG.
- Promote neither the QSS root nor any kinetic constant.
- Next audit `dB23PG/dt = VDPGM - V23DPGP` in the revert and QSS-B13PG contexts before opening B13PG/B23PG initializations or shunt kinetics.

Artifacts:

- `Simulations/brodbar/hermes/b13pg_constrained_initialization_screen_J1_J10/decision_report.md`
- `Simulations/brodbar/hermes/b13pg_constrained_initialization_screen_J1_J10/summary.json`
- `Simulations/brodbar/hermes/b13pg_constrained_initialization_screen_J1_J10/diagnostic_initializations.json`
- `Simulations/brodbar/hermes/b13pg_constrained_initialization_screen_J1_J10/short_screen_metrics.csv`
- `Simulations/brodbar/hermes/b13pg_constrained_initialization_screen_J1_J10/short_screen_assessments.csv`
- `Simulations/brodbar/hermes/b13pg_constrained_initialization_screen_J1_J10/short_screen_timeseries.csv`
- `Simulations/brodbar/hermes/b13pg_constrained_initialization_screen_J1_J10/b13pg_initialization_screen.png`

## Whole-Model and FLA State Audit

Date: 2026-08-11

Run:

- `output/model_fla_state_audit_2026_08_11`
- Runner: `scripts/audit_model_fla_state.py`

Contract:

- Audited the executable ODE, parsed stoichiometry, parameter reachability, Brodbar observability, initialization provenance, current FLA candidates, and fixed 46-day model behavior.
- Compared an exact legacy network replay, corrected SAM stoichiometry with legacy initialization, and corrected SAM stoichiometry with compartment-strict historical initialization at the same kinetic seed.
- Performed no kinetic optimization and promoted no initial state.

Structural findings and corrections:

- The audited model contains 114 dynamic states, 109 reaction/rate terms, 97 parsed stoichiometric reactions, and 201 parameters exposed to the structural map after restoring numeric reaction names to the parameter parser.
- Corrected `VSAM` to `MET + ATP -> ADOMET + Pi + PPi`; the previous additional AMP coproduct duplicated the transferred adenosyl moiety. `legacy_amp_coproduct` remains available for exact historical replay.
- Replaced hidden extracellular GSH/GSSG loss terms with explicit `VEGSH_deg` and `VEGSSG_deg` reactions, preserving the numerical law while exposing it to FLA.
- Added `legacy_experimental_alias`, `compartment_strict_generic`, and `compartment_strict_historical` initialization policies. The legacy initializer contains five cross-compartment aliases.
- Detected two exact duplicated Brodbar row pairs: B13PG/B23PG and P2G/P3G. B13PG and P2G are quarantined from independent aggregate weighting pending source verification.

Fixed-replay findings:

- Correcting SAM is structurally required but does not materially improve the whole-panel concentration fit; it reduces artificial adenylate retention.
- Strict historical initialization modestly improves the aggregate score but worsens key PPP, glycolytic, lactate, and adenylate safeguards. It remains diagnostic only.
- The seed fits EGLC comparatively well but retains high GLC, G6P, and F6P, near-zero terminal ATP/B23PG, low LAC, and insufficient ELAC accumulation.
- The dominant calibration limitation is therefore not optimizer budget. It is the combined identifiability of latent initial states and neighboring kinetic fluxes under incomplete observations.

Decision:

- Adopt network version `airbc-rbc-2026.08.11` for new work while preserving explicit legacy replay modes.
- Do not launch a broader Optuna campaign.
- The B23PG balance, duplicated-row provenance, transport scaling, temporal-block, and identifiability analyses are now complete; the next scope is `vmax_VDPGM` alone in J1-J3.

Artifacts:

- `output/model_fla_state_audit_2026_08_11/model_fla_state_report.md`
- `output/model_fla_state_audit_2026_08_11/model_fla_state_summary.json`
- `output/model_fla_state_audit_2026_08_11/configuration_metabolite_metrics.csv`
- `output/model_fla_state_audit_2026_08_11/configuration_summary.csv`
- `output/model_fla_state_audit_2026_08_11/fla_candidate_snapshot.csv`
- `output/model_fla_state_audit_2026_08_11/model_fla_state_overview.png`

## Five-step pre-calibration execution (2026-08-11)

The five diagnostics requested after the whole-model audit were completed without kinetic optimization or parameter promotion.

1. **Exact B23PG balance:** `dB23PG/dt = VDPGM - V23DPGP` closes exactly. Removing the duplicated B13PG initial stock removes `93.34%` of J1-J3 VDPGM supply, whereas V23DPGP changes little. The defect is assigned to insufficient VDPGM supply in the QSS-B13PG context, not excessive V23DPGP drainage.
2. **Data provenance:** the local 55-by-14 Brodbar workbook is a curated model-input table whose duplicate pairs were already present at first repository import. B13PG is now latent, B23PG is the retained BPG observation, and P2G/P3G cannot define two independent reaction teachers.
3. **Transport scaling:** 26 paired transports use equal-and-opposite concentration coefficients. This is amount-conserving only for equal effective compartment volumes. The historical hour/day rate conversion and hematocrit are not traceable, so transport constants remain frozen and interpreted as empirical per-model-day values.
4. **Temporal ownership:** FLA calibration is now sequential across J1-J3, J3-J10, and J10-J46, with cumulative safeguards and mandatory whole-horizon replay.
5. **Identifiability mask:** numeric reaction names were restored to automatic parameter parsing, yielding 109 parametrized reactions and 201 exposed parameters. Local SVD/QR sensitivity bases were computed in both B13PG contexts. The next executable scope is one-dimensional: `vmax_VDPGM` only. V23DPGP and all later-block parameters remain fixed.

Primary artifacts:

- `Simulations/brodbar/hermes/b23pg_balance_qss_b13pg_context_J1_J3/summary.json`
- `output/brodbar_data_provenance_2026_08_11/provenance.json`
- `output/transport_scaling_audit_2026_08_11/summary.json`
- `output/fla_temporal_contract_2026_08_11/summary.json`
- `output/fla_identifiability_mask_2026_08_11/summary.json`

Next execution: a reversible one-dimensional screen of `vmax_VDPGM` at fixed QSS-B13PG initialization, with J1-J3 attribution first and sequential extension only after all guards pass.

## QSS-B13PG one-factor vmax_VDPGM screen (2026-08-11)

Run:

- `Simulations/brodbar/hermes/vmax_vdpgm_qss_b13pg_screen_J1_J46`
- Runner: `scripts/screen_vmax_vdpgm_qss_b13pg.py`

Contract:

- Fixed the exact QSS B13PG(0), measured B23PG(0), seven PPP latent states, V23DPGP kinetics, and every parameter except `vmax_VDPGM`.
- Evaluated `0.5x, 1x, 2x, 4x, 8x, 16x, 32x` deterministically with no Optuna optimization.
- Required exact B13PG, B23PG, P3G, and ATP balance reconstruction plus positivity, redox, ATP-pulse, concentration, temporal-transfer, and whole-panel guards.

Results:

- J1-J3 B23PG nRMSE improved monotonically from `0.47409` at `1x` to `0.22445` at `32x`; the teacher-required VDPGM supply fraction increased from `3.74%` to `48.7%`.
- `2x-32x` passed J1-J3. Higher capacity did not recreate the duplicated-stock VPGK ATP pulse.
- `8x, 16x, 32x` failed J1-J10 because F6P nRMSE exceeded the cumulative `10%` non-inferiority guard.
- `2x` and `4x` passed J1-J10 and J1-J46, including aggregate whole-panel mean/median safeguards.
- At J46, B23PG nRMSE improved `0.56807 -> 0.55413 -> 0.52777` for seed, `2x`, and `4x`. The whole-panel mean nRMSE changed only `8.2489 -> 8.2550 -> 8.2588`, within the declared guard, while F6P, GLC, and ELAC regressed more at `4x` than at `2x`.
- ATP still fell below `0.01 mM` near day `2.1` in all retained branches; the screen improves B23PG handling but does not solve the energy defect.
- VDPGM had not plateaued at `32x`: integrated J1-J3 supply rose another `44.5%` from `16x`, although mean B13PG occupancy was only `0.00402` and GAPDH redox drive `0.0499`.

Decision:

- Retain `2x-4x` as a reversible diagnostic bracket, with `2x` (`vmax_VDPGM = 2.99439`) as the conservative anchor.
- Promote neither value. The current observations do not select a unique point, ATP remains unsustainable, and the larger B23PG benefit at `4x` trades against F6P/GLC/ELAC margins.
- Next refine only the `2x-4x` Pareto interval on a narrow deterministic grid. Do not open another parameter.

## vmax_VDPGM Pareto refinement (2026-08-11)

Run:

- `Simulations/brodbar/hermes/vmax_vdpgm_qss_b13pg_pareto_refinement_J1_J46`
- Runner: `scripts/refine_vmax_vdpgm_pareto.py`

Contract:

- Fixed the QSS-B13PG initialization, B23PG(0), V23DPGP, PPP states, and every kinetic constant except `vmax_VDPGM`.
- Replayed `2x, 2.5x, 3x, 3.5x, 4x` over J1-J3, J1-J10, and J1-J46 without adaptive optimization.
- Minimized B23PG nRMSE, endpoint error, and slope nRMSE against the transfer costs F6P, GLC, and ELAC nRMSE at J46.
- Used min-max normalization on the predeclared grid, pivoted no weights after observing results, and required an interior point to improve the best anchor distance by at least `5%`.

Results:

- All five points passed exact balance, positivity, redox, temporal, ATP-collapse non-inferiority, and whole-panel guards.
- `2x` minimized the transfer cost; `4x` minimized the B23PG objective. The non-dominated front therefore preserved the expected mechanistic tradeoff.
- `3x` minimized the six-objective ideal distance at `0.77357`, compared with `0.98353` for the best endpoint anchor, an improvement of `21.35%`.
- At J46, the `3x` point gave B23PG nRMSE `0.54287`, B23PG endpoint error `0.27792`, F6P nRMSE `19.0808`, GLC nRMSE `6.31764`, and ELAC nRMSE `0.39431`.
- The strict-solver check (`rtol=1e-5`, `atol=1e-8`) independently retained `3x`; its compromise improvement was `21.11%`. Selection was invariant even though some individual normalized metrics remained solver-sensitive.

Decision:

- Retain `3x`, corresponding to `vmax_VDPGM = 4.49158`, as the interior diagnostic Pareto anchor.
- Do not promote the parameter. ATP still collapses, uncertainty is not quantified by profile likelihood, and numerical robustness is not external biological validation.
- Stop DPGM capacity refinement. Next re-audit ATP production/consumption and VPGK-versus-VDPGM partitioning in the fixed `3x` branch before considering any coupled upstream lever.

## Fixed-3x ATP and VPGK/VDPGM attribution (2026-08-11)

Run:

- `Simulations/brodbar/hermes/atp_partition_vdpgm_3x_qss_b13pg_J1_J3`
- Runner: `scripts/audit_atp_partition_vdpgm_3x_qss_b13pg.py`

Contract:

- Replayed the identical QSS-B13PG state and fixed V6PGD/PPP kinetics in both branches.
- Changed only `vmax_VDPGM`, from `1.49719` to the diagnostic `4.49158` (`3x`).
- Reconstructed exact ATP and B13PG balances over five early windows plus J1-J3, with reaction-level ATP attribution.

Results:

- ATP and B13PG pointwise closure errors were at most `3.55e-15` and `0` mM/day.
- Integrated VGAPDH supply changed by `+0.0048%`, and mean GAPDH redox drive by `+0.0050%`; upstream supply was effectively invariant.
- Integrated VDPGM increased `171.08%`, while VPGK decreased `7.98%`. The VPGK share of B13PG drainage fell from `95.58%` to `88.00%`.
- Total ATP production decreased `1.44%`; the VPGK decrease explained `99.52%` of that gross production loss.
- ATP consumption decreased `1.14%` in response. VNDPK, VHK, VRKa, and VPFK represented about `42.0%`, `23.3%`, `16.1%`, and `7.1%` of this compensatory relief.
- ATP at day 3 changed from `0.002054` to `0.001914 mM`; the `0.01 mM` crossing advanced from day `2.073` to `2.066`.

Decision:

- Assign the perturbation to diversion of B13PG from ATP-producing VPGK into the Rapoport-Luebering branch under unchanged GAPDH/redox supply.
- Keep `3x` as a reversible B23PG diagnostic anchor only. Do not promote it and do not open another kinetic constant yet.
- Next reconstruct VPGK required by measured ATP and native ATP demand, then infer the corresponding VGAPDH requirement under fixed `3x` partitioning.

## ATP-teacher-required VPGK and VGAPDH reconstruction (2026-08-31)

Run:

- `Simulations/brodbar/hermes/atp_teacher_required_vpgk_vgapdh_3x_qss_J1_J3`
- Runner: `scripts/reconstruct_atp_teacher_required_fluxes.py`

Contract:

- Kept the complete fixed `vmax_VDPGM = 3x` QSS-B13PG replay unchanged; no kinetic parameter was optimized.
- Reconstructed `VPGK_required = dATP_teacher/dt + ATP_consumption - VPK - VAK` from the Brodbar ATP curve and native reaction-resolved fluxes.
- Reconstructed `VGAPDH_required = dB13PG/dt + VPGK_required + VDPGM` under both a QSS B13PG derivative and the native latent B13PG derivative. The duplicated B13PG workbook row was not used.
- Used full-record PCHIP as the primary teacher and the J1-J4 secant slope as a sensitivity analysis.

Results:

- Only one ATP observation, day 1, lies inside J1-J3; the next observation is day 4. The teacher is therefore temporally weak inside the early block.
- PCHIP and linear reconstructions nevertheless agreed on the integrated VPGK requirement within `0.014%`.
- Integrated VPGK requirement was `1.58942 mM`, `2.835x` the native `0.56071 mM`.
- `VPGK_required` ranged from `-0.2293` to `7.6708 mM/day` and first became negative at day `1.453`. It was nonnegative for `97.30%` of the grid but cannot be represented pointwise by the current irreversible rate law with all other ATP terms frozen.
- The current VPGK hard ceiling `40.0226 mM/day` was not exceeded. At the fixed replayed states, however, the median and p95 required `vmax_VPGK` were `63.48` and `170.42`, showing that increasing capacity alone would be strongly state-coupled.
- Under QSS B13PG, integrated VGAPDH requirement was `1.66589 mM`, `2.646x` native. Its peak `7.9339 mM/day` exceeded the current hard ceiling `6.3899`, beginning at day 1; the integrated excess was `0.02764 mM`.
- Replacing QSS with the native latent B13PG derivative barely changed the result (`2.6455x` native), so B13PG derivative policy is not the source of the incompatibility.

Decision:

- Do not calibrate `vmax_VPGK`, `vmax_VGAPDH`, redox constants, or ATP-demand kinetics from ATP alone.
- The integrated energy requirement is robust to the interpolation choice, but the pointwise inversion is sign-infeasible and the ATP teacher is sparse within J1-J3.
- Next reconstruct the joint ATP, ADP, and AMP teacher balances and audit adenylate-kinase directionality before opening another kinetic lever.

## Joint ATP-ADP-AMP balance and adenylate-kinase audit (2026-08-31)

Run:

- `Simulations/brodbar/hermes/joint_adenylate_balance_3x_qss_J1_J3`
- Runner: `scripts/audit_joint_adenylate_balances.py`

Contract:

- Kept the fixed `vmax_VDPGM = 3x` QSS-B13PG branch and all kinetic constants unchanged.
- Reconstructed the exact native ATP, ADP, and AMP balances and the corrected total-pool identity
  `d(ATP+ADP+AMP)/dt = VAK2 - VSAM + VADSL + VAPRT - VAMPD1`.
- Split net adenylate kinase into forward `2 ADP -> AMP + ATP` and reverse `AMP + ATP -> 2 ADP` components.
- Used PCHIP teachers for ATP, ADP, and AMP, with J1-J4 linear slopes as a sensitivity analysis. Each pool still has only one direct observation inside J1-J3.

Results:

- Native ATP, ADP, AMP, VAK split, and total-pool closure errors were `0`, `0`, `0`, `0`, and `3.55e-15 mM/day`.
- The measured total adenylate teacher decreased `0.10187 mM` from J1 to J3, while the model increased `0.46368 mM`.
- The integrated correction required in the total-pool balance was `-0.56481 mM`; non-negativity damping accounted for only `+0.00072 mM` and cannot explain the discrepancy.
- VAK cancels from the total pool. Native VAK remained forward for `100%` of J1-J3, whereas the exact joint correction required reverse VAK for `100%`, ranging from `-0.55685` to `-0.01782 mM/day`. The current hard direction bounds covered `92.7%` of this required trajectory.
- Separate ATP-, ADP-, and AMP-based VAK reconstructions had integrated values `2.97845`, `1.39495`, and `-0.75337 mM`, with a mean pointwise spread of `1.86591 mM/day`. A single VAK trajectory cannot reconcile all three teachers under native total-pool ownership.
- Native total-pool creation was dominated by VAPRT (`+0.53882 mM`), then VADSL (`+0.09548`) and VAK2 (`+0.01561`). VAMPD1 and VSAM removed `0.15553` and `0.03143 mM`.
- A VAPRT-only inversion required `-0.02599 mM` integrated flux and was nonnegative for only `8.8%` of J1-J3. Complete VAPRT suppression is therefore necessary but still insufficient.
- If assigned to one sink alone, the required integrated VAMPD1 and VSAM fluxes were `0.72034` and `0.59624 mM`. VAMPD1 is the more direct mechanistic diagnostic because it removes AMP to IMP, whereas VSAM removes ATP into ADOMET.
- PCHIP and linear total-pool corrections differed by only `0.44%`, so the direction and scale of the defect are robust to this interpolation choice despite sparse sampling.

Decision:

- Do not calibrate VAK or VAK_rev first. Its direction is wrong, but it cannot repair the total adenylate source/sink mismatch.
- Prioritize a reversible fixed-parameter `VAPRT = 0` replay. Then quantify, without fitting, the residual VAMPD1 sink needed under safeguards on IMP, ADE, PRPP, ATP, ADP, AMP, and total adenylate.
- Keep VSAM as a secondary alternative only because changing it directly perturbs ATP and ADOMET.

## Reversible VAPRT suppression and residual VAMPD1 requirement (2026-09-04)

Run:

- `Simulations/brodbar/hermes/vaprt_zero_vampd1_requirement_3x_qss_J1_J3`
- Runner: `scripts/diagnose_vaprt_suppression_vampd1_requirement.py`

Contract:

- Kept the fixed `vmax_VDPGM = 3x` QSS-B13PG state and every kinetic constant unchanged except `vmax_VAPRT`, which was set from `4.08799` to `0` without optimization.
- Replayed the baseline and VAPRT-suppressed branches over J1-J3, reconstructed the exact ATP, ADP, AMP, IMP, ADE, PRPP, ADOMET, adenylate-kinase, and total-adenylate balances, and required state positivity.
- Compared ATP, ADP, AMP, IMP, and ADE against Brodbar PCHIP teachers. PRPP and ADOMET, which are not observed in this dataset, were retained as latent positivity and non-divergence safeguards.
- Reconstructed the residual sink directly from
  `VAMPD1_required = VAK2 - VSAM + VADSL + VAPRT - d(ATP+ADP+AMP)_teacher/dt`.
- Used the J1-J4 linear teacher as an interpolation sensitivity analysis and repeated the complete replay with `rtol=1e-5`, `atol=1e-8`.

Results:

- Exact balance closure was preserved; the largest candidate total-adenylate residual was `3.89e-15 mM/day`, and every modeled state remained at or above `1e-6 mM`.
- Suppressing VAPRT changed the J1-J3 total-adenylate trajectory from `+0.46368` to `-0.07310 mM`, close to the PCHIP teacher change of `-0.10187 mM`.
- Total-adenylate nRMSE improved from `0.30122` to `0.00824`. ATP nRMSE was non-inferior (`1.12458 -> 1.12467`), while AMP, IMP, and ADE improved from `6.55470 -> 5.14412`, `0.42329 -> 0.26983`, and `4.41204 -> 0.14011`, respectively. ADP changed only from `1.70694` to `1.70707`.
- The native VAMPD1 integral after VAPRT suppression was `0.15355 mM`; the teacher-required integral was `0.18163 mM`, leaving an additional sink requirement of `0.02807 mM`.
- The required VAMPD1 trajectory was positive throughout J1-J3 and ranged from `0.04408` to `0.09787 mM/day`, but it remained below the current `vmax_VAMPD1 = 0.08301` for only `11.2%` of the interval.
- At the fixed replayed states, the required `vmax_VAMPD1` median, p95, and maximum were `0.10295`, `0.10397`, and `0.10399`, corresponding to approximately `1.24-1.25x` the seed.
- The linear-teacher reconstruction gave a similar required integral (`0.17915 mM`). The strict-solver replay retained the same classification, p95 target (`0.10398`), and total-pool nRMSE (`0.00824`).
- PRPP increased to `0.11686 mM` at day 3 but remained positive and finite; ADOMET remained positive and essentially unchanged.

Decision:

- Retain `VAPRT = 0` as a reversible structural diagnostic, not as a promoted whole-model parameter. Its effect strongly localizes the early total-adenylate defect to APRT activity under the current storage-model context.
- Next screen `vmax_VAMPD1` deterministically at `1.0x, 1.1x, 1.2x, 1.25x, 1.3x, 1.4x, 1.5x` under fixed VAPRT suppression, with no Optuna optimization.
- Select the smallest capacity that improves total-adenylate trajectory, slope, endpoint, and AMP while preserving ATP, ADP, IMP, ADE, PRPP, ADOMET, positivity, exact balances, and VAK directionality guards. Validate sequentially over J1-J3, J1-J10, then J1-J46.

## Deterministic VAMPD1 screen under fixed VAPRT suppression (2026-09-04)

Run:

- `Simulations/brodbar/hermes/vmax_vampd1_vaprt_zero_screen_J1_J46`
- Runner: `scripts/screen_vmax_vampd1_vaprt_zero.py`

Contract:

- Fixed the `3x` QSS-B13PG state, set `vmax_VAPRT = 0`, and varied only `vmax_VAMPD1` over `1.0x, 1.1x, 1.2x, 1.25x, 1.3x, 1.4x, 1.5x` relative to the `0.0830092` seed.
- Used no Optuna or adaptive search. The selection rule was fixed in advance: retain the smallest capacity improving total-adenylate trajectory, slope, endpoint, AMP, and the VAMPD1 teacher flux while preserving ATP, ADP, IMP, ADE, PRPP, ADOMET, non-negativity, exact balances, and VAK directionality.
- Replayed all points over J1-J3, only eligible points over J1-J10, and only relay survivors over J1-J46. The J46 gate additionally protected the mean and median nRMSE of the complete mapped Brodbar panel.
- Repeated the full sequential screen with `rtol=1e-5` and `atol=1e-8`.

Results:

- J1-J3 retained `1.1x, 1.2x, 1.25x, 1.3x`; `1.4x` and `1.5x` over-corrected at least one target. All four early candidates passed J1-J10.
- Standard J1-J46 retained `1.1x, 1.2x, 1.25x`. The `1.3x` point failed only VAK directionality.
- The strict replay retained `1.1x` and `1.2x`. The `1.25x` forward-VAK time fraction was `0.53026`, below the predeclared baseline-minus-`0.01` threshold of `0.53248`; `1.3x` failed the same guard.
- The smallest fully guarded candidate was therefore `1.1x`, or `vmax_VAMPD1 = 0.0913101`. This selection was invariant to solver tolerance even though the upper admissible boundary was not.
- At J1-J3, the selected point improved total-pool nRMSE `0.00824 -> 0.00343`, slope nRMSE `0.33825 -> 0.22522`, endpoint error `0.01691 -> 0.00791`, AMP nRMSE `5.14271 -> 5.11861`, IMP nRMSE `0.26965 -> 0.26118`, and VAMPD1 teacher-flux nRMSE `0.18529 -> 0.12226`.
- At J1-J46, improvements remained for total-pool nRMSE (`0.33313 -> 0.24452`), slope (`1.12329 -> 1.11315`), endpoint (`0.39026 -> 0.20607`), AMP (`5.31243 -> 4.90597`), IMP (`1.00544 -> 0.99646`), and VAMPD1 teacher flux (`0.87426 -> 0.86660`). ATP and ADP were effectively invariant.
- The J46 whole-panel mean changed `7.99355 -> 8.01444` (`+0.261%`) and the median `0.91775 -> 0.91748` (`-0.029%`), both well inside the `5%` guard. Maximum selected balance error was `2.03e-15 mM/day`; all states remained nonnegative.
- Strict selected metrics remained close: total nRMSE `0.24481`, slope nRMSE `1.11339`, endpoint error `0.20689`, AMP nRMSE `4.90742`, and whole-panel mean `8.01422`.
- During J46 QA, the independent VAK split was aligned with the ODE's `1e-6 mM` substrate floor. This corrected the audit closure at depleted ATP/ADP states without changing the ODE or any kinetic law.

Decision:

- Retain `1.1x` as the conservative reversible VAMPD1 diagnostic anchor under VAPRT suppression. Treat `1.1x-1.2x` as the solver-robust admissible interval.
- Promote neither `VAPRT = 0` nor `vmax_VAMPD1 = 0.0913101` globally. AMP remains poorly reproduced, and PRPP/ADOMET approach depletion by J46 despite passing non-negativity guards.
- Next audit the exact IMP source/sink balance and linked ADE/PRPP transfer under the fixed `1.1x` anchor before opening another parameter or deciding whether APRT suppression must be bounded or time dependent.

## Exact IMP and purine-transfer audit under the VAMPD1 anchor (2026-09-04)

Run:

- `Simulations/brodbar/hermes/imp_purine_transfer_vampd1_1p1_vaprt_zero_J1_J46`
- Runner: `scripts/audit_imp_purine_transfer_vampd1_anchor.py`

Contract:

- Consumed the validated standard and strict replays from the deterministic VAMPD1 screen; no ODE was refitted and no kinetic parameter changed.
- Compared the fixed VAPRT-zero `1.0x` VAMPD1 seed and selected `1.1x` anchor over J1-J3, J1-J10, and J1-J46.
- Reconstructed pointwise `dIMP/dt = VHGPRT1 + VAMPD1 - VADSS - VIMPH - Vnucleo2`, `dADE/dt = -VEADE - VAPRT`, and `dPRPP/dt = VPRPPASe - VAPRT - VHGPRT1 - VHGPRT2`.
- Derived a conditional IMP teacher for VAMPD1, a direct adenine-pair teacher `VAPRT^T = -d(ADE^T+EADE^T)/dt`, and an independent total-adenylate teacher `VAPRT^T = dA_tot^T/dt - VAK2 + VSAM - VADSL + VAMPD1`.
- Treated the ADE+EADE sum as provisional because intracellular and extracellular measurements are combined in the current standardized/model units without an explicit volume factor.

Results:

- Maximum exact reconstruction error was `3.10e-16 mM/day`; all native ODE closure columns remained exact. The strict-screen audit preserved the same classification.
- At J1-J46, actual VAMPD1 integrated `3.76275 mM`; the IMP-conditioned teacher required `3.84357 mM`. The residual `0.08082 mM` deficit explains the modest IMP nRMSE change `1.00544 -> 0.99646` but is an order of magnitude smaller than the adenine-pool contradiction.
- The IMP anchor changed `-0.11050 mM`, compared with a teacher change of `-0.02971 mM`. Its integrated sources were VHGPRT1 `+0.92344 mM` and VAMPD1 `+3.76275 mM`; sinks were VADSS `-1.50985`, VIMPH `-2.58858`, and Vnucleo2 `-0.69831 mM`.
- In the current model, VAPRT is the only net sink of the combined ADE+EADE pair. The experimental pair decreased by `0.99211 mM`, whereas `VAPRT = 0` conserved the modeled pair to machine precision. The direct teacher therefore required `+0.99211 mM` integrated APRT and remained positive for `100%` of J1-J46.
- The total-adenylate teacher required `-0.34019 mM` integrated APRT over J1-J46. Window requirements were negative over J1-J3 (`-0.01276`), J3-J10 (`-0.19641`), J10-J21 (`-0.40133`), and J35-J46 (`-0.23114`), but positive over J21-J35 (`+0.50145 mM`).
- The adenine-pair and total-pool APRT teachers disagreed by `1.33229 mM` integrated. The strict replay gave `-0.34046 mM` for the total-pool requirement and the same `+0.99211 mM` adenine-pair requirement.
- PRPP was already overdrawn without APRT: integrated VPRPPASe production was `+0.12595 mM`, while VHGPRT1 and VHGPRT2 consumed `0.92344` and `0.20720 mM`. PRPP ended at `7.23e-6 mM`; adding the direct APRT requirement would be mass-infeasible under this ownership.
- VAK first became reverse near day `3.725` and changed net direction twice by J46. The VAMPD1 anchor did not repair the broader purine panel: ADE, EADE, HYPX, and INO nRMSE remained `4.64480`, `4.34949`, `4.99860`, and `6.61959`.

Decision:

- Reject hard `VAPRT = 0` as a globally promotable mechanism because it violates the measured ADE+EADE amount trend under the current scale. Retain it only as an attribution branch.
- Do not restore positive APRT alone. It would worsen total adenylate and requires PRPP that the current model cannot supply.
- Resolve the intracellular/extracellular adenine scaling first. If the conflict persists over plausible volume factors, test an explicit reversible EADE-loss option against bounded APRT at fixed kinetics before any calibration.

## 2026-09-08 - Consolidated model/FLA review and validation repair

This entry supersedes earlier next-step recommendations. Full review: `tasks/fla_model_review_2026_09_08.md`; active handoff: `tasks/fla_current_tasks.md`. Three requested agents (Raman, Dewey, Poincare) failed on usage quota before reporting. The parent completed the review locally; no additional agents, new kinetic fit, or promotion.

### Intervening work recovered from artifacts

- ADE/EADE compartment scaling did not resolve the teacher sign conflict over the tested range. The purine-structure inverse problem remains non-identifiable without additional assumptions.
- A seven-capacity AMP nucleotidase screen rejected a constant positive AMP-to-ADO sink at fixed kinetics, including a negative required late integrated sink.
- Storage-dependent VAMPD1 improved fixed-state teacher fitting but only improved the free-run combined trajectory objective by about 2.92%; the IMP endpoint worsened. No promotion.
- VADSS-specific GTP-affinity mapping improved a fixed-state score but all five full-ODE candidates failed joint guards. No promotion.
- ATP falls below 0.01 mM near J2.1 in the archived VAMPD1-decay candidate and ends at 2.7094e-5 mM versus 0.46976 mM in the table. This is a global predictive failure, not a useful calibrated ATP trajectory.
- External manifest retains 40 Bardyn control, 37 supplemented and 28 Michel rows after conservative placeholder quarantine. External predictive validation has not been completed.

### Demonstrated defects and corrections

- **P1 structural parser**: reaction names starting with a digit after V were excluded from stoichiometric extraction. Restored V6PGD and V23DPGP, including PPP redox and B23PG/P3G coefficients. Schema revision 2, 100 nonzero stoichiometric reactions. ODE equations/kinetics remain unchanged at network version airbc-rbc-2026.09.04.
- **P1 numerical accounting**: distinguish raw S v from the derivative after pool-wise damping. Eight positive-state full-network audits close within 7.11e-15 mM/day. Depleted-state tests show raw nonconservation even when the effective reconstruction is exact. On the archived adenylate replay, the numerical/raw discrepancy reaches 0.0073571 mM/day and integrates to about +0.0109917 mM. This is not an experimental source and does not explain the entire ATP collapse.
- **P1 validation**: revision 3 now requires pre-clipping minimum evidence, raw balance closure, continuous unforced replay and predeclared absolute accuracy limits on protected targets. Limits remain unset pending measurement-contract justification, so absent evidence blocks promotion. Invalid errors and unsupported holdout claims fail closed.
- **P2 exports/teachers**: malformed dimensions and nonfinite values are rejected before CSV creation; missing flux samples are no longer filled with zero. Integrated teachers reject nonfinite values and invalid scales/tolerances. Signed fluxes remain supported.
- **P2 segmented diagnostic**: discontinuity loss was recorded, not penalized by an optimizer. Corrected elapsed ATP availability is 2.36565% free versus 26.52987% reset, replacing sample fractions 2.44173%/28.24716%. Reset gains are not sensitivity or predictive evidence. No multiple-shooting calibration is claimed.
- **P2 interpretation**: NDPK counterfactual replaced both ATP and ADP, not ATP alone. Signed production/consumption groups contain reversible AK/NDPK; a negative group is not an irreversibility proof. Corrected the runners and regenerated separate review outputs.
- Updated manuscript inventory to 114 default states, 110 reaction/rate identifiers, 100 parsed reactions, and 204 non-hybrid structural parameter names. Added interval teachers, conditional attribution, proposed continuity objective, raw/effective numerical gates and recent negative results.

### Artifacts and verification

- `output/fla_review_2026_09_08/evidence.json`: deterministic full-state probes, corrected durations, archived adenylate residual, input hashes.
- `output/fla_review_2026_09_08/validation_policy/contract.json`: policy revision 3; absolute thresholds explicitly unset.
- `output/fla_review_2026_09_08/atp_sustainability/` and `gtp_ndpk/`: regenerated audits, with corrected interpretations. Historical artifacts are preserved.
- `python -m pytest -q qa`: 512 passed, six existing Optuna experimental-feature warnings; local startup also warns about Pydantic v1 under Python 3.14. Final verification persisted in `output/fla_review_2026_09_08/qa_results.xml`.
- `git diff --check`: passed. Existing unrelated worktree changes retained.

### Next execution

1. Regenerate PPP/Rapoport-Luebering teachers, matrix ranks and parameter reachability under parser schema 2, with kinetics fixed.
2. Quantify raw/effective ATP/adenylate/redox/guanylate balance defects on standard and strict accepted-state replays. Test a reversible reaction-consistent positivity mode before a new optimization; do not add an artificial ATP source.
3. Freeze measurement provenance, absolute guard thresholds and temporal partitions, then compare short-horizon dynamic sensitivities before deciding on a continuity-constrained energy-block fit.
4. Keep purines frozen during that experiment; require continuous J1-J46 and correctly time-aligned external replay for promotion.

Open platform risks: numeric-only API parameter contract omits kinetic-family strings; custom dataset time origin is not consistently propagated; raw solver-call trackers are not accepted-state quadrature; not every historical runner uses validation revision 3. Repository-wide NumPy<2 compatibility and independent source/biological validation remain unverified.

## 2026-10-05 - Corrected PPP constraints and fixed-kinetic numerical audit

Executed the recorded next task without optimization, observation resets, kinetic changes or promotion. Runner: `scripts/audit_ppp_constraints_and_numerics.py`; reusable accounting helpers: `src/fla_balance_audit.py`; evidence: `output/ppp_numerical_audit_2026_10_05/`.

The full parameter dictionary and 114-state initialization were frozen from the unpromoted VAMPD1 storage-decay diagnostic. The reconstructed initial state matches the archived J1 row within 1e-12 mM. Source/reference/initialization hashes and predeclared numerical tolerances are persisted in `preregistered_contract.json`. Optional PHE is absent from this 114-state context and is not fabricated.

### Corrected structural supervision

- Regenerated four matrix scopes, SVD ranks/nullspaces, parameter reachability, PCHIP net-balance teachers and exact tabulated interval constraints for G6P, GO6P, F6P and B23PG over 14 reference time points (13 intervals).
- The measured PPP/shunt matrix has rank 4 of 22 subgraph columns, nullity 18; ten represented columns alone have nullity 6. Restoring V6PGD and V23DPGP removes false individual identifiability of VPGLS and VDPGM. No individual reaction flux is independently identifiable from these four balances without further assumptions.
- The seven latent PPP pools remain unobserved. Higher rank after adding their rows is hypothetical, not measured-data evidence. B13PG and P3G remain excluded from independent teachers because of duplicate-row ambiguities.
- Conditional V6PGD, VG6PDH, VDPGM and VTKL2+VTAL interval requirements are exported separately with their simulated-neighbor dependencies. Derivative and interval targets reuse the same measurements; neither resolves provenance or adds independent information.

### Numerical results

- Executed continuous BDF J1-J46 with identical parameters/states: standard rtol=3e-4/atol=1e-6, strict rtol=1e-7/atol=1e-9. Stored raw accepted states and replayed fluxes on accepted-step dense solutions, without output clipping.
- Gauss-Legendre integration splits at accepted steps and experimental/audit boundaries; orders 4 and 8 supply a preregistered convergence comparison. Strict passes all 565 pool/quantity checks; standard fails nine. This does not establish cross-solver convergence.
- Effective pointwise closure is within 3.56e-15 mM/day, while maximum raw balance defect reaches about 0.144424 mM/day across the full model. Both raw-balance gates fail; derivative clipping is inactive.
- Strict integrated damping contributes +0.0114236 mM to adenylates, partitioned as ADP +0.00887729 and ATP +0.00254635 mM. GO6P gains +0.00397148 and B13PG +0.019655 mM. Redox pair sums remain conserved within roundoff. The largest strict integrated solver residual is approximately 2e-6 mM.
- Standard and strict GO6P, ATP and adenylate correction budgets disagree beyond 1% relative +1e-5 mM absolute tolerance. The strict budget is better quadrature-resolved, not a certified tolerance-invariant value.
- Strict raw accepted B13PG and ADP minima are -1.07350e-5 and -1.15022e-6 mM. Negative depleted pools retain negative executed derivatives because a positive input floor does not make the zero boundary invariant. Non-negativity fails under both tolerances.
- Strict ATP remains about 3e-5 mM at J46 versus 0.46976 mM in the reference table; the numerical correction cannot explain the whole failure. The conditional F6P VTKL2+VTAL requirement is 0.354852 mM versus 1.717250 mM simulated, with effectively no F6P damping; that discrepancy is not numerical or an individually observed flux.

### Decision and verification

Do not reopen optimization. Next implement an opt-in reaction-consistent positivity diagnostic preserving the entire signed reaction stoichiometry, with boundary tests first and fixed-context J1-J3/J1-J10/J1-J46 replays. Keep the legacy option and frozen kinetics; inspect raw states and solver convergence. Never fit numerical repair terms as experimental sources or add an artificial ATP source. Measurement provenance and absolute predictive thresholds still require resolution before promotion.

Verification: `python -m pytest -q qa --junitxml=output/ppp_numerical_audit_2026_10_05/qa_results.xml` -> 522 passed, six existing Optuna warnings; existing Pydantic-v1/Python-3.14 startup warning. Updated active tasks and manuscript methods/results. Older artifacts and unrelated dirty-worktree changes are preserved.

## 2026-10-05 - Opt-in reaction-consistent positivity at frozen kinetics

Implemented the recorded positivity diagnostic without changing kinetic constants, promoting a candidate or changing the default legacy policy. Core helper: `src/reaction_positivity.py`, version `reaction-consistent-v1-2026.10.05`; ODE activation: `positivity_policy="reaction_consistent"`. Omit the keyword or set `"legacy"` to restore the former behavior. Numerical options are separate from the kinetic parameter dictionary; this keyword is not yet exposed by the numeric-only API.

### Construction and boundary evidence

- Each native signed net rate is multiplied by the minimum unfloored availability among its consumed states: clip(x/1e-3 mM, 0, 1). Negative net rates reverse the consumed-state set. One factor scales all contributions of the reaction column; products do not limit incoming production. Native kinetic floors remain unchanged.
- Concentration equations use the executed limited fluxes, with no independent derivative damping/clipping or nonfinite sanitization. Invalid forcing/nonfinite/oversized concentration RHS fails explicitly. pH production uses the same effective metabolic rates.
- Trackers expose executed limited rates under the option; per-call numerical audit exposes native rates, factors and derivatives. S(v_limited-v_native) is a chemical reaction-rate modification, not a numerical material source or experimental teacher. Gross forward/reverse exchange is not inferred.
- Passed 22 new regression tests, including signed reverse reactions, multireactant stoichiometry, adenylate/redox invariants, all 113 initial-state zero boundaries, pH rate parity, rejection of forcing, rollback and exact snapshot parsing.
- Passed 339 boundary probes (113 pools across the initial and archived depleted B13PG/ADP contexts). Only synthetic boundary counterparts are projected nonnegative; integrated trajectories are never clipped.

### Reproducibility and final execution

- Preliminary output: `output/reaction_positivity_fixed_2026_10_05/`, with an immutable `executed_runner.py` matching its recorded source hash. Default CSV parsing shifted 39 initialization entries by at most 4.44e-16 mM. This pass is preserved but superseded for decisions.
- Final output: `output/reaction_positivity_fixed_2026_10_05_roundtrip/`. CSV parsing now uses round-trip precision and rejects anything not exactly equal to the archived binary day-1 state. Complete legacy strict J46 accepted times and 114-state arrays reproduce the preceding audit bit-for-bit.
- Runner: `scripts/test_reaction_positivity_fixed_context.py`. Completed 12 replays: legacy/reaction-consistent, standard/strict, J1-J3/J1-J10/J1-J46. Parameter/state hashes, policy and solver thresholds were frozen before solving. No optimization, forcing, observation resets, source additions or promotion.

### Results and limits

- Reaction-consistent strict runs pass all 452 pool/quantity quadrature checks per horizon. No accepted concentration is negative. J46 minimum accepted/dense states are +8.14761e-7/+8.14731e-7 mM (accepted minimum ADP); B13PG ends at +7.47477e-6 mM.
- Maximum executed stoichiometric residual is 3.56e-15 mM/day; encoded left-nullspace residual is 4.13e-15 mM/day. Matrix rank 93, left nullity 20. This verifies encoded invariants, not independent elemental correctness.
- Nonreaction integrated adenylate/GO6P/B13PG sources vanish to roundoff versus legacy +0.0114236/+0.00397148/+0.0196545 mM. The maximum strict state-change-minus-integrated-executed-RHS residual is 1.90e-6 mM.
- Standard reaction-consistent quadrature fails 8 J10 and 16 J46 checks. At J46, all 116 pool/group state-change comparisons pass standard/strict tolerance, but five effective-balance and two rate-change integrals fail. Strict quadrature passes do not establish strict/ultrastrict convergence; the overall all-case numerical-integrity flag remains false.
- The availability modifier is strong: native/executed integrated VPGK on the new trajectory is 14.7626/0.670233 mM; VDPGM 12.1508/4.80649 mM. These are evaluations on the same trajectory, not comparisons with the separate legacy simulation. The threshold is not a validated physiological mechanism.
- ATP remains 1.64866e-5 mM at J46 versus 0.469757 mM. Postinitial GLC/ELAC/LAC nRMSE worsen 6.58931->7.04889, 0.369576->0.397191 and 0.960311->0.971356. G6P/B23PG improve 12.8854->11.3949 and 0.706404->0.639804 but remain inaccurate. The 53-row postinitial mean is 8.39423->8.37775. These exclude initial observations and duplicate aliases; J1-J3 has no postinitial measured point and no invented predictive score.

### Decision and next execution

Retain an opt-in diagnostic only; keep legacy default, kinetics, data ownership and unpromoted context unchanged. Before calibration, verify J1-J46 strict/ultrastrict convergence, then perform a predeclared availability-threshold sensitivity at fixed kinetics. Do not optimize the numerical threshold as a kinetic constant. After that, re-audit B13PG and ATP using actual executed VPGK/VDPGM, resolving measurement/absolute-accuracy contracts before selecting an energy-block fit. No artificial ATP source and no promotion based on mean error alone.

Updated manuscript methods 2.21/results 3.23 and active tasks. Decision report plus native/effective reaction budgets, raw solver arrays, postinitial metrics and inspected PNG/PDF comparisons are in the final output directory. Verification: 544 QA tests passed, six existing Optuna warnings, existing Pydantic-v1/Python-3.14 startup warning. `git diff --check` and Python compilation pass. Unrelated worktree edits and historical outputs remain intact.

## 2026-10-05 - Provisional working reference, convergence and threshold sensitivity

At the user's explicit request, adopted reaction-consistent limiting with strict BDF as the provisional reference for new campaign work, retaining legacy for historical reproduction. Profile: `config/fla_working_reference.json`; loader/options: `src/fla_working_reference.py`. Kernel, older API and historical runner defaults remain legacy; new work must explicitly load this profile. This numerical adoption does not promote the frozen, unvalidated VAMPD1 storage-decay kinetic context.

### Implementation and predeclared experiment

- Added `reaction_availability_threshold` as an ODE numerical keyword, separate from `custom_params`. Explicit overrides require reaction-consistent mode and finite positive numeric values; legacy rejects them. Omitting the threshold retains the existing 1e-3 mM law exactly. Policy version: `reaction-consistent-v2-explicit-threshold-2026.10.05`.
- Runner: `scripts/verify_fla_working_reference.py`; evidence: `output/fla_working_reference_verification_2026_10_05/`. Completed outputs cannot be overwritten. `--historical --out-dir <fresh-directory>` selects the legacy profile without modifying the working reference.
- Predeclared six continuous unforced J1-J46 replays: thresholds 1e-4, 1e-3, 1e-2 mM, each strict rtol=1e-7/atol=1e-9 and ultrastrict 1e-8/1e-10. Kinetics and round-trip initial states remain fixed; no observation resets, output clipping, threshold selection by predictive loss, optimization or kinetic promotion.
- Added individual native/executed/absolute-modifier reaction quadrature checks, in addition to the pool budgets. Orders 4/8 compare 452 pool/quantity and 300 reaction/quantity combinations over the declared intervals. Absolute/relative allowances remain 1e-6 mM +1e-3 for quadrature and 1e-5 mM +1% for strict/ultrastrict comparisons.

### Numerical results

- All 1017 zero-boundary probes pass. Legacy RHS compatibility on 24 archived states passes within 1.12e-15 mM/day. The new explicit strict reference reproduces the preceding reaction-consistent accepted times and 114-state arrays bit-for-bit.
- All six replays pass positivity, executed closure and every pool/reaction quadrature check. No raw accepted or sampled dense concentration is negative. Closure is within 3.56e-15 mM/day.
- All 978 strict/ultrastrict comparisons pass at each threshold, covering dense concentrations, interval changes, individual native/executed/modifier reaction integrals and numerical budgets. Maximum dense concentration differences are 1.28e-6 / 9.38e-7 / 1.25e-6 mM at 1e-4 / 1e-3 / 1e-2 mM. Reference solver-integral residual improves from 1.89829e-6 to 2.20075e-7 mM under ultrastrict tolerances.
- Numerical convergence is established for this frozen context and these declared tolerances, not arbitrary future parameters or biological validity. All preregistered source/data/context hashes remain unchanged after execution.

### Threshold sensitivity and decision

- Ultrastrict ATP endpoints: 1.58795e-6 / 1.64866e-5 / 1.40143e-4 mM across the three thresholds, all far below the local reference 0.469757 mM. A 100-fold threshold change produces about an 88-fold ATP change.
- Executed VPGK integrals: 0.645152 / 0.670233 / 0.939334 mM (about 46% span). Native VPGK on each corresponding trajectory: 14.6492 / 14.7626 / 60.9452 mM. These native/executed pairs are same-trajectory evaluations, not observed exchange fluxes. Executed VDPGM: 4.83265 / 4.80649 / 4.70985 mM; executed V6PGD: 3.37590 / 3.37001 / 3.43356 mM.
- Against the 1e-3 mM reference, 39/66 dense pool trajectories and 462/639 of all 978 quantities exceed the comparison band at 1e-4/1e-2 mM. These describe threshold sensitivity, not failed solver convergence.
- GLC remains approximately 10.4 mM versus 0.826365 mM; ELAC remains 16.7-16.9 mM versus 28.363716 mM. Numerical repair and convergence do not resolve predictive calibration.
- Keep reaction-consistent + strict BDF +1e-3 mM as the explicit provisional work reference, legacy historical mode retained. Do not fit the threshold to teacher or concentration loss or promote the kinetic context. Calibration remains blocked by unresolved biological/data/absolute-accuracy contracts, not by a failed numerical convergence screen.
- Next execution: audit B13PG and ATP production/consumption using executed limited VPGK/VDPGM and the complete actual balances, with native rates separately labeled as counterfactuals and threshold sensitivity retained in interpretation. Only then choose an energy-block calibration strategy.

Updated active tasks and manuscript methods 2.22/results 3.24/conclusion. QA: 567 passed (23 new tests), six existing Optuna warnings and the existing Python 3.14/Pydantic startup warning; JUnit persisted in the new output directory. Python compilation and `git diff --check` pass. Historical artifacts and unrelated worktree changes remain intact.

## 2026-10-05 - Executed B13PG-ATP attribution under the provisional reference

Executed the requested next audit without changing the network, kinetics, initial conditions or 1e-3 mM threshold. Runner: `scripts/audit_b13pg_atp_executed_fluxes.py`; focused helpers: `src/fla_executed_attribution.py`; evidence: `output/b13pg_atp_executed_audit_2026_10_05/`. Legacy artifacts remain unchanged. The context is still the unpromoted VAMPD1 storage-decay branch, not a new best model.

### Accounting and verification

- Repeated continuous strict/ultrastrict J1-J46 replays and required accepted time/state arrays to reproduce the preceding verification bit-for-bit. The audit uses all corrected ATP/ADP/B13PG/B23PG matrix terms, with early subwindows and J1-J3/J3-J10/J10-J46/J1-J46 budgets.
- Split contributions by the actual sign of S_ij*v_exec before integration, not static producer/consumer names. Negative AK/NDPK rates reverse their contribution. These are sign-resolved net-rate contributions, not thermodynamic gross exchange fluxes.
- Native fluxes are evaluated on the same executed trajectory. Allocated absolute rate reduction goes to minimum-availability consumers, with equal tie sharing; products cannot limit a positive rate. Allocation describes the numerical limiter, not an experimentally identified control coefficient or intervention effect.
- Both runs pass 215 quadrature checks; all 215 strict/ultrastrict attribution comparisons pass. No accepted or sampled dense concentration is negative. Closure remains within 3.56e-15 mM/day; maximum window solver residuals are 1.62e-6 /2.22e-7 mM.
- Independent explicit equations reconcile 136 reaction terms and 32 loss sums in each replay against the preceding archive within 7.11e-15 mM. Reproduction script/results: `independent_equation_check.py` / `independent_equation_checks.json`. Frozen input hashes remain unchanged.

### Findings

- ATP falls 0.932992 -> 0.00132197 mM on J1-J3, with executed production 3.354344 mM versus consumption 4.286015 mM; the -0.931670 mM pool change is not a numerical material source or clipping artifact.
- VHK/VPFK consume 2.277206/0.956468 mM, 75.45% of early ATP consumption. PGK+PK produce 1.352359 mM, less than the 3.233674 mM investment.
- VAK produces 1.950491 mM ATP but consumes 3.900981 mM ADP (73.54% of total ADP consumption). ADP falls 1.169400 -> 0.000330904 mM. NDPK reverses on this interval: actual ATP-positive/negative contributions 0.051494/0.449487 mM versus the signed net -0.397993 mM.
- Early PGK native/executed integrals are 3.086995/0.542806 mM, with all reduction assigned to B13PG availability. At J3-J10, 95.68% of PGK reduction is assigned to ADP; after J10 all is assigned to ADP. Overall ADP/B13PG shares are 80.53%/19.47% of the 14.092400 mM rate reduction.
- PGK receives 88.52%, 8.16% and 0.334% of executed B13PG drainage over early/middle/late windows. Late shunt dominance does not establish that reducing DPGM alone can repair the early energy deficit.
- NAD/NADH initial states are 1 mM each, and the local workbook has no NAD/NADH rows. Their simulated evolution reduces the native GAPDH redox MM factor 0.320279 -> 0.018580 at J3 while GA3P rises 1.635591 -> 4.444030 mM. This is an unobserved initialization/model-state concern, not a measured redox teacher or a validated NADH-affinity fitting target.
- At the first measured interval J1-J4, reference ATP rises +0.146772 mM while the executed integral is -0.932487 mM. Conditional required PGK is 1.691940 mM versus 0.612681 mM executed with all other terms held fixed. Six of 13 intervals require negative conditional PGK; this rejects the fixed-neighbor PGK-only explanation, not the full network. B13PG remains excluded as an independent teacher because of the duplicated B23PG row. No postinitial measured J1-J3 endpoint is invented.

### Decision and next task

Do not reopen one-factor PGK/DPGM/ATP-affinity fitting, fit the availability threshold, or add an artificial ATP source. Next construct a fixed-kinetic J1-J4 feasibility contract for executed ATP-ADP-AMP balances and latent NAD/NADH initialization, including AMP/purine transfers accompanying VAK and measured-data/absolute-accuracy requirements. Only after that select a coupled investment-adenylate-GAPDH/PGK dynamic sensitivity experiment.

Active tasks and manuscript methods 2.23/results 3.25/conclusion updated. All 587 QA tests pass, including 20 new attribution tests; six existing Optuna warnings and existing Python 3.14/Pydantic startup warning remain. JUnit evidence is persisted. PNG/PDF figures generated, PNG visually inspected. No biological validation, kinetic optimization or promotion is claimed.

## 2026-10-05 - Joint adenylate/redox feasibility contract on J1-J4

Constructed and executed the requested precalibration contract without an optimizer, network change, threshold fitting or kinetic promotion. Runner: `scripts/build_adenylate_redox_feasibility.py`; algebra/IC helpers: `src/fla_adenylate_redox_contract.py`; tests: `qa/test_fla_adenylate_redox_contract.py`. Evidence: `output/adenylate_redox_feasibility_2026_10_05/`. The archived unpromoted kinetic context remains diagnostic, and the provisional strict reaction-consistent profile remains unchanged.

### Preregistered diagnostic

- J1 and J4 are the first two nominal local tabulated endpoints; intermediate J2/J3 trajectories are simulated, not additional measurements or teachers. ATP/ADP/AMP initial states remain exactly the archived measured inputs.
- Four NAD/NADH initializations isolate current/historical total and ratio: baseline, historical total only, historical ratio only, historical pair. Historical NAD/NADH are 0.015633767237772305/0.002738327309279107 nominal mM from `src/Initial_conditions_JA_Final.xls`, not independently verified biological priors. Current NAD/NADH are 1/1 mM. No other initial state changes; NADP/NADPH remain unobserved and unchanged. No best scenario is selected or promoted.
- Eight continuous, unforced J1-J4 replays: each scenario at strict and ultrastrict BDF, threshold 1e-3 mM. Frozen source/configuration/code hashes precede execution. Six disjoint early windows plus J1-J4 summary retain native/executed rates, signed net production/consumption and every nonzero adenylate/redox matrix contribution.
- The exact total equation is d(ATP+ADP+AMP)/dt=VADSL+VAK2+VAPRT-VSAM-VAMPD1-VAMP_NT. VAK contributes (1,-2,1), so it has no direct total source. NAD+NADH and NADP+NADPH are encoded invariants, not observed initial-total constraints. Individual endpoint tolerances and supported redox prior bounds remain unset rather than inferred from numerical tolerances.

### Verification and findings

- All eight cases pass 223 quadrature checks each; all 1344 strict/ultrastrict comparisons pass. No accepted or sampled dense concentration is negative; minimum checked value is 1e-6 mM. Executed closure is within 3.55e-15 mM/day; maximum strict/ultrastrict window solver residuals are 8.47e-7/8.52e-8 mM. Baseline prefixes match the preceding verified replay within 1.07e-14 mM.
- Independent explicitly written equations reconcile 224 window balances within 3.33e-15 mM, independently recomputing energy charge and all conditional AK requirements. Script/results: `independent_contract_check.py` and `independent_contract_checks.json` in the output directory.
- Baseline total adenylates change -0.213800 mM versus -0.149077 mM in the local table. Executed contributions are +0.143890 VADSL +0.015602 VAK2 -0.341839 VAMPD1 -0.031453 VSAM; VAPRT/VAMP_NT are zero. Total J4 is 2.627505 versus 2.692228 nominal mM (about -2.40%), but ATP/ADP/AMP are 0.000505122/0.000042261/2.626957 versus 1.079765/1.073256/0.539208 mM. Energy charge is 0.0002003 versus 0.600392. Total-only matching would conceal severe partition error.
- Baseline executed VAK is +1.950617 mM, whereas ATP/ADP/AMP require +3.029876/+1.414010/-0.137132 mM with other contributions fixed. This rejects only the fixed-neighbor single-AK explanation, not the coupled network or statistical compatibility without uncertainty.
- The four redox scenarios alter early transients but leave J4 ATP at 0.000505-0.000677 mM and ADP at 0.0000423-0.0000496 mM. None restores the nominal endpoints. This does not rule out the full latent-redox domain and does not validate historical values or a fitted redox affinity.

### Decision and handoff

The numerical diagnostic passes; biological calibration readiness remains blocked by six unresolved prerequisites: upstream source lineage, normalization, measurement uncertainty, biological time origin, supported redox prior, and absolute accuracy limits for each adenylate. `feasibility_contract.json` explicitly keeps calibration disabled. No weighted-total pass substitutes for ATP/ADP/AMP agreement, no artificial ATP source is added, and no new model or initial state is promoted.

Next prepare a predeclared coupled J1-J4 investment/adenylate/GAPDH-PGK dynamic sensitivity protocol at fixed initialization with full executed pool and purine/redox budgets; resolve scientific contracts before optimization. Do not reopen another isolated VAK/PGK/redox-affinity fit or optimize the numerical threshold. Updated active tasks and manuscript methods 2.24/results 3.26/conclusion/reproducibility map.

All 605 QA tests pass, including 18 new contract tests; six existing Optuna warnings and the Python 3.14/Pydantic startup warning remain. JUnit persisted, Python compilation and whitespace checks pass. PNG/PDF generated and PNG visually inspected. Historical artifacts and unrelated worktree edits remain intact.

## 2026-10-05 - Scientific readiness guard and prepared coupled energy protocol

Implemented supported preparation before optimization, without inventing scientific evidence: `config/fla_adenylate_redox_readiness.json`, `src/fla_precalibration_readiness.py`, `src/fla_coupled_energy_protocol.py`, `scripts/prepare_adenylate_redox_readiness.py`, and `qa/test_fla_precalibration_readiness.py`. Final evidence is `output/adenylate_redox_readiness_2026_10_05_v2/`; earlier readiness iterations are preserved and explicitly superseded. No new simulation, optimization, kinetic change, IC change, network change or working-profile default change occurred. The preceding eight-simulation archive remains intact.

### Evidence and independent review

One read-only agent audited local provenance and reviewed the new guard. Independent workbook receipts confirm ATP/ADP/AMP J1/J4 cells at Sheet1 B9/C9, B3/C3 and B5/C5; historical NAD/NADH are rows 84/85. A `cellbb` text-import connection references an unrecovered `cellbb.txt`; this is a lead only, not a demonstrated source for those rows. No external connection was followed.

Primary sources distinguish the [Bordbar/SAGM publication candidate](https://pubmed.ncbi.nlm.nih.gov/26749434/) from [Qi's separate ADSOL cohort and normalization](https://pmc.ncbi.nlm.nih.gov/articles/PMC5487983/). Their metadata/variability cannot be assigned to the local 46-day workbook without mapping. [Simpson et al.](https://www.cruk.cam.ac.uk/publications/studies-of-lactate-dehydrogenase-in-the-purified-state-and-in-intact-erythrocytes/) also distinguish free reaction-available from total extractable NAD(H). Neither historical points nor these published point estimates are adopted as stored-RBC prior intervals. Normalization, time origin, paired uncertainty, absolute accuracy limits and matching redox pool/volume support remain unresolved.

### Guard and protocol

- Six scientific domains yield 13 explicit guard checks. Every required-readiness/endpoint assessment rereads the actual contract and hashed support files, not saved result booleans. Missing counts, unverified evidence, modified/nonfinite limits, covariance defects and incompatible prior volume/pool definitions block readiness. The frozen redox initialization must lie within supported bounds.
- Joint six-observation covariance retains cross-pool/cross-day terms. Total/per-pool changes propagate exactly; energy charge uses a first-order gradient. Missing covariance is not filled with independence or zero. Scale-normalized validation rejects impossible correlations at any covariance magnitude. No acceptance threshold is automatically inferred from variance or fitted error.
- Eleven baseline/single-group and eight paired configurations give 19 diagnostic configurations /38 planned strict-ultrastrict replays. HK/PFK probes are downward-only, retaining HK<=5.0; AK forward/reverse capacities and GAPDH/PGK capacities each scale together. Log steps 0.05/0.10 are finite-difference design choices, not biological bounds. Kernel defaults are resolved through the actual hashed AST; GAPDH uses the existing 6.389868 default.
- Investment sensitivities are one-sided, other responses central, and pairwise interactions retain their single-group terms. All ICs, unlisted kinetics, network and numerical threshold remain fixed. No best-case ranking, reset, artificial ATP source or optimizer is introduced. Status is prepared_not_executed, execution_authorized=false. Historical runners/platform entry points are not silently migrated.

### Verification and next task

The native CLI was checked via a subprocess: `--require-ready` returns 2 for the current missing evidence. All 24 existing scenario/solver/pool biological endpoint decisions remain unknown. All 657 QA tests pass, including 52 new guard/protocol/source-receipt tests; six existing Optuna warnings and the Python 3.14/Pydantic startup warning remain. Final inputs include 41 unchanged hashes; prior simulation input hashes remain unchanged. JUnit, Python compilation and whitespace checks are retained.

Updated active tasks, `tasks/fla_data_evidence_requirements.md`, manuscript methods 2.25/results 3.27/conclusion and reproducibility map. Next recover the upstream export, including the `cellbb.txt` lead, with source-to-model conversion/time mapping and paired uncertainty; justify three independent endpoint tolerances and pool-compatible redox bounds. Only then execute the prepared coupled diagnostic or open a calibration protocol. A concise source/replicate request was sent to the user while supported preparation continued. No candidate is promoted.

## 2026-10-05 - Separate synthetic FLA transport recovery benchmark

Completed the user-approved data-independent benchmark, not a Bordbar optimization or an execution of the blocked energy protocol. Configuration: `config/fla_synthetic_recovery.json`; helpers: `src/fla_synthetic_recovery.py`; runner: `scripts/run_fla_synthetic_recovery.py`; independent verifier: `scripts/verify_fla_synthetic_recovery.py`; tests: `qa/test_fla_synthetic_recovery.py`. Final evidence: `output/fla_synthetic_recovery_2026_10_05_v2/`. Source hashes, initial state, network, availability threshold, biological readiness and the prepared 38 coupled energy replays remain unchanged. No model/default/kinetic/initialization promotion.

### Design and scope

- Known synthetic truth perturbs only `vmax_VEGLC` / `vmax_VELAC` by 0.85 /1.15, giving capacities 1.7571787128329357 /1.9836097450705532. All other archived unpromoted kinetics and all 114 initial entries remain fixed.
- Learn on J1-J22, predict continuously through J46 without resets, forcing or raw-output clipping. Sparse training times are the actual local schedule 1,4,8,11,15,18,22, not invented J2/J3 observations. Postinitial experimental concentrations are never targets.
- Production PCHIP teachers and executed kernel rates feed a benchmark-specific positive log-capacity least-squares adapter. Three starts and conditional Jacobian rank/spread are retained. Capacity linearity is checked against the real kernel within a cap-inactive domain; no full kinetic/affinity/global identifiability or historical optimizer/ML validation is claimed.
- Nonoracle learning uses only four generated observed pools: EGLC/ELAC/GLC/LAC. Remaining proxy entries are inert fixed scaffolding; exact latent trajectories never enter those fits. The oracle uses exact executed synthetic fluxes/states as a labeled control.
- Compare pointwise flux teachers with exact signed interval increments and order-8/16 quadrature of reconstructed kinetic inputs. Six observation regimes yield 12 fits plus one oracle, each replayed strict/ultrastrict: 13 fits /28 complete ODE simulations.
- An initial additive-noise preparation stopped on negative generated observations before fitting. It remains preserved and superseded in `output/fla_synthetic_recovery_2026_10_05/`. The final predeclared design uses independent mean-preserving log-normal noise with 0.5% CV, exact initial observations, one dense and three sparse noise seeds. These are synthetic realizations, not biological replicates or measured assay uncertainty.

### Results and verification

- Oracle capacities and held-out trajectory are recovered exactly at stored precision. Dense clean pointwise relative errors are 1.424%/0.1179%; integrated errors are 3.70e-9/1.83e-9 (fractions). Both pass declared synthetic checks. Sparse clean errors are 0.2840%/0.5714% pointwise versus 0.07968%/0.2682% integrated.
- Dense noisy capacity errors are 65.48%/4.175% pointwise versus 3.621%/0.3359% integrated. EGLC holdout excursion nRMSE is 1.583 versus 0.04758. The fixed 401-point derivative grid may underresolve noisy derivatives; this single realization does not establish universal method superiority. Sparse noisy glucose errors are 0.474-2.161% pointwise and 0.115-1.865% integrated; improvement is not uniform.
- All 28 replays pass checked raw positivity and strict/ultrastrict state/transport convergence. Executed truth interval balances close within 1.342e-8 mM, order-4/8 differences within 7.99e-15 mM. Full 113-pool and executed-flux temporal metrics are preserved, not just transport endpoint scores.
- Independent verification passes 92 checks: input hashes, frozen nonlearned kinetics/ICs, bound/scope and noise receipts, independent bounded closed-form fits (maximum optimizer difference 1.38e-7), accepted-state positivity/continuity and all exported metrics (maximum difference zero). Additional absolute/mean-relative metrics cover 2938 pool-period-case entries; near-flat RIB shows why excursion nRMSE alone can be misleading.
- All 686 QA tests pass, including 29 new targeted tests, with six existing Optuna warnings and the existing Python 3.14/Pydantic startup warning. JUnit, final receipts, Python compilation and whitespace checks are retained. PNG/PDF trajectories and parameter-error PNG generated and visually inspected.

### Decision and next execution

FLA can recover these two fixed-affinity capacities from clean generated concentrations, while noisy pointwise reconstruction can bias the learned rate and its free prediction. Keep this as a scoped software result, not resolution of the biological ATP/ADP/AMP mismatch. Next preregister a teacher-grid/smoothing comparison with additional dense noise seeds against interval supervision before changing the experimental objective. In parallel, recover Bordbar source/normalization/time/replicate evidence and justified redox/accuracy support; the scientific guard and the 38 coupled energy replays remain blocked. Manuscript methods 2.26/results 3.28/discussion/limitations and active tasks updated.

Reproduction requires a fresh directory: `python scripts/run_fla_synthetic_recovery.py --out output/fla_synthetic_recovery_new`, then `python scripts/verify_fla_synthetic_recovery.py --out output/fla_synthetic_recovery_new`. The separate QA command is `python -m pytest qa -q --junitxml=output/fla_synthetic_recovery_new/qa_results.xml`.

## 2026-10-05 - Paired teacher-resolution and smoothing screen

User-approved continuation of the synthetic FLA diagnostic only. New design/helper/runner/verifier: `config/fla_teacher_resolution.json`, `src/fla_teacher_resolution.py`, `scripts/run_fla_teacher_resolution.py`, `scripts/verify_fla_teacher_resolution.py`; targeted tests: `qa/test_fla_teacher_resolution.py`. The verified parent and all its hashed inputs remain intact. Biological calibration, changes to the model/defaults, initialization or numerical threshold, and the 38 prepared energy replays remain disabled.

### Preflight correction and declared design

- Preserve the initial interrupted preflight in `output/fla_teacher_resolution_2026_10_05/`: GCV factorization failed on two inherited timestamp pairs separated by 2.22e-16 day. No fit or simulation was completed in that attempt.
- The successor `output/fla_teacher_resolution_2026_10_05_v2/` merges roundoff-only clean synthetic timestamps at 1e-10 day tolerance before noise, retaining source-index groups and mean clean values: 689 -> 687 observations. Historical input tables are untouched. Within-screen paired noise is not bit-identical to the parent's draws; the 401 control reproduces the historical objective on the new partition, not the exact parent fit.
- Six regimes (clean plus five fixed 0.5%-CV noise seeds) and 15 methods give 90 conditional capacity fits. Compare four uniform grids (101/401/1601/6401), Gauss quadrature within every observation interval (orders 4/8), training-only log-GCV smoothing with a postfit initial anchor, and raw interval supervision (orders 8/16). Smoothed interval inputs retain raw increments as targets.
- Freeze four replay methods and three noise seeds plus clean before fitting: 16 capacity pairs /32 strict-ultrastrict continuous unforced J1-J46 ODE replays. Other conditional variants have no full ODE validation. A fast basis calls the actual rate helpers and reaction-consistent limiter; complete-kernel parity is checked rather than inventing a replacement law.
- All 90 fits are complete. Independent analytic optima differ by at most 4.24e-7 from optimizer outputs. Aligned order-4/8 capacity variation is at most 1.48e-7; interval order-8/16 basis difference is at most 1.39e-17. All conditional ranks are two at frozen affinities; this is not global identifiability. One coarse raw-grid fit reaches its bound.
- All 714 QA tests pass, including 28 new tests. Existing six Optuna warnings and Python 3.14/Pydantic startup warning remain. Manuscript method 2.27 documents the design and numerical timestamp correction. Full replay/archive verification is in progress; final interpretation must include held-out predictions, not conditional fits alone.

### Completed results, independent verification and next execution

All 32 full replays are complete and pass positivity, executed closure and strict/ultrastrict convergence gates. Minimum checked concentration is +8.157751e-7 mM; executed transport-balance closure is zero at stored precision. Independent verification passes 458 checks, including paired noise/partition/curve reconstruction, temporal weights, complete-kernel problem parity at fixed probes, bounded closed-form fits, frozen scope/ICs, raw archives and all 3680 metrics. Maximum fit difference is 4.242e-7 and metric difference 6.661e-16. Two full QA runs pass all 714 tests; Python compilation/whitespace checks pass. Parent inputs and biological contracts remain unchanged.

- Five-noise-seed median/max glucose capacity errors: legacy 401 38.72%/92.66%; raw aligned 0.2386%/0.3261%; aligned log-GCV 0.5604%/0.6157%; raw intervals 2.684%/7.370%. Lactate medians are 16.16%/0.3039%/0.9140%/0.2207%, respectively; rankings are not uniform across targets.
- Three preselected replay-seed median EGLC holdout excursion nRMSE: 56.38%/0.1958%/0.5128%/3.698%; ELAC: 2.476%/0.03749%/0.09105%/0.2402%. Raw aligned absolute median RMSE: 0.005187 mM EGLC and 0.001273 mM ELAC. Whole-pool maximum mean-normalized holdout error is 1.47% raw aligned versus 261.2% legacy, 25.44% intervals and 2.11% smoothed; GTP/LAC sensitivity reinforces the free whole-model replay requirement.
- A posthoc numerical partition control independently reproduces the original parent clean errors 1.424%/0.1179%. At the same 401-point equal-weight objective, canonical clean data give 0.00005416%/0.00004605%. `timestamp_impact.json` records this separate conditioning effect; original and successor noisy draws are not bit-identical.
- Figure postprocessing changes presentation only (nonnegative error axes and readable labels), retaining runner originals in `initial_figures/`. `scripts/finalize_fla_teacher_resolution_figures.py` and its hash are retained alongside the verifier. Manuscript methods 2.27/results 3.29/discussion and active tasks are updated. No biological candidate is promoted; six-domain readiness still has 13 missing checks and energy execution remains unauthorized.

Next repeat the aligned PCHIP/log-GCV/interval comparison on the seven sparse training times matching local Bordbar with paired noise and fixed free-ODE validation, before transferring the dense-grid ranking or changing an experimental objective. Source normalization, time/replicate evidence, justified accuracy limits and redox support remain required for biological calibration.

Reproduction: `python scripts/run_fla_teacher_resolution.py --out output/fla_teacher_resolution_new`; full QA with `--junitxml=output/fla_teacher_resolution_new/qa_results.xml`; optional presentation export via `python scripts/finalize_fla_teacher_resolution_figures.py --out output/fla_teacher_resolution_new`; then `python scripts/verify_fla_teacher_resolution.py --out output/fla_teacher_resolution_new`. Fresh directories are required; no historical archive is overwritten.

## 2026-10-05 - Seven-time sparse teacher continuation

User-approved next synthetic execution on J1/J4/J8/J11/J15/J18/J22, not a new Bordbar biological calibration. Separate configuration/runner/verifier/tests: `config/fla_sparse_teacher_resolution.json`, `scripts/run_fla_sparse_teacher_resolution.py`, `scripts/verify_fla_sparse_teacher_resolution.py`, `qa/test_fla_sparse_teacher_resolution.py`. Output: `output/fla_sparse_teacher_resolution_2026_10_05/`. The original recovery and dense resolution archives, all kernel/defaults, kinetic/initial snapshots, availability threshold and readiness contracts remain sealed and unchanged.

### Declared design and completed conditional fits

- Retain all 15 methods, fixed affinities/other kinetics/full ICs, truth capacities, capacity bounds, three starts, five synthetic 0.5%-CV noise seeds and the same four replay methods/three replay noise seeds plus clean. This gives 90 conditional fits and 32 planned strict/ultrastrict continuous unforced J1-J46 ODE replays; no additional method is chosen using truth errors.
- Use only generated sparse concentrations. The table supplies sampling times only. No near-duplicate times occur (7 -> 7); the three original sparse noise draws reproduce exactly. Sparse/dense draws are not matched, despite sharing seed labels. Final noise lineage is documented separately from inherited partition-helper metadata.
- All 90 conditional fits complete; independent analytic capacity discrepancy <=3.581e-10, multistart spread <=8.715e-10, all conditional ranks two and no fitted bound hits. Aligned order-4/8 capacity variation <=3.142e-6; interval order-8/16 basis difference <=1.176e-9. These are conditional numerical checks, not global identifiability or biological accuracy.
- Five-seed median glucose capacity errors: historical 401 1.3815%; raw aligned 1.3345%; log-GCV aligned 1.0992%; raw intervals 0.9725%; smoothed-input intervals 0.7097%. The last method has no predeclared full ODE replay in this campaign; its favorable median does not authorize validation or promotion by itself.
- All 735 QA tests pass, including 21 targeted new tests, with the existing six Optuna warnings and Python 3.14/Pydantic startup warning. Python compilation passes. Manuscript method 2.28 and active tasks document the sealed sparse continuation. Full replay/archive verification remains in progress.

### Reconstruction illustration

`scripts/plot_fla_sparse_teacher_diagnostics.py` exports an inspected PNG/PDF of four training concentrations and both derivative teachers, using the first predeclared seed (2718), not a best-case selection. Exact synthetic reference is for evaluation only. The clean sparse PCHIP proxy misses the early GLC/LAC troughs between J1 and J4: the saved reference grid samples GLC down to 0.002697 mM near J1.525, while its reconstructed minimum is 1.087361 mM. These are sampled synthetic values, not measurements or exact continuous extrema. Good recovered capacities need not imply good conditional state reconstruction. No extra solver replay or experimental time point is introduced by this illustration.

### Completed replays, verification and decision

All 32 strict/ultrastrict continuous J1-J46 ODE replays complete and pass numerical gates. Minimum checked concentration +8.230065e-7 mM; executed transport-balance closure zero at stored precision. Independent verification passes 477 checks, including complete-kernel reconstruction of all sparse aligned/interval training nodes, sampled uniform nodes, original sparse legacy reproduction, frozen IC/nonlearned kinetics, exact paired noise and raw arrays, and all 3680 exported metrics (maximum difference 6.661e-16). Original and dense archives remain unchanged. All 735 QA tests pass, with six existing Optuna warnings and the Python 3.14/Pydantic startup warning. Compilation/whitespace checks pass; all three PNG/PDF pairs are generated and PNGs inspected.

- Teacher resolution is not the sparse bottleneck: changing 401 -> 6401 temporal quadrature shifts capacities by at most 1.128e-6 raw or 8.155e-7 smoothed in relative terms. The large dense-grid aliasing result must not be transferred to local sparse Bordbar data.
- Three preselected noisy holdout EGLC median/max excursion errors: historical 1.111%/2.870%; raw aligned 1.097%/2.813%; aligned log-GCV 0.7814%/2.514%; raw intervals 1.303%/2.483%. ELAC medians are 0.09000%/0.08823%/0.08435%/0.08034%, respectively. Parameter medians concern five seeds, prediction medians three; their rankings must remain separate.
- Maximum whole-pool mean-normalized holdout error is 7.97% historical, 7.81% raw aligned, 6.99% smoothed aligned and 6.90% intervals, using the 0.001 mM mean-scale floor. GTP is most sensitive. No synthetic acceptance metric is converted to a biological tolerance.
- Smoothed-input intervals have favorable five-seed conditional medians (0.7097% glucose, 0.7145% lactate), but their clean glucose bias is 0.2450%, versus 0.07968% raw intervals. They have no predeclared ODE replay here, so no adoption or promotion follows.
- Noise lineage is independently saved in `verified_noise_lineage.json`, separate from the generic partition helper's inherited optional noise flag. Three sparse parent draws are regenerated identically; dense/sparse draws are not matched. Method 2.28/results 3.30/discussion and current tasks are updated. Scientific readiness remains blocked in six domains/13 checks, with the 38 energy replays unauthorized.

Next preregister a targeted full-ODE comparison of raw versus smoothed-input intervals on clean plus all five sparse seeds, preserving raw increments and all frozen model/numerical settings. Reuse four verified raw-interval pairs; add two raw-interval and six smoothed-input pairs (16 new integrations, 24 total including eight reused), with full-pool/flux checks and explicit clean bias assessment. Do not optimize a new kinetic lever or silently change production defaults.

Reproduction requires a fresh output directory: `python scripts/run_fla_sparse_teacher_resolution.py --out output/fla_sparse_teacher_resolution_new`; full QA with `--junitxml=output/fla_sparse_teacher_resolution_new/qa_results.xml`; optional reconstruction figure via `python scripts/plot_fla_sparse_teacher_diagnostics.py --out output/fla_sparse_teacher_resolution_new`; then `python scripts/verify_fla_sparse_teacher_resolution.py --out output/fla_sparse_teacher_resolution_new`. The runner already exports the grid and holdout comparisons, keeping initial figure versions. No historical result is overwritten.

## 2026-10-05 - Fixed-capacity smoothed-interval free-ODE validation

User-approved execution of the preceding handoff, in a separate archive `output/fla_smoothed_interval_replay_2026_10_05/`. Configuration/runner/verifier/QA: `config/fla_smoothed_interval_replay.json`, `scripts/run_fla_smoothed_interval_replay.py`, `scripts/verify_fla_smoothed_interval_replay.py`, `qa/test_fla_smoothed_interval_replay.py`. Existing sealed code and archives remain unchanged.

- Preregister twelve exact archived capacity pairs: raw versus smoothed-input interval training, clean plus five paired sparse 0.5%-CV synthetic seeds. No new fit or optimizer; six raw signed increments per flux are unchanged.
- Reuse four verified raw strict/ultrastrict pairs with byte-level copy receipts. Add two missing raw and six smoothed-input pairs: sixteen new integrations, twenty-four represented integrations including eight reused.
- Prediction receives capacities only, never reconstructed concentrations or external forcing: continuous J1-J46 with the same full ICs, affinities, other kinetics, network, reaction-consistent profile and availability threshold. J22 remains the training boundary.
- Export all 113-pool/two-executed-flux training and holdout metrics; independently verify raw positivity, endpoint convergence, full dense comparison receipts, sampled kernel rates, frozen capacity/target lineage and paired five-seed summaries. Report clean bias separately. Scientific readiness and the unauthorized 38 energy replays are unchanged.
- All 26 targeted tests pass. The ODE campaign and full QA are in progress; manuscript method 2.29 is updated before interpreting results.

## 2026-10-06 - Resumed and completed smoothed-interval predictive validation

After the usage-limit interruption, the existing archive shows all sixteen new integrations completed; none was rerun. The four copied raw pairs account for eight additional verified historical integrations. All twelve strict/ultrastrict pairs pass numerical checks with minimum checked concentration +8.2317856e-7 mM and zero stored executed transport closure. Raw accepted ICs are identical bit-for-bit to the frozen snapshot. No refit, forcing, reset, state clipping, kinetic/profile/threshold change or biological promotion occurred.

Independent verification initially rejected all dense-output initial anchors despite the exact raw accepted initialization: the inspected clean dense polynomial differs by only 1.11e-16 mM. Preserve that attempt in `initial_anchor_verification_attempt.json`; change only the dense-anchor comparison to eight machine-epsilon-scaled units. Raw accepted-state equality stays exact. Add four anchor regression tests; all 30 targeted and 765 full QA tests pass, with six existing Optuna warnings and the Python 3.14/Pydantic startup warning. Final verification passes 815 checks; maximum independent metric difference 6.661e-16 and closed-form capacity difference 3.581e-10. All input/source/support/output hashes from prior archives remain unchanged. Scientific readiness still has thirteen unmet checks and the 38 coupled energy replays remain unauthorized.

### Paired prediction findings

- Noisy EGLC median/max excursion error decreases 1.3034%/2.4828% -> 0.9634%/2.0633%, improving four of five seeds. ELAC median decreases 0.08034% -> 0.07683% but its maximum worsens 0.13416% -> 0.15870%; only three seeds improve.
- Executed VEGLC RMS-normalized median/max error decreases 0.4845%/0.9318% -> 0.3516%/0.7717%; VELAC 0.3177%/0.3641% -> 0.2892%/0.3287%. Each improves four seeds. LAC median decreases despite improving only two individual seeds: medians are not paired effects or uniform gains.
- Clean EGLC error worsens 0.10752% -> 0.33133%, with signed J46 endpoint -0.002230 -> +0.006878 mM. Clean ELAC worsens 0.02465% -> 0.03733%; clean VELAC rate error improves. This identifies bias/noise and rate/concentration trade-offs, not general superiority.
- All 113-pool metrics are retained. Worst noisy mean-normalized holdout error is GTP/seed31415: 6.9034% raw versus 5.7469% smoothed (0.001 mM scale floor). No synthetic guard becomes an experimental accuracy limit.
- Export 2760 full metrics, 1380 paired rows, 230 five-seed aggregates and 168 net transport integrals over six training windows plus J22-J46. The integrals are endpoint-derived executed balance identities, explicitly not independent quadrature. Noisy median absolute holdout integral errors improve VEGLC 0.013247 -> 0.009597 mM and VELAC 0.007513 -> 0.006523 mM. Integrated signed errors can cancel and do not override ELAC trajectory regressions.

Both PNG figures are inspected and companion PDFs are exported. Method 2.29/result 3.31/discussion and active tasks are updated. Decision: retain raw interval supervision as the comparator; smoothed-input intervals are a completed optional synthetic predictive hypothesis, not a production-default replacement or biologically validated calibration. The remaining priority is source normalization/time/uncertainty/accuracy and latent-redox support before biological optimization. Five synthetic seeds are descriptive, not confidence intervals or biological replicates.

Reproduction: fresh directory via `python scripts/run_fla_smoothed_interval_replay.py --out output/fla_smoothed_interval_replay_new`; full QA with `--junitxml=output/fla_smoothed_interval_replay_new/qa_results.xml`; then `python scripts/verify_fla_smoothed_interval_replay.py --out output/fla_smoothed_interval_replay_new`. Current evidence: `output/fla_smoothed_interval_replay_2026_10_05/decision_report.md`, `independent_verification.json`, `final_verification.json`. The archive name retains its launch date; completion is recorded on 2026-10-06.

## 2026-10-06 - Read-only Bordbar source, units and time-origin audit

User-approved next step before biological optimization. Configuration/runner/verifier/QA: `config/fla_bordbar_source_audit.json`, `scripts/audit_bordbar_source_units_time.py`, `scripts/verify_bordbar_source_units_time_audit.py`, `qa/test_bordbar_source_units_time_audit.py`. Separate archive: `output/bordbar_source_units_time_audit_2026_10_06/`.

### Verified local evidence

- Sheet1 contains 55 rows at 14 model times: 770 finite nonnegative concentrations, no missing cells or formulas. Workbook SHA-256 is `7a7393972628646f7cf44fcc7d227381fd4921873eeb88296bfba0d37de92ad4`. All five available Git workbook snapshots preserve the numeric matrix, labels and times exactly; duplicate B13PG/B23PG and P2G/P3G signals were already present in the first import.
- Query-table XML binds `cellbb` to **Feuil1**, not Sheet1. Named range `Feuil1!$A$5:$F$49` contains 44 rows of five curve coefficients b_1-b_5 and polynomial/log evaluation formulas. Recovering cellbb.txt is a coefficient-lineage task, not sufficient evidence of raw concentration provenance. Project filename search and all-ref Git filename history find no cellbb source file; no private cloud or whole-machine search was performed.
- Independent source comparisons cover all 770 calibration cells and 266 extracellular cells, with exact numeric/time parity. Current loaders apply no declared volume conversion; the kernel retains `MODEL_TIME_UNIT=day` and `TRANSPORT_VOLUME_SCALING_MODE=legacy_equal_concentration`.

### Primary-source interpretation and corrections

- The 2017 PLOS reanalysis (DOI 10.1371/journal.pcbi.1005424) describes 14 Bordbar observations over 45 days. J1-J46 is likewise 45 elapsed days. A +1 model-origin hypothesis is plausible but unverified; the candidate vector is `[0,3,7,10,14,17,21,24,28,31,35,37,42,45]`. Local J38 is not repaired. Earlier 42/46 wording cannot establish endpoint extrapolation.
- The publication excluded source day 31 after an extracellular anomaly. Under the unverified offset it might correspond to local J32; local EGLC rises 16.640 -> 16.950 nominal mM from J29 to J32. This is not proof of shared sample identity. No observation is excluded, relabeled, imputed or transformed.
- Bordbar uFBA methods (DOI 10.1038/srep46249) use total-bag-volume mmol/L for both compartments, prioritize glucose/lactate/ATP assay values and describe unresolved-pool handling. This is a concrete normalization lead, not proof of the local denominator. No hematocrit or cell-water factor is guessed; equal-reference-volume transport could be consistent with a verified bag-volume basis.
- Qi ADSOL remains a distinct cohort; its normalization/variability cannot provide this table's uncertainty. Two public supplementary endpoints returned HTTP 200 with 3038-byte HTML payloads, not Excel; responses, access metadata and SHA-256 are retained as failed-access evidence. No supplemental concentration dataset was imported.

### Verification and decision

All 25 new targeted tests and 790 full QA tests pass; six existing Optuna warnings and the Python 3.14/Pydantic startup warning persist. Independent verification passes 227 checks, including workbook XML, every loader value vector, historical blobs, input/output hashes, current readiness and four sealed synthetic archives. Frozen kinetics/ICs, model source, current profile/readiness configuration and the prepared coupled protocol remain unchanged. No ODE integration, parameter fit, normalization/time-offset application or promotion was performed by the audit.

Scientific readiness remains blocked in six domains /thirteen checks; 19 configurations /38 coupled energy replays remain unauthorized. Next request the **original concentration export feeding Sheet1**, row/assay dictionary, unit/donor identifiers, exact source sampling times, aggregation/missingness handling and the normalization script/factors. cellbb.txt is a separate coefficient-provenance request. Paired biological/technical values, justified absolute error requirements and supported NAD(H) pool bounds remain necessary. The missing source evidence is not repaired by changing optimizer settings.

Manuscript methods 2.30/results 3.32, primary-dataset description/limitations, active tasks and `tasks/fla_data_evidence_requirements.md` now reflect these distinctions. The historical sealed reports are preserved rather than rewritten.

Reproduce in a fresh directory: `python scripts/audit_bordbar_source_units_time.py --out output/bordbar_source_audit_new --fetch-supplements`; `python -m pytest qa -q --junitxml=output/bordbar_source_audit_new/qa_results.xml`; `python scripts/verify_bordbar_source_units_time_audit.py --out output/bordbar_source_audit_new`. Public network availability may change; access receipts are descriptive and no source mapping is promoted by a successful download alone.

## 2026-10-06 - Conditional exploratory energy sensitivity, exact measured J1

User explicitly retained Sheet1 J1 initialization rather than historical XLS initialization, then authorized a separate conditional protocol and execution of steps 1-3: freeze initial states/numerical policy, perturb the three capacity groups singly and jointly, and measure actual energy/redox/limiter responses. This does not authorize or execute the original scientifically blocked biological protocol.

New configuration/runner/verifier/QA: `config/fla_exploratory_energy_sensitivity.json`, `scripts/run_exploratory_energy_sensitivity.py`, `scripts/verify_exploratory_energy_sensitivity.py`, `qa/test_exploratory_energy_sensitivity.py`. Separate archive: `output/exploratory_energy_sensitivity_J1_J4_2026_10_06/`.

Preflight found that the frozen historical context did not preserve all nominal J1 observations: B13PG was a QSS value 0.000176677669 mM, versus Sheet1 3.584045211 mM, and ECYS/EINO zeros were floored to 1e-6. The new branch explicitly restores all 55 exact nominal J1 values, including zeros. All 59 unmeasured entries (including pHi) remain unchanged; NAD=NADH=1 mM remains an unverified assumption. Source duplicates B13PG/B23PG and P2G/P3G are not independent endpoint validation channels. Old snapshots, source files, readiness configuration, numerical threshold and platform defaults are unchanged.

The stencil has 11 baseline/single-group cases and 8 paired cases, each strict/ultrastrict: 38 continuous J1-J4 integrations. Group multipliers are exp(+/-0.05), exp(+/-0.10), with downward-only HK/PFK at HK<=5.0; AK forward/reverse and GAPDH/PGK capacities scale together. All other kinetics, latent ICs and network stay fixed. No optimizer, state fitting, forcing, reset, artificial ATP or candidate ranking/promotion.

All 33 targeted new tests and 823 full QA tests pass. The complete ODE campaign is running; baseline strict already passes quadrature/closure/positivity checks and ends at ATP 0.000751043, ADP 0.0000804467, AMP 2.593665 nominal mM. Exact source J1 by itself does not restore the nominal J4 partition. Method 2.31 records the conditional design before interpreting the complete response vectors.

### Completion and independent verification

All 38 integrations completed in approximately 1926 seconds. All 8474 quadrature and 6384 strict/ultrastrict checks passed. The minimum checked raw concentration is zero; independent inspection found no negative accepted or stored dense concentrations. The frozen measured J1 vector is exact and every unmeasured state is unchanged; no historical redox migration, observation forcing/reset, source/threshold/network change or optimization occurred.

Independent verification passed 6430 checks before visual refinement: complete input/output hashes, five prior sealed archives, all raw initial states and restricted parameter dictionaries, full saved rates/factors and reaction balance closure, signed-consumer factor reconstruction, nine executable-kernel samples per replay, energy-charge/redox conservation, signed seven-window adenylate budgets, every nominal endpoint and complete finite-difference/interaction vector. The final rerun after legend-only refinement passed 6445 checks, including the additional preserved artifacts; no numerical evidence or model input changed. The source audit remains the separate verification of all 770 source cells; this campaign initializes their 55 J1 entries. Independent convergence checks cover the shared 601-node grids and all stored integral quantities; the runner additionally checks the union of both accepted solver grids. Gauss nodes themselves are not independently replayed a second time. Limiter shares are explicitly sampled trapezoid bookkeeping, not quadrature or causal controls.

Export 2090 nominal J4 endpoint rows, 3800 executed reaction integrals, 2580 single-group responses, 1290 paired interactions, 1290 probe-size comparisons and 1935 solver-response comparisons. ATP/ADP/AMP response signs agree between solvers; maximal relative differences are 0.0273% single and 0.1643% mixed. Small/near-zero other features remain separately interpretable; no statistical confidence follows from these numerical comparisons. QA remains 823 passing tests, including 33 new targeted tests, six existing Optuna warnings and the Python 3.14/Pydantic startup warning.

### Conditional findings and decision

- Baseline J4 ATP/ADP/AMP: 0.000751043 /0.0000804467 /2.593665 nominal mM versus 1.079765 /1.073256 /0.539208. Total 2.594497 vs 2.692228 mM is relatively close, but energy charge 0.000304979 vs 0.600392 is not. The restored nominal B13PG J1 is not evidence of an independent true B13PG measurement.
- Baseline executed J1-J4 ATP production/consumption: 5.822852 /6.755092 mM, net -0.932240 vs nominal +0.146772. ADP net -1.169321 vs -0.0961443; AMP +1.854752 vs -0.199705. Integrated material closure has no artificial ATP source.
- Downward HK/PFK modestly raises ATP/ADP but also AMP. Downward AK modestly raises ATP/ADP and lowers AMP. Upward GAPDH/PGK raises ATP and lowers AMP but slightly lowers ADP. These are tied-group dynamic responses with feedback and limiter action, not independent enzyme control coefficients.
- Across all 19 strict points, ATP J4 stays 0.000685896-0.000837634, ADP 0.0000684698-0.0000990709 and AMP 2.592957-2.594368 nominal mM. Paired interactions are nonzero but no probe point restores the nominal partition. This rejects no broad coupled hypothesis outside the tested neighborhood and selects/promotes no best case.
- Baseline sampled VPGK limiting-loss shares over J1-J4 are B13PG 93.30%, ADP 6.70%; VPK loss is allocated to ADP. These are same-trajectory numerical-limiter accounts, not measured biological control or independent integral estimates.

Two PNG/PDF figure pairs are exported and visually inspected. Initial exports, finalizer code and verification receipts are preserved with `pre_visual_review_` prefixes before a legend-only refinement removed overlap with J4 markers. The original five archives and all model/data/readiness inputs remain unchanged. Manuscript methods 2.31/results 3.33 and active tasks are updated. Steps 1-3 are complete; no J10/J46 extension or optimizer is launched. Scientific readiness remains blocked in six domains /13 checks, and the original biological coupled protocol remains unauthorized. Larger conditional feasibility tests or biological calibration need a subsequent explicit scope and cannot borrow numerical pass thresholds as biological accuracy limits.

Reproduce in a fresh directory: `python scripts/run_exploratory_energy_sensitivity.py --out output/exploratory_energy_new`; `python -m pytest qa -q --junitxml=output/exploratory_energy_new/qa_results.xml`; `python scripts/finalize_exploratory_energy_sensitivity.py --out output/exploratory_energy_new`; `python scripts/verify_exploratory_energy_sensitivity.py --out output/exploratory_energy_new`. Main evidence: `decision_report.md`, `summary.json`, `independent_verification.json`, `final_verification.json` in the exploratory archive. Old historical protocols and platform defaults are not migrated.

## 2026-10-06 - Published-source inventory and latent-state inference preparation

User approved all three follow-ups: audit ATP/free-total and volume/pool identities, inventory Nishino/Bordbar/Yurkovich sources, and prepare a reversible fixed-kinetic latent-inference protocol. Config: `config/fla_latent_inference_preparation.json`; isolated helper: `src/fla_latent_inference.py`; runner/verifier: `scripts/prepare_fla_latent_inference.py`; protocol: `tasks/fla_latent_inference_protocol.md`. Evidence: `output/fla_latent_inference_preparation_2026_10_06/`.

Preserve the exact measured J1 branch and every latent state/kinetic constant; no simulation or initial-state fitting. Parent energy and source-audit archives verify unchanged. Workbook reconstruction covers all 770 cells and distinguishes missing cells (zero) from pools not observed. Kernel audit identifies one ATP state with no explicit free/MgATP/Hb-bound observation operator, no Pi/Mg state, and an unverified concentration denominator. Duplicate B13PG/B23PG and P2G/P3G remain preserved and non-independent. The 53 retained nominal balance channels have rank 50 across 100 reactions, nullity 50; this is not latent dynamic identifiability.

Read the attached Nishino main/supplement and retain all 101 section-5 concentration entries (pages 34/35/36: 40/46/15 rows), exact source labels and dimensional-only M-to-mM conversion. These are model reference points, not measured MAP day 1-5 donor anchors. ATP free/total are 0.0551/1.91 mM. NAD/NADH and NADP/NADPH are 0.0651/0.000240 and 0.0000647/0.0653 mM; each current unmeasured redox state remains 1 mM. No confidence interval, prior width or applicable bound is fabricated. Small reference points below the fixed 1e-3 mM availability threshold require future limiter auditing, not threshold fitting.

Inventory separates Nishino experimental temporal ratios/commercial calibration/model references, Bordbar 2015 cross-sectional personalized metabolism, Yurkovich 2017 externally calibrated absolute measurements with predicted 2,3-DPG, antioxidant same-day treatment/control ratios, and the uFBA total-bag-volume lead. JBC supplementary retrieval returned HTML status 203; payload/hash/access limitation are retained, with no numeric import. Exact external sampling tables, applicable volume/pool definitions and paired control intensities remain outstanding. No figures are digitized into fabricated absolute observations.

Prepared observation models retain temporal ratios, contemporaneous treatment/control ratios, source-specific absolute operators and optional uncertain external anchors as distinct channels. Derived flux teachers are correlated with their concentration source and cannot count as independent evidence. First future latent block: four NAD(H)/NADP(H) total/reduced-fraction coordinates, fixed kinetics and measured ICs. Synthetic dynamic identifiability/recovery precedes biological MAP/profile/ensemble inference and needs a separate execution decision. Bounds/covariance/accuracy limits stay null; readiness remains false. Pi/Mg require a model change, not an IC tweak; B13PG/B23PG are not opened.

All 863 QA tests pass, including 40 new observation/preparation tests; six existing Optuna warnings and the Python 3.14/Pydantic startup warning remain. Initial preparation preflight stopped before creating output because the archived parameter filename was `frozen_parameters.json`, not `frozen_params.json`; corrected the new runner only. Source-cell and reference-table reconstruction pass. Methods 2.32/results 3.34 and active tasks are updated. No model, historical source/configuration, initial condition, kinetic parameter or threshold is changed, and no claim that ATP is restored is made.

Reproduce: `python scripts/prepare_fla_latent_inference.py --out output/latent_preparation_new --fetch-supplements`; verify: `python scripts/prepare_fla_latent_inference.py --verify output/latent_preparation_new`. New helper tests: `python -m pytest qa/test_fla_latent_inference_preparation.py -q`. Current full QA receipt is `qa_results.xml` in the preparation archive.

## 2026-10-06 - Supplied JBC supplements: exact, isolated ingestion

User supplied `C:/Users/Jorgelindo/Downloads/mmc1/jbc.M117.804914-1.xlsx` and `jbc.M117.804914-2.pdf`. Read all workbook schedules/headers/values and the relevant supplement methods; visually inspect PDF pages2,5,6,13. This resolves the earlier failed public download, which remains preserved in the old archive. New source files are copied byte-for-byte into `output/jbc_supplements_ingestion_2026_10_06/source_files/` and retained with SHA256 receipts. Old sealed preparation scripts, configs, source inventory and latent-inference protocol are not edited.

New isolated config/helper/runner/tests: `config/fla_jbc_data_ingestion.json`, `src/fla_jbc_data.py`, `scripts/ingest_jbc_supplements.py`, `qa/test_fla_jbc_data.py`. Workbook:47 endo,23 exo,26 assay/physiology channels;123/123/126 sample rows;11,886 numeric observations, no missing/nonfinite/negative concentrations and182 reported extracellular zeros. Three positional replicate blocks at4/13/22/37C are retained without inventing donor IDs or cross-sheet pairing. Exact noninteger times are unchanged. Source day0 is one day after storage began according to PDF p2; source_day+1 is stored only as a separate JBC-specific coordinate. At37C assay extends to source day14, endo/exo end at7; no row-number joins.

Candidate mapping preserves phosphoglycerate as P2G+P3G, maps 6-phosphogluconate to GO6P rather than GL6P, and refuses nicotinamide->NAD, S-adenosylmethioninamine->ADOMET, LDH activity->VLDH or analyzer pH->pHi. ATP workbook endo versus FigS7 exo, unknown free/total recovery, hexose-6-phosphate calibration identity, duplicate hemoglobin columns, count-unit notation and unknown volume equations are explicit conflicts. 2,3-DPG is not measured despite a contradictory methods kit mention; its modeled estimate is excluded. Reported zeros are not transformed to logarithms/epsilon or imputed. No NAD(H)/NADP(H), B13PG or seven PPP latent pools are measured here.

The independent verifier compares every exported cell and key with the original worksheet, verifies all input/output hashes and rechecks the sealed parent. All37 targeted tests pass. Initial importer preflight rejected the textual temperature labels (`4 degrees C`, etc.) before output creation; the reader now uses an explicit label dictionary and retains each original label/source cell. No source file was changed to accommodate the parser. Manuscript methods2.33/results3.35 and active tasks distinguish numerical access from scientific readiness.

No volume conversion, teacher generation, ODE, initial-state inference, optimization, model modification or promotion is executed. The exact55 Bordbar J1 entries, all unmeasured ICs, kinetics, provisional reaction_consistent strict/ultrastrict profile and historical thirteen-check readiness guard remain unchanged. Next confirm JBC pool/volume definitions, donor pairing and cohort independence before a distinct4C external test. Redox synthetic recovery remains separately scoped; supplied data do not justify replacing current ICs or using external concentrations as exact Bordbar anchors.

Reproduce into a fresh directory: `python scripts/ingest_jbc_supplements.py --out output/jbc_import_new`. Verify the current archive: `python scripts/ingest_jbc_supplements.py --verify output/jbc_supplements_ingestion_2026_10_06`. Test: `python -m pytest qa/test_fla_jbc_data.py -q`. Full-suite verification completed: all 900 QA tests pass in 129.84 seconds, with six existing Optuna warnings and the existing Python 3.14/Pydantic startup warning. JUnit and a verification receipt are archived; the pre-QA manifest is preserved before final resealing. No source/model/parent input changed.

## 2026-10-06 - Recent Palsson proteomics sources and FLA capacity-prior review

User requested a recent-publication search, review of the six supplied Issaian/Deep Red files and explicit memory preservation. Primary sources identify Issaian/Blood2026, Haiman/RBC-GEM2025, Nemkov/PFK2024, Bevers/PIMT2026 and the Karafin/G6PD2025 preprint as relevant. Publication versions and overlapping REDS cohorts are distinguished; this is a targeted search, not an exhaustive systematic review. Report: `tasks/fla_proteomics_source_review_2026_10_06.md`.

New isolated runners/config/QA: `scripts/audit_palsson_proteomics_sources.py`, `scripts/enrich_palsson_proteomics_review.py`, `config/fla_proteomics_source_review.json`, `qa/test_palsson_proteomics_review.py`, `qa/test_palsson_source_metadata.py`. Evidence: `output/palsson_proteomics_review_2026_10_06/`. Six attachments copied byte-for-byte; no HTML/JavaScript execution. Inventory: 21 workbook sheets, 3799 unique human protein rows (3781 F-positive, 18 zero), 940 phosphopeptide/site rows, 4061 cysteine rows, 558 interactome nodes and 50 provisional protein/reaction mappings. The article's 3775 proteins versus 3799 supplied rows remains unresolved. Two copy-number calibrations differ by approximately 5.65-fold for selected enzymes; neither is automatically adopted.

RBC-GEM S6 was retrieved from official Figshare metadata/file52949041: 82603979 bytes, valid Excel ZIP and matching provider MD5. SHA256: `e951fe9c4a5bb94913a10e6c31296ca59c7ddb7aa430cd6d70c9946944f86f45`. Eleven sheet headers/previews are inspected. TablesD/E contain estimated abundances/copies for1827 proteins and1848 longitudinal samples; TableF contains616 donors, D10/D23/D42. Individual sample values have not been imported into FLA. Hb normalization, 95%/5% allocation and missing-Hb imputation are uncertainty sources, not direct active-enzyme measurements.

The corrected Europe PMC `AUTH:Palsson` query and verified author metadata are archived in `evidence_extension_v2/`; earlier zero-result author-field queries and an interrupted attempt remain preserved. The raw query includes homonyms/off-topic papers and is not a curated RBC count. PMC browser checks and HTTP500 XML failures for Issaian/PFK are recorded; RBC-GEM/PIMT primary XML is archived. G6PD/PIMT supplementary measurements and raw mass spectrometry are not downloaded. Original JBC attachments are no longer present in Downloads/mmc1; two byte-identical archived source copies substitute only for verifying those missing external inputs. All other registered reference hashes remain checked; no historical manifest or source was rewritten.

All24 targeted source-review tests pass; the full QA suite was not rerun in this documentary/source-analysis pass. Proteomics is proposed as uncertain Vmax/capacity information, not Km, equilibrium constants, PTM occupancy or missing NAD(P)(H) concentrations. Shared TKT/BPGM enzyme budgets, isoforms/complexes, active fraction, volume and temperature must be audited before a soft prior is defined. Next: source-preserving priority-enzyme extraction from S6 with donor metadata, then source/complex reconciliation and synthetic identifiability testing. No IC, kinetics, availability threshold, reaction, ODE simulation, optimizer or model promotion is changed; exact Bordbar J1 and biological readiness blockers remain intact.

## 2026-10-06 - RBC-GEM exhaustive executed-network audit and reversible corrections

User requested missing-reaction corrections in Rxn_RBC.txt/ODE using RBC-GEM and its supplements. Report: `tasks/fla_rbc_gem_network_audit_2026_10_06.md`. Separate archive: `output/rbc_gem_network_audit_2026_10_06/`. Retrieve 33 source resources with pinned Git blob/provider MD5 and SHA256 receipts: published 1.2.0 commit5347d80275be01e410aa9787b0aac99497a8ed57, current1.3.0 commit43fd381d9eb8a8a4079629012362312960e1c009, model JSON/curation/GPR/complex/reference tables and S1/S2/S5/S7. Prior S6 original is reused hash-identically. External source code and supplied HTML are not executed. Git full models contain3275/3290 reactions including boundary reactions, not the article's biochemical-reaction count. Common reaction IDs have identical stoichiometry between these versions.

Compare all100 executed ODE columns with explicit compartment-preserving mappings for107/113 pools. Project only declared H/H2O/Pi/PPi/CO2 currencies, never another unknown metabolite. Final comparison_v2:82 projected equivalents,13 unmatched reactions,5 unresolved pool-identity reactions and47 closed unmatched candidates. An initial comparison had three incomplete aliases and remains preserved/superseded. Equivalence is projected stoichiometry, not full atom or kinetic validation.

Synchronize RBC/Rxn_RBC.txt with the historical100-column/113-pool ODE:11 missing equations, SAM without AMP, VEGLC import orientation and explicit CYT chemostat balances. Original text is archived. Fix src/parse.py term coefficients, repeated-species accumulation and external-only/empty source/sink recognition. Both parsers reconstruct all100 historical columns exactly. CYT parity does not close a physical compartment. The historical kernel, schema2 structural parser, reaction limiter, working-reference config, Bordbar workbook, exact55 J1 entries and59 unmeasured inputs remain unchanged by hash.

New isolated adapter src/rbc_gem_network.py exposes historical/redox_stoichiometry/rbc_gem_core modes. Correct CAT/XAO oxygen-peroxide coefficients; core additionally tests OPLAH-off and ATP->ADP-coupled GSSG/urate exports. Recompute reaction_consistent factors against the whole modified reaction matrix; track executed rates, not clipped derivatives. Five optional explicit branches (ARGN, XPPT, ACYP, GMPR, GSR_NADH) require all kinetic inputs and default to zero. None is activated in the replay campaign or calibration/API. Historical mode remains bit-identical; no default migration or artificial ATP source.

Important unresolved findings: VCSE creates carbon by using AKG instead of a C4 product; METTHF conflates methylene/methyl folates; CYT is buffered; cytosolic ACO1/IDH1/ACLY cannot be rejected solely for absent mitochondria; shared AK1/HPRT1/GSR capacities and explicit metHb/TXN/FMN acceptor cycles need contracts. RBC-GEM removes OPLAH, but Deep Red2026 detects O14841 (Sheet1 row2004, F~1227/G~217 copies/cell). Do not promote absence/zero activity from an older curation or active flux from protein detection. Recent GLUD1/GDA/ASRGL1 evidence likewise prevents deletion solely by GEM absence. Branches, GPR and proteomics are hypotheses/uncertain capacity support, not Km or redox-pool measurements.

Complete source-only S6 extraction:62 selected proteins,616 donors,1848 D10/D23/D42 samples. Each of D/E has114576 values,6247 reported zeros and no missing values in this subset. Units are nmol protein/gDW and copies/cell, two representations of one estimate, not independent assays. Their columns differ in163 positions, so join strictly by sample ID. The initial positional-equality attempt failed and is retained; priority_proteomics_v2 is the final sealed extraction. Preserve TableF donor metadata and both Deep Red F/G calibrations without conversion/imputation or training. Independent workbook-cell verification checks all229152 numeric values and17864 TableF cells exactly, plus source/sample/time/unit keys and archive hashes; all pass. REDS cohort overlap and active-enzyme calibration remain unresolved.

Complete eight preregistered free J1-J4 integrations at fixed kinetics/IC/threshold, strict and ultrastrict, in335.7 seconds. Historical/OPLAH-off/redox-only/core ATP J4 ultrastrict:0.0007510433/0.0007724954/0.0007510427/0.0007664191 mM nominal, versus Bordbar1.079765. Core adds~2.05%, OPLAH-off~2.86%, nowhere near restored adenylate partition. All7632 numerical quadrature/balance controls and1423774 pointwise convergence comparisons pass; minimum checked concentration zero with no negatives at declared tolerance. Historical accepted time/state arrays reproduce prior runs exactly. These are numerical comparisons, not independent experiments or biological calibration success.

QA:952 passed,2 skipped in102.28 seconds, including30 new tests; skips concern missing original JBC/Nishino inputs, not RBC-GEM. Six Optuna warnings and Python3.14/Pydantic startup warning are pre-existing. Independent network/replay verification passes207 checks, including all retrieved hashes, catalogue/GEM columns, saved budgets and seven live ODE evaluations per replay. Source-cell verification receipt is separate. Executed code, contracts and updated documents are captured in the final archive manifest; older manifests/archives remain untouched.

Decision: retain catalogue/parser corrections and reversible adapter, do not promote core or activate candidate capacities. Close biochemical identities/OPLAH activity and shared enzyme/redox budgets before additional network fitting. No J46 extension, optimizer, latent-state fitting, source normalization, teacher generation or biological readiness override. Existing13-check/six-domain block remains valid. Reproduce in fresh directories using scripts/fetch_rbc_gem_network_sources.py, audit_rbc_gem_network.py, extract_rbc_gem_priority_proteomics.py and run_rbc_gem_structural_diagnostic.py; verify with verify_rbc_gem_network_audit.py and the bundled-openpyxl verify_rbc_gem_proteomics_cells.py.

## 2026-10-06 - Reversible C4/folate closure, finite redox mechanisms and OPLAH retention

User authorized the three remaining biochemical priorities, expressly retaining OPLAH because recent protein detection conflicts with older GEM exclusion. Implement a separate adapter `src/rbc_biochemical_extensions.py`, version airbc-biochemical-diagnostic-2026.10.06-v1, and config `config/fla_biochemical_closure_diagnostic.json`. Report: `tasks/fla_biochemical_closure_2026_10_06.md`; archive: `output/biochemical_closure_2026_10_06/`. All111 files of the preceding RBC-GEM sealed archive verify unchanged. Historical kernel/catalogue/schema2/limiter/working profile/Bordbar workbook and kinetic seed remain unchanged; no API/default/teacher migration.

VCSE now has a C4 diagnostic: CYSTHIO+H2O->CYS+AKB+NH4 rather than AKG, eliminating the old +1-carbon defect. The explicit AKB state is not an untracked sink. The sum CYSTL1+2ABUTENT+2IMBUTDA closes every source formula element; UniProt/Rhea14005 confirms chemistry. Native CSE kinetics are retained conditionally, intermediate elimination/fate and AKB(0)=0 remain declared diagnostic assumptions. No C4 measurement or downstream mechanism is fabricated.

Split latent METTHF into5-methyl-THF(MTHF at47) and5,10-methylene-THF(MLTHF added). SHMT produces MLTHF; MESE consumes only MTHF. Optional human MTHFR consumes MLTHF+NADPH to produce MTHF+NADP, with explicit kinetic inputs and no implicit conversion; it is inactive in Bordbar replays. Preserve the unsupported old1mM latent total under explicitly named methyl-only/methylene-only partitions, not as a supported biological prior. All55 observed J1 entries remain exact. MTR/MTHFR activity, B12/FAD/MTRR, downstream one-carbon fate and old MESE Km remain unvalidated.

Add explicit finite redox carriers: NADH->cytochrome b5->metHb with CYB5OX/CYB5RED and single-site HBFE3/HBFE2; NADPH->TXN->PRDX with TXNOX/TXNRED and PRDXRED/PRDXSO/PRDXOX. Totals and electron-equivalent ledgers close; no free NADH/NADPH sink or ATP source. GEM FCYTOB5OXR/TRDRy/PRDX2OX1/PRDX2SOR/PRDX2TRDXRD match projected columns. GEM METHBCYTBR has a stored-charge residual+1 and consumes two cytochrome electrons per one-Fe Hb proxy; do not reproduce that mismatch in a one-site definition. Primary UniProt five original JSONs and pinned targeted GEM evidence are preserved; all accession/hash/chemistry checks pass. PRDX active redox units are not directly monomer copy counts. Oxygen/autooxidation, proton/pH terms, repair/hyperoxidation, active fractions and shared capacities still require evidence.

Extended modes have124 concentrations+pHi(125 states),112 reaction columns. Historical mode forwards unchanged and must use the historical114-vector; return to its preserved seed, not the extended vector with a renamed mode. Added ICs and every new kinetic input must be explicit; require whole redox chains. Reaction-consistent limiting is applied to complete extended columns, without derivative/output clipping, forcing, reset or fake initial-data imputation. The same1e-3 numerical threshold is fixed; new real active pools may lie below it and need future sensitivity auditing. Protein detection does not supply those pools or constants.

OPLAH is retained by default with its archived ATP->ADP consumption. `oplah_policy=diagnostic_off` only zeros the rate in a named countertest; no reaction/gene/seed is deleted. Source conflict O14841/DeepRed Sheet1 row2004 versus GEM exclusion is preserved, not resolved by automatic zero or positive activity. New ABC-export coupling is a separate explicit option and is off in this campaign.

Complete10 free Bordbar J1-J4 replays (five preregistered structural cases each strict/ultrastrict) and4 isolated synthetic redox replays0-2 in731.7 seconds. All11480 quadrature/budget checks and2142136 numerical convergence comparisons pass; minimum checked raw concentration zero and executed closure numerical. Ultrastrict ATP: C4only0.0007547004, folates methyl-only0.0007510429, combined methyl-only0.0007547005, combined methylene-only0.0007588565, combined OPLAH-off0.0007766316 nominal mM. Prior historical0.0007510433; nominal Bordbar J4 ATP/ADP/AMP1.079765/1.073256/0.539208. No case restores ATP/ADP/AMP; no folate partition is selected. The four synthetic chains conserve totals/ledgers, consume finite available acceptors and keep ATP zero. New redox branches/MTHFR remain inactive in all biological replays; no predictive benefit is claimed.

Pass30 new tests including372 zero-boundary probes. Full QA982 passed/2 skipped in127.70 seconds, six existing Optuna warnings and Python3.14/Pydantic startup warning. Independent verification passes2377 checks: every campaign input/output and parent archive hash, source chemistry/columns, exact55 observed ICs, frozen other entries/declared folate partitions, budgets, carrier/redox totals, electron bounds, seven live RHS/limiter reevaluations per replay and stored-common-grid convergence. It does not separately reconstruct Gauss-node integrands not stored. Final catalogue explicitly preserves27 external pools and matches112 matrix columns; the initial matrix-only catalogue remains archived, not the final compartment contract. Executed code/docs and immutable receipts are sealed without rewriting the parent.

Manuscript methods2.34/results3.36 and active tasks updated. Next rebuild the augmented FLA balance/observation/identifiability contract, support active redox pools and enzyme kinetics with matching units/source/temperature, and audit small-pool limiting/acid-base/shared capacities before biological activation. CYT/methylation and C4 fate remain open. No optimizer, source normalization, latent inference, J46 extension, readiness override, ATP source or global promotion occurred; historical thirteen-check/six-domain biological readiness still blocks fitting.

## 2026-10-06 - Reference-anchored reduced dynamic model: project objectives

User proposes four pillars to focus costly calibration: Bordbar/Yurkovich metabolic evidence, RBC-GEM network reduction, Issaian proteomic capacity information, and population-atlas validation. Formalize the strategy in `tasks/fla_project_objectives_2026_10_06.md`; update manuscript development target/introduction/methods2.35 and active task priorities. This is a planned RBC-GEM-informed reduced dynamic ODE model, not an assertion that all current reactions/kinetics are already an exact validated GEM reduction.

Live primary-source checks establish that PMID41846981 and DOI10.64898/2026.03.07.710284 identify the same Dzieciatkowska/Issaian population proteome atlas; PubMed labels it a preprint. Its abstract describes13,091 donors and aging/hemolysis/transfusion associations, not confirmed complete absolute metabolite trajectories. Detailed methods/supplements and cohort overlap were not established in this pass; public publisher/PMC access restrictions are not replaced by assumed independence. Issaian2025 has a published Blood2026 version, DOI10.1182/blood.2025032915/PMID42224377, which is distinguished from the supplied preprint/supplement version. The cited Bordbar2015 study uses24 fasting-state individual profiles and does not resolve our local storage-table lineage; Yurkovich2017 is the distinct quantitative temperature/storage study. RBC-GEM FVA outputs remain model predictions, not experimental teachers.

Define reconciliation through source-specific observation operators, contexts and initial states, not direct trajectory pooling. Preserve exact55 local Sheet1 J1 values and source normalization uncertainty. Proteomics supports soft effective-capacity priors with explicit kcat/active-fraction/volume/site/complex/shared-enzyme uncertainty, not direct Km or redox-pool initialization. Atlas measurements used in development cannot simultaneously serve as untouched validation; confirm available observables and donor/condition overlap before claiming external prediction. Clinical outcomes currently lack a validated AIRBC observation model.

Next deliverable is a joint source/role/cohort manifest with held-out partitions, followed by augmented balance/identifiability contracts, active-pool/shared-capacity audits and restricted synthetic recovery before biological fitting. No data merging, normalization, new kinetic conversion, simulation, optimizer, reaction activation, IC change, readiness override or model promotion is performed in this documentary pass. Historical evidence remains unchanged; ATP partitioning remains unresolved. Source URLs and role/version boundaries are recorded in the objectives document.

## 2026-10-06 - Common source, observation and cohort manifest executed

User requested the common manifest before any fusion/optimization. Create a separate inventory-only design, builder and29 regression tests: `config/fla_common_manifest.json`, `scripts/build_fla_common_manifest.py`, `qa/test_fla_common_manifest.py`. Execute into fresh `output/fla_common_manifest_2026_10_06/`; report `tasks/fla_common_manifest_2026_10_06.md`. Update active tasks and manuscript methods2.36. No prior archive or historical role record is rewritten.

Ten source identities/eight dataset descriptors/seven cohort groups distinguish local unresolved Sheet1 provenance, Bordbar2015 kinetic lineage, candidate storage publications, YurkovichJBC, GEM/DeepRed proteomics, population-atlas metadata and Bardyn/Michel. Atlas PMID/DOI aliases represent one preprint; Issaian2025/Blood2026 are versioned within one study, without asserting supplied-file equivalence. Live PubMed indexed metadata confirm these publication identifiers/status; full atlas methods/supplements and donor overlap remain unresolved.

Reconstruct8097 channel representations and2249 sample records:55 Sheet1 series/770 values;96 JBC channels/11886 values/372 sheet-sample records;62 S6 priority proteins in D/E/229152 represented values/1848 samples/616 source donor IDs;3799 DeepRed proteins under F/G alternative calibrations;98/98/28 Bardyn-control/supplemented/Michel rows. These are heterogeneous bookkeeping counts, not independent sample totals. Other-species/assay/PTM/interactome resources and pinned GEM materials remain resource-level evidence; full S6 and atlas metabolomic observations are not imported.

Retain182 JBC zeros, exact sampling coordinates, source-cell/channel keys and complete sheet-specific coverage. Positional blocks do not create donor IDs or cross-sheet/temperature pairing. Identify exact local B13PG/B23PG and P2G/P3G duplicate curves; preserve all55 J1 values. Use the explicit catalogue for compartments, including intracellular E4P. D/E join by sample ID and share one evidence group; F/G are alternative estimates, not independent replicates or active enzyme capacity. Bardyn58/61 constant-one rows remain suspected excluded placeholders. Prior exploratory exposure means Bardyn/Michel are not newly certified pristine holdouts. All unverified cohort relationships remain unknown; no split is fabricated.

Check155 distinct upstream sealed files/receipts and174 total input hashes, with identical protected inputs after build. Seal nine output files. Read-only verification reconstructs channel/sample/dataset/cohort/relationship tables and checks all174 input/nine output hashes; this is source reconstruction using the same builder, not a separately implemented independent algorithm. Combined targeted QA76 passed/one skipped existing JBC test requiring original Downloads files; archived byte-preserved copies remain hash-checked. Startup Python3.14/Pydantic warning is pre-existing; full QA is not rerun. Reproduce with `python scripts/build_fla_common_manifest.py --out output/fla_common_manifest_new`; verify with `--verify output/fla_common_manifest_2026_10_06`.

No source normalization, value fusion, teacher generation, latent initialization, Vmax conversion, ODE, optimizer, reaction activation or readiness/default migration. Exact55 Sheet1 J1, kernels, kinetic context, working reaction-consistent strict profile, OPLAH and historical readiness are unchanged. Next resolve local/JBC concentration-denominator and pool-identity observation contracts, especially EGLC/ELAC, ATP-ADP-AMP, P2G+P3G and duplicate B13PG/B23PG; obtain atlas sample/cohort linkage before reserving a genuine external test. Do not replace missing source evidence by an assumed scale or source label.

## 2026-10-06 - Distinct reference litres and GEM glucose/lactate transport contract

User requested local Bordbar/Yurkovich and publication checks, donor/matched-group validation and GEM-guided intra/extracellular transport. Add a separate source-only contract, executable audit and35 tests: `config/fla_transport_observation_contract.json`, `scripts/audit_rbc_transport_contract.py`, `qa/test_rbc_transport_contract.py`. Report: `tasks/fla_transport_contract_2026_10_06.md`; final archive: `output/fla_transport_contract_2026_10_06_v3/`. Update active tasks and manuscript methods2.37. No preceding common-manifest input or archive is rewritten.

Reopen the byte-verified JBC workbook and recheck876 selected numeric cells/headers/units: intracellular glucose/lactate, extracellular assay glucose/lactate, hematocrit and two pH channels. Hematocrit has126 values, overall0.548-0.764; the24 measurements at4C span0.574-0.702. Individual donor IDs and cross-sheet pairing remain unavailable. Supplement p2 establishes three units split across temperatures, day0 one day after storage began and pH measured at37C, not directly pHi/pHe at4C. No Hct value is borrowed for Bordbar and no amount-normalization formula is invented.

Primary uFBA2017 PDF methods explicitly adjust BOTH intracellular and extracellular pools to mmol per total bag litre; this is not proof of either local workbook's processing lineage. Preserve the user's distinct physical reference litres and separate observation operators: cell/supernatant, cell/bag and bag/bag. Amount conservation uses d(Vi ci)/dt=-Q and d(Ve ce)/dt=Q, including denominator derivatives if volumes change. Equal/opposite concentration slopes can be correct for bag/bag observations but are not generally correct for physical cell/supernatant concentrations. Measured mM alone requires no single-cell-volume conversion; reference-volume ratios and free/total/cell-water compatibility remain necessary for coupled kinetic interpretation.

Extract15 targeted GEM records from each pinned version: glucose membrane transport,12 lactate c/e routes and two environment boundaries. GLC_Dt positive export maps to negative VEGLC; L_LACt2 exports one lactate plus one proton. GPRs include GLUT isoforms and MCT/BSG/EMB alternatives; LLAC_Cltex and ten monocarboxylate exchanges prevent identifying MCT1 alone from ELAC. Functional records agree between1.2/1.3; eleven reference annotations differ only in string/array encoding, preserved raw. Curated evidence is available from1.3 only. Bounds+/-1000 are not Vmax or instructions for an infinite bag reservoir.

Propose, but do not implement in production, a Haldane-constrained reversible glucose reduction and an explicit proton-lactate driving term with supported pHi/pHe/temperature and buffer closure. Existing GLUT zero-flux coordinate ratio49.484/5=9.8968 and irreversible default lactate efflux require source-coordinate/physical-equilibrium review before migration. Protein abundance does not supply active capacity or Km; competing monocarboxylates share carrier budgets. No ATP transport cost/source or restoration claim is added.

Prespecify donor/matched-group validation using compatible solution, temperature, processing, time origin, pool/denominator and supported donor covariates. Keep all repeated days/paired conditions of a donor together; no outcome-selected grouping, guessed donor IDs or new independence claim. With only three linked JBC donors, leave-one-donor-out would be a small transfer diagnostic, not population validation. Until linkage is established, condition-level aggregate checks must be labeled accordingly.

Focused QA64 passed (35 new/29 manifest checks); existing Python3.14/Pydantic warning remains. Preliminary unsealed source builds are preserved: initial reference-encoding mismatch, then v2 optional primary-PDF download blocked by an expired TLS certificate. No certificate verification bypass. Primary PDF was read through the web tool; final v3 is source-only with no claimed local PDF download. Existing common manifest verifies174 input/nine output hashes and reconstructs8097 channel representations/2249 samples. Full ODE QA is not rerun. No rescaling, donor split, teacher reconstruction, kinetic change, ODE, optimizer, J1 modification, threshold/default change or readiness override. Next resolve the source normalization and donor key, then test an opt-in amount-conserving transport adapter at fixed parameters before biological calibration.

## 2026-10-06 - User-selected cell/supernatant coordinates and fixed reversible transport executed

User rejects applying uFBA normalization, authorizes distinct physical volumes using Yurkovich hematocrit, selection of working keys/normalization and logical diagnostic initiatives. Implement `config/fla_distinct_volume_transport.json`, `src/rbc_distinct_volume_transport.py`, source preparation, fixed-context runner, endpoint/figure reporter and verifier. Report: `tasks/fla_distinct_volume_transport_2026_10_06.md`; archive: `output/distinct_phase_transport_2026_10_06/`. Update manuscript methods2.38/results3.37 and active tasks. The user-selected working coordinates are mmol/L packed cells and mmol/L supernatant. Original concentrations, all measured/unmeasured initial coordinates and historical defaults remain unchanged. H-weighted amounts are quantity ledgers only, not uFBA training normalization. Exact source preprocessing/free-pool/water definitions remain unverified.

Prepare372 stable source sample keys and36 sheet/temperature/positional-block trajectories. Candidate P01/P02/P03 keys are explicitly ordinal hypotheses, not verified donors. Prespecify identity ordinal matching as the primary endo/assay hypothesis and retain all six4C permutations, giving144 paired records and576 concentration representations of96 distinct source values. Reopen original workbook values/locators; no rescaling, aggregation, teacher generation or favorable pairing selection. All unknown-linkage JBC units remain one conservative validation split group; no fabricated donor-level independence.

The complete113-pool/100-reaction geometry is A=D^-1*S*Vr using explicit27-pool external classification. E4P stays intracellular. Native intracellular/membrane rates have a conditional cell-volume basis; extracellular GSH/GSSG degradation retains the fluid basis. VECYT is membrane transport from buffered CYT, not external degradation despite its projected source column. A preliminary replay was interrupted to correct this distinction; `fixed_context/` is retained/excluded, and `fixed_context_v2/` is final. Existing CYT chemostat and other historical biochemical approximations remain open rather than silently claimed closed.

Implement tied-conductance reduced GLUT/MCT hypotheses. Seed Km values are fixed, glucose directional capacities obey Haldane, and lactate has the reversible Li*Hi-Le*He drive with a declared symmetric Km approximation. Conductances are0.08796558869207803 and0.637848035897014 day^-1, deterministically tied to the old seed, not fitted biological estimates. The accessible-concentration approximation is not a verified free-water observation map. Require unforced reaction-consistent execution; historical forwarding remains bit-identical under legacy/reaction_consistent. pHi is clamped to the exact initial value and new MCT pHe=7.2 is a controlled diagnostic, not a4C measurement. Executed MCT proton export is recorded with compensating buffer-reservoir semantics, not a free acid/base prediction or ATP pump.

Complete14 free concentration J1-J4 integrations in543.53 seconds: common-coordinate clamped control and native/reversible transport at three original4C source-day0 Hct values0.580/0.574/0.632 (assay!D3/D11/D19). Geometry is constant and borrowed, not matched Bordbar donor metadata. All13146 quadrature/budget and240191 strict/ultrastrict comparisons pass; minimum checked concentration0 mM. All113 pools and100 raw/executed reaction integrals are retained. Ultrastrict ATP J4: common-coordinate0.0007510432991 mM; native phase-volume0.0007558684489-0.0007613387033; reversible0.0007016819763-0.0007033733348. None restores nominal Sheet1 ATP1.0797646. No parameter winner, optimizer, artificial ATP source, initialization change, readiness override or global promotion.

Equal clamped pH yields net lactate import under the reversible law, unlike the native irreversible efflux. Native phase-volume ELAC J4 is5.4883-6.0029 versus common-coordinate5.0051; reversible2.6974-2.8156, versus unchanged nominal Sheet1 ELAC6.9959375. Generate144 source-cell-traceable conditional directionality bounds for all six pairings: positive reduced-MCT export requires pHi-pHe<log10(LAC/ELAC). Source-day0 bounds span-0.732948 to-0.253806. They are mathematical requirements under the declared accessible-coordinate/single-route hypothesis, not measured/inferred physiological pH or proof against MCT. Inspect the six-panel figure, preserving nominal Sheet1 comparison points with unverified basis labels. Files: `fixed_results.md`, `fixed_endpoints.csv`, `fixed_trajectories.png`, `conditional_mct_directionality_bounds.csv`.

Full QA1076 passed/two source-dependent skips in92.01 seconds, including30 new phase/key/carrier tests. Six existing Optuna warnings and Python3.14/Pydantic warning remain. Workbook preparation uses bundled Python; scientific replays/tests use installed project Python because bundled scipy/pytest are absent. No dependencies installed. Unsealed final verification passes2018 controls before archive hashing: original source values/quantity ledgers, all conditional log bounds, complete stored budgets/quadrature/convergence and seven live RHS states per replay. Live checks use the same kernel; stored quadrature-node minima/integrands are not independently reconstructed. Previous common manifest and transport source audit still verify unchanged.

Next priority: source-compatible accessible-pool and supported pHi/pHe/buffer/Hb/CO2 contract before free MCT-pH replay, then restricted identifiable redox/energy diagnostics. Preserve anonymous donor linkage uncertainty and shared carrier capacities. Do not increase biological optimizer budget or select a favorable Hct/pairing/pH to conceal the unresolved ATP and lactate mismatch. This branch executes the user's working coordinate choice, not the discarded uFBA normalization or certified donor-level biological validation.

## 2026-10-06 - Accessible transport activities and acid/base contract executed

User requested the accessible-concentration, pHi/pHe and buffering contract before any new calibration. Add a separate configuration, mathematical utilities, source-reconstructing audit and85 regression cases: `config/fla_transport_access_ph_contract.json`, `src/fla_transport_access_ph.py`, `scripts/audit_transport_access_ph.py`, `qa/test_transport_access_ph.py`. Report: `tasks/fla_transport_access_ph_contract_2026_10_06.md`; sealed evidence: `output/transport_access_ph_contract_2026_10_06/`. Update active tasks and manuscript methods2.39/results3.38. Do not change the historical ODE, previous transport adapter/archive, kinetics, numerical profile, source concentrations or exact initial states.

Define an explicit conditional observation-to-accessible-activity operator a_mM=gamma*f*C/(w*r), with free substrate, phase water, recovery and activity factors separately named. Leave all biological factors null. Recovery already incorporated in source processing cannot be applied twice. Reading mM needs no single-cell volume; free-water conversion is a distinct kinetic operation. For lactate, ionic/free-pool speciation still needs support. Effective historical Km/conductances cannot silently be reclassified as free-activity affinities/capacities.

Reconstruct144 paired source records under all six unverified donor-sheet permutations. Export576 bounds and2880 directional counterfactuals across four rho ratios and five pH differences. Positive MCT export requires delta_pH<log10(LAC/ELAC)+log10(rho); direction depends only on delta_pH-log10(rho), so accessibility and pH are not individually identified by these sign constraints. The equal-mapping source-day0 range remains -0.732948 to -0.253806. Source-derived repeated bounds are not independent measurements. Reopen48 original pH source cells for4C storage, retaining37C measurement and22C reported-channel metadata. No4C pHi/pHe assignment, universal temperature correction or favorable rho/pH selection.

Use signed executed MCT proton export J_H=H*j on the bag-volume basis. Local buffer equations conserve acid equivalents and give the correct import/export signs. Reopen six saved strict/ultrastrict executed VELAC integrals and verify extracellular lactate amount closure. Prepare54 MCT-only frozen-integral buffer counterfactuals using historical beta_i30 and37C context anchors65/85 with synthetic beta_e1/10/30. These are neither4C priors nor re-integrated pH predictions. The large low-beta_e excursions exceed the local-capacity approximation. Explicit carbonate and effective total buffering must not be double counted; Hb/oxygenation, CA, AE1/Cl/HCO3, metabolic protons and gas/sampling/hemolysis contracts remain necessary. Historical empirical pH terms/minute-hour comments inside the day-based kernel are audited, not adopted or patched.

All7392 source/algebra/archive controls pass, including65 prior-seal hash checks; read-only reconstruction verifies the new sealed tables and summary. Primary RBC pH/buffer context checked from Swietach2010 (PMC3036193), Jennings (PMC4042536) and Guppy1992 (PMID1519370); limitations are saved in literature_context.json. Primary full-text search/institutional PDF excerpts were available for Swietach, while direct PMC reopening met recaptcha. No new literature parameter is treated as a storage-cohort measurement.

Focused QA150 passed (85 new/65 existing transport tests). Full QA1161 passed/two existing source-dependent skips/six existing Optuna warnings in95.35 seconds; startup Python3.14/Pydantic warning remains. JUnit evidence: `output/transport_access_ph_contract_validation_2026_10_06/qa_results.xml`, outside the sealed scientific archive. No new ODE or optimizer ran, so ATP outcomes remain unchanged. The local inventory lists14 missing prerequisite groups and never grants free-pH or fitting authorization, even when nominal fields are filled; existing biological readiness, donor/covariance and absolute-accuracy gates are not replaced.

Next: support original observation processing, accessible pools and temperature-compatible acid/base inputs, then preregister synthetic coupled carrier/buffer recovery at fixed geometry. Obtain independent pH or accessibility evidence to break their directional ambiguity before biological fitting. Preserve the six pairing hypotheses until donor keys are verified. Reproduce the audit with `python scripts/audit_transport_access_ph.py --verify output/transport_access_ph_contract_2026_10_06`; use a new output directory for a new build.

## 2026-10-06 - Transport source processing and synthetic coupled benchmark prepared

User authorized the proposed next execution. Add targeted source audit, isolated carrier/buffer simulator, frozen synthetic design, forward-control runner and36 new QA cases: `scripts/audit_transport_source_processing.py`, `src/fla_transport_buffer_synthetic.py`, `config/fla_transport_buffer_synthetic.json`, `scripts/prepare_transport_buffer_benchmark.py`, `qa/test_transport_buffer_preparation.py`. Sealed archives: `output/transport_source_processing_2026_10_06/` and `output/transport_buffer_synthetic_preparation_2026_10_06/`. Report: `tasks/fla_transport_source_and_benchmark_2026_10_06.md`; manuscript methods2.40/results3.39. Historical files/archives and source observations remain unchanged.

Reopen126 original pH37/pH22 pairs. All agree with the documented Radiometer ABL90 correction pH22=pH37+15*(0.0147+0.0065*(pH37-7.40)) within propagated three-decimal rounding: maximum residual0.001027500, bound0.001048750. Candidate constants come from the manufacturer rather than a fitted regression. This is a strong inference of derived-channel provenance, not author-confirmed software/processing. Retrieve/hash the391-page IFU; formula is chapter11 printed276/PDF296. Main JBC institutional PDF is readable online but local download returns403, retained in retrieval receipts. No4C conversion or independent double-counting of the pH channels. JBC and Bordbar Sheet1 contain no formulas; standards/extraction still do not establish final denominator, water/free-pool mapping or analyte recovery already applied.

Prepare a five-coordinate closed MCT/lactate/pHi/pHe/extent toy at fixed geometry, reusing the existing reduced carrier and acid ledger. Construct both initial export/import contexts with constant capacities and no ATP, glycolysis, gas, AE1, carbonate or metabolic acid. Use only original JBC4C sampling coordinates, not biological concentrations, for sparse timing; reserve later times after7.0417days. Prespecify bounded staged recovery, three starts,100 objective evaluations/start, clean/noisy criteria and independent later-time predictions. Future noise/scaling values are design assumptions, not experimental covariance. Concentration-derived teachers are not new independent observations.

Execute72 forward integrations: four strict/ultrastrict truth cases, four exact equivalent-family controls and64 finite-difference perturbations supporting12 observation/sampling sensitivity designs. All declared amount/acid closure, extent/quadrature, checked positivity and convergence criteria pass. Ultrastrict integrated export is+0.351333931/-0.462220077mM on the cell basis. Exact toy ambiguity when affinity is unknown: access_i and Km_i multiplied byc while initial pHi increases bylog10(c) preserve concentrations, pHe and flux. Checkc0.5/2 in both scenarios. pHe alone does not break this family; supported affinity or independent pHi/accessibility is needed. A separate test rejects extending this full-rate symmetry to unchanged known Km. No universal full-network nonidentifiability claim.

Sparse concentration-only training has three noninitial independent amount samples for four unknowns because LAC/ELAC share one conservation relation. Conditional pH observations improve the sensitivity spectrum at fixed affinity, but neither local rank nor denser synthetic data prove unique recovery. Two differentiation steps expose numerical sensitivity rather than hiding it. Both archive verifiers pass hashes and source/stored-trajectory reconstruction using the implemented audit logic; verification does not freshly rerun72 integrations or constitute a separate algorithmic proof.

Focused QA121 passed. Full QA1197 passed/two existing source-dependent skips/six existing Optuna warnings in128.63seconds; startup Python3.14/Pydantic warning persists. JUnit: `output/transport_buffer_preparation_validation_2026_10_06/qa_results.xml`, outside sealed scientific archives. No dependencies installed. Executed recovery fits0; biological replays0; promoted kinetic parametersnone. Existing reaction-consistent strict profile, exact55 J1, threshold,14 unresolved acid/base prerequisite groups and biological readiness are unchanged. No new ATP result or ATP restoration.

Next: implement bounded clean staged synthetic recovery under the frozen protocol, retain the unknown-affinity equivalent-family negative control, then evaluate noisy and untouched later-time robustness when clean recovery is supported. Obtain source processing/donor/channel lineage and supported4C accessible-pool/pHi/buffer/gas/AE1 inputs in parallel; do not initiate biological calibration merely because the toy forward controls pass. Use new output directories for subsequent experiments.

## 2026-10-06 - User-requested pause and saved recovery handoff

User explicitly requests memorization and pause. Save a persistent memory update and mark the active handoff paused. Completed source audit,72 synthetic forward integrations, verified archives and1197-passed QA remain the latest execution; no additional simulation, optimizer or biological calibration is launched. Resume on the user's return at bounded staged clean synthetic parameter recovery using `output/transport_buffer_synthetic_preparation_2026_10_06/recovery_protocol.md`, first conductance-only, then buffer/accessibility/pHi scopes with the equivalent-family negative control and untouched later-time predictions. Preserve exact J1, working strict profile, source values, historical archives and biological readiness. No scheduled or autonomous restart.

## 2026-10-23 - Resume and execute bounded clean carrier-buffer recovery

User requests resumption at the saved checkpoint, revoking the session pause. Verify the October6 prepared archive before work. Add separate `src/fla_transport_buffer_recovery.py`, `scripts/run_transport_buffer_recovery.py` and17 new cases in `qa/test_transport_buffer_recovery.py`; keep all previous hashed modules/configs/tests unchanged. Execute successor archive `output/transport_buffer_clean_recovery_2026_10_23/`. Report: `tasks/fla_transport_buffer_clean_recovery_2026_10_23.md`; manuscript methods2.41/results3.40; active handoff updated. No persistent memory edit is performed because the new request authorizes project resumption, not a new memory update.

Run72 noiseless conditional fits under the frozen truth/bounds/start/timing/error limits:12 oracle conductance,24 conductance/beta_e and36 access_i/pHi0 fits. Counts cover two initial transport directions, sparse/dense training schedules and three starts. Concentration-only, plus-pHe and both-pH plans are used in their declared stages. The access/pHi stage frees two coordinates while other inputs remain known; it does not test simultaneous four-parameter identifiability. Unknown pHi is overwritten by the candidate rather than leaked from truth. Objective integration ends at7.0417days; later observations do not enter optimization. Predictions continue freely through20.9583days. No derived-teacher independent likelihood is added.

Log-positive/linear-pH bounded least-squares uses three-point differences (step1e-4), x_scale1, ftol/xtol/gtol1e-10. These recorded implementation choices are not retuned after outcomes. Count all2613 actual residual/ODE calls, including Jacobian perturbations; maximum65 per fit against the100-call budget. All72 fits pass optimizer/numerical/parameter/holdout criteria and all24 multistart groups agree. Worst conductance/beta_e/access_i relative errors are2.71e-9/2.40e-9/1.52e-8; pHi0 absolute error6.96e-9pH; all-state scaled holdout RMSE1.74e-7 against0.05. This near-exact result is expected for a noiseless correctly specified conditional inverse problem, not biological precision.

Run144 strict/ultrastrict full-horizon fitted validations with declared state/flux/amount/acid/extent/quadrature/checked-positivity criteria. Four unknown-Km family controls use eight further integrations and preserve concentrations/pHe/flux when access_i and Km_i scale together and pHi0 shifts bylog10(c). Do not claim that pHe alone removes the family, that fixed synthetic Km has become biological evidence, or that the toy predicts ATP. No biological ODE, optimizer promotion, source normalization, latent biological IC change or readiness override.

Add `scripts/audit_transport_buffer_clean_recovery.py`, separately coding the one-dimensional conservation-based extent rate and integrating with DOP853 (1e-11/1e-13). All72 fitted trajectories agree with the five-state BDF evidence; maximum absolute state difference3.3074e-8. Independently recompute parameter-error and holdout arithmetic. Scalar audit output: `output/transport_buffer_clean_recovery_validation_2026_10_23/scalar_audit/scalar_crosscheck.json`. This computational cross-check shares the intended toy chemistry and does not constitute independent biological validation.

Successor archive read-only verification reconstructs parameter/prediction metrics, stored invariants, actual-call/training limits, multistart groups and summary; all input/output hashes pass. October6 preparation still verifies unchanged. Focused QA53 passed; full QA1214 passed/two existing source-dependent skips/six existing Optuna warnings in84.54seconds. Existing Python3.14/Pydantic startup warning remains. JUnit: `output/transport_buffer_clean_recovery_validation_2026_10_23/qa_results.xml`. No dependencies installed. No test or optimization session remains running.

Next execution: preregister the remaining noisy observation details (distribution/correlation and known-versus-estimated initial observations), freeze common per-scenario realizations using CV0.005/pH SD0.005/seeds2718/31415/1618, then run the same conditional scopes/starts/bounds/budgets and untouched temporal predictions. Report failure and parameter dispersion without cherry-picking a seed or increasing budget. Simultaneous four-unknown recovery remains a separate stress-test design. Biological denominator/free-pool/donor/temperature-compatible acid-base/covariance prerequisites and the prior ATP deficit remain unresolved. Preserve exact55 J1, legacy reproducibility, reaction-consistent strict reference, OPLAH and historical evidence.

## 2026-10-23 - Preregistered three-seed noisy recovery executed

User requests the noise robustness stage. Add isolated noise design/module/runner/audit/18 QA cases: `config/fla_transport_buffer_noise.json`, `src/fla_transport_buffer_noise.py`, `scripts/run_transport_buffer_noise.py`, `scripts/audit_transport_buffer_noise.py`, `qa/test_transport_buffer_noise.py`. Keep all previous sealed code, configurations and data unchanged. Complete design `tasks/fla_transport_buffer_noise_protocol_2026_10_23.md`; results `tasks/fla_transport_buffer_noisy_recovery_2026_10_23.md`; manuscript methods2.42/results3.41 and active tasks updated.

Retain frozen CV0.005, pH SD0.005, seeds2718/31415/1618. Before fitting, declare mean-preserving lognormal noninitial concentration noise and independent additive Gaussian pH noise, including initial pH assays. Initial concentrations and pHe context remain known exact; initial pHi is known only in the first two oracle stages and is replaced by the candidate in access/pHi recovery. All analytical errors are conditionally independent by channel/time in this synthetic design, not inferred biological covariance. Six PCG64/SeedSequence([seed,scenario_index]) panels share87 union-grid time points across scopes/plans/starts/schedules. `--prepare` seals the configuration/code and every panel in `noise_manifest.json` before `--run` can fit. No clipping, redraw, state reset, noisy-curve smoothing or observation-derived independent teacher likelihood.

Execute all216 fits and72 three-start groups in successor `output/transport_buffer_noisy_recovery_2026_10_23/`. Keep clean weights1mM/0.02pH, log/linear coordinates, bounds, starts, differentiation/stopping rules, training through7.0417days and100 actual-call limit unchanged. Record9198 objective integrations,432 fitted strict/ultrastrict full-horizon integrations and24 integrations for12 equivalent-family controls. All216 pass numerical gates;214 optimizers succeed, two exhaust the budget and retain their diagnostic best evaluated point without being relabeled successes. Twenty-one vectors approach a bound. Parameter accuracy78/216; latent holdout102/216; complete recovery66/216. All72 multistart groups agree, but only26/72 pass parameters,34/72 prediction and22/72 complete recovery for all starts. Starts are not independent random panels; three seeds/context supply descriptive ranges, not population confidence intervals.

Sparse oracle conductance passes parameters in1/6 panels yet predicts in6/6; dense oracle passes6/6. Joint conductance/beta_e passes parameters0/6 sparse and3/6 dense for either pH plan, while dense predictions pass6/6. Access/pHi sparse concentrations or plus-pHe pass0/6; sparse both-pH improves parameters to5/6 but complete recovery only2/6. Dense concentrations pass parameters1/6 and complete recovery0/6; dense plus-pHe passes1/6; dense both-pH passes6/6. Dense sampling represents extra independent synthetic assays, NOT information manufactured by interpolation. Thirty-six fits pass latent prediction with wrong parameters;12 pass parameter limits but not the original joint latent prediction criterion. Max relative conductance/beta_e/access_i errors0.8282/0.5231/1.6667; max pHi0 error0.5259pH. All12 unknown-Km families remain exact within declared tolerances; noisy concentration/pHe observations cannot break identical predictions.

Independent scalar DOP853/parameter/holdout arithmetic audit passes216 saved fitted trajectories, max five-coordinate absolute difference3.9482e-8. Output: `output/transport_buffer_noisy_recovery_validation_2026_10_23/scalar_audit/scalar_crosscheck.json`. Completed archive verifier reconstructs panels, all per-fit metrics, group/seed summaries, flags and negative controls; all protected input/output hashes pass. This is computational validation of the same toy, not independent biological evidence or a rerun of all9198 optimization integrations. Earlier clean/preparation archives remain unchanged.

Focused QA35 passed (18 new noise/17 existing clean-recovery cases); full QA1232 passed/two existing source-dependent skips/six existing Optuna warnings in195.95seconds. Existing Python3.14/Pydantic startup warning persists. JUnit: `output/transport_buffer_noisy_recovery_validation_2026_10_23/qa_results.xml`. No dependencies installed, biological ODE replay, ATP inference, parameter promotion, source normalization, exact55 J1/latent biological IC change, readiness override or persistent memory update.

Assessment: numerical execution is valid within the reviewed toy scope, but the current heuristic-weighted estimator is not reliably accurate under this declared noise. Next proposed execution is a preregistered paired current-cost versus matched-observation-likelihood comparison on these same sealed panels, seeds, starts, bounds,100-call budgets and unchanged truth-recovery limits. Use the declared lognormal/Gaussian observation model and no independent double-counting of derived teachers. Do not increase budgets or assume multistart agreement establishes biological constants. If matching observation statistics is insufficient, profile weak directions and test informative early sampling or independently supported pHi/activity/affinity inputs. Simultaneous four-unknown recovery, uncertain initial concentrations/pHe and biological fitting remain separate, unexecuted steps. Existing source/temperature/donor/acid-base and ATP issues remain unresolved.

## 2026-10-23 - Matched likelihood, budget escalation and first conditional experimental kinetic candidates

User authorizes the likelihood comparison, permits candidate constant changes and explicitly makes budget secondary. This supersedes the previous no-budget-increase recommendation as a general project rule. Preserve source measurements, exact J1 and archived reference for reversibility. Add full assay likelihood and conditional adapter (`src/fla_observation_likelihood.py`, `src/fla_transport_likelihood.py`), paired comparison configuration/runner and17 likelihood tests. Source report: `tasks/fla_likelihood_real_transition_2026_10_23.md`; manuscript methods2.43/2.44 and results3.42/3.43; active handoff updated.

Archive `output/transport_likelihood_comparison_2026_10_23/` pairs all216 archived current-cost fits with216 newly executed matched-likelihood fits on the same six sealed noise panels. Initial concentration observations are exact excluded terms; pHi truth remains hidden when estimated. No synthetic or experimental source rescaling. Primary100-call limits stay equal to isolate objective effects, not as a permanent budget cap. Matched parameter recovery135/216 versus78; latent holdout123 versus102; complete117 versus66, with54 gained/three lost complete pairs. All216 matched optimizers converge. All-start parameter/prediction/complete groups45/41/39 of72 versus26/34/22. Matched objective calls8273. Independent scalar DOP853/likelihood arithmetic checks pass216 fitted trajectories, max state discrepancy3.4434e-8. All12 archived unknown-Km concentration/pHe families retain equal likelihood; no new control integrations are claimed.

Separate prespecified secondary budget escalation selects optimizer failure only for either objective, with500 calls then2000 only if still unconverged, restarting from the original declared start. Only two archived current-cost failures qualify; both converge in115/110 actual calls under500 but remain inaccurate and fail prediction. The2000-call stage is unused. Primary100-call results are never overwritten or conflated with secondary outcomes. This distinguishes optimizer limits from stable inferential errors.

Begin actual-data fitting in the same session: `config/fla_real_glucose_pilot.json` and source-preserving preparation of56 original Sheet1 GLC/EGLC/LAC/ELAC cells plus55 exact J1 values. Fit a conditional reversible GLUT law to EGLC, with measured GLC as training-only PCHIP input through J25 and the last training GLC value held through J46. Seven noninitial EGLC observations train one effective clearance or clearance plus extracellular affinity, with three starts. Later EGLC/GLC do not enter the objective or driver. The comparison is historically exposed internal evaluation, not independent prediction. Conditional source-coordinate/geometry assumptions remain explicit; intracellular metabolism is not predicted.

Add `src/fla_profiled_observation_noise.py`: analytically profile the complete mean-preserving lognormal training likelihood with its normalizers. Residual dispersion includes model/input/assay error and is not called analytical measurement precision; no0.005 synthetic CV is imported into experimental fitting. Initial source values remain fixed. Source alias/source-denominator/donor uncertainty is not silently resolved by a successful fit.

The preliminary unsegmented real archive `output/real_glucose_likelihood_pilot_2026_10_23/` fails several BDF/strict/DOP853 comparisons and one optimizer terminates abnormally. Preserve this evidence without promotion. Diagnose sensitivity to integration across measured-input knots. Create explicit successor code/config/scripts and `output/real_glucose_likelihood_pilot_segmented_2026_10_23/`, splitting continuous integrations at every training knot/cutoff, tightening solver tolerances and declaring a stable finite-difference step and4000-call maximum. No measurement-state reset or relaxed numerical acceptance. All six successor fits converge and pass numerical criteria. Independent original-cell/replay/flux verification passes all56 cells,55 J1 coordinates and six candidates: `output/real_glucose_likelihood_pilot_segmented_validation_2026_10_23/verification.json`.

Simple fixed-affinity real candidate: effective clearance0.0376631537888491/day, conditional cell-basis conductance0.027273318260890734/day at borrowed H0.58 versus seed0.08796558869207803. Profiled total residual CV0.0205150. Conditional late EGLC RMSE1.14909mM versus11.81161 for the same conditional model's seed control; J46 prediction11.70122 versus nominal12.915. Opening Km_e gives late RMSE0.80683/J46 prediction12.31106, but two starts reach the500 bound and another stops near325.6 with a flat nearby training objective; do not infer physiological affinity or promote the large constructor-equivalent Vmax. H0.574/0.632 produce different cell-basis conductance from the same phase-weighted clearance. Export the simpler verified candidate in `config/fla_glucose_real_candidate.json` for opt-in GLUT-only replay, not automatic native-Vmax replacement.

Final focused29 tests passed (17 likelihood/eight profiled-real/four segmented). Full final QA1261 passed/two existing source-dependent skips/six existing Optuna warnings in87.20seconds; existing Python3.14/Pydantic startup warning remains. JUnit: `output/transport_likelihood_real_transition_validation_2026_10_23/qa_results.xml`. The preliminary full1257-passed run before segmented repair is retained separately. Both synthetic comparison and repaired real-pilot verifiers pass; first unsegmented pilot intentionally retains its failure. No dependencies installed, production default change, full-RBC candidate simulation, MCT/pH activation, ATP inference, source-data change, donor-validation claim or persistent memory update.

Immediate next execution: implement a reversible GLUT-only full-network successor and run reference versus the simple real-data candidate at fixed current initialization on J1-J4, strict/ultrastrict, with EGLC/GLC/LAC/ELAC/ATP/ADP/AMP and raw/executed-flux guards. Keep native VELAC and current pH handling to avoid importing an unsupported free-MCT gradient. The key test is whether the fitted transport survives release of the measured GLC driver. Extend horizon before broader kinetic optimization only after numerical checks. Candidate kinetic constants may move and budgets may expand usefully; source values and physiological interpretation still require appropriate evidence. The unresolved ATP problem cannot be claimed solved by the conditional one-pool pilot.

## 2026-10-27 - Conditional GLUT candidate tested in the free whole-network ODE

User authorizes the recorded next execution. Add opt-in GLUT-only adapter `src/rbc_glut_only_transport.py`, frozen protocol `config/fla_glut_only_free_replay.json`, runner/verifier and11 adapter regression tests. Disabled adapter delegates exactly to the phase-native reference; enabled adapter replaces only raw VEGLC before reaction-consistent execution. Native VELAC and other raw reaction laws are unchanged at a common state. Keep exact55 measured J1 and all latent coordinates/other kinetics, H0.58 borrowed geometry, clamped diagnostic pHi and threshold0.001mM. No concentration curve enters the RHS; GLC evolves freely. No new MCT or physiological pH mechanism is activated.

Complete18 fixed-context strict/ultrastrict replays: reference, reversible GLUT seed and learned GLUT, each J1-J4/J1-J10/J1-J46, extending only after preceding numerical checks. Scientific archive: `output/glut_only_free_network_2026_10_27/`. Both J4 reference profiles reproduce earlier accepted times/states bitwise. All352521 convergence comparisons pass. Executed daily balances pass38646/38646, raw/executed Gauss4/8 comparisons each34200/34200. Minimum across saved accepted/dense/quadrature concentration states is0mM; no checked negative GLUT substrate extension occurs. RHS closure maxima0mM/day. Preserve all quadrature nodes/weights/states/raw/executed rates,100 reaction integrals and seven guard-pool attributions. These checks are not a continuous interval proof of positivity.

Read-only verifier `scripts/verify_glut_only_free_replay.py` passes1914 checks, reconstructing seals, weighted integrals, increments, minima, original-source metrics, contributions and seven sampled live RHS/rate states per replay. Receipt: `output/glut_only_free_network_validation_2026_10_27/archive_verification.json`. This is neither an independently coded whole-network solver nor physiological validation.

Learned GLUT reduces nominal whole-trajectory EGLC/GLC RMSE3.444393/5.361098 ->1.224563/3.431573mM versus phase-native reference, but J46 EGLC15.387647 versus nominal12.915 is worse than reference12.509023. GLC remains6.204097 versus0.826365mM; ATP1.691866e-5 versus0.469757mM; ADP1.706068e-6 versus0.165503mM; AMP1.063145 versus0.221310mM. LAC/ELAC errors slightly worsen. J4 EGLC improves, but candidate GLC falls to0.081253 versus nominal1.275821mM. J10 has no source endpoint: only actual J4/J8 points enter its descriptive errors. Late J29-J46 remains exposed internal evaluation. No candidate promotion or ATP restoration.

Executed glucose attribution shows reference import9.291397/HK2.769200/GLC storage+6.522197mM cell basis versus candidate7.206876/2.126065/+5.080811. Nominal J1-J46 joint increments at fixed H0.58 imply HK9.294335mM, a conditional derived requirement, not independent experimental flux. After J4, reference native PGK11.248187 versus executed0.080478mM; ADP is the minimum-availability consumer at all saved post-J4 quadrature nodes. Candidate native/executed PGK11.358594/0.148984mM, with ADP minimum for99.0862% of quadrature-weighted time. Attribution along a limited trajectory is not a no-limiter counterfactual or proof of kinetic causal control. Earlier threshold/energy diagnostics remain preserved; VHK Vmax already5.0.

Add source-only joint glucose inventory audit and two tests, without re-integrating or changing observations. `scripts/audit_joint_glucose_observations.py` checks executed GLC scope before deriving `integral(HK)=-(H*delta_GLC+(1-H)*delta_EGLC)/H`. At H0.58, J1-J4 and J29-J32 nominal source intervals require negative HK-0.080121/-0.154057mM; their constant-H constraints H<=0.395985 and H>=0.814877 do not overlap. Evidence: `output/glut_only_free_network_validation_2026_10_27/observation_audit/`. This conditional exact-endpoint inconsistency does not exclude noise, source normalization/aggregation, pool mapping or variable geometry, and does not justify adding an unsupported glucose source or clipping teachers. Concentration-derived teachers must not be counted as independent observations.

Final full QA1274 passed/two existing source-dependent skips/six existing Optuna warnings in125.89seconds. Existing Python3.14/Pydantic startup warning remains. JUnit `output/glut_only_free_network_validation_2026_10_27/qa_results_final.xml`; preceding1272-passed run retained. Report and active handoff: `tasks/fla_glut_only_free_network_2026_10_27.md`, `tasks/fla_current_tasks.md`; manuscript methods2.45/2.46 and results3.44/3.45 updated. No dependencies, production defaults, source values, initial pools, acid/base mechanism or readiness criteria changed. No optimizer, commit/push or persistent memory update.

Next proposed execution: separately declare a joint free-network concentration likelihood for EGLC/GLC/LAC/ELAC/ATP/ADP/AMP and coordinated kinetic feasibility block, using exact J1, actual source sampling, explicit residual-dispersion/covariance assumptions, executed-flux diagnostics and no independent double-counting of derived teachers. Start J1-J4, then J10 before J46, compare reference/learned-GLUT starts and allow useful budget escalation. Use prior coupled energy evidence to choose the block; do not repeat exhausted single-parameter screens, blindly raise VHK or refit transport alone. This is exploratory calibration, not resolution of source lineage, physiological-pool uncertainty, donor independence or acid/base readiness.

## 2026-10-27 - Joint glucose-energy-adenylate calibration started

User authorizes the preceding next pass. Create a separately sealed exploratory calibration, `config/fla_joint_glucose_energy.json`, with six log factors: GLUT conductance, HK/PFK investment together, AK forward/reverse together, GAPDH/PGK together, PK and competing PEP phosphatase. Bounds are exploratory limits, not physiological priors. Keep HK<=5.0, all affinities, exact55 nominal J1/latent initialization, other kinetics, H0.58 geometry, clamped diagnostic pH, native VELAC and0.001mM reaction_consistent threshold. OPLAH and historical purine/redox context remain fixed. No source rescaling, new ATP source, MCT activation or biological readiness override.

Reopen original Sheet1 and verify770 source concentrations against the preceding sealed inventory before preparing `output/joint_glucose_energy_calibration_2026_10_27/`. Fit seven pools jointly at actual J4, then J4/J8 within a J10 horizon, with three starts. Use one shared profiled mean-preserving lognormal total residual dispersion and full normalizers. Common relative variance and conditional independence are explicit assumptions, not measured precision/covariance. J1 and concentration-derived teachers are not independent likelihood terms. No late observation enters selection; future J11-J46 is exposed internal temporal prediction, not untouched validation.

Add isolated source-AST fitting evaluator `src/fla_joint_calibration.py`, runner/verifier, conservative source-derived Jacobian support and21 focused tests. No historical module is edited or monkey-patched. All100 raw/executed rates and RHS match the original adapter exactly on five fixed/random/boundary contexts. Selected candidates must also pass original-path strict/ultrastrict trajectories and complete accepted-step Gauss4/8 executed-flux audits before extension. Numerical checks do not assert physiological fit.

Initial full QA1295 passed/two existing skips/six existing Optuna warnings in205.79seconds; existing Python3.14/Pydantic startup warning remains. Three subsequent cheap workflow controls verify temporal isolation, objective integration caps including Jacobian calls, and signed budget reversals. Their focused run passes. Full final QA and archive verification are recorded after completion. The first1295-passed receipt remains separate.

Campaign is running, not complete at this entry. Three numerical worker processes explore the starting points. Primary250 and cumulative secondary600 actual integration caps per start/stage are counted including finite differences; secondary is used only for optimizer failure. Preserve success/status, terminal point, lowest valid evaluated point, bound hits and actual calls separately. No optimizer convergence, J10/J46 prediction improvement or ATP restoration is implied by the design. Follow `tasks/fla_joint_glucose_energy_2026_10_27.md` and its final continuation entry; no persistent memory, commit or push requested.

Final QA continuation:1298 passed/two existing source-dependent skips/six existing Optuna warnings in179.16seconds. JUnit `output/joint_glucose_energy_validation_2026_10_27/qa_results_final.xml`; the1295-passed first run remains preserved in `qa_results.xml`. Three workflow controls pass, including mutation of future data without changing training/selection, actual objective/Jacobian budget accounting across restart, and integration of positive/negative reaction contributions before netting. Calibration and archive verification remain in progress; this QA receipt is not a biological calibration result.

## 2026-10-27 - Joint campaign completed; numerical validity accepted, biological candidate rejected

Complete six converged fits and1124 valid objective integrations: J4 coordinated/learned/seed231/354/147 calls, J10 continuations119/119/154. Only learned-GLUT J4 needs the secondary restart after250, then104 additional calls. All ODEs begin from exact frozen J1; continuation warm-starts parameters only. No measured or latent initial state, source value, affinity, native VELAC, pH policy, geometry, threshold or production default is changed. Nine primitive kinetic quantities are adjusted through six factors, not nine independently identified parameters.

Training NLL against the same nominal observations: GLUT-only40.823325 ->14.541840 on seven J4 values;91.356916 ->35.611361 on14 J4/J8 values. Best two starts nearly tie. Final selected learned-GLUT J10 start uses conductance0.0448414170/day, investment factor0.0703747598, AK0.001, GAPDH/PGK0.25, PK0.25, PEP phosphatase0.001. Last four hit lower limits. Shared residual CV1.22327 is total model/source/assay discrepancy, not measured assay precision or biological acceptance. Every Jacobian integration is counted; none of1124 evaluations is invalid.

All six original-path strict/ultrastrict audit replays pass, including J46 internal transfer. Comparisons117507/117507, executed daily balances12882/12882, native and executed Gauss4/8 comparisons11400/11400 each. Checked concentration minima0mM, raw/executed closure maxima0mM/day. Source-extracted fitting and original-path trajectories agree within declared limits. Read-only `scripts/verify_joint_glucose_energy.py` passes2556 checks, including33 protected inputs,45 outputs, original770 concentrations, training likelihood arithmetic, kinetic injection, quadrature budgets and seven sampled original/fast RHS states per replay. It does not re-integrate all optimizer evaluations or validate physiology. Receipt: `output/joint_glucose_energy_validation_2026_10_27/archive_verification.json`.

J4-only candidate ATP0.280234mM is an early-stage result, not the final parameter set. Final J10-fit ATPJ4/J8/J46=0.152875/0.112545/0.000021290 versus nominal1.079765/1.272527/0.469757mM. At J46 EGLC12.930681 nearly matches12.915, but GLC7.365007 versus0.826365, LAC0.049733 versus6.462934, ELAC19.908172 versus28.363716, ADP2.540276e-7 versus0.165503 and AMP0.932696 versus0.221310 remain unacceptable nominal mismatches. Import8.986058/HK2.744338mM leaves GLC storage+6.241721, versus nominal-0.296921. Near-exact EGLC is not correct metabolism.

Secondary report `scripts/report_joint_glucose_energy.py` exports12 training comparisons, three full-horizon cases,144 off-objective pool/comparator rows, explicit native rate-volume bases, complete signed ATP/purine budgets and a non-promoted reusable candidate in `output/joint_glucose_energy_validation_2026_10_27/comparison/`. All48 non-objective channel representations remain non-independent/duplicate-aware and excluded from selection. PEP RMSE worsens0.019981 ->3.187252mM and J46 PEP4.942643 versus nominal0.011204. Early J4/J8 PEP RMSE0.027824 ->1.123899 already identifies this regression without future leakage. Early G6P improves1.402464 ->0.944753, but full-period G6P slightly worsens0.595678 ->0.616120mM. Do not cherry-pick early ATP or the EGLC endpoint.

Joint executed ATP positive contributions10.854335 versus GLUT-only5.871436mM are offset by negative11.787306 versus6.804411. These integrate signed contributions before netting, not microscopic exchange. Major net joint expenditures are NDPK3.163899, HK2.744338, PRPPASe1.593547, PFK1.335535 and RKa0.999975mM; OPLAH remains active at0.393717. PGK after J4 is native6.842341/executed0.723325mM, with reduction allocated B13PG3.319691/ADP2.799325. This is actual-trajectory accounting, not a promise of ATP recovery after suppression. Unmeasured RIB is frozen1mM with sole balance dRIB=-VRKa and spends0.999902mM ATP by J4; R5P/PRPP/GTP/GDP/ADO/ADESUC and redox initialization remain assumptions, not newly inferred observations. IMP remains its measured J1 value0.124119mM, not a latent1mM default.

Independent SciPy lognormal-density arithmetic reproduces late fixed-training-variance NLL1736.490204541 within2.3e-13; reaction-wise signed ATP sums match within4e-15mM. Late GLUT-only NLL581.935607 uses that comparator's own frozen early dispersion; this is an exposed predictive-score comparison, not assay-noise estimation. Additional receipt `secondary_arithmetic_verification.json`. Final QA1298 passed/two skipped/six existing warnings remains valid; no calibrated default, source normalization, temperature/pH estimate, donor validation, commit/push or persistent memory update.

Decision: retain the campaign and candidate for reversible diagnostics, reject biological/reference promotion. The early seven-pool likelihood improves but permits severe measured PEP regression and does not prevent late ATP depletion. Neither optimizer convergence nor this restricted early-fit failure establishes a globally identified solution or whole-network infeasibility. Report: `tasks/fla_joint_glucose_energy_2026_10_27.md`; manuscript methods2.47/results3.46-3.47; active handoff updated.

Next execution: protected same-coordinate J1-J10 calibration including PEP/G6P, with component-wise non-regression versus the archived GLUT-only control on the nine monitored pools, defined on J4/J8 only. Keep exact55 J1, latent pools, bounds, geometry and threshold so objective protection is the only methodological change. Preserve a feasible comparator fallback and distinguish a declared numerical allowance from unknown biological accuracy. Do not use J11-J46 to choose constants/guard limits or weaken guards to obtain a winner. Only after this comparison consider a separate reversible RIB(0) feasibility/profile test, explicitly diagnostic and preserving measured J1. No further kinetic-box expansion or OPLAH deletion is justified by the present endpoint fit.

Final close-out checks:24 relevant tests pass after the reporting edits in14.08seconds (`qa_focused_final.xml`). All151 checked hashes across the new33-input/45-output seal, prior24-input/40-output GLUT-only archive and seven-input/two-output comparison seal match. `git diff --check` is clean. IMP initialization is confirmed measured0.124119mM, not a generic latent1mM value; only the separately flagged unmeasured pools are assumptions. No running calibration/verifier session remains.

## 2026-11-02 - Protected calibration resumed and launched

User returns after the pause and authorizes PEP/G6P and other monitored-pool protection before new parameters. Read live handoff and preserve all older scientific archives. Add `config/fla_protected_joint.json`, `src/fla_protected_calibration.py`, runner/verifier and21 targeted QA cases. Exact original770 concentrations/55 measured J1 are rechecked before source/guard/code sealing. Same six log coordinates, kinetic box, latent pools, affinities, native VELAC, H0.58, clamped pHi7.2, reaction_consistent threshold0.001mM and OPLAH. No extra ATP source, normalization, RIB test or production promotion.

Protect nine per-pool RMSEs on actual J4/J8: EGLC/GLC/LAC/ELAC/ATP/ADP/AMP/PEP/G6P. Fixed GLUT-only ultrastrict reference errors define numerical allowance1e-5mM+1e-4*reference_RMSE, of which25% is used for fitting and75% reserved for replay. These are engineering allowances, not assay noise/biological targets. Objective is shared-profile normalized lognormal likelihood over18 values, not the prior seven-pool objective. No direct comparison of different-sized NLLs or independent teacher duplication. Other46 channels are audited, not claimed hard-guarded or independent. No late value enters guard limits or parameter selection.

SLSQP with shared cost/constraint/finite-difference cache runs three starts: control, rejected joint fit, log midpoint. Every trace row is flushed to JSONL; completed fits get separate seals; explicit resumption preserves cumulative call counts and does not infer convergence from interrupted stages. A real feasible control is retained in every fit. Primary250/cumulative secondary600 actual integrations include perturbations; best valid guard-feasible evaluation is distinct from optimizer status. Original-path J4/J10/J46 strict/ultrastrict and complete executed-flux audits follow, with J4/J8 guards checked again at later replay horizons. Candidate failure falls back to the control without changing thresholds. No biological acceptance follows from numerical/training-guard acceptance.

Scientific archive: `output/protected_joint_calibration_2026_11_02/`; detailed preregistered report: `tasks/fla_protected_joint_2026_11_02.md`. Full QA1319 passed/two existing skips/six existing Optuna warnings in205.84seconds; existing Python3.14/Pydantic startup warning persists. Receipt: `output/protected_joint_validation_2026_11_02/qa_results.xml`. Campaign still running at this entry: early guard-feasible improvements are not yet original-path validated, no completed-fit/global-convergence/ATP-rescue result is asserted. Final result will follow in a completion entry.

## 2026-11-02 - Protected campaign completed; nine early guards pass, wider calibration still fails

Complete three converged SLSQP fits in208/261/402 actual objective integrations (871 total,240 feasible, none invalid). Rejected-joint and midpoint starts use declared secondary restarts after250 calls; all cumulative counts stay below600. Select the lowest guard-feasible training-NLL evaluation, including derivative probes. Winner label `control` means the control-initialized SEARCH, not an unchanged control or fallback; its selected point differs from the terminal optimizer point. Selected nine-channel NLL31.8760745 versus GLUT-only92.3381; the previous rejected candidate rescored on the same18 values gives35.7333. Do not compare this directly to seven-channel scores or equate close multistart costs with identifiability.

All nine fitting/original-path early guards pass. Eight training RMSEs decrease; PEP0.027823825 ->0.027827014mM increases3.19e-6 within the frozen numerical allowance, NOT an improvement. G6P1.402464 ->0.207126, ATP1.179142 ->1.076975, ADP0.987604 ->0.415911 and AMP2.012606 ->1.255294mM. PEP is the active constraint; aggregate J4/J8 protection does not guarantee each point. GLC J8 is worse despite lower two-point RMSE. Factors GLUT0.85278995, investment0.02, AK0.001, GAPDH/PGK1.11059294, PK0.80781831 and PEP phosphatase0.61233450. Investment/AK hit lower bounds; total residual CV1.22878 includes model/source/assay error. GLUT conductance0.0232584116/day, affinities unchanged.

Six original full-adapter strict/ultrastrict J4/J10/J46 replays pass117507/117507 convergence comparisons,12882/12882 daily balances and11400/11400 each raw/executed Gauss4/8 comparisons. Full/source-extracted trajectory parity and all nine early guards pass without fallback. Minimum across saved accepted/dense/quadrature concentration states0mM, not a continuous-time positivity proof. Reconstruct770 original concentrations and all55 measured J1; all latent initial pools, geometry, pH, native VELAC, threshold, other kinetics and OPLAH unchanged. No source rescaling, ATP source, RIB test, new kinetic lever or production default.

Primary verifier passes4705 checks, including independent density arithmetic, per-fit feasible selection, seals and seven sampled original/fast RHS/rate states per replay, not full re-execution of all optimizer ODEs. Secondary comparison exports165 pool/comparator rows,21 signed pool budgets and an explicitly unpromoted candidate. Independent secondary verification passes846 hash/arithmetic checks; max full-density NLL difference1.42e-14, signed-budget difference3.55e-15mM, budget/endpoint discrepancy2.02e-7mM. Receipts: `output/protected_joint_validation_2026_11_02/archive_verification.json`, `secondary_arithmetic_verification.json` and `comparison/manifest.json`. All checked parent/comparison archive seals match.

ATP J4/J8/J46 remains0.126445/0.084701/0.000021399mM versus nominal1.079765/1.272527/0.469757. J46 EGLC17.151448/GLC6.291967/LAC0.129211/ELAC19.374754 remain far from nominal12.915000/0.826365/6.462934/28.363716. PEP J46 avoids prior4.942643 accumulation but is0.00013585 versus nominal0.011204mM. Full-period PEP RMSE0.019981 ->0.021531 and glucose/lactate errors worsen, whereas G6P0.595678 ->0.115187 improves. The training constraint is not a long-horizon guarantee, and J11-J46 is exposed evaluation, not independent validation or selection.

Other46 audit-only channels show17 raw training-RMSE increases and22 full-period increases; representations/duplicates are not independent assays, and no significance claim is made. Early F6P0.254513 ->0.715042 and B23PG0.403227 ->0.550146mM are material off-objective regressions. ATP positive/negative executed contributions7.999860/8.932831 leave-0.932971mM; main net expenditures NDPK3.268288, PRPPASe1.595348, RKa0.999975, HK0.760960 and PFK0.400772, OPLAH retained0.393887. Import5.929641 minus HK0.760960 leaves5.168681mM GLC storage. These are trajectory budgets, not causal rescue predictions.

Final QA1322 passed/two existing skips/six existing Optuna warnings in155.20seconds, including three new reporting/selection tests. Earlier1319-passed receipt preserved; current `qa_results_final.xml` is separate. Existing Python3.14/Pydantic startup warning persists. Report/handoff/manuscript results3.48 updated; no dependency installation, commit/push or persistent memory update.

Decision: numerical and nine-pool early guard contract accepted; global calibration/reference promotion rejected. NEXT, before another optimizer or RIB(0): exact saved-executed-flux audit of early F6P/B23PG regressions and PEP's active constraint at fixed control/candidate parameters, then propose duplicate-aware broader training guards. Preserve this archive and do not retrospectively use late data to reselect its constants. RIB remains a deferred diagnostic hypothesis, not an inferred concentration or assured ATP correction.

Final close-out:24 focused tests pass in8.66seconds (`qa_focused_final.xml`), all43 protected inputs and six completed fit/audit subarchive seals still match, and `git diff --check` is clean. No required calibration, QA or verifier session remains running. No persistent-memory write or version-control operation was requested.

## 2026-11-03 - Fixed-parameter F6P-B23PG executed-flux attribution completed

Execute the requested next audit without new ODE integrations, optimizer calls, kinetic edits, source rescaling or initial-state changes. Reuse GLUT-only/protected strict/ultrastrict J1-J10 archives at their respective fixed parameter sets. Exact770 source values/55 measured J1 and prior4705-check verification pass. Preserve native VELAC, clamped pHi, H0.58, OPLAH, affinities, latent initialization and0.001mM reaction_consistent threshold. New config/runner/verifier/tests are isolated from production and old sealed code. Completed archive `output/protected_f6p_b23pg_executed_audit_2026_11_03_v3/`; report `tasks/fla_protected_f6p_b23pg_audit_2026_11_03.md`.

F6P J1-J4 net excess+0.751261mM is dominated by reduced executed PFK consumption1.067734 ->0.116466 (signed delta+0.951269), partly offset by falling PGI-0.141050 and TKL2/TAL-0.058957mM. PPP return falls0.886328 ->0.827370 rather than rising. PFK raw=executed on this interval, so numerical positivity does not explain the early loss. Shared investment factor0.02 reduces VPFK2.549430647 ->0.050988613mM/day; fixed-control-state PFK capacity term-1.046380 plus altered-state remainder+0.095111 gives raw-0.951269mM. This is ordered trajectory algebra, not a causal intervention. On J4-J8 protected PFK0.131434 exceeds control0.044164 despite lower capacity; its F6P excess is largely inherited from before J4.

B23PG absolute error improves slightly at J4 but worsens at J8. J4-J8 DPGM executed0.574717 ->0.065738 while phosphatase1.968504 ->1.985787 accounts for net difference-0.526262mM. GAPDH input0.703791 ->0.687450 stays close, while PGK withdrawal0.128753 ->0.621674 rises. PGK loss attribution shifts from91.27% ADP/8.73% B13PG to100% B13PG. Model B13PG J8 falls0.000452839 ->0.000129517mM; its duplicated source signal is not an independent teacher. DPGM raw1.750715 ->0.631014 declines; retained fraction32.83% ->10.42%, but absolute limiter loss DECREASES1.175998 ->0.565276. Exact executed delta-0.508979=raw-1.119700+modifier0.610721. Do not claim increased absolute numerical suppression caused this regression or infer that changing the threshold restores ATP.

PEP absolute J4 error0.039280 ->0.010754 improves while J8 error0.002325 ->0.037856 regresses. The previous aggregate RMSE guard hid that tradeoff. Generate a PROPOSAL ONLY for eleven RMSE-guarded channels (existing nine+F6P/B23PG), plus pointwise PEP J4/J8. Retain the original engineering allowances/25% fitting margin, six-coordinate box and exact initialization. Candidate fails F6P/B23PG and PEP J8, control passes;44 other source representations remain audit-only. B13PG/P2G aliases excluded;22 future residuals are not22 independent assays. No proposal is wired to optimization or retroactively selects the parent.

All312 quadrature reconstruction/window-balance/profile checks and912/912 limiter-allocation Gauss4/8 comparisons pass. Export192 pool budgets,888 reaction rows,1824 allocation rows and source-time predictions. Maximum residual1.80159e-6mM across eight context pools/windows/profiles passes the unchanged absolute-plus-relative contract. Four exact focus supports close; no network coefficient error is demonstrated here. Independently recompute all exported pool/reaction/limiter amounts and proposed guards:8508 checks pass,55 source hashes retained. Source/compiled rate parity and common-state PFK scaling checked at14 sampled saved states. Verification is arithmetic/source sampling, not an independent solver or physiological validation.

Full final QA1337 passed/two existing source-dependent skips/six existing Optuna warnings in117.55seconds (`output/protected_f6p_b23pg_validation_2026_11_03/qa_results_final.xml`); the earlier1335-passed receipt remains preserved. Existing Python3.14/Pydantic startup warning persists. A figure is visually inspected; a separate presentation-only successor uses shared within-pool contribution scales and sparse readable ticks. Its source/output manifest is in the validation `figures/` directory, without editing the scientific archive.

Retain two partial predecessor directories. First dense-J1 bitwise check was too strong: all actual inputs/accepted initial states are exact, dense re-evaluation differs at most1.11e-16mM. Successor requires exact actual/accepted states and separate four-machine-spacing dense check. Second attempt stopped on a local parameter/path name collision before rate sampling; explicit names and an added workflow-boundary test resolve it. No failed attempt changed trajectories or sources or performed new integration. Final `_v3` is independently sealed and verified, not an overwritten repair.

Update manuscript methods2.49/results3.49 and active tasks. NEXT: implement/test the proposed broader training guards before a same-six-coordinate feasibility screen; keep RIB(0), redox initialization, threshold, OPLAH and new kinetic coordinates closed. A later VHK/VPFK decoupling remains a conditional hypothesis, not an executed lever or proof of current-box infeasibility. No commit/push or persistent-memory update requested.

Final close-out:38 focused new/executed-attribution/reporting tests pass in11.20seconds (`qa_focused_final.xml`). All161 checked input/output hashes across the new audit, separate readable-figure archive, November2 parent and GLUT-only archive match. `git diff --check` is clean. Required audit, verifier, figure and QA sessions have finished; no optimizer or ODE integration is left running for this task.

## 2026-11-03 - Eleven-pool optimization authorized and prepared

User requests optimization now. Create a separate successor activating eleven RMSE guards (nine existing+F6P/B23PG) and two pointwise PEP absolute errors on actual J4/J8. There are22 source likelihood values and13 constraints, with the same mean-preserving full-normalized lognormal shared total residual variance, not independent teacher labels or measured assay noise. Preserve exact770 source cells/55 J1, all latents, six-coordinate bounds, paired HK/PFK and GAPDH/PGK, affinities, H0.58, clamped pH, native VELAC,0.001mM reaction threshold and OPLAH. No RIB/redox fitting, new ATP source or production migration.

Implement isolated `src/fla_broad_protected_calibration.py`, config and new runner/verifier without editing old sealed code. Pass24 focused tests: all eleven RMSE vetoes, both PEP times despite improved aggregate RMSE, future/J1 isolation, invalid-data rejection, canonical aliases, full density normalizers, cached13-by6 Jacobians, resumption and actual cumulative budgets. One initial test incorrectly requested an all-perfect zero-dispersion likelihood; correct the test to isolate a single zero-reference-error channel while retaining nonzero global dispersion. Keep the no-invented-variance-floor behavior unchanged; preserve the initial failed QA receipt and rerun final QA.

Preparation re-verifies the nine-pool campaign and fixed-state flux audit, rederives original guards and compares with the sealed proposal before freezing code/data hashes. Starts are control, previous nine-pool candidate and their log midpoint. SLSQP step0.002,400 primary/1000 cumulative actual objective/derivative integrations per start, secondary only after unsuccessful termination; this is a larger engineering budget than250/600, not a pure matched-budget comparison. Complete traces, best feasible evaluation, terminal status and fallback are separate. Fit only J4/J8 inside J1-J10, then original full-RHS strict/ultrastrict J4/J10/J46 with all13 early guards rechecked. No late-data selection, relaxed thresholds or automatic physiological promotion.

Planned archive `output/broad_protected_joint_calibration_2026_11_03/`; report `tasks/fla_broad_protected_joint_2026_11_03.md`. Preparation/verification is running at this entry; no optimizer convergence, calibration gain or ATP rescue is claimed yet. Subsequent completion entry will supersede this status. No persistent-memory update or version-control operation requested.

Preparation continuation: parent4705 and guard-audit8508 checks pass, all54 input hashes match after the corrected24-case test suite. Freeze22 training values/13 constraints from exact source/GLUT-only reference; references match the prior proposal exactly. Three numerical workers are launched with400/1000 actual-call caps. Full corrected QA1361 passed/two skipped/six existing Optuna warnings in80.03seconds (`qa_results_final.xml`); retain the first failed test-only receipt. The no-variance-floor scientific likelihood was never modified. Manuscript methods2.50 and current handoff updated. Early lower-cost trials are guard-infeasible; no completed optimization or admissible gain is claimed yet.

Numerical-restoration continuation: two SLSQP starts stop unsuccessfully (midpoint65, previous_nine144 actual calls), selecting only the real control. The control-start trajectory reaches NLL about96.61 but remains just outside some frozen fitting caps. Local first-order LP descent is not an infeasibility proof: actually integrate three predeclared directions in a separate validation archive; none passes all13 guards despite slightly lower costs. Keep those three calls separate from SLSQP counts and do not select them into its sealed protocol.

Declare a separate numerical-restoration successor before additional calls, with all13 acceptance limits unchanged. Training-only near-boundary seed screen<=1e-5 normalized violation is NOT acceptance. At most17 new actual objective calls/two linearizations, h1e-4, log trust radius0.005 and minimum-L1 correction toward an interior target reserving5% of the existing allowance. No new kinetic coordinate or biological correction. First correction finds a true fitting-guard-feasible point in nine objective integrations: NLL99.776418 ->96.615834, factors GLUT0.96303370, investment0.39580749, AK0.56916353, GAPDH/PGK1.00304070, PK0.74581723, PEP phosphatase0.93366367. This is feasibility restoration, NOT NLL optimizer convergence. Total residual CV19.7946 indicates severe remaining discrepancy, not measured assay noise. ATPJ4/J8=0.0053358/0.00021184 versus nominal1.079765/1.272527mM.

Restoration archive `output/broad_protected_joint_restoration_2026_11_03/`. Preserve the completed fit and its source hashes. Generic selection initially expects a `fits/control` reference even for the one-label restoration; continuation adapter copies the first real control evaluation from the sealed restoration trace, with provenance, adding no integration or extra fit. No sealed source/fit is edited. `scripts/finish_broad_restoration.py` resumes original-path audits and records its own source hash. The first SLSQP campaign continues independently; no biological acceptance is claimed before full checks. Updated full QA1363 passed/two existing skips/six existing Optuna warnings in142.95seconds (`qa_results_with_restoration.xml`), including two extra LP boundary tests. Existing Python3.14/Pydantic startup warning persists.

## 2026-11-03 - Broader optimization completed through strict feasibility restoration; no ATP rescue

Stop only the verified stagnant SLSQP master and its three numerical workers after the separate restored candidate has passed full J1-J10 checks; keep J46 restoration audit running. Preserve all original traces. Explicit interruption manifest records764 completed logged objective integrations:control555 unfinished, midpoint65 and previous_nine144 unsuccessful completed fits. One extra in-flight integration may have been interrupted, not fabricated in the count. No main-campaign optimizer convergence, completed-calibration state or admissible gain is claimed. Both completed fit seals remain intact. `interruption_summary.json` and manifest state prevent confusing this interrupted attempt with the delivered successor.

The delivered restoration archive passes all13 UNCHANGED fitting and original-path guards. Same22-value NLL99.776418 ->96.615834; nine actual objective calls, two feasible evaluations including the real control, one minimum-L1 inward correction. This is not convergence to an NLL optimum. Preserve all six coordinates/primitive bounds, original770 source cells/55 measured J1 and every latent initial state, native VELAC, diagnostic pH, H0.58, affinities,0.001mM threshold, OPLAH and production defaults. GLUT conductance0.02626512463/day, VHK Vmax1.97903744, PFK Vmax1.00908374mM/day; complete unpromoted overrides in `output/broad_protected_joint_validation_2026_11_03/comparison/candidate.json`. `run_broad_restoration_pipeline.py` bridges the immutable fit/reference adapter for one-shot fresh successors; no completed fit is modified.

All six original-RHS J4/J10/J46 strict/ultrastrict replays pass117507/117507 comparisons,12882/12882 executed daily balances and11400/11400 each raw/executed quadrature checks. All113 concentration trajectories and100 reaction rates retained, full/fast state parity passes; minimum across checked accepted/dense/quadrature concentrations0mM, not an interval proof. Independent verifier passes1152 checks including22-value likelihood,13-guard arithmetic, parameter injection, source/fit/audit seals and seven live original/fast RHS checkpoints per replay. Not all optimizer ODEs are independently rerun.

Secondary verification passes801 source/report/provenance checks over165 pool/comparator rows and33 signed budgets. Confirm exact same parent/child13 caps and biological contexts, restoration seed equals its original parent trace row, and copied control equals the restoration's first actual evaluation. Adapter source/trace hashes and interrupted/child/local/report/baseline seals match. Independent full-density NLL difference at most7.11e-15, signed-budget difference5.33e-15mM. Receipts `restoration_verification.json` and `secondary_verification.json` in the validation directory.

Training B23PG RMSE0.403227 ->0.321445, G6P1.402464 ->1.373741 and EGLC0.935594 ->0.865189mM improve, while GLC/AMP/F6P rise slightly within engineering allowances. PEP absolute J4/J8 errors0.039261583/0.002327255 versus control0.039280073/0.002325143: J8 held within tolerance, not improved. Earlier nine-pool candidate rescores36.0186 on the same22 values but fails F6P/B23PG/PEP J8 and is not admissible. Broader constraint acceptance does not turn its NLL difference into physiological validation.

ATPJ4/J8/J46=0.0053358/0.00021184/0.000017252 versus nominal1.079765/1.272527/0.469757mM. J46 EGLC15.596004, GLC6.100110, LAC0.159472, ELAC21.670112, F6P1.164808 and B23PG0.00040796 remain inconsistent with nominal trajectories. Residual CV19.7946 is extremely large total discrepancy, not analytical precision. ATP positive/negative executed contributions5.775129/6.708104mM give-0.932975 net; glucose import7.055997 minus HK2.079174 leaves4.976823mM GLC storage. OPLAH active0.120679mM net ATP expenditure. No ATP rescue, source correction or reaction deletion.

All13 postinitial source points show modest full-period B23PG/GLC/PEP/G6P improvements but EGLC worsening1.224563 ->1.358335mM. Other44 representations show28 raw early-error increases, largest ASP0.002505mM; tiny differences/aliases are not independent assays or significance. Full original-ODE concentration figure is visually inspected; J10 line denotes training horizon, not an assay. Late data are exposed evaluation only and never choose constants/limits.

Decision: retain a reversible numerically/guard-admissible candidate, no production/reference/physiological promotion and no optimality/global-infeasibility claim. NEXT PROPOSED: controlled reversible VHK/VPFK capacity-pair separation under existing primitive bounds and the same13 guards. This is not run here or a promise of ATP recovery; RIB/redox, pH/MCT, threshold and OPLAH remain closed. Update report, manuscript results3.50 and active handoff. No dependency install, commit/push or persistent-memory update requested.

Final close-out:full QA1363 passed/two existing skips/six existing Optuna warnings in119.54seconds (`qa_results_closeout.xml`);26 focused broad/restoration tests pass in8.60seconds. All268 checked input/output hashes across six interrupted/restored/local/comparison/parent/baseline archives match (`hash_closeout.json`). `git diff --check` is clean. All required search, continuation, audit, report, verifier and QA exec sessions have ended. The first search remains explicitly interrupted; only the separately verified restoration is a complete delivered candidate. No user changes were reverted or default parameters promoted.

## 2026-11-03 - Reversible nested HK/PFK test registered and started

Explicit request: test HK/PFK dissociation under the same guards. Freeze
`output/hk_pfk_split_2026_11_03/` after1152 parent verification checks and16
new focused tests. Compare paired1D and split2D, two starts each, with all
other restored-parent constants fixed. Original primitive capacity bounds,
all13 guard limits,22 original J4/J8 values and every initial state remain
unchanged. Nine registered fixed perturbations,200/500 cumulative actual
fit-call caps per start including probes, predeclared admissible-stagnation
stop and one optional within-budget interior repair. Changed candidate must
pass original strict/ultrastrict J4/J10/J46 audits; later residuals cannot
choose parameters. No source edit, biological promotion or RIB/redox/pH/MCT
opening. Campaign started; results and full QA pending. Details in
`tasks/fla_hk_pfk_split_2026_11_03.md`.

## 2026-11-03 - HK/PFK dissociation completed, early gain without ATP rescue

Complete nine fixed screens and four SLSQP fits:paired seed17/directed31,
split seed69/directed45 actual objective integrations,162 total. All four
optimizers converge within the primary ceiling; no repair, secondary stage
or manual interruption. All eight nonbaseline fixed screens fail at least
one guard, whereas both split starts find a feasible combined adjustment.
Best paired96.615785 is within1e-4 of parent96.615834; retain actual parent
as paired comparator. Split91.3669447 gains5.24884075 versus raw best paired,
5.24888898 versus retained parent. The archive's best-paired-gain field uses
the registered retained-reference rule; report distinguishes both arithmetic
quantities. No significance/global-optimality or identifiability claim.

Select split_directed:HK Vmax0.16266444975 and PFK0.64493576569mM/day, factors
0.03253288995/0.25297246913 relative to original primitive capacities.
Every other parameter, GLUT kinetics,55 measured J1, latent ICs, geometry,
pH, threshold, native VELAC and OPLAH unchanged. Same13 original early caps,
not newly relaxed or rederived from a less protective parent. All six
original strict/ultrastrict J4/J10/J46 audits pass117507 convergence checks,
12882 daily balances and11400 raw/11400 executed quadrature checks. Minimum
checked concentration0mM, no continuous-time proof. Fast/full parity and
seven live raw/executed/RHS checkpoints per new replay pass.

Primary1123 checks; secondary1754 checks reopen770 source cells and verify
110 pool/comparator rows,94 signed full/period budgets and source/report
hashes. Maximum budget difference7.66e-15mM; report228 arithmetic checks.
Both PNG comparisons visually inspected, no overlapping labels. Full QA1379
passed/two existing skips/six existing Optuna warnings in167.99seconds;
42 focused tests pass in14.10seconds. Initial16 new tests passed before
freezing. Source-input and completed parent archives are never modified.

Early G6P RMSE1.373741 ->0.202344, F6P0.254520 ->0.046837, B23PG0.321445 ->
0.259481mM. ATPJ4/J8=0.0210574/0.00030533mM remains far below nominal
1.079765/1.272527. Residual CV14.2743 includes severe model discrepancy.
J46 ATP1.77345e-5mM versus nominal0.469757; EGLC worsens15.596004 ->
16.825361 and GLC6.100110 ->6.896167mM. Early guard acceptance is not
all-time protection. Sixteen unguarded representations have raw early-RMSE
increases versus parent (largest GMP0.028762mM); aliases/correlations remain.

Executed ATP production5.775129 ->4.976611 and consumption6.708104 ->
5.909585mM leave nearly unchanged net depletion-0.932975. HK expenditure
falls2.079174 ->0.392892, while other sinks compensate and production falls.
Glucose import6.165773 minus HK0.392892 leaves5.772880mM accumulation,
versus4.976823 before. These trajectory ledgers are not causal interventions.

Decision: dissociation improves conditional early fitting but does not solve
ATP or late glucose. Export remains opt-in, no reference/default/biological
promotion. Preserve paired parent for rollback. Proposed next: preregister
progressive J1-J15 with actual J11/J15 and explicit temporal glucose/lactate
protection before further parameter freedom. Not executed, and exposed
late observations are not blind external validation. Update manuscript
methods2.51/results3.51 and current handoff. All fit/audit/report/verifier/QA
processes have ended; no commit/push, dependency install or persistent-memory
write requested.
