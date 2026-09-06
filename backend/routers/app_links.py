"""Share-the-app links: tracked App Store redirect, QR, first-open install matching, per-user stats."""
import hashlib
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

from routers.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["app-links"])

APP_STORE_URL = "https://apps.apple.com/us/app/im-on-social/id6774618559"
PLAY_STORE_URL = os.environ.get("PLAY_STORE_URL")  # not listed yet -> marketing site
SITE_GET_APP_URL = os.environ.get("MARKETING_SITE_URL", "https://imonsocial.com").rstrip("/") + "/#get-the-app"
LINK_BASE = os.environ.get("APP_LINK_BASE", "https://imonsocial.com/get").rstrip("/")
MATCH_WINDOW_HOURS = 72
SITE_CODE = "site"


def _now():
    return datetime.now(timezone.utc)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return (fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "")) or ""


def _ip_hash(ip: str) -> str:
    return hashlib.sha256(f"{ip}|{os.environ.get('JWT_SECRET', 'imos')}".encode()).hexdigest()[:16]


def _platform_from_ua(ua: str) -> str:
    ua = (ua or "").lower()
    if any(k in ua for k in ("iphone", "ipad", "ipod")):
        return "ios"
    if "android" in ua:
        return "android"
    return "desktop"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())[:24]


async def _ensure_link(db, user: dict) -> dict:
    uid = str(user["_id"])
    link = await db.app_links.find_one({"user_id": uid, "kind": "personal"})
    if link:
        return link
    base = _slug(user.get("first_name")) or _slug(user.get("name")) or "rep"
    code, n = base, 2
    while await db.app_links.find_one({"code": code}):
        code, n = f"{base}{n}", n + 1
    doc = {"code": code, "user_id": uid, "kind": "personal", "label": "My link", "created_at": _now()}
    await db.app_links.insert_one(doc)
    if user.get("role") == "super_admin" and not await db.app_links.find_one({"code": SITE_CODE}):
        await db.app_links.insert_one({"code": SITE_CODE, "user_id": uid, "kind": "site", "label": "Marketing site", "created_at": _now()})
    return doc


async def _notify_owner(db, owner_id: str, title: str, body: str, ntype: str):
    await db.notifications.insert_one({
        "type": ntype, "user_id": owner_id, "title": title, "message": body, "icon": "phone-portrait",
        "color": "#34C759", "link": "/share-app", "read": False, "dismissed": False, "created_at": _now(),
    })
    try:
        from routers.push_notifications import send_push_to_user
        await send_push_to_user(owner_id, title, body, "/share-app", "phone-portrait")
    except Exception as e:
        logger.warning(f"[app-links] push failed: {e}")


# ---------------------------------------------------------------- public: tap + redirect
@router.get("/get/{code}")
async def tap_and_redirect(code: str, request: Request):
    db = get_db()
    code = code.lower().strip()
    link = await db.app_links.find_one({"code": code})
    ua = request.headers.get("user-agent", "")
    platform = _platform_from_ua(ua)
    await db.app_link_taps.insert_one({
        "code": code, "user_id": link["user_id"] if link else None, "platform": platform,
        "ip_hash": _ip_hash(_client_ip(request)), "ua": ua[:300], "created_at": _now(), "matched_install_id": None,
    })
    if platform == "android":
        target = PLAY_STORE_URL or SITE_GET_APP_URL
    else:
        target = APP_STORE_URL  # iPhone opens the App Store app; desktop gets Apple's listing page
    return RedirectResponse(target, status_code=302)


@router.get("/app-links/qr/{code}.png")
async def link_qr(code: str, size: int = 512):
    import qrcode
    from qrcode.constants import ERROR_CORRECT_M
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=10, border=2)
    qr.add_data(f"{LINK_BASE}/{code.lower()}")
    qr.make(fit=True)
    img = qr.make_image(fill_color="#111111", back_color="white").convert("RGB")
    img = img.resize((max(128, min(size, 1024)),) * 2)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


# ---------------------------------------------------------------- public: first open (called by the app once per device)
@router.post("/app-installs/first-open")
async def first_open(request: Request, data: dict = Body(...)):
    db = get_db()
    install_id = str(data.get("install_id") or "").strip()[:80]
    if not install_id:
        raise HTTPException(400, "install_id required")
    existing = await db.app_installs.find_one({"install_id": install_id})
    if existing:
        return {"ok": True, "attributed": bool(existing.get("attributed_code")), "duplicate": True}
    platform = (data.get("platform") or "").lower()
    ip_hash = _ip_hash(_client_ip(request))
    since = _now() - timedelta(hours=MATCH_WINDOW_HOURS)
    tap = await db.app_link_taps.find_one(
        {"ip_hash": ip_hash, "platform": platform, "created_at": {"$gte": since}, "matched_install_id": None},
        sort=[("created_at", -1)])
    doc = {
        "install_id": install_id, "platform": platform, "os_version": str(data.get("os_version") or "")[:40],
        "app_version": str(data.get("app_version") or "")[:20], "timezone": str(data.get("timezone") or "")[:60],
        "locale": str(data.get("locale") or "")[:20], "ip_hash": ip_hash, "first_open_at": _now(),
        "attributed_code": tap["code"] if tap else None, "attributed_user_id": tap.get("user_id") if tap else None,
        "attributed_tap_id": tap["_id"] if tap else None, "claimed_user_id": None, "claimed_name": None, "claimed_at": None,
    }
    await db.app_installs.insert_one(doc)
    if tap:
        await db.app_link_taps.update_one({"_id": tap["_id"]}, {"$set": {"matched_install_id": install_id}})
        if tap.get("user_id"):
            label = "your website QR" if tap["code"] == SITE_CODE else "your link"
            await _notify_owner(db, tap["user_id"], "New app install",
                                f"Someone who tapped {label} just installed i'M On Social on {'iPhone' if platform == 'ios' else platform}.",
                                "app_install")
    return {"ok": True, "attributed": bool(tap)}


# ---------------------------------------------------------------- claim: ties the install to the signed-in user
@router.post("/app-installs/claim")
async def claim_install(request: Request, data: dict = Body(...)):
    from routers.auth import verify_jwt_token
    auth = request.headers.get("Authorization", "")
    payload = verify_jwt_token(auth[7:]) if auth.startswith("Bearer ") else None
    if not payload or not payload.get("sub"):
        raise HTTPException(401, "Authentication required")
    db = get_db()
    install_id = str(data.get("install_id") or "").strip()[:80]
    inst = await db.app_installs.find_one({"install_id": install_id})
    if not inst:
        return {"ok": True, "claimed": False}
    if inst.get("claimed_user_id"):
        return {"ok": True, "claimed": True, "duplicate": True}
    user = await db.users.find_one({"_id": ObjectId(payload["sub"])}, {"first_name": 1, "last_name": 1, "name": 1, "email": 1})
    name = " ".join(filter(None, [(user or {}).get("first_name"), (user or {}).get("last_name")])).strip() or (user or {}).get("name") or (user or {}).get("email") or "A new user"
    await db.app_installs.update_one({"_id": inst["_id"]}, {"$set": {"claimed_user_id": payload["sub"], "claimed_name": name, "claimed_at": _now()}})
    owner = inst.get("attributed_user_id")
    if owner and owner != payload["sub"]:
        await _notify_owner(db, owner, f"{name} joined from your link", f"{name} installed i'M On Social and signed up. Say hi.", "app_signup")
    return {"ok": True, "claimed": True}


# ---------------------------------------------------------------- owner: link + stats
@router.get("/app-links/{user_id}")
async def my_app_link(user_id: str):
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"first_name": 1, "name": 1, "role": 1})
    if not user:
        raise HTTPException(404, "User not found")
    link = await _ensure_link(db, user)
    codes = [l["code"] async for l in db.app_links.find({"user_id": user_id}, {"code": 1})]
    week = _now() - timedelta(days=7)
    taps_total = await db.app_link_taps.count_documents({"code": {"$in": codes}})
    taps_week = await db.app_link_taps.count_documents({"code": {"$in": codes}, "created_at": {"$gte": week}})
    installs = await db.app_installs.count_documents({"attributed_code": {"$in": codes}})
    signups = await db.app_installs.count_documents({"attributed_code": {"$in": codes}, "claimed_user_id": {"$ne": None}})

    recent = []
    async for t in db.app_link_taps.find({"code": {"$in": codes}}, sort=[("created_at", -1)], limit=15):
        recent.append({"kind": "tap", "code": t["code"], "platform": t.get("platform"), "at": t["created_at"].isoformat()})
    async for i in db.app_installs.find({"attributed_code": {"$in": codes}}, sort=[("first_open_at", -1)], limit=15):
        recent.append({"kind": "signup" if i.get("claimed_user_id") else "install", "code": i.get("attributed_code"),
                       "platform": i.get("platform"), "name": i.get("claimed_name"),
                       "at": (i.get("claimed_at") or i["first_open_at"]).isoformat()})
    recent.sort(key=lambda r: r["at"], reverse=True)
    return {
        "code": link["code"], "link": f"{LINK_BASE}/{link['code']}", "qr_path": f"/app-links/qr/{link['code']}.png",
        "app_store_url": APP_STORE_URL, "codes": codes,
        "stats": {"taps": taps_total, "taps_week": taps_week, "installs": installs, "signups": signups},
        "recent": recent[:20],
    }
