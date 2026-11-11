# Fine finite-step confirmation, numerical resolution only

The coarse bounded-Jacobian confirmation has positive early results but
slow unresolved low-pool cases. Its 1e-9/1e-10 mM minimum perturbations can
exceed ADP (approximately 2e-11 mM at tau=1e-6). A forward difference of
a quadratic small-substrate rate then substantially overestimates its
local derivative, even without the former unbounded factor growth.

Register a separate six-case confirmation: the same Radau tolerances,
max_step, thresholds, Vmax/Km/initials and source data, with minimum FD
steps 1e-15/1e-16 mM. Relative step sqrt(eps) and maximum 1e-5 are unchanged.
The finite-difference engine and all state/flux/convergence gates remain
identical. This is a numerical derivative-resolution change, not fitting
the gate or kinetic constants. Retain coarse incomplete records if they
must be stopped for runtime; never use an incomplete result as evidence.

No clipping, relaxed negative tolerance, biological optimization, default
promotion or J46 simulation. Record numerical profiles and every attempt.
