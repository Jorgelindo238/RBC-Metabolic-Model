# Extracellular release successor (`extracellular_first/2`): corrected delivery for Codex

Date 2026-11-12. This applies `tasks/fla_extracellular_prerun_review_2026_11_12.md`. Read/Grep/Glob/Edit/Write only. NOTHING has been executed: no shell, test, ODE, optimizer, server, agent, commit or push.

**Pre-check:** a Glob found no `output/extracellular_release*` directory, so the pre-registration was revised in place and versioned /2. Version /1 was never run. No archive or scientific constant was modified.

## Changed files

- `config/fla_extracellular_release_2026_11_12.json`: schema /2 and objective `extracellular_first/2`. It records:
  - the log1p utility, its gradient and its utility threshold `log1p(0.001)`;
  - the global worst cap, named as such;
  - the EGLC/ELAC focus protection and its allowance formula;
  - the unit status rule;
  - the transitive cache rule, matched replays and the drift rule;
  - the activation policy.
- `src/fla_extracellular_release.py`:
  - **Utility:** `release_score` (finite at exact fit, `unit_status` field) and `release_gradient` (divides by 1+MSE).
  - **Focus protection:** `focus_metrics`, `focus_caps` (inherited atol/rtol allowances), `focus_ok`; `release_admissible` now includes the focus caps; `ReleaseSearch` takes them as smooth constraints; `restore_seeds` gains an `admit` hook (release admission, not only guard feasibility).
  - **Provenance and cache:** `local_import_closure`, `transitive_evidence`, `context_fingerprint` (design, observations, closure, profile, backend, SciPy), `unit_status`.
  - **Activation:** `activation_permitted`.
- `scripts/run_extracellular_release.py` (rewritten):
  - the transitive cache check, with unqualified archived rows becoming hints;
  - matched replays and the drift check (`blocked_source_drift`);
  - focus caps from the selected fallback;
  - unit status in the inventory, scores, export and release;
  - the activation policy in the release;
  - resume refused if the closure hashes changed.
- `scripts/verify_extracellular_release.py` (rewritten): it recomputes the closure and context, unit status, focus allowances, drift checks, trace rows, budgets, seeds, qualification and the single-vector release. It also asserts that `activation_permitted` refuses the produced release even with an explicit request.
- `qa/test_fla_extracellular_release.py` (rewritten): 33 tests, WRITTEN, NOT RUN.
- `tasks/fla_extracellular_release_protocol_2026_11_12.md` (rewritten), `tasks/fla_application_return_handoff_2026_11_12.md` (activation and units corrected), this note, and `fla_progress_log.md` (entry).

## Objective and acceptance

    MSE_c = mean_{d: b_cd>0} ((x_cd - y_cd)/b_cd)^2
    U     = mean_c 0.5*[log1p(MSE_c) - log1p(MSE_anchor_c)],   dU = mean_c 0.5*dMSE_c/(1+MSE_c)

A new vector is accepted when all of the following hold:

- U_new < U_fallback − log1p(0.001) (utility units);
- 84 reserved guards;
- global cap: every channel's RMSE ≤ the fallback's worst channel (a global cap, not per-species);
- EGLC/ELAC: RMSE, |J15 residual| and |J4–J15 slope error| ≤ fallback + allowance, with δ_d = 1e-5 + 0.01·|x_fallback,d|. The allowances are sqrt(mean (δ/b)²), δ_J15 and (δ_J4 + δ_J15)/11;
- strict and ultrastrict full-backend qualification with paired convergence.

## Tests targeting the review

The new tests cover:

- exact fit of candidate and anchor;
- all-zero-band channel;
- no domination by a near-perfect channel;
- a finite gradient matching central differences, including at exact fit;
- allowance formula;
- focus regression rejected despite a better mean;
- unit status assumed vs recorded;
- dependency drift: a deep kernel change with an unchanged wrapper disqualifies the cache, and recording only the wrapper gives missing evidence;
- the actual archives lack the RHS/positivity hashes;
- a guard-feasible but focus-inadmissible seed is not admitted;
- a provisional release is refused activation even after an explicit click.

Kept: restoration feasibility, Phase-I, separation, shared and per-start budgets, failed-attempt accounting, fixed Km/J1 invariants, Vmax-only directions with AK/NDPK ratios, single-vector export, fallback, blocked status, both validation profiles.

## Consequences for execution

- **Cache:** neither the corrected nor the multistart campaign recorded the RHS/positivity kernel hashes. Their 145 rows will be hints, not cache.
- **Matched replays:** the two fallbacks plus up to 6 of the best hints, at most 8 ODE from the 80 restoration budget. A fallback drift stops the campaign as `blocked_source_drift`.
- **Resume:** any change to code, config or closure sources blocks resume; a new versioned campaign is then required.
- **Seeds:** the focus protections may reduce the admissible seeds; that is reported honestly.

## Unexecuted commands (Codex)

```text
python -m pytest qa/test_fla_extracellular_release.py -q
python scripts/run_extracellular_release.py --out output/extracellular_release_2026_11_12
python scripts/verify_extracellular_release.py output/extracellular_release_2026_11_12 --receipt output/extracellular_release_verification_2026_11_12
```

After these: freeze one verified provisional extracellular vector, or the audited fallback, or the explicit blocked receipt, then move on to the application.

No activation, no default replacement, no claim of biological validation. ATP/ADP remain unmet.
