"""Smoke: live rep takeover + booking + crawl. Run: cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && python tests/smoke_widget_live.py"""
import asyncio
import os
import sys

import httpx

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
WID = "6ab72996c248f5420bf0a14a"


async def main():
    async with httpx.AsyncClient(timeout=90) as c:
        tok = (await c.post(f"{API}/auth/login", json={"email": "qa-manager@invalid.imonsocial.test", "password": "Manager123!"})).json()
        H = {"Authorization": f"Bearer {tok.get('token') or tok.get('access_token')}"}
        d = (await c.get(f"{API}/widgets/{WID}", headers=H)).json()
        key = d["widget"]["key"]
        print("key", key, "booking_on", d["widget"]["doors"]["chat"].get("booking_on"))
        page = {"page": "https://qa-dealer.test/inventory", "title": "QA", "visitor": "vsmoke"}
        s = (await c.post(f"{API}/w/{key}/chat/start", json=page)).json()
        sid = s["sid"]
        print("start", s["mode"], s["greeting"][:50])
        r = (await c.post(f"{API}/w/{key}/chat/{sid}/message", json={"text": "Can I come in for a test drive this week?"})).json()
        print("visitor msg -> offer_booking", r["offer_booking"], "| jessi:", (r["reply"] or "")[:100])
        live = (await c.get(f"{API}/widgets/chats/live", headers=H)).json()
        print("live chats", [(x["sid"][:6], x["mode"], x["turns"], x["visitor_here"]) for x in live["chats"]][:3])
        assert any(x["sid"] == sid for x in live["chats"]), "chat not in live list"
        j = (await c.post(f"{API}/widgets/chats/{sid}/join", headers=H)).json()
        print("join ->", j["mode"], j["agent"], j["messages"][-1])
        m = (await c.post(f"{API}/widgets/chats/{sid}/message", headers=H, json={"text": "Hi, this is QA from the store, happy to help!"})).json()
        print("rep msg ->", m["messages"][-1]["role"], m["messages"][-1]["who"])
        v = (await c.get(f"{API}/w/{key}/chat/{sid}")).json()
        print("visitor sees mode", v["mode"], "agent", v["agent"], "last", v["messages"][-1])
        assert v["messages"][-1]["role"] == "rep"
        r2 = (await c.post(f"{API}/w/{key}/chat/{sid}/message", json={"text": "Great, do you have a red one?"})).json()
        print("visitor in human mode -> reply", r2["reply"], "mode", r2["mode"])
        assert r2["reply"] is None
        det = (await c.get(f"{API}/widgets/chats/{sid}", headers=H)).json()
        print("rep detail unread(after read)", det["rep_unread"], "visitor_here", det["visitor_here"], "n msgs", len(det["messages"]))
        lv = (await c.post(f"{API}/widgets/chats/{sid}/leave", headers=H)).json()
        print("leave ->", lv["mode"], lv["messages"][-1]["text"])
        sl = (await c.get(f"{API}/w/{key}/chat/{sid}/slots")).json()
        print("slots tz", sl["tz"], "days", [(x["date"], x["label"], len(x["slots"])) for x in sl["days"]][:3])
        day = sl["days"][0]
        b = await c.post(f"{API}/w/{key}/chat/{sid}/book", json={"kind": "test_drive", "date": day["date"], "time": day["slots"][0]["v"], "vehicle": "Red Bronco", "name": "QA Booker", "phone": "5005550041"})
        print("book", b.status_code, b.json().get("reply") or b.json().get("detail"), b.json().get("booking"))
        bad = await c.post(f"{API}/w/{key}/chat/{sid}/book", json={"kind": "service", "date": day["date"], "time": "03:00", "name": "x", "phone": "5005550041"})
        print("book again ->", bad.status_code, bad.json().get("detail"))
        det = (await c.get(f"{API}/widgets/chats/{sid}", headers=H)).json()
        print("rep detail booking", det["booking"], "contact", bool(det["contact_id"]), "conv", bool(det["conversation_id"]))
        if det["conversation_id"]:
            bc = (await c.get(f"{API}/widgets/chats/by-conversation/{det['conversation_id']}", headers=H)).json()
            print("by-conversation ->", bool(bc["chat"]))
        e = (await c.post(f"{API}/widgets/chats/{sid}/end", headers=H)).json()
        print("end ->", e["status"], e["messages"][-1]["text"])
        v = (await c.get(f"{API}/w/{key}/chat/{sid}")).json()
        print("visitor sees status", v["status"])
        if "--crawl" in sys.argv:
            cr = (await c.post(f"{API}/widgets/{WID}/crawl", headers=H, json={"url": "https://www.imonsocial.com"})).json()
            print("crawl started", cr["status"], cr["id"])
            for _ in range(40):
                await asyncio.sleep(3)
                job = (await c.get(f"{API}/widgets/{WID}/crawl", headers=H)).json()["job"]
                if job["status"] != "running":
                    break
            print("crawl ->", job["status"], job.get("error"), "pages", len(job.get("pages") or []))
            if job.get("draft"):
                print("facts", job["draft"]["facts"][:4]); print("specials", job["draft"]["specials"][:2]); print("notes", job["draft"]["notes"][:200])

asyncio.run(main())
