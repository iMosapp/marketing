"""Who mentioned X? Cross-contact search over everything a rep has on record: texts, call transcripts, voice memos, notes, sold records.
Two passes: a cheap keyword scan (query -> search variants -> regex over the rep's records) and one LLM read of the actual
snippets that keeps only people who meant it ("I'm looking for a Model 3 around 20k"), not passing mentions ("my neighbor's Tesla")."""
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

from bson import ObjectId

from services.scripts import _llm_json

logger = logging.getLogger(__name__)

MAX_HITS = 40
PER_CONTACT = 3
WINDOW = 140
SOURCES = {"text": "text", "call": "call transcript", "memo": "voice memo", "note": "note", "sale": "sold record"}


def _now():
    return datetime.now(timezone.utc)


def _when(v) -> Optional[datetime]:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, str):
        try:
            d = datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            return None
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    return None


def _fmt(d: Optional[datetime]) -> str:
    return d.strftime("%b %d, %Y") if d else ""


def _spoken_date(d: Optional[datetime]) -> str:
    if not d:
        return "a while back"
    days = (_now() - d).days
    if days < 1:
        return "today"
    if days < 2:
        return "yesterday"
    if days < 14:
        return f"{days} days ago"
    if days < 60:
        return f"{days // 7} weeks ago"
    if days < 365:
        return f"{max(1, round(days / 30))} months ago"
    return d.strftime("%B %Y")


async def terms_for(query: str) -> dict:
    """Turn the ask into search variants + what the rep is really after. LLM first (handles 20k -> twenty grand), word split as fallback."""
    q = (query or "").strip()
    words = [w for w in re.findall(r"[a-zA-Z0-9$][a-zA-Z0-9$,.'-]*", q.lower()) if len(w) > 2 and w not in STOP]
    fallback = {"topic": q, "terms": sorted(set(words))[:8]}
    if not q:
        return fallback
    try:
        data = await _llm_json(
            "A car sales rep is trying to find a customer by something that came up in past texts, calls or voice memos, or by what that customer bought (sold records: 'who did I sell a Tahoe to'). "
            "Turn the ask into keyword search variants that could literally appear in a transcript or a vehicle description: product names and their nicknames (Tesla Model 3 -> tesla, model 3; Chevy Tahoe -> tahoe), "
            "numbers the way people say and type them (20k -> 20k, 20,000, twenty thousand, twenty grand, 20 grand), and the key nouns. 4 to 10 short lowercase terms, "
            "no stop words, no generic words like car, customer, looking, sold, bought, no trim levels or drivetrain codes (LS, LT, 4x4). Also restate the TOPIC as the thing itself in 2 to 5 words (e.g. 'a 20k Tesla Model 3'), no time words, no 'inquiry'. Return ONLY JSON: {\"topic\": \"...\", \"terms\": [\"...\"]}",
            q, timeout=12)
        terms = [str(t).strip().lower() for t in (data.get("terms") or []) if str(t).strip()]
        terms = [t for t in dict.fromkeys(terms) if len(t) >= 3][:10]
        if terms:
            return {"topic": (data.get("topic") or q).strip(), "terms": terms}
    except Exception as e:
        logger.debug(f"[Mentions] term expansion failed: {e}")
    return fallback


STOP = {"the", "and", "who", "was", "were", "for", "about", "anyone", "someone", "customer", "looking", "asked", "mentioned", "talked", "find", "that", "with", "had", "have",
        "month", "ago", "week", "last", "did", "said", "wants", "want", "wanted", "into", "any", "all", "our", "you", "get", "got", "car", "one", "some", "like",
        "sold", "sell", "sale", "bought", "buy", "purchase", "purchased", "vehicle", "delivered", "year"}


def _regex(terms: list) -> re.Pattern:
    parts = [re.escape(t) for t in terms if t]
    return re.compile(r"(" + "|".join(parts) + r")", re.IGNORECASE) if parts else re.compile(r"$^")


def _snippet(text: str, rx: re.Pattern) -> Optional[str]:
    m = rx.search(text or "")
    if not m:
        return None
    a, b = max(0, m.start() - WINDOW), min(len(text), m.end() + WINDOW)
    s = re.sub(r"\s+", " ", text[a:b]).strip()
    return ("..." if a > 0 else "") + s + ("..." if b < len(text) else "")


async def _owners(db, user: dict) -> list:
    from routers.contacts import _dup_owners
    owners, _, _ = await _dup_owners(db, str(user["_id"]))
    return owners


async def scan(db, user: dict, terms: list, days: Optional[int] = None) -> list:
    """Keyword hits across texts, call transcripts, voice memos and notes. Newest first, at most PER_CONTACT per person."""
    rx = _regex(terms)
    owners = await _owners(db, user)
    since = _now() - timedelta(days=days) if days else None
    mongo_rx = {"$regex": "|".join(re.escape(t) for t in terms), "$options": "i"}
    hits = []

    q = {"user_id": {"$in": owners}, "sender": {"$in": ["contact", "user", "ai"]}, "content": mongo_rx}
    if since:
        q["timestamp"] = {"$gte": since}
    async for m in db.messages.find(q, {"content": 1, "conversation_id": 1, "sender": 1, "timestamp": 1}).sort("timestamp", -1).limit(400):
        snip = _snippet(m.get("content") or "", rx)
        if snip:
            hits.append({"source": "text", "conversation_id": m.get("conversation_id"), "contact_id": None, "who": "them" if m.get("sender") == "contact" else "me",
                         "when": _when(m.get("timestamp")), "quote": snip, "ref": str(m["_id"])})
    conv_ids = {h["conversation_id"] for h in hits if h.get("conversation_id") and ObjectId.is_valid(str(h["conversation_id"]))}
    if conv_ids:
        convs = {str(c["_id"]): c.get("contact_id") for c in await db.conversations.find({"_id": {"$in": [ObjectId(i) for i in conv_ids]}}, {"contact_id": 1}).to_list(len(conv_ids))}
        for h in hits:
            h["contact_id"] = convs.get(str(h.get("conversation_id")))

    q = {"user_id": {"$in": owners}, "transcript": mongo_rx}
    if since:
        q["created_at"] = {"$gte": since}
    async for c in db.call_logs.find(q, {"transcript": 1, "contact_id": 1, "created_at": 1, "timestamp": 1, "direction": 1}).sort("created_at", -1).limit(120):
        snip = _snippet(c.get("transcript") or "", rx)
        if snip:
            hits.append({"source": "call", "contact_id": c.get("contact_id"), "who": "call", "when": _when(c.get("created_at") or c.get("timestamp")), "quote": snip, "ref": str(c["_id"])})

    q = {"user_id": {"$in": owners}, "$or": [{"transcript": mongo_rx}, {"summary": mongo_rx}]}
    if since:
        q["created_at"] = {"$gte": since}
    async for v in db.voice_notes.find(q, {"transcript": 1, "summary": 1, "contact_id": 1, "created_at": 1, "kind": 1}).sort("created_at", -1).limit(120):
        snip = _snippet(v.get("transcript") or "", rx) or _snippet(v.get("summary") or "", rx)
        if snip:
            hits.append({"source": "memo", "contact_id": v.get("contact_id"), "who": "memo", "when": _when(v.get("created_at")), "quote": snip, "ref": str(v["_id"])})

    async for c in db.contacts.find({"user_id": {"$in": owners}, "status": {"$nin": ["merged", "deleted", "hidden"]}, "notes": mongo_rx}, {"notes": 1, "updated_at": 1}).limit(120):
        snip = _snippet(c.get("notes") or "", rx)
        if snip:
            hits.append({"source": "note", "contact_id": str(c["_id"]), "who": "note", "when": _when(c.get("updated_at")), "quote": snip, "ref": str(c["_id"])})

    hits.extend(await _sales(db, owners, rx, mongo_rx, since))

    hits = [h for h in hits if h.get("contact_id")]
    hits.sort(key=lambda h: h["when"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    per, out = {}, []
    for h in hits:
        n = per.get(h["contact_id"], 0)
        if n < PER_CONTACT:
            per[h["contact_id"]] = n + 1
            out.append(h)
        if len(out) >= MAX_HITS:
            break
    return out


async def _sales(db, owners: list, rx: re.Pattern, mongo_rx: dict, since: Optional[datetime]) -> list:
    """What each customer bought (purchase_history, the derived vehicle field) and the vehicle they said they want. 'Who did I sell a Tahoe to?'"""
    hits = []
    q = {"user_id": {"$in": owners}, "status": {"$nin": ["merged", "deleted", "hidden"]},
         "$or": [{"purchase_history": {"$elemMatch": {"$or": [{"title": mongo_rx}, {"notes": mongo_rx}, {"category": mongo_rx}]}}}, {"vehicle": mongo_rx}, {"vehicle_interest": mongo_rx}]}
    async for c in db.contacts.find(q, {"purchase_history": 1, "vehicle": 1, "vehicle_interest": 1, "date_sold": 1, "updated_at": 1}).limit(200):
        cid = str(c["_id"])
        found = False
        for e in c.get("purchase_history") or []:
            if not rx.search(" ".join(str(x) for x in (e.get("title"), e.get("category"), e.get("notes")) if x)):
                continue
            when = _when(e.get("date"))
            if since and when and when < since:
                continue
            quote = f"Sold: {e.get('title') or 'a purchase'}" + (f" on {_fmt(when)}" if when else "") + (f". {e['notes']}" if e.get("notes") else "")
            hits.append({"source": "sale", "contact_id": cid, "who": "sale", "when": when, "quote": quote, "ref": cid})
            found = True
        if not found and rx.search(c.get("vehicle") or ""):
            when = _when(c.get("date_sold")) or _when(c.get("updated_at"))
            if not (since and when and when < since):
                hits.append({"source": "sale", "contact_id": cid, "who": "sale", "when": when, "quote": f"Sold: {c['vehicle']}" + (f" on {_fmt(when)}" if c.get("date_sold") and when else ""), "ref": cid})
                found = True
        if not found and rx.search(c.get("vehicle_interest") or ""):
            hits.append({"source": "note", "contact_id": cid, "who": "note", "when": _when(c.get("updated_at")), "quote": f"Vehicle interest on file: {c['vehicle_interest']}", "ref": cid})
    return hits


async def verify(topic: str, query: str, hits: list) -> dict:
    """One LLM read of the snippets: which ones show the person actually meant this (asked, wants, is shopping), and a one-line why."""
    if not hits:
        return {}
    listing = "\n".join(f"[{i}] ({SOURCES[h['source']]}, {'the customer' if h['who'] == 'them' else 'me' if h['who'] == 'me' else h['who']}, {_fmt(h['when'])}) {h['quote']}" for i, h in enumerate(hits))
    try:
        data = await _llm_json(
            "You help a car sales rep find the customer they are thinking of. Given what the rep is looking for and numbered snippets from past texts, calls and memos, "
            "decide for each snippet whether it is a REAL match: the customer (or the rep about that customer) actually raised, wanted, asked about or shopped for the thing. "
            "A passing mention (someone else's car, a joke, the rep pitching it unprompted with no interest back) is not a match. "
            "A 'Sold:' snippet is the rep's own sold record (that customer bought that item from the rep): it is a strong match whenever the item fits the ask, "
            "including 'who did I sell a Tahoe to', 'who bought a Silverado', 'who has a Tahoe', or a plain product search. "
            "Return ONLY JSON: {\"matches\": [{\"i\": <index>, \"why\": \"<one short sentence quoting or paraphrasing what they said>\", \"strength\": \"strong|maybe\"}]}",
            f"LOOKING FOR: {query}\nTOPIC: {topic}\n\nSNIPPETS:\n{listing}", timeout=25)
        return {int(m["i"]): m for m in (data.get("matches") or []) if str(m.get("i", "")).isdigit() and int(m["i"]) < len(hits)}
    except Exception as e:
        logger.warning(f"[Mentions] verify failed, keeping keyword hits: {e}")
        return {i: {"why": h["quote"][:140], "strength": "maybe"} for i, h in enumerate(hits)}


async def search(db, user: dict, query: str, days: Optional[int] = None) -> dict:
    t = await terms_for(query)
    hits = await scan(db, user, t["terms"], days)
    keep = await verify(t["topic"], query, hits)
    by_contact = {}
    for i, h in enumerate(hits):
        m = keep.get(i)
        if not m:
            continue
        row = by_contact.setdefault(h["contact_id"], {"contact_id": h["contact_id"], "strength": "maybe", "hits": [], "when": None})
        row["hits"].append({"source": h["source"], "who": h["who"], "when": h["when"].isoformat() if h["when"] else None, "when_label": _fmt(h["when"]), "quote": h["quote"], "why": m.get("why") or "", "ref": h["ref"], "conversation_id": h.get("conversation_id"),
                            "strength": "strong" if m.get("strength") == "strong" else "maybe"})
        if m.get("strength") == "strong":
            row["strength"] = "strong"
        if h["when"] and (row["when"] is None or h["when"] > row["when"]):
            row["when"] = h["when"]
    ids = [ObjectId(c) for c in by_contact if ObjectId.is_valid(str(c))]
    people = {str(c["_id"]): c for c in await db.contacts.find({"_id": {"$in": ids}}, {"first_name": 1, "last_name": 1, "phone": 1, "vehicle": 1, "vehicle_interest": 1, "photo_thumbnail": 1, "status": 1}).to_list(len(ids))} if ids else {}
    results = []
    for cid, row in by_contact.items():
        c = people.get(cid)
        if not c or c.get("status") in ("merged", "deleted"):
            continue
        # Lead with the hard fact: strong matches first, a sold record before a text about it, then newest.
        row["hits"].sort(key=lambda h: (0 if h["strength"] == "strong" else 1, 0 if h["source"] == "sale" else 1, -(_when(h["when"]) or datetime.min.replace(tzinfo=timezone.utc)).timestamp()))
        best = row["hits"][0]
        results.append({**row, "when": row["when"].isoformat() if row["when"] else None, "when_label": _fmt(row["when"]), "when_spoken": _spoken_date(row["when"]),
                        "name": f"{c.get('first_name') or ''} {c.get('last_name') or ''}".strip(), "first": c.get("first_name") or "", "phone": c.get("phone") or "",
                        "vehicle": c.get("vehicle") or c.get("vehicle_interest") or "", "photo": c.get("photo_thumbnail"), "best": best})
    results.sort(key=lambda r: (0 if r["strength"] == "strong" else 1, -(_when(r["when"]) or datetime.min.replace(tzinfo=timezone.utc)).timestamp()))
    return {"query": query, "topic": t["topic"], "terms": t["terms"], "scanned": len(hits), "results": results}


def spoken(res: dict) -> str:
    """What Jessi says out loud."""
    rs = res.get("results") or []
    topic = res.get("topic") or res.get("query")
    if not rs:
        return f"Nobody on record mentioned {topic}. I checked your texts, call transcripts, voice memos, notes and sold records." + (" The closest keyword hits were not about that." if res.get("scanned") else "")
    lines = []
    for r in rs[:3]:
        b = r["best"]
        src = {"text": "texted", "call": "on a call", "memo": "in your voice memo", "note": "in your notes", "sale": "in your sold records"}[b["source"]]
        lines.append(f"{r['name']}, {src} {r['when_spoken']}: {b['why'] or b['quote']}")
    more = f" And {len(rs) - 3} more on the screen." if len(rs) > 3 else ""
    head = f"{len(rs)} {'person' if len(rs) == 1 else 'people'} mentioned {topic}. " if len(rs) > 1 else ""
    return head + " ".join(lines) + more + f" Want me to pull up {rs[0]['first'] or 'the first one'} or text them?"
