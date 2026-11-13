# Successor engine: historical replay qualification

Date: 2026-11-12. Executed by Codex after Claude handoff. No agents.

## Result and scope

Both fixed-parameter working-centre replays completed through
`fla_user_engine.prepare/run`, using the existing phase-aware
`GemCorrectionRHS`, the archived Radau settings and bounded Jacobian.
Strict and ultrastrict each reproduce their own sealed reference exactly
at J1/J4/J8/J11/J15: maximum absolute state difference 0, 570 values per
profile (113 concentration states plus clamped pH, five dates).
The 55 curated measured J1 values are identical, and 220 post-J1 residuals
per profile use only the four actual measured dates.

This qualifies historical adapter parity ONLY. It does not qualify arbitrary
user datasets, establish biological validity, or rescue ATP. The strict
replay still has ATP J15 = 8.982165602991936e-5 mM. No parameter was changed,
no optimizer ran, no source archive was overwritten, no default was promoted.
`QUALIFICATION_STATUS` and API `engine_compatibility` remain unchanged.

## Evidence

- Source: `output/vmax_requalification_2026_11_09/`, working_center/joint.
- New sealed archive: `output/user_engine_qualification_2026_11_12/`.
- Independent receipt:
  `output/user_engine_qualification_verification_2026_11_12/receipt.json`.
- Runner: `scripts/qualify_user_engine.py`.
- Independent verifier: `scripts/verify_user_engine_qualification.py`.
- Adversarial verifier tests: `qa/test_user_engine_qualification_verifier.py`.

The source manifest was checked before and after replay and independently
at verification. The successor archive records the input contract, overrides,
solver profiles, source/code hashes and full trajectory supports. A first
preparation attempt failed on a missing structural key before any output
directory or integration was created. The retry explicitly used the historical
biochemical_transfer layout without adding or changing parameter values.

| Support | Strict points | Ultrastrict points |
| --- | ---: | ---: |
| Accepted solver states | 2308 | 3998 |
| Dense recorded support | 313 | 313 |
| Order-4 quadrature | 9280 | 16040 |
| Order-8 quadrature | 18560 | 32080 |

All recorded supports are finite and inside J1-J15. Concentration minima are
nonnegative on these supports; global recorded minimum is zero. This is not
a mathematical proof of positivity at every continuous time. Clamped pH
remains exactly 7.2. No negative-state clipping or repair was applied.
The verifier recomputes array comparisons, support gates, initial identity,
parameter/kinetic identity and residuals without calling the runner or RHS.
It does not recompute reaction flux ledgers or daily balance closure in this
pass; those remain evidence of the historical campaigns, not new claims.

## Software verification and corrections

- Six Python test files (engine plus previous contract/orchestrator tranche):
  276 passed in 22.14 s.
- New independent-verifier tests: 7 passed in 2.28 s, including resealed
  changed parameters, early times, altered J1, wrong trajectories and negative
  quadrature support. Total targeted Python tests: 283.
- Lifecycle tests: 21 passed after two additional regression tests.
- TypeScript: `tsc --project apps/web/tsconfig.json --noEmit --incremental false`
  passed. `git diff --check` passed.
- Full repository suite and rendered browser flows were NOT run. No UI layout
  redesign, API wiring, dev server, commit or push was performed.

Lifecycle corrections beyond Claude's tranche:
1. A missing completion status is no longer interpreted as completed.
2. Unknown/invalid data-contract statuses cannot authorize activation.
3. Monitoring cannot claim active from a persisted boolean alone: an explicit
   activation with identical dataset, subject and contract fingerprint is needed.

## Remaining gates before general user calibration

1. The 118 archived parameter entries are overrides, NOT a complete explicit
   kinetic vector. Missing keys still resolve through kernel defaults, including
   the historical SAM convention. Source pinning and parity make the replay
   reproducible, not the user-engine claim of fully explicit constants true.
   Build an audited effective-parameter resolver and source fingerprint without
   changing numerical values, then test missing-key rejection for new datasets.
2. `PreparedRun` is only shallowly frozen. Its current fingerprint omits model
   layout, kinetics, network mode, tolerances, solver settings and provenance.
   `validate` does not comprehensively detect mutation of nested fields and can
   raise on malformed structures despite its documented contract. Harden and
   test these before wiring this engine to the API.
3. The historical recorder is deliberately J1-specific and requires 114 states
   with pH 7.2. This replay does not validate a real solver starting on other
   first-sample dates. Generalize as a successor, not an edit of sealed code.
4. Sample-only default solver output is not enough to establish the physical
   trajectory gate. Accepted and quadrature supports must be required on the
   production successor path, as they were in this qualification adapter.
5. Historical R5P remains an unpromoted latent comparator; other latent inventory
   provenance, adenylate observation definitions and borrowed H=0.58 remain open.
   The subject label explicitly says unknown-donor curated table; no actual donor
   validation was claimed. Relative data remain blocked.
6. Simplify Calibration/Monitoring only around the real contract and job state.
   Static demonstration bags and forecasts and the unconditional applied flag in
   `research-calibration.ts` are still outstanding; no broad UI changes in this pass.

## Next bounded task

Harden the prepared-run integrity and effective-parameter contract (items 1-2)
with injected, non-ODE tests first. Then qualify a recorded solver successor
at a shifted first-sample date. Keep all public launch/activation gates closed
until the whole input-to-evidence path passes. Do not increase Vmax search
budget on the strength of this software parity result.
