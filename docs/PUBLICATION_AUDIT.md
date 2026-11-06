# Public-source audit — 6 November 2026

## Persistent account release

The SaaS branch adds real accounts and PostgreSQL primary storage, separate from the preserved operator release. Before its public push, exact/private-value scans were repeated against all local Git objects, including unreachable objects, history paths and nonignored source. Ignored account passwords, recovery keys, portal tokens and the authentication pepper were included in exact matching. Zero findings. Gitleaks 8.30.1 independently reported no leaks in all-branch history and the publication-only tree.

The release includes 102 passing local tests, a production frontend build, real-cloud two-account/restart/security reports, actual account UI captures, architecture/setup/security/recovery documentation and unchanged honest evaluation results. New pwdlib, argon2-cffi/bindings, cffi and pycparser notices are retained, including upstream Argon2 terms. Dependency licenses retain their scope alongside original MIT code; provider service terms are separate.

Deployment replacement acceptance is tracked in [SAAS_ACCEPTANCE.md](SAAS_ACCEPTANCE.md). Source publication alone is not a claim that the upgraded service is deployed. The original audit below describes the earlier operator release.

The owner explicitly authorized a public repository under `harshil0014`. Publication includes the functioning frontend/backend, tests, schemas, setup/deployment configuration, authored fictional data, research and honest evaluation. It excludes private runtime and credentials.

## Secret and data checks

- Independently scanned every local Git blob, commit and tag object, including unreachable objects, and inspected every reachable/reflog commit path. Compared against private local credential values and private Supabase project identifiers without logging those values. No matches found.
- Ran upstream Gitleaks **v8.30.1**, downloaded from its official release with the published archive SHA-256 verified. Scanned all branch history and a separate publication-only working tree with full redaction enabled. No leaks found. These scans are repeated against the final publication commit.
- Checked ignore rules for `.env`, virtual environments, node_modules, runtime/session/bootstrap state, work files, compiled assets, caches, logs, private-key containers and CLI-local state. `.env.example` contains names/placeholders only.
- Reviewed the actual application screenshot: only fictional demo records, no API credentials, private customer records, browser account chrome or Supabase project identifiers. The original frame is preserved and its capture limitation is disclosed in the README.
- Evaluation inputs, labels and model outputs are authored fictional cases. Private Supabase snapshots, original local databases, invitations and session tokens are excluded. Public connection reports expose only redacted status/count/configuration evidence.

No secret scanner can prove the absence of all sensitive information. Exact-value matching, generic rules, path/history inspection and visual/document review provide complementary checks. No credential rotation is indicated by the inspected publication history; local credentials remain private.

## Dependencies and attribution

Inspected all 90 installed npm package manifests and their license declarations: MIT, ISC, Apache-2.0, BSD-3-Clause and CC-BY-4.0. Retained 86 available package-root license texts. CC-BY-4.0 caniuse-lite data attribution is explicitly retained. Inspected every locked Python distribution and retained its available license/notice texts. The unmodified certifi bundle retains MPL-2.0; typing_extensions retains PSF-2.0; these component licenses are not replaced by the project MIT license.

No competitor application code or proprietary UI assets were copied. Research influences are attributed with inspected source paths, licenses and commits. See [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) and [RESEARCH.md](RESEARCH.md).

## Supabase boundary review

Read-only metadata confirmed snapshot-table RLS enabled and forced, with no SELECT grants to anonymous or ordinary authenticated roles. Fresh security advisors identified unnecessary execution grants on a setup-generated `SECURITY DEFINER` event-trigger helper. An idempotent migration revoked `PUBLIC`, `anon` and `authenticated` execution without changing its owner or automatic RLS event trigger. Verification confirmed both API-role grants are false, owner execution remains true and the automatic trigger remains enabled.

After hardening, security advisors contain only the informational **RLS enabled with no policies** notice. This is intentional: snapshots are server-only and have no client-facing row policies. Do not add permissive policies to silence it. [Advisor explanation](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy), [function-execution guidance](https://supabase.com/docs/guides/database/database-linter?lint=0028_anon_security_definer_function_executable).

## Functionality and documentation

The release contains actual FastAPI routes, server sessions and tenant checks, immutable-source ingestion, scoped one-response portals, SQLite transactions, private snapshot mirroring, Gemini extraction/support assessment and a sandbox PayPal adapter. It does not rely on a mock frontend server or hardcoded chatbot sequence. Mock transports exist in isolated tests; fictional data and unverified external lifecycle operations remain explicitly labeled.

README, [architecture](ARCHITECTURE.md), setup instructions, genuine screenshot, [security boundaries](SECURITY.md), [provider capability ledger](PAYPAL.md), tests and [frozen evaluation](EVALUATION.md) accompany the source. Initial conclusions tied the checklist baseline at 28/30; request-topic matching does not establish independent evidence availability or real dispute outcomes.

Live PayPal evidence submission, registered webhook delivery, stable hosting and the public demo video remain separate work. Publication of source does not certify those integrations or production readiness.
