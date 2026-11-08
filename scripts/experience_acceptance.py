"""Ordinary two-account UX/API acceptance; private credentials never published."""
import argparse,hashlib,json,secrets,time
from pathlib import Path
from datetime import datetime,timezone
import httpx

ROOT=Path(__file__).resolve().parents[1]
def fingerprint(c):return hashlib.sha256(json.dumps({k:c.get(k) for k in ('revision','evidence','analysis','timeline','delivery_location')},sort_keys=True).encode()).hexdigest()
def run(a):
 path=ROOT/'runtime/saas-experience-acceptance-private.json';state=json.loads(path.read_text()) if path.exists() else {'actors':[]};checks={}
 def save():path.write_text(json.dumps(state,indent=2),encoding='utf-8')
 def check(n,v):checks[n]=bool(v);assert v,n
 def ok(r):
  if r.status_code!=200:state['last_failure']={'status':r.status_code};save();raise AssertionError('Unexpected HTTP '+str(r.status_code))
  return r.json()
 clients=[httpx.Client(base_url=a.base,timeout=120,limits=httpx.Limits(max_keepalive_connections=0)) for _ in range(2)]
 try:
  for i,c in enumerate(clients):
   if len(state['actors'])<=i:
    assert a.phase=='prepare'
    actor={'username':'experience_qa_'+secrets.token_hex(5),'password':secrets.token_urlsafe(24),'display_name':'Product QA '+str(i+1)};r=ok(c.post('/api/auth/register',json=actor));actor.update(owner_id=r['id'],recovery_code=r['recovery_code']);state['actors'].append(actor);save()
   else:
    actor=state['actors'][i]
    if actor.get('session_cookie'):
     c.cookies.set('verdict_account_session',actor['session_cookie'],domain=httpx.URL(a.base).host,path='/')
     if c.get('/api/me').status_code!=200:c.cookies.clear()
    if not c.cookies.get('verdict_account_session'):ok(c.post('/api/auth/login',json={k:actor[k] for k in ('username','password')}))
  c,other=clients
  if a.phase=='prepare':
   check('new_account_external_maps_default_off',ok(c.get('/api/preferences'))['mode']=='off')
   check('explicit_acknowledgement_required',c.post('/api/preferences/maps',json={'mode':'area_only','acknowledged':False}).status_code==422)
   ok(c.post('/api/preferences/maps',json={'mode':'area_only','acknowledged':True}));check('one_time_map_preference_saved',ok(c.get('/api/preferences'))['mode']=='area_only')
   check('other_account_preference_unchanged',ok(other.get('/api/preferences'))['mode']=='off')
   if 'case_id' not in state:
    case=ok(c.post('/api/cases',json={'title':'Product experience acceptance','amount':'12000','currency':'INR','reason':'ITEM_NOT_RECEIVED'}));state['case_id']=case['id'];save()
   route='/api/cases/'+state['case_id'];case=ok(c.get(route));check('normal_amount_normalized',case['amount']=='12000.00')
   check('no_case_permission_dialog_required',case['effective_map_preference']['mode']=='area_only' and not case.get('location_authorization'))
   if not case['evidence']:
    raw=b'AUTHORED FICTIONAL TEST.\nBuyer intended destination PIN code: 400076\nSeller tracking: DELIVERED.\nCarrier reported delivery destination PIN code: 400078\nNo physical shipment, delivery GPS or independent receipt verification is claimed.'
    r=ok(c.post(route+'/upload',files={'file':('fictional-receipt.txt',raw,'text/plain')},data={'party':'other'}));state['original_id']=r['evidence'][-1]['id'];state['original_sha256']=hashlib.sha256(raw).hexdigest();save()
   print(json.dumps({'checks':checks,'all_passed':all(checks.values()),'ordinary_accounts':2,'workflow_queued':True}));return
  route='/api/cases/'+state['case_id'];deadline=time.monotonic()+900
  while True:
   case=ok(c.get(route));w=case['automation']
   if w['state'] in ('completed','partial') and case.get('analysis'):break
   if w['state']=='failed':state['last_failure']={'detail':w.get('detail')};save();raise AssertionError('Automatic review stopped; private diagnostic retained')
   assert a.phase!='verify' and time.monotonic()<deadline,'Automatic review not yet complete'
   time.sleep(3)
  check('real_automatic_gemini_assessment',bool(case['analysis']['model']) and not case['analysis_stale'])
  check('remembered_permission_used_without_per_case_prompt',case['delivery_location']['authorization_mode']=='area_only' and not case.get('location_authorization'))
  check('source_pin_discrepancy_retained',case['delivery_location']['status']=='LOCATION MISMATCH')
  check('actual_geocoder_markers',sum(m['geocode'].get('status')=='resolved' for m in case['delivery_location']['mentions'])>=2)
  check('original_bytes_intact',hashlib.sha256(c.get(route+'/files/'+state['original_id']).content).hexdigest()==state['original_sha256'])
  evidence={e['id']:e for e in case['evidence']};check('claims_quote_actual_sources',all(cl['quote'] in evidence[cl['source_id']]['text'] for cl in case['analysis']['claims']))
  check('audit_integrity',case['audit_valid'])
  check('other_account_case_hidden',other.get(route).status_code==404)
  check('other_account_cannot_change_case_permission',other.post(route+'/location-authorization',json={'mode':'address','acknowledged':True}).status_code==404)
  check('other_account_has_no_cases',ok(other.get('/api/cases'))==[])
  if a.phase=='wait' and not state.get('witness_done'):
   result=ok(c.post(route+'/requests',json={'witness_id':'manual','title':'Delivery destination','question':'For this fictional test, which PIN was recorded for delivery?','recipient':'carrier'}));state['witness_id']=result['request']['id'];state['portal_token']=result['portal_fragment'].split('=',1)[1];save()
   before=case['analysis']['input_digest'];raw=b'FICTIONAL CARRIER RESPONSE. Delivery destination PIN code: 400078. Recipient signature and actual GPS are not available. No real delivery occurred.'
   headers={'Authorization':'Bearer '+state['portal_token']}
   check('witness_portal_has_restricted_projection',set(ok(other.get('/api/portal',headers=headers)))=={'id','title','question','recipient','expires_at'})
   ok(other.post('/api/portal/upload',headers=headers,files={'file':('carrier-response.txt',raw,'text/plain')}))
   deadline=time.monotonic()+600
   while True:
    case=ok(c.get(route))
    if case.get('analysis') and not case['analysis_stale'] and case['analysis']['input_digest']!=before and case['automation']['state'] in ('completed','partial'):break
    assert case['automation']['state']!='failed' and time.monotonic()<deadline,'Witness reassessment did not complete'
    time.sleep(3)
   check('witness_reply_automatically_reassessed',any(r['id']==state['witness_id'] and r['status']=='received' for r in case['requests']))
   check('no_duplicate_geocoding_after_witness_reply',case['delivery_location']['new_provider_queries']==0)
   check('witness_portal_replay_denied',other.post('/api/portal',headers=headers,json={'title':'Replay','text':'Denied'}).status_code==409)
   state['witness_done']=True;state['fingerprint']=fingerprint(case);save()
  if a.phase=='wait':state['fingerprint']=fingerprint(case);save()
  else:check('deployment_and_restart_persistence',fingerprint(case)==state['fingerprint'])
  ok(c.post('/api/auth/logout'));check('logout_revokes_session',c.get(route).status_code==401)
  ok(c.post('/api/auth/login',json={k:state['actors'][0][k] for k in ('username','password')}));check('login_returns_same_records',fingerprint(ok(c.get(route)))==state['fingerprint'])
  check('account_map_preference_persisted',ok(c.get('/api/preferences'))['mode']=='area_only')
  report={'checked_at':datetime.now(timezone.utc).isoformat(),'base_url':a.base,'phase':a.phase,'checks':checks,'all_passed':all(checks.values()),'scope':'Two ordinary automated accounts, authored fictional PIN evidence, actual cloud/Gemini/Photon APIs. No manual investigation or per-case mapping action. Restricted witness response triggers actual automatic reassessment. Not a human usability or full-browser visual test.','provider_business_writes':0,'paid_services_enabled':False}
  a.report.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
 finally:
  for i,c in enumerate(clients):
   if i<len(state['actors']) and c.cookies.get('verdict_account_session'):state['actors'][i]['session_cookie']=c.cookies.get('verdict_account_session')
   c.close()
  save()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--phase',choices=['prepare','wait','verify'],required=True);p.add_argument('--report',type=Path,default=ROOT/'work/experience-acceptance.json');run(p.parse_args())
