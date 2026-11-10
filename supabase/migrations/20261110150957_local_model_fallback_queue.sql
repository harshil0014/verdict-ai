-- Tenant-bound outbound Ollama worker. No local inference port is exposed.
create table verdict_saas.local_model_workers (
 owner_id uuid primary key references verdict_saas.accounts(id),
 token_hash text not null unique check(token_hash ~ '^[a-f0-9]{64}$'),
 model text not null, model_digest text not null check(model_digest ~ '^[a-f0-9]{64}$'),
 context_tokens integer not null check(context_tokens between 4096 and 262144),
 enabled boolean not null default false, last_seen timestamptz,
 authorized_at timestamptz not null default now()
);
create table verdict_saas.local_model_jobs (
 id uuid primary key default gen_random_uuid(), owner_id uuid not null references verdict_saas.accounts(id),
 request_digest text not null check(request_digest ~ '^[a-f0-9]{64}$'),
 request_text text not null check(octet_length(request_text)<=1500000),
 model text not null,model_digest text not null,
 state text not null default 'queued' check(state in ('queued','running','completed','failed','cancelled')),
 result jsonb, error_code text,lease_token uuid,lease_until timestamptz,
 created_at timestamptz not null default now(),expires_at timestamptz not null default now()+interval '30 minutes',
 unique(owner_id,request_digest)
);
alter table verdict_saas.local_model_workers enable row level security;
alter table verdict_saas.local_model_workers force row level security;
alter table verdict_saas.local_model_jobs enable row level security;
alter table verdict_saas.local_model_jobs force row level security;
revoke all on verdict_saas.local_model_workers,verdict_saas.local_model_jobs from public,anon,authenticated;
grant all on verdict_saas.local_model_workers,verdict_saas.local_model_jobs to service_role;
grant select on verdict_saas.local_model_workers to verdict_saas_executor;
grant select,insert,update,delete on verdict_saas.local_model_jobs to verdict_saas_executor;
create policy owner_read on verdict_saas.local_model_workers for select to verdict_saas_executor
 using(owner_id::text=current_setting('verdict_saas.actor',true));
create policy owner_jobs on verdict_saas.local_model_jobs for all to verdict_saas_executor
 using(owner_id::text=current_setting('verdict_saas.actor',true)) with check(owner_id::text=current_setting('verdict_saas.actor',true));

create function public.verdict_local_model_api(p_op text,p_session_hash text default '',p_args jsonb default '{}')
returns jsonb language plpgsql set search_path=pg_catalog,verdict_saas as $$
declare actor uuid; w local_model_workers; j local_model_jobs; token uuid;
begin
 if p_op in ('claim','renew','complete','fail') then
  select * into w from local_model_workers where token_hash=p_args->>'worker_hash' and enabled;
  if not found then raise exception 'verdict:unauthorized'; end if;
  actor:=w.owner_id;
 else
  select owner_id into actor from sessions where hash=p_session_hash and expires>now();
  if actor is null then raise exception 'verdict:unauthorized'; end if;
  select * into w from local_model_workers where owner_id=actor and enabled;
 end if;
 if p_op in ('claim','renew','complete','fail') then update local_model_workers set last_seen=now() where owner_id=actor; end if;
 perform set_config('verdict_saas.actor',actor::text,true);
 execute 'set local role verdict_saas_executor';
 if p_op='available' then
  return jsonb_build_object('available',w.enabled and w.last_seen>now()-interval '90 seconds','model',w.model);
 elsif p_op='enqueue' then
  if w.owner_id is null or not w.enabled or w.last_seen is null or w.last_seen<=now()-interval '90 seconds' then
   return jsonb_build_object('available',false);
  end if;
  if octet_length(coalesce(p_args->>'request_text','')) not between 2 and 1500000
   or encode(sha256(convert_to(p_args->>'request_text','UTF8')),'hex') is distinct from p_args->>'request_digest'
   or jsonb_typeof((p_args->>'request_text')::jsonb)<>'object' then raise exception 'verdict:invalid_revision'; end if;
  delete from local_model_jobs where owner_id=actor and expires_at<now();
  if (select count(*) from local_model_jobs where owner_id=actor and state in ('queued','running'))>=2
   and not exists(select 1 from local_model_jobs where owner_id=actor and request_digest=p_args->>'request_digest') then
   raise exception 'verdict:analysis_busy'; end if;
  insert into local_model_jobs(owner_id,request_digest,request_text,model,model_digest)
   values(actor,p_args->>'request_digest',p_args->>'request_text',w.model,w.model_digest)
   on conflict(owner_id,request_digest) do update set
    id=gen_random_uuid(),request_text=excluded.request_text,model=excluded.model,model_digest=excluded.model_digest,
    state='queued',result=null,error_code=null,lease_token=null,lease_until=null,created_at=now(),expires_at=now()+interval '30 minutes'
    where local_model_jobs.state in ('failed','cancelled') or local_model_jobs.model_digest<>excluded.model_digest;
  select * into j from local_model_jobs where owner_id=actor and request_digest=p_args->>'request_digest';
  return jsonb_build_object('available',true,'id',j.id,'state',j.state,'result',j.result,'request_digest',j.request_digest);
 elsif p_op in ('poll','cancel','reject') then
  select * into j from local_model_jobs where id=(p_args->>'job_id')::uuid and owner_id=actor and expires_at>now();
  if not found then raise exception 'verdict:not_found'; end if;
  if p_op='cancel' and j.state in ('queued','running') then
   update local_model_jobs set state='cancelled',request_text='{}',result=null,lease_token=null,lease_until=null where id=j.id;
  end if;
  if p_op='reject' and j.state='completed' then
   update local_model_jobs set state='failed',error_code='invalid_response',request_text='{}',result=null where id=j.id;
  end if;
  return jsonb_build_object('state',j.state,'result',j.result,'error_code',j.error_code,'request_digest',j.request_digest);
 elsif p_op='claim' then
  delete from local_model_jobs where owner_id=actor and expires_at<now();
  update local_model_jobs set state='failed',error_code='worker_interrupted',lease_token=null,lease_until=null
   where owner_id=actor and state='running' and lease_until<now();
  if exists(select 1 from local_model_jobs where owner_id=actor and state='running') then return 'null'::jsonb; end if;
  select * into j from local_model_jobs where owner_id=actor and state='queued' and expires_at>now()
   and model_digest=w.model_digest order by created_at for update skip locked limit 1;
  if not found then return 'null'::jsonb; end if;
  token:=gen_random_uuid();
  update local_model_jobs set state='running',lease_token=token,lease_until=now()+interval '90 seconds' where id=j.id;
  return jsonb_build_object('job_id',j.id,'lease_token',token,'request_text',j.request_text,
   'request_digest',j.request_digest,'model',j.model,'model_digest',j.model_digest,'context_tokens',w.context_tokens);
 elsif p_op in ('renew','complete','fail') then
  select * into j from local_model_jobs where id=(p_args->>'job_id')::uuid and owner_id=actor
   and state='running' and lease_token=(p_args->>'lease_token')::uuid and lease_until>now() for update;
  if not found then raise exception 'verdict:stale_job'; end if;
  if p_op='renew' then
   update local_model_jobs set lease_until=now()+interval '90 seconds' where id=j.id;
  elsif p_op='complete' then
   if p_args->>'request_digest' is distinct from j.request_digest or p_args->'result'->>'model_digest' is distinct from j.model_digest
    or p_args->'result'->>'model' is distinct from j.model
    or jsonb_typeof(p_args->'result')<>'object' or octet_length((p_args->'result')::text)>1500000
    or p_args->'result'->>'done_reason' is distinct from 'stop' then raise exception 'verdict:invalid_revision'; end if;
   update local_model_jobs set state='completed',result=p_args->'result',request_text='{}',lease_token=null,lease_until=null where id=j.id;
  else
   if p_args->>'error_code' not in ('context_limit','ollama_unavailable','invalid_response','generation_limit','worker_interrupted','model_changed') then raise exception 'verdict:invalid_revision'; end if;
   update local_model_jobs set state='failed',error_code=p_args->>'error_code',request_text='{}',lease_token=null,lease_until=null where id=j.id;
  end if;
  return jsonb_build_object('ok',true);
 end if;
 raise exception 'verdict:unsupported_operation';
end $$;
revoke all on function public.verdict_local_model_api(text,text,jsonb) from public,anon,authenticated;
grant execute on function public.verdict_local_model_api(text,text,jsonb) to service_role;

-- Provider outages do not consume the user's successful-investigation allowance.
-- The shared 100-attempt service cap and provider pacing remain unchanged.
CREATE OR REPLACE FUNCTION public.verdict_saas_api(p_op text, p_session_hash text DEFAULT ''::text, p_args jsonb DEFAULT '{}'::jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO 'pg_catalog', 'verdict_saas'
AS $function$
declare u accounts; s sessions; c cases; r requests; j jobs; n integer; slot timestamptz;
  a uuid; result jsonb; attempt integer; until_at timestamptz;
begin
  if p_op='health' then return jsonb_build_object('schema_version',1,'storage','postgres'); end if;
  if p_op='rate' then
    insert into rate_limits(key,attempts,expires) values(p_args->>'key',1,now()+make_interval(secs=>(p_args->>'seconds')::integer))
    on conflict(key) do update set attempts=case when rate_limits.expires<=now() then 1 else rate_limits.attempts+1 end,
      expires=case when rate_limits.expires<=now() then excluded.expires else rate_limits.expires end
    returning attempts,expires into attempt,until_at;
    return jsonb_build_object('allowed',attempt<=(p_args->>'limit')::integer,'expires',until_at);
  end if;
  if p_op='register' then
    perform pg_advisory_xact_lock(194732061);
    if (select count(*) from accounts)>=1000 then return jsonb_build_object('error','registration_capacity'); end if;
    if exists(select 1 from accounts where username=p_args->>'username') then return jsonb_build_object('error','username_taken'); end if;
    insert into accounts(username,display_name,password_hash,recovery_hash) values(p_args->>'username',p_args->>'display_name',p_args->>'password_hash',p_args->>'recovery_hash') returning * into u;
    insert into sessions(hash,owner_id) values(p_session_hash,u.id);
    return jsonb_build_object('id',u.id,'username',u.username,'display_name',u.display_name);
  elsif p_op='login_lookup' then
    select * into u from accounts where username=p_args->>'username';
    return case when found then jsonb_build_object('id',u.id,'password_hash',u.password_hash) else 'null'::jsonb end;
  elsif p_op='login_commit' then
    select * into u from accounts where username=p_args->>'username' for update;
    if not found or u.password_hash is distinct from p_args->>'expected_hash' then return jsonb_build_object('error','invalid_credentials'); end if;
    if p_args->>'upgraded_hash' is not null then update accounts set password_hash=p_args->>'upgraded_hash' where id=u.id; end if;
    insert into sessions(hash,owner_id) values(p_session_hash,u.id);
    return jsonb_build_object('id',u.id,'username',u.username,'display_name',u.display_name);
  elsif p_op='recover' then
    select * into u from accounts where username=p_args->>'username' for update;
    if not found or u.recovery_hash is distinct from p_args->>'recovery_hash' then return jsonb_build_object('error','invalid_credentials'); end if;
    update accounts set password_hash=p_args->>'password_hash',recovery_hash=p_args->>'new_recovery_hash' where id=u.id;
    delete from sessions where owner_id=u.id;
    insert into sessions(hash,owner_id) values(p_session_hash,u.id);
    return jsonb_build_object('id',u.id,'username',u.username,'display_name',u.display_name);
  end if;
  if p_op in ('portal_context','portal_submit') then
    select * into r from requests where hash=p_args->>'request_hash' and not completed and expires>now();
    if not found then return jsonb_build_object('error','request_closed'); end if;
    a:=r.owner_id;
  else
    select * into s from sessions where hash=p_session_hash and expires>now();
    if not found then return jsonb_build_object('error','unauthorized'); end if;
    a:=s.owner_id;
    if p_op='me' then
      select * into u from accounts where id=a;
      return jsonb_build_object('id',u.id,'username',u.username,'display_name',u.display_name,
        'storage_bytes',(select coalesce(sum(octet_length(content)),0) from files where owner_id=a),
        'analyses_today',(select count(*) from jobs where owner_id=a and started_at>=date_trunc('day',now()) and not (state='failed' and (coalesce(error,'') like 'Gemini is temporarily unavailable.%' or coalesce(error,'') like 'Gemini is rate limited.%' or coalesce(error,'') like 'The connection to Gemini failed.%'))));
    elsif p_op='logout' then delete from sessions where hash=p_session_hash; return '{}'::jsonb;
    end if;
  end if;
  -- Session-derived actor is set before dropping BYPASSRLS privileges.
  perform set_config('verdict_saas.actor',a::text,true);
  execute 'set local role verdict_saas_executor';
  if p_op='list' then
    return coalesce((select jsonb_agg(body order by created_at desc) from cases),'[]'::jsonb);
  elsif p_op='get' then
    select * into c from cases where id=p_args->>'case_id';
    if not found then return jsonb_build_object('error','not_found'); end if;
    return c.body||jsonb_build_object('timeline',coalesce((select jsonb_agg(jsonb_build_object('seq',seq,'case_id',case_id,'at',at,'kind',kind,'data',data,'previous',previous,'hash',hash) order by seq) from audit where case_id=c.id),'[]'::jsonb));
  elsif p_op='file' then
    return coalesce((select jsonb_build_object('content',encode(content,'base64'),'mime',mime,'name',name,'sha256',sha256) from files where id=p_args->>'file_id' and case_id=p_args->>'case_id'),jsonb_build_object('error','not_found'));
  elsif p_op='create' then return commit_case(a,p_args,true);
  elsif p_op='save' then return commit_case(a,p_args,false);
  elsif p_op='portal_context' then
    select * into c from cases where id=r.case_id;
    return jsonb_build_object('request',r.body,'case',c.body,'timeline',coalesce((select jsonb_agg(jsonb_build_object('seq',seq,'case_id',case_id,'at',at,'kind',kind,'data',data,'previous',previous,'hash',hash) order by seq) from audit where case_id=c.id),'[]'::jsonb));
  elsif p_op='portal_submit' then
    if p_args->>'case_id' is distinct from r.case_id then return jsonb_build_object('error','not_found'); end if;
    return commit_case(a,p_args,false);
  elsif p_op='reserve_analysis' then
    select * into c from cases where id=p_args->>'case_id' for update;
    if not found then return jsonb_build_object('error','not_found'); end if;
    if c.active_job is not null and exists(select 1 from jobs where id=c.active_job and state='running' and expires>now()) then return jsonb_build_object('error','analysis_busy'); end if;
    perform pg_advisory_xact_lock(hashtextextended(a::text,0));
    if (select count(*) from jobs where started_at>=date_trunc('day',now()) and not (state='failed' and (coalesce(error,'') like 'Gemini is temporarily unavailable.%' or coalesce(error,'') like 'Gemini is rate limited.%' or coalesce(error,'') like 'The connection to Gemini failed.%')))>=10 then return jsonb_build_object('error','analysis_limit'); end if;
    perform 1 from quota where id=1 for update;
    update quota set analysis_day=current_date,analysis_count=0 where id=1 and analysis_day<>current_date;
    if (select analysis_count from quota where id=1)>=100 then return jsonb_build_object('error','global_analysis_limit'); end if;
    update quota set analysis_count=analysis_count+1 where id=1;
    insert into jobs(case_id,owner_id,revision,state) values(c.id,a,c.revision,'running') returning * into j;
    update cases set active_job=j.id where id=c.id;
    return jsonb_build_object('job_id',j.id,'revision',c.revision);
  elsif p_op='fail_analysis' then
    update jobs set state='failed',error=left(p_args->>'error',500) where id=(p_args->>'job_id')::uuid and state='running';
    update cases set active_job=null where active_job=(p_args->>'job_id')::uuid;
    return '{}'::jsonb;
  elsif p_op='model_slot' then
    insert into model_slots(model,next_at) values(p_args->>'model',now()) on conflict do nothing;
    select greatest(next_at,clock_timestamp()) into slot from model_slots where model=p_args->>'model' for update;
    update model_slots set next_at=slot+interval '5.5 seconds' where model=p_args->>'model';
    return jsonb_build_object('wait_seconds',greatest(0,extract(epoch from slot-clock_timestamp())));
  end if;
  return jsonb_build_object('error','unsupported_operation');
end $function$
;
