# Temporal Vmax-only calibration protocol

Use the verified opt-in RBC-GEM redox/GSSG-ABC projection with OPLAH retained.
The matched reference is that same projection with the original half-step
Vmax. The preceding J4 Pareto vector is a diagnostic direction, not an admitted
start. Preserve the17 positive capacities in14 factor groups and the registered
factor boxes. Every Km, other parameter, zero capacity, source cell, J1 state,
phase volume, transport law and positivity threshold stays locked. No teachers,
observation forcing, source rescaling, resets, new branch or ATP injection.

Fit only actual J4/J8/J11/J15. Working scales derive from J1 and these fit dates;
the same source-specific uncertainty and alias limits apply. Report all55
representations; B13PG/P2G are not independent residuals. B23PG/P3G keep their
nominal non-regression checks. No assay SD, replicate likelihood or independent
donor claim. A structural comparison to native is not an optimization objective.

Minimize the maximum across dates of the ATP/ADP/AMP mean squared log error
divided by its same-date reference. Never select by an average across time.
Use the previous1% engineering allowance for canonical nonadenylate working
MSE and each dated adenylate absolute log error. Additionally cap each PEP,
G6P, F6P and AMP absolute residual at each of the four dates by
`sqrt(reference_error^2 + 0.01*(band^2 + reference_error^2))`.
Zero-band points receive the numerical absolute guard, not a guessed LOD.
For original replay admission, require every guard and >=0.1% log-error gain
at each date at both tolerances. This is not an absolute biological target.

Use real forward finite differences in all14 log coordinates and a bounded
minimax LP proposal with10% of baseline guard slack reserved. Test the actual
ODE at bounded backtracking fractions, keeping at least half of that reserve;
no linearized proposal is accepted without actual guards and objective improvement. Use at most four rounds and
three deterministic warm starts along the prior Pareto direction. Preserve all
attempts, rejected candidates, local solver failure and boundary details.
This is local constrained optimization, not global identification.

Audit the same-network fixed reference and selected feasible point using
strict/ultrastrict original-rate free J1-J15 replays, signed quadrature and
native/fast consistency. No J46 continuation unless separately authorized.
