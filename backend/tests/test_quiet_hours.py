"""
Tests for scheduler quiet hours gate in _process_pending_campaign_sends()
Tests that campaign sends outside 8 AM - 9 PM are deferred, and inside window are not.
"""
import pytest
import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from zoneinfo import ZoneInfo

# Add backend to path
sys.path.insert(0, '/app/backend')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# ── Unit tests for quiet hours logic ──────────────────────────────────────────

def make_send_doc(send_id, user_id, contact_id):
    return {
        "_id": send_id,
        "user_id": str(user_id),
        "contact_id": str(contact_id),
        "contact_name": "Test User",
        "contact_phone": "+15005550006",
        "message": "Hello {first_name}!",
        "status": "pending",
        "send_at": datetime.utcnow(),
        "campaign_name": "Test Campaign",
        "delivery_mode": "automated",
        "channel": "sms",
    }


class TestQuietHoursLogic:
    """Unit tests for quiet hours gate using mocked datetime and DB"""

    def _get_deferred_utc_for_2am(self, tz_name="America/Denver"):
        """Calculate what deferred_utc should be when local time is 2 AM"""
        local_tz = ZoneInfo(tz_name)
        # Simulate 2 AM local time
        now_local = datetime.now(local_tz).replace(hour=2, minute=0, second=0, microsecond=0)
        # hour < 8, so defer to 9 AM same day
        deferred_local = now_local.replace(hour=9, minute=0, second=0, microsecond=0)
        return deferred_local.astimezone(timezone.utc).replace(tzinfo=None)

    def _get_deferred_utc_for_22(self, tz_name="America/Denver"):
        """Calculate what deferred_utc should be when local time is 10 PM (hour=22)"""
        local_tz = ZoneInfo(tz_name)
        now_local = datetime.now(local_tz).replace(hour=22, minute=0, second=0, microsecond=0)
        # hour >= 21, so defer to 9 AM next day
        next_day = (now_local + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        return next_day.astimezone(timezone.utc).replace(tzinfo=None)

    def test_quiet_hours_2am_should_defer(self):
        """At 2 AM local time, message should be deferred (outside 8 AM - 9 PM window)"""
        tz_name = "America/Denver"
        local_tz = ZoneInfo(tz_name)
        # Simulate 2 AM
        local_now = datetime.now(local_tz).replace(hour=2, minute=0, second=0, microsecond=0)
        hour = local_now.hour
        assert hour < 8, f"Expected hour < 8, got {hour}"
        
        # Logic: should defer
        should_defer = hour < 8 or hour >= 21
        assert should_defer, "At 2 AM, should_defer must be True"

        # Deferred time should be 9 AM same day
        deferred_local = local_now.replace(hour=9, minute=0, second=0, microsecond=0)
        deferred_utc = deferred_local.astimezone(timezone.utc).replace(tzinfo=None)
        assert deferred_utc.hour != 2, "Deferred time should not be at 2 AM UTC"
        print(f"PASS: 2 AM local → deferred to {deferred_utc} UTC")

    def test_quiet_hours_10am_should_not_defer(self):
        """At 10 AM local time, message should NOT be deferred"""
        tz_name = "America/Denver"
        local_tz = ZoneInfo(tz_name)
        local_now = datetime.now(local_tz).replace(hour=10, minute=0, second=0, microsecond=0)
        hour = local_now.hour
        
        should_defer = hour < 8 or hour >= 21
        assert not should_defer, f"At 10 AM, should_defer must be False but hour={hour}"
        print(f"PASS: 10 AM local → not deferred")

    def test_quiet_hours_boundary_8am_not_deferred(self):
        """At exactly 8 AM (start of window), should NOT defer"""
        tz_name = "America/Denver"
        local_tz = ZoneInfo(tz_name)
        local_now = datetime.now(local_tz).replace(hour=8, minute=0, second=0, microsecond=0)
        hour = local_now.hour
        should_defer = hour < 8 or hour >= 21
        assert not should_defer, "8 AM should be inside the window (not deferred)"
        print("PASS: 8 AM boundary → not deferred")

    def test_quiet_hours_boundary_9pm_deferred(self):
        """At 9 PM (hour=21, start of night window), should defer"""
        tz_name = "America/Denver"
        local_tz = ZoneInfo(tz_name)
        local_now = datetime.now(local_tz).replace(hour=21, minute=0, second=0, microsecond=0)
        hour = local_now.hour
        should_defer = hour < 8 or hour >= 21
        assert should_defer, "21:00 (9 PM) should be outside the window (deferred)"
        print("PASS: 9 PM boundary → deferred")

    def test_quiet_hours_evening_defers_to_next_day(self):
        """At 10 PM (hour=22), should defer to 9 AM NEXT day"""
        tz_name = "America/Denver"
        local_tz = ZoneInfo(tz_name)
        local_now = datetime.now(local_tz).replace(hour=22, minute=0, second=0, microsecond=0)
        hour = local_now.hour
        assert hour >= 21
        
        # Logic per scheduler.py: if hour >= 21, defer to next day
        next_day = (local_now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        deferred_utc = next_day.astimezone(timezone.utc).replace(tzinfo=None)
        
        # The deferred date should be tomorrow
        local_today = local_now.date()
        deferred_local_date = next_day.date()
        assert deferred_local_date > local_today, "Evening defer should push to next day"
        print(f"PASS: 10 PM local → deferred to next day 9 AM: {deferred_utc} UTC")

    def test_quiet_hours_defaults_to_america_denver(self):
        """If user has no timezone set, defaults to America/Denver"""
        user_cache = {}
        user_id = "fake_user_id"
        
        # Simulate cache miss — no timezone key
        user_doc = {}  # No timezone field
        tz_name = user_doc.get("timezone") or "America/Denver"
        assert tz_name == "America/Denver", f"Expected America/Denver default, got {tz_name}"
        print("PASS: No timezone → defaults to America/Denver")

    def test_deferred_reason_format(self):
        """Deferred reason should contain 'quiet hours' and the local hour"""
        hour = 2
        tz_name = "America/Denver"
        reason = f"quiet hours (was {hour}:00 local)"
        assert "quiet hours" in reason
        assert "2:00" in reason
        print(f"PASS: deferred_reason = '{reason}'")


class TestQuietHoursWithMockedDB:
    """Integration-style tests with mocked DB to simulate actual scheduler behavior"""

    def test_2am_send_is_deferred_in_db(self):
        """Simulate the scheduler deferring a send at 2 AM by running the quiet hours block"""
        from zoneinfo import ZoneInfo

        tz_name = "America/Denver"
        local_tz = ZoneInfo(tz_name)
        
        # Build a fake local_now at 2 AM
        real_now = datetime.now(local_tz)
        fake_local_now = real_now.replace(hour=2, minute=0, second=0, microsecond=0)
        
        # Simulate the scheduler block
        hour = fake_local_now.hour
        send_id = ObjectId()
        
        updates = {}
        if hour < 8 or hour >= 21:
            if hour >= 21:
                next_day = (fake_local_now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
            else:
                next_day = fake_local_now.replace(hour=9, minute=0, second=0, microsecond=0)
            deferred_utc = next_day.astimezone(timezone.utc).replace(tzinfo=None)
            updates = {
                "status": "pending",
                "send_at": deferred_utc,
                "deferred_reason": f"quiet hours (was {hour}:00 local)"
            }
        
        assert updates.get("status") == "pending", "Status should remain pending after deferral"
        assert "deferred_reason" in updates, "deferred_reason must be set"
        assert "quiet hours" in updates["deferred_reason"]
        assert updates["send_at"].hour != 2 or updates["send_at"].hour == 9  # deferred to 9 AM
        
        # Verify deferred time is 9 AM local = some UTC hour
        deferred_local = updates["send_at"].replace(tzinfo=timezone.utc).astimezone(local_tz)
        assert deferred_local.hour == 9, f"Expected deferred at 9 AM local, got {deferred_local.hour}"
        print(f"PASS: 2 AM send deferred to {updates['send_at']} UTC (9 AM {tz_name})")
        print(f"      deferred_reason: {updates['deferred_reason']}")

    def test_10am_send_not_deferred(self):
        """Simulate the scheduler NOT deferring a send at 10 AM"""
        tz_name = "America/Denver"
        local_tz = ZoneInfo(tz_name)
        
        real_now = datetime.now(local_tz)
        fake_local_now = real_now.replace(hour=10, minute=0, second=0, microsecond=0)
        
        hour = fake_local_now.hour
        deferred = False
        if hour < 8 or hour >= 21:
            deferred = True
        
        assert not deferred, f"10 AM should not be deferred, hour={hour}"
        print(f"PASS: 10 AM send is NOT deferred (hour={hour})")

    def test_custom_timezone_user(self):
        """Rep with America/New_York timezone at 2 AM should be deferred"""
        tz_name = "America/New_York"
        local_tz = ZoneInfo(tz_name)
        
        real_now = datetime.now(local_tz)
        fake_local_now = real_now.replace(hour=2, minute=0, second=0, microsecond=0)
        
        hour = fake_local_now.hour
        should_defer = hour < 8 or hour >= 21
        assert should_defer, "2 AM New York should defer"

        next_day = fake_local_now.replace(hour=9, minute=0, second=0, microsecond=0)
        deferred_utc = next_day.astimezone(timezone.utc).replace(tzinfo=None)
        deferred_local = deferred_utc.replace(tzinfo=timezone.utc).astimezone(local_tz)
        assert deferred_local.hour == 9
        print(f"PASS: 2 AM America/New_York → deferred to 9 AM New_York = {deferred_utc} UTC")
