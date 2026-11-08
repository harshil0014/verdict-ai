# Automatic geocoding recovery

The resolver now automatically tries bounded alternative names and broader versions of the same address. It keeps the original landmark and geographic constraints, preserves actual provider responses, and labels parent-campus/street estimates explicitly. No PIN or extra investigation action is required after authorized source submission.

## Executed local verification

[Real API acceptance](geocoding-local-acceptance.json) used two ordinary automated accounts, three authored fictional cases, actual Photon and Gemini APIs, and durable cloud storage. IIT Bombay Main Gate resolved to the university campus, explicitly approximate with the gate unconfirmed. The provider identified Bhandup Railway Station (W) as a bus station, so VERDICT reports an approximate transit-stop location with no platform claim. Their map-estimate separation was 2,740 m. Springfield remained ambiguous and the invented Zzqxv landmark remained unresolved. An additional source automatically triggered reanalysis with zero new map queries. Cross-account access was denied, original file hashes and audit integrity passed, and logout/login retained records.

[The original owner case](geocoding-owner-upgrade.json) was upgraded automatically without another case retry, PIN or manual research action. All four original sources and every prior audit entry were preserved; the new map comparison and assessment were appended through normal audited operations.

[Map component runtime checks](geocoding-map-runtime.json) execute actual React/Leaflet with the preserved provider points: two markers, zoom, source popup, accuracy qualification, attribution and cleanup pass. This is JSDOM validation; browser control remains disabled, so full-browser visual QA is not claimed.

Deterministic tests include frozen real public responses and clearly synthetic provider outages, wrong-city/state/country results, ambiguity within and across alternative queries, missing landmarks, revoked consent, source anchoring and cache reuse. No new provider, dependency, billing, account access or PayPal business write was introduced. Existing private RPC ownership and forced RLS remain intact.

## Release verification

Hosted verification is recorded after deployment. The prior release remains recoverable at `release/product-experience-working-20261108` (`4f920bf`). Additive queue migrations retain all existing data and limit upgraded work to compatible workers.

Provider references: [Photon API](https://github.com/komoot/photon/blob/master/docs/api-v1.md), [public demo usage limits](https://github.com/komoot/photon#public-demo-server), [OpenStreetMap attribution](https://www.openstreetmap.org/copyright). This free public demo has no availability guarantee.
