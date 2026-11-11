# Instrument rejected integrations before any calibration

Fresh successor to the fixed-parameter availability-threshold audit. Do not
edit the old integration helpers, source data, source/hash receipts or archived
failure flags. Keep every Vmax and Km, exact J1 and latent states, pH, network,
transport and phase volumes fixed. The negative criterion stays -1e-10 mM.

Stage A: repeat the six original BDF settings at thresholds 1e-4/1e-5/1e-6
mM and strict/ultrastrict profiles. Preserve accepted states, the original
dense sampling grid, and states at order-4/order-8 accepted-step quadrature
nodes BEFORE accepting or rejecting a trajectory. Record per-species finite
minima, times and support indices, negative/below-policy/nonfinite counts,
first sampled policy violation, solver diagnostics and internal-RHS witnesses.
Internal Newton/Jacobian proposals are not accepted physical states and do
not define the concentration admission decision. Nonfinite JSON values are
represented by null with an explicit nonfinite classification, not imputed.

Capture raw/executed contributions at each support's worst finite state when
possible. This is forensic evidence, not permission to calibrate rejected
states. Rate-audit evidence is produced only after the concentration gate
passes; no clipping, source injection, post-step state repair or pseudocount.

Require the Stage A pass/fail pattern to reproduce the sealed parent, and
the three completed parent controls to agree at rtol=atol=1e-12 on saved
time/states/accepted time/states. Otherwise stop before Stage B and diagnose
the instrumentation. Record exact equality separately from numerical parity.

Stage B, only after that gate: same six cases, BDF, inherited strict/ultrastrict
rtol, atol=1e-12/1e-13 mM respectively, max_step=0.05 day for both. This
tests numerical resolution without changing or relaxing concentration policy.
Total maximum: twelve new integrations, no budget-based or fit-based retry.

Every candidate must pass accepted/dense/quadrature concentration gates,
raw/executed quadrature convergence, all daily executed balances, and native
versus fast rate parity. Paired solver comparisons retain the threshold
audit's inherited plus focused nucleotide/integral criteria. Report all55
dated pools and six-pool executed balances, including latent GDP/GTP as
predictions only. Reassess adjacent-threshold comparisons separately; a
working integration wrapper does not prove convergence as the gate shrinks.

No threshold or solver default is promoted, no biological parameter is
optimized, and no J46 continuation is run. Tiny negative values within the
unchanged tolerance are reported explicitly, not called exact nonnegativity.
