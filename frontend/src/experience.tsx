import React from "react";
import {visibleClaims,requestState,nextRequest} from './assessment-view';
import {
  ArrowRight,
  ArrowUpRight,
  FileText,
  Check,
  Clock3,
  Plus,
  ShieldCheck,
} from "lucide-react";

export const outcomes: Record<string, string> = {
  insufficient: "More evidence needed",
  conflicting: "The accounts conflict",
  supports_buyer: "Evidence supports the buyer’s account",
  supports_seller: "Evidence supports the seller’s account",
};
export const people: Record<string, string> = {
  carrier: "Delivery company",
  buyer: "Buyer",
  seller: "Seller",
  payment_provider: "Payment provider",
  other: "Someone with first-hand information",
};
export function humanError(message: string) {
  if (
    /HTTP (429|503)|Gemini|model.*(unavailable|quota)|capacity|rate.limit/i.test(
      message,
    )
  )
    return "This service is temporarily busy. Your saved evidence is safe. Please try again shortly.";
  if (/HTTP 403|refus|blocked|denied automated/i.test(message))
    return "This source did not allow access. We kept your original evidence.";
  if (/database|network|fetch|connection|Non-JSON|unreadable/i.test(message))
    return "We couldn’t connect just now. Your saved records are unchanged. Try again in a moment.";
  if (/validation|format|pattern|request could not/i.test(message))
    return "Check the highlighted fields and try again. Your entries are still here.";
  return message;
}
export function Money({ amount, currency }: { amount: any; currency: any }) {
  if (amount === null || amount === undefined || !currency)
    return <>Amount unavailable</>;
  try {
    return (
      <>
        {new Intl.NumberFormat(undefined, {
          style: "currency",
          currency,
          currencyDisplay: "symbol",
        }).format(Number(amount))}
      </>
    );
  } catch {
    return (
      <>
        {currency} {amount}
      </>
    );
  }
}

export function EvidenceRequestAction({ current, witness, onShare, busy = false }: {
  current: any; witness: any; onShare: (w: any) => void; busy?: boolean;
}) {
  const state = requestState(current,witness);
  if (state !== "prepared") return <p role="status" className="fine">{
    state === "open" || state === "link_ready" ? "Waiting for the requested response. No duplicate invitation was created."
      : ["received","response_received","evidence_received"].includes(state) ? "Response received. New evidence is investigated automatically."
      : state === "unavailable" || state === "reported_unavailable" ? "Source reported unavailable. This limitation is preserved."
      : "Request closed; its history is preserved."
  }</p>;
  return <div><button className="primary" disabled={busy || !!current.analysis_stale} onClick={() => onShare(witness)}>
    Share request <ArrowUpRight size={16} />
  </button><p className="fine">Prepared automatically. Sharing creates a private response link; VERDICT sends no message.</p></div>;
}

export function CaseOverview({
  current,
  onEvidence,
  onRequest,
  onSource,
}: {
  current: any;
  onEvidence: () => void;
  onRequest: (w: any) => void;
  onSource: (id: string, claim?: any) => void;
}) {
  const a = current.analysis;
  const plain = (text: string, fallback: string) => current.delivery_location &&
    /Photon|OpenStreetMap|geocod|\bGPS\b|\b(?:latitude|longitude|coordinates|proximity threshold)\b|\b\d+(?:\.\d+)?\s*(?:km|kilometres?|kilometers?|metres?|meters?)\b|(?<!\d)-?\d{1,3}\.\d{4,}/i.test(text || "")
    ? fallback : text;
  const w = nextRequest(current);
  const state = w ? requestState(current,w) : undefined;
  const shareable = !state || state === "prepared";
  const requestStatus = state === "open" || state === "link_ready" ? "Waiting for a response. The existing private link is ready."
    : state === "received" || state === "response_received" ? "Response received; new evidence is investigated automatically."
    : state === "unavailable" || state === "reported_unavailable" ? "This source reported the evidence unavailable. The investigation retains that limitation."
    : "Request closed. VERDICT has retained its history.";
  const distinct = visibleClaims(a?.claims || []);
  const order=(id:string)=>{const i=a?.highlight_claim_ids?.indexOf(id)??-1;return i<0?99:i;};
  const ordered = [...distinct].sort((x:any,y:any)=>order(x.id)-order(y.id));
  const claims = ordered
    .filter(
      (c: any) =>
        c.semantic_support === "entailed" &&
        ['exact_quote_found','whitespace_aligned_quote_found','quote_in_machine_transcription'].includes(c.source_check),
    )
    .slice(0, 3);
  const shown = claims.length ? claims : distinct.slice(0, 3);
  return (
    <section className="case-overview" aria-label="Investigation overview">
      <div className="overview-heading">
        <span className="overview-status">
          <i />
          {a ? outcomes[a.finding] : "Waiting for evidence"}
        </span>
      </div>
      <h3>
        {a ? "What does the evidence suggest?" : "Start with what you have."}
      </h3>
      <p className="overview-summary">
        {a
          ? plain(a.overview_summary || (a.assessment_quality_version ? a.summary : 'A refresh is needed. Review the source-backed findings below.'), "Review the submitted address descriptions and source-backed findings below. The records alone do not establish physical delivery.")
          : current.evidence.length
            ? "Your evidence is saved. VERDICT will read it, follow relevant public references and compare the accounts. You can leave this page and return later."
            : "Add a receipt, message, delivery record or your account of what happened. VERDICT will investigate and show what the evidence supports."}
      </p>
      {!a && (
        <button className="primary" onClick={onEvidence}>
          <Plus size={16} />
          Add evidence
        </button>
      )}
      {a && (
        <>
          <div className="overview-reasons">
            <h4>Why this matters</h4>
            {shown.map((c: any, i: number) => (
              <button
                key={c.id}
                className="overview-finding"
                onClick={() => onSource(c.source_id, c)}
              >
                <span className="finding-number">{i + 1}</span>
                <span>
                  <strong>{plain(c.display_text || c.text, "Inspect the supporting address evidence for this finding.")}</strong>
                  <small>
                    {c.source_check === 'quote_in_machine_transcription' ? 'Image transcription · unverified' : c.semantic_support === "entailed"
                      ? "Supported by the document · reported information, not independent proof"
                      : "Needs closer review"}{" "}
                    <ArrowUpRight size={13} />
                  </small>
                </span>
              </button>
            ))}
            {!shown.length && (
              <p>
                There isn’t enough source-backed information to explain an
                outcome yet.
              </p>
            )}
          </div>
          <div className="overview-next">
            <div>
              <span className="eyebrow">WHAT HAPPENS NEXT</span>
              <h4>{w ? plain(w.title, "Delivery destination evidence") : "No new request prepared"}</h4>
              <p>
                {w
                  ? state === 'prepared' ? `Prepared for ${people[w.recipient] || w.recipient}: ${plain(w.question, "Please supply the original delivery destination record.") || plain(w.title, "Delivery destination evidence")}` : requestStatus
                  : 'Existing responses and unavailable records are retained. Add new evidence if it becomes available.'}
              </p>
              {w && (
                <details>
                  <summary>Why ask?</summary>
                  <p>{plain(w.rationale, "Clarify which destination the delivery record identifies.")}</p>
                </details>
              )}
            </div>
            {w && shareable ? (
              <button
                className="primary"
                disabled={!!current.analysis_stale}
                onClick={() => onRequest(w)}
              >
                Share request <ArrowRight size={16} />
              </button>
            ) : !w ? (
              <button className="secondary" onClick={onEvidence}>
                Add evidence <Plus size={16} />
              </button>
            ) : null}
          </div>
          {w && shareable && <p className="fine">Request prepared automatically. Sharing creates a private response link; VERDICT sends no message.</p>}
          {!!a.unknowns?.length && (
            <details className="overview-unknowns">
              <summary>
                What we still don’t know <span>{a.unknowns.length}</span>
              </summary>
              <ul>
                {a.unknowns.map((u: string, i: number) => (
                  <li key={i}>{plain(u, "Independent evidence of the reported delivery destination is still needed.")}</li>
                ))}
              </ul>
            </details>
          )}
          <p className="overview-disclaimer">
            <ShieldCheck size={14} />
            This assessment explains the supplied records. It does not
            independently prove events or decide the dispute.
          </p>
        </>
      )}
    </section>
  );
}

const eventNames: Record<string, string> = {
  case_created: "Case opened",
  evidence_received: "Evidence added",
  public_source_collected: "Referenced document saved",
  public_source_approved: "Public source added",
  investigation_updated: "Investigation updated",
  request_created: "Evidence request prepared",
  request_received: "A response arrived",
  witness_received: "A response arrived",
  request_closed: "Evidence request closed",
  delivery_location_verified: "Delivery locations compared",
  location_authorization_changed: "Map permission updated",
  automatic_investigation_configured:
    "Automatic investigation preference changed",
  paypal_imported: "PayPal dispute imported",
  paypal_refreshed: "PayPal records checked",
};
export function CaseTimeline({
  events,
  onSource,
}: {
  events: any[];
  onSource: (id: string) => void;
}) {
  return (
    <section className="case-history" aria-label="Case history">
      <header>
        <span className="eyebrow">THE STORY OF THIS CASE</span>
        <h3>Every new piece changes the picture.</h3>
      </header>
      <ol>
        {[...(events || [])].reverse().map((e: any, i: number) => {
          const d = e.data || {},
            change = d.analysis?.change;
          return (
            <li key={e.hash || i}>
              <div className="history-icon">
                {e.kind === "investigation_updated" ? (
                  <Check size={16} />
                ) : e.kind === "evidence_received" ? (
                  <FileText size={16} />
                ) : (
                  <Clock3 size={16} />
                )}
              </div>
              <div className="history-content">
                <time dateTime={e.at}>
                  {new Date(e.at).toLocaleString(undefined, {
                    month: "short",
                    day: "numeric",
                    hour: "numeric",
                    minute: "2-digit",
                  })}
                </time>
                <h4>
                  {eventNames[e.kind] ||
                    e.kind
                      .replaceAll("_", " ")
                      .replace(/\b\w/, (c: string) => c.toUpperCase())}
                </h4>
                {d.title && <p>{d.title}</p>}
                {e.kind === "investigation_updated" && (
                  <p>
                    {outcomes[d.finding] ||
                      "The latest evidence has been reviewed."}
                  </p>
                )}
                {change && (
                  <div className="history-change">
                    <span>Before: {outcomes[change.previous_finding]}</span>
                    <strong>After: {outcomes[change.current_finding]}</strong>
                  </div>
                )}
                {e.kind === "delivery_location_verified" && (
                  <p>
                    {d.status === "LOCATION MISMATCH"
                      ? "A difference in the reported destinations needs attention."
                      : d.status === "LIKELY MATCH"
                        ? "The addresses appear consistent."
                        : "The available locations need closer review."}
                  </p>
                )}
                {d.evidence_id && (
                  <button
                    className="text-btn"
                    onClick={() => onSource(d.evidence_id)}
                  >
                    View evidence <ArrowUpRight size={13} />
                  </button>
                )}
                <details className="technical-record">
                  <summary>Technical record</summary>
                  <code>{e.hash}</code>
                  <pre>{JSON.stringify(d, null, 2)}</pre>
                </details>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

export const currencyOptions = [
  ["USD", "$", "US Dollar"],
  ["INR", "₹", "Indian Rupee"],
  ["EUR", "€", "Euro"],
  ["GBP", "£", "British Pound"],
  ["CAD", "CA$", "Canadian Dollar"],
  ["AUD", "A$", "Australian Dollar"],
  ["SGD", "S$", "Singapore Dollar"],
  ["AED", "د.إ", "UAE Dirham"],
  ["JPY", "¥", "Japanese Yen"],
  ["NZD", "NZ$", "New Zealand Dollar"],
  ["CHF", "Fr", "Swiss Franc"],
  ["HKD", "HK$", "Hong Kong Dollar"],
];
export function CurrencyField() {
  const [value, setValue] = React.useState("USD");
  const [search, setSearch] = React.useState("");
  const [open, setOpen] = React.useState(false);
  const all: string[][] = [
    ...currencyOptions,
    ...((Intl as any).supportedValuesOf?.("currency") || [])
      .filter((code: string) => !currencyOptions.some((c) => c[0] === code))
      .map((code: string) => [
        code,
        code,
        new Intl.DisplayNames(undefined, { type: "currency" }).of(code) || code,
      ]),
  ];
  const options = all.filter((c) =>
    c.join(" ").toLowerCase().includes(search.toLowerCase()),
  );
  const selected = all.find((c) => c[0] === value)!;
  return (
    <div className="currency-field">
      <label htmlFor="currency-search">Currency</label>
      <input type="hidden" name="currency" value={value} />
      <input
        id="currency-search"
        role="combobox"
        aria-expanded={open}
        aria-controls="currency-options"
        autoComplete="off"
        value={open ? search : `${selected[1]} · ${selected[2]} (${value})`}
        onFocus={() => {
          setOpen(true);
          setSearch("");
        }}
        onBlur={(e) => {
          if (!e.currentTarget.parentElement?.contains(e.relatedTarget as Node))
            setOpen(false);
        }}
        onChange={(e) => setSearch(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            e.preventDefault();
            setOpen(false);
          }
          if (e.key === "Enter" && open && options[0]) {
            e.preventDefault();
            setValue(options[0][0]);
            setOpen(false);
          }
          if (e.key === "ArrowDown") {
            e.preventDefault();
            document
              .querySelector<HTMLButtonElement>("#currency-options button")
              ?.focus();
          }
        }}
      />
      {open && (
        <div role="listbox" id="currency-options">
          {options.slice(0, 35).map((c) => (
            <button
              type="button"
              role="option"
              aria-selected={value === c[0]}
              key={c[0]}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => {
                setValue(c[0]);
                setOpen(false);
              }}
              onKeyDown={(e) => {
                if (e.key === "ArrowDown") {
                  e.preventDefault();
                  (e.currentTarget.nextElementSibling as HTMLElement)?.focus();
                }
                if (e.key === "ArrowUp") {
                  e.preventDefault();
                  (
                    e.currentTarget.previousElementSibling as HTMLElement
                  )?.focus();
                }
              }}
            >
              {c[1]} <span>{c[2]}</span>
              <small>{c[0]}</small>
            </button>
          ))}
          {!options.length && <p>No currency found.</p>}
        </div>
      )}
    </div>
  );
}
