# Deployment and recovery

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

The compatibility Docker default is `app:app`; legacy source and private configuration remain recoverable. That SQLite application cannot read SaaS account tables. Do not route user accounts there as if it provided their workspaces. Rolling back an application does not delete or roll back cloud data; avoid destructive down migrations. A retained source branch is not a database backup.

Operational references: [Render deploy lifecycle](https://render.com/docs/deploys), [database-aware HTTP health checks](https://render.com/docs/health-checks). A successful deploy trigger alone is not a live verification.
