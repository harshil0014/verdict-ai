-- Global public-geocoder pacing and hard free quotas. Case records themselves
-- use existing private cases/originals/audit ownership RLS; no public cache.
create function public.verdict_location_api(p_op text,p_session_hash text default '',p_args jsonb default '{}'::jsonb)
returns jsonb language plpgsql security invoker set search_path=pg_catalog,verdict_saas as $$
declare actor uuid; slot timestamptz; n integer; account_key text; global_key text;
begin
 select owner_id into actor from sessions where hash=p_session_hash and expires>now();
 if actor is null then raise exception 'verdict:unauthorized'; end if;
 if not exists(select 1 from cases where id=p_args->>'case_id' and owner_id=actor) then raise exception 'verdict:not_found'; end if;
 if not exists(select 1 from cases where id=p_args->>'case_id' and owner_id=actor and body->'location_authorization'->>'mode' in ('area_only','address')) then raise exception 'verdict:forbidden'; end if;
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

-- A settings-only requeue must also carry the application's required version,
-- so an older retained worker cannot consume a location-enabled job.
create function verdict_saas.location_workflow_version() returns trigger
language plpgsql security invoker set search_path=pg_catalog,verdict_saas as $$
begin
 if new.body->'location_authorization' is distinct from old.body->'location_authorization' then
  update workflows set progress=progress||jsonb_build_object('required_worker_version',greatest(4,coalesce((new.body->>'automatic_workflow_version')::integer,4))) where case_id=new.id;
 end if;
 return new;
end $$;
revoke all on function verdict_saas.location_workflow_version() from public,anon,authenticated;
create trigger location_worker_compatibility after update of body on verdict_saas.cases
 for each row execute function verdict_saas.location_workflow_version();
