# Explain the field behind a claim check

The reported source-inspector warning was not checking the visible monetary amount. A read-only inspection of the specifically identified claim found `field=refund_status`, `value=ordered_to_pay`. Its quote contains the tribunal's payment order and `$812.02`, but not the extracted label `ordered_to_pay`.

The existing checker compares the extracted value's text with the quote, ignoring case and whitespace. It does not interpret status labels or infer currency. Therefore the saved literal mismatch is reproducible. The source quote independently passed `exact_quote_found`, semantic review recorded `entailed`, and the claim was retained. A structured mismatch does not discard a quote or, by itself, establish semantic inconsistency.

The inspector now displays **Extracted field**, **Extracted value** and **Literal value check**, alongside source existence and AI-assessed semantic support. A literal mismatch explains that it concerns the displayed value, not every number in the claim, and does not invalidate the source quote. Older records without a saved field/value identify that information as unavailable. Untrusted field/value strings remain escaped.

This is a presentation correction. The monetary parser, extraction/review engine, comparisons, saved analyses, provenance, audit records and historical evaluation are unchanged. `$812.02` and `812.02` already pass when they are the actual extracted amount value. `CAD 812.02` is not a literal match to `$812.02`; this release does not pretend that an ambiguous dollar symbol independently verifies a currency. No automatic relabeling or semantic status matching was added.

Validation: 209 Python tests, 10 component-rendering checks and the production TypeScript/Vite build pass. New regressions reproduce the exact status-label mismatch, confirm that citation/hypothesis links survive it, verify monetary value examples, expose the checked field/value, support older records and escape hostile strings. Tests are deterministic and do not call Gemini. Hosted deployment and retained-case verification are recorded after execution. Browser click-through/layout verification is not claimed.
