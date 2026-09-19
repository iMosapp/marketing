"""Per-store Twilio texting compliance: Trust Hub Secondary Customer Profile -> A2P Messaging Profile -> Brand -> Messaging Service +
Campaign, plus an optional CNAM display name, all driven from the store record and advanced by a background poller.

Every dealership whose reps text from our numbers is its own brand in carriers' eyes (ISV rule), so nothing here ever runs under
i'M On Social's own profile. State lives in `stores.compliance`; `advance()` is idempotent and moves a store one step at a time, so a
poller can call it every few minutes and a rejection can be fixed and resubmitted from the admin.

Modes (settings key `twilio_compliance.mode`): `dry_run` (no Twilio calls, fake SIDs, auto-approves; the default and what preview uses),
`mock` (real Trust Hub profiles, Twilio *mock* brand and campaign: no TCR fees, cannot send), `live`."""
import asyncio
import logging
import os
import re
import secrets
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

logger = logging.getLogger(__name__)

SETTINGS_KEY = "twilio_compliance"
MODES = ("dry_run", "mock", "live")
CUSTOMER_POLICY = os.environ.get("TWILIO_TRUSTHUB_CUSTOMER_POLICY", "RNdfbf3fae0e1107f8aded0e7cead80bf5")
A2P_POLICY = os.environ.get("TWILIO_TRUSTHUB_A2P_POLICY", "RNb0d4771c2c98518d916a3d4cd70a8f8b")
CNAM_POLICY = os.environ.get("TWILIO_TRUSTHUB_CNAM_POLICY", "RN7a97559effdf62d00f4298208492a5ea")

STAGES = ("draft", "profile", "a2p", "brand", "campaign", "complete")
STAGE_LABEL = {"draft": "Not started", "profile": "Business profile", "a2p": "A2P messaging profile", "brand": "Brand", "campaign": "Campaign", "complete": "Approved"}
APPROVED = {"twilio-approved", "APPROVED", "VERIFIED"}
REJECTED = {"twilio-rejected", "FAILED", "SUSPENDED", "REJECTED"}
BUSINESS_TYPES = ("Corporation", "Limited Liability Corporation", "Partnership", "Sole Proprietorship", "Non-profit Corporation", "Co-operative")
JOB_POSITIONS = ("Director", "GM", "VP", "CEO", "CFO", "General Counsel", "Other")
USE_CASES = {
    "LOW_VOLUME": "Low volume mixed (up to ~2,000 segments/day, no vetting needed)",
    "MIXED": "Mixed (follow-ups, offers, appointment reminders)",
    "CUSTOMER_CARE": "Customer care (support and account follow-up)",
    "MARKETING": "Marketing (offers and promotions)",
}
REQUIRED_BUSINESS = ("legal_name", "ein", "business_type", "website", "street", "city", "state", "postal_code")
REQUIRED_REP = ("first_name", "last_name", "email", "phone", "title", "job_position")
REQUIRED_CAMPAIGN = ("use_case", "description", "message_flow", "privacy_url", "terms_url")


def _now():
    return datetime.now(timezone.utc)


# ── defaults from the store record ────────────────────────────────────────────
def defaults(store: dict) -> dict:
    """A compliance record pre-filled from what we already know about the store; the admin completes the rest."""
    name = store.get("name") or "the dealership"
    site = (store.get("website") or "").strip()
    base = site.rstrip("/") if site.startswith("http") else (f"https://{site.rstrip('/')}" if site else "")
    return {
        "business": {
            "legal_name": name, "ein": "", "business_type": "Limited Liability Corporation", "website": base,
            "street": store.get("address") or "", "city": store.get("city") or "", "state": store.get("state") or "", "postal_code": store.get("zip_code") or "", "country": store.get("country") or "US",
            "company_type": "private",
        },
        "rep": {"first_name": "", "last_name": "", "email": "", "phone": store.get("phone") or "", "title": "General Manager", "job_position": "GM"},
        "campaign": {
            "use_case": "LOW_VOLUME",
            "description": f"{name} sales and service reps text customers who bought a vehicle from them or asked to be contacted: follow-ups after a visit, appointment reminders, vehicle updates and occasional offers. One rep, one customer, one conversation at a time.",
            "message_flow": f"Customers give their mobile number to their {name} sales or service rep in person, on a credit application, on the {name} website contact form, or by texting the rep first, and agree to receive texts from {name}. Consent is recorded on the customer record. Every message includes the rep's name and STOP opt-out instructions; STOP is honored immediately.",
            "samples": [
                f"Hi Jordan, this is Sam at {name}. Your Tahoe is ready for pickup any time after 3 today. Reply STOP to opt out.",
                f"Hey Jordan, Sam from {name} here. Still thinking about the black Wrangler? I can hold it through Saturday. Reply STOP to opt out.",
                f"Jordan, it's Sam at {name}: quick reminder about your service appointment tomorrow at 9. Reply STOP to opt out.",
            ],
            "privacy_url": f"{base}/privacy" if base else "", "terms_url": f"{base}/terms" if base else "",
            "opt_in_keywords": ["START", "YES"], "opt_out_keywords": ["STOP", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"], "help_keywords": ["HELP", "INFO"],
            "opt_in_message": f"You're now receiving texts from your {name} rep. Reply HELP for help or STOP to opt out. Msg & data rates may apply.",
            "opt_out_message": f"You've been unsubscribed from {name} texts. No more messages will be sent. Reply START to opt back in.",
            "help_message": f"{name}: text your rep any time or call the store. Reply STOP to opt out.",
            "has_embedded_links": True, "has_embedded_phone": True,
        },
        "cnam": {"display_name": cnam_name(name), "enabled": True},
    }


def cnam_name(name: str) -> str:
    """CNAM display names: 15 chars max, letters/digits/spaces, carriers show them upper-case."""
    clean = re.sub(r"[^A-Za-z0-9 ]+", "", name or "").upper()
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) > 15:
        words = clean.split(" ")
        while len(" ".join(words)) > 15 and len(words) > 1:
            words.pop()
        clean = " ".join(words)[:15].strip()
    return clean


def missing_fields(rec: dict) -> list[str]:
    out = []
    for k in REQUIRED_BUSINESS:
        if not str((rec.get("business") or {}).get(k) or "").strip():
            out.append(f"business.{k}")
    for k in REQUIRED_REP:
        if not str((rec.get("rep") or {}).get(k) or "").strip():
            out.append(f"rep.{k}")
    for k in REQUIRED_CAMPAIGN:
        if not str((rec.get("campaign") or {}).get(k) or "").strip():
            out.append(f"campaign.{k}")
    samples = [s for s in ((rec.get("campaign") or {}).get("samples") or []) if str(s).strip()]
    if len(samples) < 2 or any(len(s) < 20 for s in samples):
        out.append("campaign.samples")
    ein = re.sub(r"\D", "", str((rec.get("business") or {}).get("ein") or ""))
    if ein and len(ein) != 9:
        out.append("business.ein_format")
    return out


# ── settings ──────────────────────────────────────────────────────────────────
async def get_settings(db) -> dict:
    doc = await db.settings.find_one({"key": SETTINGS_KEY}) or {}
    mode = doc.get("mode") if doc.get("mode") in MODES else "dry_run"
    return {"mode": mode, "notify_email": doc.get("notify_email") or os.environ.get("COMPLIANCE_NOTIFY_EMAIL", ""), "updated_at": doc.get("updated_at")}


async def set_settings(db, patch: dict, me: dict) -> dict:
    sets = {"updated_at": _now(), "updated_by": str(me.get("_id"))}
    if patch.get("mode") in MODES:
        sets["mode"] = patch["mode"]
    if "notify_email" in patch:
        sets["notify_email"] = str(patch.get("notify_email") or "").strip()
    await db.settings.update_one({"key": SETTINGS_KEY}, {"$set": sets, "$setOnInsert": {"key": SETTINGS_KEY}}, upsert=True)
    return await get_settings(db)


# ── Twilio adapters ───────────────────────────────────────────────────────────
class DryRunTwilio:
    """No network. Returns fake SIDs and approves everything on the next status poll, so the whole flow can be exercised anywhere."""
    name = "dry_run"

    def __init__(self):
        self.calls: list[tuple] = []

    def _sid(self, prefix: str) -> str:
        return prefix + secrets.token_hex(16)

    async def create_customer_profile(self, rec, email, callback):
        self.calls.append(("customer_profile", rec["business"]["legal_name"]))
        return {"customer_profile": self._sid("BU"), "business_info": self._sid("IT"), "rep": self._sid("IT"), "address": self._sid("AD"), "doc": self._sid("RD")}

    async def assign_numbers_to_profile(self, profile_sid, pn_sids):
        self.calls.append(("profile_numbers", profile_sid, tuple(pn_sids)))

    async def submit_customer_profile(self, profile_sid):
        self.calls.append(("submit_profile", profile_sid))
        return "pending-review"

    async def customer_profile_status(self, profile_sid):
        return "twilio-approved", ""

    async def create_a2p_product(self, rec, profile_sid, email, callback):
        self.calls.append(("a2p_product", profile_sid))
        return {"a2p_product": self._sid("BU"), "a2p_info": self._sid("IT")}

    async def a2p_status(self, product_sid):
        return "twilio-approved", ""

    async def create_brand(self, profile_sid, a2p_sid, mock):
        self.calls.append(("brand", profile_sid, a2p_sid, mock))
        return self._sid("BN")

    async def brand_status(self, brand_sid):
        return "APPROVED", ""

    async def create_messaging_service(self, name, inbound_url, pn_sids):
        self.calls.append(("messaging_service", name, tuple(pn_sids)))
        return self._sid("MG")

    async def add_numbers_to_service(self, service_sid, pn_sids):
        self.calls.append(("service_numbers", service_sid, tuple(pn_sids)))

    async def create_campaign(self, service_sid, brand_sid, rec):
        self.calls.append(("campaign", service_sid, brand_sid, rec["campaign"]["use_case"]))
        return self._sid("QE")

    async def campaign_status(self, service_sid, campaign_sid):
        return "VERIFIED", ""

    async def create_cnam(self, rec, profile_sid, pn_sids, email, callback):
        self.calls.append(("cnam", rec["cnam"]["display_name"], tuple(pn_sids)))
        return {"cnam_product": self._sid("BU"), "cnam_info": self._sid("IT")}

    async def cnam_status(self, product_sid):
        return "twilio-approved", ""

    async def assign_numbers_to_cnam(self, product_sid, pn_sids):
        self.calls.append(("cnam_numbers", product_sid, tuple(pn_sids)))


class LiveTwilio:
    """The real thing (twilio SDK is sync: every call runs in a thread)."""
    name = "live"

    def __init__(self):
        from twilio.rest import Client
        self.c = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])

    async def _t(self, fn, *a, **kw):
        return await asyncio.to_thread(fn, *a, **kw)

    async def create_customer_profile(self, rec, email, callback):
        b, r = rec["business"], rec["rep"]
        th = self.c.trusthub.v1
        profile = await self._t(th.customer_profiles.create, policy_sid=CUSTOMER_POLICY, friendly_name=f"{b['legal_name']} Secondary Customer Profile", email=email, status_callback=callback)
        info = await self._t(th.end_users.create, type="customer_profile_business_information", friendly_name=f"{b['legal_name']} Business Information", attributes={
            "business_name": b["legal_name"], "business_type": b["business_type"], "business_registration_identifier": "EIN",
            "business_registration_number": re.sub(r"\D", "", b["ein"]), "business_identity": "direct_customer", "business_industry": "AUTOMOTIVE",
            "business_regions_of_operation": "USA_AND_CANADA", "website_url": b["website"], "social_media_profile_urls": b.get("social_urls") or ""})
        rep = await self._t(th.end_users.create, type="authorized_representative_1", friendly_name=f"{b['legal_name']} Authorized Representative", attributes={
            "first_name": r["first_name"], "last_name": r["last_name"], "email": r["email"], "phone_number": r["phone"], "business_title": r["title"], "job_position": r["job_position"]})
        address = await self._t(self.c.addresses.create, customer_name=b["legal_name"], street=b["street"], city=b["city"], region=b["state"], postal_code=b["postal_code"], iso_country=b.get("country") or "US")
        doc = await self._t(th.supporting_documents.create, type="customer_profile_address", friendly_name=f"{b['legal_name']} Physical Address", attributes={"address_sids": address.sid})
        for sid in (info.sid, rep.sid, doc.sid):
            await self._t(th.customer_profiles(profile.sid).customer_profiles_entity_assignments.create, object_sid=sid)
        return {"customer_profile": profile.sid, "business_info": info.sid, "rep": rep.sid, "address": address.sid, "doc": doc.sid}

    async def assign_numbers_to_profile(self, profile_sid, pn_sids):
        for pn in pn_sids:
            await self._t(self.c.trusthub.v1.customer_profiles(profile_sid).customer_profiles_channel_endpoint_assignment.create, channel_endpoint_sid=pn, channel_endpoint_type="phone-number")

    async def submit_customer_profile(self, profile_sid):
        th = self.c.trusthub.v1
        ev = await self._t(th.customer_profiles(profile_sid).customer_profiles_evaluations.create, policy_sid=CUSTOMER_POLICY)
        if getattr(ev, "status", "") == "noncompliant":
            raise ValueError("Twilio evaluation: " + _eval_errors(ev))
        p = await self._t(th.customer_profiles(profile_sid).update, status="pending-review")
        return p.status

    async def customer_profile_status(self, profile_sid):
        p = await self._t(self.c.trusthub.v1.customer_profiles(profile_sid).fetch)
        return p.status, ""

    async def create_a2p_product(self, rec, profile_sid, email, callback):
        th = self.c.trusthub.v1
        b = rec["business"]
        tp = await self._t(th.trust_products.create, friendly_name=f"{b['legal_name']} A2P Messaging Profile", policy_sid=A2P_POLICY, email=email, status_callback=callback)
        info = await self._t(th.end_users.create, type="us_a2p_messaging_profile_information", friendly_name=f"{b['legal_name']} A2P Messaging Profile Information", attributes={"company_type": b.get("company_type") or "private"})
        for sid in (info.sid, profile_sid):
            await self._t(th.trust_products(tp.sid).trust_products_entity_assignments.create, object_sid=sid)
        ev = await self._t(th.trust_products(tp.sid).trust_products_evaluations.create, policy_sid=A2P_POLICY)
        if getattr(ev, "status", "") == "noncompliant":
            raise ValueError("Twilio evaluation: " + _eval_errors(ev))
        await self._t(th.trust_products(tp.sid).update, status="pending-review")
        return {"a2p_product": tp.sid, "a2p_info": info.sid}

    async def a2p_status(self, product_sid):
        p = await self._t(self.c.trusthub.v1.trust_products(product_sid).fetch)
        return p.status, ""

    async def create_brand(self, profile_sid, a2p_sid, mock):
        b = await self._t(self.c.messaging.v1.brand_registrations.create, customer_profile_bundle_sid=profile_sid, a2p_profile_bundle_sid=a2p_sid, brand_type="STANDARD", mock=mock, skip_automatic_sec_vet=True)
        return b.sid

    async def brand_status(self, brand_sid):
        b = await self._t(self.c.messaging.v1.brand_registrations(brand_sid).fetch)
        errs = getattr(b, "errors", None) or []
        return b.status, "; ".join(str(e.get("description") or e) for e in errs) if isinstance(errs, list) else str(errs or "")

    async def create_messaging_service(self, name, inbound_url, pn_sids):
        svc = await self._t(self.c.messaging.v1.services.create, friendly_name=name, inbound_request_url=inbound_url, use_inbound_webhook_on_number=True)
        await self.add_numbers_to_service(svc.sid, pn_sids)
        return svc.sid

    async def add_numbers_to_service(self, service_sid, pn_sids):
        for pn in pn_sids:
            try:
                await self._t(self.c.messaging.v1.services(service_sid).phone_numbers.create, phone_number_sid=pn)
            except Exception as e:  # already in this pool
                if "21712" not in str(e) and "already" not in str(e).lower():
                    raise

    async def create_campaign(self, service_sid, brand_sid, rec):
        c = rec["campaign"]
        camp = await self._t(self.c.messaging.v1.services(service_sid).us_app_to_person.create,
                             brand_registration_sid=brand_sid, description=c["description"], us_app_to_person_usecase=c["use_case"],
                             has_embedded_links=bool(c.get("has_embedded_links")), has_embedded_phone=bool(c.get("has_embedded_phone")),
                             message_samples=[s for s in c["samples"] if str(s).strip()], message_flow=c["message_flow"],
                             opt_in_message=c.get("opt_in_message"), opt_out_message=c.get("opt_out_message"), help_message=c.get("help_message"),
                             opt_in_keywords=c.get("opt_in_keywords"), opt_out_keywords=c.get("opt_out_keywords"), help_keywords=c.get("help_keywords"),
                             subscriber_opt_in=True, age_gated=False, direct_lending=False)
        return camp.sid

    async def campaign_status(self, service_sid, campaign_sid):
        camp = await self._t(self.c.messaging.v1.services(service_sid).us_app_to_person(campaign_sid).fetch)
        errs = getattr(camp, "errors", None) or []
        return camp.campaign_status, "; ".join(str(e.get("description") or e) for e in errs) if isinstance(errs, list) else str(errs or "")

    async def create_cnam(self, rec, profile_sid, pn_sids, email, callback):
        th = self.c.trusthub.v1
        name = rec["cnam"]["display_name"]
        tp = await self._t(th.trust_products.create, friendly_name=f"{rec['business']['legal_name']} CNAM", policy_sid=CNAM_POLICY, email=email, status_callback=callback)
        info = await self._t(th.end_users.create, type="cnam_information", friendly_name=f"{name} CNAM", attributes={"cnam_display_name": name})
        for sid in (info.sid, profile_sid):
            await self._t(th.trust_products(tp.sid).trust_products_entity_assignments.create, object_sid=sid)
        await self.assign_numbers_to_cnam(tp.sid, pn_sids)
        ev = await self._t(th.trust_products(tp.sid).trust_products_evaluations.create, policy_sid=CNAM_POLICY)
        if getattr(ev, "status", "") == "noncompliant":
            raise ValueError("Twilio evaluation: " + _eval_errors(ev))
        await self._t(th.trust_products(tp.sid).update, status="pending-review")
        return {"cnam_product": tp.sid, "cnam_info": info.sid}

    async def cnam_status(self, product_sid):
        p = await self._t(self.c.trusthub.v1.trust_products(product_sid).fetch)
        return p.status, ""

    async def assign_numbers_to_cnam(self, product_sid, pn_sids):
        for pn in pn_sids:
            await self._t(self.c.trusthub.v1.trust_products(product_sid).trust_products_channel_endpoint_assignment.create, channel_endpoint_sid=pn, channel_endpoint_type="phone-number")


def _eval_errors(ev) -> str:
    try:
        out = []
        for r in ev.results or []:
            for f in (r.get("fields") or []):
                if not f.get("passed"):
                    out.append(f"{f.get('object_field') or f.get('friendly_name')}: {f.get('failure_reason') or 'failed'}")
        return "; ".join(out) or "profile is non-compliant"
    except Exception:
        return "profile is non-compliant"


_override: Optional[object] = None


def use_adapter(adapter):
    """Tests inject a fake adapter here (None restores the mode-based choice)."""
    global _override
    _override = adapter


def adapter_for(mode: str):
    if _override is not None:
        return _override
    if mode == "dry_run" or not (os.environ.get("TWILIO_ACCOUNT_SID") and os.environ.get("TWILIO_AUTH_TOKEN")):
        return DryRunTwilio()
    return LiveTwilio()


# ── numbers ───────────────────────────────────────────────────────────────────
async def store_numbers(db, store_id: str) -> list[dict]:
    """Every Twilio number that texts on this store's behalf: the reps' numbers (users.twilio_number_sid)."""
    out, seen = [], set()
    async for u in db.users.find({"store_id": store_id, "twilio_number_sid": {"$exists": True, "$nin": [None, ""]}}, {"twilio_number_sid": 1, "twilio_number": 1, "name": 1}):
        sid = u.get("twilio_number_sid")
        if sid and sid not in seen:
            seen.add(sid)
            out.append({"sid": sid, "number": u.get("twilio_number"), "owner": u.get("name")})
    return out


# ── the state machine ─────────────────────────────────────────────────────────
def _hist(rec: dict, stage: str, status: str, note: str = "") -> list:
    h = list(rec.get("history") or [])
    h.append({"at": _now(), "stage": stage, "status": status, "note": note[:500]})
    return h[-60:]


async def _save(db, store_id: str, rec: dict):
    rec["updated_at"] = _now()
    await db.stores.update_one({"_id": ObjectId(store_id)}, {"$set": {"compliance": rec}})


def _callback_url() -> str:
    from services.scripts import _app_url
    return f"{_app_url()}/api/webhooks/twilio/trusthub-status"


def _inbound_url() -> str:
    from services.scripts import _app_url
    return f"{_app_url()}/api/webhooks/twilio/sms"


async def start(db, store: dict, me: dict) -> dict:
    """Admin pressed Submit: validate, then create + submit the Secondary Customer Profile."""
    rec = store.get("compliance") or defaults(store)
    miss = missing_fields(rec)
    if miss:
        raise ValueError("Missing: " + ", ".join(miss))
    settings = await get_settings(db)
    rec.update({"mode": settings["mode"], "stage": "profile", "status": "submitting", "error": "", "submitted_by": str(me.get("_id")), "submitted_at": _now()})
    rec.setdefault("sids", {})
    rec.setdefault("statuses", {})
    rec["history"] = _hist(rec, "profile", "submitting")
    await _save(db, str(store["_id"]), rec)
    return await advance(db, store_id=str(store["_id"]))


async def resubmit(db, store: dict, me: dict) -> dict:
    """After a rejection: start over with the corrected data (Twilio does not allow editing a rejected bundle in place)."""
    rec = store.get("compliance") or {}
    rec["history"] = _hist(rec, rec.get("stage") or "draft", "resubmit", f"previous sids: {rec.get('sids')}")
    rec["previous_sids"] = rec.get("sids") or {}
    rec["sids"], rec["statuses"] = {}, {}
    await _save(db, str(store["_id"]), rec)
    store = await db.stores.find_one({"_id": store["_id"]})
    return await start(db, store, me)


async def advance(db, store_id: str) -> dict:
    """One idempotent step for one store. Safe to call repeatedly (poller, webhook, admin 'check now')."""
    store = await db.stores.find_one({"_id": ObjectId(store_id)})
    rec = (store or {}).get("compliance")
    if not store or not rec or rec.get("stage") in (None, "draft"):
        return rec or {}
    tw = adapter_for(rec.get("mode") or "dry_run")
    before = (rec.get("stage"), rec.get("status"))
    sids, statuses = rec.setdefault("sids", {}), rec.setdefault("statuses", {})
    numbers = await store_numbers(db, store_id)
    pn_sids = [n["sid"] for n in numbers]
    rec["numbers"] = numbers
    settings = await get_settings(db)
    email = settings["notify_email"] or (rec.get("rep") or {}).get("email") or ""
    try:
        stage = rec["stage"]
        if stage == "profile":
            if not sids.get("customer_profile"):
                sids.update(await tw.create_customer_profile(rec, email, _callback_url()))
                await tw.assign_numbers_to_profile(sids["customer_profile"], pn_sids)
                rec["numbers_on_profile"] = pn_sids
                statuses["customer_profile"] = await tw.submit_customer_profile(sids["customer_profile"])
                rec["status"] = "pending"
                rec["history"] = _hist(rec, "profile", "submitted")
            else:
                await _assign_new_numbers(tw, rec, pn_sids)
                st, why = await tw.customer_profile_status(sids["customer_profile"])
                statuses["customer_profile"] = st
                if st in APPROVED:
                    rec["stage"], rec["status"] = "a2p", "submitting"
                    rec["history"] = _hist(rec, "profile", "approved")
                elif st in REJECTED:
                    rec["status"], rec["error"] = "rejected", why or "Twilio rejected the business profile. Check the legal name, EIN and address match IRS records."
                    rec["history"] = _hist(rec, "profile", "rejected", rec["error"])
        elif stage == "a2p":
            if not sids.get("a2p_product"):
                sids.update(await tw.create_a2p_product(rec, sids["customer_profile"], email, _callback_url()))
                rec["status"] = "pending"
                rec["history"] = _hist(rec, "a2p", "submitted")
            else:
                st, why = await tw.a2p_status(sids["a2p_product"])
                statuses["a2p_product"] = st
                if st in APPROVED:
                    rec["stage"], rec["status"] = "brand", "submitting"
                    rec["history"] = _hist(rec, "a2p", "approved")
                elif st in REJECTED:
                    rec["status"], rec["error"] = "rejected", why or "Twilio rejected the A2P messaging profile."
                    rec["history"] = _hist(rec, "a2p", "rejected", rec["error"])
        elif stage == "brand":
            if not sids.get("brand"):
                sids["brand"] = await tw.create_brand(sids["customer_profile"], sids["a2p_product"], mock=(rec.get("mode") == "mock"))
                rec["status"] = "pending"
                rec["history"] = _hist(rec, "brand", "submitted")
            else:
                st, why = await tw.brand_status(sids["brand"])
                statuses["brand"] = st
                if st in APPROVED:
                    rec["stage"], rec["status"] = "campaign", "submitting"
                    rec["history"] = _hist(rec, "brand", "approved")
                elif st in REJECTED:
                    rec["status"], rec["error"] = "rejected", why or "Brand registration failed. The EIN, legal name and address must match IRS records exactly."
                    rec["history"] = _hist(rec, "brand", "rejected", rec["error"])
        elif stage == "campaign":
            if not sids.get("messaging_service"):
                sids["messaging_service"] = await tw.create_messaging_service(f"{rec['business']['legal_name']} A2P", _inbound_url(), pn_sids)
                rec["numbers_on_service"] = pn_sids
            if not sids.get("campaign"):
                sids["campaign"] = await tw.create_campaign(sids["messaging_service"], sids["brand"], rec)
                rec["status"] = "pending"
                rec["history"] = _hist(rec, "campaign", "submitted")
            else:
                await _assign_new_numbers(tw, rec, pn_sids)
                st, why = await tw.campaign_status(sids["messaging_service"], sids["campaign"])
                statuses["campaign"] = st
                if st in APPROVED:
                    rec["stage"], rec["status"] = "complete", "approved"
                    rec["approved_at"] = _now()
                    rec["history"] = _hist(rec, "campaign", "approved")
                elif st in REJECTED:
                    rec["status"], rec["error"] = "rejected", why or "Campaign rejected. Samples must name the dealership, match the description and end with STOP instructions; privacy and terms pages must be public."
                    rec["history"] = _hist(rec, "campaign", "rejected", rec["error"])
        elif stage == "complete":
            await _assign_new_numbers(tw, rec, pn_sids)
        # CNAM rides alongside once the business profile is approved (voice only, optional)
        cn = rec.get("cnam") or {}
        if cn.get("enabled") and cn.get("display_name") and statuses.get("customer_profile") in APPROVED and rec.get("status") != "rejected":
            if not sids.get("cnam_product"):
                if pn_sids:
                    sids.update(await tw.create_cnam(rec, sids["customer_profile"], pn_sids, email, _callback_url()))
                    rec["numbers_on_cnam"] = pn_sids
                    statuses["cnam"] = "pending-review"
                    rec["history"] = _hist(rec, "cnam", "submitted", cn["display_name"])
            elif statuses.get("cnam") not in APPROVED | REJECTED:
                st, _why = await tw.cnam_status(sids["cnam_product"])
                statuses["cnam"] = st
                if st in APPROVED | REJECTED:
                    rec["history"] = _hist(rec, "cnam", "approved" if st in APPROVED else "rejected")
    except Exception as e:
        rec["status"], rec["error"] = "error", str(e)[:600]
        rec["history"] = _hist(rec, rec.get("stage") or "?", "error", str(e))
        logger.warning(f"[Compliance] store {store_id} {rec.get('stage')}: {e}")
    rec["last_checked_at"] = _now()
    await _save(db, store_id, rec)
    after = (rec.get("stage"), rec.get("status"))
    if after != before and after[1] != "submitting":
        try:
            from services.compliance_onboarding import on_twilio_change
            await on_twilio_change(db, store_id, before, after, rec)
        except Exception as e:
            logger.warning(f"[Compliance] status notify failed: {e}")
    return rec


async def _assign_new_numbers(tw, rec: dict, pn_sids: list[str]):
    """Reps get numbers after the profile went in: attach the new ones everywhere they belong."""
    sids = rec.get("sids") or {}
    new_p = [p for p in pn_sids if p not in (rec.get("numbers_on_profile") or [])]
    if new_p and sids.get("customer_profile"):
        await tw.assign_numbers_to_profile(sids["customer_profile"], new_p)
        rec["numbers_on_profile"] = (rec.get("numbers_on_profile") or []) + new_p
    new_s = [p for p in pn_sids if p not in (rec.get("numbers_on_service") or [])]
    if new_s and sids.get("messaging_service"):
        await tw.add_numbers_to_service(sids["messaging_service"], new_s)
        rec["numbers_on_service"] = (rec.get("numbers_on_service") or []) + new_s
    new_c = [p for p in pn_sids if p not in (rec.get("numbers_on_cnam") or [])]
    if new_c and sids.get("cnam_product"):
        await tw.assign_numbers_to_cnam(sids["cnam_product"], new_c)
        rec["numbers_on_cnam"] = (rec.get("numbers_on_cnam") or []) + new_c


async def poll_all(db) -> int:
    """Scheduler entry: nudge every store that is mid-flight (approved ones too, so reps' new numbers get attached)."""
    n = 0
    async for s in db.stores.find({"compliance.stage": {"$in": ["profile", "a2p", "brand", "campaign", "complete"]}, "compliance.status": {"$nin": ["rejected", "error"]}}, {"_id": 1}):
        try:
            await advance(db, str(s["_id"]))
            n += 1
        except Exception as e:
            logger.warning(f"[Compliance] poll {s['_id']}: {e}")
    return n


async def on_status_callback(db, form: dict) -> Optional[str]:
    """Twilio Trust Hub status callback: find the store by bundle SID and advance it."""
    sid = form.get("BundleSid") or form.get("bundle_sid") or form.get("Sid") or ""
    if not sid:
        return None
    store = await db.stores.find_one({"$or": [{"compliance.sids.customer_profile": sid}, {"compliance.sids.a2p_product": sid}, {"compliance.sids.cnam_product": sid}]}, {"_id": 1})
    if not store:
        return None
    await db.stores.update_one({"_id": store["_id"]}, {"$push": {"compliance.callbacks": {"$each": [{"at": _now(), "sid": sid, "status": form.get("Status"), "raw": {k: str(v)[:200] for k, v in form.items()}}], "$slice": -20}}})
    await advance(db, str(store["_id"]))
    return str(store["_id"])


def summary(store: dict) -> dict:
    """Compact view for lists and the store page."""
    from services.compliance_onboarding import onboarding_status, ONBOARDING_STATUS_LABEL, next_action
    c = store.get("compliance") or {}
    stage = c.get("stage") or "draft"
    ob = onboarding_status(c)
    pf = c.get("preflight") or {}
    return {"store_id": str(store["_id"]), "store_name": store.get("name"), "stage": stage, "stage_label": STAGE_LABEL.get(stage, stage), "status": c.get("status") or ("not_started" if stage == "draft" else "pending"),
            "error": c.get("error") or "", "mode": c.get("mode"), "cnam": (c.get("statuses") or {}).get("cnam"), "cnam_name": (c.get("cnam") or {}).get("display_name"),
            "numbers": len(c.get("numbers") or []), "updated_at": c.get("updated_at"), "approved_at": c.get("approved_at"), "last_checked_at": c.get("last_checked_at"),
            "onboarding": ob, "onboarding_label": ONBOARDING_STATUS_LABEL[ob], "reminders_sent": (c.get("onboarding") or {}).get("reminders_sent", 0),
            "missing": len(missing_fields(c)) if stage == "draft" else 0, "preflight": {"score": pf.get("score"), "verdict": pf.get("verdict"), "blockers": pf.get("blockers")} if pf.get("at") else None,
            "review": (c.get("review") or {}).get("status"), "next_action": next_action(store)}


def public(rec: dict) -> dict:
    """The record as the admin sees it: the EIN never leaves the server, only its last four; public-form tokens stay server-side."""
    out = dict(rec or {})
    b = dict(out.get("business") or {})
    ein = re.sub(r"\D", "", str(b.get("ein") or ""))
    b["ein"] = ""
    b["ein_masked"] = f"**-***{ein[-4:]}" if ein else ""
    b["has_ein"] = bool(ein)
    out["business"] = b
    for k in ("onboarding", "portout"):
        if isinstance(out.get(k), dict):
            out[k] = {kk: vv for kk, vv in out[k].items() if kk != "token"}
    return out


def merge_patch(existing: dict, patch: dict, store: dict) -> dict:
    """Admin edits: business / rep / campaign / cnam blocks; a blank EIN keeps the one on file."""
    rec = existing or defaults(store)
    for block in ("business", "rep", "campaign", "cnam"):
        if isinstance(patch.get(block), dict):
            cur = dict(rec.get(block) or {})
            for k, v in patch[block].items():
                if k in ("ein_masked", "has_ein"):
                    continue
                if k == "ein" and not str(v or "").strip():
                    continue
                cur[k] = v
            rec[block] = cur
    if "display_name" in (patch.get("cnam") or {}):
        rec["cnam"]["display_name"] = cnam_name(rec["cnam"].get("display_name") or "")
    rec.setdefault("stage", "draft")
    rec.setdefault("status", "not_started")
    return rec
