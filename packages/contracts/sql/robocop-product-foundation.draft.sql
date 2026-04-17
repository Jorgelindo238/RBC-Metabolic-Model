create extension if not exists pgcrypto;

create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    email text unique,
    display_name text,
    organization_name text,
    active_workspace_id uuid,
    active_workspace_updated_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.workspaces (
    id uuid primary key default gen_random_uuid(),
    slug text not null unique,
    name text not null,
    created_by_user_id uuid not null references auth.users(id),
    created_at timestamptz not null default now(),
    archived_at timestamptz
);

create table if not exists public.workspace_memberships (
    workspace_id uuid not null references public.workspaces(id) on delete cascade,
    user_id uuid not null references auth.users(id) on delete cascade,
    membership_role text not null check (membership_role in ('owner', 'admin', 'member')),
    membership_status text not null default 'active' check (membership_status in ('active', 'invited', 'suspended')),
    joined_at timestamptz not null default now(),
    primary key (workspace_id, user_id)
);

create table if not exists public.workspace_subscriptions (
    workspace_id uuid primary key references public.workspaces(id) on delete cascade,
    plan_key text not null default 'research_free',
    subscription_status text not null default 'active' check (subscription_status in ('trialing', 'active', 'past_due', 'canceled')),
    seat_limit integer,
    trial_ends_at timestamptz,
    current_period_ends_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.agent_sessions (
    id uuid primary key default gen_random_uuid(),
    workspace_id uuid not null references public.workspaces(id) on delete cascade,
    created_by_user_id uuid references auth.users(id) on delete set null,
    calibration_run_id text,
    session_kind text not null default 'robocop' check (session_kind in ('robocop', 'analysis', 'triage')),
    session_status text not null default 'open' check (session_status in ('open', 'archived', 'errored')),
    title text,
    metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
    created_at timestamptz not null default now(),
    last_activity_at timestamptz not null default now()
);

create table if not exists public.agent_messages (
    id uuid primary key default gen_random_uuid(),
    session_id uuid not null references public.agent_sessions(id) on delete cascade,
    author_kind text not null check (author_kind in ('user', 'assistant', 'system', 'tool')),
    message_kind text not null default 'message' check (message_kind in ('message', 'tool_call', 'tool_result', 'note')),
    content text not null,
    metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
    created_at timestamptz not null default now()
);

create table if not exists public.external_identities (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    workspace_id uuid references public.workspaces(id) on delete cascade,
    provider text not null,
    provider_user_id text not null,
    provider_chat_id text,
    identity_status text not null default 'linked' check (identity_status in ('linked', 'pending', 'revoked')),
    metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
    linked_at timestamptz not null default now(),
    unique (provider, provider_user_id)
);

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'profiles_active_workspace_id_fkey'
    ) then
        alter table public.profiles
            add constraint profiles_active_workspace_id_fkey
            foreign key (active_workspace_id)
            references public.workspaces(id)
            on delete set null;
    end if;
end
$$;

create index if not exists profiles_email_idx
    on public.profiles (email);

create index if not exists profiles_active_workspace_idx
    on public.profiles (active_workspace_id);

create index if not exists workspaces_created_by_idx
    on public.workspaces (created_by_user_id, created_at desc);

create index if not exists workspace_memberships_user_idx
    on public.workspace_memberships (user_id, membership_status);

create index if not exists agent_sessions_workspace_activity_idx
    on public.agent_sessions (workspace_id, last_activity_at desc);

create index if not exists agent_sessions_run_idx
    on public.agent_sessions (calibration_run_id);

create index if not exists agent_messages_session_created_idx
    on public.agent_messages (session_id, created_at asc);

create index if not exists external_identities_user_idx
    on public.external_identities (user_id, provider);

create or replace function public.handle_new_profile()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.profiles (id, email, display_name)
    values (
        new.id,
        new.email,
        coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name')
    )
    on conflict (id) do update
    set email = excluded.email,
        display_name = coalesce(excluded.display_name, public.profiles.display_name),
        updated_at = now();
    return new;
end;
$$;

drop trigger if exists on_auth_user_created_profile on auth.users;
create trigger on_auth_user_created_profile
    after insert on auth.users
    for each row execute procedure public.handle_new_profile();

alter table public.profiles enable row level security;
alter table public.workspaces enable row level security;
alter table public.workspace_memberships enable row level security;
alter table public.workspace_subscriptions enable row level security;
alter table public.agent_sessions enable row level security;
alter table public.agent_messages enable row level security;
alter table public.external_identities enable row level security;

drop policy if exists "Profiles can read own row" on public.profiles;
create policy "Profiles can read own row"
    on public.profiles
    for select
    to authenticated
    using (id = auth.uid());

drop policy if exists "Profiles can update own row" on public.profiles;
create policy "Profiles can update own row"
    on public.profiles
    for update
    to authenticated
    using (id = auth.uid())
    with check (
        id = auth.uid()
        and (
            active_workspace_id is null
            or exists (
                select 1
                from public.workspace_memberships wm
                where wm.workspace_id = profiles.active_workspace_id
                  and wm.user_id = auth.uid()
                  and wm.membership_status = 'active'
            )
        )
    );

drop policy if exists "Authenticated users can create workspaces" on public.workspaces;
create policy "Authenticated users can create workspaces"
    on public.workspaces
    for insert
    to authenticated
    with check (created_by_user_id = auth.uid());

drop policy if exists "Workspace members can read workspaces" on public.workspaces;
create policy "Workspace members can read workspaces"
    on public.workspaces
    for select
    to authenticated
    using (
        exists (
            select 1
            from public.workspace_memberships wm
            where wm.workspace_id = workspaces.id
              and wm.user_id = auth.uid()
              and wm.membership_status = 'active'
        )
    );

drop policy if exists "Workspace members can read memberships" on public.workspace_memberships;
create policy "Workspace members can read memberships"
    on public.workspace_memberships
    for select
    to authenticated
    using (
        user_id = auth.uid()
        or exists (
            select 1
            from public.workspace_memberships self_wm
            where self_wm.workspace_id = workspace_memberships.workspace_id
              and self_wm.user_id = auth.uid()
              and self_wm.membership_status = 'active'
        )
    );

drop policy if exists "Workspace members can read subscriptions" on public.workspace_subscriptions;
create policy "Workspace members can read subscriptions"
    on public.workspace_subscriptions
    for select
    to authenticated
    using (
        exists (
            select 1
            from public.workspace_memberships wm
            where wm.workspace_id = workspace_subscriptions.workspace_id
              and wm.user_id = auth.uid()
              and wm.membership_status = 'active'
        )
    );

drop policy if exists "Workspace members can read agent sessions" on public.agent_sessions;
create policy "Workspace members can read agent sessions"
    on public.agent_sessions
    for select
    to authenticated
    using (
        exists (
            select 1
            from public.workspace_memberships wm
            where wm.workspace_id = agent_sessions.workspace_id
              and wm.user_id = auth.uid()
              and wm.membership_status = 'active'
        )
    );

drop policy if exists "Workspace members can create agent sessions" on public.agent_sessions;
create policy "Workspace members can create agent sessions"
    on public.agent_sessions
    for insert
    to authenticated
    with check (
        created_by_user_id = auth.uid()
        and exists (
            select 1
            from public.workspace_memberships wm
            where wm.workspace_id = agent_sessions.workspace_id
              and wm.user_id = auth.uid()
              and wm.membership_status = 'active'
        )
    );

drop policy if exists "Workspace members can read agent messages" on public.agent_messages;
create policy "Workspace members can read agent messages"
    on public.agent_messages
    for select
    to authenticated
    using (
        exists (
            select 1
            from public.agent_sessions s
            join public.workspace_memberships wm on wm.workspace_id = s.workspace_id
            where s.id = agent_messages.session_id
              and wm.user_id = auth.uid()
              and wm.membership_status = 'active'
        )
    );

drop policy if exists "Workspace members can create agent messages" on public.agent_messages;
create policy "Workspace members can create agent messages"
    on public.agent_messages
    for insert
    to authenticated
    with check (
        exists (
            select 1
            from public.agent_sessions s
            join public.workspace_memberships wm on wm.workspace_id = s.workspace_id
            where s.id = agent_messages.session_id
              and wm.user_id = auth.uid()
              and wm.membership_status = 'active'
        )
    );

drop policy if exists "Users can manage own external identities" on public.external_identities;
create policy "Users can manage own external identities"
    on public.external_identities
    for all
    to authenticated
    using (user_id = auth.uid())
    with check (user_id = auth.uid());
