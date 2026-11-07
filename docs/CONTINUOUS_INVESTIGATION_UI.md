# One continuous investigation

The standalone Public research tab has been removed from case navigation. The five destinations are Investigation, Evidence, Witnesses, Timeline and Human review.

- **Evidence** combines uploads and automatically collected documents. Public source cards show requested/final URLs, retrieval/publication metadata, original and extracted SHA-256 hashes, origin-verification and human-review status. Original downloads and passage inspection remain in the source drawer. Historical applicability is not inferred from retrieval.
- **Other discoveries** retains older staged or dismissed records without duplicating sources already in Evidence. Their saved text, hashes and metadata remain inspectable. An older ready snapshot can still be added through the existing transactional API. The UI offers no destructive research-record operation.
- **Investigation and Timeline** show persisted automatic progress and failed/blocked reference attempts. Saved search/provider reports and URL Context metadata remain available in expandable retrieval history. Search leads are labeled as leads rather than evidence. Existing hash-linked case events remain intact.
- **Find more evidence** is an optional dialog from Evidence/Add evidence. It offers one URL or search form at a time, with dates and optional Google URL Context under additional options. Submission uses the existing protected research APIs; accessible sources still trigger automatic investigation. It does not introduce a new manual review stage.

This release changes presentation, CI and verification scripts only. No backend application module, provider, quota, URL security control, database schema, migration or existing record is changed. It issues no automatic case/research mutation just to display history. All stored records remain server-side and private. The existing automatic engine, witness portals and separate PayPal sandbox adapter are preserved.

## Validation

Six frontend server-rendering checks cover the five-tab navigation, retained records and deduplication, failures/provider history, complete provenance display, escaped hostile content/unsafe links, and the optional acquisition form. These render real React components with the installed toolchain; they are not browser click-through or visual-layout tests. The existing 175 Python tests and production frontend compilation pass. `npm test` is now included in CI without adding dependencies.

The read-only preservation runner captures case bodies, research records and original-file hashes for existing independent QA accounts before deployment. It compares the same data after preview and main replacement; it does not create evidence, run analysis, search or delete records. Authentication sessions are the only writes made by this runner. Deployed asset hashes are compared against the local production build separately.

Visual/browser click-through verification remains unverified in this session; prior browser/native control limits have not been bypassed. Hosted verification records are added only after execution.
