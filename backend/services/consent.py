"""Contact texting consent, per organization and phone number, in three scopes: requested_info, transactional, marketing.
`consent_records` is the append-only audit history (who, how, which statement, evidence); `consent_state` holds the current
status per (organization, phone, scope). No record means UNKNOWN: nobody is opted in by default. A STOP is never undone here:
only the contact texting START lifts it (services/suppression.py)."""
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId

logger = logging.getLogger(__name__)

RECORDS = "consent_records"
STATE = "consent_state"
INBOUND = "sms_inbound_index"
SCOPES = ("requested_info", "transactional", "marketing")
SCOPE_LABELS = {"requested_info": "Requested information", "transactional": "Transactional updates", "marketing": "Marketing"}
METHODS = {
    "verbal_in_person": {"label": "Verbal, in person", "scopes": {"requested_info", "transactional"}},
    "written_signature": {"label": "Signed or written form", "scopes": set(SCOPES), "evidence": True},
    "web_form": {"label": "Online form completed by the contact", "scopes": set(SCOPES)},
    "text_keyword": {"label": "Contact texted a sign-up keyword", "scopes": set(SCOPES)},
    "lead_inquiry": {"label": "Contact submitted an inquiry", "scopes": {"requested_info"}},
    "import_documented": {"label": "Imported with documented evidence", "scopes": set(SCOPES), "evidence": True},
}
STATEMENT_VERSION = "2026-06-v1"
STATEMENTS = {
    "requested_info": "{business} may text me the information I ask for, such as photos, documents, quotes, estimates or receipts. "
                      "Msg & data rates may apply. Reply STOP to opt out.",
    "transactional": "{business} may text me updates about my purchase, delivery, service or appointments. "
                     "Msg & data rates may apply. Reply STOP to opt out.",
    "marketing": "I agree to receive recurring marketing and promotional texts from {business} at this number. Consent is not a "
                 "condition of purchase. Msg frequency varies. Msg & data rates may apply. Reply HELP for help, STOP to opt out.",
}
CONTACT_PURPOSES = {"conversational": ("requested_info", "transactional"), "requested_info": ("requested_info",),
                    "transactional": ("transactional",), "marketing": ("marketing",)}
DEFAULT_REPLY_WINDOW_DAYS = 30


class ConsentError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def e164(phone: str) -> str:
    from services.twilio_service import normalize_phone
    return normalize_phone(phone or "") if re.sub(r"\D", "", phone or "") else ""


def _key(org_id: str, phone: str, scope: str) -> str:
    return f"{org_id}:{phone}:{scope}"


def solo_scope(user_id: Optional[str]) -> str:
    """Consent owner for a team member with no organization (an individual account): their own user scope."""
    return f"user:{user_id}" if user_id else "platform"


def statements(business: str) -> dict:
    name = (business or "").strip() or "This business"
    return {"version": STATEMENT_VERSION, "scopes": {s: {"label": SCOPE_LABELS[s], "text": STATEMENTS[s].format(business=name)} for s in SCOPES},
            "methods": {k: {"label": v["label"], "scopes": sorted(v["scopes"]), "evidence_required": bool(v.get("evidence"))} for k, v in METHODS.items()}}


async def policy(db) -> dict:
    doc = await db.settings.find_one({"key": "consent_policy"}, {"_id": 0}) or {}
    return {"reply_window_days": int(doc.get("reply_window_days") or DEFAULT_REPLY_WINDOW_DAYS)}


def validate(scopes: list, method: str, evidence: Optional[dict]) -> list:
    """Raises ConsentError when the method cannot authorize a scope (verbal never authorizes marketing)."""
    scopes = [s for s in dict.fromkeys(scopes or []) if s]
    if not scopes:
        raise ConsentError("no_scope", "Pick at least one kind of message.")
    bad = [s for s in scopes if s not in SCOPES]
    if bad:
        raise ConsentError("bad_scope", f"Unknown consent scope: {bad[0]}")
    m = METHODS.get(method or "")
    if not m:
        raise ConsentError("bad_method", "Unknown consent method.")
    for s in scopes:
        if s not in m["scopes"]:
            if s == "marketing":
                raise ConsentError("marketing_needs_written", "Marketing texts need written or digital opt-in (a signed form, the online opt-in form, or a texted keyword). A verbal OK is not enough.")
            raise ConsentError("method_not_allowed", f"{m['label']} cannot authorize {SCOPE_LABELS[s].lower()}.")
    ev = evidence or {}
    if m.get("evidence") and not (str(ev.get("reference") or "").strip() or str(ev.get("file_url") or "").strip()):
        raise ConsentError("evidence_required", "Add the evidence: a form reference or a photo/file of the signed form.")
    return scopes


async def record(db, *, org_id: str, phone: str, scopes: list, method: str, source: str, location_id: Optional[str] = None,
                 contact_id: Optional[str] = None, captured_by: Optional[dict] = None, evidence: Optional[dict] = None,
                 business: str = "", ip: str = "", user_agent: str = "", statement_version: str = STATEMENT_VERSION) -> list:
    """Grant consent for each scope. Refused while the number is opted out (STOP) for this organization."""
    from services import suppression
    phone = e164(phone)
    if not org_id or not phone:
        raise ConsentError("no_target", "A phone number and organization are required.")
    scopes = validate(scopes, method, evidence)
    if await suppression.active(db, phone, org_id):
        raise ConsentError("opted_out", "This contact texted STOP. Only they can turn texts back on, by texting START to your number.")
    now = _now()
    by = {"user_id": str(captured_by["_id"]), "name": captured_by.get("name") or captured_by.get("email") or ""} if captured_by else None
    out = []
    for s in scopes:
        rec = {"org_id": str(org_id), "location_id": location_id, "contact_id": contact_id, "phone": phone, "scope": s, "action": "granted",
               "method": method, "source": source, "statement_version": statement_version,
               "statement_text": STATEMENTS[s].format(business=(business or "This business").strip()), "evidence": evidence or {},
               "captured_by": by, "ip": ip or None, "user_agent": (user_agent or "")[:300] or None, "at": now}
        rid = (await db[RECORDS].insert_one(rec)).inserted_id
        await db[STATE].update_one({"_id": _key(org_id, phone, s)}, {"$set": {
            "org_id": str(org_id), "phone": phone, "scope": s, "status": "granted", "method": method, "at": now, "record_id": str(rid),
            "contact_id": contact_id, "location_id": location_id, "captured_by": by, "statement_version": statement_version}}, upsert=True)
        out.append({"scope": s, "record_id": str(rid)})
    return out


async def revoke(db, *, org_id: str, phone: str, scopes: list, source: str, by: Optional[dict] = None, reason: str = "",
                 contact_id: Optional[str] = None) -> int:
    phone = e164(phone)
    now = _now()
    n = 0
    for s in [s for s in scopes if s in SCOPES]:
        await db[RECORDS].insert_one({"org_id": str(org_id), "contact_id": contact_id, "phone": phone, "scope": s, "action": "revoked", "source": source,
                                      "reason": reason[:300], "captured_by": {"user_id": str(by["_id"]), "name": by.get("name") or ""} if by else None, "at": now})
        r = await db[STATE].update_one({"_id": _key(org_id, phone, s), "status": "granted"}, {"$set": {"status": "revoked", "at": now, "revoked_source": source}})
        n += r.modified_count
    return n


async def state(db, org_id: str, phone: str) -> dict:
    phone = e164(phone)
    rows = {r["scope"]: r async for r in db[STATE].find({"org_id": str(org_id), "phone": phone})} if phone else {}
    out = {}
    for s in SCOPES:
        r = rows.get(s)
        out[s] = {"status": r["status"], "method": r.get("method"), "at": r["at"].isoformat() if isinstance(r.get("at"), datetime) else r.get("at"),
                  "captured_by": (r.get("captured_by") or {}).get("name")} if r else {"status": "unknown"}
    return out


async def history(db, org_id: str, phone: str, limit: int = 100) -> list:
    rows = await db[RECORDS].find({"org_id": str(org_id), "phone": e164(phone)}, {"_id": 0}).sort("at", -1).to_list(limit)
    for r in rows:
        if isinstance(r.get("at"), datetime):
            r["at"] = r["at"].isoformat()
    return rows


async def note_inbound(db, org_id: Optional[str], phone: str, to_number: str, message_sid: str) -> None:
    """A text from the contact: evidence the conversation is customer-initiated (never treated as marketing consent)."""
    phone = e164(phone)
    if not org_id or not phone:
        return
    now = _now()
    await db[INBOUND].update_one({"_id": f"{org_id}:{phone}"}, {"$set": {"last_at": now, "last_to": to_number, "last_sid": message_sid},
                                                                "$setOnInsert": {"org_id": str(org_id), "phone": phone, "first_at": now}}, upsert=True)


async def _org_user_ids(db, org_id: str) -> list:
    if str(org_id).startswith("user:"):
        return [str(org_id)[5:]]
    return [str(u["_id"]) async for u in db.users.find({"organization_id": str(org_id)}, {"_id": 1})]


async def last_inbound(db, org_id: str, phone: str) -> Optional[datetime]:
    """When this contact last texted the organization: the inbound index, else the message history (pre-index threads)."""
    doc = await db[INBOUND].find_one({"_id": f"{org_id}:{phone}"}, {"last_at": 1})
    if doc:
        return doc["last_at"].replace(tzinfo=timezone.utc) if doc["last_at"].tzinfo is None else doc["last_at"]
    from services.contact_match import phone_clause
    uids = await _org_user_ids(db, org_id)
    pc = phone_clause(phone, "contact_phone")
    if not uids or not pc:
        return None
    conv_ids = [str(c["_id"]) async for c in db.conversations.find({"user_id": {"$in": uids}, **pc}, {"_id": 1}).limit(20)]
    if not conv_ids:
        return None
    m = await db.messages.find_one({"conversation_id": {"$in": conv_ids}, "sender": "contact"}, {"timestamp": 1}, sort=[("timestamp", -1)])
    ts = (m or {}).get("timestamp")
    if isinstance(ts, datetime):
        return ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts
    return None


async def eligible(db, org_id: str, phone: str, purpose: str) -> dict:
    """{ok, basis, needs}: may this organization send a `purpose` text to this phone? Marketing needs marketing consent only;
    the others accept their own scope, or a recent text from the contact (a reply to a customer-initiated conversation)."""
    phone = e164(phone)
    scopes = CONTACT_PURPOSES.get(purpose) or CONTACT_PURPOSES["conversational"]
    granted = {r["scope"] async for r in db[STATE].find({"org_id": str(org_id), "phone": phone, "status": "granted", "scope": {"$in": list(scopes)}}, {"scope": 1})}
    if granted:
        return {"ok": True, "basis": f"consent:{sorted(granted)[0]}", "needs": []}
    if purpose != "marketing":
        days = (await policy(db))["reply_window_days"]
        last = await last_inbound(db, org_id, phone)
        if last and last >= _now() - timedelta(days=days):
            return {"ok": True, "basis": "customer_initiated", "needs": []}
    return {"ok": False, "basis": "unknown", "needs": list(scopes)}


async def org_for_contact(db, contact: dict) -> tuple[Optional[str], Optional[str]]:
    """(organization_id, location_id) of the contact's owner."""
    uid = contact.get("user_id")
    if uid and ObjectId.is_valid(str(uid)):
        u = await db.users.find_one({"_id": ObjectId(str(uid))}, {"organization_id": 1, "store_id": 1})
        if u:
            return (str(u["organization_id"]) if u.get("organization_id") else None), (str(u["store_id"]) if u.get("store_id") else None)
    return None, None


async def migration_report(db, org_id: Optional[str] = None) -> dict:
    """Controlled migration, step 1 (read-only): contacts per organization by documented consent, opt-out and recent inbound."""
    q = {"organization_id": org_id} if org_id else {}
    out = []
    async for org in db.organizations.find(q, {"name": 1}).limit(500):
        oid = str(org["_id"])
        uids = await _org_user_ids(db, oid)
        total = await db.contacts.count_documents({"user_id": {"$in": uids}, "phone": {"$nin": [None, ""]}}) if uids else 0
        if not total:
            continue
        by_scope = {s: await db[STATE].count_documents({"org_id": oid, "scope": s, "status": "granted"}) for s in SCOPES}
        opted = await db.contacts.count_documents({"user_id": {"$in": uids}, "$or": [{"opted_out": True}, {"sms_opt_out": True}]})
        legacy_form = await db.contacts.count_documents({"user_id": {"$in": uids}, "sms_consent": True})
        inbound = await db[INBOUND].count_documents({"org_id": oid})
        out.append({"organization_id": oid, "name": org.get("name"), "contacts_with_phone": total, "granted": by_scope, "opted_out": opted,
                    "legacy_lead_form_opt_in": legacy_form, "customer_initiated_indexed": inbound,
                    "unknown_estimate": max(0, total - max(by_scope.values() or [0]) - opted)})
    return {"organizations": out, "statement_version": STATEMENT_VERSION}


async def migrate_legacy_form_opt_ins(db, org_id: str, actor: dict, apply: bool = False) -> dict:
    """Controlled migration, step 2: contacts whose lead form recorded an SMS opt-in get requested_info + transactional consent
    (method web_form, evidence = the stored lead-form flag). Marketing is never inferred. Dry run unless apply=True."""
    uids = await _org_user_ids(db, org_id)
    rows = await db.contacts.find({"user_id": {"$in": uids}, "sms_consent": True, "phone": {"$nin": [None, ""]}},
                                  {"phone": 1, "sms_consent_at": 1, "sms_consent_source": 1, "user_id": 1}).to_list(20000) if uids else []
    done = skipped = 0
    for c in rows:
        phone = e164(c["phone"])
        have = await db[STATE].count_documents({"org_id": org_id, "phone": phone, "status": "granted", "scope": {"$in": ["requested_info", "transactional"]}})
        if have >= 2 or not phone:
            skipped += 1
            continue
        if apply:
            try:
                await record(db, org_id=org_id, phone=phone, scopes=["requested_info", "transactional"], method="web_form", source="migration_lead_form",
                             contact_id=str(c["_id"]), captured_by=actor,
                             evidence={"legacy_field": "contacts.sms_consent", "legacy_at": str(c.get("sms_consent_at") or ""), "legacy_source": c.get("sms_consent_source")})
                done += 1
            except ConsentError:
                skipped += 1
        else:
            done += 1
    return {"organization_id": org_id, "eligible": len(rows), "would_record" if not apply else "recorded": done, "skipped": skipped, "applied": apply}


async def backfill_inbound(db, org_id: str, apply: bool = False, days: int = 90) -> dict:
    """Controlled migration, step 3: index recent customer texts so replies to them count as customer-initiated."""
    uids = await _org_user_ids(db, org_id)
    since = _now() - timedelta(days=days)
    n = 0
    async for conv in db.conversations.find({"user_id": {"$in": uids}, "contact_phone": {"$nin": [None, ""]}}, {"contact_phone": 1, "rep_phone": 1}):
        m = await db.messages.find_one({"conversation_id": str(conv["_id"]), "sender": "contact", "timestamp": {"$gte": since.replace(tzinfo=None)}},
                                       {"timestamp": 1, "twilio_sid": 1}, sort=[("timestamp", -1)])
        if not m:
            continue
        n += 1
        if apply:
            phone = e164(conv["contact_phone"])
            ts = m["timestamp"].replace(tzinfo=timezone.utc) if m["timestamp"].tzinfo is None else m["timestamp"]
            await db[INBOUND].update_one({"_id": f"{org_id}:{phone}"}, {"$max": {"last_at": ts}, "$setOnInsert": {"org_id": org_id, "phone": phone, "first_at": ts,
                                                                                                                   "backfilled": True}}, upsert=True)
    return {"organization_id": org_id, "threads_with_recent_customer_text": n, "applied": apply}
