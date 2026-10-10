"""Intelligent Nudges (Phase 2C): fewer, truer follow-up tasks computed from facts. Every nudge says whether it rests on a verified fact or a guess,
carries its evidence, and is written through the existing tasks collection with an idempotency key. Flag INTEL_NUDGES; nothing here sends anything."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId

from services.intelligence import brief, config
from services.intelligence import facts as F
from services.intelligence import intent as I
from services.intelligence.reply_context import about, from_comment, subject_interest
from services.intelligence.timeline import SOURCE_LABEL, _ago, _dt, _when

logger = logging.getLogger(__name__)
RUNS = "intel_nudge_runs"
SOURCE = "intelligence"
OPEN = {"$in": ["pending", "snoozed", None]}
MILESTONE_LOOKAHEAD_DAYS = 14
DISPOSED_LOOKBACK_DAYS = 180
PRIORITY = {"possible_trade": ("high", 1), "interest_aging": ("high", 1), "ownership_unclear": ("medium", 2), "verify_ownership": ("medium", 2), "milestone": ("medium", 2)}


def enabled() -> bool:
    return config._flag("INTEL_NUDGES")


def _label(f: dict) -> str:
    return (f.get("label") or f.get("statement") or "").strip()


def _ev(f: dict, text: str) -> dict:
    kind = (f.get("source") or {}).get("kind")
    return {"fact_id": f["id"], "label": text, "source": SOURCE_LABEL.get(kind, kind), "at": f.get("occurred_at")}


def _first(contact: dict) -> str:
    return (contact.get("first_name") or "them").strip().split(" ")[0]


def _cand(kind: str, fact_id: str, title: str, why: str, basis: str, evidence: list, message: str, due: datetime, key_suffix: str = "") -> dict:
    pr, order = PRIORITY[kind]
    return {"kind": kind, "fact_id": fact_id, "title": title, "why": why, "basis": basis, "evidence": evidence, "suggested_message": message, "due": due, "priority": pr, "priority_order": order, "key_suffix": key_suffix}


def _anniversaries(contact: dict, facts: list, now: datetime) -> list:
    out, first = [], _first(contact)
    for f in facts:
        if f["key"] == "vehicle.purchase":
            d = _dt(f.get("occurred_at"))
            if not d:
                continue
            try:
                anniv = d.replace(year=now.year)
            except ValueError:
                anniv = d.replace(year=now.year, day=28)
            if anniv.date() < now.date():
                anniv = anniv.replace(year=now.year + 1)
            years = anniv.year - d.year
            days = (anniv.date() - now.date()).days
            if years >= 1 and 0 <= days <= MILESTONE_LOOKAHEAD_DAYS:
                when = anniv.strftime("%b %-d")
                out.append(_cand("milestone", f["id"], f"{first}'s {years}-year anniversary with the {_label(f)} ({when})",
                                 f"Bought {_label(f)} on {d.strftime('%b %-d, %Y')} (sale record).", "verified", [_ev(f, f"bought {_label(f)} in {_when(f.get('occurred_at'))}")],
                                 f"Hi {first}, {years} year{'s' if years != 1 else ''} with the {_label(f)} this week. How is it treating you?", max(now, anniv - timedelta(days=3)), str(anniv.year)))
        elif f["key"] == "milestone.date":
            v = f.get("value") if isinstance(f.get("value"), dict) else {}
            d = _dt(str(v.get("date") or ""))
            if not d:
                continue
            try:
                nxt = d.replace(year=now.year)
            except ValueError:
                nxt = d.replace(year=now.year, day=28)
            if nxt.date() < now.date():
                nxt = nxt.replace(year=now.year + 1)
            days = (nxt.date() - now.date()).days
            if 0 <= days <= MILESTONE_LOOKAHEAD_DAYS:
                what = v.get("description") or _label(f)
                human = (f.get("source") or {}).get("kind") in F.HUMAN_SOURCES
                out.append(_cand("milestone", f["id"], f"{first}: {what} ({nxt.strftime('%b %-d')})", f"{what}: {f.get('statement')}.", "verified" if human else "uncertain",
                                 [_ev(f, f"{what} on {nxt.strftime('%b %-d')}")], f"Hi {first}, thinking of you with {what} coming up. Hope it is a good one.", max(now, nxt - timedelta(days=3)), str(nxt.year)))
    return out


async def candidates(db, contact: dict, now: Optional[datetime] = None) -> list:
    """What the facts say should be nudged for this contact right now; one nudge per anchoring fact, in priority order. Pure read."""
    now = now or datetime.now(timezone.utc)
    b = await brief.build(db, contact, now)
    first = _first(contact)
    drv, mode = b["now"]["driving"], b["next"]["mode"]
    owned = b["who"]["owns"]
    out: list = []
    subject = subject_interest(b) if drv else None
    if subject and owned:
        other = [o for o in owned if not I.matches(o.get("value"), subject.get("value"))]
        if other:
            o, drv = other[0], subject
            ok = (o.get("confirmations") or 0) >= 1
            ago = _ago(drv.get("last_signal_at") or drv.get("occurred_at"), now)
            asked = f"asked about {about(drv)}" if not from_comment(drv) else f"sent {about(drv)}"
            out.append(_cand("possible_trade", drv["id"],
                             f"Ask {first} if the {_label(o)} is a trade" if ok else f"Ask {first} what they are driving now, and whether it is a trade",
                             f"{first} {asked} {ago}; the {_label(o)} is on record" + ("." if ok else " but nobody has confirmed they still own it."),
                             "verified" if ok else "uncertain", [_ev(drv, f"{_label(drv)[:60]} inquiry {ago}"), _ev(o, f"owns {_label(o)} since {_when(o.get('occurred_at'))}" + ("" if ok else " (unconfirmed)"))],
                             f"Hi {first}, saw your note on {about(drv) if not from_comment(drv) else 'the site'}. Is this to replace your {_label(o)}, or an additional vehicle?" if ok
                             else f"Hi {first}, saw your note on {about(drv) if not from_comment(drv) else 'the site'}. Quick one: what are you driving today, and would it be a trade?", now))
    for f in b["now"]["active_intent"]:
        if f.get("phase") == "aging" and f["key"] in ("vehicle.interest", "buying.signal") and not any(c["fact_id"] == f["id"] for c in out):
            days = f.get("days_since_signal")
            topic = about(f) if f["key"] == "vehicle.interest" else f"their {_label(f)[:60]}"
            out.append(_cand("interest_aging", f["id"], f"Follow up with {first} on {topic} before it goes cold",
                             f"Their own inquiry, {days} days ago via {SOURCE_LABEL.get((f.get('source') or {}).get('kind'), 'unknown').lower()}; nothing since, window closes in {max(0, (f.get('window_days') or 0) - (days or 0))} days.",
                             "verified", [_ev(f, f"{_label(f)[:60]} inquiry {_ago(f.get('last_signal_at') or f.get('occurred_at'), now)}")],
                             f"Hi {first}, a few weeks back you asked about {about(f) if not from_comment(f) else 'something on our site'}. Still on your radar, or has that changed?", now))
    if not owned:
        disposed = [f for f in b["history"] if f["key"] == "vehicle.disposed" and _dt(f.get("occurred_at")) and (now - _dt(f.get("occurred_at"))).days <= DISPOSED_LOOKBACK_DAYS]
        disputed = [v for v in b["verify"] if v.get("status") == "disputed" and "Owns" in (v.get("statement") or "")]
        if disposed:
            d = disposed[0]
            out.append(_cand("ownership_unclear", d["id"], f"Confirm what {first} is driving now", f"The {_label(d)} left their garage {_ago(d.get('occurred_at'), now)} and no replacement is on record.",
                             "uncertain", [_ev(d, f"{_label(d)} gone {_ago(d.get('occurred_at'), now)}")], f"Hi {first}, what are you driving these days? Want to make sure I have your garage right.", now))
        elif disputed:
            v = disputed[0]
            out.append(_cand("ownership_unclear", v["fact_id"], f"Confirm what {first} is driving now", f"The ownership record was disputed: {v['statement']}.", "uncertain",
                             [{"fact_id": v["fact_id"], "label": "disputed ownership", "source": None, "at": None}], f"Hi {first}, what are you driving these days? Want to make sure I have your garage right.", now))
    if mode == "verify_ownership" and owned:
        o = owned[0]
        out.append(_cand("verify_ownership", o["id"], f"Confirm {first} still owns the {_label(o)}", "The only ownership record comes from an appraisal; nobody has confirmed it.", "uncertain",
                         [_ev(o, f"{_label(o)} on an appraisal record")], f"Hi {first}, quick one: is the {_label(o)} still yours? Want to make sure I have your garage right.", now))
    out += _anniversaries(contact, b["history"] + b["who"]["identity"], now)
    return out


def _key(kind: str, cid: str, fact_id: str, suffix: str = "") -> str:
    return f"intel_{kind}_{cid}_{fact_id}" + (f"_{suffix}" if suffix else "")


async def _skip_reason(db, contact: dict, c: dict, sup: Optional[dict]) -> Optional[str]:
    cid, uid = str(contact["_id"]), str(contact.get("user_id") or "")
    if await db.tasks.find_one({"idempotency_key": _key(c["kind"], cid, c["fact_id"], c["key_suffix"])}, {"_id": 1}):
        return "exists"
    if await db.tasks.find_one({"user_id": uid, "contact_id": cid, "source": SOURCE, "intel_kind": c["kind"], "status": OPEN, "completed": {"$ne": True}}, {"_id": 1}):
        return "open_same_kind"
    if c["kind"] != "milestone":
        if contact.get("opted_out"):
            return "opted_out"
        if sup:
            return "suppressed"
        if await db.ai_reply_queue.find_one({"contact_id": cid, "status": "pending"}, {"_id": 1}):
            return "draft_pending"
    return None


async def write(db, contact: dict, cands: list, now: Optional[datetime] = None, *, dry: bool = False) -> dict:
    """Candidates -> tasks (source intelligence). Skips duplicates, opted-out / not-shopping contacts (milestones excepted) and threads with a Jessi draft waiting.
    A generic 90-day 'Reconnect' task for the same contact is dismissed so the two never coexist."""
    now = now or datetime.now(timezone.utc)
    cid, uid = str(contact["_id"]), str(contact.get("user_id") or "")
    out = {"contact_id": cid, "created": [], "skipped": []}
    if not uid or not cands:
        return out
    sup = await I.suppression(db, cid, now)
    name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
    for c in cands:
        reason = await _skip_reason(db, contact, c, sup)
        if reason:
            out["skipped"].append({"kind": c["kind"], "fact_id": c["fact_id"], "reason": reason})
            continue
        if dry:
            out["created"].append({"kind": c["kind"], "fact_id": c["fact_id"], "title": c["title"], "basis": c["basis"], "dry": True})
            continue
        doc = {
            "user_id": uid, "contact_id": cid, "contact_name": name, "contact_phone": contact.get("phone", ""),
            "type": "follow_up", "source": SOURCE, "intel_kind": c["kind"], "basis": c["basis"], "evidence": c["evidence"], "why": c["why"],
            "title": c["title"], "description": f"{c['why']} ({'Verified fact' if c['basis'] == 'verified' else 'Worth checking, not confirmed'}.)",
            "suggested_message": c["suggested_message"], "action_type": "text", "priority": c["priority"], "priority_order": c["priority_order"],
            "status": "pending", "completed": False, "due_date": c["due"], "channel": "sms", "created_at": now,
            "idempotency_key": _key(c["kind"], cid, c["fact_id"], c["key_suffix"]),
        }
        try:
            res = await db.tasks.insert_one(doc)
        except Exception as e:  # noqa: BLE001 - a racing duplicate key is a skip, not a failure
            out["skipped"].append({"kind": c["kind"], "fact_id": c["fact_id"], "reason": f"insert: {e}"[:80]})
            continue
        dismissed = await db.tasks.update_many({"user_id": uid, "contact_id": cid, "source": "system", "type": "follow_up", "status": OPEN, "completed": {"$ne": True}},
                                               {"$set": {"status": "dismissed", "dismissed_reason": "intelligence_nudge", "dismissed_at": now}})
        out["created"].append({"task_id": str(res.inserted_id), "kind": c["kind"], "fact_id": c["fact_id"], "title": c["title"], "basis": c["basis"], "dormant_dismissed": dismissed.modified_count})
    return out


async def run(db, *, user_id: Optional[str] = None, store_id: Optional[str] = None, contact_id: Optional[str] = None, dry: bool = False, limit: int = 5000, now: Optional[datetime] = None) -> dict:
    """Daily pass over every contact that has facts (optionally one rep, one store or one contact). Re-running creates nothing new."""
    now = now or datetime.now(timezone.utc)
    started = datetime.now(timezone.utc)
    if not dry and not enabled():
        return {"enabled": False, "dry": dry, "contacts": 0, "created": 0, "skipped": 0, "message": "INTEL_NUDGES is off"}
    q: dict = {}
    if user_id:
        q["owner_user_id"] = str(user_id)
    if store_id:
        q["store_id"] = str(store_id)
    if contact_id:
        q["contact_id"] = str(contact_id)
    ids = [ObjectId(i) for i in await db[F.FACTS].distinct("contact_id", q) if ObjectId.is_valid(str(i))][:limit]
    created, skipped, by_kind, details = 0, 0, {}, []
    async for contact in db.contacts.find({"_id": {"$in": ids}, "status": {"$nin": ["hidden", "merged", "deleted"]}, "user_id": {"$exists": True, "$ne": None}}):
        try:
            r = await write(db, contact, await candidates(db, contact, now), now, dry=dry)
        except Exception as e:  # noqa: BLE001 - one bad contact never stops the pass
            logger.warning("[Intel nudges] skipped contact %s: %s", contact.get("_id"), e)
            continue
        created += len(r["created"])
        skipped += len(r["skipped"])
        for c in r["created"]:
            by_kind[c["kind"]] = by_kind.get(c["kind"], 0) + 1
        if r["created"] or r["skipped"]:
            details.append(r)
    doc = {"at": started, "dry": dry, "user_id": user_id, "store_id": store_id, "contact_id": contact_id, "contacts": len(ids), "created": created, "skipped": skipped, "by_kind": by_kind,
           "processing_ms": int((datetime.now(timezone.utc) - started).total_seconds() * 1000), "details": details[:200]}
    res = await db[RUNS].insert_one(doc)
    return {**doc, "_id": None, "run_id": str(res.inserted_id), "at": F.iso(started), "enabled": enabled()}


async def runs(db, limit: int = 20) -> list:
    rows = await db[RUNS].find({}, {"details": 0}).sort("at", -1).to_list(limit)
    return [{**r, "_id": str(r["_id"]), "at": F.iso(r.get("at"))} for r in rows]
