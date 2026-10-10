"""Time-aware customer facts (contact_facts) and the status engine.
A fact keeps what was said, where it came from, when it happened, when we learned it, how sure we are and whether it is still current.
Nothing is deleted: a newer fact supersedes, a weaker one is disputed, an older arrival becomes history. Every status change is audited in contact_fact_events."""
import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

from services.intelligence import conflict

logger = logging.getLogger(__name__)
FACTS, EVENTS = "contact_facts", "contact_fact_events"
LAYERS = ("identity", "history", "state", "intent")
STATUSES = ("current", "historical", "disputed", "superseded", "retired", "proposed")
CONFIDENCE = {"high": 0.9, "medium": 0.65, "low": 0.35}
# How much a source can be trusted when two facts disagree (higher wins). The customer's own words beat the rep's memory; system records beat both.
RELIABILITY = {"sale": 5, "appraisal": 5, "appointment": 4, "lead_form": 4, "message": 4, "call": 4, "rep": 3, "voice_memo": 3, "crm_sync": 2, "import": 2, "ai_inference": 1}
CUSTOMER_SOURCES = {"message", "call", "lead_form", "appointment"}
# A person stood behind these. An appraisal record alone is a system entry (the rep confirming ownership on the vehicle page passes an actor and counts).
HUMAN_SOURCES = CUSTOMER_SOURCES | {"rep", "voice_memo", "sale"}
# One value at a time (a newer different value supersedes); everything else coexists as a list.
SCALAR_KEYS = {"family.spouse", "work.occupation", "work.employer", "contact.preferred_channel", "contact.phone", "contact.email", "contact.name", "identity.neighborhood",
               "buying.status", "family.pet", "preference.restaurant", "preference.purchase_context", "trade.vehicle", "vehicle.color"}
# Identity-like keys: an AI inference without the customer's or the rep's words waits for a human.
REQUIRE_CONFIRM = {"family.spouse", "work.occupation", "work.employer", "contact.phone", "contact.email", "contact.name", "vehicle.owned", "trade.vehicle", "vehicle.color"}
REFRESH_SIGNALS = {"inquiry", "customer_reply", "appointment", "inbound_call", "customer_statement"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def aware(v):
    """Motor hands back naive UTC datetimes; everything in here compares against aware ones."""
    return v.replace(tzinfo=timezone.utc) if isinstance(v, datetime) and v.tzinfo is None else v


DT_FIELDS = ("occurred_at", "recorded_at", "processed_at", "confirmed_at", "active_until", "last_signal_at", "created_at", "updated_at", "closed_at")


def hydrate(f: Optional[dict]) -> Optional[dict]:
    if not f:
        return f
    for k in DT_FIELDS:
        if f.get(k) is not None:
            f[k] = aware(f[k])
    for e in f.get("evidence") or []:
        if e.get("excerpt_at") is not None:
            e["excerpt_at"] = aware(e["excerpt_at"])
    if (f.get("source") or {}).get("excerpt_at") is not None:
        f["source"]["excerpt_at"] = aware(f["source"]["excerpt_at"])
    return f


async def load(db, query: dict, sort=None, limit: int = 2000) -> list:
    cur = db[FACTS].find(query)
    if sort:
        cur = cur.sort(sort)
    return [hydrate(f) for f in await cur.to_list(limit)]


def iso(v) -> Optional[str]:
    return aware(v).isoformat() if isinstance(v, datetime) else (str(v) if v else None)


def norm_value(v) -> str:
    if v is None:
        return ""
    if isinstance(v, dict):
        label = v.get("label")
        if label:
            return norm_value(label)
        return json.dumps({k: norm_value(x) for k, x in sorted(v.items()) if x not in (None, "", [], {})}, sort_keys=True)
    if isinstance(v, (list, tuple)):
        return json.dumps(sorted(norm_value(x) for x in v))
    return re.sub(r"\s+", " ", str(v)).strip().lower()


def fingerprint(contact_id: str, key: str, source: dict, value) -> str:
    raw = f"{contact_id}|{key}|{(source or {}).get('kind')}|{(source or {}).get('ref')}|{norm_value(value)}"
    return hashlib.sha1(raw.encode()).hexdigest()


def is_weak(f: dict) -> bool:
    src = f.get("source") or {}
    return f.get("confidence") == "low" or (src.get("kind") == "ai_inference" and not src.get("quote"))


def make(contact: dict, *, layer: str, domain: str, key: str, statement: str, value=None, occurred_at: Optional[datetime] = None, precision: str = "exact",
         source: Optional[dict] = None, confidence: str = "medium", actor: Optional[dict] = None, extractor: Optional[dict] = None, recorded_at: Optional[datetime] = None,
         active_until: Optional[datetime] = None, category: Optional[str] = None) -> dict:
    assert layer in LAYERS, layer
    assert confidence in CONFIDENCE, confidence
    recorded = aware(recorded_at) or now_utc()
    occurred = aware(occurred_at) or recorded
    active_until = aware(active_until)
    source = {"kind": "ai_inference", **(source or {})}
    cid = str(contact["_id"])
    human = source["kind"] in HUMAN_SOURCES or bool(actor)
    status = "proposed" if (key in REQUIRE_CONFIRM and source["kind"] == "ai_inference" and not actor) else "current"
    return {
        "contact_id": cid, "owner_user_id": str(contact.get("user_id") or ""), "store_id": str(contact.get("store_id") or ""),
        "layer": layer, "domain": domain, "key": key, "category": category, "statement": (statement or "").strip(), "value": value,
        "occurred_at": occurred, "occurred_precision": precision, "recorded_at": recorded, "processed_at": now_utc(),
        "confirmed_at": recorded if actor else None, "confirmed_by": {"user_id": str(actor["_id"]), "name": actor.get("name") or actor.get("email")} if actor else None,
        "confidence": confidence, "confidence_score": CONFIDENCE[confidence], "status": status, "active_until": active_until, "last_signal_at": occurred if layer == "intent" else None,
        "outcome": None, "source": source, "evidence": [source], "supersedes": None, "superseded_by": None, "disputes": None,
        "extractor": extractor, "fingerprint": fingerprint(cid, key, source, value), "evidence_fingerprints": [], "confirmations": 1 if human else 0,
        "created_at": recorded, "updated_at": recorded,
    }


def pub(f: dict) -> dict:
    out = {k: v for k, v in f.items() if k not in ("_id", "fingerprint")}
    out["id"] = str(f["_id"])
    for k in ("occurred_at", "recorded_at", "processed_at", "confirmed_at", "active_until", "last_signal_at", "created_at", "updated_at", "closed_at"):
        if k in out:
            out[k] = iso(out[k])
    for k in ("supersedes", "superseded_by", "disputes"):
        if out.get(k) is not None:
            out[k] = str(out[k])
    out["evidence"] = [{**e, "excerpt_at": iso(e.get("excerpt_at"))} for e in (out.get("evidence") or [])]
    out["source"] = {**(out.get("source") or {}), "excerpt_at": iso((out.get("source") or {}).get("excerpt_at"))}
    return out


async def _event(db, fact: dict, action: str, actor: Optional[dict] = None, before: Optional[dict] = None, after: Optional[dict] = None, note: str = ""):
    await db[EVENTS].insert_one({"fact_id": fact["_id"], "contact_id": fact["contact_id"], "key": fact["key"], "action": action,
                                 "actor": {"user_id": str(actor["_id"]), "name": actor.get("name") or actor.get("email")} if actor else {"user_id": None, "name": "system"},
                                 "before": before, "after": after, "note": note, "at": now_utc()})


async def currents_for(db, contact_id: str, key: str) -> list:
    return await load(db, {"contact_id": contact_id, "key": key, "status": "current"}, sort=[("occurred_at", -1)], limit=200)


async def record(db, fact: dict, actor: Optional[dict] = None) -> dict:
    """Store one fact through the status engine. Idempotent on fingerprint (same source, same value), including a source that already reaffirmed an existing fact. Returns {fact, action, affected}."""
    existing = hydrate(await db[FACTS].find_one({"$or": [{"fingerprint": fact["fingerprint"]}, {"evidence_fingerprints": fact["fingerprint"]}]}))
    if existing:
        return {"fact": existing, "action": "duplicate", "affected": []}
    currents = await currents_for(db, fact["contact_id"], fact["key"])
    kind, target = conflict.resolve(fact, currents, SCALAR_KEYS, RELIABILITY, is_weak)
    if kind == "reaffirm":
        src = fact["source"]
        human = src.get("kind") in HUMAN_SOURCES or bool(actor) or bool(fact.get("confirmed_by"))
        sets = {"updated_at": now_utc(), "last_signal_at": max(target.get("last_signal_at") or target["occurred_at"], fact["occurred_at"]) if target.get("layer") == "intent" else target.get("last_signal_at")}
        if human:
            sets["confirmed_at"] = fact["recorded_at"]
            sets["confirmed_by"] = fact["confirmed_by"] or {"user_id": None, "name": "customer" if src.get("kind") in CUSTOMER_SOURCES else src.get("kind")}
            if not target.get("confirmations"):
                sets["statement"] = fact["statement"]  # first person to stand behind it: the confirmed wording replaces the hedged one
        if CONFIDENCE[fact["confidence"]] > target.get("confidence_score", 0):
            sets.update({"confidence": fact["confidence"], "confidence_score": CONFIDENCE[fact["confidence"]]})
        if RELIABILITY.get(src.get("kind"), 0) > RELIABILITY.get((target.get("source") or {}).get("kind"), 0):
            sets["statement"] = fact["statement"]  # a better source now stands behind the same value; say it in its words
        # a person (customer, rep, sale) confirms; a repeated system record only corroborates
        inc = {"confirmations": 1} if human else {"corroborations": 1}
        await db[FACTS].update_one({"_id": target["_id"]}, {"$set": sets, "$inc": inc, "$push": {"evidence": src, "evidence_fingerprints": fact["fingerprint"]}})
        await _event(db, target, "reaffirmed", actor, after={"source": src.get("kind"), "ref": src.get("ref")})
        return {"fact": hydrate(await db[FACTS].find_one({"_id": target["_id"]})), "action": "reaffirmed", "affected": []}
    if kind == "older":
        fact = {**fact, "status": "historical", "outcome": "replaced", "superseded_by": target["_id"]}
    elif kind == "dispute":
        fact = {**fact, "status": "disputed", "disputes": target["_id"]}
    elif kind == "supersede":
        fact = {**fact, "supersedes": target["_id"]}
    res = await db[FACTS].insert_one(fact)
    fact["_id"] = res.inserted_id
    affected = []
    if kind == "supersede":
        for c in currents:
            await db[FACTS].update_one({"_id": c["_id"]}, {"$set": {"status": "superseded", "superseded_by": fact["_id"], "updated_at": now_utc()}})
            await _event(db, c, "superseded", actor, before={"status": "current"}, after={"status": "superseded", "by": str(fact["_id"])})
            affected.append(c["_id"])
    await _event(db, fact, {"create": "created", "coexist": "created", "older": "created_historical", "dispute": "created_disputed", "supersede": "created_superseding"}[kind], actor,
                 after={"status": fact["status"], "source": fact["source"].get("kind")})
    return {"fact": fact, "action": {"create": "created", "coexist": "created", "older": "historical", "dispute": "disputed", "supersede": "superseded"}[kind], "affected": affected}


async def set_status(db, fact_id, status: str, actor: Optional[dict], note: str = "", outcome: Optional[str] = None) -> dict:
    assert status in STATUSES
    f = await db[FACTS].find_one({"_id": ObjectId(str(fact_id))})
    if not f:
        raise LookupError("Fact not found")
    sets = {"status": status, "updated_at": now_utc()}
    if outcome:
        sets["outcome"] = outcome
    if status in ("historical", "retired"):
        sets["closed_at"] = now_utc()
    await db[FACTS].update_one({"_id": f["_id"]}, {"$set": sets})
    await _event(db, f, f"status_{status}", actor, before={"status": f["status"]}, after={"status": status, "outcome": outcome}, note=note)
    return hydrate(await db[FACTS].find_one({"_id": f["_id"]}))


async def confirm(db, fact_id, actor: dict, note: str = "", statement: Optional[str] = None) -> dict:
    """A human vouches for the fact: it becomes current (superseding a conflicting current value for scalar keys) and is marked confirmed."""
    f = await db[FACTS].find_one({"_id": ObjectId(str(fact_id))})
    if not f:
        raise LookupError("Fact not found")
    now = now_utc()
    worded = {"statement": statement.strip()} if statement else {}
    if f["key"] in SCALAR_KEYS:
        for c in await currents_for(db, f["contact_id"], f["key"]):
            if c["_id"] != f["_id"]:
                await db[FACTS].update_one({"_id": c["_id"]}, {"$set": {"status": "superseded", "superseded_by": f["_id"], "updated_at": now}})
                await _event(db, c, "superseded", actor, before={"status": c["status"]}, after={"status": "superseded", "by": str(f["_id"])}, note="confirmed by a person")
    await db[FACTS].update_one({"_id": f["_id"]}, {"$set": {"status": "current", "confirmed_at": now, "confirmed_by": {"user_id": str(actor["_id"]), "name": actor.get("name") or actor.get("email")},
                                                            "confidence": "high", "confidence_score": CONFIDENCE["high"], "updated_at": now, "disputes": None, **worded}, "$inc": {"confirmations": 1}})
    await _event(db, f, "confirmed", actor, before={"status": f["status"]}, after={"status": "current"}, note=note)
    return hydrate(await db[FACTS].find_one({"_id": f["_id"]}))


async def dispute(db, fact_id, actor: dict, note: str = "") -> dict:
    return await set_status(db, fact_id, "disputed", actor, note=note)


async def events_for(db, fact_id) -> list:
    rows = await db[EVENTS].find({"fact_id": ObjectId(str(fact_id))}).sort("at", 1).to_list(200)
    return [{**r, "id": str(r["_id"]), "fact_id": str(r["fact_id"]), "at": iso(r["at"]), "_id": None} for r in rows]


async def ensure_indexes(db):
    await db[FACTS].create_index("fingerprint", unique=True)
    await db[FACTS].create_index("evidence_fingerprints")
    await db[FACTS].create_index([("contact_id", 1), ("status", 1), ("layer", 1)])
    await db[FACTS].create_index([("contact_id", 1), ("key", 1), ("occurred_at", -1)])
    await db[FACTS].create_index([("owner_user_id", 1), ("layer", 1), ("status", 1), ("active_until", 1)])
    await db[EVENTS].create_index([("fact_id", 1), ("at", 1)])
    await db[EVENTS].create_index([("contact_id", 1), ("at", -1)])
