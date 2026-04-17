---
name: rbc-calibration-campaign
description: Run a bounded RBC calibration campaign, evaluate it with the fixed outer-loop harness, and produce a keep-discard triage recommendation.
version: 1.0.0
metadata:
  hermes:
    tags: [rbc, calibration, autoresearch, benchmarking, optuna]
    category: research
---

# RBC Calibration Campaign

## When to Use
Use this skill when you need to run a calibration campaign in this repository, compare a candidate policy or manifest against the current benchmark baseline, and produce a triage recommendation grounded in benchmark artifacts.

Use it for:
- fast outer-loop strategy screening
- candidate policy comparison
- benchmark triage after a calibration run
- promotion-gate review after a fast-benchmark win

Do not use it to mutate the scientific core by default.
This skill assumes config-only mutation unless the human explicitly opens a deeper scope.

## Required Inputs
- a one-sentence hypothesis
- a policy path
- a manifest path
- optional baseline run directory for comparison
- optional promotion manifest path

## Read First
Before doing anything, read:
- `AGENTS.md`
- `program.md`
- `config/autoresearch_mutation_policy.yaml`
- the selected policy file
- the selected manifest file

## Procedure
1. Validate scope.
   - Confirm the task is inside the mutation policy.
   - Refuse in-place edits to committed templates.
   - Refuse scientific-core edits unless explicitly approved.

2. Extract the run contract.
   - Record the exact `target_scope`, `param_scope`, `optimization_strategy`, `t_max`, `curve_fit_strength`, ATP guard settings, and selected benchmark manifest.

3. Run the evaluation harness.
   - Execute:
     `python scripts/run_calibration_eval.py --policy <policy> --manifest <manifest>`

4. Locate the generated run directory.
   - Read the newest campaign folder under `Simulations/brodbar/autoresearch/`.
   - Open `eval_summary.json`.
   - Read case-level `calibration_report.json` files when the summary shows a regression or outlier.

5. Triage the result.
   - Compare the new run against the best prior result for the same manifest.
   - Focus on `aggregate_score`, `mean_final_loss`, `mean_improvement_pct`, `best_case`, `worst_case`, and protected monitor metrics.
   - Treat a score win with obvious ATP, adenylate, extracellular, or robustness regression as suspect.

6. Recommend an action.
   - `keep` when the benchmark evidence is better and the result respects guardrails.
   - `discard` when the score is worse, the profile is brittle, or the mutation violated policy.
   - `queue for promotion` only after a credible fast-benchmark win.

7. If promotion is requested.
   - Run the promotion benchmark separately.
   - Do not call a candidate promotable without evidence from `config/rbc_calibration_promotion_benchmarks.json`.

## Output Contract
Always return a structured summary with:
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
- protected metric notes
- recommendation
- next best experiment

## Pitfalls
- Do not confuse a local short-horizon win with a robust campaign improvement.
- Do not widen parameter scope just because a narrow hypothesis failed once.
- Do not rely on a single plot when benchmark artifacts disagree.
- Do not mutate promotion criteria and then claim promotion success from the same edited gate.
- Do not edit `results.tsv`, `eval_summary.json`, or `calibration_report.json` by hand.

## Repository-Specific Notes
- `scripts/run_calibration_eval.py` is the fixed outer-loop evaluator.
- `src/MM_calibration.py` is the scientific execution engine.
- `config/rbc_calibration_benchmarks.json` is the default fast search gate.
- `config/rbc_calibration_promotion_benchmarks.json` is the promotion gate.
- Candidate configs should live under `config/generated/`.

## Success Standard
A good run is not just a lower score.
A good run is a lower score that remains scientifically interpretable, respects protected metrics, and is strong enough to justify the next experiment or promotion check.
