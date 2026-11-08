-- Honor long provider-directed retry windows without adding attempts or paid fallback.
do $$ declare definition text; revised text; begin
 definition:=pg_get_functiondef('public.verdict_workflow_api(text,text,jsonb)'::regprocedure);
 revised:=replace(definition,'least(3600,greatest(30,','least(86400,greatest(30,');
 if revised=definition then raise exception 'Expected bounded retry clause missing; inspect before changing function'; end if;
 execute revised;
end $$;
