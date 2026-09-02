import re


def no_em_dash(text):
    """Replace em/en dashes (a dead AI giveaway) with natural punctuation."""
    if not text or not isinstance(text, str):
        return text
    text = re.sub(r"(?<=\d)\s*[—–]\s*(?=\d)", "-", text)
    text = re.sub(r"\s*[—–―]+\s*", ", ", text)
    text = re.sub(r"\s*,\s*,+", ",", text)
    return text


def parse_banned(s):
    if not s:
        return []
    return [p.strip() for p in re.split(r"[,\n;]+", s) if p.strip()]


def strip_banned(text, phrases):
    """Remove the user's banned words/phrases from AI output, tidying leftover spacing."""
    if not text or not phrases:
        return text
    for p in phrases:
        text = re.sub(re.escape(p), "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    text = re.sub(r"([.!?])\s*[,;:]+", r"\1", text)
    text = re.sub(r"([,;:])\1+", r"\1", text)
    text = re.sub(r"^[\s,.;:!?]+", "", text)
    return text.strip()


def _phone_pattern(phone):
    """Regex matching a phone number in any common formatting (+1, dots, dashes, parens)."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return None
    a, b, c = digits[:3], digits[3:6], digits[6:]
    return re.compile(rf"(?<!\d)(?:\+?1[\s.-]?)?\(?{a}\)?[\s.-]?{b}[\s.-]?{c}(?!\d)")


def format_phone_display(phone):
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return phone or ""
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"


def enforce_business_number(text, personal_phone, business_phone):
    """Never let AI hand out the rep's personal cell: swap it for the dedicated business line."""
    if not text or not personal_phone or not business_phone:
        return text
    pat = _phone_pattern(personal_phone)
    if not pat:
        return text
    return pat.sub(format_phone_display(business_phone), text)


async def clean_ai_text(text, user_id=None):
    """Full AI output cleanup: em-dash removal + user's banned words/phrases + business-number guard."""
    text = no_em_dash(text)
    if user_id and text:
        try:
            from bson import ObjectId
            from routers.database import get_db
            u = await get_db().users.find_one(
                {"_id": ObjectId(user_id)},
                {"persona.banned_words": 1, "phone": 1, "twilio_number": 1, "mvpline_number": 1},
            )
            phrases = parse_banned(((u or {}).get("persona") or {}).get("banned_words", ""))
            text = strip_banned(text, phrases)
            business = (u or {}).get("twilio_number") or (u or {}).get("mvpline_number")
            text = enforce_business_number(text, (u or {}).get("phone"), business)
        except Exception:
            pass
    return text
