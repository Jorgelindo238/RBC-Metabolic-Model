# Executed ATP/adenylate attribution of the AK ratio arms: results

Closed on 2026-11-11. Protocol
`tasks/fla_ak_arm_attribution_protocol_2026_11_11.md`, config
`config/fla_ak_arm_attribution_2026_11_11.json`. Chosen by the user
("Attribution lecture seule"). Read-only archive
`output/ak_arm_attribution_2026_11_11/` and receipt
`output/ak_arm_attribution_decision_2026_11_11/` are sealed: do not
overwrite or rerun. No integration, no parameter, state, threshold or bound
change. Descriptive, not causal. The class of the AK diagnostic
(`no_supported_effect`) is not reopened; the arms fail the original guards
and are not admissible model states.

All values below: ultrastrict, mM, executed integrals. Primary arm =
`balanced_forward_lowered` (Vf/Vr 0.667). All 384 window closures pass;
strict and ultrastrict agree.

## Registered reading (J1-J4)

| Case | NDPK share of gross ATP consumption | PRPPASe share | Glycolytic yield | Bypass share | Flags |
| --- | --- | --- | --- | --- | --- |
| control | 33.9% | 13.6% | 3.39 | 0.364 | `NDPK_purine_cycle` |
| intermediate_ratio | 31.3% | 14.4% | 3.75 | 0.311 | `NDPK_purine_cycle` |
| balanced_forward_lowered | 27.7% | 14.5% | 3.90 | 0.299 | `NDPK_purine_cycle` |
| balanced_reverse_upper_bound | 28.2% | 14.3% | 3.90 | 0.298 | `NDPK_purine_cycle` |

Same single flag in every case; `PRPPASe`, `availability_gate_on_PGK_PK`
and `lower_glycolysis_supply` false everywhere.

## Registered expectations

- (a) NDPK largest gross ATP consumer in J1-J4 with at least 25%:
  CONFIRMED (1.450 of 5.233, 27.7%).
- (b) PRPPASe largest sink of phosphate-bond equivalents in J1-J4:
  CONFIRMED narrowly in the primary and capacity arms (1.514 versus NDPK
  1.450; 1.524 versus 1.500); not in the intermediate arm (NDPK 1.781,
  PRPPASe 1.639).
- (c) Lower PGK gate loss after J4 than in the control: REFUTED. It is
  higher (J4-J8 3.090 versus 1.213; J8-J15 5.252 versus 1.635), and the
  limiting pool changes from ADP to B13PG.
- (d) Glycolytic yield above 1: CONFIRMED (3.90).

## Where the phosphoryl stock goes in J1-J4

AK cannot change 2 ATP + ADP. Its J1-J4 change is -1.832 mM in the primary
arm against -2.982 in the control.

| Reaction | Control | Primary arm | Arm minus control |
| --- | --- | --- | --- |
| PGK | +2.711 | +2.989 | +0.278 |
| PK | +0.915 | +1.320 | +0.405 |
| PRPPASe (2 per turnover) | -1.536 | -1.514 | +0.022 |
| NDPK | -1.916 | -1.450 | +0.467 |
| RKa | -1.000 | -1.000 | 0.000 |
| PFK | -0.843 | -0.865 | -0.022 |
| SAM | -0.314 | -0.310 | +0.004 |
| HK | -0.225 | -0.239 | -0.013 |
| GSS, OPLAH, GLUCYS and others | -0.774 | -0.764 | +0.010 |
| Total | -2.982 | -1.832 | +1.149 |

NDPK 1.450 = ADSS 1.058 + GTP charging 0.392 (GTP 1.00 -> 1.39). The
demand side is almost unchanged by the ratio: PRPPASe, RKa, PFK, HK, SAM
and the glutathione reactions move by less than 0.03 mM each. The 1.15 mM
spared comes from NDPK (0.47) and from more PGK and PK (0.68).

Total adenylates fall by 0.270 (control 0.286): AMPD1 -0.357, SAM -0.155,
ADSL +0.144, AK2 +0.098. The ratio does not change the adenylate loss.

## ATP itself, day by day

| Day | ATP control | ATP arm | ADP control | ADP arm |
| --- | --- | --- | --- | --- |
| J1 | 0.933 | 0.933 | 1.169 | 1.169 |
| J2 | 0.788 | 0.602 | 0.153 | 1.005 |
| J3 | 0.165 | 0.157 | 0.065 | 1.143 |
| J4 | 0.024 | 0.113 | 0.006 | 0.977 |
| J8 | 3e-4 | 0.074 | 1e-5 | 0.355 |
| J15 | 9e-5 | 0.004 | 2e-6 | 2e-4 |

ATP leaves its J15 window at day 1.89 (control 2.07) and never falls below
the 1e-3 gate; ADP falls below the gate at day 13.83 (control 4.64). ADP
dips below 0.316 mM inside day 1 (first saved time 1.19) and is back at
1.005 at J2. Cumulative executed ATP net: -0.331 after day 1 (control
-0.145), -0.776 after day 2, -0.820 at J4, -0.929 at J15.

Day 1-2 in the arm: PGK +2.807, PK +0.421 against NDPK -1.182, RKa -1.000,
PRPPASe -0.425, PFK -0.352, glutathione reactions and SAM -0.37. From day 2
on, PGK gives only 0.09 mM/day and PK about 0.45 mM/day.

## Why production does not follow once ADP is available

- GAPDH is 0.681 mM on J1-J4 in the control and 0.681 in the arm, 0.652 on
  J4-J8 (control 0.682), 2.185 on J8-J15 (control 2.237). The supply of
  B13PG is insensitive to the AK ratio.
- PGK in J1-J4 (2.989) is mostly the initial B13PG stock: B13PG(0) is the
  3.584 mM duplicated B13PG/B23PG Sheet1 row, drained in day 1. Afterwards
  PGK is held at the B13PG gate: raw minus executed 1.805, 3.090, 5.252 mM
  on the three windows, limiting pool B13PG. PK has no gate loss before J8.
- With ADP available, the Rapoport-Luebering bypass share falls (0.193 on
  J4-J8 and 0.317 on J8-J15, against 0.770 and 0.997 in the control), and
  B23PG is drained faster by 23DPGP (1.759, 1.975, 1.631) than DPGM refills
  it (1.276, 0.126, 0.693): the B23PG guard failure.
- PEP: of the PEP produced by ENOPGM, the phosphatase VPEP_PASE takes 2.337
  of 3.657 mM on J1-J4 (64%), 2.735 of 3.762 on J4-J8 (73%) and 2.927 of
  3.502 on J8-J15 (84%), with no ATP formed, while PK is not ADP-gated. In
  the control the share is 75%, 95% and 100%.
- Upper glycolysis: HK is 0.239, 0.235 and 0.250 mM on the three windows
  (control 0.225, 0.024, 0.0003). G6P accumulates (+0.177, +0.061) while
  F6P falls (PGI only 0.028 and 0.058): the G6P and F6P guard failures.
  On J1-J4, PFK (0.865) is fed mainly by TAL 0.473 and TKL2 0.354, not by
  PGI.

Read together: in the arm ATP demand in J1-J4 is unchanged, AK no longer
converts ADP into ATP and AMP, and sustained ATP production after day 2 is
set by B13PG supply and by the PK/PEP phosphatase split, not by ADP.

## Later windows (primary arm)

Gross ATP turnover continues: 1.78 mM on J4-J8 and 2.15-2.22 on J8-J15
(control 0.33 and 0.007). NDPK is the top consumer throughout (35.9% and
53.9%); on J8-J15 NDPK 1.196 exceeds ADSS 0.642, so it again charges GTP
(GTP 1.39 -> 1.94 at J15). PRPPASe continues (0.350, 0.281; control 0.019,
0.0002). Net ATP -0.039 and -0.070; bond equivalents -0.700 and -0.495.

## Capacity and intermediate arms

Same J1-J4 structure. Capacity arm: bond equivalents -1.893, top consumers
NDPK 28.2%, RKa 18.8%, PFK 16.3%, PRPPASe 14.3%; ADP below the gate at day
12.15. Intermediate arm: bond equivalents -2.518; ADP below the gate at day
7.35, ATP at day 9.68.

## Verification

Independent verifier passed on its first execution: 6,912 ledger values,
384/384 closures, 24 gross ATP budget rows equal to the sealed AK
diagnostic summary, 408 gate identities, 19,200 strict/ultrastrict
comparisons, 6,318 contrast values (702 rows), reading flags of all four
cases re-derived. 9 targeted tests (plus the 13 inherited attribution
tests) passed immediately before launch. Full repository suite not run.

## Limits

One trajectory per case, additive bookkeeping, no causal claim: three
fixed-kinetics diagnostics have shown that this network compensates. The
arms fail the original guards. GDP, GTP, RIB, R5P and PRPP start from
unmeasured latent conventions; the B13PG initial value is the ambiguous
duplicated row that the user decided to keep. No statement about biology
beyond the model.

## Next step: a decision for the user, nothing launched

1. Registered Vmax-only search with the AK ratio free (AK ungrouped, a
   change of the search design), same bounds and guards. This attribution
   says what such a search would have to do: raise B13PG supply and the PK
   share of PEP while holding G6P, F6P, PEP and B23PG.
2. Read-only review of the two ATP-free routes seen here, VPEP_PASE and
   the B13PG/B23PG initial convention with the DPGM/23DPGP laws, against
   RBC-GEM and their provenance. No integration.
3. Observation contract for Sheet1 ATP/ADP/AMP.
