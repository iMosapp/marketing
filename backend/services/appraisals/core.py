"""Trade appraisal core (MVP1): vehicles on a contact, appraisal drafts, capture modes, media with provenance, the audit trail,
and the lines Jessi reads. Scoping reuses the platform's accessible-user-ids rule (rep = own, manager = store, admin = org)."""
import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

from routers.database import get_accessible_user_ids
from services.appraisals.providers import IDENTITY, ProviderUnavailable, empty_vehicle, vehicle_label, VEHICLE_FIELDS
from services.appraisals import readers
from services.contact_files import _normalize_image
from utils.activity_log import log_activity
from utils.image_storage import put_object

logger = logging.getLogger(__name__)

V, A, M, ACT = "vehicles", "vehicle_appraisals", "appraisal_media", "appraisal_activity"
MODES = {"vehicle_here": "Vehicle is here", "customer_sent": "Customer sent media"}
SOURCES = {"captured_by_rep": "Captured by rep", "uploaded_by_rep": "Uploaded by rep", "customer_supplied": "Customer supplied"}
ROLES = {"vin_photo": "VIN photo", "odometer_photo": "Odometer photo", "exterior": "Exterior photo", "interior": "Interior photo",
         "walkaround_video": "Walkaround video", "other": "Other"}
# Status machine; MVP1 only moves within draft. Later MVPs add analyzing/ready/submitted/approved/changed/needs_info/declined/presented/closed.
STATUSES = ["draft", "analyzing", "ready", "submitted", "approved", "changed", "needs_info", "declined", "presented", "closed"]
STEPS = ["customer", "mode", "identity", "mileage", "expectation", "review"]
MAX_IMAGE = 25 * 1024 * 1024
MAX_VIDEO = 150 * 1024 * 1024


def _now():
    return datetime.now(timezone.utc)


def _oid(s) -> Optional[ObjectId]:
    return ObjectId(s) if s and ObjectId.is_valid(str(s)) else None


async def scope(me: dict) -> dict:
    """Appraisals and vehicles are owned by the salesperson (user_id); managers/admins see their people through the platform rule."""
    if me.get("role") == "super_admin":
        return {}
    ids = await get_accessible_user_ids(me)
    return {"user_id": {"$in": [str(i) for i in ids]}}


def _store(me: dict) -> Optional[str]:
    sid = me.get("store_id") or ((me.get("store_ids") or [None])[0])
    return str(sid) if sid else None


def _name(u: dict) -> str:
    return (u.get("name") or f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip() or u.get("email") or "").strip()


def _contact_name(c: dict) -> str:
    return (c.get("name") or f"{c.get('first_name') or ''} {c.get('last_name') or ''}".strip()).strip() or "Customer"


# ---------- serializers ----------
def public_vehicle(v: dict) -> dict:
    out = {k: v.get(k) for k in VEHICLE_FIELDS}
    out.update({"id": str(v["_id"]), "contact_id": v.get("contact_id"), "label": vehicle_label(v), "decoded_by": v.get("decoded_by"),
                "current_mileage": v.get("current_mileage"), "mileage_as_of": v.get("mileage_as_of"), "ownership_status": v.get("ownership_status") or "owns",
                "appraisal_count": v.get("appraisal_count") or 0, "last_appraisal": v.get("last_appraisal"), "created_at": v.get("created_at")})
    return out


def public_appraisal(a: dict) -> dict:
    keep = ("contact_id", "contact_name", "vehicle_id", "vin", "vehicle", "status", "step", "mode", "mileage_detected", "mileage_confirmed", "mileage_source",
            "expectation_asked", "customer_expected_value", "notes", "stock_number", "user_id", "user_name", "store_id", "previous_appraisal_id", "is_reappraisal",
            "identity_method", "created_at", "updated_at", "submitted_at", "approved_value", "suggested_acv", "outcome")
    out = {k: a.get(k) for k in keep}
    out["id"] = str(a["_id"])
    out["vehicle_label"] = vehicle_label(a.get("vehicle") or {"vin": a.get("vin")}) if (a.get("vehicle") or a.get("vin")) else None
    out["mode_label"] = MODES.get(a.get("mode") or "", "")
    return out


def public_media(m: dict) -> dict:
    return {"id": str(m["_id"]), "appraisal_id": m.get("appraisal_id"), "role": m.get("role"), "role_label": ROLES.get(m.get("role") or "", "File"),
            "source": m.get("source"), "source_label": SOURCES.get(m.get("source") or "", ""), "kind": m.get("kind"), "name": m.get("name"), "size": m.get("size"),
            "url": f"/api/images/{m['path']}" if m.get("path") and m.get("kind") == "image" else None,
            "thumb_url": f"/api/images/{m['thumb_path']}" if m.get("thumb_path") else None,
            "uploaded_by": m.get("uploaded_by"), "uploaded_by_name": m.get("uploaded_by_name"), "uploaded_at": m.get("created_at"), "reading": m.get("reading")}


# ---------- audit ----------
async def audit(db, appr: dict, actor: dict, action: str, detail: str = "", from_status: Optional[str] = None, to_status: Optional[str] = None, meta: Optional[dict] = None):
    await db[ACT].insert_one({"appraisal_id": str(appr["_id"]), "contact_id": appr.get("contact_id"), "store_id": appr.get("store_id"), "actor_id": str(actor.get("_id")),
                              "actor_name": _name(actor), "action": action, "detail": detail[:500], "from_status": from_status, "to_status": to_status,
                              "meta": meta or {}, "created_at": _now()})


async def activity(db, appr: dict, limit: int = 100) -> list:
    rows = await db[ACT].find({"appraisal_id": str(appr["_id"])}).sort("created_at", 1).to_list(limit)
    return [{"id": str(r["_id"]), **{k: r.get(k) for k in ("actor_name", "action", "detail", "from_status", "to_status", "meta", "created_at")}} for r in rows]


# ---------- lookups ----------
async def get_appraisal(db, me: dict, appraisal_id: str) -> Optional[dict]:
    oid = _oid(appraisal_id)
    if not oid:
        return None
    return await db[A].find_one({"_id": oid, "deleted": {"$ne": True}, **(await scope(me))})


async def get_vehicle(db, me: dict, vehicle_id: str) -> Optional[dict]:
    oid = _oid(vehicle_id)
    if not oid:
        return None
    return await db[V].find_one({"_id": oid, "deleted": {"$ne": True}, **(await scope(me))})


async def contact_vehicles(db, me: dict, contact_id: str) -> list:
    rows = await db[V].find({"contact_id": contact_id, "deleted": {"$ne": True}, **(await scope(me))}).sort("created_at", -1).to_list(50)
    return [public_vehicle(v) for v in rows]


async def vehicle_appraisals(db, me: dict, vehicle_id: str) -> list:
    rows = await db[A].find({"vehicle_id": vehicle_id, "deleted": {"$ne": True}, **(await scope(me))}).sort("created_at", -1).to_list(50)
    return [public_appraisal(a) for a in rows]


# ---------- create / reappraise ----------
async def create(db, me: dict, contact: dict, mode: str = "vehicle_here", vehicle_id: Optional[str] = None) -> dict:
    """New draft. With vehicle_id this is a REAPPRAISE: same vehicles doc, new appraisal carrying the VIN/decoded vehicle forward."""
    now = _now()
    doc = {"_id": ObjectId(), "contact_id": str(contact["_id"]), "contact_name": _contact_name(contact), "user_id": str(me["_id"]), "user_name": _name(me),
           "store_id": _store(me), "organization_id": str(me.get("organization_id") or "") or None, "status": "draft", "step": "mode",
           "mode": mode if mode in MODES else "vehicle_here", "vehicle_id": None, "vin": None, "vehicle": None, "identity_method": None,
           "mileage_detected": None, "mileage_confirmed": None, "mileage_source": None, "expectation_asked": None, "customer_expected_value": None,
           "notes": "", "stock_number": None, "book_values": [], "is_reappraisal": False, "previous_appraisal_id": None, "created_at": now, "updated_at": now}
    if vehicle_id:
        veh = await get_vehicle(db, me, vehicle_id)
        if not veh or veh.get("contact_id") != str(contact["_id"]):
            raise ValueError("That vehicle is not on this customer")
        prev = await db[A].find_one({"vehicle_id": vehicle_id, "deleted": {"$ne": True}}, sort=[("created_at", -1)])
        doc.update({"vehicle_id": vehicle_id, "vin": veh.get("vin"), "vehicle": {k: veh.get(k) for k in VEHICLE_FIELDS} | {"decoded_by": veh.get("decoded_by"), "decode_ok": True},
                    "identity_method": "reappraise", "is_reappraisal": True, "previous_appraisal_id": str(prev["_id"]) if prev else None, "step": "mileage"})
    await db[A].insert_one(doc)
    await audit(db, doc, me, "reappraisal_started" if vehicle_id else "appraisal_started", f"{MODES[doc['mode']]}" + (f" · {vehicle_label(doc['vehicle'])}" if doc.get("vehicle") else ""),
                None, "draft")
    if vehicle_id:
        await db[V].update_one({"_id": ObjectId(vehicle_id)}, {"$inc": {"appraisal_count": 1}, "$set": {"updated_at": now}})
    await log_activity(db, user_id=str(me["_id"]), contact_id=str(contact["_id"]), event_type="appraisal_started",
                       description=(f"Reappraisal of {vehicle_label(doc['vehicle'])}" if vehicle_id else f"Trade appraisal started ({MODES[doc['mode']]})"),
                       metadata={"appraisal_id": str(doc["_id"]), "vehicle_id": vehicle_id, "mode": doc["mode"]})
    return doc


async def set_mode(db, appr: dict, me: dict, mode: str) -> dict:
    if mode not in MODES:
        raise ValueError("Unknown capture mode")
    await db[A].update_one({"_id": appr["_id"]}, {"$set": {"mode": mode, "step": "identity" if not appr.get("vehicle_id") else "mileage", "updated_at": _now()}})
    await audit(db, appr, me, "mode_set", MODES[mode])
    return await db[A].find_one({"_id": appr["_id"]})


# ---------- identity ----------
async def identify(db, kind: str, **inputs) -> dict:
    prov = IDENTITY.get(kind)
    if not prov:
        raise ValueError("Unknown identity method")
    if not prov.configured():
        raise ProviderUnavailable(f"{prov.label} lookup is not switched on yet")
    return await prov.identify(db, **inputs)


async def _upsert_vehicle(db, me: dict, appr: dict, vehicle: dict) -> dict:
    """One vehicles doc per (contact, VIN). Manual vehicles without a VIN are keyed by the appraisal so they never collide."""
    now = _now()
    cid = appr["contact_id"]
    key = {"contact_id": cid, "vin": vehicle["vin"], "deleted": {"$ne": True}} if vehicle.get("vin") else {"contact_id": cid, "manual_key": str(appr["_id"]), "deleted": {"$ne": True}}
    existing = await db[V].find_one(key)
    fields = {k: vehicle.get(k) for k in VEHICLE_FIELDS}
    if existing:
        upd = {k: v for k, v in fields.items() if v and not existing.get(k)}
        upd.update({"updated_at": now})
        await db[V].update_one({"_id": existing["_id"]}, {"$set": upd})
        return await db[V].find_one({"_id": existing["_id"]})
    doc = {"_id": ObjectId(), **fields, "contact_id": cid, "user_id": appr["user_id"], "store_id": appr.get("store_id"), "organization_id": appr.get("organization_id"),
           "decoded_by": vehicle.get("decoded_by"), "decode_raw": vehicle.get("raw"), "ownership_status": "owns", "current_mileage": None, "mileage_as_of": None,
           "appraisal_count": 0, "created_at": now, "updated_at": now}
    if not vehicle.get("vin"):
        doc["manual_key"] = str(appr["_id"])
    await db[V].insert_one(doc)
    await log_activity(db, user_id=appr["user_id"], contact_id=cid, event_type="vehicle_added", description=vehicle_label(doc),
                       metadata={"vehicle_id": str(doc["_id"]), "vin": doc.get("vin")})
    return doc


async def set_vehicle(db, appr: dict, me: dict, *, vin: Optional[str] = None, manual: Optional[dict] = None, method: str = "manual_vin") -> dict:
    """Confirmed identity -> vehicles doc linked to the appraisal. Decode failure or no VIN still produces a vehicle the rep fills in."""
    if vin:
        res = await identify(db, "vin", vin=vin)
        if not res["validation"]["valid"]:
            raise ValueError("; ".join(res["validation"]["errors"]))
        vehicle = res["vehicle"] or empty_vehicle(res["vin"])
    else:
        vehicle = empty_vehicle(None)
    if manual:
        for k in VEHICLE_FIELDS:
            if k in manual and manual[k] not in (None, ""):
                vehicle[k] = int(manual[k]) if k == "year" and str(manual[k]).isdigit() else str(manual[k]).strip()
        if not vehicle.get("decoded_by"):
            vehicle["decoded_by"] = "manual"
        vehicle["decode_ok"] = bool(vehicle.get("make") and vehicle.get("model"))
    if not (vehicle.get("vin") or (vehicle.get("make") and vehicle.get("model"))):
        raise ValueError("Give me a VIN, or at least the make and model")
    if appr.get("vehicle_id"):
        old = await db[V].find_one({"_id": _oid(appr["vehicle_id"])})
        if old and old.get("vin") and vehicle.get("vin") and old["vin"] != vehicle["vin"]:
            await db[V].update_one({"_id": old["_id"]}, {"$inc": {"appraisal_count": -1}})
    veh = await _upsert_vehicle(db, me, appr, vehicle)
    if str(veh["_id"]) != appr.get("vehicle_id"):
        await db[V].update_one({"_id": veh["_id"]}, {"$inc": {"appraisal_count": 1}})
    snapshot = {k: veh.get(k) for k in VEHICLE_FIELDS} | {"decoded_by": veh.get("decoded_by"), "decode_ok": vehicle.get("decode_ok"), "decode_message": vehicle.get("decode_message") or ""}
    await db[A].update_one({"_id": appr["_id"]}, {"$set": {"vehicle_id": str(veh["_id"]), "vin": veh.get("vin"), "vehicle": snapshot, "identity_method": method, "step": "mileage", "updated_at": _now()}})
    await audit(db, appr, me, "vehicle_identified", f"{vehicle_label(veh)} via {method}" + (f" · {veh.get('vin')}" if veh.get("vin") else ""), meta={"vehicle_id": str(veh["_id"])})
    return await db[A].find_one({"_id": appr["_id"]})


# ---------- mileage / expectation / notes ----------
async def set_mileage(db, appr: dict, me: dict, confirmed: int, detected: Optional[int] = None, source: str = "manual") -> dict:
    if not (0 <= int(confirmed) <= 1_500_000):
        raise ValueError("That mileage does not look right")
    now = _now()
    upd = {"mileage_confirmed": int(confirmed), "mileage_source": source, "step": "expectation", "updated_at": now}
    if detected is not None:
        upd["mileage_detected"] = int(detected)
    await db[A].update_one({"_id": appr["_id"]}, {"$set": upd})
    if appr.get("vehicle_id"):
        await db[V].update_one({"_id": _oid(appr["vehicle_id"])}, {"$set": {"current_mileage": int(confirmed), "mileage_as_of": now, "updated_at": now}})
    await audit(db, appr, me, "mileage_confirmed", f"{int(confirmed):,} mi ({source})" + (f", Jessi read {int(detected):,}" if detected is not None else ""))
    return await db[A].find_one({"_id": appr["_id"]})


async def set_expectation(db, appr: dict, me: dict, asked: bool, value: Optional[int]) -> dict:
    if asked and value is not None and not (0 < int(value) < 5_000_000):
        raise ValueError("That amount does not look right")
    upd = {"expectation_asked": bool(asked), "customer_expected_value": int(value) if asked and value is not None else None, "step": "review", "updated_at": _now()}
    await db[A].update_one({"_id": appr["_id"]}, {"$set": upd})
    await audit(db, appr, me, "expectation_recorded", f"Customer wants ${int(value):,}" if upd["customer_expected_value"] else "Customer has not named a number")
    if upd["customer_expected_value"]:
        await log_activity(db, user_id=appr["user_id"], contact_id=appr["contact_id"], event_type="trade_expectation",
                           description=f"Wants about ${int(value):,} for {vehicle_label(appr.get('vehicle') or {}) if appr.get('vehicle') else 'their trade'}",
                           metadata={"appraisal_id": str(appr["_id"]), "value": int(value)})
    return await db[A].find_one({"_id": appr["_id"]})


async def patch(db, appr: dict, me: dict, data: dict) -> dict:
    upd = {}
    if "notes" in data:
        upd["notes"] = str(data["notes"] or "")[:4000]
    if "stock_number" in data:
        upd["stock_number"] = (str(data["stock_number"] or "").strip()[:40] or None)
    if "step" in data and data["step"] in STEPS:
        upd["step"] = data["step"]
    if upd:
        upd["updated_at"] = _now()
        await db[A].update_one({"_id": appr["_id"]}, {"$set": upd})
    return await db[A].find_one({"_id": appr["_id"]})


async def delete_draft(db, appr: dict, me: dict):
    """Soft-delete a draft. A vehicle that no other appraisal references goes with it, so a discarded test never leaves a ghost car on the customer."""
    if appr.get("status") != "draft":
        raise ValueError("Only drafts can be deleted")
    await db[A].update_one({"_id": appr["_id"]}, {"$set": {"deleted": True, "updated_at": _now()}})
    vid = appr.get("vehicle_id")
    if vid:
        others = await db[A].count_documents({"vehicle_id": vid, "deleted": {"$ne": True}})
        if others == 0:
            await db[V].update_one({"_id": _oid(vid)}, {"$set": {"deleted": True, "appraisal_count": 0, "updated_at": _now()}})
        else:
            await db[V].update_one({"_id": _oid(vid)}, {"$set": {"appraisal_count": others, "updated_at": _now()}})
    await audit(db, appr, me, "draft_deleted")


# ---------- media ----------
def _kind(content_type: str, name: str) -> Optional[str]:
    ct = (content_type or "").lower()
    if ct.startswith("video/") or re.search(r"\.(mp4|mov|m4v|webm)$", (name or "").lower()):
        return "video"
    if ct.startswith("image/") or re.search(r"\.(jpe?g|png|webp|heic|heif)$", (name or "").lower()):
        return "image"
    return None


async def save_media(db, appr: dict, me: dict, *, role: str, source: str, data: bytes, content_type: str, name: str) -> dict:
    """Store one photo/video with provenance, then read it when it is a VIN or odometer photo. Same path for rep-captured and customer-sent."""
    if role not in ROLES:
        raise ValueError("Unknown media role")
    if source not in SOURCES:
        raise ValueError("Unknown media source")
    kind = _kind(content_type, name)
    if not kind:
        raise ValueError("Only photos and videos can be added to an appraisal")
    if len(data) > (MAX_VIDEO if kind == "video" else MAX_IMAGE):
        raise ValueError("That file is too large")
    mid = ObjectId()
    base = f"appraisals/{appr['user_id']}/{appr['_id']}/{mid}"
    thumb_path = None
    if kind == "image":
        try:
            data, thumb, _ = await asyncio.to_thread(_normalize_image, data)
        except Exception as e:
            raise ValueError(f"That image could not be read: {e}")
        content_type, path = "image/jpeg", f"{base}.jpg"
        thumb_path = f"{base}_thumb.jpg"
        await asyncio.to_thread(put_object, thumb_path, thumb, "image/jpeg")
    else:
        ext = "mp4" if "mp4" in (content_type or "") or (name or "").lower().endswith(".mp4") else "mov"
        path = f"{base}.{ext}"
    await asyncio.to_thread(put_object, path, data, content_type)
    now = _now()
    doc = {"_id": mid, "appraisal_id": str(appr["_id"]), "contact_id": appr["contact_id"], "vehicle_id": appr.get("vehicle_id"), "user_id": appr["user_id"],
           "store_id": appr.get("store_id"), "role": role, "source": source, "kind": kind, "name": (name or f"{role}.{path.rsplit('.', 1)[-1]}")[:120], "content_type": content_type,
           "size": len(data), "path": path, "thumb_path": thumb_path, "uploaded_by": str(me["_id"]), "uploaded_by_name": _name(me), "upload_token": None,
           "reading": None, "retain_original": True, "created_at": now}
    await db[M].insert_one(doc)
    reading = None
    if kind == "image" and role == "vin_photo":
        reading = await readers.vin_from_image(data)
    elif kind == "image" and role == "odometer_photo":
        reading = await readers.odometer_from_image(data)
    if reading is not None:
        await db[M].update_one({"_id": mid}, {"$set": {"reading": reading}})
        doc["reading"] = reading
    await audit(db, appr, me, "media_added", f"{ROLES[role]} · {SOURCES[source]}" + (f" · read {reading.get('vin') or reading.get('mileage')}" if reading and (reading.get('vin') or reading.get('mileage')) else ""),
                meta={"media_id": str(mid), "role": role, "source": source})
    return doc


async def list_media(db, appr: dict) -> list:
    rows = await db[M].find({"appraisal_id": str(appr["_id"]), "deleted": {"$ne": True}}).sort("created_at", 1).to_list(200)
    return [public_media(m) for m in rows]


# ---------- lists / search ----------
_STATUS_GROUPS = {"drafts": ["draft", "analyzing", "ready"], "waiting": ["submitted", "needs_info"], "approved": ["approved", "changed"], "completed": ["presented", "closed", "declined"]}


async def list_appraisals(db, me: dict, group: Optional[str] = None, q: str = "", date_from: Optional[datetime] = None, date_to: Optional[datetime] = None, limit: int = 60) -> dict:
    base = {"deleted": {"$ne": True}, **(await scope(me))}
    if group in _STATUS_GROUPS:
        base["status"] = {"$in": _STATUS_GROUPS[group]}
    if date_from or date_to:
        base["created_at"] = {k: v for k, v in (("$gte", date_from), ("$lte", date_to)) if v}
    q = (q or "").strip()
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        base["$or"] = [{"contact_name": rx}, {"vin": rx}, {"stock_number": rx}, {"user_name": rx}, {"vehicle.make": rx}, {"vehicle.model": rx}, {"vehicle.trim": rx}]
        if q.isdigit() and len(q) == 4:
            base["$or"].append({"vehicle.year": int(q)})
    rows = await db[A].find(base).sort("updated_at", -1).to_list(limit)
    counts = {}
    for g, sts in _STATUS_GROUPS.items():
        counts[g] = await db[A].count_documents({"deleted": {"$ne": True}, **(await scope(me)), "status": {"$in": sts}})
    return {"appraisals": [public_appraisal(a) for a in rows], "counts": counts}


# ---------- relationship intelligence (Jessi / Ask) ----------
async def for_context(db, contact_id: str) -> list:
    """One line per vehicle plus its appraisal history, oldest first, for the contact record Jessi reads."""
    out = []
    async for v in db[V].find({"contact_id": contact_id, "deleted": {"$ne": True}}).sort("created_at", 1):
        line = f"VEHICLE {vehicle_label(v)}" + (f" VIN {v['vin']}" if v.get("vin") else "") + (f", {v['current_mileage']:,} mi" if v.get("current_mileage") else "") + f", status {v.get('ownership_status') or 'owns'}"
        hist = []
        async for a in db[A].find({"vehicle_id": str(v["_id"]), "deleted": {"$ne": True}}).sort("created_at", 1):
            bits = [a["created_at"].strftime("%b %d, %Y"), a.get("status") or "draft"]
            if a.get("mileage_confirmed") is not None:
                bits.append(f"{a['mileage_confirmed']:,} mi")
            if a.get("approved_value"):
                bits.append(f"dealer offer ${a['approved_value']:,}")
            elif a.get("suggested_acv"):
                bits.append(f"suggested ${a['suggested_acv']:,}")
            if a.get("customer_expected_value"):
                bits.append(f"customer wanted ${a['customer_expected_value']:,}")
            if a.get("outcome"):
                bits.append(f"outcome {a['outcome']}")
            hist.append(" · ".join(bits))
        if hist:
            line += "\n  appraisals: " + " | ".join(hist)
        out.append({"vehicle_id": str(v["_id"]), "line": line, "created_at": v.get("created_at")})
    return out
