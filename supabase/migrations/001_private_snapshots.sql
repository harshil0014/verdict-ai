-- Only server-side service-role credentials may access this table.
-- No browser/anonymous/authenticated grants or permissive RLS policies.
begin;
create table if not exists public.verdict_snapshots (
  case_id text primary key,
  tenant text not null,
  revision integer not null check (revision > 0),
  body jsonb not null,
  audit jsonb not null default '[]'::jsonb,
  snapshot_sha256 text not null,
  updated_at timestamptz not null default now()
);
alter table public.verdict_snapshots enable row level security;
alter table public.verdict_snapshots force row level security;
revoke all on table public.verdict_snapshots from public, anon, authenticated;
grant select, insert, update on table public.verdict_snapshots to service_role;
commit;
-- Verify configuration without returning case contents.
select c.relname,c.relrowsecurity,c.relforcerowsecurity,
  has_table_privilege('anon','public.verdict_snapshots','select') as anon_can_select,
  has_table_privilege('authenticated','public.verdict_snapshots','select') as authenticated_can_select
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname='public' and c.relname='verdict_snapshots';
