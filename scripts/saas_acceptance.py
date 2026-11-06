"""Real two-account cloud acceptance. Private state is never a public artifact.

Run with --phase prepare, then restart/redeploy and run --phase verify.
The prepare phase uses the public registration and investigation endpoints, real
Gemini calls, synthetic user-authored evidence, and no payment/provider writes.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import httpx

ROOT = Path(__file__).resolve().parents[1]


def run(base, phase, state_path, report_path):
    state = json.loads(state_path.read_text()) if state_path.exists() else {"actors": []}
    checks = {}
    def save():
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=2))
    def check(name, condition):
        checks[name] = bool(condition)
        if not condition:
            raise AssertionError(name)
    def ok(response):
        # Do not log provider bodies or account details on failure.
        if response.status_code != 200:
            try: detail = response.json().get('detail','')
            except ValueError: detail = 'Non-JSON service response'
            state['last_failure']={'status':response.status_code,'detail':detail if isinstance(detail,str) else 'Validation failed'}
            save()
            if isinstance(detail,str) and detail.startswith(('Gemini ', 'The model returned', 'Cloud database', 'Non-JSON')):
                print(json.dumps({'acceptance_failure_status':response.status_code,'safe_service_diagnostic':detail}))
            raise AssertionError("Unexpected HTTP status: " + str(response.status_code))
        return response.json()
    clients = []
    try:
        for i in range(2):
            label = f"actor_{i+1}"
            c = httpx.Client(base_url=base, timeout=240, follow_redirects=False,
                             limits=httpx.Limits(max_keepalive_connections=0))
            clients.append(c)
            if len(state["actors"]) <= i:
                if phase != "prepare": raise AssertionError("Missing prepared accounts")
                actor = {"username": "saas_qa_"+secrets.token_hex(6), "password": secrets.token_urlsafe(24), "display_name": "Acceptance "+str(i+1)}
                registration = ok(c.post("/api/auth/register", json=actor))
                actor["recovery_code"] = registration["recovery_code"]
                actor["registered_through_public_api"] = True
                state["actors"].append(actor); save()
                check(label+"_empty_on_registration", ok(c.get("/api/cases")) == [])
            else:
                actor = state["actors"][i]
                ok(c.post("/api/auth/login", json={k:actor[k] for k in ("username","password")}))
            check(label+"_authenticated", ok(c.get("/api/me"))["role"] == "member")
            check(label+"_http_only_cookie", any(v.name == "verdict_account_session" and v.has_nonstandard_attr("HttpOnly") for v in c.cookies.jar))
            if phase == "prepare":
                if "case_id" not in actor:
                    case = ok(c.post("/api/cases", json={"title": "Acceptance private case "+str(i+1), "reason":"ITEM_NOT_RECEIVED", "amount":"1.00", "currency":"USD"}))
                    actor["case_id"] = case["id"]; save()
                path = "/api/cases/"+actor["case_id"]
                if "original_id" not in actor:
                    raw = (f"Synthetic acceptance record for actor {i+1}. Order TEST-{i+1}. Buyer reports no parcel received. Seller reports a reception scan; recipient and destination are not confirmed. No actual payment or shipment occurred.").encode()
                    case = ok(c.post(path+"/upload", files={"file":("own-record.txt",raw,"text/plain")}, data={"party":"seller"}))
                    actor.update(original_id=case["evidence"][-1]["id"], original_sha256=hashlib.sha256(raw).hexdigest()); save()
                if "witness_id" not in actor:
                    result = ok(c.post(path+"/requests", json={"witness_id":"manual","title":"Destination clarification", "question":"For this synthetic test, which destination and recipient were recorded?", "recipient":"carrier"}))
                    actor["witness_id"] = result["request"]["id"]
                    actor["portal_token"] = result["portal_fragment"].split("=",1)[1]; save()
                case = ok(c.get(path))
                witness = next(r for r in case["requests"] if r["id"]==actor["witness_id"])
                header = {"Authorization":"Bearer "+actor["portal_token"]}
                if witness["status"]=="open":
                    with httpx.Client(base_url=base,timeout=60,limits=httpx.Limits(max_keepalive_connections=0)) as recipient:
                        portal = ok(recipient.get("/api/portal",headers=header))
                        check(label+"_portal_minimal_projection", set(portal)=={"id","title","question","recipient","expires_at"})
                        response = b"Synthetic carrier response: recipient and delivery destination are unavailable. No fulfillment is established."
                        ok(recipient.post("/api/portal/upload",headers=header,files={"file":("carrier-response.txt",response,"text/plain")}))
                        check(label+"_portal_replay_denied", recipient.post("/api/portal",headers=header,json={"title":"Replay","text":"Duplicate response"}).status_code==409)
                case = ok(c.get(path))
                if not case.get("analysis") or case.get("analysis_stale"):
                    ok(c.post(path+"/analyze",json={"consent":True}))
                    case = ok(c.get(path))
                check(label+"_real_analysis", bool(case.get("analysis",{}).get("model")) and bool(case["analysis"].get("created_at")))
                check(label+"_claim_sources_exist", all(claim["source_id"] in {s["id"] for s in case["evidence"]} for claim in case["analysis"]["claims"]))
                actor["expected_revision"] = case["revision"]
                actor["expected_analysis_hash"] = hashlib.sha256(json.dumps(case["analysis"],sort_keys=True).encode()).hexdigest()
                actor["expected_audit_hash"] = case["timeline"][-1]["hash"]
                received = next(r for r in case['requests'] if r['id']==actor['witness_id'])
                actor['witness_original_id'] = received['evidence_id']
                actor['witness_original_sha256'] = next(s['sha256'] for s in case['evidence'] if s['id']==received['evidence_id'])
                save()
            path = "/api/cases/"+actor["case_id"]
            case = ok(c.get(path))
            check(label+"_durable_revision", case["revision"]==actor["expected_revision"])
            check(label+"_durable_analysis", hashlib.sha256(json.dumps(case["analysis"],sort_keys=True).encode()).hexdigest()==actor["expected_analysis_hash"])
            check(label+"_durable_audit", case["audit_valid"] and case["timeline"][-1]["hash"]==actor["expected_audit_hash"])
            check(label+"_durable_witness", any(r["id"]==actor["witness_id"] and r["status"]=="received" for r in case["requests"]) and any(s["party"]=="carrier" and s["origin"]=="portal_upload" for s in case["evidence"]))
            downloaded = c.get(path+"/files/"+actor["original_id"])
            check(label+"_original_bytes_match", downloaded.status_code==200 and hashlib.sha256(downloaded.content).hexdigest()==actor["original_sha256"])
            witness_file = c.get(path+'/files/'+actor['witness_original_id'])
            check(label+'_witness_original_bytes_match',witness_file.status_code==200 and hashlib.sha256(witness_file.content).hexdigest()==actor['witness_original_sha256'])
            check(label+"_private_no_store", "no-store" in downloaded.headers.get("cache-control",""))
        for i,c in enumerate(clients):
            label = f"actor_{i+1}"
            foreign = state["actors"][1-i]
            path = "/api/cases/"+foreign["case_id"]
            check(label+"_foreign_list_hidden", all(row["id"] != foreign["case_id"] for row in ok(c.get("/api/cases"))))
            for suffix in ("", "/export", "/files/"+foreign["original_id"]):
                check(label+"_foreign_read_denied_"+str(len(checks)), c.get(path+suffix).status_code==404)
            for suffix,payload in (("/evidence",{"title":"Denied","text":"Cross-account write"}), ("/analyze",{"consent":True}), ("/requests",{"title":"Denied","question":"Forbidden request", "recipient":"other"}), ("/requests/"+foreign["witness_id"]+"/close",{"status":"withdrawn","reason":"Forbidden update"})):
                check(label+"_foreign_write_denied_"+str(len(checks)), c.post(path+suffix,json=payload).status_code==404)
            check(label+"_foreign_upload_denied", c.post(path+"/upload",files={"file":("denied.txt",b"Forbidden")}).status_code==404)
            old_cookie = c.cookies.get("verdict_account_session")
            ok(c.post("/api/auth/logout"))
            check(label+"_logout_revoked", c.get("/api/me",headers={"Cookie":"verdict_account_session="+old_cookie}).status_code==401)
            actor = state["actors"][i]
            ok(c.post("/api/auth/login",json={k:actor[k] for k in ("username","password")}))
            case = ok(c.get("/api/cases/"+actor["case_id"]))
            check(label+"_return_retains_data", case["audit_valid"] and case["revision"]==actor["expected_revision"])
        report = {"checked_at":datetime.now(timezone.utc).isoformat(),"base_url":base,"phase":phase,"actors":2,
            "actor_type":"independent automated public account sessions; not two human usability sessions",
            "evidence":"synthetic user-authored test records; real cloud persistence and real Gemini investigation",
            "checks":checks,"all_passed":all(checks.values()),"payment_or_dispute_writes":0}
        report_path.parent.mkdir(parents=True,exist_ok=True)
        report_path.write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2))
    finally:
        for c in clients: c.close()


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--base",default="http://127.0.0.1:8001")
    p.add_argument("--phase",choices=("prepare","verify"),required=True)
    p.add_argument("--state",type=Path,default=ROOT/"runtime/saas-acceptance-private.json")
    p.add_argument("--report",type=Path,default=ROOT/"work/saas-acceptance.json")
    args=p.parse_args()
    run(args.base,args.phase,args.state,args.report)
