-- Durable SaaS data is separate from the recoverable legacy operator application.
create schema if not exists verdict_saas;
do $$ begin
  if not exists(select 1 from pg_roles where rolname='verdict_saas_executor') then
    create role verdict_saas_executor nologin nobypassrls;
  end if;
end $$;
grant verdict_saas_executor to service_role;
grant usage on schema verdict_saas to service_role, verdict_saas_executor;
revoke all on schema verdict_saas from public, anon, authenticated;

create table verdict_saas.accounts (
  id uuid primary key default gen_random_uuid(),
  username text not null unique check(username ~ '^[a-z0-9][a-z0-9_-]{2,31}$'),
  display_name text not null check(length(display_name) between 1 and 80),
  password_hash text not null check(password_hash like '$argon2id$%'),
  recovery_hash text not null,
  created_at timestamptz not null default now()
);
create table verdict_saas.sessions (
  hash text primary key check(hash ~ '^[a-f0-9]{64}$'),
  owner_id uuid not null references verdict_saas.accounts(id),
  expires timestamptz not null default now()+interval '30 days',
  created_at timestamptz not null default now()
);
create index sessions_owner on verdict_saas.sessions(owner_id);
create table verdict_saas.cases (
  id text primary key, owner_id uuid not null references verdict_saas.accounts(id),
  revision integer not null, body jsonb not null,
  created_at timestamptz not null default now(), active_job uuid
);
create index cases_owner_created on verdict_saas.cases(owner_id,created_at desc);
create table verdict_saas.files (
  id text primary key, case_id text not null references verdict_saas.cases(id),
  owner_id uuid not null references verdict_saas.accounts(id),
  content bytea not null, mime text not null, name text not null, sha256 text not null,
  created_at timestamptz not null default now()
);
create index files_owner_case on verdict_saas.files(owner_id,case_id);
create table verdict_saas.requests (
  hash text primary key, case_id text not null references verdict_saas.cases(id),
  owner_id uuid not null references verdict_saas.accounts(id), body jsonb not null,
  expires timestamptz not null, completed boolean not null default false
);
create index requests_owner_case on verdict_saas.requests(owner_id,case_id);
create table verdict_saas.audit (
  seq bigint generated always as identity primary key,
  case_id text not null references verdict_saas.cases(id),
  owner_id uuid not null references verdict_saas.accounts(id),
  at text not null, kind text not null, data jsonb not null,
  previous text not null, hash text not null, canonical_record text not null
);
create index audit_owner_case_seq on verdict_saas.audit(owner_id,case_id,seq);
create table verdict_saas.jobs (
  id uuid primary key default gen_random_uuid(),
  case_id text not null references verdict_saas.cases(id),
  owner_id uuid not null references verdict_saas.accounts(id),
  revision integer not null, state text not null,
  started_at timestamptz not null default now(), expires timestamptz not null default now()+interval '15 minutes',
  error text
);
create index jobs_owner_started on verdict_saas.jobs(owner_id,started_at);
create table verdict_saas.model_slots(model text primary key,next_at timestamptz not null);
create table verdict_saas.rate_limits(key text primary key,attempts integer not null,expires timestamptz not null);
create table verdict_saas.quota(id integer primary key check(id=1), bytes_used bigint not null default 0, analysis_day date not null default current_date,analysis_count integer not null default 0);
insert into verdict_saas.quota(id) values(1);

do $$ declare t text; begin
  foreach t in array array['accounts','sessions','cases','files','requests','audit','jobs','model_slots','rate_limits','quota'] loop
    execute format('alter table verdict_saas.%I enable row level security',t);
    execute format('alter table verdict_saas.%I force row level security',t);
    execute format('revoke all on verdict_saas.%I from public, anon, authenticated',t);
    execute format('grant select,insert,update,delete on verdict_saas.%I to service_role',t);
  end loop;
  foreach t in array array['cases','files','requests','audit','jobs'] loop
    execute format('grant select,insert,update on verdict_saas.%I to verdict_saas_executor',t);
    execute format('create policy owner_isolation on verdict_saas.%I to verdict_saas_executor using (owner_id::text=current_setting(''verdict_saas.actor'',true)) with check (owner_id::text=current_setting(''verdict_saas.actor'',true))',t);
  end loop;
end $$;
grant usage on all sequences in schema verdict_saas to service_role,verdict_saas_executor;
grant select,insert,update on verdict_saas.model_slots,verdict_saas.quota to verdict_saas_executor;
create policy shared_pacing on verdict_saas.model_slots to verdict_saas_executor using(true) with check(true);
create policy shared_quota on verdict_saas.quota to verdict_saas_executor using(true) with check(true);

create function verdict_saas.commit_case(actor uuid, args jsonb, creating boolean default false)
returns jsonb language plpgsql security invoker set search_path=pg_catalog,verdict_saas as $$
declare c cases; b jsonb:=args->'body'; a jsonb:=args->'audit'; r requests;
  prev text; raw bytea; f jsonb:=args->'file'; added_bytes bigint; current_bytes bigint;
begin
  if actor::text is distinct from current_setting('verdict_saas.actor',true) then raise exception 'actor mismatch'; end if;
  if creating then
    perform pg_advisory_xact_lock(hashtextextended(actor::text,0));
    if (select count(*) from cases)>=50 then raise exception 'verdict:case_limit'; end if;
    if (b->>'id') is null or (b->>'id') !~ '^V-[a-f0-9]{16}$' then raise exception 'verdict:invalid_case'; end if;
    insert into cases(id,owner_id,revision,body) values(b->>'id',actor,1,b);
    select * into c from cases where id=b->>'id' for update;
  else
    select * into c from cases where id=args->>'case_id' for update;
    if not found then raise exception 'verdict:not_found'; end if;
    if c.revision<>(args->>'expected_revision')::integer then raise exception 'verdict:stale_revision'; end if;
    if b->>'id' is distinct from c.id or (b->>'revision')::integer<>c.revision+1 then raise exception 'verdict:invalid_revision'; end if;
  end if;
  select hash into prev from audit where case_id=c.id order by seq desc limit 1;
  if a->>'previous' is distinct from coalesce(prev,'') or a->>'case_id' is distinct from c.id
    or (args->>'canonical_record')::jsonb <> (a-'hash')
    or encode(sha256(convert_to(args->>'canonical_record','UTF8')),'hex') is distinct from a->>'hash'
    then raise exception 'audit validation failed'; end if;
  added_bytes:=octet_length(b::text)-case when creating then 0 else octet_length(c.body::text) end+octet_length(a::text);
  if f is not null and f<>'null'::jsonb then
    raw:=decode(f->>'content','base64');
    if octet_length(raw)>5242880 or encode(sha256(raw),'hex') is distinct from f->>'sha256' then raise exception 'verdict:invalid_file'; end if;
    perform pg_advisory_xact_lock(hashtextextended(actor::text,0));
    if (select coalesce(sum(octet_length(content)),0) from files)+octet_length(raw)>20971520 then raise exception 'verdict:storage_limit'; end if;
    added_bytes:=added_bytes+octet_length(raw);
  end if;
  select bytes_used into current_bytes from quota where id=1 for update;
  if current_bytes+added_bytes>209715200 then raise exception 'verdict:service_storage_limit'; end if;
  if args->>'request_action' in ('reply','close') then
    select * into r from requests where hash=args->>'request_hash' and case_id=c.id for update;
    if not found or r.completed or (args->>'request_action'='reply' and r.expires<=now()) then raise exception 'verdict:request_closed'; end if;
    if args->>'request_action'='reply' and (b->'evidence'->-1->>'party') is distinct from r.body->>'recipient' then raise exception 'verdict:recipient_mismatch'; end if;
    update requests set completed=true,body=(select x from jsonb_array_elements(b->'requests') x where x->>'id'=r.body->>'id') where hash=r.hash;
  elsif args->>'request_action'='create' then
    insert into requests(hash,case_id,owner_id,body,expires) values(args->>'request_hash',c.id,actor,args->'request',to_timestamp((args->'request'->>'expires_at')::double precision));
  end if;
  if args->>'job_id' is not null then
    if c.active_job is distinct from (args->>'job_id')::uuid then raise exception 'verdict:stale_job'; end if;
    if not exists(select 1 from jobs where id=c.active_job and state='running' and expires>now()) then raise exception 'verdict:stale_job'; end if;
    update jobs set state='completed' where id=c.active_job;
    update cases set active_job=null where id=c.id;
  end if;
  if raw is not null then
    insert into files(id,case_id,owner_id,content,mime,name,sha256) values(f->>'id',c.id,actor,raw,f->>'mime',f->>'name',f->>'sha256');
  end if;
  update cases set body=b,revision=(b->>'revision')::integer where id=c.id;
  insert into audit(case_id,owner_id,at,kind,data,previous,hash,canonical_record)
    values(c.id,actor,a->>'at',a->>'kind',a->'data',a->>'previous',a->>'hash',args->>'canonical_record');
  update quota set bytes_used=bytes_used+added_bytes where id=1;
  return b;
end $$;
revoke all on function verdict_saas.commit_case(uuid,jsonb,boolean) from public,anon,authenticated;
grant execute on function verdict_saas.commit_case(uuid,jsonb,boolean) to service_role,verdict_saas_executor;

-- Fixed operations only. No user-supplied SQL, owner ID, role or table name is executed.
create function public.verdict_saas_api(p_op text,p_session_hash text default '',p_args jsonb default '{}'::jsonb)
returns jsonb language plpgsql security invoker set search_path=pg_catalog,verdict_saas as $$
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
        'analyses_today',(select count(*) from jobs where owner_id=a and started_at>=date_trunc('day',now())));
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
    if (select count(*) from jobs where started_at>=date_trunc('day',now()))>=10 then return jsonb_build_object('error','analysis_limit'); end if;
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
end $$;
revoke all on function public.verdict_saas_api(text,text,jsonb) from public,anon,authenticated;
grant execute on function public.verdict_saas_api(text,text,jsonb) to service_role;
