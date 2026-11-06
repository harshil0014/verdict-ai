"""Account-isolated proposals, explicit approval and transactional provenance."""
import base64
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

router=APIRouter(prefix='/api')


class URLInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    url: str=Field(min_length=8,max_length=2048)
    consent: bool=False
    google_context: bool=False
    relevance: str=Field(default='User-supplied public source; review its contents and relevance.',max_length=1000)
    event_date: date | None=None


class SearchInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    query: str=Field(min_length=8,max_length=600)
    consent: bool=False
    event_date: date | None=None
    google_context: bool=False


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


async def stage_url(case_id,data):
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
    return await stage_url(id,data)


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
            acquired.append(await stage_url(id,URLInput(url=doc['url'],consent=True,relevance=doc['provider']+': '+doc['relevance'],event_date=data.event_date,google_context=data.google_context)))
        except HTTPException as error:
            acquired.append({'status':'unavailable','failure_message':error.detail})
    return {'report':saved,'proposals':acquired}


@router.post('/cases/{id}/research/{draft_id}/dismiss')
async def dismiss(id:str,draft_id:str,user=Depends(auth.current_session)):
    return await repo.rpc('research:dismiss',{'case_id':id,'id':draft_id})


@router.post('/cases/{id}/research/{draft_id}/approve')
async def approve(id:str,draft_id:str,data:ApprovalInput,user=Depends(auth.current_session)):
    body=await repo.get(id)
    draft=await repo.rpc('research:get',{'case_id':id,'id':draft_id})
    if not data.consent: raise HTTPException(422,'Review the exact extracted text and authorize preservation before adding it to the case.')
    if data.snapshot_sha256!=draft['raw_sha256']: raise HTTPException(409,'The approved snapshot hash does not match the staged document')
    if draft.get('source_id'): return {'case':body,'duplicate':True}
    if draft['status']!='ready' or not draft.get('content'): raise HTTPException(409,'This proposal has no readable snapshot to approve. Upload an authorized copy or use another source.')
    if len(body['evidence'])>=40: raise HTTPException(422,'Maximum 40 evidence sources per case')
    prior=next((s for s in body['evidence'] if s.get('sha256')==draft['raw_sha256'] and s.get('provenance',{}).get('final_url')==draft['metadata']['final_url']),None)
    if prior: return {'case':body,'duplicate':True}
    if data.source_kind=='archived_record' and not draft['metadata'].get('archive_capture_requested'):
        raise HTTPException(422,'No archive capture was established. A current webpage cannot be labeled as an archived record.')
    meta={**draft['metadata'],'source_kind':data.source_kind,'classification_basis':'user-reviewed classification; not independent authentication',
          'historical_note':data.historical_note,'event_date':draft.get('event_date'),'approved_at':now(),'research_proposal_id':draft_id}
    source=evidence(draft['title'][:160],draft['text'],'other','public_web_snapshot')
    source.update(sha256=draft['raw_sha256'],synthetic=False,file_available=True,mime=meta['mime'],origin_verified=False,provenance=meta)
    body['evidence'].append(source);body['analysis_stale']=body.get('analysis') is not None
    raw=base64.b64decode(draft['content'])
    file=repo.file_record(source['id'],raw,meta['mime'],draft['title'][:150]+('.pdf' if meta['mime']=='application/pdf' else '.html' if 'html' in meta['mime'] else '.txt'))
    mutation=repo.mutation(body,'public_evidence_approved',{'evidence_id':source['id'],'url':meta['final_url'],'raw_sha256':source['sha256'],'text_sha256':meta['text_sha256'],'source_kind':data.source_kind},file=file)
    return await repo.rpc('research:approve',{'case_id':id,'id':draft_id,'mutation':mutation})
