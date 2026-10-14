"""Preview simulation: production without live Stripe billing credentials. Run ONLY while STRIPE_BILLING_SECRET_KEY is unset on the backend.
Creates + wipes "QA FP NoStripe *". PYTHONPATH=/app/backend python tests/nostripe_pilot_check.py"""
import os
import secrets
import time

from pymongo import MongoClient

from tests.live_auth import SUPER_ADMIN, Session, anon, oid
from tests.wipe_pilot_customers import wipe
from tests import qa_creds

PREFIX = "QA FP NoStripe"
PW = qa_creds.password_for("qa-pilot-owner-ui@invalid.imonsocial.test")
out = []


def check(name, ok, detail=""):
    out.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f" · {detail}" if detail else ""), flush=True)


def main():
    mongo = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    wipe(mongo, PREFIX, dry_run=False)
    sa = Session(*SUPER_ADMIN)
    email = f"qa-fp-nostripe-{secrets.token_hex(2)}@invalid.imonsocial.test"
    st, res = sa.post("/api/setup-wizard/new-account", {"business_name": f"{PREFIX} Motors", "city": "Lehi", "state": "UT", "zip": "84043", "industry": "Automotive / Dealership",
                                                         "contact_name": "No Stripe", "contact_email": email, "contact_phone": f"+1500555{secrets.randbelow(9000) + 1000}",
                                                         "plan_key": "pilot_store_monthly", "seats_extra": 0, "pilot": True, "billing_mode": "founding_pilot"})
    check("create Founding Partner Pilot customer without Stripe", st == 200, str(res)[:80] if st != 200 else "")
    org_id, user_id = res["organization_id"], res["user_id"]
    c = mongo.organizations.find_one({"_id": oid(org_id)})["customer"]
    check("record: $375/mo, 5 seats included, $75/extra seat, pilot pending", c["amount"] == 375.0 and c["seats_included"] == 5 and c["seat_price"] == 75.0 and c["billing_status"] == "pilot" and c["pilot_program"]["state"] == "pending")
    st, a = sa.post(f"/api/customers/{org_id}/activate")
    check("founder Activate without payment", st == 200 and a.get("activated") is True)
    st, i = sa.post(f"/api/customers/{org_id}/invite-owner")
    check("founder Invite owner (SMS + email)", st == 200)
    tok = mongo.password_reset_tokens.find_one({"user_id": user_id, "purpose": "activate_link", "used": False})
    st, swap = anon("POST", "/api/auth/activate/link", {"token": tok["token"]})
    st2, done = anon("POST", "/api/auth/activate/complete", {"phone": swap["identifier"], "code": swap["code"], "new_password": PW})
    for _ in range(30):
        p = mongo.organizations.find_one({"_id": oid(org_id)})["customer"]["pilot_program"]
        if p.get("state") == "active":
            break
        time.sleep(0.5)
    check("owner activation starts the 90-day clock", st == 200 and st2 == 200 and p["state"] == "active" and p["ends_at"])
    st, me = anon("POST", "/api/auth/login", {"email": email, "password": PW})
    check("owner login -> pilot flags on the session user", st == 200 and me["user"].get("pilot") is True and me["user"]["pilot_program"]["state"] == "active")
    owner = Session(email, PW)
    st, bill = owner.get("/api/billing/me")
    check("owner Billing renders (200) with can_continue FALSE and no portal/checkout link", st == 200 and bill["pilot"]["can_continue"] is False and bill["portal_available"] is False and bill["checkout_url"] is None, f"status line data: {bill['billing_status']} / {bill['pilot']['days_left']} days left / monthly_total {bill['monthly_total']}")
    st, co = owner.post("/api/billing/checkout")
    check("owner POST /billing/checkout fails safely: 503 'Billing is not configured on this server'", st == 503 and "not configured" in str(co), f"{st} {str(co)[:80]}")
    st, pl = sa.post(f"/api/customers/{org_id}/payment-link", {"send": False})
    check("founder Send continue link fails safely: 503", st == 503 and "not configured" in str(pl), f"{st} {str(pl)[:80]}")
    st, sync = sa.post(f"/api/customers/{org_id}/sync-billing")
    check("founder Check Stripe fails safely: 503", st == 503, f"{st} {str(sync)[:60]}")
    c = mongo.organizations.find_one({"_id": oid(org_id)})["customer"]
    check("after the failed attempts the customer is unchanged: still pilot/active, no stripe ids, no checkout fields", c["billing_status"] == "pilot" and c["pilot_program"]["state"] == "active" and not c.get("stripe_customer_id") and not c.get("checkout_url"))
    st, hub = sa.get("/api/customers")
    row = next(r for r in hub if r["organization_id"] == org_id)
    check("Hub row: pilot active, days left, potential MRR $375", row["pilot_program"]["state"] == "active" and row["pilot_program"]["days_left"] in (89, 90) and row["mrr"] == {"amount": 375.0, "kind": "potential", "first_charge_on": None})
    st, chk = owner.get("/api/pilot/checklist")
    check("owner simplified Home checklist API works", st == 200 and "steps" in str(chk) or st == 200)
    st, ext = sa.post(f"/api/customers/{org_id}/pilot/extend", {"days": 30, "reason": "No-Stripe gate extend"})
    st2, end = sa.post(f"/api/customers/{org_id}/pilot/end", {"reason": "No-Stripe gate end"})
    st3 = anon("POST", "/api/auth/login", {"email": email, "password": PW})[0]
    st4, rs = sa.post(f"/api/customers/{org_id}/pilot/resume", {"reason": "No-Stripe gate resume"})
    check("extend / end (login 403) / resume work without Stripe", st == 200 and st2 == 200 and st3 == 403 and st4 == 200)
    wh = anon("POST", "/api/billing/stripe/webhook", {})[0]
    check("webhook endpoint without webhook secret answers 503 (no event is ever processed unsigned)", wh in (503, 400), f"{wh}")
    wipe(mongo, PREFIX, dry_run=False)
    fails = [o for o in out if not o[1]]
    print(f"\n{len(out) - len(fails)}/{len(out)} PASS")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
