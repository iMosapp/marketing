"""Wallet passes — Apple Wallet (.pkpass) and Google Wallet (save link) for the rep's digital card QR."""
import os
import io
import json
import base64
import hashlib
import logging
import secrets as pysecrets
import zipfile
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from bson import ObjectId

from routers.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/wallet", tags=["Wallet Passes"])

APP_URL = (os.environ.get("APP_URL") or "https://app.imonsocial.com").strip('"').rstrip("/")
ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")


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
    return user


def _user_display(user: dict):
    name = user.get("name") or user.get("email") or "My Card"
    title = user.get("title") or (user.get("persona") or {}).get("title") or ""
    org = user.get("store_name") or "i'M On Social"
    card_url = f"{APP_URL}/card/{str(user['_id'])}"
    return name, title, org, card_url


def _build_pkpass(user: dict) -> bytes:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.serialization import Encoding, pkcs7, pkcs12

    p12_bytes = _env_bytes("APPLE_PASS_P12_B64", "APPLE_PASS_P12_PATH")
    pwd = os.environ.get("APPLE_PASS_P12_PASSWORD", "")
    key, cert, _extra = pkcs12.load_key_and_certificates(p12_bytes, pwd.encode() if pwd else None)
    wwdr = x509.load_pem_x509_certificate(_env_bytes("APPLE_WWDR_PEM_B64", "APPLE_WWDR_PEM_PATH"))

    name, title, org, card_url = _user_display(user)
    pass_json = {
        "formatVersion": 1,
        "passTypeIdentifier": os.environ["APPLE_PASS_TYPE_ID"],
        "serialNumber": str(user["_id"]),
        "teamIdentifier": os.environ["APPLE_TEAM_ID"],
        "organizationName": org,
        "description": f"{name} — Digital Business Card",
        "logoText": org,
        "foregroundColor": "rgb(255,255,255)",
        "backgroundColor": "rgb(18,18,20)",
        "labelColor": "rgb(201,169,98)",
        "generic": {
            "primaryFields": [{"key": "name", "label": "", "value": name}],
            "secondaryFields": ([{"key": "title", "label": "TITLE", "value": title}] if title else []),
            "backFields": [{"key": "url", "label": "My Digital Card", "value": card_url}],
        },
        "barcodes": [{
            "format": "PKBarcodeFormatQR",
            "message": card_url,
            "messageEncoding": "iso-8859-1",
            "altText": "Scan to open my card",
        }],
    }

    files = {"pass.json": json.dumps(pass_json, separators=(",", ":")).encode()}
    for fname, asset in (("icon.png", "wallet_icon.png"), ("icon@2x.png", "wallet_icon@2x.png")):
        path = os.path.join(ASSETS_DIR, asset)
        if os.path.exists(path):
            with open(path, "rb") as f:
                files[fname] = f.read()

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
        raise HTTPException(status_code=404, detail="Link expired — generate a new pass from the app")
    exp = doc.get("expires_at")
    if exp and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if not exp or exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=404, detail="Link expired — generate a new pass from the app")
    if not apple_configured():
        raise HTTPException(status_code=503, detail="Apple Wallet is not configured yet")
    user = await _load_user(doc["user_id"])
    try:
        pkpass = _build_pkpass(user)
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


@router.get("/{user_id}/google-save-url")
async def google_save_url(user_id: str):
    if not google_configured():
        raise HTTPException(status_code=503, detail="Google Wallet is not configured yet")
    user = await _load_user(user_id)
    name, title, org, card_url = _user_display(user)

    import jwt as pyjwt
    sa = json.loads(_env_bytes("GOOGLE_WALLET_SA_JSON_B64", "GOOGLE_WALLET_SA_JSON_PATH"))
    issuer = os.environ["GOOGLE_WALLET_ISSUER_ID"]
    suffix = hashlib.sha256(str(user["_id"]).encode()).hexdigest()[:32]

    payload = {
        "genericClasses": [{
            "id": f"{issuer}.imos-digital-card",
            "issuerName": org,
            "reviewStatus": "UNDER_REVIEW",
        }],
        "genericObjects": [{
            "id": f"{issuer}.{suffix}",
            "classId": f"{issuer}.imos-digital-card",
            "state": "ACTIVE",
            "cardTitle": {"defaultValue": {"language": "en-US", "value": "Digital Business Card"}},
            "header": {"defaultValue": {"language": "en-US", "value": name}},
            "textModulesData": ([{"id": "title", "header": "Title", "body": title}] if title else []),
            "barcode": {"type": "QR_CODE", "value": card_url},
            "linksModuleData": {"uris": [{"uri": card_url, "description": "Open my card"}]},
            "hexBackgroundColor": "#121214",
        }],
    }
    token = pyjwt.encode(
        {
            "iss": sa["client_email"],
            "aud": "google",
            "typ": "savetowallet",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "origins": [APP_URL],
            "payload": payload,
        },
        sa["private_key"],
        algorithm="RS256",
    )
    return {"save_url": f"https://pay.google.com/gp/v/save/{token}"}
