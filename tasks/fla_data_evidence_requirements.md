# J1-J4 scientific evidence required before fitting

Updated: 2026-10-06. Active configuration: `config/fla_adenylate_redox_readiness.json`. Final preparation: `output/adenylate_redox_readiness_2026_10_05_v2/`. Read-only source audit: `output/bordbar_source_units_time_audit_2026_10_06/`.

## What is already verified

| Pool | Local sheet | J1 cell | J4 cell |
|---|---|---|---|
| ATP | Data_Bordbar_et_al_exp.xlsx / Sheet1 | B9 | C9 |
| ADP | Data_Bordbar_et_al_exp.xlsx / Sheet1 | B3 | C3 |
| AMP | Data_Bordbar_et_al_exp.xlsx / Sheet1 | B5 | C5 |

The concentration header is nominal `Conc / mM`; model-day headers are 1 and 4. NAD/NADH are historical model inputs in `Initial_conditions_JA_Final.xls`, rows 84/85, not observed rows in this panel. Actual source hashes and values are recorded in `source_receipt.json`. This establishes reproducibility of local inputs, not biological provenance or normalization.

Workbook XML now localizes the `cellbb` text import to **Feuil1**, with named range `Feuil1!$A$5:$F$49`: 44 rows of five curve coefficients (`b_1` through `b_5`) and polynomial/log evaluation formulas. It is not bound to **Sheet1**, the 55-by-14 concentration table used for training. Sheet1 contains no formulas. Recovering `cellbb.txt` alone cannot establish measurement lineage. Request the original concentration export feeding Sheet1 and its preparation script; the text file remains useful for coefficient provenance. Neither the workspace filename search nor all-ref Git history recovered that file; other folders/private cloud storage were not searched.

All 770 concentration cells are finite and nonnegative. Five available workbook Git snapshots retain identical labels, values and time headers. This confirms local preservation, not publication provenance or independence of the exact duplicate B13PG/B23PG and P2G/P3G signals.

## Minimal evidence to supply

| Domain | Required material | Why the current input is insufficient |
|---|---|---|
| Lineage | Original concentration export feeding Sheet1 and exact ATP/ADP/AMP row mapping; biological unit/donor IDs | cellbb is a coefficient import, not a verified raw concentration export |
| Normalization | Source quantity unit, cell/volume/water basis, formula and factors into intracellular model mM | A concentration header does not identify its denominator |
| Time | Sampling origin, original days and explicit source-to-model day offset | J1-J46 spans 45 elapsed days; a +1 origin is plausible but unverified, and local J38 must not be repaired |
| Uncertainty | Paired biological and technical measurements, or supported assay covariance, plus effectives and estimand | No local donor IDs, SD/SEM or replicate table supports numerical uncertainty |
| Accuracy | Three independently justified J4 absolute prediction-error limits in mM, with timestamped policy | Solver tolerances and failed replay errors are not prediction requirements |
| Redox | Applicable NAD-total and NADH-fraction bounds, with verified intracellular concentration basis and pool definition | Historical points and a generic 1+1 mM initialization are not prior intervals |

Store supporting files without modifying historical inputs. Each verified section must reference their paths and SHA256. Fill only verified fields in the active configuration; missing values remain `null` and verification remains `false`. Do not flip flags to bypass missing source content. A ready local contract still does not authorize full-model promotion or fitting without a separate calibration protocol.

## Uncertainty contract

Use observation order `(ATP_J1, ADP_J1, AMP_J1, ATP_J4, ADP_J4, AMP_J4)` and a full symmetric positive-semidefinite covariance in model mM^2. State whether uncertainty describes an individual unit, a population distribution or an estimated mean. Biological donor variation and technical error are different quantities. For paired, equally weighted independent biological units, covariance of the mean can be estimated from their joint sample covariance divided by unit count; that operation is invalid without these assumptions.

Cross-pool and cross-day covariance must not be guessed as zero. For a documented deterministic normalization A, covariance transforms as A*C_source*A^T; uncertain normalization requires joint propagation of its parameters and their covariances, not an undocumented diagonal rescaling. Energy-charge uncertainty uses a first-order delta method and is not an exact nonlinear interval or a kinetic uncertainty estimate.

Set endpoint tolerances through either a measurement-supported rule or an explicitly justified, predeclared prediction requirement. Measurement uncertainty, engineering acceptability and numerical integration error remain distinct. Do not automatically use a published coefficient of variation as an epsilon, SD or SEM. Full-panel nRMSE limits remain separately unresolved.

## Publication leads, not dataset mappings

The [Bordbar study candidate](https://pubmed.ncbi.nlm.nih.gov/26749434/) describes 20 SAGM units over 42 days. [Qi et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC5487983/) use a separate ADSOL cohort and a relative-to-absolute normalization procedure. These methods cannot be transferred to the local workbook without a verified mapping. No published variability or redox interval was imported automatically.

The [2017 primary Bordbar reanalysis](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005424) reports 14 observations over **45 days**. Consequently the earlier 42/46 wording is not evidence that local J43/J46 are extrapolated. The candidate offset maps local days to `[0,3,7,10,14,17,21,24,28,31,35,37,42,45]`; this is a hypothesis, not a verified source vector. The reanalysis excluded source day 31 after an extracellular anomaly. Its possible correspondence to local J32 and the local EGLC rise are only leads: no observation is removed.

The [Bordbar uFBA study](https://www.nature.com/articles/srep46249) describes mmol per liter of **total bag volume** for intracellular and extracellular pools and prioritizes glucose/lactate/ATP assay measurements. If this is the verified local convention, equal-reference-volume transport coefficients could be appropriate; an intracellular-water conversion must not be invented. Request the actual denominator, assay-to-table transformations and any volume changes first. The current concentration loaders preserve nominal numbers without declaring a volume conversion. Two public supplementary endpoints returned HTML with HTTP 200, not usable Excel evidence; access receipts and response hashes are archived.

[Simpson et al., 1982](https://www.cruk.cam.ac.uk/publications/studies-of-lactate-dehydrogenase-in-the-purified-state-and-in-intact-erythrocytes/) distinguish free reaction-available NAD(H) from total extractable NAD(H). This is an additional compatibility requirement, not a numeric stored-RBC prior. Declare the source and modeled pool definitions explicitly and consistently; a matching mM unit and volume denominator alone are insufficient. No binding model or free fraction is invented to convert between them.

## Prepared next diagnostic

`coupled_sensitivity_protocol.json` specifies 19 configurations / 38 strict-ultrastrict replays. The three groups are downward-only HK/PFK investment (HK ceiling 5.0), AK forward/reverse capacity together, and GAPDH/PGK capacity together. All initial states, other kinetics, network and numerical threshold remain fixed. Log steps 0.05/0.10 are numerical probe sizes, not biological parameter ranges.

The protocol is prepared, not executed. Scientific readiness must be resolved first. Existing eight J1-J4 redox-initialization replays remain the simulation evidence. No best scenario, parameter fitting, artificial ATP source or promotion is permitted in this preparation.

## Reproduce the guard

`python scripts/prepare_adenylate_redox_readiness.py --out-dir <fresh-directory> --require-ready`

This prepares evidence only. Unresolved prerequisites return native exit code 2; existing output directories cannot be overwritten. Historical runners and platform defaults are unchanged. The guard rereads the contract and hashed evidence rather than trusting saved readiness booleans.
