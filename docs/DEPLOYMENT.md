# Deployment preparation and operational contract

No application host was created, no repository was pushed and no service was published during this build. Docker is not installed on the execution host; the image was not built here. Local backend tests and the frontend production build are separate validation evidence, not remote deployment certification.

## Hosting choice

The available Sites platform runs Cloudflare Workers, not the existing Python backend. A static frontend publication would leave investigation/auth/upload functionality disconnected. Preserve the integrated FastAPI service; prepare a container host such as Render. [Render Docker documentation](https://render.com/docs/docker), [persistent disks](https://render.com/docs/disks) and [free services](https://render.com/docs/free) must be rechecked at deployment time for current availability, quotas and sleep behavior. No paid disk or service activation is authorized by this configuration.

`render.yaml` deliberately keeps sandbox writes disabled. Free instance disk is ephemeral. A durable transactional primary store is required for safe action reservations and portal continuity; private snapshots do not replace it. A continuously available judging demo may require a separately approved hosting choice rather than assuming a sleeping free service is always online.

## Concrete publication sequence

1. Review the sanitized release, evaluation report and known limitations. Obtain final owner approval for a public repository under `harshil0014` and the chosen hosting audience/provider. The mandate explicitly reserves public publication and sensitive account actions for approval.
2. Create/push only the sanitized source with MIT license, lockfiles, CI workflow, docs and dataset. Never upload runtime or `.env`. Run the release secret scanner immediately before pushing.
3. Deploy the container with private environment variables: PayPal sandbox client credentials, Gemini key, existing Supabase server key/URL, operator password (16+ characters) and a separate judge demo access code (16+ characters). Do not put them in source, Docker arguments, screenshots, public README or logs.
4. Set `VERDICT_PUBLIC_HOST` to the exact host, `VERDICT_SECURE_COOKIES=true`, `VERDICT_LOCAL_BOOTSTRAP=false`, `VERDICT_ALLOW_SANDBOX_ACTIONS=false`, `VERDICT_SUPABASE_MIRROR=true`. A public host without a valid judge code refuses guest demo sessions. Share the judge code only through the approved private judging channel.
5. Verify health, HTTPS cookies, operator login, demo isolation, original upload/download, Gemini consent, live quota failures, a scoped request/reply, reassessment and cloud outbox status against the actual host. Record exact deployed commit, time, URL and provider status.
6. Keep no payment writes on an ephemeral instance. Register webhook delivery only after HTTPS ingress and state durability have been reviewed. Test real signature verification and repeated delivery. Do not weaken host checks or disable authentication to work around a deployment error.
7. Confirm availability through the end of the official judging period and record a genuine functioning demo under three minutes. Final Devpost/YouTube publication remains a separate owner-approved step.

## Local process control

The launcher starts only this project's loopback server and writes its logs under ignored `runtime/`. For a manual server, Ctrl+C stops it. Do not use broad process-kill commands that might terminate the user's other Python work. An uncertain PayPal dispatch or reserved action must be reconciled directly with PayPal before any manual database repair or retry.
