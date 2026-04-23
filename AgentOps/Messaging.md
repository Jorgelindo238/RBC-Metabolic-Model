# RoBoCop Messaging

This file tracks the lightweight outbound messaging seam for long-running RoBoCop orchestration work.

## Current decision

- Use a native Telegram mini-client inside `services/robocop/messaging/`
- Keep the flow unidirectional only
- Do not add inbound Telegram commands
- Do not keep the full local `hermes-agent/` tree for this alerting seam

## Current behavior

`scripts/run_bounded_autosearch.py` can now emit non-blocking Telegram alerts for:

- session start
- each completed iteration
- session completion
- unexpected session failure

If Telegram is not configured, the runner behaves exactly as before.

## Environment variables

The alerting seam is explicitly gated. Nothing is sent unless all required values are present and enabled.

- `ROBOCOP_TELEGRAM_ENABLED=true`
- `ROBOCOP_TELEGRAM_BOT_TOKEN=...`
- `ROBOCOP_TELEGRAM_CHAT_ID=...`

Optional:

- `ROBOCOP_TELEGRAM_MESSAGE_THREAD_ID=...`
- `ROBOCOP_TELEGRAM_API_BASE_URL=https://api.telegram.org`
- `ROBOCOP_TELEGRAM_PARSE_MODE=HTML`
- `ROBOCOP_TELEGRAM_TIMEOUT_SECONDS=10`

## Operational notes

- Messaging must never block or fail the scientific run
- The autosearch runner catches notification errors and only logs them
- Alerts should stay concise and session-oriented rather than streaming every internal node event
- Session summary paths and decision record paths are included so the morning-after review can jump straight to artifacts

## Scope boundary

This seam is only for bounded RoBoCop orchestration alerts right now.

Not included in this phase:

- Telegram command handling
- interactive approvals
- chat-style agent conversations
- replacing LangSmith or the JSON session ledgers
