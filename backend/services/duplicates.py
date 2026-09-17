"""Duplicate contacts: find the sets (same phone, same email, same or sounds-alike name) and merge them.
Used by the cleanup screen (/contacts/duplicates) and by live Jessi ("do I have duplicates?", "merge them")."""
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

logger = logging.getLogger(__name__)

LIVE = {"$nin": ["hidden", "merged", "deleted"]}
FIELDS = {"_id": 1, "first_name": 1, "last_name": 1, "phone": 1, "email": 1, "user_id": 1, "tags": 1, "notes": 1, "source": 1, "created_at": 1,
          "photo_thumbnail": 1, "photo_url": 1, "possible_duplicate_of": 1, "vehicle": 1, "vehicle_interest": 1, "last_activity_at": 1, "updated_at": 1}
MIGRATE = ["messages", "contact_events", "conversations", "tasks", "campaign_enrollments", "campaign_pending_sends", "congrats_cards",
           "short_urls", "broadcast_messages", "inbound_leads", "voice_notes", "ai_reply_queue", "inventory_interest"]
COPY_FIELDS = ["vehicle", "email", "phone", "notes", "birthday", "anniversary", "photo_url", "photo_thumbnail"]
SOUNDS_ALIKE = 0.86


def _digits(p: Optional[str]) -> str:
    return re.sub(r"\D", "", p or "")


def _phone_key(p: Optional[str]) -> str:
    d = _digits(p)
    k = d[-10:] if len(d) >= 10 else d
    return k if len(k) >= 7 else ""


def name_of(c: dict) -> str:
    return f"{c.get('first_name') or ''} {c.get('last_name') or ''}".strip()


def _key(c: dict) -> str:
    from services.live_voice import _norm
    return _norm(name_of(c))


class _Union:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def join(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def _name_groups(rows: list) -> list:
    """Same normalized first+last name, or sounds alike (Tod/Todd Berry) inside the same last-name bucket. Needs both names."""
    from services.live_voice import _norm, _sim, _soundex
    uf = _Union()
    named = [c for c in rows if _norm(c.get("first_name") or "") and _norm(c.get("last_name") or "")]
    exact = {}
    for c in named:
        exact.setdefault(_key(c), []).append(c)
    for g in exact.values():
        for c in g[1:]:
            uf.join(str(g[0]["_id"]), str(c["_id"]))
    buckets = {}
    for c in named:
        buckets.setdefault(_soundex(_norm(c.get("last_name") or "")) + (_norm(c.get("first_name") or "")[:1]), []).append(c)
    alike = set()
    for g in buckets.values():
        if len(g) < 2 or len(g) > 60:
            continue
        for i in range(len(g)):
            for j in range(i + 1, len(g)):
                a, b = g[i], g[j]
                if _key(a) == _key(b):
                    continue
                if _sim(_norm(a.get("first_name") or ""), _norm(b.get("first_name") or "")) >= SOUNDS_ALIKE and _sim(_norm(a.get("last_name") or ""), _norm(b.get("last_name") or "")) >= SOUNDS_ALIKE:
                    uf.join(str(a["_id"]), str(b["_id"]))
                    alike.add(uf.find(str(a["_id"])))
    groups = {}
    for c in named:
        groups.setdefault(uf.find(str(c["_id"])), []).append(c)
    out = []
    for root, g in groups.items():
        if len(g) < 2:
            continue
        names = sorted({name_of(c) for c in g})
        label = f"Sounds alike: {' / '.join(names[:3])}" if len(names) > 1 else "Same name, different number"
        out.append(("name", label, g))
    return out


def _covered(g: list, groups: list) -> bool:
    ids = {str(c["_id"]) for c in g}
    return any(ids <= {str(c["_id"]) for c in og[2]} for og in groups)


async def _flagged_pairs(db, owners: list, rows: list) -> list:
    by_id = {str(c["_id"]): c for c in rows}
    out = []
    for c in rows:
        oid = c.get("possible_duplicate_of")
        if not oid or not ObjectId.is_valid(str(oid)):
            continue
        orig = by_id.get(str(oid)) or await db.contacts.find_one({"_id": ObjectId(str(oid)), "status": LIVE}, FIELDS)
        if orig:
            out.append(("name", "Same name, different number", [orig, c]))
    return out


def _activity(c: dict) -> Optional[datetime]:
    w = c.get("last_activity_at") or c.get("updated_at") or c.get("created_at")
    if isinstance(w, str):
        try:
            w = datetime.fromisoformat(w.replace("Z", "+00:00"))
        except ValueError:
            return None
    if isinstance(w, datetime) and w.tzinfo is None:
        w = w.replace(tzinfo=timezone.utc)
    return w if isinstance(w, datetime) else None


async def _enrich(db, c: dict, user_id: str) -> dict:
    cid = str(c["_id"])
    event_count = await db.contact_events.count_documents({"contact_id": cid})
    conv_count = await db.conversations.count_documents({"contact_id": cid})
    card_count = await db.congrats_cards.count_documents({"contact_id": cid})
    last_event = await db.contact_events.find_one({"contact_id": cid}, {"timestamp": 1}, sort=[("timestamp", -1)])
    created = c.get("created_at")
    return {"id": cid, "first_name": c.get("first_name", ""), "last_name": c.get("last_name", ""), "phone": c.get("phone", ""), "email": c.get("email", ""),
            "photo": c.get("photo_thumbnail") or c.get("photo_url"), "store_owned": str(c.get("user_id") or "") != user_id, "tags": c.get("tags", []), "notes": c.get("notes", ""),
            "source": c.get("source", ""), "vehicle": c.get("vehicle") or c.get("vehicle_interest") or "", "created_at": created.isoformat() if hasattr(created, "isoformat") else str(created or ""),
            "event_count": event_count, "conversation_count": conv_count, "card_count": card_count,
            "last_activity": last_event["timestamp"].isoformat() if last_event and last_event.get("timestamp") else None}


async def find_sets(db, user_id: str) -> list:
    """Every set of records that look like one person, most active record first. Each set: {phone, name, reason, reason_label, contacts[], _rows[]}."""
    from routers.contacts import _dup_owners
    owners, _sid, _role = await _dup_owners(db, user_id)
    rows = await db.contacts.find({"user_id": {"$in": owners}, "status": LIVE}, FIELDS).to_list(8000)
    groups = []
    by_phone = {}
    for c in rows:
        k = _phone_key(c.get("phone"))
        if k:
            by_phone.setdefault(k, []).append(c)
    groups += [("phone", "Same phone number", g) for g in by_phone.values() if len(g) >= 2]
    by_email = {}
    for c in rows:
        e = (c.get("email") or "").strip().lower()
        if e and "@" in e:
            by_email.setdefault(e, []).append(c)
    groups += [("email", "Same email", g) for g in by_email.values() if len(g) >= 2 and not _covered(g, groups)]
    for g in _name_groups(rows) + await _flagged_pairs(db, owners, rows):
        if not _covered(g[2], groups):
            groups.append(g)
    out = []
    for reason, label, g in groups:
        enriched = [await _enrich(db, c, user_id) for c in g]
        order = sorted(range(len(g)), key=lambda i: (-(enriched[i]["event_count"] + enriched[i]["conversation_count"] + enriched[i]["card_count"]), enriched[i]["store_owned"],
                                                    -((_activity(g[i]) or datetime.min.replace(tzinfo=timezone.utc)).timestamp())))
        enriched, raw = [enriched[i] for i in order], [g[i] for i in order]
        out.append({"phone": enriched[0]["phone"], "name": name_of(raw[0]), "contacts": enriched, "reason": reason, "reason_label": label, "_rows": raw})
    out.sort(key=lambda s: (-len(s["contacts"]), s["name"]))
    return out


def public(sets: list) -> list:
    return [{k: v for k, v in s.items() if not k.startswith("_")} for s in sets]


async def merge(db, user_id: str, primary_id: str, duplicate_id: str) -> dict:
    """Fold duplicate_id into primary_id: every linked record moves over, tags merge, missing fields copy, the duplicate is hidden as merged."""
    from routers.contacts import _dup_owners
    if not primary_id or not duplicate_id or primary_id == duplicate_id:
        raise ValueError("primary_id and duplicate_id must be two different contacts")
    owners, _sid, role = await _dup_owners(db, user_id)
    own = {} if role == "super_admin" else {"user_id": {"$in": owners}}
    primary = await db.contacts.find_one({"_id": ObjectId(primary_id), **own})
    duplicate = await db.contacts.find_one({"_id": ObjectId(duplicate_id), **own})
    if not primary:
        raise LookupError("Primary contact not found")
    if not duplicate:
        raise LookupError("Duplicate contact not found")
    now = datetime.now(timezone.utc)
    migrated = 0
    for col in MIGRATE:
        try:
            r = await db[col].update_many({"contact_id": duplicate_id}, {"$set": {"contact_id": primary_id}})
            migrated += r.modified_count
        except Exception:
            pass
    dup_tags = [t for t in duplicate.get("tags", []) if t != "Possible Duplicate"]
    if dup_tags:
        await db.contacts.update_one({"_id": ObjectId(primary_id)}, {"$addToSet": {"tags": {"$each": dup_tags}}})
    updates = {f: duplicate[f] for f in COPY_FIELDS if not primary.get(f) and duplicate.get(f)}
    if str(primary.get("user_id") or "") != user_id and role != "super_admin":
        updates["user_id"] = user_id
    await db.contacts.update_one({"_id": ObjectId(primary_id)}, {"$set": {**updates, "updated_at": now}, "$pull": {"tags": "Possible Duplicate"}, "$unset": {"possible_duplicate_of": ""}})
    await db.contacts.update_one({"_id": ObjectId(duplicate_id)}, {"$set": {"status": "merged", "merged_into": primary_id, "updated_at": now}})
    logger.info(f"[Merge] {duplicate_id} -> {primary_id} | {migrated} records migrated")
    return {"success": True, "records_migrated": migrated, "primary_id": primary_id}


async def merge_set(db, user_id: str, ids: list) -> dict:
    """Merge every id after the first into the first."""
    primary, migrated, merged = str(ids[0]), 0, 0
    for dup in ids[1:]:
        r = await merge(db, user_id, primary, str(dup))
        migrated += r["records_migrated"]
        merged += 1
    return {"primary_id": primary, "merged": merged, "records_migrated": migrated}
