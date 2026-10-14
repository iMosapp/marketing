"""Shared live-API auth fixtures for the preview backend (REACT_APP_BACKEND_URL).
Every request carries a real Bearer JWT; bare X-User-ID has not been accepted since the Sep 27 2026 hardening."""
import os

import pytest
from bson import ObjectId
from pymongo import MongoClient

from tests._http import API, auth, call, login
from tests import qa_creds

SUPER_ADMIN = ("forest@imosapp.com", qa_creds.password_for("forest@imosapp.com"))
STORE_MANAGER = ("qa-manager@invalid.imonsocial.test", qa_creds.password_for("qa-manager@invalid.imonsocial.test"))      # store_manager on STORE_A
ORG_ADMIN = ("qa-orgadmin@invalid.imonsocial.test", qa_creds.password_for("qa-orgadmin@invalid.imonsocial.test"))        # org_admin on ORG_B / STORE_B
REP = ("mjeast1985@gmail.com", qa_creds.password_for("mjeast1985@gmail.com"))                               # role user, no store

STORE_A = "69a0b7095fddcede09591668"
ORG_B = "69a907033b77512d1d8d8a08"
STORE_B = "69a907033b77512d1d8d8a09"

BASE = API


class Session:
    """A logged-in caller: .get/.post/... return (status, body)."""

    def __init__(self, email, password):
        self.email = email
        self.token, self.user_id = login(email, password)
        self.headers = auth(self.token, self.user_id)

    def get(self, path):
        return call("GET", path, headers=self.headers)

    def post(self, path, body=None):
        return call("POST", path, body if body is not None else {}, self.headers)

    def put(self, path, body=None):
        return call("PUT", path, body if body is not None else {}, self.headers)

    def patch(self, path, body=None):
        return call("PATCH", path, body if body is not None else {}, self.headers)

    def delete(self, path, body=None):
        return call("DELETE", path, body, self.headers)


def anon(method, path, body=None):
    return call(method, path, body)


@pytest.fixture(scope="session")
def super_admin():
    return Session(*SUPER_ADMIN)


@pytest.fixture(scope="session")
def store_manager():
    return Session(*STORE_MANAGER)


@pytest.fixture(scope="session")
def org_admin():
    return Session(*ORG_ADMIN)


@pytest.fixture(scope="session")
def rep():
    return Session(*REP)


@pytest.fixture(scope="session")
def mongo():
    client = MongoClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]]


def oid(value):
    return ObjectId(value)


def ensure_qa_user(mongo, email, role, org_id, store_id, name):
    """A QA account that exists only in preview; its password lives in the gitignored credentials file. Returns (email, password)."""
    from datetime import datetime
    from routers.auth import hash_password
    from tests import qa_creds
    pw = qa_creds.password_for(email)
    base = {"email": email, "name": name, "role": role, "organization_id": org_id, "store_id": store_id, "status": "active",
            "is_active": True, "onboarding_complete": True, "password": hash_password(pw)}
    doc = mongo.users.find_one({"email": email})
    if not doc:
        mongo.users.insert_one({**base, "created_at": datetime.utcnow()})
    else:
        mongo.users.update_one({"_id": doc["_id"]}, {"$set": base})
    return email, pw
