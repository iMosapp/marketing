"""
Voice Notes API Tests
Tests for voice note recording, transcription, storage, and activity feed integration.

Features tested:
- GET /api/voice-notes/{user_id}/{contact_id} returns array (even if empty)
- POST /api/voice-notes/{user_id}/{contact_id} creates voice note with transcription
- Voice note appears as contact_event with event_type='voice_note'
- DELETE /api/voice-notes/{user_id}/{contact_id}/{note_id} removes voice note
- Duration validation rejects recordings over 120 seconds
"""

import pytest
import requests
import os
import struct
import io

# Get base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_USER_ID = "69a0b7095fddcede09591667"
TEST_CONTACT_ID = "69a1354f2c0649ac6fb7f3f1"

# Create a minimal WAV file for testing (44 byte header with no audio data)
def create_minimal_wav():
    """Create a minimal valid WAV file header for testing"""
    data = b"RIFF" + struct.pack("<I", 36) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, 8000, 8000, 1, 8) + b"data" + struct.pack("<I", 0)
    return data


class TestVoiceNotesAPI:
    """Voice Notes CRUD endpoint tests"""

    def test_get_voice_notes_returns_array(self):
        """GET /api/voice-notes/{user_id}/{contact_id} returns array (even if empty)"""
        response = requests.get(f"{BASE_URL}/api/voice-notes/{TEST_USER_ID}/{TEST_CONTACT_ID}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"GET voice notes returned array with {len(data)} items")

    def test_create_voice_note_success(self):
        """POST /api/voice-notes/{user_id}/{contact_id} creates voice note"""
        wav_bytes = create_minimal_wav()
        
        files = {
            'audio': ('test_note.wav', io.BytesIO(wav_bytes), 'audio/wav')
        }
        form_data = {
            'duration': '10'  # 10 seconds
        }
        
        response = requests.post(
            f"{BASE_URL}/api/voice-notes/{TEST_USER_ID}/{TEST_CONTACT_ID}",
            files=files,
            data=form_data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert 'id' in data, "Response missing 'id'"
        assert 'audio_url' in data, "Response missing 'audio_url'"
        assert 'transcript' in data, "Response missing 'transcript'"
        assert 'duration' in data, "Response missing 'duration'"
        assert 'created_at' in data, "Response missing 'created_at'"
        
        # Store the note ID for later tests
        pytest.created_note_id = data['id']
        
        # Verify duration is stored correctly
        assert data['duration'] == 10, f"Expected duration 10, got {data['duration']}"
        
        print(f"Created voice note with ID: {data['id']}")
        print(f"Audio URL: {data['audio_url']}")
        print(f"Transcript: '{data['transcript']}'")

    def test_get_voice_note_after_create(self):
        """After creating a voice note, GET returns it with all fields populated"""
        response = requests.get(f"{BASE_URL}/api/voice-notes/{TEST_USER_ID}/{TEST_CONTACT_ID}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0, "Expected at least one voice note"
        
        # Check the latest note (should be first, sorted by newest)
        latest_note = data[0]
        assert 'id' in latest_note, "Note missing 'id'"
        assert 'contact_id' in latest_note, "Note missing 'contact_id'"
        assert 'user_id' in latest_note, "Note missing 'user_id'"
        assert 'audio_url' in latest_note, "Note missing 'audio_url'"
        assert 'duration' in latest_note, "Note missing 'duration'"
        assert 'created_at' in latest_note, "Note missing 'created_at'"
        
        print(f"GET returned {len(data)} voice notes")
        print(f"Latest note ID: {latest_note['id']}")

    def test_voice_note_appears_in_contact_events(self):
        """Voice note also appears as contact_event with event_type='voice_note'"""
        response = requests.get(
            f"{BASE_URL}/api/contacts/{TEST_USER_ID}/{TEST_CONTACT_ID}/events",
            params={'limit': 50}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Check for voice_note events
        events = data.get('events', [])
        voice_note_events = [e for e in events if e.get('event_type') == 'voice_note']
        
        assert len(voice_note_events) > 0, "No voice_note events found in contact events"
        
        # Verify event structure
        latest_vn_event = voice_note_events[0]
        assert latest_vn_event.get('event_type') == 'voice_note', "Event type should be 'voice_note'"
        assert 'title' in latest_vn_event, "Event missing 'title'"
        assert 'timestamp' in latest_vn_event or 'created_at' in latest_vn_event, "Event missing timestamp"
        
        print(f"Found {len(voice_note_events)} voice_note events in activity feed")
        print(f"Latest voice note event title: {latest_vn_event.get('title')}")

    def test_duration_validation_rejects_over_120_seconds(self):
        """Duration validation rejects recordings over 120 seconds"""
        wav_bytes = create_minimal_wav()
        
        files = {
            'audio': ('test_note.wav', io.BytesIO(wav_bytes), 'audio/wav')
        }
        form_data = {
            'duration': '150'  # 150 seconds - over the 120s limit
        }
        
        response = requests.post(
            f"{BASE_URL}/api/voice-notes/{TEST_USER_ID}/{TEST_CONTACT_ID}",
            files=files,
            data=form_data
        )
        
        assert response.status_code == 400, f"Expected 400 for duration > 120s, got {response.status_code}: {response.text}"
        data = response.json()
        assert 'detail' in data, "Error response missing 'detail'"
        assert '120' in str(data['detail']).lower() or 'limit' in str(data['detail']).lower(), \
            f"Error message should mention 120s limit: {data['detail']}"
        
        print(f"Duration validation working - rejected with: {data['detail']}")

    def test_delete_voice_note_success(self):
        """DELETE /api/voice-notes/{user_id}/{contact_id}/{note_id} removes the voice note"""
        # First get the current voice notes to find one to delete
        get_response = requests.get(f"{BASE_URL}/api/voice-notes/{TEST_USER_ID}/{TEST_CONTACT_ID}")
        assert get_response.status_code == 200
        notes = get_response.json()
        
        if len(notes) == 0:
            # Create a note first if none exist
            wav_bytes = create_minimal_wav()
            files = {'audio': ('test_note.wav', io.BytesIO(wav_bytes), 'audio/wav')}
            form_data = {'duration': '5'}
            create_response = requests.post(
                f"{BASE_URL}/api/voice-notes/{TEST_USER_ID}/{TEST_CONTACT_ID}",
                files=files,
                data=form_data
            )
            assert create_response.status_code == 200
            note_id = create_response.json()['id']
        else:
            note_id = notes[0]['id']
        
        # Now delete the note
        delete_response = requests.delete(
            f"{BASE_URL}/api/voice-notes/{TEST_USER_ID}/{TEST_CONTACT_ID}/{note_id}"
        )
        
        assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}: {delete_response.text}"
        data = delete_response.json()
        assert 'message' in data, "Delete response missing 'message'"
        
        print(f"Deleted voice note {note_id}")
        print(f"Delete response: {data['message']}")
        
        # Verify it's actually deleted by trying to get it
        verify_response = requests.get(f"{BASE_URL}/api/voice-notes/{TEST_USER_ID}/{TEST_CONTACT_ID}")
        assert verify_response.status_code == 200
        remaining_notes = verify_response.json()
        note_ids = [n['id'] for n in remaining_notes]
        assert note_id not in note_ids, f"Voice note {note_id} still exists after deletion"
        
        print(f"Verified deletion - note {note_id} no longer in list")

    def test_delete_nonexistent_voice_note_returns_404(self):
        """DELETE for non-existent voice note returns 404"""
        fake_note_id = "000000000000000000000000"  # ObjectId format but doesn't exist
        
        response = requests.delete(
            f"{BASE_URL}/api/voice-notes/{TEST_USER_ID}/{TEST_CONTACT_ID}/{fake_note_id}"
        )
        
        assert response.status_code == 404, f"Expected 404 for non-existent note, got {response.status_code}"
        print("404 returned for non-existent voice note as expected")

    def test_empty_audio_file_rejected(self):
        """Empty audio file is rejected with 400"""
        files = {
            'audio': ('empty.wav', io.BytesIO(b''), 'audio/wav')
        }
        form_data = {
            'duration': '5'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/voice-notes/{TEST_USER_ID}/{TEST_CONTACT_ID}",
            files=files,
            data=form_data
        )
        
        assert response.status_code == 400, f"Expected 400 for empty file, got {response.status_code}: {response.text}"
        print("Empty audio file correctly rejected with 400")


class TestVoiceNotesEdgeCases:
    """Edge case tests for voice notes"""
    
    def test_webm_content_type_accepted(self):
        """audio/webm content type is accepted (common browser format)"""
        # Create minimal content
        content = b"webm content placeholder"  # Not real webm but tests content type handling
        
        files = {
            'audio': ('test.webm', io.BytesIO(content), 'audio/webm')
        }
        form_data = {
            'duration': '5'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/voice-notes/{TEST_USER_ID}/{TEST_CONTACT_ID}",
            files=files,
            data=form_data
        )
        
        # Should not fail due to content type (might fail on whisper transcription which is expected)
        # We're testing that the upload itself works
        assert response.status_code in [200, 500], f"Unexpected status {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            print("webm upload succeeded")
            # Clean up
            note_id = response.json().get('id')
            if note_id:
                requests.delete(f"{BASE_URL}/api/voice-notes/{TEST_USER_ID}/{TEST_CONTACT_ID}/{note_id}")

    def test_boundary_duration_120_seconds_accepted(self):
        """Duration of exactly 120 seconds is accepted"""
        wav_bytes = create_minimal_wav()
        
        files = {
            'audio': ('test_note.wav', io.BytesIO(wav_bytes), 'audio/wav')
        }
        form_data = {
            'duration': '120'  # Exactly at the limit
        }
        
        response = requests.post(
            f"{BASE_URL}/api/voice-notes/{TEST_USER_ID}/{TEST_CONTACT_ID}",
            files=files,
            data=form_data
        )
        
        # Should be accepted (120 is not > 120)
        assert response.status_code == 200, f"Expected 200 for duration=120, got {response.status_code}: {response.text}"
        data = response.json()
        
        print(f"Boundary test passed - 120 second duration accepted with note ID: {data.get('id')}")
        
        # Clean up
        if data.get('id'):
            requests.delete(f"{BASE_URL}/api/voice-notes/{TEST_USER_ID}/{TEST_CONTACT_ID}/{data['id']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
