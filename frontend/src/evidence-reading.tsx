import React from 'react';

type API=(path:string,method?:string,body?:any)=>Promise<any>;
export function ReadingPreference({api}:{api:API}) {
  const [enabled,setEnabled]=React.useState<boolean|null>(null),[busy,setBusy]=React.useState(false),[error,setError]=React.useState('');
  React.useEffect(()=>{let active=true;api('/evidence-reading').then(r=>{if(active)setEnabled(r.enabled)}).catch(()=>{if(active)setError('Image-reading preferences could not be loaded. Offline reading remains available.')});return()=>{active=false}},[api]);
  return <details className="technical-record"><summary>Reading images and handwriting</summary>
    <p>Images and scanned pages are read automatically. The original stays in your private case. Machine transcription can be wrong.</p>
    <p>Optional handwriting and image reading sends up to three cleaned page images per document to Google Gemini. Google’s free service may use submitted content to improve its products. Only enable this for documents you are authorized to share. This permission applies to future uploads and can be revoked here.</p>
    <label><input type="checkbox" checked={enabled===true} disabled={enabled===null||busy} onChange={async e=>{const next=e.target.checked;setBusy(true);setError('');try{const r=await api('/evidence-reading','POST',{enabled:next});setEnabled(r.enabled)}catch(err:any){setError(err.message)}finally{setBusy(false)}}}/> Allow Gemini to read my uploaded page images</label>
    {error&&<p role="alert">{error}</p>}
  </details>
}

export function ExtractionDetails({source}:{source:any}) {
  const r=source.extraction;if(!r)return null;
  return <section className="source-provenance"><strong>{r.status==='pending'?'Checking document…':r.status==='unreadable'?'Couldn’t reliably read this document':'Machine transcription · inspect the original'}</strong>
    <p>{r.warning||'Text is being extracted. No document content has been inferred.'}</p>
    <details><summary>Page details and integrity</summary>
      <p>Original SHA-256: <code>{r.original_sha256}</code></p>
      {r.text_sha256&&<p>Transcription SHA-256: <code>{r.text_sha256}</code></p>}
      {r.pages?.map((p:any)=><div key={p.page}><strong>Page {p.page} · {p.status}</strong><p>{p.method==='pdf_text'?'Embedded PDF text':'Image transcription; authenticity unverified'}</p>
        {p.vision&&<p>{p.vision.writing} · {p.vision.uncertainty.join('; ')||'AI transcription remains unverified.'}</p>}
        {p.vision_failure&&<p>{p.vision_failure}</p>}
        {!!p.words?.length&&<details><summary>Recognized words and page positions</summary><p>Positions refer to the normalized {p.width} × {p.height} page. Scores measure engine confidence, not factual truth.</p><pre>{p.words.map((w:any)=>`${w.text} · ${w.box.join(', ')} · score ${w.confidence}`).join('\n')}</pre></details>}
      </div>)}
    </details>
  </section>
}
