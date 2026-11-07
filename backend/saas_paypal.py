"""Account-authorized first-party sandbox reads. No public OAuth or provider writes."""
import base64
import copy
import json
import os
import re
from decimal import Decimal,InvalidOperation
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field
import saas_auth as auth
from saas_store import repo
from paypal import PayPal,PayPalError
from payment_records import ReadBudget,fetch_records,merge_records,safe_id
from source_recovery import RECOVERY_VERSION
from store import now,digest,canon

router=APIRouter(prefix='/api')
MISSING='Not available from PayPal'


def select(data,keys):
    return {k:data[k] for k in keys if k in data and data[k] is not None}


def money(value):
    if not isinstance(value,dict):return None
    currency=value.get('currency_code');amount=value.get('value')
    if not isinstance(currency,str) or not re.fullmatch('[A-Z]{3}',currency):return None
    if not isinstance(amount,str) or not re.fullmatch(r'\d{1,12}(?:\.\d{1,8})?',amount):return None
    try:
        if not Decimal(amount).is_finite():return None
    except InvalidOperation:return None
    return {'currency_code':currency,'value':amount}


def identifier(value):return value if safe_id(value) else None


def canonical_provider_record(data):
    """Top-level HATEOAS relations form a set; retain every link's content.

    PayPal can return the same links in a different array order. Normalize only
    that known envelope field, never party statements or transaction arrays.
    The stored snapshot is explicitly canonical JSON, not original HTTP bytes.
    """
    out=copy.deepcopy(data);links=out.get('links')
    if isinstance(links,list) and all(isinstance(x,dict) and isinstance(x.get('rel'),str) and isinstance(x.get('href'),str) for x in links):
        out['links']=sorted(links,key=canon)
    return out


def payment_summary(detail,records,merchant):
    """Cross-check the provider's IDs; missing identity is not person authentication."""
    expected={t.get('seller_transaction_id') for t in detail.get('disputed_transactions',[]) if safe_id(t.get('seller_transaction_id'))}
    for r in records:
        if r['kind'] not in ('capture','order') or r['body'].get('id')!=r['id']:
            raise HTTPException(409,'PayPal record identifiers disagree. No case was changed.')
        if r['kind']=='capture' and r['id'] not in expected:
            raise HTTPException(409,'PayPal capture is not referenced by this dispute. No case was changed.')
    captures={r['id']:r['body'] for r in records if r['kind']=='capture'}
    orders={r['id']:r['body'] for r in records if r['kind']=='order'}
    expected_orders={c.get('supplementary_data',{}).get('related_ids',{}).get('order_id') for c in captures.values()}
    if any(oid not in expected_orders for oid in orders):raise HTTPException(409,'PayPal order is not referenced by the retrieved capture. No case was changed.')
    result=[];merchant_seen=False
    for tx in detail.get('disputed_transactions',[]):
        seller=identifier((tx.get('seller') or {}).get('merchant_id'))
        if seller and seller!=merchant:raise HTTPException(409,'PayPal seller does not match the authorized merchant. No case was changed.')
        merchant_seen=merchant_seen or seller==merchant
        cap_id=identifier(tx.get('seller_transaction_id'));cap=captures.get(cap_id,{})
        payee=identifier((cap.get('payee') or {}).get('merchant_id'))
        if payee and payee!=merchant:raise HTTPException(409,'PayPal capture payee does not match the authorized merchant. No case was changed.')
        merchant_seen=merchant_seen or payee==merchant
        oid=identifier(cap.get('supplementary_data',{}).get('related_ids',{}).get('order_id'));order=orders.get(oid,{})
        members=[u for u in order.get('purchase_units',[]) if any(x.get('id')==cap_id for x in u.get('payments',{}).get('captures',[]))]
        if order and not members and any(u.get('payments',{}).get('captures') for u in order.get('purchase_units',[])):
            raise HTTPException(409,'PayPal order and capture identifiers disagree. No case was changed.')
        for unit in members:
            mid=identifier(unit.get('payee',{}).get('merchant_id'))
            if mid and mid!=merchant:raise HTTPException(409,'PayPal order payee does not match the authorized merchant. No case was changed.')
            merchant_seen=merchant_seen or mid==merchant
            listed=next(x for x in unit['payments']['captures'] if x.get('id')==cap_id)
            listed_amount=money(listed.get('amount'));captured_amount=money(cap.get('amount'))
            if listed_amount and captured_amount:
                if listed_amount['currency_code']!=captured_amount['currency_code'] or Decimal(listed_amount['value'])!=Decimal(captured_amount['value']):
                    raise HTTPException(409,'PayPal capture amounts disagree across records. No case was changed.')
        buyer=identifier((tx.get('buyer') or {}).get('payer_id'))
        order_buyer=identifier((order.get('payer') or {}).get('payer_id')) or identifier(order.get('payment_source',{}).get('paypal',{}).get('account_id'))
        if buyer and order_buyer and buyer!=order_buyer:raise HTTPException(409,'PayPal buyer account identifiers disagree. No case was changed.')
        result.append({'capture_id':cap_id,'buyer_transaction_id':identifier(tx.get('buyer_transaction_id')),
            'order_id':oid,'payment_amount':money(cap.get('amount')),'reported_transaction_amount':money(tx.get('gross_amount')),
            'status':cap.get('status'),'transaction_status':tx.get('transaction_status'),
            'payment_date':cap.get('create_time'),'transaction_date':tx.get('create_time'),
            'buyer_id':buyer or order_buyer,'seller_merchant_id':payee or seller,
            'linkage':'verified_capture_and_order' if cap and members else 'capture_retrieved_order_link_partial' if cap else 'payment_record_unavailable'})
    if not merchant_seen:raise HTTPException(409,'The receiving merchant could not be established from available PayPal records. No case was changed.')
    return result


def project(kind,data,merchant,capture_ids):
    """Explicit field allowlist: no emails, names, addresses or free-form PII."""
    out=select(data,('id','dispute_id','create_time','update_time','status'))
    if kind=='dispute':
        out.update(select(data,('reason','dispute_state','dispute_life_cycle_stage','dispute_channel','seller_response_due_date')))
        out['dispute_amount']=money(data.get('dispute_amount'))
        out['disputed_transactions']=[]
        for tx in data.get('disputed_transactions',[]):
            row=select(tx,('seller_transaction_id','buyer_transaction_id','create_time','transaction_status','seller_protection_eligible','seller_protection_type'))
            row.update(gross_amount=money(tx.get('gross_amount')),buyer={'payer_id':identifier(tx.get('buyer',{}).get('payer_id'))},seller={'merchant_id':identifier(tx.get('seller',{}).get('merchant_id'))})
            out['disputed_transactions'].append(row)
    elif kind=='capture':
        out.update(amount=money(data.get('amount')),final_capture=data.get('final_capture'),
            payee={'merchant_id':identifier(data.get('payee',{}).get('merchant_id'))},
            supplementary_data={'related_ids':{'order_id':identifier(data.get('supplementary_data',{}).get('related_ids',{}).get('order_id'))}})
        out['status_details']=select(data.get('status_details',{}),('reason',))
    else:
        out['payer']={'payer_id':identifier(data.get('payer',{}).get('payer_id')) or identifier(data.get('payment_source',{}).get('paypal',{}).get('account_id'))}
        out['purchase_units']=[]
        for unit in data.get('purchase_units',[]):
            caps=unit.get('payments',{}).get('captures',[])
            if unit.get('payee',{}).get('merchant_id')!=merchant and not any(c.get('id') in capture_ids for c in caps):continue
            out['purchase_units'].append({'payee':{'merchant_id':identifier(unit.get('payee',{}).get('merchant_id'))},'amount':money(unit.get('amount')),
                'payments':{'captures':[{**select(c,('id','status','create_time','update_time')),'amount':money(c.get('amount'))} for c in caps if c.get('id') in capture_ids]}})
    out['_verdict']={'projection':'privacy_minimized_authenticated_json','canonical_response_sha256':digest(data),
        'free_form_communications':'Retained server-side; omitted from this view for privacy.','reported_dispute_reason_is_not_a_verified_finding':kind=='dispute'}
    return out


def prepare_import(existing,detail,records,issues,count,connection):
    did=detail.get('dispute_id')
    if not isinstance(did,str) or not re.fullmatch(r'[A-Za-z0-9-]{1,80}',did):raise HTTPException(502,'PayPal returned an invalid dispute identifier.')
    merchant=connection['merchant_id'];payments=payment_summary(detail,records,merchant)
    all_records=[{**r,'body':canonical_provider_record(r['body'])} for r in [{'kind':'dispute','id':did,'body':detail}]+records]
    cap_ids={p['capture_id'] for p in payments if p['capture_id']}
    projected=[{**r,'body':project(r['kind'],r['body'],merchant,cap_ids)} for r in all_records]
    body=copy.deepcopy(existing) if existing else {'evidence':[],'requests':[],'analysis':None,'automatic_investigation':True,'automatic_workflow_version':RECOVERY_VERSION}
    summary={'environment':'sandbox','merchant_id':merchant,'dispute':{**select(detail,('dispute_id','reason','status','dispute_life_cycle_stage','create_time','update_time','seller_response_due_date')),
        'disputed_amount':money(detail.get('dispute_amount'))},'payments':payments,
        'identity_assurance':'PayPal account identifiers are provider records, not verification of a person’s identity.',
        'privacy':'Names, email, addresses and free-form communications are not exposed. Original JSON snapshots remain server-side.'}
    change=merge_records(body,projected,issues,count)
    changed=not existing or change['changed'] or body.get('paypal_account')!=summary
    amount=money(detail.get('dispute_amount'))
    body.update(title='PayPal sandbox dispute · '+did,mode='paypal_sandbox_saas',paypal_id=did,paypal_connection_id=connection['id'],
        status=detail.get('status') or 'UNKNOWN',reason=detail.get('reason') or MISSING,
        amount=amount['value'] if amount else None,currency=amount['currency_code'] if amount else None,
        deadline=detail.get('seller_response_due_date'),paypal_account=summary,paypal_snapshot=projected[0]['body'],
        story='Authenticated PayPal sandbox records. Provider origin does not verify reported party statements, delivery or personal identity.')
    for source in body['evidence']:
        if source['id'] in change['source_ids']:
            meta=json.loads(source['text'])['_verdict']
            source['provider_provenance']={'environment':'sandbox','retrieved_at':source['received_at'],'record_kind':source['provider_record_kind'],
                'canonical_json_sha256':meta['canonical_response_sha256'],'projection_sha256':source['sha256'],
                'privacy':'Data-minimized projection; full authenticated JSON retained privately on the server.',
                'verification':'PayPal API record origin, not truth of party statements or personal identity.'}
    if changed:body.update(analysis_stale=bool(body.get('analysis')),paypal_synced_at=now())
    snapshots=[{'kind':r['kind'],'record_id':r['id'],'sha256':digest(r['body']),
        'content':base64.b64encode(json.dumps(r['body'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).decode()} for r in all_records]
    return body,changed,snapshots,change


async def authorized_connection():
    c=await repo.rpc('paypal:connection')
    if not c:raise HTTPException(403,'Your workspace has no authorized PayPal sandbox connection. Public self-service merchant onboarding is not enabled.')
    if c['owner_id']!=os.getenv('VERDICT_PAYPAL_DEMO_OWNER_ID') or c['merchant_id']!=os.getenv('VERDICT_PAYPAL_DEMO_MERCHANT_ID'):
        raise HTTPException(503,'This sandbox connection is not configured for this server. Existing records are retained.')
    if not os.getenv('PAYPAL_CLIENT_ID') or not os.getenv('PAYPAL_CLIENT_SECRET'):raise HTTPException(503,'PayPal sandbox credentials are not configured. Existing records are retained.')
    return c


def provider_client():
    return PayPal(os.environ['PAYPAL_CLIENT_ID'],os.environ['PAYPAL_CLIENT_SECRET'],read_only=True)


async def limited(connection,operation):
    key='paypal:'+operation+':'+connection['id']
    rate=await repo.rpc('rate',{'key':key,'limit':30,'seconds':3600},session='')
    if not rate['allowed']:raise HTTPException(429,'Sandbox synchronization capacity reached. Existing cases remain available.')


async def provider_failure(connection,error):
    await repo.rpc('paypal:status',{'connection_id':connection['id'],'status':'provider_error','diagnostic':error.diagnostic})
    raise HTTPException(502,{'message':'PayPal sandbox could not complete the authorized read. Existing evidence is retained.',
        'provider':'paypal_sandbox','diagnostic':error.diagnostic}) from None


@router.get('/paypal/connection')
async def connection_status(user=Depends(auth.current_session)):
    c=await repo.rpc('paypal:connection')
    if not c:return {'connected':False,'environment':'sandbox','self_service_onboarding':False,'notice':'Restricted test merchant only. Your workspace has no authorized connection.'}
    configured=c['owner_id']==os.getenv('VERDICT_PAYPAL_DEMO_OWNER_ID') and c['merchant_id']==os.getenv('VERDICT_PAYPAL_DEMO_MERCHANT_ID') and bool(os.getenv('PAYPAL_CLIENT_ID') and os.getenv('PAYPAL_CLIENT_SECRET'))
    return {'connected':configured,'environment':'sandbox','read_only':True,'self_service_onboarding':False,
        **select(c,('merchant_id','last_checked_at','last_status','last_error'))}


@router.get('/paypal/disputes')
async def available_disputes(user=Depends(auth.current_session)):
    c=await authorized_connection();await limited(c,'list')
    try:rows=await provider_client().disputes()
    except PayPalError as e:await provider_failure(c,e)
    imported=await repo.rpc('paypal:list_imports',{'connection_id':c['id']})
    ids={r['dispute_id']:r['case_id'] for r in imported}
    await repo.rpc('paypal:status',{'connection_id':c['id'],'status':'healthy','diagnostic':None})
    return {'environment':'sandbox','disputes':[{**select(r,('dispute_id','reason','status','create_time','update_time')),
        'disputed_amount':money(r.get('dispute_amount')),'case_id':ids.get(r.get('dispute_id'))} for r in rows],
        'notice':'Authenticated merchant list. Seller/payment linkage is checked during import. No PayPal action is submitted.'}


class ImportInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    dispute_id:str=Field(pattern=r'^[A-Za-z0-9-]{1,80}$')


async def import_for_connection(connection,dispute_id,*,expected_case_id=None,origin='account_import'):
    await limited(connection,'import')
    link=await repo.rpc('paypal:get_import',{'connection_id':connection['id'],'dispute_id':dispute_id})
    if expected_case_id and (not link or link['case_id']!=expected_case_id):raise HTTPException(404,'Record not found')
    existing=await repo.get(link['case_id']) if link else None
    client=provider_client()
    try:
        detail=await client.detail(dispute_id)
        if detail.get('dispute_id')!=dispute_id:raise HTTPException(502,'PayPal returned a different dispute. No case was changed.')
        if any(t.get('seller',{}).get('merchant_id') not in (None,connection['merchant_id']) for t in detail.get('disputed_transactions',[])):
            raise HTTPException(409,'PayPal dispute seller does not match this connection. No case was changed.')
        records,issues,count=await fetch_records(client,detail,ReadBudget())
    except PayPalError as e:await provider_failure(connection,e)
    body,changed,snapshots,change=prepare_import(existing,detail,records,issues,count,connection)
    if changed:
        mutation=repo.mutation(body,'paypal_dispute_imported' if not existing else 'paypal_dispute_synchronized',
            {'origin':origin,'environment':'sandbox','provider_records':len(snapshots),'source_ids':change['source_ids'],
                'superseded':change['superseded'],'read_only':True},creating=not existing)
        result=await repo.rpc('paypal:commit_import',{'connection_id':connection['id'],'dispute_id':dispute_id,
            'creating':not existing,'mutation':mutation,'snapshots':snapshots})
        case_id=result['id']
    else:case_id=existing['id']
    await repo.rpc('paypal:status',{'connection_id':connection['id'],'status':'healthy','diagnostic':None})
    from automatic_investigation import WAKE
    WAKE.set()
    return {'case':await repo.get(case_id),'duplicate':not changed,'environment':'sandbox','provider_writes':0}


@router.post('/paypal/import')
async def import_dispute(data:ImportInput,user=Depends(auth.current_session)):
    return await import_for_connection(await authorized_connection(),data.dispute_id)


@router.post('/cases/{id}/paypal/refresh')
async def refresh_dispute(id:str,user=Depends(auth.current_session)):
    body=await repo.get(id)
    if body.get('mode')!='paypal_sandbox_saas':raise HTTPException(422,'This is not an account-connected PayPal sandbox case.')
    c=await authorized_connection()
    if body.get('paypal_connection_id')!=c['id']:raise HTTPException(403,'This case’s merchant connection is no longer authorized.')
    return await import_for_connection(c,body['paypal_id'],expected_case_id=id)
