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
        "stock", "stock_number", "stocknumber", "stock_no",
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

    if existing_contact:
        contact_id = str(existing_contact["_id"])
        is_new_contact = False
    else:
        # Create contact
        contact_doc = {
            "first_name":    first,
            "last_name":     last,
            "phone":         phone_e164,
            "email":         email.lower().strip() if email else "",
            "city":          normalized.get("city", ""),
            "state":         normalized.get("state", ""),
            "zip":           normalized.get("zip_code", ""),
            "source":        "internet_lead",
            "ownership_type": "org",
            "status":        "active",
            "tags":          ["Internet Lead", normalized.get("source_name", source.get("name", "Lead"))],
            "notes":         normalized.get("comments", ""),
            "vehicle_interest": " ".join(filter(None, [
                normalized.get("vehicle_year"), normalized.get("vehicle_make"),
                normalized.get("vehicle_model"), normalized.get("vehicle_trim"),
            ])),
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
    assigned_user_id = await _resolve_assignment(db, source)
    assigned_user = None
    if assigned_user_id:
        try:
            assigned_user = await db.users.find_one({"_id": ObjectId(assigned_user_id)})
        except Exception:
            pass

    # ── Determine send time (after-hours logic)
    scheduled_send_at = calculate_send_time(store)
    is_immediate = (scheduled_send_at - now).total_seconds() < 120

    # ── Match vehicle of interest against live inventory
    matched_vehicle = await _match_lead_inventory(db, normalized, store_id)

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
        "extra_fields":      normalized.get("extra_fields", {}),
        "assigned_to":       assigned_user_id,
        "draft_message":     first_message,
        "scheduled_send_at": scheduled_send_at,
        "is_after_hours":    not is_immediate,
        "status":            "queued",   # queued → sent | failed
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
        "ai_mode":          "assist",
        "draft_message":    first_message,
        "is_internet_lead": True,
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

    # ── Fire Workflow Automation ───────────────────────────────────────────────
    # Sends instant intake text, blasts all workflow reps with push notifications
    asyncio.create_task(_fire_intake_workflow(
        source=source, lead_doc=lead_doc, conv_id=conv_id,
        contact_id=contact_id, phone_e164=phone_e164,
        normalized=normalized, db=db, now=now,
    ))

    logger.info(
        f"[LeadIntake] Lead received: {full_name} | {phone_e164} | "
        f"source={source.get('name')} | send_at={scheduled_send_at.isoformat()} | "
        f"after_hours={not is_immediate}"
    )

    return {
        "lead_id":        lead_id,
        "contact_id":     contact_id,
        "conversation_id": conv_id,
        "is_new_contact": is_new_contact,
        "draft_message":  first_message,
        "scheduled_send_at": scheduled_send_at.isoformat(),
        "is_after_hours":   not is_immediate,
        "assigned_to":      assigned_user_id,
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
                result = await send_sms(phone, message, from_phone=rep_twilio_num)
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

    return [
        {
            "id":             str(l["_id"]),
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

    sources = []
    for s in by_source.values():
        s["reply_rate"] = round(s["replied"] / s["leads"] * 100) if s["leads"] else 0
        s["sold_rate"] = round(s["sold"] / s["leads"] * 100) if s["leads"] else 0
        sources.append(s)
    sources.sort(key=lambda x: x["leads"], reverse=True)

    totals = {
        "leads": sum(s["leads"] for s in sources),
        "replied": sum(s["replied"] for s in sources),
        "sold": sum(s["sold"] for s in sources),
    }
    return {"days": days, "sources": sources, "totals": totals}


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


async def _fire_intake_workflow(source, lead_doc, conv_id, contact_id, phone_e164, normalized, db, now):
    """
    Fires instantly when a lead arrives:
    1. Sends the instant intake text (with merge fields) if configured
    2. Blasts all workflow reps with push + in-app notification
    """
    try:
        source_name         = source.get("name", "Lead Source")
        intake_text         = source.get("intake_text", "").strip()
        workflow_user_ids   = source.get("workflow_user_ids", [])
        notify_all          = source.get("notify_all_on_intake", True)

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

            # Find a Twilio number to send from — prefer first on-shift rep's number
            from_number = None
            if workflow_user_ids:
                # Get on-shift reps to pick a sender from
                sender_pool = await _get_on_shift_reps(workflow_user_ids, fallback_all=True)
                rep = await db.users.find_one(
                    {"_id": ObjectId(sender_pool[0])},
                    {"twilio_number": 1, "mvpline_number": 1}
                )
                from_number = (rep or {}).get("twilio_number") or (rep or {}).get("mvpline_number")

            if not from_number:
                from_number = os.environ.get("TWILIO_PHONE_NUMBER", "")

            if from_number and message_body:
                try:
                    import asyncio as _aio
                    from twilio.rest import Client as _TC
                    tw_sid   = os.environ.get("TWILIO_ACCOUNT_SID", "")
                    tw_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
                    if tw_sid and tw_token:
                        client = _TC(tw_sid, tw_token)
                        await _aio.to_thread(
                            client.messages.create,
                            to=phone_e164,
                            from_=from_number,
                            body=message_body,
                        )
                        # Save as a message in the conversation
                        await db.messages.insert_one({
                            "conversation_id": conv_id,
                            "content":         message_body,
                            "sender":          "ai",
                            "direction":       "outbound",
                            "channel":         "sms",
                            "ai_generated":    True,
                            "is_intake_text":  True,
                            "timestamp":       now,
                        })
                        logger.info(f"[IntakeWorkflow] Intake text sent to {phone_e164}")
                except Exception as send_err:
                    logger.warning(f"[IntakeWorkflow] Intake text send failed: {send_err}")

        # ── 2. Blast workflow reps with notification ──────────────────────────
        if notify_all and workflow_user_ids:
            full_name = normalized.get("full_name", "") or f"{normalized.get('first_name','')} {normalized.get('last_name','')}".strip() or "New Lead"
            vehicle   = normalized.get("vehicle_interest", "") or " ".join(filter(None, [normalized.get("vehicle_year"), normalized.get("vehicle_make"), normalized.get("vehicle_model")]))
            notif_title = f"New Lead: {full_name}"
            notif_body  = f"{source_name} | {vehicle}" if vehicle else source_name
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
                        from routers.push_notifications import send_push_to_user
                        import asyncio as _aio2
                        _aio2.create_task(send_push_to_user(
                            uid, notif_title, f"{notif_body} — tap to claim",
                            conv_link, "flash"
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
