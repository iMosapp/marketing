"""Reports tell a text shop from a call from an email shop: report JSON by_channel + per-row channel, PDF tags and channel line,
weekly digest rows carry the channel word, the rep scorecard says which channel, and lead-shop conversations stay out of the
store report and the Shops list.
Run: cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_report_channels.py -q"""
import asyncio
import io
import os
import sys

import pytest
import requests
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seed_channel_mix import main as seed  # noqa: E402
from services import mystery_shops as ms  # noqa: E402
from services import shop_report_mail as mail  # noqa: E402

BASE_URL = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/")
API = BASE_URL + "/api"
CID = "6aa6d7dfb4c41decb2734ec4"  # QA Jeep 979a


def _db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _run(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture(scope="module")
def seeded():
    _run(seed(False))
    yield
    _run(seed(True))


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages)


def test_report_json_and_pdf_distinguish_channels(seeded):
    async def go():
        db = _db()
        client = await db.shop_clients.find_one({"_id": ObjectId(CID)})
        rep = await ms.build_report(db, client, None)
        return client, rep
    client, rep = _run(go())
    bc = rep["summary"]["by_channel"]
    assert {"call", "text", "email"} <= set(bc) and bc["text"]["completed"] >= 1 and bc["email"]["completed"] >= 1
    assert bc["text"]["avg_first_reply_s"] == 45 and bc["email"]["avg_first_reply_s"] == 2880
    chans = {c["channel"] for c in rep["calls"] if c["status"] == "completed"}
    assert chans == {"call", "text", "email"}
    assert all(c.get("text") for c in rep["calls"] if c["channel"] in ("text", "email")), "thread rows carry reply stats"
    assert all(not (c.get("rep_name") == "the store") for c in rep["calls"]), "lead-shop children never appear on the store report"
    sam = next(p for p in rep["people"] if p["name"] == "Sam Seller" and p["department"] == "sales")
    assert sam["channels"]["text"] == 1 and sam["channels"]["email"] == 1
    text = _pdf_text(ms.report_pdf(rep))
    for needle in ("BY CHANNEL", "Text shops: 1", "Email shops: 1", "TEXT SHOP", "EMAIL SHOP", "CALL", "Reply speed: first under a minute", "first reply 48 min"):
        assert needle in text, needle
    line = mail.summary_line(rep)
    assert "Text shops 1" in line and "Email shops 1" in line and "Calls" in line
    # public endpoints agree
    r = requests.get(f"{API}/public/shop-report/{client['report_token']}", timeout=60).json()
    assert r["summary"]["by_channel"]["text"]["completed"] >= 1
    pdf = requests.get(f"{API}/public/shop-report/{client['report_token']}.pdf", timeout=90)
    assert pdf.status_code == 200 and "TEXT SHOP" in _pdf_text(pdf.content)


def test_scorecard_digest_and_shops_list_name_the_channel(seeded):
    async def go():
        db = _db()
        client = await db.shop_clients.find_one({"_id": ObjectId(CID)})
        s_text = await db.roleplay_sessions.find_one({"client_id": CID, "qa_channel_seed": True, "mode": "text"})
        s_mail = await db.roleplay_sessions.find_one({"client_id": CID, "qa_channel_seed": True, "mode": "email"})
        start, end = ms.month_bounds(None, ms._tz(client))
        rows = await mail.week_shops(db, client, start, end)
        return client, s_text, s_mail, rows
    client, s_text, s_mail, rows = _run(go())
    sc = requests.get(f"{API}/public/shop-score/{s_text['score_token']}", timeout=30).json()
    assert sc["channel"] == "text" and sc["text"]["first_reply_s"] == 45 and len(sc["transcript_turns"]) == 6
    sc2 = requests.get(f"{API}/public/shop-score/{s_mail['score_token']}", timeout=30).json()
    assert sc2["channel"] == "email" and sc2["subject"]
    labels = {r["channel_label"] for r in rows}
    assert {"Text Shop", "Email Shop", "Call"} <= labels, labels
    html = mail.digest_html(client, rows, "line", "this week", "https://x", "")
    assert "Text Shop" in html and "Email Shop" in html and "calls, texts, emails and coaching" in html
    # admin Shops list: lead-shop children excluded, channel present
    r = requests.post(f"{API}/auth/login", json={"email": "forest@imosapp.com", "password": "Admin123!"}, timeout=30).json()
    tok = r.get("token") or r.get("access_token")
    lst = requests.get(f"{API}/shop-clients/{CID}/calls", headers={"Authorization": f"Bearer {tok}"}, timeout=30).json()
    calls = lst.get("calls") if isinstance(lst, dict) else lst
    assert all(c.get("target_name") != "the store" for c in calls)
    assert {c["channel"] for c in calls} >= {"call", "text", "email"}
