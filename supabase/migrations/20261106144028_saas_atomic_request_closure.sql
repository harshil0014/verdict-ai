create or replace function verdict_saas.commit_case(actor uuid, args jsonb, creating boolean default false)
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
    select * into r from requests where case_id=c.id and case when args->>'request_action'='close' then body->>'id'=args->>'request_id' else hash=args->>'request_hash' end for update;
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

