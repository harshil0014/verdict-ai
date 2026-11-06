import asyncio
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs
from paypal import PayPal
from paypal import error_diagnostic
import httpx


def test_list_uses_explicit_history_window_and_follows_validated_pages(monkeypatch):
    provider = PayPal()
    paths = []
    async def request(method, path):
        paths.append(path)
        if len(paths) == 1:
            query = parse_qs(urlparse(path).query)
            after = datetime.fromisoformat(query["update_time_after"][0].replace("Z", "+00:00"))
            assert 178 < (datetime.now(timezone.utc) - after).total_seconds()/86400 < 180
            assert query["page_size"] == ["50"]
            return {"items": [{"dispute_id": "PP-D-TEST-1"}], "links": [{"rel": "next", "href": "https://api-m.sandbox.paypal.com/v1/customer/disputes?page=2"}]}
        return {"items": [{"dispute_id": "PP-D-TEST-2"}]}
    monkeypatch.setattr(provider, "request", request)
    assert len(asyncio.run(provider.disputes())) == 2
    assert paths[-1] == "/v1/customer/disputes?page=2"


def test_rejection_diagnostics_keep_codes_without_customer_data():
    response = httpx.Response(422, json={"name": "UNPROCESSABLE_ENTITY", "debug_id": "test-debug-123", "message": "Customer private message", "details": [{"issue": "INVALID_EVIDENCE_TYPE", "description": "private details", "value": "private value"}, {"issue": "private@example.invalid"}]})
    diagnostic = error_diagnostic(response)
    assert diagnostic == {"http_status": 422, "name": "UNPROCESSABLE_ENTITY", "debug_id": "test-debug-123", "issues": ["INVALID_EVIDENCE_TYPE"]}
    assert error_diagnostic(httpx.Response(502, text="private html")) == {"http_status": 502}
