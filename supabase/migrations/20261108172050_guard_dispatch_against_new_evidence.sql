-- Do not dispatch an intent after a new upload or changed investigation.
-- Lock order matches reservation: connection, case, policy, action.
do $$ declare definition text; revised text; begin
 definition:=pg_get_functiondef('public.verdict_agent_api(text,text,jsonb)'::regprocedure);
 revised:=replace(definition,
  'select * into pol from agent_policies where id=act.policy_id for update;',
  'select * into c from cases where id=act.case_id for share;
   if c.revision is distinct from (act.basis->>''case_revision'')::integer
    or coalesce((c.body->>''analysis_stale'')::boolean,false) then return jsonb_build_object(''send'',false); end if;
   select * into pol from agent_policies where id=act.policy_id for update;');
 if revised=definition then raise exception 'Expected dispatch branch missing'; end if;
 execute revised;
end $$;
