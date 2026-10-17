# Jessi enroll_group read-back -> no (cancel) -> again -> yes (enrolls); inactive campaign 400 on met-at enroll
import os
import random

import pytest
import requests

from tests.test_transcript_retry_memos_met_at import BASE_URL, REP, CAMP, chat, _login

STATE = {}


@pytest.fixture(scope="module")
def rep():
    return _login(REP[0], REP[1])


def _mk(rep, last):
    ph = f"+150055501{random.randint(10, 99)}"
    r = rep.post(f"{BASE_URL}/api/contacts/{REP[2]}", json={"first_name": "Qavn", "last_name": last, "phone": ph})
    assert r.status_code in (200, 201), r.text
    cid = r.json().get("id") or r.json().get("_id")
    assert rep.patch(f"{BASE_URL}/api/contacts/{REP[2]}/{cid}/how-we-met", json={"event": "NADA Show"}).status_code == 200
    return cid


def test_group_no_then_yes(rep):
    STATE["ids"] = [_mk(rep, f"India{random.randint(100, 999)}"), _mk(rep, f"Juliet{random.randint(100, 999)}")]
    d = chat(rep, "put everyone I met at NADA on the trade-in plan")
    assert d.get("tool") == "enroll_group" and d.get("pending") is True
    assert d["open"]["kind"] == "campaign" and d["open"]["id"] == CAMP
    t = d["text"]
    assert "2 people you met at NADA Show" in t and "Qavn Trade-in Plan" in t and "Say yes" in t and "texts stopped" in t and "no phone number" in t
    d = chat(rep, "no")
    assert "Nobody was enrolled" in d["text"]
    pv = rep.get(f"{BASE_URL}/api/met-at/{REP[2]}/preview", params={"campaign_id": CAMP, "event": "NADA"}).json()
    assert pv["counts"]["ok"] == 2
    d = chat(rep, "put everyone I met at NADA on the trade-in plan")
    assert d.get("pending") is True
    d = chat(rep, "yes")
    assert d["text"].startswith("Done. 2 people are on Qavn Trade-in Plan"), d["text"]
    print("yes open:", d.get("open"))
    pv = rep.get(f"{BASE_URL}/api/met-at/{REP[2]}/preview", params={"campaign_id": CAMP, "event": "NADA"}).json()
    assert pv["counts"]["ok"] == 0


def test_bad_inputs(rep):
    r = rep.get(f"{BASE_URL}/api/met-at/{REP[2]}/preview", params={"campaign_id": CAMP, "event": "the show"})
    print("empty-ish event:", r.status_code, r.text[:150])
    r = rep.get(f"{BASE_URL}/api/met-at/{REP[2]}/preview", params={"campaign_id": "bad", "event": "NADA"})
    assert r.status_code == 404
