"""Courses & Certification: end-to-end admin CRUD, enrollment, RBAC (manager scope),
record_result -> certify path (simulated), public certificate, cleanup."""
import os
import time
import uuid
import pytest
import requests
from bson import ObjectId

BASE_URL = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/")
API = BASE_URL + "/api"


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    r.raise_for_status()
    d = r.json()
    u = d["user"]
    u["id"] = u.get("id") or u.get("_id")
    return d.get("token") or d.get("access_token"), u


@pytest.fixture(scope="module")
def admin():
    try:
        tok, u = _login("forest@imosapp.com", "Admin123!")
    except Exception:
        tok, u = _login("forest@imonsocial.com", "Admin123!")
    return {"tok": tok, "user": u, "H": {"Authorization": f"Bearer {tok}"}}


@pytest.fixture(scope="module")
def rep():
    tok, u = _login("activation-tester@invalid.imonsocial.test", "NewPass123!")
    return {"tok": tok, "user": u, "H": {"Authorization": f"Bearer {tok}"}}


@pytest.fixture(scope="module")
def mgr():
    tok, u = _login("qa-manager@invalid.imonsocial.test", "Manager123!")
    return {"tok": tok, "user": u, "H": {"Authorization": f"Bearer {tok}"}}


@pytest.fixture(scope="module")
def library_challenges(admin):
    r = requests.get(f"{API}/shop-clients/challenges", headers=admin["H"], timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    ch = d.get("challenges") or d.get("all") or []
    if not ch and isinstance(d, dict):
        for k in ("sales", "service", "parts", "rental"):
            ch += (d.get(k) or [])
    assert len(ch) >= 2, f"Need at least 2 library challenges, got {len(ch)}"
    return ch


@pytest.fixture(scope="module")
def course_ctx(admin, library_challenges):
    """Create a course + add 2 sales challenges; yields ctx and cleans up at end (course retire)."""
    ts = int(time.time())
    body = {"title": f"TEST_QA Course {ts}", "description": "QA created by tester", "department": "sales", "pass_pct": 80}
    r = requests.post(f"{API}/courses", headers=admin["H"], json=body, timeout=30)
    assert r.status_code == 200, r.text
    course = r.json()
    cid = course["id"]

    sales = [c for c in library_challenges if c.get("department") == "sales"][:2]
    if len(sales) < 2:
        sales = library_challenges[:2]
    ch_ids = [c["id"] for c in sales]

    r2 = requests.put(f"{API}/courses/{cid}", headers=admin["H"], json={"challenge_ids": ch_ids}, timeout=30)
    assert r2.status_code == 200, r2.text
    ctx = {"cid": cid, "challenge_ids": ch_ids, "course": r2.json()}
    yield ctx
    # cleanup: retire course
    try:
        requests.delete(f"{API}/courses/{cid}", headers=admin["H"], timeout=30)
    except Exception:
        pass


# ----- List / CRUD -----
def test_list_courses_shape(admin):
    r = requests.get(f"{API}/courses", headers=admin["H"], timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("courses", "can_manage", "can_assign", "my", "departments"):
        assert k in d, f"missing {k}"
    assert d["can_manage"] is True


def test_create_requires_title(admin):
    r = requests.post(f"{API}/courses", headers=admin["H"], json={"title": "  "}, timeout=30)
    assert r.status_code == 400


def test_create_invalid_department(admin):
    r = requests.post(f"{API}/courses", headers=admin["H"], json={"title": "TEST_x", "department": "bodyshop"}, timeout=30)
    assert r.status_code == 400


def test_get_course_and_stats(admin, course_ctx):
    r = requests.get(f"{API}/courses/{course_ctx['cid']}", headers=admin["H"], timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["course"]["id"] == course_ctx["cid"]
    assert d["course"]["pass_pct"] == 80
    assert len(d["challenges"]) == 2
    assert d["can_manage"] is True


def test_update_pass_pct(admin, course_ctx):
    r = requests.put(f"{API}/courses/{course_ctx['cid']}", headers=admin["H"], json={"pass_pct": 85}, timeout=30)
    assert r.status_code == 200
    assert r.json()["pass_pct"] == 85
    # revert
    requests.put(f"{API}/courses/{course_ctx['cid']}", headers=admin["H"], json={"pass_pct": 80}, timeout=30)


# ----- Manager RBAC -----
def test_manager_cannot_create(mgr):
    r = requests.post(f"{API}/courses", headers=mgr["H"], json={"title": "TEST_x"}, timeout=30)
    assert r.status_code == 403


def test_manager_cannot_edit(mgr, course_ctx):
    r = requests.put(f"{API}/courses/{course_ctx['cid']}", headers=mgr["H"], json={"pass_pct": 90}, timeout=30)
    assert r.status_code == 403


def test_manager_list_no_can_manage(mgr):
    r = requests.get(f"{API}/courses", headers=mgr["H"], timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["can_manage"] is False
    assert d["can_assign"] is True


def test_manager_people_no_targets(mgr, course_ctx):
    r = requests.get(f"{API}/courses/{course_ctx['cid']}/people", headers=mgr["H"], timeout=30)
    assert r.status_code == 200
    assert r.json()["targets"] == []


def test_rep_people_forbidden(rep, course_ctx):
    r = requests.get(f"{API}/courses/{course_ctx['cid']}/people", headers=rep["H"], timeout=30)
    assert r.status_code == 403


# ----- Enrollment -----
@pytest.fixture(scope="module")
def enrollment_rep(admin, rep, course_ctx):
    r = requests.post(f"{API}/courses/{course_ctx['cid']}/assign", headers=admin["H"],
                      json={"user_ids": [rep["user"]["id"]]}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["enrollments"]) == 1
    return d["enrollments"][0]


def test_enroll_rep_and_idempotent(admin, rep, course_ctx, enrollment_rep):
    assert enrollment_rep["kind"] == "user"
    assert enrollment_rep["user_id"] == rep["user"]["id"]
    assert enrollment_rep["status"] == "in_progress"
    assert enrollment_rep["total"] == 2
    # Re-assign same rep -> still 1 enrollment
    r = requests.post(f"{API}/courses/{course_ctx['cid']}/assign", headers=admin["H"],
                      json={"user_ids": [rep["user"]["id"]]}, timeout=30)
    assert r.status_code == 200
    # notified count should be 0 second time
    assert r.json()["notified"] == 0


def test_get_enrollment_detail(admin, enrollment_rep):
    r = requests.get(f"{API}/courses/enrollments/{enrollment_rep['id']}", headers=admin["H"], timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["enrollment"]["id"] == enrollment_rep["id"]
    assert "attempts" in d and "challenges" in d


def test_rep_sees_own_enrollment_in_list(rep, course_ctx):
    r = requests.get(f"{API}/courses", headers=rep["H"], timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert any(m["course_id"] == course_ctx["cid"] for m in d["my"])


def test_rep_can_view_course(rep, course_ctx):
    r = requests.get(f"{API}/courses/{course_ctx['cid']}", headers=rep["H"], timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["my_enrollment"] is not None
    assert d["can_manage"] is False


# ----- record_result -> certify (direct service call) -----
def test_record_result_certifies_and_public_certificate(admin, rep, course_ctx, enrollment_rep):
    """Simulate two graded passing sessions via services.courses.record_result, verify certification + public cert page."""
    import asyncio
    import sys
    sys.path.insert(0, "/app/backend")
    from motor.motor_asyncio import AsyncIOMotorClient
    from services import courses as cs

    mongo_url = [l.split("=", 1)[1].strip().strip('"') for l in open("/app/backend/.env") if l.startswith("MONGO_URL=")][0]
    db_name = [l.split("=", 1)[1].strip().strip('"') for l in open("/app/backend/.env") if l.startswith("DB_NAME=")][0]

    fake_session_ids = []

    async def run():
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        eid = enrollment_rep["id"]
        for cid in course_ctx["challenge_ids"]:
            sid = ObjectId()
            fake_session_ids.append(sid)
            await db.roleplay_sessions.insert_one({
                "_id": sid, "kind": "practice", "user_id": rep["user"]["id"],
                "script_id": cid, "enrollment_id": eid, "score_pct": 90,
                "status": "completed", "ended_at": None,
            })
            await cs.record_result(db, {"_id": sid, "enrollment_id": eid, "script_id": cid}, 90)
        client.close()

    asyncio.get_event_loop().run_until_complete(run()) if False else asyncio.new_event_loop().run_until_complete(run())

    # verify certification
    r = requests.get(f"{API}/courses/enrollments/{enrollment_rep['id']}", headers=admin["H"], timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    e = d["enrollment"]
    assert e["status"] == "certified", e
    assert e["certificate_token"], e
    assert e["certificate_url"] and "/certificate/" in e["certificate_url"]
    token = e["certificate_token"]

    # public certificate (no auth)
    r2 = requests.get(f"{API}/public/certificate/{token}", timeout=30)
    assert r2.status_code == 200, r2.text
    cert = r2.json()
    assert cert["name"]
    assert cert["course_title"] == course_ctx["course"]["title"]
    assert cert["badge_label"]
    assert len(cert["challenges"]) == 2
    assert all(c["best_pct"] == 90 for c in cert["challenges"])

    # invalid token -> 404
    r3 = requests.get(f"{API}/public/certificate/{'z' * 32}", timeout=30)
    assert r3.status_code == 404

    # notifications: rep + assigner (forest, who is both assigner AND may equal user for admin, but rep != admin here)
    import asyncio as _a
    from motor.motor_asyncio import AsyncIOMotorClient as _C
    async def check():
        client = _C(mongo_url); db = client[db_name]
        rn = await db.notifications.count_documents({"user_id": rep["user"]["id"], "type": "course_certified"})
        an = await db.notifications.count_documents({"user_id": admin["user"]["id"], "type": "course_certified"})
        # cleanup fake sessions + notifications from this test course
        await db.roleplay_sessions.delete_many({"_id": {"$in": fake_session_ids}})
        client.close()
        return rn, an
    rn, an = _a.new_event_loop().run_until_complete(check())
    assert rn >= 1, f"rep notification missing, got {rn}"
    assert an >= 1, f"assigner notification missing, got {an}"


# ----- Unenroll -----
def test_unenroll_removes_enrollment(admin, enrollment_rep, course_ctx):
    r = requests.delete(f"{API}/courses/enrollments/{enrollment_rep['id']}", headers=admin["H"], timeout=30)
    assert r.status_code == 200
    # confirm gone
    r2 = requests.get(f"{API}/courses/enrollments/{enrollment_rep['id']}", headers=admin["H"], timeout=30)
    assert r2.status_code == 404


# ----- Retire -----
def test_retire_course_returns_404_after(admin, course_ctx):
    r = requests.delete(f"{API}/courses/{course_ctx['cid']}", headers=admin["H"], timeout=30)
    assert r.status_code == 200
    r2 = requests.get(f"{API}/courses/{course_ctx['cid']}", headers=admin["H"], timeout=30)
    assert r2.status_code == 404
