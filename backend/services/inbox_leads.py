"""How leads reach a shared inbox's team, in one place: which lead sources point here, who rings, who gets pinged,
and the one-tap fixes ("point this source here", "ring everyone on this inbox")."""
from typing import Optional

from bson import ObjectId

from services import inboxes as ib
from services import lead_flows as lf
from services.lead_call_engine import normalize_attempts

RING_KINDS = ("everyone", "some", "others", "none", "text_only")


def _oid(v) -> Optional[ObjectId]:
    return ObjectId(str(v)) if ObjectId.is_valid(str(v or "")) else None


def _first(u: dict) -> str:
    return (u.get("name") or u.get("first_name") or "Rep").split(" ")[0]


async def _people(db, ids: set) -> dict:
    oids = [ObjectId(i) for i in ids if ObjectId.is_valid(str(i))]
    out = {}
    if not oids:
        return out
    async for u in db.users.find({"_id": {"$in": oids}}, {"name": 1, "first_name": 1, "phone": 1, "twilio_number": 1, "mvpline_number": 1, "status": 1, "photo_thumbnail": 1, "photo_url": 1}):
        out[str(u["_id"])] = {"id": str(u["_id"]), "name": u.get("name") or u.get("first_name") or "Rep", "first": _first(u),
                              "has_cell": bool((u.get("phone") or "").strip()), "has_number": bool(u.get("twilio_number") or u.get("mvpline_number")),
                              "photo": u.get("photo_thumbnail") or u.get("photo_url"), "active": u.get("status") != "deactivated"}
    return out


def pointed_query(inbox_id: str) -> dict:
    return {"$or": [{"inbox_id": inbox_id}, {"team_id": inbox_id}], "is_active": {"$ne": False}, "active": {"$ne": False}}


def _ringing(eff: dict, raw: dict, team: list, people: dict) -> dict:
    """Who a source rings after the flow + inbox are applied. `raw` is the stored doc (to spot the @inbox token)."""
    mode = eff.get("contact_mode") or "text_only"
    if mode != "text_and_call":
        return {"kind": "text_only", "attempts": 0, "names": [], "missing": [], "dynamic": False}
    attempts = normalize_attempts(eff.get("call_attempts"), eff.get("workflow_user_ids") or [])
    rung: list = []
    for a in attempts:
        for u in a["user_ids"]:
            if u not in rung:
                rung.append(u)
    missing = [m for m in team if m not in rung]
    if not rung:
        kind = "none"
    elif team and not missing:
        kind = "everyone"
    elif any(m in rung for m in team):
        kind = "some"
    else:
        kind = "others"
    dynamic = any(ib.INBOX_TOKEN in (a.get("user_ids") or []) for a in raw.get("call_attempts") or [])
    return {"kind": kind, "attempts": len(attempts), "names": [people.get(u, {}).get("first", "Rep") for u in rung],
            "missing": [people.get(u, {}).get("first", "Rep") for u in missing], "dynamic": dynamic,
            "no_cell": [people[u]["first"] for u in rung if u in people and not people[u]["has_cell"]]}


async def overview(db, inbox: dict) -> dict:
    iid = str(inbox["_id"])
    team = ib.members(inbox)
    sources = await db.lead_sources.find(pointed_query(iid)).sort("name", 1).to_list(200)
    effs = []
    ids: set = set(team)
    for s in sources:
        flowed = await lf.apply_flow(db, s)
        eff = await ib.apply_inbox(db, flowed)
        effs.append((flowed, eff))
        for a in eff.get("call_attempts") or []:
            ids.update(a.get("user_ids") or [])
    people = await _people(db, ids)
    rows = []
    for s, (raw, eff) in zip(sources, effs):
        direct = s.get("kind") == "inbox_direct"
        rows.append({
            "id": str(s["_id"]), "name": s.get("name") or "Lead source", "kind": s.get("kind") or "source", "direct": direct,
            "lead_count": s.get("lead_count", 0), "flow": {"id": str(s["flow_id"]), "name": s.get("flow_name") or "Lead flow"} if _oid(s.get("flow_id")) else None,
            "contact_mode": eff.get("contact_mode") or "text_only", "routing": eff.get("assignment_method") or "jump_ball",
            "notify_everyone": bool(eff.get("notify_all_on_intake", True)),
            "ringing": _ringing(eff, raw, team, people),
            "website_default": bool(s.get("website_default")), "website_pages": s.get("website_pages") or [],
        })
    # sources on the same store that live elsewhere (or nowhere) and could be pointed here
    other = []
    if inbox.get("store_id"):
        sid = str(inbox["store_id"])
        pointed = {r["id"] for r in rows}
        inbox_names = {str(i["_id"]): i.get("name") for i in await db.shared_inboxes.find({"store_id": {"$in": [sid] + ([ObjectId(sid)] if ObjectId.is_valid(sid) else [])}}, {"name": 1}).to_list(100)}
        async for s in db.lead_sources.find({"store_id": sid, "kind": {"$ne": "inbox_direct"}, "is_active": {"$ne": False}, "active": {"$ne": False}}, {"name": 1, "inbox_id": 1, "team_id": 1, "lead_count": 1}).sort("name", 1):
            if str(s["_id"]) in pointed:
                continue
            cur = s.get("inbox_id") or s.get("team_id")
            other.append({"id": str(s["_id"]), "name": s.get("name") or "Lead source", "lead_count": s.get("lead_count", 0), "inbox_name": inbox_names.get(str(cur)) if cur else None})
    call_rows = [r for r in rows if r["contact_mode"] == "text_and_call"]
    checklist = {
        "number": bool(inbox.get("phone_number")),
        "members": len(team), "members_without_number": sum(1 for m in team if m in people and not people[m]["has_number"]),
        "members_without_cell": [people[m]["first"] for m in team if m in people and not people[m]["has_cell"]],
        "sources": sum(1 for r in rows if not r["direct"]),
        "ringing_ok": (all(r["ringing"]["kind"] == "everyone" for r in call_rows) if call_rows else None),
        "ai_mode": inbox.get("ai_mode") or "auto_reply",
    }
    return {"sources": rows, "other_sources": other, "team": [people.get(m) or {"id": m, "name": "Removed user", "first": "Removed", "active": False} for m in team], "checklist": checklist}


async def point_source(db, inbox: dict, source_id: str, me: dict) -> dict:
    src = await db.lead_sources.find_one({"_id": _oid(source_id)}) if _oid(source_id) else None
    if not src:
        raise ValueError("Lead source not found")
    if src.get("kind") == "inbox_direct":
        raise ValueError("That is an inbox's own text line, it already lives where it belongs")
    if inbox.get("store_id") and src.get("store_id") and str(src["store_id"]) != str(inbox["store_id"]) and me.get("role") != "super_admin":
        raise PermissionError("That lead source belongs to another store")
    iid = str(inbox["_id"])
    await db.lead_sources.update_one({"_id": src["_id"]}, {"$set": {"inbox_id": iid, "team_id": iid, "updated_at": ib._now()}})
    return src


async def unpoint_source(db, inbox: dict, source_id: str) -> None:
    iid = str(inbox["_id"])
    res = await db.lead_sources.update_one({"_id": _oid(source_id), **{"$or": [{"inbox_id": iid}, {"team_id": iid}]}, "kind": {"$ne": "inbox_direct"}},
                                           {"$set": {"team_id": "", "updated_at": ib._now()}, "$unset": {"inbox_id": ""}})
    if not res.matched_count:
        raise ValueError("That lead source is not on this inbox")


async def ring_everyone(db, inbox: dict, source_id: str, me: dict) -> dict:
    """Put "@inbox" on attempt 1 of whatever rings for this source: its Lead Flow (shared by every source using it),
    else the source's own ladder. Returns {"changed": "flow"|"source", "name": ...}."""
    src = await db.lead_sources.find_one({"_id": _oid(source_id)}) if _oid(source_id) else None
    if not src:
        raise ValueError("Lead source not found")
    iid = str(inbox["_id"])
    if src.get("inbox_id") != iid and src.get("team_id") != iid:
        raise ValueError("That lead source is not on this inbox")

    def with_token(attempts: list) -> list:
        out = [dict(a) for a in (attempts or []) if a.get("user_ids") or not attempts]
        if not out:
            out = [{"user_ids": [], "delay_seconds": 0, "delivery": "call"}]
        first = out[0]
        if ib.INBOX_TOKEN not in (first.get("user_ids") or []):
            first["user_ids"] = [ib.INBOX_TOKEN] + [u for u in first.get("user_ids") or [] if u != ib.INBOX_TOKEN]
        return out

    flow = await db[lf.COLL].find_one({"_id": _oid(src["flow_id"])}) if _oid(src.get("flow_id")) else None
    if flow:
        body = {"contact_mode": "text_and_call", "call_attempts": with_token(flow.get("call_attempts"))}
        cleaned = lf.clean_flow(body, flow)
        cleaned.update({"updated_at": ib._now(), "updated_by": str(me["_id"]), "updated_by_name": me.get("name") or me.get("first_name") or ""})
        await db[lf.COLL].update_one({"_id": flow["_id"]}, {"$set": cleaned})
        await lf.sync_flow_to_sources(db, {**flow, **cleaned})
        return {"changed": "flow", "name": flow.get("name")}
    attempts = [{"user_ids": a.get("user_ids") or [], "delay_seconds": max(0 if i == 0 else 30, int(a.get("delay_seconds") or (0 if i == 0 else 60))), **({"delivery": a["delivery"]} if a.get("delivery") else {})}
                for i, a in enumerate(with_token(src.get("call_attempts"))[:4])]
    notify = [u for u in src.get("workflow_user_ids") or [] if u != ib.INBOX_TOKEN]
    await db.lead_sources.update_one({"_id": src["_id"]}, {"$set": {"contact_mode": "text_and_call", "call_attempts": attempts,
                                                                    "workflow_user_ids": [ib.INBOX_TOKEN] + notify, "updated_at": ib._now()}})
    return {"changed": "source", "name": src.get("name")}
