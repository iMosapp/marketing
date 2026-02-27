"""
Reports Router - Unified reporting with org/store/user level permissions
"""
from fastapi import APIRouter, HTTPException, Header, Query
from datetime import datetime, timedelta
from bson import ObjectId
from typing import Optional
from pydantic import BaseModel
import logging
import os

from routers.database import get_db

router = APIRouter(prefix="/reports", tags=["reports"])
logger = logging.getLogger(__name__)


async def get_requesting_user(user_id: str):
    """Get user making the request"""
    if not user_id:
        return None
    try:
        return await get_db().users.find_one({"_id": ObjectId(user_id)})
    except:
        return None


def get_date_range(days: int = 30):
    """Get start and end dates for query"""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    return start_date, end_date


@router.get("/overview")
async def get_reports_overview(
    days: int = Query(30, ge=1, le=365),
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """
    Get reports overview based on user's permission level:
    - super_admin/org_admin: See org-wide stats
    - store_manager: See store stats
    - user: See personal stats only
    """
    user = await get_requesting_user(x_user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    role = user.get('role', 'user')
    user_id = str(user['_id'])
    org_id = user.get('organization_id')
    store_ids = user.get('store_ids', [])
    
    start_date, end_date = get_date_range(days)
    db = get_db()
    
    # Build query filters based on role
    if role in ['super_admin', 'org_admin']:
        # Can see everything in their org (or everything for super_admin)
        user_filter = {}
        if role == 'org_admin' and org_id:
            user_filter['organization_id'] = org_id
        scope = 'organization'
    elif role == 'store_manager':
        # Can see their stores only
        user_filter = {'store_id': {'$in': store_ids}} if store_ids else {'_id': ObjectId(user_id)}
        scope = 'store'
    else:
        # Regular users see only their own stats
        user_filter = {'_id': ObjectId(user_id)}
        scope = 'personal'
    
    # Get users in scope
    users_in_scope = await db.users.find(user_filter, {'_id': 1}).limit(500).to_list(500)
    user_ids = [str(u['_id']) for u in users_in_scope]
    
    # Aggregate statistics
    stats = {
        'scope': scope,
        'period_days': days,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'summary': {},
        'messaging': {},
        'contacts': {},
        'campaigns': {},
        'team': {}
    }
    
    # Message stats
    message_filter = {
        'created_at': {'$gte': start_date, '$lte': end_date}
    }
    if user_ids:
        message_filter['$or'] = [
            {'sender_id': {'$in': user_ids}},
            {'user_id': {'$in': user_ids}}
        ]
    
    total_messages = await db.messages.count_documents(message_filter)
    
    # SMS vs Email breakdown
    sms_count = await db.messages.count_documents({**message_filter, 'type': 'sms'})
    email_count = await db.messages.count_documents({**message_filter, 'type': 'email'})
    ai_messages = await db.messages.count_documents({**message_filter, 'sent_by_ai': True})
    
    stats['messaging'] = {
        'total_messages': total_messages,
        'sms_sent': sms_count,
        'emails_sent': email_count,
        'ai_handled': ai_messages,
        'manual': total_messages - ai_messages
    }
    
    # Contact stats
    contact_filter = {'created_at': {'$gte': start_date, '$lte': end_date}}
    if user_ids:
        contact_filter['user_id'] = {'$in': user_ids}
    
    new_contacts = await db.contacts.count_documents(contact_filter)
    total_contacts = await db.contacts.count_documents(
        {'user_id': {'$in': user_ids}} if user_ids else {}
    )
    
    stats['contacts'] = {
        'new_contacts': new_contacts,
        'total_contacts': total_contacts
    }
    
    # Campaign/Broadcast stats
    campaign_filter = {'created_at': {'$gte': start_date, '$lte': end_date}}
    if user_ids:
        campaign_filter['created_by'] = {'$in': user_ids}
    
    campaigns = await db.campaigns.find(campaign_filter).to_list(100)
    total_recipients = sum(c.get('recipient_count', 0) for c in campaigns)
    total_delivered = sum(c.get('delivered_count', 0) for c in campaigns)
    
    stats['campaigns'] = {
        'total_campaigns': len(campaigns),
        'total_recipients': total_recipients,
        'total_delivered': total_delivered,
        'delivery_rate': round(total_delivered / total_recipients * 100, 1) if total_recipients > 0 else 0
    }
    
    # Team stats (for managers and admins)
    if role in ['super_admin', 'org_admin', 'store_manager']:
        team_count = len(users_in_scope)
        active_users = await db.users.count_documents({
            **user_filter,
            'last_active': {'$gte': start_date}
        })
        
        stats['team'] = {
            'total_members': team_count,
            'active_members': active_users
        }
    
    # Summary
    stats['summary'] = {
        'total_messages': total_messages,
        'new_contacts': new_contacts,
        'campaigns_sent': len(campaigns),
        'ai_automation_rate': round(ai_messages / total_messages * 100, 1) if total_messages > 0 else 0
    }
    
    return stats


@router.get("/messaging")
async def get_messaging_report(
    days: int = Query(30, ge=1, le=365),
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """Detailed messaging analytics"""
    user = await get_requesting_user(x_user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    role = user.get('role', 'user')
    user_id = str(user['_id'])
    org_id = user.get('organization_id')
    store_ids = user.get('store_ids', [])
    
    start_date, end_date = get_date_range(days)
    db = get_db()
    
    # Build user scope
    if role in ['super_admin', 'org_admin']:
        user_filter = {'organization_id': org_id} if role == 'org_admin' and org_id else {}
    elif role == 'store_manager':
        user_filter = {'store_id': {'$in': store_ids}} if store_ids else {'_id': ObjectId(user_id)}
    else:
        user_filter = {'_id': ObjectId(user_id)}
    
    users_in_scope = await db.users.find(user_filter, {'_id': 1}).limit(500).to_list(500)
    user_ids = [str(u['_id']) for u in users_in_scope]
    
    # Daily breakdown
    daily_stats = []
    for i in range(days):
        day_start = start_date + timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        
        day_filter = {
            'created_at': {'$gte': day_start, '$lt': day_end}
        }
        if user_ids:
            day_filter['$or'] = [
                {'sender_id': {'$in': user_ids}},
                {'user_id': {'$in': user_ids}}
            ]
        
        sms = await db.messages.count_documents({**day_filter, 'type': 'sms'})
        email = await db.messages.count_documents({**day_filter, 'type': 'email'})
        ai = await db.messages.count_documents({**day_filter, 'sent_by_ai': True})
        
        daily_stats.append({
            'date': day_start.strftime('%Y-%m-%d'),
            'sms': sms,
            'email': email,
            'ai_handled': ai,
            'total': sms + email
        })
    
    return {
        'period_days': days,
        'daily_breakdown': daily_stats,
        'totals': {
            'sms': sum(d['sms'] for d in daily_stats),
            'email': sum(d['email'] for d in daily_stats),
            'ai_handled': sum(d['ai_handled'] for d in daily_stats),
            'total': sum(d['total'] for d in daily_stats)
        }
    }


@router.get("/campaigns")
async def get_campaigns_report(
    days: int = Query(30, ge=1, le=365),
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """Broadcast/Campaign analytics"""
    user = await get_requesting_user(x_user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    role = user.get('role', 'user')
    user_id = str(user['_id'])
    org_id = user.get('organization_id')
    store_ids = user.get('store_ids', [])
    
    start_date, end_date = get_date_range(days)
    db = get_db()
    
    # Build filter based on role
    campaign_filter = {'created_at': {'$gte': start_date, '$lte': end_date}}
    
    if role == 'super_admin':
        pass  # No filter, see all
    elif role == 'org_admin' and org_id:
        campaign_filter['organization_id'] = org_id
    elif role == 'store_manager' and store_ids:
        campaign_filter['store_id'] = {'$in': store_ids}
    else:
        campaign_filter['created_by'] = user_id
    
    campaigns = await db.campaigns.find(campaign_filter).sort('created_at', -1).to_list(100)
    
    # Process campaigns
    campaign_list = []
    for c in campaigns:
        campaign_list.append({
            '_id': str(c['_id']),
            'name': c.get('name', 'Untitled'),
            'type': c.get('type', 'sms'),
            'status': c.get('status', 'unknown'),
            'created_at': c.get('created_at').isoformat() if c.get('created_at') else None,
            'recipient_count': c.get('recipient_count', 0),
            'delivered_count': c.get('delivered_count', 0),
            'opened_count': c.get('opened_count', 0),
            'clicked_count': c.get('clicked_count', 0),
            'delivery_rate': round(c.get('delivered_count', 0) / c.get('recipient_count', 1) * 100, 1),
            'open_rate': round(c.get('opened_count', 0) / c.get('delivered_count', 1) * 100, 1) if c.get('delivered_count', 0) > 0 else 0
        })
    
    # Aggregate totals
    totals = {
        'total_campaigns': len(campaign_list),
        'total_recipients': sum(c['recipient_count'] for c in campaign_list),
        'total_delivered': sum(c['delivered_count'] for c in campaign_list),
        'total_opened': sum(c['opened_count'] for c in campaign_list),
        'total_clicked': sum(c['clicked_count'] for c in campaign_list),
        'avg_delivery_rate': round(sum(c['delivery_rate'] for c in campaign_list) / len(campaign_list), 1) if campaign_list else 0,
        'avg_open_rate': round(sum(c['open_rate'] for c in campaign_list) / len(campaign_list), 1) if campaign_list else 0
    }
    
    return {
        'period_days': days,
        'campaigns': campaign_list,
        'totals': totals
    }


@router.get("/team")
async def get_team_report(
    days: int = Query(30, ge=1, le=365),
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """Team performance report - managers and admins only"""
    user = await get_requesting_user(x_user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    role = user.get('role', 'user')
    if role not in ['super_admin', 'org_admin', 'store_manager']:
        raise HTTPException(status_code=403, detail="Team reports require manager access")
    
    org_id = user.get('organization_id')
    store_ids = user.get('store_ids', [])
    
    start_date, end_date = get_date_range(days)
    db = get_db()
    
    # Build user filter
    if role == 'super_admin':
        user_filter = {}
    elif role == 'org_admin' and org_id:
        user_filter = {'organization_id': org_id}
    else:
        user_filter = {'store_id': {'$in': store_ids}} if store_ids else {}
    
    users = await db.users.find(user_filter).to_list(500)
    
    # Get stats for each user
    team_stats = []
    for u in users:
        uid = str(u['_id'])
        
        # Message count
        msg_count = await db.messages.count_documents({
            'sender_id': uid,
            'created_at': {'$gte': start_date, '$lte': end_date}
        })
        
        # Contact count
        contact_count = await db.contacts.count_documents({
            'user_id': uid,
            'created_at': {'$gte': start_date, '$lte': end_date}
        })
        
        team_stats.append({
            '_id': uid,
            'name': u.get('name', 'Unknown'),
            'email': u.get('email', ''),
            'role': u.get('role', 'user'),
            'messages_sent': msg_count,
            'contacts_added': contact_count,
            'last_active': u.get('last_active').isoformat() if u.get('last_active') else None
        })
    
    # Sort by messages sent
    team_stats.sort(key=lambda x: x['messages_sent'], reverse=True)
    
    return {
        'period_days': days,
        'team_members': team_stats,
        'totals': {
            'total_members': len(team_stats),
            'total_messages': sum(t['messages_sent'] for t in team_stats),
            'total_contacts': sum(t['contacts_added'] for t in team_stats)
        }
    }


@router.get("/personal")
async def get_personal_report(
    days: int = Query(30, ge=1, le=365),
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """Personal performance stats for any user"""
    user = await get_requesting_user(x_user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    user_id = str(user['_id'])
    start_date, end_date = get_date_range(days)
    db = get_db()
    
    # Messages
    total_messages = await db.messages.count_documents({
        'sender_id': user_id,
        'created_at': {'$gte': start_date, '$lte': end_date}
    })
    
    sms_sent = await db.messages.count_documents({
        'sender_id': user_id,
        'type': 'sms',
        'created_at': {'$gte': start_date, '$lte': end_date}
    })
    
    emails_sent = await db.messages.count_documents({
        'sender_id': user_id,
        'type': 'email',
        'created_at': {'$gte': start_date, '$lte': end_date}
    })
    
    # Contacts
    new_contacts = await db.contacts.count_documents({
        'user_id': user_id,
        'created_at': {'$gte': start_date, '$lte': end_date}
    })
    
    total_contacts = await db.contacts.count_documents({'user_id': user_id})
    
    # Conversations
    conversations = await db.threads.count_documents({
        'user_id': user_id,
        'updated_at': {'$gte': start_date}
    })
    
    # Daily activity
    daily_activity = []
    for i in range(min(days, 14)):  # Last 14 days detail
        day_start = end_date - timedelta(days=i+1)
        day_end = end_date - timedelta(days=i)
        
        day_messages = await db.messages.count_documents({
            'sender_id': user_id,
            'created_at': {'$gte': day_start, '$lt': day_end}
        })
        
        daily_activity.append({
            'date': day_start.strftime('%Y-%m-%d'),
            'messages': day_messages
        })
    
    daily_activity.reverse()
    
    return {
        'period_days': days,
        'user': {
            'name': user.get('name'),
            'email': user.get('email'),
            'role': user.get('role')
        },
        'messaging': {
            'total_messages': total_messages,
            'sms_sent': sms_sent,
            'emails_sent': emails_sent,
            'avg_per_day': round(total_messages / days, 1)
        },
        'contacts': {
            'new_contacts': new_contacts,
            'total_contacts': total_contacts
        },
        'activity': {
            'conversations_active': conversations,
            'daily_breakdown': daily_activity
        }
    }



# ===== NEW: Activity Report with all tracked events =====

class ReportPreferences(BaseModel):
    frequency: str = "none"  # none, daily, weekly, monthly
    day_of_week: Optional[int] = 1
    day_of_month: Optional[int] = 1
    email_enabled: bool = False
    email_to: Optional[str] = None


@router.get("/activity/{user_id}")
async def get_activity_report(
    user_id: str,
    start_date: str = Query(..., description="YYYY-MM-DD"),
    end_date: str = Query(..., description="YYYY-MM-DD"),
    team: bool = Query(False),
):
    """Comprehensive activity report: messages, cards, reviews, congrats, contacts, clicks."""
    db = get_db()
    try:
        start = datetime.fromisoformat(start_date)
    except Exception:
        start = datetime.strptime(start_date, "%Y-%m-%d")
    try:
        end = datetime.fromisoformat(end_date)
    except Exception:
        end = datetime.strptime(end_date, "%Y-%m-%d")
    if end.hour == 0:
        end = end.replace(hour=23, minute=59, second=59)

    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"_id": 0, "role": 1, "store_id": 1, "name": 1})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    is_manager = user.get("role") in ("super_admin", "admin", "manager", "store_manager", "org_admin")

    if team and is_manager and user.get("store_id"):
        team_users = await db.users.find(
            {"store_id": user["store_id"], "status": {"$ne": "deactivated"}},
            {"_id": 1, "name": 1, "role": 1}
        ).to_list(200)
        user_ids = [str(u["_id"]) for u in team_users]
        user_map = {str(u["_id"]): u.get("name", "Unknown") for u in team_users}
    else:
        user_ids = [user_id]
        user_map = {user_id: user.get("name", "You")}

    date_filter = {"timestamp": {"$gte": start, "$lte": end}}

    # Messages by channel
    msg_results = await db.messages.aggregate([
        {"$match": {"user_id": {"$in": user_ids}, "sender": "user", **date_filter}},
        {"$group": {"_id": {"user_id": "$user_id", "channel": {"$ifNull": ["$channel", "sms"]}}, "count": {"$sum": 1}}}
    ]).to_list(500)

    # Contact events
    evt_results = await db.contact_events.aggregate([
        {"$match": {"user_id": {"$in": user_ids}, **date_filter}},
        {"$group": {"_id": {"user_id": "$user_id", "event_type": "$event_type"}, "count": {"$sum": 1}}}
    ]).to_list(500)

    # New contacts
    contact_results = await db.contacts.aggregate([
        {"$match": {"user_id": {"$in": user_ids}, "created_at": {"$gte": start, "$lte": end}}},
        {"$group": {"_id": "$user_id", "count": {"$sum": 1}}}
    ]).to_list(200)

    # Calls
    call_results = await db.calls.aggregate([
        {"$match": {"user_id": {"$in": user_ids}, "timestamp": {"$gte": start, "$lte": end}}},
        {"$group": {"_id": "$user_id", "count": {"$sum": 1}}}
    ]).to_list(200)

    # Build per-user stats
    per_user = {}
    for uid in user_ids:
        per_user[uid] = {
            "name": user_map.get(uid, "Unknown"),
            "sms_sent": 0, "sms_personal": 0, "emails_sent": 0,
            "digital_cards_sent": 0, "review_invites_sent": 0,
            "congrats_cards_sent": 0, "vcards_sent": 0,
            "new_contacts": 0, "calls": 0, "link_clicks": 0,
            "total_touchpoints": 0,
        }

    for r in msg_results:
        uid = r["_id"]["user_id"]
        ch = r["_id"]["channel"]
        if uid not in per_user:
            continue
        if ch == "sms":
            per_user[uid]["sms_sent"] += r["count"]
        elif ch == "sms_personal":
            per_user[uid]["sms_personal"] += r["count"]
        elif ch == "email":
            per_user[uid]["emails_sent"] += r["count"]

    for r in evt_results:
        uid = r["_id"]["user_id"]
        etype = r["_id"]["event_type"]
        if uid not in per_user:
            continue
        mapping = {
            "digital_card_sent": "digital_cards_sent",
            "review_request_sent": "review_invites_sent",
            "congrats_card_sent": "congrats_cards_sent",
            "vcard_sent": "vcards_sent",
        }
        if etype in mapping:
            per_user[uid][mapping[etype]] += r["count"]

    for r in contact_results:
        uid = r["_id"]
        if uid in per_user:
            per_user[uid]["new_contacts"] = r["count"]

    for r in call_results:
        uid = r["_id"]
        if uid in per_user:
            per_user[uid]["calls"] = r["count"]

    for uid, s in per_user.items():
        s["total_touchpoints"] = (
            s["sms_sent"] + s["sms_personal"] + s["emails_sent"] +
            s["calls"] + s["digital_cards_sent"] +
            s["review_invites_sent"] + s["congrats_cards_sent"] + s["vcards_sent"]
        )

    totals = {}
    for key in ["sms_sent", "sms_personal", "emails_sent", "digital_cards_sent",
                 "review_invites_sent", "congrats_cards_sent", "vcards_sent",
                 "new_contacts", "calls", "link_clicks", "total_touchpoints"]:
        totals[key] = sum(s[key] for s in per_user.values())

    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "is_team_report": team and is_manager,
        "totals": totals,
        "per_user": [{"user_id": uid, **stats} for uid, stats in per_user.items()],
    }


@router.get("/activity-daily/{user_id}")
async def get_activity_daily(
    user_id: str,
    start_date: str = Query(...),
    end_date: str = Query(...),
    team: bool = Query(False),
):
    """Day-by-day breakdown for charts."""
    db = get_db()
    try:
        start = datetime.fromisoformat(start_date)
    except Exception:
        start = datetime.strptime(start_date, "%Y-%m-%d")
    try:
        end = datetime.fromisoformat(end_date)
    except Exception:
        end = datetime.strptime(end_date, "%Y-%m-%d")
    if end.hour == 0:
        end = end.replace(hour=23, minute=59, second=59)

    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"_id": 0, "role": 1, "store_id": 1})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    is_manager = user.get("role") in ("super_admin", "admin", "manager", "store_manager")
    if team and is_manager and user.get("store_id"):
        team_users = await db.users.find(
            {"store_id": user["store_id"], "status": {"$ne": "deactivated"}}, {"_id": 1}
        ).to_list(200)
        user_ids = [str(u["_id"]) for u in team_users]
    else:
        user_ids = [user_id]

    results = await db.messages.aggregate([
        {"$match": {"user_id": {"$in": user_ids}, "sender": "user",
                     "timestamp": {"$gte": start, "$lte": end}}},
        {"$group": {
            "_id": {"date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                    "channel": {"$ifNull": ["$channel", "sms"]}},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id.date": 1}}
    ]).to_list(1000)

    days = {}
    cur = start
    while cur <= end:
        ds = cur.strftime("%Y-%m-%d")
        days[ds] = {"date": ds, "sms": 0, "sms_personal": 0, "email": 0, "total": 0}
        cur += timedelta(days=1)
    for r in results:
        d = r["_id"]["date"]
        ch = r["_id"]["channel"]
        if d in days and ch in ("sms", "sms_personal", "email"):
            days[d][ch] += r["count"]
            days[d]["total"] += r["count"]
    return {"days": list(days.values())}


# --- Report preferences & email delivery ---

@router.get("/preferences/{user_id}")
async def get_report_preferences(user_id: str):
    db = get_db()
    prefs = await db.report_preferences.find_one({"user_id": user_id}, {"_id": 0})
    return prefs or {"user_id": user_id, "frequency": "none", "day_of_week": 1,
                     "day_of_month": 1, "email_enabled": False, "email_to": None}


@router.put("/preferences/{user_id}")
async def update_report_preferences(user_id: str, prefs: ReportPreferences):
    db = get_db()
    from datetime import timezone as tz
    await db.report_preferences.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id, **prefs.dict(), "updated_at": datetime.now(tz.utc)}},
        upsert=True,
    )
    return {"message": "Preferences saved", **prefs.dict()}


@router.post("/send-email/{user_id}")
async def send_report_email(
    user_id: str,
    start_date: str = Query(...),
    end_date: str = Query(...),
    team: bool = Query(False),
    recipient_email: Optional[str] = Query(None),
):
    """Generate and email a clean HTML activity report."""
    import resend as resend_mod
    import asyncio
    import os as _os
    from datetime import timezone as tz

    RESEND_KEY = _os.environ.get("RESEND_API_KEY")
    SENDER = _os.environ.get("SENDER_EMAIL", "noreply@imosapp.com")
    if not RESEND_KEY:
        raise HTTPException(status_code=500, detail="Email not configured")
    resend_mod.api_key = RESEND_KEY

    db = get_db()
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"_id": 0, "name": 1, "email": 1})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    to_email = recipient_email or user.get("email")
    if not to_email:
        raise HTTPException(status_code=400, detail="No email address")

    report = await get_activity_report(user_id, start_date, end_date, team)
    t = report["totals"]
    per_user = report["per_user"]

    try:
        sfmt = datetime.fromisoformat(start_date).strftime("%b %d, %Y")
    except Exception:
        sfmt = start_date
    try:
        efmt = datetime.fromisoformat(end_date).strftime("%b %d, %Y")
    except Exception:
        efmt = end_date

    rows = ""
    for u in per_user:
        rows += f'<tr><td style="padding:10px 12px;border-bottom:1px solid #2C2C2E;color:#FFF;font-weight:600;">{u["name"]}</td>'
        for k in ["total_touchpoints", "sms_sent", "sms_personal", "emails_sent", "digital_cards_sent", "review_invites_sent", "congrats_cards_sent", "new_contacts"]:
            rows += f'<td style="padding:10px 8px;border-bottom:1px solid #2C2C2E;color:#CCC;text-align:center;">{u[k]}</td>'
        rows += '</tr>'

    team_table = ""
    if len(per_user) > 1:
        headers = ["Name", "Touch", "SMS", "Personal", "Email", "Cards", "Reviews", "Congrats", "Contacts"]
        th = "".join(f'<th style="padding:10px 8px;text-align:center;color:#8E8E93;font-size:11px;">{h}</th>' for h in headers)
        team_table = f'<h3 style="font-size:16px;color:#FFF;margin:24px 0 12px;">Team Breakdown</h3><div style="overflow-x:auto;"><table style="width:100%;border-collapse:collapse;background:#1C1C1E;border-radius:12px;overflow:hidden;"><thead><tr style="background:#2C2C2E;">{th}</tr></thead><tbody>{rows}</tbody></table></div>'

    stats_cards = [
        (t["total_touchpoints"], "TOUCHPOINTS", "#34C759"),
        (t["sms_sent"] + t["sms_personal"], "SMS SENT", "#007AFF"),
        (t["emails_sent"], "EMAILS", "#AF52DE"),
        (t["digital_cards_sent"], "CARDS SHARED", "#007AFF"),
        (t["review_invites_sent"], "REVIEW INVITES", "#FFD60A"),
        (t["congrats_cards_sent"], "CONGRATS", "#C9A962"),
        (t["new_contacts"], "NEW CONTACTS", "#32ADE6"),
        (t["calls"], "CALLS", "#34C759"),
    ]
    cards_html = ""
    for val, label, color in stats_cards:
        cards_html += f'<div style="flex:1;min-width:120px;background:#1C1C1E;padding:14px;border-radius:12px;text-align:center;"><div style="font-size:24px;font-weight:700;color:{color};">{val}</div><div style="font-size:10px;color:#8E8E93;margin-top:4px;">{label}</div></div>'

    html = f"""<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:640px;margin:0 auto;background:#000;color:#FFF;padding:28px;border-radius:16px;">
    <div style="text-align:center;margin-bottom:20px;"><h1 style="font-size:22px;margin:0;color:#FFD60A;">iMOs Activity Report</h1><p style="color:#8E8E93;margin:6px 0 0;font-size:14px;">{sfmt} &ndash; {efmt}</p></div>
    <div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:20px;">{cards_html}</div>
    {team_table}
    <p style="text-align:center;color:#6E6E73;font-size:11px;margin-top:24px;">Generated by iMOs &middot; {datetime.now(tz.utc).strftime('%b %d, %Y %I:%M %p UTC')}</p>
    </div>"""

    try:
        result = await asyncio.to_thread(resend_mod.Emails.send, {
            "from": f"iMOs Reports <{SENDER}>",
            "to": to_email,
            "subject": f"iMOs Activity Report | {sfmt} - {efmt}",
            "html": html,
        })
        return {"message": f"Report sent to {to_email}", "resend_id": result.get("id")}
    except Exception as e:
        logger.error(f"Report email failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
