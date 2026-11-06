import os, time, json, re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, quote
import httpx

BASE = "https://api-m.sandbox.paypal.com"


class PayPalError(Exception):
    def __init__(self, status, uncertain=False, diagnostic=None):
        self.status = status
        self.uncertain = uncertain
        self.diagnostic = diagnostic or {"http_status": status}
        super().__init__(f"PayPal sandbox returned {status}")


def error_diagnostic(response):
    """Keep machine codes for reconciliation; never return provider message/PII bodies."""
    result = {"http_status": response.status_code}
    try:
        body = response.json()
    except ValueError:
        return result
    if not isinstance(body, dict):
        return result
    for target, value in [("name", body.get("name")), ("debug_id", body.get("debug_id") or response.headers.get("paypal-debug-id"))]:
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
            result[target] = value
    details = body.get("details", [])
    result["issues"] = [x["issue"] for x in (details if isinstance(details, list) else []) if isinstance(x, dict) and isinstance(x.get("issue"), str) and re.fullmatch(r"[A-Z0-9_]{1,100}", x["issue"])]
    return result


class PayPal:
    def __init__(self):
        self.token = None
        self.expires = 0

    async def request(self, method, path, payload=None, key=None, files=None, raw=None):
        if not path.startswith("/v1/") and not path.startswith("/v2/"):
            raise ValueError("Unapproved PayPal path")
        async with httpx.AsyncClient(timeout=35, follow_redirects=False) as c:
            if not self.token or self.expires < time.time():
                r = await c.post(
                    BASE + "/v1/oauth2/token",
                    auth=(
                        os.getenv("PAYPAL_CLIENT_ID", ""),
                        os.getenv("PAYPAL_CLIENT_SECRET", ""),
                    ),
                    data={"grant_type": "client_credentials"},
                )
                if r.status_code != 200:
                    raise PayPalError(r.status_code, diagnostic=error_diagnostic(r))
                d = r.json()
                self.token = d["access_token"]
                self.expires = time.time() + d.get("expires_in", 300) - 60
            h = {"Authorization": "Bearer " + self.token}
            if key:
                h["PayPal-Request-Id"] = key
            if raw is not None:
                h["Content-Type"] = "application/json"
            try:
                r = await c.request(
                    method,
                    BASE + path,
                    headers=h,
                    json=payload if files is None and raw is None else None,
                    files=files,
                    content=raw,
                )
            except httpx.HTTPError:
                raise PayPalError("network_error", method != "GET") from None
            if r.status_code >= 300:
                raise PayPalError(
                    r.status_code,
                    method != "GET"
                    and r.status_code not in {400, 401, 403, 404, 405, 415, 422},
                    diagnostic=error_diagnostic(r),
                )
            return r.json() if r.content else {}

    async def disputes(self):
        result = []
        # Avoid the provider's current-time default excluding existing cases.
        after = (datetime.now(timezone.utc) - timedelta(days=179)).strftime("%Y-%m-%dT%H:%M:%SZ")
        path = "/v1/customer/disputes?update_time_after=" + quote(after, safe="") + "&page_size=50"
        seen = set()
        for _ in range(20):
            if path in seen:
                raise ValueError(
                    "PayPal pagination loop; no incomplete import accepted"
                )
            seen.add(path)
            d = await self.request("GET", path)
            result.extend(d.get("items", []))
            next_link = next(
                (l["href"] for l in d.get("links", []) if l.get("rel") == "next"), None
            )
            if not next_link:
                return result
            parsed = urlparse(next_link)
            if (
                parsed.scheme != "https"
                or parsed.netloc != "api-m.sandbox.paypal.com"
                or parsed.path != "/v1/customer/disputes"
            ):
                raise ValueError("Unsafe PayPal pagination link")
            path = parsed.path + ("?" + parsed.query if parsed.query else "")
        raise ValueError(
            "PayPal pagination exceeded 20 pages; no incomplete import accepted"
        )

    async def detail(self, id):
        if not re.fullmatch(r"[A-Za-z0-9-]{1,80}", id):
            raise ValueError("Invalid dispute id")
        return await self.request("GET", "/v1/customer/disputes/" + quote(id, safe=""))

    async def verify(self, headers, raw):
        if not os.getenv("PAYPAL_WEBHOOK_ID"):
            return False
        keys = {
            "auth_algo": "paypal-auth-algo",
            "cert_url": "paypal-cert-url",
            "transmission_id": "paypal-transmission-id",
            "transmission_sig": "paypal-transmission-sig",
            "transmission_time": "paypal-transmission-time",
        }
        fields = {k: headers.get(v) for k, v in keys.items()}
        if not all(fields.values()):
            return False
        fields["webhook_id"] = os.environ["PAYPAL_WEBHOOK_ID"]
        # Preserve raw JSON event bytes inside the verification request.
        body = json.dumps(fields)[:-1].encode() + b',"webhook_event":' + raw + b"}"
        d = await self.request(
            "POST", "/v1/notifications/verify-webhook-signature", raw=body
        )
        return d.get("verification_status") == "SUCCESS"


def allowed(detail):
    id = detail["dispute_id"]
    result = []
    for l in detail.get("links", []):
        p = urlparse(l.get("href", ""))
        for action in ["send-message", "provide-evidence", "accept-claim"]:
            if (
                l.get("method", "").upper() == "POST"
                and p.scheme == "https"
                and p.netloc == "api-m.sandbox.paypal.com"
                and p.path == f"/v1/customer/disputes/{id}/{action}"
                and not p.query
            ):
                result.append(action)
    return sorted(set(result))


def requested_seller_evidence(detail):
    return sorted({e["evidence_type"] for e in detail.get("evidences", [])
        if e.get("source") == "REQUESTED_FROM_SELLER"
        and e.get("evidence_type") in ("PROOF_OF_FULFILLMENT", "OTHER")
        and (e.get("action_info") or {}).get("action") in (None, "PROVIDE_EVIDENCE")})


def state(detail):
    # Bind all provider detail, not merely status; any changed evidence invalidates approval.
    return detail


client = PayPal()
