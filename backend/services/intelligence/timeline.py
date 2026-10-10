"""Intelligent Timeline: what the contact screen shows above the familiar History feed (Recommended / Active / Current / Historical markers), in plain words, plus the source behind any belief."""
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

from services.intelligence import brief, config
from services.intelligence import facts as F

SOURCE_LABEL = {"message": "Text message", "call": "Phone call", "voice_memo": "Voice memo", "lead_form": "Lead form", "sale": "Sale record", "appraisal": "Appraisal", "rep": "Entered by rep", "import": "Contact record", "appointment": "Appointment", "ai_inference": "AI reading"}
DOMAIN_GROUP = {"vehicle_owned": "drives", "family": "household", "work": "work", "preference": "preferences", "contact": "contact", "identity": "contact", "trade": "drives", "vehicle_color": "drives", "milestone": "household", "buying_status": "preferences"}


def _dt(s):
    if isinstance(s, datetime):
        return s
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _ago(iso: Optional[str], now: datetime) -> str:
    d = _dt(iso)
    if not d:
        return ""
    days = (now - d).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 30:
        return f"{days} days ago"
    if days < 365:
        return f"{days // 30} months ago" if days >= 60 else "a month ago"
    return f"{days // 365} years ago" if days >= 730 else "a year ago"


def _when(iso: Optional[str]) -> str:
    d = _dt(iso)
    return d.strftime("%b %Y") if d else ""


def _confirmed(f: dict) -> bool:
    return (f.get("confirmations") or 0) >= 1


def _active_chip(f: dict, now: datetime) -> dict:
    src = (f.get("source") or {}).get("kind", "")
    via = SOURCE_LABEL.get(src, src).lower()
    phase = f.get("phase")
    when = _ago(f.get("last_signal_at") or f.get("occurred_at"), now)
    label = f.get("label") or f.get("statement")
    from_comment = isinstance(f.get("value"), dict) and f["value"].get("from_comment")
    kind = "signal" if f.get("key") == "buying.signal" else ("inquiry" if from_comment else "interest")
    status = "going quiet" if phase == "aging" else ("quiet" if phase == "dormant" else "")
    return {"fact_id": f["id"], "kind": kind, "label": ("Website inquiry: " if from_comment else "") + label, "detail": ", ".join(x for x in (when, f"via {via}" if via else "", status) if x), "phase": phase, "occurred_at": f.get("occurred_at")}


def _current_item(f: dict) -> dict:
    by = (f.get("confirmed_by") or {}).get("name")
    return {"fact_id": f["id"], "label": f.get("label") or f.get("statement"), "key": f["key"], "confirmed": _confirmed(f), "by": by, "since": _when(f.get("occurred_at")), "stale_days": f.get("stale_days")}


def _marker(f: dict, title: str, description: str, icon: str, kind: str) -> dict:
    return {"event_type": "intel_milestone", "category": "milestone", "icon": icon, "color": "#C9A962", "title": title, "description": description, "timestamp": f.get("occurred_at"), "fact_id": f["id"], "kind": kind, "intel": True}


def markers(st_history: list, current: list) -> list:
    """Historical markers from facts, shaped like contact_events rows so the existing feed renders them in its date groups."""
    out = []
    labels = {f["id"]: f.get("label") or f.get("statement") for f in st_history + current}
    for f in st_history:
        k, outcome = f["key"], f.get("outcome")
        if k in ("purchase.vehicle", "purchase.other"):
            out.append(_marker(f, f"Bought {f.get('label')}", "Purchase on record", "car-sport" if k == "purchase.vehicle" else "pricetag", "purchase"))
        elif k == "vehicle.disposed":
            status = (f.get("value") or {}).get("status", "no longer owns").replace("_", " ")
            out.append(_marker(f, f"{f.get('label')}: {status}", "Ownership changed", "swap-horizontal", "disposed"))
        elif k == "purchase.elsewhere":
            out.append(_marker(f, "Bought elsewhere", (f.get("source") or {}).get("quote") or f.get("statement"), "exit", "lost"))
        elif k == "vehicle.interest" and f.get("status") == "historical" and outcome:
            word = {"purchased": "bought", "lost": "went elsewhere", "cancelled": "cancelled", "declined": "declined"}.get(outcome, outcome)
            out.append(_marker(f, f"Interest in {f.get('label')} closed: {word}", f.get("statement"), "flag", "interest_closed"))
        elif k == "vehicle.interest" and f.get("status") == "historical":
            out.append(_marker(f, f"Was looking at {f.get('label')}", "Older interest, no outcome recorded", "time", "interest_quiet"))
        elif k == "buying.status" and f.get("expired"):
            out.append(_marker(f, "Said they were not shopping", f.get("statement"), "pause", "not_shopping"))
        elif f.get("status") == "superseded" and f.get("superseded_by") and f.get("superseded_by") in labels:
            field = (f.get("key") or "").split(".")[-1].replace("_", " ")
            out.append(_marker(f, f"{field.capitalize()} changed: {f.get('label')} -> {labels[f['superseded_by']]}", "Updated from a newer source", "git-compare", "change"))
    for f in current:
        if f["key"] == "vehicle.owned" and (f.get("source") or {}).get("kind") == "sale":
            out.append(_marker(f, f"Bought {f.get('label')}", "Purchase on record", "car-sport", "purchase"))
    out.sort(key=lambda m: m["timestamp"] or "", reverse=True)
    return out


async def build(db, contact: dict, now: Optional[datetime] = None) -> dict:
    if not config.ingest_enabled():
        return {"enabled": False}
    now = now or datetime.now(timezone.utc)
    b = await brief.build(db, contact, now)
    drv = b["now"]["driving"]
    active = [_active_chip(f, now) for f in b["now"]["active_intent"] if f.get("phase") != "dormant"]
    current: dict = {"drives": [], "household": [], "work": [], "preferences": [], "contact": []}
    for f in b["who"]["owns"] + b["who"]["known"] + b["who"]["identity"]:
        current.setdefault(DOMAIN_GROUP.get(f.get("domain"), "preferences"), []).append(_current_item(f))
    current["drives"].sort(key=lambda x: (not x["confirmed"], x["since"]), reverse=False)
    sup = b["now"]["suppression"]
    needs = [{"fact_id": v["id"] if "id" in v else v.get("fact_id"), "statement": v["statement"], "reason": "unconfirmed" if v.get("unverified") else ("stale" if v.get("stale_days") else v.get("status"))} for v in b["verify"]]
    rec = None
    if b["discuss"]["topic"]:
        rec = {"topic": b["discuss"]["topic"], "why": b["discuss"]["why"], "opening": b["discuss"]["opening"], "action": b["next"]["action"], "mode": b["next"]["mode"], "mention_history": b["discuss"]["mention_history"],
               "evidence": [{"fact_id": e["fact_id"], "source": SOURCE_LABEL.get(e.get("source"), e.get("source")), "at": e.get("at")} for e in b["evidence"]]}
    return {
        "enabled": True, "as_of": b["as_of"], "name": b["name"],
        "recommended": rec,
        "active": active,
        "driving_fact_id": drv["id"] if drv else None,
        "suppression": {"fact_id": sup["id"], "label": sup.get("label") or sup.get("statement"), "when": _ago(sup.get("occurred_at"), now)} if sup else None,
        "current": current,
        "needs_look": needs,
        "markers": markers(b["history"], b["who"]["owns"] + b["who"]["known"] + b["who"]["identity"]),
        "counts": b["counts"],
    }


async def source(db, fact: dict, contact: dict) -> dict:
    """The record behind a belief: what, when, who, the exact excerpt, and where to open it in the app."""
    src = fact.get("source") or {}
    kind, ref = src.get("kind"), str(src.get("ref") or "")
    who = (fact.get("confirmed_by") or {}).get("name")
    out = {"fact_id": fact["id"], "statement": fact["statement"], "kind": kind, "label": SOURCE_LABEL.get(kind, kind or "Unknown"), "title": SOURCE_LABEL.get(kind, kind or "Unknown"), "excerpt": src.get("quote"), "at": fact.get("occurred_at"), "who": who, "link": None,
           "confirmed": _confirmed(fact), "status": fact.get("status"), "evidence_count": len(fact.get("evidence") or []), "other_sources": sorted({SOURCE_LABEL.get(e.get("kind"), e.get("kind")) for e in (fact.get("evidence") or []) if e.get("kind") != kind})}
    cid = str(contact["_id"])
    try:
        if kind == "message":
            conv_id = src.get("conversation_id")
            msg = await db.messages.find_one({"_id": ObjectId(ref), "contact_id": cid}) if ObjectId.is_valid(ref) else None
            if msg:
                out["excerpt"] = msg.get("content") or out["excerpt"]
                out["at"] = F.iso(msg.get("created_at")) or out["at"]
                conv_id = conv_id or msg.get("conversation_id")
            out["title"] = f"Text from {contact.get('first_name') or 'the customer'}"
            if conv_id and str(conv_id).startswith("conv_intel:"):
                conv_id = None
            out["link"] = f"/thread/{conv_id}" if conv_id else None
        elif kind == "call":
            call = await db.call_logs.find_one({"_id": ObjectId(ref), "contact_id": cid}) if ObjectId.is_valid(ref) else None
            if call:
                out["excerpt"] = out["excerpt"] or (call.get("ai_summary") or (call.get("transcript") or "")[:400])
                out["at"] = F.iso(call.get("timestamp") or call.get("created_at")) or out["at"]
            out["title"] = "Phone call"
            out["link"] = f"/contact/{cid}?tab=history&filter=calls"
        elif kind == "voice_memo":
            note = await db.voice_notes.find_one({"_id": ObjectId(ref), "contact_id": cid}) if ObjectId.is_valid(ref) else None
            if note:
                out["excerpt"] = out["excerpt"] or (note.get("transcript") or "")[:400]
                out["at"] = F.iso(note.get("created_at")) or out["at"]
            out["title"] = "Your voice memo"
            out["link"] = f"/contact/{cid}?tab=history&filter=memos"
        elif kind == "lead_form":
            lead = await db.inbound_leads.find_one({"_id": ObjectId(ref)}) if ObjectId.is_valid(ref) else None
            if lead and str(lead.get("contact_id") or "") in ("", cid):
                inq = lead.get("inquiry") if isinstance(lead.get("inquiry"), dict) else {}
                parts = [p for p in (lead.get("vehicle_interest"), lead.get("comments") or inq.get("message")) if p]
                out["excerpt"] = "\n".join(parts) or out["excerpt"]
                out["title"] = f"{lead.get('source_name') or 'Website'} lead"
                out["at"] = F.iso(lead.get("received_at") or lead.get("created_at")) or out["at"]
                if lead.get("conversation_id"):
                    out["link"] = f"/thread/{lead['conversation_id']}"
        elif kind == "sale":
            entry = next((p for p in (contact.get("purchase_history") or []) if str(p.get("id")) == ref), None)
            if entry:
                out["excerpt"] = f"{entry.get('title')} on {entry.get('date')}" + (f". {entry.get('notes')}" if entry.get("notes") else "")
            out["title"] = "Sale record"
            out["link"] = f"/contact/{cid}?purchase={ref}"
        elif kind == "appraisal":
            veh = await db.vehicles.find_one({"_id": ObjectId(ref), "contact_id": cid}) if ObjectId.is_valid(ref) else None
            if veh:
                label = " ".join(str(veh.get(k) or "") for k in ("year", "make", "model", "trim")).strip()
                out["excerpt"] = f"{label}" + (f", VIN {veh.get('vin')}" if veh.get("vin") else "") + f". Ownership on the vehicle record: {str(veh.get('ownership_status') or 'unknown').replace('_', ' ')}"
                out["at"] = F.iso(veh.get("ownership_updated_at") or veh.get("created_at")) or out["at"]
            out["title"] = "Appraisal vehicle record"
            out["link"] = f"/vehicle/{ref}" if ObjectId.is_valid(ref) else None
        elif kind == "rep":
            out["title"] = f"Entered by {who or 'a teammate'}"
            out["excerpt"] = out["excerpt"] or fact["statement"]
        elif kind == "import":
            out["title"] = "From the contact record"
            out["excerpt"] = out["excerpt"] or "This was already on the contact card before relationship intelligence was turned on; nobody has confirmed it since."
    except Exception:  # noqa: BLE001 - a missing record must not break the sheet; the quote on the fact still shows
        pass
    return out
