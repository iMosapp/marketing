"""
GEO Router — Generative Engine Optimization
Scores how well a rep will appear when AI tools (ChatGPT, Gemini, Perplexity,
Google AI Overviews) answer questions like "who is the best car salesperson near me?"

GEO is distinct from SEO/AEO:
- SEO  = search engine rankings (Google organic results)
- AEO  = answer engine snippets (featured snippets, People Also Ask)
- GEO  = generative AI citation (LLM answers, AI chatbot recommendations)

The key to GEO: AI models synthesize answers from structured, authoritative,
consistent content. Every factor here signals to LLMs that you are a real,
trustworthy, relevant expert worth citing.
"""
from fastapi import APIRouter, Header
from datetime import datetime, timezone
from bson import ObjectId
import logging
from cachetools import TTLCache

from routers.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/geo", tags=["geo"])

_geo_cache: TTLCache = TTLCache(maxsize=1000, ttl=300)  # 5-min TTL


# ─── Health Score ────────────────────────────────────────────────────────────

@router.get("/health-score/{user_id}")
async def geo_health_score(user_id: str, skip_cache: bool = False):
    """Return the GEO health score for a user. Cached 5 min."""
    if not skip_cache and user_id in _geo_cache:
        return _geo_cache[user_id]
    result = await _compute_geo_score(user_id)
    if "error" not in result:
        _geo_cache[user_id] = result
    return result


@router.get("/health-score/team/{store_id}")
async def geo_team_scores(store_id: str):
    """Return GEO scores for all reps in a store."""
    db = get_db()
    try:
        members = await db.users.find(
            {"store_id": store_id, "status": {"$ne": "deactivated"}},
            {"_id": 1, "name": 1, "title": 1}
        ).limit(50).to_list(50)
    except Exception:
        return {"team": []}

    results = []
    for m in members:
        uid = str(m["_id"])
        score_data = _geo_cache.get(uid) or await _compute_geo_score(uid)
        if "error" not in score_data:
            _geo_cache[uid] = score_data
            results.append({
                "user_id":   uid,
                "name":      m.get("name", ""),
                "title":     m.get("title", ""),
                "score":     score_data["total_score"],
                "grade":     score_data["grade"],
                "grade_color": score_data["grade_color"],
                "ai_identity": score_data["factors"]["ai_identity"]["score"],
                "citation":    score_data["factors"]["citation"]["score"],
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return {"team": results}


# ─── Core Scoring Engine ─────────────────────────────────────────────────────

async def _compute_geo_score(user_id: str) -> dict:
    """
    Compute GEO score across 5 factors:
      1. AI Identity Completeness  (20 pts)
      2. Conversational Signals    (20 pts)
      3. AI Content Distribution   (20 pts)
      4. Citation Authority        (20 pts)
      5. Generative Freshness      (20 pts)
    Total: 100 pts
    """
    db = get_db()
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)}, {"password": 0})
    except Exception:
        return {"error": "Invalid user ID"}
    if not user:
        return {"error": "User not found"}

    store_id = user.get("store_id")
    store = None
    if store_id:
        try:
            store = await db.stores.find_one({"_id": ObjectId(store_id)})
        except Exception:
            pass

    persona  = user.get("persona") or {}
    social   = user.get("social_links") or {}
    now_utc  = datetime.now(timezone.utc)
    thirty_ago = now_utc.replace(day=max(1, now_utc.day - 30)).isoformat()

    # ── Factor 1: AI Identity Completeness (20 pts) ──────────────────────────
    # LLMs rely on consistent, rich entity data to identify and cite a person.
    # NAP consistency, structured identity, and cross-platform linking.
    identity_checks = {
        "full_name":    bool(user.get("name") and len(user.get("name", "")) > 3),
        "job_title":    bool(user.get("title")),
        "phone":        bool(user.get("phone") or user.get("twilio_number") or user.get("mvpline_number")),
        "profile_photo":bool(user.get("photo_url")),
        "bio":          bool(persona.get("bio") and len(persona.get("bio", "")) > 30),
        "seo_slug":     bool(user.get("seo_slug")),
        "employer":     bool(store and store.get("name")),
        "location":     bool(store and (store.get("city") or store.get("address"))),
        "linkedin":     bool(social.get("linkedin")),
        "social_graph": bool(any(v for k, v in social.items() if k in ("facebook", "instagram", "twitter", "x"))),
    }
    id_filled   = sum(1 for v in identity_checks.values() if v)
    id_score    = round((id_filled / len(identity_checks)) * 20)
    id_tips = []
    id_tip_map = {
        "full_name":    {"tip": "Use your full name exactly as customers search for you", "points": 2, "route": "/my-account"},
        "job_title":    {"tip": "Add your exact job title — AI uses this to categorize your expertise", "points": 2, "route": "/my-account"},
        "phone":        {"tip": "Add a contact number — part of NAP consistency AI uses to verify you", "points": 2, "route": "/my-account"},
        "profile_photo":{"tip": "Add a professional photo — visual identity anchors your digital presence", "points": 2, "route": "/my-account"},
        "bio":          {"tip": "Write a 50+ word bio with your name, city, and specialty — AI reads this for context", "points": 2, "route": "/settings/persona"},
        "seo_slug":     {"tip": "Generate your public profile URL to make your page crawlable", "points": 2, "route": "/my-account"},
        "employer":     {"tip": "Link your store profile — employer association is a major AI trust signal", "points": 2, "route": ""},
        "location":     {"tip": "Add your store city/address — local context drives geo-relevant AI answers", "points": 2, "route": ""},
        "linkedin":     {"tip": "Connect LinkedIn — AI engines heavily weight LinkedIn as an authority source", "points": 2, "route": "/settings/brand-kit"},
        "social_graph": {"tip": "Connect social profiles (Facebook, Instagram) — cross-platform presence = stronger entity", "points": 2, "route": "/settings/brand-kit"},
    }
    for key, passed in identity_checks.items():
        if not passed:
            id_tips.append(id_tip_map[key])

    # ── Factor 2: Conversational Signals (20 pts) ─────────────────────────────
    # Generative AI is trained on conversational text. Reviews, Q&A-style content,
    # and natural language bios are the signals LLMs weight most heavily.
    review_agg = await db.customer_feedback.aggregate([
        {"$match": {"salesperson_id": user_id, "approved": True}},
        {"$group": {"_id": None, "count": {"$sum": 1}, "avg": {"$avg": "$rating"}}}
    ]).to_list(1)
    review_count  = review_agg[0]["count"] if review_agg else 0
    avg_rating    = round(review_agg[0]["avg"], 1) if review_agg else 0.0

    bio_text      = persona.get("bio", "") or ""
    bio_word_count = len(bio_text.split())
    has_qa_bio    = bio_word_count >= 50        # 50+ words reads as conversational
    has_specialty = bool(persona.get("specialties") or persona.get("tone"))
    has_catchphrase = bool(persona.get("personal_motto") or persona.get("custom_phrases"))

    review_pts    = min(review_count / 10, 1.0) * 10   # up to 10 pts
    rating_pts    = (avg_rating / 5.0) * 4 if review_count > 0 else 0  # up to 4 pts
    bio_pts       = (3 if has_qa_bio else 0) + (1 if has_specialty else 0) + (1 if has_catchphrase else 0) + min(bio_word_count / 100, 1.0)
    conv_score    = round(min(review_pts + rating_pts + bio_pts, 20))
    conv_tips = []
    if review_count < 5:
        conv_tips.append({"tip": f"Get {5 - review_count} more customer reviews — reviews are the #1 AI citation signal", "points": round((5 - review_count) / 5 * 10), "route": "/settings/review-links"})
    if avg_rating < 4.5 and review_count > 0:
        conv_tips.append({"tip": "Aim for 4.5+ star average — AI tools prioritize top-rated professionals", "points": 3, "route": ""})
    if not has_qa_bio:
        conv_tips.append({"tip": f"Expand your bio to 50+ words (currently {bio_word_count}) — longer, natural language bios get cited by AI", "points": 2, "route": "/settings/persona"})
    if not has_specialty:
        conv_tips.append({"tip": "Add your specialties to your AI Persona — AI uses this for recommendation matching", "points": 1, "route": "/settings/persona"})

    # ── Factor 3: AI Content Distribution (20 pts) ───────────────────────────
    # Every link you share that contains structured JSON-LD is a citation seed.
    # The more AI-readable pages you distribute, the more surface area for citation.
    card_stats   = await db.seo_stats.find_one({"reference_id": user_id, "page_type": "card"}) or {}
    card_visits  = card_stats.get("total_visits", 0)

    link_agg = await db.short_urls.aggregate([
        {"$match": {"user_id": user_id, "click_count": {"$gt": 0}}},
        {"$group": {"_id": None, "total_clicks": {"$sum": "$click_count"}, "links": {"$sum": 1}}}
    ]).to_list(1)
    total_clicks  = link_agg[0]["total_clicks"] if link_agg else 0
    active_links  = link_agg[0]["links"] if link_agg else 0

    campaign_count = await db.campaigns.count_documents({"user_id": user_id, "active": True})
    enrollments   = await db.campaign_enrollments.count_documents({"user_id": user_id, "status": "active"})

    visit_pts    = min(card_visits / 20, 1.0) * 7
    click_pts    = min(total_clicks / 50, 1.0) * 5
    campaign_pts = min(campaign_count / 3, 1.0) * 4 + min(enrollments / 10, 1.0) * 4
    dist_score   = round(min(visit_pts + click_pts + campaign_pts, 20))
    dist_tips = []
    if card_visits < 20:
        dist_tips.append({"tip": "Share your digital card more — each share creates a crawlable, AI-readable page", "points": round((1 - min(card_visits/20,1)) * 7), "route": "/quick-send/digitalcard"})
    if active_links < 5:
        dist_tips.append({"tip": "Create tracking links with your content — AI indexes pages linked from your profiles", "points": round((1 - min(active_links/5,1)) * 5), "route": "/settings/link-page"})
    if campaign_count < 3:
        dist_tips.append({"tip": "Run active SMS campaigns — consistent outreach builds a real-world engagement signal AI detects", "points": 4, "route": "/campaigns"})

    # ── Factor 4: Citation Authority (20 pts) ─────────────────────────────────
    # AI models heavily weight cross-platform corroboration. The more places
    # your name + employer + title appear consistently, the higher your
    # "entity authority" in AI knowledge graphs.
    has_store_website = bool(store and store.get("website"))
    has_store_brand   = bool(store and store.get("logo_url"))
    has_congrats      = await db.congrats_cards_sent.count_documents({"user_id": user_id}) > 0
    has_review_link   = bool(user.get("review_link") or (store and store.get("review_link")))
    has_vcf_downloads = card_stats.get("vcf_downloads", 0) > 0
    has_link_page     = bool(user.get("link_page_enabled") or user.get("username"))
    has_digital_card  = bool(user.get("has_digital_card") or card_visits > 0)
    showcase_count    = await db.congrats_cards_sent.count_documents({"user_id": user_id})

    auth_checks = {
        "store_website":    has_store_website,
        "review_profile":   has_review_link,
        "linkedin":         bool(social.get("linkedin")),
        "digital_card":     has_digital_card,
        "link_page":        has_link_page,
        "vcf_downloads":    has_vcf_downloads,
        "store_brand":      has_store_brand,
        "congrats_sent":    has_congrats,
    }
    auth_filled  = sum(1 for v in auth_checks.values() if v)
    auth_score   = round((auth_filled / len(auth_checks)) * 20)
    auth_tips = []
    auth_tip_map = {
        "store_website":    {"tip": "Add your dealership's website — a verified employer domain is a top AI trust signal", "points": 3, "route": ""},
        "review_profile":   {"tip": "Add your Google/DealerRater review link — external review platforms validate your existence", "points": 3, "route": "/settings/review-links"},
        "linkedin":         {"tip": "Connect LinkedIn — it is the highest-authority professional network AI cites", "points": 3, "route": "/settings/brand-kit"},
        "digital_card":     {"tip": "Activate your digital business card — it becomes a Schema.org/Person page AI can index", "points": 2, "route": "/quick-send/digitalcard"},
        "link_page":        {"tip": "Set up your public link page to create another AI-readable citation surface", "points": 2, "route": "/settings/link-page"},
        "vcf_downloads":    {"tip": "Get customers to download your vCard — each save is a real-world entity confirmation", "points": 2, "route": ""},
        "store_brand":      {"tip": "Add your store's logo and branding to create visual entity consistency", "points": 2, "route": ""},
        "congrats_sent":    {"tip": "Send congrats cards to create relationship signals that appear in customer testimonials", "points": 1, "route": ""},
    }
    for key, passed in auth_checks.items():
        if not passed:
            auth_tips.append(auth_tip_map[key])

    # ── Factor 5: Generative Freshness (20 pts) ──────────────────────────────
    # AI models weight recent, active digital footprints over stale profiles.
    # Consistent outreach, new content, and regular app activity = a live entity.
    recent_contacts  = await db.contacts.count_documents({"user_id": user_id, "created_at": {"$gte": thirty_ago}})
    recent_messages  = await db.messages.count_documents({"user_id": user_id, "created_at": {"$gte": thirty_ago}})
    recent_events    = await db.contact_events.count_documents({"user_id": user_id, "timestamp": {"$gte": datetime.fromisoformat(thirty_ago.replace("Z",""))}})

    last_login = user.get("last_login")
    login_pts  = 4
    if last_login:
        try:
            ll = last_login if isinstance(last_login, datetime) else datetime.fromisoformat(str(last_login).replace("Z", "+00:00"))
            days = (now_utc - ll.replace(tzinfo=timezone.utc)).days
            login_pts = max(0, 4 - days)
        except Exception:
            login_pts = 2

    contact_pts = min(recent_contacts / 10, 1.0) * 6
    message_pts = min(recent_messages / 20, 1.0) * 6
    event_pts   = min(recent_events / 30, 1.0) * 4
    fresh_score = round(min(contact_pts + message_pts + event_pts + login_pts, 20))
    fresh_tips = []
    if recent_contacts < 5:
        fresh_tips.append({"tip": f"Add {5 - recent_contacts} more contacts this month — new relationships signal an active practitioner", "points": round((1 - min(recent_contacts/10,1)) * 6), "route": ""})
    if recent_messages < 10:
        fresh_tips.append({"tip": "Send more messages — AI engines detect active, engaged professionals", "points": round((1 - min(recent_messages/20,1)) * 6), "route": ""})

    # ── Total ────────────────────────────────────────────────────────────────
    total = min(id_score + conv_score + dist_score + auth_score + fresh_score, 100)

    if total >= 80:   grade, gc = "AI-Ready",      "#34C759"
    elif total >= 60: grade, gc = "Building",       "#007AFF"
    elif total >= 40: grade, gc = "Developing",     "#FF9500"
    elif total >= 20: grade, gc = "Needs Work",     "#FF3B30"
    else:             grade, gc = "Just Starting",  "#8E8E93"

    all_tips = (id_tips + conv_tips + dist_tips + auth_tips + fresh_tips)
    all_tips.sort(key=lambda t: t["points"], reverse=True)

    return {
        "total_score": total,
        "grade":       grade,
        "grade_color": gc,
        "user_name":   user.get("name", ""),
        "factors": {
            "ai_identity":   {"score": id_score,    "max": 20, "label": "AI Identity",         "checks": identity_checks},
            "conversational":{"score": conv_score,   "max": 20, "label": "Conversational Signals","details": {"review_count": review_count, "avg_rating": avg_rating, "bio_words": bio_word_count}},
            "distribution":  {"score": dist_score,   "max": 20, "label": "AI Distribution",     "details": {"card_visits": card_visits, "total_clicks": total_clicks, "active_campaigns": campaign_count}},
            "citation":      {"score": auth_score,   "max": 20, "label": "Citation Authority",   "checks": auth_checks},
            "freshness":     {"score": fresh_score,  "max": 20, "label": "Generative Freshness", "details": {"recent_contacts": recent_contacts, "recent_messages": recent_messages, "login_pts": login_pts}},
        },
        "tips": all_tips[:6],
    }
