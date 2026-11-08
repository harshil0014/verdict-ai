"""Frozen real public results plus explicitly synthetic fault/security transports."""
import asyncio,copy,json
from pathlib import Path
import pytest
from fastapi import HTTPException
import delivery_location as dl
from fixtures import evidence
from test_delivery_location import feature,fake_repo

IIT='IIT Bombay Main Gate, Powai, Mumbai, Maharashtra'
BHANDUP='Bhandup Railway Station, Bhandup West, Mumbai, Maharashtra'
PUBLIC=json.loads((Path(__file__).parent/'data/photon-mumbai-public.json').read_text(encoding='utf-8'))['responses']

def test_real_campus_is_not_rejected_by_abbreviation_or_confused_with_staff_housing():
    r=dl.photon_result(PUBLIC[0]['data'],IIT,'address')
    assert r['status']=='resolved' and r['osm_id']==8546708
    assert r['precision']=='site' and r['match_scope']=='parent_campus'
    assert r['lat']==19.1326186 and r['lon']==72.9149702
    assert 'exact gate' in r['accuracy_label'] and r['uncertainty_m']>=1000

def test_real_bhandup_result_is_honestly_a_transit_stop_not_a_train_platform():
    r=dl.photon_result(PUBLIC[3]['data'],BHANDUP,'address')
    assert r['status']=='resolved' and r['provider_properties']['osm_value']=='bus_station'
    assert r['precision']=='site' and 'platform not confirmed' in r['accuracy_label']

def test_plan_preserves_named_identity_and_city_state_without_postcode():
    plan=dl.lookup_plan(IIT,'address')
    assert len(plan)==4 and 'Indian Institute of Technology' in plan[1][0]
    assert 'Gate' not in plan[2][0] and 'Powai' not in plan[3][0]
    assert all(q.endswith('Mumbai, Maharashtra') for q,_ in plan)
    assert dl.lookup_plan('Unknown Palace, Powai, Mumbai, Maharashtra','address')[-1][0]=='Unknown Palace, Mumbai, Maharashtra'
    assert dl.lookup_plan('400076 India','postcode')==[('400076 India','original')]

@pytest.mark.parametrize('change',[{'city':'Delhi'},{'state':'Karnataka'},{'countrycode':'CA'},{'locality':'Somewhere Else'}])
def test_original_geographic_constraints_apply_to_less_specific_queries(change):
    f=copy.deepcopy(PUBLIC[0]['data']['features'][0]);f['properties'].update(change)
    address=IIT+', India' if 'countrycode' in change else IIT
    assert dl.photon_result({'features':[f]},'Indian Institute of Technology Bombay','address',address=address)['status']=='no_compatible_result'

def test_exact_real_gate_type_beats_parent_and_bus_stop_never_becomes_gate():
    campus=copy.deepcopy(PUBLIC[0]['data']['features'][0])
    gate=feature(name='Indian Institute of Technology Bombay Main Gate',type='house',value='gate',osm_key='barrier',locality='Powai',osm_id=99)
    r=dl.photon_result({'features':[campus,gate]},IIT,'address')
    assert r['osm_id']==99 and r['precision']=='entrance' and r['match_scope']=='named_location'
    gate['properties'].update(osm_value='bus_stop',osm_key='highway')
    r=dl.photon_result({'features':[gate]},IIT,'address');assert r['status']=='no_compatible_result'

def test_missing_landmark_is_not_satisfied_by_city_or_partial_name():
    for f in [feature(name='Mumbai',type='city',value='city'),feature(name='Unknown Palace Staff Housing',type='house',value='apartments')]:
        assert dl.photon_result({'features':[f]},'Unknown Palace, Mumbai, Maharashtra','address')['status']=='no_compatible_result'

def test_two_identically_named_places_remain_ambiguous_even_with_city_context():
    a=feature(name='Central Station',type='house',value='station',osm_key='railway');b=copy.deepcopy(a);b['properties']['osm_id']=2
    r=dl.photon_result({'features':[a,b]},'Central Station, Mumbai, Maharashtra','address')
    assert r['status']=='ambiguous' and len(r['candidates'])==2 and 'lat' not in r

def address_case(monkeypatch):
    case,calls=fake_repo(monkeypatch,'address')
    case['evidence']=[evidence('Public landmark test','Intended destination: '+IIT,'buyer'),evidence('Fictional delivery report','Delivery destination: '+BHANDUP,'carrier')]
    return case,calls

def test_automatic_fallback_maps_both_retains_provenance_and_reuses_cache(monkeypatch):
    case,_=address_case(monkeypatch);original=copy.deepcopy(case['evidence']);lookups=[]
    async def lookup(id,q,kind,pin):
        lookups.append(q);data=PUBLIC[3 if q.startswith('Bhandup') else 0]['data']
        # Force the originally failed query to have no result, then acquire a
        # campus with the alternate full name. This is a synthetic fault path.
        if q==IIT:data={'features':[]}
        raw=json.dumps(data);return dl.photon_result(data,q,kind,pin)|{'raw_response':raw,'response_sha256':dl.digest(raw.encode()),'retrieved_at':dl.now(),'query':q}
    monkeypatch.setattr(dl,'geocode',lookup)
    r=asyncio.run(dl.verify_case('case'))
    assert lookups[:2]==[IIT,BHANDUP] and len(lookups)==4
    assert len(r['comparisons'])==1 and r['comparisons'][0]['distance_m']>2000
    a,b=r['mentions'];assert a['geocode']['precision']=='site' and b['geocode']['status']=='resolved'
    assert a['geocode']['attempts'][0]['status']=='no_compatible_result' and len(a['geocode']['attempts'])==3
    assert 'exact gate' in a['geocode']['accuracy_label'] and a['geocode']['fallback_used']
    assert all(x['result'].get('raw_response') for x in r['lookup_cache'].values()) and case['evidence']==original
    case['evidence'].append(evidence('Unrelated','Tracking status DELIVERED','seller'));case['revision']+=1
    again=asyncio.run(dl.verify_case('case'));assert len(lookups)==4 and again['new_provider_queries']==0
    assert 'raw_response' not in json.dumps(dl.investigation_record(again))
    assert 'exact gate' in json.dumps(dl.investigation_record(again))

def test_revocation_between_fallback_queries_stops_disclosure(monkeypatch):
    case,_=address_case(monkeypatch);calls=[]
    async def lookup(*args):
        calls.append(1);case['location_authorization']={'mode':'off'};case['revision']+=1
        return {'status':'no_compatible_result'}
    monkeypatch.setattr(dl,'geocode',lookup)
    with pytest.raises(HTTPException) as err:asyncio.run(dl.verify_case('case'))
    assert err.value.status_code==409 and len(calls)==1 and 'delivery_location' not in case

def test_outages_stop_name_fallback_without_sending_four_duplicate_outage_requests(monkeypatch):
    case,_=address_case(monkeypatch);calls=[]
    async def lookup(*args):calls.append(1);return {'status':'provider_unavailable','http_status':503}
    monkeypatch.setattr(dl,'geocode',lookup);r=asyncio.run(dl.verify_case('case'))
    assert len(calls)==2 and r.get('retry_at')
    assert all('lat' not in m['geocode'] for m in r['mentions'])

def test_bounded_failed_queries_keep_other_addresses_and_never_invent_coordinates(monkeypatch):
    case,_=address_case(monkeypatch);calls=[]
    async def lookup(*args):calls.append(args[1]);return {'status':'no_compatible_result'}
    monkeypatch.setattr(dl,'geocode',lookup);r=asyncio.run(dl.verify_case('case'))
    assert calls[:2]==[IIT,BHANDUP] and len(calls)<=8
    assert all(m['geocode']['status']=='no_compatible_result' and 'lat' not in m['geocode'] for m in r['mentions'])

def test_different_plausible_campuses_across_alternate_queries_remain_ambiguous(monkeypatch):
    case,_=address_case(monkeypatch)
    async def lookup(id,q,kind,pin):
        data=copy.deepcopy(PUBLIC[3 if q.startswith('Bhandup') else 0]['data'])
        if q.startswith('Indian'):data['features'][0]['properties']['osm_id']=999
        raw=json.dumps(data);return dl.photon_result(data,q,kind,pin)|{'raw_response':raw,'response_sha256':dl.digest(raw.encode()),'query':q,'retrieved_at':dl.now()}
    monkeypatch.setattr(dl,'geocode',lookup);r=asyncio.run(dl.verify_case('case'))
    g=next(m['geocode'] for m in r['mentions'] if m['role']=='intended')
    assert g['status']=='ambiguous' and 'lat' not in g and len(g['candidates'])==2
