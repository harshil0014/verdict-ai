-- Additive server-only policy, durable dispatch barrier and transcription consent.
create table verdict_saas.agent_preferences (
 owner_id uuid primary key references verdict_saas.accounts(id),enabled boolean not null default false,
 updated_at timestamptz not null default now()
);
create table verdict_saas.agent_policies (
 id uuid primary key default gen_random_uuid(),owner_id uuid not null references verdict_saas.accounts(id),
 connection_id uuid not null references verdict_saas.paypal_connections(id),enabled boolean not null,
 per_claim_usd numeric(8,2) not null check(per_claim_usd>0 and per_claim_usd<=5),
 total_usd numeric(8,2) not null check(total_usd>0 and total_usd<=10),
 reserved_usd numeric(8,2) not null default 0 check(reserved_usd>=0),
 max_actions integer not null check(max_actions between 1 and 5),actions integer not null default 0,
 unfulfilled_test_orders boolean not null check(unfulfilled_test_orders),expires_at timestamptz not null,
 authorized_at timestamptz not null default now(),revoked_at timestamptz,next_check_at timestamptz not null default now(),
 authorization_basis text not null default 'authenticated merchant opt-in; sandbox unfulfilled VERDICT test orders only'
);
create unique index agent_one_active_policy on verdict_saas.agent_policies(connection_id) where enabled;
create index agent_policies_owner on verdict_saas.agent_policies(owner_id);
create table verdict_saas.agent_actions (
 id uuid primary key default gen_random_uuid(),owner_id uuid not null references verdict_saas.accounts(id),
 connection_id uuid not null references verdict_saas.paypal_connections(id),policy_id uuid not null references verdict_saas.agent_policies(id),
 case_id text not null references verdict_saas.cases(id),dispute_id text not null,merchant_id text not null,
 state text not null default 'prepared' check(state in ('prepared','sending','waiting_provider','uncertain','rejected','resolved','refunded')),
 amount numeric(8,2) not null check(amount>0 and amount<=5),basis jsonb not null,result jsonb,
 created_at timestamptz not null default now(),sent_at timestamptz,updated_at timestamptz not null default now(),
 unique(merchant_id,dispute_id)
);
create index agent_actions_owner on verdict_saas.agent_actions(owner_id);
create index agent_actions_connection on verdict_saas.agent_actions(connection_id);
create index agent_actions_policy on verdict_saas.agent_actions(policy_id);
create index agent_actions_case on verdict_saas.agent_actions(case_id);
create table verdict_saas.agent_observations (
 case_id text primary key references verdict_saas.cases(id),owner_id uuid not null references verdict_saas.accounts(id),
 body jsonb not null,updated_at timestamptz not null default now()
);
create index agent_observations_owner on verdict_saas.agent_observations(owner_id);
create table verdict_saas.agent_events (
 id bigint generated always as identity primary key,owner_id uuid not null references verdict_saas.accounts(id),
 kind text not null,data jsonb not null,at timestamptz not null default now()
);
create index agent_events_owner on verdict_saas.agent_events(owner_id);
do $$ declare t text; begin
 foreach t in array array['agent_preferences','agent_policies','agent_actions','agent_observations','agent_events'] loop
  execute format('alter table verdict_saas.%I enable row level security',t);
  execute format('alter table verdict_saas.%I force row level security',t);
  execute format('revoke all on verdict_saas.%I from public,anon,authenticated',t);
  execute format('grant select,insert,update on verdict_saas.%I to service_role,verdict_saas_executor',t);
  execute format('create policy owner_isolation on verdict_saas.%I to verdict_saas_executor using(owner_id::text=current_setting(''verdict_saas.actor'',true)) with check(owner_id::text=current_setting(''verdict_saas.actor'',true))',t);
 end loop;
end $$;
revoke update on verdict_saas.agent_events from verdict_saas_executor;
grant usage on sequence verdict_saas.agent_events_id_seq to verdict_saas_executor,service_role;

create function public.verdict_agent_api(p_op text,p_session_hash text default '',p_args jsonb default '{}'::jsonb)
returns jsonb language plpgsql security invoker set search_path=pg_catalog,verdict_saas as $$
declare actor uuid; conn paypal_connections; pol agent_policies; act agent_actions; c cases; result jsonb; amount numeric; n integer; global_vision integer;
begin
 -- No HTTP route exposes this service-only scheduling operation.
 if p_op='due' then
  with due as (
   select p.id from agent_policies p join paypal_connections pc on pc.id=p.connection_id
   where pc.active and p.next_check_at<=now() and
    ((p.enabled and p.expires_at>now()) or exists(select 1 from agent_actions a where a.policy_id=p.id and a.state in ('prepared','sending','waiting_provider','uncertain')))
   order by p.next_check_at limit 2 for update of p skip locked
  ), changed as (
   update agent_policies set next_check_at=now()+interval '5 minutes' where id in (select id from due)
   returning connection_id,(enabled and expires_at>now()) as enabled
  ) select coalesce(jsonb_agg(to_jsonb(changed)),'[]'::jsonb) into result from changed;
  return result;
 end if;
 select owner_id into actor from sessions where hash=p_session_hash and expires>now();
 if actor is null then raise exception 'verdict:unauthorized'; end if;
 if p_op='vision_budget' then
  perform pg_advisory_xact_lock(hashtextextended('agent-vision-budget',0));
  select count(*) into global_vision from agent_events where kind='vision_attempt' and at>date_trunc('day',now());
  if global_vision>=50 then raise exception 'verdict:global_analysis_limit'; end if;
 end if;
 perform set_config('verdict_saas.actor',actor::text,true);
 execute 'set local role verdict_saas_executor';
 if p_op='reading_preference' then
  return jsonb_build_object('enabled',coalesce((select enabled from agent_preferences where owner_id=actor),false));
 elsif p_op='reading_consent' then
  insert into agent_preferences(owner_id,enabled) values(actor,(p_args->>'enabled')::boolean)
   on conflict(owner_id) do update set enabled=excluded.enabled,updated_at=now();
  insert into agent_events(owner_id,kind,data) values(actor,'image_reading_consent',jsonb_build_object('enabled',(p_args->>'enabled')::boolean));
  return jsonb_build_object('enabled',(p_args->>'enabled')::boolean);
 elsif p_op='vision_budget' then
  if not coalesce((select enabled from agent_preferences where owner_id=actor),false) then raise exception 'verdict:unauthorized'; end if;
  if not exists(select 1 from cases where id=p_args->>'case_id') then raise exception 'verdict:not_found'; end if;
  perform pg_advisory_xact_lock(hashtextextended('agent-vision-budget',0));
  if (select count(*) from agent_events where kind='vision_attempt' and at>date_trunc('day',now()))>=20 then raise exception 'verdict:analysis_limit'; end if;
  -- Server role sees the global budget; executor sees its own attempts under RLS.
  insert into agent_events(owner_id,kind,data) values(actor,'vision_attempt',p_args);
  return '{}'::jsonb;
 end if;
 if p_op in ('status','observe') then
  select * into c from cases where id=p_args->>'case_id';
  if not found then raise exception 'verdict:not_found'; end if;
  if p_op='observe' then
   if octet_length((p_args->'observation')::text)>8000 then raise exception 'verdict:invalid_revision'; end if;
   if (select body from agent_observations where case_id=c.id) is distinct from p_args->'observation' then
    insert into agent_observations(case_id,owner_id,body) values(c.id,actor,p_args->'observation')
     on conflict(case_id) do update set body=excluded.body,updated_at=now();
    insert into agent_events(owner_id,kind,data) values(actor,'provider_observed',jsonb_build_object('case_id',c.id,'observation',p_args->'observation'));
   end if;
   update agent_actions set state=p_args->'observation'->>'state',updated_at=now()
    where case_id=c.id and p_args->'observation'->>'state' in ('resolved','refunded');
  end if;
  select * into act from agent_actions where case_id=c.id;
  return jsonb_build_object('observation',(select body from agent_observations where case_id=c.id),
   'action',case when act.id is null then null else to_jsonb(act) end);
 end if;
 select * into conn from paypal_connections where owner_id=actor and active for share;
 if not found then raise exception 'verdict:not_found'; end if;
 if p_op in ('policy','enable','reserve') and conn.id is distinct from (p_args->>'connection_id')::uuid then raise exception 'verdict:not_found'; end if;
 if p_op='policy' then
  select * into pol from agent_policies where connection_id=conn.id order by authorized_at desc limit 1;
  if not found then return jsonb_build_object('enabled',false); end if;
  return to_jsonb(pol)||jsonb_build_object('enabled',pol.enabled and pol.expires_at>now());
 elsif p_op='enable' then
  perform pg_advisory_xact_lock(hashtextextended('agent-policy:'||conn.id::text,0));
  update agent_policies set enabled=false,revoked_at=now() where connection_id=conn.id and enabled;
  if (p_args->>'enabled')::boolean then
   if not (p_args->>'unfulfilled_test_orders')::boolean or (p_args->>'hours')::integer not between 1 and 24 then raise exception 'verdict:invalid_revision'; end if;
   insert into agent_policies(owner_id,connection_id,enabled,per_claim_usd,total_usd,max_actions,unfulfilled_test_orders,expires_at)
    values(actor,conn.id,true,(p_args->>'per_claim_usd')::numeric,(p_args->>'total_usd')::numeric,
     (p_args->>'max_actions')::integer,true,now()+make_interval(hours=>(p_args->>'hours')::integer)) returning * into pol;
  end if;
  insert into agent_events(owner_id,kind,data) values(actor,'sandbox_policy_changed',p_args);
  return jsonb_build_object('enabled',pol.id is not null,'policy',to_jsonb(pol));
 elsif p_op='reserve' then
  select * into c from cases where id=p_args->>'case_id' for update;
  if not found or c.revision<>(p_args->>'expected_revision')::integer then raise exception 'verdict:stale_revision'; end if;
  if c.body->>'mode'<>'paypal_sandbox_saas' or c.body->>'paypal_connection_id'<>conn.id::text then raise exception 'verdict:not_found'; end if;
  select * into pol from agent_policies where id=(p_args->>'policy_id')::uuid and connection_id=conn.id for update;
  amount:=(p_args->>'amount')::numeric;
  if not found or not pol.enabled or pol.expires_at<=now() or pol.actions>=pol.max_actions or amount>pol.per_claim_usd
   or amount<=0 or pol.reserved_usd+amount>pol.total_usd then return jsonb_build_object('created',false); end if;
  insert into agent_actions(owner_id,connection_id,policy_id,case_id,dispute_id,merchant_id,amount,basis)
   values(actor,conn.id,pol.id,c.id,c.body->>'paypal_id',conn.merchant_id,amount,p_args->'basis')
   on conflict(merchant_id,dispute_id) do nothing returning * into act;
  if not found then return jsonb_build_object('created',false); end if;
  update agent_policies set actions=actions+1,reserved_usd=reserved_usd+amount where id=pol.id;
  insert into agent_events(owner_id,kind,data) values(actor,'sandbox_action_reserved',to_jsonb(act));
  return jsonb_build_object('created',true,'action',to_jsonb(act));
 elsif p_op='sending' then
  select * into act from agent_actions where id=(p_args->>'id')::uuid;
  if not found then raise exception 'verdict:not_found'; end if;
  select * into pol from agent_policies where id=act.policy_id for update;
  if not pol.enabled or pol.expires_at<=now() then return jsonb_build_object('send',false); end if;
  update agent_actions set state='sending',sent_at=now(),updated_at=now() where id=act.id and state='prepared';
  get diagnostics n=row_count;
  if n=1 then insert into agent_events(owner_id,kind,data) values(actor,'sandbox_dispatch_started',jsonb_build_object('id',act.id)); end if;
  return jsonb_build_object('send',n=1);
 elsif p_op='action_result' then
  if p_args->'result'->>'state' not in ('waiting_provider','uncertain','rejected') then raise exception 'verdict:invalid_revision'; end if;
  update agent_actions set state=p_args->'result'->>'state',result=p_args->'result',updated_at=now()
   where id=(p_args->>'id')::uuid and state='sending';
  if not found then raise exception 'verdict:not_found'; end if;
  insert into agent_events(owner_id,kind,data) values(actor,'sandbox_action_response',p_args);
  return '{}'::jsonb;
 end if;
 raise exception 'verdict:not_found';
end $$;
revoke all on function public.verdict_agent_api(text,text,jsonb) from public,anon,authenticated;
grant execute on function public.verdict_agent_api(text,text,jsonb) to service_role;

-- Older workers must not claim a source while a document is awaiting OCR.
do $$ declare definition text; revised text; begin
 definition:=pg_get_functiondef('public.verdict_workflow_api(text,text,jsonb)'::regprocedure);
 revised:=replace(definition,
  'and coalesce((w0.progress->>''required_worker_version'')::integer,1)<=coalesce((p_args->>''worker_version'')::integer,1)',
  'and greatest(coalesce((w0.progress->>''required_worker_version'')::integer,1),coalesce((c0.body->>''automatic_workflow_version'')::integer,1))<=coalesce((p_args->>''worker_version'')::integer,1)');
 if revised=definition then raise exception 'Inspect worker compatibility before upgrading'; end if;
 execute revised;
end $$;
