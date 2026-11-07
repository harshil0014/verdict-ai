# Autonomous original-publisher recovery

Uploading evidence can trigger bounded retrieval, recovery and source-linked investigation without a separate search, approval or reassessment request. Human review still applies to conclusions and consequential actions. Retrieved sources remain explicitly unreviewed.

## Identity before evidence

The initial recovery adapter supports **British Columbia Civil Resolution Tribunal decisions linked by canonical CanLII neutral citations**. It extracts only the public year, tribunal code and decision number, then searches the existing free Tavily keyless/Wikimedia/Crossref providers. Case text, party names, customer identifiers and arbitrary URL paths are not sent as recovery queries. No individual decision URL is hardcoded in production.

Only API-returned links at the tribunal's configured original-publisher host are candidates. There is at most one citation recovery per workflow, two search candidates and one explicitly embedded same-document publisher frame, with three candidate fetches in total. A wrapper may yield its literal HTTPS iframe only when host and path are unchanged and the sole query is `iframe=true`. Its raw snapshot and hash remain in the private research record. This is bounded document acquisition, not recursive crawling.

A candidate becomes evidence only if its actual preserved text identifies itself as tribunal reasons for decision, names the indexed case with the **exact expected neutral citation**, and supplies an explicit issued date. The identity result includes the real header passage, offsets and extracted-text hash. A matching citation establishes document identity within the configured publisher; it does not authenticate every assertion or prove byte equivalence to the inaccessible CanLII copy. Investigations must still distinguish party reports from quoted adjudicative findings. Current documents do not establish past policy applicability.

The original refusal remains unchanged, including the unavailable research record. A recovered source adds requested/final URLs, retrieval time, raw/text SHA-256 hashes, discovery provider/query, identity check, parent evidence reference and a `public_source_recovered` audit event. Failed candidates remain inspectable. Search snippets, a URL in a model answer and recalled content never substitute for retrieved passages.

## Failure and security boundaries

Unknown documents and unsupported courts retain honest retrieval failures; this is not universal document matching. No HTTP 403 challenge is bypassed. HTTP 429 is not routed around; provider cooldowns, shared daily limits, account ownership, SSRF/DNS-rebinding controls, TLS verification, extraction limits and prompt-injection protections remain active. Known tracking parameters are removed from automatically submitted URLs; credential-bearing and unknown query parameters remain blocked.

The additive queue migration keeps existing case/research/evidence records. Enabled, previously partial CanLII/BCCRT cases are eligible for one bounded recovery pass. Paused cases remain paused. A worker-version requirement prevents old deployment workers from consuming new recovery jobs during rollout. PostgreSQL leases and case-before-workflow locks coordinate instances; only the server service role may claim or schedule work.

No new dependency, paid service, Google billing, proxy, browser crawler or credential is introduced. See [official tribunal decision-search guidance](https://civilresolutionbc.ca/help/how-do-i-search-crt-decisions/) and [Tavily keyless documentation](https://docs.tavily.com/documentation/keyless). Provider availability and free quotas are not guaranteed.

## Verification

Local checks: **203 Python tests**, seven real-component React rendering checks and the production TypeScript/Vite build pass. New tests cover exact/mismatched citations, spoofed publishers, privacy, existing failure recovery, wrapper integrity and restricted frames, retained refusals and automatic adoption. A regression verifies that recovery reads retained bytes after staging omits them, including PostgreSQL's line-wrapped base64. An initial wrapper-only attempt can resume once from its saved snapshot without another search; its earlier failure remains in history. These UI checks are not browser click-through tests.

`scripts/source_recovery_acceptance.py` creates two independent automated QA accounts. A single upload for the first contains only the blocked CanLII URL; a single upload for the second contains accessible BC legislation. It makes no manual search, research approval, retry or analysis calls. The executed hosted results are recorded separately after validation. The runner verifies actual Gemini results, source quotes, snapshot bytes, identity hashes, original failures, audit integrity, isolation, logout/login and persistence across deployment. Automated accounts are not a two-human usability trial. Workflow success does not change the frozen 28/30 model evaluation tie.
