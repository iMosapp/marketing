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


async def clean_ai_text(text, user_id=None):
    """Full AI output cleanup: em-dash removal + user's banned words/phrases."""
    text = no_em_dash(text)
    if user_id and text:
        try:
            from bson import ObjectId
            from routers.database import get_db
            u = await get_db().users.find_one({"_id": ObjectId(user_id)}, {"persona.banned_words": 1})
            phrases = parse_banned(((u or {}).get("persona") or {}).get("banned_words", ""))
            text = strip_banned(text, phrases)
        except Exception:
            pass
    return text
