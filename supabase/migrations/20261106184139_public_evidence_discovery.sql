-- Research proposals remain private and separate from official evidence.
create table verdict_saas.research (
 id text primary key, case_id text not null references verdict_saas.cases(id),
 owner_id uuid not null references verdict_saas.accounts(id),
 body jsonb not null, content bytea, source_id text,
 created_at timestamptz not null default now()
);
create unique index research_snapshot_unique on verdict_saas.research(case_id,(body->>'url'),(body->>'raw_sha256'));
create index research_owner_case on verdict_saas.research(owner_id,case_id);
alter table verdict_saas.research enable row level security;
alter table verdict_saas.research force row level security;
revoke all on verdict_saas.research from public,anon,authenticated;
grant select,insert,update on verdict_saas.research to service_role,verdict_saas_executor;
create policy owner_isolation on verdict_saas.research to verdict_saas_executor
 using(owner_id::text=current_setting('verdict_saas.actor',true))
 with check(owner_id::text=current_setting('verdict_saas.actor',true));

create function public.verdict_research_api(p_op text,p_session_hash text default '',p_args jsonb default '{}'::jsonb)
returns jsonb language plpgsql security invoker set search_path=pg_catalog,verdict_saas as $$
declare actor uuid; c cases; r research; b jsonb:=p_args->'body'; raw bytea; size bigint; used bigint; result jsonb; e jsonb;
begin
 select owner_id into actor from sessions where hash=p_session_hash and expires>now();
 if actor is null then raise exception 'verdict:unauthorized'; end if;
 perform set_config('verdict_saas.actor',actor::text,true);
 execute 'set local role verdict_saas_executor';
 select * into c from cases where id=p_args->>'case_id';
 if not found then raise exception 'verdict:not_found'; end if;
 if p_op='list' then
  return coalesce((select jsonb_agg(body||jsonb_build_object('source_id',source_id) order by created_at desc) from research where case_id=c.id),'[]'::jsonb);
 end if;
 if p_op='stage' then
  perform pg_advisory_xact_lock(hashtextextended(actor::text,0));
  select * into r from research where case_id=c.id and body->>'url'=b->>'url' and body->>'raw_sha256'=b->>'raw_sha256';
  if found then return r.body||jsonb_build_object('duplicate',true,'source_id',r.source_id); end if;
  if (select count(*) from research where case_id=c.id)>=40 then raise exception 'verdict:research_limit'; end if;
  if octet_length(b::text)>160000 then raise exception 'verdict:research_limit'; end if;
  if p_args->>'content' is not null then
   raw:=decode(p_args->>'content','base64');
   if octet_length(raw)>5242880 or encode(sha256(raw),'hex') is distinct from b->>'raw_sha256'
     or encode(sha256(convert_to(b->>'text','UTF8')),'hex') is distinct from b->'metadata'->>'text_sha256'
     then raise exception 'verdict:invalid_file'; end if;
  end if;
  if (select coalesce(sum(octet_length(content)),0) from research)+coalesce(octet_length(raw),0)>20971520 then raise exception 'verdict:research_storage_limit'; end if;
  size:=coalesce(octet_length(raw),0)+octet_length(b::text);
  select bytes_used into used from quota where id=1 for update;
  if used+size>209715200 then raise exception 'verdict:service_storage_limit'; end if;
  insert into research(id,case_id,owner_id,body,content) values(b->>'id',c.id,actor,b,raw);
  update quota set bytes_used=bytes_used+size where id=1;
  return b;
 end if;
 select * into r from research where id=p_args->>'id' and case_id=c.id for update;
 if not found then raise exception 'verdict:not_found'; end if;
 if p_op='get' then return r.body||jsonb_build_object('source_id',r.source_id,'content',encode(r.content,'base64')); end if;
 if p_op='dismiss' then
  if r.source_id is not null then raise exception 'verdict:research_closed'; end if;
  update quota set bytes_used=bytes_used-coalesce(octet_length(r.content),0) where id=1;
  update research set content=null,body=jsonb_set(body,'{status}','"dismissed"') where id=r.id;
  return jsonb_build_object('ok',true);
 end if;
 if p_op='approve' then
  if r.source_id is not null then return jsonb_build_object('case',c.body,'duplicate',true); end if;
  if r.body->>'status'<>'ready' or r.content is null then raise exception 'verdict:research_closed'; end if;
  e:=p_args->'mutation'->'body'->'evidence'->-1;
  if e->>'text' is distinct from r.body->>'text' or e->>'sha256' is distinct from r.body->>'raw_sha256'
     or e->'provenance'->>'text_sha256' is distinct from r.body->'metadata'->>'text_sha256'
     or e->'provenance'->>'final_url' is distinct from r.body->'metadata'->>'final_url'
     or p_args->'mutation'->'file'->>'sha256' is distinct from r.body->>'raw_sha256'
     or decode(p_args->'mutation'->'file'->>'content','base64') is distinct from r.content
     then raise exception 'verdict:invalid_file'; end if;
  result:=commit_case(actor,p_args->'mutation',false);
  update quota set bytes_used=bytes_used-octet_length(r.content) where id=1;
  update research set source_id=e->>'id',content=null,body=jsonb_set(body,'{status}','"approved"') where id=r.id;
  return jsonb_build_object('case',result,'duplicate',false);
 end if;
 raise exception 'verdict:unsupported_operation';
end $$;
revoke all on function public.verdict_research_api(text,text,jsonb) from public,anon,authenticated;
grant execute on function public.verdict_research_api(text,text,jsonb) to service_role;
