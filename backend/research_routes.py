"""Account-isolated proposals, explicit approval and transactional provenance."""
import base64
import re
from datetime import date, datetime, timezone
from typing import Literal
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
import saas_auth as auth
from saas_store import repo
from store import now, uid
from fixtures import evidence
from public_web import retrieve, normalize_url, public_addresses, RetrievalError
from google_research import call_google, capabilities
from free_search import discover
from source_recovery import check_decision,decision_identity

router=APIRouter(prefix='/api')


class URLInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    url: str=Field(min_length=8,max_length=2048)
    consent: bool=False
    google_context: bool=False
    review_only: bool=False
    relevance: str=Field(default='User-supplied public source; review its contents and relevance.',max_length=1000)
    event_date: date | None=None


class SearchInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    query: str=Field(min_length=8,max_length=600)
    consent: bool=False
    event_date: date | None=None
    google_context: bool=False
    review_only: bool=False


class ApprovalInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    consent: bool=False
    snapshot_sha256: str=Field(pattern=r'^[a-f0-9]{64}$')
    source_kind: Literal['reported_document','tribunal_decision','current_policy','archived_record']='reported_document'
    historical_note: str=Field(default='',max_length=1000)


async def budget(user,kind):
    today=datetime.now(timezone.utc).date().isoformat()
    for key,limit in [('research:'+today+':'+kind+':'+user['id'],8),('research:'+today+':'+kind+':global',40)]:
        result=await repo.rpc('rate',{'key':key,'limit':limit,'seconds':86400},session='')
        if not result['allowed']: raise HTTPException(429,'Today’s public research capacity has been reached. Existing proposals and evidence are retained.')


def public_draft(draft):
    return {k:v for k,v in draft.items() if k!='content'}


async def stage_url(case_id,data,*,recovery_identity=None):
    url=normalize_url(data.url)
    draft={'id':uid('D-'),'url':url,'title':urlsplit(url).hostname,'status':'unavailable','created_at':now(),
           'relevance':data.relevance,'event_date':data.event_date.isoformat() if data.event_date else None,
           'raw_sha256':'','text':'','metadata':{},'google':None}
    raw=None
    try:
        # Validate the destination before sending the URL to an external tool.
        await public_addresses(url)
        source=await retrieve(url)
        raw=source['raw'];draft.update(title=source['title'],status='ready',text=source['text'],metadata=source['metadata'],raw_sha256=source['metadata']['raw_sha256'])
    except RetrievalError as error:
        draft.update(failure_code=error.code,failure_message=error.message)
        if error.code=='unsafe_url': raise HTTPException(422,error.message) from None
    if data.google_context:
        draft['google']=await call_google('url_context',url)
    if recovery_identity:
        draft['identity_check']=check_decision(draft,recovery_identity)
    args={'case_id':case_id,'body':draft,'content':base64.b64encode(raw).decode() if raw is not None else None}
    return await repo.rpc('research:stage',args)


@router.get('/research/config')
async def config(user=Depends(auth.current_session)):
    return {**capabilities(),'search_enabled':True,'search_provider':'Tavily keyless with Wikimedia/Crossref fallback',
            'free_search_notice':'No API key, account or credit card. Keyless limits are shared and not guaranteed; provider throttling is respected. Google Search grounding remains off.'}


@router.get('/cases/{id}/research')
async def drafts(id:str,user=Depends(auth.current_session)):
    return await repo.rpc('research:list',{'case_id':id})


@router.post('/cases/{id}/research/url')
async def from_url(id:str,data:URLInput,user=Depends(auth.current_session)):
    await repo.get(id)
    if not data.consent: raise HTTPException(422,'Authorize retrieval and private staging of this public document. Approval to add it to the case is separate.')
    try: normalize_url(data.url)
    except RetrievalError as e: raise HTTPException(422,e.message) from None
    await budget(user,'url')
    draft = await stage_url(id,data)
    if draft['status'] == 'ready' and not data.review_only:
        await collect_draft(id, draft['id'], acquisition='submitted_url')
        draft = public_draft(await repo.rpc('research:get', {'case_id':id,'id':draft['id']}))
    return draft


@router.post('/cases/{id}/research/search')
async def search(id:str,data:SearchInput,user=Depends(auth.current_session)):
    await repo.get(id)
    if not data.consent: raise HTTPException(422,'Review the public query and authorize Tavily/Wikimedia/Crossref research. Do not include customer or transaction identifiers.')
    await budget(user,'search')
    result=await discover(data.query,id)
    report={'id':uid('D-'),'url':'search:'+uid('Q-'),'raw_sha256':'','title':'Public evidence research',
            'created_at':now(),'status':'research_report','query':data.query,'google':result,'text':'',
            'event_date':data.event_date.isoformat() if data.event_date else None,'metadata':{},'relevance':'User-authorized free public research; not official evidence.'}
    saved=await repo.rpc('research:stage',{'case_id':id,'body':report})
    # Bounded autonomous acquisition visits only API-returned URLs, never
    # links embedded in a page or a URL invented in its answer.
    acquired=[]
    for doc in result.get('documents',[])[:3]:
        try:
            await budget(user,'url')
            draft=await stage_url(id,URLInput(url=doc['url'],consent=True,relevance=doc['provider']+': '+doc['relevance'],event_date=data.event_date,google_context=data.google_context))
            if draft['status']=='ready' and not data.review_only:
                await collect_draft(id,draft['id'],acquisition='authorized_search')
                draft=public_draft(await repo.rpc('research:get',{'case_id':id,'id':draft['id']}))
            acquired.append(draft)
        except HTTPException as error:
            acquired.append({'status':'unavailable','failure_message':error.detail})
    return {'report':saved,'proposals':acquired}


@router.post('/cases/{id}/research/{draft_id}/dismiss')
async def dismiss(id:str,draft_id:str,user=Depends(auth.current_session)):
    return await repo.rpc('research:dismiss',{'case_id':id,'id':draft_id})


@router.post('/cases/{id}/research/{draft_id}/approve')
async def approve(id:str,draft_id:str,data:ApprovalInput,user=Depends(auth.current_session)):
    return await collect_draft(id,draft_id,approval=data)


def inferred_kind(metadata, title, text=''):
    host=urlsplit(metadata.get('final_url','')).hostname or ''
    if host=='decisions.civilresolutionbc.ca' and re.search(r'\bBCCRT\b|Civil Resolution Tribunal',title+' '+text[:1000],re.I):
        return 'tribunal_decision'
    if any(word in metadata.get('final_url','').lower() for word in ('/policy','/policies','bereavement')):
        return 'current_policy'
    return 'reported_document'


async def collect_draft(id,draft_id,*,approval=None,acquisition='human_review',parent=None,recovery=None):
    body=await repo.get(id)
    body.setdefault('automatic_investigation',True)
    body['automatic_workflow_version']=2
    draft=await repo.rpc('research:get',{'case_id':id,'id':draft_id})
    if approval and not approval.consent: raise HTTPException(422,'Review the exact extracted text and authorize preservation before adding it to the case.')
    if approval and approval.snapshot_sha256!=draft['raw_sha256']: raise HTTPException(409,'The approved snapshot hash does not match the staged document')
    if draft.get('source_id'): return {'case':body,'duplicate':True}
    if draft['status']!='ready' or not draft.get('content'): raise HTTPException(409,'This proposal has no readable snapshot to approve. Upload an authorized copy or use another source.')
    if recovery:
        identity=decision_identity(recovery['blocked_url'])
        if not identity:raise HTTPException(409,'No supported public document identity was established.')
        draft['identity_check']=check_decision(draft,identity)
        if draft['identity_check']['status']!='matched':
            raise HTTPException(409,'The recovered document did not pass its source-identity check; it was not added to evidence.')
    if len(body['evidence'])>=40: raise HTTPException(422,'Maximum 40 evidence sources per case')
    prior=next((s for s in body['evidence'] if s.get('sha256')==draft['raw_sha256'] and s.get('provenance',{}).get('final_url')==draft['metadata']['final_url']),None)
    if prior: return {'case':body,'duplicate':True}
    kind=approval.source_kind if approval else inferred_kind(draft['metadata'],draft['title'],draft['text'])
    if kind=='archived_record' and not draft['metadata'].get('archive_capture_requested'):
        raise HTTPException(422,'No archive capture was established. A current webpage cannot be labeled as an archived record.')
    meta={**draft['metadata'],'source_kind':kind,'classification_basis':'user-reviewed classification; not independent authentication' if approval else 'URL/document metadata heuristic; reviewable and not independently authenticated',
          'historical_note':approval.historical_note if approval else 'Automatically collected source. Retrieval does not establish historical policy applicability.',
          'event_date':draft.get('event_date'),'collected_at':now(),'research_proposal_id':draft_id,
          'acquisition_mode':acquisition,'review_status':'human_reviewed' if approval else 'unreviewed',
          'parent_reference':parent}
    if recovery:meta['source_recovery']={**recovery,'identity_check':draft['identity_check']}
    automatic=acquisition=='embedded_reference'
    source=evidence(draft['title'][:160],draft['text'],'other','public_web_automatic' if automatic else 'public_web_snapshot')
    source.update(sha256=draft['raw_sha256'],synthetic=False,file_available=True,mime=meta['mime'],origin_verified=False,provenance=meta)
    body['evidence'].append(source);body['analysis_stale']=body.get('analysis') is not None
    raw=base64.b64decode(draft['content'])
    file=repo.file_record(source['id'],raw,meta['mime'],draft['title'][:150]+('.pdf' if meta['mime']=='application/pdf' else '.html' if 'html' in meta['mime'] else '.txt'))
    mutation=repo.mutation(body,'public_source_recovered' if recovery else 'public_evidence_approved' if approval else 'public_evidence_acquired',{'evidence_id':source['id'],'url':meta['final_url'],'raw_sha256':source['sha256'],'text_sha256':meta['text_sha256'],'source_kind':kind,'acquisition_mode':acquisition,'parent_reference':parent,**({'source_recovery':meta['source_recovery']} if recovery else {})},file=file)
    return await repo.rpc('research:approve',{'case_id':id,'id':draft_id,'mutation':mutation})
