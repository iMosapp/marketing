"""
Test VCF (vCard) Import Functionality
=====================================
Tests the new VCF import parsing capabilities added alongside the existing CSV import.
Covers:
- POST /api/contacts/{user_id}/import-vcf/preview - VCF file parsing
- POST /api/contacts/{user_id}/import/preview - Auto-detect CSV vs VCF
- VCF field extraction: N, FN, TEL, EMAIL, ORG, TITLE, BDAY, ADR, NOTE
- Phone label priority: Mobile/Cell > pref > Work > Home
- Duplicate detection for VCF imports
- ownership_type='personal' for imported contacts
"""
import pytest
import requests
import os
import io
import tempfile

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
TEST_USER_ID = "69a0b7095fddcede09591667"
AUTH_EMAIL = "forest@imosapp.com"
AUTH_PASSWORD = "Admin123!"

# Sample VCF test files
VCF_SINGLE_CONTACT = """BEGIN:VCARD
VERSION:3.0
N:Jenkins;Aaron;;;
FN:Aaron Jenkins
TEL;type=CELL;type=VOICE;type=pref:(555) 123-4567
TEL;type=WORK;type=VOICE:(555) 987-6543
TEL;type=HOME;type=VOICE:(555) 111-2222
EMAIL;type=INTERNET;type=HOME;type=pref:aaron@home.com
EMAIL;type=INTERNET;type=WORK:aaron@work.com
ORG:Jenkins Consulting;
TITLE:Senior Consultant
BDAY:1985-06-15
ADR;type=HOME;type=pref:;;123 Main Street;Springfield;IL;62701;USA
NOTE:Met at conference 2024
END:VCARD
"""

VCF_APPLE_FORMAT = """BEGIN:VCARD
VERSION:3.0
N:Smith;John;;;
FN:John Smith
item1.TEL;type=CELL;type=VOICE;type=pref:(555) 222-3333
item1.X-ABLabel:Mobile
item2.TEL;type=WORK;type=VOICE:(555) 444-5555
item2.X-ABLabel:Work
item3.EMAIL;type=INTERNET;type=HOME;type=pref:john@personal.com
item3.X-ABLabel:Home
ORG:Smith Industries;
TITLE:CEO
END:VCARD
"""

VCF_MULTIPLE_CONTACTS = """BEGIN:VCARD
VERSION:3.0
N:Doe;Jane;;;
FN:Jane Doe
TEL;type=CELL:(555) 111-1111
EMAIL;type=INTERNET:jane@example.com
ORG:Doe Corp;
END:VCARD
BEGIN:VCARD
VERSION:3.0
N:Brown;Bob;;;
FN:Bob Brown
TEL;type=WORK:(555) 222-2222
TEL;type=HOME:(555) 333-3333
EMAIL;type=INTERNET:bob@example.com
END:VCARD
BEGIN:VCARD
VERSION:3.0
N:Wilson;Mary;;;
FN:Mary Wilson
TEL;type=HOME;type=pref:(555) 444-4444
EMAIL;type=INTERNET:mary@example.com
ORG:Wilson LLC;
TITLE:Manager
BDAY:1990-03-20
NOTE:VIP Client
END:VCARD
"""

VCF_WORK_ONLY_PHONE = """BEGIN:VCARD
VERSION:3.0
N:Worker;Bill;;;
FN:Bill Worker
TEL;type=WORK;type=VOICE:(555) 999-8888
EMAIL;type=INTERNET:bill@workonly.com
END:VCARD
"""

VCF_HOME_ONLY_PHONE = """BEGIN:VCARD
VERSION:3.0
N:Homer;Test;;;
FN:Test Homer
TEL;type=HOME;type=VOICE:(555) 777-6666
EMAIL;type=INTERNET:test@homeonly.com
END:VCARD
"""

VCF_PREF_MARKED_PHONE = """BEGIN:VCARD
VERSION:3.0
N:Prefer;Test;;;
FN:Test Prefer
TEL;type=HOME;type=pref:(555) 111-0000
TEL;type=WORK:(555) 222-0000
EMAIL;type=INTERNET:test@pref.com
END:VCARD
"""

VCF_NO_NAME_ONLY_ORG = """BEGIN:VCARD
VERSION:3.0
N:;;;;
FN:
ORG:Anonymous Company;
TEL;type=WORK:(555) 000-1111
EMAIL;type=INTERNET:info@anonymous.com
END:VCARD
"""

VCF_CONTACT_NO_PHONE_NO_EMAIL = """BEGIN:VCARD
VERSION:3.0
N:Empty;Contact;;;
FN:Contact Empty
ORG:Some Org;
END:VCARD
"""

VCF_BIRTHDAY_FORMATS = """BEGIN:VCARD
VERSION:3.0
N:Birthday;Test;;;
FN:Test Birthday
TEL;type=CELL:(555) 888-9999
BDAY:1975-06-26
END:VCARD
BEGIN:VCARD
VERSION:3.0
N:Birthday2;Test;;;
FN:Test Birthday2
TEL;type=CELL:(555) 888-0000
BDAY;value=date:1962-01-23
END:VCARD
"""

VCF_ADDRESS_FULL = """BEGIN:VCARD
VERSION:3.0
N:Address;Full;;;
FN:Full Address
TEL;type=CELL:(555) 555-5555
ADR;type=HOME:PO Box 100;;456 Oak Avenue;Chicago;IL;60601;United States
END:VCARD
"""


class TestVCFImportPreview:
    """Tests for the VCF preview endpoint: POST /api/contacts/{user_id}/import-vcf/preview"""

    def test_vcf_preview_basic_contact(self):
        """Test VCF preview parses a single contact with all fields correctly"""
        files = {'file': ('test.vcf', VCF_SINGLE_CONTACT, 'text/vcard')}
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-vcf/preview",
            files=files
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data['total_parsed'] >= 1, "Should parse at least 1 contact"
        assert data['source'] == 'vcf', "Source should be 'vcf'"
        
        # Find the contact
        contacts = data['contacts']
        assert len(contacts) >= 1, "Should have at least one contact"
        
        contact = contacts[0]
        # Name extraction from N: field
        assert contact['first_name'] == 'Aaron', f"First name should be 'Aaron', got {contact['first_name']}"
        assert contact['last_name'] == 'Jenkins', f"Last name should be 'Jenkins', got {contact['last_name']}"
        
        # Organization
        assert contact['organization_name'] == 'Jenkins Consulting', f"Org should be 'Jenkins Consulting', got {contact['organization_name']}"
        assert contact['employer'] == 'Jenkins Consulting'
        
        # Title/Occupation
        assert contact['occupation'] == 'Senior Consultant', f"Occupation should be 'Senior Consultant', got {contact['occupation']}"
        
        # Birthday
        assert contact['birthday'] is not None, "Birthday should be parsed"
        assert '1985-06-15' in contact['birthday'], f"Birthday should contain 1985-06-15, got {contact['birthday']}"
        
        # Notes
        assert contact['notes'] == 'Met at conference 2024', f"Notes should match, got {contact['notes']}"
        
        # Address
        assert contact['address_street'] is not None, "Street should be parsed"
        assert 'Main Street' in contact['address_street'], f"Street should contain 'Main Street', got {contact['address_street']}"
        assert contact['address_city'] == 'Springfield'
        assert contact['address_state'] == 'IL'
        assert contact['address_zip'] == '62701'
        assert contact['address_country'] == 'USA'
        
        print("PASS: VCF basic contact parsing with all fields")

    def test_vcf_preview_phone_priority_mobile(self):
        """Test that Mobile/Cell phone is selected as primary over Work/Home"""
        files = {'file': ('test.vcf', VCF_SINGLE_CONTACT, 'text/vcard')}
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-vcf/preview",
            files=files
        )
        assert response.status_code == 200
        
        contact = response.json()['contacts'][0]
        # CELL phone should be primary (555-123-4567 normalized)
        assert contact['phone'] == '15551234567', f"Primary phone should be mobile, got {contact['phone']}"
        
        # Check phones array has all 3 phones
        assert len(contact['phones']) == 3, f"Should have 3 phones, got {len(contact['phones'])}"
        
        # Verify labels
        labels = [p['label'] for p in contact['phones']]
        assert 'Mobile' in labels, "Should have Mobile label"
        assert 'Work' in labels, "Should have Work label"
        assert 'Home' in labels, "Should have Home label"
        
        print("PASS: Phone priority correctly selects Mobile as primary")

    def test_vcf_preview_phone_priority_work_over_home(self):
        """Test Work phone is selected over Home when no Mobile exists"""
        files = {'file': ('test.vcf', VCF_WORK_ONLY_PHONE, 'text/vcard')}
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-vcf/preview",
            files=files
        )
        assert response.status_code == 200
        
        contact = response.json()['contacts'][0]
        # Work phone should be primary
        assert contact['phone'] == '15559998888', f"Primary should be work phone, got {contact['phone']}"
        
        print("PASS: Work phone selected as primary when no Mobile")

    def test_vcf_preview_phone_priority_home_only(self):
        """Test Home phone is used when it's the only phone"""
        files = {'file': ('test.vcf', VCF_HOME_ONLY_PHONE, 'text/vcard')}
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-vcf/preview",
            files=files
        )
        assert response.status_code == 200
        
        contact = response.json()['contacts'][0]
        assert contact['phone'] == '15557776666', f"Primary should be home phone, got {contact['phone']}"
        
        print("PASS: Home phone selected when only option")

    def test_vcf_preview_phone_priority_work_over_home_pref(self):
        """Test Work phone is selected over Home+pref (work is higher in priority list)"""
        files = {'file': ('test.vcf', VCF_PREF_MARKED_PHONE, 'text/vcard')}
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-vcf/preview",
            files=files
        )
        assert response.status_code == 200
        
        contact = response.json()['contacts'][0]
        # Work should be selected because priority is: mobile > cell > main > work > home
        # 'pref' is only a fallback when no priority labels match
        assert contact['phone'] == '15552220000', f"Work phone should be primary (higher priority than home), got {contact['phone']}"
        
        print("PASS: Work phone selected over Home+pref correctly")

    def test_vcf_preview_multiple_emails(self):
        """Test multiple emails are parsed with labels"""
        files = {'file': ('test.vcf', VCF_SINGLE_CONTACT, 'text/vcard')}
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-vcf/preview",
            files=files
        )
        assert response.status_code == 200
        
        contact = response.json()['contacts'][0]
        assert len(contact['emails']) == 2, f"Should have 2 emails, got {len(contact['emails'])}"
        
        # Primary email should be home (Personal > Home > Work priority)
        assert contact['email'] == 'aaron@home.com', f"Primary email should be home, got {contact['email']}"
        
        email_values = [e['value'] for e in contact['emails']]
        assert 'aaron@home.com' in email_values
        assert 'aaron@work.com' in email_values
        
        print("PASS: Multiple emails parsed correctly with proper priority")

    def test_vcf_preview_apple_format_item_prefix(self):
        """Test Apple VCF format with item1.TEL prefix is parsed correctly"""
        files = {'file': ('test.vcf', VCF_APPLE_FORMAT, 'text/vcard')}
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-vcf/preview",
            files=files
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data['total_parsed'] == 1
        
        contact = data['contacts'][0]
        assert contact['first_name'] == 'John'
        assert contact['last_name'] == 'Smith'
        
        # Phone should be parsed even with item1. prefix
        assert contact['phone'], "Phone should be extracted from item1.TEL"
        assert len(contact['phones']) == 2, f"Should have 2 phones, got {len(contact['phones'])}"
        
        # Email with item3. prefix
        assert contact['email'] == 'john@personal.com'
        
        print("PASS: Apple VCF format with item prefix parsed correctly")

    def test_vcf_preview_multiple_contacts(self):
        """Test parsing multiple vCards in single file"""
        files = {'file': ('test.vcf', VCF_MULTIPLE_CONTACTS, 'text/vcard')}
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-vcf/preview",
            files=files
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data['total_parsed'] == 3, f"Should parse 3 contacts, got {data['total_parsed']}"
        
        first_names = [c['first_name'] for c in data['contacts']]
        assert 'Jane' in first_names
        assert 'Bob' in first_names
        assert 'Mary' in first_names
        
        print("PASS: Multiple vCards in single file parsed correctly")

    def test_vcf_preview_organization_only_contact(self):
        """Test contact with only organization name (no first/last name)"""
        files = {'file': ('test.vcf', VCF_NO_NAME_ONLY_ORG, 'text/vcard')}
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-vcf/preview",
            files=files
        )
        assert response.status_code == 200
        
        data = response.json()
        # Contact should still be included because it has org + phone/email
        assert data['total_parsed'] >= 1, "Org-only contact should be parsed"
        
        contact = data['contacts'][0]
        assert contact['organization_name'] == 'Anonymous Company'
        
        print("PASS: Organization-only contact parsed correctly")

    def test_vcf_preview_skips_contact_no_phone_no_email(self):
        """Test contacts without phone AND email are skipped"""
        files = {'file': ('test.vcf', VCF_CONTACT_NO_PHONE_NO_EMAIL, 'text/vcard')}
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-vcf/preview",
            files=files
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data['total_parsed'] == 0, "Contact with no phone/email should be skipped"
        assert data['skipped_no_info'] == 1, f"Should report 1 skipped, got {data['skipped_no_info']}"
        
        print("PASS: Contacts without phone/email are skipped")

    def test_vcf_preview_birthday_formats(self):
        """Test various birthday formats are parsed correctly"""
        files = {'file': ('test.vcf', VCF_BIRTHDAY_FORMATS, 'text/vcard')}
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-vcf/preview",
            files=files
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data['total_parsed'] == 2
        
        # First contact: BDAY:1975-06-26
        contact1 = data['contacts'][0]
        assert contact1['birthday'] is not None
        assert '1975-06-26' in contact1['birthday']
        
        # Second contact: BDAY;value=date:1962-01-23
        contact2 = data['contacts'][1]
        assert contact2['birthday'] is not None
        assert '1962-01-23' in contact2['birthday']
        
        print("PASS: Birthday formats parsed correctly")

    def test_vcf_preview_full_address(self):
        """Test full ADR field parsing including PO Box"""
        files = {'file': ('test.vcf', VCF_ADDRESS_FULL, 'text/vcard')}
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-vcf/preview",
            files=files
        )
        assert response.status_code == 200
        
        contact = response.json()['contacts'][0]
        # ADR format: PO Box;Extended;Street;City;State;ZIP;Country
        assert 'PO Box 100' in contact['address_street'], f"Should include PO Box, got {contact['address_street']}"
        assert 'Oak Avenue' in contact['address_street'], f"Should include street, got {contact['address_street']}"
        assert contact['address_city'] == 'Chicago'
        assert contact['address_state'] == 'IL'
        assert contact['address_zip'] == '60601'
        assert contact['address_country'] == 'United States'
        
        print("PASS: Full address with PO Box parsed correctly")

    def test_vcf_preview_rejects_non_vcf_file(self):
        """Test that non-VCF file is rejected"""
        files = {'file': ('test.csv', 'First Name,Last Name\nJohn,Doe', 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-vcf/preview",
            files=files
        )
        assert response.status_code == 400, f"Should reject CSV file, got {response.status_code}"
        assert 'vcf' in response.json()['detail'].lower()
        
        print("PASS: VCF endpoint rejects non-VCF files")


class TestAutoDetectImport:
    """Tests for auto-detect endpoint: POST /api/contacts/{user_id}/import/preview"""

    def test_autodetect_vcf_file(self):
        """Test auto-detect routes VCF file correctly"""
        files = {'file': ('contacts.vcf', VCF_SINGLE_CONTACT, 'text/vcard')}
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import/preview",
            files=files
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data['source'] == 'vcf', f"Should detect as VCF, got {data['source']}"
        assert data['total_parsed'] >= 1
        
        print("PASS: Auto-detect correctly routes VCF file")

    def test_autodetect_vcard_extension(self):
        """Test auto-detect handles .vcard extension"""
        files = {'file': ('contacts.vcard', VCF_SINGLE_CONTACT, 'text/vcard')}
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import/preview",
            files=files
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data['source'] == 'vcf', f"Should detect as VCF, got {data['source']}"
        
        print("PASS: Auto-detect handles .vcard extension")

    def test_autodetect_csv_file(self):
        """Test auto-detect routes CSV file correctly"""
        csv_content = "First Name,Last Name,Phone 1 - Value,E-mail 1 - Value\nJohn,Doe,(555) 123-4567,john@test.com"
        files = {'file': ('contacts.csv', csv_content, 'text/csv')}
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import/preview",
            files=files
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data['source'] == 'csv', f"Should detect as CSV, got {data['source']}"
        
        print("PASS: Auto-detect correctly routes CSV file")

    def test_autodetect_rejects_unsupported(self):
        """Test auto-detect rejects unsupported file types"""
        files = {'file': ('contacts.txt', 'some text content', 'text/plain')}
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import/preview",
            files=files
        )
        assert response.status_code == 400
        assert 'unsupported' in response.json()['detail'].lower() or 'csv' in response.json()['detail'].lower()
        
        print("PASS: Auto-detect rejects unsupported file types")


class TestVCFDuplicateDetection:
    """Tests for duplicate detection with VCF imports"""

    def test_vcf_duplicate_detection_by_phone(self):
        """Test that existing contacts are marked as duplicates"""
        # First, create a contact with a known phone
        create_response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}",
            json={
                "first_name": "TEST_Existing",
                "last_name": "Contact",
                "phone": "15559991234",
                "email": "test_existing_vcf@test.com"
            }
        )
        
        created_id = None
        if create_response.status_code == 200:
            created_id = create_response.json().get('id')
        
        try:
            # Now preview a VCF with same phone number
            vcf_with_dupe = """BEGIN:VCARD
VERSION:3.0
N:Duplicate;Test;;;
FN:Test Duplicate
TEL;type=CELL:(555) 999-1234
EMAIL;type=INTERNET:different@email.com
END:VCARD
"""
            files = {'file': ('test.vcf', vcf_with_dupe, 'text/vcard')}
            response = requests.post(
                f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-vcf/preview",
                files=files
            )
            assert response.status_code == 200
            
            data = response.json()
            assert data['duplicates'] >= 1, f"Should detect duplicate, got duplicates={data['duplicates']}"
            
            contact = data['contacts'][0]
            assert contact['is_duplicate'] == True, "Contact should be marked as duplicate"
            
            print("PASS: Duplicate detection by phone works for VCF")
        finally:
            # Cleanup
            if created_id:
                requests.delete(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{created_id}")


class TestVCFImportConfirm:
    """Tests for importing VCF-previewed contacts via the confirm endpoint"""

    def test_vcf_import_confirm_creates_contacts(self):
        """Test VCF-previewed contacts can be imported via confirm endpoint"""
        import random
        unique_id = random.randint(10000, 99999)
        
        # First preview
        files = {'file': ('test.vcf', VCF_SINGLE_CONTACT, 'text/vcard')}
        preview_response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-vcf/preview",
            files=files
        )
        assert preview_response.status_code == 200
        
        contacts = preview_response.json()['contacts']
        # Modify to avoid duplicates - use unique phone
        contacts[0]['phone'] = f'1555{unique_id}01'
        contacts[0]['email'] = f'test_vcf_import_{unique_id}@test.com'
        contacts[0]['first_name'] = 'TEST_VCFImport'
        contacts[0]['is_duplicate'] = False  # Ensure not marked as duplicate
        
        # Now confirm import
        confirm_response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-csv/confirm",
            json=contacts
        )
        assert confirm_response.status_code == 200
        
        result = confirm_response.json()
        assert result['imported'] >= 1, f"Should import at least 1 contact, got {result['imported']}"
        
        # Cleanup - delete the imported contact
        list_response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}")
        if list_response.status_code == 200:
            contacts_list = list_response.json()  # Returns list directly
            for c in contacts_list:
                if c.get('first_name') == 'TEST_VCFImport':
                    requests.delete(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{c['_id']}")
        
        print("PASS: VCF-previewed contacts imported successfully")

    def test_vcf_import_sets_ownership_type_personal(self):
        """Test imported VCF contacts have ownership_type='personal'"""
        import random
        unique_id = random.randint(10000, 99999)
        
        # Preview and modify for unique test
        files = {'file': ('test.vcf', VCF_SINGLE_CONTACT, 'text/vcard')}
        preview_response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-vcf/preview",
            files=files
        )
        assert preview_response.status_code == 200
        
        contacts = preview_response.json()['contacts']
        contacts[0]['phone'] = f'1555{unique_id}02'
        contacts[0]['email'] = f'test_ownership_{unique_id}@test.com'
        contacts[0]['first_name'] = 'TEST_Ownership'
        contacts[0]['is_duplicate'] = False
        
        # Import
        confirm_response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-csv/confirm",
            json=contacts
        )
        assert confirm_response.status_code == 200
        
        # Fetch the contact and verify ownership_type
        list_response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}")
        
        contact_id = None
        if list_response.status_code == 200:
            contacts_list = list_response.json()  # Returns list directly
            for c in contacts_list:
                if c.get('first_name') == 'TEST_Ownership':
                    contact_id = c['_id']
                    # Check ownership_type
                    assert c.get('ownership_type') == 'personal', f"ownership_type should be 'personal', got {c.get('ownership_type')}"
                    break
        
        assert contact_id is not None, "Imported contact not found"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{contact_id}")
        
        print("PASS: VCF imports set ownership_type to personal")

    def test_vcf_import_sets_source_and_tags(self):
        """Test imported VCF contacts have source='csv' and tags=['csv-import']"""
        import random
        unique_id = random.randint(10000, 99999)
        
        files = {'file': ('test.vcf', VCF_SINGLE_CONTACT, 'text/vcard')}
        preview_response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-vcf/preview",
            files=files
        )
        assert preview_response.status_code == 200
        
        contacts = preview_response.json()['contacts']
        contacts[0]['phone'] = f'1555{unique_id}03'
        contacts[0]['email'] = f'test_source_{unique_id}@test.com'
        contacts[0]['first_name'] = 'TEST_Source'
        contacts[0]['is_duplicate'] = False
        
        # Import
        confirm_response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-csv/confirm",
            json=contacts
        )
        assert confirm_response.status_code == 200
        
        # Find and verify
        list_response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}")
        contact_id = None
        if list_response.status_code == 200:
            contacts_list = list_response.json()  # Returns list directly
            for c in contacts_list:
                if c.get('first_name') == 'TEST_Source':
                    contact_id = c['_id']
                    assert c.get('source') == 'csv', f"Source should be 'csv', got {c.get('source')}"
                    assert 'csv-import' in c.get('tags', []), f"Tags should include 'csv-import', got {c.get('tags')}"
                    break
        
        assert contact_id is not None, "Imported contact not found"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{contact_id}")
        
        print("PASS: VCF imports have correct source and tags")


class TestRealVCFFile:
    """Test with the real VCF file URL provided"""

    def test_real_vcf_file_from_url(self):
        """Test parsing the real Apple VCF file (1208 contacts)"""
        vcf_url = "https://customer-assets.emergentagent.com/job_0e985e85-6651-4df7-92c1-4c74ea78aa26/artifacts/u3ek6701_Aaron%20Jenkins%20SS%20and%201207%20others.vcf"
        
        # Download the VCF file
        download_response = requests.get(vcf_url)
        assert download_response.status_code == 200, f"Failed to download VCF file: {download_response.status_code}"
        
        vcf_content = download_response.content
        
        # Preview the VCF
        files = {'file': ('contacts.vcf', vcf_content, 'text/vcard')}
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/import-vcf/preview",
            files=files
        )
        assert response.status_code == 200, f"VCF preview failed: {response.status_code} - {response.text}"
        
        data = response.json()
        # The file should have ~1208 contacts, but some may be skipped
        assert data['total_parsed'] > 100, f"Should parse many contacts, got {data['total_parsed']}"
        
        print(f"Real VCF file stats:")
        print(f"  - Total parsed: {data['total_parsed']}")
        print(f"  - New contacts: {data['new_contacts']}")
        print(f"  - Duplicates: {data['duplicates']}")
        print(f"  - Skipped (no info): {data['skipped_no_info']}")
        
        # Verify a sample contact has expected fields
        if data['contacts']:
            sample = data['contacts'][0]
            print(f"  - Sample contact: {sample.get('first_name')} {sample.get('last_name')}")
            assert 'first_name' in sample
            assert 'last_name' in sample
            assert 'phone' in sample
            assert 'phones' in sample
            assert 'emails' in sample
        
        print("PASS: Real VCF file parsed successfully")


# Cleanup fixture to remove test contacts after all tests
@pytest.fixture(scope="module", autouse=True)
def cleanup_test_contacts():
    """Cleanup TEST_ prefixed contacts after tests complete"""
    yield
    # Cleanup after all tests
    try:
        # Delete contacts with source='csv' and tag='csv-import' that have TEST_ prefix
        list_response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}?search=TEST_")
        if list_response.status_code == 200:
            contacts = list_response.json().get('contacts', [])
            for c in contacts:
                if c.get('first_name', '').startswith('TEST_'):
                    requests.delete(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{c['id']}")
    except Exception as e:
        print(f"Cleanup warning: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
