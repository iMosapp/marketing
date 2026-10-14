"""Backend tests for voice-memos iter358: view=attached/unattached, tags PATCH, day-label PUT, delete attached."""
import os
import pytest
import requests
from tests import qa_creds

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://user-routing-issue.preview.emergentagent.com').rstrip('/')
UID = '6a978d68b8673c29063aa8b9'
ATT_MEMO = '6ac56248b0694990705a353b'  # attached, Sarah
UN_MARCUS = '6ac56248b0694990705a3538'
UN_SERVICE = '6ac56248b0694990705a3539'
UN_TRADE = '6ac56248b0694990705a353a'


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "activation-tester@invalid.imonsocial.test",
                            "password": qa_creds.password_for("activation-tester@invalid.imonsocial.test")})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def token2():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "qa-manager@invalid.imonsocial.test",
                            "password": qa_creds.password_for("qa-manager@invalid.imonsocial.test")})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def H(t):
    return {"Authorization": f"Bearer {t}"}


# GET view=unattached (default)
def test_get_unattached(token):
    r = requests.get(f"{BASE_URL}/api/voice-memos/{UID}?view=unattached", headers=H(token))
    assert r.status_code == 200, r.text
    data = r.json()
    assert "memos" in data and "counts" in data and "day_labels" in data
    titles = [m["title"] for m in data["memos"]]
    for required in ["QA Memo Marcus Delgado", "QA Memo Service walk-around", "QA Memo Trade show thought"]:
        assert required in titles, f"missing {required}"
    for m in data["memos"]:
        assert m["contact_id"] is None
        assert m["attached_at"] == ""
        assert "tags" in m and isinstance(m["tags"], list)
        assert m.get("kind") == "memo"
    assert data["counts"]["unattached"] == len(data["memos"])
    assert data["day_labels"].get("2026-10-06") == "Walk-around Wednesday"


def test_get_default_equals_unattached(token):
    a = requests.get(f"{BASE_URL}/api/voice-memos/{UID}", headers=H(token)).json()
    b = requests.get(f"{BASE_URL}/api/voice-memos/{UID}?view=unattached", headers=H(token)).json()
    assert [m["id"] for m in a["memos"]] == [m["id"] for m in b["memos"]]


def test_get_attached(token):
    r = requests.get(f"{BASE_URL}/api/voice-memos/{UID}?view=attached", headers=H(token))
    assert r.status_code == 200
    data = r.json()
    assert data["counts"]["attached"] == len(data["memos"])
    sarah = next((m for m in data["memos"] if m["id"] == ATT_MEMO), None)
    assert sarah is not None
    assert sarah["contact_name"] == "Sarah Tester"
    assert sarah["contact_id"] == "6aa413008f0d53e3f2261853"
    assert set(sarah["tags"]) == {"Kubota", "Pricing"}
    assert sarah["attached_at"]
    # ensure newest-first by attached_at
    ats = [m["attached_at"] for m in data["memos"]]
    assert ats == sorted(ats, reverse=True)


# PATCH tags normalization
def test_patch_tags_normalize(token):
    payload = {"tags": ["  Kubota  ", "kubota", "", "   ", "Hot Lead", "hot lead", "x" * 50]}
    r = requests.patch(f"{BASE_URL}/api/voice-memos/{UID}/{UN_MARCUS}",
                       json=payload, headers=H(token))
    assert r.status_code == 200, r.text
    tags = r.json()["tags"]
    # dedup case-insensitive, trim whitespace runs, drop empties, 40 char cap
    assert tags == ["Kubota", "Hot Lead", "x" * 40]
    # restore
    requests.patch(f"{BASE_URL}/api/voice-memos/{UID}/{UN_MARCUS}",
                   json={"tags": ["Kubota"]}, headers=H(token))


def test_patch_max_20_tags(token):
    many = [f"tag{i}" for i in range(30)]
    r = requests.patch(f"{BASE_URL}/api/voice-memos/{UID}/{UN_MARCUS}",
                       json={"tags": many}, headers=H(token))
    assert r.status_code == 200
    assert len(r.json()["tags"]) == 20
    requests.patch(f"{BASE_URL}/api/voice-memos/{UID}/{UN_MARCUS}",
                   json={"tags": ["Kubota"]}, headers=H(token))


def test_patch_title(token):
    r = requests.patch(f"{BASE_URL}/api/voice-memos/{UID}/{UN_MARCUS}",
                       json={"title": "Renamed Test"}, headers=H(token))
    assert r.status_code == 200
    assert r.json()["title"] == "Renamed Test"
    # restore
    requests.patch(f"{BASE_URL}/api/voice-memos/{UID}/{UN_MARCUS}",
                   json={"title": "QA Memo Marcus Delgado"}, headers=H(token))


def test_patch_empty_body_400(token):
    r = requests.patch(f"{BASE_URL}/api/voice-memos/{UID}/{UN_MARCUS}",
                       json={}, headers=H(token))
    assert r.status_code == 400
    assert "Nothing to change" in r.text


def test_patch_attached_memo_tags_works(token):
    r = requests.patch(f"{BASE_URL}/api/voice-memos/{UID}/{ATT_MEMO}",
                       json={"tags": ["Kubota", "Pricing", "Priority"]}, headers=H(token))
    assert r.status_code == 200
    assert set(r.json()["tags"]) == {"Kubota", "Pricing", "Priority"}
    # restore
    requests.patch(f"{BASE_URL}/api/voice-memos/{UID}/{ATT_MEMO}",
                   json={"tags": ["Kubota", "Pricing"]}, headers=H(token))


def test_patch_unknown_404(token):
    r = requests.patch(f"{BASE_URL}/api/voice-memos/{UID}/6ac56248b0694990705a9999",
                       json={"title": "x"}, headers=H(token))
    assert r.status_code == 404


def test_patch_other_user_403(token2):
    r = requests.patch(f"{BASE_URL}/api/voice-memos/{UID}/{UN_MARCUS}",
                       json={"title": "nope"}, headers=H(token2))
    assert r.status_code == 403


# PUT day-label
def test_put_day_label_set_and_remove(token):
    # set
    r = requests.put(f"{BASE_URL}/api/voice-memos/{UID}/day-label",
                     json={"day": "2026-10-05", "label": "Service day"}, headers=H(token))
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "day": "2026-10-05", "label": "Service day"}
    # verify via GET
    g = requests.get(f"{BASE_URL}/api/voice-memos/{UID}", headers=H(token)).json()
    assert g["day_labels"].get("2026-10-05") == "Service day"
    # remove
    r2 = requests.put(f"{BASE_URL}/api/voice-memos/{UID}/day-label",
                      json={"day": "2026-10-05", "label": ""}, headers=H(token))
    assert r2.status_code == 200
    g2 = requests.get(f"{BASE_URL}/api/voice-memos/{UID}", headers=H(token)).json()
    assert "2026-10-05" not in g2["day_labels"]


def test_put_day_label_bad_format(token):
    r = requests.put(f"{BASE_URL}/api/voice-memos/{UID}/day-label",
                     json={"day": "10/05/2026", "label": "oops"}, headers=H(token))
    assert r.status_code == 400


# DELETE attached memo should 404
def test_delete_attached_404(token):
    r = requests.delete(f"{BASE_URL}/api/voice-memos/{UID}/{ATT_MEMO}", headers=H(token))
    assert r.status_code == 404
