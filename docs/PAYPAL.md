# PayPal Sandbox

An authorized test merchant can import a dispute into a private VERDICT workspace and refresh it from PayPal. The server checks the merchant binding and links the dispute to available capture and order records. Repeated imports reuse the same case. Changed records preserve earlier snapshots.

## Configuration

Apply the [Supabase migrations](../supabase/migrations) and register the intended workspace account. A database administrator can provision one active `operator_sandbox_demo` connection using the server-only `verdict_paypal_api` operation `provision_demo` with `owner_id` and `merchant_id`. Set `VERDICT_PAYPAL_DEMO_OWNER_ID` and `VERDICT_PAYPAL_DEMO_MERCHANT_ID` to those values, and configure the Sandbox app's `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` on the server.

This integration uses a restricted first-party Sandbox merchant. Delegated merchant access requires PayPal partner approval and merchant onboarding. [PayPal disputes API](https://developer.paypal.com/api/customer-disputes/v1)

## Records and safety

Provider originals are canonicalized and hashed in a private snapshot table. The workspace and model receive a minimized projection. Payment amounts and dispute amounts remain distinct, and absent provider fields stay unknown. Refreshing an unchanged snapshot leaves the evidence and audit trail intact.

Imports and refreshes use read-only business requests. The separate Sandbox automation policy defaults off and requires deliberate merchant opt-in, eligible unfulfilled test orders, limits and expiry. A committed dispatch record prevents duplicate actions after an uncertain response. The model does not authorize financial execution. [Security boundaries](SECURITY.md)