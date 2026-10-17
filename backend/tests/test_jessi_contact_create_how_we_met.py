# Jessi typed chat (unified brain), create-by-chat w/ read-back+yes, duplicate warning, recall, How we met PATCH, voice-note transcript upload
import os
import random
import re
import string
import time
from datetime import datetime

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
EMAIL, PASSWORD = "mjeast1985@gmail.com", "NavyBean1!"
UID = "69c75782e051d06491e6fa9f"
SUFFIX = "".join(random.choice(string.ascii_lowercase) for _ in range(5))
FIRST, LAST = "Qavn", f"Bryn{SUFFIX.lower()}"
PHONE_DIGITS = f"50055501{random.randint(10, 99)}"
STATE = {}


@pytest.fixture(scope="module")
def s():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    if r.status_code != 200:
        pytest.skip(f"login failed {r.status_code}")
    sess = requests.Session()
    sess.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    return sess


def chat(s, msg, contact_id=None):
    body = {"user_id": UID, "message": msg, "include_voice": False}
    if contact_id:
        body["contact_id"] = contact_id
    r = s.post(f"{BASE_URL}/api/jessie/chat", json=body, timeout=90)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    print(f"\n>> {msg}\n<< tool={d.get('tool')} pending={d.get('pending')} open={d.get('open')}\n   {d.get('text')}")
    return d


def find_contacts(s, q):
    r = s.get(f"{BASE_URL}/api/contacts/{UID}", params={"search": q, "limit": 50})
    assert r.status_code == 200
    d = r.json()
    rows = d if isinstance(d, list) else d.get("contacts", [])
    return [c for c in rows if q.lower() in f"{c.get('first_name','')} {c.get('last_name','')}".lower()]


# Auth / ownership
def test_chat_requires_auth():
    r = requests.post(f"{BASE_URL}/api/jessie/chat", json={"user_id": UID, "message": "hi"})
    assert r.status_code in (401, 403)


def test_chat_wrong_user_403(s):
    r = s.post(f"{BASE_URL}/api/jessie/chat", json={"user_id": "69a0b7095fddcede09591669", "message": "hi"})
    assert r.status_code == 403


# Response shape + app help
def test_app_help_answer(s):
    chat(s, "never mind")
    d = chat(s, "how do I send my digital card?")
    for k in ("text", "session_id", "open", "tool", "pending"):
        assert k in d
    assert d["tool"] == "answer"
    assert len(d["text"]) > 20


# Create flow: read-back -> nothing saved -> yes -> reminder offer -> yes
def test_create_readback_nothing_saved(s):
    chat(s, "never mind")
    p = PHONE_DIGITS
    d = chat(s, f"add {FIRST} {LAST}, I met him at NADA in Las Vegas today, his number is {p[:3]} {p[3:6]} {p[6:]}. He rides Harleys. Follow up next Tuesday about a fleet deal.")
    assert d["tool"] == "create_contact"
    assert d["pending"] is True
    t = d["text"]
    assert LAST in t and "NADA" in t and "Las Vegas" in t
    assert "yes" in t.lower()
    assert re.search(r"\(?500\)?[ -.]?555[ -.]?01", t), t
    assert not find_contacts(s, LAST), "contact saved before yes"


def test_create_yes_then_reminder(s):
    d = chat(s, "yes")
    assert d["tool"] == "confirm", d
    assert d["text"].startswith(f"Saved {FIRST} {LAST}")
    assert "Tuesday" in d["text"] and "9:00 AM" in d["text"] and "fleet deal" in d["text"]
    assert d["open"]["kind"] == "contact"
    assert d["pending"] is True
    STATE["cid"] = d["open"]["id"]
    d2 = chat(s, "yes")
    assert d2["open"] and d2["open"]["kind"] == "task", d2
    assert d2["pending"] is False
    assert ".." not in d2["text"]
    STATE["reminder_text"] = d2["text"]


def test_created_contact_fields(s):
    cid = STATE.get("cid") or pytest.skip("no cid")
    r = s.get(f"{BASE_URL}/api/contacts/{UID}/{cid}")
    assert r.status_code == 200
    c = r.json()
    print(c.get("how_we_met"), c.get("notes"), c.get("tags"), c.get("source"))
    assert c.get("source") == "jessi"
    assert not (c.get("notes") or "").strip()
    assert not c.get("tags")
    h = c.get("how_we_met") or {}
    assert h.get("event") == "NADA" and h.get("place") == "Las Vegas" and h.get("source") == "jessi"
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", h.get("date") or "")
    assert h.get("summary", "").startswith("At NADA in Las Vegas, ")


def test_created_contact_memo_and_tasks(s):
    cid = STATE.get("cid") or pytest.skip("no cid")
    r = s.get(f"{BASE_URL}/api/voice-notes/{UID}/{cid}")
    assert r.status_code == 200
    d = r.json()
    notes = d if isinstance(d, list) else d.get("voice_notes") or d.get("notes") or []
    print([(n.get("kind"), n.get("source"), (n.get("transcript") or "")[:80]) for n in notes])
    assert any(n.get("kind") == "memo" and n.get("source") in ("jessi", None) and "Harley" in (n.get("transcript") or "") for n in notes)
    time.sleep(25)
    r = s.get(f"{BASE_URL}/api/tasks/{UID}/contact/{cid}")
    assert r.status_code == 200
    td = r.json()
    tasks = td if isinstance(td, list) else td.get("tasks") or []
    titles = [t.get("title") for t in tasks]
    print("tasks:", titles)
    assert len(tasks) == 1, titles
    assert titles[0] in (f"Follow up with {FIRST}: fleet deal", f"Follow up with {FIRST}: a fleet deal")
    c = s.get(f"{BASE_URL}/api/contacts/{UID}/{cid}").json()
    print("personal_details:", c.get("personal_details"))
    assert "harley" in str(c.get("personal_details") or "").lower()


# Correction + cancel
def test_correction_and_cancel(s):
    chat(s, "never mind")
    d = chat(s, f"add Qavn Corra{SUFFIX}, met her at the Phoenix auto show")
    assert d["pending"] is True and d["tool"] == "create_contact"
    d = chat(s, f"her last name is actually Corrine{SUFFIX} with an e")
    assert d["pending"] is True
    assert f"Corrine{SUFFIX}".lower() in d["text"].lower(), d["text"]
    assert not find_contacts(s, f"Corr")or all("qavn" not in (c.get("first_name") or "").lower() or SUFFIX.lower() not in (c.get("last_name") or "").lower() for c in find_contacts(s, "Corr"))
    d = chat(s, "never mind")
    assert "Nothing was saved" in d["text"]
    assert d["pending"] is False
    assert not find_contacts(s, f"Corrine{SUFFIX}")


# Duplicate warning
def test_duplicate_warning(s):
    chat(s, "never mind")
    d = chat(s, "add Qavn Dupe, his number is 500 555 0148")
    assert d["pending"] is True
    assert "Heads up: you already have" in d["text"], d["text"]
    chat(s, "no")


# Recall + find mentions
def test_recall_person(s):
    if not STATE.get("cid"):
        pytest.skip()
    chat(s, "never mind")
    d = chat(s, f"tell me about {FIRST} {LAST}")
    assert d["tool"] == "recall_person"
    assert d["open"] and d["open"]["kind"] == "contact"
    assert "NADA" in d["text"] or "Harley" in d["text"]


def test_recall_with_contact_id(s):
    cid = STATE.get("cid") or pytest.skip()
    d = chat(s, "what did I say about him?", contact_id=cid)
    assert "harley" in d["text"].lower() or "nada" in d["text"].lower()


def test_find_mentions_nada(s):
    if not STATE.get("cid"):
        pytest.skip()
    d = chat(s, "who did I meet at NADA?")
    assert d["tool"] == "find_mentions"
    assert LAST.lower() in d["text"].lower() or "Testpeterson" in d["text"]


# How we met PATCH
def test_how_we_met_patch(s):
    cid = STATE.get("cid") or pytest.skip()
    u = f"{BASE_URL}/api/contacts/{UID}/{cid}/how-we-met"
    r = s.patch(u, json={"event": "SEMA", "place": "Las Vegas", "date": "2026-11"})
    assert r.status_code == 200
    h = r.json()["how_we_met"]
    assert h["source"] == "rep" and h["date"] == "2026-11" and h["summary"] == "At SEMA in Las Vegas, Nov 2026"
    r = s.patch(u, json={"event": "SEMA", "place": "", "date": "last spring"})
    assert r.json()["how_we_met"]["date"] == ""
    r = s.patch(u, json={"event": "SEMA", "date": "2026-11-04"})
    assert r.json()["how_we_met"]["date"] == "2026-11-04"
    g = s.get(f"{BASE_URL}/api/contacts/{UID}/{cid}").json()
    assert g["how_we_met"]["source"] == "rep"
    r = s.patch(u, json={"event": "", "place": "", "date": ""})
    assert r.status_code == 200 and r.json()["how_we_met"] == {}
    g = s.get(f"{BASE_URL}/api/contacts/{UID}/{cid}").json()
    assert not g.get("how_we_met")
    s.patch(u, json={"event": "SEMA", "place": "Las Vegas"})


def test_how_we_met_other_user_contact(s):
    r = s.patch(f"{BASE_URL}/api/contacts/69a0b7095fddcede09591669/6ad234f24753a9577947c0b1/how-we-met", json={"event": "X"})
    assert r.status_code in (403, 404)


def test_rep_edit_wins_over_notes_intel(s):
    cid = STATE.get("cid") or pytest.skip()
    r = s.put(f"{BASE_URL}/api/contacts/{UID}/{cid}", json={"first_name": FIRST, "last_name": LAST, "notes": "Met him at the Scottsdale golf tournament, he has a daughter Emma getting married in June"})
    assert r.status_code == 200, r.text[:200]
    time.sleep(20)
    c = s.get(f"{BASE_URL}/api/contacts/{UID}/{cid}").json()
    print(c.get("how_we_met"), c.get("personal_details"))
    assert c["how_we_met"]["event"] == "SEMA" and c["how_we_met"]["source"] == "rep"
    assert "emma" in str(c.get("personal_details") or "").lower()


# Notes intelligence on create
def test_notes_intel_on_create(s):
    r = s.post(f"{BASE_URL}/api/contacts/{UID}", json={"first_name": "Qavn", "last_name": f"Notes{SUFFIX}", "phone": "+15005550177",
                                                     "notes": "Met her at the Scottsdale golf tournament, she has a daughter Emma getting married in June"})
    assert r.status_code in (200, 201), r.text[:200]
    cid = r.json().get("id") or r.json().get("_id")
    STATE["cid2"] = cid
    time.sleep(25)
    c = s.get(f"{BASE_URL}/api/contacts/{UID}/{cid}").json()
    print(c.get("how_we_met"), c.get("personal_details"))
    assert "scottsdale" in str(c.get("how_we_met") or "").lower() or "golf" in str(c.get("how_we_met") or "").lower()
    assert "emma" in str(c.get("personal_details") or "").lower()


# Voice note upload with transcript
def test_voice_note_with_transcript(s):
    cid = STATE.get("cid2") or STATE.get("cid") or pytest.skip()
    files = {"audio": ("clip.webm", b"\x1aE\xdf\xa3" + os.urandom(2000), "audio/webm")}
    r = s.post(f"{BASE_URL}/api/voice-notes/{UID}/{cid}", files=files, data={"duration": "7.5", "kind": "memo", "transcript": "QA transcript: she loves sailing on Lake Powell"}, timeout=60)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    print(d)
    vn = d.get("voice_note") or d
    assert vn.get("transcript") == "QA transcript: she loves sailing on Lake Powell"
    assert float(vn.get("duration") or 0) == 7.5
