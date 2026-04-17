# Agent Editable Calibration Policy

This document defines the current policy for allowing agent-driven source
edits in the calibration layer while keeping the scientific ODE core frozen.

The current scope is intentionally simple:

- agents may edit [`src/MM_calibration.py`](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/MM_calibration.py)
- agents must not edit [`src/equadiff_brodbar.py`](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/equadiff_brodbar.py)
- every accepted patch must be validated against the real Brodbar ODE through
  [`src/main.py`](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/main.py)

This policy is designed to improve experimental curve fit and real pure-ODE
behavior without letting agents rewrite the scientific model itself.

## 1. Purpose

The goal is to let bounded agents improve calibration behavior in places where
the code is orchestration-heavy rather than equation-heavy.

The target benefits are:

- better calibration objective design
- better stage-plan and seam selection
- better diagnostics and reporting
- better fit-first ranking and promotion logic
- better custom-data handling where it does not alter the ODE model

The target non-goals are:

- rewriting the Brodbar ODE
- changing state indexing or stoichiometric meaning
- replacing deterministic model evaluation with conversational logic
- letting agents optimize the score by weakening the science

## 2. Core Principle

The hierarchy remains:

1. improve experimental fit on the intended metabolite families
2. preserve or improve real pure-ODE behavior
3. use penalties and operational heuristics only as guardrails

Agents may edit the calibration orchestrator, but not the scientific truth
source.

## 3. File-Level Boundary

### Editable in the initial policy

- [`src/MM_calibration.py`](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/MM_calibration.py)

### Read-only in the initial policy

- [`src/equadiff_brodbar.py`](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/equadiff_brodbar.py)
- [`src/main.py`](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/main.py), except for narrowly reviewed reporting or export changes
- benchmark datasets and historical scientific artifacts

## 4. Editable Scope Inside `MM_calibration.py`

`MM_calibration.py` is now treated as fully editable by the agent layer.

This is a deliberate shift from the earlier marker-bounded rollout.

The reason for the shift is that the current bottleneck is no longer only local
objective weighting. We need the autonomy layer to be able to:

- change calibration flow structure
- change ranking and acceptance behavior
- change stage sequencing
- change parameter-seam resolution logic
- change diagnostics and decision logic
- change other calibration-orchestrator internals without being blocked by
  line-marker boundaries

What remains frozen is not a zone within `MM_calibration.py`, but the
scientific core outside it.

## 5. Frozen Scope

Even under full autonomy on `MM_calibration.py`, the following remain frozen:

- [`src/equadiff_brodbar.py`](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/equadiff_brodbar.py)
- scientific benchmark datasets
- external ODE state indexing truth
- any source file outside `MM_calibration.py`, unless separately approved

## 6. Patch Safety Rules

Every agent-generated patch must satisfy all of the following:

### Rule 1. Small, explainable changes

The patch must state:

- what scientific problem it targets
- why the chosen calibration zone is the right place
- which metabolites are expected to improve
- which protected metabolites must not regress

### Rule 2. No silent benchmark hacking

The patch must not:

- remove hard targets from evaluation without explanation
- hide penalties rather than reframe them
- change the task so the metric becomes easier without becoming more truthful
- special-case one dataset in a way that breaks general scientific meaning

### Rule 3. No ODE-core edits

The patch must not change:

- [`src/equadiff_brodbar.py`](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/equadiff_brodbar.py)
- state indices
- dynamic equations
- conservation semantics

### Rule 4. Pure ODE remains the promotion gate

A calibration patch is never considered successful from fit metrics alone.

It must also be checked through [`src/main.py`](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/main.py).

## 7. Required Validation After Every Patch

Every agent edit to [`src/MM_calibration.py`](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/MM_calibration.py)
must run this minimum validation bundle.

### A. Static validation

```bat
python -m py_compile src\MM_calibration.py
git diff --check
```

### B. Calibration validation

Run one bounded calibration on the intended seed and stage plan.

The exact command may vary, but it must use:

- explicit seed
- explicit `t_max`
- explicit `curve_fit_strength`
- explicit protected floors if the patch touches energetic behavior

### C. Real ODE validation

Run:

```bat
python src\main.py --model brodbar --load-params <candidate_best_params.json>
```

### D. Required comparison set

The patch must compare seed vs candidate on:

- `ATP`
- `ADP`
- `AMP`
- `IMP`
- `EGLC`
- `ELAC`
- `PYR`
- `PEP`
- `LAC`

The comparison must include:

- calibration-fit deltas
- pure-ODE trajectory deltas
- explicit notes on any new collapse, plateau, or distortion

## 8. Promotion Rules For Agent Patches

An agent patch may be classified only as:

- `promote`
- `informative`
- `discard`

### `promote`

Allowed only if all are true:

- fit improved meaningfully in the intended target family
- protected metabolites did not regress materially
- pure ODE did not introduce a new collapse or severe distortion
- the improvement is not only a context or reporting artifact

### `informative`

Use when:

- the patch clarifies a tradeoff
- or opens a new basin but is not safe to adopt
- or improves one critical family while causing a visible protected regression

### `discard`

Use when:

- the patch reproduces the seed
- the patch worsens the fit-first objective
- the patch worsens the pure ODE
- or the patch only improves by weakening scientific discipline

## 9. Agent Operating Mode

The initial editing mode should be:

### Mode: `CALIBRATION_ORCHESTRATOR_FULL_FILE_WRITE`

Capabilities:

- read the repo
- edit all of [`src/MM_calibration.py`](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/MM_calibration.py)
- run calibration
- run pure-ODE validation
- write decision artifacts

Restrictions:

- cannot edit [`src/equadiff_brodbar.py`](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/equadiff_brodbar.py)
- cannot edit scientific benchmark datasets
- cannot auto-promote a patch without the validation bundle

## 10. Current Implementation Scope

The current rollout now allows full-file edits for:

1. fit-vs-penalty hierarchy
2. target routing and scope resolution
3. stage-plan generation
4. candidate ranking and decision reporting
5. solver-bridge and evaluation flow inside `MM_calibration.py`
6. parameter and seam resolution logic inside `MM_calibration.py`
7. data-provenance handling inside `MM_calibration.py`

The current rollout still does not allow edits for:

1. [`src/equadiff_brodbar.py`](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/equadiff_brodbar.py)
2. external scientific datasets
3. other source files unless separately approved

## 11. Good First Patch Examples

Examples that should be allowed:

- restoring experimental fit quality as the primary objective when a penalty term became dominant
- improving extracellular target routing for custom datasets
- clarifying stage-plan construction so ATP/ADP and extracellular seams are not mixed carelessly
- improving reporting so a candidate with good fit but bad pure ODE is clearly marked `informative` or `discard`

Examples that should not be allowed in the first rollout:

- changing any ODE equation in [`src/equadiff_brodbar.py`](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/equadiff_brodbar.py)
- changing metabolite indices
- changing what a Vmax or Km parameter biologically means
- quietly rewriting data-loading logic to make a benchmark easier

## 12. Review Checklist

Before accepting an agent-generated patch to
[`src/MM_calibration.py`](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/MM_calibration.py),
reviewers should ask:

1. Did the patch stay inside the allowed zones?
2. Did it preserve fit-first scientific intent?
3. Did it avoid hidden benchmark hacking?
4. Did it run the real ODE through [`src/main.py`](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/main.py)?
5. Did `ATP`, `ADP`, `EGLC`, and `ELAC` stay at least non-regressive?
6. Is the result truly `promote`, or only `informative`?

## 13. Initial Policy Conclusion

Yes, agents can be allowed to edit
[`src/MM_calibration.py`](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/MM_calibration.py)
before they are ever allowed to touch
[`src/equadiff_brodbar.py`](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/equadiff_brodbar.py).

That is the right first step because it expands autonomy in the orchestration
layer while preserving the scientific model as the frozen truth source.

The key condition is simple:

agent edits must remain bounded, explainable, and promotion-gated by the real
ODE.

## 14. First Enforcement Layer

The first implementation layer now exists and should be treated as mandatory
for any agent-generated source edit attempt.

### Full-file editable mode

[`src/MM_calibration.py`](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/MM_calibration.py)
is now treated as fully editable by the agent validation layer.

The earlier marker-bounded rollout is preserved only as historical scaffolding;
it is no longer the enforcement mechanism.

### Frozen-file enforcement

[`src/equadiff_brodbar.py`](C:/Users/Jorgelindo/Desktop/Mario_RBC_up/src/equadiff_brodbar.py)
is now explicitly rejected by the first enforcement layer.

### Hermes validation tool

The Hermes calibration toolset now includes:

- `calibration_validate_agent_edit`
- `calibration_apply_agent_edit`

This validator checks:

- the edited file path
- the current editable zones
- the before/after changed line spans
- whether the proposed edit touches any locked source lines

The guarded apply tool enforces that validation on the write path itself:

- it reads the live file
- validates the proposed before/after change
- writes the file only if validation passes
- leaves the source untouched otherwise

The next bounded loop is now also available:

- `calibration_execute_patch_proposal`

This loop:

- takes `proposedText`
- runs the editable-zone gate
- runs `py_compile`
- launches scientific validation only after the patch is safely applied
- keeps the patch only for allowed decisions
- reverts the patch automatically otherwise

The enforcement layer is intentionally simple:

- it permits any edit inside `MM_calibration.py`
- it rejects frozen-file edits immediately
- it still routes every live patch through compile + scientific validation
