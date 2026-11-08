import React from 'react';
type API=(path:string,method?:string,body?:any)=>Promise<any>;
const reasons:Record<string,string>={existing_refund_requires_reconciliation:'PayPal already reports a refund record. Another financial action is blocked while that record is reconciled.',investigation_pending:'The investigation must finish before an action can be considered.',investigation_conflict:'The evidence does not support an automatic concession.',unresolved_document_uncertainty:'Important document content remains uncertain.',outside_test_order_policy:'This order is outside the authorized test policy.',provider_action_unavailable:'PayPal does not currently offer an eligible action.'};
export function SandboxAutonomy({api,caseId}:{api:API,caseId?:string}) {
 const [policy,setPolicy]=React.useState<any>(null),[status,setStatus]=React.useState<any>(null),[busy,setBusy]=React.useState(false),[error,setError]=React.useState('');
 const load=React.useCallback(async()=>{const p=await api('/paypal/autonomy');setPolicy(p);if(caseId)setStatus(await api(`/cases/${caseId}/resolution`))},[api,caseId]);
 React.useEffect(()=>{let active=true;const check=()=>load().catch(e=>{if(active)setError(e.message)});check();const t=setInterval(check,15000);return()=>{active=false;clearInterval(t)}},[load]);
 async function change(f:HTMLFormElement|undefined,enabled:boolean){setBusy(true);setError('');try{const d=f?new FormData(f):null;await api('/paypal/autonomy','POST',{enabled,unfulfilled_test_orders:!!d?.get('attest'),per_claim_usd:d?Number(d.get('per_claim')).toFixed(2):'1.00',total_usd:d?Number(d.get('total')).toFixed(2):'1.00',max_actions:d?Number(d.get('actions')):1,hours:24});await load()}catch(e:any){setError(e.message)}finally{setBusy(false)}}
 const o=status?.observation;
 return <section className="paypal-source">
  {o&&<><strong>{o.label}</strong>{o.reason&&<p>{reasons[o.reason]||'An automatic action is not supported by the available records. The investigation and originals are retained.'}</p>}{o.checked_at&&<p className="fine">PayPal checked {new Date(o.checked_at).toLocaleString()}</p>}</>}
  <details><summary>Sandbox automatic resolution {policy?.enabled?'· enabled':'· off'}</summary>
   <p>Test funds only. Eligible, unfulfilled VERDICT test orders can be conceded to the buyer without another approval. PayPal makes the refund and confirms the outcome. Uploaded documents and AI conclusions alone cannot authorize a financial action. Existing refunds, uncertain records and unsupported seller claims cause abstention.</p>
   {policy?.enabled?<><p>USD {policy.per_claim_usd} per claim · USD {policy.total_usd} total · {policy.max_actions} actions maximum. Expires {new Date(policy.expires_at).toLocaleString()}.</p><button className="secondary" disabled={busy} onClick={()=>change(undefined,false)}>Turn off automatic resolution</button><p>Revocation stops new dispatches. An action already sent cannot be recalled.</p></>:
    <form onSubmit={e=>{e.preventDefault();change(e.currentTarget,true)}}>
     <label>Maximum USD per claim<input name="per_claim" type="number" min="0.01" max="5" step="0.01" defaultValue="1.00" required/></label>
     <label>Total USD limit<input name="total" type="number" min="0.01" max="10" step="0.01" defaultValue="1.00" required/></label>
     <label>Maximum actions<input name="actions" type="number" min="1" max="5" defaultValue="1" required/></label>
     <label><input name="attest" type="checkbox" required/> I am the authorized sandbox merchant. Orders identified as VERDICT-SANDBOX-TEST under this policy are integration tests with no physical fulfillment. I authorize eligible buyer concessions within these limits for 24 hours.</label>
     <button className="primary" disabled={busy||!policy}>Enable sandbox autonomy</button>
    </form>}
   {status?.action&&<details><summary>Action record</summary><p>{status.action.state} · no automatic resubmission</p><pre>{JSON.stringify(status.action,null,2)}</pre></details>}
  </details>{error&&<p role="alert">{error}</p>}
 </section>
}
