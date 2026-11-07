"""Actual first-party sandbox import; private state stays out of publication.

Registration/login use the public API. Provision is an operator-only, server-key
step for the designated controlled QA account, never a public connection flow.
"""
import argparse,asyncio,hashlib,json,os,secrets,sys,time
from pathlib import Path
from datetime import datetime,timezone
import httpx
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))


def fingerprint(case):
    return hashlib.sha256(json.dumps({'revision':case['revision'],'evidence':case['evidence'],
        'analysis':case['analysis'],'audit':case['timeline'][-1]['hash']},sort_keys=True).encode()).hexdigest()


def run(a):
    state=json.loads(a.state.read_text(encoding='utf-8')) if a.state.exists() else {'actors':[]}
    def save():a.state.parent.mkdir(parents=True,exist_ok=True);a.state.write_text(json.dumps(state,indent=2),encoding='utf-8')
    def ok(r):
        if r.status_code!=200:
            state['last_failure']={'status':r.status_code,'detail':r.json().get('detail')};save();raise AssertionError('HTTP '+str(r.status_code)+'; private detail retained')
        return r.json()
    clients=[httpx.Client(base_url=a.base,timeout=120,limits=httpx.Limits(max_keepalive_connections=0)) for _ in range(2)]
    try:
        for i,c in enumerate(clients):
            if len(state['actors'])<=i:
                assert a.phase=='register'
                actor={'username':'paypal_saas_qa_'+secrets.token_hex(5),'display_name':'Sandbox integration QA '+str(i+1),'password':secrets.token_urlsafe(24)}
                r=ok(c.post('/api/auth/register',json=actor));actor.update(owner_id=r['id'],recovery_code=r['recovery_code']);state['actors'].append(actor);save()
            else:ok(c.post('/api/auth/login',json={k:state['actors'][i][k] for k in ['username','password']}))
        if a.phase=='register':print(json.dumps({'normal_registrations':2,'provider_calls':0}));return
        if a.phase in ('provision','local-import'):
            config={**dotenv_values(ROOT/'backend/.env'),**json.loads((ROOT/'runtime/saas-deploy-private.json').read_text())}
            os.environ.update({k:v for k,v in config.items() if v is not None})
            from saas_store import repo,SESSION
            from saas_auth import COOKIE
            from saas_paypal import import_for_connection,authorized_connection
            probe=json.loads((ROOT/'runtime/saas-paypal-probe-private.json').read_text())
            merchant=probe['dispute']['disputed_transactions'][0]['seller']['merchant_id']
            owner=state['actors'][0]['owner_id'];os.environ.update(VERDICT_PAYPAL_DEMO_OWNER_ID=owner,VERDICT_PAYPAL_DEMO_MERCHANT_ID=merchant)
            async def work():
                await repo.start()
                token=SESSION.set(hashlib.sha256(clients[0].cookies.get(COOKIE).encode()).hexdigest())
                try:
                    if a.phase=='provision':
                        c=await repo.rpc('paypal:provision_demo',{'owner_id':owner,'merchant_id':merchant},session='')
                        state.update(connection_id=c['id'],dispute_id=probe['dispute']['dispute_id']);save()
                        private={'VERDICT_PAYPAL_DEMO_OWNER_ID':owner,'VERDICT_PAYPAL_DEMO_MERCHANT_ID':merchant,'connection_id':c['id']}
                        (ROOT/'runtime/saas-paypal-preview-private.json').write_text(json.dumps(private,indent=2),encoding='utf-8')
                        print(json.dumps({'operator_provisioned_one_controlled_qa_connection':True,'public_self_service':False}));return
                    result=await import_for_connection(await authorized_connection(),state['dispute_id'])
                    state['case_id']=result['case']['id'];state['first_source_ids']=[s['id'] for s in result['case']['evidence']];save()
                    print(json.dumps({'real_sandbox_import':True,'provider_sources':len(result['case']['evidence']),'provider_business_writes':0}))
                finally:SESSION.reset(token);await repo.close()
            asyncio.run(work());return
        c,other=clients;path='/api/cases/'+state['case_id'];checks={}
        def check(name,v):
            checks[name]=bool(v)
            if not v:raise AssertionError(name)
        if a.phase=='wait':
            deadline=time.monotonic()+600
            while True:
                case=ok(c.get(path));w=case['automation']
                if w['state'] in ('completed','partial'):break
                if w['state']=='failed':state['last_failure']={'detail':w['detail']};save();raise AssertionError('Automatic investigation failed; private detail retained')
                if time.monotonic()>deadline:raise AssertionError('Automatic investigation timed out')
                time.sleep(3)
        else:case=ok(c.get(path))
        check('authenticated_account_workspace',case['mode']=='paypal_sandbox_saas')
        check('real_provider_origin',len(case['evidence'])>=3 and all(e.get('origin_verified') for e in case['evidence'] if e['origin']=='paypal_sandbox_api'))
        receipt=case['paypal_account'];payment=receipt['payments'][0]
        check('real_capture_order_linkage',payment['linkage']=='verified_capture_and_order')
        check('real_buyer_and_seller_ids',bool(payment['buyer_id']) and payment['seller_merchant_id']==receipt['merchant_id'])
        check('disputed_amount_provider_populated',case['amount']==receipt['dispute']['disputed_amount']['value'] and case['currency']==receipt['dispute']['disputed_amount']['currency_code'])
        check('actual_usd_one_test_record',payment['payment_amount']=={'value':'1.00','currency_code':'USD'})
        check('actual_gemini_investigation',case['analysis'] is not None and case['analysis']['model']=='gemini-3.1-flash-lite' and not case['analysis_stale'])
        evidence={e['id']:e for e in case['evidence']}
        check('analysis_quotes_real_provider_sources',bool(case['analysis']['claims']) and all(x['quote'] in evidence[x['source_id']]['text'] for x in case['analysis']['claims']))
        check('audit_integrity',case['audit_valid'])
        check('provider_provenance_hashes',all(e['provider_provenance']['canonical_json_sha256'] and e['provider_provenance']['projection_sha256']==e['sha256'] for e in case['evidence'] if e['origin']=='paypal_sandbox_api'))
        check('sensitive_fields_not_exposed',all(term not in json.dumps(case) for term in ['email_address','address_line_1','given_name','surname']))
        check('other_account_case_denied',other.get(path).status_code==404)
        check('other_account_connection_denied',ok(other.get('/api/paypal/connection'))['connected'] is False)
        check('other_account_dispute_list_denied',other.get('/api/paypal/disputes').status_code==403)
        check('other_account_import_denied',other.post('/api/paypal/import',json={'dispute_id':state['dispute_id']}).status_code==403)
        check('other_account_sync_denied',other.post(path+'/paypal/refresh',json={}).status_code==404)
        if a.phase=='wait':
            before=fingerprint(case)
            for _ in range(2):
                result=ok(c.post('/api/paypal/import',json={'dispute_id':state['dispute_id']}))
                check('unchanged_sync_deduplicated',result['duplicate'] is True)
                check('unchanged_sync_preserves_revision_sources_audit_analysis',fingerprint(ok(c.get(path)))==before)
            state['fingerprint']=before;save()
        check('deployment_persistence',fingerprint(ok(c.get(path)))==state['fingerprint'])
        ok(c.post('/api/auth/logout',json={}));check('logout_revoked',c.get(path).status_code==401)
        ok(c.post('/api/auth/login',json={k:state['actors'][0][k] for k in ['username','password']}));check('login_preserves_case',fingerprint(ok(c.get(path)))==state['fingerprint'])
        report={'checked_at':datetime.now(timezone.utc).isoformat(),'base_url':a.base,'phase':a.phase,'checks':checks,'all_passed':all(checks.values()),'provider':'real PayPal sandbox OAuth and authenticated GETs','payment_amount':payment['payment_amount'],'disputed_amount':receipt['dispute']['disputed_amount'],'capture_status':payment['status'],'order_linkage':payment['linkage'],'provider_business_writes':0,'actors':'Two controlled automated QA accounts with normal registration/login; merchant binding is operator-provisioned, not public OAuth consent.'}
        a.report.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
    finally:
        for c in clients:c.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--phase',choices=['register','provision','local-import','wait','verify'],required=True);p.add_argument('--state',type=Path,default=ROOT/'runtime/saas-paypal-acceptance-private.json');p.add_argument('--report',type=Path,default=ROOT/'work/saas-paypal-acceptance.json');run(p.parse_args())
