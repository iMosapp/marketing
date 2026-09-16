"""GoHighLevel (LeadConnector) API v2 client. One Private Integration Token per store (sub-account); OAuth can slot in later
by swapping `_token()`. Base https://services.leadconnectorhq.com, header Version 2021-07-28."""
import logging
import re
import secrets
from datetime import datetime, timezone
from typing import Optional

import httpx
from bson import ObjectId

logger = logging.getLogger(__name__)

BASE = "https://services.leadconnectorhq.com"
VERSION = "2021-07-28"
COLL = "ghl_connections"
PAGE = 100
MAX_IMPORT = 5000
TIMEOUT = 30.0


class GhlError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def _now():
    return datetime.now(timezone.utc)


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Version": VERSION, "Accept": "application/json", "Content-Type": "application/json"}


async def _req(method: str, path: str, token: str, params: Optional[dict] = None, json: Optional[dict] = None) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.request(method, f"{BASE}{path}", headers=_headers(token), params=params, json=json)
    if r.status_code >= 400:
        try:
            body = r.json()
            msg = body.get("message") or body.get("error") or r.text
            if isinstance(msg, list):
                msg = "; ".join(str(m) for m in msg)
        except Exception:
            msg = r.text
        raise GhlError(r.status_code, f"GoHighLevel {r.status_code}: {str(msg)[:300]}")
    try:
        return r.json() if r.content else {}
    except Exception:
        return {}


# ── connection ────────────────────────────────────────────────────────────────
def scope_key(store_id: Optional[str], user_id: str) -> str:
    return str(store_id) if store_id else f"user:{user_id}"


async def connection(db, key: str) -> Optional[dict]:
    return await db[COLL].find_one({"scope_key": key})


async def connection_for_campaign(db, c: dict) -> Optional[dict]:
    return await connection(db, scope_key(c.get("store_id"), str(c.get("created_by") or "")))


async def test_token(location_id: str, token: str) -> dict:
    data = await _req("GET", f"/locations/{location_id}", token)
    loc = data.get("location") or data
    return {"id": loc.get("id") or location_id, "name": loc.get("name") or "", "timezone": loc.get("timezone"), "email": loc.get("email")}


async def save_connection(db, key: str, store_id: Optional[str], me: dict, location_id: str, token: str, lead_source_id: Optional[str]) -> dict:
    info = await test_token(location_id, token)
    doc = {"scope_key": key, "store_id": store_id, "location_id": location_id, "token": token, "location_name": info["name"], "location_timezone": info.get("timezone"),
           "connected_by": str(me["_id"]), "connected_by_name": me.get("name"), "connected_at": _now(), "last_test_at": _now(), "ok": True, "error": None}
    if lead_source_id is not None:
        doc["lead_source_id"] = lead_source_id or None
    await db[COLL].update_one({"scope_key": key}, {"$set": doc, "$setOnInsert": {"webhook_key": secrets.token_urlsafe(18)}}, upsert=True)
    return await connection(db, key)


def serialize(conn: Optional[dict], app_url: str) -> dict:
    if not conn:
        return {"connected": False}
    tok = conn.get("token") or ""
    return {"connected": True, "id": str(conn["_id"]), "store_id": conn.get("store_id"), "location_id": conn.get("location_id"), "location_name": conn.get("location_name"),
            "token_hint": f"…{tok[-4:]}" if tok else "", "lead_source_id": conn.get("lead_source_id"), "connected_by_name": conn.get("connected_by_name"),
            "connected_at": conn["connected_at"].isoformat() if conn.get("connected_at") else None, "last_test_at": conn["last_test_at"].isoformat() if conn.get("last_test_at") else None,
            "ok": conn.get("ok", True), "error": conn.get("error"), "webhook_url": f"{app_url}/api/ghl/webhook/{conn['_id']}?key={conn.get('webhook_key', '')}",
            "last_sync": conn.get("last_sync"), "pushed": int(conn.get("pushed") or 0)}


# ── reads ─────────────────────────────────────────────────────────────────────
async def tags(conn: dict) -> list:
    data = await _req("GET", f"/locations/{conn['location_id']}/tags", conn["token"])
    return sorted({(t.get("name") or "").strip() for t in (data.get("tags") or []) if t.get("name")}, key=str.lower)


async def pipelines(conn: dict) -> list:
    data = await _req("GET", "/opportunities/pipelines", conn["token"], params={"locationId": conn["location_id"]})
    return [{"id": p.get("id"), "name": p.get("name"), "stages": [{"id": s.get("id"), "name": s.get("name")} for s in (p.get("stages") or [])]} for p in (data.get("pipelines") or [])]


def _normalize(ct: dict) -> dict:
    phone = ct.get("phone") or next((p.get("phone") for p in (ct.get("additionalPhones") or []) if isinstance(p, dict) and p.get("phone")), "") or ""
    return {"ghl_contact_id": ct.get("id"), "first_name": (ct.get("firstName") or ct.get("firstNameLowerCase") or "").strip(), "last_name": (ct.get("lastName") or "").strip(),
            "phone": phone, "email": (ct.get("email") or "").strip(), "company": (ct.get("companyName") or ct.get("businessName") or "").strip(), "state": ct.get("state") or "",
            "city": ct.get("city") or "", "tags": [t for t in (ct.get("tags") or []) if isinstance(t, str)], "notes": "", "source": "ghl"}


async def search_contacts(conn: dict, tag: Optional[str] = None, query: Optional[str] = None, limit: int = MAX_IMPORT) -> list:
    """Every contact in the location (optionally free-text `query`), filtered client-side by tag. Cursor = `searchAfter` of the last row."""
    out, search_after, want = [], None, (tag or "").strip().lower()
    while len(out) < limit:
        body = {"locationId": conn["location_id"], "pageLimit": PAGE}
        if query:
            body["query"] = query
        if search_after:
            body["searchAfter"] = search_after
        data = await _req("POST", "/contacts/search", conn["token"], json=body)
        rows = data.get("contacts") or []
        for ct in rows:
            n = _normalize(ct)
            if want and want not in {t.lower() for t in n["tags"]}:
                continue
            out.append(n)
        if len(rows) < PAGE or not rows[-1].get("searchAfter"):
            break
        search_after = rows[-1]["searchAfter"]
    return out[:limit]


# ── writes ────────────────────────────────────────────────────────────────────
async def upsert_contact(conn: dict, data: dict) -> Optional[str]:
    body = {"locationId": conn["location_id"], **{k: v for k, v in data.items() if v not in (None, "", [])}}
    res = await _req("POST", "/contacts/upsert", conn["token"], json=body)
    ct = res.get("contact") or res
    return ct.get("id")


async def add_note(conn: dict, contact_id: str, body: str):
    await _req("POST", f"/contacts/{contact_id}/notes", conn["token"], json={"body": body[:5000]})


async def add_tags(conn: dict, contact_id: str, new_tags: list):
    if new_tags:
        await _req("POST", f"/contacts/{contact_id}/tags", conn["token"], json={"tags": new_tags})


async def create_opportunity(conn: dict, contact_id: str, pipeline_id: str, stage_id: str, name: str) -> Optional[str]:
    res = await _req("POST", "/opportunities/", conn["token"], json={"pipelineId": pipeline_id, "locationId": conn["location_id"], "name": name[:120], "pipelineStageId": stage_id, "status": "open", "contactId": contact_id})
    return (res.get("opportunity") or res).get("id")


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:40]


async def push_outcome(db, c: dict, lead: dict, attempt: dict, me: dict):
    """After a disposition: make sure the contact exists in GHL, add a note + tags, open an opportunity for interested/callback."""
    from services.dialer import DISPO, LEADS, lead_name
    conn = await connection_for_campaign(db, c)
    if not conn or not lead:
        return
    try:
        cid = lead.get("ghl_contact_id")
        if not cid:
            cid = await upsert_contact(conn, {"firstName": lead.get("first_name") or lead.get("company") or "Unknown", "lastName": lead.get("last_name") or "", "phone": lead["phone"],
                                              "email": lead.get("email") or None, "companyName": lead.get("company") or None, "state": lead.get("state"), "city": lead.get("city") or None,
                                              "source": "i'M On Social power dialer", "tags": ["imos-dialer"]})
            if cid:
                await db[LEADS].update_one({"_id": lead["_id"]}, {"$set": {"ghl_contact_id": cid}})
        if not cid:
            raise GhlError(0, "GoHighLevel returned no contact id")
        key = (attempt or {}).get("disposition") or lead.get("disposition") or ""
        label = DISPO.get(key, {}).get("label", key or "called")
        when = _now().strftime("%b %-d, %Y %-I:%M %p UTC")
        note = f"Power dialer call by {me.get('name') or 'rep'} on {when}: {label}."
        if (attempt or {}).get("notes"):
            note += f"\n{attempt['notes']}"
        if (attempt or {}).get("talk_s"):
            note += f"\nTalk time {int(attempt['talk_s'] // 60)}m {int(attempt['talk_s'] % 60)}s."
        if key == "callback" and (attempt or {}).get("callback_at"):
            note += f"\nCall back at {attempt['callback_at'].strftime('%b %-d, %Y %-I:%M %p UTC')}."
        await add_note(conn, cid, note)
        await add_tags(conn, cid, ["imos-dialer", f"dialer-{_slug(key)}"] + ([f"dialer-{_slug(c.get('name'))}"] if c.get("name") else []))
        g = c.get("ghl") or {}
        if key in ("interested", "callback") and g.get("pipeline_id") and g.get("stage_id") and not lead.get("ghl_opportunity_id"):
            opp = await create_opportunity(conn, cid, g["pipeline_id"], g["stage_id"], f"{lead_name(lead)} - {c.get('name') or 'Dialer'}")
            if opp:
                await db[LEADS].update_one({"_id": lead["_id"]}, {"$set": {"ghl_opportunity_id": opp}})
        await db[LEADS].update_one({"_id": lead["_id"]}, {"$set": {"ghl_synced_at": _now(), "ghl_sync_error": None}})
        await db[COLL].update_one({"_id": conn["_id"]}, {"$inc": {"pushed": 1}, "$set": {"last_sync": _now().isoformat(), "ok": True, "error": None}})
    except GhlError as e:
        logger.warning(f"[GHL] push failed for lead {lead.get('_id')}: {e.message}")
        await db[LEADS].update_one({"_id": lead["_id"]}, {"$set": {"ghl_sync_error": e.message[:200]}})
        await db[COLL].update_one({"_id": conn["_id"]}, {"$set": {"ok": e.status != 401, "error": e.message[:200]}})
    except Exception as e:
        logger.warning(f"[GHL] push crashed for lead {lead.get('_id')}: {e}")
        await db[LEADS].update_one({"_id": lead["_id"]}, {"$set": {"ghl_sync_error": str(e)[:200]}})


async def push_contact(db, conn: dict, contact: dict, extra_tags: Optional[list] = None) -> str:
    """Send one of our contacts to GHL (upsert by phone/email) and remember its id."""
    cid = await upsert_contact(conn, {"firstName": contact.get("first_name") or "Unknown", "lastName": contact.get("last_name") or "", "phone": contact.get("phone"),
                                      "email": contact.get("email") or None, "companyName": contact.get("organization_name") or contact.get("employer") or None,
                                      "city": contact.get("address_city") or None, "state": contact.get("address_state") or None, "postalCode": contact.get("address_zip") or None,
                                      "address1": contact.get("address_street") or None, "source": "i'M On Social", "tags": ["imos"] + list(extra_tags or [])})
    if cid:
        await db.contacts.update_one({"_id": contact["_id"]}, {"$set": {"external_ids.ghl": cid, "updated_at": _now()}})
        await db[COLL].update_one({"_id": conn["_id"]}, {"$inc": {"pushed": 1}, "$set": {"last_sync": _now().isoformat()}})
    return cid or ""


# ── inbound webhook (GHL workflow "Webhook" action) ───────────────────────────
def normalize_webhook(raw: dict) -> dict:
    """GHL workflow webhooks post the contact flat (first_name, phone, email, tags, location{...}, customData{...})."""
    src = dict(raw or {})
    for k in ("contact", "data"):
        if isinstance(src.get(k), dict):
            src = {**src[k], **{kk: vv for kk, vv in src.items() if kk != k}}
    out = {}
    for key, aliases in {"first_name": ("first_name", "firstName"), "last_name": ("last_name", "lastName"), "full_name": ("full_name", "name", "contact_name"),
                         "phone": ("phone", "phone_number", "mobile"), "email": ("email",), "city": ("city",), "state": ("state",), "zip": ("postal_code", "postalCode", "zip"),
                         "address": ("address1", "address"), "company": ("company_name", "companyName", "business_name")}.items():
        for a in aliases:
            if src.get(a):
                out[key] = str(src[a]).strip()
                break
    if out.get("full_name") and not out.get("first_name"):
        parts = out["full_name"].split(" ", 1)
        out["first_name"], out["last_name"] = parts[0], (parts[1] if len(parts) > 1 else "")
    tags = src.get("tags")
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    comments = []
    if tags:
        comments.append("Tags: " + ", ".join(str(t) for t in tags))
    custom = src.get("customData") or src.get("custom_data") or {}
    if isinstance(custom, dict):
        comments += [f"{k}: {v}" for k, v in custom.items() if v not in (None, "")]
    for k in ("message", "comments", "notes", "source"):
        if src.get(k):
            comments.append(f"{k}: {src[k]}" if k == "source" else str(src[k]))
    if comments:
        out["comments"] = "\n".join(comments)[:2000]
    out["external_id"] = src.get("contact_id") or src.get("id") or ""
    out["source_name"] = "GoHighLevel"
    return out
