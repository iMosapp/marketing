"""SESSIONS_VALID_AFTER: tokens issued before the configured moment are dead, JWT_SECRET untouched.
Pure unit tests on routers.auth (needs JWT_SECRET in the env: `set -a && . ./.env && set +a`)."""
import time
from datetime import datetime, timezone

import jwt as pyjwt
import pytest

from routers import auth

ALG = auth._JWT_ALGORITHM


def _token(iat="now", **extra):
    payload = {"sub": "507f1f77bcf86cd799439011", "role": "user", "exp": time.time() + 3600}
    if iat == "now":
        payload["iat"] = int(time.time())
    elif iat is not None:
        payload["iat"] = iat
    payload.update(extra)
    return pyjwt.encode(payload, auth._get_jwt_secret(), algorithm=ALG)


def _iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_unset_cutoff_keeps_current_behaviour(monkeypatch):
    monkeypatch.delenv("SESSIONS_VALID_AFTER", raising=False)
    assert auth.sessions_valid_after() is None
    assert auth.verify_jwt_token(_token())["sub"] == "507f1f77bcf86cd799439011"
    monkeypatch.setenv("SESSIONS_VALID_AFTER", "   ")
    assert auth.verify_jwt_token(_token()) is not None


def test_token_issued_before_cutoff_is_rejected_iso(monkeypatch):
    old = _token(iat=int(time.time()) - 3600)
    monkeypatch.setenv("SESSIONS_VALID_AFTER", _iso(time.time() - 60))
    assert auth.verify_jwt_token(old) is None
    assert auth.verify_jwt_token(_token()) is not None


def test_token_issued_before_cutoff_is_rejected_epoch(monkeypatch):
    old = _token(iat=int(time.time()) - 3600)
    monkeypatch.setenv("SESSIONS_VALID_AFTER", str(int(time.time()) - 60))
    assert auth.verify_jwt_token(old) is None
    assert auth.verify_jwt_token(_token()) is not None


def test_iat_equal_to_cutoff_is_accepted(monkeypatch):
    now = int(time.time()) - 5
    monkeypatch.setenv("SESSIONS_VALID_AFTER", str(now))
    assert auth.verify_jwt_token(_token(iat=now)) is not None
    assert auth.verify_jwt_token(_token(iat=now - 1)) is None


def test_iso_variants(monkeypatch):
    past = time.time() - 120
    for raw in (_iso(past), _iso(past).replace("Z", "+00:00"), _iso(past).rstrip("Z"), _iso(past).replace("T", " ").rstrip("Z")):
        monkeypatch.setenv("SESSIONS_VALID_AFTER", raw)
        assert abs(auth.sessions_valid_after() - past) < 1.5, raw
        assert auth.verify_jwt_token(_token()) is not None, raw
        assert auth.verify_jwt_token(_token(iat=int(past) - 10)) is None, raw


def test_missing_iat(monkeypatch):
    no_iat = _token(iat=None)
    monkeypatch.delenv("SESSIONS_VALID_AFTER", raising=False)
    assert auth.verify_jwt_token(no_iat) is not None  # unchanged behaviour without a cutoff
    monkeypatch.setenv("SESSIONS_VALID_AFTER", _iso(time.time() - 60))
    assert auth.verify_jwt_token(no_iat) is None  # cannot be placed on the timeline -> dead


def test_malformed_iat_is_rejected(monkeypatch):
    monkeypatch.setenv("SESSIONS_VALID_AFTER", _iso(time.time() - 60))
    assert auth.verify_jwt_token(_token(iat="yesterday")) is None
    assert auth.verify_jwt_token(_token(iat=True)) is None
    assert auth.verify_jwt_token(_token(iat=int(time.time()) + 900)) is None  # future iat: PyJWT ImmatureSignatureError
    assert auth.issued_after_cutoff({"iat": None}) is False
    assert auth.issued_after_cutoff({"iat": "123"}) is False
    assert auth.issued_after_cutoff({}) is False


def test_malformed_env_value_fails_closed(monkeypatch, caplog):
    for raw in ("tomorrow", "2026-13-45", "14/10/2026", "1e999x"):
        monkeypatch.setenv("SESSIONS_VALID_AFTER", raw)
        with pytest.raises(ValueError):
            auth.sessions_valid_after()
        assert auth.verify_jwt_token(_token()) is None, raw
    assert "SESSIONS_VALID_AFTER is malformed" in caplog.text


def test_signature_and_expiry_still_enforced(monkeypatch):
    monkeypatch.setenv("SESSIONS_VALID_AFTER", _iso(time.time() - 60))
    forged = pyjwt.encode({"sub": "x", "iat": int(time.time()), "exp": time.time() + 60}, "not-the-secret", algorithm=ALG)
    assert auth.verify_jwt_token(forged) is None
    expired = pyjwt.encode({"sub": "x", "iat": int(time.time()) - 7200, "exp": time.time() - 3600}, auth._get_jwt_secret(), algorithm=ALG)
    assert auth.verify_jwt_token(expired) is None
    assert auth.verify_jwt_token("mock_token_abc") is None


def test_create_jwt_token_carries_numeric_iat(monkeypatch):
    monkeypatch.setenv("SESSIONS_VALID_AFTER", _iso(time.time() - 60))
    tok = auth.create_jwt_token("507f1f77bcf86cd799439011", "user")
    payload = pyjwt.decode(tok, options={"verify_signature": False})
    assert isinstance(payload["iat"], int)
    assert auth.verify_jwt_token(tok)["role"] == "user"


def test_refresh_path_honours_cutoff(monkeypatch):
    """/auth/refresh decodes with verify_exp=False; an old token must not be tradeable for a fresh one."""
    import asyncio
    from fastapi import HTTPException

    monkeypatch.setenv("SESSIONS_VALID_AFTER", _iso(time.time() - 60))
    old = _token(iat=int(time.time()) - 3600)

    class Req:
        headers = {"Authorization": f"Bearer {old}"}

        async def json(self):
            return {}

    with pytest.raises(HTTPException) as e:
        asyncio.run(auth.refresh_session(Req()))
    assert e.value.status_code == 401


def test_impersonation_session_honours_cutoff(monkeypatch):
    """impersonate_* sessions are DB rows (8 h TTL); one created before the cutoff is dead too."""
    import asyncio
    import os
    from datetime import timedelta

    from pymongo import MongoClient

    from routers import database
    from routers.rbac import resolve_impersonation_session

    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    now = datetime.utcnow()
    tokens = {"old": "impersonate_qa_cutoff_old", "new": "impersonate_qa_cutoff_new"}
    db.impersonation_sessions.delete_many({"token": {"$in": list(tokens.values())}})
    db.impersonation_sessions.insert_many([
        {"token": tokens["old"], "impersonated_user_id": "507f1f77bcf86cd799439011", "user_id": "507f1f77bcf86cd799439011", "created_at": now - timedelta(hours=2), "expires_at": now + timedelta(hours=6)},
        {"token": tokens["new"], "impersonated_user_id": "507f1f77bcf86cd799439011", "user_id": "507f1f77bcf86cd799439011", "created_at": now, "expires_at": now + timedelta(hours=8)},
    ])
    try:
        async def run():
            database._client, database._db = None, None
            monkeypatch.delenv("SESSIONS_VALID_AFTER", raising=False)
            both = (await resolve_impersonation_session(tokens["old"]), await resolve_impersonation_session(tokens["new"]))
            monkeypatch.setenv("SESSIONS_VALID_AFTER", _iso(time.time() - 600))
            gated = (await resolve_impersonation_session(tokens["old"]), await resolve_impersonation_session(tokens["new"]))
            monkeypatch.setenv("SESSIONS_VALID_AFTER", "garbage")
            closed = await resolve_impersonation_session(tokens["new"])
            return both, gated, closed

        both, gated, closed = asyncio.run(run())
        assert both == ("507f1f77bcf86cd799439011", "507f1f77bcf86cd799439011")
        assert gated == (None, "507f1f77bcf86cd799439011")
        assert closed is None
    finally:
        db.impersonation_sessions.delete_many({"token": {"$in": list(tokens.values())}})
        database._client, database._db = None, None
