"""Persistent multi-user application; the legacy operator app is recoverable separately."""
import asyncio
import base64
from contextlib import asynccontextmanager
import hashlib
import json
import os
from pathlib import Path
import secrets
import time
from typing import Literal
from urllib.parse import quote
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict
from domain import CaseInput, EvidenceInput, AnalyzeInput
from evidence_io import extract_file
from fixtures import evidence
import investigator
from investigator import investigate, ModelError, MODEL
from saas_store import repo, SESSION
import saas_auth as auth
from store import digest, now, uid
from web_security import guard, BoundedBodyMiddleware
from research_routes import router as research_router


async def cloud_slot():
    slot = await repo.rpc("model_slot", {"model": MODEL})
    await asyncio.sleep(float(slot["wait_seconds"]))


@asynccontextmanager
async def lifespan(app):
    await repo.start()
    previous = investigator.SLOT_RESERVER
    investigator.SLOT_RESERVER = cloud_slot
    try:
        yield
    finally:
        investigator.SLOT_RESERVER = previous
        await repo.close()


app = FastAPI(title="VERDICT", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(research_router)


@app.middleware("http")
async def security(request, call_next):
    token = SESSION.set("")
    try:
        return await guard(request, call_next)
    finally:
        SESSION.reset(token)


app.add_middleware(BoundedBodyMiddleware)


@app.exception_handler(RequestValidationError)
async def invalid_input(request, error):
    return JSONResponse({"detail": "; ".join(str(e["msg"]) for e in error.errors())}, 422)


@app.exception_handler(ModelError)
async def model_error(request, error):
    return JSONResponse({"detail": str(error)}, 502)


@app.get("/api/config")
def config():
    return {"auth_mode": "account", "storage": "postgres", "signup": True, "paypal": "sandbox_operator_build_only"}


@app.get("/api/health")
async def health():
    result = await repo.rpc("health", session="")
    return {"status": "ok", "service": "VERDICT", "environment": "private-user-workspaces", **result}


@app.post("/api/auth/register")
async def register(data: auth.Registration, request: Request, response: Response):
    return await auth.register(data, request, response)


@app.post("/api/auth/login")
async def login(data: auth.Credentials, request: Request, response: Response):
    return await auth.login(data, request, response)


@app.post("/api/auth/recover")
async def recover(data: auth.Recovery, request: Request, response: Response):
    return await auth.recover(data, request, response)


@app.post("/api/auth/logout")
async def logout(response: Response, user=Depends(auth.current_session)):
    await repo.rpc("logout")
    response.delete_cookie(auth.COOKIE, path="/")
    return {"ok": True}


@app.get("/api/me")
async def me(user=Depends(auth.current_session)):
    return {"role": "member", "tenant": user["id"], "user": user, "model": MODEL,
        "sandbox_actions_enabled": False, "ephemeral_storage": False, "storage": "postgres",
        "quotas": {"storage_bytes": 20971520, "cases": 50, "analyses_per_day": 10}}


@app.get("/api/cases")
async def cases(user=Depends(auth.current_session)):
    return await repo.rpc("list")


@app.post("/api/cases")
async def create_case(data: CaseInput, user=Depends(auth.current_session)):
    return await repo.create({**data.model_dump(), "mode": "manual", "status": "OPEN", "deadline": None,
        "story": "User-created case. Statements and uploads require assessment.", "evidence": []})


@app.get("/api/cases/{id}")
async def get_case(id: str, user=Depends(auth.current_session)):
    return await repo.get(id)


def add_source(body, data, raw=None, mime="text/plain", request_row=None):
    if len(body["evidence"]) >= 40: raise HTTPException(422, "Maximum 40 evidence sources per case")
    if "\x00" in data.text: raise HTTPException(422, "Null bytes are not supported")
    source = evidence(data.title, data.text, data.party, "portal_upload" if request_row else "user_upload")
    source.update(synthetic=False, mime=mime, sha256=digest(raw if raw is not None else data.text.encode()), file_available=raw is not None)
    body["evidence"].append(source)
    if request_row:
        for request in body["requests"]:
            if request["id"] == request_row["id"]:
                request.update(status="received", received_at=now(), evidence_id=source["id"])
    body["analysis_stale"] = body.get("analysis") is not None
    original = repo.file_record(source["id"], raw, mime, data.title) if raw is not None else None
    event = {"evidence_id": source["id"], "title": source["title"], "sha256": source["sha256"], "party": source["party"], "origin_verified": False}
    return event, original


@app.post("/api/cases/{id}/evidence")
async def text_evidence(id: str, data: EvidenceInput, user=Depends(auth.current_session)):
    body = await repo.get(id)
    event, original = add_source(body, data)
    return await repo.save(body, "evidence_received", event)


@app.post("/api/cases/{id}/upload")
async def upload(id: str, file: UploadFile=File(...), party: Literal["buyer","seller","carrier","payment_provider","other"]=Form("seller"), user=Depends(auth.current_session)):
    body = await repo.get(id)
    raw, text, mime = await extract_file(file)
    data = EvidenceInput(title=Path(file.filename or "Evidence").name[:160], text=text, party=party)
    event, original = add_source(body, data, raw, mime)
    return await repo.save(body, "evidence_received", event, file=original)


@app.get("/api/cases/{id}/files/{file_id}")
async def download(id: str, file_id: str, user=Depends(auth.current_session)):
    record = await repo.rpc("file", {"case_id": id, "file_id": file_id})
    raw = base64.b64decode(record["content"])
    if hashlib.sha256(raw).hexdigest() != record["sha256"]: raise HTTPException(503, "The stored file failed its integrity check")
    filename = quote(record['name'], safe='')
    return Response(raw, media_type=record["mime"], headers={"Content-Disposition": "attachment; filename=evidence; filename*=UTF-8''"+filename})


@app.post("/api/cases/{id}/analyze")
async def analyze(id: str, data: AnalyzeInput, user=Depends(auth.current_session)):
    if not data.consent: raise HTTPException(422, "Confirm that these records may be sent to Gemini for analysis")
    body = await repo.get(id)
    if not body["evidence"]: raise HTTPException(422, "Add evidence before investigating")
    job = await repo.rpc("reserve_analysis", {"case_id": id})
    try:
        result = await investigate(body)
        prior = body.get("analysis")
        if prior:
            result["change"] = {"previous_finding": prior["finding"], "current_finding": result["finding"],
                "previous_claims": len(prior["claims"]), "current_claims": len(result["claims"]),
                "new_source_ids": [e["id"] for e in body["evidence"] if e["id"] not in {c["source_id"] for c in prior["claims"]}]}
        body.update(analysis=result, analysis_stale=False)
        return await repo.save(body, "investigation_updated", {"finding": result["finding"], "input_digest": result["input_digest"], "model": MODEL, "analysis": result}, job_id=job["job_id"])
    except Exception:
        await repo.rpc("fail_analysis", {"job_id": job["job_id"], "error": "Investigation did not commit; prior case data retained"})
        raise


class RequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    witness_id: str | None = Field(default=None, max_length=100)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    question: str | None = Field(default=None, min_length=1, max_length=1000)
    recipient: Literal["buyer","seller","carrier","payment_provider","other"] | None = None


@app.post("/api/cases/{id}/requests")
async def create_request(id: str, data: RequestInput, user=Depends(auth.current_session)):
    body = await repo.get(id)
    if data.witness_id and data.witness_id != "manual":
        if not body.get("analysis") or body.get("analysis_stale"): raise HTTPException(409, "Investigate current records before using a suggested request")
        original = next((w for w in body["analysis"]["requests"] if w["id"]==data.witness_id), None)
        if original is None: raise HTTPException(404, "Suggested witness not found")
    else:
        if not data.title or not data.question or not data.recipient: raise HTTPException(422, "Supply a title, question and intended recipient")
        original = {"title": data.title, "question": data.question, "recipient": data.recipient,
            "distinguishes": [], "rationale": "Investigator-created request", "burden": "medium", "priority": "first"}
    witness = {**original, **{k:v for k,v in data.model_dump().items() if k in ('title','question','recipient') and v is not None}}
    if any(r["question"]==witness["question"] and r["status"]=="open" for r in body["requests"]): raise HTTPException(409, "This request is already open")
    token = secrets.token_urlsafe(32)
    request = {**witness, "id": uid("R-"), "created_at": now(), "status": "open", "expires_at": time.time()+7*86400}
    body["requests"].append(request)
    saved = await repo.save(body, "witness_requested", {"request_id":request["id"],"recipient":request["recipient"],"question":request["question"]},
        request_action="create", request_hash=auth.token_hash(token), request=request)
    return {"request": request, "portal_fragment": "#request="+token, "case": saved,
            "delivery": "No message was sent. Share this restricted link only with its intended recipient."}


class CloseInput(BaseModel):
    status: Literal["unavailable","withdrawn"]
    reason: str = Field(min_length=3, max_length=500)


@app.post("/api/cases/{id}/requests/{request_id}/close")
async def close_request(id: str, request_id: str, data: CloseInput, user=Depends(auth.current_session)):
    body = await repo.get(id)
    request = next((r for r in body["requests"] if r["id"]==request_id), None)
    if request is None: raise HTTPException(404, "Request not found")
    if request["status"]!="open": raise HTTPException(409, "Only an unanswered request can be closed")
    if len(data.reason.strip())<3: raise HTTPException(422,"Record a reason")
    request.update(status=data.status, closure_reason=data.reason.strip(), closed_at=now(), closure_origin="investigator_report", availability_verified=False)
    body["analysis_stale"] = body.get("analysis") is not None
    return await repo.save(body, "witness_request_closed", {"request_id":request_id,"reason":data.reason.strip(),"status":data.status}, request_action="close", request_id=request_id)


def portal_hash(request):
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer ") or not 32<=len(header[7:])<=128: raise HTTPException(401, "Request token required")
    return auth.token_hash(header[7:])


@app.get("/api/portal")
async def portal(request: Request):
    context = await repo.rpc("portal_context", {"request_hash": portal_hash(request)}, session="")
    return {k:context["request"][k] for k in ("id","title","question","recipient","expires_at")}


async def portal_save(request, data, raw=None, mime="text/plain"):
    hashed = portal_hash(request)
    context = await repo.rpc("portal_context", {"request_hash": hashed}, session="")
    body = {**context["case"], "timeline": context["timeline"]}
    data.party = context["request"]["recipient"]
    event, original = add_source(body, data, raw, mime, context["request"])
    await repo.rpc("portal_submit", repo.mutation(body, "evidence_received", event,
        request_action="reply", request_hash=hashed, file=original), session="")
    return {"ok": True, "message": "Response saved for review. Origin and factual truth remain unverified."}


@app.post("/api/portal")
async def portal_reply(request: Request, data: EvidenceInput):
    return await portal_save(request, data)


@app.post("/api/portal/upload")
async def portal_upload(request: Request, file: UploadFile=File(...)):
    await repo.rpc("portal_context", {"request_hash": portal_hash(request)}, session="")
    raw,text,mime = await extract_file(file)
    return await portal_save(request, EvidenceInput(title=Path(file.filename or "Evidence").name[:160], text=text),raw,mime)


@app.get("/api/cases/{id}/export")
async def export(id: str, user=Depends(auth.current_session)):
    return Response(json.dumps(await repo.get(id),indent=2),media_type="application/json",headers={"Content-Disposition":"attachment; filename=verdict-case.json"})


@app.get("/api/integrations")
async def integrations(user=Depends(auth.current_session)):
    return {"paypal":{"configured":False,"status":"not_configured","environment":"sandbox"}, "gemini":{"configured":bool(os.getenv("GEMINI_API_KEY")),"model":MODEL}, "storage":{"configured":True,"primary":"postgres"},"webhook":{"configured":False}}


@app.api_route("/api/paypal/{path:path}", methods=["GET","POST"])
@app.api_route("/api/cases/{id}/actions/{path:path}", methods=["POST"])
async def provider_not_connected(path: str, user=Depends(auth.current_session), id: str=""):
    raise HTTPException(409,"Merchant connections are not enabled for individual accounts. The protected operator build retains the PayPal sandbox adapter.")


DIST = Path(__file__).resolve().parents[1]/"frontend/dist"
if DIST.exists(): app.mount("/assets",StaticFiles(directory=DIST/"assets"),name="assets")


@app.get("/")
def index():
    if not (DIST/"index.html").exists(): raise HTTPException(503,"Frontend build is missing")
    return FileResponse(DIST/"index.html")
