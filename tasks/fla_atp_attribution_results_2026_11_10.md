# Executed ATP/adenylate attribution at the working center: results

Status: executed and independently verified 2026-11-10. Closed. Read-only
bookkeeping on sealed trajectories: no integration, no parameter, state,
threshold or bound change, no promotion. Do not overwrite or rerun.

Archive: `output/atp_attribution_2026_11_10/`.
Receipt: `output/atp_attribution_decision_2026_11_10/`.
Protocol: `tasks/fla_atp_attribution_protocol_2026_11_10.md`.

Everything below describes ONE model trajectory (working center, full
backend, ultrastrict; strict agrees). Shares are not causes, and removing a
consumer is not predicted to restore ATP.

## Main findings

1. The collapse happens in the first two to three days, not late. ADP
   falls from 1.169 to 0.153 mM during day 1 and leaves its J15 working
   window at day 1.14. ATP falls from 0.933 to 0.165 mM by J3 and leaves
   its window at day 2.07. ADP drops below the 1e-3 mM gate at day 4.64,
   ATP at day 6.41. Of the 0.933 mM cumulative ATP deficit, 0.909 is
   incurred by J4.
2. In J1-J4 phosphate-bond demand is about 1.8 times glycolytic supply:
   bond equivalents (2 ATP + ADP) lose 2.98 mM, with 3.63 produced by
   PGK + PK and 6.61 consumed.
3. NDPK is the largest gross ATP consumer in J1-J4: 1.916 mM, 33.9% of
   5.656. Of that, 0.834 mM simply charges the latent GTP pool (GTP 1.00 ->
   1.83, GDP 1.00 -> 0.19) and 1.082 mM is spent by ADSS.
4. The ADSS flux is not a closed purine nucleotide cycle. ADSS 1.082 mM
   against ADSL 0.144 mM: the registered cycle throughput is only 0.144,
   and about 0.94 mM accumulates as ADESUC. Its IMP comes mainly from
   hypoxanthine salvage (HGPRT1 1.320 mM) rather than AMPD1 (0.374).
5. Adenylate kinase runs 2 ADP -> ATP + AMP (net 1.121 mM): it supplies
   23.6% of ATP production and is 38.2% of ADP consumption. AMP rises by
   1.786 mM in J1-J4: adenylates are parked as AMP.
6. After J4 the system is starved rather than driven: PGK is limited by
   ADP, and B13PG leaves almost entirely through the Rapoport-Luebering
   bypass (no ATP yield).

## Registered expectations

| Expectation | Outcome |
| --- | --- |
| (a) NDPK among the two largest J1-J4 ATP consumers, about one third | Confirmed: largest, 33.9% |
| (b) NDPK flux implies a purine-nucleotide-cycle throughput of comparable size | REFUTED: throughput 0.144 mM versus 1.916; the flux goes to GTP pool charging and ADESUC accumulation |
| (c) after J4 the availability gate, not raw capacity, limits PGK | Confirmed: J4-J8 PGK loses 1.213 of 1.370 mM raw (ADP 0.793, B13PG 0.421); J8-J15 1.634 of 1.642, all ADP |

## Gross ATP turnover, working center (mM)

| Window | Production | Consumption | Net | Top producers | Top consumers |
| --- | --- | --- | --- | --- | --- |
| J1-J4 | 4.747 | 5.656 | -0.909 | PGK 57.1%, AK 23.6%, PK 19.3% | NDPK 33.9%, RKa 17.7%, PFK 14.9%, PRPPASe 13.6%, HK 4.0% |
| J4-J8 | 0.325 | 0.349 | -0.024 | PK 49.9%, PGK 48.3% | NDPK 61.6%, PFK 18.8%, HK 6.8%, PRPPASe 5.4% |
| J8-J15 | 0.0072 | 0.0074 | -0.0002 | PGK 99.5% | NDPK 55.0%, PFK 19.6%, EGSSG 13.9% |

Daily, first days: production/consumption 3.473/3.617 (day 1), 0.755/1.378
(day 2), 0.520/0.661 (day 3), 0.228/0.246 (day 4). Day 1 alone turns over
more than three times the ATP pool; its consumers are NDPK 34.4%, RKa
27.6%, PRPPASe 12.1%, PFK 9.8%. Day 2 carries the largest deficit (-0.624).

## Cycle and pathway accounts, J1-J4 (mM)

| Account | Values |
| --- | --- |
| Purine nucleotide cycle | AMPD1 0.374, ADSS 1.082, ADSL 0.144; throughput 0.144; GTP cost 1.082 |
| NDPK coupling | net ATP -> GTP 1.916; GTP sink ADSS 1.082; GTP +0.834, GDP -0.809 |
| Adenylate kinase | AK 1.121 (2 ADP -> ATP + AMP), AK2 0.100 |
| PRPP | PRPPASe 0.768; sinks HGPRT1 1.320, HGPRT2 0.291, APRT 0; PRPP stock -0.843 |
| Glycolytic yield | return PGK + PK 3.626, investment HK + PFK 1.068, ratio 3.39 |
| Rapoport-Luebering | DPGM 1.554, PGK 2.711, bypass share 36.4% |

The bypass share rises to 77.0% in J4-J8 and 99.7% in J8-J15. The lumped
adenylate pool ATP+ADP+AMP loses 0.286, 0.296 and 0.447 mM in the three
windows, through AMPD1 net of ADSL (and VSAM early).

## Availability gate, J1-J4

No ATP/ADP-coupled reaction is limited by ATP or ADP in J1-J4. PGK already
loses 1.193 of 3.904 mM raw, entirely to B13PG availability. PK, HK, PFK,
NDPK, AK and PRPPASe run ungated. The gate therefore does not explain the
early deficit; it shapes the state after J4.

## Registered reading

Flags for the primary window: `NDPK_purine_cycle` TRUE (NDPK share 33.9%,
threshold 25%); `PRPPASe` false (13.6%); `availability_gate_on_PGK_PK`
false; `lower_glycolysis_supply` false (yield 3.39, bypass 36.4%). The
flag name predates the refutation of (b): what it supports is the NDPK /
latent guanylate part, not a closed cycle.

Registered prioritization: the latent GDP/GTP initialization contract and
the AMPD1/ADSS/ADSL structure.

## Contrast between trajectories

Fixed reference and search-selected point give the same picture: J1-J4 ATP
consumption 5.568 and 5.657 mM, NDPK 32.1% and 33.9%, cycle throughput
0.144 in both. The Vmax changes made so far do not alter the structure of
the early deficit.

## Hypotheses raised, not established

- H1. GDP = GTP = 1 mM at J1 is a latent convention far from where NDPK
  drives the pair given measured ATP and ADP. Charging GTP costs 0.834 mM
  ATP in J1-J4, the same order as the whole net ATP loss (0.909). This is
  an accounting coincidence until tested; other fluxes would respond.
- H2. Hypoxanthine salvage (HGPRT1) feeds ADSS, which spends GTP while
  ADSL does not keep up, so ADESUC accumulates. Whether that reflects the
  kinetics, the J1 stocks of HYPX/PRPP/IMP, or a structural issue is open.
- H3. Day-1 ribokinase demand (about 1.0 mM ATP in J1-J4) depends on the
  J1 ribose stock, whose measured or latent status was not checked here.

## Verification

Independent verifier passed on its first execution with a separate code
path (daily bincount integrals): 3,456 ledger values, 198/198 window
closures, 18 published ATP-budget rows reproduced, 306 gate identities
(executed equals raw times minimum consumer availability), 9,900
strict/ultrastrict comparisons, registered reading reproduced. The runner
additionally closed the lumped pools and all 14 daily intervals. 13
targeted tests pass (32 with the existing attribution suite). Full
repository suite not run.

## Limits

One trajectory per case under frozen parameters and the reaction-consistent
positivity policy. First-crossing days are support-based. GDP, GTP and
ADESUC are unmeasured latent states. Nothing here is validated against
independent biology.

## Next step: a decision for the user, nothing launched

Recommended: a read-only J1 provenance audit of the states that feed the
early sinks (GDP, GTP, RIB, PRPP, HYPX, IMP, ADESUC, B13PG): which are
measured in Sheet1, which are latent conventions, and where each latent
value comes from. It changes nothing and tells us which of H1-H3 can be
tested without touching a measured J1 value.

Only after that: a registered, reversible latent-guanylate diagnostic
(for example GDP/GTP initialized consistently with the NDPK relation at
measured J1 ATP/ADP), with measured J1 values untouched, the same guards
and the working center as comparator.
