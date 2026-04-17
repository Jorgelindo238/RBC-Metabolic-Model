# RBC Calibration Autoresearch Program

## Objective
You are optimizing the outer-loop calibration strategy for the RBC metabolic model.
Your job is to improve calibration quality through bounded, eval-driven experiments.
Optimize the configuration around the scientific engine.
Do not rewrite the scientific engine unless the human explicitly opens that scope.

## Primary metric
- Optimize `aggregate_score` from `eval_summary.json`.
- Lower is better.
- A candidate is not acceptable if it improves `aggregate_score` by sacrificing protected monitor metrics or violating the mutation policy.

## Read before every run
- `AGENTS.md`
- `program.md`
- `config/autoresearch_mutation_policy.yaml`
- the selected policy template
- the selected benchmark manifest
- the latest `eval_summary.json` and relevant TSV history for the same manifest

## Authoritative execution surface
- Calibrator: `src/MM_calibration.py`
- Eval harness: `scripts/run_calibration_eval.py`
- Policy templates: `config/*.json`
- Fast benchmark gate: `config/rbc_calibration_benchmarks.json`
- Promotion benchmark gate: `config/rbc_calibration_promotion_benchmarks.json`
- Output root: `Simulations/brodbar/autoresearch/`

## Default mode
- Run in config-only mutation mode.
- Create candidate files under `config/generated/`.
- Treat committed templates in `config/` as read-only inputs.
- Never edit source code, reaction files, experimental data, or benchmark outputs in place.

## Default experiment loop
1. State one hypothesis in one sentence.
2. Choose a single template policy and a single template manifest.
3. Copy them to candidate files under `config/generated/`.
4. Apply only the mutations allowed by `config/autoresearch_mutation_policy.yaml`.
5. Keep the mutation narrow. Prefer one cluster of knobs per run.
6. Run the fixed eval harness:
   `python scripts/run_calibration_eval.py --policy <candidate_policy> --manifest <candidate_manifest>`
7. Read the new `eval_summary.json` in the generated run directory.
8. Compare the new result to the best prior run for the same manifest.
9. Keep the candidate only if it improves benchmark evidence without violating protected metrics or guardrails.
10. Record a concise triage note with the exact configuration and rationale.

## Required reporting after every run
Report all of the following:
- hypothesis
- exact policy path
- exact manifest path
- exact command run
- exact `target_scope`
- exact `param_scope`
- exact `optimization_strategy`
- `aggregate_score`
- `mean_final_loss`
- `mean_improvement_pct`
- `best_case`
- `worst_case`
- `status`
- notable protected metric changes
- recommendation: keep, discard, or queue for promotion

## Protected metrics and scientific guardrails
- Preserve protected monitor metrics when adding or widening scopes.
- Compare before and after using benchmark artifacts, not a single figure.
- Prefer the narrowest parameter scope that tests the hypothesis.
- Avoid opening broad compensator parameters before the core mismatch is understood.
- Report scope changes explicitly whenever `target_scope`, `param_scope`, `parameter_classes`, or `stage_plan` differ from the template.
- Treat a local win that fails the promotion benchmark as non-promotable.

## Keep and discard rules
Keep a candidate only when all of the following are true:
- it respects `config/autoresearch_mutation_policy.yaml`
- it improves `aggregate_score` for the same manifest or produces a clearly better protected-metric profile at equivalent score
- it does not create an obvious regression in ATP, adenylate, extracellular, or other protected monitor behavior
- the result can be explained by the stated hypothesis

Discard a candidate when any of the following are true:
- it edits files or fields outside the mutation policy
- it depends on broad scope expansion without explicit approval
- it wins only on a short horizon while failing the longer-horizon or ATP-guarded cases
- it improves one case while materially worsening the weighted benchmark outcome
- it cannot be justified from the benchmark artifacts

## Promotion rule
- Use the fast benchmark suite for search.
- Use `config/rbc_calibration_promotion_benchmarks.json` only as a promotion gate.
- Do not auto-promote a fast-benchmark winner without running the promotion suite.
- Do not mutate the promotion manifest unless the human explicitly opens that scope.

## Prohibited actions
- Do not edit `src/MM_calibration.py`, `src/equadiff_brodbar.py`, `RBC/Rxn_RBC.txt`, experimental data files, or Streamlit app files in default mode.
- Do not edit prior `results.tsv`, `eval_summary.json`, or `calibration_report.json` files by hand.
- Do not change metric directionality. Lower `aggregate_score` remains better.
- Do not broaden mutation scope after a weak result just to chase a score.
- Do not claim promotion readiness without evidence from the promotion benchmark.

## Preferred search posture
- Start from existing policy templates.
- Mutate one hypothesis at a time.
- Favor reproducible improvements over clever but brittle wins.
- Use ATP-guarded and longer-horizon cases to reject compensatory solutions.
- Treat the scientific core as stable until the human explicitly authorizes deeper mutation.
