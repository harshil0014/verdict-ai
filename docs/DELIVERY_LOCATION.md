# Delivery location comparison

VERDICT compares intended and reported destinations from cited evidence. It preserves the source passages and distinguishes a precise map result from an area estimate. Shared postal codes and short distances cannot establish that two named buildings are the same destination.

Text comparison runs locally. Under **Settings → Automatic address checks**, an account can authorize sharing either supplied Indian PIN areas or delivery addresses with unit details omitted. The geocoder rechecks current authorization before sending a query. Opening an authorized map shares the viewed area and browser IP with the tile service.

The normal comparison shows the map and estimated separation when both points resolve. The display rounds sufficiently precise separations below the configured tolerance to a threshold label. The default tolerance is 200 metres and can be configured with `VERDICT_LOCATION_PROXIMITY_METRES`. Coarse results retain their accuracy limits, and unresolved addresses retain their text comparison. The technical record includes map provenance, source links and precision details.

Photon provides map lookups. Leaflet renders OpenStreetMap tiles with visible attribution. Map estimates do not establish physical delivery. [Photon](https://github.com/komoot/photon) · [OpenStreetMap attribution](https://www.openstreetmap.org/copyright)