"""Remove QA customers created by the Stage 1 tests / founder walkthrough in preview.
Only organizations that carry `customer` AND whose name starts with the prefix are touched; legacy orgs are never read.
Run: cd /app/backend && set -a && . ./.env && set +a && python tests/wipe_pilot_customers.py [--prefix "QA Pilot"] [--dry-run]"""
import argparse
import os
import sys

from bson import ObjectId
from pymongo import MongoClient

USER_COLLECTIONS = ["templates", "email_templates", "campaigns", "date_trigger_configs", "review_response_templates", "social_templates", "tags", "contacts", "notifications",
                    "contact_events", "voice_notes", "bug_reports", "card_scans"]
STORE_COLLECTIONS = ["tags", "lead_sources", "congrats_card_templates", "setup_wizard_progress"]


def _stripe_cleanup(org: dict) -> None:
    """Best effort: delete the test-mode Stripe customer (which cancels its subscriptions) for a QA org."""
    cid = (org.get("customer") or {}).get("stripe_customer_id")
    if not cid or not os.environ.get("STRIPE_BILLING_SECRET_KEY"):
        return
    try:
        import stripe
        sc = stripe.StripeClient(os.environ["STRIPE_BILLING_SECRET_KEY"])
        if sc.v1.balance.retrieve().livemode:
            print("  live-mode key: Stripe objects left alone")
            return
        sc.v1.customers.delete(cid)
        print(f"  Stripe customer {cid} deleted")
    except Exception as e:
        print(f"  Stripe cleanup skipped: {type(e).__name__}")


def wipe(db, prefix: str, dry_run: bool) -> int:
    orgs = list(db.organizations.find({"customer": {"$exists": True}, "name": {"$regex": f"^{prefix}"}}, {"name": 1, "customer.stripe_customer_id": 1}))
    for org in orgs:
        org_id = str(org["_id"])
        users = list(db.users.find({"organization_id": org_id}, {"_id": 1, "email": 1}))
        user_ids = [str(u["_id"]) for u in users]
        stores = [str(s["_id"]) for s in db.stores.find({"organization_id": org_id}, {"_id": 1})]
        print(f"{'would remove' if dry_run else 'removing'} {org['name']} ({org_id}): {len(users)} users, {len(stores)} stores")
        if dry_run:
            continue
        _stripe_cleanup(org)
        db.stripe_events.delete_many({"organization_id": org_id})
        for coll in USER_COLLECTIONS:
            db[coll].delete_many({"user_id": {"$in": user_ids}})
        db.contacts.delete_many({"email": {"$in": [u.get("email") for u in users if u.get("email")]}, "source": "user_creation"})
        db.password_reset_tokens.delete_many({"user_id": {"$in": user_ids}})
        db.short_urls.delete_many({"link_type": "activation", "reference_id": {"$in": user_ids}})
        for coll in STORE_COLLECTIONS:
            db[coll].delete_many({"store_id": {"$in": stores}})
        db.setup_wizard_progress.delete_many({"organization_id": org_id})
        db.onboarding_clients.delete_many({"organization_id": org_id})
        db.customer_audit_log.delete_many({"organization_id": org_id})
        db.notifications.delete_many({"link": f"/admin/customers/{org_id}"})
        db.users.delete_many({"_id": {"$in": [ObjectId(u) for u in user_ids]}})
        db.stores.delete_many({"organization_id": org_id})
        db.organizations.delete_one({"_id": org["_id"]})
    return len(orgs)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="QA Pilot")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    client = MongoClient(os.environ["MONGO_URL"])
    n = wipe(client[os.environ["DB_NAME"]], args.prefix, args.dry_run)
    print(f"{n} customer org(s) matched prefix '{args.prefix}'")
    sys.exit(0)
