"""Layer E, deterministic base: topic, why now, opening line, next action, history worth mentioning, what to verify, evidence.
Rules only; Phase 4 adds one phrasing call on top. Nothing here sends anything."""
from datetime import datetime, timezone
from typing import Optional

from services.intelligence import intent as I


def _first(contact: dict) -> str:
    return (contact.get("first_name") or "there").strip().split(" ")[0]


def _ago(iso: Optional[str], now: datetime) -> str:
    if not iso:
        return ""
    d = (now - datetime.fromisoformat(iso)).days
    return "today" if d <= 0 else ("yesterday" if d == 1 else f"{d} days ago" if d < 60 else f"{d // 30} months ago")


def _when(iso: Optional[str]) -> str:
    return datetime.fromisoformat(iso).strftime("%b %Y") if iso else ""


def recommend(contact: dict, st: dict, now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    first = _first(contact)
    owned = [f for f in st["current_state"] + st["history"] if f["key"] == "vehicle.owned" and f["status"] == "current"]
    owned_label = owned[0]["label"] if owned else ""
    owned_note = "" if not owned or (owned[0].get("confirmations") or 0) >= 1 else " (ownership not confirmed yet)"
    past_interests = [f for f in st["history"] if f["key"] == "vehicle.interest"]
    verify = [{"fact_id": f["id"], "statement": f["statement"], "status": f["status"], "stale_days": f.get("stale_days"), "unverified": f.get("unverified", False)} for f in st["needs_verification"]]
    driving, sup = st.get("driving"), st.get("suppression")
    dormant = [f for f in st["active_intent"] if f.get("phase") == "dormant"]
    lost = [f for f in st["history"] if f["key"] == "purchase.elsewhere" and (now - datetime.fromisoformat(f["occurred_at"])).days <= 90]
    evidence, mention = [], []

    if driving:
        label = driving["label"]
        evidence.append({"fact_id": driving["id"], "source": driving["source"].get("kind"), "ref": driving["source"].get("ref"), "at": driving["occurred_at"]})
        related = [p for p in past_interests if I.matches(p.get("value"), driving.get("value"))]
        for p in related[:2]:
            mention.append(f"Asked about {p['label']} in {_when(p['occurred_at'])} ({p.get('outcome') or 'no outcome recorded'})")
            evidence.append({"fact_id": p["id"], "source": p["source"].get("kind"), "ref": p["source"].get("ref"), "at": p["occurred_at"]})
        if owned:
            mention.append(f"Owns {owned_label} (recorded {_when(owned[0]['occurred_at'])}){owned_note}")
            evidence.append({"fact_id": owned[0]["id"], "source": owned[0]["source"].get("kind"), "ref": owned[0]["source"].get("ref"), "at": owned[0]["occurred_at"]})
        others = [f for f in st["active_intent"] if f["id"] != driving["id"] and f.get("phase") != "dormant"]
        from_comment = driving["key"] == "vehicle.interest" and isinstance(driving.get("value"), dict) and driving["value"].get("from_comment")
        bridge = (f" Is this to replace your {owned_label}, or an additional vehicle?" if owned and driving["key"] == "vehicle.interest" else " What matters most to you in it?")
        if from_comment:
            topic = "Their website inquiry (no vehicle named)"
            opening = f"Hi {first}, I saw your note: \"{label[:100]}\". Happy to help. Which vehicle were you looking at?"
        elif driving["key"] == "vehicle.interest":
            topic, opening = label, f"Hi {first}, I saw your inquiry on the {label}.{bridge}"
        else:
            topic, opening = label, f"Hi {first}, thanks for reaching out. {driving['statement'].rstrip('.')}. What would be most helpful right now?"
        return {"topic": topic, "why": f"Newest active buying signal, {_ago(driving['occurred_at'], now)} via {driving['source'].get('kind', 'unknown').replace('_', ' ')} ({driving.get('phase')}).",
                "opening": opening, "action": "Reply today with one qualifying question; do not pitch anything else first." if driving.get("phase") == "active" else "Follow up this week; the signal is aging.",
                "also_active": [f["label"] for f in others], "mention_history": mention, "verify": verify, "evidence": evidence, "mode": "active_intent"}
    if lost:
        lo = lost[0]
        evidence.append({"fact_id": lo["id"], "source": lo["source"].get("kind"), "ref": lo["source"].get("ref"), "at": lo["occurred_at"]})
        closed = [p for p in past_interests if p.get("outcome") == "lost"][:2]
        for p in closed:
            mention.append(f"Was looking at {p['label']} in {_when(p['occurred_at'])} (bought elsewhere)")
            evidence.append({"fact_id": p["id"], "source": p["source"].get("kind"), "ref": p["source"].get("ref"), "at": p["occurred_at"]})
        return {"topic": "They bought elsewhere; stay the trusted contact", "why": f"Customer said {_ago(lo['occurred_at'], now)} they bought somewhere else; no open buying signal.",
                "opening": f"Hi {first}, congrats on the new ride! No pitch here. If you ever want a second set of eyes on service or a future trade, I am around.",
                "action": "Thank them, no selling; set a 6-month ownership check-in.", "also_active": [], "mention_history": mention, "verify": verify, "evidence": evidence, "mode": "lost"}
    if sup:
        evidence.append({"fact_id": sup["id"], "source": sup["source"].get("kind"), "ref": sup["source"].get("ref"), "at": sup["occurred_at"]})
        return {"topic": "Relationship touch, no selling", "why": f"Customer said they are not shopping ({_ago(sup['occurred_at'], now)}); suppression holds until {sup.get('active_until', '')[:10]}.",
                "opening": f"Hi {first}, no sales pitch, just checking in. Anything I can help with on your {owned_label}?" if owned else f"Hi {first}, no sales pitch, just checking in. Hope all is well.",
                "action": "Do not send buying-intent follow-ups until the suppression ends or the customer reaches out.", "also_active": [], "mention_history": [f"Owns {owned_label}"] if owned else [],
                "verify": verify, "evidence": evidence, "mode": "suppressed"}
    if dormant:
        d = dormant[0]
        evidence.append({"fact_id": d["id"], "source": d["source"].get("kind"), "ref": d["source"].get("ref"), "at": d["occurred_at"]})
        return {"topic": f"Re-check interest in {d['label']}", "why": f"Interest went quiet {d.get('days_since_signal')} days ago; dormant, not 'not shopping'.",
                "opening": f"Hi {first}, a while back you mentioned the {d['label']}. Still on your radar, or has that changed?", "action": "One light check-in; if no reply, leave it as history.",
                "also_active": [], "mention_history": [f"Owns {owned_label}"] if owned else [], "verify": verify, "evidence": evidence, "mode": "dormant"}
    if owned:
        evidence.append({"fact_id": owned[0]["id"], "source": owned[0]["source"].get("kind"), "ref": owned[0]["source"].get("ref"), "at": owned[0]["occurred_at"]})
        if owned_note:
            return {"topic": f"Confirm they still own the {owned_label}", "why": "The only ownership record comes from an appraisal; nobody has confirmed it.",
                    "opening": f"Hi {first}, quick one: is the {owned_label} still yours? Want to make sure I have your garage right.", "action": "Ask once; confirm or dispute the ownership fact from the reply.",
                    "also_active": [], "mention_history": [], "verify": verify, "evidence": evidence, "mode": "verify_ownership"}
        return {"topic": f"Ownership check-in on the {owned_label}", "why": "No open buying signal; keep the relationship warm.",
                "opening": f"Hi {first}, how is the {owned_label} treating you? Anything you need from us?", "action": "Relationship touch; log anything you learn as a voice note.",
                "also_active": [], "mention_history": [], "verify": verify, "evidence": evidence, "mode": "relationship"}
    return {"topic": "Get to know the customer", "why": "Nothing current on record.", "opening": f"Hi {first}, it has been a while. What are you driving these days?",
            "action": "Open a conversation and capture what you learn.", "also_active": [], "mention_history": [], "verify": verify, "evidence": evidence, "mode": "cold"}
