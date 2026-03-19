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
Allow: /salesperson/
Allow: /store/
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
        {"_id": 1, "username": 1, "name": 1, "seo_slug": 1, "updated_at": 1, "created_at": 1}
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
        
        # SEO-friendly salesperson page (preferred by Google)
        if u.get("seo_slug"):
            urls.append({
                "loc": f"{base}/salesperson/{u['seo_slug']}",
                "lastmod": lastmod,
                "changefreq": "weekly",
                "priority": "0.9",
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
            # Store directory page
            urls.append({
                "loc": f"{base}/store/{slug}",
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



# ─── User slug generation & lookup ──────────────────────────────────

def _user_slug(name: str, city: str = "", state: str = "") -> str:
    """Generate a SEO-friendly slug from user name + location."""
    parts = [name]
    if city:
        parts.append(city)
    if state:
        parts.append(state)
    return _slug(" ".join(parts))


@router.post("/generate-slugs")
async def generate_user_slugs():
    """Batch-generate slugs for all users that don't have one."""
    db = get_db()
    users = await db.users.find(
        {"is_active": True, "$or": [{"seo_slug": {"$exists": False}}, {"seo_slug": ""}]},
        {"_id": 1, "name": 1, "store_id": 1}
    ).to_list(10000)
    
    updated = 0
    for u in users:
        name = u.get("name", "")
        if not name:
            continue
        
        city, state = "", ""
        if u.get("store_id"):
            try:
                store = await db.stores.find_one({"_id": ObjectId(u["store_id"])}, {"city": 1, "state": 1})
                if store:
                    city = store.get("city", "")
                    state = store.get("state", "")
            except Exception:
                pass
        
        base_slug = _user_slug(name, city, state)
        slug = base_slug
        
        # Ensure uniqueness
        counter = 1
        while await db.users.find_one({"seo_slug": slug, "_id": {"$ne": u["_id"]}}):
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        await db.users.update_one({"_id": u["_id"]}, {"$set": {"seo_slug": slug}})
        updated += 1
    
    return {"updated": updated}


@router.get("/user-by-slug/{slug}")
async def get_user_by_slug(slug: str):
    """Resolve a user ID from an SEO slug."""
    db = get_db()
    user = await db.users.find_one({"seo_slug": slug}, {"_id": 1, "name": 1, "username": 1})
    if not user:
        # Fallback: try matching by username
        user = await db.users.find_one({"username": slug}, {"_id": 1, "name": 1, "username": 1})
    if not user:
        return {"error": "not_found"}
    return {"user_id": str(user["_id"]), "name": user.get("name"), "username": user.get("username")}


# ─── Store directory endpoint ───────────────────────────────────────

@router.get("/store-directory/{slug}")
async def store_directory(slug: str, request: Request):
    """Return store info + full team listing for a store directory page."""
    base = _base_url(request)
    db = get_db()
    
    store = await db.stores.find_one({"slug": slug})
    if not store:
        return {"error": "not_found"}
    
    store_id = str(store["_id"])
    
    # Get the organization
    org = None
    org_name = ""
    if store.get("organization_id"):
        try:
            org = await db.organizations.find_one({"_id": ObjectId(store["organization_id"])})
            org_name = org.get("name", "") if org else ""
        except Exception:
            pass
    
    # Get all active team members
    team = await db.users.find(
        {"store_id": store_id, "is_active": True, "status": {"$ne": "deleted"}},
        {"password": 0}
    ).sort("name", 1).to_list(500)
    
    team_list = []
    for member in team:
        photo = resolve_user_photo(member)
        
        # Get review count and avg rating
        reviews = await db.customer_feedback.find({
            "salesperson_id": str(member["_id"]),
            "approved": True,
            "rating": {"$gte": 1}
        }).to_list(100)
        
        avg_rating = round(sum(r.get("rating", 5) for r in reviews) / len(reviews), 1) if reviews else None
        
        team_list.append({
            "_id": str(member["_id"]),
            "name": member.get("name", ""),
            "title": member.get("title", ""),
            "photo_url": photo,
            "phone": member.get("phone", ""),
            "email": member.get("email", ""),
            "bio": (member.get("persona", {}) or {}).get("bio", ""),
            "seo_slug": member.get("seo_slug", ""),
            "username": member.get("username", ""),
            "review_count": len(reviews),
            "avg_rating": avg_rating,
        })
    
    logo = resolve_store_logo(store)
    
    result = {
        "store": {
            "_id": store_id,
            "name": store.get("name", ""),
            "slug": store.get("slug", ""),
            "city": store.get("city", ""),
            "state": store.get("state", ""),
            "address": store.get("address", ""),
            "phone": store.get("phone", ""),
            "website": store.get("website", ""),
            "email": store.get("admin_email", ""),
            "logo_url": logo,
            "organization_name": org_name,
        },
        "team": team_list,
        "team_count": len(team_list),
    }
    
    # Schema.org
    location = f"{store.get('city', '')}, {store.get('state', '')}" if store.get("city") else store.get("state", "")
    
    schema = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": store.get("name", ""),
        "url": f"{base}/store/{slug}",
        "numberOfEmployees": {"@type": "QuantitativeValue", "value": len(team_list)},
    }
    if logo:
        schema["image"] = logo
    if store.get("address"):
        schema["address"] = {
            "@type": "PostalAddress",
            "streetAddress": store.get("address", ""),
            "addressLocality": store.get("city", ""),
            "addressRegion": store.get("state", ""),
        }
    if store.get("phone"):
        schema["telephone"] = store["phone"]
    if store.get("website"):
        schema["sameAs"] = store["website"]
    
    # Add employees to schema
    employee_schemas = []
    for m in team_list:
        emp = {"@type": "Person", "name": m["name"]}
        if m.get("title"):
            emp["jobTitle"] = m["title"]
        if m.get("photo_url"):
            emp["image"] = m["photo_url"]
        if m.get("seo_slug"):
            emp["url"] = f"{base}/salesperson/{m['seo_slug']}"
        if m.get("avg_rating"):
            emp["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": m["avg_rating"],
                "reviewCount": m["review_count"],
            }
        employee_schemas.append(emp)
    
    if employee_schemas:
        schema["employee"] = employee_schemas
    
    result["schema"] = schema
    return result


# ─── UTM link builder ───────────────────────────────────────────────

@router.post("/utm-link")
async def create_utm_link(data: dict, request: Request):
    """Create a UTM-tagged link for tracking. Optionally creates a short URL."""
    base = _base_url(request)
    db = get_db()
    
    page_type = data.get("page_type", "card")  # card, link, store, showcase
    reference_id = data.get("reference_id", "")
    source = data.get("source", "imonsocial")
    medium = data.get("medium", "sms")
    campaign = data.get("campaign", "")
    user_id = data.get("user_id", "")
    
    # Build the base URL
    if page_type == "card":
        # Try to use SEO slug first
        user = await db.users.find_one({"_id": ObjectId(reference_id)}, {"seo_slug": 1}) if reference_id else None
        if user and user.get("seo_slug"):
            path = f"/salesperson/{user['seo_slug']}"
        else:
            path = f"/card/{reference_id}"
    elif page_type == "link":
        path = f"/l/{reference_id}"
    elif page_type == "store":
        path = f"/card/store/{reference_id}"
    elif page_type == "showcase":
        path = f"/showcase/{reference_id}"
    else:
        path = f"/card/{reference_id}"
    
    # Build UTM params
    utm_parts = [f"utm_source={source}", f"utm_medium={medium}"]
    if campaign:
        utm_parts.append(f"utm_campaign={campaign}")
    
    full_url = f"{base}{path}?{'&'.join(utm_parts)}"
    
    # Optionally create a short URL
    if data.get("shorten", False):
        from routers.short_urls import create_short_url
        short = await create_short_url(
            original_url=full_url,
            link_type=f"seo_{page_type}",
            reference_id=reference_id,
            user_id=user_id,
            metadata={"source": source, "medium": medium, "campaign": campaign}
        )
        return {
            "url": full_url,
            "short_url": short["short_url"],
            "short_code": short["short_code"],
        }
    
    return {"url": full_url}


# ─── UTM tracking on page visit ─────────────────────────────────────

@router.post("/track-visit")
async def track_page_visit(data: dict):
    """Track a page visit with UTM parameters for analytics."""
    db = get_db()
    
    visit = {
        "page_type": data.get("page_type", ""),
        "reference_id": data.get("reference_id", ""),
        "utm_source": data.get("utm_source", ""),
        "utm_medium": data.get("utm_medium", ""),
        "utm_campaign": data.get("utm_campaign", ""),
        "referrer": data.get("referrer", ""),
        "user_agent": data.get("user_agent", ""),
        "timestamp": datetime.now(timezone.utc),
    }
    
    await db.seo_page_visits.insert_one(visit)
    
    # Update aggregate stats
    if visit["reference_id"]:
        await db.seo_stats.update_one(
            {"reference_id": visit["reference_id"], "page_type": visit["page_type"]},
            {
                "$inc": {"total_visits": 1},
                "$set": {"last_visit": visit["timestamp"]},
                "$push": {
                    "recent_sources": {
                        "$each": [{"source": visit["utm_source"], "medium": visit["utm_medium"], "ts": visit["timestamp"]}],
                        "$slice": -50,
                    }
                },
            },
            upsert=True,
        )
    
    return {"tracked": True}


# ─── SEO Analytics dashboard data ──────────────────────────────────

@router.get("/analytics/{user_id}")
async def seo_analytics(user_id: str):
    """Get SEO analytics for a user's public pages."""
    db = get_db()
    
    # Page visit stats
    card_stats = await db.seo_stats.find_one({"reference_id": user_id, "page_type": "card"})
    
    # Short URL click stats
    short_urls = await db.short_urls.find(
        {"user_id": user_id, "link_type": {"$regex": "^seo_"}}
    ).to_list(100)
    
    total_link_clicks = sum(s.get("click_count", 0) for s in short_urls)
    
    return {
        "card_visits": card_stats.get("total_visits", 0) if card_stats else 0,
        "last_visit": card_stats.get("last_visit", "").isoformat() if card_stats and hasattr(card_stats.get("last_visit"), "isoformat") else None,
        "recent_sources": card_stats.get("recent_sources", []) if card_stats else [],
        "total_link_clicks": total_link_clicks,
        "active_short_urls": len(short_urls),
    }


# ─── SEO Health Score ──────────────────────────────────────────────

@router.get("/health-score/{user_id}")
async def seo_health_score(user_id: str):
    """Calculate a comprehensive SEO/AEO health score (0-100) for a user."""
    db = get_db()

    # Validate user_id format
    if not user_id or user_id == "undefined" or len(user_id) != 24:
        return {"error": "Invalid user ID"}
    
    try:
        user = await db.users.find_one(
            {"_id": ObjectId(user_id)},
            {"password": 0}
        )
    except Exception:
        return {"error": "Invalid user ID format"}
        
    if not user:
        return {"error": "User not found"}

    # Auto-generate SEO slug if missing
    if not user.get("seo_slug") and user.get("name"):
        import re
        base_slug = re.sub(r'[^a-z0-9]+', '-', user["name"].lower()).strip('-')
        existing = await db.users.find_one({"seo_slug": base_slug, "_id": {"$ne": user["_id"]}})
        slug = f"{base_slug}-{str(user['_id'])[-4:]}" if existing else base_slug
        await db.users.update_one({"_id": user["_id"]}, {"$set": {"seo_slug": slug}})
        user["seo_slug"] = slug

    store_id = user.get("store_id")
    store = await db.stores.find_one({"store_id": store_id}) if store_id else None

    # ── Factor 1: Profile Completeness (20 pts) ────────────────────
    profile_checks = {
        "profile_photo": bool(user.get("photo_url") or user.get("profile_image")),
        "bio": bool((user.get("persona", {}) or {}).get("bio") or user.get("bio")),
        "phone": bool(user.get("phone")),
        "title": bool(user.get("title")),
        "seo_slug": bool(user.get("seo_slug")),
        "social_links": bool(user.get("social_links") and any(v for v in (user.get("social_links") or {}).values())),
    }
    profile_filled = sum(1 for v in profile_checks.values() if v)
    profile_score = round((profile_filled / len(profile_checks)) * 20)
    profile_tips = []
    tip_map = {
        "profile_photo": {"tip": "Add a professional profile photo in Hub > Settings > My Profile", "points": 3},
        "bio": {"tip": "Write a personal bio in Hub > Settings > AI Persona", "points": 3},
        "phone": {"tip": "Add your phone number in Hub > Settings > My Profile", "points": 3},
        "title": {"tip": "Set your job title in Hub > Settings > My Profile", "points": 3},
        "seo_slug": {"tip": "Your SEO-friendly URL has been auto-generated! Refresh to update.", "points": 4},
        "social_links": {"tip": "Connect social media profiles in Hub > Settings > My Profile", "points": 4},
    }
    for key, passed in profile_checks.items():
        if not passed:
            profile_tips.append(tip_map[key])

    # ── Factor 2: Review Strength (20 pts) ─────────────────────────
    reviews = await db.customer_feedback.find({
        "salesperson_id": user_id,
        "approved": True,
        "rating": {"$gte": 1}
    }).to_list(200)
    review_count = len(reviews)
    avg_rating = round(sum(r.get("rating", 5) for r in reviews) / review_count, 1) if review_count else 0

    # Scale: 0 reviews = 0, 5+ reviews = full count points (10), 4.5+ rating = full rating points (10)
    count_pts = min(review_count / 5, 1.0) * 10
    rating_pts = (avg_rating / 5.0) * 10 if review_count > 0 else 0
    review_score = round(count_pts + rating_pts)
    review_tips = []
    if review_count < 5:
        review_tips.append({"tip": f"Get {5 - review_count} more reviews to reach 'Strong' status", "points": round((5 - review_count) / 5 * 10)})
    if review_count > 0 and avg_rating < 4.5:
        review_tips.append({"tip": "Focus on 5-star experiences to boost your average rating", "points": round((4.5 - avg_rating) / 5 * 10)})

    # ── Factor 3: Content Distribution (20 pts) ────────────────────
    card_stats = await db.seo_stats.find_one({"reference_id": user_id, "page_type": "card"})
    card_visits = card_stats.get("total_visits", 0) if card_stats else 0

    short_urls = await db.short_urls.find(
        {"user_id": user_id}
    ).to_list(200)
    total_link_clicks = sum(s.get("click_count", 0) for s in short_urls)
    active_links = len([s for s in short_urls if s.get("click_count", 0) > 0])

    # card shares from tasks or messages
    shares_count = await db.tasks.count_documents({
        "assigned_to": user_id,
        "type": {"$in": ["card_share", "digital_card_share"]}
    })

    # Scale: 10+ visits = full (8pts), 5+ active links = full (6pts), 5+ shares = full (6pts)
    visit_pts = min(card_visits / 10, 1.0) * 8
    link_pts = min(active_links / 5, 1.0) * 6
    share_pts = min(shares_count / 5, 1.0) * 6
    distribution_score = round(visit_pts + link_pts + share_pts)
    distribution_tips = []
    if card_visits < 10:
        distribution_tips.append({"tip": "Share your digital card to drive more page views", "points": round((1 - min(card_visits / 10, 1.0)) * 8)})
    if active_links < 5:
        distribution_tips.append({"tip": "Create and share tracking links to monitor engagement", "points": round((1 - min(active_links / 5, 1.0)) * 6)})

    # ── Factor 4: Search Visibility (20 pts) ───────────────────────
    # Based on organic/direct visits and source diversity
    recent_sources = card_stats.get("recent_sources", []) if card_stats else []
    organic_visits = sum(1 for s in recent_sources if s.get("source") in ["organic", "direct", "google", "bing"])
    unique_sources = len(set(s.get("source", "unknown") for s in recent_sources)) if recent_sources else 0

    # Also check if user has schema.org data setup (store exists)
    has_store_schema = bool(store and store.get("store_name"))
    has_person_schema = bool(user.get("name") and user.get("seo_slug"))

    # Scale: 10+ organic visits = full (8pts), 3+ unique sources = full (4pts), schema checks (8pts)
    organic_pts = min(organic_visits / 10, 1.0) * 8
    source_pts = min(unique_sources / 3, 1.0) * 4
    schema_pts = (4 if has_person_schema else 0) + (4 if has_store_schema else 0)
    visibility_score = round(organic_pts + source_pts + schema_pts)
    visibility_tips = []
    if not has_person_schema:
        visibility_tips.append({"tip": "Complete your profile & SEO slug to enable Person schema markup", "points": 4})
    if organic_visits < 10:
        visibility_tips.append({"tip": "Boost organic traffic by sharing your public profile on social media", "points": round((1 - min(organic_visits / 10, 1.0)) * 8)})

    # ── Factor 5: Freshness & Activity (20 pts) ───────────────────
    stats = user.get("stats", {})
    contacts_added = stats.get("contacts_added", 0)
    messages_sent = stats.get("messages_sent", 0)

    # Recent activity: contacts added in last 30 days
    thirty_days_ago = datetime.now(timezone.utc).isoformat()[:10]
    recent_contacts = await db.contacts.count_documents({
        "user_id": user_id,
        "created_at": {"$gte": thirty_days_ago}
    })
    recent_messages = await db.messages.count_documents({
        "user_id": user_id,
        "created_at": {"$gte": thirty_days_ago}
    })

    # Scale: 10+ contacts this month (8pts), 20+ messages this month (8pts), login recency (4pts)
    contact_pts = min(recent_contacts / 10, 1.0) * 8
    msg_pts = min(recent_messages / 20, 1.0) * 8
    last_login = user.get("last_login")
    login_recency = 4  # assume recent unless we know otherwise
    if last_login:
        try:
            if isinstance(last_login, str):
                ll = datetime.fromisoformat(last_login.replace("Z", "+00:00"))
            else:
                ll = last_login
            days_since = (datetime.now(timezone.utc) - ll.replace(tzinfo=timezone.utc)).days
            login_recency = max(0, 4 - days_since)  # lose 1pt per day inactive
        except Exception:
            login_recency = 2
    freshness_score = round(contact_pts + msg_pts + login_recency)
    freshness_tips = []
    if recent_contacts < 10:
        freshness_tips.append({"tip": f"Add {10 - recent_contacts} more contacts this month to maximize freshness", "points": round((1 - min(recent_contacts / 10, 1.0)) * 8)})
    if recent_messages < 20:
        freshness_tips.append({"tip": "Send more messages to show active engagement signals", "points": round((1 - min(recent_messages / 20, 1.0)) * 8)})

    # ── Total Score ────────────────────────────────────────────────
    total_score = min(profile_score + review_score + distribution_score + visibility_score + freshness_score, 100)

    # Grade
    if total_score >= 80:
        grade = "Excellent"
        grade_color = "#34C759"
    elif total_score >= 60:
        grade = "Good"
        grade_color = "#007AFF"
    elif total_score >= 40:
        grade = "Fair"
        grade_color = "#FF9500"
    elif total_score >= 20:
        grade = "Needs Work"
        grade_color = "#FF3B30"
    else:
        grade = "Getting Started"
        grade_color = "#8E8E93"

    # Collect all tips sorted by points (highest impact first)
    all_tips = profile_tips + review_tips + distribution_tips + visibility_tips + freshness_tips
    all_tips.sort(key=lambda t: t["points"], reverse=True)

    return {
        "total_score": total_score,
        "grade": grade,
        "grade_color": grade_color,
        "factors": {
            "profile": {"score": profile_score, "max": 20, "label": "Profile Completeness", "checks": profile_checks},
            "reviews": {"score": review_score, "max": 20, "label": "Review Strength", "details": {"count": review_count, "avg_rating": avg_rating}},
            "distribution": {"score": distribution_score, "max": 20, "label": "Content Distribution", "details": {"card_visits": card_visits, "active_links": active_links, "shares": shares_count}},
            "visibility": {"score": visibility_score, "max": 20, "label": "Search Visibility", "details": {"organic_visits": organic_visits, "unique_sources": unique_sources, "has_person_schema": has_person_schema, "has_store_schema": has_store_schema}},
            "freshness": {"score": freshness_score, "max": 20, "label": "Activity & Freshness", "details": {"recent_contacts": recent_contacts, "recent_messages": recent_messages, "login_recency_pts": login_recency}},
        },
        "tips": all_tips[:6],
        "user_name": user.get("name", ""),
    }


@router.get("/health-score/team/{store_id}")
async def seo_team_scores(store_id: str):
    """Get SEO health scores for all active team members in a store."""
    if not store_id or store_id in ("undefined", "null", "None"):
        return {"team": []}
    db = get_db()

    members = await db.users.find(
        {"store_id": store_id, "is_active": True, "status": {"$ne": "deleted"}},
        {"password": 0}
    ).to_list(500)

    results = []
    for member in members:
        uid = str(member["_id"])
        # Use the same scoring logic as the individual endpoint
        try:
            score_data = await seo_health_score(uid)
            if "error" in score_data:
                continue
            results.append({
                "user_id": uid,
                "name": member.get("name", ""),
                "title": member.get("title", ""),
                "photo": resolve_user_photo(member),
                "score": score_data["total_score"],
                "grade": score_data["grade"],
                "review_count": score_data["factors"]["reviews"]["details"]["count"],
                "card_visits": score_data["factors"]["distribution"]["details"]["card_visits"],
            })
        except Exception:
            continue

    results.sort(key=lambda x: x["score"], reverse=True)
    return {"team": results}
