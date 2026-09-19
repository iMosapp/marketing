"""Pre-flight for a store's A2P 10DLC packet: the checks Twilio / TCR reviewers actually reject on, run before the team submits.

`run(rec, numbers)` returns {score, verdict, checks[], blockers, warnings, at}. Levels: pass | warn | block. A block is something
the campaign is very likely to be rejected for (missing EIN, dead privacy link, link shorteners in samples); a warn is a known
soft reason (free email domain, no STOP in samples, no entity suffix)."""
import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

FREE_MAIL = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "aol.com", "me.com", "live.com", "msn.com", "ymail.com", "protonmail.com"}
SHORTENERS = ("bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly", "is.gd", "buff.ly", "rebrand.ly", "cutt.ly", "tiny.cc", "shorturl.at", "rb.gy")
ENTITY_SUFFIX = re.compile(r"\b(llc|l\.l\.c\.|inc\.?|incorporated|corp\.?|corporation|co\.|company|ltd\.?|limited|lp|l\.p\.|llp|pllc|pc|p\.c\.)\b", re.I)
CONSENT_WORDS = ("consent", "opt-in", "opt in", "opts in", "agree", "checkbox", "check box", "form", "verbal", "in person", "website", "signs", "sign up", "text us first", "texts the rep", "text the rep")
NO_SHARE = re.compile(r"(mobile|sms|text(ing)?( message)?|phone number|opt-?in).{0,200}?(not|never|won'?t|will not).{0,120}?(shar|sold|sell|disclos).{0,120}?(third[- ]part|affiliate)", re.I | re.S)
NO_SHARE_ALT = re.compile(r"(no mobile (information|data) will be shared|not (be )?shared with third parties|will not be shared or sold)", re.I)
SMS_MENTION = re.compile(r"\b(sms|text(s|ing|ed)?|mms|mobile messag)\b", re.I)
TERMS_NEED = {
    "STOP to opt out": re.compile(r"\bstop\b", re.I),
    "HELP for help": re.compile(r"\bhelp\b", re.I),
    "message and data rates may apply": re.compile(r"(msg|message)s?\s*(&|and)\s*data rates", re.I),
    "message frequency": re.compile(r"(message frequency|messages? per (month|week|day)|msgs?/(mo|month)|frequency (varies|may vary)|recurring messages)", re.I),
}
VERDICTS = {"likely": "Likely to pass", "needs_work": "Should pass, fix the warnings first", "reject": "Will likely be rejected as is"}


def _now():
    return datetime.now(timezone.utc)


def _domain(url: str) -> str:
    try:
        h = urlparse(url if "://" in url else f"https://{url}").hostname or ""
    except Exception:
        return ""
    return h.lower().removeprefix("www.")


def _text_of(html: str) -> str:
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html or "", flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t)


async def fetch(url: str) -> tuple[Optional[int], str, str]:
    """(status, text, final_url). status None on network failure."""
    if not url:
        return None, "", ""
    u = url if "://" in url else f"https://{url}"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0, headers={"User-Agent": "Mozilla/5.0 (compatible; iMOS-compliance-preflight/1.0)"}) as c:
            r = await c.get(u)
        return r.status_code, _text_of(r.text[:600_000]), str(r.url)
    except Exception as e:
        logger.info(f"[Preflight] fetch {u}: {e}")
        return None, "", u


class Checks:
    def __init__(self):
        self.items: list[dict] = []

    def add(self, key: str, label: str, level: str, detail: str = "", fix: str = ""):
        self.items.append({"key": key, "label": label, "level": level, "detail": detail, "fix": fix})

    def ok(self, key, label, detail=""):
        self.add(key, label, "pass", detail)


async def run(rec: dict, numbers: list[dict], store: Optional[dict] = None) -> dict:
    b, rp, c = rec.get("business") or {}, rec.get("rep") or {}, rec.get("campaign") or {}
    ck = Checks()
    brand_words = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", (store or {}).get("name") or b.get("legal_name") or "") if w.lower() not in {"the", "and", "llc", "inc", "corp"}}

    # ── business ──────────────────────────────────────────────────────────────
    ein = re.sub(r"\D", "", str(b.get("ein") or ""))
    if len(ein) == 9:
        ck.ok("ein", "EIN on file", "9 digits")
    else:
        ck.add("ein", "EIN", "block", "Missing or not 9 digits." if ein else "Missing.", "Enter the EIN exactly as on the IRS CP-575 or 147C letter. Brand registration fails instantly without a matching EIN.")
    name = (b.get("legal_name") or "").strip()
    if not name:
        ck.add("legal_name", "Legal business name", "block", "Missing.", "Use the exact legal name on the IRS letter, not the DBA.")
    elif b.get("business_type") != "Sole Proprietorship" and not ENTITY_SUFFIX.search(name):
        ck.add("legal_name", "Legal business name", "warn", f"\"{name}\" has no entity suffix (LLC, Inc, Corp).", "TCR matches the legal name against the EIN record. If the IRS letter says \"Smith Motors LLC\", use exactly that.")
    else:
        ck.ok("legal_name", "Legal business name", name)
    if b.get("business_type") == "Sole Proprietorship":
        ck.add("business_type", "Sole proprietorship", "warn", "Sole proprietors register differently: one number, 1,000 segments/day, personal cell verification.", "If the dealership has an EIN, pick the real entity type instead.")
    st, zp = (b.get("state") or "").strip(), re.sub(r"\D", "", str(b.get("postal_code") or ""))
    if b.get("street") and b.get("city") and re.fullmatch(r"[A-Za-z]{2}", st) and len(zp) in (5, 9):
        ck.ok("address", "Business address", f"{b.get('street')}, {b.get('city')}, {st} {zp[:5]}")
    else:
        ck.add("address", "Business address", "block", "Street, city, 2-letter state and 5-digit ZIP are all required.", "Use the address on the IRS record; a PO box is fine if that is what the IRS has.")

    # ── website ───────────────────────────────────────────────────────────────
    site = (b.get("website") or "").strip()
    site_status, site_text, _ = await fetch(site) if site else (None, "", "")
    if not site:
        ck.add("website", "Website", "block", "Missing.", "Twilio requires a working public website for the brand.")
    elif site_status and site_status < 400:
        ck.ok("website", "Website reachable", f"HTTP {site_status}" + ("" if site.startswith("https") else " (add https://)"))
    else:
        ck.add("website", "Website", "block", f"Not reachable (HTTP {site_status})." if site_status else "Could not load it.", "Fix the URL or the site before submitting; reviewers open it.")
    site_dom = _domain(site)

    # ── authorized rep ────────────────────────────────────────────────────────
    email = (rp.get("email") or "").strip().lower()
    edom = email.split("@")[-1] if "@" in email else ""
    if not email or not edom:
        ck.add("rep_email", "Representative email", "block", "Missing.", "A real person at the dealership; Twilio may email them.")
    elif edom in FREE_MAIL:
        ck.add("rep_email", "Representative email", "warn", f"{email} is a free mailbox.", "Use an address on the dealership's own domain; free email is one of the most common rejection reasons.")
    elif site_dom and edom != site_dom and not edom.endswith("." + site_dom) and not site_dom.endswith("." + edom):
        ck.add("rep_email", "Representative email", "warn", f"{edom} does not match the website domain {site_dom}.", "Reviewers like the rep's email domain to match the website. Acceptable if it is the dealer group's domain.")
    else:
        ck.ok("rep_email", "Representative email", email)
    phone = re.sub(r"\D", "", str(rp.get("phone") or ""))
    if len(phone) in (10, 11):
        ck.ok("rep_phone", "Representative phone", rp.get("phone"))
    else:
        ck.add("rep_phone", "Representative phone", "block", "Missing or not a full number.", "Direct line or cell of the GM / controller.")
    if not (rp.get("first_name") and rp.get("last_name") and rp.get("title")):
        ck.add("rep_name", "Representative name and title", "block", "Missing.", "First name, last name and title (General Manager, Owner, Controller).")
    else:
        ck.ok("rep_name", "Representative", f"{rp.get('first_name')} {rp.get('last_name')}, {rp.get('title')}")

    # ── privacy + terms ───────────────────────────────────────────────────────
    purl, turl = (c.get("privacy_url") or "").strip(), (c.get("terms_url") or "").strip()
    (p_status, p_text, _), (t_status, t_text, _) = await asyncio.gather(fetch(purl), fetch(turl))
    if not purl:
        ck.add("privacy", "Privacy policy URL", "block", "Missing.", "Twilio requires a public privacy policy that covers texting.")
    elif not p_status or p_status >= 400:
        ck.add("privacy", "Privacy policy URL", "block", f"Not reachable (HTTP {p_status})." if p_status else "Could not load it.", "The page must be public, no login, no 404.")
    else:
        has_sms, has_no_share = bool(SMS_MENTION.search(p_text)), bool(NO_SHARE.search(p_text) or NO_SHARE_ALT.search(p_text))
        if has_sms and has_no_share:
            ck.ok("privacy", "Privacy policy", "Public, mentions texting and the no-sharing statement")
        elif has_sms:
            ck.add("privacy", "Privacy policy wording", "warn", "Mentions texting but we could not find the no-sharing statement.", "Add: \"No mobile information will be shared with third parties or affiliates for marketing or promotional purposes.\" Campaigns get rejected for this exact sentence being absent.")
        else:
            ck.add("privacy", "Privacy policy wording", "block", "Does not mention SMS / text messaging at all.", "Add a texting section: how numbers are collected, that consent is not a condition of purchase, and \"No mobile information will be shared with third parties or affiliates for marketing or promotional purposes.\"")
    if not turl:
        ck.add("terms", "Terms URL", "block", "Missing.", "Public terms (or an SMS terms page) with STOP, HELP, message frequency and rates.")
    elif not t_status or t_status >= 400:
        ck.add("terms", "Terms URL", "block", f"Not reachable (HTTP {t_status})." if t_status else "Could not load it.", "The page must be public, no login, no 404.")
    else:
        missing = [k for k, rx in TERMS_NEED.items() if not rx.search(t_text)]
        if purl and turl and _domain(purl) and purl.rstrip("/") == turl.rstrip("/"):
            ck.add("terms", "Terms URL", "warn", "Same page as the privacy policy.", "Fine if that page carries the SMS terms; a separate /sms-terms page is cleaner.")
        elif missing:
            ck.add("terms", "Terms wording", "warn", "Missing: " + ", ".join(missing) + ".", "Add a short SMS terms block: \"Reply STOP to opt out, HELP for help. Message frequency varies. Msg & data rates may apply.\"")
        else:
            ck.ok("terms", "Terms page", "Public, STOP / HELP / rates / frequency all present")

    # ── campaign ──────────────────────────────────────────────────────────────
    desc, flow = (c.get("description") or "").strip(), (c.get("message_flow") or "").strip()
    if len(desc) < 40:
        ck.add("description", "Campaign description", "block" if not desc else "warn", "Missing." if not desc else "Too short.", "Two or three sentences: who texts whom, about what, how often.")
    else:
        ck.ok("description", "Campaign description", f"{len(desc)} characters")
    if len(flow) < 40:
        ck.add("message_flow", "Opt-in flow (how customers consent)", "block" if not flow else "warn", "Missing." if not flow else "Too short.", "Describe every way a number is collected and that the customer agrees to texts; mention that consent is recorded.")
    elif not any(w in flow.lower() for w in CONSENT_WORDS):
        ck.add("message_flow", "Opt-in flow wording", "warn", "Does not say how the customer consents.", "Use the word consent or opt-in and name the moments: in person, credit application, website form, or the customer texting first.")
    else:
        ck.ok("message_flow", "Opt-in flow", "Describes consent")
    samples = [str(s).strip() for s in (c.get("samples") or []) if str(s).strip()]
    use_case = c.get("use_case") or "LOW_VOLUME"
    if len(samples) < 2:
        ck.add("samples", "Sample messages", "block", f"{len(samples)} given, 2 required.", "Two to three real texts a rep would send, each 20 to 1,024 characters.")
    else:
        bad_len = [i + 1 for i, s in enumerate(samples) if not 20 <= len(s) <= 1024]
        short = [i + 1 for i, s in enumerate(samples) if any(sh in s.lower() for sh in SHORTENERS)]
        placeholders = [i + 1 for i, s in enumerate(samples) if re.search(r"\[[^\]]+\]|\{[^}]+\}|<[^>]+>", s)]
        has_brand = any(any(w in s.lower() for w in brand_words) for s in samples) if brand_words else True
        has_stop = any(re.search(r"\bstop\b", s, re.I) for s in samples)
        if bad_len:
            ck.add("samples_len", "Sample message length", "block", f"Sample {', '.join(map(str, bad_len))} outside 20 to 1,024 characters.", "Make every sample a real, complete text.")
        if short:
            ck.add("samples_short", "Link shorteners in samples", "block", f"Sample {', '.join(map(str, short))} uses a public shortener.", "Public shorteners (bit.ly, tinyurl) are an automatic rejection. Use the full dealership link.")
        if placeholders:
            ck.add("samples_placeholders", "Placeholders in samples", "warn", f"Sample {', '.join(map(str, placeholders))} has [brackets] or {{braces}}.", "Write them like real texts: \"Hi Jordan, this is Sam at Smith Motors ...\".")
        if not has_brand:
            ck.add("samples_brand", "Dealership name in samples", "warn", "No sample names the dealership.", "Every sample should identify the sender: \"Sam at Smith Motors\".")
        if not has_stop:
            ck.add("samples_stop", "Opt-out language in samples", "block" if use_case in ("MARKETING", "MIXED") else "warn", "No sample ends with STOP instructions.", "End at least one sample with \"Reply STOP to opt out\" (required for marketing and mixed campaigns).")
        if not (bad_len or short or placeholders) and has_brand and has_stop:
            ck.ok("samples", "Sample messages", f"{len(samples)} samples, brand named, STOP present")
    if use_case == "MARKETING":
        ck.add("use_case", "Marketing use case", "warn", "Marketing gets the strictest review.", "If reps mostly do one-to-one follow-ups, LOW_VOLUME or MIXED is more accurate and easier to pass.")
    for k, label in (("opt_in_message", "Opt-in confirmation text"), ("opt_out_message", "STOP reply"), ("help_message", "HELP reply")):
        if not (c.get(k) or "").strip():
            ck.add(k, label, "warn", "Missing.", "Twilio asks for the exact auto-reply text.")

    # ── numbers + caller id ───────────────────────────────────────────────────
    if numbers:
        ck.ok("numbers", "Numbers attached", f"{len(numbers)} rep number{'s' if len(numbers) != 1 else ''} will be added to the campaign")
    else:
        ck.add("numbers", "Numbers attached", "warn", "No rep on this store has a Twilio number yet.", "The campaign can be created now; reps cannot text until a number is assigned and attached (that happens automatically).")
    cn = rec.get("cnam") or {}
    if cn.get("enabled") is not False:
        dn = (cn.get("display_name") or "").strip()
        if 1 <= len(dn) <= 15 and re.fullmatch(r"[A-Z0-9 ]+", dn):
            ck.ok("cnam", "Caller ID name", dn)
        else:
            ck.add("cnam", "Caller ID name", "warn", f"\"{dn}\" is not 1 to 15 upper-case letters, digits and spaces." if dn else "Missing.", "Example: SMITH MOTORS")

    blockers = sum(1 for x in ck.items if x["level"] == "block")
    warnings = sum(1 for x in ck.items if x["level"] == "warn")
    score = max(0, 100 - 25 * blockers - 8 * warnings)
    verdict = "reject" if blockers else ("likely" if score >= 85 else "needs_work")
    order = {"block": 0, "warn": 1, "pass": 2}
    return {"at": _now(), "score": score, "verdict": verdict, "verdict_label": VERDICTS[verdict], "blockers": blockers, "warnings": warnings,
            "checks": sorted(ck.items, key=lambda x: order[x["level"]])}
