import asyncio
import copy
import json
import httpx
import pytest
from fastapi import HTTPException
import saas_paypal as pp
from paypal import PayPal,PayPalError
from test_saas_security import account_client,register


def fixture():
    detail={'dispute_id':'PP-D-UNIT','status':'WAITING_FOR_SELLER_RESPONSE','reason':'MERCHANDISE_OR_SERVICE_NOT_RECEIVED',
        'dispute_amount':{'value':'1.00','currency_code':'USD'},'messages':[{'content':'Private buyer email: hidden@example.test'}],
        'disputed_transactions':[{'seller_transaction_id':'CAP1','buyer_transaction_id':'BUY1','seller':{'merchant_id':'MERCHANT1','email':'seller@example.test'},'buyer':{'payer_id':'BUYER1','email':'hidden@example.test','name':'Private Name'}}]}
    cap={'id':'CAP1','status':'PENDING','amount':{'value':'5.00','currency_code':'USD'},'payee':{'merchant_id':'MERCHANT1','email_address':'seller@example.test'},'supplementary_data':{'related_ids':{'order_id':'ORDER1'}}}
    order={'id':'ORDER1','status':'COMPLETED','payer':{'payer_id':'BUYER1','email_address':'hidden@example.test'},'purchase_units':[{'payee':{'merchant_id':'MERCHANT1'},'shipping':{'address':{'address_line_1':'Private Road'}},'payments':{'captures':[{'id':'CAP1','amount':{'value':'5.00','currency_code':'USD'}}]}}]}
    return detail,[{'kind':'capture','id':'CAP1','body':cap},{'kind':'order','id':'ORDER1','body':order}],{'id':'unit-connection','merchant_id':'MERCHANT1','owner_id':'owner'}


def test_import_populates_distinct_payment_and_disputed_amounts_and_minimizes_pii():
    d,r,c=fixture();body,changed,snapshots,change=pp.prepare_import(None,d,r,[],1,c)
    assert changed and len(body['evidence'])==3 and len(snapshots)==3
    assert body['amount']=='1.00' and body['currency']=='USD'
    payment=body['paypal_account']['payments'][0]
    assert payment['payment_amount']['value']=='5.00' and payment['buyer_id']=='BUYER1'
    assert payment['linkage']=='verified_capture_and_order' and payment['status']=='PENDING'
    assert not any(x in json.dumps(body) for x in ['hidden@example.test','Private Name','Private Road','email_address'])
    assert all(e['provider_provenance']['canonical_json_sha256'] for e in body['evidence'])
    assert pp.prepare_import(body,d,r,[],1,c)[1] is False


def test_missing_buyer_and_disputed_amount_are_not_invented():
    d,r,c=fixture();d.pop('dispute_amount');d['disputed_transactions'][0].pop('buyer');r[1]['body'].pop('payer')
    body,_,_,_=pp.prepare_import(None,d,r,[],1,c)
    assert body['amount'] is None and body['currency'] is None
    assert body['paypal_account']['payments'][0]['buyer_id'] is None
    assert body['paypal_account']['payments'][0]['payment_date'] is None


def test_equivalent_capture_money_formats_match_without_rewriting_provider_values():
    d,r,c=fixture();r[1]['body']['purchase_units'][0]['payments']['captures'][0]['amount']['value']='5.0'
    body,_,_,_=pp.prepare_import(None,d,r,[],1,c)
    assert body['paypal_account']['payments'][0]['linkage']=='verified_capture_and_order'
    assert body['paypal_account']['payments'][0]['payment_amount']['value']=='5.00'


def test_provider_link_order_is_deduplicated_but_changed_actions_are_preserved():
    d,r,c=fixture();d['links']=[{'rel':'self','method':'GET','href':'https://api-m.sandbox.paypal.com/v1/customer/disputes/PP-D-UNIT'},
        {'rel':'send-message','method':'POST','href':'https://api-m.sandbox.paypal.com/v1/customer/disputes/PP-D-UNIT/send-message'}]
    original=copy.deepcopy(d);body,_,snapshots,_=pp.prepare_import(None,d,r,[],1,c)
    d['links'].reverse();again,changed,second,_=pp.prepare_import(body,d,r,[],1,c)
    assert not changed and snapshots[0]['sha256']==second[0]['sha256'] and len(again['evidence'])==3
    assert d['links']==list(reversed(original['links']))
    d['links'][0]['method']='PATCH'
    updated,changed,third,_=pp.prepare_import(body,d,r,[],1,c)
    assert changed and len(updated['evidence'])==4 and third[0]['sha256']!=snapshots[0]['sha256']


@pytest.mark.parametrize('change',[
    lambda d,r,c:d['disputed_transactions'][0]['seller'].update(merchant_id='OTHER'),
    lambda d,r,c:r[0]['body']['payee'].update(merchant_id='OTHER'),
    lambda d,r,c:r[1]['body']['payer'].update(payer_id='OTHER'),
    lambda d,r,c:r[1]['body']['purchase_units'][0]['payments']['captures'][0].update(id='OTHER'),
    lambda d,r,c:r[0]['body'].update(id='OTHER'),
    lambda d,r,c:r[1]['body']['purchase_units'][0]['payee'].update(merchant_id='OTHER'),
    lambda d,r,c:r[1]['body']['purchase_units'][0]['payments']['captures'][0]['amount'].update(value='6.00'),
])
def test_inconsistent_or_cross_merchant_records_are_rejected(change):
    d,r,c=fixture();change(d,r,c)
    with pytest.raises(HTTPException):pp.prepare_import(None,d,r,[],1,c)


def test_changed_snapshot_preserves_versions_and_existing_analysis_and_requests():
    d,r,c=fixture();body,_,_,_=pp.prepare_import(None,d,r,[],1,c)
    body.update(id='V-existing',analysis={'finding':'insufficient'},requests=[{'id':'W-existing'}])
    original=copy.deepcopy(body);r[0]['body']['status']='COMPLETED'
    new,changed,_,_=pp.prepare_import(body,d,r,[],1,c)
    assert changed and body==original and len(new['evidence'])==4
    assert new['analysis']==body['analysis'] and new['requests']==body['requests'] and new['analysis_stale']
    assert new['evidence'][1].get('superseded_by')


def test_temporarily_unavailable_order_preserves_its_snapshot_and_existing_assessment():
    d,r,c=fixture();body,_,_,_=pp.prepare_import(None,d,r,[],1,c)
    body.update(analysis={'finding':'insufficient'},analysis_stale=False)
    new,changed,_,change=pp.prepare_import(body,d,r[:1],['order_unavailable:403'],1,c)
    assert changed and not change['source_ids'] and len(new['evidence'])==3
    assert new['analysis']==body['analysis'] and new['analysis_stale'] is False
    assert new['payment_record_acquisition']['status']=='partial'


@pytest.mark.parametrize('method',['POST','PATCH','PUT','DELETE'])
def test_read_only_adapter_blocks_business_writes_before_oauth(monkeypatch,method):
    def forbidden(*args,**kwargs):raise AssertionError('No network request may occur')
    monkeypatch.setattr(httpx,'AsyncClient',forbidden)
    with pytest.raises(ValueError):asyncio.run(PayPal('app','secret',read_only=True).request(method,'/v1/customer/disputes/PP-D-UNIT/accept-claim'))


def test_expired_read_token_is_refreshed_and_explicit_credentials_remain_scoped(monkeypatch):
    calls=[];real=httpx.AsyncClient
    def handler(req):
        calls.append(req)
        return httpx.Response(200,json={'access_token':'unit-access-token','expires_in':300} if req.url.path.endswith('/token') else {'id':'CAP1'})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
    client=PayPal('scoped-client','scoped-secret',read_only=True);client.token='expired';client.expires=0
    assert asyncio.run(client.request('GET','/v2/payments/captures/CAP1'))=={'id':'CAP1'}
    assert [c.method for c in calls]==['POST','GET']
    assert calls[0].url.path=='/v1/oauth2/token' and calls[1].headers['Authorization']=='Bearer unit-access-token'


def test_invalid_credentials_stop_before_any_provider_record_read(monkeypatch):
    calls=[];real=httpx.AsyncClient
    def handler(req):calls.append(req.url.path);return httpx.Response(401,json={'error':'invalid_client'})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
    with pytest.raises(PayPalError) as error:asyncio.run(PayPal('invalid','invalid',read_only=True).request('GET','/v1/customer/disputes'))
    assert error.value.status==401 and calls==['/v1/oauth2/token']


def test_failed_refresh_retains_existing_case_and_never_commits_a_replacement(monkeypatch):
    d,r,c=fixture();body,_,_,_=pp.prepare_import(None,d,r,[],1,c);body['id']='V-existing'
    original=copy.deepcopy(body);calls=[]
    async def rpc(op,args=None,**kwargs):
        calls.append(op)
        if op=='rate':return {'allowed':True}
        if op=='paypal:get_import':return {'case_id':body['id']}
        return {}
    async def get(case_id):return body
    class Unavailable:
        async def detail(self,id):raise PayPalError(401)
    monkeypatch.setattr(pp.repo,'rpc',rpc);monkeypatch.setattr(pp.repo,'get',get);monkeypatch.setattr(pp,'provider_client',Unavailable)
    with pytest.raises(HTTPException) as error:asyncio.run(pp.import_for_connection(c,d['dispute_id']))
    assert error.value.status_code==502 and body==original and 'paypal:commit_import' not in calls


def test_unconnected_authenticated_account_cannot_trigger_provider_reads(account_client,monkeypatch):
    client,accounts,calls=account_client;assert register(client).status_code==200
    original=pp.repo.rpc
    async def rpc(op,*args,**kwargs):
        if op=='paypal:connection':return None
        return await original(op,*args,**kwargs)
    monkeypatch.setattr(pp.repo,'rpc',rpc)
    monkeypatch.setattr(pp,'provider_client',lambda:(_ for _ in ()).throw(AssertionError('No provider access for this account')))
    assert client.get('/api/paypal/connection').json()['connected'] is False
    assert client.get('/api/paypal/disputes').status_code==403
    assert client.post('/api/paypal/import',json={'dispute_id':'PP-D-UNIT'}).status_code==403
    assert client.post('/api/paypal/import',json={'dispute_id':'PP-D-UNIT','owner_id':'owner','amount':'1.00'}).status_code==422


def test_unauthenticated_provider_access_is_rejected(account_client):
    client,_,_=account_client
    assert client.get('/api/paypal/disputes').status_code==401
    assert client.post('/api/paypal/import',json={'dispute_id':'PP-D-UNIT'}).status_code==401
