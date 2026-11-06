# Acquire accessible payment records before asking a witness

Import, sync and provider refresh now attempt read-only capture/order acquisition after retrieving the actual PayPal dispute. The model receives available records when the operator subsequently chooses to investigate and gives processing consent. The model itself has no provider tools and cannot dispatch a payment or dispute action.

Each capture ID comes from the authenticated dispute. Order IDs come only from a retrieved capture's related-order field. Returned IDs must match the requested IDs. Fixed sandbox hosts/GET paths and validated identifiers prevent arbitrary-URL retrieval. Capture IDs and shared order IDs are deduplicated before reads. Permission errors, missing linkage, mismatched identifiers and exhausted budgets remain explicit diagnostics. No synthetic replacement record is generated.

## Bounds and partial results

- Sync shares 12 capture/order GET attempts across its cases. Dispute list/detail reads remain separate. Individual import/refresh uses at most 20 payment reads and ten distinct captures.
- `complete` means eligible reads succeeded, not sufficient fulfillment evidence. `partial` preserves accessible records and reports missing ones. `unavailable` records failed retrieval. `deferred` means the read budget was exhausted, not that the record does not exist.
- Read failures do not erase the imported dispute. Existing snapshots remain available with acquisition status visible. A changed failure status makes an analysis stale.
- The existing 40-source history bound remains. Reaching it reports a limit; old sources are not silently deleted. Larger histories need a future archival design.

## Versioned sources

Unchanged snapshots are recognized even if JSON object-key ordering differs. An unchanged import does not add evidence, append another acquisition event or bump the revision. Changed records append a new snapshot and mark older versions superseded while preserving original text/SHA-256. Previously duplicated legacy snapshots can become historical without deletion.

Dispute snapshots are versioned too. New investigations and quote validation use active provider snapshots. Historical records remain in the library, inspector, export and audit history, with a link to the newer version. An older reported status is not automatically compared as a simultaneous current fact. Only server-verified snapshots of the same provider record can supersede each other; unverified uploads cannot hide an existing source.

Read completion does not establish party statements or delivery. This test purchase did not ship goods and still lacks fulfillment proof. Payment acquisition does not convert the earlier rejected notes attempts into a successful submission.

## Verification

Two actual local imports of the sandbox inquiry retrieved its capture/order. Both returned 200 and contained three sources. The second preserved exact evidence and revision. Dispatch stayed disabled. Raw provider records remain in ignored private storage; [the public record](payment-acquisition-verification.json) contains counts/statuses only.

Transport/SQLite tests separately cover budgets, ID validation, duplicate reads, inaccessible records, legacy snapshots, version selection, returning to an old value, history limits, automatic acquisition, idempotent refresh, and rejecting quotes from excluded historical sources. Mock tests are distinct from live provider checks.

This is an operational acquisition improvement, not measured accuracy or dispute-win improvement. The original baseline and custody-pilot ties remain unchanged. Earlier frozen evaluations refer to their original commits; changed source hashes prevent silently rerunning their protocols against a different pipeline.
