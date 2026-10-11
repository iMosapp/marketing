"""Stage 3: simplified pilot onboarding. Everything here is derived from existing collections (users, contacts, contact_events,
voice_notes, bug_reports); the only write is the first-completion timestamp per step on the user document."""
import logging
from datetime import datetime, timezone

from bson import ObjectId

from services import customers as cust

logger = logging.getLogger(__name__)

CARD_SHARE_EVENTS = {"digital_card_shared", "card_qr_shown", "vcf_shared", "digital_card_sent"}
STEPS = [
    {"key": "profile", "title": "Complete your profile and photo", "hint": "Your name and photo are what customers see first", "route": "/my-account"},
    {"key": "card", "title": "Complete your digital business card", "hint": "Add your title and a short bio", "route": "/my-account"},
    {"key": "contact", "title": "Add your first contact", "hint": "Someone you talked to today", "route": "/contact/new"},
    {"key": "share", "title": "Share your digital card", "hint": "Text it or show the QR code", "route": "share"},
    {"key": "memo", "title": "Record your first customer voice memo", "hint": "30 seconds after a conversation", "route": "/voice-memos"},
]
OPEN_ISSUE_STATUSES = ["open", "in_progress"]


def _iso(v) -> str | None:
    if isinstance(v, datetime):
        return v.isoformat()
    return v or None


async def _step_states(db, user: dict) -> dict:
    uid = str(user["_id"])
    persona = user.get("persona") or {}
    photo = bool(user.get("photo_url") or user.get("photo_path"))
    first_contact = await db.contacts.find_one({"user_id": uid, "source": {"$ne": "user_creation"}}, {"created_at": 1}, sort=[("created_at", 1)])
    first_share = await db.contact_events.find_one({"user_id": uid, "event_type": {"$in": sorted(CARD_SHARE_EVENTS)}}, {"timestamp": 1, "created_at": 1}, sort=[("timestamp", 1)])
    first_scan = None if first_share else await db.card_scans.find_one({"user_id": uid}, {"scanned_at": 1}, sort=[("scanned_at", 1)])
    first_memo = await db.voice_notes.find_one({"user_id": uid}, {"created_at": 1}, sort=[("created_at", 1)])
    shared = first_share is not None or first_scan is not None
    return {
        "profile": (photo and bool((user.get("name") or "").strip()), None),
        "card": (photo and bool(user.get("title") or persona.get("title")) and bool(persona.get("bio") or user.get("bio")), None),
        "contact": (first_contact is not None, _iso((first_contact or {}).get("created_at"))),
        "share": (shared, _iso((first_share or {}).get("timestamp") or (first_share or {}).get("created_at") or (first_scan or {}).get("scanned_at"))),
        "memo": (first_memo is not None, _iso((first_memo or {}).get("created_at"))),
    }


async def checklist(db, user: dict) -> dict:
    """Five steps, each true/false from real activity; first-completion stamps persist on users.pilot_checklist."""
    states = await _step_states(db, user)
    stamps = dict(user.get("pilot_checklist") or {})
    new_stamps = {}
    steps = []
    for s in STEPS:
        done, at = states[s["key"]]
        if done and not stamps.get(s["key"]):
            new_stamps[s["key"]] = at or cust.now_iso()
        steps.append({**s, "done": done, "done_at": stamps.get(s["key"]) or new_stamps.get(s["key"])})
    if new_stamps:
        await db.users.update_one({"_id": user["_id"]}, {"$set": {f"pilot_checklist.{k}": v for k, v in new_stamps.items()}})
    n = sum(1 for s in steps if s["done"])
    return {"steps": steps, "done": n, "total": len(STEPS), "complete": n == len(STEPS)}


async def org_users(db, org_id: str) -> list[dict]:
    return await db.users.find({"organization_id": org_id, "status": {"$nin": ["deactivated", "inactive"]}},
                               {"name": 1, "last_login": 1, "pilot_checklist": 1, "photo_url": 1, "photo_path": 1, "persona": 1, "title": 1, "bio": 1}).to_list(500)


async def last_activity(db, user_ids: list[str], users: list[dict]) -> str | None:
    """Most recent sign of life across the org: login, any contact event, any voice memo."""
    candidates = [_iso(u.get("last_login")) for u in users]
    ev = await db.contact_events.find_one({"user_id": {"$in": user_ids}}, {"timestamp": 1}, sort=[("timestamp", -1)])
    if ev:
        candidates.append(_iso(ev.get("timestamp")))
    memo = await db.voice_notes.find_one({"user_id": {"$in": user_ids}}, {"created_at": 1}, sort=[("created_at", -1)])
    if memo:
        candidates.append(_iso(memo.get("created_at")))
    stamps = [c for c in candidates if isinstance(c, str)]
    return max(stamps) if stamps else None


async def issues(db, user_ids: list[str], limit: int = 10) -> tuple[int, list[dict]]:
    open_count = await db.bug_reports.count_documents({"user_id": {"$in": user_ids}, "status": {"$in": OPEN_ISSUE_STATUSES}})
    rows = await db.bug_reports.find({"user_id": {"$in": user_ids}}, {"category": 1, "description": 1, "status": 1, "created_at": 1, "user_name": 1, "screen": 1}).sort("created_at", -1).to_list(limit)
    return open_count, [{"id": str(r["_id"]), "category": r.get("category"), "status": r.get("status"), "created_at": _iso(r.get("created_at")),
                         "user_name": r.get("user_name"), "screen": r.get("screen"), "description": (r.get("description") or "")[:240]} for r in rows]


def attention(c: dict, owner: dict | None, progress: dict | None, last_active: str | None, issues_open: int) -> list[str]:
    """Plain-language reasons this customer needs the founder's attention."""
    now = datetime.now(timezone.utc)
    reasons = []

    def age_days(iso):
        try:
            dt = datetime.fromisoformat(iso) if iso else None
        except (ValueError, TypeError):
            return None
        if not dt:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (now - dt).days

    bs = c.get("billing_status")
    if bs == "past_due":
        reasons.append("Payment failed")
    if bs == "awaiting_payment" and (age_days(c.get("payment_link_sent_at") or c.get("checkout_created_at")) or 0) >= 3:
        reasons.append("Payment link unpaid 3+ days")
    if bs == "exception":
        d = age_days((c.get("billing_exception") or {}).get("expires_at"))
        if d is not None and d >= 0:
            reasons.append("Billing exception expired")
        elif d is not None and d >= -7:
            reasons.append("Billing exception ends within a week")
    if c.get("owner_invited_at") and not c.get("owner_activated_at") and (age_days(c.get("owner_invited_at")) or 0) >= 2:
        reasons.append("Owner has not activated (2+ days)")
    if c.get("activated_at") and not c.get("owner_invited_at") and (age_days(c.get("activated_at")) or 0) >= 2:
        reasons.append("Owner not invited yet")
    if c.get("owner_activated_at") and progress and not progress.get("complete") and (age_days(c.get("owner_activated_at")) or 0) >= 3 and (age_days(last_active) or 99) >= 3:
        reasons.append(f"Setup stalled at {progress.get('done')}/{progress.get('total')}")
    if c.get("owner_activated_at") and (age_days(last_active) or 0) >= 7:
        reasons.append("No activity for a week")
    if issues_open:
        reasons.append(f"{issues_open} open issue{'s' if issues_open != 1 else ''}")
    return reasons


async def founder_view(db, org: dict, owner: dict | None, with_issues: bool = False) -> dict:
    """Progress, activity and issue signals for one customer (used by /customers rows and the detail page)."""
    org_id = str(org["_id"])
    users = await org_users(db, org_id)
    user_ids = [str(u["_id"]) for u in users]
    progress = None
    c = org.get("customer") or {}
    if owner:
        full_owner = await db.users.find_one({"_id": owner["_id"]}) if isinstance(owner.get("_id"), ObjectId) else None
        if full_owner and (c.get("owner_activated_at") or full_owner.get("is_active")):
            progress = await checklist(db, full_owner)
    last_active = await last_activity(db, user_ids, users)
    issues_open, rows = await issues(db, user_ids) if user_ids else (0, [])
    view = {
        "progress": progress and {"done": progress["done"], "total": progress["total"], "complete": progress["complete"],
                                  "steps": {s["key"]: {"done": s["done"], "done_at": s.get("done_at")} for s in progress["steps"]}},
        "last_activity": last_active, "issues_open": issues_open,
        "attention": attention(c, owner, progress, last_active, issues_open),
    }
    if with_issues:
        view["issues"] = rows
    return view
