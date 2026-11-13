---
name: airbc-vmax-calibration
description: Prepare constrained Vmax-only calibration and stiff-ODE verification for AIRBC, preserving measured initial states, compartment volumes and sealed evidence.
---

# AIRBC Vmax Calibration

## Start From Evidence

Read `tasks/fla_current_tasks.md` and the latest results it links. For the
2026-11-12 continuation, read `tasks/fla_corrected_vmax_results_2026_11_12.md`,
`scripts/run_corrected_vmax.py` and `scripts/verify_corrected_vmax.py`.
Check the actual archive before claiming a result. Completed optimization,
numerical validity, guard admissibility and biological validation are distinct.

## Preserve the Scientific Contract

- Fit Vmax only; keep Km, initial state and transport constants fixed. Current
  fourteen groups contain seventeen capacities; paired AK/NDPK ratios remain
  fixed unless a separate hypothesis is explicitly authorized.
- In the historical energy profile retain J4/J8/J11/J15 constraints, guard
  caps/reserve, alias exclusions and absolute ATP/ADP J15 targets. A separately
  requested extracellular profile must have its own versioned objective and
  scope: unresolved ATP is a disclosed limitation, not a concealed success.
  Never rebase caps on a candidate or silently relax acceptance constraints.
- Keep measured initial values exact and latent values explicitly labelled.
  Intracellular and extracellular mM refer to different volumes. H=0.58 is
  borrowed geometry, not a matched donor measurement. Do not merge donors.
- Relative data are not absolute concentrations. Teacher-derived fluxes are
  not independent extra observations of their source concentrations.
- GEM is structural evidence, not automatic permission to alter reactions.
  Do not delete OPLAH. Proteomics is not direct active-Vmax measurement.

## Numerical and Search Discipline

Use the archived qualified Radau/bounded-Jacobian recipe at the same availability
threshold; inspect its actual source rather than inventing a solver variant.
Retain accepted, dense and quadrature supports; reject physical-support failures
without clipping, repair or fabricated scores. Do not confuse internal Newton
probes with accepted trajectory states. Preserve absolute kinetic storage time.

Optimizer proposals need nonlinear ODE evaluation. Parameter sensitivities
must not be inferred from invalid integrations; check differencing noise and
bound direction. Express optimizer tolerances and budgets explicitly. Cache
identical vectors. A local plateau does not establish global infeasibility.

Finalists require strict/ultrastrict full-backend validation, executed-flux
balances and independent guard reconstruction. A feasible candidate that
improves late ATP may still worsen an early date; report all dates.

## Feasible Starts and Extracellular Release

The 2026-11-12 SLSQP run optimized only two starts; its three additional seeds
were infeasible and discarded. Do not call this five explored basins. Restore
seeds explicitly before optimization: bounded log-space directions with
backtracking, then an optional Phase-I constraint-violation minimization. Phase-I
violation scores do not replace hard final constraints or biochemical fit scores.
Demand nonlinear replay feasibility and meaningful seed separation; duplicates
and near-identical seeds are not independent starts. Count restoration ODEs.

For extracellular selection use the real observed external-pool registry, the
same dataset/geometry/J1/horizon and one coherent parameter vector. Never assemble
the best species curves from different vectors. Compare normalized per-channel,
worst-channel and dated residuals; qualify means, units and uncertainty. Export
the best admissible available profile as provisional with its exact scope and
open intracellular limitations. A bounded failure to improve must still return
the audited fallback and allow application delivery; do not block that delivery
on another unbounded energy-calibration campaign.

## Delivery and Permissions

Make successor modules and fresh output directories. Never overwrite sealed
archives or their historical source files. Do not edit MM_calibration.py or
active scientific defaults to launch an experiment. No automatic promotion.
Keep dirty user changes. Do not install packages or launch agents implicitly.

The dispatch prompt defines execution permission. In a code-preparation
handoff, use file tools only, leave tests unexecuted and provide explicit entry
points for Codex to execute through its own tools. Do not run shell commands,
code, servers, optimizations, commits or pushes from that restricted handoff.

Return exact changed paths, tests actually run versus merely written, objective
and all dated guard outcomes, numerical failures, selected Vmax changes,
provenance, and remaining biological gaps. No promise of calibration success.
