"""Bounded, read-only acquisition and versioning of provider payment records."""
from dataclasses import dataclass
import json
import re
from fixtures import evidence
from paypal import PayPalError
from store import digest


@dataclass
class ReadBudget:
    remaining: int = 20


def safe_id(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9]{1,80}", value) is not None


def record_identity(source):
    if source.get("origin") != "paypal_sandbox_api" or source.get("origin_verified") is not True:
        return None
    try:
        body = json.loads(source["text"])
    except (ValueError, KeyError, TypeError):
        return None
    if not isinstance(body, dict):
        return None
    if source.get("title") == "PayPal sandbox dispute record" and isinstance(body.get("dispute_id"), str) and re.fullmatch(r"[A-Za-z0-9-]{1,80}", body["dispute_id"]):
        return ("dispute", body["dispute_id"]), digest(body)
    if not safe_id(body.get("id")):
        return None
    # Recognize original build snapshots too; no destructive migration is needed.
    for kind in ("capture", "order"):
        if source.get("title") == f"PayPal {kind} {body['id']}":
            return (kind, body["id"]), digest(body)
    return None


def active_sources(sources):
    # Only server-verified, versioned provider records can supersede a source.
    by_id = {s["id"]: s for s in sources}
    output = []
    for source in sources:
        replacement = by_id.get(source.get("superseded_by"))
        old_identity = record_identity(source)
        new_identity = record_identity(replacement) if replacement else None
        if old_identity and new_identity and old_identity[0] == new_identity[0]:
            continue
        output.append(source)
    return output


async def fetch_records(client, detail, budget):
    records, issues, captures, seen_orders = [], [], [], set()
    for transaction in detail.get("disputed_transactions", []):
        capture = transaction.get("seller_transaction_id")
        if not safe_id(capture):
            if capture is not None:
                issues.append("invalid_capture_identifier")
            continue
        if capture not in captures:
            captures.append(capture)
    if len(captures) > 10:
        issues.append("transaction_limit")

    async def read(kind, identifier):
        if budget.remaining <= 0:
            issues.append("read_budget_exhausted")
            return None
        budget.remaining -= 1
        path = "/v2/payments/captures/" if kind == "capture" else "/v2/checkout/orders/"
        try:
            body = await client.request("GET", path + identifier)
        except PayPalError as error:
            issues.append(kind + "_unavailable:" + str(error.status))
            return None
        if not isinstance(body, dict) or body.get("id") != identifier:
            issues.append(kind + "_identifier_mismatch")
            return None
        records.append({"kind": kind, "id": identifier, "body": body})
        return body

    for capture in captures[:10]:
        body = await read("capture", capture)
        if body is None:
            continue
        order = body.get("supplementary_data", {}).get("related_ids", {}).get("order_id")
        if order is None:
            issues.append("capture_has_no_order_link")
        elif not safe_id(order):
            issues.append("invalid_order_identifier")
        elif order not in seen_orders:
            seen_orders.add(order)
            await read("order", order)
    return records, sorted(set(issues)), len(captures)


def merge_records(body, records, issues, capture_count):
    """Preserve old bytes; supersede only the latest verified snapshot of a record."""
    latest = {}
    for source in body["evidence"]:
        identity = record_identity(source)
        if identity:
            latest[identity[0]] = source, identity[1]
    added, superseded = [], []
    issues = list(issues)

    def supersede_older(key, replacement):
        for older in body["evidence"]:
            identity = record_identity(older)
            if identity and identity[0] == key and older["id"] != replacement["id"] and not older.get("superseded_by"):
                older["superseded_by"] = replacement["id"]
                superseded.append({"old_source_id": older["id"], "new_source_id": replacement["id"]})

    for record in records:
        key, fingerprint = (record["kind"], record["id"]), digest(record["body"])
        previous = latest.get(key)
        if previous and previous[1] == fingerprint:
            supersede_older(key, previous[0])
            continue
        if len(body["evidence"]) >= 40:
            issues.append("evidence_source_limit")
            continue
        source = evidence(f"PayPal {record['kind']} {record['id']}",
                          json.dumps(record["body"], indent=2, sort_keys=True),
                          "payment_provider", "paypal_sandbox_api")
        source.update(origin_verified=True, synthetic=False,
                      provider_record_kind=record["kind"], provider_record_id=record["id"],
                      provider_record_sha256=fingerprint)
        if previous:
            source["replaces_source_id"] = previous[0]["id"]
            supersede_older(key, source)
        body["evidence"].append(source)
        latest[key] = source, fingerprint
        added.append(source["id"])
    status = "partial" if records and issues else "complete" if records else "deferred" if "read_budget_exhausted" in issues else "unavailable" if capture_count or issues else "no_eligible_capture"
    acquisition = {"status": status, "eligible_captures": capture_count,
                   "records_read": len(records), "issues": sorted(set(issues))}
    status_changed = body.get("payment_record_acquisition") != acquisition
    if added or status_changed or superseded:
        body["payment_record_acquisition"] = acquisition
    if added or superseded or (status_changed and issues):
        body["analysis_stale"] = bool(body.get("analysis"))
    return {"changed": bool(added or status_changed or superseded), "source_ids": added,
            "superseded": superseded, "acquisition": acquisition}
