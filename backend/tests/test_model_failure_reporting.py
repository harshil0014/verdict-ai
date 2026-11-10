import asyncio
import pytest
from investigator import ModelError,model_failure_info
import automatic_investigation as auto
from test_automatic_investigation import fake_process


@pytest.mark.parametrize('status,code,retryable',[(503,'model_unavailable',True),(429,'model_rate_limited',True),(403,'model_access_denied',False),(500,'model_unavailable',True)])
def test_provider_status_is_safe_and_distinct_from_bad_evidence(status,code,retryable):
    detail=model_failure_info(ModelError(f'Gemini returned HTTP {status}; private-key-and-evidence-must-not-leak'))
    assert detail['http_status']==status and detail['code']==code and detail['retryable']==retryable
    assert 'private-key' not in str(detail) and 'missing information' not in detail['summary']


def test_network_and_non_model_failures_are_not_reported_as_a_fake_http_status():
    assert model_failure_info(ModelError('Gemini network request failed.'))['http_status'] is None
    assert model_failure_info(RuntimeError('a private implementation detail')) is None


def test_transient_failure_survives_in_durable_workflow_progress(monkeypatch):
    case,calls,claim=fake_process(monkeypatch)
    async def unavailable(*a,**k):raise ModelError('Gemini returned HTTP 503; secret provider body')
    monkeypatch.setattr(auto,'run_investigation',unavailable)
    asyncio.run(auto.process(claim))
    args=next(x[1] for x in calls if x[0]=='workflow:reschedule')
    assert args['progress']['last_failure']['http_status']==503
    assert args['progress']['last_failure']['code']=='model_unavailable'
    assert 'secret provider body' not in str(args)
    assert not any(x[0]=='workflow:finish' for x in calls)


def test_permanent_failure_records_its_safe_diagnosis_before_finish(monkeypatch):
    case,calls,claim=fake_process(monkeypatch)
    async def denied(*a,**k):raise ModelError('Gemini returned HTTP 403; private provider body')
    monkeypatch.setattr(auto,'run_investigation',denied)
    asyncio.run(auto.process(claim))
    assert claim['progress']['last_failure']['code']=='model_access_denied'
    assert any(x[0]=='workflow:finish' and x[1]['state']=='failed' for x in calls)
