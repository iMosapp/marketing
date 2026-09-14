"""Monthly GM report email: toggle + where it goes, 1st-of-month due logic, one-line summary, send-now (Resend test inbox)."""
import asyncio
import os
from datetime import datetime, timezone

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

from services import shop_report_mail as srm

API = os.environ.get("TEST_API_URL", "http://localhost:8001").rstrip("/")
DENVER = {"timezone": "America/Denver", "active": True, "auto_report": {"enabled": True, "to": "gm@example.com"}}


def test_previous_month_and_due_logic():
    assert srm.previous_month(DENVER, datetime(2026, 9, 1, 15, 0, tzinfo=timezone.utc)) == "2026-08"
    assert srm.previous_month(DENVER, datetime(2026, 1, 3, 15, 0, tzinfo=timezone.utc)) == "2025-12"
    # 1st at 9am Denver (15:00 UTC): due
    assert srm.due_now(DENVER, datetime(2026, 9, 1, 15, 0, tzinfo=timezone.utc))
    # 1st at 6am Denver: too early
    assert not srm.due_now(DENVER, datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc))
    # 3rd (catch-up) still due, 4th not
    assert srm.due_now(DENVER, datetime(2026, 9, 3, 15, 0, tzinfo=timezone.utc))
    assert not srm.due_now(DENVER, datetime(2026, 9, 4, 15, 0, tzinfo=timezone.utc))
    # already sent this cycle
    assert not srm.due_now({**DENVER, "auto_report": {**DENVER["auto_report"], "last_sent_month": "2026-08"}}, datetime(2026, 9, 1, 15, 0, tzinfo=timezone.utc))
    # toggle off / paused / quick-shops bucket never send
    assert not srm.due_now({**DENVER, "auto_report": {"enabled": False, "to": "x@y.com"}}, datetime(2026, 9, 1, 15, 0, tzinfo=timezone.utc))
    assert not srm.due_now({**DENVER, "active": False}, datetime(2026, 9, 1, 15, 0, tzinfo=timezone.utc))
    assert not srm.due_now({**DENVER, "demo": True}, datetime(2026, 9, 1, 15, 0, tzinfo=timezone.utc))


def test_summary_line():
    rep = {"month_label": "August 2026", "summary": {"completed": 5, "planned": 40, "avg_score": 50, "people_shopped": 3, "needs_training": 3},
           "by_department": {"sales": {"label": "Sales", "completed": 4, "avg_score": 48}, "service": {"label": "Service", "completed": 1, "avg_score": 60}}}
    assert srm.summary_line(rep) == "August 2026: 5 shops completed of 40 planned, average score 50%, 3 people shopped, 3 need training. Sales 48% · Service 60%."
    assert srm.summary_line({"month_label": "July 2026", "summary": {"completed": 0}}) == "No shops were completed in July 2026."


def test_weekly_digest_logic():
    # Monday Sep 14 2026 09:00 Denver (15:00 UTC): last week = Sep 7-13, key 2026-W37, due
    mon = datetime(2026, 9, 14, 15, 0, tzinfo=timezone.utc)
    start, end, key, label = srm.last_week(DENVER, mon)
    assert key == "2026-W37" and label == "Sep 7 to Sep 13" and (end - start).days == 7
    wk = {**DENVER, "weekly_digest": {"enabled": True, "to": "gm@example.com"}}
    assert srm.digest_due_now(wk, mon)
    assert not srm.digest_due_now(wk, datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc))          # 6am Monday: too early
    assert srm.digest_due_now(wk, datetime(2026, 9, 15, 15, 0, tzinfo=timezone.utc))              # Tuesday catch-up
    assert not srm.digest_due_now(wk, datetime(2026, 9, 16, 15, 0, tzinfo=timezone.utc))          # Wednesday: no
    assert not srm.digest_due_now({**wk, "weekly_digest": {**wk["weekly_digest"], "last_sent_week": "2026-W37"}}, mon)
    assert not srm.digest_due_now({**wk, "demo": True}, mon) and not srm.digest_due_now(DENVER, mon)
    assert srm.next_monday(DENVER, mon) == "2026-09-21" and srm.next_monday(DENVER, datetime(2026, 9, 16, 15, 0, tzinfo=timezone.utc)) == "2026-09-21"
    rows = [{"name": "Bud", "status": "completed", "score": 72, "critical": 1}, {"name": "Jessi", "status": "completed", "score": 88, "critical": 0}, {"name": "Kira", "status": "unreachable", "score": None, "critical": 0}]
    assert srm.digest_line(rows, "Sep 7 to Sep 13") == "2 shops Sep 7 to Sep 13, average 80%, top score Jessi 88%, 1 critical miss, 1 unreachable."
    assert srm.digest_line([rows[2]], "Sep 7 to Sep 13") == "No shops were completed Sep 7 to Sep 13. 1 could not be reached."


async def _login(c):
    r = await c.post(f"{API}/api/auth/login", json={"email": "forest@imosapp.com", "password": "Admin123!"})
    d = r.json()
    u = d.get("user") or {}
    return {"Authorization": f"Bearer {d.get('token') or d.get('access_token')}", "X-User-ID": str(u.get("_id") or u.get("id") or d.get("user_id"))}


async def _api_flow():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    now = datetime.now(timezone.utc)
    res = await db.shop_clients.insert_one({"name": "QA Auto Report Motors", "industry": "automotive", "active": True, "timezone": "America/Denver", "plan": {"sales": 2}, "contact_name": "Pat GM",
                                            "contact_email": "", "report_token": "qa" + "0" * 30, "created_at": now, "qa_auto_report": True})
    cid = str(res.inserted_id)
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            h = await _login(c)
            r = await c.get(f"{API}/api/shop-clients/{cid}", headers=h)
            assert r.status_code == 200 and r.json()["auto_report"] == {"enabled": False, "to": "", "last_sent_month": None, "last_sent_at": None, "last_sent_to": None, "last_error": None, "next_send": None}, r.json().get("auto_report")
            # cannot turn on without an email
            r = await c.put(f"{API}/api/shop-clients/{cid}/report/auto", json={"enabled": True}, headers=h)
            assert r.status_code == 400 and "email" in r.json()["detail"].lower()
            r = await c.put(f"{API}/api/shop-clients/{cid}/report/auto", json={"to": "not-an-email"}, headers=h)
            assert r.status_code == 400
            r = await c.put(f"{API}/api/shop-clients/{cid}/report/auto", json={"enabled": True, "to": "Delivered@resend.dev"}, headers=h)
            assert r.status_code == 200, r.text
            ar = r.json()["auto_report"]
            assert ar["enabled"] is True and ar["to"] == "delivered@resend.dev" and ar["next_send"] and ar["next_send"].endswith("-01")
            # toggle off keeps the address
            r = await c.put(f"{API}/api/shop-clients/{cid}/report/auto", json={"enabled": False}, headers=h)
            assert r.json()["auto_report"] == {**ar, "enabled": False, "next_send": None}
            # send now: real Resend call to their sink inbox, PDF attached, send recorded
            month = now.strftime("%Y-%m")
            r = await c.post(f"{API}/api/shop-clients/{cid}/report/send", json={"month": month}, headers=h)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["ok"] and body["to"] == "delivered@resend.dev" and body["month"] == month and body["summary"].startswith(body["month_label"]) or "No shops" in body["summary"]
            assert body["auto_report"]["last_sent_month"] == month and body["auto_report"]["last_sent_to"] == "delivered@resend.dev"
            log = await db.shop_report_sends.find_one({"client_id": cid})
            assert log and log["ok"] and log["reason"] == "manual" and log["month"] == month
            # the hourly job skips it now (already sent for this cycle only if month == previous month; either way it must not raise)
            n = await srm.send_due_reports(db)
            assert isinstance(n, int)
            # weekly digest: same toggle rules, own address defaults to the monthly one, send-now hits Resend's sink
            r = await c.get(f"{API}/api/shop-clients/{cid}", headers=h)
            wd = r.json()["weekly_digest"]
            assert wd["enabled"] is False and wd["to"] == "delivered@resend.dev" and wd["next_send"] is None
            r = await c.put(f"{API}/api/shop-clients/{cid}/report/weekly", json={"enabled": True}, headers=h)
            assert r.status_code == 200 and r.json()["weekly_digest"]["enabled"] and r.json()["weekly_digest"]["next_send"]
            r = await c.post(f"{API}/api/shop-clients/{cid}/report/weekly/send", json={}, headers=h)
            assert r.status_code == 200, r.text
            w = r.json()
            assert w["ok"] and w["to"] == "delivered@resend.dev" and w["week"].count("-W") == 1 and w["summary"] and w["weekly_digest"]["last_sent_week"] == w["week"]
            assert await db.shop_report_sends.count_documents({"client_id": cid, "kind": "weekly", "ok": True}) == 1
            assert isinstance(await srm.send_due_digests(db), int)
            print(f"OK: toggle validated, send-now delivered ({body['summary']}), due-run sent {n}; weekly digest sent ({w['summary']})")
    finally:
        await db.shop_clients.delete_many({"qa_auto_report": True})
        await db.shop_report_sends.delete_many({"client_id": cid})


def test_toggle_and_send_now_api():
    asyncio.run(_api_flow())
