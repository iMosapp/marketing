"""Locales: the country + language + currency + voices a store or shop client runs in.
en-US is the default and behaves exactly as before. Everything that speaks, writes money or picks a voice asks this module.
Voice IDs can be overridden per locale in db.settings {key: "locale_voices"} so a native speaker can swap in better ElevenLabs voices without a deploy."""
from typing import Optional

DEFAULT = "en-US"

# relay voices are "Provider:voiceId" so one locale can mix providers per voice type (ConversationRelay picks the provider per call)
LOCALES = {
    "en-US": {"label": "United States", "language": "en", "language_label": "English (US)", "country": "US", "currency": "usd", "symbol": "$", "timezone": "America/Denver", "flag": "US",
              "relay": {"female": "Google:en-US-Journey-F", "male": "Google:en-US-Journey-D", "young": "Google:en-US-Journey-O", "older": "Google:en-US-Journey-F"},
              "relay_language": "en-US", "say_voice": "Polly.Joanna-Neural", "whisper": "en", "phone_style": "us", "decimal": ".", "date": "%B %-d, %Y"},
    "en-GB": {"label": "United Kingdom", "language": "en", "language_label": "English (UK)", "country": "GB", "currency": "gbp", "symbol": "£", "timezone": "Europe/London", "flag": "GB",
              "relay": {"female": "ElevenLabs:19STyYD15bswVz51nqLf", "male": "ElevenLabs:Fahco4VZzobUeiPqni1S", "young": "ElevenLabs:19STyYD15bswVz51nqLf", "older": "ElevenLabs:NNl6r8mD7vthiJatiJt1"},
              "relay_language": "en-GB", "say_voice": "Polly.Amy-Neural", "whisper": "en", "phone_style": "uk", "decimal": ".", "date": "%-d %B %Y"},
    "en-IE": {"label": "Ireland", "language": "en", "language_label": "English (Ireland)", "country": "IE", "currency": "eur", "symbol": "€", "timezone": "Europe/Dublin", "flag": "IE",
              "relay": {"female": "ElevenLabs:19STyYD15bswVz51nqLf", "male": "ElevenLabs:Fahco4VZzobUeiPqni1S", "young": "ElevenLabs:19STyYD15bswVz51nqLf", "older": "ElevenLabs:NNl6r8mD7vthiJatiJt1"},
              "relay_language": "en-GB", "say_voice": "Polly.Niamh-Neural", "whisper": "en", "phone_style": "uk", "decimal": ".", "date": "%-d %B %Y"},
    "nl-NL": {"label": "Netherlands", "language": "nl", "language_label": "Nederlands", "country": "NL", "currency": "eur", "symbol": "€", "timezone": "Europe/Amsterdam", "flag": "NL",
              "relay": {"female": "ElevenLabs:D6MRWCKoavI2xUJXmaCb", "male": "ElevenLabs:UNBIyLbtFB9k7FKW8wJv", "young": "ElevenLabs:D6MRWCKoavI2xUJXmaCb", "older": "ElevenLabs:tfweP7lGJyLeNV9dH1Rm"},
              "relay_language": "nl-NL", "say_voice": "Polly.Laura-Neural", "whisper": "nl", "phone_style": "nl", "decimal": ",", "date": "%-d %B %Y"},
    "nl-BE": {"label": "Belgium (Flemish)", "language": "nl", "language_label": "Nederlands (Vlaams)", "country": "BE", "currency": "eur", "symbol": "€", "timezone": "Europe/Brussels", "flag": "BE",
              "relay": {"female": "ElevenLabs:s7Z6uboUuE4Nd8Q2nye6", "male": "ElevenLabs:UNBIyLbtFB9k7FKW8wJv", "young": "ElevenLabs:s7Z6uboUuE4Nd8Q2nye6", "older": "ElevenLabs:tfweP7lGJyLeNV9dH1Rm"},
              "relay_language": "nl-BE", "say_voice": "Polly.Lisa-Neural", "whisper": "nl", "phone_style": "nl", "decimal": ",", "date": "%-d %B %Y"},
}

# what the LLM is told about the language it must write/speak in
LANGUAGE_RULES = {
    "en": "",
    "nl": ("LANGUAGE: Write and speak ONLY natural Dutch as spoken in the Netherlands (Nederlands), never English, even if the other person mixes in English words. "
           "Use everyday spoken Dutch with 'je/jij' unless the other person is clearly formal, then 'u'. Use Dutch car and business words a Dutch consumer uses "
           "(kenteken, APK, inruil, occasion, proefrit, private lease, bijtelling, rijklaarmaakkosten, afspraak, offerte, werkplaats, onderdelen, schadeherstel, huurauto). "
           "Prices in euro's, distances in kilometers, dates and times the Dutch way. "),
}
LANGUAGE_RULES["nl-BE"] = LANGUAGE_RULES["nl"].replace("as spoken in the Netherlands (Nederlands)", "as spoken in Flanders (Vlaams)")
LANGUAGE_RULES["en-GB"] = ("LANGUAGE: Speak and write natural British English as used in the UK motor trade, with British spelling (colour, tyre, favour, organise, centre). "
                           "Use the words a British car buyer uses: part exchange (never trade-in), MOT, reg or registration plate (never VIN or license plate), bonnet, boot, tyres, windscreen, "
                           "saloon, estate, hatchback, forecourt, showroom, screen price or asking price (never sticker price or MSRP), a deposit and monthly payments on PCP or HP finance, "
                           "road tax, service plan, courtesy car, postcode (never ZIP), mobile (never cell). Prices in pounds, mileage in miles, dates day then month. ")
LANGUAGE_RULES["en-IE"] = (LANGUAGE_RULES["en-GB"].replace("British English as used in the UK motor trade", "Irish English as spoken in Ireland").replace("a British car buyer", "an Irish car buyer")
                           .replace("MOT", "NCT").replace("road tax", "motor tax").replace("postcode (never ZIP)", "Eircode (never ZIP)").replace("Prices in pounds, mileage in miles", "Prices in euro, distances and mileage in kilometres"))

# regional English with its own client-facing wording; everything else keys on the plain language
DIALECTS = ("en-GB", "en-IE")

_VOICE_OVERRIDES: dict = {}


def get(code: Optional[str]) -> dict:
    return LOCALES.get(code or DEFAULT) or LOCALES[DEFAULT]


def key_of(doc: Optional[dict]) -> str:
    """Locale of a store or shop client document; anything unknown or missing is en-US."""
    code = (doc or {}).get("locale")
    return code if code in LOCALES else DEFAULT


def language(code: Optional[str]) -> str:
    return get(code)["language"]


def currency(code: Optional[str]) -> str:
    return get(code)["currency"]


def dialect(code: Optional[str]) -> str:
    """Text key for client-facing copy: 'en', 'nl', or a regional English ('en-GB', 'en-IE') with its own wording."""
    return code if code in DIALECTS else language(code)


def language_rule(code: Optional[str]) -> str:
    """Prompt fragment forcing the model into the locale's language ('' for English)."""
    if code in LANGUAGE_RULES:
        return LANGUAGE_RULES[code]
    return LANGUAGE_RULES.get(language(code), "")


def relay_voice(code: Optional[str], voice_type: Optional[str]) -> tuple:
    """(ttsProvider, voice) for ConversationRelay, honouring db overrides."""
    loc = get(code)
    voices = {**loc["relay"], **_VOICE_OVERRIDES.get(code or DEFAULT, {})}
    spec = voices.get(voice_type or "female") or voices.get("female") or next(iter(voices.values()))
    provider, _, voice = spec.partition(":")
    return (provider or "Google"), voice


def say_voice(code: Optional[str]) -> str:
    return _VOICE_OVERRIDES.get(code or DEFAULT, {}).get("say") or get(code)["say_voice"]


def for_api() -> list:
    return [{"code": k, **{f: v[f] for f in ("label", "language", "language_label", "country", "currency", "symbol", "timezone", "flag", "relay_language", "say_voice")},
             "voices": {**v["relay"], **_VOICE_OVERRIDES.get(k, {})}} for k, v in LOCALES.items()]


async def load_overrides(db):
    """Pull voice overrides once at startup (and after every PUT)."""
    global _VOICE_OVERRIDES
    doc = await db.settings.find_one({"key": "locale_voices"}) or {}
    _VOICE_OVERRIDES = {k: v for k, v in (doc.get("voices") or {}).items() if k in LOCALES and isinstance(v, dict)}


async def set_voices(db, code: str, voices: dict) -> dict:
    """Override voice ids for one locale: {"female": "ElevenLabs:xxx", "male": ..., "say": "Polly.Laura-Neural"}. Empty value removes the override."""
    if code not in LOCALES:
        raise ValueError("Unknown locale")
    clean = {k: str(v).strip() for k, v in (voices or {}).items() if k in ("female", "male", "young", "older", "say") and str(v or "").strip()}
    await db.settings.update_one({"key": "locale_voices"}, {"$set": {f"voices.{code}": clean}}, upsert=True)
    await load_overrides(db)
    return {**LOCALES[code]["relay"], **clean}


async def store_locale(db, store_id) -> str:
    """Locale of a store by id; en-US when unknown."""
    from bson import ObjectId
    if not store_id or not ObjectId.is_valid(str(store_id)):
        return DEFAULT
    s = await db.stores.find_one({"_id": ObjectId(str(store_id))}, {"locale": 1})
    return key_of(s)


async def user_locale(db, user: Optional[dict]) -> str:
    return await store_locale(db, (user or {}).get("store_id"))
