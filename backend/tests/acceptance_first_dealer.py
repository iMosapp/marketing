"""First-dealership acceptance walk (preview only): founder creates a disposable "QA Sales Ready *" dealership, owner + rep activate,
first contact, card share, first text, inbound reply, campaign enrollment, manager visibility, permission scoping; wipes everything.
Run: PYTHONPATH=/app/backend python tests/acceptance_first_dealer.py   (24/24 on Oct 14 2026)"""
import json
import os
import secrets
import time
from datetime import datetime, timedelta, timezone

import requests
from bson import ObjectId
from pymongo import MongoClient

from tests._http import API, UA
from tests.live_auth import SUPER_ADMIN, Session, anon
from tests.wipe_pilot_customers import wipe
from tests import qa_creds

PREFIX = "QA Sales Ready"
PW_OWNER = "SalesReady123!"
PW_REP = "SalesRep123!"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
R = []


def rec(step, ok, detail=""):
    R.append((step, "PASS" if ok else "FAIL", str(detail)[:300]))
    print(f"{'PASS' if ok else 'FAIL'} | {step} | {str(detail)[:300]}", flush=True)


def note(step, detail):
    R.append((step, "INFO", str(detail)[:300]))
    print(f"INFO | {step} | {str(detail)[:300]}", flush=True)


def phone():
    return f"+1500555{secrets.randbelow(9000) + 1000}"


def activate_by_link(user_id, password):
    tok = db.password_reset_tokens.find_one({"user_id": user_id, "purpose": "activate_link", "used": False})
    st, swap = anon("POST", "/api/auth/activate/link", {"token": tok["token"]})
    assert st == 200, swap
    return anon("POST", "/api/auth/activate/complete", {"phone": swap["identifier"], "code": swap["code"], "new_password": password})


created_user_ids, org_id = [], None
try:
    sa = Session(*SUPER_ADMIN)
    sfx = secrets.token_hex(3)
    owner_phone, rep_phone, cust_phone = phone(), phone(), phone()
    owner_email = f"qa-salesready-owner-{sfx}@invalid.imonsocial.test"
    rep_email = f"qa-salesready-rep-{sfx}@invalid.imonsocial.test"

    # 1. Founder creates the dealership (paid plan, billing exception instead of a charge)
    body = {"business_name": f"{PREFIX} Motors {sfx}", "city": "Sandy", "state": "UT", "zip": "84070", "industry": "Automotive / Dealership",
            "contact_name": f"Olive Owner{sfx}", "contact_email": owner_email, "contact_phone": owner_phone,
            "plan_key": "pilot_store_monthly", "seats_extra": 0, "pilot": True}
    st, res = sa.post("/api/setup-wizard/new-account", body)
    rec("1 founder creates dealership (org+store+dormant owner)", st == 200, {k: res.get(k) for k in ("organization_id", "store_id", "user_id")} if st == 200 else res)
    org_id, store_id, owner_id = res["organization_id"], res["store_id"], res["user_id"]
    created_user_ids.append(owner_id)
    st, b = anon("POST", "/api/auth/login", {"email": owner_email, "password": "anything123"})
    rec("1b dormant owner cannot sign in before activation", st in (401, 403), st)
    expires = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
    rec("2 billing exception (no charge) recorded", sa.post(f"/api/customers/{org_id}/billing-exception", {"reason": "Sales readiness QA", "expires_at": expires})[0] == 200)
    rec("3 founder activates account", sa.post(f"/api/customers/{org_id}/activate")[0] == 200)
    st, inv = sa.post(f"/api/customers/{org_id}/invite-owner")
    rec("4 founder sends owner activation link (text+email)", st == 200, inv)
    link = db.password_reset_tokens.find_one({"user_id": owner_id, "purpose": "activate_link", "used": False})
    short = db.short_urls.find_one({"link_type": "activation", "reference_id": owner_id})
    note("4b activation link target", (short or {}).get("original_url", "")[:120] or "no short url row")

    # 5. Owner activates + signs in
    st, done = activate_by_link(owner_id, PW_OWNER)
    rec("5 owner activation (link -> code -> password)", st == 200, st)
    st, me = anon("POST", "/api/auth/login", {"email": owner_email, "password": PW_OWNER})
    u = me.get("user", {}) if st == 200 else {}
    rec("5b owner login: pilot owner, store_manager, no slideshow gate", st == 200 and u.get("pilot") and u.get("pilot_owner") and u.get("role") == "store_manager",
        {k: u.get(k) for k in ("role", "pilot", "pilot_owner", "pilot_billing_status", "needs_password_change", "onboarding_complete")})
    owner = Session(owner_email, PW_OWNER)
    st, cl = owner.get("/api/pilot/checklist")
    rec("6 owner GET SET UP checklist 0/5", st == 200 and cl.get("done") == 0 and cl.get("total") == 5, [s["key"] for s in cl.get("steps", [])])
    for _ in range(10):
        c = db.organizations.find_one({"_id": ObjectId(org_id)})["customer"]
        if c.get("owner_activated_at"):
            break
        time.sleep(0.5)
    rec("6b founder notified / owner_activated_at stamped", bool(c.get("owner_activated_at")), c.get("onboarding_status"))

    # 7. Owner invites a salesperson
    payload = {"first_name": "Riley", "last_name": f"Rep{sfx}", "name": f"Riley Rep{sfx}", "email": rep_email, "phone": rep_phone, "role": "user",
               "send_invite": True, "send_sms": True, "organization_id": org_id, "store_id": store_id, "title": "Sales Consultant"}
    st, cr = owner.post("/api/admin/users/create", payload)
    rep_id = (cr or {}).get("user_id") or (cr or {}).get("user", {}).get("_id") if isinstance(cr, dict) else None
    if not rep_id:
        doc = db.users.find_one({"email": rep_email})
        rep_id = str(doc["_id"]) if doc else None
    if rep_id:
        created_user_ids.append(rep_id)
    rec("7 owner invites salesperson (invite email + activation SMS)", st == 200 and bool(rep_id), {k: cr.get(k) for k in ("success", "sms_sent", "invite_sent", "contact_created", "activation_flow")} if isinstance(cr, dict) else cr)
    rep_doc = db.users.find_one({"_id": ObjectId(rep_id)})
    note("7b rep defaults", {"role": rep_doc.get("role"), "activation_pending": rep_doc.get("activation_pending"), "store_id": rep_doc.get("store_id") == store_id,
                             "feature_permissions_set": bool(rep_doc.get("feature_permissions")), "twilio_number": rep_doc.get("twilio_number")})
    seeded = {c: db[c].count_documents({"user_id": rep_id}) for c in ("templates", "sms_templates", "email_templates", "campaigns", "tags", "date_triggers")}
    note("7c seeded defaults for rep", seeded)

    # 8. Rep activates with the SMS code path (the code text goes to a 500-555 number; read the code from the DB)
    st, rq = anon("POST", "/api/auth/activate/request", {"phone": rep_phone})
    tok = db.password_reset_tokens.find_one({"user_id": rep_id, "purpose": "activate", "used": False}, sort=[("created_at", -1)])
    st2, fin = anon("POST", "/api/auth/activate/complete", {"phone": rep_phone, "code": (tok or {}).get("code", ""), "new_password": PW_REP})
    rec("8 rep activation (phone -> SMS code -> password)", st == 200 and st2 == 200, (st, st2, fin if st2 != 200 else ""))
    st, me = anon("POST", "/api/auth/login", {"email": rep_email, "password": PW_REP})
    ru = me.get("user", {}) if st == 200 else {}
    rec("8b rep login lands as pilot rep", st == 200 and ru.get("pilot") is True and not ru.get("pilot_owner"),
        {k: ru.get(k) for k in ("role", "pilot", "pilot_owner", "jessi_welcome_pending", "onboarding_complete")})
    fp = ru.get("feature_permissions") or {}
    note("8c rep visible tools (true flags)", {sec: sorted(k for k, v in (vals or {}).items() if v) for sec, vals in fp.items() if isinstance(vals, dict)})
    rep = Session(rep_email, PW_REP)
    st, cl = rep.get("/api/pilot/checklist")
    rec("8d rep has own GET SET UP checklist", st == 200 and cl.get("total") == 5, cl.get("done") if st == 200 else cl)

    # 9. Twilio number (compliance dry_run only)
    mode = (db.settings.find_one({"key": "twilio_compliance"}) or {}).get("mode", "dry_run")
    rep_number = None
    if mode == "dry_run":
        st, view = sa.post(f"/api/admin/organizations/{org_id}/twilio/provision")
        rec("9 founder provisions Twilio subaccount (dry_run fake SIDs)", st == 200, (view or {}).get("provisioning_status") if isinstance(view, dict) else view)
        st, found = sa.get(f"/api/admin/organizations/{org_id}/twilio/numbers/search?area_code=801&limit=3")
        nums = (found or {}).get("numbers") or (found or {}).get("results") or [] if isinstance(found, dict) else []
        pick = (nums[0].get("phone_number") if nums and isinstance(nums[0], dict) else None)
        st, bought = sa.post(f"/api/admin/organizations/{org_id}/twilio/numbers", {"phone_number": pick, "assigned_user_id": rep_id}) if pick else (0, "no search result")
        rep_number = db.users.find_one({"_id": ObjectId(rep_id)}).get("twilio_number")
        rec("9b number bought (fake) + assigned to rep", st == 200 and bool(rep_number), {"picked": pick, "rep_twilio_number": rep_number, "status": st})
        st, view = sa.get(f"/api/admin/organizations/{org_id}/twilio")
        if isinstance(view, dict):
            note("9c messaging readiness", {k: view.get(k) for k in ("provisioning_status", "messaging_ready", "messaging_status", "blockers")})
    else:
        note("9 skipped Twilio provisioning", f"compliance mode is {mode}, not dry_run")

    # 10. Profile -> card -> contact -> share
    st, _ = rep.put(f"/api/profile/{rep_id}", {"title": "Sales Consultant", "bio": "Here to make car buying easy."})
    note("10 rep profile update", st)
    st, contact = rep.post(f"/api/contacts/{rep_id}", {"first_name": "Casey", "last_name": f"Customer{sfx}", "phone": cust_phone, "email": f"casey-{sfx}@invalid.imonsocial.test"})
    contact_id = (contact or {}).get("_id") or (contact or {}).get("id") if isinstance(contact, dict) else None
    rec("10b rep creates first contact", st == 200 and bool(contact_id), st)
    st, shared = rep.post(f"/api/contacts/{rep_id}/find-or-create-and-log", {"phone": cust_phone, "name": f"Casey Customer{sfx}", "event_type": "digital_card_shared",
                                                                              "event_title": "Share My Card", "event_channel": "sms"})
    rec("10c rep shares digital card (logged)", st == 200, st)
    st, card = anon("GET", f"/api/card/data/{rep_id}")
    note("10d public digital card data", st)

    # 11. First outbound SMS + inbound reply
    st, conv = rep.post(f"/api/messages/conversations/{rep_id}", {"contact_id": contact_id, "contact_phone": cust_phone})
    conv_id = (conv or {}).get("_id") or (conv or {}).get("id") if isinstance(conv, dict) else None
    rec("11 conversation created", st == 200 and bool(conv_id), st)
    st, sent = rep.post(f"/api/messages/send/{rep_id}/{conv_id}", {"content": "Hi Casey, it's Riley. Great meeting you today!", "conversation_id": conv_id})
    note("11b first outbound SMS (500-555 recipient: Twilio rejects by design)", {"http": st, "status": (sent or {}).get("status") if isinstance(sent, dict) else sent,
                                                                               "error": (sent or {}).get("error") if isinstance(sent, dict) else ""})
    if rep_number:
        sid = "SMqasr" + secrets.token_hex(12)
        r = requests.post(API + "/api/webhooks/twilio/incoming", data={"From": cust_phone, "To": rep_number, "Body": "Thanks Riley! Is the blue one still there?",
                                                                       "MessageSid": sid, "NumMedia": "0"}, headers=UA, timeout=40)
        time.sleep(3)
        inbound = db.messages.find_one({"conversation_id": conv_id, "sender": {"$in": ["contact", "customer"]}}) or db.messages.find_one({"twilio_sid": sid}) or db.messages.find_one({"message_sid": sid})
        rec("11c inbound customer reply routed to the rep's thread", r.status_code in (200, 204) and bool(inbound), {"webhook": r.status_code, "found": bool(inbound),
                                                                                                                  "conv": str((inbound or {}).get("conversation_id")) == conv_id})
    # 12. Campaign enrollment
    st, camps = rep.get(f"/api/campaigns/{rep_id}")
    clist = camps if isinstance(camps, list) else (camps or {}).get("campaigns", []) if isinstance(camps, dict) else []
    active = [c for c in clist if c.get("active")]
    note("12 rep campaigns", {"total": len(clist), "active": len(active), "names": [c.get("name") for c in clist][:6]})
    if active:
        cid = active[0].get("_id") or active[0].get("id")
        st, en = rep.post(f"/api/campaigns/{rep_id}/{cid}/enroll/{contact_id}")
        rec("12b enroll first contact in a campaign", st == 200, en if st != 200 else active[0].get("name"))
    elif clist:
        cid = clist[0].get("_id") or clist[0].get("id")
        st, en = rep.post(f"/api/campaigns/{rep_id}/{cid}/enroll/{contact_id}")
        rec("12b enroll first contact in a campaign (no active seeded campaign)", st == 200, (st, en))
    else:
        rec("12b enroll first contact in a campaign", False, "rep has no campaigns")

    # 13. Manager visibility
    st, team = owner.get(f"/api/admin/users?store_id={store_id}")
    names = [x.get("email") for x in (team if isinstance(team, list) else (team or {}).get("users", []))] if st == 200 else team
    rec("13 owner sees the rep on the team list", st == 200 and rep_email in (names or []), st)
    st, convs = owner.get(f"/api/messages/conversations/{rep_id}")
    note("13b owner opens rep's conversations", st)
    st, cl = rep.get("/api/pilot/checklist")
    note("13c rep checklist after activity", {s["key"]: s["done"] for s in cl.get("steps", [])} if st == 200 else cl)
    st, row = sa.get(f"/api/customers/{org_id}")
    if isinstance(row, dict):
        note("13d founder customer row", {k: row.get(k) for k in ("onboarding_status", "billing_status", "seats", "progress", "attention")} if "onboarding_status" in row else list(row.keys())[:12])

    # 14. Gate 5: visibility controls
    st, p = owner.get(f"/api/admin/permissions/{rep_id}")
    rec("14 owner reads rep permissions", st == 200, st)
    perms = p.get("permissions", {}) if isinstance(p, dict) else {}
    newp = json.loads(json.dumps(perms))
    newp.setdefault("my_tools", {})["voice_memos"] = False
    st, up = owner.put(f"/api/admin/permissions/{rep_id}", {"permissions": newp})
    st2, me2 = anon("POST", "/api/auth/login", {"email": rep_email, "password": PW_REP})
    rec("14b owner hides a tool for the rep without a developer", st == 200 and st2 == 200, {"put": st, "rep_sees_voice_memos": ((me2.get("user") or {}).get("feature_permissions") or {}).get("my_tools", {}).get("voice_memos")})
    other = db.users.find_one({"email": "activation-tester@invalid.imonsocial.test"}, {"_id": 1})
    st, _ = owner.get(f"/api/admin/permissions/{other['_id']}")
    rec("14c owner CANNOT read another company's rep permissions", st in (403, 404), f"HTTP {st} for a user outside the owner's org")
    st, bl = rep.get(f"/api/broadcast?user_id={rep_id}")
    note("14d rep (broadcast tile hidden) calls broadcast list API", {"http": st, "rep_broadcast_flag": fp.get("campaigns", {}).get("broadcast")})
finally:
    if org_id:
        ids = [i for i in created_user_ids if i]
        oids = [ObjectId(i) for i in ids]
        removed = {}
        for name in db.list_collection_names():
            n = 0
            for q in ({"user_id": {"$in": ids}}, {"created_by": {"$in": ids}}, {"organization_id": org_id}, {"assigned_user_id": {"$in": ids}}):
                if name in ("users", "organizations"):
                    continue
                try:
                    n += db[name].delete_many(q).deleted_count
                except Exception:
                    pass
            if n:
                removed[name] = n
        removed["wipe"] = wipe(db, PREFIX, dry_run=False)
        db.users.delete_many({"_id": {"$in": oids}})
        left = {"org": db.organizations.count_documents({"name": {"$regex": f"^{PREFIX}"}}), "users": db.users.count_documents({"email": {"$regex": "qa-salesready-"}})}
        print("CLEANUP", removed, "LEFT", left, flush=True)
    print("SUMMARY", sum(1 for r in R if r[1] == "PASS"), "pass", sum(1 for r in R if r[1] == "FAIL"), "fail", flush=True)
