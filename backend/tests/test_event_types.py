"""
Regression tests for event type resolution.
Run: cd /app/backend && python -m pytest tests/test_event_types.py -v
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.event_types import (
    LINK_TYPE_TO_EVENT, EVENT_TYPE_LABELS, 
    get_event_label, get_card_sent_info, get_card_viewed_info,
)


class TestLinkTypeMapping:
    """Every short URL link_type must map to a specific event_type."""

    def test_birthday_card_maps_correctly(self):
        assert LINK_TYPE_TO_EVENT["birthday_card"] == "birthday_card_sent"

    def test_thank_you_card_maps_correctly(self):
        assert LINK_TYPE_TO_EVENT["thank_you_card"] == "thank_you_card_sent"

    def test_holiday_card_maps_correctly(self):
        assert LINK_TYPE_TO_EVENT["holiday_card"] == "holiday_card_sent"

    def test_welcome_card_maps_correctly(self):
        assert LINK_TYPE_TO_EVENT["welcome_card"] == "welcome_card_sent"

    def test_anniversary_card_maps_correctly(self):
        assert LINK_TYPE_TO_EVENT["anniversary_card"] == "anniversary_card_sent"

    def test_congrats_card_maps_correctly(self):
        assert LINK_TYPE_TO_EVENT["congrats_card"] == "congrats_card_sent"

    def test_business_card_maps_to_digital(self):
        assert LINK_TYPE_TO_EVENT["business_card"] == "digital_card_sent"

    def test_review_request_maps_correctly(self):
        assert LINK_TYPE_TO_EVENT["review_request"] == "review_request_sent"


class TestEventLabels:
    """Every card event_type must have a human-readable label."""

    def test_birthday_card_has_label(self):
        assert "Birthday" in EVENT_TYPE_LABELS["birthday_card_sent"]

    def test_congrats_card_has_label(self):
        assert "Congrats" in EVENT_TYPE_LABELS["congrats_card_sent"]

    def test_thank_you_card_has_label(self):
        assert "Thank You" in EVENT_TYPE_LABELS["thank_you_card_sent"]

    def test_holiday_card_has_label(self):
        assert "Holiday" in EVENT_TYPE_LABELS["holiday_card_sent"]

    def test_welcome_card_has_label(self):
        assert "Welcome" in EVENT_TYPE_LABELS["welcome_card_sent"]

    def test_anniversary_card_has_label(self):
        assert "Anniversary" in EVENT_TYPE_LABELS["anniversary_card_sent"]

    def test_birthday_viewed_has_label(self):
        assert "Birthday" in EVENT_TYPE_LABELS["birthday_card_viewed"]

    def test_unknown_type_generates_label(self):
        label = get_event_label("some_random_event")
        assert label == "Some Random Event"


class TestCardSentInfo:
    """get_card_sent_info must return correct event_type for each card type."""

    @pytest.mark.parametrize("card_type,expected_event", [
        ("congrats", "congrats_card_sent"),
        ("birthday", "birthday_card_sent"),
        ("anniversary", "anniversary_card_sent"),
        ("holiday", "holiday_card_sent"),
        ("thank_you", "thank_you_card_sent"),
        ("thankyou", "thank_you_card_sent"),
        ("welcome", "welcome_card_sent"),
    ])
    def test_card_type_to_event_type(self, card_type, expected_event):
        info = get_card_sent_info(card_type)
        assert info["event_type"] == expected_event

    def test_unknown_card_type_generates_event(self):
        info = get_card_sent_info("graduation")
        assert info["event_type"] == "graduation_card_sent"


class TestCardViewedInfo:
    """get_card_viewed_info must return correct event_type for each card type."""

    @pytest.mark.parametrize("card_type,expected_event", [
        ("congrats", "congrats_card_viewed"),
        ("birthday", "birthday_card_viewed"),
        ("anniversary", "anniversary_card_viewed"),
    ])
    def test_card_type_to_viewed_event(self, card_type, expected_event):
        info = get_card_viewed_info(card_type)
        assert info["event_type"] == expected_event


class TestNoCongratsFallback:
    """
    CRITICAL REGRESSION TEST: No card type should ever accidentally 
    resolve to congrats_card_sent unless it IS a congrats card.
    """

    def test_birthday_is_not_congrats(self):
        assert LINK_TYPE_TO_EVENT["birthday_card"] != "congrats_card_sent"

    def test_thank_you_is_not_congrats(self):
        assert LINK_TYPE_TO_EVENT["thank_you_card"] != "congrats_card_sent"

    def test_holiday_is_not_congrats(self):
        assert LINK_TYPE_TO_EVENT["holiday_card"] != "congrats_card_sent"

    def test_welcome_is_not_congrats(self):
        assert LINK_TYPE_TO_EVENT["welcome_card"] != "congrats_card_sent"

    def test_anniversary_is_not_congrats(self):
        assert LINK_TYPE_TO_EVENT["anniversary_card"] != "congrats_card_sent"

    def test_business_card_is_not_congrats(self):
        assert LINK_TYPE_TO_EVENT["business_card"] != "congrats_card_sent"

    def test_review_is_not_congrats(self):
        assert LINK_TYPE_TO_EVENT["review_request"] != "congrats_card_sent"

    def test_birthday_sent_info_is_not_congrats(self):
        info = get_card_sent_info("birthday")
        assert info["event_type"] != "congrats_card_sent"
        assert "Congrats" not in info["label"]
