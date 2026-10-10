"""Layers A-D assembled from facts in code (no model call): identity, relationship history, current state, active intent, plus what changed recently and what needs verification."""
from datetime import timedelta
from typing import Optional

from services.intelligence import facts as F
from services.intelligence import intent as I


def _stale(f: dict, settings: dict, now) -> Optional[int]:
    days = (settings.get("stale_after_days") or {}).get(f.get("domain"))
    if not days:
        return None
    anchor = f.get("confirmed_at") or f.get("recorded_at")
    age = (now - anchor).days if anchor else None
    return age if age is not None and age > int(days) else None


def _label(f: dict) -> str:
    v = f.get("value")
    if isinstance(v, dict) and v.get("label"):
        return v["label"]
    return f.get("statement") or ""


async def build(db, contact: dict, settings: dict, now=None) -> dict:
    now = now or F.now_utc()
    cid = str(contact["_id"])
    rows = await F.load(db, {"contact_id": cid}, sort=[("occurred_at", -1)])
    sup = await I.suppression(db, cid, now)
    recent_cut = now - timedelta(days=int(settings.get("recent_days", 14)))

    def out(f, **extra):
        return {**F.pub(f), "label": _label(f), **extra}

    identity = [out(f) for f in rows if f["layer"] == "identity" and f["status"] == "current"]
    state = [out(f, stale_days=_stale(f, settings, now)) for f in rows if f["layer"] == "state" and f["status"] == "current"]
    expired = [f for f in rows if f["key"] == "buying.status" and f["status"] == "current" and f.get("active_until") and f["active_until"] <= now]
    history = [out(f) for f in rows if f["layer"] == "history" or f["status"] in ("historical", "superseded")] + [out(f, expired=True) for f in expired]
    history.sort(key=lambda x: x["occurred_at"] or "", reverse=True)
    intents = [out(f, **(I.phase(f, settings, now) or {})) for f in rows if f["layer"] == "intent" and f["status"] == "current" and f["key"] != "buying.status"]
    intents.sort(key=lambda x: (x.get("last_signal_at") or x["occurred_at"], x["occurred_at"], x["recorded_at"]), reverse=True)
    verify = [out(f) for f in rows if f["status"] in ("disputed", "proposed")] + [s for s in state if s.get("stale_days")]
    verify += [out(f, unverified=True) for f in rows if f["status"] == "current" and f["key"] in F.REQUIRE_CONFIRM and not f.get("confirmations")]
    changed = [out(f) for f in rows if f["recorded_at"] >= recent_cut]
    changed.sort(key=lambda x: x["recorded_at"], reverse=True)
    return {
        "contact_id": cid, "as_of": F.iso(now),
        "identity": identity, "history": history, "current_state": state,
        "active_intent": intents, "driving": intents[0] if intents and intents[0].get("phase") != "dormant" else None,
        "suppression": out(sup) if sup else None,
        "needs_verification": verify, "changed_recently": changed,
        "counts": {"facts": len(rows), "current": len([r for r in rows if r["status"] == "current"]) - len(expired), "historical": len([r for r in rows if r["status"] in ("historical", "superseded")]) + len(expired),
                   "needs_verification": len(verify)},
    }
