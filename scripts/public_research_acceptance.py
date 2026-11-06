"""Actual public-source/cloud/Gemini test; synthetic case, no financial writes.

Private accounts/IDs remain ignored. Report contains public URLs, hashes/counts
and booleans. Use --phase verify after restart/deploy to avoid refetching sources.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import secrets
import httpx

ROOT=Path(__file__).resolve().parents[1]
SOURCES=[('decision','https://decisions.civilresolutionbc.ca/crt/crtd/en/525448/1/document.do','tribunal_decision'),
 ('act','https://www.bclaws.gov.bc.ca/civix/document/id/complete/statreg/12025_01','reported_document')]


def run(args):
 state_path=args.state
 state=json.loads(state_path.read_text()) if state_path.exists() else {'actors':[],'sources':{}}
 checks={};public_sources=[]
 def save():state_path.write_text(json.dumps(state,indent=2))
 def check(name,value):
  checks[name]=bool(value)
  if not value:raise AssertionError(name)
 def ok(r):
  if r.status_code!=200:
   state['last_failure']={'status':r.status_code,'detail':r.json().get('detail')};save()
   raise AssertionError('HTTP '+str(r.status_code)+'; private diagnostic saved')
  return r.json()
 clients=[]
 try:
  for i in range(2):
   c=httpx.Client(base_url=args.base,timeout=240,limits=httpx.Limits(max_keepalive_connections=0));clients.append(c)
   if len(state['actors'])<=i:
    a={'username':'research_qa_'+secrets.token_hex(6),'password':secrets.token_urlsafe(24),'display_name':'Public research QA '+str(i+1)}
    r=ok(c.post('/api/auth/register',json=a));a['recovery_code']=r['recovery_code'];state['actors'].append(a);save()
    check('account_'+str(i+1)+'_empty',ok(c.get('/api/cases'))==[])
   else:
    a=state['actors'][i];ok(c.post('/api/auth/login',json={k:a[k] for k in ('username','password')}))
  c=clients[0];a=state['actors'][0]
  if 'case_id' not in a:
   case=ok(c.post('/api/cases',json={'title':'Moffatt public decision: reported facts versus tribunal findings','reason':'OTHER','amount':'0.00','currency':'CAD'}));a['case_id']=case['id'];save()
  path='/api/cases/'+a['case_id']
  check('foreign_research_hidden',clients[1].get(path+'/research').status_code==404)
  check('foreign_retrieval_denied',clients[1].post(path+'/research/url',json={'url':SOURCES[0][1],'consent':True}).status_code==404)
  if args.phase=='prepare':
   for label,url,kind in SOURCES:
    if label not in state['sources']:
     before=ok(c.get(path))
     d=ok(c.post(path+'/research/url',json={'url':url,'consent':True,'google_context':label=='decision','event_date':'2022-11-11'}))
     check(label+'_real_snapshot_ready',d['status']=='ready')
     after=ok(c.get(path));check(label+'_unapproved_not_evidence',after['revision']==before['revision'] and len(after['evidence'])==len(before['evidence']))
     check(label+'_text_integrity',hashlib.sha256(d['text'].encode()).hexdigest()==d['metadata']['text_sha256'])
     if label=='decision':
      check('decision_title_and_issued_date','Moffatt' in d['text'] and d['metadata']['publication_date']=='2024-02-14')
      statuses=d.get('google',{}).get('url_context_metadata',[])
      check('real_google_url_context',any(m['status']=='URL_RETRIEVAL_STATUS_SUCCESS' for m in statuses))
     state['sources'][label]={'draft_id':d['id'],'raw_sha256':d['raw_sha256'],'text_sha256':d['metadata']['text_sha256'],'url':url,'kind':kind};save()
    s=state['sources'][label]
    check(label+'_foreign_approval_denied',clients[1].post(path+'/research/'+s['draft_id']+'/approve',json={'consent':True,'snapshot_sha256':s['raw_sha256'],'source_kind':kind}).status_code==404)
    check(label+'_approval_required',c.post(path+'/research/'+s['draft_id']+'/approve',json={'consent':False,'snapshot_sha256':s['raw_sha256'],'source_kind':kind}).status_code==422)
    result=ok(c.post(path+'/research/'+s['draft_id']+'/approve',json={'consent':True,'snapshot_sha256':s['raw_sha256'],'source_kind':kind,'historical_note':'This is a retrieved published document. The current Act is not proof of a policy in November 2022; the tribunal decision reports allegations and separately states findings.'}))
    case=ok(c.get(path));source=next(e for e in case['evidence'] if e['sha256']==s['raw_sha256']);s['source_id']=source['id'];save()
    revision=case['revision'];audit=len(case['timeline'])
    duplicate=ok(c.post(path+'/research/'+s['draft_id']+'/approve',json={'consent':True,'snapshot_sha256':s['raw_sha256'],'source_kind':kind}))
    fresh=ok(c.get(path));check(label+'_approval_replay_idempotent',duplicate['duplicate'] and fresh['revision']==revision and len(fresh['timeline'])==audit)
   if not state.get('duplicate_fetch_checked'):
    duplicate=ok(c.post(path+'/research/url',json={'url':SOURCES[0][1],'consent':True}))
    check('duplicate_url_import_deduplicated',duplicate.get('duplicate') and duplicate['id']==state['sources']['decision']['draft_id']);state['duplicate_fetch_checked']=True;save()
   for url in ('http://127.0.0.1/private','https://169.254.169.254/latest/meta-data','https://user:secret@example.com/'):
    check('malicious_url_denied_'+str(len(checks)),c.post(path+'/research/url',json={'url':url,'consent':True,'google_context':True}).status_code==422)
   if not state.get('unavailable_checked'):
    failed=ok(c.post(path+'/research/url',json={'url':'https://www.python.org/verdict-public-evidence-does-not-exist/','consent':True}))
    check('unavailable_has_no_source_text',failed['status']=='unavailable' and not failed['text']);state['unavailable_checked']=True;save()
   if not state.get('free_search_checked'):
    before=ok(c.get(path))
    search=ok(c.post(path+'/research/search',json={'query':'Moffatt v Air Canada 2024 BCCRT 149 official tribunal decision','consent':True,'event_date':'2022-11-11'}))
    check('real_free_search_returned_documents',search['report']['google']['status']=='completed' and bool(search['report']['google']['documents']))
    check('autonomous_primary_source_retrieved',any(p.get('status')=='ready' and 'decisions.civilresolutionbc.ca' in p.get('metadata',{}).get('final_url','') for p in search['proposals']))
    check('discovery_did_not_write_official_evidence',ok(c.get(path))['revision']==before['revision'])
    state['free_search_checked']=True;state['free_search_providers']=search['report']['google']['provider_attempts'];save()
   case=ok(c.get(path))
   if args.reinvestigate or not case.get('analysis') or not case['analysis']['claims'] or case.get('analysis_stale'):
    ok(c.post(path+'/analyze',json={'consent':True}));case=ok(c.get(path))
   if not state.get('reanalysis_verified') and case.get('analysis',{}).get('claims'):
    first_statuses={x.get('epistemic_status') for x in case['analysis']['claims']}
    check('initial_investigation_reported_and_adjudicated_distinguished','party_report' in first_statuses and bool(first_statuses & {'document_finding','document_order'}))
    first=case['analysis']['created_at']
    ok(c.post(path+'/analyze',json={'consent':True}));case=ok(c.get(path))
    check('real_reanalysis_preserved_history',case['analysis']['created_at']!=first and sum(e['kind']=='investigation_updated' for e in case['timeline'])>=2)
    state['reanalysis_verified']=True;save()
   state['expected_revision']=case['revision'];state['expected_audit']=case['timeline'][-1]['hash'];state['expected_analysis']=hashlib.sha256(json.dumps(case['analysis'],sort_keys=True).encode()).hexdigest();save()
  case=ok(c.get(path));analysis=case['analysis']
  staged={d['id']:d for d in ok(c.get(path+'/research'))}
  decision=staged[state['sources']['decision']['draft_id']]
  check('preserved_real_google_url_context_success',any(m.get('status')=='URL_RETRIEVAL_STATUS_SUCCESS' for m in decision.get('google',{}).get('url_context_metadata',[])))
  check('decision_issued_date_retained',decision['metadata'].get('publication_date')=='2024-02-14')
  check('both_real_html_and_pdf_preserved',{s['provenance']['mime'] for s in case['evidence']}=={'application/pdf','text/html'})
  check('real_source_linked_investigation',bool(analysis and analysis['claims']))
  evidence={e['id']:e for e in case['evidence']}
  check('every_quote_in_preserved_text',all(x['quote'] in evidence[x['source_id']]['text'] for x in analysis['claims']))
  check('graph_bound_to_snapshot_hash_and_offsets',all(evidence[x['source_id']]['text'][x['passage_start']:x['passage_end']]==x['quote'] and x['snapshot_text_sha256']==evidence[x['source_id']]['provenance']['text_sha256'] for x in analysis['claims']))
  statuses={x.get('epistemic_status') for x in analysis['claims']}
  check('reported_and_adjudicated_distinguished','party_report' in statuses and bool(statuses & {'document_finding','document_order'}))
  check('past_policy_not_established_by_current_source',all(e['provenance']['historical_applicability']=='not_established' for e in evidence.values()))
  for label,s in state['sources'].items():
   file=c.get(path+'/files/'+s['source_id']);check(label+'_original_bytes_preserved',file.status_code==200 and hashlib.sha256(file.content).hexdigest()==s['raw_sha256'])
   check(label+'_original_served_as_attachment',file.headers.get('content-disposition','').startswith('attachment;'))
   check(label+'_original_private',clients[1].get(path+'/files/'+s['source_id']).status_code==404)
   public_sources.append({'label':label,'url':s['url'],'raw_sha256':s['raw_sha256'],'extracted_text_sha256':s['text_sha256']})
  check('durable_revision_and_audit',case['revision']==state['expected_revision'] and case['audit_valid'] and case['timeline'][-1]['hash']==state['expected_audit'])
  check('durable_analysis',hashlib.sha256(json.dumps(analysis,sort_keys=True).encode()).hexdigest()==state['expected_analysis'])
  report={'checked_at':datetime.now(timezone.utc).isoformat(),'base_url':args.base,'phase':args.phase,'checks':checks,'all_passed':all(checks.values()),'public_sources':public_sources,'claim_count':len(analysis['claims']),'epistemic_status_counts':{k:sum(x.get('epistemic_status')==k for x in analysis['claims']) for k in sorted(statuses)},'free_search_providers':state.get('free_search_providers'),'search_grounding':'Google paid grounding remains disabled. Documented Tavily keyless search plus public research APIs independently discover documents, which are retrieved directly before approval.','payment_writes':0}
  args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
 finally:
  for c in clients:c.close()


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--base',default='http://127.0.0.1:8001');p.add_argument('--phase',choices=['prepare','verify'],default='prepare');p.add_argument('--reinvestigate',action='store_true',help='Run one fresh investigation when validating a changed engine.');p.add_argument('--state',type=Path,default=ROOT/'runtime/saas-research-acceptance-private.json');p.add_argument('--report',type=Path,default=ROOT/'work/web-research/acceptance.json');run(p.parse_args())
