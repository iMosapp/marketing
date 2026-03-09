"""
Test Contact Search by Tag Name feature
Tests that the contacts search endpoint now matches contacts by their tag names
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://rms-polish.preview.emergentagent.com')

# Test credentials from review request
TEST_USER_ID = "69a0b7095fddcede09591667"
TEST_CONTACT_ID = "69a0c06f7626f14d125f8c34"  # Forest Ward

class TestContactTagSearch:
    """Tests for contact search by tag name functionality"""

    def test_search_contacts_by_tag_birthday(self):
        """Test: Search contacts by 'Birthday' tag returns Forest Ward"""
        response = requests.get(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}",
            params={"search": "Birthday"},
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        contacts = response.json()
        assert isinstance(contacts, list), "Response should be a list of contacts"
        
        # Forest Ward should be in results (has Birthday tag)
        forest_ward = None
        for contact in contacts:
            if contact.get("_id") == TEST_CONTACT_ID:
                forest_ward = contact
                break
        
        assert forest_ward is not None, f"Forest Ward (ID: {TEST_CONTACT_ID}) should appear in search results for 'Birthday' tag"
        print(f"PASS: Found Forest Ward in 'Birthday' tag search. Contact has tags: {forest_ward.get('tags', [])}")
        
    def test_search_contacts_by_tag_sold_date(self):
        """Test: Search contacts by 'Sold Date' tag returns Forest Ward"""
        response = requests.get(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}",
            params={"search": "Sold Date"},
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        contacts = response.json()
        # Forest Ward has 'Sold Date' tag
        forest_found = any(c.get("_id") == TEST_CONTACT_ID for c in contacts)
        assert forest_found, "Forest Ward should appear in search for 'Sold Date' tag"
        print(f"PASS: Forest Ward found in 'Sold Date' tag search results")

    def test_search_contacts_by_tag_anniversary(self):
        """Test: Search contacts by 'Anniversary' tag returns Forest Ward"""
        response = requests.get(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}",
            params={"search": "Anniversary"},
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        contacts = response.json()
        forest_found = any(c.get("_id") == TEST_CONTACT_ID for c in contacts)
        assert forest_found, "Forest Ward should appear in search for 'Anniversary' tag"
        print(f"PASS: Forest Ward found in 'Anniversary' tag search results")

    def test_search_contacts_by_tag_hot_lead(self):
        """Test: Search contacts by 'Hot Lead' tag returns Forest Ward"""
        response = requests.get(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}",
            params={"search": "Hot Lead"},
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        contacts = response.json()
        forest_found = any(c.get("_id") == TEST_CONTACT_ID for c in contacts)
        assert forest_found, "Forest Ward should appear in search for 'Hot Lead' tag"
        print(f"PASS: Forest Ward found in 'Hot Lead' tag search results")

    def test_search_contacts_by_tag_out_of_state(self):
        """Test: Search contacts by 'Out of State' tag returns Forest Ward"""
        response = requests.get(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}",
            params={"search": "Out of State"},
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        contacts = response.json()
        forest_found = any(c.get("_id") == TEST_CONTACT_ID for c in contacts)
        assert forest_found, "Forest Ward should appear in search for 'Out of State' tag"
        print(f"PASS: Forest Ward found in 'Out of State' tag search results")

    def test_search_contacts_by_partial_tag_name(self):
        """Test: Search by partial tag name (regex search)"""
        response = requests.get(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}",
            params={"search": "Birth"},  # partial match for 'Birthday'
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        contacts = response.json()
        forest_found = any(c.get("_id") == TEST_CONTACT_ID for c in contacts)
        assert forest_found, "Forest Ward should appear in partial tag search 'Birth'"
        print(f"PASS: Partial tag search works - found contacts with 'Birth' match")

    def test_search_contacts_by_nonexistent_tag(self):
        """Test: Search by tag that doesn't exist returns empty or no match for Forest Ward"""
        response = requests.get(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}",
            params={"search": "NonExistentTagXYZ123"},
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        contacts = response.json()
        forest_found = any(c.get("_id") == TEST_CONTACT_ID for c in contacts)
        assert not forest_found, "Forest Ward should NOT appear for non-existent tag search"
        print(f"PASS: Non-existent tag search correctly excludes Forest Ward. Found {len(contacts)} contacts")

    def test_search_by_name_still_works(self):
        """Test: Search by contact name still works (Forest)"""
        response = requests.get(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}",
            params={"search": "Forest"},
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        contacts = response.json()
        forest_found = any(c.get("_id") == TEST_CONTACT_ID for c in contacts)
        assert forest_found, "Forest Ward should appear when searching by first name 'Forest'"
        print(f"PASS: Name search still works - Forest Ward found")

    def test_get_specific_contact_has_tags(self):
        """Test: Get specific contact shows expected tags"""
        response = requests.get(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}",
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        contact = response.json()
        tags = contact.get("tags", [])
        
        # Forest Ward should have these tags according to the review request
        expected_tags = ['Birthday', 'Sold Date', 'Anniversary', 'Out of State', 'Hot Lead']
        
        print(f"Contact tags: {tags}")
        for expected_tag in expected_tags:
            assert expected_tag in tags, f"Expected tag '{expected_tag}' not found in contact tags: {tags}"
        
        print(f"PASS: Forest Ward has all expected tags: {tags}")


class TestTagsAPI:
    """Tests for Tags API endpoint"""
    
    def test_get_all_tags(self):
        """Test: Get all tags for user"""
        response = requests.get(
            f"{BASE_URL}/api/tags/{TEST_USER_ID}",
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        tags = response.json()
        assert isinstance(tags, list), "Tags response should be a list"
        print(f"PASS: Found {len(tags)} tags")
        
        # Print tag names for debugging
        tag_names = [t.get("name") for t in tags]
        print(f"Available tags: {tag_names}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
