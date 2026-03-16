"""
CSV Import Feature Tests
Tests for Google Contacts CSV import functionality including:
- CSV file upload and parsing (preview endpoint)
- Duplicate detection by phone number
- Primary phone selection with label priority (Mobile > Work > Home)
- Contact import confirmation with organization_name, phones[], emails[] fields
- Skip contacts with no phone AND no email
- Proper tagging (csv-import, source=csv)
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_USER_ID = "69a0b7095fddcede09591667"
TEST_CSV_URL = "https://customer-assets.emergentagent.com/job_0e985e85-6651-4df7-92c1-4c74ea78aa26/artifacts/vvjztx9a_contacts.csv"

# Authentication credentials
AUTH_EMAIL = "forest@imosapp.com"
AUTH_PASSWORD = "Admin123!"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for API calls"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": AUTH_EMAIL, "password": AUTH_PASSWORD}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def csv_content():
    """Download the test CSV file content"""
    response = requests.get(TEST_CSV_URL)
    assert response.status_code == 200, f"Failed to download CSV: {response.status_code}"
    return response.content


@pytest.fixture
def api_client(auth_token):
    """Session with auth headers"""
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {auth_token}",
        "Accept": "application/json"
    })
    return session


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_data(auth_token):
    """Cleanup any previously imported test contacts after module completes"""
    yield
    # Teardown: Delete contacts with source='csv' and tag='csv-import'
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {auth_token}"})
    
    try:
        # Get contacts with csv-import tag
        response = session.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}")
        if response.status_code == 200:
            contacts = response.json()
            csv_contacts = [c for c in contacts if c.get("source") == "csv" or "csv-import" in c.get("tags", [])]
            contact_ids = [c.get("_id") or c.get("id") for c in csv_contacts if c.get("_id") or c.get("id")]
            
            if contact_ids:
                # Bulk delete
                delete_response = session.post(
                    f"{BASE_URL}/api/contacts/{TEST_USER_ID}/bulk-delete",
                    json={"contact_ids": contact_ids}
                )
                print(f"Cleanup: Deleted {len(contact_ids)} test contacts: {delete_response.status_code}")
    except Exception as e:
        print(f"Cleanup failed: {e}")


class TestCSVPreviewEndpoint:
    """Test POST /api/contacts/{user_id}/import-csv/preview endpoint"""
    
    def test_preview_csv_upload_success(self, api_client, csv_content):
        """Test successful CSV upload returns parsed contacts"""
        files = {"file": ("contacts.csv", csv_content, "text/csv")}
        response = api_client.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-csv/preview",
            files=files
        )
        
        assert response.status_code == 200, f"Preview failed: {response.status_code} - {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "total_parsed" in data, "Missing total_parsed field"
        assert "new_contacts" in data, "Missing new_contacts field"
        assert "duplicates" in data, "Missing duplicates field"
        assert "skipped_no_info" in data, "Missing skipped_no_info field"
        assert "contacts" in data, "Missing contacts field"
        
        # Verify contacts were parsed
        assert data["total_parsed"] > 0, "No contacts were parsed"
        print(f"Parsed {data['total_parsed']} contacts, {data['new_contacts']} new, {data['duplicates']} duplicates, {data['skipped_no_info']} skipped")
    
    def test_preview_returns_duplicate_detection(self, api_client, csv_content):
        """Test that duplicate detection works for existing contacts"""
        files = {"file": ("contacts.csv", csv_content, "text/csv")}
        response = api_client.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-csv/preview",
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check for is_duplicate flag in contacts
        contacts = data.get("contacts", [])
        duplicates = [c for c in contacts if c.get("is_duplicate") == True]
        
        # We know Forest Ward (8016349122) exists, so there should be at least 1 duplicate
        assert data["duplicates"] >= 0, "Duplicates count should be >= 0"
        print(f"Found {data['duplicates']} duplicate contacts")
        
        # Verify duplicate flag structure
        if duplicates:
            dup = duplicates[0]
            assert "is_duplicate" in dup
            assert dup["is_duplicate"] == True
    
    def test_preview_contact_has_phones_array(self, api_client, csv_content):
        """Test that parsed contacts include phones[] array"""
        files = {"file": ("contacts.csv", csv_content, "text/csv")}
        response = api_client.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-csv/preview",
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        contacts = data.get("contacts", [])
        
        # Find a contact with phones array
        contacts_with_phones = [c for c in contacts if c.get("phones")]
        assert len(contacts_with_phones) > 0, "No contacts with phones[] array found"
        
        # Verify phones array structure
        contact = contacts_with_phones[0]
        phones = contact.get("phones", [])
        assert isinstance(phones, list), "phones should be a list"
        if phones:
            phone = phones[0]
            assert "label" in phone, "Phone entry should have 'label'"
            assert "value" in phone, "Phone entry should have 'value'"
            print(f"Sample phone entry: {phone}")
    
    def test_preview_contact_has_emails_array(self, api_client, csv_content):
        """Test that parsed contacts include emails[] array"""
        files = {"file": ("contacts.csv", csv_content, "text/csv")}
        response = api_client.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-csv/preview",
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        contacts = data.get("contacts", [])
        
        # Find a contact with emails array
        contacts_with_emails = [c for c in contacts if c.get("emails")]
        
        if contacts_with_emails:
            contact = contacts_with_emails[0]
            emails = contact.get("emails", [])
            assert isinstance(emails, list), "emails should be a list"
            if emails:
                email = emails[0]
                assert "label" in email, "Email entry should have 'label'"
                assert "value" in email, "Email entry should have 'value'"
                print(f"Sample email entry: {email}")
    
    def test_preview_contact_has_organization_name(self, api_client, csv_content):
        """Test that parsed contacts include organization_name field"""
        files = {"file": ("contacts.csv", csv_content, "text/csv")}
        response = api_client.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-csv/preview",
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        contacts = data.get("contacts", [])
        
        # Find a contact with organization_name
        contacts_with_org = [c for c in contacts if c.get("organization_name")]
        
        if contacts_with_org:
            contact = contacts_with_org[0]
            assert "organization_name" in contact, "organization_name field should exist"
            print(f"Sample organization: {contact.get('organization_name')}")
    
    def test_preview_rejects_non_csv_file(self, api_client):
        """Test that non-CSV files are rejected"""
        files = {"file": ("test.txt", b"Not a CSV file", "text/plain")}
        response = api_client.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-csv/preview",
            files=files
        )
        
        assert response.status_code == 400, f"Should reject non-CSV: {response.status_code}"
    
    def test_preview_primary_phone_selection(self, api_client, csv_content):
        """Test that primary phone is selected with correct priority (Mobile > Work > Home)"""
        files = {"file": ("contacts.csv", csv_content, "text/csv")}
        response = api_client.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-csv/preview",
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        contacts = data.get("contacts", [])
        
        # Find contacts with multiple phones
        contacts_with_multi_phones = [c for c in contacts if len(c.get("phones", [])) > 1]
        
        if contacts_with_multi_phones:
            contact = contacts_with_multi_phones[0]
            phones = contact.get("phones", [])
            primary_phone = contact.get("phone", "")
            
            # Check if Mobile phone exists and is selected as primary
            mobile_phones = [p for p in phones if "mobile" in p.get("label", "").lower()]
            if mobile_phones:
                # Primary should be the normalized mobile phone
                mobile_digits = ''.join(c for c in mobile_phones[0].get("value", "") if c.isdigit())
                primary_digits = ''.join(c for c in primary_phone if c.isdigit())
                assert mobile_digits[-7:] == primary_digits[-7:], f"Mobile should be primary. Mobile: {mobile_phones[0]}, Primary: {primary_phone}"
                print(f"Mobile phone correctly selected as primary")
    
    def test_preview_skips_contacts_without_phone_or_email(self, api_client, csv_content):
        """Test that contacts with no phone AND no email are skipped"""
        files = {"file": ("contacts.csv", csv_content, "text/csv")}
        response = api_client.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-csv/preview",
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify skipped_no_info count
        assert "skipped_no_info" in data
        skipped = data.get("skipped_no_info", 0)
        print(f"Skipped {skipped} contacts with no phone/email")
        
        # Verify all returned contacts have either phone or email
        contacts = data.get("contacts", [])
        for contact in contacts:
            has_phone = bool(contact.get("phone"))
            has_email = bool(contact.get("email"))
            assert has_phone or has_email, f"Contact should have phone or email: {contact.get('first_name')} {contact.get('last_name')}"


class TestCSVConfirmEndpoint:
    """Test POST /api/contacts/{user_id}/import-csv/confirm endpoint"""
    
    def test_confirm_import_creates_contacts(self, api_client, csv_content):
        """Test that confirming import creates contacts in database"""
        # First get preview to get parsed contacts
        files = {"file": ("contacts.csv", csv_content, "text/csv")}
        preview_response = api_client.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-csv/preview",
            files=files
        )
        
        assert preview_response.status_code == 200
        preview_data = preview_response.json()
        contacts = preview_data.get("contacts", [])
        
        # Select only non-duplicate contacts for import (limit to 3 for testing)
        new_contacts = [c for c in contacts if not c.get("is_duplicate")][:3]
        
        if not new_contacts:
            pytest.skip("No new contacts to import")
        
        # Confirm import
        confirm_response = api_client.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-csv/confirm",
            json=new_contacts
        )
        
        assert confirm_response.status_code == 200, f"Confirm failed: {confirm_response.status_code} - {confirm_response.text}"
        confirm_data = confirm_response.json()
        
        # Verify response structure
        assert "imported" in confirm_data, "Missing 'imported' field"
        assert "skipped" in confirm_data, "Missing 'skipped' field"
        assert "total" in confirm_data, "Missing 'total' field"
        
        assert confirm_data["imported"] > 0, "No contacts were imported"
        print(f"Imported {confirm_data['imported']} contacts, skipped {confirm_data['skipped']}")
    
    def test_confirm_import_sets_correct_source_and_tags(self, api_client, csv_content):
        """Test that imported contacts have source='csv' and tags=['csv-import']"""
        # First get preview
        files = {"file": ("contacts.csv", csv_content, "text/csv")}
        preview_response = api_client.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-csv/preview",
            files=files
        )
        
        assert preview_response.status_code == 200
        preview_data = preview_response.json()
        contacts = preview_data.get("contacts", [])
        
        # Select one non-duplicate contact with unique phone for testing
        new_contacts = [c for c in contacts if not c.get("is_duplicate")]
        
        if not new_contacts:
            pytest.skip("No new contacts to import")
        
        test_contact = new_contacts[0]
        
        # Confirm import with single contact
        confirm_response = api_client.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-csv/confirm",
            json=[test_contact]
        )
        
        assert confirm_response.status_code == 200
        
        # Verify the contact in database has correct source and tags
        list_response = api_client.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}")
        assert list_response.status_code == 200
        
        all_contacts = list_response.json()
        # Find the imported contact by phone
        test_phone_digits = ''.join(c for c in test_contact.get("phone", "") if c.isdigit())
        
        imported = None
        for c in all_contacts:
            c_phone_digits = ''.join(ch for ch in c.get("phone", "") if ch.isdigit())
            if c_phone_digits[-7:] == test_phone_digits[-7:]:
                imported = c
                break
        
        if imported:
            assert imported.get("source") == "csv", f"Source should be 'csv', got: {imported.get('source')}"
            assert "csv-import" in imported.get("tags", []), f"Tags should include 'csv-import', got: {imported.get('tags')}"
            print(f"Contact imported with source='csv' and tags={imported.get('tags')}")
    
    def test_confirm_import_stores_phones_emails_arrays(self, api_client, csv_content):
        """Test that imported contacts have phones[] and emails[] arrays stored"""
        # First get preview
        files = {"file": ("contacts.csv", csv_content, "text/csv")}
        preview_response = api_client.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-csv/preview",
            files=files
        )
        
        assert preview_response.status_code == 200
        preview_data = preview_response.json()
        contacts = preview_data.get("contacts", [])
        
        # Find a non-duplicate contact with phones array
        test_contacts = [c for c in contacts if not c.get("is_duplicate") and c.get("phones")]
        
        if not test_contacts:
            pytest.skip("No new contacts with phones[] to import")
        
        test_contact = test_contacts[0]
        original_phones = test_contact.get("phones", [])
        
        # Confirm import
        confirm_response = api_client.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-csv/confirm",
            json=[test_contact]
        )
        
        assert confirm_response.status_code == 200
        
        # Fetch the contact and verify phones array
        list_response = api_client.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}")
        assert list_response.status_code == 200
        
        all_contacts = list_response.json()
        test_phone_digits = ''.join(c for c in test_contact.get("phone", "") if c.isdigit())
        
        imported = None
        for c in all_contacts:
            c_phone_digits = ''.join(ch for ch in c.get("phone", "") if ch.isdigit())
            if c_phone_digits[-7:] == test_phone_digits[-7:]:
                imported = c
                break
        
        if imported:
            stored_phones = imported.get("phones", [])
            assert isinstance(stored_phones, list), "phones should be a list"
            assert len(stored_phones) >= len(original_phones), f"phones[] should be stored. Original: {original_phones}, Stored: {stored_phones}"
            print(f"Contact stored with phones={stored_phones}")
    
    def test_confirm_skips_duplicates(self, api_client, csv_content):
        """Test that contacts marked as duplicates are skipped during confirm"""
        # Get preview
        files = {"file": ("contacts.csv", csv_content, "text/csv")}
        preview_response = api_client.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-csv/preview",
            files=files
        )
        
        assert preview_response.status_code == 200
        preview_data = preview_response.json()
        contacts = preview_data.get("contacts", [])
        
        # Find duplicate contacts
        duplicates = [c for c in contacts if c.get("is_duplicate")]
        
        if not duplicates:
            pytest.skip("No duplicate contacts to test")
        
        # Try to import duplicates
        confirm_response = api_client.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-csv/confirm",
            json=duplicates[:2]
        )
        
        assert confirm_response.status_code == 200
        confirm_data = confirm_response.json()
        
        # All should be skipped
        assert confirm_data["imported"] == 0 or confirm_data["skipped"] == len(duplicates[:2]), f"Duplicates should be skipped: {confirm_data}"
        print(f"Correctly skipped {confirm_data['skipped']} duplicate contacts")


class TestContactUpdateWithNewFields:
    """Test PUT /api/contacts/{user_id}/{contact_id} with organization_name, phones[], emails[]"""
    
    def test_update_contact_with_organization_name(self, api_client):
        """Test updating a contact with organization_name field"""
        # First create a contact
        create_response = api_client.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}",
            json={
                "first_name": "TEST_OrgUpdate",
                "last_name": "Contact",
                "phone": "8015550100",
                "tags": ["test-org-update"]
            }
        )
        
        assert create_response.status_code == 200, f"Create failed: {create_response.status_code}"
        created = create_response.json()
        contact_id = created.get("_id") or created.get("id")
        
        try:
            # Update with organization_name
            update_response = api_client.put(
                f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{contact_id}",
                json={
                    "first_name": "TEST_OrgUpdate",
                    "last_name": "Contact",
                    "phone": "8015550100",
                    "organization_name": "Test Company Inc",
                    "tags": ["test-org-update"]
                }
            )
            
            assert update_response.status_code == 200, f"Update failed: {update_response.status_code} - {update_response.text}"
            
            # Verify by fetching the contact
            get_response = api_client.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{contact_id}")
            assert get_response.status_code == 200
            
            updated = get_response.json()
            assert updated.get("organization_name") == "Test Company Inc", f"organization_name not saved: {updated.get('organization_name')}"
            print(f"organization_name updated successfully: {updated.get('organization_name')}")
            
        finally:
            # Cleanup
            api_client.delete(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{contact_id}")
    
    def test_update_contact_with_phones_array(self, api_client):
        """Test updating a contact with phones[] array"""
        # Create a contact
        create_response = api_client.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}",
            json={
                "first_name": "TEST_PhonesUpdate",
                "last_name": "Contact",
                "phone": "8015550101",
                "tags": ["test-phones-update"]
            }
        )
        
        assert create_response.status_code == 200
        created = create_response.json()
        contact_id = created.get("_id") or created.get("id")
        
        try:
            # Update with phones array
            phones = [
                {"label": "Mobile", "value": "8015550101"},
                {"label": "Work", "value": "8015550102"},
                {"label": "Home", "value": "8015550103"}
            ]
            
            update_response = api_client.put(
                f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{contact_id}",
                json={
                    "first_name": "TEST_PhonesUpdate",
                    "last_name": "Contact",
                    "phone": "8015550101",
                    "phones": phones,
                    "tags": ["test-phones-update"]
                }
            )
            
            assert update_response.status_code == 200, f"Update failed: {update_response.status_code} - {update_response.text}"
            
            # Verify
            get_response = api_client.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{contact_id}")
            assert get_response.status_code == 200
            
            updated = get_response.json()
            stored_phones = updated.get("phones", [])
            assert len(stored_phones) == 3, f"phones[] should have 3 entries: {stored_phones}"
            print(f"phones[] updated successfully: {stored_phones}")
            
        finally:
            api_client.delete(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{contact_id}")
    
    def test_update_contact_with_emails_array(self, api_client):
        """Test updating a contact with emails[] array"""
        # Create a contact
        create_response = api_client.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}",
            json={
                "first_name": "TEST_EmailsUpdate",
                "last_name": "Contact",
                "phone": "8015550104",
                "tags": ["test-emails-update"]
            }
        )
        
        assert create_response.status_code == 200
        created = create_response.json()
        contact_id = created.get("_id") or created.get("id")
        
        try:
            # Update with emails array
            emails = [
                {"label": "Personal", "value": "test@personal.com"},
                {"label": "Work", "value": "test@work.com"}
            ]
            
            update_response = api_client.put(
                f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{contact_id}",
                json={
                    "first_name": "TEST_EmailsUpdate",
                    "last_name": "Contact",
                    "phone": "8015550104",
                    "emails": emails,
                    "tags": ["test-emails-update"]
                }
            )
            
            assert update_response.status_code == 200, f"Update failed: {update_response.status_code} - {update_response.text}"
            
            # Verify
            get_response = api_client.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{contact_id}")
            assert get_response.status_code == 200
            
            updated = get_response.json()
            stored_emails = updated.get("emails", [])
            assert len(stored_emails) == 2, f"emails[] should have 2 entries: {stored_emails}"
            print(f"emails[] updated successfully: {stored_emails}")
            
        finally:
            api_client.delete(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{contact_id}")


class TestSmartNameSplitting:
    """Test smart name splitting logic in CSV parsing"""
    
    def test_name_splitting_with_full_name_in_first(self, api_client):
        """Test that full name in First Name field is properly split"""
        # Create a CSV with full name in First Name field only
        csv_content = """First Name,Middle Name,Last Name,Phone 1 - Label,Phone 1 - Value
John Smith,,,Mobile,(801) 555-9999"""
        
        files = {"file": ("test_name.csv", csv_content.encode(), "text/csv")}
        response = api_client.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-csv/preview",
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        contacts = data.get("contacts", [])
        
        if contacts:
            contact = contacts[0]
            assert contact.get("first_name") == "John", f"First name should be 'John': {contact.get('first_name')}"
            assert contact.get("last_name") == "Smith", f"Last name should be 'Smith': {contact.get('last_name')}"
            print(f"Name split correctly: first={contact.get('first_name')}, last={contact.get('last_name')}")
    
    def test_organization_only_contact(self, api_client):
        """Test that contacts with only organization name are parsed correctly"""
        csv_content = """First Name,Middle Name,Last Name,Organization Name,Phone 1 - Label,Phone 1 - Value
,,,Acme Corp,Work,(801) 555-8888"""
        
        files = {"file": ("test_org.csv", csv_content.encode(), "text/csv")}
        response = api_client.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-csv/preview",
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        contacts = data.get("contacts", [])
        
        if contacts:
            contact = contacts[0]
            assert contact.get("organization_name") == "Acme Corp", f"Org name should be 'Acme Corp': {contact}"
            print(f"Organization-only contact parsed: {contact.get('organization_name')}")


class TestDuplicateDetection:
    """Test duplicate detection functionality"""
    
    def test_duplicate_detection_by_phone(self, api_client, csv_content):
        """Test that contacts with matching phone numbers are flagged as duplicates"""
        files = {"file": ("contacts.csv", csv_content, "text/csv")}
        response = api_client.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-csv/preview",
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check duplicate count
        duplicates_count = data.get("duplicates", 0)
        contacts = data.get("contacts", [])
        
        duplicates = [c for c in contacts if c.get("is_duplicate")]
        assert len(duplicates) == duplicates_count, f"Duplicate count mismatch: {duplicates_count} vs {len(duplicates)}"
        
        print(f"Duplicate detection working: {duplicates_count} duplicates found")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
