import React from "react";
export function AccountSettings({
  api,
  me,
  changed,
}: {
  api: (path: string, method?: string, body?: any) => Promise<any>;
  me: any;
  changed: () => Promise<void>;
}) {
  const [pref, setPref] = React.useState<any>(null),
    [choice, setChoice] = React.useState("off"),
    [ack, setAck] = React.useState(false),
    [busy, setBusy] = React.useState(false),
    [message, setMessage] = React.useState("");
  React.useEffect(() => {
    let live = true;
    api("/preferences")
      .then((p) => {
        if (live) {
          setPref(p);
          setChoice(p.mode);
        }
      })
      .catch(() => {
        if (live)
          setMessage(
            "Couldn’t load your preference. Try opening Settings again.",
          );
      });
    return () => {
      live = false;
    };
  }, [api]);
  async function save() {
    setBusy(true);
    setMessage("");
    try {
      const p = await api("/preferences/maps", "POST", {
        mode: choice,
        acknowledged: ack,
      });
      setPref(p);
      setAck(false);
      setMessage("Saved for existing and future investigations. Stricter case restrictions stay in effect.");
      await changed();
    } catch {
      setMessage("Couldn’t save this change. Please try again.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="account-settings">
      <span className="eyebrow">YOUR WORKSPACE</span>
      <h2>Settings</h2>
      <p>Private records. Automatic investigation. You stay in control.</p>
      <section>
        <h3>Automatic address checks</h3>
        <p>
          Choose once for existing and future eligible investigations. This
          preference is remembered until you change or revoke it.
        </p>
        {pref ? (
          <>
            <label>
              Share with the map service
              <select
                value={choice}
                onChange={(e) => {
                  setChoice(e.target.value);
                  setAck(false);
                }}
              >
                <option value="off">Nothing · compare evidence locally</option>
                <option value="area_only">
                  Only supplied Indian PIN areas
                </option>
                <option value="address">
                  Delivery addresses · unit details omitted
                </option>
              </select>
            </label>
            {choice !== "off" && (
              <>
                <p className="fine">
                  Photon/OpenStreetMap receives the extracted address or PIN
                  query. Your documents are not sent. Map tiles share your IP
                  and viewed geographic area. Address text can contain personal
                  information, so share only what you’re authorized to disclose.
                </p>
                <label className="map-remember">
                  <input
                    type="checkbox"
                    checked={ack}
                    onChange={(e) => setAck(e.target.checked)}
                  />
                  I’m authorized to share this information for my
                  investigations.
                </label>
              </>
            )}
            <button
              className="primary small"
              disabled={busy || (choice !== "off" && !ack)}
              onClick={save}
            >
              {busy ? "Saving…" : "Save address-check preference"}
            </button>
            <p className="fine">
              Turning this off stops all future external lookups for your account,
              including older case permissions. Requests already sent cannot be
              recalled. Previously preserved results stay in your records.
            </p>
          </>
        ) : (
          <p>Loading your preference…</p>
        )}
        {message && <p role="status">{message}</p>}
      </section>
      <section>
        <h3>Account & storage</h3>
        <p>
          Signed in as <strong>{me.user.display_name}</strong>. Your cases,
          original records and responses are saved.
        </p>
        <p className="fine">
          {((me.user.storage_bytes || 0) / 1048576).toFixed(1)} MB of 20 MB used
          · {me.user.analyses_today || 0} of 10 daily investigation attempts
          used. Shared free-service limits apply.
        </p>
      </section>
      <section>
        <h3>External actions</h3>
        <p>
          VERDICT prepares the next useful evidence requests automatically.
          Sharing a private response link requires your authorization; VERDICT
          does not contact witnesses automatically. Eligible PayPal Sandbox
          resolutions run only within a separately enabled, bounded merchant policy.
        </p>
        <p className="fine">
          PayPal imports use test payments only and are available to the
          authorized test merchant. Public merchant onboarding and real-money
          actions aren’t enabled.
        </p>
      </section>
    </div>
  );
}
