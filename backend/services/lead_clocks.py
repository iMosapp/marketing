"""Stop-the-clock timers for internet leads.

For each lead (conversation) we find, relative to when the lead arrived:
  first_call_at        first outbound call to the customer (in-app call, recorded Twilio call, or press-1 bridge)
  first_human_text_at  first text typed by a rep (not automated)
  first_ai_text_at     first text Jessi sent (intake text or AI reply)
  first_customer_reply_at  first inbound text after the first outbound touch, only when a text was sent
"""
from datetime import datetime, timezone, timedelta
from typing import Optional
from bson import ObjectId


def _utc(v) -> Optional[datetime]:
    if isinstance(v, str):
        try:
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception:
            return None
    if not isinstance(v, datetime):
        return None
    return v if v.tzinfo else v.replace(tzinfo=timezone.utc)


def _secs(start, end) -> Optional[int]:
    a, b = _utc(start), _utc(end)
    if a is None or b is None:
        return None
    return max(0, int((b - a).total_seconds()))


def _median(vals: list) -> Optional[int]:
    if not vals:
        return None
    s = sorted(vals)
    return int(s[len(s) // 2])


async def clocks_for_leads(db, leads: list) -> dict:
    """Batch: {conversation_id: {received_at, first_call_at, first_human_text_at, first_human_rep, first_ai_text_at,
    first_outbound_at, texted, first_customer_reply_at, call_secs, human_secs, ai_secs, reply_secs}}"""
    leads = [l for l in leads if l.get("conversation_id")]
    if not leads:
        return {}
    conv_ids = [l["conversation_id"] for l in leads]
    contact_ids = [str(l["contact_id"]) for l in leads if l.get("contact_id")]
    earliest = min((_utc(l.get("received_at")) for l in leads if _utc(l.get("received_at"))), default=None)
    floor = (earliest - timedelta(minutes=5)) if earliest else None

    # texts: first ai, first human, all inbound timestamps
    pipeline = [
        {"$match": {"conversation_id": {"$in": conv_ids}, "sender": {"$in": ["ai", "user", "contact"]}}},
        {"$addFields": {"_ts": {"$ifNull": ["$timestamp", "$created_at"]}}},
        {"$match": {"_ts": {"$ne": None}}},
        {"$sort": {"_ts": 1}},
        {"$group": {
            "_id": "$conversation_id",
            "ai_first": {"$min": {"$cond": [{"$and": [{"$eq": ["$sender", "ai"]}, {"$ne": ["$direction", "inbound"]}]}, "$_ts", None]}},
            "human_first": {"$min": {"$cond": [{"$and": [{"$eq": ["$sender", "user"]}, {"$ne": ["$direction", "inbound"]}, {"$ne": ["$auto_sent", True]}]}, "$_ts", None]}},
            "human_rows": {"$push": {"$cond": [{"$and": [{"$eq": ["$sender", "user"]}, {"$ne": ["$direction", "inbound"]}, {"$ne": ["$auto_sent", True]}]},
                                               {"ts": "$_ts", "rep": {"$ifNull": ["$user_id", "$sender_id"]}}, None]}},
            "inbound": {"$push": {"$cond": [{"$or": [{"$eq": ["$sender", "contact"]}, {"$eq": ["$direction", "inbound"]}]}, "$_ts", None]}},
            "out_count": {"$sum": {"$cond": [{"$and": [{"$in": ["$sender", ["ai", "user"]]}, {"$ne": ["$direction", "inbound"]}]}, 1, 0]}},
        }},
    ]
    texts = {}
    async for row in db.messages.aggregate(pipeline):
        texts[row["_id"]] = row

    # calls to the customer, by contact
    calls: dict = {}
    if contact_ids:
        cq = {"contact_id": {"$in": contact_ids}, "type": {"$in": ["outbound", "completed", "answered"]}}
        if floor:
            cq["timestamp"] = {"$gte": floor.replace(tzinfo=None)}
        async for row in db.calls.aggregate([{"$match": cq}, {"$group": {"_id": "$contact_id", "first": {"$min": "$timestamp"}, "user_id": {"$first": "$user_id"}, "n": {"$sum": 1}}}]):
            calls[row["_id"]] = row
        lq = {"contact_id": {"$in": contact_ids}, "direction": {"$ne": "inbound"}}
        if floor:
            lq["timestamp"] = {"$gte": floor.replace(tzinfo=None)}
        async for row in db.call_logs.aggregate([{"$match": lq}, {"$group": {"_id": "$contact_id", "first": {"$min": "$timestamp"}, "user_id": {"$first": "$user_id"}, "n": {"$sum": 1}}}]):
            prev = calls.get(row["_id"])
            if prev:
                prev["n"] = max(prev.get("n", 0), row.get("n", 0))
            if not prev or (_utc(row["first"]) or datetime.max.replace(tzinfo=timezone.utc)) < (_utc(prev["first"]) or datetime.max.replace(tzinfo=timezone.utc)):
                calls[row["_id"]] = row
    bridged: dict = {}
    async for job in db.lead_call_jobs.find({"conversation_id": {"$in": conv_ids}, "claimed_via": "press_1", "claimed_at": {"$ne": None}},
                                            {"conversation_id": 1, "claimed_at": 1, "claimed_by": 1}):
        bridged[job["conversation_id"]] = job

    out = {}
    for l in leads:
        cid = l["conversation_id"]
        received = _utc(l.get("received_at")) or _utc(l.get("created_at"))
        t = texts.get(cid, {})
        c = calls.get(str(l.get("contact_id") or ""))
        b = bridged.get(cid)
        first_call = None
        call_rep = None
        for cand, rep in ((_utc((c or {}).get("first")), (c or {}).get("user_id")), (_utc((b or {}).get("claimed_at")), (b or {}).get("claimed_by"))):
            if cand and (received is None or cand >= received - timedelta(minutes=5)) and (first_call is None or cand < first_call):
                first_call, call_rep = cand, rep
        ai_first = _utc(t.get("ai_first"))
        human_first = _utc(t.get("human_first"))
        human_rep = next((r.get("rep") for r in sorted((r for r in t.get("human_rows", []) if r), key=lambda r: r["ts"]) if r.get("rep")), None)
        text_first = min((x for x in (ai_first, human_first) if x), default=None)
        outbound_first = min((x for x in (ai_first, human_first, first_call) if x), default=None)
        reply = None
        if text_first:
            reply = min((x for x in (_utc(v) for v in t.get("inbound", []) if v) if x and x > outbound_first), default=None)
        out[cid] = {
            "received_at": received,
            "first_call_at": first_call, "call_rep": str(call_rep) if call_rep else None,
            "first_human_text_at": human_first, "human_rep": str(human_rep) if human_rep else None,
            "first_ai_text_at": ai_first,
            "first_outbound_at": outbound_first,
            "texted": text_first is not None,
            "first_customer_reply_at": reply,
            "call_secs": _secs(received, first_call), "human_secs": _secs(received, human_first),
            "ai_secs": _secs(received, ai_first), "reply_secs": _secs(outbound_first, reply) if reply else None,
            "assigned_to": str(l.get("assigned_to")) if l.get("assigned_to") else None,
            "outbound_texts": int(t.get("out_count") or 0),
            "inbound_texts": len([v for v in t.get("inbound", []) if v]),
            "calls": int((c or {}).get("n") or 0) + (1 if b else 0),
            "contact_id": str(l.get("contact_id") or ""),
        }
    return out


def summarize_clocks(rows: list) -> dict:
    """Team-level aggregates over per-lead clock rows."""
    def agg(key):
        vals = [r[key] for r in rows if r.get(key) is not None]
        return {"measured": len(vals), "avg_seconds": int(sum(vals) / len(vals)) if vals else None,
                "median_seconds": _median(vals), "fastest_seconds": min(vals) if vals else None}
    texted = [r for r in rows if r.get("texted")]
    replied = [r for r in texted if r.get("reply_secs") is not None]
    reply_vals = [r["reply_secs"] for r in replied]
    return {
        "leads": len(rows),
        "clocks": {"call": agg("call_secs"), "human_text": agg("human_secs"), "ai_text": agg("ai_secs")},
        "customer": {
            "texted": len(texted), "replied": len(replied),
            "reply_rate": int(round(100 * len(replied) / len(texted))) if texted else None,
            "avg_seconds": int(sum(reply_vals) / len(reply_vals)) if reply_vals else None,
            "median_seconds": _median(reply_vals),
        },
    }


async def clocks_for_conversation(db, conversation_id: str) -> Optional[dict]:
    lead = await db.inbound_leads.find_one({"conversation_id": conversation_id}, {"conversation_id": 1, "contact_id": 1, "received_at": 1, "created_at": 1, "assigned_to": 1})
    if not lead:
        conv = await db.conversations.find_one({"_id": ObjectId(conversation_id)}, {"contact_id": 1, "created_at": 1}) if ObjectId.is_valid(conversation_id) else None
        if not conv:
            return None
        lead = {"conversation_id": conversation_id, "contact_id": conv.get("contact_id"), "received_at": conv.get("created_at")}
    rows = await clocks_for_leads(db, [lead])
    r = rows.get(conversation_id)
    if not r:
        return None
    iso = lambda v: v.isoformat() if isinstance(v, datetime) else None
    return {
        "first_call_at": iso(r["first_call_at"]), "first_human_text_at": iso(r["first_human_text_at"]),
        "first_ai_text_at": iso(r["first_ai_text_at"]), "first_customer_reply_at": iso(r["first_customer_reply_at"]),
        "call_secs": r["call_secs"], "human_secs": r["human_secs"], "ai_secs": r["ai_secs"], "reply_secs": r["reply_secs"],
        "texted": r["texted"],
    }
