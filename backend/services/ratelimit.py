"""Tiny in-process rate limiter for anonymous endpoints that cost money (public chat widget, help-center AI).
Fixed windows per key; good enough to stop a script from burning LLM budget, not a substitute for an edge WAF."""
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException, Request

_hits: Dict[str, Deque[float]] = defaultdict(deque)
_MAX_KEYS = 50_000


def client_ip(request: Request) -> str:
    h = request.headers
    return (h.get("cf-connecting-ip") or (h.get("x-forwarded-for") or "").split(",")[0].strip() or (request.client.host if request.client else "unknown")).strip()


def allow(key: str, limit: int, window_s: int, now: float | None = None) -> bool:
    now = now if now is not None else time.time()
    q = _hits[key]
    while q and q[0] <= now - window_s:
        q.popleft()
    if len(q) >= limit:
        return False
    q.append(now)
    if len(_hits) > _MAX_KEYS:
        for k in [k for k, v in _hits.items() if not v or v[-1] <= now - window_s][:1000]:
            _hits.pop(k, None)
    return True


def throttle(request: Request, bucket: str, per_minute: int, per_day: int) -> None:
    """429 when this client has exceeded either window for the bucket."""
    ip = client_ip(request)
    if not allow(f"{bucket}:m:{ip}", per_minute, 60) or not allow(f"{bucket}:d:{ip}", per_day, 86400):
        raise HTTPException(status_code=429, detail="Too many requests, please slow down")


def reset() -> None:
    _hits.clear()
