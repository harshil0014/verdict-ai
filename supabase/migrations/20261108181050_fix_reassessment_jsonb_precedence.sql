-- JSON extraction must be parenthesized before jsonb key subtraction.
-- The prior branch failed closed before committing any case or queue mutation.
do $$ declare definition text; revised text; begin
 definition:=pg_get_functiondef('public.verdict_agent_api(text,text,jsonb)'::regprocedure);
 revised:=replace(definition,'(p_args->''mutation''->''body'' - array[',
  '((p_args->''mutation''->''body'') - array[');
 if revised=definition then raise exception 'Expected reassessment validation missing'; end if;
 execute revised;
end $$;
