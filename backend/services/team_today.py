"""Team today: a store manager's morning digest. Every rep on the team, and who each of them should be working today
(replies waiting, overdue touchpoints, their three for today, hot opportunities), built from the same agenda a rep hears
in Walk My Day. Spoken by Jessi, shown on /team-today, and a manager can nudge a rep about a specific person."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

from services import day_agenda

logger = logging.getLogger(__name__)

MANAGER_ROLES = ("store_manager", "manager", "org_admin", "admin", "super_admin")
KIND_LABEL = {"reply": "replied, waiting on a response", "hot": "hot opportunity", "task": "overdue touchpoint", "my3": "one of their three today"}
PER_REP_SCREEN = 8


def is_manager(user: dict) -> bool:
    return (user.get("role") or "") in MANAGER_ROLES


def _first(u: dict) -> str:
    return (u.get("name") or "").split(" ")[0] or "them"


async def reps_for(db, manager: dict) -> list:
    """The salespeople this manager oversees: the same store team Ask-the-Team uses, minus the manager, super admins and org-only admins. Capped at 25."""
    from services.lead_flows import store_reps, user_store_id
    me = str(manager["_id"])
    rows = await store_reps(db, user_store_id(manager), manager)
    out = []
    for p in rows:
        if p["_id"] == me or p.get("role") == "super_admin" or (p.get("via") and p.get("via") == ["org"]):
            continue
        out.append({"user_id": p["_id"], "name": p["name"], "first": p["name"].split(" ")[0], "role": p.get("role") or "user", "photo": p.get("photo") or p.get("photo_url")})
    out.sort(key=lambda p: (0 if p["role"] in ("user", "salesperson") else 1, p["name"].lower()))
    return out[:25]


async def _agenda(db, rep: dict) -> list:
    try:
        return await day_agenda.build(db, rep["user_id"])
    except Exception as e:
        logger.warning(f"[TeamToday] agenda for {rep['user_id']} failed: {e}")
        return []


async def build(db, manager: dict) -> dict:
    reps = await reps_for(db, manager)
    agendas = await asyncio.gather(*(_agenda(db, r) for r in reps))
    rows = []
    for rep, stops in zip(reps, agendas):
        seen, uniq = set(), []
        for s in stops:  # one line per customer, the most urgent reason wins
            key = s.get("contact_id") or s.get("key")
            if key in seen:
                continue
            seen.add(key)
            uniq.append(s)
        stops = uniq
        counts = {}
        for s in stops:
            counts[s["kind"]] = counts.get(s["kind"], 0) + 1
        rows.append({**rep, "total": len(stops), "counts": counts, "foreign": sum(1 for s in stops if s.get("foreign")),
                     "stops": [{"contact_id": s.get("contact_id"), "name": s.get("name"), "first": s.get("first"), "kind": s.get("kind"), "label": KIND_LABEL.get(s.get("kind"), s.get("kind")),
                                "why": s.get("why") or "", "conversation_id": s.get("conversation_id"), "task_id": s.get("task_id"),
                                "foreign": bool(s.get("foreign")), "owner_user_id": s.get("owner_user_id") or ""} for s in stops[:PER_REP_SCREEN]]})
    rows.sort(key=lambda r: (-r["counts"].get("reply", 0), -r["total"], r["name"].lower()))
    owner_ids = {s["owner_user_id"] for r in rows for s in r["stops"] if s["foreign"] and ObjectId.is_valid(s["owner_user_id"])}
    owners = {str(u["_id"]): (u.get("name") or "").split(" ")[0] or "another rep" for u in await db.users.find({"_id": {"$in": [ObjectId(x) for x in owner_ids]}}, {"name": 1}).to_list(len(owner_ids))} if owner_ids else {}
    for r in rows:
        for s in r["stops"]:
            s["owner_name"] = owners.get(s["owner_user_id"], "") if s["foreign"] else ""
    return {"reps": rows, "rep_count": len(rows), "total": sum(r["total"] for r in rows),
            "waiting": sum(r["counts"].get("reply", 0) for r in rows), "foreign": sum(r["foreign"] for r in rows), "generated_at": datetime.now(timezone.utc).isoformat()}


def _why(stop: dict) -> str:
    w = (stop.get("why") or "").strip().rstrip(".")
    return w or stop.get("label") or ""


def spoken(digest: dict, rep_first: str = "") -> str:
    """The morning digest out loud: who on the team has work waiting and the first couple of names each, or one rep's full list."""
    reps = digest.get("reps") or []
    if not reps:
        return "I do not see any salespeople on your team yet. Once reps are assigned to your store I will walk you through their day every morning."
    if rep_first:
        want = rep_first.strip().lower()
        rep = next((r for r in reps if r["first"].lower() == want or r["name"].lower() == want), None) or next((r for r in reps if want in r["name"].lower()), None)
        if not rep:
            return f"I do not have anyone named {rep_first} on your team. Your reps are {', '.join(r['first'] for r in reps[:10])}."
        if not rep["stops"]:
            return f"{rep['first']} is caught up. Nothing waiting, nothing overdue."
        lines = [f"{s['name']}, {_why(s)}" for s in rep["stops"][:6]]
        more = f" And {rep['total'] - 6} more on the screen." if rep["total"] > 6 else ""
        return f"{rep['first']} has {rep['total']} to work today. " + ". ".join(lines) + "." + more + f" Want me to nudge {rep['first']} about any of them?"
    busy = [r for r in reps if r["total"]]
    idle = [r for r in reps if not r["total"]]
    head = f"Your team today: {digest['total']} follow-ups across {len(busy)} of your {len(reps)} reps" + (f", {digest['waiting']} customers waiting on a reply" if digest.get("waiting") else "") + ". "
    parts = []
    for r in busy[:5]:
        own = [s for s in r["stops"] if not s.get("foreign")] or r["stops"]
        names = [f"{s['name']}, {_why(s)}" for s in own[:2]]
        extra = f", plus {r['total'] - 2} more" if r["total"] > 2 else ""
        parts.append(f"{r['first']} has {r['total']}: " + "; ".join(names) + extra + ".")
    if len(busy) > 5:
        parts.append(f"{len(busy) - 5} more reps have work on the screen.")
    if idle:
        parts.append((", ".join(r["first"] for r in idle[:6]) + (" and others" if len(idle) > 6 else "")) + (" is" if len(idle) == 1 else " are") + " caught up.")
    if digest.get("foreign"):
        who = [r["first"] for r in busy if r["foreign"]]
        parts.append(f"Heads up: {digest['foreign']} of these are on customers that belong to someone else, under {', '.join(who[:4])}. They are flagged on the screen so you can see where they came from.")
    out = head + " ".join(parts) + " Say a rep's name for their full list, or tell me to nudge someone."
    return out[:1300]


async def explain(db, manager: dict, rep_user_id: str) -> dict:
    """Where every one of a rep's stops came from: the owning rep of the customer, the task or conversation behind it, who created it and how.
    Plus any automations (campaign enrollments, queued sends) this rep has running on customers that are not theirs."""
    stops = await day_agenda.build(db, rep_user_id)
    cids = [ObjectId(s["contact_id"]) for s in stops if s.get("contact_id") and ObjectId.is_valid(s["contact_id"])]
    contacts = {str(c["_id"]): c for c in await db.contacts.find({"_id": {"$in": cids}}, {"first_name": 1, "last_name": 1, "user_id": 1, "birthday": 1, "anniversary": 1, "date_sold": 1, "tags": 1, "created_at": 1, "source": 1}).to_list(len(cids))} if cids else {}
    uids = {str(c.get("user_id")) for c in contacts.values() if c.get("user_id")} | {rep_user_id}
    users = {str(u["_id"]): u.get("name") or u.get("email") or "" for u in await db.users.find({"_id": {"$in": [ObjectId(x) for x in uids if ObjectId.is_valid(x)]}}, {"name": 1, "email": 1}).to_list(len(uids))}
    out = []
    for s in stops:
        c = contacts.get(s.get("contact_id") or "", {})
        row = {"n": s["n"], "kind": s["kind"], "label": KIND_LABEL.get(s["kind"], s["kind"]), "name": s["name"], "why": s["why"], "contact_id": s.get("contact_id"),
               "contact": {"owner_user_id": str(c.get("user_id") or ""), "owner_name": users.get(str(c.get("user_id") or ""), ""), "foreign": bool(s.get("foreign")),
                           "birthday": c.get("birthday").isoformat() if isinstance(c.get("birthday"), datetime) else c.get("birthday"),
                           "anniversary": c.get("anniversary").isoformat() if isinstance(c.get("anniversary"), datetime) else c.get("anniversary"),
                           "date_sold": c.get("date_sold").isoformat() if isinstance(c.get("date_sold"), datetime) else c.get("date_sold"),
                           "tags": c.get("tags") or [], "created_at": _iso(c.get("created_at")), "source": c.get("source")}}
        if s.get("task_id") and ObjectId.is_valid(s["task_id"]):
            t = await db.tasks.find_one({"_id": ObjectId(s["task_id"])}) or {}
            row["task"] = {k: _iso(t.get(k)) for k in ("title", "user_id", "source", "task_type", "action_type", "type", "campaign_id", "campaign_name", "created_by", "nudged_by_name", "auto_generated", "due_date", "created_at", "status")}
        if s.get("conversation_id"):
            conv = await db.conversations.find_one({"_id": ObjectId(s["conversation_id"])}) if ObjectId.is_valid(s["conversation_id"]) else None
            conv = conv or {}
            row["conversation"] = {k: _iso(conv.get(k)) for k in ("user_id", "inbox_id", "assigned_to", "channel", "source", "hot_opportunity", "created_at", "last_message_at")}
            row["conversation"]["owner_name"] = users.get(str(conv.get("user_id") or ""), "")
            msgs = await db.messages.find({"conversation_id": s["conversation_id"], "content": {"$exists": True, "$ne": ""}}, {"sender": 1, "content": 1, "timestamp": 1, "auto_sent": 1, "trigger_type": 1, "campaign_id": 1, "campaign_name": 1, "sent_by": 1, "source": 1, "user_id": 1}).sort("timestamp", -1).limit(4).to_list(4)
            row["recent_messages"] = [{k: _iso(m.get(k)) for k in ("sender", "content", "timestamp", "auto_sent", "trigger_type", "campaign_id", "campaign_name", "sent_by", "source", "user_id")} for m in msgs]
        out.append(row)
    foreign_ids = [cid for cid, c in contacts.items() if str(c.get("user_id") or "") not in ("", rep_user_id)]
    enrollments = await db.campaign_enrollments.find({"user_id": rep_user_id, "status": {"$in": ["active", "paused"]}}, {"contact_id": 1, "contact_name": 1, "campaign_name": 1, "trigger_type": 1, "enrolled_at": 1, "current_step": 1, "next_send_at": 1}).sort("enrolled_at", -1).limit(400).to_list(400)
    e_cids = [ObjectId(e["contact_id"]) for e in enrollments if ObjectId.is_valid(str(e.get("contact_id") or ""))]
    e_owner = {str(c["_id"]): str(c.get("user_id") or "") for c in await db.contacts.find({"_id": {"$in": e_cids}}, {"user_id": 1}).to_list(len(e_cids))} if e_cids else {}
    foreign_enrollments = [{**{k: _iso(e.get(k)) for k in ("contact_id", "contact_name", "campaign_name", "trigger_type", "enrolled_at", "current_step", "next_send_at")}, "id": str(e["_id"]),
                            "owner_name": users.get(e_owner.get(str(e.get("contact_id")), ""), "") or e_owner.get(str(e.get("contact_id")), "")}
                           for e in enrollments if e_owner.get(str(e.get("contact_id")), rep_user_id) not in ("", rep_user_id)]
    return {"rep_user_id": rep_user_id, "rep_name": users.get(rep_user_id, ""), "stops": out, "foreign_stops": sum(1 for r in out if r["contact"]["foreign"]),
            "foreign_enrollments": foreign_enrollments, "foreign_contact_ids": foreign_ids}


def _iso(v):
    return v.isoformat() if isinstance(v, datetime) else v


async def cancel_foreign_automations(db, rep_user_id: str) -> dict:
    """Stop every campaign enrollment and queued send this rep has on customers owned by somebody else."""
    enrollments = await db.campaign_enrollments.find({"user_id": rep_user_id, "status": {"$in": ["active", "paused"]}}, {"contact_id": 1}).to_list(2000)
    cids = [ObjectId(e["contact_id"]) for e in enrollments if ObjectId.is_valid(str(e.get("contact_id") or ""))]
    owner = {str(c["_id"]): str(c.get("user_id") or "") for c in await db.contacts.find({"_id": {"$in": cids}}, {"user_id": 1}).to_list(len(cids))} if cids else {}
    bad = [e["_id"] for e in enrollments if owner.get(str(e.get("contact_id")), rep_user_id) not in ("", rep_user_id)]
    now = datetime.now(timezone.utc)
    r1 = await db.campaign_enrollments.update_many({"_id": {"$in": bad}}, {"$set": {"status": "cancelled", "cancelled_at": now, "cancel_reason": "contact belongs to another rep"}}) if bad else None
    r2 = await db.campaign_pending_sends.update_many({"enrollment_id": {"$in": [str(b) for b in bad]}, "status": {"$in": ["pending", "pending_user"]}}, {"$set": {"status": "cancelled", "cancelled_at": now}}) if bad else None
    return {"enrollments_cancelled": r1.modified_count if r1 else 0, "sends_cancelled": r2.modified_count if r2 else 0}


async def _leak_rows(db, manager: dict) -> dict:
    """Every active/paused enrollment in this manager's scope whose contact belongs to somebody else, tagged cross-store or not.
    Super admins see the whole database (the original leak crossed tenants); store managers see their team."""
    everyone = (manager.get("role") or "") == "super_admin"
    scope = None if everyone else [str(manager["_id"])] + [r["user_id"] for r in await reps_for(db, manager)]
    q = {"status": {"$in": ["active", "paused"]}}
    if scope is not None:
        q["user_id"] = {"$in": scope}
    enr = await db.campaign_enrollments.find(q, {"user_id": 1, "contact_id": 1, "campaign_id": 1}).to_list(50000)
    cids = list({ObjectId(e["contact_id"]) for e in enr if ObjectId.is_valid(str(e.get("contact_id") or ""))})
    contacts = {str(c["_id"]): c for c in await db.contacts.find({"_id": {"$in": cids}}, {"user_id": 1, "store_id": 1}).to_list(len(cids))} if cids else {}
    uids = list({ObjectId(e["user_id"]) for e in enr if ObjectId.is_valid(str(e.get("user_id") or ""))})
    users = {str(u["_id"]): u for u in await db.users.find({"_id": {"$in": uids}}, {"name": 1, "store_id": 1}).to_list(len(uids))} if uids else {}
    rows = []
    for e in enr:
        c = contacts.get(str(e.get("contact_id")))
        if not c:
            continue
        owner = str(c.get("user_id") or "")
        if owner in ("", str(e.get("user_id")), None):
            continue
        rep = users.get(str(e.get("user_id"))) or {}
        cross = bool(c.get("store_id")) and bool(rep.get("store_id")) and str(c.get("store_id")) != str(rep.get("store_id"))
        rows.append({"enrollment_id": e["_id"], "rep_user_id": str(e.get("user_id")), "rep_name": rep.get("name") or "Unknown", "cross_store": cross})
    return {"rows": rows, "scope": "everyone" if everyone else "team"}


async def leak_scan(db, manager: dict) -> dict:
    data = await _leak_rows(db, manager)
    per: dict = {}
    for r in data["rows"]:
        row = per.setdefault(r["rep_user_id"], {"rep_user_id": r["rep_user_id"], "rep_name": r["rep_name"], "enrollments": 0, "cross_store": 0})
        row["enrollments"] += 1
        row["cross_store"] += 1 if r["cross_store"] else 0
    ids = [str(r["enrollment_id"]) for r in data["rows"]]
    sends = await db.campaign_pending_sends.count_documents({"enrollment_id": {"$in": ids}, "status": {"$in": ["pending", "pending_user"]}}) if ids else 0
    reps = sorted(per.values(), key=lambda r: (-r["cross_store"], -r["enrollments"]))
    return {"scope": data["scope"], "reps": reps, "total": len(ids), "cross_store": sum(1 for r in data["rows"] if r["cross_store"]), "queued_sends": sends}


async def cancel_leaks(db, manager: dict, cross_store_only: bool) -> dict:
    """One tap for the whole scope: stop every leaked enrollment (optionally only the ones that crossed a store line) and its queued sends."""
    data = await _leak_rows(db, manager)
    bad = [r["enrollment_id"] for r in data["rows"] if r["cross_store"] or not cross_store_only]
    if not bad:
        return {"enrollments_cancelled": 0, "sends_cancelled": 0, "reps": 0}
    now = datetime.now(timezone.utc)
    reason = "contact belongs to another store" if cross_store_only else "contact belongs to another rep"
    r1 = await db.campaign_enrollments.update_many({"_id": {"$in": bad}}, {"$set": {"status": "cancelled", "cancelled_at": now, "cancel_reason": reason, "cancelled_by": str(manager["_id"])}})
    r2 = await db.campaign_pending_sends.update_many({"enrollment_id": {"$in": [str(b) for b in bad]}, "status": {"$in": ["pending", "pending_user"]}}, {"$set": {"status": "cancelled", "cancelled_at": now}})
    reps = len({r["rep_user_id"] for r in data["rows"] if r["cross_store"] or not cross_store_only})
    logger.info(f"[TeamToday] {manager.get('name')} stopped {r1.modified_count} leaked enrollments ({'cross-store' if cross_store_only else 'all'}), {r2.modified_count} sends")
    return {"enrollments_cancelled": r1.modified_count, "sends_cancelled": r2.modified_count, "reps": reps}


async def nudge(db, manager: dict, rep_user_id: str, contact_id: str, note: str = "") -> dict:
    """A manager points a rep at one customer: a high-priority task on the rep's list today, an in-app notification and a push."""
    from routers.tasks import create_task
    from routers.notifications import create_notification
    from routers.push_notifications import send_push_to_user
    rep = await db.users.find_one({"_id": ObjectId(rep_user_id)}, {"name": 1}) if ObjectId.is_valid(rep_user_id) else None
    contact = await db.contacts.find_one({"_id": ObjectId(contact_id)}, {"first_name": 1, "last_name": 1, "phone": 1}) if ObjectId.is_valid(contact_id) else None
    if not rep or not contact:
        return {"ok": False, "error": "rep or contact not found"}
    cname = f"{contact.get('first_name') or ''} {contact.get('last_name') or ''}".strip()
    who = _first(manager)
    title = f"{who} asked: follow up with {cname}"
    task = await create_task(rep_user_id, {"title": title, "description": note or f"{who} flagged {cname} for today.", "contact_id": contact_id, "type": "follow_up", "action_type": "text",
                                           "priority": "high", "due_date": datetime.now(timezone.utc).isoformat()})
    await db.tasks.update_one({"_id": ObjectId(task["_id"])}, {"$set": {"source": "manager_nudge", "nudged_by": str(manager["_id"]), "nudged_by_name": manager.get("name") or ""}})
    body = f"{who}: follow up with {cname} today." + (f" {note}" if note else "")
    try:
        await create_notification("manager_nudge", f"Nudge from {who}", body, user_id=rep_user_id, contact_id=contact_id, contact_name=cname, contact_phone=contact.get("phone") or "", priority="high")
    except Exception as e:
        logger.warning(f"[TeamToday] notification failed: {e}")
    try:
        await send_push_to_user(rep_user_id, f"Nudge from {who}", body, url=f"/contact/{contact_id}", icon="flame")
    except Exception as e:
        logger.warning(f"[TeamToday] push failed: {e}")
    return {"ok": True, "task_id": task["_id"], "rep": rep.get("name") or "", "contact": cname}
