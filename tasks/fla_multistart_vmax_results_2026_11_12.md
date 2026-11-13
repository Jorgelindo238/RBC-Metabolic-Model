# Multistart Vmax-only SLSQP: execution results

Date: 2026-11-12. Claude prepared the successor; Codex reviewed and executed it.
Protocol: `tasks/fla_multistart_vmax_protocol_2026_11_12.md`.

## Review and tests

Claude's30 tests passed. Codex strengthened `admissible` to require exactly
both strict and ultrastrict profiles, adding missing-profile assertions.
The combined multistart/corrected-search/requalification/absolute/temporal
suite passed62 tests in15.96s. Full repository suite not run.

No other scientific, solver or historical source change was made for this
launch. Both archived control replays reproduce concentrations bitwise before
optimization. Km, J1, network, transport, H, availability threshold, the14 Vmax
groups (17 capacities), boxes and84 dated constraints/reserve remain unchanged.

## Actual search coverage

87 distinct ODE evaluations, all numerically valid; nine pass the inherited
reserved guard screen. No numerical failure, repaired state or fabricated score.
240 was a ceiling, not a target that had to be exhausted.

| Start | Distinct evaluations | Outcome |
| --- | ---: | --- |
| Candidate35 | 34 | Two SLSQP iterations; stagnation; incumbent unchanged |
| Working centre | 50 | Three iterations; per-start budget stops the next complete gradient batch |
| Objective descent seed | 1 | Metabolic guards fail; not optimized |
| Guard-relief seed | 1 | Metabolic guards fail; not optimized |
| Fixed-RNG seed | 1 | Metabolic guards fail; not optimized |

The working-centre allowance was52, but another complete Jacobian batch would
exceed the remaining allowance. Evaluation budgets are not interchangeable
between starts under this protocol. Only TWO starts actually underwent SLSQP;
do not describe this as five successfully optimized basins or global coverage.

Five Jacobians were computed. The four leading-group0.006/0.003 checks passed
for each optimized start, with no coordinate frozen. This checks the registered
objective-side and binding-guard components only, not all possible derivatives.
The inspected groups were PRPP, PGK, SAM and NDPK at both initial anchors.

## Result

No new point improved on candidate35 by more than the registered1e-6 objective
threshold. Its retained objective remains12.087279723325437; the smallest valid
guard-feasible optimizer objective was12.087279442161297 (attempt84), a decrease
of only2.81164e-7, below that threshold. Do not report this as exactly zero
numerical movement, or lower the threshold after seeing it.

Consequently: no new finalist, no new strict/ultrastrict finalist integrations,
no new accepted Vmax vector, no promotion. `selected: null` and the campaign's
`admitted_under_inherited_guards: false` refer to NEW finalists; they do not
revoke candidate35's previous validated guard admissibility.

The retained candidate35 has ATP J15=8.993285092e-5mM and
ADP J15=1.778157524e-6mM. Biological ATP/ADP targets remain unmet.

## Interpretation and limitations

Replacing local LP rounds with constrained nonlinear SLSQP did not produce
a material gain in this run. This is a bounded local-search outcome, NOT
global infeasibility, identified kinetic constants or biological validation.
The working-centre start approaches the same objective as candidate35.

The three radius0.05 seeds are outside metabolic guards, despite numerical
success. They were not feasibility-restored; thus the advertised additional
starts did not explore other feasible basins. Objective-seed violations include
G6P/GLN/LAC and purine channels; the guard-relief seed violates F6P/G6P/PEP
and other guards; the random seed violates several of these too.

SLSQP reports a large multiplier on zero:EINO:J4 and contributions from GLN,
MAL, AMP, XAN, LAC and other guards. Multiplier magnitudes depend on constraint
scaling and are local numerical output, not a ranking of biological importance.
Optimizer feasibility uses the full inherited reserve, while incumbent acceptance
uses the original half-reserve rule; this stricter proposal margin was declared
before execution, not a post-hoc relaxation or change in guard caps.

## Evidence

- Sealed campaign: `output/multistart_vmax_2026_11_12/`.
- Independent verification is run separately with
  `scripts/verify_multistart_vmax.py`; receipt path:
  `output/multistart_vmax_verification_2026_11_12/verification.json`.
- Verification PASSED:87 evaluations,2,659,753 inspected support points,
  five reconstructed Jacobians, two leading-group derivative checks,30 events,
  budget/cache/seed/incumbent rules and source/campaign/code hashes. Zero new
  daily-balance verifications, because no finalist triggered full flux auditing;
  do not carry over the previous campaign's3,164 balances as a new result.
- `trace.jsonl`, `checkpoint.json`, `search_result.json`, `jacobians.json`,
  `summary.json` and per-attempt recorded trajectories preserve all outcomes.
- Exports: objective/constraint traces, dated concentrations and seed statuses.
  `vmax_by_finalist.csv` has a header only because there is no new finalist.
- No J46 run, UI change, agent launch, active parameter change, commit or push.

## Next decision

Do not simply repeat this SLSQP run or claim that using more nominal starts
solved exploration. The next optimization-method improvement would be an explicit
feasibility-restoration phase for joint seeds, keeping the ORIGINAL guard caps,
before another multistart search. Register its budget and reject unrepaired seeds
honestly. Changing AK/NDPK grouping, state/observation definitions, network or
parameter bounds remains a separate scientific hypothesis, not authorized by
this null result.
