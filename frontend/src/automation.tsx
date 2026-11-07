import React from 'react';
import { LoaderCircle, ScanLine, AlertTriangle, CheckCircle2 } from 'lucide-react';

export function AutomaticInvestigation({current,api,changed}: {current:any;api:(path:string,method?:string,body?:any)=>Promise<any>;changed:()=>Promise<void>}) {
 const a=current.automation;
 const [busy,setBusy]=React.useState(false),[error,setError]=React.useState('');
 if(!a)return null;
 const active=['queued','running'].includes(a.state), failed=a.state==='failed';
 const labels:Record<string,string>={queued:'Evidence saved. Investigation queued.',finding_references:'Finding public references in your evidence…',retrieving_references:'Retrieving and preserving public sources…',investigating:'Investigating preserved evidence…',complete:'Investigation updated.',needs_attention:'Evidence saved. Automatic investigation needs attention.',paused:'Automatic investigation is paused.',waiting_for_evidence:'Add evidence to start your investigation.'};
 const rows=Object.entries(a.progress?.references||{}) as [string,any][];
 async function run(path:string,body?:any){setBusy(true);setError('');try{await api(`/cases/${current.id}/${path}`,'POST',body);await changed();}catch(e:any){setError(e.message);}finally{setBusy(false);}}
 return <section className={`automatic-investigation ${active?'working':''}`} aria-label="Automatic investigation">
  <div className="automatic-status" role="status">{active?<LoaderCircle className="spin" size={19}/>:failed||a.state==='partial'?<AlertTriangle size={19}/>:a.state==='completed'?<CheckCircle2 size={19}/>:<ScanLine size={19}/>}<div><strong>{labels[a.stage]||a.detail||'Automatic investigation'}</strong><p>{a.detail||'Submitting evidence starts investigation and safe public-reference retrieval. You review the sources, conclusions and consequential actions.'}</p></div></div>
  <div className="automatic-controls">{failed&&a.enabled&&<button className="secondary small" disabled={busy} onClick={()=>run('automation/retry')}>Retry investigation</button>}<button className="small" disabled={busy} onClick={()=>run('automation',{enabled:!a.enabled})}>{a.enabled?'Pause automatic investigation':'Enable automatic investigation'}</button></div>
  {rows.length>0&&<details><summary>{rows.filter(([,r])=>['preserved','already_preserved'].includes(r.status)).length} references preserved · {rows.length} checked</summary><ul>{rows.map(([url,r])=><li key={url}>{url.startsWith('http')?<a href={url} target="_blank" rel="noreferrer">{url}</a>:<span>Unsafe reference withheld</span>}<strong>{String(r.status).replaceAll('_',' ')}</strong>{r.detail&&<p>{r.detail}</p>}</li>)}</ul></details>}
  {error&&<p role="alert">{error}</p>}
 </section>;
}
