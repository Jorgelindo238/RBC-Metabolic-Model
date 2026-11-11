# Latent guanylate partition diagnostic: results

Status: executed and independently verified 2026-11-10 after explicit user
authorization. Closed. Do not overwrite or rerun. The working center
(absolute attempt 76) and the J1 convention GDP = GTP = 1 mM are retained.
Nothing promoted; no calibration launched.

Archive: `output/guanylate_partition_2026_11_10/`.
Receipt: `output/guanylate_partition_decision_2026_11_10/`.
Protocol: `tasks/fla_guanylate_partition_protocol_2026_11_10.md`.

## Verdict

Registered classification: `no_supported_effect`. The hypothesis that the
initial guanylate partition explains part of the early ATP/ADP loss is NOT
supported at fixed kinetics. Both arms are numerically valid, both carry
the `early_only` flag, both fail the original guards, and neither reaches
the absolute J15 windows.

Arms A (inventory +0.93 mM) and B (inventory-matched) give almost the same
trajectory, so the result is not an inventory effect either.

## What was changed

Only GDP(0) and GTP(0). All 55 measured J1 values (220 identity checks),
every other latent state, the working-center Vmax, every Km, network,
threshold and guards are unchanged. Four new integrations, no retry.

| Arm | GDP(0) | GTP(0) | Total | delta_E_G(0) | Raw NDPK at J1 (mM/day) |
| --- | --- | --- | --- | --- | --- |
| control (sealed) | 1.0 | 1.0 | 2.0 | 0 | 6.634 |
| A_fixed_total | 0.067476 | 1.932524 | 2.0 | +0.932524 | 0 |
| B_fixed_phosphoryl | 0.062507 | 1.468747 | 1.531253 | 0 | 0 |

The zeros are zeros of the executable law on both backends at day 1 only.

## Outcome (ultrastrict; strict agrees to the digits shown)

| Quantity | Control | Arm A | Arm B |
| --- | --- | --- | --- |
| ATP J4 (mM) | 0.02399 | 0.03097 | 0.03153 |
| ADP J4 (mM) | 0.005784 | 0.009152 | 0.009294 |
| ATP J15 (mM) | 8.982e-5 | 9.118e-5 | 9.132e-5 |
| ADP J15 (mM) | 1.775e-6 | 1.807e-6 | 1.808e-6 |
| AMP J4 (mM) | 2.525 | 2.510 | 2.509 |
| Worst-profile absolute gap | 12.08918 | 12.07103 | 12.07062 |
| ATP:lower / ADP:lower | 9.039 / 12.089 | 9.024 / 12.071 | 9.023 / 12.071 |
| Worst dated adenylate ratio | 0.9345 | 0.9292 | 0.9291 |
| Original reserved guards | pass | FAIL | FAIL |

ATP at J15 rises by about 1.7% and ADP by 1.9% in arm B, against a gap of
four to five orders of magnitude. The gap moves by 0.019 log units.

Guards failed by arm B (value above zero; control value in brackets):
F6P J4 0.487 (-0.002), B23PG MSE 0.457 (-0.049), F6P J11 0.235, PEP J15
0.193, PEP J8 0.188, G6P J8 0.105, G6P MSE 0.099, PEP J4 0.095, PEP MSE
0.054, G6P J4 0.048, GLN MSE 0.034, GMP MSE 0.030, plus ESER, INO, SER and
EINO J4/J8. Arm A fails a nearly identical set.

## Executed J1-J4 ledger (mM)

| Quantity | Control | Arm A | Arm B |
| --- | --- | --- | --- |
| NDPK net | 1.9164 | 1.0170 | 0.9967 |
| ADSS | 1.0821 | 1.0866 | 1.0635 |
| ADSL | 0.1441 | 0.1441 | 0.1440 |
| Gross ATP consumption | 5.6560 | 4.9457 | 4.9319 |
| Gross ATP production | 4.7470 | 4.0437 | 4.0304 |
| Net ATP | -0.9090 | -0.9020 | -0.9015 |
| PGK | 2.7110 | 2.2267 | 2.2203 |
| PK | 0.9152 | 0.7989 | 0.7957 |
| AK (2 ADP -> ATP + AMP) | 1.1208 | 1.0181 | 1.0144 |
| PRPPASe | 0.7679 | 0.8423 | 0.8447 |
| RKa | 1.0000 | 1.0000 | 1.0000 |

Reading, descriptive:

- Starting at zero NDPK flux removes the GTP-charging part (about 0.92 mM)
  but NDPK still transfers about 1.0 mM in J1-J4, the amount ADSS consumes.
- Gross ATP consumption falls by 0.72 mM and gross production falls by
  0.72 mM. The net J1-J4 ATP balance is unchanged at about -0.90 mM.
- The registered `compensation` flag is FALSE in both arms: it compares the
  NDPK reduction with the consumption reduction (0.72 >= 0.5 x 0.92). It
  was not designed to catch a production-side response. Noted after seeing
  the results, therefore not a registered finding: production fell by as
  much as consumption.
- Phosphoryl stocks: E_A = 2 ATP + ADP falls from 3.035 to 0.054 (control),
  0.071 (A), 0.072 (B) by J4. In the control E_G absorbs +0.86; in arm B
  E_G falls slightly (3.000 -> 2.961). E_A + E_G at J4 is 3.913 (control),
  3.962 (A), 3.033 (B). Removing the guanylate sink did not preserve the
  adenylate phosphoryl stock.

## What this establishes and what it does not

Established for this parameter set, network and positivity policy:
repartitioning latent GDP/GTP to the NDPK zero at J1, with or without added
phosphoryl inventory, does not prevent the early collapse and breaks the
original PEP/G6P/F6P/B23PG guards. The earlier accounting observation
(0.834 mM of ATP charged into GTP) was correctly not read as a predicted
recovery.

Not established: anything about other guanylate totals or partitions (two
arms do not map the plane); any biological statement about guanylates;
global infeasibility; the cause of the collapse.

## Observation for the next decision (post hoc, not a registered result)

RKa integrates to 1.0000 mM in J1-J4 in all three trajectories, the size of
the latent RIB(0) = 1 mM software default, and PRPPASe then converts 0.77
to 0.84 mM ATP directly to AMP. AMP rises from 0.739 to about 2.51 mM by J4
in every arm. An earlier plan already named this test and its conditions
(`tasks/fla_joint_glucose_energy_2026_10_27.md`, line 153: a separately
recorded RIB(0) latent-initialization feasibility test, all 55 measured J1
preserved, any range labelled diagnostic, tracking VRKa, PRPPASe, NDPK and
the adenylate/PEP budgets, no promised ATP rescue). This is bookkeeping on
existing trajectories and may be refuted like the guanylate hypothesis.

## Verification

Independent verifier passed on its first execution: 4 zero-flux checks on
both backends, 220 measured-J1 identity checks, 4 replays re-verified
(6,328/6,328 daily executed balances, 22,400 quadrature values, 36
native/compiled checkpoints), 336 guard values rescored, executed J1-J4
integrals recomputed by a separate code path, paired comparisons and the
classification re-derived. 22 targeted tests passed before launch. Full
repository suite not run. The run, audit description and verifier executed
end to end for the first time in this campaign.

## Next step: a decision for the user, nothing launched

1. A RIB(0)-only fixed-kinetics diagnostic under the 27 October conditions,
   with a registered production-side compensation criterion this time.
2. A structural review of the purine branch against RBC-GEM (ADSS versus
   ADSL capacity, ADESUC accumulation, PRPPASe/HGPRT salvage), read-only
   first.
3. Stop latent-state diagnostics and return to the observation contract
   (normalization and pool definition of ATP/ADP in Sheet1).
