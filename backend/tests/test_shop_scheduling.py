"""Mystery shop scheduling rules: nothing outside 8 AM to 8 PM in the person's own time, a person's own hours beat the client's,
retries are spaced per policy, a month's quota splits evenly across a department's people (own numbers respected), phone shops
alternate inbound / outbound, difficulty shapes the shopper (objections + curveballs), outbound calls are graded with the follow-up card."""
import os
import pytest
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from routers.database import get_db  # noqa: E402
from services import mystery_shops as ms  # noqa: E402
from services import scripts as scr  # noqa: E402


DEN = ZoneInfo("America/Denver")
CLIENT = {"_id": ObjectId(), "name": "QA Sched Motors", "timezone": "America/Denver", "hours": {"start": "07:00", "end": "22:00", "days": [0, 1, 2, 3, 4, 5, 6]}, "industry": "automotive"}


def _local(dt: datetime, target=None) -> datetime:
    return dt.astimezone(ms._tz(CLIENT, target))


def test_night_guard_caps_generous_client_hours():
    """Client says 7 AM to 10 PM every day; the guard still keeps every slot between 8 AM and 8 PM (minus the 20 min tail)."""
    for _ in range(300):
        after = datetime(2026, 6, 1, tzinfo=timezone.utc) + timedelta(minutes=17 * _)
        when = _local(ms.next_slot(CLIENT, after, min_gap_minutes=0))
        assert 8 <= when.hour < 20, when
        assert (when.hour, when.minute) < (19, 41), when


def test_two_am_is_never_in_hours_and_moves_to_morning():
    two_am = datetime(2026, 6, 3, 2, 0, tzinfo=DEN)
    assert not ms.in_hours(CLIENT, two_am)
    assert not ms.in_hours({**CLIENT, "hours": ms.ALWAYS_OPEN}, two_am)
    when = _local(ms.next_slot(CLIENT, two_am.astimezone(timezone.utc), min_gap_minutes=0))
    assert when.date() == two_am.date() and when.hour >= 8
    # a slot that lands past the guard in the evening rolls to the next morning, never into the night
    late = datetime(2026, 6, 3, 21, 30, tzinfo=DEN)
    when = _local(ms.next_slot(CLIENT, late.astimezone(timezone.utc), min_gap_minutes=0))
    assert when.date() == late.date() + timedelta(days=1) and 8 <= when.hour < 20


def test_person_hours_and_timezone_win_over_the_client():
    """Val works Tue to Sat 10 to 4 in Chicago: her shops land inside that, in her time, even though the client is in Denver."""
    val = {"_id": ObjectId(), "hours": {"start": "10:00", "end": "16:00", "days": [1, 2, 3, 4, 5]}, "timezone": "America/Chicago"}
    for i in range(200):
        after = datetime(2026, 6, 1, tzinfo=timezone.utc) + timedelta(hours=5 * i)
        when = ms.next_slot(CLIENT, after, min_gap_minutes=0, target=val).astimezone(ZoneInfo("America/Chicago"))
        assert when.weekday() in (1, 2, 3, 4, 5), when
        assert 10 <= when.hour < 16, when
    monday_noon = datetime(2026, 6, 1, 12, 0, tzinfo=ZoneInfo("America/Chicago"))
    assert not ms.in_hours(CLIENT, monday_noon, val) and ms.in_hours(CLIENT, monday_noon)


def test_retry_spacing():
    now = datetime(2026, 6, 3, 10, 0, tzinfo=DEN).astimezone(timezone.utc)  # a Wednesday
    same = _local(ms.retry_slot(CLIENT, None, now, "same_day"))
    assert same.date() == datetime(2026, 6, 3).date() and same.hour >= 12
    nxt = _local(ms.retry_slot(CLIENT, None, now, "next_day"))
    assert nxt.date() == datetime(2026, 6, 4).date() and 8 <= nxt.hour < 20
    two = _local(ms.retry_slot(CLIENT, None, now, "two_days"))
    assert two.date() == datetime(2026, 6, 5).date()
    # same-day retry with the day over -> next open day, morning
    evening = datetime(2026, 6, 3, 19, 50, tzinfo=DEN).astimezone(timezone.utc)
    later = _local(ms.retry_slot(CLIENT, None, evening, "same_day"))
    assert later.date() == datetime(2026, 6, 4).date() and 8 <= later.hour < 20
    weekdays = {**CLIENT, "hours": {"start": "09:00", "end": "18:00", "days": [0, 1, 2, 3, 4]}}
    friday = datetime(2026, 6, 5, 10, 0, tzinfo=DEN).astimezone(timezone.utc)
    assert _local(ms.retry_slot(weekdays, None, friday, "next_day")).date() == datetime(2026, 6, 8).date()
    assert ms.retry_policy({"retry": {"tries": 9, "spacing": "weird", "by_dept": {"service": {"tries": 2, "spacing": "same_day"}}}}) == {"tries": 5, "spacing": "next_day"}
    assert ms.retry_policy({"retry": {"tries": 3, "by_dept": {"service": {"tries": 2, "spacing": "same_day"}}}}, "service") == {"tries": 2, "spacing": "same_day"}


def test_person_quotas_split_evenly_and_respect_own_numbers():
    people = [{"_id": ObjectId()} for _ in range(4)]
    assert sorted(ms._person_quotas(20, people, {}).values()) == [5, 5, 5, 5]
    assert sorted(ms._person_quotas(10, people, {}).values()) == [2, 2, 3, 3]
    # the least-shopped person gets the extra one
    counts = {str(people[0]["_id"]): 3, str(people[1]["_id"]): 2, str(people[2]["_id"]): 0, str(people[3]["_id"]): 1}
    q = ms._person_quotas(10, people, counts)
    assert q[str(people[2]["_id"])] == 3 and q[str(people[3]["_id"])] == 3 and q[str(people[0]["_id"])] == 2
    fixed = [{"_id": ObjectId(), "monthly_quota": 8}, {"_id": ObjectId()}, {"_id": ObjectId()}]
    q = ms._person_quotas(20, fixed, {})
    assert q[str(fixed[0]["_id"])] == 8 and sorted(q[str(f["_id"])] for f in fixed[1:]) == [6, 6]
    assert ms.difficulty_for({"difficulty": "hard"}, {"difficulty": "easy"}) == "easy"
    assert ms.difficulty_for({"difficulty": "hard"}, {}) == "hard"
    assert ms.difficulty_for({}, {}) == "medium"
    assert ms.difficulty_for({"difficulty": "mixed"}) in ("easy", "medium", "hard")


def test_difficulty_shapes_the_shopper_not_the_card():
    objections = ["A", "B", "C", "D"]
    temper, once, objs = scr.shopper_temper("easy", objections)
    assert objs == ["A"] and "easygoing" in temper and "ASK ONCE" in once
    _, _, objs = scr.shopper_temper("medium", objections)
    assert objs == ["A", "B"]
    _, _, objs = scr.shopper_temper("hard", objections)
    assert objs == ["A", "B", "C"]
    _, _, objs = scr.shopper_temper(None, objections)
    assert objs == ["A", "B"]
    prompt = scr._customer_system({"title": "t", "purpose": "p"}, {"name": "Casey", "summary": "s", "goals": "g", "objections": objections}, "QA Jeep", "Sam", [], live=True, direction="inbound", mystery=True, industry="automotive", department="sales", difficulty="easy")
    assert "ASK ONCE RULE" in prompt and "; B" not in prompt
    for direction in ("inbound", "outbound"):
        card = ms.template_card("sales", "en-US", direction)
        assert card and card["direction"] == direction
    assert ms.template_card("sales", "en-US", "inbound")["name"] != ms.template_card("sales", "en-US", "outbound")["name"]
    assert ms.template_card("service", "en-US", "outbound")["name"] == "Service Follow-Up Call"
    assert ms.template_card("service", "nl-NL", "outbound")["name"] == "Werkplaats-nabelgesprek"


@pytest.mark.asyncio
async def test_plan_month_splits_people_alternates_direction_and_stays_in_hours():
    """20 sales shops / 4 people -> 5 each, phone shops alternate inbound and outbound per person, every slot inside 8 AM to 8 PM local, none the same challenge twice."""
    db = get_db()
    client = {"_id": ObjectId(), "name": "QA Sched Motors", "industry": "automotive", "timezone": "America/Denver", "hours": {"start": "06:00", "end": "23:00", "days": [0, 1, 2, 3, 4, 5, 6]},
              "plan": {"per_month": {"sales": 20, "service": 0}}, "active": True, "direction_mix": "mixed", "created_at": ms._now()}
    await db.shop_clients.insert_one(client)
    cid = str(client["_id"])
    people = []
    for i in range(4):
        t = {"_id": ObjectId(), "client_id": cid, "name": f"QA Sched {i}", "phone": f"+1500555{9100 + i}", "department": "sales", "active": True, "challenge_history": [], "created_at": ms._now()}
        if i == 3:
            t["hours"] = {"start": "12:00", "end": "17:00", "days": [0, 1, 2, 3, 4]}
        await db.shop_targets.insert_one(t)
        people.append(t)
    try:
        nxt = (ms._now().astimezone(DEN).replace(day=1) + timedelta(days=40)).replace(day=1)
        month = nxt.strftime("%Y-%m")  # next month: the whole window is ahead of us
        made = await ms.plan_month(db, client, month)
        assert made["sales"] == 20
        rows = await db.roleplay_sessions.find({"kind": "mystery_shop", "client_id": cid}).to_list(100)
        assert len(rows) == 20
        by_person = {}
        for r in rows:
            by_person.setdefault(r["target_id"], []).append(r)
        assert sorted(len(v) for v in by_person.values()) == [5, 5, 5, 5]
        for tid, sess in by_person.items():
            target = next(p for p in people if str(p["_id"]) == tid)
            dirs = [s["direction"] for s in sess]
            assert abs(dirs.count("inbound") - dirs.count("outbound")) <= 1, dirs
            assert len({s["script_id"] for s in sess}) == 5, "same challenge twice for one person"
            for s in sess:
                local = s["scheduled_for"].replace(tzinfo=timezone.utc).astimezone(DEN)
                assert 8 <= local.hour < 20, local
                assert s["difficulty"] == "medium" and s["max_attempts"] == 3
                if target.get("hours"):
                    assert 12 <= local.hour < 17 and local.weekday() < 5, local
        # planning again adds nothing
        assert (await ms.plan_month(db, client, month))["sales"] == 0
        stats = await ms.people_month_stats(db, client, month)
        assert all(stats[str(p["_id"])]["planned"] == 5 and stats[str(p["_id"])]["quota"] == 5 and stats[str(p["_id"])]["scheduled"] == 5 for p in people)
        grading = await ms.grading_summary(db, client)
        assert grading["sales"]["inbound"]["name"] == "Sales Phone-Up" and grading["sales"]["outbound"]["name"] == "Internet Sales Call"
    finally:
        await db.roleplay_sessions.delete_many({"client_id": cid})
        await db.shop_targets.delete_many({"client_id": cid})
        await db.shop_clients.delete_one({"_id": client["_id"]})


@pytest.mark.asyncio
async def test_record_outcome_retries_by_policy_then_gives_up():
    db = get_db()
    client = {"_id": ObjectId(), "name": "QA Sched Retry", "industry": "automotive", "timezone": "America/Denver", "hours": ms.DEFAULT_HOURS, "retry": {"tries": 2, "spacing": "same_day"}, "active": True, "created_at": ms._now()}
    await db.shop_clients.insert_one(client)
    cid = str(client["_id"])
    target = {"_id": ObjectId(), "client_id": cid, "name": "QA Sched Retry", "phone": "+15005559200", "department": "sales", "active": True, "challenge_history": []}
    await db.shop_targets.insert_one(target)
    try:
        call = await ms.create_shop_call(db, client, target, ms._now())
        assert call and call["max_attempts"] == 2 and call["direction"] in ("inbound", "outbound")
        await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"attempts": 1}})
        call = await db.roleplay_sessions.find_one({"_id": call["_id"]})
        await ms.record_outcome(db, call, "no-answer")
        doc = await db.roleplay_sessions.find_one({"_id": call["_id"]})
        assert doc["status"] == "scheduled" and "later today" in doc["fail_reason"]
        local = doc["scheduled_for"].replace(tzinfo=timezone.utc).astimezone(DEN)
        assert 8 <= local.hour < 20
        await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"attempts": 2}})
        call = await db.roleplay_sessions.find_one({"_id": call["_id"]})
        await ms.record_outcome(db, call, "no-answer")
        doc = await db.roleplay_sessions.find_one({"_id": call["_id"]})
        assert doc["status"] == "unreachable" and "(2 tries)" in doc["fail_reason"]
    finally:
        await db.roleplay_sessions.delete_many({"client_id": cid})
        await db.shop_targets.delete_many({"client_id": cid})
        await db.shop_clients.delete_one({"_id": client["_id"]})
