"""
Lead Intake Router
Handles inbound internet leads from any source:
  - ADF/XML  (Cars.com, AutoTrader, OEM, most major portals)
  - JSON/Form webhook  (dealer websites, Zapier, n8n, CRM POST)
  - Email body parse   (sources that only send email — GPT extracts fields)

Every lead gets normalized to a standard schema, deduplicated, timed for
after-hours scheduling, an AI-drafted first message generated, and placed
in the Unassigned inbox queue.
"""
import asyncio
import logging
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from routers.database import get_db

router = APIRouter(prefix="/leads", tags=["Lead Intake"])
logger = logging.getLogger(__name__)

_APP_URL = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))

# ── Smart field normalizer ─────────────────────────────────────────────────────

# Map of normalized (snake_case) keys → standard schema fields
# Covers 60+ real-world variations from Cars.com, AutoTrader, OEM, dealer sites
_FIELD_ALIASES: dict[str, list[str]] = {
    "first_name": [
        "first_name", "firstname", "fname", "first", "customer_first_name",
        "buyer_first_name", "contact_first", "lead_first_name", "f_name",
        "given_name", "givenname",
    ],
    "last_name": [
        "last_name", "lastname", "lname", "last", "customer_last_name",
        "buyer_last_name", "contact_last", "lead_last_name", "l_name",
        "family_name", "surname",
    ],
    "full_name": [
        "name", "full_name", "fullname", "customer_name", "contact_name",
        "buyer_name", "lead_name", "your_name",
    ],
    "email": [
        "email", "email_address", "emailaddress", "customer_email",
        "buyer_email", "contact_email", "lead_email", "e_mail",
    ],
    "phone": [
        "phone", "phone_number", "phonenumber", "telephone", "tel",
        "cell", "cell_phone", "cellphone", "mobile", "mobile_phone",
        "mobilephone", "contact_phone", "buyer_phone", "customer_phone",
        "primary_phone", "phone1",
    ],
    "comments": [
        "comments", "comment", "notes", "note", "message", "inquiry",
        "description", "customer_comments", "additional_info",
        "customer_message", "lead_comments", "body", "text",
    ],
    "vehicle_year": [
        "vehicle_year", "year", "car_year", "auto_year", "model_year",
        "vehicleyear", "veh_year",
    ],
    "vehicle_make": [
        "vehicle_make", "make", "car_make", "auto_make", "brand",
        "vehiclemake", "veh_make", "manufacturer",
    ],
    "vehicle_model": [
        "vehicle_model", "model", "car_model", "auto_model",
        "vehiclemodel", "veh_model",
    ],
    "vehicle_trim": [
        "vehicle_trim", "trim", "trim_level", "trimlevel", "package",
        "veh_trim",
    ],
    "vehicle_vin": [
        "vin", "vehicle_vin", "vin_number", "stock_vin",
    ],
    "vehicle_stock": [
        "vehicle_stock", "stock", "stock_number", "stocknumber", "stock_no",
    ],
    "vehicle_type": [
        "vehicle_type", "type", "sale_type", "interest", "condition",
        "new_used", "new_or_used",
    ],
    "source_name": [
        "source", "source_name", "lead_source", "leadsource", "provider",
        "vendor", "origin", "referrer", "utm_source",
    ],
    "zip_code": [
        "zip", "zipcode", "zip_code", "postal_code", "postalcode",
    ],
    "city": ["city", "customer_city"],
    "state": ["state", "province", "customer_state"],
    "street": ["street", "street_address", "address", "address1", "customer_street"],
    "external_lead_id": ["external_lead_id", "lead_id", "leadid", "prospect_id"],
    "trade_year": ["trade_year", "tradein_year", "trade_in_year"],
    "trade_make": ["trade_make", "tradein_make", "trade_in_make"],
    "trade_model": ["trade_model", "tradein_model", "trade_in_model"],
    "trade_mileage": ["trade_mileage", "tradein_miles", "trade_miles"],
}

# Build reverse lookup: normalized_alias → standard_key
_ALIAS_LOOKUP: dict[str, str] = {}
for std_key, aliases in _FIELD_ALIASES.items():
    for alias in aliases:
        _ALIAS_LOOKUP[alias.lower().replace("-", "_").replace(" ", "_")] = std_key


def _snake(key: str) -> str:
    """CamelCase / PascalCase → snake_case, strip special chars."""
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", str(key))
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return s.lower().replace("-", "_").replace(" ", "_")


def normalize_fields(raw: dict) -> dict:
    """
    Accept any dict of raw fields and return our standard lead schema.
    Unknown fields go into `extra_fields` for admin review.
    """
    std: dict = {}
    extra: dict = {}

    for raw_key, value in raw.items():
        if value is None or value == "":
            continue
        nk = _snake(raw_key)
        mapped = _ALIAS_LOOKUP.get(nk)
        if mapped:
            # Only take first match (some sources duplicate fields)
            if mapped not in std:
                std[mapped] = str(value).strip()
        else:
            extra[raw_key] = value

    # Build full_name if split names present
    if "full_name" not in std and ("first_name" in std or "last_name" in std):
        std["full_name"] = f"{std.get('first_name', '')} {std.get('last_name', '')}".strip()

    # Split full_name if only full name provided
    if "full_name" in std and "first_name" not in std:
        parts = std["full_name"].split(" ", 1)
        std["first_name"] = parts[0]
        std["last_name"] = parts[1] if len(parts) > 1 else ""

    std["extra_fields"] = extra
    return std


# ── ADF / XML parser ───────────────────────────────────────────────────────────

def parse_adf_xml(body: str) -> dict:
    """
    Parse ADF (Automotive Data Format) XML lead.
    Returns dict of normalized lead fields.
    Handles ADF 1.0 spec used by Cars.com, AutoTrader, most OEMs.
    """
    try:
        root = ET.fromstring(body.strip())
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML: {e}")

    # ADF root can be <adf> or <adfleads> or bare <prospect>
    prospect = root if root.tag in ("prospect", "Prospect") else root.find(
        "prospect") or root.find("Prospect")
    if prospect is None:
        raise ValueError("No <prospect> element found in ADF XML")

    def txt(el, *tags) -> str:
        for tag in tags:
            node = el.find(tag)
            if node is not None and node.text:
                return node.text.strip()
        return ""

    def attr(el, *tags, attrib="type") -> str:
        for tag in tags:
            node = el.find(tag)
            if node is not None:
                return node.get(attrib, "")
        return ""

    raw: dict = {}

    # ── Request date
    raw["adf_requestdate"] = txt(prospect, "requestdate", "RequestDate")

    # ── Portal's lead ID (<id sequence source> on prospect)
    id_el = prospect.find("id")
    if id_el is None:
        id_el = prospect.find("Id")
    if id_el is not None and id_el.text:
        raw["external_lead_id"] = id_el.text.strip()

    # ── Vehicle
    veh = prospect.find("vehicle") or prospect.find("Vehicle")
    if veh is not None:
        raw["vehicle_year"]  = txt(veh, "year", "Year")
        raw["vehicle_make"]  = txt(veh, "make", "Make")
        raw["vehicle_model"] = txt(veh, "model", "Model")
        raw["vehicle_trim"]  = txt(veh, "trim", "Trim")
        raw["vehicle_vin"]   = txt(veh, "vin", "VIN", "Vin")
        raw["vehicle_stock"] = txt(veh, "stock", "Stock", "StockNumber")
        raw["vehicle_type"]  = veh.get("status") or veh.get("interest") or ""
        raw["vehicle_price"] = txt(veh, "price", "Price")

    # ── Customer / Contact
    customer = prospect.find("customer") or prospect.find("Customer")
    if customer is not None:
        contact = customer.find("contact") or customer.find("Contact")
        if contact is not None:
            # Name — ADF can use <name part="first"> or <name part="full">
            for name_el in contact.findall("name") + contact.findall("Name"):
                part = name_el.get("part", "full").lower()
                val  = (name_el.text or "").strip()
                if val:
                    if part == "first":
                        raw["first_name"] = val
                    elif part == "last":
                        raw["last_name"] = val
                    else:
                        raw["full_name"] = val

            # Email
            for el in contact.findall("email") + contact.findall("Email"):
                if el.text:
                    raw["email"] = el.text.strip()
                    break

            # Phone — prefer "voice" or "cell" type
            phones = contact.findall("phone") + contact.findall("Phone")
            for ph in phones:
                t = ph.get("type", "voice").lower()
                if t in ("voice", "cell", "mobile", "home") and ph.text:
                    raw["phone"] = ph.text.strip()
                    break
            if "phone" not in raw and phones and phones[0].text:
                raw["phone"] = phones[0].text.strip()

            # Address
            addr = contact.find("address") or contact.find("Address")
            if addr is not None:
                raw["street"]   = txt(addr, "street", "Street", "address1", "line1")
                raw["city"]     = txt(addr, "city", "City")
                raw["state"]    = txt(addr, "regioncode", "state", "State")
                raw["zip_code"] = txt(addr, "postalcode", "zip", "Zip")

        raw["comments"] = txt(customer, "comments", "Comments")

    # ── Trade-in
    trade = prospect.find("trade") or prospect.find("Trade") or prospect.find("tradein")
    if trade is not None:
        raw["trade_year"]    = txt(trade, "year", "Year")
        raw["trade_make"]    = txt(trade, "make", "Make")
        raw["trade_model"]   = txt(trade, "model", "Model")
        raw["trade_mileage"] = txt(trade, "odometer", "Odometer", "mileage")

    # ── Vendor / Source
    vendor = prospect.find("vendor") or prospect.find("Vendor")
    if vendor is not None:
        raw["source_name"] = txt(vendor, "vendorname", "VendorName", "name")

    # ── Provider (some ADF variants)
    provider = prospect.find("provider") or prospect.find("Provider")
    if provider is not None and "source_name" not in raw:
        raw["source_name"] = txt(provider, "name", "Name", "service")

    return normalize_fields(raw)


# ── After-hours timing ─────────────────────────────────────────────────────────

_DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday",
              "friday", "saturday", "sunday"]

LEAD_SEND_DELAY_SECONDS = 90   # fire 90 s after receipt if within hours
# Generic instant confirmation for opted-in form leads when the source has no intake text yet.
DEFAULT_FORM_CONFIRMATION = "Hi {{first_name}}, we got it! Someone from {{store_name}} will reach out shortly. Reply STOP to opt out."

LEAD_MORNING_BUFFER_MINUTES = 5  # fire X min after opening to avoid exact-on-open blasts


def calculate_send_time(store: dict) -> datetime:
    """
    Given a store document (with business_hours + timezone), return the UTC
    datetime when the automated first text should fire.

    - During hours  → now + 90 s
    - After hours   → next opening time + 5 min buffer
    - No hours set  → now + 90 s (safe default)
    """
    hours = store.get("business_hours") or {}
    tz_str = store.get("timezone") or "America/Chicago"

    try:
        tz = ZoneInfo(tz_str)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("America/Chicago")

    now_local = datetime.now(tz)
    now_utc   = datetime.now(timezone.utc)

    if not hours:
        return now_utc + timedelta(seconds=LEAD_SEND_DELAY_SECONDS)

    today_name = _DAY_NAMES[now_local.weekday()]
    today_hours = hours.get(today_name)

    if today_hours:
        open_h, open_m   = map(int, today_hours["open"].split(":"))
        close_h, close_m = map(int, today_hours["close"].split(":"))
        open_dt  = now_local.replace(hour=open_h,  minute=open_m,  second=0, microsecond=0)
        close_dt = now_local.replace(hour=close_h, minute=close_m, second=0, microsecond=0)

        if open_dt <= now_local < close_dt:
            # Within hours — send shortly
            return now_utc + timedelta(seconds=LEAD_SEND_DELAY_SECONDS)

    # After hours (or closed today) — find next opening
    for offset in range(1, 8):
        candidate = now_local + timedelta(days=offset)
        day_name  = _DAY_NAMES[candidate.weekday()]
        day_hours = hours.get(day_name)
        if day_hours:
            open_h, open_m = map(int, day_hours["open"].split(":"))
            send_local = candidate.replace(
                hour=open_h, minute=open_m + LEAD_MORNING_BUFFER_MINUTES,
                second=0, microsecond=0
            )
            return send_local.astimezone(timezone.utc)

    # Fallback: 2 hours from now
    return now_utc + timedelta(hours=2)


# ── AI first message generator ────────────────────────────────────────────────

async def _match_lead_inventory(db, normalized: dict, store_id: str) -> Optional[dict]:
    """Match the lead's vehicle of interest against live inventory.
    Returns a compact summary (id, name, price, stock#, photo) or None."""
    make  = (normalized.get("vehicle_make") or "").strip()
    model = (normalized.get("vehicle_model") or "").strip()
    if not make and not model:
        return None
    try:
        base = {"status": "available", "is_visible": {"$ne": False}}
        if store_id:
            base["store_id"] = str(store_id)
        clauses = []
        if make:
            clauses.append({"$or": [
                {"attributes.make": {"$regex": re.escape(make), "$options": "i"}},
                {"name": {"$regex": re.escape(make), "$options": "i"}},
            ]})
        if model:
            clauses.append({"$or": [
                {"attributes.model": {"$regex": re.escape(model), "$options": "i"}},
                {"name": {"$regex": re.escape(model), "$options": "i"}},
            ]})
        items = await db.inventory.find({**base, "$and": clauses}).limit(5).to_list(5)
        if not items and len(clauses) == 2:
            # Loosen: model-only match (portals often mangle the make)
            items = await db.inventory.find({**base, "$and": clauses[1:]}).limit(5).to_list(5)
        if not items:
            return None
        year = (normalized.get("vehicle_year") or "").strip()
        trim = (normalized.get("vehicle_trim") or "").strip().lower()

        def rank(it):
            a = it.get("attributes") or {}
            score = 0
            if year and str(a.get("year", "")) == year:
                score += 2
            if trim and trim in str(a.get("trim", "")).lower():
                score += 1
            return score

        items.sort(key=rank, reverse=True)
        it = items[0]
        a = it.get("attributes") or {}
        return {
            "inventory_id": str(it["_id"]),
            "name": it.get("name", ""),
            "price": it.get("price"),
            "stock_number": a.get("stock_number", ""),
            "color": a.get("color", ""),
            "mileage": a.get("mileage", ""),
            "photo_url": it.get("photo_url", ""),
            "photo_full_path": it.get("photo_full_path", ""),
        }
    except Exception as e:
        logger.warning(f"[LeadIntake] Inventory match failed: {e}")
        return None


async def generate_first_message(lead: dict, assigned_user: Optional[dict],
                                  store: dict, matched_vehicle: Optional[dict] = None) -> str:
    """
    Generate an AI-drafted first message in the assigned rep's voice.
    Falls back to a store-branded template if no persona is set.
    """
    first  = lead.get("first_name", "there")
    veh    = " ".join(filter(None, [
        lead.get("vehicle_year"), lead.get("vehicle_make"),
        lead.get("vehicle_model")
    ])) or "the vehicle"
    source = lead.get("source_name", "your inquiry")
    store_name = store.get("name", "our dealership")

    stock_line = ""
    if matched_vehicle:
        bits = [matched_vehicle.get("name", "")]
        if matched_vehicle.get("color"):
            bits.append(str(matched_vehicle["color"]))
        if matched_vehicle.get("price"):
            bits.append(f"${matched_vehicle['price']:,.0f}")
        if matched_vehicle.get("stock_number"):
            bits.append(f"Stock #{matched_vehicle['stock_number']}")
        stock_line = " — ".join(str(b) for b in bits if b)

    # Try personal AI clone if user has a persona
    if assigned_user:
        try:
            from routers.auth import _build_ai_clone_prompt
            from emergentintegrations.llm.chat import LlmChat, UserMessage

            persona    = assigned_user.get("persona") or {}
            user_name  = assigned_user.get("name", "your rep")
            system_prompt = _build_ai_clone_prompt(user_name, user_name.split()[0], persona, assigned_user)
            system_prompt += (
                "\n\nYou are drafting the FIRST outbound text message to a new internet lead. "
                "Keep it under 2 sentences. Warm, personal, NOT generic. "
                "Mention their vehicle interest if given. Never use em dashes. "
                "End with a simple question that invites a reply."
            )

            user_msg = (
                f"New lead: {first} inquired about {veh} via {source}. "
                + (f"GOOD NEWS — we have it in stock right now: {stock_line}. Confirm availability naturally (no need to list every detail). " if stock_line else "")
                + f"Write a first outreach text from {user_name.split()[0]}."
            )

            emergent_key = os.environ.get("EMERGENT_LLM_KEY", "")
            chat = LlmChat(
                api_key=emergent_key,
                session_id=f"lead-first-msg-{lead.get('phone','')}",
                system_message=system_prompt,
            ).with_model("openai", "gpt-5.2")

            response = await chat.send_message(UserMessage(text=user_msg))
            msg = response.strip() if isinstance(response, str) else (
                response.text.strip() if hasattr(response, "text") else str(response))
            if msg:
                return msg
        except Exception as e:
            logger.warning(f"[LeadIntake] AI message generation failed: {e}")

    # Fallback template
    rep_first = (assigned_user.get("name", "").split()[0] if assigned_user else "")
    intro = f"I'm {rep_first} at {store_name}. " if rep_first else f"This is {store_name}. "
    vehicle_str = f"the {veh}" if veh != "the vehicle" else "what you were looking at"
    if stock_line:
        return (
            f"Hey {first}! {intro}Good news, we've still got {vehicle_str} on the lot "
            f"({stock_line}). Want me to hold it for a quick look?"
        )
    return (
        f"Hey {first}! {intro}Saw your inquiry about {vehicle_str} — "
        f"are you still in the market or just browsing? Happy to help either way."
    )


# ── Core lead processor ────────────────────────────────────────────────────────

async def process_inbound_lead(normalized: dict, source: dict, db,
                                raw_body: str = "") -> dict:
    """
    Central processing pipeline. Called by every intake endpoint.
    Returns the created inbound_lead document _id.
    """
    now = datetime.now(timezone.utc)

    phone = normalized.get("phone", "")
    email = normalized.get("email", "")
    first = normalized.get("first_name", "Unknown")
    last  = normalized.get("last_name", "")
    full_name = normalized.get("full_name") or f"{first} {last}".strip()

    # Normalise phone
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        digits = "1" + digits
    phone_e164 = f"+{digits}" if digits else ""

    if not phone_e164 and not email:
        raise HTTPException(status_code=422, detail="Lead has no phone or email — cannot process")

    # ── Get store for timing + assignment
    store_id = source.get("store_id") or source.get("organization_id") or ""
    store = {}
    if store_id:
        try:
            store = await db.stores.find_one({"_id": ObjectId(store_id)}) or {}
        except Exception:
            pass

    # ── Dedup: check existing contact
    contact_query: dict = {"$or": []}
    if phone_e164:
        contact_query["$or"].append({"phone": {"$regex": re.escape(digits[-10:])}})
    if email:
        contact_query["$or"].append({"email": email.lower().strip()})

    existing_contact = None
    if contact_query["$or"]:
        existing_contact = await db.contacts.find_one(contact_query)

    # Returning customer: an existing contact owned by an ACTIVE rep in this store goes straight to
    # that rep (skips the shared queue + ladder). Store-owned / orphaned contacts are treated as new.
    owner_id = None
    if existing_contact:
        cand = str(existing_contact.get("user_id") or "")
        if cand and cand != store_id and ObjectId.is_valid(cand):
            owner = await db.users.find_one(
                {"_id": ObjectId(cand), "active": {"$ne": False}, "status": {"$ne": "deactivated"}}, {"store_id": 1})
            if owner and (not store_id or str(owner.get("store_id") or "") == store_id):
                owner_id = cand

    if existing_contact:
        contact_id = str(existing_contact["_id"])
        is_new_contact = False
    else:
        vehicle_interest = " ".join(filter(None, [
            normalized.get("vehicle_year"), normalized.get("vehicle_make"),
            normalized.get("vehicle_model"), normalized.get("vehicle_trim"),
        ]))
        notes_parts = [normalized.get("comments", "")]
        if normalized.get("vehicle_vin"):
            notes_parts.append(f"VIN: {normalized['vehicle_vin']}")
        if normalized.get("vehicle_stock"):
            notes_parts.append(f"Stock #: {normalized['vehicle_stock']}")
        trade_desc = " ".join(filter(None, [
            normalized.get("trade_year"), normalized.get("trade_make"), normalized.get("trade_model"),
        ]))
        if trade_desc:
            miles = f", {normalized['trade_mileage']} mi" if normalized.get("trade_mileage") else ""
            notes_parts.append(f"Trade-in: {trade_desc}{miles}")
        # Create contact
        contact_doc = {
            "first_name":    first,
            "last_name":     last,
            "phone":         phone_e164,
            "email":         email.lower().strip() if email else "",
            "address_street": normalized.get("street", ""),
            "address_city":  normalized.get("city", ""),
            "address_state": normalized.get("state", ""),
            "address_zip":   normalized.get("zip_code", ""),
            "source":        "internet_lead",
            "ownership_type": "org",
            "status":        "active",
            "tags":          ["Internet Lead", normalized.get("source_name", source.get("name", "Lead"))],
            "notes":         "\n".join(filter(None, notes_parts)),
            "vehicle":          vehicle_interest or None,
            "vehicle_interest": vehicle_interest,
            "external_id":      normalized.get("external_lead_id") or None,
            "lead_source_id":   str(source.get("_id", "")),
            "lead_source_name": source.get("name", ""),
            "store_id":         store_id,
            "created_at":       now,
            "updated_at":       now,
        }
        # Assign user_id if source has a default user (round robin / weighted)
        assigned_user_id = await _resolve_assignment(db, source)
        if assigned_user_id:
            contact_doc["user_id"]      = assigned_user_id
            contact_doc["original_user_id"] = assigned_user_id
        else:
            # No assignment yet — belongs to the store/org
            contact_doc["user_id"] = store_id or ""

        result = await db.contacts.insert_one(contact_doc)
        contact_id = str(result.inserted_id)
        is_new_contact = True

    # ── Resolve assigned user (for AI message)
    assigned_user_id = owner_id or await _resolve_assignment(db, source)
    routing_kind = "returning_owner" if owner_id else ("assigned" if assigned_user_id else "queue")
    assigned_user = None
    if assigned_user_id:
        try:
            assigned_user = await db.users.find_one({"_id": ObjectId(assigned_user_id)})
        except Exception:
            pass

    # ── Determine send time (after-hours logic)
    # Business-initiated contact (intake text, AI first message, rep call ladder) respects the
    # customer's texting window and the store's hours; overnight leads are released staggered.
    from services.lead_timing import build_contact_plan, parse_iso
    plan = await build_contact_plan(db, source, store, phone_e164, now)
    scheduled_send_at = parse_iso(plan["intake_at"]) or (now + timedelta(seconds=LEAD_SEND_DELAY_SECONDS))
    if not plan["intake_deferred"]:
        scheduled_send_at = now + timedelta(seconds=LEAD_SEND_DELAY_SECONDS)
    is_immediate = not plan["intake_deferred"]
    is_test = bool(normalized.get("is_test"))
    sms_opt_in = bool(normalized.get("sms_opt_in"))

    # Form leads that opted in always get an instant, generic "we got it" text even when the
    # store never wrote an intake text (the rep isn't known yet, so no rep name).
    if sms_opt_in and not (source.get("intake_text") or "").strip():
        source = {**source, "intake_text": DEFAULT_FORM_CONFIRMATION.replace(
            "{{store_name}}", (store.get("name") or "").strip() or "our team")}

    if sms_opt_in:
        await db.contacts.update_one(
            {"_id": ObjectId(contact_id)},
            {"$set": {"sms_consent": True, "sms_consent_at": now, "sms_consent_source": (normalized.get("attribution") or {}).get("kind") or "lead_form"}},
        )
    if is_test:
        await db.contacts.update_one({"_id": ObjectId(contact_id)}, {"$addToSet": {"tags": "Test Lead"}, "$set": {"is_test": True}})

    # ── Match vehicle of interest against live inventory
    matched_vehicle = await _match_lead_inventory(db, normalized, store_id)

    # Photo of the matched vehicle rides along with the first text (MMS)
    lead_media = []
    if matched_vehicle:
        _pub = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com")).rstrip("/")
        if matched_vehicle.get("photo_full_path"):
            lead_media = [f"{_pub}/api/images/{matched_vehicle['photo_full_path']}"]
        elif matched_vehicle.get("photo_url"):
            _pu = matched_vehicle["photo_url"]
            lead_media = [_pu if _pu.startswith("http") else f"{_pub}{_pu}"]

    # ── Generate AI first message
    first_message = await generate_first_message(normalized, assigned_user, store, matched_vehicle)

    # ── Save inbound_lead record
    lead_doc = {
        "source_id":         str(source.get("_id", "")),
        "source_name":       source.get("name", ""),
        "store_id":          store_id,
        "contact_id":        contact_id,
        "is_new_contact":    is_new_contact,
        "phone":             phone_e164,
        "email":             email,
        "full_name":         full_name,
        "vehicle_interest":  " ".join(filter(None, [
            normalized.get("vehicle_year"), normalized.get("vehicle_make"),
            normalized.get("vehicle_model"),
        ])),
        "comments":          normalized.get("comments", ""),
        "vehicle_raw":       {k: v for k, v in normalized.items() if k.startswith("vehicle_") or k.startswith("trade_")},
        "matched_inventory": matched_vehicle,
        "media_urls":        lead_media,
        "extra_fields":      normalized.get("extra_fields", {}),
        "attribution":       normalized.get("attribution") or None,
        "assigned_to":       assigned_user_id,
        "routing_kind":      routing_kind,
        "draft_message":     first_message,
        "scheduled_send_at": scheduled_send_at,
        "is_after_hours":    not is_immediate,
        "is_test":           is_test,
        # The workflow intake text is the first touch when configured; the legacy AI first
        # message only runs for sources without one (never two texts in 90 seconds).
        "status":            "skipped" if (source.get("intake_text") or "").strip() else "queued",   # queued → sent | failed
        "skip_reason":       "intake_text_workflow" if (source.get("intake_text") or "").strip() else None,
        "raw_body":          raw_body[:4000] if raw_body else "",
        "received_at":       now,
        "created_at":        now,
    }
    lead_result = await db.inbound_leads.insert_one(lead_doc)
    lead_id = str(lead_result.inserted_id)

    # ── Create conversation in inbox (Unassigned queue)
    conversation = {
        "contact_id":       contact_id,
        "contact_phone":    phone_e164,
        "contact_name":     full_name,
        "lead_source_id":   str(source.get("_id", "")),
        "lead_source_name": source.get("name", ""),
        "inbound_lead_id":  lead_id,
        "team_id":          source.get("team_id"),
        "assigned_to":      assigned_user_id,
        "store_id":         store_id,
        "user_id":          assigned_user_id or store_id or "",
        "status":           "active",
        "claimed":          assigned_user_id is not None,
        "claimed_by":       assigned_user_id,
        "claimed_at":       now.isoformat() if assigned_user_id else None,
        "claim_source":     routing_kind if assigned_user_id else None,
        "routing_kind":     routing_kind,
        # Returning-customer safety net: manager alert, then auto-release to the shared queue
        "owner_alert_at":   now + timedelta(minutes=int(source.get("returning_alert_minutes") or 10)) if owner_id else None,
        "release_at":       now + timedelta(minutes=int(source.get("returning_release_minutes") or 30)) if owner_id else None,
        "owner_alerted":    False,
        # Jessi answers the lead's replies (any hour, consumer-initiated) when the source's
        # AI toggle is on or the store is closed under the after-hours rule.
        "ai_mode":          "auto_reply" if plan["jessi_on"] else "assist",
        "ai_enabled":       True if plan["jessi_on"] else None,
        "draft_message":    first_message,
        "is_internet_lead": True,
        "is_test":          is_test,
        "after_hours_lead": bool(plan["after_hours"]),
        "routing_plan":     plan,
        "sms_consent":      {"opted_in": True, "at": now.isoformat(), "source": (normalized.get("attribution") or {}).get("kind") or "lead_form"} if sms_opt_in else None,
        "attribution":      normalized.get("attribution") or None,
        "created_at":       now,
        "updated_at":       now,
        "last_message_at":  now,
    }
    conv_result = await db.conversations.insert_one(conversation)
    conv_id = str(conv_result.inserted_id)

    # Update lead with conversation_id
    await db.inbound_leads.update_one(
        {"_id": ObjectId(lead_id)},
        {"$set": {"conversation_id": conv_id}}
    )

    # Increment source lead count
    if source.get("_id"):
        await db.lead_sources.update_one(
            {"_id": source["_id"]}, {"$inc": {"lead_count": 1}}
        )

    # ── Instant push to the assigned rep — a fresh internet lead just landed
    if assigned_user_id:
        try:
            from routers.push_notifications import send_push_to_user
            _veh_note = normalized.get("vehicle_interest") or "New inquiry"
            if matched_vehicle:
                _veh_note += f" — IN STOCK ({matched_vehicle.get('name', '')})"
            if owner_id:
                _title = f"Returning customer: {full_name}"
                _body = f"Your customer came back via {source.get('name', 'the website')} · {_veh_note}. Reply now, it's yours."
            else:
                _title = f"🔥 New Lead — {full_name}"
                _body = f"{_veh_note} via {source.get('name', 'internet lead')}"
            from routers.push_notifications import LEAD_SOUND, LEAD_CHANNEL
            asyncio.create_task(send_push_to_user(assigned_user_id, _title, _body, f"/thread/{conv_id}", "flash", sound=LEAD_SOUND, channel_id=LEAD_CHANNEL))
        except Exception as e:
            logger.warning(f"[LeadIntake] Rep push failed: {e}")

    # ── Fire Workflow Automation ───────────────────────────────────────────────
    # Sends instant intake text, blasts all workflow reps with push notifications
    asyncio.create_task(_fire_intake_workflow(
        source=source, lead_doc=lead_doc, conv_id=conv_id,
        contact_id=contact_id, phone_e164=phone_e164,
        normalized=normalized, db=db, now=now, plan=plan,
    ))

    logger.info(
        f"[LeadIntake] Lead received: {full_name} | {phone_e164} | "
        f"source={source.get('name')} | intake_at={plan['intake_at']} | "
        f"after_hours={plan['after_hours']} | ladder_deferred={plan['ladder_deferred']}"
    )

    return {
        "lead_id":        lead_id,
        "contact_id":     contact_id,
        "conversation_id": conv_id,
        "is_new_contact": is_new_contact,
        "draft_message":  first_message,
        "scheduled_send_at": scheduled_send_at.isoformat(),
        "is_after_hours":   bool(plan["after_hours"]),
        "assigned_to":      assigned_user_id,
        "plan":             plan,
    }


async def _resolve_assignment(db, source: dict) -> Optional[str]:
    """Resolve assignment from source's method. Returns user_id or None.
    Prefers on-shift reps for round-robin; falls back to all if none on shift."""
    method  = source.get("assignment_method", "jump_ball")
    team_id = source.get("team_id")
    if not team_id or method == "jump_ball":
        return None
    try:
        team = await db.teams.find_one({"_id": ObjectId(team_id)})
        if not team or not team.get("members"):
            return None
        all_members = team["members"]
        # Prefer on-shift members, fall back to all
        members = await _get_on_shift_reps(all_members, fallback_all=True)
        if method == "round_robin":
            idx = source.get("round_robin_index", 0)
            user_id = members[idx % len(members)]
            await db.lead_sources.update_one(
                {"_id": source["_id"]},
                {"$set": {"round_robin_index": (idx + 1) % len(members)}}
            )
            return user_id
        if method == "weighted_round_robin":
            counts = source.get("member_lead_counts", {})
            for m in members:
                if m not in counts:
                    counts[m] = 0
            user_id = min(members, key=lambda m: counts.get(m, 0))
            counts[user_id] = counts.get(user_id, 0) + 1
            await db.lead_sources.update_one(
                {"_id": source["_id"]},
                {"$set": {"member_lead_counts": counts}}
            )
            return user_id
    except Exception as e:
        logger.warning(f"[LeadIntake] Assignment error: {e}")
    return None


# ── Queued lead processor (called by scheduler every 2 min) ──────────────────

async def process_queued_leads():
    """
    Fire queued after-hours leads whose scheduled_send_at has passed.
    Sends via Twilio (or logs mock) and updates status.
    """
    db   = get_db()
    now  = datetime.now(timezone.utc)
    due  = await db.inbound_leads.find({
        "status": "queued",
        "scheduled_send_at": {"$lte": now},
    }).to_list(50)

    if not due:
        return

    logger.info(f"[LeadIntake] Processing {len(due)} queued leads")

    for lead in due:
        lead_id = str(lead["_id"])
        try:
            phone   = lead.get("phone", "")
            message = lead.get("draft_message", "")

            if phone and message:
                from services.twilio_service import send_sms, TWILIO_ENABLED
                # Use the rep's dedicated number for this lead if available
                rep_twilio_num = None
                rep_uid = lead.get("assigned_to") or lead.get("user_id")
                if rep_uid:
                    try:
                        rep = await db.users.find_one({"_id": ObjectId(rep_uid)}, {"twilio_number": 1, "mvpline_number": 1})
                        rep_twilio_num = (rep or {}).get("twilio_number") or (rep or {}).get("mvpline_number")
                    except Exception:
                        pass
                result = await send_sms(phone, message, from_phone=rep_twilio_num, media_urls=lead.get("media_urls") or None)
                mocked = result.get("mock", True)
            else:
                mocked = True

            await db.inbound_leads.update_one(
                {"_id": lead["_id"]},
                {"$set": {
                    "status":  "sent" if not mocked else "sent_mock",
                    "sent_at": now,
                }}
            )

            # Add message to conversation
            if lead.get("conversation_id"):
                try:
                    msg_doc = {
                        "conversation_id": lead["conversation_id"],
                        "content":         message,
                        "direction":       "outbound",
                        "channel":         "sms",
                        "sender":          "ai_draft",
                        "mocked":          mocked,
                        "created_at":      now,
                        "status":          "sent",
                        "has_media":       bool(lead.get("media_urls")),
                        "media_urls":      lead.get("media_urls") or [],
                    }
                    await db.messages.insert_one(msg_doc)
                    await db.conversations.update_one(
                        {"_id": ObjectId(lead["conversation_id"])},
                        {"$set": {"last_message_at": now, "status": "active"}}
                    )
                except Exception:
                    pass

            logger.info(f"[LeadIntake] Sent {'(MOCK) ' if mocked else ''}to {phone}: {message[:60]}…")

        except Exception as e:
            logger.error(f"[LeadIntake] Failed to send queued lead {lead_id}: {e}")
            await db.inbound_leads.update_one(
                {"_id": lead["_id"]},
                {"$set": {"status": "failed", "error": str(e)}}
            )


# ── API Endpoints ─────────────────────────────────────────────────────────────

def _get_source_from_query(source_id: Optional[str]) -> str:
    return source_id or ""


@router.post("/adf", response_class=PlainTextResponse)
async def receive_adf_lead(request: Request):
    """
    ADF/XML lead intake. Used by Cars.com, AutoTrader, and most OEM/portal providers.
    Accepts both raw XML body and URL-encoded 'XML=' form fields.
    Returns plain-text acknowledgement (required by ADF spec).

    Configure your portal: POST to  /api/leads/adf?source_id=<your_source_id>
    Optional header:  X-API-Key: <your_api_key>
    """
    db = get_db()

    body_bytes = await request.body()
    body_str   = body_bytes.decode("utf-8", errors="replace").strip()

    # Some portals POST as form field: XML=<adf>...</adf>
    if body_str.lower().startswith("xml=") or "xml=" in body_str.lower():
        import urllib.parse
        parsed = urllib.parse.parse_qs(body_str, keep_blank_values=True)
        body_str = next(
            (v[0] for k, v in parsed.items() if k.lower() == "xml"),
            body_str
        )

    # Parse
    try:
        normalized = parse_adf_xml(body_str)
    except ValueError as e:
        logger.error(f"[LeadIntake/ADF] Parse error: {e}\nBody: {body_str[:500]}")
        return PlainTextResponse("ERROR: Could not parse ADF XML", status_code=400)

    # Resolve source
    source_id = request.query_params.get("source_id")
    source = None
    if source_id and ObjectId.is_valid(source_id):
        source = await db.lead_sources.find_one({"_id": ObjectId(source_id)})

    if source is None:
        # Auto-match by vendor/source name or create a default
        vendor_name = normalized.get("source_name", "ADF Lead")
        source = await db.lead_sources.find_one(
            {"name": {"$regex": vendor_name, "$options": "i"}}
        )
        if source is None:
            # Use first active source as fallback
            source = await db.lead_sources.find_one({"is_active": True}) or {
                "name": vendor_name, "assignment_method": "jump_ball",
                "_id": None, "store_id": None
            }

    # Optional API key validation (skip if no key configured)
    api_key = request.headers.get("X-API-Key")
    if source.get("api_key") and api_key and api_key != source["api_key"]:
        return PlainTextResponse("ERROR: Invalid API key", status_code=401)

    if not normalized.get("source_name") and source.get("name"):
        normalized["source_name"] = source["name"]

    try:
        result = await process_inbound_lead(normalized, source, db, raw_body=body_str)
    except HTTPException as e:
        logger.error(f"[LeadIntake/ADF] Processing error: {e.detail}")
        return PlainTextResponse(f"ERROR: {e.detail}", status_code=e.status_code)

    # ADF spec requires plain-text acknowledgement
    return PlainTextResponse(
        f"SUCCESS: Lead received for {normalized.get('full_name','')} "
        f"| Lead ID: {result['lead_id']}"
    )


def _extract_adf_from_text(text: str) -> Optional[str]:
    """Pull an <adf>...</adf> block out of any text (email body, attachment, field)."""
    if not text:
        return None
    low = text.lower()
    i = low.find("<adf")
    if i == -1:
        return None
    j = low.find("</adf>", i)
    if j == -1:
        return None
    return text[i:j + 6]


@router.post("/email-inbound", response_class=PlainTextResponse)
async def receive_email_lead(request: Request):
    """
    Inbound-email webhook for ADF leads delivered by EMAIL (the industry default).
    Point any inbound email service here — SendGrid Inbound Parse, Mailgun Routes,
    CloudMailin, Zapier Email Parser, etc. The payload is scanned for ADF XML in
    every text field AND every attachment, so the provider format doesn't matter.

    Configure:  POST to /api/leads/email-inbound?source_id=<your_source_id>
    """
    import json as _json
    import base64 as _b64
    import quopri as _quopri

    db = get_db()
    content_type = request.headers.get("content-type", "")
    candidates: list = []
    subject, from_addr = "", ""

    try:
        if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
            form = await request.form()
            for key, val in form.multi_items():
                if hasattr(val, "read"):  # attachment (UploadFile)
                    try:
                        data = await val.read()
                        candidates.append(data.decode("utf-8", errors="replace"))
                    except Exception:
                        pass
                else:
                    sval = str(val)
                    lk = key.lower()
                    if lk == "subject":
                        subject = sval
                    elif lk in ("from", "sender"):
                        from_addr = sval
                    candidates.append(sval)
        else:
            body = (await request.body()).decode("utf-8", errors="replace")
            try:
                data = _json.loads(body)

                def _walk(o):
                    if isinstance(o, dict):
                        for v in o.values():
                            _walk(v)
                    elif isinstance(o, list):
                        for v in o:
                            _walk(v)
                    elif isinstance(o, str):
                        candidates.append(o)
                        if len(o) > 100 and "<" not in o[:60]:
                            try:  # base64-encoded attachment content
                                candidates.append(_b64.b64decode(o, validate=True).decode("utf-8", errors="replace"))
                            except Exception:
                                pass

                _walk(data)
                if isinstance(data, dict):
                    subject = str(data.get("subject") or (data.get("headers") or {}).get("subject") or "")
                    from_addr = str(data.get("from") or (data.get("envelope") or {}).get("from") or "")
            except Exception:
                candidates.append(body)
    except Exception as e:
        return PlainTextResponse(f"ERROR: could not read request: {e}", status_code=400)

    adf_xml = None
    for c in candidates:
        adf_xml = _extract_adf_from_text(c)
        if adf_xml:
            break
    if not adf_xml:
        # Emails are often quoted-printable encoded ("=3D" etc.) — retry after decoding
        for c in candidates:
            try:
                cleaned = _quopri.decodestring(c.encode("utf-8", errors="replace")).decode("utf-8", errors="replace")
                adf_xml = _extract_adf_from_text(cleaned)
                if adf_xml:
                    break
            except Exception:
                pass

    if not adf_xml:
        await db.lead_email_failures.insert_one({
            "subject": subject, "from": from_addr,
            "preview": " | ".join(c[:200] for c in candidates[:3]),
            "received_at": datetime.now(timezone.utc),
        })
        logger.warning(f"[LeadIntake/Email] No ADF XML found — subject='{subject}' from='{from_addr}'")
        return PlainTextResponse("ERROR: No ADF XML found in email", status_code=422)

    try:
        normalized = parse_adf_xml(adf_xml)
    except ValueError as e:
        logger.error(f"[LeadIntake/Email] Parse error: {e}")
        return PlainTextResponse("ERROR: Could not parse ADF XML", status_code=400)

    # Resolve source — same strategy as /adf
    source_id = request.query_params.get("source_id")
    source = None
    if source_id and ObjectId.is_valid(source_id):
        source = await db.lead_sources.find_one({"_id": ObjectId(source_id)})
    if source is None:
        vendor_name = normalized.get("source_name", "ADF Email Lead")
        source = await db.lead_sources.find_one(
            {"name": {"$regex": re.escape(vendor_name), "$options": "i"}}
        )
        if source is None:
            source = await db.lead_sources.find_one({"is_active": True}) or {
                "name": vendor_name, "assignment_method": "jump_ball",
                "_id": None, "store_id": None
            }
    if not normalized.get("source_name") and source.get("name"):
        normalized["source_name"] = source["name"]

    try:
        result = await process_inbound_lead(normalized, source, db, raw_body=adf_xml)
    except HTTPException as e:
        logger.error(f"[LeadIntake/Email] Processing error: {e.detail}")
        return PlainTextResponse(f"ERROR: {e.detail}", status_code=e.status_code)

    return PlainTextResponse(
        f"SUCCESS: Email lead received for {normalized.get('full_name', '')} "
        f"| Lead ID: {result['lead_id']}"
    )


@router.post("/webhook/{source_id}")
async def receive_webhook_lead(source_id: str, request: Request):
    """
    Universal JSON/form-data webhook.
    Accepts any field structure — smart normalizer maps to standard schema.
    Each lead source gets its own URL with an API key for security.

    POST to /api/leads/webhook/<source_id>
    Header: X-API-Key: <your_api_key>
    Body:   JSON or application/x-www-form-urlencoded
    """
    db = get_db()

    if not ObjectId.is_valid(source_id):
        raise HTTPException(status_code=400, detail="Invalid source ID")

    source = await db.lead_sources.find_one({"_id": ObjectId(source_id)})
    if not source:
        raise HTTPException(status_code=404, detail="Lead source not found")

    api_key = request.headers.get("X-API-Key")
    if source.get("api_key") and not api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header required")
    if source.get("api_key") and api_key != source["api_key"]:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not source.get("is_active", True):
        raise HTTPException(status_code=400, detail="Lead source is inactive")

    # Parse body — JSON or form
    content_type = request.headers.get("content-type", "")
    body_bytes = await request.body()
    body_str   = body_bytes.decode("utf-8", errors="replace")

    try:
        if "application/json" in content_type:
            import json
            raw = json.loads(body_str)
            # Flatten nested dict one level (some CRMs wrap in {"lead": {...}})
            if len(raw) == 1:
                only_val = next(iter(raw.values()))
                if isinstance(only_val, dict):
                    raw = only_val
        elif "xml" in content_type or body_str.strip().startswith("<"):
            # ADF XML posted to generic webhook
            raw_normalized = parse_adf_xml(body_str)
            result = await process_inbound_lead(raw_normalized, source, db, raw_body=body_str)
            return {"success": True, **result}
        else:
            import urllib.parse
            raw = {k: v[0] if isinstance(v, list) and v else v
                   for k, v in urllib.parse.parse_qs(body_str, keep_blank_values=True).items()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse request body: {e}")

    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="Expected JSON object or form fields")

    normalized = normalize_fields(raw)
    if not normalized.get("source_name"):
        normalized["source_name"] = source.get("name", "")

    result = await process_inbound_lead(normalized, source, db, raw_body=body_str)
    return {"success": True, **result}


async def _first_human_replies(db, conv_ids: list) -> dict:
    """Batch: first human (non-automated) outbound message per conversation.
    Returns {conversation_id: {"ts": datetime, "rep_id": str}}."""
    if not conv_ids:
        return {}
    pipeline = [
        {"$match": {"conversation_id": {"$in": conv_ids}, "sender": "user", "auto_sent": {"$ne": True}}},
        {"$addFields": {"_ts": {"$ifNull": ["$timestamp", "$created_at"]}}},
        {"$match": {"_ts": {"$ne": None}}},
        {"$sort": {"_ts": 1}},
        {"$group": {"_id": "$conversation_id",
                    "first_ts": {"$first": "$_ts"},
                    "rep_id": {"$first": {"$ifNull": ["$user_id", "$sender_id"]}}}},
    ]
    out = {}
    async for row in db.messages.aggregate(pipeline):
        out[row["_id"]] = {"ts": row["first_ts"], "rep_id": row.get("rep_id")}
    return out


def _resp_seconds(received, ts) -> Optional[int]:
    try:
        if received.tzinfo:
            received = received.replace(tzinfo=None)
        if ts.tzinfo:
            ts = ts.replace(tzinfo=None)
        s = (ts - received).total_seconds()
        return int(s) if s >= 0 else None
    except Exception:
        return None


def _require_auth(request: Request) -> str:
    """JWT gate for read/analytics endpoints (intake POSTs stay public for providers)."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        from routers.auth import verify_jwt_token
        p = verify_jwt_token(auth[7:])
        if p and p.get("sub"):
            return p["sub"]
    raise HTTPException(status_code=401, detail="Authentication required")


@router.get("/")
async def list_leads(
    request:  Request,
    store_id: Optional[str] = None,
    status:   Optional[str] = None,
    limit:    int = 50,
    skip:     int = 0,
):
    """List received internet leads with status, matched vehicle, and reply flag."""
    _require_auth(request)
    db    = get_db()
    query: dict = {}
    if store_id:
        query["store_id"] = store_id
    if status:
        query["status"] = status

    leads = await db.inbound_leads.find(query).sort(
        "received_at", -1
    ).skip(skip).limit(limit).to_list(limit)

    # Which of these leads' conversations got a customer reply?
    conv_ids = [l.get("conversation_id") for l in leads if l.get("conversation_id")]
    replied_convs = set()
    if conv_ids:
        replied_convs = set(await db.messages.distinct(
            "conversation_id",
            {"conversation_id": {"$in": conv_ids}, "direction": "inbound"}
        ))

    # Speed-to-lead: first human rep reply per conversation
    first_replies = await _first_human_replies(db, conv_ids)

    return [
        {
            "id":             str(l["_id"]),
            "first_response_seconds": (
                _resp_seconds(l.get("received_at"), first_replies[l["conversation_id"]]["ts"])
                if l.get("conversation_id") in first_replies and isinstance(l.get("received_at"), datetime)
                else None
            ),
            "source_name":    l.get("source_name"),
            "full_name":      l.get("full_name"),
            "phone":          l.get("phone"),
            "email":          l.get("email"),
            "vehicle_interest": l.get("vehicle_interest"),
            "matched_inventory": l.get("matched_inventory"),
            "comments":       l.get("comments", ""),
            "status":         l.get("status"),
            "has_reply":      l.get("conversation_id") in replied_convs,
            "is_after_hours": l.get("is_after_hours", False),
            "scheduled_send_at": l.get("scheduled_send_at").isoformat() if isinstance(l.get("scheduled_send_at"), datetime) else l.get("scheduled_send_at"),
            "sent_at":        l.get("sent_at").isoformat() if isinstance(l.get("sent_at"), datetime) else None,
            "draft_message":  l.get("draft_message"),
            "contact_id":     l.get("contact_id"),
            "conversation_id": l.get("conversation_id"),
            "assigned_to":    l.get("assigned_to"),
            "received_at":    l.get("received_at").isoformat() if isinstance(l.get("received_at"), datetime) else None,
        }
        for l in leads
    ]


@router.get("/analytics/sources")
async def lead_source_analytics(
    request:  Request,
    store_id: Optional[str] = None,
    days:     int = 90,
):
    """Per-source funnel: leads → sent → replied → sold. Shows what's worth paying for."""
    _require_auth(request)
    db = get_db()
    days = min(max(days, 1), 365)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    query: dict = {"received_at": {"$gte": since}}
    if store_id:
        query["store_id"] = store_id
    leads = await db.inbound_leads.find(
        query,
        {"source_name": 1, "source_id": 1, "status": 1, "conversation_id": 1, "contact_id": 1}
    ).to_list(3000)

    conv_ids = [l.get("conversation_id") for l in leads if l.get("conversation_id")]
    replied_convs = set()
    if conv_ids:
        replied_convs = set(await db.messages.distinct(
            "conversation_id",
            {"conversation_id": {"$in": conv_ids}, "direction": "inbound"}
        ))

    contact_oids = []
    for l in leads:
        try:
            contact_oids.append(ObjectId(l.get("contact_id")))
        except Exception:
            pass
    sold_contacts = set()
    if contact_oids:
        async for c in db.contacts.find(
            {"_id": {"$in": contact_oids}, "date_sold": {"$nin": [None, ""]}}, {"_id": 1}
        ):
            sold_contacts.add(str(c["_id"]))

    by_source: dict = {}
    for l in leads:
        key = l.get("source_name") or "Unknown"
        s = by_source.setdefault(key, {
            "source_name": key, "source_id": l.get("source_id", ""),
            "leads": 0, "sent": 0, "replied": 0, "sold": 0, "failed": 0,
        })
        s["leads"] += 1
        if l.get("status") == "sent":
            s["sent"] += 1
        elif l.get("status") == "failed":
            s["failed"] += 1
        if l.get("conversation_id") in replied_convs:
            s["replied"] += 1
        if l.get("contact_id") in sold_contacts:
            s["sold"] += 1

    # Layer in real-dollar cost (from lead source monthly_cost)
    cost_by_name = {}
    async for src in db.lead_sources.find({"monthly_cost": {"$gt": 0}}, {"name": 1, "monthly_cost": 1}):
        cost_by_name[src.get("name", "")] = float(src["monthly_cost"])

    sources = []
    for s in by_source.values():
        s["reply_rate"] = round(s["replied"] / s["leads"] * 100) if s["leads"] else 0
        s["sold_rate"] = round(s["sold"] / s["leads"] * 100) if s["leads"] else 0
        monthly = cost_by_name.get(s["source_name"])
        if monthly:
            period_cost = round(monthly * days / 30, 2)
            s["monthly_cost"] = monthly
            s["period_cost"] = period_cost
            s["cost_per_lead"] = round(period_cost / s["leads"], 2) if s["leads"] else None
            s["cost_per_sale"] = round(period_cost / s["sold"], 2) if s["sold"] else None
        else:
            s["monthly_cost"] = None
            s["period_cost"] = None
            s["cost_per_lead"] = None
            s["cost_per_sale"] = None
        sources.append(s)
    sources.sort(key=lambda x: x["leads"], reverse=True)

    totals = {
        "leads": sum(s["leads"] for s in sources),
        "replied": sum(s["replied"] for s in sources),
        "sold": sum(s["sold"] for s in sources),
    }
    return {"days": days, "sources": sources, "totals": totals}


@router.get("/analytics/response-times")
async def lead_response_times(
    request:  Request,
    store_id: Optional[str] = None,
    days:     int = 90,
):
    """Speed-to-lead: per-rep average time from lead arrival to first human reply."""
    _require_auth(request)
    db = get_db()
    days = min(max(days, 1), 365)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    query: dict = {"received_at": {"$gte": since}, "conversation_id": {"$nin": [None, ""]}}
    if store_id:
        query["store_id"] = store_id
    leads = await db.inbound_leads.find(
        query, {"conversation_id": 1, "received_at": 1, "assigned_to": 1, "contact_id": 1, "created_at": 1}
    ).to_list(3000)

    conv_map = {l["conversation_id"]: l for l in leads}
    from services.lead_clocks import clocks_for_leads, summarize_clocks
    clocks = await clocks_for_leads(db, leads)

    per_rep: dict = {}
    all_secs: list = []
    rep_rows: dict = {}
    for cid, l in conv_map.items():
        r = clocks.get(cid)
        if not r:
            continue
        rep_id = str(r.get("human_rep") or r.get("call_rep") or r.get("assigned_to") or "") or "unassigned"
        rep_rows.setdefault(rep_id, []).append(r)
        if r.get("human_secs") is not None:
            per_rep.setdefault(rep_id, []).append(r["human_secs"])
            all_secs.append(r["human_secs"])

    names = {}
    rep_oids = [ObjectId(r) for r in rep_rows if ObjectId.is_valid(r)]
    if rep_oids:
        async for u in db.users.find({"_id": {"$in": rep_oids}}, {"name": 1}):
            names[str(u["_id"])] = u.get("name", "")

    reps = []
    for rid, rows in rep_rows.items():
        secs = per_rep.get(rid, [])
        s = summarize_clocks(rows)
        if s["clocks"]["call"]["measured"] == 0 and not secs and s["customer"]["texted"] == 0:
            continue
        reps.append({
            "user_id":        rid,
            "name":           names.get(rid) or ("Unassigned" if rid == "unassigned" else "Unknown"),
            "count":          len(secs),
            "avg_seconds":    int(sum(secs) / len(secs)) if secs else None,
            "fastest_seconds": min(secs) if secs else None,
            "slowest_seconds": max(secs) if secs else None,
            "leads":          len(rows),
            "call_avg_seconds": s["clocks"]["call"]["avg_seconds"],
            "call_measured":  s["clocks"]["call"]["measured"],
            "reply_rate":     s["customer"]["reply_rate"],
            "replied":        s["customer"]["replied"],
            "texted":         s["customer"]["texted"],
            "reply_avg_seconds": s["customer"]["avg_seconds"],
        })
    reps.sort(key=lambda r: (r["avg_seconds"] is None, r["avg_seconds"] or 0))

    team = summarize_clocks(list(clocks.values()))
    return {
        "days": days,
        "overall": {
            "avg_seconds":     int(sum(all_secs) / len(all_secs)) if all_secs else None,
            "measured":        len(all_secs),
            "unanswered":      len(conv_map) - len(all_secs),
            "fastest_seconds": min(all_secs) if all_secs else None,
        },
        "clocks": team["clocks"],
        "customer": team["customer"],
        "reps": reps,
    }


def _bucket_rows(rows: list, sold: set, key, buckets: list) -> list:
    """buckets: [(label, predicate)] over per-lead clock rows. Returns leads/sold/close_rate/reply_rate per bucket."""
    out = []
    for label, pred in buckets:
        grp = [r for r in rows if pred(r.get(key))]
        s = sum(1 for r in grp if r.get("contact_id") in sold)
        rep = sum(1 for r in grp if r.get("reply_secs") is not None)
        out.append({"label": label, "leads": len(grp), "sold": s,
                    "close_rate": int(round(100 * s / len(grp))) if grp else None,
                    "reply_rate": int(round(100 * rep / len(grp))) if grp else None})
    return out


async def compute_proof(db, store_id: Optional[str], days: int) -> dict:
    """Does engagement move the close rate? Replied vs silent, speed buckets, touchpoint buckets, per source cost, all against date_sold."""
    days = min(max(days, 1), 1095)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    query: dict = {"received_at": {"$gte": since}, "conversation_id": {"$nin": [None, ""]}, "is_test": {"$ne": True}}
    if store_id:
        query["store_id"] = store_id
    leads = await db.inbound_leads.find(query, {"conversation_id": 1, "received_at": 1, "assigned_to": 1, "contact_id": 1, "created_at": 1, "source_name": 1, "source_id": 1}).to_list(5000)
    from services.lead_clocks import clocks_for_leads
    clocks = await clocks_for_leads(db, leads)
    rows = list(clocks.values())
    src_by_conv = {l["conversation_id"]: (l.get("source_name") or "Unknown") for l in leads}
    src_ids = {(l.get("source_name") or "Unknown"): str(l.get("source_id") or "") for l in leads if l.get("source_id")}
    for cid, r in clocks.items():
        r["source_name"] = src_by_conv.get(cid, "Unknown")

    sold: set = set()
    sold_at: dict = {}
    oids = [ObjectId(r["contact_id"]) for r in rows if ObjectId.is_valid(r.get("contact_id") or "")]
    if oids:
        async for c in db.contacts.find({"_id": {"$in": oids}, "date_sold": {"$nin": [None, ""]}}, {"_id": 1, "date_sold": 1}):
            sold.add(str(c["_id"]))
            ds = c.get("date_sold")
            if isinstance(ds, str):
                try:
                    ds = datetime.fromisoformat(ds.replace("Z", "+00:00"))
                except Exception:
                    ds = None
            if isinstance(ds, datetime):
                sold_at[str(c["_id"])] = ds if ds.tzinfo else ds.replace(tzinfo=timezone.utc)

    def _days_to_sold(r):
        ds, rcv = sold_at.get(r.get("contact_id")), r.get("received_at")
        if not ds or not rcv:
            return None
        d = (ds - rcv).total_seconds() / 86400
        return round(d, 1) if d >= 0 else None
    tts = [d for d in (_days_to_sold(r) for r in rows) if d is not None]
    time_to_sold = {"count": len(tts), "avg_days": round(sum(tts) / len(tts), 1) if tts else None,
                    "median_days": sorted(tts)[len(tts) // 2] if tts else None, "fastest_days": min(tts) if tts else None}

    cost_by_name = {}
    async for src in db.lead_sources.find({"monthly_cost": {"$gt": 0}}, {"name": 1, "monthly_cost": 1}):
        cost_by_name[src.get("name", "")] = float(src["monthly_cost"])
    by_src: dict = {}
    for r in rows:
        by_src.setdefault(r["source_name"], []).append(r)
    sources = []
    for name, grp in by_src.items():
        s = sum(1 for r in grp if r.get("contact_id") in sold)
        texted_g = [r for r in grp if r.get("texted")]
        replied_g = [r for r in texted_g if r.get("reply_secs") is not None]
        touch = [t for t in ((r.get("received_at") and r.get("first_outbound_at") and int((r["first_outbound_at"] - r["received_at"]).total_seconds())) for r in grp) if isinstance(t, int)]
        dts = [d for d in (_days_to_sold(r) for r in grp) if d is not None]
        monthly = cost_by_name.get(name)
        period_cost = round(monthly * days / 30, 2) if monthly else None
        sources.append({
            "source_name": name, "source_id": src_ids.get(name), "leads": len(grp), "sold": s,
            "close_rate": int(round(100 * s / len(grp))) if grp else None,
            "reply_rate": int(round(100 * len(replied_g) / len(texted_g))) if texted_g else None,
            "first_touch_avg_seconds": int(sum(touch) / len(touch)) if touch else None,
            "touched_pct": int(round(100 * len(touch) / len(grp))) if grp else None,
            "avg_touches": round(sum(int(r.get("outbound_texts") or 0) + int(r.get("calls") or 0) for r in grp) / len(grp), 1) if grp else None,
            "avg_days_to_sold": round(sum(dts) / len(dts), 1) if dts else None,
            "monthly_cost": monthly, "period_cost": period_cost,
            "cost_per_lead": round(period_cost / len(grp), 2) if period_cost and grp else None,
            "cost_per_sale": round(period_cost / s, 2) if period_cost and s else None,
        })
    sources.sort(key=lambda x: (-(x["sold"]), -(x["leads"])))

    def rate(grp):
        s = sum(1 for r in grp if r.get("contact_id") in sold)
        return {"leads": len(grp), "sold": s, "close_rate": int(round(100 * s / len(grp))) if grp else None}

    texted = [r for r in rows if r.get("texted")]
    replied = [r for r in texted if r.get("reply_secs") is not None]
    silent = [r for r in texted if r.get("reply_secs") is None]
    reply_cmp = {"replied": rate(replied), "silent": rate(silent)}
    rr, sr = reply_cmp["replied"]["close_rate"], reply_cmp["silent"]["close_rate"]
    reply_cmp["lift"] = round(rr / sr, 1) if rr is not None and sr else None

    speed = _bucket_rows(rows, sold, "human_secs", [
        ("Under 5 min", lambda s: s is not None and s < 300),
        ("5 to 30 min", lambda s: s is not None and 300 <= s < 1800),
        ("30 min to 2 h", lambda s: s is not None and 1800 <= s < 7200),
        ("2 to 24 h", lambda s: s is not None and 7200 <= s < 86400),
        ("Over 24 h", lambda s: s is not None and s >= 86400),
        ("No human text", lambda s: s is None),
    ])
    # first touch of any kind (AI, human or call)
    def _touch_secs(r):
        a, b = r.get("received_at"), r.get("first_outbound_at")
        return int((b - a).total_seconds()) if a and b else None
    for r in rows:
        r["_touch_secs"] = _touch_secs(r)
    first_touch = _bucket_rows(rows, sold, "_touch_secs", [
        ("Under 5 min", lambda s: s is not None and s < 300),
        ("5 to 30 min", lambda s: s is not None and 300 <= s < 1800),
        ("30 min to 2 h", lambda s: s is not None and 1800 <= s < 7200),
        ("Over 2 h", lambda s: s is not None and s >= 7200),
        ("Never touched", lambda s: s is None),
    ])
    for r in rows:
        r["_touches"] = int(r.get("outbound_texts") or 0) + int(r.get("calls") or 0)
    touches = _bucket_rows(rows, sold, "_touches", [
        ("0", lambda n: n == 0), ("1", lambda n: n == 1), ("2 to 3", lambda n: 2 <= n <= 3),
        ("4 to 6", lambda n: 4 <= n <= 6), ("7+", lambda n: n >= 7),
    ])
    conversation = _bucket_rows(rows, sold, "inbound_texts", [
        ("No reply", lambda n: n == 0), ("1 reply", lambda n: n == 1), ("2 to 4 replies", lambda n: 2 <= n <= 4), ("5+ replies", lambda n: n >= 5),
    ])

    headlines = []
    if rr is not None and sr is not None and replied and silent:
        headlines.append(f"Leads that texted back closed at {rr}% vs {sr}% for leads that stayed silent" + (f" ({reply_cmp['lift']}x)" if reply_cmp["lift"] else "") + ".")
    fast = next((b for b in first_touch if b["label"] == "Under 5 min" and b["leads"]), None)
    slow = [b for b in first_touch if b["label"] in ("30 min to 2 h", "Over 2 h") and b["leads"]]
    if fast and slow and fast["close_rate"] is not None:
        slow_leads = sum(b["leads"] for b in slow); slow_sold = sum(b["sold"] for b in slow)
        slow_rate = int(round(100 * slow_sold / slow_leads)) if slow_leads else None
        if slow_rate is not None:
            headlines.append(f"First touch under 5 minutes closed at {fast['close_rate']}% vs {slow_rate}% when it took over 30 minutes.")
    many = [b for b in touches if b["label"] in ("4 to 6", "7+") and b["leads"]]
    few = [b for b in touches if b["label"] in ("0", "1") and b["leads"]]
    if many and few:
        ml, ms = sum(b["leads"] for b in many), sum(b["sold"] for b in many)
        fl, fs = sum(b["leads"] for b in few), sum(b["sold"] for b in few)
        if ml and fl:
            headlines.append(f"Leads with 4 or more touches closed at {int(round(100 * ms / ml))}% vs {int(round(100 * fs / fl))}% with one touch or none.")
    total_sold = len([r for r in rows if r.get("contact_id") in sold])
    if time_to_sold["avg_days"] is not None:
        headlines.append(f"Sold leads went from submission to sold in {time_to_sold['avg_days']} days on average (fastest {time_to_sold['fastest_days']}).")
    best_cost = [s for s in sources if s.get("cost_per_sale")]
    if len(best_cost) >= 2:
        best_cost.sort(key=lambda s: s["cost_per_sale"])
        b, w = best_cost[0], best_cost[-1]
        headlines.append(f"True cost per sale: {b['source_name']} ${b['cost_per_sale']:,.0f} vs {w['source_name']} ${w['cost_per_sale']:,.0f}.")
    by_rep: dict = {}
    for r in rows:
        rid = str(r.get("human_rep") or r.get("call_rep") or r.get("assigned_to") or "") or None
        if rid:
            by_rep.setdefault(rid, []).append(r)
    rep_names = {}
    rep_oids = [ObjectId(x) for x in by_rep if ObjectId.is_valid(x)]
    if rep_oids:
        async for u in db.users.find({"_id": {"$in": rep_oids}}, {"name": 1}):
            rep_names[str(u["_id"])] = u.get("name", "")
    reps = []
    for rid, grp in by_rep.items():
        tg = [r for r in grp if r.get("texted")]
        rg = [r for r in tg if r.get("reply_secs") is not None]
        sg = [r for r in tg if r.get("reply_secs") is None]
        hs = [r["human_secs"] for r in grp if r.get("human_secs") is not None]
        reps.append({"user_id": rid, "name": rep_names.get(rid) or "Unknown", "leads": len(grp), **rate(grp),
                     "replied": rate(rg), "silent": rate(sg), "reply_rate": int(round(100 * len(rg) / len(tg))) if tg else None,
                     "first_text_avg_seconds": int(sum(hs) / len(hs)) if hs else None})
    reps.sort(key=lambda x: (-(x["sold"]), -(x["leads"])))
    unpriced = [{"source_id": x["source_id"], "source_name": x["source_name"], "leads": x["leads"]} for x in sources
                if x["leads"] and not x.get("monthly_cost") and x.get("source_id") and x["source_name"] != "Unknown"]
    return {
        "days": days, "leads": len(rows), "sold": total_sold,
        "close_rate": int(round(100 * total_sold / len(rows))) if rows else None,
        "small_sample": len(rows) < 30,
        "reply": reply_cmp, "speed_human_text": speed, "speed_first_touch": first_touch,
        "touchpoints": touches, "conversation_depth": conversation, "headlines": headlines,
        "time_to_sold": time_to_sold, "sources": sources, "unpriced_sources": unpriced, "reps": reps,
        "benchmark": "Harvard Business Review: contacting a lead within 1 hour makes qualifying it 7x more likely than waiting 2 hours or more.",
    }


@router.get("/analytics/proof")
async def lead_engagement_proof(request: Request, store_id: Optional[str] = None, days: int = 365):
    _require_auth(request)
    return await compute_proof(get_db(), store_id, days)


async def store_display_name(db, store_id) -> str:
    if store_id and ObjectId.is_valid(str(store_id)):
        st = await db.stores.find_one({"_id": ObjectId(str(store_id))}, {"name": 1})
        return (st or {}).get("name") or ""
    return ""


def proof_png_response(proof: dict, store_name: str, theme: str, fmt: str):
    from services.proof_card import render_proof_card
    from fastapi.responses import Response
    png = render_proof_card(proof, store_name, theme=("light" if theme == "light" else "dark"), square=(fmt == "square"))
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "no-store", "Content-Disposition": "inline; filename=imos-proof.png"})


@router.get("/analytics/proof-card.png")
async def lead_engagement_proof_card(request: Request, store_id: Optional[str] = None, days: int = 90, theme: str = "dark", format: str = "portrait"):
    """Branded PNG of the proof headlines, ready to text or post. theme=dark|light, format=portrait|square."""
    caller_id = _require_auth(request)
    db = get_db()
    proof = await compute_proof(db, store_id, days)
    sid = store_id
    if not sid and ObjectId.is_valid(caller_id):
        u = await db.users.find_one({"_id": ObjectId(caller_id)}, {"store_id": 1})
        sid = (u or {}).get("store_id")
    return proof_png_response(proof, await store_display_name(db, sid), theme, format)


async def _caller_store(db, caller_id: str, store_id: Optional[str]) -> tuple:
    """(store_id, user) for proof-link management. Managers only, scoped to their own store unless super admin."""
    user = await db.users.find_one({"_id": ObjectId(caller_id)}, {"role": 1, "store_id": 1, "name": 1}) if ObjectId.is_valid(caller_id) else None
    if not user or user.get("role") not in ("super_admin", "admin", "manager", "store_manager", "org_admin"):
        raise HTTPException(status_code=403, detail="Manager role required")
    sid = store_id if (store_id and user.get("role") == "super_admin") else user.get("store_id")
    if not sid:
        raise HTTPException(status_code=400, detail="No store on this account")
    return str(sid), user


def _proof_public_url(token: str) -> str:
    base = (os.environ.get("PUBLIC_FACING_URL") or os.environ.get("APP_URL") or "https://app.imonsocial.com").rstrip("/")
    return f"{base}/proof/{token}"


@router.get("/analytics/proof-link")
async def get_proof_link(request: Request, store_id: Optional[str] = None):
    caller_id = _require_auth(request)
    db = get_db()
    sid, _ = await _caller_store(db, caller_id, store_id)
    st = await db.stores.find_one({"_id": ObjectId(sid)}, {"proof_share": 1}) or {}
    ps = st.get("proof_share") or {}
    return {"enabled": bool(ps.get("enabled")) and bool(ps.get("token")), "url": _proof_public_url(ps["token"]) if ps.get("token") else None,
            "views": ps.get("views", 0), "last_viewed_at": ps.get("last_viewed_at")}


class ProofLinkBody(BaseModel):
    enabled: bool = True
    rotate: bool = False


@router.post("/analytics/proof-link")
async def set_proof_link(body: ProofLinkBody, request: Request, store_id: Optional[str] = None):
    """Enable, disable or rotate the public proof page link for the manager's store."""
    caller_id = _require_auth(request)
    db = get_db()
    sid, user = await _caller_store(db, caller_id, store_id)
    st = await db.stores.find_one({"_id": ObjectId(sid)}, {"proof_share": 1}) or {}
    ps = dict(st.get("proof_share") or {})
    if body.rotate or not ps.get("token"):
        import secrets
        ps["token"] = secrets.token_urlsafe(12)
        ps["created_at"] = datetime.now(timezone.utc)
        ps["created_by"] = caller_id
        ps["views"] = 0
    ps["enabled"] = body.enabled
    ps["updated_at"] = datetime.now(timezone.utc)
    await db.stores.update_one({"_id": ObjectId(sid)}, {"$set": {"proof_share": ps}})
    return {"enabled": ps["enabled"], "url": _proof_public_url(ps["token"]), "views": ps.get("views", 0)}


async def public_proof_payload(db, token: str, days: int) -> dict:
    st = await db.stores.find_one({"proof_share.token": token}, {"name": 1, "proof_share": 1, "city": 1, "state": 1})
    if not st or not (st.get("proof_share") or {}).get("enabled"):
        raise HTTPException(status_code=404, detail="This proof link is not active")
    days = days if days in (30, 90, 365) else 90
    proof = await compute_proof(db, str(st["_id"]), days)
    proof.pop("unpriced_sources", None)
    proof["reps"] = [{k: v for k, v in r.items() if k != "user_id"} for r in proof.get("reps", [])]
    for s in proof.get("sources", []):
        s.pop("source_id", None)
    proof["store_name"] = st.get("name") or "Dealership"
    proof["generated_at"] = datetime.now(timezone.utc).isoformat()
    return proof


def _retry_by_attempt(tasks: list) -> list:
    """Outcomes grouped by which miss (# attempt) the retry task was on when it closed."""
    out: dict = {}
    for t in tasks:
        a = max(1, int(t.get("retry_attempt") or 1))
        b = out.setdefault(a, {"attempt": a, "retries": 0, "connected": 0, "replied": 0, "just_tried": 0})
        b["retries"] += 1
        if t.get("just_tried_sent_at"):
            b["just_tried"] += 1
        via = t.get("completed_via") if t.get("completed") else None
        if via == "call_connected":
            b["connected"] += 1
        elif via == "customer_replied":
            b["replied"] += 1
    return [out[k] for k in sorted(out)]


def _retry_reach_split(tasks: list) -> tuple:
    """(reach% with a just-tried text, n, reach% without, n) over closed retries."""
    def _rate(sub):
        closed = [t for t in sub if t.get("completed")]
        reached = sum(1 for t in closed if t.get("completed_via") in ("call_connected", "customer_replied"))
        return (int(round(100 * reached / len(closed))) if closed else None), len(closed)
    w, nw = _rate([t for t in tasks if t.get("just_tried_sent_at")])
    wo, nwo = _rate([t for t in tasks if not t.get("just_tried_sent_at")])
    return w, nw, wo, nwo


def _median_reply_minutes(tasks: list):
    mins = []
    for t in tasks:
        a, b = t.get("just_tried_sent_at"), t.get("completed_at")
        if t.get("completed_via") == "customer_replied" and isinstance(a, datetime) and isinstance(b, datetime):
            d = (b.replace(tzinfo=None) - a.replace(tzinfo=None)).total_seconds() / 60
            if 0 <= d <= 7 * 24 * 60:
                mins.append(d)
    if not mins:
        return None
    mins.sort()
    return int(round(mins[len(mins) // 2]))


def _retry_coach_tip(r: dict, tasks: list, team_best: int | None) -> str:
    w, nw, wo, nwo = _retry_reach_split(tasks)
    if nw >= 2 and nwo >= 2 and w is not None and wo is not None:
        if w > wo:
            verb = "doubles" if wo and w >= 2 * wo else "lifts"
            return f"Texting after a miss {verb} your reach rate: {wo}% without a text, {w}% with one. Send the just-tried text every time."
        return f"Your calls alone reach {wo}%; texts aren't adding much yet. Try texting right after miss #1 instead of later."
    replied_by = {b["attempt"]: b["replied"] for b in _retry_by_attempt(tasks) if b["replied"]}
    if replied_by:
        best = max(replied_by, key=lambda k: (replied_by[k], -k))
        return f"Most of your texts back land after miss #{best}. Send the just-tried text by then at the latest."
    if r["misses"] and not r["just_tried"]:
        return "No just-tried texts this period. One tap after a voicemail is the easiest way to get a reply."
    if team_best:
        return f"Team-wide, texts back come most often after miss #{team_best}. Text by then and you'll catch most of them."
    return "Text right after the first voicemail. A quick just-tried text gets most replies within the hour."


@router.get("/analytics/call-retries")
async def call_retry_outcomes(
    request:  Request,
    store_id: Optional[str] = None,
    days:     int = 7,
):
    """Voicemail retries: per rep, how many missed calls turned into a connection (or a text back)."""
    caller_id = _require_auth(request)
    db = get_db()
    days = min(max(days, 1), 365)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    caller = await db.users.find_one({"_id": ObjectId(caller_id)}, {"role": 1}) if ObjectId.is_valid(caller_id) else None
    is_manager = (caller or {}).get("role") in ("super_admin", "admin", "manager", "store_manager", "org_admin")
    scope: dict = {"user_id": caller_id}
    if is_manager:
        scope = {"user_id": {"$in": [str(u["_id"]) async for u in db.users.find({"store_id": store_id}, {"_id": 1})]}} if store_id else {}

    def _blank():
        return {"misses": 0, "voicemails": 0, "retries": 0, "connected": 0, "replied": 0, "open": 0, "gave_up": 0, "just_tried": 0}
    per: dict = {}
    tasks_by_user: dict = {}
    async for e in db.contact_events.find({**scope, "event_type": {"$in": ["call_voicemail", "call_no_answer", "call_busy"]},
                                           "timestamp": {"$gte": since}}, {"user_id": 1, "event_type": 1}):
        r = per.setdefault(str(e.get("user_id")), _blank())
        r["misses"] += 1
        if e.get("event_type") == "call_voicemail":
            r["voicemails"] += 1
    task_q = {**scope, "auto_kind": {"$in": ["call_retry", "call_retry_final"]},
              "$or": [{"created_at": {"$gte": since}}, {"completed_at": {"$gte": since}}, {"completed": {"$ne": True}}]}
    async for t in db.tasks.find(task_q, {"user_id": 1, "auto_kind": 1, "completed": 1, "completed_via": 1, "retry_attempt": 1,
                                          "completed_at": 1, "created_at": 1, "just_tried_sent_at": 1}):
        uid = str(t.get("user_id"))
        r = per.setdefault(uid, _blank())
        created = t.get("created_at")
        in_window = isinstance(created, datetime) and (created.replace(tzinfo=created.tzinfo or timezone.utc) >= since)
        if t.get("auto_kind") == "call_retry_final":
            if in_window:
                r["gave_up"] += 1
            continue
        tasks_by_user.setdefault(uid, []).append(t)
        r["retries"] += 1
        if not t.get("completed"):
            r["open"] += 1
        elif t.get("completed_via") == "call_connected":
            r["connected"] += 1
        elif t.get("completed_via") == "customer_replied":
            r["replied"] += 1
        if t.get("just_tried_sent_at"):
            r["just_tried"] += 1

    names = {}
    oids = [ObjectId(u) for u in per if ObjectId.is_valid(u)]
    if oids:
        async for u in db.users.find({"_id": {"$in": oids}}, {"name": 1}):
            names[str(u["_id"])] = u.get("name", "")

    all_tasks = [t for ts in tasks_by_user.values() for t in ts]
    by_attempt = _retry_by_attempt(all_tasks)
    replied_total = sum(b["replied"] for b in by_attempt)
    best = max((b for b in by_attempt if b["replied"]), key=lambda b: (b["replied"], -b["attempt"]), default=None)
    insight = {
        "best_attempt": best["attempt"] if best else None,
        "replied_total": replied_total,
        "share_pct": int(round(100 * best["replied"] / replied_total)) if best else None,
        "median_reply_minutes": _median_reply_minutes(all_tasks),
    }
    team_best = insight["best_attempt"]

    def _rate(r):
        done = r["retries"] - r["open"] + r["gave_up"]
        return int(round(100 * (r["connected"] + r["replied"]) / done)) if done else None
    reps = [{"user_id": uid, "name": names.get(uid) or "Unknown", **r, "reach_rate": _rate(r),
             "tip": _retry_coach_tip(r, tasks_by_user.get(uid, []), team_best)} for uid, r in per.items()]
    reps.sort(key=lambda r: (-(r["connected"] + r["replied"]), -r["misses"]))
    totals = _blank()
    for r in per.values():
        for k in totals:
            totals[k] += r[k]
    mine = per.get(caller_id) or _blank()
    return {"days": days, "is_manager": is_manager, "totals": {**totals, "reach_rate": _rate(totals)}, "reps": reps,
            "by_attempt": by_attempt, "insight": insight,
            "my_tip": _retry_coach_tip(mine, tasks_by_user.get(caller_id, []), team_best)}


@router.get("/awaiting/{user_id}")
async def awaiting_leads(user_id: str):
    """Speed-to-lead: this rep's internet leads still waiting on a first human reply."""
    db = get_db()
    convs = await db.conversations.find(
        {"user_id": user_id, "is_internet_lead": True, "status": "active"},
        {"contact_name": 1, "created_at": 1},
    ).sort("created_at", 1).limit(50).to_list(50)
    for c in convs:
        c["_id"] = str(c["_id"])
    replied = await _first_human_replies(db, [c["_id"] for c in convs])
    waiting = [c for c in convs if c["_id"] not in replied]
    oldest = waiting[0] if waiting else None
    return {
        "count": len(waiting),
        "oldest": {
            "conversation_id": oldest["_id"],
            "contact_name": oldest.get("contact_name"),
            "received_at": oldest["created_at"].isoformat() if isinstance(oldest.get("created_at"), datetime) else oldest.get("created_at"),
        } if oldest else None,
    }


# ── Monthly ROI email ─────────────────────────────────────────────────────────

_DEFAULT_ROI_RECIPIENT = os.environ.get("ADMIN_EMAIL", "forest@imosapp.com")


async def _compute_roi_rows(db, store_id, start, end):
    """Per-source funnel + cost for one store over a window. Returns (rows, totals)."""
    query: dict = {"received_at": {"$gte": start, "$lt": end}}
    if store_id:
        query["store_id"] = store_id
    else:
        query["store_id"] = {"$in": [None, ""]}
    leads = await db.inbound_leads.find(
        query, {"source_name": 1, "status": 1, "conversation_id": 1, "contact_id": 1}
    ).to_list(5000)
    if not leads:
        return [], {}

    conv_ids = [l.get("conversation_id") for l in leads if l.get("conversation_id")]
    replied = set()
    if conv_ids:
        replied = set(await db.messages.distinct(
            "conversation_id",
            {"conversation_id": {"$in": conv_ids}, "direction": "inbound"}
        ))
    contact_oids = []
    for l in leads:
        try:
            contact_oids.append(ObjectId(l.get("contact_id")))
        except Exception:
            pass
    sold = set()
    if contact_oids:
        async for c in db.contacts.find(
            {"_id": {"$in": contact_oids}, "date_sold": {"$nin": [None, ""]}}, {"_id": 1}
        ):
            sold.add(str(c["_id"]))

    cost_by_name = {}
    async for src in db.lead_sources.find({"monthly_cost": {"$gt": 0}}, {"name": 1, "monthly_cost": 1}):
        cost_by_name[src.get("name", "")] = float(src["monthly_cost"])

    by: dict = {}
    for l in leads:
        key = l.get("source_name") or "Unknown"
        s = by.setdefault(key, {"source": key, "leads": 0, "replied": 0, "sold": 0})
        s["leads"] += 1
        if l.get("conversation_id") in replied:
            s["replied"] += 1
        if l.get("contact_id") in sold:
            s["sold"] += 1

    rows = []
    for s in by.values():
        cost = cost_by_name.get(s["source"])
        s["cost"] = cost
        s["cost_per_lead"] = round(cost / s["leads"], 2) if cost and s["leads"] else None
        s["cost_per_sale"] = round(cost / s["sold"], 2) if cost and s["sold"] else None
        rows.append(s)
    rows.sort(key=lambda x: x["leads"], reverse=True)

    totals = {
        "leads":   sum(r["leads"] for r in rows),
        "replied": sum(r["replied"] for r in rows),
        "sold":    sum(r["sold"] for r in rows),
        "cost":    round(sum(r["cost"] or 0 for r in rows), 2),
    }
    return rows, totals


def _build_roi_email_html(store_name: str, month_label: str, rows: list, totals: dict) -> str:
    def money(v):
        return f"${v:,.0f}" if v is not None else "—"

    body_rows = ""
    for r in rows:
        body_rows += f"""
        <tr>
            <td style="padding:10px 12px;border-bottom:1px solid #eee;font-size:14px;color:#1a1a1a;font-weight:600;">{r['source']}</td>
            <td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:center;font-size:14px;">{r['leads']}</td>
            <td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:center;font-size:14px;color:#007AFF;">{r['replied']}</td>
            <td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:center;font-size:14px;color:#34C759;font-weight:700;">{r['sold']}</td>
            <td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:right;font-size:14px;">{money(r['cost'])}</td>
            <td style="padding:10px 8px;border-bottom:1px solid #eee;text-align:right;font-size:13px;color:#555;">{money(r['cost_per_lead'])}</td>
            <td style="padding:10px 12px;border-bottom:1px solid #eee;text-align:right;font-size:13px;color:#555;">{money(r['cost_per_sale'])}</td>
        </tr>"""

    return f"""
    <div style="font-family:-apple-system,Arial,sans-serif;max-width:640px;margin:0 auto;padding:24px;">
        <h2 style="color:#1a1a1a;margin-bottom:2px;">Lead Source ROI — {month_label}</h2>
        <p style="color:#555;margin-top:0;">{store_name}</p>
        <div style="display:flex;gap:10px;margin:16px 0;">
            <div style="flex:1;background:#f5f5f7;border-radius:10px;padding:14px;text-align:center;">
                <div style="font-size:22px;font-weight:800;color:#AF52DE;">{totals.get('leads', 0)}</div>
                <div style="font-size:11px;color:#888;letter-spacing:0.5px;">LEADS</div>
            </div>
            <div style="flex:1;background:#f5f5f7;border-radius:10px;padding:14px;text-align:center;">
                <div style="font-size:22px;font-weight:800;color:#34C759;">{totals.get('sold', 0)}</div>
                <div style="font-size:11px;color:#888;letter-spacing:0.5px;">SOLD</div>
            </div>
            <div style="flex:1;background:#f5f5f7;border-radius:10px;padding:14px;text-align:center;">
                <div style="font-size:22px;font-weight:800;color:#1a1a1a;">${totals.get('cost', 0):,.0f}</div>
                <div style="font-size:11px;color:#888;letter-spacing:0.5px;">SPENT</div>
            </div>
        </div>
        <table style="width:100%;border-collapse:collapse;background:#fafafa;border-radius:10px;">
            <tr>
                <th style="padding:8px 12px;text-align:left;font-size:11px;color:#888;letter-spacing:0.5px;">SOURCE</th>
                <th style="padding:8px;font-size:11px;color:#888;">LEADS</th>
                <th style="padding:8px;font-size:11px;color:#888;">REPLIED</th>
                <th style="padding:8px;font-size:11px;color:#888;">SOLD</th>
                <th style="padding:8px;text-align:right;font-size:11px;color:#888;">SPENT</th>
                <th style="padding:8px;text-align:right;font-size:11px;color:#888;">$/LEAD</th>
                <th style="padding:8px 12px;text-align:right;font-size:11px;color:#888;">$/SALE</th>
            </tr>{body_rows}
        </table>
        <p style="color:#888;font-size:12px;margin-top:20px;">Set monthly costs per source in Admin &rarr; Lead Sources. Full funnel in the app &rarr; Internet Leads &rarr; Source ROI.</p>
    </div>
    """


async def send_monthly_roi_email(start: Optional[datetime] = None,
                                  end: Optional[datetime] = None,
                                  label: Optional[str] = None) -> dict:
    """1st-of-month: email each store what every lead source cost vs returned.
    Recipient = store.roi_report_email, falling back to the super admin default."""
    db = get_db()
    resend_key = os.environ.get("RESEND_API_KEY")
    if not resend_key:
        logger.info("[ROI Email] skipped — no RESEND_API_KEY")
        return {"sent": 0, "reason": "no_api_key"}

    now = datetime.now(timezone.utc)
    if not (start and end):
        end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start = (end - timedelta(days=1)).replace(day=1)
    month_label = label or start.strftime("%B %Y")

    store_ids = await db.inbound_leads.distinct(
        "store_id", {"received_at": {"$gte": start, "$lt": end}}
    )
    if not store_ids:
        logger.info(f"[ROI Email] no leads for {month_label} — nothing to send")
        return {"sent": 0, "reason": "no_leads", "month": month_label}

    import resend
    resend.api_key = resend_key
    sender = os.environ.get("SENDER_EMAIL", "notifications@send.imonsocial.com")

    sent, recipients = 0, []
    for sid in store_ids:
        rows, totals = await _compute_roi_rows(db, sid, start, end)
        if not rows:
            continue
        store = {}
        if sid:
            try:
                store = await db.stores.find_one(
                    {"_id": ObjectId(sid)}, {"name": 1, "roi_report_email": 1}
                ) or {}
            except Exception:
                pass
        recipient = (store.get("roi_report_email") or "").strip() or _DEFAULT_ROI_RECIPIENT
        store_name = store.get("name") or "All Stores"
        html = _build_roi_email_html(store_name, month_label, rows, totals)
        try:
            await asyncio.to_thread(resend.Emails.send, {
                "from": f"I'm On Social <{sender}>",
                "to": recipient,
                "subject": f"Lead Source ROI — {month_label} ({store_name})",
                "html": html,
            })
            sent += 1
            recipients.append(recipient)
            logger.info(f"[ROI Email] sent {month_label} report for '{store_name}' to {recipient}")
        except Exception as e:
            logger.warning(f"[ROI Email] send failed for store {sid}: {e}")

    return {"sent": sent, "month": month_label, "recipients": recipients}


@router.post("/analytics/roi-email-test")
async def roi_email_test(request: Request):
    """Admin utility: send the ROI report for the current month-to-date right now."""
    _require_auth(request)
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = await send_monthly_roi_email(
        start=start, end=now, label=f"{now.strftime('%B %Y')} (month to date)"
    )
    return result


# ── Slow-reply alerts ─────────────────────────────────────────────────────────

SLOW_REPLY_MINUTES = 15


async def send_slow_lead_alerts() -> dict:
    """Every 5 min: ping store managers when a new lead has sat 15+ minutes
    without a HUMAN rep reply. One alert per lead, daytime hours only."""
    import pytz
    db = get_db()
    now = datetime.utcnow()
    leads = await db.inbound_leads.find({
        "received_at": {"$gte": now - timedelta(hours=24), "$lte": now - timedelta(minutes=SLOW_REPLY_MINUTES)},
        "slow_alert_sent": {"$ne": True},
        "conversation_id": {"$nin": [None, ""]},
    }, {
        "conversation_id": 1, "received_at": 1, "full_name": 1, "store_id": 1,
        "source_name": 1, "vehicle_interest": 1, "assigned_to": 1,
    }).to_list(500)
    if not leads:
        return {"alerted": 0}

    first = await _first_human_replies(db, [l["conversation_id"] for l in leads])
    from routers.push_notifications import send_push_to_user

    alerted = 0
    for lead in leads:
        lead_id = lead["_id"]
        if lead["conversation_id"] in first:
            # A rep replied — never alert for this lead
            await db.inbound_leads.update_one({"_id": lead_id}, {"$set": {"slow_alert_sent": True}})
            continue

        # Daytime guard: hold overnight alerts until 8 AM local (assigned rep's tz, default Denver)
        tz_name = "America/Denver"
        try:
            if lead.get("assigned_to") and ObjectId.is_valid(str(lead["assigned_to"])):
                rep = await db.users.find_one({"_id": ObjectId(lead["assigned_to"])}, {"timezone": 1})
                tz_name = (rep or {}).get("timezone") or tz_name
            local_hour = datetime.now(pytz.timezone(tz_name)).hour
        except Exception:
            local_hour = 12
        if not (8 <= local_hour < 21):
            continue  # re-checked next run; fires once morning opens

        # Recipients: store managers/org admins of the lead's store, else super admins
        uids = []
        sid = lead.get("store_id")
        if sid:
            store_vals = [sid, ObjectId(sid)] if ObjectId.is_valid(str(sid)) else [sid]
            admins = await db.users.find(
                {"store_id": {"$in": store_vals}, "role": {"$in": ["store_manager", "org_admin"]}},
                {"_id": 1},
            ).to_list(20)
            uids = [str(a["_id"]) for a in admins]
        if not uids:
            supers = await db.users.find({"role": "super_admin"}, {"_id": 1}).to_list(5)
            uids = [str(a["_id"]) for a in supers]

        received = lead.get("received_at")
        if received and received.tzinfo:
            received = received.replace(tzinfo=None)
        mins = int((now - received).total_seconds() // 60) if received else SLOW_REPLY_MINUTES
        detail = lead.get("vehicle_interest") or lead.get("source_name") or "internet lead"
        title = f"Lead going cold: {lead.get('full_name') or 'New lead'}"
        body = f"{mins} min without a rep reply — {detail}. Jump in before it goes cold."

        for uid in uids:
            idem = f"slow_lead_{lead_id}_{uid}"
            r = await db.notifications.update_one(
                {"idempotency_key": idem},
                {"$setOnInsert": {
                    "user_id": uid,
                    "type": "slow_lead",
                    "title": title,
                    "message": body,
                    "link": "/leads",
                    "idempotency_key": idem,
                    "read": False,
                    "dismissed": False,
                    "created_at": datetime.now(timezone.utc),
                }},
                upsert=True,
            )
            if r.upserted_id:
                try:
                    await send_push_to_user(uid, f"⏱️ {title}", body, "/leads", "flame")
                except Exception:
                    pass

        await db.inbound_leads.update_one({"_id": lead_id}, {"$set": {"slow_alert_sent": True}})
        alerted += 1
        logger.info(f"[SlowLead] Alerted {len(uids)} manager(s): {title} ({mins}m)")

    return {"alerted": alerted, "checked": len(leads)}


@router.get("/{lead_id}")
async def get_lead(lead_id: str):
    """Get a specific inbound lead."""
    db = get_db()
    if not ObjectId.is_valid(lead_id):
        raise HTTPException(status_code=400, detail="Invalid lead ID")
    lead = await db.inbound_leads.find_one({"_id": ObjectId(lead_id)})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead["id"] = str(lead.pop("_id"))
    lead["scheduled_send_at"] = lead["scheduled_send_at"].isoformat() if isinstance(lead.get("scheduled_send_at"), datetime) else lead.get("scheduled_send_at")
    lead["received_at"]       = lead["received_at"].isoformat() if isinstance(lead.get("received_at"), datetime) else lead.get("received_at")
    return lead


@router.post("/{lead_id}/retry")
async def retry_lead(lead_id: str):
    """Re-queue a failed lead for sending."""
    db = get_db()
    if not ObjectId.is_valid(lead_id):
        raise HTTPException(status_code=400, detail="Invalid lead ID")
    lead = await db.inbound_leads.find_one({"_id": ObjectId(lead_id)})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    now = datetime.now(timezone.utc)
    await db.inbound_leads.update_one(
        {"_id": lead["_id"]},
        {"$set": {"status": "queued", "scheduled_send_at": now + timedelta(seconds=30), "error": None}}
    )
    return {"success": True, "message": "Lead re-queued"}



async def _get_on_shift_reps(user_ids: list, fallback_all: bool = True) -> list:
    """
    Filter user_ids to those currently on shift per their schedule.
    If none are on shift (or no schedules set), returns all user_ids so
    the lead is never silently dropped.
    """
    if not user_ids:
        return user_ids
    try:
        from routers.user_schedule import is_user_available
        on_shift = [uid for uid in user_ids if await is_user_available(uid)]
        if on_shift:
            logger.info(f"[SmartRoute] {len(on_shift)}/{len(user_ids)} reps on shift → routing to on-shift only")
            return on_shift
        # No one on shift — fall back so lead is never dropped
        logger.info(f"[SmartRoute] 0/{len(user_ids)} reps on shift → falling back to all reps")
        return user_ids if fallback_all else []
    except Exception as e:
        logger.warning(f"[SmartRoute] Schedule check failed (non-fatal): {e}")
        return user_ids   # safe fallback


async def _send_intake_sms(db, conv_id: str, to_phone: str, from_number: str, body: str) -> dict:
    """Send the intake text and log it on the thread. Returns the twilio_service result."""
    from services.twilio_service import send_sms
    result = await send_sms(to_phone, body, from_phone=from_number or None)
    if result.get("success"):
        now = datetime.now(timezone.utc)
        await db.messages.insert_one({
            "conversation_id": conv_id,
            "content":         body,
            "sender":          "ai",
            "direction":       "outbound",
            "channel":         "sms",
            "ai_generated":    True,
            "is_intake_text":  True,
            "mocked":          bool(result.get("mock")),
            "timestamp":       now,
        })
        await db.conversations.update_one({"_id": ObjectId(conv_id)}, {"$set": {"last_message_at": now}})
        logger.info(f"[IntakeWorkflow] Intake text sent to {to_phone}")
    else:
        logger.warning(f"[IntakeWorkflow] Intake text send failed: {result.get('error')}")
    return result


async def process_lead_deferred_actions():
    """Scheduler (every 30s): release overnight intake texts once the customer's texting window
    opens. Staggered at plan time, so a pile of overnight leads trickles out one per minute."""
    db = get_db()
    now = datetime.now(timezone.utc)
    due = await db.lead_deferred_actions.find({"status": "pending", "run_at": {"$lte": now}}).sort("run_at", 1).to_list(25)
    for action in due:
        try:
            conv_id = action["conversation_id"]
            from services.lead_call_engine import _rep_already_engaged
            if await _rep_already_engaged(db, conv_id):
                await db.lead_deferred_actions.update_one({"_id": action["_id"]}, {"$set": {"status": "cancelled", "reason": "rep_replied", "updated_at": now}})
                continue
            result = await _send_intake_sms(db, conv_id, action["to"], action.get("from_number", ""), action["body"])
            await db.lead_deferred_actions.update_one(
                {"_id": action["_id"]},
                {"$set": {"status": "sent" if result.get("success") else "failed", "error": result.get("error"), "sent_at": now, "updated_at": now}},
            )
        except Exception as e:
            logger.warning(f"[IntakeWorkflow] Deferred action {action.get('_id')} failed: {e}")
            await db.lead_deferred_actions.update_one({"_id": action["_id"]}, {"$set": {"status": "failed", "error": str(e)[:300], "updated_at": now}})


def _local_clock(iso_utc: str, tz_name: str) -> str:
    """'9:05 AM' / 'Mon 9:05 AM' in the given zone, for rep-facing copy."""
    from services.lead_timing import parse_iso, _tz
    dt = parse_iso(iso_utc)
    if not dt:
        return ""
    local = dt.astimezone(_tz(tz_name))
    same_day = local.date() == datetime.now(timezone.utc).astimezone(_tz(tz_name)).date()
    return local.strftime("%-I:%M %p") if same_day else local.strftime("%a %-I:%M %p")


async def _fire_intake_workflow(source, lead_doc, conv_id, contact_id, phone_e164, normalized, db, now, plan=None):
    """
    Fires instantly when a lead arrives:
    1. Sends the instant intake text (with merge fields) if configured - or queues it for the
       customer's texting window (staggered) when the lead lands overnight
    2. Blasts all workflow reps with push + in-app notification
    3. Starts the Text + Call rep ladder (deferred to store opening under the after-hours rule)
    """
    try:
        plan = plan or {}
        source_name         = source.get("name", "Lead Source")
        intake_text         = source.get("intake_text", "").strip()
        workflow_user_ids   = source.get("workflow_user_ids", [])
        notify_all          = source.get("notify_all_on_intake", True)
        store_tz            = plan.get("store_tz") or "America/Denver"
        # Returning customer already routed to their own rep: no jump-ball blast, no ladder
        if lead_doc.get("routing_kind") == "returning_owner":
            notify_all = False
            source = {**source, "contact_mode": "text_only"}

        # ── 1. Send instant intake text ──────────────────────────────────────
        if intake_text and phone_e164:
            from routers.lead_sources import hydrate_intake_text
            lead_data = {
                "first_name":    normalized.get("first_name", ""),
                "last_name":     normalized.get("last_name", ""),
                "full_name":     normalized.get("full_name", ""),
                "vehicle_interest": normalized.get("vehicle_interest", ""),
                "vehicle_year":  normalized.get("vehicle_year", ""),
                "vehicle_make":  normalized.get("vehicle_make", ""),
                "vehicle_model": normalized.get("vehicle_model", ""),
                "phone":         phone_e164,
            }
            message_body = hydrate_intake_text(intake_text, lead_data, source_name)

            # Send from the assigned rep's business number so the customer's reply lands in
            # this thread and that rep's inbox; otherwise the first on-shift workflow rep.
            from_number = None
            sender_ids = ([lead_doc.get("assigned_to")] if lead_doc.get("assigned_to") else []) + list(workflow_user_ids)
            if sender_ids:
                pool = await _get_on_shift_reps(sender_ids, fallback_all=True) if not lead_doc.get("assigned_to") else sender_ids
                for uid in pool:
                    try:
                        rep = await db.users.find_one({"_id": ObjectId(uid)}, {"twilio_number": 1, "mvpline_number": 1})
                    except Exception:
                        rep = None
                    from_number = (rep or {}).get("twilio_number") or (rep or {}).get("mvpline_number")
                    if from_number:
                        break

            if not from_number:
                from_number = os.environ.get("TWILIO_PHONE_NUMBER", "")

            if from_number and message_body:
                # rep_phone lets the Twilio webhook route the customer's reply into THIS thread
                await db.conversations.update_one({"_id": ObjectId(conv_id)}, {"$set": {"rep_phone": from_number}})
                if plan.get("intake_deferred"):
                    from services.lead_timing import parse_iso
                    await db.lead_deferred_actions.insert_one({
                        "kind": "intake_text", "conversation_id": conv_id, "contact_id": contact_id,
                        "source_id": str(source.get("_id", "")), "store_id": source.get("store_id"),
                        "to": phone_e164, "from_number": from_number, "body": message_body,
                        "run_at": parse_iso(plan["intake_at"]), "reason": plan.get("intake_reason"),
                        "status": "pending", "created_at": now,
                    })
                    logger.info(f"[IntakeWorkflow] Intake text for {phone_e164} held until {plan['intake_at']} ({plan.get('intake_reason')})")
                else:
                    await _send_intake_sms(db, conv_id, phone_e164, from_number, message_body)

        # ── 2. Blast workflow reps with notification ──────────────────────────
        if notify_all and workflow_user_ids:
            full_name = normalized.get("full_name", "") or f"{normalized.get('first_name','')} {normalized.get('last_name','')}".strip() or "New Lead"
            vehicle   = normalized.get("vehicle_interest", "") or " ".join(filter(None, [normalized.get("vehicle_year"), normalized.get("vehicle_make"), normalized.get("vehicle_model")]))
            notif_title = f"New Lead: {full_name}"
            notif_body  = f"{source_name} | {vehicle}" if vehicle else source_name
            if plan.get("ladder_deferred") and source.get("contact_mode") == "text_and_call":
                when = _local_clock(plan.get("ladder_at"), store_tz)
                notif_body += f" | After hours: {'Jessi is replying, ' if plan.get('jessi_on') else ''}calls ring at {when}"
            elif plan.get("after_hours") and plan.get("jessi_on"):
                notif_body += " | After hours: Jessi is replying"
            if plan.get("intake_deferred"):
                notif_body += f" | Intake text goes out {_local_clock(plan.get('intake_at'), store_tz)}"
            app_url     = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))
            conv_link   = f"{app_url}/thread/{conv_id}"

            # Only notify reps currently on shift (falls back to all if none on shift)
            notif_recipients = await _get_on_shift_reps(workflow_user_ids)

            for uid in notif_recipients:
                try:
                    await db.notifications.insert_one({
                        "user_id":         uid,
                        "type":            "new_lead",
                        "priority":        "urgent",
                        "title":           notif_title,
                        "message":         notif_body,
                        "contact_id":      contact_id,
                        "conversation_id": conv_id,
                        "link":            conv_link,
                        "read":            False,
                        "dismissed":       False,
                        "created_at":      now,
                    })
                    # Push notification
                    try:
                        from routers.push_notifications import send_push_to_user, LEAD_SOUND, LEAD_CHANNEL
                        import asyncio as _aio2
                        _aio2.create_task(send_push_to_user(
                            uid, notif_title, f"{notif_body} — tap to claim",
                            conv_link, "flash", sound=LEAD_SOUND, channel_id=LEAD_CHANNEL
                        ))
                    except Exception:
                        pass

                    # SMS to rep's personal phone
                    rep = await db.users.find_one(
                        {"_id": ObjectId(uid)},
                        {"phone": 1, "twilio_number": 1, "mvpline_number": 1, "name": 1, "notification_settings": 1}
                    )
                    rep_phone  = (rep or {}).get("phone", "").strip()
                    rep_twilio = (rep or {}).get("twilio_number") or (rep or {}).get("mvpline_number", "")
                    notif_prefs = (rep or {}).get("notification_settings", {})
                    sms_enabled = notif_prefs.get("sms_active_conversation", True)

                    if rep_phone and rep_twilio and sms_enabled:
                        try:
                            from twilio.rest import Client as _TC2
                            tw_sid   = os.environ.get("TWILIO_ACCOUNT_SID", "")
                            tw_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
                            if tw_sid and tw_token:
                                sms_body = (
                                    f"I'm On Social: New Lead! {full_name}"
                                    + (f" — {vehicle}" if vehicle else "")
                                    + f"\n\nSource: {source_name}"
                                    + f"\n\nClaim it: {conv_link}"
                                )
                                import asyncio as _aio3
                                async def _sms(to=rep_phone, frm=rep_twilio, body=sms_body, sid=tw_sid, tok=tw_token):
                                    try:
                                        _TC2(sid, tok).messages.create(to=to, from_=frm, body=body)
                                    except Exception as _e:
                                        logger.debug(f"[IntakeWorkflow] Rep SMS failed: {_e}")
                                _aio3.create_task(_sms())
                        except Exception:
                            pass
                except Exception as notif_err:
                    logger.debug(f"[IntakeWorkflow] Notification failed for {uid}: {notif_err}")

        # ── 3. Text + Call: start the CallDrip-style rep dialing ladder ──────
        if source.get("contact_mode") == "text_and_call" and phone_e164:
            try:
                from services.lead_call_engine import start_call_workflow
                from services.lead_timing import parse_iso
                attribution = normalized.get("attribution") or {}
                lead_summary = {
                    "name":         normalized.get("full_name") or f"{normalized.get('first_name','')} {normalized.get('last_name','')}".strip(),
                    "source_label": attribution.get("source_label") or source_name,
                    "company":      normalized.get("company", ""),
                    "industry":     normalized.get("industry", ""),
                    "interest":     normalized.get("vehicle_interest", ""),
                    "comments":     normalized.get("comments", ""),
                }
                await start_call_workflow(
                    source=source, conversation_id=conv_id, contact_id=contact_id,
                    customer_phone=phone_e164, lead=lead_summary,
                    assigned_user_id=lead_doc.get("assigned_to"),
                    not_before=parse_iso(plan.get("ladder_at")) if plan.get("ladder_deferred") else None,
                    deferred_reasons=plan.get("ladder_reasons") or [],
                )
            except Exception as call_err:
                logger.warning(f"[IntakeWorkflow] Call engine start failed: {call_err}")

        logger.info(f"[IntakeWorkflow] Complete for {phone_e164} | reps_notified={len(notif_recipients if notify_all and workflow_user_ids else workflow_user_ids)}/{len(workflow_user_ids)}")
    except Exception as e:
        logger.warning(f"[IntakeWorkflow] Workflow fire failed: {e}")



@router.post("/test-adf")
async def test_adf_parse(request: Request):
    """Dev/admin utility: parse and preview an ADF XML body without saving."""
    body = await request.body()
    body_str = body.decode("utf-8", errors="replace")
    try:
        normalized = parse_adf_xml(body_str)
        return {"success": True, "normalized": normalized}
    except ValueError as e:
        return {"success": False, "error": str(e)}
