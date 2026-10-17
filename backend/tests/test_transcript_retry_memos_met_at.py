# Missed transcripts (retry), memos visible after reassignment (recorded_by/can_delete/403), Met-At campaign preview/enroll, Jessi enroll_group
import os
import random
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
REP = ("activation-tester@invalid.imonsocial.test", "NewPass123!", "6a978d68b8673c29063aa8b9")
MGR = ("qa-manager@invalid.imonsocial.test", "Manager123!", "6a9b2b82cc6e7504dafc33f2")
OTHER = ("mjeast1985@gmail.com", "NavyBean1!", "69c75782e051d06491e6fa9f")
HANDOFF = "6ad255ff5d01fb1e41498bbe"
QA_MEMO = "6ad255ff5d01fb1e41498bbf"
FAILED_NOTE = "6ad25708c700b04aff99c434"
RETRYING_NOTE = "6ad25709c700b04aff99c436"
CAMP = "6ad2565e176f60e4da573e2a"
STATE = {}


def _login(email, pw):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed {email} {r.status_code}")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    return s


@pytest.fixture(scope="module")
def rep():
    return _login(REP[0], REP[1])


@pytest.fixture(scope="module")
def mgr():
    return _login(MGR[0], MGR[1])


@pytest.fixture(scope="module")
def other():
    return _login(OTHER[0], OTHER[1])


def chat(s, msg):
    r = s.post(f"{BASE_URL}/api/jessie/chat", json={"user_id": REP[2], "message": msg, "include_voice": False}, timeout=120)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    print(f"\n>> {msg}\n<< tool={d.get('tool')} pending={d.get('pending')} open={d.get('open')}\n   {d.get('text')}")
    return d


# ---------- Reassignment: memos visible to the new rep ----------
class TestMemoReassignment:
    def test_rep_sees_qa_memo(self, rep):
        r = rep.get(f"{BASE_URL}/api/voice-notes/{REP[2]}/{HANDOFF}")
        assert r.status_code == 200, r.text
        notes = {n["id"]: n for n in r.json()}
        assert QA_MEMO in notes
        m = notes[QA_MEMO]
        assert m["recorded_by"] == "QA" and m["mine"] is False and m["can_delete"] is False
        assert notes[FAILED_NOTE]["transcript_status"] == "failed"
        assert notes[RETRYING_NOTE]["transcript_status"] == "retrying"
        assert notes[FAILED_NOTE]["mine"] is True and notes[FAILED_NOTE]["can_delete"] is True

    def test_rep_cannot_delete_or_rename(self, rep):
        r = rep.delete(f"{BASE_URL}/api/voice-notes/{REP[2]}/{HANDOFF}/{QA_MEMO}")
        assert r.status_code == 403 and "Only the person who recorded" in r.text
        r = rep.patch(f"{BASE_URL}/api/voice-notes/{REP[2]}/{HANDOFF}/{QA_MEMO}", json={"title": "x"})
        assert r.status_code == 403 and "rename" in r.text

    def test_rep_get_one(self, rep):
        r = rep.get(f"{BASE_URL}/api/voice-notes/{REP[2]}/{HANDOFF}/{QA_MEMO}")
        assert r.status_code == 200 and "dirt" in r.json()["transcript"].lower()

    def test_manager_can_delete_flag(self, mgr):
        r = mgr.get(f"{BASE_URL}/api/voice-notes/{MGR[2]}/{HANDOFF}")
        assert r.status_code == 200, r.text
        notes = {n["id"]: n for n in r.json()}
        assert notes[QA_MEMO]["can_delete"] is True and notes[QA_MEMO]["mine"] is True
        assert notes[FAILED_NOTE]["can_delete"] is True and notes[FAILED_NOTE]["mine"] is False

    def test_out_of_scope_404(self, other):
        r = other.get(f"{BASE_URL}/api/voice-notes/{OTHER[2]}/{HANDOFF}")
        assert r.status_code == 404 and "Contact not found" in r.text
        r = other.post(f"{BASE_URL}/api/voice-notes/{OTHER[2]}/{HANDOFF}/{FAILED_NOTE}/retry-transcript")
        assert r.status_code == 404

    def test_cross_user_path_rejected(self, other):
        r = other.get(f"{BASE_URL}/api/voice-notes/{REP[2]}/{HANDOFF}")
        print("cross-user voice-notes:", r.status_code)
        assert r.status_code in (401, 403)

    def test_manual_retry_done_short_circuit(self, rep):
        r = rep.post(f"{BASE_URL}/api/voice-notes/{REP[2]}/{HANDOFF}/{QA_MEMO}/retry-transcript")
        assert r.status_code == 200 and r.json()["transcript_status"] == "done"

    def test_voice_memos_list_has_status(self, rep):
        r = rep.get(f"{BASE_URL}/api/voice-memos/{REP[2]}")
        assert r.status_code == 200, r.text
        d = r.json()
        rows = d if isinstance(d, list) else (d.get("memos") or d.get("items") or [])
        print("memo rows", len(rows))
        for row in rows[:20]:
            assert "transcript_status" in row


# ---------- Jessi recall from another rep's memo ----------
class TestJessiRecall:
    def test_recall_person(self, rep):
        d = chat(rep, "what do I know about Qavn Handoff?")
        t = (d.get("text") or "").lower()
        assert "dirt" in t or "tacoma" in t, d.get("text")

    def test_find_mentions(self, rep):
        d = chat(rep, "who races dirt bikes?")
        assert "handoff" in (d.get("text") or "").lower(), d.get("text")


# ---------- Met-At API ----------
class TestMetAt:
    def test_events(self, rep):
        r = rep.get(f"{BASE_URL}/api/met-at/{REP[2]}/events")
        assert r.status_code == 200, r.text
        ev = {e["key"]: e for e in r.json()["events"]}
        print(ev)
        assert "nada" in ev and ev["nada"]["count"] >= 6
        assert "golf tournament" in ev

    def test_events_other_user_403(self, other):
        r = other.get(f"{BASE_URL}/api/met-at/{REP[2]}/events")
        assert r.status_code == 403, r.status_code

    def test_preview_nada(self, rep):
        r = rep.get(f"{BASE_URL}/api/met-at/{REP[2]}/preview", params={"campaign_id": CAMP, "event": "NADA"})
        assert r.status_code == 200, r.text
        d = r.json()
        print(d["counts"], [(p["name"], p["status"]) for p in d["people"]])
        assert d["campaign"]["name"] == "Qavn Trade-in Plan" and d["limit"] == 100
        st = {p["name"]: p["status"] for p in d["people"]}
        assert st.get("Qavn Bravo", "").startswith("no_phone") or any(k.startswith("Qavn Bravo") and v == "no_phone" for k, v in st.items())
        assert any(k.startswith("Qavn Charlie") and v == "opted_out" for k, v in st.items())
        assert any(k.startswith("Qavn Alpha") and v == "already" for k, v in st.items())
        assert set(d["ok_ids"]) == {p["id"] for p in d["people"] if p["status"] == "ok"}

    def test_preview_place_match(self, rep):
        r = rep.get(f"{BASE_URL}/api/met-at/{REP[2]}/preview", params={"campaign_id": CAMP, "event": "Scottsdale"})
        assert r.status_code == 200
        assert any(p["name"].startswith("Qavn Echo") for p in r.json()["people"])

    def test_preview_unknown_campaign_404(self, rep):
        r = rep.get(f"{BASE_URL}/api/met-at/{REP[2]}/preview", params={"campaign_id": "6ad2565e176f60e4da573e2b", "event": "NADA"})
        assert r.status_code == 404

    def test_preview_other_user_403(self, other):
        r = other.get(f"{BASE_URL}/api/met-at/{REP[2]}/preview", params={"campaign_id": CAMP, "event": "NADA"})
        assert r.status_code == 403, r.status_code

    def test_enroll_flow(self, rep):
        # create a NADA contact with a test phone
        ph = f"+150055501{random.randint(10, 99)}"
        r = rep.post(f"{BASE_URL}/api/contacts/{REP[2]}", json={"first_name": "Qavn", "last_name": f"Hotel{random.randint(100, 999)}", "phone": ph})
        assert r.status_code in (200, 201), r.text
        cid = r.json().get("id") or r.json().get("_id")
        STATE["hotel"] = cid
        r = rep.patch(f"{BASE_URL}/api/contacts/{REP[2]}/{cid}/how-we-met", json={"event": "NADA"})
        assert r.status_code == 200, r.text
        pv = rep.get(f"{BASE_URL}/api/met-at/{REP[2]}/preview", params={"campaign_id": CAMP, "event": "nada show"}).json()
        assert cid in pv["ok_ids"], pv["counts"]
        # stale / not-ok ids are ignored
        r = rep.post(f"{BASE_URL}/api/met-at/{REP[2]}/enroll", json={"campaign_id": CAMP, "event": "NADA", "contact_ids": [cid, HANDOFF]})
        assert r.status_code == 200, r.text
        d = r.json()
        print(d)
        assert d["enrolled"] == 1 and d["enrolled_ids"] == [cid]
        pv = rep.get(f"{BASE_URL}/api/met-at/{REP[2]}/preview", params={"campaign_id": CAMP, "event": "NADA"}).json()
        assert any(p["id"] == cid and p["status"] == "already" for p in pv["people"])
        r = rep.post(f"{BASE_URL}/api/met-at/{REP[2]}/enroll", json={"campaign_id": CAMP, "event": "NADA"})
        assert r.status_code == 200 and r.json()["enrolled"] == 0


# ---------- Jessi enroll_group ----------
class TestJessiEnrollGroup:
    def test_unknown_event(self, rep):
        d = chat(rep, "put everyone I met at CES on the trade-in plan")
        assert "do not have anyone marked as met at" in (d.get("text") or "")

    def test_nobody_new(self, rep):
        d = chat(rep, "put everyone I met at NADA on the trade-in plan")
        STATE["nobody"] = d
        assert d.get("tool") == "enroll_group"
        assert "Nobody new to add" in (d.get("text") or "") or d.get("pending")

    def test_single_enroll_uses_enroll_campaign(self, rep):
        d = chat(rep, "put Qavn Alpha on the trade-in plan")
        assert d.get("tool") == "enroll_campaign", d.get("tool")
        if d.get("pending"):
            chat(rep, "no")
