# Accessible transport pools and acid/base handoff

Date: 2026-10-06. Requested step: establish accessible concentrations, pHi/pHe gradient and buffering before calibration. This contract is implemented and checked, but its biological input requirements are not yet satisfied.

## Delivered

- Configuration: `config/fla_transport_access_ph_contract.json`.
- Isolated mathematical utilities and prerequisite inventory: `src/fla_transport_access_ph.py`.
- Source-reconstructing builder/verifier: `scripts/audit_transport_access_ph.py`.
- Regression tests: `qa/test_transport_access_ph.py`.
- Sealed decision report and tables: `output/transport_access_ph_contract_2026_10_06/`.

The historical ODE, transport adapter, exact55 J1, latent initial pools, frozen constants, source observations, numerical threshold and prior sealed campaign are unchanged. No uFBA normalization, inferred donor identity, teacher regeneration, biological optimization or production activation is performed.

## Mathematical decisions

Separate an observed extractable concentration from a membrane-accessible activity equivalent. On each declared phase litre, the conditional operator is a_mM = gamma*f*C/(w*r). All four factors must be explicit: accessible substrate fraction f, aqueous volume fraction w, analytical recovery r and activity coefficient gamma. Recovery must not be applied again to an already corrected observation. Packed-cell mM needs no single-cell volume to be read; converting its denominator to cell water is a separate kinetic operation. For lactate, f includes the selected free anion species, not an unsupported total-lactate equivalence. These factors remain null in the biological configuration.

With rho=lambda_i/lambda_e, positive reduced-MCT export requires pHi-pHe < log10(LAC/ELAC)+log10(rho). Direction depends on the effective difference pHi-pHe-log10(rho). Therefore a directional match cannot identify both a free-pool scale and a pH gradient. Hematocrit controls the amount balance, not this chemical equilibrium. GLUT equilibrium similarly concerns accessible activities, not necessarily equal extractable numbers. Existing effective Km and conductance values are not silently reinterpreted as free-activity parameters.

For cell-normalized executed MCT j, J_H=H*j on the bag-volume basis. At fixed geometry and local buffer capacities, dpHi/dt=-(s_i-J_H)/(H*beta_i) and dpHe/dt=-(s_e+J_H)/((1-H)*beta_e). This closes acid equivalents when capacities and sources use the stated bases. Positive export raises pHi and lowers pHe; import does the reverse. Clamped pH requires balancing reservoir acid R_i=J_H-s_i and R_e=-J_H-s_e. The present ledger is explicitly MCT-only: missing metabolic proton sources are not assumed absent from biology.

Do not add explicit carbonate buffering to an already effective total beta. A future explicit carbonate model needs Hb/oxygenation and phosphate context, CA, Cl/HCO3/AE1 coupling, carbon balance and gas/sampling/hemolysis boundaries. AE1 is not an independent H+ pump. Fluxes must be executed rather than native counterfactual rates. Historical empirical pH terms and minute/hour comments inside the day-based kernel are not adopted as a closed acid/base model.

## Executed evidence

Reopen the original archived JBC workbook and reconstruct144 paired records across six equally retained source-sheet permutations. Preserve all concentration values and source locators. Recheck48 original pH cells for4C storage: assay!Y was measured at37C per the supplement, while assay!Z is reported at22C with its exact derivation unresolved. Neither supplies observed pHi or automatically supplies pHe at4C. A universal temperature correction is not introduced.

Produce576 accessibility-dependent bounds using rho0.5/1/2/4 and2880 directional counterfactuals using delta_pH -1/-0.5/-0.2/0/0.2. These grids are algebraic sensitivity probes, not physiological prior ranges. Equal-mapping source-day0 bounds remain -0.732948 to -0.253806. The576 bounds reuse original observations, not576 independent measurements.

Reopen the six reversible strict/ultrastrict archives and their executed VELAC integrals. Verify supernatant lactate amount closure and construct54 MCT-only frozen-integral buffer ledgers. beta_i30 is a historical code anchor;65 and85 are37C literature-context anchors. beta_e1/10/30 is synthetic, not measured SAGM capacity. All7392 source/algebra/archive checks pass, including65 previous-seal hash checks. Verification reconstructs using the same builder, with direct algebraic identities and signed acid conservation checks; it is not an independent biological validation implementation.

Frozen-integral delta_pHi spans -0.019758 to -0.006281 and delta_pHe +0.026622 to +0.916841 under this grid. These are not new ODE simulations or physiological pH predictions. In particular, the large excursions with beta_e1 exceed the intended local-capacity approximation and diagnose sensitivity, not plausible storage pH. Fluxes must be re-integrated if pH changes. ATP outcomes are unchanged.

Primary mechanism/context sources: [Swietach2010](https://pmc.ncbi.nlm.nih.gov/articles/PMC3036193/), [Jennings](https://pmc.ncbi.nlm.nih.gov/articles/PMC4042536/), [Guppy1992](https://pubmed.ncbi.nlm.nih.gov/1519370/). The full-text search extract/institutional PDF for Swietach was available, while direct PMC reopening met recaptcha; other retrieval limitations and transfer roles are recorded in `literature_context.json`. No37C value is promoted to a4C biological input.

Focused regression run:150 tests passed, including85 new contract cases and65 existing phase/source transport checks. Full QA:1161 passed, two existing source-dependent skips and six existing Optuna warnings, in95.35 seconds. The Python3.14/Pydantic startup warning remains. Full QA results are recorded separately in `output/transport_access_ph_contract_validation_2026_10_06/qa_results.xml`.

## Next execution

Fourteen explicit prerequisite groups remain open: source processing/denominators; four accessible-pool definitions; pHi/pHe at compatible temperature; buffer representation/capacities; Hb/oxygenation/CO2; metabolic proton accounting; AE1/Cl/HCO3; gas/sampling/hemolysis; carrier parameter-coordinate compatibility; and alternative routes/shared capacity. Filling fields or citing a paper is not an automatic scientific-readiness override. The local inventory never authorizes optimization or free pH prediction.

Next obtain or justify these observation/context mappings and preregister a synthetic coupled carrier/buffer identifiability/recovery test at fixed geometry. Use supported independent pH or pool information to break the activity-gradient ambiguity. Do not choose a favorable rho, pH or donor permutation by ATP/ELAC agreement. Donor linkage, covariance, absolute accuracy and previous biological-readiness gates still apply before biological fitting.

## Reproduction

```powershell
python scripts/audit_transport_access_ph.py --verify output/transport_access_ph_contract_2026_10_06
python scripts/audit_transport_access_ph.py --out output/transport_access_ph_contract_new
python -m pytest qa/test_transport_access_ph.py qa/test_distinct_volume_transport.py qa/test_rbc_transport_contract.py -q
```

Existing evidence directories are not overwritten. Reproduction uses the original workbook and saved executed fluxes; it does not launch the14 preceding ODE replays again.
