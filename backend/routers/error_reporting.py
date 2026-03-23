"""
Error Reporting Router — captures frontend crashes and API errors for production diagnostics.
Stores error reports in MongoDB so they can be pulled up and shared for debugging.
"""
from fastapi import APIRouter, Request
from datetime import datetime, timezone
from routers.database import get_db
import logging

router = APIRouter(prefix="/errors", tags=["Error Reporting"])
logger = logging.getLogger("error_reporting")


@router.post("/report")
async def report_error(request: Request):
    """Receive and store an error report from the frontend."""
    db = get_db()
    data = await request.json()

    report = {
        "error_message": data.get("error_message", "Unknown error"),
        "error_stack": data.get("error_stack", ""),
        "component_stack": data.get("component_stack", ""),
        "page": data.get("page", "unknown"),
        "user_id": data.get("user_id"),
        "user_email": data.get("user_email"),
        "user_name": data.get("user_name"),
        "platform": data.get("platform", "unknown"),
        "user_agent": request.headers.get("user-agent", ""),
        "error_type": data.get("error_type", "render_crash"),  # render_crash | unhandled_rejection | api_error
        "extra": data.get("extra", {}),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.error_reports.insert_one(report)
    logger.warning(f"[ERROR REPORT] {report['error_type']} on {report['page']} for user {report['user_email'] or report['user_id']}: {report['error_message'][:200]}")

    return {"status": "reported"}


@router.get("/recent")
async def get_recent_errors(limit: int = 50, error_type: str = None, user_id: str = None):
    """Get recent error reports for admin diagnosis. Supports filtering by type and user."""
    db = get_db()

    query = {}
    if error_type:
        query["error_type"] = error_type
    if user_id:
        query["user_id"] = user_id

    cursor = db.error_reports.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
    reports = await cursor.to_list(length=limit)
    return {"count": len(reports), "reports": reports}


@router.delete("/clear")
async def clear_errors():
    """Clear all error reports (admin action)."""
    db = get_db()
    result = await db.error_reports.delete_many({})
    return {"deleted": result.deleted_count}
