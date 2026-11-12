# Delivery location comparison

VERDICT compares intended and reported destinations from cited evidence. It preserves the source passages and distinguishes a precise map result from an area estimate. Shared postal codes and short distances cannot establish that two named buildings are the same destination.

Text comparison runs locally. Under **Settings → Automatic address checks**, an account can authorize sharing either supplied Indian PIN areas or delivery addresses with unit details omitted. The geocoder rechecks current authorization before sending a query. Opening an authorized map shares the viewed area and browser IP with the tile service.

The normal comparison shows the map and estimated separation when both points resolve. The display rounds sufficiently precise separations below the configured tolerance to a threshold label. The default tolerance is 200 metres and can be configured with `VERDICT_LOCATION_PROXIMITY_METRES`. Coarse results retain their accuracy limits, and unresolved addresses retain their text comparison. The technical record includes map provenance, source links and precision details.

Photon provides map lookups. Leaflet renders OpenStreetMap tiles with visible attribution. Map estimates do not establish physical delivery. [Photon](https://github.com/komoot/photon) · [OpenStreetMap attribution](https://www.openstreetmap.org/copyright)

## Gemini-assisted search wording

In authorized address mode, Gemini prepares search wording from the address with unit details already omitted. One bounded batch uses the existing primary/backup model policy. Deterministic validation accepts punctuation changes, established abbreviation expansions and small spelling proposals only. Every supplied place and number must remain accounted for, in the same order and geographic segment. Invented buildings, added countries and missing PIN guesses are rejected. The original address and its source quote never change.

Coordinates and any missing postal code come only from compatible real Photon results. A model spelling proposal remains unverified and its map result is downgraded to an approximate site estimate; it cannot establish an exact building match. Model preparation never runs for local-only or PIN-area-only settings. If preparation fails or times out, ordinary source-based lookup continues. Validated proposals and map responses are cached in the existing private location record with integrity metadata; there is no database migration or new provider.

Implementation references: [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output) and [Photon search API](https://github.com/komoot/photon/blob/master/docs/api-v1.md). Structured model output is validated by application code; JSON conformance alone does not establish address accuracy.
