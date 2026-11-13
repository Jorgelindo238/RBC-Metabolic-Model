-- Transaction-only fixtures: no accounts are created and every row is rolled back.
begin;
do $$ begin
    if (select count(*) from auth.users) < 2 then
        raise exception 'RLS verification needs two existing accounts; none will be created';
    end if;
end $$;

do $$ begin
    perform set_config('test.registry_owner', (select id::text from auth.users order by id limit 1), true);
    perform set_config('test.registry_other', (select id::text from auth.users order by id offset 1 limit 1), true);
end $$;
insert into public.calibration_runs (
    run_id, registry_recorded_at, created_by_user_id, visibility, workspace_id,
    target_scopes, param_scopes, trace_context, chat_context, artifact_refs
) values
    ('__qa_registry_private__', now(), current_setting('test.registry_owner')::uuid, 'private', null, '[]', '[]', '{}', '{}', '{}'),
    ('__qa_registry_public__', now(), null, 'public', null, '[]', '[]', '{}', '{}', '{}'),
    ('__qa_registry_workspace__', now(), current_setting('test.registry_other')::uuid, 'workspace', gen_random_uuid(), '[]', '[]', '{}', '{}', '{}');
insert into public.calibration_runs (
    run_id, registry_recorded_at, created_by_user_id,
    target_scopes, param_scopes, trace_context, chat_context, artifact_refs
) values ('__qa_registry_default__', now(), current_setting('test.registry_owner')::uuid, '[]', '[]', '{}', '{}', '{}');
do $$ begin
    if (select visibility from public.calibration_runs where run_id = '__qa_registry_default__') <> 'private' then
        raise exception 'Default visibility is not private';
    end if;
end $$;

set local role anon;
do $$ begin
    if (select count(*) from public.calibration_runs where run_id like '__qa_registry_%') <> 1 then
        raise exception 'Anonymous access is not restricted to public rows';
    end if;
    if has_table_privilege('anon', 'public.calibration_runs', 'INSERT')
       or has_table_privilege('anon', 'public.calibration_runs', 'UPDATE')
       or has_table_privilege('anon', 'public.calibration_runs', 'DELETE')
       or has_table_privilege('anon', 'public.calibration_runs', 'TRUNCATE') then
        raise exception 'Anonymous role has write privileges';
    end if;
end $$;
reset role;

do $$ begin
    perform set_config('request.jwt.claims', json_build_object('sub', current_setting('test.registry_owner'), 'role', 'authenticated')::text, true);
end $$;
set local role authenticated;
do $$ begin
    if (select count(*) from public.calibration_runs where run_id like '__qa_registry_%') <> 3 then
        raise exception 'Owner must see own private row and public row, not another workspace row';
    end if;
    if has_table_privilege('authenticated', 'public.calibration_runs', 'INSERT')
       or has_table_privilege('authenticated', 'public.calibration_runs', 'UPDATE')
       or has_table_privilege('authenticated', 'public.calibration_runs', 'DELETE')
       or has_table_privilege('authenticated', 'public.calibration_runs', 'TRUNCATE') then
        raise exception 'Authenticated browser role has write privileges';
    end if;
end $$;
reset role;

do $$ begin
    perform set_config('request.jwt.claims', json_build_object('sub', current_setting('test.registry_other'), 'role', 'authenticated')::text, true);
end $$;
set local role authenticated;
do $$ begin
    if (select count(*) from public.calibration_runs where run_id like '__qa_registry_%') <> 2
       or exists (select 1 from public.calibration_runs where run_id = '__qa_registry_private__') then
        raise exception 'Cross-owner isolation failed';
    end if;
end $$;
reset role;
rollback;
