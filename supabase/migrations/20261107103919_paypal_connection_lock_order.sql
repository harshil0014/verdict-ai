create or replace function public.verdict_paypal_api(p_op text,p_session_hash text default '',p_args jsonb default '{}'::jsonb)
returns jsonb language plpgsql security invoker set search_path=pg_catalog,verdict_saas as $$
declare actor uuid; conn paypal_connections; imported paypal_imports; c cases; result jsonb; item jsonb;
 raw bytea; added bigint:=0; used bigint; internal_session text;
begin
 -- Service-role administrative operations have no application HTTP route.
 if p_op='provision_demo' then
  if not exists(select 1 from accounts where id=(p_args->>'owner_id')::uuid) then raise exception 'verdict:not_found'; end if;
  insert into paypal_connections(owner_id,environment,merchant_id,credential_ref)
   values((p_args->>'owner_id')::uuid,'sandbox',p_args->>'merchant_id','operator_sandbox_demo') returning * into conn;
  return jsonb_build_object('id',conn.id,'owner_id',conn.owner_id,'merchant_id',conn.merchant_id);
 elsif p_op='revoke_demo' then
  update paypal_connections set active=false where id=(p_args->>'connection_id')::uuid;
  return jsonb_build_object('ok',true);
 elsif p_op='operator_context' then
  select * into conn from paypal_connections where id=(p_args->>'connection_id')::uuid and active;
  if not found then raise exception 'verdict:not_found'; end if;
  -- Non-browser, short-lived server context, like the existing workflow runner.
  internal_session:=encode(sha256(convert_to(gen_random_uuid()::text,'UTF8')),'hex');
  insert into sessions(hash,owner_id,expires) values(internal_session,conn.owner_id,now()+interval '10 minutes');
  return jsonb_build_object('session_hash',internal_session);
 elsif p_op='close_operator_context' then
  delete from sessions where hash=p_args->>'session_hash';return '{}'::jsonb;
 end if;
 select owner_id into actor from sessions where hash=p_session_hash and expires>now();
 if actor is null then raise exception 'verdict:unauthorized'; end if;
 perform set_config('verdict_saas.actor',actor::text,true);
 execute 'set local role verdict_saas_executor';
 -- Status updates take their row lock directly rather than upgrading SHARE.
 -- Commit holds a shared authorization lock until the case transaction ends.
 if p_op='commit_import' then
  select * into conn from paypal_connections where owner_id=actor and active for share;
 elsif p_op='status' then
  select * into conn from paypal_connections where owner_id=actor and active for update;
 else
  select * into conn from paypal_connections where owner_id=actor and active;
 end if;
 if p_op='connection' then
  if not found then return 'null'::jsonb; end if;
  return to_jsonb(conn)-'credential_ref';
 end if;
 if not found or conn.id is distinct from (p_args->>'connection_id')::uuid then raise exception 'verdict:not_found'; end if;
 if p_op='list_imports' then
  return coalesce((select jsonb_agg(jsonb_build_object('dispute_id',dispute_id,'case_id',case_id)) from paypal_imports where connection_id=conn.id),'[]'::jsonb);
 elsif p_op='status' then
  if p_args->>'status' not in ('healthy','provider_error') then raise exception 'verdict:invalid_revision'; end if;
  update paypal_connections set last_checked_at=now(),last_status=p_args->>'status',last_error=p_args->'diagnostic' where id=conn.id;
  return '{}'::jsonb;
 end if;
 select * into imported from paypal_imports where connection_id=conn.id and dispute_id=p_args->>'dispute_id';
 if p_op='get_import' then
  if not found then return 'null'::jsonb; end if;
  return jsonb_build_object('case_id',imported.case_id);
 elsif p_op='commit_import' then
  perform pg_advisory_xact_lock(hashtextextended(conn.id::text||':'||(p_args->>'dispute_id'),0));
  select * into imported from paypal_imports where connection_id=conn.id and dispute_id=p_args->>'dispute_id';
  if (p_args->>'creating')::boolean and found then raise exception 'verdict:stale_revision'; end if;
  if not (p_args->>'creating')::boolean and (not found or imported.case_id is distinct from p_args->'mutation'->>'case_id') then raise exception 'verdict:not_found'; end if;
  if p_args->'mutation'->'body'->>'mode'<>'paypal_sandbox_saas'
    or p_args->'mutation'->'body'->>'paypal_id' is distinct from p_args->>'dispute_id'
    or p_args->'mutation'->'body'->>'paypal_connection_id' is distinct from conn.id::text
    or p_args->'mutation'->'body'->'paypal_account'->>'merchant_id' is distinct from conn.merchant_id
    then raise exception 'verdict:invalid_revision'; end if;
  if jsonb_array_length(p_args->'snapshots') not between 1 and 21 then raise exception 'verdict:invalid_file'; end if;
  -- Validate and reserve original JSON space before the case/audit transaction.
  for item in select * from jsonb_array_elements(p_args->'snapshots') loop
   raw:=decode(item->>'content','base64');
   if octet_length(raw)>5242880 or encode(sha256(raw),'hex') is distinct from item->>'sha256'
    or item->>'kind' not in ('dispute','capture','order')
    or (convert_from(raw,'UTF8')::jsonb)->>(case when item->>'kind'='dispute' then 'dispute_id' else 'id' end) is distinct from item->>'record_id'
    or (item->>'kind'='dispute' and item->>'record_id' is distinct from p_args->>'dispute_id')
    then raise exception 'verdict:invalid_file'; end if;
   if not exists(select 1 from jsonb_array_elements(p_args->'mutation'->'body'->'evidence') e
     where e->>'origin'='paypal_sandbox_api' and e->>'provider_record_kind'=item->>'kind'
      and e->>'provider_record_id'=item->>'record_id'
      and e->'provider_provenance'->>'canonical_json_sha256'=item->>'sha256') then raise exception 'verdict:invalid_file'; end if;
   if not exists(select 1 from paypal_snapshots where connection_id=conn.id and kind=item->>'kind' and record_id=item->>'record_id' and sha256=item->>'sha256') then added:=added+octet_length(raw); end if;
  end loop;
  -- Follow commit_case's case-before-quota lock order. A later exception rolls
  -- back the case, audit, outbox and snapshots together.
  result:=commit_case(actor,p_args->'mutation',(p_args->>'creating')::boolean);
  if (select coalesce(sum(octet_length(content)),0) from paypal_snapshots where owner_id=actor)+added>20971520 then raise exception 'verdict:storage_limit'; end if;
  select bytes_used into used from quota where id=1 for update;
  if used+added>209715200 then raise exception 'verdict:service_storage_limit'; end if;
  update quota set bytes_used=bytes_used+added where id=1;
  if (p_args->>'creating')::boolean then
   insert into paypal_imports(connection_id,dispute_id,owner_id,case_id) values(conn.id,p_args->>'dispute_id',actor,result->>'id');
   if coalesce((result->>'automatic_investigation')::boolean,false) then
    insert into workflows(case_id,owner_id,progress) values(result->>'id',actor,jsonb_build_object('required_worker_version',coalesce((result->>'automatic_workflow_version')::integer,3)));
   end if;
  end if;
  for item in select * from jsonb_array_elements(p_args->'snapshots') loop
   insert into paypal_snapshots(connection_id,case_id,owner_id,kind,record_id,sha256,content)
    values(conn.id,result->>'id',actor,item->>'kind',item->>'record_id',item->>'sha256',decode(item->>'content','base64')) on conflict do nothing;
  end loop;
  return result;
 end if;
 raise exception 'verdict:unsupported_operation';
end $$;
revoke all on function public.verdict_paypal_api(text,text,jsonb) from public,anon,authenticated;
grant execute on function public.verdict_paypal_api(text,text,jsonb) to service_role;
