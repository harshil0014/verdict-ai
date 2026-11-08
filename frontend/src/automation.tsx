import React from "react";
import { LoaderCircle, CheckCircle2, AlertTriangle } from "lucide-react";
export function AutomaticInvestigation({
  current,
  api,
  changed,
}: {
  current: any;
  api: (path: string, method?: string, body?: any) => Promise<any>;
  changed: () => Promise<void>;
}) {
  const a = current.automation;
  const [busy, setBusy] = React.useState(false),
    [error, setError] = React.useState("");
  if (!a) return null;
  const active = ["queued", "running"].includes(a.state),
    retry = a.stage === "retry_wait";
  const labels: Record<string, string> = {
    queued: "Your evidence is saved. We’ll investigate it.",
    finding_references: "Reading your evidence…",
    retrieving_references: "Checking a referenced document…",
    recovering_sources: "Looking for another accessible source…",
    verifying_delivery_locations: "Comparing delivery locations…",
    investigating: "Reviewing the accounts…",
    complete: "Investigation updated.",
    needs_attention: "Your evidence is safe. This review needs attention.",
    paused: "Automatic investigation is paused.",
    waiting_for_evidence: "Add evidence to start your investigation.",
    retry_wait:
      "Investigation temporarily interrupted. Trying again automatically.",
    interrupted: "Your evidence is safe. Automatic attempts have stopped.",
  };
  async function run(path: string, body?: any) {
    setBusy(true);
    setError("");
    try {
      await api(`/cases/${current.id}/${path}`, "POST", body);
      await changed();
    } catch {
      setError("Couldn’t update this preference just now. Please try again.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className={"automatic-investigation " + (active ? "working" : "")}
      aria-label="Automatic investigation"
    >
      <div className="automatic-status" role="status">
        {active ? (
          <LoaderCircle className="spin" size={17} />
        ) : a.state === "completed" ? (
          <CheckCircle2 size={17} />
        ) : (
          <AlertTriangle size={17} />
        )}
        <div>
          <strong>{labels[a.stage] || "Investigation status updated."}</strong>
          {active && (
            <p>
              {retry
                ? "Completed work is retained. We’ll show an update here."
                : "You can leave this page and come back. Free hosting may pause while idle."}
            </p>
          )}
          {a.state === "partial" && (
            <p>
              Some referenced documents couldn’t be accessed. The available
              evidence has still been reviewed.
            </p>
          )}
          {a.state === "failed" && (
            <p>
              We couldn’t finish after the available attempts. Review the
              details or add the missing information.
            </p>
          )}
        </div>
      </div>
      <details className="automatic-advanced">
        <summary>Details & controls</summary>
        <p className="fine">{a.detail}</p>
        {a.retry_at && (
          <p>
            Next eligible attempt: {new Date(a.retry_at).toLocaleString()}. Work
            resumes when the service is awake.
          </p>
        )}
        <div className="automatic-controls">
          {a.state === "failed" && (
            <button
              className="secondary small"
              disabled={busy}
              onClick={() => run("automation/retry", {})}
            >
              Try another review
            </button>
          )}
          <button
            className="secondary small"
            disabled={busy}
            onClick={() => run("automation", { enabled: !a.enabled })}
          >
            {a.enabled
              ? "Pause automatic investigation"
              : "Enable automatic investigation"}
          </button>
        </div>
        <details className="technical-record">
          <summary>Technical activity record</summary>
          <p>
            Recovered source identity does not verify legal truth or identical
            bytes at another publisher. The original refusal is retained.
          </p>
          <pre>{JSON.stringify(a.progress, null, 2)}</pre>
        </details>
      </details>
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
