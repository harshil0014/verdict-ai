"""Create a genuine sandbox checkout; capture only after actual buyer approval.

No live endpoint, card details, invented transaction or automatic write retry.
Provider records stay in ignored runtime state. Never commit that journal.
"""

import argparse
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlparse
import uuid

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://api-m.sandbox.paypal.com"
REFERENCE = "VERDICT-SANDBOX-TEST"


def checkout_payload():
    return {
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": REFERENCE,
                "description": "VERDICT sandbox-only delivery dispute integration test",
                "amount": {
                    "currency_code": "USD",
                    "value": "1.00",
                    "breakdown": {
                        "item_total": {"currency_code": "USD", "value": "1.00"}
                    },
                },
                "items": [
                    {
                        "name": "VERDICT sandbox delivery test",
                        "sku": "VERDICT-SANDBOX-ONLY",
                        "category": "PHYSICAL_GOODS",
                        "quantity": "1",
                        "unit_amount": {"currency_code": "USD", "value": "1.00"},
                    }
                ],
            }
        ],
        "application_context": {
            "brand_name": "VERDICT Sandbox Test",
            "shipping_preference": "GET_FROM_FILE",
            "user_action": "PAY_NOW",
            "return_url": "http://127.0.0.1:8000/?sandbox_test=approved",
            "cancel_url": "http://127.0.0.1:8000/?sandbox_test=cancelled",
        },
    }


def validate_capture(order):
    if order.get("status") != "APPROVED" or order.get("intent") != "CAPTURE":
        raise ValueError("The buyer has not approved this sandbox capture.")
    units = order.get("purchase_units", [])
    if any(u.get("payments", {}).get("captures") for u in units):
        raise ValueError("An existing capture blocks another capture attempt.")
    if len(units) != 1 or units[0].get("reference_id") != REFERENCE:
        raise ValueError(
            "The approved order does not match the reviewed test purchase."
        )
    amount = units[0].get("amount", {})
    try:
        valid = amount.get("currency_code") == "USD" and Decimal(
            amount.get("value", "")
        ) == Decimal("1.00")
    except InvalidOperation:
        valid = False
    if not valid:
        raise ValueError(
            "The approved amount is not the reviewed USD 1.00 sandbox amount."
        )


def approval_link(order):
    link = next(
        (
            x.get("href")
            for x in order.get("links", [])
            if x.get("rel") in ("approve", "payer-action")
        ),
        None,
    )
    if link:
        parsed = urlparse(link)
        if parsed.scheme != "https" or parsed.hostname not in (
            "www.sandbox.paypal.com",
            "sandbox.paypal.com",
        ):
            raise ValueError("Unexpected checkout approval host; refused.")
    return link


def save(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(body, indent=2), encoding="utf-8", newline="\n")
    temporary.replace(path)


@contextmanager
def checkout_lock(path):
    """OS-backed lock prevents two local processes from dispatching the same write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        handle.seek(0, 2)
        if not handle.tell():
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError("Another checkout process holds the journal lock; no request sent.") from None
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["create", "status", "capture"])
    parser.add_argument("--confirm-sandbox-capture", action="store_true")
    parser.add_argument("--show-approval-link", action="store_true")
    args = parser.parse_args()
    with checkout_lock(ROOT / "runtime/sandbox-checkout.lock"):
        run(args)


def run(args):
    load_dotenv(ROOT / "backend/.env")
    if os.getenv("PAYPAL_BASE_URL", BASE).rstrip("/") != BASE:
        raise ValueError("Only the PayPal sandbox is allowed.")
    path = ROOT / "runtime/sandbox-checkout.json"
    journal = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    if args.command == "capture" and not args.confirm_sandbox_capture:
        raise ValueError("Explicit --confirm-sandbox-capture is required.")
    with httpx.Client(timeout=35, follow_redirects=False) as client:
        auth = client.post(
            BASE + "/v1/oauth2/token",
            auth=(
                os.getenv("PAYPAL_CLIENT_ID", ""),
                os.getenv("PAYPAL_CLIENT_SECRET", ""),
            ),
            data={"grant_type": "client_credentials"},
        )
        if auth.status_code != 200:
            raise RuntimeError("Sandbox OAuth HTTP " + str(auth.status_code))
        headers = {
            "Authorization": "Bearer " + auth.json()["access_token"],
            "Content-Type": "application/json",
        }
        if args.command == "create" and not journal:
            journal = {
                "environment": "sandbox",
                "state": "creating",
                "create_key": "verdict-test-" + uuid.uuid4().hex,
                "payload": checkout_payload(),
            }
            save(path, journal)
            try:
                r = client.post(
                    BASE + "/v2/checkout/orders",
                    headers={**headers, "PayPal-Request-Id": journal["create_key"]},
                    json=journal["payload"],
                )
                if r.status_code != 201:
                    journal.update(
                        state="creation_unconfirmed", http_status=r.status_code
                    )
                    save(path, journal)
                    raise RuntimeError(
                        "Sandbox order creation HTTP "
                        + str(r.status_code)
                        + "; no retry performed."
                    )
                order = r.json()
                journal.update(
                    state="created", order_id=order["id"], provider_order=order
                )
                save(path, journal)
            except httpx.HTTPError:
                journal["state"] = "creation_unconfirmed"
                save(path, journal)
                raise RuntimeError(
                    "Sandbox creation result is unknown; inspect PayPal before retrying."
                ) from None
        if not journal or not journal.get("order_id"):
            raise RuntimeError(
                "No confirmed order ID is available. Resolve any unconfirmed creation first."
            )
        order_id = journal["order_id"]
        if not order_id.isalnum():
            raise ValueError("Invalid journal order ID")
        r = client.get(BASE + "/v2/checkout/orders/" + order_id, headers=headers)
        if r.status_code != 200:
            raise RuntimeError("Sandbox order read HTTP " + str(r.status_code))
        order = r.json()
        if args.command == "capture" and order.get("status") != "COMPLETED":
            if journal["state"] != "created":
                raise RuntimeError(
                    "The journal does not allow a new capture. Reconcile directly with PayPal."
                )
            validate_capture(order)
            journal.update(
                state="capturing", capture_key="verdict-capture-" + uuid.uuid4().hex
            )
            save(path, journal)
            try:
                r = client.post(
                    BASE + "/v2/checkout/orders/" + order_id + "/capture",
                    headers={**headers, "PayPal-Request-Id": journal["capture_key"]},
                    json={},
                )
                if r.status_code not in (200, 201):
                    journal.update(
                        state="capture_unconfirmed", http_status=r.status_code
                    )
                    save(path, journal)
                    raise RuntimeError(
                        "Sandbox capture HTTP "
                        + str(r.status_code)
                        + "; no retry performed."
                    )
                order = r.json()
                journal.update(state="captured", provider_capture=order)
                save(path, journal)
            except httpx.HTTPError:
                journal["state"] = "capture_unconfirmed"
                save(path, journal)
                raise RuntimeError(
                    "Sandbox capture result is unknown; no automatic retry."
                ) from None
        journal["provider_order"] = order
        save(path, journal)
        summary = {
            "environment": "sandbox",
            "http_status": 200,
            "order_status": order.get("status"),
            "journal_state": journal["state"],
            "reviewed_amount": "USD 1.00",
            "money_is_real": False,
            "capture_statuses": [
                capture.get("status")
                for unit in order.get("purchase_units", [])
                for capture in unit.get("payments", {}).get("captures", [])
            ],
        }
        if args.show_approval_link:
            summary["approval_url"] = approval_link(order)
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
