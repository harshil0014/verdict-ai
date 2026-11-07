"""Hosted public-demo geocoding with ordinary accounts. Private state is ignored."""
import argparse,hashlib,json,secrets,time
from pathlib import Path
from datetime import datetime,timezone
import httpx

ROOT=Path(__file__).resolve().parents[1]
CASES=[
 ('headphones','area_only','Fictional buyer intended destination PIN code: 400076\nFictional carrier delivery destination PIN code: 400078\nSeller tracking: DELIVERED. No actual package or authenticated delivery GPS exists.'),
 ('missing_pin','address','Intended destination: Indian Institute of Technology Bombay, Powai, Mumbai 400076\nReported delivery destination: Indian Institute of Technology Bombay, Powai, Mumbai\nFictional comparison using a public campus, not a customer address.'),
 ('nearby_distinct','address','Intended destination: Taj Mahal Palace Hotel, Mumbai 400001\nReported delivery destination: Gateway of India, Mumbai 400001\nFictional comparison of distinct public sites, not actual delivery.'),
 ('different_locations','area_only','Intended destination: Mumbai PIN code 400076\nReported delivery destination: New Delhi PIN code 110001\nPublic area demonstration only. No actual shipment.'),
 ('vague','address','Intended destination: Mumbai\nReported delivery destination: Mumbai\nOnly a city is known; no actual delivery occurred.')]

def fingerprint(case):
 return hashlib.sha256(json.dumps({k:case.get(k) for k in ('revision','evidence','analysis','timeline','delivery_location')},sort_keys=True).encode()).hexdigest()

def run(a):
 state_path=ROOT/'runtime/saas-location-acceptance-private.json'
 state=json.loads(state_path.read_text()) if state_path.exists() else {'actors':[],'cases':{}}
 def save():state_path.write_text(json.dumps(state,indent=2),encoding='utf-8')
 checks={}
 def check(name,v):
  checks[name]=bool(v)
  if not v:raise AssertionError(name)
 def ok(r):
  if r.status_code!=200:
   state['last_failure']={'status':r.status_code};save();raise AssertionError('Unexpected HTTP '+str(r.status_code))
  return r.json()
 clients=[httpx.Client(base_url=a.base,timeout=120,limits=httpx.Limits(max_keepalive_connections=0)) for _ in range(2)]
 try:
  for i,c in enumerate(clients):
   if len(state['actors'])<=i:
    assert a.phase=='prepare'
    actor={'username':'location_qa_'+secrets.token_hex(5),'password':secrets.token_urlsafe(24),'display_name':'Location QA '+str(i+1)}
    r=ok(c.post('/api/auth/register',json=actor));actor.update(owner_id=r['id'],recovery_code=r['recovery_code']);state['actors'].append(actor);save()
   else:
    actor=state['actors'][i]
    if actor.get('session_cookie'):
     c.cookies.set('verdict_account_session',actor['session_cookie'],domain=httpx.URL(a.base).host,path='/')
     if c.get('/api/me').status_code!=200:c.cookies.clear()
    if not c.cookies.get('verdict_account_session'):ok(c.post('/api/auth/login',json={k:actor[k] for k in ('username','password')}))
  c,outsider=clients
  if a.phase=='prepare':
   for label,mode,text in CASES:
    if label in state['cases']:continue
    case=ok(c.post('/api/cases',json={'title':'Location acceptance · '+label,'reason':'ITEM_NOT_RECEIVED','amount':'1.00','currency':'USD'}));path='/api/cases/'+case['id']
    check(label+'_external_authorization_required',c.post(path+'/location-authorization',json={'mode':mode,'acknowledged':False}).status_code==422)
    ok(c.post(path+'/location-authorization',json={'mode':mode,'acknowledged':True}))
    raw=('AUTHORED FICTIONAL DELIVERY TEST.\n'+text).encode()
    uploaded=ok(c.post(path+'/upload',files={'file':('public-location-test.txt',raw,'text/plain')},data={'party':'other'}))
    state['cases'][label]={'case_id':case['id'],'original_sha256':hashlib.sha256(raw).hexdigest(),'source_id':uploaded['evidence'][-1]['id']};save()
   print(json.dumps({'ordinary_account_registrations':2,'automatic_workflows_queued':len(state['cases']),'provider_business_writes':0}));return
  summaries=[]
  for label,mode,text in CASES:
   row=state['cases'][label];path='/api/cases/'+row['case_id'];deadline=time.monotonic()+900
   while True:
    case=ok(c.get(path));w=case['automation']
    if w['state'] in ('completed','partial'):break
    if w['state']=='failed':
     state['last_failure']={'label':label,'detail':w.get('detail')};save();raise AssertionError(label+' automatic workflow failed; private diagnostic retained')
    if a.phase=='verify' or time.monotonic()>deadline:raise AssertionError(label+' workflow not complete')
    time.sleep(3)
   r=case['delivery_location'];mentions=r['mentions'];comparisons=r['comparisons']
   evidence={e['id']:e for e in case['evidence']}
   check(label+'_source_anchored',bool(mentions) and all(m['address'] in m['quote'] and m['quote'] in evidence[m['source_id']]['text'] for m in mentions))
   check(label+'_original_bytes_preserved',hashlib.sha256(c.get(path+'/files/'+row['source_id']).content).hexdigest()==row['original_sha256'])
   check(label+'_real_gemini_and_fresh_analysis',bool(case.get('analysis',{}).get('model')) and not case['analysis_stale'])
   check(label+'_quotes_from_actual_sources',all(cl['quote'] in evidence[cl['source_id']]['text'] for cl in case['analysis']['claims']))
   check(label+'_location_record_in_investigation',case['analysis']['input_digest'] is not None and case['audit_valid'] and any(e['kind']=='delivery_location_verified' for e in case['timeline']))
   for m in mentions:
    g=m['geocode']
    if 'raw_response' in g:check(label+'_provider_response_hash_'+m['role'],hashlib.sha256(g['raw_response'].encode()).hexdigest()==g['response_sha256'])
   if label=='headphones':
    check('headphones_explicit_pin_mismatch',r['status']=='LOCATION MISMATCH')
    check('headphones_real_postcode_area_points',len(mentions)>=2 and all(m['geocode'].get('precision')=='postcode_area' for m in mentions))
    check('no_fabricated_delivery_gps',all(m['geocode']['provider']=='Photon / OpenStreetMap' for m in mentions))
   if label=='missing_pin':check('missing_pin_not_mismatch',r['status'] in ('POSSIBLE MATCH','LIKELY MATCH') and any(m['explicit_postcode'] is None for m in mentions))
   if label=='nearby_distinct':check('distinct_sites_not_exact_match',r['status']!='LIKELY MATCH')
   if label=='different_locations':check('different_locations_mismatch',r['status']=='LOCATION MISMATCH' and all(m['geocode'].get('status')=='resolved' for m in mentions))
   if label=='vague':check('vague_not_precise_match',r['status'] in ('UNVERIFIED','POSSIBLE MATCH') and all(m['geocode'].get('precision')!='building' for m in mentions))
   check(label+'_foreign_case_denied',outsider.get(path).status_code==404)
   check(label+'_foreign_consent_write_denied',outsider.post(path+'/location-authorization',json={'mode':'address','acknowledged':True}).status_code==404)
   if a.phase=='verify':check(label+'_deployment_persistence',fingerprint(case)==row['fingerprint'])
   else:row['fingerprint']=fingerprint(case);save()
   summaries.append({'scenario':label,'status':r['status'],'resolved_markers':sum(m['geocode'].get('status')=='resolved' for m in mentions),'precision':[m['geocode'].get('precision') for m in mentions],'provider_status':[m['geocode']['status'] for m in mentions]})
  if a.phase=='wait' and not state.get('reanalysis_done'):
   row=state['cases']['headphones'];path='/api/cases/'+row['case_id'];before=ok(c.get(path));raw=b'FICTIONAL carrier receipt. Delivery destination PIN code: 400078\nTracking remains DELIVERED; recipient and actual delivery GPS are not authenticated.'
   ok(c.post(path+'/upload',files={'file':('new-carrier-receipt.txt',raw,'text/plain')},data={'party':'carrier'}))
   deadline=time.monotonic()+600
   while True:
    case=ok(c.get(path))
    if case['automation']['state'] in ('completed','partial') and case['analysis']['input_digest']!=before['analysis']['input_digest']:break
    if case['automation']['state']=='failed' or time.monotonic()>deadline:raise AssertionError('new carrier receipt reassessment not completed')
    time.sleep(3)
   check('new_carrier_receipt_automatically_reassessed',case['delivery_location']['status']=='LOCATION MISMATCH' and not case['analysis_stale'])
   check('reanalysis_reuses_geocoder_cache',case['delivery_location']['new_provider_queries']==0)
   row['fingerprint']=fingerprint(case);state['reanalysis_done']=True;save()
  check('other_account_lists_no_cases',ok(outsider.get('/api/cases'))==[])
  row=state['cases']['headphones'];path='/api/cases/'+row['case_id'];ok(c.post('/api/auth/logout'));check('logout_revoked',c.get(path).status_code==401)
  ok(c.post('/api/auth/login',json={k:state['actors'][0][k] for k in ('username','password')}));check('login_preserves_location_record',fingerprint(ok(c.get(path)))==row['fingerprint'])
  report={'checked_at':datetime.now(timezone.utc).isoformat(),'base_url':a.base,'phase':a.phase,'checks':checks,'all_passed':all(checks.values()),'scenarios':summaries,'real_public_photon_api':True,'evidence':'Authored fictional delivery scenarios using public places/PINs; actual geocoder responses, cloud storage and Gemini. Two automated accounts, not two human testers.','provider_business_writes':0,'billing_enabled':False}
  a.report.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
 finally:
  for i,c in enumerate(clients):
   if i<len(state['actors']) and c.cookies.get('verdict_account_session'):state['actors'][i]['session_cookie']=c.cookies.get('verdict_account_session')
   c.close()
  save()

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--phase',choices=['prepare','wait','verify'],required=True);p.add_argument('--report',type=Path,default=ROOT/'work/location-acceptance.json');run(p.parse_args())
