"""Real provider/cloud/model acceptance with authored public-landmark evidence.

Credentials and case records stay in ignored runtime; public reports contain
only checks and the public map matches. No fake live responses or shipments.
"""
import argparse,hashlib,json,secrets,time
from datetime import datetime,timezone
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[1]
DESTINATIONS={'campus':'IIT Bombay Main Gate, Powai, Mumbai, Maharashtra',
    'ambiguous':'Springfield','missing':'Zzqxv Invented Quantum Palace, Powai, Mumbai, Maharashtra'}
REPORTED='Bhandup Railway Station, Bhandup West, Mumbai, Maharashtra'
def fingerprint(c):return hashlib.sha256(json.dumps({k:c.get(k) for k in ('revision','evidence','analysis','timeline','delivery_location')},sort_keys=True).encode()).hexdigest()

def run(a):
 state=json.loads(a.state.read_text(encoding='utf-8')) if a.state.exists() else {'actors':[],'cases':{}}
 def save():a.state.write_text(json.dumps(state,indent=2),encoding='utf-8')
 checks={};results={}
 def check(name,v):
  checks[name]=bool(v)
  if not v:raise AssertionError(name)
 def ok(r):
  if r.status_code!=200:raise AssertionError('Unexpected HTTP '+str(r.status_code))
  return r.json()
 clients=[httpx.Client(base_url=a.base,timeout=90,limits=httpx.Limits(max_keepalive_connections=0)) for _ in range(2)]
 try:
  for i,c in enumerate(clients):
   if len(state['actors'])<=i:
    assert a.phase=='prepare'
    actor={'username':'geocoding_qa_'+secrets.token_hex(5),'password':secrets.token_urlsafe(24),'display_name':'Geocoding QA '+str(i+1)}
    r=ok(c.post('/api/auth/register',json=actor));actor.update(owner_id=r['id'],recovery_code=r['recovery_code']);state['actors'].append(actor);save()
   else:
    actor=state['actors'][i];ok(c.post('/api/auth/login',json={k:actor[k] for k in ('username','password')}))
  c,other=clients
  if a.phase=='prepare':
   check('new_account_lookup_default_off',ok(c.get('/api/preferences'))['mode']=='off')
   ok(c.post('/api/preferences/maps',json={'mode':'address','acknowledged':True}))
   for name,address in DESTINATIONS.items():
    if name not in state['cases']:
     case=ok(c.post('/api/cases',json={'title':'Public map acceptance: '+name,'amount':'1','currency':'INR','reason':'ITEM_NOT_RECEIVED'}))
     state['cases'][name]={'id':case['id']};save()
    row=state['cases'][name];route='/api/cases/'+row['id']
    if not ok(c.get(route))['evidence']:
     raw=('AUTHORED FICTIONAL TEST. Public landmarks only; no actual shipment, loss or delivery is claimed.\nIntended destination: '+address+'\nReported delivery destination: '+REPORTED+'\nThe location comparison is an approximate research aid, not proof of delivery.').encode()
     r=ok(c.post(route+'/upload',files={'file':('public-location-test.txt',raw,'text/plain')},data={'party':'other'}))
     row.update(source_id=r['evidence'][-1]['id'],source_sha256=hashlib.sha256(raw).hexdigest());save()
   print(json.dumps({'all_passed':True,'checks':checks,'queued_real_automatic_cases':3}));return
  for name,row in state['cases'].items():
   route='/api/cases/'+row['id'];deadline=time.monotonic()+900
   while True:
    case=ok(c.get(route));w=case['automation']
    if w['state'] in ('completed','partial') and case.get('analysis') and not case['analysis_stale'] and case.get('delivery_location',{}).get('version')==2:break
    assert w['state']!='failed' and time.monotonic()<deadline,'Automatic review not complete; inspect private case state'
    time.sleep(3)
   location=case['delivery_location'];intended=next(m['geocode'] for m in location['mentions'] if m['role']=='intended');reported=next(m['geocode'] for m in location['mentions'] if m['role']=='reported_delivery')
   check(name+'_actual_automatic_assessment',bool(case['analysis']['model']) and location['version']==2)
   check(name+'_original_file_intact',hashlib.sha256(c.get(route+'/files/'+row['source_id']).content).hexdigest()==row['source_sha256'])
   check(name+'_audit_valid',case['audit_valid'])
   check(name+'_no_manual_pin_required',all(m['explicit_postcode'] is None for m in location['mentions']))
   check(name+'_reported_map_result_resolved',reported['status']=='resolved')
   check(name+'_foreign_case_hidden',other.get(route).status_code==404)
   check(name+'_foreign_original_hidden',other.get(route+'/files/'+row['source_id']).status_code==404)
   check(name+'_foreign_permission_denied',other.post(route+'/location-authorization',json={'mode':'off'}).status_code==404)
   sources={e['id']:e for e in case['evidence']}
   check(name+'_claims_link_preserved_passages',all(cl['quote'] in sources[cl['source_id']]['text'] for cl in case['analysis']['claims']))
   if name=='campus':
    check('campus_resolved_with_explicit_approximation',intended['status']=='resolved' and intended['precision']=='site' and intended['match_scope']=='parent_campus' and 'exact gate' in intended['accuracy_label'])
    check('both_locations_compared_automatically',len(location['comparisons'])==1 and 2000<location['comparisons'][0]['distance_m']<5000)
    check('real_fallback_attempts_preserved',len(intended['attempts'])>=2 and intended['fallback_used'])
    for label,g in [('campus',intended),('reported',reported)]:
     raw=json.loads(g['raw_response']);check(label+'_coordinate_exists_in_preserved_response',any(f['geometry']['coordinates']==[g['lon'],g['lat']] and f['properties']['osm_id']==g['osm_id'] for f in raw['features']))
     check(label+'_response_integrity',hashlib.sha256(g['raw_response'].encode()).hexdigest()==g['response_sha256'])
    if a.phase=='wait' and not row.get('reanalysis_done'):
     before=case['analysis']['input_digest'];ok(c.post(route+'/evidence',json={'title':'Additional fictional context','text':'No recipient signature is available in this fictional test. No real delivery occurred.','party':'seller'}))
     deadline=time.monotonic()+600
     while True:
      case=ok(c.get(route))
      if case.get('analysis') and not case['analysis_stale'] and case['analysis']['input_digest']!=before and case['automation']['state'] in ('completed','partial'):break
      assert case['automation']['state']!='failed' and time.monotonic()<deadline;time.sleep(3)
     check('reanalysis_reuses_provider_results',case['delivery_location']['new_provider_queries']==0)
     check('reanalysis_keeps_campus_accuracy',next(m['geocode'] for m in case['delivery_location']['mentions'] if m['role']=='intended')['match_scope']=='parent_campus')
     row['reanalysis_done']=True;save()
    if row.get('reanalysis_done'):
     check('reanalysis_reuses_provider_results',case['delivery_location']['new_provider_queries']==0)
     check('reanalysis_history_is_preserved',sum(e['kind']=='investigation_updated' for e in case['timeline'])>=2)
    results[name]={'label':intended['label'],'precision':intended['precision'],'accuracy_label':intended['accuracy_label'],'reported_label':reported['label'],'reported_accuracy':reported['accuracy_label'],'distance_m':location['comparisons'][0]['distance_m']}
   elif name=='ambiguous':check('ambiguous_address_has_no_selected_coordinates',intended['status']=='ambiguous' and 'lat' not in intended and len(intended['candidates'])>1)
   else:check('missing_landmark_not_replaced_by_city',intended['status']=='no_compatible_result' and 'lat' not in intended)
   if a.phase=='wait':row['fingerprint']=fingerprint(case);save()
   else:check(name+'_persists_across_deployment',fingerprint(case)==row['fingerprint'])
  ok(c.post('/api/auth/logout'));check('logout_revokes_access',c.get(route).status_code==401)
  ok(c.post('/api/auth/login',json={k:state['actors'][0][k] for k in ('username','password')}))
  check('login_preserves_records',fingerprint(ok(c.get(route)))==row['fingerprint'])
  report={'checked_at':datetime.now(timezone.utc).isoformat(),'base_url':a.base,'phase':a.phase,'checks':checks,'results':results,'all_passed':all(checks.values()),'controlled_workflow_retries':state.get('controlled_workflow_retries',0),'diagnostic_conditions':state.get('diagnostic_conditions',[]),'scope':'Two ordinary automated accounts and three authored fictional cases with public landmarks. Actual Photon, durable cloud and Gemini APIs; source upload alone queues investigations. Any controlled recovery after a test interruption is listed explicitly. Not a human usability or browser visual test.','paid_services_enabled':False,'provider_business_writes':0}
  a.report.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
 finally:
  for c in clients:c.close()
  save()

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--phase',choices=['prepare','wait','verify'],required=True);p.add_argument('--state',type=Path,default=ROOT/'runtime/saas-geocoding-acceptance-private.json');p.add_argument('--report',type=Path,default=ROOT/'work/geocoding-acceptance.json');run(p.parse_args())
