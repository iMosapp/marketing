"""Preview-only demo account for the Live Jessi fallback UI (Phase 3). Idempotent.

  python tests/seed_voice_ui_demo.py                       # org "QA Voice UI Org" + qa-voice-ui@invalid.imonsocial.test / <password in memory/test_credentials.md>, policy on (1 min premium, 60 min mini)
  python tests/seed_voice_ui_demo.py --scenario exhausted  # premium off + 1 min of mini (the stop has no fallback -> "Ask Jessi by text")
  python tests/seed_voice_ui_demo.py --scenario refused    # every pool spent today (POST /live-voice/session -> 429)
  python tests/seed_voice_ui_demo.py --reset               # forget today's usage for the user (keeps the scenario)
  python tests/seed_voice_ui_demo.py --flag live|lab       # Test Lab flag jessi_live_voice (reps need `live`; put it back to `lab` after the run)
  python tests/seed_voice_ui_demo.py --backdate <live_id> <seconds>   # pretend an open session started that long ago (server clock meters it)
  python tests/seed_voice_ui_demo.py --wipe
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from pymongo import MongoClient
from tests import qa_creds

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from routers.auth import hash_password  # noqa: E402
from services import voice_controls as vc  # noqa: E402

ORG_NAME = "QA Voice UI Org"
EMAIL = "qa-voice-ui@invalid.imonsocial.test"
PW = qa_creds.password_for("qa-voice-ui@invalid.imonsocial.test")
SCENARIOS = {
    "handoff": {"daily_premium_min": 1, "daily_backup_min": None, "premium_disabled": False},
    "exhausted": {"daily_premium_min": None, "daily_backup_min": 1, "premium_disabled": True},
    "refused": {"daily_premium_min": None, "daily_backup_min": 1, "premium_disabled": True},
}


def main():
    args = sys.argv[1:]
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    now = datetime.now(timezone.utc)
    if "--backdate" in args:
        i = args.index("--backdate")
        live_id, seconds = args[i + 1], float(args[i + 2])
        r = db.live_sessions.update_one({"live_id": live_id}, {"$set": {"started_at": now - timedelta(seconds=seconds)}})
        print(f"backdated {live_id}: matched={r.matched_count}")
        return
    if "--flag" in args:
        status = args[args.index("--flag") + 1]
        db.settings.update_one({"key": "lab_features"}, {"$set": {"value.jessi_live_voice": {"status": status, "changed_at": now, "changed_by_name": "seed_voice_ui_demo"}}}, upsert=True)
        print(f"jessi_live_voice -> {status}")
        return
    org = db.organizations.find_one({"name": ORG_NAME})
    user = db.users.find_one({"email": EMAIL})
    if "--wipe" in args:
        if user:
            uid = str(user["_id"])
            db.live_sessions.delete_many({"user_id": uid})
            db[vc.LEDGER_COLL].delete_many({"user_id": uid})
            db.users.delete_one({"_id": user["_id"]})
        if org:
            oid = str(org["_id"])
            for coll in (vc.LEDGER_COLL, vc.RES_COLL, vc.ACCT_DAY_COLL, vc.ACCT_MONTH_COLL, vc.POLICY_COLL, vc.OVERRIDE_COLL):
                db[coll].delete_many({"org_id": oid})
            db.organizations.delete_one({"_id": org["_id"]})
        print("wiped")
        return
    if not org:
        oid = db.organizations.insert_one({"name": ORG_NAME, "timezone": "America/Denver", "qa_voice": True, "active": True, "created_at": now}).inserted_id
        org = db.organizations.find_one({"_id": oid})
    org_id = str(org["_id"])
    if not user:
        uid = db.users.insert_one({"name": "Voice UI Tester", "email": EMAIL, "password": hash_password(PW), "role": "user", "organization_id": org_id, "store_id": None,
                                   "phone": "+15005550930", "is_active": True, "status": "active", "onboarding_complete": True, "phone_verified": True, "timezone": "America/Denver",
                                   "qa_voice": True, "created_at": now, "updated_at": now}).inserted_id
        user = db.users.find_one({"_id": uid})
    uid = str(user["_id"])
    db[vc.POLICY_COLL].update_one({"org_id": org_id}, {"$set": {**vc.DEFAULT_POLICY, "org_id": org_id, "enabled": True, "per_user_daily_premium_min": 15, "per_user_daily_backup_min": 60,
                                                                 "timezone": "America/Denver", "updated_at": now, "updated_by": "seed_voice_ui_demo"}}, upsert=True)
    scenario = args[args.index("--scenario") + 1] if "--scenario" in args else "handoff"
    ov = SCENARIOS[scenario]
    db[vc.OVERRIDE_COLL].update_one({"org_id": org_id, "user_id": uid}, {"$set": {**ov, "org_id": org_id, "user_id": uid, "super_admin_authorized": False, "grants": [], "notes": f"QA UI scenario {scenario}", "updated_at": now}}, upsert=True)
    day = datetime.now(ZoneInfo("America/Denver")).strftime("%Y-%m-%d")
    if "--reset" in args or "--scenario" in args or not db[vc.RES_COLL].find_one({"_id": f"{org_id}:{uid}:{day}"}):
        db.live_sessions.delete_many({"user_id": uid})
        db[vc.LEDGER_COLL].delete_many({"user_id": uid, "kind": "segment"})
        db[vc.RES_COLL].delete_many({"org_id": org_id})
        db[vc.ACCT_DAY_COLL].delete_many({"org_id": org_id})
        db[vc.ACCT_MONTH_COLL].delete_many({"org_id": org_id})
    if scenario == "refused":
        db[vc.RES_COLL].update_one({"_id": f"{org_id}:{uid}:{day}"}, {"$set": {"org_id": org_id, "user_id": uid, "day": day, "premium_used_s": 0, "premium_reserved_s": 0, "backup_used_s": 60, "backup_reserved_s": 0, "updated_at": now}}, upsert=True)
    print(f"org {org_id} user {uid} scenario={scenario} login {EMAIL} / {PW}")


if __name__ == "__main__":
    main()
