import asyncio,copy
import pytest
from fastapi import HTTPException
from test_saas_security import account_client,register
import preferences as prefs
import delivery_location as dl
from fixtures import evidence

def test_account_map_preference_requires_explicit_consent_and_session(account_client,monkeypatch):
    client,accounts,calls=account_client
    assert client.get('/api/preferences').status_code==401
    register(client);original=prefs.repo.rpc;state={'mode':'off','acknowledged_at':None}
    async def rpc(op,args=None,**kw):
        if op=='experience:preferences':return state.copy()
        if op=='experience:set_maps':state.update(mode=args['mode'],acknowledged_at='2026-11-08');return state.copy()
        return await original(op,args,**kw)
    monkeypatch.setattr(prefs.repo,'rpc',rpc)
    assert client.get('/api/preferences').json()['mode']=='off'
    assert client.post('/api/preferences/maps',json={'mode':'address','acknowledged':False}).status_code==422
    assert state['mode']=='off'
    assert client.post('/api/preferences/maps',json={'mode':'address','acknowledged':True}).status_code==200
    assert client.post('/api/preferences/maps',json={'mode':'off'}).json()['mode']=='off'
    assert client.post('/api/preferences/maps',json={'mode':'address','acknowledged':True,'owner_id':'another'}).status_code==422

def test_explicit_case_off_wins_over_remembered_account_permission(monkeypatch):
    src=[evidence('Buyer','Intended destination PIN code: 400076','buyer'),evidence('Carrier','Reported delivery destination PIN code: 400078','carrier')]
    case={'id':'case','revision':1,'evidence':src,'location_authorization':{'mode':'off'},'analysis':None}
    async def get(id):return copy.deepcopy(case)
    async def save(body,*a,**k):case.update(body);return body
    async def rpc(op,*a,**k):return {'mode':'address','acknowledged_at':'2026-11-08'}
    async def forbidden(*a,**k):raise AssertionError('Explicit case revocation must prevent geocoding')
    monkeypatch.setattr(dl.repo,'get',get);monkeypatch.setattr(dl.repo,'save',save);monkeypatch.setattr(dl.repo,'rpc',rpc);monkeypatch.setattr(dl,'geocode',forbidden)
    result=asyncio.run(dl.verify_case('case'));assert result['authorization_mode']=='off' and result['new_provider_queries']==0

def test_unavailable_geocoder_sets_durable_retry_but_permanent_refusal_does_not(monkeypatch):
    src=[evidence('Buyer','Intended PIN code: 400076','buyer'),evidence('Carrier','Reported delivery PIN code: 400078','carrier')]
    initial={'id':'case','revision':1,'evidence':src,'location_authorization':{'mode':'area_only'},'analysis':None};case=copy.deepcopy(initial)
    async def get(id):return copy.deepcopy(case)
    async def save(body,*a,**k):case.update(body);return body
    async def unavailable(*a,**k):return {'status':'provider_unavailable','http_status':503}
    monkeypatch.setattr(dl.repo,'get',get);monkeypatch.setattr(dl.repo,'save',save);monkeypatch.setattr(dl,'geocode',unavailable)
    assert asyncio.run(dl.verify_case('case'))['retry_at']
    case.clear();case.update(copy.deepcopy(initial))
    async def refused(*a,**k):return {'status':'provider_unavailable','http_status':403}
    monkeypatch.setattr(dl,'geocode',refused)
    assert 'retry_at' not in asyncio.run(dl.verify_case('case'))
