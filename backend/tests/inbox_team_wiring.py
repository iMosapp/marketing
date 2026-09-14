"""Inbox = team wiring: eligible people, @inbox ladder token, claim pool, Leads tab overview + one-tap fixes, store linking.
Usage:  cd /app/backend && python tests/inbox_team_wiring.py"""
import asyncio
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from bson import ObjectId

TAG = f"qa_team_wiring_{ObjectId()}"
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(ok)
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"   <- {detail}"))


async def main():
    import routers.database as rdb
    db = rdb.get_db()
    from services import inboxes as ib, team_scope as ts, inbox_leads as il, lead_flows as lf
    from services.lead_call_engine import normalize_attempts
    from routers.lead_queue import source_member_ids

    now = datetime.utcnow()
    sid = str((await db.stores.insert_one({"name": "QA Wiring Store", "timezone": "America/Denver", "qa_tag": TAG, "created_at": now})).inserted_id)
    other_sid = str((await db.stores.insert_one({"name": "QA Other Store", "qa_tag": TAG, "created_at": now})).inserted_id)

    async def mk_user(name, store=None, role="user", phone="+15005550999"):
        doc = {"name": name, "email": f"{name.lower().replace(' ', '')}-{TAG}@test.local", "role": role, "status": "active", "phone": phone, "qa_tag": TAG, "created_at": now}
        if store:
            doc["store_id"] = store
        return str((await db.users.insert_one(doc)).inserted_id)

    mgr = await mk_user("Mia Manager", sid, role="store_manager")
    alice = await mk_user("Alice Rep", sid)
    bob = await mk_user("Bob Rep", sid, phone="")
    bridger = await mk_user("Bridger Outside")                # no store at all (invited at org level)
    jessi = await mk_user("Jessi Elsewhere", other_sid)       # home store is another store
    me = await db.users.find_one({"_id": ObjectId(mgr)})

    inbox_id = (await db.shared_inboxes.insert_one({"name": "Website Inbox", "phone_number": "+15005550700", "assigned_user_ids": [alice, bob, bridger, jessi],
                                                    "store_id": sid, "routing": "jump_ball", "is_active": True, "qa_tag": TAG, "created_at": now})).inserted_id
    inbox = await db.shared_inboxes.find_one({"_id": inbox_id})

    # 1. eligible people: store members + inbox members who live elsewhere
    scope = await ts.eligible_people(db, sid, me)
    ids = {p["id"]: p for p in scope["people"]}
    check("1a store members are eligible", alice in ids and bob in ids and mgr in ids)
    check("1b inbox member with no store shows up (via inbox)", bridger in ids and ids[bridger]["via"] == ["inbox"], str(ids.get(bridger, {}).get("via")))
    check("1c inbox member from another store shows up", jessi in ids and "inbox" in ids[jessi]["via"])
    check("1d everyone is flagged on_team", all(p["on_team"] for p in scope["people"]))
    reps = await lf.store_reps(db, sid, me)
    check("1e lead flow rep picker sees the whole inbox team", {alice, bob, bridger, jessi, mgr} <= {r["_id"] for r in reps}, str(len(reps)))
    everyone = await ts.eligible_people(db, sid, me, include_everyone=True)
    check("1f include_everyone appends outsiders as not on team", any(not p["on_team"] for p in everyone["people"]) and all(p["on_team"] for p in everyone["people"][:5]))

    # 2. @inbox resolution + claim pool
    src_id = (await db.lead_sources.insert_one({"name": "Web Form", "store_id": sid, "team_id": str(inbox_id), "assignment_method": "jump_ball", "contact_mode": "text_and_call",
                                                "workflow_user_ids": [alice], "call_attempts": [{"user_ids": [alice], "delay_seconds": 30}], "is_active": True, "qa_tag": TAG, "created_at": now})).inserted_id
    src = await db.lead_sources.find_one({"_id": src_id})
    eff = await ib.apply_inbox(db, src)
    check("2a everyone on the inbox joins the notify / claim pool", set(eff["workflow_user_ids"]) == {alice, bob, bridger, jessi}, str(eff["workflow_user_ids"]))
    check("2b ladder untouched when no token", eff["call_attempts"][0]["user_ids"] == [alice])
    check("2c inbox_member_ids carried", set(eff.get("inbox_member_ids") or []) == {alice, bob, bridger, jessi})
    check("2d claim pool (lead queue) includes inbox members", {bob, bridger, jessi} <= source_member_ids(eff))
    tok = {**src, "call_attempts": [{"user_ids": ["@inbox", alice], "delay_seconds": 0}, {"user_ids": [mgr], "delay_seconds": 60}]}
    eff2 = await ib.apply_inbox(db, tok)
    check("2e @inbox resolves to the members, no dupes, order kept", eff2["call_attempts"][0]["user_ids"] == [alice, bob, bridger, jessi], str(eff2["call_attempts"][0]["user_ids"]))
    check("2f later attempts untouched", eff2["call_attempts"][1]["user_ids"] == [mgr])
    lonely = await ib.apply_inbox(db, {"name": "no inbox", "workflow_user_ids": ["@inbox", alice], "call_attempts": [{"user_ids": ["@inbox"], "delay_seconds": 0}]})
    check("2g token on a source with no inbox is dropped, not dialed", lonely["workflow_user_ids"] == [alice] and lonely["call_attempts"][0]["user_ids"] == [])
    check("2h call engine skips stray tokens", normalize_attempts([{"user_ids": ["@inbox"], "delay_seconds": 0}], ["@inbox"]) == [])
    check("2i call engine keeps real ids", normalize_attempts([{"user_ids": ["@inbox", alice], "delay_seconds": 0}], []) [0]["user_ids"] == [alice])

    # 3. Leads tab overview
    ov = await il.overview(db, inbox)
    row = next(r for r in ov["sources"] if r["id"] == str(src_id))
    check("3a pointed source listed with ringing = some", row["ringing"]["kind"] == "some" and "Alice" in row["ringing"]["names"], str(row["ringing"]))
    check("3b missing names are the never-rung members", set(row["ringing"]["missing"]) == {"Bob", "Bridger", "Jessi"}, str(row["ringing"]["missing"]))
    check("3c checklist flags partial ringing", ov["checklist"]["ringing_ok"] is False and ov["checklist"]["sources"] == 1 and ov["checklist"]["members"] == 4)
    check("3d no-cell member surfaced", ov["checklist"]["members_without_cell"] == ["Bob"], str(ov["checklist"]["members_without_cell"]))

    # 4. ring everyone on a source with its own ladder
    changed = await il.ring_everyone(db, inbox, str(src_id), me)
    fresh = await db.lead_sources.find_one({"_id": src_id})
    check("4a token written to attempt 1 of the source", changed["changed"] == "source" and fresh["call_attempts"][0]["user_ids"][0] == "@inbox" and alice in fresh["call_attempts"][0]["user_ids"], str(fresh["call_attempts"]))
    ov = await il.overview(db, inbox)
    row = next(r for r in ov["sources"] if r["id"] == str(src_id))
    check("4b overview now says everyone (dynamic)", row["ringing"]["kind"] == "everyone" and row["ringing"]["dynamic"] and ov["checklist"]["ringing_ok"] is True, str(row["ringing"]))
    eff3 = await ib.apply_inbox(db, fresh)
    check("4c the job that would be created rings all four", set(normalize_attempts(eff3["call_attempts"], eff3["workflow_user_ids"])[0]["user_ids"]) == {alice, bob, bridger, jessi})

    # 5. ring everyone through an attached flow (flow wins, synced to every source using it)
    flow_id = (await db.lead_flows.insert_one({**lf.DEFAULT_FLOW, "name": "QA flow", "store_id": sid, "call_attempts": [{"user_ids": [alice], "delay_seconds": 0, "delivery": "call"}], "qa_tag": TAG, "created_at": now})).inserted_id
    src2_id = (await db.lead_sources.insert_one({"name": "ADF Feed", "store_id": sid, "inbox_id": str(inbox_id), "team_id": str(inbox_id), "flow_id": str(flow_id), "flow_name": "QA flow",
                                                 **lf.flow_fields(await db.lead_flows.find_one({"_id": flow_id})), "is_active": True, "qa_tag": TAG, "created_at": now})).inserted_id
    changed = await il.ring_everyone(db, inbox, str(src2_id), me)
    flow = await db.lead_flows.find_one({"_id": flow_id})
    mirrored = await db.lead_sources.find_one({"_id": src2_id})
    check("5a flow attempt 1 gained the token", changed["changed"] == "flow" and flow["call_attempts"][0]["user_ids"][0] == "@inbox", str(flow["call_attempts"]))
    check("5b mirrored onto the source", mirrored["call_attempts"][0]["user_ids"][0] == "@inbox")
    check("5c flow summary names the inbox", any("everyone on the inbox" in r["text"] for r in lf.summarize(flow, {"@inbox": "everyone on the inbox"})))

    # 6. point / unpoint
    loose_id = (await db.lead_sources.insert_one({"name": "Facebook", "store_id": sid, "is_active": True, "qa_tag": TAG, "created_at": now})).inserted_id
    ov = await il.overview(db, inbox)
    check("6a loose source offered under other_sources", any(o["id"] == str(loose_id) and o["inbox_name"] is None for o in ov["other_sources"]))
    await il.point_source(db, inbox, str(loose_id), me)
    pointed = await db.lead_sources.find_one({"_id": loose_id})
    check("6b pointing sets inbox_id + team_id", pointed["inbox_id"] == str(inbox_id) and pointed["team_id"] == str(inbox_id))
    await il.unpoint_source(db, inbox, str(loose_id))
    unp = await db.lead_sources.find_one({"_id": loose_id})
    check("6c unpointing clears both", not unp.get("inbox_id") and unp.get("team_id") == "")
    try:
        await il.point_source(db, inbox, str(inbox.get("direct_source_id") or ObjectId()), me)
        check("6d cannot point a missing / direct source", False)
    except ValueError:
        check("6d cannot point a missing / direct source", True)
    foreign_id = (await db.lead_sources.insert_one({"name": "Foreign", "store_id": other_sid, "is_active": True, "qa_tag": TAG, "created_at": now})).inserted_id
    try:
        await il.point_source(db, inbox, str(foreign_id), me)
        check("6e manager cannot pull another store's source", False)
    except PermissionError:
        check("6e manager cannot pull another store's source", True)

    # 7. linking members to the store
    n = await ts.link_to_store(db, [alice, bridger, jessi, mgr], sid)
    b = await db.users.find_one({"_id": ObjectId(bridger)})
    j = await db.users.find_one({"_id": ObjectId(jessi)})
    check("7a two people needed linking", n == 2, str(n))
    check("7b no-store member gets store_id", b.get("store_id") == sid)
    check("7c other-store member gets store_ids", j.get("store_id") == other_sid and sid in (j.get("store_ids") or []))
    check("7d idempotent", await ts.link_to_store(db, [bridger, jessi], sid) == 0)

    # cleanup
    for coll in ("users", "stores", "shared_inboxes", "lead_sources", "lead_flows"):
        await db[coll].delete_many({"qa_tag": TAG})
    await db.lead_sources.delete_many({"kind": "inbox_direct", "inbox_id": str(inbox_id)})
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} passed")
    sys.exit(0 if all(RESULTS) else 1)


if __name__ == "__main__":
    asyncio.run(main())
