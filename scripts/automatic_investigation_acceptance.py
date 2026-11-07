"""One submission -> real public retrieval -> preserved sources -> Gemini.

No /analyze, /approve, /search or /retry request is made by this runner.
Prepare with a stopped worker, restart the service, then wait to verify recovery.
Private credentials/IDs remain ignored; reports contain public URLs and hashes.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import io
import json
from pathlib import Path
import secrets
import time
import httpx

ROOT=Path(__file__).resolve().parents[1]
URLS=['https://decisions.civilresolutionbc.ca/crt/crtd/en/525448/1/document.do',
      'https://www.bclaws.gov.bc.ca/civix/document/id/complete/statreg/12025_01']


def reference_pdf():
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject,ArrayObject,FloatObject,TextStringObject
    writer=PdfWriter();page=writer.add_blank_page(600,800)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 20 740 Td (SYNTHETIC INVESTIGATOR NOTE. Not a real customer dispute.) Tj 0 -24 Td (Distinguish reported accounts from tribunal findings in Moffatt v Air Canada.) Tj 0 -24 Td (Current legislation does not establish a policy in November 2022.) Tj 0 -36 Td (Open the published decision and current legislation through these hyperlinks.) Tj ET');page[NameObject('/Contents')]=writer._add_object(stream)
    annotations=ArrayObject()
    for i,url in enumerate(URLS):
        annotation=DictionaryObject({NameObject('/Type'):NameObject('/Annot'),NameObject('/Subtype'):NameObject('/Link'),NameObject('/Rect'):ArrayObject([FloatObject(x) for x in (20,610-i*24,500,630-i*24)]),NameObject('/A'):DictionaryObject({NameObject('/S'):NameObject('/URI'),NameObject('/URI'):TextStringObject(url)})})
        annotations.append(writer._add_object(annotation))
    page[NameObject('/Annots')]=annotations
    raw=io.BytesIO();writer.write(raw);return raw.getvalue()


def run(args):
    state=json.loads(args.state.read_text(encoding='utf-8')) if args.state.exists() else {'actors':[]}
    checks={};clients=[]
    def save():args.state.parent.mkdir(parents=True,exist_ok=True);args.state.write_text(json.dumps(state,indent=2),encoding='utf-8')
    def check(name,value):
        checks[name]=bool(value)
        if not value:raise AssertionError(name)
    def ok(r):
        if r.status_code!=200:
            state['last_failure']={'status':r.status_code,'detail':r.json().get('detail')};save()
            raise AssertionError('HTTP '+str(r.status_code)+'; private diagnostic retained')
        return r.json()
    try:
        for i in range(2):
            c=httpx.Client(base_url=args.base,timeout=120,limits=httpx.Limits(max_keepalive_connections=0));clients.append(c)
            if len(state['actors'])<=i:
                assert args.phase=='prepare','Prepare accounts first'
                a={'username':'auto_qa_'+secrets.token_hex(6),'password':secrets.token_urlsafe(24),'display_name':'Automatic investigation QA '+str(i+1)}
                result=ok(c.post('/api/auth/register',json=a));a['recovery_code']=result['recovery_code'];state['actors'].append(a);save()
            else:
                a=state['actors'][i];ok(c.post('/api/auth/login',json={k:a[k] for k in ('username','password')}))
            if 'case_id' not in a:
                case=ok(c.post('/api/cases',json={'title':'Public decision versus reported accounts' if i==0 else 'Independent synthetic nonreceipt record', 'reason':'OTHER','amount':'0.00','currency':'CAD'}));a['case_id']=case['id'];save()
            if args.phase=='prepare' and not a.get('submitted'):
                text=('SYNTHETIC INVESTIGATOR NOTE, not a real customer dispute. Please distinguish a party report from the tribunal findings in Moffatt v Air Canada. '
                      'The current legislation does not establish an Air Canada policy in November 2022. Public decision: '+URLS[0]+'\nPrimary legislation: '+URLS[1]) if i==0 else (
                      'SYNTHETIC TEST RECORD, no payment or shipment occurred. The buyer reports a missing parcel. The seller has a reception scan but no destination or recipient identification. Determine what remains unproven. Do not issue a refund or message anyone.')
                pdf=i==0 and args.pdf_references
                raw=reference_pdf() if pdf else text.encode();r=c.post('/api/cases/'+a['case_id']+'/upload',files={'file':('submitted-record.pdf' if pdf else 'submitted-record.txt',raw,'application/pdf' if pdf else 'text/plain')},data={'party':'other'});case=ok(r)
                if pdf:a['pdf_annotation_references']=True
                a.update(submitted=True,original_id=case['evidence'][-1]['id'],original_sha256=hashlib.sha256(raw).hexdigest());save()
                check('actor_'+str(i+1)+'_single_submission_saved',True)
        if args.phase=='prepare':
            for i,c in enumerate(clients):
                case=ok(c.get('/api/cases/'+state['actors'][i]['case_id']))
                check('actor_'+str(i+1)+'_durable_job_visible',case['automation']['state'] in ('queued','running','completed','partial'))
            print(json.dumps({'phase':'prepare','checks':checks,'manual_investigation_or_approval_calls':0},indent=2));return
        for i,c in enumerate(clients):
            a=state['actors'][i];path='/api/cases/'+a['case_id'];prefix='actor_'+str(i+1)+'_'
            if args.phase=='wait':
                deadline=time.monotonic()+480
                while True:
                    case=ok(c.get(path));status=case['automation']['state']
                    if status in ('completed','partial'):break
                    if status=='failed':
                        state['last_failure']={'detail':case['automation']['detail']};save();raise AssertionError('Automatic job failed; private diagnostic retained')
                    if time.monotonic()>deadline:raise AssertionError('Automatic investigation timed out')
                    time.sleep(3)
            else:case=ok(c.get(path))
            check(prefix+'automatic_investigation_finished',case['automation']['state'] in ('completed','partial') and bool(case.get('analysis')) and not case.get('analysis_stale'))
            check(prefix+'actual_gemini',case['analysis']['model']=='gemini-3.1-flash-lite')
            check(prefix+'audit_valid',case['audit_valid'])
            check(prefix+'original_bytes_preserved',hashlib.sha256(c.get(path+'/files/'+a['original_id']).content).hexdigest()==a['original_sha256'])
            check(prefix+'foreign_case_hidden',clients[1-i].get(path).status_code==404)
            check(prefix+'foreign_original_hidden',clients[1-i].get(path+'/files/'+a['original_id']).status_code==404)
            check(prefix+'foreign_automatic_retry_denied',clients[1-i].post(path+'/automation/retry',json={}).status_code==404)
            check(prefix+'foreign_automation_setting_denied',clients[1-i].post(path+'/automation',json={'enabled':False}).status_code==404)
            check(prefix+'no_human_source_approval',not any(e['kind']=='public_evidence_approved' for e in case['timeline']))
            evidence={e['id']:e for e in case['evidence']}
            check(prefix+'all_claims_bound_to_actual_text',bool(case['analysis']['claims']) and all(x['quote'] in evidence[x['source_id']]['text'] for x in case['analysis']['claims']))
            if i==0:
                if a.get('pdf_annotation_references'):
                    root=evidence[a['original_id']]
                    check('pdf_annotation_links_found_without_copying_urls',len(root.get('embedded_links',[]))==2 and all(url not in root['text'] for url in URLS))
                public=[e for e in case['evidence'] if e.get('origin')=='public_web_automatic']
                check('both_actual_html_and_pdf_automatically_preserved',{e['provenance']['mime'] for e in public}=={'text/html','application/pdf'})
                check('both_exact_public_references_retrieved',{e['provenance']['requested_url'] for e in public}==set(URLS))
                check('automatic_sources_remain_unreviewed',all(e['provenance']['review_status']=='unreviewed' and not e['origin_verified'] for e in public))
                check('references_link_to_submitted_parent',all(e['provenance']['parent_reference']['parent_source_id']==a['original_id'] for e in public))
                check('historical_policy_not_established',all(e['provenance']['historical_applicability']=='not_established' for e in public))
                statuses={x['epistemic_status'] for x in case['analysis']['claims']}
                check('party_reports_and_adjudicated_findings_distinguished','party_report' in statuses and bool(statuses & {'document_finding','document_order'}))
                check('public_claims_have_exact_snapshot_offsets',all(evidence[x['source_id']]['text'][x['passage_start']:x['passage_end']]==x['quote'] and x['snapshot_text_sha256']==evidence[x['source_id']]['provenance']['text_sha256'] for x in case['analysis']['claims'] if evidence[x['source_id']].get('provenance')))
                for e in public:
                    check('public_original_'+e['provenance']['mime'],hashlib.sha256(c.get(path+'/files/'+e['id']).content).hexdigest()==e['sha256'])
            fingerprint=hashlib.sha256(json.dumps({'analysis':case['analysis'],'revision':case['revision'],'audit':case['timeline'][-1]['hash']},sort_keys=True).encode()).hexdigest()
            if args.phase=='wait':a['fingerprint']=fingerprint;save()
            check(prefix+'persisted_analysis_revision_audit',fingerprint==a['fingerprint'])
            ok(c.post('/api/auth/logout',json={}));check(prefix+'logout_revokes_session',c.get(path).status_code==401)
            ok(c.post('/api/auth/login',json={k:a[k] for k in ('username','password')}))
            fresh=ok(c.get(path));check(prefix+'return_keeps_investigation',fresh['analysis']==case['analysis'] and fresh['revision']==case['revision'])
        report={'checked_at':datetime.now(timezone.utc).isoformat(),'base_url':args.base,'phase':args.phase,'actor_type':'Two independent automated public-account actors; not two human testers.',
            'checks':checks,'all_passed':all(checks.values()),'automatic_public_sources':URLS,'manual_investigation_or_approval_calls':0,'payment_or_dispute_writes':0}
        args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
    finally:
        for c in clients:c.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',default='http://127.0.0.1:8001');p.add_argument('--phase',choices=['prepare','wait','verify'],required=True);p.add_argument('--pdf-references',action='store_true');p.add_argument('--state',type=Path,default=ROOT/'runtime/saas-automatic-private.json');p.add_argument('--report',type=Path,default=ROOT/'work/automatic-verification.json');run(p.parse_args())
