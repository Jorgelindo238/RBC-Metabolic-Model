# Corrected-solver Vmax continuation (registered before execution)

User authorization: recalculate sensitivities with the corrected solver, then
resume Vmax-only optimization under the same multi-date constraints.

- Parent: sealed vmax_requalification_2026_11_09, historical working centre.
- Same 14 grouped Vmax coordinates (17 capacities), bounds, network, J1, Km,
  H=0.58, threshold 1e-3 mM, native transport and clamped pH. No new data.
- Same J4/J8/J11/J15 guards, original aliases, 1% working allowance, pointwise
  PEP/G6P/F6P/AMP, adenylate/date-gain guards and guard reserve. Guard caps
  continue to use historical fixed-reference metrics, not the new centre.
- Objective remains absolute ATP/ADP J15 log minimax with the inherited bands.
- Strict Radau rtol1e-8/atol1e-12, bounded Jacobian minimum1e-15, max_step0.05.
  Sensitivities use one-sided log step0.006, reversed at the upper bound.
- Four trust-region LP rounds with the inherited radii and backtracking.
  At most80 search integrations; three numerical worker processes, no agents.
- Full accepted/dense/order4/order8 concentration evidence retained per attempt.
  Failed integrations cannot yield a sensitivity or accepted optimizer step.
- Finalist: two full-backend replays, strict and ultrastrict (1e-9/1e-13,
  Jacobian minimum1e-16), daily executed balances and quadrature checks,
  paired convergence, original guard re-evaluation, independent verification.
- No automatic production promotion, J46 extrapolation or claim of global
  optimum. User-engine v2 stays unqualified and is not silently substituted
  for the already qualified historical solver path in this scientific search.
