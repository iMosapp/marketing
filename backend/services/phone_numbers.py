"""Centralized phone number registry (collection `phone_numbers`): every Twilio number IMOS knows about, who owns it
(organization -> location -> user), its type, status and webhooks. The ORGANIZATION owns the number; users are assigned.
Legacy fields (users.twilio_number / mvpline_number / twilio_number_sid, phone_number_pool) are mirrored on every write so
the existing send / inbound / compliance code keeps working unchanged. Usage counters (usage_daily) live here too."""
import asyncio
import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

from services import twilio_tenant as tenant

logger = logging.getLogger(__name__)

COLL = "phone_numbers"
POOL = "phone_number_pool"
USAGE = "usage_daily"
TYPES = ("USER", "STORE", "SHARED", "CAMPAIGN", "VA")
STATUSES = ("AVAILABLE", "ASSIGNED", "SUSPENDED", "RELEASED")
MONTHLY_COST = 1.15
TYPE_LABEL = {"USER": "Rep number", "STORE": "Store number", "SHARED": "Shared inbox", "CAMPAIGN": "Campaign / shopper", "VA": "Virtual assistant"}


def _now():
    return datetime.now(timezone.utc)


def _oid(v) -> Optional[ObjectId]:
    return ObjectId(str(v)) if v and ObjectId.is_valid(str(v)) else None


def normalize(phone: str) -> str:
    from services.twilio_service import normalize_phone
    return normalize_phone(phone or "") if phone else ""


def _app_url() -> str:
    return (os.environ.get("PUBLIC_FACING_URL") or os.environ.get("APP_URL") or "https://app.imonsocial.com").rstrip("/")


def webhooks() -> dict:
    base = _app_url()
    return {"sms": f"{base}/api/webhooks/twilio/sms", "voice": f"{base}/api/webhooks/twilio/voice", "status": f"{base}/api/webhooks/twilio/status"}


def is_imos_webhook(url: str) -> bool:
    return bool(url) and "/api/webhooks/twilio/" in url and (url.startswith(_app_url()) or "imonsocial.com" in url)


def public(n: dict, owner: Optional[dict] = None, location: Optional[dict] = None) -> dict:
    d = {k: v for k, v in n.items() if k not in ("_id", "history")}
    d["id"] = str(n["_id"])
    d["type_label"] = TYPE_LABEL.get(n.get("number_type") or "", n.get("number_type"))
    d["owner_name"] = (owner or {}).get("name") or (owner or {}).get("email") or ""
    d["location_name"] = (location or {}).get("name") or ""
    d["dry_run"] = str(n.get("twilio_phone_number_sid") or "").startswith("PNdry")
    for k in ("created_at", "updated_at", "released_at", "assigned_at", "suspended_at"):
        if isinstance(d.get(k), datetime):
            d[k] = d[k].isoformat()
    return d


# ── lookups ───────────────────────────────────────────────────────────────────
async def get(db, number_id) -> Optional[dict]:
    o = _oid(number_id)
    return await db[COLL].find_one({"_id": o}) if o else None


async def by_phone(db, phone: str, include_released: bool = False) -> Optional[dict]:
    q: dict = {"phone_number": normalize(phone)}
    if not include_released:
        q["status"] = {"$ne": "RELEASED"}
    return await db[COLL].find_one(q, sort=[("updated_at", -1)])


async def by_sid(db, sid: str) -> Optional[dict]:
    return await db[COLL].find_one({"twilio_phone_number_sid": sid}) if sid else None


async def _decorate(db, rows: list) -> list:
    uids = {_oid(r.get("assigned_user_id")) for r in rows if _oid(r.get("assigned_user_id"))}
    sids = {_oid(r.get("location_id")) for r in rows if _oid(r.get("location_id"))}
    users = {str(u["_id"]): u async for u in db.users.find({"_id": {"$in": list(uids)}}, {"name": 1, "email": 1})} if uids else {}
    stores = {str(s["_id"]): s async for s in db.stores.find({"_id": {"$in": list(sids)}}, {"name": 1})} if sids else {}
    return [public(r, users.get(str(r.get("assigned_user_id") or "")), stores.get(str(r.get("location_id") or ""))) for r in rows]


async def list_for_org(db, org_id: str, include_released: bool = False) -> list:
    q: dict = {"organization_id": str(org_id)}
    if not include_released:
        q["status"] = {"$ne": "RELEASED"}
    rows = await db[COLL].find(q).sort([("status", 1), ("created_at", -1)]).to_list(500)
    return await _decorate(db, rows)


async def list_all(db, include_released: bool = False) -> list:
    q: dict = {} if include_released else {"status": {"$ne": "RELEASED"}}
    rows = await db[COLL].find(q).sort([("organization_id", 1), ("created_at", -1)]).to_list(2000)
    return await _decorate(db, rows)


async def for_store(db, store_id: str) -> list:
    """Active registry numbers that text for this store: pinned to the location, or assigned to one of its users."""
    sid = str(store_id)
    uids = [str(u["_id"]) async for u in db.users.find({"$or": [{"store_id": sid}, {"store_ids": sid}]}, {"_id": 1})]
    q = {"status": {"$ne": "RELEASED"}, "$or": [{"location_id": sid}, {"assigned_user_id": {"$in": uids}}]}
    return await db[COLL].find(q).to_list(200)


async def resolve_inbound(db, to_phone: str) -> Optional[dict]:
    """Twilio number -> organization -> location -> user. Server-side only, never from anything the client sends."""
    num = await by_phone(db, to_phone)
    if not num:
        return None
    org = await tenant.org_by_id(db, num.get("organization_id"))
    store = await db.stores.find_one({"_id": _oid(num.get("location_id"))}) if _oid(num.get("location_id")) else None
    user = None
    if num.get("status") == "ASSIGNED" and _oid(num.get("assigned_user_id")):
        user = await db.users.find_one({"_id": _oid(num["assigned_user_id"]), "status": {"$ne": "deactivated"}})
    if not store and user and _oid(user.get("store_id")):
        store = await db.stores.find_one({"_id": _oid(user["store_id"])})
    return {"number": num, "org": org, "store": store, "user": user}


# ── Twilio helpers ────────────────────────────────────────────────────────────
async def _tw(fn, *a, timeout: float = 20.0, **kw):
    return await asyncio.wait_for(asyncio.to_thread(fn, *a, **kw), timeout)


async def _client_for_number(db, num: dict, org: Optional[dict] = None):
    """The account that owns the number: its recorded account SID (subaccount or parent)."""
    acct = num.get("twilio_account_sid") or ""
    if acct and acct != tenant.parent_sid():
        o = org if org and (org.get(tenant.KEY) or {}).get("subaccount_sid") == acct else await tenant.org_by_account_sid(db, acct)
        if o:
            return tenant.client_for_org(o)
    return tenant.parent_client() if tenant.configured() else None


def _dry_sid(phone: str) -> str:
    return "PNdry" + hashlib.sha1(normalize(phone).encode()).hexdigest()[:29]


# ── search / suggestions ──────────────────────────────────────────────────────
def area_code_of(phone: str) -> str:
    d = re.sub(r"\D", "", phone or "")
    if len(d) == 11 and d.startswith("1"):
        return d[1:4]
    if len(d) == 10:
        return d[:3]
    return ""


async def suggest_area_codes(db, org: dict, store: Optional[dict] = None, user: Optional[dict] = None) -> list:
    """Local-number suggestions: the rep's own cell, the store's main line, the organization's phone, then what the org already uses."""
    out, seen = [], set()

    def add(ac: str, reason: str):
        if ac and ac not in seen:
            seen.add(ac)
            out.append({"area_code": ac, "reason": reason})

    if user:
        add(area_code_of(user.get("phone") or user.get("cell_phone") or ""), f"{(user.get('name') or 'This rep').split()[0]}'s cell")
    if store:
        add(area_code_of(store.get("phone") or ""), f"{store.get('name') or 'Store'} main line")
    if not store and user and _oid(user.get("store_id")):
        s = await db.stores.find_one({"_id": _oid(user["store_id"])}, {"name": 1, "phone": 1})
        if s:
            add(area_code_of(s.get("phone") or ""), f"{s.get('name') or 'Store'} main line")
    add(area_code_of((org or {}).get("admin_phone") or ""), "Organization phone")
    if org:
        async for s in db.stores.find({"organization_id": str(org["_id"])}, {"name": 1, "phone": 1}).limit(20):
            add(area_code_of(s.get("phone") or ""), f"{s.get('name') or 'Location'} main line")
        counts: dict = {}
        async for n in db[COLL].find({"organization_id": str(org["_id"]), "status": {"$ne": "RELEASED"}}, {"phone_number": 1}):
            ac = area_code_of(n["phone_number"])
            counts[ac] = counts.get(ac, 0) + 1
        for ac, _ in sorted(counts.items(), key=lambda kv: -kv[1]):
            add(ac, "Other numbers in this organization")
    return out[:6]


async def search(db, org: Optional[dict], area_code: str = "", contains: str = "", sms: bool = True, mms: bool = True, voice: bool = True,
                 locality: str = "", region: str = "", country: str = "US", limit: int = 10) -> dict:
    area_code = re.sub(r"\D", "", area_code or "")[:3]
    if await tenant.dry_run(db):
        ac = area_code or "801"
        nums = [{"phone_number": f"+1{ac}555{100 + i:04d}", "friendly_name": f"({ac}) 555-{100 + i:04d}", "locality": locality or "Dry run", "region": region or "UT",
                 "capabilities": {"sms": True, "mms": True, "voice": True}, "monthly_cost_usd": MONTHLY_COST} for i in range(min(limit, 6))]
        return {"numbers": nums, "dry_run": True}
    c = tenant.client_for_org(org)
    if not c:
        raise ValueError("Twilio is not configured on this server")
    params: dict = {"limit": max(1, min(limit, 30)), "sms_enabled": bool(sms), "mms_enabled": bool(mms), "voice_enabled": bool(voice)}
    if area_code:
        params["area_code"] = area_code
    if contains:
        params["contains"] = contains
    if locality:
        params["in_locality"] = locality
    if region:
        params["in_region"] = region
    found = await _tw(lambda: c.available_phone_numbers(country).local.list(**params), timeout=20)
    return {"numbers": [{"phone_number": n.phone_number, "friendly_name": n.friendly_name, "locality": n.locality, "region": n.region,
                         "capabilities": {"sms": n.capabilities.get("SMS", False), "mms": n.capabilities.get("MMS", False), "voice": n.capabilities.get("voice", False)},
                         "monthly_cost_usd": MONTHLY_COST} for n in found], "dry_run": False}


# ── legacy mirrors ────────────────────────────────────────────────────────────
async def _mirror_user_set(db, user_id: str, phone: str, sid: str):
    await db.users.update_many({"$or": [{"twilio_number": phone}, {"mvpline_number": phone}], "_id": {"$ne": _oid(user_id)}},
                               {"$unset": {"mvpline_number": "", "twilio_number": "", "twilio_number_sid": ""}})
    await db.users.update_one({"_id": _oid(user_id)}, {"$set": {"twilio_number": phone, "mvpline_number": phone, "twilio_number_sid": sid, "updated_at": _now()}})


async def _mirror_user_unset(db, phone: str):
    await db.users.update_many({"$or": [{"twilio_number": phone}, {"mvpline_number": phone}]},
                               {"$unset": {"mvpline_number": "", "twilio_number": "", "twilio_number_sid": ""}})


async def _mirror_pool(db, num: dict, status: str, extra: Optional[dict] = None):
    legacy = {"ASSIGNED": "assigned", "AVAILABLE": "pool", "SUSPENDED": "suspended", "RELEASED": "released"}[status]
    sets = {"phone_number": num["phone_number"], "status": legacy, "assigned_user_id": num.get("assigned_user_id") if status == "ASSIGNED" else None,
            "purpose": (num.get("number_type") or "USER").lower(), "registry_id": str(num["_id"]), "updated_at": _now(), **(extra or {})}
    await db[POOL].update_one({"twilio_sid": num["twilio_phone_number_sid"]}, {"$set": sets, "$setOnInsert": {"twilio_sid": num["twilio_phone_number_sid"], "purchased_at": num.get("created_at") or _now(), "monthly_cost": MONTHLY_COST}}, upsert=True)


def _h(num: dict, action: str, actor, note: str = "") -> list:
    h = list(num.get("history") or [])
    h.append({"at": _now(), "action": action, **tenant._actor(actor), "note": (note or "")[:300]})
    return h[-60:]


async def _save(db, num: dict, sets: dict, action: str, actor, note: str = "") -> dict:
    sets = {**sets, "updated_at": _now(), "history": _h(num, action, actor, note)}
    await db[COLL].update_one({"_id": num["_id"]}, {"$set": sets})
    return {**num, **sets}


# ── lifecycle ─────────────────────────────────────────────────────────────────
async def _check_user(db, org: Optional[dict], user_id: Optional[str]) -> Optional[dict]:
    if not user_id:
        return None
    user = await db.users.find_one({"_id": _oid(user_id)}) if _oid(user_id) else None
    if not user:
        raise ValueError("That user does not exist")
    if org and user.get("organization_id") and str(user["organization_id"]) != str(org["_id"]):
        raise ValueError(f"{user.get('name') or 'That user'} belongs to another organization")
    return user


async def _service_for(db, org: Optional[dict], location_id: Optional[str]) -> str:
    if org:
        ms = (org.get(tenant.KEY) or {}).get("messaging_service_sid")
        if ms:
            return ms
    if _oid(location_id):
        s = await db.stores.find_one({"_id": _oid(location_id)}, {"compliance.sids": 1})
        return (((s or {}).get("compliance") or {}).get("sids") or {}).get("messaging_service") or ""
    if org:
        s = await tenant.compliance_store(db, org)
        return (((s or {}).get("compliance") or {}).get("sids") or {}).get("messaging_service") or ""
    return ""


async def purchase(db, *, org: Optional[dict], phone_number: str, number_type: str = "USER", location_id: Optional[str] = None,
                    assigned_user_id: Optional[str] = None, actor=None, friendly_name: str = "", voice_enabled: bool = True) -> dict:
    """Buy under the organization's account, set the IMOS webhooks, attach to its Messaging Service, register, mirror legacy fields."""
    phone = normalize(phone_number)
    if not re.fullmatch(r"\+\d{8,15}", phone):
        raise ValueError("phone_number must be a full number like +18015550100")
    number_type = (number_type or "USER").upper()
    if number_type not in TYPES:
        raise ValueError(f"number_type must be one of {', '.join(TYPES)}")
    if await by_phone(db, phone):
        raise ValueError(f"{phone} is already in the registry")
    user = await _check_user(db, org, assigned_user_id)
    if user and not location_id:
        location_id = user.get("store_id") or None
    if location_id and org:
        loc = await db.stores.find_one({"_id": _oid(location_id)}, {"organization_id": 1})
        if not loc or str(loc.get("organization_id") or "") != str(org["_id"]):
            raise ValueError("That location is not part of this organization")
    hooks = webhooks()
    label = friendly_name or f"IMOS {(org or {}).get('name') or 'platform'} · {(user or {}).get('name') or TYPE_LABEL[number_type]}"
    dry = await tenant.dry_run(db)
    if dry:
        sid, account_sid, caps = _dry_sid(phone), tenant.creds_for_org(org)[0] or "ACdry", {"sms": True, "mms": True, "voice": True}
    else:
        c = tenant.client_for_org(org)
        if not c:
            raise ValueError("Twilio is not configured on this server")
        params = {"phone_number": phone, "friendly_name": label[:64], "sms_url": hooks["sms"], "sms_method": "POST"}
        if voice_enabled:
            params.update({"voice_url": hooks["voice"], "voice_method": "POST"})
        created = await _tw(c.incoming_phone_numbers.create, timeout=30, **params)
        sid, account_sid = created.sid, created.account_sid
        caps = {"sms": bool((created.capabilities or {}).get("sms")), "mms": bool((created.capabilities or {}).get("mms")), "voice": bool((created.capabilities or {}).get("voice"))}
    ms_sid = await _service_for(db, org, location_id)
    now = _now()
    doc = {"organization_id": str(org["_id"]) if org else None, "location_id": str(location_id) if location_id else None,
           "assigned_user_id": str(user["_id"]) if user else None, "twilio_phone_number_sid": sid, "twilio_account_sid": account_sid,
           "phone_number": phone, "friendly_name": label, "number_type": number_type,
           "sms_enabled": caps["sms"], "mms_enabled": caps["mms"], "voice_enabled": caps["voice"] and voice_enabled,
           "messaging_service_sid": "", "incoming_sms_webhook": hooks["sms"], "incoming_voice_webhook": hooks["voice"] if voice_enabled else "",
           "status": "ASSIGNED" if user else "AVAILABLE", "monthly_cost_usd": MONTHLY_COST, "created_at": now, "updated_at": now,
           "assigned_at": now if user else None, "history": [{"at": now, "action": "purchased", **tenant._actor(actor), "note": "dry run" if dry else ""}]}
    res = await db[COLL].insert_one(doc)
    doc["_id"] = res.inserted_id
    if ms_sid:
        try:
            doc = await attach_to_service(db, doc, ms_sid, org=org)
        except Exception as e:
            logger.warning(f"[Numbers] attach {phone} to {ms_sid}: {e}")
    if user:
        await _mirror_user_set(db, str(user["_id"]), phone, sid)
    await _mirror_pool(db, doc, doc["status"], {"webhook_url": hooks["sms"], "organization_id": doc["organization_id"]})
    await tenant.audit(db, action="number_purchased", actor=actor, org_id=doc["organization_id"],
                       target={"phone_number": phone, "sid": sid, "account_sid": account_sid, "number_id": str(doc["_id"])},
                       details={"number_type": number_type, "assigned_user_id": doc["assigned_user_id"], "location_id": doc["location_id"], "dry_run": dry})
    return public(doc, user)


async def attach_to_service(db, num: dict, ms_sid: str, org: Optional[dict] = None) -> dict:
    if not ms_sid or num.get("messaging_service_sid") == ms_sid:
        return num
    sid = num["twilio_phone_number_sid"]
    if not sid.startswith("PNdry") and not ms_sid.startswith("MGdry") and not await tenant.dry_run(db):
        c = await _client_for_number(db, num, org)
        if c:
            try:
                await _tw(c.messaging.v1.services(ms_sid).phone_numbers.create, phone_number_sid=sid)
            except Exception as e:
                if "already" not in str(e).lower() and "21710" not in str(e):
                    raise
    return await _save(db, num, {"messaging_service_sid": ms_sid}, "attached_to_service", "system", ms_sid)


async def assign(db, num: dict, user_id: str, actor=None) -> dict:
    if num.get("status") == "RELEASED":
        raise ValueError("This number was released")
    org = await tenant.org_by_id(db, num.get("organization_id"))
    user = await _check_user(db, org, user_id)
    previous = num.get("assigned_user_id")
    if previous == str(user["_id"]) and num.get("status") == "ASSIGNED":
        return num
    sets = {"assigned_user_id": str(user["_id"]), "status": "ASSIGNED", "assigned_at": _now(), "suspended_at": None}
    if not num.get("location_id") and user.get("store_id"):
        sets["location_id"] = str(user["store_id"])
    if num.get("number_type") in ("STORE", "SHARED") and not previous:
        sets["number_type"] = "USER"
    action = "number_reassigned" if previous else "number_assigned"
    out = await _save(db, num, sets, action, actor, f"{previous or 'pool'} -> {user['_id']}")
    await _mirror_user_set(db, str(user["_id"]), num["phone_number"], num["twilio_phone_number_sid"])
    await _mirror_pool(db, out, "ASSIGNED", {"assigned_at": _now()})
    await tenant.audit(db, action=action, actor=actor, org_id=num.get("organization_id"), target={"phone_number": num["phone_number"], "number_id": str(num["_id"])},
                       details={"from_user_id": previous, "to_user_id": str(user["_id"]), "to_user_name": user.get("name")})
    return out


async def unassign(db, num: dict, actor=None, reason: str = "") -> dict:
    if num.get("status") == "RELEASED":
        raise ValueError("This number was released")
    previous = num.get("assigned_user_id")
    prev_user = await db.users.find_one({"_id": _oid(previous)}, {"name": 1, "email": 1, "store_id": 1}) if _oid(previous) else None
    out = await _save(db, num, {"assigned_user_id": None, "status": "AVAILABLE", "previous_user_id": previous, "previous_user_name": (prev_user or {}).get("name")}, "number_unassigned", actor, reason)
    await _mirror_user_unset(db, num["phone_number"])
    await _mirror_pool(db, out, "AVAILABLE", {"previous_user_id": previous, "previous_user_name": (prev_user or {}).get("name"), "previous_user_email": (prev_user or {}).get("email"),
                                              "previous_store_id": num.get("location_id") or (prev_user or {}).get("store_id"), "released_at": _now(), "released_by": tenant._actor(actor)["actor_id"] or "system"})
    await tenant.audit(db, action="number_unassigned", actor=actor, org_id=num.get("organization_id"), target={"phone_number": num["phone_number"], "number_id": str(num["_id"])},
                       details={"from_user_id": previous, "reason": reason})
    return out


async def unassign_user(db, user_id: str, actor=None, reason: str = "") -> int:
    """Every registry number a departing user held goes back to the organization (AVAILABLE). History stays on the messages."""
    n = 0
    async for num in db[COLL].find({"assigned_user_id": str(user_id), "status": {"$in": ["ASSIGNED", "SUSPENDED"]}}):
        await unassign(db, num, actor, reason)
        n += 1
    return n


async def suspend(db, num: dict, actor=None, reason: str = "") -> dict:
    if num.get("status") in ("RELEASED", "SUSPENDED"):
        raise ValueError(f"This number is already {num.get('status', '').lower()}")
    out = await _save(db, num, {"status": "SUSPENDED", "suspended_at": _now(), "suspended_from_user_id": num.get("assigned_user_id")}, "number_suspended", actor, reason)
    await _mirror_user_unset(db, num["phone_number"])
    await _mirror_pool(db, out, "SUSPENDED")
    await tenant.audit(db, action="number_suspended", actor=actor, org_id=num.get("organization_id"), target={"phone_number": num["phone_number"], "number_id": str(num["_id"])}, details={"reason": reason})
    return out


async def reactivate(db, num: dict, actor=None) -> dict:
    if num.get("status") != "SUSPENDED":
        raise ValueError("Only a suspended number can be reactivated")
    uid = num.get("assigned_user_id")
    user = await db.users.find_one({"_id": _oid(uid), "status": {"$ne": "deactivated"}}) if _oid(uid) else None
    status = "ASSIGNED" if user else "AVAILABLE"
    out = await _save(db, num, {"status": status, "suspended_at": None, "assigned_user_id": str(user["_id"]) if user else None}, "number_reactivated", actor)
    if user:
        await _mirror_user_set(db, str(user["_id"]), num["phone_number"], num["twilio_phone_number_sid"])
    await _mirror_pool(db, out, status)
    await tenant.audit(db, action="number_reactivated", actor=actor, org_id=num.get("organization_id"), target={"phone_number": num["phone_number"], "number_id": str(num["_id"])})
    return out


async def release(db, num: dict, actor=None, reason: str = "") -> dict:
    """Permanent: the number goes back to Twilio, billing stops, it cannot be ported afterwards."""
    if num.get("status") == "RELEASED":
        return num
    sid = num["twilio_phone_number_sid"]
    if not sid.startswith("PNdry") and not await tenant.dry_run(db):
        c = await _client_for_number(db, num)
        if c:
            try:
                await _tw(c.incoming_phone_numbers(sid).delete, timeout=30)
            except Exception as e:
                if "20404" not in str(e) and "not found" not in str(e).lower():
                    raise
    out = await _save(db, num, {"status": "RELEASED", "released_at": _now(), "previous_user_id": num.get("assigned_user_id"), "assigned_user_id": None, "messaging_service_sid": ""}, "number_released", actor, reason)
    await _mirror_user_unset(db, num["phone_number"])
    await _mirror_pool(db, out, "RELEASED", {"released_at": _now(), "released_by": tenant._actor(actor)["actor_id"] or "system"})
    await tenant.audit(db, action="number_released", actor=actor, org_id=num.get("organization_id"), target={"phone_number": num["phone_number"], "sid": sid, "number_id": str(num["_id"])}, details={"reason": reason})
    return out


async def adopt(db, *, phone_number: str, sid: str, account_sid: str = "", org_id: Optional[str] = None, location_id: Optional[str] = None,
                assigned_user_id: Optional[str] = None, number_type: str = "USER", friendly_name: str = "", sms_url: str = "", voice_url: str = "",
                messaging_service_sid: str = "", actor=None, note: str = "") -> dict:
    """Register a number that already exists in Twilio (migration import, legacy purchase path). Never touches Twilio."""
    phone = normalize(phone_number)
    existing = await by_sid(db, sid) if sid else await by_phone(db, phone, include_released=True)
    now = _now()
    status = "ASSIGNED" if assigned_user_id else "AVAILABLE"
    sets = {"organization_id": str(org_id) if org_id else None, "location_id": str(location_id) if location_id else None, "assigned_user_id": str(assigned_user_id) if assigned_user_id else None,
            "twilio_phone_number_sid": sid or existing and existing.get("twilio_phone_number_sid") or _dry_sid(phone), "twilio_account_sid": account_sid or tenant.parent_sid(),
            "phone_number": phone, "friendly_name": friendly_name or phone, "number_type": number_type if number_type in TYPES else "USER",
            "messaging_service_sid": messaging_service_sid or (existing or {}).get("messaging_service_sid") or "", "incoming_sms_webhook": sms_url or (existing or {}).get("incoming_sms_webhook") or "",
            "incoming_voice_webhook": voice_url or (existing or {}).get("incoming_voice_webhook") or "", "status": status, "updated_at": now}
    if existing:
        await db[COLL].update_one({"_id": existing["_id"]}, {"$set": sets, "$push": {"history": {"at": now, "action": "imported", **tenant._actor(actor), "note": note[:300]}}})
        doc = {**existing, **sets}
    else:
        doc = {**sets, "sms_enabled": True, "mms_enabled": True, "voice_enabled": bool(voice_url), "monthly_cost_usd": MONTHLY_COST, "created_at": now,
               "history": [{"at": now, "action": "imported", **tenant._actor(actor), "note": note[:300]}]}
        res = await db[COLL].insert_one(doc)
        doc["_id"] = res.inserted_id
    await tenant.audit(db, action="number_imported", actor=actor, org_id=doc.get("organization_id"), target={"phone_number": phone, "sid": doc["twilio_phone_number_sid"], "number_id": str(doc["_id"])}, details={"number_type": doc["number_type"], "updated": bool(existing)})
    return doc


# ── migration report (Phase 9) ────────────────────────────────────────────────
async def _twilio_inventory() -> tuple[dict, str]:
    if not tenant.configured():
        return {}, "Twilio credentials are not configured; DB-only report"
    try:
        rows = await _tw(tenant.parent_client().incoming_phone_numbers.list, timeout=25)
        return {normalize(r.phone_number): {"sid": r.sid, "account_sid": r.account_sid, "sms_url": r.sms_url or "", "voice_url": r.voice_url or "", "friendly_name": r.friendly_name or ""} for r in rows}, ""
    except Exception as e:
        return {}, f"Could not list Twilio numbers ({tenant._friendly(e)}); DB-only report"


async def migration_report(db) -> dict:
    """Every number IMOS or Twilio knows about, mapped to org / store / user / Messaging Service / webhook. Read-only."""
    twilio, note = await _twilio_inventory()
    rows: dict = {}

    def row(phone: str) -> dict:
        return rows.setdefault(phone, {"phone_number": phone, "sources": [], "sid": "", "account_sid": "", "organization_id": None, "organization_name": "",
                                       "store_id": None, "store_name": "", "user_id": None, "user_name": "", "user_status": "", "number_type": "STORE",
                                       "messaging_service_sid": "", "webhook_sms_url": "", "webhook_ok": None, "in_twilio": False, "in_registry": False, "registry_status": "", "issues": []})

    stores = {str(s["_id"]): s async for s in db.stores.find({}, {"name": 1, "organization_id": 1, "compliance.sids": 1, "compliance.numbers_on_service": 1})}
    orgs = {str(o["_id"]): o async for o in db.organizations.find({}, {"name": 1})}
    service_of_sid = {}
    for s in stores.values():
        ms = (((s.get("compliance") or {}).get("sids")) or {}).get("messaging_service")
        for sid in ((s.get("compliance") or {}).get("numbers_on_service") or []):
            if ms:
                service_of_sid[sid] = ms

    async for u in db.users.find({"$or": [{"twilio_number": {"$nin": [None, ""]}}, {"mvpline_number": {"$nin": [None, ""]}}]}, {"name": 1, "email": 1, "twilio_number": 1, "mvpline_number": 1, "twilio_number_sid": 1, "store_id": 1, "organization_id": 1, "status": 1}):
        phone = normalize(u.get("twilio_number") or u.get("mvpline_number"))
        r = row(phone)
        r["sources"].append("users.twilio_number")
        r.update({"sid": r["sid"] or u.get("twilio_number_sid") or "", "user_id": str(u["_id"]), "user_name": u.get("name") or u.get("email") or "", "user_status": u.get("status") or "active", "number_type": "USER"})
        st = stores.get(str(u.get("store_id") or ""))
        if st:
            r.update({"store_id": str(st["_id"]), "store_name": st.get("name") or ""})
        org_id = str(u.get("organization_id") or (st or {}).get("organization_id") or "") or None
        if org_id:
            r.update({"organization_id": org_id, "organization_name": (orgs.get(org_id) or {}).get("name") or ""})
    async for ib in db.shared_inboxes.find({"phone_number": {"$nin": [None, ""]}}, {"name": 1, "phone_number": 1, "store_id": 1, "twilio_sid": 1}):
        r = row(normalize(ib["phone_number"]))
        r["sources"].append(f"shared_inboxes ({ib.get('name') or 'inbox'})")
        r["number_type"] = "SHARED"
        r["sid"] = r["sid"] or ib.get("twilio_sid") or ""
        st = stores.get(str(ib.get("store_id") or ""))
        if st and not r["store_id"]:
            r.update({"store_id": str(st["_id"]), "store_name": st.get("name") or ""})
            if st.get("organization_id") and not r["organization_id"]:
                r.update({"organization_id": str(st["organization_id"]), "organization_name": (orgs.get(str(st["organization_id"])) or {}).get("name") or ""})
    async for p in db[POOL].find({"phone_number": {"$nin": [None, ""]}}):
        r = row(normalize(p["phone_number"]))
        r["sources"].append(f"phone_number_pool ({p.get('status') or '?'}{', ' + p['purpose'] if p.get('purpose') else ''})")
        r["sid"] = r["sid"] or p.get("twilio_sid") or ""
        if (p.get("purpose") or "") in ("lead_shop", "mystery_shop", "mystery_shop_client"):
            r["number_type"] = "CAMPAIGN"
        if not r["store_id"] and p.get("previous_store_id") and stores.get(str(p["previous_store_id"])):
            st = stores[str(p["previous_store_id"])]
            r.update({"store_id": str(st["_id"]), "store_name": st.get("name") or "", "organization_id": r["organization_id"] or (str(st["organization_id"]) if st.get("organization_id") else None)})
            r["organization_name"] = r["organization_name"] or (orgs.get(r["organization_id"] or "") or {}).get("name") or ""
    async for c in db.shop_clients.find({"from_number": {"$nin": [None, ""]}}, {"name": 1, "from_number": 1}):
        r = row(normalize(c["from_number"]))
        r["sources"].append(f"shop_clients ({c.get('name') or 'client'})")
        r["number_type"] = "CAMPAIGN"
    platform = normalize(os.environ.get("TWILIO_PHONE_NUMBER") or "") if os.environ.get("TWILIO_PHONE_NUMBER") else ""
    if platform:
        r = row(platform)
        r["sources"].append("TWILIO_PHONE_NUMBER (platform)")
        r["number_type"] = "CAMPAIGN"
    async for n in db[COLL].find({}):
        r = row(n["phone_number"])
        r["sources"].append("phone_numbers registry")
        r.update({"in_registry": True, "registry_status": n.get("status") or "", "sid": r["sid"] or n.get("twilio_phone_number_sid") or ""})
        if not r["organization_id"] and n.get("organization_id"):
            r.update({"organization_id": n["organization_id"], "organization_name": (orgs.get(n["organization_id"]) or {}).get("name") or ""})
    for phone, t in twilio.items():
        r = row(phone)
        r.update({"in_twilio": True, "sid": t["sid"], "account_sid": t["account_sid"], "webhook_sms_url": t["sms_url"], "webhook_ok": is_imos_webhook(t["sms_url"])})
        if not r["sources"]:
            r["sources"].append("Twilio only")
    for r in rows.values():
        r["messaging_service_sid"] = service_of_sid.get(r["sid"], "")
        if twilio and not r["in_twilio"] and not str(r["sid"]).startswith("PNdry"):
            r["issues"].append("Not found in the Twilio account")
        if r["in_twilio"] and r["webhook_ok"] is False:
            r["issues"].append("Inbound webhook is not IMOS")
        if not r["organization_id"] and r["number_type"] in ("USER", "STORE", "SHARED"):
            r["issues"].append("No organization mapped")
        if r["user_status"] == "deactivated":
            r["issues"].append("Assigned to a deactivated user")
        if len([s for s in r["sources"] if s.startswith("users.")]) > 1:
            r["issues"].append("Held by more than one user")
        if not r["sid"]:
            r["issues"].append("No Twilio SID on file")
        if not r["in_registry"]:
            r["issues"].append("Not in the registry yet")
        r["proposed_action"] = "already registered" if r["in_registry"] else (
            "import" if r["sid"] and (r["in_twilio"] or not twilio) and (r["organization_id"] or r["number_type"] == "CAMPAIGN") else "review")
    out = sorted(rows.values(), key=lambda r: (r["in_registry"], r["organization_name"], r["phone_number"]))
    summary = {"total": len(out), "in_twilio": sum(1 for r in out if r["in_twilio"]), "in_registry": sum(1 for r in out if r["in_registry"]),
               "importable": sum(1 for r in out if r["proposed_action"] == "import"), "needs_review": sum(1 for r in out if r["proposed_action"] == "review"),
               "webhook_wrong": sum(1 for r in out if r["webhook_ok"] is False), "no_org": sum(1 for r in out if "No organization mapped" in r["issues"])}
    return {"rows": out, "summary": summary, "twilio_reachable": bool(twilio), "note": note, "generated_at": _now().isoformat(), "webhooks": webhooks()}


async def import_report(db, actor=None, phones: Optional[list] = None) -> dict:
    """Register the importable rows (or the given phones). Nothing is moved or released in Twilio."""
    rep = await migration_report(db)
    if phones is not None and not phones:
        return {"imported": [], "skipped": [], "count": 0}
    wanted = {normalize(p) for p in (phones or [])}
    done, skipped = [], []
    for r in rep["rows"]:
        if wanted and r["phone_number"] not in wanted:
            continue
        if r["in_registry"] and not wanted:
            continue
        if not r["sid"]:
            skipped.append({"phone_number": r["phone_number"], "why": "no SID"})
            continue
        await adopt(db, phone_number=r["phone_number"], sid=r["sid"], account_sid=r["account_sid"], org_id=r["organization_id"], location_id=r["store_id"],
                    assigned_user_id=r["user_id"] if r["user_status"] != "deactivated" else None, number_type=r["number_type"], sms_url=r["webhook_sms_url"],
                    messaging_service_sid=r["messaging_service_sid"], actor=actor, note="migration import: " + ", ".join(r["sources"])[:200])
        done.append(r["phone_number"])
    return {"imported": done, "skipped": skipped, "count": len(done)}


# ── usage (Phase 7) ───────────────────────────────────────────────────────────
async def record_usage(db, *, direction: str, phone_number: str, segments: int = 1, mms: bool = False, org_id: Optional[str] = None,
                       location_id: Optional[str] = None, user_id: Optional[str] = None, price_usd: Optional[float] = None):
    """One $inc per message into usage_daily {org, location, user, number, day}. Best effort, never raises."""
    try:
        phone = normalize(phone_number) if phone_number else ""
        if phone and not (org_id and user_id):
            num = await by_phone(db, phone)
            if num:
                org_id = org_id or num.get("organization_id")
                location_id = location_id or num.get("location_id")
                user_id = user_id or num.get("assigned_user_id")
        d = "out" if direction == "outbound" else "in"
        inc = {f"sms_{d}": 0 if mms else 1, f"mms_{d}": 1 if mms else 0, f"segments_{d}": max(1, int(segments or 1)), "messages": 1}
        if price_usd:
            inc["cost_usd"] = round(abs(float(price_usd)), 5)
        day = _now().strftime("%Y-%m-%d")
        await db[USAGE].update_one({"organization_id": str(org_id) if org_id else None, "location_id": str(location_id) if location_id else None,
                                    "user_id": str(user_id) if user_id else None, "phone_number": phone or None, "day": day},
                                   {"$inc": inc, "$set": {"updated_at": _now()}}, upsert=True)
    except Exception as e:
        logger.debug(f"[Usage] skipped: {e}")


async def usage_summary(db, org_id: Optional[str], month: Optional[str] = None) -> dict:
    month = month or _now().strftime("%Y-%m")
    match: dict = {"day": {"$regex": f"^{month}"}}
    if org_id:
        match["organization_id"] = str(org_id)
    fields = ("sms_out", "sms_in", "mms_out", "mms_in", "segments_out", "segments_in", "messages", "cost_usd")
    group = {f: {"$sum": f"${f}"} for f in fields}
    totals = {f: 0 for f in fields}
    async for r in db[USAGE].aggregate([{"$match": match}, {"$group": {"_id": None, **group}}]):
        totals = {f: r.get(f, 0) or 0 for f in fields}
    per_number = [{"phone_number": r["_id"], **{f: r.get(f, 0) or 0 for f in fields}} async for r in db[USAGE].aggregate([{"$match": match}, {"$group": {"_id": "$phone_number", **group}}, {"$sort": {"messages": -1}}, {"$limit": 50}])]
    per_user = [{"user_id": r["_id"], **{f: r.get(f, 0) or 0 for f in fields}} async for r in db[USAGE].aggregate([{"$match": match}, {"$group": {"_id": "$user_id", **group}}, {"$sort": {"messages": -1}}, {"$limit": 50}])]
    active = await db[COLL].count_documents({**({"organization_id": str(org_id)} if org_id else {}), "status": {"$ne": "RELEASED"}})
    totals["cost_usd"] = round(float(totals.get("cost_usd") or 0), 4)
    return {"month": month, "totals": totals, "per_number": per_number, "per_user": per_user, "numbers_active": active, "numbers_monthly_cost_usd": round(active * MONTHLY_COST, 2)}
