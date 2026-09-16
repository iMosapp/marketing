"""Test Lab: new features land here first so the owner can try them on their own account before anyone else sees them.
A feature is `lab` (only visible inside the Test Lab, super admins) until it is flipped to `live` (everyone)."""
from datetime import datetime, timezone
from typing import Optional

FEATURES = [
    {"key": "voice_interview", "name": "Jessi Voice Interview", "icon": "mic",
     "tagline": "Jessi calls a rep, interviews them for about ten minutes and writes their VA, bio and card from the call.",
     "description": "The rep taps Call me in My Profile (or My VA). Jessi rings their cell, asks about 17 things (role, years, hometown, family, hobbies, what they drive, "
                    "specialties, ideal customer, a proud story, motto, texting style, humor, go-to phrases, never-say lines, a fun fact, why pick them, greeting and sign-off), "
                    "then GPT turns the transcript into their persona. The call records the rep's side only and enrolls their Voice ID so we know when it is them on recorded calls.",
     "how_to_test": ["Tap Call me and pick up. Talk like you would with a new hire, Jessi adapts to short and long answers.",
                     "Try interrupting her, asking what this is for, or saying you have to go: she should wrap up.",
                     "Hang up or let her finish. In about a minute the review opens with what she learned. In the lab NOTHING is saved to your profile until you tap Save to my profile.",
                     "Check the bio reads like you, the tone and phrases match, and the title is right. Redo as often as you like."],
     "added": "2026-09-16", "needs": "Voice ID needs PICOVOICE_ACCESS_KEY in the backend .env; until then the interview works and Voice ID shows as coming soon."},
]
STATUSES = ("lab", "live")
SETTINGS_KEY = "lab_features"


def _now():
    return datetime.now(timezone.utc)


async def statuses(db) -> dict:
    doc = await db.settings.find_one({"key": SETTINGS_KEY}, {"value": 1})
    return (doc or {}).get("value") or {}


async def is_live(db, key: str) -> bool:
    return ((await statuses(db)).get(key) or {}).get("status") == "live"


async def visible(db, user: Optional[dict], key: str) -> bool:
    """Everyone once live; nobody outside the Test Lab before that."""
    return await is_live(db, key)


async def list_features(db) -> list:
    st = await statuses(db)
    out = []
    for f in FEATURES:
        s = st.get(f["key"]) or {}
        at = s.get("changed_at")
        out.append({**f, "status": s.get("status") or "lab", "changed_at": at.isoformat() if hasattr(at, "isoformat") else at, "changed_by": s.get("changed_by_name")})
    return out


async def set_status(db, key: str, status: str, me: dict) -> dict:
    if key not in {f["key"] for f in FEATURES}:
        raise LookupError("Unknown feature")
    if status not in STATUSES:
        raise ValueError("status must be lab or live")
    await db.settings.update_one({"key": SETTINGS_KEY}, {"$set": {f"value.{key}": {"status": status, "changed_at": _now(), "changed_by": str(me["_id"]), "changed_by_name": me.get("name")}}}, upsert=True)
    return next(f for f in await list_features(db) if f["key"] == key)
