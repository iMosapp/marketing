"""Serve rendered promo videos with HTTP Range support (iOS Safari refuses mp4 without 206)."""
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response

router = APIRouter(prefix="/promo-videos", tags=["marketing"])
VIDEO_DIR = Path("/app/marketing/build-preview/videos")
CHUNK = 1024 * 1024


@router.get("/", response_class=HTMLResponse)
async def promo_index():
    index = VIDEO_DIR / "index.html"
    if not index.exists():
        raise HTTPException(404)
    return index.read_text()


@router.get("/{filename}")
async def promo_video(filename: str, request: Request):
    if not re.fullmatch(r"[a-z0-9\-]+\.(mp4|mp3)", filename):
        raise HTTPException(404)
    path = VIDEO_DIR / filename
    if not path.exists():
        raise HTTPException(404)
    size = path.stat().st_size
    rng = request.headers.get("range")
    if not rng:
        return FileResponse(path, media_type=("audio/mpeg" if filename.endswith(".mp3") else "video/mp4"), headers={"Accept-Ranges": "bytes"})
    m = re.fullmatch(r"bytes=(\d*)-(\d*)", rng.strip())
    if not m:
        raise HTTPException(416)
    start = int(m.group(1)) if m.group(1) else 0
    end = int(m.group(2)) if m.group(2) else min(start + CHUNK * 4, size - 1)
    end = min(end, size - 1)
    if start > end or start >= size:
        raise HTTPException(416, headers={"Content-Range": f"bytes */{size}"})
    with open(path, "rb") as f:
        f.seek(start)
        data = f.read(end - start + 1)
    return Response(
        content=data, status_code=206, media_type=("audio/mpeg" if filename.endswith(".mp3") else "video/mp4"),
        headers={"Content-Range": f"bytes {start}-{end}/{size}", "Accept-Ranges": "bytes",
                 "Content-Length": str(len(data)), "Cache-Control": "public, max-age=3600"},
    )
