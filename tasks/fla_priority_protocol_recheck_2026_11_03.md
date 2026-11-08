# Recheck of the three priority calibration steps

## Scope and fresh verification

User requested confirmation of the matched objective comparison, integrated
feasibility screen and actual J1-J15 extension, with multiple shooting only if
needed. This is a read-only scientific recheck, not a new optimization. Original
sealed archives are unchanged. Fresh receipts:
`output/fla_priority_protocol_recheck_2026_11_03/`.

- [x] Rerun primary verifier:2299 checks, eight fits, fourteen original ODE replays.
- [x] Rerun independent report verifier:1444 checks,21 analytic certificates,
  six certified LP minima and275 source/comparator rows.
- [x] Rerun objective/observation and balance-certificate QA:32 tests pass.
- [x] Check actual observation times, parameter scope and conditional J15 gate.
- [ ] Multiple-shooting calibration in this campaign: not run; conditional,
  not required merely to mark the already executed extension complete.

## 1. Matched J4/J8 comparison: executed and numerically verified

Archive `output/fla_objective_reformulation_2026_11_03/` contains six fits:
three losses, two common starts, identical22 J4/J8 values from11 pools. Only
vmax_VHK/vmax_VPFK change, with the same primitive bounds. All other kinetic
constants, exact55 J1, latent initialization, phase geometry, native VELAC,
clamped pH, threshold and OPLAH remain fixed. J10 is the integration horizon,
not an extra measurement. Historical13 caps are diagnostics for ALL refits;
the older guarded fit is not the matched NLL control.

| Refitted objective | Mean working channel MSE | Worst working channel MSE |
|---|---:|---:|
| Profiled lognormal NLL |129.687654|1016.534072|
| Normalized residuals |37.494381|343.776200|
| Minimax |68.215816|339.304298|

These are common re-scored metrics, not direct numerical comparisons between
heterogeneous scalar costs. Scales are engineering normalization, not measured
assay SD. Normalized residuals preserve F6P better; minimax worsens its MSE
0.156857 ->339.304 for a small AMP improvement. No biological winner promoted.

## 2. Integrated feasibility: executed, exact nominal balances fail

Six necessary LPs use J8/J15/J46 and eleven training pools or53 canonical
source representations. Eleven-pool minimum working-error multipliers are
0.016542/0.016779/0.023310; canonical53 multipliers0.959227/1.661963/2.804155.
All six EXACT nominal systems are infeasible under their declared matrix and
direction assumptions. Primal witnesses plus analytic lower bounds certify
the relaxed minima to maximum gap2.22e-16. Hypothetical shared adjustments
do not overwrite observations. This does not prove existence of a kinetic ODE
or error in the data; normalization, volume, pool and network hypotheses matter.

## 3. J1-J15 extension: executed and numerically verified

The eleven-pool J15 gate passes its registered multiplier<=1 criterion. Two
continuations, normalized and minimax, use actual J4/J8/J11/J15 values,44 total,
with exact J1 fixed and scales recomputed on this training support only. Both
converge (8/16 objective integrations). Across the matched comparison and both
extensions there are208 actual objective integrations and eight converged fits.
Original strict/ultrastrict replays verify each J10 selection and both J15
continuations at J15/J46: fourteen ODE replays total. The fourteen integrations
are archived prior executions, not new integrations in this recheck.

All original numerical checks pass, including278617 convergence comparisons
and32770 daily executed balances. ATP J46 remains about1.8e-5mM against
nominal0.469757mM. Later exposed observations are not blind validation. These
are completed executions, not a biologically validated calibration.

## Multiple shooting: not silently counted as completed

The current objective-comparison runner has no multiple-shooting optimizer.
Older `diagnose_brodbar_multiple_shooting.py` and `fla_multiple_shooting.py`
implement an observation-reset diagnostic under a different historical setup;
they are not continuous constrained shooting on the current data/model contract.
Their reset trajectories must never be reported as free-ODE predictions.

Convergence alone does not rule out a benefit from multiple shooting. However,
it cannot remove an exact network invariant while enforcing continuity: if
w^T S=0, every ODE segment preserves w^T x, and exact matching of consecutive
end/start states preserves it globally. Resets would bypass that condition.
The identified source/network conflicts therefore remain ahead of using another
optimizer formulation to seek an apparent fit. No multiple-shooting fit or
duplicate HK/PFK optimization is launched by this recheck.

## Current next task remains separate

The later coverage/sensitivity pass is already complete; see
`tasks/fla_coverage_adenylate_sensitivity_2026_11_03.md`. Its proposed small
VSAM/PGK interaction screen is NOT run here. New coverage branches remain off
until kinetics/latent-stock/pool contracts are justified. A future genuine
multiple-shooting implementation must share kinetics across segments, keep
exact J1, report continuity defects and replay its candidate freely from J1.

A first independent receipt write found its new parent directory absent; the
primary verifier subsequently created it and the independent check was rerun
successfully. No scientific input or sealed verifier was changed to fix this.
