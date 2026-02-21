"""
MVPLine API Server - Main entry point
Refactored to use modular routers for maintainability
"""
from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from bson import ObjectId
import os
import logging
from pathlib import Path
from datetime import datetime

# Load environment first
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Import routers (after env is loaded)
from routers import auth, contacts, tasks, messages, calls, campaigns, admin, leaderboard
from routers.database import get_db

# Create the main app
app = FastAPI(title="MVPLine API", version="2.0")

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
    return {"message": "MVPLine API", "version": "2.0"}

# ============= INCLUDE ROUTERS =============
api_router.include_router(auth.router)
api_router.include_router(contacts.router)
api_router.include_router(tasks.router)
api_router.include_router(messages.router)
api_router.include_router(calls.router)
api_router.include_router(campaigns.router)
api_router.include_router(admin.router)
api_router.include_router(leaderboard.router)

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

# Include the api_router in the main app
app.include_router(api_router)

# ============= STARTUP EVENT =============
@app.on_event("startup")
async def startup_event():
    # Initialize database connection
    db = get_db()
    if db:
        logger.info("MVPLine API v2.0 started")
        logger.info(f"Connected to MongoDB: {os.environ.get('DB_NAME', 'unknown')}")
    else:
        logger.error("Failed to connect to MongoDB!")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
