"""One-way projection from the canonical facts into the legacy fields today's screens read (contacts.vehicle_interest, contacts.personal_details.*).
Only current facts project; proposed/disputed never do; nothing is blanked. Writes only when INTEL_LEGACY_PROJECTION is on (Phase 1B) or forced by a test."""
from bson import ObjectId

from services.intelligence import config, state
from services.intelligence import facts as F

SCALARS = {"family.spouse": "spouse_name", "work.occupation": "occupation", "work.employer": "employer", "contact.preferred_channel": "communication_preference",
           "identity.neighborhood": "neighborhood", "family.pet": "pets", "preference.restaurant": "favorite_restaurant", "preference.purchase_context": "purchase_context", "trade.vehicle": "trade_in"}
LISTS = {"preference.interest": "interests", "family.kid": "kids", "milestone.date": "important_dates"}
SNAPSHOTS = "intel_legacy_snapshots"


def _legacy_item(v):
    """Facts carry a `label` next to the original fields; legacy lists hold plain strings or the original dicts. Keep that shape exactly."""
    if not isinstance(v, dict):
        return v
    rest = {k: x for k, x in v.items() if k != "label"}
    return rest if rest else v.get("label")


def plan(st: dict) -> dict:
    """What the legacy fields would become from the current facts (pure function, used by the dry run too)."""
    sets: dict = {}
    for f in st["identity"] + st["current_state"]:
        if f["key"] in SCALARS:
            v = f["value"]
            sets[f"personal_details.{SCALARS[f['key']]}"] = v.get("label") if isinstance(v, dict) and "label" in v else v
    for key, field in LISTS.items():
        items = [_legacy_item(f["value"]) for f in st["identity"] + st["current_state"] if f["key"] == key and f["value"] not in (None, "")]
        if items:
            sets[f"personal_details.{field}"] = items
    drv = st.get("driving")
    if drv and drv["key"] == "vehicle.interest" and not (isinstance(drv.get("value"), dict) and drv["value"].get("from_comment")):
        sets["vehicle_interest"] = drv["label"]
    # ownership only projects once a person stood behind it (a sale, or the rep confirming on the vehicle page); appraisal records alone never do
    owned = [f for f in st["current_state"] if f["key"] == "vehicle.owned" and (f.get("confirmations") or 0) >= 1]
    if owned:
        sets["personal_details.vehicle_purchased"] = owned[0]["label"]
    for k in ("occupation", "employer"):
        if f"personal_details.{k}" in sets:
            sets[k] = sets[f"personal_details.{k}"]
    return sets


async def project(db, contact: dict, *, force: bool = False) -> dict:
    if not (force or config.projection_enabled()):
        return {"written": False, "sets": {}}
    settings = await config.settings(db, contact.get("store_id"))
    st = await state.build(db, contact, settings)
    sets = plan(st)
    if not sets:
        return {"written": False, "sets": {}}
    oid = ObjectId(str(contact["_id"]))
    await _snapshot(db, oid, sets)
    await db.contacts.update_one({"_id": oid}, {"$set": {**sets, "intel_projected_at": F.now_utc()}})
    return {"written": True, "sets": sets}


async def _snapshot(db, oid: ObjectId, sets: dict) -> None:
    """First projection on a contact keeps the pre-projection legacy values (one row per contact, never overwritten) so Phase 1B can be undone."""
    if await db[SNAPSHOTS].count_documents({"contact_id": str(oid)}, limit=1):
        return
    doc = await db.contacts.find_one({"_id": oid}, {"vehicle_interest": 1, "personal_details": 1, "occupation": 1, "employer": 1})
    if not doc:
        return
    before = {k: doc[k] for k in ("vehicle_interest", "personal_details", "occupation", "employer") if k in doc}
    missing = [k for k in ("vehicle_interest", "personal_details", "occupation", "employer") if k not in doc]
    await db[SNAPSHOTS].update_one({"contact_id": str(oid)}, {"$setOnInsert": {"contact_id": str(oid), "taken_at": F.now_utc(), "before": before, "missing": missing, "first_sets": list(sets.keys())}}, upsert=True)


async def rollback(db, *, contact_id: str | None = None) -> dict:
    """Put the legacy fields back exactly as they were before the first projection (keys that did not exist are removed again; facts untouched). Owner-only, explicit."""
    q = {"contact_id": contact_id} if contact_id else {}
    restored = 0
    async for s in db[SNAPSHOTS].find(q):
        upd: dict = {"$unset": {**{k: "" for k in (s.get("missing") or [])}, "intel_projected_at": ""}}
        if s.get("before"):
            upd["$set"] = s["before"]
        r = await db.contacts.update_one({"_id": ObjectId(s["contact_id"])}, upd)
        restored += r.matched_count
    deleted = await db[SNAPSHOTS].delete_many(q)
    return {"restored": restored, "snapshots_cleared": deleted.deleted_count}
