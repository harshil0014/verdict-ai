-- Additive private preferences and durable, bounded transient recovery.
alter table verdict_saas.workflows add column next_attempt_at timestamptz;
create table verdict_saas.preferences(owner_id uuid primary key references verdict_saas.accounts(id),mode text not null default 'off' check(mode in ('off','area_only','address')),acknowledged_at timestamptz);
alter table verdict_saas.preferences enable row level security;
alter table verdict_saas.preferences force row level security;
revoke all on verdict_saas.preferences from public,anon,authenticated;
grant select,insert,update on verdict_saas.preferences to service_role,verdict_saas_executor;
create policy preferences_owner on verdict_saas.preferences to verdict_saas_executor using(owner_id::text=current_setting('verdict_saas.actor',true)) with check(owner_id::text=current_setting('verdict_saas.actor',true));
create function public.verdict_experience_api(p_op text,p_session_hash text default '',p_args jsonb default '{}'::jsonb)
returns jsonb language plpgsql security invoker set search_path=pg_catalog,verdict_saas as $$
declare actor uuid; r preferences; c cases;
begin
 select owner_id into actor from sessions where hash=p_session_hash and expires>now();
 if actor is null then raise exception 'verdict:unauthorized'; end if;
 perform set_config('verdict_saas.actor',actor::text,true);execute 'set local role verdict_saas_executor';
 if p_op='set_maps' then
  if p_args->>'mode' not in ('off','area_only','address') then raise exception 'verdict:invalid_revision'; end if;
  insert into preferences(owner_id,mode,acknowledged_at) values(actor,p_args->>'mode',now()) on conflict(owner_id) do update set mode=excluded.mode,acknowledged_at=excluded.acknowledged_at;
  -- No case mutation, no ownership changes. Existing explicit per-case choices win.
  for c in select * from cases where owner_id=actor and coalesce((body->>'automatic_investigation')::boolean,false) and jsonb_array_length(body->'evidence')>0 and coalesce(body->'location_authorization'->>'mode','account')='account' order by id for update loop
   insert into workflows(case_id,owner_id,progress) values(c.id,actor,jsonb_build_object('required_worker_version',5))
   on conflict(case_id) do update set generation=workflows.generation+1,state=case when workflows.state='running' then 'running' else 'queued' end,attempts=0,next_attempt_at=null,detail='',progress=workflows.progress||excluded.progress,updated_at=now();
  end loop;
 elsif p_op<>'preferences' then raise exception 'verdict:unsupported_operation'; end if;
 select * into r from preferences where owner_id=actor;
 return jsonb_build_object('mode',coalesce(r.mode,'off'),'acknowledged_at',r.acknowledged_at,'scope','account');
end $$;
revoke all on function public.verdict_experience_api(text,text,jsonb) from public,anon,authenticated;
grant execute on function public.verdict_experience_api(text,text,jsonb) to service_role;

-- One bounded upgrade from retained publisher wrappers; prior failures remain in history.
-- Additive recovery scheduling and worker compatibility; no evidence or research rows are removed.
create or replace function public.verdict_workflow_api(p_op text,p_session_hash text default '',p_args jsonb default '{}'::jsonb)
returns jsonb language plpgsql security invoker set search_path=pg_catalog,verdict_saas as $$
declare actor uuid; c cases; w workflows; token uuid; sess text; enabled boolean; queued integer;
begin
 if p_op='queue_recovery' then
  -- One bounded upgrade pass for enabled, previously blocked BCCRT references.
  -- Lock case before workflow, as the source/audit transaction does.
  with eligible as (
   select c0.id from cases c0 join workflows w0 on w0.case_id=c0.id
   where w0.state in ('partial','failed') and coalesce((c0.body->>'automatic_investigation')::boolean,false)
    and coalesce((w0.progress->>'recovery_version')::integer,0)<3
    and coalesce((w0.progress->>'recovery_scheduled_version')::integer,0)<3
    and exists(select 1 from jsonb_each(coalesce(w0.progress->'references','{}'::jsonb)) ref
      where ref.key ~ '^https://(www\.)?canlii\.org/[a-z]{2}/bc/bccrt/doc/20[0-9]{2}/20[0-9]{2}bccrt[1-9][0-9]*/'
       and ref.value->>'status'='unavailable' and coalesce(ref.value->>'detail','') not like '%HTTP 429%')
    and (coalesce((w0.progress->>'recovery_version')::integer,0)<2 or exists(
     select 1 from jsonb_each(coalesce(w0.progress->'recoveries','{}')) rr
     cross join lateral jsonb_array_elements(coalesce(rr.value->'candidates','[]')) candidate
     where rr.value->>'status'='unavailable' and coalesce((rr.value->>'version')::integer,0)<3
      and candidate->>'draft_id' is not null
      and candidate->'identity_check'->>'reason'='The preserved header has no explicit indexed case name and neutral citation.'))
   order by w0.updated_at limit 5 for update of c0,w0 skip locked
  )
  update workflows set state='queued',stage='queued',generation=generation+1,attempts=0,
   progress=progress||jsonb_build_object('required_worker_version',3,'recovery_scheduled_version',3),
   detail='Checking the original publisher for a previously unavailable public decision.',updated_at=now()
   where case_id in (select id from eligible);
  get diagnostics queued=row_count;
  return jsonb_build_object('queued',queued);
 end if;
 if p_op='claim' then
  select w0.* into w from cases c0 join workflows w0 on w0.case_id=c0.id
   where (w0.state='queued' or (w0.state='running' and w0.lease_until<now()))
    and (w0.next_attempt_at is null or w0.next_attempt_at<=now())
    and coalesce((w0.progress->>'required_worker_version')::integer,1)<=coalesce((p_args->>'worker_version')::integer,1)
   order by w0.updated_at for update of c0,w0 skip locked limit 1;
  if not found then return 'null'::jsonb; end if;
  if w.session_hash is not null then delete from sessions where hash=w.session_hash; end if;
  if w.analysis_job_id is not null then
   update jobs set state='failed',error='Automatic worker lease expired; source records retained' where id=w.analysis_job_id and state='running';
   update cases set active_job=null where id=w.case_id and active_job=w.analysis_job_id;
  end if;
  if w.attempts>=3 then
   update workflows set state='failed',stage='interrupted',detail='Automatic work was interrupted repeatedly. Saved evidence is intact; retry when ready.',updated_at=now() where case_id=w.case_id;
   return 'null'::jsonb;
  end if;
  select * into c from cases where id=w.case_id;
  if coalesce((c.body->>'automatic_investigation')::boolean,true)=false then
   update workflows set state='paused',stage='paused',updated_at=now() where case_id=w.case_id;
   return 'null'::jsonb;
  end if;
  -- Do not compete with a human-requested investigation.
  if c.active_job is not null and exists(select 1 from jobs where id=c.active_job and state='running' and expires>now()) then
   update workflows set updated_at=now() where case_id=w.case_id;
   return 'null'::jsonb;
  end if;
  token:=gen_random_uuid(); sess:=encode(sha256(convert_to(gen_random_uuid()::text||gen_random_uuid()::text,'UTF8')),'hex');
  insert into sessions(hash,owner_id,expires) values(sess,w.owner_id,now()+interval '15 minutes');
  update workflows set state='running',stage='finding_references',detail='',attempts=attempts+1,
   lease_token=token,lease_until=now()+interval '120 seconds',session_hash=sess,analysis_job_id=null,updated_at=now()
   where case_id=w.case_id returning * into w;
  return jsonb_build_object('case_id',w.case_id,'owner_id',w.owner_id,'attempts',w.attempts,'generation',w.generation,'lease_token',token,'session_hash',sess,'progress',w.progress);
 end if;
 if p_op in ('heartbeat','finish','release','reschedule') then
  -- Keep the same case-before-workflow lock order as the transactional outbox.
  perform 1 from cases where id=p_args->>'case_id' for update;
  select * into w from workflows where case_id=p_args->>'case_id' and lease_token=(p_args->>'lease_token')::uuid and state='running' for update;
  if not found or w.lease_until<=now() then raise exception 'verdict:stale_job'; end if;
  if p_op='reschedule' then
   delete from sessions where hash=w.session_hash;
   update jobs set state='failed',error='Temporary interruption; retained completed work' where id=w.analysis_job_id and state='running';
   update cases set active_job=null where id=w.case_id and active_job=w.analysis_job_id;
   update workflows set state=case when attempts>=3 then 'failed' else 'queued' end,
    stage=case when attempts>=3 then 'needs_attention' else 'retry_wait' end,
    detail=case when attempts>=3 then 'Automatic attempts stopped. Saved evidence is safe; review the remaining limitation.' else 'Temporary interruption. Completed work is retained and another attempt is scheduled.' end,
    next_attempt_at=case when attempts>=3 then null else now()+make_interval(secs=>least(3600,greatest(30,coalesce((p_args->>'delay_seconds')::integer,60)))) end,
    progress=coalesce(p_args->'progress',progress)||jsonb_build_object('required_worker_version',5,'recovery_attempts',attempts),
    lease_token=null,lease_until=null,session_hash=null,analysis_job_id=null,updated_at=now() where case_id=w.case_id;
   return jsonb_build_object('ok',true);
  end if;
  if p_op='heartbeat' then
   if octet_length(coalesce(p_args->'progress',w.progress)::text)>24000 then raise exception 'verdict:invalid_revision'; end if;
   update workflows set lease_until=now()+interval '120 seconds',stage=coalesce(p_args->>'stage',stage),
    progress=coalesce(p_args->'progress',progress),analysis_job_id=coalesce((p_args->>'analysis_job_id')::uuid,analysis_job_id),updated_at=now() where case_id=w.case_id;
   return jsonb_build_object('ok',true,'generation',w.generation);
  end if;
  delete from sessions where hash=w.session_hash;
  if p_op='release' then
   update jobs set state='failed',error='Worker stopped before completion' where id=w.analysis_job_id and state='running';
   update cases set active_job=null where id=w.case_id and active_job=w.analysis_job_id;
   update workflows set state='queued',stage='queued',lease_token=null,lease_until=null,session_hash=null,updated_at=now() where case_id=w.case_id;
  else
   if p_args->>'state' not in ('completed','partial','failed') then raise exception 'verdict:invalid_revision'; end if;
   update workflows set state=case when generation>(p_args->>'generation')::integer then 'queued' else p_args->>'state' end,
    stage=case when generation>(p_args->>'generation')::integer then 'queued' else coalesce(p_args->>'stage','complete') end,
    completed_generation=(p_args->>'generation')::integer,detail=left(coalesce(p_args->>'detail',''),500),
    lease_token=null,lease_until=null,session_hash=null,analysis_job_id=null,updated_at=now() where case_id=w.case_id;
  end if;
  return jsonb_build_object('ok',true);
 end if;
 select owner_id into actor from sessions where hash=p_session_hash and expires>now();
 if actor is null then raise exception 'verdict:unauthorized'; end if;
 perform set_config('verdict_saas.actor',actor::text,true);
 execute 'set local role verdict_saas_executor';
 select * into c from cases where id=p_args->>'case_id';
 if not found then raise exception 'verdict:not_found'; end if;
 enabled:=coalesce((c.body->>'automatic_investigation')::boolean,true);
 if p_op='status' then
  select * into w from workflows where case_id=c.id;
  if not found then return jsonb_build_object('enabled',enabled,'state','idle','stage','waiting_for_evidence','progress','{}'::jsonb); end if;
  return jsonb_build_object('enabled',enabled,'state',w.state,'stage',w.stage,'detail',w.detail,'generation',w.generation,
   'retry_at',w.next_attempt_at,'attempts',w.attempts,'completed_generation',w.completed_generation,'updated_at',w.updated_at,'progress',w.progress);
 elsif p_op='retry' then
  if not enabled or jsonb_array_length(c.body->'evidence')=0 then raise exception 'verdict:invalid_revision'; end if;
  insert into workflows(case_id,owner_id) values(c.id,actor)
   on conflict(case_id) do update set generation=workflows.generation+1,
   state=case when workflows.state='running' then 'running' else 'queued' end,attempts=0,detail='',updated_at=now();
  return jsonb_build_object('ok',true);
 elsif p_op='pause' then
  update workflows set state='paused',stage='paused',lease_token=null,lease_until=null,updated_at=now() where case_id=c.id;
  return jsonb_build_object('ok',true);
 end if;
 raise exception 'verdict:unsupported_operation';
end $$;
revoke all on function public.verdict_workflow_api(text,text,jsonb) from public,anon,authenticated;
grant execute on function public.verdict_workflow_api(text,text,jsonb) to service_role;


-- New evidence or explicit retry cancels an obsolete cooldown, without touching sources.
create function verdict_saas.reset_workflow_cooldown() returns trigger language plpgsql security invoker set search_path=pg_catalog,verdict_saas as $$
begin
 if new.generation<>old.generation then new.next_attempt_at:=null; end if;return new;
end $$;
revoke all on function verdict_saas.reset_workflow_cooldown() from public,anon,authenticated;
create trigger reset_workflow_cooldown before update on verdict_saas.workflows for each row execute function verdict_saas.reset_workflow_cooldown();

-- Extend the existing fixed-provider quota check to inherited, explicit account consent.
create or replace function public.verdict_location_api(p_op text,p_session_hash text default '',p_args jsonb default '{}'::jsonb)
returns jsonb language plpgsql security invoker set search_path=pg_catalog,verdict_saas as $$
declare actor uuid; slot timestamptz; n integer; account_key text; global_key text;
begin
 select owner_id into actor from sessions where hash=p_session_hash and expires>now();
 if actor is null then raise exception 'verdict:unauthorized'; end if;
 if not exists(select 1 from cases where id=p_args->>'case_id' and owner_id=actor) then raise exception 'verdict:not_found'; end if;
 if not exists(select 1 from cases where id=p_args->>'case_id' and owner_id=actor and (case when coalesce(body->'location_authorization'->>'mode','account')='account' then coalesce((select mode from preferences where owner_id=actor),'off') else body->'location_authorization'->>'mode' end) in ('area_only','address')) then raise exception 'verdict:forbidden'; end if;
 if p_op<>'slot' then raise exception 'verdict:not_found'; end if;
 perform pg_advisory_xact_lock(hashtextextended('verdict:photon:global',0));
 account_key:='location:account:'||actor::text||':'||current_date::text;
 global_key:='location:global:'||current_date::text;
 if coalesce((select attempts from rate_limits where key=account_key),0)>=20
 or coalesce((select attempts from rate_limits where key=global_key),0)>=120 then
  return jsonb_build_object('allowed',false,'wait_seconds',0);
 end if;
 select greatest(next_at,clock_timestamp()) into slot from model_slots where model='photon-geocoder';
 slot:=coalesce(slot,clock_timestamp());
 if slot>clock_timestamp()+interval '30 seconds' then return jsonb_build_object('allowed',false,'wait_seconds',0); end if;
 insert into model_slots(model,next_at) values('photon-geocoder',slot+interval '1.25 seconds')
 on conflict(model) do update set next_at=excluded.next_at;
 insert into rate_limits(key,attempts,expires) values(account_key,1,now()+interval '2 days')
 on conflict(key) do update set attempts=rate_limits.attempts+1;
 insert into rate_limits(key,attempts,expires) values(global_key,1,now()+interval '2 days')
 on conflict(key) do update set attempts=rate_limits.attempts+1;
 return jsonb_build_object('allowed',true,'wait_seconds',greatest(0,extract(epoch from slot-clock_timestamp())));
end $$;
revoke all on function public.verdict_location_api(text,text,jsonb) from public,anon,authenticated;
grant execute on function public.verdict_location_api(text,text,jsonb) to service_role;

