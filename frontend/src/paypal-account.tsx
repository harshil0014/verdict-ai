import React from "react";
import { ArrowDownToLine, RefreshCw } from "lucide-react";
import "./paypal-account.css";
import {SandboxAutonomy} from './autonomous-resolution';

type API = (path: string, method?: string, body?: any) => Promise<any>;
const missing = "Not available from PayPal";
const value = (v: any) => (typeof v === "string" && v.length ? v : missing);
const amount = (v: any) =>
  v?.currency_code && v?.value ? `${v.currency_code} ${v.value}` : missing;
const date = (v: any) => (v ? new Date(v).toLocaleString() : missing);

export function PayPalCaseEntry({ onImport }: { onImport: () => void }) {
  return (
    <div className="paypal-entry">
      <div>
        <strong>Have a PayPal sandbox dispute?</strong>
        <p>
          Import provider records. Payment and dispute fields are filled
          automatically.
        </p>
      </div>
      <button className="secondary" onClick={onImport}>
        <ArrowDownToLine size={16} /> Import from PayPal
      </button>
    </div>
  );
}

export function PayPalConnectionNotice({ connection }: { connection: any }) {
  return (
    <div className="paypal-connection">
      <span className="pill">PAYPAL SANDBOX</span>
      {connection?.connected ? (
        <>
          <h3>Authorized test merchant connected</h3>
          <p>
            Merchant account <code>{connection.merchant_id}</code>
          </p>
          <p>
            Only this private workspace can import this connection’s disputes.
            PayPal account identifiers do not verify a person’s identity.
          </p>
          {connection.last_checked_at && (
            <p>
              Last checked {date(connection.last_checked_at)} ·{" "}
              {value(connection.last_status)}
            </p>
          )}
        </>
      ) : (
        <>
          <h3>No authorized connection for this workspace</h3>
          <p>
            This beta has a restricted sandbox test merchant. Public merchant
            onboarding is not enabled. Typing a transaction ID or email does not
            grant access.
          </p>
          <p>You can continue with a manual case for other investigations.</p>
        </>
      )}
    </div>
  );
}

export function PayPalImport({
  api,
  onImported,
}: {
  api: API;
  onImported: (id: string) => Promise<void>;
}) {
  const [connection, setConnection] = React.useState<any>(null),
    [rows, setRows] = React.useState<any[]>([]),
    [loading, setLoading] = React.useState(true),
    [busy, setBusy] = React.useState(""),
    [error, setError] = React.useState("");
  async function load() {
    setLoading(true);
    setError("");
    try {
      const c = await api("/paypal/connection");
      setConnection(c);
      if (c.connected) {
        const r = await api("/paypal/disputes");
        setRows(r.disputes);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }
  React.useEffect(() => {
    let active = true;
    (async () => {
      try {
        const c = await api("/paypal/connection");
        if (!active) return;
        setConnection(c);
        if (c.connected) {
          const r = await api("/paypal/disputes");
          if (active) setRows(r.disputes);
        }
      } catch (e: any) {
        if (active) setError(e.message);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [api]);
  async function importCase(id: string) {
    setBusy(id);
    setError("");
    try {
      const r = await api("/paypal/import", "POST", { dispute_id: id });
      await onImported(r.case.id);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  }
  return (
    <section className="paypal-import">
      <span className="eyebrow">PROVIDER RECORDS, PRIVATE INVESTIGATION</span>
      <h2>Import from PayPal</h2>
      <p>
        A seller-authorized sandbox connection supplies the records. Importing
        starts VERDICT’s investigation. No payment is created or captured here.
        An explicitly enabled merchant policy may act on an eligible sandbox
        dispute after investigation.
      </p>
      {loading ? (
        <p role="status">Checking the authorized sandbox connection…</p>
      ) : (
        <>
        <PayPalConnectionNotice connection={connection} />
        {connection?.connected&&<SandboxAutonomy api={api}/>}
        </>
      )}
      {connection?.connected && (
        <>
          <button
            className="secondary small"
            disabled={loading || !!busy}
            onClick={load}
          >
            <RefreshCw size={14} /> Refresh available disputes
          </button>
          {!loading && rows.length === 0 && (
            <p>
              No disputes were returned by PayPal. No sample records were
              substituted.
            </p>
          )}
          <ul className="paypal-dispute-list">
            {rows.map((r) => (
              <li key={r.dispute_id}>
                <div>
                  <strong>{r.dispute_id}</strong>
                  <span>{value(r.reason).replaceAll("_", " ")}</span>
                  <small>
                    {value(r.status)} · Disputed {amount(r.disputed_amount)}
                  </small>
                </div>
                <button
                  className="primary small"
                  disabled={!!busy}
                  onClick={() => importCase(r.dispute_id)}
                >
                  {busy === r.dispute_id
                    ? "Importing…"
                    : r.case_id
                      ? "Sync & open case"
                      : "Import case"}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}

export function PayPalReceipt({
  caseData,
  api,
  onUpdated,
}: {
  caseData: any;
  api: API;
  onUpdated: () => Promise<void>;
}) {
  const p = caseData.paypal_account;
  const [busy, setBusy] = React.useState(false),
    [error, setError] = React.useState("");
  if (!p) return null;
  async function sync() {
    setBusy(true);
    setError("");
    try {
      await api(`/cases/${caseData.id}/paypal/refresh`, "POST", {});
      await onUpdated();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className="paypal-receipt compact-payment"
      aria-label="PayPal sandbox transaction records"
    >
      <div className="payment-overview">
        <span className="pill">PayPal · test payment</span>
        <p>Sandbox uses test funds. No real money moves.</p>
      </div>
      <SandboxAutonomy api={api} caseId={caseData.id}/>
      <dl>
        <dt>Disputed amount</dt>
        <dd>{amount(p.dispute?.disputed_amount)}</dd>
        <dt>Payment amount</dt>
        <dd>{amount(p.payments?.[0]?.payment_amount)}</dd>
        <dt>Payment status</dt>
        <dd>{value(p.payments?.[0]?.status).replaceAll("_", " ")}</dd>
        <dt>Dispute status</dt>
        <dd>{value(p.dispute?.status).replaceAll("_", " ")}</dd>
      </dl>
      <p className="fine">
        PayPal supplies the transaction record. The parties’ statements still
        need assessment.
      </p>
      <details>
        <summary>Payment details &amp; identifiers</summary>
        <p>Reason: {value(p.dispute?.reason).replaceAll("_", " ")}</p>
        <dl>
          <dt>Dispute</dt>
          <dd>{value(p.dispute?.dispute_id)}</dd>
          <dt>Receiving merchant</dt>
          <dd>{value(p.merchant_id)}</dd>
        </dl>
        {p.payments?.map((payment: any, i: number) => (
          <dl key={i}>
            <dt>Buyer PayPal account</dt>
            <dd>{value(payment.buyer_id)}</dd>
            <dt>Payee merchant</dt>
            <dd>{value(payment.seller_merchant_id)}</dd>
            <dt>Capture / seller transaction</dt>
            <dd>{value(payment.capture_id)}</dd>
            <dt>Buyer transaction</dt>
            <dd>{value(payment.buyer_transaction_id)}</dd>
            <dt>Order</dt>
            <dd>{value(payment.order_id)}</dd>
            <dt>Payment date</dt>
            <dd>{date(payment.payment_date)}</dd>
            <dt>Record linkage</dt>
            <dd>{value(payment.linkage).replaceAll("_", " ")}</dd>
          </dl>
        ))}
        <p className="fine">
          {p.identity_assurance} {p.privacy} No UPI identifier is assumed for
          PayPal payments.
        </p>
        <p className="fine">
          Last checked {date(caseData.paypal_synced_at)}. Transaction amounts
          and disputed amounts are separate.
        </p>
        <button className="secondary small" disabled={busy} onClick={sync}>
          <RefreshCw size={14} />
          {busy ? "Checking…" : "Check for updates"}
        </button>
      </details>
      {!!caseData.payment_record_acquisition?.issues?.length && (
        <details>
          <summary>Some payment records couldn’t be updated</summary>
          <p>
            Previously preserved sources are retained. Missing data has not been
            filled in.
          </p>
          <ul>
            {caseData.payment_record_acquisition.issues.map((issue: string) => (
              <li key={issue}>{issue.replaceAll("_", " ")}</li>
            ))}
          </ul>
        </details>
      )}
      {error && (
        <p role="alert">
          Couldn’t check PayPal just now. Your saved records are safe.
          <details>
            <summary>Technical details</summary>
            {error}
          </details>
        </p>
      )}
    </section>
  );
}

export function ProviderRecordFacts({ source }: { source: any }) {
  const p = source.provider_provenance;
  if (!p) return null;
  return (
    <div className="paypal-source">
      <strong>PAYPAL SANDBOX · API RECORD</strong>
      <p>Authenticated provider origin. {p.verification}</p>
      {p.record_kind === "dispute" && (
        <p>
          Buyer/seller statements carried by a dispute record remain reported
          statements. They are not verified delivery or a provider finding.
        </p>
      )}
      <p>{p.privacy}</p>
      <dl>
        <dt>Retrieved</dt>
        <dd>{date(p.retrieved_at)}</dd>
        <dt>Original canonical JSON SHA-256</dt>
        <dd>
          <code>{p.canonical_json_sha256}</code>
        </dd>
        <dt>Displayed projection SHA-256</dt>
        <dd>
          <code>{p.projection_sha256}</code>
        </dd>
      </dl>
    </div>
  );
}
