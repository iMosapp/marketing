"""
Reports Router - Unified reporting with org/store/user level permissions
"""
from fastapi import APIRouter, HTTPException, Header, Query
from datetime import datetime, timedelta
from bson import ObjectId
from typing import Optional
import logging

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
