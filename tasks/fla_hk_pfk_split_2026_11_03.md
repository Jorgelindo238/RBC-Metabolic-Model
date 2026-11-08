# Reversible HK/PFK dissociation - 2026-11-03

## Registered question

Does freeing the two investment capacities independently improve the same
22-value J4/J8 likelihood beyond a paired one-coordinate fit, while preserving
all thirteen original guards? This is a conditional, local nested-model test,
not a seven-coordinate reoptimization or a claim of biological validity.

## Frozen scope

- Parent: `output/broad_protected_joint_restoration_2026_11_03/`.
- Only `vmax_VHK` and `vmax_VPFK` can change. All other parent kinetics and
  GLUT constants remain fixed. Keep exact 55 source J1 and all latent pools,
  Hct0.58, clamped pH, native VELAC, OPLAH, threshold0.001mM and positivity.
- Original primitive factors [0.02,1.0], not multiplied onto fitted capacities:
  HK [0.1,5.0] and PFK [0.0509886129444,2.54943064721943] mM/day.
- Identical eleven J4/J8 RMSE guards plus pointwise PEP J4/J8. Caps unchanged;
  an inner solver target reserves 1% of the existing numerical allowance.
- Nine fixed screens: each capacity at factor1.05 or its reciprocal, paired
  and opposite directions, plus the exact parent. No late-data ranking.
- Two starts per model: exact parent and a predeclared0.8 directed change.
  Two paired-coordinate fits and two split-coordinate fits, maximum3 workers.
  Same200 primary/500 cumulative actual objective integrations per fit;
  derivative probes count and function/constraints share cached simulations.
- Registered stop after120 calls and90 calls without admissible1e-4 NLL
  progress; one optional within-budget same-coordinate interior repair.
- Select the lowest outer-guard-feasible score, including the real parent
  fallback. Prefer paired unless split gains at least1e-4 NLL. This threshold
  resolves numerical ties; it is not a statistical significance criterion.
- Changed paired comparator first gets original strict/ultrastrict J10 checks.
  Changed selected model must pass original J4/J10/J46 strict/ultrastrict
  executed-flux, positivity, convergence and unchanged early guards. Late
  residuals cannot select constants. Never promote production defaults.

## Execution

- [x] Implement reversible isolated parameterization and guarded runner.
- [x] Pass16 focused tests, including actual-budget coverage.
- [x] Freeze archive after1152 parent verification checks;13 guards and22 values.
- [x] Execute nine screens/four fits: all four SLSQP starts converge.
- [x] Complete six original-path audits; split selected, no fallback.
- [x] Complete QA:1379 passed,2 existing skips,6 existing Optuna warnings.
- [x] Independently verify and inspect both comparison figures.
- [x] Record results, limitations, manuscript and next handoff.

Archive: `output/hk_pfk_split_2026_11_03/`.
Separate mutable-then-sealed verification/report directory:
`output/hk_pfk_split_validation_2026_11_03/`.

## Training results

| Model/start | Actual objective integrations | Feasible NLL | Optimizer success |
| --- | ---: | ---: | --- |
| Paired/seed | 17 | 96.6157938200 | yes |
| Paired/directed | 31 | 96.6157854545 | yes |
| Split/seed | 69 | 91.3669502767 | yes |
| Split/directed | 45 | 91.3669446997 | yes |

The eight nonbaseline fixed5%-scale screens violate at least one
guard. This does not imply local/global infeasibility: the constrained split
search finds a different admissible compromise. All162 actual fit evaluations
and9 screens are logged. Four selected fitting replays are additional ODE
integrations, not objective calls. No secondary stage, budget stop, stagnation
stop or inward repair is needed. Both split starts have costs within5.6e-6,
not proof of global optimality or parameter identifiability.

Best paired improvement over the true parent is4.8223e-5 NLL, below the
registered1e-4 tie threshold. Therefore the retained paired comparator is
the parent, not an unreported parameter adjustment. Raw split gain versus
the best paired fit is5.2488407548; gain versus the retained comparator is
5.2488889776. The archive field named `split_training_NLL_gain_vs_best_paired_found`
uses this retained-reference rule; report both quantities explicitly.

Selected split training factors relative to original primitive capacities:
HK0.03253288995 and PFK0.25297246913, versus parent0.39580748813 for both.
Training ATP J4/J8 is0.021057443/0.000305327mM versus parent0.005335800/
0.000211843mM, still far below nominal1.079765/1.272527mM. Residual CV14.2743
is total mismatch, not measured assay precision. Original-path acceptance
now passes; this does not establish physiological validity or promotion.

## Original ODE and independent acceptance

Selected `split_directed`: `vmax_VHK=0.1626644497521443` and
`vmax_VPFK=0.6449357656932573` mM/day, versus parent1.97903744065 and
1.00908374064. Both remain inside the original bounds. Every other parameter
and GLUT constant is unchanged. No source, initialization or network edit.

All six original strict/ultrastrict J4/J10/J46 replays pass:117507/117507
state/integral comparisons,12882/12882 executed daily balances and11400/11400
quadrature checks each for raw and executed fluxes. All13 J4/J8 constraints
pass in fitting and original J10/J46 replays. They are early-time constraints,
not all-time non-regression. Minimum over saved accepted/dense/quadrature
concentrations is0mM, not a continuous-time positivity proof. Full/fast parity
passes, with seven independent live rate/RHS checkpoints per new replay.

Primary verifier1123 checks; secondary1754 checks reopen all770 original
workbook cells, verify source/report hashes and reconstruct110 pool/comparator
rows plus94 full/period signed budgets. Maximum independent budget difference
7.66e-15mM. Report generation adds228 checks. Full QA1379 passed/two existing
skips/six existing Optuna warnings;42 focused tests pass. No global optimality,
parameter identifiability, all55-channel protection or biological validation.

## Gains and remaining failures

| Pool | Parent J4/J8 RMSE (mM) | Split J4/J8 RMSE (mM) |
| --- | ---: | ---: |
| EGLC | 0.865189 | 0.689487 |
| GLC | 0.846827 | 0.846831 |
| ATP | 1.177536 | 1.170344 |
| PEP | 0.0278109 | 0.0278105 |
| G6P | 1.373741 | 0.202344 |
| F6P | 0.254520 | 0.0468370 |
| B23PG | 0.321445 | 0.259481 |

GLC slightly increases relative to the restored parent while remaining below
the unchanged original GLUT-derived cap. No literal zero-regression claim.
F6P/G6P also improve over the full source schedule, but EGLC RMSE worsens
1.358335 ->2.241474mM and GLC3.349069 ->4.102435mM. J46 EGLC15.596004 ->
16.825361, GLC6.100110 ->6.896167 and ELAC21.670112 ->20.764654mM. The
nominal J46 values are12.915,0.826365 and28.363716mM, respectively.
ATP J46 is1.77345e-5 versus parent1.72524e-5 and nominal0.469757mM:
no energetic rescue. J46 F6P1.164808 ->0.220713mM still exceeds nominal
0.007026. Among44 unguarded representations,16 have raw early-RMSE increases
versus the parent; largest GMP0.028762mM. These are not independent assays
or statistical significance counts.

Full-period executed ATP production5.775129 ->4.976611 and consumption
6.708104 ->5.909585mM yield nearly unchanged net depletion-0.932975mM.
HK ATP expenditure2.079174 ->0.392892 falls, but compensatory NDPK,
PRPPASe and other expenditures increase, while PGK/PK/AK contributions
decrease. This is a trajectory budget, not a causal isolation experiment.
Glucose import7.055997 ->6.165773 minus HK2.079174 ->0.392892 leaves
accumulation4.976823 ->5.772880mM. Saving ATP at HK does not restore the
adenylate partition. OPLAH remains present and active.

## Decision and handoff

Dissociation is useful for conditional early fitting and retained as an
opt-in candidate, not a production/default reference or validated storage
prediction. Keep the original paired candidate for direct rollback. All
fits/audits have ended. Suggested next task, NOT executed: preregister a
progressive J1-J15 extension with actual J11/J15 observations and explicit
glucose/lactate temporal protection before opening more kinetic groups.
The late data have already been exposed; they cannot become a blind external
validation set by changing the split. Redox/RIB ICs, pH/MCT and thresholds
remain closed. Do not fix the ATP deficit by inventing source concentrations.

Artifacts:

- `output/hk_pfk_split_2026_11_03/summary.json`
- `output/hk_pfk_split_validation_2026_11_03/comparison/comparison.json`
- `output/hk_pfk_split_validation_2026_11_03/comparison/candidate.json`
- `output/hk_pfk_split_validation_2026_11_03/comparison/training_comparison.png`
- `output/hk_pfk_split_validation_2026_11_03/comparison/concentration_comparison.png`
- `output/hk_pfk_split_validation_2026_11_03/verification.json`
- `output/hk_pfk_split_validation_2026_11_03/secondary_verification.json`
