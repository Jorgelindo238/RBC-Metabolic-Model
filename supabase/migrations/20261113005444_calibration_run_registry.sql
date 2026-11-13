-- Approved registry on rbc-metabolic-model; no scientific archives are imported.
-- Workspace sharing stays disabled until the workspace foundation is qualified.
create table public.calibration_runs (
    run_id text primary key,
    canonical_run_label text,
    run_timestamp text,
    run_timestamp_utc timestamptz,
    registry_recorded_at timestamptz not null,
    status text,
    benchmark_status text,
    completion_status text,
    job_name text,
    hypothesis text,
    job_version integer,
    campaign text,
    workspace_id uuid,
    created_by_user_id uuid references auth.users(id),
    agent_session_id uuid,
    visibility text default 'private',
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
    time_aware_score double precision,
    case_count integer,
    completed_cases integer,
    total_cases integer,
    elapsed_seconds double precision,
    time_budget_seconds double precision,
    case_time_budget_seconds double precision,
    timeout_policy text,
    coverage_ratio double precision,
    coverage_weight_ratio double precision,
    timed_out boolean,
    crashed boolean,
    stop_reason text,
    run_dir text,
    artifact_manifest_path text,
    tags jsonb not null default '[]'::jsonb check (jsonb_typeof(tags) = 'array'),
    job_metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(job_metadata) = 'object'),
    parameter_classes jsonb check (parameter_classes is null or jsonb_typeof(parameter_classes) = 'array'),
    target_scopes jsonb not null check (jsonb_typeof(target_scopes) = 'array'),
    param_scopes jsonb not null check (jsonb_typeof(param_scopes) = 'array'),
    trace_context jsonb not null check (jsonb_typeof(trace_context) = 'object'),
    chat_context jsonb not null check (jsonb_typeof(chat_context) = 'object'),
    artifact_refs jsonb not null check (jsonb_typeof(artifact_refs) = 'object')
);

comment on table public.calibration_runs is
    'Calibration registry read model. Completion is not biological validation or activation. No browser writes or workspace sharing.';

create index calibration_runs_run_timestamp_utc_desc_idx
    on public.calibration_runs (run_timestamp_utc desc);
create index calibration_runs_creator_recorded_at_idx
    on public.calibration_runs (created_by_user_id, registry_recorded_at desc);
create index calibration_runs_workspace_recorded_at_idx
    on public.calibration_runs (workspace_id, registry_recorded_at desc);

alter table public.calibration_runs enable row level security;
revoke all on public.calibration_runs from public, anon, authenticated;
grant select on public.calibration_runs to anon, authenticated;
grant all on public.calibration_runs to service_role;

create policy "Read explicitly public calibration runs"
    on public.calibration_runs for select to anon, authenticated
    using (visibility = 'public');
create policy "Read own calibration runs"
    on public.calibration_runs for select to authenticated
    using (created_by_user_id = (select auth.uid()));

notify pgrst, 'reload schema';
