import re


def no_em_dash(text):
    """Replace em/en dashes (a dead AI giveaway) with natural punctuation."""
    if not text or not isinstance(text, str):
        return text
    text = re.sub(r"(?<=\d)\s*[—–]\s*(?=\d)", "-", text)
    text = re.sub(r"\s*[—–―]+\s*", ", ", text)
    text = re.sub(r"\s*,\s*,+", ",", text)
    return text
