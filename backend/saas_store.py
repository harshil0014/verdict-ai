"""Durable PostgreSQL RPC repository. There is deliberately no local fallback."""
import base64
import hashlib
import os
from contextvars import ContextVar
import httpx
from fastapi import HTTPException
from store import canon, digest, now, uid, verify_timeline

SESSION = ContextVar("verdict_saas_session", default="")
ERRORS = {
    "unauthorized": (401, "Sign in to continue"),
    "invalid_credentials": (401, "The username, password or recovery code is incorrect"),
    "username_taken": (409, "That username is already in use"),
    "not_found": (404, "Record not found"),
    "stale_revision": (409, "The case changed. Refresh before saving your changes"),
    "invalid_revision": (409, "The case revision is invalid"),
    "request_closed": (409, "This request is expired, answered or closed"),
    "recipient_mismatch": (409, "The response does not match this request"),
    "analysis_busy": (409, "This case already has an investigation in progress"),
    "stale_job": (409, "This investigation is no longer current; refresh the case"),
    "analysis_limit": (429, "Your daily limit of 10 investigation attempts has been reached"),
    "global_analysis_limit": (429, "Today's service investigation capacity has been reached"),
    "storage_limit": (413, "Your 20 MB original-file storage limit has been reached"),
    "service_storage_limit": (503, "Cloud storage capacity has been reached; your existing data is retained"),
    "case_limit": (409, "Your workspace has reached its 50-case limit"),
    "registration_capacity": (503, "Registration capacity has been reached"),
    "invalid_file": (422, "The original file failed integrity or size validation"),
    "research_limit": (409, "This case has reached its 40 research-proposal limit"),
    "research_storage_limit": (413, "Your private research drafts have reached their 20 MB limit"),
    "research_closed": (409, "This proposal cannot be approved or changed in its current state"),
}


def fail(code):
    status, message = ERRORS.get(code, (503, "Cloud storage could not complete this operation"))
    raise HTTPException(status, message)


class CloudRepository:
    def __init__(self):
        self.client = None

    async def start(self):
        # Avoid stale pooled sockets across sleeping/free-service boundaries.
        # No automatic replay of an ambiguous database mutation is performed.
        self.client = httpx.AsyncClient(timeout=40, follow_redirects=False,
            limits=httpx.Limits(max_keepalive_connections=0))
        await self.rpc("health", session="")

    async def close(self):
        if self.client:
            await self.client.aclose()
            self.client = None

    async def rpc(self, operation, args=None, session=None):
        if self.client is None:
            raise HTTPException(503, "Cloud database is not connected")
        url = os.getenv("SUPABASE_URL", "").rstrip("/")
        key = os.getenv("SUPABASE_SECRET_KEY", "")
        if not url.startswith("https://") or not key:
            raise HTTPException(503, "Cloud database configuration is missing")
        try:
            prefix = operation.split(':', 1)[0] if ':' in operation else ''
            function = {'research': 'verdict_research_api', 'workflow': 'verdict_workflow_api', 'paypal':'verdict_paypal_api'}.get(prefix, 'verdict_saas_api')
            op = operation.split(':', 1)[-1]
            response = await self.client.post(url + "/rest/v1/rpc/"+function,
                headers={"apikey": key, "Content-Type": "application/json"},
                json={"p_op": op, "p_session_hash": SESSION.get() if session is None else session,
                      "p_args": args or {}})
        except httpx.HTTPError:
            raise HTTPException(503, "Cloud database connection failed. Refresh to check whether the operation completed") from None
        try:
            body = response.json()
        except ValueError:
            raise HTTPException(503, "Cloud database returned an unreadable response") from None
        if response.status_code >= 300:
            message = body.get("message", "") if isinstance(body, dict) else ""
            if message.startswith("verdict:"):
                fail(message.split(":", 1)[1])
            raise HTTPException(503, "Cloud database refused the operation; no local fallback was used")
        if isinstance(body, dict) and "error" in body:
            fail(body["error"])
        return body

    async def get(self, case_id):
        body = await self.rpc("get", {"case_id": case_id})
        body["audit_valid"] = verify_timeline(body["timeline"])
        return body

    def mutation(self, body, kind, data, creating=False, **extra):
        body = dict(body)
        history = body.pop("timeline", [])
        body.pop("audit_valid", None)
        old_revision = body.get("revision", 0)
        body["revision"] = 1 if creating else old_revision + 1
        body["updated_at"] = now()
        if creating:
            body.update(id=uid("V-"), created_at=body["updated_at"], requests=[], analysis=None)
        record = {"case_id": body["id"], "at": now(), "kind": kind, "data": data,
                  "previous": history[-1]["hash"] if history else ""}
        return {"case_id": body["id"], "expected_revision": old_revision, "body": body,
                "canonical_record": canon(record), "audit": {**record, "hash": digest(record)}, **extra}

    async def create(self, body):
        return await self.rpc("create", self.mutation(body, "case_created", {"title": body["title"], "mode": "manual"}, True))

    async def save(self, body, kind, data, **extra):
        return await self.rpc("save", self.mutation(body, kind, data, **extra))

    @staticmethod
    def file_record(evidence_id, content, mime, name):
        return {"id": evidence_id, "content": base64.b64encode(content).decode("ascii"),
                "mime": mime, "name": name, "sha256": hashlib.sha256(content).hexdigest()}


repo = CloudRepository()
