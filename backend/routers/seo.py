"""
SEO & AEO Router — Dynamic sitemap, robots.txt, meta tags, and Schema.org JSON-LD
for public-facing pages (digital cards, link pages, showcase, store pages).
"""
from fastapi import APIRouter, Request
from fastapi.responses import Response, HTMLResponse
from datetime import datetime, timezone
from bson import ObjectId
import json
import logging

from routers.database import get_db
from utils.image_urls import resolve_user_photo, resolve_store_logo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/seo", tags=["seo"])

# ─── helpers ────────────────────────────────────────────────────────

def _base_url(request: Request) -> str:
    """Derive the public base URL from the request."""
    forwarded = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    scheme = request.headers.get("x-forwarded-proto", "https")
    if forwarded:
        return f"{scheme}://{forwarded}"
    return str(request.base_url).rstrip("/")


def _slug(name: str) -> str:
    """Generate a URL-friendly slug from a name."""
    import re
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug


# ─── robots.txt ─────────────────────────────────────────────────────

@router.get("/robots.txt")
async def robots_txt(request: Request):
    base = _base_url(request)
    content = f"""User-agent: *
Allow: /card/
Allow: /l/
Allow: /showcase/
Allow: /card/store/
Allow: /congrats/
Disallow: /admin/
Disallow: /settings/
Disallow: /api/
Disallow: /auth/

Sitemap: {base}/api/seo/sitemap.xml
"""
    return Response(content=content, media_type="text/plain")


# ─── sitemap.xml ────────────────────────────────────────────────────

@router.get("/sitemap.xml")
async def sitemap_xml(request: Request):
    base = _base_url(request)
    db = get_db()
    
    urls = []
    
    # Homepage
    urls.append({"loc": base, "changefreq": "daily", "priority": "1.0"})
    
    # All active users with digital cards
    users = await db.users.find(
        {"is_active": True, "status": {"$ne": "deleted"}},
        {"_id": 1, "username": 1, "name": 1, "updated_at": 1, "created_at": 1}
    ).to_list(10000)
    
    for u in users:
        uid = str(u["_id"])
        lastmod = u.get("updated_at") or u.get("created_at") or datetime.now(timezone.utc)
        if hasattr(lastmod, "strftime"):
            lastmod = lastmod.strftime("%Y-%m-%d")
        
        # Digital card page
        urls.append({
            "loc": f"{base}/card/{uid}",
            "lastmod": lastmod,
            "changefreq": "weekly",
            "priority": "0.8",
        })
        
        # Link page (if username exists)
        if u.get("username"):
            urls.append({
                "loc": f"{base}/l/{u['username']}",
                "lastmod": lastmod,
                "changefreq": "weekly",
                "priority": "0.8",
            })
    
    # All active stores with slugs
    stores = await db.stores.find(
        {"is_active": {"$ne": False}},
        {"_id": 1, "slug": 1, "name": 1, "updated_at": 1}
    ).to_list(5000)
    
    for s in stores:
        slug = s.get("slug") or _slug(s.get("name", ""))
        if slug:
            lastmod = s.get("updated_at") or datetime.now(timezone.utc)
            if hasattr(lastmod, "strftime"):
                lastmod = lastmod.strftime("%Y-%m-%d")
            urls.append({
                "loc": f"{base}/card/store/{slug}",
                "lastmod": lastmod,
                "changefreq": "weekly",
                "priority": "0.7",
            })
    
    # Build XML
    xml_entries = []
    for u in urls:
        entry = f"  <url>\n    <loc>{u['loc']}</loc>\n"
        if u.get("lastmod"):
            entry += f"    <lastmod>{u['lastmod']}</lastmod>\n"
        if u.get("changefreq"):
            entry += f"    <changefreq>{u['changefreq']}</changefreq>\n"
        if u.get("priority"):
            entry += f"    <priority>{u['priority']}</priority>\n"
        entry += "  </url>"
        xml_entries.append(entry)
    
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(xml_entries)}
</urlset>"""
    
    return Response(content=xml, media_type="application/xml")


# ─── Meta / OG tags endpoint ────────────────────────────────────────

@router.get("/meta/card/{user_id}")
async def meta_card(user_id: str, request: Request):
    """Return SEO metadata for a digital card page."""
    base = _base_url(request)
    db = get_db()
    
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)}, {"password": 0})
    except Exception:
        return {"error": "not_found"}
    
    if not user:
        return {"error": "not_found"}
    
    name = user.get("name", "Sales Professional")
    title = user.get("title", "Sales Professional")
    bio = user.get("persona", {}).get("bio", "")
    photo = resolve_user_photo(user)
    
    store = None
    store_name = ""
    store_city = ""
    store_state = ""
    if user.get("store_id"):
        store = await db.stores.find_one({"_id": ObjectId(user["store_id"])})
        if store:
            store_name = store.get("name", "")
            store_city = store.get("city", "")
            store_state = store.get("state", "")
    
    location = f"{store_city}, {store_state}" if store_city and store_state else store_state or store_city
    page_title = f"{name} - {title}"
    if store_name:
        page_title += f" at {store_name}"
    
    description = bio[:160] if bio else f"Connect with {name}"
    if store_name:
        description += f" at {store_name}"
    if location:
        description += f" in {location}"
    description = description[:300]
    
    page_url = f"{base}/card/{user_id}"
    
    # Schema.org structured data
    schema = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": name,
        "jobTitle": title,
        "url": page_url,
    }
    if photo:
        schema["image"] = photo
    if user.get("email"):
        schema["email"] = user["email"]
    if user.get("phone"):
        schema["telephone"] = user["phone"]
    if bio:
        schema["description"] = bio[:500]
    
    if store:
        schema["worksFor"] = {
            "@type": "LocalBusiness",
            "name": store_name,
        }
        if store.get("address"):
            schema["worksFor"]["address"] = {
                "@type": "PostalAddress",
                "streetAddress": store.get("address", ""),
                "addressLocality": store_city,
                "addressRegion": store_state,
            }
        if store.get("website"):
            schema["worksFor"]["url"] = store["website"]
        if store.get("phone"):
            schema["worksFor"]["telephone"] = store["phone"]
    
    # Testimonials as reviews
    testimonials = await db.customer_feedback.find({
        "salesperson_id": user_id, "approved": True, "rating": {"$gte": 4}
    }).sort("created_at", -1).limit(5).to_list(5)
    
    if testimonials:
        avg_rating = sum(t.get("rating", 5) for t in testimonials) / len(testimonials)
        schema["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": round(avg_rating, 1),
            "reviewCount": len(testimonials),
            "bestRating": 5,
        }
    
    return {
        "title": page_title,
        "description": description,
        "url": page_url,
        "image": photo or f"{base}/icon.png",
        "type": "profile",
        "schema": schema,
    }


@router.get("/meta/link/{username}")
async def meta_link_page(username: str, request: Request):
    """Return SEO metadata for a link page."""
    base = _base_url(request)
    db = get_db()
    
    user = await db.users.find_one({"username": username}, {"password": 0})
    if not user:
        return {"error": "not_found"}
    
    name = user.get("name", "")
    title = user.get("title", "")
    bio = user.get("persona", {}).get("bio", "")
    photo = resolve_user_photo(user)
    
    store = None
    store_name = ""
    if user.get("store_id"):
        store = await db.stores.find_one({"_id": ObjectId(user["store_id"])})
        store_name = store.get("name", "") if store else ""
    
    page_title = f"{name} - Links & Contact"
    if store_name:
        page_title += f" | {store_name}"
    
    description = f"Connect with {name}"
    if title:
        description += f", {title}"
    if store_name:
        description += f" at {store_name}"
    description += ". Find all contact links, social media, and more."
    
    page_url = f"{base}/l/{username}"
    
    schema = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": name,
        "url": page_url,
    }
    if title:
        schema["jobTitle"] = title
    if photo:
        schema["image"] = photo
    if store:
        schema["worksFor"] = {"@type": "Organization", "name": store_name}
    
    return {
        "title": page_title,
        "description": description[:300],
        "url": page_url,
        "image": photo or f"{base}/icon.png",
        "type": "profile",
        "schema": schema,
    }


@router.get("/meta/store/{store_slug}")
async def meta_store(store_slug: str, request: Request):
    """Return SEO metadata for a store card page."""
    base = _base_url(request)
    db = get_db()
    
    store = await db.stores.find_one({"slug": store_slug})
    if not store:
        return {"error": "not_found"}
    
    name = store.get("name", "")
    city = store.get("city", "")
    state = store.get("state", "")
    location = f"{city}, {state}" if city and state else city or state
    logo = resolve_store_logo(store)
    
    # Count team members
    team_count = await db.users.count_documents({
        "store_id": str(store["_id"]), "is_active": True
    })
    
    page_title = f"{name} Team"
    if location:
        page_title += f" - {location}"
    
    description = f"Meet the team at {name}"
    if location:
        description += f" in {location}"
    description += f". {team_count} professionals ready to help you."
    
    page_url = f"{base}/card/store/{store_slug}"
    
    schema = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": name,
        "url": page_url,
        "numberOfEmployees": {"@type": "QuantitativeValue", "value": team_count},
    }
    if logo:
        schema["image"] = logo
    if store.get("address"):
        schema["address"] = {
            "@type": "PostalAddress",
            "streetAddress": store.get("address", ""),
            "addressLocality": city,
            "addressRegion": state,
        }
    if store.get("phone"):
        schema["telephone"] = store["phone"]
    if store.get("website"):
        schema["sameAs"] = store["website"]
    
    return {
        "title": page_title,
        "description": description[:300],
        "url": page_url,
        "image": logo or f"{base}/icon.png",
        "type": "business",
        "schema": schema,
    }
