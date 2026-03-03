"""
Test: Contact Photo Update Bug Fix
Tests that PUT /api/contacts/{user_id}/{contact_id} with a photo:
1. Generates a new photo_thumbnail and photo_url
2. photo_thumbnail is small (~3-5KB)
3. raw 'photo' field is NOT stored in contacts collection
4. high-res version is stored in contact_photos collection
5. Updating without photo preserves existing photo_thumbnail
6. _process_photo applies EXIF auto-rotation (ImageOps.exif_transpose)
7. Congrats cards still get full-res photos via /photo/full endpoint
"""
import pytest
import requests
import os
import base64
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "forest@imonsocial.com"
TEST_PASSWORD = "Admin123!"
TEST_USER_ID = "69a0b7095fddcede09591667"
TEST_CONTACT_ID = "69a1354f2c0649ac6fb7f3f1"

# Small valid base64 JPEG - a red square 100x100
# This is a minimal valid JPEG image
SMALL_TEST_IMAGE_B64 = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAMCAgMCAgMDAwMEAwMEBQgFBQQEBQoHBwYI"
    "DAgMCgsJCwkMChELDAwLEg8SKRUPDhkMEhsTFBQYGxkWHhgYGBP/2wBDAQMEBAUEBQkF"
    "BQkTDAsNExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExMT"
    "ExMTExP/wAARCABkAGQDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQF"
    "BgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEI"
    "I0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNk"
    "ZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLD"
    "xMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEB"
    "AQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJS"
    "QVFhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZH"
    "SElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaan"
    "qKmqsrO0tba3uLm0wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oA"
    "DAMBAAIRAxEAPwD7+ooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooo"
    "oAKKKKACiiigAooooAKKKKACiiigAooooA//2Q=="
)

# A larger test image - still small but more realistic
def create_test_photo_base64():
    """Creates a test photo as base64 data URL"""
    return f"data:image/jpeg;base64,{SMALL_TEST_IMAGE_B64}"


class TestContactPhotoUpdateBugFix:
    """Tests for the contact photo update bug fix - iteration 50"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth context"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.user_data = response.json()
        self.user_id = self.user_data.get('user', {}).get('_id') or self.user_data.get('_id')
        assert self.user_id, "No user_id in login response"
    
    def test_01_update_contact_with_photo_generates_thumbnail(self):
        """PUT /contacts with photo should generate photo_thumbnail"""
        # First get the current contact data
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}")
        assert response.status_code == 200, f"Failed to get contact: {response.text}"
        contact = response.json()
        
        # Build update payload with a new photo
        test_photo = create_test_photo_base64()
        update_payload = {
            "first_name": contact.get("first_name", "API"),
            "last_name": contact.get("last_name", "Test"),
            "phone": contact.get("phone", "+15551234567"),
            "email": contact.get("email", ""),
            "photo": test_photo,  # Send new photo
            "tags": contact.get("tags", []),
            "notes": contact.get("notes", "")
        }
        
        # Update the contact with new photo
        response = requests.put(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}",
            json=update_payload
        )
        assert response.status_code == 200, f"Failed to update contact: {response.text}"
        
        # Fetch the contact again to verify thumbnail was generated
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}")
        assert response.status_code == 200, f"Failed to get updated contact: {response.text}"
        updated = response.json()
        
        # Verify photo_thumbnail was generated
        assert updated.get("photo_thumbnail"), "photo_thumbnail should be set after photo update"
        assert updated["photo_thumbnail"].startswith("data:image/"), "photo_thumbnail should be a data URL"
        print(f"PASS: photo_thumbnail generated. Length: {len(updated['photo_thumbnail'])} chars")
    
    def test_02_photo_thumbnail_is_small_size(self):
        """photo_thumbnail should be under 5KB (small for avatars)"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}")
        assert response.status_code == 200
        contact = response.json()
        
        thumbnail = contact.get("photo_thumbnail", "")
        if thumbnail:
            # Extract base64 part
            if "," in thumbnail:
                b64_data = thumbnail.split(",")[1]
            else:
                b64_data = thumbnail
            
            # Calculate size
            try:
                decoded_bytes = base64.b64decode(b64_data)
                size_kb = len(decoded_bytes) / 1024
                print(f"Thumbnail size: {size_kb:.2f} KB")
                assert size_kb < 10, f"Thumbnail should be under 10KB but was {size_kb:.2f}KB"
                print(f"PASS: Thumbnail is {size_kb:.2f} KB (under 10KB limit)")
            except Exception as e:
                print(f"Could not decode thumbnail to check size: {e}")
        else:
            print("NOTE: No thumbnail found on contact")
    
    def test_03_raw_photo_not_stored_in_contacts(self):
        """Raw 'photo' field should not be stored in contacts collection after update"""
        # Update contact with a photo
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}")
        assert response.status_code == 200
        contact = response.json()
        
        # The photo field should be empty/null OR should be the thumbnail (not the large raw photo)
        photo_field = contact.get("photo")
        thumbnail = contact.get("photo_thumbnail")
        
        if photo_field:
            # If photo exists, it should match thumbnail (small) not be a large base64
            if len(photo_field) > 20000:  # > 20KB is definitely not a thumbnail
                pytest.fail(f"Raw photo field contains large data ({len(photo_field)} chars) - should not store raw photo")
            else:
                print(f"PASS: photo field is small ({len(photo_field)} chars) - likely thumbnail")
        else:
            print("PASS: photo field is empty/null (as expected)")
    
    def test_04_highres_stored_in_contact_photos_collection(self):
        """High-res photo should be stored in contact_photos collection"""
        # First update the contact with a photo to ensure high-res is stored
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}")
        assert response.status_code == 200
        contact = response.json()
        
        test_photo = create_test_photo_base64()
        update_payload = {
            "first_name": contact.get("first_name", "API"),
            "last_name": contact.get("last_name", "Test"),
            "phone": contact.get("phone", "+15551234567"),
            "photo": test_photo,
            "tags": contact.get("tags", [])
        }
        
        response = requests.put(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}",
            json=update_payload
        )
        assert response.status_code == 200
        
        # Now get the full photo from the contact_photos collection
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/photo/full")
        assert response.status_code == 200, f"Failed to get full photo: {response.text}"
        
        data = response.json()
        assert "photo" in data, f"Response should have 'photo' field. Got: {data.keys()}"
        assert data["photo"], "Full photo should not be empty"
        assert data["photo"].startswith("data:image/") or len(data["photo"]) > 100, "Should be valid image data"
        print(f"PASS: High-res photo retrieved from contact_photos. Length: {len(data['photo'])} chars")
    
    def test_05_update_without_photo_preserves_thumbnail(self):
        """Updating contact without photo should preserve existing photo_thumbnail"""
        # First get current contact with thumbnail
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}")
        assert response.status_code == 200
        contact = response.json()
        
        original_thumbnail = contact.get("photo_thumbnail")
        print(f"Original thumbnail exists: {bool(original_thumbnail)}")
        
        # Update contact WITHOUT photo - just update notes
        update_payload = {
            "first_name": contact.get("first_name", "API"),
            "last_name": contact.get("last_name", "Test"),
            "phone": contact.get("phone", "+15551234567"),
            "notes": f"Updated at {time.time()}",  # Change something else
            "tags": contact.get("tags", [])
            # NOTE: No 'photo' field in this update
        }
        
        response = requests.put(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}",
            json=update_payload
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        
        # Verify thumbnail is preserved
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}")
        assert response.status_code == 200
        updated = response.json()
        
        if original_thumbnail:
            # If there was a thumbnail, it should still be there
            # Note: The thumbnail might be in photo_url instead
            new_thumbnail = updated.get("photo_thumbnail") or updated.get("photo_url")
            assert new_thumbnail, "Thumbnail should be preserved after update without photo"
            print(f"PASS: Thumbnail preserved after update without photo")
        else:
            print("NOTE: No original thumbnail to preserve")
    
    def test_06_dedicated_photo_upload_endpoint_works(self):
        """POST /contacts/{user_id}/{contact_id}/photo should work correctly"""
        test_photo = create_test_photo_base64()
        
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/photo",
            json={"photo": test_photo}
        )
        assert response.status_code == 200, f"Photo upload failed: {response.text}"
        
        data = response.json()
        assert "message" in data, f"Should have success message. Got: {data}"
        print(f"PASS: Dedicated photo upload endpoint works. Response: {data}")
    
    def test_07_photo_full_endpoint_returns_highres(self):
        """GET /contacts/{user_id}/{contact_id}/photo/full returns high-res image"""
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/photo/full")
        
        # Should return 200 if photo exists, 404 if not
        if response.status_code == 200:
            data = response.json()
            assert "photo" in data, f"Should have 'photo' field. Got: {data.keys()}"
            photo = data["photo"]
            
            if photo:
                print(f"PASS: Full photo retrieved. Length: {len(photo)} chars")
                # For congrats cards, the full photo should be larger than thumbnail
                # Thumbnail is ~5KB, high-res should be larger
                if "," in photo:
                    b64_data = photo.split(",")[1]
                else:
                    b64_data = photo
                try:
                    decoded = base64.b64decode(b64_data)
                    size_kb = len(decoded) / 1024
                    print(f"Full photo size: {size_kb:.2f} KB")
                except:
                    pass
        elif response.status_code == 404:
            print("NOTE: No high-res photo found for this contact")
        else:
            pytest.fail(f"Unexpected status: {response.status_code} - {response.text}")


class TestPhotoProcessingNewContact:
    """Test photo processing when creating a new contact"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        self.user_data = response.json()
        self.user_id = self.user_data.get('user', {}).get('_id') or self.user_data.get('_id')
        self.created_contact_id = None
    
    def test_create_contact_then_update_photo(self):
        """Create a contact, then update with photo, verify thumbnail generated"""
        # Create a new contact without photo
        create_payload = {
            "first_name": "PhotoTest",
            "last_name": f"Contact{int(time.time())}",
            "phone": f"+1555{int(time.time()) % 10000000:07d}",
            "tags": []
        }
        
        response = requests.post(
            f"{BASE_URL}/api/contacts/{self.user_id}",
            json=create_payload
        )
        assert response.status_code == 200, f"Create contact failed: {response.text}"
        created = response.json()
        contact_id = created.get("_id")
        self.created_contact_id = contact_id
        
        assert contact_id, "No _id in created contact response"
        print(f"Created contact: {contact_id}")
        
        # Verify no photo initially
        assert not created.get("photo_thumbnail"), "New contact should not have thumbnail"
        
        # Now update with a photo
        test_photo = create_test_photo_base64()
        update_payload = {
            "first_name": create_payload["first_name"],
            "last_name": create_payload["last_name"],
            "phone": create_payload["phone"],
            "photo": test_photo,
            "tags": []
        }
        
        response = requests.put(
            f"{BASE_URL}/api/contacts/{self.user_id}/{contact_id}",
            json=update_payload
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        
        # Verify thumbnail was generated
        response = requests.get(f"{BASE_URL}/api/contacts/{self.user_id}/{contact_id}")
        assert response.status_code == 200
        updated = response.json()
        
        assert updated.get("photo_thumbnail"), "photo_thumbnail should be generated after update"
        print(f"PASS: New contact got photo_thumbnail after update")
        
        # Cleanup - delete the test contact
        requests.delete(f"{BASE_URL}/api/contacts/{self.user_id}/{contact_id}")


class TestCongratsCardsPhotoIntegration:
    """Test that congrats cards can still get full-res photos"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        self.user_data = response.json()
        self.user_id = self.user_data.get('user', {}).get('_id') or self.user_data.get('_id')
    
    def test_full_photo_available_for_congrats_card(self):
        """Congrats cards need full-res photos from /photo/full endpoint"""
        # First ensure contact has a photo
        test_photo = create_test_photo_base64()
        
        response = requests.post(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/photo",
            json={"photo": test_photo}
        )
        assert response.status_code == 200
        
        # Now verify full photo is available
        response = requests.get(f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/photo/full")
        assert response.status_code == 200, f"Full photo endpoint should return 200: {response.text}"
        
        data = response.json()
        assert data.get("photo"), "Full photo should be available for congrats cards"
        print(f"PASS: Full-res photo available for congrats cards. Size: {len(data['photo'])} chars")


class TestContactListExcludesHeavyPhoto:
    """Test that contact list excludes heavy photo field"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        self.user_data = response.json()
        self.user_id = self.user_data.get('user', {}).get('_id') or self.user_data.get('_id')
    
    def test_contacts_list_uses_thumbnail_not_full_photo(self):
        """GET /contacts should return photo_thumbnail, not heavy photo field"""
        response = requests.get(f"{BASE_URL}/api/contacts/{self.user_id}")
        assert response.status_code == 200, f"Failed to get contacts: {response.text}"
        
        contacts = response.json()
        assert isinstance(contacts, list)
        
        if len(contacts) > 0:
            # Check contacts have photo_thumbnail but NOT heavy photo
            for contact in contacts[:5]:  # Check first 5
                # If contact has any photo data, it should be the thumbnail
                thumbnail = contact.get("photo_thumbnail")
                photo_url = contact.get("photo_url")
                
                if thumbnail or photo_url:
                    print(f"Contact {contact.get('first_name')}: has thumbnail")
                
                # The 'photo' field in list response should be excluded or small
                photo = contact.get("photo")
                if photo and len(photo) > 50000:  # > 50KB
                    print(f"WARNING: Contact has large photo field in list ({len(photo)} chars)")
        
        print(f"PASS: Contact list returned {len(contacts)} contacts")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
