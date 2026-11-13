# Extracellular release: verifier gate closed (delivery for Codex)

Date 2026-11-12. This applies `tasks/fla_extracellular_execution_gate_2026_11_12.md`. Read/Grep/Glob/Edit/Write only. NOTHING executed: no test, ODE, optimizer, agent, commit or push.

Codex's extraction fix in `scripts/run_extracellular_release.py::qualified_references` is kept unchanged: `metrics.prediction_mM` for the control gate, top-level `prediction_mM` for the campaign validation.

Not changed: objective /2, budgets, algorithm, bounds, Km/J1, historical protocols, sealed verifiers (`verify_corrected_vmax.py`, `verify_multistart_vmax.py`; their patterns were reused, not edited), UI.

## Changed files

- `scripts/verify_extracellular_release.py` (completed). New pure verdict functions, called from `verify()`:
  - **`trajectory_verdict`**, for every attempt and every qualification profile:
    - checks the accepted, dense, q4 and q8 supports: presence, shape (pools + pH), ordered finite times inside J1–J15, clamped pH 7.2, initial identity, and `inspect_support` with the unchanged `negative_tolerance_mM`;
    - also checks the dated predictions against the dense support;
    - a valid result requires all four supports to pass;
    - rejects are classified (`rejected_physical`, `rejected_no_evidence`, `rejected_other`), never repaired, and counted in the receipt.
  - **`jacobian_verdict`**, for every record of `jacobians.json`:
    - each column is rebuilt from the anchor and probe rows at its actual signed step (|step| = 0.006);
    - companion coordinates must be unchanged;
    - a reverse step is accepted only at the upper bound or after a recorded failed forward probe;
    - unavailable or frozen columns must be zero;
    - half-step checks are rebuilt (0.003, same sign, d006/d003, pass flag).
  - **`Components`**: an independent re-implementation of the search vector [U, scaled guards, global cap, EGLC/ELAC focus caps], used by the Jacobian and admission checks.
  - **`incumbent_verdict`**: start-best and global incumbent updates are recomputed from the rows: admissibility, utility, gain log1p(0.001).
  - **`seed_verdict`**: seeds must come from restoration and pass the 84 reserved guards, the global cap, the EGLC/ELAC focus protection and the separation.
  - **`flux_verdict`**, for NEW finalists only:
    - raw and executed order-4/8 integrals are rebuilt from rates, weights and intervals;
    - order 4 vs 8 within the quadrature tolerance;
    - daily species balances, matrix @ executed8;
    - strict vs ultrastrict through `compare_files`, then admissibility.
  - **`export_verdict`**: each exported Vmax value must equal the injected parameter of the ONE selected vector. It also checks the exact 17-member set, the log factors and the parameter hash.
  - **Source and context:** each referenced id resolves either to a trace row (same context) or to context-qualified imported evidence. Unqualified hints never resolve. Restoration records must name admitted seeds; each start's best must be an admissible row equal to its stored vector.
  - **Receipt contents:**
    - `attempt_classes`, `support_points_checked`, `jacobian_columns_rebuilt`, `incumbent_updates`, `new_finalists`;
    - `new_daily_balances_verified`, which is 0 when there is no new finalist: no historical figure is reused;
    - `fallback_qualification: historical sealed receipts, not re-verified here` when a fallback is selected.
- `qa/test_fla_extracellular_release.py`: unchanged.
- `qa/test_verify_extracellular_release.py` (new): 22 adversarial tests, WRITTEN, NOT RUN.

## Adversarial tests

The verifier must reject each case below from the evidence itself, whatever success booleans the campaign recorded and even if the manifest has been resealed:

- **Supports:** negative q8 support with positive dated predictions; missing q4; missing evidence for a valid result; changed initial state; changed pH.
- **Jacobians:** falsified column; falsified probe step; moved companion coordinate; reverse step without justification; falsified half-step check; frozen column carrying values.
- **Flux:** falsified stored integral; falsified daily balance; rates breaking the order-4/8 agreement.
- **Seeds:** focus-inadmissible seed that passes the guards; unseparated seed; seed failing the guards.
- **Incumbent:** a forged update from an inadmissible row.
- **Export:** tampered `vmax_VPK`, an extra non-Vmax key, a shifted log factor (sealed design and candidate35, read only).

Positive controls (clean supports, honest Jacobian, consistent flux, admissible seed, honest export) must pass.

## Commands (Codex)

```text
python -m pytest qa/test_verify_extracellular_release.py qa/test_fla_extracellular_release.py -q
python scripts/run_extracellular_release.py --out output/extracellular_release_2026_11_12
python scripts/verify_extracellular_release.py output/extracellular_release_2026_11_12 --receipt output/extracellular_release_verification_2026_11_12
```

## Note for the campaign

`verify_extracellular_release.py` is listed in the runner's `CODE` hashes. Any further edit to it after the launch blocks resume and verification, as intended.
