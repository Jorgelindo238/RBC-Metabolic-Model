# Bounded-Jacobian confirmation, separate from the first two campaigns

Preserve the twelve BDF attempts and six automatic-Jacobian Radau attempts.
Their rejected internal samples include geometric-growth perturbations up
to 1e307 and ELAC=inf although the last retained accepted Radau state is
finite. The installed SciPy 1.17.1 sparse num_jac increases persistent FD
factors on columns with tiny differences and has no finite upper cap.

Register six more integrations, the same three thresholds and fixed
biological vector. Use Radau at the same two profiles as its preceding
confirmation, but supply a stateless sparse Jacobian callback. It calls
SciPy approx_derivative with explicit forward steps: max(sqrt(eps)*abs(x),
floor), capped at 1e-5 mM. Floors are 1e-9/1e-10 mM for strict/ultrastrict.
The callback does not grow steps, clamp states, alter RHS, remove a column,
change network sparsity or perturb initial conditions. SciPy's existing
finite-difference/coloring implementation remains the numerical engine.
Reject nonfinite/unrepresentable samples. Record callback counts and bounds.

Retain all earlier concentration, quadrature, balance, parity, paired-solver
and threshold-convergence gates. The negative boundary remains -1e-10 mM.
All Vmax, Km, J1 and volumes stay fixed. This is numerical confirmation,
not threshold selection by fit or biological calibration. No default
promotion, parameter optimization, state repair or J46 run.
