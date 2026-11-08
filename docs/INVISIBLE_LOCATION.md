# Invisible location intelligence

The normal case view now presents one plain result, a brief explanation grounded in submitted descriptions, and original-evidence links. It does not instantiate a map, request tiles, display coordinates, distances, provider names or precision terminology. An explicitly opened Advanced review retains the full map and source diagnostics. Closing it removes the map. Browser visual QA remains disabled; real React/Leaflet DOM interaction is verified in JSDOM.

External address sharing still defaults off. One-time affirmative consent discloses Photon/OpenStreetMap and address minimization; workspace permission is remembered, with existing case overrides and revocation preserved. Normal authorized investigations do not prompt repeatedly. Provider configuration is kept inside consent/settings or advanced review. No paid service or new dependency was added.

## Comparison rules

Clear contradictions in identifiable building/landmark descriptions, explicit country/postal codes, building identifiers or units take priority over regional proximity. Small geographic separation does not erase different buildings. Established lexical aliases and reordered/unit-omitted descriptions can be compatible; missing postal information is not a contradiction. Street/locality differences prevent a precise match until reconciled. A default configurable 200-metre tolerance applies only when both locations are sufficiently precise and their source descriptions are compatible. It is never universal address or physical-delivery proof. Ambiguity, coarse campus/postcode points, missing accuracy and provider failures retain their limitations internally.

The IIT Bombay Main Gate versus Bhandup Railway Station case is now a **destination-description mismatch**, rather than a possible match merely because both are in Mumbai. The old campus and transit-stop estimates stay qualified. No exact gate/platform position or actual parcel handover is asserted.

## Executed verification

[Original owner case](invisible-location-owner-upgrade.json): the additive, version-gated background upgrade reused preserved source extraction and provider records, with zero new external lookups. All four originals, earlier assessments in the audit, provider points and provenance were preserved; a real Gemini reassessment completed without a manual retry.

[UI runtime](invisible-location-ui-runtime.json): ten checks execute the actual React component and Leaflet with that case. The ordinary view contains only the mismatch, submitted landmark explanation and evidence links. Advanced review mounts both real points and diagnostics, then removes them on close. Consent disclosure precedes the affirmative mocked API calls, and authorized normal views contain neither a repeated permission prompt nor an instantiated map. This is DOM/API-contract verification, not a full browser visual test or tile fetch.

Deterministic backend tests cover different buildings 50 metres apart, written variants of a matching building, configurable thresholds, omitted PIN codes, source coordinate suppression in public explanations, conflicting landmarks, coarse estimates, ambiguous results, missing/unavailable providers, unchanged source/provenance reuse, and idempotent upgrades. Frontend tests retain escaping, privacy, original-evidence and advanced diagnostics coverage.

Deployment and current hosted preservation verification are recorded after release. The previous application remains recoverable at `release/geocoding-working-20261108` (`2020f17`); additive migrations and cloud evidence must be retained on application rollback.
