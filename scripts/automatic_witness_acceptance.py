"""A synthetic portal reply must trigger reanalysis without an analyze call."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import time
import httpx


def run(args):
    state=json.loads(args.state.read_text(encoding='utf-8'));actor=state['actors'][1]
    def save():args.state.write_text(json.dumps(state,indent=2),encoding='utf-8')
    def ok(r):
        assert r.status_code==200,'HTTP '+str(r.status_code)
        return r.json()
    with httpx.Client(base_url=args.base,timeout=120,limits=httpx.Limits(max_keepalive_connections=0)) as c:
        ok(c.post('/api/auth/login',json={k:actor[k] for k in ('username','password')}))
        path='/api/cases/'+actor['case_id'];case=ok(c.get(path))
        witness=actor.setdefault('automatic_witness_probe',{})
        if not witness:
            assert case['analysis'] and case['automation']['state']=='completed'
            witness['previous_analysis']=case['analysis']['created_at']
            r=ok(c.post(path+'/requests',json={'witness_id':'manual','title':'Synthetic destination clarification',
                'question':'In this synthetic test only, was a destination or recipient recorded?','recipient':'carrier'}))
            witness.update(request_id=r['request']['id'],portal_token=r['portal_fragment'].split('=',1)[1]);save()
        if not witness.get('submitted'):
            with httpx.Client(base_url=args.base,timeout=90) as portal:
                ok(portal.post('/api/portal',headers={'Authorization':'Bearer '+witness['portal_token']},json={
                    'title':'Synthetic carrier reply; no real shipment',
                    'text':'SYNTHETIC TEST RESPONSE. No real parcel or customer exists. The record identifies only reception; it does not establish a matching destination or the intended recipient. No delivery proof was obtained.',
                    'party':'seller'}))
            witness['submitted']=True;save()
        deadline=time.monotonic()+480
        while True:
            case=ok(c.get(path))
            if case['automation']['state'] in ('completed','partial') and case['analysis']['created_at']!=witness['previous_analysis']:break
            assert case['automation']['state']!='failed','Automatic witness investigation failed'
            assert time.monotonic()<deadline,'Timed out waiting for witness reanalysis'
            time.sleep(3)
        request=next(r for r in case['requests'] if r['id']==witness['request_id'])
        reply=next(e for e in case['evidence'] if e['id']==request['evidence_id'])
        checks={'reply_received':request['status']=='received','recipient_bound_to_stored_request':reply['party']=='carrier',
            'investigation_updated_without_manual_analyze':case['analysis']['created_at']!=witness['previous_analysis'] and not case['analysis_stale'],
            'new_response_reached_investigation':any(x['source_id']==reply['id'] for x in case['analysis']['claims']),
            'every_quote_exists':all(x['quote'] in next(e for e in case['evidence'] if e['id']==x['source_id'])['text'] for x in case['analysis']['claims']),
            'audit_valid':case['audit_valid']}
        actor['fingerprint']=hashlib.sha256(json.dumps({'analysis':case['analysis'],'revision':case['revision'],'audit':case['timeline'][-1]['hash']},sort_keys=True).encode()).hexdigest();save()
        report={'checked_at':datetime.now(timezone.utc).isoformat(),'base_url':args.base,'checks':checks,'all_passed':all(checks.values()),
            'data_kind':'Synthetic user-authored portal reply; real cloud/model workflow','manual_analyze_calls':0,'messages_sent_to_third_parties':0,'payment_writes':0}
        args.report.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2));assert report['all_passed']


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--state',type=Path,required=True);p.add_argument('--report',type=Path,required=True);run(p.parse_args())
