"""Scan with Jessi, Phase C: key dates Jessi read on a quote, invoice, service paper or screenshot become SUGGESTED rep reminders.
Rules only (no second model call). A reminder is a task for the rep (source jessi_scan, never auto-texts, no calendar invite) and is
created only when the rep taps it. Private documents get no suggestions."""
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)

DOC_TYPES = {"quote": "Quote", "estimate": "Estimate", "purchase_order": "Purchase order", "invoice": "Invoice", "service": "Service paperwork",
             "spec_sheet": "Spec sheet", "form": "Form", "screenshot": "Screenshot", "other": "Document"}
WHATS = {"expires": "Expires", "appointment": "Appointment", "due": "Due", "delivery": "Delivery", "follow_up": "Follow up", "other": "Date"}
LEAD_DAYS = 3   # a quote reminder lands this many days before it expires
MAX_SUGGESTIONS = 3


def clean_dates(raw) -> list:
    out, seen = [], set()
    for d in raw if isinstance(raw, list) else []:
        if not isinstance(d, dict) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(d.get("date") or "")):
            continue
        try:
            date.fromisoformat(d["date"])
        except ValueError:
            continue
        what = d.get("what") if d.get("what") in WHATS else "other"
        if (what, d["date"]) in seen:
            continue
        seen.add((what, d["date"]))
        out.append({"date": d["date"], "what": what, "label": no_em_dash(" ".join(str(d.get("label") or "").split()))[:60] or WHATS[what]})
    return out[:4]


def doc_label(doc: dict) -> str:
    return DOC_TYPES.get(doc.get("doc_type") or "", "")


def _nice(day: date) -> str:
    return f"{day:%b} {day.day}"


def suggest(doc: dict, today: Optional[date] = None) -> list:
    """What the rep could be reminded about. Past dates drop off unless already created; dismissed ones never come back."""
    if doc.get("sensitive"):
        return []
    today = today or datetime.now(timezone.utc).date()
    acts = doc.get("actions") or {}
    kind = (doc_label(doc) or "document").lower()
    out = []
    for d in doc.get("dates") or []:
        try:
            day = date.fromisoformat(d["date"])
        except (KeyError, ValueError):
            continue
        key = f"{d['what']}_{d['date']}"
        act = acts.get(key) or {}
        if act.get("status") == "dismissed" or (day < today and act.get("status") != "created"):
            continue
        due = max(day - timedelta(days=LEAD_DAYS), today) if d["what"] == "expires" else day
        title = f"Follow up before the {kind} expires {_nice(day)}" if d["what"] == "expires" else f"{d.get('label') or WHATS[d['what']]} {_nice(day)}"
        out.append({"key": key, "what": d["what"], "date": d["date"], "label": d.get("label") or WHATS[d["what"]], "title": title[:90],
                    "due": act.get("due") or due.isoformat(), "status": act.get("status") or "", "task_id": act.get("task_id") or ""})
    return out[:MAX_SUGGESTIONS]


async def decide(db, user_id: str, doc: dict, contact: dict, key: str, decision: str = "create") -> dict:
    """Create (or dismiss) one suggested reminder. Idempotent: a second tap returns the task already made."""
    s = next((x for x in suggest(doc) if x["key"] == key), None)
    if not s:
        raise ValueError("That reminder is no longer available")
    if s["status"] == "created":
        return s
    now = datetime.now(timezone.utc)
    if decision == "dismiss":
        await db.contact_files.update_one({"_id": doc["_id"]}, {"$set": {f"actions.{key}": {"status": "dismissed", "at": now}}})
        return {**s, "status": "dismissed"}
    day = date.fromisoformat(s["due"])
    name = f"{contact.get('first_name') or ''} {contact.get('last_name') or ''}".strip()
    what = doc.get("title") or doc_label(doc) or "a document"
    first = contact.get("first_name") or ""
    task = {"user_id": user_id, "contact_id": str(contact["_id"]), "contact_name": name, "contact_phone": contact.get("phone") or "",
            "type": "follow_up", "source": "jessi_scan", "title": s["title"],
            "description": f"Jessi read this from {what} in {first + chr(39) + 's' if first else 'their'} Files. {doc.get('summary') or ''}".strip()[:400],
            "suggested_message": "", "action_type": "manual", "priority": "medium", "priority_order": 2, "status": "pending", "completed": False,
            "due_date": datetime(day.year, day.month, day.day, 15, 0, tzinfo=timezone.utc), "has_time": False, "appointment_type": None,
            "reminded_15": False, "reminded_due": False, "completed_at": None, "snoozed_until": None, "campaign_id": None, "campaign_name": None,
            "pending_send_id": None, "channel": "", "file_id": str(doc["_id"]), "created_at": now}
    r = await db.tasks.insert_one(task)
    tid = str(r.inserted_id)
    await db.contact_files.update_one({"_id": doc["_id"]}, {"$set": {f"actions.{key}": {"status": "created", "task_id": tid, "due": s["due"], "at": now}}})
    try:
        await db.contact_events.insert_one({"contact_id": str(contact["_id"]), "user_id": user_id, "event_type": "task_created", "channel": "system",
                                            "content_preview": s["title"], "metadata": {"task_id": tid, "description": task["description"], "priority": "medium",
                                                                                        "due_date": task["due_date"].isoformat(), "source": "jessi_scan", "file_id": str(doc["_id"])},
                                            "timestamp": now})
    except Exception as e:
        logger.warning(f"[DocReminders] event log failed: {e}")
    return {**s, "status": "created", "task_id": tid}
