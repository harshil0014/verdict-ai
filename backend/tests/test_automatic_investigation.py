"""Automatic research must be bounded, resumable and separate from actions."""
import asyncio
import copy
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path
import pytest
from fastapi import HTTPException
import automatic_investigation as auto
import research_routes as research
from investigator import reviewed_public_classification
from domain import Support
from saas_store import SESSION


def source(text,origin='user_upload',**extra):
    return {'id':'E1','title':'Original','text':text,'origin':origin,**extra}


def test_literal_links_and_pdf_annotations_keep_parent_but_do_not_recurse():
    rows=auto.references([source('A published policy (https://agency.gov/policy).',embedded_links=[{'url':'https://agency.gov/decision.pdf','page':2}]),
        source('https://evil.example/next','public_web_automatic'),source('https://other.example/next','public_web_snapshot')])
    assert [r['url'] for r in rows]==['https://agency.gov/policy','https://agency.gov/decision.pdf']
    assert rows[1]['parent_source_id']=='E1' and rows[1]['page']==2


@pytest.mark.parametrize('url',['http://127.0.0.1/private','https://user:password@example.com/','https://example.com/?access_token=private','https://agency.gov/?email=private%40example.com'])
def test_unsafe_or_customer_query_references_are_withheld_without_secret_in_progress(url):
    ref=auto.references([source('Policy '+url)])[0]
    assert ref['failure'] and ref['url'].startswith('blocked-reference-')
    assert 'password' not in ref['context'] and 'email=' not in ref['context']


def test_search_fallback_never_uses_private_case_context_or_arbitrary_path_segments():
    q=auto.public_fallback_query('https://carrier.example/refund/customer-name-123/policy')
    assert q=='site:carrier.example policy refund official public document'
    assert auto.public_fallback_query('https://carrier.example/customer-name-123/tracking') is None


@pytest.mark.parametrize('text,quote,expected',[
 ('A chatbot suggested a retroactive fare.','Apply within 90 days.','party_report'),
 ('The company admitted misleading information.','A representative admitted the words were misleading.','party_report'),
 ('The tribunal found negligent misrepresentation.','I find the claim of negligent misrepresentation is made out.','document_finding'),
 ('A flight was booked in November.','In November, the applicant booked a flight.','uncertain'),
])
def test_model_finding_labels_require_explicit_adjudication_in_the_actual_cited_passage(text,quote,expected):
    review=Support(claim_id='C1',support='entailed',reason='Present in the source',epistemic_status='document_finding',epistemic_reason='Model proposed a finding')
    status,reason=reviewed_public_classification({'text':text,'quote':quote},review,{'provenance':{'source_kind':'tribunal_decision'}})
    assert status==expected and reason


def test_automatic_reference_candidates_are_bounded_and_unique():
    rows=auto.references([source(' '.join('https://agency.gov/policy/'+str(i) for i in range(100)))])
    assert len(rows)==24
    assert len(auto.references([source('https://agency.gov/a https://agency.gov/a')]))==1


def fake_process(monkeypatch,refs=None,outcomes=None,retrieval='ready',fail_model=False):
    case={'id':'V-test','title':'Test','evidence':[source('Policy https://agency.gov/policy')], 'requests':[], 'revision':2,'analysis':None}
    calls=[]
    async def get(case_id):return copy.deepcopy(case)
    async def rpc(op,args=None,session=None):
        calls.append((op,copy.deepcopy(args),SESSION.get()))
        return {'ok':True}
    async def budget(user,kind):calls.append(('budget',kind,SESSION.get()))
    async def stage(case_id,data):
        calls.append(('retrieve',data.url,SESSION.get()))
        return {'id':'D1','status':retrieval,'raw_sha256':'snapshot','metadata':{'final_url':data.url,'retrieved_at':'2026-11-07'},'failure_message':'Source refused access'}
    async def collect(case_id,draft_id,**kwargs):
        calls.append(('collect',kwargs,SESSION.get()))
        case['evidence'].append(source('The actual source content.','public_web_automatic',id='E2',sha256='snapshot',provenance={'final_url':'https://agency.gov/policy'}))
    async def investigate(case_id,on_reserved=None,before_commit=None):
        calls.append(('investigate',None,SESSION.get()))
        if on_reserved:await on_reserved('job-test')
        if fail_model:raise HTTPException(502,'Do not expose unexpected provider bodies')
        if before_commit:await before_commit()
    monkeypatch.setattr(auto.repo,'get',get);monkeypatch.setattr(auto.repo,'rpc',rpc)
    monkeypatch.setattr(auto,'budget',budget);monkeypatch.setattr(auto,'stage_url',stage)
    monkeypatch.setattr(auto,'collect_draft',collect);monkeypatch.setattr(auto,'run_investigation',investigate)
    async def discover(query,case_id):return {'status':'unavailable','documents':[],'provider_attempts':[]}
    monkeypatch.setattr(auto,'discover',discover)
    claim={'case_id':'V-test','owner_id':'owner-test','generation':1,'lease_token':'lease-test','session_hash':'internal-session', 'progress':{'references':outcomes or {}}}
    return case,calls,claim


def test_one_evidence_submission_retrieves_preserves_and_investigates_without_approval(monkeypatch):
    case,calls,claim=fake_process(monkeypatch)
    asyncio.run(auto.process(claim))
    order=[x[0] for x in calls]
    assert order.index('retrieve')<order.index('collect')<order.index('investigate')
    assert next(x for x in calls if x[0]=='collect')[1]['acquisition']=='embedded_reference'
    finish=next(x[1] for x in calls if x[0]=='workflow:finish')
    assert finish['state']=='completed'
    assert SESSION.get()==''
    assert all(x[2]=='internal-session' for x in calls)
    assert not any('paypal' in x[0] or 'message' in x[0] for x in calls)


def test_unavailable_link_still_investigates_original_with_visible_partial_status(monkeypatch):
    case,calls,claim=fake_process(monkeypatch,retrieval='unavailable')
    asyncio.run(auto.process(claim))
    assert any(x[0]=='investigate' for x in calls) and not any(x[0]=='collect' for x in calls)
    assert next(x[1] for x in calls if x[0]=='workflow:finish')['state']=='partial'
    assert claim['progress']['references']['https://agency.gov/policy']['detail']=='Source refused access'


def test_resume_does_not_refetch_completed_reference(monkeypatch):
    case,calls,claim=fake_process(monkeypatch,outcomes={'https://agency.gov/policy':{'status':'preserved'}})
    asyncio.run(auto.process(claim))
    assert not any(x[0] in ('retrieve','collect') for x in calls)
    assert any(x[0]=='investigate' for x in calls)


def test_ready_checkpoint_is_adopted_after_restart_without_new_fetch(monkeypatch):
    case,calls,claim=fake_process(monkeypatch,outcomes={'https://agency.gov/policy':{'status':'ready','draft_id':'D1','parent_source_id':'E1'}})
    asyncio.run(auto.process(claim))
    assert not any(x[0]=='retrieve' for x in calls)
    assert any(x[0]=='collect' for x in calls)


def test_committed_fresh_analysis_is_not_repeated_after_worker_restart(monkeypatch):
    from store import digest
    case,calls,claim=fake_process(monkeypatch,outcomes={'https://agency.gov/policy':{'status':'preserved'}})
    case['analysis']={'input_digest':digest(auto.investigation_payload(case))}
    asyncio.run(auto.process(claim))
    assert not any(x[0]=='investigate' for x in calls)


def test_model_failure_retains_original_and_records_recoverable_failure(monkeypatch):
    case,calls,claim=fake_process(monkeypatch,fail_model=True)
    asyncio.run(auto.process(claim))
    assert case['evidence'][0]['id']=='E1'
    finish=next(x[1] for x in calls if x[0]=='workflow:finish')
    assert finish['state']=='failed' and 'provider bodies' not in finish['detail']


@pytest.mark.parametrize('failure,expected_calls',[('dns_failed',3),('network_failed',3),('http_503',3),('http_403',1),('http_429',1)])
def test_transient_reads_have_bounded_retry_but_refusals_and_limits_are_not_retried(monkeypatch,failure,expected_calls):
    case,calls,claim=fake_process(monkeypatch)
    attempts=[]
    async def stage(case_id,data):
        attempts.append(data.url)
        return {'id':'D1','status':'unavailable','failure_code':failure,'failure_message':'Source unavailable'}
    async def no_wait(seconds):pass
    monkeypatch.setattr(auto,'stage_url',stage);monkeypatch.setattr(auto,'backoff',no_wait)
    asyncio.run(auto.process(claim))
    assert len(attempts)==expected_calls
    assert any(x[0]=='investigate' for x in calls)


def test_lease_revocation_prevents_research_and_result_commit(monkeypatch):
    case,calls,claim=fake_process(monkeypatch)
    async def lost(op,args=None,session=None):
        if op=='workflow:heartbeat':raise HTTPException(409,'lease lost')
        return {}
    monkeypatch.setattr(auto.repo,'rpc',lost)
    asyncio.run(auto.process(claim))
    assert not any(x[0] in ('collect','investigate','retrieve') for x in calls)


def test_storage_connection_interruption_requeues_for_state_reconciliation(monkeypatch):
    case,calls,claim=fake_process(monkeypatch)
    async def interrupted(*args,**kwargs):raise HTTPException(503,'Cloud database connection failed. Refresh to check whether the operation completed')
    async def no_wait(seconds):pass
    monkeypatch.setattr(auto,'run_investigation',interrupted);monkeypatch.setattr(auto,'backoff',no_wait)
    asyncio.run(auto.process(claim))
    assert any(x[0]=='workflow:release' for x in calls)
    assert not any(x[0]=='workflow:finish' for x in calls)


def test_submitted_url_automatically_collects_without_separate_approval(monkeypatch):
    calls=[]
    async def get(id):calls.append('ownership');return {}
    async def budget(user,kind):pass
    async def stage(id,data):calls.append('retrieve');return {'id':'D1','status':'ready'}
    async def collect(id,draft,**kw):calls.append(kw['acquisition'])
    async def rpc(op,args):return {'id':'D1','status':'approved','content':'private bytes'}
    monkeypatch.setattr(research.repo,'get',get);monkeypatch.setattr(research.repo,'rpc',rpc)
    monkeypatch.setattr(research,'budget',budget);monkeypatch.setattr(research,'stage_url',stage);monkeypatch.setattr(research,'collect_draft',collect)
    result=asyncio.run(research.from_url('owned',research.URLInput(url='https://agency.gov/policy',consent=True),{'id':'owner'}))
    assert calls==['ownership','retrieve','submitted_url'] and 'content' not in result


def test_foreign_case_is_denied_before_any_automatic_url_retrieval(monkeypatch):
    async def denied(id):raise HTTPException(404,'Not found')
    async def forbidden(*args):raise AssertionError('Foreign case triggered research')
    monkeypatch.setattr(research.repo,'get',denied);monkeypatch.setattr(research,'stage_url',forbidden)
    with pytest.raises(HTTPException) as error:asyncio.run(research.from_url('foreign',research.URLInput(url='https://agency.gov/policy',consent=True),{'id':'other'}))
    assert error.value.status_code==404


def test_pdf_hyperlink_annotation_is_extracted_without_executing_actions():
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject,ArrayObject,FloatObject,TextStringObject
    writer=PdfWriter();page=writer.add_blank_page(600,800)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 20 700 Td (An original document with a policy hyperlink for independent investigation.) Tj ET');page[NameObject('/Contents')]=writer._add_object(stream)
    annotation=DictionaryObject({NameObject('/Type'):NameObject('/Annot'),NameObject('/Subtype'):NameObject('/Link'),NameObject('/Rect'):ArrayObject([FloatObject(x) for x in (20,680,200,720)]),NameObject('/A'):DictionaryObject({NameObject('/S'):NameObject('/URI'),NameObject('/URI'):TextStringObject('https://agency.gov/policy.pdf')})})
    page[NameObject('/Annots')]=ArrayObject([writer._add_object(annotation)])
    raw=io.BytesIO();writer.write(raw)
    result=subprocess.run([sys.executable,str(Path(auto.__file__).with_name('parse_pdf.py'))],input=raw.getvalue(),capture_output=True,timeout=15)
    assert result.returncode==0
    doc=json.loads(result.stdout);assert doc['links']==[{'url':'https://agency.gov/policy.pdf','page':1}]
    assert 'An original document' in doc['text']
