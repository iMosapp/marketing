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
        rows.append({**rep, "total": len(stops), "counts": counts,
                     "stops": [{"contact_id": s.get("contact_id"), "name": s.get("name"), "first": s.get("first"), "kind": s.get("kind"), "label": KIND_LABEL.get(s.get("kind"), s.get("kind")),
                                "why": s.get("why") or "", "conversation_id": s.get("conversation_id"), "task_id": s.get("task_id")} for s in stops[:PER_REP_SCREEN]]})
    rows.sort(key=lambda r: (-r["counts"].get("reply", 0), -r["total"], r["name"].lower()))
    return {"reps": rows, "rep_count": len(rows), "total": sum(r["total"] for r in rows),
            "waiting": sum(r["counts"].get("reply", 0) for r in rows), "generated_at": datetime.now(timezone.utc).isoformat()}


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
        names = [f"{s['name']}, {_why(s)}" for s in r["stops"][:2]]
        extra = f", plus {r['total'] - 2} more" if r["total"] > 2 else ""
        parts.append(f"{r['first']} has {r['total']}: " + "; ".join(names) + extra + ".")
    if len(busy) > 5:
        parts.append(f"{len(busy) - 5} more reps have work on the screen.")
    if idle:
        parts.append((", ".join(r["first"] for r in idle[:6]) + (" and others" if len(idle) > 6 else "")) + (" is" if len(idle) == 1 else " are") + " caught up.")
    out = head + " ".join(parts) + " Say a rep's name for their full list, or tell me to nudge someone."
    return out[:1300]


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
