# Constrained multistart Vmax-only SLSQP search (registered before execution)

Date 2026-11-12. Prepared by Claude with file tools only. NOTHING here has been
executed: no test, integration or optimizer run. Codex reviews, runs the tests,
then runs the campaign with its own tools.

## Why a successor, and what is new

The sealed campaign `output/corrected_vmax_2026_11_12/` (independent receipt
`output/corrected_vmax_verification_2026_11_12/verification.json`) finished
four trust-region LP rounds: 58 search integrations, candidate35 admissible
under the 84 inherited guards, ATP J15 +0.1238 %, ADP +0.1902 %, local plateau.
It is not rerun here.

New elements:

- a genuinely nonlinear constrained optimizer, SciPy SLSQP (already in the
  qualified stack, SciPy 1.17.1, no new dependency), with BFGS curvature and
  a nonlinear merit line search on real ODE evaluations;
- several deterministic starts;
- the 0.006/0.003 derivative check built into gradient preparation.

The LP rounds had none of these three.

## Unchanged scientific contract

The following are all fixed:

- **Model:** the same network (`gem_corrected`), initial state (55 measured J1 values plus latent entries), Km, transport, H = 0.58, availability threshold 1e-3 mM, native transport and clamped pH.
- **Search space:** the same 14 groups and 17 capacities. AK and NDPK forward/reverse stay paired.
- **Boxes:** the original factor boxes.
- **Guards and objective:** the same J4/J8/J11/J15 guards, 84 feasibility constraints, historical fixed-reference metrics and reserve, and the same absolute ATP/ADP J15 log-minimax objective.
- **Integrator:** every evaluation goes through `run_corrected_vmax.evaluate`, i.e. strict Radau rtol 1e-8 / atol 1e-12, bounded Jacobian minimum 1e-15 mM, max_step 0.05. Accepted, dense and order-4/8 quadrature evidence is saved per attempt.
- **Not done:** no guard rebasing, reaction change, latent reinitialization, AK/NDPK ungrouping or bound change.

The runner refuses to start if the configuration or sealed inputs disagree with this contract (`check_invariants`, `load_inputs`).

## Optimization problem

Variables are z = (x_free, t), where x is the vector of log group factors. SLSQP minimises t subject to:

- t - side_k(x) >= 0 for the four sides ATP/ADP lower/upper (the inherited minimax, written as an epigraph);
- -reserve_i - g_i(x) >= 0 for the 84 guards: hard constraints with the full inherited reserve, the same signs as `fla_temporal_vmax.lp_step`;
- the original box (intersected with a shrunken box after failures, see below).

No penalty term is used.

Acceptance of a point is unchanged: `scored().reserved_guards_pass`, i.e. guards <= -0.5 x reserve.

## Starts (registered order) and budgets

| Start | Origin | Distinct ODE limit |
| --- | --- | ---: |
| candidate35 | replay of sealed attempt 35 | 80 |
| working_centre | replay of sealed attempt 1 | 52 |
| seed_objective_descent | candidate35 + 0.05 x direction of steepest descent of the active side (sealed round-3 Jacobian) | 36 |
| seed_guard_relief | candidate35 + 0.05 x relief direction of the 3 most binding guards (same Jacobian) | 36 |
| seed_random | candidate35 + 0.05 x uniform direction, `default_rng(20261112)` | 36 |

The total is 240 distinct search ODE evaluations.

How seeds are built:

- A component that would push a coordinate already at a bound outward is set to zero (PGK at its lower bound, NDPK at its upper bound).
- Seeds are clipped to the box.
- A seed is only a proposal. It competes only if its replay is valid and reserved-feasible; an infeasible seed is recorded and not optimised.

How evaluations are counted:

- Each distinct log-factor vector integrated counts once toward the 240.
- Cache hits are free.
- A batch that would exceed the global or start limit is refused before anything is launched.

## Numerical qualification gate

Attempts 1 and 2 replay candidate35 and the working centre. Each must reproduce the sealed predictions within 1e-12 mM + 1e-9 relative and be reserved-feasible. Bitwise equality is recorded separately.

If the gate fails, the campaign stops before any optimisation (`stop: numerical_qualification_failure`).

## Derivatives

Forward differences use step 0.006 in log units, reversed at the upper bound as before.

If a probe integration fails:

1. the opposite step is tried once;
2. if both fail, that coordinate is frozen for the rest of the start.

No derivative is ever inferred from an invalid integration.

At the first complete Jacobian of each start, the 4 groups with the largest derivative of the active side are re-probed at step 0.003, with the same sign:

- **Compared quantities:** the active side and the 5 most binding guards.
- **Pass criterion:** |d006 - d003| <= 0.25 x max(|d006|, |d003|) + 1e-6 per log unit.
- **On failure:** the group is frozen for that start. No derivative is replaced or averaged.

This check costs at most 4 evaluations per start. It is not a separate campaign.

## Failures, incumbent, stopping

Invalid integrations:

- A failed integration requested by SLSQP returns no value: no fabricated loss, and its row has no score.
- It ends the SLSQP segment. The next segment restarts from the start's best feasible point inside a box of radius 0.5 x the max-norm distance to the failed point.
- Repeated failures shrink this radius further.
- The start stops when the radius would fall below 1e-4, or after 4 segments.

Incumbent rules:

- Only rows the optimizer asked for can update the incumbent: the start point, line-search points and iterates. Finite-difference and check probes never can.
- The row must be valid and reserved-feasible.
- Its objective must be lower than the incumbent's by more than 1e-6, the inherited threshold.
- Infeasible proposals are recorded and inspectable but never selected.

Stop rules:

- **A start stops** on:
  - SLSQP exit (ftol 1e-8, maxiter 15 per segment);
  - two consecutive iterates without a start-best gain above 1e-6 (stagnation);
  - its own budget;
  - the probe-failure radius;
  - the segment limit;
  - no free coordinate left.
- **The search stops** on the global budget or on a failed qualification gate.

SLSQP Lagrange multipliers of each segment are recorded, as indications of which constraints are active. They are not a proof of a global plateau.

## Finalists and validation

The best feasible row of each start is a finalist when it improves on the candidate35 replay by more than 1e-6. Finalists are deduplicated and limited to 5.

Each finalist gets two full-backend integrations with flux audit, strict and ultrastrict (1e-9/1e-13, Jacobian minimum 1e-16). That is at most 10, under the declared ceiling of 12.

A finalist is admissible only if all of the following hold:

- both profiles are valid;
- both pass the reserved guards against their own historical reference;
- paired convergence passes.

The selected point is the admissible finalist with the lowest strict objective. If none exists, candidate35 remains the comparator.

There is no promotion and no claim of optimality or biological validation.

## Resume and checkpoints

Files written during the run:

- `trace.jsonl` gets one fsynced row per completed integration.
- `checkpoint.json` holds the full event log, rewritten atomically after each event.
- A completed folder whose row is missing is reused; an incomplete folder is renamed `*.orphanK` and logged in `orphans.jsonl`, never deleted.

On `--resume`, the deterministic driver replays SLSQP from the cached rows without integrating, checks each regenerated event against the checkpoint (a mismatch stops the run), then continues.

Resume requires unchanged code hashes, configuration, design and seeds.

## Entry points (for Codex, in this order)

```text
python -m pytest qa/test_fla_multistart_vmax.py -q
python scripts/run_multistart_vmax.py --out output/multistart_vmax_2026_11_12
python scripts/run_multistart_vmax.py --out output/multistart_vmax_2026_11_12 --resume   # only after an interruption
python scripts/verify_multistart_vmax.py output/multistart_vmax_2026_11_12 --receipt output/multistart_vmax_verification_2026_11_12
```

Use the system Python with SciPy 1.17.1; the runner refuses any other version. Up to 3 worker processes; no agents.

Maximum integrations are 240 search plus at most 10 validation (ceiling 12), so 250. After an interruption, at most 3 in-flight integrations per interruption may be redone. Wall time is not estimated.

## Outputs

The campaign writes:

- `protocol.json`, `config.json`, `seeds.json`, `replay_reproduction.json`;
- `trace.jsonl`, `search/NNN/`, `checkpoint.json`, `search_result.json` (events, starts, incumbent), `jacobians.json` (every Jacobian with its probe attempts and derivative check);
- `validation/<rank>_attemptNNN/{strict,ultrastrict}/`;
- `summary.json`, `exports/` (objective and constraint traces, concentrations by day, Vmax by finalist, seed status), `manifest.json`.

The verifier re-derives, without any ODE:

- every trace row from its folder;
- the budget and per-start counts;
- the seeds;
- every Jacobian column bit for bit, and the derivative checks;
- the incumbent and start-best rules;
- the finalists;
- the validation quadrature and daily balances, paired convergence and admissibility.

## What a result would and would not mean

A finalist is admissible under historical engineering guards; that is not agreement with the data. Report all four dates, since a late gain can worsen J4/J8.

Given the 0.12-0.19 % gains so far and the absolute gap (ATP J15 about 9e-5 mM against a window starting at 0.757 mM), a large improvement is not expected. A null result is a valid outcome. It would not prove global infeasibility.

Open questions that this search does not touch:

- the observation contract;
- latent stocks;
- borrowed geometry;
- the single donor.
