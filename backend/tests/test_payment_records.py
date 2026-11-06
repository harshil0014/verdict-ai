import asyncio
import copy
import json
import httpx
import pytest
import app as application
import investigator
import store
from domain import Analysis, SupportReview
from fixtures import evidence
from payment_records import ReadBudget, active_sources, fetch_records, merge_records
from paypal import PayPal, PayPalError
from test_boundaries import env, login


def capture(identifier="CAP1", status="COMPLETED", order="ORDER1"):
    return {"id": identifier, "status": status, "amount": {"currency_code": "USD", "value": "1.00"}, "supplementary_data": {"related_ids": {"order_id": order}}}


def snapshot(record, kind="capture"):
    source = evidence(f"PayPal {kind} {record['id']}", json.dumps(record), "payment_provider", "paypal_sandbox_api")
    source.update(origin_verified=True, synthetic=False)
    return source


def detail(identifier="PP-D-TESTAUTO", transaction="CAP1"):
    return {"dispute_id": identifier, "status": "WAITING_FOR_SELLER_RESPONSE", "reason": "MERCHANDISE_OR_SERVICE_NOT_RECEIVED", "disputed_transactions": [{"seller_transaction_id": transaction}], "dispute_amount": {"value": "1.00", "currency_code": "USD"}}


def test_reads_are_bounded_deduplicate_capture_and_order_and_never_write():
    class Reader:
        def __init__(self): self.calls = []
        async def request(self, method, path):
            assert method == "GET"
            self.calls.append(path)
            identifier = path.rsplit("/", 1)[1]
            return capture(identifier) if "/captures/" in path else {"id": identifier}
    reader = Reader()
    body = {"disputed_transactions": [{"seller_transaction_id": c} for c in ("CAP1", "CAP1", "CAP2")]}
    records, issues, count = asyncio.run(fetch_records(reader, body, ReadBudget(3)))
    assert len(reader.calls) == 3 and count == 2 and not issues
    assert len(records) == 3
    assert sum("/orders/" in p for p in reader.calls) == 1
    assert asyncio.run(fetch_records(reader, body, ReadBudget(0)))[0] == []
    assert len(reader.calls) == 3


def test_inaccessible_or_mismatched_records_never_become_verified_evidence():
    class Reader:
        async def request(self, method, path):
            if path.endswith("CAP1"): raise PayPalError(403)
            return {"id": "WRONGID"}
    body = {"disputed_transactions": [{"seller_transaction_id": x} for x in ("CAP1", "CAP2", "../unsafe")]}
    records, issues, count = asyncio.run(fetch_records(Reader(), body, ReadBudget()))
    assert records == [] and count == 2
    assert set(issues) == {"capture_unavailable:403", "capture_identifier_mismatch", "invalid_capture_identifier"}


def test_legacy_snapshot_is_not_duplicated_when_only_json_key_order_changes():
    original = snapshot(capture())
    body = {"evidence": [original], "analysis": {"finding": "insufficient"}, "analysis_stale": False}
    record = {"kind": "capture", "id": "CAP1", "body": dict(reversed(list(capture().items())))}
    first = merge_records(body, [record], [], 1)
    assert first["source_ids"] == [] and body["evidence"] == [original]
    assert body["analysis_stale"] is False
    assert merge_records(body, [record], [], 1)["changed"] is False


def test_changed_record_preserves_old_bytes_and_reverting_creates_a_new_version():
    original = snapshot(capture(status="PENDING"))
    old_text, old_hash = original["text"], original["sha256"]
    body = {"evidence": [original], "analysis": {"finding": "insufficient"}}
    merge_records(body, [{"kind": "capture", "id": "CAP1", "body": capture()}], [], 1)
    assert len(body["evidence"]) == 2 and body["analysis_stale"]
    assert original["text"] == old_text and original["sha256"] == old_hash
    assert original["superseded_by"] == body["evidence"][-1]["id"]
    assert active_sources(body["evidence"]) == [body["evidence"][-1]]
    merge_records(body, [{"kind": "capture", "id": "CAP1", "body": capture(status="PENDING")}], [], 1)
    assert len(body["evidence"]) == 3
    assert active_sources(body["evidence"]) == [body["evidence"][-1]]


def test_unverified_or_unrelated_replacement_cannot_hide_a_source():
    old, new = snapshot(capture()), snapshot(capture(status="REFUNDED"))
    old["superseded_by"] = new["id"]
    new["origin_verified"] = False
    assert active_sources([old, new]) == [old, new]
    new["origin_verified"] = True
    new["text"] = json.dumps(capture("DIFFERENT"))
    new["title"] = "PayPal capture DIFFERENT"
    assert active_sources([old, new]) == [old, new]


@pytest.mark.parametrize("new_status", ["COMPLETED", "REFUNDED"])
def test_old_duplicate_snapshots_are_preserved_but_only_latest_is_active(new_status):
    sources = [snapshot(capture()) for _ in range(2)]
    original = [(s["text"], s["sha256"]) for s in sources]
    body = {"evidence": sources, "analysis": {"finding": "insufficient"}}
    merge_records(body, [{"kind": "capture", "id": "CAP1", "body": capture(status=new_status)}], [], 1)
    assert [(s["text"], s["sha256"]) for s in sources[:2]] == original
    assert active_sources(body["evidence"]) == [body["evidence"][-1]]
    assert body["analysis_stale"]


def test_source_history_limit_does_not_erase_or_silently_replace_content():
    body = {"evidence": [snapshot(capture(status="PENDING")) for _ in range(40)], "analysis": {}}
    before = [e["text"] for e in body["evidence"]]
    result = merge_records(body, [{"kind": "capture", "id": "CAP1", "body": capture()}], [], 1)
    assert "evidence_source_limit" in result["acquisition"]["issues"]
    assert [e["text"] for e in body["evidence"]] == before
    assert len(body["evidence"]) == 40


def test_import_acquires_records_and_identical_refresh_is_idempotent(env, monkeypatch):
    login(env)
    state, calls = {"status": "COMPLETED"}, []
    async def provider_detail(identifier): return detail()
    async def read(method, path, **kw):
        assert method == "GET"
        calls.append(path)
        return capture(status=state["status"]) if "/captures/" in path else {"id": "ORDER1", "status": "COMPLETED"}
    monkeypatch.setattr(application.paypal, "detail", provider_detail)
    monkeypatch.setattr(application.paypal, "request", read)
    route = "/api/paypal/import"
    first = env.post(route, json={"dispute_id": "PP-D-TESTAUTO"}).json()
    assert len(first["evidence"]) == 3 and first["payment_record_acquisition"]["status"] == "complete"
    second = env.post(route, json={"dispute_id": "PP-D-TESTAUTO"}).json()
    assert first == second and len(calls) == 4
    first["analysis"] = {"finding": "insufficient"}
    store.save(first, "operator", "analysis_fixture", {})
    state["status"] = "REFUNDED"
    third = env.post(route, json={"dispute_id": "PP-D-TESTAUTO"}).json()
    assert third["analysis_stale"] and len(third["evidence"]) == 4
    assert len(active_sources(third["evidence"])) == 3


def test_dispute_refresh_preserves_history_and_excludes_superseded_snapshot(env, monkeypatch):
    login(env)
    state = detail()
    state["disputed_transactions"] = []
    async def provider_detail(identifier): return copy.deepcopy(state)
    monkeypatch.setattr(application.paypal, "detail", provider_detail)
    first = env.post("/api/paypal/import", json={"dispute_id": "PP-D-TESTAUTO"}).json()
    state["status"] = "WAITING_FOR_BUYER_RESPONSE"
    second = env.post("/api/paypal/import", json={"dispute_id": "PP-D-TESTAUTO"}).json()
    assert len(second["evidence"]) == 2
    assert second["evidence"][0]["text"] == first["evidence"][0]["text"]
    assert active_sources(second["evidence"]) == [second["evidence"][-1]]


def test_failed_read_keeps_actual_dispute_and_records_unavailability(env, monkeypatch):
    login(env)
    async def provider_detail(identifier): return detail()
    async def forbidden(*args, **kwargs): raise PayPalError(403)
    monkeypatch.setattr(application.paypal, "detail", provider_detail)
    monkeypatch.setattr(application.paypal, "request", forbidden)
    r = env.post("/api/paypal/import", json={"dispute_id": "PP-D-TESTAUTO"})
    assert r.status_code == 200
    body = r.json()
    assert len(body["evidence"]) == 1 and body["evidence"][0]["origin_verified"]
    assert body["payment_record_acquisition"]["status"] == "unavailable"
    assert body["payment_record_acquisition"]["issues"] == ["capture_unavailable:403"]


def test_sync_shares_payment_read_budget_across_cases(env, monkeypatch):
    login(env)
    calls = []
    async def rows(): return [{"dispute_id": "PP-D-"+str(i)} for i in range(8)]
    async def provider_detail(identifier): return detail(identifier, "CAP"+identifier.rsplit("-", 1)[1])
    async def read(method, path, **kw):
        assert method == "GET"
        calls.append(path)
        identifier = path.rsplit("/", 1)[1]
        return capture(identifier, order="ORDER"+identifier[3:]) if "/captures/" in path else {"id": identifier}
    monkeypatch.setattr(application.paypal, "disputes", rows)
    monkeypatch.setattr(application.paypal, "detail", provider_detail)
    monkeypatch.setattr(application.paypal, "request", read)
    assert env.post("/api/paypal/sync").json()["imported"] == 8
    assert len(calls) == 12
    assert sum(b.get("payment_record_acquisition", {}).get("status") == "deferred" for b in env.get("/api/cases").json()) == 2


def test_model_never_receives_superseded_provider_record_or_accepts_its_quote(monkeypatch):
    old, current = snapshot(capture(status="PENDING")), snapshot(capture())
    old["superseded_by"] = current["id"]
    seen = []
    async def generate(prompt, payload, schema):
        seen.append(payload)
        if schema is SupportReview: return SupportReview(reviews=[]), {}
        return Analysis(summary="Test", finding="supports_seller", claims=[{"id":"C1","text":"Pending","source_id":old["id"],"quote":"PENDING","subject":"payment","field":"status","value":"PENDING","stance":"neutral"}], hypotheses=[], requests=[], unknowns=[], recommendation="Review"), {}
    monkeypatch.setattr(investigator, "generate", generate)
    result = asyncio.run(investigator.investigate({"id":"TEST","evidence":[old,current]}))
    assert [s["id"] for s in seen[0]["evidence"]] == [current["id"]]
    assert result["finding"] == "insufficient" and not result["claims"] and result["rejected_claims"]


def test_authentication_network_failure_is_not_a_dispatched_write(monkeypatch):
    real = httpx.AsyncClient
    def failure(request): raise httpx.ConnectError("Test transport error", request=request)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(failure), **kw))
    with pytest.raises(PayPalError) as error:
        asyncio.run(PayPal().request("POST", "/v1/customer/disputes/PP-D-TEST/send-message", {}))
    assert error.value.status == "authentication_network_error" and error.value.uncertain is False


@pytest.mark.parametrize("method,uncertain", [("GET", False), ("POST", True)])
def test_unparseable_provider_success_is_unknown_for_writes_and_never_retried(monkeypatch, method, uncertain):
    real, calls = httpx.AsyncClient, []
    def response(request):
        calls.append(request)
        return httpx.Response(200, text="not provider JSON")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(response), **kw))
    provider = PayPal()
    provider.token, provider.expires = "test-only-token", float("inf")
    with pytest.raises(PayPalError) as error:
        asyncio.run(provider.request(method, "/v1/customer/disputes/PP-D-TEST/send-message"))
    assert error.value.status == "invalid_json_response" and error.value.uncertain is uncertain
    assert len(calls) == 1
