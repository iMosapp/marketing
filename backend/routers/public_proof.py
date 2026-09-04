"""Public, token-based proof page for prospects. No auth. Token lives on stores.proof_share."""
from datetime import datetime, timezone
from fastapi import APIRouter, Request
from routers.database import get_db

router = APIRouter(prefix="/public/proof", tags=["Public Proof"])


@router.get("/{token}")
async def public_proof(token: str, request: Request, days: int = 90):
    from routers.lead_intake import public_proof_payload
    db = get_db()
    payload = await public_proof_payload(db, token, days)
    await db.stores.update_one({"proof_share.token": token}, {"$inc": {"proof_share.views": 1}, "$set": {"proof_share.last_viewed_at": datetime.now(timezone.utc)}})
    return payload


@router.get("/{token}/card.png")
async def public_proof_card(token: str, days: int = 90, theme: str = "dark", format: str = "portrait"):
    from routers.lead_intake import public_proof_payload, proof_png_response
    db = get_db()
    payload = await public_proof_payload(db, token, days)
    return proof_png_response(payload, payload.get("store_name", ""), theme, format)
