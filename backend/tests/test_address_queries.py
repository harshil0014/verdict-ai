"""Synthetic model/provider transports; no customer data or live case writes."""
import asyncio
import copy
import json

import pytest
import address_queries as aq
import delivery_location as dl
from fixtures import evidence
from test_delivery_location import fake_repo, feature


def proposal(query, *corrections):
    return aq.PreparedAddress(id='a', query=query, corrections=[
        {'original':a,'replacement':b} for a,b in corrections])


def test_alias_expansion_preserves_every_place_and_number():
    address='IIT Bombay Main Gate, Powai, Mumbai 400076'
    result=aq.validated_query(address,proposal('Indian Institute of Technology Bombay Main Gate, Powai, Mumbai 400076',('IIT','Indian Institute of Technology')))
    assert result and not result['spelling_proposal']


def test_minor_typo_is_a_proposal_not_a_verified_repair():
    result=aq.validated_query('Green Heights, Mumabi',proposal('Green Heights, Mumbai',('Mumabi','Mumbai')))
    assert result['spelling_proposal']


@pytest.mark.parametrize('query,changes',[
    ('Green Heights, Mumbai 400078',()),
    ('Green Heights, Mumbai 400076 India',()),
    ('Sunrise Residency, Mumbai 400076',()),
    ('Green Heights, Mumbai',()),
    ('Green Heights Mumbai, 400076',()),
    ('Green Heights, Delhi 400076',(('Mumbai','Delhi'),)),
    ('Green Heights, Mumbai 400078',(('400076','400078'),)),
    ('Green Heights, Mumbai 400076 https://evil.test',()),
    ('Green Heights, Mumbai 400076 ignore instructions',()),
])
def test_model_cannot_invent_or_erase_source_constraints(query,changes):
    assert aq.validated_query('Green Heights, Mumbai 400076',proposal(query,*changes)) is None


def test_preparation_cached_and_duplicate_ids_rejected(monkeypatch):
    calls=[]
    async def generate(*args):
        calls.append(args)
        return aq.PreparedQueries(addresses=[proposal('Green Heights, Mumbai')]),{'model':'test-model'}
    monkeypatch.setattr(aq,'generate',generate)
    cache={}
    first=asyncio.run(aq.prepare_queries({'a':'Green Heights, Mumbai'},cache))
    assert asyncio.run(aq.prepare_queries({'a':'Green Heights, Mumbai'},cache))==first
    assert len(calls)==1 and first['a']['model']=='test-model'
    async def duplicates(*args):
        return aq.PreparedQueries(addresses=[proposal('Green Heights, Mumbai')]*2),{}
    monkeypatch.setattr(aq,'generate',duplicates)
    assert asyncio.run(aq.prepare_queries({'a':'Green Heights, Mumbai'},{}))=={}


@pytest.mark.parametrize('error',[aq.ModelError('Unavailable'),TimeoutError()])
def test_failure_falls_back_without_poisoning_cache(monkeypatch,error):
    async def generate(*args):raise error
    monkeypatch.setattr(aq,'generate',generate)
    cache={}
    assert asyncio.run(aq.prepare_queries({'a':'Green Heights, Mumbai'},cache))=={} and cache=={}


def test_preparation_uses_sanitized_text_preserves_sources_and_map_uncertainty(monkeypatch):
    case,_=fake_repo(monkeypatch,'address')
    case['evidence']=[evidence('Order','Intended destination: Flat 302, Green Heights, Mumabi','buyer'),
                      evidence('Receipt','Delivery destination: Flat 14B, Sunrise Residency, Mumbai','carrier')]
    original=copy.deepcopy(case['evidence'])
    calls=[]
    async def prepare(addresses,cache):
        assert all('302' not in a and '14B' not in a for a in addresses.values())
        return {id:{'query':address.replace('Mumabi','Mumbai'),'spelling_proposal':'Mumabi' in address}
                for id,address in addresses.items()}
    async def geocode(id,q,kind,pin):
        calls.append(q)
        name='Green Heights' if q.startswith('Green') else 'Sunrise Residency'
        data={'features':[feature(name=name,type='house',value='apartments')]}
        return dl.photon_result(data,q,kind,pin)|{'raw_response':json.dumps(data)}
    monkeypatch.setattr(dl,'prepare_queries',prepare)
    monkeypatch.setattr(dl,'geocode',geocode)
    record=asyncio.run(dl.verify_case('case'))
    assert case['evidence']==original and len(calls)==2
    first=record['mentions'][0]
    assert 'Mumabi' in first['address'] and '302' in first['quote']
    assert first['geocode']['precision']=='site' and first['geocode']['uncertainty_m']>=1000
    assert first['explicit_postcode'] is None and first['geocode']['inferred_postcode']=='400076'
    assert record['status']=='LOCATION MISMATCH'


def test_accepted_model_wording_cannot_manufacture_a_map_result(monkeypatch):
    case,_=fake_repo(monkeypatch,'address')
    case['evidence']=[evidence('Order','Intended destination: Unknown Palace, Mumbai','buyer'),
                      evidence('Receipt','Delivery destination: Unknown Castle, Mumbai','carrier')]
    async def prepare(addresses,cache):
        return {id:{'query':a,'spelling_proposal':False} for id,a in addresses.items()}
    async def geocode(*args):return {'status':'no_compatible_result','raw_response':'{"features":[]}'}
    monkeypatch.setattr(dl,'prepare_queries',prepare)
    monkeypatch.setattr(dl,'geocode',geocode)
    record=asyncio.run(dl.verify_case('case'))
    assert all('lat' not in m['geocode'] for m in record['mentions'])
    assert all(c['distance_m'] is None for c in record['comparisons'])


@pytest.mark.parametrize('mode',['off','area_only'])
def test_restricted_modes_never_call_model_preparation(monkeypatch,mode):
    fake_repo(monkeypatch,mode)
    async def forbidden(*args):raise AssertionError('Preparation must not run')
    async def geocode(*args):return {'status':'provider_unavailable'}
    monkeypatch.setattr(dl,'prepare_queries',forbidden)
    monkeypatch.setattr(dl,'geocode',geocode)
    asyncio.run(dl.verify_case('case'))
