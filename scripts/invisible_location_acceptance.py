"""Ordinary account/source submission, actual cloud/provider/model verification.

Only authored fictional records and public landmarks are used. Private account
state and full cases remain under ignored runtime; reports contain checks only.
"""
import argparse,hashlib,json,secrets,time
from datetime import datetime,timezone
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[1]
CASES=[('landmarks',0,'IIT Bombay Main Gate, Powai, Mumbai, Maharashtra','Bhandup Railway Station, Bhandup West, Mumbai, Maharashtra','LOCATION MISMATCH'),
 ('aliases',0,'IIT Bombay, Powai, Mumbai, Maharashtra','Indian Institute of Technology Bombay, Powai, Mumbai, Maharashtra','POSSIBLE MATCH'),
 ('local_only',1,'Alpha Tower, Powai, Mumbai','Beta Tower, Powai, Mumbai','LOCATION MISMATCH')]

def fingerprint(c):return hashlib.sha256(json.dumps({k:c.get(k) for k in ('revision','evidence','analysis','timeline','delivery_location')},sort_keys=True).encode()).hexdigest()

def run(a):
 state=json.loads(a.state.read_text(encoding='utf-8')) if a.state.exists() else {'actors':[],'cases':{}}
 def save():a.state.write_text(json.dumps(state,indent=2),encoding='utf-8')
 checks={}
 def check(name,value):checks[name]=bool(value);assert value,name
 def ok(r):assert r.status_code==200,'Unexpected HTTP '+str(r.status_code);return r.json()
 clients=[httpx.Client(base_url=a.base,timeout=120,limits=httpx.Limits(max_keepalive_connections=0)) for _ in range(2)]
 try:
  for i,c in enumerate(clients):
   if len(state['actors'])<=i:
    assert a.phase=='prepare'
    actor={'username':'address_qa_'+secrets.token_hex(5),'password':secrets.token_urlsafe(24),'display_name':'Address QA '+str(i+1)}
    r=ok(c.post('/api/auth/register',json=actor));actor.update(owner_id=r['id'],recovery_code=r['recovery_code']);state['actors'].append(actor);save()
   else:
    actor=state['actors'][i]
    if actor.get('cookie'):
     c.cookies.set('verdict_account_session',actor['cookie'],domain=httpx.URL(a.base).host,path='/')
     if c.get('/api/me').status_code!=200:c.cookies.clear()
    if not c.cookies.get('verdict_account_session'):ok(c.post('/api/auth/login',json={k:actor[k] for k in ('username','password')}))
  if a.phase=='prepare':
   check('new_account_external_sharing_default_off',ok(clients[0].get('/api/preferences'))['mode']=='off')
   check('affirmative_consent_required',clients[0].post('/api/preferences/maps',json={'mode':'address','acknowledged':False}).status_code==422)
   ok(clients[0].post('/api/preferences/maps',json={'mode':'address','acknowledged':True}))
   check('other_account_permission_unchanged',ok(clients[1].get('/api/preferences'))['mode']=='off')
   for name,actor_index,intended,reported,_ in CASES:
    c=clients[actor_index]
    if name not in state['cases']:
     case=ok(c.post('/api/cases',json={'title':'Address intelligence acceptance: '+name,'amount':'1','currency':'INR','reason':'ITEM_NOT_RECEIVED'}));state['cases'][name]={'id':case['id']};save()
    row=state['cases'][name];route='/api/cases/'+row['id']
    if not ok(c.get(route))['evidence']:
     raw=('AUTHORED FICTIONAL INTEGRATION TEST. No real parcel, transaction or physical delivery is claimed.\nIntended destination: '+intended+'\nReported delivery destination: '+reported+'\nThese are source descriptions, not authenticated physical delivery scans.').encode()
     d=ok(c.post(route+'/upload',files={'file':('fictional-address-evidence.txt',raw,'text/plain')},data={'party':'other'}));row.update(original_id=d['evidence'][-1]['id'],original_sha256=hashlib.sha256(raw).hexdigest());save()
   print(json.dumps({'checks':checks,'all_passed':True,'source_submissions':3,'manual_location_or_investigation_calls':0}));return
  for name,actor_index,_,_,expected in CASES:
   c,other=clients[actor_index],clients[1-actor_index];row=state['cases'][name];route='/api/cases/'+row['id'];deadline=time.monotonic()+900
   while True:
    case=ok(c.get(route));w=case['automation']
    if case.get('delivery_location',{}).get('version')==3 and case.get('analysis') and not case['analysis_stale'] and w['state'] in ('completed','partial'):break
    if w['state']=='failed':state['last_failure']={'scenario':name,'detail':w.get('detail')};save();raise AssertionError('Automatic workflow stopped; private diagnostic retained')
    assert time.monotonic()<deadline,'Automatic review exceeded verification deadline';time.sleep(3)
   loc=case['delivery_location'];pair=loc['comparisons'][0]
   check(name+'_expected_comparison',loc['status']==expected)
   check(name+'_plain_result_and_source_explanation',bool(pair['result_label']) and bool(pair['explanation']) and 'physical delivery' in pair['explanation'])
   check(name+'_actual_automatic_model_assessment',bool(case['analysis']['model']))
   check(name+'_original_file_preserved',hashlib.sha256(c.get(route+'/files/'+row['original_id']).content).hexdigest()==row['original_sha256'])
   check(name+'_audit_valid',case['audit_valid'])
   check(name+'_no_per_case_permission_action',not case.get('location_authorization'))
   check(name+'_no_pin_required',all(m.get('explicit_postcode') is None for m in loc['mentions']))
   check(name+'_foreign_case_hidden',other.get(route).status_code==404)
   check(name+'_foreign_evidence_hidden',other.get(route+'/files/'+row['original_id']).status_code==404)
   check(name+'_foreign_permission_denied',other.post(route+'/location-authorization',json={'mode':'address','acknowledged':True}).status_code==404)
   sources={s['id']:s for s in case['evidence']};check(name+'_claims_cite_preserved_quotes',all(cl['quote'] in sources[cl['source_id']]['text'] for cl in case['analysis']['claims']))
   if name=='local_only':check('off_account_sends_no_address_queries',loc['new_provider_queries']==0 and all(m['geocode']['status']=='not_authorized' for m in loc['mentions']))
   else:
    check(name+'_actual_provider_records_preserved',all(m['geocode']['status']=='resolved' and m['geocode'].get('raw_response') and hashlib.sha256(m['geocode']['raw_response'].encode()).hexdigest()==m['geocode']['response_sha256'] for m in loc['mentions']))
    check(name+'_coarse_points_not_precise',not pair['sufficiently_precise'])
    if name=='landmarks':check('landmark_contradiction_overrides_common_region',loc['status']=='LOCATION MISMATCH' and 2000<pair['distance_m']<5000)
   if a.phase=='wait':row['fingerprint']=fingerprint(case);save()
   else:check(name+'_deployment_persistence',fingerprint(case)==row['fingerprint'])
  for i,c in enumerate(clients):
   row=state['cases']['landmarks' if i==0 else 'local_only'];route='/api/cases/'+row['id']
   ok(c.post('/api/auth/logout'));check('account_'+str(i+1)+'_logout_revokes',c.get(route).status_code==401)
   ok(c.post('/api/auth/login',json={k:state['actors'][i][k] for k in ('username','password')}));check('account_'+str(i+1)+'_return_preserves_records',fingerprint(ok(c.get(route)))==row['fingerprint'])
  report={'checked_at':datetime.now(timezone.utc).isoformat(),'base_url':a.base,'phase':a.phase,'checks':checks,'all_passed':all(checks.values()),'controlled_workflow_retries':0,'scope':'Two ordinary automated accounts and three explicitly fictional user-authored cases. Actual Photon and Gemini APIs and durable cloud records. Source submission alone triggers work after one-time consent. No independent human usability or full-browser visual test is claimed.','manual_location_or_investigation_calls':0,'payment_or_dispute_writes':0,'paid_services_enabled':False}
  a.report.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
 finally:
  for i,c in enumerate(clients):
   if i<len(state['actors']):
    if c.cookies.get('verdict_account_session'):state['actors'][i]['cookie']=c.cookies.get('verdict_account_session')
    else:state['actors'][i].pop('cookie',None)
   c.close()
  save()

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--phase',choices=['prepare','wait','verify'],required=True);p.add_argument('--state',type=Path,default=ROOT/'runtime/saas-invisible-acceptance-private.json');p.add_argument('--report',type=Path,default=ROOT/'work/invisible-acceptance.json');run(p.parse_args())
