"""
App Directory Router - Page catalog and sharing for super admins
"""
import os
import logging
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from typing import Optional

import resend

from routers.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/app-directory", tags=["App Directory"])

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "noreply@imosapp.com")
APP_URL = os.environ.get("APP_URL")

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY


class SharePageRequest(BaseModel):
    page_name: str
    page_path: str
    recipient_name: Optional[str] = None
    recipient_email: Optional[str] = None
    recipient_phone: Optional[str] = None
    channel: str  # "email" or "sms"
    custom_message: Optional[str] = None


async def get_admin_user(x_user_id: str = Header(None, alias="X-User-ID")):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    from bson import ObjectId
    user = await get_db().users.find_one({"_id": ObjectId(x_user_id)})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.get("role") not in ("super_admin", "org_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.post("/share")
async def share_page(data: SharePageRequest, x_user_id: str = Header(None, alias="X-User-ID")):
    """Share an app page link via email or SMS"""
    user = await get_admin_user(x_user_id)

    page_url = f"{APP_URL}{data.page_path}"
    sender_name = user.get("name", "iMOs Admin")
    recipient_name = data.recipient_name or "there"

    if data.channel == "email":
        if not data.recipient_email:
            raise HTTPException(status_code=400, detail="Email address required")
        if not RESEND_API_KEY:
            raise HTTPException(status_code=500, detail="Email service not configured")

        custom_msg = f'<p style="font-size: 15px; line-height: 1.6; color: #ccc; margin-bottom: 20px;">{data.custom_message}</p>' if data.custom_message else ""

        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #111;">
            <div style="text-align: center; padding: 24px; background: #1A1A2E; border-radius: 16px 16px 0 0;">
                <h1 style="margin: 0; font-size: 28px; font-weight: 700;">
                    <span style="color:#FF3B30;">i</span><span style="color:#FFD60A;">M</span><span style="color:#34C759;">O</span><span style="color:#007AFF;">s</span>
                </h1>
                <p style="margin: 6px 0 0; font-size: 12px; color: #888; letter-spacing: 1px;">Relationship Management System</p>
            </div>
            <div style="background: linear-gradient(135deg, #1A1A2E 0%, #16213E 100%); padding: 30px; border-radius: 0 0 16px 16px; color: white;">
                <h2 style="margin-top: 0; color: #C9A962;">Hi {recipient_name}!</h2>
                <p style="font-size: 15px; line-height: 1.6; color: #ccc;">{sender_name} shared a page with you from <strong style="color:#fff;">iMOs</strong>:</p>
                {custom_msg}
                <div style="background: rgba(255,255,255,0.08); padding: 16px 20px; border-radius: 12px; margin: 20px 0; border-left: 4px solid #C9A962;">
                    <p style="margin: 0; font-size: 17px; font-weight: 600; color: #fff;">{data.page_name}</p>
                    <p style="margin: 6px 0 0; font-size: 13px; color: #888;">{data.page_path}</p>
                </div>
                <div style="text-align: center; margin-top: 24px;">
                    <a href="{page_url}" style="display: inline-block; background: #C9A962; color: #000; padding: 14px 36px; text-decoration: none; border-radius: 30px; font-weight: 700; font-size: 15px;">
                        View Page
                    </a>
                </div>
            </div>
            <div style="text-align: center; margin-top: 20px; color: #555; font-size: 11px;">
                <p>Sent from iMOs by {sender_name}</p>
            </div>
        </div>
        """

        try:
            result = await asyncio.to_thread(resend.Emails.send, {
                "from": SENDER_EMAIL,
                "to": data.recipient_email,
                "subject": f"{sender_name} shared \"{data.page_name}\" with you from iMOs",
                "html": html,
            })
            logger.info(f"Page share email sent to {data.recipient_email}")
            return {"success": True, "channel": "email", "message": f"Email sent to {data.recipient_email}"}
        except Exception as e:
            logger.error(f"Failed to send share email: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

    elif data.channel == "sms":
        if not data.recipient_phone:
            raise HTTPException(status_code=400, detail="Phone number required")

        sms_body = f"{sender_name} shared \"{data.page_name}\" with you from iMOs."
        if data.custom_message:
            sms_body += f"\n\n{data.custom_message}"
        sms_body += f"\n\nView here: {page_url}"

        try:
            from services.twilio_service import send_sms
            result = await send_sms(data.recipient_phone, sms_body)
            if result.get("success"):
                return {
                    "success": True,
                    "channel": "sms",
                    "message": f"SMS sent to {data.recipient_phone}",
                    "mock": result.get("mock", False),
                }
            else:
                raise HTTPException(status_code=500, detail=result.get("error", "SMS failed"))
        except ImportError:
            raise HTTPException(status_code=500, detail="SMS service not available")
    else:
        raise HTTPException(status_code=400, detail="Invalid channel. Use 'email' or 'sms'")


@router.post("/share/copy-link")
async def log_copy_link(data: dict, x_user_id: str = Header(None, alias="X-User-ID")):
    """Log when a page link is copied (analytics)"""
    user = await get_admin_user(x_user_id)
    await get_db().activity.insert_one({
        "type": "page_link_copied",
        "user_id": x_user_id,
        "user_name": user.get("name"),
        "page_name": data.get("page_name"),
        "page_path": data.get("page_path"),
        "created_at": datetime.now(timezone.utc),
    })
    return {"success": True}
