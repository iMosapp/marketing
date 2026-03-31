"""
i'M On Social API Server - Main entry point
Refactored to use modular routers for maintainability
"""
from fastapi import FastAPI, APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse as _JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from bson import ObjectId
import os
import logging
from pathlib import Path
from datetime import datetime
import json

class UTCDateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that ensures naive datetimes (from MongoDB) get Z suffix."""
    def default(self, obj):
        if isinstance(obj, datetime):
            s = obj.isoformat()
            if obj.tzinfo is None and not s.endswith('Z'):
                s += 'Z'
            return s
        return super().default(obj)

# Load environment
# In production: Kubernetes/deployment platform injects env vars (MONGO_URL, DB_NAME, etc.)
# override=False means platform env vars take priority over .env file
# In preview: .env file provides defaults (MONGO_URL=localhost) since no platform vars exist
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env', override=False)

# Import routers (after env is loaded)
from routers import auth, contacts, tasks, messages, calls, campaigns, admin, admin_hierarchy, admin_users, leaderboard, calendar, templates, tags, search, public_review, digital_card, profile, integrations, partners, legal, subscriptions, directory, shared_inboxes, voice, twilio_webhooks, public_landing, congrats_cards, short_urls, onboarding_settings, team_invite, jessie, sop, invoices, email, reports, broadcast, lead_sources, notifications, webhooks, inventory_webhooks, demo_requests, team_chat, date_triggers, app_directory, scheduler_admin, contact_events, white_label, image_router, webhook_subscriptions, public_api, user_lifecycle, docs, nda, voice_notes, contact_intel, leaderboard_v2, notifications_center, ai_campaigns, showcase, brand_assets, linkpage, setup_wizard, help_center, review_templates, social_templates, training, engagement_signals, ai_outreach, campaign_config, permission_templates, opt_in, push_notifications, crm_timeline, tracking, contact_merge, account_health, messaging_channels, csv_import, sold_workflow, partner_billing, seo, chat_widget, partner_invoices, training_reports, media_tracking
from routers.database import get_db
from websocket_manager import manager as ws_manager

# Patch jsonable_encoder to append Z to naive datetime ISO strings
import re
_ISO_NAIVE_RE = re.compile(r'"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?"')

class UTCJSONResponse(_JSONResponse):
    """JSONResponse that fixes naive datetime strings by appending Z."""
    def render(self, content) -> bytes:
        body = json.dumps(content, ensure_ascii=False)
        def _add_z(m):
            s = m.group(0)
            if 'Z' not in s and '+' not in s:
                return s[:-1] + 'Z"'
            return s
        body = _ISO_NAIVE_RE.sub(_add_z, body)
        return body.encode("utf-8")

# Create the main app - disable trailing slash redirects to avoid mixed content issues
app = FastAPI(title="i'M On Social API", version="2.0", redirect_slashes=False, default_response_class=UTCJSONResponse)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============= PERFORMANCE MONITORING MIDDLEWARE =============
import time

@app.middleware("http")
async def log_slow_requests(request: Request, call_next):
    """Log any request that takes longer than 2 seconds — helps identify bottlenecks."""
    start = time.monotonic()
    response = await call_next(request)
    duration = time.monotonic() - start
    if duration > 2.0:
        path = request.url.path
        method = request.method
        logger.warning(f"[SLOW REQUEST] {method} {path} took {duration:.2f}s")
    return response


# ============= CORS MIDDLEWARE =============
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Serve static files (voice samples, etc.)
from fastapi.staticfiles import StaticFiles
static_dir = ROOT_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ============= HEALTH CHECK =============
@api_router.get("/")
async def root():
    return {"message": "i'M On Social API", "version": "2.0"}

@api_router.get("/health")
async def api_health():
    """
    Liveness health check — must always return 200 quickly so K8s/Emergent
    does NOT restart the pod during brief MongoDB hiccups.
    Use /health/deep for full DB connectivity check.
    """
    return {"status": "healthy", "message": "i'M On Social API v2.0"}


@api_router.get("/health/deep")
async def api_health_deep():
    """Deep health check including MongoDB ping — use for monitoring only, NOT as a liveness probe."""
    try:
        db = get_db()
        await db.command("ping")
        return {"status": "healthy", "db": "connected"}
    except Exception as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "db": "unreachable", "error": str(e)[:100]}
        )

@api_router.get("/build-version")
async def build_version():
    """Returns current build version for cache-busting"""
    import hashlib
    start_time = getattr(app.state, 'start_time', 0)
    version = hashlib.md5(str(start_time).encode()).hexdigest()[:8]
    return {"version": version}


@app.get("/voice-picker")
async def voice_picker():
    """Voice sample picker for choosing Jessi's voice"""
    return FileResponse(str(ROOT_DIR / "static" / "voice-picker.html"), media_type="text/html")

# Debug endpoint removed for security

# ============= BRANDING / STATIC ASSETS =============
@api_router.get("/branding/logo")
async def get_branding_logo():
    """Serve the i'M On Social logo for emails and public pages"""
    logo_path = ROOT_DIR / "static" / "imos-logo-email.png"
    if not logo_path.exists():
        raise HTTPException(status_code=404, detail="Logo not found")
    return FileResponse(
        str(logo_path),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=31536000"}
    )

# ============= INCLUDE ROUTERS =============
api_router.include_router(auth.router)
api_router.include_router(contact_events.router)
api_router.include_router(contact_merge.router)
api_router.include_router(contacts.router)
api_router.include_router(white_label.router)
api_router.include_router(image_router.router)
api_router.include_router(tasks.router)
api_router.include_router(messages.router)
api_router.include_router(calls.router)
api_router.include_router(campaigns.router)
api_router.include_router(admin.router)
api_router.include_router(admin_hierarchy.router)
api_router.include_router(admin_users.router)
api_router.include_router(leaderboard.router)
api_router.include_router(calendar.router)
api_router.include_router(templates.router)
api_router.include_router(tags.router)
api_router.include_router(search.router)
api_router.include_router(public_review.router)
api_router.include_router(digital_card.router)
api_router.include_router(profile.router)
api_router.include_router(integrations.router)
api_router.include_router(partners.router)
api_router.include_router(legal.router)
api_router.include_router(subscriptions.router)
api_router.include_router(directory.router)
api_router.include_router(shared_inboxes.router)
api_router.include_router(voice.router)
api_router.include_router(twilio_webhooks.router)
api_router.include_router(public_landing.router)
api_router.include_router(congrats_cards.router)
api_router.include_router(showcase.router)
api_router.include_router(short_urls.router)
api_router.include_router(onboarding_settings.router)
api_router.include_router(team_invite.router)
api_router.include_router(jessie.router)
api_router.include_router(sop.router)
api_router.include_router(invoices.router)
api_router.include_router(email.router)
api_router.include_router(reports.router)
api_router.include_router(broadcast.router)
api_router.include_router(lead_sources.router)
api_router.include_router(notifications.router)
api_router.include_router(webhooks.router)
api_router.include_router(inventory_webhooks.router)
api_router.include_router(demo_requests.router)
api_router.include_router(team_chat.router)
api_router.include_router(date_triggers.router)
api_router.include_router(app_directory.router)
api_router.include_router(scheduler_admin.router)
api_router.include_router(webhook_subscriptions.router)
api_router.include_router(public_api.router)
api_router.include_router(user_lifecycle.router)
api_router.include_router(docs.router)
api_router.include_router(nda.router)
api_router.include_router(voice_notes.router)
api_router.include_router(contact_intel.router)
api_router.include_router(leaderboard_v2.router)
api_router.include_router(notifications_center.router)
api_router.include_router(ai_campaigns.router)
api_router.include_router(brand_assets.router)
api_router.include_router(linkpage.router)
api_router.include_router(setup_wizard.router)
api_router.include_router(help_center.router)
api_router.include_router(review_templates.router)
api_router.include_router(social_templates.router)
api_router.include_router(training.router)
api_router.include_router(engagement_signals.router)
api_router.include_router(ai_outreach.router)
api_router.include_router(campaign_config.router)
api_router.include_router(permission_templates.router)
api_router.include_router(opt_in.router)
api_router.include_router(push_notifications.router)
api_router.include_router(crm_timeline.router)
api_router.include_router(tracking.router)
api_router.include_router(account_health.router)
api_router.include_router(messaging_channels.router)
api_router.include_router(csv_import.router)
api_router.include_router(sold_workflow.router)
api_router.include_router(partner_billing.router)
api_router.include_router(partner_invoices.router)
api_router.include_router(training_reports.router)
api_router.include_router(seo.router)
api_router.include_router(chat_widget.router)
api_router.include_router(media_tracking.router)

from routers import error_reporting
api_router.include_router(error_reporting.router)

# ============= WEBSOCKET ENDPOINT =============
@app.websocket("/api/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await ws_manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Client can send pings or other messages; we just keep the connection alive
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_id)
    except Exception:
        ws_manager.disconnect(websocket, user_id)

# ============= USER SETTINGS ENDPOINTS (kept here for URL compatibility) =============
@api_router.get("/users/{user_id}/leaderboard-settings")
async def get_leaderboard_settings(user_id: str):
    """Get user's leaderboard settings"""
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user.get('settings', {
        'leaderboard_visible': False,
        'compare_scope': 'state'
    })

@api_router.put("/users/{user_id}/leaderboard-settings")
async def update_leaderboard_settings(user_id: str, settings: dict):
    """Update user's leaderboard settings"""
    db = get_db()
    allowed_fields = ['leaderboard_visible', 'compare_scope', 'state']
    update_dict = {f"settings.{k}": v for k, v in settings.items() if k in allowed_fields}
    
    # Also update state at root level if provided
    if 'state' in settings:
        update_dict['state'] = settings['state']
    
    result = await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_dict}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "Settings updated"}

# ============= REVIEW LINKS ENDPOINTS =============
@api_router.get("/users/{user_id}/review-links")
async def get_review_links(user_id: str):
    """Get user's review links for quick sharing"""
    db = get_db()
    user = await db.users.find_one(
        {"_id": ObjectId(user_id)},
        {"review_links": 1, "custom_link_name": 1}
    )
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "review_links": user.get("review_links", {}),
        "custom_link_name": user.get("custom_link_name", "")
    }


@api_router.put("/users/{user_id}/review-links")
async def update_review_links(user_id: str, data: dict):
    """Save user's review links"""
    db = get_db()
    result = await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "review_links": data.get("review_links", {}),
            "custom_link_name": data.get("custom_link_name", "")
        }}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "Review links saved"}

# ============= PERSONA SETTINGS ENDPOINTS =============
@api_router.get("/users/{user_id}/persona")
async def get_persona_settings(user_id: str):
    """Get user's MVP persona settings"""
    db = get_db()
    user = await db.users.find_one(
        {"_id": ObjectId(user_id)},
        {"persona": 1}
    )
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user.get("persona", {})


@api_router.put("/users/{user_id}/persona")
async def update_persona_settings(user_id: str, data: dict):
    """Save user's MVP persona settings"""
    db = get_db()
    result = await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"persona": data}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "Persona settings saved"}


@api_router.get("/users/{user_id}")
async def get_user_profile(user_id: str):
    """Get user profile data"""
    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user["_id"] = str(user["_id"])
    user.pop("password", None)
    # Convert any ObjectId fields to strings
    for key in ["organization_id", "org_id", "store_id", "partner_id"]:
        if user.get(key):
            user[key] = str(user[key])
    return user


@api_router.patch("/users/{user_id}")
async def patch_user_profile(user_id: str, data: dict):
    """Update user profile fields. Photo updates must go through POST /profile/{user_id}/photo."""
    db = get_db()
    allowed_fields = ['name', 'phone', 'persona', 'settings', 'photo_url', 'bio', 'social_links',
                      'timezone', 'address', 'city', 'state', 'zip_code', 'country']
    update_dict = {k: v for k, v in data.items() if k in allowed_fields}
    
    if not update_dict:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    
    # Block raw base64 from being stored as photo_url — it causes massive MongoDB docs,
    # breaks resolve_user_photo(), and bypasses the WebP/thumbnail pipeline.
    # Photo uploads must use POST /profile/{user_id}/photo.
    if 'photo_url' in update_dict:
        url_val = update_dict.get('photo_url') or ''
        if url_val and url_val.startswith('data:'):
            raise HTTPException(
                status_code=400,
                detail="Base64 images are not accepted here. Use POST /profile/{user_id}/photo for photo uploads."
            )
        # When photo_url is set to a real URL or cleared, invalidate ALL cached optimised paths
        # so resolve_user_photo() returns the fresh image everywhere (digital card, showroom, etc.)
        update_ops: dict = {
            "$set": update_dict,
            "$unset": {"photo_path": "", "photo_avatar_path": "", "photo_thumb_path": ""},
        }
    else:
        update_ops = {"$set": update_dict}
    
    result = await db.users.update_one({"_id": ObjectId(user_id)}, update_ops)
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Return the updated user data
    updated_user = await db.users.find_one({"_id": ObjectId(user_id)}, {"password": 0})
    if updated_user:
        updated_user["_id"] = str(updated_user["_id"])
        for key in ["organization_id", "org_id", "store_id", "partner_id"]:
            if updated_user.get(key):
                updated_user[key] = str(updated_user[key])
    
    return updated_user


# ============= ACTIVITY FEED ENDPOINT =============
@api_router.get("/activity/{user_id}")
async def get_activity_feed(user_id: str, limit: int = 20):
    """
    Get team activity feed based on user's role.
    Shows recent actions by accessible team members, including contact events.
    """
    from routers.database import get_data_filter, get_user_by_id
    
    db = get_db()
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    base_filter = await get_data_filter(user_id)
    activities = []
    sub_limit = max(limit // 5, 2)
    
    # ── 1. Contact Events (the PRIMARY source for tracked user actions) ──
    try:
        recent_events = await db.contact_events.find(base_filter).sort("timestamp", -1).limit(limit).to_list(limit)

        # Bulk-fetch all referenced users and contacts in TWO queries instead of N+1
        user_ids_needed = set()
        contact_ids_needed = set()
        for ev in recent_events:
            if ev.get("user_id"):
                user_ids_needed.add(ev["user_id"])
            if ev.get("contact_id") and not ev.get("contact_name"):
                contact_ids_needed.add(ev["contact_id"])

        users_map = {}
        if user_ids_needed:
            try:
                uoids = [ObjectId(uid) for uid in user_ids_needed if len(uid) == 24]
                async for u in db.users.find({"_id": {"$in": uoids}}, {"name": 1}):
                    users_map[str(u["_id"])] = u.get("name", "Someone")
            except Exception:
                pass

        contacts_map = {}
        if contact_ids_needed:
            try:
                coids = [ObjectId(cid) for cid in contact_ids_needed if len(cid) == 24]
                async for c in db.contacts.find({"_id": {"$in": coids}}, {"first_name": 1, "last_name": 1}):
                    contacts_map[str(c["_id"])] = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
            except Exception:
                pass

        for ev in recent_events:
            creator_name = users_map.get(ev.get("user_id", ""), "Someone")
            contact_name = ev.get("contact_name", "") or contacts_map.get(ev.get("contact_id", ""), "")

            event_type = ev.get('event_type', 'activity')
            event_labels = {
                'digital_card_shared': 'shared a digital card with',
                'digital_card_sent': 'shared a digital card with',
                'review_request_sent': 'sent a review invite to',
                'congrats_card_sent': 'sent a congrats card to',
                'showcase_shared': 'shared the showroom with',
                'vcard_sent': 'shared a contact card with',
                'sms_sent': 'texted',
                'email_sent': 'emailed',
                'call_placed': 'called',
                'note_updated': 'updated notes for',
                'link_page_shared': 'shared link page with',
            }
            label = event_labels.get(event_type)
            if label is None:
                # Use get_event_label for proper human-readable labels (handles custom card types)
                from utils.event_types import get_event_label as _gel
                generated = _gel(event_type)
                # For "sent" actions: convert "X Card Sent" → "sent an X card"
                if event_type.endswith('_card_sent'):
                    card_display = generated.replace(' Card Sent', '').replace(' Card Viewed', '')
                    label = f"sent a {card_display.lower()} card"
                elif event_type.endswith('_card_viewed'):
                    card_display = generated.replace('Viewed ', '').replace(' Card', '')
                    label = f"viewed a {card_display.lower()} card"
                else:
                    label = ev.get('title') or generated
            msg = f"{creator_name} {label} {contact_name}".strip() if contact_name else f"{creator_name} {label}".strip()
            
            activities.append({
                "type": event_type,
                "icon": ev.get('icon', 'flash'),
                "color": ev.get('color', '#C9A962'),
                "message": msg,
                "timestamp": ev.get('timestamp'),
                "user_id": ev.get('user_id'),
                "entity_id": str(ev.get('contact_id', ev.get('_id', ''))),
            })
    except Exception as e:
        logger.error(f"Error fetching contact_events for activity feed: {e}")
    
    # ── 2. Recent contacts added ──
    try:
        recent_contacts = await db.contacts.find(base_filter).sort("created_at", -1).limit(sub_limit).to_list(sub_limit)
        existing_contact_ids = {a.get('entity_id') for a in activities}
        for c in recent_contacts:
            cid = str(c['_id'])
            if cid in existing_contact_ids:
                continue
            creator_name = "Someone"
            try:
                creator = await db.users.find_one({"_id": ObjectId(c['user_id'])}, {"name": 1})
                if creator:
                    creator_name = creator.get('name', 'Someone')
            except Exception:
                pass
            activities.append({
                "type": "contact_added",
                "icon": "person-add",
                "color": "#34C759",
                "message": f"{creator_name} added {c.get('first_name', '')} {c.get('last_name', '')}".strip(),
                "timestamp": c.get('created_at'),
                "user_id": c.get('user_id'),
                "entity_id": cid,
            })
    except Exception as e:
        logger.error(f"Error fetching contacts for activity feed: {e}")
    
    # ── 3. Recent tasks created ──
    try:
        recent_tasks = await db.tasks.find(base_filter).sort("created_at", -1).limit(sub_limit).to_list(sub_limit)
        for t in recent_tasks:
            creator_name = "Someone"
            try:
                creator = await db.users.find_one({"_id": ObjectId(t['user_id'])}, {"name": 1})
                if creator:
                    creator_name = creator.get('name', 'Someone')
            except Exception:
                pass
            activities.append({
                "type": "task_created",
                "icon": "checkmark-circle",
                "color": "#FF9500",
                "message": f"{creator_name} created task: {t.get('title', 'Untitled')[:40]}",
                "timestamp": t.get('created_at'),
                "user_id": t.get('user_id'),
                "entity_id": str(t['_id']),
            })
    except Exception as e:
        logger.error(f"Error fetching tasks for activity feed: {e}")
    
    # ── 4. Recent campaign enrollments ──
    try:
        recent_enrollments = await db.campaign_enrollments.find(base_filter).sort("enrolled_at", -1).limit(sub_limit).to_list(sub_limit)
        for en in recent_enrollments:
            creator_name = "Someone"
            try:
                creator = await db.users.find_one({"_id": ObjectId(en['user_id'])}, {"name": 1})
                if creator:
                    creator_name = creator.get('name', 'Someone')
            except Exception:
                pass
            activities.append({
                "type": "campaign_enrollment",
                "icon": "rocket",
                "color": "#AF52DE",
                "message": f"{creator_name} enrolled {en.get('contact_name', 'a contact')} in campaign",
                "timestamp": en.get('enrolled_at'),
                "user_id": en.get('user_id'),
                "entity_id": str(en['_id']),
            })
    except Exception as e:
        logger.error(f"Error fetching enrollments for activity feed: {e}")
    
    # Sort all activities by timestamp (newest first)
    activities.sort(key=lambda x: x.get('timestamp') or datetime.min, reverse=True)
    
    # Convert timestamps to ISO strings
    for a in activities:
        ts = a.get('timestamp')
        if ts and hasattr(ts, 'isoformat'):
            a['timestamp'] = ts.isoformat() + 'Z' if not str(ts).endswith('Z') else ts.isoformat()
        elif ts:
            a['timestamp'] = str(ts)
    
    return {
        "activities": activities[:limit],
        "user_role": user.get('role', 'user'),
        "total": len(activities)
    }

# ============= STRIPE WEBHOOK ENDPOINT =============

@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events for payment processing"""
    from emergentintegrations.payments.stripe.checkout import StripeCheckout
    
    try:
        api_key = os.environ.get("STRIPE_API_KEY")
        if not api_key:
            logger.error("Stripe API key not configured")
            raise HTTPException(status_code=500, detail="Payment system not configured")
        
        stripe_checkout = StripeCheckout(api_key=api_key, webhook_url="")
        
        # Get request body and signature
        body = await request.body()
        signature = request.headers.get("Stripe-Signature", "")
        
        # Handle the webhook
        webhook_response = await stripe_checkout.handle_webhook(body, signature)
        
        logger.info(f"Stripe webhook received: {webhook_response.event_type}")
        
        # Process based on event type
        if webhook_response.event_type == "checkout.session.completed":
            db = get_db()
            
            # Update payment transaction
            await db.payment_transactions.update_one(
                {"session_id": webhook_response.session_id},
                {"$set": {
                    "status": webhook_response.payment_status,
                    "event_type": webhook_response.event_type,
                    "event_id": webhook_response.event_id,
                    "updated_at": datetime.utcnow()
                }}
            )
            
            # If payment was successful and it's for a partner agreement
            if webhook_response.payment_status == "paid":
                metadata = webhook_response.metadata or {}
                if metadata.get("type") == "partner_agreement":
                    agreement_id = metadata.get("agreement_id")
                    if agreement_id:
                        # Update agreement status
                        await db.partner_agreements.update_one(
                            {"_id": ObjectId(agreement_id)},
                            {"$set": {
                                "status": "signed",
                                "paid_at": datetime.utcnow(),
                                "payment_session_id": webhook_response.session_id,
                            }}
                        )
                        # Update partner status
                        await db.partners.update_one(
                            {"agreement_id": agreement_id},
                            {"$set": {"status": "active"}}
                        )
                        logger.info(f"Partner agreement {agreement_id} marked as paid")
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Stripe webhook error: {str(e)}")
        return {"status": "received"}  # Always return 200 to Stripe

# Root health check
@app.get("/health")
@app.get("/healthz")
async def health_check():
    return {"status": "healthy", "message": "i'M On Social API v2.0"}

@app.get("/")
async def app_root():
    return {"status": "healthy", "message": "i'M On Social API v2.0"}


@app.get("/l/{username}")
async def serve_link_page(username: str):
    """Serve the public link page HTML for any username."""
    from pathlib import Path
    html_path = Path(__file__).parent.parent / "frontend" / "public" / "l.html"
    if html_path.exists():
        return FileResponse(str(html_path), media_type="text/html")
    raise HTTPException(status_code=404, detail="Page template not found")


# Include the api_router in the main app
app.include_router(api_router)

# Include short URL router at root level
app.include_router(short_urls.router)

# ============= STARTUP EVENT =============
@app.on_event("startup")
async def startup_event():
    import time
    import asyncio
    app.state.start_time = time.time()
    logger.info("i'M On Social API v2.0 starting...")
    logger.info(f"Database configured: {os.environ.get('DB_NAME', 'unknown')} (MONGO_URL {'set' if os.environ.get('MONGO_URL') else 'missing'})")

    # ── Global asyncio exception handler ────────────────────────────────────
    # Catches ANY unhandled exception from asyncio.create_task() calls so they
    # get LOGGED instead of silently crashing or corrupting the event loop.
    def _handle_async_exception(loop, context):
        msg = context.get("exception", context.get("message", "Unknown async error"))
        task = context.get("task")
        task_name = getattr(task, "get_name", lambda: "unknown")() if task else "no-task"
        logger.error(f"[Asyncio] Unhandled background task exception ({task_name}): {msg}")
        # DO NOT re-raise — this would crash the server. Just log and continue.

    asyncio.get_event_loop().set_exception_handler(_handle_async_exception)
    
    # Initialize object storage (non-blocking, will retry on first use)
    try:
        from utils.image_storage import init_storage
        init_storage()
        logger.info("Object storage ready")
    except Exception as e:
        logger.warning(f"Object storage init deferred (will retry on first upload): {e}")
    
    # Create database indexes for performance (non-blocking)
    try:
        import asyncio
        from routers.database import get_db
        db = get_db()
        if db is not None:
            # Give index creation 15 seconds max, don't block startup
            try:
                await asyncio.wait_for(asyncio.gather(
                    # Contacts - core queries
                    db.contacts.create_index("user_id"),
                    db.contacts.create_index([("first_name", 1)]),
                    db.contacts.create_index([("user_id", 1), ("first_name", 1)]),
                    db.contacts.create_index([("user_id", 1), ("status", 1)]),
                    db.contacts.create_index([("user_id", 1), ("ownership_type", 1), ("status", 1)]),
                    db.contacts.create_index([("user_id", 1), ("updated_at", -1)]),
                    # Users
                    db.users.create_index("email", unique=True, sparse=True),
                    db.users.create_index("role"),
                    db.users.create_index([("store_id", 1)]),
                    # Conversations - inbox queries
                    db.conversations.create_index([("user_id", 1), ("last_message_at", -1)]),
                    db.conversations.create_index([("contact_id", 1)]),
                    db.conversations.create_index([("user_id", 1), ("status", 1)]),
                    # Messages - thread loading
                    db.messages.create_index([("conversation_id", 1), ("timestamp", -1)]),
                    # Contact events & photos
                    db.contact_photos.create_index("contact_id", unique=True),
                    db.contact_events.create_index([("user_id", 1), ("timestamp", -1)]),
                    db.contact_events.create_index([("contact_id", 1), ("timestamp", -1)]),
                    db.contact_events.create_index([("contact_id", 1), ("event_type", 1)]),
                    # Link pages — was missing, caused 60s timeout on full collection scan
                    db.link_pages.create_index("user_id", unique=True, sparse=True),
                    db.link_pages.create_index("username", sparse=True),
                    # Campaign system
                    db.campaign_enrollments.create_index([("campaign_id", 1), ("contact_id", 1), ("status", 1)]),
                    db.campaign_enrollments.create_index([("user_id", 1), ("status", 1)]),
                    db.campaign_enrollments.create_index([("contact_id", 1)]),
                    db.campaign_enrollments.create_index([("user_id", 1), ("status", 1), ("next_send_at", 1)]),
                    db.campaign_pending_sends.create_index([("user_id", 1), ("status", 1)]),
                    db.campaign_pending_sends.create_index([("campaign_id", 1), ("contact_id", 1), ("step", 1), ("status", 1)]),
                    # Tasks
                    db.tasks.create_index([("user_id", 1), ("status", 1), ("due_date", 1)]),
                    db.tasks.create_index("idempotency_key", unique=True, partialFilterExpression={"idempotency_key": {"$type": "string"}}),
                    # Date triggers & notifications
                    db.date_trigger_configs.create_index([("user_id", 1), ("trigger_type", 1)]),
                    db.notifications.create_index([("user_id", 1), ("read", 1), ("created_at", -1)]),
                    # Tags
                    db.tags.create_index([("user_id", 1)]),
                    # Short URL click dedup index
                    db.short_url_clicks.create_index([("short_code", 1), ("ip", 1), ("clicked_at", -1)]),
                    # Performance: compound indexes for contact page queries
                    db.campaign_enrollments.create_index([("contact_id", 1), ("user_id", 1), ("status", 1)]),
                    db.campaign_pending_sends.create_index([("contact_id", 1), ("user_id", 1)]),
                    # New pre-scheduled queue index — powers the scheduler's primary query
                    db.campaign_pending_sends.create_index([("status", 1), ("send_at", 1)]),
                    db.campaign_pending_sends.create_index([("enrollment_id", 1), ("status", 1)]),
                    db.tasks.create_index([("contact_id", 1), ("user_id", 1), ("type", 1)]),
                    db.congrats_cards_sent.create_index([("contact_id", 1), ("user_id", 1)]),
                    db.messages.create_index([("_id", 1)]),  # Ensures batch message lookups are instant
                    db.contacts.create_index([("user_id", 1), ("phone", 1)]),  # For phone dedup
                    db.contacts.create_index([("user_id", 1), ("email", 1)]),  # For email dedup
                ), timeout=15)
                logger.info("Database indexes created/verified (production-ready)")
            except asyncio.TimeoutError:
                logger.warning("Index creation timed out - will retry on first request")
    except Exception as e:
        logger.warning(f"Index creation skipped: {e}")
    
    # Auto-sync PRD.md into the database
    try:
        prd_path = Path(__file__).parent.parent / "memory" / "PRD.md"
        if prd_path.exists():
            prd_content = prd_path.read_text()
            existing = await db.company_docs.find_one({"slug": "product-requirements-document"}, {"content": 1})
            if not existing or existing.get("content") != prd_content:
                await db.company_docs.update_one(
                    {"slug": "product-requirements-document"},
                    {"$set": {
                        "content": prd_content,
                        "updated_at": datetime.utcnow(),
                        "title": "Product Requirements Document",
                        "summary": "Complete PRD for the i'M On Social platform - features, architecture, backlog, and known issues.",
                        "category": "prd",
                        "icon": "clipboard",
                        "is_published": True,
                        "sort_order": 0,
                    },
                    "$setOnInsert": {
                        "slug": "product-requirements-document",
                        "version": "1.0",
                        "created_at": datetime.utcnow(),
                    }},
                    upsert=True,
                )
                logger.info("PRD auto-synced from PRD.md")
    except Exception as e:
        logger.warning(f"PRD auto-sync skipped: {e}")

    # Start the background campaign scheduler
    try:
        from scheduler import start_scheduler
        start_scheduler()
        logger.info("Campaign scheduler started")
    except Exception as e:
        logger.warning(f"Scheduler start failed (non-fatal): {e}")

    logger.info("i'M On Social API v2.0 started")

@app.on_event("shutdown")
async def shutdown_event():
    try:
        from scheduler import stop_scheduler
        stop_scheduler()
        logger.info("Campaign scheduler stopped")
    except Exception as e:
        logger.warning(f"Scheduler stop failed: {e}")


async def seed_admin_user(db):
    """Create default admin user if no users exist in database"""
    try:
        user_count = await db.users.count_documents({})
        if user_count == 0:
            logger.info("Empty database detected - creating default admin user...")
            
            admin_user = {
                "email": "admin@imonsocial.com",
                "password": "i'M On Social2026!",
                "name": "Admin User",
                "phone": "",
                "role": "super_admin",
                "organization_id": None,
                "store_id": None,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "onboarding_complete": True,
                "status": "active",
                "is_active": True,
                "needs_password_change": False,
                "stats": {
                    'contacts_added': 0,
                    'messages_sent': 0,
                    'calls_made': 0,
                    'deals_closed': 0
                },
                "settings": {
                    'leaderboard_visible': True,
                    'compare_scope': 'state'
                }
            }
            
            await db.users.insert_one(admin_user)
            logger.info("=" * 50)
            logger.info("DEFAULT ADMIN USER CREATED:")
            logger.info("  Email: admin@imonsocial.com")
            logger.info("  Password: i'M On Social2026!")
            logger.info("=" * 50)
        else:
            logger.info(f"Database has {user_count} existing users - skipping seed")
    except Exception as e:
        logger.error(f"Failed to seed admin user: {e}")

# Serve marketing preview (temporary - for content review only)
marketing_preview_dir = Path("/app/marketing/build-preview")
if marketing_preview_dir.exists():
    app.mount("/api/marketing-preview", StaticFiles(directory=str(marketing_preview_dir), html=True), name="marketing-preview")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
