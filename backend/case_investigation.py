"""Shared manual/automatic investigation, with one durable lease and stale checks."""
import asyncio
from saas_store import repo
from investigator import investigate, MODEL


async def run_investigation(case_id, on_reserved=None, before_commit=None):
    body = await repo.get(case_id)
    job = await repo.rpc('reserve_analysis', {'case_id': case_id})
    try:
        if on_reserved:
            await on_reserved(job['job_id'])
        result = await investigate(body)
        prior = body.get('analysis')
        if prior:
            result['change'] = {'previous_finding': prior['finding'], 'current_finding': result['finding'],
                'previous_claims': len(prior['claims']), 'current_claims': len(result['claims']),
                'new_source_ids': [e['id'] for e in body['evidence'] if e['id'] not in {c['source_id'] for c in prior['claims']}]}
        if before_commit:
            await before_commit()
        body.update(analysis=result, analysis_stale=False)
        return await repo.save(body, 'investigation_updated', {'finding': result['finding'],
            'input_digest': result['input_digest'], 'model': MODEL, 'analysis': result}, job_id=job['job_id'])
    except BaseException:
        # Cancellation is also a failed lease. Never leave a job running merely
        # because the HTTP client disconnected or the process is shutting down.
        try:
            await asyncio.shield(repo.rpc('fail_analysis', {'job_id': job['job_id'],
                'error': 'Investigation did not commit; prior case data retained'}))
        except Exception:
            pass
        raise
