"""Documented no-key APIs only. No SERP scraping, billing keys or cap evasion."""
from datetime import datetime,timezone
from urllib.parse import urlsplit,unquote
import re
import httpx
from public_web import normalize_url,RetrievalError
from saas_store import repo

AGENT='VERDICT/1.0 (https://github.com/harshil0014/verdict-ai; bounded public evidence discovery)'


def candidate(url,title,provider,relevance,parent=None):
    try:url=normalize_url(url)
    except (RetrievalError,TypeError):return None
    return {'url':url,'title':str(title or urlsplit(url).hostname)[:200],'provider':provider,
            'relevance':relevance[:700],'publication_date':None,'content_retrieved':False,'discovered_via':parent}


def primary_rank(doc):
    host=urlsplit(doc['url']).hostname or ''
    return 0 if host.endswith(('.gov','.gov.bc.ca','.gc.ca')) or host.startswith(('decisions.','judgments.','laws.')) else 1 if host.endswith('.edu') else 2 if 'wikipedia.org' not in host else 3


async def discover(query,case_id):
    docs=[]; attempts=[];wiki_titles=[]
    async with httpx.AsyncClient(timeout=20,follow_redirects=False,trust_env=False,headers={'User-Agent':AGENT}) as client:
        cooldown=await repo.rpc('research:provider_status',{'case_id':case_id})
        wait=float(cooldown.get('wait_seconds',0))
        if wait>0:
            attempts.append({'provider':'Tavily keyless','status':'cooldown','retry_after_seconds':round(wait)})
        else:
            try:
                # Explicitly select free keyless mode. Never consult API-key
                # environment variables or add an Authorization header.
                r=await client.post('https://api.tavily.com/search',headers={'X-Tavily-Access-Mode':'keyless'},json={
                    'query':query,'search_depth':'basic','max_results':5,'include_answer':False,
                    'include_raw_content':False,'include_images':False,'auto_parameters':False})
                if r.status_code==429:
                    data=r.json();detail=data.get('detail',data);detail=detail if isinstance(detail,dict) else {}
                    supplied=r.headers.get('retry-after') or detail.get('retry_after_seconds') or 600
                    try:delay=max(1,min(int(float(supplied)),604800))
                    except (TypeError,ValueError):delay=600
                    await repo.rpc('research:provider_backoff',{'case_id':case_id,'seconds':delay})
                    attempts.append({'provider':'Tavily keyless','status':'rate_limited','http':429,'retry_after_seconds':delay})
                elif r.status_code==200:
                    data=r.json()
                    for item in data.get('results',[])[:5]:
                        d=candidate(item.get('url',''),item.get('title'),'Tavily keyless','Search lead, not evidence: '+str(item.get('content',''))[:500])
                        if d:docs.append(d)
                    attempts.append({'provider':'Tavily keyless','status':'completed','results':len(docs)})
                else:attempts.append({'provider':'Tavily keyless','status':'unavailable','http':r.status_code})
            except (httpx.HTTPError,ValueError):attempts.append({'provider':'Tavily keyless','status':'unavailable'})
        for d in docs:
            p=urlsplit(d['url'])
            if p.hostname=='en.wikipedia.org' and p.path.startswith('/wiki/'):
                wiki_titles.append(unquote(p.path[len('/wiki/'):]).replace('_',' '))
        # Wikimedia provides an official full-text topic search and external
        # reference API. Article prose is not copied or treated as primary.
        if not wiki_titles:
            try:
                r=await client.get('https://en.wikipedia.org/w/api.php',params={'action':'query','list':'search','srsearch':query,'srlimit':2,'srprop':'','format':'json','maxlag':5})
                if r.status_code==200:
                    wiki_titles=[x['title'] for x in r.json().get('query',{}).get('search',[])[:2]]
                attempts.append({'provider':'Wikimedia topic search','http':r.status_code,'status':'completed' if wiki_titles else 'no_results'})
            except (httpx.HTTPError,ValueError):attempts.append({'provider':'Wikimedia topic search','status':'unavailable'})
        if wiki_titles:
            try:
                r=await client.get('https://en.wikipedia.org/w/api.php',params={'action':'query','prop':'extlinks','titles':'|'.join(wiki_titles[:2]),'ellimit':40,'format':'json','maxlag':5})
                if r.status_code==200:
                    for page in r.json().get('query',{}).get('pages',{}).values():
                        parent=page.get('title','Wikipedia topic')
                        for ref in page.get('extlinks',[])[:40]:
                            d=candidate(ref.get('*',ref.get('url','')),None,'Wikimedia cited reference',f'External reference listed on {parent}; linked document and primary-source status require review.',parent)
                            if d:docs.append(d)
                attempts.append({'provider':'Wikimedia cited references','status':'completed' if r.status_code==200 else 'unavailable','http':r.status_code})
            except (httpx.HTTPError,ValueError):attempts.append({'provider':'Wikimedia cited references','status':'unavailable'})
        if not docs:
            try:
                r=await client.get('https://api.crossref.org/works',params={'query.bibliographic':query,'rows':3,'select':'title,URL,link,DOI'})
                if r.status_code==200:
                    for item in r.json().get('message',{}).get('items',[])[:3]:
                        for url in [x.get('URL') for x in item.get('link',[])[:1]]+[item.get('URL')]:
                            d=candidate(url,(item.get('title') or ['Research document'])[0],'Crossref metadata','Bibliographic match; not proof of relevance, access or document content.')
                            if d:docs.append(d)
                attempts.append({'provider':'Crossref public metadata','status':'completed' if r.status_code==200 else 'unavailable','http':r.status_code})
            except (httpx.HTTPError,ValueError):attempts.append({'provider':'Crossref public metadata','status':'unavailable'})
    unique={}
    for d in docs:unique.setdefault(d['url'],d)
    ranked=sorted(unique.values(),key=primary_rank)[:8]
    return {'status':'completed' if ranked else 'unavailable','provider':'Free public discovery: Tavily keyless / Wikimedia / Crossref',
            'summary':'Primary-domain candidates are prioritized heuristically, not authenticated. Independently retrieved source snapshots appear below for human review.' if ranked else 'No accessible search results were returned. Provider limits and failures are recorded; no result was invented. Try a public URL or return after the indicated delay.',
            'query':query,'discovered_at':datetime.now(timezone.utc).isoformat(),'documents':ranked,'provider_attempts':attempts,
            'billing_mode':'keyless_only','notice':'Search snippets, bibliographic records and encyclopedia references are discovery leads, never official evidence. No paid API or automatic upgrade is used.'}
