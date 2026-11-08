# Agentic Vmax-only pilot: results and handoff

## What ran

Three real subagents worked in parallel on ATP demand, RBC-GEM projection,
and numerical search. The GEM agent hit its usage limit after writing the
adapter, tests and fixed replay archive; the controller completed its archive
verification. The demand and search agents completed their assignments. See
`manuscript_agentic_fla_addendum.md` for the proposed Methods text. The prior
manuscript and `fla_current_tasks.md` remain byte-preserved as protected inputs
of the structural audit; this report and the progress log provide the handoff.

Demand evidence:4400 signed reaction/window rows and four separate starts.
On the sealed reference, RKa spends0.9974mM ATP before J2 and NDPK transfers
1.9295mM ATP to guanylates over J1-J46. Neither is simply a free loss that
can be removed. The coupled GAPDH/AK diagnostic had74% compensation of its
extra J2-J4 ATP production by additional demand. Raw-rate counterfactuals do
not count as available ATP. The search uses the agent's four proposed starts,
plus the registered supply/partition and downstream combinations.

## Active opt-in structural changes

The executable adapter projects four columns from
[pinned RBC-GEM1.3.0](https://github.com/z-haiman/RBC-GEM/tree/43fd381d9eb8a8a4079629012362312960e1c009):

| Local | GEM | Change in the reduced model |
|---|---|---|
| VH2O2 | CAT | Produce0.5 O2 per H2O2 consumed |
| VXAO | XAO2 | Include O2 consumption |
| VXAO2 | XAO | Include O2 consumption and H2O2 production |
| VEGSSG | GTHOXABCte | Couple export to ATP -> ADP in cell coordinates |

No new binding law, Vmax/Km prior or physiological ATP source. The selected
mode retains OPLAH and does not activate unmeasured branches. Urate coupling,
VCSE C4 identity, folate pools and further structural issues are not solved by
these columns. Exact native rollback remains available. At fixed capacities,
12 structural replays across original and fast backends and4068 daily amount balances were
verified, including the matched native and corrected pair. Corrected O2 J4
0.804762 versus native1.618007mM, but ATP0.023668 versus0.023747mM. This
isolates a structural change without an energetic rescue. RBC-GEM provenance:
[Haiman et al.](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1012109).

## Vmax search and original replay

Both registered128-attempt searches complete;256 actual valid J4 ODE attempts,
four cache hits, no optimizer convergence or global optimum claim. Fourteen
coordinates govern17 positive Vmax values. Every Km, unlisted capacity,
zero-capacity branch, original concentration and latent J1 entry is unchanged.
The six valid Pareto points per network include guard-violating compromises.
No improved point passes all J4 gates. The native anchor is the only
guard-feasible point, without sufficient gain. The two networks select the
same diagnostic Pareto vector (evaluation95) for original J15 replays;
the best early-energy vector (evaluation125) is separate and not replayed.

Best J4 energetic attempt: native ATP0.589133mM, ADP0.891115mM and
AMP1.472879mM; corrected ATP0.588249mM. Approximate97% log-error gain against
the poor reference, with large per-pool guard failures. This is a tested
compromise, not an eligible parameter estimate. All17 tested values for
both roles/network contexts are exported in `diagnostic_Vmax.csv`.

The J15 diagnostic vector gives the following original ultrastrict ATP
concentrations, in nominal mM coordinates:

| Day | Native reference | Native diagnostic | Corrected diagnostic | Nominal |
|---|---:|---:|---:|---:|
| 4 |0.023747|0.248870|0.248438|1.079765|
| 8 |0.000322|0.335044|0.335377|1.272527|
| 11 |0.000145|0.061658|0.061758|1.302859|
| 15 |0.000084|0.003346|0.003348|1.013827|

Mean ATP/ADP/AMP log-error gains are92.61%/92.60% at J4 and76.16%/76.27%
on J8/J11/J15 (native/corrected). In the corrected run, the mean other-pool
working MSE also falls15.78% on J8/J11/J15, but hides clear regressions.
PEP J11 is1.015828mM versus nominal0.069142; G6P and F6P also violate guards.
AMP violates the pointwise guard at J8, J11 and J15. Neither finalist passes.
J8/J11/J15 were not used by the pilot, but had been historically exposed.

## Demand interpretation

In the corrected original replay, J1-J4 ATP production/consumption is
4.355070/5.039624mM versus reference4.657046/5.566291mM. The reduction in early
demand exceeds the reduction in production. J4-J8 net ATP becomes positive
(about+0.087mM); J8-J15 is negative again (1.154125 produced,1.486153 consumed).
The leading signed late uses are PRPPASe0.316383mM and NDPK0.315206mM, followed
by HK/PFK and glutathione-associated costs. The improved early state maintains
more turnover than the depleted reference, so smaller total ATP use over the
full interval is not the right acceptance criterion. No unique causal or
physiological activity inference follows from these integrated differences.

## Verification and decision

83 targeted tests. Four original strict/ultrastrict J1-J15 free integrations
pass;76964 cross-tolerance comparisons. Independent verifier reconstructs
256 fitting scores,6328 daily balances,22400 stored quadrature integrals,
36 live native-rate checkpoints and440 source audit rows. No changed defaults
or promotion. The exploratory ranges and all guard failures remain visible.

Do not extend the J4 winner blindly to J46. A follow-up Vmax-only fit should
use several actual early/mid time points and explicitly separate PEP, G6P,
F6P and AMP protection from mean residual improvement. Compare paired
network hypotheses and use J8-J15 PRPP/guanylate demand as a diagnostic, not
an extra likelihood or a reason to delete reactions. The pilot refutes the
claim that Vmax changes only give tiny early gains, but does not yet identify
a parameter vector that reproduces all relevant trajectories.

Artifacts: `output/agentic_vmax_pilot_2026_11_04/` (traces and original ODE),
`output/agentic_vmax_pilot_decision_2026_11_04/` (tested Vmax and executed
budgets), `output/agentic_vmax_pilot_validation_2026_11_04/` (receipts).
