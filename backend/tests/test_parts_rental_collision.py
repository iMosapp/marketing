"""Parts, Rental and Body Shop (collision) are real mystery shop departments for automotive accounts: starter challenges exist for
each, the scorecard template resolves, the persona reads naturally, and plans / proposals / kickoff / report all carry the five departments."""
import asyncio
import os

import pytest
import requests
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from services import industries as ind
from services import mystery_shops as ms
from services import scorecards as sc

BASE_URL = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/")
API = BASE_URL + "/api"
NEW_DEPTS = ["parts", "rental", "collision"]


def _db():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def admin():
    r = requests.post(f"{API}/auth/login", json={"email": "forest@imosapp.com", "password": "Admin123!"}, timeout=30)
    r.raise_for_status()
    tok = r.json().get("token") or r.json().get("access_token")
    return {"Authorization": f"Bearer {tok}"}


def test_pack_departments_and_templates():
    assert ind.dept_keys("automotive") == ["sales", "service", "parts", "rental", "collision"]
    assert ind.dept_label("collision") == "Body Shop"
    for d in NEW_DEPTS:
        card = ms.template_card(d)
        assert card and len(card["criteria"]) >= 8, d
        assert any(c["critical"] for c in card["criteria"])
    assert "Body Shop" in sc.DEPARTMENTS
    assert next(t for t in sc.TEMPLATES if t["key"] == "collision_phone")["name"] == "Body Shop Call"


def test_starters_cover_every_department():
    by_dept = {}
    for t in ms.STARTER_CHALLENGES:
        by_dept.setdefault(t["department"], []).append(t)
    for d in NEW_DEPTS:
        assert len(by_dept.get(d, [])) >= 3, d
        for t in by_dept[d]:
            assert t["persona"]["opening_line"] and len(t["success_points"]) >= 5 and "{vehicle}" in (t["persona"]["summary"] + t["persona"]["opening_line"])
    assert len({t["slug"] for t in ms.STARTER_CHALLENGES}) == len(ms.STARTER_CHALLENGES)


def test_persona_reads_naturally_per_department():
    client = {"industry": "automotive", "name": "QA Motors", "vehicles": ["2024 Jeep Grand Cherokee"]}
    for d, lead in (("collision", "my "), ("parts", "my "), ("service", "my "), ("rental", "a "), ("sales", "the ")):
        p = ms.fill_persona({"opening_line": "Hi, about {vehicle} at {store}"}, client, d)
        assert p["opening_line"].startswith(f"Hi, about {lead}2024 Jeep"), (d, p["opening_line"])
        assert "QA Motors" in p["opening_line"]


def test_pool_and_pick_for_new_departments():
    async def run():
        db = _db()
        await ms.ensure_challenges(db)
        for d in NEW_DEPTS:
            pool = await ms.challenge_pool(db, None, d)
            assert len(pool) >= 3, d
            assert all(s.get("industry") == "automotive" and s.get("pool") == "mystery_shop" for s in pool)
            picked = await ms.pick_challenge(db, {"_id": ObjectId(), "industry": "automotive"}, {"department": d, "challenge_history": []})
            assert picked and picked["department"] == d
    asyncio.run(run())


def test_client_plan_proposal_kickoff_report_carry_five_departments(admin):
    r = requests.post(f"{API}/shop-clients", headers=admin, timeout=30, json={"name": "QA Five Depts", "industry": "automotive", "contact_name": "GM", "contact_email": "gm@invalid.imonsocial.test",
                                                                             "plan": {"per_month": {"sales": 4, "service": 2, "parts": 2, "rental": 1, "collision": 1}, "price_monthly": 500}})
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    try:
        d = requests.get(f"{API}/shop-clients/{cid}", headers=admin, timeout=30).json()
        assert d["client"]["plan"]["per_month"] == {"sales": 4, "service": 2, "parts": 2, "rental": 1, "collision": 1}
        assert [x["key"] for x in d["departments"]] == ["sales", "service", "parts", "rental", "collision"]
        # people can be added in every department
        for i, dept in enumerate(NEW_DEPTS):
            p = requests.post(f"{API}/shop-clients/{cid}/people", headers=admin, timeout=30, json={"name": f"QA {dept.title()}", "phone": f"+1500555{600 + i:04d}", "department": dept})
            assert p.status_code == 200 and p.json()["department"] == dept, p.text
        # proposal terms keep all five
        pr = requests.post(f"{API}/shop-clients/{cid}/proposals", headers=admin, timeout=30, json={"per_month": {"sales": 4, "service": 2, "parts": 2, "rental": 1, "collision": 1}, "price_monthly": 500, "term_months": 3})
        assert pr.status_code == 200, pr.text
        pub = requests.get(f"{API}/public/proposal/{pr.json()['token']}", timeout=30).json()
        assert pub["per_month"]["collision"] == 1 and any(x["key"] == "collision" for x in pub["departments"])
        assert "4 sales, 2 service, 2 parts, 1 rental and 1 body shop" in " ".join(s["body"] for s in pub["sections"])
        # kickoff form lists the five departments
        k = requests.get(f"{API}/public/shop-kickoff/{d['kickoff_url'].rsplit('/', 1)[-1]}", timeout=30).json()
        assert [x["key"] for x in k["departments"]] == ["sales", "service", "parts", "rental", "collision"]
        # report carries a card per planned department
        rep = requests.get(f"{API}/shop-clients/{cid}/report", headers=admin, timeout=30).json()
        bd = rep.get("by_department") or rep.get("report", {}).get("by_department")
        assert set(NEW_DEPTS) <= set(bd) and bd["collision"]["label"] == "Body Shop" and bd["collision"]["planned"] == 1
    finally:
        requests.delete(f"{API}/shop-clients/{cid}", headers=admin, timeout=30)
