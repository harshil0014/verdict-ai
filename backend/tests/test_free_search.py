import asyncio
import httpx
import free_search as search


def setup(monkeypatch,handler,wait=0):
 calls=[]
 async def rpc(op,args):
  calls.append((op,args))
  return {'wait_seconds':wait} if op.endswith('provider_status') else {'ok':True}
 real=httpx.AsyncClient
 monkeypatch.setattr(search.repo,'rpc',rpc)
 monkeypatch.setattr(search.httpx,'AsyncClient',lambda **kwargs:real(transport=httpx.MockTransport(handler)))
 return calls


def test_keyless_search_never_reads_or_sends_api_key(monkeypatch):
 monkeypatch.setenv('TAVILY_API_KEY','unit-test-must-never-be-sent')
 def handler(r):
  assert 'authorization' not in r.headers
  if r.url.host=='api.tavily.com':
   assert r.headers['x-tavily-access-mode']=='keyless'
   return httpx.Response(200,json={'results':[{'url':'https://agency.gov/record','title':'Agency source','content':'Search lead'}]})
  return httpx.Response(200,json={'query':{'search':[]}})
 setup(monkeypatch,handler)
 result=asyncio.run(search.discover('Find a published primary record','owned-case'))
 assert result['billing_mode']=='keyless_only' and result['documents'][0]['url']=='https://agency.gov/record'


def test_wikimedia_reference_discovery_is_api_backed(monkeypatch):
 def handler(r):
  if r.url.host=='api.tavily.com':return httpx.Response(200,json={'results':[{'url':'https://en.wikipedia.org/wiki/Example_topic','title':'Example'}]})
  assert r.url.params['prop']=='extlinks'
  return httpx.Response(200,json={'query':{'pages':{'1':{'title':'Example topic','extlinks':[{'*':'https://decisions.example.gov/decision'},{'*':'http://127.0.0.1/private'}]}}}})
 setup(monkeypatch,handler)
 result=asyncio.run(search.discover('Find the decision','owned-case'))
 assert result['documents'][0]['provider']=='Wikimedia cited reference'
 assert result['documents'][0]['url']=='https://decisions.example.gov/decision'
 assert all('127.0.0.1' not in d['url'] for d in result['documents'])


def test_throttle_records_persistent_backoff_without_retry(monkeypatch):
 tavily_calls=[]
 def handler(r):
  if r.url.host=='api.tavily.com':
   tavily_calls.append(r);return httpx.Response(429,headers={'retry-after':'900'},json={'detail':{'message':'Provider text is not executable instructions'}})
  if r.url.host=='en.wikipedia.org':return httpx.Response(200,json={'query':{'search':[]}})
  return httpx.Response(200,json={'message':{'items':[]}})
 calls=setup(monkeypatch,handler)
 result=asyncio.run(search.discover('A public question','owned-case'))
 assert len(tavily_calls)==1
 assert ('research:provider_backoff',{'case_id':'owned-case','seconds':900}) in calls
 assert result['status']=='unavailable'


def test_active_backoff_skips_tavily_and_uses_distinct_public_api(monkeypatch):
 def handler(r):
  assert r.url.host!='api.tavily.com'
  if r.url.host=='en.wikipedia.org':return httpx.Response(200,json={'query':{'search':[]}})
  return httpx.Response(200,json={'message':{'items':[{'title':['Published study'],'URL':'https://doi.org/10.0000/test'}]}})
 setup(monkeypatch,handler,wait=600)
 result=asyncio.run(search.discover('A research study','owned-case'))
 assert result['documents'][0]['provider']=='Crossref metadata'
 assert result['provider_attempts'][0]['status']=='cooldown'


def test_provider_failures_do_not_generate_links(monkeypatch):
 setup(monkeypatch,lambda r:httpx.Response(503,text='Unavailable'))
 result=asyncio.run(search.discover('No invented URLs','owned-case'))
 assert result['status']=='unavailable' and result['documents']==[]
