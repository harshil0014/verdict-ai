# Persistent multi-user acceptance

The requested lifecycle is tested with **two independent automated actors**. This does not claim two humans completed usability sessions. Records are synthetic user-authored data; persistence and Gemini calls are real. No payment/dispute writes occur.

**Acceptance passed at 2026-11-06 17:16:19 UTC / 22:46:19 IST**, after a completed replacement deployment. Both fresh public accounts retained original and witness-file bytes, analysis digests, audit tails and request state; foreign operations remained denied. [Forty post-redeploy checks](saas-redeploy-acceptance.json). A separate browser session also remained valid across server replacement.

| Phase | Result | Evidence |
|---|---|---|
| Independent normal registration, empty workspace | Passed, no admin-confirmed/shared accounts | Cloud smoke and [security probe](saas-cloud-security.json) |
| Own cases, original uploads, witness replies, real investigations | Passed for both accounts | [Lifecycle report](saas-local-acceptance.json) |
| Foreign reads/writes/files/exports/analyses/requests | Denied for both | Same report |
| Logout and return, revoked old cookie | Passed | Same report |
| Stop/start process, same originals/analysis/witness/audit | Passed; latest 2026-11-06 16:55:42 UTC, including witness original bytes | [Restart report](saas-restart-acceptance.json) |
| Recovery rotation/all-session revocation | Passed | [Actual cloud security](saas-cloud-security.json) |
| Invalid-original rollback, stale revision, portal revocation | Passed | Same report |
| Forced-RLS foreign rows/updates/inserts; anonymous grants | Passed on actual database role | [Security](SECURITY.md) |
| Fresh registrations and full lifecycle over public HTTPS | Passed for both accounts | [Public lifecycle](saas-public-acceptance.json) |
| Public replacement deploy, then sign in and compare saved records | Passed, 2026-11-06 17:16:19 UTC | [Post-redeploy report](saas-redeploy-acceptance.json) |
| Browser registration, recovery acknowledgement, case/upload, real investigation, manual request, logout/login | Passed through actual UI with synthetic records | [Landing](screenshots/account-landing-desktop.jpg), [investigation](screenshots/account-investigation-desktop.jpg) |
| Responsive workspace and landing | Checked at 390×844 and 1440×1000; no horizontal document overflow | Actual browser DOM, mobile sign-out and screenshots |
| Two-human usability | Not completed | Automated API actors and an automated browser walkthrough are not human usability testing |

The acceptance runner keeps credentials/identifiers/expected hashes in ignored runtime state. Verify compares revision, analysis digest, audit tail, witness state and original bytes, then repeats isolation/logout checks. Run after server restart and after replacement deploy against the same database. Never publish the private state file.

The previous 83 tests and 19 new contracts pass: **102 total**. Remote application and Docker/container jobs passed for application commit `e7c4aa3ac21276093abc32375f91b2fd34e908fb`: [CI run](https://github.com/harshil0014/verdict-ai/actions/runs/42258399852). The container also imports the actual account application and verifies that this does not create a SQLite case database.

The public run was resumed after an initial HTTP 502 and a later Windows connection reset on a GET. A fresh read confirmed that the second investigation attempt had committed; no substitute output was inserted. The harness disabled HTTP keep-alive and resumed existing case/request state; both public investigations and the subsequent replacement-deploy run completed. The initial 502's root cause is not established. These incidents are retained in [the deployment ledger](saas-deployment-verification.json); this is not an uptime guarantee.
