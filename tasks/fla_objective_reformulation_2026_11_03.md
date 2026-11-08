# Objective reformulation and reusable FLA observation contract

## Purpose and registered design

Ultimate user objective: allow research groups to calibrate the joint blood-bag
and RBC model from their own raw/relative intra/extracellular metabolomics.
This pass delivers a reusable observation-contract core and a real matched
Bordbar experiment; it does not yet claim arbitrary-file ingestion or complete
end-to-end relative-data ODE calibration.

Archive: `output/fla_objective_reformulation_2026_11_03/`.
Parent HK/PFK archive remains immutable. Only HK/PFK are free, with the same
original primitive capacity bounds, restored non-HK/PFK constants, exact55 J1
and all latent ICs. Native VELAC, H0.58, clamped pH, OPLAH and0.001mM
reaction-consistent threshold remain fixed. No network deletion or teacher forcing.

Compare three objectives on the exact same22 J4/J8 observations, two common
starts each (restored and previous dissociated selection). All use SLSQP with
step1e-4, max60 iterations, ftol1e-6 and220 actual objective integrations per
fit including derivative probes. Scalar NLL and normalized means use bounded
optimization; minimax uses an epigraph with11 error inequalities. Eta probes
never require a new ODE. The different minimax formulation is explicit, not a
claim of perfectly identical optimizer trajectories.

For pool i, freeze `a_i=0.05*median(training observations_i)` and `b=0.2`.
Residual `(prediction-observation)/(a_i+b*abs(observation))`; pool error is its
mean square. Normalized objective averages eleven pool errors; minimax
minimizes their maximum. These are engineering scales, NOT assay SDs or
published biological accuracy thresholds. Report whether unit working MSE
is achieved without promoting that to experimental accuracy. No loss clipping,
endpoint/slope/fold-change stacking or fitted residual variance for new losses.
Four declared scale-pair re-scorings are sensitivity diagnostics, not new fits.

Old13 guards become DIAGNOSTICS ONLY for all three refitted objectives. The
old guarded fit is a historical comparator, not the refitted NLL control.
Do not secretly discard candidates on old RMSE caps. Physical/numerical
requirements and source/IC exactness remain mandatory. A zero concentration
may be scored by the absolute losses even if a lognormal diagnostic is undefined.

Before fits, screen integrated balances on J1-J8/J15/J46 for11 fitting pools
and53 canonical source representations (exclude B13PG/P2G aliases). All100
extents are unknown; twelve confirmed forward laws have nonnegative integrals,
others are optimistically signed. No kinetic capacities, complete directionality,
continuous-state availability or thermodynamic feasibility is asserted. Joint
observation adjustments are shared across intervals, nonnegative and fixed to
zero at J1. Minimize their working-scale multiplier; raw observations are never
edited. Zero-only EINO stays nominal zero without inventing an assay limit.
This is a necessary relaxation, not uFBA or an ODE-existence proof.

If the eleven-channel J15 necessary screen needs multiplier<=1, automatically
run normalized and minimax J1-J15 continuation from their J10 selections,
adding only actual J11/J15 observations (44 values), with newly frozen training
scales. Otherwise stop that extension with a reason. No later residual chooses
constants. Later points are already exposed evaluation, not blind validation.

Audit each J10 selection with original strict/ultrastrict J10 replays. Audit
both J15 continuations at J15/J46; if continuation is gated off, instead audit
all three J10 selections at J46. Require executed daily balances, quadrature,
convergence, positivity and full/fast parity. Old guard failures remain visible
but do not define new acceptance. Production promotion is prohibited.

## Automated-platform contract

- Explicit source, cohort, bag trajectory, donor identity or unresolved status.
- Explicit metabolite, compartment and denominator; cell mM and supernatant
  mM are not total-bag concentrations and need no invented absolute cell volume.
- Absolute concentration, linear relative signal with a training-only nuisance
  scale, or a declared within-metabolite temporal ratio. No implicit conversion
  from relative intensity to absolute mM; treatment/control ratios need a separate
  operator. Shared-reference covariance is not claimed modelled by this core.
- Missing normalization, unknown units, duplicate channels and fabricated donor
  joins fail validation. No implicit missing-value imputation.
- `scripts/validate_fla_observation_manifest.py` validates external JSON contracts;
  a valid contract alone does not certify complete ODE initialization or identifiability.
- Example: `config/examples/fla_relative_observation_contract.json`, explicitly
  synthetic, with absolute extracellular glucose, relative intracellular lactate
  and an extracellular temporal ratio. It is not imported as biological data.
- Preserve every source value, assumption, excluded alias, fit trace and numerical
  receipt. An automated run must be able to return "not identifiable/not ready"
  rather than manufacture absolute concentrations or a biologically validated fit.

## Execution

- [x] Implement isolated observation operators, three losses and integrated LP.
- [x] Pass27 focused tests and freeze sources after1123 parent checks.
- [x] Execute six balance screens and six matched objective fits.
- [x] Execute both gated J15 continuations (all eight optimizers converge).
- [x] Complete all seven original strict/ultrastrict ODE audit pairs.
- [x] Independently verify, run full QA, inspect three figures and update manuscript/handoff.

## Completed execution record

Eight converged fits use208 actual objective integrations: J10 lognormal52/18,
normalized40/21, minimax37/16; J15 normalized8 and minimax16. No budget cap
or fit interruption. HK hits the shared0.1mM/day lower search bound in all
J10 selections; this is not enzyme-capacity identification or an infeasibility proof.

Necessary eleven-channel LP working-error multipliers are0.016542/0.016779/
0.023310 at J8/J15/J46; canonical53 need0.959227/1.661963/2.804155. Exact
nominal balances fail for all six relaxations. These multipliers act on the
engineering bands, not measured SDs. No source observation changes.

Supplemental analytic certificates (not used for parameter selection) explain
all six minima. Eleven-channel bottleneck: nonincreasing
`GLC + (0.42/0.58)*EGLC`, imposed by nonnegative HK. Canonical53 bottleneck:
constant `CIT + (0.42/0.58)*ECIT`. Other model invariants: constant CITR and
constant `ARG + (0.42/0.58)*EARG`. Their nominal source trajectories vary.
Direct matrix cancellation and error-band inequalities together with LP primal
witnesses independently certify these specific relaxation optima, not ODE or
biochemical feasibility. They do not authorize inserting reactions without evidence.

Automation must identify invariant violations before optimizing all kinetics.
Shared LP adjustment witnesses are nonunique and are not reconstructed biological
concentration trajectories. Source/volume-provenance uncertainty remains.
Expanded full QA1411 passed/two existing skips/six existing Optuna warnings.

## Common-metric comparison

The following metrics use identical22 training values and fixed scales.
NLL is re-scored for every model, not compared numerically to squared errors.

| Objective | J4/J8 NLL | Mean channel MSE | Worst channel MSE | PFK Vmax |
| --- | ---: | ---: | ---: | ---: |
| Refitted lognormal | 86.728329 | 129.687654 | 1016.534072 | 0.085424 |
| Normalized mean | 90.159301 | 37.494381 | 343.776200 | 0.489358 |
| Minimax | 87.464317 | 68.215816 | 339.304298 | 0.215293 |

All have HK0.1mM/day, the search floor. Historical guarded split re-scores
mean42.558139/worst346.142575, but unlike these three refits was constrained
by old13 caps. Do not attribute that historical difference to cost alone.
Starts broadly agree, not proof of global optimality or identifiability.
New squared errors are engineering criteria, not verified assay likelihoods.

Reject naked minimax as default here: it reduces AMP channel MSE343.776 to
339.304 while worsening F6P0.156857 to339.304. Refitted NLL sacrifices F6P
to1016.534. Normalized mean retains F6P but ATP/ADP remain near zero and AMP
excessive. None meets all unit working-MSE criteria; all fail at least one
historical diagnostic guard. No winner is biologically calibrated or promoted.

J15 continuation: normalized mean55.750696/worst527.238091; minimax
mean102.264177/worst518.965003, on44 values. Do not interpret raw changes
from the22-value scores as improved/worsened algorithm performance.
PFK capacities0.489581886/0.133724500mM/day; HK0.1. J46 normalized/minimax
ATP1.77479e-5/1.79867e-5mM, GLC6.968671/6.956652, EGLC16.922500/16.907523,
F6P0.181296/0.757990. Nominal ATP0.469757 and GLC0.826365 remain far away.

## Verification

Fourteen original ODE replays plus seven fast-parity integrations pass278617
state/integral convergence comparisons,32770 executed daily balances and29000
quadrature comparisons each for raw/executed fluxes. Checked minimum0mM,
not a continuous-time proof. Primary2299 checks reopen770 source cells/55 J1,
traces, scopes, matrices, rates and sampled live RHS. Secondary1444 checks
reconstruct275 pool/comparator rows,35 signed budgets and21 analytic certificates.
Six LP minima have primal/lower-bound gap at most2.22e-16; independent budget
difference at most9.77e-15mM. Primary verifier alone does not prove LP optimality;
the supplemental certificate verification does. Three PNGs visually inspected.

Full QA1411 passed/two existing skips/six Optuna warnings in122.68s;27 new
objective/observation and five certificate tests pass. Real11-series and
synthetic mixed3-series manifests validate, NOT as complete generic ODE fits.
Source values, ICs, defaults and prior archives are unchanged.

Artifacts in `output/fla_objective_reformulation_validation_2026_11_03/`:

- `comparison/readiness.json` and `comparison/comparison.json`
- `comparison/matched_J10.png` and `comparison/exposed_J46.png`
- `comparison/structural_balance_certificates.png`
- `verification.json` and `secondary_verification.json`
- `observation_manifest_validation.json` and `synthetic_relative_manifest_validation.json`

## Next handoff

Do not repeat an HK/PFK-only search. Next: source/GEM-informed coverage decision
for CIT/ECIT, ARG/EARG and CITR, separating missing dynamics from normalization,
binding, volume or cohort effects. Never add an artificial sink from an invariant
violation alone. Then sensitivity/identifiability-directed adenylate parameter
selection with per-metabolite acceptance; normalized residuals are a candidate
base, not a proven universal loss or deployed reference.

Universal platform gaps remain: raw-file mapping, explicit raw time-unit/storage
canonicalization, covariance/censoring, anchored relative uncertainty and full
ODE initialization. Core `time` is canonical model days; v1 structural validation
does not certify arbitrary raw units or kinetic identifiability. Multiple shooting
and conditional linear Vmax fitting are not implemented here; optimizer convergence
alone did not require them. All jobs ended; no promotion, commit/push, install or
persistent-memory-folder update.
