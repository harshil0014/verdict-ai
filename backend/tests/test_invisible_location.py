"""Address identity is evidence; proximity alone is never identity or delivery proof."""
import asyncio,copy
import pytest
import delivery_location as dl
from fixtures import evidence
from test_delivery_location import mention,point,fake_repo
from test_geocoding_recovery import PUBLIC,IIT,BHANDUP

def test_different_buildings_fifty_metres_apart_are_a_description_mismatch():
    a=mention('Alpha Tower, Powai, Mumbai',geocode=point(precision='building'))
    b=mention('Beta Tower, Powai, Mumbai','reported_delivery',geocode=point(precision='building',lat=19.10045))
    r=dl.compare_pair(a,b)
    assert 40<r['distance_m']<60 and r['status']=='LOCATION MISMATCH'
    assert r['result_label']=="Delivery address doesn't match" and 'physical delivery' in r['explanation']

def test_written_variants_same_building_with_small_map_error_match():
    a=mention('Flat 402, Green Heights Building, Powai, Mumbai 400076',geocode=point(precision='building'))
    b=mention('Green Heights, 4th Floor, Powai, Mumbai','reported_delivery',geocode=point(precision='building',lat=19.10135))
    r=dl.compare_pair(a,b)
    assert 140<r['distance_m']<160 and r['status']=='LIKELY MATCH'
    assert r['result_label']=='Delivery address matches' and 'absence is not a mismatch' in ' '.join(r['limitations'])

def test_precision_specific_tolerance_is_configurable_and_never_erases_identity(monkeypatch):
    monkeypatch.setenv('VERDICT_LOCATION_PROXIMITY_METRES','100')
    a=mention('Green Heights, Mumbai',geocode=point(precision='building'))
    b=mention('Green Heights Building, Mumbai','reported_delivery',geocode=point(precision='building',lat=19.10135))
    r=dl.compare_pair(a,b);assert r['proximity_tolerance_m']==100 and r['status']=='POSSIBLE MATCH'
    monkeypatch.setenv('VERDICT_LOCATION_PROXIMITY_METRES','200')
    assert dl.compare_pair(a,b)['status']=='LIKELY MATCH'
    for invalid in ('NaN','inf','-10','0','5000','banana'):
        monkeypatch.setenv('VERDICT_LOCATION_PROXIMITY_METRES',invalid);assert dl.proximity_tolerance()==200

def test_actual_landmarks_override_broad_campus_uncertainty():
    ga=dl.photon_result(PUBLIC[0]['data'],IIT,'address');gb=dl.photon_result(PUBLIC[3]['data'],BHANDUP,'address')
    a=mention(IIT,geocode=ga);b=mention(BHANDUP,'reported_delivery',geocode=gb)
    r=dl.compare_pair(a,b)
    assert r['status']=='LOCATION MISMATCH' and r['distance_m']==2740
    assert not r['sufficiently_precise'] and 'IIT Bombay Main Gate' in r['explanation'] and 'Bhandup Railway Station' in r['explanation']
    assert 'different named destinations' in ' '.join(r['conflicting_facts'])

def test_campus_and_postcode_estimates_never_become_precise_even_when_identical():
    for precision in ('site','postcode_area'):
        g=point();g.update(precision=precision,uncertainty_m=1000)
        a=mention('IIT Bombay, Powai, Mumbai',geocode=g);b=mention('Indian Institute of Technology Bombay, Powai, Mumbai','reported_delivery',geocode=copy.deepcopy(g))
        r=dl.compare_pair(a,b);assert r['status']=='POSSIBLE MATCH' and not r['sufficiently_precise']

def test_same_city_or_postcode_is_not_an_address_match():
    a=mention('Mumbai 400076',geocode=point());b=mention('Mumbai 400076','reported_delivery',geocode=point())
    assert dl.compare_pair(a,b)['status']=='UNVERIFIED'

def test_same_name_different_street_details_need_reconciliation_even_at_same_point():
    a=mention('Green Heights, Alpha Road, Mumbai',geocode=point(precision='building'))
    b=mention('Green Heights, Beta Road, Mumbai','reported_delivery',geocode=point(precision='building'))
    r=dl.compare_pair(a,b);assert r['status']=='UNVERIFIED' and 'Street or locality details differ' in ' '.join(r['limitations'])
    b=mention('Green Heights Building, Mumbai','reported_delivery',geocode=point(precision='building'))
    assert dl.compare_pair(a,b)['status']=='LIKELY MATCH'

def test_ambiguous_map_remains_unverified_for_compatible_names():
    g={'status':'ambiguous','candidates':[{},{}]}
    a=mention('Green Heights, Mumbai',geocode=g);b=mention('Green Heights Building, Mumbai','reported_delivery',geocode=g)
    r=dl.compare_pair(a,b);assert r['status']=='UNVERIFIED' and r['distance_m'] is None

def test_source_coordinates_remain_in_diagnostics_and_not_in_public_explanation():
    a=mention('Green Heights GPS: 19.125000, 72.913000')
    b=mention('Green Heights Building GPS: 19.126000, 72.914000','reported_delivery')
    r=dl.compare_pair(a,b);assert r['status']=='POSSIBLE MATCH'
    assert 'GPS' not in r['explanation'] and '19.12' not in r['explanation'] and '72.91' not in r['explanation']

def test_provider_unavailability_does_not_block_clear_source_contradictions_or_invent_points():
    g={'status':'provider_unavailable'}
    a=mention(IIT,geocode=g);b=mention(BHANDUP,'reported_delivery',geocode=g)
    r=dl.compare_pair(a,b);assert r['status']=='LOCATION MISMATCH' and r['distance_m'] is None
    assert not r['sufficiently_precise'] and 'physical delivery' in r['explanation']
    b=mention('Indian Institute of Technology Bombay Main Entrance, Powai, Mumbai, Maharashtra','reported_delivery',geocode=g)
    assert dl.compare_pair(a,b)['status']=='POSSIBLE MATCH'

def test_conflicting_building_identifiers_survive_nearly_identical_spelling_and_points():
    a=mention('Green Heights Tower A, Mumbai',geocode=point(precision='building'))
    b=mention('Green Heights Tower B, Mumbai','reported_delivery',geocode=point(precision='building'))
    assert dl.compare_pair(a,b)['status']=='LOCATION MISMATCH'

def test_comparison_upgrade_reuses_original_preserved_locations_without_external_calls(monkeypatch):
    case,calls=fake_repo(monkeypatch,'address')
    case['evidence']=[evidence('Order','Intended destination: '+IIT,'buyer'),evidence('Delivery','Delivery destination: '+BHANDUP,'carrier')]
    mentions=dl.local_mentions(case['evidence'])
    for m in mentions:m['geocode']=dl.photon_result(PUBLIC[0 if m['role']=='intended' else 3]['data'],m['address'],'address')
    old={'version':2,'input_digest':dl.digest({'version':2,'evidence':[(s['id'],s['sha256']) for s in case['evidence']],'authorization':{'mode':'address','acknowledged_at':None}}),'mentions':mentions,'status':'POSSIBLE MATCH','lookup_cache':{},'extraction':'Original parser'}
    case['delivery_location']=copy.deepcopy(old);original=copy.deepcopy(case['evidence'])
    async def forbidden(*a,**k):raise AssertionError('Comparison-only upgrade must not send addresses or invoke extraction')
    monkeypatch.setattr(dl,'geocode',forbidden);monkeypatch.setattr(dl,'generate',forbidden)
    r=asyncio.run(dl.verify_case('case'))
    assert r['version']==3 and r['status']=='LOCATION MISMATCH' and r['comparison_only_upgrade'] and r['new_provider_queries']==0
    assert r['mentions']==old['mentions'] and case['evidence']==original and calls==['delivery_location_verified']
    assert asyncio.run(dl.verify_case('case'))==r
