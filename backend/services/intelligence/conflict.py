"""Conflict resolution between a new fact and what is currently believed for the same key.
Order of evaluation (per the spec): can both be true? -> same statement? -> event date -> verification -> source reliability -> confidence. Recency alone never decides."""
from typing import Callable, Optional

HUMAN = ("message", "call", "lead_form", "appointment", "rep", "voice_memo", "sale")


def _norm(v):
    from services.intelligence.facts import norm_value
    return norm_value(v)


def resolve(new: dict, currents: list, scalar_keys: set, reliability: dict, is_weak: Callable[[dict], bool]) -> tuple[str, Optional[dict]]:
    """Returns (kind, target). kinds: create | reaffirm | coexist | older | supersede | dispute."""
    if not currents:
        return "create", None
    same = [c for c in currents if _norm(c.get("value")) == _norm(new.get("value")) or (new.get("value") is None and _norm(c.get("statement")) == _norm(new.get("statement")))]
    if same:
        return "reaffirm", same[0]
    if new["key"] not in scalar_keys:
        return "coexist", None
    cur = currents[0]  # newest current by occurred_at
    if new["occurred_at"] < cur["occurred_at"]:
        return "older", cur
    cur_human = bool(cur.get("confirmed_by")) or (cur.get("source") or {}).get("kind") in HUMAN
    if is_weak(new) and cur_human:
        return "dispute", cur
    r_new = reliability.get((new.get("source") or {}).get("kind"), 1)
    r_cur = reliability.get((cur.get("source") or {}).get("kind"), 1)
    if r_new >= r_cur and new.get("confidence") in ("medium", "high"):
        return "supersede", cur
    return "dispute", cur
