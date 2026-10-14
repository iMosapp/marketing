"""Live adversarial probe: external webhook bound to its organisation. Preview-only.
Sets a temporary webhook_secret on ORG_B, then verifies:
 - creating a NEW user with role=super_admin and org_id='org_001' => created with role 'user' and organization_id = ORG_B
 - with store_id=STORE_A (belongs to a different org) => 400
 - targeting an EXISTING user outside ORG_B by email => 403, user unchanged
 - user-deleted for outside email => 'not_found', user still active
 - user-deleted for the created user => 'deleted'
Removes the secret + created user at the end.
"""
import uuid

import pytest
from bson import ObjectId

from tests._http import call
from tests.live_auth import ORG_B, STORE_A

OUTSIDE_EMAIL = "mjeast1985@gmail.com"
SECRET = "qa-hotfix3-webhook-secret-" + uuid.uuid4().hex[:8]


@pytest.fixture(scope="module")
def seeded_secret(mongo):
    org_oid = ObjectId(ORG_B)
    prev = mongo.organizations.find_one({"_id": org_oid}, {"webhook_secret": 1}) or {}
    mongo.organizations.update_one({"_id": org_oid}, {"$set": {"webhook_secret": SECRET}})
    yield SECRET
    if "webhook_secret" in prev:
        mongo.organizations.update_one({"_id": org_oid}, {"$set": {"webhook_secret": prev["webhook_secret"]}})
    else:
        mongo.organizations.update_one({"_id": org_oid}, {"$unset": {"webhook_secret": ""}})


def test_webhook_scoped_to_its_org(seeded_secret, mongo):
    H = {"X-Webhook-Secret": seeded_secret}
    created_email = f"qa-hotfix3-wh-{uuid.uuid4().hex[:8]}@example.com"
    try:
        # 1. Create NEW user: body says super_admin + org_001 => real org=ORG_B, role=user
        st, body = call("POST", "/api/webhooks/user-created", body={
            "external_id": "qa-" + uuid.uuid4().hex[:8],
            "email": created_email, "name": "QA Hotfix3 WH User",
            "role": "super_admin", "organization_id": "org_001",
        }, headers=H)
        assert st == 200, body
        user_doc = mongo.users.find_one({"email": created_email})
        assert user_doc is not None, "user not created"
        assert user_doc.get("role") == "user", f"webhook let caller pick role: {user_doc.get('role')}"
        assert str(user_doc.get("organization_id")) == ORG_B, user_doc.get("organization_id")

        # 2. Cross-org store_id => 400
        st, body = call("POST", "/api/webhooks/user-created", body={
            "external_id": "qa-" + uuid.uuid4().hex[:8],
            "email": f"qa-hotfix3-wh-rej-{uuid.uuid4().hex[:8]}@example.com",
            "name": "QA Reject", "store_id": STORE_A,
        }, headers=H)
        assert st == 400, f"cross-org store_id accepted: {st} {body}"

        # 3. Hit an existing OUTSIDE user => 403 and user unchanged
        before = mongo.users.find_one({"email": OUTSIDE_EMAIL}, {"role": 1, "organization_id": 1, "status": 1})
        assert before is not None
        st, body = call("POST", "/api/webhooks/user-created", body={
            "external_id": "qa-" + uuid.uuid4().hex[:8],
            "email": OUTSIDE_EMAIL, "name": "pwn", "role": "super_admin",
        }, headers=H)
        assert st == 403, f"outside user takeover: {st} {body}"
        after = mongo.users.find_one({"email": OUTSIDE_EMAIL}, {"role": 1, "organization_id": 1, "status": 1})
        assert before == after, "outside user was modified"

        # 4. user-deleted outside => not_found, still active
        st, body = call("POST", "/api/webhooks/user-deleted", body={"email": OUTSIDE_EMAIL}, headers=H)
        assert st == 200
        assert (body or {}).get("status") == "not_found", body
        outside = mongo.users.find_one({"email": OUTSIDE_EMAIL}, {"is_active": 1, "status": 1})
        assert outside.get("is_active") is True or outside.get("status") == "active"

        # 5. user-deleted for created => deleted
        st, body = call("POST", "/api/webhooks/user-deleted", body={"email": created_email}, headers=H)
        assert st == 200
        assert (body or {}).get("status") == "deleted", body
    finally:
        mongo.users.delete_one({"email": created_email})
