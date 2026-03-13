"""
Account Health API — Aggregates user/org metrics for retention dashboards.
"""
from fastapi import APIRouter, HTTPException, Body
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from pydantic import BaseModel
import logging
import os
import asyncio
import resend

from routers.database import get_db

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "notifications@send.imonsocial.com")
APP_URL = os.environ.get("APP_URL", "https://app.imonsocial.com")

router = APIRouter(prefix="/account-health", tags=["Account Health"])
logger = logging.getLogger(__name__)


def _health_score(metrics: dict) -> dict:
    """Calculate overall health score from metrics. Returns score (0-100), grade, color."""
    score = 0
    # Activity (40 points max)
    days_since_login = metrics.get("days_since_login", 999)
    if days_since_login <= 1:
        score += 40
    elif days_since_login <= 3:
        score += 30
    elif days_since_login <= 7:
        score += 20
    elif days_since_login <= 14:
        score += 10
    elif days_since_login <= 30:
        score += 5

    # Contacts (20 points max)
    contacts = metrics.get("total_contacts", 0)
    if contacts >= 50:
        score += 20
    elif contacts >= 20:
        score += 15
    elif contacts >= 5:
        score += 10
    elif contacts >= 1:
        score += 5

    # Messages (20 points max)
    msgs_30d = metrics.get("messages_30d", 0)
    if msgs_30d >= 50:
        score += 20
    elif msgs_30d >= 20:
        score += 15
    elif msgs_30d >= 5:
        score += 10
    elif msgs_30d >= 1:
        score += 5

    # Campaigns & Touchpoints (20 points max)
    campaigns = metrics.get("active_campaigns", 0)
    touchpoints = metrics.get("touchpoints_30d", 0)
    if campaigns >= 3 and touchpoints >= 10:
        score += 20
    elif campaigns >= 1 and touchpoints >= 5:
        score += 15
    elif campaigns >= 1 or touchpoints >= 3:
        score += 10
    elif touchpoints >= 1:
        score += 5

    if score >= 70:
        return {"score": score, "grade": "Healthy", "color": "#34C759"}
    elif score >= 40:
        return {"score": score, "grade": "At Risk", "color": "#FF9500"}
    else:
        return {"score": score, "grade": "Critical", "color": "#FF3B30"}


async def _get_user_metrics(db, user_id: str, days: int = 30) -> dict:
    """Aggregate all metrics for a single user."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    uid = user_id

    # Contacts
    total_contacts = await db.contacts.count_documents({"user_id": uid})
    new_contacts = await db.contacts.count_documents({"user_id": uid, "created_at": {"$gte": cutoff}})

    # Messages
    total_messages = await db.messages.count_documents({"user_id": uid})
    messages_period = await db.messages.count_documents({"user_id": uid, "timestamp": {"$gte": cutoff}})

    # Tasks
    total_tasks = await db.tasks.count_documents({"user_id": uid})
    completed_tasks = await db.tasks.count_documents({"user_id": uid, "completed": True})

    # Campaigns
    active_campaigns = await db.campaigns.count_documents({"user_id": uid, "active": True})
    total_campaigns = await db.campaigns.count_documents({"user_id": uid})
    enrollments = await db.campaign_enrollments.count_documents({"user_id": uid})
    enrollments_period = await db.campaign_enrollments.count_documents({"user_id": uid, "enrolled_at": {"$gte": cutoff}})

    # Contact events (touchpoints)
    total_events = await db.contact_events.count_documents({"user_id": uid})
    events_period = await db.contact_events.count_documents({"user_id": uid, "timestamp": {"$gte": cutoff}})

    # Event breakdown
    event_pipeline = [
        {"$match": {"user_id": uid, "timestamp": {"$gte": cutoff}}},
        {"$group": {"_id": "$event_type", "count": {"$sum": 1}}},
    ]
    event_breakdown = {}
    async for doc in db.contact_events.aggregate(event_pipeline):
        event_breakdown[doc["_id"]] = doc["count"]

    # Short URL clicks
    short_urls = await db.short_urls.count_documents({"user_id": uid})
    link_clicks = await db.short_url_clicks.count_documents({"clicked_at": {"$gte": cutoff}})

    # Congrats cards
    cards_shared = await db.congrats_cards.count_documents({"user_id": uid})

    # User info
    user = await db.users.find_one({"_id": ObjectId(uid)}, {"password": 0, "_id": 0})
    last_login = user.get("last_login") if user else None
    days_since_login = (datetime.utcnow() - last_login).days if last_login else 999

    return {
        "total_contacts": total_contacts,
        "new_contacts": new_contacts,
        "total_messages": total_messages,
        "messages_30d": messages_period,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "active_campaigns": active_campaigns,
        "total_campaigns": total_campaigns,
        "enrollments": enrollments,
        "enrollments_30d": enrollments_period,
        "total_touchpoints": total_events,
        "touchpoints_30d": events_period,
        "event_breakdown": event_breakdown,
        "short_urls_created": short_urls,
        "link_clicks_30d": link_clicks,
        "cards_shared": cards_shared,
        "days_since_login": days_since_login,
        "last_login": last_login.isoformat() if last_login else None,
    }


@router.get("/overview")
async def get_accounts_overview(period: int = 30):
    """List all user accounts with health scores for the dashboard."""
    db = get_db()
    cutoff = datetime.utcnow() - timedelta(days=period)

    users = await db.users.find(
        {"role": {"$nin": ["super_admin"]}, "is_active": {"$ne": False}},
        {"password": 0}
    ).sort("last_login", -1).limit(500).to_list(500)

    accounts = []
    for u in users:
        uid = str(u["_id"])
        # Fast counts (no full aggregation for overview)
        contacts = await db.contacts.count_documents({"user_id": uid})
        messages = await db.messages.count_documents({"user_id": uid, "timestamp": {"$gte": cutoff}})
        events = await db.contact_events.count_documents({"user_id": uid, "timestamp": {"$gte": cutoff}})
        campaigns = await db.campaigns.count_documents({"user_id": uid, "active": True})

        last_login = u.get("last_login")
        days_since = (datetime.utcnow() - last_login).days if last_login else 999

        health = _health_score({
            "days_since_login": days_since,
            "total_contacts": contacts,
            "messages_30d": messages,
            "active_campaigns": campaigns,
            "touchpoints_30d": events,
        })

        # Get org/store names
        org_name = ""
        store_name = ""
        if u.get("organization_id"):
            try:
                org = await db.organizations.find_one({"_id": ObjectId(u["organization_id"])}, {"name": 1})
                org_name = org.get("name", "") if org else ""
            except:
                pass
        if u.get("store_id"):
            try:
                store = await db.stores.find_one({"_id": ObjectId(u["store_id"])}, {"name": 1})
                store_name = store.get("name", "") if store else ""
            except:
                pass

        accounts.append({
            "user_id": uid,
            "name": u.get("name", u.get("email", "")),
            "email": u.get("email", ""),
            "role": u.get("role", "user"),
            "organization": org_name,
            "store": store_name,
            "photo_url": u.get("photo_url", ""),
            "contacts": contacts,
            "messages_30d": messages,
            "touchpoints_30d": events,
            "active_campaigns": campaigns,
            "days_since_login": days_since,
            "last_login": last_login.isoformat() if isinstance(last_login, datetime) else str(last_login or ""),
            "health": health,
            "created_at": u.get("created_at").isoformat() if isinstance(u.get("created_at"), datetime) else str(u.get("created_at", "")),
            "tos_accepted": u.get("tos_accepted", False),
        })

    # Sort by health score ascending (worst first)
    accounts.sort(key=lambda x: x["health"]["score"])
    return accounts


@router.get("/user/{user_id}")
async def get_user_health(user_id: str, period: int = 30):
    """Detailed health report for a single user."""
    db = get_db()

    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"password": 0})
    if not user:
        raise HTTPException(404, "User not found")

    metrics = await _get_user_metrics(db, user_id, period)
    health = _health_score(metrics)

    # Get org/store info
    org_name = ""
    store_name = ""
    if user.get("organization_id"):
        try:
            org = await db.organizations.find_one({"_id": ObjectId(user["organization_id"])}, {"name": 1})
            org_name = org.get("name", "") if org else ""
        except:
            pass
    if user.get("store_id"):
        try:
            store = await db.stores.find_one({"_id": ObjectId(user["store_id"])}, {"name": 1})
            store_name = store.get("name", "") if store else ""
        except:
            pass

    # Recent activity timeline (last 10 events)
    recent_events = []
    async for ev in db.contact_events.find(
        {"user_id": user_id}, {"_id": 0}
    ).sort("timestamp", -1).limit(10):
        if "timestamp" in ev and ev["timestamp"]:
            ev["timestamp"] = ev["timestamp"].isoformat()
        recent_events.append(ev)

    user_id_str = str(user["_id"])
    del user["_id"]

    return {
        "user": {**user, "id": user_id_str, "created_at": user.get("created_at").isoformat() if isinstance(user.get("created_at"), datetime) else str(user.get("created_at", "")), "last_login": user.get("last_login").isoformat() if isinstance(user.get("last_login"), datetime) else str(user.get("last_login", ""))},
        "organization": org_name,
        "store": store_name,
        "metrics": metrics,
        "health": health,
        "recent_events": recent_events,
        "period_days": period,
    }


@router.get("/org/{org_id}")
async def get_org_health(org_id: str, period: int = 30):
    """Aggregate health report for an entire organization."""
    db = get_db()

    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    if not org:
        raise HTTPException(404, "Organization not found")

    # Get all users in this org
    users = await db.users.find(
        {"organization_id": org_id, "is_active": {"$ne": False}},
        {"password": 0}
    ).to_list(500)

    user_reports = []
    agg = {"contacts": 0, "messages_30d": 0, "touchpoints_30d": 0, "active_campaigns": 0, "total_users": len(users), "active_users_7d": 0}

    cutoff = datetime.utcnow() - timedelta(days=period)
    for u in users:
        uid = str(u["_id"])
        contacts = await db.contacts.count_documents({"user_id": uid})
        messages = await db.messages.count_documents({"user_id": uid, "timestamp": {"$gte": cutoff}})
        events = await db.contact_events.count_documents({"user_id": uid, "timestamp": {"$gte": cutoff}})
        campaigns = await db.campaigns.count_documents({"user_id": uid, "active": True})

        last_login = u.get("last_login")
        days_since = (datetime.utcnow() - last_login).days if last_login else 999
        if days_since <= 7:
            agg["active_users_7d"] += 1

        health = _health_score({"days_since_login": days_since, "total_contacts": contacts, "messages_30d": messages, "active_campaigns": campaigns, "touchpoints_30d": events})

        agg["contacts"] += contacts
        agg["messages_30d"] += messages
        agg["touchpoints_30d"] += events
        agg["active_campaigns"] += campaigns

        user_reports.append({
            "user_id": uid,
            "name": u.get("name", u.get("email", "")),
            "role": u.get("role", ""),
            "contacts": contacts,
            "messages_30d": messages,
            "touchpoints_30d": events,
            "days_since_login": days_since,
            "health": health,
        })

    # Org-level health
    avg_score = sum(r["health"]["score"] for r in user_reports) / len(user_reports) if user_reports else 0
    if avg_score >= 70:
        org_health = {"score": round(avg_score), "grade": "Healthy", "color": "#34C759"}
    elif avg_score >= 40:
        org_health = {"score": round(avg_score), "grade": "At Risk", "color": "#FF9500"}
    else:
        org_health = {"score": round(avg_score), "grade": "Critical", "color": "#FF3B30"}

    org_id_str = str(org["_id"])
    del org["_id"]

    return {
        "organization": {**org, "id": org_id_str},
        "health": org_health,
        "aggregate": agg,
        "users": sorted(user_reports, key=lambda x: x["health"]["score"]),
        "period_days": period,
    }



def _build_report_html(user_info: dict, metrics: dict, health: dict, event_breakdown: dict, recent_events: list, org_name: str, store_name: str, period: int, note: str = "") -> str:
    """Build an HTML email report for an account's health status."""
    score = health["score"]
    grade = health["grade"]
    color = health["color"]
    m = metrics

    # Event breakdown rows
    breakdown_rows = ""
    sorted_events = sorted(event_breakdown.items(), key=lambda x: x[1], reverse=True)
    max_val = max(event_breakdown.values()) if event_breakdown else 1
    for etype, count in sorted_events[:15]:
        bar_pct = min(100, int((count / max_val) * 100))
        label = etype.replace("_", " ").title()
        breakdown_rows += f"""
        <tr>
          <td style="padding:6px 10px;font-size:13px;color:#333;text-transform:capitalize">{label}</td>
          <td style="padding:6px 10px;width:50%">
            <div style="background:#E8E8ED;border-radius:4px;height:8px;overflow:hidden">
              <div style="background:{color};height:100%;width:{bar_pct}%;border-radius:4px"></div>
            </div>
          </td>
          <td style="padding:6px 10px;font-size:13px;font-weight:700;text-align:right;color:#333">{count}</td>
        </tr>"""

    # Recent activity rows
    activity_rows = ""
    for ev in recent_events[:10]:
        ev_type = (ev.get("event_type") or "").replace("_", " ").title()
        contact = ev.get("contact_name") or ""
        ts = ev.get("timestamp") or ""
        if isinstance(ts, str) and ts:
            try:
                dt = datetime.fromisoformat(ts)
                ts = dt.strftime("%b %d, %Y %I:%M %p")
            except:
                pass
        activity_rows += f"""
        <tr>
          <td style="padding:6px 10px;font-size:12px;color:#333">{ev_type}</td>
          <td style="padding:6px 10px;font-size:12px;color:#666">{contact}</td>
          <td style="padding:6px 10px;font-size:12px;color:#999;text-align:right">{ts}</td>
        </tr>"""

    note_block = f"""
    <div style="background:#FFF8E7;border-left:4px solid #C9A962;padding:12px 16px;margin-bottom:24px;border-radius:0 8px 8px 0">
      <p style="margin:0;font-size:13px;color:#333;font-style:italic">{note}</p>
    </div>""" if note else ""

    login_text = "Today" if m.get("days_since_login", 999) <= 0 else "Never" if m.get("days_since_login", 999) >= 999 else f"{m['days_since_login']} days ago"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
    <body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#F5F5F7">
    <div style="max-width:640px;margin:0 auto;padding:20px">

      <!-- Header -->
      <div style="text-align:center;padding:24px 0 16px">
        <h1 style="margin:0;font-size:22px;color:#1D1D1F">Account Health Report</h1>
        <p style="margin:4px 0 0;font-size:13px;color:#888">{period}-Day Snapshot &bull; Generated {datetime.now(timezone.utc).strftime('%b %d, %Y')}</p>
      </div>

      {note_block}

      <!-- Health Score Banner -->
      <div style="background:{'#E8FAE8' if score >= 70 else '#FFF3E0' if score >= 40 else '#FEEBEE'};border:1.5px solid {color}30;border-radius:16px;padding:20px;text-align:center;margin-bottom:24px">
        <div style="display:inline-block;width:56px;height:56px;border-radius:28px;background:{color};line-height:56px;text-align:center;color:#FFF;font-size:20px;font-weight:900">{score}</div>
        <h2 style="margin:10px 0 4px;font-size:20px;color:{color}">{grade}</h2>
        <p style="margin:0;font-size:13px;color:#666">{'Actively using the platform' if score >= 70 else 'Declining engagement — needs attention' if score >= 40 else 'Critical — immediate attention required'}</p>
      </div>

      <!-- Account Info -->
      <div style="background:#FFF;border-radius:12px;border:1px solid #E5E5EA;padding:16px;margin-bottom:20px">
        <h3 style="margin:0 0 10px;font-size:14px;color:#333">Account</h3>
        <table style="width:100%;border-collapse:collapse">
          <tr><td style="padding:4px 0;font-size:13px;color:#888">Name</td><td style="padding:4px 0;font-size:13px;font-weight:600;text-align:right;color:#333">{user_info.get('name', user_info.get('email', ''))}</td></tr>
          <tr><td style="padding:4px 0;font-size:13px;color:#888">Email</td><td style="padding:4px 0;font-size:13px;text-align:right;color:#333">{user_info.get('email', '')}</td></tr>
          <tr><td style="padding:4px 0;font-size:13px;color:#888">Organization</td><td style="padding:4px 0;font-size:13px;text-align:right;color:#333">{org_name or 'N/A'}</td></tr>
          <tr><td style="padding:4px 0;font-size:13px;color:#888">Store</td><td style="padding:4px 0;font-size:13px;text-align:right;color:#333">{store_name or 'N/A'}</td></tr>
          <tr><td style="padding:4px 0;font-size:13px;color:#888">Last Login</td><td style="padding:4px 0;font-size:13px;font-weight:600;text-align:right;color:{'#34C759' if m.get('days_since_login',999) <= 7 else '#FF9500' if m.get('days_since_login',999) <= 30 else '#FF3B30'}">{login_text}</td></tr>
        </table>
      </div>

      <!-- Key Metrics -->
      <div style="background:#FFF;border-radius:12px;border:1px solid #E5E5EA;padding:16px;margin-bottom:20px">
        <h3 style="margin:0 0 12px;font-size:14px;color:#333">Key Metrics ({period} days)</h3>
        <table style="width:100%;border-collapse:collapse">
          <tr>
            <td style="text-align:center;padding:10px;border-right:1px solid #E5E5EA">
              <div style="font-size:24px;font-weight:800;color:#007AFF">{m.get('total_contacts', 0)}</div>
              <div style="font-size:11px;color:#888;margin-top:2px">Contacts</div>
              {'<div style="font-size:10px;color:#34C759">+' + str(m.get('new_contacts',0)) + ' new</div>' if m.get('new_contacts',0) > 0 else ''}
            </td>
            <td style="text-align:center;padding:10px;border-right:1px solid #E5E5EA">
              <div style="font-size:24px;font-weight:800;color:#5856D6">{m.get('messages_30d', 0)}</div>
              <div style="font-size:11px;color:#888;margin-top:2px">Messages</div>
              <div style="font-size:10px;color:#999">{m.get('total_messages',0)} total</div>
            </td>
            <td style="text-align:center;padding:10px">
              <div style="font-size:24px;font-weight:800;color:#FF9500">{m.get('touchpoints_30d', 0)}</div>
              <div style="font-size:11px;color:#888;margin-top:2px">Touchpoints</div>
              <div style="font-size:10px;color:#999">{m.get('total_touchpoints',0)} total</div>
            </td>
          </tr>
        </table>
        <div style="border-top:1px solid #E5E5EA;margin-top:10px;padding-top:10px">
        <table style="width:100%;border-collapse:collapse">
          <tr>
            <td style="text-align:center;padding:8px;border-right:1px solid #E5E5EA">
              <div style="font-size:20px;font-weight:800;color:#34C759">{m.get('active_campaigns', 0)}</div>
              <div style="font-size:11px;color:#888">Active Campaigns</div>
            </td>
            <td style="text-align:center;padding:8px;border-right:1px solid #E5E5EA">
              <div style="font-size:20px;font-weight:800;color:#AF52DE">{m.get('enrollments_30d', 0)}</div>
              <div style="font-size:11px;color:#888">Enrollments</div>
            </td>
            <td style="text-align:center;padding:8px;border-right:1px solid #E5E5EA">
              <div style="font-size:20px;font-weight:800;color:#00C7BE">{m.get('completed_tasks', 0)}/{m.get('total_tasks', 0)}</div>
              <div style="font-size:11px;color:#888">Tasks Done</div>
            </td>
            <td style="text-align:center;padding:8px">
              <div style="font-size:20px;font-weight:800;color:#007AFF">{m.get('cards_shared', 0)}</div>
              <div style="font-size:11px;color:#888">Cards Shared</div>
            </td>
          </tr>
        </table>
        </div>
        <div style="border-top:1px solid #E5E5EA;margin-top:10px;padding-top:10px">
        <table style="width:100%;border-collapse:collapse">
          <tr>
            <td style="text-align:center;padding:8px;border-right:1px solid #E5E5EA">
              <div style="font-size:20px;font-weight:800;color:#FF2D55">{m.get('short_urls_created', 0)}</div>
              <div style="font-size:11px;color:#888">Links Created</div>
            </td>
            <td style="text-align:center;padding:8px">
              <div style="font-size:20px;font-weight:800;color:#FFCC00">{m.get('link_clicks_30d', 0)}</div>
              <div style="font-size:11px;color:#888">Link Clicks</div>
            </td>
          </tr>
        </table>
        </div>
      </div>

      <!-- Touchpoint Breakdown -->
      {f'''<div style="background:#FFF;border-radius:12px;border:1px solid #E5E5EA;padding:16px;margin-bottom:20px">
        <h3 style="margin:0 0 10px;font-size:14px;color:#333">Touchpoint Breakdown</h3>
        <table style="width:100%;border-collapse:collapse">{breakdown_rows}</table>
      </div>''' if breakdown_rows else ''}

      <!-- Recent Activity -->
      {f'''<div style="background:#FFF;border-radius:12px;border:1px solid #E5E5EA;padding:16px;margin-bottom:20px">
        <h3 style="margin:0 0 10px;font-size:14px;color:#333">Recent Activity</h3>
        <table style="width:100%;border-collapse:collapse">{activity_rows}</table>
      </div>''' if activity_rows else ''}

      <!-- Footer -->
      <div style="text-align:center;padding:20px 0;border-top:1px solid #E5E5EA;margin-top:10px">
        <p style="font-size:12px;color:#999;margin:0">Generated by i'M On Social &bull; <a href="{APP_URL}" style="color:#007AFF;text-decoration:none">Open Dashboard</a></p>
      </div>
    </div>
    </body>
    </html>"""
    return html


class SendReportRequest(BaseModel):
    recipient_email: str
    recipient_name: str = ""
    note: str = ""
    period: int = 30


@router.post("/user/{user_id}/send-report")
async def send_user_health_report(user_id: str, req: SendReportRequest):
    """Generate and email a health report for a single user."""
    if not RESEND_API_KEY:
        raise HTTPException(500, "Email service not configured")
    resend.api_key = RESEND_API_KEY

    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"password": 0})
    if not user:
        raise HTTPException(404, "User not found")

    metrics = await _get_user_metrics(db, user_id, req.period)
    health = _health_score(metrics)

    org_name, store_name = "", ""
    if user.get("organization_id"):
        try:
            org = await db.organizations.find_one({"_id": ObjectId(user["organization_id"])}, {"name": 1})
            org_name = org.get("name", "") if org else ""
        except:
            pass
    if user.get("store_id"):
        try:
            store = await db.stores.find_one({"_id": ObjectId(user["store_id"])}, {"name": 1})
            store_name = store.get("name", "") if store else ""
        except:
            pass

    recent_events = []
    async for ev in db.contact_events.find({"user_id": user_id}, {"_id": 0}).sort("timestamp", -1).limit(10):
        if "timestamp" in ev and ev["timestamp"]:
            ev["timestamp"] = ev["timestamp"].isoformat()
        recent_events.append(ev)

    user_info = {"name": user.get("name", ""), "email": user.get("email", ""), "role": user.get("role", "")}
    html = _build_report_html(user_info, metrics, health, metrics.get("event_breakdown", {}), recent_events, org_name, store_name, req.period, req.note)

    account_name = user.get("name") or user.get("email", "Account")
    subject = f"Account Health Report: {account_name} — {health['grade']} ({health['score']}/100)"

    try:
        result = await asyncio.to_thread(resend.Emails.send, {
            "from": f"i'M On Social <{SENDER_EMAIL}>",
            "to": [req.recipient_email],
            "reply_to": "support@imonsocial.com",
            "subject": subject,
            "html": html,
        })
        await db.email_logs.insert_one({
            "type": "health_report",
            "user_id": user_id,
            "recipient_email": req.recipient_email,
            "recipient_name": req.recipient_name,
            "subject": subject,
            "status": "sent",
            "resend_id": result.get("id") if isinstance(result, dict) else str(result),
            "sent_at": datetime.now(timezone.utc),
        })
        return {"status": "sent", "message": f"Report sent to {req.recipient_email}"}
    except Exception as e:
        logger.error(f"Failed to send health report: {e}")
        raise HTTPException(500, f"Failed to send email: {str(e)}")


@router.post("/org/{org_id}/send-report")
async def send_org_health_report(org_id: str, req: SendReportRequest):
    """Generate and email an aggregate health report for an organization."""
    if not RESEND_API_KEY:
        raise HTTPException(500, "Email service not configured")
    resend.api_key = RESEND_API_KEY

    db = get_db()
    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    if not org:
        raise HTTPException(404, "Organization not found")

    org_name = org.get("name", "Organization")
    users = await db.users.find({"organization_id": org_id, "is_active": {"$ne": False}}, {"password": 0}).to_list(500)

    # Build aggregate metrics
    cutoff = datetime.utcnow() - timedelta(days=req.period)
    total_contacts, total_messages, total_touchpoints, total_campaigns = 0, 0, 0, 0
    user_summaries = []
    all_event_breakdown = {}

    for u in users:
        uid = str(u["_id"])
        contacts = await db.contacts.count_documents({"user_id": uid})
        messages = await db.messages.count_documents({"user_id": uid, "timestamp": {"$gte": cutoff}})
        events = await db.contact_events.count_documents({"user_id": uid, "timestamp": {"$gte": cutoff}})
        campaigns = await db.campaigns.count_documents({"user_id": uid, "active": True})

        total_contacts += contacts
        total_messages += messages
        total_touchpoints += events
        total_campaigns += campaigns

        last_login = u.get("last_login")
        days_since = (datetime.utcnow() - last_login).days if last_login else 999
        h = _health_score({"days_since_login": days_since, "total_contacts": contacts, "messages_30d": messages, "active_campaigns": campaigns, "touchpoints_30d": events})
        user_summaries.append({"name": u.get("name", u.get("email", "")), "health": h, "contacts": contacts, "messages": messages, "touchpoints": events})

        # Aggregate event breakdown
        pipeline = [{"$match": {"user_id": uid, "timestamp": {"$gte": cutoff}}}, {"$group": {"_id": "$event_type", "count": {"$sum": 1}}}]
        async for doc in db.contact_events.aggregate(pipeline):
            all_event_breakdown[doc["_id"]] = all_event_breakdown.get(doc["_id"], 0) + doc["count"]

    avg_score = sum(u["health"]["score"] for u in user_summaries) / len(user_summaries) if user_summaries else 0
    org_health = {"score": round(avg_score), "grade": "Healthy" if avg_score >= 70 else "At Risk" if avg_score >= 40 else "Critical", "color": "#34C759" if avg_score >= 70 else "#FF9500" if avg_score >= 40 else "#FF3B30"}

    agg_metrics = {
        "total_contacts": total_contacts, "new_contacts": 0, "total_messages": 0, "messages_30d": total_messages,
        "total_tasks": 0, "completed_tasks": 0, "active_campaigns": total_campaigns, "total_campaigns": total_campaigns,
        "enrollments": 0, "enrollments_30d": 0, "total_touchpoints": total_touchpoints, "touchpoints_30d": total_touchpoints,
        "short_urls_created": 0, "link_clicks_30d": 0, "cards_shared": 0, "days_since_login": 0, "event_breakdown": all_event_breakdown,
    }

    # Build user breakdown table for the email
    user_rows_html = ""
    for us in sorted(user_summaries, key=lambda x: x["health"]["score"]):
        user_rows_html += f"""<tr>
          <td style="padding:6px 10px;font-size:12px;color:#333">{us['name']}</td>
          <td style="padding:6px 10px;text-align:center"><span style="display:inline-block;padding:2px 8px;border-radius:8px;font-size:11px;font-weight:700;color:#FFF;background:{us['health']['color']}">{us['health']['score']}</span></td>
          <td style="padding:6px 10px;font-size:12px;text-align:center;color:#333">{us['contacts']}</td>
          <td style="padding:6px 10px;font-size:12px;text-align:center;color:#333">{us['messages']}</td>
          <td style="padding:6px 10px;font-size:12px;text-align:center;color:#333">{us['touchpoints']}</td>
        </tr>"""

    org_info = {"name": org_name, "email": "", "role": "Organization"}
    html = _build_report_html(org_info, agg_metrics, org_health, all_event_breakdown, [], org_name, "", req.period, req.note)

    # Inject user breakdown table before the footer
    user_table = f"""<div style="background:#FFF;border-radius:12px;border:1px solid #E5E5EA;padding:16px;margin-bottom:20px">
      <h3 style="margin:0 0 10px;font-size:14px;color:#333">Team Members ({len(user_summaries)})</h3>
      <table style="width:100%;border-collapse:collapse">
        <tr style="border-bottom:1px solid #E5E5EA">
          <th style="padding:6px 10px;font-size:11px;color:#888;text-align:left">Name</th>
          <th style="padding:6px 10px;font-size:11px;color:#888;text-align:center">Score</th>
          <th style="padding:6px 10px;font-size:11px;color:#888;text-align:center">Contacts</th>
          <th style="padding:6px 10px;font-size:11px;color:#888;text-align:center">Messages</th>
          <th style="padding:6px 10px;font-size:11px;color:#888;text-align:center">Touches</th>
        </tr>
        {user_rows_html}
      </table>
    </div>"""
    html = html.replace("<!-- Footer -->", f"{user_table}\n      <!-- Footer -->")

    subject = f"Organization Health Report: {org_name} — {org_health['grade']} ({org_health['score']}/100)"
    try:
        result = await asyncio.to_thread(resend.Emails.send, {
            "from": f"i'M On Social <{SENDER_EMAIL}>",
            "to": [req.recipient_email],
            "reply_to": "support@imonsocial.com",
            "subject": subject,
            "html": html,
        })
        await db.email_logs.insert_one({
            "type": "org_health_report",
            "org_id": org_id,
            "recipient_email": req.recipient_email,
            "recipient_name": req.recipient_name,
            "subject": subject,
            "status": "sent",
            "resend_id": result.get("id") if isinstance(result, dict) else str(result),
            "sent_at": datetime.now(timezone.utc),
        })
        return {"status": "sent", "message": f"Organization report sent to {req.recipient_email}"}
    except Exception as e:
        logger.error(f"Failed to send org health report: {e}")
        raise HTTPException(500, f"Failed to send email: {str(e)}")


# ==================== Scheduled Health Reports ====================

class ScheduleCreateRequest(BaseModel):
    scope: str  # "user" or "org"
    target_id: str
    target_name: str = ""
    recipient_email: str
    recipient_name: str = ""
    note: str = ""


@router.post("/schedules")
async def create_schedule(req: ScheduleCreateRequest, created_by: str = ""):
    """Create a monthly health report schedule."""
    db = get_db()
    if req.scope not in ("user", "org"):
        raise HTTPException(400, "scope must be 'user' or 'org'")

    # Validate ObjectId format
    try:
        ObjectId(req.target_id)
    except Exception:
        raise HTTPException(400, "Invalid target ID format")

    # Validate target exists
    if req.scope == "user":
        target = await db.users.find_one({"_id": ObjectId(req.target_id)}, {"name": 1, "email": 1})
        if not target:
            raise HTTPException(404, "User not found")
        target_name = req.target_name or target.get("name") or target.get("email", "")
    else:
        target = await db.organizations.find_one({"_id": ObjectId(req.target_id)}, {"name": 1})
        if not target:
            raise HTTPException(404, "Organization not found")
        target_name = req.target_name or target.get("name", "")

    doc = {
        "scope": req.scope,
        "target_id": req.target_id,
        "target_name": target_name,
        "recipient_email": req.recipient_email,
        "recipient_name": req.recipient_name,
        "note": req.note,
        "frequency": "monthly",
        "active": True,
        "created_by": created_by,
        "created_at": datetime.now(timezone.utc),
        "last_sent_at": None,
    }
    result = await db.health_report_schedules.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    del doc["_id"]
    if "created_at" in doc and doc["created_at"]:
        doc["created_at"] = doc["created_at"].isoformat()
    return doc


@router.get("/schedules")
async def list_schedules():
    """List all scheduled health reports."""
    db = get_db()
    schedules = []
    async for doc in db.health_report_schedules.find().sort("created_at", -1):
        doc["id"] = str(doc["_id"])
        del doc["_id"]
        if isinstance(doc.get("created_at"), datetime):
            doc["created_at"] = doc["created_at"].isoformat()
        if isinstance(doc.get("last_sent_at"), datetime):
            doc["last_sent_at"] = doc["last_sent_at"].isoformat()
        schedules.append(doc)
    return schedules


@router.put("/schedules/{schedule_id}")
async def update_schedule(schedule_id: str, data: dict = Body(...)):
    """Update a schedule (toggle active, change email, etc.)."""
    db = get_db()
    allowed = {"active", "recipient_email", "recipient_name", "note"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        raise HTTPException(400, "No valid fields to update")

    result = await db.health_report_schedules.update_one(
        {"_id": ObjectId(schedule_id)},
        {"$set": updates}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Schedule not found")
    return {"status": "updated"}


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str):
    """Delete a scheduled health report."""
    db = get_db()
    result = await db.health_report_schedules.delete_one({"_id": ObjectId(schedule_id)})
    if result.deleted_count == 0:
        raise HTTPException(404, "Schedule not found")
    return {"status": "deleted"}


async def run_monthly_health_reports():
    """Called by the scheduler on the last day of each month. Sends all active health report schedules."""
    from routers.database import get_db
    db = get_db()

    today = datetime.now(timezone.utc)
    tomorrow = today + timedelta(days=1)
    if tomorrow.month == today.month:
        # Not the last day of the month
        return 0

    logger.info("[HealthScheduler] Last day of month — processing scheduled health reports")

    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        logger.error("[HealthScheduler] RESEND_API_KEY not set")
        return 0

    resend.api_key = api_key
    sent = 0

    async for schedule in db.health_report_schedules.find({"active": True}):
        try:
            scope = schedule["scope"]
            target_id = schedule["target_id"]
            email = schedule["recipient_email"]
            note = schedule.get("note", "")
            period = 30

            if scope == "user":
                user = await db.users.find_one({"_id": ObjectId(target_id)}, {"password": 0})
                if not user:
                    continue
                metrics = await _get_user_metrics(db, target_id, period)
                health = _health_score(metrics)

                org_name, store_name = "", ""
                if user.get("organization_id"):
                    try:
                        org = await db.organizations.find_one({"_id": ObjectId(user["organization_id"])}, {"name": 1})
                        org_name = org.get("name", "") if org else ""
                    except:
                        pass
                if user.get("store_id"):
                    try:
                        store = await db.stores.find_one({"_id": ObjectId(user["store_id"])}, {"name": 1})
                        store_name = store.get("name", "") if store else ""
                    except:
                        pass

                recent = []
                async for ev in db.contact_events.find({"user_id": target_id}, {"_id": 0}).sort("timestamp", -1).limit(10):
                    if ev.get("timestamp"):
                        ev["timestamp"] = ev["timestamp"].isoformat()
                    recent.append(ev)

                user_info = {"name": user.get("name", ""), "email": user.get("email", "")}
                html = _build_report_html(user_info, metrics, health, metrics.get("event_breakdown", {}), recent, org_name, store_name, period, note)
                subject = f"Monthly Health Report: {user_info['name'] or user_info['email']} — {health['grade']} ({health['score']}/100)"

            else:
                org = await db.organizations.find_one({"_id": ObjectId(target_id)})
                if not org:
                    continue
                # Simplified org report — reuse the org send logic
                org_name = org.get("name", "Organization")
                users = await db.users.find({"organization_id": target_id, "is_active": {"$ne": False}}, {"password": 0}).to_list(500)
                cutoff = datetime.utcnow() - timedelta(days=period)
                tc, tm, tt, tca = 0, 0, 0, 0
                for u in users:
                    uid = str(u["_id"])
                    tc += await db.contacts.count_documents({"user_id": uid})
                    tm += await db.messages.count_documents({"user_id": uid, "timestamp": {"$gte": cutoff}})
                    tt += await db.contact_events.count_documents({"user_id": uid, "timestamp": {"$gte": cutoff}})
                    tca += await db.campaigns.count_documents({"user_id": uid, "active": True})

                avg_score = 50  # placeholder
                org_health = {"score": avg_score, "grade": "At Risk", "color": "#FF9500"}
                agg_metrics = {"total_contacts": tc, "new_contacts": 0, "total_messages": 0, "messages_30d": tm,
                    "total_tasks": 0, "completed_tasks": 0, "active_campaigns": tca, "total_campaigns": tca,
                    "enrollments": 0, "enrollments_30d": 0, "total_touchpoints": tt, "touchpoints_30d": tt,
                    "short_urls_created": 0, "link_clicks_30d": 0, "cards_shared": 0, "days_since_login": 0, "event_breakdown": {}}
                org_info = {"name": org_name, "email": ""}
                html = _build_report_html(org_info, agg_metrics, org_health, {}, [], org_name, "", period, note)
                subject = f"Monthly Org Health Report: {org_name}"

            await asyncio.to_thread(resend.Emails.send, {
                "from": f"i'M On Social <{SENDER_EMAIL}>",
                "to": [email],
                "reply_to": "support@imonsocial.com",
                "subject": subject,
                "html": html,
            })

            await db.health_report_schedules.update_one(
                {"_id": schedule["_id"]},
                {"$set": {"last_sent_at": datetime.now(timezone.utc)}}
            )
            sent += 1
            logger.info(f"[HealthScheduler] Sent {scope} report for {target_id} to {email}")

        except Exception as e:
            logger.error(f"[HealthScheduler] Failed to send report for schedule {schedule.get('_id')}: {e}")

    logger.info(f"[HealthScheduler] Monthly reports complete: {sent} sent")
    return sent
