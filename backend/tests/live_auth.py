"""Shared live-API auth fixtures for the preview backend (REACT_APP_BACKEND_URL).
Every request carries a real Bearer JWT; bare X-User-ID has not been accepted since the Sep 27 2026 hardening."""
import os

import pytest
from bson import ObjectId
from pymongo import MongoClient

from tests._http import API, auth, call, login

SUPER_ADMIN = ("forest@imosapp.com", "Admin123!")
STORE_MANAGER = ("qa-manager@invalid.imonsocial.test", "Manager123!")      # store_manager on STORE_A
ORG_ADMIN = ("qa-orgadmin@invalid.imonsocial.test", "OrgAdmin123!")        # org_admin on ORG_B / STORE_B
REP = ("mjeast1985@gmail.com", "NavyBean1!")                               # role user, no store

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

    def delete(self, path):
        return call("DELETE", path, headers=self.headers)


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
