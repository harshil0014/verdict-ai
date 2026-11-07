"""Actual blocked-source recovery and a separate accessible-source lifecycle.

The first submitted record contains only the blocked CanLII URL. No original
publisher URL, search, retry, approval or analysis request is supplied by this test.
Private state remains ignored. Reports expose public URLs/hashes/counts only.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import secrets
import re
import time
import httpx

ROOT=Path(__file__).resolve().parents[1]
BLOCKED='https://www.canlii.org/en/bc/bccrt/doc/2024/2024bccrt149/2024bccrt149.html'
ACCESSIBLE='https://www.bclaws.gov.bc.ca/civix/document/id/complete/statreg/12025_01?utm_source=acceptance'


def fingerprint(case):
    return hashlib.sha256(json.dumps({'revision':case['revision'],'analysis':case['analysis'],
        'audit':case['timeline'][-1]['hash'],'evidence':case['evidence']},sort_keys=True).encode()).hexdigest()


def run(args):
    state=json.loads(args.state.read_text(encoding='utf-8')) if args.state.exists() else {'actors':[]}
    checks={};clients=[];public_sources=[];investigation_results=[]
    acquisition_only=args.phase=='acquisition'
    def save():args.state.parent.mkdir(parents=True,exist_ok=True);args.state.write_text(json.dumps(state,indent=2),encoding='utf-8')
    def check(name,value):
        checks[name]=bool(value)
        if not value:raise AssertionError(name)
    def ok(r):
        if r.status_code!=200:
            state['last_failure']={'status':r.status_code,'detail':r.json().get('detail')};save();raise AssertionError('HTTP '+str(r.status_code)+'; private diagnostic retained')
        return r.json()
    try:
        for i in range(2):
            c=httpx.Client(base_url=args.base,timeout=120,limits=httpx.Limits(max_keepalive_connections=0));clients.append(c)
            if len(state['actors'])<=i:
                assert args.phase=='prepare'
                actor={'username':'recovery_qa_'+secrets.token_hex(6),'password':secrets.token_urlsafe(24),'display_name':'Source recovery QA '+str(i+1)}
                result=ok(c.post('/api/auth/register',json=actor));actor['recovery_code']=result['recovery_code'];state['actors'].append(actor);save()
            else:
                actor=state['actors'][i];ok(c.post('/api/auth/login',json={k:actor[k] for k in ('username','password')}))
            if 'case_id' not in actor:
                assert args.phase=='prepare'
                actor['case_id']=ok(c.post('/api/cases',json={'title':'Synthetic source recovery review' if i==0 else 'Independent accessible public source review','reason':'OTHER','amount':'0.00','currency':'CAD'}))['id'];save()
            if args.phase=='prepare' and not actor.get('submitted'):
                text=('SYNTHETIC QA RECORD. No real customer, transaction or claim. Distinguish reported accounts and tribunal findings in the public decision referenced here: '+BLOCKED) if i==0 else ('SYNTHETIC QA RECORD. No customer or real claim. Investigate what this current legislation states without treating it as proof of a past policy: '+ACCESSIBLE)
                raw=text.encode();case=ok(c.post('/api/cases/'+actor['case_id']+'/upload',files={'file':('source-reference.txt',raw,'text/plain')},data={'party':'other'}))
                actor.update(submitted=True,original_id=case['evidence'][-1]['id'],original_sha256=hashlib.sha256(raw).hexdigest());save()
        if args.phase=='prepare':print(json.dumps({'phase':'prepare','single_uploads':2,'publisher_urls_supplied_for_recovery':0,'manual_search_analysis_approval_retry_calls':0}));return
        for i,c in enumerate(clients):
            actor=state['actors'][i];path='/api/cases/'+actor['case_id'];prefix='actor_'+str(i+1)+'_'
            if args.phase in ('wait','acquisition'):
                deadline=time.monotonic()+480
                while True:
                    case=ok(c.get(path));workflow=case['automation']
                    if workflow['state'] in ('completed','partial'):break
                    if workflow['state']=='failed':
                        if acquisition_only:break
                        state['last_failure']={'detail':workflow['detail']};save();raise AssertionError('Automatic recovery failed; private detail retained')
                    if time.monotonic()>deadline:raise AssertionError('Recovery timed out')
                    time.sleep(3)
            else:case=ok(c.get(path));workflow=case['automation']
            analysis=case.get('analysis') or {}
            complete=workflow['state']=='completed' and bool(analysis) and not case['analysis_stale']
            model_failure=re.search(r'Gemini returned HTTP (\d{3})',workflow.get('detail',''))
            investigation_results.append({'actor':i+1,'workflow_state':workflow['state'],'investigation_complete':complete,
                'gemini_http_status':int(model_failure[1]) if model_failure else None})
            if not acquisition_only:
                check(prefix+'automatic_investigation_complete',complete)
                check(prefix+'actual_gemini',analysis['model']=='gemini-3.1-flash-lite')
            check(prefix+'original_submission_preserved',hashlib.sha256(c.get(path+'/files/'+actor['original_id']).content).hexdigest()==actor['original_sha256'])
            check(prefix+'foreign_case_denied',clients[1-i].get(path).status_code==404)
            check(prefix+'foreign_research_denied',clients[1-i].get(path+'/research').status_code==404)
            check(prefix+'foreign_retry_denied',clients[1-i].post(path+'/automation/retry',json={}).status_code==404)
            check(prefix+'audit_valid',case['audit_valid'])
            check(prefix+'no_human_approval_calls',not any(e['kind']=='public_evidence_approved' for e in case['timeline']))
            evidence={e['id']:e for e in case['evidence']}
            public=[e for e in case['evidence'] if e.get('origin')=='public_web_automatic'];check(prefix+'real_public_source_preserved',bool(public))
            if not acquisition_only:
                check(prefix+'source_claims_bound_to_preserved_text',bool(analysis['claims']) and all(x['quote'] in evidence[x['source_id']]['text'] for x in analysis['claims']))
                check(prefix+'actual_public_source_used',any(evidence[x['source_id']].get('provenance') for x in analysis['claims']))
            if i==0:
                original=evidence[actor['original_id']]['text']
                check('publisher_url_not_in_original_submission','civilresolutionbc.ca' not in original and BLOCKED in original)
                check('case_name_not_supplied_for_discovery','Moffatt' not in original)
                refusal=workflow['progress']['references'][BLOCKED];recovery=workflow['progress']['recoveries'][BLOCKED]
                check('blocked_403_retained',refusal['status']=='unavailable' and 'HTTP 403' in refusal.get('detail',''))
                check('original_publisher_discovered_without_supplied_url',recovery['status']=='recovered' and recovery['recovered_url'].startswith('https://decisions.civilresolutionbc.ca/'))
                recovered=next(e for e in public if e['id']==recovery['source_id']);identity=recovered['provenance']['source_recovery']['identity_check']
                check('same_neutral_citation_in_real_header',identity['status']=='matched' and identity['expected_citation']==identity['observed_citation']=='2024 BCCRT 149')
                check('identity_bound_to_exact_passage',recovered['text'][identity['passage_start']:identity['passage_end']]==identity['identity_passage'])
                check('identity_bound_to_snapshot_hash',identity['text_sha256']==recovered['provenance']['text_sha256'])
                check('blocked_copy_byte_identity_not_claimed',identity['byte_equivalence_to_blocked_copy']=='not_verified')
                check('recovery_is_audited',any(e['kind']=='public_source_recovered' for e in case['timeline']))
                check('discovery_sent_only_public_identifier','Private customer' not in recovery['query'] and '2024 BCCRT 149' in recovery['query'])
                drafts=ok(c.get(path+'/research'));blocked=next(d for d in drafts if d['url']==BLOCKED)
                check('failed_research_record_retained',blocked['status']=='unavailable' and not blocked['text'])
                wrapper=recovered['provenance']['source_recovery'].get('publisher_wrapper')
                if wrapper:
                    check('publisher_wrapper_retained_with_integrity',any(d['id']==wrapper['draft_id'] and d['raw_sha256']==wrapper['raw_sha256'] for d in drafts))
            else:check('separate_accessible_source_without_recovery',not any(e['provenance'].get('source_recovery') for e in public))
            for j,e in enumerate(public):
                data=c.get(path+'/files/'+e['id']);check(prefix+'snapshot_hash_'+str(j),data.status_code==200 and hashlib.sha256(data.content).hexdigest()==e['sha256'])
                check(prefix+'snapshot_foreign_denied_'+str(j),clients[1-i].get(path+'/files/'+e['id']).status_code==404)
                check(prefix+'historical_applicability_unestablished_'+str(j),e['provenance']['historical_applicability']=='not_established')
                public_sources.append({'url':e['provenance']['final_url'],'raw_sha256':e['sha256'],'text_sha256':e['provenance']['text_sha256'],
                    'retrieved_at':e['provenance']['retrieved_at'],'publication_date':e['provenance'].get('publication_date'),
                    'discovery_provider':e['provenance'].get('source_recovery',{}).get('discovered_via')})
            value=fingerprint(case)
            key='acquisition_fingerprint' if acquisition_only else 'fingerprint'
            if args.phase=='wait' or acquisition_only and key not in actor:actor[key]=value;save()
            check(prefix+'retained_case_analysis_audit',value==actor[key])
            ok(c.post('/api/auth/logout',json={}));check(prefix+'logout_revoked',c.get(path).status_code==401)
            ok(c.post('/api/auth/login',json={k:actor[k] for k in ('username','password')}));check(prefix+'return_retains_records',fingerprint(ok(c.get(path)))==value)
        report={'checked_at':datetime.now(timezone.utc).isoformat(),'base_url':args.base,'phase':args.phase,'checks':checks,'all_passed':all(checks.values()),'full_end_to_end_acceptance':not acquisition_only and all(checks.values()),'investigation_results':investigation_results,'public_sources':public_sources,'blocked_url':BLOCKED,'publisher_urls_supplied_for_recovery':0,'manual_search_analysis_approval_retry_calls':state.get('diagnostic_analysis_calls',0),'actors':'Two independent automated test accounts, not two humans','payment_or_dispute_writes':0}
        args.report.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
    finally:
        for c in clients:c.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',default='http://127.0.0.1:8001');p.add_argument('--phase',choices=['prepare','wait','verify','acquisition'],required=True);p.add_argument('--state',type=Path,default=ROOT/'runtime/saas-recovery-private.json');p.add_argument('--report',type=Path,default=ROOT/'work/recovery-verification.json');run(p.parse_args())
