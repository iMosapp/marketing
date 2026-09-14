"""Monthly report leaderboard: ranked per department (never across), medals implied by rank, badges for top score / most improved
vs last month / most shops; carried into the PDF and the monthly GM email."""
import asyncio
import io
import os
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from services import mystery_shops as ms
from services import shop_report_mail as srm


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader
    return "\n".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(data)).pages)


async def _run():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    now = datetime.now(timezone.utc)
    if now.day < 3:
        now = now.replace(day=5)  # keep "this month" shops clear of the month boundary
    client_res = await db.shop_clients.insert_one({"name": "QA Leaderboard Store", "industry": "automotive", "active": True, "timezone": "America/Denver", "plan": {"per_month": {"sales": 6, "parts": 2}},
                                                   "contact_name": "Pat GM", "contact_email": "gm@invalid.imonsocial.test", "report_token": "qa-leader-token", "created_at": now, "qa_leader": True})
    cid = str(client_res.inserted_id)
    client = await db.shop_clients.find_one({"_id": client_res.inserted_id})
    people = {}
    for name, dept in (("Ana", "sales"), ("Ben", "sales"), ("Cy", "sales"), ("Dee", "parts")):
        t = await db.shop_targets.insert_one({"client_id": cid, "name": name, "phone": f"+1500555{len(people):04d}", "department": dept, "active": True, "created_at": now, "qa_leader": True})
        people[name] = (str(t.inserted_id), dept)
    last_month = (now.replace(day=1) - timedelta(days=1)).replace(day=15)

    def call(name, score, when, title="Shop"):
        tid, dept = people[name]
        return {"kind": "mystery_shop", "client_id": cid, "target_id": tid, "rep_name": name, "department": dept, "status": "completed", "scheduled_for": when, "ended_at": when + timedelta(minutes=4),
                "score_pct": score, "adherence_pct": score, "script_title": title, "persona": {"name": "Shopper"}, "turns": [], "created_at": now, "qa_leader": True}

    d0 = now.replace(hour=15, minute=0) - timedelta(days=1)
    await db.roleplay_sessions.insert_many([
        call("Ana", 90, d0), call("Ana", 70, d0 - timedelta(hours=3)),          # avg 80, 2 shops
        call("Ben", 82, d0 - timedelta(hours=1)),                                # avg 82, 1 shop, best 82
        call("Cy", 60, d0 - timedelta(hours=2)), call("Cy", 64, d0 - timedelta(hours=5)), call("Cy", 62, d0 - timedelta(hours=8)),  # avg 62, 3 shops (most)
        call("Dee", 95, d0 - timedelta(hours=4)),                                # parts, alone in its department
        call("Ana", 60, last_month), call("Cy", 61, last_month), call("Ben", 85, last_month),  # Ana +20 (most improved), Cy +1, Ben -3
    ])
    try:
        rep = await ms.build_report(db, client, now.strftime("%Y-%m"))
        sales = rep["by_department"]["sales"]["leaderboard"]
        parts = rep["by_department"]["parts"]["leaderboard"]
        assert [r["name"] for r in sales] == ["Ben", "Ana", "Cy"], sales
        assert [r["rank"] for r in sales] == [1, 2, 3]
        assert sales[0]["avg_score"] == 82 and sales[1]["avg_score"] == 80 and sales[2]["avg_score"] == 62
        assert sales[1]["prev_avg"] == 60 and sales[1]["delta"] == 20 and sales[0]["delta"] == -3 and sales[2]["delta"] == 1
        badges = {r["name"]: [b["key"] for b in r["badges"]] for r in sales}
        assert badges["Ana"] == ["top_score", "most_improved"], badges   # 90 is the best single call, +20 the biggest climb
        assert badges["Cy"] == ["most_shops"] and badges["Ben"] == [], badges
        assert [r["name"] for r in parts] == ["Dee"] and parts[0]["rank"] == 1 and parts[0]["delta"] is None
        assert [b["key"] for b in parts[0]["badges"]] == ["top_score"]   # one shop: no "most shops" badge
        assert rep["prev_month_label"] == last_month.strftime("%b")
        assert "vs" in sales[1]["badges"][1]["detail"]
        # PDF
        text = _pdf_text(ms.report_pdf(rep))
        assert "Sales leaderboard" in text and "Parts leaderboard" in text, text[:2000]
        assert "Most improved" in text and "Most shops" in text and "Top score" in text
        # monthly email carries the per-department board
        html = srm.email_html(client, rep, srm.summary_line(rep), "https://x/report", "")
        assert "Leaderboard" in html and "<b>Sales</b>: 1. Ben <b>82%</b>" in html and "Most improved" in html and "<b>Parts</b>: 1. Dee" in html, html
        # an empty month has empty boards, never a crash
        empty = await ms.build_report(db, client, (now.replace(day=1) - timedelta(days=40)).strftime("%Y-%m"))
        assert all(not v.get("leaderboard") for v in empty["by_department"].values())
        print("ALL OK")
    finally:
        await db.roleplay_sessions.delete_many({"qa_leader": True})
        await db.shop_targets.delete_many({"qa_leader": True})
        await db.shop_clients.delete_many({"qa_leader": True})


def test_leaderboard():
    asyncio.run(_run())


if __name__ == "__main__":
    asyncio.run(_run())
