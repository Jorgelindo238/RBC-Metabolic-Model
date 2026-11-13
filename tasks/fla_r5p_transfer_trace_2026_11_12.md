# R5P(0): transfer from an unpromoted diagnostic to the current centre

Date 2026-11-12, tranche following lots A/B/C. Read-only trace with file
tools; nothing executed, no hash recomputed, no value changed. Complements
`tasks/fla_latent_inventory_contract_2026_11_12.md` and
`config/fla_latent_inventory_contract_2026_11_12.json`.

## Result

R5P(0) = 1.6110905450195272 mM in every current trajectory is the value
solved by the 2026-08-11 diagnostic candidate
`constrained_balanced_teacher__v6pgd_0.9000x`, which the log records as
"diagnostic only, do not replace the production initialization". It
reached the current centre by being carried, unchanged, through five
scripted steps, each of which copied the previous frozen state. No step
re-examined it, and no step promoted it. Its biological provenance is NOT
resolved by this trace.

## Chain (code reading, with lines)

| Step | Date | File / function | What happens to R5P |
| --- | --- | --- | --- |
| 1 | 2026-08-11 | `Simulations/brodbar/hermes/v6pgd_constrained_transition_refinement_46d/diagnostic_candidates.json` lines 30-35; `summary.json` line 1268 `selected_candidate` | Seven latent PPP states (GL6P, RU5P, R5P, X5P, E4P, S7P, GA3P) solved together at `vmax_V6PGD` = 9.0 under the balanced-teacher formulation. R5P = 1.6110905450195272. Log decision: robust diagnostic point, not promoted. |
| 2 | 2026-08-11 onward | `scripts/audit_b23pg_balance_qss_context.py`, `_build_state_contract`, lines 106-129 | Base state = `MM_calibration.load_initial_conditions()`, then the seven saved latent states of the step-1 candidate are written over it (`_state_with_saved_latent`, `scripts/audit_atp_transition_v6pgd_ppp_context.py` lines 113-121), then B13PG/B23PG from the B13PG screen. |
| 3 | 2026-08 | `scripts/audit_atp_partition_vdpgm_3x_qss_b13pg.py`, `_build_contract`, lines 85-105 | Takes the `qss_1.000x` state of step 2 unchanged. |
| 4 | 2026-08/09 | `scripts/screen_amp_nucleotidase_fixed_purine.py`, `_build_anchor`, lines 105-116 | Takes the step-3 state unchanged; changes parameters only. |
| 5 | 2026-10-05 | `scripts/audit_ppp_constraints_and_numerics.py`, `_fixed_context`, lines 83-102, and line 379 | Rebuilds the step-4 state, checks it against the cached J1 row of `vampd1_storage_decay_full_ode_J1_J46` to 1e-12, writes `output/ppp_numerical_audit_2026_10_05/fixed_initial_state.csv` (R5P line 8). |
| 6 | 2026-10-06 | `scripts/run_exploratory_energy_sensitivity.py`, `measured_initialization`, lines 53-76 | Overwrites the 55 Sheet1 J1 pools; every other pool, R5P included, kept as `unchanged_frozen_unmeasured_pool` (`initialization_inventory.csv` line 59). Saved as `frozen_initial_state.npz`. |
| 7 | 2026-11-09 to 11-11 | `output/vmax_requalification_2026_11_09/` and successors, `initial_context` = the step-6 archive | Carried unchanged; `levels_by_day.csv` of the AK/PEPase archive shows R5P = 1.6110905450195272 at day 1 in every arm. |

Not proven by this trace: that steps 2-6 ran exactly the code read today
(only the archived hashes could prove it, and none was recomputed); that
the six other PPP states in the current centre are still the step-1 values
(only RU5P was compared, line 7 of the CSV, and it matches); and that the
step-6 overwrite did not touch any of the seven (none of them is among the
55 measured channels, so by reading it did not).

## Two roles that must stay apart

| Role | R5P = 1.6110905 is... | Allowed use |
| --- | --- | --- |
| Historical comparator | the value every sealed campaign since 2026-10-06 used | Reproducing or comparing against sealed trajectories. Must be kept exactly. |
| Eligible biological initialization | NOT established | It came from a teacher-balanced solve at a non-promoted V6PGD capacity, under a different kinetic centre and a QSS-B13PG context that the current centre no longer uses (B13PG is back to the duplicated Sheet1 row). It cannot be offered to a user dataset as a default, and the successor engine does not load it. |

Consequence: a user calibration must declare its own R5P(0) with its own
provenance (status `latent_declared`); a run that wants to reproduce the
historical centre must declare the same value with provenance "historical
comparator, unpromoted 2026-08-11 diagnostic", and that run is a
comparison, not a biological initialization.

## Not done

No value changed, no archive touched, no execution.
