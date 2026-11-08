# Document reading and bounded sandbox autonomy

Evidence uploads now enter the durable investigation queue before source research,
location comparison and Gemini assessment. Images and scanned PDFs are supported;
original files remain in private PostgreSQL storage. Existing cases are not migrated
or replaced. The previous application remains recoverable at release commit
`9106c8476de328a78928a104d3b12ff69ca7cc98`.

## Reading evidence

PNG, JPEG, WebP, single-frame TIFF, PDF, UTF-8 TXT and JSON are accepted, up to
5 MB. Image decoding, PDF parsing/rasterization and English Tesseract run in a
disposable process, with time, pixel, page, text and Linux resource limits. No PDF
JavaScript, active content, document commands or URLs execute in that process.
Digital PDF text is preserved per page; up to ten scanned pages are rasterized
within the existing thirty-page PDF limit. Unread pages remain explicitly unread.
Small, encrypted, damaged, oversized or unsupported files are rejected safely.
Valid originals whose reading fails are retained with an unreadable status.

Printed OCR retains words, normalized-page boxes, engine scores and unclear
markers. Scores are not calibrated factual probabilities. The original SHA-256,
extracted-text SHA-256, processing time, page methods and extraction warnings are
preserved with an audited extraction event. Identical same-party original uploads
in a case are idempotent; another party's submission is a separate provenance event.

Optional image/handwriting reading uses Google's official `google-genai` SDK and
the configured Gemini model/key. It requires affirmative, account-private consent,
remembered until revoked. The disclosure explains Google's free-tier data use.
Up to three EXIF-free, bounded page images per original are sent; originals remain
local to private storage. Requests use the shared model pacing, twenty attempts per
account/day and fifty image attempts globally/day. A changed permission is checked
again before transmission. No billing or paid search is activated. Provider
unavailability retains offline reading and an explicit failure notice.

The vision model transcribes, identifies writing style and records uncertain
portions; it cannot contact anyone or execute actions. Its transcription is kept
separate from the offline text, with model and image hash metadata. Neither is
authenticated ground truth. Claims cite the actual preserved transcription and
offsets; the source check says **quote in machine transcription**, not exact quote
verified in the original image. The original is downloadable from the source
inspector. Automatic URL discovery excludes model-authored image transcription.

## Merchant policy

Autonomy is **off by default**. Only the previously provisioned, server-allowlisted
Sandbox merchant's authenticated owner can enable it. The merchant must explicitly
attest that covered `VERDICT-SANDBOX-TEST` orders are unfulfilled integration tests
and authorize buyer concessions. The UI offers a per-claim limit (maximum USD 5),
total limit (maximum USD 10), action count (maximum five) and twenty-four-hour expiry.
The initial UI defaults are USD 1 / USD 1 / one action. Revocation stops new
dispatches, not actions already sent. Public merchant onboarding remains unavailable.

An enabled policy periodically discovers/imports actual merchant disputes and uses
the existing automatic investigation. Its independent financial gate requires:

- Exact dispute/capture/order linkage and matching merchant identifiers.
- Completed order, captured payment or the specifically recognized buyer-complaint
  hold, matching full USD amounts and policy limits.
- Current provider eligibility and the exact Sandbox `accept-claim` action link,
  with `REFUND` explicitly allowed.
- A completed, current investigation, no seller-favor/conflicting conclusion and
  no unreadable/pending/uncertain uploaded transcription.
- The merchant's test-order/no-fulfillment policy, independently of an AI finding.
- No prior refund record, including pending, and no earlier action for the dispute
  **or the capture**, across policy replacement or reconnection.

Uploaded delivery claims, OCR, maps, fictional records and AI preference cannot
authorize money movement or prove fulfillment. Other transactions and unsupported
seller-favor cases abstain. No carrier-authentication integration was added, so the
agent does not submit unverified shipping information as seller proof. Existing
human-authorized provider adapters remain recoverable; no outside witness contact
or evidence disclosure was newly authorized by this feature.

## Dispatch and verification

Paused investigations abstain. New account evidence and provider-source updates require the version-nine worker; older workers cannot consume those jobs during rollout. Provider polling has a ninety-second wall-time limit so an unavailable provider cannot indefinitely block other investigations.

The private PostgreSQL ledger reserves policy budget and inserts a unique intent
atomically. A `sending` barrier commits **before** HTTP dispatch and checks that the
case revision and authorization are still current. Unique merchant/dispute and
merchant/capture constraints prevent two full financial actions. Workers coordinate
through PostgreSQL locks; replacing a policy does not reset deduplication. Crashes,
ambiguous responses and unknown dispatches retain the reservation and never cause
an automatic POST retry. This prioritizes abstention over a possible duplicate.
An interrupted prepared intent may therefore require advanced review.

The only new financial operation is Sandbox `accept-claim`; it is not combined with
a separate capture-refund request. No production-money host or Sandbox adjudication
simulator is called. PayPal's live dispute detail is read after a write and on later
checks. HTTP success alone means neither resolved nor refunded. `Resolved` requires
PayPal's terminal status; a displayed refunded amount requires its explicit
`dispute_outcome.amount_refunded`. A merchant token does not expose the buyer's
wallet balance. Original response uncertainty remains in the action record.

## Verified results and current limits

Actual checks on 2026-11-08, not simulated customer outcomes:

- Two separately registered QA accounts uploaded an authored printed screenshot
  and an image-only PDF. Actual Tesseract extracted USD 812.02 and TEST-2048.
  The long tracking string was uncertain in offline OCR; no expected digits were
  inserted. Real Gemini image reading separately read that string.
- Both uploads triggered actual source-linked Gemini investigations without an
  analyze request. Cloud originals, extraction, analysis and isolation survived a
  local server restart. API QA accounts are not two independent human testers.
- A public-domain Library of Congress handwritten manuscript was read by actual
  Gemini image requests. The opening phrase was found; faded final words were
  marked uncertain. One manuscript is not a general handwriting benchmark.
- A consented QA account uploaded that manuscript and a blank page through the
  real ingestion workflow. Both received uncertain extraction; the blank was
  classified unreadable. The investigation finished with a valid audit history.
- Real PostgreSQL assertions exercised reservation, duplicate blocking, stale
  evidence, single dispatch, unknown responses, replacement policy and revocation
  in a transaction rolled back without any provider HTTP action. Fault-injection
  tests additionally cover timeouts and lost response commits.
- **The actual existing USD 1 dispute remains open.** Fresh PayPal dispute, capture,
  order and refund reads found an existing **USD 0.60 PENDING refund**. A second
  financial operation is blocked. No new refund or dispute write was sent in this
  release, and no completed end-to-end refund is claimed. Following explicit merchant chat approval, a USD 1 per-claim / USD 1 total / one-action policy was enabled for twenty-four hours. The deployed background agent independently abstained on the pending refund; no budget was reserved. [Enablement](autonomous-merchant-enablement.json) and [actual abstention](autonomous-live-abstention.json) record that outcome. A clean eligible test dispute is still needed for a genuine write test. The app has the dispute-create scope, but no delegated buyer OAuth consent is configured. PayPal documents that separate consent requirement; a checkout approval is not a substitute. No fresh payment was created without a usable, authorized API-only dispute flow. [Actual eligibility check](autonomous-api-only-eligibility.json).

Free hosting can sleep and does not guarantee continuous worker execution. The
durable queue resumes when a service instance runs. OCR is English-first;
multilingual text, dense tables, difficult handwriting, manipulated documents and
hidden PDF text layers still need careful source inspection. Neither OCR nor the
semantic model authenticates documents. No independent penetration test or broad
OCR benchmark was performed. Browser control remains disabled; UI checks use React
rendering/API tests, not a claimed interactive browser session.

Reports: [local upload](autonomous-ocr-local-upload.json),
[automatic investigation](autonomous-ocr-local-investigation.json),
[restart](autonomous-ocr-local-restart.json),
[printed vision](autonomous-vision-printed.json),
[handwriting](autonomous-handwriting-evaluation.json),
[ledger/security](autonomous-ledger-security.json),
[actual PayPal preflight](autonomous-sandbox-preflight.json).

Official references: [Tesseract](https://tesseract-ocr.github.io/tessdoc/),
[PDFium wrapper](https://pypdfium2.readthedocs.io/en/stable/python_api.html),
[Gemini images](https://ai.google.dev/gemini-api/docs/image-understanding),
[Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing),
[PayPal accept claim](https://developer.paypal.com/api/customer-disputes/v1/disputes-accept-claim),
[PayPal Sandbox testing](https://developer.paypal.com/disputes/test-go-live),
[public manuscript and rights](https://www.loc.gov/item/mal4356500/).

A compatible, current reassessment can be queued atomically with its audit marker when a previously completed investigation uses an older payload schema. The queue and case update share a database transaction; the same unchanged payload is not repeatedly force-retried. The hosted check initially rejected a JSONB validation expression before mutation, then passed after a separate corrective migration. Existing originals and the audit prefix were verified intact. [Actual queue check](autonomous-atomic-reassessment.json).
