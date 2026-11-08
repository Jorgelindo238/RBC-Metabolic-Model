# Glucose/lactate observation bases and RBC-GEM transport audit

Date: 2026-10-06. Scope: source verification and prospective transport design, not production kinetics, data conversion or optimization. This successor contract leaves the common source manifest and all historical archives unchanged.

## Decisions

1. Retain distinct reference litres, as requested. A concentration already expressed in mM needs no cell-count or single-cell-volume conversion simply to be read. However, coupling two concentration balances requires compatible amount bookkeeping and the ratio of their reference volumes. A litre of cells, intracellular water, supernatant and whole bag must be named explicitly.
2. Do not reinterpret a published mmol/L-bag value as mmol/L-cell or mmol/L-supernatant. Observation normalization and membrane kinetics are separate operations.
3. Validate identified donors, or predefined groups with compatible protocols and covariates. Do not invent donor identities from positional replicate blocks. No validation split or biological fit is created here.

## Available measurements

The archived original Yurkovich JBC workbook is available and byte-verified: `output/jbc_supplements_ingestion_2026_10_06/source_files/jbc.M117.804914-1.xlsx`. Selected cells are rechecked against that workbook, not only against the earlier CSV export.

| Signal | Exact channel | Source unit | Interpretation limit |
|---|---|---|---|
| Intracellular glucose | endo!L | mM | Extraction pool and exact normalization equation require confirmation |
| Intracellular lactate | endo!AE | mM | Same denominator/free-pool issue |
| Hematocrit | assay!D | L/L | Measured geometry, not an assumed 0.6 |
| Extracellular glucose | assay!Q | mM | Assay concentration denominator must be linked to source processing |
| Extracellular lactate | assay!T | mM | Same requirement |
| pH | assay!Y | dimensionless | Supplement p2: measured at 37 C, not pHi or automatically pHe at 4 C |
| pH at 22 C | assay!Z | dimensionless | Reported temperature-specific channel; not substituted for 4 C |

There are 126 hematocrit values. Overall range is 0.548-0.764; the 24 values at 4 C span 0.574-0.702. Under a cells/supernatant interpretation these correspond to Vcell/Vsupernatant ranges 1.2124-3.2373 overall and 1.3474-2.3557 at 4 C. These are descriptive ratios, not conversions applied to concentration data. All seven selected channels comprise 876 numeric source cells. The workbook also includes cell volume, cell count, bag weight and hemolysis channels; those are available leads, not a verified amount-normalization or donor-join equation.

The supplement p2 documents three healthy donors, SAGM and splitting each unit among four temperatures. It also describes pellet/supernatant extraction and source day0 one day after storage began. The absence of an explicit donor key in the workbook still prevents a reliable cross-sheet/temperature join. Assay-only day14 at37 C makes positional row joins particularly unsafe. No hematocrit from JBC is borrowed for the locally labeled Bordbar cohort.

Local `src/Data_Bordbar_et_al_exp.xlsx`, Sheet1 has `Conc / mM`, four glucose/lactate rows and 14 nominal days J1-J46. It does not establish a per-cell, cell-water, supernatant or bag denominator or donor-specific identity. All values, including J1, remain unchanged. This local limitation is not a claim that published Bordbar source data lack those metadata.

## Published normalization evidence

[Bordbar uFBA2017](https://www.nature.com/articles/srep46249), article p7, Data Preparation, explicitly adjusts intracellular AND extracellular RBC measurements to amounts per litre of TOTAL BAG. The [institutional primary PDF](https://backend.orbit.dtu.dk/ws/portalfiles/portal/132148106/srep46249.pdf) includes a cover, placing the statement on PDF page8. Methods also describe unresolved-pool splitting, rates per hour and closed-system modeling. This establishes that article's observation convention, not the preprocessing lineage of local Sheet1 or the original JBC workbook. No automatic 24-fold rate correction, J1 rescaling or pool splitting is justified.

The supplied [Yurkovich JBC2017](https://pubmed.ncbi.nlm.nih.gov/29030425/) supplement establishes separated assays and hematocrit, but the audited method does not give a complete equation linking recovered intracellular amounts to the final workbook denominator. The earlier source review of [Yurkovich PLOS2017](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005424) distinguishes a Bordbar-storage reanalysis from this separate temperature-storage experiment. Published pooled/aggregate data cannot be reconstituted into individual donors without their original identifiers and measurements.

## Exact volume contract

Let Vi and Ve be total cellular and extracellular-fluid reference volumes; ci and ce are mmol per corresponding litre. For a membrane export Q in mmol/day, with no other processes:

```text
d(Vi ci)/dt = -Q
d(Ve ce)/dt = +Q
dci/dt = (-Q - ci dVi/dt)/Vi
dce/dt = (+Q - ce dVe/dt)/Ve
```

At fixed bag volume Vb and hematocrit H=Vi/Vb, Vi=H Vb and Ve=(1-H)Vb. For a cell-normalized export j=Q/Vi, dci/dt=-j and dce/dt=H/(1-H) j. Glucose import has the opposite signs. Thus physical concentrations generally do NOT have equal-and-opposite transport slopes.

Observation operators have three distinct cases:

| Intracellular observation | Extracellular observation | Fixed-volume export contributions |
|---|---|---|
| ci per cell litre | ce per supernatant litre | -j and H/(1-H) j |
| ci per cell litre | ye=(1-H)ce per bag litre | -j and H j |
| yi=H ci per bag litre | ye=(1-H)ce per bag litre | -H j and +H j |

The third case explains why equal-and-opposite published bag-normalized slopes can be correct despite different physical compartments. It does not make those bag-normalized observations suitable direct arguments to a physical transport Km. Accessible free concentration/activity, packed-cell versus cell-water basis and recovery/binding definitions remain separate kinetic requirements. If the denominator is cellular WATER rather than packed cells, include its supported water fraction; do not assign one by default.

For extracellular observation y=n_e/B_e, the transport teacher is Q=d(B_e y)/dt, and its integrated version is the corresponding amount change, only after accounting for other extracellular production/degradation, leakage/hemolysis and sampling terms. For glucose import Q_import has the opposite sign. Changes of denominator, bag removal and sampling cannot be absorbed into an apparent membrane flux. Hematocrit variation alone does not distinguish swelling, sampling or lysis; no automatic derivative correction is applied. ODE time is days; imported rates require an explicit time and mass/volume-unit contract.

## What RBC-GEM actually encodes

Read both pinned versions: published1.2.0 commit5347d80275be01e410aa9787b0aac99497a8ed57 and1.3.0 commit43fd381d9eb8a8a4079629012362312960e1c009. Target JSON transport records agree in stoichiometry, bounds, GPR and reference content, after normalizing semicolon strings versus JSON arrays. Eleven raw reference fields change encoding; both original representations are preserved. Curated transport evidence is read separately from the available1.3.0 table; no1.2.0 curation table is present in this archive. [RBC-GEM primary article](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1012109); [versioned repository](https://github.com/z-haiman/RBC-GEM).

| GEM reaction | Positive orientation | AIRBC counterpart | Supported mechanism |
|---|---|---|---|
| GLC_Dt | glc__D_c -> glc__D_e | -VEGLC after consistent flux normalization | Reversible facilitated glucose transport, no ATP/proton stoichiometry |
| L_LACt2 | lac__L_c + h_c -> lac__L_e + h_e | VELAC contribution, not necessarily total VELAC | Reversible lactate/proton symport |
| LLAC_Cltex | lac__L_c + cl_e -> lac__L_e + cl_c | Alternative lactate route | SLC4A1 anion exchange |
| PYR_LLACtex | pyr_c + lac__L_e -> pyr_e + lac__L_c | Alternative/competitive MCT route | Positive lactate IMPORT, not export |

GLC_Dt GPR includes SLC2A1/2/3/4/14. SLC2A1 is the first reduced-model hypothesis, not proof every listed isoform is active. L_LACt2 GPR includes SLC16A1/7 with BSG/EMB and standalone alternatives. The archive retains complete GPRs and evidence rather than replacing them with a single forced complex. There are 12 lactate c/e routes in each pinned model: the main symport, chloride exchange and ten monocarboxylate exchanges. Total net lactate transport is the stoichiometrically signed sum of those routes. A measured ELAC slope does not identify each route independently. Shared carrier capacity must not be duplicated across substrates.

EX_glc__D_e and EX_lac__L_e are environment boundary reactions, distinct from membrane transport. Their permissive +/-1000 bounds are neither measured transport capacities nor instructions to feed a closed blood bag from an infinite reservoir. GEM flux feasibility supplies no Km or storage-temperature dynamic law.

Human-RBC [De Bruijne et al.1983](https://pubmed.ncbi.nlm.nih.gov/6871216/) supports proton-first ordered carrier binding and parallel lactate pathways; [Halestrap1976](https://pubmed.ncbi.nlm.nih.gov/942406/) supports chloride-dependent/independent routes and pyruvate competition. Their published abstracts were read; full kinetic tables were not retrieved and no parameter value is imported. [Lloyd et al.2018](https://pubmed.ncbi.nlm.nih.gov/29209831/) demonstrates GLUT1 allostery. These sources inform candidate mechanisms, not a validated kinetic fit at4 C or universal route fractions.

## Current AIRBC discrepancy and proposed reversible hypotheses

The existing kernel uses dGLC/dt=VEGLC-VHK, dEGLC/dt=-VEGLC, dLAC/dt=VLDH-VELAC and dELAC/dt=VELAC. Equal-and-opposite transport concentration contributions require a common reference denominator or explicit conversion; otherwise the coupling is dimensionally incomplete. Whether the historical numerical scale is wrong remains unresolved until source processing is established.

The default glucose rate subtracts two independently saturated terms with one shared Vmax but Km_e=49.484 and Km_i=5.0. Its zero occurs at EGLC/GLC=9.8968 in those state coordinates. That is not generally the equal-activity equilibrium of passive glucose transport. Observation scaling might explain a coordinate ratio, but distinct Km values alone do not justify a shifted chemical equilibrium. The default lactate law permits efflux only; its optional reversible variant lacks explicit proton coupling.

First prospective glucose reduction, for comparable free concentration/activity coordinates and unit partition coefficient:

```text
j_G_import = k_G (g_e - g_i)/(1 + g_e/K_e + g_i/K_i)
V_forward/K_e = V_reverse/K_i = k_G
```

This permits directional saturation asymmetry while retaining zero net flux at equal activity. k_G is day^-1 and the directional capacities are mmol/L-cell/day only if that is the declared j basis. It is a proposed Haldane-constrained reduction, not the full GLUT1 alternating-access/allosteric mechanism. A justified activity/partition correction must precede using total extractable concentrations. First compare fixed-parameter behavior and synthetic recovery; do not open both Km and both capacities from extracellular slopes alone.

For lactate, a reduced reversible law must have an export driving term proportional to a_Li a_Hi - a_Le a_He, divided by a positive saturation/competition denominator derived from the selected carrier reduction. Ideal same-standard-state equilibrium gives Li/Le=10^(pHi-pHe); different observation denominators do not alter this physical equilibrium. No full MCT law or parameters are implemented in this pass. Explicit pHi/pHe and temperature compatibility are mandatory; the assay pH measured at37 C cannot silently supply pHe at4 C. H+ export also needs an acid/base buffer and Hb/CO2 contract; pH is not a concentration to which +/-VELAC can simply be added. Neither GLUT nor MCT requires ATP hydrolysis per transported molecule in the GEM. ATP regulation of GLUT is not an ATP pump.

## Donor/group validation and next execution

Prespecify matching on storage solution, temperature, collection/processing, actual storage origin, analytical pool and denominator, plus supported donor features such as sex, age or genotype when actually available. Keep all days and paired temperatures/conditions from one donor in the same partition. Freeze preprocessing, smoothing, uncertainty and capacity priors on training donors. With only three identified JBC donors, leave-one-donor-out is a small-sample transfer diagnostic, not a strong population validation claim; it is executable only after donor linkage. Without keys, report condition-level aggregate compatibility instead of donor validation. Never define groups from fitted ATP loss or favorable outcomes, and document REDS cohort overlap.

Next: confirm the original intracellular amount-normalization formula and the workbook's cross-sheet donor key, then instantiate exactly one source-specific observation basis. Implement an opt-in fixed-parameter transport adapter with amount-conservation, zero-boundary, reversible-equilibrium and proton-ledger tests. Compare source-compatible glucose/lactate budgets before teacher reconstruction, joint redox/ATP inference or biological calibration. The new mathematical audit utilities are isolated in the audit script; they are not called by the ODE/API/training path. No claim of restored ATP is made.

## Reproduction

```powershell
python scripts/audit_rbc_transport_contract.py --out output/fla_transport_contract_new
python scripts/audit_rbc_transport_contract.py --verify output/fla_transport_contract_2026_10_06_v3
python -m pytest qa/test_rbc_transport_contract.py qa/test_fla_common_manifest.py -q
python scripts/build_fla_common_manifest.py --verify output/fla_common_manifest_2026_10_06
```

Use the bundled Python with pypdf for optional `--fetch-methods`, which archives and checks the institutional primary PDF. New source values, JSON, decisions and input/output hashes are kept in a separate archive. Verification reconstructs selected cells and GEM records with the same audit implementation; it is not an independent algorithm or proof of biological readiness. Full ODE QA is not rerun for this source/design-only pass.

The preliminary unsealed directory `output/fla_transport_contract_2026_10_06/` preserves an interrupted source build that exposed the annotation-encoding difference. A subsequent v2 attempt could not archive the methods PDF because Python TLS verification reported an expired certificate; verification was not disabled. The primary PDF was read through the web research tool, but no successful local PDF download is claimed. Both incomplete directories remain preserved. The final sealed source-only target is v3, built without optional network retrieval.

Focused QA: 64 tests passed (35 new transport-contract checks and29 common-manifest checks). The preceding common manifest still verifies all174 input and nine output hashes, reconstructing8097 channel representations and2249 sample records. Full ODE QA is not rerun; no production behavior changed.
