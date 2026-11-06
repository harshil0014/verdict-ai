# Witness availability and revocation

Investigators can close an unanswered request as **reported unavailable** or **withdrawn**, with a required reason. The action revokes the scoped response token, updates the request and audit record atomically, and makes an existing analysis stale. Text and file replies are refused after closure. A reply that began before closure cannot commit against the newer case revision. An answered request cannot be relabelled unavailable.

Availability is an investigator report with `availability_verified=false`; it is not evidence that a party's account is true. No witness reply, independent identity check or external record retrieval is invented. Existing evidence and the prior analysis are preserved. Reassessment sees the updated request history through the existing model input. Production prompt/schema defaults are unchanged.

The deterministic tests cover both closure statuses, text/file token revocation, cross-tenant denial, answered-request protection, the reply-versus-revocation race, rollback if token closure fails, and blank-reason rejection. The frontend uses the existing request cards and modal styles and compiles successfully. Browser control is disabled; fresh visual/interaction QA is outstanding.

The deployed build `d36dc625beb48d6985fcecec0541ad465dbd2a93` passed both remote CI jobs, including graceful Docker shutdown, and all 17 actual HTTPS checks for the closure workflow. The hosted probe used real Gemini analysis on a fresh fictional case, then verified token revocation, preserved evidence/analysis, staleness, tenant boundaries and audit integrity. It did not submit any PayPal action. [Hosted verification record](witness-closure-host-verification.json) · [CI run](https://github.com/harshil0014/verdict-ai/actions/runs/42198564461). Render error-log query for the new deployment returned no entries.

## Frozen live behavior probe

[Protocol](../evaluation/availability-probe/protocol.json) · [Raw results](../evaluation/availability-probe/results.json) · [Runner](../evaluation/availability_probe.py)

The protocol and relevant code/input hashes were frozen before calls. The runner used the actual local HTTP API and real production Gemini calls on fresh fictional cases, serially, with no PayPal operations. No session cookie or portal token was written to public results. It selected the model's unique first request, closed it as reported unavailable, checked token revocation and staleness, then reassessed without adding evidence.

| Fictional case | Initial result | Closure/reassessment |
|---|---|---|
| Delivery destination missing | Insufficient; first request asks carrier for the actual destination | Portal GET rejected with 409; prior analysis stale; reassessment remained insufficient and proposed no requests |
| Two charges for one order | Conflicting; no requests proposed | No unique first request, so the closure branch was skipped; no substitute request was fabricated |

Three actual analyses completed, with zero recorded transport/API failures. Only one closure/reassessment branch was exercised. This is a behavior trace, not a baseline comparison, held-out benchmark, semantic availability score or accuracy improvement. Alternative useful witnesses may still exist even when the model stops. Independent review of request usefulness, attainable alternatives and unavailability reports remains necessary. The earlier 28/30 tie and custody-pilot ties remain unchanged.

Run `backend/.venv/Scripts/python.exe evaluation/availability_probe.py run` only against the matching frozen build and a local server. The runner refuses to overwrite existing results or silently replay calls. A new run needs a new experiment directory/protocol.
