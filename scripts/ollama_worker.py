"""Outbound-only private model worker. Never executes model/tool instructions."""
import argparse,asyncio,hashlib,json,logging,os,sys,time
from pathlib import Path
import httpx

log=logging.getLogger('verdict.local_model')

class WorkerError(Exception):
    def __init__(self,code):self.code=code;super().__init__(code)

def digest(value):return hashlib.sha256(value.encode()).hexdigest()

def messages_for(request):
    system=request['system']+'\nReturn only valid JSON satisfying this schema:\n'+json.dumps(request['schema'],ensure_ascii=False,separators=(',',':'))
    return [{'role':'system','content':system},
        {'role':'user','content':json.dumps(request['payload'],ensure_ascii=False,sort_keys=True,separators=(',',':'))}]

def budget(messages,tokenizer,context,output):
    count=sum(len(tokenizer.encode(m['content'],add_special_tokens=False).ids) for m in messages)
    if count+output+512>context:raise WorkerError('context_limit')
    return count

async def infer(job,config,tokenizer,client):
    if digest(job['request_text'])!=job['request_digest']:raise WorkerError('invalid_response')
    if job['model']!=config['model'] or job['model_digest']!=config['model_digest']:raise WorkerError('model_changed')
    request=json.loads(job['request_text']);messages=messages_for(request)
    context=min(job['context_tokens'],config['context_tokens'])
    output=min(6000,request['max_output_tokens'])
    minimum=budget(messages,tokenizer,context,output)
    data={'model':config['model'],'stream':False,'messages':messages,'format':request['schema'],
        'options':{'num_ctx':context,'num_batch':64,'num_predict':output,'temperature':0.1},'keep_alive':'5m'}
    if config.get('supports_thinking'):data['think']=False
    try:
        r=await client.post('http://127.0.0.1:11434/api/chat',json=data,timeout=240)
        r.raise_for_status();result=r.json()
    except (httpx.HTTPError,ValueError):raise WorkerError('ollama_unavailable') from None
    if not result.get('done') or result.get('done_reason')!='stop':raise WorkerError('generation_limit')
    if result.get('model')!=config['model']:raise WorkerError('model_changed')
    content=result.get('message',{}).get('content','')
    if result.get('message',{}).get('tool_calls'):raise WorkerError('invalid_response')
    try:json.loads(content)
    except (ValueError,TypeError):raise WorkerError('invalid_response') from None
    # Detect unexpected prompt truncation/tokenizer mismatch as well as checking
    # capacity BEFORE inference. No abridged result is accepted as full context.
    prompt=result.get('prompt_eval_count',0);generated=result.get('eval_count',0)
    if prompt<minimum-64 or prompt+generated>context:raise WorkerError('context_limit')
    try:
        tags=await client.get('http://127.0.0.1:11434/api/tags',timeout=15);tags.raise_for_status()
        current=next((m for m in tags.json()['models'] if m['name']==config['model']),None)
    except (httpx.HTTPError,ValueError,KeyError):raise WorkerError('ollama_unavailable') from None
    if not current or current['digest']!=config['model_digest']:raise WorkerError('model_changed')
    return {'content':content,'model':config['model'],'model_digest':config['model_digest'],
        'done_reason':'stop','prompt_tokens':prompt,'output_tokens':generated,'context_tokens':context}

async def process(job,config,tokenizer,local,cloud):
    lease={k:job[k] for k in ('job_id','lease_token')}
    async def renew():
        while True:
            await asyncio.sleep(20)
            r=await cloud.post('/api/local-model/renew',json=lease);r.raise_for_status()
    inference=asyncio.create_task(infer(job,config,tokenizer,local));heartbeat=asyncio.create_task(renew())
    try:
        done,_=await asyncio.wait([inference,heartbeat],return_when=asyncio.FIRST_COMPLETED)
        if heartbeat in done:raise WorkerError('worker_interrupted')
        result=await inference
        r=await cloud.post('/api/local-model/complete',json={**lease,'request_digest':job['request_digest'],'result':result});r.raise_for_status()
        log.info('Completed validated local generation (%s prompt tokens, %s output tokens)',result['prompt_tokens'],result['output_tokens'])
    except WorkerError as error:
        r=await cloud.post('/api/local-model/fail',json={**lease,'error_code':error.code});r.raise_for_status()
        log.warning('Local generation refused (%s)',error.code)
    finally:
        for task in (inference,heartbeat):
            task.cancel()
            try:await task
            except (asyncio.CancelledError,Exception):pass

async def run(config):
    from tokenizers import Tokenizer
    path=Path(config['tokenizer_path']);raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=config['tokenizer_sha256']:raise ValueError('Tokenizer integrity check failed')
    tokenizer=Tokenizer.from_file(str(path))
    base=config['base_url'].rstrip('/')
    if not base.startswith('https://'):raise ValueError('A verified HTTPS application URL is required')
    async with httpx.AsyncClient(timeout=20,follow_redirects=False) as local, httpx.AsyncClient(base_url=base,
        timeout=45,follow_redirects=False,headers={'Authorization':'Bearer '+config['worker_token']}) as cloud:
        while True:
            try:
                tags=await local.get('http://127.0.0.1:11434/api/tags');tags.raise_for_status()
                model=next((m for m in tags.json()['models'] if m['name']==config['model']),None)
                if not model or model['digest']!=config['model_digest']:raise WorkerError('model_changed')
                r=await cloud.post('/api/local-model/claim',json={});r.raise_for_status();job=r.json()
                if job:await process(job,config,tokenizer,local,cloud)
            except (httpx.HTTPError,WorkerError,ValueError):
                # Do not log URLs with credentials, payloads, raw model output,
                # server bodies or exceptions that might contain case records.
                log.warning('Worker unavailable; preserving queued work and backing off')
                await asyncio.sleep(20)
            await asyncio.sleep(10)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);args=parser.parse_args()
    config_path=Path(args.config).resolve();config=json.loads(config_path.read_text(encoding='utf-8'))
    lock=open(config_path.with_suffix('.lock'),'a+b')
    if os.name=='nt':
        import msvcrt
        lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:return
    logging.basicConfig(filename=str(config_path.with_suffix('.log')),level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',encoding='utf-8')
    logging.getLogger('httpx').setLevel(logging.WARNING)
    log.info('Starting tenant-bound local model worker')
    asyncio.run(run(config))

if __name__=='__main__':main()
