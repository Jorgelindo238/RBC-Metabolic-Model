# Fixed-parameter reaction-consistent threshold sensitivity

Use the last PGK/NDPK center, with the exact same Vmax, every Km, kinetics,
network, phase volumes, pH, all55 Sheet1 J1 entries, latent states and data.
Keep GDP/GTP J1 at their locked values. Do not refit, reset, rescale,
force observations, inject ATP or switch to legacy positivity.

Compare positive availability thresholds 1e-3, 1e-4, 1e-5 and 1e-6 mM.
Use the inherited strict and ultrastrict solver profiles, negative tolerance,
quadrature orders, closure and native/fast parity checks unchanged. Reuse
the two sealed center replays at 1e-3 after hash/parameter checks. Attempt
six new original-rate free J1-J15 replays. Preserve failures; do not retry
with looser positivity or alter a threshold after seeing its fit.

Distinguish three decisions:

- Numerical validity at each threshold: accepted/dense/quadrature checks,
  daily executed balances, quadrature convergence and native rate parity.
- Solver convergence at fixed threshold: inherited state/raw/executed
  comparisons AND the focused checks below.
- Threshold convergence: adjacent-threshold comparisons at BOTH solver
  tolerances, not a fit score. Require the FINAL TWO adjacent pairs to pass
  all comparisons and their involved solver/numerical checks before calling
  a plateau within this registered interval. This is not a proof of the
  limit at zero, nor an automatic threshold promotion.

Inherited comparisons use atol=1e-5 mM and rtol=1%. Additionally compare
ATP/ADP/AMP/GDP/GTP/GMP at actual J4/J8/J11/J15 with atol=1e-10 mM and
rtol=1%, and every daily executed reaction integral with atol=1e-8 mM and
rtol=1%. These focused numerical bounds are not experimental errors or
pseudocounts. Zero values remain zero, and failed comparisons are reported.
No averaging across metabolites or dates may hide an individual failure.

Report all55 dated predictions, absolute ATP/ADP targets, the same inherited
metabolic guards, raw/executed PGK/PK/NDPK and six-pool executed balances.
For the guard diagnostic ONLY, retain the fixed historical same-network
control at 1e-3, rather than resetting the reference to each new threshold.
Guard/target improvement never selects the numerical threshold. GDP/GTP
remain latent; H denotes ATP+0.5 ADP, not pH.

No J46 continuation, extended threshold grid, parameter optimization,
default change or biological validation claim is authorized by this audit.
