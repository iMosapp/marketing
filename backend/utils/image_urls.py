"""
Optimized image URL resolver.
Single source of truth for converting any image field to the fastest possible URL.
Used across all public-facing endpoints (showcase, digital card, congrats, birthday).

Rules:
  1. photo_path → /api/images/{photo_path}  (fastest — direct from cache)
  2. /api/images/ URL → return as-is
  3. short http URL → return as-is
  4. base64 or long string → return lazy-migration endpoint URL
  5. None/empty → None
"""


def resolve_user_photo(user: dict) -> str | None:
    """Get the fastest URL for a user's profile photo."""
    if not user:
        return None
    if user.get("photo_path"):
        return f"/api/images/{user['photo_path']}"
    if user.get("photo_avatar_path"):
        return f"/api/images/{user['photo_avatar_path']}"
    url = user.get("photo_url", "")
    if not url:
        return None
    if url.startswith("/api/images/"):
        return url
    if url.startswith("http") and len(url) < 500:
        return url
    # Fallback: lazy-migrate endpoint
    uid = str(user.get("_id", ""))
    return f"/api/showcase/user-photo/{uid}" if uid else None


def resolve_store_logo(store: dict) -> str | None:
    """Get the fastest URL for a store logo."""
    if not store:
        return None
    if store.get("logo_path"):
        return f"/api/images/{store['logo_path']}"
    if store.get("logo_avatar_path"):
        return f"/api/images/{store['logo_avatar_path']}"
    url = store.get("logo_url", "")
    if not url:
        return None
    if url.startswith("/api/images/"):
        return url
    if url.startswith("http") and len(url) < 500:
        return url
    # Fallback: lazy-migrate endpoint
    sid = str(store.get("_id", ""))
    return f"/api/showcase/store-logo/{sid}" if sid else None


def resolve_card_photo(card: dict) -> str | None:
    """Get the fastest URL for a congrats/birthday card customer photo."""
    if not card:
        return None
    if card.get("photo_path"):
        return f"/api/images/{card['photo_path']}"
    url = card.get("customer_photo", "") or card.get("photo_url", "")
    if not url:
        return None
    if url.startswith("/api/images/"):
        return url
    if url.startswith("http") and len(url) < 500:
        return url
    # Fallback: lazy-migrate endpoint
    cid = card.get("card_id", str(card.get("_id", "")))
    return f"/api/showcase/photo/{cid}" if cid else None


def resolve_contact_photo(contact: dict) -> str | None:
    """Get the fastest URL for a contact's photo."""
    if not contact:
        return None
    if contact.get("photo_path"):
        return f"/api/images/{contact['photo_path']}"
    if contact.get("photo_thumb_path"):
        return f"/api/images/{contact['photo_thumb_path']}"
    url = contact.get("photo_thumbnail") or contact.get("photo_url") or contact.get("photo", "")
    if not url:
        return None
    if url.startswith("/api/images/"):
        return url
    if url.startswith("http") and len(url) < 500:
        return url
    return None


def resolve_feedback_photo(feedback: dict) -> str | None:
    """Get the fastest URL for a customer feedback photo."""
    if not feedback:
        return None
    if feedback.get("photo_path"):
        return f"/api/images/{feedback['photo_path']}"
    url = feedback.get("purchase_photo_url", "")
    if not url:
        return None
    if url.startswith("/api/images/"):
        return url
    if url.startswith("http") and len(url) < 500:
        return url
    fid = str(feedback.get("_id", ""))
    return f"/api/showcase/feedback-photo/{fid}" if fid else None
