# PayPal sandbox capability record

The account's existing `.env` was retained privately. OAuth and dispute listing were repeated on 2026-11-05: **200 / 200, zero disputes**. No real-money endpoint is used. The adapter hardcodes `https://api-m.sandbox.paypal.com` and does not permit redirects or arbitrary provider URLs.

Authority: [PayPal integration guide, updated October 14, 2026](https://developer.paypal.com/platforms/disputes/integrate-disputes/) and [current API reference](https://developer.paypal.com/api/customer-disputes/v1).

| Operation | Implementation | Current external validation |
|---|---|---|
| OAuth + bounded dispute pagination | Implemented; safe host/path and loop checks | Actual 200; zero disputes |
| Dispute detail and inbox import | Implemented; preserves raw JSON source and API provenance | Contract tests only; no eligible case available |
| Capture/order linkage | Capture ID from dispute → capture API → related order ID | Implemented but unverified against an actual accessible transaction |
| Send inquiry message | Exact reviewed JSON payload, current provider link required | Mock transport tests; no message sent |
| Provide fulfillment evidence | Multipart `input` with reviewed carrier/tracking and notes | Mock transport tests; no provider submission made |
| Accept claim | Explicit note; sandbox only, warns about refund effect | Mock transport tests; no claim accepted |
| Webhooks | Provider verification endpoint, mandatory configured webhook ID, event reservation and duplicate handling, refresh provider state | Rejection and duplicate tests; registration/delivery not performed |

All writes default to disabled (`VERDICT_ALLOW_SANDBOX_ACTIONS=false`). The AI has no PayPal tools. Action preparation creates a ten-minute server-side record binding the exact payload, approver, evidence, revision and entire provider detail. Execution rereads PayPal, validates the current HATEOAS link, reserves dispatch transactionally and checks a durable replay record. Timeouts/5xx become **unknown** and block further case actions pending reconciliation; no automatic external write retries. A crash after reservation intentionally remains blocked. This is fail-closed, not automatic recovery.

`provide-evidence` initially supports tracking metadata and notes, not arbitrary file attachments. Make-offer, appeals, adjudication, production merchant onboarding and third-party merchant delegated consent are not exposed. Our rule does not authorize card-network representment or real financial advice.

## Obtaining a real test dispute

The sandbox scope list includes disputes/create, but that alone does not establish operational permission. Current [sandbox guidance](https://developer.paypal.com/platforms/disputes/integrate-disputes/) describes special authorization for API creation and the buyer Resolution Center alternative. There is no existing seller transaction to dispute. A create request without one would not prove anything; none was fabricated.

Create/approve a sandbox checkout with the US buyer and Indian seller, retain its capture ID, then open the dispute from the sandbox buyer Resolution Center. No PAN, live card or Payouts redesign is needed for VERDICT. The actual checkout approval and case opening require account interaction; do not invent sandbox passwords or treat credentials as publication material. Once the case exists, press **Sync PayPal**, link its payment record, investigate, and review whichever action PayPal currently exposes. Record raw response statuses, provider request identifiers privately and before/after state. Forced sandbox adjudication is never evidence of real-world win rate.
