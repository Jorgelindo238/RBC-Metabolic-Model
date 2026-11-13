# Latent inventory contract: ADO, EADO, RIB, PRPP (R5P as context)

Date 2026-11-12. Lot A of the mandate of that day. Contract only: no
integration, no state, bound, Km or constant change, no archive written.
Machine-readable form: `config/fla_latent_inventory_contract_2026_11_12.json`.
Tools used: file reading and text search only. Nothing was executed and no
hash was recomputed.

Follows the "next gate" of `tasks/fla_purine_ribose_results_2026_11_11.md`.

## What the contract fixes

| Pool | Compartment | J1 value (mM, own phase) | Bag amount, conditional on H = 0.58 | Status | Bounds | Change allowed |
| --- | --- | --- | --- | --- | --- | --- |
| ADO | intracellular | 1.0 | 0.58 mmol/L bag | latent, convention, provenance unresolved | none | not in the reference state; registered reversible diagnostic only |
| EADO | extracellular | 1.0 | 0.42 mmol/L bag | latent, convention, provenance unresolved | none | same; never tested |
| RIB | intracellular | 1.0 | 0.58 mmol/L bag | latent, convention, provenance unresolved | none | same; stock size already tested on 2026-11-10 (`no_supported_effect`) |
| PRPP | intracellular | 1.0 | 0.58 mmol/L bag | latent, convention, provenance unresolved | none | same; never tested alone |
| R5P (context) | intracellular | 1.6110905450195272 | 0.934433 mmol/L bag | latent, solved diagnostic initialization | none | never overwritten by a generic value |

Units are the nominal model unit of the frozen design. Geometry H = 0.58,
Vi = 0.58, Ve = 0.42 L per L of bag is the borrowed working geometry
(`hematocrit_status: borrowed_working_geometry_not_matched_Bordbar_donor`
in the archived design), so bag amounts are conditional, not measured.

## Evidence chain actually read

1. `output/ak_pepase_2026_11_11/execution_design.json`: `initial_day` 1.0,
   `initial_context` =
   `output/exploratory_energy_sensitivity_J1_J4_2026_10_06`, hematocrit 0.58
   with the borrowed-geometry status.
2. `.../exploratory_energy_sensitivity_J1_J4_2026_10_06/initialization_inventory.csv`:
   ADO (line 68), EADO (108), RIB (104), PRPP (75) are
   `unchanged_frozen_unmeasured_pool`, no source cell, prior and initial
   value 1.0, `independent_observation` False. R5P (line 59) is the same
   class with 1.6110905450195272. Its contract states the initialization as
   exact Sheet1 J1 for the 55 measured pools and unchanged frozen
   unmeasured pools, with `output/ppp_numerical_audit_2026_10_05` as fixed
   context.
3. `output/ppp_numerical_audit_2026_10_05/fixed_initial_state.csv`: same
   five values (lines 28, 90, 84, 43, 8).
4. `output/ak_pepase_2026_11_11/observations.json`: no key for ADO, EADO,
   RIB, PRPP or R5P among the 55 channels (ADE, EADE, INO, EINO, HYPX,
   EHYPX and SAH are present).
5. `output/ak_pepase_2026_11_11/levels_by_day.csv`: PRPP 1.0 and R5P
   1.6110905450195272 at day 1 in every trajectory.
6. `src/parse_initial_conditions.py`, lines 66-87: every model pool starts
   at 1.0 with source `generic_1mM`; a workbook row overrides it; under
   `legacy_experimental_alias` an E-prefixed pool takes the intracellular
   row and conversely; the result is floored at 1e-6.
   `src/MM_calibration.py`, line 1524: `load_initial_conditions` uses that
   policy by default and takes no data argument.
7. R5P: `Simulations/brodbar/hermes/v6pgd_constrained_transition_refinement_46d/diagnostic_candidates.json`,
   lines 30-35, candidate `constrained_balanced_teacher__v6pgd_0.9000x`,
   gives R5P = 1.6110905450195272 together with GL6P, RU5P, X5P, E4P, S7P
   and GA3P. The 2026-08-11 log entries record that candidate as diagnostic
   and not promoted.

## Reading

- ADO, EADO, RIB and PRPP are not measured in this panel. Their archived
  value 1.0 coincides with the loader's generic default, and by reading the
  loader no other rule could have assigned them. That is an inference from
  code, not a re-execution: the contract therefore records
  `generic_1mM_assignment_proven: false` and the status "provenance
  unresolved" next to "convention".
- R5P is not a generic value. It is one of seven pentose-phosphate latent
  states solved together by an August diagnostic initialization that was
  explicitly not promoted, and it has been carried in every frozen context
  since. Changing it alone would break the set it was solved with.
- No pool has a justified bound. The repository holds no measurement, no
  source range and no conservation relation tying any of them to a measured
  pool. The values used on 2026-11-10 for RIB (0.0023 from the historical
  workbook, 0.1 as a probe) are not bounds. The loader floor 1e-6 is
  numerical.
- The purine audit shows these stocks matter in the modelled budget
  (extracellular ADO 0.42 mmol/L bag almost fully imported; RIB 0.58
  consumed by J4 at a cost of 0.58 ATP; PRPP stock supplying more than half
  of net salvage withdrawal). That is why they need a contract; it does not
  make any alternative value more correct.

## What is allowed

- Reference and production states: no change to any of the five pools.
- A registered, reversible, user-authorized sensitivity diagnostic in a
  fresh dated archive may vary ADO, EADO, RIB or PRPP, with declared values
  and their provenance, the sealed control as revert branch, measured J1
  untouched, and bag amounts reported with distinct volumes.
- Never: zero as a default replacement, a scenario value reported as
  physiological, R5P overwritten with 1.0, or a relabelling of any of these
  pools as measured.
- RIB(0) size alone was already tested (`no_supported_effect`); a new RIB
  diagnostic needs a different question.

## Blockage, stated exactly

- `.xlsx`, `.xls` and `.npz` files cannot be opened with the permitted
  tools. Absence of the five pools from Sheet1 is therefore established
  through the archived 55-channel observations and the inventory table,
  not by reopening the workbook. The historical-workbook values of ADO and
  EADO are unknown here.
- The path from `fixed_initial_state.csv` back to the loader runs through
  `scripts/audit_ppp_constraints_and_numerics.py` (`_fixed_context`, lines
  83-102), `scripts/screen_amp_nucleotidase_fixed_purine.py`
  (`_build_anchor`, line 105) and
  `scripts/audit_atp_partition_vdpgm_3x_qss_b13pg.py` (`_build_contract`,
  line 85). The last function was not read to its end and nothing was
  re-executed. Proving that each archived 1.0 is the loader default needs
  one execution of the loader with its provenance map, compared pool by
  pool with `fixed_initial_state.csv`.
- No hash was recomputed.

## Not done

No integration, no sensitivity run, no change to any archive, source file,
constant, Km, measured J1 value, OPLAH or numerical policy.
