# Security model and limits

The account application provides durable private workspaces. It is a public beta, not an independent penetration test, compliance claim or financial-service certification.

## Implemented

- Maintained Argon2id password verification, 12–128-character passwords, dummy-hash verification for unknown users and generic login errors. Persistent account/IP attempt limits; forwarded IP headers are not trusted, so proxy IP limits can be coarse/shared.
- Random 256-bit sessions/recovery keys, hashed in PostgreSQL. HttpOnly, SameSite=Lax cookies, Secure on HTTPS. Logout revokes the session; recovery rotates the code and revokes every old session. No email, MFA or SSO is claimed.
- Fixed-operation server RPC, private schema and restricted executor with forced ownership RLS. Endpoints authenticate and cloud operations revalidate the session. Foreign cases/files/exports/updates return 404. Client-supplied owners are rejected.
- Same-origin writes, host allowlist, CSP, no-referrer, no-sniff and no-store API responses. React escapes evidence and model text. Account changes clear private UI state; responses from an old authentication generation are discarded.
- Atomic case/original/request/audit commits, revision checks and durable investigation leases. Corrupt originals fail closed. Cloud failure produces an error, never local fallback.
- Bounded TXT/JSON/text-PDF ingestion; no HTML/executable/image upload. PDFs run in timed subprocesses with additional POSIX resource bounds. This is not malware scanning or a complete document sandbox. Originals download as attachments.
- Scoped single-response witness portals with expiry/revocation and stored recipient binding. A link does not authenticate its holder's identity.
- Gemini receives case evidence under the account's investigation consent; provider data terms still apply. No automatic email or financial action in account mode. The account-scoped PayPal bridge is sandbox-only and read-only, with separately restricted operator functionality. [Authorization, private originals and minimized projections](SAAS_PAYPAL.md).

## Evidence and limits

Delivery location comparison is local-only by default. A per-case affirmative authorization enables bounded Photon geocoding; PIN-area mode transmits only the public area code. Address mode omits unit/floor details but cannot guarantee removal of names embedded in address text, which the consent disclosure explains. Source-anchored extraction never accepts model-invented coordinates. Case-private raw responses/hashes, quote links and derived comparisons use existing tenant RLS and audits. Fixed provider URLs, no redirects, bounded responses, shared daily/per-account quotas, persisted pacing/caches and no paid fallback limit exposure. Leaflet popups use DOM text nodes. The explicit OSM tile image host is allowed by CSP; tile requests use an origin-only referrer while other app requests retain no-referrer. Loading tiles shares the browser IP and viewed geographic area only after the disclosed authorization. [Detailed controls and limits](DELIVERY_LOCATION.md).

Public web proposals use a separate private RLS table and server-only RPC. Direct retrieval rejects private/reserved addresses, credentials, unsafe ports and redirects, pins DNS-validated destinations with TLS verification, and executes no page scripts. Exact-byte/text hashes bind approval to the preserved source; a Google/Tavily summary cannot become evidence. Documented keyless APIs are explicitly selected; API-key environment variables are never consumed for search. Provider cooldown persists across server replacement. See [public research controls and actual tests](PUBLIC_RESEARCH.md).

[Acceptance results](SAAS_ACCEPTANCE.md) separate HTTP contracts from actual cloud tests: two independent accounts, foreign reads/writes/files/exports/analyses/requests, original hashes, logout/recovery, atomic rollback and stale revisions. Actual database-role checks cover foreign rows across five relations, denied foreign updates/inserts and denied anonymous RPC/schema access.

The cloud security advisor returned informational RLS-without-policy notices for server-only accounts/sessions/rate-limits and legacy snapshots, with no warning/error finding at that check. These tables deliberately have no ordinary-role grants or policies. This is not proof of absence of vulnerabilities.

Remaining: organization sharing, SSO/MFA, verified email, malware scanning, OCR, independent source identity verification, externally anchored audit, comprehensive redaction, independent penetration testing and certified backup restoration. Self-service account deletion/retention controls are not implemented; do not use the beta for records requiring a verified retention/deletion process. Export important cases. Free cloud quotas/suspension may cause downtime; paid capacity is never enabled automatically.

An administrator/server-key holder can alter data and recompute hashes. Prompt-injection detection is incomplete; the model has no external action tools or authorization bypass. Exact quotes and model support judgments do not prove real-world truth.

## Publication

Never publish `.env`, runtime databases, user credentials, recovery/session/portal tokens, private sandbox details or customer records. Ignore rules and the publication audit cover these paths. The scanner inspects all local Git objects including unreachable ones, history paths and nonignored release files against patterns and exact private values. Independent Gitleaks checks complement it. Public reports omit account identifiers. Dependency license texts remain in `third_party/`.
