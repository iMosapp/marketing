"""Twilio webhook signature validation for every public Twilio callback.
Mode via TWILIO_WEBHOOK_VALIDATION: enforce (default: 403 on a missing or bad signature) | log (record mismatches, never
block: the emergency lever, set it in production secrets to loosen without a code change) | off.
The signing token is the auth token of the account that owns the number (subaccount when provisioned, else the parent)."""
import logging
import os
from typing import Optional

from fastapi import HTTPException, Request
from fastapi.responses import Response

from services import twilio_tenant as tenant

logger = logging.getLogger(__name__)

# Under the Twilio prefix but called by the app with a session, never by Twilio.
APP_ROUTES = ("/call", "/call-cancel")
APP_ROUTE_PREFIXES = ("/call-progress/",)


def mode() -> str:
    m = (os.environ.get("TWILIO_WEBHOOK_VALIDATION") or "enforce").strip().lower()
    return m if m in ("off", "log", "enforce") else "enforce"


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
    from twilio.request_validator import RequestValidator
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


def is_app_route(path: str) -> bool:
    tail = path.split("/webhooks/twilio", 1)[-1]
    return tail in APP_ROUTES or tail.startswith(APP_ROUTE_PREFIXES)


async def require_signed_callback(request: Request) -> None:
    """Router dependency: every POST Twilio callback must carry a valid signature before its handler runs.
    GET fetches (TwiML <Play> media, greeting mp3, media proxy) and the app's own session routes are not Twilio callbacks."""
    if request.method != "POST" or is_app_route(request.url.path):
        return
    from routers.database import get_db
    form = dict(await request.form())
    blocked = await guard(request, form, get_db(), request.url.path.split("/webhooks/twilio", 1)[-1].strip("/") or "root")
    if blocked is not None:
        raise HTTPException(status_code=403, detail="forbidden")
