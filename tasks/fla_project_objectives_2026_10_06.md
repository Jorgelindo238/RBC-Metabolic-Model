# AIRBC / FLA: reference-anchored project objectives

Date: 2026-10-06. Status: development strategy, not a completed model reduction or predictive validation.

## Central Objective

Develop a reduced, dynamic RBC-GEM-informed model of human red blood cell metabolism, using the existing AIRBC ODE and kinetic laws where appropriate. Use Flux Learning Analysis (FLA) to estimate only identifiable effective kinetic capacities from metabolomics, with proteomic capacity priors and independent predictive checks.

The intended contribution is a tractable, mechanistically documented dynamic model, not reproduction of every genome-scale reaction or estimation of every kinetic constant. The existing AIRBC model is being reconciled with RBC-GEM; it is not yet an exact, fully validated reduction of that reconstruction.

## Source Roles And Versions

| Source | Intended role | Important boundary |
|---|---|---|
| [Bordbar et al., Cell Systems 2015](https://pubmed.ncbi.nlm.nih.gov/27136057/), DOI 10.1016/j.cels.2015.10.003 | Personalized kinetic-model lineage and plasma/RBC metabolomic context | The cited study uses fasting-state profiles from 24 individuals. It does not by itself establish the provenance of our local J1-J46 storage table. |
| [Yurkovich et al., JBC 2017](https://pubmed.ncbi.nlm.nih.gov/29030425/), DOI 10.1074/jbc.M117.804914 | Quantitative storage time courses and temperature-dependent constraints | Preserve temperature, sampling coordinates, compartments, analytical definitions and replicate identity; resolve normalization before joint biological fitting. |
| [Haiman et al., RBC-GEM, PLOS Computational Biology 2025](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1012109), DOI 10.1371/journal.pcbi.1012109 | Structural reference: reaction chemistry, compartments, gene-protein-reaction associations and capacity organization | Its proteome-constrained FVA outputs are model-derived feasible fluxes, not experimentally measured teacher fluxes or verified ODE kinetics. |
| [Issaian et al., 2025 preprint](https://www.biorxiv.org/content/10.1101/2025.11.29.691178v1); [published Blood 2026 version](https://pubmed.ncbi.nlm.nih.gov/42224377/), DOI 10.1182/blood.2025032915 | Enzyme abundance and regulatory evidence for uncertain capacity priors | Retain supplied-file/preprint provenance; cite the published article for current biological interpretation. Abundance and interactions do not directly measure active fraction, kcat or Km. |
| [Dzieciatkowska et al., population proteome atlas, PMID 41846981](https://pubmed.ncbi.nlm.nih.gov/41846981/), DOI 10.64898/2026.03.07.710284, version 1 | Population-level biological benchmarking and candidate external tests | This is the same study as the supplied March 2026 validation preprint, not an additional dataset. PubMed currently labels it a preprint. Eligibility for quantitative ODE validation still requires matching observations and untouched cohorts. |

The atlas describes 13,091 donors and proteomic aging signatures associated with hemolysis and transfusion outcomes. This does not establish that 13,091 complete, absolute storage metabolite trajectories are available. Donor biological aging and storage duration are different coordinates. Its full methods/supplements and overlap with previously used RBC-Omics samples still require inspection; the present source check establishes metadata and abstract-level scope, not cohort independence.

Use these sources as complementary evidence, not one infallible source of truth. RBC-GEM itself can contain representation-dependent chemistry that requires correction, and recent protein detection can conflict with older reaction exclusions.

## Objective 1: Reconcile Metabolomics Without Pooling Incompatible Observations

Build a source-preserving measurement manifest containing metabolite identity, compartment, absolute/relative measurement type, units, time origin, temperature, storage medium, donor/replicate, normalization equation and source cell. Reconcile Bordbar-related materials with Yurkovich at the level of identity and observation models, not by averaging or concatenating incompatible trajectories.

For source s, represent observations as:

\[
y_s(t) = H_s(x_s(t), \eta_s) + \epsilon_s(t),
\]

where H_s includes measured pool sums, compartment-volume conversions and any explicitly supported analytical scaling. Each cohort retains its own initial conditions and environmental context. Shared kinetic parameters are a hypothesis to test, not an assumed equivalence of experiments.

The current `src/Data_Bordbar_et_al_exp.xlsx`, Sheet1 J1 initialization remains unchanged: all 55 measured entries stay exact in the historical context. The local filename does not prove the experimental lineage of its storage values. No substitution by the separate initial-condition workbook or cross-study absolute anchor is authorized by this strategy.

Relative-to-absolute reconstruction, if eventually used, requires a compatible absolute anchor and an explicit measurement-response model. Such values must be labeled inferred and carry anchor/normalization uncertainty; they are not new independent measurements. The imported JBC data do not directly measure the missing NAD(H)/NADP(H) pools or all latent PPP states. Its predicted 2,3-DPG channel must not be relabeled as experimental supervision.

Primary observables remain extracellular glucose/lactate and other measured extracellular metabolites, complemented by intracellular glycolysis, PPP, ATP-ADP-AMP and measured redox indicators where available. Allocate entire donors/trajectories to development or validation before teacher construction; preserve within-donor temperature pairing when confirmed.

## Objective 2: Construct A Documented Dynamic Reduction Of RBC-GEM

Retain the dynamic pathways needed for the observables: transport, glycolysis, oxidative/nonoxidative PPP, Rapoport-Luebering, adenylates/purines and supported redox mechanisms. Include additional pathways only when they affect conserved pools, measured exchanges or testable predictions.

For every retained AIRBC rate, record the pinned GEM reaction(s), metabolite identities, compartment, gene/enzyme/complex, direction, conservation checks and kinetic-law provenance. Mark reactions as retained, composite, omitted, lumped or externally buffered. A lumped reaction needs explicit stoichiometric justification and a declared approximation, not just a matching name.

Check amount balances before converting to concentration derivatives. For a variable-volume measured pool, use d(VC)/dt = V dC/dt + C dV/dt; concentration slopes alone are not automatically fluxes. Check carbon, nitrogen, phosphate, cofactor/carrier and electron-equivalent budgets on the relevant biochemical representation. Proton/charge conventions and pH coupling require their own explicit contract.

Keep recent corrections reversible until their observation/kinetic contracts are satisfied: VCSE has an explicit C4 product, methyl and methylene folates are distinct, and redox acceptors/regeneration are finite. OPLAH remains in the working hypothesis despite its older GEM exclusion; protein detection alone does not fix its catalytic activity. No artificial ATP source or untracked cofactor sink is allowed.

Deliverable: a versioned reduced-network map, executed stoichiometric matrix and boundary/observation registry sufficient to reproduce the dynamic reduction independently of a catalogue label.

## Objective 3: Use Proteomics To Constrain Effective Vmax

For an enzyme with compatible absolute active-site concentration:

\[
V_{\max,r}\;[\mathrm{mM/day}]
= 86400\; k_{\mathrm{cat},r}\;[\mathrm{s}^{-1}]
\; E_{\mathrm{active},r}\;[\mathrm{mM}].
\]

E_active requires copy-number/amount conversion, measured volume where needed, complex stoichiometry, catalytic sites and an uncertain active fraction. Isoenzymes and shared capacities require explicit allocation. In particular, one enzyme catalyzing several reactions must not receive its full measured capacity independently in every branch.

Use the relationship as a soft prior or an effective-capacity parameterization, not a deterministic conversion of protein intensity into Vmax. kcat, active fraction, pH, temperature and regulatory context are not supplied by abundance alone. Their product may be identifiable even when its individual factors are not. Preserve alternative proteomic calibrations and their uncertainties rather than choosing the one yielding the best ATP fit.

Start from established AIRBC kinetic laws. Freeze unsupported Km/equilibrium terms provisionally, with sensitivity checks and explicit uncertainty. Release a small number of capacity factors or specific affinity terms only when the observations can distinguish them. Proteomics does not initialize NAD(H), NADP(H), heme or other unmeasured metabolite pools.

## Objective 4: Validate Predictions Against Unused Evidence

Separate four levels of evidence:

1. Structural verification: biochemical identities, stoichiometry, compartments and enzyme mapping.
2. Numerical verification: positivity of raw accepted states, executed reaction closure, quadrature, solver convergence and threshold sensitivity.
3. Quantitative prediction: unforced concentration trajectories, endpoints and integrated flux balances on held-out donors/conditions with compatible observation operators.
4. Biological benchmarking: agreement with independently supported pathway responses and population associations; this is not automatically quantitative ODE validation.

The population atlas is useful for the fourth level and potentially the third if matching source measurements are accessible. If atlas observations inform network choice, priors, initialization or parameter selection, those observations are development evidence. Reserve genuinely unused donors/cohorts/conditions for validation and document any RBC-Omics overlap with RBC-GEM proteomics. A new article or DOI does not create a new independent cohort.

AIRBC currently does not have a validated observation model for clinical hemoglobin increments, donor activity or hemolysis. Matching an ATP or redox trend does not validate prediction of those outcomes. Any later endpoint model needs explicit design and its own held-out test.

## FLA And The Computational Budget

FLA remains the bridge from concentration dynamics to the executable ODE: learn identifiable net balances or flux intervals, constrain a restricted parameter scope, then test the candidate in continuous unforced simulation. Do not assign a unique flux to an underdetermined internal balance; keep nullspace/latent-state uncertainty explicit.

Concentrations and teachers derived from them are correlated evidence. Joint penalties are permitted as declared supervision, but they must not be reported as independent experimental likelihoods. GEM-predicted fluxes are optional structural feasibility information, not replacements for concentration-derived experimental constraints.

Reduce cost by auditing observation support and parameter reachability first, screening sensitivity/identifiability, testing synthetic recovery, and fitting a few effective capacities. Short-horizon checks can reject infeasible candidates cheaply; surviving candidates still require free J1-J46 replay and whole-network safeguards. Proteomic priors can narrow the search but do not remove the need for kinetic calibration or guarantee ATP recovery.

## Next Deliverables And Decision Gates

1. Create the joint source/role/cohort manifest and resolve local storage-table lineage, JBC compartment/volume equations and usable atlas measurements. Freeze held-out partitions before any multi-source fitting.
2. Rebuild augmented FLA observation/balance constraints against the corrected network; separate measurable net balances from unidentifiable internal fluxes and latent pools.
3. Audit shared enzyme capacities, active-pool units and small-pool limiter sensitivity; run synthetic recovery for the proposed small parameter scope.
4. Fit only a declared identifiable scope, using soft capacity priors; benchmark against the unchanged seed under identical observation and numerical contracts.
5. Evaluate unforced held-out predictions and report source-specific uncertainty and failures, including ATP-ADP-AMP partitioning.

Declare success only with reproducible network/measurement mappings, validated executed balances, parameters supported by recovery/uncertainty analysis, and improvement on predeclared held-out observables without violating other measured pools. Specify numerical and predictive acceptance limits before selecting candidates; do not fabricate thresholds from unavailable experimental errors.

## What This Pass Changes

This pass formalizes objectives and source roles. It does not merge datasets, activate new reactions, convert proteomics, alter initial conditions/kinetics, run an optimizer or promote a model. Historical replays and sealed archives remain the evidence for completed executions. The provisional `reaction_consistent` strict reference remains in place, with `legacy` retained for reproduction. The unresolved ATP partition and existing biological-readiness gates are not waived by the new positioning.
