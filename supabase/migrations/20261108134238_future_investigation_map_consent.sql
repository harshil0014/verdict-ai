-- Remembered permission applies to subsequent investigation work. Enabling it
-- must not silently initiate geocoding across older cases. Revocation may
-- requeue inherited cases for local-only comparison; current-case authorization
-- already has its own explicit, owner-checked enqueue operation.
do $$ declare definition text; revised text; begin
 definition:=pg_get_functiondef('public.verdict_experience_api(text,text,jsonb)'::regprocedure);
 revised:=replace(definition,'for c in select * from cases where owner_id=actor and coalesce(',
  'for c in select * from cases where owner_id=actor and p_args->>''mode''=''off'' and coalesce(');
 if revised=definition then raise exception 'Expected preference enqueue clause missing; inspect before changing function'; end if;
 execute revised;
end $$;
