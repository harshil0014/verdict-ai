# Persistent multi-user acceptance

The requested lifecycle is tested with **two independent automated actors**. This does not claim two humans completed usability sessions. Records are synthetic user-authored data; persistence and Gemini calls are real. No payment/dispute writes occur.

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
| Public deployment and replacement deploy | Pending | Updated only after live checks |
| Browser registration, recovery acknowledgement, case/upload, real investigation, manual request, logout/login | Passed through actual UI with synthetic records | [Landing](screenshots/account-landing-desktop.jpg), [investigation](screenshots/account-investigation-desktop.jpg) |
| Responsive workspace and landing | Checked at 390×844 and 1440×1000; no horizontal document overflow | Actual browser DOM, mobile sign-out and screenshots |
| Two-human usability | Not completed | Automated API actors and an automated browser walkthrough are not human usability testing |

The acceptance runner keeps credentials/identifiers/expected hashes in ignored runtime state. Verify compares revision, analysis digest, audit tail, witness state and original bytes, then repeats isolation/logout checks. Run after server restart and after replacement deploy against the same database. Never publish the private state file.

The previous 83 tests pass; 19 account/security/stream-boundary contracts were added and pass locally. Remote CI/container and final deployed commit will be recorded after they are checked.
