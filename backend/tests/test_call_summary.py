"""services.call_summary.clean: markdown, bracket tags and prompt leaks never reach the apps."""
from services.call_summary import clean

LEGACY_VOICEMAIL = """[Voicemail] **CALL SUMMARY**
The call went to voicemail, and no live conversation occurred. The speaker wished Forest a happy Friday and left a brief message.

**FOLLOW-UP ACTIONS**
List 2-4 specific, actionable next steps the rep should take. Be concrete — not 'follow up' but 'Text John about the F-150 availability'."""

LEGACY_FULL = """**CALL SUMMARY**
Forest called Bud about the 2024 Tahoe — Bud wants numbers on the black one.

**KEY DETAILS**
• Vehicle/product interest: 2024 Tahoe, black
• Budget: [if mentioned]
• Timeline: Not mentioned
• Personal notes: Wife Karen, two kids

**FOLLOW-UP ACTIONS**
1. Text Bud the out-the-door price on the black Tahoe
2. Call Bud Saturday morning to set an appointment"""


def test_legacy_voicemail_is_one_clean_sentence():
    out = clean(LEGACY_VOICEMAIL)
    assert out.startswith("Summary: The call went to voicemail")
    assert "*" not in out and "[" not in out and "List 2-4" not in out and "Be concrete" not in out
    assert "\n" not in out


def test_legacy_full_summary_normalizes_sections_and_drops_empty_facts():
    out = clean(LEGACY_FULL)
    assert "**" not in out and "•" not in out and "—" not in out
    assert out.startswith("Summary: Forest called Bud")
    assert "Key details:\n- Vehicle/product interest: 2024 Tahoe, black\n- Personal notes: Wife Karen, two kids" in out
    assert "Budget" not in out and "Timeline" not in out
    assert out.endswith("Next steps:\n- Text Bud the out-the-door price on the black Tahoe\n- Call Bud Saturday morning to set an appointment")


def test_canonical_and_plain_inputs_pass_through():
    canonical = "Summary: Quick check-in.\n\nNext steps:\n- Text Sam the service coupon"
    assert clean(canonical) == canonical
    assert clean("Plain sentence.") == "Summary: Plain sentence."
    assert clean("") == ""
