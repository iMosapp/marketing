"""Founder Command Center (Phase 1A-min): the owner's private strategic operating system.

Five collections, nothing else touched:
  cc_blueprint   one doc per key (statements, One Big Thing, pillars, products, next_action, and the `focus` singleton
                 that holds the three active priority ids); every edit keeps the previous data in versions[]
  cc_priorities  strategic priorities (proposed | active | paused | completed | replaced)
  cc_roadmap     90-day milestones (package | validate | replicate)
  cc_ideas       the Idea Vault (captured by default; ideas never become work on their own)
  cc_notes       Waiting On (kind waiting) and This Week's Wins (kind win)
The three-slot rule is one atomic update on the focus doc: a fourth active priority cannot exist, even under concurrent calls."""
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from bson import ObjectId

logger = logging.getLogger(__name__)

BLUEPRINT, PRIORITIES, ROADMAP, IDEAS, NOTES = "cc_blueprint", "cc_priorities", "cc_roadmap", "cc_ideas", "cc_notes"
MAX_ACTIVE = 3
PILLARS = ("capture", "understand", "engage", "improve")
PRODUCTS = ("relationship_os", "opportunity_intelligence", "performance_intelligence")
PRIORITY_STATUS = ("proposed", "active", "paused", "completed", "replaced")
ROADMAP_STATUS = ("not_started", "in_progress", "done", "blocked")
ROADMAP_PHASES = ("package", "validate", "replicate")
IDEA_STATUS = ("captured", "evaluating", "parked", "approved", "active", "rejected")
NOTE_KINDS = ("waiting", "win")
READINESS = ("unknown", "not_started", "in_progress", "ready")

STATEMENTS = {
    "company": "I'm On Social",
    "category": "Relationship Intelligence Platform",
    "vision": "The Relationship Operating System",
    "promise": "Turn every interaction into a stronger relationship and every relationship into more business.",
    "mission": "Help businesses capture opportunities, understand their customers, maintain meaningful engagement, and continuously improve performance through AI-powered relationship intelligence.",
    "philosophy": "Never forget a customer. Never miss an opportunity. Never lose the context of a relationship.",
    "positioning": "Relationship Intelligence Platform",
}
PILLAR_SEED = {
    "capture": {"name": "Capture", "promise": "Never miss an opportunity.", "capabilities": ["Lead capture", "Website forms", "Phone calls and SMS", "Lead source tracking", "Dynamic Number Insertion", "Marketing attribution", "CRM integrations", "Customer interaction history"], "outcome": "Identify and capture every meaningful customer opportunity."},
    "understand": {"name": "Understand", "promise": "Know the customer, not just the contact.", "capabilities": ["Relationship intelligence", "AI conversation summaries", "Customer preferences", "Historical interactions", "Voice notes", "Buying signals", "Relationship memory", "Customer lifecycle intelligence"], "outcome": "Build a complete and evolving understanding of every customer relationship."},
    "engage": {"name": "Engage", "promise": "Stay connected without relying on human memory.", "capabilities": ["AI voice assistants", "SMS and email campaigns", "Personalized follow-up", "Customer reactivation", "Automated relationship touchpoints", "Landing pages", "Review requests", "Appointment follow-up"], "outcome": "Create relevant, timely engagement that generates repeat business."},
    "improve": {"name": "Improve", "promise": "Measure what works. Fix what doesn't.", "capabilities": ["Mystery shopping", "AI call scoring", "Training and coaching", "Practice calls", "Certifications", "Performance dashboards", "Conversion measurement", "Opportunity analysis"], "outcome": "Continuously improve sales performance and customer experience."},
}
PRODUCT_SEED = {
    "relationship_os": {"name": "Relationship OS", "target": "Sales professionals, dealership teams, and businesses.", "promise": "Never forget a customer. Never miss a reason to reconnect.", "includes": ["Contact management", "Relationship intelligence", "AI follow-up", "SMS and email campaigns", "Digital business presence", "Personalized engagement", "Relationship timelines"]},
    "opportunity_intelligence": {"name": "Opportunity Intelligence", "target": "Dealerships, marketing agencies, dealer groups, and OEM partners.", "promise": "Know where your business comes from and where it's being lost.", "includes": ["Marketing attribution", "Lead source tracking", "Missed-opportunity identification", "Website conversion tracking", "Call intelligence", "DNI, when available", "Marketing ROI analysis"]},
    "performance_intelligence": {"name": "Performance Intelligence", "target": "Dealerships, OEMs, dealer groups, and training organizations.", "promise": "Stop guessing how your team performs. Measure it and improve it.", "includes": ["Mystery shopping", "AI coaching", "Call scoring", "Training", "Practice simulations", "Certifications", "Performance analytics"]},
}
PRODUCT_EMPTY = {"problem": "", "value_prop": "", "readiness": {"product": "unknown", "demo": "unknown", "collateral": "unknown", "pilot": "unknown"}, "pricing": {"status": "uncommitted", "notes": ""}, "revenue": None}
PILLAR_EMPTY = {"purpose": "", "problems": [], "features": [], "status": "unknown", "target_customer": "", "revenue_opportunity": "", "kpis": [], "enhancements": []}
OBJECTIVE_SEED = {"title": "Launch into equipment dealerships and validate a repeatable partner-led sales model.", "why": "", "target_date": None, "progress_pct": 0, "status": "proposed"}
PRIORITY_SEED = ["Finalize company positioning and commercial packages.", "Prepare the equipment dealership demonstration.", "Identify and recruit initial pilot partners."]
ROADMAP_SEED = {
    "package": ["Finalize company positioning", "Approve four pillars", "Define three commercial products", "Select initial ideal customer profile", "Create company overview", "Build one compelling equipment-dealer demo", "Identify target pilot partners"],
    "validate": ["Recruit 2-3 design partners", "Run structured pilots", "Establish baseline performance metrics", "Validate willingness to pay", "Identify onboarding challenges", "Refine product packaging"],
    "replicate": ["Convert pilots into paid customers", "Document measurable results", "Develop an approved case study", "Establish partner economics", "Document repeatable onboarding", "Prepare a scalable partner sales process"],
}
PHASE_LABEL = {"package": "Days 1-30 · Package", "validate": "Days 31-60 · Validate", "replicate": "Days 61-90 · Replicate"}


def _now():
    return datetime.now(timezone.utc)


def _oid(v) -> Optional[ObjectId]:
    return ObjectId(str(v)) if ObjectId.is_valid(str(v or "")) else None


def _iso(v):
    return v.isoformat() if isinstance(v, datetime) else v


def _who(me: dict) -> dict:
    return {"id": str(me["_id"]), "name": me.get("name") or me.get("email")}


def _pub(doc: dict) -> dict:
    out = {k: (_iso(v) if isinstance(v, datetime) else v) for k, v in doc.items() if k != "_id"}
    out["id"] = str(doc["_id"])
    for k in ("history", "versions"):
        if isinstance(out.get(k), list):
            out[k] = [{kk: _iso(vv) for kk, vv in h.items()} for h in out[k]]
    return out


# ───────────────────────── seed (idempotent: inserts missing keys only, never overwrites founder edits) ─────────────────────────
async def seed(db, me: dict) -> dict:
    now, added = _now(), []

    async def put(key: str, kind: str, data: dict):
        r = await db[BLUEPRINT].update_one({"key": key}, {"$setOnInsert": {"key": key, "kind": kind, "data": data, "status": "draft", "versions": [], "created_at": now, "updated_at": now}}, upsert=True)
        if r.upserted_id:
            added.append(key)

    for k, text in STATEMENTS.items():
        await put(k, "statement", {"text": text})
    await put("objective", "objective", OBJECTIVE_SEED)
    for k, p in PILLAR_SEED.items():
        await put(f"pillar.{k}", "pillar", {**PILLAR_EMPTY, **p, "key": k})
    for k, p in PRODUCT_SEED.items():
        await put(f"product.{k}", "product", {**PRODUCT_EMPTY, **p, "key": k})
    await put("next_action", "action", {"text": "", "why": "", "state": "none", "updated_by": None})
    await put("focus", "focus", {"active_priority_ids": []})
    if await db[PRIORITIES].count_documents({}) == 0:
        await db[PRIORITIES].insert_many([{"title": t, "status": "proposed", "pillar": "", "product": "", "purpose": "", "next_action": "", "due": None, "owner": _who(me), "progress_pct": 0,
                                           "definition_of_done": "", "seeded": True, "history": [{"at": now, "by": _who(me), "action": "seeded"}], "created_at": now, "updated_at": now} for t in PRIORITY_SEED])
        added.append("priorities")
    if await db[ROADMAP].count_documents({}) == 0:
        docs = [{"phase": ph, "order": i, "title": t, "status": "not_started", "owner": _who(me), "due": None, "pillar": "", "product": "", "note": "", "seeded": True, "created_at": now, "updated_at": now}
                for ph in ROADMAP_PHASES for i, t in enumerate(ROADMAP_SEED[ph])]
        await db[ROADMAP].insert_many(docs)
        added.append("roadmap")
    return {"added": added}


# ───────────────────────── blueprint (statements, objective, pillars, products, next action) ─────────────────────────
async def blueprint(db) -> dict:
    rows = {r["key"]: r async for r in db[BLUEPRINT].find({})}
    def one(k):
        r = rows.get(k)
        return {"key": k, "kind": r.get("kind"), "data": r.get("data"), "status": r.get("status"), "versions": len(r.get("versions") or []), "updated_at": _iso(r.get("updated_at")), "approved_at": _iso(r.get("approved_at"))} if r else None
    return {"statements": {k: one(k) for k in STATEMENTS}, "objective": one("objective"), "pillars": [one(f"pillar.{k}") for k in PILLARS], "products": [one(f"product.{k}") for k in PRODUCTS], "next_action": one("next_action")}


def _clean_data(key: str, data: dict, current: dict) -> dict:
    """Keep the stored shape; only known fields change, so a later phase can add editing without a migration."""
    data = data or {}
    out = dict(current or {})
    if key in STATEMENTS:
        out["text"] = str(data.get("text") or "").strip()[:600]
    elif key == "objective":
        for f in ("title", "why"):
            if f in data:
                out[f] = str(data.get(f) or "").strip()[:400]
        if "target_date" in data:
            out["target_date"] = str(data["target_date"])[:10] if data.get("target_date") else None
        if "progress_pct" in data:
            out["progress_pct"] = max(0, min(100, int(data.get("progress_pct") or 0)))
        if data.get("status") in ("proposed", "on_track", "at_risk", "behind", "done"):
            out["status"] = data["status"]
    elif key == "next_action":
        if "text" in data:
            out["text"] = str(data.get("text") or "").strip()[:300]
        if "why" in data:
            out["why"] = str(data.get("why") or "").strip()[:300]
        out["state"] = "set" if out.get("text") else "none"
    elif key.startswith("pillar."):
        for f in ("name", "promise", "outcome", "purpose", "target_customer", "revenue_opportunity", "status"):
            if f in data:
                out[f] = str(data.get(f) or "").strip()[:400]
        for f in ("capabilities", "problems", "features", "kpis", "enhancements"):
            if isinstance(data.get(f), list):
                out[f] = [str(x).strip()[:160] for x in data[f] if str(x).strip()][:20]
    elif key.startswith("product."):
        for f in ("name", "target", "promise", "problem", "value_prop"):
            if f in data:
                out[f] = str(data.get(f) or "").strip()[:400]
        if isinstance(data.get("includes"), list):
            out["includes"] = [str(x).strip()[:160] for x in data["includes"] if str(x).strip()][:20]
        if isinstance(data.get("readiness"), dict):
            out["readiness"] = {k: (data["readiness"].get(k) if data["readiness"].get(k) in READINESS else (current.get("readiness") or {}).get(k, "unknown")) for k in ("product", "demo", "collateral", "pilot")}
        if isinstance(data.get("pricing"), dict):
            out["pricing"] = {"status": data["pricing"].get("status") if data["pricing"].get("status") in ("uncommitted", "draft", "committed") else "uncommitted", "notes": str(data["pricing"].get("notes") or "")[:400]}
    return out


async def update_blueprint(db, key: str, data: dict, me: dict) -> dict:
    """Save a new draft version: the previous data goes to versions[], the doc returns to draft until approved again."""
    cur = await db[BLUEPRINT].find_one({"key": key})
    if not cur:
        raise ValueError("Unknown key")
    if key == "focus":
        raise ValueError("The focus doc is managed by the priority endpoints")
    new = _clean_data(key, data, cur.get("data") or {})
    if new == (cur.get("data") or {}):
        return cur
    now = _now()
    version = {"data": cur.get("data"), "status": cur.get("status"), "by": _who(me), "at": now, "reason": str((data or {}).get("reason") or "")[:300]}
    await db[BLUEPRINT].update_one({"_id": cur["_id"]}, {"$set": {"data": new, "status": "draft", "updated_at": now}, "$push": {"versions": {"$each": [version], "$slice": -50}}})
    return await db[BLUEPRINT].find_one({"_id": cur["_id"]})


async def approve_blueprint(db, key: str, reason: str, me: dict) -> dict:
    cur = await db[BLUEPRINT].find_one({"key": key})
    if not cur or cur.get("kind") == "focus":
        raise ValueError("Unknown key")
    if not (reason or "").strip():
        raise ValueError("A reason is required to approve a statement")
    now = _now()
    await db[BLUEPRINT].update_one({"_id": cur["_id"]}, {"$set": {"status": "approved", "approved_at": now, "approved_by": _who(me), "approval_reason": reason.strip()[:300], "updated_at": now}})
    return await db[BLUEPRINT].find_one({"_id": cur["_id"]})


async def versions(db, key: str) -> list:
    cur = await db[BLUEPRINT].find_one({"key": key}, {"versions": 1})
    return [{**v, "at": _iso(v.get("at"))} for v in (cur or {}).get("versions") or []][::-1]


# ───────────────────────── priorities and the three-slot rule ─────────────────────────
def _clean_priority(body: dict, cur: Optional[dict] = None) -> dict:
    out = {}
    for f, w in (("title", 160), ("pillar", 40), ("product", 60), ("purpose", 300), ("next_action", 300), ("definition_of_done", 400)):
        if f in body:
            out[f] = str(body.get(f) or "").strip()[:w]
    if "pillar" in out and out["pillar"] and out["pillar"] not in PILLARS:
        raise ValueError("Unknown pillar")
    if "product" in out and out["product"] and out["product"] not in PRODUCTS:
        raise ValueError("Unknown product")
    if "due" in body:
        out["due"] = str(body["due"])[:10] if body.get("due") else None
    if "progress_pct" in body:
        out["progress_pct"] = max(0, min(100, int(body.get("progress_pct") or 0)))
    if isinstance(body.get("owner"), dict) and body["owner"].get("name"):
        out["owner"] = {"id": str(body["owner"].get("id") or ""), "name": str(body["owner"]["name"])[:80]}
    if cur is None and not out.get("title"):
        raise ValueError("A title is required")
    return out


async def create_priority(db, body: dict, me: dict) -> dict:
    now = _now()
    doc = {"title": "", "status": "proposed", "pillar": "", "product": "", "purpose": "", "next_action": "", "due": None, "owner": _who(me), "progress_pct": 0, "definition_of_done": "", "seeded": False,
           **_clean_priority(body), "history": [{"at": now, "by": _who(me), "action": "created"}], "created_at": now, "updated_at": now}
    res = await db[PRIORITIES].insert_one(doc)
    return await db[PRIORITIES].find_one({"_id": res.inserted_id})


async def update_priority(db, p: dict, body: dict, me: dict) -> dict:
    upd = _clean_priority(body, p)
    if not upd:
        return p
    await db[PRIORITIES].update_one({"_id": p["_id"]}, {"$set": {**upd, "updated_at": _now()}, "$push": {"history": {"at": _now(), "by": _who(me), "action": "edited", "fields": sorted(upd)}}})
    return await db[PRIORITIES].find_one({"_id": p["_id"]})


async def active_ids(db) -> list:
    f = await db[BLUEPRINT].find_one({"key": "focus"}, {"data": 1})
    return list(((f or {}).get("data") or {}).get("active_priority_ids") or [])


async def activate_priority(db, p: dict, me: dict) -> dict:
    """Atomic: the push only matches while the focus doc holds fewer than three ids, so two concurrent activations can never both win a last slot."""
    if p.get("status") == "active":
        return p
    if p.get("status") in ("completed", "replaced"):
        raise ValueError("A finished priority cannot be reactivated; propose it again")
    if not p.get("pillar") or not p.get("purpose"):
        raise ValueError("Give this priority a pillar and a commercial purpose before activating it")
    pid = str(p["_id"])
    r = await db[BLUEPRINT].update_one({"key": "focus", f"data.active_priority_ids.{MAX_ACTIVE - 1}": {"$exists": False}, "data.active_priority_ids": {"$ne": pid}},
                                       {"$push": {"data.active_priority_ids": pid}, "$set": {"updated_at": _now()}})
    if r.modified_count == 0:
        if pid in await active_ids(db):
            return p
        raise SlotsFull(await _active_docs(db))
    await db[PRIORITIES].update_one({"_id": p["_id"]}, {"$set": {"status": "active", "activated_at": _now(), "updated_at": _now()}, "$push": {"history": {"at": _now(), "by": _who(me), "action": "activated"}}})
    return await db[PRIORITIES].find_one({"_id": p["_id"]})


class SlotsFull(Exception):
    def __init__(self, active: list):
        super().__init__("Three priorities are already active")
        self.active = active


async def _active_docs(db) -> list:
    ids = [ObjectId(i) for i in await active_ids(db) if ObjectId.is_valid(i)]
    rows = await db[PRIORITIES].find({"_id": {"$in": ids}}).to_list(MAX_ACTIVE)
    return [_pub(r) for r in rows]


async def _release(db, p: dict, new_status: str, me: dict, action: str, extra: Optional[dict] = None):
    now = _now()
    await db[BLUEPRINT].update_one({"key": "focus"}, {"$pull": {"data.active_priority_ids": str(p["_id"])}, "$set": {"updated_at": now}})
    await db[PRIORITIES].update_one({"_id": p["_id"]}, {"$set": {"status": new_status, f"{new_status}_at": now, "updated_at": now, **(extra or {})}, "$push": {"history": {"at": now, "by": _who(me), "action": action}}})
    return await db[PRIORITIES].find_one({"_id": p["_id"]})


async def pause_priority(db, p: dict, me: dict) -> dict:
    if p.get("status") != "active":
        raise ValueError("Only an active priority can be paused")
    return await _release(db, p, "paused", me, "paused")


async def complete_priority(db, p: dict, me: dict) -> dict:
    if p.get("status") not in ("active", "paused"):
        raise ValueError("Only an active or paused priority can be completed")
    doc = await _release(db, p, "completed", me, "completed", {"progress_pct": 100})
    await db[NOTES].insert_one({"kind": "win", "title": f"Completed: {p.get('title')}", "party": "", "since": _now(), "due": None, "priority_id": str(p["_id"]), "status": "done", "source": "priority", "created_at": _now(), "updated_at": _now()})
    return doc


async def replace_priority(db, p: dict, replace_id: str, reason: str, me: dict) -> dict:
    """Deliberate swap: the active one steps aside (status replaced) and the new one takes its slot, with the founder's reason recorded on both."""
    if not (reason or "").strip():
        raise ValueError("Say why this replaces the current priority")
    old = await db[PRIORITIES].find_one({"_id": _oid(replace_id)}) if _oid(replace_id) else None
    if not old or old.get("status") != "active":
        raise ValueError("Pick one of the three active priorities to replace")
    if not p.get("pillar") or not p.get("purpose"):
        raise ValueError("Give this priority a pillar and a commercial purpose before activating it")
    await _release(db, old, "replaced", me, "replaced", {"replaced_by": str(p["_id"]), "replace_reason": reason.strip()[:300]})
    try:
        doc = await activate_priority(db, p, me)
    except SlotsFull:
        # someone filled the slot in between: put the old one back and report
        await db[BLUEPRINT].update_one({"key": "focus", f"data.active_priority_ids.{MAX_ACTIVE - 1}": {"$exists": False}}, {"$push": {"data.active_priority_ids": str(old["_id"])}})
        await db[PRIORITIES].update_one({"_id": old["_id"]}, {"$set": {"status": "active"}})
        raise
    await db[PRIORITIES].update_one({"_id": p["_id"]}, {"$push": {"history": {"at": _now(), "by": _who(me), "action": "replaced_other", "replaced": str(old["_id"]), "reason": reason.strip()[:300]}}})
    return doc


async def priorities(db) -> list:
    ids = await active_ids(db)
    rows = await db[PRIORITIES].find({}).sort("created_at", 1).to_list(200)
    out = [_pub(r) for r in rows]
    for o in out:
        o["slot"] = (ids.index(o["id"]) + 1) if o["id"] in ids else None
    return sorted(out, key=lambda o: (o["slot"] or 99, o["created_at"]))


# ───────────────────────── notes (waiting on / wins), roadmap, ideas ─────────────────────────
def _clean_note(body: dict, create: bool) -> dict:
    out = {}
    if "title" in body or create:
        out["title"] = str(body.get("title") or "").strip()[:200]
        if create and not out["title"]:
            raise ValueError("A title is required")
    if "kind" in body or create:
        k = body.get("kind") or "waiting"
        if k not in NOTE_KINDS:
            raise ValueError("Unknown kind")
        out["kind"] = k
    if "party" in body:
        out["party"] = str(body.get("party") or "").strip()[:80]
    if "due" in body:
        out["due"] = str(body["due"])[:10] if body.get("due") else None
    if body.get("status") in ("open", "done"):
        out["status"] = body["status"]
    if "priority_id" in body:
        out["priority_id"] = str(body.get("priority_id") or "") or None
    return out


async def create_note(db, body: dict) -> dict:
    now = _now()
    doc = {"party": "", "due": None, "status": "open", "priority_id": None, "source": "manual", **_clean_note(body, True), "since": now, "created_at": now, "updated_at": now}
    res = await db[NOTES].insert_one(doc)
    return await db[NOTES].find_one({"_id": res.inserted_id})


def _clean_roadmap(body: dict, create: bool) -> dict:
    out = {}
    if "title" in body or create:
        out["title"] = str(body.get("title") or "").strip()[:200]
        if create and not out["title"]:
            raise ValueError("A title is required")
    if "phase" in body or create:
        ph = body.get("phase") or "package"
        if ph not in ROADMAP_PHASES:
            raise ValueError("Unknown phase")
        out["phase"] = ph
    if "status" in body:
        if body.get("status") not in ROADMAP_STATUS:
            raise ValueError("Unknown status")
        out["status"] = body["status"]
    for f, w in (("note", 400), ("pillar", 40), ("product", 60)):
        if f in body:
            out[f] = str(body.get(f) or "").strip()[:w]
    if "due" in body:
        out["due"] = str(body["due"])[:10] if body.get("due") else None
    if isinstance(body.get("owner"), dict) and body["owner"].get("name"):
        out["owner"] = {"id": str(body["owner"].get("id") or ""), "name": str(body["owner"]["name"])[:80]}
    return out


async def create_roadmap(db, body: dict, me: dict) -> dict:
    now = _now()
    ph = body.get("phase") or "package"
    n = await db[ROADMAP].count_documents({"phase": ph})
    doc = {"status": "not_started", "owner": _who(me), "due": None, "pillar": "", "product": "", "note": "", "seeded": False, **_clean_roadmap(body, True), "order": n, "created_at": now, "updated_at": now}
    res = await db[ROADMAP].insert_one(doc)
    return await db[ROADMAP].find_one({"_id": res.inserted_id})


async def roadmap(db) -> dict:
    rows = [_pub(r) for r in await db[ROADMAP].find({}).sort([("phase", 1), ("order", 1), ("created_at", 1)]).to_list(500)]
    phases = []
    for ph in ROADMAP_PHASES:
        items = [r for r in rows if r.get("phase") == ph]
        done = sum(1 for r in items if r.get("status") == "done")
        phases.append({"phase": ph, "label": PHASE_LABEL[ph], "items": items, "done": done, "total": len(items), "pct": int(round(100 * done / len(items))) if items else 0})
    return {"phases": phases}


def _clean_idea(body: dict, create: bool) -> dict:
    out = {}
    if "title" in body or create:
        out["title"] = str(body.get("title") or body.get("description") or "").strip()[:200]
        if create and not out["title"]:
            raise ValueError("Say what the idea is")
    for f, w in (("description", 2000), ("transcript", 4000), ("customer", 120), ("value", 400), ("complexity", 40), ("urgency", 40)):
        if f in body:
            out[f] = str(body.get(f) or "").strip()[:w]
    if "pillar" in body:
        v = str(body.get("pillar") or "")
        if v and v not in PILLARS:
            raise ValueError("Unknown pillar")
        out["pillar"] = v
    if "product" in body:
        v = str(body.get("product") or "")
        if v and v not in PRODUCTS:
            raise ValueError("Unknown product")
        out["product"] = v
    if "status" in body:
        if body.get("status") not in IDEA_STATUS:
            raise ValueError("Unknown status")
        out["status"] = body["status"]
    return out


async def create_idea(db, body: dict, me: dict) -> dict:
    now = _now()
    doc = {"description": "", "transcript": "", "pillar": "", "product": "", "customer": "", "value": "", "complexity": "", "urgency": "", "status": "captured", "source": body.get("source") if body.get("source") in ("text", "voice") else "text",
           **{k: v for k, v in _clean_idea(body, True).items() if k != "status"}, "captured_by": _who(me), "history": [{"at": now, "by": _who(me), "action": "captured"}], "reviewed_at": None, "created_at": now, "updated_at": now}
    res = await db[IDEAS].insert_one(doc)
    return await db[IDEAS].find_one({"_id": res.inserted_id})


async def update_idea(db, idea: dict, body: dict, me: dict) -> dict:
    upd = _clean_idea(body, False)
    if not upd:
        return idea
    now = _now()
    push = {"at": now, "by": _who(me), "action": "edited", "fields": sorted(upd)}
    if "status" in upd and upd["status"] != idea.get("status"):
        push = {"at": now, "by": _who(me), "action": "status", "from": idea.get("status"), "to": upd["status"]}
        upd["reviewed_at"] = now
    await db[IDEAS].update_one({"_id": idea["_id"]}, {"$set": {**upd, "updated_at": now}, "$push": {"history": push}})
    return await db[IDEAS].find_one({"_id": idea["_id"]})


async def ideas(db, status: Optional[str] = None, view: Optional[str] = None) -> dict:
    q = {}
    if status in IDEA_STATUS:
        q["status"] = status
    if view == "new_week":
        q["created_at"] = {"$gte": _now() - timedelta(days=7)}
    elif view == "parked":
        q["status"] = "parked"
    rows = await db[IDEAS].find(q).sort("created_at", -1).to_list(500)
    counts = {s: await db[IDEAS].count_documents({"status": s}) for s in IDEA_STATUS}
    counts["new_week"] = await db[IDEAS].count_documents({"created_at": {"$gte": _now() - timedelta(days=7)}})
    return {"ideas": [_pub(r) for r in rows], "counts": counts}


# ───────────────────────── focus payload and export ─────────────────────────
async def focus(db) -> dict:
    bp = await blueprint(db)
    pri = await priorities(db)
    active = [p for p in pri if p["slot"]]
    week_ago = _now() - timedelta(days=7)
    waiting = [_pub(r) for r in await db[NOTES].find({"kind": "waiting", "status": "open"}).sort("created_at", -1).to_list(50)]
    wins = [_pub(r) for r in await db[NOTES].find({"kind": "win", "created_at": {"$gte": week_ago}}).sort("created_at", -1).to_list(50)]
    return {"objective": bp["objective"], "next_action": bp["next_action"], "active": active, "proposed": [p for p in pri if p["status"] == "proposed"], "paused": [p for p in pri if p["status"] == "paused"],
            "slots": MAX_ACTIVE, "waiting": waiting, "wins": wins, "ideas_new_week": await db[IDEAS].count_documents({"created_at": {"$gte": week_ago}}), "pillars": [{"key": k, "name": PILLAR_SEED[k]["name"]} for k in PILLARS],
            "products": [{"key": k, "name": PRODUCT_SEED[k]["name"]} for k in PRODUCTS]}


async def export_json(db) -> dict:
    out = {"exported_at": _iso(_now()), "blueprint": [_pub(r) for r in await db[BLUEPRINT].find({}).sort("key", 1).to_list(200)], "priorities": await priorities(db), "roadmap": (await roadmap(db))["phases"],
           "ideas": [_pub(r) for r in await db[IDEAS].find({}).sort("created_at", -1).to_list(2000)], "notes": [_pub(r) for r in await db[NOTES].find({}).sort("created_at", -1).to_list(2000)]}
    return out


async def export_markdown(db) -> str:
    bp = await blueprint(db)
    pri = await priorities(db)
    rm = await roadmap(db)
    idea_rows = await db[IDEAS].find({}).sort("created_at", -1).to_list(2000)
    notes = await db[NOTES].find({}).sort("created_at", -1).to_list(2000)
    s = lambda k: ((bp["statements"].get(k) or {}).get("data") or {}).get("text", "")
    st = lambda k: (bp["statements"].get(k) or {}).get("status", "draft")
    L = [f"# {s('company') or 'Company Blueprint'}", f"_Exported {_iso(_now())[:16].replace('T', ' ')} UTC. Statements marked (draft) are not yet approved._", "", "## North Star"]
    for k, label in (("category", "Category"), ("vision", "Long-term vision"), ("promise", "Company promise"), ("mission", "Mission"), ("philosophy", "Core philosophy"), ("positioning", "Positioning")):
        L.append(f"- **{label}** ({st(k)}): {s(k)}")
    ob = (bp["objective"] or {}).get("data") or {}
    L += ["", "## The One Big Thing", f"**{ob.get('title', '')}**", (f"Why: {ob.get('why')}" if ob.get("why") else ""), f"Target: {ob.get('target_date') or 'not set'} · Progress: {ob.get('progress_pct', 0)}% · Status: {ob.get('status', 'proposed')}"]
    na = (bp["next_action"] or {}).get("data") or {}
    L += ["", "## Next Best Action", na.get("text") or "_none set_", (f"Why: {na.get('why')}" if na.get("why") else "")]
    L += ["", "## Strategic Priorities (max three active)"]
    for p in pri:
        L.append(f"- [{'ACTIVE ' + str(p['slot']) if p['slot'] else p['status']}] **{p['title']}**" + (f" · pillar {p['pillar']}" if p.get("pillar") else "") + (f" · due {p['due']}" if p.get("due") else "") + f" · {p.get('progress_pct', 0)}%"
                 + (f"\n  - Next: {p['next_action']}" if p.get("next_action") else "") + (f"\n  - Done when: {p['definition_of_done']}" if p.get("definition_of_done") else "") + (f"\n  - Purpose: {p['purpose']}" if p.get("purpose") else ""))
    L += ["", "## Four Pillars"]
    for pl in bp["pillars"]:
        d = (pl or {}).get("data") or {}
        L += [f"### {d.get('name')} — {d.get('promise')}", f"Outcome: {d.get('outcome')}", "Capabilities: " + ", ".join(d.get("capabilities") or []), ""]
    L += ["## Commercial Products (one platform, three packages)"]
    for pr in bp["products"]:
        d = (pr or {}).get("data") or {}
        rd = d.get("readiness") or {}
        L += [f"### {d.get('name')}", f"Target: {d.get('target')}", f"Promise: {d.get('promise')}", "Includes: " + ", ".join(d.get("includes") or []),
              f"Readiness: product {rd.get('product', 'unknown')} · demo {rd.get('demo', 'unknown')} · collateral {rd.get('collateral', 'unknown')} · pilot {rd.get('pilot', 'unknown')}", f"Pricing: {(d.get('pricing') or {}).get('status', 'uncommitted')}", ""]
    L += ["## 90-Day Roadmap"]
    for ph in rm["phases"]:
        L.append(f"### {ph['label']} ({ph['done']}/{ph['total']} done)")
        for it in ph["items"]:
            L.append(f"- [{'x' if it['status'] == 'done' else ' '}] {it['title']} ({it['status'].replace('_', ' ')}{', due ' + it['due'] if it.get('due') else ''})")
        L.append("")
    L += ["## Idea Vault"]
    for st_ in IDEA_STATUS:
        rows = [i for i in idea_rows if i.get("status") == st_]
        if rows:
            L.append(f"### {st_.title()} ({len(rows)})")
            L += [f"- {i.get('title')}" + (f": {i.get('description')}" if i.get("description") else "") for i in rows]
            L.append("")
    waiting = [n for n in notes if n.get("kind") == "waiting" and n.get("status") == "open"]
    wins = [n for n in notes if n.get("kind") == "win"]
    L += ["## Waiting On"] + ([f"- {n.get('title')}" + (f" ({n.get('party')})" if n.get("party") else "") for n in waiting] or ["_nothing_"]) + ["", "## Wins"] + ([f"- {_iso(n.get('created_at'))[:10]} {n.get('title')}" for n in wins] or ["_none yet_"])
    return "\n".join(x for x in L if x is not None)
