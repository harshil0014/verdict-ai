# Evaluation: 30-case fictional development pilot

Model: **gemini-3.1-flash-lite**. All 30 authored scenarios have completed A, B and VERDICT initial runs. Completed recorded run slots: 141; some final slots reuse the unchanged initial result when no witness was acquired. Raw outputs, usage and historical failures are retained in `evaluation/results.json`. Final strict structured checks were reapplied offline to those frozen claims in `evaluation/postprocessed-results.json`; model findings/requests were not changed.

## Main result

VERDICT and the checklist baseline both matched the authored initial finding policy on **28/30 cases**. Ordinary initial review matched **20/30**. The result does **not** establish better initial conclusion accuracy than a checklist.

Among 25 cases with a prepared witness response, the first request matched the authored topic screen for A **10/25**, B **9/25**, and VERDICT **21/25**. This suggests useful targeting in this development set. It is a regex-based topic proxy, not independent human relevance adjudication.

On the **same 21 acquired-evidence cases**, VERDICT matched the authored final finding policy on **20/21**; checklist B given the identical new evidence matched **19/21**. This small difference is not evidence of a reliable reasoning advantage. Much of the demonstrated value comes from obtaining missing information, which also helps a simpler reviewer.

| Pipeline | Cases | Authored finding-policy matches | Non-entailed / total claims, model assessed | Mean recorded pipeline latency |
|---|---:|---:|---:|---:|
| A_initial | 30 | 20 | 3/60 | 5.54s |
| B_checklist_initial | 30 | 28 | 1/61 | 5.40s |
| VERDICT_initial | 30 | 28 | 0/62 | 8.44s |
| VERDICT_after_acquisition | 30 | 26 | 2/83 | 9.27s |
| B_matched_new_evidence | 21 | 19 | 4/56 | 5.01s |

## Protocol and important qualifications

- Inputs cover 30 distinct fictional situations: delivery destination/recipient ambiguity, label-only shipments, missing signatures, damaged goods, model/description/accessory discrepancies, duplicate captures versus holds/partial captures, currencies, refund lifecycle, timestamps, unrelated tracking, misleading records, two prompt-injection cases and cases with no proportionate further evidence.
- `cases.json` is investigator input. `labels.json` is loaded only by the harness and contains the prepared response inventory, request regex, recipient and allowable finding labels. Labels are never sent to the investigator or semantic-support reviewer.
- A is a standard one-shot reviewer; B adds a conventional evidence checklist; VERDICT uses the product prompt plus source/semantic checks and qualitative witness prioritization. The baselines share the structured output contract and exact quotation check. Baseline claims receive a separate support-review call for the diagnostic metric; their original conclusions are not rewritten by that evaluation review.
- One top request can unlock one authored fictional witness response when its **topic regex** matches. No external carrier API or human respondent is involved in the benchmark. There is no multi-turn adaptive evidence marketplace here. The actual UI portal→new evidence→reassessment loop was tested separately in the browser.
- **Recipient sensitivity:** only **10/21** topic-matched requests also exactly match the authored recipient category. Some evidence can be forwarded by another party, but this was not adjudicated. Topic-only acquisition is optimistic; it must not be presented as 21 independently validated obtainable witness requests. A stricter human-reviewed acquisition protocol is needed before promoting a superiority claim.
- The final all-case score uses authored final-information labels even on cases where no new evidence was acquired; it is not directly comparable to initial-information accuracy. The matched-evidence comparison is the more useful control.
- Five authored stop cases produced 1, 2 and 2 unnecessary proposed requests for A, B and VERDICT respectively. VERDICT does not dominate the baselines on stopping behavior.
- Source checks rejected 0 claims across distinct recorded analyses. Claim support percentages are judgments by the same model family, not independent factual accuracy. Partial/unsupported claims remain visible as review problems; VERDICT prevents them from supporting hypothesis edges and can downgrade its finding.
- The initial labeling policy favors abstention on incomplete records. Some baseline buyer-supported conclusions may be defensible to a different reviewer. No independent annotation or inter-rater agreement study was performed. Cases were authored by the developer, are short, and are not a held-out test set or representative customer population.
- Contradiction text/topic screens are retained for inspection but are **not** reported as validated contradiction precision/recall. Scope alignment is model-extracted. The final mechanical comparator refuses absent quoted values, timezone-free dates and currency-free amounts, normalizes explicit timestamps to UTC, and performs Decimal amount normalization.
- Recorded A/B latency covers their initial generation, excluding the common evaluation support-review call. VERDICT latency includes its two product calls. Runs before/after rate pacing share the same prompts and model; later latency can include queue waits. These are development observations, not a controlled latency comparison.
- Usage metadata is saved for successful calls. Failed-call usage, provider billing and dollar cost were not independently measured. The provider explicitly reported a **15 requests/minute free-tier** limit. Shared local pacing and RetryInfo handling were added after quota failures, then missing checkpoint slots were completed. Historical failed-attempt records: **11**. These are not discarded or counted as successful analyses.
- No financial operation was performed by the benchmark. Two injected-message cases exercised the prompts; the deterministic authorization tests are stronger evidence of action isolation than model prose. This does not certify resistance to all prompt injection.

## Reproduce

Run `evaluation/build_dataset.py`, then `evaluation/run.py` with the existing virtual environment and private Gemini key. The default run resumes matching dataset/label/model checkpoints. To conduct a fresh replicate, use `--output evaluation/replicate-2.json`; do not overwrite the frozen record. Model sampling, provider version/quota and request timing may change outputs. Generate this report with `evaluation/report.py`.

Dataset SHA-256: `bc09d40aeed2593633c3141d2b370a38cc82bab093abe839a6e3d597a3ccc474`  
Labels SHA-256: `e3dfc421b89416d847640b060f370a0bcad0212372ba938f2fa1c4eccef7a10a`

## Decision

Keep the active investigation workflow as a useful, working product capability. Describe its pilot result as stronger topic targeting on authored fictional cases, with comparable initial conclusion accuracy to a checklist and a small, inconclusive matched-evidence difference. Next evidence needed: independently labeled cases, realistic recipient availability/cost, multiple model seeds and blinded human usability review. Do not claim real PayPal win-rate improvement, production accuracy or superiority over commercial systems.
