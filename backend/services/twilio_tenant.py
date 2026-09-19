"""Per-organization Twilio record (organizations.twilio): subaccount, Messaging Service, compliance mirror, the
provisioning state machine and the audit log. IMOS is the source of truth, Twilio is infrastructure.
Secrets (subaccount auth tokens) are Fernet-encrypted at rest and never leave the backend."""
import asyncio
import base64
import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

KEY = "twilio"
AUDIT = "audit_logs"

NOT_STARTED, INFO_REQUIRED, SUBMITTED, PENDING, APPROVED, REJECTED, ACTION_REQUIRED = (
    "NOT_STARTED", "INFORMATION_REQUIRED", "SUBMITTED", "PENDING", "APPROVED", "REJECTED", "ACTION_REQUIRED")
STATUS_LABEL = {NOT_STARTED: "Not started", INFO_REQUIRED: "Information required", SUBMITTED: "Submitted",
                PENDING: "Pending", APPROVED: "Approved", REJECTED: "Rejected", ACTION_REQUIRED: "Action required"}
PROVISIONING_LABEL = {"NOT_STARTED": "Not provisioned", "IN_PROGRESS": "Provisioning", "INFORMATION_REQUIRED": "Information required",
                      "WAITING_APPROVAL": "Waiting on Twilio approval", "READY": "Messaging ready", "ERROR": "Needs attention"}
RESOURCES = ("subaccount", "compliance_profile", "a2p_brand", "a2p_campaign", "messaging_service", "phone_numbers")
RESOURCE_LABEL = {"subaccount": "Twilio subaccount", "compliance_profile": "Compliance profile", "a2p_brand": "A2P brand",
                  "a2p_campaign": "A2P campaign", "messaging_service": "Messaging Service", "phone_numbers": "Phone numbers"}


def _now():
    return datetime.now(timezone.utc)


def defaults() -> dict:
    return {
        "enabled": False,
        "subaccount_sid": "", "subaccount_friendly_name": "", "subaccount_status": "", "subaccount_auth_token_enc": "",
        "messaging_service_sid": "",
        "compliance_profile_sid": "", "compliance_profile_status": NOT_STARTED,
        "a2p_brand_sid": "", "a2p_brand_status": NOT_STARTED,
        "a2p_campaign_sid": "", "a2p_campaign_status": NOT_STARTED,
        "compliance_store_id": "",
        "provisioning_status": "NOT_STARTED", "provisioning_error": "", "provisioning_step": "",
        "last_synced_at": None, "provisioning_history": [], "messaging_ready": False,
    }


def record(org: dict) -> dict:
    return {**defaults(), **((org or {}).get(KEY) or {})}


# ── secrets ───────────────────────────────────────────────────────────────────
def _fernet() -> Fernet:
    secret = os.environ.get("TWILIO_TOKEN_KEY") or os.environ.get("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET is not set")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("twilio-subaccount:" + secret).encode()).digest()))


def encrypt(value: str) -> str:
    return _fernet().encrypt((value or "").encode()).decode()


def decrypt(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, Exception):
        return ""


# ── credentials / clients ─────────────────────────────────────────────────────
def parent_sid() -> str:
    return os.environ.get("TWILIO_ACCOUNT_SID", "") or ""


def parent_token() -> str:
    return os.environ.get("TWILIO_AUTH_TOKEN", "") or ""


def configured() -> bool:
    return bool(parent_sid() and parent_token())


def parent_client():
    from twilio.rest import Client
    return Client(parent_sid(), parent_token())


def creds_for_org(org: Optional[dict]) -> tuple[str, str]:
    """(account_sid, auth_token) that owns this org's resources: the subaccount when provisioned, else the parent."""
    t = (org or {}).get(KEY) or {}
    if t.get("subaccount_sid") and t.get("subaccount_auth_token_enc") and not t["subaccount_sid"].startswith("ACdry"):
        tok = decrypt(t["subaccount_auth_token_enc"])
        if tok:
            return t["subaccount_sid"], tok
    return parent_sid(), parent_token()


def client_for_org(org: Optional[dict]):
    from twilio.rest import Client
    sid, tok = creds_for_org(org)
    if not sid or not tok:
        return None
    return Client(sid, tok)


async def org_by_id(db, org_id) -> Optional[dict]:
    if not org_id or not ObjectId.is_valid(str(org_id)):
        return None
    return await db.organizations.find_one({"_id": ObjectId(str(org_id))})


async def org_for_store(db, store: Optional[dict]) -> Optional[dict]:
    return await org_by_id(db, (store or {}).get("organization_id"))


async def client_for_store(db, store: Optional[dict]):
    return client_for_org(await org_for_store(db, store))


async def org_by_account_sid(db, account_sid: str) -> Optional[dict]:
    if not account_sid or account_sid == parent_sid():
        return None
    return await db.organizations.find_one({f"{KEY}.subaccount_sid": account_sid})


async def token_for_account(db, account_sid: str) -> str:
    """Twilio signs a webhook with the auth token of the account that owns the number (the subaccount when there is one)."""
    if not account_sid or account_sid == parent_sid():
        return parent_token()
    org = await org_by_account_sid(db, account_sid)
    if org:
        return decrypt(((org.get(KEY) or {}).get("subaccount_auth_token_enc")) or "") or parent_token()
    return parent_token()


async def dry_run(db) -> bool:
    """One switch for every Twilio write: the compliance mode setting (dry_run default) or missing parent credentials."""
    from services.twilio_compliance import get_settings
    return (await get_settings(db))["mode"] == "dry_run" or not configured()


async def flags(db) -> dict:
    from services.twilio_compliance import SETTINGS_KEY
    doc = await db.settings.find_one({"key": SETTINGS_KEY}) or {}
    return {"enforce_ready": bool(doc.get("enforce_ready", False)), "auto_provision": bool(doc.get("auto_provision", False))}


async def set_flags(db, patch: dict, me: dict) -> dict:
    from services.twilio_compliance import SETTINGS_KEY
    sets = {"updated_at": _now(), "updated_by": str(me.get("_id"))}
    for k in ("enforce_ready", "auto_provision"):
        if k in patch:
            sets[k] = bool(patch[k])
    await db.settings.update_one({"key": SETTINGS_KEY}, {"$set": sets, "$setOnInsert": {"key": SETTINGS_KEY}}, upsert=True)
    return await flags(db)


# ── audit log ─────────────────────────────────────────────────────────────────
def _actor(actor) -> dict:
    if isinstance(actor, dict):
        return {"actor_id": str(actor.get("_id") or ""), "actor_name": actor.get("name") or actor.get("email") or "", "actor_role": actor.get("role") or ""}
    return {"actor_id": "", "actor_name": str(actor or "system"), "actor_role": "system"}


async def audit(db, *, action: str, actor=None, org_id=None, target: Optional[dict] = None, details: Optional[dict] = None, ok: bool = True, error: str = ""):
    doc = {"action": action, **_actor(actor), "organization_id": str(org_id) if org_id else None, "target": target or {},
           "details": details or {}, "ok": ok, "error": (error or "")[:600], "at": _now()}
    try:
        await db[AUDIT].insert_one(doc)
    except Exception as e:
        logger.warning(f"[Audit] write failed: {e}")


def audit_public(row: dict, full: bool) -> dict:
    d = {"id": str(row["_id"]), "action": row.get("action"), "actor_name": row.get("actor_name"), "actor_role": row.get("actor_role"),
         "organization_id": row.get("organization_id"), "ok": row.get("ok", True), "error": row.get("error") or "",
         "at": row["at"].isoformat() if isinstance(row.get("at"), datetime) else row.get("at"),
         "target": dict(row.get("target") or {}), "details": dict(row.get("details") or {})}
    if not full:
        for k in ("sid", "account_sid", "subaccount_sid", "messaging_service_sid"):
            d["target"].pop(k, None)
            d["details"].pop(k, None)
    return d


async def audit_list(db, org_id=None, limit: int = 50, full: bool = True) -> list:
    q = {"organization_id": str(org_id)} if org_id else {}
    rows = await db[AUDIT].find(q).sort("at", -1).to_list(limit)
    return [audit_public(r, full) for r in rows]


# ── record helpers ────────────────────────────────────────────────────────────
def _hist(rec: dict, step: str, status: str, note: str = "") -> list:
    h = list(rec.get("provisioning_history") or [])
    h.append({"at": _now(), "step": step, "status": status, "note": (note or "")[:400]})
    return h[-80:]


async def save(db, org_id, patch: dict):
    await db.organizations.update_one({"_id": ObjectId(str(org_id))}, {"$set": {f"{KEY}.{k}": v for k, v in patch.items()}})


def friendly_name(org: dict) -> str:
    return f"IMOS {(org.get('name') or 'Organization')[:40]} ({org['_id']})"


# ── subaccount ────────────────────────────────────────────────────────────────
async def provision_subaccount(db, org: dict, actor=None) -> dict:
    """Idempotent: keep the SID on file, else adopt a parent subaccount with our friendly name, else create one."""
    rec = record(org)
    if rec.get("subaccount_sid"):
        return rec
    name = friendly_name(org)
    if await dry_run(db):
        sid = "ACdry" + hashlib.sha1(name.encode()).hexdigest()[:29]
        tok, status, how = "dry-" + hashlib.sha1(("t" + name).encode()).hexdigest()[:28], "active", "dry_run"
    else:
        c = parent_client()
        existing = await asyncio.wait_for(asyncio.to_thread(lambda: c.api.v2010.accounts.list(friendly_name=name, limit=5)), 20)
        existing = [a for a in existing if a.sid != parent_sid() and a.status != "closed"]
        if existing:
            acc, how = existing[0], "adopted"
        else:
            acc, how = await asyncio.wait_for(asyncio.to_thread(c.api.v2010.accounts.create, friendly_name=name), 30), "created"
        sid, tok, status = acc.sid, acc.auth_token, acc.status
    patch = {"enabled": True, "subaccount_sid": sid, "subaccount_friendly_name": name, "subaccount_status": status,
             "subaccount_auth_token_enc": encrypt(tok), "subaccount_created_at": _now(),
             "provisioning_history": _hist(rec, "subaccount", how, sid)}
    await save(db, org["_id"], patch)
    await audit(db, action=f"subaccount_{how}", actor=actor, org_id=org["_id"], target={"subaccount_sid": sid, "friendly_name": name})
    rec.update(patch)
    return rec


async def sync_subaccount_status(db, org: dict, rec: dict) -> str:
    sid = rec.get("subaccount_sid") or ""
    if not sid or sid.startswith("ACdry") or not configured():
        return rec.get("subaccount_status") or ""
    try:
        acc = await asyncio.wait_for(asyncio.to_thread(parent_client().api.v2010.accounts(sid).fetch), 15)
        return acc.status or ""
    except Exception as e:
        logger.warning(f"[Tenant] subaccount status {sid}: {e}")
        return rec.get("subaccount_status") or ""


async def set_subaccount_status(db, org: dict, status: str, actor=None) -> dict:
    """suspended | active | closed (closed is final and frees nothing we still track)."""
    rec = record(org)
    sid = rec.get("subaccount_sid")
    if not sid:
        raise ValueError("This organization has no Twilio subaccount yet")
    if status not in ("active", "suspended", "closed"):
        raise ValueError("status must be active, suspended or closed")
    if not sid.startswith("ACdry") and configured():
        await asyncio.wait_for(asyncio.to_thread(parent_client().api.v2010.accounts(sid).update, status=status), 20)
    await save(db, org["_id"], {"subaccount_status": status, "provisioning_history": _hist(rec, "subaccount", status)})
    await audit(db, action=f"subaccount_{status}", actor=actor, org_id=org["_id"], target={"subaccount_sid": sid})
    rec["subaccount_status"] = status
    return rec


# ── compliance mirror ─────────────────────────────────────────────────────────
async def compliance_store(db, org: dict, rec: Optional[dict] = None) -> Optional[dict]:
    """The store whose stores.compliance record backs this organization: the pinned one, else the furthest along."""
    from services.twilio_compliance import STAGES
    rec = rec or record(org)
    pinned = rec.get("compliance_store_id")
    if pinned and ObjectId.is_valid(pinned):
        s = await db.stores.find_one({"_id": ObjectId(pinned), "organization_id": str(org["_id"])})
        if s:
            return s
    stores = await db.stores.find({"organization_id": str(org["_id"])}, {"name": 1, "compliance": 1, "phone": 1, "city": 1, "state": 1}).to_list(50)
    if not stores:
        return None
    stores.sort(key=lambda s: (-STAGES.index(((s.get("compliance") or {}).get("stage") or "draft")), str(s.get("name") or "")))
    return stores[0]


def compliance_statuses(store: Optional[dict]) -> dict:
    """7-value status for the profile / brand / campaign resources out of stores.compliance."""
    from services.twilio_compliance import STAGES, missing_fields
    c = (store or {}).get("compliance") or {}
    stage = c.get("stage") or "draft"
    st = c.get("status") or "not_started"
    idx = STAGES.index(stage) if stage in STAGES else 0
    has_data = any(str(v or "").strip() for v in (c.get("business") or {}).values()) if c else False

    def one(stages: tuple[str, ...]) -> tuple[str, str]:
        my = max(STAGES.index(s) for s in stages)
        first = min(STAGES.index(s) for s in stages)
        if stage == "complete" or idx > my:
            return APPROVED, "Approved by Twilio"
        if stage == "draft":
            if not has_data:
                return NOT_STARTED, "Compliance form not started"
            miss = missing_fields(c)
            return (INFO_REQUIRED, f"{len(miss)} field{'s' if len(miss) != 1 else ''} still needed") if miss else (INFO_REQUIRED, "Form complete, waiting for team review and submit")
        if first <= idx <= my:
            if st == "submitting":
                return SUBMITTED, "Submitted to Twilio"
            if st == "rejected":
                return REJECTED, c.get("error") or "Twilio rejected this step"
            if st == "error":
                return ACTION_REQUIRED, c.get("error") or "The last Twilio call failed"
            return PENDING, "In Twilio's review queue"
        return NOT_STARTED, "Starts after the previous step is approved"

    sids = c.get("sids") or {}
    prof, prof_why = one(("profile", "a2p"))
    brand, brand_why = one(("brand",))
    camp, camp_why = one(("campaign",))
    return {"compliance_profile": {"status": prof, "detail": prof_why, "sid": sids.get("customer_profile") or ""},
            "a2p_brand": {"status": brand, "detail": brand_why, "sid": sids.get("brand") or ""},
            "a2p_campaign": {"status": camp, "detail": camp_why, "sid": sids.get("campaign") or ""},
            "messaging_service_sid": sids.get("messaging_service") or "", "stage": stage, "store_status": st}


async def mirror_compliance(db, store: dict, rec_store: Optional[dict] = None) -> Optional[dict]:
    """Called after every compliance state change: copy SIDs + statuses onto the org record and recompute readiness."""
    org = await org_for_store(db, store)
    if not org:
        return None
    if rec_store is not None:
        store = {**store, "compliance": rec_store}
    rec = record(org)
    backing = await compliance_store(db, org, rec)
    if backing and str(backing["_id"]) != str(store["_id"]):
        store = backing
    return await _recompute(db, org, rec, store=store, create=False, actor="system")


# ── the state machine ─────────────────────────────────────────────────────────
async def _numbers_status(db, org: dict, rec: dict) -> tuple[str, str, list]:
    from services import phone_numbers as pn
    nums = [n for n in await pn.list_for_org(db, str(org["_id"])) if n["status"] != "RELEASED"]
    if not nums:
        return NOT_STARTED, "No phone numbers yet", nums
    ms = rec.get("messaging_service_sid") or ""
    attached = [n for n in nums if n.get("messaging_service_sid")]
    if ms and len(attached) < len(nums):
        return PENDING, f"{len(nums) - len(attached)} number{'s' if len(nums) - len(attached) != 1 else ''} not on the Messaging Service yet", nums
    if not ms:
        return PENDING, f"{len(nums)} number{'s' if len(nums) != 1 else ''}, waiting for the Messaging Service", nums
    return APPROVED, f"{len(nums)} number{'s' if len(nums) != 1 else ''} on the Messaging Service", nums


async def _recompute(db, org: dict, rec: dict, store: Optional[dict] = None, create: bool = False, actor=None) -> dict:
    """One idempotent pass. create=True is the admin's Provision button (may create the subaccount and attach numbers);
    create=False is a read-mostly sync. Never duplicates a Twilio resource: every step checks what is on file first."""
    from services import phone_numbers as pn
    org_id = str(org["_id"])
    patch: dict = {}
    started = rec.get("provisioning_status") != "NOT_STARTED" or create
    try:
        if create and not rec.get("subaccount_sid"):
            rec = await provision_subaccount(db, org, actor)
        if rec.get("subaccount_sid"):
            patch["subaccount_status"] = await sync_subaccount_status(db, org, rec)
        store = store or await compliance_store(db, org, rec)
        cs = compliance_statuses(store)
        patch.update({"compliance_store_id": str(store["_id"]) if store else "",
                      "compliance_profile_sid": cs["compliance_profile"]["sid"], "compliance_profile_status": cs["compliance_profile"]["status"],
                      "a2p_brand_sid": cs["a2p_brand"]["sid"], "a2p_brand_status": cs["a2p_brand"]["status"],
                      "a2p_campaign_sid": cs["a2p_campaign"]["sid"], "a2p_campaign_status": cs["a2p_campaign"]["status"]})
        if cs["messaging_service_sid"]:
            patch["messaging_service_sid"] = cs["messaging_service_sid"]
        rec = {**rec, **patch}
        if create and rec.get("messaging_service_sid"):
            for n in await pn.list_for_org(db, org_id):
                if n["status"] != "RELEASED" and not n.get("messaging_service_sid"):
                    await pn.attach_to_service(db, n, rec["messaging_service_sid"], org=org)
        num_status, num_why, nums = await _numbers_status(db, org, rec)
        ready = cs["a2p_campaign"]["status"] == APPROVED and bool(rec.get("messaging_service_sid")) and num_status == APPROVED \
            and (rec.get("subaccount_status") or "active") in ("active", "")
        patch["messaging_ready"] = ready
        if started:
            if ready:
                status, step, err = "READY", "complete", ""
            elif not store:
                status, step, err = "INFORMATION_REQUIRED", "compliance", "Add a location (store) to this organization first; the compliance form lives on it."
            elif cs["stage"] == "draft":
                status, step, err = "INFORMATION_REQUIRED", "compliance", f"Complete and submit the compliance form for {store.get('name') or 'the store'}: {cs['compliance_profile']['detail']}."
            elif cs["store_status"] in ("rejected", "error"):
                status, step, err = "ERROR", cs["stage"], (store.get("compliance") or {}).get("error") or "Twilio rejected the registration."
            elif cs["stage"] != "complete":
                status, step, err = "WAITING_APPROVAL", cs["stage"], ""
            elif num_status == NOT_STARTED:
                status, step, err = "INFORMATION_REQUIRED", "numbers", "Registration is approved. Add a phone number to finish."
            elif (rec.get("subaccount_status") or "active") not in ("active", ""):
                status, step, err = "ERROR", "subaccount", f"The Twilio subaccount is {rec.get('subaccount_status')}."
            else:
                status, step, err = "IN_PROGRESS", "numbers", num_why
            if (status, step) != (rec.get("provisioning_status"), rec.get("provisioning_step")):
                patch["provisioning_history"] = _hist(rec, step, status, err)
            patch.update({"provisioning_status": status, "provisioning_step": step, "provisioning_error": err})
    except Exception as e:
        msg = _friendly(e)
        patch.update({"provisioning_status": "ERROR", "provisioning_error": msg, "provisioning_history": _hist(rec, rec.get("provisioning_step") or "?", "ERROR", msg)})
        await audit(db, action="provisioning_error", actor=actor, org_id=org_id, ok=False, error=msg)
        logger.warning(f"[Tenant] provision {org_id}: {e}")
    patch["last_synced_at"] = _now()
    await save(db, org_id, patch)
    return {**rec, **patch}


def _friendly(e: Exception) -> str:
    s = str(e) or e.__class__.__name__
    low = s.lower()
    if "authenticate" in low or "20003" in low:
        return "Twilio rejected our credentials. Check TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN on the server."
    if "timed out" in low or "timeout" in low:
        return "Twilio did not answer in time. Try again in a minute."
    if "subaccount" in low and "limit" in low:
        return "Twilio refused a new subaccount (account limit). Ask Twilio support to raise the subaccount limit."
    return s[:400]


async def provision(db, org: dict, actor=None) -> dict:
    """Super admin pressed Provision Twilio (or auto-provision at signup)."""
    rec = record(org)
    if rec.get("provisioning_status") == "NOT_STARTED":
        await save(db, org["_id"], {"provisioning_status": "IN_PROGRESS", "provisioning_step": "subaccount", "provisioning_history": _hist(rec, "subaccount", "IN_PROGRESS", "provisioning started")})
        rec.update({"provisioning_status": "IN_PROGRESS", "provisioning_step": "subaccount"})
        await audit(db, action="provisioning_started", actor=actor, org_id=org["_id"])
    out = await _recompute(db, org, rec, create=True, actor=actor)
    await audit(db, action="provision_step", actor=actor, org_id=org["_id"], details={"status": out.get("provisioning_status"), "step": out.get("provisioning_step")}, ok=out.get("provisioning_status") != "ERROR", error=out.get("provisioning_error") or "")
    return out


async def sync(db, org: dict, actor=None) -> dict:
    return await _recompute(db, org, record(org), create=False, actor=actor)


async def sync_all(db) -> int:
    n = 0
    async for org in db.organizations.find({f"{KEY}.provisioning_status": {"$exists": True, "$ne": "NOT_STARTED"}}):
        try:
            await sync(db, org, actor="scheduler")
            n += 1
        except Exception as e:
            logger.warning(f"[Tenant] sync {org.get('_id')}: {e}")
    return n


# ── send gate ─────────────────────────────────────────────────────────────────
async def send_block_reason(db, from_phone: str) -> str:
    """When enforce_ready is on: numbers in the registry only text once their organization is MESSAGING READY."""
    if not from_phone:
        return ""
    fl = await flags(db)
    if not fl["enforce_ready"]:
        return ""
    from services import phone_numbers as pn
    num = await pn.by_phone(db, from_phone)
    if not num or not num.get("organization_id"):
        return ""
    org = await org_by_id(db, num["organization_id"])
    rec = record(org) if org else None
    if not rec or rec.get("messaging_ready"):
        return ""
    st = rec.get("a2p_campaign_status")
    what = {NOT_STARTED: "the A2P registration has not been submitted", INFO_REQUIRED: "the compliance form is incomplete",
            SUBMITTED: "campaign registration is still pending", PENDING: "campaign registration is still pending",
            REJECTED: "the campaign registration was rejected", ACTION_REQUIRED: "the registration needs attention"}.get(st, "messaging is not set up")
    return f"Texting is not active yet for {(org or {}).get('name') or 'this organization'}: {what}."


# ── views ─────────────────────────────────────────────────────────────────────
def _sanitize(rec: dict, full: bool) -> dict:
    out = {k: v for k, v in rec.items() if k != "subaccount_auth_token_enc"}
    out["has_subaccount_token"] = bool(rec.get("subaccount_auth_token_enc"))
    if not full:
        for k in ("subaccount_sid", "messaging_service_sid", "compliance_profile_sid", "a2p_brand_sid", "a2p_campaign_sid", "provisioning_history"):
            out.pop(k, None)
    for k in ("last_synced_at", "subaccount_created_at"):
        if isinstance(out.get(k), datetime):
            out[k] = out[k].isoformat()
    for h in out.get("provisioning_history") or []:
        if isinstance(h.get("at"), datetime):
            h["at"] = h["at"].isoformat()
    return out


def _sub_status(rec: dict) -> tuple[str, str]:
    sid = rec.get("subaccount_sid")
    if not sid:
        return NOT_STARTED, "Using the platform account until provisioned"
    st = rec.get("subaccount_status") or "active"
    if st == "active":
        return APPROVED, "Active" + (" (dry run)" if sid.startswith("ACdry") else "")
    return ACTION_REQUIRED, f"Subaccount is {st}"


async def view(db, org: dict, full: bool) -> dict:
    from services import phone_numbers as pn
    from services.twilio_compliance import summary as c_summary, get_settings
    rec = record(org)
    org_id = str(org["_id"])
    store = await compliance_store(db, org, rec)
    cs = compliance_statuses(store)
    num_status, num_why, nums = await _numbers_status(db, org, rec)
    sub, sub_why = _sub_status(rec)
    ms_sid = rec.get("messaging_service_sid") or cs["messaging_service_sid"]
    statuses = {
        "subaccount": {"status": sub, "detail": sub_why},
        "compliance_profile": {"status": cs["compliance_profile"]["status"], "detail": cs["compliance_profile"]["detail"]},
        "a2p_brand": {"status": cs["a2p_brand"]["status"], "detail": cs["a2p_brand"]["detail"]},
        "a2p_campaign": {"status": cs["a2p_campaign"]["status"], "detail": cs["a2p_campaign"]["detail"]},
        "messaging_service": {"status": APPROVED if ms_sid else NOT_STARTED, "detail": "Created with the campaign" if ms_sid else "Created when the brand is approved"},
        "phone_numbers": {"status": num_status, "detail": num_why},
    }
    for k, v in statuses.items():
        v["label"] = STATUS_LABEL[v["status"]]
        v["title"] = RESOURCE_LABEL[k]
        if full:
            v["sid"] = {"subaccount": rec.get("subaccount_sid"), "compliance_profile": cs["compliance_profile"]["sid"], "a2p_brand": cs["a2p_brand"]["sid"],
                        "a2p_campaign": cs["a2p_campaign"]["sid"], "messaging_service": ms_sid, "phone_numbers": ""}[k] or ""
    stores = await db.stores.find({"organization_id": org_id}, {"name": 1, "compliance": 1, "phone": 1, "city": 1, "state": 1}).sort("name", 1).to_list(100)
    people = await db.users.find({"organization_id": org_id, "status": {"$ne": "deactivated"}}, {"name": 1, "email": 1, "role": 1, "store_id": 1, "twilio_number": 1, "phone": 1}).sort("name", 1).to_list(500)
    store_names = {str(s["_id"]): s.get("name") for s in stores}
    settings = await get_settings(db)
    ready = rec.get("messaging_ready", False)
    prov = rec.get("provisioning_status") or "NOT_STARTED"
    next_action = rec.get("provisioning_error") or ("Ready. Reps on this organization can text." if ready else ("Press Provision Twilio to start." if prov == "NOT_STARTED" else PROVISIONING_LABEL.get(prov, prov)))
    return {
        "organization": {"id": org_id, "name": org.get("name"), "admin_phone": org.get("admin_phone"), "city": org.get("city"), "state": org.get("state")},
        "record": _sanitize(rec, full),
        "statuses": statuses,
        "messaging_ready": ready,
        "provisioning": {"status": prov, "label": PROVISIONING_LABEL.get(prov, prov), "step": rec.get("provisioning_step") or "", "error": rec.get("provisioning_error") or "",
                         "next_action": next_action, "history": _sanitize(rec, True)["provisioning_history"] if full else []},
        "compliance": [c_summary(s) for s in stores],
        "compliance_store_id": str(store["_id"]) if store else "",
        "numbers": nums,
        "locations": [{"id": str(s["_id"]), "name": s.get("name"), "phone": s.get("phone") or "", "city": s.get("city") or "", "state": s.get("state") or ""} for s in stores],
        "people": [{"id": str(u["_id"]), "name": u.get("name") or u.get("email"), "email": u.get("email"), "role": u.get("role"), "store_id": u.get("store_id"),
                    "store_name": store_names.get(str(u.get("store_id") or "")), "phone": u.get("phone") or "", "twilio_number": u.get("twilio_number") or ""} for u in people],
        "usage": await pn.usage_summary(db, org_id),
        "audit": await audit_list(db, org_id, limit=40 if full else 15, full=full),
        "settings": {"mode": settings["mode"], **(await flags(db))},
        "full": full,
        "webhooks": pn.webhooks() if full else None,
    }


async def overview(db) -> list:
    """Super admin list: every organization with its readiness in one line."""
    from services import phone_numbers as pn
    out = []
    counts = {}
    async for row in db[pn.COLL].aggregate([{"$match": {"status": {"$ne": "RELEASED"}}}, {"$group": {"_id": "$organization_id", "n": {"$sum": 1}}}]):
        counts[str(row["_id"])] = row["n"]
    async for org in db.organizations.find({}, {"name": 1, KEY: 1, "active": 1}).sort("name", 1):
        rec = record(org)
        out.append({"id": str(org["_id"]), "name": org.get("name"), "active": org.get("active", True), "messaging_ready": rec.get("messaging_ready", False),
                    "provisioning_status": rec.get("provisioning_status"), "provisioning_label": PROVISIONING_LABEL.get(rec.get("provisioning_status") or "NOT_STARTED"),
                    "has_subaccount": bool(rec.get("subaccount_sid")), "campaign_status": rec.get("a2p_campaign_status"), "numbers": counts.get(str(org["_id"]), 0),
                    "error": rec.get("provisioning_error") or ""})
    return out
