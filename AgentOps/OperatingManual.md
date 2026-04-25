# AgentOps Operating Manual

Stable rules for how Codex should work in this repository.

## Core rules

1. Correctness before polish.
2. Inspect before editing.
3. Make the smallest coherent change.
4. Preserve validated behavior.
5. Report what was proven, what was inferred, and what remains untested.

## Execution model

Before changing files:
- inspect the relevant execution path
- identify current behavior
- identify likely root cause
- state the validation path for non-trivial work

While changing files:
- keep edits focused
- avoid speculative rewrites
- do not revert user changes unless explicitly requested
- prefer additive contracts and backwards-compatible responses

Before finishing:
- run the most direct validation available
- update `Tasks.md` if active state changed
- update `Memory.md` only for reusable lessons
- update `Archive.md` only for durable historical milestones

## Validation expectations

Use the most direct evidence for the task:
- TypeScript check for web changes
- production build for deployment-sensitive web changes
- FastAPI route smoke for API changes
- worker endpoint smoke for calibration-worker changes
- `py_compile` for Python entrypoints
- `qa/robocop` for RoBoCop calibration logic
- browser validation for UI behavior
- artifact inspection for scientific runs
- LangSmith trace inspection for tracing work

Done means:
- the issue is addressed
- the relevant validation was performed or explicitly blocked
- obvious regressions were checked
- residual risk is named

## Git rules

- Do not commit or push unless the user asks.
- Do not stage credentials, `.env`, `.vercel`, `.next`, `node_modules`, logs, caches, SQLite runtime files, or generated calibration outputs.
- Keep commits focused.
- Do not rewrite history or amend commits unless explicitly requested.

## Security and auth

- Never expose secrets.
- Do not invent test credentials.
- Treat authentication as a first-class dependency.
- Protected flows require either a user-provided session, safe test credentials, or an explicit bypass approved by the user.

## Frontend/product rules

- Preserve the premium airbc/RoBoCop dark scientific visual direction.
- Prefer route-backed navigation for real product structure.
- Keep Research and Monitoring concepts distinct.
- RoBoCop is the product-facing assistant identity.
- Avoid UI messages that imply a blocker when the app can continue with defaults.

## Backend/scientific rules

- Do not duplicate scientific core logic.
- `src/MM_calibration.py` is the canonical calibration orchestration core.
- `src/equadiff_brodbar.py` is the ODE/scientific model core and should stay protected unless scope is explicitly opened.
- Preserve pure-ODE validation as a promotion gate.
- Keep timeout, crash, partial, and complete states distinct.
- Serialize NumPy/scientific outputs explicitly.

## Calibration worker and production rules

- Vercel web uses `CALIBRATION_API_BASE_URL` and `CALIBRATION_API_SHARED_SECRET`.
- Hetzner worker uses `CALIBRATION_WORKER_SHARED_SECRET`.
- The shared secret value must match across Vercel and worker.
- Worker public endpoints should require the secret except intentionally public health/root checks.
- Production smoke must verify both direct worker health and web proxy behavior.

## RoBoCop messaging

Telegram messaging is outbound-only and non-blocking.

Required env:
- `ROBOCOP_TELEGRAM_ENABLED=true`
- `ROBOCOP_TELEGRAM_BOT_TOKEN=...`
- `ROBOCOP_TELEGRAM_CHAT_ID=...`

Optional env:
- `ROBOCOP_TELEGRAM_MESSAGE_THREAD_ID=...`
- `ROBOCOP_TELEGRAM_API_BASE_URL=https://api.telegram.org`
- `ROBOCOP_TELEGRAM_PARSE_MODE=HTML`
- `ROBOCOP_TELEGRAM_TIMEOUT_SECONDS=10`

Messaging must never fail a scientific run.

## Reporting style

Final reports should include:
- what changed
- files touched
- validation performed
- anything not validated
- next recommended action only when useful
