"""End-to-end test: Sold workflow triggered by Sold tag."""
import requests, json, os, sys
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime

API = os.environ.get("API_URL")
UID = os.environ.get("USER_ID")
headers = {"X-User-ID": UID, "Content-Type": "application/json"}

client = MongoClient("mongodb://localhost:27017")
db = client["imos-admin-test_database"]

# Get Calendar Systems partner ID
partner = db.white_label_partners.find_one({"slug": "calendar-systems"})
partner_id = str(partner["_id"])
print(f"Partner: {partner['name']} ({partner_id})")

# Create a test org linked to Calendar Systems
org_id = ObjectId()
db.organizations.insert_one({
    "_id": org_id,
    "name": "Test CS Org",
    "partner_id": partner_id,
    "created_at": datetime.utcnow(),
})
print(f"Created org: {org_id}")

# Create a test store linked to org with external_account_id
store_id = ObjectId()
db.stores.insert_one({
    "_id": store_id,
    "name": "Test CS Store",
    "organization_id": str(org_id),
    "partner_id": partner_id,
    "external_account_id": "CS-ACCT-001",
    "deal_or_stock_mode": "stock_number",
    "created_at": datetime.utcnow(),
})
print(f"Created store: {store_id}")

# Assign user to this store/org
db.users.update_one(
    {"_id": ObjectId(UID)},
    {"$set": {"store_id": str(store_id), "organization_id": str(org_id)}}
)
print(f"Assigned user to store/org")

# Create a contact WITHOUT sold tag
print("\n=== TEST 1: Create contact without sold tag ===")
r = requests.post(f"{API}/api/contacts/{UID}", json={
    "first_name": "SoldTest",
    "last_name": "Contact",
    "phone": "5559876543",
    "tags": ["New Customer"],
}, headers=headers)
contact = r.json()
contact_id = contact.get("_id", "")
print(f"  Contact created: {r.status_code}, id={contact_id}")

# Apply Sold tag via PATCH
print("\n=== TEST 2: Apply 'Sold' tag via PATCH ===")
r = requests.patch(f"{API}/api/contacts/{UID}/{contact_id}/tags", json={
    "tags": ["New Customer", "Sold"],
}, headers=headers)
result = r.json()
print(f"  Status: {r.status_code}")
print(f"  sold_workflow: {json.dumps(result.get('sold_workflow'), indent=2)}")

# Check contact fields
contact_doc = db.contacts.find_one({"_id": ObjectId(contact_id)})
print(f"\n=== Contact sold fields ===")
print(f"  sold_workflow_status: {contact_doc.get('sold_workflow_status')}")
print(f"  sold_tag_applied_at: {contact_doc.get('sold_tag_applied_at')}")
print(f"  date_sold: {contact_doc.get('date_sold')}")
print(f"  missing_fields: {contact_doc.get('sold_validation_missing_fields')}")

# Check event log
event = db.sold_event_logs.find_one({"contact_id": contact_id})
print(f"\n=== Sold Event Log ===")
if event:
    print(f"  validation_status: {event.get('validation_status')}")
    print(f"  missing_fields: {event.get('missing_fields')}")
    print(f"  delivery_status: {event.get('delivery_status')}")
    print(f"  trigger_source: {event.get('trigger_source')}")
else:
    print(f"  ERROR: No event log!")

# Fix missing fields and revalidate
print("\n=== TEST 3: Fix fields and revalidate ===")
db.contacts.update_one(
    {"_id": ObjectId(contact_id)},
    {"$set": {
        "full_size_image_url": "https://example.com/test-image.jpg",
        "stock_number": "STK-12345",
    }}
)
r = requests.post(f"{API}/api/sold-workflow/revalidate/{contact_id}", headers=headers)
result = r.json()
print(f"  Revalidate: {r.status_code}")
print(f"  Result: {json.dumps(result, indent=2)}")

contact_doc = db.contacts.find_one({"_id": ObjectId(contact_id)})
print(f"  Status after: {contact_doc.get('sold_workflow_status')}")

# Test idempotency
print("\n=== TEST 4: Idempotency ===")
old_event_count = db.sold_event_logs.count_documents({"contact_id": contact_id})
r = requests.patch(f"{API}/api/contacts/{UID}/{contact_id}/tags", json={
    "tags": ["New Customer", "Sold"],
}, headers=headers)
new_event_count = db.sold_event_logs.count_documents({"contact_id": contact_id})
print(f"  Events before: {old_event_count}, after: {new_event_count}")
print(f"  {'PASS (no duplicate)' if old_event_count == new_event_count else 'FAIL (duplicate created)'}")

# Test status endpoint
print("\n=== TEST 5: Contact sold status ===")
r = requests.get(f"{API}/api/sold-workflow/contact/{contact_id}", headers=headers)
status = r.json()
print(f"  Events: {len(status.get('events', []))}")
print(f"  Has partner: {status.get('has_partner')}")
print(f"  Deal/stock mode: {status.get('deal_or_stock_mode')}")

# Cleanup
print("\n=== CLEANUP ===")
db.contacts.delete_one({"_id": ObjectId(contact_id)})
db.sold_event_logs.delete_many({"contact_id": contact_id})
db.campaign_pending_sends.delete_many({"contact_id": contact_id})
db.stores.delete_one({"_id": store_id})
db.organizations.delete_one({"_id": org_id})
db.users.update_one(
    {"_id": ObjectId(UID)},
    {"$unset": {"store_id": "", "organization_id": ""}}
)
print("Done!")
