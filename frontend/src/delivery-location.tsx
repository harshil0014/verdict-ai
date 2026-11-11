import React from "react";
import type { Map as LeafletMapType } from "leaflet";
import "leaflet/dist/leaflet.css";
import "./delivery-location.css";

const labels: any = {
  off: "Local comparison only",
  area_only: "PIN-code area lookup",
  address: "Address lookup (unit details omitted)",
};

export function DeliveryMap({ mentions, compact = false }: { mentions: any[]; compact?: boolean }) {
  const ref = React.useRef<HTMLDivElement>(null),
    [failed, setFailed] = React.useState(false);
  const mapSignature = JSON.stringify(mentions.map(m => [m.id, m.role, m.address, m.source_id,
    m.geocode?.status, m.geocode?.lat, m.geocode?.lon, m.geocode?.precision,
    m.geocode?.accuracy_label, m.geocode?.uncertainty_m]));
  React.useEffect(() => {
    let disposed = false,
      map: LeafletMapType | undefined;
    (async () => {
      try {
        const L = await import("leaflet");
        if (disposed || !ref.current) return;
        const points = mentions.filter(
          (m) =>
            m.geocode?.status === "resolved" &&
            Number.isFinite(m.geocode.lat) &&
            Number.isFinite(m.geocode.lon),
        );
        if (!points.length) return;
        map = L.map(ref.current, { scrollWheelZoom: false });
        L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 18,
          referrerPolicy: "origin",
          attribution:
            '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        })
          .on("tileerror", () => setFailed(true))
          .addTo(map);
        const coords: [number, number][] = [];
        points.forEach((m) => {
          const g = m.geocode;
          coords.push([g.lat, g.lon]);
          const content = document.createElement("div");
          // Provider/source text never enters an HTML-string popup.
          content.textContent =
            (m.role === "intended"
              ? "Intended destination: "
              : "Reported delivery: ") +
            m.address +
            " · " +
            (g.accuracy_label || (g.precision || "unknown").replaceAll("_", " ")) +
            " · " +
            m.source_id;
          const marker = L.circleMarker([g.lat, g.lon], {
            radius: m.role === "intended" ? 11 : 6,
            color: m.role === "intended" ? "#214f40" : "#be6c37",
            weight: 3,
            fillOpacity: 0.55,
          }).addTo(map!);
          if (!compact) marker.bindPopup(content);
          if (compact && Number.isFinite(g.uncertainty_m) && g.uncertainty_m > 0) {
            L.circle([g.lat, g.lon], {radius: g.uncertainty_m,
              color: m.role === "intended" ? "#214f40" : "#be6c37",
              weight: 1, fillOpacity: 0.06, interactive: false}).addTo(map!);
          }
        });
        if (compact && coords.length === 2) L.polyline(coords, {
          color: "#53685e", weight: 2, dashArray: "5 7", interactive: false,
        }).addTo(map);
        map.fitBounds(L.latLngBounds(coords).pad(0.3), {
          maxZoom: points.some(
            (m) =>
              m.geocode.precision !== "building" &&
              m.geocode.precision !== "source_reported_gps",
          )
            ? 12
            : 16,
        });
        map.invalidateSize();
      } catch {
        setFailed(true);
      }
    })();
    return () => {
      disposed = true;
      map?.remove();
    };
  }, [mapSignature, compact]);
  return (
    <>
      <div
        ref={ref}
        className="delivery-map"
        aria-label={failed ? "Map tiles unavailable" : "Interactive source-linked delivery location map"}
      />
      {failed && !compact && (
        <p role="status">
          Map tiles are unavailable. Preserved coordinates, source passages and
          comparisons remain below.
        </p>
      )}
      {!compact && <p className="fine">
        Green: intended destination. Orange: reported delivery. Overlapping
        markers do not establish the same building or actual receipt. Map data ©
        OpenStreetMap contributors; geocoding by Photon.
      </p>}
    </>
  );
}

const locationMessages: Record<string, string> = {
  "LIKELY MATCH": "Delivery address matches",
  "POSSIBLE MATCH": "Delivery address appears to match",
  "LOCATION MISMATCH": "Delivery address doesn't match",
  UNVERIFIED: "Couldn't verify delivery address",
};
export function DeliveryLocation({ current }: { current: any }) {
  const record = current.delivery_location;
  if (!record || record.version < 3 || current.analysis_stale ||
    ["queued", "running"].includes(current.automation?.state) || mapAuthorization(current) === "off") return null;
  const pair = record?.comparisons?.find((c: any) => c.status === record.status) || record?.comparisons?.[0];
  if (!pair || !Number.isFinite(pair.distance_m) || pair.distance_m < 0) return null;
  const points = [pair.intended_id, pair.reported_delivery_id].map(id =>
    record.mentions?.find((m: any) => m.id === id));
  if (!points[0] || !points[1] || points[0].role !== "intended" || points[1].role !== "reported_delivery" ||
    points.some(m => m.geocode?.status !== "resolved" ||
      !Number.isFinite(m.geocode.lat) || !Number.isFinite(m.geocode.lon) ||
      Math.abs(m.geocode.lat) > 90 || Math.abs(m.geocode.lon) > 180)) return null;
  return <section className="delivery-location location-map-result" aria-label="Delivery location comparison">
    <DeliveryMap mentions={points} compact />
    <output className="map-distance" aria-label="Estimated straight-line separation" title="Estimated straight-line separation">
      {distanceLabel(pair.distance_m, record.proximity_tolerance_m, !pair.sufficiently_precise)}
    </output>
  </section>;
}

export function distanceLabel(distance: number, threshold = 200, approximate = false) {
  if (!Number.isFinite(distance) || distance < 0) return null;
  const limit = Number.isFinite(threshold) && threshold >= 10 && threshold <= 1000 ? threshold : 200;
  if (distance < limit) return `<${limit} m`;
  const number = new Intl.NumberFormat("en", {maximumFractionDigits: distance >= 1000 ? 1 : 0});
  return `${approximate ? "≈ " : ""}${number.format(distance >= 1000 ? distance / 1000 : distance)} ${distance >= 1000 ? "km" : "m"}`;
}

function mapAuthorization(current: any) {
  const account = current.effective_map_preference;
  const choice = current.location_authorization?.mode || "account";
  const configured = account?.has_account_choice ?? !!account?.acknowledged_at;
  return (configured && account.mode === "off") || choice === "off" ? "off"
    : configured && account.mode === "area_only" ? "area_only"
    : choice === "account" ? account?.mode || "off" : choice;
}

export function LocationTechnicalRecord(props: {
  current: any; onSource: (id: string) => void;
}) {
  const [open, setOpen] = React.useState(false);
  React.useEffect(() => setOpen(false), [props.current.id]);
  return <details className="technical-record" open={open} onToggle={e => setOpen(e.currentTarget.open)}>
    <summary>Technical location record</summary>
    {open && <DeliveryLocationDiagnostics {...props} />}
  </details>;
}

export function DeliveryLocationDiagnostics({
  current,
  onSource,
}: {
  current: any;
  onSource: (id: string) => void;
}) {
  const record = current.delivery_location;
  const authorization = mapAuthorization(current);
  if (!record?.mentions?.length) return null;
  const pair = record?.comparisons?.[0];
  const paired = pair ? [pair.intended_id, pair.reported_delivery_id] : [];
  const mentions = (record?.mentions || []).filter(
    (m: any) => m.role !== "other" && (!paired.length || paired.includes(m.id)),
  );
  const plotted = mentions.filter((m: any) => m.geocode?.status === "resolved");
  return (
    <section
      className="delivery-location simple-location"
      aria-label="Delivery location"
    >
      <div className="delivery-heading">
        <div>
          <span className="eyebrow">DELIVERY LOCATION</span>
          <h3>
            {locationMessages[record?.status] || locationMessages.UNVERIFIED}
          </h3>
        </div>
      </div>
      <p className="location-caption">{labels[authorization]}. External-check privacy preferences are managed once in account Settings. Local comparison continues when external checks are off.</p>
      {plotted.length > 0 && authorization !== "off" && (
        <DeliveryMap mentions={plotted} />
      )}
      <div className="location-addresses">
        {mentions.map((m: any) => (
          <div key={m.id}>
            <span>
              <i className={m.role === "intended" ? "expected" : "reported"} />
              {m.role === "intended"
                ? "Expected destination"
                : "Reported delivery"}
            </span>
            <strong>{m.address}</strong>
            <p>
              {m.geocode?.status === "resolved"
                ? m.geocode.accuracy_label || (m.geocode.precision === "building"
                  ? "Map-estimated location."
                  : "Approximate location.")
                : authorization === "off"
                  ? "Not checked on a map."
                  : "We couldn’t locate this address accurately."}
            </p>
            <button className="text-btn" onClick={() => onSource(m.source_id)}>
              View evidence
            </button>
          </div>
        ))}
      </div>
      {pair?.distance_m !== null && pair?.distance_m !== undefined && (
        <p className="location-distance">
          Approximate separation{" "}
          <strong>
            {pair.distance_m >= 1000
              ? (pair.distance_m / 1000).toFixed(1) + " km"
              : pair.distance_m + " m"}
          </strong>
        </p>
      )}
      {pair?.conflicting_facts?.some((x: string) => x.includes("PIN")) && (
        <p className="location-important">
          The PIN codes explicitly supplied in the records differ.
        </p>
      )}
      <p className="scope-note">
        A map estimate doesn’t prove where a package was delivered or who
        received it.
      </p>
      <details className="location-evidence">
        <summary>View comparison evidence</summary>
        {record?.comparisons?.map((c: any, i: number) => (
          <div key={i}>
            <strong>{c.status}</strong>
            <ul>
              {[
                ...c.supporting_facts,
                ...c.conflicting_facts,
                ...c.limitations,
              ].map((fact: string, j: number) => (
                <li key={j}>{fact}</li>
              ))}
            </ul>
          </div>
        ))}
        {record?.mentions?.map((m: any) => (
          <article className="delivery-source" key={m.id}>
            <button className="text-btn" onClick={() => onSource(m.source_id)}>
              Inspect source {m.source_id}
            </button>
            <blockquote>{m.quote}</blockquote>
            <p>
              Source-supplied PIN: {m.explicit_postcode || "Not supplied"}.{" "}
              {m.source_authenticity}
            </p>
            {m.geocode?.inferred_postcode && (
              <p>
                Map-provider PIN (inferred): {m.geocode.inferred_postcode}. This
                is not a PIN supplied by the carrier.
              </p>
            )}
            {m.geocode?.label && <p>Map result: {m.geocode.label}</p>}
            <p>{m.geocode?.detail}</p>
            <details className="technical-record">
              <summary>Technical details</summary>
              <p>
                {m.geocode?.provider} ·{" "}
                {m.geocode?.precision?.replaceAll("_", " ")}
                {m.geocode?.precision === "postcode_area"
                  ? " · Approximate area location"
                  : ""}
                . {m.geocode?.uncertainty_basis}
              </p>
              <p>
                {m.geocode?.lat}, {m.geocode?.lon}. Source: {m.source_id}
              </p>
              <p>Response SHA-256</p>
              <code>{m.geocode?.response_sha256}</code>
              {m.geocode?.attempts?.map((a: any, i: number) => (
                <p key={i}>Lookup {i + 1}: {a.query} · {a.status.replaceAll("_", " ")} · {a.response_sha256 || "No response retained"}</p>
              ))}
              <p>Source hash</p>
              <code>{m.source_sha256}</code>
              <code>{m.quote_sha256}</code>
              <p>Retrieved {m.geocode?.retrieved_at || "Not retrieved"}</p>
            </details>
          </article>
        ))}
        <details className="technical-record">
          <summary>Verification record integrity</summary>
          <code>{record?.record_sha256}</code>
          <p>
            {record?.extraction} · {record?.extraction_error}
          </p>
        </details>
      </details>
      {current.analysis && <details className="technical-record">
        <summary>Full investigation assessment</summary>
        <p>{current.analysis.summary}</p>
        <p>{current.analysis.recommendation}</p>
      </details>}
    </section>
  );
}
