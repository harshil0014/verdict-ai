-- A setup-generated event-trigger helper is not a public application RPC.
-- Keep its owner/event-trigger behavior; remove unnecessary API role execution.
-- Optional because fresh projects may not install this helper at all.
do $migration$
begin
  if to_regprocedure('public.rls_auto_enable()') is not null then
    revoke execute on function public.rls_auto_enable() from public, anon, authenticated;
  end if;
end
$migration$;
