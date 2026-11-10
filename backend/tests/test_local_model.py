import asyncio,json,sys,importlib.util
from pathlib import Path
from types import SimpleNamespace
import httpx,pytest
from pydantic import BaseModel
import investigator as inv
import local_model as local

class Answer(BaseModel):
    quote:str

def test_full_context_packet_preserves_every_source_and_schema():
    payload={'sources':[{'id':'E1','text':'first\npassage'},{'id':'E2','text':'last Ω passage'}]}
    text,sha=local.request_packet('Keep original context',payload,Answer)
    obj=json.loads(text)
    assert obj['payload']==payload and obj['system']=='Keep original context'
    assert obj['schema']==Answer.model_json_schema() and len(sha)==64
    with pytest.raises(local.LocalModelError):local.request_packet('system',{'data':'x'*1500000},Answer)

def test_gemini_is_first_and_local_receives_identical_request_after_failure(monkeypatch):
    calls=[];payload={'source':'exact full evidence'}
    async def ready():return True
    async def primary(system,data,schema,attempts):
        calls.append(('Gemini',system,data,schema,attempts));raise inv.ModelError('Gemini returned HTTP 503; temporary')
    async def fallback(system,data,schema):calls.append(('Ollama',system,data,schema));return Answer(quote=data['source']),{'provider':'Ollama','model':'local-tested-model'}
    monkeypatch.setattr(local,'available',ready);monkeypatch.setattr(inv,'_generate_gemini',primary);monkeypatch.setattr(local,'generate',fallback)
    answer,usage=asyncio.run(inv.generate('original system',payload,Answer))
    assert [c[0] for c in calls]==['Gemini','Ollama'] and calls[0][1:4]==calls[1][1:4]
    assert calls[0][4]==1 and answer.quote==payload['source'] and usage['provider']=='Ollama'

def test_successful_primary_never_calls_local_inference(monkeypatch):
    async def ready():return True
    async def primary(*a,**k):return Answer(quote='source'),{}
    async def forbidden(*a,**k):raise AssertionError('Successful primary triggered fallback')
    monkeypatch.setattr(local,'available',ready);monkeypatch.setattr(inv,'_generate_gemini',primary);monkeypatch.setattr(local,'generate',forbidden)
    assert asyncio.run(inv.generate('s',{},Answer))[1]['provider']=='Gemini'

def test_offline_worker_is_not_reported_as_a_successful_fallback(monkeypatch):
    async def offline():return False
    async def primary(*a,**k):assert k['attempts']==3;raise inv.ModelError('Gemini returned HTTP 503; temporary')
    async def forbidden(*a,**k):raise AssertionError('Offline fallback invoked')
    monkeypatch.setattr(local,'available',offline);monkeypatch.setattr(inv,'_generate_gemini',primary);monkeypatch.setattr(local,'generate',forbidden)
    with pytest.raises(inv.ModelError):asyncio.run(inv.generate('s',{},Answer))

def test_invalid_local_json_is_rejected_and_not_cached_as_accepted_analysis(monkeypatch):
    operations=[]
    async def rpc(op,args):
        operations.append(op)
        if op=='local_model:enqueue':return {'available':True,'id':'id','state':'completed','result':{'content':'{"wrong":1}','done_reason':'stop'}}
        return {'ok':True}
    monkeypatch.setattr(local.repo,'rpc',rpc)
    with pytest.raises(local.LocalModelError):asyncio.run(local.generate('s',{},Answer))
    assert operations==['local_model:enqueue','local_model:reject']

spec=importlib.util.spec_from_file_location('ollama_worker_test',Path(__file__).resolve().parents[2]/'scripts'/'ollama_worker.py')
worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
class Tokenizer:
    def encode(self,text,**kw):return SimpleNamespace(ids=list(text))

def test_context_overflow_refuses_inference_without_dropping_text():
    messages=[{'role':'user','content':'whole source text'}]
    with pytest.raises(worker.WorkerError) as e:worker.budget(messages,Tokenizer(),515,20)
    assert e.value.code=='context_limit' and messages[0]['content']=='whole source text'

def test_worker_rejects_a_changed_request_before_contacting_ollama():
    job={'request_text':'{}','request_digest':'0'*64}
    with pytest.raises(worker.WorkerError) as e:asyncio.run(worker.infer(job,{},Tokenizer(),None))
    assert e.value.code=='invalid_response'

def test_tool_calls_and_truncated_outputs_never_become_accepted_answers():
    config={'model':'test-local','model_digest':'a'*64,'context_tokens':16384}
    request={'system':'original','payload':{'record':'source'},'schema':Answer.model_json_schema(),'max_output_tokens':100}
    text=json.dumps(request);job={'request_text':text,'request_digest':worker.digest(text),**config}
    for reason,tools in [('length',[]),('stop',[{'function':{'name':'refund'}}])]:
        data={'done':True,'done_reason':reason,'model':'test-local','message':{'content':'{"quote":"source"}','tool_calls':tools},'prompt_eval_count':1000,'eval_count':10}
        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=data))) as c:
                await worker.infer(job,config,Tokenizer(),c)
        with pytest.raises(worker.WorkerError):asyncio.run(run())

def test_local_fallback_does_not_expand_financial_authority():
    from test_autonomous_resolution import example
    from autonomous_resolution import decision
    case,policy,detail,records=example();case['analysis']['generation_providers']=[{'provider':'Ollama','model':'test-local'}]
    assert decision(case,policy,detail,records,'MERCHANT',[])['reason']=='local_model_financial_execution_not_enabled'

def test_worker_sends_the_complete_context_and_checks_the_loaded_model():
    config={'model':'test-local','model_digest':'a'*64,'context_tokens':16384}
    payload={'sources':[{'text':'FIRST source'},{'text':'LAST source Ω'}]}
    request={'system':'original','payload':payload,'schema':Answer.model_json_schema(),'max_output_tokens':100}
    text=json.dumps(request);job={'request_text':text,'request_digest':worker.digest(text),**config};seen=[]
    def handle(r):
        if r.url.path=='/api/tags':return httpx.Response(200,json={'models':[{'name':'test-local','digest':'a'*64}]})
        body=json.loads(r.content);seen.append(body)
        return httpx.Response(200,json={'done':True,'done_reason':'stop','model':'test-local',
            'message':{'content':'{"quote":"FIRST source"}'},'prompt_eval_count':1000,'eval_count':10})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as c:return await worker.infer(job,config,Tokenizer(),c)
    result=asyncio.run(run())
    assert json.loads(seen[0]['messages'][1]['content'])==payload and seen[0]['format']==request['schema']
    assert result['model_digest']==config['model_digest'] and result['done_reason']=='stop'
