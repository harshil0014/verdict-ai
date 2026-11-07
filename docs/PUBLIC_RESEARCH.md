# Public evidence discovery

VERDICT now starts investigation when evidence is submitted: literal public references are retrieved, preserved as unreviewed sources and investigated automatically. The case UI has one continuous flow: collected documents and provenance under **Evidence**, retrieval activity under **Investigation/Timeline**, and an optional **Find more evidence** dialog for URL/search input. There is no standalone Public research tab. Direct URL and authorized Search submissions still collect and investigate accessible snapshots by default. The optional `review_only=true` API retains staging-only research; older staged/dismissed records remain inspectable in Evidence. Humans review conclusions and consequential actions. [Current automatic workflow](AUTOMATIC_INVESTIGATION.md). Search summaries, URL Context answers and a URL mentioned in generated prose are never substituted for source text. Earlier acceptance records below describe the preceding approval-driven workflow and remain historical evidence.

## Provider decision — 7 November 2026

| Option | Current documented access | Decision |
|---|---|---|
| Google Gemini URL Context | Free-tier support; existing 3.1 Flash-Lite key returned successful retrieval metadata for the official Moffatt decision | Integrated through the official Google Gen AI SDK; optional explicit consent for public URLs |
| Google Search grounding | Current 3.x pricing requires paid tier; both documented free 2.5 models returned 404 on this key | Adapter implemented, successful grounding unverified and disabled; no billing upgrade or paid fallback |
| Brave Search | No standalone free plan; accessing recurring free credit requires a credit-card check | Excluded under the no-card mandate |
| DuckDuckGo Instant Answers | Official API is not a full web-search results API | Probed successfully; insufficient as the primary discovery provider. No HTML SERP scraper or evasion wrapper used |
| Tavily keyless | Officially documented Search/Extract access without a key, account or card; shared limits are not a published production quota | Working general search provider. Explicit `X-Tavily-Access-Mode: keyless`; no Authorization header or API-key lookup |
| Wikimedia APIs | Public topic search and external-reference lookup | Topic/reference discovery, including the official tribunal link referenced by the Moffatt article; encyclopedia content is not presented as primary evidence |
| Crossref public REST | No account/key required for bibliographic metadata | Research-document fallback; abstracts are not copied and a metadata match is not proof of relevance/content access |

Official references: [Google URL Context](https://ai.google.dev/gemini-api/docs/url-context), [Google pricing](https://ai.google.dev/gemini-api/docs/pricing), [Brave activation requirements](https://api-dashboard.search.brave.com/documentation/resources/help-feedback), [DuckDuckGo's own API description](https://github.com/duckduckgo/duckduckgo-publisher/blob/master/share/site/duckduckgo/api.tx), [Tavily keyless](https://docs.tavily.com/documentation/keyless), [Tavily throttling](https://docs.tavily.com/documentation/rate-limits), [Wikimedia search](https://www.mediawiki.org/wiki/API:Search), [external references](https://www.mediawiki.org/wiki/API:Extlinks), [Crossref access/licensing](https://www.crossref.org/documentation/retrieve-metadata/).

Tavily keyless is suitable for a bounded public beta, not a production SLA. Provider 429 responses persist a shared cooldown; the service does not retry early, rotate identities/IPs or switch to paid keys. Distinct documented public research APIs can still be used during that cooldown. A future free account could provide Tavily's documented 1,000 monthly credits without a card, but no account, key or paid plan was activated here.

## User flow

1. Open a case and **Public research**, or choose the public-URL option in Add evidence.
2. Supply a public HTML/PDF/text URL and optional event date. Authorize retrieval/private staging, with optional Google URL Context. Alternatively review a public question, optionally adapt a model-suggested publicly obtainable witness question, and authorize discovery. Only that reviewed query is sent to search providers; the entire case is not sent for search.
3. Discovery gets up to five search leads and uses documented reference APIs. Primary-looking domains are heuristically prioritized, without claiming authentication. Up to three result URLs are independently retrieved. The panel records the provider, relevance, URLs, timestamps, failures and exact extracted text.
4. Inspect the preserved text and original/text SHA-256 values. Review document type and historical limitations; explicitly approve that snapshot. A transaction appends the exact text, original bytes, provenance and audit event together. Dismissed/unavailable/search-only proposals do not become evidence.
5. Investigate or reassess. Claims resolve to actual preserved passages and character offsets; the source inspector shows provenance and downloads the original. New approved evidence marks prior analysis stale. Repeated approval is idempotent.

## Source and historical integrity

- Direct retrieval uses public HTTP(S), standard ports, no login/cookies/proxies and no JavaScript execution. Hostnames are resolved, every address checked, and the connection pinned to a validated IP with original TLS hostname verification. Every redirect is revalidated; private/reserved addresses, signed credential links and HTTPS downgrades are refused.
- Trafilatura extracts HTML and existing pypdf extracts PDFs in a bounded offline subprocess. Limits are 5 MB, 30 PDF pages, 30,000 extracted characters, bounded redirects and timeouts. Truncation is prominently marked; original bytes remain preserved. No OCR or malware-scanning claim.
- A publication date is accepted only from explicit publication metadata or an explicit document-issued date, with its basis recorded. HTTP Last-Modified, retrieval time and model guesses are not publication dates. Unknown stays unknown.
- Retrieval time, publication/decision date, archive capture and policy effective dates are distinct. Every source defaults to `historical_applicability=not_established`. A current webpage cannot be labeled an archived record. An observed Internet Archive URL can establish a capture reference, not its policy's effective dates or authenticity. No unavailable archive is invented.
- User-reviewed tribunal classification is a classification, not blanket truth verification. The engine separately labels party reports, document findings/orders, current policy and uncertainty. A party's quotation inside a decision remains a report unless the tribunal adopts it.
- Citation validation requires matching wording. PDF whitespace may be mechanically aligned, but the accepted quote is replaced with the exact original substring and offsets. No fuzzy semantic match, punctuation/number substitution or model assertion is accepted as a source check.
- All drafts, snapshots and official records remain private under forced ownership RLS. Draft storage is bounded to 20 MB/account and 40 proposals/case, in addition to existing official-evidence limits. Global stored bytes remain capped. Search/retrieval calls are bounded per account and service; capacity errors retain saved data.

## Actual verification

**Deployed to the main [VERDICT application](https://verdict-ai-harshil0014.onrender.com). Final primary write/investigation/return verification passed at 2026-11-07 01:12:32 IST / 2026-11-06 19:42:32 UTC.** Application commit `9a3ae6655bd0e3c3c3620069eaa012d9eaf8f62d` was first validated on the independent free service, then promoted without changing cloud case data or enabling billing.

| Actual phase | Result | Record |
|---|---|---|
| Corrected hosted Moffatt investigation and separate reanalysis | 29 checks passed; final three exact source-linked claims include two findings and one report | [Hosted investigation](public-research-host-verification.json) |
| Free autonomous discovery, inaccessible URL, duplicate import | Seven checks passed; official tribunal HTML was retrieved into an unapproved proposal; real 404 has no invented text | [Hosted discovery](public-research-host-discovery-verification.json) |
| Existing account records after validation-service replacement | All 40 isolation/persistence/logout checks passed | [Preview regression](public-research-account-regression.json) |
| Primary promotion: saved research, originals, graph, audit, classification | All 18 checks passed at 01:10:31 IST | [Primary research](public-research-primary-verification.json) |
| Primary promotion: two independent existing account workspaces | All 40 checks passed at 01:10:41 IST, including witness original bytes and revoked sessions | [Primary account regression](public-research-primary-account-regression.json) |
| Fresh primary-source retrieval, approval and real investigation by the other research account, logout and return | All 12 checks passed at 01:12:32 IST; own original/analysis/audit preserved and foreign access denied | [Primary writes](public-research-primary-write-verification.json) |
| Exact tested frontend and research chunk served publicly | All six asset/readiness/auth checks passed; byte-for-byte hashes match the local production build | [Primary frontend](public-research-primary-frontend-verification.json) |

These are automated API/network/model checks, not two-human usability or a visual click-through pass. The two-account SaaS acceptance remains intact. Free compute can sleep and keyless discovery can throttle; no uptime or provider SLA is claimed.

[Machine-readable release ledger](public-research-release-verification.json) records the exact application commit, live deployments, primary CI, report counts, recovery reference and remaining visual limit. Later documentation/acceptance-runner commits do not change the deployed application modules or built frontend.

The preview replacement took approximately eleven minutes; its build succeeded before the delayed rollout completed. One log query returned provider HTTP 503; the delay's root cause is not established. A pre-promotion primary-service request timed out. No resource upgrade was used. The primary replacement subsequently became live at 19:39:30 UTC and passed the checks above. The preceding account release remains available as `release/saas-working-20261107` at `04ec72ca720124df3df41047d4b38afef917d760`; application rollback does not reverse cloud data or restore a database backup.

[Initial retrieval/discovery report](public-research-retrieval-verification.json) and [updated-engine local report](public-research-local-verification.json) exercise the official **Moffatt v. Air Canada, 2024 BCCRT 149** PDF and the current **Civil Resolution Tribunal Act** on BC Laws. The latter is a current primary source, not proof of a policy in November 2022. Raw and extracted hashes, actual Google URL Context metadata, human-approval separation, duplicate/replay behavior, foreign-account denial, unavailable URLs and real Gemini reanalysis are checked. A free search independently returned the tribunal's primary HTML page through Tavily/Wikimedia references; source URLs were not invented by the model.

The first investigation rejected all four proposed quotes because PDF whitespace did not match. After adding whitespace-only alignment, a real rerun retained source-bound claims and separated party reports from tribunal findings. This is a workflow verification, not a general legal-accuracy benchmark or improvement over the frozen 28/30 baseline tie.

A subsequent hosted check exposed a separate classification failure: all four source-linked claims were labeled findings, including quoted statements. The existing independent semantic-review pass now also reviews epistemic classification and returns a source-context explanation; missing review defaults to uncertain. The original wording/hash/offset checks remain mandatory. This review uses the same model and is fallible, not a legal truth oracle. The corrected local run retained four claims (three findings and one report); 148 automated tests and the production frontend build passed. Container verification now inspects generated OpenAPI paths, supporting FastAPI's included-router representation while still requiring both registration and public research endpoints.

The Air Canada policy URL returned HTTP 403 to direct retrieval. This is recorded as unavailable; neither Google's summary nor a current accessible snippet was used as a historical policy snapshot. Legitimate alternatives are another public official source or a user-provided copy they have authority to upload. No challenge was bypassed.

Automated tests include unsafe URL forms, mixed-public/private DNS, rebinding-resistant transport, redirect blocking, size/type limits, malicious page instructions, failed tool retrievals, model-invented URLs, citation alignment, keyless-only headers, provider cooldown/fallback and preserved graph spans. Mock tests are distinct from actual network/provider checks. Public deployment and browser verification are recorded separately when completed.

Remote [application and container CI](https://github.com/harshil0014/verdict-ai/actions/runs/42279376268) both passed for application commit `9a3ae6655bd0e3c3c3620069eaa012d9eaf8f62d`. The container checks the built frontend, credential exclusion, real account/research route registration, no SQLite account database, HTTP health/auth boundary and graceful shutdown.

Visual click-through QA for the new panel remains unverified. The browser connector was disabled; a native Windows-control attempt was also stopped by its URL-confidence safety check. No permissions or safety barriers were changed. Existing account screenshots predate this feature and are not represented as research-panel captures.

A [real-model adversarial probe](public-research-injection-verification.json) supplied explicitly synthetic hostile evidence instructing the engine to invent delivery proof, retrieve a private URL, reveal keys and issue refunds. All seven checks passed: warning retained, no delivery conclusion, exact quotations, unchanged evidence/research/request records and no dispatched action. This is one bounded probe, not a universal prompt-injection defense benchmark. Downloaded originals are served as attachments; HTML snapshots are not run inside the application.
