# Security model and limits

This is a production-minded single-instance hackathon build, not a production financial service certification.

## Implemented boundaries

- Server-side eight-hour sessions, opaque random cookie, HttpOnly, SameSite Strict, logout invalidation. HTTPS deployments must set secure cookies. Operator password must contain at least 16 characters. Local launcher uses a single-use loopback-only bootstrap token stored under ignored runtime state; it is never logged.
- Demo workspaces have independently generated tenant IDs and cannot read the operator sandbox, other demo cases or integration details. Every case/file operation verifies tenant membership. Bearer witness portals expose only their specific question and accept one response before expiry. Intended recipient comes from the stored token record, not a client-supplied role. Possession of a portal token does not prove the respondent's identity.
- Same-origin write checks, explicit host allowlist, no permissive CORS, CSP, no-sniff, no-referrer and no-store API responses. React escapes source content and model text; no HTML evidence rendering.
- File size/type/page/extracted-text bounds; executable/HTML/image uploads refused. PDFs are parsed in a disposable subprocess with a 12-second timeout and additional CPU/memory limits on POSIX. Windows enforces timeout but not a process RAM limit. Parsing is not malware scanning. Original documents download as attachments; text extraction preserves page labels.
- Evidence is immutable within the current interface. New sources append; old analyses survive in the timeline. Optimistic revisions reject analysis results or writes based on stale input. An SHA-256 value supports byte integrity only.
- Exact quotation check rejects nonexistent sources and quotations. Semantic support is a separate model assessment. Only entailed reported claims can support hypothesis edges. Discrepancies compare a small allowlist of semantically assessed, model-extracted fields; scope normalization may be wrong and requires human review. Unknown/missing values do not prove a contradiction.
- Evidence is enclosed as data in structured model calls. Instruction-like text receives a warning. Pattern detection is incomplete; the stronger boundary is that the model has no external action tools and cannot bypass backend authorization. Generated summaries/recommendations are not comprehensively semantically verified: reviewers must inspect source claims.
- Operator source data is sent to Gemini only after per-investigation UI consent. Check the current Google API data terms before using real customer records. Demonstration records are fictional. No external email, SMS or carrier-system request is sent automatically.
- PayPal write approvals bind exact state/payload and expire; durable reservations, duplicate checks and unknown-result blocking live outside the LLM. Current provider capability is checked immediately before dispatch. A provider state can still change between the check and its own operation; PayPal is the final authority and may reject the request.
- Supabase private snapshot mirror is server-only: RLS enabled/forced, no anonymous/authenticated grants, service-role key never reaches the frontend. SQLite is the primary transactional database. A durable outbox retries snapshot backups. Cloud snapshots are not a tested full disaster recovery system; sessions, raw files and action reservations remain local. Deploy with durable private disk before enabling provider writes.

## Scope not yet certified

Multi-user organization membership/SSO/MFA, tenant administration, malware scanning, OCR, independent source identity verification, externally anchored audit logs, encrypted local disk management, comprehensive privacy redaction, backup restoration, multi-instance distributed locking, penetration testing, and production PayPal authorization. Do not place this service on an unrestricted public host with operator access enabled until deployment controls have been reviewed.

Local filesystem access can alter the database and recompute its audit chain. The audit verifies internal continuity, not protection against a privileged machine owner. Original evidence can contain misleading data even when its origin is authenticated.

## Secrets

The existing credentials are excluded from Git and release archives. No API key value is included in documentation, screenshots, test fixtures, built JavaScript or runtime API responses. No preexisting Git repository existed, so there was no tracked secret history to clean. Re-check staged files and all source before any publication. Never publish `.env`, sandbox buyer passwords, session/bootstrap tokens, raw runtime databases or portal invitations.
