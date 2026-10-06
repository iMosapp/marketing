"""Backend tests for voice memos (chunked upload, list, rename, delete, attach, permissions)."""
import base64
import io
import math
import os
import struct
import wave

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

FOREST_EMAIL = "forest@imosapp.com"
FOREST_PASS = "Admin123!"
OTHER_EMAIL = "qa-manager@invalid.imonsocial.test"
OTHER_PASS = "Manager123!"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    body = r.json()
    user = body.get("user") or {}
    uid = str(user.get("_id") or user.get("id") or "")
    return body["token"], uid


def _wav_bytes(seconds=3, freq=440, rate=16000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        for i in range(int(seconds * rate)):
            val = int(0.3 * 32767 * math.sin(2 * math.pi * freq * i / rate))
            w.writeframes(struct.pack("<h", val))
    return buf.getvalue()


@pytest.fixture(scope="module")
def forest():
    tok, uid = _login(FOREST_EMAIL, FOREST_PASS)
    return {"token": tok, "id": uid}


@pytest.fixture(scope="module")
def other_user():
    try:
        tok, uid = _login(OTHER_EMAIL, OTHER_PASS)
        return {"token": tok, "id": uid}
    except AssertionError:
        pytest.skip("qa-manager user not available")


@pytest.fixture(scope="module")
def seeded_memo(forest):
    """Upload a 3-second WAV memo and return its id."""
    audio = _wav_bytes(3)
    b64 = base64.b64encode(audio).decode()
    upload_id = "testmemo" + os.urandom(4).hex()
    headers = {"Authorization": f"Bearer {forest['token']}"}
    # Single-chunk upload
    r = requests.post(
        f"{API}/voice-memos/{forest['id']}/chunk",
        json={"upload_id": upload_id, "index": 0, "total": 1, "data": b64,
              "content_type": "audio/wav", "duration": 3.0},
        headers=headers, timeout=120,
    )
    assert r.status_code == 200, f"chunk upload failed {r.status_code} {r.text}"
    data = r.json()
    assert data.get("success") is True
    assert data.get("id")
    assert data.get("audio_url", "").startswith("/api/images/")
    return data["id"]


# --- Chunked upload ---------------------------------------------------------
class TestChunkUpload:
    def test_partial_upload_returns_progress(self, forest):
        headers = {"Authorization": f"Bearer {forest['token']}"}
        audio = _wav_bytes(2)
        b64 = base64.b64encode(audio).decode()
        upload_id = "partial" + os.urandom(4).hex()
        half = len(b64) // 2
        r = requests.post(
            f"{API}/voice-memos/{forest['id']}/chunk",
            json={"upload_id": upload_id, "index": 0, "total": 2, "data": b64[:half],
                  "content_type": "audio/wav", "duration": 2.0},
            headers=headers, timeout=30,
        )
        assert r.status_code == 200
        d = r.json()
        assert d.get("success") is True
        assert d.get("received") == 1
        assert d.get("total") == 2
        assert "id" not in d  # not yet assembled
        # Cleanup orphan chunks: send the last piece too so they drain
        requests.post(
            f"{API}/voice-memos/{forest['id']}/chunk",
            json={"upload_id": upload_id, "index": 1, "total": 2, "data": b64[half:],
                  "content_type": "audio/wav", "duration": 2.0},
            headers=headers, timeout=120,
        )

    def test_duration_above_limit_rejected(self, forest):
        headers = {"Authorization": f"Bearer {forest['token']}"}
        audio = _wav_bytes(1)
        b64 = base64.b64encode(audio).decode()
        r = requests.post(
            f"{API}/voice-memos/{forest['id']}/chunk",
            json={"upload_id": "toolong" + os.urandom(3).hex(), "index": 0, "total": 1,
                  "data": b64, "content_type": "audio/wav", "duration": 2800},
            headers=headers, timeout=20,
        )
        assert r.status_code == 400

    def test_seeded_memo_has_fields(self, seeded_memo, forest):
        # confirm the seeded memo is reachable via GET list
        r = requests.get(f"{API}/voice-memos/{forest['id']}",
                         headers={"Authorization": f"Bearer {forest['token']}"}, timeout=20)
        assert r.status_code == 200
        ids = [m["id"] for m in r.json().get("memos", [])]
        assert seeded_memo in ids


# --- Permissions ------------------------------------------------------------
class TestPermissions:
    def test_unauthenticated_list(self, forest):
        r = requests.get(f"{API}/voice-memos/{forest['id']}", timeout=15)
        assert r.status_code in (401, 403)

    def test_other_user_forbidden(self, forest, other_user):
        r = requests.get(
            f"{API}/voice-memos/{forest['id']}",
            headers={"Authorization": f"Bearer {other_user['token']}"}, timeout=20,
        )
        assert r.status_code == 403


# --- List / rename / delete / attach ---------------------------------------
class TestMemoLifecycle:
    def test_list_only_unattached_newest_first(self, forest, seeded_memo):
        r = requests.get(f"{API}/voice-memos/{forest['id']}",
                         headers={"Authorization": f"Bearer {forest['token']}"}, timeout=20)
        assert r.status_code == 200
        memos = r.json().get("memos", [])
        assert isinstance(memos, list) and len(memos) >= 1
        # Newest first: created_at descending
        times = [m.get("created_at", "") for m in memos]
        assert times == sorted(times, reverse=True)
        # None are attached
        for m in memos:
            assert not m.get("contact_id")

    def test_rename(self, forest, seeded_memo):
        new_title = "TEST_renamed_memo"
        r = requests.patch(
            f"{API}/voice-memos/{forest['id']}/{seeded_memo}",
            json={"title": new_title},
            headers={"Authorization": f"Bearer {forest['token']}"}, timeout=20,
        )
        assert r.status_code == 200
        assert r.json().get("title") == new_title
        # Verify persisted
        r = requests.get(f"{API}/voice-memos/{forest['id']}",
                         headers={"Authorization": f"Bearer {forest['token']}"}, timeout=20)
        got = next((m for m in r.json()["memos"] if m["id"] == seeded_memo), None)
        assert got and got["title"] == new_title

    def test_delete_memo(self, forest):
        # create a throwaway memo and delete it
        audio = _wav_bytes(2)
        b64 = base64.b64encode(audio).decode()
        r = requests.post(
            f"{API}/voice-memos/{forest['id']}/chunk",
            json={"upload_id": "del" + os.urandom(4).hex(), "index": 0, "total": 1,
                  "data": b64, "content_type": "audio/wav", "duration": 2.0},
            headers={"Authorization": f"Bearer {forest['token']}"}, timeout=120,
        )
        memo_id = r.json()["id"]
        d = requests.delete(f"{API}/voice-memos/{forest['id']}/{memo_id}",
                            headers={"Authorization": f"Bearer {forest['token']}"}, timeout=20)
        assert d.status_code == 200
        # Second delete -> 404
        d2 = requests.delete(f"{API}/voice-memos/{forest['id']}/{memo_id}",
                             headers={"Authorization": f"Bearer {forest['token']}"}, timeout=20)
        assert d2.status_code == 404


# --- Attach ----------------------------------------------------------------
class TestAttach:
    def _get_a_contact(self, forest):
        r = requests.get(
            f"{API}/contacts/{forest['id']}?limit=5",
            headers={"Authorization": f"Bearer {forest['token']}"}, timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        contacts = body if isinstance(body, list) else body.get("contacts") or body.get("items") or []
        assert contacts, "No contact available for attach test"
        return str(contacts[0].get("_id") or contacts[0].get("id"))

    def test_attach_to_nonexistent_contact_404(self, forest, seeded_memo):
        r = requests.post(
            f"{API}/voice-memos/{forest['id']}/{seeded_memo}/attach",
            json={"contact_id": "6a" + "0" * 22, "as_kind": "memo"},
            headers={"Authorization": f"Bearer {forest['token']}"}, timeout=30,
        )
        assert r.status_code == 404

    def test_attach_memo_moves_to_contact_and_404_on_reattach(self, forest):
        # Fresh memo
        audio = _wav_bytes(3)
        b64 = base64.b64encode(audio).decode()
        r = requests.post(
            f"{API}/voice-memos/{forest['id']}/chunk",
            json={"upload_id": "att" + os.urandom(4).hex(), "index": 0, "total": 1,
                  "data": b64, "content_type": "audio/wav", "duration": 3.0},
            headers={"Authorization": f"Bearer {forest['token']}"}, timeout=120,
        )
        assert r.status_code == 200
        memo = r.json()
        memo_id = memo["id"]
        # Set a known title
        requests.patch(
            f"{API}/voice-memos/{forest['id']}/{memo_id}",
            json={"title": "TEST_attach_memo"},
            headers={"Authorization": f"Bearer {forest['token']}"}, timeout=15,
        )
        contact_id = self._get_a_contact(forest)
        r = requests.post(
            f"{API}/voice-memos/{forest['id']}/{memo_id}/attach",
            json={"contact_id": contact_id, "as_kind": "memo"},
            headers={"Authorization": f"Bearer {forest['token']}"}, timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("contact_id") == contact_id
        assert body.get("kind") == "memo"
        # Gone from unattached list
        lst = requests.get(f"{API}/voice-memos/{forest['id']}",
                           headers={"Authorization": f"Bearer {forest['token']}"}, timeout=15).json()
        assert memo_id not in [m["id"] for m in lst.get("memos", [])]
        # Appears on contact's voice notes list with title preserved
        vn = requests.get(f"{API}/voice-notes/{forest['id']}/{contact_id}",
                         headers={"Authorization": f"Bearer {forest['token']}"}, timeout=20)
        assert vn.status_code == 200, vn.text
        vn_body = vn.json()
        notes = vn_body if isinstance(vn_body, list) else vn_body.get("notes") or vn_body.get("voice_notes") or []
        got = next((n for n in notes if str(n.get("id") or n.get("_id")) == memo_id), None)
        assert got is not None, f"memo not found on contact voice notes: {notes}"
        assert got.get("title") == "TEST_attach_memo"
        # Re-attach same memo -> 404
        r2 = requests.post(
            f"{API}/voice-memos/{forest['id']}/{memo_id}/attach",
            json={"contact_id": contact_id, "as_kind": "memo"},
            headers={"Authorization": f"Bearer {forest['token']}"}, timeout=20,
        )
        assert r2.status_code == 404
        # Cleanup
        requests.delete(
            f"{API}/voice-notes/{forest['id']}/{contact_id}/{memo_id}",
            headers={"Authorization": f"Bearer {forest['token']}"}, timeout=20,
        )

    def test_attach_as_conversation(self, forest):
        audio = _wav_bytes(3)
        b64 = base64.b64encode(audio).decode()
        r = requests.post(
            f"{API}/voice-memos/{forest['id']}/chunk",
            json={"upload_id": "conv" + os.urandom(4).hex(), "index": 0, "total": 1,
                  "data": b64, "content_type": "audio/wav", "duration": 3.0},
            headers={"Authorization": f"Bearer {forest['token']}"}, timeout=120,
        )
        memo_id = r.json()["id"]
        contact_id = TestAttach()._get_a_contact(forest)
        r = requests.post(
            f"{API}/voice-memos/{forest['id']}/{memo_id}/attach",
            json={"contact_id": contact_id, "as_kind": "conversation"},
            headers={"Authorization": f"Bearer {forest['token']}"}, timeout=60,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("kind") == "conversation"
        # Cleanup
        requests.delete(
            f"{API}/voice-notes/{forest['id']}/{contact_id}/{memo_id}",
            headers={"Authorization": f"Bearer {forest['token']}"}, timeout=20,
        )
