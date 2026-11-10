"""Durable evidence-triggered work, bounded public references and real reanalysis.

One runner per process; PostgreSQL leases coordinate all instances. No browser,
financial writes, messages, document instructions or recursive crawling.
"""
import asyncio
from contextlib import suppress
import logging
import random
import re
from urllib.parse import urlsplit
from fastapi import HTTPException
from public_web import normalize_url, RetrievalError
from saas_store import repo, SESSION
from research_routes import URLInput, budget, stage_url, collect_draft
from case_investigation import run_investigation
from delivery_location import verify_case as verify_delivery_locations
from investigator import investigation_payload,ModelError,model_failure_info
from store import digest,now
from free_search import discover
from source_recovery import automatic_url,decision_identity,recovery_query,publisher_candidates,check_decision,publisher_embed,RECOVERY_VERSION

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
        if source.get('extraction'):
            # Model-authored image transcriptions never become invented URL
            # discovery leads. Only the offline reader's literal text is used.
            text='\n'.join(p.get('offline_text',p.get('text','')) for p in source['extraction'].get('pages',[]))
        candidates = [(m.group().rstrip('.,;:!?)]}'), text[max(0,m.start()-100):m.end()+100], None)
                      for m in URL_PATTERN.finditer(text)]
        candidates += [(row['url'], 'Embedded PDF reference', row.get('page'))
                       for row in source.get('embedded_links', []) if isinstance(row,dict) and isinstance(row.get('url'),str)]
        for value, context, page in candidates:
            try:
                url = automatic_url(value)
                # An ordinary public reference is not a credential-bearing,
                # customer-specific or tracking link. Unknown query keys need
                # explicit manual retrieval rather than automatic transmission.
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
    if isinstance(error,ModelError):
        status=re.match(r'Gemini returned HTTP (\d{3});',str(error))
        if status:
            return 'Gemini returned HTTP '+status[1]+'. Retrieved sources and any prior investigation are retained; no substitute analysis was generated.'
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

    async def recover_reference(blocked_url,row):
        nonlocal stage
        identity=decision_identity(blocked_url)
        if not identity or row.get('failure_code')=='http_429' or 'HTTP 429' in row.get('detail',''):
            return
        recoveries=progress.setdefault('recoveries',{})
        record=recoveries.get(blocked_url)
        # Upgrade the initial wrapper-only attempt without searching again or
        # losing its failure. Resume from the saved publisher snapshot once.
        if record and record.get('status')=='unavailable' and record.get('version',0)<RECOVERY_VERSION:
            wrappers=[c for c in record.get('candidates',[]) if c.get('draft_id') and c.get('identity_check',{}).get('reason')=='The preserved header has no explicit indexed case name and neutral citation.']
            if wrappers:
                import copy
                history=record.setdefault('previous_attempts',[])
                history.append(copy.deepcopy({k:v for k,v in record.items() if k!='previous_attempts'}))
                for c in wrappers:c['status']='retrieved'
                record.update(version=RECOVERY_VERSION,status='checking_publisher',detail='Resuming the retained publisher wrapper with bounded document extraction.')
                await heartbeat()
        if record and record.get('status') in ('recovered','unavailable','interrupted','no_publisher_candidates'):
            return
        if not record and len(recoveries)>=1:
            return
        stage='recovering_sources'
        if not record:
            record={'version':RECOVERY_VERSION,'citation':identity['citation'],'query':recovery_query(identity),
                'status':'searching','started_at':now(),'candidates':[]}
            recoveries[blocked_url]=record
            await heartbeat()
            await budget({'id':claim['owner_id']},'search')
            discovery=await discover(record['query'],case_id)
            record.update(status='checking_publisher',providers=discovery.get('provider_attempts',[]),
                candidates=publisher_candidates(discovery.get('documents',[]),identity,blocked_url))
            await heartbeat()
        elif record['status']=='searching':
            record.update(status='interrupted',detail='Discovery was interrupted before results were saved; the provider request was not blindly replayed.')
            await heartbeat();return
        if not record['candidates']:
            record.update(status='no_publisher_candidates',detail='No original-publisher candidate was returned by the public discovery APIs. No document URL was invented.')
            await heartbeat();return
        for candidate in record['candidates']:
            if candidate.get('status') in ('rejected','unavailable','wrapper'):
                continue
            if candidate.get('draft_id'):
                draft=await repo.rpc('research:get',{'case_id':case_id,'id':candidate['draft_id']})
            elif candidate.get('status')=='retrieving':
                candidate.update(status='unavailable',detail='Interrupted candidate retrieval was not silently repeated.');continue
            else:
                candidate['status']='retrieving'
                await heartbeat()
                await budget({'id':claim['owner_id']},'url')
                draft=await stage_url(case_id,URLInput(url=candidate['url'],consent=True,
                    relevance='Original-publisher candidate for '+identity['citation']+' after the linked source was unavailable.'),recovery_identity=identity)
                candidate.update(draft_id=draft['id'],status='retrieved')
                await heartbeat()
            candidate['identity_check']=check_decision(draft,identity)
            if candidate['identity_check'].get('status')!='matched':
                embed=publisher_embed(draft,identity)
                if embed and len(record['candidates'])<3 and not any(c.get('publisher_wrapper') for c in record['candidates']) and not any(c['url']==embed['url'] for c in record['candidates']):
                    candidate.update(status='wrapper',detail='Publisher wrapper preserved; checking its explicit same-document iframe.')
                    record['candidates'].append(embed)
                    await heartbeat();continue
                candidate.update(status='rejected' if draft['status']=='ready' else 'unavailable',
                    detail=candidate['identity_check'].get('reason',draft.get('failure_message','No verifiable source content was retrieved.')))
                await heartbeat();continue
            parent={k:row.get(k) for k in ('parent_source_id','page','context')}
            recovery={'blocked_url':blocked_url,'original_failure':row.get('detail'),'expected_citation':identity['citation'],
                'discovery_query':record['query'],'discovered_via':candidate.get('provider'),'recovered_at':now()}
            if candidate.get('publisher_wrapper'):recovery['publisher_wrapper']=candidate['publisher_wrapper']
            await heartbeat()
            await collect_draft(case_id,draft['id'],acquisition='embedded_reference',parent=parent,recovery=recovery)
            current=await repo.get(case_id)
            src=next(e for e in current['evidence'] if e.get('sha256')==draft['raw_sha256'] and e.get('provenance',{}).get('final_url')==draft['metadata']['final_url'])
            candidate.update(status='preserved',source_id=src['id'])
            record.update(status='recovered',source_id=src['id'],recovered_url=draft['metadata']['final_url'],
                identity_check=candidate['identity_check'])
            row['recovery']={'status':'recovered','url':record['recovered_url'],'citation':identity['citation'],'source_id':src['id']}
            outcomes[candidate['url']]={'status':'preserved','source_id':src['id'],'retrieved_at':draft['metadata']['retrieved_at'],
                'recovered_from':blocked_url,**parent}
            await heartbeat();return
        record.update(status='unavailable',detail='No retrieved original-publisher candidate passed the exact document-identity check. Original evidence and failed attempts are retained.')
        await heartbeat()

    renewal=asyncio.create_task(renew())
    try:
        async with asyncio.timeout(900):
            body=await repo.get(case_id)
            stage='checking_evidence'
            await heartbeat()
            from document_reading import extract_pending
            await extract_pending(case_id,heartbeat)
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
                    outcomes[key]={'status':draft['status'],'draft_id':draft['id'],'failure_code':draft.get('failure_code'),**parent}
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
            # Older failed references are also eligible on a newly queued run;
            # preserve the original failure while checking another publisher.
            for url,row in list(outcomes.items()):
                if row.get('status')=='unavailable':
                    try:
                        await recover_reference(url,row)
                    except HTTPException as error:
                        if error.status_code in (409,503):raise
                        record=progress.setdefault('recoveries',{}).get(url)
                        if record:record.update(status='unavailable',detail=safe_failure(error))
            progress['recovery_version']=RECOVERY_VERSION
            await heartbeat()
            # Recover a ready snapshot left between staging and atomic adoption.
            for url,row in outcomes.items():
                if row['status']=='ready':
                    await heartbeat()
                    await collect_draft(case_id,row['draft_id'],acquisition='embedded_reference',parent={k:row.get(k) for k in ('parent_source_id','page','context')})
                    row['status']='preserved'
            stage='verifying_delivery_locations'
            await heartbeat()
            location_record=await verify_delivery_locations(case_id)
            if location_record:progress['delivery_location_status']=location_record['status']
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
            if location_record and location_record.get('retry_at'):
                await repo.rpc('workflow:reschedule',{**credentials,'delay_seconds':320,'progress':progress},session='')
                return
            stage='checking_resolution'
            await heartbeat()
            from autonomous_resolution import evaluate_case
            try:
                await evaluate_case(case_id)
            except Exception as error:
                # Optional provider resolution must not undo a committed
                # investigation. A durable dispatch barrier, if present,
                # remains intact and the policy scheduler reconciles reads.
                progress['resolution_check_unavailable']=True
                log.warning('Sandbox resolution check unavailable (%s)',type(error).__name__)
            partial=any(r['status'] in ('unavailable','blocked') and r.get('recovery',{}).get('status')!='recovered' for r in outcomes.values())
            await repo.rpc('workflow:finish',{**credentials,'generation':claim['generation'],
                'state':'partial' if partial else 'completed','stage':'complete',
                'detail':'Investigation updated. Some references were unavailable or blocked; inspect the source record.' if partial else 'Investigation updated from preserved evidence. Review conclusions and source passages.'},session='')
    except asyncio.CancelledError:
        with suppress(Exception):
            await asyncio.shield(repo.rpc('workflow:release',credentials,session=''))
        raise
    except Exception as error:
        with suppress(Exception):
            failure=model_failure_info(error)
            if failure:progress['last_failure']={**failure,'observed_at':now()}
            temporary=isinstance(error,ModelError) and (bool(re.search(r'HTTP (429|500|502|503|504)',str(error))) or 'network request failed' in str(error))
            temporary=temporary or (isinstance(error,HTTPException) and error.status_code in (429,503))
            if temporary:
                base=300 if '429' in str(error) else 45
                delay=min(3600,base*(2**min(4,max(0,claim.get('attempts',1)-1)))+random.randint(5,25))
                delay=int(max(delay,min(86400,getattr(error,'retry_after',0) or 0)))+1
                await repo.rpc('workflow:reschedule',{**credentials,'delay_seconds':delay,'progress':progress},session='')
            else:
                if failure:await heartbeat()
                await repo.rpc('workflow:finish',{**credentials,'generation':claim['generation'],
                    'state':'failed','stage':'needs_attention','detail':safe_failure(error)},session='')
        failure=model_failure_info(error)
        log.warning('Automatic investigation did not complete (%s, %s, HTTP %s); saved records retained',
            type(error).__name__,failure['code'] if failure else 'non_model_error',failure['http_status'] if failure else None)
    finally:
        renewal.cancel()
        with suppress(asyncio.CancelledError,Exception):
            await renewal
        SESSION.reset(session_token)


async def worker():
    while True:
        try:
            WAKE.clear()
            from autonomous_resolution import tick
            try:
                async with asyncio.timeout(90):
                    await tick()
            except TimeoutError:
                log.warning('Sandbox polling timed out; durable dispatch barriers retained')
            await repo.rpc('workflow:queue_location_experience_upgrade',session='')
            await repo.rpc('workflow:queue_recovery',session='')
            await repo.rpc('workflow:queue_location_upgrade',session='')
            await repo.rpc('workflow:queue_location_comparison_upgrade',session='')
            claim=await repo.rpc('workflow:claim',{'worker_version':max(10,RECOVERY_VERSION)},session='')
            if claim:
                await process(claim)
                continue
        except asyncio.CancelledError:
            raise
        except Exception as error:
            log.warning('Automatic investigation queue unavailable (%s)',type(error).__name__)
        with suppress(TimeoutError):
            await asyncio.wait_for(WAKE.wait(),10)
