# Flux Learning Analysis: dynamic flux-supervised calibration of kinetic metabolic models from longitudinal metabolomics

**Provisional article type:** Research article  
**Target journal:** *Metabolic Engineering*  
**Running title:** Flux-supervised calibration of kinetic models  
**Manuscript status:** Working draft; not yet ready for submission  
**Development target:** RBC-GEM-informed reduced dynamic RBC model with source-specific metabolomics and uncertain proteomic capacity priors; integration and independent validation remain prospective.  
**Authors:** [To be completed]  
**Affiliations:** [To be completed]  
**Corresponding author:** [To be completed]

## Highlights

- Flux Learning Analysis converts longitudinal metabolite concentrations into time-resolved teacher fluxes.
- Teacher fluxes supervise kinetic parameter estimation in an executable ordinary differential equation model.
- Concentration, slope, endpoint, flux, and physiological safeguards are evaluated jointly over model days 1-46.
- A red blood cell case study shows why local transport fits must pass whole-network replay before promotion.
- A machine-learning warm-start reduces synthetic calibration loss but remains to be validated on experimental data.

## Abstract

Kinetic metabolic models can predict transient cellular responses and support metabolic or environmental intervention design, but their utility is limited by weakly identifiable parameters. We introduce Flux Learning Analysis (FLA), a dynamic, flux-supervised calibration framework linking longitudinal metabolomics to executable ordinary differential equation (ODE) models. FLA interpolates concentration trajectories, reconstructs teacher fluxes from compartment balances and local stoichiometry, and estimates kinetic constants with an objective combining concentration levels, slopes, endpoints, fold changes, and teacher-flux discrepancies. Candidates must then pass physiological safeguards and whole-model replay.

FLA was implemented in a human red blood cell model with 114 default states, 110 declared reaction or rate identifiers, and 100 reactions in the corrected stoichiometric map. The non-hybrid structural scope exposes 204 parameter names, not 204 independently identifiable constants. A locally curated reference table contained 55 metabolite rows at 14 model time points, J1-J46 (45 elapsed days). Phase A reconstructed 19 extracellular teacher fluxes; glucose import and lactate export achieved heuristic confidence scores of 0.845 and 0.871. A depletion-gated glucose transport hypothesis reduced extracellular glucose normalized root-mean-square error from 0.404 to 0.101 and moved its terminal concentration from 24.90 to 13.21 mM, compared with 12.92 mM in the reference table. However, intracellular glucose and lactate errors deteriorated from 0.358 to 8.281 and from 0.216 to 0.957. Subsequent audits exposed two omitted reactions in the FLA parser and distinguished exact executed balances from numerical corrections near depleted pools. No candidate has yet achieved whole-model predictive validation.

FLA thus provides an auditable route from concentration dynamics to kinetic hypotheses while exposing structural mismatch that concentration-only calibration can conceal. External and prospective validation remain required.

**Keywords:** kinetic modeling; metabolic flux; longitudinal metabolomics; parameter estimation; red blood cell storage; ordinary differential equations; machine learning; model calibration

## Abbreviations

| Abbreviation | Definition |
|---|---|
| FBA | Flux Balance Analysis |
| dFBA | dynamic Flux Balance Analysis |
| FLA | Flux Learning Analysis |
| MFA | Metabolic Flux Analysis |
| ODE | ordinary differential equation |
| PCHIP | piecewise cubic Hermite interpolating polynomial |
| RBC | red blood cell |
| nRMSE | normalized root-mean-square error |
| PPP | pentose phosphate pathway |
| TPE | tree-structured Parzen estimator |

## 1. Introduction

Metabolic engineering increasingly relies on computational models to identify pathway bottlenecks, prioritize interventions, and predict the consequences of genetic, media, or environmental perturbations. Constraint-based approaches, particularly Flux Balance Analysis (FBA), provide a scalable description of feasible steady-state flux distributions through the relation $S v = 0$, where $S$ is the stoichiometric matrix and $v$ is the reaction-flux vector [1]. Dynamic FBA extends this framework by coupling successive constraint-based solutions to extracellular dynamics [2]. These methods are powerful when kinetic information is limited, but they do not directly identify the kinetic constants required to simulate transient intracellular metabolite dynamics.

Kinetic ODE models address a complementary question. They represent reaction rates as explicit functions of concentrations and parameters, thereby enabling prediction away from steady state. Their practical limitation is parameter identifiability: multiple combinations of maximal rates, Michaelis constants, equilibrium terms, and regulatory coefficients may reproduce a subset of measured concentrations while generating incompatible internal fluxes. The resulting models can fit observations locally yet fail when transferred to a new condition or used to predict a pathway intervention.

Longitudinal metabolomics contains more mechanistic information than concentration levels alone. For a measured pool, its temporal derivative constrains the net balance of the reactions that produce or consume it. Directly measured extracellular pools can be particularly informative because their balances may contain a single transport flux. Previous studies have combined metabolite derivatives, stoichiometric balances, and kinetic laws to infer storage-dependent glycolytic fluxes in donated blood [3]. However, a general workflow is still needed to turn such inferred fluxes into supervision for parameter estimation, to reinsert the learned parameters into the original ODE, and to reject locally attractive solutions that damage unoptimized pathways.

We introduce **Flux Learning Analysis (FLA)** as this workflow. The name deliberately echoes FBA while denoting a different mathematical task. FBA searches for feasible flux states under stoichiometric constraints, whereas FLA learns kinetic parameters from dynamic concentration-derived flux information. FLA does not replace FBA, dFBA, isotope-based MFA, or kinetic modeling. It connects longitudinal metabolomics to a kinetic model through four operations: (i) infer concentration derivatives and teacher fluxes; (ii) calibrate a restricted, mechanistically selected parameter scope; (iii) replay the learned parameters in the unforced ODE; and (iv) promote a candidate only if target and whole-network safeguards pass.

Stored RBCs provide a demanding proof of concept. Refrigerated storage drives progressive changes in glycolysis, redox metabolism, purine metabolism, amino-acid pools, and extracellular exchange [4,5]. Mature RBCs lack transcriptional adaptation and are therefore especially suitable for studying regulation through enzyme kinetics, transport, substrate availability, pH, and storage-medium composition. A kinetic erythrocyte model can consequently support metabolic-engineering questions such as storage-media formulation, nutrient supplementation, or environmental control, provided that its parameters remain predictive across conditions. The current AIRBC implementation builds on established RBC reconstructions and kinetic modeling efforts [6,7].

The development program now has four complementary objectives: reconcile source-specific metabolic observations; document a reduced dynamic network against RBC-GEM while retaining justified AIRBC kinetic laws; constrain identifiable effective capacities with uncertain proteomic information; and evaluate predictions against genuinely unused measurements. FLA provides the parameter-learning bridge between the reconciled observations and the executable ODE. Completed work implements teacher-flux construction, restricted calibration, native flux replay and balance auditing, with glucose/lactate case studies over model days 1-46. Proteomic kinetic integration and independent predictive validation remain prospective. Accepted and rejected hypotheses distinguish transport, downstream coupling and structural mismatch; synthetic machine-learning tests are reported separately from biological validation.

## 2. Materials and methods

### 2.1. Study design and FLA phases

FLA was organized as a staged analysis rather than a single global optimization:

1. **Phase 0, model and data audit:** map measured metabolites to ODE states, parse the model stoichiometry, define units and time support, and establish immutable seed parameters.
2. **Phase A, flux learning:** interpolate experimental concentration curves, estimate derivatives, reconstruct identifiable teacher fluxes, and assign confidence weights.
3. **Phase B, kinetic calibration:** optimize a restricted parameter set against concentrations and teacher fluxes, then reinsert the resulting constants into the original ODE.
4. **Phase C, machine-learning warm-start:** learn a mapping from concentration/flux features to parameter seeds using simulated perturbations.
5. **Phase D, transfer and prospective validation:** evaluate retained hypotheses on independent datasets and perturbed storage conditions.

Only Phases 0-A and the core components of Phase B are experimentally instantiated in the current study. Phase C has passed synthetic smoke tests but has not yet demonstrated benefit on experimental calibration. Phase D datasets have been standardized and used for preliminary transfer diagnostics, but independent validation has not been completed.

### 2.2. Experimental datasets

#### 2.2.1. Primary longitudinal reference dataset

The primary calibration dataset is the locally curated AIRBC "Bordbar reference" table (`Data_Bordbar_et_al_exp.xlsx`, Sheet1). It contains 55 model-mapped intracellular and extracellular rows at 14 model time points, J1-J46, spanning 45 elapsed days. A [primary reanalysis of Bordbar data](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005424) reports 14 observations over 45 days, but the exact local sampling origin and row mapping remain unverified. This compatibility does not establish that every local value is an original measurement. No time offset, endpoint exclusion or normalization is applied. The first available observation initializes measured ODE states. Concentrations retain the nominal `Conc / mM` label. Nineteen extracellular species have direct balance rules in the current model:


\[
\mathrm{EADE, EASN, ECIT, ECYS, EFUM, EGLC, EGLN, EGLU, EGSSG, EGSH,}
\]

\[
\mathrm{EHYPX, EINO, ELAC, EMAL, EARG, EURT, EXAN, EOXOP, ESER}.
\]

The current repository does not preserve sufficient metadata to reconstruct donor number, aggregation, analytical variance, and every transformation used to produce this local table. In addition, the filename attribution must be reconciled with the primary experimental publication before submission. The present manuscript therefore reports computational method development on this reference table and does not treat it as a fully documented clinical cohort.

#### 2.2.2. Secondary Bardyn datasets

Two standardized tables represent a control condition and a condition labeled "UA-AA supplemented" in the local source workbook. The exact supplement composition must be confirmed from the primary study before submission. Each table contains 98 mapped rows at storage days 2, 8, 15, 29, and 43, but this is not the number of independently observed metabolites. A conservative manifest excludes all-1.0 rows as suspected placeholders, retaining 40 control and 37 supplemented rows. This heuristic must be replaced by source-level missingness metadata before external scoring. These paired conditions are intended for transfer evaluation and intervention prediction; they were not pooled with the primary dataset during the current parameter searches.

#### 2.2.3. Secondary Michel dataset

The standardized Michel table contains 28 mapped metabolites at storage days 2, 15, 22, 36, and 43. Local stoichiometric inference identifies 60 candidate reactions from 28 measured balances, with matrix rank 22. The system is therefore underdetermined and is used for transfer diagnostics rather than as a source of uniquely identified internal fluxes. A preliminary replay initializes the model with Michel day-2 measurements and simulates to day 43.

#### 2.2.4. Separation of training and validation

The primary reference dataset is used for teacher-flux construction, kinetic-hypothesis testing, and whole-panel replay. Bardyn and Michel are held out from parameter selection. This separation avoids mixing storage protocols, initial conditions, and analytical scales before dataset-specific measurement models are available. No claim of cross-dataset predictive validity is made at the current stage.

### 2.3. Kinetic red blood cell model

The AIRBC model is an ODE representation of human RBC metabolism. The September 8 audit contains 114 default dynamic states (113 biochemical concentration states and intracellular pH), 110 declared reaction or rate identifiers, 100 reactions with explicit nonzero stoichiometric contributions parsed from the ODE, and 204 parameter names exposed to the non-hybrid structural calibration map. The source declares 283 parameter keys including switches and helper options; these counts do not imply identifiability. Pathways include glycolysis, the Rapoport-Luebering shunt, the PPP, purine salvage, glutathione/redox metabolism, amino-acid reactions, and extracellular transport.

Let $x(t)\in\mathbb{R}^{n_x}$ denote the concentration vector, $v(x,t;\theta)\in\mathbb{R}^{n_v}$ the vector of kinetic rates, $S\in\mathbb{R}^{n_x\times n_v}$ the stoichiometric matrix, and $b(x,t;\theta)$ non-reaction source, degradation, pH, or boundary terms. The model is

\[
\frac{dx}{dt}=S\,v(x,t;\theta)+b(x,t;\theta), \tag{1}
\]

where $\theta$ contains maximal rates, Michaelis constants, transport terms, and regulatory coefficients. Candidate parameters are passed to the ODE as an explicit dictionary formed by merging the frozen seed with candidate overrides. A key absent from the final dictionary falls back to the ODE default, not necessarily to the campaign seed. Kinetic-family switches, initialization provenance, and parser revision are therefore part of the replay contract.

Simulations use `scipy.integrate.solve_ivp` with LSODA or BDF, as recorded for each campaign [8]. Recent purine and segmented diagnostics used BDF. Unless otherwise noted, the calibration horizon is day 1 to day 46. The targeted 46-day campaigns reported here used relative tolerance $3\times10^{-4}$ and absolute tolerance $10^{-6}$; the generic calibration engine and Phase C smoke tests used $10^{-5}$ and $10^{-7}$ unless a run artifact stated otherwise. Strict recent replays used $10^{-7}$ and $10^{-9}$. Direct experimental forcing was disabled (`curve_fit_strength = 0`). Observation resets, when used for diagnostic training studies, are reported separately and never count as continuous predictive replay.

The model includes non-negativity handling near depleted pools. Since this handling can alter the derivative close to the concentration floor, exact balance audits either remain above that floor or explicitly account for the damping term. All promoted-model decisions are based on unforced ODE trajectories.

### 2.4. Stoichiometric extraction and model consistency

To prevent a separately maintained stoichiometric table from drifting away from the executable model, FLA extracts reaction coefficients directly from the ODE source. For every state equation, the parser records the signed coefficient of each named flux. It also links reaction expressions to their referenced kinetic parameters. The parsed matrix is validated against the state and reaction registries before flux inference or automatic parameter scoping.

This single-source strategy supports two distinct operations. First, it determines which parameters are stoichiometrically reachable from the measured metabolites. Second, it reconstructs exact pool balances during replay. For example, the implemented glycolytic investment-phase balances are

\[
\frac{d[\mathrm{G6P}]}{dt}=V_{\mathrm{HK}}-V_{\mathrm{PGI}}-V_{\mathrm{G6PDH}}, \tag{2}
\]

\[
\frac{d[\mathrm{F6P}]}{dt}=V_{\mathrm{PGI}}+V_{\mathrm{TKL2}}+V_{\mathrm{TAL}}-V_{\mathrm{PFK}}. \tag{3}
\]

Equations (2) and (3) are generated from the same reaction terms used by the solver and are not manually reconstructed from pathway diagrams.

#### 2.4.1. Network versioning and biochemical integrity audit

The executable network is assigned a version identifier whenever its reaction or stoichiometric contract changes. The present executable version is `airbc-rbc-2026.09.04`, with structural parser schema revision 2 from September 8. The parser revision restores V6PGD and V23DPGP without changing the ODE equations. An earlier audit corrected S-adenosylmethionine synthesis from a legacy implementation that produced AMP in addition to ADOMET. The corrected adenylate balance uses

\[
\mathrm{MET}+\mathrm{ATP}\rightarrow\mathrm{ADOMET}+P_i+PP_i,
\]

so the ATP adenosyl group is transferred to ADOMET and AMP is not a coproduct. The legacy behavior remains selectable solely for exact replay of earlier campaigns. First-order extracellular GSH and GSSG losses were also promoted from anonymous derivative terms to explicit `VEGSH_deg` and `VEGSSG_deg` reactions, making them visible to stoichiometric reachability, teacher construction, and balance closure.

Initial-state provenance is stored separately from kinetic parameters. Three reversible policies are available: the historical legacy policy, a compartment-strict policy with generic priors for unmeasured states, and a compartment-strict policy using exact values from the historical JA table before applying exact primary-data overrides. The legacy policy contains five cross-compartment aliases and is retained for replay compatibility. Strict policies do not infer an intracellular value from an extracellular row, or conversely. They are diagnostic priors rather than promoted initial-state estimates.

The primary table contains two pointwise-identical row pairs, B13PG/B23PG and P2G/P3G. To prevent duplicated measurements from receiving double weight, B13PG and P2G are quarantined as non-independent observations in whole-panel aggregate scores, while B23PG and P3G are retained as representatives. All four raw trajectories remain available for provenance review; this quarantine does not assert which original labels are biologically correct.

### 2.5. Phase A: concentration interpolation and derivative estimation

For metabolite $i$, the observations are $\{t_k,C_{i,k}\}_{k=1}^{K}$. Time points are sorted, duplicates and non-finite series are rejected, and a shape-preserving PCHIP interpolant is fitted [9]:

\[
\widehat C_i(t)=\operatorname{PCHIP}\left(\{t_k,C_{i,k}\}_{k=1}^{K}\right). \tag{4}
\]

The derivative is evaluated analytically from the interpolating polynomial rather than by finite differences:

\[
\widehat{\dot C}_i(t)=\frac{d\widehat C_i(t)}{dt}. \tag{5}
\]

PCHIP was selected because it limits the overshoot that unconstrained cubic splines can introduce between monotone observations. For the primary teacher dataset, derivatives were evaluated on a dense grid spanning the complete experimental interval. PCHIP does not remove experimental noise or quantify derivative uncertainty; its limitations are addressed through confidence weighting and, prospectively, bootstrap resampling.

### 2.6. Direct extracellular teacher fluxes

When an extracellular pool has a single transport term, its flux is structurally identifiable from Eq. (1). For extracellular glucose and lactate, the implemented balances are

\[
\frac{d[\mathrm{EGLC}]}{dt}=-V_{\mathrm{EGLC}}, \qquad
V^{T}_{\mathrm{EGLC}}(t)=-\widehat{\dot C}_{\mathrm{EGLC}}(t), \tag{6}
\]

\[
\frac{d[\mathrm{ELAC}]}{dt}=V_{\mathrm{ELAC}}, \qquad
V^{T}_{\mathrm{ELAC}}(t)=\widehat{\dot C}_{\mathrm{ELAC}}(t), \tag{7}
\]

where superscript (T) denotes a teacher flux. Equivalent sign rules are defined for the other measured extracellular species. For extracellular glutathione pools with a first-order degradation term,

\[
\frac{dC_i}{dt}=s_i v_i-k_i C_i,
\]

the corrected teacher is

\[
v_i^T(t)=s_i\left[\widehat{\dot C}_i(t)+k_i\max(\widehat C_i(t),0)\right], \tag{8}
\]

with $s_i\in\{-1,+1\}$ set by the model convention.

Teacher fluxes have units of concentration per day under the current compartment scaling. They are effective net transport rates. Conversion to amount per cell, packed-cell volume, or enzyme-specific activity requires additional volume and hematocrit metadata that are not yet included.

### 2.7. Local inference for non-singleton balances

For a selected set of measured metabolites (I), FLA writes

\[
\widehat{\dot x}_I(t)=S_{I,J}v_J(t)+r_I(t), \tag{9}
\]

where $J$ contains reactions touching the measured pools and $r_I$ contains contributions from already resolved reactions. Fluxes are first propagated through singleton rows. If only one unresolved reaction $j$ remains in row $i$,

\[
v_j^T(t)=\frac{\widehat{\dot x}_i(t)-\sum_{\ell\neq j}S_{i\ell}v_\ell^T(t)}{S_{ij}}. \tag{10}
\]

At each time point, remaining fluxes are estimated by bounded linear least squares:

\[
\widehat v_U(t)=\arg\min_{v_U}\left\|S_{I,U}v_U-r_I(t)\right\|_2^2, \tag{11}
\]

subject to $v_j\geq0$ for reactions declared irreversible. Reactions explicitly marked reversible are unbounded in sign. The current implementation does not add temporal regularization to Eq. (11); smoothness is evaluated after inference. Consequently, underdetermined internal fluxes are treated as exploratory constraints and receive less evidential weight than direct extracellular singleton fluxes.

Balance diagnostics include RMSE, nRMSE, $R^2$, matrix rank, and rank fraction. These diagnostics assess algebraic reconstruction and do not establish biological uniqueness.

### 2.8. Teacher-flux confidence and weighting

For a direct extracellular teacher $v^T$, FLA computes sign consistency $q_{\mathrm{sign}}$, smoothness $q_{\mathrm{smooth}}$, and relative signal $q_{\mathrm{signal}}$. Smoothness is

\[
q_{\mathrm{smooth}}=
\left(1+
\frac{\operatorname{median}|\Delta^2v^T|}
{\operatorname{median}|\Delta v^T|+\varepsilon}
\right)^{-1}, \tag{12}
\]

and relative signal is

\[
q_{\mathrm{signal}}=
\frac{\operatorname{mean}|v^T|}{\max|v^T|+\varepsilon}. \tag{13}
\]

The current heuristic confidence score is

\[
q_v=\operatorname{clip}_{[0,1]}
\left(0.20+0.45q_{\mathrm{sign}}+0.25q_{\mathrm{smooth}}+0.10q_{\mathrm{signal}}\right). \tag{14}
\]

The base teacher weight is $\max(0.10,q_v)$, followed by explicit hypothesis-level emphasis where declared before optimization. For internal least-squares fluxes, confidence also depends on balance $R^2$ and matrix rank. Equation (14) is an engineering reliability score, not a calibrated probability. A future version will replace or augment it with replicate-aware derivative uncertainty and bootstrap confidence intervals.

### 2.9. Phase B: flux-supervised kinetic calibration

#### 2.9.1. Simulated concentrations and flux replay

For candidate parameters $\theta$, the unforced ODE is solved to obtain $x(t;\theta)$. Simulated concentration targets are sampled at experimental times. For teacher comparison, dense states are replayed through the native ODE flux expressions, yielding $v_j(t;\theta)$ with exactly the same rate laws, modifiers, and sign conventions as the state simulation. Flux replay is cached by parameter vector to avoid repeated ODE and rate-law evaluations.

#### 2.9.2. Concentration loss

For each concentration target $i$, the normalization factor is

\[
a_i=\max\left(\frac{1}{K}\sum_{k=1}^{K}|C_{i,k}^{\mathrm{exp}}|,0.01\right). \tag{15}
\]

The level term is a weighted mean of capped nRMSE values:

\[
J_{\mathrm{level}}=
w_{\mathrm{level}}
\frac{\sum_i\omega_i
\min\left(\operatorname{RMSE}(C_i^{\mathrm{sim}},C_i^{\mathrm{exp}})/a_i,c_i\right)}
{\sum_i\omega_i}. \tag{16}
\]

Piecewise slopes between experimental points are compared similarly:

\[
J_{\mathrm{slope}}=
w_{\mathrm{slope}}
\frac{\sum_i\omega_i
\min\left(\operatorname{RMSE}(\Delta C_i^{\mathrm{sim}}/\Delta t,
\Delta C_i^{\mathrm{exp}}/\Delta t)/a_i,c_i\right)}
{\sum_i\omega_i}. \tag{17}
\]

Endpoint and fold-change terms are

\[
J_{\mathrm{endpoint}}=
w_{\mathrm{end}}
\frac{\sum_i\omega_i
|C_{i,K}^{\mathrm{sim}}-C_{i,K}^{\mathrm{exp}}|/a_i}
{\sum_i\omega_i}+J_{\mathrm{focused\ end}}, \tag{18}
\]

\[
J_{\mathrm{fold}}=
w_{\mathrm{fold}}
\frac{\sum_i\omega_i
\left|log\frac{C_{i,K}^{\mathrm{sim}}+\varepsilon}{C_{i,1}^{\mathrm{sim}}+\varepsilon}
-\log\frac{C_{i,K}^{\mathrm{exp}}+\varepsilon}{C_{i,1}^{\mathrm{exp}}+\varepsilon}\right|}
{\sum_i\omega_i}. \tag{19}
\]

Default coefficients are $w_{\mathrm{level}}=1.0$, $w_{\mathrm{slope}}=0.35$, $w_{\mathrm{end}}=0.50$, and $w_{\mathrm{fold}}=0.30$. Hypothesis-specific runs can increase the slope or endpoint emphasis for a declared target such as EGLC. All run-specific weights are persisted with the results.

#### 2.9.3. Teacher-flux loss

For teacher reaction $j$, the flux normalization factor is

\[
b_j=\max\left(\operatorname{mean}|v_j^T|,0.01\right). \tag{20}
\]

The flux loss is

\[
J_{\mathrm{flux}}=
\frac{\sum_j q_j
\min\left(\operatorname{RMSE}(v_j(t;\theta),v_j^T(t))/b_j,c_j^v\right)}
{\sum_j q_j}. \tag{21}
\]

An analogous $J_{\mathrm{teacher\ curve}}$ is available when dense interpolated concentration curves are used as teacher targets. The primary FLA objective is

\[
J_{\mathrm{fit}}(\theta)=
J_{\mathrm{level}}+J_{\mathrm{slope}}+J_{\mathrm{endpoint}}+J_{\mathrm{fold}}
+\lambda_CJ_{\mathrm{teacher\ curve}}+\lambda_VJ_{\mathrm{flux}}. \tag{22}
\]

Targeted campaigns may instantiate a declared subset of Eq. (22). The key 46-day transport campaign omitted the fold-change and dense teacher-curve terms and used

\[
J_{\mathrm{transport}}=J_{\mathrm{level}}+4J_{\mathrm{EGLC\ slope}}
+16J_{\mathrm{EGLC\ end}}+2J_{\mathrm{ELAC\ end}}+3J_{\mathrm{flux}}, \tag{23}
\]

with EGLC/ELAC concentration weights of 3.0/1.5 and VEGLC/VELAC teacher-flux weights of 8.0/3.0. The minimum simulated EGLC depletion fraction was fixed at 0.05 before optimization.

The fitted parameter vector is

\[
\theta^*=\arg\min_{\theta\in\Omega}J_{\mathrm{fit}}(\theta), \tag{24}
\]

where $\Omega$ is a bounded, hypothesis-specific parameter domain.

#### 2.9.4. Regularization and physiological penalties

A diagnostic regularization term penalizes logarithmic deviation from the seed:

\[
R(\theta)=\sum_{p\in P}\rho_p
\left[\log_{10}\left(\frac{\theta_p}{\theta_{p,0}}\right)\right]^2. \tag{25}
\]

Weights $\rho_p$ depend on parameter class and identifiability risk. Physiological penalties monitor energy, redox, purine, and concentration floors. In the current fit-first ranking policy, Eq. (22) ranks candidates, while regularization and physiological penalties are reported as guardrail diagnostics. This separation prevents an arbitrary penalty weight from silently compensating for a poor experimental fit. Hard promotion gates remain mandatory.

### 2.10. Parameter scope, optimization, and reversibility

Parameters are not opened globally at the start. Each run declares a mechanistic hypothesis and the smallest parameter subset capable of testing it. Examples include transport-only $V_{\max,\mathrm{EGLC}}$ and $V_{\max,\mathrm{ELAC}}$, fixed glucose-transport gating followed by $V_{\max,\mathrm{HK}}$, or a single Michaelis constant such as $K_{m,\mathrm{ATP,HK}}$. Reachability from measured states is obtained from the parsed stoichiometry, but biological judgment defines the final scope.

Optimization uses Optuna with a TPE sampler and median pruning when available [10], with differential evolution as a fallback. Campaigns may separate maximal-rate and affinity stages, include deterministic seed or multiplier anchors, and use local bounds around the seed before any broader search. Random seeds, bounds, objective weights, solver settings, and every trial are stored.

Alternative kinetic families are implemented behind explicit options. The default rate law and seed parameter file remain unchanged, and each hypothesis writes to a separate output directory. This makes depletion gates, transport feedback, asymmetric transport, or reversible PPP hypotheses directly reversible. No diagnostic run overwrites the global best-parameter file.

### 2.11. Candidate acceptance and whole-panel safeguards

A candidate must satisfy three levels of evidence:

1. **Direct FLA improvement:** the candidate must improve the predeclared concentration/flux objective relative to its exact seed.
2. **Targeted safeguards:** specified concentrations, endpoints, slopes, and fluxes must remain within run-specific tolerances. For glucose/lactate hypotheses these include EGLC, ELAC, GLC, LAC, ATP, PEP, G6P, F6P, and the VEGLC, VELAC, VLDH fluxes as applicable.
3. **Whole-panel replay:** the candidate is compared with the seed across all 55 mapped primary-reference metabolites. Strong degradation outside the optimized scope blocks promotion.

The terms "accepted locally," "retained as a hypothesis," and "promoted globally" are distinct. A locally accepted candidate may be used as the fixed seed of the next mechanistic diagnostic without being promoted as the model default.

### 2.12. Native flux and balance audits

When a kinetic perturbation changes ATP or an intermediate unexpectedly, each solved state is replayed through the native flux tracker. For pool $i$, closure is evaluated pointwise as

\[
\epsilon_i(t)=\dot x_i^{\mathrm{ODE}}(t)-
\left(\sum_jS_{ij}v_j(t;\theta)+b_i(t)\right). \tag{26}
\]

Window-integrated production, consumption, and net terms are also calculated. This audit distinguishes an algebraic omission from an imbalance among correctly implemented flux magnitudes. ATP production and consumption are decomposed by reaction before another kinetic parameter is opened.

### 2.13. Observation provenance, temporal ownership, and identifiability mask

The local primary-reference workbook was treated as a curated model-input table rather than a raw replicate-level dataset. File hashes, workbook metadata, sampling times, exact row duplicates, and repository history were recorded before defining the observation contract. Pointwise-identical rows were not counted as independent constraints. B13PG was treated as a latent state while B23PG was retained as the BPG observation. P2G and P3G were excluded from reaction-specific teacher assignment; P3G was retained only as a descriptive representative of the grouped signal. The local day-46 endpoint was not assumed to be a raw measurement because the associated publication describes a 42-day storage study.

Calibration ownership was divided into three sequential windows: J1-J3 for latent initialization, adenylate behavior, and the Rapoport-Luebering shunt; J3-J10 for propagation through upper and lower glycolysis; and J10-J46 for transport and storage preservation. A candidate could enter a later block only after passing the local and protected-target gates of all preceding blocks. Every retained point also required an unforced J1-J46 replay.

Before opening kinetics, a block-specific identifiability mask was constructed from two complementary matrices. First, the measured-pool-by-target-reaction stoichiometric submatrix provided a structural rank. Second, direct kinetic sensitivities were calculated by central finite differences in log-parameter space at fixed states from both the duplicated-data and QSS-B13PG trajectories:

\[
J_{kp}=\frac{1}{s_k}\frac{v_k(x;\theta_p e^h)-v_k(x;\theta_p e^{-h})}{2h},
\qquad h=0.05, \tag{27}
\]

where $s_k$ is the mean absolute baseline flux with a numerical floor. Singular values above $10^{-3}$ of the largest singular value defined the practical local rank, and pivoted QR supplied a nonredundant sensitivity basis. This matrix is a screening device rather than a proof of global identifiability. Accordingly, the basis was further restricted by causal balance attribution, temporal ownership, and one-factor reversibility before defining an optimization scope.

Transport parameters were not reopened during this procedure. Paired intracellular/extracellular transport equations currently use equal-and-opposite concentration coefficients, which conserve amount only under equal effective compartment volumes. Because hematocrit, extracellular volume, and the historical hour-to-day rate conversion were not traceable in the local dataset, current transport constants were interpreted as empirical per-model-day values pending a documented observation model.

### 2.14. Phase C machine-learning warm-start

The optional machine-learning module predicts parameter seeds; it does not replace mechanistic simulation or final optimization. A fixed schema summarizes 17 concentration trajectories using 12 features per metabolite: presence, initial, final, mean, minimum, maximum, log-initial, log-final, log-fold change, maximum absolute slope, normalized time to half-change, and a hill-shape descriptor. Four flux trajectories are summarized using 10 features each: presence, mean, mean absolute value, maximum, minimum, final value, net change, sign changes, smoothness, and log-mean absolute value. The current schema therefore contains $17\times12+4\times10=244$ features.

Synthetic training cases are generated by perturbing a conservative parameter subset, solving the ODE, reconstructing FLA features, and using the known log-parameter multipliers as labels:

\[
y_p=\log\left(\frac{\theta_p}{\theta_{p,0}}\right). \tag{28}
\]

Features are standardized and a multi-output ridge model is fitted:

\[
\widehat B=\arg\min_B\|ZB-Y\|_F^2+\lambda_{\mathrm{ML}}\|B\|_F^2. \tag{29}
\]

The predicted seed is

\[
\theta_p^{\mathrm{warm}}=\theta_{p,0}\exp(\widehat y_p), \tag{30}
\]

clipped to the calibration bounds. Both the default and warm-start branches then receive the same solver, objective, trial budget, and random seed. Phase C is considered useful only if the warm-start branch improves held-out calibration loss without violating the Phase B safeguards.

### 2.15. Evaluation metrics

Concentration and flux fits are reported with RMSE, nRMSE, terminal relative error, and slope error. The primary nRMSE denominator is the mean absolute experimental concentration with a 0.01 floor, matching Eq. (15). Whole-panel reports include the mean and median nRMSE and counts of improved, similar, and regressed metabolites. Structural diagnostics report pointwise balance closure, integrated residuals, reaction shares, and pool production/consumption ratios.

No formal biological hypothesis test is currently reported because replicate-level observations and measurement variances are not available in the local primary table. Quantitative changes are therefore descriptive and computational.

### 2.16. Software and reproducibility

The workflow is implemented in Python using NumPy, pandas, SciPy, and Optuna. Core modules provide the ODE, stoichiometric parsing, extracellular teacher-flux generation, local flux inference, feature extraction, calibration, candidate comparison, and native flux replay. Every campaign stores its seed and candidate parameters, configuration, objective decomposition, trial table, concentration and flux metrics, figures, and a machine-readable summary. All calculations reported here use `curve_fit_strength = 0`.

### 2.17. Interval-integrated teachers and conditional flux attribution

For sparse records, interval balances complement derivative-based supervision. Let a measured pool satisfy $\dot C(t)=r_{\mathrm{known}}(t)+s_u v_u(t)$, with a nonzero stoichiometric coefficient $s_u$. Between two tabulated observation times, the required unknown flux integral is

\[
\widehat I_{u,k}=\frac{C(t_{k+1})-C(t_k)-\int_{t_k}^{t_{k+1}}r_{\mathrm{known}}(t)\,dt}{s_u}. \tag{31}
\]

The model integral is compared with this quantity in mM, using trapezoidal quadrature on an accepted-state replay grid containing both interval boundaries. Missing boundaries, nonfinite observations or rates, and invalid normalization scales are rejected. The implementation does not substitute interpolated endpoints for missing primary support, but source provenance must additionally establish that the table entries themselves are observations.

When $r_{\mathrm{known}}$ contains simulated fluxes, Eq. (31) defines a **conditional teacher**, not an independent experimental flux measurement. Only identifiable flux combinations may be reconstructed without such assumptions. Concentrations, their derivatives, and their interval differences originate from the same data and are statistically dependent; treating all three objectives as independent likelihood terms would overstate information. Current weights are engineering choices pending a covariance-aware observation model.

For irreversibility tests, forward and reverse components must be distinguished. In particular, the signed ATP production group $V_{\mathrm{PGK}}+V_{\mathrm{PK}}+V_{\mathrm{AK}}$ contains reversible net AK. Its negative conditional integral alone does not establish an impossible irreversible reaction.

### 2.18. Observation-reset diagnostics and a prospective multiple-shooting objective

The current diagnostic integrates consecutive observed intervals at fixed kinetics, replaces 52 observed states at each node, and carries latent states forward. B13PG, P2G, and P3G are excluded from resets because of ambiguous duplicate signals. The normalized discontinuity is recorded but not optimized. This is an observation-reset diagnostic, not yet a calibrated multiple-shooting estimator.

A future estimator would infer kinetic parameters and admissible latent shooting states jointly, with an explicit continuity term such as

\[
L_{\mathrm{continuity}}=\lambda_c\sum_k\left\|D_k^{-1}\left[z_{k+1}-\Phi_{\theta}(t_{k+1},t_k,z_k)\right]\right\|_2^2, \tag{32}
\]

where $\Phi_\theta$ is the unforced ODE flow and $D_k$ contains scales determined from the training partition only. Equation (32) is a proposed next experiment, not an implemented optimization result. Node constraints, measurement uncertainty, continuity weights, and parameter scopes must be frozen before a held-out comparison.

Availability of ATP above a diagnostic threshold is quantified by elapsed time, summing piecewise-linear threshold crossings separately within each continuous segment. Resets contribute no duration. This statistic is not a sensitivity rank: local dynamic sensitivities, profile bounds, and predictive transfer must be measured separately. Final validation integrates continuously from one initial condition with no observation resets.

### 2.19. Raw numerical integrity and cumulative validation

The current RHS applies concentration floors and state-wise derivative damping. We distinguish the effective implemented balance from the physical reaction balance using

\[
\delta_{\mathrm{num}}(t)=f_{\mathrm{implemented}}(x,t;\theta)-[S v(x,t;\theta)+b_{\mathrm{physical}}(x,t;\theta)]. \tag{33}
\]

An exact reconstruction including the damping term verifies software consistency but does not prove conservation of the underlying pool. Both raw and effective residuals must be reported. Minimum concentrations are now recorded before output clipping; historical clipped trajectories cannot supply that evidence retroactively. Accepted-state flux replay is also distinguished from raw solver-call logs, which can contain rejected or nonmonotone steps.

Validation policy revision 3 requires data provenance, structural feasibility, identifiable parameter combinations, calibration gain, internal predictive validity, and external predictive validity in cumulative gates. Relative error reduction is insufficient: protected targets must meet predeclared absolute nRMSE limits. Those limits have not yet been justified and frozen for the reference table, so their absence explicitly blocks promotion. Dataset identifiers and nonoverlap are checked, but preprocessing provenance and actual sample partitions remain necessary to rule out leakage. Historical decisions are retained as campaign records, not automatically upgraded to this policy.

### 2.20. Regeneration of PPP constraints and accepted-step numerical budgets

Following the parser correction, structural supervision was rebuilt from the executable stoichiometry. Four measured balances were retained: G6P, GO6P, F6P and B23PG. B13PG and P3G were excluded from independent supervision because of the known duplicate-row ambiguities. Seven additional PPP pools were retained as latent states, not supplied with fabricated observations. For a selected row matrix $A$, singular-value decomposition at a relative threshold of $10^{-10}$ produced its rank and a basis $N$ of its nullspace. An individual reaction flux is structurally identifiable from these balance observations alone only if its corresponding row of $N$ is zero within the declared tolerance. This test concerns flux observability without kinetic priors; it does not establish parameter identifiability.

The observed balances were reconstructed as

\[
\begin{aligned}
\dot{G6P}&=VHK-VPGI-VG6PDH,\\
\dot{GO6P}&=VPGLS-V6PGD,\\
\dot{F6P}&=VPGI-VPFK+VTKL2+VTAL,\\
\dot{B23PG}&=VDPGM-V23DPGP.
\end{aligned}
\]

For each of the 13 intervals between the 14 tabulated reference times, the balance target was the actual endpoint concentration difference. PCHIP derivatives were exported as an alternative temporal representation, not independent observations. Reaction-level requirements conditioned on other simulated fluxes were labeled explicitly, for example $\int V6PGD^{T,\mathrm{cond}}dt=\int VPGLS^{\mathrm{model}}dt-\Delta GO6P^{\mathrm{ref}}$. The analogous F6P construction constrains the sum VTKL2+VTAL, not either reaction individually. Data provenance and nominal concentration units remain part of the unresolved measurement contract.

The archived, unpromoted AMPD1 storage-decay context supplied a frozen complete parameter dictionary and initialization, verified against its saved day-1 state. Continuous BDF integrations over J1-J46 used standard tolerances $(3\times10^{-4},10^{-6})$ and strict tolerances $(10^{-7},10^{-9})$ for relative and absolute error, respectively. No observation resets, curve-forcing term or optimization was used. All 113 concentration balances were replayed from raw accepted states and the accepted-step dense interpolant; neither negative states nor missing fluxes were repaired in the audit exports.

The numerical accounting separated $Sv$, state-wise damping, derivative clipping and any unexplained executed-RHS residual. A positive input floor changes the state supplied to the kinetic laws; its displacement was recorded in concentration units and was not integrated as a material source. Gauss-Legendre quadrature cells were split at accepted solver steps and audit/measurement boundaries. Orders 4 and 8 were compared per pool, quantity and interval using $10^{-6}$ mM absolute plus $10^{-3}$ relative tolerance. Standard/strict budget comparisons used $10^{-5}$ mM absolute plus 1% relative tolerance. The integrated solver residual $\Delta x-\int f_{\mathrm{implemented}}dt$ was reported separately from $\Delta x-\int Sv\,dt$ and from the reference-data residual. Quadrature convergence on one dense solution does not establish convergence across solver tolerances or biological validity.

### 2.21. Opt-in reaction-consistent boundary policy

An alternative boundary policy was implemented without changing the default legacy replay or any kinetic constants. Let $v_j^0$ be the native signed net rate, evaluated with the existing kinetic input floors. Its consumed-state set is $C_j=\{i:S_{ij}v_j^0<0\}$. From unfloored concentrations, the executed rate is

\[
g_i(x)=\min(1,\max(0,x_i/\tau)),\qquad
\alpha_j(x,v_j^0)=\min_{i\in C_j}g_i(x),\qquad
v_j^{\mathrm{exec}}=\alpha_jv_j^0,
\]

with $\tau=10^{-3}$ mM fixed to the existing damping threshold. The empty-set minimum is one. The sign of a negative net rate reverses the consumed-state set; products do not limit incoming production. Each factor multiplies the whole reaction column, so the concentration RHS is $Sv^{\mathrm{exec}}$, not independently damped pool derivatives. For a zero or negative boundary probe, every reaction consuming that state has zero executed net rate. Any left-nullspace invariant $\ell^TS=0$ is preserved by this construction. This mathematical boundary property does not guarantee nonnegative discrete solver states, which remain audited without output clipping.

Native and executed rates, availability factors and $S(v^{\mathrm{exec}}-v^0)$ are exported separately. The latter is a stoichiometric reaction-rate change, not an independent material source or experimental teacher. The method limits signed net rates; it does not reconstruct thermodynamic forward/reverse gross exchange and should not be interpreted as a validated biological regulation mechanism. Kinetic floors still influence the native laws. Observation forcing is rejected under this diagnostic option, and nonfinite or excessively large concentration derivatives cause explicit failure rather than hidden independent clipping. pH production terms use the same executed metabolic rates.

The software switch is `positivity_policy="reaction_consistent"`; omission or `"legacy"` restores the previous behavior. A separate numerical-policy version identifies the diagnostic while the default network and parser versions are unchanged. Fixed-context comparisons are predeclared at J1-J3, J1-J10 and J1-J46, each using standard and strict BDF tolerances and the frozen initialization from Section 2.20. CSV snapshots are parsed with round-trip floating-point precision and required to match the archived binary day-1 state exactly; mismatches cause failure before integration. A preliminary default-precision CSV pass is retained separately, not used for the final decision. Before integration, boundary probes cover all 113 concentrations at the initial state and at nonnegative boundary-test counterparts of archived depleted B13PG/ADP states. This construction is confined to synthetic probes; integrated outputs are never projected. Prediction scores exclude initial observations and duplicated B13PG/P2G rows. J1-J3 contains no postinitial tabulated reference point, so no trajectory nRMSE is invented for that interval. Numerical closure, quadrature accuracy, cross-solver convergence and biological predictive validity remain separate assessments.

### 2.22. Provisional work profile and fixed-kinetic convergence protocol

Following the boundary audit, reaction-consistent limiting was adopted as the explicit provisional numerical reference for new campaign work, not as evidence that the archived kinetic candidate was valid. The working profile specifies BDF with relative/absolute tolerances $10^{-7}/10^{-9}$ and availability threshold $\tau=10^{-3}$ mM. Legacy remains explicitly available for historical replay, and older kernel/API defaults are unchanged. The numerical profile is recorded separately from the kinetic parameter dictionary; neither kinetic constants nor initial conditions are changed or promoted by its adoption.

Before further calibration, six continuous, unforced J1-J46 replays were predeclared: $\tau\in\{10^{-4},10^{-3},10^{-2}\}$ mM, each with strict and ultrastrict BDF tolerances ($10^{-7}/10^{-9}$ and $10^{-8}/10^{-10}$). Frozen parameter and round-trip initialization snapshots, source hashes, solver settings and acceptance controls are persisted before integration. All 113 zero boundaries are checked across three probe contexts at every threshold, giving 1017 probes. Stored native-rate and executed-rate histories are distinguished throughout.

Accepted-step quadrature orders 4 and 8 are compared for 452 pool/quantity and 300 individual reaction/quantity combinations over every experimental/audit interval, with $10^{-6}$ mM absolute plus $10^{-3}$ relative tolerance. Strict/ultrastrict comparisons cover 113 dense concentration trajectories, 113 interval concentration changes, 300 native/executed/modifier reaction-integral quantities and 452 pool-budget quantities: 978 comparisons per threshold. Dense comparisons use the union of both accepted meshes and a fixed 901-point grid. The declared allowance is $10^{-5}$ mM plus 1% of the ultrastrict value, applied pointwise or per interval rather than only to endpoints. Passing requires both replays to meet raw-state, closure and quadrature gates, and all 978 comparisons to pass.

Threshold sensitivity is assessed separately by comparing ultrastrict replays against the $10^{-3}$ mM reference. Such differences describe sensitivity to a rate-law modifier, not solver failure or independently measured regulation. No threshold is selected by concentration loss or teacher-flux loss. Failed checks remain failed evidence, and neither their tolerances nor the calibration block are relaxed. Absolute biological accuracy and source-data contracts remain prerequisites distinct from this numerical verification.

### 2.23. Executed-flux attribution of the B13PG-energy block

After numerical convergence verification, two continuous J1-J46 replays reproduced the strict/ultrastrict working-reference accepted time/state arrays bit-for-bit. No kinetics, initialization, network or availability threshold changed. All nonzero corrected-matrix contributions to B13PG, ATP, ADP and B23PG were reconstructed from executed rates. The B13PG and shunt balances were $dB13PG/dt=v_{GAPDH}^{exec}-v_{PGK}^{exec}-v_{DPGM}^{exec}$ and $dB23PG/dt=v_{DPGM}^{exec}-v_{23DPGP}^{exec}$. For every pool $i$, actual-sign production and consumption were computed before integration:

\[
P_i=\sum_j\max(S_{ij}v_j^{exec},0),\qquad
C_i=\sum_j\max(-S_{ij}v_j^{exec},0),\qquad
\dot x_i=P_i-C_i.
\]

This treatment reverses the contribution of negative AK/NDPK net rates and retains the factor of two for ADP in AK. It is a decomposition of signed net reaction rates, not thermodynamic gross exchange. Budgets cover early subwindows J1-J1.1, J1.1-J1.3, J1.3-J1.6, J1.6-J2 and J2-J3, plus J1-J3, J3-J10, J10-J46 and J1-J46. Overlapping summaries are not additive independent periods. Accepted-step quadrature orders 4/8 and strict/ultrastrict comparisons use the previously declared tolerances, with raw state changes, executed reaction integrals and nonreaction/solver residuals exported separately.

For PGK, DPGM, GAPDH, PK, HK, PFK, AK and NDPK, the absolute native-minus-executed rate reduction was allocated to minimum-availability consumers on the same trajectory; co-minimum ties were split equally. The allocation conserves total rate reduction but is descriptive numerical bookkeeping, not a causal intervention or a metabolic control coefficient. Native rates retain their original concentration floors and remain separately labeled counterfactuals. The GAPDH NAD/(NADH+1e-6) MM factor was recorded with the native floors; NAD/NADH were treated as unobserved initialized states rather than experimental teachers.

Exact tabulated ATP, ADP and B23PG interval changes were compared with executed integrals. Conditional ATP-required PGK was defined as $\Delta ATP_{ref}-\int\sum_{j\ne PGK}S_{ATP,j}v_j^{exec}dt$, holding all other simulated terms fixed. It neither independently identifies PGK nor predicts the effect of changing its kinetics. B13PG was excluded as an independent teacher because of its duplicate B23PG row; no postinitial J1-J3 observation was invented. An independent script used explicitly written balance coefficients, rather than the parsed-matrix helper, to reconcile contributions and allocated-loss totals against the preceding archive.

### 2.24. Joint adenylate and latent-redox feasibility contract before calibration

The precalibration diagnostic was restricted to the first two tabulated endpoints, J1 and J4. Intermediate J2/J3 states were simulated, not independent observations or additional teachers. All kinetic constants, measured initial states, the corrected network and the provisional availability threshold were frozen. For total adenylates $T_A=ATP+ADP+AMP$, the exact executed balance was

\[
\dot T_A=v_{ADSL}^{exec}+v_{AK2}^{exec}+v_{APRT}^{exec}
-v_{SAM}^{exec}-v_{AMPD1}^{exec}-v_{AMP\_NT}^{exec}.
\]

AK contributes $(1,-2,1)$ to ATP/ADP/AMP and therefore has no direct source term in this sum. Its coupled effects on other rates are not excluded. Total-pool closure, individual-pool closure and energy charge $EC=(ATP+0.5ADP)/T_A$ were evaluated separately; energy charge requires nonnegative concentrations and a positive total. Every nonzero AMP and purine-transfer term was included, even if its executed integral was zero. Conditional AK requirements were reconstructed independently from each observed pool change with all other executed terms held fixed. Inconsistent requirements reject only this fixed-neighbor explanation, not global coupled-network feasibility; they are not measured AK fluxes.

NAD+NADH and NADP+NADPH are encoded invariants, but their initial totals are not identified by conservation. The local reference table contains no corresponding redox observations. Four reversible, predeclared NAD/NADH initialization scenarios separated current total/current ratio, historical total/current ratio, current total/historical ratio, and historical total/historical ratio. Historical values were read at full precision from the archived initialization workbook, not assumed to be experimentally validated priors. Only NAD/NADH changed; NADP/NADPH and every other initial state remained bit-identical. No scenario was selected by predictive loss or promoted.

Each scenario used strict and ultrastrict BDF, continuous unforced J1-J4 integration and accepted-step quadrature orders 4/8 over six disjoint subwindows plus their overlapping J1-J4 summary. Full raw concentration positivity, executed reaction closure, state-change/integral agreement, both redox-pair conservation checks and cross-tolerance convergence were required separately from biological accuracy. Source/configuration/code hashes were frozen before replay. The baseline prefix was compared with the preceding verified J1-J46 replay. Independent explicit equations recomputed adenylate budgets, energy charge and conditional AK requirements from saved evidence.

Latent initialization can be parameterized as $N_0=NAD_0+NADH_0>0$, $f_0=NADH_0/N_0\in[0,1]$, with $NAD_0=N_0(1-f_0)$ and $NADH_0=N_0f_0$. This mathematical domain alone is not a biologically supported prior. Joint endpoint feasibility requires $|x_i(4)-y_i(4)|\le\epsilon_i$ for every $i\in\{ATP,ADP,AMP\}$, not merely a favorable total or weighted-average error. The $\epsilon_i$ and the admissible prior support for $(N_0,f_0)$ must be justified and frozen before fitting; neither was estimated from these four diagnostic runs.

The machine-readable feasibility contract records unknown upstream lineage, normalization, measurement uncertainty, biological time origin, redox-prior bounds and absolute accuracy limits explicitly. None can be inferred from solver convergence. Numerical success permits interpretation of this diagnostic only; unresolved scientific prerequisites keep calibration disabled. No optimizer, artificial ATP source, observation reset or concentration clipping was introduced.

### 2.25. Evidence-backed scientific readiness and a prepared coupled sensitivity protocol

A separate precalibration configuration records source lineage, concentration normalization, biological time origin, joint observation uncertainty, absolute endpoint accuracy requirements and latent redox prior support. Each verified claim requires supporting files with unchanged hashes and substantive fields, not a saved Boolean flag. The guard reevaluates the actual contract and files before an endpoint decision; modified limits or evidence invalidate prior readiness. Its scope is the J1-J4 diagnostic campaign, not a silent migration of historical runners or the whole platform.

Uncertainty is represented in the fixed order $(ATP_1,ADP_1,AMP_1,ATP_4,ADP_4,AMP_4)$ by a full covariance $C$ in model mM$^2$. The estimator, estimand, biological unit count and technical replicate count must be documented. Covariance validity is checked relative to its own scale, including symmetry, nonnegative variances, permissible correlations and positive semidefiniteness. Unknown cross-pool or cross-day covariance is not replaced by independence. For $a=(-1,-1,-1,1,1,1)^T$ and $D=(-I,I)$,

\[
\operatorname{Var}(\Delta T_A)=a^TCa,\qquad
\operatorname{Cov}(\Delta ATP,\Delta ADP,\Delta AMP)=DCD^T.
\]

At each endpoint, energy-charge variance is approximated by $g^TCg$ using its embedded gradient $g_i=(w_iT_A-Q)/T_A^2$, $w=(1,0.5,0)$ and $Q=ATP+0.5ADP$. This is first-order nonlinear propagation, not an exact interval. Deterministic, documented normalization factors transform covariance by $AC_{source}A^T$; uncertain normalization requires joint propagation. The code does not infer acceptance thresholds from this covariance automatically. Absolute endpoint tolerances in mM must instead follow a justified measurement-supported rule or a separately predeclared prediction requirement, independently of fitted model error. They do not replace full-panel nRMSE guards.

The redox contract requires supported NAD-total/fraction bounds in the same volume basis and pool definition as the model and checks whether the frozen baseline lies inside them. Free reaction-available NAD(H) and total extractable NAD(H) are not interchangeable, as demonstrated experimentally by [Simpson et al.](https://www.cruk.cam.ac.uk/publications/studies-of-lactate-dehydrogenase-in-the-purified-state-and-in-intact-erythrocytes/). Their measurements were not adopted as stored-RBC prior intervals. Historical nominal values alone cannot satisfy the contract. If the baseline is unsupported, a separate initialization decision is required; no value or free fraction is changed automatically.

A coupled sensitivity protocol was prepared without execution. Three groups jointly scale HK/PFK investment, both AK directions, and GAPDH/PGK capacities. Omitted defaults are resolved from the hashed kernel syntax tree rather than guessed. HK remains at or below its retained ceiling 5.0, so investment probes are downward-only. Single-group log steps 0.05/0.10 yield 11 configurations including baseline; eight paired-group probes at 0.05 yield 19 configurations, each planned at strict/ultrastrict tolerances. Investment response is one-sided, $[x(1)-x(e^{-h})]/h$; other group responses are central, $[x(e^h)-x(e^{-h})]/(2h)$. Paired finite differences retain the appropriate one-sided investment and central other-group terms. All unlisted kinetics, initial states, numerical thresholds and the network remain fixed. Probe sizes describe a local diagnostic design, not biological parameter bounds, an optimizer search space or a candidate ranking. Execution remains conditional on scientific readiness and a separate execution decision.

### 2.26. Separate synthetic recovery benchmark for the FLA transport loop

A separate software benchmark tests whether concentration-to-flux reconstruction and parameter reinsertion can recover a known ODE-generated transport trajectory. It does not satisfy or override the biological readiness contract in Section 2.25. The provisional reaction-consistent profile, numerical availability threshold, corrected network, full 114-entry initial state and all unlisted kinetics remain fixed. Known synthetic truth multiplies the archived glucose and lactate transport capacities by 0.85 and 1.15, respectively. This same-family experiment is a positive-control problem, not evidence that the archived model is biologically adequate.

Training uses model days 1-22; model days greater than 22 through 46 are held out. Sparse sampling copies only the local workbook's times, with seven training times (1, 4, 8, 11, 15, 18, 22). No postinitial experimental concentration is used as a training target. Dense sampling combines 601 uniformly spaced training times with 101 uniformly spaced early times over days 1-2. Synthetic observations are restricted to EGLC, ELAC, GLC and LAC. These four concentrations are required because the transport laws depend on intracellular substrates as well as extracellular observations. Nonoracle kinetic inputs use PCHIP reconstruction of those four pools, not simulated latent truth. All other entries of a proxy state vector are fixed inert scaffolding; tests verify that changing latent energy/redox entries cannot change the two transport rates. A separately labeled oracle uses exact synthetic states and executed fluxes only as a diagnostic control.

Clean dense/sparse observations are compared with independent, mean-preserving multiplicative log-normal noise: $y_i=C_i\exp(\sigma_{\log}z_i-\sigma_{\log}^2/2)$, $z_i\sim N(0,1)$, $\sigma_{\log}^2=\log(1+0.005^2)$. Thus the coefficient of variation is 0.5%, positive pools remain positive, and zero pools remain zero. The initial state is exact and unperturbed. One dense and three sparse noisy realizations use recorded deterministic seeds. These realizations are not biological replicates and their variability is not an experimental uncertainty estimate. An earlier additive-noise preparation stopped because it generated negative synthetic observations; that incomplete attempt is preserved separately and is not used for recovery conclusions. No negative draw is clipped or resampled. The noise level and recovery criteria are predeclared numerical design choices.

The production extracellular teacher builder supplies $\hat v_{EGLC}=-d\hat C_{EGLC}/dt$ and $\hat v_{ELAC}=d\hat C_{ELAC}/dt$. Pointwise learning minimizes scaled squared differences between those teachers and the executed transport laws evaluated on reconstructed observed states. A second method uses signed observed interval increments instead:

\[
\hat I_{EGLC,k}=-[C_{EGLC}(t_{k+1})-C_{EGLC}(t_k)],\qquad
\hat I_{ELAC,k}=C_{ELAC}(t_{k+1})-C_{ELAC}(t_k).
\]

Only the two positive capacities $a_r$ are fitted, with all affinities, transport-family settings and initial conditions fixed. In an explicitly checked cap-inactive domain, the executed rate is $v_r^{exec}=a_r b_r(\hat x)$, where $b_r$ comes from the actual ODE kernel at unit capacity, including its native input floors and signed reaction-availability factor. This cached basis is checked against direct kernel rates at the lower bound, seed and upper bound; a potentially cap-active domain is rejected. Interval learning minimizes $\sum_{r,k}[(a_r\int_{t_k}^{t_{k+1}}b_r(\hat x(t))dt-\hat I_{r,k})/s_r]^2$; Gauss-Legendre orders 8 and 16 check reconstructed-basis quadrature. Pointwise and interval scales are derived from their respective targets, with a numerical floor, never from the hidden parameter truth. The methods share observations and therefore do not provide independent statistical evidence.

A benchmark-specific bounded log-capacity least-squares adapter uses three predeclared starts, rather than silently migrating the historical calibration/Optuna runners. Search multipliers are 0.25-2 relative to the archived capacities; truth is not a starting point. Multistart spread and the singular values/rank of the conditional log-capacity Jacobian are retained. This rank assesses the two capacities at fixed affinities and reconstructed inputs, not global network identifiability or identifiability of joint capacity-affinity combinations. No profile-likelihood confidence interval or Phase C machine-learning benefit is claimed.

Each recovered parameter pair is reinserted into an uninterrupted, unforced complete ODE replay from day 1 through day 46, at both strict and ultrastrict tolerances. All 113 concentration trajectories are scored against hidden synthetic truth, separately over training and holdout; executed glucose/lactate fluxes, native rates, availability factors, raw minima and solver convergence are retained. Concentration nRMSE uses the truth's excursion within the evaluated period with a 0.001 mM floor, not the experimental whole-panel normalization. Oracle recovery, dense-clean recovery and dense-clean transport holdout have separate preregistered synthetic checks. Sparse/noisy outcomes are descriptive stress tests, not biological pass/fail decisions. Experimental thresholds, latent redox bounds, model defaults and the blocked coupled energy protocol remain unchanged.

### 2.27. Paired teacher-resolution and smoothing diagnostic

A second, separate synthetic experiment reuses the verified truth in Section 2.26 but tests the numerical resolution of flux learning before proposing a different experimental objective. The inherited dense training partition contains two pairs of floating-point times separated by 2.22e-16 day. They are canonicalized in clean synthetic data before any noise is drawn: times within 1e-10 day share the first source timestamp and their mean clean concentration, after consistency checks. The resulting partition has 687 rather than 689 observations. A source-index receipt preserves this operation; the parent archive and experimental tables are unchanged. An initial GCV preflight that failed on the original ill-conditioned partition is retained separately. Noise draws are paired across methods within the new experiment, not bit-identical to those in the parent experiment.

Clean observations and five predeclared 0.5%-CV noise realizations are reconstructed by raw PCHIP or a cubic smoothing spline of log concentration. The latter selects its penalty by generalized cross-validation (GCV) on training observations only, using [SciPy's smoothing-spline implementation](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.interpolate.make_smoothing_spline.html). The known synthetic log-normal mean correction is applied before fitting. A postfit log shift anchors each curve to its exact initial concentration; this is not an exact constrained-spline optimum. Exponentiation preserves positivity, and derivatives follow the chain rule. No holdout observations or true parameter error select the smoothing penalty.

Pointwise supervision compares uniform grids of 101, 401, 1601 and 6401 points with order-4/8 Gauss quadrature within every observation interval. Except for a labeled equal-point 401-grid historical-objective control, residuals are weighted by temporal quadrature:

$$J_{\mathrm{point}}(a)=\sum_{r,j}w_j\left[a_r b_r(t_j;\widehat C)-\widehat v_r(t_j)\right]^2/s_r^2.$$

Here $a_r$ is the positive transport capacity, $b_r$ the unit-capacity executed rate, and $s_r$ a fixed teacher-RMS scale with a numerical floor. The control reproduces the historical objective and teacher builder on the new partition, not the earlier noise realization. Interval supervision retains raw signed observation increments and compares order-8/16 integrals of kinetic inputs. A secondary interval control smooths kinetic inputs only; it does not replace observed increments with denoised targets. The two learned capacities, frozen affinities and inactive import-cap domain are unchanged. A transport-only evaluation path calls the actual production rate helpers and signed reaction limiter, with full-kernel parity checks; it is not a substitute kinetic law.

Six observation regimes and 15 methods give 90 conditional multistart fits. A fixed subset of four methods (historical 401 objective, raw aligned order-8, smoothed aligned order-8, raw interval supervision), evaluated in the clean control and three preselected noise realizations, receives 32 complete strict/ultrastrict ODE replays. This subset is declared before fitting, not selected by recovered errors. All 113 concentrations and both executed transport fluxes are scored over training and holdout, with absolute, mean-normalized, excursion-normalized and endpoint errors kept distinct. Independent bounded closed-form capacity estimates, saved curve coefficients, temporal weights, raw solver states and metric recomputation support verification. Five synthetic seeds describe this stress design, not biological replicates, confidence intervals or broad robustness. Other conditional grid variants do not receive full ODE validation. Biological readiness and the prepared energy protocol remain unchanged.

### 2.28. Sparse-schedule continuation with sealed controls

The same teacher comparison is repeated using only the seven synthetic training concentrations at model days 1, 4, 8, 11, 15, 18 and 22. These are the local Bordbar observation times already stored in the original synthetic benchmark. Experimental concentration values do not enter this continuation. All affinities, other kinetics, full initial state, truth capacities, bounds, three optimization starts, numerical profile and availability threshold are identical to the dense comparison. The seven times are distinct and well separated, so no concentration aggregation or timestamp repair is required. A new runner and archive preserve all previously hashed sources and outputs.

The five noise seeds, known 0.5% synthetic CV, 15 methods, training-only log-GCV reconstruction and residual weights are retained. Noise is paired across methods within the sparse schedule. The three shared sparse seeds reproduce the original sparse observations exactly, but equal seed labels do not constitute matched dense-sparse perturbations because observation counts and random-draw positions differ. Sparse/dense comparisons are descriptive within this synthetic design, not paired inferential tests. GCV now has only seven training observations per pool; the same known-noise correction and postfit initial log anchor are used without a hidden-truth choice of penalty. Raw observed increments remain the interval targets, also when only kinetic inputs are smoothed.

The continuation again comprises 90 conditional fits and a predeclared subset of 16 parameter pairs for 32 full strict/ultrastrict J1-J46 ODE replays. No additional replay is selected after ranking errors. Independent verification regenerates noise and curve coefficients, reconstructs all sparse aligned and interval training nodes using the complete executed kernel, samples uniform-grid parity, computes bounded analytic capacity estimates and recomputes all 113-pool and two-flux temporal metrics. Legacy 401 results are compared against the original sparse benchmark within optimizer tolerance. The scientific readiness contract and all platform defaults remain unchanged; this experiment cannot promote a biological parameter set or establish joint kinetic/latent-state identifiability.

### 2.29. Fixed-capacity free-ODE validation of smoothed-input interval supervision

A separate prediction experiment compares the sealed raw-interval and smoothed-input interval capacity estimates from Section 2.28. No parameter is refitted. Both methods retain the same six signed raw-observation increments as supervision; only the interpolated kinetic inputs differed during the preceding conditional training. The complete ODE receives the resulting two transport capacities, the identical full initial state and frozen remaining kinetics, and evolves continuously from J1 to J46 without observed or smoothed concentration inputs, forcing, resets or state-output clipping. Training ends at J22; all later archived reference times are held out.

The design includes the clean control and all five sparse noise seeds (2718, 31415, 1618, 57721 and 104729), giving twelve fixed capacity pairs. Four verified raw-interval strict/ultrastrict pairs are copied with SHA-256 lineage receipts. The two remaining raw pairs and all six smoothed-input pairs require sixteen new integrations, for twenty-four integrations represented in the final comparison. The replay plan and exact capacity vectors are recorded before execution, with no selection according to predictive errors. Parent inputs, support code and archived outputs are hash-checked before and after the experiment.

Numerical checks cover all 113 raw concentration pools on accepted and archived dense nodes, the 114-state strict/ultrastrict comparison including pH, and the actually executed VEGLC/VELAC rates and extracellular balance closure. Prediction assessment retains absolute RMSE, mean-normalized and excursion-normalized concentration errors and signed endpoints, separately from RMS-normalized flux errors. Net transport integrals over the six training intervals and J22-J46 are also reported from the executed extracellular balance identities, $\int v_{\mathrm{EGLC}}dt=-\Delta\mathrm{EGLC}$ and $\int v_{\mathrm{ELAC}}dt=\Delta\mathrm{ELAC}$. These endpoint-derived integrals are not presented as independent rate quadrature. Paired differences are computed for every noise seed; five-seed medians, maxima and improvement counts exclude the clean control. The latter is reported separately to expose reconstruction bias. No new experimental accuracy limit is inferred from these synthetic metrics. Independent verification recomputes all metrics, checks the frozen training increments and analytic capacity solution, examines all saved raw states, and recomputes sampled fluxes through the full executed kernel. These tests validate the synthetic transport loop only, not biological calibration, the latent initial-state problem or the machine-learning warm-start.

### 2.30. Read-only source, observation-basis and time-origin audit

Before reopening biological calibration, an isolated audit records the workbook SHA-256, all 770 concentration cells, labels, time headers, formulas, named ranges, query-table relationships and import connections. All available Git snapshots at the original/current workbook paths are compared at the numeric-cell level; byte differences in Excel metadata are not interpreted as concentration changes. Filename search is restricted to the project and all local Git refs, excluding dependency/cache directories. Legacy path hints are recorded without accessing private storage or searching the user's whole computer.

The concentration and curve-coefficient tables are distinguished explicitly. The external `cellbb` connection is bound to Feuil1 and its range `A5:F49`, containing five coefficients per curve, not to the Sheet1 concentration table. Query metadata therefore documents a coefficient-import lead, not measurement provenance. An independent verifier rereads workbook cells/XML and historical Git blobs and compares all training-loader values and 19 extracellular-loader vectors against the source. Only the isolated calibration data-loading function is executed, without importing optimization runtime side effects. Public-source interpretation is documented separately; supplementary HTTP responses must pass an Excel-format gate, and HTML responses remain access receipts rather than accepted datasets.

Observation units are part of the inverse problem. At fixed source and model volume bases, a documented observation map can be written

$$y_j(t_s)=a_j x_j(t_m)+\epsilon_j,\qquad a_j=V_{j,\mathrm{model}}/V_{j,\mathrm{source}},\qquad t_m=t_s+\delta.$$

Here $x_j=n_j/V_{j,\mathrm{model}}$ and $y_j=n_j/V_{j,\mathrm{source}}$ refer to the same amount and pool definition; this diagonal map is not valid for unresolved mixed pools or an unmodeled free/bound distinction. At fixed volumes, the corresponding increment is $\Delta y_j/a_j=\sum_r S_{jr}\int v_r^{exec}dt+\int b_jdt$. Time-dependent volume bases require explicit dilution/sampling terms. The [Bordbar uFBA methods](https://www.nature.com/articles/srep46249) use mmol per liter of total bag volume for both intracellular and extracellular pools. Under a verified common bag-volume convention, equal-volume transport coefficients may be appropriate; no intracellular-water or hematocrit factor is inferred from a nominal mM header. Scaling flux teachers without also reconciling states, kinetic concentration arguments and uncertainty would change the calibration problem inconsistently.

The candidate $\delta=1$ day is exported as an unapplied hypothesis because J1-J46 spans 45 elapsed days. The exact source sampling vector remains unknown; local J38 is neither relabeled nor repaired. A published exclusion of source day 31 is recorded without transferring it to local J32. All configurations, initial states, numerical policies, historical archives and scientific-readiness flags remain unchanged. No ODE integration or parameter fitting belongs to this audit.

### 2.31. User-authorized conditional energy sensitivity with exact measured J1

A separate exploratory branch evaluates the coupled energy response without completing or bypassing the historical biological-readiness contract. All 55 Sheet1 values at model J1 are inserted into their exact mapped states, including measured zeros; every unmeasured pool is copied unchanged from the frozen diagnostic context. This explicitly differs from the earlier context at B13PG (0.000176677669 to 3.584045211 nominal mM) and ECYS/EINO (1e-6 to zero). The B13PG/B23PG and P2G/P3G duplicate signals remain non-independent, so exact initialization does not establish separate measurements or a physiological latent-state prior. Historical XLS initialization is not enabled, NAD/NADH remain 1 mM each, and no initial condition is fitted or promoted.

With the same reaction-consistent threshold and strict/ultrastrict BDF settings, three capacity groups are perturbed: HK/PFK investment, AK forward/reverse capacities together, and GAPDH/PGK production coupling. Every member of group $g$ receives $\theta_r(z_g)=\theta_{r,0}\exp(z_g)$; affinities and unlisted parameters are fixed. HK is already at its 5.0 ceiling, so its group has downward-only probes. At $h=0.05$ and $0.10$, the investment response for any simulated feature $Y$ is $[Y(0)-Y(-h)]/h$, whereas AK and GAPDH/PGK use $[Y(h)-Y(-h)]/(2h)$. Paired mixed differences use $h=0.05$ and the same one-sided/central tensor-product stencils, including required single-group and corner terms. Eleven baseline/single-group configurations plus eight paired configurations give 38 uninterrupted J1-J4 integrations. Probe sizes are numerical diagnostic choices, not physiological ranges or optimization bounds.

Outputs include all 113 concentration trajectories, same-trajectory native and executed rates, signed ATP/ADP/AMP and purine/redox budgets, nominal J4 endpoint errors, all executed reaction integrals and complete group-response vectors. Accepted-step Gauss orders 4/8 audit the budgets, and strict/ultrastrict comparisons audit numerical convergence. Signed-consumer limiter factors are archived separately; loss attribution on accepted-plus-dense nodes uses an explicitly labeled trapezoid approximation and is not independent quadrature or a biological control coefficient. Two probe sizes describe local nonlinearity, and cross-solver response differences must be reported because finite differences amplify numerical error.

There is no optimizer, candidate ranking, threshold adjustment, external forcing, observation reset, artificial ATP source or promotion. Source units, exact biological time origin, uncertainty, endpoint accuracy requirements and unmeasured-pool support remain unresolved. Thus the branch can identify conditional dynamic responses and interactions, not establish a biological parameter set, statistical compatibility or J1-J46/external predictive validity. The historical prepared coupled protocol remains unauthorized and unchanged; this explicit exploratory authorization is recorded in a new configuration and archive.

### 2.32. Prepared latent-pool inference and heterogeneous observation contracts

A separate preparation extends the FLA framework to partially observed initial states without executing biological estimation. At compatible constant volumes, $x(t_b)-x(t_a)=S\int_{t_a}^{t_b}v^{exec}(t)dt$ constrains increments, not generally the initial concentration offset. Measured balances can also admit multiple internal flux distributions. We therefore distinguish structural flux ambiguity from dynamic initial-state identifiability; the latter requires perturbation sensitivities, observable combinations and recovery tests, not a stoichiometric rank calculation alone.

For an absolute assay, $y_{i,d}(t)=H_{i,d}(x_d(t))+\epsilon$ includes source-specific pool identity, free/bound recovery and volume normalization. For a linear, stable, correctly normalized temporal relative signal, the observation is $\log R_i(t)-\log R_i(t_0)=\log H_i(x(t))-\log H_i(x(t_0))+\epsilon$. An optional anchored estimate is $\widehat C_i(t)=C_i(t_0)R_i(t)/R_i(t_0)$, provided the anchor matches the metabolite, exact day, pool definition and volume denominator. Its log-variance uses the full joint covariance of log(anchor), log(signal) and log(reference), with contrast vector $(1,1,-1)$; a shared reference induces cross-time dependence. An external-cohort anchor remains a prior or nuisance scale, not an absolute measurement. Same-day treatment/control ratios instead constrain $\log H_i(x_{treated}(t))-\log H_i(x_{control}(t))$ and require both contemporaneous trajectories. Nonpositive/censored signals require an explicit detection-limit model, not numerical epsilon replacement. Teachers derived from these same observations cannot be counted as independent likelihood terms.

The proposed first latent block comprises initial NAD(H) and NADP(H) totals and reduced fractions, with NAD=$T_N(1-f_N)$, NADH=$T_N f_N$ and analogous NADP/NADPH equations. All 55 nominal Sheet1 J1 entries, kinetics, other unmeasured pools and the numerical reference remain fixed. Duplicate B13PG/B23PG and P2G/P3G signals remain non-independent and cannot be resolved by arbitrary splitting. Pi and Mg are not explicit states in this kernel and cannot be inferred merely by assigning initial concentrations. The [Nishino model supplement](https://doi.org/10.1016/j.jbiotec.2009.08.010) supplies reference points, not stored-cohort prior widths or measured J1-J5 anchors. Context, volume and free/total compatibility must be established before using them as biological prior support.

The staged protocol first calls for a separately authorized synthetic recovery and sensitivity benchmark using the actual observation schedule and unchanged executable kinetics, followed by constrained maximum-a-posteriori estimation and profile/ensemble uncertainty only when scientific evidence is supported. A later Bayesian analysis is optional and cannot remove nonidentifiability. Strict/ultrastrict free-ODE agreement, signed integrated budgets and numerical-limiter involvement must be audited independently of predictive agreement. The preparation implements isolated observation/parameterization helpers, not a production fitting path; supported bounds, observation covariance and absolute prediction limits remain unset. No new simulation, biological fit, threshold adjustment, observation forcing or promotion is part of this preparation.

### 2.33. Source-preserving ingestion of the JBC temperature-storage supplement

The user-supplied numerical supplement to Yurkovich et al. (DOI 10.1074/jbc.M117.804914) is archived separately from the Bordbar training table. A read-only importer retains each workbook sheet, original column label and unit, source-cell coordinate, temperature-block label, exact reported day and numerical value. Channel identifiers use sheet plus column rather than metabolite names because two hemoglobin columns have identical headers but different values. Missing values, reported zeros and invalid values remain distinct; no interpolation, rounding, concentration rescaling, zero-to-epsilon substitution or automatic production import is permitted.

The supplement describes three donors with each unit divided among four temperatures. The workbook contains three time-reset trajectory blocks per temperature, but no explicit individual identifiers. We retain positional replicate-block indices without asserting donor pairing across sheets or temperatures. Sampling schedules are source-specific: at 37 C the assay sheet includes day 14 although endo/exometabolomics ends at day 7. Joins by worksheet row number are prohibited. PDF page 2 defines the first sample, source day 0, as one day after storage began; a derived storage-day coordinate is stored separately, without transferring this convention to the local Bordbar table. Temperature conditions are not pooled into one trajectory or used as interchangeable physiological replicates.

Candidate observation operators are distinguished from verified mappings. The phosphoglycerate signal is a candidate $H(x)=x_{P2G}+x_{P3G}$ on a compatible common basis, not two independent concentrations. Workbook glucose-6-phosphate is held pending reconciliation with the hexose-6-phosphate calibration label and its two HMDB identifiers in Table S1. ATP is held because the workbook labels it endo whereas Fig. S7 labels it exo, and extraction recovery/free-versus-total interpretation remains unresolved. The methods mention a 2,3-DPG assay kit but also explicitly state that 2,3-DPG was not measured; the flux-modeling section describes an estimated profile, and no numerical workbook channel is present. It is therefore excluded from independent experimental supervision. Nicotinamide, S-adenosylmethioninamine, LDH activity and analyzer pH are not mapped automatically to NAD, ADOMET, executed VLDH or intracellular pH.

Original mM values are retained without assuming cytosolic, supernatant or total-bag concentration equivalence. Hematocrit, cell metrics and bag weight are archived but do not establish the missing normalization equation. If an eventual observation uses a time-varying compartment volume, its amount balance is $d(VC)/dt=V\,dC/dt+C\,dV/dt$; differentiating reported concentration alone need not yield a reaction-flux balance. Tables S1/S2 provide analytical calibration and detection limits in mg/L, not sample-level biological covariance, extraction uncertainty or predictive accuracy limits. Descriptive means/standard deviations across positional blocks are not automatically likelihood weights or a paired covariance. Dataset independence from training must also be established before calling a test independent external validation.

All source cells are independently reconstructed from the original workbook, and input/output checksums preserve the original files, numerical reference, frozen initial states and preceding archives. This ingestion resolves numerical source access only. It executes neither flux reconstruction nor dynamic inference, ODE prediction, kinetic optimization or model promotion.

### 2.34. Reversible biochemical closure before extending FLA calibration

A separate opt-in adapter audits carbon identity, one-carbon pools and redox acceptors without modifying the historical kernel, stored teachers or production initialization. Pinned RBC-GEM chemistry is treated as evidence to inspect, not a source of kinetic constants or an infallible balance specification. The cystathionine branch is replaced by the composite reaction cystathionine + water -> cysteine + 2-oxobutanoate + ammonium, supported by the sum of CYSTL1, 2ABUTENT and 2IMBUTDA and [UniProt/Rhea CTH](https://www.uniprot.org/uniprotkb/P32929/entry). The C4 product is an explicit latent state, not AKG or an untracked sink. The intermediate-elimination approximation and the absence of a validated downstream C4 fate are recorded.

The former latent METTHF coordinate is separated into 5-methyl-THF (MTHF) and 5,10-methylene-THF (MLTHF). SHMT produces MLTHF, whereas methionine synthase consumes MTHF. An optional MTHFR branch couples MLTHF + NADPH -> MTHF + NADP; human [MTHFR](https://www.uniprot.org/uniprotkb/P42898/entry) and [MTR](https://www.uniprot.org/uniprotkb/Q99707/entry) chemistry does not establish their activity in mature stored RBCs. No implicit interconversion is permitted. Conditional initialization preserves the unsupported historical latent folate total under explicitly named methyl-only or methylene-only partitions; neither partition is an inferred biological prior. All 55 nominal measured Bordbar J1 entries remain exact.

Two redox modules introduce finite available acceptor states: NADH-cytochrome b5 reduction followed by methemoglobin reduction, and NADPH-thioredoxin reduction followed by PRDX sulfenylation, resolution and disulfide reduction. Cytochrome b5 and hemoglobin states use one-electron heme-site equivalents rather than Hb tetramer concentrations: NADH reduces two ferricytochrome sites and one reduced cytochrome transfers one electron per ferric hemoglobin site. The pinned GEM METHBCYTBR column has a charge residual of +1 under its stored formula/charge definitions and a one-site electron-accounting mismatch; its factor of two is therefore not copied into the one-site diagnostic. The [CYB5R mechanism](https://reactome.org/content/detail/R-HSA-6806831) and site-versus-complex observation basis are recorded separately. PRDX retains an explicit sulfenic intermediate rather than hiding acceptor regeneration in a free NADPH sink. Cofactor, cytochrome, heme, thioredoxin and PRDX totals and electron-equivalent ledgers are checked; no ATP-producing source is added.

New branches require explicit finite initial pools and substrate kinetic constants and remain inactive in Bordbar replays. Their phenomenological substrate-saturation laws are exercised only in separately labeled synthetic software tests; these are not fitted enzyme kinetics or empirical priors. The augmented matrix is subjected to reaction-consistent limiting before differentiation and flux tracking. New proton contributions, Hb oxygen binding/oxidation, PRDX hyperoxidation/repair, source-specific active fractions and shared enzyme capacity limits are not yet validated. The fixed availability threshold must be audited against realistic small active pools before physiological activation; historical convergence does not establish validity for these added states.

OPLAH is retained by default: its exclusion in older GEM curation conflicts with its detection in the supplied recent proteome. A named off-policy is an isolated countertest, not deletion or promotion of zero activity. Five predeclared J1-J4 structural cases isolate C4 correction, folate separation, two conditional partitions and the OPLAH countertest, each under strict/ultrastrict integration with unchanged historical kinetics. Two separate synthetic redox chains receive the same numerical checks. Source hashes, executed integrated budgets, zero-boundary probes and independent stored-grid verification are archived. Before future FLA fitting, the observation matrix and flux identifiability must be rebuilt for the augmented registry, and new active-pool/kinetic/acid-base evidence must satisfy the scientific readiness contract. Existing teachers are neither recycled silently nor counted as independent evidence.

### 2.35. Planned reference-anchored reduction and multi-source validation

The intended model is a RBC-GEM-informed reduced dynamic model, not yet an exact reduction or validated reproduction of the genome-scale reconstruction. [RBC-GEM](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1012109) supplies reaction, compartment and enzyme/complex evidence. Every retained, omitted, composite, lumped or buffered component must receive an explicit mapping and conservation/approximation contract. Existing AIRBC kinetic laws are retained where justified; genome-scale feasibility or proteome-constrained FVA is not interpreted as a measurement of dynamic reaction rates. Recent biochemical evidence can justify documented exceptions to older GEM curation, including retention of OPLAH.

Source reconciliation does not mean direct pooling of all metabolite values. The cited [Bordbar2015 study](https://pubmed.ncbi.nlm.nih.gov/27136057/) concerns fasting-state personalized profiles, whereas [Yurkovich2017](https://pubmed.ncbi.nlm.nih.gov/29030425/) reports quantitative storage time courses. Their experimental contexts and the lineage of the locally labeled Bordbar J1-J46 table must remain distinguishable. Each source receives an observation operator $y_s(t)=H_s(x_s(t),\eta_s)+\epsilon_s(t)$ encoding compartment, analytical pool, supported normalization and uncertainty, with its own initialization and environmental context. Shared kinetic parameters are then testable cross-context hypotheses. The current exact55 Sheet1 J1 initialization is unchanged; this plan neither supplies missing redox measurements nor authorizes external absolute anchors as replacements.

Proteomics informs uncertain capacity priors through $V_{\max,r}=86400\,k_{\mathrm{cat},r}E_{\mathrm{active},r}$ when rates are in mM/day, turnover in s^-1 and active catalytic-site concentrations in mM. Conversion requires compatible volume, complex/site stoichiometry, active fraction and temperature/pH context, with shared enzyme capacity allocated across reactions. [Issaian2025](https://www.biorxiv.org/content/10.1101/2025.11.29.691178v1) is retained as the supplied preprint version; the [published Blood2026 study](https://pubmed.ncbi.nlm.nih.gov/42224377/) provides the current biological reference. Neither abundance nor interactome/PTM evidence directly supplies Km, active fractions or latent cofactor concentrations. FLA will therefore prioritize a restricted identifiable set of effective capacities after synthetic recovery, rather than globally fit every kinetic constant. Teachers derived from concentrations remain correlated supervision, not independent experimental likelihoods.

The proposed [population-scale RBC atlas, PMID41846981](https://pubmed.ncbi.nlm.nih.gov/41846981/), is the same study as DOI10.64898/2026.03.07.710284, currently indexed as a preprint. Its proteomic aging and outcome associations motivate biological benchmarking but are not direct kinetic truth. Metadata and abstract-level scope were verified; access to detailed methods/supplements, compatible metabolite observations and donor overlap remains to be established. Measurements informing structure, priors or candidate selection are development evidence and cannot also be counted as untouched validation. Donors/conditions must be reserved before teacher construction, with RBC-Omics reuse documented. Storage time is not equated with donor biological age; hemolysis, transfusion hemoglobin increments and donor activity require separate observation models before predictive claims.

This positioning changes study objectives, not executed results. Source/role/cohort manifests, augmented observation/balance identifiability, active-pool and shared-capacity contracts, numerical threshold sensitivity, and synthetic recovery precede any joint biological fitting. Candidate evaluation remains continuous, unforced ODE prediction against source-specific held-out observations and whole-network safeguards. A proteomic prior is expected to focus the search, not guarantee restoration of ATP or waive existing readiness failures. The operational objectives are recorded in `tasks/fla_project_objectives_2026_10_06.md`.

### 2.36. Executed common source, observation and cohort inventory

A separate source-only registry records ten source identities, eight dataset descriptors and seven cohort/risk groups before multi-source fitting. Publication aliases and preprint/published versions are attached to one study identity where supported; the locally labeled Sheet1 storage table is not automatically assigned to the Bordbar2015 fasting-state study. Channel records retain source-cell/row locators, units, compartment and candidate observation operator, sampling support, alternative-estimate groups, prior exposure and unresolved integration requirements. Sample IDs are namespaced within a release; absent donor IDs are not reconstructed from row position. Compartment identity is taken from the explicit model catalogue rather than an initial-letter heuristic.

The inventory covers55 local series,96 JBC channels,62 S6 priority proteins in two abundance representations,3799 human Deep Red proteins under two copy-number calibrations, and the standardized Bardyn/Michel panels. S6 D/E share protein/sample keys and one evidence group per protein; Deep Red F/G share one group as alternative calibrations. Their combined channel/value totals are bookkeeping quantities, not independent experimental sample sizes. The S6 extraction is a priority subset, other Deep Red assays/species/PTM/interactome resources remain resource-level evidence, and the population atlas contains metadata only in this registry. Identical local B13PG/B23PG and P2G/P3G trajectories are flagged without overwriting measured initialization or treating analytical identity as physiological equivalence.

JBC source_day and the separately documented storage coordinate remain distinct; positional replicate blocks do not establish cross-sheet or cross-temperature donor pairing. Previous exploratory transfer diagnostics qualify Bardyn/Michel as exposed external panels, not certified untouched holdouts. No donor/condition split is fabricated, and no imported panel is declared independently validated. Source/overlap relationships default to unverified when not resolved; absence of an edge does not establish independence. Future assignments must keep repeated days and paired conditions from an identified donor together and satisfy source-specific observation contracts.

The reproducible builder verifies upstream seals and hashes protected model/data inputs before and after inventory construction. A separate read-only verification pass reconstructs channel/sample and cohort/relationship tables from the source extracts, without claiming an independent reimplementation of the same reconstruction algorithm. No fusion, rescaling, teacher reconstruction, active-capacity conversion, ODE run, kinetic optimization, model-input change or readiness override is performed. Source contracts for concentration denominator, ATP pool form, merged phosphoglycerates, duplicate-pool lineage and donor linkage remain prerequisites to biological fitting. The registry and execution report are `output/fla_common_manifest_2026_10_06/` and `tasks/fla_common_manifest_2026_10_06.md`.

### 2.37. Source-specific volume denominators and prospective membrane transport reduction

Intracellular and extracellular mM values are not assumed to share a reference litre. We distinguish concentrations per packed-cell volume, intracellular water, extracellular fluid and total bag volume. For physical phase concentrations $c_i=n_i/V_i$ and $c_e=n_e/V_e$, a positive membrane export $Q$ in mmol/day obeys $d(V_i c_i)/dt=-Q$ and $d(V_e c_e)/dt=Q$. Therefore $\dot c_i=(-Q-c_i\dot V_i)/V_i$ and $\dot c_e=(Q-c_e\dot V_e)/V_e$, before adding other reactions, sampling or leakage. At fixed volumes and hematocrit $H=V_i/V_b$, a cell-normalized export $j=Q/V_i$ contributes $-j$ and $Hj/(1-H)$ to the physical concentration derivatives. No single-cell volume is required for this ratio once the source's volume definition is verified. Cellular-water normalization additionally requires its supported water fraction, not an assumed conversion.

Observation operators remain source-specific. Bag-normalized intracellular and extracellular amounts are $y_i=Hc_i$ and $y_e=(1-H)c_e$; their fixed-volume transport derivatives are equal and opposite even though the physical compartments differ. [Bordbar uFBA2017, Data Preparation](https://www.nature.com/articles/srep46249) explicitly adopts this total-bag normalization for both pools. Its processing is not established as the lineage of local Sheet1 or the original Yurkovich JBC workbook. Consequently, we preserve all local J1 values and do not apply automatic hematocrit rescaling. An extracellular teacher constrains $d(B_e y_e)/dt$, not merely $\dot y_e$, when its reference denominator $B_e$ varies; other extracellular processes and sample removal must be accounted for separately. Rates per hour require a documented conversion to model days, not an assumed correction to historical effective parameters.

A read-only audit reopens the JBC source workbook and verifies876 selected numeric cells with original headers and units. These include126 measured hematocrit values, intracellular glucose/lactate, extracellular assay glucose/lactate and two pH channels. The24 hematocrit measurements at4 C span0.574-0.702. Supplement p2 reports blood-gas pH measured at37 C; neither this value nor the separately reported22 C channel is automatically substituted for intracellular or extracellular pH at4 C. The absence of verified donor keys still prevents cross-sheet donor assignment. These measurements supply geometry and assay evidence, not a resolved intracellular concentration-normalization equation.

The pinned [RBC-GEM](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1012109) encodes reversible glucose transport GLC_Dt, whose positive direction is export, opposite to AIRBC VEGLC. L_LACt2 exports one lactate with one proton. Twelve lactate c/e routes, including chloride and monocarboxylate exchanges, are retained in the source inventory. Net extracellular lactate constrains their stoichiometrically signed sum, not MCT1 alone. Gene rules and permissive flux bounds supply structural evidence, not Km, kinetic Vmax or a mandate to add an infinite environmental reservoir to a closed storage bag. Carrier capacities shared across substrates must not be duplicated.

The prospective first glucose hypothesis is a reduced reversible law $j_G=k_G(g_e-g_i)/(1+g_e/K_e+g_i/K_i)$ for comparable accessible free-concentration/activity coordinates with unit partition coefficient. Directional capacities satisfy the Haldane constraint $V_f/K_e=V_r/K_i=k_G$, allowing saturation asymmetry without shifting the passive equal-activity equilibrium. This is a proposed reduction, not the complete GLUT1 allosteric mechanism demonstrated in [human-RBC transport studies](https://pubmed.ncbi.nlm.nih.gov/29209831/). The prospective lactate law has an export driving term proportional to $a_{L_i}a_{H_i}-a_{L_e}a_{H_e}$ and an explicitly specified positive saturation/competition denominator, consistent with the [proton-coupled carrier evidence](https://pubmed.ncbi.nlm.nih.gov/6871216/). pHi/pHe at the simulation temperature, buffer/Hb/CO2 closure and parallel transport contributions must be specified before activation. No full carrier law, new rate constant or biological replay is implemented in this audit.

Validation will reserve identified donors, or prespecified groups matched on solution, temperature, processing, time origin, analytical pool/denominator and supported donor covariates. All repeated days and paired conditions from a donor remain in one partition; preprocessing, teacher reconstruction and capacity priors are estimated within the training partition. Positional blocks and outcome-selected groups cannot establish independent validation, and overlapping RBC-Omics cohorts remain explicitly tracked. Without donor linkage, a condition-level aggregate comparison is labeled as such. The isolated source audit and dimensional conservation checks do not alter the ODE, API, numerical reference, initialization or scientific readiness. Operational evidence is recorded in `tasks/fla_transport_contract_2026_10_06.md`.

### 2.38. Executed phase-volume branch and conditional source-pairing preparation

The next authorized branch selects intracellular mmol/L packed cells and extracellular mmol/L supernatant as working coordinates and does not apply uFBA normalization. Original source concentrations and all historical J1 values remain unchanged. Hct-weighted quantities are derived for conservation accounting only, not substituted as bag-normalized training observations. This explicit coordinate choice does not establish the original assay preprocessing, accessible free pools or cellular-water correction. Original evidence manifests remain intact; a successor configuration records the new branch.

JBC trajectories receive stable sheet/temperature/positional-block keys and samples retain exact source time. Ordinal candidate-unit identifiers are labeled unverified pairing hypotheses, not source donor IDs. The first4 C pairing is prespecified as matching ordinal endo/assay blocks, and all six possible permutations are prepared for sensitivity rather than selecting the most favorable model fit. The144 paired records represent24 time/block combinations under each mapping, not144 independent experimental samples. Until donor linkage is supported, all anonymous units share one conservative validation split key; temperature and storage solution support condition-level groups, not fabricated independent donor partitions.

The opt-in full113-pool adapter expresses concentration dynamics as $\dot c=D^{-1}S V_r v^{exec}$ at constant phase volumes. $D$ contains cellular or supernatant fractions and $V_r$ the explicitly declared rate-reference fraction for each reaction. Native intracellular/membrane rates are conditionally interpreted per cell litre/day; the two extracellular glutathione degradation rates remain per fluid litre/day. VECYT remains a cell-normalized membrane process from its historical intracellular CYT chemostat, despite its projected external-only column. The explicit27-pool external registry prevents misclassification of E4P. Reaction-consistent availability is applied to the complete scaled columns, preserving signed quantity accounting rather than independently damping derivatives.

Seven fixed-context J1-J4 cases isolate common-coordinate transport versus distinct-volume native transport and the reversible GLUT/MCT hypothesis, using the three Yurkovich4 C source-day0 hematocrits0.580,0.574 and0.632. These are borrowed geometry scenarios, not asserted Bordbar donor measurements. Strict/ultrastrict BDF and accepted-step quadrature compare all113 concentration balances and100 reaction integrals. Historical forwarding remains bit-identical; all source-measured and unmeasured initial coordinates and native kinetic inputs are preserved. The new carrier conductances are deterministically tied to frozen native capacities/Km rather than fitted, and hypothetical symmetric lactate Km and accessible glucose coordinates are declared explicitly.

All comparison cases clamp pHi to its initial value; the new MCT law uses pHe=7.2 as a diagnostic control, not a storage-temperature measurement. Executed MCT proton export is recorded as $H v_{VELAC}^{exec}$ per bag-volume reference. Clamping implies compensating buffer reservoirs and does not predict acidification, Hb/CO2 dynamics or ion-pump ATP expenditure. This pass therefore tests geometric and carrier-family effects on a free concentration ODE, not a fully closed proton system or independent biological validation. Proteomic capacities, alternative lactate routes, source pairing and active redox evidence remain separate constraints before biological fitting.

### 2.39. Accessible-pool and acid-equivalent contract before free transport prediction

We distinguish phase-normalized extractable observations from membrane-accessible activities. For an uncorrected observation $C$, an explicit conditional operator is $\widetilde a=\gamma f C/(wr)$, where $f$ is the accessible substrate fraction, $w$ the phase aqueous fraction, $r$ analytical recovery and $\gamma$ an activity coefficient. $\widetilde a$ denotes an activity-equivalent concentration on a1mM standard. Already recovery-corrected data require $r=1$ with processing support; lactate additionally requires free-anion/speciation support. Unknown factors remain unset. No cellular-water fraction is inferred from hematocrit or assigned from another cohort. Reading an observation in mM and converting it to a kinetic activity coordinate are separate operations.

Writing $\rho=\lambda_i/\lambda_e$ for the relative activity scale, the reduced lactate export condition becomes $pH_i-pH_e<\log_{10}(L_i/L_e)+\log_{10}\rho$. Direction depends on $pH_i-pH_e-\log_{10}\rho$; directionality alone therefore cannot distinguish an accessibility correction from a pH difference. The glucose zero-flux condition likewise involves equal accessible activities rather than necessarily equal extractable concentrations. Previously fitted effective affinities/capacities must be re-expressed or supported in the chosen kinetic coordinates before being reused. An extracellular net lactate teacher still does not separately identify MCT versus parallel exchange routes.

For constant geometry, signed executed proton export is $J_H=Hj_{MCT}^{exec}$ in mmol/L-bag/day. With other acid sources $s_i,s_e$ in the same units and local capacities $\beta_i,\beta_e$ per corresponding phase litre/pH, the conditional equations are $\dot pH_i=-(s_i-J_H)/(H\beta_i)$ and $\dot pH_e=-(s_e+J_H)/((1-H)\beta_e)$. They satisfy $-H\beta_i\dot pH_i-(1-H)\beta_e\dot pH_e=s_i+s_e$. Clamping requires acid reservoir terms $R_i=J_H-s_i$ and $R_e=-J_H-s_e$. This ledger does not infer missing metabolic proton stoichiometry from reaction names. A local effective-total buffer model and explicit carbonate chemistry are alternative representations, not additive duplicates; explicit chemistry requires intrinsic buffering, Hb/oxygenation context, CA, AE1/Cl/HCO3 coupling, carbon conservation and gas/sampling boundaries.

[Primary RBC pH measurements](https://pmc.ncbi.nlm.nih.gov/articles/PMC3036193/) support medium-dependent Hb buffering and AE1-mediated recovery; [37C RBC experiments](https://pmc.ncbi.nlm.nih.gov/articles/PMC4042536/) provide buffer/volume context. These are not storage-cohort4C inputs. Source assay pH channels at37C and reported22C remain distinct from unmeasured4C pHi/pHe. Historical empirical pH dynamics are not adopted as a closed proton balance. The successor contract reconstructs source-cell values, tests activity-gradient ambiguity and applies saved executed MCT integrals to explicitly labeled buffer counterfactuals. No new ODE, inferred pH, fitted activity scale or scientific-readiness override is introduced.

### 2.40. Targeted pH-channel lineage audit and synthetic carrier-buffer recovery preparation

We reopened the original JBC pH37/pH22 cell pairs and compared them against a prespecified manufacturer correction, $pH_{22}=pH_{37}+15[0.0147+0.0065(pH_{37}-7.40)]$. The [Radiometer ABL90 IFU](https://www.ruh.nhs.uk/pathology/documents/poct/SOP_Radiometer_ABL90_Flex_IFU_Instructions.pdf), chapter11 printed page276, supplies the equation. Compatibility was evaluated against the propagated rounding bound for two three-decimal channels, not by fitting correction coefficients. A matching transformation supports calculated-channel provenance only as an inference; analyzer settings and the authors' preprocessing are still required. We did not extrapolate to4C, infer pHi from assay pH, or treat potentially derived channels as independent likelihoods. Source extraction protocols and internal standards were separately distinguished from unsupported free-pool, water-fraction and final-denominator conversions.

An isolated closed synthetic model coupled reduced reversible MCT export $j$ to $\dot L_i=-j$, $\dot L_e=Hj/(1-H)$, $\dot pH_i=j/\beta_i$, $\dot pH_e=-Hj/[(1-H)\beta_e]$ and an integrated extent $\dot z=j$. Accessible substrates were $\lambda_iL_i$ and $\lambda_eL_e$. Constant geometry, buffers and truth parameters were constructed experiment inputs, not storage-temperature estimates. The model excludes ATP, metabolic acid production, gas, AE1 and carbonate chemistry. Two initial import/export contexts were tested under strict/ultrastrict unforced BDF integration, accepted-step flux quadrature and amount/acid-equivalent closure. Synthetic sparse timing follows JBC4C coordinates; training ends at7.0417days and subsequent times through20.9583days are held out. No measured source concentrations supplied synthetic truth.

We preregistered staged bounded recovery, from oracle conductance to conditional capacity/accessibility/pHi estimation, with fixed starts and later-time prediction checks. Conditional local sensitivities compare concentrations alone, concentrations with pHe, and concentrations with both pH channels at sparse/dense training schedules and two differentiation steps. Design scaling and future noise assumptions are not biological covariance estimates. A negative control explicitly allows unknown intracellular affinity: $\lambda_i\mapsto c\lambda_i$, $K_{m,i}\mapsto cK_{m,i}$ and $pH_i(0)\mapsto pH_i(0)+\log_{10}c$ preserve concentration and pHe trajectories and the full toy flux. This transformation does not hold with unchanged known affinity and need not extend to the full RBC network. Recovery must therefore report equivalent families where appropriate rather than identify one parameter vector from concentration-derived teachers. This execution prepared recovery and ran forward controls only; no recovery optimization or biological replay was performed.

### 2.41. Executed bounded clean carrier-buffer parameter recovery

The frozen carrier-buffer preparation was followed by a separate clean synthetic recovery campaign. We estimated conductance alone with all other inputs known; conductance and extracellular effective buffer capacity with independent synthetic pH observations; and intracellular accessibility plus initial pHi with conductance, buffers and affinities known. The last stage compared concentrations alone, concentrations plus pHe, and concentrations plus both pH channels. Two initial transport directions, sparse/dense training schedules and three prespecified starts gave72 fits in24 comparison groups. Fixed inputs were constructed oracle context, not newly supported biological parameters. Initial pHi truth was excluded whenever that coordinate was estimated. No concentration-derived teacher was added as an independent likelihood.

The objective used only observations through7.0417days and BDF integration limited to that training horizon. Unforced later-time predictions extended through20.9583days without state resets. Positive free parameters were log-transformed, pHi was linear, and finite bounded least-squares used three-point differences with step1e-4, unit coordinate scaling and1e-10 stopping tolerances. All actual objective integrations, including Jacobian perturbations, counted toward the frozen100-call budget. Final predictions were separately checked under strict/ultrastrict profiles, flux quadrature, amount/acid closure and nonnegative lactate states. Four unknown-affinity equivalent-family transformations remained explicit negative controls rather than unique optimized estimates. A separately coded scalar-extent reduction, integrated with DOP853, cross-checked all fitted five-state BDF trajectories and independently recomputed parameter/holdout error arithmetic.

### 2.42. Frozen three-seed observation-noise robustness challenge

The clean conditional recovery design was challenged with the previously specified concentration CV0.005, pH SD0.005 and seeds2718/31415/1618. Remaining distribution and initialization conventions were recorded in a separate successor design before generating the recovery observations. Noninitial concentration observations followed independent mean-preserving lognormal analytical noise, with log variance $\log(1+CV^2)$; pH observations followed independent additive Gaussian noise. Conditional assay errors were independent across channel and time, not inferred experimental covariance. Each seed/context generated one shared panel on the union of sparse/dense training and sparse holdout times. Overlapping measurements were identical across stage, observation plan, schedule and optimizer start.

Initial lactate concentrations and extracellular pH remained exact known context, whereas pH assays, including their initial readings, were noisy. Initial intracellular pH remained known in the first two oracle stages and was estimated in the accessibility/pHi stage without receiving its hidden true initial value. A noisy assay of a known coordinate contributes a constant residual rather than an extra parameter. The challenge therefore does not evaluate uncertainty in the known initial concentration or extracellular-pH coordinates. Concentration noise was not projected onto a conservation constraint, clipped or redrawn.

The clean objective weights, parameter bounds, starts, numerical profiles, acceptance limits and100 actual-call budget were retained unchanged. The cost consequently remains a design-weighted least-squares objective, not a matched noise likelihood; this experiment evaluates that existing estimator under specified noise rather than an efficient statistical estimator. Training ends at7.0417days, followed by uninterrupted prediction through20.9583days. Latent-truth prediction error, noisy-observation error, parameter recovery, optimizer success and three-start agreement are separate outcomes. Budget-exhausted fits retain their best evaluated point for diagnostic prediction but remain optimizer failures. No noisy seed or start is selected as a favorable winner.

The full design comprises216 fits,72 three-start groups and six independently generated noise panels, not216 independent datasets. Descriptive across-seed ranges use each panel's median over all starts; three seeds per context do not establish population confidence intervals. Twelve predetermined unknown-affinity transformations retain the exact concentration/pHe ambiguity as a negative control. All saved fitted trajectories are cross-checked against a separately coded scalar-extent DOP853 integration. No biological data, teacher likelihood, full-RBC simulation, ATP source or kinetic promotion is introduced by this challenge.

### 2.43. Paired observation-likelihood comparison and separate budget escalation

The same six sealed noise panels and216 prespecified fitting configurations were reanalyzed with a mean-preserving lognormal concentration likelihood and additive Gaussian pH likelihood. Initial exact concentrations were excluded from stochastic terms. The concentration residual was $[\log y-\log\mu+v/2]/\sqrt v$, with $v=\log(1+CV^2)$; pH residuals used their specified standard deviation. Full likelihood normalizers were implemented and checked against independent library densities. The216 archived design-cost fits supplied the paired baseline;216 matched fits were newly executed. Bounds, starts, numerical settings,100-call primary budget and truth/holdout limits were unchanged. No new noise or outcome-based seed selection was introduced.

Budget was subsequently made secondary to scientific progress. A separate, prespecified follow-up reran optimizer failures only, for either objective, from their original starts with500 calls and2000 only if still unconverged. Parameter truth error and heldout performance did not select those reruns. Primary results were retained rather than replaced. This distinguishes objective/identifiability problems from numerical iteration limits. The likelihood was also evaluated on the12 archived unknown-affinity concentration/pHe families; equal predicted observations must retain equal likelihood.

### 2.44. Conditional transport calibration on the original experimental table

We then fitted a reduced GLUT equation directly to original nominal Bordbar-table EGLC observations, preserving all source values and exact J1. Intracellular GLC was a declared measured input: training-only PCHIP through J25 followed by its last training value through J46. No later GLC or EGLC informed the fit. The conditional model was $\dot E=-a(E-G)/(1+E/K_{m,e}+G/K_{m,i})$, with $a=Hk/(1-H)$ under the user-selected distinct phase-volume convention. It does not predict GLC or close intracellular metabolism. The source denominator and borrowed hematocrit remain working assumptions, not independently verified donor metadata.

Seven noninitial EGLC observations trained either clearance alone with fixed seed affinities, or clearance plus extracellular affinity, using three starts. Residual lognormal variance was profiled rather than copied from the synthetic generator. For $d=\log y-\log\mu$, the exact positive stationary variance is $v=2\overline{d^2}/(\sqrt{1+\overline{d^2}}+1)$; full normalizers remain in the objective. This estimates total residual dispersion, including model/input error, not isolated assay noise. Zero-variance boundaries are rejected rather than regularized by an invented floor. Later-time comparison is historically exposed and internal, not independent external validation.

An initial unsegmented pilot failed some numerical cross-checks and remains preserved. Its successor integrates continuously in separate intervals ending at every training input knot and the cutoff, with tightened numerical profiles and declared differentiation settings; these are integration boundaries, not measurement resets. Strict/ultrastrict and DOP853 predictions, original-cell reconstruction and extracellular transport-integral closure were checked. Candidate kinetic values are exported separately for prospective GLUT-only full-network replay, without replacing native defaults or changing MCT/pH mechanisms.

### 2.45. Free-network replay of the conditional GLUT candidate

The experimentally fitted conditional GLUT candidate was tested in the entire113-concentration-pool network with GLC and EGLC evolving as ODE states. A separate opt-in adapter replaces only raw VEGLC before complete-reaction positivity execution. The disabled adapter delegates to the existing phase-native model; all other raw reaction laws, including VELAC, are unchanged at a common state. The phase-volume matrix, exact55 measured J1 coordinates, latent initialization and other kinetic constants are fixed. Existing H0.58 geometry and the clamped diagnostic pHi context are retained rather than introducing a new acid/base model.

Three cases distinguish the phase-native reference, reversible GLUT with seed conductance and reversible GLUT with learned conductance at fixed affinities. Strict/ultrastrict unforced BDF replays proceed from J1 to J4, J10 and J46, extending only after numerical validity at the preceding horizon. No concentration curve is supplied to the RHS, and no observation-state reset, optimization, MCT activation or production promotion occurs. Daily executed-flux/state-increment balances, accepted-step Gauss4/8 raw/executed quadrature, checked positivity, raw/executed RHS closure and numerical convergence are assessed. Full node/weight/state/rate evidence and guard-pool reaction attributions are retained. Comparison with nominal source concentrations uses only actual post-initial samples; the absent J10 measurement is not interpolated into an experimental endpoint. Later-time comparisons remain internal and historically exposed rather than independent external validation.

### 2.46. Conditional inventory audit of joint glucose observations

The source-only observation audit additionally checked whether nominal paired GLC/EGLC increments could be imposed as exact balances. In the executed network, GLC has only VEGLC input and nonnegative VHK consumption. At fixed phase fraction H, transport cancels and $\int V_{HK}dt=-[H\Delta GLC+(1-H)\Delta EGLC]/H$. We computed the interval-wise H constraints and their intersection without altering source concentrations. A negative required HK integral is an inconsistency of exact nominal endpoints under the specified fixed-volume observation/network assumptions, not an experimental negative enzyme flux. This test does not exclude variable geometry, analytical uncertainty, unmatched aggregation or an incorrect observation denominator, and does not authorize adding a biochemical source without evidence.

### 2.47. Joint free-network glucose-energy-adenylate inference

Following the free-network GLUT test, a separately declared exploratory campaign fitted EGLC, GLC, LAC, ELAC, ATP, ADP and AMP jointly. Exact55 measured J1 coordinates and all latent initial pools, affinities, phase geometry, native VELAC, diagnostic pH clamp and reaction-availability threshold were fixed. Six log-factor coordinates changed GLUT conductance, HK/PFK capacities together, AK forward/reverse capacities together, GAPDH/PGK capacities together, PK and competing PEP phosphatase. The paired groups reduce degrees of freedom; they are not inferred protein complexes or independently identified shared capacities. HK retained its5.0 ceiling. Declared factor ranges are exploratory search limits rather than physiological priors. Historical purine/redox hypotheses were not silently promoted or altered.

Three starts were fitted on actual J4 observations, then continued through J10 using only J4/J8 source points after numerical auditing. Thus the two stages contained seven and14 postinitial observations, respectively. No J10 assay, dense experimental sampling or independent teacher observation was manufactured. A single mean-preserving lognormal variance was profiled across all included pools/times with the full normalizers retained. It describes common total residual dispersion, not isolated assay precision or measured covariance. Independent residuals and common relative variance are explicit working assumptions; individual pool errors remain visible. This sparse conditional fit does not establish six independent biological constants or support uncertainty intervals based on a known assay model.

The fitting RHS extracts the unchanged kinetic-expression prefix from the trusted local kernel AST and executes the full signed reaction vector once. A scalar finite test preserves MM arithmetic; no source module is monkey-patched. Conservative Jacobian support comes from state reads and both sides of participating reactions, not observed numerical zeros. L-BFGS-B finite differences use0.002 log-factor steps respecting bounds. Objective integration accounting includes Jacobian perturbations; a250-call primary cap can be extended to a cumulative600 only on optimizer failure. Terminal status and lowest valid training-NLL evaluated point are retained separately. The selected candidate is never chosen by later source errors. A final candidate undergoes original full-adapter strict/ultrastrict replay, accepted-step quadrature, whole-pool executed-balance reconstruction and source-extracted/full-path trajectory comparison before extension. J11-J46 evaluation is exposed internal temporal transfer, not independent external validation. No platform default, source value, initial state or biological readiness criterion is replaced by this exploratory fit.

### 2.48. Training-only non-regression constraints for protected joint calibration

The subsequent protected campaign retained the same six kinetic coordinates and bounds, exact55 measured J1 values, latent initialization, affinities, phase geometry, native VELAC, diagnostic pH clamp and0.001mM reaction threshold. PEP and G6P were added to the likelihood, giving nine channels and18 actual J4/J8 observations within a J1-J10 training horizon. The profiled normalized lognormal likelihood retains a shared total residual dispersion, not measured assay noise. All comparators must be rescored on these same18 values; seven-channel and nine-channel NLLs are not directly comparable.

For each of the nine pools, reference RMSE was reconstructed from the archived GLUT-only ultrastrict J1-J10 trajectory at J4/J8. A fixed numerical allowance was defined as1e-5mM plus1e-4 times that pool's reference RMSE. The fitting limit uses25% of this allowance and original-path verification its full value, reserving margin for solver differences. These are engineering tolerances, not biological accuracy or assay uncertainty. SLSQP enforces nine normalized inequality constraints while minimizing joint NLL; source observations and guard limits after J10 never enter parameter selection. The remaining46 source-channel representations are audited separately, not described as hard-constrained independent measurements.

Three starts are the feasible control, the previous rejected joint vector and their log-space midpoint. Cost, constraints and one-sided0.002 log-factor finite differences share each cached ODE evaluation. Actual cumulative caps are250 primary/600 secondary per start, including perturbations and control evaluation. Every trace is written incrementally, completed fits are sealed, and explicit resumption preserves prior call accounting. Optimizer termination is separate from feasibility; select only the lowest training-NLL valid point satisfying all nine fitting limits. Retain the control if no numerical-resolved gain of at least1e-4 NLL is found. Final original-RHS strict/ultrastrict J4/J10/J46 replays test numerical closure, source-extracted/full-path parity and the J4/J8 guard limits. A failure triggers control fallback without enlarging thresholds. No biological promotion follows from constrained numerical acceptance.

### 2.49. Fixed-parameter attribution of off-objective F6P and B23PG regression

To explain the protected fit's off-objective regressions without opening another parameter, we reused four sealed J1-J10 replays: GLUT-only control and protected candidate, each strict/ultrastrict. No ODE was reintegrated. Accepted-step Gauss4/8 node/weight/state/rate evidence reconstructed daily and exact-boundary window integrals. The archived matrix was required to reproduce complete balances dF6P/dt=VPGI+VTKL2+VTAL-VPFK, dB23PG/dt=VDPGM-V23DPGP, dB13PG/dt=VGAPDH-VPGK-VDPGM and dPEP/dt=VENOPGM-VPK-VPEP_PASE. Supporting G6P, P3G, F16BP and ATP budgets were also reconstructed. Signed production and consumption were integrated before netting. J1-J4 and J4-J8 were primary disjoint interpretation windows; overlapping additional windows were not pooled as independent observations.

Execution modifiers were defined as executed minus raw rate, so candidate-control integral differences decomposed exactly into raw-rate and modifier differences. Absolute availability loss was allocated to minimum-availability consumers, reversing consumers for negative signed rates and splitting ties. Per-consumer Gauss4/8 agreement was checked separately. These allocations describe the implemented threshold on a given trajectory, not causal intervention effects, microscopic exchange or physiological enzyme control. For PFK, the multiplicative investment factor was checked at14 saved shared states. The ordered decomposition I_new-I_control=(f-1)I_control+(I_new-f I_control) separates a fixed-control-state capacity term and a state-response remainder algebraically, without a counterfactual integration.

Exact source aliases B13PG/B23PG and P2G/P3G were reconfirmed and not treated as independent teachers. A proposed, inactive successor guard contract added F6P/B23PG RMSE constraints and pointwise PEP errors at actual J4/J8, retaining the earlier numerical allowance and excluding initial/late residuals. Neither these proposed guards nor later errors reselected the already sealed parent. Actual initial and accepted J1 states remained exact; machine-rounding differences in dense initial evaluation were checked separately. No source, latent initial state, kinetic constant, availability threshold, OPLAH rule or production default was changed.

### 2.50. Eleven-channel optimization with pointwise protection of PEP

After the fixed-parameter audit, a separately authorized successor activated the proposed F6P/B23PG RMSE constraints alongside the nine existing pool guards, plus separate absolute-error limits for PEP at J4 and J8. The same22 original source values entered one normalized mean-preserving lognormal likelihood with a shared profiled total residual dispersion; the13 inequalities are acceptance constraints on reused data, not13 additional independent observations. Duplicate aliases remained excluded. Neither J1 nor a fabricated J10 endpoint nor later source concentrations entered the fitting residuals.

All references were rederived from the same GLUT-only ultrastrict J1-J10 control and required to match the sealed proposal exactly. Each error retained allowance1e-5mM+1e-4 times its reference value,25% available during fitting and100% during original-path verification. These are numerical engineering allowances, not assay precision or biological accuracy requirements. The same six-coordinate kinetic box, paired capacities, affinities, exact55 measured J1 entries, latent initial pools, phase geometry, pH clamp, native VELAC, OPLAH and0.001mM availability threshold remained fixed outside the declared capacity factors. No RIB/redox initialization or additional kinetic degree of freedom was fitted.

Three SLSQP starts were the real feasible control, the prior nine-pool optimum and their log midpoint. Cost,13 constraints and their finite-difference Jacobians shared cached integrations. Step0.002 was retained; primary400 and cumulative secondary1000 actual objective integrations per start included derivative calls and control evaluation. Secondary restart followed unsuccessful optimizer termination. This larger budget than the earlier250/600 prevents claiming a pure matched-budget objective comparison. The lowest valid evaluated training-NLL point satisfying all13 fitting constraints was selected independently of terminal status, with control fallback below a1e-4 gain or after failed original-RHS audit. Strict/ultrastrict J4/J10/J46 replay required full executed-flux closure, quadrature and source-extracted/full-path parity; J10/J46 also rechecked all13 constraints at J4/J8. Later observations provided exposed temporal evaluation only. No fit, numerical convergence or guard acceptance automatically changed production defaults or established physiological validity.

When the SLSQP iterates stalled just outside the frozen fitting limits, a separate numerical-restoration successor was declared rather than relaxing those limits. A training-only near-boundary starting point was snapshotted; its screening tolerance was not an acceptance criterion. A maximum17 new objective integrations and two linearizations used step1e-4, log trust radius0.005 and a minimum-L1 correction toward an interior target reserving5% of the existing numerical allowance. All13 outer fitting/audit caps, six coordinates and biological context were unchanged. The selected valid point still required original full-RHS audits, and restoration was not interpreted as convergence to an NLL optimum. The original SLSQP campaign and three separately checked local directions retained separate traces and call accounting.

### 2.51. Conditional dissociation of HK and PFK capacities

A separately registered nested-model test examined whether the imposed HK/PFK
pairing restricted feasible calibration. All other constants were fixed at the
thirteen-guard restored candidate. The paired model had one log-capacity factor;
the dissociated model had two. Both retained the original primitive factors
[0.02,1.0] relative to HK5.0 and PFK2.5494306472mM/day, rather than applying
these bounds to already fitted capacities. All measured and latent initial
states, transport kinetics, phase geometry, pH, affinities, OPLAH and the
reaction-consistent availability threshold remained unchanged.

Nine predeclared fixed screens used factors1.05 and1/1.05 separately, together
and in opposite directions. Two starts per model used the exact restored
parent and a predeclared0.8 directed perturbation (paired change for the
one-coordinate model, HK-only change for the split model). Both models used
the same22 J4/J8 observations, profiled likelihood and thirteen outer guard
caps. The inner SLSQP target reserved1% of the existing numerical allowance
without modifying acceptance limits. Cached objective/constraint/Jacobian
calls used step1e-4, at most200 primary/500 cumulative actual integrations
per start, and a registered stagnation stop after120 calls with90 calls
without admissible1e-4 NLL progress. At most one same-coordinate inward repair
could use the remaining budget. Selection included all valid feasible probes
and the actual parent fallback, not merely the optimizer terminal point.

The simpler paired result was preferred unless dissociation improved its
training NLL by at least1e-4; this numerical tie rule was not a significance
test or a proof of global optimality. A changed paired comparator required
original-path early verification, and a changed selected model required
strict/ultrastrict J4/J10/J46 executed-flux and convergence audits with the
unchanged early guards. Later observations never ranked parameters. An
unchanged fallback reused its verified parent replays explicitly, without
claiming new simulations. This test isolated two capacities; it was not a
full reoptimization of all previously open groups or an ATP rescue claim.

### 2.52. Observation-aware objective comparison and necessary integrated feasibility

A separately registered branch compared profiled lognormal NLL, balanced
normalized squared residuals and a minimax epigraph on the same22 J4/J8
observations. All retained two independent HK/PFK coordinates, the original
primitive bounds, non-HK/PFK constants, measured and latent J1, phase geometry,
native lactate transport, pH and positivity policy. Old thirteen non-regression
caps became diagnostics for all three objectives, not hidden search constraints.
Physical/numerical acceptance and source exactness remained mandatory.

Each channel's normalization combined0.05 times its training median with0.2
times the absolute observed value. These engineering scales were not assay
standard deviations and were not profiled from model residuals. Balanced
fitting minimized mean channel MSE; minimax minimized the maximum through
eleven epigraph inequalities. No clipping or extra slope/endpoint/fold-change
costs were used. Two starts per J10 loss,220 actual objective integrations
including probes, step1e-4, max60 SLSQP iterations and ftol1e-6 were registered.
Absolute losses could score nonnegative zero predictions with an undefined
lognormal diagnostic. Four later scale re-scorings were not new fits.

Integrated reaction extents were tested with the phase-scaled stoichiometric
matrix on J1-J8/J15/J46 for eleven fitting channels and53 canonical source
representations. Twelve confirmed forward laws constrained extents nonnegative;
other directions were optimistically signed. Shared hypothetical measurement
adjustments linked adjacent intervals, remained zero at J1 and preserved
nonnegative endpoints. A linear program minimized their maximum working-error
multiplier. Zero-only channels stayed nominal zero without invented detection
limits. Capacities, full directionality, intermediate-state availability and
thermodynamic feasibility were relaxed: this was not stationary uFBA or an ODE
existence proof. Constant/monotone single or paired pool combinations supplied
analytic lower-bound certificates. Nonunique witnesses never replaced source data.

A predeclared eleven-channel J15 multiplier at most one enabled normalized/
minimax continuation from their J10 selections, adding actual J11/J15 values,
44 observations, with new frozen training scales. Original strict/ultrastrict
J10 replays checked all three J10 selections; J15/J46 replays checked both
continuations. Executed balances, quadrature, positivity and full/fast parity
remained distinct from experimental accuracy. Later exposed data were not blind validation.

A reusable observation layer required source, cohort, trajectory, donor or
explicit unknown identity, compartment and reference-litre metadata. Operators
supported absolute mM, verified linear relative signals with a positive
training-only nuisance scale, and explicitly referenced temporal ratios.
Relative signals were not relabelled absolute; a ratio reference did not add
a stochastic observation. Unknown normalization, unsupported treatment/control
ratios, duplicate channels and implicit unit conversions failed validation.
Shared-reference covariance was not claimed modelled. These operators and a
manifest-validation CLI were prerequisites, not evidence of generic raw-file
ingestion or experimental relative-data ODE calibration.

### 2.53. Network-observation coverage and adenylate sensitivity before renewed fitting

A separate fixed-initial-state branch used the J15 normalized-objective fit
as an explicit conditional baseline, not a production reference. Measured
Sheet1 J1 and all latent initial pools, Hct0.58, clamped pH7.2, native lactate
transport, glucose transport constants, OPLAH and the0.001mM reaction-consistent
availability threshold remained fixed. The pinned RBC-GEM1.3.0 source was
commit43fd381d9eb8a8a4079629012362312960e1c009. Reaction/GPR records, original
protein-table cells and source compartments were checked before network changes.

Closed reduced projections were ACITL/ACLY, CIT+ATP+COA -> ACCOA+OAA+ADP,
and ARGN/ARG1, ARG -> ORN+UREA, with declared Pi/H2O currency omissions.
An isolated optional RHS adapter required explicit positive Km values and
capacity before activation, otherwise reproducing the native RHS exactly.
No activity or kinetic constant was inferred from protein copy numbers. Both
capacities remained zero in all real-data ODE integrations. No historical
reaction, including OPLAH, was removed. CITR-producing or transporting routes
requiring absent species were recorded as incomplete, not silently lumped.

For each of J15/J46, four necessary integrated LP relaxations compared the
historical matrix, citrate-only, arginase-only and both added columns, with
the same53 canonical representations, working error bands, exact J1 and
optimistically signed extents except confirmed forward reactions. All55 source
channels remained archived with fitting, audit-only, alias or blocked-dynamic
roles. Constant-H diagnostics separately tested phase-weighted CIT/ECIT and
ARG/EARG conservation. Implied H and counterfactual time-varying H were not
fitted or measured volumes. A separately registered structural follow-up added
signed ARGSL/ASL, ARGSUC <-> ARG+FUM, without a rate law or ODE activation.
Its latent substrate inventory remained relaxed. Analytic constant/monotone
certificates and primal witnesses independently checked relaxation minima.

Twenty-five positive native kinetic parameters were resolved from frozen
overrides or literal native defaults, preserving their shared-reaction scopes.
Closed APRT/AMP-nucleotidase capacities were not reopened. Each parameter was
perturbed independently by exp(+/-h) and exp(+/-h/2), h=log(1.05), giving101
whole-network J1-J15 fast integrations including baseline. Only actual
J4/J8/J11/J15 values entered selection. For the12 positive ATP/ADP/AMP
predictions, local response columns were central derivatives of log concentration
with respect to log parameter. No pseudocount was used. Concentration residual
derivatives for all11 fitting pools, total adenylates and energy charge were
diagnostics; derived totals were not independent extra observations.

Full/half-step relative disagreement had to be at most0.25. A full-step response
norm had to exceed both1e-6 and ten times baseline fast/original log discrepancy.
These were engineering screening rules, not statistical confidence limits.
The descent direction followed the mean log-adenylate residual gradient; its
actual integrated probe had to reduce that mean squared log error by at least
0.1%, worsen no individual adenylate log MSE by more than1%, and keep each other
protected channel's working MSE within baseline+0.01*(1+baseline). Old thirteen
J4/J8 guards remained visible diagnostics under the parent contract. A greedy
ranking by actual gain admitted at most three columns with absolute pairwise
cosine below0.95. Thin SVD at relative1e-6 described local rank only.

Proposed single levers were replayed independently with the original ODE at
strict/ultrastrict tolerances, checking actual executed rates, quadrature,
daily balances, positivity, full/fast parity and admission at both tolerances.
Raw and executed rates were additionally evaluated at fixed baseline states
to distinguish direct parameter sensitivity from feedback along trajectories.
All55 source-channel errors and signed budgets for14 pools were reported.
No joint-lever test, new optimizer, J46 sensitivity selection or production
promotion was part of this design.

## 3. Results

### 3.1. Phase A generated 19 extracellular teacher fluxes

All 19 predefined extracellular species were present in the primary reference table, yielding 19 direct teacher-flux trajectories. Confidence varied according to direction consistency and smoothness. VEGLC had confidence 0.845, sign consistency 0.947, smoothness 0.731, mean absolute flux 0.286 mM day$^{-1}$, and maximum absolute flux 0.780 mM day$^{-1}$. VELAC had confidence 0.871, sign consistency 1.000, smoothness 0.695, mean absolute flux 0.553 mM day$^{-1}$, and maximum absolute flux 1.181 mM day$^{-1}$.

Lower scores occurred when the PCHIP derivative changed sign despite a transport rule expected to be nonnegative. For example, VEADE and VECIT scored 0.428 and 0.391. These reactions were retained in the complete Phase A artifact but were not given the same evidential status as VEGLC and VELAC. The focused Phase B dataset therefore used EGLC and ELAC concentrations with VEGLC and VELAC teacher fluxes.

An initial 14-day, two-trial Phase B run produced no optimized parameters and no loss improvement. It served only as an end-to-end software pilot for teacher dataset ingestion, native flux comparison, and artifact generation. All mechanistic conclusions below use the subsequent 46-day targeted campaigns.

### 3.2. A depletion-gated transport law captured extracellular glucose dynamics

Changing only the maximal rates of the original VEGLC and VELAC laws could not reproduce the observed EGLC slope and endpoint. We therefore tested an optional `transport_depletion_gate` family around glucose transport. The 46-day campaign used 32 local trials, four global trials, increased EGLC slope and endpoint weights, and teacher supervision on VEGLC and VELAC.

The selected transport candidate reduced direct FLA loss from 23.72 to 7.31. EGLC nRMSE decreased from 0.404 to 0.101. The simulated terminal EGLC concentration changed from 24.90 mM at the baseline to 13.21 mM, compared with 12.92 mM experimentally. ELAC nRMSE decreased from 0.552 to 0.330, and its terminal value increased from 15.70 to 19.88 mM, compared with 28.36 mM experimentally. The candidate was accepted locally because it improved the declared transport objective and passed the minimum EGLC-depletion gate.

### 3.3. Whole-panel replay rejected transport-only validity

Replay across all 55 mapped metabolites exposed a major internal inconsistency. Mean whole-panel nRMSE increased from 7.081 to 7.230 and median nRMSE from 0.889 to 0.915. Two metabolites improved, two regressed, and 51 were similar under the prespecified comparison rule. The two improved species were the optimized extracellular targets, EGLC and ELAC.

In contrast, intracellular GLC nRMSE increased from 0.358 to 8.281. Its day-46 value increased from 0.704 mM at baseline to 12.40 mM, compared with 0.826 mM experimentally. Intracellular LAC nRMSE increased from 0.216 to 0.957, with a terminal value of 0.166 mM instead of 6.463 mM. The transport candidate was consequently retained only as an EGLC transport hypothesis. It was not promoted as the model default.

This result is central to the FLA logic: a concentration-only analysis of EGLC would have suggested a successful calibration, whereas flux supervision and whole-panel replay localized the remaining failure to the coupling between import, intracellular glycolysis, lactate production, and export.

### 3.4. Opening hexokinase improved glucose use but did not restore feasibility

With the VEGLC gate fixed, $V_{\max,\mathrm{HK}}$ and $K_{m,\mathrm{ATP,HK}}$ were opened under strong safeguards. The best point reached the global $V_{\max,\mathrm{HK}}$ ceiling of 5.0 and $K_{m,\mathrm{ATP,HK}}=0.0601$. Relative to the gated seed, intracellular GLC nRMSE decreased from 8.281 to 6.302 and the day-46 GLC concentration from 12.40 to 9.75 mM. EGLC remained close to its target at 12.95 mM. Nevertheless, GLC remained more than an order of magnitude above the experimental endpoint and intracellular LAC remained poorly reproduced. The candidate failed acceptance and was not promoted.

A controlled VEGLC import-cap/feedback hypothesis further reduced GLC nRMSE from 6.301 to 5.111 and its terminal value from 9.75 to 7.62 mM. However, the EGLC endpoint shifted to 14.71 mM and violated the protected extracellular behavior. This hypothesis was also rejected. These runs showed that restricting import can reduce intracellular accumulation but cannot, by itself, reconcile extracellular depletion with downstream utilization.

### 3.5. Single-parameter energy and redox screens were informative negative results

Subsequent diagnostics opened one parameter at a time while resetting previously rejected parameters to their seed values. Narrow tests of $K_{m,\mathrm{ATP,HK}}$, $K_{m,\mathrm{NADH,NAD}}$, and $K_{m,\mathrm{ATP,PFK}}$ did not produce a candidate that improved the direct glycolytic targets while preserving ATP, PEP, G6P, GLC, LAC, EGLC, ELAC, VEGLC, VELAC, and VLDH safeguards. Optimization was aborted when a directed screen showed no sufficiently informative feasible point.

Lowering the ATP-production control $K_{m,\mathrm{ADP,ATP}}$ to 0.75-fold increased late ATP production by 21.1%. ATP consumption simultaneously increased by 21.0%, making the net balance more negative. GLC improved only modestly, while G6P and P3G endpoint safeguards failed. Stronger perturbations were therefore not tested. This result indicated compensatory ATP demand rather than a simple production limitation.

### 3.6. ATP sink attribution identified the glycolytic investment phase

Native flux decomposition achieved exact ATP consumption closure. Hexokinase accounted for 48.6% and phosphofructokinase for 41.6% of the induced late ATP consumption after the $K_{m,\mathrm{ADP,ATP}}$ perturbation; together they explained 90.2%. The dominant compensatory demand was therefore not an unrelated ATP sink. It was the expected consequence of accelerating the upper glycolytic investment phase.

This attribution redirected the analysis from another isolated ATP parameter to the flux matching sequence

\[
V_{\mathrm{HK}}\rightarrow(V_{\mathrm{PGI}}+V_{\mathrm{G6PDH}})
\rightarrow V_{\mathrm{PFK}}.
\]

### 3.7. Exact balance auditing separated implementation error from kinetic mismatch

The G6P and F6P balances in Eqs. (2) and (3) closed pointwise to a maximum absolute error of $3.55\times10^{-15}$ mM day$^{-1}$. Thus, the observed accumulation was not explained by a missing term in the implemented equations.

For the retained seed, the G6P output/input ratio was 0.045 during days 1-2, 3.382 during days 10-20, and 2.877 during days 40-46. The model therefore overfilled G6P early and drained it later, but G6P remained far above the measured trajectory (nRMSE 12.946). The corresponding F6P output/input ratios were 0.680, 0.399, and 0.471, with F6P nRMSE 27.008.

The non-oxidative PPP return terms $V_{\mathrm{TKL2}}+V_{\mathrm{TAL}}$ supplied 98.2% of early F6P input and approximately 47-48% during the middle and late windows. This finding motivated a reversible, option-controlled audit of VTKL2 and VTAL directionality. That audit remains a structural hypothesis and is not included as a calibrated result in the present manuscript.

### 3.8. External datasets are prepared but do not yet establish validation

The Bardyn control and supplemented datasets each yielded eight direct extracellular teacher fluxes over days 2-43. They provide a natural future test of whether a calibration learned in the primary condition transfers to a storage-medium perturbation. No Bardyn data were used to select the parameters reported above.

The Michel dataset yielded 60 local candidate fluxes, but the stoichiometric matrix rank was only 22. Its balance reconstruction had $R^2=0.998$ and nRMSE 0.043, demonstrating algebraic fit but not unique flux identification. A preliminary simulation with the current global Bordbar baseline and Michel-specific initial values produced a median concentration nRMSE of 0.790 across 28 metabolites. The mean nRMSE was 37.5 because several low-concentration pools diverged strongly, including R5P and urate. This replay demonstrates incomplete transfer and must not be interpreted as external validation.

### 3.9. Machine learning passed synthetic warm-start tests only

The Phase C ridge model was trained on 11 deterministic synthetic perturbations of $V_{\max,\mathrm{EGLC}}$, $V_{\max,\mathrm{ELAC}}$, $V_{\max,\mathrm{LDH}}$, and $V_{\max,\mathrm{HK}}$. Three held-out synthetic cases achieved a mean log-parameter absolute error of 0.0161, compared with 0.126 for the unmodified seed.

In a calibration-level smoke comparison using a two-day horizon and one trial per branch, the warm-start branch beat the default branch in all three held-out cases. Mean final loss decreased from 0.0541 to 0.00293, corresponding to a mean relative improvement of 94.3%. Because the data were generated by the same ODE family, the horizon was short, and the optimization budget was minimal, this result validates the software contract and the potential value of a warm-start. It does not demonstrate generalization to experimental data and is not part of the biological evidence for FLA.

### 3.10. Whole-model audit separated network corrections from calibration gains

A fixed-parameter 46-day audit compared the exact legacy replay, the corrected SAM network with legacy initialization, and the corrected network with compartment-strict historical initialization. Removing the artificial AMP coproduct had a negligible effect on the aggregate concentration fit, as expected for a structural correction, but reduced adenylate retention because SAM synthesis now removes an adenosyl moiety from the ATP/ADP/AMP pool. This correction was adopted on biochemical grounds and not because it improved the fitting objective.

The strict historical initialization modestly improved the aggregate nRMSE but did not pass pathway safeguards. It reduced intracellular GLC error while worsening G6P, F6P, ELAC, PEP, and adenylate retention. ATP still collapsed to approximately zero by the end of storage. Consequently, replacing generic latent states with historical priors is insufficient; latent initial pools must be estimated jointly under measured-state locks, pool-balance constraints, and temporal transfer guards.

The audited seed reproduced EGLC relatively well but retained severe intracellular defects: high GLC, G6P, and F6P, near-zero terminal ATP and B23PG, low intracellular LAC, and insufficient ELAC accumulation. These failures support temporal decomposition of calibration into an initialization/energy block (days 1-3), a glycolytic-relay block (days 3-10), and a transport/storage block (days 10-46), rather than a single global search over all kinetic constants.

### 3.11. Provenance and identifiability audits reduced the next calibration to one parameter

The exact J1-J3 B23PG balance closed pointwise in both the duplicated-data and QSS-B13PG contexts. Integrated VDPGM supply decreased from `0.42352` to `0.02822 mM` when the duplicated B13PG initial stock was removed, a loss of `93.34%`. Integrated V23DPGP changed by only `-0.03079 mM`. In the QSS context, VDPGM provided `3.74%` of the production required to follow the B23PG teacher given the modeled drainage. The current B23PG defect was therefore assigned to insufficient B13PG-to-VDPGM supply rather than excessive V23DPGP drainage.

The provenance audit confirmed that the B13PG/B23PG and P2G/P3G duplicate pairs predated the current FLA work and were present at first repository import. Their exact source annotation could not be recovered from the workbook. They were consequently quarantined according to the observation contract above rather than used as duplicate evidence.

The unoptimized seed had mean concentration nRMSE values of `6.1763`, `4.4476`, and `1.5302` in J1-J3, J3-J10, and J10-J46, respectively. G6P was the worst target in the first two blocks; GLC was worst in the long storage block. Local sensitivity analysis found practical ranks of 14, 24, and 10, compared with measured-pool stoichiometric ranks of 4, 8, and 5. The disparity shows that many parameters can alter native fluxes locally even though the observation system supports fewer independent balance directions.

After causal and sequential restrictions, only $V_{\max,\mathrm{DPGM}}$ remained open for the next reversible screen. $V_{\max,\mathrm{23DPGP}}$ and $K_{m,\mathrm{B23PG}}$ were held fixed, and no J3-J10 or J10-J46 parameter was opened. Thus, the identifiability analysis reduced rather than expanded the optimization scope.

### 3.12. A one-factor DPGM screen defined a guarded interval but did not restore energy homeostasis

The subsequent screen varied only $V_{\max,\mathrm{DPGM}}$ over deterministic multipliers `0.5`, `1`, `2`, `4`, `8`, `16`, and `32` relative to the fixed seed value `1.49719`. B13PG(0) remained at its exact J1 quasi-steady value, B23PG(0) remained locked to the observation, and all other initial states and kinetic constants were unchanged. No stochastic optimizer was used.

Over J1-J3, B23PG nRMSE decreased from `0.47409` at the seed to `0.22445` at `32-fold` capacity. The integrated fraction of teacher-required VDPGM supply increased from `3.74%` to `48.7%`. VDPGM remained responsive at the upper boundary: integrated supply increased by a further `44.5%` between `16-fold` and `32-fold`, despite a mean B13PG occupancy of only `0.00402` and mean GAPDH redox drive of `0.0499`. Thus, the tested range did not establish a pure capacity plateau.

Temporal guards nevertheless restricted the transferable interval. Multipliers from `2-fold` through `32-fold` passed J1-J3, but `8-fold`, `16-fold`, and `32-fold` failed the J3-J10 F6P non-inferiority gate. Only `2-fold` and `4-fold` passed the cumulative J1-J10 and J1-J46 guards. At J46, B23PG nRMSE changed from `0.56807` at the seed to `0.55413` and `0.52777`, respectively. Whole-panel mean nRMSE changed from `8.2489` to `8.2550` and `8.2588`, while the `4-fold` point consumed more of the F6P, GLC, and ELAC guard margins.

We therefore retained a reversible `2-fold` to `4-fold` diagnostic bracket, with `2-fold` ($V_{\max,\mathrm{DPGM}}=2.99439$ in model-day units) as the conservative anchor. Neither point was promoted. ATP still fell below `0.01 mM` near day `2.1`, and the data did not identify a unique DPGM constant within the guarded interval. This screen demonstrates that improving the Rapoport-Luebering branch can preserve whole-model behavior locally but does not resolve the upstream energy deficit.

A predeclared deterministic refinement then evaluated `2-fold`, `2.5-fold`, `3-fold`, `3.5-fold`, and `4-fold` capacity over all three temporal blocks. Three B23PG criteria (concentration nRMSE, endpoint error, and slope nRMSE) were balanced against J46 F6P, GLC, and ELAC nRMSE. Each objective was min-max normalized within the fixed grid; the mean normalized B23PG objective and mean normalized transfer cost defined a two-dimensional compromise whose Euclidean distance to the ideal origin was minimized. An interior point was retained only if it improved the best endpoint-anchor distance by at least `5%`.

All five points passed the cumulative guards. The `3-fold` point was the interior Pareto knee, with ideal distance `0.77357` versus `0.98353` for the best `2-fold` or `4-fold` anchor, a `21.35%` improvement. Its J46 metrics were B23PG nRMSE `0.54287`, B23PG endpoint error `0.27792`, F6P nRMSE `19.0808`, GLC nRMSE `6.31764`, and ELAC nRMSE `0.39431`. Repeating the complete grid with stricter solver tolerances (`rtol=10^{-5}`, `atol=10^{-8}`) selected the same `3-fold` point and yielded a `21.11%` compromise improvement. We therefore retained $V_{\max,\mathrm{DPGM}}=4.49158$ as a solver-robust diagnostic anchor. It was not promoted because ATP sustainability and global parameter uncertainty remained unresolved.

### 3.13. DPGM improvement diverts B13PG from ATP-producing PGK

We next compared the seed and retained `3-fold` DPGM branches over J1-J3 at the identical QSS-B13PG initial state. All parameters other than $V_{\max,\mathrm{DPGM}}$ were fixed. ATP production was reconstructed as $V_{\mathrm{PGK}}+V_{\mathrm{PK}}+V_{\mathrm{AK}}$, ATP consumption was decomposed over all 13 consuming reactions represented in the ODE, and the B13PG balance was reconstructed as $V_{\mathrm{GAPDH}}-V_{\mathrm{PGK}}-V_{\mathrm{DPGM}}$. Maximum pointwise closure errors were $3.55\times10^{-15}$ mM day$^{-1}$ for ATP and zero at machine precision for B13PG.

The perturbation left integrated $V_{\mathrm{GAPDH}}$ and the mean GAPDH NAD/NADH drive effectively unchanged (`+0.0048%` and `+0.0050%`). However, integrated $V_{\mathrm{DPGM}}$ increased by `171.08%`, whereas $V_{\mathrm{PGK}}$ decreased by `7.98%`. Consequently, the PGK share of B13PG drainage decreased from `95.58%` to `88.00%`. The PGK decrease accounted for `99.52%` of the gross `1.44%` loss of ATP production, identifying competition between the Rapoport-Luebering shunt and ATP-generating glycolysis under nearly fixed upstream supply.

ATP consumption decreased concurrently by `1.14%`, mostly through lower NDPK, HK, RKa, and PFK demand. This compensatory relief nearly masked the production loss in the integrated ATP pool, but did not restore energy sustainability: ATP crossed `0.01` mM at day `2.066` in the `3-fold` branch versus day `2.073` at the seed. Thus, the Pareto improvement in B23PG is mechanistically real but energetically costly. The `3-fold` point remains a reversible diagnostic anchor rather than a promoted whole-model calibration.

### 3.14. ATP-only flux inversion was robust in integral but infeasible pointwise

To determine the glycolytic production needed to reproduce measured ATP, we inverted the exact ATP balance in the fixed `3-fold` QSS-B13PG replay:

\[
V_{\mathrm{PGK}}^{\mathrm{req}}
=\frac{d\mathrm{ATP}^{T}}{dt}
+\sum_j V_{\mathrm{ATP\ consumption},j}
-V_{\mathrm{PK}}-V_{\mathrm{AK}}.
\]

All terms except the ATP concentration derivative were taken from the native replay. The corresponding upstream requirement was

\[
V_{\mathrm{GAPDH}}^{\mathrm{req}}
=\frac{d\mathrm{B13PG}}{dt}
+V_{\mathrm{PGK}}^{\mathrm{req}}+V_{\mathrm{DPGM}}.
\]

Because B13PG is latent, this second inversion was evaluated both with a quasi-steady derivative of zero and with the native latent-state derivative. No duplicated B13PG observation was used. Full-record PCHIP interpolation was compared with the linear J1-J4 secant because only the day-1 ATP measurement lies inside J1-J3 and the next measurement occurs on day 4.

The two ATP interpolation policies agreed on integrated required PGK flux within `0.014%`. The primary reconstruction required `1.58942 mM` integrated PGK flux, `2.835-fold` the native value. However, the pointwise requirement ranged from `-0.2293` to `7.6708 mM day^{-1}` and became negative at day `1.453`. Thus, an irreversible PGK rate cannot reproduce the ATP teacher while PK, adenylate kinase, and all ATP-consuming reactions are held at their native replay values. Although the current PGK hard ceiling of `40.0226 mM day^{-1}` was not exceeded, the fixed-state median and 95th-percentile capacity requirements were `63.48` and `170.42`, indicating that a capacity-only perturbation would not be self-consistent.

The QSS upstream reconstruction required `2.646-fold` the native GAPDH integral and peaked at `7.9339 mM day^{-1}`, above the current hard ceiling of `6.3899`. The native-latent B13PG derivative produced essentially the same result. We therefore rejected isolated PGK or GAPDH calibration from ATP alone. The sign inconsistency and sparse early ATP sampling require a joint ATP-ADP-AMP balance analysis, including adenylate-kinase directionality, before another kinetic parameter can be opened.

### 3.15. Joint adenylate balances localized a total-pool source defect

ATP alone does not distinguish redistribution among adenylates from net creation or loss of the total adenylate pool. We therefore reconstructed the three native balances simultaneously. Under the corrected SAM stoichiometry, summing the ATP, ADP, and AMP equations cancels PGK, PK, adenylate kinase, and all ATP-to-ADP investment reactions, yielding

\[
\frac{d(\mathrm{ATP}+\mathrm{ADP}+\mathrm{AMP})}{dt}
=V_{\mathrm{AK2}}-V_{\mathrm{SAM}}+V_{\mathrm{ADSL}}
+V_{\mathrm{APRT}}-V_{\mathrm{AMPD1}}.
\]

Here AK2 denotes adenosine kinase, which introduces an adenosine moiety into the adenylate pool, whereas AK denotes reversible adenylate kinase. Exact pointwise closures were obtained for ATP, ADP, AMP, the split forward/reverse AK rate, and the total pool, with a maximum error of $3.55\times10^{-15}$ mM day$^{-1}$.

Over J1-J3, the sum of the PCHIP ATP, ADP, and AMP teachers decreased by `0.10187 mM`, whereas the native model total increased by `0.46368 mM`. The required integrated total-pool correction was therefore `-0.56481 mM`. Numerical non-negativity damping contributed only `+0.00072 mM`. The discrepancy is consequently biochemical rather than a boundary artifact. A J1-J4 linear sensitivity reconstruction changed the missing total integral by only `0.44%`.

Native adenylate kinase was forward (`2 ADP -> AMP + ATP`) throughout J1-J3. The exact joint correction required reverse kinase throughout the same window, with a range of `-0.55685` to `-0.01782 mM day^{-1}`; `92.7%` of this trajectory lay within the current hard forward/reverse bounds. Nevertheless, AK cancels exactly from total adenylate. Separate AK estimates derived from ATP, ADP, and AMP had integrated values of `2.97845`, `1.39495`, and `-0.75337 mM`, confirming that no single AK trajectory can reconcile all three teachers while the native total-pool terms remain fixed.

APRT was the dominant modeled adenylate source (`+0.53882 mM` integrated), followed by ADSL (`+0.09548`) and adenosine kinase (`+0.01561`). AMPD1 and SAM transfer removed `0.15553` and `0.03143 mM`. An APRT-only inversion required a negative integrated flux (`-0.02599 mM`) and remained nonnegative for only `8.8%` of J1-J3. Thus, complete APRT suppression is necessary but insufficient; an additional sink is required. AMPD1 is the next diagnostic candidate because it removes AMP to IMP directly, while increasing SAM transfer would perturb ATP and ADOMET. No adenylate kinetic parameter was promoted from this audit.

### 3.16. APRT suppression exposed a residual AMPD1 capacity deficit

We next performed a reversible fixed-kinetic diagnostic in which only `vmax_VAPRT` was changed, from `4.08799` to zero. The fixed `vmax_VDPGM = 3x` QSS-B13PG state, all remaining kinetic constants, and the J1-J3 integration contract were unchanged, and no optimization was performed. ATP, ADP, AMP, IMP, ADE, PRPP, ADOMET, adenylate-kinase, and total-adenylate balances were reconstructed pointwise. ATP, ADP, AMP, IMP, and ADE were compared with Brodbar concentration teachers, whereas the unobserved PRPP and ADOMET pools were used only as positivity and non-divergence safeguards.

VAPRT suppression changed the modeled total-adenylate variation from `+0.46368` to `-0.07310 mM`, compared with `-0.10187 mM` for the PCHIP teacher. Total-pool nRMSE consequently decreased from `0.30122` to `0.00824`. ATP was non-inferior (`1.12458` versus `1.12467`), while the AMP, IMP, and ADE nRMSE values decreased from `6.55470` to `5.14412`, from `0.42329` to `0.26983`, and from `4.41204` to `0.14011`, respectively. Exact balance closure was preserved to `3.89 x 10^{-15} mM day^{-1}`, and all states remained positive. PRPP increased to `0.11686 mM` at day 3, defining an explicit latent-pool guard for subsequent tests.

The remaining AMPD1 sink required by the concentration-derived total-pool teacher was calculated without fitting:

\[
V_{\mathrm{AMPD1}}^{\mathrm{req}}
=V_{\mathrm{AK2}}-V_{\mathrm{SAM}}+V_{\mathrm{ADSL}}
+V_{\mathrm{APRT}}-\frac{dA_{\mathrm{tot}}^{T}}{dt},
\qquad
A_{\mathrm{tot}}^{T}=\mathrm{ATP}^{T}+\mathrm{ADP}^{T}+\mathrm{AMP}^{T}.
\]

After VAPRT suppression, native and required VAMPD1 integrals were `0.15355` and `0.18163 mM`, respectively, leaving a residual `0.02807 mM` sink requirement. The required trajectory was positive throughout J1-J3 and ranged from `0.04408` to `0.09787 mM day^{-1}`, but remained below the current VAMPD1 hard ceiling for only `11.2%` of the interval. At the fixed replayed states, the median, 95th-percentile, and maximum required `vmax_VAMPD1` were `0.10295`, `0.10397`, and `0.10399`, approximately `1.24-1.25-fold` the seed value. A linear J1-J4 teacher and a strict-solver replay reproduced the classification and capacity scale. We therefore retained APRT suppression as a structural diagnostic rather than a promoted parameter and defined a narrow deterministic AMPD1-capacity screen as the next falsifiable step.

### 3.17. Sequential AMPD1 screening selected a conservative diagnostic anchor

We evaluated `vmax_VAMPD1` at `1.0-, 1.1-, 1.2-, 1.25-, 1.3-, 1.4-, and 1.5-fold` its seed value (`0.0830092`) while maintaining `vmax_VAPRT=0`, the `3x` QSS-B13PG state, and all other kinetic constants. No adaptive optimization was used. Candidates first had to improve total-adenylate trajectory nRMSE, derivative nRMSE, endpoint error, AMP nRMSE, and the concentration-derived VAMPD1 teacher-flux nRMSE over J1-J3. ATP, ADP, IMP, ADE, PRPP, ADOMET, VAK directionality, exact balance closure, and whole-model non-negativity were protected. Only passing points were relayed to J1-J10 and then J1-J46; mean and median nRMSE over the complete mapped Brodbar panel were additionally protected at J46.

The `1.1x`, `1.2x`, `1.25x`, and `1.3x` capacities passed J1-J3 and J1-J10. Standard J1-J46 replay retained `1.1x-1.25x`, whereas `1.3x` failed only the VAK-directionality guard. A complete strict-solver replay retained `1.1x-1.2x`; the upper boundary therefore remained numerically sensitive, but the predeclared smallest-capacity selection was invariant. The selected value was `vmax_VAMPD1=0.0913101` (`1.1x`).

At J1-J3, this point reduced total-adenylate trajectory nRMSE from `0.00824` to `0.00343`, derivative nRMSE from `0.33825` to `0.22522`, endpoint error from `0.01691` to `0.00791`, and VAMPD1 teacher-flux nRMSE from `0.18529` to `0.12226`. At J1-J46, the corresponding changes were `0.33313` to `0.24452`, `1.12329` to `1.11315`, `0.39026` to `0.20607`, and `0.87426` to `0.86660`. AMP nRMSE improved from `5.31243` to `4.90597`, while ATP and ADP changed by less than `0.001%`. The whole-panel mean nRMSE increased by only `0.261%`, and the median improved by `0.029%`. Strict-solver values closely reproduced the selected trajectory (`0.24481` total nRMSE; `0.20689` endpoint error).

The maximum selected balance residual was `2.03 x 10^{-15} mM day^{-1}`, and no state became negative. During long-horizon quality control, the independent VAK decomposition was aligned with the same `10^{-6} mM` substrate floor used by the ODE; this repaired diagnostic closure at depleted states without changing the model rate law. Despite passing all declared gates, the AMPD1 point was not promoted: AMP remained substantially mismatched, PRPP and ADOMET approached their numerical floor by J46, and hard APRT suppression had not yet been tested against the exact IMP and purine-transfer balances.

### 3.18. Independent purine teachers rejected both hard APRT suppression and simple APRT restoration

The selected AMPD1 anchor was next audited without refitting. The IMP balance was reconstructed as

\[
\frac{d\mathrm{IMP}}{dt}=V_{\mathrm{HGPRT1}}+V_{\mathrm{AMPD1}}
-V_{\mathrm{ADSS}}-V_{\mathrm{IMPH}}-V_{\mathrm{nucleo2}}.
\]

At J1-J46, the actual AMPD1 integral was `3.76275 mM`, compared with `3.84357 mM` conditionally required by the IMP teacher. The residual was only `0.08082 mM`, and IMP nRMSE improved modestly from `1.00544` to `0.99646`. Integrated IMP sources were HGPRT1 (`+0.92344 mM`) and AMPD1 (`+3.76275 mM`); sinks were ADSS (`-1.50985 mM`), IMP dehydrogenase (`-2.58858 mM`), and IMP nucleotidase (`-0.69831 mM`). All balance reconstructions closed within `3.10 x 10^{-16} mM day^{-1}`.

The adenine pair supplied an independent, nominally direct FLA constraint. Because the current equations are

\[
\frac{d\mathrm{ADE}}{dt}=-V_{\mathrm{EADE}}-V_{\mathrm{APRT}},
\qquad
\frac{d\mathrm{EADE}}{dt}=V_{\mathrm{EADE}},
\]

their sum gives $V_{\mathrm{APRT}}^T=-d(\mathrm{ADE}^T+\mathrm{EADE}^T)/dt$. The measured pair decreased by `0.99211 mM` over J1-J46 and implied positive APRT throughout, whereas the VAPRT-zero model conserved this pair exactly. Hard APRT suppression is therefore inconsistent with the adenine-pair trajectory under the present concentration scaling.

However, the independently reconstructed total-adenylate balance required an integrated APRT flux of `-0.34019 mM` under the same AMPD1 anchor. Its requirement changed sign across storage blocks, and the two APRT teachers disagreed by `1.33229 mM`. Furthermore, PRPP production integrated only `0.12595 mM`, while HGPRT1 and HGPRT2 already consumed `0.92344` and `0.20720 mM`; PRPP reached `7.23 x 10^{-6} mM` at J46. Restoring the approximately `0.992 mM` APRT flux suggested by ADE+EADE would therefore violate both total-adenylate and PRPP ownership. Strict-solver replay reproduced these results.

This incompatibility is a structural FLA result rather than a new parameter estimate. ADE and EADE are currently combined in standardized model concentration units; an explicit intracellular/extracellular volume conversion may change the direct teacher magnitude. If plausible scaling cannot reconcile the constraints, the network requires an additional adenine-loss route, potentially extracellular EADE degradation or removal, rather than simple APRT restoration. Neither APRT nor AMPD1 was promoted from this audit.

### 3.19. Purine improvements at fixed states did not transfer to the free ODE

A storage-dependent AMPD1 capacity, with initial maximum rate 0.125 and decay coefficient 0.0125 day$^{-1}$, improved fixed-state attribution but reduced the combined trajectory objective by only approximately 2.92% in the free J1-J46 replay, despite approximately 41.88% improvement in its integrated teacher objective. IMP endpoint error worsened, preventing promotion. A subsequent VADSS-specific GTP-affinity map substantially improved its fixed-state score, but none of five free-ODE candidates passed the joint guards. These negative results do not support adding purine capacity as a stand-alone repair.

In the AMPD1-decay replay, ATP fell below 0.01 mM near day 2.1 and ended at $2.7094\times10^{-5}$ mM compared with 0.46976 mM in the table. Conditional replacement of both ATP and ADP at fixed guanylate states increased predicted NDPK activity. This does not isolate ATP causally or prove that a refitted energy-corrected model would fail.

### 3.20. Whole-network testing uncovered a structural parsing omission

Executable tests found that V6PGD and V23DPGP were present in the ODE and its tracker but omitted from the extracted stoichiometry because their names contain a digit immediately after V. Correcting the parser restored the GO6P/RU5P/NADP/NADPH and P3G/B23PG reaction coefficients. On eight positive-state probes, all 113 concentration equations then matched the parsed reaction balances within $7.11\times10^{-15}$ mM day$^{-1}$. Historical internal-flux teachers, reachability masks and rank calculations that used the incomplete matrix require regeneration; the correction does not alter kinetic trajectories directly.

Near depleted pools, exact effective closure coexisted with nonzero raw residuals due to state-wise damping. The archived AMPD1-decay trajectory showed an approximately +0.01099 mM integrated discrepancy in the ATP+ADP+AMP balance, with a maximum instantaneous discrepancy of 0.00736 mM day$^{-1}$. These are sampled numerical diagnostics, not measured pool production. Their size does not explain the entire ATP failure, but they must not become supervision for new kinetic fluxes.

### 3.21. Observation resets improved local availability without establishing calibration

The 13-interval reset diagnostic reported an energy-panel mean endpoint nRMSE of 3.397 compared with 4.794 in the continuous replay. The corrected elapsed-time fraction with ATP at or above 0.01 mM was 26.53% with resets versus 2.37% without resets; earlier values of 28.25% and 2.44% incorrectly represented sample fractions as durations. The mean normalized continuity-jump loss was 28.591 and was not optimized. No kinetic sensitivity restoration, temporal validation, or successful multiple-shooting calibration is claimed from this diagnostic.

### 3.22. Corrected PPP constraints exposed underdetermination and numerical boundary defects

The four measured PPP/shunt balances had rank 4 in the 22-reaction subgraph, leaving 18 null directions. Only ten columns were represented in the measured rows; restricting to those columns still left six null directions. The omitted V6PGD and V23DPGP columns had previously made VPGLS and VDPGM appear individually identifiable. The corrected matrix identified neither of these, nor any other individual reaction, from the four measured balances alone. Higher ranks obtained after adding latent rows were not interpreted as additional experimental evidence.

At identical fixed kinetics and initialization, strict accepted-step integration passed all 565 pool/quantity quadrature checks, whereas the standard integration failed nine. Both simulations reconstructed the effective RHS within $3.56\times10^{-15}$ mM day$^{-1}$ but failed raw closure, with a maximum whole-model defect of approximately 0.144424 mM day$^{-1}$. Derivative clipping was inactive. In the strict replay, state-wise damping contributed +0.0114236 mM to the cumulative ATP+ADP+AMP balance, comprising +0.00887729 mM for ADP and +0.00254635 mM for ATP. Corresponding GO6P and B13PG corrections were +0.00397148 and +0.019655 mM. NAD+NADH and NADP+NADPH remained conserved within roundoff. The largest absolute strict integrated solver residual across the audited windows was approximately $2\times10^{-6}$ mM.

The GO6P, ATP and adenylate corrections were not invariant between standard and strict tolerances under the declared budget criterion. Consequently, the strict values are better quadrature-resolved estimates for that trajectory, not established solver-converged constants. They supersede neither historical trajectories nor their parameter contexts automatically.

Raw accepted B13PG and ADP reached minima of $-1.07350\times10^{-5}$ and $-1.15022\times10^{-6}$ mM in the strict run. Sampled negative pools retained negative executed derivatives because the positive kinetic input floor leaves residual consumption at the zero boundary. The observations therefore do not support attributing the failure solely to solver undershoot. Effective closure and a positive substrate floor did not ensure a nonnegative physical trajectory.

These numerical defects did not account for the complete predictive mismatch. Strict ATP ended at approximately $3\times10^{-5}$ mM against 0.46976 mM in the reference table. The conditional integrated F6P requirement for VTKL2+VTAL was 0.354852 mM against 1.717250 mM simulated, despite effectively zero F6P numerical correction. No individual PPP rate or kinetic constant was inferred from these conditional quantities. No parameter was optimized or promoted. A reversible, reaction-consistent positivity diagnostic at fixed kinetics is required before using depleted-pool residuals to guide another calibration.

### 3.23. Reaction-consistent limiting repaired the numerical boundary, not prediction

The opt-in policy passed 339 zero-boundary probes across the initial and two archived depleted-state contexts. The final initialization was bit-identical to the archived binary day-1 state. The complete legacy strict J1-J46 accepted time/state arrays were also reproduced bit-for-bit, establishing rollback compatibility for this fixed context. Twelve replays compared two policies, two solver tolerances and three horizons without optimization or observation resets.

Reaction-consistent strict integration remained positive at every horizon and passed all 452 pool/quantity quadrature checks per horizon. The J46 raw accepted minimum was $8.14761\times10^{-7}$ mM for ADP; the minimum sampled dense-interpolant value was $8.14731\times10^{-7}$ mM. B13PG ended at $7.47477\times10^{-6}$ mM. Executed stoichiometric closure was within $3.56\times10^{-15}$ mM day$^{-1}$, and the 20 encoded left-nullspace invariant directions were preserved within $4.13\times10^{-15}$ mM day$^{-1}$. The nonreaction adenylate source of +0.0114236 mM under legacy damping disappeared to roundoff. This conservation result concerns the encoded matrix, not an independent elemental-balance validation of every reaction.

The reaction-consistent standard runs also remained positive but failed eight quadrature checks at J10 and 16 at J46. At J46, all 116 pool/group state-change comparisons met the declared standard/strict tolerance; five effective-balance integrals and two reaction-rate-change integrals did not. The maximum strict integrated solver residual was $1.90\times10^{-6}$ mM. These findings support the boundary construction and strict accepted-step accounting, but do not establish strict/ultrastrict convergence. The all-case numerical-integrity criterion remained unmet.

The policy strongly altered near-depletion rates. On the reaction-consistent trajectory, native VPGK integrated to 14.7626 mM whereas its executed limited rate integrated to 0.670233 mM; VDPGM changed from 12.1508 to 4.80649 mM. These are same-state native/limited evaluations, not flux integrals from two separately evolving simulations. They show that the $10^{-3}$ mM availability threshold is an influential rate modifier and cannot be treated as validated biological regulation or fitted as an experimental source.

Predictive failures persisted. Strict ATP ended at $1.64866\times10^{-5}$ mM against 0.469757 mM in the reference table. For postinitial observations, GLC nRMSE deteriorated from 6.58931 to 7.04889, ELAC from 0.369576 to 0.397191, and LAC from 0.960311 to 0.971356. G6P improved from 12.8854 to 11.3949 and B23PG from 0.706404 to 0.639804, while their terminal concentrations remained mismatched. The 53-row postinitial panel mean changed only from 8.39423 to 8.37775; these metrics exclude J1 and duplicate aliases and are not interchangeable with historical all-time metrics. No numerical policy or kinetic candidate was globally promoted. Threshold sensitivity and tighter-tolerance verification are required before the next B13PG/ATP attribution or kinetic calibration.

### 3.24. The provisional reference converged numerically but remained threshold-sensitive

Reaction-consistent limiting with strict BDF and $\tau=10^{-3}$ mM was adopted as the explicit provisional working profile. The complete accepted time/state arrays reproduced the preceding reaction-consistent strict replay bit-for-bit. Legacy remained the historical kernel default; archived legacy RHS probes differed by at most $1.12\times10^{-15}$ mM day$^{-1}$. Adoption changed neither the archived kinetic constants nor their unpromoted diagnostic status.

All six fixed-kinetic J1-J46 replays completed. At each of the three predeclared thresholds, all 978 strict/ultrastrict comparisons passed. Each replay passed all 452 pool/quantity and 300 individual reaction/quantity quadrature checks. Maximum dense concentration differences between solver tolerances were $1.28\times10^{-6}$, $9.38\times10^{-7}$ and $1.25\times10^{-6}$ mM for thresholds $10^{-4}$, $10^{-3}$ and $10^{-2}$ mM, respectively. No accepted or sampled dense concentration was negative, and executed closure remained within $3.56\times10^{-15}$ mM day$^{-1}$. These results establish convergence under the declared fixed-context comparison contract, not for arbitrary future parameters or every unsampled interpolant point.

Threshold sensitivity was substantial despite solver convergence. In ultrastrict replays, reducing or increasing the threshold relative to $10^{-3}$ mM caused 39 or 66 dense pool trajectories to exceed the same comparison band. Across state, interval, reaction and budget quantities, 462/978 and 639/978 comparisons exceeded it. These are modifier-sensitivity results, not numerical convergence failures.

| Ultrastrict quantity | $\tau=10^{-4}$ mM | $\tau=10^{-3}$ mM | $\tau=10^{-2}$ mM |
|---|---:|---:|---:|
| ATP at J46 (mM) | 1.58795e-6 | 1.64866e-5 | 1.40143e-4 |
| ADP at J46 (mM) | 2.08146e-8 | 1.67349e-6 | 3.75159e-5 |
| G6P at J46 (mM) | 0.00445768 | 0.00465130 | 0.00719845 |
| B23PG at J46 (mM) | 0.000173845 | 0.000405887 | 0.00158932 |
| Integrated executed VPGK (mM) | 0.645152 | 0.670233 | 0.939334 |
| Integrated executed VDPGM (mM) | 4.83265 | 4.80649 | 4.70985 |
| Integrated executed V6PGD (mM) | 3.37590 | 3.37001 | 3.43356 |

Across the 100-fold threshold range, terminal ATP changed about 88-fold and executed VPGK about 46%. Native VPGK evaluated on each corresponding trajectory integrated to 14.6492, 14.7626 and 60.9452 mM, respectively. Each native/executed pair is evaluated on the same trajectory; these quantities are not experimental gross flux measurements. The threshold therefore remains an influential numerical rate-law modifier, not validated physiological regulation. ATP remained far below the local reference endpoint 0.469757 mM at every threshold; GLC remained near 10.4 mM versus 0.826365 mM, and ELAC near 16.7-16.9 mM versus 28.363716 mM. The provisional threshold was retained at $10^{-3}$ mM without selection by predictive loss. No kinetic optimization or promotion was performed. Executed-flux B13PG/ATP attribution and measurement/absolute-accuracy contracts remain prerequisites for the next calibration.

### 3.25. Executed budgets revealed an early energy deficit and a changing PGK limiter

Both repeated replays passed all 215 attribution quadrature checks and all 215 strict/ultrastrict comparisons. Executed closure was within $3.56\times10^{-15}$ mM day$^{-1}$, with no negative accepted or sampled dense concentrations. Maximum window solver residuals were $1.62\times10^{-6}$ and $2.22\times10^{-7}$ mM. Independent explicit equations reconciled 272 reaction terms and 64 allocated-loss totals with the preceding archive within $7.11\times10^{-15}$ mM.

ATP fell from 0.932992 to 0.00132197 mM over J1-J3. Executed production and consumption integrated to 3.354344 and 4.286015 mM, accounting for the -0.931670 mM change without a numerical material source. HK/PFK consumed 2.277206/0.956468 mM, or 75.45% of ATP consumption. Their combined 3.233674 mM investment exceeded PGK+PK production of 1.352359 mM. Forward AK supplied 1.950491 mM ATP but consumed 3.900981 mM ADP, or 73.54% of total ADP consumption. ADP fell from 1.169400 to 0.000330904 mM. NDPK's ATP-positive and ATP-negative contributions were 0.051494/0.449487 mM, distinct from its net -0.397993 mM contribution.

The minimum-availability consumer limiting PGK changed over time. All early J1-J3 reduction was allocated to B13PG: native/executed PGK integrals were 3.086995/0.542806 mM. At J3-J10, ADP accounted for 95.68% of reduction, and after J10 it accounted for all of it. Across J1-J46, ADP/B13PG accounted for 80.53%/19.47% of the 14.092400 mM reduction. PGK received 88.52% of executed B13PG drainage early, 8.16% in the middle window and only 0.334% late. Late shunt dominance therefore did not establish DPGM reduction as a solution to the early ATP/ADP deficit. These shares characterize the adopted limiter and encoded fluxes, not independently established biological control.

The unobserved redox initialization also affected native GAPDH regulation. NAD/NADH started at 1 mM each without corresponding reference-table rows. The native redox MM factor fell from 0.320279 at J1 to 0.018580 at J3 while GA3P rose from 1.635591 to 4.444030 mM. Neither this initialized trajectory nor its redox-factor decline is an experimental teacher. Redox-state feasibility must therefore be reviewed before interpreting a fitted NADH affinity as a biochemical estimate.

At the first measured ATP interval J1-J4, the tabulated change was +0.146772 mM whereas the executed integral was -0.932487 mM. Conditional required PGK was 1.691940 mM against 0.612681 mM executed; six of 13 intervals required negative conditional PGK under the fixed-neighbor assumption. This rejects that PGK-only explanation within the present nonnegative law, not the full network or the measurements. No kinetic optimization or promotion followed. The next task is a fixed-kinetic J1-J4 feasibility contract for executed ATP-ADP-AMP balances and latent NAD/NADH initialization, including AMP/purine transfers and measurement/absolute-accuracy requirements before coupled dynamic sensitivity.

### 3.26. The J1-J4 contract separated total-pool closure from failed adenylate partitioning

All eight fixed-kinetic redox-initialization replays passed 223 quadrature checks each and all 1344 strict/ultrastrict comparisons. No accepted or sampled dense concentration was negative; the minimum checked value was $10^{-6}$ mM. Maximum executed closure was $3.55\times10^{-15}$ mM day$^{-1}$. Maximum strict/ultrastrict window solver residuals were $8.47\times10^{-7}/8.52\times10^{-8}$ mM. Baseline prefixes agreed with the preceding verified replay within $1.07\times10^{-14}$ mM. Independent explicit equations reconciled 224 window balances within $3.33\times10^{-15}$ mM and recomputed energy charge and conditional AK requirements.

In the baseline, J1-J4 total adenylates declined by 0.213800 mM versus 0.149077 mM in the nominal local reference. The executed total-pool contributions were +0.143890 ADSL, +0.015602 AK2, -0.341839 AMPD1 and -0.031453 SAM, with APRT and AMP nucleotidase zero. The J4 total was 2.627505 versus 2.692228 mM, a difference of approximately -2.40%, but this modest total discrepancy concealed ATP/ADP depletion and AMP accumulation. ATP, ADP and AMP were 0.000505122, 0.000042261 and 2.626957 mM versus 1.079765, 1.073256 and 0.539208 mM; energy charge was 0.0002003 versus 0.600392. Thus total-pool agreement alone is insufficient for calibration.

The executed AK integral was 1.950617 mM. Conditional requirements from ATP, ADP and AMP were 3.029876, 1.414010 and -0.137132 mM, respectively. Their disagreement excludes the exact fixed-neighbor single-AK explanation, not the full coupled network or statistical compatibility of the measurements. Measurement uncertainty remains unavailable.

Historical nominal NAD/NADH values were 0.015633767 and 0.002738327 mM, giving a total of 0.018372095 mM and NADH fraction 0.149048, versus the current total 2 mM and fraction 0.5. Changing total, ratio or both altered early transients but left J4 ATP at 0.000505-0.000677 mM and ADP at 0.0000423-0.0000496 mM. None of the four diagnostic initializations restored the tabulated endpoints. This screen does not identify biological redox priors or establish infeasibility over the complete latent-state domain. NADP/NADPH were not varied.

The contract was constructed and numerically verified, but biological readiness remained blocked by six unresolved prerequisites: upstream lineage, normalization, observation uncertainty, biological time origin, supported redox priors and absolute accuracy limits. All 605 QA tests passed; this is software verification, not biological validation. No optimization, threshold fitting, kinetic promotion or initialization promotion followed. A coupled investment/adenylate/GAPDH-PGK sensitivity protocol is the next diagnostic to prepare, with scientific contracts resolved before optimization.

### 3.27. Readiness preparation did not justify numerical accuracy thresholds or redox priors

Local workbook inspection verified ATP, ADP and AMP J1/J4 cells at Sheet1 B9/C9, B3/C3 and B5/C5, respectively, and historical NAD/NADH input rows 84/85. The workbook retains a text-import connection named `cellbb` referring to an external `cellbb.txt`. The subsequent audit in Section 3.32 localizes it to the Feuil1 coefficient table, not the Sheet1 concentration table. The external file was not recovered or read. A nominal mM header and model-day labels do not establish their biological denominator or time origin.

The publication candidate for Bordbar describes 20 SAGM units over 42 days ([primary record](https://pubmed.ncbi.nlm.nih.gov/26749434/)), whereas Qi's analysis uses a separate ADSOL cohort and its own normalization procedure ([primary article](https://pmc.ncbi.nlm.nih.gov/articles/PMC5487983/)). Consequently, neither Qi's reported variability nor its normalization was imported into the local workbook. A subsequent primary reanalysis reports 45-day sampling (Section 3.32), so the earlier 42/46 mismatch is not sufficient evidence of endpoint extrapolation. The exact upstream mapping, time origin, paired uncertainty and redox prior support remain unresolved.

The new scoped guard therefore remained blocked on 13 explicit checks across six scientific domains, with no biological endpoint pass assigned to the 24 existing scenario/solver/pool comparisons. A native command-line preflight correctly returned exit code 2 under `--require-ready`. The coupled sensitivity protocol was prepared as 19 configurations/38 planned replays but none was executed. No threshold, initial state or kinetic parameter was fitted or promoted. This preparation makes the missing evidence and permitted future calculation explicit; it does not resolve the scientific prerequisites by assertion.

### 3.28. Synthetic transport recovery exposed sensitivity to teacher reconstruction

The separate benchmark completed 13 conditional capacity fits and 28 uninterrupted J1-J46 ODE replays, including a strict/ultrastrict truth pair and a pair for every recovered parameter vector. Known glucose/lactate capacities were 1.757178713 and 1.983609745 in the kernel's nominal rate units. The exact-state/executed-flux oracle recovered both values exactly at stored precision from all three starts, with zero held-out trajectory error. Both dense-clean methods passed their preregistered synthetic parameter and transport-prediction checks. No experimental acceptance limit or biological redox prior was supplied by this result.

With dense clean concentrations, pointwise PCHIP supervision recovered glucose/lactate capacities with 1.424%/0.1179% relative error; held-out EGLC/ELAC excursion nRMSE was 0.01944/0.0007695. Interval supervision reduced relative parameter errors to $3.70\times10^{-9}/1.83\times10^{-9}$ and transport holdout nRMSE to $7.96\times10^{-9}/4.97\times10^{-9}$. Sparse clean observations at the seven local training times also supported recovery: pointwise errors were 0.2840%/0.5714%, compared with 0.07968%/0.2682% for interval supervision. Thus sparse sampling alone did not prevent recovery in this fixed-affinity, known-initialization transport problem.

In the single dense realization with 0.5% synthetic log-normal CV, pointwise parameter errors increased to 65.48%/4.175%, versus 3.621%/0.3359% for interval supervision. Corresponding held-out EGLC nRMSE was 1.583 versus 0.04758. This is a reconstruction/learning stress result, not biological model infeasibility. It also depends on the fixed 401-point teacher grid and its resolution of noisy PCHIP derivatives; it does not establish superiority over all pointwise methods, smoothing choices or temporal quadratures. The three sparse noisy realizations gave glucose capacity errors of 0.474-2.161% pointwise and 0.115-1.865% integrated. Improvement was not uniform: for seed 1618, glucose error was 0.8283% pointwise versus 0.9725% integrated. These few realizations do not establish uncertainty intervals or general robustness.

All replays passed the declared state/transport solver-convergence and checked raw-positivity criteria. All input hashes, the biological readiness configuration and the prepared 38-replay energy protocol remained unchanged. Independent verification passed 92 checks, compared nonoracle optimizer solutions with separately computed bounded linear least-squares optima within $1.38\times10^{-7}$ capacity units, reproduced every exported concentration/flux metric, and confirmed scope, noise receipts and raw accepted-state initialization. The full QA suite passed 686 tests. These results verify this benchmark adapter, production teacher builder and executed-rate path, not every historical optimizer or the Phase C ML module.

All 113 concentrations were evaluated, not only transport outputs. Excursion-normalized errors are accompanied by independently recomputed absolute mM and mean-normalized errors because nearly flat pools can inflate excursion nRMSE. For example, RIB varies only from 0.616563 to 0.616618 nominal mM during holdout; the dense-noisy integrated RIB RMSE is 0.004506 mM, although its floor-normalized excursion score is 4.506. Its mean-relative error is approximately 0.73%, illustrating why an excursion score alone is not a biological accuracy criterion. No new kinetic context or initialization was promoted. These historical results motivated the separate resolution and smoothing study below.

### 3.29. Resolved dense pointwise supervision did not require an integral-only replacement

The paired study completed 90 conditional fits and its 32 predeclared full ODE replays. All numerical replay gates passed, and 458 independent archive checks and 714 QA tests passed. The minimum checked concentration was +8.15775e-7 mM. All conditional capacity Jacobians had rank two at frozen affinities; one coarse raw-grid noisy fit reached a bound. Independent bounded analytic estimates differed from optimizer outputs by at most 4.24e-7. Raw aligned order-4/8 capacity variation was at most 1.48e-7, and interval order-8/16 basis difference at most 1.39e-17.

| Teacher/objective | Median glucose capacity error (%) | Maximum glucose capacity error (%) | Median lactate capacity error (%) | Maximum lactate capacity error (%) |
|---|---:|---:|---:|---:|
| Equal-point historical 401 control | 38.72 | 92.66 | 16.16 | 41.35 |
| Raw PCHIP, uniform 6401 temporal quadrature | 0.5923 | 1.145 | 0.3323 | 0.9092 |
| Raw PCHIP, observation-aligned order 8 | 0.2386 | 0.3261 | 0.3039 | 0.8989 |
| Log-GCV, observation-aligned order 8 | 0.5604 | 0.6157 | 0.9140 | 1.087 |
| Raw interval increments | 2.684 | 7.370 | 0.2207 | 0.9365 |

These descriptive parameter errors use five paired synthetic noise seeds, not five independent biological samples. Raw aligned supervision had lower glucose error than raw intervals in all five seeds, but lactate rankings were mixed. Smoothing stabilized grid evaluation without uniformly improving recovery. Clean aligned smoothing introduced glucose/lactate capacity biases of 0.03118%/0.006474%; raw aligned and raw interval clean errors were below 6e-7%. Thus temporal resolution, smoothing bias and learning objective are distinct effects.

A separate posthoc partition diagnostic reproduced the parent's original clean errors of 1.424%/0.1179% on its 689-time observations. Canonicalizing only the two roundoff timestamp pairs before reconstruction, at the same 401-point equal-weight objective, reduced errors to 0.00005416%/0.00004605%. The historical noisy result therefore cannot be interpreted as a pure uniform-grid comparison. All historical artifacts are preserved, while the new methods share a canonical partition and new within-study paired noise draws.

For the three preselected noisy free-ODE replays, median held-out EGLC excursion nRMSE was 56.38% for the historical 401 control, 0.1958% for raw aligned, 0.5128% for smoothed aligned and 3.698% for raw intervals. ELAC medians were 2.476%, 0.03749%, 0.09105% and 0.2402%, respectively. Raw-aligned median absolute RMSE was 0.005187 mM for EGLC and 0.001273 mM for ELAC. Other conditional grid variants did not receive full ODE replays.

Across all 113 pools, maximum mean-normalized holdout error over the three noise seeds was 1.47% for raw aligned, versus 261.2% for the historical control, 25.44% for intervals and 2.11% for smoothing, using the declared 0.001 mM mean-scale floor. GTP and intracellular LAC were among the most sensitive pools. Exported absolute/relative pool and executed-flux metrics were independently recomputed within 6.66e-16. These same-family, fixed-initialization results identify numerical teacher construction as a tractable bottleneck in this dense benchmark, not the cause of the biological energy mismatch. Sparse-schedule resolution/smoothing controls remain necessary before transferring the ranking to Bordbar or revising the experimental objective; no kinetic candidate or numerical threshold was promoted.

### 3.30. Sparse teacher resolution did not reproduce the dense recovery ranking

The seven-time continuation completed all 90 conditional fits and 32 predeclared complete ODE replays. All numerical gates, 477 independent archive checks and 735 QA tests passed. No checked raw accepted or sampled concentration was negative; the minimum was +8.230065e-7 mM. Independent analytic capacities agreed with optimizer outputs within 3.58e-10, with multistart spread below 8.72e-10. Conditional Jacobian rank was two throughout at frozen affinities, and no bound was reached.

| Teacher/objective | Median glucose capacity error (%) | Maximum glucose capacity error (%) | Median lactate capacity error (%) | Maximum lactate capacity error (%) |
|---|---:|---:|---:|---:|
| Equal-point historical 401 control | 1.3815 | 2.1609 | 0.8589 | 1.2474 |
| Raw PCHIP, observation-aligned order 8 | 1.3345 | 2.1169 | 0.8666 | 1.2378 |
| Log-GCV, observation-aligned order 8 | 1.0992 | 1.8888 | 0.8640 | 1.1438 |
| Raw interval increments | 0.9725 | 1.8650 | 0.8641 | 1.2319 |
| Raw interval increments with smoothed kinetic inputs | 0.7097 | 1.5462 | 0.7145 | 1.2023 |

These are five-seed descriptive conditional errors, not confidence intervals. Unlike the dense experiment, temporal quadrature at 401 points was already resolved: moving to 6401 changed capacities by at most 1.13e-6 raw or 8.16e-7 smoothed in relative terms. Order-4/8 aligned capacity variation remained below 3.15e-6; order-8/16 interval basis difference was below 1.18e-9. Sparse reconstruction and noise, rather than coarse teacher-grid aliasing, remained the relevant limitations in this experiment.

The three preselected noisy replays had median held-out EGLC excursion nRMSE of 1.111% historical, 1.097% raw aligned, 0.7814% smoothed aligned and 1.303% raw intervals. ELAC medians were 0.09000%, 0.08823%, 0.08435% and 0.08034%, respectively. Smoothed-aligned EGLC median absolute RMSE was 0.02070 mM; raw-interval ELAC median absolute RMSE was 0.002729 mM. Method ranking was not uniform across seeds or outputs. The five-seed parameter table and three-seed replay medians concern different subsets and must not be equated. Smoothed-input interval fits did not receive full ODE validation in this campaign.

On clean sparse observations, smoothed-aligned glucose error was 0.02561%, versus 0.2621% raw aligned and 0.07968% raw intervals, whereas raw intervals had lower lactate error than either aligned method. Smoothed-input intervals had a clean glucose error of 0.2450%, worse than raw intervals despite their favorable noisy medians. This clean/noisy trade-off requires a separately predeclared full-ODE check before adopting that hypothesis.

Whole-pool replay remained informative: maximum mean-normalized holdout error across the three seeds was 7.97% historical, 7.81% raw aligned, 6.99% smoothed aligned and 6.90% raw intervals, with the declared 0.001 mM mean-scale floor; GTP was most sensitive. All 3680 temporal pool/flux metrics were independently recomputed within 6.66e-16. A reconstruction figure for the first predeclared noise seed also illustrates missing early internal transients. On clean data, the saved truth grid samples GLC down to 0.002697 mM near day 1.525, whereas the sparse J1-J4 PCHIP proxy stays above 1.087361 mM. These are sampled synthetic values, not observed biology or exact continuous extrema. Successful conditional capacity recovery does not validate the reconstructed internal trajectory.

Taken together, dense and sparse experiments do not support a universal pointwise-versus-integral replacement. The present sparse schedule does not share the dense numerical-resolution bottleneck, and neither a favorable teacher fit nor a small transport output error replaces whole-ODE validation. Source/normalization/time/uncertainty contracts and latent-redox support remain required for biological calibration; no parameter or numerical policy was promoted.

### 3.31. Smoothed-input intervals improved noisy glucose prediction but introduced clean bias

All twelve predeclared fixed capacity pairs completed free J1-J46 strict/ultrastrict replay, comprising sixteen new integrations and eight reused verified integrations. No fit was repeated and the ODE received no observed or smoothed concentration inputs. All numerical gates passed; minimum checked raw concentration was +8.231786e-7 mM, with zero stored executed transport-balance closure. Positivity refers to accepted and archived dense samples, not a formal proof for every continuous time. Exact raw accepted initial states were preserved; machine-roundoff differences in BDF dense output were distinguished from initialization changes.

| Held-out quantity | Raw five-seed median error (%) | Smoothed median (%) | Raw maximum (%) | Smoothed maximum (%) | Seeds improved by smoothing /5 |
|---|---:|---:|---:|---:|---:|
| EGLC | 1.3034 | 0.9634 | 2.4828 | 2.0633 | 4 |
| ELAC | 0.08034 | 0.07683 | 0.13416 | 0.15870 | 3 |
| GLC | 1.0719 | 0.7938 | 2.0398 | 1.6958 | 4 |
| LAC | 0.6315 | 0.5145 | 0.8551 | 0.8116 | 2 |
| Executed VEGLC | 0.4845 | 0.3516 | 0.9318 | 0.7717 | 4 |
| Executed VELAC | 0.3177 | 0.2892 | 0.3641 | 0.3287 | 4 |

Concentrations use excursion normalization with a 0.001 mM floor; executed rates use truth RMS with a 1e-6 mM/day floor. Five-seed medians are descriptive and exclude the clean control. Median paired differences and median method errors are retained separately; the difference between two medians is not itself the median paired effect. The EGLC median decreased by approximately 26.1%, but improvement was not uniform across outputs or seeds. For example, LAC's median improved while only two of five individual seeds improved.

The clean control exposed additional reconstruction bias. Held-out EGLC excursion error increased from 0.10752% raw to 0.33133% smoothed, with signed J46 concentration errors of -0.002230 and +0.006878 mM, respectively. Clean ELAC error increased from 0.02465% to 0.03733%. Conversely, clean executed VELAC RMS-normalized error decreased from 0.08550% to 0.05752%. These differing rankings show why rate recovery and concentration prediction cannot substitute for one another.

Executed-balance-derived J22-J46 integral errors also improved in noisy median: glucose transport absolute error decreased from 0.013247 to 0.009597 mM and lactate transport from 0.007513 to 0.006523 mM. Their maxima decreased from 0.025497 to 0.021111 mM and 0.008993 to 0.007963 mM, respectively. These endpoint identities are not independent quadrature checks, and signed rate errors can cancel within an interval; they do not invalidate the observed worst-seed ELAC trajectory regression. Across all 113 pools, the largest noisy mean-normalized holdout error decreased from 6.9034% to 5.7469%, both GTP at seed 31415 with the declared scale floor.

The experiment completes the previously missing predictive test for smoothed-input interval capacities on the sparse synthetic schedule. It supports an optional noise-reduction hypothesis, not an unconditional replacement of raw teachers, production defaults or the biological parameter set. Known synthetic noise amplitude, same-family truth, frozen full initial states and affinities remain important limitations. Experimental transfer still requires source normalization, uncertainty, accuracy limits and supported latent-redox initialization.

### 3.32. Source audit separated preserved inputs from verified biological observations

All 55-by-14 local concentration values were finite and nonnegative, with no missing cells. Five available Git workbook snapshots preserved every concentration, metabolite label and time header. The exact duplicate B13PG/B23PG and P2G/P3G rows were already present in the first import. This confirms reproducibility of the local table, not independent observation of both pools or their publication lineage. The calibration loader and all 19 extracellular observation vectors preserved the workbook numbers without a declared volume conversion.

Workbook XML bound `cellbb` to Feuil1's 44 curve rows, with columns `b_1` through `b_5` and polynomial/log evaluation formulas. Sheet1 contained no formulas or query-table connection. Thus the proposed recovery of `cellbb.txt` is useful for curve-coefficient provenance but cannot alone verify the raw concentration table. Neither scoped workspace filename search nor all-ref Git filename history recovered that file. The original concentration export feeding Sheet1, assay/row dictionary and preparation script remain the priority evidence request.

The [primary 2017 reanalysis](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005424) reports 14 Bordbar observations over 45 days. Local J1-J46 likewise spans 45 elapsed days, which makes a +1 origin hypothesis plausible but unverified. Its candidate source vector ends in days 35, 37, 42 and 45; the irregular local J38 was retained. The publication excluded source day 31 following an extracellular anomaly. A corresponding local J32 exclusion was not adopted, despite a local EGLC rise from 16.640 to 16.950 nominal mM at J29-J32. Resemblance is not sample identity or permission to modify training support.

The [uFBA study's total-bag-volume convention](https://www.nature.com/articles/srep46249) provides a specific normalization lead, not a validated local conversion. Both attempted public supplementary downloads returned HTML with status 200 rather than usable spreadsheets. Response payloads, hashes and access limitations were retained, and no supplemental data were imported. Scientific readiness remained at thirteen unmet checks. All four sealed synthetic archives, frozen kinetics/initial states and current readiness/profile configurations were preserved; no simulation, fit, data transformation or promotion occurred.

### 3.33. Exact nominal J1 and coupled capacity probes did not restore the energy partition

All 38 predeclared conditional integrations completed. All 8474 order-4/8 quadrature checks and 6384 strict/ultrastrict comparisons passed. The minimum checked raw concentration was zero, reflecting retained source zeros; no negative accepted or archived dense values were found. Independent verification passed 6445 checks after visual refinement, including initial-state and parameter-scope preservation, signed consumer factors, executable-kernel samples, energy charge/redox conservation, window budgets and every endpoint/response feature. All 823 QA tests passed. These are numerical checks of the specified exploratory context, not biological validation.

Restoring exact nominal Sheet1 J1 changed B13PG and the two source zeros but did not resolve the energy phenotype. Baseline J4 ATP, ADP and AMP were 0.000751043, 0.0000804467 and 2.593665 nominal mM, versus local values 1.079765, 1.073256 and 0.539208. Total adenylates were 2.594497 versus 2.692228 mM, while energy charge was 0.000304979 versus 0.600392. The nearly preserved total again concealed an incorrect partition. Executed J1-J4 ATP production/consumption were 5.822852/6.755092 mM, giving net -0.932240 mM versus nominal observed +0.146772 mM. ADP lost 1.169321 mM and AMP gained 1.854752 mM, rather than the nominal -0.0961443 and -0.199705 mM changes. These discrepancies were not numerical material sources.

The local signed responses were consistent across both probe sizes. Increasing HK/PFK had negative J4 ATP and ADP responses; a downward investment probe therefore raised both slightly but also raised AMP. Increasing AK capacity lowered ATP/ADP and raised AMP, so its downward probe modestly preserved the partition. Increasing GAPDH/PGK raised ATP and lowered AMP but slightly lowered ADP. At h=0.05 the respective ATP responses were -0.000383685, -0.000747731 and +0.000321226 mM per log capacity. Groups contain tied capacities, so these effects do not separately identify HK versus PFK, forward versus reverse AK, or GAPDH versus PGK control.

Paired mixed responses were nonzero, documenting local nonadditivity. For example, the AK-GAPDH/PGK ATP interaction was -0.000511193 mM per squared log capacity at h=0.05. ATP/ADP/AMP response signs agreed between solvers; maximum strict/ultrastrict relative differences were 0.0273% for single responses and 0.1643% for paired interactions. This concerns these endpoint features, not all near-zero features, statistical uncertainty or physiological control coefficients.

Across all nineteen strict probe points, ATP at J4 ranged from 0.000685896 to 0.000837634 mM, ADP from 0.0000684698 to 0.0000990709 mM, and AMP from 2.592957 to 2.594368 mM. None restored the nominal partition, without implying whole-network infeasibility outside the tested neighborhood. The baseline sampled loss attribution assigned 93.30% of VPGK native/executed reduction to B13PG and 6.70% to ADP over J1-J4; these trapezoid-weighted same-trajectory shares are numerical-limiter bookkeeping, not measured control coefficients or independent quadrature.

The archive retains 2090 nominal endpoint rows, 3800 executed reaction integrals, 2580 single-response rows, 1290 paired-interaction rows and 1935 cross-solver response comparisons, plus full trajectories and signed window budgets. No optimizer, fitted initialization, source transformation, threshold tuning or model promotion followed. The original biological protocol and its thirteen unmet evidence checks remain unchanged; no J1-J10/J1-J46 extension was executed. Initial figure exports and their verification receipts were retained before a legend-only layout refinement.

### 3.34. Pool-definition and published-source audit prepared, but did not execute, latent inference

The preparation reconstructed all 770 nominal local concentration cells and extracted 101 reference concentration entries from Nishino supplement section 5 (PDF pages 34-36), retaining exact labels, page provenance, M values and dimensional-only mM conversions. The table distinguishes free ATP (0.0551 mM) from total ATP (1.91 mM). Its NAD, NADH, NADP and NADPH reference values are 0.0651, 0.000240, 0.0000647 and 0.0653 mM, respectively; the frozen exploratory initialization remains 1 mM for each. These differences identify unsupported assumptions to investigate, not replacements that restore ATP. Several small reference values lie below the provisional 1e-3 mM availability threshold, so an eventual inference must distinguish numerical availability suppression from physiological redox effects.

The current kernel has one ATP state and no explicit ATP free/MgATP/Hb-bound observation operator. Its nominal mM header and legacy equal-concentration transport convention do not establish a cytosolic volume denominator. Both exact duplicate signal pairs remain unchanged. For the 53 retained nominal balance channels after excluding B13PG/P2G as independent channels, the 100-reaction matrix has rank 50 and flux nullity 50. This conditional algebraic result documents internal-flux ambiguity; it neither establishes dynamic latent-state identifiability nor verifies the biological identities of unresolved source pools.

The source inventory separates Nishino's experimental relative trajectories from its model-reference concentrations and from commercial-MAP ATP/2,3-BPG calibration data. [Bordbar 2015](https://pubmed.ncbi.nlm.nih.gov/27136057/) is a cross-sectional personalized-modeling study, not the provenance of a stored-RBC time series. [Yurkovich 2017](https://pmc.ncbi.nlm.nih.gov/articles/PMC5712598/) provides targeted absolute quantitation, but its 2,3-DPG profile is predicted rather than independently measured. The attempted public spreadsheet retrieval returned HTML (status 203), not Excel; its response and access limitation are preserved and no numerical observations were imported. [Tzounakas 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC9513173/) provides same-day treatment/control ratios at days 7, 21 and 42, requiring original longitudinal control data before temporal reconstruction. None of these source leads verifies the local Sheet1 normalization or supplies its missing covariance.

All 863 QA tests passed, including 40 added observation/preparation tests. Source-cell and reference-table reconstruction and unchanged parent/input/output hashes were checked. No ODE integration, latent estimate, kinetic optimization, source conversion or model promotion occurred. The output is a reversible preparation contract with unresolved biological evidence, not a fitted latent-state solution or demonstrated correction of the energy deficit.

### 3.35. Supplied JBC data resolve source access but not latent-redox inference

The supplied workbook contains 47 intracellular, 23 extracellular and 26 assay/physiology channels. These 96 channels are not 96 distinct metabolites. The endo and exo sheets each contain 123 sample rows and the assay sheet 126, giving 11,886 numeric observations. No values are missing or nonfinite and no concentration is negative; 182 extracellular zeros are retained as reported, with censoring status unresolved. The three positional trajectory blocks at 4 C have exact source days 0, 1.0417, 3, 7.0417, 10, 14.0417, 17 and 20.9583. The assay-only 37 C extension to day 14 is preserved rather than extrapolated into metabolomics.

ATP, ADP, AMP, glucose/lactate, 6-phosphogluconate, fructose-1,6-bisphosphate, phosphoenolpyruvate, glutathione and other source concentrations are now available as candidate observations. These data can support future source-specific energy-partition and pathway tests once pool/volume operators are resolved. NAD, NADH, NADP, NADPH, B13PG and the seven latent PPP pools have no direct numerical channels; their initial states cannot be supplied by treating nicotinamide or a predicted 2,3-DPG profile as measured substitutes. No ATP restoration, redox estimate or predictive calibration follows from access alone.

Independent reconstruction checks all 11,886 exported source values and their time/temperature/replicate/label/unit keys; all 900 platform QA tests passed, including 37 targeted ingestion tests. The frozen Bordbar workbook, all 55 nominal J1 entries, unmeasured initial states, kinetic parameters, numerical threshold and previous archives remain unchanged. The earlier unsuccessful public download remains preserved as historical evidence; the newly supplied original files now resolve that access limitation. The thirteen-check historical biological-readiness contract is not rewritten or automatically satisfied. Evidence is archived in `output/jbc_supplements_ingestion_2026_10_06/` with a source-inventory update, candidate model coverage and twelve explicit source conflicts. No ODE or optimization is executed.

### 3.36. Targeted biochemical corrections did not restore the adenylate partition

The opt-in network replaces the carbon-creating cystathionine-to-AKG term with an explicit C4 product and separates methyl/methylene folates without introducing an implicit MTHFR flux. The two finite-acceptor redox chains conserve their cofactor/carrier totals and electron ledgers in separately labeled synthetic tests. OPLAH remains active by default despite its exclusion in earlier GEM curation, because the supplied recent proteome detects the protein; neither source establishes catalytic activity during storage. The historical executable kernel, all 55 measured Bordbar J1 entries, archived kinetics and numerical threshold remain unchanged.

Ten new fixed-context J1-J4 structural integrations and four synthetic redox integrations completed under strict/ultrastrict profiles. All 11,480 budget/quadrature checks and 2,142,136 cellwise convergence comparisons passed; these are numerical checks, not biological replicates. Independent verification passed 2,377 checks; 982 QA tests passed and two source-dependent tests were skipped. The minimum checked concentration was zero and executed material budgets closed numerically. Primary chemistry/source evidence and both the expanded matrix and compartment-specific diagnostic catalogue are archived in `output/biochemical_closure_2026_10_06/`.

Ultrastrict ATP J4 was 0.000754700 mM with C4 correction alone, 0.000751043 mM with methyl-only folate separation, 0.000754701 mM with both, 0.000758857 mM with the combined methylene-only partition, and 0.000776632 mM in the combined OPLAH-off countertest. The verified historical endpoint was 0.000751043 mM and the nominal source target was 1.079765 mM. ADP remained near 8e-5 mM and AMP near 2.59 mM rather than the nominal 1.073256/0.539208 mM. No tested structural case restores the energy partition. New redox rates and MTHFR were inactive in all Bordbar replays, so these results do not assess their biological predictive benefit. Further FLA fitting requires regenerated balance constraints, supported active-pool/kinetic observations and new small-pool/acid-base numerical audits, not promotion of a synthetic acceptor sink.

### 3.37. Distinct volumes repaired the transport contract without restoring ATP

The user-selected cell/supernatant coordinate branch preserves source concentrations and exact historical initialization while introducing explicit phase-volume and rate-reference weights. Three original Yurkovich4 C source-day0 hematocrits supplied separate constant geometry scenarios, not matched Bordbar donor metadata. All14 fixed J1-J4 replays passed13146 integrated budget/quadrature and240191 strict/ultrastrict comparisons; the minimum checked concentration was0 mM. Full QA passed1076 tests, with two source-dependent skips. These numerical checks establish conditional implementation consistency, not biological calibration.

Under the common-coordinate clamped-pH control, nominal ATP J4 was0.0007510432991 mM. Distinct-volume native-transport cases yielded0.0007558684489-0.0007613387033 mM; the tied-conductance reversible GLUT/MCT cases yielded0.0007016819763-0.0007033733348 mM. None approached the nominal unchanged Sheet1 endpoint1.079765 mM. Geometry therefore does not explain the large energy-partition deficit within this frozen, pH-clamped context; this does not exclude supported coupled redox/pH effects or establish whole-network infeasibility.

The reversible law produced net lactate import at equal clamped pH, lowering nominal ELAC J4 to2.6974-2.8156 mM while native distinct-volume cases yielded5.4883-6.0029. This exposes the omitted chemical driving gradient rather than validating an irreversible export or disproving MCT biology. A conditional screen across all six source-sheet pairings derives the positive-export requirement $pH_i-pH_e<\log_{10}(LAC/ELAC)$ under the reduced accessible-coordinate assumption. Source-day0 bounds span-0.732948 to-0.253806; they are not measured or inferred physiological pH values, and unresolved free-pool/volume definitions affect their interpretation. No pairing, pH or carrier constant was selected by predictive agreement. Supported acid/base and accessible-pool observations therefore precede free MCT prediction and further biological fitting.

### 3.38. Accessibility and pH remain inseparable from lactate direction alone

The successor contract reconstructed144 source-sheet pairing records without assigning donor identity,576 accessibility-dependent export bounds,2880 directional counterfactuals and48 original pH-channel cells. Four relative-accessibility values and five pH differences were algebraic probes, not physiological priors or values selected by fit. The equal-mapping source-day0 bounds remained -0.732948 to -0.253806. Direct identities confirmed that direction is unchanged when an accessibility ratio and pH difference preserve $pH_i-pH_e-\log_{10}\rho$. These source-derived constraints consequently do not estimate either quantity independently.

Six saved reversible strict/ultrastrict flux archives supplied54 MCT-only frozen-integral capacity counterfactuals. Signed proton transfer closed on the amount basis and net import acidified cells while alkalinizing the medium. The local-capacity calculations were not re-integrated pH predictions; large synthetic low-extracellular-capacity excursions exceed the local approximation. All7392 source/algebra/archive checks passed. Fourteen local evidence prerequisites remained unresolved, including accessible pools, compatible pHi/pHe, buffer/gas/AE1 and carrier-coordinate contracts. No new ODE replay or optimization ran, so the preceding ATP deficit is unchanged. Contract implementation and numerical closure therefore prepare a future coupled identifiability test rather than establish biological readiness.

### 3.39. Source-channel dependence and coupled synthetic ambiguity preceded recovery

All126 original pH37/pH22 pairs matched the manufacturer candidate equation within double-rounding uncertainty: the maximum residual was0.001027500 pH, below the0.001048750 bound. This is strong compatibility with a calculated pH22 channel, not author-confirmed lineage or a validated4C correction. Intracellular concentration denominator, accessible fractions, analyte recovery, cell-water mapping and original concentration processing remained unresolved. No source value or exact measured initial condition was changed.

Seventy-two synthetic forward integrations completed: four truth integrations, four equivalent-family controls and64 sensitivity perturbations. Truth trajectories passed declared conservation, checked positivity, quadrature and strict/ultrastrict criteria. Ultrastrict integrated export was+0.351333931 and-0.462220077mM on the cell-volume basis for the two constructed contexts. All four unknown-affinity controls preserved concentrations, pHe and flux despite a shifted pHi. Thus pHe alone cannot resolve this particular toy's accessibility/affinity/pHi family. With known affinity, sparse concentration-only training additionally contains only three noninitial independent amount samples for four unknowns; independent pH improved the conditional sensitivity spectrum but did not demonstrate global recovery. These are synthetic design diagnostics, not successful biological calibration. Zero recovery fits and zero biological replays were executed; the preceding ATP deficit and readiness decision remain unchanged.

### 3.40. Conditional clean recovery passed without removing the unknown-affinity ambiguity

All72 clean fits met optimizer, numerical, parameter-recovery and later-time prediction criteria; all24 multistart groups agreed. The campaign used2613 actual objective integrations, at most65 per fit, plus144 strict/ultrastrict full-horizon validation integrations and eight integrations for four equivalent-family controls. Worst relative parameter errors were2.71e-9 for conductance,2.40e-9 for extracellular buffer capacity and1.52e-8 for intracellular accessibility; maximum initial-pHi error was6.96e-9pH. Worst all-coordinate scaled holdout RMSE was1.74e-7 against the frozen0.05 limit. These very small errors arise in noiseless, correctly specified conditional problems and do not estimate experimental precision or noisy-data identifiability.

All72 independently coded scalar DOP853 trajectories agreed with their saved five-state BDF counterparts within the declared numerical tolerances; maximum absolute discrepancy across all coordinates was3.31e-8. Nevertheless, all four simultaneous accessibility/affinity/pHi transformations preserved concentrations, pHe and transport flux. Conditional two-coordinate recovery at known affinity therefore does not establish simultaneous four-coordinate recovery, nor does it contradict the previous sparse four-unknown sensitivity limitation. Noise robustness and biological calibration remain subsequent tasks. No full-RBC replay or kinetic promotion occurred, and the ATP deficit remains unresolved.

### 3.41. Small observation noise exposed stable but inaccurate conditional estimates

The three-seed challenge completed216 fits on six shared noise panels. All216 passed numerical checks,214 terminated successfully and two exhausted the unchanged100-call budget. Parameter accuracy passed78/216, latent holdout prediction102/216 and complete recovery66/216. All72 three-start groups agreed within the prespecified spread limits, although only22 groups met complete recovery for all starts. Optimizer agreement therefore did not establish correct kinetic inference. Thirty-six fits predicted adequately while failing parameter accuracy;12 met parameter limits but failed the original joint latent prediction criterion. With only three seeds per context, these are descriptive design outcomes rather than independent population success-rate estimates.

On sparse concentrations, oracle conductance passed parameter recovery in only one of six panel/context combinations although all six passed prediction. Dense independent synthetic sampling passed both criteria in all six. Joint conductance/buffer recovery passed in none of the six sparse panels for either pH observation plan; dense sampling passed parameter recovery in three of six, while prediction passed in all six. Accessibility/initial-pHi recovery on sparse concentrations or concentrations plus pHe passed in none; adding both pH channels passed parameter accuracy in five of six but complete recovery in only two. Dense both-pH observations passed all six conditional access/pHi cases. These dense observations are additional independent synthetic assays, not interpolation of the original sparse measurements.

Worst relative errors across fitted parameters were0.8282 for conductance,0.5231 for extracellular buffer capacity and1.6667 for accessibility; maximum initial-pHi error was0.5259pH. The216 independently coded scalar DOP853 trajectories agreed with five-state BDF within the original numerical limits, with maximum absolute state discrepancy3.95e-8. All12 unknown-affinity equivalent-family controls remained valid. Thus small numerical error and agreement across optimizer starts did not protect against noisy inferential error. The current heuristic-weighted estimator requires further assessment; these results do not establish impossibility for a correctly specified observation-likelihood estimator. That paired estimator comparison is prospective. No full-RBC prediction, ATP restoration or biological kinetic promotion occurred.

### 3.42. Matched likelihood improved recovery more than extending failed optimizations

At the same primary budget, matched likelihood increased parameter recovery from78 to135 of216 pairs, latent holdout prediction from102 to123, and complete recovery from66 to117. Complete recovery gained54 paired cases and lost three. All216 matched optimizers converged; all-start complete recovery passed39/72 groups versus22/72. Sparse conductance/buffer recovery improved from0/6 to4/6 context/seed panels under either pH observation plan; dense recovery improved from3/6 to6/6. These gains did not remove weak accessibility/pHi inference without independent pHi observations or the unknown-affinity family.

The two previous design-cost failures converged with115 and110 objective calls under the secondary500-call cap, but still failed parameter and prediction criteria. The2000-call stage was unnecessary. Their failures were therefore not remedied by merely allowing more iterations. All216 matched trajectories passed the separately coded scalar DOP853 and arithmetic checks, maximum absolute state discrepancy3.44e-8. The12 equivalent concentration/pHe families retained equal likelihood. These are descriptive conditional synthetic comparisons with three seeds per context, not general biological success rates.

### 3.43. Experimental glucose data produced a conditional candidate, not a whole-network solution

The numerically repaired experimental pilot completed six successful fits with unchanged source observations. With fixed affinities, effective clearance was0.03766315/day; at assumed H0.58 this corresponds to cell-basis conductance0.02727332/day versus seed0.08796559/day. Profiled total residual CV was0.020515, not an independently measured analytical CV. The same conditional model's later EGLC RMSE decreased from11.8116mM for the seed to1.1491mM for this candidate. Predicted J46 EGLC was11.7012 versus nominal12.915. This comparison conditions on measured training GLC and a frozen later input; it is not a full-RBC prediction improvement.

Opening extracellular affinity reduced later nominal RMSE to0.8068mM and predicted J46 EGLC12.3111, but two starts reached the500mM affinity bound and another stopped near325.6 with a similar training objective. The affinity is therefore not established by these fits, and the simpler fixed-affinity candidate was retained for subsequent whole-network testing. Geometry alternatives give different cell-basis conductances for the same effective clearance. Independent checks reconstructed all56 source cells and55 exact J1 values, replayed all six candidates and closed their extracellular transport integrals. This conditional pilot alone did not test a free whole-network candidate or establish ATP restoration, clinical validation or automatic production promotion; the subsequent free-network results are reported below.

### 3.44. Releasing intracellular glucose preserved partial fit gains but exposed network failure

All18 fixed-parameter free-network replays completed the staged J1-J4, J1-J10 and J1-J46 design. All352521 strict/ultrastrict state and reaction-integral comparisons passed, as did38646 daily executed-balance checks and34200 comparisons each for raw and executed quadrature. The minimum over saved accepted, dense and quadrature concentration states was0mM; no checked GLUT substrate extension was used. Both J4 phase-native reference profiles reproduced archived accepted times/states bitwise. The archive verifier passed1914 reconstruction and sampled live-RHS checks; this is not an independent implementation of the full physiological network.

With GLC freely predicted, the learned-GLUT candidate reduced nominal postinitial EGLC RMSE from3.4444 to1.2246mM and GLC RMSE from5.3611 to3.4316mM versus the phase-native reference. However, J46 EGLC was15.3876 versus nominal12.915mM, worse at this endpoint than reference12.5090. Candidate GLC remained6.2041 versus nominal0.8264mM. ATP remained1.6919e-5 versus nominal0.4698mM, ADP1.7061e-6 versus0.1655mM, and AMP1.0631 versus0.2213mM. LAC/ELAC errors slightly worsened. Thus numerical validity and improved extracellular trajectory error did not establish joint metabolic adequacy. The candidate was not promoted.

At the assumed fixed H0.58, source J1-J46 GLC/EGLC increments imply an HK integral of9.2943mM cell basis. The reference executed VEGLC9.2914 and VHK2.7692mM, leaving6.5222mM glucose accumulation. The learned candidate executed VEGLC7.2069 and VHK2.1261mM, leaving5.0808mM accumulation. Native PGK evaluated along the reference trajectory integrated to11.2482mM after J4, but executed PGK integrated to0.08048mM. ADP was its minimum-availability consumer at all saved post-J4 quadrature nodes; it held that role for99.09% of quadrature-weighted time in the candidate. These are trajectory-specific limiter attributions, not counterfactual ATP production without limiting or independently measured HK fluxes. The observation supports joint glucose/adenylate-energy inference rather than another isolated transport fit.

### 3.45. Joint nominal glucose increments were inconsistent with exact fixed-volume flux labels

At H0.58, the original paired glucose observations imply negative HK integrals of-0.08012mM on J1-J4 and-0.15406mM on J29-J32 under the specified two-reaction GLC balance. The first interval requires a constant H no greater than0.395985 for nonnegative HK; the second requires H no less than0.814877. No physical constant-H intersection satisfies all exact nominal interval balances. This does not demonstrate biological impossibility: source normalization, aggregation, observation uncertainty, pool identity and variable geometry remain alternatives. It does demonstrate that these nominal increments should not be imposed as noise-free, independent reaction-flux teachers. Original observations were not corrected or rescaled.

### 3.46. Joint early fitting improved partition but did not sustain ATP in storage

The joint campaign completed six converged fits and1124 valid objective integrations, counting finite-difference perturbations. Five fits converged within250 actual integrations; one required104 additional calls after its250-call primary stop. Selected NLL decreased from40.8233 to14.5418 on seven J4 observations, and from91.3569 to35.6114 on14 J4/J8 observations, compared with the GLUT-only model. The two best starts were effectively tied. The final common total residual CV was1.2233, not measured analytical precision. AK, GAPDH/PGK, PK and PEP phosphatase factors reached their lower search limits; these boundary values do not establish independently identified physiological capacities.

Six original-adapter strict/ultrastrict replays passed117507 state/integral comparisons,12882 executed daily-balance checks and11400 quadrature comparisons each for native and executed rates. Checked concentration minima were0mM. The source-extracted and original trajectories agreed, and2556 archive/source/arithmetic/sampled-RHS checks passed. Numerical acceptance did not establish biochemical validity. All55 measured J1 values, latent initialization, affinities, geometry, diagnostic pH and reaction threshold were unchanged.

The J4-trained candidate raised J4 ATP to0.2802mM versus0.001863 for GLUT-only, but this stage must not be conflated with the final J10-trained parameter set. The latter predicted ATP0.1529 at J4,0.1125 at J8 and2.1290e-5mM at J46, versus nominal1.0798/1.2725/0.4698mM. At J46, EGLC12.9307 nearly matched nominal12.915, while GLC accumulated to7.3650 versus0.8264mM. LAC/ELAC were0.04973/19.9082 versus6.4629/28.3637mM. Executed glucose import8.9861 and HK consumption2.7443mM left6.2417mM intracellular glucose accumulation, rather than the nominal-0.2969mM change. A correct extracellular endpoint therefore did not establish correct substrate utilization. No candidate was promoted.

### 3.47. Broader observed pools and executed budgets exposed compensatory failure

On all13 postinitial source points, joint fitting slightly reduced ATP RMSE0.8626->0.8296mM and improved ADP/AMP errors, but worsened EGLC/GLC/lactate errors versus GLUT-only. Among48 individually reported non-objective source-channel representations, PEP RMSE worsened0.01998->3.18725mM; predicted J46 PEP4.9426 versus nominal0.01120mM made the candidate unacceptable despite early adenylate gains. This regression was already apparent on the training days: J4/J8 PEP RMSE0.02782->1.12390mM. Thus a protected successor can prevent this failure without selecting constants using later observations. These channel representations are not independent assays or aggregate whole-network validation.

Signed executed ATP production increased5.8714->10.8543mM over J1-J46, but consumption increased6.8044->11.7873mM, leaving nearly the same net ATP loss. Positive and negative contributions were integrated before netting, including reaction reversals. Dominant joint net ATP expenditures included NDPK3.1639, HK2.7443, PRPP synthesis1.5935 and ribokinase0.99997mM; OPLAH remained active. After J4, executed PGK0.7233mM remained far below native6.8423mM evaluated along the same trajectory. Its availability reduction was allocated3.3197mM to B13PG and2.7993 to ADP. These are trajectory-specific numerical and stoichiometric attributions, not causal recovery estimates or a no-limiter counterfactual.

The unmeasured frozen RIB initial state was1mM, with sole model balance dRIB/dt=-VRKa. It accounted for0.99990mM ATP expenditure by J4 in the final candidate. This identifies a concrete initial-demand assumption but does not infer ribose concentration or predict the ATP effect of changing it under feedback. The next controlled methodological comparison is joint fitting protected against measured-pool regressions, especially PEP, before further kinetic expansion or a separately declared latent-initialization test. J11-J46 remains exposed internal transfer, not independent validation; the present early-fit failure does not prove global network or longer-window calibration infeasibility.

### 3.48. Component-wise training protection prevented the large PEP failure but not broader regression

The nine-channel protected successor converged from all three starts in208,261 and402 actual objective integrations, including control and finite-difference calls (871 total). The latter two needed the declared secondary restart. Selection used only the lowest valid guard-feasible training NLL, not a late endpoint or necessarily the optimizer terminal point. The winning point came from the control-initialized search but was not the unchanged control. Normalized nine-channel NLL decreased92.3381 to31.8761 on the same18 J4/J8 values; the earlier rejected candidate rescored on these observations gave35.7333. These scores are not directly comparable to its original seven-channel NLL. Close multistart costs do not establish unique biological parameters or global optimality.

Eight protected training RMSEs decreased, including G6P1.402464 to0.207126mM, ATP1.179142 to1.076975mM, ADP0.987604 to0.415911mM and AMP2.012606 to1.255294mM. PEP RMSE0.027823825 to0.027827014mM increased by3.19e-6mM, within the predefined numerical allowance; it was maintained within tolerance, not improved. The active PEP constraint prevented the previous large early accumulation without using future observations. This aggregated two-point guarantee did not imply pointwise improvement: GLC J8 increased from1.12745 to2.10631mM against nominal1.21216mM, while its combined J4/J8 RMSE decreased. Investment and AK factors reached lower bounds0.02 and0.001. Other factors were GLUT0.85279, GAPDH/PGK1.11059, PK0.80782 and PEP phosphatase0.61233; the common total residual CV remained1.22878, not assay precision.

Six original-adapter strict/ultrastrict J4/J10/J46 replays passed117507 convergence comparisons,12882 daily executed-balance checks and11400 quadrature comparisons each for raw and executed rates. Nine early guards and full/source-extracted trajectory parity passed without fallback. Checked concentration minima were0mM, not a proof over every continuous time. Original770 observations,55 measured J1 entries, all latent initial pools and the kinetic box remained unchanged. Independent source/archive/arithmetic/sampled-RHS verification passed4705 checks, with846 additional comparison/hash/arithmetic checks. No biological promotion occurred.

The protected candidate did not restore storage prediction. ATP J4/J8/J46 was0.126445/0.084701/0.000021399mM against nominal1.079765/1.272527/0.469757mM. J46 EGLC17.151448, GLC6.291967 and ELAC19.374754 remained inconsistent with nominal12.915000,0.826365 and28.363716mM. Full-period PEP RMSE0.019981 to0.021531mM worsened modestly, while G6P0.595678 to0.115187 improved. Among46 separately audited source-channel representations,17 had a raw positive training-RMSE change and22 had a raw positive full-period change; these are neither independent assays nor statistical-significance counts. F6P early RMSE0.254513 to0.715042mM and B23PG0.403227 to0.550146mM exposed substantial off-objective regressions already on training days.

Executed ATP positive and negative contributions were7.999860 and8.932831mM, leaving0.932971mM net depletion. Net NDPK, PRPP-synthesis and ribokinase expenditures were3.268288,1.595348 and0.999975mM; OPLAH remained active. Glucose import5.929641 minus HK0.760960mM left5.168681mM intracellular accumulation. Thus nine-channel non-regression protection repaired an objective-selection failure but did not establish whole-panel accuracy or energy feasibility. The next declared analysis is fixed-parameter executed-flux attribution of F6P/B23PG regressions and the active PEP constraint before broadening guards or testing latent initialization. Late observations remain exposed internal evaluation and did not select this campaign's constants.

### 3.49. Executed-flux attribution localized early PFK loss and a later B13PG-limited shunt

F6P regression was established primarily before J4. Executed PFK consumption decreased1.067734 to0.116466mM, producing a+0.951269mM signed contribution difference, whereas PGI input decreased0.170036 to0.028987mM and PPP return via TKL2/TAL decreased0.886328 to0.827370mM. The net F6P difference was+0.751261mM at J4. Thus increased PPP return did not explain this candidate's excess. PFK execution equalled its raw flux on this interval; the early loss was not produced by the numerical limiter. At fixed control states the0.02 investment factor accounted for-1.046380mM raw PFK flux, partly offset by+0.095111mM along the altered state trajectory. This ordered arithmetic is not an isolated causal PFK perturbation. After J4, protected PFK flux exceeded control0.044164 to0.131434mM despite its lower capacity, and protected F6P declined slightly: its persistent excess was largely inherited from the earlier interval.

B23PG had a slightly smaller absolute error at J4 but a larger error at J8. Between those observations, executed DPGM replenishment fell0.574717 to0.065738mM while phosphatase consumption changed only1.968504 to1.985787mM. The net B23PG difference-0.526262mM comprised-0.508979mM less replenishment and-0.017283mM extra consumption. DPGM/phosphatase kinetics were unchanged. GAPDH input was nearly stable, but PGK withdrawal increased0.128753 to0.621674mM. PGK's control loss was allocated91.27% to ADP; protected loss was allocated entirely to B13PG. At J8, model B13PG was0.000129517 versus0.000452839mM control. These trajectories shifted scarcity rather than removing it, and the duplicated source channel did not independently validate B13PG.

DPGM's retained raw-flux fraction fell32.83% to10.42%, but its absolute execution loss decreased1.175998 to0.565276mM. The exact executed change was-0.508979=-1.119700+0.610721mM: the raw substrate-dependent decline was partially offset by the modifier difference. Consequently a greater absolute limiter loss must not be claimed as the cause. Under the implemented law, substrate enters both Michaelis-Menten saturation and min(B13PG/0.001,1), making the low-pool response especially sensitive without justifying a fitted threshold change.

PEP's J4 absolute error improved0.039280 to0.010754mM while J8 error worsened0.002325 to0.037856mM; the maintained two-point RMSE therefore concealed a pointwise regression. A proposed eleven-channel RMSE contract plus pointwise PEP constraints would reject F6P, B23PG and PEP J8 for the present candidate, but was not activated for new fitting. The audit passed312 numerical checks,912 allocation-resolution comparisons and8508 independent hash/arithmetic checks; full software QA passed1337 tests with two existing skips. It reused four archived trajectories and14 sampled fixed-state rate checks, not an independent ODE solver or biological validation. No kinetic or structural correction was promoted. Broader guard implementation precedes another same-coordinate feasibility screen, latent RIB initialization or new kinetic freedom.

### 3.50. Broader protection required numerical restoration and retained only modest biological gains

The eleven-channel SLSQP search recorded764 completed objective integrations:65 and144 for unsuccessful completed starts, and555 for a control-initialized search interrupted after stagnation. One in-flight integration may have been interrupted and was not invented in the count. No fit convergence or new feasible gain was asserted for this attempt. Three additional locally linearized directions decreased cost but failed actual ODE guard checks. These failures did not demonstrate global kinetic infeasibility: the real control was feasible, and linearized admissibility did not guarantee nonlinear replay admissibility.

A separately declared inward feasibility restoration found a valid point in nine objective integrations, reducing the same22-value NLL99.7764 to96.6158 without relaxing any of the13 caps. The minimum-L1 correction was not NLL-optimum convergence. Factors were GLUT0.963034, investment0.395807, AK0.569164, GAPDH/PGK1.003041, PK0.745817 and PEP phosphatase0.933664, inside the unchanged box. Shared total residual CV remained19.7946, evidence of severe aggregate discrepancy rather than measured assay precision. The earlier nine-channel fit rescored on these22 values gave36.0186 but failed F6P/B23PG and PEP J8; its lower NLL was not an admissible solution.

All13 fitting constraints and their original-RHS J10/J46 checks passed. Six strict/ultrastrict replays passed117507 state/integral comparisons,12882 daily executed-balance checks and11400 quadrature comparisons each for raw and executed rates. Checked concentration minima were0mM, not a continuous-time proof. Independent verification passed1152 source/trace/arithmetic/sampled-RHS checks and801 secondary provenance/report/budget checks. All770 observations,55 measured J1 entries, latent pools and biological context were unchanged. Full software QA passed1363 tests with two existing skips. The original interrupted attempt, local checks and restored candidate retained separate archives and integration counts.

Training B23PG RMSE improved0.403227 to0.321445mM, whereas GLC, AMP and F6P errors increased slightly within their frozen engineering allowances. PEP J4/J8 absolute errors were0.0392616/0.00232725mM against control0.0392801/0.00232514: J8 was maintained within tolerance, not strictly improved. ATP J4/J8/J46 remained0.0053358/0.00021184/0.000017252mM against nominal1.079765/1.272527/0.469757. Thus numerical admissibility did not restore energy. J46 GLC6.100110 versus0.826365mM and F6P1.164808 versus0.007026mM remained severe mismatches. Executed ATP production5.775129 and consumption6.708104mM retained approximately0.932975mM net depletion; OPLAH remained active.

Whole-period B23PG, GLC, G6P and PEP errors improved modestly, but EGLC worsened1.224563 to1.358335mM. Among44 audit-only channel representations,28 raw early-RMSE differences were positive, with largest ASP0.002505mM; these are not independent assay counts or significance tests. No whole-panel, external-donor or physiological validation was claimed. The next proposed hypothesis is reversible separation of the imposed HK/PFK capacity pairing under unchanged primitive bounds and the same13 guards, not an executed additional kinetic freedom, a guaranteed ATP rescue or justification to alter measured initialization.

### 3.51. Dissociating HK and PFK improved early fitting but did not restore late energy or glucose handling

All four nested-model starts converged:17/31 actual objective integrations
for paired fits and69/45 for split fits,162 in total plus nine fixed screens.
The eight nonbaseline screens violated at least one guard, but this did not
imply infeasibility of a combined adjustment. Both split starts reached NLLs
within5.6e-6. Best paired NLL96.615785 differed from the true parent96.615834
by less than the registered1e-4 tie threshold; the retained paired reference
therefore remained the parent. Split NLL91.366945 improved the raw best paired
fit by5.248841 and retained reference by5.248889. These were conditional
training gains, not a significance test, global optimum or identifiability result.

Selected HK/PFK capacities were0.16266445/0.64493577mM/day versus parent
1.97903744/1.00908374, with all other constants and initial states unchanged.
All thirteen original early guards and six original strict/ultrastrict
J4/J10/J46 replays passed:117507 convergence comparisons,12882 executed daily
balances and11400 quadrature checks each for raw and executed rates. Checked
concentration minima were0mM. Independent primary/secondary verification
passed1123/1754 checks, including770 original source cells and94 signed
budgets; software QA passed1379 tests with two existing skips. Neither these
checks nor sampled live-RHS parity established physiological validity.

Original-path early G6P/F6P RMSE improved1.373741/0.254520 to
0.202344/0.046837mM, and B23PG0.321445 to0.259481mM. GLC error slightly rose
within the unchanged GLUT-derived numerical cap; no strict zero-regression
claim relative to the restored parent was made. ATP J4/J8 increased from
0.0053358/0.00021184 to0.0210574/0.00030533mM, still far below nominal
1.079765/1.272527. Total residual CV14.2743 remained very large model/data
discrepancy, not measured assay imprecision.

Late glucose handling worsened: J46 EGLC15.596004 to16.825361 and
GLC6.100110 to6.896167mM, versus nominal12.915/0.826365. ATP remained
approximately1.77345e-5mM against nominal0.469757. Executed full-period ATP
production5.775129 to4.976611 and consumption6.708104 to5.909585mM left nearly
unchanged net depletion. Reduced HK expenditure was accompanied by changes
in other sinks and lower production, not sustained ATP restoration. Glucose
import minus HK expenditure increased accumulation4.976823 to5.772880mM.
Sixteen of44 unguarded channel representations had increased raw early RMSE
versus the parent, largest GMP0.028762mM; these were not independent-assay or
significance counts. The dissociated candidate remained opt-in and reversible,
without production promotion. Progressive temporal calibration with explicit
glucose/lactate protection was proposed before opening additional groups;
already exposed later observations would not constitute blind validation.

### 3.52. Objective changes exposed trade-offs and integral certificates identified model-observation conflicts

All eight fits converged in208 actual objective integrations: six matched
J4/J8 fits and two44-value J1-J15 continuations. All J10 selections reached
the HK0.1mM/day search floor, not an identified physiological capacity. On the
same22 values, refitted NLL, normalized mean and minimax had mean working
MSE129.687654/37.494381/68.215816 and worst MSE1016.534072/343.776200/
339.304298. Refitted NLL86.728329 sacrificed F6P. Plain minimax improved AMP
343.776 to339.304 while worsening F6P0.156857 to339.304. Neither scalar NLL
nor naked minimax was supported as deployment criterion. Normalized residuals
retained F6P but did not restore adenylates. All selected fits failed a historical
diagnostic guard and none met all unit working-MSE targets, which were not assay SDs.

Exact nominal balances failed all six LP screens. Eleven-channel working
multipliers0.016542/0.016779/0.023310 at J8/J15/J46 were analytically explained
by nonincreasing GLC+0.724138EGLC under nonnegative HK. Canonical53 multipliers
0.959227/1.661963/2.804155 were explained by constant CIT+0.724138ECIT.
Additional invariants were constant CITR and ARG+0.724138EARG, whereas nominal
trajectories varied. Twenty-one certificates plus feasible primal witnesses
certified all six relaxation minima to maximum gap2.22e-16. These results
depended on the selected matrix and volume conventions; they did not establish
that data were erroneous or kinetics feasible. Missing dynamics, normalization,
binding/pool definitions and cohort effects remained possible explanations.
No artificial sink or reaction deletion was introduced.

Fourteen original strict/ultrastrict integrations passed278617 convergence
comparisons,32770 executed daily balances and29000 quadrature comparisons each
for raw/executed rates; checked minima0mM. Primary2299/secondary1444 checks
preserved770 source cells/55 J1 and reconstructed275 source/comparator rows.
Software QA passed1411 tests with two existing skips. J46 ATP nevertheless
remained1.77479e-5/1.79867e-5mM for normalized/minimax continuation against
nominal0.469757, and GLC6.968671/6.956652 versus0.826365. No biological
calibration, production promotion, global optimum or independent donor validation followed.

Observation operators and manifest validation formed an automation foundation,
not a completed universal platform. Real relative-data fitting, raw time/storage
mapping, covariance/censoring and complete initialization remained future adapters.
Readiness explicitly distinguished numerical success from unmet fitting criteria
and structural conflicts. The next priority became source/GEM-informed coverage
reconciliation and sensitivity-directed adenylate calibration, not repeated HK/PFK searches.

### 3.53. Coverage reconciliation reduced necessary conflicts but local adenylate levers did not restore energy status

Historical53-channel J15/J46 relaxation multipliers1.661963/2.804155 fell to
0.781803/1.216622 with citrate lyase; arginase alone left these maxima unchanged.
Projected ranks were50 historical,51 for either added branch and52 for both.
Forward citrate utilization replaced constant CIT+0.724138ECIT by a
nonincreasing combination. Arginase similarly allowed decreases, not increases,
in ARG+0.724138EARG. No physical constant H in(0,1) could conserve nominal
amounts in8/13 citrate and5/13 arginine intervals. This did not distinguish
missing metabolism from normalization, binding or cohort/pool-definition effects.

The separate signed-ARGSL relaxation reduced multipliers to0.344415/0.479320
without increasing rank52. The maximum analytic lower bound among48 certificates
matched the feasible primal minimum in each of ten LPs to maximum gap8.89e-16. The residual certificate
bottleneck was static CITR. Its nominal variation lay within the selected
engineering bands, whose relationship to assay noise remained unknown; neither
the variation nor protein detection established obligatory NOS activity at4C.
The ARGSL improvement was an optimistic extent-cone result with unconstrained
latent ARGSUC inventory, not a feasible calibrated dynamic pathway.

Original Deep Red workbook checks confirmed ACLY, ARG1, ASL, ASS1 and ANKH
identity and both F/G copy-number representations. ASS1 detection conflicted
with its absence from the pinned GEM, requiring separate curation rather than
an absence claim. Its forward direction consumes CITR and cannot alone explain
the initial CITR increase. Missing NOS3 in this copy-number table was not proof
of biological absence. No new branch was active in any real-data ODE replay.

All101 sensitivity integrations were valid. Nonzero full/half-step derivative
disagreement ranged from0.0000194 to0.0106845. The12x25 log-adenylate Jacobian
had rank12 at relative1e-6, leaving at least13 unresolved local parameter
directions. Forty-five parameter pairs had absolute response cosine>=0.95.
Stronger PRPPASe/shared km_ATP/forward AK effects failed protected-pool admission.
Two less-correlated single levers survived: vmax_VSAM0.2 ->0.1904761905 and
vmax_VPGK40.14432755 ->38.23269291. Mean log-adenylate diagnostic improvements
were0.5385%/0.2229% in fast probes and were reproduced by both original
tolerance profiles. These were small conditional directions, not fitted constants.

Original ultrastrict ATP J15 was8.335252e-5mM at baseline,8.461394e-5 with
VSAM-down and8.319557e-5 with PGK-down, compared with nominal1.0138273mM.
Thus PGK-down slightly worsened terminal ATP despite aggregate improvement.
Reducing VSAM lowered its executed ATP demand by0.00907749mM over J1-J15,
but NDPK/PRPPASe and other responses compensated. Executed ATP production/
consumption changed from4.911014/5.843923mM at baseline to4.921154/5.854061
for VSAM-down and4.901654/5.834563 for PGK-down. Neither lever rescued energy
status or justified globally suppressing ATP production. Eighteen/twenty-seven
of44 nonprotected source channels had higher raw RMSE for VSAM-down/PGK-down,
respectively; these descriptive increases were not significance tests.

Four new original replays passed76338 convergence comparisons,6328 daily
executed balances and5600 each raw/executed quadrature comparisons; checked
minimum concentrations were0mM. Primary3045 and independent report1708 checks
reconstructed165 source/comparator rows,42 signed pool budgets and all ten
certified relaxations. Software QA passed1433 tests with two pre-existing skips.
All770 source cells,55 exact J1 entries and latent pools were unchanged.
The coverage contract and conditional parameter selection advanced, but full
network-observation coherence, joint feasibility and biological calibration
remained unresolved. Activating new coverage branches would require kinetic
and latent-inventory contracts and a new sensitivity analysis on that network.

## 4. Discussion

### 4.1. FLA links observed dynamics to executable kinetics

The main contribution of FLA is not derivative estimation alone. Its contribution is the closed loop from measured concentrations to teacher fluxes, from teacher fluxes to kinetic parameters, and from those parameters back to an unforced ODE that can be audited and challenged. This makes the learned quantity explicit: FLA learns parameters $\theta$ that generate flux trajectories $v(x;\theta)$, rather than learning a direct black-box map from time to concentration.

For extracellular singleton balances, teacher fluxes are transparent and interpretable. EGLC and ELAC directly constrain glucose import and lactate export. For internal pools, identifiability depends on stoichiometric rank, reversibility, and the availability of neighboring measurements. FLA therefore attaches confidence and method metadata to each flux and avoids treating every reconstructed trajectory as equally observed.

### 4.2. Relationship to FBA, dFBA, and MFA

FBA identifies flux states satisfying steady-state mass balance and other constraints, often under an objective function [1]. dFBA introduces time by updating extracellular states around repeated constraint-based solutions [2]. Isotope-based MFA estimates fluxes from labeling patterns and mass balances. FLA instead starts from longitudinal concentration changes and uses them to calibrate a pre-existing kinetic rate law:

\[
\text{FBA: }Sv=0,
\qquad
\text{FLA: }\dot x\approx Sv(x;\theta)+b,
\quad \theta\ \text{learned from}\ x^{\mathrm{exp}}(t)\ \text{and}\ v^T(t).
\]

FLA can therefore use FBA-derived network structure, dFBA predictions, or MFA measurements when available. The current extracellular teachers are net rates and do not replace isotope-resolved fluxes. A future multimodal implementation could incorporate isotope-MFA estimates as higher-confidence teacher channels in Eq. (21).

### 4.3. Local success and global failure are both useful outcomes

The depletion-gated VEGLC law reproduced extracellular glucose substantially better than the baseline. If evaluation had stopped at the optimized target, this would have appeared to solve glucose handling. Whole-panel replay instead revealed extreme intracellular glucose accumulation and lactate collapse. The candidate was consequently useful as a localized transport hypothesis but invalid as a global parameterization.

This distinction is important for metabolic engineering. An intervention predicted to improve one extracellular product or substrate can perturb ATP demand, intermediate pools, or redox balance elsewhere. FLA's promotion gates formalize the requirement that a pathway intervention remain coherent in the full model. Negative results become mechanistic evidence: the VEGLC gate established that transport flexibility was needed, while its downstream failure showed that transport was not sufficient.

### 4.4. Flux audits expose structural hypotheses

The ATP-production screen initially suggested an energy limitation, but native replay showed nearly proportional compensation by ATP-consuming reactions. Reaction-level attribution then localized 90.2% of induced consumption to VHK and VPFK. Exact G6P/F6P closure excluded a simple algebraic omission and directed attention toward kinetic magnitude, allosteric coupling, and PPP directionality.

This sequence illustrates a general FLA diagnostic principle. If a candidate fails, first verify balance closure; if closure holds, compare production and consumption windows; then inspect directionality and kinetic-family assumptions before opening another parameter. Such staged diagnostics reduce compensatory overfitting and create experimentally testable hypotheses. In the present case, the high modeled contribution of VTKL2 and VTAL to F6P input motivates direct evaluation of reversible non-oxidative PPP behavior.

### 4.5. Relevance to metabolic engineering

Metabolic engineering includes computational and modeling approaches for pathway elucidation and manipulation by genetic, media, or environmental means. Within this remit, the strongest use case for FLA is not retrospective curve fitting. It is the design and evaluation of interventions whose effects unfold dynamically.

For RBC storage, candidate interventions include altered glucose availability, pH control, antioxidant supplementation, oxygen management, and storage-solution composition [4,5]. The paired Bardyn control/supplemented data are particularly relevant because they can test whether FLA identifies kinetic changes that explain a media intervention. More generally, FLA could rank enzyme, transporter, or medium targets in microbial and mammalian systems whenever longitudinal metabolomics and an executable kinetic model are available.

The current study remains a methodological proof of concept. To make a strong metabolic-engineering claim, the final article should show that a parameterization learned in one condition predicts a held-out intervention and helps select or explain a successful pathway or medium modification.

### 4.6. Role of machine learning

The machine-learning component is intentionally subordinate to the mechanistic model. Its role is computational: propose an informed initial parameter vector so that a bounded optimizer spends fewer simulations far from plausible regions. The synthetic results show that the feature and artifact contracts work and that the ridge model can recover perturbations generated by the same ODE family. The separate transport benchmarks in Sections 3.28-3.31 test the Phase A/B concentration-to-flux-to-ODE loop, not the ridge warm-start. The dense resolution study shows that a well-resolved pointwise objective can outperform the tested interval objective for glucose recovery, but its ranking did not transfer uniformly to the sparse schedule. Smoothed-input interval supervision subsequently improved five-seed noisy glucose prediction while worsening clean bias and some lactate trajectories. Neither objective or reconstruction is established as universally preferable, and no biological optimization or global kinetic identifiability follows.

Experimental use poses harder problems, including domain shift, incomplete metabolite panels, non-identifiability, and model discrepancy. For this reason, ML predictions are clipped, reoptimized through the mechanistic objective, and subjected to the same safeguards as any other seed. A learned warm-start can accelerate FLA; it cannot validate the ODE or override mass-balance failure.

## 5. Limitations

First, the exact provenance, replicate structure, variance, and preprocessing of the local primary reference table must be reconciled before submission. The read-only source audit established local numeric preservation and localized the external coefficient import, but did not recover the raw concentration export. J1-J46 means 45 elapsed days, compatible with a published reanalysis but not a verified local time origin. The pointwise-identical B13PG/B23PG and P2G/P3G row pairs require source-level verification and are not treated as independent constraints. Without this information, biological uncertainty and inferential statistics cannot be reported adequately.

Second, derivatives amplify measurement noise. PCHIP limits overshoot but is not a statistical smoothing or uncertainty model. Replicate-aware splines, Gaussian processes, or bootstrap resampling should be compared, and teacher uncertainty should enter Eq. (21) directly. The first transport benchmark evaluated pointwise teachers on a fixed 401-point grid and contained two roundoff-only timestamp pairs. The paired resolution study separated partition conditioning, temporal quadrature and smoothing bias, improving dense pointwise recovery without replacing the experimental objective. Its seven-time continuation found that 401 points already resolved the sparse numerical objective, while unobserved early state transients and clean/noisy interpolation trade-offs remained. Neither study establishes an optimal statistical noise model, robustness beyond five synthetic seeds, experimental transfer, or superiority for joint affinity/capacity/initial-state learning. Signed interval differences also share measurement errors with concentrations and derivatives; covariance cannot be replaced by independent objective terms.

Third, extracellular concentration derivatives represent effective net rates under the current compartment convention. Hematocrit, extracellular volume, hemolysis, evaporation, sampling replacement, and unit conversion may alter the quantitative mapping from concentration change to cellular transport.

Fourth, internal flux inference is underdetermined whenever the measured stoichiometric subsystem is rank deficient. Bounded least squares selects a feasible local solution but not necessarily the biological solution. Reversibility, thermodynamic constraints, enzyme abundance, and isotope tracing would improve identifiability.

Fifth, the primary calibration currently demonstrates strong improvement for extracellular glucose but not a globally acceptable 55-metabolite model. The downstream glucose/lactate and upper-glycolysis mismatch must be resolved before the transport candidate can be considered predictive.

Sixth, external validation is incomplete. Bardyn and Michel differ in metabolite coverage, initial conditions, protocols, and likely analytical scale. These differences require dataset-specific observation models and a predeclared transfer protocol.

Seventh, the ML warm-start has only been tested on simulated data generated by the model used for training. It may fail under experimental model discrepancy and should not yet be presented as a validated biological predictor.

Finally, parameter uncertainty, practical identifiability, and equivalence among kinetic families remain to be quantified. Profile likelihoods, repeated optimization, posterior sampling, and prospective perturbations are needed to determine whether retained constants are uniquely supported. Numerical floors, the corrected stoichiometric parser, and API/runner parity remain part of that validity audit. In particular, dataset-specific time origins and string-valued kinetic-family options are not yet consistently represented across platform entry points. A software test suite passing is not evidence of predictive biological validation.

## 6. Conclusions

Flux Learning Analysis provides a structured route from longitudinal metabolite concentrations to dynamic flux constraints and kinetic parameter hypotheses. In the RBC proof of concept, FLA reconstructed 19 extracellular teacher fluxes and identified a glucose transport law that reproduced extracellular depletion over 46 days. Whole-panel safeguards then prevented that local improvement from being mistaken for a valid global model. Native flux replay and exact balance auditing localized the remaining discrepancy to glycolytic investment-phase coupling and non-oxidative PPP behavior rather than to a missing G6P or F6P balance term.

The whole-model audit also identified correctable implementation and provenance risks. SAM synthesis now conserves biochemical moieties without an artificial AMP coproduct, extracellular glutathione degradation is represented by explicit fluxes, and compartment-strict initialization policies are available. These corrections improve interpretability and reproducibility but do not by themselves solve the kinetic mismatch, reinforcing the need to separate network validity, latent-state inference, and parameter calibration.

The resulting framework is deliberately iterative: establish observation and conservation contracts, infer identifiable flux combinations, calibrate a restricted hypothesis, replay the unforced ODE, and promote only transferable candidates. The PPP/shunt constraints have now been regenerated with the corrected matrix, and fixed-kinetic replay has separated numerical repair from the remaining biochemical mismatch. Reaction-consistent limiting is the explicit provisional working reference with strict tolerances, while legacy remains available for historical replay and older defaults are unchanged. Strict/ultrastrict convergence passed at all three tested thresholds, but strong threshold sensitivity and persistent predictive failure preclude interpreting the modifier as validated biology or promoting the kinetic context. Executed B13PG/ATP attribution identified early investment imbalance, ATP compensation accompanied by AK-mediated ADP consumption, a changing PGK limiter and unobserved redox initialization. The completed J1-J4 feasibility contract shows that modest total-adenylate disagreement conceals severely incorrect partitioning and that four historical/current redox initialization combinations do not restore the endpoints. An evidence-backed scientific guard and a predeclared coupled investment/adenylate/GAPDH-PGK sensitivity protocol are now prepared; the latter remains unexecuted. Recovering the exact upstream data, normalization, uncertainty and time origin, and justifying absolute accuracy and pool-compatible redox priors are prerequisites for execution and optimization. A continuity-constrained training experiment is justified only after those checks. Held-out temporal and supplemented-condition predictions remain the decisive evidence for metabolic-engineering utility; neither is established by the current work.

## Data and code availability

The separate synthetic transport benchmark preserves its design, input hashes, generated observations, PCHIP teachers, conditional multistart fits, all raw accepted solver arrays, native/executed transport rates, 113-pool temporal metrics, independent verification and PNG/PDF figures. An incomplete additive-noise preparation is preserved separately and explicitly superseded. Its successful final archive does not supersede the biological readiness contract.

The current implementation, standardized working datasets, configuration files, and machine-readable result artifacts are maintained in the AIRBC project repository. A public archival repository, release tag, software environment, dataset licenses, and persistent identifier will be provided before submission. The local source filenames and generated artifacts used for this draft are listed in the internal reproducibility map below.

## Author contributions

**Conceptualization:** [To be completed]  
**Methodology:** [To be completed]  
**Software:** [To be completed]  
**Validation:** [To be completed]  
**Formal analysis:** [To be completed]  
**Investigation:** [To be completed]  
**Data curation:** [To be completed]  
**Writing - original draft:** [To be completed]  
**Writing - review and editing:** [To be completed]  
**Visualization:** [To be completed]  
**Supervision:** [To be completed]

## Funding

[To be completed]

## Declaration of competing interest

[To be completed]

## Declaration of generative AI and AI-assisted technologies in the writing process

During manuscript preparation, the authors used an AI-assisted coding and writing system to inspect the computational implementation, organize analysis artifacts, and draft text. All scientific claims, numerical results, equations, references, and final wording must be reviewed and approved by the authors, who retain full responsibility for the manuscript.

## Acknowledgements

[To be completed]

## References

1. Orth JD, Thiele I, Palsson BO. What is flux balance analysis? *Nat Biotechnol.* 2010;28:245-248. https://doi.org/10.1038/nbt.1614.
2. Mahadevan R, Edwards JS, Doyle FJ III. Dynamic flux balance analysis of diauxic growth in *Escherichia coli*. *Biophys J.* 2002;83:1331-1340. https://doi.org/10.1016/S0006-3495(02)73903-9.
3. Qi Z, Roback JD, Voit EO. Effects of storage time on glycolysis in donated human blood units. *Metabolites.* 2017;7:12. https://doi.org/10.3390/metabo7020012.
4. D'Alessandro A, Nemkov T, Kelher M, et al. Routine storage of red blood cell units in additive solution-3: a comprehensive investigation of the RBC metabolome. *Transfusion.* 2015;55:1155-1168. https://doi.org/10.1111/trf.12975.
5. D'Alessandro A, Nemkov T, Yoshida T, Bordbar A, Palsson BO, Hansen KC. Citrate metabolism in red blood cells stored in additive solution-3. *Transfusion.* 2017;57:325-336. https://doi.org/10.1111/trf.13892.
6. Bordbar A, Jamshidi N, Palsson BO. iAB-RBC-283: a proteomically derived knowledge-base of erythrocyte metabolism that can be used to simulate its physiological and patho-physiological states. *BMC Syst Biol.* 2011;5:110. https://doi.org/10.1186/1752-0509-5-110.
7. Bordbar A, McCloskey D, Zielinski DC, Sonnenschein N, Jamshidi N, Palsson BO. Personalized whole-cell kinetic models of metabolism for discovery in genomics and pharmacodynamics. *Cell Syst.* 2015;1:283-292. https://doi.org/10.1016/j.cels.2015.10.003.
8. Virtanen P, Gommers R, Oliphant TE, et al. SciPy 1.0: fundamental algorithms for scientific computing in Python. *Nat Methods.* 2020;17:261-272. https://doi.org/10.1038/s41592-019-0686-2.
9. Fritsch FN, Carlson RE. Monotone piecewise cubic interpolation. *SIAM J Numer Anal.* 1980;17:238-246. https://doi.org/10.1137/0717021.
10. Akiba T, Sano S, Yanase T, Ohta T, Koyama M. Optuna: a next-generation hyperparameter optimization framework. In: *Proceedings of the 25th ACM SIGKDD International Conference on Knowledge Discovery and Data Mining*. 2019:2623-2631. https://doi.org/10.1145/3292500.3330701.

## Figure and table plan

### Main figures

**Figure 1. FLA workflow and mathematical contract.** Longitudinal concentrations, PCHIP derivatives, stoichiometric teacher-flux reconstruction, restricted parameter calibration, ODE reinsertion, and whole-panel promotion gates.

**Figure 2. Phase A teacher fluxes.** Experimental EGLC and ELAC concentrations with PCHIP curves and the corresponding VEGLC and VELAC teachers; inset confidence components.

**Figure 3. Local transport calibration.** Baseline and depletion-gated simulations versus EGLC/ELAC observations, with teacher and simulated VEGLC/VELAC fluxes.

**Figure 4. Whole-panel consequence of local calibration.** EGLC improvement contrasted with GLC accumulation and LAC collapse; summary of nRMSE changes across all 55 metabolites.

**Figure 5. Mechanistic diagnosis.** ATP production/consumption attribution and exact VHK-VPGI/VG6PDH-VPFK investment-phase balances across early, middle, and late windows.

**Figure 6. Validation design.** Locked primary training workflow and prospective transfer to Bardyn control, Bardyn supplemented, and Michel datasets. This figure should report results only after the validation protocol is frozen.

### Main tables

**Table 1. Datasets, time points, compartments, and role in the study.**

**Table 2. Teacher-flux balance rules, confidence scores, and identifiability class.**

**Table 3. Calibration hypotheses, opened parameters, safeguards, and decisions.**

**Table 4. Baseline and candidate metrics for EGLC, ELAC, GLC, LAC, ATP, PEP, G6P, and F6P.**

### Supplementary material

- Complete 19-flux Phase A dataset and confidence diagnostics.
- Parameter bounds, seeds, and trial histories for every calibration campaign.
- Full 55-metabolite concentration metrics and trajectories.
- Native flux trajectories and pointwise balance-closure tables.
- Synthetic Phase C feature schema, perturbations, and held-out comparisons.
- Dataset standardization maps and unresolved provenance metadata.

---

## Internal pre-submission worklist (remove from submitted manuscript)

### Scientific blockers

- [ ] Establish and cite the exact primary source of `Data_Bordbar_et_al_exp.xlsx`; document donor number, storage solution, sampling schedule, normalization, and transformations.
- [ ] Resolve the duplicated B13PG/B23PG and P2G/P3G source rows before using them as independent observations or reaction-level teachers.
- [ ] Verify the original Sheet1 concentration export, all sampling days and their model-origin mapping; J1-J46 spans 45 elapsed days and a 42/46 label mismatch alone does not establish extrapolation. Do not repair J38 or exclude J32 without source evidence.
- [ ] Recover replicate-level data or measurement uncertainty; implement uncertainty-aware teacher fluxes and sensitivity to interpolation.
- [ ] Complete the reversible VTKL2/VTAL fixed-parameter diagnostic and decide whether the kinetic family changes before further calibration.
- [ ] Obtain a candidate that passes the full 55-metabolite Bordbar panel, not only EGLC/ELAC.
- [ ] Freeze a validation protocol before fitting any Bardyn or Michel data.
- [ ] Demonstrate prediction of an environmental or media intervention, preferably Bardyn supplementation, to strengthen fit with *Metabolic Engineering*.
- [ ] Extend the completed local SVD/QR identifiability mask with repeated seeds, profile likelihood, posterior analysis, or an equivalent uncertainty method.
- [ ] Audit intracellular/extracellular volume scaling, hematocrit, and time-unit conversion in every transport balance.

### Reporting blockers

- [ ] Complete authors, affiliations, funding, competing interests, and CRediT roles.
- [ ] Verify every bibliographic entry and add primary citations for Bardyn and Michel datasets.
- [ ] Generate publication-quality figures with biological replicates or uncertainty bands where available.
- [ ] Archive code and data with a release tag, environment lockfile, license, and DOI.
- [ ] Move implementation paths and extended configuration details to supplementary methods.
- [ ] Verify the current journal-specific Guide for Authors before final formatting; exact word, figure, and data-statement requirements were not assumed in this draft.

### Internal reproducibility map

| Component | Current project artifact |
|---|---|
| Primary ODE | `src/equadiff_brodbar.py` |
| Parsed stoichiometry | `src/rbc_stoichiometry.py` |
| Opt-in C4, distinct folates and bounded redox mechanisms | `src/rbc_biochemical_extensions.py`; `config/fla_biochemical_closure_diagnostic.json`; `output/biochemical_closure_2026_10_06/` |
| Provisional numerical work profile | `config/fla_working_reference.json`; `src/fla_working_reference.py` |
| Fixed-kinetic convergence and threshold verification | `scripts/verify_fla_working_reference.py`; `output/fla_working_reference_verification_2026_10_05/summary.json` |
| Executed B13PG-ATP attribution | `scripts/audit_b13pg_atp_executed_fluxes.py`; `output/b13pg_atp_executed_audit_2026_10_05/summary.json` |
| Joint adenylate/redox J1-J4 feasibility contract | `scripts/build_adenylate_redox_feasibility.py`; `src/fla_adenylate_redox_contract.py`; `output/adenylate_redox_feasibility_2026_10_05/feasibility_contract.json` |
| Evidence-backed scientific readiness | `config/fla_adenylate_redox_readiness.json`; `src/fla_precalibration_readiness.py`; `output/adenylate_redox_readiness_2026_10_05_v2/readiness_contract.json` |
| Prepared coupled energy sensitivity | `src/fla_coupled_energy_protocol.py`; `scripts/prepare_adenylate_redox_readiness.py`; `output/adenylate_redox_readiness_2026_10_05_v2/coupled_sensitivity_protocol.json` |
| Direct extracellular teachers | `src/extracellular_teacher_flux.py` |
| Synthetic transport recovery benchmark | `config/fla_synthetic_recovery.json`; `src/fla_synthetic_recovery.py`; `scripts/run_fla_synthetic_recovery.py`; `output/fla_synthetic_recovery_2026_10_05_v2/` |
| Paired teacher-grid and smoothing diagnostic | `config/fla_teacher_resolution.json`; `src/fla_teacher_resolution.py`; `scripts/run_fla_teacher_resolution.py`; `scripts/verify_fla_teacher_resolution.py`; `output/fla_teacher_resolution_2026_10_05_v2/` |
| Seven-time sparse teacher continuation | `config/fla_sparse_teacher_resolution.json`; `scripts/run_fla_sparse_teacher_resolution.py`; `scripts/verify_fla_sparse_teacher_resolution.py`; `output/fla_sparse_teacher_resolution_2026_10_05/` |
| Fixed-capacity smoothed-interval free prediction | `config/fla_smoothed_interval_replay.json`; `scripts/run_fla_smoothed_interval_replay.py`; `scripts/verify_fla_smoothed_interval_replay.py`; `output/fla_smoothed_interval_replay_2026_10_05/` |
| Read-only Bordbar source, units and time audit | `config/fla_bordbar_source_audit.json`; `scripts/audit_bordbar_source_units_time.py`; `scripts/verify_bordbar_source_units_time_audit.py`; `output/bordbar_source_units_time_audit_2026_10_06/` |
| Separate conditional energy sensitivity with exact observed J1 | `config/fla_exploratory_energy_sensitivity.json`; `scripts/run_exploratory_energy_sensitivity.py`; `scripts/verify_exploratory_energy_sensitivity.py`; `output/exploratory_energy_sensitivity_J1_J4_2026_10_06/` |
| General local flux inference | `src/flux_inference.py` |
| Calibration objective and optimizer | `src/MM_calibration.py` |
| Fixed ML feature schema | `src/ml_features.py` |
| Phase A/B runner | `scripts/run_extracellular_flux_learning_phase_ab.py` |
| Phase C smoke model | `scripts/run_phase_c_warmstart_smoke.py` |
| Phase C branch comparison | `scripts/run_phase_c_warmstart_compare.py` |
| Phase A/B summary | `Simulations/brodbar/hermes/extracellular_flux_phase_ab/phase_ab_summary.json` |
| Transport-gate summary | `Simulations/brodbar/hermes/transport_gate_eglc_elac_46d_n32_endpoint16/summary.json` |
| Whole-panel transport replay | `output/brodbar_transport_gate_full_panel/manifest.json` |
| ATP sink attribution | `Simulations/brodbar/hermes/atp_consumption_sink_attribution_46d/summary.json` |
| G6P/F6P balance audit | `Simulations/brodbar/hermes/investment_phase_flux_matching_46d/summary.json` |
| Model and FLA state audit | `output/model_fla_state_audit_2026_08_11/model_fla_state_summary.json` |
| Brodbar provenance contract | `output/brodbar_data_provenance_2026_08_11/provenance.json` |
| Transport scaling audit | `output/transport_scaling_audit_2026_08_11/summary.json` |
| Sequential temporal contract | `output/fla_temporal_contract_2026_08_11/summary.json` |
| Local identifiability mask | `output/fla_identifiability_mask_2026_08_11/summary.json` |
| QSS-B13PG DPGM screen | `Simulations/brodbar/hermes/vmax_vdpgm_qss_b13pg_screen_J1_J46/summary.json` |
| DPGM Pareto refinement | `Simulations/brodbar/hermes/vmax_vdpgm_qss_b13pg_pareto_refinement_J1_J46/summary.json` |
| Fixed-3x ATP/DPGM partition attribution | `Simulations/brodbar/hermes/atp_partition_vdpgm_3x_qss_b13pg_J1_J3/summary.json` |
| ATP-required VPGK/VGAPDH reconstruction | `Simulations/brodbar/hermes/atp_teacher_required_vpgk_vgapdh_3x_qss_J1_J3/summary.json` |
| Joint ATP-ADP-AMP and AK audit | `Simulations/brodbar/hermes/joint_adenylate_balance_3x_qss_J1_J3/summary.json` |
| VAPRT suppression and VAMPD1 requirement | `Simulations/brodbar/hermes/vaprt_zero_vampd1_requirement_3x_qss_J1_J3/summary.json` |
| VAMPD1 screen under fixed VAPRT suppression | `Simulations/brodbar/hermes/vmax_vampd1_vaprt_zero_screen_J1_J46/summary.json` |
| IMP and purine-transfer audit | `Simulations/brodbar/hermes/imp_purine_transfer_vampd1_1p1_vaprt_zero_J1_J46/summary.json` |
| Michel transfer diagnostic | `output/michel_best_params_simulation/manifest.json` |
| FLA progress record | `fla_progress_log.md` |
| Current calibration tasks | `tasks/fla_current_tasks.md` |
