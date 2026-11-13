# Calibration registry

Reference project confirmed by the user on 2026-11-12:
`rbc-metabolic-model` (`hniqmghepbygphbswwvx`), API
`https://hniqmghepbygphbswwvx.supabase.co`.

Migration `20261113005444_calibration_run_registry.sql` is applied to that
project, with the same version/name in its remote migration history. It is a
successor to the unchanged draft under `packages/contracts/sql/` and includes
the lifecycle fields currently selected by the web application.

## Access contract

- RLS enabled; visibility defaults to private.
- Anonymous: read only explicitly public records.
- Authenticated: read explicitly public records and own records.
- No INSERT, UPDATE, DELETE or TRUNCATE privileges for browser roles.
- Service-role write privileges stay server-only; no service key was retrieved
  or added to the web application. A registry writer is not connected yet.
- Workspace sharing is not enabled. Workspace/profile foundation tables are
  absent; the server preserves personal authenticated scope instead of
  downgrading signed-in users to anonymous reads.

No scientific archives, reference profiles or synthetic campaigns were imported.
An empty registry is expected. A finished record would not imply biological
validation or automatic activation.

## Local configuration

`apps/web/.env.local` uses the project URL and its enabled public anon key.
The file is ignored by Git. Other environment settings are unchanged. Do not
print keys, commit this file or add a service-role key to a public variable.

On user authorization, Vercel project `web` (`prj_02TQUhtl5pW5EfALI9MsGNFSRiqp`,
root `apps/web`) was aligned on 2026-11-12 Toronto / 2026-11-13 01:23 UTC.
`NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` now match this
reference project in development, preview and production. All six values were
read back and compared without printing the key. Per-environment Auth health
and registry requests return HTTP200, with zero visible campaigns. The eight
other variables, variable IDs, target scopes and types are unchanged.

No deployment was triggered. Existing deployments retain their old values;
the corrected pair applies to new deployments only. Production/browser access
with the corrected configuration remains unverified until an authorized
deployment and end-to-end acceptance. No service-role key was retrieved.

## Verification

Run `tests/calibration_registry_access.sql` via an authorized SQL connection.
It checks anon/owner/cross-owner reads, private-by-default visibility and no
browser writes, using existing accounts and transaction-only test rows. All
fixtures are rolled back; no new accounts are created. It requires two accounts.
This tests database roles, not browser sign-in or session refresh.

Executed on 2026-11-12 (Toronto; migration timestamp is UTC 2026-11-13):
42 Node tests, TypeScript and six strict live-registry desktop/mobile scenarios
pass. Real Auth health and registry REST reads return HTTP200. SQL RLS tests
pass; subsequent count confirms zero persisted runs and zero test fixtures.
Browser console checks pass without the old Supabase failure exemption being
used. Screenshots are outside Git in the system temporary directory under
`airbc-calibration-monitoring/`. No authenticated browser-login flow, populated
registry/worker write, full repository suite or production deployment is verified.

Local regression commands:

```powershell
node --test apps/web/lib/server-run-access.test.mjs apps/web/lib/calibration-journey.test.mjs apps/web/lib/calibration-lifecycle.test.mjs
$env:BASE_URL='http://127.0.0.1:3100'
$env:REQUIRE_LIVE_REGISTRY='1'
node apps/web/e2e/calibration-monitoring.scenarios.mjs
```

The strict live-registry flag rejects the previously tolerated unavailable
state. No new ODE or calibration is launched by those browser scenarios.

## Existing security debt

The pre-change advisor reports `user_activity_summary` as a security-definer
view, nine existing security-definer functions callable by anon/authenticated,
and disabled leaked-password protection. These were not introduced or changed
by this migration. They need a separate review before production acceptance.
Post-change advisor findings have the same counts as before the migration.
Remediation references:

- [Security-definer view](https://supabase.com/docs/guides/database/database-linter?lint=0010_security_definer_view)
- [Anonymous execution of security-definer functions](https://supabase.com/docs/guides/database/database-linter?lint=0028_anon_security_definer_function_executable)
- [Authenticated execution of security-definer functions](https://supabase.com/docs/guides/database/database-linter?lint=0029_authenticated_security_definer_function_executable)
- [Leaked-password protection](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection)
