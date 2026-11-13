# Multistart Vmax-only SLSQP successor: delivery for Codex review

Date 2026-11-12. Read/Grep/Glob/Edit/Write only.

Nothing has been executed in this tranche: no shell, test, ODE integration, optimizer, server, agent, commit or push. No computation has started. Codex reviews, runs the tests, then the campaign.

The skill `.claude/skills/airbc-vmax-calibration/SKILL.md` and the dispatch `tasks/fla_claude_optimization_dispatch_2026_11_12.md` were read in this same checkout before writing. So were the results, protocol, runner and verifier of `corrected_vmax_2026_11_12`, its sealed archive files, and the SciPy 1.17.1 SLSQP source: constraints receive unclipped x, exceptions from `fun` propagate, and `StopIteration` in the callback halts.

## Files

New:

- `config/fla_multistart_vmax_2026_11_12.json`: preregistered budgets, steps, seeds, stopping rules and invariants.
- `src/fla_multistart_vmax.py`: driver with no ODE and no model import. It contains:
  - `EvaluationStore`: distinct-vector budget, bitwise cache, attempt ledger;
  - `MultistartSearch`: SLSQP epigraph, Jacobians, 0.006/0.003 check, freezing, failure box, incumbent, checkpoint hook, deterministic replay;
  - `joint_seeds`, `select_finalists`, `admissible`.
- `scripts/run_multistart_vmax.py`: runner. Evaluations reuse `run_corrected_vmax.evaluate` (qualified strict Radau, bounded Jacobian, recorded evidence). It also does the replay qualification gate, the strict/ultrastrict full-backend validation, exports and the manifest.
- `scripts/verify_multistart_vmax.py`: independent verifier, no ODE.
- `qa/test_fla_multistart_vmax.py`: 30 tests, written and NOT executed.
- `tasks/fla_multistart_vmax_protocol_2026_11_12.md`: registered protocol.
- `tasks/fla_multistart_vmax_delivery_2026_11_12.md`: this note.

Edited: `fla_progress_log.md` (one entry prepended).

Not touched:

- every sealed archive under `output/`;
- `run_corrected_vmax.py`, `verify_corrected_vmax.py` and every other historical script or source;
- `MM_calibration.py`;
- constants, Km, J1, OPLAH and numerical policies;
- Calibration/Monitoring UI.

## Tests written, not executed

`python -m pytest qa/test_fla_multistart_vmax.py -q` (system Python, SciPy 1.17.1).

The driver tests use an injected analytic evaluator (3 coordinates, 2 sides, 3 guards). They cover:

- **Budget:** cache hits are free; a batch that would exceed the global or start limit is refused before launching; start limits must not exceed the global limit; a trace above budget, duplicated or renumbered is refused; a small start budget stops the start and keeps the feasible incumbent.
- **Constraint signs:** the SLSQP `>= 0` convention for epigraph and guard rows, including the Jacobian; the objective passed to `minimize` is the epigraph variable t (spy on `minimize`), not a penalty; the final incumbent respects the guards with reserve; infeasible rows never update the incumbent; an infeasible start is recorded and not optimised; the registered start order is enforced.
- **Resume:** a full replay from the trace needs zero integrations and reproduces the events; an interrupted run resumes to the identical path; a diverging checkpoint raises; the checkpoint hook sees every event.
- **Derivatives:** Jacobian columns are bitwise secants at 0.006; the 0.003 check runs once per start; a curvature-induced check failure freezes the group; a failed forward probe uses the reverse step; an invalid integration is never scored and shrinks the box.
- **Seeds, finalists, admission:** seeds are deterministic, bounded and do not push outward at bounds; finalists are feasible, improving, unique and capped; admission needs both profiles and paired convergence.

The tests on sealed inputs read files only (no ODE). They check:

- the config against the sealed design (14/17, 84 guards, steps, budgets, start order, every hashed code file exists);
- that seeds and difference probes built from the sealed round-3 Jacobian change only grouped Vmax, inside the box, with the AK/NDPK ratios intact.

Runner helpers tested: truncated trace tail, orphan folder kept aside, reproduction tolerance. A final test checks that the driver imports only json, numpy and scipy.

## Exact execution entry points

1. `python -m pytest qa/test_fla_multistart_vmax.py -q`
2. `python scripts/run_multistart_vmax.py --out output/multistart_vmax_2026_11_12`
3. After an interruption only: the same command with `--resume`.
4. `python scripts/verify_multistart_vmax.py output/multistart_vmax_2026_11_12 --receipt output/multistart_vmax_verification_2026_11_12`

Maximum integrations: 240 distinct search evaluations, plus at most 10 validation integrations (5 finalists x 2; registered ceiling 12). After an interruption, at most 3 in-flight integrations may be redone. Up to 3 worker processes. No wall-time estimate.

## Stopping criteria (all preregistered)

- **Before optimisation:** the candidate35 or working-centre replay fails to reproduce the sealed predictions (1e-12 mM + 1e-9 relative) or is not reserved-feasible. Stop: `numerical_qualification_failure`.
- **Per start:**
  - SLSQP exit (ftol 1e-8, maxiter 15 per segment);
  - stagnation: two iterates without a start-best gain above 1e-6;
  - start budget;
  - probe-failure radius below 1e-4;
  - 4 segments;
  - no free coordinate.
- **Global:** the 240 budget.

The best feasible incumbent is always retained.

## Review points I want Codex to check

1. **Optimizer margin = full reserve.** Constraints use g <= -reserve, as `lp_step` did; acceptance stays g <= -0.5 reserve. If candidate35 has a guard between these two levels, SLSQP starts slightly infeasible for its own constraints and may first restore them. That costs budget but cannot admit an infeasible point.
2. **Budget depth.** 14 groups make one Jacobian cost 14 integrations, so 80 evaluations allow about four SLSQP iterations from candidate35, and 36 about one to two from a seed. This is a bounded local multistart, not a global search.
3. **BFGS memory.** It is lost when a segment restarts after a freeze or a failure. This is documented, not hidden.
4. **Replay reproduction.** It assumes the same machine and SciPy as the sealed run. Exact bitwise equality is recorded but not required.
5. **SLSQP clipping.** SciPy's internal clipping of x to the bounds can warn (`RuntimeWarning`); vectors are clipped to the segment box before evaluation, so the cache key is the evaluated vector.

## What this does not establish

A result admissible under historical engineering guards is not biological agreement. The ATP J15 gap is still about four orders of magnitude. Report all four dates. A null result is valid and does not prove global infeasibility.

Open questions this search does not touch: the observation contract, latent stocks, borrowed geometry, the single donor.

No promotion and no claim of optimality.
