# Security

Please report vulnerabilities privately through GitHub's security advisory reporting for this repository. Include the affected version, impact and reproduction details. Redact credentials and private evidence from reports.

## Account and evidence boundaries

- Argon2id password hashing, hashed random session and recovery tokens, persistent login throttling, and revocation on logout or recovery.
- Same-origin writes, host validation, security headers and HttpOnly cookies. HTTPS deployments use Secure cookies.
- Server-only RPCs and forced row-level security derive ownership from authenticated sessions. Clients cannot assign an owner or access raw provider snapshots directly.
- Uploaded originals are preserved with SHA-256 integrity checks and served as attachments. Image and PDF decoding run in bounded subprocesses. Optional Gemini image transcription requires separate authorization.
- Single-response witness links expire and can be revoked. A link authorizes submission without independently verifying the respondent's identity.
- Public evidence retrieval validates destinations and limits fetches and decoding. Extracted text is untrusted data. Exact citations and model support judgments establish what a source says, not whether its account is true.
- Location lookups require affirmative disclosure consent. Local text comparison remains available with external lookup disabled. [Location controls](DELIVERY_LOCATION.md)
- PayPal imports use the authenticated Sandbox merchant binding. Financial actions require the separate bounded policy, server eligibility checks and durable duplicate-dispatch protection. [PayPal integration](PAYPAL.md)

## Operating limits

The product is a beta. Its current controls do not constitute a penetration test, malware scanning, independent witness authentication, certified backup restoration or an externally anchored audit log. Administrators with database access can modify stored data and recompute hashes. Review provider terms before sending sensitive data.

Keep `.env`, account tokens, provider credentials, runtime databases and private reports out of commits. Run the publication audit before sharing release artifacts.