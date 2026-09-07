"""Weekly account-health alert: diff logic + email render against a seeded baseline (no email sent).

run: cd /app/backend && python tests/test_account_health_alert.py
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from motor.motor_asyncio import AsyncIOMotorClient
import routers.database as database
from routers.account_health import _alert_diff, _alert_baseline, _build_alert_html, _health_rows

SEED_KEY = "seed-test-baseline"
passed = failed = 0


def check(name, cond):
    global passed, failed
    passed += cond
    failed += (not cond)
    print(("PASS " if cond else "FAIL ") + name)


def row(uid, score, grade):
    return {"user_id": uid, "name": uid, "email": f"{uid}@x.test", "organization": "Org", "store": "",
            "health": {"score": score, "grade": grade, "color": "#000"}, "days_since_login": 3, "messages_30d": 1, "contacts": 5}


def test_pure_diff():
    rows = [row("a", 20, "Critical"), row("b", 30, "Critical"), row("c", 50, "At Risk"), row("d", 80, "Healthy"), row("e", 45, "At Risk"), row("f", 10, "Critical")]
    baseline = {"grades": {"a": {"score": 60, "grade": "At Risk"}, "b": {"score": 25, "grade": "Critical"}, "c": {"score": 75, "grade": "Healthy"},
                           "d": {"score": 30, "grade": "Critical"}, "e": {"score": 42, "grade": "At Risk"}}}
    d = _alert_diff(rows, baseline)
    check("a slipped to Critical (was At Risk)", [r["user_id"] for r in d["slipped_critical"]] == ["a"])
    check("b + f still Critical (f has no baseline)", sorted(r["user_id"] for r in d["still_critical"]) == ["b", "f"])
    check("c slipped to At Risk (was Healthy)", [r["user_id"] for r in d["slipped_risk"]] == ["c"])
    check("e At Risk -> At Risk not listed", all(r["user_id"] != "e" for k in d for r in d[k]))
    check("d recovered", [r["user_id"] for r in d["recovered"]] == ["d"])
    check("prev score attached", d["slipped_critical"][0]["prev_score"] == 60)
    empty = _alert_diff(rows, None)
    check("no baseline -> everything Critical is still_critical", len(empty["still_critical"]) == 3 and not empty["slipped_critical"])
    html = _build_alert_html(d, {"taken_at": datetime.now(timezone.utc) - timedelta(days=7)}, datetime.now(timezone.utc))
    check("html lists slipped account with open link", "/admin/account-health/a" in html and "Slipped to Critical" in html)
    check("html has no em dash", "\u2014" not in html and "\u2013" not in html)
    check("all-clear banner hidden when changes exist", "No account changed grade" not in html)
    quiet = _build_alert_html(_alert_diff(rows, None), None, datetime.now(timezone.utc))
    check("all-clear banner shown when nothing changed", "No account changed grade" in quiet)


async def test_seeded_baseline():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    database.db = db
    now = datetime.now(timezone.utc)
    rows = await _health_rows(db, 30)
    critical = [r for r in rows if r["health"]["grade"] == "Critical"]
    check("preview db has at least one Critical account", len(critical) >= 1)
    if not critical:
        return
    victim = critical[0]["user_id"]
    grades = {r["user_id"]: {"score": r["health"]["score"], "grade": r["health"]["grade"]} for r in rows}
    grades[victim] = {"score": 72, "grade": "Healthy"}
    # seed an 8-day-old snapshot newer than anything real from last week so _alert_baseline picks it
    await db.account_health_snapshots.delete_many({"week_key": SEED_KEY})
    await db.account_health_snapshots.insert_one({"week_key": SEED_KEY, "taken_at": now - timedelta(days=6, hours=1), "grades": grades, "counts": {}})
    try:
        base = await _alert_baseline(db, now)
        check("baseline picks the 6+ day old snapshot", base and base.get("week_key") == SEED_KEY)
        d = _alert_diff(await _health_rows(db, 30), base)
        check("victim reported as slipped to Critical", [r["user_id"] for r in d["slipped_critical"]] == [victim])
        check("victim shows 72 -> current", d["slipped_critical"][0]["prev_score"] == 72)
        html = _build_alert_html(d, base, now)
        check("email names the victim", (critical[0].get("name") or critical[0]["email"]) in html)
    finally:
        await db.account_health_snapshots.delete_many({"week_key": SEED_KEY})
    client.close()


if __name__ == "__main__":
    test_pure_diff()
    asyncio.run(test_seeded_baseline())
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
