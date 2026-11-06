# Genuine sandbox transaction setup

Use the existing private sandbox credentials. The helper hardcodes the sandbox host and refuses a live `PAYPAL_BASE_URL`. It creates a USD 1.00 test purchase; no real funds are involved. Account login and buyer approval are genuine PayPal steps, not simulation.

```powershell
backend/.venv/Scripts/python.exe scripts/sandbox_checkout.py create --show-approval-link
```

Open the returned private approval link and sign in with the intended **US Personal sandbox buyer**. Do not use a live account or publish the link. Approve the displayed USD 1.00 sandbox purchase. The local return page does not automatically capture or create a dispute.

```powershell
backend/.venv/Scripts/python.exe scripts/sandbox_checkout.py status
backend/.venv/Scripts/python.exe scripts/sandbox_checkout.py capture --confirm-sandbox-capture
```

Capture is refused unless PayPal currently reports `APPROVED`, the intent is `CAPTURE`, and the single purchase unit still has the expected reference and USD 1.00 amount. A journal reservation is written before dispatch. Network/ambiguous results block retries pending reconciliation. A completed capture is not sent again. Do not delete the journal to bypass an uncertain outcome.

The provider order/capture records are stored only in ignored `runtime/sandbox-checkout.json`. This record can contain account identifiers; never commit it or paste it into a public issue. The publication auditor checks known private order/account identifiers against the source and history.

After capture, use the buyer's sandbox Resolution Center to open an actual item-not-received dispute against that transaction. Then synchronize VERDICT's PayPal inbox. API-based buyer dispute creation additionally requires documented buyer-side permission/consent and the appropriate buyer assertion; a listed scope is insufficient evidence that those prerequisites are met. No buyer assertion or consent record is fabricated.

An actual eligible dispute and current PayPal action links are required before testing merchant evidence submission. The main application keeps writes disabled by default and requires its exact-payload human approval path. Test notes, carrier/tracking metadata and any forced sandbox adjudication must be labeled synthetic test evidence; forced outcomes never establish a real win rate.

Authority: [PayPal's end-to-end sandbox testing guide](https://developer.paypal.com/disputes/test-go-live), [buyer-side prerequisites](https://developer.paypal.com/platforms/disputes/integrate-disputes/) and [Orders API](https://developer.paypal.com/api/orders/v2).
