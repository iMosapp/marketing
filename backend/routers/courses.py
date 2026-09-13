"""Courses & certification: Forest builds courses from the challenge library; managers enroll reps, Forest enrolls mystery-shop people."""
import logging
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from routers.database import get_db
from routers.scripts import require_user, _current, _is_manager
from services import courses as cs
from services import mystery_shops as ms
from services import scripts as scr
from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/courses", tags=["Courses"], dependencies=[Depends(require_user)])
public_router = APIRouter(prefix="/public", tags=["Courses public"])
OWNER_ROLES = {"super_admin", "admin"}


class CourseBody(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    department: Optional[str] = None
    challenge_ids: Optional[list] = None
    pass_pct: Optional[int] = None
    badge_label: Optional[str] = None
    active: Optional[bool] = None


class AssignBody(BaseModel):
    user_ids: list = []
    target_ids: list = []
    note: Optional[str] = ""


def _oid(v: str, what: str = "Course") -> ObjectId:
    if not ObjectId.is_valid(str(v)):
        raise HTTPException(status_code=404, detail=f"{what} not found")
    return ObjectId(str(v))


def _owner(me: dict):
    if me.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Courses are built by iMOS admins")


async def _course(db, cid: str) -> dict:
    c = await db.courses.find_one({"_id": _oid(cid), "active": {"$ne": False}})
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")
    return c


def _fields(body: CourseBody) -> dict:
    d = {k: v for k, v in body.dict().items() if v is not None}
    if "title" in d:
        d["title"] = no_em_dash(d["title"].strip())[:120]
    if "description" in d:
        d["description"] = no_em_dash(d["description"].strip())[:1000]
    if "badge_label" in d:
        d["badge_label"] = no_em_dash(d["badge_label"].strip())[:80]
    if "department" in d and d["department"] not in ms.ALL_DEPARTMENTS + ["mixed"]:
        raise HTTPException(status_code=400, detail="Department must be sales, service, parts, rental or mixed")
    if "pass_pct" in d:
        d["pass_pct"] = max(50, min(100, int(d["pass_pct"])))
    if "challenge_ids" in d:
        ids, seen = [], set()
        for x in d["challenge_ids"]:
            if ObjectId.is_valid(str(x)) and str(x) not in seen:
                ids.append(str(x)); seen.add(str(x))
        d["challenge_ids"] = ids[:60]
    return d


def _challenge_out(s: dict) -> dict:
    return {"id": str(s["_id"]), "title": s.get("title"), "department": s.get("department"), "purpose": s.get("purpose", ""), "runtime": s.get("runtime", ""), "persona_name": (s.get("persona") or {}).get("name"), "active": s.get("active", True)}


async def _stats(db, course: dict) -> dict:
    rows = await db.course_enrollments.find({"course_id": str(course["_id"])}, {"status": 1}).to_list(2000)
    return {"enrolled": len(rows), "certified": len([r for r in rows if r.get("status") == "certified"]), "challenge_count": len(course.get("challenge_ids") or [])}


def _visible_enrollments_q(me: dict, course_id: str) -> dict:
    q = {"course_id": course_id}
    if me.get("role") not in OWNER_ROLES:
        q["$or"] = [{"store_id": me.get("store_id")}, {"assigned_by": str(me["_id"])}]
    return q


# ---------------------------------------------------------------- list / CRUD
@router.get("")
async def list_courses(request: Request):
    me = await _current(request)
    db = get_db()
    courses = await db.courses.find({"active": {"$ne": False}}).sort("title", 1).to_list(200)
    mine = await db.course_enrollments.find({"kind": "user", "user_id": str(me["_id"])}).to_list(100)
    by_id = {str(c["_id"]): c for c in courses}
    return {"courses": [cs.serialize_course(c, await _stats(db, c)) for c in courses], "can_manage": me.get("role") in OWNER_ROLES, "can_assign": _is_manager(me),
            "my": [cs.serialize_enrollment(e, by_id.get(e["course_id"]), {"course": cs.serialize_course(by_id[e["course_id"]])}) for e in mine if e.get("course_id") in by_id],
            "certifications": (me.get("certifications") or []) and [{**c, "certified_at": cs._iso(c.get("certified_at"))} for c in me.get("certifications")], "departments": [{"key": d, "label": ms.DEPT_LABEL[d]} for d in ms.ALL_DEPARTMENTS] + [{"key": "mixed", "label": "Mixed"}]}


@router.post("")
async def create_course(body: CourseBody, request: Request):
    me = await _current(request)
    _owner(me)
    d = _fields(body)
    if not d.get("title"):
        raise HTTPException(status_code=400, detail="Give the course a name")
    now = datetime.now(timezone.utc)
    doc = {"description": "", "department": "mixed", "challenge_ids": [], "pass_pct": cs.DEFAULT_PASS, "badge_label": f"Certified: {d['title']}", **d, "active": True, "created_by": str(me["_id"]), "created_by_name": me.get("name"), "created_at": now, "updated_at": now}
    res = await get_db().courses.insert_one(doc)
    return cs.serialize_course(await get_db().courses.find_one({"_id": res.inserted_id}), {"enrolled": 0, "certified": 0, "challenge_count": len(doc["challenge_ids"])})


@router.get("/{cid}")
async def get_course(cid: str, request: Request):
    me = await _current(request)
    db = get_db()
    c = await _course(db, cid)
    challenges = await cs.challenges_for(db, c)
    enrollments = await db.course_enrollments.find(_visible_enrollments_q(me, cid)).sort("assigned_at", -1).to_list(500) if _is_manager(me) else []
    mine = await db.course_enrollments.find_one({"course_id": cid, "kind": "user", "user_id": str(me["_id"])})
    return {"course": cs.serialize_course(c, await _stats(db, c)), "challenges": [_challenge_out(s) for s in challenges], "enrollments": [cs.serialize_enrollment(e, c) for e in enrollments],
            "my_enrollment": cs.serialize_enrollment(mine, c) if mine else None, "can_manage": me.get("role") in OWNER_ROLES, "can_assign": _is_manager(me)}


@router.put("/{cid}")
async def update_course(cid: str, body: CourseBody, request: Request):
    me = await _current(request)
    _owner(me)
    db = get_db()
    c = await _course(db, cid)
    d = _fields(body)
    if "title" in d and not d["title"]:
        raise HTTPException(status_code=400, detail="Give the course a name")
    await db.courses.update_one({"_id": c["_id"]}, {"$set": {**d, "updated_at": datetime.now(timezone.utc)}})
    c = await db.courses.find_one({"_id": c["_id"]})
    if "challenge_ids" in d or "pass_pct" in d:
        await _recheck(db, c)
    return cs.serialize_course(c, await _stats(db, c))


async def _recheck(db, course: dict):
    """Course changed: anyone who now has every challenge passed gets certified; certified people stay certified."""
    async for e in db.course_enrollments.find({"course_id": str(course["_id"]), "status": {"$ne": "certified"}}):
        prog = e.get("progress") or {}
        ids = course.get("challenge_ids") or []
        if ids and all((prog.get(x) or {}).get("passed") for x in ids):
            await cs.certify(db, e, course)
        elif e.get("kind") == "target":
            await cs.schedule_next_shop(db, e, course)


@router.delete("/{cid}")
async def delete_course(cid: str, request: Request):
    me = await _current(request)
    _owner(me)
    db = get_db()
    c = await _course(db, cid)
    await db.courses.update_one({"_id": c["_id"]}, {"$set": {"active": False, "updated_at": datetime.now(timezone.utc)}})
    await db.roleplay_sessions.update_many({"kind": "mystery_shop", "course_id": cid, "status": "scheduled"}, {"$set": {"status": "canceled", "fail_reason": "Course retired", "updated_at": datetime.now(timezone.utc)}})
    return {"ok": True}


# ---------------------------------------------------------------- enrollment
@router.get("/{cid}/people")
async def assignable_people(cid: str, request: Request):
    """Who this user may enroll: their store's reps (managers), plus every mystery-shop person (iMOS admins)."""
    me = await _current(request)
    if not _is_manager(me):
        raise HTTPException(status_code=403, detail="Managers assign courses")
    db = get_db()
    await _course(db, cid)
    uq = {"status": {"$ne": "deactivated"}, "active": {"$ne": False}}
    if me.get("role") not in OWNER_ROLES:
        uq["$or"] = [{"store_id": me.get("store_id")}, {"store_ids": me.get("store_id")}]
    users = await db.users.find(uq, {"name": 1, "first_name": 1, "role": 1, "store_id": 1, "photo_url": 1}).sort("name", 1).limit(500).to_list(500)
    enrolled = {(e["kind"], e.get("user_id") or e.get("target_id")) for e in await db.course_enrollments.find({"course_id": cid}, {"kind": 1, "user_id": 1, "target_id": 1}).to_list(2000)}
    out = {"users": [{"id": str(u["_id"]), "name": u.get("name") or u.get("first_name") or "Rep", "role": u.get("role"), "enrolled": ("user", str(u["_id"])) in enrolled} for u in users], "targets": []}
    if me.get("role") in OWNER_ROLES:
        clients = {str(c["_id"]): c.get("name") for c in await db.shop_clients.find({}, {"name": 1}).to_list(200)}
        targets = await db.shop_targets.find({"active": {"$ne": False}}).sort([("client_id", 1), ("name", 1)]).to_list(1000)
        out["targets"] = [{"id": str(t["_id"]), "name": t.get("name"), "department": t.get("department"), "client_id": t.get("client_id"), "client_name": clients.get(t.get("client_id"), ""), "enrolled": ("target", str(t["_id"])) in enrolled} for t in targets]
    return out


@router.post("/{cid}/assign")
async def assign(cid: str, body: AssignBody, request: Request):
    me = await _current(request)
    if not _is_manager(me):
        raise HTTPException(status_code=403, detail="Managers assign courses")
    db = get_db()
    c = await _course(db, cid)
    if not c.get("challenge_ids"):
        raise HTTPException(status_code=400, detail="Add at least one challenge to the course first")
    created, notified = [], []
    for uid in body.user_ids[:200]:
        u = await db.users.find_one({"_id": _oid(uid, "Rep")}, {"name": 1, "first_name": 1, "store_id": 1, "store_ids": 1})
        if not u:
            continue
        if me.get("role") not in OWNER_ROLES and me.get("store_id") not in [u.get("store_id")] + list(u.get("store_ids") or []):
            raise HTTPException(status_code=403, detail="You can only enroll reps on your own store")
        before = await db.course_enrollments.count_documents({"course_id": cid, "kind": "user", "user_id": uid})
        e = await cs.enroll(db, c, me, "user", {"id": uid, "name": u.get("name") or u.get("first_name") or "Rep", "store_id": u.get("store_id")}, body.note or "")
        created.append(cs.serialize_enrollment(e, c))
        if not before:
            notified.append(uid)
    if body.target_ids and me.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="Only iMOS admins enroll mystery-shop people")
    for tid in body.target_ids[:200]:
        t = await db.shop_targets.find_one({"_id": _oid(tid, "Person")})
        if not t:
            continue
        e = await cs.enroll(db, c, me, "target", {"id": tid, "name": t.get("name"), "client_id": t.get("client_id")}, body.note or "")
        created.append(cs.serialize_enrollment(e, c))
    if notified:
        await cs.notify_assigned(db, c, me, notified)
    return {"enrollments": created, "notified": len(notified)}


@router.get("/enrollments/{eid}")
async def enrollment_detail(eid: str, request: Request):
    me = await _current(request)
    db = get_db()
    e = await db.course_enrollments.find_one({"_id": _oid(eid, "Enrollment")})
    if not e:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    if not (_is_manager(me) or e.get("user_id") == str(me["_id"])):
        raise HTTPException(status_code=403, detail="Not your course")
    c = await db.courses.find_one({"_id": ObjectId(e["course_id"])}) or {}
    sessions = await db.roleplay_sessions.find({"$or": [{"enrollment_id": eid}, {"user_id": e.get("user_id"), "script_id": {"$in": c.get("challenge_ids") or []}, "status": "completed"}] if e.get("user_id") else {"enrollment_id": eid}},
                                              {"script_id": 1, "script_title": 1, "score_pct": 1, "status": 1, "ended_at": 1, "started_at": 1, "evaluation_id": 1, "mode": 1, "kind": 1, "fail_reason": 1}).sort("started_at", -1).limit(200).to_list(200)
    return {"enrollment": cs.serialize_enrollment(e, c), "course": cs.serialize_course(c), "challenges": [_challenge_out(s) for s in await cs.challenges_for(db, c)],
            "attempts": [{"session_id": str(s["_id"]), "script_id": s.get("script_id"), "script_title": s.get("script_title"), "score_pct": s.get("score_pct"), "status": s.get("status"), "mode": s.get("mode"), "kind": s.get("kind"),
                          "fail_reason": s.get("fail_reason"), "evaluation_id": s.get("evaluation_id"), "at": cs._iso(s.get("ended_at") or s.get("started_at"))} for s in sessions]}


@router.delete("/enrollments/{eid}")
async def unenroll(eid: str, request: Request):
    me = await _current(request)
    if not _is_manager(me):
        raise HTTPException(status_code=403, detail="Managers manage enrollments")
    db = get_db()
    e = await db.course_enrollments.find_one({"_id": _oid(eid, "Enrollment")})
    if not e:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    if me.get("role") not in OWNER_ROLES and e.get("store_id") != me.get("store_id") and e.get("assigned_by") != str(me["_id"]):
        raise HTTPException(status_code=403, detail="Not your enrollment")
    await db.course_enrollments.delete_one({"_id": e["_id"]})
    await db.roleplay_sessions.update_many({"kind": "mystery_shop", "enrollment_id": eid, "status": "scheduled"}, {"$set": {"status": "canceled", "fail_reason": "Removed from the course", "updated_at": datetime.now(timezone.utc)}})
    return {"ok": True}


@router.post("/enrollments/{eid}/shop-now")
async def enrollment_shop_now(eid: str, request: Request):
    """Call a mystery-shop person right now with their next un-passed challenge."""
    me = await _current(request)
    if me.get("role") not in OWNER_ROLES:
        raise HTTPException(status_code=403, detail="iMOS admins place shop calls")
    db = get_db()
    e = await db.course_enrollments.find_one({"_id": _oid(eid, "Enrollment"), "kind": "target"})
    if not e:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    c = await db.courses.find_one({"_id": ObjectId(e["course_id"])})
    live = await db.roleplay_sessions.find_one({"kind": "mystery_shop", "target_id": e["target_id"], "status": {"$in": ["dialing", "live", "grading"]}})
    if live:
        raise HTTPException(status_code=409, detail=f"{e.get('name')} is already on a shop call")
    await db.roleplay_sessions.update_many({"kind": "mystery_shop", "enrollment_id": eid, "status": "scheduled"}, {"$set": {"status": "canceled", "fail_reason": "Replaced by a call now", "updated_at": datetime.now(timezone.utc)}})
    call = await cs.schedule_next_shop(db, e, c, immediate=True)
    if not call:
        raise HTTPException(status_code=400, detail="Nothing left to shop, or the person or client is missing")
    ok = await ms.dial_now(db, call)
    s = await db.roleplay_sessions.find_one({"_id": call["_id"]})
    if not ok:
        raise HTTPException(status_code=503, detail=s.get("fail_reason") or "The call could not be placed")
    return ms.serialize_call(s)


# ---------------------------------------------------------------- public certificate
@public_router.get("/certificate/{token}")
async def public_certificate(token: str):
    db = get_db()
    e = await db.course_enrollments.find_one({"certificate_token": token, "status": "certified"}) if len(token or "") >= 16 else None
    if not e:
        raise HTTPException(status_code=404, detail="Certificate not found")
    c = await db.courses.find_one({"_id": ObjectId(e["course_id"])})
    if not c:
        raise HTTPException(status_code=404, detail="Certificate not found")
    return cs.public_certificate(e, c, await cs.challenges_for(db, c))
