"""READ-ONLY launch-gate report: subscription access classes and texting-sender mapping. Writes nothing (no index builds, no updates).
Usage: cd /app/backend && python tests/launch_gate_report.py [--json out.json]
Sections:
  billing  every organization's access class (internal / pilot / exception / subscribed / legacy / unclassified), lock state, review/expiry
  senders  every user holding a texting number: organization, registry row, org Twilio readiness and the sender-policy decision
  orphans  contacts whose user_id is not an existing account (never changed here)
The same queries are listed for production in /app/memory/LAUNCH_GATE_FINAL.md (run there only read-only, through the deployer)."""
import argparse
import asyncio
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

HEX24 = re.compile(r"^[0-9a-fA-F]{24}$")


async def senders(db) -> dict:
    from services import phone_numbers as pn
    from services import sender_policy as sp
    rows = []
    q = {"$or": [{"twilio_number": {"$nin": [None, ""]}}, {"mvpline_number": {"$nin": [None, ""]}}]}
    async for u in db.users.find(q, {"email": 1, "role": 1, "organization_id": 1, "store_id": 1, "twilio_number": 1, "mvpline_number": 1, "status": 1}):
        number = u.get("mvpline_number") or u.get("twilio_number")
        reg = await pn.by_phone(db, number, include_released=True)
        oid = str(u.get("organization_id") or "")
        org = await db.organizations.find_one({"_id": ObjectId(oid)}, {"name": 1, "twilio": 1, "internal": 1}) if HEX24.match(oid) else None
        t = (org or {}).get("twilio") or {}
        pol = await sp.check(db, from_phone=number, user_id=str(u["_id"]), org_id=None, platform=False)
        rows.append({
            "user": u.get("email"), "user_id": str(u["_id"]), "role": u.get("role"), "status": u.get("status"), "number": number,
            "organization_id": oid or None, "organization_resolves": bool(org), "org_name": (org or {}).get("name"),
            "registry": {"found": bool(reg), "status": (reg or {}).get("status"), "org_matches": bool(reg) and str(reg.get("organization_id") or "") == oid,
                         "assigned_to_user": bool(reg) and str(reg.get("assigned_user_id") or "") == str(u["_id"]), "number_type": (reg or {}).get("number_type"),
                         "account_sid_matches_org": bool(reg) and bool(t.get("subaccount_sid")) and reg.get("twilio_account_sid") == t.get("subaccount_sid"),
                         "messaging_service_matches_org": bool(reg) and bool(t.get("messaging_service_sid")) and reg.get("messaging_service_sid") == t.get("messaging_service_sid")},
            "org_twilio": {"subaccount": bool(t.get("subaccount_sid")), "messaging_ready": bool(t.get("messaging_ready")), "messaging_service": bool(t.get("messaging_service_sid"))},
            "decision": {"allowed": pol["allowed"], "code": pol["code"], "internal_org": not pol.get("dealership") and bool(pol.get("org_id"))},
        })
    unassigned = await db.phone_numbers.count_documents({"$or": [{"assigned_user_id": {"$in": [None, ""]}}, {"assigned_user_id": {"$exists": False}}]})
    by_code: dict = {}
    for r in rows:
        by_code[r["decision"]["code"]] = by_code.get(r["decision"]["code"], 0) + 1
    return {"holders": len(rows), "by_decision": by_code, "without_org": [r["user"] for r in rows if not r["organization_resolves"]],
            "registry_rows": await db.phone_numbers.count_documents({}), "registry_unassigned": unassigned,
            "internal_org_ids": sorted(await sp.internal_org_ids(db)), "rows": rows}


async def orphans(db) -> dict:
    out = []
    async for c in db.contacts.find({"$or": [{"user_id": {"$not": HEX24}}, {"user_id": None}, {"user_id": {"$exists": False}}]},
                                    {"user_id": 1, "first_name": 1, "last_name": 1, "created_at": 1, "source": 1}).limit(500):
        out.append({"id": str(c["_id"]), "user_id": c.get("user_id"), "name": f"{c.get('first_name') or ''} {c.get('last_name') or ''}".strip(),
                    "created_at": str(c.get("created_at")), "source": c.get("source")})
    return {"count": len(out), "contacts": out}


async def main(path):
    from services import billing_lock
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    rep = {"billing": await billing_lock.classification_report(db), "senders": await senders(db), "orphans": await orphans(db)}
    b, s, o = rep["billing"], rep["senders"], rep["orphans"]
    print("BILLING classes:", b["counts"], "| locked now:", [(r["name"], r["reason"]) for r in b["locked"]])
    print("  non-ObjectId organization ids:", [r["id"] for r in b["organizations"] if not r["id_is_objectid"]])
    print("SENDERS holders:", s["holders"], "| decisions:", s["by_decision"], "| without a resolvable org:", s["without_org"],
          "| registry rows:", s["registry_rows"], "unassigned:", s["registry_unassigned"], "| internal orgs:", s["internal_org_ids"])
    print("ORPHAN contacts:", o["count"], [(c["id"], c["user_id"], c["name"]) for c in o["contacts"]][:20])
    if path:
        with open(path, "w") as f:
            json.dump(rep, f, indent=1, default=str)
        print("written", path)


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--json")
    asyncio.run(main(a.parse_args().json))
