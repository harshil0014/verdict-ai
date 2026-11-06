# PayPal sandbox capability record

The account's existing `.env` was retained privately. On 6 November 2026 a genuine USD 1.00 sandbox order was buyer-approved, captured once, and independently read through both order and capture APIs: HTTP 200, `COMPLETED`, one capture, matching amount/order linkage. The buyer created an actual item-not-received inquiry. Exact detail returned 200 and `WAITING_FOR_SELLER_RESPONSE`; its seller transaction matched the capture. The adapter hardcodes `https://api-m.sandbox.paypal.com` and does not permit redirects or arbitrary provider URLs. No real funds were used.

Authority: [PayPal integration guide, updated October 14, 2026](https://developer.paypal.com/platforms/disputes/integrate-disputes/) and [current API reference](https://developer.paypal.com/api/customer-disputes/v1).

| Operation | Implementation | Current external validation |
|---|---|---|
| OAuth + bounded dispute pagination | Explicit update-time window; safe host/path and loop checks | Actual 200; one inquiry found with update filter |
| Dispute detail and inbox import | Listing sync or operator import by exact ID; preserves raw JSON/API provenance | Actual detail 200 and imported locally |
| Capture/order linkage | Capture ID from dispute → capture API → related order ID | Actual APIs retrieved and linked three provider-origin records |
| Send inquiry message | Exact reviewed JSON payload, current provider link required | Mock transport tests; no message sent |
| Provide evidence | Multipart `input`; requested fulfillment tracking or `OTHER` notes; exact approval binding | Two individually user-approved notes attempts rejected; latest HTTP 400 `EVIDENCE_TYPE_IS_NOT_ALLOWED`; zero accepted |
| Accept claim | Explicit note; sandbox only, warns about refund effect | Mock transport tests; no claim accepted |
| Webhooks | Provider verification endpoint, mandatory configured webhook ID, event reservation and duplicate handling, refresh provider state | Rejection and duplicate tests; registration/delivery not performed |

All writes default to disabled (`VERDICT_ALLOW_SANDBOX_ACTIONS=false`). The AI has no PayPal tools. Action preparation creates a ten-minute server-side record binding the exact payload, approver, evidence, revision and entire provider detail. Execution rereads PayPal, validates the current HATEOAS link, reserves dispatch transactionally and checks a durable replay record. Timeouts/5xx become **unknown** and block further case actions pending reconciliation; no automatic external write retries. A crash after reservation intentionally remains blocked. This is fail-closed, not automatic recovery.

`provide-evidence` supports requested tracking metadata or other evidence notes, not arbitrary file attachments. No goods were shipped; no tracking or fulfillment proof was invented. The first approved notes attempt retained only its rejection classification. After fixing diagnostics, the owner separately approved one additional attempt with identical notes. PayPal returned HTTP 400 `EVIDENCE_TYPE_IS_NOT_ALLOWED`: this case requests fulfillment proof, not `OTHER`. A fresh detail read showed zero matching submitted notes. The adapter now checks requested seller evidence types before preparation and retains bounded error codes for reconciliation. Both attempts were explicit; neither was an automatic retry. Writes were restored to disabled. [Sanitized lifecycle record](paypal-lifecycle-verification.json). Make-offer, appeals, adjudication and delegated merchant consent remain unexposed.

## Obtaining a real test dispute

The sandbox scope list includes disputes/create, but that alone does not establish operational permission. Current [sandbox guidance](https://developer.paypal.com/platforms/disputes/integrate-disputes/) describes buyer authorization and the Resolution Center alternative. This test used actual buyer checkout approval and Resolution Center interaction, not an invented buyer assertion or transaction.

Unfiltered listing, capture filtering and a creation-time window initially returned zero despite successful exact detail retrieval. Explicit `update_time_after` returned the real inquiry. The product now uses a bounded 179-day update window and supports authenticated exact-ID import. Deprecated `start_time` returned 400 on this account. A zero result from one query is not proof that no case exists.

Create/approve a sandbox checkout with the US buyer and Indian seller, retain its capture ID, then open the dispute from the sandbox buyer Resolution Center. No PAN, live card or Payouts redesign is needed for VERDICT. The actual checkout approval and case opening require account interaction; do not invent sandbox passwords or treat credentials as publication material. Once the case exists, press **Sync PayPal**, link its payment record, investigate, and review whichever action PayPal currently exposes. Record raw response statuses, provider request identifiers privately and before/after state. Forced sandbox adjudication is never evidence of real-world win rate.
