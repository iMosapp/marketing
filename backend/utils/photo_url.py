"""Absolute photo URLs for API responses.

Native iOS/Android cannot load relative paths ("/api/images/...") or bare storage
paths ("imos/contacts/abc.jpg") - only web can. Every list endpoint that returns a
contact photo must run it through contact_photo_url() so phones render it.
"""
import os


def _base() -> str:
    return os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com")).rstrip("/")


def abs_photo_url(value: str) -> str:
    if not value:
        return ""
    if value.startswith(("http://", "https://", "data:")):
        return value
    if value.startswith("/"):
        return f"{_base()}{value}"
    return f"{_base()}/api/images/{value}"


def contact_photo_url(contact: dict) -> str:
    """Smallest available photo for a contact, absolutized (thumbnail first)."""
    c = contact or {}
    raw = (c.get("photo_thumbnail") or c.get("photo_url")
           or (f"/api/images/{c['photo_thumb_path']}" if c.get("photo_thumb_path") else "")
           or (f"/api/images/{c['photo_path']}" if c.get("photo_path") else "") or "")
    return abs_photo_url(raw)
