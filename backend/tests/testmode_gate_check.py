"""Preview simulation of PRODUCTION with a Stripe TEST key and no BILLING_ALLOW_TEST_MODE flag: paid conversion must be paused,
complimentary pilots untouched. Run ONLY while BILLING_ALLOW_TEST_MODE is absent from the backend env (see release notes).
Creates + wipes "QA FP TestMode *". PYTHONPATH=/app/backend python tests/testmode_gate_check.py"""
import hashlib
import hmac
import json
import os
import secrets
import time

from pymongo import MongoClient

from tests._http import API, UA, call
from tests.live_auth import SUPER_ADMIN, Session, anon, oid
from tests.wipe_pilot_customers import wipe

PREFIX = "QA FP TestMode"
PW = "PilotOwner123!"
MSG = "Stripe TEST mode"
out = []


def check(name, ok, detail=""):
    out.append((name, ok))
    print(("PASS " if ok else "FAIL ") + name + (f" · {detail}" if detail else ""), flush=True)


def signed_event(secret: str, event: dict):
    payload = json.dumps(event)
    ts = int(time.time())
    sig = hmac.new(secret.encode(), f"{ts}.{payload}".encode(), hashlib.sha256).hexdigest()
    return payload, f"t={ts},v1={sig}"


def main():
    mongo = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    wipe(mongo, PREFIX, dry_run=False)
    sa = Session(*SUPER_ADMIN)
    email = f"qa-fp-testmode-{secrets.token_hex(2)}@invalid.imonsocial.test"
    st, res = sa.post("/api/setup-wizard/new-account", {"business_name": f"{PREFIX} Motors", "city": "Lehi", "state": "UT", "zip": "84043", "industry": "Automotive / Dealership",
                                                         "contact_name": "Test Mode", "contact_email": email, "contact_phone": f"+1500555{secrets.randbelow(9000) + 1000}",
                                                         "plan_key": "pilot_store_monthly", "seats_extra": 1, "pilot": True, "billing_mode": "founding_pilot"})
    check("complimentary pilot: create", st == 200, str(res)[:80] if st != 200 else "")
    org_id, user_id = res["organization_id"], res["user_id"]
    check("complimentary pilot: Activate without payment", sa.post(f"/api/customers/{org_id}/activate")[0] == 200)
    check("complimentary pilot: Invite owner", sa.post(f"/api/customers/{org_id}/invite-owner")[0] == 200)
    tok = mongo.password_reset_tokens.find_one({"user_id": user_id, "purpose": "activate_link", "used": False})
    st, swap = anon("POST", "/api/auth/activate/link", {"token": tok["token"]})
    st2, _ = anon("POST", "/api/auth/activate/complete", {"phone": swap["identifier"], "code": swap["code"], "new_password": PW})
    for _ in range(30):
        p = mongo.organizations.find_one({"_id": oid(org_id)})["customer"]["pilot_program"]
        if p.get("state") == "active":
            break
        time.sleep(0.5)
    check("complimentary pilot: owner activation starts the 90-day clock", st == 200 and st2 == 200 and p["state"] == "active")
    st, row = sa.get(f"/api/customers/{org_id}")
    check("founder row: billing_config {configured, mode test, conversion_enabled FALSE}", st == 200 and row["billing_config"] == {"configured": True, "mode": "test", "conversion_enabled": False}, json.dumps(row.get("billing_config")))
    owner = Session(email, PW)
    st, me = owner.get("/api/billing/me")
    check("owner Billing: renders, can_continue FALSE, no portal, no checkout link, conversion_enabled FALSE", st == 200 and me["pilot"]["can_continue"] is False and me["portal_available"] is False and me["checkout_url"] is None and me["conversion_enabled"] is False and me["billing_mode"] == "test")
    st, co = owner.post("/api/billing/checkout")
    check("owner POST /billing/checkout -> 503 with the TEST-mode message", st == 503 and MSG in str(co), f"{st} {str(co)[:90]}")
    st, pl = sa.post(f"/api/customers/{org_id}/payment-link", {"send": False})
    check("founder Send continue link -> 503 with the TEST-mode message", st == 503 and MSG in str(pl), f"{st} {str(pl)[:90]}")
    st, sync = sa.post(f"/api/customers/{org_id}/sync-billing")
    check("founder Check Stripe (read-only) still answers", st in (200, 409), f"{st}")
    c = mongo.organizations.find_one({"_id": oid(org_id)})["customer"]
    check("nothing created: no Stripe customer / session on the record, still pilot/active", not c.get("stripe_customer_id") and not c.get("checkout_session_id") and c["billing_status"] == "pilot")
    st, hub = sa.get("/api/customers")
    r = next(x for x in hub if x["organization_id"] == org_id)
    check("Hub row: pilot active, potential MRR $450", r["pilot_program"]["state"] == "active" and r["mrr"]["kind"] == "potential" and r["mrr"]["amount"] == 450.0)
    st, _ = sa.post(f"/api/customers/{org_id}/pilot/extend", {"days": 30, "reason": "Test-mode gate extend"})
    st2, _ = sa.post(f"/api/customers/{org_id}/pilot/end", {"reason": "Test-mode gate end"})
    st3 = anon("POST", "/api/auth/login", {"email": email, "password": PW})[0]
    st4, _ = sa.post(f"/api/customers/{org_id}/pilot/resume", {"reason": "Test-mode gate resume"})
    check("extend / end (login 403) / resume unaffected", st == 200 and st2 == 200 and st3 == 403 and st4 == 200)
    # a correctly signed TEST-mode webhook event must be acknowledged and ignored
    secret = os.environ["STRIPE_BILLING_WEBHOOK_SECRET"]
    ev = {"id": f"evt_testmode_{secrets.token_hex(6)}", "object": "event", "type": "customer.subscription.updated", "livemode": False, "created": int(time.time()),
          "data": {"object": {"id": "sub_testmode_fake", "object": "subscription", "status": "active", "customer": "cus_fake", "metadata": {"organization_id": org_id}}}}
    payload, sig = signed_event(secret, ev)
    import urllib.error
    import urllib.request
    req = urllib.request.Request(API + "/api/billing/stripe/webhook", method="POST", data=payload.encode(), headers={"Content-Type": "application/json", "Stripe-Signature": sig, **UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            wst, body = r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        wst, body = e.code, e.read().decode()[:120]
    c = mongo.organizations.find_one({"_id": oid(org_id)})["customer"]
    check("signed TEST-mode webhook event: 200 acknowledged, ignored as test_event, customer untouched", wst == 200 and body.get("ignored") and body.get("test_event") and c["billing_status"] == "pilot" and mongo.stripe_events.find_one({"_id": ev["id"]})["result"] == "ignored_test_event", json.dumps(body)[:100])
    wipe(mongo, PREFIX, dry_run=False)
    fails = [o for o in out if not o[1]]
    print(f"\n{len(out) - len(fails)}/{len(out)} PASS")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
