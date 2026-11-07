"""Read-only before/after case, research, audit and original-byte comparison.

Uses existing independent QA accounts. No case/research/analysis mutation is sent.
Private IDs and credentials remain in ignored runtime; public reports use counts.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[1]
def digest(data):return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()

def run(args):
    accounts=json.loads(args.accounts.read_text(encoding='utf-8'))['actors']
    baseline=json.loads(args.state.read_text(encoding='utf-8')) if args.state.exists() else {}
    checks={};originals=0;research_records=0
    with httpx.Client(base_url=args.base,timeout=120,limits=httpx.Limits(max_keepalive_connections=0)) as c:
        for i,actor in enumerate(accounts):
            r=c.post('/api/auth/login',json={k:actor[k] for k in ('username','password')});r.raise_for_status()
            if args.phase=='capture':baseline[str(i)]={}
            for case_id in [actor['case_id']]+[actor[k]['case_id'] for k in ('unavailable_probe','primary_automation_probe') if k in actor]:
                r=c.get('/api/cases/'+case_id);r.raise_for_status();case=r.json();case.pop('automation',None)
                r=c.get('/api/cases/'+case_id+'/research');r.raise_for_status();research=r.json();research_records+=len(research)
                files={}
                for source in case['evidence']:
                    if source.get('file_available'):
                        r=c.get('/api/cases/'+case_id+'/files/'+source['id']);r.raise_for_status();files[source['id']]=hashlib.sha256(r.content).hexdigest();assert files[source['id']]==source['sha256'];originals+=1
                values={'case':digest(case),'research':digest(sorted(research,key=lambda d:d['id'])),'files':files}
                if args.phase=='capture':baseline[str(i)][case_id]=values
                else:
                    expected=baseline[str(i)][case_id]
                    for field in values:
                        name='account_'+str(i+1)+'_case_'+str(len(checks))+'_'+field+'_unchanged';checks[name]=values[field]==expected[field]
                    checks['account_'+str(i+1)+'_audit_'+str(len(checks))]=case['audit_valid']
            c.post('/api/auth/logout',json={}).raise_for_status()
    if args.phase=='capture':
        args.state.write_text(json.dumps(baseline,indent=2),encoding='utf-8');print('Captured private baseline; no case or research writes.');return
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'base_url':args.base,'phase':args.phase,'checks':checks,'all_passed':all(checks.values()),'accounts':len(accounts),'cases':sum(len(v) for v in baseline.values()),'original_files_verified':originals,'research_records_verified':research_records,'case_research_or_analysis_writes':0}
    args.report.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2));assert report['all_passed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--phase',choices=['capture','verify'],required=True);p.add_argument('--accounts',type=Path,default=ROOT/'runtime/saas-automatic-host-final-private.json');p.add_argument('--state',type=Path,default=ROOT/'runtime/saas-ui-preservation-private.json');p.add_argument('--report',type=Path,default=ROOT/'work/ui-preservation.json');run(p.parse_args())
