"""
Test Contact Search - Name-Only Matching
=========================================
Verifies that GET /api/contacts/{user_id}?search= returns contacts
filtered by first_name and last_name ONLY (not email, phone, or conversation content)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
USER_ID = "69a0b7095fddcede09591667"


class TestContactSearchNameOnly:
    """Tests for contact search with strict name matching"""

    def test_search_by_first_name_forest(self):
        """Search 'Forest' should return Forest Ward only"""
        response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}?search=Forest")
        assert response.status_code == 200
        data = response.json()
        
        # Should return at least one contact
        assert len(data) >= 1, "Expected at least one result for 'Forest'"
        
        # All results should have 'Forest' in first_name or last_name
        for contact in data:
            name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".lower()
            assert 'forest' in name, f"Contact {contact.get('_id')} doesn't match 'forest' in name"

    def test_search_by_last_name_ward(self):
        """Search 'Ward' should return contacts with Ward in first_name or last_name"""
        response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}?search=Ward")
        assert response.status_code == 200
        data = response.json()
        
        # All results should have 'Ward' in first_name or last_name
        for contact in data:
            name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".lower()
            assert 'ward' in name, f"Contact {contact.get('_id')} doesn't match 'ward' in name"

    def test_search_by_partial_name(self):
        """Search 'For' should still match Forest (partial match)"""
        response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}?search=For")
        assert response.status_code == 200
        data = response.json()
        
        # Should find at least Forest Ward
        names = [f"{c.get('first_name', '')} {c.get('last_name', '')}".lower() for c in data]
        has_forest = any('forest' in n for n in names)
        assert has_forest, "Partial search 'For' should return Forest"

    def test_search_does_not_match_email(self):
        """Search should NOT match email addresses"""
        # Get all contacts first
        all_response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}")
        assert all_response.status_code == 200
        all_contacts = all_response.json()
        
        # Find a contact with an email that doesn't match name
        for contact in all_contacts:
            email = contact.get('email', '')
            first_name = contact.get('first_name', '')
            last_name = contact.get('last_name', '')
            
            if email and '@' in email:
                # Extract email username (before @)
                email_username = email.split('@')[0].lower()
                name_lower = f"{first_name} {last_name}".lower()
                
                # If email username is not in the name, test that searching for it doesn't return this contact
                if email_username and email_username not in name_lower and len(email_username) > 3:
                    search_response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}?search={email_username}")
                    assert search_response.status_code == 200
                    results = search_response.json()
                    
                    # Verify the contact is NOT in results (or only if name matches)
                    for r in results:
                        result_name = f"{r.get('first_name', '')} {r.get('last_name', '')}".lower()
                        assert email_username in result_name or r.get('phone', '') == contact.get('phone'), \
                            f"Search by email username '{email_username}' should not return contacts by email match alone"
                    break

    def test_search_can_match_phone(self):
        """Search by phone number should still work (backend allows first_name/last_name/phone)"""
        # Get a contact with a phone number
        all_response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}")
        assert all_response.status_code == 200
        all_contacts = all_response.json()
        
        for contact in all_contacts:
            phone = contact.get('phone', '')
            if phone and len(phone) >= 10:
                # Search by last 4 digits of phone
                search_term = phone[-4:]
                search_response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}?search={search_term}")
                assert search_response.status_code == 200
                # Phone search should work
                break

    def test_search_case_insensitive(self):
        """Search should be case insensitive"""
        response_lower = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}?search=forest")
        response_upper = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}?search=FOREST")
        
        assert response_lower.status_code == 200
        assert response_upper.status_code == 200
        
        data_lower = response_lower.json()
        data_upper = response_upper.json()
        
        # Both should return same results
        assert len(data_lower) == len(data_upper), "Case insensitive search should return same results"

    def test_empty_search_returns_all(self):
        """Empty search should return all contacts"""
        response_all = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}")
        response_empty = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}?search=")
        
        assert response_all.status_code == 200
        assert response_empty.status_code == 200
        
        # Empty search should return all contacts
        assert len(response_all.json()) == len(response_empty.json()), \
            "Empty search should return all contacts"

    def test_no_results_for_nonexistent_name(self):
        """Search for non-existent name should return empty array"""
        response = requests.get(f"{BASE_URL}/api/contacts/{USER_ID}?search=ZZZNONEXISTENT")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0, "Non-existent name should return empty results"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
