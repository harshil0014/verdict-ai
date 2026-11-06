# Architecture

`backend/saas_app.py` is the account application. React calls same-origin FastAPI with an HttpOnly cookie. Only FastAPI has the cloud secret and Gemini key. `saas_auth.py` uses maintained pwdlib/argon2-cffi, not a custom password algorithm.

```mermaid
flowchart LR
  B[React: accounts, cases, graph] --> A[FastAPI account API]
  A --> R[Fixed-operation PostgreSQL RPC]
  R --> S[Resolve hashed session]
  S --> P[Restricted role and forced ownership RLS]
  P --> D[(Private cloud PostgreSQL)]
  A --> G[Gemini investigation]
  W[Scoped witness link] --> A
```

## Ownership and authentication

Registration atomically creates an account/session. Passwords use Argon2id; only SHA-256 hashes of random session/recovery tokens are stored. Sessions last 30 days; recovery rotates the key and revokes all prior sessions. Usernames avoid simulating verified email when public email delivery is unconfigured.

The fixed-operation `public.verdict_saas_api` is SECURITY INVOKER with EXECUTE only for the server service role. After resolving an active session it sets a transaction-local actor and drops privileges to `verdict_saas_executor` (NOLOGIN, NOBYPASSRLS). Forced RLS compares row ownership with that actor for cases/files/requests/audit/jobs. The client cannot supply its owner. The private schema is not exposed in PostgREST and ordinary roles lack grants/RPC execution.

Server secret compromise or a privileged administrator remains outside this ownership boundary. Authentication operations use the privileged server role; that key never reaches React. Shared pacing/quota metadata has separate restricted policies.

## Atomic persistence

Cases are revisioned JSONB; audit events are separate append-only rows. A row lock and expected revision reject stale updates. Case, original bytes, request completion and hash-linked event commit in one transaction; validation errors raise and roll back all changes. Downloads recompute SHA-256. Audit continuity proves internal consistency, not evidence truth or resistance to a privileged administrator.

Originals use cloud PostgreSQL bytea, bounded to 5 MB/file and 20 MB/account. This avoids split case/object-store commits in the free beta. Scaling requires a private object store with a reviewed finalization protocol, retention and backup plan. No account state depends on ephemeral Render files or SQLite.

## Investigations and witnesses

The existing engine retains typed Gemini extraction, separate support review, citation checks, comparisons and graph pruning. Consent gates transmission. A durable 15-minute job lease plus case revision prevents stale results replacing current work. Failures retain prior analysis. Database-backed shared pacing replaces legacy local model pacing; failed attempts count toward daily caps.

Witness tokens are random, hashed in storage, expire after seven days and permit one response. Only the question is exposed. Recipient binding comes from the stored request, not reply JSON. Reply/original/revision/audit completion is atomic. Bearer possession does not verify respondent identity.

## Public research boundary

`research_routes.py` separates public research proposals from official case evidence. `free_search.py` uses documented Tavily keyless and Wikimedia/Crossref APIs; no API key, credit card, scraped SERP or paid fallback. `google_research.py` uses the official Gen AI SDK for consented URL Context. Google's paid 3.x Search grounding is disabled after both free 2.5 options returned 404. Provider summaries stay research-only.

`public_web.py` performs a bounded single-document fetch, validates all resolved addresses/redirects and pins the actual network destination while preserving TLS SNI. `extract_public.py` runs offline Trafilatura/pypdf extraction. Cloud research drafts have forced ownership RLS; approval uses the existing atomic case/file/audit transaction, binds exact snapshot/text hashes and marks the analysis stale. Search snippets and inaccessible documents cannot be approved. [Detailed provenance and provider selection](PUBLIC_RESEARCH.md).

## Legacy boundary

`backend/app.py` remains a separate SQLite operator application with the optional snapshot mirror, fictional exploration and sandbox PayPal. It does not read account tables. Docker's module switch and the preserved legacy branch/service keep the working release recoverable. Cloud schema changes do not overwrite old data. See [deployment](DEPLOYMENT.md).
