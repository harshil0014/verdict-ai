# A simpler VERDICT

The product's main path is **add evidence → automatic investigation → review → request missing evidence if useful**. The interface leads with the current assessment, source-linked reasons and a single reviewed evidence request. It keeps uncertainty explicit and consequential actions separate.

## Product audit and design decisions

| Surface | User-facing change | Preserved capability |
|---|---|---|
| Public landing and account access | Outcome-led copy, shorter privacy explanation, same clear registration/sign-in/recovery flow | Actual private accounts, session revocation, recovery key |
| Workspace | Compact accessible navigation, case inbox, less dashboard chrome, consistent cream/green hierarchy | Case search/filtering, PayPal import and manual cases |
| Investigation | Summary first; three source-linked reasons; useful next request and remaining unknowns | Competing explanations, evidence graph with expanded view, manual rerun under advanced controls |
| Evidence | Readable records; source details and integrity behind disclosure | Original downloads, provenance, provider records, automatic public discovery, manual search/URL entry |
| Activity | Persisted stage translated into plain English | Raw diagnostic/progress record remains available on demand |
| Delivery | Concise outcome, two relevant addresses, actual interactive map and approximate separation | Source quotes, inferred/source PIN distinction, precision, response hashes and original records under details |
| Map consent | Affirmative remembered account preference plus explicit per-case overrides | Default off for existing/new accounts; revocation and private caches; no invented GPS |
| PayPal | Separate disputed/payment amounts and current states; IDs under details | Authenticated sandbox record origin, reported-statement limits, authorized sync, no financial write |
| Timeline | Meaningful events with before/after assessment changes, readable dates and source links | Full original audit data and hashes under technical record |
| Witnesses | Request evidence from a named record holder; review the question before preparing a link | Restricted single-response portal, no automatic contact or identity claim, automatic reply reassessment |
| Forms/dialogs | Searchable currency names/symbols, whole-number amount entry, focus handling, friendly error summary, retained inputs | Backend validation, no blind mutation replay, exact technical error available |
| Human review/settings | Recommendation and source support, clear available-action boundary; ordinary account/privacy settings | Separate operator action safeguards remain intact; no successful resolution inferred |

The CSS system defines responsive desktop/mobile layouts, readable source/history text, focus-visible states and reduced-motion behavior. Leaflet remains a real map, not a static illustration. Backend security, case ownership and data retention do not depend on which details a user expands.

## Automatic recovery

The cloud workflow stores a next eligible attempt timestamp. Transient model/network/database failures schedule bounded exponential backoff with jitter; rate-limit failures use a longer cooldown. A provider's numeric retry hint is retained by the model adapter. Up to three workflow attempts are allowed for a generation. Completed source acquisition and current committed analysis are read before work resumes; unchanged geocoder content does not force a new model assessment solely because its retrieval time changed. Hard provider refusals and missing authorization do not retry endlessly. Free-service sleep still pauses compute; queued work persists and resumes on an awake compatible worker.

The application never tells a user “we’ll try again automatically” unless its saved workflow is in the scheduled retry state. Failed/exhausted work asks for attention. The UI provides no external notification claim: updates appear in the case. An ambiguous case/file commit is never blindly re-sent by the frontend. Server reconciliation re-reads committed state before investigation, preserving source IDs and revision/audit checks.

Geocoding failures retain the original text comparison; temporary unavailable results can be revisited after a persisted cooldown. Source/public-search providers keep their existing restrictions and cooldowns. Normal geocoding still uses fixed provider URLs, shared quotas, data minimization and explicit permission. No paid fallback is activated.

## Privacy preference and isolation

Account map preference is stored in a new private forced-RLS relation through a server-only security-invoker RPC. No existing user is opted into address sharing. Account defaults apply only where a case has no explicit permission or uses the account preference. Existing explicit `off`, PIN-area and address choices win until changed in that case. Switching the account preference requeues only eligible enabled cases that inherit it; existing sources and case bodies are not rewritten by that operation. Revocation stops future lookups, retains prior evidence, and cannot recall a request already sent. The settings copy explains that case-specific permissions remain separate.

The additive recovery migration does not delete or recreate account/case/original/audit relations. New worker-version requirements prevent older retained workers from consuming jobs whose recovery/location behavior they cannot perform. Previous functioning source is retained at `release/location-working-20261108` (`2cf6249`). Application rollback must not reverse cloud data migrations.

## Verification boundaries

Automated tests and published execution reports distinguish mocked faults, actual provider responses, real cloud storage and UI component execution. Browser control remains disabled in Work settings. JSDOM interaction checks and served-asset verification are not full-browser visual/responsive/usability certification; no screenshot or human play-through is fabricated. Independent accessibility and human usability review remain valuable. No new runtime dependency, license substitution, paid service, unapproved message, refund, claim acceptance or live merchant capability is introduced. The frozen Missing Witness Engine evaluation remains 28/30, tied with its baseline.
