# Separate Radau confirmation after the preserved BDF diagnostic

The twelve-case BDF diagnostic is closed and unchanged. It reproduced the
three old concentration failures and identical successful controls. Its
first tighter BDF policy did not resolve low-threshold rejection, including
one RHS nonfinite exception. Register this SEPARATE six-integration follow-up
before running it; do not amend the old budget or overwrite its outputs.

Use SciPy 1.17.1 public Radau with its own accepted-step/dense interpolation
API. Preserve accepted states even when a later RHS evaluation throws.
Do not hand-roll an ODE method, alter kinetics or project/clamp a state.

Same center, Vmax/Km, exact J1, pH, all latent states, matrix and volumes.
Thresholds remain 1e-4/1e-5/1e-6 mM; two numeric profiles per threshold:
rtol 1e-8/1e-9, atol 1e-12/1e-13 mM, max_step 0.05 day. The concentration
rejection boundary remains -1e-10 mM. Profile selection is unrelated to fit.

Apply the same accepted/dense/order4/order8 concentration contract, exact
executed daily balances, raw/executed quadrature convergence and native rate
parity, then the previously registered paired-solver and threshold comparisons.
Retain all evidence even if Radau fails. An admissible numerical recipe does
not establish a threshold plateau, biologically fitted constants, or a proof
of nonnegativity at all unobserved times. No default promotion or J46 run.

Use a successor verifier that also handles partial RHS-failure evidence;
the first planned BDF verifier assumed a complete dense array and could not
finish on the captured RHS exception. Its code and failed execution remain
unchanged. No model rerun is needed to verify those twelve saved records.
