# Latent ribose stock RIB(0) diagnostic: results

Status: executed and independently verified 2026-11-10 after explicit user
authorization. Closed. Do not overwrite or rerun. The working center
(absolute attempt 76) and the J1 convention RIB = 1 mM are retained.
Nothing promoted; no calibration launched.

Archive: `output/ribose_stock_2026_11_10/`.
Receipt: `output/ribose_stock_decision_2026_11_10/`.
Protocol: `tasks/fla_ribose_stock_protocol_2026_11_10.md`.

## Verdict

Registered classification: `no_supported_effect`. Removing almost all of
the latent ribose stock at fixed kinetics does not prevent the early
ATP/ADP collapse and breaks the original guards. Both arms are numerically
valid and carry `early_only` and `production_compensation`. The response is
monotone (`monotone_response` true). No absolute J15 target is reached.

## What was changed

Only RIB(0). All 55 measured J1 values (110 identity checks), every other
latent state including R5P(0) = 1.6110905 mM, the working-center Vmax,
every Km, network, threshold and guards are unchanged. Four integrations,
no retry.

## Outcome (ultrastrict; strict agrees to the digits shown)

| Quantity | Control RIB 1.0 | Intermediate RIB 0.1 | JA value RIB 0.0023 |
| --- | --- | --- | --- |
| ATP J4 (mM) | 0.02399 | 0.03466 | 0.03536 |
| ADP J4 (mM) | 0.005784 | 0.01071 | 0.01109 |
| AMP J4 (mM) | 2.525 | 2.503 | 2.502 |
| ATP J15 (mM) | 8.982e-5 | 9.208e-5 | 9.221e-5 |
| ADP J15 (mM) | 1.775e-6 | 1.829e-6 | 1.832e-6 |
| Worst-profile absolute gap | 12.08918 | 12.05933 | 12.05754 |
| ATP:lower / ADP:lower | 9.039 / 12.089 | 9.015 / 12.059 | 9.013 / 12.058 |
| Worst dated adenylate ratio | 0.9345 | 0.9274 | 0.9271 |
| Original reserved guards | pass | FAIL | FAIL |

ATP at J15 rises 2.7% and ADP 3.2% in the JA arm; the gap moves by 0.032
log units of 12.09. Guards failed by the JA arm (control value in
brackets): F6P J4 0.641 (-0.002), B23PG MSE 0.364 (-0.049), F6P J11 0.315,
PEP J15 0.168, PEP J8 0.161, G6P J8 0.151, G6P MSE 0.142, F6P MSE 0.099,
PEP J4 0.092, G6P J4 0.067, plus GLN, GMP, PEP MSE and EINO J8. The
intermediate arm fails the same set.

## Executed J1-J4 ledger (mM)

| Quantity | Control | RIB 0.1 | RIB 0.0023 |
| --- | --- | --- | --- |
| RKa | 1.0000 | 0.1000 | 0.0023 |
| Gross ATP consumption | 5.6560 | 5.0411 | 4.9585 |
| Gross ATP production | 4.7470 | 4.1428 | 4.0609 |
| Net ATP | -0.9090 | -0.8983 | -0.8976 |
| PGK | 2.7110 | 2.3567 | 2.2926 |
| PK | 0.9152 | 0.7950 | 0.7844 |
| AK (2 ADP -> ATP + AMP) | 1.1208 | 0.9911 | 0.9840 |
| PRPPASe | 0.7679 | 0.8588 | 0.8634 |
| NDPK | 1.9164 | 1.9605 | 1.9625 |
| HGPRT1 | 1.3201 | 1.3300 | 1.3304 |
| E_A = 2 ATP + ADP at J4 | 0.0538 | 0.0800 | 0.0818 |

Registered flags, JA arm: RKa demand falls by 0.998 mM, gross consumption
by 0.697 (so `demand_compensation` false: 0.697 >= 0.5 x 0.998), gross
production by 0.686 (`production_compensation` TRUE: 0.686 >= 0.5 x 0.697).
Production fell by 98% of the consumption reduction. PRPPASe and NDPK rise
slightly. R5P still accumulates (1.61 -> 5.34 mM at J15).

## Reading across the two latent diagnostics (descriptive)

Removing about 1 mM of early ATP demand by two unrelated routes (guanylate
charging, ribokinase) gives the same picture: gross consumption falls by
about 0.70-0.72 mM, gross production falls by about 0.69-0.72 mM, the net
J1-J4 ATP balance stays near -0.90 mM, and AMP reaches about 2.50 mM at J4
in every trajectory. In this model the early collapse is not explained by
the size of either latent stock.

## Observation for the next decision (post hoc, not a registered result)

Computed from the coded law and Sheet1 values only, no integration. The
coded adenylate kinase law is
`VAK = Vf*mm(ADP,K_ADP) - Vr*mm(AMP,K_AMP)*mm(ATP,K_ATP)`
(`src/equadiff_brodbar.py`, line 1524) with Vf/Vr = 10.766 at the working
center. Evaluated at the OBSERVED adenylate values:

| Date | Observed ATP*AMP/ADP^2 | Observed energy charge | Vf/Vr that would zero the coded AK | Coded net AK (mM/day) |
| --- | --- | --- | --- | --- |
| J1 | 0.504 | 0.534 | 0.667 | +1.490 |
| J4 | 0.505 | 0.600 | 0.673 | +1.456 |
| J8 | 0.549 | 0.685 | 0.659 | +1.383 |
| J11 | 0.954 | 0.736 | 0.698 | +1.203 |
| J15 | 1.289 | 0.719 | 0.716 | +1.053 |

At every observed date the coded law would run 2 ADP -> ATP + AMP at more
than 1 mM/day, and the ratio that would balance it is nearly constant
(0.66-0.72) and about 16 times lower than the 10.77 used. In every Vmax
campaign so far vmax_VAK and vmax_VAK_rev share one factor, so this ratio
could never move; the same holds for NDPK. Earlier work found forward AK to
be one of the strongest levers (`fla_progress_log.md`, AK x0.5 factorial of
2026-11-04) and rejected it on other-pool guards.

Caveats that keep this a hypothesis: Sheet1 totals are not proven to be
free enzyme substrate (the observation contract is unresolved); the coded
law is a difference of saturating terms without a Haldane constraint, so
"balance" is a model property, not a thermodynamic statement; the two
diagnostics above show that this network compensates, so an AK change may
also be absorbed; and measured J1 adenylates must stay untouched.

## Verification

Independent verifier passed on its first execution: 110 measured-J1
identity checks, only RIB(0) changed and equal to the registered values, 4
replays re-verified (6,328/6,328 daily balances, 22,400 quadrature values,
36 native/compiled checkpoints), 336 guard values rescored, J1-J4 integrals
recomputed by a separate code path, classification, monotonicity and both
compensation flags re-derived. 17 targeted tests passed immediately before
launch. Full repository suite not run.

## Next step: a decision for the user, nothing launched

1. Adenylate kinase forward/reverse ratio diagnostic: Vmax-only, Km and all
   J1 unchanged, but with vmax_VAK and vmax_VAK_rev UNGROUPED, which is a
   change of the registered search design and needs explicit approval.
   Fixed-kinetics arms first (for example the ratio that balances the coded
   law at observed J1), same guards, production-side criteria registered.
2. Read-only structural review of AK, NDPK and the purine branch against
   RBC-GEM and the rate-law forms.
3. Return to the observation contract: what the Sheet1 ATP/ADP/AMP numbers
   measure (J1 energy charge 0.53 with ADP above ATP).
