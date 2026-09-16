"""Dutch speed-to-lead + Test Lab default: flow texts, placeholder fallbacks, VA language rule, industry_va live by default.
Run: cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_dutch_speed_to_lead.py -q"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import lab  # noqa: E402
from services import industries as ind  # noqa: E402
from services import va_prompt  # noqa: E402
from services.lead_flows import DEFAULT_FLOW, DUTCH_FLOW_TEXTS, localized_texts  # noqa: E402
from routers.lead_sources import hydrate_intake_text  # noqa: E402


def test_dutch_store_gets_dutch_defaults():
    src = {"name": "Website", "intake_text": DEFAULT_FLOW["intake_text"], "after_hours_text": DEFAULT_FLOW["after_hours_text"], "no_answer_text": DEFAULT_FLOW["no_answer_text"]}
    out = localized_texts(src, "nl-NL")
    assert out["intake_text"] == DUTCH_FLOW_TEXTS["intake_text"]
    assert out["after_hours_text"].startswith("Hoi {{first_name}}") and "gesloten" in out["after_hours_text"]
    assert out["no_answer_text"] == DUTCH_FLOW_TEXTS["no_answer_text"]
    assert localized_texts(src, "nl-BE")["intake_text"] == DUTCH_FLOW_TEXTS["intake_text"]
    assert src["intake_text"] == DEFAULT_FLOW["intake_text"], "input must not be mutated"


def test_edited_or_blank_texts_are_kept_and_english_stores_untouched():
    src = {"intake_text": "Hey {{first_name}}, Bob here at QA Motors!", "after_hours_text": "", "no_answer_text": DEFAULT_FLOW["no_answer_text"]}
    out = localized_texts(src, "nl-NL")
    assert out["intake_text"] == src["intake_text"]
    assert out["after_hours_text"] == ""
    assert out["no_answer_text"] == DUTCH_FLOW_TEXTS["no_answer_text"]
    en = {"intake_text": DEFAULT_FLOW["intake_text"]}
    assert localized_texts(en, "en-US") is en and localized_texts(en, None) is en and localized_texts(en, "en-GB") is en


def test_dutch_placeholder_fallbacks():
    body = hydrate_intake_text(DUTCH_FLOW_TEXTS["intake_text"], {"first_name": "", "vehicle_interest": ""}, "Website", lang="nl")
    assert body.startswith("Hoi daar, bedankt voor je bericht over de auto!")
    body = hydrate_intake_text(DUTCH_FLOW_TEXTS["no_answer_text"], {"first_name": "Sanne", "vehicle_year": "2022", "vehicle_make": "Volvo", "vehicle_model": "XC40"}, "AutoTrack", lang="nl")
    assert body == "Hoi Sanne, we hebben geprobeerd je te bereiken over 2022 Volvo XC40, maar kregen je niet te pakken. Wanneer kunnen we het beste bellen, of wil je liever verder sms'en?"
    en = hydrate_intake_text(DEFAULT_FLOW["intake_text"], {}, "Website")
    assert en.startswith("Hi there, thanks for reaching out about vehicle!")


def test_va_prompt_carries_language_rule():
    user = {"name": "Sanne de Vries", "persona": {"tone": "friendly"}}
    store = {"name": "Autobedrijf QA", "locale": "nl-NL"}
    nl = va_prompt.build_text(user, store, ind.va("automotive"), {}, "nl-NL")
    assert "LANGUAGE: Write and speak ONLY natural Dutch" in nl and "You ARE Sanne de Vries" in nl
    en = va_prompt.build_text(user, {**store, "locale": "en-US"}, ind.va("automotive"), {}, "en-US")
    assert "LANGUAGE:" not in en
    assert "LANGUAGE:" not in va_prompt.build_text(user, None, ind.va("general"), {})


class _Settings:
    def __init__(self, value):
        self._value = value

    async def find_one(self, *_a, **_k):
        return {"value": self._value} if self._value is not None else None


class _Db:
    def __init__(self, value=None):
        self.settings = _Settings(value)


def test_industry_va_is_live_by_default_and_lab_can_pull_it_back():
    assert lab._default("industry_va") == "live" and lab._default("voice_interview") == "lab"
    assert asyncio.run(lab.is_live(_Db(), "industry_va")) is True
    assert asyncio.run(lab.is_live(_Db(), "voice_interview")) is False
    assert asyncio.run(lab.is_live(_Db({"industry_va": {"status": "lab"}}), "industry_va")) is False
    rows = {f["key"]: f["status"] for f in asyncio.run(lab.list_features(_Db()))}
    assert rows == {"voice_interview": "lab", "industry_va": "live"}
