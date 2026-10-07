"""Customer trade link: the rep texts (or copies) a one-vehicle, 7-day link; the customer sends VIN, mileage, photos and a few condition answers from
their own phone. Everything lands on the SAME appraisal through the same media path as rep captures (source customer_supplied), so the stepper, the
inspection and the desk see it. Nothing the customer types is accepted as confirmed: the rep confirms VIN and mileage exactly as before."""
import datetime as dt
import logging
import os
import secrets
from datetime import timedelta
from typing import Optional

from services.appraisals import core, voice, workflow
from services.appraisals.core import A, _now, _oid, _name, audit
from services.appraisals.providers import ProviderUnavailable

logger = logging.getLogger(__name__)

LINK_DAYS = 7
MAX_PHOTOS = 40
MAX_SUBMITS = 5
PHOTO_ROLES = {"vin_photo": "VIN sticker", "odometer_photo": "Odometer", "exterior": "Outside", "interior": "Inside", "photo": "Other"}
CONDITION_QUESTIONS = [
    {"key": "overall", "label": "Overall condition", "options": [("excellent", "Excellent"), ("good", "Good"), ("fair", "Fair"), ("rough", "Rough")]},
    {"key": "accidents", "label": "Any accidents or body repairs?", "options": [("no", "No"), ("yes", "Yes"), ("unsure", "Not sure")]},
    {"key": "warning_lights", "label": "Any warning lights on the dash?", "options": [("no", "No"), ("yes", "Yes")]},
    {"key": "tires", "label": "Tires", "options": [("good", "Good"), ("worn", "Getting worn"), ("replace", "Need replacing")]},
    {"key": "smoke", "label": "Smoked in?", "options": [("no", "No"), ("yes", "Yes")]},
    {"key": "keys", "label": "How many keys?", "options": [("2", "2 or more"), ("1", "1")]},
]


def public_base() -> str:
    return (os.environ.get("PUBLIC_FACING_URL") or os.environ.get("APP_URL") or "https://app.imonsocial.com").rstrip("/")


def _first(name: Optional[str]) -> str:
    return (name or "").strip().split(" ")[0] or "there"


def public_intake(a: dict) -> Optional[dict]:
    i = a.get("intake")
    if not i:
        return None
    return {k: i.get(k) for k in ("url", "short_url", "created_at", "expires_at", "sent_at", "sent_via", "sent_to", "opened_at", "submitted_at", "photo_count", "revoked_at")}


async def _store_name(db, appr: dict) -> str:
    st = await db.stores.find_one({"_id": _oid(appr.get("store_id"))}, {"name": 1}) if appr.get("store_id") else None
    return (st or {}).get("name") or "the dealership"


async def create_link(db, appr: dict, me: dict, *, channel: str = "copy") -> dict:
    """Mint (or reuse an unexpired) link, optionally text it. Mode becomes customer_sent because that is what is happening."""
    from routers.short_urls import create_short_url
    if appr.get("abilities", {}).get("locked") or appr.get("status") not in ("draft", "capturing", "analyzing", "ready", "needs_info"):
        raise ValueError("This appraisal is past the capture stage; start a reappraisal to collect new info.")
    now = _now()
    intake = appr.get("intake") or {}
    exp = intake.get("expires_at")
    if not (appr.get("intake_token") and exp and exp.replace(tzinfo=exp.tzinfo or dt.timezone.utc) > now and not intake.get("revoked_at")):
        token = secrets.token_urlsafe(24)
        url = f"{public_base()}/api/public/trade/{token}"
        short = None
        try:
            short = (await create_short_url(url, "trade_intake", reference_id=str(appr["_id"]), user_id=appr["user_id"], metadata={"contact_id": appr.get("contact_id")})).get("short_url")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[Intake] short url failed: {e}")
        intake = {"url": url, "short_url": short or url, "created_at": now, "expires_at": now + timedelta(days=LINK_DAYS), "sent_at": None, "sent_via": None, "sent_to": None,
                  "opened_at": None, "submitted_at": None, "photo_count": 0, "submits": 0, "revoked_at": None}
        await db[A].update_one({"_id": appr["_id"]}, {"$set": {"intake_token": token, "intake": intake, "mode": "customer_sent", "updated_at": now}})
        await audit(db, appr, me, "intake_link_created", f"Customer trade link created, good for {LINK_DAYS} days")
    sent_note = ""
    if channel == "sms":
        from services.twilio_service import send_sms
        contact = await db.contacts.find_one({"_id": _oid(appr["contact_id"])}, {"phone": 1, "first_name": 1, "name": 1}) if appr.get("contact_id") else None
        phone = (contact or {}).get("phone")
        if not phone:
            raise ValueError("This customer has no phone number on file. Add one, or copy the link instead.")
        store = await _store_name(db, appr)
        veh = core.vehicle_label(appr.get("vehicle") or {}) if appr.get("vehicle") else None
        msg = (f"Hi {_first(appr.get('contact_name'))}, it's {_first(_name(me))} at {store}. Tap this link to send me your {veh or 'vehicle'}'s VIN, mileage and a few photos "
               f"so I can work up a real number for your trade: {intake['short_url']} Takes about 3 minutes.")
        res = await send_sms(phone, msg, org_id=appr.get("organization_id"), user_id=str(me["_id"]), contact_id=appr.get("contact_id"))
        if not (res or {}).get("success", True) and (res or {}).get("error"):
            raise ValueError(f"Text failed: {res['error']}")
        intake.update({"sent_at": now, "sent_via": "sms", "sent_to": phone})
        await db[A].update_one({"_id": appr["_id"]}, {"$set": {"intake.sent_at": now, "intake.sent_via": "sms", "intake.sent_to": phone, "updated_at": now}})
        sent_note = f" · texted to {phone}"
        await audit(db, appr, me, "intake_link_sent", f"Customer trade link texted{sent_note}", meta={"to": phone})
    elif channel == "copy" and not intake.get("sent_at"):
        await db[A].update_one({"_id": appr["_id"]}, {"$set": {"intake.sent_via": "copy", "updated_at": now}})
        intake["sent_via"] = "copy"
    return public_intake({"intake": intake})


async def revoke(db, appr: dict, me: dict) -> dict:
    now = _now()
    await db[A].update_one({"_id": appr["_id"]}, {"$set": {"intake.revoked_at": now, "intake.expires_at": now, "updated_at": now}})
    await audit(db, appr, me, "intake_link_revoked", "Customer trade link turned off")
    a = await db[A].find_one({"_id": appr["_id"]})
    return public_intake(a)


# ---------- public side (token, no login) ----------
async def by_token(db, token: str) -> Optional[dict]:
    if not token or len(token) < 20:
        return None
    return await db[A].find_one({"intake_token": token, "deleted": {"$ne": True}})


def link_state(appr: dict) -> str:
    i = appr.get("intake") or {}
    exp = i.get("expires_at")
    if i.get("revoked_at") or not exp or exp.replace(tzinfo=exp.tzinfo or dt.timezone.utc) <= _now():
        return "expired"
    if appr.get("status") not in ("draft", "capturing", "analyzing", "ready", "needs_info"):
        return "closed"
    return "open"


async def context(db, appr: dict, *, mark_opened: bool = False) -> dict:
    """What the customer page needs: who is asking, what we already have, what is still wanted. No values, no internal ids."""
    i = appr.get("intake") or {}
    if mark_opened and not i.get("opened_at"):
        await db[A].update_one({"_id": appr["_id"]}, {"$set": {"intake.opened_at": _now()}})
    rep = await db.users.find_one({"_id": _oid(appr["user_id"])}, {"name": 1, "first_name": 1, "last_name": 1, "phone": 1}) if appr.get("user_id") else None
    media = await db[core.M].find({"appraisal_id": str(appr["_id"]), "source": "customer_supplied", "deleted": {"$ne": True}}, {"role": 1, "thumb_path": 1, "kind": 1}).sort("created_at", 1).to_list(MAX_PHOTOS)
    ci = appr.get("customer_intake") or {}
    return {"state": link_state(appr), "store": await _store_name(db, appr), "rep": _first(_name(rep or {})), "customer": _first(appr.get("contact_name")),
            "vehicle": core.vehicle_label(appr.get("vehicle")) if appr.get("vehicle") else None, "have_vin": bool(appr.get("vin")), "have_mileage": appr.get("mileage_confirmed") is not None,
            "photos": [{"id": str(m["_id"]), "role": m.get("role"), "thumb": f"/api/images/{m['thumb_path']}" if m.get("thumb_path") else None} for m in media],
            "answers": ci.get("condition") or {}, "notes": ci.get("notes"), "vin": ci.get("vin") or appr.get("vin"), "mileage": ci.get("mileage"), "zip": ci.get("zip"),
            "voice_notes": [_public_voice(v) for v in (appr.get("voice_notes") or []) if v.get("by") == "customer"], "max_voice_notes": voice.MAX_CUSTOMER,
            "submitted": bool(ci.get("submitted_at")), "roles": PHOTO_ROLES, "questions": [{"key": q["key"], "label": q["label"], "options": [{"value": v, "label": l} for v, l in q["options"]]} for q in CONDITION_QUESTIONS],
            "max_photos": MAX_PHOTOS}


def _customer_actor(appr: dict) -> dict:
    return {"_id": "customer", "name": f"{appr.get('contact_name') or 'Customer'} (customer)"}


async def add_photo(db, appr: dict, *, role: str, data: bytes, content_type: str, name: str) -> dict:
    if link_state(appr) != "open":
        raise ValueError("This link is no longer active.")
    if (appr.get("intake") or {}).get("photo_count", 0) >= MAX_PHOTOS:
        raise ValueError(f"That is plenty of photos ({MAX_PHOTOS} max).")
    role = role if role in PHOTO_ROLES else "photo"
    doc = await core.save_media(db, appr, _customer_actor(appr), role=role, source="customer_supplied", data=data, content_type=content_type, name=name or f"{role}.jpg")
    await db[A].update_one({"_id": appr["_id"]}, {"$inc": {"intake.photo_count": 1}, "$set": {"updated_at": _now()}})
    pm = core.public_media(doc)
    return {"id": pm["id"], "role": pm["role"], "thumb": pm.get("thumb_url"), "reading": pm.get("reading")}


def _public_voice(v: dict) -> dict:
    return {"id": v.get("id"), "transcript": v.get("transcript") or "", "duration": v.get("duration"), "transcribed": bool(v.get("transcript"))}


async def add_voice(db, appr: dict, *, data: bytes, content_type: str, duration: float, name: str = "") -> dict:
    """The customer talks about the car from the link page. Same voice-note path as the rep's, author customer, words appended to the appraisal notes."""
    if link_state(appr) != "open":
        raise ValueError("This link is no longer active.")
    vn = await voice.add_voice_note(db, appr, _customer_actor(appr), by="customer", data=data, content_type=content_type, duration=duration, name=name)
    return _public_voice(vn)


async def submit(db, appr: dict, body: dict) -> dict:
    """Store the customer's answers, set the vehicle when a valid VIN arrives and none is on file, tell the rep. Mileage is kept as 'reported' for the rep to confirm."""
    if link_state(appr) != "open":
        raise ValueError("This link is no longer active.")
    if (appr.get("intake") or {}).get("submits", 0) >= MAX_SUBMITS:
        raise ValueError("This link has already been submitted. Your salesperson has everything.")
    now = _now()
    vin = (body.get("vin") or "").strip().upper().replace("I", "1").replace("O", "0").replace("Q", "0")[:17] or None
    mileage = body.get("mileage")
    mileage = int(mileage) if isinstance(mileage, (int, float)) or (isinstance(mileage, str) and mileage.strip().isdigit()) else None
    if mileage is not None and not (0 <= mileage <= 1_500_000):
        mileage = None
    zip_code = (str(body.get("zip") or "").strip()[:5]) or None
    answers = {q["key"]: str(body.get("condition", {}).get(q["key"]) or "") for q in CONDITION_QUESTIONS if str(body.get("condition", {}).get(q["key"]) or "") in {v for v, _ in q["options"]}}
    notes = (str(body.get("notes") or "").strip())[:1500] or None
    wants = body.get("wants")
    wants = int(wants) if isinstance(wants, (int, float)) or (isinstance(wants, str) and wants.strip().isdigit()) else None
    if wants is not None and not (0 < wants < 5_000_000):
        wants = None
    ci = {"submitted_at": now, "vin": vin, "mileage": mileage, "zip": zip_code, "condition": answers, "notes": notes, "wants": wants, "photo_count": (appr.get("intake") or {}).get("photo_count", 0)}
    await db[A].update_one({"_id": appr["_id"]}, {"$set": {"customer_intake": ci, "intake.submitted_at": now, "updated_at": now}, "$inc": {"intake.submits": 1}})
    actor = _customer_actor(appr)
    vehicle_set = False
    if vin and len(vin) == 17 and not appr.get("vin"):
        try:
            await core.set_vehicle(db, appr, actor, vin=vin, method="customer_link")
            vehicle_set = True
        except (ValueError, ProviderUnavailable) as e:
            await audit(db, appr, actor, "customer_vin_unverified", f"Customer typed VIN {vin}; not accepted automatically ({str(e)[:80]}). The rep decides.")
    bits = [f"VIN {vin}" if vin else None, f"{mileage:,} mi" if mileage is not None else None, f"{ci['photo_count']} photo{'s' if ci['photo_count'] != 1 else ''}" if ci["photo_count"] else None,
            f"condition {answers.get('overall')}" if answers.get("overall") else None, "has a number in mind" if wants else None]
    text = "Customer sent trade info: " + " · ".join(b for b in bits if b) if any(bits) else "Customer submitted the trade link with notes only"
    await audit(db, appr, actor, "customer_intake", text, meta={"vehicle_set": vehicle_set, "zip": zip_code})
    fresh = await db[A].find_one({"_id": appr["_id"]})
    try:
        label = core.vehicle_label(fresh.get("vehicle")) if fresh.get("vehicle") else "their trade"
        await workflow._notify(fresh["user_id"], "appraisal_intake", "Customer sent trade info", f"{fresh.get('contact_name') or 'Your customer'} sent details for {label}. Open the appraisal to confirm and keep going.",
                               f"/appraisal/{fresh['_id']}", fresh, icon="cloud-done")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[Intake] notify failed: {e}")
    return {"ok": True, "vehicle_set": vehicle_set}
