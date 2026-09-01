"""
I'm On Social API Server - Main entry point
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
from routers import auth, contacts, tasks, messages, calls, campaigns, admin, admin_hierarchy, admin_users, leaderboard, calendar, templates, tags, search, public_review, digital_card, profile, integrations, partners, legal, subscriptions, directory, shared_inboxes, voice, twilio_webhooks, twilio_admin, public_landing, congrats_cards, short_urls, onboarding_settings, team_invite, jessie, sop, invoices, email, reports, broadcast, lead_sources, lead_intake, notifications, webhooks, inventory_webhooks, demo_requests, team_chat, date_triggers, app_directory, scheduler_admin, contact_events, white_label, image_router, webhook_subscriptions, public_api, user_lifecycle, docs, nda, voice_notes, contact_intel, leaderboard_v2, notifications_center, ai_campaigns, ai_reply, home_intelligence, showcase, brand_assets, linkpage, setup_wizard, help_center, review_templates, social_templates, training, engagement_signals, ai_outreach, campaign_config, permission_templates, opt_in, push_notifications, crm_timeline, tracking, contact_merge, account_health, messaging_channels, csv_import, sold_workflow, partner_billing, seo, geo, chat_widget, partner_invoices, training_reports, media_tracking, va_profiles, user_schedule, keyword_rules, wallet_pass
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
app = FastAPI(title="I'm On Social API", version="2.0", redirect_slashes=False, default_response_class=UTCJSONResponse)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# ============= SITEMAP + ROBOTS =============
from fastapi.responses import PlainTextResponse

@app.get("/sitemap.xml", response_class=PlainTextResponse)
async def sitemap():
    """Dynamic XML sitemap — lists all public salesperson pages and store pages.
    Google and AI crawlers use this to discover and index every user's presence pages."""
    from routers.database import get_db as _get_db
    db = _get_db()
    base = os.environ.get("APP_URL", "https://app.imonsocial.com").rstrip("/")
    urls = [
        f"{base}/",
        f"{base}/sitemap.xml",
    ]
    # All active users' digital card + landing pages
    async for user in db.users.find(
        {"status": {"$in": ["active", "trialing"]}},
        {"_id": 1, "seo_slug": 1}
    ).limit(10000):
        uid = str(user["_id"])
        urls.append(f"{base}/card/{uid}")
        urls.append(f"{base}/p/{uid}")
    # All store pages
    async for store in db.stores.find({}, {"slug": 1}).limit(5000):
        if store.get("slug"):
            urls.append(f"{base}/p/store/{store['slug']}")
            urls.append(f"{base}/showcase/store/{store['slug']}")

    url_entries = "\n".join(
        f"  <url><loc>{u}</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>"
        for u in urls
    )
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{url_entries}
</urlset>"""
    return PlainTextResponse(content=xml, media_type="application/xml")


@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots():
    """robots.txt — let Google crawl all public pages, block private app routes."""
    base = os.environ.get("APP_URL", "https://app.imonsocial.com").rstrip("/")
    return PlainTextResponse(content=f"""User-agent: *
Allow: /card/
Allow: /p/
Allow: /showcase/
Allow: /review/
Allow: /l/

Disallow: /admin/
Disallow: /api/
Disallow: /settings/
Disallow: /campaigns/
Disallow: /contacts/
Disallow: /touchpoints/
Disallow: /thread/

Sitemap: {base}/sitemap.xml
""")



# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============= PERFORMANCE MONITORING MIDDLEWARE =============
import time

@app.middleware("http")
async def enforce_user_ownership(request: Request, call_next):
    """
    Phase 2 BOLA protection — enforce that the JWT caller owns (or administers)
    the user_id appearing in the URL path for all major data endpoints.

    Protects: contacts, tasks, campaigns, voice-notes, messages/conversations,
              tags, templates, home, activity, search, notifications-center,
              reports, push preferences, users data endpoints.

    Skips: public pages, auth, webhooks, admin routes, images, and any
           path that doesn't contain a user_id segment.
    """
    import re as _re
    from fastapi.responses import JSONResponse as _JSONResponse

    path = request.url.path

    # ── Paths that are always public / handled by their own auth ──────────────
    ALWAYS_SKIP = (
        "/api/auth/", "/api/webhooks/", "/api/public/", "/api/images/",
        "/api/card/", "/api/l/", "/api/p/", "/api/showcase/", "/api/congrats/",
        "/api/review/", "/api/s/", "/api/opt-in/", "/api/health",
        "/api/admin/", "/api/imos/", "/api/birthday/", "/api/timeline/",
        "/api/onboarding/", "/api/profile/", "/api/docs", "/openapi.json",
        "/api/seo/sitemap", "/api/directory/", "/api/analytics/",
        "/api/integrations/public", "/api/demo/", "/api/leads/",
    )
    if any(path.startswith(p) for p in ALWAYS_SKIP):
        return await call_next(request)

    # ── Routes protected: resource/{user_id}/... ──────────────────────────────
    # The first ObjectId segment after the resource name is the user_id.
    PROTECTED_PREFIXES = (
        "/api/contacts/", "/api/tasks/", "/api/campaigns/", "/api/voice-notes/",
        "/api/messages/conversations/", "/api/tags/", "/api/templates/",
        "/api/home/", "/api/activity/", "/api/search/", "/api/notifications-center/",
        "/api/reports/", "/api/push/preferences/", "/api/push/subscribe-native/",
        "/api/push/status/", "/api/users/", "/api/engagement-signals/",
        "/api/ai-outreach/", "/api/broadcast/", "/api/bug-reports/",
        "/api/inventory/", "/api/keyword-rules/", "/api/wallet/",
    )

    matched_prefix = next((p for p in PROTECTED_PREFIXES if path.startswith(p)), None)
    if not matched_prefix:
        return await call_next(request)

    # Extract the segment immediately after the prefix — that's the user_id
    remainder = path[len(matched_prefix):]
    path_user_id = remainder.split("/")[0].split("?")[0]

    OID_RE = _re.compile(r'^[0-9a-f]{24}$')
    if not OID_RE.match(path_user_id):
        # Not an ObjectId — could be a sub-route like /api/campaigns/scheduler
        return await call_next(request)

    # ── Resolve caller from JWT ───────────────────────────────────────────────
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return _JSONResponse({"detail": "Authentication required"}, status_code=401)

    token = auth[7:]
    caller_id = None
    caller_role = "user"

    # JWT path
    from routers.auth import verify_jwt_token
    payload = verify_jwt_token(token)
    if payload:
        caller_id = payload.get("sub")
        caller_role = payload.get("role", "user") or "user"
    elif token.startswith("impersonate_"):
        # Impersonation session
        try:
            session = await get_db().impersonation_sessions.find_one({"token": token})
            if session:
                uid = session.get("impersonated_user_id") or session.get("user_id")
                if uid:
                    caller_id = str(uid)
                    # Impersonating admin can access anyone
                    caller_role = "super_admin"
        except Exception:
            pass

    if not caller_id:
        return _JSONResponse({"detail": "Authentication required"}, status_code=401)

    # ── Ownership check ───────────────────────────────────────────────────────
    if caller_id == path_user_id:
        # Own data — always allowed
        return await call_next(request)

    if caller_role in ("super_admin", "org_admin", "store_manager"):
        # Admins/managers may access data for users they manage
        # Full scope check deferred to get_data_filter — allow through here
        return await call_next(request)

    # Caller is a regular user trying to access another user's data
    logger.warning(
        f"[BOLA] Blocked {request.method} {path} — "
        f"caller={caller_id} tried to access user_id={path_user_id}"
    )
    return _JSONResponse(
        {"detail": "Access denied — you can only access your own data"},
        status_code=403
    )


@app.middleware("http")
async def log_slow_requests(request: Request, call_next):
    """Log all requests — with impersonation context and error tracking for crash diagnosis."""
    import traceback
    start = time.monotonic()
    
    # Capture impersonation context from headers
    impersonating_as = request.headers.get("X-Impersonating-As")
    real_admin = request.headers.get("X-Real-Admin")
    user_id = request.headers.get("X-User-ID")
    
    if impersonating_as:
        logger.info(f"[IMPERSONATION] Admin {real_admin} acting as {impersonating_as} → {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
    except Exception as e:
        duration = time.monotonic() - start
        ctx = f" [IMPERSONATING as={impersonating_as} admin={real_admin}]" if impersonating_as else ""
        logger.error(f"[UNHANDLED CRASH]{ctx} {request.method} {request.url.path} after {duration:.2f}s — {type(e).__name__}: {e}\n{traceback.format_exc()}")
        raise
    
    duration = time.monotonic() - start
    
    # Log 5xx errors with full context
    if response.status_code >= 500:
        ctx = f" [IMPERSONATING as={impersonating_as} admin={real_admin}]" if impersonating_as else (f" [user={user_id}]" if user_id else "")
        logger.error(f"[SERVER ERROR {response.status_code}]{ctx} {request.method} {request.url.path} {duration:.2f}s")
    
    if duration > 2.0:
        ctx = f" [IMPERSONATING as={impersonating_as}]" if impersonating_as else ""
        logger.warning(f"[SLOW REQUEST]{ctx} {request.method} {request.url.path} took {duration:.2f}s")
    
    return response


# ============= CORS MIDDLEWARE =============
# Strict, env-driven origins. Set CORS_ORIGINS to a comma-separated allowlist in
# production (e.g. "https://app.imonsocial.com,https://imos-deploy-prep.emergent.host").
# "*" keeps it permissive. Native apps send no Origin header, so they're unaffected.
_cors_env = os.environ.get("CORS_ORIGINS", "*").strip()
if _cors_env and _cors_env != "*":
    _allowed_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
else:
    _allowed_origins = ["*"]
logger.info(f"[CORS] Allowed origins: {_allowed_origins}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
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
    return {"message": "I'm On Social API", "version": "2.0"}

@api_router.get("/health")
async def api_health():
    """
    Liveness health check — must always return 200 quickly so K8s/Emergent
    does NOT restart the pod during brief MongoDB hiccups.
    Use /health/deep for full DB connectivity check.
    """
    return {"status": "healthy", "message": "I'm On Social API v2.0"}


@api_router.post("/admin/backfill-last-activity")
async def backfill_last_activity(request: Request):
    """
    One-time admin backfill: populate contacts.last_activity_at from contact_events.
    Run once after deploying the last_activity_at feature.
    Powers the 'sort by recent' contacts query with O(log n) index performance.
    """
    from utils.contact_activity import backfill_last_activity_at
    db = get_db()
    result = await backfill_last_activity_at(db)
    return {"success": True, **result}


@api_router.post("/admin/migrate-sold-campaign")
async def migrate_sold_campaign_endpoint():
    """One-time migration: update all Sold campaigns to long-term only (day 7+). Run once after deploying the SOLD wizard."""
    from services.seed_defaults import migrate_sold_campaign_remove_immediate_steps
    result = await migrate_sold_campaign_remove_immediate_steps()
    return result


@api_router.post("/admin/deduplicate-campaigns")
async def deduplicate_campaigns():
    """
    EMERGENCY: Remove duplicate campaigns created by seeder running multiple times.
    Cancels all pending sends tied to duplicate campaigns.
    Keeps the NEWEST version of each campaign name per user.
    """
    db = get_db()
    all_camps = await db.campaigns.find(
        {}, {"name": 1, "user_id": 1, "created_at": 1}
    ).sort("created_at", -1).to_list(2000)

    seen: dict = {}
    to_delete = []
    for c in all_camps:
        key = f"{c.get('name', '')}__{ c.get('user_id', '')}"
        if key in seen:
            to_delete.append(c["_id"])
        else:
            seen[key] = str(c["_id"])

    if not to_delete:
        return {"message": "No duplicate campaigns found", "deleted": 0}

    dup_ids = [str(i) for i in to_delete]

    # Cancel pending sends from duplicate campaigns
    sends = await db.campaign_pending_sends.update_many(
        {"campaign_id": {"$in": dup_ids}, "status": "pending"},
        {"$set": {"status": "cancelled", "cancelled_reason": "duplicate_campaign_cleanup"}}
    )
    # Cancel enrollments in duplicate campaigns
    enrs = await db.campaign_enrollments.update_many(
        {"campaign_id": {"$in": dup_ids}},
        {"$set": {"status": "cancelled"}}
    )
    # Delete the duplicate campaigns
    deleted = await db.campaigns.delete_many({"_id": {"$in": to_delete}})

    # Also cancel any remaining anniversary sends to prevent re-occurrence
    ann = await db.campaign_pending_sends.update_many(
        {
            "message_template": {"$regex": "anniversary|time flies|another year|been a year", "$options": "i"},
            "status": "pending"
        },
        {"$set": {"status": "cancelled", "cancelled_reason": "anniversary_duplicate_protection"}}
    )

    logger.info(f"[Admin] Deduped campaigns: deleted={deleted.deleted_count} sends_cancelled={sends.modified_count} enrs_cancelled={enrs.modified_count} ann_cancelled={ann.modified_count}")
    return {
        "duplicate_campaigns_deleted": deleted.deleted_count,
        "pending_sends_cancelled": sends.modified_count,
        "enrollments_cancelled": enrs.modified_count,
        "anniversary_sends_cancelled": ann.modified_count,
        "unique_campaigns_kept": len(seen),
    }


@api_router.post("/admin/fix-sold-campaign-sequences")
async def fix_sold_campaign_sequences():
    """
    Fix Sold campaigns so they start at day 7 (not day 0).
    Day 0/2 immediate texts are handled by the SOLD wizard — this prevents duplicates.
    Also sets all tag-triggered campaigns to delivery_mode=auto.
    """
    db = get_db()
    LONG_TERM = [
        {"step": 1, "delay_days": 7,   "channel": "sms", "message_template": "Hey {name}, just checking in! How's everything going? Let me know if you need anything at all."},
        {"step": 2, "delay_days": 21,  "channel": "sms", "message_template": "Hey {name}! Quick question — do you know anyone else who might be looking? I'd love to help them the same way I helped you."},
        {"step": 3, "delay_days": 90,  "channel": "sms", "message_template": "Hey {name}, hope everything is still going great! Thinking of you and wanted to check in. Let me know if you ever need anything."},
        {"step": 4, "delay_days": 180, "channel": "sms", "message_template": "Hey {name}! Hard to believe it's already been 6 months. Hope you're still loving everything. I'm always here if you need me!"},
        {"step": 5, "delay_days": 365, "channel": "sms", "message_template": "Hey {name}! It's been a whole year — time flies! Hope everything is still great. Would love to connect again whenever you're ready."},
    ]
    # Fix Sold campaign sequences
    r1 = await db.campaigns.update_many(
        {"trigger_tag": {"$regex": "^sold$", "$options": "i"}, "active": True},
        {"$set": {"sequences": LONG_TERM, "total_steps": 5, "delivery_mode": "auto",
                  "description": "Long-term follow-up. Day 7+ only — immediate texts handled by SOLD wizard."}}
    )
    # Set all tag-triggered campaigns to auto
    r2 = await db.campaigns.update_many(
        {"trigger_tag": {"$exists": True, "$ne": ""}, "active": True, "delivery_mode": {"$ne": "auto"}},
        {"$set": {"delivery_mode": "auto"}}
    )
    # Cancel duplicate day-0 congratulations sends still pending
    r3 = await db.campaign_pending_sends.update_many(
        {"status": "pending", "step": {"$in": [1, 2]},
         "message_template": {"$regex": "congratulations|excited for you|quick review|great experience", "$options": "i"}},
        {"$set": {"status": "cancelled", "cancelled_reason": "duplicate_of_sold_wizard"}}
    )
    # Update pending sends delivery_mode to auto
    r4 = await db.campaign_pending_sends.update_many(
        {"status": "pending", "delivery_mode": {"$ne": "auto"}},
        {"$set": {"delivery_mode": "auto"}}
    )
    return {
        "sold_campaigns_fixed": r1.modified_count,
        "other_campaigns_set_auto": r2.modified_count,
        "duplicate_sends_cancelled": r3.modified_count,
        "pending_sends_set_auto": r4.modified_count,
    }


@api_router.post("/admin/backfill-user-contact-links")
async def backfill_user_contact_links(request: Request):
    """
    One-time backfill: find all users and link any matching contacts (by email/phone).
    Run once to fix contacts that existed before the auto-link feature was added.
    """
    db = get_db()
    linked = 0
    users = await db.users.find({}, {"_id": 1, "email": 1, "phone": 1, "role": 1, "store_id": 1, "organization_id": 1, "name": 1}).to_list(2000)

    for u in users:
        user_id = str(u["_id"])
        email = u.get("email", "")
        phone = u.get("phone", "")
        role = u.get("role", "user")

        conditions = []
        if email:
            conditions.append({"email": email})
        if phone:
            digits = ''.join(filter(str.isdigit, phone))[-10:]
            if digits:
                conditions.append({"phone": {"$regex": digits}})
        if not conditions:
            continue

        link_update = {"linked_user_id": user_id, "linked_role": role, "updated_at": datetime.utcnow()}
        if u.get("store_id"):
            try:
                sd = await db.stores.find_one({"_id": ObjectId(u["store_id"])}, {"name": 1})
                if sd:
                    link_update["linked_store_id"] = u["store_id"]
                    link_update["linked_store_name"] = sd.get("name", "")
            except Exception:
                pass
        if u.get("organization_id"):
            try:
                od = await db.organizations.find_one({"_id": ObjectId(u["organization_id"])}, {"name": 1})
                if od:
                    link_update["linked_org_name"] = od.get("name", "")
            except Exception:
                pass

        r = await db.contacts.update_many(
            {"$or": conditions, "linked_user_id": {"$exists": False}},
            {"$set": link_update, "$addToSet": {"tags": {"$each": ["imos_user", f"imos_{role}"]}}},
        )
        linked += r.modified_count

    return {"success": True, "contacts_linked": linked, "users_scanned": len(users)}


@api_router.get("/health/deep")
async def api_health_deep():
    """
    Deep health check: DB + scheduler validation.
    Returns 503 if the scheduler is broken — use this for deploy verification.
    """
    issues = []
    details: dict = {}

    # DB ping
    try:
        db = get_db()
        await db.command("ping")
        details["db"] = "connected"
    except Exception as e:
        issues.append(f"DB unreachable: {e!s:.80}")
        details["db"] = "unreachable"

    # Scheduler check
    try:
        from scheduler import scheduler
        if not scheduler.running:
            issues.append("Scheduler is not running")
            details["scheduler"] = "stopped"
        else:
            job_count = len(scheduler.get_jobs())
            details["scheduler"] = f"running ({job_count} jobs)"
            if job_count < 8:   # Should have 12+ jobs; <8 = something is very wrong
                issues.append(f"Scheduler has only {job_count} jobs (expected 12+) — likely a startup error")
    except Exception as e:
        issues.append(f"Scheduler check failed: {e!s:.80}")
        details["scheduler"] = "unknown"

    if issues:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "issues": issues, **details}
        )
    return {"status": "healthy", **details}

@api_router.get("/build-version")
async def build_version():
    """Returns current build version for cache-busting"""
    import hashlib
    start_time = getattr(app.state, 'start_time', 0)
    version = hashlib.sha256(str(start_time).encode()).hexdigest()[:8]
    return {"version": version}


@app.get("/voice-picker")
async def voice_picker():
    """Voice sample picker for choosing Jessi's voice"""
    return FileResponse(str(ROOT_DIR / "static" / "voice-picker.html"), media_type="text/html")

# Debug endpoint removed for security

# ============= BRANDING / STATIC ASSETS =============
@api_router.get("/branding/logo")
async def get_branding_logo():
    """Serve the I'm On Social logo for emails and public pages"""
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
from routers import crm_push
api_router.include_router(crm_push.router)
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
api_router.include_router(keyword_rules.router)
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
api_router.include_router(twilio_admin.router)
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
api_router.include_router(lead_intake.router)
api_router.include_router(ai_reply.router)
api_router.include_router(home_intelligence.router)
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
api_router.include_router(geo.router)
api_router.include_router(va_profiles.router)
api_router.include_router(user_schedule.router)
api_router.include_router(chat_widget.router)
api_router.include_router(media_tracking.router)

from routers import error_reporting
api_router.include_router(error_reporting.router)
from routers import bug_reports
api_router.include_router(bug_reports.router)
from routers import inventory as inventory_mgmt
api_router.include_router(inventory_mgmt.router)
api_router.include_router(wallet_pass.router)

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

# ============= SALES ANALYTICS =============
@api_router.get("/users/{user_id}/sold-performance")
async def get_sold_performance(user_id: str, months: int = 6, month: int = 0, year: int = 0):
    """
    Monthly sold performance: count, referrals, repeat buyers, MoM comparison.
    Used for the Home screen widget and Hub performance section.
    month/year (optional) anchor 'current month' to the client's local date
    so counts don't roll over early/late across timezones.
    """
    db = get_db()
    from datetime import timezone as tz
    now = datetime.now(tz.utc)
    anchor_month = month or now.month
    anchor_year = year or now.year
    results = []
    for i in range(months - 1, -1, -1):
        # Calculate month start/end
        month_offset = anchor_month - i - 1
        yr = anchor_year + (month_offset // 12)
        mo = (month_offset % 12) + 1
        if mo <= 0:
            mo += 12
            yr -= 1
        start = datetime(yr, mo, 1, tzinfo=tz.utc)
        end = datetime(yr + (1 if mo == 12 else 0), (mo % 12) + 1, 1, tzinfo=tz.utc)
        start_naive = start.replace(tzinfo=None)
        end_naive = end.replace(tzinfo=None)

        # Total sold this month (contacts with date_sold in range)
        total = await db.contacts.count_documents({
            "user_id": user_id,
            "date_sold": {"$gte": start_naive, "$lt": end_naive},
            "status": {"$nin": ["hidden", "merged", "deleted"]},
        })
        # Referral sales (had a referrer)
        referrals = await db.contacts.count_documents({
            "user_id": user_id,
            "date_sold": {"$gte": start_naive, "$lt": end_naive},
            "referred_by": {"$exists": True, "$nin": [None, ""]},
            "status": {"$nin": ["hidden", "merged", "deleted"]},
        })
        # Repeat buyers (sold_count > 1 or has purchase_history)
        repeats = await db.contacts.count_documents({
            "user_id": user_id,
            "date_sold": {"$gte": start_naive, "$lt": end_naive},
            "sold_count": {"$gt": 1},
            "status": {"$nin": ["hidden", "merged", "deleted"]},
        })
        results.append({
            "year": yr, "month": mo,
            "label": start.strftime("%b %Y"),
            "short": start.strftime("%b"),
            "total": total,
            "referrals": referrals,
            "repeats": repeats,
            "organic": max(0, total - referrals - repeats),
        })

    # MoM comparison
    current = results[-1] if results else {"total": 0, "referrals": 0, "repeats": 0}
    previous = results[-2] if len(results) >= 2 else {"total": 0, "referrals": 0, "repeats": 0}
    mom_change = current["total"] - previous["total"]
    mom_pct = round((mom_change / previous["total"] * 100) if previous["total"] > 0 else 0)

    # All-time totals
    all_time = await db.contacts.count_documents({
        "user_id": user_id,
        "date_sold": {"$exists": True, "$ne": None},
        "status": {"$nin": ["hidden", "merged", "deleted"]},
    })
    all_referrals = await db.contacts.count_documents({
        "user_id": user_id,
        "referred_by": {"$exists": True, "$nin": [None, ""]},
        "status": {"$nin": ["hidden", "merged", "deleted"]},
    })

    return {
        "monthly": results,
        "current_month": current,
        "previous_month": previous,
        "mom_change": mom_change,
        "mom_pct": mom_pct,
        "all_time_sold": all_time,
        "all_time_referrals": all_referrals,
    }



MANAGER_ROLES = ("super_admin", "admin", "manager", "store_manager", "org_admin")


async def _team_user_ids(db, user_id: str):
    """Return (is_manager, [user_ids]) for the requester's team scope."""
    requester = await db.users.find_one({"_id": ObjectId(user_id)}, {"role": 1, "store_id": 1})
    role = (requester or {}).get("role", "user")
    if role not in MANAGER_ROLES:
        return False, [user_id]
    if role in ("super_admin", "org_admin"):
        users_q: dict = {"active": {"$ne": False}}
    else:
        users_q = {"store_id": requester.get("store_id"), "active": {"$ne": False}}
    reps = await db.users.find(users_q, {"_id": 1}).to_list(300)
    return True, [str(r["_id"]) for r in reps]


@api_router.get("/users/{user_id}/sold-contacts")
async def get_sold_contacts_list(user_id: str, filter_type: str = "sold", month: int = 0, year: int = 0, scope: str = "me"):
    """Return filtered sold contacts for home screen tile taps."""
    db = get_db()
    from datetime import timezone as _tz
    now_dt = datetime.now(_tz.utc)
    m = month or now_dt.month
    y = year or now_dt.year
    start = datetime(y, m, 1)
    end = datetime(y + (1 if m == 12 else 0), (m % 12) + 1, 1)
    base: dict = {
        "user_id": user_id,
        "date_sold": {"$gte": start.replace(tzinfo=None), "$lt": end.replace(tzinfo=None)},
        "status": {"$nin": ["hidden", "merged", "deleted"]},
    }
    rep_names: dict = {}
    if scope == "team":
        is_mgr, ids = await _team_user_ids(db, user_id)
        if is_mgr:
            base["user_id"] = {"$in": ids}
            reps = await db.users.find({"_id": {"$in": [ObjectId(i) for i in ids]}}, {"name": 1}).to_list(300)
            rep_names = {str(r["_id"]): r.get("name", "") for r in reps}
    if filter_type == "referrals":
        base["referred_by"] = {"$exists": True, "$nin": [None, ""]}
    elif filter_type == "repeats":
        base["sold_count"] = {"$gt": 1}
    contacts = await db.contacts.find(base, {
        "_id": 1, "first_name": 1, "last_name": 1, "phone": 1, "user_id": 1,
        "vehicle": 1, "date_sold": 1, "sold_count": 1, "referred_by_name": 1, "photo_thumbnail": 1
    }).sort("date_sold", -1).to_list(500)
    return {"contacts": [{
        "_id": str(c["_id"]),
        "name": f"{c.get('first_name','')} {c.get('last_name','')}".strip(),
        "phone": c.get("phone", ""),
        "vehicle": c.get("vehicle", ""),
        "date_sold": c["date_sold"].isoformat() if c.get("date_sold") else "",
        "sold_count": c.get("sold_count", 1),
        "referred_by_name": c.get("referred_by_name", ""),
        "photo_thumbnail": c.get("photo_thumbnail", ""),
        "rep_name": rep_names.get(c.get("user_id", ""), ""),
    } for c in contacts], "total": len(contacts)}


@api_router.get("/users/{user_id}/sold-monthly-summary")
async def get_sold_monthly_summary(user_id: str, filter_type: str = "sold", scope: str = "me", month: int = 0, year: int = 0):
    """Monthly sold counts for the last 24 months plus year totals.
    month/year (optional) anchor the series to the client's local current month."""
    db = get_db()
    from datetime import timezone as _tz
    now_dt = datetime.now(_tz.utc)
    anchor_m = month or now_dt.month
    anchor_y = year or now_dt.year
    window_start = datetime(anchor_y - 2, anchor_m, 1)
    match: dict = {
        "user_id": user_id,
        "date_sold": {"$gte": window_start, "$ne": None},
        "status": {"$nin": ["hidden", "merged", "deleted"]},
    }
    is_manager = False
    if scope == "team":
        is_manager, ids = await _team_user_ids(db, user_id)
        if is_manager:
            match["user_id"] = {"$in": ids}
    if filter_type == "referrals":
        match["referred_by"] = {"$exists": True, "$nin": [None, ""]}
    elif filter_type == "repeats":
        match["sold_count"] = {"$gt": 1}
    pipeline = [
        {"$match": match},
        {"$group": {"_id": {"y": {"$year": "$date_sold"}, "m": {"$month": "$date_sold"}}, "total": {"$sum": 1}}},
    ]
    rows = await db.contacts.aggregate(pipeline).to_list(60)
    by_key = {(r["_id"]["y"], r["_id"]["m"]): r["total"] for r in rows}
    months = []
    y, m = anchor_y, anchor_m
    for _ in range(24):
        months.append({"year": y, "month": m, "label": datetime(y, m, 1).strftime("%b %Y"), "total": by_key.get((y, m), 0)})
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    months.reverse()
    year_totals: dict = {}
    for row in months:
        key = str(row["year"])
        year_totals[key] = year_totals.get(key, 0) + row["total"]
    return {"months": months, "year_totals": year_totals, "is_manager": is_manager if scope == "team" else None}


@api_router.get("/team/{user_id}/performance")
async def get_team_performance(user_id: str, month: int = 0, year: int = 0):
    """Team sales performance grouped by store. Admin sees all stores, others see their store."""
    db = get_db()
    from datetime import timezone as _tz
    now_dt = datetime.now(_tz.utc)
    m = month or now_dt.month
    y = year or now_dt.year
    start = datetime(y, m, 1).replace(tzinfo=None)
    end = datetime(y + (1 if m == 12 else 0), (m % 12) + 1, 1).replace(tzinfo=None)
    requester = await db.users.find_one({"_id": ObjectId(user_id)}, {"role": 1, "store_id": 1})
    if not requester:
        raise HTTPException(status_code=404, detail="User not found")
    role = requester.get("role", "user")
    is_admin = role in ("super_admin", "org_admin")
    users_q: dict = {"active": {"$ne": False}} if is_admin else {"store_id": requester.get("store_id"), "active": {"$ne": False}}
    reps = await db.users.find(users_q, {"_id": 1, "name": 1, "store_id": 1, "role": 1, "photo_thumbnail": 1}).to_list(200)
    store_ids = list({str(r.get("store_id", "")) for r in reps if r.get("store_id")})
    stores_map: dict = {}
    for sid in store_ids:
        try:
            s = await db.stores.find_one({"_id": ObjectId(sid)}, {"name": 1})
            stores_map[sid] = (s or {}).get("name", "Unknown Store")
        except Exception:
            stores_map[sid] = "Unknown Store"
    results: dict = {}
    for rep in reps:
        rid = str(rep["_id"])
        sid = str(rep.get("store_id", "")) or "no_store"
        store_name = stores_map.get(sid, "No Store")
        sold = await db.contacts.count_documents({"user_id": rid, "date_sold": {"$gte": start, "$lt": end}, "status": {"$nin": ["hidden", "merged", "deleted"]}})
        refs = await db.contacts.count_documents({"user_id": rid, "date_sold": {"$gte": start, "$lt": end}, "referred_by": {"$exists": True, "$nin": [None, ""]}, "status": {"$nin": ["hidden", "merged", "deleted"]}})
        rpts = await db.contacts.count_documents({"user_id": rid, "date_sold": {"$gte": start, "$lt": end}, "sold_count": {"$gt": 1}, "status": {"$nin": ["hidden", "merged", "deleted"]}})
        all_t = await db.contacts.count_documents({"user_id": rid, "date_sold": {"$exists": True, "$ne": None}, "status": {"$nin": ["hidden", "merged", "deleted"]}})
        if sid not in results:
            results[sid] = {"store_id": sid, "store_name": store_name, "reps": [], "totals": {"sold": 0, "referrals": 0, "repeats": 0, "all_time": 0}}
        results[sid]["reps"].append({"user_id": rid, "name": rep.get("name", "?"), "role": role, "photo": rep.get("photo_thumbnail", ""), "sold": sold, "referrals": refs, "repeats": rpts, "all_time": all_t})
        for k, v in [("sold", sold), ("referrals", refs), ("repeats", rpts), ("all_time", all_t)]:
            results[sid]["totals"][k] += v
    for sid in results:
        results[sid]["reps"].sort(key=lambda r: -r["sold"])
    return {"stores": list(results.values()), "month": m, "year": y, "month_label": datetime(y, m, 1).strftime("%B %Y"), "is_admin": is_admin}


# ============= REVIEW LINKS ENDPOINTS =============

# ============= REVIEW LINKS ENDPOINTS =============
@api_router.get("/users/{user_id}/review-links")
async def get_review_links(user_id: str):
    """Get user's review links. Returns the I'm On Social review landing page URL as first choice,
    structured links, and the flat review_url field. Falls back through store → direct."""
    db = get_db()
    APP_BASE = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))

    user = await db.users.find_one(
        {"_id": ObjectId(user_id)},
        {"review_links": 1, "review_url": 1, "custom_link_name": 1, "store_id": 1, "store_slug": 1}
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    review_links = user.get("review_links") or {}
    review_url   = user.get("review_url", "") or ""
    store_slug   = user.get("store_slug", "") or ""

    # Try to get store slug from store document if not on user
    if not store_slug and user.get("store_id"):
        try:
            store = await db.stores.find_one(
                {"_id": ObjectId(str(user["store_id"]))},
                {"slug": 1, "review_links": 1}
            )
            if store:
                store_slug = store.get("slug", "") or ""
                if not review_links and not review_url:
                    sl = store.get("review_links") or {}
                    review_url = sl.get("google", "") or sl.get("yelp", "") or sl.get("facebook", "") or ""
                    review_links = sl
        except Exception:
            pass

    # Build the I'm On Social review landing page URL (preferred — shows Google/Yelp/Facebook options)
    if store_slug:
        imos_review_url = f"{APP_BASE}/review/{store_slug}?sp={user_id}"
    else:
        # No store slug — fall back to direct review URL
        imos_review_url = review_url or review_links.get("google", "") or review_links.get("yelp", "") or ""

    # Best single direct URL (fallback for platforms that can't load the landing page)
    best_direct_url = (
        review_links.get("google") or review_links.get("yelp") or
        review_links.get("facebook") or review_url or ""
    )

    return {
        "imos_review_url": imos_review_url,   # ← USE THIS: the I'm On Social review page
        "review_links": review_links,
        "review_url": best_direct_url,        # direct fallback
        "store_slug": store_slug,
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
    # Always merge permissions with role defaults so Hub sections never disappear
    # after refreshUserData (raw DB may have null/stale feature_permissions)
    from permissions import merge_permissions
    user["feature_permissions"] = merge_permissions(user.get("feature_permissions"), user.get("role", "user"))
    return user


@api_router.patch("/users/{user_id}")
async def patch_user_profile(user_id: str, data: dict):
    """Update user profile fields. Photo updates must go through POST /profile/{user_id}/photo."""
    db = get_db()
    allowed_fields = ['name', 'phone', 'persona', 'settings', 'photo_url', 'bio', 'social_links',
                      'timezone', 'address', 'city', 'state', 'zip_code', 'country',
                      'notification_settings', 'ai_master_paused']
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
    
    # Return the updated user data with properly merged permissions
    updated_user = await db.users.find_one({"_id": ObjectId(user_id)}, {"password": 0})
    if updated_user:
        updated_user["_id"] = str(updated_user["_id"])
        for key in ["organization_id", "org_id", "store_id", "partner_id"]:
            if updated_user.get(key):
                updated_user[key] = str(updated_user[key])
        from permissions import merge_permissions
        updated_user["feature_permissions"] = merge_permissions(updated_user.get("feature_permissions"), updated_user.get("role", "user"))
    
    return updated_user


# ============= ACTIVITY FEED ENDPOINT =============
from cachetools import TTLCache as _TTLCache
_activity_cache: _TTLCache = _TTLCache(maxsize=500, ttl=30)  # bounded, auto-evicts

@api_router.get("/activity/{user_id}")
async def get_activity_feed(user_id: str, limit: int = 20):
    """
    Get team activity feed based on user's role. Cached 30s to prevent thundering herd.
    """
    import time as _time
    cached = _activity_cache.get(user_id)
    if cached is not None:
        return cached

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
    
    result = {
        "activities": activities[:limit],
        "user_role": user.get('role', 'user'),
        "total": len(activities)
    }
    _activity_cache[user_id] = result
    return result

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

                # ── Quote payment ────────────────────────────────────────────
                if metadata.get("type") == "quote_payment":
                    quote_id = metadata.get("quote_id")
                    if quote_id:
                        try:
                            await db.subscription_quotes.update_one(
                                {"_id": ObjectId(quote_id)},
                                {"$set": {
                                    "payment_status": "paid",
                                    "paid_at":        datetime.utcnow(),
                                    "payment_session_id": webhook_response.session_id,
                                }}
                            )
                            logger.info(f"[Stripe] Quote {quote_id} marked as paid via webhook")
                        except Exception as qe:
                            logger.error(f"[Stripe] Quote payment update failed for {quote_id}: {qe}")

                # ── Partner agreement payment ────────────────────────────────
                elif metadata.get("type") == "partner_agreement":
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
    return {"status": "healthy", "message": "I'm On Social API v2.0"}

@app.get("/")
async def app_root():
    return {"status": "healthy", "message": "I'm On Social API v2.0"}


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
    logger.info("I'm On Social API v2.0 starting...")
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

    # ── Backfill account_id for existing users ────────────────────────────────
    # One-time migration: super_admins get account_id = their own _id,
    # other users get account_id from their creator's account (approx via org/store match).
    async def _backfill_account_ids():
        try:
            db = get_db()
            # 1. Stamp super_admins who have no account_id
            admins = await db.users.find(
                {"role": "super_admin", "account_id": {"$exists": False}},
                {"_id": 1}
            ).to_list(500)
            for a in admins:
                await db.users.update_one(
                    {"_id": a["_id"]},
                    {"$set": {"account_id": str(a["_id"])}}
                )

            # 2. Stamp other users based on who created them (org/store match with a super_admin)
            super_admins = await db.users.find(
                {"role": "super_admin"},
                {"_id": 1, "account_id": 1, "organization_id": 1, "store_id": 1}
            ).to_list(200)

            unstamped = await db.users.count_documents(
                {"account_id": {"$exists": False}, "role": {"$ne": "super_admin"}}
            )
            if unstamped > 0:
                for sa in super_admins:
                    sa_account = sa.get("account_id") or str(sa["_id"])
                    match: dict = {"account_id": {"$exists": False}}
                    if sa.get("organization_id"):
                        match["organization_id"] = sa["organization_id"]
                    elif sa.get("store_id"):
                        match["store_id"] = sa["store_id"]
                    else:
                        # Super admin with no org — match users with no org
                        match["$or"] = [
                            {"organization_id": {"$in": [None, ""]}},
                            {"organization_id": {"$exists": False}},
                        ]
                    await db.users.update_many(match, {"$set": {"account_id": sa_account}})

            stamped = await db.users.count_documents({"account_id": {"$exists": True}})
            logger.info(f"[Startup] account_id backfill: {stamped} users now have account_id")
        except Exception as e:
            logger.warning(f"[Startup] account_id backfill skipped: {e}")

    import asyncio as _aio3
    _aio3.create_task(_backfill_account_ids())
    # Enforces: one phone number = one named contact = one conversation.
    # Safe to run on every startup — skips already-merged contacts.
    async def _consolidate_phone_contacts():
        try:
            db = get_db()
            GENERIC = {"Contact", "Unknown", "New Lead", "", None}

            def _quality(c: dict) -> int:
                n = (c.get("name") or f"{c.get('first_name','')} {c.get('last_name','')}".strip()).strip()
                if not n or n in GENERIC: return 0
                if n.startswith("Lead ("): return 1
                return 2  # Real name — wins

            # Find all contacts that have a phone number, grouped in memory
            all_contacts = await db.contacts.find(
                {"phone": {"$exists": True, "$ne": ""}},
                {"_id": 1, "phone": 1, "name": 1, "first_name": 1, "last_name": 1, "user_id": 1}
            ).to_list(50000)

            # Group by normalised phone
            from collections import defaultdict
            groups: dict = defaultdict(list)
            for c in all_contacts:
                raw = (c.get("phone") or "").strip()
                if not raw: continue
                # Normalise: always +1XXXXXXXXXX
                digits = "".join(ch for ch in raw if ch.isdigit())
                if len(digits) == 10:  digits = "1" + digits
                if len(digits) == 11 and digits.startswith("1"): digits = digits
                groups[digits].append(c)

            merged_contacts = 0
            merged_convs    = 0

            for digits, contacts in groups.items():
                if len(contacts) < 2:
                    continue

                contacts.sort(key=_quality, reverse=True)
                winner   = contacts[0]
                losers   = contacts[1:]
                winner_id = str(winner["_id"])

                for loser in losers:
                    loser_id = str(loser["_id"])
                    if _quality(loser) >= _quality(winner):
                        continue  # Both are named — skip to avoid bad merges

                    # Re-point all conversations from loser → winner
                    w_name = (winner.get("name") or f"{winner.get('first_name','')} {winner.get('last_name','')}".strip()).strip()
                    conv_res = await db.conversations.update_many(
                        {"contact_id": loser_id},
                        {"$set": {"contact_id": winner_id, "contact_name": w_name or ""}}
                    )
                    if conv_res.modified_count:
                        merged_convs += conv_res.modified_count

                    # Re-point messages, events, enrollments, tasks
                    for col in ("messages", "contact_events", "campaign_enrollments", "tasks", "notes", "call_logs"):
                        await db[col].update_many(
                            {"contact_id": loser_id},
                            {"$set": {"contact_id": winner_id}}
                        )

                    # Mark loser as merged
                    await db.contacts.update_one(
                        {"_id": loser["_id"]},
                        {"$set": {"merged_into": winner_id, "merged_at": datetime.utcnow()}}
                    )
                    merged_contacts += 1

            # Merge duplicate conversations for the same user + phone
            # Find conversations with the same contact_id, keep the most recent
            cursor = db.conversations.aggregate([
                {"$match": {"contact_id": {"$exists": True}}},
                {"$group": {
                    "_id": {"user_id": "$user_id", "contact_id": "$contact_id"},
                    "convs": {"$push": {"id": "$_id", "last": "$last_message_at"}},
                    "count": {"$sum": 1}
                }},
                {"$match": {"count": {"$gt": 1}}}
            ])
            async for group in cursor:
                convs_in_group = sorted(
                    group["convs"],
                    key=lambda x: str(x.get("last") or ""),
                    reverse=True
                )
                primary_id = convs_in_group[0]["id"]
                for dup in convs_in_group[1:]:
                    dup_id = str(dup["id"])
                    primary_str = str(primary_id)
                    await db.messages.update_many(
                        {"conversation_id": dup_id},
                        {"$set": {"conversation_id": primary_str}}
                    )
                    await db.conversations.update_one(
                        {"_id": dup["id"]},
                        {"$set": {"status": "closed", "merged_into": primary_str}}
                    )
                    merged_convs += 1

            if merged_contacts or merged_convs:
                logger.info(f"[Startup] Phone consolidation: {merged_contacts} duplicate contacts merged, {merged_convs} conversations consolidated")
            else:
                logger.info("[Startup] Phone consolidation: all clean — no duplicates found")
        except Exception as e:
            logger.warning(f"[Startup] Phone consolidation skipped: {e}")

    import asyncio as _aio2
    _aio2.create_task(_consolidate_phone_contacts())

    # Self-heal: re-link voice notes whose audio_url was never saved (storage response bug),
    # then convert any stored webm memos to m4a so they play on iOS
    async def _voice_note_backfill():
        try:
            from routers.voice_notes import run_audio_backfill, run_webm_conversion
            result = await run_audio_backfill()
            if result.get("notes_scanned"):
                logger.info(f"[Startup] Voice note audio backfill: {result}")
            conv = await run_webm_conversion()
            if conv.get("scanned"):
                logger.info(f"[Startup] Voice note webm conversion: {conv}")
        except Exception as e:
            logger.warning(f"[Startup] Voice note backfill skipped: {e}")
    _aio2.create_task(_voice_note_backfill())

    # ONE-TIME migration: birthday/anniversary sends become manual opt-in.
    # Wipes previously auto-applied Birthday/Anniversary tags and cancels
    # enrollments created by the old save-time auto-enroll (which fired
    # messages immediately instead of on the actual date).
    async def _date_optin_migration():
        try:
            db = get_db()
            if await db.migrations.find_one({"_id": "date_optin_reset_2026_08"}):
                return
            r1 = await db.contacts.update_many(
                {},
                {"$pull": {"tags": {"$in": [
                    "Birthday", "birthday", "BIRTHDAY",
                    "Anniversary", "anniversary", "ANNIVERSARY",
                ]}}},
            )
            enr_filter = {"status": "active", "$or": [
                {"trigger_type": {"$in": ["birthday", "anniversary", "sold_date"]}},
                {"trigger_type": "tag", "trigger_tag": {"$in": ["Birthday", "birthday", "Anniversary", "anniversary"]}},
            ]}
            enr_ids = [str(e["_id"]) async for e in db.campaign_enrollments.find(enr_filter, {"_id": 1})]
            cancelled_sends = 0
            if enr_ids:
                await db.campaign_enrollments.update_many(
                    enr_filter, {"$set": {"status": "cancelled", "cancel_reason": "date_optin_reset"}}
                )
                rs = await db.campaign_pending_sends.update_many(
                    {"enrollment_id": {"$in": enr_ids}, "status": "pending"},
                    {"$set": {"status": "cancelled", "cancel_reason": "date_optin_reset"}},
                )
                cancelled_sends = rs.modified_count
            await db.migrations.insert_one({
                "_id": "date_optin_reset_2026_08",
                "tags_cleared_on": r1.modified_count,
                "enrollments_cancelled": len(enr_ids),
                "pending_sends_cancelled": cancelled_sends,
                "ran_at": datetime.utcnow(),
            })
            logger.info(f"[Startup] Date opt-in reset: tags cleared on {r1.modified_count} contacts, "
                        f"{len(enr_ids)} enrollments + {cancelled_sends} pending sends cancelled")
        except Exception as e:
            logger.warning(f"[Startup] Date opt-in reset failed: {e}")
    _aio2.create_task(_date_optin_migration())

    # Sync internal docs (PRD / Ops Manual / App Scope) from repo files into Admin → Docs
    async def _doc_sync():
        try:
            from routers.docs import sync_repo_docs
            result = await sync_repo_docs()
            if result.get("synced"):
                logger.info(f"[Startup] Internal docs synced: {result}")
        except Exception as e:
            logger.warning(f"[Startup] Doc sync failed: {e}")
    _aio2.create_task(_doc_sync())
    # Removes any accidentally-stored test prompts from the ai_clone_prompts collection
    try:
        db = get_db()
        deleted = await db.ai_clone_prompts.delete_many({
            "scope": "global",
            "$or": [
                {"prompt": {"$regex": "^Test global prompt"}},
                {"prompt": {"$regex": "^Test "}},
            ]
        })
        if deleted.deleted_count:
            logger.info(f"[Startup] Removed {deleted.deleted_count} test AI prompt(s) from DB — will use built-in DEFAULT_CLONE_PROMPT")
    except Exception as e:
        logger.warning(f"[Startup] AI prompt cleanup skipped: {e}")
    
    # Create database indexes for performance (non-blocking)
    try:
        import asyncio
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
                    # Compound index for catchup query: (user_id, status, send_at) — prevents collection scan
                    db.campaign_pending_sends.create_index([("user_id", 1), ("status", 1), ("send_at", 1)]),
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
                    # Login brute-force tracking — TTL auto-cleans stale records after 1 day
                    db.login_attempts.create_index("updated_at", expireAfterSeconds=86400),
                    # last_activity_at — powers "recent" sort without in-memory aggregation
                    db.contacts.create_index([("user_id", 1), ("last_activity_at", -1)]),
                    db.contacts.create_index([("user_id", 1), ("last_activity_at", -1), ("status", 1)]),
                    # Short URLs — user's link listing and cleanup
                    db.short_urls.create_index([("user_id", 1), ("created_at", -1)]),
                    db.short_urls.create_index([("short_code", 1)]),
                    # Notifications — user reads (also has TTL applied separately)
                    db.notifications.create_index([("user_id", 1), ("created_at", -1)]),
                    db.notifications.create_index([("idempotency_key", 1)], unique=False, sparse=True),  # Notification dedup
                    # Congrats cards — tracking and reporting
                    db.congrats_cards_sent.create_index([("user_id", 1), ("sent_at", -1)]),
                    db.congrats_cards_sent.create_index([("salesman_id", 1), ("sent_at", -1)]),
                    # Notification center — compound indexes for all 8 section queries
                    # Section 6: contact_events by user + timestamp + event_type (was doing full collection scan)
                    db.contact_events.create_index([("user_id", 1), ("event_type", 1), ("timestamp", -1)]),
                    # Section 4/5: conversations by participants
                    db.conversations.create_index([("participants", 1), ("unread", 1), ("updated_at", -1)]),
                    db.conversations.create_index([("participants", 1), ("flagged", 1), ("updated_at", -1)]),
                    # Section 8: engagement signals by user + type + date
                    db.notifications.create_index([("user_id", 1), ("type", 1), ("created_at", -1)]),
                    # customer_feedback — Review Center queries
                    db.customer_feedback.create_index([("salesperson_id", 1), ("approved", 1), ("created_at", -1)]),
                    db.customer_feedback.create_index([("salesperson_id", 1), ("created_at", -1)]),
                    # ai_reply_queue — scheduler lookup: status + send_at (runs every 60s)
                    db.ai_reply_queue.create_index([("status", 1), ("send_at", 1)]),
                    db.ai_reply_queue.create_index([("contact_id", 1), ("status", 1)]),
                    db.ai_reply_queue.create_index([("assigned_user_id", 1), ("status", 1), ("requires_approval", 1)]),
                ), timeout=15)
                logger.info("Database indexes created/verified (production-ready)")

                # TTL indexes — run separately so a failure doesn't block all indexes
                # These auto-expire old data to prevent unbounded collection growth
                try:
                    import pymongo
                    one_year_secs   = 365 * 24 * 3600
                    two_year_secs   = 2 * one_year_secs
                    ninety_day_secs = 90 * 24 * 3600

                    # short_url_clicks: keep 1 year of click analytics
                    await db.short_url_clicks.create_index(
                        [("clicked_at", pymongo.ASCENDING)],
                        expireAfterSeconds=one_year_secs,
                        background=True,
                    )
                    # notifications: expire after 90 days (users rarely read old ones)
                    await db.notifications.create_index(
                        [("created_at", pymongo.ASCENDING)],
                        expireAfterSeconds=ninety_day_secs,
                        background=True,
                    )
                    # contact_events: archive after 2 years (compliance-safe retention)
                    await db.contact_events.create_index(
                        [("timestamp", pymongo.ASCENDING)],
                        expireAfterSeconds=two_year_secs,
                        background=True,
                    )
                    logger.info("TTL indexes created — data auto-expires to prevent unbounded growth")
                except Exception as ttl_err:
                    logger.warning(f"TTL index creation failed (non-critical): {ttl_err}")

                # Unique index on inbound_message_dedup.message_sid — enables atomic Twilio retry dedup
                try:
                    await db.inbound_message_dedup.create_index(
                        "message_sid", unique=True, background=True
                    )
                    await db.inbound_message_dedup.create_index(
                        "created_at",
                        expireAfterSeconds=3600,  # Auto-clean dedup records after 1 hour
                        background=True,
                    )
                    logger.info("inbound_message_dedup index created — Twilio retry dedup active")
                except Exception as dedup_idx_err:
                    logger.warning(f"inbound_message_dedup index skipped: {dedup_idx_err}")
            except asyncio.TimeoutError:
                logger.warning("Index creation timed out - will retry on first request")
    except Exception as e:
        logger.warning(f"Index creation skipped: {e}")
    
    # PRD/Ops Manual/App Scope now sync from /app/docs via routers.docs.sync_repo_docs()
    # (the old raw PRD.md sync lives on as the "PRD Working Log" doc — see REPO_DOC_SOURCES)

    # ── Auto-assign Twilio phone number to the primary admin on every deploy ──
    # Uses ADMIN_EMAIL env var if set, otherwise falls back to first super_admin.
    # Idempotent — safe to run every startup. Will NOT overwrite an existing number.
    try:
        twilio_phone = os.environ.get("TWILIO_PHONE_NUMBER", "").strip()
        if twilio_phone:
            # Try ADMIN_EMAIL first for precision
            admin_email = os.environ.get("ADMIN_EMAIL", "").strip()
            admin_user = None
            if admin_email:
                admin_user = await db.users.find_one({"email": admin_email}, {"_id": 1, "name": 1, "twilio_number": 1, "mvpline_number": 1})
            # Fallback: super_admin with most recent login or highest _id
            if not admin_user:
                admin_user = await db.users.find_one(
                    {"role": "super_admin"},
                    {"_id": 1, "name": 1, "twilio_number": 1, "mvpline_number": 1},
                    sort=[("created_at", 1)]  # Oldest = primary admin
                )
            if admin_user:
                existing_number = admin_user.get("twilio_number") or admin_user.get("mvpline_number")
                if existing_number and existing_number != twilio_phone:
                    # User already has a number assigned — do NOT overwrite it
                    logger.info(f"[Startup] Skipping auto-assign: {admin_user.get('name')} already has {existing_number} (env has {twilio_phone})")
                else:
                    await db.users.update_one(
                        {"_id": admin_user["_id"]},
                        {"$set": {
                            "mvpline_number": twilio_phone,
                            "twilio_number":  twilio_phone,
                        }}
                    )
                    logger.info(f"[Startup] Twilio number {twilio_phone} auto-assigned to {admin_user.get('name','admin')}")
    except Exception as e:
        logger.warning(f"[Startup] Twilio number auto-assign skipped: {e}")

    # ── Auto-fix Twilio webhook URLs on every deploy ───────────────────────────
    # Ensures all purchased numbers point to THIS app's inbound endpoint.
    # Runs in background so it doesn't slow down startup.
    async def _fix_twilio_webhooks():
        try:
            import asyncio as _asyncio
            from twilio.rest import Client as _TwilioClient
            tw_sid   = os.environ.get("TWILIO_ACCOUNT_SID", "")
            tw_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
            if not tw_sid or not tw_token:
                return  # Twilio not configured — skip silently

            base_url    = os.environ.get("PUBLIC_FACING_URL", os.environ.get("APP_URL", "https://app.imonsocial.com"))
            sms_url     = f"{base_url}/api/webhooks/twilio/incoming"
            voice_url   = f"{base_url}/api/webhooks/twilio/voice"
            client = _TwilioClient(tw_sid, tw_token)
            numbers = await _asyncio.to_thread(client.incoming_phone_numbers.list)
            fixed = 0
            for n in numbers:
                sms_ok   = (n.sms_url or "") == sms_url
                voice_ok = (n.voice_url or "") == voice_url
                if not sms_ok or not voice_ok:
                    await _asyncio.to_thread(
                        client.incoming_phone_numbers(n.sid).update,
                        sms_url=sms_url,
                        sms_method="POST",
                        voice_url=voice_url,
                        voice_method="POST",
                    )
                    logger.info(f"[Startup] Fixed webhooks for {n.phone_number} (sms={not sms_ok}, voice={not voice_ok})")
                    fixed += 1
            if fixed:
                logger.info(f"[Startup] Fixed {fixed} Twilio number(s) — SMS + Voice URLs updated")
            else:
                logger.info(f"[Startup] All Twilio webhooks already correct")
        except Exception as e:
            logger.warning(f"[Startup] Twilio webhook auto-fix skipped: {e}")

    import asyncio as _aio
    _aio.create_task(_fix_twilio_webhooks())

    # Start the background campaign scheduler
    try:
        from scheduler import start_scheduler
        start_scheduler()
        logger.info("Campaign scheduler started")
    except Exception as e:
        logger.warning(f"Scheduler start failed (non-fatal): {e}")

    # One-time migration: upgrade any existing campaigns with delivery_mode="manual"
    # to delivery_mode="auto" so they actually fire.
    # Safe to run every startup — only updates campaigns that still have the old value.
    try:
        db = get_db()
        result = await db.campaigns.update_many(
            {"delivery_mode": {"$in": ["manual", None, ""]}},
            {"$set": {"delivery_mode": "auto"}}
        )
        if result.modified_count > 0:
            logger.info(f"[Migration] Upgraded {result.modified_count} campaign(s) from manual → auto delivery_mode")
        # Cancel all old stuck pending_sends rather than releasing them.
        # These were created before the delivery_mode bug was fixed — releasing them
        # would flood customers with out-of-sequence messages from months ago.
        # New enrollments from today forward will create fresh pending_sends with delivery_mode="auto".
        sends_result = await db.campaign_pending_sends.update_many(
            {"delivery_mode": {"$in": ["manual", None, ""]}, "status": {"$in": ["pending_user_action", "pending"]}},
            {"$set": {"status": "cancelled", "cancelled_reason": "pre-fix manual delivery_mode — cancelled on deploy"}}
        )
        if sends_result.modified_count > 0:
            logger.info(f"[Migration] Cancelled {sends_result.modified_count} old stuck pending_sends (pre-fix). New enrollments will work correctly.")
    except Exception as e:
        logger.warning(f"Campaign delivery_mode migration failed (non-fatal): {e}")

    logger.info("I'm On Social API v2.0 started")

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
                "password": "I'm On Social2026!",
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
            logger.info("  Password: I'm On Social2026!")
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
