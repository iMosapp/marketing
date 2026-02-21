"""
Tasks router - handles task/reminder CRUD operations
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime
from typing import Optional
import logging

from models import Task, TaskCreate
from routers.database import get_db, get_data_filter

router = APIRouter(prefix="/tasks", tags=["Tasks"])
logger = logging.getLogger(__name__)

@router.post("/{user_id}", response_model=Task)
async def create_task(user_id: str, task_data: TaskCreate):
    """Create a task/reminder"""
    task_dict = task_data.dict()
    task_dict['user_id'] = user_id
    task_dict['created_at'] = datetime.utcnow()
    
    result = await get_db().tasks.insert_one(task_dict)
    task_dict['_id'] = result.inserted_id
    
    return Task(**task_dict)

@router.get("/{user_id}")
async def get_tasks(user_id: str, completed: Optional[bool] = None):
    """Get tasks with role-based access"""
    # Get role-based data filter
    base_filter = await get_data_filter(user_id)
    
    if completed is not None:
        query = {"$and": [base_filter, {"completed": completed}]}
    else:
        query = base_filter
    
    tasks = await get_db().tasks.find(query).sort("due_date", 1).to_list(1000)
    return [Task(**{**task, "_id": str(task["_id"])}) for task in tasks]

@router.put("/{user_id}/{task_id}")
async def update_task(user_id: str, task_id: str, task_data: dict):
    """Update a task with role-based access check"""
    # Get role-based data filter
    base_filter = await get_data_filter(user_id)
    
    # Only allow updating specific fields
    allowed_fields = ["completed", "title", "description", "due_date", "type", "priority"]
    update_dict = {k: v for k, v in task_data.items() if k in allowed_fields}
    update_dict["updated_at"] = datetime.utcnow()
    
    try:
        result = await get_db().tasks.update_one(
            {"$and": [{"_id": ObjectId(task_id)}, base_filter]},
            {"$set": update_dict}
        )
    except:
        result = await get_db().tasks.update_one(
            {"$and": [{"_id": task_id}, base_filter]},
            {"$set": update_dict}
        )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"message": "Task updated successfully"}

@router.delete("/{user_id}/{task_id}")
async def delete_task(user_id: str, task_id: str):
    """Delete a task with role-based access check"""
    # Get role-based data filter
    base_filter = await get_data_filter(user_id)
    
    try:
        result = await get_db().tasks.delete_one(
            {"$and": [{"_id": ObjectId(task_id)}, base_filter]}
        )
    except:
        result = await get_db().tasks.delete_one(
            {"$and": [{"_id": task_id}, base_filter]}
        )
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"message": "Task deleted successfully"}
