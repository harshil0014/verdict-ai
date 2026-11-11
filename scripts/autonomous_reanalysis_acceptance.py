"""One controlled new evidence submission, then read-only verification.

Uses only the authored QA case from document_reading_acceptance. No financial
action, provider operation, manual analyze request or automatic upload retry.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import httpx


def run(base,state_path,report,phase):
    state=json.loads(state_path.read_text());actor=state['actors'][0]
    with httpx.Client(base_url=base,timeout=180) as c:
        def ok(r):
            assert r.status_code==200,'HTTP '+str(r.status_code)
            return r.json()
        ok(c.post('/api/auth/login',json={k:actor[k] for k in ('username','password')}))
        path='/api/cases/'+actor['case_id']
        if phase=='submit':
            assert not actor.get('followup_attempted'),'An upload attempt already exists; inspect state rather than replaying it'
            before=ok(c.get(path));actor['before_followup_analysis']=before['analysis'];actor['followup_attempted']=True
            state_path.write_text(json.dumps(state,indent=2),encoding='utf8')
            after=ok(c.post(path+'/evidence',json={'title':'Authored conflicting buyer receipt','party':'buyer',
                'text':'AUTHORED FICTIONAL TEST RECEIPT. Order TEST-2048. Total: USD 900.00. Date: 2026-11-08. This conflicts with the seller receipt of USD 812.02. No real payment or physical fulfillment is asserted. These records exist only to test review.'}))
            actor['followup_source_id']=after['evidence'][-1]['id'];state_path.write_text(json.dumps(state,indent=2),encoding='utf8')
            print('New authored evidence submitted once; no manual analysis call.')
            return
        body=ok(c.get(path));prior=actor['before_followup_analysis'];source=next(e for e in body['evidence'] if e['id']==actor['followup_source_id'])
        current=body.get('analysis') or {};claims=[cl for cl in current.get('claims',[]) if cl['source_id']==source['id']]
        original=next(e for e in body['evidence'] if e['id']==actor['source_id'])
        checks={'new_evidence_automatically_investigated':bool(current) and not body.get('analysis_stale') and current.get('input_digest')!=prior['input_digest'],
            'new_source_has_exact_preserved_passage':bool(claims) and all(cl['quote'] in source['text'] for cl in claims),
            'prior_investigation_remains_in_audit':any(e['kind']=='investigation_updated' and e['data'].get('analysis')==prior for e in body['timeline']),
            'original_file_and_extraction_retained':original['sha256']==actor['original_sha256'] and original['extraction']==actor['preserved_extraction'],
            'audit_valid':body['audit_valid']}
        assert all(checks.values()),str(checks)
        actor['preserved_analysis']=current;state_path.write_text(json.dumps(state,indent=2),encoding='utf8')
        report.write_text(json.dumps({'checked_at':datetime.now(timezone.utc).isoformat(),'base':base,'checks':checks,
            'passed':True,'manual_analysis_calls':0,'financial_actions':0,'scope':'Real automatic Gemini reassessment after one newly submitted authored contradictory receipt; prior analysis/originals preserved. Not real merchant evidence.'},indent=2),encoding='utf8')
        print(json.dumps({'checks':len(checks),'passed':True}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--state',type=Path,required=True)
    p.add_argument('--phase',choices=['submit','verify'],required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();run(a.base,a.state,a.report,a.phase)
