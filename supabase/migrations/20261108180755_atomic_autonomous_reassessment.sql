-- Queue the current source payload and its audited stale marker in one commit.
do $$ declare definition text; revised text; begin
 definition:=pg_get_functiondef('public.verdict_agent_api(text,text,jsonb)'::regprocedure);
 revised:=replace(definition,'if p_op in (''status'',''observe'') then',$branch$
 if p_op='reassess' then
  select * into c from cases where id=p_args->>'case_id' for update;
  if not found or c.body->>'mode'<>'paypal_sandbox_saas'
   or c.body->>'automatic_investigation'='false'
   or p_args->'mutation'->>'case_id' is distinct from c.id
   or coalesce((p_args->'mutation'->'body'->>'automatic_workflow_version')::integer,0)<9
   or coalesce(p_args->'mutation'->'body'->>'sandbox_reassessment_digest','') !~ '^[a-f0-9]{64}$'
   or (p_args->'mutation'->'body' - array['revision','updated_at','analysis_stale','automatic_workflow_version','sandbox_reassessment_digest'])
     is distinct from (c.body - array['revision','updated_at','analysis_stale','automatic_workflow_version','sandbox_reassessment_digest'])
   then raise exception 'verdict:invalid_revision'; end if;
  result:=verdict_saas.commit_case(actor,p_args->'mutation',false);
  insert into workflows(case_id,owner_id) values(c.id,actor)
   on conflict(case_id) do update set generation=workflows.generation+1,
    state=case when workflows.state='running' then 'running' else 'queued' end,
    stage=case when workflows.state='running' then workflows.stage else 'queued' end,
    attempts=0,next_attempt_at=null,updated_at=now();
  return result;
 end if;
 if p_op in ('status','observe') then$branch$);
 if revised=definition then raise exception 'Expected observation branch missing'; end if;
 execute revised;
end $$;
