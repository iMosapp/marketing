"""
Database connection and shared utilities for all routers.
Uses FastAPI dependency injection pattern.
"""
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from typing import List
import os
import logging

logger = logging.getLogger(__name__)

# MongoDB connection - lazy initialization
_client = None
_db = None

def get_db():
    """Get database instance - lazy initialization"""
    global _client, _db
    if _db is None:
        mongo_url = os.environ.get('MONGO_URL')
        db_name = os.environ.get('DB_NAME')
        if mongo_url:
            _client = AsyncIOMotorClient(
                mongo_url,
                serverSelectionTimeoutMS=30000,
                connectTimeoutMS=30000,
            )
            # Try to get database name from the MONGO_URL path first
            # (e.g. mongodb+srv://user:pass@host/my_database)
            try:
                default_db = _client.get_default_database()
                _db = default_db
                logger.info(f"Database connected (from URL): {default_db.name}")
            except Exception:
                if db_name:
                    _db = _client[db_name]
                    logger.info(f"Database connected (from DB_NAME): {db_name}")
                else:
                    logger.error("No database name in MONGO_URL or DB_NAME")
        else:
            logger.error("MONGO_URL not found in environment")
    return _db

# ============= ROLE-BASED ACCESS HELPERS =============
async def get_user_by_id(user_id: str) -> dict:
    """Get user by ID, returns None if not found"""
    db = get_db()
    if db is None:
        return None
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if user:
            user['_id'] = str(user['_id'])
        return user
    except:
        return None

async def get_accessible_user_ids(user: dict) -> List[str]:
    """Get list of user IDs that this user can access based on role"""
    db = get_db()
    if db is None:
        return []
    
    role = user.get('role', 'user')
    user_id = str(user.get('_id'))
    
    if role == 'super_admin':
        # Super admin can see all users
        all_users = await db.users.find({}, {"_id": 1}).to_list(10000)
        return [str(u['_id']) for u in all_users]
    
    elif role == 'org_admin':
        # Org admin can see all users in their organization
        org_id = user.get('organization_id')
        if not org_id:
            return [user_id]
        org_users = await db.users.find({"organization_id": org_id}, {"_id": 1}).to_list(10000)
        return [str(u['_id']) for u in org_users]
    
    elif role == 'store_manager':
        # Store manager can see all users in their store
        store_id = user.get('store_id')
        if not store_id:
            return [user_id]
        store_users = await db.users.find({"store_id": store_id}, {"_id": 1}).to_list(10000)
        return [str(u['_id']) for u in store_users]
    
    else:
        # Regular user can only see their own data
        return [user_id]

async def get_data_filter(user_id: str) -> dict:
    """
    Returns a MongoDB query filter for data access based on user role.
    This is the CORE function for role-based data filtering.
    
    - super_admin: {} (all data)
    - org_admin: {"user_id": {"$in": [all users in org]}}
    - store_manager: {"user_id": {"$in": [all users in store]}}
    - user: {"user_id": user_id}
    """
    user = await get_user_by_id(user_id)
    if not user:
        # If user not found, return filter that matches nothing
        return {"user_id": "__NONE__"}
    
    accessible_ids = await get_accessible_user_ids(user)
    
    # For regular users, return simple filter
    if len(accessible_ids) == 1 and accessible_ids[0] == user_id:
        return {"user_id": user_id}
    
    # For admins/managers, return $in filter
    return {"user_id": {"$in": accessible_ids}}

async def verify_user_access(requesting_user_id: str, target_user_id: str) -> bool:
    """
    Verify that requesting_user can access data for target_user.
    Returns True if access is allowed, False otherwise.
    """
    user = await get_user_by_id(requesting_user_id)
    if not user:
        return False
    
    accessible_ids = await get_accessible_user_ids(user)
    return target_user_id in accessible_ids

async def increment_user_stat(user_id: str, stat_name: str, amount: int = 1):
    """Increment a user's stat for leaderboard tracking"""
    db = get_db()
    if db is None:
        return
    try:
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$inc": {f"stats.{stat_name}": amount}}
        )
    except Exception as e:
        logger.error(f"Failed to increment stat {stat_name} for user {user_id}: {e}")
