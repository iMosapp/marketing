"""Ingest adapters: turn what the app already captures into facts. Each adapter has a pure `plan_*` (returns facts, used by the backfill dry run)
and an `apply` path that records through the status engine. Every adapter is a no-op unless INTEL_FACTS_INGEST is on, and host flows wrap calls in try/except."""
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

from services.intelligence import config, projection
from services.intelligence import facts as F
from services.intelligence import intent as I

logger = logging.getLogger(__name__)
MERGES = "contact_merges"

# voice_intel field -> (layer, domain, key, label)
MAP = {
    "spouse_name": ("identity", "family", "family.spouse", "Spouse"), "spouse_details": ("identity", "family", "family.spouse_details", "Spouse details"),
    "kids": ("identity", "family", "family.kid", "Kid"), "interests": ("state", "preference", "preference.interest", "Interest"),
    "occupation": ("state", "work", "work.occupation", "Occupation"), "employer": ("state", "work", "work.employer", "Employer"),
    "vehicle_purchased": ("state", "vehicle_owned", "vehicle.owned", "Owns"), "vehicle_color": ("state", "vehicle_owned", "vehicle.color", "Vehicle color"),
    "vehicle_details": ("state", "vehicle_owned", "vehicle.details", "Vehicle details"), "trade_in": ("state", "trade", "trade.vehicle", "Trade-in"),
    "purchase_context": ("state", "preference", "preference.purchase_context", "What matters in a purchase"), "important_dates": ("identity", "milestone", "milestone.date", "Important date"),
    "pets": ("identity", "family", "family.pet", "Pets"), "favorite_restaurant": ("state", "preference", "preference.restaurant", "Favorite restaurant"),
    "neighborhood": ("identity", "identity", "identity.neighborhood", "Lives in"), "referral_potential": ("state", "relationship", "relationship.referral", "Referral potential"),
    "personal_notes": ("state", "note", "note.personal", "Note"), "communication_preference": ("identity", "contact_pref", "contact.preferred_channel", "Prefers"),
}
CATEGORY_WORDS = {"service": "service", "finance": "finance", "financing": "finance", "lease": "finance", "trade": "trade", "appraisal": "appraisal", "sell": "appraisal"}


def _ts(v) -> Optional[datetime]:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, str) and v:
        try:
            d = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def quote_for(transcript: str, value) -> Optional[str]:
    """The sentence of the transcript that contains the value (or its most distinctive word); None when the words are not there."""
    if not transcript or value in (None, "", [], {}):
        return None
    label = value.get("name") or value.get("label") or value.get("description") if isinstance(value, dict) else str(value)
    if not label:
        return None
    sentences = re.split(r"(?<=[.!?\n])\s+", transcript)
    needles = [label.lower()] + sorted((t for t in re.findall(r"[a-z0-9']+", label.lower()) if len(t) >= 4), key=len, reverse=True)[:2]
    for n in needles:
        for s in sentences:
            if n in s.lower():
                return s.strip()[:220]
    return None


def _item_label(field: str, item) -> str:
    if isinstance(item, dict):
        if field == "kids":
            return " ".join(x for x in (item.get("name"), f"({item['details']})" if item.get("details") else "") if x).strip()
        if field == "important_dates":
            return " ".join(x for x in (item.get("description"), f"on {item['date']}" if item.get("date") else "") if x).strip()
        return item.get("label") or item.get("name") or str(item)
    return str(item).strip()


def plan_extraction(contact: dict, details: dict, *, transcript: str = "", source_kind: str, source_ref: str, occurred_at: datetime, recorded_at: Optional[datetime] = None,
                    conversation_id: Optional[str] = None, actor: Optional[dict] = None, extractor: Optional[dict] = None, precision: str = "exact", confidence: Optional[str] = None) -> list:
    """Extracted personal details -> facts. Rep's own words (voice memo, manual edit) are current; the customer's words need the quote to count as evidence;
    an AI inference without a quote on an identity-like key waits for a human (proposed)."""
    out = []
    for field, value in (details or {}).items():
        if field not in MAP or value in (None, "", [], {}):
            continue
        layer, domain, key, label = MAP[field]
        items = value if isinstance(value, list) else [value]
        for item in items:
            text = _item_label(field, item)
            if not text:
                continue
            q = quote_for(transcript, item)
            if source_kind in ("message", "call"):
                src = {"kind": source_kind if q else "ai_inference", "ref": source_ref, "quote": q, "conversation_id": conversation_id, "excerpt_at": occurred_at}
                conf = confidence or ("medium" if q else "low")
            else:
                src = {"kind": source_kind, "ref": source_ref, "quote": q, "conversation_id": conversation_id, "excerpt_at": occurred_at}
                conf = confidence or ("high" if actor else "medium")
            val = item if isinstance(item, dict) else {"label": text}
            out.append(F.make(contact, layer=layer, domain=domain, key=key, statement=f"{label}: {text}", value={**val, "label": text} if isinstance(val, dict) else val,
                              occurred_at=occurred_at, precision=precision, source=src, confidence=conf, actor=actor, extractor=extractor, recorded_at=recorded_at))
    return out


async def apply(db, facts: list, actor: Optional[dict] = None, *, sync: bool = True) -> dict:
    summary = {"created": 0, "reaffirmed": 0, "superseded": 0, "disputed": 0, "historical": 0, "duplicate": 0, "proposed": 0, "facts": []}
    for f in facts:
        r = await F.record(db, f, actor)
        summary[r["action"]] = summary.get(r["action"], 0) + 1
        if r["action"] == "created" and r["fact"]["status"] == "proposed":
            summary["proposed"] += 1
        summary["facts"].append(r["fact"])
    if sync and facts and (summary["created"] or summary["superseded"] or summary["disputed"] or summary["historical"]):
        summary["projection"] = await sync_legacy(db, facts[0]["contact_id"], facts[0].get("store_id"))
    return summary


async def sync_legacy(db, contact_id: str, store_id: Optional[str] = None) -> dict:
    """Phase 1B: after facts change, the legacy fields today's screens read follow (no-op while INTEL_LEGACY_PROJECTION is off)."""
    if not config.projection_enabled():
        return {"written": False, "sets": {}}
    try:
        return await projection.project(db, {"_id": contact_id, "store_id": store_id or None})
    except Exception as e:  # noqa: BLE001 - the fact write already happened; a projection hiccup must not fail the caller
        logger.warning("[Intel] legacy projection skipped for %s: %s", contact_id, e)
        return {"written": False, "sets": {}, "error": str(e)}


async def from_extraction(db, contact: dict, details: dict, **kw) -> Optional[dict]:
    if not config.ingest_enabled():
        return None
    return await apply(db, plan_extraction(contact, details, **kw), kw.get("actor"))


def _category(text: str) -> str:
    for w, c in CATEGORY_WORDS.items():
        if re.search(rf"\b{w}\w*", (text or "").lower()):
            return c
    return "purchase"


def _inquiry(lead: dict) -> dict:
    """inbound_leads.inquiry is a structured block ({kind, topic, vehicle, message, ...}); older rows may hold a plain string."""
    inq = lead.get("inquiry")
    if isinstance(inq, dict):
        return inq
    return {"message": str(inq or "")}


def plan_lead(contact: dict, lead: dict, settings: dict) -> Optional[dict]:
    raw = lead.get("vehicle_raw") or {}
    inq = _inquiry(lead)
    label = (lead.get("vehicle_interest") or "").strip() or " ".join(str(raw.get(k) or "") for k in ("vehicle_year", "vehicle_make", "vehicle_model", "vehicle_trim")).strip() or str(inq.get("vehicle") or "").strip()
    comments = str(lead.get("comments") or inq.get("message") or "").strip()
    if not label and not comments:
        return None
    at = _ts(lead.get("received_at") or lead.get("created_at")) or F.now_utc()
    first_line = re.sub(r"\s*\(from https?://\S+\)\s*$", "", comments.split("\n")[0], flags=re.I).strip() or comments[:80]
    value = {"label": label or first_line[:80], "year": raw.get("vehicle_year"), "make": raw.get("vehicle_make"), "model": raw.get("vehicle_model"), "trim": raw.get("vehicle_trim"), "stock": raw.get("vehicle_stock"), "from_comment": not label}
    source_name = lead.get("source_name") or inq.get("source_name") or "Website"
    stmt = f"{source_name} lead: asked about {label}" if label else f"{source_name} lead: {first_line[:120]}"
    return I.make(contact, settings, key="vehicle.interest", domain="vehicle_interest", statement=stmt, value=value, occurred_at=at, recorded_at=_ts(lead.get("created_at")) or at,
                  source={"kind": "lead_form", "ref": str(lead.get("_id") or lead.get("id") or ""), "quote": comments[:220] or None, "conversation_id": lead.get("conversation_id"), "excerpt_at": at},
                  category=_category(" ".join([comments, str(inq.get("topic") or ""), str(inq.get("kind") or "")])), confidence="high")


async def from_lead(db, contact: dict, lead: dict) -> Optional[dict]:
    """A new website/ADF inquiry is the newest active buying signal: it lifts a standing 'not shopping' and refreshes every open intent."""
    if not config.ingest_enabled():
        return None
    settings = await config.settings(db, contact.get("store_id"))
    f = plan_lead(contact, lead, settings)
    if not f:
        return None
    r = await F.record(db, f)
    if r["action"] == "created":
        await I.replace_matching(db, str(contact["_id"]), r["fact"])
    if r["action"] in ("created", "superseded", "reaffirmed"):
        await I.lift_suppression(db, str(contact["_id"]), r["fact"])
        await I.refresh(db, str(contact["_id"]), settings, f["occurred_at"], "inquiry")
        r["projection"] = await sync_legacy(db, str(contact["_id"]), contact.get("store_id"))
    return r


async def from_inbound_message(db, contact: dict, conversation_id: str, text: str, result: Optional[dict] = None, at: Optional[datetime] = None, message_id: Optional[str] = None) -> dict:
    """Every customer message is a real action: it refreshes open intents; an explicit 'not shopping' suppresses; a scored buying signal becomes an intent fact."""
    if not config.ingest_enabled():
        return {}
    settings = await config.settings(db, contact.get("store_id"))
    at = at or F.now_utc()
    cid = str(contact["_id"])
    src = {"kind": "message", "ref": message_id or conversation_id, "quote": (text or "")[:220], "conversation_id": conversation_id, "excerpt_at": at}
    out = {"refreshed": await I.refresh(db, cid, settings, at, "customer_reply")}
    if I.detect_purchased_elsewhere(text):
        # the customer closed the loop themselves: open interests become history (lost), the statement is kept as a record, nothing is pitched next
        f = F.make(contact, layer="history", domain="buying_status", key="purchase.elsewhere", statement=f'Bought elsewhere: "{(text or "")[:140]}"', value={"label": "bought elsewhere"}, occurred_at=at, source=src, confidence="high")
        r = await F.record(db, f)
        out["purchased_elsewhere"] = r["action"]
        if r["action"] == "created":
            out["closed"] = [str(x) for x in await I.close(db, cid, reason="lost", at=at, note="customer said they bought elsewhere")]
            out["projection"] = await sync_legacy(db, cid, contact.get("store_id"))
        return out
    if I.detect_not_shopping(text):
        out["not_shopping"] = (await I.not_shopping(db, contact, settings, at=at, source=src, quote=(text or "")[:220]))["action"]
        return out
    score = int((result or {}).get("score") or 0)
    if score >= 4:
        cat = _category(" ".join([(result or {}).get("category") or "", text or ""]))
        summary = (result or {}).get("hot_summary") or (result or {}).get("category") or "buying signal"
        f = I.make(contact, settings, key="buying.signal", domain="buying_status", statement=f"Buying signal {score}/10: {summary}", value={"label": summary[:120], "score": score, "signals": (result or {}).get("signals") or [], "category": cat},
                   occurred_at=at, source=src, category=cat, confidence="high" if score >= 7 else "medium")
        r = await F.record(db, f)
        out["signal"] = r["action"]
        if score >= 7 and r["action"] in ("created", "reaffirmed"):
            out["lifted"] = await I.lift_suppression(db, cid, r["fact"])
        if r["action"] == "created":
            out["projection"] = await sync_legacy(db, cid, contact.get("store_id"))
    return out


def plan_purchases(contact: dict, entries: list) -> list:
    out = []
    for e in entries or []:
        title = (e.get("title") or "").strip()
        if not title:
            continue
        day = _ts(e.get("date") + "T12:00:00+00:00" if isinstance(e.get("date"), str) and len(e.get("date")) == 10 else e.get("date")) or _ts(e.get("created_at")) or F.now_utc()
        rec = _ts(e.get("created_at")) or day
        src = {"kind": "sale", "ref": str(e.get("id") or ""), "quote": (e.get("notes") or "")[:220] or None}
        cat = e.get("category") or "vehicle"
        out.append(F.make(contact, layer="history", domain="vehicle_owned" if cat == "vehicle" else "experience", key="vehicle.purchase" if cat == "vehicle" else "purchase.other",
                          statement=f"Bought {title}" + (f" ({cat})" if cat != "vehicle" else ""), value={"label": title, "category": cat, "date": e.get("date")}, occurred_at=day, precision="day",
                          source=src, confidence="high", recorded_at=rec))
        if cat == "vehicle":
            out.append(F.make(contact, layer="state", domain="vehicle_owned", key="vehicle.owned", statement=f"Owns {title}", value={"label": title}, occurred_at=day, precision="day",
                              source=src, confidence="high", recorded_at=rec))
    return out


async def from_purchases(db, contact: dict, entries: list, actor: Optional[dict] = None) -> Optional[dict]:
    """A recorded sale: history + ownership facts; the matching open interest closes as purchased."""
    if not config.ingest_enabled():
        return None
    facts = plan_purchases(contact, entries)
    r = await apply(db, facts, actor)
    for f in facts:
        if f["key"] == "vehicle.purchase":
            r.setdefault("closed", []).extend(await I.close(db, str(contact["_id"]), reason="purchased", at=f["occurred_at"], match=f["value"], actor=actor, note=f"bought {f['value']['label']}"))
    return r


async def from_appraisal_vehicle(db, contact: dict, vehicle_label: str, vehicle_id: str, *, at: Optional[datetime] = None) -> Optional[dict]:
    """A vehicle appears on an appraisal: the customer probably owns it, but nobody has said so. Current, medium confidence, unconfirmed -> listed under 'verify', never projected."""
    if not config.ingest_enabled() or not vehicle_label:
        return None
    at = at or F.now_utc()
    return await apply(db, [F.make(contact, layer="state", domain="vehicle_owned", key="vehicle.owned", statement=f"Owns {vehicle_label} (per appraisal record, not confirmed)", value={"label": vehicle_label},
                                   occurred_at=at, source={"kind": "appraisal", "ref": vehicle_id, "excerpt_at": at}, confidence="medium")])


async def from_ownership(db, contact: dict, vehicle_label: str, status: str, *, at: Optional[datetime] = None, actor: Optional[dict] = None, vehicle_id: Optional[str] = None) -> Optional[dict]:
    """Manual ownership confirmation from the appraisal desk: owns -> current + confirmed by the person; traded/sold/no_longer_owns -> the owned fact becomes history with the outcome."""
    if not config.ingest_enabled():
        return None
    at = at or F.now_utc()
    cid = str(contact["_id"])
    src = {"kind": "appraisal", "ref": vehicle_id or "", "excerpt_at": at}
    if status == "owns":
        for f in await F.load(db, {"contact_id": cid, "key": "vehicle.owned", "status": "current"}):
            if I.matches(f.get("value"), vehicle_label) and actor:
                return {"confirmed": F.pub(await F.confirm(db, f["_id"], actor, note="ownership confirmed on the vehicle page", statement=f"Owns {vehicle_label}")), "projection": await sync_legacy(db, cid, contact.get("store_id"))}
        return await apply(db, [F.make(contact, layer="state", domain="vehicle_owned", key="vehicle.owned", statement=f"Owns {vehicle_label}", value={"label": vehicle_label}, occurred_at=at, source=src, confidence="high", actor=actor)], actor)
    if status not in ("traded", "sold", "no_longer_owns"):
        return None
    closed = []
    for f in await F.load(db, {"contact_id": cid, "key": "vehicle.owned", "status": "current"}):
        if I.matches(f.get("value"), vehicle_label):
            await F.set_status(db, f["_id"], "historical", actor, note=f"{status} per appraisal desk", outcome=status)
            closed.append(f["_id"])
    r = await apply(db, [F.make(contact, layer="history", domain="vehicle_owned", key="vehicle.disposed", statement=f"{vehicle_label}: {status.replace('_', ' ')}", value={"label": vehicle_label, "status": status},
                                occurred_at=at, source=src, confidence="high", actor=actor)], actor)
    r["closed"] = closed
    return r


IDENTITY_FIELDS = {"phone": ("contact.phone", "Phone"), "email": ("contact.email", "Email")}


def plan_rep_edit(contact_before: dict, changes: dict, actor: dict, at: Optional[datetime] = None) -> list:
    """A rep changed phone/email/name: the new value is a confirmed identity fact; the previous value is kept as history (recorded first so the chain is explicit)."""
    at = at or F.now_utc()
    out = []
    for field, (key, label) in IDENTITY_FIELDS.items():
        if field in changes and F.norm_value(changes[field]) != F.norm_value(contact_before.get(field)) and changes[field]:
            old = contact_before.get(field)
            if old:
                out.append(F.make(contact_before, layer="identity", domain="identity", key=key, statement=f"{label}: {old}", value={"label": str(old)}, occurred_at=_ts(contact_before.get("created_at")) or at,
                                  precision="unknown", source={"kind": "import", "ref": "legacy:contact"}, confidence="medium", recorded_at=_ts(contact_before.get("created_at")) or at))
            out.append(F.make(contact_before, layer="identity", domain="identity", key=key, statement=f"{label}: {changes[field]}", value={"label": str(changes[field])}, occurred_at=at,
                              source={"kind": "rep", "ref": f"user:{actor['_id']}"}, confidence="high", actor=actor))
    new_name = " ".join(x for x in (changes.get("first_name"), changes.get("last_name")) if x).strip()
    old_name = " ".join(x for x in (contact_before.get("first_name"), contact_before.get("last_name")) if x).strip()
    if new_name and F.norm_value(new_name) != F.norm_value(old_name):
        if old_name:
            out.append(F.make(contact_before, layer="identity", domain="identity", key="contact.name", statement=f"Name: {old_name}", value={"label": old_name}, occurred_at=_ts(contact_before.get("created_at")) or at,
                              precision="unknown", source={"kind": "import", "ref": "legacy:contact"}, confidence="medium", recorded_at=_ts(contact_before.get("created_at")) or at))
        out.append(F.make(contact_before, layer="identity", domain="identity", key="contact.name", statement=f"Name: {new_name}", value={"label": new_name}, occurred_at=at, source={"kind": "rep", "ref": f"user:{actor['_id']}"}, confidence="high", actor=actor))
    return out


async def from_rep_edit(db, contact_before: dict, changes: dict, actor: dict) -> Optional[dict]:
    if not config.ingest_enabled():
        return None
    facts = plan_rep_edit(contact_before, changes, actor)
    vi = (changes.get("vehicle_interest") or "").strip() if isinstance(changes.get("vehicle_interest"), str) else ""
    if vi and F.norm_value(vi) != F.norm_value(contact_before.get("vehicle_interest")):
        settings = await config.settings(db, contact_before.get("store_id"))
        facts.append(I.make(contact_before, settings, key="vehicle.interest", domain="vehicle_interest", statement=f"Rep noted interest in {vi}", value={"label": vi},
                            occurred_at=F.now_utc(), source={"kind": "rep", "ref": f"user:{actor['_id']}"}, confidence="high", actor=actor))
    r = await apply(db, facts, actor, sync=False)
    for f in r["facts"]:
        if f["key"] == "vehicle.interest" and f["status"] == "current":
            await I.replace_matching(db, str(contact_before["_id"]), f, actor)
    if facts:
        r["projection"] = await sync_legacy(db, str(contact_before["_id"]), contact_before.get("store_id"))
    return r


async def from_personal_details_edit(db, contact: dict, personal_details: dict, actor: dict) -> Optional[dict]:
    if not config.ingest_enabled():
        return None
    return await apply(db, plan_extraction(contact, personal_details, source_kind="rep", source_ref=f"user:{actor['_id']}", occurred_at=F.now_utc(), actor=actor), actor)


async def on_merge(db, primary_id: str, duplicate_id: str, user_id: str, counts: Optional[dict] = None) -> dict:
    """Facts follow the surviving contact and the merge itself becomes a record (who, when, what moved)."""
    moved = await db[F.FACTS].update_many({"contact_id": duplicate_id}, {"$set": {"contact_id": primary_id, "merged_from": duplicate_id, "updated_at": F.now_utc()}})
    await db[F.EVENTS].update_many({"contact_id": duplicate_id}, {"$set": {"contact_id": primary_id}})
    doc = {"primary_id": primary_id, "duplicate_id": duplicate_id, "by_user_id": user_id, "at": F.now_utc(), "facts_moved": moved.modified_count, "counts": counts or {}}
    await db[MERGES].insert_one(doc)
    return {"facts_moved": moved.modified_count}


async def contact_by_id(db, contact_id: str) -> Optional[dict]:
    return await db.contacts.find_one({"_id": ObjectId(str(contact_id))}) if ObjectId.is_valid(str(contact_id)) else None
