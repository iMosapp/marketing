"""Request gate for /api: who may call a route without a session, and whose data a {user_id} route may touch.

Default is deny: an /api request with no proven caller (signed JWT or live impersonation session) is refused unless the route is
public here. Public = webhooks that verify their own secret or signature, customer-facing pages and token links, machine callers
with their own credential (cron secret, X-API-Key) and the login flows. Anything else needs a session, including every /api/auth
route that reads or writes an account."""
import re

from bson import ObjectId
from fastapi import HTTPException
from starlette.routing import Match

from routers.database import get_db

MANAGER_ROLES = ("super_admin", "org_admin", "store_manager")

# Any method.
PUBLIC_PREFIXES = (
    "/api/health", "/api/build-version", "/api/branding/", "/api/legal/", "/api/public/", "/api/w/", "/api/card/", "/api/opt-in/",
    "/api/go/", "/api/go-links/", "/api/get/", "/api/app-links/qr/", "/api/app-installs/", "/api/email/track/", "/api/email/webhook/",
    "/api/ghl/webhook/", "/api/messages/webhook/", "/api/webhook/stripe", "/api/stripe/webhook", "/api/billing/stripe/webhook",
    "/api/billing/checkout/confirm", "/api/leads/adf", "/api/leads/email-inbound", "/api/leads/webhook/", "/api/lead-sources/inbound/",
    "/api/cron/", "/api/v1/", "/api/promo-videos/", "/api/onboarding-jessi/jessi.vcf", "/api/onboarding-jessi/call/",
    "/api/scripts/roleplay/audio/", "/api/scripts/roleplay/twiml/", "/api/scripts/roleplay/gate/", "/api/scripts/roleplay/host-after/",
    "/api/scripts/roleplay/after/", "/api/scripts/roleplay/status/", "/api/scripts/roleplay/recording/", "/api/interview/call/",
    "/api/nda/sign/", "/api/team-invite/", "/api/crm/timeline/", "/api/contact-files/open/", "/api/share/", "/api/wallet/download/",
    "/api/linkpage/public/", "/api/help-center/ask", "/api/push/vapid-key", "/api/push/log-error", "/api/errors/report",
    "/api/tracking/event", "/api/subscriptions/plans", "/api/subscriptions/discount-codes/validate/", "/api/subscriptions/checkout",
    "/api/subscriptions/w9/", "/api/calendar/oauth/", "/api/media/view/", "/api/appraisals/intake/", "/api/chat/start",
    "/api/chat/message", "/api/chat/capture", "/api/seo/robots.txt", "/api/seo/sitemap", "/api/seo/meta/", "/api/seo/store-directory/",
    "/api/seo/user-by-slug/", "/api/seo/track-visit", "/api/review/page/", "/api/review/track-click", "/api/review/submit",
    "/api/review/check-hours/", "/api/showcase/user/", "/api/showcase/store/", "/api/showcase/org/", "/api/showcase/photo/",
    "/api/showcase/feedback-photo/", "/api/showcase/user-photo/", "/api/showcase/store-logo/", "/api/congrats/card/",
    "/api/congrats/share/", "/api/congrats/referral-link/", "/api/s/og-", "/api/p/data/", "/api/p/store/", "/api/p/review/", "/api/p/refer/", "/api/training/certificate/",
    "/api/webhooks/twilio/", "/api/webhooks/dialer/", "/api/webhooks/resend/", "/api/webhooks/inventory", "/api/webhooks/user-created",
    "/api/webhooks/user-deleted", "/api/webhooks/contact-created", "/api/webhooks/event", "/api/webhooks/config",
    "/api/auth/login", "/api/auth/signup", "/api/auth/test-login", "/api/auth/logout", "/api/auth/refresh", "/api/auth/me",
    "/api/auth/forgot-password/", "/api/auth/activate/", "/api/auth/ref/",
    "/api/auth/admin-reset", "/api/auth/admin-fix-login", "/api/auth/force-reset-password", "/api/auth/admin-fix-all-passwords",  # dead, answer 410
)
PUBLIC_PATTERNS = (
    re.compile(r"^/api/(p|card)/[0-9a-f]{24}$"),
    re.compile(r"^/api/subscriptions/quotes/[^/]+/(public|payment-status|accept|create-payment)$"),
    re.compile(r"^/api/subscriptions/checkout/status/"),
    re.compile(r"^/api/scripts/[^/]+/pdf$"),
    re.compile(r"^/api/calls/recording/[^/]+$"),
    re.compile(r"^/api/messages/media/[^/]+$"),
    re.compile(r"^/api/admin/partners/by-slug/"),
    re.compile(r"^/api/admin/team/shared-inboxes/[^/]+/webhook$"),
    re.compile(r"^/api/partners/agreements/[^/]+/(sign|w9|w9-digital|create-payment)$"),
)
# GET only.
PUBLIC_GET_PATTERNS = (
    re.compile(r"^/api/s/[^/]+$"),  # short link redirect page; minting (/create, /wrap) needs a session
    re.compile(r"^/api/images/(?!_health|cache-stats|migrate)"),
    re.compile(r"^/api/profile/[0-9a-f]{24}(/gallery|/vcard\.vcf)?$"),
    re.compile(r"^/api/partners/agreements/[^/]+(/pdf|/payment-status)?$"),
)
PUBLIC_POST_EXACT = {"/api/demo-requests"}
# Under a public prefix but called by the app with a session (not by the provider): never anonymous.
PRIVATE_EXACT = {"/api/webhooks/twilio/call", "/api/webhooks/twilio/call-cancel"}
PRIVATE_PATTERNS = (re.compile(r"^/api/webhooks/twilio/call-progress/"),)


def is_public(method: str, path: str) -> bool:
    if path in PRIVATE_EXACT or any(p.match(path) for p in PRIVATE_PATTERNS):
        return False
    if path.startswith(PUBLIC_PREFIXES) or any(p.match(path) for p in PUBLIC_PATTERNS):
        return True
    if method == "GET" and any(p.match(path) for p in PUBLIC_GET_PATTERNS):
        return True
    return method == "POST" and path in PUBLIC_POST_EXACT


_OID_SEGMENT = re.compile(r"/[0-9a-f]{24}(/|$)")


def route_user_id(app, scope) -> str | None:
    """The {user_id} path parameter of the route this request resolves to, if it has one."""
    if not _OID_SEGMENT.search(scope["path"]):
        return None
    for route in app.router.routes:
        match, child = route.matches(scope)
        if match == Match.FULL:
            value = (child.get("path_params") or {}).get("user_id")
            return str(value) if value else None
    return None


_OID = re.compile(r"^[0-9a-f]{24}$")


def query_user_id(request) -> str | None:
    """`?user_id=` is an identity claim too (49 routes read it): bound like the path parameter."""
    value = (request.query_params.get("user_id") or "").strip()
    return value if _OID.match(value) else None


RANK = {"super_admin": 4, "org_admin": 3, "store_manager": 2, "user": 1}


def outranked(caller_role: str, target_role: str) -> bool:
    """True when the target holds more privilege than the caller (a store manager vs an org admin)."""
    return RANK.get(target_role or "user", 1) > RANK.get(caller_role or "user", 1)


async def manager_can_access(caller_id: str, target_id: str, write: bool = False) -> bool:
    """A manager may touch another user only inside their own organization / stores, and may never modify an account that
    outranks them (phone, email, password, persona and recovery details included). Anyone else: no."""
    from routers.rbac import get_scoped_organization_ids, get_scoped_store_ids
    db = get_db()
    try:
        caller = await db.users.find_one({"_id": ObjectId(caller_id)}, {"role": 1, "organization_id": 1, "store_id": 1, "store_ids": 1, "partner_id": 1})
        target = await db.users.find_one({"_id": ObjectId(target_id)}, {"role": 1, "organization_id": 1, "store_id": 1, "store_ids": 1})
    except Exception:
        return False
    if not caller:
        return False
    role = caller.get("role")
    if role == "super_admin":
        return True
    if not target:
        return True  # let the handler answer 404
    if write and outranked(role, target.get("role")):
        return False
    if role == "org_admin":
        return str(target.get("organization_id") or "") in {str(o) for o in await get_scoped_organization_ids(caller)}
    if role == "store_manager":
        stores = {str(s) for s in await get_scoped_store_ids(caller)}
        return str(target.get("store_id") or "") in stores or bool(stores & {str(s) for s in (target.get("store_ids") or [])})
    return False


async def assert_self_or_scoped_manager(caller_id: str, target_id: str, write: bool = True) -> None:
    if str(caller_id) == str(target_id) or await manager_can_access(str(caller_id), str(target_id), write=write):
        return
    raise HTTPException(status_code=403, detail="Access denied — you can only access your own data")
