"""Actual API uploads, cloud originals and automatic Gemini investigations.

Synthetic authored receipt; independent accounts created through registration.
State contains credentials and must remain in the gitignored runtime directory.
No payment/dispute writes. Run prepare, wait, then verify after deployment.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import secrets
import httpx

ROOT=Path(__file__).resolve().parents[1]


def run(base,phase,state_path,report):
    state=json.loads(state_path.read_text()) if state_path.exists() else {'actors':[]}
    checks={}
    def save():state_path.write_text(json.dumps(state,indent=2),encoding='utf8')
    def check(name,value):
        checks[name]=bool(value)
        if not value:raise AssertionError(name)
    def ok(r):
        if r.status_code!=200:raise AssertionError('HTTP '+str(r.status_code))
        return r.json()
    clients=[]
    try:
        for i in range(2):
            c=httpx.Client(base_url=base,timeout=180,limits=httpx.Limits(max_keepalive_connections=0));clients.append(c)
            if len(state['actors'])<=i:
                assert phase=='prepare'
                a={'username':'ocr_qa_'+secrets.token_hex(6),'password':secrets.token_urlsafe(26),'display_name':'Document reading acceptance '+str(i+1)}
                reg=ok(c.post('/api/auth/register',json=a));a['recovery_code']=reg['recovery_code'];state['actors'].append(a);save()
            else:
                a=state['actors'][i];ok(c.post('/api/auth/login',json={k:a[k] for k in ('username','password')}))
            if phase=='prepare':
                if not a.get('case_id'):
                    case=ok(c.post('/api/cases',json={'title':'Authored document reading acceptance '+str(i+1),'reason':'ITEM_NOT_RECEIVED','amount':'812.02','currency':'USD'}));a['case_id']=case['id'];save()
                if not a.get('source_id'):
                    filename='receipt.png' if i==0 else 'scanned-receipt.pdf'
                    raw=(ROOT/'backend/tests/fixtures/ocr'/filename).read_bytes()
                    body=ok(c.post(f"/api/cases/{a['case_id']}/upload",files={'file':(filename,raw,'image/png' if i==0 else 'application/pdf')}))
                    src=body['evidence'][-1];a.update(source_id=src['id'],original_sha256=hashlib.sha256(raw).hexdigest());save()
                    check(f'actor_{i}_durable_pending_ingestion',src['extraction']['status']=='pending')
                    check(f'actor_{i}_original_hash',src['sha256']==a['original_sha256'])
            body=ok(c.get('/api/cases/'+a['case_id']));source=next(s for s in body['evidence'] if s['id']==a['source_id'])
            if phase!='prepare':
                ex=source.get('extraction',{})
                check(f'actor_{i}_real_ocr_completed',ex.get('status') in ('extracted','uncertain'))
                check(f'actor_{i}_amount_and_order_extracted','812.02' in source['text'] and 'TEST-2048' in source['text'])
                check(f'actor_{i}_original_integrity',hashlib.sha256(c.get(f"/api/cases/{a['case_id']}/files/{a['source_id']}").content).hexdigest()==a['original_sha256'])
                check(f'actor_{i}_automatic_investigation',body.get('analysis') is not None and not body.get('analysis_stale'))
                claims=body['analysis']['claims'];mine=[cl for cl in claims if cl['source_id']==source['id']]
                check(f'actor_{i}_source_linked_claim',len(mine)>0 and all(cl['quote'] in source['text'] and cl['source_check']=='quote_in_machine_transcription' for cl in mine))
                check(f'actor_{i}_audit_valid',body['audit_valid'])
                check(f'actor_{i}_extraction_audited',any(e['kind']=='document_read' for e in body['timeline']))
                if phase=='wait':
                    a['preserved_extraction']=ex;a['preserved_analysis']=body['analysis'];save()
                else:
                    check(f'actor_{i}_extraction_survived_deployment',ex==a['preserved_extraction'])
                    check(f'actor_{i}_analysis_survived_deployment',body['analysis']==a['preserved_analysis'])
            check(f'actor_{i}_no_private_vision_disclosure_without_consent',not ok(c.get('/api/evidence-reading'))['enabled'])
        for i,c in enumerate(clients):
            other=state['actors'][1-i]
            for label,suffix in [('case',''),('resolution','/resolution'),('file','/files/'+other['source_id'])]:
                check(f'actor_{i}_foreign_denied_{label}',c.get('/api/cases/'+other['case_id']+suffix).status_code==404)
            check(f'actor_{i}_foreign_merchant_denied',c.get('/api/paypal/autonomy').status_code in (403,404))
            ok(c.post('/api/auth/logout',json={}))
            check(f'actor_{i}_logout_denies_access',c.get('/api/cases/'+state['actors'][i]['case_id']).status_code==401)
        report.write_text(json.dumps({'at':datetime.now(timezone.utc).isoformat(),'base':base,'phase':phase,'checks':checks,
            'passed':all(checks.values()),'payment_or_dispute_writes':0,'manual_analysis_calls':0,
            'scope':'Real OCR on authored synthetic receipt image and scanned PDF; real Gemini source-linked automatic investigations. Accounts operated by API QA, not two independent human testers. No handwriting claim from these printed fixtures.'},indent=2),encoding='utf8')
        print(json.dumps({'phase':phase,'checks':len(checks),'passed':True}))
    finally:
        for c in clients:c.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--phase',choices=['prepare','wait','verify'],required=True)
    p.add_argument('--state',type=Path,default=ROOT/'runtime/saas-document-reading-private.json');p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();run(a.base,a.phase,a.state,a.report)
