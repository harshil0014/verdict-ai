import os, json, time, secrets, hashlib, io, asyncio, subprocess, sys
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
from contextlib import asynccontextmanager
from fastapi import (
    FastAPI,
    Request,
    Response,
    HTTPException,
    Depends,
    UploadFile,
    File,
    Form,
)
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pypdf import PdfReader
import store
from store import now, uid, digest, canon, connect
from domain import EvidenceInput, CaseInput, AnalyzeInput, ActionInput, ExecuteInput
from investigator import investigate, ModelError, MODEL
from fixtures import seed, evidence
from paypal import client as paypal, PayPalError, allowed
import cloud

BOOTSTRAP = secrets.token_urlsafe(32)
bootstrap_used = False
LOGIN_FAILURES = {}
MODEL_LOCK = asyncio.Semaphore(1)
MAX_FILE = 5 * 1024 * 1024


@asynccontextmanager
async def lifespan(app):
    store.init()
    if not store.listing("operator"):
        seed("operator", store.create)
    cloud.seed_outbox()

    async def mirror_worker():
        while True:
            await asyncio.to_thread(cloud.flush_one)
            await asyncio.sleep(3)

    mirror_task = asyncio.create_task(mirror_worker())
    # Private local operator handoff. Never emitted to logs or checked into Git.
    if os.getenv("VERDICT_LOCAL_BOOTSTRAP") == "true":
        (store.RUNTIME / "local-access.url").write_text(
            "http://127.0.0.1:8000/#bootstrap=" + BOOTSTRAP
        )
    yield
    mirror_task.cancel()


app = FastAPI(
    title="VERDICT", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan
)


@app.middleware("http")
async def security(request, call_next):
    # Same-origin JSON endpoints, including login, prevent CSRF and DNS rebinding.
    host = request.headers.get("host", "")
    configured = os.getenv("VERDICT_PUBLIC_HOST", "")
    allowed_hosts = {"127.0.0.1:8000", "localhost:8000", "testserver"}
    if configured:
        allowed_hosts.add(configured)
    if host not in allowed_hosts:
        return JSONResponse({"detail": "Host is not allowed"}, 400)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and origin not in {
            f"http://{host}",
            f"https://{host}",
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        }:
            return JSONResponse({"detail": "Cross-origin request refused"}, 403)
        size = request.headers.get("content-length")
        if size and (not size.isdigit() or int(size) > MAX_FILE + 100000):
            return JSONResponse({"detail": "Request is too large"}, 413)
    result = await call_next(request)
    result.headers["X-Content-Type-Options"] = "nosniff"
    result.headers["Referrer-Policy"] = "no-referrer"
    result.headers["X-Frame-Options"] = "DENY"
    result.headers["Cache-Control"] = (
        "no-store" if request.url.path.startswith("/api") else "no-cache"
    )
    result.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    return result


@app.exception_handler(KeyError)
async def missing(req, e):
    return JSONResponse({"detail": "Record not found"}, 404)


@app.exception_handler(ValueError)
async def conflict(req, e):
    return JSONResponse({"detail": str(e)}, 409)


@app.exception_handler(ModelError)
async def modelerror(req, e):
    return JSONResponse({"detail": str(e)}, 502)


@app.exception_handler(PayPalError)
async def providererror(req, e):
    return JSONResponse({"detail": str(e), "uncertain": e.uncertain}, 502)


def session(request: Request):
    token = request.cookies.get("verdict_session", "")
    with connect() as c:
        row = c.execute(
            "SELECT * FROM sessions WHERE hash=? AND expires>?",
            (hashlib.sha256(token.encode()).hexdigest(), time.time()),
        ).fetchone()
    if not row:
        raise HTTPException(401, "Sign in to continue")
    return dict(row)


def operator(s=Depends(session)):
    if s["role"] != "operator":
        raise HTTPException(403, "Operator authorization required")
    return s


def new_session(response, tenant, role):
    token = secrets.token_urlsafe(32)
    with connect() as c:
        c.execute(
            "INSERT INTO sessions VALUES(?,?,?,?)",
            (
                hashlib.sha256(token.encode()).hexdigest(),
                tenant,
                role,
                time.time() + 8 * 3600,
            ),
        )
        c.commit()
    response.set_cookie(
        "verdict_session",
        token,
        httponly=True,
        samesite="strict",
        secure=os.getenv("VERDICT_SECURE_COOKIES") == "true",
        max_age=8 * 3600,
        path="/",
    )
    return {"tenant": tenant, "role": role, "model": MODEL}


class Login(BaseModel):
    password: str = Field(default="", max_length=200)
    bootstrap: str = Field(default="", max_length=200)


@app.post("/api/auth/login")
def login(data: Login, request: Request, response: Response):
    global bootstrap_used
    ip = request.client.host if request.client else "unknown"
    recent = [t for t in LOGIN_FAILURES.get(ip, []) if t > time.time() - 300]
    if len(recent) >= 8:
        raise HTTPException(429, "Too many attempts. Try again in five minutes.")
    local_boot = (
        os.getenv("VERDICT_LOCAL_BOOTSTRAP") == "true"
        and ip in ("127.0.0.1", "::1", "testclient")
        and data.bootstrap
        and not bootstrap_used
        and secrets.compare_digest(data.bootstrap, BOOTSTRAP)
    )
    configured = os.getenv("VERDICT_OPERATOR_PASSWORD", "")
    password_ok = (
        len(configured) >= 16
        and data.password
        and secrets.compare_digest(data.password, configured)
    )
    if not local_boot and not password_ok:
        LOGIN_FAILURES[ip] = recent + [time.time()]
        raise HTTPException(401, "Invalid credentials")
    if local_boot:
        bootstrap_used = True
    if local_boot:
        (store.RUNTIME / "local-access.url").unlink(missing_ok=True)
    return new_session(response, "operator", "operator")


class DemoLogin(BaseModel):
    code: str = Field(default="", max_length=200)


@app.post("/api/auth/demo")
def demo(response: Response, data: DemoLogin = DemoLogin()):
    if os.getenv("VERDICT_DISABLE_DEMO") == "true":
        raise HTTPException(403, "Demo sessions are disabled on this instance")
    code = os.getenv("VERDICT_DEMO_ACCESS_CODE", "")
    if os.getenv("VERDICT_PUBLIC_HOST") and (
        len(code) < 16 or not secrets.compare_digest(data.code, code)
    ):
        raise HTTPException(
            403,
            "This hosted demo requires a judge access code. Use operator access or obtain the code from the project owner.",
        )
    tenant = uid("demo-")
    seed(tenant, store.create)
    return new_session(response, tenant, "demo")


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    with connect() as c:
        c.execute(
            "DELETE FROM sessions WHERE hash=?",
            (
                hashlib.sha256(
                    request.cookies.get("verdict_session", "").encode()
                ).hexdigest(),
            ),
        )
        c.commit()
    response.delete_cookie("verdict_session")
    return {"ok": True}


@app.get("/api/me")
def me(s=Depends(session)):
    return {
        "role": s["role"],
        "tenant": s["tenant"],
        "model": MODEL,
        "sandbox_actions_enabled": os.getenv("VERDICT_ALLOW_SANDBOX_ACTIONS") == "true",
        "cloud": cloud.status() if s["role"] == "operator" else None,
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "VERDICT", "environment": "sandbox-only"}


@app.get("/api/cases")
def cases(s=Depends(session)):
    return store.listing(s["tenant"])


@app.post("/api/cases")
def create_case(data: CaseInput, s=Depends(session)):
    return store.create(
        s["tenant"],
        {
            **data.model_dump(),
            "mode": "manual",
            "status": "OPEN",
            "deadline": None,
            "story": "User-created case. Sources are reported statements until assessed.",
        },
    )


@app.get("/api/cases/{id}")
def case(id: str, s=Depends(session)):
    body = store.get(id, s["tenant"])
    rows = store.timeline(id)
    return {**body, "timeline": rows, "audit_valid": store.verify_timeline(rows)}


def add_evidence(body, tenant, data, raw=None, mime="text/plain", request_row=None):
    if len(body["evidence"]) >= 40:
        raise HTTPException(422, "Maximum 40 evidence sources per case")
    item = evidence(
        data.title,
        data.text,
        data.party,
        "portal_upload" if request_row else "operator_upload",
    )
    item.update(
        synthetic=body["mode"] == "synthetic",
        mime=mime,
        sha256=digest(raw if raw is not None else data.text.encode()),
        file_available=raw is not None,
    )
    body["evidence"].append(item)
    if request_row:
        for req in body["requests"]:
            if req["id"] == json.loads(request_row["body"])["id"]:
                req.update(status="received", received_at=now(), evidence_id=item["id"])
    body["analysis_stale"] = body.get("analysis") is not None

    def extra(c):
        if raw is not None:
            c.execute(
                "INSERT INTO files VALUES(?,?,?,?,?,?)",
                (item["id"], body["id"], tenant, raw, mime, data.title),
            )
        if request_row:
            r = c.execute(
                "UPDATE requests SET completed=1 WHERE hash=? AND completed=0 AND expires>?",
                (request_row["hash"], time.time()),
            )
            if r.rowcount != 1:
                raise ValueError("Request was already answered or expired")

    return store.save(
        body,
        tenant,
        "evidence_received",
        {
            "evidence_id": item["id"],
            "title": item["title"],
            "sha256": item["sha256"],
            "party": item["party"],
            "origin_verified": False,
        },
        extra=extra,
    )


@app.post("/api/cases/{id}/evidence")
def text_evidence(id: str, data: EvidenceInput, s=Depends(session)):
    return add_evidence(store.get(id, s["tenant"]), s["tenant"], data)


async def extract_file(file):
    raw = await file.read(MAX_FILE + 1)
    if len(raw) > MAX_FILE:
        raise HTTPException(413, "File exceeds 5 MB")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".txt", ".json", ".pdf"):
        raise HTTPException(
            415,
            "Use TXT, JSON, or a text-bearing PDF. Images and executable files are not accepted.",
        )
    mime = "text/plain"
    try:
        if suffix == ".pdf":

            def parse():
                result = subprocess.run(
                    [sys.executable, str(Path(__file__).parent / "parse_pdf.py")],
                    input=raw,
                    capture_output=True,
                    timeout=12,
                )
                if result.returncode != 0:
                    raise ValueError("PDF extraction failed")
                return json.loads(result.stdout)["text"]

            text = await asyncio.to_thread(parse)
            mime = "application/pdf"
        else:
            text = raw.decode("utf-8-sig")
            mime = "application/json" if suffix == ".json" else "text/plain"
            if suffix == ".json":
                json.loads(text)
        if "\x00" in text or len(text) > 30000 or not text.strip():
            raise ValueError("Empty, binary, or over 30,000 extracted characters")
    except Exception:
        raise HTTPException(
            422,
            "Could not safely parse this file. Use UTF-8 text or an unencrypted text-bearing PDF of at most 30 pages and 30,000 characters.",
        ) from None
    return raw, text, mime


@app.post("/api/cases/{id}/upload")
async def upload(
    id: str,
    file: UploadFile = File(...),
    party: Literal["buyer", "seller", "carrier", "payment_provider", "other"] = Form(
        "seller"
    ),
    s=Depends(session),
):
    body = store.get(id, s["tenant"])
    raw, text, mime = await extract_file(file)
    data = EvidenceInput(
        title=Path(file.filename or "Document").name, text=text, party=party
    )
    return add_evidence(body, s["tenant"], data, raw, mime)


@app.get("/api/cases/{id}/files/{file_id}")
def download(id: str, file_id: str, s=Depends(session)):
    store.get(id, s["tenant"])
    with connect() as c:
        row = c.execute(
            "SELECT * FROM files WHERE id=? AND case_id=? AND tenant=?",
            (file_id, id, s["tenant"]),
        ).fetchone()
    if not row:
        raise KeyError("File not found")
    return Response(
        row["content"],
        media_type=row["mime"],
        headers={"Content-Disposition": "attachment; filename=evidence"},
    )


@app.post("/api/cases/{id}/analyze")
async def analyze(id: str, data: AnalyzeInput, s=Depends(session)):
    body = store.get(id, s["tenant"])
    if not data.consent:
        raise HTTPException(
            422, "Confirm that this evidence may be sent to Gemini for analysis."
        )
    if not body["evidence"]:
        raise HTTPException(422, "Add evidence before investigating")
    with connect() as c:
        n = c.execute(
            "SELECT count(*) FROM audit a JOIN cases b ON a.case_id=b.id WHERE b.tenant=? AND a.kind='investigation_updated'",
            (s["tenant"],),
        ).fetchone()[0]
    if s["role"] == "demo" and n >= 8:
        raise HTTPException(
            429, "This demo workspace has reached its eight-analysis limit"
        )
    async with MODEL_LOCK:
        result = await investigate(body)
    prior = body.get("analysis")
    if prior:
        result["change"] = {
            "previous_finding": prior["finding"],
            "current_finding": result["finding"],
            "previous_claims": len(prior["claims"]),
            "current_claims": len(result["claims"]),
            "new_source_ids": [
                e["id"]
                for e in body["evidence"]
                if e["id"] not in {c["source_id"] for c in prior["claims"]}
            ],
        }
    body.update(analysis=result, analysis_stale=False)
    return store.save(
        body,
        s["tenant"],
        "investigation_updated",
        {
            "finding": result["finding"],
            "input_digest": result["input_digest"],
            "model": result["model"],
            "analysis": result,
        },
    )


class RequestInput(BaseModel):
    witness_id: str = Field(max_length=100)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    question: str | None = Field(default=None, min_length=1, max_length=1000)
    recipient: (
        Literal["buyer", "seller", "carrier", "payment_provider", "other"] | None
    ) = None


@app.post("/api/cases/{id}/requests")
def make_request(id: str, data: RequestInput, s=Depends(session)):
    body = store.get(id, s["tenant"])
    if not body.get("analysis") or body.get("analysis_stale"):
        raise HTTPException(
            409, "Investigate the latest evidence before creating a request"
        )
    witness = next(
        (w for w in body["analysis"]["requests"] if w["id"] == data.witness_id), None
    )
    if not witness:
        raise KeyError("Witness not found")
    original = dict(witness)
    witness = {
        **witness,
        **{
            k: v
            for k, v in data.model_dump().items()
            if k in ("title", "question", "recipient") and v is not None
        },
    }
    if any(
        r["question"] == witness["question"] and r["status"] == "open"
        for r in body["requests"]
    ):
        raise HTTPException(409, "This request is already open")
    token = secrets.token_urlsafe(32)
    hashed = hashlib.sha256(token.encode()).hexdigest()
    req = {
        **witness,
        "id": uid("R-"),
        "created_at": now(),
        "status": "open",
        "expires_at": time.time() + 7 * 86400,
    }
    body["requests"].append(req)

    def extra(c):
        c.execute(
            "INSERT INTO requests(hash,case_id,tenant,body,expires) VALUES(?,?,?,?,?)",
            (hashed, id, s["tenant"], canon(req), req["expires_at"]),
        )

    body = store.save(
        body,
        s["tenant"],
        "witness_requested",
        {
            "request_id": req["id"],
            "question": req["question"],
            "recipient": req["recipient"],
            "model_proposal": original,
            "human_edited": any(
                witness[k] != original[k] for k in ("title", "question", "recipient")
            ),
        },
        extra=extra,
    )
    return {
        "request": req,
        "portal_fragment": "#request=" + token,
        "case": body,
        "delivery": "Link created locally. No email or notification was sent. Share only with the intended recipient.",
    }


def portal_token(request):
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Request token required")
    token = auth[7:]
    with connect() as c:
        row = c.execute(
            "SELECT * FROM requests WHERE hash=? AND expires>?",
            (hashlib.sha256(token.encode()).hexdigest(), time.time()),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Request expired or unavailable")
    if row["completed"]:
        raise HTTPException(409, "This request has already been answered")
    return dict(row)


@app.get("/api/portal")
def portal(request: Request):
    row = portal_token(request)
    req = json.loads(row["body"])
    return {k: req[k] for k in ["id", "title", "question", "recipient", "expires_at"]}


@app.post("/api/portal")
def portal_reply(request: Request, data: EvidenceInput):
    row = portal_token(request)
    req = json.loads(row["body"])
    # The token's intended recipient determines submitter role, never the client.
    data.party = req["recipient"]
    add_evidence(
        store.get(row["case_id"], row["tenant"]), row["tenant"], data, request_row=row
    )
    return {
        "ok": True,
        "message": "Evidence received for investigator review. Origin and factual truth have not been independently verified.",
    }


@app.post("/api/portal/upload")
async def portal_upload(request: Request, file: UploadFile = File(...)):
    row = portal_token(request)
    req = json.loads(row["body"])
    raw, text, mime = await extract_file(file)
    data = EvidenceInput(
        title=Path(file.filename or "Document").name, text=text, party=req["recipient"]
    )
    add_evidence(
        store.get(row["case_id"], row["tenant"]), row["tenant"], data, raw, mime, row
    )
    return {"ok": True}


@app.get("/api/cases/{id}/export")
def export(id: str, s=Depends(session)):
    body = case(id, s)
    return Response(
        json.dumps(body, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="verdict-{id}.json"'},
    )


@app.get("/api/integrations")
async def integrations(s=Depends(operator)):
    details = await paypal.disputes()
    return {
        "paypal": {
            "environment": "sandbox",
            "list_status": 200,
            "disputes": len(details),
        },
        "gemini": {"model": MODEL, "configured": bool(os.getenv("GEMINI_API_KEY"))},
        "storage": cloud.status(),
        "webhook": {"configured": bool(os.getenv("PAYPAL_WEBHOOK_ID"))},
    }


async def import_dispute(detail):
    id = detail["dispute_id"]
    existing = next(
        (b for b in store.listing("operator") if b.get("paypal_id") == id), None
    )
    ev = evidence(
        "PayPal sandbox dispute record",
        json.dumps(detail, indent=2),
        "payment_provider",
        "paypal_sandbox_api",
    )
    ev["origin_verified"] = True
    ev["synthetic"] = False
    if existing:
        if existing.get("paypal_snapshot") == detail:
            return existing
        existing["evidence"].append(ev)
        existing.update(
            paypal_snapshot=detail,
            status=detail.get("status", "UNKNOWN"),
            analysis_stale=bool(existing.get("analysis")),
        )
        return store.save(existing, "operator", "paypal_refreshed", {"provider_id": id})
    amount = detail.get("dispute_amount", {})
    return store.create(
        "operator",
        {
            "title": "PayPal · " + id,
            "paypal_id": id,
            "mode": "paypal_sandbox",
            "status": detail.get("status", "UNKNOWN"),
            "reason": detail.get("reason", "OTHER"),
            "amount": amount.get("value", "0.00"),
            "currency": amount.get("currency_code", "USD"),
            "deadline": detail.get("seller_response_due_date"),
            "paypal_snapshot": detail,
            "evidence": [ev],
            "story": "Retrieved from PayPal sandbox. API origin is verified; the truth of party statements is not.",
        },
    )


@app.post("/api/paypal/sync")
async def sync(s=Depends(operator)):
    rows = await paypal.disputes()
    imported = []
    for r in rows:
        imported.append(await import_dispute(await paypal.detail(r["dispute_id"])))
    return {
        "listed": len(rows),
        "imported": len(imported),
        "environment": "sandbox",
        "message": "No sandbox disputes available. No fictional PayPal case was substituted."
        if not rows
        else "Sandbox cases synchronized",
    }


@app.post("/api/cases/{id}/paypal/refresh")
async def refresh(id: str, s=Depends(operator)):
    body = store.get(id, s["tenant"])
    if not body.get("paypal_id"):
        raise HTTPException(422, "This case is not linked to PayPal")
    return await import_dispute(await paypal.detail(body["paypal_id"]))


@app.post("/api/cases/{id}/paypal/link-payment")
async def link_payment(id: str, s=Depends(operator)):
    body = store.get(id, s["tenant"])
    if not body.get("paypal_id"):
        raise HTTPException(422, "This case is not linked to PayPal")
    current = await paypal.detail(body["paypal_id"])
    linked = []
    for tx in current.get("disputed_transactions", [])[:10]:
        capture = tx.get("seller_transaction_id")
        if not capture or not capture.isalnum():
            continue
        try:
            record = await paypal.request("GET", "/v2/payments/captures/" + capture)
            linked.append(
                evidence(
                    "PayPal capture " + capture,
                    json.dumps(record, indent=2),
                    "payment_provider",
                    "paypal_sandbox_api",
                )
            )
            order = (
                record.get("supplementary_data", {})
                .get("related_ids", {})
                .get("order_id")
            )
            if order and order.isalnum():
                linked.append(
                    evidence(
                        "PayPal order " + order,
                        json.dumps(
                            await paypal.request("GET", "/v2/checkout/orders/" + order),
                            indent=2,
                        ),
                        "payment_provider",
                        "paypal_sandbox_api",
                    )
                )
        except PayPalError:
            continue
    if not linked:
        raise HTTPException(
            422,
            "No accessible capture or order was linked. PayPal permissions or transaction type may limit retrieval.",
        )
    for ev in linked:
        ev.update(origin_verified=True, synthetic=False)
    body["evidence"].extend(linked)
    body["analysis_stale"] = bool(body.get("analysis"))
    return store.save(
        body,
        s["tenant"],
        "payment_records_linked",
        {"source_ids": [e["id"] for e in linked]},
    )


@app.post("/api/cases/{id}/actions/prepare")
async def prepare(id: str, data: ActionInput, s=Depends(operator)):
    body = store.get(id, s["tenant"])
    if body["mode"] != "paypal_sandbox":
        raise HTTPException(422, "Fictional/manual cases cannot send PayPal actions")
    detail = await paypal.detail(body["paypal_id"])
    if data.action not in allowed(detail):
        raise HTTPException(409, "PayPal does not currently offer this action")
    if not body.get("analysis") or body.get("analysis_stale"):
        raise HTTPException(409, "Review an investigation of the latest evidence first")
    payload = (
        {"message": data.note} if data.action == "send-message" else {"note": data.note}
    )
    if data.action == "provide-evidence":
        if not data.carrier or not data.tracking_number:
            raise HTTPException(
                422, "Review and supply the actual carrier and tracking number"
            )
        payload = {
            "evidences": [
                {
                    "evidence_type": "PROOF_OF_FULFILLMENT",
                    "evidence_info": {
                        "tracking_info": [
                            {
                                "carrier_name": data.carrier,
                                "tracking_number": data.tracking_number,
                            }
                        ]
                    },
                    "notes": data.note,
                }
            ]
        }
    record = {
        "id": uid("A-"),
        "case_id": id,
        "paypal_id": body["paypal_id"],
        "revision": body["revision"],
        "action": data.action,
        "payload": payload,
        "provider_digest": digest(detail),
        "evidence_digest": digest(body["evidence"]),
        "approver": s["tenant"],
        "expires": time.time() + 600,
    }
    hashed = digest(record)
    with connect() as c:
        c.execute(
            "INSERT INTO approvals VALUES(?,?,?,?,?,?,?)",
            (
                record["id"],
                id,
                s["tenant"],
                hashed,
                canon(record),
                "prepared",
                record["expires"],
            ),
        )
        c.commit()
    return {
        "approval": record,
        "digest": hashed,
        "warning": "Sandbox action only. Accept claim can trigger a sandbox refund. Review this exact payload; approval expires in ten minutes.",
    }


@app.post("/api/cases/{id}/actions/execute")
async def execute(id: str, data: ExecuteInput, s=Depends(operator)):
    if os.getenv("VERDICT_ALLOW_SANDBOX_ACTIONS") != "true":
        raise HTTPException(
            403,
            "Sandbox writes are disabled. Enable VERDICT_ALLOW_SANDBOX_ACTIONS only after reviewing the integration.",
        )
    if not data.confirmed:
        raise HTTPException(422, "Explicit approval required")
    with connect() as c:
        row = c.execute(
            "SELECT * FROM approvals WHERE id=? AND case_id=? AND tenant=?",
            (data.approval_id, id, s["tenant"]),
        ).fetchone()
    if not row:
        raise KeyError("Approval not found")
    rec = json.loads(row["body"])
    body = store.get(id, s["tenant"])
    if (
        row["digest"] != data.reviewed_digest
        or digest(rec) != row["digest"]
        or row["expires"] <= time.time()
    ):
        raise HTTPException(409, "Approval expired or changed")
    if row["status"] != "prepared":
        return {
            "status": row["status"],
            "message": "Already reserved or dispatched. Never retry an unknown outcome.",
        }
    if (
        body["revision"] != rec["revision"]
        or digest(body["evidence"]) != rec["evidence_digest"]
    ):
        raise HTTPException(409, "Case changed since review")
    detail = await paypal.detail(rec["paypal_id"])
    if digest(detail) != rec["provider_digest"] or rec["action"] not in allowed(detail):
        raise HTTPException(409, "PayPal state changed since review")
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        live = c.execute(
            "SELECT revision FROM cases WHERE id=? AND tenant=?", (id, s["tenant"])
        ).fetchone()
        prior = c.execute(
            "SELECT status,body FROM approvals WHERE case_id=? AND status IN ('dispatching','unknown','succeeded')",
            (id,),
        ).fetchall()
        busy = any(
            p["status"] in ("dispatching", "unknown")
            or all(
                json.loads(p["body"]).get(k) == rec.get(k)
                for k in ("provider_digest", "evidence_digest", "action", "payload")
            )
            for p in prior
        )
        if live["revision"] != rec["revision"] or busy:
            raise HTTPException(
                409, "Case changed or another action needs reconciliation"
            )
        r = c.execute(
            "UPDATE approvals SET status='dispatching' WHERE id=? AND status='prepared'",
            (rec["id"],),
        )
        if r.rowcount != 1:
            raise HTTPException(409, "Action already reserved")
        store.audit(
            c,
            id,
            "action_approved",
            {
                "approval_id": rec["id"],
                "digest": row["digest"],
                "payload": rec["payload"],
                "action": rec["action"],
            },
        )
        c.commit()
    status = "unknown"
    try:
        files = (
            {"input": (None, json.dumps(rec["payload"]), "application/json")}
            if rec["action"] == "provide-evidence"
            else None
        )
        await paypal.request(
            "POST",
            f"/v1/customer/disputes/{rec['paypal_id']}/{rec['action']}",
            payload=rec["payload"],
            files=files,
            key=rec["id"],
        )
        status = "succeeded"
    except PayPalError as e:
        status = "unknown" if e.uncertain else "rejected"
    finally:
        with connect() as c:
            c.execute("UPDATE approvals SET status=? WHERE id=?", (status, rec["id"]))
            store.audit(
                c,
                id,
                "paypal_action_result",
                {"approval_id": rec["id"], "status": status},
            )
            c.commit()
    return {
        "status": status,
        "message": "Check PayPal before any further action if status is unknown. No automatic retry is performed.",
    }


@app.post("/api/webhooks/paypal")
async def webhook(request: Request):
    raw = await request.body()
    if len(raw) > 500000:
        raise HTTPException(413, "Webhook too large")
    if not await paypal.verify(request.headers, raw):
        raise HTTPException(
            401, "Webhook verification failed or PAYPAL_WEBHOOK_ID is missing"
        )
    try:
        event = json.loads(raw)
    except Exception:
        raise HTTPException(422, "Invalid JSON") from None
    event_id = event.get("id")
    dispute_id = event.get("resource", {}).get("dispute_id")
    if (
        not event_id
        or not dispute_id
        or not str(event.get("event_type", "")).startswith("CUSTOMER.DISPUTE.")
    ):
        raise HTTPException(422, "Unsupported webhook event")
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        previous = c.execute(
            "SELECT status FROM webhooks WHERE id=?", (event_id,)
        ).fetchone()
        if previous and previous["status"] in ("processing", "completed"):
            return {"duplicate": True}
        c.execute(
            "INSERT OR REPLACE INTO webhooks VALUES(?,?)", (event_id, "processing")
        )
        c.commit()
    try:
        await import_dispute(await paypal.detail(dispute_id))
        with connect() as c:
            c.execute("UPDATE webhooks SET status='completed' WHERE id=?", (event_id,))
            c.commit()
    except Exception:
        with connect() as c:
            c.execute("UPDATE webhooks SET status='failed' WHERE id=?", (event_id,))
            c.commit()
        raise
    return {"ok": True}


DIST = Path(__file__).resolve().parents[1] / "frontend/dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/")
def index():
    if not (DIST / "index.html").exists():
        return JSONResponse(
            {"detail": "Frontend not built. Run npm ci and npm run build in frontend."},
            503,
        )
    return FileResponse(DIST / "index.html")
