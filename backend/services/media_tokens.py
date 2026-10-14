"""Short-lived, user-bound tokens for media that players fetch by URL (no Authorization header possible on <audio>/<Image>):
call recordings and the Twilio media proxy. HMAC-SHA256 keyed from JWT_SECRET (unchanged); the token says WHO is fetching,
the route then checks that person may hear that call."""
import base64
import hashlib
import hmac
import os
import time
from typing import Optional

TTL_SECONDS = 2 * 60 * 60
SIG_LEN = 20


def _key() -> bytes:
    secret = os.environ.get("JWT_SECRET") or ""
    if not secret:
        raise RuntimeError("JWT_SECRET missing")
    return hashlib.sha256(b"media-token:" + secret.encode()).digest()


def mint(user_id: str, ttl: int = TTL_SECONDS, now: Optional[float] = None) -> str:
    exp = int((now if now is not None else time.time()) + ttl)
    body = f"{user_id}.{exp}".encode()
    sig = hmac.new(_key(), body, hashlib.sha256).digest()[:SIG_LEN]
    return base64.urlsafe_b64encode(body + sig).decode().rstrip("=")


def verify(token: str, now: Optional[float] = None) -> Optional[str]:
    """The user_id the token was minted for, or None when forged / expired / malformed."""
    if not token or len(token) > 200:
        return None
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        body, sig = raw[:-SIG_LEN], raw[-SIG_LEN:]   # fixed-length signature: the raw bytes may contain any byte value
        user_id, exp = body.decode().split(".", 1)
    except Exception:
        return None
    if len(sig) != SIG_LEN or not hmac.compare_digest(hmac.new(_key(), body, hashlib.sha256).digest()[:SIG_LEN], sig):
        return None
    if int(exp) < (now if now is not None else time.time()):
        return None
    return user_id or None
