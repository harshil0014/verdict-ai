# Map and distance in the investigation

This UI-only update supersedes the ordinary location display described in earlier releases. After the authorized computation completes, the location section shows only the map and distance badge. It contains no result heading, explanation paragraph, permission prompt, source-action buttons or technical disclosure. Original evidence remains available under Evidence, and full technical location records remain under Findings.

The distance is taken from the existing backend comparison for the same two plotted mention IDs. The default threshold is 200 metres: distances below it display `<200 m`; exactly 200 displays `200 m`; larger distances use metres or kilometres. A configured backend tolerance is respected. Coarse estimates above the threshold retain the `≈` symbol. An area/campus estimate or nearby point does not change the existing address-identity decision or authorize financial actions.

Both original resolved locations must have valid finite coordinates and a valid computed separation. Unresolved, ambiguous, unpaired, invalid, stale or still-processing comparisons do not produce a fabricated map or distance. Existing consent is required before loading external map tiles, including for previously preserved results. No permission is granted by this release.

The compact map shows the two existing markers, a dashed straight-line connector and available uncertainty circles. Map-only zoom controls and required OpenStreetMap attribution remain. Expanded marker explanations are reserved for technical diagnostics. Unchanged polling does not recreate the map and reset the user's pan/zoom. Technical maps do not mount while their disclosure is closed.

Verification: 42 frontend component/render checks passed, covering threshold boundaries, configured tolerance, unavailable/invalid locations, revocation, compact-only markup and preserved acquisition workflows. The production TypeScript/Vite build passed. No deployed test accounts, cases, invitations, geocoder requests or financial actions were created. Browser control remains disabled; interactive usability testing is left to the owner.

The existing Leaflet library is reused according to its [stable API documentation](https://leafletjs.com/reference-1.9.4.html). The map retains the attribution and browser cache behavior required by the [OpenStreetMap tile policy](https://operations.osmfoundation.org/policies/tiles/).
