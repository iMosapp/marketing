"""Twilio webhook signature validation for every public Twilio callback.
Mode via TWILIO_WEBHOOK_VALIDATION: off | log (default: record mismatches, never block) | enforce (403 on a bad signature).
The signing token is the auth token of the account that owns the number (subaccount when provisioned, else the parent)."""
import logging
import os
from typing import Optional

from fastapi import Request
from fastapi.responses import Response

from services import twilio_tenant as tenant

logger = logging.getLogger(__name__)


def mode() -> str:
    m = (os.environ.get("TWILIO_WEBHOOK_VALIDATION") or "log").strip().lower()
    return m if m in ("off", "log", "enforce") else "log"


def candidate_urls(request: Request) -> list:
    """Twilio signs the exact URL it requested; behind the ingress we may see http:// or an internal host, so try the public shapes."""
    path_q = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    out = []
    base = (os.environ.get("PUBLIC_FACING_URL") or os.environ.get("APP_URL") or "").rstrip("/")
    if base:
        out.append(base + path_q)
    raw = str(request.url)
    out.append(raw)
    if raw.startswith("http://"):
        out.append("https://" + raw[len("http://"):])
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if host:
        out.append(f"https://{host}{path_q}")
    seen, uniq = set(), []
    for u in out:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


async def check(request: Request, form: dict, db) -> tuple[bool, str]:
    if mode() == "off":
        return True, "off"
    sig = request.headers.get("X-Twilio-Signature", "")
    if not sig:
        return False, "missing X-Twilio-Signature"
    token = await tenant.token_for_account(db, form.get("AccountSid") or "")
    if not token:
        return False, "no auth token for this account"
    try:
        from twilio.request_validator import RequestValidator
    except ImportError:
        return True, "validator unavailable"
    v = RequestValidator(token)
    params = {k: str(val) for k, val in form.items()}
    for url in candidate_urls(request):
        if v.validate(url, params, sig):
            return True, "ok"
    return False, "signature mismatch"


async def guard(request: Request, form: dict, db, where: str) -> Optional[Response]:
    """None when the request may proceed; a 403 Response when enforce mode rejects it."""
    try:
        ok, why = await check(request, form, db)
    except Exception as e:
        ok, why = False, f"validator error: {e}"
    if ok:
        return None
    m = mode()
    logger.warning(f"[TwilioSig] {where}: {why} (mode={m}, account={form.get('AccountSid', '')[:10]}, to={form.get('To', '')})")
    if m == "enforce":
        return Response(content="forbidden", status_code=403, media_type="text/plain")
    return None
