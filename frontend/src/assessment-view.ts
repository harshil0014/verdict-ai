const normalized=(text:string='')=>text.toLowerCase().replace(/[^\p{L}\p{N}]+/gu,' ').trim();

export function visibleClaims(claims:any[]=[]){
  const seen=new Set<string>();
  return [...claims].sort((a,b)=>Number(b.semantic_support==='entailed')-Number(a.semantic_support==='entailed')).filter(c=>{
    const text=c.text||'',key=normalized(text);
    // Old malformed assessments stay in the audit record, not as paragraphs
    // repeated throughout the overview and graph while reassessment runs.
    if(!key||text.length>240||text.split(/\s+/).length>48||seen.has(key))return false;
    seen.add(key);return true;
  });
}
export function graphClaims(claims:any[]=[]){
  const kept=visibleClaims(claims).map(c=>({...c,additional_citations:[...(c.additional_citations||[])]})),aliases=new Map<string,string>();
  for(const c of claims){const match=kept.find(x=>normalized(x.text)===normalized(c.text));if(match){aliases.set(c.id,match.id);if(c.source_id!==match.source_id&&!match.additional_citations.some((p:any)=>p.source_id===c.source_id))match.additional_citations.push(c);}}
  return {claims:kept,aliases};
}
export function requestPurpose(r:any){
  const text=((r.title||'')+' '+(r.question||'')).toLowerCase();
  if(/address|destination/.test(text)&&/original|checkout|time of (?:purchase|order)|captured/.test(text))return 'original_checkout_address';
  if(/proof of delivery|delivery confirmation|delivery receipt|delivery or service fulfillment/.test(text))return 'delivery_proof';
  return null;
}
export function requestState(current:any,w:any){
  const prepared=current.analysis?.acquisition_plan?.find((p:any)=>p.suggestion_id===w?.id);
  if(prepared&&prepared.state!=='prepared')return prepared.state;
  const follow=(current.requests||[]).find((r:any)=>r.id===w?.follow_up_to);
  if(follow?.status==='received'&&(w?.unresolved_defect||'').trim().length>=20&&w.question?.trim()!==follow.question?.trim())return 'prepared';
  const ids=(r:any)=>new Set<string>((r.question||'').match(/\b(?:order|transaction|capture)\s+([a-zA-Z0-9-]{6,})/gi)?.map((v:string)=>v.split(/\s+/).pop()!.toLowerCase()).filter((v:string)=>/\d/.test(v))||[]);
  const prior=[...(current.requests||[])].reverse().find((r:any)=>{
    if(r.recipient!==w?.recipient)return false;
    if(normalized(r.question)===normalized(w?.question))return true;
    const a=ids(r),b=ids(w);if(a.size&&b.size&&![...a].some(v=>b.has(v)))return false;
    return requestPurpose(r)&&requestPurpose(r)===requestPurpose(w||{});
  });
  return prior?.status||'prepared';
}
export function nextRequest(current:any){
  const list=[...(current.analysis?.requests||[])].sort((a:any,b:any)=>(a.priority==='first'?-1:0)-(b.priority==='first'?-1:0));
  return list.find(w=>requestState(current,w)==='prepared')||list.find(w=>['open','link_ready'].includes(requestState(current,w)));
}
