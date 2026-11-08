-- Two dispute IDs for the same payment must not produce two full refunds.
alter table verdict_saas.agent_actions add constraint agent_capture_required
 check(coalesce(basis->>'capture_id','') ~ '^[A-Za-z0-9-]{1,80}$');
create unique index agent_one_financial_capture on verdict_saas.agent_actions(merchant_id,(basis->>'capture_id'));
do $$ declare definition text; revised text; begin
 definition:=pg_get_functiondef('public.verdict_agent_api(text,text,jsonb)'::regprocedure);
 revised:=replace(definition,'on conflict(merchant_id,dispute_id) do nothing returning * into act;',
  'on conflict do nothing returning * into act;');
 if revised=definition then raise exception 'Expected reservation branch missing'; end if;
 execute revised;
end $$;
