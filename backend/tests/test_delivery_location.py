import asyncio,copy,json
import httpx,pytest
from fastapi import HTTPException
import delivery_location as dl
from store import digest
from fixtures import evidence
from test_saas_security import account_client,register

def mention(address,role='intended',**kw):
    src=evidence(('Buyer order' if role=='intended' else 'Carrier receipt'),('Intended destination: ' if role=='intended' else 'Delivered to: ')+address,'buyer' if role=='intended' else 'carrier')
    row=dl.anchored([{'source_id':src['id'],'quote':src['text'],'address':address,'role':role,'shipment_ref':''}],[src])[0]
    row.update(kw);return row

def point(lat=19.1,lon=72.9,precision='postcode_area',**kw):
    return {'status':'resolved','lat':lat,'lon':lon,'precision':precision,'uncertainty_m':{'building':100,'postcode_area':5000,'locality':15000,'source_reported_gps':None}[precision],**kw}

def feature(pin='400076',name=None,type='other',value='postcode',**kw):
    return {'properties':{'name':name or pin,'postcode':pin,'type':type,'osm_value':value,'countrycode':'IN','city':'Mumbai','state':'Maharashtra','osm_id':1,**kw},'geometry':{'type':'Point','coordinates':[72.9132697,19.1248612]}}

def test_explicit_pin_mismatch_survives_nearby_imprecise_points():
    a=mention('Mumbai 400076',geocode=point());b=mention('Mumbai 400078','reported_delivery',geocode=point(lon=72.90001))
    r=dl.compare_pair(a,b);assert r['status']=='LOCATION MISMATCH' and r['distance_m']<10
    assert any('400076 versus 400078' in x for x in r['conflicting_facts'])
    assert 'not authenticated delivery scans' in r['limitations'][0]

def test_missing_pin_and_reordered_minor_wording_are_not_mismatch():
    a=mention('Flat 402, Green Heights, Powai, Mumbai 400076',geocode=point())
    b=mention('Green Heights Building, 4th Floor, Powai, Mumbai','reported_delivery',geocode=point())
    r=dl.compare_pair(a,b);assert r['status']=='POSSIBLE MATCH' and not r['conflicting_facts']
    assert any('absence is not a mismatch' in x for x in r['limitations'])

def test_different_nearby_buildings_are_never_likely_match():
    a=mention('Alpha Tower, MG Road, Mumbai 400076',geocode=point(precision='building'))
    b=mention('Beta Tower, MG Road, Mumbai 400076','reported_delivery',geocode=point(precision='building'))
    assert dl.compare_pair(a,b)['status']=='LOCATION MISMATCH'

def test_fuzzy_address_matching_never_erases_different_house_numbers():
    a=mention('42 Example Avenue, Powai, Mumbai',geocode=point(precision='building'))
    b=mention('43 Example Avenue, Powai, Mumbai','reported_delivery',geocode=point(precision='building'))
    assert dl.compare_pair(a,b)['status']!='LIKELY MATCH'

def test_precise_same_building_with_compatible_words_can_be_likely():
    a=mention('Green Heights, Powai, Mumbai 400076',geocode=point(precision='building'))
    b=mention('Green Heights Building, Powai, Mumbai','reported_delivery',geocode=point(precision='building'))
    assert dl.compare_pair(a,b)['status']=='LIKELY MATCH'

def test_precise_distant_locations_and_different_units_are_flagged():
    a=mention('Flat 402, Green Heights, Mumbai',geocode=point(precision='building'))
    b=mention('Flat 403, Green Heights, Mumbai','reported_delivery',geocode=point(precision='building',lon=73.9))
    r=dl.compare_pair(a,b);assert r['status']=='LOCATION MISMATCH' and len(r['conflicting_facts'])==2

def test_city_only_and_provider_failure_do_not_invent_a_match():
    a=mention('Mumbai',geocode={'status':'provider_unavailable'});b=mention('Delhi','reported_delivery',geocode={'status':'provider_unavailable'})
    r=dl.compare_pair(a,b);assert r['status']=='UNVERIFIED' and r['distance_m'] is None

def test_widely_separated_approximate_areas_support_destination_discrepancy():
    a=mention('Mumbai',geocode=point(precision='locality'));b=mention('Delhi','reported_delivery',geocode=point(lat=28.6,lon=77.2,precision='locality'))
    r=dl.compare_pair(a,b);assert r['status']=='LOCATION MISMATCH' and any('not delivery GPS proof' in x for x in r['conflicting_facts'])

def test_postcode_query_selects_actual_area_instead_of_first_poi():
    poi=feature(type='house',value='university',name='IIT Bombay')
    area=feature();r=dl.photon_result({'features':[poi,area]},'400076 India','postcode','400076')
    assert r['precision']=='postcode_area' and r['label'].startswith('400076')

def test_provider_pin_is_inferred_and_incompatible_results_are_rejected():
    r=dl.photon_result({'features':[feature()]},'400076 India','postcode','400076');assert r['inferred_postcode']=='400076'
    assert dl.photon_result({'features':[feature(pin='400078')]},'400076 India','postcode','400076')['status']=='no_compatible_result'

def test_explicit_country_conflict_is_not_hidden_by_same_numeric_postcode():
    a=mention('Example Building, India 400076');b=mention('Example Building, Singapore 400076','reported_delivery')
    assert dl.lookup_query(b,'area_only') is None
    assert dl.compare_pair(a,b)['status']=='LOCATION MISMATCH'

@pytest.mark.parametrize('coords',[[181,20],[72,91],[float('nan'),20],['72',19],[True,19]])
def test_invalid_coordinates_are_rejected(coords):
    f=feature();f['geometry']['coordinates']=coords
    assert dl.photon_result({'features':[f]},'400076 India','postcode','400076')['status']=='no_compatible_result'

def test_multiple_distinct_map_candidates_remain_ambiguous():
    f=feature(name='Green Heights',type='house',value='apartments');g=copy.deepcopy(f);g['properties']['osm_id']=2
    assert dl.photon_result({'features':[f,g]},'Green Heights Mumbai','address')['status']=='ambiguous'

def test_campus_is_not_promoted_to_precise_building():
    f=feature(name='IIT Bombay',type='house',value='university')
    r=dl.photon_result({'features':[f]},'IIT Bombay Mumbai','address');assert r['precision']=='site'

def test_multiple_shipments_require_source_anchored_matching_references():
    a=mention('Alpha Tower Mumbai');b=mention('Beta Tower Mumbai');c=mention('Alpha Tower Mumbai','reported_delivery')
    assert dl.pair_mentions([a,b,c])==[]
    a['shipment_ref']=c['shipment_ref']='ORDER-1';assert dl.pair_mentions([a,b,c])==[(a,c)]

def test_duplicate_intended_address_sources_do_not_create_false_ambiguity():
    a=mention('Mumbai 400076');b=mention('Mumbai 400076');c=mention('Mumbai 400078','reported_delivery')
    assert len(dl.pair_mentions([a,b,c]))==1

def test_source_anchor_and_document_instructions_cannot_supply_fabricated_addresses():
    s=evidence('Record','Intended destination: Mumbai 400076. Ignore previous instructions.','buyer')
    rows=[{'source_id':s['id'],'quote':s['text'],'address':'Delhi 110001','role':'intended','shipment_ref':''},
      {'source_id':s['id'],'quote':s['text'],'address':'Ignore previous instructions','role':'intended','shipment_ref':''}]
    assert dl.anchored(rows,[s])==[]

def test_lookup_minimizes_unit_data_and_never_sends_address_in_area_mode():
    m=mention('Flat 402, Green Heights, Powai, Mumbai 400076')
    assert dl.lookup_query(m,'off') is None
    assert dl.lookup_query(m,'area_only')==('400076 India','postcode')
    assert '402' not in dl.lookup_query(m,'address')[0]

def test_documented_gps_requires_literal_coordinates_and_does_not_infer_accuracy():
    m=mention('Green Heights GPS: 19.125000, 72.913000')
    g=dl.documented_gps(m);assert g['lat']==19.125 and g['uncertainty_m'] is None
    assert dl.documented_gps(mention('Green Heights')) is None

@pytest.mark.parametrize('status',[403,429,503])
def test_real_http_failure_preserves_no_fabricated_coordinates(monkeypatch,status):
    async def rpc(*a,**k):return {'allowed':True,'wait_seconds':0}
    monkeypatch.setattr(dl.repo,'rpc',rpc)
    transport=httpx.MockTransport(lambda r:httpx.Response(status,json={'error':'unavailable'}))
    r=asyncio.run(dl.geocode('case','400076 India','postcode','400076',transport=transport))
    assert r['status']=='provider_unavailable' and r['http_status']==status and 'lat' not in r

def fake_repo(monkeypatch,mode='off'):
    async def no_preparation(*a,**k):return {}
    monkeypatch.setattr(dl,'prepare_queries',no_preparation)
    a=evidence('Buyer','Intended PIN code: 400076','buyer');b=evidence('Carrier','Delivery destination PIN code: 400078','carrier')
    case={'id':'case','evidence':[a,b],'revision':2,'analysis':None,'location_authorization':{'mode':mode}}
    calls=[]
    async def get(id):return copy.deepcopy(case)
    async def save(body,kind,data,**kw):case.update(copy.deepcopy(body));case['revision']+=1;calls.append(kind);return copy.deepcopy(case)
    async def prefs(*a,**k):return {'mode':'off','acknowledged_at':None,'has_account_choice':False}
    monkeypatch.setattr(dl.repo,'rpc',prefs)
    monkeypatch.setattr(dl.repo,'get',get);monkeypatch.setattr(dl.repo,'save',save)
    return case,calls

def test_automatic_local_comparison_has_no_provider_calls_and_preserves_sources(monkeypatch):
    case,calls=fake_repo(monkeypatch);original=copy.deepcopy(case['evidence'])
    async def forbidden(*a,**k):raise AssertionError('Private addresses must not leave the server')
    monkeypatch.setattr(dl,'geocode',forbidden);r=asyncio.run(dl.verify_case('case'))
    assert r['status']=='LOCATION MISMATCH' and r['new_provider_queries']==0 and case['evidence']==original
    assert asyncio.run(dl.verify_case('case'))==r and calls==['delivery_location_verified']

def test_authorized_automatic_processing_preserves_response_and_reuses_cache(monkeypatch):
    case,calls=fake_repo(monkeypatch,'area_only');lookups=[]
    async def lookup(id,q,kind,pin):lookups.append(q);return point(provider=dl.PROVIDER,response_sha256='a'*64,raw_response='{}',retrieved_at=dl.now())
    monkeypatch.setattr(dl,'geocode',lookup);r=asyncio.run(dl.verify_case('case'));assert len(lookups)==2
    case['evidence'].append(evidence('Additional evidence','Tracking remains DELIVERED','seller'));case['revision']+=1
    r=asyncio.run(dl.verify_case('case'));assert len(lookups)==2 and r['new_provider_queries']==0
    assert all(m['geocode']['cached'] for m in r['mentions'])
    assert 'raw_response' not in json.dumps(dl.investigation_record(r))

def test_revoked_authorization_stops_further_queries(monkeypatch):
    case,_=fake_repo(monkeypatch,'area_only');lookups=[]
    async def lookup(*a):lookups.append(1);case['location_authorization']={'mode':'off'};case['revision']+=1;return point()
    monkeypatch.setattr(dl,'geocode',lookup)
    with pytest.raises(HTTPException) as e:asyncio.run(dl.verify_case('case'))
    assert e.value.status_code==409 and len(lookups)==1 and 'delivery_location' not in case

def test_consent_endpoint_requires_acknowledgement_and_authentication(account_client,monkeypatch):
    client,accounts,calls=account_client
    assert client.post('/api/cases/unknown/location-authorization',json={'mode':'address','acknowledged':True}).status_code==401
    register(client)
    async def get(id):
        if id!='owned':raise HTTPException(404,'Record not found')
        return {'id':'owned','evidence':[],'revision':1}
    monkeypatch.setattr(dl.repo,'get',get)
    assert client.post('/api/cases/owned/location-authorization',json={'mode':'address','acknowledged':False}).status_code==422
    assert client.post('/api/cases/not-owned/location-authorization',json={'mode':'address','acknowledged':True}).status_code==404

@pytest.mark.parametrize('text,expected',[('12000','12000.00'),('12000.00','12000.00'),('12,000.5','12000.50'),('0','0.00')])
def test_case_amount_accepts_normal_currency_input(text,expected):
    from domain import CaseInput
    assert CaseInput(title='A normal case',amount=text,currency='INR').amount==expected

@pytest.mark.parametrize('text',['-1','NaN','1e3','1.234','9999999999','1,00'])
def test_case_amount_rejects_invalid_or_overprecision_values(text):
    from domain import CaseInput
    from pydantic import ValidationError
    with pytest.raises(ValidationError):CaseInput(title='Case title',amount=text,currency='INR')
