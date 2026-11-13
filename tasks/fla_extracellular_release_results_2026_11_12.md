# Extracellular /2 release: bounded campaign completed and verified

Date2026-11-12. Claude prepared code; Codex reviewed, tested and executed it.
The earlier control-gate prediction extraction fix is retained. No new source
or scoring change was needed after this verifier delivery. Tests:
`qa/test_verify_extracellular_release.py qa/test_fla_extracellular_release.py`:
51 passed in18.31s. Full repository suite not run.

## Result

Release: `output/extracellular_release_2026_11_12/release/provisional_extracellular_reference.json`.
Selected ONE coherent vector: **working_centre**, the audited fallback.
Status `provisional_extracellular_reference`, `improved_over_fallback:false`,
`activation_allowed:false`, `default_replacement:false`.

Selection is among the qualified compatible references/candidates considered,
not the best of every historical context. Earlier transport campaigns with
different Km/transport/network/initial context were listed but not ranked.
No curves or parameters were stitched together from different candidates.

38 new ODE evaluations:4 restoration/replay and34 search. All38 pass the
physical-support gate. Both required source replays match their archived
predictions bitwise.145 old rows were screening hints, not qualified cache:
the transitive source proof was insufficient. No cached ODE was silently reused.

No distinct new release-admissible seed was constructed. Four projected
directions were too close to their anchors and caused no ODE; the random
direction and its Phase-I replay pass inherited metabolic guards but fail the
additional release criteria. Only ONE actual SLSQP start was optimized, from
the working centre. It stopped after two iterations on declared stagnation.
This does NOT demonstrate exploration of multiple feasible basins or global
infeasibility. Do not start another campaign automatically to exhaust a ceiling.

The candidate35 historical reference is not an extracellular improvement:
utility+1.546269e-5 vs working-centre0, and it fails this release's additional
admission criteria. The optimization's first proposal reduces utility to
-7.491011e-5 but is not release-admissible and is below the declared improvement
threshold. No new finalist; zero new qualification integrations or daily flux
balances. Historical full-backend strict/ultrastrict qualification of the fallback
is referenced by its sealed receipts, not claimed to have been rerun here.

## Numerical receipt

`output/extracellular_release_verification_2026_11_12/verification.json`:

- verified:true;38 accepted-valid attempts;
-1,162,575 recorded support points checked;
-56 Jacobian columns reconstructed (records include repeated/cache-derived
  columns; this is not56 independent perturbation integrations);
-17 exported Vmax values matched to the selected injected parameter vector;
- source/context, objective, guards, seed admission, incumbent and export checks;
- new_finalists:0, qualification_integrations:0, new_daily_balances_verified:0.

The verifier and campaign both exited successfully. No commit/push, agent,
new J46 simulation, automatic activation or UI modification in this pass.

## Fit quality and limits

The release reports19 actually observed external channels at J4/J8/J11/J15.
EGLC normalized RMSE0.168464; ELAC0.828752 under declared working bands.
These bands are not assay SD and do not establish statistical validation.

| Focus quantity | EGLC | ELAC |
| --- | ---: | ---: |
| J15 predicted minus observed, historical model-unit convention | +1.359656 | -3.184371 |
| J4-J15 predicted secant slope | -0.264488/day | +0.679006/day |
| Observed secant slope | -0.473636/day | +0.836531/day |

Do NOT describe all extracellular channels as well calibrated. Worst channel
is EINO, normalized RMSE633.091; the mean of per-channel normalized RMSEs is
44.704. Tiny working scales can magnify these ratios; inspect the raw dated
residuals before biological interpretation. ATP/ADP absolute targets remain
unmet. The success here is executing/verifying/selecting a provisional reference,
not resolving the energy deficit or validating all extracellular species.

Unit status is `assumed_mM_historical_model_convention`: the numeric observation
archive has no recorded units. H0.58 is borrowed, donor unknown, latent initial
inventories unresolved. HorizonJ1-J15 only. No transferability to arbitrary new
user datasets or claim of a held-out test. Historical J46 is already exposed.

## Close this optimization tranche and return to application

Retain the frozen artifact and receipts; no further automatic optimization.
Next application tranche should expose this profile READ-ONLY with context,
receipt hash, exact scope, per-species/date residuals and ATP/ADP/EINO limitations.
An explicit click cannot override `activation_allowed:false`.

Then simplify Data -> Verification -> Calibration -> Results around real
preflight and worker states. Remove unconditional calibrationApplied=true and
fictional monitoring bags/forecast percentages. Keep unit provenance and
data validity distinct from engine compatibility. A new user's dataset must
not inherit the historical reference initialization or this profile silently.
The user-engine shifted-origin qualification is still a separate prerequisite
for launching genuinely new contractual calibration jobs; do not bypass it.
See `tasks/fla_application_return_handoff_2026_11_12.md` for the existing route
and code pointers. This app work is not contingent on ATP rescue.
