-- One bounded upgrade for previously failed, already-authorized address lookups.
-- No evidence changes here; a compatible worker performs normal audited writes.
-- This operation is internal to the existing service-only, invoker-rights RPC.
do $migration$ declare definition text; revised text; begin
 definition:=pg_get_functiondef('public.verdict_workflow_api(text,text,jsonb)'::regprocedure);
 revised:=replace(definition,' if p_op=''queue_recovery'' then',$branch$
 if p_op='queue_location_upgrade' then
  with eligible as (
   select c0.id from cases c0 join workflows w0 on w0.case_id=c0.id
   left join preferences p0 on p0.owner_id=c0.owner_id
   where w0.state in ('completed','partial','failed')
    and coalesce((c0.body->>'automatic_investigation')::boolean,false)
    and coalesce((c0.body->'delivery_location'->>'version')::integer,0)=1
    and c0.body->'delivery_location'->>'authorization_mode'='address'
    and case when coalesce(c0.body->'location_authorization'->>'mode','account')='account'
      then coalesce(p0.mode,'off') else c0.body->'location_authorization'->>'mode' end='address'
    and coalesce((w0.progress->>'geocoding_scheduled_version')::integer,0)<2
    and exists(select 1 from jsonb_array_elements(coalesce(c0.body->'delivery_location'->'mentions','[]'::jsonb)) m
      where m->>'role' in ('intended','reported_delivery') and m->'geocode'->>'status' in ('no_compatible_result','ambiguous'))
   order by w0.updated_at limit 5 for update of c0,w0 skip locked
  )
  update workflows set state='queued',stage='queued',generation=generation+1,attempts=0,next_attempt_at=null,
   progress=progress||jsonb_build_object('required_worker_version',6,'geocoding_scheduled_version',2),
   detail='Checking alternative map names for a previously unresolved authorized address.',updated_at=now()
   where case_id in (select id from eligible);
  get diagnostics queued=row_count;
  return jsonb_build_object('queued',queued);
 end if;
 if p_op='queue_recovery' then$branch$);
 if revised=definition then raise exception 'Expected recovery branch missing; inspect before modifying workflow RPC'; end if;
 execute revised;
end $migration$;
