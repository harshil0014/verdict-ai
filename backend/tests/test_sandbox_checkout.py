import copy
import pytest
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
