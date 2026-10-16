"""How we met: the event, place and date where the rep met a contact. Jessi fills it once from a voice note, the notes or a contact
she created; the rep can edit it, and a rep's own entry is never overwritten by Jessi."""
import re
from datetime import datetime, timezone

from bson import ObjectId

FIELDS = ("event", "place", "date")


def _date(v) -> str:
    """YYYY-MM-DD or YYYY-MM; anything else (words like 'last spring') is dropped rather than guessed."""
    m = re.match(r"^(\d{4})-(\d{2})(?:-(\d{2}))?", str(v or "").strip())
    return m.group(0) if m else ""


def clean(met: dict) -> dict:
    met = met or {}
    return {"event": str(met.get("event") or "").strip()[:80], "place": str(met.get("place") or "").strip()[:80], "date": _date(met.get("date"))}


def line(met: dict) -> str:
    """'At NADA in Las Vegas, Feb 12, 2026'."""
    m = clean(met)
    bits = []
    if m["event"]:
        bits.append(m["event"] if re.match(r"(?i)^(at|in|on|through|via|from|when|while)\b", m["event"]) else f"At {m['event']}")
    if m["place"]:
        bits.append(f"in {m['place']}" if bits else f"In {m['place']}")
    out = " ".join(bits)
    if m["date"]:
        fmt = "%b %-d, %Y" if len(m["date"]) == 10 else "%b %Y"
        when = datetime.strptime(m["date"], "%Y-%m-%d" if len(m["date"]) == 10 else "%Y-%m").strftime(fmt)
        out = f"{out}, {when}" if out else f"Met {when}"
    return out


def _doc(met: dict, source: str, ref: str = "") -> dict:
    m = clean(met)
    return {**m, "summary": line(m), "source": source, "source_ref": ref, "updated_at": datetime.now(timezone.utc)}


async def fill(db, contact_id: str, met: dict, source: str, ref: str = "") -> bool:
    """Jessi's capture: only when nothing is on file yet (the first time they met is the one worth keeping)."""
    m = clean(met)
    if not (m["event"] or m["place"]) or not ObjectId.is_valid(str(contact_id)):
        return False
    empty = {"$or": [{"how_we_met": {"$exists": False}}, {"how_we_met": None}, {"how_we_met.summary": {"$in": ["", None]}}]}
    r = await db.contacts.update_one({"$and": [{"_id": ObjectId(str(contact_id))}, empty]}, {"$set": {"how_we_met": _doc(m, source, ref)}})
    return r.modified_count > 0


async def set_by_rep(db, contact_id: str, met: dict) -> dict:
    """The rep's edit always wins; clearing every field removes it."""
    m = clean(met)
    if not any(m.values()):
        await db.contacts.update_one({"_id": ObjectId(str(contact_id))}, {"$unset": {"how_we_met": ""}})
        return {}
    doc = _doc(m, "rep")
    await db.contacts.update_one({"_id": ObjectId(str(contact_id))}, {"$set": {"how_we_met": doc}})
    return doc


def public(h) -> dict:
    if not isinstance(h, dict) or not h.get("summary"):
        return {}
    return {**clean(h), "summary": h["summary"], "source": h.get("source") or ""}
