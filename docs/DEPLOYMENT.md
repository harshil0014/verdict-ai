# Deployment and recovery

The simplified product release adds `20261108075136_product_experience_preferences_and_recovery.sql` and `20261108080516_provider_retry_after_cooldown.sql`. Apply in order after the delivery-location migration. They add private account map preferences and persisted retry eligibility without deleting existing account/evidence records. Compatible workers identify as version 5; old retained workers cannot consume newly versioned jobs. No new service/key/paid capacity is required. [Executed acceptance and recovery limits](PRODUCT_EXPERIENCE.md). Keep `release/location-working-20261108` for application recovery and retain all additive cloud migrations.

Apply the subsequent `20261108134238_future_investigation_map_consent.sql` scope hardening as well. It preserves the private preference and revocation behavior while preventing permission enablement from starting new lookups across older cases. Its live RPC behavior was verified with a rolled-back, isolated QA transaction; it requires no application redeploy or paid resource.

Smart Delivery Location Verification adds `20261107191843_smart_delivery_location_verification.sql`, a service-only shared geocoder quota/pacing RPC and worker-version compatibility trigger. Apply after earlier migrations; no new paid service, geocoder key or database table is required. `VERDICT_GEOCODING_ENABLED=false` disables external lookup; local comparisons and preserved records remain. New cases default to local-only location processing until per-case authorization. [Architecture, privacy and verification](DELIVERY_LOCATION.md). Preserve `release/paypal-saas-working-20261108` at `0254738` and never down-migrate user data for an application rollback.

For the account-scoped read-only PayPal sandbox bridge, apply `20261107100159_account_paypal_sandbox_import.sql` and `20261107103919_paypal_connection_lock_order.sql` after earlier migrations. Bind the owned test merchant through the server-only provisioning RPC and configure matching `VERDICT_PAYPAL_DEMO_OWNER_ID` / `VERDICT_PAYPAL_DEMO_MERCHANT_ID`, alongside server-only sandbox credentials. Do not provision public users against shared credentials. [Scope, setup and executed checks](SAAS_PAYPAL.md). The prior application is preserved at `release/claim-inspector-working-20261107`; its recovery must not down-migrate or delete account data.

The evidence-triggered automatic release is live at application commit `6ef3b8d4897d539c1754600d90d9ea78ca0f20fd`. The main service became live at 2026-11-07 04:41:21 UTC; its fresh upload/retrieval/investigation acceptance passed at 04:43:08 UTC. [Executed release checks](AUTOMATIC_INVESTIGATION.md). Apply the two new automatic-workflow migrations in filename order before upgrading another project. The worker runs inside the existing free web process, coordinates leases in PostgreSQL and resumes on an awake instance; no extra paid worker/Redis/cron service was added. `VERDICT_AUTOMATIC_WORKER=false` disables only the local process runner, retaining queued work for another runner/restart. Both public services run it normally. Preserve `release/public-research-working-20261107` for the prior working public-research application; do not down-migrate user data for an application rollback.

The public research upgrade is live on both free services at application commit `9a3ae66`. Its separate preview passed before the main replacement, which became live at 2026-11-06 19:39:30 UTC. Primary verification completed at 19:42:32 UTC: original snapshots, exact graph passages, old account/witness data, real retrieval/approval/investigation and logout/return remained functional and private. [Release evidence and incidents](PUBLIC_RESEARCH.md). Google paid Search grounding remains disabled; Tavily keyless and Wikimedia/Crossref need no account, card or API key. Apply the two new timestamped public-research migrations before deploying to another project. Preserve `release/saas-working-20261107` for the preceding account release; do not reverse cloud migrations to roll back application code.

Account mode uses the existing cloud database and a free Render web service. No paid resource or automatic paid overflow is authorized.

| Server variable | Value |
|---|---|
| VERDICT_APP_MODULE | `saas_app:app` |
| VERDICT_PUBLIC_HOST | Exact public hostname without scheme |
| VERDICT_SECURE_COOKIES | `true` on HTTPS |
| VERDICT_AUTH_PEPPER | Stable random secret, at least 24 characters |
| SUPABASE_URL / SUPABASE_SECRET_KEY | Private project URL and server-only key |
| GEMINI_API_KEY | Server-only model key |
| GEMINI_MODEL | `gemini-3.1-flash-lite` |
| VERDICT_ALLOW_SANDBOX_ACTIONS | `false` |
| VERDICT_SUPABASE_MIRROR | `false`; account storage already cloud-primary |

Apply timestamped SaaS migrations in filename order before startup. No startup DDL or secret in committed plaintext. Startup fails closed if cloud connectivity/configuration is missing. `/api/health` checks actual cloud RPC connectivity; use it for HTTP readiness. A live deploy must pass acceptance, not merely a TCP probe.

All user cases, originals, responses, sessions, jobs and audits are cloud-primary. Ephemeral compute is replaceable. Free services can sleep; cloud quotas still apply. Database backups and full restore drills remain a separate operational requirement.

## Release and recoverability

1. Preserve `release/legacy-working-20261106` at the prior working release. Leave its existing operator service untouched during separate account-service validation.
2. Run tests, frontend build, real cloud lifecycle/restart checks, secret/history scans and attribution review before public source pushes.
3. Deploy `saas` to a separate **free** account service. Wait for its named deploy to be live; check health/config and both accounts against persisted originals, investigation digests, witnesses and audit hashes.
4. Replace the application with a subsequent deploy and repeat checks. Only then designate it as the public product/update links. Source promotion does not itself change the manually deployed legacy service.
5. After acceptance, promote the reviewed source to `main`, preserve the legacy environment privately, and switch the original service to `saas_app:app` with the same cloud database. Repeat account/original/audit/isolation verification at the original URL. Keep the independently validated account service available during this promotion.

The separate free service passed replacement-deploy acceptance at 17:16:19 UTC on 6 November 2026. [Recorded checks and incidents](SAAS_ACCEPTANCE.md). The Blueprint declares HTTP readiness; the direct service-creation tool currently leaves Render's platform probe at TCP. Startup checks cloud RPC, and HTTPS `/api/health` is verified separately. No continuous monitoring or paid SLA is claimed.

The original URL was promoted only after that pass. It became live at 17:21:31 UTC and passed the same two-account persistence/isolation checks at 17:22:55 UTC. [Primary application](https://verdict-ai-harshil0014.onrender.com) · [Independent validation service](https://verdict-saas-harshil0014.onrender.com). Both use the same durable primary database and remain on free compute; no paid resources were activated. Legacy source and a private recovery environment are retained separately. These source/configuration recovery artifacts are not a backup of volatile legacy demo cases or a certified database restore procedure.

The compatibility Docker default is `app:app`; legacy source and private configuration remain recoverable. That SQLite application cannot read SaaS account tables. Do not route user accounts there as if it provided their workspaces. Rolling back an application does not delete or roll back cloud data; avoid destructive down migrations. A retained source branch is not a database backup.

Operational references: [Render deploy lifecycle](https://render.com/docs/deploys), [database-aware HTTP health checks](https://render.com/docs/health-checks). A successful deploy trigger alone is not a live verification.
