# Adenylate kinase forward/reverse ratio diagnostic: results

Closed on 2026-11-11. Protocol `tasks/fla_ak_ratio_protocol_2026_11_11.md`,
config `config/fla_ak_ratio_2026_11_11.json`. Launch authorized by the user
("Oui, lance"). Archive `output/ak_ratio_2026_11_11/` and receipt
`output/ak_ratio_decision_2026_11_11/` are sealed: do not overwrite or rerun.

## Registered outcome

Class: `no_supported_effect`. `monotone_response`: true.

Six J1-J15 integrations (three arms, strict and ultrastrict), all
numerically valid, all paired comparisons pass, strict and ultrastrict
scores identical to the printed digits. No retry. The hypothesis arm lowers
the absolute gap but fails the original reserved guards, so it does not
`improve` in the registered sense; the capacity arm fails the same way.

Working center, grouped search design and J1 conventions retained. Nothing
promoted, no calibration launched, no J46 run.

## Scores

| Arm | Vf/Vr | Worst gap | ATP J4 | ATP J15 | ADP J15 | Guards |
| --- | --- | --- | --- | --- | --- | --- |
| control (sealed) | 10.766 | 12.0892 | 0.02399 | 8.98e-5 | 1.77e-6 | pass |
| intermediate_ratio | 2.680 | 11.4403 | 0.11105 | 1.48e-4 | 3.40e-6 | 18 fail |
| balanced_forward_lowered | 0.667 | 7.5002 | 0.11326 | 4.44e-3 | 1.75e-4 | 23 fail |
| balanced_reverse_upper_bound | 0.667 | 8.3943 | 0.11809 | 1.59e-3 | 7.14e-5 | 22 fail |

J15 window for ATP is [0.757, 1.271] mM: `absolute_J15_targets_reached`
false for every arm. ATP at J15 is 49 times the control in the hypothesis
arm and still about 170 times below the window.

Failed guards, hypothesis arm: MSE B23PG, EINO, PEP, F6P, G6P, GLN, GLU,
INO, P3G, PYR; zero EINO J4/J8; point PEP J4/J8/J15, G6P and F6P at
J4/J8/J11/J15. Capacity arm: same list without point PEP J8. Intermediate
arm: zero EINO J8; MSE PEP, F6P, G6P, GLN, GLU, GMP, PYR; point PEP at all
four dates, G6P and F6P at J4/J8/J11.

## Registered flags (ultrastrict, J1-J4, reductions versus control)

| Arm | dAK | dC | dP | `ak_flux_reduced` | `consumption_compensation` | `net_ATP_change_mM` | `early_only` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| balanced_forward_lowered | 1.0467 | 0.4227 | 0.3335 | true | false (0.4227 < 0.5 x 1.0467) | +0.0893 | true |
| balanced_reverse_upper_bound | 0.9876 | 0.3360 | 0.2419 | true | false | +0.0941 | true |
| intermediate_ratio | 0.4406 | -0.0314 | -0.1184 | true | false | +0.0871 | true |

## Levels (ultrastrict, mM)

| Pool | Arm | J1 | J4 | J8 | J11 | J15 |
| --- | --- | --- | --- | --- | --- | --- |
| ATP | control | 0.933 | 0.0240 | 3.4e-4 | 1.5e-4 | 9.0e-5 |
| ATP | hypothesis | 0.933 | 0.1133 | 0.0744 | 0.0432 | 0.0044 |
| ADP | control | 1.169 | 0.0058 | 1.1e-5 | 3.7e-6 | 1.8e-6 |
| ADP | hypothesis | 1.169 | 0.9766 | 0.3549 | 0.0830 | 1.7e-4 |
| AMP | control | 0.739 | 2.525 | 2.259 | 2.057 | 1.812 |
| AMP | hypothesis | 0.739 | 1.481 | 1.817 | 1.895 | 1.753 |
| E_A = 2 ATP + ADP | control | 3.035 | 0.054 | 6.9e-4 | 3.1e-4 | 1.8e-4 |
| E_A = 2 ATP + ADP | hypothesis | 3.035 | 1.203 | 0.504 | 0.170 | 0.0090 |
| B23PG | control | 3.584 | 3.358 | 1.798 | 1.392 | 1.065 |
| B23PG | hypothesis | 3.584 | 3.102 | 1.252 | 0.465 | 0.314 |
| G6P | control | 0.080 | 0.244 | 0.148 | 0.093 | 0.050 |
| G6P | hypothesis | 0.080 | 0.257 | 0.319 | 0.322 | 0.252 |
| F6P | control | 0.069 | 0.081 | 0.092 | 0.125 | 0.152 |
| F6P | hypothesis | 0.069 | 0.059 | 0.012 | 0.014 | 0.031 |

Full tables for the 13 pools, both stocks and all arms:
`output/ak_ratio_2026_11_11/levels_by_day.csv`.

## Executed integrals J1-J4 (ultrastrict, mM)

| Quantity | Control | Intermediate | Hypothesis | Capacity |
| --- | --- | --- | --- | --- |
| AK (2 ADP -> ATP + AMP) | 1.1208 | 0.6802 | 0.0742 | 0.1332 |
| Gross ATP production | 4.7470 | 4.8654 | 4.4136 | 4.5051 |
| Gross ATP consumption | 5.6560 | 5.6874 | 5.2333 | 5.3200 |
| Net ATP | -0.9090 | -0.8220 | -0.8197 | -0.8149 |
| PGK | 2.7110 | 2.9380 | 2.9886 | 2.9960 |
| PK | 0.9152 | 1.2471 | 1.3199 | 1.3220 |
| NDPK | 1.9164 | 1.7814 | 1.4499 | 1.5002 |
| ADSS | 1.0821 | 1.0745 | 1.0578 | 1.0591 |
| PRPPASe | 0.7679 | 0.8194 | 0.7569 | 0.7618 |
| RKa | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| AMPD1 | 0.3741 | 0.3658 | 0.3572 | 0.3571 |

Later windows (hypothesis versus control): gross ATP production J4-J8
1.777 versus 0.325, J8-J15 2.150 versus 0.007; PGK J8-J15 1.492 versus
0.007. Details in `executed_ledger.csv`.

## Reading (descriptive, not causal, not a registered result)

- The ratio changes the adenylate partition strongly. With AK balanced at
  J1, ADP at J4 is 0.977 mM instead of 0.006 and E_A at J4 is 1.20 mM
  instead of 0.05. This is the largest change of the absolute gap in any
  fixed-kinetics diagnostic so far (12.09 to 7.50), where the two latent
  stock diagnostics moved it by about 0.03.
- ATP itself still falls from 0.933 to 0.113 mM by J4 in every arm, and the
  J1-J4 net ATP balance barely moves (-0.909 to -0.820). Removing 1.05 mM of
  AK production lowered consumption by 0.42 and production by 0.33; PGK and
  PK rose, NDPK fell by 0.47. The early ATP deficit is therefore not caused
  by the AK ratio alone.
- The collapse is delayed, not avoided: ADP is 0.355 at J8, 0.083 at J11 and
  1.7e-4 at J15. Glycolytic ATP production continues to J15 instead of
  stopping after J4.
- Ratio versus capacity: the capacity arm (same ratio, both capacities 1.82
  times higher) gives the same J4 picture and a smaller late gain (gap 8.39
  versus 7.50). The early effect follows the ratio; the registered class
  does not depend on the absolute capacity.
- The response is monotone across the three ratios, but the intermediate
  ratio 2.68 gives almost no J15 gain (gap 11.44): most of the effect lies
  between 2.68 and 0.67.
- The guards that fail are the same family that rejected the common AK x0.5
  factor on 2026-11-04 (G6P, F6P, PEP), plus B23PG, which is depleted faster
  (0.31 versus 1.07 mM at J15) while G6P accumulates and F6P is depleted.
  All other Vmax were held at a center tuned with the ratio at 10.77.

Limits as registered: three points, one state for the balancing ratio, no
Haldane constraint, unresolved observation contract, hypothesis arm near the
lower bound and capacity arm on the upper bound.

## Verification

Independent verifier passed on its first execution: 55 measured-J1 identity
checks, 3 arm vectors (only the two AK capacities changed, registered rules,
inside the box, no Km changed, balanced arms zero the native law at J1), 6
replays re-verified (9,492/9,492 daily balances, 33,600 quadrature values,
54 native/compiled checkpoints, 0 quarantined), 504 guard values rescored,
J1-J4 integrals recomputed by a separate code path, classification,
monotonicity and ledger flags re-derived. 21 targeted tests passed
immediately before launch. Full repository suite not run.

## Next step: a decision for the user, nothing launched

1. Registered Vmax-only search with the AK ratio as an additional dimension
   (AK ungrouped, a change of the search design), same bounds, same guards:
   tests whether the other capacities can restore G6P/F6P/PEP/B23PG once
   the ratio is free.
2. Read-only attribution of the hypothesis arm, J1-J4 and J4-J15, on the
   sealed evidence: where the remaining 0.82 mM net ATP loss goes now that
   AK is near zero (NDPK/ADSS, RKa, PRPPASe remain).
3. Observation contract for Sheet1 ATP/ADP/AMP, on which the balancing
   ratio rests.
