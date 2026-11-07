import asyncio
import copy
import hashlib
import base64
import pytest
from source_recovery import decision_identity,recovery_query,publisher_candidates,check_decision,automatic_url,publisher_embed
import automatic_investigation as auto
import research_routes as research
from test_automatic_investigation import fake_process

BLOCKED='https://www.canlii.org/en/bc/bccrt/doc/2024/2024bccrt149/2024bccrt149.html'
PUBLISHER='https://decisions.civilresolutionbc.ca/crt/crtd/en/525448/1/document.do'


def document(citation='2024 BCCRT 149',host_url=PUBLISHER):
    text=f'Date Issued: February 14, 2024\nCivil Resolution Tribunal\nIndexed as: Example v. Respondent, {citation}\nAPPLICANT\nRESPONDENT\nREASONS FOR DECISION\nI find the claim made out.'
    return {'id':'D-matched','status':'ready','text':text,'title':'Example decision','raw_sha256':'a'*64,
        'metadata':{'final_url':host_url,'publication_date':'2024-02-14','retrieved_at':'2026-11-07',
        'text_sha256':hashlib.sha256(text.encode()).hexdigest()}}


def test_neutral_citation_query_comes_from_public_canlii_route_only():
    identity=decision_identity(BLOCKED)
    assert identity['citation']=='2024 BCCRT 149'
    query=recovery_query(identity)
    assert query=='"2024 BCCRT 149" British Columbia Civil Resolution Tribunal official decision'
    assert 'site:www.canlii.org' not in query and 'Moffatt' not in query


@pytest.mark.parametrize('url',[
 'https://evil.example/2024bccrt149.html',
 'https://www.canlii.org.evil.example/en/bc/bccrt/doc/2024/2024bccrt149/2024bccrt149.html',
 BLOCKED.replace('2024bccrt149.html','2024bccrt150.html'),
 BLOCKED.replace('/2024/','/2023/'),BLOCKED+'?customer=private',
])
def test_private_spoofed_and_inconsistent_identifiers_do_not_create_recovery_queries(url):
    assert decision_identity(url) is None


def test_harmless_tracking_is_removed_before_automatic_fetch_but_secret_links_stay_blocked():
    assert automatic_url(PUBLISHER+'?utm_source=chatgpt.com')==PUBLISHER
    with pytest.raises(Exception):automatic_url(PUBLISHER+'?access_token=private')


def test_candidates_are_api_backed_original_publisher_only_and_bounded():
    docs=[{'url':'https://lawfirm.example/commentary'},{'url':'http://127.0.0.1/private'},
        {'url':PUBLISHER+'?utm_source=search'},{'url':PUBLISHER},
        {'url':PUBLISHER+'/second'},{'url':PUBLISHER+'/third'}]
    rows=publisher_candidates(docs,decision_identity(BLOCKED),BLOCKED)
    assert [r['url'] for r in rows]==[PUBLISHER,PUBLISHER+'/second']


def test_identity_is_bound_to_exact_preserved_header_and_not_inaccessible_bytes():
    draft=document();result=check_decision(draft,decision_identity(BLOCKED))
    assert result['status']=='matched' and result['observed_citation']=='2024 BCCRT 149'
    assert draft['text'][result['passage_start']:result['passage_end']]==result['identity_passage']
    assert result['text_sha256']==draft['metadata']['text_sha256']
    assert result['byte_equivalence_to_blocked_copy']=='not_verified'


@pytest.mark.parametrize('change',[
 lambda d:d.update(text=d['text'].replace('2024 BCCRT 149','2024 BCCRT 150')),
 lambda d:d['metadata'].update(final_url='https://lawfirm.example/decision'),
 lambda d:d.update(text='An article quotes 2024 BCCRT 149. No original header.'),
 lambda d:d.update(text=d['text'].replace('REASONS FOR DECISION','Commentary')),
 lambda d:d['metadata'].pop('publication_date'),
 lambda d:d.update(status='unavailable',text=''),
])
def test_mismatches_commentary_redirects_and_missing_content_are_rejected(change):
    draft=document();change(draft)
    assert check_decision(draft,decision_identity(BLOCKED))['status']=='not_matched'


def run_recovery(monkeypatch,*,matched=True,resume=False,documents=None):
    case,calls,claim=fake_process(monkeypatch)
    case['evidence'][0]['text']='Private customer text must not be searched. Published decision '+BLOCKED
    if resume:
        claim['progress']['references'][BLOCKED]={'status':'unavailable','draft_id':'D-original','detail':'HTTP 403','parent_source_id':'E1'}
    async def stage(case_id,data,**kw):
        calls.append(('retrieve',data.url,auto.SESSION.get()))
        if data.url==BLOCKED:return {'id':'D-original','status':'unavailable','failure_code':'http_403','failure_message':'HTTP 403; original blocked'}
        d=document('2024 BCCRT 149' if matched else '2024 BCCRT 150')
        d['identity_check']=check_decision(d,kw['recovery_identity']);return d
    async def discover(query,case_id):
        calls.append(('search',query,auto.SESSION.get()))
        return {'status':'completed','documents':documents if documents is not None else [{'url':PUBLISHER,'provider':'Public API'}], 'provider_attempts':[{'provider':'Public API','status':'completed'}]}
    async def collect(case_id,draft_id,**kw):
        calls.append(('collect',kw,auto.SESSION.get()));d=document()
        case['evidence'].append({'id':'E-recovered','title':d['title'],'origin':'public_web_automatic','text':d['text'],
            'sha256':d['raw_sha256'],'provenance':d['metadata']})
    monkeypatch.setattr(auto,'stage_url',stage);monkeypatch.setattr(auto,'discover',discover);monkeypatch.setattr(auto,'collect_draft',collect)
    asyncio.run(auto.process(claim));return case,calls,claim


def test_one_submission_recovers_same_decision_without_erasing_403_or_manual_approval(monkeypatch):
    case,calls,claim=run_recovery(monkeypatch)
    assert [r[1] for r in calls if r[0]=='retrieve']==[BLOCKED,PUBLISHER]
    queries=[r[1] for r in calls if r[0]=='search'];assert len(queries)==1 and 'Private customer' not in queries[0]
    original=claim['progress']['references'][BLOCKED]
    assert original['status']=='unavailable' and original['failure_code']=='http_403' and original['recovery']['status']=='recovered'
    assert len(case['evidence'])==2 and case['evidence'][0]['id']=='E1'
    adoption=next(r[1] for r in calls if r[0]=='collect')
    assert adoption['recovery']['blocked_url']==BLOCKED and adoption['acquisition']=='embedded_reference'
    assert next(r[1] for r in calls if r[0]=='workflow:finish')['state']=='completed'


def test_cached_old_403_recovers_without_requesting_blocked_site_again(monkeypatch):
    case,calls,claim=run_recovery(monkeypatch,resume=True)
    assert [r[1] for r in calls if r[0]=='retrieve']==[PUBLISHER]
    assert claim['progress']['recovery_version']==2


def test_wrong_decision_is_retained_as_rejected_candidate_never_case_evidence(monkeypatch):
    case,calls,claim=run_recovery(monkeypatch,matched=False)
    assert len(case['evidence'])==1 and not any(c[0]=='collect' for c in calls)
    candidate=claim['progress']['recoveries'][BLOCKED]['candidates'][0]
    assert candidate['status']=='rejected' and candidate['identity_check']['observed_citation']=='2024 BCCRT 150'
    assert next(c[1] for c in calls if c[0]=='workflow:finish')['state']=='partial'


def test_no_original_publisher_result_does_not_invent_url_or_document(monkeypatch):
    case,calls,claim=run_recovery(monkeypatch,documents=[{'url':'https://lawfirm.example/commentary'}])
    assert len(case['evidence'])==1
    assert claim['progress']['recoveries'][BLOCKED]['status']=='no_publisher_candidates'
    assert [r[1] for r in calls if r[0]=='retrieve']==[BLOCKED]


@pytest.mark.parametrize('src,allowed',[
 ('/decision/index.do?iframe=true',True),
 ('https://evil.example/decision/index.do?iframe=true',False),
 ('/another/index.do?iframe=true',False),
 ('/decision/index.do?iframe=true&token=private',False),
 ('javascript:alert(1)',False),
])
def test_only_literal_same_document_publisher_frame_is_followed(src,allowed):
    raw=('<html><iframe src="'+src+'"></iframe></html>').encode()
    draft={'id':'D-wrapper','status':'ready','raw_sha256':hashlib.sha256(raw).hexdigest(),
        'content':base64.encodebytes(raw).decode(),'metadata':{'final_url':'https://decisions.civilresolutionbc.ca/decision/index.do','mime':'text/html'}}
    result=publisher_embed(draft,decision_identity(BLOCKED))
    assert bool(result)==allowed
    if allowed:
        assert result['publisher_wrapper']['raw_sha256']==draft['raw_sha256']
        draft['raw_sha256']='0'*64
        assert publisher_embed(draft,decision_identity(BLOCKED)) is None


def test_publisher_wrapper_frame_is_preserved_then_checked_before_adoption(monkeypatch):
    case,calls,claim=fake_process(monkeypatch)
    case['evidence'][0]['text']=BLOCKED
    wrapper=PUBLISHER.replace('/525448/1/document.do','/item/525448/index.do')
    frame=wrapper+'?iframe=true'
    async def stage(case_id,data,**kwargs):
        calls.append(('retrieve',data.url,''))
        if data.url==BLOCKED:return {'id':'D-blocked','status':'unavailable','failure_code':'http_403','failure_message':'HTTP 403'}
        if data.url==wrapper:
            raw=b'<iframe src="?iframe=true"></iframe>'
            return {'id':'D-wrapper','status':'ready','raw_sha256':hashlib.sha256(raw).hexdigest(),'content':base64.b64encode(raw).decode(),
                'text':'Publisher navigation, not a decision.', 'metadata':{'final_url':wrapper,'mime':'text/html'}}
        return document(host_url=frame)
    async def discover(*args):return {'documents':[{'url':wrapper}], 'provider_attempts':[]}
    async def collect(case_id,draft_id,**kwargs):
        calls.append(('collect',kwargs,''))
        case['evidence'].append({'id':'E-frame','sha256':'a'*64,'provenance':{'final_url':frame}})
    monkeypatch.setattr(auto,'stage_url',stage);monkeypatch.setattr(auto,'discover',discover);monkeypatch.setattr(auto,'collect_draft',collect)
    asyncio.run(auto.process(claim))
    assert [c[1] for c in calls if c[0]=='retrieve']==[BLOCKED,wrapper,frame]
    record=claim['progress']['recoveries'][BLOCKED]
    assert record['status']=='recovered' and record['candidates'][0]['status']=='wrapper'
    adoption=next(c[1] for c in calls if c[0]=='collect')
    assert adoption['recovery']['publisher_wrapper']['url']==wrapper


def test_recovery_reads_retained_raw_snapshot_after_staging_omits_content(monkeypatch):
    calls=[];snapshot=document();snapshot['raw']=b'actual retained wrapper'
    async def addresses(url):return ['8.8.8.8']
    async def retrieve(url):return snapshot
    async def rpc(op,args):
        calls.append(op)
        if op=='research:stage':return {'id':'D-retained','status':'ready'}
        return {'id':'D-retained','status':'ready','content':base64.encodebytes(snapshot['raw']).decode()}
    monkeypatch.setattr(research,'public_addresses',addresses);monkeypatch.setattr(research,'retrieve',retrieve);monkeypatch.setattr(research.repo,'rpc',rpc)
    result=asyncio.run(research.stage_url('case',research.URLInput(url=PUBLISHER,consent=True),recovery_identity=decision_identity(BLOCKED)))
    assert calls==['research:stage','research:get'] and base64.b64decode(result['content'])==snapshot['raw']
