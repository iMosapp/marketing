"""
Demo Request Router - Captures leads from the marketing site, ads, and in-app CTAs.
Tracks source, channel, UTM parameters for full-funnel attribution.
"""
from fastapi import APIRouter
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from typing import Optional

from routers.database import get_db

router = APIRouter(prefix="/demo-requests", tags=["demo-requests"])

# Channel classification based on UTM or source
CHANNEL_MAP = {
    "facebook": "paid_social",
    "instagram": "paid_social",
    "tiktok": "paid_social",
    "linkedin": "paid_social",
    "twitter": "paid_social",
    "x": "paid_social",
    "snapchat": "paid_social",
    "youtube": "paid_social",
    "google": "paid_search",
    "bing": "paid_search",
    "email": "email",
    "newsletter": "email",
}


def classify_channel(source: str, utm_source: str, utm_medium: str) -> str:
    """Auto-classify the lead channel from UTM params or source."""
    utm_src = (utm_source or "").lower()
    utm_med = (utm_medium or "").lower()
    src = (source or "").lower()

    if utm_src in CHANNEL_MAP:
        return CHANNEL_MAP[utm_src]
    if "cpc" in utm_med or "ppc" in utm_med or "paid" in utm_med:
        return "paid_search"
    if "social" in utm_med:
        return "paid_social"
    if "email" in utm_med:
        return "email"
    if "referral" in utm_med:
        return "referral"
    if "sales_presentation" in src:
        return "sales_presentation"
    if "imos" in src:
        return "in_app"
    if src:
        return "organic"
    return "direct"


def parse_source_page(source: str) -> str:
    """Extract the page name from a source like 'digital_card_hero'."""
    if not source:
        return "unknown"
    parts = source.rsplit("_", 1)
    if len(parts) == 2 and parts[1] in ("nav", "hero", "cta", "footer"):
        return parts[0]
    return source


def parse_source_position(source: str) -> str:
    """Extract the CTA position from a source like 'digital_card_hero'."""
    if not source:
        return "unknown"
    parts = source.rsplit("_", 1)
    if len(parts) == 2 and parts[1] in ("nav", "hero", "cta", "footer"):
        return parts[1]
    return "direct"


def _classify_referrer_type(ref_code: str, role: str) -> str:
    """Classify the referrer type based on ref code prefix or role."""
    code = ref_code.upper()
    if code.startswith("PARTNER_"):
        return "partner"
    if code.startswith("RESELLER_"):
        return "reseller"
    if code.startswith("REF_"):
        return "referral"
    if code.startswith("TEAM_"):
        return "internal"
    if role in ("super_admin", "admin"):
        return "internal"
    return "user"


@router.post("")
async def create_demo_request(data: dict):
    """Capture a demo request with full attribution tracking."""
    db = get_db()

    required = ["name", "email"]
    for field in required:
        if not data.get(field):
            return {"status": "error", "message": f"{field} is required"}

    source = (data.get("source") or data.get("lead_source") or "").strip()
    utm_source = data.get("utm_source", "").strip()
    utm_medium = data.get("utm_medium", "").strip()
    utm_campaign = data.get("utm_campaign", "").strip()
    utm_content = data.get("utm_content", "").strip()
    utm_term = data.get("utm_term", "").strip()

    demo = {
        "name": data.get("name", "").strip(),
        "email": data.get("email", "").strip().lower(),
        "phone": data.get("phone", "").strip(),
        "company": data.get("company", "").strip(),
        "team_size": data.get("team_size", "").strip(),
        "message": data.get("message", "").strip(),
        "source": source,
        "source_page": parse_source_page(source),
        "source_position": parse_source_position(source),
        "channel": classify_channel(source, utm_source, utm_medium),
        "utm_source": utm_source,
        "utm_medium": utm_medium,
        "utm_campaign": utm_campaign,
        "utm_content": utm_content,
        "utm_term": utm_term,
        "referrer": data.get("referrer", "").strip(),
        "referred_by": data.get("ref", "").strip(),
        "business_type": data.get("business_type", "").strip(),
        "status": "new",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Resolve ref code to user if present
    ref_code = data.get("ref", "").strip()
    if ref_code:
        ref_user = await db.users.find_one({"ref_code": ref_code}, {"_id": 1, "name": 1, "role": 1, "organization_id": 1})
        if ref_user:
            demo["referred_by_user_id"] = str(ref_user["_id"])
            demo["referred_by_name"] = ref_user.get("name", "")
            demo["referred_by_role"] = ref_user.get("role", "")
            demo["referrer_type"] = _classify_referrer_type(ref_code, ref_user.get("role", ""))

    result = await db.demo_requests.insert_one({**demo, "_id": ObjectId()})
    demo_id = str(result.inserted_id)

    # Create lead notification for the referring salesperson AND all admins
    lead_name = demo["name"]
    lead_source = demo.get("source", "direct")
    lead_channel = demo.get("channel", "unknown")
    utm_info = f"utm_source={demo.get('utm_source', '')}" if demo.get("utm_source") else ""
    form_details = f"Name: {lead_name}"
    if demo.get("email"):
        form_details += f"\nEmail: {demo['email']}"
    if demo.get("phone"):
        form_details += f"\nPhone: {demo['phone']}"
    if demo.get("company"):
        form_details += f"\nCompany: {demo['company']}"
    if demo.get("message"):
        form_details += f"\nMessage: {demo['message'][:200]}"
    if demo.get("source"):
        form_details += f"\nSource: {demo['source']}"
    if utm_info:
        form_details += f"\n{utm_info}"
    if demo.get("referred_by_name"):
        form_details += f"\nReferred by: {demo['referred_by_name']}"

    notif_body = f"{lead_name} submitted a form via {lead_source or 'direct'}."
    if demo.get("referred_by_name"):
        notif_body += f" Referred by {demo['referred_by_name']}."

    # Notify the referring salesperson
    notify_user_ids = set()
    if demo.get("referred_by_user_id"):
        notify_user_ids.add(demo["referred_by_user_id"])

    # Also notify all admins/super_admins in the same org
    org_id = None
    if demo.get("referred_by_user_id"):
        ref_user_full = await db.users.find_one({"_id": ObjectId(demo["referred_by_user_id"])}, {"organization_id": 1})
        if ref_user_full:
            org_id = ref_user_full.get("organization_id")
    if org_id:
        async for admin in db.users.find({"organization_id": org_id, "role": {"$in": ["admin", "super_admin"]}}, {"_id": 1}):
            notify_user_ids.add(str(admin["_id"]))
    else:
        # No org context — notify all super admins
        async for admin in db.users.find({"role": "super_admin"}, {"_id": 1}):
            notify_user_ids.add(str(admin["_id"]))

    for uid in notify_user_ids:
        await db.notifications.insert_one({
            "user_id": uid,
            "type": "new_lead",
            "title": f"New Lead: {lead_name}",
            "message": notif_body,
            "form_details": form_details,
            "lead_name": lead_name,
            "lead_email": demo.get("email", ""),
            "lead_phone": demo.get("phone", ""),
            "lead_source": lead_source,
            "lead_channel": lead_channel,
            "demo_request_id": demo_id,
            "referred_by_user_id": demo.get("referred_by_user_id", ""),
            "referred_by_name": demo.get("referred_by_name", ""),
            "contact_name": lead_name,
            "action_required": True,
            "read": False,
            "dismissed": False,
            "created_at": datetime.now(timezone.utc),
        })
        # Send push notification for new lead
        try:
            from routers.push_notifications import send_push_to_user
            import asyncio
            asyncio.create_task(
                send_push_to_user(uid, f"New Lead: {lead_name}", notif_body, "/admin/hot-leads", "person.fill.badge.plus")
            )
        except Exception:
            pass

    # === CREATE CONTACT + INBOX THREAD FOR FAST RESPONSE ===
    try:
        # Pretty source name for display
        source_labels = {
            "seo_page": "SEO & AEO", "store_reviews_page": "Store Reviews",
            "digital_card_page": "Digital Cards", "showcase_page": "Showcase",
            "reviews_page": "Reviews", "inbox_page": "Inbox",
            "congrats_cards_page": "Congrats Cards", "automations_page": "Automations",
            "jessi_ai_page": "Jessi AI", "leaderboard_page": "Leaderboards",
            "homepage": "Homepage", "pricing_page": "Pricing",
            "organizations_page": "For Organizations", "individuals_page": "For Individuals",
            "features_page": "Features", "dealers_page": "Automotive",
            "pitch_powersports": "Powersports", "pitch_real_estate": "Real Estate",
            "pitch_salons": "Salons & Spas", "pitch_restaurants": "Restaurants",
            "pitch_home_services": "Home Services", "pitch_fitness": "Fitness",
            "pitch_insurance": "Insurance & Financial", "pitch_medical": "Medical & Dental",
        }
        pretty_source = source_labels.get(lead_source, lead_source.replace("_", " ").title() if lead_source else "Website")

        # Find or pick owner — prefer referring salesperson, else first admin notified
        owner_id = demo.get("referred_by_user_id") or (list(notify_user_ids)[0] if notify_user_ids else None)

        if owner_id:
            # Create contact if email/phone doesn't already exist
            contact_filter = []
            if demo.get("email"):
                contact_filter.append({"email": demo["email"]})
            if demo.get("phone"):
                contact_filter.append({"phone": demo["phone"]})

            existing_contact = None
            if contact_filter:
                existing_contact = await db.contacts.find_one({
                    "user_id": owner_id,
                    "$or": contact_filter
                }, {"_id": 1})

            if existing_contact:
                contact_id = str(existing_contact["_id"])
            else:
                # Split name
                name_parts = lead_name.split(" ", 1)
                new_contact = {
                    "user_id": owner_id,
                    "first_name": name_parts[0] if name_parts else lead_name,
                    "last_name": name_parts[1] if len(name_parts) > 1 else "",
                    "email": demo.get("email", ""),
                    "phone": demo.get("phone", ""),
                    "company": demo.get("company", ""),
                    "source": f"demo_form_{lead_source}",
                    "tags": ["new-lead", "demo-request"],
                    "notes": f"Submitted demo form from {pretty_source} page",
                    "created_at": datetime.now(timezone.utc),
                }
                contact_result = await db.contacts.insert_one(new_contact)
                contact_id = str(contact_result.inserted_id)

            # Create inbox conversation
            existing_conv = await db.conversations.find_one({
                "user_id": owner_id,
                "contact_id": contact_id,
            })

            if existing_conv:
                conv_id = str(existing_conv["_id"])
                # Update it to unread + high priority
                await db.conversations.update_one(
                    {"_id": existing_conv["_id"]},
                    {"$set": {
                        "unread": True,
                        "unread_count": (existing_conv.get("unread_count", 0) or 0) + 1,
                        "last_message_at": datetime.now(timezone.utc),
                        "ai_outcome": "new_lead",
                        "ai_outcome_priority": 1,
                    }}
                )
            else:
                new_conv = {
                    "user_id": owner_id,
                    "contact_id": contact_id,
                    "contact_phone": demo.get("phone", ""),
                    "status": "active",
                    "unread": True,
                    "unread_count": 1,
                    "ai_enabled": False,
                    "ai_outcome": "new_lead",
                    "ai_outcome_priority": 1,
                    "needs_assistance": True,
                    "created_at": datetime.now(timezone.utc),
                    "last_message_at": datetime.now(timezone.utc),
                }
                conv_result = await db.conversations.insert_one(new_conv)
                conv_id = str(conv_result.inserted_id)

            # Add the lead info as the first message in the thread
            intro_lines = [f"New lead from {pretty_source}"]
            if demo.get("company"):
                intro_lines.append(f"Company: {demo['company']}")
            if demo.get("email"):
                intro_lines.append(f"Email: {demo['email']}")
            if demo.get("phone"):
                intro_lines.append(f"Phone: {demo['phone']}")
            if demo.get("business_type"):
                intro_lines.append(f"Industry: {demo['business_type']}")
            if demo.get("message"):
                intro_lines.append(f"Message: {demo['message'][:300]}")

            await db.messages.insert_one({
                "conversation_id": conv_id,
                "user_id": owner_id,
                "contact_id": contact_id,
                "direction": "inbound",
                "channel": "form",
                "body": "\n".join(intro_lines),
                "type": "lead_form",
                "read": False,
                "created_at": datetime.now(timezone.utc),
            })

    except Exception as e:
        # Don't fail the demo request if inbox creation fails
        import traceback
        traceback.print_exc()

    return {"status": "success", "message": "Demo request received! We'll be in touch soon."}


@router.get("")
async def list_demo_requests():
    """List all demo requests (admin)."""
    db = get_db()
    requests = []
    async for doc in db.demo_requests.find({}, {"_id": 0}).sort("created_at", -1):
        requests.append(doc)
    return requests


@router.get("/analytics")
async def demo_analytics(days: int = 30):
    """Aggregate demo request analytics for the admin dashboard."""
    db = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # Total counts
    total_all = await db.demo_requests.count_documents({})
    total_period = await db.demo_requests.count_documents({"created_at": {"$gte": cutoff}})
    total_new = await db.demo_requests.count_documents({"status": "new"})

    # Previous period for comparison
    prev_cutoff = (datetime.now(timezone.utc) - timedelta(days=days * 2)).isoformat()
    total_prev = await db.demo_requests.count_documents({
        "created_at": {"$gte": prev_cutoff, "$lt": cutoff}
    })

    # By channel
    channel_pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}}},
        {"$group": {"_id": "$channel", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    channel_stats = []
    async for doc in db.demo_requests.aggregate(channel_pipeline):
        channel_stats.append({"channel": doc["_id"] or "direct", "count": doc["count"]})

    # By source page
    page_pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}}},
        {"$group": {"_id": "$source_page", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    page_stats = []
    async for doc in db.demo_requests.aggregate(page_pipeline):
        page_stats.append({"page": doc["_id"] or "unknown", "count": doc["count"]})

    # By CTA position
    position_pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}}},
        {"$group": {"_id": "$source_position", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    position_stats = []
    async for doc in db.demo_requests.aggregate(position_pipeline):
        position_stats.append({"position": doc["_id"] or "unknown", "count": doc["count"]})

    # By full source (page + position)
    source_pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}}},
        {"$group": {"_id": "$source", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    source_stats = []
    async for doc in db.demo_requests.aggregate(source_pipeline):
        source_stats.append({"source": doc["_id"] or "direct", "count": doc["count"]})

    # By UTM campaign (for paid ads)
    campaign_pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}, "utm_campaign": {"$nin": ["", None]}}},
        {"$group": {
            "_id": {"campaign": "$utm_campaign", "source": "$utm_source", "medium": "$utm_medium"},
            "count": {"$sum": 1},
        }},
        {"$sort": {"count": -1}},
    ]
    campaign_stats = []
    async for doc in db.demo_requests.aggregate(campaign_pipeline):
        campaign_stats.append({
            "campaign": doc["_id"].get("campaign", ""),
            "utm_source": doc["_id"].get("source", ""),
            "utm_medium": doc["_id"].get("medium", ""),
            "count": doc["count"],
        })

    # Daily trend
    daily_pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}}},
        {"$addFields": {"date": {"$substr": ["$created_at", 0, 10]}}},
        {"$group": {"_id": "$date", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    daily_trend = []
    async for doc in db.demo_requests.aggregate(daily_pipeline):
        daily_trend.append({"date": doc["_id"], "count": doc["count"]})

    # Recent requests (last 10)
    recent = []
    async for doc in db.demo_requests.find({}, {"_id": 0}).sort("created_at", -1).limit(10):
        recent.append(doc)

    # By referrer (for attribution to users/partners)
    referrer_pipeline = [
        {"$match": {"created_at": {"$gte": cutoff}, "referred_by": {"$nin": ["", None]}}},
        {"$group": {
            "_id": {"ref_code": "$referred_by", "name": "$referred_by_name", "type": "$referrer_type"},
            "count": {"$sum": 1},
        }},
        {"$sort": {"count": -1}},
    ]
    referrer_stats = []
    async for doc in db.demo_requests.aggregate(referrer_pipeline):
        referrer_stats.append({
            "ref_code": doc["_id"].get("ref_code", ""),
            "name": doc["_id"].get("name", "Unknown"),
            "type": doc["_id"].get("type", "user"),
            "count": doc["count"],
        })

    return {
        "summary": {
            "total_all_time": total_all,
            "total_period": total_period,
            "total_previous_period": total_prev,
            "total_new": total_new,
            "period_days": days,
        },
        "by_channel": channel_stats,
        "by_page": page_stats,
        "by_position": position_stats,
        "by_source": source_stats,
        "by_campaign": campaign_stats,
        "by_referrer": referrer_stats,
        "daily_trend": daily_trend,
        "recent_requests": recent,
    }


@router.patch("/{request_id}/status")
async def update_demo_status(request_id: str, data: dict):
    """Update the status of a demo request (new, contacted, scheduled, closed)."""
    db = get_db()
    status = data.get("status", "").strip()
    if status not in ("new", "contacted", "scheduled", "closed", "lost"):
        return {"status": "error", "message": "Invalid status"}

    result = await db.demo_requests.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    if result.modified_count == 0:
        return {"status": "error", "message": "Request not found"}
    return {"status": "success"}


@router.post("/{request_id}/claim")
async def claim_lead(request_id: str, data: dict):
    """
    Claim a demo request lead: creates a contact from the lead data,
    assigns it to the claiming user, and returns the contact_id with
    a pre-built welcome message ready to send.
    """
    db = get_db()
    user_id = data.get("user_id", "")
    if not user_id:
        return {"status": "error", "message": "user_id is required"}

    # Get the demo request
    demo = await db.demo_requests.find_one({"_id": ObjectId(request_id)})
    if not demo:
        return {"status": "error", "message": "Lead not found"}

    # Check if already claimed
    if demo.get("claimed_by"):
        # Already claimed — return the existing contact
        existing = await db.contacts.find_one({"_id": ObjectId(demo["claimed_contact_id"])})
        if existing:
            return {
                "status": "already_claimed",
                "contact_id": demo["claimed_contact_id"],
                "claimed_by": demo["claimed_by"],
                "prefill_message": _build_lead_welcome(demo, existing),
            }
        return {"status": "error", "message": "Lead already claimed but contact not found"}

    # Get the claiming user's info
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"name": 1, "organization_id": 1, "store_id": 1})
    if not user:
        return {"status": "error", "message": "User not found"}

    # Create a contact from the demo request
    name_parts = (demo.get("name", "") or "").strip().split(" ", 1)
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    contact_doc = {
        "first_name": first_name,
        "last_name": last_name,
        "phone": demo.get("phone", ""),
        "email": demo.get("email", ""),
        "company": demo.get("company", ""),
        "user_id": user_id,
        "organization_id": str(user.get("organization_id", "")),
        "store_id": str(user.get("store_id", "")),
        "ownership_type": "org",
        "source": "lead_form",
        "lead_source": demo.get("source", "website"),
        "tags": ["new_client", "hot_lead"],
        "notes": f"Lead from {demo.get('source', 'website')}. {demo.get('message', '')}".strip(),
        "utm_source": demo.get("utm_source", ""),
        "utm_medium": demo.get("utm_medium", ""),
        "utm_campaign": demo.get("utm_campaign", ""),
        "referred_by_user_id": demo.get("referred_by_user_id", ""),
        "referred_by_name": demo.get("referred_by_name", ""),
        "created_at": datetime.now(timezone.utc),
    }

    result = await db.contacts.insert_one(contact_doc)
    contact_id = str(result.inserted_id)

    # Mark the demo request as claimed
    await db.demo_requests.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": {
            "status": "contacted",
            "claimed_by": user_id,
            "claimed_by_name": user.get("name", ""),
            "claimed_contact_id": contact_id,
            "claimed_at": datetime.now(timezone.utc).isoformat(),
        }}
    )

    # Update the notification to include the new contact_id
    await db.notifications.update_many(
        {"demo_request_id": str(request_id)},
        {"$set": {"contact_id": contact_id}}
    )

    # Build a welcome message
    prefill = _build_lead_welcome(demo, contact_doc)

    return {
        "status": "success",
        "contact_id": contact_id,
        "contact_name": demo.get("name", ""),
        "prefill_message": prefill,
    }


def _build_lead_welcome(demo: dict, contact: dict) -> str:
    """Build a personalized welcome message for a claimed lead."""
    first = contact.get("first_name", demo.get("name", "").split(" ")[0])
    source_raw = demo.get("source", "")
    # Clean up source names: "pricing_page_hero" -> "pricing page"
    source = source_raw.replace("_", " ").replace("hero", "").replace("cta", "").replace("  ", " ").strip() if source_raw else ""
    msg = f"Hi {first}! Thanks for reaching out"
    if source and source not in ("direct", "unknown", ""):
        msg += f" through our {source}"
    msg += ". I'd love to learn more about what you're looking for and see how we can help. When's a good time to chat?"
    return msg
