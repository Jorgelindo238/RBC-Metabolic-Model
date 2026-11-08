# FLA latent-pool inference protocol: preparation only

## Scope and rollback

This protocol prepares, but does not execute, inference of unmeasured initial pools at fixed kinetics. The reference remains the exact 55 nominal Sheet1 J1 concentrations in `src/Data_Bordbar_et_al_exp.xlsx`, the frozen exploratory context and strict/ultrastrict `reaction_consistent` profile. All 59 other initial entries, including pHi, remain unchanged during preparation. No historical XLS initialization, optimizer, source scaling, artificial ATP source, observation reset, teacher forcing, threshold fitting or model promotion. The isolated configuration/helper is not imported by the production calibration or API; rollback is simply continued use of the existing reference. Prior archives are immutable.

## 1. Resolve the observation contract

For each metabolite/source preserve its identity, exact day, compartment, denominator, analytical assay, free/total/recovered definition, donor pairing, preprocessing and uncertainty. Nominal mM are not proof of cytosolic mM. Known Hct alone is insufficient without matching cell-water/extracellular volume definitions. No generic volume multiplier is applied.

The exact duplicate B13PG/B23PG and P2G/P3G rows are preserved at J1 but cannot supply independent likelihood channels. Exclude B13PG/P2G as independent channels in the diagnostic; do not assume the remaining row is a uniquely identified biological pool. An eventual summed-pool observation requires upstream assay evidence, not arbitrary splitting. ATP/ADP/AMP remain observed states, not latent optimization variables. The current ATP state is phenomenological; adding a binding model or assigning it to ATP total/free would be a separately validated model change.

Nishino supplement section 5 gives initial/steady-state model reference concentrations in M, not measured donor anchors at MAP storage day 1-5. Convert units by 1000 only for the inventory, not into local observations. Different donors, MAP/SAGM, temperature, pH, extraction and bound forms require explicit transfer assumptions. Values below the availability threshold must be checked against numerical suppression; changing the threshold to improve a fit is forbidden.

## 2. Observation models

Absolute observations: y_abs = H_source(x(t)) + error. H_source specifies pool sums/bound forms and volume normalization; identity is only a provisional nominal diagnostic when the assay mapping is unknown.

Temporal relative signals with linear, stable response and resolved sample normalization: log R_i(t) - log R_i(t0) = log H_i(x(t)) - log H_i(x(t0)) + error. Do not include the zero reference residual as an independent observation; shared reference noise correlates all ratios. Censored/nonpositive signals require a separately specified detection-limit likelihood, not epsilon replacement.

Optional anchored estimate: C_hat_i(t) = C_anchor_i(t0) * R_i(t)/R_i(t0). One anchor per metabolite with exact matching day/pool/volume definition. Propagate joint uncertainty, including covariance, of log(anchor), log(signal), log(reference); vector [1,1,-1]. These are anchored estimates, never new absolute measurements. An external-cohort anchor is a prior/nuisance scale, not a same-donor calibration.

Same-day treatment/control fold changes: log FC_i(t) = log H_i(x_treated(t)) - log H_i(x_control(t)) + error. Both same-day trajectories are required. The Tzounakas day 7/21/42 figures cannot be transformed into a temporal trajectory from one initial absolute anchor. Z-scores, log-transformed and total-signal-normalized tables require their inverse transform/normalizers before any anchored conversion.

## 3. Integrated FLA and dependency

At constant, compatible volume: x(t_b)-x(t_a) = S * integral(v_executed dt). For variable volume use amounts and explicit dilution instead. Teachers derived from y are not independent measurements: either use raw-observation likelihood as primary or a joint covariance including observations and derived interval teachers; never count both as independent evidence. Internal fluxes not uniquely constrained by measured balances remain model-derived latent quantities. The algebraic nullspace is not the dynamic latent-state identifiability test.

Evaluate reaction rates actually executed with availability factors. Preserve signed reversible contributions and complete ATP/ADP/AMP, purine, B13PG and redox budgets. Native rates on the same trajectory are diagnostic counterfactuals, not executed fluxes.

## 4. First latent block, only after evidence and separate execution authorization

Parameterize initial NAD(H) as positive T_NAD and fraction f_NADH in [0,1]: NAD=T_NAD*(1-f), NADH=T_NAD*f. Likewise T_NADP/f_NADPH. Four initial variables; no measured J1 entries change. Other unmeasured pools and pHi are fixed. The implemented network conserves each redox pair total; impose only conservation identities verified for that network. Adenylate total is not fixed because purine transfers alter it.

Nishino points may inform a context-qualified prior later; they do not supply variances, bounds or proof of biological validity. Supported bounds, covariance and absolute error limits remain null in the configuration. Pi and Mg are absent as explicit states: they cannot be inferred by simply adding an initial value. Additional PPP/GA3P/PRPP pools are deferred blocks, opened only when justified by sensitivity and evidence. B13PG/B23PG are not opened in this block.

## 5. Identifiability before biological estimation

First separately authorize a synthetic benchmark: known latent truth, unchanged executable ODE/kinetics, actual sampling schedule and observation operators. Start with clean observations, then explicitly declared synthetic noise. Independently perturb four latent coordinates and calculate whitened trajectory/interval sensitivities from paired strict/ultrastrict free replays. Report singular values, observable combinations and parameter scaling. Numerical rank thresholds are diagnostic choices, not statistical confidence. Compare finite-difference step sizes and solver precision, especially near limiter transitions.

Verify recovery with multiple initial guesses and held-out observations. Synthetic truth/uncertainty do not replace biological evidence. If individual variables are not identifiable, report constrained combinations or prediction intervals; do not present a unique value. Evidence of a prior-dominated solution must remain explicit.

## 6. Future estimation and uncertainty

After contracts are supported, use a constrained maximum-a-posteriori estimate of initial latent variables conditional on fixed kinetics, then profile/ensemble analysis. A later Bayesian posterior is optional; it cannot remove structural nonidentifiability. Each cohort retains its own initial state and observation scales; kinetic sharing across MAP/SAGM/temperatures is a separately tested assumption. Do not invent numerical likelihood weights or prior widths to enable fitting.

The primary diagnostic window is J1-J4. Hold J8 and subsequent real samples out of any future J1-J4 fit; a J1-J8/J46 predictive replay requires separate authorization. No fabricated J2/J3 observations or averaged J2-J5 pseudo-baseline. Prefer interpolation supported by the actual sample vector when an exact anchor day is missing, with propagated uncertainty.

## 7. Acceptance criteria and decision

Require positive raw accepted and dense concentrations, exact executed stoichiometric closure, converged signed reaction integrals/quadrature and strict/ultrastrict predictions. Assess numerical-limiter participation separately from physiological mechanisms. Require measured-pool prediction limits justified before fitting, joint ATP/ADP/AMP agreement and energy charge, conserved redox totals and measured EGLC/ELAC/GLC/LAC/G6P/PEP where available. Never select a point using ATP alone. Nonidentifiable latent intervals and all prior/context limitations accompany any result.

If plausible latent states cannot recover the observations, retain the failure and inspect observation mapping or network/kinetic structure rather than expanding unconstrained latent pools. Every source, preparation, fit and replay receives its own immutable hash-based receipt. This preparation closes no historical biological-readiness blocker by itself.
