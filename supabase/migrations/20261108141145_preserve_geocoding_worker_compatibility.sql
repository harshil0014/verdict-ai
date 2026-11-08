-- Preserve the new resolver requirement when transient work is rescheduled.
do $$ declare definition text; revised text; begin
 definition:=pg_get_functiondef('public.verdict_workflow_api(text,text,jsonb)'::regprocedure);
 revised:=replace(definition,'''required_worker_version'',5,''recovery_attempts''',
  '''required_worker_version'',greatest(6,coalesce((progress->>''required_worker_version'')::integer,1)),''recovery_attempts''');
 if revised=definition then raise exception 'Expected retry compatibility clause missing'; end if;
 execute revised;
end $$;
