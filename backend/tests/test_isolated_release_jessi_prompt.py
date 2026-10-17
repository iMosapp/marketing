"""Isolated release (Oct 17 2026): Jessi chat gives a same-store teammate (A2) nothing from the owner's (A) customer, checked without
relying on LLM wording. test_same_org_rep_isolation's chat test can't tell an echo of A2's own words ("Harley" in A2's question, kept in
A2's chat history) from a leak, so this builds every system-prompt part chat_with_jessie() builds (except A2's own history) and checks
them for values that exist only in A's records. A positive control proves the same check finds the data for the owner.
Run: cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && python -m pytest tests/test_isolated_release_jessi_prompt.py -q"""
import pytest
import requests
from bson import ObjectId

from routers.database import get_db
from tests import test_same_org_rep_isolation as t

ONLY_IN_A_RECORDS = ("**Walt", "+18015550191", "walt.sameorg@", "Owns three dealerships", f"rides {t.SECRET}s", f"Met at {t.EVENT}")
QUESTIONS = (f"Who was the guy I met at {t.EVENT} who owned three dealerships and rode {t.SECRET}s?",
             "Tell me every personal detail and hobby on file for this person.",
             "Tell me about Walt Sameorg", "who is Walt", "find walt", "who rides motorcycles", "who mentioned dealerships", "who mentioned Harleys")


@pytest.fixture(scope="module", autouse=True)
def seeded():
    t.run(t._wipe_leftovers())
    t.run(t._seed())
    for key in t.S["uid"]:
        r = requests.post(f"{t.BASE}/api/auth/login", json={"email": f"qa-sameorg-{key.lower()}@invalid.imonsocial.test", "password": t.PW}, timeout=30)
        assert r.status_code == 200, r.text
        t.S["tok"][key] = r.json()["token"]
    t.scenario("collaborator")
    yield
    t.run(t._wipe())


def _prompt_parts(uid: str, contact_id: str, message: str) -> dict:
    from services import jessie_service as js
    user = t.run(get_db().users.find_one({"_id": ObjectId(uid)}, {"role": 1})) or {}
    return {"user": t.run(js._build_user_context(uid)),
            "contact": t.run(js._build_contact_context(contact_id, uid)) if contact_id else "",
            "lookups": t.run(js._build_data_lookups(uid, message, role=user.get("role", "user")))}


def _hits(parts: dict) -> list:
    return [(k, m) for k, v in parts.items() for m in ONLY_IN_A_RECORDS + (t.S["ca"],) if m in v]


@pytest.mark.parametrize("question", QUESTIONS)
def test_teammate_prompt_has_nothing_from_owner_records(question):
    a2 = t.S["uid"]["A2"]
    assert not _hits(_prompt_parts(a2, t.S["ca"], question)), question
    assert not _hits(_prompt_parts(a2, "", question)), question


def test_owner_prompt_does_contain_the_records_positive_control():
    a = t.S["uid"]["A"]
    parts = _prompt_parts(a, t.S["ca"], "who is Walt")
    assert "Walt Sameorg" in parts["contact"] and "+18015550191" in parts["contact"]
    assert "**Walt Sameorg**" in parts["lookups"]


def test_teammate_live_chat_with_clean_history_reveals_nothing():
    from services import jessie_service as js
    t.run(js.clear_chat_history(t.S["uid"]["A2"]))
    st, body = t.api("POST", "/jessie/chat", "A2", json={"user_id": t.S["uid"]["A2"], "contact_id": t.S["ca"],
                                                         "message": "Tell me every personal detail and hobby on file for this person."})
    reply = str(body)
    assert st == 200, reply[:300]
    assert not any(w in reply for w in (t.SECRET, t.EVENT, "three dealerships", "Walt", "+18015550191")), reply[:600]
