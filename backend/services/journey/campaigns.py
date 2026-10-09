"""Journey campaigns: a batch of 1 to 10 virtual customers sent at one store, with reply modes, a window of up to 30 days,
an authorization record before anything goes out, and an emergency stop.

States: draft (identities are being generated and edited, nothing has reached the store) -> armed (numbers reserved, leads
delivered or waiting for the admin to submit the store's web form) -> live (the first clock started) -> closed (every identity
graded) | stopped (emergency stop: every open identity closed on the spot). Each identity is a Lead Shop, so every inbound
call, text and email keeps flowing through the existing webhooks and grading."""
import logging
from datetime import datetime
from typing import Optional

from services import lead_shops as ls
from services.journey import identities as ids

logger = logging.getLogger(__name__)

COLL = "journey_campaigns"
MODES = ("observe", "approve", "auto")
VOICE_MODES = ("voicemail", "live")
WINDOWS = {24: "24 hours", 72: "3 days", 168: "7 days", 720: "30 days"}
DEFAULT_MODES = {"email": "approve", "sms": "approve", "voice": "voicemail"}
STATUSES = ("draft", "armed", "live", "stopped", "closed")
OPEN_SHOP = ("pending_delivery", "live", "closing")


def clean_modes(raw: Optional[dict], base: Optional[dict] = None) -> dict:
    out = dict(base or DEFAULT_MODES)
    raw = raw or {}
    for k in ("email", "sms"):
        if raw.get(k) in MODES:
            out[k] = raw[k]
    if raw.get("voice") in VOICE_MODES:
        out["voice"] = raw["voice"]
    return out


def _window(v, default=72) -> int:
    try:
        v = int(v)
    except (TypeError, ValueError):
        return default
    return v if v in WINDOWS else default


async def create(db, client: dict, me: dict, body: dict) -> dict:
    if not ls.inbound_domain():
        raise ValueError("Email receiving is not configured (INBOUND_EMAIL_DOMAIN)")
    method = "adf" if body.get("method") == "adf" else "manual"
    now = ls._now()
    dept = body.get("department") or "sales"
    name = (body.get("name") or "").strip()[:80] or f"{dept.replace('_', ' ').title()} journey · {now.strftime('%b %Y')}"
    doc = {"client_id": str(client["_id"]), "name": name, "department": dept, "industry": client.get("industry") or "automotive", "store_name": client.get("name"), "locale": client.get("locale"),
           "scenario": {"offering": (body.get("offering") or "").strip()[:80], "script_id": body.get("script_id") or None, "notes": (body.get("notes") or "").strip()[:500]},
           "modes": clean_modes(body.get("modes")), "live_voice_enabled": bool(body.get("live_voice_enabled")), "window_hours": _window(body.get("window_hours")), "method": method,
           "source_name": (body.get("source_name") or "").strip()[:60] or "Website", "submission_limit": max(1, min(int(body.get("submission_limit") or ids.MAX_IDENTITIES), ids.MAX_IDENTITIES)),
           "authorization": None, "emergency_stop": None, "status": "draft", "created_by": str(me["_id"]), "created_at": now, "updated_at": now, "armed_at": None, "stopped_at": None, "closed_at": None}
    if doc["scenario"]["script_id"]:
        sc = await db.scripts.find_one({"_id": ls._oid(doc["scenario"]["script_id"])}) if ls._oid(doc["scenario"]["script_id"]) else None
        doc["scenario"]["script_title"] = sc.get("title") if sc else None
    res = await db[COLL].insert_one(doc)
    doc["_id"] = res.inserted_id
    count = int(body.get("count") or 0)
    if count > 0:
        try:
            await ids.generate(db, doc, client, me, count)
        except Exception as e:
            await db[COLL].delete_one({"_id": doc["_id"]})
            raise ValueError(str(e)[:200])
    return await db[COLL].find_one({"_id": doc["_id"]})


async def update(db, camp: dict, body: dict) -> dict:
    """Modes may change while the campaign runs; the scenario, method, window and source only while it is a draft."""
    if camp.get("status") in ("stopped", "closed"):
        raise ValueError("This campaign has ended")
    upd = {}
    if body.get("name") is not None:
        upd["name"] = str(body["name"]).strip()[:80] or camp.get("name")
    if body.get("modes") is not None:
        upd["modes"] = clean_modes(body["modes"], camp.get("modes"))
    if body.get("live_voice_enabled") is not None:
        upd["live_voice_enabled"] = bool(body["live_voice_enabled"])
    if camp.get("status") == "draft":
        if body.get("window_hours") is not None:
            upd["window_hours"] = _window(body["window_hours"], camp.get("window_hours") or 72)
        if body.get("method") in ("adf", "manual"):
            upd["method"] = body["method"]
        if body.get("source_name") is not None:
            upd["source_name"] = str(body["source_name"]).strip()[:60] or camp.get("source_name")
        if body.get("offering") is not None or body.get("notes") is not None:
            sc = dict(camp.get("scenario") or {})
            if body.get("offering") is not None:
                sc["offering"] = str(body["offering"]).strip()[:80]
            if body.get("notes") is not None:
                sc["notes"] = str(body["notes"]).strip()[:500]
            upd["scenario"] = sc
        if body.get("submission_limit") is not None:
            upd["submission_limit"] = max(1, min(int(body["submission_limit"]), ids.MAX_IDENTITIES))
    elif any(body.get(k) is not None for k in ("window_hours", "method", "source_name", "offering", "notes", "submission_limit")):
        raise ValueError("The scenario, window and delivery method are locked once the campaign is armed")
    if not upd:
        return camp
    await db[COLL].update_one({"_id": camp["_id"]}, {"$set": {**upd, "updated_at": ls._now()}})
    camp = await db[COLL].find_one({"_id": camp["_id"]})
    if "window_hours" in upd or "method" in upd or "source_name" in upd:
        await db[ls.COLL].update_many({"campaign_id": str(camp["_id"]), "status": "draft"},
                                      {"$set": {"window_hours": camp["window_hours"], "method": camp["method"], "delivery.method": camp["method"], "source_name": camp["source_name"], "updated_at": ls._now()}})
    return camp


async def identities_of(db, camp: dict) -> list:
    return await db[ls.COLL].find({"campaign_id": str(camp["_id"])}).sort("created_at", 1).to_list(ids.MAX_IDENTITIES * 2)


async def arm(db, camp: dict, client: dict, me: dict, body: dict) -> dict:
    """Reserve a shopper number for every draft identity and (ADF) deliver the leads. Needs an explicit authorization from the admin."""
    if camp.get("status") != "draft":
        raise ValueError("Only a draft campaign can be armed")
    if not body.get("confirm"):
        raise ValueError("Confirm that you are authorized to test this store before arming")
    drafts = [s for s in await identities_of(db, camp) if s.get("status") == "draft"]
    if not drafts:
        raise ValueError("Generate at least one identity first")
    if camp.get("method") == "adf" and not (client.get("lead_email") or "").strip():
        raise ValueError("Add the store's CRM lead email in Lead shop setup first (or switch the campaign to the web form)")
    if not ls.inbound_domain():
        raise ValueError("Email receiving is not configured (INBOUND_EMAIL_DOMAIN)")
    pool = await ls.pool_state(db)
    import os
    from services.runtime_env import is_preview_runtime
    buying_off = is_preview_runtime() and (os.environ.get("LEAD_SHOP_BUY_NUMBERS") or "true").strip().lower() in ("0", "false", "no", "off")
    room = pool["available"] + (0 if buying_off else max(0, pool["cap"] - pool["total"]))
    if room < len(drafts):
        raise ValueError(f"Only {room} shopper number{'s are' if room != 1 else ' is'} free for {len(drafts)} identities. Free some numbers (close older shops) or arm fewer identities.")
    now = ls._now()
    auth = {"by": str(me["_id"]), "by_name": me.get("name") or me.get("email"), "at": now, "website_url": (body.get("website_url") or "").strip()[:300], "note": (body.get("note") or "").strip()[:500]}
    await db[COLL].update_one({"_id": camp["_id"]}, {"$set": {"authorization": auth, "status": "armed", "armed_at": now, "updated_at": now}})
    errors = []
    for s in drafts:
        try:
            number = await ls.acquire_number(db, client, me)
        except Exception as e:
            errors.append(f"{s['persona'].get('name')}: no number ({str(e)[:120]})")
            break
        await db[ls.POOL].update_one({"_id": number["_id"]}, {"$set": {"lead_shop_id": str(s["_id"])}})
        await db[ls.COLL].update_one({"_id": s["_id"]}, {"$set": {"persona.phone": number["phone_number"], "number_pool_id": str(number["_id"]), "status": "pending_delivery", "method": camp.get("method"),
                                                                 "delivery.method": camp.get("method"), "delivery.to_email": (client.get("lead_email") or "").strip().lower() if camp.get("method") == "adf" else None,
                                                                 "window_hours": int(camp.get("window_hours") or 72), "armed_at": now, "updated_at": now}})
        s = await db[ls.COLL].find_one({"_id": s["_id"]})
        if camp.get("method") == "adf":
            r = await ls.deliver(db, s, client)
            if r.get("success"):
                await ls.mark_delivered(db, s, email_id=r.get("id"), subject=r.get("subject"))
            else:
                await db[ls.COLL].update_one({"_id": s["_id"]}, {"$set": {"delivery.error": r.get("error"), "updated_at": ls._now()}})
                errors.append(f"{s['persona'].get('name')}: lead email failed ({r.get('error')})")
    if errors:
        await db[COLL].update_one({"_id": camp["_id"]}, {"$set": {"arm_errors": errors, "updated_at": ls._now()}})
    return await db[COLL].find_one({"_id": camp["_id"]})


async def on_identity_live(db, shop: dict):
    """The first clock in an armed campaign started: the campaign is live."""
    if shop.get("campaign_id"):
        await db[COLL].update_one({"_id": ls._oid(shop["campaign_id"]), "status": "armed"}, {"$set": {"status": "live", "updated_at": ls._now()}})


async def stop(db, camp: dict, me: dict, reason: str = "") -> dict:
    """Emergency stop: every open identity closes right now (number back to the pool, threads graded on what happened), drafts stay drafts."""
    if camp.get("status") not in ("armed", "live"):
        raise ValueError("Only an armed or live campaign can be stopped")
    now = ls._now()
    await db[COLL].update_one({"_id": camp["_id"]}, {"$set": {"status": "stopped", "stopped_at": now, "emergency_stop": {"at": now, "by": str(me["_id"]), "by_name": me.get("name") or me.get("email"), "reason": (reason or "").strip()[:300]}, "updated_at": now}})
    for s in await identities_of(db, camp):
        if s.get("status") in ("live", "pending_delivery"):
            try:
                await ls.close(db, s, "emergency_stop")
            except Exception as e:
                logger.warning(f"[Journey] stop: closing {s['_id']} failed: {e}")
    return await db[COLL].find_one({"_id": camp["_id"]})


async def close(db, camp: dict) -> dict:
    """Admin closes early: open identities close and grade normally, never-armed drafts are removed."""
    if camp.get("status") not in ("armed", "live", "draft"):
        raise ValueError("This campaign has already ended")
    for s in await identities_of(db, camp):
        if s.get("status") in ("live", "pending_delivery"):
            await ls.close(db, s, "closed_by_admin")
        elif s.get("status") == "draft":
            await db[ls.COLL].delete_one({"_id": s["_id"]})
    now = ls._now()
    await db[COLL].update_one({"_id": camp["_id"]}, {"$set": {"status": "closed", "closed_at": now, "updated_at": now}})
    return await db[COLL].find_one({"_id": camp["_id"]})


async def remove(db, camp: dict):
    if camp.get("status") in ("armed", "live"):
        raise ValueError("Stop or close the campaign before deleting it")
    await db[ls.COLL].delete_many({"campaign_id": str(camp["_id"]), "status": "draft"})
    await db[ls.COLL].update_many({"campaign_id": str(camp["_id"])}, {"$unset": {"campaign_id": ""}})
    await db[COLL].delete_one({"_id": camp["_id"]})


async def sweep(db) -> int:
    """Armed / live campaigns whose identities have all finished close themselves."""
    n = 0
    async for camp in db[COLL].find({"status": {"$in": ["armed", "live"]}}):
        rows = await identities_of(db, camp)
        if rows and all(s.get("status") == "completed" for s in rows):
            now = ls._now()
            await db[COLL].update_one({"_id": camp["_id"]}, {"$set": {"status": "closed", "closed_at": now, "updated_at": now}})
            n += 1
    return n


def _iso_dict(d: Optional[dict]) -> Optional[dict]:
    return {k: ls._iso(v) for k, v in d.items()} if isinstance(d, dict) else d


async def serialize(db, camp: dict, with_identities: bool = False) -> dict:
    rows = await identities_of(db, camp)
    counts = {k: sum(1 for s in rows if s.get("status") == k) for k in ("draft", "pending_delivery", "live", "closing", "completed")}
    scores = [s["score"]["overall"] for s in rows if s.get("status") == "completed" and (s.get("score") or {}).get("overall") is not None]
    out = {"id": str(camp["_id"]), "client_id": camp.get("client_id"), "name": camp.get("name"), "department": camp.get("department"), "store_name": camp.get("store_name"), "status": camp.get("status"),
           "method": camp.get("method"), "source_name": camp.get("source_name"), "window_hours": camp.get("window_hours"), "window_label": WINDOWS.get(int(camp.get("window_hours") or 72), ""),
           "modes": clean_modes(camp.get("modes")), "live_voice_enabled": bool(camp.get("live_voice_enabled")), "submission_limit": camp.get("submission_limit") or ids.MAX_IDENTITIES,
           "scenario": camp.get("scenario") or {}, "authorization": _iso_dict(camp.get("authorization")), "emergency_stop": _iso_dict(camp.get("emergency_stop")), "arm_errors": camp.get("arm_errors") or [],
           "created_at": ls._iso(camp.get("created_at")), "armed_at": ls._iso(camp.get("armed_at")), "stopped_at": ls._iso(camp.get("stopped_at")), "closed_at": ls._iso(camp.get("closed_at")),
           "counts": {**counts, "total": len(rows), "open": counts["pending_delivery"] + counts["live"] + counts["closing"]}, "avg_score": int(round(sum(scores) / len(scores))) if scores else None,
           "identities": [{"id": str(s["_id"]), "name": (s.get("persona") or {}).get("name"), "status": s.get("status"), "score": (s.get("score") or {}).get("overall")} for s in rows]}
    if with_identities:
        out["identities"] = [await ls.serialize(db, s) for s in rows]
    return out
