"""Lead Flows: reusable, store-wide "what happens when a lead comes in" playbooks (CallRevu-style Outbound Flows).

A flow = Steps (ring attempts: who, how, when) + Settings (contact mode, after-hours rule, texting window, caller ID)
+ Automations (intake / after-hours / no-answer texts, tags by outcome, Jessi). A lead source points at a flow via
`lead_sources.flow_id`; the flow's fields are MIRRORED onto the source (`sync_flow_to_sources`) so every existing
intake / ladder / queue code path keeps reading the same keys, and `apply_flow()` re-merges at intake as a safety net.
"""
import logging
import os
from datetime import datetime, timezone

from bson import ObjectId

logger = logging.getLogger(__name__)

COLL = "lead_flows"
MAX_ATTEMPTS = 6
MANAGER_ROLES = {"super_admin", "admin", "org_admin", "store_manager", "manager"}
REP_ROLES = {"user", "salesperson"}

# Keys a flow owns on the lead source while attached
FLOW_FIELDS = [
    "contact_mode", "call_attempts", "workflow_user_ids", "notify_all_on_intake",
    "intake_text", "after_hours_text", "intake_delay_seconds", "no_answer_text",
    "va_enabled", "inquiry_context", "after_hours_mode", "text_window_start", "text_window_end",
    "caller_id_mode", "auto_call_on_claim", "tags_on_claim", "tags_on_no_answer",
    "exhausted_text_lead", "exhausted_push_manager",
]

DEFAULT_FLOW = {
    "name": "New flow",
    "description": "",
    "contact_mode": "text_and_call",
    "call_attempts": [{"user_ids": [], "delay_seconds": 0, "delivery": "call"}],
    "notify_all_on_intake": True,
    "intake_text": "Hi {{first_name}}, thanks for reaching out about {{vehicle}}! Someone from our team is reaching out right now. Is text OK for now?",
    "after_hours_text": "Hi {{first_name}}, thanks for reaching out about {{vehicle}}! We're closed right now but I'll personally follow up first thing in the morning. Anything I can answer by text tonight?",
    "intake_delay_seconds": 0,
    "no_answer_text": "Hi {{first_name}}, we tried to reach you about {{vehicle}} but missed you. What's the best time to call, or would you rather keep texting?",
    "va_enabled": True,
    "inquiry_context": "",
    "after_hours_mode": "text_and_ai",
    "text_window_start": "09:00",
    "text_window_end": "20:00",
    "caller_id_mode": "rep",            # rep = the ringing rep's own business line, store = the source's main line
    "auto_call_on_claim": True,
    "tags_on_claim": ["Working"],
    "tags_on_no_answer": ["Lost Contact"],
    "exhausted_text_lead": True,
    "exhausted_push_manager": True,
}

# Starter flows. `role_hint` per attempt is resolved to the store's reps/managers when the flow is created.
TEMPLATES = [
    {
        "key": "ring_all_then_manager", "name": "Ring everyone, then the manager",
        "description": "Text the lead instantly, ring every rep at once, ring again, then escalate to the managers. Nobody answers: text the lead and alert managers.",
        "contact_mode": "text_and_call",
        "call_attempts": [{"role_hint": "reps", "delay_seconds": 0, "delivery": "call"},
                          {"role_hint": "reps", "delay_seconds": 60, "delivery": "call"},
                          {"role_hint": "managers", "delay_seconds": 90, "delivery": "call"}],
    },
    {
        "key": "text_first_push_only", "name": "Text first, push only",
        "description": "Instant text + Jessi answers. Reps get a push and the first to claim owns it. Nobody's phone rings.",
        "contact_mode": "text_only", "call_attempts": [], "notify_hint": "reps", "tags_on_no_answer": [], "exhausted_text_lead": False,
    },
    {
        "key": "after_hours_jessi", "name": "After-hours: Jessi tonight, ring at opening",
        "description": "Store closed: after-hours text + Jessi handles replies, reps' phones ring first thing at opening (reps twice, then managers).",
        "contact_mode": "text_and_call", "after_hours_mode": "text_and_ai",
        "call_attempts": [{"role_hint": "reps", "delay_seconds": 0, "delivery": "call"},
                          {"role_hint": "reps", "delay_seconds": 60, "delivery": "call"},
                          {"role_hint": "managers", "delay_seconds": 120, "delivery": "push"}],
    },
]


# ---------------------------------------------------------------- scope
def user_store_id(user: dict):
    sid = user.get("store_id") or (user.get("store_ids") or [None])[0]
    return str(sid) if sid else None


def scope_filter(user: dict) -> dict:
    """Which flows a manager can see: their store's. Super/org admins without a store see every store's."""
    sid = user_store_id(user)
    if sid:
        return {"$or": [{"store_id": sid}, {"owner_user_id": str(user["_id"])}]}
    if user.get("role") in ("super_admin", "org_admin"):
        return {}
    return {"owner_user_id": str(user["_id"])}


async def store_reps(db, store_id: str | None, me: dict | None = None) -> list:
    """People who can be on a flow's ladder: the store's members (+ the caller). No store: every active user (admins)."""
    ors: list = []
    if store_id:
        vals = [store_id] + ([ObjectId(store_id)] if ObjectId.is_valid(store_id) else [])
        ors += [{"store_id": {"$in": vals}}, {"store_ids": {"$in": vals}}]
    if me:
        ors.append({"_id": ObjectId(str(me["_id"]))})
    q = {"status": {"$ne": "deactivated"}, "active": {"$ne": False}}
    if ors:
        q["$or"] = ors
    users = await db.users.find(q, {"name": 1, "first_name": 1, "last_name": 1, "email": 1, "role": 1, "phone": 1,
                                    "twilio_number": 1, "mvpline_number": 1, "photo_url": 1}).limit(300).to_list(300)
    rank = {"user": 0, "salesperson": 0, "store_manager": 1, "manager": 1, "org_admin": 2, "admin": 2, "super_admin": 3}
    out = [{"_id": str(u["_id"]), "id": str(u["_id"]),
            "name": u.get("name") or f"{u.get('first_name', '')} {u.get('last_name', '')}".strip() or u.get("email", "Rep"),
            "email": u.get("email", ""), "role": u.get("role", "user"), "phone": u.get("phone", ""),
            "has_number": bool(u.get("twilio_number") or u.get("mvpline_number")), "photo_url": u.get("photo_url")} for u in users]
    out.sort(key=lambda r: (rank.get(r["role"], 1), r["name"].lower()))
    return out


# ---------------------------------------------------------------- normalise / clean
def normalize_flow_attempts(raw: list) -> list:
    """Clamp to MAX_ATTEMPTS, drop attempts with nobody on them, keep delivery (call | push)."""
    out = []
    for a in (raw or [])[:MAX_ATTEMPTS]:
        users = [str(u) for u in (a.get("user_ids") or []) if u]
        if not users:
            continue
        delay = a.get("delay_seconds")
        out.append({"user_ids": users, "delay_seconds": max(0, int(60 if delay is None else delay)),
                    "delivery": a.get("delivery") if a.get("delivery") in ("call", "push") else "call"})
    return out


def clean_flow(body: dict, existing: dict | None = None) -> dict:
    base = {**DEFAULT_FLOW, **{k: v for k, v in (existing or {}).items() if k in DEFAULT_FLOW or k in ("name", "description")}}
    for k in list(DEFAULT_FLOW.keys()):
        if k in body and body[k] is not None:
            base[k] = body[k]
    base["call_attempts"] = normalize_flow_attempts(base.get("call_attempts"))
    notify = body["workflow_user_ids"] if body.get("workflow_user_ids") is not None else (existing or {}).get("workflow_user_ids") or []
    base["workflow_user_ids"] = sorted({u for a in base["call_attempts"] for u in a["user_ids"]} | {str(u) for u in notify if u})
    for k in ("tags_on_claim", "tags_on_no_answer"):
        base[k] = [str(t).strip() for t in (base.get(k) or []) if str(t).strip()][:10]
    if base.get("contact_mode") not in ("text_only", "text_and_call"):
        base["contact_mode"] = "text_and_call"
    if base.get("after_hours_mode") not in ("text_and_ai", "ring_anyway"):
        base["after_hours_mode"] = "text_and_ai"
    if base.get("caller_id_mode") not in ("rep", "store"):
        base["caller_id_mode"] = "rep"
    for k in ("intake_text", "after_hours_text", "no_answer_text"):
        base[k] = (base.get(k) or "").strip()[:600]
    base["inquiry_context"] = (base.get("inquiry_context") or "").strip()[:300]
    base["intake_delay_seconds"] = max(0, min(3600, int(base.get("intake_delay_seconds") or 0)))
    for k in ("notify_all_on_intake", "va_enabled", "auto_call_on_claim", "exhausted_text_lead", "exhausted_push_manager"):
        base[k] = bool(base.get(k))
    base["name"] = (base.get("name") or "New flow").strip()[:80]
    base["description"] = (base.get("description") or "").strip()[:300]
    return base


async def flow_from_template(db, key: str, store_id: str | None, me: dict | None = None) -> dict:
    """Template -> concrete flow body with the store's reps/managers filled into each attempt."""
    tpl = next((t for t in TEMPLATES if t["key"] == key), None)
    if not tpl:
        return {}
    reps = await store_reps(db, store_id, me)
    by_hint = {
        "reps": [r["_id"] for r in reps if r["role"] in REP_ROLES] or [r["_id"] for r in reps if r["role"] != "super_admin"],
        "managers": [r["_id"] for r in reps if r["role"] in MANAGER_ROLES and r["role"] != "super_admin"] or [r["_id"] for r in reps if r["role"] in MANAGER_ROLES],
    }
    body = {k: v for k, v in tpl.items() if k not in ("key", "call_attempts", "notify_hint")}
    body["call_attempts"] = [{"user_ids": by_hint.get(a.get("role_hint"), []), "delay_seconds": a.get("delay_seconds", 60), "delivery": a.get("delivery", "call")}
                             for a in tpl.get("call_attempts", [])]
    if tpl.get("notify_hint"):
        body["workflow_user_ids"] = by_hint.get(tpl["notify_hint"], [])
    body["template_key"] = key
    return body


# ---------------------------------------------------------------- attach / mirror
def flow_fields(flow: dict) -> dict:
    return {k: flow.get(k, DEFAULT_FLOW.get(k)) for k in FLOW_FIELDS}


async def sync_flow_to_sources(db, flow: dict) -> int:
    """Mirror the flow onto every source that uses it (flow wins entirely)."""
    res = await db.lead_sources.update_many(
        {"flow_id": str(flow["_id"])},
        {"$set": {**flow_fields(flow), "flow_name": flow.get("name"), "updated_at": datetime.now(timezone.utc)}})
    return res.modified_count


async def attach_flow(db, source_id: str, flow: dict | None) -> dict:
    """Point a source at a flow (copying its fields), or detach (source keeps the last copy so nothing breaks)."""
    if flow:
        update = {"$set": {**flow_fields(flow), "flow_id": str(flow["_id"]), "flow_name": flow.get("name"), "updated_at": datetime.now(timezone.utc)}}
    else:
        update = {"$set": {"updated_at": datetime.now(timezone.utc)}, "$unset": {"flow_id": "", "flow_name": ""}}
    await db.lead_sources.update_one({"_id": ObjectId(source_id)}, update)
    return await db.lead_sources.find_one({"_id": ObjectId(source_id)}) or {}


async def apply_flow(db, source: dict | None) -> dict:
    """Merge the attached flow over a lead source doc (flow wins). Safe on None / sources without a flow."""
    if not source:
        return source or {}
    fid = source.get("flow_id")
    if not fid or not ObjectId.is_valid(str(fid)):
        return source
    flow = await db[COLL].find_one({"_id": ObjectId(str(fid))})
    if not flow:
        return source
    merged = {**source, **flow_fields(flow), "flow_name": flow.get("name"), "flow_id": str(flow["_id"])}
    return merged


# ---------------------------------------------------------------- read models
def _iso(v):
    return v.isoformat() if isinstance(v, datetime) else v


def summarize(flow: dict, names: dict | None = None) -> list:
    """Plain-English steps for the flow card / source page."""
    names = names or {}
    rows = []
    mode = flow.get("contact_mode")
    if flow.get("intake_text"):
        rows.append({"icon": "chatbubble", "text": "Instant text to the lead" + (" (after-hours version when the store is closed)" if flow.get("after_hours_text") else "")})
    if flow.get("va_enabled"):
        rows.append({"icon": "sparkles", "text": "Jessi answers replies until a rep claims"})
    if mode == "text_and_call":
        for i, a in enumerate(flow.get("call_attempts") or []):
            who = [names.get(u, "Rep") for u in a.get("user_ids") or []]
            who_txt = ", ".join(who[:3]) + (f" +{len(who) - 3}" if len(who) > 3 else "")
            when = "right away" if i == 0 and not a.get("delay_seconds") else f"{a.get('delay_seconds', 0)}s later"
            verb = "Push" if a.get("delivery") == "push" else "Ring"
            rows.append({"icon": "notifications" if a.get("delivery") == "push" else "call", "text": f"Attempt {i + 1} ({when}): {verb} {who_txt or 'nobody yet'}" + (" at once" if len(who) > 1 and verb == "Ring" else "")})
        bits = []
        if flow.get("exhausted_text_lead") and flow.get("no_answer_text"):
            bits.append("text the lead")
        if flow.get("tags_on_no_answer"):
            bits.append("tag " + ", ".join(flow["tags_on_no_answer"]))
        if flow.get("exhausted_push_manager"):
            bits.append("alert managers")
        if flow.get("call_attempts"):
            rows.append({"icon": "alert-circle", "text": "Nobody answers: " + (", ".join(bits) if bits else "nothing else") + "; the lead stays in the queue"})
        if flow.get("after_hours_mode") == "text_and_ai":
            rows.append({"icon": "moon", "text": "Store closed: text + Jessi now, phones ring at opening"})
        else:
            rows.append({"icon": "moon", "text": "Store closed: ring anyway"})
    else:
        rows.append({"icon": "notifications", "text": "Text only: reps get a push, first to claim owns it"})
    if flow.get("tags_on_claim"):
        rows.append({"icon": "pricetag", "text": "On claim: tag " + ", ".join(flow["tags_on_claim"]) + (" and ring the rep to connect" if flow.get("auto_call_on_claim") else "")})
    return rows


def serialize(flow: dict, sources: list | None = None, names: dict | None = None) -> dict:
    out = {k: flow.get(k, DEFAULT_FLOW.get(k)) for k in DEFAULT_FLOW}
    out.update({
        "id": str(flow["_id"]), "store_id": flow.get("store_id"), "owner_user_id": flow.get("owner_user_id"),
        "template_key": flow.get("template_key"), "workflow_user_ids": flow.get("workflow_user_ids") or [],
        "sources": [{"id": str(s["_id"]), "name": s.get("name")} for s in (sources or [])], "source_count": len(sources or []),
        "summary": summarize(flow, names),
        "created_at": _iso(flow.get("created_at")), "updated_at": _iso(flow.get("updated_at")), "updated_by_name": flow.get("updated_by_name"),
    })
    return out


# ---------------------------------------------------------------- automations
async def on_lead_claimed(db, conversation_id: str, user_id: str):
    """Runs when a rep claims a flow-managed lead: tags_on_claim (+ tag workflows)."""
    try:
        conv = await db.conversations.find_one({"_id": ObjectId(conversation_id)}, {"contact_id": 1, "lead_source_id": 1})
        if not conv or not conv.get("contact_id") or not ObjectId.is_valid(str(conv.get("lead_source_id") or "")):
            return
        src = await apply_flow(db, await db.lead_sources.find_one({"_id": ObjectId(str(conv["lead_source_id"]))}))
        if not src.get("flow_id"):
            return
        tags = src.get("tags_on_claim") or []
        if tags and ObjectId.is_valid(str(conv["contact_id"])):
            await db.contacts.update_one({"_id": ObjectId(str(conv["contact_id"]))}, {"$addToSet": {"tags": {"$each": tags}}})
            from services.tag_workflows import apply_tag_workflows
            await apply_tag_workflows(user_id, str(conv["contact_id"]), tags, source="lead-flow-claim")
            logger.info(f"[LeadFlows] claim tags {tags} -> contact {conv['contact_id']} ({src.get('flow_name')})")
    except Exception as e:
        logger.warning(f"[LeadFlows] on_lead_claimed skipped: {e}")


async def on_ladder_exhausted(db, job: dict, source: dict) -> list:
    """Nobody claimed after the last attempt: no-answer text, tags, manager alert. Lead stays in the queue."""
    actions = []
    try:
        from routers.lead_sources import hydrate_intake_text
        lead = job.get("lead") or {}
        contact_id = str(job.get("contact_id") or "")
        contact = (await db.contacts.find_one({"_id": ObjectId(contact_id)}) if ObjectId.is_valid(contact_id) else None) or {}
        rep_ids = [u for a in job.get("attempts", []) for u in a.get("user_ids", [])]
        conv_id = job.get("conversation_id")
        if source.get("exhausted_text_lead") and (source.get("no_answer_text") or "").strip() and job.get("customer_phone"):
            already = await db.messages.find_one({"conversation_id": conv_id, "is_no_answer_text": True}, {"_id": 1})
            from_phone = None
            for uid in rep_ids:
                if not ObjectId.is_valid(uid):
                    continue
                rep = await db.users.find_one({"_id": ObjectId(uid)}, {"twilio_number": 1, "mvpline_number": 1})
                from_phone = (rep or {}).get("twilio_number") or (rep or {}).get("mvpline_number")
                if from_phone:
                    break
            from_phone = source.get("phone_number") if source.get("caller_id_mode") == "store" and source.get("phone_number") else (from_phone or source.get("phone_number"))
            conv = await db.conversations.find_one({"_id": ObjectId(conv_id)}, {"rep_phone": 1}) if ObjectId.is_valid(str(conv_id)) else None
            # Same line the intake text went out on, so the reply lands in the same thread
            from_phone = (conv or {}).get("rep_phone") or from_phone or os.environ.get("TWILIO_PHONE_NUMBER", "")
            lead_data = {"first_name": (lead.get("name") or "").split(" ")[0] or contact.get("first_name", ""),
                         "vehicle_interest": lead.get("interest") or contact.get("vehicle_interest") or "", "phone": job.get("customer_phone", "")}
            body = hydrate_intake_text(source["no_answer_text"], lead_data, source.get("name") or "")
            if from_phone and body and not already:
                from services.twilio_service import send_sms
                res = await send_sms(job["customer_phone"], body, from_phone=from_phone)
                actions.append(f"no-answer text {'sent' if res.get('success') else 'failed'}")
                if res.get("success"):
                    now = datetime.now(timezone.utc)
                    await db.messages.insert_one({"conversation_id": conv_id, "content": body, "sender": "ai", "direction": "outbound", "channel": "sms",
                                                  "ai_generated": True, "is_no_answer_text": True, "mocked": bool(res.get("mock")), "timestamp": now})
                    await db.conversations.update_one({"_id": ObjectId(conv_id)}, {"$set": {"last_message_at": now}})
        tags = source.get("tags_on_no_answer") or []
        if tags and contact:
            await db.contacts.update_one({"_id": contact["_id"]}, {"$addToSet": {"tags": {"$each": tags}}})
            actions.append("tagged " + ", ".join(tags))
        if source.get("exhausted_push_manager"):
            from routers.push_notifications import send_push_to_user
            q: dict = {"role": {"$in": ["store_manager", "org_admin", "manager", "admin"]}, "status": {"$ne": "deactivated"}, "active": {"$ne": False}}
            sid = str(source.get("store_id") or "")
            if sid:
                q["$or"] = [{"store_id": {"$in": [sid] + ([ObjectId(sid)] if ObjectId.is_valid(sid) else [])}}, {"store_ids": sid}]
            managers = [str(u["_id"]) async for u in db.users.find(q, {"_id": 1}).limit(10)]
            for mid in managers:
                await send_push_to_user(mid, f"Unclaimed lead: {lead.get('name') or 'New lead'}",
                                        f"{len(job.get('attempts', []))} attempts, nobody picked up ({source.get('name', 'Lead')}). Tap to assign.",
                                        f"/thread/{conv_id}", "exclamationmark.triangle")
                await db.notifications.insert_one({"user_id": mid, "type": "slow_lead", "priority": "urgent", "title": f"Unclaimed lead: {lead.get('name') or 'New lead'}",
                                                   "message": f"Nobody picked up after {len(job.get('attempts', []))} attempts ({source.get('name', 'Lead')}).",
                                                   "conversation_id": conv_id, "contact_id": contact_id or None, "read": False, "dismissed": False,
                                                   "created_at": datetime.now(timezone.utc)})
            if managers:
                actions.append(f"alerted {len(managers)} manager(s)")
        if actions and contact_id:
            from utils.activity_log import log_activity
            await log_activity(db, user_id=rep_ids[0] if rep_ids else "", contact_id=contact_id, event_type="lead_flow",
                               description="Nobody answered: " + "; ".join(actions), metadata={"job_id": str(job.get("_id")), "flow": source.get("flow_name")})
        logger.info(f"[LeadFlows] exhausted actions for job {job.get('_id')}: {actions}")
    except Exception as e:
        logger.warning(f"[LeadFlows] on_ladder_exhausted failed: {e}")
    return actions
