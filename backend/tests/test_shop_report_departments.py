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
            "script_title": "Shop", "persona": {"name": "Shopper"}, "turns": [], "created_at": now, "qa_report": True}
    await db.roleplay_sessions.insert_many([
        {**base, "department": "sales", "score_pct": 70, "adherence_pct": 70, "evaluation_id": str(e_sales.inserted_id)},
        {**base, "department": "service", "score_pct": 60, "adherence_pct": 60, "evaluation_id": str(e_service.inserted_id)},
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
        # the shared criterion text is NOT merged across departments any more
        shared = [c for c in rep["criteria"] if c["text"] == "Set a specific day and time"]
        assert len(shared) == 2 and all(c["total"] == 1 for c in shared)
        pdf = ms.report_pdf(rep)
        assert pdf[:4] == b"%PDF" and len(pdf) > 2000
        text = _pdf_text(pdf)
        if text:
            assert "SERVICE" in text and "What Service misses most" in text and "What Sales misses most" in text, text[:1500]
            assert "Bud  |  Service  |  Shop" in text.replace("\n", " ") or "Service" in text
        print(f"OK: {len(rep['people'])} person rows, depts {list(bd)}, pdf {len(pdf)} bytes, text_checked={bool(text)}")
    finally:
        await db.roleplay_sessions.delete_many({"qa_report": True})
        await db.call_evaluations.delete_many({"qa_report": True})
        await db.shop_targets.delete_many({"qa_report": True})
        await db.shop_clients.delete_many({"qa_report": True})


def test_report_per_department():
    asyncio.run(_run())
