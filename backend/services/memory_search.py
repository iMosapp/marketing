"""Who mentioned X? Cross-contact search over everything a rep has on record: texts, call transcripts, voice memos, notes, sold records.
Two passes: a cheap keyword scan (query -> search variants -> regex over the rep's records) and one LLM read of the actual
snippets that keeps only people who meant it ("I'm looking for a Model 3 around 20k"), not passing mentions ("my neighbor's Tesla")."""
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

from bson import ObjectId

from services.scripts import _llm_json
from services import date_window as dw

logger = logging.getLogger(__name__)

MAX_HITS = 150
PER_CONTACT = 3
WINDOW = 140
SOURCES = {"text": "text", "call": "call transcript", "memo": "voice memo", "note": "note", "sale": "sold record", "tag": "tag", "file": "file or photo",
           "fact": "saved detail", "met": "how you met", "unfiled": "voice memo not filed yet"}
LIVE = {"status": {"$nin": ["merged", "deleted", "hidden"]}}
# Words that carry no topic once the time frame is gone: "people I met in October", "memos from last week".
LISTING = {"met", "meet", "meeting", "guy", "guys", "girl", "lady", "person", "folks", "talk", "talked", "spoke", "spoken", "memo", "memos",
           "voice", "note", "notes", "recorded", "record", "from", "what", "whom", "new", "added", "add", "them"}
MET = re.compile(r"\b(met|meet|meeting|added|new contacts?|new people)\b", re.IGNORECASE)


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
            "A car sales rep is trying to find a customer by something that came up in past texts, calls or voice memos, by what that customer bought (sold records: 'who did I sell a Tahoe to'), "
            "or by a tag the rep put on people ('who are my Harley riders', 'everyone tagged VIP', 'who do I have as first-time buyers'). "
            "Turn the ask into keyword search variants that could literally appear in a transcript, a vehicle description or a tag name: product names and their nicknames (Tesla Model 3 -> tesla, model 3; Chevy Tahoe -> tahoe; Harley riders -> harley, harley-davidson, rider, motorcycle), "
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
        "sold", "sell", "sale", "bought", "buy", "purchase", "purchased", "vehicle", "delivered", "year",
        "tagged", "tag", "tags", "people", "everyone", "everybody", "anybody", "list", "show", "pull", "which", "customers", "contacts", "many"}


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


def _range(since: Optional[datetime], until: Optional[datetime]) -> dict:
    r = {}
    if since:
        r["$gte"] = since
    if until:
        r["$lt"] = until
    return r


def _flat(pd: dict) -> list:
    """personal_details as 'kids: Emma, Jake' lines (lists of {name: ...} read as names)."""
    out = []
    for k, v in (pd or {}).items():
        if isinstance(v, list):
            v = ", ".join(str(x.get("name") or x.get("value") or "") if isinstance(x, dict) else str(x) for x in v)
        elif isinstance(v, dict):
            v = ", ".join(f"{a}: {b}" for a, b in v.items() if b)
        if v:
            out.append(f"{k.replace('_', ' ')}: {v}")
    return out


async def scan(db, user: dict, terms: list, days: Optional[int] = None, window: Optional[dict] = None) -> list:
    """Keyword hits across texts, call transcripts, voice memos, notes and saved details. Newest first, at most PER_CONTACT per person.
    window ({start, end}) bounds every DATED record; undated ones (notes, tags, personal details, How we met without a date) still count, as with days."""
    rx = _regex(terms)
    owners = await _owners(db, user)
    since = window["start"] if window else (_now() - timedelta(days=days) if days else None)
    until = window["end"] if window else None
    rng = _range(since, until)
    mongo_rx = {"$regex": "|".join(re.escape(t) for t in terms), "$options": "i"}
    hits = []

    q = {"user_id": {"$in": owners}, "sender": {"$in": ["contact", "user", "ai"]}, "content": mongo_rx}
    if rng:
        q["timestamp"] = rng
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
    if rng:
        q["created_at"] = rng
    async for c in db.call_logs.find(q, {"transcript": 1, "contact_id": 1, "created_at": 1, "timestamp": 1, "direction": 1}).sort("created_at", -1).limit(120):
        snip = _snippet(c.get("transcript") or "", rx)
        if snip:
            hits.append({"source": "call", "contact_id": c.get("contact_id"), "who": "call", "when": _when(c.get("created_at") or c.get("timestamp")), "quote": snip, "ref": str(c["_id"])})

    # memos by the contacts the rep can see (not by who recorded them), so a reassigned customer brings their memos along
    cid_oids = await db.contacts.distinct("_id", {"user_id": {"$in": owners}, **LIVE})
    cids = [str(i) for i in cid_oids]
    q = {"contact_id": {"$in": cids}, "$or": [{"transcript": mongo_rx}, {"summary": mongo_rx}]}
    if rng:
        q["created_at"] = rng
    async for v in db.voice_notes.find(q, {"transcript": 1, "summary": 1, "contact_id": 1, "created_at": 1, "kind": 1}).sort("created_at", -1).limit(120):
        snip = _snippet(v.get("transcript") or "", rx) or _snippet(v.get("summary") or "", rx)
        if snip:
            hits.append({"source": "memo", "contact_id": v.get("contact_id"), "who": "memo", "when": _when(v.get("created_at")), "quote": snip, "ref": str(v["_id"])})

    async for c in db.contacts.find({"user_id": {"$in": owners}, **LIVE, "notes": mongo_rx}, {"notes": 1, "updated_at": 1}).limit(120):
        snip = _snippet(c.get("notes") or "", rx)
        if snip:
            hits.append({"source": "note", "contact_id": str(c["_id"]), "who": "note", "when": _when(c.get("updated_at")), "quote": snip, "ref": str(c["_id"])})

    async for c in db.contacts.find({"user_id": {"$in": owners}, **LIVE, "how_we_met.summary": mongo_rx}, {"how_we_met": 1}).limit(120):
        met = c.get("how_we_met") or {}
        if not _snippet(met.get("summary") or "", rx):
            continue
        span = dw.period(met.get("date") or "")
        if window and span and not dw.overlaps(span, window):
            continue
        hits.append({"source": "note", "contact_id": str(c["_id"]), "who": "note", "when": span[0] if span else _when(met.get("updated_at")), "quote": f"How we met: {met['summary']}", "ref": str(c["_id"])})

    # saved relationship facts (family, hobbies, interests, events) on the same contacts; superseded facts are history, not what is true now
    q = {"contact_id": {"$in": cids}, "status": {"$ne": "superseded"}, "statement": mongo_rx}
    if rng:
        q["$or"] = [{"occurred_at": rng}, {"occurred_at": None}]
    async for f in db.contact_facts.find(q, {"statement": 1, "contact_id": 1, "occurred_at": 1, "recorded_at": 1}).sort("recorded_at", -1).limit(200):
        snip = _snippet(f.get("statement") or "", rx)
        if snip:
            hits.append({"source": "fact", "contact_id": f.get("contact_id"), "who": "fact", "when": _when(f.get("occurred_at") or f.get("recorded_at")), "quote": f"Saved detail: {snip}", "ref": str(f["_id"])})

    async for c in db.contacts.find({"_id": {"$in": cid_oids}, "personal_details": {"$type": "object", "$ne": {}}}, {"personal_details": 1, "updated_at": 1}).limit(3000):
        for line in _flat(c.get("personal_details")):
            if rx.search(line):
                hits.append({"source": "fact", "contact_id": str(c["_id"]), "who": "fact", "when": _when(c.get("updated_at")), "quote": f"Personal detail: {line[:280]}", "ref": str(c["_id"])})

    # files and photos Jessi read (business cards, VIN plates, PDFs); sensitive ones only when the searcher filed them
    q = {"user_id": {"$in": owners}, "deleted": {"$ne": True}, "contact_id": {"$nin": ["", None]}, "$or": [{"text": mongo_rx}, {"summary": mongo_rx}, {"name": mongo_rx}, {"title": mongo_rx}]}
    if rng:
        q["created_at"] = rng
    async for f in db.contact_files.find(q, {"text": 1, "summary": 1, "name": 1, "title": 1, "contact_id": 1, "created_at": 1, "sensitive": 1, "user_id": 1}).sort("created_at", -1).limit(120):
        if f.get("sensitive") and str(f.get("user_id")) != str(user["_id"]):
            continue
        snip = _snippet(f.get("summary") or "", rx) or _snippet(f.get("text") or "", rx) or _snippet(f"{f.get('title') or ''} {f.get('name') or ''}", rx)
        if snip:
            hits.append({"source": "file", "contact_id": f.get("contact_id"), "who": "file", "when": _when(f.get("created_at")), "quote": snip, "ref": str(f["_id"])})

    hits.extend(await _sales(db, owners, rx, mongo_rx, since, until))
    hits.extend(await _tags(db, owners, rx, mongo_rx))

    hits = [h for h in hits if h.get("contact_id")]
    # Tags first (a label the rep set on purpose never gets squeezed out by the hit cap), then newest first.
    hits.sort(key=lambda h: (0 if h["source"] == "tag" else 1, -(h["when"] or datetime.min.replace(tzinfo=timezone.utc)).timestamp()))
    per, out = {}, []
    for h in hits:
        n = per.get(h["contact_id"], 0)
        if n < PER_CONTACT:
            per[h["contact_id"]] = n + 1
            out.append(h)
        if len(out) >= MAX_HITS:
            break
    return out


async def _sales(db, owners: list, rx: re.Pattern, mongo_rx: dict, since: Optional[datetime], until: Optional[datetime] = None) -> list:
    """What each customer bought (purchase_history, the derived vehicle field) and the vehicle they said they want. 'Who did I sell a Tahoe to?'"""
    hits = []

    def outside(when):
        return bool(when) and bool((since and when < since) or (until and when >= until))
    q = {"user_id": {"$in": owners}, "status": {"$nin": ["merged", "deleted", "hidden"]},
         "$or": [{"purchase_history": {"$elemMatch": {"$or": [{"title": mongo_rx}, {"notes": mongo_rx}, {"category": mongo_rx}]}}}, {"vehicle": mongo_rx}, {"vehicle_interest": mongo_rx}]}
    async for c in db.contacts.find(q, {"purchase_history": 1, "vehicle": 1, "vehicle_interest": 1, "date_sold": 1, "updated_at": 1}).limit(200):
        cid = str(c["_id"])
        found = False
        for e in c.get("purchase_history") or []:
            if not rx.search(" ".join(str(x) for x in (e.get("title"), e.get("category"), e.get("notes")) if x)):
                continue
            when = _when(e.get("date"))
            if outside(when):
                continue
            quote = f"Sold: {e.get('title') or 'a purchase'}" + (f" on {_fmt(when)}" if when else "") + (f". {e['notes']}" if e.get("notes") else "")
            hits.append({"source": "sale", "contact_id": cid, "who": "sale", "when": when, "quote": quote, "ref": cid})
            found = True
        if not found and rx.search(c.get("vehicle") or ""):
            when = _when(c.get("date_sold")) or _when(c.get("updated_at"))
            if not outside(when):
                hits.append({"source": "sale", "contact_id": cid, "who": "sale", "when": when, "quote": f"Sold: {c['vehicle']}" + (f" on {_fmt(when)}" if c.get("date_sold") and when else ""), "ref": cid})
                found = True
        if not found and rx.search(c.get("vehicle_interest") or ""):
            hits.append({"source": "note", "contact_id": cid, "who": "note", "when": _when(c.get("updated_at")), "quote": f"Vehicle interest on file: {c['vehicle_interest']}", "ref": cid})
    return hits


async def _tags(db, owners: list, rx: re.Pattern, mongo_rx: dict) -> list:
    """People the rep tagged with something that fits the ask: 'who are my Harley riders'. Tags are the current label, so no lookback window."""
    hits = []
    q = {"user_id": {"$in": owners}, "status": {"$nin": ["merged", "deleted", "hidden"]}, "tags": mongo_rx}
    async for c in db.contacts.find(q, {"tags": 1, "updated_at": 1}).limit(300):
        matched = [t for t in (c.get("tags") or []) if isinstance(t, str) and rx.search(t)]
        if matched:
            hits.append({"source": "tag", "contact_id": str(c["_id"]), "who": "tag", "when": _when(c.get("updated_at")), "quote": "Tagged: " + ", ".join(matched), "ref": str(c["_id"]), "tags": matched})
    return hits


def _memo_hit(v: dict, quote: str) -> dict:
    return {"source": "unfiled", "contact_id": None, "who": "memo", "when": _when(v.get("created_at")), "quote": quote, "ref": str(v["_id"]),
            "memo_id": str(v["_id"]), "title": v.get("title") or ""}


async def unfiled(db, user: dict, terms: list, window: Optional[dict] = None) -> list:
    """The searcher's OWN voice memos that are not filed to a contact yet (the memo inbox). Nobody else's, whatever their role."""
    q = {"user_id": str(user["_id"]), "unattached": True}
    if window:
        q["created_at"] = _range(window["start"], window["end"])
    rx = _regex(terms) if terms else None
    if rx:
        mongo_rx = {"$regex": "|".join(re.escape(t) for t in terms), "$options": "i"}
        q["$or"] = [{"transcript": mongo_rx}, {"summary": mongo_rx}, {"title": mongo_rx}, {"tags": mongo_rx}]
    hits = []
    async for v in db.voice_notes.find(q, {"transcript": 1, "summary": 1, "title": 1, "tags": 1, "created_at": 1}).sort("created_at", -1).limit(60):
        text = " ".join(str(x) for x in (v.get("title"), v.get("summary"), v.get("transcript")) if x)
        snip = _snippet(v.get("transcript") or "", rx) or _snippet(v.get("summary") or "", rx) or _snippet(text, rx) if rx else (v.get("summary") or v.get("transcript") or v.get("title") or "")[:280]
        if not snip and rx and any(rx.search(str(t)) for t in v.get("tags") or []):
            snip = (v.get("summary") or v.get("transcript") or v.get("title") or "")[:280]
        if snip:
            hits.append(_memo_hit(v, snip))
    return hits


async def met_between(db, user: dict, window: dict) -> list:
    """'People I met in October': How we met dated inside the window, else the day the contact was added. Same owner lists as scan()."""
    owners = await _owners(db, user)
    years = sorted({str(y) for y in range(window["start"].year, window["end"].year + 1)})
    q = {"user_id": {"$in": owners}, **LIVE, "$or": [{"how_we_met.date": {"$regex": "^(" + "|".join(years) + ")"}}, {"created_at": _range(window["start"], window["end"])}]}
    hits = []
    async for c in db.contacts.find(q, {"how_we_met": 1, "created_at": 1}).sort("created_at", -1).limit(400):
        met = c.get("how_we_met") if isinstance(c.get("how_we_met"), dict) else {}
        span = dw.period(met.get("date") or "")
        if span:
            if not dw.overlaps(span, window):
                continue
            hits.append({"source": "met", "contact_id": str(c["_id"]), "who": "met", "when": span[0], "quote": met.get("summary") or f"Met {_fmt(span[0])}", "ref": str(c["_id"])})
        else:
            when = _when(c.get("created_at"))
            if when and window["start"] <= when < window["end"]:
                hits.append({"source": "met", "contact_id": str(c["_id"]), "who": "met", "when": when,
                             "quote": (f"{met['summary']}. " if met.get("summary") else "") + f"Added to your contacts {_fmt(when)}", "ref": str(c["_id"])})
    return hits


async def memos_between(db, user: dict, window: dict) -> list:
    """'Memos from last week': voice memos recorded inside the window, on contacts the rep can see plus their own unfiled ones."""
    owners = await _owners(db, user)
    cids = [str(i) for i in await db.contacts.distinct("_id", {"user_id": {"$in": owners}, **LIVE})]
    hits = []
    async for v in db.voice_notes.find({"contact_id": {"$in": cids}, "created_at": _range(window["start"], window["end"])},
                                       {"transcript": 1, "summary": 1, "contact_id": 1, "created_at": 1}).sort("created_at", -1).limit(120):
        quote = (v.get("summary") or v.get("transcript") or "")[:280]
        if quote:
            hits.append({"source": "memo", "contact_id": v.get("contact_id"), "who": "memo", "when": _when(v.get("created_at")), "quote": quote, "ref": str(v["_id"])})
    return hits + await unfiled(db, user, [], window)


def _topic_left(text: str) -> bool:
    return any(len(w) > 2 and w not in STOP and w not in LISTING for w in re.findall(r"[a-z0-9$][a-z0-9$,.'-]*", (text or "").lower()))


async def verify(topic: str, query: str, hits: list) -> dict:
    """One LLM read of the snippets: which ones show the person actually meant this (asked, wants, is shopping), and a one-line why.
    Identical snippets (sixty people all 'Tagged: Harley riders') are judged once and the verdict applied to every one of them."""
    if not hits:
        return {}
    groups: dict = {}
    for i, h in enumerate(hits):
        groups.setdefault((h["source"], h["who"], h["quote"].strip().lower()), []).append(i)
    reps = [idx[0] for idx in groups.values()]
    listing = "\n".join(f"[{k}] ({SOURCES[hits[i]['source']]}, {'the customer' if hits[i]['who'] == 'them' else 'me' if hits[i]['who'] == 'me' else hits[i]['who']}, {_fmt(hits[i]['when'])}) {hits[i]['quote']}" for k, i in enumerate(reps))
    try:
        data = await _llm_json(
            "You help a car sales rep find the customer they are thinking of. Given what the rep is looking for and numbered snippets from past texts, calls and memos, "
            "decide for each snippet whether it is a REAL match: the customer (or the rep about that customer) actually raised, wanted, asked about or shopped for the thing. "
            "A passing mention (someone else's car, a joke, the rep pitching it unprompted with no interest back) is not a match. "
            "A 'Sold:' snippet is the rep's own sold record (that customer bought that item from the rep): it is a strong match whenever the item fits the ask, "
            "including 'who did I sell a Tahoe to', 'who bought a Silverado', 'who has a Tahoe', or a plain product search. "
            "A 'Tagged:' snippet is a label the rep put on that customer on purpose: it is a strong match whenever the tag fits the ask "
            "(tag 'Harley riders' fits 'who rides a Harley', 'my Harley people', 'anyone into motorcycles'; tag 'VIP' fits 'who are my VIPs'). A tag that only shares a word by coincidence is not a match. "
            "A 'Saved detail:' or 'Personal detail:' snippet is something the rep saved about that customer (family, kids, hobbies, interests, important events): it is a strong match whenever it fits the ask "
            "('whose daughter plays violin', 'the guy with the boat', 'who is into golf'). 'How we met:' tells where the rep met them. "
            "Snippets marked 'voice memo not filed yet' are the rep's own memos not attached to anyone: match them by what the memo is about. "
            "Return ONLY JSON: {\"matches\": [{\"i\": <index>, \"why\": \"<one short sentence quoting or paraphrasing what they said>\", \"strength\": \"strong|maybe\"}]}",
            f"LOOKING FOR: {query}\nTOPIC: {topic}\n\nSNIPPETS:\n{listing}", timeout=25)
        out = {}
        for m in data.get("matches") or []:
            k = str(m.get("i", ""))
            if not k.isdigit() or int(k) >= len(reps):
                continue
            rep = hits[reps[int(k)]]
            for i in groups[(rep["source"], rep["who"], rep["quote"].strip().lower())]:
                out[i] = m
        return out
    except Exception as e:
        logger.warning(f"[Mentions] verify failed, keeping keyword hits: {e}")
        return {i: {"why": h["quote"][:140], "strength": "maybe"} for i, h in enumerate(hits)}


async def search(db, user: dict, query: str, days: Optional[int] = None) -> dict:
    """Who mentioned X. A time frame in the ask ('last February', 'three months ago', 'in October') becomes a hard window; an ask that is only
    a time frame ('people I met in October', 'memos from last week') lists by date with no keyword or LLM pass."""
    win = dw.parse(query)
    core = dw.strip(query, win)
    if not win and days and not _topic_left(core):
        win = {"start": _now() - timedelta(days=days), "end": _now(), "label": f"the last {days} days", "phrase": ""}
    mode = "search"
    if win and not _topic_left(core):
        mode = "met" if MET.search(core) else "memos"
        hits = await (met_between(db, user, win) if mode == "met" else memos_between(db, user, win))
        t = {"topic": "people you met" if mode == "met" else "voice memos", "terms": []}
        keep = {i: {"why": "", "strength": "strong"} for i in range(len(hits))}
    else:
        t = await terms_for(core or query)
        hits = await scan(db, user, t["terms"], days, win) + await unfiled(db, user, t["terms"], win)
        keep = await verify(t["topic"], query, hits)
    by_contact, memos = {}, []
    for i, h in enumerate(hits):
        m = keep.get(i)
        if not m:
            continue
        if h["source"] == "unfiled":
            memos.append({"memo_id": h["memo_id"], "title": h.get("title") or "", "when": h["when"].isoformat() if h["when"] else None, "when_label": _fmt(h["when"]),
                          "when_spoken": _spoken_date(h["when"]), "quote": h["quote"], "why": m.get("why") or "", "link": f"/voice-memos?memo={h['memo_id']}",
                          "strength": "strong" if m.get("strength") == "strong" else "maybe"})
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
        row["hits"].sort(key=lambda h: (0 if h["strength"] == "strong" else 1, 0 if h["source"] in ("sale", "tag") else 1, -(_when(h["when"]) or datetime.min.replace(tzinfo=timezone.utc)).timestamp()))
        best = row["hits"][0]
        results.append({**row, "when": row["when"].isoformat() if row["when"] else None, "when_label": _fmt(row["when"]), "when_spoken": _spoken_date(row["when"]),
                        "name": f"{c.get('first_name') or ''} {c.get('last_name') or ''}".strip(), "first": c.get("first_name") or "", "phone": c.get("phone") or "",
                        "vehicle": c.get("vehicle") or c.get("vehicle_interest") or "", "photo": c.get("photo_thumbnail"), "best": best})
    results.sort(key=lambda r: (0 if r["strength"] == "strong" else 1, -(_when(r["when"]) or datetime.min.replace(tzinfo=timezone.utc)).timestamp()))
    window = {"label": win["label"], "from": win["start"].isoformat(), "to": win["end"].isoformat()} if win else None
    return {"query": query, "topic": t["topic"], "terms": t["terms"], "scanned": len(hits), "results": results, "memos": memos, "window": window, "mode": mode}


def _line(r: dict) -> str:
    b = r["best"]
    if b["source"] == "tag":
        return f"{r['name']}, {b['quote'].replace('Tagged:', 'tagged', 1)}".rstrip(". ")
    if b["source"] == "met":
        return f"{r['name']}, {b['quote']}".rstrip(". ")
    src = {"text": "texted", "call": "on a call", "memo": "in your voice memo", "note": "in your notes", "sale": "in your sold records", "file": "in a file on their record",
           "fact": "in what you saved about them"}.get(b["source"], "on their record")
    return f"{r['name']}, {src} {r['when_spoken']}: {b['why'] or b['quote']}".rstrip(". ")


def _lines(rs: list) -> str:
    return ". ".join(_line(r) for r in rs) + "."


def _memo_tail(memos: list) -> str:
    if not memos:
        return ""
    m = memos[0]
    name = f"\"{m['title']}\"" if m.get("title") else f"from {m['when_label'] or 'a while back'}"
    more = f" and {len(memos) - 1} more" if len(memos) > 1 else ""
    return f" There is also a voice memo you have not filed to anyone yet, {name}{more}. It is on your screen, want me to file it to someone?"


def spoken(res: dict, first: int = 3) -> str:
    """What Jessi says out loud: the first few, the total, and how to hear the rest."""
    rs = res.get("results") or []
    topic = res.get("topic") or res.get("query")
    when = f" in {res['window']['label']}" if res.get("window") else ""
    memo = _memo_tail(res.get("memos") or [])
    if not rs:
        if res.get("mode") == "met":
            return f"I have nobody you met{when}." + memo
        if res.get("mode") == "memos":
            return (f"No voice memos{when}." if not memo else f"No memos on a contact{when}.") + memo
        return (f"Nobody on record mentioned {topic}{when}. I checked your texts, call transcripts, voice memos, notes, saved details, tags and sold records."
                + (" The closest keyword hits were not about that." if res.get("scanned") else "") + memo)
    left = len(rs) - first
    more = f" And {left} more on your screen. Say keep going and I will read the rest." if left > 0 else ""
    if res.get("mode") == "met":
        head = f"You met {len(rs)} {'person' if len(rs) == 1 else 'people'}{when}. "
    elif res.get("mode") == "memos":
        head = f"{len(rs)} {'person has' if len(rs) == 1 else 'people have'} voice memos{when}. "
    else:
        verb = "match" if any(r["best"]["source"] == "tag" for r in rs) else "mentioned"
        head = f"{len(rs)} {'person' if len(rs) == 1 else 'people'} {verb} {topic}{when}. " if len(rs) > 1 else ""
    return head + _lines(rs[:first]) + more + memo + f" Want me to pull up {rs[0]['first'] or 'the first one'} or text them?"


def spoken_more(res: dict, start: int, count: int) -> tuple:
    """The next batch of the same list ('keep going'). Returns (text, new_cursor)."""
    rs = res.get("results") or []
    if start >= len(rs):
        return "That was everyone. They are all on your screen.", len(rs)
    batch = rs[start:start + count]
    end = start + len(batch)
    left = len(rs) - end
    tail = f" {left} more to go. Say keep going for the next ones." if left > 0 else " And that is everyone."
    return _lines(batch) + tail, end
