"""
Tests for GET /api/profile/{user_id}/vcard.vcf endpoint
Covers: photo embedded as base64 JPEG, no-photo case, MIME type, Content-Disposition, vCard fields
"""
import pytest
import requests
import os
import re
import base64

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


def login(email, password):
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    if resp.status_code == 200:
        return resp.json().get("token")
    return None


def get_user_id_from_login(email, password):
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    if resp.status_code == 200:
        return resp.json().get("user", {}).get("_id")
    return None


@pytest.fixture(scope="module")
def admin_token():
    token = login("forest@imosapp.com", "Admin123!")
    if not token:
        pytest.skip("Admin login failed")
    return token


@pytest.fixture(scope="module")
def admin_user_id():
    uid = get_user_id_from_login("forest@imosapp.com", "Admin123!")
    if not uid:
        pytest.skip("Could not get admin user id")
    return uid


@pytest.fixture(scope="module")
def test_user_id_no_photo():
    """Use the mjeast test user which has no photo"""
    uid = get_user_id_from_login("mjeast1985@gmail.com", "NavyBean1!")
    if not uid:
        pytest.skip("Could not get test user id")
    return uid


class TestVCardNoPhoto:
    """VCard endpoint for user without a photo — must not crash"""

    def test_vcard_returns_200(self, test_user_id_no_photo):
        resp = requests.get(f"{BASE_URL}/api/profile/{test_user_id_no_photo}/vcard.vcf")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        print("PASS: vCard returns 200 for no-photo user")

    def test_vcard_mime_type(self, test_user_id_no_photo):
        resp = requests.get(f"{BASE_URL}/api/profile/{test_user_id_no_photo}/vcard.vcf")
        ct = resp.headers.get("Content-Type", "")
        assert "vcard" in ct.lower() or "text" in ct.lower(), f"Unexpected Content-Type: {ct}"
        print(f"PASS: Content-Type is {ct}")

    def test_vcard_content_disposition(self, test_user_id_no_photo):
        resp = requests.get(f"{BASE_URL}/api/profile/{test_user_id_no_photo}/vcard.vcf")
        cd = resp.headers.get("Content-Disposition", "")
        assert "attachment" in cd.lower(), f"Content-Disposition missing 'attachment': {cd}"
        assert ".vcf" in cd, f"Content-Disposition missing .vcf: {cd}"
        print(f"PASS: Content-Disposition is {cd}")

    def test_vcard_structure_no_photo(self, test_user_id_no_photo):
        resp = requests.get(f"{BASE_URL}/api/profile/{test_user_id_no_photo}/vcard.vcf")
        body = resp.text
        assert "BEGIN:VCARD" in body
        assert "END:VCARD" in body
        assert "VERSION:3.0" in body
        # Note: if user has a photo it will be present; if not, it should be absent but not crash
        print(f"PASS: vCard structure correct. PHOTO present: {'PHOTO' in body}")
        # Endpoint should work regardless of photo presence — no crash is the key assertion here

    def test_vcard_has_url_field(self, test_user_id_no_photo):
        resp = requests.get(f"{BASE_URL}/api/profile/{test_user_id_no_photo}/vcard.vcf")
        body = resp.text
        assert "URL:" in body, "vCard should contain URL field"
        assert test_user_id_no_photo in body, "vCard URL should contain user_id"
        print("PASS: URL field present in vCard")


class TestVCardWithPhoto:
    """VCard endpoint for a user with a photo — PHOTO field must be embedded as base64 JPEG"""

    @pytest.fixture(scope="class")
    def user_with_photo(self, admin_user_id):
        """Admin user already has a photo set in the database"""
        return admin_user_id

    def test_vcard_with_photo_returns_200(self, user_with_photo):
        resp = requests.get(f"{BASE_URL}/api/profile/{user_with_photo}/vcard.vcf")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        print("PASS: vCard returns 200 for user with photo")

    def test_vcard_photo_field_present(self, user_with_photo):
        resp = requests.get(f"{BASE_URL}/api/profile/{user_with_photo}/vcard.vcf")
        body = resp.text
        assert "PHOTO" in body, f"Expected PHOTO field in vCard for user with photo. Body excerpt: {body[:500]}"
        print("PASS: PHOTO field is present in vCard")

    def test_vcard_photo_encoding_format(self, user_with_photo):
        """PHOTO must use PHOTO;ENCODING=b;TYPE=JPEG format (not VALUE=URL)"""
        resp = requests.get(f"{BASE_URL}/api/profile/{user_with_photo}/vcard.vcf")
        body = resp.text
        assert "PHOTO;ENCODING=b;TYPE=JPEG" in body, (
            f"Expected PHOTO;ENCODING=b;TYPE=JPEG in vCard. Body excerpt: {body[:600]}"
        )
        # Must NOT be a URL reference
        assert "PHOTO;VALUE=URL" not in body, "PHOTO should be base64, not a URL reference"
        print("PASS: PHOTO field uses PHOTO;ENCODING=b;TYPE=JPEG format")

    def test_vcard_photo_is_valid_base64(self, user_with_photo):
        """The embedded photo data must be valid base64 that decodes to a JPEG"""
        resp = requests.get(f"{BASE_URL}/api/profile/{user_with_photo}/vcard.vcf")
        body = resp.text

        # Extract base64 data after PHOTO line (folded lines with leading space)
        photo_match = re.search(r"PHOTO;ENCODING=b;TYPE=JPEG:\r?\n?([ \S]+(?:\r?\n [ \S]+)*)", body)
        assert photo_match, "Could not extract PHOTO base64 data from vCard"

        raw_b64 = photo_match.group(1).replace("\r\n ", "").replace("\n ", "").replace(" ", "")
        try:
            img_bytes = base64.b64decode(raw_b64)
        except Exception as e:
            pytest.fail(f"PHOTO base64 data is not valid base64: {e}")

        # Verify it's a JPEG (starts with FFD8FF)
        assert img_bytes[:3] == b'\xff\xd8\xff', f"Decoded photo is not a valid JPEG (magic bytes: {img_bytes[:3].hex()})"
        assert len(img_bytes) > 100, f"Decoded JPEG seems too small: {len(img_bytes)} bytes"
        print(f"PASS: PHOTO field contains valid base64 JPEG ({len(img_bytes)} bytes)")

    def test_vcard_contains_name_and_email(self, user_with_photo):
        resp = requests.get(f"{BASE_URL}/api/profile/{user_with_photo}/vcard.vcf")
        body = resp.text
        assert "FN:" in body, "vCard missing FN (full name) field"
        assert "EMAIL:" in body or "N:" in body, "vCard missing EMAIL or N field"
        print("PASS: vCard contains name and email fields")

    def test_vcard_mime_and_disposition(self, user_with_photo):
        resp = requests.get(f"{BASE_URL}/api/profile/{user_with_photo}/vcard.vcf")
        ct = resp.headers.get("Content-Type", "")
        cd = resp.headers.get("Content-Disposition", "")
        assert "vcard" in ct.lower() or "text" in ct.lower()
        assert "attachment" in cd.lower() and ".vcf" in cd
        print(f"PASS: Content-Type={ct}, Content-Disposition={cd}")


class TestVCardEdgeCases:
    """Edge cases for vCard endpoint"""

    def test_vcard_404_for_invalid_user(self):
        resp = requests.get(f"{BASE_URL}/api/profile/000000000000000000000000/vcard.vcf")
        assert resp.status_code == 404, f"Expected 404 for invalid user, got {resp.status_code}"
        print("PASS: 404 returned for invalid user id")
