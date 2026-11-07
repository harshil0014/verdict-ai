import React, {useEffect,useRef,useState} from 'react';
import {AlertTriangle,ArrowRight,FileText,Globe,LoaderCircle,ShieldCheck,X,Search} from 'lucide-react';
import {evidenceDiscoveries,researchActivity,safeSourceUrl} from './research-records';
import './research.css';

type API=(path:string,method?:string,body?:any)=>Promise<any>;
type Props={caseId:string;revision:number;activityVersion?:string;api:API;changed:()=>Promise<void>};
const date=(v:any)=>v?new Date(v).toLocaleString():'Not established';
const label=(v:string)=>v.replaceAll('_',' ');

function SourceLink({url}:{url:any}) {
  const href=safeSourceUrl(url);
  return href?<a className="research-url" href={href} target="_blank" rel="noreferrer">{url} ↗</a>:null;
}

function useRecords({caseId,revision,activityVersion,api}:Props) {
  const [records,setRecords]=useState<any[]>([]),[error,setError]=useState('');
  useEffect(()=>{let active=true;setError('');(async()=>{try{const rows=await api(`/cases/${caseId}/research`);if(active)setRecords(rows);}catch(e:any){if(active)setError(e.message);}})();return()=>{active=false;};},[caseId,revision,activityVersion]);
  return {records,error};
}

export function DiscoveryRecords({records,evidenceIds,onInspect}:{records:any[];evidenceIds:string[];onInspect:(r:any)=>void}) {
  const rows=evidenceDiscoveries(records,evidenceIds);
  if(!rows.length)return null;
  return <section className="evidence-discoveries"><div className="section-heading"><h4>Other discoveries</h4><span>{rows.length} retained records</span></div>
    <p className="fine">Earlier staged or dismissed documents remain available here. They are separate from the sources already in your investigation.</p>
    <div className="research-results">{rows.map(d=><article className="research-card" key={d.id}>
      <span className="pill">{d.source_id?'Preserved':d.status==='ready'?'Not yet in investigation':label(d.status)}</span>
      <h4>{d.title}</h4><SourceLink url={d.metadata?.final_url||d.url}/>
      <p>{d.relevance}</p><SourceIntegrity metadata={d.metadata} rawHash={d.raw_sha256}/>
      <button className="secondary small" onClick={()=>onInspect(d)}><FileText size={14}/> Inspect retained source</button>
    </article>)}</div></section>;
}

export function SourceIntegrity({metadata,rawHash}:{metadata:any;rawHash?:string}) {
  return <div className="source-integrity"><span>Origin unverified · {metadata?.review_status==='human_reviewed'?'Human reviewed':metadata?.review_status==='unreviewed'?'Not human reviewed':'Review not recorded'}</span>
    <span>Retrieved: {date(metadata?.retrieved_at)}</span><span>Publication: {metadata?.publication_date||'Unknown — not inferred'}</span>
    {rawHash&&<details><summary>Integrity hashes</summary><strong>Original SHA-256</strong><code>{rawHash}</code>
      {metadata?.text_sha256&&<><strong>Extracted text SHA-256</strong><code>{metadata.text_sha256}</code></>}</details>}
    <small>Retrieval does not establish historical policy applicability.</small>
  </div>;
}

export function PublicSourceFacts({source}:{source:any}) {
  const p=source.provenance;
  if(!p)return null;
  return <div className="evidence-source-facts"><strong>{p.acquisition_mode==='embedded_reference'?'Automatically discovered source':'Preserved public source'}</strong>
    <SourceLink url={p.requested_url||p.final_url}/>
    {p.final_url&&p.final_url!==p.requested_url&&<><small>Retrieved from</small><SourceLink url={p.final_url}/></>}
    <SourceIntegrity metadata={p} rawHash={source.sha256}/>
  </div>;
}

export function EvidenceDiscoveries(props:Props&{evidenceIds:string[]}) {
  const {records,error}=useRecords(props),[selected,setSelected]=useState<any>(null),[busy,setBusy]=useState(false),[actionError,setActionError]=useState('');
  const dialog=useRef<HTMLElement>(null);
  useEffect(()=>{if(!selected)return;const previous=document.activeElement as HTMLElement|null;dialog.current?.focus();return()=>{previous?.focus();};},[selected]);
  async function collect(form:HTMLFormElement) {
    const f=new FormData(form);setBusy(true);setActionError('');
    try{await props.api(`/cases/${props.caseId}/research/${selected.id}/approve`,'POST',{consent:true,snapshot_sha256:selected.raw_sha256,source_kind:String(f.get('kind')),historical_note:String(f.get('note')||'')});setSelected(null);await props.changed();}
    catch(e:any){setActionError(e.message);}finally{setBusy(false);}
  }
  return <>{error&&<p className="research-error" role="alert">Could not load retained discoveries: {error}</p>}
    <DiscoveryRecords records={records} evidenceIds={props.evidenceIds} onInspect={setSelected}/>
    {selected&&<div className="research-overlay" onClick={()=>setSelected(null)}><section ref={dialog} tabIndex={-1} className="research-review" role="dialog" aria-modal="true" aria-label="Retained evidence source" onClick={e=>e.stopPropagation()} onKeyDown={e=>{if(e.key==='Escape'){e.stopPropagation();setSelected(null);}}}>
      <button className="close" aria-label="Close retained source" onClick={()=>setSelected(null)}><X/></button>
      <span className="eyebrow">PRESERVED SOURCE RECORD</span><h2>{selected.title}</h2><SourceLink url={selected.metadata?.final_url||selected.url}/>
      <SourceIntegrity metadata={selected.metadata} rawHash={selected.raw_sha256}/>
      <p className="research-limit"><ShieldCheck size={15}/> Collection and integrity hashes do not verify factual truth or a past policy.</p>
      {selected.text&&<pre>{selected.text}</pre>}<ProviderReport data={selected.google}/>
      {selected.status==='ready'&&!selected.source_id&&<form onSubmit={e=>{e.preventDefault();collect(e.currentTarget);}}>
        <label>Document type<select name="kind"><option value="reported_document">Reported / unclassified document</option><option value="tribunal_decision">Published tribunal or court decision</option><option value="current_policy">Current policy — past applicability unestablished</option>{selected.metadata?.archive_capture_requested&&<option value="archived_record">Archived capture</option>}</select></label>
        <label>Historical context or limitations<textarea name="note" maxLength={1000} rows={2}/></label>
        <p className="fine">Use the exact preserved snapshot in your case only if you have permission to retain it. This will update the investigation automatically.</p>
        <button className="primary" disabled={busy}>Use this preserved source</button>
      </form>}{selected.status==='dismissed'&&<p className="fine">Previously dismissed. Its retained text and integrity metadata remain inspectable.</p>}
      {actionError&&<p className="research-error" role="alert">{actionError}</p>}
    </section></div>}
  </>;
}

export function ActivityRecords({records}:{records:any[]}) {
  const rows=researchActivity(records);
  if(!rows.length)return null;
  return <details className="retrieval-history"><summary>Source retrieval & discovery history · {rows.length}</summary>
    <p className="fine">Provider reports and failed attempts are retained here. A failed retrieval never becomes source evidence.</p>
    {rows.map(d=><article className="research-card" key={d.id}><div className="research-card-top"><strong>{d.title}</strong><small>{date(d.metadata?.retrieved_at||d.created_at)}</small></div>
      <SourceLink url={d.url}/>{d.failure_message&&<p className="research-error"><AlertTriangle size={14}/>{d.failure_message}</p>}
      <ProviderReport data={d.google}/>
    </article>)}
  </details>;
}

export function ResearchActivity(props:Props) {
  const {records,error}=useRecords(props);
  return <>{error&&<p className="research-error" role="alert">Could not load retrieval history: {error}</p>}<ActivityRecords records={records}/></>;
}

export function FindEvidence({caseId,api,suggestions,completed}:{caseId:string;api:API;suggestions:any[];completed:()=>Promise<void>}) {
  const [mode,setMode]=useState('url'),[query,setQuery]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[config,setConfig]=useState<any>(null);
  useEffect(()=>{let active=true;api('/research/config').then(c=>{if(active)setConfig(c);}).catch(()=>{});return()=>{active=false;};},[api]);
  async function submit(form:HTMLFormElement) {
    const f=new FormData(form);setBusy(true);setError('');
    try{const result=await api(`/cases/${caseId}/research/${mode==='url'?'url':'search'}`,'POST',{
      ...(mode==='url'?{url:String(f.get('url'))}:{query}),consent:true,event_date:f.get('event_date')||null,
      google_context:f.get('google')==='on'});
      if(mode==='url'&&result.status==='unavailable'){setError(result.failure_message||'This page could not be retrieved. The failed attempt is saved in Investigation and Timeline.');return;}
      await completed();
    }catch(e:any){setError(e.message);}finally{setBusy(false);}
  }
  return <><span className="eyebrow">OPTIONAL EVIDENCE ACQUISITION</span><h2>Find more evidence.</h2>
    <p>VERDICT already follows safe public links in submitted evidence. Add another source or ask a public question when something is still missing.</p>
    <div className="find-evidence-modes" role="group" aria-label="Evidence discovery method"><button type="button" aria-pressed={mode==='url'} onClick={()=>{setMode('url');setError('');}}><Globe size={15}/> Enter a URL</button><button type="button" aria-pressed={mode==='search'} onClick={()=>{setMode('search');setError('');}}><Search size={15}/> Search the web</button></div>
    <form onSubmit={e=>{e.preventDefault();submit(e.currentTarget);}}>
      {mode==='url'?<label>Public webpage or PDF URL<input name="url" type="url" required maxLength={2048} placeholder="https://…"/></label>:<>
        <label>Public evidence to look for<textarea value={query} onChange={e=>setQuery(e.target.value)} minLength={8} maxLength={600} rows={3} required placeholder="Find an official policy or published decision…"/></label>
        {suggestions.length>0&&<div className="research-suggestions"><span>Suggested missing public evidence</span>{suggestions.slice(0,3).map(s=><button type="button" key={s.id} onClick={()=>setQuery((s.public_research_query||`Find public primary documents relevant to: ${s.title}`).slice(0,600))}>{s.title}<ArrowRight size={12}/></button>)}</div>}
      </>}
      <details className="find-evidence-options"><summary>Dates & optional URL Context</summary><label>Relevant event date<input type="date" name="event_date"/></label><label className="research-check"><input type="checkbox" name="google"/> Also authorize Google URL Context for these public URLs. Its answer is a lead, not source text.</label></details>
      <p className="fine">Submitting authorizes public retrieval, preservation and investigation. Only use sources you may retain. Search questions go to public search providers: include no customer, account or transaction identifiers.</p>
      {mode==='search'&&config&&<p className="fine">{config.free_search_notice}</p>}
      <button className="primary" disabled={busy}>{busy?<LoaderCircle size={16} className="spin"/>:mode==='url'?<Globe size={16}/>:<Search size={16}/>} {busy?'Finding evidence…':mode==='url'?'Add & investigate':'Find & investigate'}</button>
    </form>{error&&<p className="research-error" role="alert">{error}</p>}
  </>;
}

function ProviderReport({data}:{data:any}) {
  if(!data)return null;
  return <details className="google-report"><summary>{data.provider||'Google URL Context'} · {data.status}</summary><p>{data.summary}</p>
    {data.url_context_metadata?.map((m:any,i:number)=><p className="fine" key={i}>Retrieval: {m.status} · {m.url}</p>)}
    {data.provider_attempts?.map((p:any,i:number)=><p className="fine" key={i}>{p.provider}: {p.status}{p.retry_after_seconds?` · retry after ${p.retry_after_seconds}s`:''}</p>)}
    {data.documents?.map((d:any)=><div key={d.url}><strong>{d.title}</strong><SourceLink url={d.url}/></div>)}
    {data.search_entry_point&&<iframe title="Google Search suggestions" sandbox="allow-popups allow-popups-to-escape-sandbox" srcDoc={data.search_entry_point}/>}
    <p className="fine">Search summaries and snippets are leads, not original source passages.</p>
  </details>;
}
