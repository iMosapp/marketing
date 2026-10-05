"""Owner layer: one account (is_owner) above super admins. Decides which internal tools other super admins can see,
and serves Forest's request log (memory/REQUEST_LOG.md) inside the admin panel."""
import os
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from routers.contact_ask import require_user
from routers.database import get_db

router = APIRouter(prefix="/owner", tags=["Owner"], dependencies=[Depends(require_user)])

# key, title, visible to other super admins by default
OWNER_TOOLS = [
    ("request_log", "Request Log", False),
    ("owner_settings", "Owner Settings", False),
    ("billing_revenue", "Billing & Revenue", False),
    ("revenue_forecast", "Revenue Forecast", False),
    ("partner_agreements", "Partner Agreements", False),
    ("white_label_partners", "White Label Partners", False),
    ("discount_codes", "Discount Codes", False),
    ("digest_recipients", "Who gets the morning text", False),
    ("partner_portal", "Partner Portal", True),
    ("view_quotes", "View Quotes", True),
    ("create_quote", "Create Quote", True),
    ("mystery_shops", "Mystery Shops", True),
    ("test_lab", "Test Lab", True),
    ("jessi_voice_lab", "Jessi Voice Lab", True),
    ("texting_compliance", "Texting Compliance", True),
    ("twilio_migration", "Twilio Migration", True),
    ("shared_inboxes", "Shared Inboxes", True),
    ("bulk_transfer", "Bulk Transfer", True),
    ("app_directory", "App Directory", True),
    ("company_docs", "Company Docs", True),
    ("brand_assets", "Brand Assets", True),
    ("error_reports", "Error Reports", True),
    ("bug_reports", "Bug Reports", True),
    ("system_logs", "System Logs", True),
    ("fix_duplicate_campaigns", "Fix Duplicate Campaigns", True),
    ("fix_sold_sequences", "Fix Sold Campaign Sequences", True),
]
ALWAYS_OWNER_ONLY = {"owner_settings"}
LOG_PATH = Path(__file__).resolve().parent.parent.parent / "memory" / "REQUEST_LOG.md"


def is_owner(user: dict) -> bool:
    return bool(user.get("is_owner")) and user.get("role") == "super_admin"


async def visibility_map(db) -> dict:
    doc = await db.settings.find_one({"_id": "owner_visibility"}) or {}
    saved = doc.get("visible") or {}
    return {k: (False if k in ALWAYS_OWNER_ONLY else bool(saved.get(k, default))) for k, _, default in OWNER_TOOLS}


async def can_see(db, user: dict, key: str) -> bool:
    if is_owner(user):
        return True
    if user.get("role") != "super_admin":
        return False
    return (await visibility_map(db)).get(key, True)


async def ensure_owner_flag(db) -> None:
    """Startup: the account named in OWNER_EMAIL is the owner. Nothing happens when the env var is unset."""
    email = (os.environ.get("OWNER_EMAIL") or "").strip().lower()
    if not email:
        return
    await db.users.update_one({"email": re.compile(f"^{re.escape(email)}$", re.I), "role": "super_admin"}, {"$set": {"is_owner": True}})


@router.get("/visibility")
async def get_visibility(request: Request):
    me = request.state.user
    db = get_db()
    vis = await visibility_map(db)
    owner = is_owner(me)
    out = {"is_owner": owner, "visibility": {k: True for k in vis} if owner else vis}
    if owner:
        out["tools"] = [{"key": k, "title": t, "visible": vis[k], "locked": k in ALWAYS_OWNER_ONLY} for k, t, _ in OWNER_TOOLS]
    return out


class VisBody(BaseModel):
    key: str
    visible: bool


@router.put("/visibility")
async def put_visibility(body: VisBody, request: Request):
    me = request.state.user
    if not is_owner(me):
        raise HTTPException(status_code=403, detail="Owner only")
    if body.key not in {k for k, _, _ in OWNER_TOOLS} or body.key in ALWAYS_OWNER_ONLY:
        raise HTTPException(status_code=400, detail="Unknown tool")
    db = get_db()
    await db.settings.update_one({"_id": "owner_visibility"}, {"$set": {f"visible.{body.key}": body.visible}}, upsert=True)
    return {"key": body.key, "visible": body.visible}


class GrantBody(BaseModel):
    user_id: str
    is_owner: bool


@router.get("/owners")
async def list_owners(request: Request):
    if not is_owner(request.state.user):
        raise HTTPException(status_code=403, detail="Owner only")
    rows = await get_db().users.find({"role": "super_admin", "is_active": {"$ne": False}}, {"name": 1, "email": 1, "is_owner": 1}).sort("name", 1).to_list(100)
    return {"admins": [{"user_id": str(u["_id"]), "name": u.get("name") or u.get("email") or "", "email": u.get("email") or "", "is_owner": bool(u.get("is_owner")), "me": str(u["_id"]) == str(request.state.user["_id"])} for u in rows]}


@router.put("/grant")
async def grant(body: GrantBody, request: Request):
    from bson import ObjectId
    me = request.state.user
    if not is_owner(me):
        raise HTTPException(status_code=403, detail="Owner only")
    if body.user_id == str(me["_id"]) and not body.is_owner:
        raise HTTPException(status_code=400, detail="You cannot remove yourself")
    r = await get_db().users.update_one({"_id": ObjectId(body.user_id), "role": "super_admin"}, {"$set": {"is_owner": body.is_owner}})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Super admin not found")
    return {"user_id": body.user_id, "is_owner": body.is_owner}


_HEAD = re.compile(r"^### (\d+) · (.+?) — (.+)$")


def parse_log(text: str) -> dict:
    """memory/REQUEST_LOG.md -> entries + trailing sections."""
    entries, tail = [], []
    cur: Optional[dict] = None
    in_tail = False
    for line in text.splitlines():
        if in_tail:
            tail.append(line)
            continue
        if line.startswith("## "):
            in_tail = True
            tail.append(line)
            continue
        m = _HEAD.match(line)
        if m:
            cur = {"n": int(m.group(1)), "date": m.group(2).strip(), "status": m.group(3).strip(), "prompt": [], "notes": []}
            entries.append(cur)
            continue
        if cur is None or line.strip() == "---":
            continue
        if line.startswith(">"):
            cur["prompt"].append(line[1:].strip())
        elif line.strip():
            cur["notes"].append(line.strip())
    for e in entries:
        e["prompt"] = "\n".join(e["prompt"]).strip()
        e["notes"] = " ".join(e["notes"]).strip()
    return {"entries": entries, "tail": "\n".join(tail).strip()}


@router.get("/request-log")
async def request_log(request: Request):
    me = request.state.user
    if not await can_see(get_db(), me, "request_log"):
        raise HTTPException(status_code=403, detail="Not available")
    if not LOG_PATH.exists():
        return {"entries": [], "tail": "", "path": str(LOG_PATH), "missing": True}
    data = parse_log(LOG_PATH.read_text(encoding="utf-8"))
    return {**data, "path": str(LOG_PATH), "updated_at": LOG_PATH.stat().st_mtime}
