"""Make LLM text sound human when a TTS voice reads it: numbers the way a person says them on the phone, in the locale's language.
en: "$132.89" -> "one hundred thirty-two dollars and eighty-nine cents", "£12.50" -> "twelve pounds and fifty pence", "(435) 275-9829" -> "four three five, two seven five, nine eight two nine",
    "2022 Tahoe" -> "twenty twenty-two Tahoe", "45,000 miles" -> "forty-five thousand miles", "9:30 am" -> "nine thirty AM", "3rd" -> "third".
nl: "€ 1.234,56" -> "twaalfhonderdvierendertig euro zesenvijftig", "06-12345678" -> "nul zes, twaalf, vierendertig, zesenvijftig, achtenzeventig", "6,9%" -> "zes komma negen procent", "3e" -> "derde"."""
import re
from typing import Optional

from num2words import num2words

from services import locales as loc

DIGIT_WORDS = {"en": {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine"},
               "nl": {"0": "nul", "1": "een", "2": "twee", "3": "drie", "4": "vier", "5": "vijf", "6": "zes", "7": "zeven", "8": "acht", "9": "negen"}}
CURRENCIES = {"$": ("dollar", "dollars", "cent", "cents"), "£": ("pound", "pounds", "penny", "pence"), "€": ("euro", "euros", "cent", "cents")}

# ---- English patterns (unchanged behaviour for en-US)
_PHONE_US = re.compile(r"(?<!\w)(?:\+?1[\s.-]?)?\(?(\d{3})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})(?!\d)")
_PHONE_UK = re.compile(r"(?<!\w)(?:\+44\s?\(?0?\)?[\s-]?|\+353\s?\(?0?\)?[\s-]?|0)(\d[\d\s-]{7,12}\d)(?!\d)")
_PHONE_NL = re.compile(r"(?<!\w)(?:\+31\s?\(?0?\)?[\s-]?|0)(\d[\d\s-]{7,11}\d)(?!\d)")
_MONEY_EN = re.compile(r"([$£€])\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?(?:\s?([kKmM])\b)?(?!\d|\.\d)")
_BARE_CENTS = re.compile(r"(?<![\d.$£€])(\d{1,6})\.(\d{2})(?![\d%]|\s?(?:l\b|liter|litre|mpg|inch|in\b|percent|\"))", re.IGNORECASE)
_PERCENT_EN = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s?(?:%|percent\b)")
_TIME = re.compile(r"(?<!\d)(\d{1,2})[:.](\d{2})\s?(a\.?m\.?|p\.?m\.?|uur)?(?![\d:])", re.IGNORECASE)
_DECIMAL_EN = re.compile(r"(?<![\d.])(\d+)\.(\d+)(?!\d|\.\d)")
_ORDINAL_EN = re.compile(r"(?<!\w)(\d+)(st|nd|rd|th)\b", re.IGNORECASE)
_K = re.compile(r"(?<![\w.])(\d+(?:[.,]\d+)?)\s?k\b(?!\w)", re.IGNORECASE)
_YEAR = re.compile(r"(?<![\d,.])((?:19[5-9]|20[0-3])\d)(?![\d,.])")
_COMMA_INT = re.compile(r"(?<![\d.])\d{1,3}(?:,\d{3})+(?!\d|\.\d)")
_INT = re.compile(r"(?<![\w.,])(\d+)(?!\d|[.,]\d)")
# ---- Dutch patterns: "." groups thousands, "," is the decimal
_MONEY_NL = re.compile(r"(?:€\s?(\d{1,3}(?:\.\d{3})+|\d{1,3}(?:,\d{3})+|\d+)(?:[,.](\d{1,2}))?(?:\s?([kK])\b)?(?!\d)|(?<!\w)(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?\s?euro\b)")
_PERCENT_NL = re.compile(r"(?<![\d,.])(\d+(?:[,.]\d+)?)\s?(?:%|procent\b)")
_DECIMAL_NL = re.compile(r"(?<![\d,.])(\d+),(\d+)(?!\d)")
_ORDINAL_NL = re.compile(r"(?<!\w)(\d+)(ste|de|e)\b")
_DOT_INT = re.compile(r"(?<![\d,])\d{1,3}(?:\.\d{3})+(?!\d|,\d)")


def _lang(locale: Optional[str]) -> str:
    return "nl" if loc.language(locale) == "nl" else "en"


def _words(n, lang: str = "en") -> str:
    try:
        w = num2words(n, lang=lang)
        return w.replace(" and ", " ").replace(",", "") if lang == "en" else w
    except Exception:
        return str(n)


def _int(s: str, lang: str = "en") -> str:
    return _words(int(re.sub(r"[^\d]", "", s)), lang)


def _digits(s: str, lang: str = "en", oh: bool = False) -> str:
    words = DIGIT_WORDS[lang]
    return " ".join(("oh" if (oh and c == "0") else words[c]) for c in s if c.isdigit())


def _pairs(s: str, lang: str) -> str:
    """Dutch phone habit: the rest of the number in pairs ('twaalf, vierendertig'), a leftover triple digit by digit."""
    digits = re.sub(r"\D", "", s)
    if len(digits) % 2:
        return ", ".join([_words(int(digits[i:i + 2]), lang) for i in range(0, len(digits) - 3, 2)] + [_digits(digits[-3:], lang)])
    return ", ".join(_words(int(digits[i:i + 2]), lang) for i in range(0, len(digits), 2))


def _phone_uk(m: re.Match) -> str:
    d = "0" + re.sub(r"\D", "", m.group(1))
    if len(d) == 11 and d.startswith("07"):
        groups = (d[:5], d[5:8], d[8:])
    elif len(d) == 11 and d.startswith("02"):
        groups = (d[:3], d[3:7], d[7:])
    elif len(d) == 11:
        groups = (d[:5], d[5:8], d[8:])
    elif len(d) == 10:
        groups = (d[:3], d[3:6], d[6:])
    else:
        groups = (d[:4], d[4:7], d[7:])
    return ", ".join(_digits(g, "en", oh=True) for g in groups if g)


def _phone_nl(m: re.Match) -> str:
    d = "0" + re.sub(r"\D", "", m.group(1))
    if d.startswith("06"):
        return f"{_digits(d[:2], 'nl')}, {_pairs(d[2:], 'nl')}"
    area = d[:3] if len(d) == 10 else d[:4]
    return f"{_digits(area, 'nl')}, {_pairs(d[len(area):], 'nl')}"


def _cents(c: str, unit: tuple, lang: str = "en") -> str:
    c = (c + "0")[:2]
    n = int(c)
    if lang == "nl":
        return f"{_words(n, 'nl')} cent"
    return f"{_words(n)} {unit[2] if n == 1 else unit[3]}"


def _money_en(m: re.Match) -> str:
    sym, whole, cents, mult = m.group(1), m.group(2), m.group(3), (m.group(4) or "").lower()
    unit = CURRENCIES.get(sym, CURRENCIES["$"])
    d = int(whole.replace(",", ""))
    if mult == "k":
        return f"{_words(d)} thousand {unit[1]}"
    if mult == "m":
        return f"{_words(d)} million {unit[1]}"
    if d == 0 and cents:
        return _cents(cents, unit)
    out = f"{_words(d)} {unit[1] if d != 1 else unit[0]}"
    if cents and int((cents + "0")[:2]):
        out += f" and {_cents(cents, unit)}"
    return out


def _money_nl(m: re.Match) -> str:
    whole = m.group(1) or m.group(4) or "0"
    cents = m.group(2) or m.group(5)
    d = int(re.sub(r"[^\d]", "", whole))
    if (m.group(3) or "").lower() == "k":
        return f"{_words(d, 'nl')}duizend euro"
    if d == 0 and cents:
        return _cents(cents, CURRENCIES["€"], "nl")
    out = f"{_words(d, 'nl')} euro"
    if cents and int((cents + "0")[:2]):
        out += f" {_words(int((cents + '0')[:2]), 'nl')}"
    return out


def _time(m: re.Match, lang: str) -> str:
    h, mi, ap = int(m.group(1)), m.group(2), (m.group(3) or "").replace(".", "").upper()
    if h > 24 or int(mi) > 59:
        return m.group(0)
    if lang == "nl":
        return f"{_words(h, 'nl')} uur" + (f" {_words(int(mi), 'nl')}" if mi != "00" else "")
    if ap == "UUR":
        ap = ""
    if mi == "00":
        mins = " o'clock" if not ap else ""
    elif mi.startswith("0"):
        mins = f" oh {_words(int(mi))}"
    else:
        mins = f" {_words(int(mi))}"
    return f"{_words(h)}{mins}{(' ' + ap) if ap else ''}"


def _year(m: re.Match, lang: str) -> str:
    try:
        return num2words(int(m.group(1)), to="year", lang=lang)
    except Exception:
        return _words(int(m.group(1)), lang)


def _ordinal(n: int, lang: str) -> str:
    try:
        return num2words(n, to="ordinal", lang=lang)
    except Exception:
        return str(n)


def _decimal_words(s: str, lang: str = "en") -> str:
    sep = "," if lang == "nl" else "."
    if sep in s:
        a, b = s.split(sep, 1)
        return f"{_int(a, lang)} {'komma' if lang == 'nl' else 'point'} {_digits(b, lang)}"
    if lang == "nl" and "." in s:
        a, b = s.split(".", 1)
        return f"{_int(a, lang)} komma {_digits(b, lang)}"
    return _int(s, lang)


def _speakable_en(t: str, locale: str) -> str:
    style = loc.get(locale)["phone_style"]
    t = (_PHONE_UK.sub(_phone_uk, t) if style == "uk" else _PHONE_US.sub(lambda m: f"{_digits(m.group(1))}, {_digits(m.group(2))}, {_digits(m.group(3))}", t))
    t = _MONEY_EN.sub(_money_en, t)
    t = _PERCENT_EN.sub(lambda m: f"{_decimal_words(m.group(1))} percent", t)
    t = _TIME.sub(lambda m: _time(m, "en"), t)
    default_sym = loc.get(locale)["symbol"]
    t = _BARE_CENTS.sub(lambda m: _money_en(re.match(_MONEY_EN, f"{default_sym}{m.group(1)}.{m.group(2)}")), t)
    t = _K.sub(lambda m: f"{_decimal_words(m.group(1).replace(',', '.'))} thousand", t)
    t = _ORDINAL_EN.sub(lambda m: _ordinal(int(m.group(1)), "en"), t)
    t = _DECIMAL_EN.sub(lambda m: f"{_int(m.group(1))} point {_digits(m.group(2))}", t)
    t = _YEAR.sub(lambda m: _year(m, "en"), t)
    t = _COMMA_INT.sub(lambda m: _int(m.group(0)), t)
    t = _INT.sub(lambda m: _int(m.group(1)) if len(m.group(1)) <= 9 else _digits(m.group(1)), t)
    return t


def _speakable_nl(t: str) -> str:
    t = _PHONE_NL.sub(_phone_nl, t)
    t = _MONEY_NL.sub(_money_nl, t)
    t = _PERCENT_NL.sub(lambda m: f"{_decimal_words(m.group(1), 'nl')} procent", t)
    t = _TIME.sub(lambda m: _time(m, "nl"), t)
    t = _K.sub(lambda m: f"{_decimal_words(m.group(1), 'nl')}duizend", t)
    t = _ORDINAL_NL.sub(lambda m: _ordinal(int(m.group(1)), "nl"), t)
    t = _YEAR.sub(lambda m: _year(m, "nl"), t)
    t = _DOT_INT.sub(lambda m: _int(m.group(0), "nl"), t)
    t = _COMMA_INT.sub(lambda m: _int(m.group(0), "nl"), t)
    t = _DECIMAL_NL.sub(lambda m: f"{_int(m.group(1), 'nl')} komma {_digits(m.group(2), 'nl')}", t)
    t = _INT.sub(lambda m: _int(m.group(1), "nl") if len(m.group(1)) <= 9 else _digits(m.group(1), "nl"), t)
    return t


def speakable(text: str, locale: Optional[str] = None) -> str:
    """Rewrite every digit sequence the way a person would say it on the phone, in the locale's language. Idempotent and safe on text with no numbers."""
    if not text or not any(ch.isdigit() for ch in text):
        return text or ""
    t = _speakable_nl(text) if _lang(locale) == "nl" else _speakable_en(text, locale or loc.DEFAULT)
    return re.sub(r"[ \t]{2,}", " ", t).strip()


NUMBERS_RULES = {
    "en": ("NUMBERS: your words are spoken aloud by a voice, so write every number the way you would SAY it, never in digits or symbols: "
           "'a hundred and thirty-two dollars and eighty-nine cents' not '$132.89', 'four three five, two seven five, nine eight two nine' for a phone number, "
           "'twenty twenty-two Tahoe' not '2022 Tahoe', 'forty-five thousand miles', 'nine thirty tomorrow morning', 'six point nine percent', 'the third'. "),
    "nl": ("GETALLEN: je woorden worden hardop uitgesproken door een stem, dus schrijf elk getal zoals je het ZEGT, nooit in cijfers of symbolen: "
           "'honderdtweeëndertig euro negenentachtig' en niet '€132,89', 'nul zes, twaalf, vierendertig, zesenvijftig, achtenzeventig' voor een telefoonnummer, "
           "'een Golf uit tweeduizend tweeëntwintig' en niet '2022 Golf', 'vijfenveertigduizend kilometer', 'morgenochtend half tien', 'zes komma negen procent', 'de derde'. "),
}
NUMBERS_RULE = NUMBERS_RULES["en"]


def numbers_rule(locale: Optional[str] = None) -> str:
    return NUMBERS_RULES.get(_lang(locale), NUMBERS_RULES["en"])
