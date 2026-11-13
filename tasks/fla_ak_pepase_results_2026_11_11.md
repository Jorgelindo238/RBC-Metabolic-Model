# AK ratio x PEP phosphatase capacity diagnostic: results

Closed on 2026-11-11. Protocol `tasks/fla_ak_pepase_protocol_2026_11_11.md`,
config `config/fla_ak_pepase_2026_11_11.json`. Launch authorized by the
user ("Oui, lance"). Archive `output/ak_pepase_2026_11_11/` and receipt
`output/ak_pepase_decision_2026_11_11/` are sealed: do not overwrite or
rerun.

## Registered outcome

Class: `no_supported_effect`. `monotone_response`: true, in the direction
opposite to the hypothesis (the gap rises as the phosphatase is lowered).

Six J1-J15 integrations (three arms, strict and ultrastrict), all
numerically valid, all paired comparisons pass, strict and ultrastrict
scores identical to the printed digits. No retry.

The registered hypothesis is REFUTED. With the balanced AK ratio, lowering
VPEP_PASE to the floor of its box raises the PK share of PEP outflow as
expected, but J15 ATP and ADP end lower than in the balanced-AK arm alone
(`beyond_reference` false), and the PEP guards fail at all four dates.

Working center, grouped search design and J1 conventions retained. Nothing
promoted, no calibration launched, no J46 run.

## Scores

| Trajectory | AK Vf/Vr | VPEP_PASE | Worst gap | ATP J4 | ATP J15 | ADP J15 | Guards |
| --- | --- | --- | --- | --- | --- | --- | --- |
| control (sealed) | 10.766 | 7.660 | 12.0892 | 0.0240 | 8.98e-5 | 1.77e-6 | pass |
| ak_only (sealed) | 0.667 | 7.660 | 7.5002 | 0.1133 | 4.44e-3 | 1.75e-4 | 23 fail |
| pepase_floor_only | 10.766 | 0.836 | 11.9016 | 0.1124 | 1.07e-4 | 2.14e-6 | 17 fail |
| ak_balanced_pepase_intermediate | 0.667 | 2.530 | 10.0561 | 0.1781 | 4.19e-4 | 1.36e-5 | 22 fail |
| ak_balanced_pepase_floor (hypothesis) | 0.667 | 0.836 | 10.6583 | 0.2855 | 2.69e-4 | 7.42e-6 | 21 fail |

`absolute_J15_targets_reached` false everywhere. Failed guards of the
hypothesis arm: MSE EGSH, EINO, PEP, F6P, G6P, GLN, GLU, GMP, SAH; zero
EINO J8; point PEP at J4/J8/J11/J15, G6P at J4/J8/J11/J15, F6P at
J4/J8/J11.

## Registered flags

| Arm | Reference | `improves` | `beyond_reference` | PK share J1-J4 | PK share J1-J15 | `pk_share_raised` | `pep_guard_failed` | `net_ATP_change_mM` | `early_only` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pepase_floor_only | control | false | true | 0.669 | 0.291 | true | true | +0.088 | true |
| ak_balanced_pepase_intermediate | ak_only | false | false | 0.610 | 0.435 | true | true | +0.154 | true |
| ak_balanced_pepase_floor | ak_only | false | false | 0.814 | 0.560 | true | true | +0.262 | true |

PK shares of the sealed trajectories, same code: control 0.254 / 0.106,
ak_only 0.361 / 0.268. `beyond_reference` true for `pepase_floor_only`
means only that its gap (11.90) is below the control's (12.09) with J15 ATP
and ADP not lower; it fails 17 guards and is not an improvement.

## Levels (ultrastrict, mM)

| Pool | Trajectory | J1 | J4 | J8 | J11 | J15 |
| --- | --- | --- | --- | --- | --- | --- |
| ATP | ak_only | 0.933 | 0.113 | 0.0744 | 0.0432 | 0.0044 |
| ATP | hypothesis | 0.933 | 0.286 | 0.0864 | 0.0044 | 2.7e-4 |
| ADP | ak_only | 1.169 | 0.977 | 0.355 | 0.0830 | 1.7e-4 |
| ADP | hypothesis | 1.169 | 0.565 | 0.0067 | 1.5e-4 | 7.4e-6 |
| AMP | ak_only | 0.739 | 1.481 | 1.817 | 1.895 | 1.753 |
| AMP | hypothesis | 0.739 | 1.693 | 2.085 | 1.961 | 1.722 |
| GTP | ak_only | 1.000 | 1.392 | 1.386 | 1.695 | 1.940 |
| GTP | hypothesis | 1.000 | 1.881 | 2.033 | 1.977 | 1.747 |
| E_A = 2 ATP + ADP | ak_only | 3.035 | 1.203 | 0.504 | 0.170 | 0.0090 |
| E_A = 2 ATP + ADP | hypothesis | 3.035 | 1.136 | 0.180 | 0.0090 | 5.5e-4 |
| PEP | observed | 0.220 | 0.158 | 0.094 | 0.069 | 0.052 |
| PEP | ak_only | 0.220 | 0.092 | 0.091 | 0.062 | 0.034 |
| PEP | hypothesis | 0.220 | 0.256 | 0.665 | 0.920 | 0.773 |
| PEP | pepase_floor_only | 0.220 | 0.734 | 1.773 | 1.643 | 1.288 |

Full tables: `output/ak_pepase_2026_11_11/levels_by_day.csv`.

## Executed integrals (ultrastrict, mM), hypothesis arm against ak_only

| Quantity | J1-J4 ak_only | J1-J4 hypothesis | J4-J8 ak_only | J4-J8 hypothesis | J8-J15 ak_only | J8-J15 hypothesis |
| --- | --- | --- | --- | --- | --- | --- |
| PK | 1.320 | 2.838 | 1.027 | 2.338 | 0.575 | 0.245 |
| VPEP_PASE | 2.337 | 0.651 | 2.735 | 0.973 | 2.927 | 2.627 |
| PGK | 2.989 | 2.955 | 0.526 | 0.436 | 1.492 | 0.324 |
| GAPDH | 0.681 | 0.677 | 0.652 | 0.609 | 2.185 | 2.198 |
| Gross ATP production | 4.414 | 5.809 | 1.777 | 2.803 | 2.150 | 0.570 |
| Gross ATP consumption | 5.233 | 6.456 | 1.816 | 3.002 | 2.220 | 0.656 |
| NDPK | 1.450 | 1.964 | 0.653 | 1.174 | 1.196 | 0.250 |
| PRPPASe | 0.757 | 1.040 | 0.350 | 0.613 | 0.281 | 0.094 |
| ADSS | 1.058 | 1.082 | 0.659 | 1.022 | 0.642 | 0.536 |
| HK | 0.239 | 0.266 | 0.235 | 0.291 | 0.250 | 0.090 |
| AK | 0.074 | -0.038 | 0.224 | -0.007 | 0.075 | -0.025 |

Details: `executed_ledger.csv`.

## Reading (descriptive, not causal, not a registered result)

- The phosphatase does divert PEP from PK: at the floor PK doubles on
  J1-J8 (5.18 against 2.35 mM) and gross ATP production rises by 2.4 mM.
- Consumption rises by the same amount (+1.22 on J1-J4, +1.19 on J4-J8).
  The extra ATP goes to NDPK (+1.04 over J1-J8; GTP reaches 2.03 mM at J8
  and ADSS rises) and to PRPPASe (+0.55, ATP -> AMP). This is the fourth
  fixed-kinetics diagnostic in which production and consumption move
  together.
- Because PK consumes ADP and PRPPASe sends adenylate to AMP, which the
  balanced AK no longer returns, ADP is exhausted sooner: 0.0067 mM at J8
  against 0.355 in ak_only. E_A falls faster after J4 and J15 ATP ends 16
  times lower than in ak_only.
- B13PG supply is unchanged (GAPDH 0.68 on J1-J4 in every trajectory), as
  registered in the limits.
- PEP rises to 3 to 15 times the observation: the phosphatase is what
  holds modelled PEP near the data. The response is graded: the
  intermediate capacity gives intermediate PEP, PK share and gap.
- Lowering the phosphatase alone (AK at center) leaves J15 essentially at
  the control (gap 11.90) with PEP at 1.3-1.8 mM.

Two in-box capacity changes that each raise an ATP source (AK ratio, PK
share) therefore do not move the J15 state toward its window; the second
one makes it worse. In these trajectories ATP is not limited by the PK/PEP
phosphatase split.

## Post hoc observation (not registered, sealed states only)

Read after the results from the sealed trajectories and Sheet1, in model
concentration units without volume conversion:

| Quantity | Observed | control | ak_only | hypothesis |
| --- | --- | --- | --- | --- |
| Intracellular GLC J1 -> J15 | 1.12 -> 1.18 | 1.12 -> 3.74 | 1.12 -> 3.34 | 1.12 -> 3.42 |
| EGLC J1 -> J15 | 25.34 -> 20.03 | 25.34 -> 21.39 | 25.34 -> 21.29 | 25.34 -> 21.28 |
| ELAC J1 -> J15 | 3.61 -> 16.20 | 3.61 -> 13.01 | 3.61 -> 13.13 | 3.61 -> 13.13 |
| LAC J1 -> J15 | 0.95 -> 4.13 | 0.95 -> 0.87 | 0.95 -> 0.89 | 0.95 -> 0.88 |
| Executed glucose import VEGLC, J1-J15 | - | 2.86 | 2.94 | 2.94 |
| Executed HK, J1-J15 | - | 0.25 | 0.72 | 0.65 |
| Executed LDH, J1-J15 | - | 6.72 | 6.82 | 6.82 |

In every trajectory the model imports about 2.9 mM of glucose and
phosphorylates 0.25 to 0.72 of it; intracellular glucose triples while the
observation is flat. vmax_VHK is 0.098 mM/day at the working center (box
[0.25, 4.0] on base 0.1). Lactate formed by LDH (6.7-6.8 mM) is therefore
mostly carbon from the initial stocks (B13PG, B23PG, GA3P, pentoses), not
from glucose. Lower glycolysis and its ATP run on stock liquidation.

This is a description of sealed trajectories, not a diagnosis: earlier
calibrations lowered HK/PFK "investment" on purpose, a higher HK flux costs
ATP first, and intracellular/extracellular volumes differ.

## Verification

Independent verifier passed on its first execution: 55 measured-J1 identity
checks, 3 arm vectors (sealed AK arm at the balancing ratio re-derived from
the native law, only the three registered capacities changed, rules and box
respected, no Km changed), 6 replays re-verified (9,492/9,492 daily
balances, 33,600 quadrature values, 54 native/compiled checkpoints, 0
quarantined), 504 guard values rescored, both sealed trajectories rescored,
PK, phosphatase and gross ATP integrals recomputed by a separate code path,
classification, monotonicity and flags re-derived. 19 targeted tests passed
immediately before launch. Full repository suite not run.

## Limits

As registered: two capacities at two levels plus one point; the floor is a
box bound, not a physiological value; PK capacity, km_PEP, B13PG supply and
the duplicated B13PG stock unchanged; the balanced AK ratio rests on the
unresolved observation contract. The arms fail the original guards and are
not admissible model states.

## Next step: a decision for the user, nothing launched

1. Read-only carbon and glucose budget on the sealed trajectories against
   observed EGLC, GLC, ELAC and LAC, with explicit compartment volumes:
   how much of the modelled lactate and ATP comes from glucose and how much
   from initial stocks, date by date. No integration.
2. Read-only structural review of the ATP-driven sinks that absorb every
   extra ATP here: NDPK with ADSS and ADESUC accumulation, and PRPPASe with
   its R5P/PRPP latent stocks, against RBC-GEM.
3. Registered Vmax-only search with AK ungrouped. Today's two diagnostics
   give no in-box evidence that it would reach the J15 windows.
4. Observation contract for Sheet1 ATP/ADP/AMP.
