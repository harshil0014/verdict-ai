# VERDICT execution record

Started 2026-11-05. Existing Python 3.13 virtual environment and credential file retained. No Git history existed; no tracked secrets to remove. `.gitignore` installed before development.

## Priorities
1. Verify services and review closest prior art, API schemas and rules.
2. Deliver a persistent investigation: evidence → cited claims → competing hypotheses → targeted request → scoped response → revised analysis.
3. Keep authorization, source validation, factual comparisons, audit integrity and PayPal state checks outside the model.
4. Build the evidence graph, inbox, source inspector, timeline and human review on the same state.
5. Exercise adversarial/security tests and compare initial-review/checklist/active acquisition on labeled fictional cases.
6. Prepare deployable source, reproducible instructions and truthful submission materials; public publication requires the user's final approval under the mandate.

## Decisions
- FastAPI/Pydantic/httpx reuse the working Python environment; React + React Flow supply interactive graph behavior. Use SQLite with transactional writes for a complete portable single-instance build. Supabase auth/REST are reachable but no app tables exist: supply a deny-by-default migration and verify cloud operations separately, never claim a migration was applied without evidence.
- A bounded structured Gemini workflow, with independent semantic support assessment, replaces a tool-using swarm. The model has no payment tools. Raw evidence is untrusted data. Source quotation checks are mechanical; semantic assessment remains an AI judgment.
- Preserve full evidence versions and append-only hash-linked audit records. Hashes attest stored integrity, never truth.
- PayPal sandbox only. Read/list/detail/order/capture and verified webhook ingestion; exact snapshot-bound action review with current HATEOAS link checking and durable reservation. No automatic retries after uncertain dispatch.
- Text, JSON and text-bearing PDFs initially; pypdf instead of custom parsing. Scans explicitly remain unparsed. Docling/OCR are deferred until real evidence warrants their heavier runtime.
- No competitor application code copied. Inspect MIT implementations for design lessons; do not reuse unlicensed DisputeLens source. Depend on maintained MIT/BSD/Apache components for infrastructure.

## Initial service observations
- OAuth 200; dispute list 200, zero disputes. Scope list includes disputes/create but scope alone does not certify creation permission or a usable transaction.
- Gemini list 200; 2.5 generate endpoints 404; `gemini-3.5-flash-lite` generated JSON successfully. Pin the verified model and never silently replace it.
- Supabase privileged REST root 200, only `/rpc/rls_auto_enable` exposed. Publishable REST root 401, auth health 200. This does not independently prove RLS on nonexistent tables.
