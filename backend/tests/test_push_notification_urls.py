"""
Tests for push notification URL formats in push_notifications.py, twilio_webhooks.py, ai_reply.py
Verifies:
1. send_push_to_user stores url in data.url of the Expo push payload
2. twilio_webhooks.py sends full URL (https://...) for active-conv notification
3. twilio_webhooks.py sends relative path (/thread/...) for "notify assigned rep" push
4. ai_reply.py sends relative path (/thread/...) in all push calls
5. Frontend _layout.tsx has router imported and URL stripping logic (code review)
"""
import pytest
import requests
import os
import re

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestPushNotificationEndpoints:
    """Push notification endpoint availability and VAPID key"""

    def test_vapid_key_endpoint(self):
        resp = requests.get(f"{BASE_URL}/api/push/vapid-key", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "public_key" in data
        print(f"[PASS] VAPID key endpoint works, key present: {bool(data.get('public_key'))}")

    def test_push_status_endpoint(self):
        # Use a dummy user_id — should return 200 with empty token lists
        resp = requests.get(f"{BASE_URL}/api/push/status/nonexistent_user_id_000", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "native_tokens" in data
        assert "web_subscriptions" in data
        print(f"[PASS] Push status endpoint works: {data}")


class TestPushNotificationPayloadStructure:
    """Verify the data.url field in Expo push payload from push_notifications.py"""

    def test_send_push_to_user_stores_url_in_data(self):
        """
        Code review: push_notifications.py line 107 builds Expo messages with:
            "data": {"url": url, "icon": icon}
        This verifies the key is 'url' (not 'path', 'link', etc.)
        """
        import ast, inspect
        # Read the source and verify the data dict key
        with open("/app/backend/routers/push_notifications.py") as f:
            content = f.read()
        
        # Check that data dict contains "url": url pattern
        assert '"url": url' in content or '"url":url' in content or '"url": url,' in content, \
            "Expected 'data': {'url': url, ...} in push_notifications.py Expo push payload"
        print("[PASS] push_notifications.py: Expo push payload has 'data.url' key")

    def test_send_push_to_user_function_signature(self):
        """Verify send_push_to_user accepts url as a parameter"""
        with open("/app/backend/routers/push_notifications.py") as f:
            content = f.read()
        
        # Check function signature
        assert "async def send_push_to_user(user_id: str, title: str, body: str, url: str" in content, \
            "send_push_to_user should have url parameter"
        print("[PASS] send_push_to_user has correct signature with url parameter")


class TestTwilioWebhooksPushURLFormat:
    """Verify URL formats sent in push notifications from twilio_webhooks.py"""

    def test_active_conv_push_sends_full_url(self):
        """
        Lines 478-489: active conversation notification sends FULL URL.
        f"{app_url}/thread/{conversation_id}"
        This is expected — frontend strips domain via new URL(url).pathname
        """
        with open("/app/backend/routers/twilio_webhooks.py") as f:
            content = f.read()

        # Find the first push call in the active-conv SMS section (around line 485)
        # It should use app_url prefix
        pattern = r'send_push_to_user\([^)]*f"[\{$]app_url[^\)]*thread'
        # More flexible - check for app_url in push context
        assert 'f"{app_url}/thread/{conversation_id}"' in content or \
               "f'{app_url}/thread/{conversation_id}'" in content, \
               "twilio_webhooks.py active-conv push should send full URL with app_url prefix"
        print("[PASS] twilio_webhooks.py: Active-conv push sends full URL (f'{app_url}/thread/{id}')")

    def test_notify_rep_push_sends_relative_path(self):
        """
        Lines 820-833: 'notify assigned rep' push sends RELATIVE path.
        f"/thread/{conversation_id}"
        """
        with open("/app/backend/routers/twilio_webhooks.py") as f:
            content = f.read()

        # The second push call in notify rep block uses relative /thread/
        # Count occurrences of relative vs full URL in push calls
        relative_thread = content.count('f"/thread/{conversation_id}"')
        assert relative_thread >= 1, \
            "twilio_webhooks.py should have at least one push with relative /thread/{conversation_id}"
        print(f"[PASS] twilio_webhooks.py: Found {relative_thread} relative /thread/ push URL(s)")

    def test_both_push_url_formats_present(self):
        """twilio_webhooks.py uses BOTH full URL and relative path in different push calls"""
        with open("/app/backend/routers/twilio_webhooks.py") as f:
            content = f.read()

        has_full_url = f'"{{app_url}}/thread/{{conversation_id}}"' in content or \
                       'f"{app_url}/thread/{conversation_id}"' in content
        has_relative = 'f"/thread/{conversation_id}"' in content

        assert has_full_url, "Should have a full URL push call with app_url"
        assert has_relative, "Should have a relative /thread/ push call"
        print("[PASS] Both full URL and relative path push calls present in twilio_webhooks.py")


class TestAiReplyPushURLFormat:
    """Verify ai_reply.py uses relative paths in all push calls"""

    def test_hot_topic_push_uses_relative_path(self):
        """ai_reply.py line 150: hot topic escalation push uses /thread/{conversation_id}"""
        with open("/app/backend/routers/ai_reply.py") as f:
            content = f.read()

        # Line 150: f"/thread/{conversation_id}"
        assert 'f"/thread/{conversation_id}"' in content, \
            "ai_reply.py hot-topic push should use relative /thread/{conversation_id}"
        print("[PASS] ai_reply.py hot-topic push uses relative path")

    def test_draft_approval_push_uses_relative_path(self):
        """ai_reply.py line 389: draft approval push uses /thread/{conversation_id}"""
        with open("/app/backend/routers/ai_reply.py") as f:
            content = f.read()

        # Count all relative thread paths in ai_reply.py push calls
        count = content.count('f"/thread/{conversation_id}"')
        assert count >= 2, \
            f"ai_reply.py should have at least 2 relative /thread/ push calls, found {count}"
        print(f"[PASS] ai_reply.py: {count} relative /thread/ push URL(s) found")

    def test_escalation_push_uses_relative_path(self):
        """ai_reply.py line 703 (process_ai_reply_escalations): manager escalation push"""
        with open("/app/backend/routers/ai_reply.py") as f:
            content = f.read()

        # Check for the escalation push with relative URL
        assert "f\"/thread/{item.get('conversation_id" in content or \
               '''f"/thread/{item.get('conversation_id''' in content, \
               "ai_reply.py escalation push should use relative path"
        print("[PASS] ai_reply.py escalation push uses relative path")

    def test_no_full_urls_in_ai_reply_pushes(self):
        """ai_reply.py should NOT send full URLs in any push notifications"""
        with open("/app/backend/routers/ai_reply.py") as f:
            content = f.read()

        # Find all send_push_to_user calls and verify none use app_url
        push_calls = re.findall(r'send_push_to_user\([^)]+\)', content, re.DOTALL)
        for call in push_calls:
            assert 'app_url' not in call and 'http' not in call.lower(), \
                f"ai_reply.py push call should not use full URL: {call[:100]}"
        print(f"[PASS] ai_reply.py: {len(push_calls)} push calls all use relative URLs")


class TestFrontendLayoutURLStripping:
    """Code review of _layout.tsx for router import and URL stripping logic"""

    def test_router_imported_from_expo_router(self):
        """_layout.tsx must import router from expo-router"""
        with open("/app/frontend/app/_layout.tsx") as f:
            content = f.read()

        assert "router" in content
        # Check it's imported from expo-router (not a separate import)
        import_line = next((l for l in content.split('\n') if 'expo-router' in l and 'import' in l), None)
        assert import_line is not None, "expo-router import not found"
        assert 'router' in import_line, \
            f"'router' not in expo-router import line: {import_line}"
        print(f"[PASS] router imported from expo-router: {import_line.strip()}")

    def test_url_stripping_logic_present(self):
        """_layout.tsx must strip domain from full URLs before router.push()"""
        with open("/app/frontend/app/_layout.tsx") as f:
            content = f.read()

        assert "startsWith('http')" in content or 'startsWith("http")' in content, \
            "URL stripping: check for http prefix missing"
        assert "new URL(" in content, \
            "URL stripping: new URL() constructor for pathname extraction missing"
        assert ".pathname" in content, \
            "URL stripping: .pathname extraction missing"
        print("[PASS] URL stripping logic present in _layout.tsx")

    def test_router_push_called_on_notification_tap(self):
        """_layout.tsx must call router.push() in notification response handler"""
        with open("/app/frontend/app/_layout.tsx") as f:
            content = f.read()

        assert "router.push(" in content, "router.push() not found in _layout.tsx"
        assert "addNotificationResponseReceivedListener" in content, \
            "Notification response listener not found"
        print("[PASS] router.push() called in addNotificationResponseReceivedListener")
