# FLA transport source audit and synthetic benchmark preparation

Date: 2026-10-06

## Scope and completed work

The user authorized the proposed source-processing audit and synthetic carrier/pH/buffer benchmark preparation. This execution reads preserved original Bordbar/JBC files, checks a published analyzer equation, freezes the recovery design and runs numerical forward pilots. It does not fit biological parameters or rerun the full RBC ODE. Source concentrations, exact55 J1 initialization, historical kernels, reaction-consistent strict working profile and previous sealed archives remain unchanged.

Artifacts:

- `output/transport_source_processing_2026_10_06/`: original-cell reconstruction, pH lineage comparison, workbook/supplement inventories, retrieval receipts, manufacturer PDF, decision report and sealed manifest.
- `output/transport_buffer_synthetic_preparation_2026_10_06/`: frozen design/protocol, synthetic trajectories, symmetry controls, sensitivity spectra and sealed manifest.
- `config/fla_transport_buffer_synthetic.json`, `src/fla_transport_buffer_synthetic.py`, `scripts/prepare_transport_buffer_benchmark.py`: isolated synthetic experiment, not an alternative biological default.
- `scripts/audit_transport_source_processing.py`, `qa/test_transport_buffer_preparation.py`: source reconstruction and regression coverage.

## Source processing: new pH lineage evidence

All126 original `assay!Y`/`assay!Z` pH37/pH22 pairs satisfy the manufacturer candidate equation within propagated rounding:

```text
pH22 = pH37 + 15*(0.0147 + 0.0065*(pH37 - 7.40))
```

The largest residual is0.001027500 pH versus a0.001048750 bound from two three-decimal reported readings. The equation is documented in the [Radiometer ABL90 IFU](https://www.ruh.nhs.uk/pathology/documents/poct/SOP_Radiometer_ABL90_Flex_IFU_Instructions.pdf), chapter11 printed page276/PDF page296. This is strong evidence compatible with a calculated pH22 channel, not confirmation of the authors' software version or processing chain. Keep the two channels in a shared potential evidence group; do not add them as independent likelihoods. No4C pH is generated.

The manufacturer PDF was retrieved and hashed; the institutional main JBC PDF was read online but its local download returned403, recorded in the receipt rather than replaced with a fabricated file. The original23-page supplement remains source evidence. JBC contains zero workbook formulas/defined names. Bordbar Sheet1 contains no formulas; `cellbb` concerns coefficient import, not concentration normalization.

Pellet/fluid extraction and internal standards do not establish a complete original amount-to-final-mM denominator, free-water mapping, accessible fraction or analyte-specific recovery already applied. Request the original processing equations, source/sample/donor keys, aliquot/Hct factors, calibration/recovery corrections and analyzer temperature/channel settings. Hematocrit is geometry, not proof of cell-water fraction or free substrate availability. The chosen cell/supernatant coordinates remain a working hypothesis, not a retrospectively certified source normalization.

## Synthetic coupled model

The closed toy has five coordinates: intracellular lactate, extracellular lactate, pHi, pHe and integrated cell-basis export. It reuses the existing reduced reversible MCT rate and buffer ledger. With constant hematocrit H, executed export j and effective phase capacities:

```text
dLAC/dt = -j
dELAC/dt = H/(1-H)*j
dpHi/dt = j/beta_i
dpHe/dt = -H/(1-H)*j/beta_e
dz/dt = j
```

Accessible concentrations are `access_i*LAC` and `access_e*ELAC`. No concentration clipping, forcing, ATP, glycolysis, AE1, carbonate, gas boundary or metabolic proton source is included. Constant capacities and all truth parameters are constructed, not4C physiological priors. Negative substrate inputs raise an error; zero-boundary tests check the physical inward rate.

Truth uses H0.58, conductance0.3/day, accessibility1.5/1, affinities2/2mM-equivalent and capacities65/10 per phase litre/pH. Initial LAC/ELAC are2/5; export and import scenarios start with pHi/pHe6.9/7.3 and7.2/7.2. Only the JBC4C sampling coordinates, not source concentrations/pH, supply the sparse schedule. Train through source-coordinate7.0417days; later samples through20.9583days are reserved. A dense81-point training comparison is explicitly synthetic. No Bordbar J1 origin or donor identity is transferred.

## Executed numerical and ambiguity controls

Execute72 forward integrations: four strict/ultrastrict truth cases, four exact-symmetry controls and64 central finite-difference sensitivity perturbations. Amount and acid-equivalent closure, extent/quadrature consistency, checked concentration positivity and strict/ultrastrict comparisons all pass their declared tolerances. These checks concern this toy only, not ATP or the full network.

Ultrastrict integrated cell-basis export is+0.351333931mM in the export case and-0.462220077mM in the import case. Their final pHi/pHe are6.905405/7.251482 and7.192889/7.263830. Accepted-step Gauss4/8 integrals agree within the declared limits; nonzero integration errors are retained rather than called exact.

The toy admits an exact transformation when intracellular affinity is unknown:

```text
access_i -> c*access_i
Km_i -> c*Km_i
pHi(0) -> pHi(0) + log10(c)
```

For constant buffers with no other pH processes, concentrations, pHe and j remain unchanged; pHi shifts by a constant. Four forward controls verify c0.5/2 across both scenarios. Consequently, even observing pHe does not identify this full equivalent family. Independent pHi or supported accessibility/affinity information is needed. Holding Km_i fixed breaks this particular full-rate transformation; a regression test explicitly checks that distinction. This is not proof that every full RBC model shares the toy's symmetry.

Twelve conditional sensitivity results cover two scenarios, sparse/dense training and concentrations alone/plus pHe/plus both pH channels, at two finite-difference steps. In sparse concentration-only training, conserved LAC/ELAC provide only three noninitial independent scalar amount samples for four unknowns. Small singular values are therefore not a certificate of successful recovery. With supported fixed affinity, independent pH observations improve the local conditional spectrum, but neither local rank nor dense synthetic sampling proves global identifiability. Observation scaling is a design choice, not estimated biological covariance.

## Frozen recovery protocol: prepared, not executed

1. Recover conductance alone from clean synthetic observations with other inputs known.
2. Recover conductance and extracellular buffer capacity with independent pH observations.
3. Test conditional accessibility/pHi recovery with fixed supported affinities, comparing observation plans and prespecified starts without leaking hidden initial pHi to concentration-only fits.
4. Retain the unknown-affinity exact-symmetry negative control and report equivalent families rather than a false unique parameter estimate.

Three starts, bounded parameters,100 objective evaluations per start, clean recovery limits and later-time prediction criteria are preregistered. Subsequent noise seeds/CV/pH error are design assumptions, not source uncertainty. Concentration-derived flux teachers must not be counted as independent measurements of their parent concentrations. For this closed toy, the ELAC increment equals H/(1-H) times integrated cell-basis export.

Executed recovery fits: zero. Biological ODE replays: zero. Promoted kinetic parameters: none. Biological readiness and the prior ATP deficit are unchanged.

## Verification and reproducibility

Focused QA:121 passed. Full QA:1197 passed, two existing source-dependent skips and six existing Optuna experimental warnings in128.63seconds. Startup Python3.14/Pydantic warning is unchanged. JUnit record: `output/transport_buffer_preparation_validation_2026_10_06/qa_results.xml`, outside both scientific seals.

Both read-only archive verifiers pass. The source verifier reconstructs original workbook rows and supplement inventory; the benchmark verifier checks sealed inputs/outputs and stored truth conservation/positivity. They reuse the implemented audit logic and are not independently implemented proofs or a fresh rerun of all72 integrations.

```powershell
python scripts/audit_transport_source_processing.py --verify output/transport_source_processing_2026_10_06
python scripts/prepare_transport_buffer_benchmark.py --verify output/transport_buffer_synthetic_preparation_2026_10_06
```

The audit build used the bundled Python for spreadsheet/PDF extraction; the numerical benchmark and QA used the project Python. No dependencies were installed. For a new build use a new output directory; do not overwrite sealed archives.

Next execution: bounded staged clean synthetic recovery under this frozen design, then noisy/holdout robustness if clean recovery is supported. Obtain the missing source and acid/base inputs in parallel before authorizing a coupled biological J1-J4 replay or calibration.
