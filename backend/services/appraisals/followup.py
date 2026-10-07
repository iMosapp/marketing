"""Follow-up bridge (MVP5): appraisal events → the EXISTING campaign engine (trigger_events on a campaign), {trade_*} merge values with the
org-level money gate, appraisal context for Jessi-written campaign touches, and tasks through the existing task system. No second campaign system."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId

from services.appraisals import rules as rulesvc
from services.appraisals.core import A, V, _now, _oid, vehicle_label
from utils.activity_log import log_activity

logger = logging.getLogger(__name__)

TRIGGER_EVENTS = {
    "trade_appraisal.submitted": "Trade appraisal submitted to the desk",
    "trade_appraisal.approved": "Trade value approved (as suggested or changed)",
    "trade_appraisal.accepted": "Customer accepted the trade value",
    "trade_appraisal.wants_more": "Customer wants more",
    "trade_appraisal.thinking": "Customer is thinking about it",
    "trade_appraisal.not_trading": "Customer is not trading",
    "trade_appraisal.closed": "Trade appraisal closed (any outcome)",
    "trade_appraisal.reappraised": "Vehicle reappraised",
}
MONEY_FIELDS = ("trade_market_value", "trade_suggested_acv", "trade_approved_value", "trade_customer_wants", "trade_gap")
TEXT_FIELDS = ("trade_vehicle", "trade_year", "trade_make", "trade_model", "trade_trim", "trade_mileage", "trade_appraisal_date", "trade_condition", "trade_outcome", "trade_salesperson", "trade_manager")
MERGE_FIELDS = list(TEXT_FIELDS) + list(MONEY_FIELDS)
MERGE_FIELD_HELP = {"trade_vehicle": "2022 Ford F-150 Lariat", "trade_year": "2022", "trade_make": "Ford", "trade_model": "F-150", "trade_trim": "Lariat", "trade_mileage": "47,821",
                    "trade_appraisal_date": "Oct 07, 2026", "trade_condition": "Good", "trade_outcome": "Thinking about it", "trade_salesperson": "Kira", "trade_manager": "Dave",
                    "trade_market_value": "$34,850 (org setting)", "trade_suggested_acv": "$29,600 (org setting)", "trade_approved_value": "$30,000 (org setting)",
                    "trade_customer_wants": "$32,000 (org setting)", "trade_gap": "$2,000 (org setting)"}


def _money(v) -> str:
    return f"${int(v):,}" if v is not None else ""


async def org_allows_trade_values(db, org_id: Optional[str]) -> bool:
    """Organization setting allow_trade_values_in_automated_messages. Default OFF: no dollar amounts in automated SMS/email, ever, unless the org says so."""
    if not org_id:
        return False
    q = {"$or": [{"_id": org_id}] + ([{"_id": ObjectId(org_id)}] if ObjectId.is_valid(str(org_id)) else [])}
    org = await db.organizations.find_one(q, {"allow_trade_values_in_automated_messages": 1})
    return bool((org or {}).get("allow_trade_values_in_automated_messages"))


def merge_values(summary: Optional[dict], vehicle: Optional[dict], allow_money: bool, manager: Optional[str] = None) -> dict:
    """All {trade_*} values for one contact. Money fields are empty strings unless the organization allows them."""
    s = summary or {}
    v = vehicle or {}
    d = s.get("appraised_at")
    date = d.strftime("%b %d, %Y") if isinstance(d, datetime) else ""
    out = {"trade_vehicle": s.get("vehicle_label") or (vehicle_label(v) if v else "") or "", "trade_year": str(v.get("year") or ""), "trade_make": v.get("make") or "", "trade_model": v.get("model") or "",
           "trade_trim": v.get("trim") or "", "trade_mileage": f"{s['mileage']:,}" if s.get("mileage") is not None else "", "trade_appraisal_date": date,
           "trade_condition": s.get("condition_label") or "", "trade_outcome": s.get("outcome_label") or "", "trade_salesperson": s.get("salesperson") or "", "trade_manager": manager or s.get("approved_by_name") or ""}
    money = {"trade_market_value": _money(s.get("market_retail")), "trade_suggested_acv": _money(s.get("suggested_acv")), "trade_approved_value": _money(s.get("approved_value")),
             "trade_customer_wants": _money(s.get("customer_expected_value")), "trade_gap": _money(abs(s["expectation_gap"])) if s.get("expectation_gap") else ""}
    out.update(money if allow_money else {k: "" for k in money})
    return out


async def merge_values_for_contact(db, contact: dict, user_id: Optional[str] = None) -> dict:
    """Used by the one template renderer (scheduler.resolve_template_variables). Reads the normalized contact.trade_appraisal only."""
    s = (contact or {}).get("trade_appraisal")
    if not s:
        full = await db.contacts.find_one({"_id": contact["_id"]}, {"trade_appraisal": 1}) if contact.get("_id") else None
        s = (full or {}).get("trade_appraisal")
    if not s:
        return {k: "" for k in MERGE_FIELDS}
    veh = await db[V].find_one({"_id": _oid(s.get("vehicle_id"))}, {"year": 1, "make": 1, "model": 1, "trim": 1}) if _oid(s.get("vehicle_id")) else None
    org = None
    if user_id and ObjectId.is_valid(str(user_id)):
        u = await db.users.find_one({"_id": ObjectId(user_id)}, {"organization_id": 1, "store_id": 1})
        org = (u or {}).get("organization_id")
        if not org and (u or {}).get("store_id") and ObjectId.is_valid(str(u["store_id"])):
            st = await db.stores.find_one({"_id": ObjectId(u["store_id"])}, {"organization_id": 1})
            org = (st or {}).get("organization_id")
    return merge_values(s, veh, await org_allows_trade_values(db, str(org) if org else None))


def apply_merge_fields(message: str, values: dict) -> str:
    for k, v in values.items():
        message = message.replace("{" + k + "}", v or "")
    return message


async def ai_context(db, contact: dict, user_id: Optional[str]) -> str:
    """Concise appraisal block for Jessi-written campaign touches. Money only when the org allows it; otherwise Jessi is told not to quote numbers."""
    s = (contact or {}).get("trade_appraisal")
    if not s:
        return ""
    vals = await merge_values_for_contact(db, contact, user_id)
    allow = bool(vals.get("trade_approved_value") or vals.get("trade_customer_wants") or vals.get("trade_market_value"))
    lines = ["TRADE APPRAISAL (most recent):",
             f"  {vals['trade_vehicle']}" + (f", {vals['trade_mileage']} mi" if vals["trade_mileage"] else "") + (f", appraised {vals['trade_appraisal_date']}" if vals["trade_appraisal_date"] else "") + (f" by {vals['trade_salesperson']}" if vals["trade_salesperson"] else ""),
             f"  Condition: {vals['trade_condition'] or 'not graded'} · Status: {s.get('status_label') or ''}" + (f" · Outcome: {vals['trade_outcome']}" if vals["trade_outcome"] else "")]
    if allow:
        lines.append(f"  Numbers (org allows them in messages): dealer approved {vals['trade_approved_value'] or 'n/a'}, customer wanted {vals['trade_customer_wants'] or 'n/a'}" + (f", gap {vals['trade_gap']}" if vals["trade_gap"] else ""))
    else:
        lines.append("  RULE: this dealership does NOT allow dollar amounts in automated messages. Never quote the offer, the customer's number or any value. Talk about the vehicle and whether they are still thinking about a change.")
    return "\n".join(lines)


# ---------- campaign triggers ----------
def _rank(c: dict) -> int:
    return 0 if c.get("scope") == "org" else 1 if (c.get("scope") == "account" or c.get("ownership_level") == "store") else 2


async def fire_campaign_triggers(db, appr: dict, event: str) -> list:
    """Enroll the contact in every ACTIVE campaign visible to the appraisal's rep whose trigger_events include this event. Store/org copies win over a
    same-named personal copy. Nothing happens unless a dealership created/enabled such a campaign."""
    if event not in TRIGGER_EVENTS or not _oid(appr.get("contact_id")) or not ObjectId.is_valid(str(appr.get("user_id") or "")):
        return []
    from services.tag_workflows import visible_campaigns, enroll_contact
    user = await db.users.find_one({"_id": ObjectId(appr["user_id"])})
    contact = await db.contacts.find_one({"_id": ObjectId(appr["contact_id"])})
    if not user or not contact:
        return []
    camps = [c for c in await visible_campaigns(db, user) if event in (c.get("trigger_events") or [])]
    best: dict = {}
    for c in camps:
        key = (c.get("name"), c.get("type"))
        if key not in best or _rank(c) < _rank(best[key]):
            best[key] = c
    enrolled = []
    for c in best.values():
        try:
            if await enroll_contact(db, appr["user_id"], c, contact, trigger_type=event, ai_mode=None):
                enrolled.append({"campaign_id": str(c["_id"]), "name": c.get("name")})
        except Exception as e:
            logger.warning(f"[Appraisal] campaign enrollment failed for {c.get('name')}: {e}")
    if enrolled:
        await log_activity(db, user_id=appr["user_id"], contact_id=appr["contact_id"], event_type="campaign_enrolled",
                           description=f"Enrolled in {', '.join(e['name'] for e in enrolled)} (trade appraisal: {TRIGGER_EVENTS[event]})",
                           metadata={"appraisal_id": str(appr["_id"]), "event": event, "campaigns": enrolled})
    return enrolled


# ---------- tasks (existing task system) ----------
async def create_task(db, user_id: str, appr: dict, title: str, description: str, due_days: int, kind: str, priority: str = "medium") -> Optional[str]:
    """One task per (appraisal, kind): links to the contact, the vehicle and the appraisal."""
    if not ObjectId.is_valid(str(user_id)):
        return None
    if await db.tasks.find_one({"appraisal_id": str(appr["_id"]), "task_kind": kind, "status": {"$ne": "cancelled"}}, {"_id": 1}):
        return None
    c = await db.contacts.find_one({"_id": _oid(appr.get("contact_id"))}, {"first_name": 1, "last_name": 1, "name": 1, "phone": 1}) if _oid(appr.get("contact_id")) else None
    now = _now()
    doc = {"user_id": str(user_id), "contact_id": appr.get("contact_id"), "contact_name": appr.get("contact_name") or "", "contact_phone": (c or {}).get("phone", ""),
           "type": "follow_up", "task_kind": kind, "source": "trade_appraisal", "auto_kind": "trade_appraisal", "title": title[:140], "description": description[:500],
           "suggested_message": "", "action_type": "call", "priority": priority, "priority_order": 1 if priority == "high" else 2, "status": "pending", "completed": False,
           "due_date": now + timedelta(days=max(0, due_days)), "has_time": False, "appointment_type": "task", "reminded_15": False, "reminded_due": False, "completed_at": None,
           "snoozed_until": None, "campaign_id": None, "campaign_name": None, "pending_send_id": None, "channel": "", "appraisal_id": str(appr["_id"]), "vehicle_id": appr.get("vehicle_id"),
           "link": f"/appraisal/{appr['_id']}", "vehicle_link": f"/vehicle/{appr['vehicle_id']}" if appr.get("vehicle_id") else None, "created_at": now}
    res = await db.tasks.insert_one(doc)
    await log_activity(db, user_id=str(user_id), contact_id=appr.get("contact_id"), event_type="task_created", description=f"Task: {title[:120]}",
                       metadata={"task_id": str(res.inserted_id), "appraisal_id": str(appr["_id"]), "kind": kind})
    return str(res.inserted_id)


def _fill(t: str, appr: dict) -> str:
    first = (appr.get("contact_name") or "the customer").split(" ")[0]
    gap = (appr.get("customer_expected_value") or 0) - (appr.get("approved_value") or appr.get("suggested_acv") or 0)
    return t.replace("{first_name}", first).replace("{vehicle}", vehicle_label(appr.get("vehicle") or {}) or "their vehicle").replace("{gap}", _money(abs(gap)) if gap else "the")


async def tasks_for_event(db, appr: dict, event: str) -> list:
    """Dealership rules → tasks: wants_more / thinking (rep follow-up), approved-with-change (rep reviews the new value)."""
    spec = {"wants_more": ("wants_more", "high"), "thinking": ("thinking", "medium"), "approved": ("manager_changed", "medium")}.get(event)
    if not spec:
        return []
    key, prio = spec
    if key == "manager_changed" and not (appr.get("manager_adjustment") or {}).get("delta"):
        return []
    eff = await rulesvc.effective(db, appr.get("organization_id"), appr.get("store_id"))
    rule = (((eff["rules"].get("follow_up") or {}).get("tasks") or {}).get(key) or {})
    if not rule.get("enabled"):
        return []
    title = _fill(rule.get("title") or "", appr) or f"Follow up with {appr.get('contact_name')}"
    desc = _fill(rule.get("description") or "", appr)
    tid = await create_task(db, appr["user_id"], appr, title, desc, int(rule.get("days") or 0), key, prio)
    return [tid] if tid else []


async def on_event(db, appr: dict, event: str) -> dict:
    """Called by workflow.emit for every trade_appraisal.* event: campaign triggers through the existing engine, dealership tasks, then contact tags."""
    full = f"trade_appraisal.{event}"
    camps = await fire_campaign_triggers(db, appr, full) if full in TRIGGER_EVENTS else []
    tasks = await tasks_for_event(db, appr, event)
    tags = await apply_trade_tags(db, appr, event)
    return {"campaigns": camps, "tasks": tasks, "tags": tags}


# ---------- contact tags (grouping + tag-triggered campaigns) ----------
OUTCOME_TAGS = {"accepted": "trade-accepted", "wants_more": "trade-wants-more", "thinking": "trade-thinking", "not_trading": "trade-not-trading"}
GAP_TAGS = ("trade-gap-none", "trade-gap-under-1k", "trade-gap-1k-3k", "trade-gap-3k-plus")
TRADE_TAGS = ["trade-appraised", *OUTCOME_TAGS.values(), *GAP_TAGS]
TRADE_TAG_HELP = {"trade-appraised": "Any customer whose trade reached the desk", "trade-accepted": "Took the number", "trade-wants-more": "Wanted more than the offer",
                  "trade-thinking": "Left to think about it", "trade-not-trading": "Decided not to trade", "trade-gap-none": "Offer met or beat what they wanted",
                  "trade-gap-under-1k": "Wanted under $1,000 more", "trade-gap-1k-3k": "Wanted $1,000 to $3,000 more", "trade-gap-3k-plus": "Wanted $3,000+ more"}


def gap_tag(appr: dict) -> Optional[str]:
    wants, offer = appr.get("customer_expected_value"), appr.get("approved_value") or appr.get("suggested_acv")
    if not wants or not offer:
        return None
    gap = int(wants) - int(offer)
    return "trade-gap-none" if gap <= 0 else "trade-gap-under-1k" if gap < 1000 else "trade-gap-1k-3k" if gap < 3000 else "trade-gap-3k-plus"


async def apply_trade_tags(db, appr: dict, event: str) -> list:
    """Submitted → trade-appraised (always). An outcome → the dealership's outcome tag (+ a gap bucket when gap_tags is on), REPLACING earlier trade
    outcome/gap tags so the contact carries one current trade state. New tags run through the existing tag workflow so tag-triggered campaigns fire."""
    if not appr.get("contact_id"):
        return []
    add = []
    if event == "submitted":
        add.append("trade-appraised")
    elif event in OUTCOME_TAGS:
        fu = (await rulesvc.effective(db, appr.get("organization_id"), appr.get("store_id")))["rules"].get("follow_up") or {}
        if not fu.get("tag_on_outcome", True):
            return []
        t = ((fu.get("tags") or {}).get(event) or OUTCOME_TAGS[event]).strip().lower()
        if t:
            add.append(t)
        g = gap_tag(appr) if fu.get("gap_tags", True) else None
        if g:
            add.append(g)
    if not add:
        return []
    cid = _oid(appr["contact_id"])
    c = await db.contacts.find_one({"_id": cid}, {"tags": 1})
    if not c:
        return []
    before = [t for t in (c.get("tags") or []) if isinstance(t, str)]
    stale_set = set(OUTCOME_TAGS.values()) | set(GAP_TAGS) | {str(v).strip().lower() for v in ((fu.get("tags") or {}).values() if event in OUTCOME_TAGS else []) if v}
    stale = [t for t in before if t.lower() in stale_set and t.lower() not in add] if event in OUTCOME_TAGS else []
    kept = [t for t in before if t not in stale]
    new = [t for t in add if t not in [k.lower() for k in kept]]
    if not stale and not new:
        return []
    await db.contacts.update_one({"_id": cid}, {"$set": {"tags": kept + new, "updated_at": _now()}})
    if new:
        try:
            from services.tag_workflows import apply_tag_workflows
            await apply_tag_workflows(appr["user_id"], appr["contact_id"], new, source="trade_appraisal")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[Appraisal] tag workflows failed: {e}")
    return new


async def reappraisal_tasks(db) -> int:
    """Daily: for every stale vehicle (REAPPRAISE_DAYS+) still owned, one 'Reappraise …' task for the rep who appraised it last, at most once per period.
    Reads stored history only; never calls a market provider."""
    from services.appraisals.relationship import REAPPRAISE_DAYS
    cutoff = _now() - timedelta(days=REAPPRAISE_DAYS)
    n = 0
    async for v in db[V].find({"deleted": {"$ne": True}, "ownership_status": {"$in": [None, "owns", "unknown"]}, "last_appraisal.status": "closed", "last_appraisal.closed_at": {"$lte": cutoff},
                               "$or": [{"reappraisal_task_at": None}, {"reappraisal_task_at": {"$lte": cutoff}}]}).limit(500):
        la = v.get("last_appraisal") or {}
        appr = await db[A].find_one({"_id": _oid(la.get("appraisal_id"))}) if _oid(la.get("appraisal_id")) else None
        if not appr or appr.get("status") != "closed":
            continue
        if await db[A].count_documents({"vehicle_id": str(v["_id"]), "deleted": {"$ne": True}, "status": {"$nin": ["closed"]}}) > 0:
            continue
        eff = await rulesvc.effective(db, appr.get("organization_id"), appr.get("store_id"))
        rule = (((eff["rules"].get("follow_up") or {}).get("tasks") or {}).get("reappraisal") or {})
        if not rule.get("enabled"):
            continue
        d = int((_now() - (la["closed_at"] if la["closed_at"].tzinfo else la["closed_at"].replace(tzinfo=timezone.utc))).total_seconds() // 86400)
        title = _fill(rule.get("title") or "Reappraise {vehicle}", appr)
        desc = _fill(rule.get("description") or "", appr) or (f"Appraised {d} days ago" + (f" · {la.get('outcome_label')}" if la.get("outcome_label") else "") + ". Fresh mileage and a new market pull when the customer is ready.")
        tid = await create_task(db, appr["user_id"], appr, title, desc, 0, f"reappraisal_{_now().strftime('%Y%m')}", "medium")
        await db[V].update_one({"_id": v["_id"]}, {"$set": {"reappraisal_task_at": _now()}})
        if tid:
            n += 1
    return n
