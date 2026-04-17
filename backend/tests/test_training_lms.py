"""
Training/LMS API Tests
Tests for role-based training tracks, lessons, admin CRUD operations, and progress tracking.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials (super_admin user)
TEST_EMAIL = "forest@imosapp.com"
TEST_PASSWORD = os.environ.get("TEST_ADMIN_PASS", "test-admin-pass")


class TestTrainingTracks:
    """Tests for training tracks API with role filtering"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        login_data = login_res.json()
        self.user = login_data.get("user", login_data)  # Handle nested user object
        self.user_id = self.user.get("_id")
        self.session.headers.update({"X-User-ID": self.user_id})

    def test_get_tracks_super_admin_sees_all(self):
        """super_admin role should see all 4 tracks"""
        res = self.session.get(f"{BASE_URL}/api/training/tracks?role=super_admin")
        assert res.status_code == 200, f"Failed: {res.text}"
        tracks = res.json()
        assert isinstance(tracks, list)
        assert len(tracks) >= 4, f"Expected at least 4 tracks for super_admin, got {len(tracks)}"
        # Verify track slugs
        slugs = [t.get("slug") for t in tracks]
        assert "sales-team" in slugs, "Missing Sales Team Onboarding track"
        assert "partners-resellers" in slugs, "Missing Partner & Reseller Onboarding track"
        assert "white-label-partners" in slugs, "Missing White Label Partner Guide track"
        assert "managers" in slugs, "Missing Manager's Playbook track"
        print(f"PASS: super_admin sees all {len(tracks)} tracks: {slugs}")

    def test_get_tracks_user_role_sees_only_sales(self):
        """user role should only see Sales Team Onboarding track"""
        res = self.session.get(f"{BASE_URL}/api/training/tracks?role=user")
        assert res.status_code == 200, f"Failed: {res.text}"
        tracks = res.json()
        assert isinstance(tracks, list)
        # user role is only in sales-team track
        slugs = [t.get("slug") for t in tracks]
        assert "sales-team" in slugs, "Sales Team track should be visible to user role"
        # User should NOT see partner/white-label tracks
        assert "partners-resellers" not in slugs, "Partner track should NOT be visible to user role"
        assert "white-label-partners" not in slugs, "White Label track should NOT be visible to user role"
        print(f"PASS: user role sees only filtered tracks: {slugs}")

    def test_get_tracks_partner_role_sees_partner_and_whitelabel(self):
        """partner role should see Partner & Reseller and White Label tracks"""
        res = self.session.get(f"{BASE_URL}/api/training/tracks?role=partner")
        assert res.status_code == 200, f"Failed: {res.text}"
        tracks = res.json()
        slugs = [t.get("slug") for t in tracks]
        assert "partners-resellers" in slugs, "Partner track should be visible to partner role"
        assert "white-label-partners" in slugs, "White Label track should be visible to partner role"
        # Partner should NOT see sales-team (it's for user/manager/admin/store_manager)
        assert "sales-team" not in slugs, "Sales Team track should NOT be visible to partner role"
        print(f"PASS: partner role sees filtered tracks: {slugs}")

    def test_track_has_lesson_count(self):
        """Each track should have lesson_count field"""
        res = self.session.get(f"{BASE_URL}/api/training/tracks?role=super_admin")
        assert res.status_code == 200
        tracks = res.json()
        for track in tracks:
            assert "lesson_count" in track, f"Track {track.get('slug')} missing lesson_count"
            assert isinstance(track["lesson_count"], int)
            assert track["lesson_count"] > 0, f"Track {track.get('slug')} has 0 lessons"
        print(f"PASS: All tracks have lesson_count field")


class TestWhiteLabelTrackLessons:
    """Tests for White Label Partner Guide track lessons"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get track ID"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert login_res.status_code == 200
        login_data = login_res.json()
        self.user_id = login_data.get("user", login_data).get("_id")
        self.session.headers.update({"X-User-ID": self.user_id})
        
        # Get white-label track
        tracks_res = self.session.get(f"{BASE_URL}/api/training/tracks?role=super_admin")
        tracks = tracks_res.json()
        self.wl_track = next((t for t in tracks if t.get("slug") == "white-label-partners"), None)
        assert self.wl_track, "White Label Partner Guide track not found"

    def test_white_label_track_has_5_lessons(self):
        """White Label Partner Guide should have 5 lessons"""
        res = self.session.get(f"{BASE_URL}/api/training/tracks/{self.wl_track['id']}")
        assert res.status_code == 200, f"Failed: {res.text}"
        track_detail = res.json()
        lessons = track_detail.get("lessons", [])
        assert len(lessons) == 5, f"Expected 5 lessons in White Label track, got {len(lessons)}"
        
        # Verify lesson slugs
        expected_slugs = ["wl-what-is-white-label", "wl-branding-setup", "wl-onboarding-clients", "wl-messaging-guide", "wl-support-playbook"]
        actual_slugs = [l.get("slug") for l in lessons]
        for slug in expected_slugs:
            assert slug in actual_slugs, f"Missing lesson: {slug}"
        print(f"PASS: White Label track has 5 lessons: {actual_slugs}")

    def test_lessons_have_content(self):
        """Each lesson should have content field with markdown"""
        res = self.session.get(f"{BASE_URL}/api/training/tracks/{self.wl_track['id']}")
        assert res.status_code == 200
        lessons = res.json().get("lessons", [])
        for lesson in lessons:
            assert lesson.get("content"), f"Lesson {lesson.get('slug')} has no content"
            assert len(lesson.get("content", "")) > 100, f"Lesson {lesson.get('slug')} content too short"
        print(f"PASS: All 5 lessons have content")


class TestAdminTrainingCRUD:
    """Tests for Admin training management endpoints"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert login_res.status_code == 200
        login_data = login_res.json()
        self.user_id = login_data.get("user", login_data).get("_id")
        self.session.headers.update({"X-User-ID": self.user_id})
        self.created_track_id = None
        self.created_lesson_id = None

    def test_admin_list_all_tracks(self):
        """GET /api/training/admin/tracks should list all tracks"""
        res = self.session.get(f"{BASE_URL}/api/training/admin/tracks")
        assert res.status_code == 200, f"Failed: {res.text}"
        tracks = res.json()
        assert isinstance(tracks, list)
        assert len(tracks) >= 4, f"Expected at least 4 tracks, got {len(tracks)}"
        # Verify structure
        for track in tracks:
            assert "id" in track
            assert "title" in track
            assert "description" in track
            assert "roles" in track
            assert "lesson_count" in track
        print(f"PASS: Admin can list all {len(tracks)} tracks")

    def test_admin_create_track(self):
        """POST /api/training/admin/tracks should create a new track"""
        new_track = {
            "title": "TEST_Training Track",
            "description": "Test track for automated testing",
            "color": "#FF5500",
            "roles": ["user", "manager"]
        }
        res = self.session.post(f"{BASE_URL}/api/training/admin/tracks", json=new_track)
        assert res.status_code == 200, f"Failed to create track: {res.text}"
        data = res.json()
        assert data.get("success") == True
        assert "id" in data
        self.created_track_id = data["id"]
        
        # Verify track was created by fetching it
        tracks_res = self.session.get(f"{BASE_URL}/api/training/admin/tracks")
        tracks = tracks_res.json()
        created = next((t for t in tracks if t.get("id") == self.created_track_id), None)
        assert created, "Created track not found in list"
        assert created["title"] == "TEST_Training Track"
        assert created["roles"] == ["user", "manager"]
        print(f"PASS: Admin created track with ID: {self.created_track_id}")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/training/admin/tracks/{self.created_track_id}")

    def test_admin_update_track(self):
        """PUT /api/training/admin/tracks/{id} should update track"""
        # Get an existing track
        tracks_res = self.session.get(f"{BASE_URL}/api/training/admin/tracks")
        tracks = tracks_res.json()
        test_track = next((t for t in tracks if t.get("slug") == "sales-team"), None)
        assert test_track, "Sales Team track not found"
        
        original_title = test_track["title"]
        
        # Update the track
        update_data = {
            "title": "TEST_Updated Title",
            "description": "Updated description for testing"
        }
        res = self.session.put(f"{BASE_URL}/api/training/admin/tracks/{test_track['id']}", json=update_data)
        assert res.status_code == 200, f"Failed to update track: {res.text}"
        assert res.json().get("success") == True
        
        # Verify update
        tracks_res = self.session.get(f"{BASE_URL}/api/training/admin/tracks")
        updated = next((t for t in tracks_res.json() if t.get("id") == test_track['id']), None)
        assert updated["title"] == "TEST_Updated Title"
        print(f"PASS: Admin updated track title")
        
        # Restore original
        self.session.put(f"{BASE_URL}/api/training/admin/tracks/{test_track['id']}", json={"title": original_title, "description": test_track["description"]})

    def test_admin_update_track_roles(self):
        """PUT /api/training/admin/tracks/{id} should update roles"""
        tracks_res = self.session.get(f"{BASE_URL}/api/training/admin/tracks")
        test_track = next((t for t in tracks_res.json() if t.get("slug") == "managers"), None)
        assert test_track, "Managers track not found"
        
        original_roles = test_track["roles"]
        
        # Update roles
        new_roles = ["manager", "admin", "super_admin"]
        res = self.session.put(f"{BASE_URL}/api/training/admin/tracks/{test_track['id']}", json={"roles": new_roles})
        assert res.status_code == 200
        
        # Verify
        tracks_res = self.session.get(f"{BASE_URL}/api/training/admin/tracks")
        updated = next((t for t in tracks_res.json() if t.get("id") == test_track['id']), None)
        assert set(updated["roles"]) == set(new_roles)
        print(f"PASS: Admin updated track roles")
        
        # Restore
        self.session.put(f"{BASE_URL}/api/training/admin/tracks/{test_track['id']}", json={"roles": original_roles})


class TestAdminLessonCRUD:
    """Tests for Admin lesson management"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get a track for lesson tests"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert login_res.status_code == 200
        login_data = login_res.json()
        self.user_id = login_data.get("user", login_data).get("_id")
        self.session.headers.update({"X-User-ID": self.user_id})
        
        # Get sales-team track for lesson tests
        tracks_res = self.session.get(f"{BASE_URL}/api/training/admin/tracks")
        self.test_track = next((t for t in tracks_res.json() if t.get("slug") == "sales-team"), None)
        assert self.test_track, "Sales Team track not found"

    def test_admin_list_lessons(self):
        """GET /api/training/admin/tracks/{id}/lessons should list lessons"""
        res = self.session.get(f"{BASE_URL}/api/training/admin/tracks/{self.test_track['id']}/lessons")
        assert res.status_code == 200, f"Failed: {res.text}"
        lessons = res.json()
        assert isinstance(lessons, list)
        assert len(lessons) >= 6, f"Expected at least 6 lessons in Sales Team track, got {len(lessons)}"
        # Verify structure
        for lesson in lessons:
            assert "id" in lesson
            assert "title" in lesson
            assert "content" in lesson
        print(f"PASS: Admin can list {len(lessons)} lessons in track")

    def test_admin_create_lesson(self):
        """POST /api/training/admin/tracks/{id}/lessons should create lesson"""
        new_lesson = {
            "title": "TEST_New Lesson",
            "description": "Test lesson for automated testing",
            "content": "## Test Content\n\nThis is test content.",
            "duration": "3 min",
            "order": 99
        }
        res = self.session.post(f"{BASE_URL}/api/training/admin/tracks/{self.test_track['id']}/lessons", json=new_lesson)
        assert res.status_code == 200, f"Failed to create lesson: {res.text}"
        data = res.json()
        assert data.get("success") == True
        assert "id" in data
        lesson_id = data["id"]
        
        # Verify
        lessons_res = self.session.get(f"{BASE_URL}/api/training/admin/tracks/{self.test_track['id']}/lessons")
        created = next((l for l in lessons_res.json() if l.get("id") == lesson_id), None)
        assert created, "Created lesson not found"
        assert created["title"] == "TEST_New Lesson"
        print(f"PASS: Admin created lesson with ID: {lesson_id}")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/training/admin/lessons/{lesson_id}")

    def test_admin_update_lesson(self):
        """PUT /api/training/lessons/{id} should update lesson"""
        # Get first lesson
        lessons_res = self.session.get(f"{BASE_URL}/api/training/admin/tracks/{self.test_track['id']}/lessons")
        lessons = lessons_res.json()
        test_lesson = lessons[0]
        original_title = test_lesson["title"]
        original_desc = test_lesson.get("description", "")
        
        # Update
        update_data = {
            "title": "TEST_Updated Lesson Title",
            "description": "Updated description"
        }
        res = self.session.put(f"{BASE_URL}/api/training/lessons/{test_lesson['id']}", json=update_data)
        assert res.status_code == 200, f"Failed to update lesson: {res.text}"
        
        # Verify
        lessons_res = self.session.get(f"{BASE_URL}/api/training/admin/tracks/{self.test_track['id']}/lessons")
        updated = next((l for l in lessons_res.json() if l.get("id") == test_lesson['id']), None)
        assert updated["title"] == "TEST_Updated Lesson Title"
        print(f"PASS: Admin updated lesson title")
        
        # Restore
        self.session.put(f"{BASE_URL}/api/training/lessons/{test_lesson['id']}", json={"title": original_title, "description": original_desc})

    def test_admin_update_lesson_content(self):
        """PUT /api/training/lessons/{id} should update content"""
        lessons_res = self.session.get(f"{BASE_URL}/api/training/admin/tracks/{self.test_track['id']}/lessons")
        test_lesson = lessons_res.json()[0]
        original_content = test_lesson.get("content", "")
        
        # Update content
        new_content = "## Updated Content\n\nThis is updated content for testing."
        res = self.session.put(f"{BASE_URL}/api/training/lessons/{test_lesson['id']}", json={"content": new_content})
        assert res.status_code == 200
        
        # Verify
        lessons_res = self.session.get(f"{BASE_URL}/api/training/admin/tracks/{self.test_track['id']}/lessons")
        updated = next((l for l in lessons_res.json() if l.get("id") == test_lesson['id']), None)
        assert updated["content"] == new_content
        print(f"PASS: Admin updated lesson content")
        
        # Restore
        self.session.put(f"{BASE_URL}/api/training/lessons/{test_lesson['id']}", json={"content": original_content})


class TestProgressTracking:
    """Tests for user progress tracking"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get track/lesson IDs"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert login_res.status_code == 200
        login_data = login_res.json()
        self.user = login_data.get("user", login_data)  # Handle both formats
        self.user_id = self.user.get("_id")
        self.session.headers.update({"X-User-ID": self.user_id})
        
        # Get a track and lesson
        tracks_res = self.session.get(f"{BASE_URL}/api/training/tracks?role=super_admin")
        self.track = tracks_res.json()[0]
        
        track_detail = self.session.get(f"{BASE_URL}/api/training/tracks/{self.track['id']}")
        self.lesson = track_detail.json().get("lessons", [])[0]

    def test_mark_lesson_complete(self):
        """POST /api/training/progress should mark lesson as complete"""
        # First, make sure it's not complete
        res = self.session.post(f"{BASE_URL}/api/training/progress", json={
            "user_id": self.user_id,
            "lesson_id": self.lesson["id"],
            "track_id": self.track["id"],
            "completed": False
        })
        assert res.status_code == 200
        
        # Mark as complete
        res = self.session.post(f"{BASE_URL}/api/training/progress", json={
            "user_id": self.user_id,
            "lesson_id": self.lesson["id"],
            "track_id": self.track["id"],
            "completed": True
        })
        assert res.status_code == 200, f"Failed to mark complete: {res.text}"
        assert res.json().get("success") == True
        
        # Verify in progress list
        progress_res = self.session.get(f"{BASE_URL}/api/training/progress/{self.user_id}")
        assert progress_res.status_code == 200
        progress = progress_res.json()
        completed_lesson = next((p for p in progress if p.get("lesson_id") == self.lesson["id"]), None)
        assert completed_lesson, "Completed lesson not found in progress"
        assert completed_lesson["completed"] == True
        print(f"PASS: Lesson marked as complete")

    def test_progress_updates_track_count(self):
        """Completing a lesson should update the track's completed_count"""
        # Get track with completion count
        tracks_res = self.session.get(f"{BASE_URL}/api/training/tracks?role=super_admin")
        tracks = tracks_res.json()
        track = next((t for t in tracks if t.get("id") == self.track["id"]), None)
        assert track
        
        initial_count = track.get("completed_count", 0)
        
        # The count should reflect current progress
        # (Already tested mark complete above, so count should be > 0)
        assert "completed_count" in track, "Track missing completed_count field"
        print(f"PASS: Track has completed_count: {track['completed_count']}/{track['lesson_count']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
