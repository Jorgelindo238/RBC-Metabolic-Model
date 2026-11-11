# Latent ribose stock RIB(0) diagnostic at the working center: protocol

Registered on 2026-11-10 before any integration of its arms. This file is
hash-frozen into the archive at launch; status and outcome are reported
only in `tasks/fla_ribose_stock_results_2026_11_10.md` and at the top of
`fla_progress_log.md`. Config: `config/fla_ribose_stock_2026_11_10.json`.
Fresh archive: `output/ribose_stock_2026_11_10/`.

Follow-up to `tasks/fla_guanylate_partition_results_2026_11_10.md`. It
implements the separately recorded RIB(0) latent-initialization feasibility
test foreseen in `tasks/fla_joint_glucose_energy_2026_10_27.md` (line 153)
under its stated conditions: all 55 measured J1 values preserved, any range
labelled diagnostic and not a physiological prior, VRKa, PRPPASe, NDPK and
the adenylate/PEP budgets tracked, no promised ATP rescue.

## Single hypothesis

At the retained working center (absolute attempt 76), the latent ribose
stock RIB(0) = 1 mM, a generic software default, accounts for part of the
early ATP/ADP loss through ribokinase (RIB + ATP -> R5P + ADP).

Fixed kinetics. Not a calibration, not a correction of measured data, not a
biological claim about stored red cells.

## What is known before launch

Read from sealed evidence and the two workbooks, no arm integrated:

- RIB is absent from Sheet1. Its J1 value 1.0 mM is the generic default
  (`src/parse_initial_conditions.py`, lines 66-71). In the network RIB has
  one reaction only, VRKa, and no source: it is a finite stock.
- In the sealed control RIB falls from 1.0 to 0.42 mM at day 1.25, 0.063 at
  day 1.5 and 1.6e-4 at day 2. Executed VRKa integrates to 1.0000 mM on
  J1-J4, i.e. the whole stock, 17.7% of gross J1-J4 ATP consumption.
- `Initial_conditions_JA_Final.xls` lists RIB = 0.0023 mM. That workbook is
  not loaded by the FLA chain and its measurement provenance is unproven.
  It is used here only as a documented alternative convention.
- R5P is also absent from Sheet1 and starts at 1.6110905 mM in the frozen
  vector (not the 1 mM default; JA lists 0.0127). PRPPASe (km_R5P 0.05)
  is therefore saturated in R5P whatever RIB(0) is. R5P(0), PRPP(0) and
  every other latent state stay unchanged: this protocol isolates RIB(0).
- Ribose is not only an ATP cost. R5P enters the non-oxidative pentose
  pathway toward F6P and GA3P, so the stock is also a carbon source for
  later glycolytic ATP. The sign of the net effect is not assumed.
- RIB carries no phosphoryl group: the change adds no phosphoryl inventory.
  It removes pentose inventory, declared per arm below.
- Lesson from the guanylate diagnostic: a lower ATP demand was matched by an
  equal fall in ATP production. Production-side criteria are registered here.

## Arms

Only RIB(0) differs from the frozen J1 vector.

| Arm | RIB(0) mM | Provenance of the value | Pentose inventory change mM |
| --- | --- | --- | --- |
| control (sealed, not reintegrated) | 1.0 | generic software default | 0 |
| JA_historical | 0.0023 | historical JA workbook, unproven as a measurement | -0.9977 |
| intermediate_diagnostic | 0.1 | numerical probe equal to the coded km_RIB default; no physiological meaning | -0.9 |

The intermediate arm exists only to see whether the response is monotone.
Neither value is a physiological bound or prior. Four J1-J15 integrations:
two arms, strict and ultrastrict.

## Frozen contract

Unchanged and hash-verified against `output/vmax_requalification_2026_11_09/`:
all 55 Sheet1 J1 values including the ambiguous B13PG row, HYPX, IMP, every
other latent state including GDP, GTP, R5P, PRPP, ADESUC, the
working-center Vmax, every Km, network gem_corrected -> redox_gssg_abc,
hematocrit 0.58, clamped pH, availability threshold 1e-3 mM, rejection
tolerance -1e-10 mM, guard reference (old historical full control per
profile) and reserve. Recipe: SciPy 1.17.1, Radau, bounded fine Jacobian,
strict (1e-8/1e-12) and ultrastrict (1e-9/1e-13), max_step 0.05 day,
compiled backend.

No retry, clipping, parameter or bound change, optimization, follow-up
calibration, J46 run, promotion or default change.

## Outputs per arm and profile

- ATP, ADP, AMP, RIB, R5P, PRPP, IMP, GMP, GTP, ADESUC, PEP, G6P, F6P at
  J1, J4, J8, J11, J15.
- All original dated guards with reserve and the absolute J15 gap, ATP and
  ADP sides separately.
- Executed integrals on J1-J4, J4-J8, J8-J15 for RKa, PRPPASe, NDPK, ADSS,
  ADSL, AMPD1, AK, AK2, HK, PFK, PGK, PK, HGPRT1; gross ATP production and
  consumption.
- Phosphoryl stocks E_A = 2 ATP + ADP and E_G = GDP + 2 GTP.
- Daily executed balances, quadrature convergence, native/compiled rate
  checkpoints, strict/ultrastrict paired comparison.

## Decision rules, fixed before results

`improves` (per arm, identical to the guanylate protocol): both profiles
numerically valid, paired comparison passes, every original reserved guard
passes in both profiles, worst-profile absolute gap strictly below the
sealed control's, and J15 ATP and J15 ADP each not below the control in
both profiles.

Classification, on the JA_historical arm, in order:

1. `numerical_failure`: a numerical gate or the paired comparison fails.
2. `ribose_stock_effect_supported`: the arm improves.
3. `no_supported_effect`: otherwise.

Flags reported for each arm whatever the class, with dR, dC, dP the J1-J4
reductions versus control of executed RKa, gross ATP consumption and gross
ATP production (ultrastrict):

- `early_only`: J4 ATP above control but the arm does not improve.
- `failed_guards`: list.
- `demand_compensation`: dR > 0 and dC < 0.5 * dR (other consumers took
  over).
- `production_compensation`: dC > 0 and dP >= 0.5 * dC (production fell
  with demand).
- `absolute_J15_targets_reached`: expected false.
- `monotone_response` (campaign level): the intermediate arm's worst-profile
  gap lies between the control's and the JA arm's.

The 0.5 fractions are engineering conventions fixed here. An early ATP rise
alone is not a positive result. Whatever the class: working center and J1
conventions retained, nothing promoted, no calibration launched. A
supported class only authorizes proposing a later protocol to the user.

## Limits stated in advance

Two values do not map a response curve. RIB and R5P are unobserved, so no
arm can be validated against data for them. R5P(0) remains a non-default
latent value and may dominate PRPPASe demand independently of RIB(0).
Results hold for this parameter set, network and positivity policy.

## Verification and closeout

Independent verifier: checks that only RIB(0) differs from the frozen
vector and equals the registered value, that every measured J1 value is
intact, re-verifies each replay, rescored guards and gaps, recomputes the
executed integrals by a separate code path, and re-derives classification
and flags. Seal every folder; manifest last. Targeted tests pass before the
archive is created. The full repository suite is not run.

Files written before launch: `src/fla_ribose_stock.py`,
`scripts/run_ribose_stock.py`, `scripts/verify_ribose_stock.py`,
`qa/test_fla_ribose_stock.py`.
