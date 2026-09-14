"""Make LLM text sound human when a TTS voice reads it: numbers the way a person says them on the phone.
"$132.89" -> "one hundred thirty-two dollars and eighty-nine cents", "(435) 275-9829" -> "four three five, two seven five, nine eight two nine",
"2022 Tahoe" -> "twenty twenty-two Tahoe", "45,000 miles" -> "forty-five thousand miles", "9:30 am" -> "nine thirty AM", "3rd" -> "third"."""
import re

from num2words import num2words

DIGIT_WORDS = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine"}
_PHONE = re.compile(r"(?<!\w)(?:\+?1[\s.-]?)?\(?(\d{3})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})(?!\d)")
_MONEY = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?(?:\s?([kKmM])\b)?(?![\d.])")
_BARE_CENTS = re.compile(r"(?<![\d.$])(\d{1,6})\.(\d{2})(?![\d%]|\s?(?:l\b|liter|litre|mpg|inch|in\b|percent|\"))", re.IGNORECASE)
_PERCENT = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s?(?:%|percent\b)")
_TIME = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})\s?(a\.?m\.?|p\.?m\.?)?(?![\d:])", re.IGNORECASE)
_DECIMAL = re.compile(r"(?<![\d.])(\d+)\.(\d+)(?![\d.])")
_ORDINAL = re.compile(r"(?<!\w)(\d+)(st|nd|rd|th)\b", re.IGNORECASE)
_K = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s?k\b(?!\w)", re.IGNORECASE)
_YEAR = re.compile(r"(?<![\d,.])((?:19[5-9]|20[0-3])\d)(?![\d,])")
_COMMA_INT = re.compile(r"(?<![\d.])\d{1,3}(?:,\d{3})+(?![\d.])")
_INT = re.compile(r"(?<![\w.])(\d+)(?![\d.])")


def _words(n) -> str:
    try:
        return num2words(n).replace(" and ", " ").replace(",", "")
    except Exception:
        return str(n)


def _int(s: str) -> str:
    return _words(int(s.replace(",", "")))


def _digits(s: str) -> str:
    return " ".join(DIGIT_WORDS[c] for c in s if c.isdigit())


def _cents(c: str) -> str:
    c = (c + "0")[:2]
    return f"{_words(int(c))} cent{'s' if int(c) != 1 else ''}"


def _money(m: re.Match) -> str:
    dollars, cents, mult = m.group(1), m.group(2), (m.group(3) or "").lower()
    d = int(dollars.replace(",", ""))
    if mult == "k":
        return f"{_words(d)} thousand dollars"
    if mult == "m":
        return f"{_words(d)} million dollars"
    if d == 0 and cents:
        return _cents(cents)
    out = f"{_words(d)} dollar{'s' if d != 1 else ''}"
    if cents and int((cents + "0")[:2]):
        out += f" and {_cents(cents)}"
    return out


def _time(m: re.Match) -> str:
    h, mi, ap = int(m.group(1)), m.group(2), (m.group(3) or "").replace(".", "").upper()
    if h > 24:
        return m.group(0)
    if mi == "00":
        mins = " o'clock" if not ap else ""
    elif mi.startswith("0"):
        mins = f" oh {_words(int(mi))}"
    else:
        mins = f" {_words(int(mi))}"
    return f"{_words(h)}{mins}{(' ' + ap) if ap else ''}"


def _year(m: re.Match) -> str:
    try:
        return num2words(int(m.group(1)), to="year")
    except Exception:
        return m.group(1)


def speakable(text: str) -> str:
    """Rewrite every digit sequence the way a person would say it on the phone. Idempotent and safe on text with no numbers."""
    if not text or not any(ch.isdigit() for ch in text):
        return text or ""
    t = text
    t = _PHONE.sub(lambda m: f"{_digits(m.group(1))}, {_digits(m.group(2))}, {_digits(m.group(3))}", t)
    t = _MONEY.sub(_money, t)
    t = _PERCENT.sub(lambda m: f"{_decimal_words(m.group(1))} percent", t)
    t = _TIME.sub(_time, t)
    t = _BARE_CENTS.sub(lambda m: _money(re.match(_MONEY, f"${m.group(1)}.{m.group(2)}")), t)
    t = _K.sub(lambda m: f"{_decimal_words(m.group(1))} thousand", t)
    t = _ORDINAL.sub(lambda m: num2words(int(m.group(1)), to="ordinal"), t)
    t = _DECIMAL.sub(lambda m: f"{_int(m.group(1))} point {_digits(m.group(2))}", t)
    t = _YEAR.sub(_year, t)
    t = _COMMA_INT.sub(lambda m: _int(m.group(0)), t)
    t = _INT.sub(lambda m: _int(m.group(1)) if len(m.group(1)) <= 9 else _digits(m.group(1)), t)
    return re.sub(r"[ \t]{2,}", " ", t).strip()


def _decimal_words(s: str) -> str:
    if "." in s:
        a, b = s.split(".", 1)
        return f"{_int(a)} point {_digits(b)}"
    return _int(s)


NUMBERS_RULE = ("NUMBERS: your words are spoken aloud by a voice, so write every number the way you would SAY it, never in digits or symbols: "
                "'a hundred and thirty-two dollars and eighty-nine cents' not '$132.89', 'four three five, two seven five, nine eight two nine' for a phone number, "
                "'twenty twenty-two Tahoe' not '2022 Tahoe', 'forty-five thousand miles', 'nine thirty tomorrow morning', 'six point nine percent', 'the third'. ")
