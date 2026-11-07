export function safeSourceUrl(value:unknown):string|undefined {
  if(typeof value!=='string')return;
  try { const u=new URL(value);if(['http:','https:'].includes(u.protocol)&&!u.username&&!u.password)return value; } catch {}
}

// Display partitions only. The original records and API payloads are untouched.
export function evidenceDiscoveries(records:any[],evidenceIds:string[]) {
  const preserved=new Set(evidenceIds);
  return records.filter(r=>r.status!=='research_report'&&r.status!=='unavailable'&&!preserved.has(r.source_id));
}
export function researchActivity(records:any[]) {
  return records.filter(r=>r.status==='research_report'||r.status==='unavailable'||r.google);
}
