# QA Suite

Unit tests that should live alongside the repo (the top-level `tests/` path is
reserved for local-only data fixtures and is gitignored).

## Running

```
python -m pytest qa -q
```

## Layout

- `qa/robocop/` — tests for the RoBoCop / autoresearch Python services,
  including dataset-aware calibration planner and programmatic curve triage.
