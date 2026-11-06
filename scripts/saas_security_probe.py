"""Real cloud recovery, transaction rollback, and anonymous-access checks.

Uses a separate synthetic test account, never provider/payment actions. Raw
credentials and identifiers stay in ignored runtime; report contains booleans.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import sys
import httpx
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from saas_store import CloudRepository
from saas_auth import token_hash, COOKIE


def run(base, report_path):
    checks={}
    def check(name,value):
        checks[name]=bool(value)
        if not value: raise AssertionError(name)
    def ok(response):
        if response.status_code!=200: raise AssertionError('Unexpected HTTP '+str(response.status_code))
        return response.json()
    account={'username':'security_qa_'+secrets.token_hex(6),'display_name':'Security acceptance','password':secrets.token_urlsafe(24)}
    private=ROOT/'runtime/saas-security-private.json'
    with httpx.Client(base_url=base,timeout=60) as c,httpx.Client(base_url=base,timeout=60) as second:
        registration=ok(c.post('/api/auth/register',json=account))
        account['recovery_code']=registration['recovery_code'];private.write_text(json.dumps(account))
        check('empty_new_account',ok(c.get('/api/cases'))==[])
        check('duplicate_username_denied',c.post('/api/auth/register',json={k:account[k] for k in ('username','display_name','password')}).status_code==409)
        ok(second.post('/api/auth/login',json={k:account[k] for k in ('username','password')}))
        case=ok(c.post('/api/cases',json={'title':'Cloud atomicity security test','amount':'0.00','currency':'USD'}))
        path='/api/cases/'+case['id']
        case=ok(c.get(path)); before=case['timeline'][-1]['hash']
        args=CloudRepository().mutation(case,'invalid_file_attempt',{},file={'id':'E-invalid','name':'bad.txt','mime':'text/plain','content':'b3JpZ2luYWw=','sha256':'0'*64})
        env=dotenv_values(ROOT/'backend/.env')
        with httpx.Client(base_url=env['SUPABASE_URL'],timeout=60) as db:
            bad=db.post('/rest/v1/rpc/verdict_saas_api',headers={'apikey':env['SUPABASE_SECRET_KEY']},json={'p_op':'save','p_session_hash':token_hash(c.cookies.get(COOKIE)),'p_args':args})
            check('invalid_original_rejected',bad.status_code>=400 and bad.json().get('message')=='verdict:invalid_file')
            after=ok(c.get(path))
            check('failed_transaction_preserves_case_and_audit',after['revision']==case['revision'] and after['timeline'][-1]['hash']==before)
            ok(c.post(path+'/evidence',json={'title':'Valid note','text':'Synthetic note to advance the revision.'}))
            stale=db.post('/rest/v1/rpc/verdict_saas_api',headers={'apikey':env['SUPABASE_SECRET_KEY']},json={'p_op':'save','p_session_hash':token_hash(c.cookies.get(COOKIE)),'p_args':CloudRepository().mutation(case,'stale_test',{})})
            check('stale_revision_rejected',stale.status_code>=400 and stale.json().get('message')=='verdict:stale_revision')
            anonymous=db.post('/rest/v1/rpc/verdict_saas_api',headers={'apikey':env['SUPABASE_PUBLISHABLE_KEY']},json={'p_op':'list'})
            check('anonymous_rpc_denied',anonymous.status_code in (401,403))
            check('private_schema_not_exposed',db.get('/rest/v1/accounts',headers={'apikey':env['SUPABASE_PUBLISHABLE_KEY'],'Accept-Profile':'verdict_saas'}).status_code in (401,403,406))
        r=ok(c.post(path+'/requests',json={'title':'Revocation test','question':'Synthetic question only','recipient':'other'}))
        header={'Authorization':'Bearer '+r['portal_fragment'].split('=',1)[1]}
        check('request_available_before_close',httpx.get(base+'/api/portal',headers=header).status_code==200)
        ok(c.post(path+'/requests/'+r['request']['id']+'/close',json={'status':'withdrawn','reason':'Controlled revocation security test'}))
        check('request_revoked_after_close',httpx.get(base+'/api/portal',headers=header).status_code==409)
        old=account['password']; old_code=account['recovery_code']; new=secrets.token_urlsafe(24)
        check('wrong_recovery_key_denied',c.post('/api/auth/recover',json={'username':account['username'],'password':new,'recovery_code':secrets.token_urlsafe(32)}).status_code==401)
        recovered=ok(c.post('/api/auth/recover',json={'username':account['username'],'password':new,'recovery_code':old_code}))
        account.update(password=new,recovery_code=recovered['recovery_code']);private.write_text(json.dumps(account))
        check('recovery_revokes_other_sessions',second.get('/api/me').status_code==401)
        check('recovery_preserves_workspace',ok(c.get(path))['id']==case['id'])
        check('recovery_key_is_one_time',c.post('/api/auth/recover',json={'username':account['username'],'password':old,'recovery_code':old_code}).status_code==401)
        check('old_password_denied',second.post('/api/auth/login',json={'username':account['username'],'password':old}).status_code==401)
        ok(second.post('/api/auth/login',json={'username':account['username'],'password':new}))
        check('new_password_works',second.get(path).status_code==200)
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'base_url':base,'checks':checks,'all_passed':all(checks.values()),'scope':'Actual cloud API, PostgreSQL transaction rollback and recovery; synthetic user records only'}
    report_path.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--base',default='http://127.0.0.1:8001');parser.add_argument('--report',type=Path,default=ROOT/'work/saas-security-probe.json')
    args=parser.parse_args();run(args.base,args.report)
