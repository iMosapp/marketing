"""
Test for Contact Stats Bug Fix - Campaign and Referral Counts

Bug: The 'Campaigns' and 'Referrals' counters in contact card stats bar were always showing 0.

Root causes:
1. Campaign enrollments created by campaign_lifecycle.py use 'salesman_id' not 'user_id', 
   but the stats query filtered by user_id (now fixed - counts ALL enrollments for contact_id)
2. Referrals used a stale contact.referral_count field instead of dynamically counting 
   contacts with referred_by matching (now fixed - dynamic count added)

Tests verify:
- GET /api/contacts/{user_id}/{contact_id}/stats returns referral_count
- Campaign count counts enrollments regardless of user_id/salesman_id field naming
- Referral count dynamically counts contacts where referred_by matches contact_id
- All expected stats fields are returned
"""
import pytest
import requests
import os
from datetime import datetime, timezone
from bson import ObjectId

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestContactStatsBugFix:
    """Tests for the campaign and referral count bug fix in contact stats"""
    
    @pytest.fixture(scope="class")
    def api_client(self):
        """Shared requests session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        return session
    
    @pytest.fixture(scope="class")
    def test_user(self, api_client):
        """Get or create test user for stats testing"""
        # Login with provided credentials
        login_resp = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": "forest@imosapp.com",
            "password": "Admin123!"
        })
        
        if login_resp.status_code == 200:
            user = login_resp.json().get("user", {})
            return {"user_id": user.get("_id") or user.get("id")}
        
        pytest.skip("Could not authenticate - skipping stats tests")
    
    @pytest.fixture(scope="class")
    def test_contact_a(self, api_client, test_user):
        """Create a main contact (Contact A) for testing stats"""
        contact_data = {
            "first_name": "TEST_STATS",
            "last_name": f"ContactA_{datetime.now().strftime('%H%M%S')}",
            "phone": f"+1555{datetime.now().strftime('%H%M%S%f')[:7]}",
            "email": f"test_stats_a_{datetime.now().timestamp()}@test.com",
            "notes": "Test contact for stats bug fix verification"
        }
        
        resp = api_client.post(f"{BASE_URL}/api/contacts/{test_user['user_id']}", json=contact_data)
        assert resp.status_code in [200, 201], f"Failed to create contact A: {resp.text}"
        
        contact = resp.json()
        contact_id = contact.get("_id") or contact.get("id")
        assert contact_id, "Contact A must have an ID"
        
        yield {"contact_id": contact_id, "data": contact}
        
        # Cleanup
        try:
            api_client.delete(f"{BASE_URL}/api/contacts/{test_user['user_id']}/{contact_id}")
        except:
            pass
    
    @pytest.fixture(scope="class")
    def referral_contacts(self, api_client, test_user, test_contact_a):
        """Create contacts that were referred by Contact A"""
        referral_ids = []
        
        for i in range(2):
            contact_data = {
                "first_name": f"TEST_REFERRAL",
                "last_name": f"Contact{i}_{datetime.now().strftime('%H%M%S')}",
                "phone": f"+1555{datetime.now().strftime('%H%M%S%f')[:7]}{i}",
                "email": f"test_referral_{i}_{datetime.now().timestamp()}@test.com",
                "referred_by": test_contact_a["contact_id"],
                "notes": f"Referred by {test_contact_a['contact_id']}"
            }
            
            resp = api_client.post(f"{BASE_URL}/api/contacts/{test_user['user_id']}", json=contact_data)
            if resp.status_code in [200, 201]:
                contact = resp.json()
                contact_id = contact.get("_id") or contact.get("id")
                if contact_id:
                    referral_ids.append(contact_id)
        
        yield referral_ids
        
        # Cleanup referral contacts
        for cid in referral_ids:
            try:
                api_client.delete(f"{BASE_URL}/api/contacts/{test_user['user_id']}/{cid}")
            except:
                pass
    
    @pytest.fixture(scope="class")
    def campaign_enrollments(self, api_client, test_user, test_contact_a):
        """Create campaign enrollments with both user_id and salesman_id patterns"""
        from pymongo import MongoClient
        import os
        
        enrollment_ids = []
        
        try:
            mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
            db_name = os.environ.get('DB_NAME', 'imos-admin-test_database')
            client = MongoClient(mongo_url)
            db = client[db_name]
            
            # Create enrollment 1: with user_id (campaigns.py pattern)
            enrollment1 = {
                "contact_id": test_contact_a["contact_id"],
                "user_id": test_user["user_id"],
                "campaign_id": str(ObjectId()),  # Dummy campaign ID
                "status": "active",
                "enrolled_at": datetime.now(timezone.utc),
                "current_step": 1,
                "messages_sent": [],
                "test_marker": "TEST_STATS_FIX"
            }
            result1 = db.campaign_enrollments.insert_one(enrollment1)
            enrollment_ids.append(str(result1.inserted_id))
            
            # Create enrollment 2: with salesman_id (campaign_lifecycle.py pattern)
            enrollment2 = {
                "contact_id": test_contact_a["contact_id"],
                "salesman_id": test_user["user_id"],  # This was the bug - NOT user_id
                "campaign_id": str(ObjectId()),  # Dummy campaign ID
                "status": "active",
                "enrolled_at": datetime.now(timezone.utc),
                "current_step": 1,
                "messages_sent": [],
                "test_marker": "TEST_STATS_FIX"
            }
            result2 = db.campaign_enrollments.insert_one(enrollment2)
            enrollment_ids.append(str(result2.inserted_id))
            
            yield enrollment_ids
            
        except Exception as e:
            print(f"Could not create enrollment test data: {e}")
            yield []
        
        finally:
            # Cleanup
            try:
                db.campaign_enrollments.delete_many({"test_marker": "TEST_STATS_FIX"})
            except:
                pass
    
    def test_stats_endpoint_returns_all_fields(self, api_client, test_user, test_contact_a):
        """Test that stats endpoint returns all expected fields including referral_count"""
        resp = api_client.get(f"{BASE_URL}/api/contacts/{test_user['user_id']}/{test_contact_a['contact_id']}/stats")
        
        assert resp.status_code == 200, f"Stats endpoint failed: {resp.text}"
        
        stats = resp.json()
        
        # Verify all required fields are present
        required_fields = [
            "total_touchpoints",
            "messages_sent",
            "campaigns",
            "cards_sent",
            "broadcasts",
            "custom_events",
            "link_clicks",
            "referral_count",  # NEW FIELD - the bug fix
            "created_at"
        ]
        
        for field in required_fields:
            assert field in stats, f"Missing required stats field: {field}"
        
        print(f"✓ Stats endpoint returns all {len(required_fields)} required fields")
        print(f"  Stats: {stats}")
    
    def test_campaign_count_with_both_user_id_and_salesman_id(
        self, api_client, test_user, test_contact_a, campaign_enrollments
    ):
        """
        Test that campaign count correctly counts enrollments regardless of
        whether they use 'user_id' or 'salesman_id' field naming.
        
        This is the core bug fix test - before the fix, enrollments with 
        salesman_id (from campaign_lifecycle.py) would NOT be counted.
        """
        if not campaign_enrollments or len(campaign_enrollments) < 2:
            pytest.skip("Could not create test enrollments")
        
        resp = api_client.get(f"{BASE_URL}/api/contacts/{test_user['user_id']}/{test_contact_a['contact_id']}/stats")
        
        assert resp.status_code == 200, f"Stats endpoint failed: {resp.text}"
        
        stats = resp.json()
        campaign_count = stats.get("campaigns", 0)
        
        # We created 2 enrollments - one with user_id, one with salesman_id
        # The fix should count BOTH since it no longer filters by user_id
        assert campaign_count >= 2, (
            f"Expected at least 2 campaign enrollments (user_id + salesman_id patterns), "
            f"but got {campaign_count}. BUG NOT FIXED - salesman_id enrollments likely not counted!"
        )
        
        print(f"✓ Campaign count ({campaign_count}) correctly includes both user_id and salesman_id enrollments")
    
    def test_referral_count_dynamic(self, api_client, test_user, test_contact_a, referral_contacts):
        """
        Test that referral_count is dynamically calculated by counting contacts
        where referred_by equals this contact's ID.
        
        This is the second part of the bug fix - before, it used a stale 
        contact.referral_count field instead of dynamically counting.
        """
        if not referral_contacts or len(referral_contacts) < 2:
            pytest.skip("Could not create referral contacts")
        
        resp = api_client.get(f"{BASE_URL}/api/contacts/{test_user['user_id']}/{test_contact_a['contact_id']}/stats")
        
        assert resp.status_code == 200, f"Stats endpoint failed: {resp.text}"
        
        stats = resp.json()
        referral_count = stats.get("referral_count", 0)
        
        # We created 2 contacts with referred_by = test_contact_a's ID
        assert referral_count >= 2, (
            f"Expected at least 2 referrals (contacts with referred_by pointing to this contact), "
            f"but got {referral_count}. BUG NOT FIXED - referral_count not dynamically calculated!"
        )
        
        print(f"✓ Referral count ({referral_count}) is dynamically calculated from contacts collection")
    
    def test_referral_count_field_in_response(self, api_client, test_user, test_contact_a):
        """Verify referral_count field exists and is an integer"""
        resp = api_client.get(f"{BASE_URL}/api/contacts/{test_user['user_id']}/{test_contact_a['contact_id']}/stats")
        
        assert resp.status_code == 200, f"Stats endpoint failed: {resp.text}"
        
        stats = resp.json()
        
        assert "referral_count" in stats, "referral_count field missing from stats response"
        assert isinstance(stats["referral_count"], int), "referral_count should be an integer"
        
        print(f"✓ referral_count field exists and is integer: {stats['referral_count']}")
    
    def test_total_touchpoints_calculation(self, api_client, test_user, test_contact_a, campaign_enrollments):
        """Verify total_touchpoints includes campaign count"""
        if not campaign_enrollments:
            pytest.skip("No campaign enrollments created")
        
        resp = api_client.get(f"{BASE_URL}/api/contacts/{test_user['user_id']}/{test_contact_a['contact_id']}/stats")
        
        assert resp.status_code == 200, f"Stats endpoint failed: {resp.text}"
        
        stats = resp.json()
        
        # total_touchpoints = messages + campaigns + cards + broadcasts + custom_events
        expected_min = stats.get("campaigns", 0)  # At least campaign count should be in total
        actual_total = stats.get("total_touchpoints", 0)
        
        assert actual_total >= expected_min, (
            f"total_touchpoints ({actual_total}) should be >= campaigns ({expected_min})"
        )
        
        print(f"✓ total_touchpoints ({actual_total}) includes campaigns ({stats.get('campaigns', 0)})")


class TestContactStatsIntegrationWithFrontend:
    """Additional tests for frontend integration of stats"""
    
    @pytest.fixture(scope="class")
    def api_client(self):
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        return session
    
    def test_stats_endpoint_returns_json(self, api_client):
        """Test that stats endpoint returns valid JSON"""
        # Login first
        login_resp = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": "forest@imosapp.com",
            "password": "Admin123!"
        })
        
        if login_resp.status_code != 200:
            pytest.skip("Could not authenticate")
        
        user = login_resp.json().get("user", {})
        user_id = user.get("_id") or user.get("id")
        
        # Create a quick test contact
        contact_resp = api_client.post(f"{BASE_URL}/api/contacts/{user_id}", json={
            "first_name": "TEST_STATS_JSON",
            "last_name": datetime.now().strftime('%H%M%S'),
            "phone": f"+1555{datetime.now().strftime('%H%M%S%f')[:7]}999"
        })
        
        if contact_resp.status_code not in [200, 201]:
            pytest.skip("Could not create test contact")
        
        contact_id = contact_resp.json().get("_id") or contact_resp.json().get("id")
        
        try:
            # Test stats endpoint
            stats_resp = api_client.get(f"{BASE_URL}/api/contacts/{user_id}/{contact_id}/stats")
            
            assert stats_resp.status_code == 200
            assert stats_resp.headers.get("content-type", "").startswith("application/json")
            
            stats = stats_resp.json()
            assert isinstance(stats, dict), "Stats response should be a dictionary"
            
            print(f"✓ Stats endpoint returns valid JSON with {len(stats)} fields")
            
        finally:
            # Cleanup
            try:
                api_client.delete(f"{BASE_URL}/api/contacts/{user_id}/{contact_id}")
            except:
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
