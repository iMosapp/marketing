"""E2E check for Lead Flows: attach -> mirror -> intake ladder from flow -> exhausted automations -> claim tags -> sync -> detach.
Safe: only Twilio test-range numbers, manager push disabled. Restores the Website source afterwards."""
import asyncio, os, sys, json
import httpx
from dotenv import load_dotenv
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
API = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL")][0] + "/api"
TESTER = "6a978d68b8673c29063aa8b9"     # +15005550006
QA = "6a9b2b82cc6e7504dafc33f2"
WEBSITE = "69a787ca70ae63ea0ac69251"
FLOW_KEYS = ["contact_mode", "call_attempts", "workflow_user_ids", "notify_all_on_intake", "intake_text", "after_hours_text", "intake_delay_seconds",
             "no_answer_text", "va_enabled", "inquiry_context", "after_hours_mode", "text_window_start", "text_window_end", "caller_id_mode",
             "auto_call_on_claim", "tags_on_claim", "tags_on_no_answer", "exhausted_text_lead", "exhausted_push_manager", "flow_id", "flow_name"]
ok = 0; bad = 0
def check(name, cond, extra=""):
    global ok, bad
    ok += cond; bad += (not cond)
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra else ""))


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    original = await db.lead_sources.find_one({"_id": ObjectId(WEBSITE)})
    saved = {k: original.get(k) for k in FLOW_KEYS}
    created_convs, created_contacts = [], []
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{API}/auth/login", json={"email": "qa-manager@invalid.imonsocial.test", "password": "Manager123!"})
        H = {"Authorization": f"Bearer {r.json().get('token') or r.json().get('access_token')}"}
        # clean template flow created during smoke test
        await db.lead_flows.delete_many({"template_key": "ring_all_then_manager", "name": "Ring everyone, then the manager"})
        try:
            # 1. validation
            r = await c.post(f"{API}/lead-flows", json={"name": "bad", "contact_mode": "text_and_call", "call_attempts": []}, headers=H)
            check("400 when Text+Call has no reps", r.status_code == 400, r.text[:80])
            # 2. create test flow
            body = {"name": "E2E Test Flow", "contact_mode": "text_and_call", "after_hours_mode": "ring_anyway", "text_window_start": "00:00", "text_window_end": "23:59",
                    "call_attempts": [{"user_ids": [TESTER], "delay_seconds": 0, "delivery": "call"}, {"user_ids": [TESTER], "delay_seconds": 30, "delivery": "push"}],
                    "intake_text": "E2E intake {{first_name}}", "no_answer_text": "E2E no answer {{first_name}}", "tags_on_claim": ["Working", "E2EClaim"],
                    "tags_on_no_answer": ["Lost Contact", "E2ENoAnswer"], "exhausted_text_lead": True, "exhausted_push_manager": False, "auto_call_on_claim": True}
            r = await c.post(f"{API}/lead-flows", json=body, headers=H)
            flow = r.json(); fid = flow["id"]
            check("create flow", r.status_code == 200 and flow["call_attempts"][1]["delivery"] == "push", str(flow.get("summary", []))[:120])
            check("workflow_user_ids derived", flow["workflow_user_ids"] == [TESTER])
            # 3. attach
            r = await c.put(f"{API}/lead-flows/source/{WEBSITE}", json={"flow_id": fid}, headers=H)
            src = await db.lead_sources.find_one({"_id": ObjectId(WEBSITE)})
            check("attach mirrors flow onto source", r.status_code == 200 and src.get("flow_id") == fid and src.get("intake_text") == "E2E intake {{first_name}}" and len(src["call_attempts"]) == 2)
            r = await c.get(f"{API}/lead-sources/{WEBSITE}/workflow", headers=H)
            check("workflow endpoint exposes flow", r.json().get("flow", {}).get("id") == fid and r.json().get("flow_id") == fid)
            r = await c.get(f"{API}/lead-flows", headers=H)
            mine = next(f for f in r.json()["flows"] if f["id"] == fid)
            check("library shows source usage", mine["source_count"] == 1 and mine["sources"][0]["id"] == WEBSITE)
            # 4. source-level save cannot override flow fields
            r = await c.put(f"{API}/lead-sources/{WEBSITE}/workflow", json={"intake_text": "OVERRIDE", "just_tried_text": "e2e just tried"}, headers=H)
            src = await db.lead_sources.find_one({"_id": ObjectId(WEBSITE)})
            check("flow wins over source save", r.status_code == 200 and src["intake_text"] == "E2E intake {{first_name}}" and src.get("just_tried_text") == "e2e just tried")
            # 5. test lead -> ladder from flow
            r = await c.post(f"{API}/lead-sources/{WEBSITE}/test-lead", json={"phone": "5005550006", "first_name": "E2E", "last_name": "Flow"}, headers=H)
            res = r.json(); conv_id = res.get("conversation_id"); created_convs.append(conv_id); created_contacts.append(res.get("contact_id"))
            check("test lead accepted", r.status_code == 200 and bool(conv_id), json.dumps(res.get("plan", {}))[:160])
            await asyncio.sleep(4)
            job = await db.lead_call_jobs.find_one({"conversation_id": conv_id})
            check("ladder job built from flow (2 attempts, 2nd push)", bool(job) and len(job["attempts"]) == 2 and job["attempts"][1].get("delivery") == "push", str((job or {}).get("attempts")))
            check("attempt 1 fired instantly", bool(job) and job.get("attempt_index") == 1 and job["calls"] and job["calls"][0]["user_id"] == TESTER, str([(x.get("status"), x.get("error", "")[:60]) for x in (job or {}).get("calls", [])]))
            intake = await db.messages.find_one({"conversation_id": conv_id, "is_intake_text": True})
            deferred = await db.lead_deferred_actions.find_one({"conversation_id": conv_id, "kind": "intake_text"})
            check("intake text from flow used", (intake and "E2E intake E2E" in intake["content"]) or (deferred and "E2E intake E2E" in deferred["body"]), (intake or deferred or {}).get("content") or (deferred or {}).get("body"))
            print("   waiting for attempt 2 (push) + exhaustion window (~75s)...")
            for _ in range(20):
                await asyncio.sleep(5)
                job = await db.lead_call_jobs.find_one({"conversation_id": conv_id})
                if job.get("exhausted_actions") is not None:
                    break
            check("attempt 2 delivered as push", any(x.get("kind") == "push" for x in job.get("calls", [])), str([(x.get("kind"), x.get("status")) for x in job["calls"]]))
            check("job exhausted + flow actions ran", job.get("status") == "exhausted" and job.get("exhausted_actions") is not None, str(job.get("exhausted_actions")))
            contact = await db.contacts.find_one({"_id": ObjectId(res["contact_id"])})
            check("no-answer tags applied", "E2ENoAnswer" in (contact.get("tags") or []) and "Lost Contact" in contact.get("tags", []), str(contact.get("tags")))
            na = await db.messages.find_one({"conversation_id": conv_id, "is_no_answer_text": True})
            check("no-answer text attempted (sent or Twilio-rejected test number)", na is not None or any("no-answer text" in a for a in job.get("exhausted_actions", [])), str(job.get("exhausted_actions")))
            # 6. claim -> tags_on_claim
            r = await c.post(f"{API}/lead-sources/claim/{conv_id}?user_id={QA}", headers=H)
            await asyncio.sleep(2)
            contact = await db.contacts.find_one({"_id": ObjectId(res["contact_id"])})
            check("claim applies tags_on_claim", r.status_code == 200 and "E2EClaim" in contact.get("tags", []) and "Working" in contact.get("tags", []), str(contact.get("tags")))
            # 7. edit flow -> sync to source
            r = await c.put(f"{API}/lead-flows/{fid}", json={"intake_text": "E2E intake v2 {{first_name}}", "name": "E2E Test Flow v2"}, headers=H)
            src = await db.lead_sources.find_one({"_id": ObjectId(WEBSITE)})
            check("flow edit syncs to source", r.status_code == 200 and r.json().get("synced_sources") == 1 and src["intake_text"] == "E2E intake v2 {{first_name}}" and src["flow_name"] == "E2E Test Flow v2")
            # 8. duplicate
            r = await c.post(f"{API}/lead-flows/{fid}/duplicate", headers=H)
            dup = r.json(); check("duplicate", r.status_code == 200 and dup["name"].endswith("(copy)") and dup["source_count"] == 0)
            await db.lead_flows.delete_one({"_id": ObjectId(dup["id"])})
            # 9. delete guarded, then detach
            r = await c.delete(f"{API}/lead-flows/{fid}", headers=H)
            check("delete blocked while attached (409)", r.status_code == 409)
            r = await c.put(f"{API}/lead-flows/source/{WEBSITE}", json={"flow_id": None}, headers=H)
            src = await db.lead_sources.find_one({"_id": ObjectId(WEBSITE)})
            check("detach keeps settings, clears flow_id", r.status_code == 200 and "flow_id" not in src and src["intake_text"] == "E2E intake v2 {{first_name}}")
            r = await c.delete(f"{API}/lead-flows/{fid}", headers=H)
            check("delete after detach", r.status_code == 200)
            # 10. rep cannot access
            r2 = await c.post(f"{API}/auth/login", json={"email": "activation-tester@invalid.imonsocial.test", "password": "NewPass123!"})
            tok = r2.json().get("token") or r2.json().get("access_token")
            r = await c.get(f"{API}/lead-flows", headers={"Authorization": f"Bearer {tok}"})
            check("rep gets 403", r.status_code == 403, str(r.status_code))
        finally:
            # restore + cleanup
            unset = {k: "" for k in FLOW_KEYS if saved.get(k) is None}
            sets = {k: v for k, v in saved.items() if v is not None}
            upd = {}
            if sets: upd["$set"] = sets
            if unset: upd["$unset"] = unset
            await db.lead_sources.update_one({"_id": ObjectId(WEBSITE)}, upd)
            await db.lead_flows.delete_many({"name": {"$regex": "^E2E Test Flow"}})
            for cid in created_convs:
                if cid:
                    await db.conversations.delete_one({"_id": ObjectId(cid)}); await db.messages.delete_many({"conversation_id": cid})
                    await db.lead_call_jobs.delete_many({"conversation_id": cid}); await db.lead_deferred_actions.delete_many({"conversation_id": cid})
                    await db.inbound_leads.delete_many({"conversation_id": cid}); await db.notifications.delete_many({"conversation_id": cid})
            for kid in created_contacts:
                if kid:
                    await db.contacts.delete_one({"_id": ObjectId(kid)}); await db.contact_events.delete_many({"contact_id": kid})
                    await db.campaign_enrollments.delete_many({"contact_id": kid}); await db.campaign_pending_sends.delete_many({"contact_id": kid})
            restored = await db.lead_sources.find_one({"_id": ObjectId(WEBSITE)})
            print("restored Website source:", restored.get("intake_text", "")[:40], restored.get("call_attempts"), "flow_id" in restored)
    print(f"\n{ok} passed, {bad} failed")
    sys.exit(1 if bad else 0)

asyncio.run(main())
