"""
admin_helpers.py — Shared utilities for all admin router modules.
Extracted from admin.py so each split file can import without circular deps.
"""
import os
import asyncio
import logging
import resend
from bson import ObjectId
from fastapi import Header

from routers.database import get_db, get_user_by_id

logger = logging.getLogger(__name__)

# ── Resend config ──────────────────────────────────────────────────────────────
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
SENDER_EMAIL   = os.environ.get("SENDER_EMAIL", "notifications@send.imonsocial.com")
APP_URL        = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY


def safe_objectid(val):
    """Convert a string to ObjectId; return None if invalid."""
    try:
        return ObjectId(val)
    except Exception:
        return None


async def get_requesting_user(x_user_id: str = Header(None, alias="X-User-ID")) -> dict:
    """Return the calling user document for RBAC checks, or None if unauthenticated."""
    if not x_user_id:
        return None
    return await get_user_by_id(x_user_id)


async def send_invite_email(
    email: str, name: str, temp_password: str, role: str, inviter_name: str = None
) -> bool:
    """Send an invite email to a new user with temporary credentials."""
    import base64 as b64_mod

    if not RESEND_API_KEY:
        logger.warning("Resend API key not configured, skipping invite email")
        return False

    role_title = {
        'org_admin': 'Organization Administrator',
        'store_manager': 'Store Manager',
        'user': 'Team Member',
    }.get(role, 'Team Member')

    login_url = f"{APP_URL}/imos/login"

    logo_b64 = ""
    logo_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "static", "imos-logo-email.png"
    )
    try:
        with open(logo_path, "rb") as f:
            logo_b64 = b64_mod.b64encode(f.read()).decode()
    except Exception as e:
        logger.warning(f"Could not read logo file: {e}")

    email_payload = {
        "from": f"i'M On Social <{SENDER_EMAIL}>",
        "to": email,
        "reply_to": "support@imonsocial.com",
        "subject": f"You're Invited to Join i'M On Social as {role_title}",
        "html": f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5;">
                <div style="background-color: #ffffff; border-radius: 16px; overflow: hidden; border: 1px solid #e5e5e5;">
                    <div style="text-align: center; padding: 32px 20px 20px 20px; border-bottom: 1px solid #eee;">
                        <img src="cid:imos-logo" alt="i'M On Social" width="100" height="100" style="width: 100px; height: 100px; border-radius: 50%; display: block; margin: 0 auto;" />
                        <p style="margin: 10px 0 0 0; font-size: 13px; color: #888; letter-spacing: 1px;">Relationship Management System</p>
                    </div>
                    <div style="padding: 32px 30px; background-color: #ffffff;">
                        <h2 style="margin: 0 0 8px 0; color: #111; font-size: 22px;">Welcome, {name}!</h2>
                        <p style="font-size: 15px; line-height: 1.6; color: #444; margin: 0 0 24px 0;">
                            You've been invited to join <strong>i'M On Social</strong> as a
                            <strong style="color: #007AFF;">{role_title}</strong>
                            {f' by {inviter_name}' if inviter_name else ''}.
                        </p>
                        <div style="background-color: #f8f9fa; padding: 20px 24px; border-radius: 12px; margin: 0 0 24px 0; border: 1px solid #e9ecef;">
                            <p style="margin: 0 0 14px 0; font-weight: 700; color: #333; font-size: 14px;">Your Login Credentials</p>
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr>
                                    <td style="padding: 8px 0; color: #666; font-size: 14px; width: 160px;">Email:</td>
                                    <td style="padding: 8px 0;"><code style="background: #fff; padding: 5px 12px; border-radius: 6px; color: #111; font-size: 14px; border: 1px solid #ddd;">{email}</code></td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; color: #666; font-size: 14px;">Temporary Password:</td>
                                    <td style="padding: 8px 0;"><code style="background: #fff; padding: 5px 12px; border-radius: 6px; color: #111; font-size: 14px; font-weight: 600; border: 1px solid #ddd;">{temp_password}</code></td>
                                </tr>
                            </table>
                        </div>
                        <p style="font-size: 14px; color: #666; margin: 0 0 28px 0;">You'll be prompted to create a new password when you first log in.</p>
                        <div style="text-align: center;">
                            <a href="{login_url}" style="display: inline-block; background-color: #007AFF; color: #ffffff; padding: 14px 40px; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 16px;">
                                Get Started
                            </a>
                        </div>
                    </div>
                </div>
                <div style="text-align: center; margin-top: 24px; color: #999; font-size: 12px;">
                    <p style="margin: 5px 0;">i'M On Social &mdash; Your Relationship Management System</p>
                    <p style="margin: 5px 0;">Questions? Contact support@imonsocial.com</p>
                </div>
            </div>
        """,
    }

    if logo_b64:
        email_payload["attachments"] = [{
            "filename": "imos-logo.png",
            "content": logo_b64,
            "content_id": "imos-logo",
        }]

    try:
        result = await asyncio.to_thread(resend.Emails.send, email_payload)
        logger.info(f"Invite email sent to {email}, resend_id: {result.get('id')}")
        return True
    except Exception as e:
        logger.error(f"Failed to send invite email to {email}: {str(e)}")
        return False
