"""Executive Memory Lane: what each executive recommended, where they dissented and how the founder decided.
Built in code from lt_roundtables + lt_decisions; no model call, nothing written."""
from services import command_center as cc
from services import command_center_ai as ai
from services.leadership import core
from services.leadership import orchestrator as rt

PROJ = {"title": 1, "restated": 1, "status": 1, "participants": 1, "assessments": 1, "challenges": 1, "dissent": 1, "brief.recommended_decision": 1, "decision_id": 1, "created_at": 1}
BUCKET = {"approved": "approved", "rejected": "rejected", "deferred": "deferred", "pending": "pending", "modify_requested": "pending"}


def _zero() -> dict:
    return {"roundtables": 0, "dissents": 0, "open_dissents": 0, "devil_advocate": 0, "approved": 0, "rejected": 0, "deferred": 0, "pending": 0, "high_confidence": 0, "threads": 0, "last_at": None}


def _spoke(r: dict, key: str) -> bool:
    return ((r.get("assessments") or {}).get(key) or {}).get("status") == "ok"


def _mine(r: dict, key: str) -> list:
    out = []
    for d in r.get("dissent") or []:
        if key not in (d.get("executives") or []):
            continue
        pos = next((x.get("position") for x in d.get("positions") or [] if x.get("key") == key), "")
        out.append({"id": d["id"], "issue": d["issue"], "position": pos or "", "resolved": bool(d.get("resolved")), "needs_founder": bool(d.get("needs_founder")), "raised": (d.get("executives") or [""])[0] == key})
    return out


def _tally(s: dict, r: dict, key: str, dec: dict | None):
    p = next((p for p in r.get("participants") or [] if p["key"] == key), {})
    dis = _mine(r, key)
    s["roundtables"] += 1
    s["dissents"] += len(dis)
    s["open_dissents"] += len([d for d in dis if not d["resolved"]])
    s["devil_advocate"] += 1 if p.get("devil_advocate") else 0
    if (((r.get("assessments") or {}).get(key) or {}).get("data") or {}).get("confidence") == "high":
        s["high_confidence"] += 1
    if dec:
        s[BUCKET.get(dec.get("status"), "pending")] += 1
    at = cc._iso(r.get("created_at"))
    if at and (not s["last_at"] or at > s["last_at"]):
        s["last_at"] = at


def _entry(r: dict, key: str, dec: dict | None) -> dict:
    a = (((r.get("assessments") or {}).get(key) or {}).get("data")) or {}
    c = (((r.get("challenges") or {}).get(key) or {}).get("data")) or {}
    p = next((p for p in r.get("participants") or [] if p["key"] == key), {})
    pc = (c.get("position_change") or "").strip()
    if pc.lower().rstrip(".") in ("", "none", "no change") or pc.lower().startswith(("none", "no change")) and len(pc) < 40:
        pc = ""
    raised = [x for x in c.get("challenges") or [] if x.get("severity") == "material"]
    received = [x for k, v in (r.get("challenges") or {}).items() if v.get("status") == "ok" and k != key for x in (v.get("data") or {}).get("challenges") or [] if x.get("to") == key and x.get("severity") == "material"]
    founder = (dec or {}).get("founder") or {}
    return {"roundtable_id": str(r["_id"]), "title": r.get("title"), "restated": r.get("restated"), "status": r["status"], "at": cc._iso(r.get("created_at")), "devil_advocate": bool(p.get("devil_advocate")),
            "position": a.get("recommendation") or "", "confidence": a.get("confidence") or "low", "position_change": pc, "challenges_raised": len(raised), "challenged_on": len(received), "dissents": _mine(r, key),
            "brief_recommendation": ((r.get("brief") or {}).get("recommended_decision")) or "",
            "decision": {"status": dec.get("status"), "action": founder.get("action"), "reason": founder.get("reason") or "", "at": cc._iso(founder.get("at"))} if dec else None}


async def _rows(db, company_id: str) -> tuple:
    rows = await db[rt.RT].find({"company_id": company_id, "status": {"$ne": "selected"}}, PROJ).sort("created_at", -1).to_list(500)
    ids = [cc._oid(r["decision_id"]) for r in rows if r.get("decision_id")]
    decs = {str(d["_id"]): d async for d in db[rt.DECISIONS].find({"_id": {"$in": ids}}, {"status": 1, "founder": 1})} if ids else {}
    return rows, decs


async def _threads(db, company_id: str) -> dict:
    agg = db[ai.CONVOS].aggregate([{"$match": {**core.scope(company_id), "agent_keys": {"$exists": True}}}, {"$unwind": "$agent_keys"}, {"$group": {"_id": "$agent_keys", "n": {"$sum": 1}}}])
    return {r["_id"]: r["n"] async for r in agg}


async def counts(db, company_id: str) -> dict:
    """Per executive summary for the roster tiles: one pass over the roundtables."""
    rows, decs = await _rows(db, company_id)
    out: dict = {}
    for r in rows:
        dec = decs.get(str(r.get("decision_id") or ""))
        for p in r.get("participants") or []:
            if _spoke(r, p["key"]):
                _tally(out.setdefault(p["key"], _zero()), r, p["key"], dec)
    for k, n in (await _threads(db, company_id)).items():
        out.setdefault(k, _zero())["threads"] = n
    return out


async def memory(db, company_id: str, key: str, limit: int = 30) -> dict:
    rows, decs = await _rows(db, company_id)
    s, entries = _zero(), []
    for r in rows:
        if not _spoke(r, key):
            continue
        dec = decs.get(str(r.get("decision_id") or ""))
        _tally(s, r, key, dec)
        if len(entries) < limit:
            entries.append(_entry(r, key, dec))
    s["threads"] = (await _threads(db, company_id)).get(key, 0)
    return {"executive": key, "summary": s, "entries": entries}
