# Architecture

`backend/saas_app.py` is the account API. The built React frontend calls FastAPI on the same origin. Browser sessions use HttpOnly cookies. FastAPI holds the provider credentials and calls fixed-operation RPCs in PostgreSQL.

| Directory | Responsibility |
| --- | --- |
| `backend/` | FastAPI, provider adapters, OCR, investigation and workflows |
| `frontend/` | React workspace, source graph, witness portal and maps |
| `supabase/migrations/` | Database schema, private RPCs and ownership policies |
| `scripts/` | Release tools and isolated-environment acceptance checks |
| `evaluation/` | Reproducible synthetic evaluations and frozen results |
| `third_party/` | Upstream license and attribution notices |

## Account and data boundaries

Argon2id protects passwords. Session and recovery tokens are stored as hashes. Server-only RPCs resolve the session and perform account operations under a restricted executor role with forced row-level security. Cases, files, snapshots, witness responses, jobs and audit records persist in PostgreSQL.

Evidence ingestion retains original bytes and hashes. A durable job reads documents, collects supported references, compares addresses and produces an assessment. The job uses revision checks and leases to guard concurrent work. Gemini 3.1 Flash-Lite handles structured claim extraction and semantic review. Gemini 3.5 Flash-Lite can take over after eligible errors. Mechanical checks bind claim quotes to stored source passages.

Witness links have restricted scope and expiry. Reassessment retains earlier records in the audit trail. PayPal action authorization uses a separate merchant policy and server-side eligibility checks. [Security boundaries](SECURITY.md) · [PayPal integration](PAYPAL.md)

## Compatibility

The local launcher and `backend/app.py` provide a separate operator and fictional workspace backed by SQLite. The Docker default retains that entry point for compatibility. The hosted account app explicitly selects `saas_app:app` and uses cloud storage.