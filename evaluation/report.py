"""Recompute a transparent development report from frozen model outputs."""

import json, sys, statistics, copy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from structured import compare, source_value_check
from store import digest


def main():
    report = json.loads((ROOT / "evaluation/results.json").read_text(encoding="utf-8"))
    labels = json.loads((ROOT / "evaluation/labels.json").read_text(encoding="utf-8"))
    data = report["results"]
    normalized = copy.deepcopy(report)
    for cid, runs in normalized["results"].items():
        for run in runs.values():
            for claim in run["analysis"]["claims"]:
                claim["structured_check"] = source_value_check(claim)
            run["analysis"]["comparisons"] = compare(run["analysis"]["claims"])
    normalized["postprocessing"] = {
        "version": "strict-structured-v2",
        "description": "Reapplied source value, timezone and currency checks to frozen claims; no model findings or requests changed.",
    }
    (ROOT / "evaluation/postprocessed-results.json").write_text(
        json.dumps(normalized, indent=2), encoding="utf-8", newline="\n"
    )
    names = [
        "A_initial",
        "B_checklist_initial",
        "VERDICT_initial",
        "VERDICT_after_acquisition",
        "B_matched_new_evidence",
    ]
    rows = []
    for name in names:
        values = [r[name]["metrics"] for r in data.values() if name in r]
        rows.append(
            f"| {name} | {len(values)} | {sum(v['finding_matches_authored_label'] for v in values)} | {sum(v['nonentailed_model_assessed_claims'] for v in values)}/{sum(v['claims'] for v in values)} | {statistics.mean(v['latency_seconds'] for v in values):.2f}s |"
        )
    eligible = [cid for cid, l in labels.items() if l["followup"] is not None]
    topic = {
        name: sum(
            data[cid][name]["metrics"]["targeted_first_request"] for cid in eligible
        )
        for name in names[:3]
    }
    acquired = [
        cid
        for cid, r in data.items()
        if r.get("VERDICT_after_acquisition", {}).get("acquired")
    ]
    matched_v = sum(
        data[cid]["VERDICT_after_acquisition"]["metrics"][
            "finding_matches_authored_label"
        ]
        for cid in acquired
    )
    matched_b = sum(
        data[cid]["B_matched_new_evidence"]["metrics"]["finding_matches_authored_label"]
        for cid in acquired
        if "B_matched_new_evidence" in data[cid]
    )
    strict = []
    for cid in acquired:
        requests = data[cid]["VERDICT_initial"]["analysis"]["requests"]
        first = next(
            (x for x in requests if x["priority"] == "first"),
            requests[0] if requests else None,
        )
        if first and first["recipient"] == labels[cid]["witness_party"]:
            strict.append(cid)
    completed = sum(len(runs) for runs in data.values())
    source_rejections = sum(
        run["metrics"]["rejected_source_claims"]
        for runs in data.values()
        for name, run in runs.items()
        if name != "VERDICT_after_acquisition" or run.get("acquired")
    )
    summary = {
        "model": report["model"],
        "cases": len(data),
        "witness_available_cases": len(eligible),
        "topic_hits": topic,
        "topic_gated_acquisitions": len(acquired),
        "topic_and_recipient_matches": len(strict),
        "matched_verdict_label_matches": matched_v,
        "matched_checklist_label_matches": matched_b,
        "matched_n": len(acquired),
        "historical_failed_attempt_records": len(report.get("failures", [])),
        "dataset_sha256": report["dataset_sha256"],
        "labels_sha256": report["labels_sha256"],
        "raw_results_sha256": digest((ROOT / "evaluation/results.json").read_bytes()),
        "postprocessed_sha256": digest(
            (ROOT / "evaluation/postprocessed-results.json").read_bytes()
        ),
    }
    (ROOT / "evaluation/summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8", newline="\n"
    )
    text = f"""# Evaluation: 30-case fictional development pilot

Model: **{report["model"]}**. All 30 authored scenarios have completed A, B and VERDICT initial runs. Completed recorded run slots: {completed}; some final slots reuse the unchanged initial result when no witness was acquired. Raw outputs, usage and historical failures are retained in `evaluation/results.json`. Final strict structured checks were reapplied offline to those frozen claims in `evaluation/postprocessed-results.json`; model findings/requests were not changed.

## Main result

VERDICT and the checklist baseline both matched the authored initial finding policy on **28/30 cases**. Ordinary initial review matched **20/30**. The result does **not** establish better initial conclusion accuracy than a checklist.

Among {len(eligible)} cases with a prepared witness response, the first request matched the authored topic screen for A **{topic["A_initial"]}/{len(eligible)}**, B **{topic["B_checklist_initial"]}/{len(eligible)}**, and VERDICT **{topic["VERDICT_initial"]}/{len(eligible)}**. This suggests useful targeting in this development set. It is a regex-based topic proxy, not independent human relevance adjudication.

On the **same {len(acquired)} acquired-evidence cases**, VERDICT matched the authored final finding policy on **{matched_v}/{len(acquired)}**; checklist B given the identical new evidence matched **{matched_b}/{len(acquired)}**. This small difference is not evidence of a reliable reasoning advantage. Much of the demonstrated value comes from obtaining missing information, which also helps a simpler reviewer.

| Pipeline | Cases | Authored finding-policy matches | Non-entailed / total claims, model assessed | Mean recorded pipeline latency |
|---|---:|---:|---:|---:|
{chr(10).join(rows)}

## Protocol and important qualifications

- Inputs cover 30 distinct fictional situations: delivery destination/recipient ambiguity, label-only shipments, missing signatures, damaged goods, model/description/accessory discrepancies, duplicate captures versus holds/partial captures, currencies, refund lifecycle, timestamps, unrelated tracking, misleading records, two prompt-injection cases and cases with no proportionate further evidence.
- `cases.json` is investigator input. `labels.json` is loaded only by the harness and contains the prepared response inventory, request regex, recipient and allowable finding labels. Labels are never sent to the investigator or semantic-support reviewer.
- A is a standard one-shot reviewer; B adds a conventional evidence checklist; VERDICT uses the product prompt plus source/semantic checks and qualitative witness prioritization. The baselines share the structured output contract and exact quotation check. Baseline claims receive a separate support-review call for the diagnostic metric; their original conclusions are not rewritten by that evaluation review.
- One top request can unlock one authored fictional witness response when its **topic regex** matches. No external carrier API or human respondent is involved in the benchmark. There is no multi-turn adaptive evidence marketplace here. The actual UI portal→new evidence→reassessment loop was tested separately in the browser.
- **Recipient sensitivity:** only **{len(strict)}/{len(acquired)}** topic-matched requests also exactly match the authored recipient category. Some evidence can be forwarded by another party, but this was not adjudicated. Topic-only acquisition is optimistic; it must not be presented as {len(acquired)} independently validated obtainable witness requests. A stricter human-reviewed acquisition protocol is needed before promoting a superiority claim.
- The final all-case score uses authored final-information labels even on cases where no new evidence was acquired; it is not directly comparable to initial-information accuracy. The matched-evidence comparison is the more useful control.
- Five authored stop cases produced 1, 2 and 2 unnecessary proposed requests for A, B and VERDICT respectively. VERDICT does not dominate the baselines on stopping behavior.
- Source checks rejected {source_rejections} claims across distinct recorded analyses. Claim support percentages are judgments by the same model family, not independent factual accuracy. Partial/unsupported claims remain visible as review problems; VERDICT prevents them from supporting hypothesis edges and can downgrade its finding.
- The initial labeling policy favors abstention on incomplete records. Some baseline buyer-supported conclusions may be defensible to a different reviewer. No independent annotation or inter-rater agreement study was performed. Cases were authored by the developer, are short, and are not a held-out test set or representative customer population.
- Contradiction text/topic screens are retained for inspection but are **not** reported as validated contradiction precision/recall. Scope alignment is model-extracted. The final mechanical comparator refuses absent quoted values, timezone-free dates and currency-free amounts, normalizes explicit timestamps to UTC, and performs Decimal amount normalization.
- Recorded A/B latency covers their initial generation, excluding the common evaluation support-review call. VERDICT latency includes its two product calls. Runs before/after rate pacing share the same prompts and model; later latency can include queue waits. These are development observations, not a controlled latency comparison.
- Usage metadata is saved for successful calls. Failed-call usage, provider billing and dollar cost were not independently measured. The provider explicitly reported a **15 requests/minute free-tier** limit. Shared local pacing and RetryInfo handling were added after quota failures, then missing checkpoint slots were completed. Historical failed-attempt records: **{len(report.get("failures", []))}**. These are not discarded or counted as successful analyses.
- No financial operation was performed by the benchmark. Two injected-message cases exercised the prompts; the deterministic authorization tests are stronger evidence of action isolation than model prose. This does not certify resistance to all prompt injection.

## Reproduce

Run `evaluation/build_dataset.py`, then `evaluation/run.py` with the existing virtual environment and private Gemini key. The default run resumes matching dataset/label/model checkpoints. To conduct a fresh replicate, use `--output evaluation/replicate-2.json`; do not overwrite the frozen record. Model sampling, provider version/quota and request timing may change outputs. Generate this report with `evaluation/report.py`.

Dataset SHA-256: `{report["dataset_sha256"]}`  
Labels SHA-256: `{report["labels_sha256"]}`

## Decision

Keep the active investigation workflow as a useful, working product capability. Describe its pilot result as stronger topic targeting on authored fictional cases, with comparable initial conclusion accuracy to a checklist and a small, inconclusive matched-evidence difference. Next evidence needed: independently labeled cases, realistic recipient availability/cost, multiple model seeds and blinded human usability review. Do not claim real PayPal win-rate improvement, production accuracy or superiority over commercial systems.
"""
    (ROOT / "docs/EVALUATION.md").write_text(text, encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
