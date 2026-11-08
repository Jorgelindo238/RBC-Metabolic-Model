# Absolute J15 ATP/ADP target: guarded Vmax feasibility screen

## Decision

The absolute ATP/ADP target was NOT reached. The selected candidate passes
the unchanged dated non-regression contract and original-rate numerical
checks at both tolerances. These are separate results. No constants are
promoted to production and no global infeasibility is established.

This is a successor to `tasks/fla_temporal_vmax_results_2026_11_04.md`.
The fixed comparator remains the half-step reference in the same opt-in
`redox_gssg_abc` network, not the previous fitted vector. That vector is
the new search start. All Km, other parameters, exact Sheet1 J1 and latent
states, OPLAH, geometry, transport and positivity settings remain locked.
No source rescaling, ATP injection, resets or teacher forcing was used.

## Registered absolute target

The J15 nominal source observations define the targets. The two-sided
interval is nominal plus/minus the inherited working band: 5% of the
J1/J4/J8/J11/J15 median plus 20% of the J15 observation. This is an
engineering feasibility interval, not an assay SD or a confidence interval.
It does not resolve the distinction between measured ATP and free substrate.

| Pool | J15 nominal (mM) | Target interval (mM) | Previous candidate (mM) | New candidate (mM) |
| --- | ---: | ---: | ---: | ---: |
| ATP | 1.01382730 | 0.75707361 to 1.27058099 | 0.0000875098 | 0.0000898217 |
| ADP | 0.45063976 | 0.31579781 to 0.58548170 | 0.00000123266 | 0.00000177478 |

Values above are original-rate ultrastrict replays. Both targets fail by
orders of magnitude; an improved reference-relative error is not rescue.

Minimize the largest of `log(lower/prediction)` and `log(prediction/upper)`
across ATP and ADP at J15. An absolute score at or below zero means both
intervals are reached. The selected original-rate score is 12.08918,
dominated by the ADP lower bound. The previous candidate score in the fit
integrator was 12.45368; the new fit score is 12.08916, still positive.

All 16 dated PEP/G6P/F6P/AMP caps, nonadenylate trajectory guards, zero-band
guards, adenylate log guards and minimum 0.1% improvement at EACH of
J4/J8/J11/J15 remain eliminatory. The same baseline guard reserve is used.
These dates were fitted and historically exposed, not held-out validation.

## Executed search

At most 80 attempts were allowed, matching the previous budget. The control,
previous candidate, two deterministic probes toward the old J4 direction,
four finite-difference rounds and real ODE backtracking consumed all 80.
There were 75 valid integrations and five numerical rejects for negative or
nonfinite checked states; no clipping or pseudocount rescued these trials.
47 sampled rows satisfy the full reserved guard contract. Trial 76 is the
lowest absolute score among those rows. Accepted rounds: 20, 39, 58, 76.

The first full step (trial 19) improved the target score but failed PEP
J8/J15, G6P J11, F6P J8, EINO J4, SER and XAN guards. Trial 38 failed
PEP J4/J15. Trial 57 passed raw caps but failed the retained safety reserve.
The two longer probes toward the old J4 candidate also failed many guards.

The selected PGK factor reaches its lower bound 0.5 and the common
forward/reverse NDPK factor reaches its upper bound 2.0. Absolute PGK Vmax
is 19.58842609 versus the fixed 39.17685219; NDPK forward/reverse Vmax are
17.60331255/3.35089918 versus 8.80165627/1.67544959. These are tested
capacities, not identified biological enzyme activities.

## Original-rate check and energy budget

Four new free J1-J15 replays (control/candidate, strict/ultrastrict) pass
all numerical checks. Cross-tolerance comparisons pass 76,964/76,964.
All 16 critical caps pass at each tolerance. Minimum checked concentration
is zero in all four replays, within the fixed numerical contract; this is
not a proof of positivity at every unobserved continuous time.

Candidate adenylate mean squared log-error reductions relative to the fixed
control are 6.554%, 6.777%, 6.637%, 6.797% at J4/J8/J11/J15. At J15, AMP
remains approximately 1.8122 mM versus 0.25814 nominal. The relative guards
therefore prevent regressions without establishing absolute adequacy.

Executed J8-J15 ATP production is 0.00719648 mM and consumption is
0.00744403 mM: net -0.00024755 mM. Both sides increase versus the previous
candidate and the late balance remains negative. The largest signed
consumer is NDPK (-0.00409273 mM), followed by PFK (-0.00145977 mM) and
GSSG export (-0.00103718 mM). Do not equate a better ADP residual or higher
ATP production with lower energy demand. The accompanying H ledger is
ATP + 0.5 ADP, not a proton or pH balance.

## Reproducibility and next decision

- Protocol: `tasks/fla_absolute_vmax_protocol_2026_11_07.md`.
- Frozen campaign: `output/absolute_vmax_2026_11_07/`.
- Decision: `output/absolute_vmax_decision_2026_11_07/absolute_decision.json`.
- Target values: `output/absolute_vmax_decision_2026_11_07/absolute_J15_targets.csv`.
- Tested capacities and source/QA closeout:
  `output/absolute_vmax_validation_2026_11_07/`.

Independent reconstruction checks 75 fit scores, 6,300 full guard values,
32 original critical caps, 6,328 balances, 22,400 quadratures and 36 native
rate checkpoints. 97 targeted tests pass. No J46 simulation was launched.

Before a larger search, distinguish active Vmax bounds from metabolic
constraints and ATP-to-other-nucleotide redistribution. A controlled
feasibility profile of PGK/NDPK and the ATP/ADP/GDP/GTP executed balances
would address the present limiting behavior. Do not simply widen NDPK or
declare the absolute target impossible from this local screen.
