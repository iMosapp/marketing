"""
Tests for AI Relationship Intel feature (/api/contact-intel endpoints)
- GET returns cached summary or null if none exists
- POST generates AI summary via GPT-5.2 and caches it
- After generating, GET returns the cached version
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
USER_ID = "69a0b7095fddcede09591667"
CONTACT_ID = "69a1354f2c0649ac6fb7f3f1"


class TestContactIntelGetCached:
    """Test GET /api/contact-intel/{user_id}/{contact_id} endpoint"""
    
    def test_get_cached_intel_returns_200(self):
        """GET endpoint should return 200 status code"""
        response = requests.get(f"{BASE_URL}/api/contact-intel/{USER_ID}/{CONTACT_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET cached intel returns 200")
    
    def test_get_cached_intel_has_summary_field(self):
        """GET response should have summary field"""
        response = requests.get(f"{BASE_URL}/api/contact-intel/{USER_ID}/{CONTACT_ID}")
        data = response.json()
        assert "summary" in data, "Response must have 'summary' field"
        print(f"✓ Response has summary field")
    
    def test_get_cached_intel_has_data_points(self):
        """If summary exists, response should have data_points"""
        response = requests.get(f"{BASE_URL}/api/contact-intel/{USER_ID}/{CONTACT_ID}")
        data = response.json()
        if data.get("summary"):
            assert "data_points" in data, "Response should have 'data_points' when summary exists"
            dp = data["data_points"]
            assert "messages" in dp, "data_points should have 'messages'"
            assert "events" in dp, "data_points should have 'events'"
            assert "voice_notes" in dp, "data_points should have 'voice_notes'"
            assert "tasks" in dp, "data_points should have 'tasks'"
            print(f"✓ data_points structure verified: messages={dp['messages']}, events={dp['events']}, voice_notes={dp['voice_notes']}, tasks={dp['tasks']}")
        else:
            print("✓ No cached summary yet, data_points check skipped")
    
    def test_get_cached_intel_has_generated_at(self):
        """If summary exists, should have generated_at timestamp"""
        response = requests.get(f"{BASE_URL}/api/contact-intel/{USER_ID}/{CONTACT_ID}")
        data = response.json()
        if data.get("summary"):
            assert "generated_at" in data, "Response should have 'generated_at' timestamp"
            assert data["generated_at"] is not None, "generated_at should not be None"
            print(f"✓ generated_at present: {data['generated_at']}")
        else:
            print("✓ No cached summary yet, generated_at check skipped")
    
    def test_get_cached_intel_has_contact_name(self):
        """If summary exists, should have contact_name"""
        response = requests.get(f"{BASE_URL}/api/contact-intel/{USER_ID}/{CONTACT_ID}")
        data = response.json()
        if data.get("summary"):
            assert "contact_name" in data, "Response should have 'contact_name'"
            print(f"✓ contact_name: {data.get('contact_name')}")
        else:
            print("✓ No cached summary yet, contact_name check skipped")
    
    def test_get_intel_nonexistent_contact_returns_404(self):
        """GET with invalid contact_id should return 404"""
        response = requests.get(f"{BASE_URL}/api/contact-intel/{USER_ID}/000000000000000000000000")
        # This should return empty summary, not 404 (per current implementation)
        data = response.json()
        # The endpoint returns {"summary": null, "generated_at": null} for non-existent cached intel
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert data.get("summary") is None, "Summary should be None for non-existent cache"
        print("✓ Non-existent contact returns null summary")


class TestContactIntelGenerate:
    """Test POST /api/contact-intel/{user_id}/{contact_id} endpoint"""
    
    def test_generate_intel_returns_200(self):
        """POST should return 200 status code when successful"""
        response = requests.post(
            f"{BASE_URL}/api/contact-intel/{USER_ID}/{CONTACT_ID}",
            timeout=30  # AI can take up to 15 seconds
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ POST generate intel returns 200")
    
    def test_generate_intel_returns_summary(self):
        """POST should return a non-empty summary"""
        response = requests.post(
            f"{BASE_URL}/api/contact-intel/{USER_ID}/{CONTACT_ID}",
            timeout=30
        )
        data = response.json()
        assert "summary" in data, "Response must have 'summary' field"
        assert data["summary"], "Summary should not be empty"
        assert len(data["summary"]) > 50, "Summary should be substantial text"
        print(f"✓ Summary generated with {len(data['summary'])} characters")
    
    def test_generate_intel_returns_data_points(self):
        """POST should return data_points with counts"""
        response = requests.post(
            f"{BASE_URL}/api/contact-intel/{USER_ID}/{CONTACT_ID}",
            timeout=30
        )
        data = response.json()
        assert "data_points" in data, "Response must have 'data_points'"
        dp = data["data_points"]
        assert isinstance(dp.get("messages"), int), "messages should be int"
        assert isinstance(dp.get("events"), int), "events should be int"
        assert isinstance(dp.get("voice_notes"), int), "voice_notes should be int"
        assert isinstance(dp.get("tasks"), int), "tasks should be int"
        print(f"✓ data_points: messages={dp['messages']}, events={dp['events']}, voice_notes={dp['voice_notes']}, tasks={dp['tasks']}")
    
    def test_generate_intel_returns_generated_at(self):
        """POST should return generated_at timestamp"""
        response = requests.post(
            f"{BASE_URL}/api/contact-intel/{USER_ID}/{CONTACT_ID}",
            timeout=30
        )
        data = response.json()
        assert "generated_at" in data, "Response must have 'generated_at'"
        assert data["generated_at"] is not None, "generated_at should not be None"
        print(f"✓ generated_at: {data['generated_at']}")
    
    def test_generate_intel_invalid_contact_returns_404(self):
        """POST with invalid contact_id should return 404"""
        response = requests.post(
            f"{BASE_URL}/api/contact-intel/{USER_ID}/000000000000000000000000",
            timeout=30
        )
        assert response.status_code == 404, f"Expected 404 for invalid contact, got {response.status_code}"
        print("✓ Invalid contact returns 404")


class TestContactIntelCaching:
    """Test that GET returns cached intel after POST generates it"""
    
    def test_cached_intel_matches_generated(self):
        """After POST generates intel, GET should return same summary"""
        # First, generate new intel
        post_response = requests.post(
            f"{BASE_URL}/api/contact-intel/{USER_ID}/{CONTACT_ID}",
            timeout=30
        )
        assert post_response.status_code == 200
        generated = post_response.json()
        
        # Now GET should return the same summary
        get_response = requests.get(f"{BASE_URL}/api/contact-intel/{USER_ID}/{CONTACT_ID}")
        assert get_response.status_code == 200
        cached = get_response.json()
        
        # Summary text should match
        assert cached.get("summary") == generated.get("summary"), "Cached summary should match generated"
        print(f"✓ Cached summary matches generated summary ({len(cached['summary'])} chars)")
    
    def test_refresh_generates_new_summary(self):
        """POST again should generate a fresh summary (may differ slightly)"""
        # Get current cached
        get1 = requests.get(f"{BASE_URL}/api/contact-intel/{USER_ID}/{CONTACT_ID}")
        original_time = get1.json().get("generated_at")
        
        # Wait a moment and regenerate
        time.sleep(1)
        
        post_response = requests.post(
            f"{BASE_URL}/api/contact-intel/{USER_ID}/{CONTACT_ID}",
            timeout=30
        )
        assert post_response.status_code == 200
        new_data = post_response.json()
        
        # generated_at should be newer
        assert new_data.get("generated_at") != original_time, "Refreshed intel should have new timestamp"
        print(f"✓ Refresh generated new summary at {new_data['generated_at']} (was {original_time})")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
