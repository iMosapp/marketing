"""Courses: an ordered bundle of challenges with a pass mark. Reps take them by practice call; mystery-shop people get called with each one until they pass."""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from bson import ObjectId

from services import mystery_shops as ms
from services import scripts as scr

logger = logging.getLogger(__name__)
DEFAULT_PASS = 80


def _now():
    return datetime.now(timezone.utc)


def _iso(v):
    return v.isoformat() if isinstance(v, datetime) else v


def serialize_course(c: dict, extra: Optional[dict] = None) -> dict:
    from services import industries as ind
    dept = c.get("department") or "mixed"
    out = {"id": str(c["_id"]), "title": c.get("title", ""), "description": c.get("description", ""), "department": dept, "department_label": "Mixed" if dept == "mixed" else ind.dept_label(dept), "challenge_ids": c.get("challenge_ids") or [],
           "pass_pct": int(c.get("pass_pct") or DEFAULT_PASS), "badge_label": c.get("badge_label") or f"Certified: {c.get('title', '')}", "active": c.get("active", True), "created_by_name": c.get("created_by_name"),
           "created_at": _iso(c.get("created_at")), "updated_at": _iso(c.get("updated_at"))}
    if extra:
        out.update(extra)
    return out


def serialize_enrollment(e: dict, course: Optional[dict] = None, extra: Optional[dict] = None) -> dict:
    ids = (course or {}).get("challenge_ids") or []
    prog = e.get("progress") or {}
    passed = [cid for cid in ids if (prog.get(cid) or {}).get("passed")]
    out = {"id": str(e["_id"]), "course_id": e.get("course_id"), "kind": e.get("kind"), "user_id": e.get("user_id"), "target_id": e.get("target_id"), "client_id": e.get("client_id"), "name": e.get("name"),
           "status": e.get("status"), "assigned_at": _iso(e.get("assigned_at")), "assigned_by_name": e.get("assigned_by_name"), "certified_at": _iso(e.get("certified_at")), "certificate_token": e.get("certificate_token"),
           "certificate_url": f"{scr._app_url()}/certificate/{e['certificate_token']}" if e.get("certificate_token") else None, "note": e.get("note") or "",
           "progress": {cid: {**{k: _iso(v) for k, v in (prog.get(cid) or {}).items()}} for cid in ids}, "passed": len(passed), "total": len(ids),
           "next_challenge_id": next((cid for cid in ids if not (prog.get(cid) or {}).get("passed")), None), "last_activity_at": _iso(e.get("last_activity_at"))}
    if extra:
        out.update(extra)
    return out


async def challenges_for(db, course: dict) -> list:
    ids = [ObjectId(x) for x in (course.get("challenge_ids") or []) if ObjectId.is_valid(str(x))]
    rows = {str(s["_id"]): s for s in await db.scripts.find({"_id": {"$in": ids}}).to_list(200)} if ids else {}
    return [rows[str(i)] for i in ids if str(i) in rows]


async def enroll(db, course: dict, me: dict, kind: str, ref: dict, note: str = "") -> dict:
    """Idempotent: one live enrollment per person per course. Returns the enrollment (existing or new)."""
    key = {"course_id": str(course["_id"]), "kind": kind, ("user_id" if kind == "user" else "target_id"): ref["id"]}
    cur = await db.course_enrollments.find_one(key)
    if cur:
        return cur
    now = _now()
    doc = {**key, "name": ref.get("name") or "", "client_id": ref.get("client_id"), "store_id": ref.get("store_id"), "assigned_by": str(me["_id"]), "assigned_by_name": me.get("name"), "assigned_at": now,
           "status": "in_progress", "progress": {}, "note": (note or "").strip()[:300], "created_at": now, "updated_at": now}
    res = await db.course_enrollments.insert_one(doc)
    doc["_id"] = res.inserted_id
    if kind == "target":
        await schedule_next_shop(db, doc, course)
    return doc


async def schedule_next_shop(db, enrollment: dict, course: dict, delay_minutes: int = 5) -> Optional[dict]:
    """For a mystery-shop person: put the next un-passed challenge on the dialer inside the client's hours."""
    prog = enrollment.get("progress") or {}
    nxt = next((cid for cid in (course.get("challenge_ids") or []) if not (prog.get(cid) or {}).get("passed")), None)
    if not nxt:
        return None
    if await db.roleplay_sessions.find_one({"kind": "mystery_shop", "enrollment_id": str(enrollment["_id"]), "status": {"$in": ms.CALL_STATUSES_OPEN}}, {"_id": 1}):
        return None
    client = await db.shop_clients.find_one({"_id": ms._oid(enrollment["client_id"])}) if enrollment.get("client_id") else None
    target = await db.shop_targets.find_one({"_id": ms._oid(enrollment["target_id"])})
    script = await db.scripts.find_one({"_id": ObjectId(nxt)})
    if not client or not target or not script:
        return None
    when = ms.next_slot(client, _now() + timedelta(minutes=delay_minutes), min_gap_minutes=0)
    call = await ms.create_shop_call(db, client, target, when, created_by=enrollment.get("assigned_by"), manual=False, script=script)
    if call:
        await db.roleplay_sessions.update_one({"_id": call["_id"]}, {"$set": {"enrollment_id": str(enrollment["_id"]), "course_id": str(course["_id"]), "course_title": course.get("title")}})
    return call


async def record_result(db, session: dict, score_pct: Optional[int]):
    """A graded session that belongs to a course: update best score, mark passed, certify when everything is passed, line up the next shop call."""
    eid = session.get("enrollment_id")
    if not eid or not ObjectId.is_valid(str(eid)):
        return
    e = await db.course_enrollments.find_one({"_id": ObjectId(eid)})
    course = await db.courses.find_one({"_id": ObjectId(e["course_id"])}) if e else None
    if not e or not course:
        return
    cid = str(session.get("script_id"))
    if cid not in (course.get("challenge_ids") or []):
        return
    pass_pct = int(course.get("pass_pct") or DEFAULT_PASS)
    cur = (e.get("progress") or {}).get(cid) or {}
    best = max([v for v in (cur.get("best_pct"), score_pct) if isinstance(v, (int, float))], default=None)
    passed = bool(cur.get("passed")) or (score_pct is not None and score_pct >= pass_pct)
    now = _now()
    entry = {"best_pct": best, "attempts": int(cur.get("attempts") or 0) + 1, "passed": passed, "last_pct": score_pct, "last_session_id": str(session["_id"]), "last_at": now, "passed_at": cur.get("passed_at") or (now if passed else None)}
    await db.course_enrollments.update_one({"_id": e["_id"]}, {"$set": {f"progress.{cid}": entry, "last_activity_at": now, "updated_at": now}})
    e = await db.course_enrollments.find_one({"_id": e["_id"]})
    prog = e.get("progress") or {}
    all_passed = all((prog.get(x) or {}).get("passed") for x in course.get("challenge_ids") or [])
    if all_passed and e.get("status") != "certified":
        await certify(db, e, course)
    elif e.get("kind") == "target":
        await schedule_next_shop(db, e, course, delay_minutes=(60 if passed else 24 * 60))
    elif e.get("kind") == "user" and not passed:
        pass


async def certify(db, e: dict, course: dict):
    from routers.push_notifications import send_push_to_user
    from routers.notifications_center import invalidate_feed
    now = _now()
    token = e.get("certificate_token") or uuid.uuid4().hex
    await db.course_enrollments.update_one({"_id": e["_id"]}, {"$set": {"status": "certified", "certified_at": now, "certificate_token": token, "updated_at": now}})
    url = f"{scr._app_url()}/certificate/{token}"
    badge = course.get("badge_label") or f"Certified: {course.get('title')}"
    first = (e.get("name") or "").split(" ")[0] or "They"
    if e.get("kind") == "user" and e.get("user_id"):
        await db.users.update_one({"_id": ObjectId(e["user_id"])}, {"$pull": {"certifications": {"course_id": str(course["_id"])}}})
        await db.users.update_one({"_id": ObjectId(e["user_id"])}, {"$push": {"certifications": {"course_id": str(course["_id"]), "title": course.get("title"), "badge_label": badge, "certified_at": now, "certificate_token": token}}})
        title, msg, link = (badge if badge.lower().startswith("certified") else f"Certified: {badge}"), f"Every challenge in {course.get('title')} passed at {course.get('pass_pct') or DEFAULT_PASS}% or better. Your certificate is ready to share.", f"/courses/{course['_id']}"
        await db.notifications.insert_one({"user_id": e["user_id"], "type": "course_certified", "title": title, "message": msg, "link": link, "read": False, "dismissed": False, "created_at": now})
        invalidate_feed(e["user_id"])
        try:
            await send_push_to_user(e["user_id"], title, msg, link, "ribbon")
        except Exception as ex:
            logger.debug(f"[Courses] certified push failed: {ex}")
    elif e.get("kind") == "target":
        target = await db.shop_targets.find_one({"_id": ms._oid(e["target_id"])}) if e.get("target_id") else None
        client = await db.shop_clients.find_one({"_id": ms._oid(e["client_id"])}) if e.get("client_id") else None
        if target and target.get("phone"):
            from services.twilio_service import send_sms
            try:
                await send_sms(target["phone"], f"{first}, you did it. Every challenge in {course.get('title')} passed at {course.get('pass_pct') or DEFAULT_PASS}% or better. You are {badge}. Your certificate: {url}", from_phone=await ms.from_number(db, client) or None)
            except Exception as ex:
                logger.warning(f"[Courses] certificate text failed: {ex}")
    if e.get("assigned_by") and e.get("assigned_by") != e.get("user_id"):
        title = f"{first} is {badge}"
        msg = f"Every challenge in {course.get('title')} passed. Tap to see the scores."
        link = f"/admin/courses/{course['_id']}"
        await db.notifications.insert_one({"user_id": e["assigned_by"], "type": "course_certified", "title": title, "message": msg, "link": link, "read": False, "dismissed": False, "created_at": now})
        invalidate_feed(e["assigned_by"])
        try:
            await send_push_to_user(e["assigned_by"], title, msg, link, "ribbon")
        except Exception as ex:
            logger.debug(f"[Courses] manager push failed: {ex}")


async def notify_assigned(db, course: dict, me: dict, user_ids: list):
    from routers.push_notifications import send_push_to_user
    from routers.notifications_center import invalidate_feed
    n = len(course.get("challenge_ids") or [])
    title = f"New course: {course.get('title')}"
    msg = f"{me.get('name') or 'Your manager'} enrolled you. Pass all {n} challenge{'s' if n != 1 else ''} at {course.get('pass_pct') or DEFAULT_PASS}% or better to get certified. Tap to start."
    link = f"/courses/{course['_id']}"
    now = _now()
    for uid in user_ids:
        await db.notifications.insert_one({"user_id": uid, "type": "course_assigned", "title": title, "message": msg, "link": link, "read": False, "dismissed": False, "created_at": now})
        invalidate_feed(uid)
        try:
            await send_push_to_user(uid, title, msg, link, "school")
        except Exception as ex:
            logger.debug(f"[Courses] assign push failed: {ex}")


def public_certificate(e: dict, course: dict, challenges: list) -> dict:
    prog = e.get("progress") or {}
    return {"name": e.get("name"), "course_title": course.get("title"), "badge_label": course.get("badge_label") or f"Certified: {course.get('title')}", "department": course.get("department") or "mixed",
            "description": course.get("description") or "", "pass_pct": int(course.get("pass_pct") or DEFAULT_PASS), "certified_at": _iso(e.get("certified_at")),
            "challenges": [{"title": s.get("title"), "best_pct": (prog.get(str(s["_id"])) or {}).get("best_pct"), "attempts": (prog.get(str(s["_id"])) or {}).get("attempts") or 0} for s in challenges],
            "issuer": "I'm On Social", "kind": e.get("kind")}
