"""Reply In Your Voice (Phase 2B): the compact, dated block every AI writer reads before drafting, and the rationale the rep sees as "Why this reply?".
Built from facts only; nothing here sends anything. Returns None while INTEL_FACTS_INGEST is off so production prompts stay byte-identical."""
import re
from datetime import datetime, timezone
from typing import Optional

from services.intelligence import brief, config
from services.intelligence import intent as I
from services.intelligence.timeline import SOURCE_LABEL, _ago, _when

EXEMPLAR_MAX = 12
_URL = re.compile(r"https?://\S+", re.I)


def _label(f: dict) -> str:
    return (f.get("label") or f.get("statement") or "").strip()


def _via(f: dict) -> str:
    kind = (f.get("source") or {}).get("kind") or ""
    return SOURCE_LABEL.get(kind, kind.replace("_", " ")).lower()


def _confirmed(f: dict) -> bool:
    return (f.get("confirmations") or 0) >= 1


def _cite(ev: list, f: dict, text: str):
    if any(e["fact_id"] == f["id"] for e in ev):
        return
    kind = (f.get("source") or {}).get("kind")
    ev.append({"fact_id": f["id"], "label": text, "source": SOURCE_LABEL.get(kind, kind), "at": f.get("occurred_at"), "confirmed": _confirmed(f)})


def subject_interest(b: dict) -> Optional[dict]:
    """The vehicle the conversation is about: the driving intent when it names a vehicle, else the newest open vehicle interest behind a buying signal."""
    drv = b["now"]["driving"]
    if not drv:
        return None
    if drv["key"] == "vehicle.interest":
        return drv
    return next((f for f in b["now"]["active_intent"] if f["key"] == "vehicle.interest" and f.get("phase") != "dormant"), None)


def from_comment(f: dict) -> bool:
    return isinstance(f.get("value"), dict) and bool(f["value"].get("from_comment"))


def about(f: dict) -> str:
    """'the 2025 Ford F-150 Lariat' for a named vehicle, 'their website inquiry ("...")' when the lead only had a comment."""
    if from_comment(f):
        return f'their website inquiry ("{_label(f)[:60]}")'
    return f"the {_label(f)}" if f.get("key") == "vehicle.interest" else _label(f)


async def build(db, contact: dict, now: Optional[datetime] = None) -> Optional[dict]:
    """{"text": prompt block, "rationale": {topic, why, mode, summary, evidence[]}} or None when the engine is off."""
    if not config.ingest_enabled():
        return None
    now = now or datetime.now(timezone.utc)
    b = await brief.build(db, contact, now)
    if not b["counts"]["facts"]:
        return None
    first = (contact.get("first_name") or "the customer").strip().split(" ")[0]
    drv, sup, mode = b["now"]["driving"], b["now"]["suppression"], b["next"]["mode"]
    owned = sorted(b["who"]["owns"], key=lambda f: not _confirmed(f))
    history = b["history"]
    lost = [f for f in history if f["key"] == "purchase.elsewhere"]
    past_interest = [f for f in history if f["key"] == "vehicle.interest"]
    purchases = [f for f in history if f["key"] in ("vehicle.purchase", "purchase.other")]
    dormant = [f for f in b["now"]["active_intent"] if f.get("phase") == "dormant"]
    ev: list = []
    lines = ["=== WHAT THE FACTS SAY (dated and sourced; the newest buying signal comes first) ==="]

    if drv:
        label, ago, via = _label(drv), _ago(drv.get("last_signal_at") or drv.get("occurred_at"), now), _via(drv)
        from_comment = isinstance(drv.get("value"), dict) and drv["value"].get("from_comment")
        subject = subject_interest(b)
        if drv["key"] == "buying.signal":
            what = f"showed a buying signal: {label}"
        elif from_comment:
            what = f'sent a website inquiry: "{label[:120]}" (no vehicle named)'
        else:
            what = f"asked about the {label}"
        about_line = ""
        if subject and subject["id"] != drv["id"]:
            about_line = f" This is about {about(subject)} from {_ago(subject.get('occurred_at'), now)} via {_via(subject)}."
        lines.append(f"RIGHT NOW (lead with this): {first} {what}, {ago} via {via} ({drv.get('phase')}).{about_line} Answer this first; everything below is background.")
        _cite(ev, drv, f"website inquiry {ago}" if from_comment else (f"{label[:60]} inquiry {ago}" if drv["key"] == "vehicle.interest" else f"buying signal {ago}"))
        if subject and subject["id"] != drv["id"]:
            _cite(ev, subject, f"{_label(subject)[:60]} inquiry {_ago(subject.get('occurred_at'), now)}")
        also = [a for a in b["discuss"]["also_active"] if not subject or a != _label(subject)]
        if also:
            lines.append("ALSO OPEN: " + "; ".join(also[:3]))
    elif mode == "lost" and lost:
        ago = _ago(lost[0].get("occurred_at"), now)
        lines.append(f"RIGHT NOW: {first} said {ago} that they bought somewhere else. No pitch; be glad for them and stay useful.")
        _cite(ev, lost[0], f"bought elsewhere {ago}")
    elif mode == "suppressed" and sup:
        ago = _ago(sup.get("occurred_at"), now)
        lines.append(f"RIGHT NOW: {first} said they are not shopping ({ago}). No buying-intent follow-ups until they bring it up themselves.")
        _cite(ev, sup, f"said not shopping {ago}")
    elif mode == "dormant" and dormant:
        d = dormant[0]
        lines.append(f"RIGHT NOW: no active buying signal. Interest in the {_label(d)} went quiet {d.get('days_since_signal')} days ago; a light check-in is fine, no pressure.")
        _cite(ev, d, f"{_label(d)} interest, quiet {d.get('days_since_signal')} days")
    else:
        lines.append("RIGHT NOW: no open buying signal on record. This is a relationship touch, not a sales conversation.")

    rel = []
    for o in owned[:2]:
        when = _when(o.get("occurred_at"))
        who = (o.get("confirmed_by") or {}).get("name")
        note = f"confirmed by {who}" if _confirmed(o) and who else ("confirmed" if _confirmed(o) else "NOT confirmed, do not state as fact")
        rel.append(f"owns {_label(o)} (since {when}; {note})")
        _cite(ev, o, f"owns {_label(o)} since {when}" + ("" if _confirmed(o) else " (unconfirmed)"))
    owned_labels = {_label(o).lower() for o in owned}
    for p in purchases[:2]:
        if _label(p).lower() not in owned_labels:
            rel.append(f"bought {_label(p)} in {_when(p.get('occurred_at'))}")
    for p in past_interest[:2]:
        rel.append(f"asked about the {_label(p)} in {_when(p.get('occurred_at'))} ({p.get('outcome') or 'no outcome recorded'})")
        if drv and I.matches(p.get("value"), drv.get("value")):
            _cite(ev, p, f"asked about {_label(p)} in {_when(p.get('occurred_at'))}")
    known = [f for f in b["who"]["known"] + b["who"]["identity"] if not str(f.get("key", "")).startswith(("contact.", "relationship."))]
    for f in known[:6]:
        if f["key"] in ("family.spouse", "work.occupation", "work.employer", "vehicle.color", "trade.vehicle") and not _confirmed(f):
            continue
        rel.append(f.get("statement") or _label(f))
    if rel:
        lines.append("RELATIONSHIP (use only if it helps THIS reply, never as a list): " + "; ".join(rel))

    dont = []
    if sup:
        dont.append(f"pitch anything ({first} said they are not shopping {_ago(sup.get('occurred_at'), now)})")
    if lost and not drv and mode == "lost":
        dont.append(f"pitch anything (they bought elsewhere {_ago(lost[0].get('occurred_at'), now)})")
    unverified = [v["statement"] for v in b["verify"] if v.get("statement")][:4]
    if unverified:
        dont.append("state these as facts, nobody has confirmed them: " + "; ".join(unverified))
    dont.append("invent details that are not listed here")
    lines.append("DO NOT: " + " | ".join(dont))

    ask = []
    subject = subject_interest(b) if drv else None
    if subject and owned and not any(I.matches(o.get("value"), subject.get("value")) for o in owned):
        o = owned[0]
        ask.append(f"Is the {_label(o)} a trade-in, or is this an additional vehicle?" if _confirmed(o) else f"Are they still driving the {_label(o)} (not confirmed), and would it be a trade?")
    elif mode == "verify_ownership" and owned:
        ask.append(f"Is the {_label(owned[0])} still theirs?")
    if ask:
        lines.append("WORTH ASKING (one question max, only if it fits): " + " ".join(ask))
    pref = next((f for f in b["who"]["identity"] + b["who"]["known"] if f.get("key") == "contact.preferred_channel"), None)
    if pref:
        lines.append(f"PREFERS: {_label(pref)}")

    summary = "Based on: " + ", ".join(e["label"] for e in ev[:3]) if ev else ""
    return {"text": "\n".join(lines), "rationale": {"topic": b["discuss"]["topic"], "why": b["discuss"]["why"], "mode": mode, "summary": summary, "evidence": ev[:5]}}


async def style_exemplars(db, user_id: str) -> str:
    """The rep's own recent, hand-typed texts (not AI, not campaign, no links) as 'write like these' examples. Empty while the engine is off."""
    if not config.ingest_enabled() or not user_id:
        return ""
    rows = await db.messages.find(
        {"user_id": str(user_id), "sender": "user", "direction": "outbound", "channel": {"$in": ["sms", "sms_personal", None]},
         "event_type": {"$in": [None, "personal_sms", "sms_sent", "thank_you_text_sent"]}, "kind": {"$exists": False}, "type": {"$nin": ["call_log", "webchat_transcript"]},
         "ai_generated": {"$ne": True}, "template_id": {"$exists": False}, "campaign_id": {"$exists": False}, "has_media": {"$ne": True}, "content": {"$type": "string"}},
        {"content": 1}).sort("timestamp", -1).limit(80).to_list(80)
    seen, out = set(), []
    for r in rows:
        text = re.sub(r"\s+", " ", str(r.get("content") or "")).strip()
        if not (20 <= len(text) <= 320) or _URL.search(text) or text.lower() in seen:
            continue
        seen.add(text.lower())
        out.append(text)
        if len(out) >= EXEMPLAR_MAX:
            break
    if len(out) < 3:
        return ""
    return "\n\nHOW I ACTUALLY TEXT (my own recent messages; match this rhythm, length and warmth, never copy them):\n" + "\n".join(f'- "{t}"' for t in out)
