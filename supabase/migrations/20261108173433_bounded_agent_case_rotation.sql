-- Fair bounded reconciliation: do not starve later imported cases.
do $$ declare definition text; revised text; begin
 definition:=pg_get_functiondef('public.verdict_agent_api(text,text,jsonb)'::regprocedure);
 revised:=replace(definition,'if p_op=''policy'' then',$branch$
 if p_op='work_cases' then
  if conn.id is distinct from (p_args->>'connection_id')::uuid then raise exception 'verdict:not_found'; end if;
  return coalesce((select jsonb_agg(to_jsonb(q)) from (
   select i.case_id from paypal_imports i left join agent_observations o on o.case_id=i.case_id
   where i.connection_id=conn.id
   order by coalesce(o.updated_at,'-infinity'::timestamptz),i.case_id limit 5
  ) q),'[]'::jsonb);
 end if;
 if p_op='policy' then$branch$);
 if revised=definition then raise exception 'Expected policy branch missing'; end if;
 execute revised;
end $$;
