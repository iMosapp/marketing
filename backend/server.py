"""
iMOs API Server - Main entry point
Refactored to use modular routers for maintainability
"""
from fastapi import FastAPI, APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from bson import ObjectId
import os
import logging
from pathlib import Path
from datetime import datetime

# Load environment
# In production: .env values are the source of truth (no .env.local, no supervisor overrides)
# In preview: supervisor injects MONGO_URL=localhost before process starts
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env', override=True)

# Import routers (after env is loaded)
from routers import auth, contacts, tasks, messages, calls, campaigns, admin, leaderboard, calendar, templates, tags, search, public_review, digital_card, profile, integrations, partners, legal, subscriptions, directory, shared_inboxes, voice, twilio_webhooks, public_landing, congrats_cards, short_urls, onboarding_settings, team_invite, jessie, sop, invoices, email, reports, broadcast, lead_sources, notifications, webhooks, inventory_webhooks, demo_requests, team_chat, date_triggers, app_directory, scheduler_admin, contact_events, white_label
from routers.database import get_db
from websocket_manager import manager as ws_manager

# Create the main app - disable trailing slash redirects to avoid mixed content issues
app = FastAPI(title="iMOs API", version="2.0", redirect_slashes=False)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============= CORS MIDDLEWARE =============
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============= HEALTH CHECK =============
@api_router.get("/")
async def root():
    return {"message": "iMOs API", "version": "2.0"}

@api_router.get("/health")
async def api_health():
    return {"status": "healthy", "message": "iMOs API v2.0"}

@api_router.get("/build-version")
async def build_version():
    """Returns current build version for cache-busting"""
    import hashlib
    start_time = getattr(app.state, 'start_time', 0)
    version = hashlib.md5(str(start_time).encode()).hexdigest()[:8]
    return {"version": version}

# Debug endpoint removed for security

# ============= BRANDING / STATIC ASSETS =============
@api_router.get("/branding/logo")
async def get_branding_logo():
    """Serve the iMOs logo for emails and public pages"""
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
api_router.include_router(contacts.router)
api_router.include_router(contact_events.router)
api_router.include_router(tasks.router)
api_router.include_router(messages.router)
api_router.include_router(calls.router)
api_router.include_router(campaigns.router)
api_router.include_router(admin.router)
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


@api_router.patch("/users/{user_id}")
async def patch_user_profile(user_id: str, data: dict):
    """Update user profile fields including photo"""
    db = get_db()
    allowed_fields = ['name', 'phone', 'persona', 'settings', 'photo_url', 'bio', 'social_links']
    update_dict = {k: v for k, v in data.items() if k in allowed_fields}
    
    if not update_dict:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    
    result = await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_dict}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Return the updated user data
    updated_user = await db.users.find_one({"_id": ObjectId(user_id)})
    if updated_user:
        updated_user["_id"] = str(updated_user["_id"])
        # Remove sensitive fields
        updated_user.pop("password", None)
    
    return updated_user


# ============= ACTIVITY FEED ENDPOINT =============
@api_router.get("/activity/{user_id}")
async def get_activity_feed(user_id: str, limit: int = 20):
    """
    Get team activity feed based on user's role.
    Shows recent actions by accessible team members.
    """
    from routers.database import get_data_filter, get_user_by_id
    
    db = get_db()
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    base_filter = await get_data_filter(user_id)
    activities = []
    
    # Get recent contacts added
    recent_contacts = await db.contacts.find(base_filter).sort("created_at", -1).limit(limit // 4).to_list(limit // 4)
    for c in recent_contacts:
        # Get the user who created this contact
        creator = await db.users.find_one({"_id": ObjectId(c['user_id'])}, {"name": 1})
        activities.append({
            "type": "contact_added",
            "icon": "person-add",
            "color": "#34C759",
            "message": f"{creator.get('name', 'Someone') if creator else 'Someone'} added {c.get('first_name', '')} {c.get('last_name', '')}",
            "timestamp": c.get('created_at'),
            "user_id": c.get('user_id'),
            "entity_id": str(c['_id'])
        })
    
    # Get recent messages sent
    recent_messages = await db.messages.find({"sender": "user"}).sort("timestamp", -1).limit(limit // 4).to_list(limit // 4)
    for m in recent_messages:
        # Get conversation to find user
        conv = await db.conversations.find_one({"_id": ObjectId(m.get('conversation_id'))})
        if conv and conv.get('user_id') in [f.get('user_id') if isinstance(f, dict) else f for f in [base_filter.get('user_id')] if f] + (base_filter.get('user_id', {}).get('$in', []) if isinstance(base_filter.get('user_id'), dict) else []):
            creator = await db.users.find_one({"_id": ObjectId(conv['user_id'])}, {"name": 1})
            activities.append({
                "type": "message_sent",
                "icon": "chatbubble",
                "color": "#007AFF",
                "message": f"{creator.get('name', 'Someone') if creator else 'Someone'} sent a message",
                "timestamp": m.get('timestamp'),
                "user_id": conv.get('user_id'),
                "entity_id": str(m['_id'])
            })
    
    # Get recent tasks created
    recent_tasks = await db.tasks.find(base_filter).sort("created_at", -1).limit(limit // 4).to_list(limit // 4)
    for t in recent_tasks:
        creator = await db.users.find_one({"_id": ObjectId(t['user_id'])}, {"name": 1})
        activities.append({
            "type": "task_created",
            "icon": "checkmark-circle",
            "color": "#FF9500",
            "message": f"{creator.get('name', 'Someone') if creator else 'Someone'} created task: {t.get('title', 'Untitled')[:30]}",
            "timestamp": t.get('created_at'),
            "user_id": t.get('user_id'),
            "entity_id": str(t['_id'])
        })
    
    # Get recent campaign enrollments
    recent_enrollments = await db.campaign_enrollments.find(base_filter).sort("enrolled_at", -1).limit(limit // 4).to_list(limit // 4)
    for e in recent_enrollments:
        creator = await db.users.find_one({"_id": ObjectId(e['user_id'])}, {"name": 1})
        activities.append({
            "type": "campaign_enrollment",
            "icon": "rocket",
            "color": "#AF52DE",
            "message": f"{creator.get('name', 'Someone') if creator else 'Someone'} enrolled {e.get('contact_name', 'a contact')} in campaign",
            "timestamp": e.get('enrolled_at'),
            "user_id": e.get('user_id'),
            "entity_id": str(e['_id'])
        })
    
    # Sort all activities by timestamp
    activities.sort(key=lambda x: x.get('timestamp') or datetime.min, reverse=True)
    
    # Convert timestamps to strings for JSON serialization
    for a in activities:
        if a.get('timestamp'):
            a['timestamp'] = a['timestamp'].isoformat() if hasattr(a['timestamp'], 'isoformat') else str(a['timestamp'])
    
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
    return {"status": "healthy", "message": "iMOs API v2.0"}

@app.get("/")
async def app_root():
    return {"status": "healthy", "message": "iMOs API v2.0"}

# Include the api_router in the main app
app.include_router(api_router)

# Include short URL router at root level
app.include_router(short_urls.router)

# ============= STARTUP EVENT =============
@app.on_event("startup")
async def startup_event():
    import time
    app.state.start_time = time.time()
    logger.info("iMOs API v2.0 starting...")
    logger.info(f"Database configured: {os.environ.get('DB_NAME', 'unknown')} (MONGO_URL {'set' if os.environ.get('MONGO_URL') else 'missing'})")
    
    # Create database indexes for performance (non-blocking)
    try:
        import asyncio
        from routers.database import get_db
        db = get_db()
        if db is not None:
            # Give index creation 15 seconds max, don't block startup
            try:
                await asyncio.wait_for(asyncio.gather(
                    db.contacts.create_index("user_id"),
                    db.contacts.create_index([("first_name", 1)]),
                    db.contacts.create_index([("user_id", 1), ("first_name", 1)]),
                    db.users.create_index("email", unique=True, sparse=True),
                    db.users.create_index("role"),
                    db.contact_photos.create_index("contact_id", unique=True),
                    db.date_trigger_configs.create_index([("user_id", 1), ("trigger_type", 1)]),
                ), timeout=15)
                logger.info("Database indexes created/verified")
            except asyncio.TimeoutError:
                logger.warning("Index creation timed out - will retry on first request")
    except Exception as e:
        logger.warning(f"Index creation skipped: {e}")
    
    # Start the background campaign scheduler
    try:
        from scheduler import start_scheduler
        start_scheduler()
        logger.info("Campaign scheduler started")
    except Exception as e:
        logger.warning(f"Scheduler start failed (non-fatal): {e}")

    logger.info("iMOs API v2.0 started")

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
                "email": "admin@imosapp.com",
                "password": "iMOs2026!",
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
            logger.info("  Email: admin@imosapp.com")
            logger.info("  Password: iMOs2026!")
            logger.info("=" * 50)
        else:
            logger.info(f"Database has {user_count} existing users - skipping seed")
    except Exception as e:
        logger.error(f"Failed to seed admin user: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
