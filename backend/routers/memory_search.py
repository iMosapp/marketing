"""Who mentioned X: cross-contact search over texts, call transcripts, voice memos and notes."""
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from routers.contact_ask import require_user
from routers.database import get_db
from services import memory_search as ms

router = APIRouter(prefix="/memory", tags=["Who mentioned"], dependencies=[Depends(require_user)])


class SearchBody(BaseModel):
    query: str
    days: Optional[int] = None


@router.post("/search")
async def search(body: SearchBody, request: Request):
    q = (body.query or "").strip()
    if len(q) < 2:
        return {"query": q, "topic": q, "terms": [], "scanned": 0, "results": []}
    return await ms.search(get_db(), request.state.user, q[:300], body.days if body.days and body.days > 0 else None)
