"""Alerts center (notification-center) - action feed, dedupe, self-resolve, dismiss / undo / clear-all, auth.
Run: cd /app/backend && python -m pytest tests/test_alerts_center.py -q -p no:randomly
Seeds its own notifications/tasks for forest and removes them.
"""
import os
import time
import pytest
import requests
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
API = "http://127.0.0.1:8001/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
TAG = f"alerts-qa-{ObjectId()}"


@pytest.fixture(scope="module")
def admin():
    r = requests.post(f"{API}/auth/login", json={"email": "forest@imosapp.com", "password": "Admin123!"}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    return str(d["user"]["_id"] if "_id" in d["user"] else d["user"]["id"]), d["token"]


@pytest.fixture(scope="module")
def other():
    r = requests.post(f"{API}/auth/login", json={"email": "mjeast1985@gmail.com", "password": "NavyBean1!"}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    return str(d["user"]["_id"] if "_id" in d["user"] else d["user"]["id"]), d["token"]


def H(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def seed(admin):
    uid, _ = admin
    now = datetime.now(timezone.utc)
    conv_replied = ObjectId()
    conv_open = ObjectId()
    contact = DB.contacts.insert_one({"user_id": uid, "first_name": "Alerts", "last_name": "QA", "phone": "+15005550006",
                                      "tags": [TAG], "created_at": now}).inserted_id
    notifs = [
        # duplicate new_lead x3 -> one row
        {"user_id": uid, "type": "new_lead", "title": "New Lead: Dup Lead", "message": "Dup Lead submitted a form via homepage.",
         "contact_name": "Dup Lead", "conversation_id": str(conv_open), "read": False, "dismissed": False, "created_at": now - timedelta(minutes=i), "qa": TAG}
        for i in range(3)
    ] + [
        # customer_reply already answered by the rep -> auto resolved
        {"user_id": uid, "type": "customer_reply", "title": "Replied", "message": "ok sounds good", "contact_name": "Answered Person",
         "conversation_id": str(conv_replied), "read": False, "dismissed": False, "created_at": now - timedelta(minutes=30), "qa": TAG},
        # you_are_needed still open -> NOW bucket, Reply action to the thread
        {"user_id": uid, "type": "you_are_needed", "title": "You're needed", "message": "Is the Tacoma still there?", "contact_name": "Needy Customer",
         "conversation_id": str(conv_open), "contact_id": str(contact), "read": False, "dismissed": False, "created_at": now - timedelta(minutes=2), "qa": TAG},
        # activity-type notification must NOT be in the action feed
        {"user_id": uid, "type": "date_trigger", "title": "Birthday text sent", "message": "auto", "read": False, "dismissed": False,
         "created_at": now - timedelta(minutes=1), "qa": TAG},
    ]
    ids = DB.notifications.insert_many(notifs).inserted_ids
    DB.messages.insert_one({"conversation_id": str(conv_replied), "sender": "user", "content": "Yes! Still here.",
                            "timestamp": now - timedelta(minutes=10), "qa": TAG})
    task = DB.tasks.insert_one({"user_id": uid, "contact_id": str(contact), "contact_name": "Alerts QA", "type": "call",
                                "title": "Call Alerts QA about the Tacoma", "due_date": now - timedelta(days=2), "status": "pending",
                                "completed": False, "created_at": now, "qa": TAG}).inserted_id
    yield {"uid": uid, "notif_ids": ids, "task_id": str(task), "conv_open": str(conv_open), "contact": str(contact)}
    DB.notifications.delete_many({"qa": TAG})
    DB.messages.delete_many({"qa": TAG})
    DB.tasks.delete_many({"qa": TAG})
    DB.contacts.delete_one({"_id": contact})
    DB.notification_reads.update_one({"user_id": uid}, {"$pull": {"dismissed_ids": f"task_{task}", "read_ids": f"task_{task}"}})


def feed(uid, token):
    # bust the 30s server cache so seeded data is visible immediately
    requests.post(f"{API}/notification-center/{uid}/read", json={"ids": []}, headers=H(token), timeout=30)
    r = requests.get(f"{API}/notification-center/{uid}?limit=200", headers=H(token), timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


class TestAuth:
    def test_unauthenticated_401(self, admin):
        uid, _ = admin
        assert requests.get(f"{API}/notification-center/{uid}", timeout=30).status_code == 401

    def test_other_user_403(self, admin, other):
        uid, _ = admin
        _, tok = other
        assert requests.get(f"{API}/notification-center/{uid}", headers=H(tok), timeout=30).status_code == 403
        assert requests.post(f"{API}/notification-center/{uid}/clear-all", headers=H(tok), timeout=30).status_code == 403


class TestActionFeed:
    def test_verb_titles_buckets_and_actions(self, admin, seed):
        uid, tok = admin
        d = feed(uid, tok)
        items = d["notifications"]
        by_type = {}
        for n in items:
            by_type.setdefault(n["type"], []).append(n)
        needy = [n for n in by_type.get("you_are_needed", []) if n.get("contact_name") == "Needy Customer"]
        assert len(needy) == 1
        n = needy[0]
        assert n["title"] == "Reply to Needy Customer"
        assert n["bucket"] == "now"
        assert n["action"]["label"] == "Reply" and n["action"]["link"] == f"/thread/{seed['conv_open']}"
        assert n["context"] == "Is the Tacoma still there?"
        assert "bucket_counts" in d and d["bucket_counts"]["now"] >= 1

    def test_duplicates_collapse(self, admin, seed):
        uid, tok = admin
        dups = [n for n in feed(uid, tok)["notifications"] if n.get("contact_name") == "Dup Lead"]
        assert len(dups) == 1
        assert dups[0]["title"] == "Respond to Dup Lead"
        assert dups[0]["context"] == "Submitted a form via homepage"

    def test_answered_reply_auto_resolves(self, admin, seed):
        uid, tok = admin
        assert not [n for n in feed(uid, tok)["notifications"] if n.get("contact_name") == "Answered Person"]
        doc = DB.notifications.find_one({"qa": TAG, "type": "customer_reply"})
        assert doc["dismissed"] is True and doc.get("auto_resolved") is True

    def test_activity_types_hidden_from_action_feed(self, admin, seed):
        uid, tok = admin
        assert not [n for n in feed(uid, tok)["notifications"] if n["type"] == "date_trigger"]
        act = requests.get(f"{API}/notification-center/{uid}?feed=activity", headers=H(tok), timeout=30).json()
        assert [n for n in act["notifications"] if n["type"] == "date_trigger"]

    def test_overdue_call_task_becomes_call_action(self, admin, seed):
        uid, tok = admin
        rows = [n for n in feed(uid, tok)["notifications"] if n["id"] == f"task_{seed['task_id']}"]
        assert len(rows) == 1
        t = rows[0]
        assert t["title"] == "Call Alerts QA"
        assert t["bucket"] == "today"
        assert t["action"]["label"] == "Call"
        assert t["action"]["link"].startswith("/call-screen?") and f"task_id={seed['task_id']}" in t["action"]["link"]
        assert t["context"].startswith("Overdue 2d")


class TestDismiss:
    def test_dismiss_and_undo_real_and_virtual(self, admin, seed):
        uid, tok = admin
        ids = [n["id"] for n in feed(uid, tok)["notifications"] if n.get("contact_name") == "Needy Customer"]
        ids.append(f"task_{seed['task_id']}")
        r = requests.post(f"{API}/notification-center/{uid}/dismiss", json={"ids": ids}, headers=H(tok), timeout=30)
        assert r.status_code == 200 and r.json()["dismissed"] == 2
        left = {n["id"] for n in feed(uid, tok)["notifications"]}
        assert not (set(ids) & left)
        # the task itself is untouched
        assert DB.tasks.find_one({"_id": ObjectId(seed["task_id"])})["completed"] is False
        r = requests.post(f"{API}/notification-center/{uid}/undismiss", json={"ids": ids}, headers=H(tok), timeout=30)
        assert r.status_code == 200 and r.json()["restored"] == 2
        back = {n["id"] for n in feed(uid, tok)["notifications"]}
        assert set(ids) <= back

    def test_clear_all_then_undo(self, admin, seed):
        uid, tok = admin
        before = feed(uid, tok)
        assert before["total"] > 0
        r = requests.post(f"{API}/notification-center/{uid}/clear-all", headers=H(tok), timeout=30)
        assert r.status_code == 200
        cleared_ids = r.json()["ids"]
        assert r.json()["cleared"] == before["total"] == len(cleared_ids)
        after = feed(uid, tok)
        assert after["total"] == 0 and after["unread_count"] == 0
        r = requests.post(f"{API}/notification-center/{uid}/undismiss", json={"ids": cleared_ids}, headers=H(tok), timeout=30)
        assert r.status_code == 200
        restored = feed(uid, tok)
        assert restored["total"] == before["total"]
