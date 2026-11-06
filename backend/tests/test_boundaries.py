import asyncio, json, time, hashlib
import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
import store
import app as application
from domain import ActionInput, ExecuteInput
from fixtures import evidence
from investigator import validate_sources, comparisons, model_schema
from domain import Analysis
from paypal import allowed, PayPalError


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB", tmp_path / "test.sqlite3")
    monkeypatch.setenv("VERDICT_OPERATOR_PASSWORD", "test-only-long-operator-password")
    monkeypatch.setenv("VERDICT_SUPABASE_MIRROR", "false")
    monkeypatch.setenv("VERDICT_LOCAL_BOOTSTRAP", "false")
    monkeypatch.setenv("VERDICT_ALLOW_SANDBOX_ACTIONS", "false")
    application.LOGIN_FAILURES.clear()
    with TestClient(application.app) as client:
        yield client


def login(c):
    assert (
        c.post(
            "/api/auth/login", json={"password": "test-only-long-operator-password"}
        ).status_code
        == 200
    )


def demo(c):
    assert c.post("/api/auth/demo").status_code == 200
    return c.get("/api/cases").json()[-1]


def case_for_actions():
    body = store.create(
        "operator",
        {
            "title": "Sandbox fixture",
            "mode": "paypal_sandbox",
            "paypal_id": "PP-D-TEST",
            "amount": "10.00",
            "currency": "USD",
            "status": "WAITING_FOR_SELLER_RESPONSE",
            "evidence": [evidence("tracking", "Tracking T1 shipped.")],
        },
    )
    body["analysis"] = {"finding": "insufficient", "requests": []}
    return store.save(body, "operator", "analysis_fixture", {})


def provider_detail():
    return {
        "dispute_id": "PP-D-TEST",
        "status": "WAITING_FOR_SELLER_RESPONSE",
        "links": [
            {
                "method": "POST",
                "href": "https://api-m.sandbox.paypal.com/v1/customer/disputes/PP-D-TEST/send-message",
            }
        ],
    }


def test_authentication_is_required(env):
    assert env.get("/api/cases").status_code == 401
    assert env.post("/api/paypal/sync").status_code == 401


def test_optional_paypal_does_not_hide_other_integration_status(env, monkeypatch):
    login(env)
    monkeypatch.delenv("PAYPAL_CLIENT_ID", raising=False)
    monkeypatch.delenv("PAYPAL_CLIENT_SECRET", raising=False)
    async def must_not_call():
        raise AssertionError("Unconfigured provider must not receive an OAuth request")
    monkeypatch.setattr(application.paypal, "disputes", must_not_call)
    r = env.get("/api/integrations")
    assert r.status_code == 200
    assert r.json()["paypal"]["status"] == "not_configured"
    assert r.json()["paypal"]["list_status"] is None
    assert "gemini" in r.json() and "storage" in r.json()
    monkeypatch.setenv("PAYPAL_CLIENT_ID", "test-id")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "test-secret")
    async def unavailable():
        raise PayPalError(403)
    monkeypatch.setattr(application.paypal, "disputes", unavailable)
    r = env.get("/api/integrations")
    assert r.status_code == 200
    assert r.json()["paypal"]["status"] == "unavailable"
    assert r.json()["paypal"]["disputes"] is None


def test_exact_case_import_requires_operator_and_provider_record(env, monkeypatch):
    calls = []
    async def detail(identifier):
        calls.append(identifier)
        return {**provider_detail(), "reason": "MERCHANDISE_OR_SERVICE_NOT_RECEIVED", "dispute_amount": {"currency_code": "USD", "value": "1.00"}}
    monkeypatch.setattr(application.paypal, "detail", detail)
    assert env.post("/api/paypal/import", json={"dispute_id": "PP-D-TEST"}).status_code == 401
    demo(env)
    assert env.post("/api/paypal/import", json={"dispute_id": "PP-D-TEST"}).status_code == 403
    assert not calls
    login(env)
    response = env.post("/api/paypal/import", json={"dispute_id": "PP-D-TEST"})
    assert response.status_code == 200
    assert calls == ["PP-D-TEST"]
    body = response.json()
    assert body["mode"] == "paypal_sandbox" and body["evidence"][0]["origin_verified"]
    assert env.post("/api/paypal/import", json={"dispute_id": "../unsafe"}).status_code == 422


def test_other_evidence_notes_use_exact_approval_without_fabricated_tracking(env, monkeypatch):
    login(env)
    body = case_for_actions()
    detail_body = provider_detail()
    detail_body["links"][0]["href"] = detail_body["links"][0]["href"].replace("send-message", "provide-evidence")
    detail_body["evidences"] = [{"source": "REQUESTED_FROM_SELLER", "evidence_type": "OTHER"}]
    async def detail(identifier):
        return detail_body
    sent = []
    async def send(*args, **kwargs):
        sent.append(kwargs)
        return {}
    monkeypatch.setattr(application.paypal, "detail", detail)
    monkeypatch.setattr(application.paypal, "request", send)
    monkeypatch.setenv("VERDICT_ALLOW_SANDBOX_ACTIONS", "true")
    path = "/api/cases/" + body["id"] + "/actions/"
    note = "Sandbox test only. No goods shipped; no fulfillment proof exists."
    response = env.post(path + "prepare", json={"action": "provide-evidence", "evidence_type": "OTHER", "note": note})
    assert response.status_code == 200
    plan = response.json()
    expected = {"evidences": [{"evidence_type": "OTHER", "notes": note}]}
    assert plan["approval"]["payload"] == expected
    params = {"approval_id": plan["approval"]["id"], "reviewed_digest": plan["digest"], "confirmed": True}
    assert env.post(path + "execute", json=params).json()["status"] == "succeeded"
    assert json.loads(sent[0]["files"]["input"][1]) == expected
    assert env.post(path + "execute", json=params).json()["status"] == "succeeded"
    assert len(sent) == 1
    assert env.post(path + "prepare", json={"action": "provide-evidence", "evidence_type": "OTHER", "note": note, "tracking_number": "invented"}).status_code == 422
    detail_body["evidences"][0]["evidence_type"] = "PROOF_OF_FULFILLMENT"
    assert env.post(path + "prepare", json={"action": "provide-evidence", "evidence_type": "OTHER", "note": note}).status_code == 409
    assert len(sent) == 1


def test_demo_tenant_cannot_read_operator_or_other_demo(env):
    first = demo(env)
    first_id = first["id"]
    other = demo(env)
    assert env.get("/api/cases/" + first_id).status_code == 404
    with store.connect() as c:
        private = c.execute(
            "SELECT id FROM cases WHERE tenant='operator' LIMIT 1"
        ).fetchone()["id"]
    assert env.get("/api/cases/" + private).status_code == 404
    assert env.get("/api/cases/" + other["id"]).status_code == 200


def test_demo_cannot_read_or_write_paypal(env):
    body = demo(env)
    assert env.post("/api/paypal/sync").status_code == 403
    assert env.get("/api/integrations").status_code == 403
    assert (
        env.post(
            "/api/cases/" + body["id"] + "/actions/execute",
            json={"approval_id": "x", "reviewed_digest": "x", "confirmed": True},
        ).status_code
        == 403
    )


def test_hosted_demo_requires_owner_provided_code(env, monkeypatch):
    monkeypatch.setenv("VERDICT_PUBLIC_HOST", "verdict.example")
    assert env.post("/api/auth/demo").status_code == 403
    monkeypatch.setenv("VERDICT_DEMO_ACCESS_CODE", "test-judge-access-code-long")
    assert env.post("/api/auth/demo", json={"code": "wrong"}).status_code == 403
    assert (
        env.post(
            "/api/auth/demo", json={"code": "test-judge-access-code-long"}
        ).status_code
        == 200
    )


def test_cloud_outbox_retains_failed_backup_and_advances_after_success(
    env, monkeypatch
):
    import cloud

    monkeypatch.setenv("VERDICT_SUPABASE_MIRROR", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://invalid.test")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "test-secret-not-real")
    body = store.create(
        "operator", {"title": "Backup fixture", "mode": "synthetic", "evidence": []}
    )

    class Result:
        status_code = 503

    monkeypatch.setattr(cloud.httpx, "post", lambda *a, **k: Result())
    cloud.flush_one()
    with store.connect() as c:
        assert (
            c.execute(
                "SELECT error FROM cloud_outbox WHERE case_id=?", (body["id"],)
            ).fetchone()["error"]
            == "Supabase HTTP 503"
        )
    Result.status_code = 201
    cloud.flush_one()
    with store.connect() as c:
        assert not c.execute(
            "SELECT * FROM cloud_outbox WHERE case_id=?", (body["id"],)
        ).fetchone()
        assert (
            c.execute(
                "SELECT revision FROM cloud_sync WHERE case_id=?", (body["id"],)
            ).fetchone()["revision"]
            == 1
        )


def test_only_operator_cases_enter_cloud_outbox(env, monkeypatch):
    monkeypatch.setenv("VERDICT_SUPABASE_MIRROR", "true")
    body = store.create(
        "demo-private",
        {"title": "Private demo fixture", "mode": "synthetic", "evidence": []},
    )
    with store.connect() as c:
        assert not c.execute(
            "SELECT * FROM cloud_outbox WHERE case_id=?", (body["id"],)
        ).fetchone()


def test_logout_invalidates_session(env):
    demo(env)
    env.post("/api/auth/logout")
    assert env.get("/api/me").status_code == 401


def test_login_rate_limit(env):
    for _ in range(8):
        assert (
            env.post("/api/auth/login", json={"password": "wrong"}).status_code == 401
        )
    assert env.post("/api/auth/login", json={"password": "wrong"}).status_code == 429


def test_cross_origin_and_dns_rebinding_rejected(env):
    assert (
        env.post(
            "/api/auth/demo", headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert env.get("/", headers={"Host": "evil.example"}).status_code == 400


def test_security_response_headers(env):
    r = env.get("/api/me")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]


@pytest.mark.parametrize(
    "name,data",
    [
        ("evil.html", b"<script>bad()</script>"),
        ("evil.exe", b"MZ"),
        ("fake.pdf", b"not a pdf"),
        ("bad.txt", b"abc\x00def"),
        ("bad.json", b"{bad"),
    ],
)
def test_unsafe_uploads_fail_closed(env, name, data):
    body = demo(env)
    r = env.post("/api/cases/" + body["id"] + "/upload", files={"file": (name, data)})
    assert r.status_code in (415, 422)


def test_upload_and_original_download_are_scoped(env):
    body = demo(env)
    path = "/api/cases/" + body["id"]
    r = env.post(
        path + "/upload",
        files={"file": ("carrier.txt", b"Carrier destination postcode 94103.")},
    )
    assert r.status_code == 200
    ev = r.json()["evidence"][-1]
    assert (
        ev["sha256"]
        == hashlib.sha256(b"Carrier destination postcode 94103.").hexdigest()
    )
    assert not ev["origin_verified"]
    assert (
        env.get(path + "/files/" + ev["id"]).content
        == b"Carrier destination postcode 94103."
    )
    demo(env)
    assert env.get(path + "/files/" + ev["id"]).status_code == 404


def test_ai_consent_is_enforced_before_network(env):
    body = demo(env)
    assert (
        env.post(
            "/api/cases/" + body["id"] + "/analyze", json={"consent": False}
        ).status_code
        == 422
    )


def test_version_conflict_cannot_overwrite_new_evidence(env):
    body = demo(env)
    tenant = env.get("/api/me").json()["tenant"]
    old = store.get(body["id"], tenant)
    store.save(body, tenant, "first", {})
    with pytest.raises(ValueError):
        store.save(old, tenant, "stale", {})


def test_audit_modification_is_detected(env):
    body = demo(env)
    assert store.verify_timeline(store.timeline(body["id"]))
    with store.connect() as c:
        c.execute("UPDATE audit SET kind='altered' WHERE case_id=?", (body["id"],))
        c.commit()
    assert not store.verify_timeline(store.timeline(body["id"]))


def test_bad_citations_removed_and_graph_edges_pruned():
    result = {
        "claims": [
            {"id": "C1", "source_id": "E1", "quote": "not present"},
            {"id": "C2", "source_id": "missing", "quote": "x"},
        ],
        "hypotheses": [{"id": "H1", "supports": ["C1"], "challenges": ["C2"]}],
        "requests": [],
    }
    r = validate_sources(result, [{"id": "E1", "text": "Delivered to reception."}])
    assert not r["claims"]
    assert len(r["rejected_claims"]) == 2
    assert not r["hypotheses"][0]["supports"]


def test_quote_presence_is_not_semantic_entailment():
    result = {
        "claims": [
            {
                "id": "C1",
                "source_id": "E1",
                "quote": "Delivered to reception.",
                "text": "Buyer personally received parcel",
            }
        ],
        "hypotheses": [],
        "requests": [],
    }
    c = validate_sources(result, [{"id": "E1", "text": "Delivered to reception."}])[
        "claims"
    ][0]
    assert c["source_check"] == "exact_quote_found"
    assert c["semantic_support"] == "uncertain"


def test_comparison_requires_semantic_support_and_same_subject():
    rows = [
        {
            "id": "A",
            "subject": "order1",
            "field": "destination_postcode",
            "value": "94107",
            "quote": "Postcode 94107",
            "semantic_support": "entailed",
        },
        {
            "id": "B",
            "subject": "order1",
            "field": "destination_postcode",
            "value": "94103",
            "quote": "Postcode 94103",
            "semantic_support": "entailed",
        },
    ]
    assert len(comparisons(rows)) == 1
    rows[1]["semantic_support"] = "unsupported"
    assert not comparisons(rows)
    rows[1].update(semantic_support="entailed", subject="order2")
    assert not comparisons(rows)


def test_timestamps_with_different_zones_are_compared_in_utc():
    values = ["2026-11-04T00:30:00+05:30", "2026-11-03T19:00:00+00:00"]
    rows = [
        {
            "id": str(i),
            "subject": "order1",
            "field": "delivery_date",
            "value": v,
            "quote": v,
            "semantic_support": "entailed",
        }
        for i, v in enumerate(values)
    ]
    assert not comparisons(rows)
    rows[1].update(value="2026-11-03T20:00:00+00:00", quote="2026-11-03T20:00:00+00:00")
    assert len(comparisons(rows)) == 1


def test_extracted_value_not_present_in_quote_is_not_compared():
    rows = [
        {
            "id": "A",
            "subject": "order1",
            "field": "destination_postcode",
            "value": "94107",
            "quote": "94107",
            "semantic_support": "entailed",
        },
        {
            "id": "B",
            "subject": "order1",
            "field": "destination_postcode",
            "value": "94103",
            "quote": "Delivered to reception",
            "semantic_support": "entailed",
        },
    ]
    assert not comparisons(rows)


def test_schema_cleaning_preserves_title_property():
    schema = model_schema(Analysis)
    h = schema["properties"]["hypotheses"]["items"]
    assert "title" in h["properties"]


def test_hateoas_cannot_authorize_wrong_host_case_or_get():
    detail = provider_detail()
    assert allowed(detail) == ["send-message"]
    for href, method in [
        ("https://evil.example/v1/customer/disputes/PP-D-TEST/send-message", "POST"),
        (
            "https://api-m.sandbox.paypal.com/v1/customer/disputes/OTHER/send-message",
            "POST",
        ),
        (
            "https://api-m.sandbox.paypal.com/v1/customer/disputes/PP-D-TEST/send-message",
            "GET",
        ),
    ]:
        assert not allowed(
            {"dispute_id": "PP-D-TEST", "links": [{"href": href, "method": method}]}
        )


def request_fixture(env):
    body = demo(env)
    tenant = env.get("/api/me").json()["tenant"]
    body["analysis"] = {
        "finding": "insufficient",
        "requests": [
            {
                "id": "W1",
                "title": "Destination proof",
                "question": "What destination did the carrier record?",
                "recipient": "carrier",
                "distinguishes": ["H1", "H2"],
                "rationale": "Different destinations distinguish misdelivery.",
                "burden": "low",
                "priority": "first",
            }
        ],
    }
    store.save(body, tenant, "analysis_fixture", {})
    r = env.post("/api/cases/" + body["id"] + "/requests", json={"witness_id": "W1"})
    assert r.status_code == 200
    token = r.json()["portal_fragment"].split("=", 1)[1]
    return body, tenant, token


def test_portal_exposes_only_question_and_accepts_one_scoped_reply(env):
    body, tenant, token = request_fixture(env)
    h = {"Authorization": "Bearer " + token}
    d = env.get("/api/portal", headers=h).json()
    assert set(d) == {"id", "title", "question", "recipient", "expires_at"}
    assert env.get("/api/portal").status_code == 401
    payload = {
        "title": "Carrier response",
        "text": "Tracking destination was 94103.",
        "party": "buyer",
    }
    assert env.post("/api/portal", headers=h, json=payload).status_code == 200
    assert env.post("/api/portal", headers=h, json=payload).status_code == 409
    stored = store.get(body["id"], tenant)
    assert stored["evidence"][-1]["party"] == "carrier"
    assert stored["requests"][-1]["status"] == "received"
    assert stored["analysis_stale"]


def test_portal_token_not_stored_in_plaintext(env):
    _, _, token = request_fixture(env)
    with store.connect() as c:
        text = json.dumps([tuple(r) for r in c.execute("SELECT * FROM requests")])
    assert token not in text


@pytest.mark.parametrize("status", ["unavailable", "withdrawn"])
def test_closing_request_revokes_all_portal_paths_and_preserves_uncertainty(env, status):
    body, tenant, token = request_fixture(env)
    original = store.get(body["id"], tenant)
    request_id = original["requests"][-1]["id"]
    path = f"/api/cases/{body['id']}/requests/{request_id}/close"
    r = env.post(path, json={"status": status, "reason": "Carrier reports the destination record cannot be obtained."})
    assert r.status_code == 200
    closed = r.json()
    assert closed["analysis_stale"] and closed["revision"] == original["revision"] + 1
    assert closed["evidence"] == original["evidence"]
    assert closed["analysis"] == original["analysis"]
    req = closed["requests"][-1]
    assert req["status"] == status and req["availability_verified"] is False
    assert req["closure_origin"] == "investigator_report"
    h = {"Authorization": "Bearer " + token}
    assert env.get("/api/portal", headers=h).status_code == 409
    assert env.post("/api/portal", headers=h, json={"title": "Late response", "text": "Late record", "party": "carrier"}).status_code == 409
    assert env.post("/api/portal/upload", headers=h, files={"file": ("late.txt", b"Late record")}).status_code == 409
    assert env.post(path, json={"status": status, "reason": "Close again"}).status_code == 409
    event = store.timeline(body["id"])[-1]
    assert event["kind"] == "witness_request_closed" and event["data"]["portal_revoked"]
    assert store.verify_timeline(store.timeline(body["id"]))


def test_an_answered_request_cannot_be_relabelled_unavailable(env):
    body, tenant, token = request_fixture(env)
    h = {"Authorization": "Bearer " + token}
    assert env.post("/api/portal", headers=h, json={"title": "Response", "text": "Carrier record", "party": "carrier"}).status_code == 200
    before = store.get(body["id"], tenant)
    request_id = before["requests"][-1]["id"]
    assert env.post(f"/api/cases/{body['id']}/requests/{request_id}/close", json={"status": "unavailable", "reason": "Incorrect relabelling"}).status_code == 409
    assert store.get(body["id"], tenant) == before


def test_other_tenant_cannot_revoke_witness_portal(env):
    body, tenant, token = request_fixture(env)
    request_id = store.get(body["id"], tenant)["requests"][-1]["id"]
    demo(env)
    assert env.post(f"/api/cases/{body['id']}/requests/{request_id}/close", json={"status": "withdrawn", "reason": "Cross tenant"}).status_code == 404
    assert env.get("/api/portal", headers={"Authorization": "Bearer " + token}).status_code == 200


def test_reply_started_before_revocation_cannot_commit_after_it(env):
    body, tenant, token = request_fixture(env)
    stale = store.get(body["id"], tenant)
    with store.connect() as c:
        row = dict(c.execute("SELECT * FROM requests WHERE case_id=?", (body["id"],)).fetchone())
    request_id = stale["requests"][-1]["id"]
    assert env.post(f"/api/cases/{body['id']}/requests/{request_id}/close", json={"status": "withdrawn", "reason": "Wrong recipient"}).status_code == 200
    with pytest.raises(ValueError, match="Case changed"):
        application.add_evidence(stale, tenant, application.EvidenceInput(title="Late", text="Late response", party="carrier"), request_row=row)
    assert len(store.get(body["id"], tenant)["evidence"]) == len(body["evidence"])


def test_failed_portal_revocation_rolls_back_case_and_audit(env):
    body, tenant, _ = request_fixture(env)
    before = store.get(body["id"], tenant)
    history = store.timeline(body["id"])
    with store.connect() as c:
        c.execute("UPDATE requests SET completed=1 WHERE case_id=?", (body["id"],))
        c.commit()
    request_id = before["requests"][-1]["id"]
    assert env.post(f"/api/cases/{body['id']}/requests/{request_id}/close", json={"status": "withdrawn", "reason": "Concurrent reply"}).status_code == 409
    assert store.get(body["id"], tenant) == before
    assert store.timeline(body["id"]) == history


def test_blank_closure_reason_cannot_revoke_link(env):
    body, tenant, token = request_fixture(env)
    request_id = store.get(body["id"], tenant)["requests"][-1]["id"]
    assert env.post(f"/api/cases/{body['id']}/requests/{request_id}/close", json={"status": "withdrawn", "reason": "   "}).status_code == 422
    assert env.get("/api/portal", headers={"Authorization": "Bearer " + token}).status_code == 200


def test_human_can_correct_witness_recipient_and_question(env):
    body, tenant, token = request_fixture(env)
    r = env.post(
        "/api/cases/" + body["id"] + "/requests",
        json={
            "witness_id": "W1",
            "title": "Reviewed request",
            "question": "Please supply the original warehouse handover scan.",
            "recipient": "seller",
        },
    )
    assert r.status_code == 200
    assert r.json()["request"]["recipient"] == "seller"
    event = store.timeline(body["id"])[-1]
    assert event["data"]["human_edited"] is True
    assert event["data"]["model_proposal"]["recipient"] == "carrier"


def test_text_pdf_upload_extracts_page_provenance(env):
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    import io

    writer = PdfWriter()
    page = writer.add_blank_page(width=400, height=400)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    stream = DecodedStreamObject()
    stream.set_data(
        b"BT /F1 12 Tf 20 350 Td (Carrier record: destination postcode 94103, not 94107.) Tj ET"
    )
    page[NameObject("/Contents")] = writer._add_object(stream)
    data = io.BytesIO()
    writer.write(data)
    body = demo(env)
    response = env.post(
        "/api/cases/" + body["id"] + "/upload",
        files={"file": ("carrier.pdf", data.getvalue(), "application/pdf")},
    )
    assert response.status_code == 200
    source = response.json()["evidence"][-1]
    assert "[Page 1]" in source["text"] and "94103" in source["text"]
    assert source["file_available"] and source["mime"] == "application/pdf"


def test_expired_portal_and_stale_analysis_request_fail(env):
    body, tenant, token = request_fixture(env)
    with store.connect() as c:
        c.execute("UPDATE requests SET expires=0")
        c.commit()
    assert (
        env.get("/api/portal", headers={"Authorization": "Bearer " + token}).status_code
        == 404
    )
    body = store.get(body["id"], tenant)
    body["analysis_stale"] = True
    store.save(body, tenant, "new_evidence", {})
    assert (
        env.post(
            "/api/cases/" + body["id"] + "/requests", json={"witness_id": "W1"}
        ).status_code
        == 409
    )


def test_fictional_case_can_never_prepare_paypal_action(env):
    login(env)
    body = env.get("/api/cases").json()[0]
    assert (
        env.post(
            "/api/cases/" + body["id"] + "/actions/prepare",
            json={"action": "send-message", "note": "hello"},
        ).status_code
        == 422
    )


def test_stale_approval_and_modified_digest_do_not_dispatch(env, monkeypatch):
    login(env)
    body = case_for_actions()
    calls = []

    async def detail(id):
        return provider_detail()

    async def send(*args, **kwargs):
        calls.append(args)
        return {}

    monkeypatch.setattr(application.paypal, "detail", detail)
    monkeypatch.setattr(application.paypal, "request", send)
    monkeypatch.setenv("VERDICT_ALLOW_SANDBOX_ACTIONS", "true")
    plan = env.post(
        "/api/cases/" + body["id"] + "/actions/prepare",
        json={"action": "send-message", "note": "Human-reviewed note"},
    ).json()
    params = {
        "approval_id": plan["approval"]["id"],
        "reviewed_digest": "modified",
        "confirmed": True,
    }
    assert (
        env.post(
            "/api/cases/" + body["id"] + "/actions/execute", json=params
        ).status_code
        == 409
    )
    params["reviewed_digest"] = plan["digest"]
    store.save(body, "operator", "evidence_changed", {})
    assert (
        env.post(
            "/api/cases/" + body["id"] + "/actions/execute", json=params
        ).status_code
        == 409
    )
    assert not calls


@pytest.mark.parametrize("uncertain", [False, True])
def test_paypal_dispatch_not_retried_and_unknown_blocks_other_approval(
    env, monkeypatch, uncertain
):
    login(env)
    body = case_for_actions()
    calls = []

    async def detail(id):
        return provider_detail()

    async def send(*args, **kwargs):
        calls.append(args)
        if uncertain:
            raise PayPalError("network_error", True)
        return {}

    monkeypatch.setattr(application.paypal, "detail", detail)
    monkeypatch.setattr(application.paypal, "request", send)
    monkeypatch.setenv("VERDICT_ALLOW_SANDBOX_ACTIONS", "true")
    path = "/api/cases/" + body["id"] + "/actions/"
    plan = env.post(
        path + "prepare", json={"action": "send-message", "note": "Reviewed note"}
    ).json()
    data = {
        "approval_id": plan["approval"]["id"],
        "reviewed_digest": plan["digest"],
        "confirmed": True,
    }
    assert env.post(path + "execute", json=data).json()["status"] == (
        "unknown" if uncertain else "succeeded"
    )
    env.post(path + "execute", json=data)
    assert len(calls) == 1
    plan2 = env.post(
        path + "prepare", json={"action": "send-message", "note": "Reviewed note"}
    ).json()
    data.update(approval_id=plan2["approval"]["id"], reviewed_digest=plan2["digest"])
    assert env.post(path + "execute", json=data).status_code == 409
    assert len(calls) == 1


def test_webhook_fails_closed_without_signature(env):
    assert env.post("/api/webhooks/paypal", json={"id": "fake"}).status_code == 401


def test_verified_webhook_duplicate_is_not_reimported(env, monkeypatch):
    calls = []

    async def verify(*args):
        return True

    async def detail(id):
        calls.append(id)
        return provider_detail()

    monkeypatch.setattr(application.paypal, "verify", verify)
    monkeypatch.setattr(application.paypal, "detail", detail)
    event = {
        "id": "WH-TEST",
        "event_type": "CUSTOMER.DISPUTE.CREATED",
        "resource": {"dispute_id": "PP-D-TEST"},
    }
    assert env.post("/api/webhooks/paypal", json=event).status_code == 200
    assert env.post("/api/webhooks/paypal", json=event).json()["duplicate"]
    assert len(calls) == 1


@pytest.mark.parametrize(
    "status,uncertain", [(408, True), (409, True), (422, False), (503, True)]
)
def test_ambiguous_http_write_responses_are_not_treated_as_definite_rejection(
    monkeypatch, status, uncertain
):
    import httpx
    from paypal import PayPal

    original = httpx.AsyncClient
    transport = httpx.MockTransport(
        lambda request: httpx.Response(status, json={"name": "TEST_RESPONSE"})
    )
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: original(transport=transport, **kwargs)
    )
    adapter = PayPal()
    adapter.token = "test-token-not-real"
    adapter.expires = time.time() + 100
    with pytest.raises(PayPalError) as error:
        asyncio.run(
            adapter.request(
                "POST",
                "/v1/customer/disputes/PP-D-TEST/send-message",
                payload={"message": "test"},
            )
        )
    assert error.value.uncertain is uncertain


def test_overlapping_approvals_dispatch_only_once(env, monkeypatch):
    body = case_for_actions()
    calls = []
    monkeypatch.setenv("VERDICT_ALLOW_SANDBOX_ACTIONS", "true")

    async def detail(id):
        await asyncio.sleep(0.01)
        return provider_detail()

    async def send(*args, **kwargs):
        calls.append(args)
        await asyncio.sleep(0.04)
        return {}

    monkeypatch.setattr(application.paypal, "detail", detail)
    monkeypatch.setattr(application.paypal, "request", send)

    async def scenario():
        plan = await application.prepare(
            body["id"],
            ActionInput(action="send-message", note="Reviewed test"),
            {"tenant": "operator", "role": "operator"},
        )
        data = ExecuteInput(
            approval_id=plan["approval"]["id"],
            reviewed_digest=plan["digest"],
            confirmed=True,
        )
        return await asyncio.gather(
            application.execute(
                body["id"], data, {"tenant": "operator", "role": "operator"}
            ),
            application.execute(
                body["id"], data, {"tenant": "operator", "role": "operator"}
            ),
            return_exceptions=True,
        )

    results = asyncio.run(scenario())
    assert len(calls) == 1
    assert any(isinstance(r, dict) and r.get("status") == "succeeded" for r in results)
