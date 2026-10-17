"""Met-At groups: everyone a rep met at the same event (contacts.how_we_met), so a whole group can go on a campaign at once.
Always a preview first (who joins, who is skipped and why), at most MAX_BATCH people per batch, and nothing is enrolled
until the rep says yes (the campaign page button or Jessi's read-back)."""
import logging
import re
from collections import Counter
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException

from routers.database import get_data_filter

logger = logging.getLogger(__name__)

MAX_BATCH = 100
HIDDEN = ["merged", "deleted", "hidden"]
_DROP = {"the", "a", "an", "at", "in", "on", "of", "to", "from", "show", "expo", "convention", "conference", "event", "everyone", "people", "i", "we", "met"}
REASONS = {"already": "Already on this plan", "opted_out": "Texts stopped", "no_phone": "No phone number", "no_email": "No email address",
           "over_limit": f"Over the {MAX_BATCH} per batch limit. Run it again for the rest"}


def _tokens(s: str) -> list:
    words = re.findall(r"[a-z0-9]+", (s or "").lower())
    return [w for w in words if w not in _DROP] or words


def event_key(s: str) -> str:
    return " ".join(_tokens(s))


def _name(c: dict) -> str:
    return f"{c.get('first_name') or ''} {c.get('last_name') or ''}".strip() or "Unnamed"


async def _met_contacts(db, user_id: str) -> list:
    return await db.contacts.find(
        {"user_id": user_id, "status": {"$nin": HIDDEN}, "how_we_met.event": {"$nin": [None, ""]}},
        {"first_name": 1, "last_name": 1, "phone": 1, "email": 1, "opted_out": 1, "sms_opt_out": 1, "how_we_met": 1},
    ).to_list(5000)


async def events(db, user_id: str) -> list:
    """The rep's own contacts grouped by where they met, biggest group first."""
    groups: dict = {}
    for c in await _met_contacts(db, user_id):
        m = c.get("how_we_met") or {}
        k = event_key(m.get("event") or "")
        if not k:
            continue
        g = groups.setdefault(k, {"key": k, "labels": Counter(), "count": 0, "last": ""})
        g["labels"][m["event"].strip()] += 1
        g["count"] += 1
        g["last"] = max(g["last"], str(m.get("date") or ""))
    out = [{"key": g["key"], "label": g["labels"].most_common(1)[0][0], "count": g["count"], "last_date": g["last"] or None} for g in groups.values()]
    return sorted(out, key=lambda e: (-e["count"], e["label"].lower()))[:60]


def _channels(campaign: dict) -> tuple:
    steps = campaign.get("sequences") or campaign.get("steps") or []
    chans = {str(s.get("channel") or "sms").lower() for s in steps} or {"sms"}
    email_only = chans == {"email"}
    return (not email_only), email_only


async def _campaign(db, user_id: str, campaign_id: str) -> dict:
    if not ObjectId.is_valid(str(campaign_id or "")):
        raise HTTPException(status_code=404, detail="Campaign not found")
    c = await db.campaigns.find_one({"$and": [{"_id": ObjectId(campaign_id)}, await get_data_filter(user_id)]}, {"name": 1, "active": 1, "sequences": 1, "steps": 1})
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return c


async def preview(db, user_id: str, campaign_id: str, query: str) -> dict:
    """Who would join, and who is skipped with the reason. Matching: every word of the ask appears in where (or the city) they met."""
    from services import suppression
    camp = await _campaign(db, user_id, campaign_id)
    want = set(_tokens(query))
    if not want:
        raise HTTPException(status_code=400, detail="Say where you met them, like NADA or the golf tournament")
    matched = []
    for c in await _met_contacts(db, user_id):
        m = c.get("how_we_met") or {}
        if want <= set(_tokens(m.get("event") or "")) | set(_tokens(m.get("place") or "")):
            matched.append(c)
    ids = [str(c["_id"]) for c in matched]
    on_plan = set(await db.campaign_enrollments.distinct("contact_id", {"campaign_id": str(camp["_id"]), "contact_id": {"$in": ids}, "status": {"$in": ["active", "paused"]}})) if ids else set()
    me = await db.users.find_one({"_id": ObjectId(user_id)}, {"org_id": 1}) if ObjectId.is_valid(user_id) else None
    org = (me or {}).get("org_id")
    need_phone, need_email = _channels(camp)
    people, ok = [], 0
    for c in sorted(matched, key=lambda x: _name(x).lower()):
        cid, phone = str(c["_id"]), c.get("phone") or ""
        if cid in on_plan:
            st = "already"
        elif need_phone and not phone:
            st = "no_phone"
        elif need_email and not c.get("email"):
            st = "no_email"
        elif need_phone and (c.get("opted_out") or c.get("sms_opt_out") or await suppression.active(db, phone, org)):
            st = "opted_out"
        elif ok >= MAX_BATCH:
            st = "over_limit"
        else:
            st, ok = "ok", ok + 1
        people.append({"id": cid, "name": _name(c), "first": c.get("first_name") or "", "phone": phone, "met": (c.get("how_we_met") or {}).get("summary") or "",
                       "status": st, "reason": REASONS.get(st, "")})
    people.sort(key=lambda p: (p["status"] != "ok", p["name"].lower()))
    labels = Counter(((c.get("how_we_met") or {}).get("event") or "").strip() for c in matched)
    counts = Counter(p["status"] for p in people)
    return {"campaign": {"id": str(camp["_id"]), "name": camp.get("name") or "this plan", "active": bool(camp.get("active"))},
            "event": labels.most_common(1)[0][0] if labels else query.strip(), "query": query.strip(), "matched": len(people),
            "counts": {k: counts.get(k, 0) for k in ("ok", "already", "opted_out", "no_phone", "no_email", "over_limit")},
            "ok_ids": [p["id"] for p in people if p["status"] == "ok"], "people": people, "limit": MAX_BATCH}


def skipped_line(counts: dict) -> str:
    """'2 are already on it, 1 has texts stopped.' (empty when nobody is skipped)"""
    bits = []
    for k, one, many in (("already", "is already on it", "are already on it"), ("opted_out", "has texts stopped", "have texts stopped"),
                         ("no_phone", "has no phone number", "have no phone number"), ("no_email", "has no email", "have no email"),
                         ("over_limit", f"is over the {MAX_BATCH} limit for now", f"are over the {MAX_BATCH} limit for now")):
        n = counts.get(k) or 0
        if n:
            bits.append(f"{n} {one if n == 1 else many}")
    return (", ".join(bits) + ".") if bits else ""


async def enroll(db, user_id: str, campaign_id: str, query: str, contact_ids: Optional[list] = None) -> dict:
    """Re-checks the preview, then enrolls only people it still clears (at most MAX_BATCH), one by one through the normal enroll."""
    from routers.campaigns import enroll_contact_in_campaign
    pv = await preview(db, user_id, campaign_id, query)
    if not pv["campaign"]["active"]:
        raise HTTPException(status_code=400, detail=f"{pv['campaign']['name']} is turned off. Turn it on first.")
    ok = set(pv["ok_ids"])
    chosen = [c for c in dict.fromkeys(contact_ids if contact_ids is not None else pv["ok_ids"]) if c in ok][:MAX_BATCH]
    enrolled, failed = [], []
    for cid in chosen:
        try:
            await enroll_contact_in_campaign(user_id, campaign_id, cid)
            enrolled.append(cid)
        except HTTPException as e:
            failed.append({"id": cid, "reason": str(e.detail)})
        except Exception as e:
            logger.warning(f"[MetAt] enroll {cid} failed: {e}")
            failed.append({"id": cid, "reason": "Could not enroll"})
    logger.info(f"[MetAt] {user_id} put {len(enrolled)} met at '{pv['event']}' on campaign {campaign_id} ({len(failed)} failed)")
    return {"campaign": pv["campaign"], "event": pv["event"], "enrolled": len(enrolled), "enrolled_ids": enrolled, "failed": failed,
            "skipped": {k: v for k, v in pv["counts"].items() if k != "ok"}}
