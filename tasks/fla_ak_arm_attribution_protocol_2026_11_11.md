# Executed ATP/adenylate attribution of the AK ratio arms: protocol

Registered on 2026-11-11 before execution. This file is hash-frozen into
the archive; outcome and status are reported only in
`tasks/fla_ak_arm_attribution_results_2026_11_11.md` and at the top of
`fla_progress_log.md`. Config:
`config/fla_ak_arm_attribution_2026_11_11.json`. Fresh archive:
`output/ak_arm_attribution_2026_11_11/` (must not exist before launch).

Follow-up to `tasks/fla_ak_ratio_results_2026_11_11.md`, option 2 of its
next-step list, chosen by the user ("Attribution lecture seule").

## Question

On the sealed trajectories of the AK ratio diagnostic, once adenylate
kinase is close to zero net flux in J1-J4, which executed reactions and
which availability limitations account for the remaining loss of ATP and of
the adenylate phosphoryl stock, window by window from J1 to J15, and how do
they differ from the sealed control?

Descriptive bookkeeping on existing trajectories. Not a causal
intervention, a fit, a sensitivity analysis or biological validation.

## Inputs: sealed evidence only, no integration

No ODE is integrated and no parameter, state, threshold or bound is
changed. Evidence is read after hash and seal verification:

| Case | Archive folder | Backend | Profiles |
| --- | --- | --- | --- |
| control | `output/vmax_requalification_2026_11_09/controls/working_center/` | joint | strict, ultrastrict |
| balanced_forward_lowered (primary) | `output/ak_ratio_2026_11_11/candidates/balanced_forward_lowered/` | joint | strict, ultrastrict |
| balanced_reverse_upper_bound | `output/ak_ratio_2026_11_11/candidates/balanced_reverse_upper_bound/` | joint | strict, ultrastrict |
| intermediate_ratio | `output/ak_ratio_2026_11_11/candidates/intermediate_ratio/` | joint | strict, ultrastrict |

The control is the same sealed joint-backend control the AK diagnostic was
scored against (the 2026-11-10 attribution used the full backend of the
same case). Ultrastrict is primary and strict must agree. Windows: J1-J4
(primary), J4-J8, J8-J15, plus each of the 14 daily intervals.

## Disclosure: numbers seen before registration

Everything published in `tasks/fla_ak_ratio_results_2026_11_11.md` and in
`output/ak_ratio_2026_11_11/summary.json`: scores, guards, levels of 13
pools and both phosphoryl stocks at five dates, and for 13 reactions (AK,
AK2, AMPD1, ADSS, ADSL, NDPK, PRPPASe, RKa, HK, PFK, PGK, PK, HGPRT1) the
executed integrals on the three windows with gross ATP production and
consumption, for all four trajectories. Also the whole 2026-11-10
attribution of the full-backend control. Not read for the arms: any other
reaction (DPGM, 23DPGP, GMPK, transport, redox), any gate loss, any daily
value, any ledger of ADP, AMP, GTP or glycolytic intermediates.

A mechanics check of the runner was made on the control/strict trajectory
only, printing closure status and row counts, no values.

Registered expectations for the primary arm, each of which may be refuted:

(a) NDPK remains the largest gross ATP consumer in J1-J4 with a share of at
    least 25% (1.450 of 5.233 mM seen).
(b) In phosphate-bond equivalents (2 ATP + ADP), which AK cannot change,
    PRPPASe (ATP -> AMP, two equivalents per turnover) is the largest sink
    in J1-J4, ahead of NDPK and ribokinase.
(c) After J4 the availability-gate loss on PGK is lower than in the
    control, because ADP stays available longer.
(d) The glycolytic yield (PGK + PK) / (HK + PFK) is above 1 in J1-J4, as in
    the control.

## Registered analyses

A to E are the registered analyses of
`tasks/fla_atp_attribution_protocol_2026_11_10.md`, executed by the same
unchanged code (`analyse` in `scripts/run_atp_attribution.py`) with the
same windows, gate threshold 1e-3 mM, closure tolerances (1e-6 mM absolute,
0.1% relative), cycle definitions and reading thresholds:

A. Signed executed ledgers with closure, for ATP, ADP, AMP, GTP, GDP, GMP,
   IMP, PRPP, ADESUC, B13PG, B23PG, and additionally G6P, F6P and PEP (the
   pools whose guards failed), plus the lumped adenylate pool ATP+ADP+AMP
   and phosphate-bond equivalents 2*ATP+ADP.
B. Gross ATP and ADP turnover by reaction from the sign of the
   instantaneous executed rate.
C. Availability-gate loss per reaction and window with its limiting pool.
D. Cycle and pathway accounts: purine nucleotide cycle, NDPK coupling,
   adenylate kinase, PRPP, glycolytic yield, Rapoport-Luebering bypass.
E. Timing: first day ATP and ADP leave their J15 windows and fall below the
   gate; cumulative executed ATP net balance by day.

New in this protocol:

F. Contrast with the control. For ATP, phosphate-bond equivalents and total
   adenylates, per window and reaction: control, arm, and arm minus control
   for net, gross production and gross consumption, ranked by absolute net
   change. Differences between two trajectories, not effects of single
   reactions.

## Registered reading

The four prioritization flags of the 2026-11-10 protocol are evaluated on
J1-J4 for every case and reported for the primary arm next to the control:
`NDPK_purine_cycle` (NDPK at least 25% of gross ATP consumption),
`PRPPASe` (at least 25%), `availability_gate_on_PGK_PK` (gate loss above
executed integral), `lower_glycolysis_supply` (yield below 1 or bypass
share above 0.5), `none`. Several may hold. They only prioritize which
protocol to propose next; they authorize no change. Thresholds are the
engineering conventions already registered, not statistics.

No class, no pass/fail verdict on the AK hypothesis: the registered class
of the AK diagnostic (`no_supported_effect`) is not reopened.

## Limits stated in advance

One trajectory per case; shares depend on the frozen parameters and on the
reaction-consistent positivity policy. Attribution is additive
bookkeeping: a large consumer is not thereby the cause, and removing it is
not predicted to restore ATP; three fixed-kinetics diagnostics in this
model have already shown compensation. The arms fail the original guards,
so their trajectories are not admissible model states; they are read only
to describe what the network does when the AK ratio changes. GDP, GTP, RIB,
R5P and PRPP start from unmeasured latent conventions.

## Verification and closeout

An independent verifier, importing neither attribution module, recomputes
every window ledger from quadrature rates and weights, checks closure,
strict/ultrastrict agreement, agreement of gross ATP production and
consumption with the sealed AK diagnostic summary, every gate identity,
every contrast entry, and the reading flags of all cases. Seal every
folder; manifest last. Targeted tests pass before the archive is created.
The full repository suite is not run.

Files written before launch: `src/fla_ak_arm_attribution.py`,
`scripts/run_ak_arm_attribution.py`,
`scripts/verify_ak_arm_attribution.py`,
`qa/test_fla_ak_arm_attribution.py`.

Forbidden throughout: integration, parameter or bound change, threshold
change, clipping, J46, optimization, promotion.
