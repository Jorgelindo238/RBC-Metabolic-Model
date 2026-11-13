# Corrected-solver sensitivities and Vmax-only continuation

Date: 2026-11-12. Completed and independently verified by Codex.
Protocol: `tasks/fla_corrected_vmax_protocol_2026_11_12.md`.

## Execution

The four-round constrained search is complete: 58 actual search integrations,
plus two full-backend finalist integrations (strict/ultrastrict). All58 search
integrations passed their recorded concentration gate. Forty-two distinct
one-sided perturbation integrations recalculated sensitivities of14 Vmax groups
(17 capacities); the fourth round reused the third-round sensitivity points
because its anchor was unchanged. Four tables contain56 sensitivity columns,
not56 independent perturbation integrations. Two nonlinear updates were accepted
(attempts16 and35); rounds3-4 found no improvement above the inherited threshold.

Same network, initial state, Km, transport, H=0.58, availability threshold1e-3,
grouping and parameter bounds. Dates J4/J8/J11/J15; 84 inherited feasibility
constraints with their original guard reserve and historical reference metrics.
No guard rebasing. Objective: inherited absolute ATP/ADP J15 log minimax.
Radau with bounded Jacobian, max_step0.05; strict1e-8/1e-12 and ultrastrict
1e-9/1e-13, Jacobian minimum perturbations1e-15/1e-16mM respectively.
The opt-in user-engine v2 was not substituted for this qualified historical path.

## Main result

| Metric | Working centre | Selected candidate35 |
| --- | ---: | ---: |
| ATP J15, mM (strict) | 8.982165603e-5 | 8.993285092e-5 |
| ADP J15, mM (strict) | 1.774781522e-6 | 1.778157524e-6 |
| Absolute log-minimax gap | 12.089180124 | 12.087279723 |

Relative J15 gains: ATP +0.123795%, ADP +0.190221%. Absolute targets remain
NOT reached: ATP [0.75707361,1.27058099]mM and ADP
[0.3157978122,0.5854817011]mM. This is not an ATP rescue.

Both full-backend validation profiles pass the inherited reserved guards and
paired state/flux convergence. Ultrastrict J15 ATP8.993285091e-5 and
ADP1.778157524e-6mM. Maximum cross-profile state difference1.428515e-9;
executed daily integral difference2.029920e-10. Recorded finalist concentration
minimum0mM in both profiles, on the inspected accepted/dense/quadrature supports.
No claim of continuous-time positivity outside the inspected supports.

Relative dated adenylate squared-log-error gains against the historical fixed
reference, before -> after this search:

| Day | Working centre gain | Candidate gain |
| --- | ---: | ---: |
| J4 | 6.55366% | 5.83153% |
| J8 | 6.77678% | 6.74098% |
| J11 | 6.63740% | 6.64745% |
| J15 | 6.79751% | 6.82436% |

Thus the late gain is not uniform improvement over the current centre: J4/J8
slightly worsen while staying inside the original contract. Admissibility is
relative to historical engineering guards, not absolute agreement with data.

Largest selected capacity movements relative to the working centre: RKa+1.6661%,
both AK capacities+1.6488%, PK+1.2221%. PGK and both NDPK capacities unchanged
at their existing lower/upper group boundaries. The original paired AK/NDPK
grouping remains in place, so their forward/reverse ratios were not optimized.

## Sensitivities and limitations

At the initial centre, the largest absolute local ADP-J15 concentration
derivatives are PRPP(-2.65464e-6), PGK(-7.67408e-7), SAM(-5.60916e-7) and
NDPK(+3.36562e-7), in mM per unit log group factor. These are local one-sided
responses, not causal biological attribution or identifiable enzyme estimates.
Individual sensitivity probes can fail metabolic guards while still providing
valid numerical derivatives; no such probe is admitted as a candidate.

The search reaches a local plateau. LAC/MAL/XAN guards are near their reserve
limits, while PGK/NDPK sit at box limits. This does not establish global
infeasibility or prove that these alone explain the plateau. Small objective
changes also need derivative-step robustness before strong sensitivity claims.
Source aliases, unknown donor, borrowed geometry and latent-stock/adenylate
observation questions are unchanged. No per-donor or held-out validation.

## Verification and artifacts

- Sealed campaign: `output/corrected_vmax_2026_11_12/`.
- Independent receipt:
  `output/corrected_vmax_verification_2026_11_12/verification.json`.
- Independent verifier checks source/campaign/code hashes, Vmax-only identity,
  original bounds/J1, recorded supports, scores and guards, sensitivity columns,
  reconstructed raw/executed quadrature integrals, daily balances and convergence.
- Verified1,857,599 support points and3,164 daily pool balances. Finalist
  admissible under inherited guards; production_promoted=false.
- Derived exports, outside the sealed campaign:
  `output/corrected_vmax_analysis_2026_11_12/sensitivities.csv`,
  `selected_vmax.csv`, `concentrations_by_day.csv`, with provenance checksums.
-32 targeted tests passed before execution. Full repository suite not run.
  `git diff --check` passed. No agents, J46 replay, active parameter-file update,
  commit or push.

## Decision and next task

Retain candidate35 as an inspectable, admissible comparator only. Do not declare
calibration finished, replace the active working centre or widen bounds based
on the tiny gain. The requested recalculation and optimization are complete.

Next scientific task: use the stored objective/guard Jacobians to attribute
the constrained local plateau (active constraints and group-bound multipliers),
and check the leading sensitivities at a second perturbation size before a
new search. Any proposal to ungroup AK/NDPK, alter bounds or change observation
definitions must be a separately declared hypothesis. User-engine shifted-origin
qualification remains an independent software task, not completed by this pass.
