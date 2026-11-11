# Integration failure instrumentation and numerical confirmation

Status: the final fine-Jacobian confirmation passes all six integrations
and all three paired numerical comparisons. No biological optimization
or default promotion has occurred. All Vmax, Km, exact J1,
latent pools, network and volumes remain fixed; rejection stays -1e-10 mM.

## Preserved historical failures

The six instrumented BDF repetitions reproduce the original pass/fail
pattern; all saved states and times of the three successful controls are
bitwise identical to the sealed originals. The old helpers are untouched.

| Historical case | Worst physical pool | Minimum (mM) | Support/day |
| --- | --- | ---: | --- |
| tau=1e-5, strict | O2 | -8.89282912e-10 | order8, J13.29482 |
| tau=1e-6, strict | H2O2 | -1.91426821e-10 | order4, J12.44744 |
| tau=1e-6, ultrastrict | O2 | -1.51985159e-10 | order4, J12.67910 |

The last case also has H2O2 policy violations. ATP and ADP remain positive
on every retained accepted/dense/quadrature support of these three cases.
No physical-support nonfinite value caused the historical three failures.
The ordinary dense sampling grid alone misses a policy violation in the
tau=1e-6 ultrastrict case; accepted-step and quadrature checks are necessary.
At negative witnesses, executed outgoing consumption of the offending
species is zero; the raw derivative is NOT the executed material balance.

## Numerical experiments and provenance

- `output/integration_failure_audit_2026_11_08/`: twelve BDF attempts:
  six reproduction plus six smaller-atol/max_step attempts. Six numerical
  passes, six quarantined records, including one internal RHS exception.
  Its first planned verifier could not handle a missing dense array; the
  partial-safe successor verifies the same saved evidence without reruns.
- `output/integration_failure_decision_v2_2026_11_08/`: authoritative BDF
  verification, 9,492 balances/33,600 quadratures/54 native checkpoints.
- `output/integration_radau_confirmation_2026_11_08/`: separate six-case
  public Radau confirmation; three numerical passes, three internal RHS
  exceptions. Accepted partial trajectories survive those exceptions.
- `output/integration_radau_decision_2026_11_08/`: verifies all six records,
  including 4,746 balances/16,800 quadratures/27 native checkpoints.
- `output/integration_bounded_jacobian_2026_11_08/`: coarse finite-step
  confirmation. Three cases completed and passed; three costly unresolved
  cases were deliberately stopped. `interruption.json` and
  `partial_manifest.json` preserve the incomplete archive. No claim may be
  made for those three incomplete cases; it is not a complete campaign.
- `output/integration_fine_jacobian_2026_11_08/`: separate six-case final
  confirmation, all numerical gates and all paired comparisons pass. Same
  Radau profiles and biology, finer derivative sampling; no change to the
  concentration rejection boundary. Independent receipt:
  `output/integration_fine_jacobian_decision_2026_11_08/`.

The budgets are separate: 12+6+6+6 attempted integrations, not twelve
integrations silently retried. The coarse stopped cases are incomplete,
not biological failures or successes. No rejected state is repaired or
used for flux-validation admission.

## Jacobian failure mechanism

Some failed INTERNAL evaluation states contain ELAC=inf and perturbations
near 1e307 in weak/zero-sensitivity columns, while the last accepted Radau
state is finite. They are numerical Jacobian samples, not observed RBC
concentrations. Internal Newton/Jacobian proposals never define the physical
concentration admission decision.

Inspection of installed SciPy 1.17.1 shows persistent sparse-num_jac factor
growth when derivative differences stay small, without a finite upper cap.
A constant-RHS stress test reproduces a nonfinite sampling attempt at call
317 (largest finite sample about 1.49e308); the exact Jacobian is zero.
The explicit bounded callback performs 400 calls with exact zero Jacobians
and no overflow. Receipt:
`output/integration_failure_validation_2026_11_08/constant_column_jacobian_stress.json`.
This explains a specific class of numeric rejection, not every historical
calibration problem and not the biological ATP deficit.

`BoundedJacobian` uses SciPy's existing sparse finite-difference/coloring
engine, with fixed finite perturbations instead of persistent growth.
No model state, rate, reaction, sparsity column or initial value is clipped
or removed. Its private SciPy helper is release-specific and is tested on
the installed 1.17.1 runtime. The coarse 1e-9/1e-10 mM step floors can
overestimate derivatives of very small quadratic substrates. The separate
fine confirmation uses 1e-15/1e-16 mM floors, keeping sqrt(eps) relative
steps and a 1e-5 cap. These are numerical derivative resolutions, not Km.

## Safety and scope

`fla_integration_diagnostics.py` records accepted/dense/order4/order8
species/time/minimum evidence and fails closed before flux admission.
`fla_stepper_diagnostics.py` uses public SciPy BDF/Radau stepping and dense
interpolation; it also retains accepted history after a later RHS failure.
`verify_recorded_integrations.py` handles complete and partial evidence.
Internal nonfinite arrays stay in NPZ evidence; JSON marks missing/nonfinite
values explicitly, without imputation.

190 targeted tests pass, including a bitwise BDF wrapper control, rejected
dense minima, partial RHS failure, unbounded-column stress prevention, and
small-substrate derivative resolution. Mathematical nonnegativity for every
continuous-time point is not claimed; negative values within policy must
still be reported. No J46 continuation or biological calibration is run.

## Final numerical recipe and remaining limit

The tested optional recipe is public Radau with max_step=0.05 day,
rtol=1e-8/1e-9 and atol=1e-12/1e-13 mM. The sparse bounded Jacobian uses
minimum sampling steps 1e-15/1e-16 mM for concentration coordinates, a
sqrt(eps) relative step and maximum step 1e-5. The pH state is clamped;
its numerical perturbation is not a concentration measurement or a pH fit.
Every accepted/dense/order4/order8 support passes the unchanged negative
criterion. All daily executed balances and native/fast parity checks pass.

| Availability threshold (mM) | Paired numerical result | ATP J15 ultrastrict (mM) | ADP J15 ultrastrict (mM) |
| ---: | --- | ---: | ---: |
| 1e-4 | Pass | 1.05761787e-5 | 3.83871971e-8 |
| 1e-5 | Pass | 1.37984511e-6 | 1.52337969e-9 |
| 1e-6 | Pass | 1.94703064e-8 | 1.98942583e-11 |

The worst final checked concentration is O2=-3.80748e-12 mM, well above
the unchanged -1e-10 boundary but not mathematically nonnegative. ATP and
ADP are positive on the retained physical supports. Internal numerical
proposals are a different category and are not asserted to be positive.

The three previously complete BDF controls agree with the final Radau
backend under all inherited and focused comparison criteria. Final
independent reconstruction checks 9,492 daily balances, 33,600 quadrature
values and 54 native rate checkpoints. Across the three completed campaign
archives, 23,730 balances, 84,000 quadratures and 135 native checkpoints
are reconstructed; the incomplete coarse archive is excluded from those
totals. Fine-step minima and cross-backend comparisons are also exported
in `output/integration_failure_validation_2026_11_08/`.

No threshold plateau is established: both solvers are resolved, but the
adjacent thresholds still disagree. Nominal experimental ATP/ADP at J15
remain approximately 1.0138273/0.45063976 mM; neither target is rescued.
The Jacobian repair removes a demonstrable numerical failure mode, not
the underlying biological mismatch or every historical calibration issue.

Next execution: first certify the unchanged working-threshold control with
this optional numerical recipe, then requalify the previously numerically
rejected Vmax candidates at that SAME threshold and original metabolic
guards. Preserve Km and source values; do not choose a threshold for better
fit or reopen a broad optimization before reviewing the requalified set.
