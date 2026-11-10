# Local fallback for Gemini interruptions

Gemini remains the primary investigation and semantic-support model. When it fails, an enabled, recently connected local worker can process the same complete system instructions, case payload and JSON schema. The normal citation, structured-value, semantic-support and source-graph checks still run. The provider and pinned model digest are recorded per stage; mixed-provider investigations are identified honestly.

The current operator installation uses **IBM Granite 4 Micro, `granite4:3b`**, an Apache-2.0 model, through the existing local Ollama installation. No model weights, credentials or case records are distributed with this repository. Model choice follows actual tests on the operator's RTX 3050 6 GB laptop, rather than a claim of parity with Gemini. See the [model publisher](https://huggingface.co/ibm-granite/granite-4.0-micro), [Ollama model package](https://ollama.com/library/granite4:3b) and [official structured-output API](https://docs.ollama.com/capabilities/structured-outputs).

## Connection and privacy

Render cannot reach a laptop's localhost. The hosted application uses a durable, private Supabase queue. A Windows worker makes authenticated outbound HTTPS requests and calls Ollama on `127.0.0.1:11434`; there is no public Ollama port, tunnel or added paid service. A random revocable worker token is bound to one explicitly registered workspace. Other accounts are not forwarded to the operator's computer.

Both queue tables have forced row-level security. Browser database roles cannot access them or their service-only RPC. The server derives ownership from a session or a registered worker token. Job UUIDs, lease tokens, input hashes and pinned model hashes bind completion to the original request. A failed lease cannot commit a late answer. Completed request text is scrubbed; short-lived result caching avoids repeating identical work during recovery. Expired queue records are removed on subsequent queue operations. Preserved investigation output and audit records follow normal case retention.

The worker verifies its tokenizer file and installed model hashes. It counts the complete input with that model's tokenizer and reserves output capacity before inference. The configured context is **16,384 tokens**, with up to 6,000 output tokens and an additional template reserve. Oversized cases are refused, **never silently shortened**. Truncated, tool-using, invalid JSON or model-drifted responses cannot become a successful investigation. No model instruction can execute a tool through this worker.

Local-model assessments cannot expand autonomous financial authority: the resolution gate abstains when an assessment used Ollama. Existing merchant policies, PayPal state, address-disclosure consent and witness-contact authorization remain separate.

## Operator installation

1. Install Ollama locally and an eligible model; review its license. Keep the inference API bound to localhost. Install the optional worker-only packages with `backend/.venv/Scripts/python.exe -m pip install -r scripts/local-worker.requirements.txt`. They are not required in the Render container.
2. Obtain the model's tokenizer from its official publisher, pin its revision and SHA-256, and verify the Ollama model digest. Registration is an operator-only database operation: register the account UUID, **hashed** opaque worker token, exact model tag/digest and context capacity in `verdict_saas.local_model_workers`. The worker cannot register or change its own authorization.
3. Store an ACL-restricted, ignored `runtime/local-model/worker.json` containing `base_url` (the HTTPS application), `worker_token`, `model`, `model_digest`, `context_tokens`, `tokenizer_path`, `tokenizer_sha256`, and `supports_thinking` (false for the current Granite model). Never put this token in a command argument, Git or a browser bundle.
4. Run `scripts/start_local_model.ps1`. It starts a hidden, singleton worker using the private config. A user-level Windows Startup shortcut can invoke this script at login. Logs contain status and token counts, not source text or credentials.
5. To stop forwarding work, disable the registered worker row or stop its exact process. To revoke access permanently, disable it and rotate/delete the token. Remove the Startup shortcut to stop login startup. This does not delete cases or investigations.

The **laptop must be awake and online**. This is a no-paid-service fallback, not independent cloud availability. Login startup does not prevent sleep or guarantee recovery after a process crash. If Gemini and the worker are unavailable, the application retains previous work and reports the actual interruption. Google outage failures do not consume the individual account's daily investigation allowance; shared capacity and pacing limits still apply.

This adapter covers text-based investigation and semantic-support review. Provider-specific Google URL Context and optional Gemini image transcription are not emulated by this text-only model. Existing direct source retrieval and local OCR remain separate.

## Verification and limits

- Existing installed models were compared locally. Qwen 3.5 4B's fast mode missed a basic named-building contradiction; its reasoning mode exhausted the tested output budget. It was not selected as the default.
- Granite passed four small fictional controls covering conflicting buildings with a shared PIN, rewritten matching addresses without a PIN, nearby different buildings and embedded prompt injection. This is a smoke test, not a reliability benchmark.
- A local test used **all seven sources from an existing case**, without creating a case or writing its evidence. Both the investigation and separate support-review stages used real Ollama inference after a **fault-injected Gemini 503 in the local test process**. It took about 54 seconds warm, accepted three mechanically valid citations, and retained an insufficient-evidence conclusion where support was incomplete. This does not claim the model equals Gemini or that Google was failing during that probe. Cold startup can take over a minute.
- Unit tests cover primary-first routing, offline behavior, unchanged complete payloads, capacity refusal, changed input hashes, invalid/truncated/tool-using output, pinned-model validation and financial abstention. Normal application tests cover the preserved investigation and security paths.
- Hosted-worker and deployment verification are recorded below. No new demo account, payment, dispute, refund or evidence record was created to verify the adapter.

Readiness does not certify answer quality. The small local model can miss facts or produce weak conclusions; source verification, uncertainty and the preserved original evidence remain necessary.

**Subsequent quality finding:** inspection of the actual fallback assessment found duplicated paragraphs, addresses mislabelled as amounts, and an overconfident narrative despite the successful transport/schema/citation checks below. Those checks did not establish semantic quality. [Corrective validation and presentation rules](ASSESSMENT_CLARITY.md) reject those extraction defects, attribute source claims and replace unchecked prose in the ordinary explanation. The historical results below describe what the earlier checks accepted, not an endorsement of that assessment.

## Hosted verification — 2026-11-10

Application code `c8c663db46c8e693435de7de47a11f1ee7e5b719` passed both GitHub CI jobs (`application`, `container`) on the main, preview and development branches. Local verification passed **376 backend tests and 44 interface tests**, including 10 fallback-specific unit tests.

The preview's authenticated outbound worker completed an actual two-stage hosted queue run on the existing seven-source case, with a simulated primary 503 confined to the verification process. Ollama received **6,138 investigation input tokens and 4,988 support-review input tokens**, without dropping sources. Both stages used the pinned Granite model, completed in **111.2 seconds** including startup/polling, and produced eight quotations accepted by the mechanical checker with eight model-assessed entailed supports. The result was conflicting accounts. This second run differs from the earlier local smoke run; neither is an independent judgment of real-world truth. Its result was kept in private verification state, not substituted into the case as a Gemini result.

Unauthenticated and invalid-token worker requests returned 401. Both queue tables were verified with forced RLS; an unrelated actor saw zero worker/job rows. Browser database roles cannot execute the queue RPC, and the restricted executor cannot register workers. Completed queue inputs were verified scrubbed.

The same code was deployed to the main public service, and the worker was switched to it with a hidden user-level Windows login shortcut. Public HTML and database-backed health returned 200. The existing interrupted investigation was resumed normally: **Gemini had recovered and completed both stages in 12.69 seconds**, saving a fresh assessment. This is not claimed as a naturally occurring production failover. Existing evidence and witness records were unchanged; stored original bytes passed their SHA-256 checks. Financial policy/action counts remained zero. The earlier release remains recoverable because the migration is additive.
