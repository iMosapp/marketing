"""Wallet passes: Apple Wallet (.pkpass) and Google Wallet (save link) for the rep's digital card."""
import os
import io
import json
import base64
import hashlib
import logging
import asyncio
import secrets as pysecrets
import zipfile
from datetime import datetime, timezone, timedelta

import requests
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from bson import ObjectId
from PIL import Image

from routers.database import get_db
from utils.image_urls import resolve_user_photo, resolve_store_logo
from utils.image_storage import get_object
from utils.text_sanitize import format_phone_display

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/wallet", tags=["Wallet Passes"])

APP_URL = (os.environ.get("APP_URL") or "https://app.imonsocial.com").strip('"').rstrip("/")
ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
FALLBACK_LOGO = os.path.join(ASSETS_DIR, "wallet_logo.png")

THUMB_PT = 90          # Apple generic pass thumbnail is 90x90 pt
LOGO_MAX_PT = (160, 50)


def _env_bytes(b64_key: str, path_key: str):
    b64 = os.environ.get(b64_key, "")
    if b64:
        try:
            return base64.b64decode(b64)
        except Exception:
            return None
    p = os.environ.get(path_key, "")
    if p and os.path.exists(p):
        with open(p, "rb") as f:
            return f.read()
    return None


def apple_configured() -> bool:
    return bool(
        os.environ.get("APPLE_TEAM_ID")
        and os.environ.get("APPLE_PASS_TYPE_ID")
        and _env_bytes("APPLE_PASS_P12_B64", "APPLE_PASS_P12_PATH")
        and _env_bytes("APPLE_WWDR_PEM_B64", "APPLE_WWDR_PEM_PATH")
    )


def google_configured() -> bool:
    return bool(
        os.environ.get("GOOGLE_WALLET_ISSUER_ID")
        and _env_bytes("GOOGLE_WALLET_SA_JSON_B64", "GOOGLE_WALLET_SA_JSON_PATH")
    )


async def _load_user(user_id: str) -> dict:
    db = get_db()
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)}, {"password": 0})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user id")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    store = None
    if user.get("store_id") and ObjectId.is_valid(str(user["store_id"])):
        store = await db.stores.find_one({"_id": ObjectId(str(user["store_id"]))},
                                         {"name": 1, "logo_path": 1, "logo_avatar_path": 1, "logo_url": 1})
    user["_store"] = store or {}
    return user


def _card(user: dict) -> dict:
    """Everything the pass shows, resolved the same way the public /card page does it."""
    store = user.get("_store") or {}
    phone = user.get("mvpline_number") or user.get("twilio_number") or user.get("phone") or ""
    digits = "".join(ch for ch in phone if ch.isdigit())
    if digits and len(digits) == 10:
        digits = "1" + digits
    return {
        "name": user.get("name") or user.get("email") or "My Card",
        "title": (user.get("persona") or {}).get("title") or user.get("title") or "",
        "org": store.get("name") or user.get("store_name") or user.get("company") or "i'M On Social",
        "card_url": f"{APP_URL}/card/{str(user['_id'])}",
        "phone_e164": f"+{digits}" if digits else "",
        "phone_pretty": format_phone_display(phone) if phone else "",
        "email": user.get("email") or "",
        "photo": resolve_user_photo(user),
        "logo": resolve_store_logo(store),
    }


def _absolute(ref: str | None) -> str | None:
    if not ref:
        return None
    return ref if ref.startswith("http") else f"{APP_URL}{ref}"


def _fetch_image(ref: str | None, min_px: int = 40) -> Image.Image | None:
    if not ref:
        return None
    try:
        if ref.startswith("/api/images/"):
            data, _ct = get_object(ref[len("/api/images/"):])
        elif ref.startswith("http"):
            r = requests.get(ref, timeout=8)
            r.raise_for_status()
            data = r.content
        else:
            return None
        img = Image.open(io.BytesIO(data)).convert("RGBA")
        if min(img.size) < min_px:
            return None
        return img
    except Exception as e:
        logger.info(f"wallet image skipped ({ref[:60]}): {e}")
        return None


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _thumbnails(img: Image.Image) -> dict:
    """Center-square crop at 1x/2x/3x."""
    side = min(img.size)
    left, top = (img.width - side) // 2, (img.height - side) // 2
    sq = img.crop((left, top, left + side, top + side))
    return {f"thumbnail{s}.png": _png(sq.resize((THUMB_PT * n, THUMB_PT * n), Image.LANCZOS))
            for s, n in (("", 1), ("@2x", 2), ("@3x", 3))}


def _logos(img: Image.Image) -> dict:
    """Fit inside 160x50 pt keeping the aspect ratio, at 1x/2x/3x."""
    out = {}
    for s, n in (("", 1), ("@2x", 2), ("@3x", 3)):
        max_w, max_h = LOGO_MAX_PT[0] * n, LOGO_MAX_PT[1] * n
        scale = min(max_w / img.width, max_h / img.height)
        size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
        out[f"logo{s}.png"] = _png(img.resize(size, Image.LANCZOS))
    return out


def _back_fields(c: dict) -> list:
    fields = []
    if c["phone_e164"]:
        fields.append({"key": "text", "label": "TEXT ME", "value": c["phone_pretty"],
                       "attributedValue": f"<a href='sms:{c['phone_e164']}'>{c['phone_pretty']}</a>"})
        fields.append({"key": "call", "label": "CALL ME", "value": c["phone_pretty"],
                       "attributedValue": f"<a href='tel:{c['phone_e164']}'>{c['phone_pretty']}</a>"})
    if c["email"]:
        fields.append({"key": "email", "label": "EMAIL", "value": c["email"],
                       "attributedValue": f"<a href='mailto:{c['email']}'>{c['email']}</a>"})
    fields.append({"key": "url", "label": "MY DIGITAL CARD", "value": c["card_url"]})
    fields.append({"key": "about", "label": "", "value": f"Scan the QR on the front to open {c['name'].split()[0]}'s card, save the contact and text directly."})
    return fields


def _build_pkpass(user: dict) -> bytes:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.serialization import Encoding, pkcs7, pkcs12

    p12_bytes = _env_bytes("APPLE_PASS_P12_B64", "APPLE_PASS_P12_PATH")
    pwd = os.environ.get("APPLE_PASS_P12_PASSWORD", "")
    key, cert, _extra = pkcs12.load_key_and_certificates(p12_bytes, pwd.encode() if pwd else None)
    wwdr = x509.load_pem_x509_certificate(_env_bytes("APPLE_WWDR_PEM_B64", "APPLE_WWDR_PEM_PATH"))

    c = _card(user)
    secondary = []
    if c["title"]:
        secondary.append({"key": "title", "label": "TITLE", "value": c["title"]})
    secondary.append({"key": "org", "label": "STORE", "value": c["org"]})
    pass_json = {
        "formatVersion": 1,
        "passTypeIdentifier": os.environ["APPLE_PASS_TYPE_ID"],
        "serialNumber": str(user["_id"]),
        "teamIdentifier": os.environ["APPLE_TEAM_ID"],
        "organizationName": c["org"],
        "description": f"{c['name']}, Digital Business Card",
        "logoText": c["org"],
        "foregroundColor": "rgb(255,255,255)",
        "backgroundColor": "rgb(18,18,20)",
        "labelColor": "rgb(201,169,98)",
        "generic": {
            "primaryFields": [{"key": "name", "label": "", "value": c["name"]}],
            "secondaryFields": secondary,
            "backFields": _back_fields(c),
        },
        "barcodes": [{
            "format": "PKBarcodeFormatQR",
            "message": c["card_url"],
            "messageEncoding": "iso-8859-1",
            "altText": "Scan to open my card",
        }],
    }

    files = {"pass.json": json.dumps(pass_json, separators=(",", ":")).encode()}
    for fname, asset in (("icon.png", "wallet_icon.png"), ("icon@2x.png", "wallet_icon@2x.png"),
                         ("icon@3x.png", "wallet_icon@3x.png")):
        path = os.path.join(ASSETS_DIR, asset)
        if os.path.exists(path):
            with open(path, "rb") as f:
                files[fname] = f.read()
    logo = _fetch_image(c["logo"]) or (Image.open(FALLBACK_LOGO).convert("RGBA") if os.path.exists(FALLBACK_LOGO) else None)
    if logo is not None:
        files.update(_logos(logo))
    photo = _fetch_image(c["photo"])
    if photo is not None:
        files.update(_thumbnails(photo))

    manifest = json.dumps(
        {k: hashlib.sha1(v).hexdigest() for k, v in files.items()}, separators=(",", ":")
    ).encode()

    signature = (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(manifest)
        .add_signer(cert, key, hashes.SHA256())
        .add_certificate(wwdr)
        .sign(Encoding.DER, [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary])
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for k, v in files.items():
            z.writestr(k, v)
        z.writestr("manifest.json", manifest)
        z.writestr("signature", signature)
    return buf.getvalue()


@router.get("/{user_id}/status")
async def wallet_status(user_id: str):
    return {"apple": apple_configured(), "google": google_configured()}


@router.post("/{user_id}/download-token")
async def create_download_token(user_id: str):
    """Short-lived public download token so Safari/Wallet can fetch the pass without a Bearer header."""
    if not apple_configured():
        raise HTTPException(status_code=503, detail="Apple Wallet is not configured yet")
    await _load_user(user_id)
    db = get_db()
    token = pysecrets.token_urlsafe(24)
    await db.wallet_pass_tokens.insert_one({
        "token": token,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
    })
    return {"token": token}


@router.get("/download/{token}.pkpass")
async def download_pass(token: str):
    db = get_db()
    doc = await db.wallet_pass_tokens.find_one({"token": token})
    if not doc:
        raise HTTPException(status_code=404, detail="Link expired, generate a new pass from the app")
    exp = doc.get("expires_at")
    if exp and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if not exp or exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=404, detail="Link expired, generate a new pass from the app")
    if not apple_configured():
        raise HTTPException(status_code=503, detail="Apple Wallet is not configured yet")
    user = await _load_user(doc["user_id"])
    try:
        pkpass = await asyncio.to_thread(_build_pkpass, user)
    except Exception as e:
        logger.error(f"pkpass build failed: {e}")
        raise HTTPException(status_code=500, detail="Could not build wallet pass")
    return Response(
        content=pkpass,
        media_type="application/vnd.apple.pkpass",
        headers={
            "Content-Disposition": 'attachment; filename="digital-card.pkpass"',
            "Cache-Control": "no-store",
        },
    )


def _google_payload(user: dict, issuer: str) -> dict:
    c = _card(user)
    suffix = hashlib.sha256(str(user["_id"]).encode()).hexdigest()[:32]
    links = []
    if c["phone_e164"]:
        links.append({"uri": f"tel:{c['phone_e164']}", "description": f"Call {c['phone_pretty']}"})
    if c["email"]:
        links.append({"uri": f"mailto:{c['email']}", "description": "Email me"})
    links.append({"uri": c["card_url"], "description": "Open my card"})
    text_modules = [{"id": "title", "header": "Title", "body": c["title"]}] if c["title"] else []
    if c["phone_pretty"]:
        text_modules.append({"id": "text", "header": "Text me", "body": c["phone_pretty"]})
    obj = {
        "id": f"{issuer}.{suffix}",
        "classId": f"{issuer}.imos-digital-card",
        "state": "ACTIVE",
        "cardTitle": {"defaultValue": {"language": "en-US", "value": c["org"]}},
        "header": {"defaultValue": {"language": "en-US", "value": c["name"]}},
        "subheader": {"defaultValue": {"language": "en-US", "value": c["title"] or "Digital Business Card"}},
        "logo": {"sourceUri": {"uri": _absolute(c["logo"]) or f"{APP_URL}/api/public/shop-contact/logo.png"}},
        "textModulesData": text_modules,
        "barcode": {"type": "QR_CODE", "value": c["card_url"], "alternateText": "Scan to open my card"},
        "linksModuleData": {"uris": links},
        "hexBackgroundColor": "#121214",
    }
    if c["photo"]:
        obj["imageModulesData"] = [{"id": "photo", "mainImage": {"sourceUri": {"uri": _absolute(c["photo"])}}}]
    return {
        "genericClasses": [{"id": f"{issuer}.imos-digital-card", "issuerName": c["org"], "reviewStatus": "UNDER_REVIEW"}],
        "genericObjects": [obj],
    }


@router.get("/{user_id}/google-save-url")
async def google_save_url(user_id: str):
    if not google_configured():
        raise HTTPException(status_code=503, detail="Google Wallet is not configured yet")
    user = await _load_user(user_id)

    import jwt as pyjwt
    sa = json.loads(_env_bytes("GOOGLE_WALLET_SA_JSON_B64", "GOOGLE_WALLET_SA_JSON_PATH"))
    issuer = os.environ["GOOGLE_WALLET_ISSUER_ID"]
    token = pyjwt.encode(
        {
            "iss": sa["client_email"],
            "aud": "google",
            "typ": "savetowallet",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "origins": [APP_URL],
            "payload": _google_payload(user, issuer),
        },
        sa["private_key"],
        algorithm="RS256",
    )
    return {"save_url": f"https://pay.google.com/gp/v/save/{token}"}
