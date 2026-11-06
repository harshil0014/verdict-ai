# Build status — 6 November 2026

## Verified continuation after public release

- Public source: [harshil0014/verdict-ai](https://github.com/harshil0014/verdict-ai); anonymous clone/metadata verification and successful remote application/container jobs. [Publication record](PUBLICATION.md).
- Actual USD 1.00 sandbox order buyer-approved and captured once; independent order/capture APIs confirmed completed status, one capture and amount/linkage. A real buyer-created inquiry was imported and its capture/order linked. Update-time-filtered listing returned the case. Two individually approved `OTHER` notes attempts were rejected; the diagnostic attempt identified an unrequested evidence type. Sandbox writes restored to disabled. [PayPal ledger](PAYPAL.md).
- Real container hosted on free Render. HTTPS fictional-case upload, model analysis, scoped witness/reply and reassessment exercised. Optional-provider status bug found and fixed; corrected deployed-build verification tracked in [deployment notes](DEPLOYMENT.md). No payment credentials/writes on the host. Free-host sleep and ephemeral state prevent an always-on/durable claim.
- Local suite expanded to 60 passing tests and frontend production build passed. New coverage includes concurrent checkout exclusion, no recapture, exact-case import authorization, `OTHER` payload approval/replay, optional-provider failure isolation and bounded rejection diagnostics. External provider tests remain distinct from transport mocks.
- Frozen eight-case custody-aware research: both strategies acquired 3/6; matched-evidence findings tied 3/3. Original v1 results unchanged. No production prompt/schema promotion. [Follow-up report](CUSTODY_EVALUATION.md).

Update: two notes attempts were individually approved and rejected; the diagnostic attempt identified HTTP 400 `EVIDENCE_TYPE_IS_NOT_ALLOWED`. No note was accepted. The requested-type gate now blocks unrequested evidence before approval. The hosted `d97d283` build passed all 22 HTTPS checks; [verification record](deployment-verification.json). The historical sections below describe the original 5 November build; current ledgers supersede its zero-dispute, no-host and no-remote-CI statements.

## Implemented and exercised

- Integrated local application at `http://127.0.0.1:8000/`; case inbox/search/filter, source library and inspector, interactive real-data evidence/claim/hypothesis graph, human review, JSON export and audit timeline.
- Real Gemini extraction and semantic-support calls using verified `gemini-3.1-flash-lite`. Model output is validated; failures preserve prior investigation. Shared local pacing addresses the provider's observed 15 RPM limit.
- Evidence text, JSON and text-bearing PDF upload, original download, file limits, PDF subprocess timeout, source quotation and structured-value checks. Explicit timezone arithmetic is normalized in code, not guessed by the model.
- Targeted requests, editable human review of question/recipient, restricted one-response portals, expiry, submitter-role binding, stale-analysis detection and reassessment.
- Browser test: actual initial model finding of insufficient evidence → request created → fictional carrier record submitted through the portal → case marked stale → actual model reassessment to buyer-supported → changed graph and recorded timeline. Source inspector retains the original quote and identifies the upload as origin-unverified.
- Desktop navigation/inspection was exercised. Mobile DOM check measured a 390×844 CSS viewport, no horizontal document overflow and the mobile sidebar breakpoint. Final screenshot capture in the connected Edge browser was unreliable; this is not claimed as comprehensive pixel-perfect mobile QA.
- Actual PayPal sandbox OAuth/list responses 200/200, zero disputes.
- Existing Supabase project: migration applied; RLS enabled and forced, no anonymous/authenticated SELECT grants; six operator-case snapshots written and read back. Durable local outbox behavior tested under cloud failure. SQLite remains the primary store.
- 30 fictional cases evaluated against A/B and matched-new-evidence B. Results and limitations are recorded without an overall superiority claim.
- Source is MIT licensed; lockfiles and upstream frontend license texts retained. Original credential file is preserved and excluded from Git and packaging.

## Tested in isolation

Automated tests exercise tenant/session/portal isolation, source and structured checks, timezone normalization, stale revision protection, file rejection and positive PDF extraction, audit modification detection, cloud retry behavior, action approval binding/replay/unknown results, HATEOAS URL restrictions and webhook duplicate handling. External PayPal operations in these tests use mock transports; those tests do not certify the account's ability to execute those operations. Local frontend production compilation passes. CI has not run remotely.

## Partial or externally unverified

- PayPal detail/import, capture/order retrieval and message/tracking/accept-claim actions are implemented, but no eligible actual dispute exists to exercise them. Writes default off. No sandbox dispute was fabricated to conceal this.
- Webhook verification/ingestion endpoint exists and fails closed, but no public HTTPS webhook registration or live delivery has been tested.
- Provider evidence submission currently supports tracking metadata and notes, not arbitrary binary attachment submission.
- Source quotations and structured values are mechanically checked; semantic support, entity alignment, hypotheses and summaries remain fallible model judgments. No real-world truth or outcome verifier exists.
- Cloud snapshots are a private mirror; raw attachments, sessions and action reservations remain on local disk. Cloud disaster recovery and multi-instance operation are not implemented/certified.
- Docker and Render configuration are prepared; Docker is not installed here and the image has not been built. No hosted application URL exists.

## Explicitly fictional or simulated

The six sample workspace cases, 30 evaluation cases and carrier witness record in the demonstration are authored fictional data. The model calls, portal submission, storage, graph update and reassessment are real operations. The evaluation witness inventory is a simulated oracle unlocked by a topic screen, not an external carrier integration. Model/topic screen results are not real financial outcome labels.

## External steps pending

1. Public source publication under `harshil0014` was explicitly approved on 6 November 2026. Final publication/anonymous verification is recorded separately. Hosted application deployment remains outstanding; no paid resource activation has occurred.
2. A buyer-approved sandbox transaction and an eligible sandbox dispute, followed by actual provider detail/evidence/action tests. The account's zero-dispute response is the current evidence; API creation scope alone does not establish the full flow.
3. Public HTTPS host verification, optional webhook registration/delivery, and a hosting continuity decision through judging. No paid service activation has occurred.
4. Record and owner-approve a genuine sub-three-minute video, publish it on YouTube, and complete final Devpost submission. Description/storyboard/checklist are drafted; no video or submission was published.

## Planned beyond this build

Independent human-labeled and held-out evaluations; stricter realistic witness-availability validation; human usability studies; OCR and complex invoice/table parsing if warranted; source identity validation; authenticated organization membership/SSO; malware scanning; audited backup restoration and production operations. These are not advertised as working features.

## Evaluation decision

Initial finding labels: A 20/30, checklist B 28/30, VERDICT 28/30. Request-topic matches on witness-eligible cases: A 10/25, B 9/25, VERDICT 21/25. Only 10 of the 21 topic-matched VERDICT requests also exactly matched the authored recipient category. After identical new evidence, VERDICT matched 20/21 versus B 19/21. These author-labeled development results do not establish superior reasoning or real PayPal results. They motivated an editable request/recipient review step in the product.
