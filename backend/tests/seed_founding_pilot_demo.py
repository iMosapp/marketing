"""Seed two Founding Partner Pilot demo customers in preview (idempotent: wipes "QA FP Demo *" first, `--wipe` only removes).
  QA FP Demo Motors  : pilot ACTIVE, owner activated (qa-fp-demo-owner@invalid.imonsocial.test / <password in memory/test_credentials.md>)
  QA FP Demo Fresh   : pilot PENDING, created only (for the founder's Activate -> Invite click-through)
Run: cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && python tests/seed_founding_pilot_demo.py"""
import os
import sys
import time

from pymongo import MongoClient

from tests.live_auth import SUPER_ADMIN, Session, anon, oid
from tests.wipe_pilot_customers import wipe
from tests import qa_creds

PREFIX = "QA FP Demo"
OWNER_EMAIL = "qa-fp-demo-owner@invalid.imonsocial.test"
OWNER_PASSWORD = qa_creds.password_for("qa-pilot-owner-ui@invalid.imonsocial.test")


def main():
    mongo = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    wipe(mongo, PREFIX, dry_run=False)
    if "--wipe" in sys.argv:
        print("wiped")
        return
    sa = Session(*SUPER_ADMIN)
    status, res = sa.post("/api/setup-wizard/new-account", {
        "business_name": f"{PREFIX} Motors", "city": "Lehi", "state": "UT", "zip": "84043", "industry": "Automotive / Dealership",
        "contact_name": "Fran Founding", "contact_email": OWNER_EMAIL, "contact_phone": "+15005550931",
        "plan_key": "pilot_store_monthly", "seats_extra": 1, "pilot": True, "billing_mode": "founding_pilot"})
    assert status == 200, res
    org_id, user_id = res["organization_id"], res["user_id"]
    assert sa.post(f"/api/customers/{org_id}/activate")[0] == 200
    assert sa.post(f"/api/customers/{org_id}/invite-owner")[0] == 200
    tok = mongo.password_reset_tokens.find_one({"user_id": user_id, "purpose": "activate_link", "used": False})
    status, swap = anon("POST", "/api/auth/activate/link", {"token": tok["token"]})
    assert status == 200, swap
    status, done = anon("POST", "/api/auth/activate/complete", {"phone": swap["identifier"], "code": swap["code"], "new_password": OWNER_PASSWORD})
    assert status == 200, done
    for _ in range(20):
        p = mongo.organizations.find_one({"_id": oid(org_id)})["customer"]["pilot_program"]
        if p.get("state") == "active":
            break
        time.sleep(0.5)
    print(f"ACTIVE pilot: {PREFIX} Motors org={org_id} owner={OWNER_EMAIL} / {OWNER_PASSWORD} state={p.get('state')} ends={p.get('ends_at')}")
    status, res2 = sa.post("/api/setup-wizard/new-account", {
        "business_name": f"{PREFIX} Fresh", "city": "Provo", "state": "UT", "zip": "84601", "industry": "Automotive / Dealership",
        "contact_name": "Pat Pending", "contact_email": "qa-fp-demo-fresh@invalid.imonsocial.test", "contact_phone": "+15005550932",
        "plan_key": "pilot_store_monthly", "seats_extra": 0, "pilot": True, "billing_mode": "founding_pilot"})
    assert status == 200, res2
    print(f"PENDING pilot: {PREFIX} Fresh org={res2['organization_id']} (not activated, owner not invited)")


if __name__ == "__main__":
    main()
