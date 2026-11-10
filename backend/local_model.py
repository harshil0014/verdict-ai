"""Gemini fallback broker. Local inference is reached through an outbound worker."""
import asyncio,json
from contextlib import suppress
from fastapi import APIRouter,Request,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from typing import Literal
from saas_store import repo,SESSION
from store import digest
import saas_auth as auth


class LocalModelError(Exception):
    def __init__(self,code):self.code=code;super().__init__(code)


async def available():
    if repo.client is None or not SESSION.get():return False
    try:return bool((await repo.rpc('local_model:available')).get('available'))
    except HTTPException:return False


def request_packet(system,payload,schema):
    # Identical complete system/payload; never shorten evidence for a fallback.
    request={'system':system,'payload':payload,'schema':schema.model_json_schema(),'max_output_tokens':6000}
    text=json.dumps(request,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    if len(text.encode())>1400000:raise LocalModelError('context_limit')
    return text,digest(text.encode())


async def generate(system,payload,schema):
    text,request_hash=request_packet(system,payload,schema)
    job=None
    try:
        job=await repo.rpc('local_model:enqueue',{'request_text':text,'request_digest':request_hash})
        if not job.get('available'):raise LocalModelError('ollama_unavailable')
        async with asyncio.timeout(270):
            state=job
            while state['state'] in ('queued','running'):
                await asyncio.sleep(2)
                state=await repo.rpc('local_model:poll',{'job_id':job['id']})
            if state['state']!='completed':raise LocalModelError(state.get('error_code') or 'worker_interrupted')
            result=state['result']
            if state.get('request_digest',request_hash)!=request_hash or result.get('done_reason')!='stop':raise LocalModelError('invalid_response')
            try:parsed=schema.model_validate_json(result['content'])
            except Exception:
                await repo.rpc('local_model:reject',{'job_id':job['id']})
                raise LocalModelError('invalid_response') from None
            return parsed,{'provider':'Ollama','model':result['model'],'model_digest':result['model_digest'],
                'request_digest':request_hash,'promptTokenCount':result['prompt_tokens'],'candidatesTokenCount':result['output_tokens'],
                'context_tokens':result['context_tokens'],'full_context':True}
    except (TimeoutError,asyncio.CancelledError) as error:
        if job and job.get('id'):
            with suppress(Exception):await asyncio.shield(repo.rpc('local_model:cancel',{'job_id':job['id']}))
        if isinstance(error,asyncio.CancelledError):raise
        raise LocalModelError('worker_interrupted') from None


router=APIRouter(prefix='/api/local-model')
class Lease(BaseModel):
    model_config=ConfigDict(extra='forbid')
    job_id:str=Field(pattern=r'^[a-f0-9-]{36}$')
    lease_token:str=Field(pattern=r'^[a-f0-9-]{36}$')
class Result(BaseModel):
    model_config=ConfigDict(extra='forbid')
    content:str=Field(max_length=1000000)
    model:str=Field(max_length=100)
    model_digest:str=Field(pattern=r'^[a-f0-9]{64}$')
    done_reason:Literal['stop']
    prompt_tokens:int=Field(ge=1,le=262144)
    output_tokens:int=Field(ge=1,le=6000)
    context_tokens:int=Field(ge=4096,le=262144)
class Completion(Lease):
    request_digest:str=Field(pattern=r'^[a-f0-9]{64}$')
    result:Result
class Failure(Lease):
    error_code:Literal['context_limit','ollama_unavailable','invalid_response','generation_limit','worker_interrupted','model_changed']

def worker_hash(request):
    value=request.headers.get('authorization','')
    if not value.startswith('Bearer ') or not 40<=len(value[7:])<=128:raise HTTPException(401,'Worker authentication required')
    return auth.token_hash(value[7:])

@router.post('/claim')
async def claim(request:Request):
    return await repo.rpc('local_model:claim',{'worker_hash':worker_hash(request)},session='')
@router.post('/renew')
async def renew(request:Request,data:Lease):
    return await repo.rpc('local_model:renew',{**data.model_dump(),'worker_hash':worker_hash(request)},session='')
@router.post('/complete')
async def complete(request:Request,data:Completion):
    return await repo.rpc('local_model:complete',{**data.model_dump(),'worker_hash':worker_hash(request)},session='')
@router.post('/fail')
async def fail(request:Request,data:Failure):
    return await repo.rpc('local_model:fail',{**data.model_dump(),'worker_hash':worker_hash(request)},session='')
