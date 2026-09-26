"""Voicemail inbox for the Call tab: what was left on my line(s); super admins see every line."""
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from routers.database import get_db
from routers.scripts import require_user
from services import voicemails as vm

router = APIRouter(prefix="/voicemails", tags=["Voicemails"], dependencies=[Depends(require_user)])


@router.get("")
async def list_voicemails(request: Request, line: Optional[str] = None, limit: int = 100):
    me = await require_user(request)
    return await vm.list_for(get_db(), me, line=line, limit=max(1, min(limit, 300)))


@router.get("/unheard-count")
async def unheard(request: Request):
    me = await require_user(request)
    return {"unheard": await vm.unheard_count(get_db(), me)}


@router.get("/greeting")
async def greeting(request: Request):
    me = await require_user(request)
    return await vm.greeting_status(get_db(), me)


@router.post("/greeting")
async def upload_greeting(request: Request, file: UploadFile = File(...)):
    """The message callers hear when this rep does not pick up. Any recording format; stored as mp3 for Twilio <Play>."""
    me = await require_user(request)
    raw = await file.read()
    if not raw or len(raw) < 1000:
        raise HTTPException(status_code=400, detail="That recording is empty. Try again.")
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Recording too large")
    try:
        return await vm.save_greeting(get_db(), me, raw, file.filename or "greeting.m4a")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not process that recording: {e}")


@router.delete("/greeting")
async def remove_greeting(request: Request):
    me = await require_user(request)
    return await vm.delete_greeting(get_db(), me)


@router.post("/{vm_id}/heard")
async def heard(vm_id: str, request: Request):
    me = await require_user(request)
    if not ObjectId.is_valid(vm_id):
        raise HTTPException(status_code=404, detail="Not found")
    await vm.mark_heard(get_db(), me, vm_id)
    return {"ok": True, "unheard": await vm.unheard_count(get_db(), me)}


@router.delete("/{vm_id}")
async def delete(vm_id: str, request: Request):
    me = await require_user(request)
    if not ObjectId.is_valid(vm_id) or not await vm.soft_delete(get_db(), me, vm_id):
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True, "unheard": await vm.unheard_count(get_db(), me)}
