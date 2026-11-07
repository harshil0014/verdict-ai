# PayPal sandbox inside account workspaces

The account app reuses the existing PayPal OAuth/dispute and capture/order acquisition adapter. An authorized test merchant can choose **Import from PayPal** when creating a case, select a real dispute, and let PayPal populate its fields. The resulting private cloud case enters the existing automatic investigation workflow. Manual cases remain available.

## Authorization and supported scope

This release supports a **restricted first-party sandbox test merchant**, not public delegated merchant onboarding. A server operator explicitly binds that merchant's credential reference to one authenticated SaaS account. The active credential reference is unique in PostgreSQL. The server additionally checks `VERDICT_PAYPAL_DEMO_OWNER_ID` and `VERDICT_PAYPAL_DEMO_MERCHANT_ID` before any provider read. A stranger cannot activate the connection by typing a dispute, transaction, email or merchant identifier. Account ownership comes from an opaque authenticated session, not a request body or PayPal payer ID.

PayPal's current documentation requires merchant consent and `PayPal-Auth-Assertion` for third-party calls. Partner onboarding requires the applicable approved platform integration and features, including `READ_SELLER_DISPUTE`; not all onboarding modes support disputes. No partner approval or public consent flow has been demonstrated here. We do not fabricate one. [Disputes integration requirements](https://developer.paypal.com/platforms/disputes/integrate-disputes/) · [Account setup](https://developer.paypal.com/platforms/disputes/set-up/) · [Seller onboarding checklist](https://developer.paypal.com/platforms/seller-onboarding/onboarding-checklist/).

Only sandbox URLs are used. Live payments and provider writes are absent from the account integration. Its adapter rejects every non-GET business request before token acquisition; the necessary OAuth token POST is authentication, not a payment/dispute action. Public action routes remain closed. The separate legacy operator's existing human-approval/current-eligibility checks remain unchanged.

## Records, linkage and privacy

The import reads the actual dispute, its seller transaction/capture IDs, and provider-related orders. Merchant/payee mismatches, inconsistent capture/order membership, mismatched IDs, contradictory buyer IDs and inconsistent capture amounts fail closed. Missing buyer IDs, dates or amounts stay missing. The receipt shows **Not available from PayPal** rather than invented values. Disputed amount and actual capture amount are separate fields. Current capture status is preserved even when it differs from the completed order's status. PayPal identifiers are used; no UPI ID is assumed.

The frontend and Gemini receive an explicit privacy-minimized JSON projection. It retains provider transaction IDs, account IDs, status, amounts, dates, reason and lifecycle; it excludes names, email addresses, shipping addresses, instrument details and arbitrary free-form communications. Buyer-reported dispute reasons remain reported claims, not findings or proof of fulfillment. Free-form PayPal communications are retained in the original snapshot but omitted from this beta's displayed/AI projection; users are not told that all message contents were analyzed. External evidence and witness responses keep their existing origins and identity limitations.

Full authenticated JSON snapshots are canonicalized, SHA-256 hashed and stored in a separate immutable-by-application PostgreSQL relation. Canonicalization sorts object keys and the top-level HATEOAS link array, whose order varied across actual otherwise-identical reads; every link value, method and relation is retained. Other arrays are unchanged. Snapshots are never sent in normal case/export/download responses. Canonical JSON hashes are not hashes of the original HTTP envelope. Each displayed projection has its own hash and provenance link to the original. This is data minimization, not a claim of universal free-text redaction.

## Persistence and synchronization

Connection, import-link and original-snapshot relations have forced owner RLS, no anonymous/authenticated Data API grants and a service-only security-invoker RPC. Account ownership is derived before dropping into the existing restricted executor role. The import commits case, original snapshots, audit and initial workflow outbox together. An advisory lock and unique connection/dispute mapping prevent duplicate cases. Revision checks protect concurrent case edits. Raw originals have a 20 MB/account vault limit and share the existing global storage ceiling; no paid overflow is enabled.

Refresh re-reads PayPal. Unchanged snapshots do not add sources, alter the case revision/audit or repeat analysis. Changed snapshots retain older versions and invalidate the prior analysis. Authentication/provider failures retain existing records and return safe HTTP/code diagnostics. No provider secrets or raw customer response is logged. This release provides user-initiated import/sync, not an unverified webhook receiver or scheduled polling claim.

## Setup

Apply the timestamped `account_paypal_sandbox_import` migration after the existing SaaS migrations. Use server-only `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` for the owned sandbox app; bind one active `operator_sandbox_demo` credential reference through the service-role provisioning operation to the intended existing account UUID. Configure the two `VERDICT_PAYPAL_DEMO_*` values to match that connection. No HTTP route exposes provisioning or administrative contexts. Never share this reference with arbitrary registered users, place secrets in React, or substitute a buyer's account ID for SaaS authentication.

The operator-only short-lived context supports scheduled imports into an explicitly authorized account without changing its password, recovery key or browser session. It is not a human sign-in or PayPal consent event. Controlled QA uses ordinary public registration/login and separately provisioned merchant authorization. A QA connection can be revoked before the credential is assigned to the owner's intended workspace; its test case and originals stay in their original private workspace.

## Verification

`scripts/saas_paypal_acceptance.py` keeps credentials, provider IDs and case IDs under ignored runtime state. It performs normal registration/login, actual sandbox reads, provider-populated creation, automatic Gemini investigation, repeated-sync deduplication, privacy/isolation, logout/login and persistence verification. Provisioning is explicitly an administrative test-merchant step, not a claimed public OAuth flow. Unit tests cover absent buyer/amount fields, different payment/disputed amounts, mismatches, expired/invalid credentials, historical snapshots and denied writes. Hosted records are added only after execution. The frozen 28/30 evaluation remains unchanged.
