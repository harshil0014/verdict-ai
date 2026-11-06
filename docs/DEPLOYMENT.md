# Deployment preparation and operational contract

The real container application was deployed on 6 November 2026 at **https://verdict-ai-harshil0014.onrender.com** on Render's free Singapore plan. No paid resource was activated. Source publication is separately verified in [PUBLICATION.md](PUBLICATION.md). Docker is not installed on the Windows execution host; the separate GitHub Actions container job built and tested the real image remotely. [Run for the first deployed commit](https://github.com/harshil0014/verdict-ai/actions/runs/42188867300).

The first deployed build completed genuine HTTPS upload/download, consent rejection, Gemini analysis, scoped witness response, replay rejection, stale detection, reassessment and tenant-isolation checks. Its operator integration-status request failed when optional PayPal credentials were absent. That bug was fixed to report an unconfigured provider without hiding the other connection statuses. A fresh deployed-build verification record will be stored in `docs/deployment-verification.json` after the corrected build passes. Browser control is disabled in Work settings; this is API lifecycle verification, not fresh visual/browser certification.

## Hosting choice

The available Sites platform runs Cloudflare Workers, not the existing Python backend. A static frontend publication would leave investigation/auth/upload functionality disconnected. Preserve the integrated FastAPI service; prepare a container host such as Render. [Render Docker documentation](https://render.com/docs/docker), [persistent disks](https://render.com/docs/disks) and [free services](https://render.com/docs/free) must be rechecked at deployment time for current availability, quotas and sleep behavior. No paid disk or service activation is authorized by this configuration.

`render.yaml` deliberately keeps sandbox writes disabled. The deployed demo has no PayPal or Supabase credentials and uses a separate operator password and judge code stored privately. Only Gemini is configured for real analysis of fictional demo records. Free instance disk is ephemeral; cases, sessions and portal links can be lost on restart, redeploy or spin-down. The UI warns before working in this host. A durable transactional primary store is required for safe provider actions; private snapshots do not replace it. This is a working demonstration host, not continuously available production hosting. Auto-deploy is disabled so reviewed builds are deployed deliberately.

## Concrete publication sequence

1. Review the sanitized release, evaluation report and known limitations. The owner approved public source publication under `harshil0014` on 6 November 2026. Use the audited source state; do not activate paid resources without explicit authorization.
2. Create/push only the sanitized source with MIT license, lockfiles, CI workflow, docs and dataset. Never upload runtime or `.env`. Run the release secret scanner immediately before pushing.
3. For the ephemeral fictional demo, configure only the Gemini key, a new operator password (16+ characters) and a separate judge code (16+ characters). Do not copy the local payment credentials or private customer data to this host. Credentials never go in source, Docker arguments, screenshots, public README or logs.
4. Set the exact `VERDICT_PUBLIC_HOST`, `VERDICT_SECURE_COOKIES=true`, `VERDICT_LOCAL_BOOTSTRAP=false`, `VERDICT_ALLOW_SANDBOX_ACTIONS=false`, `VERDICT_SUPABASE_MIRROR=false`, `VERDICT_EPHEMERAL_STORAGE=true`. A public host without a valid judge code refuses guest sessions. Share judge access privately.
5. Verify health, HTTPS cookies, operator login, demo isolation, original upload/download, Gemini consent, live quota failures, a scoped request/reply, reassessment and cloud outbox status against the actual host. Record exact deployed commit, time, URL and provider status.
6. Keep no payment writes on an ephemeral instance. Register webhook delivery only after HTTPS ingress and state durability have been reviewed. Test real signature verification and repeated delivery. Do not weaken host checks or disable authentication to work around a deployment error.
7. Confirm availability through the end of the official judging period and record a genuine functioning demo under three minutes. Final Devpost/YouTube publication remains a separate owner-approved step.

## Local process control

The launcher starts only this project's loopback server and writes its logs under ignored `runtime/`. For a manual server, Ctrl+C stops it. Do not use broad process-kill commands that might terminate the user's other Python work. An uncertain PayPal dispatch or reserved action must be reconciled directly with PayPal before any manual database repair or retry.
