import copy
import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path
import httpx
import pytest
from scripts import sandbox_checkout as checkout
from scripts.sandbox_checkout import checkout_payload, validate_capture, approval_link


def approved():
    return {**checkout_payload(), "status": "APPROVED"}


def test_sandbox_capture_requires_actual_approval():
    order = approved()
    validate_capture(order)
    for status in ("CREATED", "PAYER_ACTION_REQUIRED", "VOIDED"):
        order["status"] = status
        with pytest.raises(ValueError):
            validate_capture(order)


def test_sandbox_capture_binds_the_reviewed_amount_currency_and_purchase():
    for key, value in (("value", "2.00"), ("currency_code", "INR"), ("value", "NaN")):
        order = approved()
        order["purchase_units"][0]["amount"][key] = value
        with pytest.raises(ValueError):
            validate_capture(order)
    order = approved()
    order["purchase_units"][0]["reference_id"] = "other-order"
    with pytest.raises(ValueError):
        validate_capture(order)


def test_approval_link_cannot_point_to_live_or_arbitrary_host():
    for url in (
        "https://www.paypal.com/checkoutnow",
        "https://evil.example/",
        "http://www.sandbox.paypal.com/checkoutnow",
    ):
        with pytest.raises(ValueError):
            approval_link({"links": [{"rel": "approve", "href": url}]})
    assert approval_link(
        {
            "links": [
                {
                    "rel": "approve",
                    "href": "https://www.sandbox.paypal.com/checkoutnow?token=TEST",
                }
            ]
        }
    )


def test_existing_capture_and_completed_journal_cannot_be_recaptured(monkeypatch, tmp_path):
    order = approved()
    order["purchase_units"][0]["payments"] = {"captures": [{"status": "COMPLETED"}]}
    with pytest.raises(ValueError, match="existing capture"):
        validate_capture(order)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    journal = {"order_id": "TESTORDER", "state": "captured"}
    (runtime / "sandbox-checkout.json").write_text(json.dumps(journal))
    monkeypatch.setattr(checkout, "ROOT", tmp_path)
    monkeypatch.setenv("PAYPAL_BASE_URL", checkout.BASE)
    writes = []
    completed = {**order, "status": "COMPLETED"}

    def respond(request):
        if request.url.path == "/v1/oauth2/token":
            return httpx.Response(200, json={"access_token": "test-only-token"})
        if request.method == "POST":
            writes.append(request.url.path)
            raise AssertionError("A second capture must never be sent")
        return httpx.Response(200, json=completed)

    client_type = httpx.Client
    monkeypatch.setattr(checkout.httpx, "Client", lambda **kw: client_type(transport=httpx.MockTransport(respond), **kw))
    args = Namespace(command="capture", confirm_sandbox_capture=True, show_approval_link=False)
    checkout.run(args)
    assert not writes
    completed["status"] = "APPROVED"
    with pytest.raises(RuntimeError, match="journal"):
        checkout.run(args)
    assert not writes


def test_separate_checkout_process_cannot_enter_locked_journal(tmp_path):
    path = tmp_path / "checkout.lock"
    with checkout.checkout_lock(path):
        child = subprocess.run(
            [sys.executable, "-c", "import sys; from pathlib import Path; from scripts.sandbox_checkout import checkout_lock;\nwith checkout_lock(Path(sys.argv[1])): print('unsafe entry')", str(path)],
            cwd=Path(checkout.__file__).resolve().parents[1], capture_output=True, text=True,
        )
        assert child.returncode != 0
        assert "unsafe entry" not in child.stdout
        assert "journal lock" in child.stderr
    with checkout.checkout_lock(path):
        pass
