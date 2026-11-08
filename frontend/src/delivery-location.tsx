import React from "react";
import type { Map as LeafletMapType } from "leaflet";
import "leaflet/dist/leaflet.css";
import "./delivery-location.css";

type API = (path: string, method?: string, body?: any) => Promise<any>;
const labels: any = {
  off: "Local comparison only",
  area_only: "PIN-code area lookup",
  address: "Address lookup (unit details omitted)",
};

export function DeliveryMap({ mentions }: { mentions: any[] }) {
  const ref = React.useRef<HTMLDivElement>(null),
    [failed, setFailed] = React.useState(false);
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
            (g.accuracy_label || g.precision.replaceAll("_", " ")) +
            " · " +
            m.source_id;
          L.circleMarker([g.lat, g.lon], {
            radius: m.role === "intended" ? 11 : 6,
            color: m.role === "intended" ? "#214f40" : "#be6c37",
            weight: 3,
            fillOpacity: 0.55,
          })
            .bindPopup(content)
            .addTo(map!);
        });
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
  }, [mentions]);
  return (
    <>
      <div
        ref={ref}
        className="delivery-map"
        aria-label="Interactive source-linked delivery location map"
      />
      {failed && (
        <p role="status">
          Map tiles are unavailable. Preserved coordinates, source passages and
          comparisons remain below.
        </p>
      )}
      <p className="fine">
        Green: intended destination. Orange: reported delivery. Overlapping
        markers do not establish the same building or actual receipt. Map data ©
        OpenStreetMap contributors; geocoding by Photon.
      </p>
    </>
  );
}

const locationMessages: Record<string, string> = {
  "LIKELY MATCH": "Delivery address matches",
  "POSSIBLE MATCH": "Delivery address appears to match",
  "LOCATION MISMATCH": "Delivery address doesn't match",
  UNVERIFIED: "Couldn't verify delivery address",
};
export function DeliveryLocation({
  current, api, changed, onSource,
}: { current: any; api: API; changed: () => Promise<void>; onSource: (id: string) => void }) {
  const [advanced, setAdvanced] = React.useState(false), [consent, setConsent] = React.useState(false);
  React.useEffect(() => { setAdvanced(false); setConsent(false); }, [current.id]);
  const record = current.delivery_location;
  const mentions = (record?.mentions || []).filter((m: any) => m.role !== "other");
  if (!mentions.length) return null;
  const pair = record?.comparisons?.find((c: any) => c.status === record.status) || record?.comparisons?.[0];
  const status = record?.version >= 3 || record?.status === "LOCATION MISMATCH" ? record?.status : "UNVERIFIED";
  const explanation = pair?.explanation || (status === "LOCATION MISMATCH"
    ? "The submitted records identify different delivery destinations. This does not establish physical delivery."
    : "The submitted address information isn't sufficient to confirm one matching delivery destination.");
  const sources = [...new Set<string>(pair?.source_ids || mentions.map((m: any) => m.source_id))];
  const override = current.location_authorization?.mode;
  const authorization = override && override !== "account" ? override : current.effective_map_preference?.mode || "off";
  return <section className="delivery-location address-result" aria-label="Delivery address">
    <h3>{locationMessages[status] || locationMessages.UNVERIFIED}</h3>
    <p>{explanation}</p>
    <div className="address-result-actions">
      {sources.slice(0, 2).map((id, i) => <button key={id} className="text-btn" onClick={() => onSource(id)}>
        {sources.length === 1 ? "View supporting evidence" : i === 0 ? "View intended address" : "View delivery record"}
      </button>)}
      {authorization === "off" && <button className="text-btn" onClick={() => setConsent(true)}>Allow automatic address checks</button>}
    </div>
    {consent && <DeliveryLocationDiagnostics current={current} api={api} changed={changed} onSource={onSource} consentOnly onClose={() => setConsent(false)} />}
    <details className="technical-record address-advanced" open={advanced} onToggle={(e) => setAdvanced(e.currentTarget.open)}>
      <summary>Advanced review</summary>
      {advanced && <DeliveryLocationDiagnostics current={current} api={api} changed={changed} onSource={onSource} />}
    </details>
  </section>;
}

export function DeliveryLocationDiagnostics({
  current,
  api,
  changed,
  onSource,
  consentOnly = false,
  onClose,
}: {
  current: any;
  api: API;
  changed: () => Promise<void>;
  onSource: (id: string) => void;
  consentOnly?: boolean;
  onClose?: () => void;
}) {
  const record = current.delivery_location,
    override = current.location_authorization?.mode;
  const account = current.effective_map_preference?.mode || "off";
  const authorization = override && override !== "account" ? override : account;
  const [choice, setChoice] = React.useState("address"),
    [remember, setRemember] = React.useState(true),
    [busy, setBusy] = React.useState(false),
    [error, setError] = React.useState(""),
    [settings, setSettings] = React.useState(consentOnly);
  React.useEffect(() => {
    setError("");
    setSettings(consentOnly);
  }, [current.id, consentOnly]);
  async function save(mode: string) {
    setBusy(true);
    setError("");
    try {
      if (remember) {
        await api("/preferences/maps", "POST", {
          mode,
          acknowledged: mode !== "off",
        });
        await api(`/cases/${current.id}/location-authorization`, "POST", {
          mode: "account",
          acknowledged: false,
        });
      } else
        await api(`/cases/${current.id}/location-authorization`, "POST", {
          mode,
          acknowledged: mode !== "off",
        });
      setSettings(false);
      await changed();
      onClose?.();
    } catch {
      setError(
        "We couldn’t finish updating your preference. Check Settings before trying again.",
      );
    } finally {
      setBusy(false);
    }
  }
  if (!record?.mentions?.length && !settings) return null;
  const pair = record?.comparisons?.[0];
  const paired = pair ? [pair.intended_id, pair.reported_delivery_id] : [];
  const mentions = (record?.mentions || []).filter(
    (m: any) => m.role !== "other" && (!paired.length || paired.includes(m.id)),
  );
  const plotted = mentions.filter((m: any) => m.geocode?.status === "resolved");
  const permission = (
    <div className="map-permission">
      <h4>
        {authorization === "off"
          ? "Allow automatic address checks?"
          : "Address-check permission"}
      </h4>
      <p>
        We’ll share a delivery address with Photon/OpenStreetMap, omitting unit
        and floor details. Opening a map shares your IP address and the area
        viewed. Only allow this for information you’re authorized to share.
      </p>
      <label className="map-choice">
        Information to share
        <select value={choice} onChange={(e) => setChoice(e.target.value)}>
          <option value="address">
            Delivery addresses · works without a PIN
          </option>
          <option value="area_only">Only supplied Indian PIN areas</option>
        </select>
      </label>
      <label className="map-remember">
        <input
          type="checkbox"
          checked={remember}
          onChange={(e) => setRemember(e.target.checked)}
        />
        Remember for my other investigations
      </label>
      <div className="map-permission-actions">
        <button
          className="primary small"
          disabled={busy}
          onClick={() => save(choice)}
        >
          {busy ? "Saving…" : "Allow automatic address checks"}
        </button>
        {authorization !== "off" && (
          <button
            className="secondary small"
            disabled={busy}
            onClick={() => save("off")}
          >
            Turn off external address checks
          </button>
        )}
        <button className="text-btn" onClick={() => { setSettings(false); onClose?.(); }}>
          Not now
        </button>
      </div>
      <details className="technical-record">
        <summary>Privacy details</summary>
        <p>
          Original documents are not sent to the geocoder. Address text may
          itself contain personal information; it cannot be perfectly redacted.
          Current choice: {authorization}. Existing explicit per-case choices
          override the account preference. Revocation stops future lookups,
          retains prior evidence, and cannot recall requests already sent.
          Public services are best effort.
        </p>
      </details>
    </div>
  );
  if (consentOnly) return <div className="address-consent">{permission}{error && <p role="alert">{error}</p>}</div>;
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
        <button className="text-btn" onClick={() => setSettings(!settings)}>
          {authorization === "off" ? "Enable maps" : "Map settings"}
        </button>
      </div>
      {settings ? (
        permission
      ) : authorization === "off" ? (
        <p className="location-caption">
          We compared the supplied wording privately.{" "}
          <button className="text-btn" onClick={() => setSettings(true)}>
            Allow map checks
          </button>{" "}
          to compare the locations too.
        </p>
      ) : null}
      {error && <p role="alert">{error}</p>}
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
