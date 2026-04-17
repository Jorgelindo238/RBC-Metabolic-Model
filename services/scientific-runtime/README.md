# Future Scientific Runtime Service Boundary

Reserved for future service shells, workers, or API adapters that invoke the existing Python scientific and orchestration interfaces.

The scientific source of truth remains:

- `src/equadiff_brodbar.py`
- `src/MM_calibration.py`
- `scripts/run_calibration_eval.py`
- `scripts/run_calibration_job.py`

This folder is intentionally outside the JS workspace so future product surfaces can integrate with Python without absorbing scientific authority into the Next.js apps.
