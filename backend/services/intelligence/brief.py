"""Dynamic Relationship Brief: who, what is happening now, what changed, what to discuss, what should happen next, what needs verification. Computed from facts; refreshes when facts change."""
from services.intelligence import config, next_action, state


async def build(db, contact: dict, now=None) -> dict:
    settings = await config.settings(db, contact.get("store_id"))
    st = await state.build(db, contact, settings, now)
    rec = next_action.recommend(contact, st, now)
    name = " ".join(x for x in (contact.get("first_name"), contact.get("last_name")) if x).strip() or contact.get("full_name") or "Customer"
    return {
        "contact_id": st["contact_id"], "as_of": st["as_of"], "name": name,
        "who": {"identity": st["identity"], "owns": [f for f in st["current_state"] if f["key"] == "vehicle.owned"], "known": [f for f in st["current_state"] if f["key"] != "vehicle.owned"]},
        "now": {"driving": st["driving"], "active_intent": st["active_intent"], "suppression": st["suppression"]},
        "changed_recently": st["changed_recently"],
        "discuss": {"topic": rec["topic"], "why": rec["why"], "opening": rec["opening"], "mention_history": rec["mention_history"], "also_active": rec["also_active"]},
        "next": {"action": rec["action"], "mode": rec["mode"]},
        "verify": rec["verify"],
        "evidence": rec["evidence"],
        "history": st["history"],
        "counts": st["counts"],
        "settings": {"intent_window_days": settings["intent_window_days"], "intent_fresh_days": settings["intent_fresh_days"], "not_shopping_days": settings["not_shopping_days"]},
        "flags": config.flags(),
    }
