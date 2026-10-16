"""Customer Preview Trio: one campaign step written for three real customers side by side, from what Jessi knows about each.
Examples only: nothing is saved or sent. The real text is written fresh, by the same writer, when the touch is due; each preview is
written in the voice of the rep who owns that customer, exactly as the sender does."""
import asyncio
import logging
import re

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from routers.database import get_data_filter, get_db

router = APIRouter(prefix="/campaign-preview", tags=["Campaign preview"])
logger = logging.getLogger(__name__)

POOL = 80
DETAIL_KEYS = [("spouse_name", "Spouse"), ("kids", "Kids"), ("interests", "Into"), ("hobbies", "Hobbies"), ("pets", "Pets"),
               ("purchase_context", "What matters to them"), ("trade_in", "Trade-in"), ("neighborhood", "Lives in"), ("occupation", "Works as")]
_STOP = {"with", "that", "this", "from", "your", "have", "they", "their", "about", "just", "into", "what", "matters"}


class PreviewBody(BaseModel):
    contact_ids: list
    step_context: str = ""
    message_template: str = ""
    channel: str = "sms"
    ai_enabled: bool = True


async def _campaign(db, user_id: str, campaign_id: str) -> dict:
    if not ObjectId.is_valid(campaign_id):
        raise HTTPException(status_code=404, detail="Campaign not found")
    c = await db.campaigns.find_one({"$and": [{"_id": ObjectId(campaign_id)}, await get_data_filter(user_id)]}, {"name": 1, "ai_enabled": 1})
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return c


def _vehicle(c: dict) -> str:
    ph = [p for p in c.get("purchase_history") or [] if isinstance(p, dict) and p.get("title")]
    if ph:
        return sorted(ph, key=lambda p: str(p.get("date") or ""))[-1]["title"]
    return c.get("vehicle_purchased") or c.get("vehicle") or (c.get("personal_details") or {}).get("vehicle_purchased") or ""


def _make(v: str) -> str:
    words = [w for w in (v or "").lower().split() if not w.isdigit()]
    return words[0] if words else ""


def _details(c: dict) -> list:
    pd, out = c.get("personal_details") or {}, []
    for k, label in DETAIL_KEYS:
        v = pd.get(k)
        if isinstance(v, list):
            v = ", ".join(str(x.get("name") if isinstance(x, dict) else x) for x in v[:3] if x)
        if v:
            out.append(f"{label}: {str(v)[:60]}")
    return out


async def _counts(db, coll: str, ids: list) -> dict:
    return {r["_id"]: r["n"] async for r in db[coll].aggregate([{"$match": {"contact_id": {"$in": ids}}}, {"$group": {"_id": "$contact_id", "n": {"$sum": 1}}}])}


async def _signals(db, contacts: list) -> list:
    ids = [str(c["_id"]) for c in contacts]
    memos, msgs = await _counts(db, "voice_notes", ids), await _counts(db, "messages", ids)
    rows = []
    for c in contacts:
        cid, veh, det = str(c["_id"]), _vehicle(c), _details(c)
        m, t = memos.get(cid, 0), msgs.get(cid, 0)
        rows.append({"c": c, "vehicle": veh, "memos": m, "messages": t, "details": len(det),
                     "score": 3 * m + 2 * len(det) + min(t, 30) / 3 + (2 if veh else 0) + (1 if c.get("notes") else 0)})
    return rows


def pick_trio(rows: list) -> list:
    """The richest history, then a different vehicle / situation, then the thinnest history: three customers who should get three different texts."""
    rows = sorted(rows, key=lambda r: -r["score"])
    if not rows:
        return []
    a, rest = rows[0], rows[1:]
    b = next((r for r in rest if r["vehicle"] and _make(r["vehicle"]) != _make(a["vehicle"])), None) or (rest[0] if rest else None)
    rest = [r for r in rest if r is not b]
    c = min(rest, key=lambda r: r["score"]) if rest else None
    return [(r, why) for r, why in ((a, "Most history"), (b, "A different situation"), (c, "Little history")) if r]


def _card(r: dict, why: str = "") -> dict:
    c = r["c"]
    return {"id": str(c["_id"]), "name": f"{c.get('first_name') or ''} {c.get('last_name') or ''}".strip() or c.get("phone") or "Customer",
            "why": why, "vehicle": r["vehicle"], "memos": r["memos"], "messages": r["messages"], "details": r["details"]}


@router.get("/{user_id}/{campaign_id}/candidates")
async def candidates(user_id: str, campaign_id: str):
    """Three of your customers with the most different histories (people already in this plan first)."""
    db = get_db()
    await _campaign(db, user_id, campaign_id)
    scope = await get_data_filter(user_id)
    proj = {"first_name": 1, "last_name": 1, "phone": 1, "notes": 1, "vehicle": 1, "vehicle_purchased": 1, "purchase_history": 1, "personal_details": 1}
    live = {"first_name": {"$nin": ["", None]}, "status": {"$nin": ["deleted", "merged", "hidden"]}}
    enrolled = [ObjectId(e["contact_id"]) async for e in db.campaign_enrollments.find({"campaign_id": campaign_id}, {"contact_id": 1}).limit(40) if ObjectId.is_valid(str(e.get("contact_id")))]
    pool = await db.contacts.find({"$and": [scope, live, {"_id": {"$in": enrolled}}]}, proj).to_list(40) if enrolled else []
    seen = {c["_id"] for c in pool}
    mine = {"user_id": user_id} if await db.contacts.find_one({"user_id": user_id}, {"_id": 1}) else scope
    async for c in db.contacts.find({"$and": [mine, live]}, proj).sort("updated_at", -1).limit(POOL):
        if c["_id"] not in seen and len(pool) < POOL:
            pool.append(c)
    return {"contacts": [_card(r, why) for r, why in pick_trio(await _signals(db, pool))]}


def _knew(c: dict, memos: int, last_msg: dict) -> list:
    out = []
    veh = _vehicle(c)
    if veh:
        out.append(f"Bought: {veh}")
    out += _details(c)
    if memos:
        out.append(f"{memos} voice memo{'s' if memos != 1 else ''}")
    if last_msg and last_msg.get("content"):
        who = "They texted" if last_msg.get("sender") == "contact" else "You texted"
        out.append(f"{who}: “{str(last_msg['content'])[:70]}”")
    return out[:7] or ["Nothing on file yet"]


def _used(knew: list, message: str) -> list:
    """What the text visibly draws on: an item counts when one of its words is in the message (each word credits one item only)."""
    words, out = set(re.findall(r"[a-z0-9']{4,}", (message or "").lower())) - _STOP, []
    for k in knew:
        hit = words & (set(re.findall(r"[a-z0-9']{4,}", k.lower().split(":", 1)[-1])) - _STOP)
        if hit:
            out.append(k)
            words -= hit
    return out


async def _one(db, user_id: str, cid: str, body: PreviewBody, campaign_name: str, ai: bool) -> dict:
    scope = await get_data_filter(user_id)
    c = await db.contacts.find_one({"$and": [{"_id": ObjectId(cid)}, scope]}) if ObjectId.is_valid(cid) else None
    if not c:
        return {"contact_id": cid, "error": "Not one of your customers"}
    owner = str(c.get("user_id") or user_id)
    memos = await db.voice_notes.count_documents({"contact_id": cid})
    last = await db.messages.find_one({"contact_id": cid, "content": {"$nin": ["", None]}}, {"content": 1, "sender": 1}, sort=[("timestamp", -1)])
    knew = _knew(c, memos, last)
    name = f"{c.get('first_name') or ''} {c.get('last_name') or ''}".strip()
    out = {"contact_id": cid, "name": name, "knew": knew, "ai": ai, "message": "", "used": [], "error": ""}
    if ai:
        from routers.ai_campaigns import generate_campaign_message
        from services.campaign_reliability import generate
        text, err = await generate(lambda: generate_campaign_message(owner, cid, {"step_context": body.step_context or "a genuine check-in", "channel": body.channel,
                                                                                    "campaign_name": campaign_name, "template_hint": body.message_template}))
        if not text:
            logger.warning(f"[CampaignPreview] writer failed for {cid}: {err}")
            out["error"] = "Jessi couldn't write this one right now. Try again in a minute."
            return out
    from scheduler import resolve_template_variables   # the sender fills {fields} after writing too
    text = await resolve_template_variables(db, text if ai else body.message_template or "", c, owner)
    out.update(message=text, used=_used(knew, text))
    return out


@router.post("/{user_id}/{campaign_id}")
async def preview(user_id: str, campaign_id: str, body: PreviewBody):
    """Write one step for up to three customers at once. Nothing is stored or sent."""
    db = get_db()
    camp = await _campaign(db, user_id, campaign_id)
    ids = [str(x) for x in body.contact_ids if isinstance(x, str)][:3]
    if not ids:
        raise HTTPException(status_code=400, detail="Pick at least one customer")
    rows = await asyncio.gather(*[_one(db, user_id, cid, body, camp.get("name") or "", body.ai_enabled) for cid in ids])
    return {"campaign_name": camp.get("name") or "", "ai": body.ai_enabled, "previews": rows}
