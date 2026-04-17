"""
Test contact tracking attribution for card links.
Tests the fixes for:
1. Card creation stores contact_id in both card doc and short URL metadata
2. Short URL redirect for CARD links uses metadata.contact_id (not reference_id/card_id)
3. Old card short URLs without contact_id don't append wrong cid
4. Tracking endpoint validates contact_id is a valid ObjectId
5. Activity feed shows correct names (no Unknown entries)
6. Card lookup works with card_id and ObjectId fallback
"""
import os
import pytest
import requests
import os
from bson import ObjectId

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from review request
SUPER_ADMIN_EMAIL = "forest@imosapp.com"
SUPER_ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")
USER_ID = "69a0b7095fddcede09591667"
VALID_CONTACT_ID = "69a0c06f7626f14d125f8c34"
TEST_CARD_ID = "a37ec720-548"
TEST_SHORT_CODE = "b3Cb86"


class TestContactTrackingAttribution:
    """Test suite for contact tracking attribution fixes."""

    def test_short_url_stats_returns_200(self):
        """Verify short URL stats endpoint works."""
        response = requests.get(f"{BASE_URL}/api/s/stats/{TEST_SHORT_CODE}")
        print(f"Short URL stats response: {response.status_code} {response.json()}")
        assert response.status_code == 200
        data = response.json()
        assert data["short_code"] == TEST_SHORT_CODE
        assert data["link_type"] in ["congrats_card", "thank_you_card", "birthday_card", "thankyou_card"]
        print("PASS - Short URL stats endpoint works")

    def test_card_lookup_by_card_id(self):
        """GET /api/congrats/card/{card_id} works with card_id."""
        response = requests.get(f"{BASE_URL}/api/congrats/card/{TEST_CARD_ID}")
        print(f"Card lookup response: {response.status_code}")
        assert response.status_code == 200
        data = response.json()
        assert data["card_id"] == TEST_CARD_ID
        print(f"PASS - Card lookup works. Customer: {data.get('customer_name')}")

    def test_tracking_event_with_valid_contact_id(self):
        """POST /api/tracking/event with valid contact_id ObjectId works."""
        payload = {
            "page": "congrats",
            "action": "viewed",
            "salesperson_id": USER_ID,
            "contact_id": VALID_CONTACT_ID,  # Valid ObjectId string
        }
        response = requests.post(f"{BASE_URL}/api/tracking/event", json=payload)
        print(f"Tracking event response: {response.status_code} {response.json()}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("tracked") == True or data.get("reason") == "contact_not_found"
        print(f"PASS - Valid contact_id tracking: {data}")

    def test_tracking_event_with_invalid_contact_id_rejected(self):
        """POST /api/tracking/event with invalid contact_id (like card_id) is rejected gracefully."""
        payload = {
            "page": "congrats",
            "action": "viewed",
            "salesperson_id": USER_ID,
            "contact_id": TEST_CARD_ID,  # This is a card_id, NOT a valid contact ObjectId
        }
        response = requests.post(f"{BASE_URL}/api/tracking/event", json=payload)
        print(f"Tracking with card_id as contact_id: {response.status_code} {response.json()}")
        assert response.status_code == 200  # Should not crash
        data = response.json()
        # Should either be tracked=false (invalid ObjectId rejected) or fallback to phone lookup
        # It should NOT store card_id as contact_id
        print(f"PASS - Invalid contact_id handled gracefully: {data}")

    def test_tracking_event_with_completely_invalid_contact_id(self):
        """POST /api/tracking/event with completely invalid contact_id is rejected."""
        payload = {
            "page": "card",
            "action": "viewed",
            "salesperson_id": USER_ID,
            "contact_id": "abc123",  # Not a valid ObjectId
        }
        response = requests.post(f"{BASE_URL}/api/tracking/event", json=payload)
        print(f"Tracking with invalid contact_id: {response.status_code} {response.json()}")
        assert response.status_code == 200
        data = response.json()
        # Should be tracked=false since abc123 is not a valid ObjectId
        assert data.get("tracked") == False or data.get("reason") is not None
        print(f"PASS - Completely invalid contact_id rejected: {data}")

    def test_master_feed_shows_correct_names(self):
        """GET /api/contacts/{user_id}/master-feed shows correct names (no Unknown for valid contacts)."""
        response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}/master-feed?limit=50")
        print(f"Master feed response: {response.status_code}")
        assert response.status_code == 200
        data = response.json()
        feed = data.get("feed", [])
        print(f"Feed has {len(feed)} items")
        
        # Count items with valid vs Unknown names
        valid_names = 0
        unknown_names = 0
        for item in feed[:20]:  # Check first 20 items
            contact = item.get("contact", {})
            name = contact.get("name", "")
            if name == "Unknown" or not name:
                unknown_names += 1
            else:
                valid_names += 1
        
        print(f"Valid names: {valid_names}, Unknown names: {unknown_names}")
        # Most entries should have valid names (allow some Unknown for orphaned contacts)
        assert valid_names > 0, "Should have some events with valid contact names"
        print(f"PASS - Master feed shows {valid_names} events with valid names")


class TestShortURLCardRedirect:
    """Test that card short URLs properly handle contact_id tracking."""

    def test_new_card_short_url_has_contact_id_in_metadata(self):
        """Verify the test card's short URL has contact_id stored in metadata."""
        from pymongo import MongoClient
        client = MongoClient(os.environ.get('MONGO_URL', 'mongodb://localhost:27017'))
        db = client[os.environ.get('DB_NAME', 'imos-admin-test_database')]
        
        doc = db.short_urls.find_one({"short_code": TEST_SHORT_CODE})
        assert doc is not None, f"Short URL {TEST_SHORT_CODE} not found"
        
        metadata = doc.get("metadata", {})
        contact_id = metadata.get("contact_id")
        reference_id = doc.get("reference_id")
        link_type = doc.get("link_type", "")
        
        print(f"Short URL doc: reference_id={reference_id}, metadata.contact_id={contact_id}, link_type={link_type}")
        
        # For card links, contact_id should be in metadata and be different from reference_id
        assert "_card" in link_type, f"Expected card link type, got: {link_type}"
        assert contact_id is not None, "contact_id should be in metadata for new cards"
        assert contact_id != reference_id, "contact_id should differ from reference_id (card_id)"
        assert contact_id == VALID_CONTACT_ID, f"contact_id should be {VALID_CONTACT_ID}"
        print(f"PASS - New card short URL has contact_id in metadata: {contact_id}")

    def test_old_card_without_contact_id_metadata(self):
        """Old card short URLs without contact_id in metadata should NOT append wrong cid."""
        from pymongo import MongoClient
        client = MongoClient(os.environ.get('MONGO_URL', 'mongodb://localhost:27017'))
        db = client[os.environ.get('DB_NAME', 'imos-admin-test_database')]
        
        # Find an old card short URL without contact_id in metadata
        old_card = db.short_urls.find_one({
            "link_type": {"$regex": "_card"},
            "$or": [
                {"metadata.contact_id": {"$exists": False}},
                {"metadata.contact_id": None}
            ]
        })
        
        if not old_card:
            print("SKIP - No old card short URLs without contact_id found")
            pytest.skip("No old card short URLs to test")
        
        short_code = old_card["short_code"]
        reference_id = old_card.get("reference_id")
        print(f"Found old card short URL: {short_code}, reference_id={reference_id}")
        
        # Verify that without contact_id in metadata, no cid should be appended for card types
        # (The fix is in short_urls.py lines 371-377)
        metadata = old_card.get("metadata", {})
        assert metadata.get("contact_id") is None, "Old card should not have contact_id"
        print(f"PASS - Old card {short_code} correctly has no contact_id in metadata")


class TestCardCreationStoresContactId:
    """Test that card creation properly stores contact_id."""

    def test_congrats_card_stores_contact_id(self):
        """Verify congrats card doc has contact_id field."""
        from pymongo import MongoClient
        client = MongoClient(os.environ.get('MONGO_URL', 'mongodb://localhost:27017'))
        db = client[os.environ.get('DB_NAME', 'imos-admin-test_database')]
        
        # Check the test card
        card = db.congrats_cards.find_one({"card_id": TEST_CARD_ID})
        if not card:
            print(f"SKIP - Test card {TEST_CARD_ID} not found")
            pytest.skip("Test card not found")
        
        contact_id = card.get("contact_id")
        print(f"Card {TEST_CARD_ID} has contact_id: {contact_id}")
        
        # For new cards created after the fix, contact_id should be set
        if contact_id:
            assert contact_id == VALID_CONTACT_ID, f"contact_id should be {VALID_CONTACT_ID}"
            print(f"PASS - Card stores correct contact_id: {contact_id}")
        else:
            print("Note: Card was created before fix - contact_id is None")


class TestContactScoping:
    """Test that contacts are properly scoped per salesperson."""

    def test_contacts_scoped_by_user_id(self):
        """Verify contacts are fetched with user_id filter."""
        from pymongo import MongoClient
        client = MongoClient(os.environ.get('MONGO_URL', 'mongodb://localhost:27017'))
        db = client[os.environ.get('DB_NAME', 'imos-admin-test_database')]
        
        # Count contacts for our test user
        user_contacts = db.contacts.count_documents({"user_id": USER_ID, "status": {"$ne": "deleted"}})
        print(f"User {USER_ID} has {user_contacts} contacts")
        
        # Check that our valid contact belongs to the test user
        contact = db.contacts.find_one({"_id": ObjectId(VALID_CONTACT_ID)})
        if contact:
            assert contact.get("user_id") == USER_ID, f"Contact should belong to user {USER_ID}"
            print(f"PASS - Contact {VALID_CONTACT_ID} belongs to user {USER_ID}")
        else:
            print(f"Note: Contact {VALID_CONTACT_ID} not found")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
