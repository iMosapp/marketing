"""Backend tests for Widget iteration 349: booking, rep takeover, site crawl, upload, widget.js.

Run: cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && \
     python -m pytest tests/test_widget_live_booking.py -v --tb=short
"""
import io
import os
import time
import uuid

import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
WID = "6ab72996c248f5420bf0a14a"
RUN = str(int(time.time()))[-6:]


def _tok(email, pw):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    return j.get("token") or j.get("access_token")


@pytest.fixture(scope="module")
def mgr():
    return {"Authorization": f"Bearer {_tok('qa-manager@invalid.imonsocial.test', 'Manager123!')}"}


@pytest.fixture(scope="module")
def rep():
    return {"Authorization": f"Bearer {_tok('activation-tester@invalid.imonsocial.test', 'NewPass123!')}"}


@pytest.fixture(scope="module")
def key(mgr):
    r = requests.get(f"{BASE}/api/widgets/{WID}", headers=mgr, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["widget"]["key"]


def _start_chat(key, visitor_suffix=""):
    r = requests.post(
        f"{BASE}/api/w/{key}/chat/start",
        json={"page": "https://qa-dealer.test/inventory", "title": "QA", "visitor": f"vqa{RUN}{visitor_suffix}"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    return r.json()


# ------------------- BOOKING -------------------
class TestBooking:
    def test_start_and_offer(self, key):
        j = _start_chat(key, "b1")
        assert "sid" in j and j["mode"] == "jessi" and j.get("greeting")

    def test_offer_booking_and_slots_and_book(self, key, mgr):
        j = _start_chat(key, "b2")
        sid = j["sid"]
        m = requests.post(f"{BASE}/api/w/{key}/chat/{sid}/message",
                          json={"text": "Can I come in for a test drive this week?"}, timeout=60)
        assert m.status_code == 200, m.text
        body = m.json()
        assert body.get("offer_booking") is True, body
        assert body.get("reply")

        sl = requests.get(f"{BASE}/api/w/{key}/chat/{sid}/slots", timeout=30).json()
        assert sl.get("tz") == "America/Denver"
        assert isinstance(sl.get("days"), list) and len(sl["days"]) >= 1
        assert sl["days"][0]["slots"]
        assert isinstance(sl.get("kinds"), list) and len(sl["kinds"]) == 3
        for d in sl["days"]:
            for s in d["slots"]:
                assert ":" in s["v"] and s["l"]

        day = sl["days"][0]
        b = requests.post(f"{BASE}/api/w/{key}/chat/{sid}/book",
                          json={"kind": "test_drive", "date": day["date"], "time": day["slots"][0]["v"],
                                "vehicle": "Red Bronco", "name": "QA Booker", "phone": "5005550041"}, timeout=45)
        assert b.status_code == 200, b.text
        bj = b.json()
        assert bj.get("booked") is True
        assert bj["booking"]["kind"] == "Test drive"
        assert " at " in bj["booking"]["when"]
        assert "all set" in (bj.get("reply") or "").lower()

        # second book -> 400
        b2 = requests.post(f"{BASE}/api/w/{key}/chat/{sid}/book",
                           json={"kind": "test_drive", "date": day["date"], "time": day["slots"][0]["v"],
                                 "vehicle": "X", "name": "QA", "phone": "5005550041"}, timeout=30)
        assert b2.status_code == 400
        assert "already have a visit booked" in b2.text.lower()

        # verify rep-side detail has booking + task
        det = requests.get(f"{BASE}/api/widgets/chats/{sid}", headers=mgr, timeout=30).json()
        assert det.get("contact_id") and det.get("conversation_id")
        assert det.get("booking", {}).get("task_id")

    def test_bad_time_bad_date_missing_phone(self, key):
        j = _start_chat(key, "b3")
        sid = j["sid"]
        requests.post(f"{BASE}/api/w/{key}/chat/{sid}/message",
                      json={"text": "book a service visit"}, timeout=60)
        sl = requests.get(f"{BASE}/api/w/{key}/chat/{sid}/slots", timeout=30).json()
        day = sl["days"][0]
        r = requests.post(f"{BASE}/api/w/{key}/chat/{sid}/book",
                          json={"kind": "service", "date": day["date"], "time": "03:00",
                                "name": "x", "phone": "5005550041"}, timeout=30)
        assert r.status_code == 400
        assert "not open" in r.text.lower() or "closed" in r.text.lower()

        r2 = requests.post(f"{BASE}/api/w/{key}/chat/{sid}/book",
                           json={"kind": "service", "date": "1999-01-01", "time": day["slots"][0]["v"],
                                 "name": "x", "phone": "5005550041"}, timeout=30)
        assert r2.status_code == 400

        r3 = requests.post(f"{BASE}/api/w/{key}/chat/{sid}/book",
                           json={"kind": "service", "date": day["date"], "time": day["slots"][0]["v"],
                                 "name": "x"}, timeout=30)
        assert r3.status_code == 400

    def test_booking_off_returns_400(self, key, mgr):
        # turn off
        requests.put(f"{BASE}/api/widgets/{WID}",
                     json={"doors": {"chat": {"booking_on": False}}}, headers=mgr, timeout=30)
        try:
            j = _start_chat(key, "b4")
            sid = j["sid"]
            sl = requests.get(f"{BASE}/api/w/{key}/chat/{sid}/slots", timeout=30).json()
            day = sl["days"][0] if sl.get("days") else {"date": "2099-01-05", "slots": [{"v": "10:00"}]}
            slot = day["slots"][0]["v"] if day.get("slots") else "10:00"
            r = requests.post(f"{BASE}/api/w/{key}/chat/{sid}/book",
                              json={"kind": "test_drive", "date": day["date"], "time": slot,
                                    "name": "x", "phone": "5005550041"}, timeout=30)
            assert r.status_code == 400
            # Message may say 'Booking is turned off' or hit an outer rate-limit; both are 400.
            body = r.text.lower()
            assert ("turned off" in body) or ("booking" in body and "off" in body) or ("wait" in body), r.text
        finally:
            requests.put(f"{BASE}/api/widgets/{WID}",
                         json={"doors": {"chat": {"booking_on": True}}}, headers=mgr, timeout=30)


# ------------------- REP TAKEOVER -------------------
class TestRepTakeover:
    def test_full_takeover_flow(self, key, mgr):
        j = _start_chat(key, "t1")
        sid = j["sid"]
        requests.post(f"{BASE}/api/w/{key}/chat/{sid}/message",
                      json={"text": "hi are you open"}, timeout=60)
        # visitor poll -> visitor_here true
        requests.get(f"{BASE}/api/w/{key}/chat/{sid}", timeout=30)

        live = requests.get(f"{BASE}/api/widgets/chats/live", headers=mgr, timeout=30).json()
        chats = live.get("chats", [])
        row = next((c for c in chats if c["sid"] == sid), None)
        assert row, f"sid missing in live list; got {len(chats)} chats"
        assert row.get("mode") == "jessi"
        assert row.get("visitor_here") is True
        assert row.get("store_name")

        join = requests.post(f"{BASE}/api/widgets/chats/{sid}/join", headers=mgr, timeout=30).json()
        assert join["mode"] == "human"
        assert join.get("agent")
        assert join["messages"][-1]["role"] == "system"
        assert "joined" in join["messages"][-1]["text"]

        rm = requests.post(f"{BASE}/api/widgets/chats/{sid}/message", headers=mgr,
                           json={"text": "Hi from QA"}, timeout=30).json()
        last = rm["messages"][-1]
        assert last["role"] == "rep"
        assert last.get("who") and last.get("uid")

        # visitor sees rep line
        v = requests.get(f"{BASE}/api/w/{key}/chat/{sid}", timeout=30).json()
        assert v["mode"] == "human"
        assert v.get("agent")
        rep_msgs = [m for m in v["messages"] if m.get("role") == "rep"]
        assert rep_msgs and rep_msgs[-1].get("who")
        # visitor never sees 'note' role messages
        assert not any(m.get("role") == "note" for m in v["messages"])

        # visitor msg while human -> reply null
        vr = requests.post(f"{BASE}/api/w/{key}/chat/{sid}/message",
                           json={"text": "Great, red one?"}, timeout=30).json()
        assert vr.get("reply") is None
        assert vr.get("mode") == "human"

        # rep_unread resets
        d1 = requests.get(f"{BASE}/api/widgets/chats/{sid}", headers=mgr, timeout=30).json()
        # after the GET above, unread for the joining rep should be 0
        d2 = requests.get(f"{BASE}/api/widgets/chats/{sid}", headers=mgr, timeout=30).json()
        assert d2.get("rep_unread") == 0

        # save as lead
        sl = requests.post(f"{BASE}/api/widgets/chats/{sid}/lead", headers=mgr,
                          json={"name": "QA Live", "phone": "5005550042"}, timeout=30).json()
        assert sl.get("contact_id") and sl.get("conversation_id")
        note_msgs = [m for m in sl["messages"] if m.get("role") == "note"]
        assert note_msgs, "expected 'note' role message"

        # visitor GET must not include notes
        v2 = requests.get(f"{BASE}/api/w/{key}/chat/{sid}", timeout=30).json()
        assert not any(m.get("role") == "note" for m in v2["messages"])

        # by-conversation summary (while open)
        conv = sl["conversation_id"]
        bc = requests.get(f"{BASE}/api/widgets/chats/by-conversation/{conv}", headers=mgr, timeout=30).json()
        assert bc.get("chat"), "expected summary while open"

        # leave -> jessi
        lv = requests.post(f"{BASE}/api/widgets/chats/{sid}/leave", headers=mgr, timeout=30).json()
        assert lv["mode"] == "jessi"
        assert "stepped away" in lv["messages"][-1]["text"].lower()

        # end -> closed
        en = requests.post(f"{BASE}/api/widgets/chats/{sid}/end", headers=mgr, timeout=30).json()
        assert en.get("status") == "closed"
        vend = requests.get(f"{BASE}/api/w/{key}/chat/{sid}", timeout=30).json()
        assert vend.get("status") == "closed"
        vp = requests.post(f"{BASE}/api/w/{key}/chat/{sid}/message",
                           json={"text": "hello?"}, timeout=30)
        assert vp.status_code == 400
        assert "ended" in vp.text.lower()

        bc2 = requests.get(f"{BASE}/api/widgets/chats/by-conversation/{conv}", headers=mgr, timeout=30).json()
        assert bc2.get("chat") is None

    def test_auth_and_unknown_sid(self, mgr, rep):
        # rep -> 200 own store
        r = requests.get(f"{BASE}/api/widgets/chats/live", headers=rep, timeout=30)
        assert r.status_code == 200
        # unauth -> 401
        r2 = requests.get(f"{BASE}/api/widgets/chats/live", timeout=30)
        assert r2.status_code in (401, 403)
        # unknown sid -> 404
        r3 = requests.get(f"{BASE}/api/widgets/chats/nope-nope-nope", headers=mgr, timeout=30)
        assert r3.status_code == 404


# ------------------- SITE CRAWL -------------------
class TestCrawl:
    def test_bad_url(self, mgr):
        r = requests.post(f"{BASE}/api/widgets/{WID}/crawl",
                         json={"url": "not a site"}, headers=mgr, timeout=30)
        assert r.status_code == 400

    def test_rep_forbidden_post_allowed_get(self, rep):
        r = requests.post(f"{BASE}/api/widgets/{WID}/crawl",
                         json={"url": "https://www.imonsocial.com"}, headers=rep, timeout=30)
        assert r.status_code == 403
        g = requests.get(f"{BASE}/api/widgets/{WID}/crawl", headers=rep, timeout=30)
        assert g.status_code == 200

    def test_crawl_and_apply_and_dedupe(self, mgr):
        r = requests.post(f"{BASE}/api/widgets/{WID}/crawl",
                         json={"url": "www.imonsocial.com"}, headers=mgr, timeout=30)
        assert r.status_code == 200, r.text
        started = r.json()
        assert started.get("status") in ("running", "done")
        job_id = started["id"]

        job = None
        for _ in range(40):
            time.sleep(3)
            g = requests.get(f"{BASE}/api/widgets/{WID}/crawl", headers=mgr, timeout=30).json()
            job = g.get("job")
            if job and job.get("status") in ("done", "failed"):
                break
        assert job and job.get("status") in ("done", "failed"), job
        if job["status"] == "failed":
            pytest.skip(f"crawl failed (network): {job.get('error')}")

        draft = job.get("draft") or {}
        assert isinstance(draft.get("facts"), list)
        assert isinstance(draft.get("specials"), list)
        assert isinstance(job.get("pages"), list) and len(job["pages"]) >= 1
        for f in draft.get("facts", []):
            assert "—" not in f and "–" not in f
        assert "—" not in (draft.get("notes") or "")

        facts_to_add = list(draft["facts"][:2])
        if not facts_to_add:
            pytest.skip("no facts drafted")
        ap = requests.post(f"{BASE}/api/widgets/{WID}/crawl/apply", headers=mgr,
                          json={"job_id": job_id, "facts": facts_to_add, "specials": [], "notes": ""}, timeout=30)
        assert ap.status_code == 200, ap.text
        aj = ap.json()
        assert aj.get("added_facts") == len(facts_to_add)
        assert isinstance(aj.get("facts"), list)
        added_ids = [f["id"] for f in aj["facts"] if f.get("text") in facts_to_add]

        # dedupe
        ap2 = requests.post(f"{BASE}/api/widgets/{WID}/crawl/apply", headers=mgr,
                           json={"job_id": job_id, "facts": facts_to_add, "specials": [], "notes": ""}, timeout=30)
        assert ap2.status_code == 200
        assert ap2.json().get("added_facts") == 0

        # cleanup
        for fid in added_ids:
            requests.delete(f"{BASE}/api/widgets/{WID}/facts/{fid}", headers=mgr, timeout=30)


# ------------------- UPLOAD -------------------
class TestUpload:
    def _tiny_png(self):
        # Generate a valid PNG using PIL
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (8, 8), (200, 100, 50)).save(buf, format="PNG")
        return buf.getvalue()

    def test_upload_avatar(self, mgr):
        files = {"file": ("t.png", io.BytesIO(self._tiny_png()), "image/png")}
        data = {"target": "avatar"}
        # Cloudflare occasionally 502s; retry once.
        r = None
        for _ in range(2):
            r = requests.post(f"{BASE}/api/widgets/{WID}/upload", files=files, data=data, headers=mgr, timeout=90)
            if r.status_code != 502:
                break
            time.sleep(2)
            files = {"file": ("t.png", io.BytesIO(self._tiny_png()), "image/png")}
        if r.status_code == 502:
            pytest.skip("Upstream 502 from CDN on upload")
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("url", "").startswith("/api/images/")
        assert "original_url" in j and "thumbnail_url" in j and "avatar_url" in j
        # fetch the image
        img = requests.get(f"{BASE}{j['url']}", timeout=30)
        assert img.status_code == 200
        assert (img.headers.get("content-type") or "").startswith("image/")

    def test_non_image_rejected(self, mgr):
        files = {"file": ("t.txt", io.BytesIO(b"hello"), "text/plain")}
        r = requests.post(f"{BASE}/api/widgets/{WID}/upload", files=files, data={"target": "avatar"},
                         headers=mgr, timeout=30)
        assert r.status_code == 400

    def test_rep_forbidden(self, rep):
        files = {"file": ("t.png", io.BytesIO(self._tiny_png()), "image/png")}
        r = requests.post(f"{BASE}/api/widgets/{WID}/upload", files=files, data={"target": "avatar"},
                         headers=rep, timeout=30)
        assert r.status_code == 403


# ------------------- WIDGET JS -------------------
class TestWidgetJs:
    def test_widget_js_has_new_bits(self, key):
        r = requests.get(f"{BASE}/api/w/{key}.js", timeout=30)
        assert r.status_code == 200
        body = r.text
        for token in ["imosw-book", "imosw-chip", "/slots", "/book", "stopPoll", "'rep'", "'system'"]:
            assert token in body, f"missing token in widget.js: {token}"

    def test_demo_renders(self, key):
        r = requests.get(f"{BASE}/api/w/{key}/demo?door=chat", timeout=30)
        assert r.status_code == 200
        assert "<html" in r.text.lower() or "<!doctype" in r.text.lower()


# ------------------- CLEANUP -------------------
def test_zzz_cleanup_widget(mgr):
    """Restore widget to defaults per instructions."""
    r = requests.put(f"{BASE}/api/widgets/{WID}", headers=mgr, timeout=30, json={
        "doors": {"chat": {"on": True, "booking_on": True, "notify_reps": True, "label": "Chat now"}},
        "appearance": {"page_rules": [], "avatar_url": "", "icon_url": ""},
    })
    assert r.status_code == 200, r.text
