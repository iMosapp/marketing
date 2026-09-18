"""Who mentioned X: cross-contact search over texts, call transcripts, voice memos and notes (real LLM for term expansion + verification)."""
import os
import subprocess
import json
import pytest
from bson import ObjectId
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from routers.database import get_db  # noqa: E402
from services import memory_search as ms  # noqa: E402
from services import live_voice as lv  # noqa: E402

pytestmark = pytest.mark.asyncio
TAG = "QA Mentions"
API = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip()


def _c(uid, first, last, phone, **extra):
    now = datetime.now(timezone.utc)
    return {"_id": ObjectId(), "user_id": uid, "first_name": first, "last_name": last, "phone": phone, "status": "active", "tags": [TAG], "created_at": now, "updated_at": now, **extra}


async def _seed(db, uid):
    now = datetime.now(timezone.utc)
    dana = _c(uid, "Dana", "QA-Cole", "+15005550701")
    mike = _c(uid, "Mike", "QA-Ross", "+15005550702")
    nb = _c(uid, "Neighbor", "QA-Guy", "+15005550703")
    note = _c(uid, "Priya", "QA-Note", "+15005550704", notes="Wants a used Model 3 under 20k, prefers white, no rush.")
    bud = _c(uid, "Bud", "QA-Sold", "+15005550705", vehicle="2024 Chevy Tahoe", date_sold="2026-03-12", tags=[TAG, "sold"],
             purchase_history=[{"id": "qa1", "title": "2024 Chevy Tahoe", "category": "vehicle", "date": "2026-03-12", "notes": "Traded a 2018 Silverado", "source": "qa"}])
    await db.contacts.insert_many([dana, mike, nb, note, bud])
    memo = {"_id": ObjectId(), "user_id": uid, "contact_id": str(dana["_id"]), "kind": "memo", "title": "Dana call", "duration": 41,
            "transcript": "Met Dana at the service drive. She said she's looking for a Tesla Model 3, wants to stay around twenty grand, maybe twenty-two tops, and asked if we ever get them in.",
            "summary": "Dana is shopping for a Model 3 around 20k.", "created_at": now - timedelta(days=32)}
    await db.voice_notes.insert_one(memo)
    conv = {"_id": ObjectId(), "user_id": uid, "contact_id": str(mike["_id"]), "channel": "sms", "last_message_at": now - timedelta(days=60), "created_at": now, "updated_at": now}
    await db.conversations.insert_one(conv)
    msg = {"_id": ObjectId(), "conversation_id": str(conv["_id"]), "contact_id": str(mike["_id"]), "user_id": uid, "sender": "contact", "direction": "inbound",
           "content": "Do you guys ever take Model 3s on trade? I'd swap mine for something with more room.", "timestamp": now - timedelta(days=60), "channel": "sms"}
    await db.messages.insert_one(msg)
    call = {"_id": ObjectId(), "user_id": uid, "contact_id": str(nb["_id"]), "contact_name": "Neighbor QA-Guy", "direction": "inbound", "duration_s": 120,
            "transcript": "Rep: Thanks for calling. Customer: Hey, my neighbor just bought a Tesla and won't shut up about it, ha. Anyway I'm calling about the Silverado you have listed, the red one.",
            "created_at": now - timedelta(days=10), "timestamp": now - timedelta(days=10)}
    await db.call_logs.insert_one(call)
    return {"contacts": [dana, mike, nb, note, bud], "memo": memo, "conv": conv, "msg": msg, "call": call}


async def _wipe(db, s):
    await db.contacts.delete_many({"_id": {"$in": [c["_id"] for c in s["contacts"]]}})
    await db.voice_notes.delete_one({"_id": s["memo"]["_id"]})
    await db.conversations.delete_one({"_id": s["conv"]["_id"]})
    await db.messages.delete_one({"_id": s["msg"]["_id"]})
    await db.call_logs.delete_one({"_id": s["call"]["_id"]})


async def test_terms_and_scan():
    db = get_db()
    forest = await db.users.find_one({"email": "forest@imosapp.com"})
    s = await _seed(db, str(forest["_id"]))
    try:
        t = await ms.terms_for("a month ago someone asked about a 20k Tesla Model 3, who was it?")
        low = " ".join(t["terms"])
        assert "tesla" in low and ("model 3" in low or "model3" in low), t
        assert any(x in low for x in ("20k", "20,000", "twenty")), t
        hits = await ms.scan(db, forest, ["tesla", "model 3", "20k", "twenty grand", "twenty"])
        mine = {h["contact_id"]: h for h in hits if h["contact_id"] in {str(c["_id"]) for c in s["contacts"][:4]}}
        assert {mine[str(c["_id"])]["source"] for c in s["contacts"][:4]} == {"memo", "text", "call", "note"}, mine
        assert "Model 3" in mine[str(s["contacts"][0]["_id"])]["quote"] and mine[str(s["contacts"][1]["_id"])]["who"] == "them"
        recent = await ms.scan(db, forest, ["tesla"], days=20)
        assert str(s["contacts"][2]["_id"]) in {h["contact_id"] for h in recent} and str(s["contacts"][0]["_id"]) not in {h["contact_id"] for h in recent}, "lookback window"
    finally:
        await _wipe(db, s)


async def test_search_verifies_and_speaks():
    db = get_db()
    forest = await db.users.find_one({"email": "forest@imosapp.com"})
    s = await _seed(db, str(forest["_id"]))
    dana, mike, nb, note, bud = (str(c["_id"]) for c in s["contacts"])
    try:
        res = await ms.search(db, forest, "who asked about a 20k Tesla Model 3 last month?")
        by = {r["contact_id"]: r for r in res["results"]}
        print("\nRESULTS:", [(r["name"], r["strength"], r["best"]["source"], r["best"]["why"]) for r in res["results"]])
        assert dana in by and by[dana]["strength"] == "strong" and by[dana]["best"]["source"] == "memo" and "Model 3" in by[dana]["best"]["quote"], by.get(dana)
        assert note in by, "the note about a used Model 3 under 20k counts"
        assert by.get(nb, {}).get("strength") != "strong", "the neighbor's Tesla is a passing mention"
        assert res["results"][0]["strength"] == "strong"
        said = ms.spoken(res)
        assert "Dana QA-Cole" in said and "voice memo" in said and "Want me to pull up" in said
        assert "Nobody on record" in ms.spoken({"results": [], "topic": "a boat", "scanned": 0})
        # live Jessi tool: focus + choices move to the top match, screen opens the results
        live = {"_id": ObjectId(), "live_id": "qa-mentions", "user_id": str(forest["_id"]), "mode": "assistant"}
        await db[lv.COLL].insert_one({**live, "status": "open", "transcript": [], "delegations": [], "pending": None, "started_at": datetime.now(timezone.utc)})
        try:
            said, opened = await lv._find_mentions(db, forest, {"query": "a 20k Tesla Model 3", "days": 0}, live)
            assert opened["kind"] == "mentions" and opened["query"] == "a 20k Tesla Model 3" and opened["id"] == res["results"][0]["contact_id"]
            assert live["last_choices"][0] == res["results"][0]["contact_id"] and live["contact_id"] == res["results"][0]["contact_id"]
            row = await db[lv.COLL].find_one({"_id": live["_id"]})
            assert row["contact_id"] == res["results"][0]["contact_id"]
        finally:
            await db[lv.COLL].delete_one({"_id": live["_id"]})
    finally:
        await _wipe(db, s)


async def test_typed_jessi_lookup():
    from services.jessie_service import _build_data_lookups
    db = get_db()
    forest = await db.users.find_one({"email": "forest@imosapp.com"})
    s = await _seed(db, str(forest["_id"]))
    try:
        block = await _build_data_lookups(str(forest["_id"]), "Who asked about a 20k Tesla Model 3 a month ago? I can't remember who it was")
        assert "WHO MENTIONED" in block and "Dana QA-Cole" in block and "voice memo" in block and f"/contact/{s['contacts'][0]['_id']}" in block, block
        assert "WHO MENTIONED" not in await _build_data_lookups(str(forest["_id"]), "how many texts did I send this week")
    finally:
        await _wipe(db, s)


async def test_sold_records():
    """'Who did I sell a Tahoe to?' finds the purchase record (title + date), not just texts and memos."""
    db = get_db()
    forest = await db.users.find_one({"email": "forest@imosapp.com"})
    s = await _seed(db, str(forest["_id"]))
    bud = str(s["contacts"][4]["_id"])
    try:
        hits = await ms.scan(db, forest, ["tahoe"])
        mine = [h for h in hits if h["contact_id"] == bud]
        assert mine and mine[0]["source"] == "sale" and "Sold: 2024 Chevy Tahoe on Mar 12, 2026" in mine[0]["quote"] and "Traded a 2018 Silverado" in mine[0]["quote"], mine
        assert not [h for h in await ms.scan(db, forest, ["tahoe"], days=30) if h["contact_id"] == bud], "lookback window applies to sale dates"
        assert "sold" in ms.STOP and "bought" in ms.STOP, "fallback terms must not match every 'Sold:' record"
        res = await ms.search(db, forest, "who did I sell a Tahoe to?")
        by = {r["contact_id"]: r for r in res["results"]}
        print("\nSOLD RESULTS:", [(r["name"], r["strength"], r["best"]["source"], r["best"]["why"]) for r in res["results"]])
        assert bud in by and by[bud]["strength"] == "strong" and by[bud]["best"]["source"] == "sale", by.get(bud)
        assert "Bud QA-Sold" in ms.spoken(res) and "sold records" in ms.spoken(res)
        from services.jessie_service import _build_data_lookups
        block = await _build_data_lookups(str(forest["_id"]), "Who did I sell a Tahoe to earlier this year?")
        assert "WHO MENTIONED" in block and "Bud QA-Sold" in block and "sold record" in block, block
    finally:
        await _wipe(db, s)


async def test_brain_and_api():
    db = get_db()
    forest = await db.users.find_one({"email": "forest@imosapp.com"})
    s = await _seed(db, str(forest["_id"]))
    live = {"_id": ObjectId(), "live_id": "qa-mentions-brain", "user_id": str(forest["_id"]), "mode": "assistant", "pending": None}
    await db[lv.COLL].insert_one({**live, "status": "open", "transcript": [], "delegations": [], "started_at": datetime.now(timezone.utc)})
    try:
        r = await lv.delegate(db, live, forest, [{"role": "rep", "text": "Hey, about a month ago somebody asked me about a twenty thousand dollar Tesla Model 3 and I can't remember who it was."}], "d1")
        assert r["tool"] == "find_mentions" and r["open"]["kind"] == "mentions" and "Dana QA-Cole" in r["content"], r
        tok = subprocess.run(["curl", "-s", "-X", "POST", f"{API}/api/auth/login", "-H", "Content-Type: application/json", "-d", json.dumps({"email": "forest@imosapp.com", "password": "Admin123!"})], capture_output=True, text=True).stdout
        token = json.loads(tok).get("token") or json.loads(tok).get("access_token")
        out = subprocess.run(["curl", "-s", "-m", "90", "-X", "POST", f"{API}/api/memory/search", "-H", "Content-Type: application/json", "-H", f"Authorization: Bearer {token}", "-d", json.dumps({"query": "who wanted a Model 3 around 20k"})], capture_output=True, text=True).stdout
        data = json.loads(out)
        names = [x["name"] for x in data["results"]]
        assert "Dana QA-Cole" in names and data["terms"] and data["results"][0]["best"]["quote"], data
        assert subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-X", "POST", f"{API}/api/memory/search", "-H", "Content-Type: application/json", "-d", json.dumps({"query": "x"})], capture_output=True, text=True).stdout == "401"
    finally:
        await db[lv.COLL].delete_one({"_id": live["_id"]})
        await _wipe(db, s)
