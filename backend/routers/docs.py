"""
Company Documents Router
Admin-only document hub: Security Policy, Company Policy, ToS, Privacy, Training, Integrations
"""
from fastapi import APIRouter, HTTPException, Header
from bson import ObjectId
from datetime import datetime
from typing import Optional
import logging

from routers.database import get_db, get_user_by_id

router = APIRouter(prefix="/docs", tags=["Docs"])
logger = logging.getLogger(__name__)


async def verify_admin_access(user_id: str) -> dict:
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.get('role') not in ['super_admin', 'org_admin', 'store_manager']:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/")
async def list_docs(
    category: Optional[str] = None,
    search: Optional[str] = None,
    x_user_id: str = Header(None, alias="X-User-ID"),
):
    user = await verify_admin_access(x_user_id)
    user_role = user.get("role", "")
    db = get_db()

    query: dict = {"is_published": True}
    # Filter out docs that require a higher role than the user has
    if user_role != "super_admin":
        query["required_role"] = {"$ne": "super_admin"}
    if category:
        query["category"] = category
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"summary": {"$regex": search, "$options": "i"}},
        ]

    docs = await db.company_docs.find(query, {"slides": 0}).sort([
        ("sort_order", 1),
        ("title", 1),
    ]).to_list(100)

    for d in docs:
        d["_id"] = str(d["_id"])

    return docs


@router.get("/categories")
async def get_categories(x_user_id: str = Header(None, alias="X-User-ID")):
    await verify_admin_access(x_user_id)
    return [
        {"id": "operations", "name": "Operations Manual", "icon": "book", "color": "#00C7BE"},
        {"id": "security", "name": "Cyber Security", "icon": "shield-checkmark", "color": "#FF3B30"},
        {"id": "company_policy", "name": "Company Policy", "icon": "business", "color": "#5856D6"},
        {"id": "legal", "name": "Legal", "icon": "document-text", "color": "#007AFF"},
        {"id": "training", "name": "Training", "icon": "school", "color": "#34C759"},
        {"id": "integrations", "name": "Integrations", "icon": "git-network", "color": "#FF9500"},
    ]


@router.get("/{doc_id}")
async def get_doc(doc_id: str, x_user_id: str = Header(None, alias="X-User-ID")):
    user = await verify_admin_access(x_user_id)
    db = get_db()

    doc = await db.company_docs.find_one({"_id": ObjectId(doc_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check role-restricted docs
    if doc.get("required_role") == "super_admin" and user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Access restricted")

    doc["_id"] = str(doc["_id"])
    return doc


@router.post("/seed-project-scope")
async def seed_project_scope(x_user_id: str = Header(None, alias="X-User-ID")):
    """Create or update the master iMOs Platform Operations Manual"""
    user = await verify_admin_access(x_user_id)
    if user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin only")

    db = get_db()
    now = datetime.utcnow()

    doc = {
        "title": "iMOs Platform — Complete Operations Manual",
        "summary": "Full scope of the iMOs platform: every feature, how it works, what not to touch, technical architecture, and operational guidance. Share this with anyone who needs to understand the system.",
        "category": "operations",
        "icon": "book",
        "sort_order": 0,
        "version": "2.0",
        "last_reviewed": now.isoformat(),
        "is_published": True,
        "slug": "imos-operations-manual",
        "slides": [
            {
                "order": 1,
                "title": "Executive Summary",
                "description": "**i'M On Social (iMOs)** is an AI-powered Relationship Management System (RMS) built specifically for automotive dealership sales teams.\n\n**What it does:** Gives every salesperson a personal CRM, digital business card, AI assistant, and full communication suite — SMS, email, calls — all tracked in one place.\n\n**Why it exists:** Dealership salespeople lose customers because they don't follow up. iMOs makes follow-up automatic, trackable, and measurable. Every text, email, call, card share, and review request is logged as a \"touchpoint\" — powering analytics, leaderboards, and manager oversight.\n\n**Core value proposition:**\n- Salespeople get tools that make them look professional and stay organized\n- Managers get visibility into team activity without micromanaging\n- Dealerships get data on which salespeople are actually working their leads\n\n**Tech stack:**\n- Frontend: React Native (Expo) — runs as web app and mobile app\n- Backend: FastAPI (Python)\n- Database: MongoDB Atlas\n- Email delivery: Resend\n- SMS: Twilio (currently in development mode)\n- AI: OpenAI (Jessi assistant)\n- Hosting: Emergent platform\n- File storage: Emergent object storage",
                "tip": "This document is the single source of truth for how iMOs works. Forward it to anyone who needs to understand the system — developers, managers, or partners."
            },
            {
                "order": 2,
                "title": "User Roles & Permissions",
                "description": "iMOs has a hierarchical role system that controls what each user can see and do:\n\n**Super Admin** (you — Forest)\n- Full access to everything\n- Can manage all organizations, users, and settings\n- Access to Company Docs, white-label settings, billing\n- Can view all leaderboards and reports across all orgs\n\n**White-Label Partner**\n- Manages multiple dealerships under their brand\n- Can see aggregate data across their partner network\n- White-label branding on all emails and cards\n\n**Org Admin**\n- Manages one dealership/organization\n- Can add/remove users, manage settings\n- Sees team-wide leaderboard and reports\n- Can reassign contacts when users leave\n\n**Store Manager**\n- Manages a specific store/location\n- Sees their team's activity and leaderboard\n- Can approve content and manage team tasks\n\n**User (Salesperson)**\n- The primary user of the app\n- Has their own contacts, inbox, digital card\n- Can see their own stats and ranking on leaderboard\n- Cannot see other users' conversations\n\n**Independent User**\n- Not part of any organization\n- Full access to their own data only\n- No team features, no leaderboard visibility\n- Ideal for solo real estate agents, freelancers, etc.",
            },
            {
                "order": 3,
                "title": "The Inbox — SMS & Email Messaging",
                "description": "The Inbox is the heart of iMOs. Every customer conversation lives here.\n\n**SMS Mode (Default)**\nWhen a user opens a conversation, they're in SMS mode. The message they type will be sent as a text message.\n\n- **If the user has a Twilio number:** Message sends automatically via Twilio and is logged in the conversation thread.\n- **If the user does NOT have a Twilio number (most users right now):** The app uses \"Personal SMS\" mode — it pre-fills the message, opens the user's native phone messaging app (iMessage/Android Messages), and the user taps Send from there. The message is STILL logged in iMOs before the native app opens.\n\n**Email Mode**\nUsers can switch to email by tapping \"Switch to Email\" in the thread. Emails are sent via Resend with branded HTML templates showing the store's logo, colors, and custom footer.\n\n**Quick Action Toolbar (bottom of thread):**\n- Camera icon — Attach photo/MMS\n- Document icon — Send template message\n- Star icon — Send review request link\n- Card icon — Share digital business card\n- AI icon — Get AI-suggested response from Jessi\n\nAll quick actions pre-fill the message in the composer. The user must tap Send to actually deliver it. This is by design — on mobile, the Send tap is the \"user gesture\" that the browser requires to open the native SMS app.",
                "warning": "CRITICAL: Quick actions must NEVER auto-send. They pre-fill the composer. The user's Send tap is required to trigger the native SMS app on mobile browsers. Breaking this pattern = messages silently fail to open the SMS app."
            },
            {
                "order": 4,
                "title": "Personal SMS — How It Actually Works",
                "description": "This is the most critical flow in the app right now. Since most users don't have a provisioned Twilio number, the \"Personal SMS\" fallback is what makes messaging work.\n\n**Step-by-step flow:**\n1. User types a message in the thread and taps Send\n2. App detects user has no Twilio number → enters \"Personal SMS\" mode\n3. App fires a `fetch()` call to the backend with `keepalive: true` to log the message\n4. `keepalive: true` is ESSENTIAL — it ensures the API call completes even when the browser navigates away\n5. App creates an invisible `<a>` tag with `sms:{phone}&body={message}` (iOS) or `sms:{phone}?body={message}` (Android)\n6. App programmatically clicks the `<a>` tag\n7. User's native SMS app opens with the message pre-filled\n8. User taps Send in their native app\n9. Meanwhile, the backend has already logged the message, created a conversation thread, and recorded the touchpoint\n\n**Why `keepalive` matters:**\nOpening `sms:` literally navigates the browser away from the page. Any normal `await` call gets killed mid-flight. `keepalive: true` tells the browser: \"finish this network request even if the page is unloading.\" Without it, messages appear sent in the UI but are never actually logged.\n\n**Why the anchor `<a>` click technique:**\nMobile Safari blocks `window.location.href` and `window.open()` for `sms:` and `tel:` protocols. The only reliable method is creating an actual `<a>` element and clicking it. This has been tested across iOS Safari, Chrome, and Android browsers.",
                "warning": "DO NOT MODIFY the keepalive pattern or the anchor-click technique. These were implemented after messages were silently lost in production. See CHANGE_RULES.md for full incident details."
            },
            {
                "order": 5,
                "title": "Email Sending — The Full Path",
                "description": "**How email mode works in the inbox:**\n1. When a thread opens, contact email is loaded from URL params AND from the backend API (double-check)\n2. User taps \"Switch to Email\" → app verifies the contact has an email address\n3. User types message → taps Send\n4. Frontend calls `POST /api/messages/send/{user_id}` with `channel: 'email'`\n5. Backend receives the request and routes based on channel:\n   - `email` → Resend (branded HTML email)\n   - `sms` → Twilio (or mock)\n   - `sms_personal` → Log only (user sends from their phone)\n6. Backend builds a branded HTML email with store logo, colors, sender name, and footer\n7. Email delivered via Resend from `noreply@imosapp.com`\n8. Backend logs a `contact_event` and updates the conversation\n\n**Important: Both email fields are checked**\nContacts can have `email` (personal) and `email_work` (work email). The backend always checks both:\n`contact_email = contact.get('email') or contact.get('email_work')`\n\n**Email branding hierarchy:**\n1. White-label partner branding (highest priority)\n2. Organization branding\n3. Store branding\n4. Default iMOs branding\n\nBranded elements: Logo, primary color, accent color, footer text, social links, \"Powered By\" attribution.",
                "tip": "The RESEND_API_KEY must be set as an environment variable in production. Without it, all emails will silently fail. Check the Resend dashboard for delivery status."
            },
            {
                "order": 6,
                "title": "Phone Calls — Dialer & Logging",
                "description": "The app includes a built-in dialer (Keypad tab) and call buttons on contact profiles.\n\n**How calls work:**\n1. User enters a number or taps Call on a contact\n2. App fires a `fetch()` with `keepalive: true` to log the call attempt\n3. App creates an `<a>` tag with `tel:{phone}` and clicks it\n4. Native phone dialer opens\n5. Call is logged as a `contact_event` with type `call_made`\n\nThis follows the exact same `keepalive` + anchor-click pattern as Personal SMS. Same rules apply — do not modify this pattern.\n\n**Dialer features:**\n- T9-style keypad with haptic feedback\n- Contact search from the dialer\n- Recent calls history\n- Quick-dial from contact profiles\n\n**What gets logged:**\n- Caller (user ID)\n- Contact called (contact ID)\n- Phone number dialed\n- Timestamp\n- Duration is NOT tracked (we can't monitor the native phone call)",
            },
            {
                "order": 7,
                "title": "Activity Tracking — Touchpoints",
                "description": "**EVERYTHING is a touchpoint.** This is the foundation of all analytics, leaderboards, and reporting.\n\n**What gets tracked (as `contact_events`):**\n- `personal_sms` — Text sent from personal phone via inbox\n- `email_sent` — Email sent via Resend\n- `call_made` — Phone call initiated\n- `digital_card_sent` — Digital business card shared\n- `review_request_sent` — Review link shared\n- `congrats_card_sent` — Congratulations card shared\n- `vcard_sent` — Contact card (vCard) shared\n- `sms_sent` — Text sent via Twilio (when active)\n\n**What gets tracked (as `messages`):**\n- All inbox messages (SMS and email) with full content, channel, and status\n\n**What gets tracked (as `short_urls`):**\n- Every shared link (card, review, landing page) gets a unique short URL\n- Click counts tracked per short URL\n- Used to calculate Click-Through Rate (CTR)\n\n**Where this data flows:**\n- Contact Activity Feed (on each contact's profile)\n- My Activity Dashboard (My Account page)\n- Admin Reports (aggregated per user, per org)\n- Leaderboards (rankings based on touchpoint totals)\n- Scheduled email reports (daily/weekly/monthly digests)",
                "tip": "If you add a new feature that involves user action toward a customer, it MUST create a contact_event. If it doesn't get tracked, it doesn't count on leaderboards or reports."
            },
            {
                "order": 8,
                "title": "My Activity Dashboard",
                "description": "Located on the **My Account** page, the \"My Activity\" dashboard gives each user a personal view of their performance.\n\n**Features:**\n- Period selector: Today, This Week, This Month, This Year, All Time\n- Summary cards: Total Texts, Emails, Calls, Shares\n- Category breakdown:\n  - Digital Cards sent (with CTR%)\n  - Review Links sent (with CTR%)\n  - Congrats Cards sent (with CTR%)\n  - vCards sent\n  - Each category shows SMS vs Email channel breakdown\n\n**Click-Through Rate (CTR):**\nFor each shareable link type, we calculate:\n`CTR = (total clicks / total sends) * 100`\n\nThis tells the salesperson: \"Of the 50 digital cards you sent, 35 people actually clicked the link (70% CTR).\"\n\n**Backend endpoint:** `GET /api/reports/user-activity/{user_id}?period=month`\n\nThis endpoint aggregates data from:\n- `messages` collection (for SMS/email counts)\n- `contact_events` collection (for shares, calls)\n- `short_urls` collection (for click counts / CTR)",
            },
            {
                "order": 9,
                "title": "Admin Reports & Scheduled Delivery",
                "description": "Managers and admins can access comprehensive activity reports.\n\n**Activity Reports Page** (`/admin/reports/activity`):\n- Aggregated metrics for all users in the organization\n- Date range picker with presets (Today, Week, Month, Custom)\n- Per-user breakdown with sortable columns\n- Metrics tracked: SMS sent, emails sent, calls made, cards shared, reviews sent, congrats sent, total touchpoints\n- Team toggle: View your team vs. entire org\n\n**Scheduled Email Reports:**\n- Admins can configure automatic report delivery\n- Frequency: Daily, Weekly, Monthly\n- Report sent as a branded HTML email to the admin's email\n- Endpoint: `POST /api/reports/send-email-report`\n- Preferences stored per-user: `GET/PUT /api/reports/preferences/{user_id}`\n\n**Backend architecture:**\nReports use MongoDB aggregation pipelines to efficiently summarize millions of events. The `apscheduler` library runs scheduled jobs (daily at 6 AM UTC) to:\n1. Execute lifecycle scans (tag users by tenure)\n2. Send scheduled reports to admins who opted in",
            },
            {
                "order": 10,
                "title": "Digital Business Cards",
                "description": "Every user gets a digital business card — a shareable web page with their professional info.\n\n**What's on the card:**\n- User's name, title, photo\n- Phone number, email\n- Store/dealership info\n- Social media links\n- Customer reviews\n- \"Save Contact\" button (downloads vCard)\n- QR code for in-person sharing\n\n**How sharing works:**\n1. User taps \"Share Digital Card\" (from More page, contact detail, or inbox action)\n2. App generates a tracked short URL for the card\n3. URL is pre-filled in the inbox composer\n4. User sends via SMS or email\n5. When the customer opens the link, the click is tracked\n6. The share is logged as a `digital_card_sent` contact_event\n\n**Customization:**\n- Brand Kit settings control colors and logo\n- AI Persona settings control the bio/description\n- Store profile controls address and social links",
            },
            {
                "order": 11,
                "title": "Review Request System",
                "description": "iMOs makes it easy for salespeople to collect customer reviews.\n\n**How it works:**\n1. Each user has a unique review link page\n2. The review page shows a star rating form and text box\n3. Submitted reviews are stored in the database\n4. Approved reviews appear on the user's digital card\n\n**Sending review requests:**\n1. User taps the Star icon in the inbox, or \"Share Review\" from More page\n2. A tracked review link is pre-filled in the composer\n3. User sends to customer via SMS or email\n4. Customer clicks link → writes a review → submits\n5. Review appears in the admin Review Management area\n\n**Tracking:**\n- `review_request_sent` logged as contact_event\n- Click tracking via `review_link_clicks` collection\n- CTR calculated and shown in My Activity dashboard\n\n**Review Link Clicks collection** tracks each click with:\n- Timestamp, referrer, user agent\n- Used for accurate CTR calculation separate from short_urls",
            },
            {
                "order": 12,
                "title": "Congrats Cards",
                "description": "When a customer makes a purchase (e.g., buys a car), the salesperson can send a branded congratulations card.\n\n**How it works:**\n1. User navigates to \"Create Congrats\" or taps the congrats action in a thread\n2. User customizes the card (customer name, vehicle, message)\n3. Card is generated as a shareable web page\n4. A tracked short URL is created\n5. URL is pre-filled in the inbox composer\n6. Sent via SMS or email to the customer\n\n**What the customer sees:**\nA beautifully branded card with:\n- Dealership logo and branding\n- Customer's name\n- Vehicle/purchase details\n- Salesperson's message\n- Salesperson's contact info and digital card link\n\n**Tracking:**\n- `congrats_card_sent` logged as contact_event\n- Click tracking on the card URL\n- CTR shown in My Activity dashboard",
            },
            {
                "order": 13,
                "title": "Contact Management",
                "description": "**Adding contacts:**\n- Manual entry (+ button on Contacts tab)\n- Import from phone contacts\n- CSV upload (bulk import)\n- Auto-created from inbound messages\n- API integration (Zapier, CRM sync)\n\n**Contact ownership model:**\n- **Organization contacts:** Belong to the dealership. Stay when a user leaves.\n- **Personal contacts:** Manually added by a user. Hidden when user is deactivated.\n- `ownership_type` field: `org` or `personal`\n- `original_user_id` preserved for audit trail\n\n**Tags:**\nTags are the primary way to organize contacts:\n- Custom tags (e.g., \"hot lead\", \"service customer\", \"referral\")\n- System tags added automatically by lifecycle engine (e.g., \"30_day_customer\", \"90_day_customer\")\n- The `sold` tag is special — triggers AI follow-up suggestions (planned feature)\n\n**Contact lifecycle:**\n- When a user is deactivated (leaves the company): soft delete\n- Personal contacts hidden from org, org contacts stay\n- 6-month grace period before data purge\n- Admin can reassign contacts before deactivation\n- Reactivation endpoint restores everything",
                "tip": "Always reassign important contacts before deactivating a user. Once the 6-month grace period expires, personal contacts are permanently purged."
            },
            {
                "order": 14,
                "title": "Leaderboard & Gamification",
                "description": "The leaderboard ranks users based on their touchpoint activity.\n\n**How rankings work:**\nRankings are calculated from total touchpoints (contact_events + messages) within a time period. Each event type counts equally.\n\n**Visibility rules (role-based):**\n- **User:** Sees their own rank + ranks of others in their org (anonymized or named, based on admin setting)\n- **Store Manager:** Sees full leaderboard for their store\n- **Org Admin:** Sees full leaderboard for entire organization\n- **Super Admin:** Sees leaderboard across all organizations\n- **Independent:** No leaderboard (no org to compare against)\n\n**Where it appears:**\n- \"My Rankings\" tile on the More page\n- \"Leaderboard\" tile on the More page\n- My Activity section on My Account page\n\n**Gamification vision (in development):**\n- Badges for milestones (100 texts sent, 50 reviews collected)\n- Streaks for daily activity\n- Manager-set challenges (\"Most review requests this week wins\")\n- Points system with weighted activities",
            },
            {
                "order": 15,
                "title": "AI Assistant — Jessi",
                "description": "Jessi is the AI assistant built into iMOs, powered by OpenAI.\n\n**Current capabilities:**\n- Suggest response messages in inbox conversations\n- Analyze conversation tone and context\n- Generate follow-up messages based on customer history\n\n**How it works:**\n1. User taps the AI icon in the inbox toolbar\n2. Frontend sends conversation context to the backend\n3. Backend calls OpenAI with the conversation history and user's AI persona settings\n4. AI generates a suggested message\n5. Suggestion appears in the composer — user can edit before sending\n\n**AI Persona:**\nEach user can customize Jessi's communication style:\n- Tone (professional, casual, friendly)\n- Industry context (automotive, real estate, etc.)\n- Custom instructions (\"Always mention our service department\")\n- Settings: More > AI Persona\n\n**Planned AI features:**\n- Auto-suggest follow-up when `sold` tag is applied\n- Sentiment analysis on customer messages\n- Smart scheduling for follow-up tasks\n- Campaign message generation",
            },
            {
                "order": 16,
                "title": "Public API & Webhooks",
                "description": "iMOs provides a public REST API for CRM integration with platforms like Zapier, Salesforce, and HubSpot.\n\n**API Authentication:**\n- API keys generated in Settings > Integrations\n- Pass key via `X-API-Key` header\n- Rate limited: 100 req/min, 10,000 req/day\n\n**Available endpoints:**\n- `GET /api/v1/contacts` — List contacts with search/filter/pagination\n- `POST /api/v1/contacts` — Create contact\n- `PUT /api/v1/contacts/{id}` — Update contact\n- `DELETE /api/v1/contacts/{id}` — Delete contact\n- `POST /api/v1/contacts/bulk/tag` — Bulk tag contacts\n- `GET /api/v1/conversations` — List conversations\n- `POST /api/v1/messages/send` — Send message (SMS or email)\n\n**Outgoing Webhooks (21 event types):**\n- Contact events: created, updated, deleted, tagged\n- Message events: sent, received\n- Campaign events: enrolled, completed\n- Review events: submitted, approved\n- User events: created, deactivated\n\nWebhooks are signed with HMAC-SHA256. Auto-retry on failure (3 attempts with exponential backoff). Delivery logs retained 30 days.\n\n**Setup:** Settings > Integrations > API Keys + Webhook Subscriptions",
            },
            {
                "order": 17,
                "title": "White-Label & Branding",
                "description": "iMOs supports full white-labeling for partners who resell the platform.\n\n**Brand Kit** (Settings > Brand Kit):\n- Store logo (appears on cards, emails, review pages)\n- Primary color and accent color\n- Social media links\n- Custom footer text for emails\n\n**White-label email branding hierarchy:**\nEmails use dynamic templates that pull branding from:\n1. White-label partner settings (if user belongs to a partner org)\n2. Organization settings\n3. Store-specific settings\n4. Default iMOs branding (fallback)\n\n**What gets branded:**\n- All outbound emails (logo, colors, footer, \"Powered By\" text)\n- Digital business cards\n- Review request pages\n- Congrats cards\n- The \"Powered By\" link in email footers\n\n**Email sender:** Always `noreply@imosapp.com` (domain verified with Resend). The \"From\" name shows as the salesperson's name.",
            },
            {
                "order": 18,
                "title": "Technical Architecture — DO NOT TOUCH List",
                "description": "These are production-critical code patterns. Modifying them WILL break the app.\n\n**1. `keepalive: true` on fetch calls**\nFiles: `thread/[id].tsx` (handleSend), `dialer.tsx` (handleCall)\nWhy: Ensures API logging completes when browser navigates to native SMS/Phone app.\nBreaking it: Messages sent from inbox will silently not be logged. Activity feeds, reports, and leaderboards will show wrong data.\n\n**2. Anchor `<a>` click for sms: and tel: links**\nFiles: `thread/[id].tsx`, `dialer.tsx`, `contact/[id].tsx`\nWhy: Mobile Safari blocks `window.location.href` and `window.open()` for protocol links.\nBreaking it: Tapping Send will do nothing. No SMS app opens. User thinks app is broken.\n\n**3. Viewport meta tag**\nFile: `+html.tsx`\nValue: `maximum-scale=1, user-scalable=no`\nBreaking it: iOS Safari will auto-zoom when focusing inputs, and the page permanently stays zoomed. Users have to pinch-zoom on every page.\n\n**4. Input font-size: 16px**\nFile: `+html.tsx` (global CSS)\nBreaking it: iOS auto-zooms on inputs below 16px.\n\n**5. `load_dotenv(override=False)` in server.py**\nBreaking it: Production will use the local .env file instead of the production environment variables. Database connects to localhost instead of Atlas. 3-day outage.\n\n**6. Both email fields checked**\nBackend: `contact.get('email') or contact.get('email_work')`\nBreaking it: Emails won't send for contacts who only have a work email.",
                "warning": "Every item on this list caused a REAL production incident. Do not modify any of these patterns without reading CHANGE_RULES.md and understanding the full impact."
            },
            {
                "order": 19,
                "title": "Third-Party Integrations",
                "description": "**Resend (Email)** — LIVE\n- Sends all transactional emails (inbox emails, reports, notifications)\n- Domain verified: imosapp.com\n- Sender: noreply@imosapp.com\n- Env variable: `RESEND_API_KEY`\n- Dashboard: resend.com (check delivery status here)\n\n**Twilio (SMS)** — DEVELOPMENT MODE\n- Currently in mock mode — messages are logged but not delivered via Twilio\n- The \"Personal SMS\" fallback handles actual message delivery\n- When ready for production: provision numbers, set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER\n\n**OpenAI (AI)** — LIVE\n- Powers Jessi AI assistant\n- Used for message suggestions and conversation analysis\n- Env variable: Uses Emergent LLM key\n\n**MongoDB Atlas (Database)** — LIVE\n- Production database hosted on Atlas\n- Preview uses localhost:27017\n- Env variable: `MONGO_URL`, `DB_NAME`\n- NEVER hardcode the connection string\n\n**Emergent Platform (Hosting & Storage)**\n- App hosted on Emergent\n- Object storage for images and file uploads\n- Deployment via Emergent platform (not manual)\n\n**Pillow (Python)** — Used for image manipulation (thumbnails, etc.)",
            },
            {
                "order": 20,
                "title": "Environment & Deployment",
                "description": "**Preview vs. Production:**\n- Preview: development environment on Emergent (separate database, separate URL)\n- Production: deployed to `app.imosapp.com` via Emergent platform\n- Changes in preview do NOT auto-deploy to production\n- To deploy: use the Deploy button in Emergent\n\n**Critical environment variables (backend/.env):**\n- `MONGO_URL` — Database connection string\n- `DB_NAME` — Database name\n- `RESEND_API_KEY` — Email delivery key\n- `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_PHONE_NUMBER` — SMS (when live)\n- `APP_URL` — Production URL (https://app.imosapp.com)\n\n**Critical environment variables (frontend/.env):**\n- `REACT_APP_BACKEND_URL` — Points frontend to backend API\n\n**Deployment checklist:**\n1. Verify all env variables are set in Emergent production settings\n2. Ensure MONGO_URL points to Atlas (NOT localhost)\n3. Confirm RESEND_API_KEY is correct and domain is verified\n4. Deploy via Emergent platform\n5. Test email sending from inbox after deployment\n6. Test SMS flow (personal fallback) from a mobile device\n7. Verify activity feed logs all events",
                "tip": "After every deployment, test the full user journey: login > open contact > send SMS > switch to email > send email > check activity feed. If any step fails, roll back immediately."
            },
            {
                "order": 21,
                "title": "Database Collections Reference",
                "description": "**users** — All user accounts\nKey fields: email, first_name, last_name, role, org_id, store_id, phone, twilio_number, status (active/deactivated)\n\n**contacts** — Customer contacts\nKey fields: first_name, last_name, phone, email, email_work, tags[], user_id, org_id, ownership_type, status, photo, photo_thumbnail\n\n**conversations** — Inbox conversation threads\nKey fields: user_id, contact_id, contact_phone, last_message_at\n\n**messages** — Individual messages in conversations\nKey fields: conversation_id, content, sender (user/contact), channel (sms/email/sms_personal), status, created_at\n\n**contact_events** — Activity tracking (touchpoints)\nKey fields: event_type, channel, content, contact_id, user_id, org_id, created_at\n\n**short_urls** — Tracked links for shares\nKey fields: original_url, short_code, link_type, user_id, contact_id, click_count\n\n**review_link_clicks** — Click tracking for review links\nKey fields: user_id, clicked_at, referrer, user_agent\n\n**company_docs** — This document system\nKey fields: title, summary, category, slides[], is_published, version\n\n**organizations** — Dealerships/companies\nKey fields: name, logo, primary_color, address, social_links",
            },
            {
                "order": 22,
                "title": "Known Limitations & Current Status",
                "description": "**What's LIVE and working:**\n- User authentication and role-based access\n- Full inbox messaging (Personal SMS + Email via Resend)\n- Digital business cards (create, share, track)\n- Review request system (send, collect, display)\n- Congrats cards (create, share, track)\n- Contact management (CRUD, tags, import, ownership)\n- Activity tracking and My Activity dashboard\n- Admin reports with scheduled email delivery\n- AI assistant (Jessi) for message suggestions\n- Public API with 21 webhook event types\n- White-label email branding\n- Company Docs system (what you're reading now)\n\n**What's in MOCK/DEVELOPMENT mode:**\n- Twilio SMS — Messages are logged but not delivered via Twilio. Personal SMS fallback handles actual delivery.\n\n**Known bugs:**\n- Contact photos sometimes revert to old image after update (thumbnail regeneration issue)\n- React Hydration Error #418 (cosmetic, doesn't affect functionality)\n\n**What's coming next (roadmap):**\n- Full gamification with leaderboards, badges, and streaks\n- AI-powered follow-up suggestions when contacts are tagged \"sold\"\n- Push notifications for new leads\n- Full Twilio integration for automated SMS campaigns\n- WhatsApp integration\n- TestFlight build for native iOS app\n- Inventory management module\n- Training Hub with video content",
                "tip": "For the most up-to-date status, check with the development team or review the latest deployment notes in the Emergent platform."
            },
            {
                "order": 23,
                "title": "Quick Reference — Key URLs & Contacts",
                "description": "**App URLs:**\n- Production: https://app.imosapp.com\n- Company website: https://imosapp.com\n\n**Service Dashboards:**\n- Resend (email monitoring): https://resend.com/emails\n- MongoDB Atlas (database): https://cloud.mongodb.com\n- Emergent (hosting/deployment): https://emergentagent.com\n\n**Key Email Addresses:**\n- App sender: noreply@imosapp.com\n- Support: support@imosapp.com\n- Security: security@imosapp.com\n- Privacy: privacy@imosapp.com\n\n**Business Address:**\n1741 Lunford Ln, Riverton, UT\n\n**Super Admin Login:**\nEmail: forest@imosapp.com\n(Password managed securely — not documented here)\n\n**API Documentation:**\nSettings > Integrations > API Docs tab\n\n**This Document:**\nCompany Docs > Operations Manual > iMOs Platform — Complete Operations Manual\n\nLast updated: February 2026\nVersion: 2.0",
            },
        ],
        "created_at": now,
        "updated_at": now,
    }

    # Upsert by slug
    existing = await db.company_docs.find_one({"slug": "imos-operations-manual"})
    if existing:
        await db.company_docs.update_one(
            {"slug": "imos-operations-manual"},
            {"$set": doc}
        )
        return {"message": "Operations Manual updated", "id": str(existing["_id"])}
    else:
        result = await db.company_docs.insert_one(doc)
        return {"message": "Operations Manual created", "id": str(result.inserted_id)}


@router.post("/seed-nda")
async def seed_nda(x_user_id: str = Header(None, alias="X-User-ID")):
    """Create or update the NDA — super_admin only"""
    user = await verify_admin_access(x_user_id)
    if user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin only")

    db = get_db()
    now = datetime.utcnow()

    doc = {
        "title": "Non-Disclosure Agreement (NDA)",
        "summary": "Confidentiality agreement for employees, contractors, and partners with access to proprietary iMOs information.",
        "category": "legal",
        "icon": "lock-closed",
        "sort_order": 0,
        "version": "1.0",
        "last_reviewed": now.isoformat(),
        "is_published": True,
        "required_role": "super_admin",
        "slug": "imos-nda",
        "slides": [
            {
                "order": 1,
                "title": "Non-Disclosure Agreement",
                "description": "**NON-DISCLOSURE AND CONFIDENTIALITY AGREEMENT**\n\nThis Non-Disclosure Agreement (\"Agreement\") is entered into as of the date of the receiving party's signature, by and between:\n\n**Disclosing Party:**\ni'M On Social LLC (\"iMOs\")\n1741 Lunford Ln\nRiverton, UT 84065\nContact: forest@imosapp.com\n\n**Receiving Party:**\nThe individual or entity identified on the signature page of this Agreement.\n\nThis Agreement governs the disclosure of confidential and proprietary information by iMOs to the Receiving Party in connection with employment, contracting, partnership, or evaluation of the iMOs platform and business operations.",
            },
            {
                "order": 2,
                "title": "1. Definition of Confidential Information",
                "description": "\"Confidential Information\" means any and all non-public, proprietary, or trade secret information disclosed by iMOs to the Receiving Party, whether orally, in writing, electronically, or by any other means, including but not limited to:\n\n**a) Technical Information:**\n- Source code, algorithms, and software architecture\n- API specifications, database schemas, and system configurations\n- Security protocols, encryption methods, and authentication systems\n- Development roadmaps, feature plans, and technical documentation\n- Server infrastructure, hosting configurations, and deployment processes\n\n**b) Business Information:**\n- Customer lists, contact databases, and CRM data\n- Pricing models, revenue figures, and financial projections\n- Marketing strategies, sales processes, and go-to-market plans\n- Partnership agreements and vendor relationships\n- Organizational structure and staffing plans\n\n**c) Product Information:**\n- UI/UX designs, wireframes, and mockups\n- AI models, training data, and machine learning configurations\n- Integration specifications and third-party service configurations\n- Beta features, unreleased functionality, and prototype designs\n\n**d) Operational Information:**\n- Internal processes, SOPs, and workflow documentation\n- Employee compensation, benefits, and personnel records\n- Legal strategies, pending litigation, and regulatory compliance plans\n- Investor communications and fundraising materials",
                "warning": "This definition is intentionally broad. When in doubt, treat information as confidential."
            },
            {
                "order": 3,
                "title": "2. Obligations of the Receiving Party",
                "description": "The Receiving Party agrees to:\n\n**a) Maintain Confidentiality:**\n- Hold all Confidential Information in strict confidence\n- Use at least the same degree of care to protect Confidential Information as it uses to protect its own confidential information, but in no event less than reasonable care\n- Not disclose Confidential Information to any third party without prior written consent from iMOs\n\n**b) Limit Use:**\n- Use Confidential Information solely for the purpose for which it was disclosed (the \"Purpose\")\n- Not use Confidential Information for personal gain, competitive advantage, or any purpose other than the Purpose\n- Not reverse engineer, decompile, or disassemble any software or technology disclosed under this Agreement\n\n**c) Limit Access:**\n- Restrict access to Confidential Information to those employees, agents, or contractors who have a need to know and who are bound by confidentiality obligations at least as restrictive as those in this Agreement\n- Maintain a record of all individuals who have been granted access to Confidential Information\n- Immediately notify iMOs if the Receiving Party becomes aware of any unauthorized disclosure or use\n\n**d) Return or Destroy:**\n- Upon termination of this Agreement or upon request by iMOs, promptly return or destroy all Confidential Information and any copies, summaries, or extracts thereof\n- Provide written certification of destruction upon request",
            },
            {
                "order": 4,
                "title": "3. Exclusions from Confidential Information",
                "description": "Confidential Information does NOT include information that:\n\n**a)** Is or becomes publicly available through no fault of the Receiving Party;\n\n**b)** Was rightfully in the Receiving Party's possession prior to disclosure by iMOs, as evidenced by written records;\n\n**c)** Is independently developed by the Receiving Party without use of or reference to the Confidential Information, as evidenced by written records;\n\n**d)** Is rightfully received from a third party without restriction on disclosure and without breach of this Agreement;\n\n**e)** Is approved for release by prior written authorization from iMOs;\n\n**f)** Is required to be disclosed by law, regulation, or court order, provided that the Receiving Party:\n- Gives iMOs prompt written notice of the required disclosure (to the extent legally permitted)\n- Cooperates with iMOs in seeking a protective order or other appropriate remedy\n- Discloses only the minimum amount of Confidential Information required by law",
                "tip": "If you're ever asked to disclose information by a legal authority, contact iMOs immediately before responding."
            },
            {
                "order": 5,
                "title": "4. Intellectual Property Rights",
                "description": "**a) Ownership:**\nAll Confidential Information remains the sole and exclusive property of iMOs. This Agreement does not grant the Receiving Party any license, right, title, or interest in or to any Confidential Information, intellectual property, trademarks, copyrights, or patents owned by iMOs.\n\n**b) No License:**\nNothing in this Agreement shall be construed as granting any rights to the Receiving Party under any patent, copyright, trademark, or other intellectual property right of iMOs, nor shall this Agreement grant the Receiving Party any rights in or to the Confidential Information except as expressly set forth herein.\n\n**c) Work Product:**\nAny work product, inventions, discoveries, or improvements made by the Receiving Party using or derived from Confidential Information shall be the sole property of iMOs. The Receiving Party hereby assigns all right, title, and interest in such work product to iMOs.\n\n**d) Moral Rights:**\nTo the extent permitted by applicable law, the Receiving Party waives all moral rights in any work product created under this Agreement.",
            },
            {
                "order": 6,
                "title": "5. Non-Solicitation & Non-Compete",
                "description": "**a) Non-Solicitation of Employees:**\nDuring the term of this Agreement and for a period of twelve (12) months following its termination, the Receiving Party shall not, directly or indirectly:\n- Solicit, recruit, or hire any employee or contractor of iMOs\n- Encourage any employee or contractor of iMOs to terminate their relationship with iMOs\n\n**b) Non-Solicitation of Customers:**\nDuring the term of this Agreement and for a period of twelve (12) months following its termination, the Receiving Party shall not, directly or indirectly:\n- Solicit or contact any customer or prospective customer of iMOs for the purpose of offering competing products or services\n- Divert or attempt to divert any business from iMOs\n\n**c) Non-Compete:**\nDuring the term of this Agreement and for a period of twelve (12) months following its termination, the Receiving Party shall not, directly or indirectly, develop, market, sell, or distribute any product or service that is substantially similar to or competitive with the iMOs platform, including but not limited to:\n- CRM systems targeted at automotive dealerships\n- Digital business card platforms with integrated messaging\n- AI-powered sales follow-up systems for dealership use",
                "warning": "Violation of non-solicitation or non-compete clauses may result in immediate legal action, including injunctive relief and monetary damages."
            },
            {
                "order": 7,
                "title": "6. Specific Protections for Platform Data",
                "description": "The Receiving Party specifically acknowledges and agrees that the following constitute trade secrets of iMOs and are subject to the highest level of protection under this Agreement:\n\n**a) Customer Database Architecture:**\n- The structure, schema, and relationships of the iMOs contact management system\n- The activity tracking and touchpoint logging methodology\n- The leaderboard ranking algorithms and gamification mechanics\n\n**b) AI and Machine Learning:**\n- AI persona configurations and prompt engineering techniques\n- Conversation analysis algorithms and sentiment models\n- The Jessi AI assistant's training data and behavior patterns\n\n**c) Communication Infrastructure:**\n- The carrier-agnostic messaging architecture (Personal SMS fallback system)\n- The keepalive pattern for reliable cross-app communication logging\n- Email template engine and white-label branding system\n- Short URL tracking and click-through rate calculation methods\n\n**d) Business Metrics:**\n- User engagement data and retention metrics\n- Revenue per user, churn rates, and lifetime value calculations\n- Conversion rates for digital cards, review requests, and campaigns\n- Internal benchmarking data across dealerships",
            },
            {
                "order": 8,
                "title": "7. Term and Termination",
                "description": "**a) Term:**\nThis Agreement shall be effective as of the date of the Receiving Party's signature and shall remain in effect for a period of three (3) years from the date of last disclosure of Confidential Information.\n\n**b) Survival:**\nThe obligations of confidentiality and non-disclosure under this Agreement shall survive termination and continue for a period of five (5) years from the date of termination, or for as long as the Confidential Information remains a trade secret under applicable law, whichever is longer.\n\n**c) Termination:**\nEither party may terminate this Agreement at any time by providing thirty (30) days' written notice to the other party. Termination shall not relieve the Receiving Party of its obligations under this Agreement with respect to Confidential Information disclosed prior to termination.\n\n**d) Effect of Termination:**\nUpon termination, the Receiving Party shall:\n- Immediately cease all use of Confidential Information\n- Return or destroy all Confidential Information within fourteen (14) days\n- Provide written certification of compliance within twenty-one (21) days",
            },
            {
                "order": 9,
                "title": "8. Remedies",
                "description": "**a) Injunctive Relief:**\nThe Receiving Party acknowledges that any breach or threatened breach of this Agreement may cause irreparable harm to iMOs for which monetary damages would be inadequate. Accordingly, iMOs shall be entitled to seek injunctive relief (including temporary restraining orders, preliminary injunctions, and permanent injunctions) in any court of competent jurisdiction, without the necessity of proving actual damages or posting any bond.\n\n**b) Monetary Damages:**\nIn addition to injunctive relief, iMOs shall be entitled to recover all actual damages resulting from any breach of this Agreement, including but not limited to:\n- Lost profits and business opportunities\n- Costs of investigation and remediation\n- Reasonable attorneys' fees and court costs\n\n**c) Indemnification:**\nThe Receiving Party shall indemnify, defend, and hold harmless iMOs and its officers, directors, employees, and agents from and against any and all claims, damages, losses, costs, and expenses (including reasonable attorneys' fees) arising out of or related to any breach of this Agreement by the Receiving Party.\n\n**d) Cumulative Remedies:**\nThe remedies provided in this Agreement are cumulative and not exclusive of any other remedies available at law or in equity.",
            },
            {
                "order": 10,
                "title": "9. General Provisions",
                "description": "**a) Governing Law:**\nThis Agreement shall be governed by and construed in accordance with the laws of the State of Utah, without regard to its conflict of laws provisions.\n\n**b) Dispute Resolution:**\nAny dispute arising out of or relating to this Agreement shall be resolved through binding arbitration in Salt Lake County, Utah, in accordance with the rules of the American Arbitration Association.\n\n**c) Entire Agreement:**\nThis Agreement constitutes the entire agreement between the parties with respect to the subject matter hereof and supersedes all prior or contemporaneous oral or written agreements concerning such subject matter.\n\n**d) Amendment:**\nThis Agreement may not be amended or modified except by a written instrument signed by both parties.\n\n**e) Severability:**\nIf any provision of this Agreement is held to be invalid or unenforceable, the remaining provisions shall continue in full force and effect.\n\n**f) Assignment:**\nThe Receiving Party may not assign this Agreement without the prior written consent of iMOs.\n\n**g) Waiver:**\nNo waiver of any breach of this Agreement shall constitute a waiver of any subsequent breach. No waiver shall be effective unless in writing and signed by the waiving party.\n\n**h) Notices:**\nAll notices under this Agreement shall be in writing and delivered to the addresses set forth on the first page of this Agreement, or to such other address as either party may designate in writing.",
            },
            {
                "order": 11,
                "title": "Signature & Acknowledgment",
                "description": "**IN WITNESS WHEREOF**, the parties have executed this Non-Disclosure Agreement as of the date set forth below.\n\n**DISCLOSING PARTY:**\ni'M On Social LLC\n\nBy: ________________________________\nName: Forest Ward\nTitle: Founder & CEO\nDate: ________________________________\n\n\n**RECEIVING PARTY:**\n\nBy: ________________________________\nName: ________________________________\nTitle: ________________________________\nCompany: ________________________________\nDate: ________________________________\nEmail: ________________________________\n\n\nBy signing this Agreement, the Receiving Party acknowledges that they have read, understood, and agree to be bound by all terms and conditions set forth herein.\n\nThis Agreement has been executed in duplicate, with each party retaining one original copy.",
                "tip": "This NDA should be signed before any confidential information is shared. Keep signed copies in a secure location."
            },
        ],
        "created_at": now,
        "updated_at": now,
    }

    # Upsert by slug
    existing = await db.company_docs.find_one({"slug": "imos-nda"})
    if existing:
        await db.company_docs.update_one({"slug": "imos-nda"}, {"$set": doc})
        return {"message": "NDA updated", "id": str(existing["_id"])}
    else:
        result = await db.company_docs.insert_one(doc)
        return {"message": "NDA created", "id": str(result.inserted_id)}


@router.post("/seed")
async def seed_docs(x_user_id: str = Header(None, alias="X-User-ID")):
    """Seed all company documents - super_admin only"""
    user = await verify_admin_access(x_user_id)
    if user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin only")

    db = get_db()
    count = await db.company_docs.count_documents({})
    if count > 0:
        return {"message": f"Docs already seeded ({count} found). Delete to re-seed."}

    now = datetime.utcnow()

    docs = [
        # ====== CYBER SECURITY POLICY ======
        {
            "title": "Cyber Security Policy",
            "summary": "Comprehensive security standards for protecting company and customer data.",
            "category": "security",
            "icon": "shield-checkmark",
            "sort_order": 1,
            "version": "1.0",
            "last_reviewed": now.isoformat(),
            "is_published": True,
            "slides": [
                {
                    "order": 1,
                    "title": "Purpose & Scope",
                    "description": "This Cyber Security Policy establishes the security standards and practices that all i'M On Social (iMOs) employees, contractors, and partners must follow.\n\nThis policy applies to:\n\n- All employees and contractors\n- All company-owned devices and systems\n- All customer data handled by iMOs\n- All third-party integrations and services\n\nViolations of this policy may result in disciplinary action, up to and including termination.",
                    "tip": "Security is everyone's responsibility. If you see something, say something."
                },
                {
                    "order": 2,
                    "title": "Data Classification",
                    "description": "All data handled by iMOs is classified into the following categories:\n\n**Confidential**\n- Customer PII (names, emails, phone numbers)\n- Authentication credentials and API keys\n- Financial and billing information\n- Internal business strategies\n\n**Internal**\n- Employee contact information\n- Internal communications\n- Training materials and SOPs\n- System configurations\n\n**Public**\n- Marketing materials\n- Published review pages\n- Digital business cards (user-approved content only)",
                    "warning": "Never share Confidential data via unsecured channels (personal email, SMS, social media)."
                },
                {
                    "order": 3,
                    "title": "Access Control",
                    "description": "Access to systems and data follows the principle of least privilege:\n\n- Employees receive only the access necessary for their role\n- Admin access requires approval from a super admin\n- All access is logged and auditable\n- Access is revoked immediately upon termination or role change\n\n**Password Requirements:**\n- Minimum 12 characters\n- Mix of uppercase, lowercase, numbers, and symbols\n- No password reuse across systems\n- Passwords must be changed every 90 days\n- Multi-factor authentication (MFA) required for all admin accounts"
                },
                {
                    "order": 4,
                    "title": "Data Encryption",
                    "description": "All sensitive data must be encrypted:\n\n**In Transit:**\n- All API communications use TLS 1.2+ (HTTPS)\n- WebSocket connections are encrypted (WSS)\n- Email communications use TLS\n\n**At Rest:**\n- Database encryption enabled (MongoDB Atlas)\n- Backups are encrypted\n- API keys stored as environment variables, never in code\n\n**Key Management:**\n- API keys rotated quarterly\n- Compromised keys revoked immediately\n- Keys never committed to version control"
                },
                {
                    "order": 5,
                    "title": "Incident Response",
                    "description": "In the event of a security incident:\n\n**Step 1: Identify**\nRecognize and confirm the incident. Common indicators:\n- Unusual account activity\n- Unauthorized data access\n- System performance anomalies\n- Reports from users or third parties\n\n**Step 2: Contain**\n- Isolate affected systems immediately\n- Revoke compromised credentials\n- Preserve evidence (logs, screenshots)\n\n**Step 3: Report**\n- Notify your manager immediately\n- Contact: security@imosapp.com\n- Document timeline of events\n\n**Step 4: Recover**\n- Restore from clean backups\n- Patch vulnerabilities\n- Monitor for recurrence\n\n**Step 5: Review**\n- Post-incident analysis within 48 hours\n- Update policies as needed\n- Communicate lessons learned",
                    "warning": "Report all suspected incidents within 1 hour. Delayed reporting increases risk."
                },
                {
                    "order": 6,
                    "title": "Third-Party & Integration Security",
                    "description": "All third-party services must meet our security standards:\n\n**Approved Services:**\n- MongoDB Atlas (database)\n- Resend (email delivery)\n- Twilio (SMS/voice)\n- OpenAI (AI features)\n- Emergent (hosting & object storage)\n\n**Requirements for new integrations:**\n- SOC 2 compliance or equivalent\n- Data processing agreement (DPA)\n- API key authentication (no shared passwords)\n- Regular security audits\n- Data residency compliance\n\n**Webhook Security:**\n- All outgoing webhooks use HMAC signatures\n- Webhook secrets rotated quarterly\n- Delivery logs retained for 30 days"
                },
                {
                    "order": 7,
                    "title": "Employee Responsibilities",
                    "description": "Every team member must:\n\n- Complete security awareness training annually\n- Report suspicious activity immediately\n- Lock devices when unattended\n- Use company-approved tools only\n- Never share login credentials\n- Keep software and systems updated\n- Use VPN when on public networks\n- Verify identity before sharing sensitive information\n\n**Prohibited Actions:**\n- Storing customer data on personal devices\n- Using personal email for company business\n- Installing unauthorized software on company devices\n- Sharing API keys or credentials via chat/email\n- Bypassing security controls",
                    "tip": "When in doubt, ask before you act. It's always better to verify than to assume."
                },
            ],
            "created_at": now,
        },

        # ====== COMPANY POLICY ======
        {
            "title": "Company Policy & Code of Conduct",
            "summary": "Guidelines for professional conduct, workplace standards, and company expectations.",
            "category": "company_policy",
            "icon": "business",
            "sort_order": 2,
            "version": "1.0",
            "last_reviewed": now.isoformat(),
            "is_published": True,
            "slides": [
                {
                    "order": 1,
                    "title": "Our Mission",
                    "description": "i'M On Social (iMOs) empowers sales professionals with intelligent communication tools that build lasting customer relationships.\n\nOur core values:\n\n- **Innovation** - We push boundaries in sales technology\n- **Integrity** - We handle customer data with the highest ethical standards\n- **Impact** - Every feature we build drives real results for our users\n- **Inclusion** - We build for everyone and welcome diverse perspectives",
                },
                {
                    "order": 2,
                    "title": "Professional Conduct",
                    "description": "All team members are expected to:\n\n- Treat colleagues, customers, and partners with respect\n- Communicate professionally in all channels\n- Be punctual and reliable\n- Take ownership of your work and mistakes\n- Collaborate openly and share knowledge\n- Maintain confidentiality of company and customer information\n\n**Zero Tolerance:**\n- Harassment or discrimination of any kind\n- Retaliation against anyone who reports concerns\n- Misuse of customer data\n- Fraudulent activity",
                    "warning": "Violations of the code of conduct will be investigated and may result in immediate termination."
                },
                {
                    "order": 3,
                    "title": "Communication Standards",
                    "description": "**Internal Communication:**\n- Use designated channels (Slack, team chat)\n- Respond to messages within 4 business hours\n- Use clear, concise language\n- Mark urgent items appropriately\n\n**Customer Communication:**\n- Always professional and courteous\n- Response time: within 2 business hours\n- Use approved templates when available\n- Never promise features or timelines without approval\n- All customer communications are logged and auditable\n\n**External Communication:**\n- Social media posts about iMOs require approval\n- Press inquiries go to management\n- Represent the company positively at all times",
                },
                {
                    "order": 4,
                    "title": "Remote Work & Equipment",
                    "description": "**Remote Work:**\n- Maintain regular working hours and availability\n- Keep your work environment professional for video calls\n- Use secure, private networks for company work\n- VPN required on public Wi-Fi\n\n**Company Equipment:**\n- Keep devices updated and secured\n- Report lost or stolen devices immediately\n- Return all equipment upon departure\n- Personal use should not interfere with work functionality\n\n**Software:**\n- Only install approved applications\n- Keep all software updated\n- Use company accounts for work tools",
                },
                {
                    "order": 5,
                    "title": "Performance & Growth",
                    "description": "We invest in our team's growth:\n\n- Regular 1:1 meetings with your manager\n- Quarterly performance reviews\n- Training budget available for professional development\n- Clear career progression paths\n\n**Expectations:**\n- Meet deadlines and deliverables\n- Proactively communicate blockers\n- Seek feedback and act on it\n- Mentor others when possible\n- Stay current with industry trends",
                    "tip": "Your growth directly impacts our customers' success. Never stop learning."
                },
            ],
            "created_at": now,
        },

        # ====== TERMS OF SERVICE ======
        {
            "title": "Terms of Service",
            "summary": "Legal terms governing the use of the iMOs platform and services.",
            "category": "legal",
            "icon": "document-text",
            "sort_order": 3,
            "version": "1.0",
            "last_reviewed": now.isoformat(),
            "is_published": True,
            "slides": [
                {
                    "order": 1,
                    "title": "Agreement to Terms",
                    "description": "By accessing or using the i'M On Social (\"iMOs\") platform, you agree to be bound by these Terms of Service.\n\n**Effective Date:** February 2026\n**Company:** i'M On Social\n**Contact:** support@imosapp.com\n**Address:** 1741 Lunford Ln, Riverton, UT\n\nIf you do not agree to these terms, you may not use the platform. We reserve the right to modify these terms at any time, with notice provided to active users.",
                },
                {
                    "order": 2,
                    "title": "Account & Eligibility",
                    "description": "**Eligibility:**\n- You must be 18 years or older\n- You must provide accurate, complete registration information\n- You are responsible for maintaining the security of your account\n\n**Account Responsibilities:**\n- Keep your password confidential\n- Notify us immediately of unauthorized access\n- You are responsible for all activity under your account\n- One account per person; no shared accounts\n\n**Account Termination:**\n- We may suspend or terminate accounts that violate these terms\n- You may close your account at any time\n- Upon termination, your data will be handled per our Data Retention Policy",
                },
                {
                    "order": 3,
                    "title": "Acceptable Use",
                    "description": "You agree NOT to use iMOs to:\n\n- Send spam or unsolicited messages\n- Harass, threaten, or intimidate any person\n- Transmit malware, viruses, or harmful code\n- Impersonate another person or entity\n- Violate any applicable laws or regulations (including TCPA, CAN-SPAM, GDPR)\n- Scrape, mine, or collect data from the platform\n- Reverse engineer or decompile any part of the platform\n- Share your account credentials with others\n- Use the platform for illegal activities\n\n**Messaging Compliance:**\n- All SMS/email campaigns must comply with TCPA and CAN-SPAM\n- Recipients must have opted in to receive communications\n- Unsubscribe mechanisms must be honored within 10 business days",
                    "warning": "Violations of acceptable use may result in immediate account termination without refund."
                },
                {
                    "order": 4,
                    "title": "Intellectual Property",
                    "description": "**Our Property:**\n- The iMOs platform, including all code, design, and content, is owned by i'M On Social\n- Our trademarks, logos, and brand elements may not be used without permission\n\n**Your Content:**\n- You retain ownership of content you create (messages, contacts, templates)\n- You grant iMOs a license to process and store your content as needed to provide the service\n- You are responsible for ensuring your content does not violate any third-party rights\n\n**AI-Generated Content:**\n- Content generated by Jessi AI is provided as-is\n- You are responsible for reviewing and approving AI suggestions before sending",
                },
                {
                    "order": 5,
                    "title": "Limitation of Liability",
                    "description": "**Service Availability:**\n- We strive for 99.9% uptime but do not guarantee uninterrupted service\n- Scheduled maintenance will be communicated in advance\n\n**Liability Cap:**\n- Our total liability is limited to the amount paid by you in the 12 months preceding the claim\n- We are not liable for indirect, incidental, or consequential damages\n\n**Indemnification:**\n- You agree to indemnify iMOs against claims arising from your use of the platform\n- This includes claims related to your content, your customers, and your compliance with applicable laws\n\n**Governing Law:**\n- These terms are governed by the laws of the State of Utah\n- Disputes will be resolved through binding arbitration in Salt Lake County, UT",
                },
            ],
            "created_at": now,
        },

        # ====== PRIVACY POLICY ======
        {
            "title": "Privacy Policy",
            "summary": "How we collect, use, store, and protect personal information.",
            "category": "legal",
            "icon": "lock-closed",
            "sort_order": 4,
            "version": "1.0",
            "last_reviewed": now.isoformat(),
            "is_published": True,
            "slides": [
                {
                    "order": 1,
                    "title": "Information We Collect",
                    "description": "**Account Information:**\n- Name, email, phone number\n- Company/dealership details\n- Profile photos and bio\n\n**Usage Data:**\n- Feature usage and interaction patterns\n- Device information and browser type\n- IP address and approximate location\n- Login times and session duration\n\n**Customer Data (stored on your behalf):**\n- Contact names, emails, phone numbers\n- Communication history (messages, emails)\n- Tags, notes, and custom fields\n- Activity events and touchpoints\n\n**Third-Party Data:**\n- Information from connected services (Twilio, Resend)\n- Review submissions from public review pages",
                },
                {
                    "order": 2,
                    "title": "How We Use Information",
                    "description": "We use collected information to:\n\n- Provide and maintain the iMOs platform\n- Process and deliver messages (SMS, email)\n- Generate activity reports and analytics\n- Power AI features (Jessi assistant, message suggestions)\n- Send service notifications and updates\n- Detect and prevent fraud or abuse\n- Improve our products and services\n\n**We do NOT:**\n- Sell your personal information to third parties\n- Use customer contact data for our own marketing\n- Share data with advertisers\n- Train general AI models on your private data",
                    "tip": "Your data is your data. We process it only to provide you the service you signed up for."
                },
                {
                    "order": 3,
                    "title": "Data Storage & Security",
                    "description": "**Where Data is Stored:**\n- Primary database: MongoDB Atlas (cloud-hosted)\n- File storage: Encrypted object storage\n- Backups: Encrypted, stored in geographically separate locations\n\n**Security Measures:**\n- TLS encryption for all data in transit\n- Database encryption at rest\n- Regular security audits and penetration testing\n- Role-based access control (RBAC)\n- Automated threat detection\n\n**Data Retention:**\n- Active account data retained while account is active\n- Deleted contacts: 30-day recovery window, then permanent deletion\n- Deactivated users: 6-month grace period before data purge\n- Logs and audit trails: retained for 12 months",
                },
                {
                    "order": 4,
                    "title": "Your Rights",
                    "description": "You have the right to:\n\n**Access** - Request a copy of all data we hold about you\n**Correction** - Update or correct inaccurate information\n**Deletion** - Request deletion of your account and data\n**Portability** - Export your data in a standard format\n**Restriction** - Limit how we process your data\n**Objection** - Object to specific processing activities\n\n**To exercise your rights:**\nEmail: privacy@imosapp.com\nResponse time: within 30 days\n\n**California Residents (CCPA):**\n- Right to know what data is collected\n- Right to delete personal information\n- Right to opt-out of data sale (we do not sell data)\n- Right to non-discrimination for exercising rights",
                },
                {
                    "order": 5,
                    "title": "Cookies & Tracking",
                    "description": "**Essential Cookies:**\n- Authentication tokens\n- Session management\n- Security (CSRF protection)\n\n**Analytics:**\n- Usage patterns to improve the product\n- Feature adoption metrics\n- Performance monitoring\n\n**Third-Party:**\n- Payment processing (Stripe)\n- Error tracking (for bug fixes)\n\nYou can manage cookie preferences in your browser settings. Note that disabling essential cookies may affect platform functionality.\n\n**Do Not Track:**\nWe respect DNT browser signals and do not engage in cross-site tracking.",
                },
            ],
            "created_at": now,
        },

        # ====== DATA RETENTION POLICY ======
        {
            "title": "Data Retention Policy",
            "summary": "How data is handled when users leave or accounts are deactivated.",
            "category": "company_policy",
            "icon": "server",
            "sort_order": 5,
            "version": "1.0",
            "last_reviewed": now.isoformat(),
            "is_published": True,
            "slides": [
                {
                    "order": 1,
                    "title": "Overview",
                    "description": "This policy outlines how iMOs handles data when users are deactivated, leave an organization, or request account deletion.\n\nOur approach prioritizes:\n- Data integrity for the organization\n- Privacy for departing individuals\n- Compliance with data protection regulations\n- Business continuity",
                },
                {
                    "order": 2,
                    "title": "User Deactivation",
                    "description": "When a user is deactivated (e.g., leaves the company):\n\n**Soft Delete (Immediate):**\n- Account status set to \"deactivated\"\n- Login access revoked\n- User removed from active team lists\n\n**Contact Ownership:**\n- Organization-owned contacts remain accessible to the org\n- Personal contacts (manually added) are hidden from org view\n- Original user ID preserved for audit trail\n\n**6-Month Grace Period:**\n- All data retained for 6 months\n- Account can be reactivated by an admin\n- Personal contacts can be reassigned to another user\n\n**After 6 Months:**\n- Personal data permanently purged\n- Organization data fully transferred to org ownership\n- Audit logs retained per compliance requirements",
                    "tip": "Always reassign important contacts before deactivating a user."
                },
                {
                    "order": 3,
                    "title": "Account Deletion",
                    "description": "When a user requests full account deletion:\n\n**Individual Users:**\n- All personal data removed within 30 days\n- Communication history anonymized (content deleted, metadata retained)\n- Public pages (review links, digital cards) deactivated\n\n**Organization Accounts:**\n- Owner must confirm deletion\n- All user accounts under the org are deactivated\n- Organization-owned data (contacts, campaigns) deleted\n- 30-day recovery window before permanent deletion\n\n**What is NOT Deleted:**\n- Submitted reviews (anonymized, kept for store ratings)\n- Aggregate analytics (no PII)\n- Legal/compliance audit logs (retained per legal hold requirements)",
                },
                {
                    "order": 4,
                    "title": "Data Backup & Recovery",
                    "description": "**Backup Schedule:**\n- Automated daily backups\n- Point-in-time recovery available (last 7 days)\n- Monthly archive snapshots (retained for 12 months)\n\n**Recovery Process:**\n- Data restoration requests: contact support@imosapp.com\n- Recovery from backup: available within 24 hours\n- Accidental deletion: 30-day recovery window for contacts\n\n**Disaster Recovery:**\n- Multi-region database replication\n- RTO (Recovery Time Objective): 4 hours\n- RPO (Recovery Point Objective): 1 hour\n- Tested quarterly",
                },
            ],
            "created_at": now,
        },

        # ====== SECURITY AWARENESS TRAINING ======
        {
            "title": "Security Awareness Training",
            "summary": "Essential security training for all employees. Covers phishing, passwords, and data handling.",
            "category": "training",
            "icon": "shield",
            "sort_order": 6,
            "version": "1.0",
            "last_reviewed": now.isoformat(),
            "is_published": True,
            "slides": [
                {
                    "order": 1,
                    "title": "Why Security Matters",
                    "description": "As a CRM platform, iMOs handles thousands of customer records including:\n\n- Phone numbers and email addresses\n- Communication history\n- Sales data and customer preferences\n\nA single breach can:\n- Expose customer PII\n- Destroy trust with our clients\n- Result in legal penalties (TCPA fines up to $1,500 per violation)\n- Damage our brand permanently\n\nSecurity isn't just IT's job. Every team member is a line of defense.",
                    "warning": "The average cost of a data breach in 2025 was $4.88 million (IBM). Prevention is always cheaper."
                },
                {
                    "order": 2,
                    "title": "Recognizing Phishing",
                    "description": "Phishing is the #1 attack vector. Watch for:\n\n**Red Flags in Emails:**\n- Urgent language (\"Act now!\", \"Your account will be locked\")\n- Sender address doesn't match the company domain\n- Links that go to unexpected URLs (hover before clicking)\n- Requests for passwords, API keys, or financial info\n- Unexpected attachments\n\n**What to Do:**\n- Don't click suspicious links\n- Don't download unexpected attachments\n- Report to security@imosapp.com\n- When in doubt, verify via a different channel (call the sender)\n\n**We will NEVER ask you to:**\n- Share your password via email or chat\n- Transfer money urgently\n- Click a link to \"verify\" your account",
                    "tip": "If an email creates urgency or fear, that's the biggest red flag. Slow down and verify."
                },
                {
                    "order": 3,
                    "title": "Password & Authentication Security",
                    "description": "**Strong Password Rules:**\n- 12+ characters minimum\n- Mix: uppercase, lowercase, numbers, symbols\n- Never reuse passwords across services\n- Use a password manager (recommended: 1Password, Bitwarden)\n\n**Multi-Factor Authentication (MFA):**\n- Required for all admin accounts\n- Recommended for all accounts\n- Use authenticator apps over SMS when possible\n\n**What NOT to Do:**\n- Write passwords on sticky notes\n- Share credentials with coworkers\n- Store passwords in plain text files\n- Use personal information in passwords (birthdays, pet names)\n- Save passwords in browser on shared devices",
                },
                {
                    "order": 4,
                    "title": "Safe Data Handling",
                    "description": "**Sharing Customer Data:**\n- Only share on need-to-know basis\n- Use internal tools (not personal email)\n- Never screenshot customer data unnecessarily\n- Redact sensitive info in support tickets\n\n**Working Remotely:**\n- Use VPN on public Wi-Fi\n- Lock your screen when away (even at home)\n- Don't use public computers for work\n- Keep work data on work devices only\n\n**API Keys & Credentials:**\n- Never put keys in code or chat messages\n- Use environment variables only\n- Rotate keys if you suspect exposure\n- Report accidentally exposed keys immediately",
                    "tip": "Treat every piece of customer data like it's your own personal information."
                },
                {
                    "order": 5,
                    "title": "Incident Reporting",
                    "description": "**When to Report:**\n- You clicked a suspicious link\n- You see unauthorized activity on any account\n- A device is lost or stolen\n- You accidentally shared sensitive data\n- You notice unusual system behavior\n- A customer reports suspicious activity\n\n**How to Report:**\n1. Email: security@imosapp.com\n2. Notify your direct manager\n3. Do NOT try to \"fix\" it yourself\n4. Preserve evidence (don't delete emails/messages)\n\n**Timeline:**\n- Report within 1 hour of discovery\n- Security team acknowledges within 2 hours\n- Investigation begins immediately\n\nThere are NO penalties for reporting in good faith. We'd rather have 10 false alarms than 1 missed incident.",
                },
            ],
            "created_at": now,
        },

        # ====== PLATFORM ONBOARDING ======
        {
            "title": "Platform Onboarding Guide",
            "summary": "Step-by-step guide for new employees to get started with the iMOs platform.",
            "category": "training",
            "icon": "rocket",
            "sort_order": 7,
            "version": "1.0",
            "last_reviewed": now.isoformat(),
            "is_published": True,
            "slides": [
                {
                    "order": 1,
                    "title": "Welcome to iMOs",
                    "description": "Welcome to the team! This guide will walk you through everything you need to know to get started with the iMOs platform.\n\niMOs is an AI-powered Relationship Management System built for sales professionals at dealerships. Our platform helps salespeople:\n\n- Manage customer relationships\n- Send digital business cards\n- Automate follow-up communications\n- Track all customer interactions\n- Share review links and collect feedback\n- Collaborate with their team",
                },
                {
                    "order": 2,
                    "title": "Setting Up Your Account",
                    "description": "**Step 1: Log In**\nUse the credentials provided by your admin to log in at app.imosapp.com\n\n**Step 2: Complete Your Profile**\nGo to More > My Account and fill in:\n- Your name and title\n- Profile photo\n- Contact information\n- Bio for your digital card\n\n**Step 3: Set Up Your AI Persona**\nGo to More > AI Persona to customize how Jessi (your AI assistant) communicates on your behalf.\n\n**Step 4: Review Your Digital Card**\nGo to More > My Digital Card to preview how customers see your digital business card.",
                    "tip": "A complete profile with a professional photo dramatically increases customer engagement."
                },
                {
                    "order": 3,
                    "title": "The Inbox",
                    "description": "The Inbox is your communication hub:\n\n**SMS Mode** (default)\n- Send text messages to customers\n- If you don't have a Twilio number, messages will open your phone's native SMS app\n- All messages are logged regardless of send method\n\n**Email Mode**\n- Switch using the 'Switch to Email' button\n- Sends branded HTML emails via Resend\n- Perfect for longer, professional communications\n\n**Quick Actions (bottom toolbar):**\n- Photo: Send MMS\n- Document: Send templates\n- Star: Send review request\n- Card: Share digital card\n- Mic: Voice note\n- AI: Get AI suggestions",
                },
                {
                    "order": 4,
                    "title": "Managing Contacts",
                    "description": "**Adding Contacts:**\n- Tap '+' on the Contacts tab\n- Import from phone contacts\n- Upload CSV files\n- Contacts auto-created from inbound messages\n\n**Contact Profile:**\n- Tap any contact to see their full profile\n- Activity feed shows all interactions\n- Add tags for organization\n- Quick actions: SMS, Email, Call, Card, Review\n\n**Tags:**\n- Use tags to organize contacts (e.g., 'sold', 'prospect', 'service')\n- Tags power automation and reporting\n- The 'sold' tag triggers AI follow-up suggestions",
                },
                {
                    "order": 5,
                    "title": "Key Features",
                    "description": "**Digital Business Card**\n- Shareable link with your info, reviews, and contact details\n- Customers can save your vCard directly\n\n**Review Requests**\n- Send review links to customers\n- Reviews appear on your public profile\n- Track review submissions in reports\n\n**Congrats Cards**\n- Send branded congratulations cards for sales milestones\n- Auto-generates tracking links\n\n**Activity Reports**\n- View your performance metrics\n- Track emails sent, SMS sent, cards shared\n- Available under More > Performance\n\n**Team Chat**\n- Collaborate with your team\n- Share updates and coordinate",
                },
            ],
            "created_at": now,
        },

        # ====== INTEGRATION DOCUMENTATION ======
        {
            "title": "Integration & API Documentation",
            "summary": "Technical documentation for iMOs integrations, webhooks, and public API.",
            "category": "integrations",
            "icon": "git-network",
            "sort_order": 8,
            "version": "1.0",
            "last_reviewed": now.isoformat(),
            "is_published": True,
            "slides": [
                {
                    "order": 1,
                    "title": "API Overview",
                    "description": "iMOs provides a RESTful API for third-party CRM integrations.\n\n**Base URL:** https://app.imosapp.com/api/v1\n\n**Authentication:**\nAll requests require an API key in the header:\n```\nX-API-Key: your_api_key_here\n```\n\n**Rate Limits:**\n- 100 requests per minute per API key\n- 10,000 requests per day\n- Bulk operations count as 1 request\n\n**Response Format:**\nAll responses are JSON. Successful responses return 200/201. Errors return appropriate HTTP status codes with detail messages.",
                },
                {
                    "order": 2,
                    "title": "Contacts API",
                    "description": "**List Contacts**\nGET /api/v1/contacts\nQuery params: page, limit, search, tag, sort_by\n\n**Get Contact**\nGET /api/v1/contacts/{contact_id}\n\n**Create Contact**\nPOST /api/v1/contacts\nBody: { first_name, last_name, email, phone, tags[] }\n\n**Update Contact**\nPUT /api/v1/contacts/{contact_id}\nBody: any contact fields to update\n\n**Delete Contact**\nDELETE /api/v1/contacts/{contact_id}\n\n**Bulk Tag**\nPOST /api/v1/contacts/bulk/tag\nBody: { contact_ids[], tags[] }\n\n**Search**\nGET /api/v1/contacts/search?q=term\nSearches name, email, phone, tags",
                },
                {
                    "order": 3,
                    "title": "Messages & Conversations API",
                    "description": "**List Conversations**\nGET /api/v1/conversations\n\n**Get Messages**\nGET /api/v1/conversations/{id}/messages\n\n**Send Message**\nPOST /api/v1/messages/send\nBody: { contact_id, content, channel: 'sms'|'email' }\n\n**Message Channels:**\n- `sms` - Send via Twilio (requires provisioned number)\n- `email` - Send branded HTML email via Resend\n- `sms_personal` - Log message sent from personal phone\n\nAll sent messages are automatically logged as contact events for activity tracking and reporting.",
                },
                {
                    "order": 4,
                    "title": "Webhooks",
                    "description": "iMOs can send real-time notifications to your systems via webhooks.\n\n**Supported Events (21 types):**\n- contact.created / contact.updated / contact.deleted\n- message.sent / message.received\n- campaign.enrolled / campaign.completed\n- review.submitted / review.approved\n- user.created / user.deactivated\n- tag.added / tag.removed\n\n**Webhook Format:**\n```\nPOST your-endpoint-url\nX-Webhook-Signature: hmac_sha256_signature\nContent-Type: application/json\n\n{\n  event: 'contact.created',\n  timestamp: '2026-02-27T...',\n  data: { ... }\n}\n```\n\n**Security:**\n- All webhooks signed with HMAC-SHA256\n- Verify signature before processing\n- Delivery logs available for 30 days\n- Auto-retry on failure (3 attempts, exponential backoff)",
                },
                {
                    "order": 5,
                    "title": "Zapier & CRM Integration",
                    "description": "iMOs integrates with popular CRM platforms via our API and webhooks:\n\n**Zapier Integration:**\n- Use webhooks as triggers in Zapier\n- Use API endpoints as actions\n- Example: New contact in iMOs > Create lead in Salesforce\n- Example: Deal closed in HubSpot > Add 'sold' tag in iMOs\n\n**Common Integrations:**\n- Salesforce: Sync contacts and activity\n- HubSpot: Bi-directional contact sync\n- DealerSocket: Import customer data\n- VinSolutions: Lead routing\n\n**Getting Started:**\n1. Generate an API key in Settings > Integrations\n2. Set up webhook subscriptions for events you need\n3. Configure your CRM to send/receive data\n4. Test with a single contact before bulk operations",
                    "tip": "Start with contact sync first. Once that's reliable, add message and event tracking."
                },
                {
                    "order": 6,
                    "title": "Email Integration (Resend)",
                    "description": "iMOs uses Resend for all transactional email delivery.\n\n**Features:**\n- Branded HTML templates with your store's logo and colors\n- Automatic sender identification\n- Delivery tracking (sent, delivered, opened, clicked)\n- CTA buttons linking to your iMOs profile\n\n**Email Branding Hierarchy:**\n1. Partner branding (highest priority)\n2. Organization branding\n3. Store branding\n4. Default iMOs branding\n\n**Sender Address:**\nnoreply@imosapp.com (domain verified)\n\n**Customization:**\n- Logo, primary color, and accent color from your Brand Kit\n- Social media links from your store profile\n- Store address in the footer\n- Custom \"Powered By\" text for white-label partners",
                },
            ],
            "created_at": now,
        },
    ]

    result = await db.company_docs.insert_many(docs)
    return {"message": f"Seeded {len(result.inserted_ids)} documents"}
