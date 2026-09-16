"""Test Lab: new features land here first so the owner can try them on their own account before anyone else sees them.
A feature is `lab` (only visible inside the Test Lab, super admins) until it is flipped to `live` (everyone)."""
import asyncio
from datetime import datetime, timezone
from typing import Optional

FEATURES = [
    {"key": "voice_interview", "name": "Jessi Voice Interview", "icon": "mic",
     "tagline": "Jessi calls a rep, interviews them for about five minutes and writes their VA, bio and card from the call.",
     "description": "The rep taps Call me in My Profile (or My VA). Jessi rings their cell and asks about 10 things (what customers call them and their role, years and how they got in, "
                    "where they grew up and live, family, hobbies, why this work and why customers pick them, how they text, things they never say, a fun fact, plus one topic for the "
                    "store's industry such as what they drive), then GPT turns the transcript into their persona. The call records the rep's side only and enrolls their Voice ID so we know when it is them on recorded calls.",
     "how_to_test": ["Tap Call me and pick up. Talk like you would with a new hire, Jessi adapts to short and long answers.",
                     "Try interrupting her, asking what this is for, or saying you have to go: she should wrap up.",
                     "Hang up or let her finish. In about a minute the review opens with what she learned. In the lab NOTHING is saved to your profile until you tap Save to my profile.",
                     "Check the bio reads like you, the tone and phrases match, and the title is right. Redo as often as you like."],
     "added": "2026-09-16", "needs": "Voice ID needs PICOVOICE_ACCESS_KEY in the backend .env; until then the interview works and Voice ID shows as coming soon."},
    {"key": "industry_va", "name": "One VA for every industry", "icon": "layers",
     "tagline": "The VA stops assuming a car dealership: it speaks the store's industry and only answers specifics from a facts list the manager controls.",
     "description": "Every AI text (auto replies, follow-ups, campaign messages, suggested replies, the My VA preview) is built from four layers: the standard assistant rules, "
                    "the store's industry (words, tone, what the VA may handle itself and what always goes to the rep), who the rep is and how they text (the persona, mostly from the interview), "
                    "and FACTS: the only place the VA is allowed to get specifics like hours, what to bring, walk-ins, pricing rules or links. Managers keep the store's facts under "
                    "Things my VA may answer on the My VA screen; reps add their own. A question a fact answers gets answered (the rep gets an FYI); pricing or availability with no matching fact "
                    "still pauses the thread for the rep, using the industry's own hold words instead of car words.",
     "how_to_test": ["Open My VA. You should see Things my VA may answer with your industry at the top. Add a store fact like 'We take walk-ins weekdays until 6'.",
                     "Tap Generate Your VA's Reply on a scenario: the reply should stay in character, use your facts, and hand pricing to you.",
                     "Text your own work number from another phone: ask something a fact covers (answered, you get an FYI push) and something it does not (you get a You're Needed push).",
                     "Check nothing car-specific leaks into a non-automotive store: switch the store's industry on the admin store page and generate again."],
     "added": "2026-09-17"},
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
    from services import voice_id
    st = await statuses(db)
    out = []
    for f in FEATURES:
        s = st.get(f["key"]) or {}
        at = s.get("changed_at")
        row = {**f, "status": s.get("status") or "lab", "changed_at": at.isoformat() if hasattr(at, "isoformat") else at, "changed_by": s.get("changed_by_name")}
        if f["key"] == "voice_interview":
            reason = await asyncio.to_thread(voice_id.available)
            row["needs"] = f"Voice ID is not running on this server: {reason}" if reason else None
        out.append(row)
    return out


async def set_status(db, key: str, status: str, me: dict) -> dict:
    if key not in {f["key"] for f in FEATURES}:
        raise LookupError("Unknown feature")
    if status not in STATUSES:
        raise ValueError("status must be lab or live")
    await db.settings.update_one({"key": SETTINGS_KEY}, {"$set": {f"value.{key}": {"status": status, "changed_at": _now(), "changed_by": str(me["_id"]), "changed_by_name": me.get("name")}}}, upsert=True)
    return next(f for f in await list_features(db) if f["key"] == key)
