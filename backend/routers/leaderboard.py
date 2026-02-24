"""
Leaderboard router - handles organization and regional leaderboards
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from typing import Optional
import logging

from routers.database import get_db, get_user_by_id

router = APIRouter(prefix="/leaderboard", tags=["Leaderboard"])
logger = logging.getLogger(__name__)

# US Region mapping for regional leaderboards
US_REGIONS = {
    'Northeast': ['CT', 'ME', 'MA', 'NH', 'RI', 'VT', 'NJ', 'NY', 'PA'],
    'Southeast': ['AL', 'AR', 'FL', 'GA', 'KY', 'LA', 'MS', 'NC', 'SC', 'TN', 'VA', 'WV'],
    'Midwest': ['IL', 'IN', 'IA', 'KS', 'MI', 'MN', 'MO', 'NE', 'ND', 'OH', 'SD', 'WI'],
    'Southwest': ['AZ', 'NM', 'OK', 'TX'],
    'West': ['AK', 'CA', 'CO', 'HI', 'ID', 'MT', 'NV', 'OR', 'UT', 'WA', 'WY']
}

def get_region_for_state(state: str) -> str:
    """Get the region for a given state code"""
    for region, states in US_REGIONS.items():
        if state in states:
            return region
    return 'Unknown'

@router.get("/organization")
async def get_organization_leaderboard(
    org_id: str,
    store_id: Optional[str] = None,
    metric: str = "contacts_added"
):
    """Get leaderboard for an organization"""
    query = {"organization_id": org_id}
    if store_id:
        query["store_id"] = store_id
    
    # Get users in org/store
    users = await get_db().users.find(query, {"password": 0}).limit(500).to_list(500)
    
    # Sort by metric
    metric_key = f"stats.{metric}"
    sorted_users = sorted(
        users,
        key=lambda u: u.get('stats', {}).get(metric, 0),
        reverse=True
    )
    
    # Build leaderboard
    leaderboard = []
    for i, user in enumerate(sorted_users):
        leaderboard.append({
            "rank": i + 1,
            "user_id": str(user['_id']),
            "name": user.get('name', 'Unknown'),
            "metric_value": user.get('stats', {}).get(metric, 0),
            "store_id": user.get('store_id')
        })
    
    return {
        "organization_id": org_id,
        "store_id": store_id,
        "metric": metric,
        "leaderboard": leaderboard
    }

@router.get("/regional")
async def get_regional_leaderboard(
    user_id: str,
    scope: str = "state",  # state, region, country
    metric: str = "contacts_added"
):
    """Get regional leaderboard for independents"""
    # Get requesting user
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_state = user.get('state', '')
    user_region = get_region_for_state(user_state)
    
    # Build query based on scope
    query = {
        "organization_id": {"$exists": False},  # Only independents
        "settings.leaderboard_visible": True
    }
    
    if scope == "state" and user_state:
        query["state"] = user_state
    elif scope == "region" and user_region != 'Unknown':
        region_states = US_REGIONS.get(user_region, [])
        query["state"] = {"$in": region_states}
    # For 'country', no additional filter
    
    # Get users matching criteria
    users = await get_db().users.find(query, {"password": 0}).limit(500).to_list(500)
    
    # Add current user if not in list (to show their rank)
    user_in_list = any(str(u['_id']) == user_id for u in users)
    if not user_in_list and user.get('settings', {}).get('leaderboard_visible', False):
        users.append(user)
    
    # Sort by metric
    sorted_users = sorted(
        users,
        key=lambda u: u.get('stats', {}).get(metric, 0),
        reverse=True
    )
    
    # Build leaderboard and find user rank
    leaderboard = []
    user_rank = None
    for i, u in enumerate(sorted_users):
        is_current_user = str(u['_id']) == user_id
        if is_current_user:
            user_rank = i + 1
        
        leaderboard.append({
            "rank": i + 1,
            "user_id": str(u['_id']),
            "name": u.get('name', 'Unknown'),
            "photo_url": u.get('photo_url'),
            "metric_value": u.get('stats', {}).get(metric, 0),
            "state": u.get('state', ''),
            "is_you": is_current_user
        })
    
    return {
        "scope": scope,
        "metric": metric,
        "user_rank": user_rank,
        "total_in_scope": len(leaderboard),
        "user_state": user_state,
        "user_region": user_region,
        "leaderboard": leaderboard[:50]  # Limit to top 50
    }


# ============= USER LEADERBOARD SETTINGS =============
# These are under /users prefix in the main app, but logically belong here
# They're registered separately in server.py
