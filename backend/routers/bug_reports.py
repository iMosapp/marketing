import os
import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Body, Request
from bson import ObjectId
import resend

from routers.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bug-reports", tags=["Bug Reports"])

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "notifications@send.imonsocial.com")
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY


async def _email_super_admins(report: dict):
    if not RESEND_API_KEY:
        return
    db = get_db()
    admins = await db.users.find({"role": "super_admin"}, {"email": 1}).to_list(10)
    emails = [a["email"] for a in admins if a.get("email")]
    if not emails:
        return
    html = f"""
    <div style="font-family: -apple-system, Arial, sans-serif; max-width: 560px; margin: 0 auto; padding: 24px;">
        <h2 style="color: #1a1a1a;">New Bug Report</h2>
        <p><strong>From:</strong> {report.get('user_name')} ({report.get('user_email')})</p>
        <p><strong>Category:</strong> {(report.get('category') or 'bug').replace('_', ' ').title()}</p>
        <p><strong>Platform:</strong> {report.get('platform') or 'unknown'}</p>
        <div style="background: #f5f5f7; border-radius: 10px; padding: 16px; margin-top: 12px;">
            <p style="white-space: pre-wrap; margin: 0;">{report.get('description')}</p>
        </div>
        <p style="color: #888; font-size: 12px; margin-top: 20px;">Manage in Hub &rarr; Internal Operations &rarr; Bug Reports.</p>
    </div>
    """
    try:
        await asyncio.to_thread(resend.Emails.send, {
            "from": f"I'm On Social <{SENDER_EMAIL}>",
            "to": emails,
            "subject": f"Bug Report from {report.get('user_name', 'User')}: {(report.get('category') or 'bug').replace('_', ' ').title()}",
            "html": html,
        })
    except Exception as e:
        logger.warning(f"[bug-reports] email notify failed: {e}")


async def _push_super_admins(report: dict):
    """Instant push notification to super admins when a bug report is filed."""
    db = get_db()
    try:
        from routers.push_notifications import send_push_to_user
        admins = await db.users.find({"role": "super_admin"}, {"_id": 1}).to_list(10)
        for a in admins:
            try:
                await send_push_to_user(
                    user_id=str(a["_id"]),
                    title=f"🐛 Bug Report — {report.get('user_name', 'User')}",
                    body=(report.get("description") or "")[:120],
                    url="/admin/bug-reports",
                    icon="bug",
                )
                logger.info(f"[bug-reports] push sent to super admin {a['_id']}")
            except Exception as e:
                logger.warning(f"[bug-reports] push to {a['_id']} failed: {e}")
    except Exception as e:
        logger.warning(f"[bug-reports] push notify failed: {e}")


async def send_weekly_bug_digest():
    """Monday digest of unresolved bug reports emailed to super admins."""
    if not RESEND_API_KEY:
        logger.info("[bug-digest] skipped — no RESEND_API_KEY")
        return {"sent": False, "reason": "no_api_key"}
    db = get_db()
    reports = await db.bug_reports.find(
        {"status": {"$in": ["open", "in_progress"]}}
    ).sort("created_at", -1).to_list(100)
    if not reports:
        logger.info("[bug-digest] skipped — no open reports")
        return {"sent": False, "reason": "no_open_reports"}

    admins = await db.users.find({"role": "super_admin"}, {"email": 1}).to_list(10)
    emails = [a["email"] for a in admins if a.get("email")]
    if not emails:
        return {"sent": False, "reason": "no_admins"}

    open_count = sum(1 for r in reports if r.get("status") == "open")
    prog_count = sum(1 for r in reports if r.get("status") == "in_progress")
    now = datetime.now(timezone.utc)

    rows = ""
    for r in reports[:25]:
        created = r.get("created_at")
        age_days = "?"
        if hasattr(created, "isoformat"):
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age_days = int((now - created).total_seconds() // 86400)
        status_color = "#FF3B30" if r.get("status") == "open" else "#FF9500"
        status_label = "OPEN" if r.get("status") == "open" else "IN PROGRESS"
        rows += f"""
        <tr>
            <td style="padding: 10px 12px; border-bottom: 1px solid #eee;">
                <span style="display: inline-block; background: {status_color}18; color: {status_color}; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 5px;">{status_label}</span>
                <span style="font-size: 12px; color: #888; margin-left: 6px;">{(r.get('category') or 'bug').replace('_', ' ').title()} · {r.get('user_name', 'Unknown')} · {age_days}d old</span>
                <div style="font-size: 14px; color: #1a1a1a; margin-top: 4px;">{(r.get('description') or '')[:180]}</div>
            </td>
        </tr>"""

    html = f"""
    <div style="font-family: -apple-system, Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px;">
        <h2 style="color: #1a1a1a; margin-bottom: 4px;">🐛 Weekly Bug Report Digest</h2>
        <p style="color: #555; margin-top: 0;">{open_count} open · {prog_count} in progress</p>
        <table style="width: 100%; border-collapse: collapse; background: #fafafa; border-radius: 10px;">{rows}</table>
        <p style="color: #888; font-size: 12px; margin-top: 20px;">Manage in Hub &rarr; Internal Operations &rarr; Bug Reports.</p>
    </div>
    """
    try:
        await asyncio.to_thread(resend.Emails.send, {
            "from": f"I'm On Social <{SENDER_EMAIL}>",
            "to": emails,
            "subject": f"Weekly Bug Digest — {open_count + prog_count} unresolved report{'s' if open_count + prog_count != 1 else ''}",
            "html": html,
        })
        logger.info(f"[bug-digest] sent to {len(emails)} super admin(s) — {len(reports)} unresolved")
        return {"sent": True, "reports": len(reports)}
    except Exception as e:
        logger.warning(f"[bug-digest] send failed: {e}")
        return {"sent": False, "reason": str(e)}


@router.post("/{user_id}")
async def submit_bug_report(user_id: str, data: dict = Body(...)):
    """Field rep submits a bug report from Hub settings."""
    db = get_db()
    description = (data.get("description") or "").strip()
    if not description:
        raise HTTPException(status_code=400, detail="Description is required")

    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)}, {"name": 1, "email": 1})
    except Exception:
        user = None

    report = {
        "user_id": user_id,
        "user_name": (user or {}).get("name", "Unknown"),
        "user_email": (user or {}).get("email", ""),
        "category": data.get("category", "bug"),
        "description": description,
        "platform": data.get("platform", ""),
        "status": "open",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    result = await db.bug_reports.insert_one(report)
    await _email_super_admins(report)
    asyncio.create_task(_push_super_admins(report))
    return {"success": True, "report_id": str(result.inserted_id)}


async def _require_super_admin(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    from routers.auth import verify_jwt_token
    payload = verify_jwt_token(auth[7:])
    caller_id = payload.get("sub") if payload else None
    if not caller_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    db = get_db()
    try:
        user = await db.users.find_one({"_id": ObjectId(caller_id)}, {"role": 1})
    except Exception:
        user = None
    if not user or user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin access required")


@router.get("")
async def list_bug_reports(request: Request, status: str = None, limit: int = 100):
    await _require_super_admin(request)
    db = get_db()
    query = {}
    if status and status != "all":
        query["status"] = status
    reports = await db.bug_reports.find(query).sort("created_at", -1).to_list(min(limit, 300))
    out = []
    for r in reports:
        r["_id"] = str(r["_id"])
        for k in ("created_at", "updated_at"):
            if hasattr(r.get(k), "isoformat"):
                r[k] = r[k].isoformat()
        out.append(r)
    counts = {}
    for s in ("open", "in_progress", "resolved"):
        counts[s] = await db.bug_reports.count_documents({"status": s})
    return {"reports": out, "counts": counts}


@router.patch("/{report_id}/status")
async def update_bug_report_status(report_id: str, request: Request, data: dict = Body(...)):
    await _require_super_admin(request)
    new_status = data.get("status")
    if new_status not in ("open", "in_progress", "resolved"):
        raise HTTPException(status_code=400, detail="Invalid status")
    db = get_db()
    result = await db.bug_reports.update_one(
        {"_id": ObjectId(report_id)},
        {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc)}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"success": True, "status": new_status}
