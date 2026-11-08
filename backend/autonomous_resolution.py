"""Conservative sandbox agent. LLM conclusions never authorize money movement.

Only the pre-provisioned merchant can opt in. Current scope is full buyer
concession for explicitly attested, unfulfilled VERDICT test orders. Other
evidence remains investigable, but cannot be promoted to fulfillment proof.
"""
import asyncio
from contextlib import suppress
from decimal import Decimal, InvalidOperation
import os
import re
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
import saas_auth as auth
from saas_store import repo, SESSION
from paypal import PayPal, PayPalError, BASE, allowed
from payment_records import fetch_records, ReadBudget, safe_id
from saas_paypal import authorized_connection, provider_client, payment_summary, project, prepare_import
from store import digest, now

router=APIRouter(prefix='/api')
NOTE='VERDICT Sandbox: the merchant authorized concession for this unfulfilled test order under its bounded autonomous policy. No proof of physical delivery is asserted.'


class PolicyInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    enabled: bool
    per_claim_usd: str=Field(default='1.00',pattern=r'^[0-5]\.\d{2}$')
    total_usd: str=Field(default='1.00',pattern=r'^\d{1,2}\.\d{2}$')
    max_actions: int=Field(default=1,ge=1,le=5)
    hours: int=Field(default=24,ge=1,le=24)
    unfulfilled_test_orders: bool=False


@router.get('/paypal/autonomy')
async def get_policy(user=Depends(auth.current_session)):
    c=await authorized_connection()
    return await repo.rpc('agent:policy',{'connection_id':c['id']})


@router.post('/paypal/autonomy')
async def set_policy(data:PolicyInput,user=Depends(auth.current_session)):
    c=await authorized_connection()
    if data.enabled and (not data.unfulfilled_test_orders or not 0<Decimal(data.per_claim_usd)<=5 or not 0<Decimal(data.total_usd)<=10):
        raise HTTPException(422,'Confirm the unfulfilled test-order policy and limits (up to USD 5 per claim, USD 10 total).')
    result=await repo.rpc('agent:enable',{'connection_id':c['id'],**data.model_dump()})
    from automatic_investigation import WAKE
    WAKE.set()
    return result


@router.get('/cases/{id}/resolution')
async def resolution(id:str,user=Depends(auth.current_session)):
    await repo.get(id)
    return await repo.rpc('agent:status',{'case_id':id})


def decision(case, policy, detail, records, merchant, issues=()):
    """Independent fail-closed rules, based on provider records and owner policy.

    This deliberately cannot prove physical fulfillment from uploaded tracking,
    OCR, an AI verdict, proximity or a seller's self-authored delivery claim.
    """
    def stop(code):return {'eligible':False,'reason':code}
    if not policy or not policy.get('enabled'):return stop('autonomy_disabled')
    if case.get('mode')!='paypal_sandbox_saas' or detail.get('dispute_id')!=case.get('paypal_id'):return stop('identity_mismatch')
    if issues:return stop('incomplete_provider_records')
    if any(u.get('payments',{}).get('refunds') for r in records if r['kind']=='order' for u in r['body'].get('purchase_units',[])):
        return stop('existing_refund_requires_reconciliation')
    if not case.get('analysis') or case.get('analysis_stale'):return stop('investigation_pending')
    if case['analysis'].get('finding') in ('conflicting','supports_seller'):return stop('investigation_conflict')
    if any(e.get('extraction',{}).get('status') in ('pending','unreadable','uncertain') for e in case.get('evidence',[])):
        return stop('unresolved_document_uncertainty')
    from investigator import investigation_payload
    if case['analysis'].get('input_digest')!=digest(investigation_payload(case)):
        return stop('investigation_pending')
    if detail.get('status')!='WAITING_FOR_SELLER_RESPONSE' or detail.get('reason')!='MERCHANDISE_OR_SERVICE_NOT_RECEIVED':
        # PayPal uses MERCHANDISE_OR_SERVICE_NOT_RECEIVED, not the UI reason.
        return stop('provider_not_eligible')
    if 'accept-claim' not in allowed(detail):return stop('provider_action_unavailable')
    if 'REFUND' not in detail.get('allowed_response_options',{}).get('accept_claim',{}).get('accept_claim_types',[]):return stop('full_refund_unavailable')
    try:
        payment_summary(detail,records,merchant)
    except Exception:return stop('identity_mismatch')
    txs=detail.get('disputed_transactions',[])
    caps=[r['body'] for r in records if r['kind']=='capture']
    orders=[r['body'] for r in records if r['kind']=='order']
    if len(txs)!=1 or len(caps)!=1 or len(orders)!=1:return stop('transaction_not_unique')
    cap=caps[0];order=orders[0]
    units=order.get('purchase_units',[])
    if len(units)!=1 or units[0].get('reference_id')!='VERDICT-SANDBOX-TEST':return stop('outside_test_order_policy')
    if units[0].get('payee',{}).get('merchant_id')!=merchant or cap.get('payee',{}).get('merchant_id')!=merchant:
        return stop('identity_mismatch')
    if txs[0].get('seller_transaction_id')!=cap.get('id') or order.get('id')!=cap.get('supplementary_data',{}).get('related_ids',{}).get('order_id'):
        return stop('identity_mismatch')
    if order.get('status')!='COMPLETED' or cap.get('status') not in ('COMPLETED','PENDING'):return stop('payment_not_captured')
    if cap.get('status')=='PENDING' and cap.get('status_details',{}).get('reason')!='BUYER_COMPLAINT':return stop('payment_pending')
    if not any(x.get('id')==cap['id'] for x in units[0].get('payments',{}).get('captures',[])):return stop('identity_mismatch')
    # ANY prior refund, including pending, blocks a second financial action.
    if any(u.get('payments',{}).get('refunds') for u in units):return stop('existing_refund_requires_reconciliation')
    if detail.get('refund_details',{}).get('allowed_refund_amount'):
        if detail['refund_details']['allowed_refund_amount']!=detail.get('dispute_amount'):return stop('refund_amount_ambiguity')
    try:
        amounts=[detail['dispute_amount'],cap['amount'],units[0]['amount']]
        if any(a['currency_code']!='USD' for a in amounts):return stop('currency_not_authorized')
        value=Decimal(amounts[0]['value'])
        if not value.is_finite() or value<=0 or any(Decimal(a['value'])!=value for a in amounts):return stop('amount_mismatch')
        if value>Decimal(policy['per_claim_usd']):return stop('per_claim_limit')
    except (KeyError,InvalidOperation,TypeError):return stop('amount_unverifiable')
    if not policy.get('unfulfilled_test_orders'):return stop('merchant_attestation_missing')
    # Model output does not appear in the authorization basis. User-uploaded
    # experimental documents are explicitly excluded from fulfillment proof.
    basis={'rule':'unfulfilled_merchant_attested_test_order_v1','dispute_id':detail['dispute_id'],
        'capture_id':cap['id'],'order_id':order['id'],'amount':str(value),'currency':'USD',
        'provider_digest':digest({'detail':detail,'records':records}),'case_revision':case['revision'],
        'policy_id':policy['id'],'excluded':'All uploaded/OCR/experimental delivery claims; no physical fulfillment asserted.'}
    basis['provider_evidence']={'dispute':project('dispute',detail,merchant,{cap['id']}),
        'records':[{'kind':r['kind'],'record':project(r['kind'],r['body'],merchant,{cap['id']})} for r in records]}
    basis['provider_request']={'path':'/v1/customer/disputes/'+detail['dispute_id']+'/accept-claim',
        'body':{'accept_claim_type':'REFUND','note':NOTE}}
    return {'eligible':True,'reason':'merchant_attested_unfulfilled_test_order','amount':str(value),'basis':basis}


def confirmation(detail, records):
    """A successful POST is never a resolution or evidence of refund completion."""
    if detail.get('status')!='RESOLVED':return {'state':'waiting_provider','label':'Waiting for PayPal confirmation'}
    outcome=detail.get('dispute_outcome',{})
    result={'state':'resolved','label':'Resolved by PayPal','outcome':outcome.get('outcome_code')}
    amount=outcome.get('amount_refunded')
    if amount and amount.get('currency_code')=='USD':
        try:
            if Decimal(amount['value'])>0 and Decimal(amount['value']).is_finite():
                result.update(state='refunded',label='Resolved — USD '+amount['value']+' refunded',amount=amount,
                    refund_verification='PayPal dispute outcome confirms refunded amount. Buyer balance not accessible with merchant credentials.')
        except (InvalidOperation,KeyError):pass
    # Do not invent an amount from the original disputed amount.
    return result


async def evaluate_case(case_id):
    case=await repo.get(case_id)
    if case.get('mode')!='paypal_sandbox_saas':return
    c=await authorized_connection()
    if c['id']!=case.get('paypal_connection_id'):return
    state=await repo.rpc('agent:policy',{'connection_id':c['id']})
    prior=await repo.rpc('agent:status',{'case_id':case_id})
    if not state.get('enabled') and not prior.get('action'):return
    client=provider_client()
    detail=await client.detail(case['paypal_id'])
    records,issues,count=await fetch_records(client,detail,ReadBudget())
    if detail.get('dispute_id')!=case['paypal_id']:
        raise RuntimeError('Provider dispute identity mismatch')
    payment_summary(detail,records,c['merchant_id'])
    checked={'checked_at':now(),'provider_reads':count+1,'provider_digest':digest({'detail':detail,'records':records})}
    changed=await sync_provider_snapshot(case,c,detail,records,issues,count)
    if prior.get('action'):
        result=confirmation(detail,records)
        if result['state']=='waiting_provider' and prior['action']['state'] in ('prepared','sending','uncertain','rejected'):
            result={'state':'uncertain','label':'PayPal response needs review','reason':'previous_action_not_replayed'}
        await repo.rpc('agent:observe',{'case_id':case_id,'observation':{**checked,**result}})
        return
    if changed:
        await repo.rpc('agent:observe',{'case_id':case_id,'observation':{**checked,'state':'investigating','label':'Investigating updated PayPal records','reason':'investigation_pending'}})
        return
    verdict=decision(case,state,detail,records,c['merchant_id'],issues)
    if not verdict['eligible']:
        await repo.rpc('agent:observe',{'case_id':case_id,'observation':{**checked,'state':'abstained','label':'Waiting for missing information','reason':verdict['reason']}})
        return
    reservation=await repo.rpc('agent:reserve',{'case_id':case_id,'connection_id':c['id'],'policy_id':state['id'],
        'amount':verdict['amount'],'basis':verdict['basis'],'expected_revision':case['revision']})
    if not reservation.get('created'):return
    action=reservation['action']
    # Only the transaction that created this durable intent may dispatch it.
    # Crashes after reservation fail closed. A sending/unknown intent is never
    # re-posted, even following restarts, revocation or replacement policies.
    sent=await repo.rpc('agent:sending',{'id':action['id']})
    if not sent.get('send'):return
    if BASE!='https://api-m.sandbox.paypal.com':raise RuntimeError('Sandbox boundary failed')
    writer=PayPal(os.getenv('PAYPAL_CLIENT_ID'),os.getenv('PAYPAL_CLIENT_SECRET'))
    try:
        await writer.request('POST','/v1/customer/disputes/'+case['paypal_id']+'/accept-claim',
            {'accept_claim_type':'REFUND','note':NOTE},key=action['id'])
        result={'state':'waiting_provider','label':'Waiting for PayPal confirmation'}
    except PayPalError as error:
        result={'state':'uncertain' if error.uncertain else 'rejected','label':'PayPal response needs review',
            'diagnostic':error.diagnostic,'automatic_retry':False}
    # Failure to save this response still leaves the committed SENDING barrier.
    await repo.rpc('agent:action_result',{'id':action['id'],'result':result})
    # Always verify with fresh reads, including after an ambiguous write.
    detail=await client.detail(case['paypal_id'])
    records,_,count=await fetch_records(client,detail,ReadBudget())
    if detail.get('dispute_id')!=case['paypal_id']:raise RuntimeError('Provider dispute identity mismatch')
    payment_summary(detail,records,c['merchant_id'])
    await sync_provider_snapshot(await repo.get(case_id),c,detail,records,[],count)
    await repo.rpc('agent:observe',{'case_id':case_id,'observation':{**confirmation(detail,records),
        'checked_at':now(),'provider_reads':count+1,'provider_digest':digest({'detail':detail,'records':records})}})


async def sync_provider_snapshot(case,c,detail,records,issues,count):
    body,changed,snapshots,change=prepare_import(case,detail,records,issues,count,c)
    if not changed:return False
    mutation=repo.mutation(body,'paypal_dispute_synchronized',{'origin':'autonomous_provider_read',
        'environment':'sandbox','provider_records':len(snapshots),'source_ids':change['source_ids'],
        'superseded':change['superseded'],'read_only':True})
    await repo.rpc('paypal:commit_import',{'connection_id':c['id'],'dispute_id':case['paypal_id'],
        'creating':False,'mutation':mutation,'snapshots':snapshots})
    return True


async def tick():
    due=await repo.rpc('agent:due',session='')
    for row in due:
        context=await repo.rpc('paypal:operator_context',{'connection_id':row['connection_id']},session='')
        token=SESSION.set(context['session_hash'])
        try:
            c=await authorized_connection()
            if row['enabled']:
                from saas_paypal import import_for_connection
                items=await provider_client().disputes()
                imported=await repo.rpc('paypal:list_imports',{'connection_id':c['id']})
                known={i['dispute_id'] for i in imported}
                items=sorted((i for i in items if i.get('status')!='RESOLVED'),key=lambda i:i['dispute_id'] in known)
                for item in items[:2]:
                    await import_for_connection(c,item['dispute_id'],origin='autonomous_sandbox_policy')
            links=await repo.rpc('agent:work_cases',{'connection_id':c['id']})
            for link in links:
                await evaluate_case(link['case_id'])
        except Exception:
            # Saved intent barriers survive provider/DB errors; never POST retry.
            pass
        finally:
            SESSION.reset(token)
            with suppress(Exception):
                await repo.rpc('paypal:close_operator_context',{'session_hash':context['session_hash']},session='')
