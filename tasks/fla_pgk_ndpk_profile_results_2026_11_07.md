# PGK/NDPK profile and executed nucleotide balances

## Decision

The fixed two-dimensional profile finds no new admissible absolute ATP/ADP
solution. Among valid screen points, the existing center remains the only
in-box grid point satisfying the temporal guard contract. Extending PGK downward, NDPK upward, or both
improves the late ADP residual but worsens ATP and breaks metabolic guards.
No production setting, Km, source cell, J1 state or network column changed.
This finite profile does not establish global infeasibility.

## Protocol and execution

Successor: `output/pgk_ndpk_profile_2026_11_07/`. Protocol:
`tasks/fla_pgk_ndpk_profile_protocol_2026_11_07.md`.

Freeze twelve factor groups at the last absolute-target candidate; vary
PGK and the common forward/reverse NDPK scale. Factors are relative to
the fixed half-step control, not relative to the last fitted values.
PGK factors are 0.25/0.5/0.75/1/1.5 and NDPK factors 0.1/0.5/1/2/4.
PGK below 0.5 or NDPK above 2 are labelled out-of-box diagnostic probes,
never candidates admitted under the previous bounds. All dated metabolic,
adenylate, zero-band and working-scale guards remain unchanged.

26 ODE attempts (25 grid points plus the original control): 24 valid,
two numerical rejects (PGK 0.75 or 1.0 with NDPK 2.0). No clipping.
Six new original-rate replays cover three diagnostic points at two
tolerances. Four archived original replays provide the same-network
control and center. All five paired points pass numerical and convergence
checks, but only the center satisfies the old fitting guard contract.
The control has no required improvement over itself and is not a candidate.

## Original-rate ultrastrict results

The absolute J15 working intervals remain ATP 0.75707-1.27058 mM and ADP
0.31580-0.58548 mM. These are engineering intervals, not measured assay SD.

| PGK factor | NDPK factor | ATP J15 (mM) | ADP J15 (mM) | Guard result |
| ---: | ---: | ---: | ---: | --- |
| 0.50 | 2.0 | 0.0000898217 | 0.00000177478 | Pass; absolute targets fail |
| 0.25 | 2.0 | 0.0000856008 | 0.00000238777 | Fail; outside old box |
| 0.50 | 4.0 | 0.0000867629 | 0.00000207291 | Fail; outside old box |
| 0.25 | 4.0 | 0.0000825815 | 0.00000278790 | Fail; outside old box |

PGK lowering alone breaks PEP J4/J8/J15, G6P J11/J15, F6P at every fit
date, AMP J4 and other guards. NDPK increasing alone breaks PEP J4,
G6P J11/J15, F6P J8/J15, AMP J4 and additional guards. The joint probe
also worsens ATP error at each dated fit point relative to the control.

## Exact transfer and latent guanylates

The executed NDPK column is ATP -1, ADP +1, GDP -1, GTP +1, AMP/GMP 0.
An ADP gain can accompany ATP consumption and phosphate transfer to GTP;
it does not establish energy restoration. Each nucleotide-family total
and ATP+GTP are conserved by this reaction alone, not by the full network.
The ledger uses signed executed NET rates, not gross forward/reverse
enzyme exchange.

At the center, J8-J15 ATP production/consumption are 0.00719648/0.00744403
mM; net -0.00024755 mM. Executed positive net NDPK transfer is 0.00409273
mM and reverse net transfer zero. The joint probe still has negative ATP
balance (-0.00020043 mM). Better ADP residuals did not rescue either target.

GDP and GTP are not observed in the current Bordbar panel. Their locked
J1 states are 1.0 mM each. At the center J15 they are 0.90645679 and
1.11939005 mM, respectively. These are latent predictions, not additional
experimental constraints. GMP is observed and retains its existing guard.
The H ledger denotes ATP+0.5 ADP, not proton balance.

## Post-hoc availability audit

This additional audit reads the completed original trajectories; it adds
no ODE simulation and changes no setting. It is separate from the
preregistered grid. Source and results are sealed in
`output/pgk_ndpk_availability_2026_11_07/`.

The availability threshold stays at 0.001 mM. At center J15, ADP is
0.00000177478 mM. The reaction-consistent gate gives PGK and PK a factor
of 0.00177478, so only 0.177478% of their same-state raw rates executes.
For NDPK, ATP is limiting, with factor 0.08982165 (8.982165%). PGK raw and
executed rates are 0.19653595 and 0.00034880836 in the model rate units.

On J8-J15 the executed/raw absolute-integral fractions are 0.436057% for
PGK, 0.476566% for PK and 18.179055% for NDPK. The gate is active over
all quadrature-weighted time in this period for these three reactions.
These are SAME-STATE raw comparisons. They are not predictions of an
unlimited ODE, and do not prove that removing the gate would rescue ATP.

Three fixed-state rate evaluations show that multiplying both NDPK Vmax
by 0.5/1/2 multiplies raw and executed net NDPK by the same factors without
changing its sign. Algebraically, common scaling cannot change the raw
zero-flux surface at fixed concentrations. It can still change trajectories
and future direction by changing states.

## Verification and next task

105 targeted tests pass. Independent reconstruction verifies 2,016 screen
guard values, 15,820 daily balances, 56,000 quadrature values, 90 native
rate checkpoints and 192,410 cross-tolerance comparisons. Decision and
six-pool/reaction ledgers:
`output/pgk_ndpk_profile_decision_2026_11_07/`. No J46 continuation.

Priority next execution: threshold-sensitivity diagnostic with Vmax, Km,
data, initialization and network FIXED. Compare the current 1e-3 mM gate
with registered positive 1e-4/1e-5/1e-6 mM gates under strict/ultrastrict
solvers. Retain reaction-consistent positivity, exact balances, all dated
outputs and executed-flux checks. Seek numerical convergence as the gate
shrinks, not the threshold giving the best biological fit. Solver rtol/atol
convergence alone does not test this separate regularization parameter.
Do not promote a threshold or resume calibration without that decision.
Keep the unmeasured GDP/GTP initial values visible; inspect their source
contract separately before any latent-pool change.
