# Prepared-run integrity and explicit effective parameters

Executed by Codex, 2026-11-12. No agents, optimization or new integration.

## Delivered

- `src/fla_effective_parameters.py`: explicit caller-requested resolution of
  numeric/string parameter defaults from the existing kernel AST. No kernel
  import, eval or simulation during resolution. Resolves dependent fallbacks,
  rejects unknown keys/nonfinite numbers/teacher kinetics, and retains all
  supplied values unchanged. A manifest records each origin, default expression,
  source lines and source hashes. Hardcoded equation constants remain pinned
  by source, not newly exposed as fitted parameters. Inactive branches are
  included; inclusion does not imply activity or identifiability.
- `src/fla_user_engine_v2.py`: opt-in successor using the preserved v1 execution
  path. Its prepared description is immutable canonical JSON, with detached
  property reads and a fingerprint covering the full input contracts, time
  origin, initial-state provenance, layout, geometry, kinetics, numerical
  settings, effective-parameter manifest and engine sources. Validation rebuilds
  the preparation checks and rejects malformed or stale descriptions. Missing
  explicit parameters are refused, never filled automatically in preparation.
- Factory arguments and the RHS's internal parameter/kinetic copies are checked
  before solver execution and after return. Corruption returns a contract
  violation, not an admissible candidate. This checks boundary mutations, not
  arbitrary malicious callback behavior or cryptographic authenticity.
- `scripts/audit_effective_parameters.py`: fixed-state parity audit against the
  sealed working centre, both joint/full backends, both archived profiles and
  J1/J4/J8/J11/J15. No ODE integration.
- `qa/test_fla_user_engine_v2.py`: 36 contract and mutation tests.

The original `fla_user_engine.py`, historical runner/verifier, kernel and
scientific parameter files were not edited. Existing sealed evidence remains
intact. No API or frontend wiring or production default change.

## Executed evidence

Archive: `output/effective_parameters_2026_11_12/` contains the effective
parameter manifest, parity receipt and checksums. Input source manifest
verified before and after the audit; output checksums subsequently verified.

118 historical supplied entries -> 283 explicit entries, including 165
previously implicit defaults. Supplied constants unchanged. Twenty fixed-state
checkpoints pass exact equality for raw rates, executed rates, availability
factors and derivatives, across the joint and full backends separately.

Targeted regression command:

```text
python -m pytest qa/test_fla_user_engine_v2.py qa/test_fla_user_engine.py qa/test_user_engine_qualification_verifier.py qa/robocop/test_vmax_only_contract.py qa/test_user_data_contract.py qa/test_calibration_preflight_api.py qa/robocop/test_strategy_orchestrator.py qa/test_auto_param_scope.py -q
```

Result: 319 passed in 16.20 s. `git diff --check` passed. Full repository tests
and browser tests were not run. The existing Python 3.14/Pydantic-v1 warning
appeared without a test failure. No commit or push.

## Scope and next gate

This establishes input integrity and fixed-state equivalence of explicit
defaults, NOT integration equivalence for v2 or biological calibration.
ATP deficit, latent initial-state provenance, adenylate observation definitions,
borrowed hematocrit and unknown donor remain unresolved. Both v2 qualification
and public engine compatibility remain closed; relative observations blocked.

Next bounded execution: a successor recorded solver supporting the declared
first-sample date, with accepted/dense/quadrature evidence and no integration
before t0. Test it with injected systems, then qualify fixed-parameter v2 replays
including a non-J1 origin. Keep absolute storage time for time-dependent rates;
do not reset kinetic time merely because observation starts later. A restart
from an archived state is a numerical benchmark, not a new measured J1 state.
Only then consider connecting this path to Calibration/Monitoring; no increase
in Vmax-search budget is justified by these software results alone.
