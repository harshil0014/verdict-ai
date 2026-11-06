"""Real local HTTP/Gemini workflow probe using fictional records only.

This is a behavior trace, not an accuracy benchmark or baseline comparison.
No private portal token or session cookie is written to the public results.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from fixtures import DEMOS
from investigator import SYSTEM
from store import now, digest

FOLDER = ROOT / "evaluation/availability-probe"
TITLES = ["The delivery that went somewhere else", "Two charges for one order?"]
REASON = "Fictional test: the intended recipient reported that the requested record is unavailable. No independent verification of that report was supplied."


def save(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(body, indent=2), encoding="utf-8", newline="\n")
    temporary.replace(path)


def protocol():
    return {"name": "request-unavailability-http-probe-v1", "case_titles": TITLES,
        "fixtures_digest": digest([d for d in DEMOS if d["title"] in TITLES]),
        "system_prompt_digest": digest(SYSTEM),
        "app_sha256": hashlib.sha256((ROOT / "backend/app.py").read_bytes()).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "closure_reason": REASON,
        "procedure": "Fresh isolated fictional demo workspace. For each selected case, run production analysis, choose its unique first request, create the scoped portal, mark the request reported unavailable, check revocation/staleness, then run production reassessment. Never substitute a request if none is proposed.",
        "bound": "Two cases; at most four analyses/eight logical generation calls before transport retries, serial. No PayPal operations. Failures checkpointed and not silently retried.",
        "limits": "Authored examples and investigator-reported availability. No independent witness verification. Raw recommendations retained for independent semantic review; no automated paraphrase/availability-accuracy metric or superiority claim. Default model prompt/schema are unchanged."}


def run():
    frozen = json.loads((FOLDER / "protocol.json").read_text(encoding="utf-8"))
    if frozen["protocol"] != protocol():
        raise RuntimeError("Frozen protocol/code differs; do not overwrite this experiment")
    path = FOLDER / "results.json"
    if path.exists():
        raise RuntimeError("Probe already has results; inspect them rather than silently replaying API calls")
    report = {"protocol_digest": digest(frozen), "started_at": now(), "cases": [], "failures": []}
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=180) as c:
        health = c.get("/api/health"); health.raise_for_status()
        assert health.json()["service"] == "VERDICT"
        c.post("/api/auth/demo", json={}).raise_for_status()
        listing = c.get("/api/cases").json()
        for title in TITLES:
            entry = {"title": title}
            report["cases"].append(entry)
            try:
                case = next(x for x in listing if x["title"] == title)
                expected = next(x for x in DEMOS if x["title"] == title)
                assert case["mode"] == "synthetic"
                assert [(e["title"], e["text"], e["party"]) for e in case["evidence"]] == expected["evidence"]
                route = "/api/cases/" + case["id"]
                r = c.post(route + "/analyze", json={"consent": True}); r.raise_for_status()
                initial = r.json(); entry["initial_analysis"] = initial["analysis"]
                save(path, report)
                first = [x for x in initial["analysis"]["requests"] if x["priority"] == "first"]
                if len(first) != 1:
                    entry["status"] = "no_unique_first_request"
                    save(path, report)
                    continue
                r = c.post(route + "/requests", json={"witness_id": first[0]["id"]}); r.raise_for_status()
                request = r.json(); token = request["portal_fragment"].split("=", 1)[1]
                entry["created_request"] = request["request"]
                headers = {"Authorization": "Bearer " + token}
                assert c.get("/api/portal", headers=headers).status_code == 200
                r = c.post(route + "/requests/" + request["request"]["id"] + "/close", json={"status": "unavailable", "reason": REASON}); r.raise_for_status()
                closed = r.json(); entry["closed_request"] = closed["requests"][-1]
                entry["revoked_portal_get_http"] = c.get("/api/portal", headers=headers).status_code
                entry["analysis_marked_stale"] = closed["analysis_stale"]
                assert entry["revoked_portal_get_http"] == 409 and entry["analysis_marked_stale"]
                assert closed["evidence"] == initial["evidence"]
                save(path, report)
                r = c.post(route + "/analyze", json={"consent": True}); r.raise_for_status()
                after = r.json(); entry["after_analysis"] = after["analysis"]
                entry["status"] = "completed"
                entry["proposed_questions_after"] = [{"recipient": w["recipient"], "question": w["question"], "rationale": w["rationale"]} for w in after["analysis"]["requests"]]
                print(title, initial["analysis"]["finding"], "->", after["analysis"]["finding"], "requests after:", len(entry["proposed_questions_after"]), flush=True)
                save(path, report)
            except Exception as e:
                report["failures"].append({"title": title, "error": str(e), "at": now()})
                save(path, report)
                raise
    report["completed_at"] = now()
    save(path, report)
    print(json.dumps({"completed_cases": sum(x.get("status") == "completed" for x in report["cases"]), "failures": report["failures"], "semantic_review_required": True}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["freeze", "run"])
    args = parser.parse_args()
    if args.command == "freeze":
        if (FOLDER / "protocol.json").exists():
            raise SystemExit("Protocol already frozen")
        save(FOLDER / "protocol.json", {"frozen_at": now(), "protocol": protocol()})
        print("Protocol frozen before calls")
    else:
        run()
