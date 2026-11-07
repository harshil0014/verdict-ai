-- Older deployed clients retain their explicit-analysis behavior until upgraded.
create or replace function verdict_saas.enqueue_evidence_workflow() returns trigger
language plpgsql security invoker set search_path=pg_catalog,verdict_saas as $$
begin
 if coalesce((new.body->>'automatic_investigation')::boolean,false)=false then return new; end if;
 if new.body->'evidence' is distinct from old.body->'evidence'
    and coalesce(new.body->'evidence'->-1->>'origin','') <> 'public_web_automatic' then
  insert into workflows(case_id,owner_id) values(new.id,new.owner_id)
  on conflict(case_id) do update set generation=workflows.generation+1,
   state=case when workflows.state='running' then 'running' else 'queued' end,
   stage=case when workflows.state='running' then workflows.stage else 'queued' end,
   attempts=0, detail='', updated_at=now();
 end if;
 return new;
end $$;
revoke all on function verdict_saas.enqueue_evidence_workflow() from public,anon,authenticated;
