-- DRAFT ONLY: future contract-derived persistence schema for public.calibration_runs.
-- This file defines the intended Postgres/Supabase row shape only.
-- It does not add any runtime integration, database writes, or app wiring.
-- Source shape:
-- - packages/contracts/schemas/calibration-runs-row.schema.json
-- - scripts/project_calibration_runs_row.py

create table if not exists public.calibration_runs (
    -- Scalar queryable columns
    run_id text primary key,
    canonical_run_label text,
    run_timestamp text,
    run_timestamp_utc timestamptz,
    registry_recorded_at timestamptz not null,
    status text,
    job_name text,
    hypothesis text,
    job_version integer,
    campaign text,
    workspace_id uuid,
    created_by_user_id uuid references auth.users(id),
    agent_session_id uuid,
    visibility text,
    run_origin text,
    policy_name text,
    policy_path text,
    manifest_name text,
    manifest_path text,
    optimization_strategy text,
    target_scope text,
    param_scope text,
    aggregate_score double precision,
    mean_final_loss double precision,
    mean_improvement_pct double precision,
    best_case text,
    worst_case text,
    case_count integer,
    run_dir text,
    artifact_manifest_path text,

    -- JSON/JSONB metadata columns
    tags jsonb not null default '[]'::jsonb check (jsonb_typeof(tags) = 'array'),
    job_metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(job_metadata) = 'object'),
    parameter_classes jsonb check (parameter_classes is null or jsonb_typeof(parameter_classes) = 'array'),
    target_scopes jsonb not null check (jsonb_typeof(target_scopes) = 'array'),
    param_scopes jsonb not null check (jsonb_typeof(param_scopes) = 'array'),
    trace_context jsonb not null check (jsonb_typeof(trace_context) = 'object'),
    chat_context jsonb not null check (jsonb_typeof(chat_context) = 'object'),

    -- Artifact reference columns
    artifact_refs jsonb not null check (jsonb_typeof(artifact_refs) = 'object')
);

comment on table public.calibration_runs is 'DRAFT ONLY: future contract-derived persistence table for calibration run registry rows projected into queryable scalar columns plus JSONB metadata and artifact references.';

create index if not exists calibration_runs_registry_recorded_at_desc_idx
    on public.calibration_runs (registry_recorded_at desc);

create index if not exists calibration_runs_run_timestamp_utc_desc_idx
    on public.calibration_runs (run_timestamp_utc desc);

create index if not exists calibration_runs_status_recorded_at_idx
    on public.calibration_runs (status, registry_recorded_at desc);

create index if not exists calibration_runs_workspace_recorded_at_idx
    on public.calibration_runs (workspace_id, registry_recorded_at desc);

create index if not exists calibration_runs_creator_recorded_at_idx
    on public.calibration_runs (created_by_user_id, registry_recorded_at desc);

create index if not exists calibration_runs_policy_manifest_recorded_at_idx
    on public.calibration_runs (policy_name, manifest_name, registry_recorded_at desc);

create index if not exists calibration_runs_scope_score_idx
    on public.calibration_runs (target_scope, param_scope, aggregate_score);

create index if not exists calibration_runs_tags_gin_idx
    on public.calibration_runs using gin (tags);

alter table public.calibration_runs enable row level security;

drop policy if exists "Draft workspace-scoped read access to calibration runs" on public.calibration_runs;
create policy "Draft workspace-scoped read access to calibration runs"
    on public.calibration_runs
    for select
    to authenticated
    using (
        visibility = 'public'
        or created_by_user_id = auth.uid()
        or (
            workspace_id is not null
            and exists (
                select 1
                from public.workspace_memberships wm
                where wm.workspace_id = calibration_runs.workspace_id
                  and wm.user_id = auth.uid()
                  and wm.membership_status = 'active'
            )
        )
    );
