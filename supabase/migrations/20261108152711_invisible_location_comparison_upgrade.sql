-- Recompare retained source descriptions once, with no new sharing permission.
-- Source snapshots and former assessments remain in the ordinary audit history.
do $migration$ declare definition text; revised text; begin
 definition:=pg_get_functiondef('public.verdict_workflow_api(text,text,jsonb)'::regprocedure);
 revised:=replace(definition,' if p_op=''queue_recovery'' then',$branch$
 if p_op='queue_location_comparison_upgrade' then
  with eligible as (
   select c0.id from cases c0 join workflows w0 on w0.case_id=c0.id
   where w0.state in ('completed','partial','failed')
    and coalesce((c0.body->>'automatic_investigation')::boolean,false)
    and c0.body->'delivery_location'->>'version'='2'
    and c0.body->'delivery_location'->>'status' in ('POSSIBLE MATCH','LIKELY MATCH','UNVERIFIED')
    and jsonb_array_length(coalesce(c0.body->'delivery_location'->'comparisons','[]'::jsonb))>0
    and exists(select 1 from jsonb_array_elements(coalesce(c0.body->'delivery_location'->'mentions','[]'::jsonb)) m
      where m->'geocode'->>'precision' in ('building','site','entrance'))
    and coalesce((w0.progress->>'location_comparison_scheduled_version')::integer,0)<3
   order by w0.updated_at limit 5 for update of c0,w0 skip locked
  )
  update workflows set state='queued',stage='queued',generation=generation+1,attempts=0,next_attempt_at=null,
   progress=progress||jsonb_build_object('required_worker_version',7,'location_comparison_scheduled_version',3),
   detail='Comparing the retained delivery address descriptions.',updated_at=now()
   where case_id in (select id from eligible);
  get diagnostics queued=row_count;
  return jsonb_build_object('queued',queued);
 end if;
 if p_op='queue_recovery' then$branch$);
 if revised=definition then raise exception 'Expected recovery branch missing; inspect before modifying workflow RPC'; end if;
 execute revised;
end $migration$;
