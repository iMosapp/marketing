"""Mystery shop report: a person shopped in two departments gets one row per department, the misses list is per department,
and the PDF carries department cards + department on every shop."""
import asyncio
import os
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from services import mystery_shops as ms


def _pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
        import io
        return "\n".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(data)).pages)
    except Exception:
        return ""


async def _run():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    now = datetime.now(timezone.utc)
    client_res = await db.shop_clients.insert_one({"name": "QA Report Store", "industry": "automotive", "active": True, "timezone": "America/Denver", "plan": {"sales": 4, "service": 2},
                                                   "created_at": now, "qa_report": True})
    cid = str(client_res.inserted_id)
    client = await db.shop_clients.find_one({"_id": client_res.inserted_id})
    target = await db.shop_targets.insert_one({"client_id": cid, "name": "Bud", "phone": "+15005550101", "department": "service", "active": True, "created_at": now, "qa_report": True})
    tid = str(target.inserted_id)

    def ev(dept_label, results):
        return {"call_sid": f"RP_qa_{ObjectId()}", "is_mystery_shop": True, "department": dept_label, "results": results, "coaching": [f"Coach {dept_label}"], "critical_misses": [], "created_at": now, "qa_report": True}

    e_sales = await db.call_evaluations.insert_one(ev("Sales Floor", [{"text": "Asked about a trade-in", "passed": False, "critical": False}, {"text": "Set a specific day and time", "passed": True, "critical": False}]))
    e_service = await db.call_evaluations.insert_one(ev("Service BDC", [{"text": "Mentioned transportation options", "passed": False, "critical": False}, {"text": "Set a specific day and time", "passed": True, "critical": False}]))
    base = {"kind": "mystery_shop", "client_id": cid, "target_id": tid, "rep_name": "Bud", "status": "completed", "scheduled_for": now - timedelta(hours=2), "ended_at": now - timedelta(hours=1),
            "script_title": "Shop", "persona": {"name": "Shopper"}, "turns": [{"role": "customer", "text": "Hi, is this the service department?"}, {"role": "rep", "text": "Yeah, what do you need?"}], "created_at": now, "qa_report": True}
    e_old = await db.call_evaluations.insert_one(ev("Sales Floor", [{"text": "Asked about a trade-in", "passed": True, "critical": False}]))
    last_month = (now.replace(day=1) - timedelta(days=1)).replace(day=15)
    await db.roleplay_sessions.insert_many([
        {**base, "department": "sales", "score_pct": 70, "adherence_pct": 70, "evaluation_id": str(e_sales.inserted_id)},
        {**base, "department": "service", "score_pct": 60, "adherence_pct": 60, "evaluation_id": str(e_service.inserted_id)},
        {**base, "department": "sales", "score_pct": 40, "adherence_pct": 40, "evaluation_id": str(e_old.inserted_id), "scheduled_for": last_month, "ended_at": last_month, "script_title": "Old shop"},
        {**base, "status": "unreachable", "score_pct": None, "department": "sales", "evaluation_id": None, "scheduled_for": now - timedelta(days=2), "ended_at": None},
    ])
    try:
        rep = await ms.build_report(db, client, now.strftime("%Y-%m"))
        rows = {(r["name"], r["department"]): r for r in rep["people"]}
        assert ("Bud", "sales") in rows and ("Bud", "service") in rows, rep["people"]
        assert rows[("Bud", "service")]["avg_score"] == 60 and rows[("Bud", "sales")]["avg_score"] == 70
        assert rows[("Bud", "service")]["department_label"] == "Service" and rows[("Bud", "service")]["key"] == f"{tid}:service"
        assert rep["summary"]["people_shopped"] == 1 and rep["summary"]["completed"] == 2
        bd = rep["by_department"]
        assert bd["sales"]["completed"] == 1 and bd["service"]["completed"] == 1 and bd["service"]["avg_score"] == 60
        assert [c["text"] for c in bd["service"]["criteria"]] == ["Mentioned transportation options", "Set a specific day and time"]
        assert all(c["department"] == "sales" for c in bd["sales"]["criteria"]) and len(bd["sales"]["criteria"]) == 2
        # coaching themes split by department
        assert bd["service"]["coaching_themes"] == [{"text": "Coach Service BDC", "count": 1}] and bd["sales"]["coaching_themes"] == [{"text": "Coach Sales Floor", "count": 1}]
        assert {t["text"] for t in rep["coaching_themes"]} == {"Coach Sales Floor", "Coach Service BDC"}
        # the shared criterion text is NOT merged across departments any more
        shared = [c for c in rep["criteria"] if c["text"] == "Set a specific day and time"]
        assert len(shared) == 2 and all(c["total"] == 1 for c in shared)
        pdf = ms.report_pdf(rep)
        assert pdf[:4] == b"%PDF" and len(pdf) > 2000
        text = _pdf_text(pdf)
        if text:
            assert "SERVICE" in text and "What Service misses most" in text and "What Sales misses most" in text, text[:1500]
            assert "Coaching themes for the next Service meeting" in text and "Coaching themes for the next Sales meeting" in text
        # person history: every shop across months, trend, departments, snippets
        hist = await ms.person_history(db, client, tid, months=3)
        assert hist["person"]["name"] == "Bud" and hist["summary"]["shops"] == 3 and hist["summary"]["unreachable"] == 1
        assert hist["summary"]["avg_score"] == round((70 + 60 + 40) / 3) and hist["summary"]["best"] == 70 and hist["summary"]["worst"] == 40
        assert set(hist["departments"]) == {"sales", "service"} and hist["departments"]["sales"]["shops"] == 2
        assert len(hist["trend"]) == 3 and hist["trend"][-1]["shops"] == 2 and hist["trend"][-1]["avg_score"] == 65 and hist["trend"][-2]["avg_score"] == 40
        assert hist["summary"]["trend_delta"] == 25
        assert hist["trend"][-1]["by_department"]["service"]["avg_score"] == 60
        assert len(hist["shops"]) == 4 and hist["shops"][0]["status"] in ("completed", "unreachable")
        done_rows = [s for s in hist["shops"] if s["status"] == "completed"]
        assert all(s["snippet"].startswith("CUSTOMER: Hi, is this the service department?") for s in done_rows), done_rows[0]["snippet"]
        assert {s["department_label"] for s in done_rows} == {"Sales", "Service"}
        assert await ms.person_history(db, client, str(ObjectId()), months=3) is None
        # compare to store: Bud is the only person here, so his numbers ARE the store line
        assert hist["store"]["avg_score"] == hist["summary"]["avg_score"] and hist["store"]["shops"] == 3 and hist["store"]["people"] == 1
        assert hist["vs_store"] == 0 and hist["vs_department"] == {"sales": 0, "service": 0}
        assert hist["trend"][-1]["store_avg_score"] == 65 and hist["trend"][-2]["store_avg_score"] == 40
        # add a stronger colleague and the line moves above Bud
        await db.roleplay_sessions.insert_one({**base, "target_id": str(ObjectId()), "rep_name": "Ace", "department": "sales", "score_pct": 100, "adherence_pct": 100, "evaluation_id": None})
        hist2 = await ms.person_history(db, client, tid, months=3)
        assert hist2["store"]["people"] == 2 and hist2["store"]["avg_score"] == round((70 + 60 + 40 + 100) / 4)
        assert hist2["vs_store"] == hist2["summary"]["avg_score"] - hist2["store"]["avg_score"] < 0
        assert hist2["store"]["by_department"]["sales"]["avg_score"] == 70 and hist2["vs_department"]["sales"] == 55 - 70
        print(f"OK: {len(rep['people'])} person rows, depts {list(bd)}, pdf {len(pdf)} bytes, text_checked={bool(text)}, history shops={hist['summary']['shops']} delta={hist['summary']['trend_delta']}")
    finally:
        await db.roleplay_sessions.delete_many({"qa_report": True})
        await db.call_evaluations.delete_many({"qa_report": True})
        await db.shop_targets.delete_many({"qa_report": True})
        await db.shop_clients.delete_many({"qa_report": True})


def test_report_per_department():
    asyncio.run(_run())
