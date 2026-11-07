# Persistent multi-user acceptance

**Automatic investigation release, 7 November 2026:** the primary service passed all 40 existing-account persistence/isolation checks at **10:12:49 IST**, plus the new 36-check automatic PDF-link acceptance. A fresh upload containing the Air Canada policy URL triggered actual retrieval, preserved provenance and real Gemini investigation with no separate approval or analyze request; all 10 main-site checks passed at **10:13:08 IST**. [Current automatic workflow and exact reports](AUTOMATIC_INVESTIGATION.md). Witness replies also triggered reanalysis automatically. The previous release remains recoverable; no paid resources were activated.

**Public research regression, 7 November 2026:** application commit `9a3ae66` passed 148 tests and remote application/container CI. After promotion to the main URL, the same two independent account actors passed all 40 persistence/isolation/logout checks at **01:10:41 IST**, including original and witness-file bytes, analyses and audit hashes. [Latest primary regression](public-research-primary-account-regression.json). A separate research account then created its own case, retrieved/approved real public legislation and ran Gemini on the primary service; all 12 checks, including private originals and logout/return, passed at **01:12:32 IST**. [Actual primary writes](public-research-primary-write-verification.json). These are automated actors, not two human usability testers. [Research acceptance and visual limits](PUBLIC_RESEARCH.md).

The requested lifecycle is tested with **two independent automated actors**. This does not claim two humans completed usability sessions. Records are synthetic user-authored data; persistence and Gemini calls are real. No payment/dispute writes occur.

**Acceptance passed at 2026-11-06 17:16:19 UTC / 22:46:19 IST**, after a completed replacement deployment. Both fresh public accounts retained original and witness-file bytes, analysis digests, audit tails and request state; foreign operations remained denied. [Forty post-redeploy checks](saas-redeploy-acceptance.json). A separate browser session also remained valid across server replacement.

The same accounts then passed **all 40 checks at the original public URL at 17:22:55 UTC / 22:52:55 IST**, after promotion to [VERDICT](https://verdict-ai-harshil0014.onrender.com). [Primary-service verification](saas-primary-acceptance.json). The previously created browser account also signed in there and recovered its earlier investigation.

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
| Original URL promotion and both-account isolation/persistence | Passed, 2026-11-06 17:22:55 UTC | [Primary report](saas-primary-acceptance.json) |
| Browser registration, recovery acknowledgement, case/upload, real investigation, manual request, logout/login | Passed through actual UI with synthetic records | [Landing](screenshots/account-landing-desktop.jpg), [investigation](screenshots/account-investigation-desktop.jpg) |
| Responsive workspace and landing | Checked at 390×844 and 1440×1000; no horizontal document overflow | Actual browser DOM, mobile sign-out and screenshots |
| Two-human usability | Not completed | Automated API actors and an automated browser walkthrough are not human usability testing |

The acceptance runner keeps credentials/identifiers/expected hashes in ignored runtime state. Verify compares revision, analysis digest, audit tail, witness state and original bytes, then repeats isolation/logout checks. Run after server restart and after replacement deploy against the same database. Never publish the private state file.

The previous 83 tests and 19 new contracts pass: **102 total**. Remote application and Docker/container jobs passed for application commit `e7c4aa3ac21276093abc32375f91b2fd34e908fb`: [CI run](https://github.com/harshil0014/verdict-ai/actions/runs/42258399852). The container also imports the actual account application and verifies that this does not create a SQLite case database.

The public run was resumed after an initial HTTP 502 and a later Windows connection reset on a GET. A fresh read confirmed that the second investigation attempt had committed; no substitute output was inserted. The harness disabled HTTP keep-alive and resumed existing case/request state; both public investigations and the subsequent replacement-deploy run completed. The initial 502's root cause is not established. These incidents are retained in [the deployment ledger](saas-deployment-verification.json); this is not an uptime guarantee.
