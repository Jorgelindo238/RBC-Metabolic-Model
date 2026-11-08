# Network/observation coverage and adenylate sensitivity

## Registered scope

User-authorized next priority: resolve CIT/ECIT, ARG/EARG and CITR coverage,
then select adenylate parameters by sensitivity, without another blind HK/PFK
optimization. Baseline is explicitly `J15_normalized` from
`output/fla_objective_reformulation_2026_11_03/`, NOT a promoted production
reference. Keep exact55 nominal J1 and latent pools, H0.58, native VELAC,
GLUT constants, pH clamp, OPLAH and0.001mM reaction-consistent threshold.
Parent archives remain immutable.

## Coverage contract

Use pinned RBC-GEM1.3.0 commit43fd381d9eb8a8a4079629012362312960e1c009 and
verified retrieval hashes, complete gene-evidence TSV and Deep Red protein
table. Preserve compartment identities; omit only declared H2O/H/Pi/PPi/CO2
currency. Existing source evidence:

- ACITL/ACLY: CIT+ATP+COA -> ACCOA+OAA+ADP (Pi omitted). Supported candidate,
  not an ATP source. It was excluded from the historical RBC-strict executable.
- ARGN/ARG1: ARG -> ORN+UREA (H2O omitted), supported candidate. The older GEM
  diagnostic has an optional ARGN, but it is inactive in the calibrated native ODE.
- CITR: NOS and exchange candidates need missing NO/N-hydroxyarginine or
  extracellular citrulline/other transport species. No automatic lumping or
  unsupported sink; static varying observations are retained and blocked for
  claims of full-network kinetic fitting. Protein presence is not4C activity.
- Correct the coverage contract, not raw data. Canonical roles distinguish
  conditional training targets, audit-only channels, duplicate aliases and
  structurally blocked dynamics. Source normalization is still user-assumed.

Implement an opt-in phase-aware `CoverageRHS`, independent of the older GEM-core
mode that disables OPLAH. Both new branches have ZERO default capacity and
require explicit positive substrate Km before activation. No new biochemical
kinetics or branch ODE integration are authorized here. Disabled mode must be
bitwise equivalent to the native kernel; positive reaction availability scales
all branch terms together. No production/catalog migration.

For each of J15/J46, run four necessary LP relaxations on53 canonical source
representations: historical, citrate-only, arginase-only and both candidate
columns. Use the parent's exact working scales and fixed J1. Added forward
extents do not demonstrate a feasible kinetic model. Report projected ranks,
remaining invariants and shared-adjustment needs. Diagnose interval-implied
constant H and counterfactual time-varying H without fitting volume data.

Sources: [RBC-GEM](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1012109),
[citrate tracing in AS-3](https://pubmed.ncbi.nlm.nih.gov/27813142/).
These are not the same verified cohort/normalization as local Sheet1.
NOS3's cited32857630 is a review, not direct storage-activity evidence.

## Registered sensitivity and selection

Twenty-five positive kinetic parameters from the actual native AST/frozen
overrides; APRT and AMP nucleotidase zero capacities stay closed. One baseline
and four probes per parameter: log offsets +/-log1.05 and half that step,
101 actual fast whole-network J1-J15 integrations, max3 workers. Only actual
J4/J8/J11/J15 observations enter response selection; no J46 selection.

Compute central elasticities of log ATP/ADP/AMP and working-scaled residual
derivatives for all11 channels. Log response is a sensitivity diagnostic, not
a new independent likelihood. Two-step disagreement must be<=25%; response
must exceed1e-6 and ten times baseline fast/original log discrepancy. These are
engineering screens, not statistical confidence. Save raw/executed rates on
each perturbed trajectory AND at fixed baseline states.

Direction is selected from the log-adenylate residual gradient. Its actually
integrated full-step probe must reduce mean log error by>=0.1%, worsen no
individual adenylate log MSE by>1%, and keep each other channel's working MSE
within baseline+0.01*(1+baseline). Select at most3 in descending actual gain,
excluding absolute column cosine>=0.95. Shared-parameter reaction scopes are
reported. SVD is local/threshold-dependent; no global-identifiability claim.

Audit proposed single levers with original strict/ultrastrict J1-J15 executed
fluxes, balances, positivity and full/fast parity; recheck individual admission
at both tolerances. If no lever qualifies, audit up to3 top stable effects as
DIAGNOSTIC FALLBACK, not recommendations. Only original-validated eligible
single levers survive; combined activation is NOT tested or promoted.
Old13 guards remain visible diagnostics, as in the parent protocol.

## Execution

- [x] Inspect pinned GEM/source evidence and native kinetic dependencies.
- [x] Implement isolated optional branches and coverage/sensitivity pipeline.
- [x] Pass22 focused tests and freeze sources after2299 parent checks.
- [x] Execute eight LP coverage scenarios and101 probes (all101 valid).
- [x] Validate both proposed single levers with original executed ODE.
- [x] Independently verify and visually inspect all three report figures.
- [x] Update manuscript methods2.53/results3.53 and current handoff.

Archive: `output/coverage_adenylate_sensitivity_2026_11_03/`.
Receipts/report: `output/coverage_adenylate_sensitivity_validation_2026_11_03/`.

## Results and coverage decision

The coverage contract is corrected and explicit; full physical network-observation
coherence is NOT resolved. Historical pools and all55 source channels are retained.
The adapter `src/rbc_coverage_extensions.py` supplies disabled-by-default VACLY
and VARGN options, with exact native rollback and no guessed Km/Vmax. Neither
branch was activated in any real-data ODE run. OPLAH remains present. CITR stays
static in this reduced matrix; no unsupported NO sink or transport shortcut was
introduced. Candidate activity at4C is not established by protein detection.

Necessary LP results, using the same53 canonical representations and engineering
bands, not measured assay SD:

| Matrix variant | J15 minimum multiplier | J46 minimum multiplier | Projected rank |
|---|---:|---:|---:|
| Historical |1.661963|2.804155|50|
| Citrate lyase only |0.781803|1.216622|51|
| Arginase only |1.661963|2.804155|51|
| Both candidates |0.781803|1.216622|52|
| Both + signed ARGSL, separate structural follow-up |0.344415|0.479320|52|

Forward ACLY makes CIT+0.724138ECIT nonincreasing rather than constant.
Forward arginase similarly permits ARG+0.724138EARG to decrease, not increase.
No physical constant H in(0,1) can conserve nominal amounts in8/13 citrate
and5/13 arginine intervals. Counterfactual H values are diagnostic, not measured
or fitted hematocrit. Source normalization, binding and cohort effects remain
alternatives to missing reactions.

The separately registered `config/fla_asl_coverage_followup.json` projects GEM
ARGSL/ASL as ARGSUC <-> ARG+FUM. It expands the extent cone without changing
its rank. No ASL rate law or ODE run was added; latent ARGSUC stock is not
bounded in this optimistic LP. Its lower multipliers do not prove dynamic
feasibility. CITR is the remaining analytic lower-bound bottleneck, but falls
within these chosen bands: nominal variation is not proof of biological flux
above unknown assay noise. The maximum of48 analytic lower-bound certificates
matches all ten primal minima to maximum gap8.89e-16.

Original Deep Red rows70/303/327/3234/3493 and F/G values were reopened for
ACLY/ARG1/ASL/ASS1/ANKH. ASS1 is detected in that workbook but absent from the
pinned GEM: retain this curation discrepancy. It consumes CITR and is not an
explanation of its initial increase. No NOS3 row in this table is not proof of
biological absence. Copy numbers are not converted to active kinetics.

## Sensitivity selection and original ODE checks

Twenty-five parameters,12 log-adenylate responses at four actual times,101
integrations. Full/half-step disagreement for nonzero responses ranges from
0.0000194 to0.0106845, below the registered0.25 cutoff. Thin SVD gives rank12
at relative1e-6 and at least13 locally unresolved parameter directions. There
are45 column pairs with absolute cosine>=0.95; this is not global identifiability.

Two nonredundant single levers pass the original strict AND ultrastrict J15
admission checks:

| Parameter | Baseline | Individually tested | Fast mean log-error reduction |
|---|---:|---:|---:|
| vmax_VSAM |0.2|0.19047619047619047|0.5385%|
| vmax_VPGK |40.1443275529602|38.23269290758114|0.2229%|

The reduction is a diagnostic over ATP/ADP/AMP and all four times, not a uniform
concentration improvement. Stronger PRPPASe/shared km_ATP/forward AK effects
fail protected-pool admission. Reverse AK and other eligible effects are
excluded as correlated with already selected columns, not declared inactive.

Original ultrastrict ATP J15 is0.00008335252mM at baseline,
0.00008461394 for VSAM-down and0.00008319557 for PGK-down. PGK-down slightly
worsens terminal ATP despite its aggregate gain. None restores the nominal
J15 ATP1.0138273mM. Raw RMSE increases in18/44 nonprotected channels for
VSAM-down and27/44 for PGK-down; these are descriptive, not significance tests.

Executed ATP production/consumption integrals (mM, J1-J15) are4.911014/5.843923
at baseline,4.921154/5.854061 for VSAM-down and4.901654/5.834563 for PGK-down.
VSAM's direct ATP demand falls by0.00907749mM, but changes in NDPK, PRPPASe
and other reactions compensate. Direct same-state sensitivity is archived
separately from trajectory-level responses; neither proves unique causality.

Four new original ODE replays pass76338 convergence comparisons,6328 executed
daily balances and5600 comparisons each for raw/executed quadrature. Checked
minima are0mM. Primary verification3045 checks; independent report verification
1708 checks,165 source rows,42 signed pool budgets and48 certificates across
ten LPs. QA1433 passed, two pre-existing skips, six existing Optuna warnings.
All770 source cells,55 exact J1 entries and latent initial conditions are
unchanged. No optimizer, combined-lever replay, activated coverage-branch ODE,
J46 sensitivity selection, production promotion or biological calibration.

## Next execution, not run

Use `comparison/next_single_levers.json` only as a two-coordinate conditional
feasibility-screen input, not fitted production constants. Register a small
VSAM/PGK interaction screen with the same exact J1 and numerical contract;
report timewise adenylates and all55 source channels, not only aggregate gain.
The current sensitivity basis must be recomputed if new coverage branches are
activated. Before activation, constrain latent ARGSUC and document candidate
kinetics/temperature/pool definitions; do not fit arbitrary drains to invariant
violations. CITR source/observation coverage remains a separate unresolved item.
