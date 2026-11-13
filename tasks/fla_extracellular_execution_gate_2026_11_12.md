# Claude: close the execution gate, no algorithm redesign

Codex executed the delivered tests: initial result30 passed/3 failed because
`qualified_references` reads control-gate `prediction_mM` at the wrong level.
Codex fixed only that extraction: control-gate predictions are in
`metrics.prediction_mM`; campaign-validation predictions remain top-level.
Combined extracellular/multistart/corrected tests now65 passed in10.21s.
Keep that fix. No new ODE campaign has been launched by Codex.

The actual `verify_extracellular_release.py` does NOT yet establish all the
claims in the handoff. Its `check_folder` only checks predictions at dates;
Jacobian files and full physical supports are not inspected, and qualification
flux ledgers are compared between profiles without independently rebuilding
integrals/daily balances. Close this gap before scientific execution.

## Required bounded corrections

1. Every attempted trajectory: inspect accepted, dense, q4 and q8 supports,
   times/order/shapes, finite concentrations, initial identity, clamped pH and
   unchanged negative-state policy. Preserve and classify partial rejects;
   never accept a result based only on dated predictions.
2. Reconstruct every stored Jacobian column from the referenced anchor/probe
   records, at its actual signed step and unchanged companion coordinates.
   Verify the half-step checks, unavailable/frozen columns, scalar release
   objective and scaled guard/global-cap/focus-cap components. Check that
   source IDs resolve only to context-qualified imported evidence or actual
   matched replays. Verify seed admission includes focus/global caps as well
   as84 guards and separation. Recompute incumbent/start update rules.
3. For each new qualified finalist, independently reconstruct raw/executed
   quadrature integrals and daily species balances, compare order4/8 and
   strict/ultrastrict. Use existing verifier patterns without changing old
   source files. No new finalist means zero NEW balance verification; label
   historical fallback qualification as historical evidence with its receipts.
4. Verify the exported Vmax values themselves against the selected injected
   parameter vector, not just the parameter hash or log-factor list. No
   activation/default promotion. Keep unit assumptions and ATP/ADP limitations.
5. Add adversarial tests: negative q8 support with positive dated predictions,
   resealed altered Jacobian/probe step, falsified flow integral or balance,
   focus-inadmissible seed, and tampered exported Vmax. A verifier must reject
   each, even if the campaign's recorded success booleans remain true.

No change to objective /2, parameters, bounds, seed strategy, budgets or UI.
Do not turn this into another open-ended design pass. Deliver verifier/tests
and necessary minimal fixes only; keep historical archives immutable. Read/
Grep/Glob/Edit/Write ONLY: no shell, tests/code/ODE/optimizer execution, agents,
servers, installs or commit/push. Codex runs tests and launches the already
defined bounded restoration/search/release once these gates pass.
