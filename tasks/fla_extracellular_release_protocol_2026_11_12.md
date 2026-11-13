# Extracellular-first Vmax-only release, objective `extracellular_first/2` (registered before execution)

Date 2026-11-12. Prepared with file tools only. NOTHING has been executed: no test, ODE or optimizer run.

Version /2 supersedes /1, which was never run: a Glob found no `output/extracellular_release*` directory before this edit. Config: `config/fla_extracellular_release_2026_11_12.json`.

## Unchanged science

The following stay fixed:

- Vmax only: 14 groups / 17 capacities, original boxes, AK/NDPK pairs intact;
- Km, J1, network, transport, H = 0.58, threshold;
- the 84 inherited J4/J8/J11/J15 guards with the historical reference and reserve. The optimizer uses the full reserve; acceptance uses half the reserve, as before.

No guard is excluded or rebased. The historical ATP/ADP J15 objective is reported as UNMET.

## Release utility (equations)

For each extracellular channel c with at least one positive inherited working band b_cd, over dates d ∈ {J4, J8, J11, J15}:

    MSE_c = mean_{d: b_cd > 0} ((x_cd - y_cd) / b_cd)^2
    U     = mean_c 0.5 * [log1p(MSE_c) - log1p(MSE_anchor_c)]
    dU/dθ = mean_c 0.5 * (dMSE_c/dθ) / (1 + MSE_c)

- **Anchor:** the working centre's qualified 2026-11-09 full/strict profile. It is a constant centring term and does not change rankings.
- **The added 1:** an explicit dimensionless utility scale, not an assay variance, uncertainty or fitted parameter. Exact agreement (MSE = 0) is finite and accepted, for candidate and anchor alike. A single near-perfect channel can no longer dominate.
- **Weights:** the same bands, dates and equal channel weights as before.
- **Unscored points and channels:** zero-band points (EINO J4/J8) are reported as absolute errors. Channels with no positive band are listed and governed by their absolute-error guards.
- **Improvement threshold:** U_new < U_fallback − log1p(0.001). This is an absolute change in utility units, not a percentage of RMSE. Fixed before any result.

## Acceptance constraints (search, seed admission and selection)

1. **The 84 reserved guards**, unchanged.
2. **Global worst-channel cap:** every channel's normalized RMSE ≤ the selected fallback's worst channel × (1 + 1e-6), the tolerance only absorbing strict-joint vs full-backend noise; final selection compares the worst channel exactly. This is a GLOBAL cap, dominated by EINO; it is not per-species non-regression.
3. **EGLC and ELAC focus protection against the selected qualified fallback:** for each channel, three metrics must stay at or below `fallback value + allowance`:
   - normalized RMSE;
   - |J15 residual|;
   - |J4→J15 secant-slope error|.

   The allowances come from the inherited element comparison `atol + rtol·max(|a|,|b|)` (atol 1e-5, rtol 0.01), taken at the fallback so they do not depend on the candidate. With δ_d = 1e-5 + 0.01·|x_fallback,d|:

       RMSE allowance  = sqrt(mean_{d: b>0} (δ_d / b_d)^2)
       J15 allowance   = δ_J15
       slope allowance = (δ_J4 + δ_J15) / 11

   They are computed once, written in `protocol.json`, `summary.json` and the release, and never tuned. In search they are smooth constraints (metric² ≤ cap²). They may reduce the number of admissible seeds; that is reported, not relaxed.

## Provenance

- **Units:** `observations.json` stores numeric arrays without a unit field. `unit_status` is therefore `assumed_mM_historical_model_convention`; it becomes `source_recorded_mM` only if the archive records units. It is propagated to the inventory, scores, every exported species row ("mM (assumed…)") and the release.
- **Scale:** the working bands are not assay SDs.
- **Scope:** the comparator applies only to the archived table identified by `observations_sha256` and is not transferable to user datasets.

## Cache qualification

The context fingerprint hashes:

- the design and the observations;
- the TRANSITIVE local import closure of `run_corrected_vmax.py`, found statically by ast over `scripts/` and `src/` (kernel/RHS/transport/positivity/solver/scoring);
- the profile, backend and SciPy version.

Archived rows enter the cache only when the campaign ITSELF recorded hashes for the whole current closure and they all match. The corrected and multistart campaigns recorded the evaluate wrapper and some solver files, but not e.g. `fla_agentic_gem_correction.py` or `reaction_positivity.py`. Their rows are therefore unqualified screening hints, not cache. Source receipts are kept per row (`source_id`).

Matched replays come out of the restoration budget (at most 8 of the 80):

- both fallback vectors (candidate35, working centre), always, as a drift check;
- then the best release-admissible hints, ranked by archived score and used only for ranking.

A fallback replay that differs from its archived strict-joint row beyond `comparison_atol_mM + comparison_rtol·max(|a|,|b|)` stops the campaign with status `blocked_source_drift`, together with a concrete requalification task.

Resume is refused if the code, config or transitive closure hashes have changed.

## Restoration, search, qualification

These steps are unchanged in structure, budgets and bounds:

- **Restoration:** directions from the stored sealed sensitivities with the /2 chain-rule gradient, linear projection, backtracking (each a real replay), then Phase-I with Broyden updates. Seed admission requires the full release admission above (guards, global cap, focus protection) and separation ≥ 0.01.
- **Search:** SLSQP on U with scaled guards, the global cap and the focus constraints; derivative steps 0.006/0.003; stagnation, budget or segment stops.
- **Qualification:** at most 6 candidates × (strict, ultrastrict) full-backend replays with flux audit and paired convergence.
- **Selection:** one vector: the best qualified improvement, otherwise the best qualified fallback, otherwise an explicit blocked status. No curve assembly.

## Activation

The release states `activation_allowed: false`, which is a prohibition. `activation_policy` says that no explicit click overrides it. `activation_permitted()` refuses activation unless the release itself has `activation_allowed: true`, with eligibility identities that match and an explicit action. The verifier asserts this refusal on the produced artifact.

## Budget

- **New ODE:** 240 overall (restoration and matched replays 80, search 160), plus at most 12 qualification integrations. These are ceilings, not targets.
- **Accounting:** failed attempts are counted per group; interrupted folders are kept as orphans.

## Entry points (Codex, in order, after review)

```text
python -m pytest qa/test_fla_extracellular_release.py -q
python scripts/run_extracellular_release.py --out output/extracellular_release_2026_11_12
python scripts/run_extracellular_release.py --out output/extracellular_release_2026_11_12 --resume   # interruption only
python scripts/verify_extracellular_release.py output/extracellular_release_2026_11_12 --receipt output/extracellular_release_verification_2026_11_12
```

## Meaning

The result is one provisional extracellular reference vector (or an audited fallback, or an explicit blocked receipt) for one archived dataset. It is not a validated RBC calibration. ATP/ADP, latent stocks, assumed units, borrowed geometry and the single unknown donor remain open.
