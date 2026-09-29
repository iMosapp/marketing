"""Score trends + weekly leaderboard + editable call guides (real Mongo, throwaway client cleaned up after)."""
import os
import uuid
import pytest
from datetime import timedelta

from bson import ObjectId
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from routers.database import get_db  # noqa: E402
from services import call_guides as cg  # noqa: E402
from services import mystery_shops as ms  # noqa: E402

pytestmark = pytest.mark.asyncio
KEY = f"test_trend_{uuid.uuid4().hex[:8]}"


async def _client(db):
    res = await db.shop_clients.insert_one({"name": "Trend Test", "seed_key": KEY, "industry": "equipment", "timezone": "America/Denver", "locale": "en-US", "plan": {"per_month": {}}, "hours": dict(ms.ALWAYS_OPEN), "active": True, "report_token": uuid.uuid4().hex})
    return await db.shop_clients.find_one({"_id": res.inserted_id})


async def _person(db, cid, name, dept="eq_sales"):
    res = await db.shop_targets.insert_one({"client_id": cid, "seed_key": KEY, "name": name, "phone": "+1500555" + uuid.uuid4().hex[:4], "department": dept, "title": "", "active": True})
    return str(res.inserted_id)


async def _shop(db, cid, tid, name, dept, days_ago, score):
    when = ms._now() - timedelta(days=days_ago)
    await db.roleplay_sessions.insert_one({"kind": "mystery_shop", "seed_key": KEY, "client_id": cid, "target_id": tid, "rep_name": name, "department": dept, "industry": "equipment", "status": "completed",
                                           "mode": "phone", "scheduled_for": when, "started_at": when, "ended_at": when + timedelta(minutes=6), "score_pct": score, "adherence_pct": score - 3, "score_token": uuid.uuid4().hex, "turns": []})


async def _cleanup(db):
    for coll in (db.shop_clients, db.shop_targets, db.roleplay_sessions, db.call_guides):
        await coll.delete_many({"seed_key": KEY})


async def test_week_bounds_are_local_mondays():
    c = {"timezone": "America/Denver", "locale": "en-US"}
    start, end, label = ms.week_bounds(c, 0)
    p_start, p_end, _ = ms.week_bounds(c, -1)
    assert (end - start) == timedelta(days=7)
    assert p_end == start
    assert start.astimezone(ms._tz(c)).weekday() == 0
    assert " to " in label


async def test_weekly_leaderboard_ranks_per_department_with_delta():
    db = get_db()
    c = await _client(db)
    cid = str(c["_id"])
    try:
        a, b = await _person(db, cid, "Alpha Rep"), await _person(db, cid, "Beta Rep")
        p = await _person(db, cid, "Parts Person", "eq_parts")
        await _shop(db, cid, a, "Alpha Rep", "eq_sales", 0, 90)
        await _shop(db, cid, a, "Alpha Rep", "eq_sales", 7, 70)  # last week
        await _shop(db, cid, b, "Beta Rep", "eq_sales", 0, 80)
        await _shop(db, cid, p, "Parts Person", "eq_parts", 0, 60)
        lb = await ms.weekly_leaderboard(db, c, 0)
        assert lb["is_current"] and lb["completed"] == 3 and lb["people"] == 3
        depts = {x["department"]: x for x in lb["boards"]}
        assert set(depts) == {"eq_sales", "eq_parts"}
        sales = depts["eq_sales"]["rows"]
        assert [r["name"] for r in sales] == ["Alpha Rep", "Beta Rep"]
        assert sales[0]["rank"] == 1 and sales[0]["avg_score"] == 90 and sales[0]["delta"] == 20 and sales[0]["prev_avg"] == 70
        assert sales[1]["delta"] is None
        assert lb["movers"] and lb["movers"][0]["name"] == "Alpha Rep" and lb["movers"][0]["delta"] == 20
        assert lb["prev_avg_score"] == 70
        last = await ms.weekly_leaderboard(db, c, -1)
        assert not last["is_current"] and last["completed"] == 1 and last["boards"][0]["rows"][0]["avg_score"] == 70
        empty = await ms.weekly_leaderboard(db, c, -10)
        assert empty["completed"] == 0 and empty["boards"] == [] and empty["movers"] == []
    finally:
        await _cleanup(db)


async def test_score_history_oldest_first_and_flags_current():
    db = get_db()
    c = await _client(db)
    cid = str(c["_id"])
    try:
        t = await _person(db, cid, "Trend Rep")
        for days, score in ((20, 60), (10, 75), (0, 88)):
            await _shop(db, cid, t, "Trend Rep", "eq_sales", days, score)
        current = await db.roleplay_sessions.find_one({"seed_key": KEY, "score_pct": 88})
        hist = await ms.score_history(db, current)
        assert [h["score_pct"] for h in hist] == [60, 75, 88]
        assert [h["current"] for h in hist] == [False, False, True]
        assert hist[-1]["department_label"] and hist[-1]["at"]
        assert await ms.score_history(db, {"target_id": None}) == []
    finally:
        await _cleanup(db)


async def test_guide_edit_validate_save_reset():
    db = get_db()
    seed = cg._shape(cg.KUBOTA_PARTS)
    with pytest.raises(ValueError):
        cg.validate({"title": "", "sections": seed["sections"], "scorecard": seed["scorecard"]})
    with pytest.raises(ValueError):
        cg.validate({"title": "x", "sections": [], "scorecard": seed["scorecard"]})
    with pytest.raises(ValueError):
        cg.validate({"title": "x", "sections": seed["sections"], "scorecard": []})
    shaped = cg.validate({**seed, "scorecard": [{"label": "A", "points": "40"}, {"label": "B", "points": 60}, {"label": "", "points": 5}, {"label": "C", "points": 0}]})
    assert shaped["total"] == 100 and [r["label"] for r in shaped["scorecard"]] == ["A", "B"]
    # save + reset on a throwaway key (a valid industry, a department key that no seed uses, so nothing real is touched)
    industry, dept = "equipment", f"eq_test_{KEY}"
    try:
        g = await cg.save_custom(db, industry, dept, {**seed, "title": "Edited"}, by="tester")
        assert g["source"] == "custom" and g["title"] == "Edited" and g["updated_by"] == "tester"
        assert (await cg.get_guide(db, industry, dept, build=False))["title"] == "Edited"
        assert await cg.ensure_call_guides(db) == 0  # custom guides are never overwritten by the seed pass
        await db.call_guides.delete_one({"industry": industry, "department": dept})
        # a seeded pair comes back verbatim after reset, even after an edit
        await cg.save_custom(db, "equipment", "eq_parts", {**seed, "title": "Edited parts"}, by="tester")
        back = await cg.reset_guide(db, "equipment", "eq_parts")
        assert back["source"] == "seed" and back["title"] == cg.KUBOTA_PARTS["title"] and back["total"] == 100
    finally:
        await db.call_guides.delete_one({"industry": industry, "department": dept})
