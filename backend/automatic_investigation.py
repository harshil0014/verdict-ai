"""Durable evidence-triggered work, bounded public references and real reanalysis.

One runner per process; PostgreSQL leases coordinate all instances. No browser,
financial writes, messages, document instructions or recursive crawling.
"""
import asyncio
from contextlib import suppress
import logging
import re
from urllib.parse import parse_qsl, urlsplit
from fastapi import HTTPException
from public_web import normalize_url, RetrievalError
from saas_store import repo, SESSION
from research_routes import URLInput, budget, stage_url, collect_draft
from case_investigation import run_investigation
from investigator import investigation_payload
from store import digest
from free_search import discover

log = logging.getLogger(__name__)
WAKE = asyncio.Event()
MAX_REFERENCES = 3
TRANSIENT_FAILURES={'dns_failed','network_failed','timeout','http_408','http_500','http_502','http_503','http_504'}
URL_PATTERN = re.compile(r'https?://[^\s<>"\x00-\x20]+', re.I)


async def backoff(seconds):
    await asyncio.sleep(seconds)


def public_fallback_query(url):
    """Only hostname and allowlisted public topic words leave for search.

    Never transmit original case text, customer IDs, arbitrary path segments,
    tracking values or a model-authored query during automatic discovery.
    """
    p=urlsplit(url)
    words=re.findall(r'[a-z]+',p.path.lower())
    allowed=[w for w in ('bereavement','policy','policies','refund','fares','terms','conditions','regulation') if w in words]
    return 'site:'+p.hostname+' '+' '.join(allowed)+' official public document' if allowed else None


def references(evidence):
    """Only literal references in supplied originals, never model-invented URLs.

    Do not follow links from automatically obtained pages. PDF annotations are
    extracted offline with their page number; no JavaScript/action is executed.
    """
    found = {}
    for source in evidence:
        if source.get('origin') in ('public_web_automatic', 'public_web_snapshot'):
            continue
        text = source.get('text', '')
        candidates = [(m.group().rstrip('.,;:!?)]}'), text[max(0,m.start()-100):m.end()+100], None)
                      for m in URL_PATTERN.finditer(text)]
        candidates += [(row['url'], 'Embedded PDF reference', row.get('page'))
                       for row in source.get('embedded_links', []) if isinstance(row,dict) and isinstance(row.get('url'),str)]
        for value, context, page in candidates:
            try:
                url = normalize_url(value)
                parsed = urlsplit(url)
                # An ordinary public reference is not a credential-bearing,
                # customer-specific or tracking link. Unknown query keys need
                # explicit manual retrieval rather than automatic transmission.
                if any(k.lower() not in ('id','article','document','lang','language','page') for k,v in parse_qsl(parsed.query)):
                    raise RetrievalError('sensitive_reference', 'The link has query parameters requiring review; it was not opened automatically.')
                failure = None
            except RetrievalError as error:
                # Do not copy credential values into progress/audit messages.
                url = 'blocked-reference-'+str(len(found)+1)
                failure = error.message
            if url in found:
                continue
            rank = 0 if re.search(r'policy|policies|terms|bereavement|decision|tribunal|regulation|statreg',context,re.I) else 1
            found[url] = {'url':url,'parent_source_id':source['id'],'page':page,
                'context':context[:350] if not failure else 'Unsafe or sensitive reference withheld',
                'rank':rank,'failure':failure}
            if len(found)>=24:
                break
    return sorted(found.values(),key=lambda r:r['rank'])[:24]


def safe_failure(error):
    if isinstance(error, HTTPException):
        if error.status_code in (409,429,413,503,422):
            return str(error.detail)[:500]
    # Provider/model exception strings are not logged or returned with secrets.
    return 'Automatic investigation could not finish. Original evidence and prior analysis are retained; retry when ready.'


async def process(claim):
    case_id=claim['case_id']
    credentials={'case_id':case_id,'lease_token':claim['lease_token']}
    progress=claim.get('progress') or {}
    outcomes=progress.setdefault('references',{})
    stage='finding_references'
    analysis_job=None
    session_token=SESSION.set(claim['session_hash'])

    async def heartbeat(**extra):
        return await repo.rpc('workflow:heartbeat',{**credentials,'stage':stage,'progress':progress,**extra},session='')

    async def renew():
        while True:
            await asyncio.sleep(25)
            await heartbeat()

    renewal=asyncio.create_task(renew())
    try:
        async with asyncio.timeout(420):
            body=await repo.get(case_id)
            pending=[ref for ref in references(body['evidence']) if ref['url'] not in outcomes or outcomes[ref['url']].get('status')=='retrieving'][:MAX_REFERENCES]
            for ref in pending:
                key=ref['url']
                if key in outcomes and outcomes[key].get('status')!='retrieving':
                    continue
                parent={k:ref[k] for k in ('parent_source_id','page','context')}
                if ref['failure']:
                    outcomes[key]={'status':'blocked','detail':ref['failure'],**parent}
                    await heartbeat()
                    continue
                stage='retrieving_references'
                await heartbeat()
                existing=next((e for e in body['evidence'] if e.get('provenance',{}).get('requested_url')==key),None)
                if existing:
                    outcomes[key]={'status':'already_preserved','source_id':existing['id'],**parent}
                    await heartbeat()
                    continue
                try:
                    attempted=outcomes.get(key,{}).get('attempts',0)
                    draft=None
                    for attempt in range(attempted,3):
                        outcomes[key]={'status':'retrieving','attempts':attempt+1,**parent}
                        await heartbeat()
                        await budget({'id':claim['owner_id']},'url')
                        draft=await stage_url(case_id,URLInput(url=key,consent=True,
                            relevance='Referenced in supplied evidence; relevance and factual truth remain subject to investigation.'))
                        if draft.get('failure_code') not in TRANSIENT_FAILURES or attempt==2:
                            break
                        await backoff(2*(attempt+1))
                    if draft is None:
                        outcomes[key]={'status':'unavailable','detail':'Interrupted retrieval exhausted its bounded attempts; no source content was invented.',**parent}
                        continue
                    # Save checkpoint before adoption. Recovered work reuses
                    # the staged snapshot, not a newer page masquerading as it.
                    outcomes[key]={'status':draft['status'],'draft_id':draft['id'],**parent}
                    await heartbeat()
                    if draft['status']=='ready':
                        await collect_draft(case_id,draft['id'],acquisition='embedded_reference',parent=parent)
                        body=await repo.get(case_id)
                        src=next(e for e in body['evidence'] if e.get('provenance',{}).get('final_url')==draft['metadata']['final_url'] and e['sha256']==draft['raw_sha256'])
                        outcomes[key].update(status='preserved',source_id=src['id'],retrieved_at=draft['metadata']['retrieved_at'])
                    else:
                        outcomes[key]['detail']=draft.get('failure_message','The source could not be retrieved; no content was invented.')
                        query=public_fallback_query(key)
                        if query and not progress.get('discovery'):
                            await budget({'id':claim['owner_id']},'search')
                            # Record the intention before dispatch, so a crash
                            # cannot silently replay a provider search.
                            progress['discovery']={'query':query,'status':'started'}
                            await heartbeat()
                            result=await discover(query,case_id)
                            progress['discovery']={'query':query,'status':result['status'],'providers':result['provider_attempts']}
                            for doc in result.get('documents',[]):
                                if len(pending)>=MAX_REFERENCES: break
                                if doc['url'] not in outcomes and not any(x['url']==doc['url'] for x in pending):
                                    pending.append({'url':doc['url'],'parent_source_id':ref['parent_source_id'],'page':ref['page'],
                                        'context':'Public API search lead following an unavailable reference: '+query,'failure':None,'rank':1})
                except HTTPException as error:
                    if error.status_code==409 and 'case changed' in str(error.detail).lower():
                        raise
                    if outcomes.get(key,{}).get('status')=='ready':
                        raise
                    outcomes[key]={'status':'unavailable','detail':safe_failure(error),**parent}
                await heartbeat()
            # Recover a ready snapshot left between staging and atomic adoption.
            for url,row in outcomes.items():
                if row['status']=='ready':
                    await heartbeat()
                    await collect_draft(case_id,row['draft_id'],acquisition='embedded_reference',parent={k:row.get(k) for k in ('parent_source_id','page','context')})
                    row['status']='preserved'
            stage='investigating'
            await heartbeat()

            async def reserved(job_id):
                nonlocal analysis_job
                analysis_job=job_id
                await heartbeat(analysis_job_id=job_id)

            current=await repo.get(case_id)
            # A restart after the atomic result commit must not spend another
            # model attempt just because the final status update was lost.
            if not current.get('analysis') or current.get('analysis_stale') or current['analysis'].get('input_digest')!=digest(investigation_payload(current)):
                await run_investigation(case_id,on_reserved=reserved,before_commit=heartbeat)
            partial=any(r['status'] in ('unavailable','blocked') for r in outcomes.values())
            await repo.rpc('workflow:finish',{**credentials,'generation':claim['generation'],
                'state':'partial' if partial else 'completed','stage':'complete',
                'detail':'Investigation updated. Some references were unavailable or blocked; inspect the source record.' if partial else 'Investigation updated from preserved evidence. Review conclusions and source passages.'},session='')
    except asyncio.CancelledError:
        with suppress(Exception):
            await asyncio.shield(repo.rpc('workflow:release',credentials,session=''))
        raise
    except Exception as error:
        with suppress(Exception):
            if isinstance(error,HTTPException) and error.status_code==503 and str(error.detail).startswith('Cloud database connection'):
                # The next claimed run reads committed state first. Do not
                # blindly replay an ambiguous storage write or invent success.
                await repo.rpc('workflow:release',credentials,session='')
                await backoff(3)
            else:
                await repo.rpc('workflow:finish',{**credentials,'generation':claim['generation'],
                    'state':'failed','stage':'needs_attention','detail':safe_failure(error)},session='')
        log.warning('Automatic investigation did not complete (%s); saved records retained',type(error).__name__)
    finally:
        renewal.cancel()
        with suppress(asyncio.CancelledError,Exception):
            await renewal
        SESSION.reset(session_token)


async def worker():
    while True:
        try:
            WAKE.clear()
            claim=await repo.rpc('workflow:claim',session='')
            if claim:
                await process(claim)
                continue
        except asyncio.CancelledError:
            raise
        except Exception as error:
            log.warning('Automatic investigation queue unavailable (%s)',type(error).__name__)
        with suppress(TimeoutError):
            await asyncio.wait_for(WAKE.wait(),10)
