"""Per-client shop numbers outside the US. Dutch (+31 97) mobile-range numbers need no paperwork, so a Dutch store gets one
automatically at kickoff; UK / Irish mobiles usually need a regulatory bundle first, so those report the Twilio reason instead of failing silently."""
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

from services import locales as loc
from services import scripts as scr

logger = logging.getLogger(__name__)

MONTHLY_COST = {"NL": 3.00, "GB": 1.15, "IE": 6.00, "BE": 3.00, "US": 1.15}
SEARCH_KIND = {"NL": "mobile", "GB": "mobile", "IE": "mobile", "BE": "mobile", "US": "local"}
# countries whose numbers Twilio only sells against a regulatory bundle (made once in the Console, reused for every client)
NEEDS_BUNDLE = {"GB": "a UK business address with proof, photo ID and a reachable UK mobile", "IE": "an Irish business address plus company registration documents", "BE": "a Belgian business address"}
BUNDLE_KEY = "shop_number_bundles"


def _now():
    return datetime.now(timezone.utc)


async def bundles(db) -> dict:
    doc = await db.settings.find_one({"key": BUNDLE_KEY}) or {}
    return doc.get("value") or {}


async def bundles_state(db) -> dict:
    have = await bundles(db)
    return {"countries": [{"country": c, "needs": n, "bundle_sid": (have.get(c) or {}).get("bundle_sid", ""), "address_sid": (have.get(c) or {}).get("address_sid", ""), "on_file": bool((have.get(c) or {}).get("bundle_sid"))} for c, n in NEEDS_BUNDLE.items()]}


async def set_bundle(db, country: str, bundle_sid: str, address_sid: str) -> dict:
    """Save (or clear, with both blank) the Twilio Bundle SID + Address SID used to buy numbers in one country."""
    country = (country or "").upper()
    if country not in NEEDS_BUNDLE:
        raise ValueError("Bundles are only needed for GB, IE and BE numbers")
    b, a = (bundle_sid or "").strip(), (address_sid or "").strip()
    if not b and not a:
        await db.settings.update_one({"key": BUNDLE_KEY}, {"$unset": {f"value.{country}": ""}})
        return await bundles_state(db)
    if not (b.startswith("BU") and len(b) == 34):
        raise ValueError("The Bundle SID starts with BU and is 34 characters (Twilio Console > Phone Numbers > Regulatory Compliance > Bundles)")
    if not (a.startswith("AD") and len(a) == 34):
        raise ValueError("The Address SID starts with AD and is 34 characters (Twilio Console > Phone Numbers > Regulatory Compliance > Addresses)")
    await db.settings.update_one({"key": BUNDLE_KEY}, {"$set": {f"value.{country}": {"bundle_sid": b, "address_sid": a, "at": _now()}}}, upsert=True)
    return await bundles_state(db)


async def ensure_dialing_permission(iso: str) -> bool:
    """Twilio blocks outbound calls to most countries until geo permissions are on; flip the low-risk switch for the client's country."""
    from routers.twilio_admin import _get_twilio_client, _twilio_call
    try:
        import json
        await _twilio_call(_get_twilio_client().voice.v1.dialing_permissions.bulk_country_updates.create,
                           update_request=json.dumps([{"iso_code": iso, "low_risk_numbers_enabled": True, "high_risk_special_numbers_enabled": False, "high_risk_tollfraud_numbers_enabled": False}]))
        return True
    except Exception as e:
        logger.warning(f"[ShopNumbers] could not enable dialing to {iso}: {e}")
        return False


async def buy_client_number(db, client: dict, me: Optional[dict] = None, reason: str = "manual") -> dict:
    """Buy a voice number in the client's country and make it the client's shop number. Never raises; the outcome is stored on the client for the admin to see."""
    from routers.twilio_admin import _get_twilio_client, _twilio_call
    lc = loc.key_of(client)
    country = loc.get(lc)["country"]
    kind = SEARCH_KIND.get(country, "local")
    base = scr._app_url()
    out = {"ok": False, "country": country, "kind": kind, "at": _now(), "reason": reason}
    bundle = (await bundles(db)).get(country) or {}
    extra = {"bundle_sid": bundle["bundle_sid"], "address_sid": bundle["address_sid"]} if bundle.get("bundle_sid") else {}
    try:
        if country in NEEDS_BUNDLE and not extra:
            raise RuntimeError(f"Twilio only sells {country} numbers against a regulatory bundle ({NEEDS_BUNDLE[country]}). Create it once in the Twilio Console and paste the Bundle SID and Address SID on the number card.")
        tw = _get_twilio_client()
        found = await _twilio_call(lambda: getattr(tw.available_phone_numbers(country), kind).list(limit=3, voice_enabled=True), timeout=25)
        if not found:
            out["error"] = f"Twilio has no {kind} numbers for {country} right now"
        else:
            bought = await _twilio_call(tw.incoming_phone_numbers.create, phone_number=found[0].phone_number, friendly_name=f"Shop · {(client.get('name') or '')[:40]}",
                                        voice_url=f"{base}/api/webhooks/twilio/voice", voice_method="POST", sms_url=f"{base}/api/webhooks/twilio/incoming", sms_method="POST", timeout=30, **extra)
            out.update({"ok": True, "phone_number": bought.phone_number, "sid": bought.sid, "monthly_cost_usd": MONTHLY_COST.get(country, 1.15), **({"bundle_sid": extra["bundle_sid"]} if extra else {})})
            await db.phone_number_pool.insert_one({"phone_number": bought.phone_number, "twilio_sid": bought.sid, "status": "mystery_shop_client", "purpose": "mystery_shop_client", "shop_client_id": str(client["_id"]),
                                                   "country": country, "monthly_cost_usd": out["monthly_cost_usd"], "purchased_at": _now(), "purchased_by": str(me["_id"]) if me else "kickoff"})
            await db.shop_clients.update_one({"_id": client["_id"]}, {"$set": {"from_number": bought.phone_number, "number": {**out, "at": _now()}, "updated_at": _now()}})
            await ensure_dialing_permission(country)
            logger.info(f"[ShopNumbers] bought {bought.phone_number} for {client.get('name')} ({country}, {reason})")
    except Exception as e:
        msg = str(e)
        if "regulatory" in msg.lower() or "bundle" in msg.lower() or "address" in msg.lower():
            msg = f"Twilio needs a regulatory bundle (business address + registration) before it sells {country} numbers: {msg[:160]}"
        out["error"] = msg[:300]
        logger.warning(f"[ShopNumbers] buy failed for {client.get('name')} ({country}): {e}")
    if not out["ok"]:
        await db.shop_clients.update_one({"_id": client["_id"]}, {"$set": {"number_error": {"error": out["error"], "at": _now(), "reason": reason, "country": country}, "updated_at": _now()}})
    return out


async def release_client_number(db, client: dict) -> dict:
    """Give the client's own number back to Twilio (client deleted or moved back to the platform number)."""
    from routers.twilio_admin import _get_twilio_client, _twilio_call
    num = client.get("number") or {}
    if not num.get("sid"):
        return {"released": False}
    try:
        await _twilio_call(_get_twilio_client().incoming_phone_numbers(num["sid"]).delete, timeout=20)
    except Exception as e:
        logger.warning(f"[ShopNumbers] release {num.get('phone_number')} failed: {e}")
        return {"released": False, "error": str(e)[:200]}
    await db.phone_number_pool.update_one({"twilio_sid": num["sid"]}, {"$set": {"status": "released", "released_at": _now()}})
    await db.shop_clients.update_one({"_id": client["_id"]}, {"$set": {"from_number": "", "updated_at": _now()}, "$unset": {"number": ""}})
    return {"released": True}


def number_state(client: dict, have_bundles: Optional[dict] = None) -> dict:
    num = client.get("number") or {}
    err = client.get("number_error") or {}
    lc = loc.key_of(client)
    country = loc.get(lc)["country"]
    return {"phone_number": client.get("from_number") or "", "own": bool(num.get("sid")), "country": country, "kind": SEARCH_KIND.get(country, "local"),
            "monthly_cost_usd": num.get("monthly_cost_usd"), "bought_at": num["at"].isoformat() if hasattr(num.get("at"), "isoformat") else None,
            "error": err.get("error"), "error_at": err["at"].isoformat() if hasattr(err.get("at"), "isoformat") else None, "needs_local_number": country != "US" and not client.get("from_number"),
            "needs_bundle": country in NEEDS_BUNDLE, "bundle_needs": NEEDS_BUNDLE.get(country), "bundle_on_file": bool(((have_bundles or {}).get(country) or {}).get("bundle_sid"))}
