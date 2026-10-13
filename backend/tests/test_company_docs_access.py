"""Company Docs authorization + tenant isolation + sync safety (security hotfix Oct 13 2026). Live preview API + preview Mongo.
    cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && python -m pytest tests/test_company_docs_access.py -q
Accounts (passwords from memory/test_credentials.md via tests/qa_creds.py): super admin forest, QA org admin (TEST_Store_Org),
QA store manager (forest's store = a different org), rep activation-tester. No credential value is asserted or printed."""
import asyncio
import os
import tempfile
import uuid

import pytest
import requests
from pymongo import MongoClient

from tests.qa_creds import password_for

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
SUPER, ORG_ADMIN, MANAGER, REP = "forest@imosapp.com", "qa-orgadmin@invalid.imonsocial.test", "qa-manager@invalid.imonsocial.test", "activation-tester@invalid.imonsocial.test"
RESTRICTED_SLUGS = {"imos-prd-working-log", "product-requirements-document", "imos-app-scope", "imos-tech-stack", "imos-operations-manual"}
S: dict = {}


def _login(email):
    r = requests.post(f"{API}/api/auth/login", json={"email": email, "password": password_for(email)}, timeout=30)
    assert r.status_code == 200, f"login {email}: {r.status_code}"
    d = r.json()
    return {"Authorization": f"Bearer {d.get('access_token') or d.get('token')}", "X-User-ID": d["user"]["_id"]}, d["user"]


def api(method, path, headers=None, **kw):
    r = requests.request(method, f"{API}/api{path}", headers=headers or {}, timeout=60, **kw)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, r.text


@pytest.fixture(scope="module", autouse=True)
def setup():
    S["mongo"] = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    for key, email in (("super", SUPER), ("org_admin", ORG_ADMIN), ("manager", MANAGER), ("rep", REP)):
        S[key], S[key + "_user"] = _login(email)
    assert S["org_admin_user"].get("organization_id") != S["manager_user"].get("organization_id"), "tenant check needs two different orgs"
    st, docs = api("GET", "/docs/", S["super"])
    assert st == 200
    S["by_slug"] = {d.get("slug"): d for d in docs if d.get("slug")}
    S["open_doc"] = next(d for d in docs if d.get("category") in ("legal", "integrations", "training", "company_policy", "security") and d.get("required_role") != "super_admin")
    yield
    S["mongo"].company_docs.delete_many({"slug": {"$regex": "^qa-sync-gate-"}})


# ── authorization: who can read what ────────────────────────────────────────────────────────────────────────────────────────
def test_super_admin_keeps_full_access():
    assert RESTRICTED_SLUGS <= set(S["by_slug"]), "all internal docs listed for the super admin"
    for slug in RESTRICTED_SLUGS:
        assert S["by_slug"][slug]["required_role"] == "super_admin"
        st, doc = api("GET", f"/docs/{S['by_slug'][slug]['_id']}", S["super"])
        assert st == 200 and len(doc.get("content") or "") > 100, slug
    assert api("GET", "/docs/prd", S["super"])[0] == 200
    assert api("GET", f"/docs/{S['by_slug']['imos-prd-working-log']['_id']}/export-pdf", S["super"])[0] == 200


@pytest.mark.parametrize("who", ["org_admin", "manager"])
def test_admin_roles_cannot_reach_internal_docs(who):
    h = S[who]
    st, docs = api("GET", "/docs/", h)
    assert st == 200 and docs, "legitimate docs still listed"
    listed = {d.get("slug") for d in docs}
    assert not (listed & RESTRICTED_SLUGS), f"{who} sees internal docs: {listed & RESTRICTED_SLUGS}"
    assert all(d.get("category") not in ("prd", "operations") and d.get("required_role") != "super_admin" for d in docs)
    for slug in RESTRICTED_SLUGS:
        assert api("GET", f"/docs/{S['by_slug'][slug]['_id']}", h)[0] == 403, f"{who} direct read of {slug}"
    assert api("GET", f"/docs/{S['by_slug']['imos-prd-working-log']['_id']}/export-pdf", h)[0] == 403
    assert api("POST", f"/docs/{S['by_slug']['imos-prd-working-log']['_id']}/email-pdf", h)[0] == 403
    assert api("GET", "/docs/prd", h)[0] == 403 and api("GET", "/docs/prd/pdf", h)[0] == 403
    assert api("PUT", "/docs/prd", h, json={"content": "# x"})[0] == 403
    assert api("GET", "/docs/?category=prd", h)[0] == 403 and api("GET", "/docs/?category=operations", h)[0] == 403
    st, cats = api("GET", "/docs/categories", h)
    assert st == 200 and not ({c["id"] for c in cats} & {"prd", "operations"}), "restricted category tabs are not offered"
    st, found = api("GET", "/docs/?search=PRD", h)
    assert st == 200 and not ({d.get("slug") for d in found} & RESTRICTED_SLUGS), "search cannot surface internal docs"
    # legitimate documentation keeps working (and the two admins live in different orgs: same global library, no cross-org leak)
    st, doc = api("GET", f"/docs/{S['open_doc']['_id']}", h)
    assert st == 200 and doc["title"] == S["open_doc"]["title"]


def test_rep_and_anonymous_and_header_spoof():
    wl = S["by_slug"]["imos-prd-working-log"]["_id"]
    assert api("GET", "/docs/", S["rep"])[0] == 403 and api("GET", f"/docs/{wl}", S["rep"])[0] == 403 and api("GET", "/docs/prd", S["rep"])[0] == 403
    assert api("GET", "/docs/")[0] == 401 and api("GET", f"/docs/{wl}")[0] == 401 and api("GET", "/docs/prd")[0] == 401
    # X-User-ID alone (no bearer) must not act as the super admin
    assert api("GET", f"/docs/{wl}", {"X-User-ID": S["super"]["X-User-ID"]})[0] == 401
    # a manager's bearer with the super admin's X-User-ID must not escalate
    assert api("GET", f"/docs/{wl}", {"Authorization": S["manager"]["Authorization"], "X-User-ID": S["super"]["X-User-ID"]})[0] in (401, 403)


# ── no credentials published, AI retrieval excludes internal docs ──────────────────────────────────────────────────────────
def test_published_docs_contain_no_credentials():
    from services.doc_access import credential_hits
    bad = [d.get("slug") or d.get("title") for d in S["mongo"].company_docs.find({"is_published": True}, {"slug": 1, "title": 1, "content": 1}) if credential_hits(d.get("content") or "")]
    assert bad == [], f"credential-like text published in: {bad}"
    assert credential_hits(open("/app/memory/PRD.md").read()) == 0, "repo PRD.md must stay free of credential literals"


def test_ai_retrieval_skips_internal_docs():
    from motor.motor_asyncio import AsyncIOMotorClient
    from services.leadership import knowledge
    from services.doc_access import is_restricted

    async def run():
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        _, index = await knowledge.doc_passages(db, "PRD working log full build history engineering deploy backend frontend tests")
        restricted_titles = {d["title"] for d in S["mongo"].company_docs.find({}, {"title": 1, "category": 1, "required_role": 1}) if is_restricted(d)}
        return set(index.values()), restricted_titles

    used, restricted = asyncio.run(run())
    assert not (used & restricted), f"restricted docs reached the prompt: {used & restricted}"


# ── sync safety: a repo file with a credential is never published, a stale copy is not kept ────────────────────────────────
def test_sync_withholds_credential_like_content_and_replaces_stale_copy():
    from routers import docs as docs_router

    slug = f"qa-sync-gate-{uuid.uuid4().hex[:6]}"
    S["mongo"].company_docs.insert_one({"slug": slug, "title": "QA gate", "category": "operations", "content": "# old copy that must not survive", "is_published": True, "synced_hash": "x"})
    leaked = "# Ops\n\nLogin: someone@example.com / " + "Qa" + "Temp" + "123!" + "\n"  # built in pieces so no literal credential sits in this file
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(leaked)
    original = docs_router.REPO_DOC_SOURCES
    tech = next(src for src in original if src[1]["slug"] == "imos-tech-stack")
    S["mongo"].company_docs.update_one({"slug": "imos-tech-stack"}, {"$unset": {"required_role": ""}})  # a stored copy that predates the rule (production has such rows)
    docs_router.REPO_DOC_SOURCES = [(f.name, {"slug": slug, "title": "QA gate", "summary": "qa", "category": "operations", "icon": "book", "sort_order": 9, "required_role": "super_admin"}), tech]
    try:
        out = asyncio.run(docs_router.sync_repo_docs())
    finally:
        docs_router.REPO_DOC_SOURCES = original
        os.unlink(f.name)
    assert out["withheld"] == 1 and out["synced"] == 0
    assert S["mongo"].company_docs.find_one({"slug": "imos-tech-stack"})["required_role"] == "super_admin", "hash shortcut still stamps required_role on unchanged docs"
    stored = S["mongo"].company_docs.find_one({"slug": slug})
    assert stored["is_published"] is False and "withheld" in stored["content"].lower() and "old copy" not in stored["content"] and "123!" not in stored["content"]
    assert stored["required_role"] == "super_admin"
    # withheld docs are invisible even to the super admin list and unreadable by admins
    st, docs = api("GET", "/docs/", S["super"])
    assert slug not in {d.get("slug") for d in docs}
    assert api("GET", f"/docs/{stored['_id']}", S["manager"])[0] == 403
