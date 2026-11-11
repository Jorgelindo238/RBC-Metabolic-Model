# Corrected-engine Vmax-only absolute ATP/ADP search: results

Status: executed, audited and independently verified 2026-11-10. Closed.
Do not overwrite or rerun this campaign. No production promotion.

Campaign: `output/vmax_corrected_search_2026_11_10/`.
Receipt: `output/vmax_corrected_search_decision_2026_11_10/`.
Protocol: `tasks/fla_vmax_corrected_search_protocol_2026_11_10.md`.

## Verdict

Classification `no_improvement`, with the registered futility flag
`original_box_local_search_exhausted`. The working center (absolute attempt
76) is retained unchanged. Absolute J15 ATP/ADP targets are not reached.

The search is numerically clean and converged to a guard-limited local
stationary point 0.0019 log units from the center. Local Vmax-only search
in the original boxes is exhausted. This is not a global optimum claim and
not evidence of global infeasibility.

## Scope kept

Same 14 groups/17 Vmax, original boxes, every Km, exact J1 and latents, 770
observation cells, network gem_corrected -> redox_gssg_abc, hematocrit
0.58, availability threshold 1e-3 mM, rejection tolerance -1e-10 mM, and
the old historical full control as guard reference. SciPy 1.17.1, Radau,
bounded fine Jacobian, strict profile inside the search. No clipping,
retry, bound expansion, J46 run or default change.

## Step 1: Controls

Both controls passed. The fixed reference and the working center reproduce
the sealed strict/joint requalification controls bitwise at J4/J8/J11/J15
for all 55 channels. The center still passes the original reserved guards.

## Steps 2-3: Sensitivities and rounds

59 actual integrations of the 80 allowed; 0 numerical rejections (the
2026-11-07 search had 5 of 80). All four rounds had 14/14 valid derivatives
(13/14 in three rounds of the old search). No fit-based retry.

| Round | Radius | Anchor | LP-predicted gap | Accepted | Gap after |
| --- | --- | --- | --- | --- | --- |
| 1 | 0.20 | 2 (center) | 12.08736 | 17 | 12.087333 |
| 2 | 0.25 | 17 | 12.08728 | 36 | 12.087280 |
| 3 | 0.30 | 36 | 12.08728 | none | 12.087280 |
| 4 | 0.15 | 36 | 12.08728 | none (cached) | 12.087280 |

From round 2 the linearized problem itself predicts no further gain at any
allowed radius: the step is limited by guards, not by the radius. Round 4
reused cached evaluations and cost no integration. All fifteen backtracking
points passed the reserved guards; none failed a guard.

Guards inside the LP reserve: at the center EINO J4 (zero band), XAN (MSE)
and PEP J15; at the final anchor LAC and XAN (MSE), PEP J8, G6P J11, F6P J4
and AMP J4.

Local sensitivities of the two binding sides at the final anchor, per unit
log factor (positive means lowering the capacity lowers the gap). Values
are stable across the three anchors to about 0.002.

| Group | d(ADP:lower) | d(ATP:lower) | Position in box |
| --- | --- | --- | --- |
| PRPP | +1.504 | +1.145 | 0.966 in [0.1, 2.0] |
| PGK | +0.431 | -0.065 | on lower bound 0.5 |
| SAM | +0.317 | +0.236 | 0.749 in [0.1, 2.0] |
| NDPK | -0.189 | +0.048 | on upper bound 2.0 |
| LDH | +0.089 | -0.073 | 1.046 in [0.25, 4.0] |
| PEPase | +0.076 | +0.072 | 0.917 in [0.1, 3.0] |
| PK | -0.076 | -0.072 | 1.249 in [0.25, 4.0] |
| others | below 0.07 in magnitude | | |

PRPPASe is by far the strongest local lever on both pools, followed by PGK
(ADP only, already on its bound) and VSAM. These are finite differences at
one point, not identifiability results.

Diagnostic extrapolation only: pushing every coordinate to its most
favourable box edge with these linear slopes, and ignoring every guard,
would change ADP:lower by about -4.65 and ATP:lower by about -3.87 log
units, against required 12.09 and 9.04. PRPP alone carries -3.41 and -2.60
of that. The model is nonlinear over such distances, so this is not a
prediction; it indicates that the remaining gap is unlikely to be a matter
of Vmax values inside these boxes.

## Step 4: Audit of the selected point

Selected: attempt 55 (round 3 backtrack), the lowest reserve-feasible gap.
It was not accepted as a step because it improves on attempt 36 by less
than the registered 1e-6. Two new integrations, both numerically valid;
paired strict/ultrastrict comparison passes.

| Quantity | Working center | Selected attempt 55 |
| --- | --- | --- |
| ATP J15, ultrastrict, mM | 8.98216559e-5 | 8.99328677e-5 |
| ADP J15, ultrastrict, mM | 1.77478152e-6 | 1.77815802e-6 |
| Worst-profile absolute gap | 12.08918013 | 12.08727944 |
| ATP:lower / ADP:lower gap | 9.039 / 12.089 | 9.038 / 12.087 |
| Worst dated adenylate ratio | 0.93446340 | 0.94168527 |
| Dated ratios J4/J8/J11/J15 | | 0.94169 / 0.93259 / 0.93353 / 0.93176 |

ATP rises 0.124% and ADP 0.190%: both in the right direction, both
negligible against four to five orders of magnitude. The gap improves by
0.0019 but the worst dated ratio worsens (J4), so registered rule 4 does
not make it a new center. Factor changes versus the center are below 2%:
PK 1.234 -> 1.249, AK 1.098 -> 1.116, RKa 1.414 -> 1.438; PGK and NDPK stay
on their bounds.

All saved supports are finite and nonnegative; global minimum 0 mM. This is
support-based evidence, not proof of continuous-time positivity.

## Independent verification

`verify_vmax_corrected_search.py` passed on its first execution: 59 search
records, 0 quarantined, 5,124 reconstructed guard values, 4,928 Jacobian
entries, 4 LP witnesses re-solved, acceptance sequence, selection and
classification reproduced. For the two audit replays: 3,164/3,164 daily
executed balances, 11,200 quadrature values, 18 native/compiled projection
checkpoints. Guard caps not recomputed; no bound, Km or J1 change.

27 targeted tests passed immediately before launch (66 with related
suites). The full repository suite was not run. The search loop, audit
stage and round verifier ran for the first time in this campaign.

Search attempts keep sealed solver diagnostics and fit-date states, not
full trajectories; only the audited point has full flux evidence.

## What this does and does not establish

Established: with a clean engine and complete derivatives, the previous
"best" center is essentially a guard-limited local optimum of this problem;
the five old numerical rejects were not hiding a better direction.

Not established: global infeasibility, a causal mechanism for the ATP/ADP
collapse, any threshold plateau, or biological validation.

## Next step: a decision for the user, nothing launched

Per the registered futility rule, no further same-box Vmax-only search.
Reversible alternatives, each needing its own registered protocol:

1. PRPPASe/ATP-demand diagnosis J8-J15: it is the dominant lever and
   earlier pilots found PRPP and NDPK demand exceeding production. Executed
   ATP-consumer attribution at the center, before touching any box.
2. Registered widening of selected boxes (PRPP lower, PGK lower, NDPK
   upper) as an explicit out-of-box diagnostic with the same guards.
3. Latent GDP/GTP initialization contract (both locked at 1 mM at J1),
   which fixes the NDPK zero-flux surface.
4. Availability-gate formulation, already shown not to restore energy by
   threshold lowering alone.

Option 1 is the cheapest and reuses existing audit code; it changes no
parameter.
