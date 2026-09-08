"""Print QR links: www.imonsocial.com/go/<slug> -> /api/go/<slug> -> counted scan -> editable destination."""
import hashlib
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from io import BytesIO
from urllib.parse import urlencode

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

from routers.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["go-links"])

ADMIN_ROLES = {"super_admin", "admin"}
SITE_URL = os.environ.get("MARKETING_SITE_URL", "https://www.imonsocial.com").rstrip("/")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,39}$")
DEFAULT_LINKS = {
    "card": {"label": "4x6 leave-behind card", "destination": f"{SITE_URL}/"},
}


def _now():
    return datetime.now(timezone.utc)


def _short_url(slug: str) -> str:
    return f"{SITE_URL}/go/{slug}"


def _platform(ua: str) -> str:
    ua = (ua or "").lower()
    if "iphone" in ua or "ipad" in ua:
        return "ios"
    if "android" in ua:
        return "android"
    return "desktop"


def _ip_hash(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "")
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


def _with_utm(destination: str, slug: str) -> str:
    if "utm_" in destination:
        return destination
    sep = "&" if "?" in destination else "?"
    return destination + sep + urlencode({"utm_source": "qr", "utm_medium": "print", "utm_campaign": slug})


async def require_admin(request: Request) -> dict:
    from routers.admin_helpers import get_requesting_user
    user = await get_requesting_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user.get("role") not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


async def _get_or_seed(db, slug: str):
    link = await db.go_links.find_one({"slug": slug})
    if not link and slug in DEFAULT_LINKS:
        link = {"slug": slug, **DEFAULT_LINKS[slug], "active": True, "created_at": _now(), "updated_at": _now()}
        await db.go_links.insert_one(link)
    return link


# ---------------------------------------------------------------- public: scan + redirect
@router.get("/go/{slug}")
async def go_redirect(slug: str, request: Request):
    db = get_db()
    slug = slug.lower().strip()
    link = await _get_or_seed(db, slug)
    ua = request.headers.get("user-agent", "")
    await db.go_scans.insert_one({
        "slug": slug, "known": bool(link), "platform": _platform(ua), "ip_hash": _ip_hash(request),
        "ua": ua[:300], "referer": request.headers.get("referer", "")[:300], "scanned_at": _now(),
    })
    destination = (link or {}).get("destination") or f"{SITE_URL}/"
    return RedirectResponse(_with_utm(destination, slug), status_code=302)


# ---------------------------------------------------------------- public: print-ready QR
def _qr(slug: str):
    import qrcode
    from qrcode.constants import ERROR_CORRECT_H
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_H, box_size=10, border=4)
    qr.add_data(_short_url(slug.lower()))
    qr.make(fit=True)
    return qr


@router.get("/go-links/{slug}/qr.svg")
async def go_qr_svg(slug: str):
    import qrcode.image.svg as qsvg
    qr = _qr(slug)
    img = qr.make_image(image_factory=qsvg.SvgPathFillImage)
    buf = BytesIO()
    img.save(buf)
    return Response(content=buf.getvalue(), media_type="image/svg+xml",
                    headers={"Content-Disposition": f'inline; filename="imos-qr-{slug}.svg"', "Cache-Control": "public, max-age=3600"})


@router.get("/go-links/{slug}/qr.png")
async def go_qr_png(slug: str, size: int = 2000):
    from PIL import Image
    qr = _qr(slug)
    img = qr.make_image(fill_color="#000000", back_color="#FFFFFF").convert("RGB")
    size = max(256, min(size, 4000))
    img = img.resize((size, size), Image.NEAREST)
    buf = BytesIO()
    img.save(buf, format="PNG", dpi=(300, 300))
    return Response(content=buf.getvalue(), media_type="image/png",
                    headers={"Content-Disposition": f'inline; filename="imos-qr-{slug}-{size}px.png"', "Cache-Control": "public, max-age=3600"})


# ---------------------------------------------------------------- admin: manage + stats
async def _counts(db, slug: str) -> dict:
    now = _now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week = now - timedelta(days=7)
    total = await db.go_scans.count_documents({"slug": slug})
    week_n = await db.go_scans.count_documents({"slug": slug, "scanned_at": {"$gte": week}})
    today_n = await db.go_scans.count_documents({"slug": slug, "scanned_at": {"$gte": today}})
    last = await db.go_scans.find_one({"slug": slug}, sort=[("scanned_at", -1)])
    return {"total": total, "week": week_n, "today": today_n,
            "last_scan_at": last["scanned_at"].isoformat() if last else None}


def _serialize(link: dict) -> dict:
    return {
        "slug": link["slug"], "label": link.get("label", ""), "destination": link.get("destination", ""),
        "active": link.get("active", True), "short_url": _short_url(link["slug"]),
        "qr_svg_path": f"/go-links/{link['slug']}/qr.svg", "qr_png_path": f"/go-links/{link['slug']}/qr.png",
        "created_at": link.get("created_at").isoformat() if link.get("created_at") else None,
    }


@router.get("/go-links", dependencies=[Depends(require_admin)])
async def list_go_links():
    db = get_db()
    for slug in DEFAULT_LINKS:
        await _get_or_seed(db, slug)
    links = await db.go_links.find({}).sort("created_at", 1).to_list(200)
    out = []
    for link in links:
        out.append({**_serialize(link), "scans": await _counts(db, link["slug"])})
    return {"links": out, "site_url": SITE_URL}


@router.post("/go-links", dependencies=[Depends(require_admin)])
async def upsert_go_link(data: dict = Body(...)):
    db = get_db()
    slug = str(data.get("slug", "")).lower().strip()
    destination = str(data.get("destination", "")).strip()
    label = str(data.get("label", "")).strip()[:80]
    if not SLUG_RE.match(slug):
        raise HTTPException(status_code=400, detail="Slug must be 2-40 chars: lowercase letters, numbers, hyphens")
    if not re.match(r"^https?://[^\s]+$", destination):
        raise HTTPException(status_code=400, detail="Destination must be a full http(s) URL")
    now = _now()
    await db.go_links.update_one(
        {"slug": slug},
        {"$set": {"destination": destination, "label": label, "active": True, "updated_at": now},
         "$setOnInsert": {"slug": slug, "created_at": now}},
        upsert=True,
    )
    link = await db.go_links.find_one({"slug": slug})
    return {**_serialize(link), "scans": await _counts(db, slug)}


@router.get("/go-links/{slug}/scans", dependencies=[Depends(require_admin)])
async def go_link_scans(slug: str, days: int = 30):
    db = get_db()
    days = max(1, min(days, 365))
    since = (_now() - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    pipeline = [
        {"$match": {"slug": slug.lower(), "scanned_at": {"$gte": since}}},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$scanned_at"}}, "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    days_out = [{"day": d["_id"], "count": d["count"]} async for d in db.go_scans.aggregate(pipeline)]
    plat = [{"platform": d["_id"], "count": d["count"]} async for d in db.go_scans.aggregate([
        {"$match": {"slug": slug.lower()}}, {"$group": {"_id": "$platform", "count": {"$sum": 1}}}])]
    return {"slug": slug.lower(), "days": days_out, "platforms": plat}
