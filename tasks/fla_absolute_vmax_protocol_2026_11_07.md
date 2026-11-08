# Absolute J15 ATP/ADP feasibility protocol

Run a fresh successor to the dated Vmax pilot, using the same network,
half-step control, Sheet1 observations, exact J1 and latent initialization,
14 groups/17 Vmax and factor bounds. All Km and other inputs stay locked.
Keep OPLAH and the opt-in redox/GSSG-ABC projection. No teacher forcing,
ATP injection, source rescaling, new geometry or production promotion.

Nominal targets are the actual J15 ATP and ADP observations. A two-sided
absolute interval uses precisely the inherited working scale at J15:
5% of the J1/J4/J8/J11/J15 median plus 20% of the J15 observation. This
engineering interval is not a measured SD, confidence interval or assay
calibration. Preserve the previous dated PEP/G6P/F6P/AMP residual caps,
canonical nonadenylate trajectory guards, zero-band and adenylate log
guards. Require at least the previous 0.1% reference-relative adenylate
log-error gain at every date, not an average over dates.

Minimize the maximum over both pools and both interval sides of
log(lower/prediction) and log(prediction/upper) at J15. The absolute target
is reached only when this maximum is nonpositive AND all temporal guards
pass. A lower positive score only indicates movement toward the target.

Start from the previously admitted dated vector. Reintegrate the fixed
reference and this start; add two deterministic probes from this start
toward the rejected old J4 direction. Four finite-difference trust-region
LP rounds use the previous difference step, radius, guard reserve and
five backtracking fractions. Only actual ODE evaluations can be accepted.
Cap the total at 80 attempts, including the control and start, matching
the preceding budget. Preserve failures and rejected candidates. Select
the lowest absolute score among all actually sampled guard-feasible rows.

Use free original-rate J1-J15 strict/ultrastrict replays of the reference
and selected candidate, executed-flux quadrature and convergence tests.
Verify all dated caps and reconstruct the absolute score and intervals
independently. Keep target attainment separate from numerical admission.
No J46 run, held-out claim, global optimum or global infeasibility claim.
