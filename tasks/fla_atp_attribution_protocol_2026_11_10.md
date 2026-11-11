# Executed ATP/adenylate attribution at the working center: protocol

Status: protocol as registered before launch on 2026-11-10. This file is
hash-frozen into the archive; outcome and status are in
`tasks/fla_atp_attribution_results_2026_11_10.md`. Module, runner, verifier
and 13 targeted tests were written before launch. Config:
`config/fla_atp_attribution_2026_11_10.json`. Planned fresh archive:
`output/atp_attribution_2026_11_10/` (must not exist before launch).

Follow-up to `tasks/fla_vmax_corrected_search_results_2026_11_10.md`, which
classified local Vmax-only search in the original boxes as exhausted.

## Question

On the sealed trajectories of the current model, which executed reactions
and which availability limitations account for the loss of ATP and ADP,
window by window from J1 to J15?

This is descriptive bookkeeping on existing trajectories. It is not a
causal intervention, a fit, a sensitivity analysis or biological validation.

## Scope change versus the proposal: J1-J15, not J8-J15 only

The proposal named J8-J15. Sealed budgets already published in
`output/vmax_requalification_decision_2026_11_09/ATP_budgets.csv` show that
window is the wrong place to look alone. For the working center
(full backend, ultrastrict):

| Window | Executed ATP production (mM) | Consumption (mM) | Net (mM) |
| --- | --- | --- | --- |
| J1-J4 | 4.74702 | 5.65603 | -0.90901 |
| J4-J8 | 0.32534 | 0.34899 | -0.02365 |
| J8-J15 | 0.00720 | 0.00744 | -0.00025 |

The deficit is incurred in J1-J4. By J8-J15 total turnover is about 0.007
mM in seven days and executed PGK is 0.0072 mM against a raw (ungated)
integral of 1.64 mM: that window describes an already starved state, not
the cause. All three windows are therefore registered, with J1-J4 as the
primary one and daily resolution inside it.

## Disclosure: numbers seen before registration

While preparing this protocol the following sealed values were read: the
table above; NDPK net ATP-consuming direction 1.91638 mM in J1-J4, 0.21509
in J4-J8, 0.00409 in J8-J15; and the ten largest J8-J15 ATP contributions
(PGK +0.007159, NDPK -0.004093, PFK -0.001460, EGSSG -0.001037, HK
-0.000342, PRPPASe -0.000235). The registered expectations below are
informed by them. Nothing else of the per-reaction J1-J8 ledger was read.

Registered expectations: (a) NDPK is among the two largest gross ATP
consumers in J1-J4 (about one third); (b) because GTP is consumed only by
ADSS in this network and GDP/GTP are latent, sustained NDPK flux implies a
purine-nucleotide-cycle throughput (AMPD1 -> ADSS -> ADSL) of comparable
size; (c) after J4 the availability gate, not raw capacity, limits PGK.
Each is checked, and each may be refuted.

## Inputs: sealed evidence only, no integration

No ODE is integrated and no parameter, state, threshold or bound is
changed. Evidence is read after hash and seal verification:

| Case | Archive folder | Backend | Profiles |
| --- | --- | --- | --- |
| fixed_reference | `output/vmax_requalification_2026_11_09/controls/fixed_reference/` | full | strict, ultrastrict |
| working_center | `output/vmax_requalification_2026_11_09/controls/working_center/` | full | strict, ultrastrict |
| search_selected (comparator) | `output/vmax_corrected_search_2026_11_10/candidates/selected/` | joint | strict, ultrastrict |

Per folder: `flux_evidence.npz` (stoichiometric matrix, reactions, raw and
executed order-8 quadrature rates, weights, intervals, daily integrals) and
`trajectory_evidence.npz` (states at the same quadrature nodes). The
working center is primary; ultrastrict is primary and strict must agree.

Windows: J1-J4, J4-J8, J8-J15, plus each of the 14 daily intervals.

## Registered analyses

A. Signed executed ledgers. For ATP, ADP, AMP, GTP, GDP, GMP, IMP, PRPP,
ADESUC, B13PG and B23PG: contribution of every reaction per window, and
closure of the sum against the state change within the inherited
quadrature tolerances (1e-6 mM absolute, 0.1% relative). Also the lumped
adenylate pool ATP+ADP+AMP and phosphate-bond equivalents 2*ATP+ADP.

B. Gross ATP and ADP turnover. Production and consumption by reaction from
the sign of the instantaneous executed rate at the quadrature nodes (so a
reaction that reverses is not netted away), with shares of the gross total
and a ranking per window.

C. Availability-gate loss. Raw minus executed integral per reaction and
window, and its allocation to the limiting substrate pool with the
existing `limiting_loss_attribution` at threshold 1e-3 mM. Reported for
every ATP/ADP-coupled reaction; PGK, PK, HK, PFK, NDPK, AK and PRPPASe are
tabulated explicitly.

D. Registered cycle and pathway accounts, defined from the frozen
stoichiometry before execution:

1. Purine nucleotide cycle: integrals of AMPD1, ADSS and ADSL; cycle
   throughput is the minimum of the three; GTP cost equals ADSS.
2. NDPK coupling: net ATP -> GTP transfer, the GTP sinks (ADSS) and GDP
   sources (ADSS, GMPK), and the GDP/GTP state changes from J1 = 1 mM each.
3. Adenylate kinase: net direction and integral of AK (2 ADP <-> ATP + AMP)
   and AK2.
4. PRPP: PRPPASe (ATP -> AMP) against its salvage sinks HGPRT1, HGPRT2 and
   APRT, and the PRPP inventory change.
5. Glycolytic yield: (PGK + PK) / (HK + PFK) executed integrals.
6. Rapoport-Luebering bypass: DPGM / (DPGM + PGK) share of B13PG outflow,
   and V23DPGP return.

E. Timing. From the dense saved states: first day ATP and ADP leave their
J15 working windows, first day each falls below the 1e-3 mM gate, and the
cumulative executed ATP net balance by day.

F. Contrast. The same tables for the fixed reference and the search-selected
point, as differences from the working center. These are descriptive
differences between three trajectories, not effects of single parameters.

## Registered reading of the outcome

The result is a ranked description, mapped to the four reversible
alternatives of the previous handoff. The mapping only prioritizes which
protocol to write next; it does not authorize any change.

- NDPK and the purine nucleotide cycle carry at least 25% of gross J1-J4
  ATP consumption: prioritize the latent GDP/GTP initialization contract
  and the AMPD1/ADSS/ADSL structure.
- PRPPASe carries at least 25%: prioritize a registered PRPP box
  diagnostic.
- Gate loss on PGK/PK exceeds their executed integral within J1-J4:
  prioritize the availability-gate formulation.
- HK + PFK investment exceeds PGK + PK return within J1-J4 (yield below 1),
  or the Rapoport-Luebering bypass exceeds 50% of B13PG outflow: prioritize
  the lower-glycolysis/B13PG supply question.
- None of the above: report so; do not force a category.

Several conditions may hold together; report all. Thresholds are
engineering conventions fixed here, not statistics.

## Limits stated in advance

One trajectory per case; shares depend on the frozen parameters and on the
reaction-consistent positivity policy. Attribution is additive bookkeeping:
a large consumer is not thereby the cause, and removing it is not
predicted to restore ATP. Earlier screens found that lowering one demand is
compensated by others. GDP and GTP are unmeasured latent states. No
statement about donors, storage conditions or biology beyond the model.

## Verification and closeout

An independent verifier recomputes every ledger from quadrature rates and
weights, checks closure, strict/ultrastrict agreement, agreement with the
published `ATP_budgets.csv` rows, and each cycle account from the matrix.
Seal every folder; manifest last. Targeted tests must pass before the
archive is created; state whether the full suite was run.

Planned files, none written yet: `src/fla_atp_attribution.py`,
`scripts/run_atp_attribution.py`, `scripts/verify_atp_attribution.py`,
`qa/test_fla_atp_attribution.py`, results report
`tasks/fla_atp_attribution_results_2026_11_10.md`.

Forbidden throughout: integration, parameter or bound change, threshold
change, clipping, J46, optimization, promotion.
