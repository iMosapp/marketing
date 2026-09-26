"""Site crawl: Jessi reads the dealership's website once (home + the pages that matter) and drafts store facts, specials and notes
for the widget's knowledge base. The manager reviews and picks what to keep; nothing is saved without them."""
import asyncio
import json
import logging
import os
import re
import secrets
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin, urlparse

from bson import ObjectId

from services import widgets as W
from services.llm_models import CUSTOMER_TEXT_MODEL
from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)

COLL = "widget_crawls"
PAGES_COLL = "widget_site_pages"
MAX_PAGES = 7
SITE_MAX_PAGES = 60
PAGE_CHARS = 6000
SITE_PAGE_CHARS = 40000   # decks and feature sheets run long; retrieval picks the relevant passages per question
SITE_BUDGET = 7000
SITE_SEG = 700
SITE_FIRST = re.compile(r"(pric|plan|cost|about|contact|faq|feature|sheet|present|deck|platform|product|solution|industr|how-it-works|how_it_works|demo|integration|support|compare|trial|why|team|hours|location|help)", re.I)
SITE_DECK = re.compile(r"(feature.?sheet|present|deck|platform|brochure|one.?pager|playbook)", re.I)
WANT = re.compile(r"(about|hours|contact|direction|location|service|special|offer|deal|promo|coupon|finance|parts|why|faq|team|staff|warranty|review|amenit|shuttle|loaner|deliver|espanol|español)", re.I)
SKIP = re.compile(r"\.(pdf|jpg|jpeg|png|gif|svg|webp|zip|mp4)$|/(inventory|vehicle|vdp|srp|used|new|search|blog|news|privacy|terms|sitemap|login|cart)\b|#|mailto:|tel:", re.I)
SITE_SKIP = re.compile(r"\.(pdf|jpg|jpeg|png|gif|svg|webp|zip|mp4|mp3|css|js|xml|json)$|/(blog|news|privacy|terms|legal|sitemap|login|signin|sign-in|signup|cart|checkout|wp-admin|tag|category|author|feed|go|s|get)(/|$)|\?|#|mailto:|tel:", re.I)


def _now():
    return datetime.now(timezone.utc)


def _norm_url(url: str) -> str:
    url = (url or "").strip()
    return url if re.match(r"^https?://", url) else f"https://{url}"


def _text(html: str, limit: int = PAGE_CHARS) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html or "", "html.parser")
    for t in soup(["script", "style", "noscript", "svg", "iframe", "form", "nav", "footer"]):
        t.decompose()
    text = soup.get_text(" ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    return re.sub(r"\n{2,}", "\n", text).strip()[:limit]


def _all_links(html: str, base: str) -> list:
    """Every same-site HTML page linked from `base`, for the whole-site read."""
    host = urlparse(base).netloc.lower().replace("www.", "")
    out, seen = [], set()
    for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\']', html or "", re.I):
        full = urljoin(base, m.group(1).strip())
        p = urlparse(full)
        if p.scheme not in ("http", "https") or p.netloc.lower().replace("www.", "") != host or SITE_SKIP.search(full):
            continue
        clean = full.split("?")[0].split("#")[0].rstrip("/") or full
        if clean in seen or clean == base.rstrip("/"):
            continue
        seen.add(clean)
        out.append(clean)
    return out


async def fetch_site(url: str, limit: int = SITE_MAX_PAGES, seeds: Optional[list] = None) -> list:
    """Breadth-first read of the site: home (+ sitemap.xml + owner-added seed pages), everything they link to, then the next hop, up to `limit` pages."""
    import httpx
    headers = {"User-Agent": "Mozilla/5.0 (compatible; iMOS-JessiReader/1.0; +https://www.imonsocial.com)"}
    pages, seen, queue = [], set(), []
    async with httpx.AsyncClient(timeout=12, follow_redirects=True, headers=headers) as client:
        r = await client.get(url)
        r.raise_for_status()
        base = str(r.url)
        seen.add(base.rstrip("/"))

        def keep(u: str, html: str):
            t = (re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S) or [None, ""])[1]
            txt = _text(html[:900000], SITE_PAGE_CHARS)
            if len(txt) > 150:
                pages.append({"url": u, "title": re.sub(r"\s+", " ", t or "").strip()[:120], "text": txt})
            return _all_links(html, u)

        for link in keep(base, r.text):
            if link not in seen:
                seen.add(link)
                queue.append(link)
        # owner-added pages first (decks, feature sheets, industry pages that nothing links to), then the sitemap if the site has one
        host = urlparse(base).netloc.lower().replace("www.", "")
        for sd in (seeds or []):
            sd = _norm_url(sd).split("#")[0].rstrip("/")
            if urlparse(sd).netloc.lower().replace("www.", "") == host and sd not in seen:
                seen.add(sd)
                queue.insert(0, sd)
        try:
            sm = await client.get(urljoin(base, "/sitemap.xml"))
            if sm.status_code == 200 and "<loc>" in sm.text:
                for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sm.text)[:200]:
                    loc = loc.split("#")[0].rstrip("/")
                    if urlparse(loc).netloc.lower().replace("www.", "") == host and not SITE_SKIP.search(loc) and loc not in seen:
                        seen.add(loc)
                        queue.append(loc)
        except Exception:
            pass

        async def one(u: str):
            try:
                x = await client.get(u)
                if x.status_code == 200 and "text/html" in (x.headers.get("content-type") or ""):
                    return u, x.text
            except Exception as e:
                logger.debug(f"[Crawl] skip {u}: {e}")
            return u, None

        while queue and len(pages) < limit:
            queue.sort(key=lambda u: 0 if SITE_FIRST.search(u) else 1)
            batch, queue = queue[:8], queue[8:]
            for u, html in await asyncio.gather(*[one(u) for u in batch]):
                if not html or len(pages) >= limit:
                    continue
                for link in keep(u, html):
                    if link not in seen and len(seen) < limit * 4:
                        seen.add(link)
                        queue.append(link)
    return pages[:limit]


async def save_site_pages(db, w: dict, pages: list) -> int:
    wid = str(w["_id"])
    await db[PAGES_COLL].delete_many({"widget_id": wid})
    if pages:
        now = _now()
        await db[PAGES_COLL].insert_many([{"widget_id": wid, "url": p["url"], "title": p["title"], "text": p["text"], "at": now} for p in pages])
    return len(pages)


async def site_knowledge_meta(db, w: dict) -> dict:
    wid = str(w["_id"])
    n = await db[PAGES_COLL].count_documents({"widget_id": wid})
    first = await db[PAGES_COLL].find_one({"widget_id": wid}, {"at": 1}) if n else None
    decks = [p["title"] or p["url"] async for p in db[PAGES_COLL].find({"widget_id": wid, "url": {"$regex": SITE_DECK.pattern, "$options": "i"}}, {"title": 1, "url": 1}).limit(20)] if n else []
    return {"pages": n, "read_at": first["at"].isoformat() if first and first.get("at") else None,
            "decks": [re.sub(r"\s*[-|·]\s*i'?m on social.*$", "", d, flags=re.I).strip() for d in decks]}


_STOP = {"the", "and", "for", "you", "your", "with", "that", "this", "have", "what", "how", "does", "can", "are", "our", "from", "about", "into", "will",
         "they", "them", "when", "where", "which", "there", "here", "just", "like", "want", "need", "know", "much", "many", "more", "some", "any", "all"}


def _tokens(text: str) -> set:
    return {t for t in re.findall(r"[a-z0-9]{3,}", (text or "").lower()) if t not in _STOP}


def _segments(text: str, size: int = SITE_SEG) -> list:
    """Split page text into ~size-char passages on sentence / line boundaries so a 93-feature sheet yields the 3 features that matter."""
    parts, cur = [], ""
    for piece in re.split(r"(?<=[.!?])\s+|\n+", text or ""):
        piece = piece.strip()
        if not piece:
            continue
        if cur and len(cur) + len(piece) + 1 > size:
            parts.append(cur)
            cur = piece
        else:
            cur = f"{cur} {piece}".strip()
    if cur:
        parts.append(cur)
    return parts


async def site_context(db, w: dict, question: str, top: int = 5, chars: int = SITE_BUDGET) -> str:
    """The passages of the site most relevant to the visitor's question (home page intro always), grouped by page, for the prompt.
    `top` = max pages quoted, `chars` = total budget across all passages."""
    wid = str(w["_id"])
    pages = await db[PAGES_COLL].find({"widget_id": wid}, {"url": 1, "title": 1, "text": 1}).to_list(SITE_MAX_PAGES)
    if not pages:
        return ""
    q = _tokens(question)
    money = bool(re.search(r"\b(price|prices|pricing|cost|costs|plan|plans|month|monthly|year|yearly|fee|fees|pay|paying|subscription|trial|free)\b", question or "", re.I))
    home = min(pages, key=lambda p: len(p["url"]))

    scored = []
    for p in pages:
        head = _tokens((p["title"] or "") + " " + p["url"])
        boost = 12 if money and re.search(r"pric|plan", p["url"] + " " + (p["title"] or ""), re.I) else 0
        for i, seg in enumerate(_segments(p["text"])):
            words = _tokens(seg)
            sc = sum(3 if t in head else 2 for t in q if t in words) + boost
            if sc > boost or (p is home and i == 0):
                scored.append((sc + (2 if p is home and i == 0 else 0), p, i, seg))
    scored.sort(key=lambda x: -x[0])

    chosen: dict = {}
    used = 0
    for sc, p, i, seg in scored:
        if used + len(seg) > chars or (len(chosen) >= top and p["url"] not in chosen):
            continue
        chosen.setdefault(p["url"], {"p": p, "segs": []})["segs"].append((i, seg))
        used += len(seg)
    if not chosen:
        chosen[home["url"]] = {"p": home, "segs": [(0, (home["text"] or "")[:1200])]}
    blocks = []
    for url, d in chosen.items():
        p = d["p"]
        body = "\n…\n".join(seg for _, seg in sorted(d["segs"]))
        blocks.append(f"=== {p['title'] or p['url']} ({p['url']}) ===\n{body}")
    return "\n\n".join(blocks)


def _links(html: str, base: str) -> list:
    host = urlparse(base).netloc.lower().replace("www.", "")
    out, seen = [], set()
    for m in re.finditer(r'<a[^>]+href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', html or "", re.I | re.S):
        href, label = m.group(1).strip(), re.sub(r"<[^>]+>", " ", m.group(2))
        full = urljoin(base, href)
        p = urlparse(full)
        if p.scheme not in ("http", "https") or p.netloc.lower().replace("www.", "") != host or SKIP.search(full):
            continue
        clean = full.split("?")[0].rstrip("/")
        if clean in seen or clean == base.rstrip("/"):
            continue
        if WANT.search(clean) or WANT.search(label):
            seen.add(clean)
            out.append(clean)
    return out[:MAX_PAGES - 1]


async def _fetch_pages(url: str) -> list:
    import httpx
    headers = {"User-Agent": "Mozilla/5.0 (compatible; iMOS-JessiReader/1.0; +https://www.imonsocial.com)"}
    pages = []
    async with httpx.AsyncClient(timeout=12, follow_redirects=True, headers=headers) as client:
        r = await client.get(url)
        r.raise_for_status()
        home = r.text[:900000]
        base = str(r.url)
        title = (re.search(r"<title[^>]*>(.*?)</title>", home, re.I | re.S) or [None, ""])[1]
        pages.append({"url": base, "title": re.sub(r"\s+", " ", title or "").strip()[:120], "text": _text(home)})

        async def one(u: str):
            try:
                x = await client.get(u)
                if x.status_code == 200 and "text/html" in (x.headers.get("content-type") or ""):
                    t = (re.search(r"<title[^>]*>(.*?)</title>", x.text, re.I | re.S) or [None, ""])[1]
                    return {"url": u, "title": re.sub(r"\s+", " ", t or "").strip()[:120], "text": _text(x.text[:900000])}
            except Exception as e:
                logger.debug(f"[Crawl] skip {u}: {e}")
            return None

        more = await asyncio.gather(*[one(u) for u in _links(home, base)])
        pages += [p for p in more if p and len(p["text"]) > 200]
    return pages


PROMPT = """You are helping a dealership manager set up Jessi, the assistant that chats with visitors on their website.
Below is text scraped from the dealership's own site. Draft the knowledge Jessi should use. Only use what the pages say; never invent.

Return STRICT JSON with exactly these keys:
{{
  "facts": ["one plain sentence each, max 12, things a visitor would ask: departments, services offered, amenities (shuttle, loaners, wifi), languages, delivery, warranties, awards, years in business, brands carried. NOT hours, NOT prices."],
  "specials": [{{"title": "short title, max 80 chars, exactly as advertised", "details": "fine print or what is included, max 300 chars, may be empty", "ends": "YYYY-MM-DD or empty string when no end date is shown"}}],
  "notes": "2 to 4 plain sentences about what makes this store different, directions or landmarks, and anything else useful. Empty string if nothing.",
  "hours_seen": "the opening hours as written on the site, or empty string if none were found"
}}
Rules: plain English, no em dashes, no emojis, no marketing fluff, no duplicates, skip anything about prices, payments, APR or financing terms. Specials max 8.

STORE NAME: {name}

PAGES:
{pages}
"""


PROMPT_BUSINESS = """You are helping a business owner set up Jessi, the assistant that chats with visitors on their company website.
Below is text scraped from the company's own site. Draft the knowledge Jessi should use. Only use what the pages say; never invent.

Return STRICT JSON with exactly these keys:
{{
  "facts": ["one plain sentence each, max 14, things a prospect would ask: what the product or service does, who it is for, key features, integrations, how setup or onboarding works, support, guarantees, awards, years in business, plan names and prices exactly as written"],
  "specials": [{{"title": "current offer or promotion exactly as advertised, max 80 chars", "details": "what is included, max 300 chars, may be empty", "ends": "YYYY-MM-DD or empty string"}}],
  "notes": "2 to 4 plain sentences on what makes this company different and the best next step for an interested visitor (demo, trial, call). Empty string if nothing.",
  "hours_seen": "support or office hours as written on the site, or empty string"
}}
Rules: plain English, no em dashes, no emojis, no marketing fluff, no duplicates. Specials max 8.

COMPANY NAME: {name}

PAGES:
{pages}
"""


def _cut(text: str, n: int) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= n:
        return text
    head = text[:n]
    return (head[: head.rfind(" ")] if " " in head else head).rstrip(",;:") + "…"


def _parse(out: str) -> dict:
    m = re.search(r"\{.*\}", out or "", re.S)
    data = json.loads(m.group(0)) if m else {}
    facts = [no_em_dash(_cut(f, 220)) for f in (data.get("facts") or []) if str(f).strip()][:12]
    specials = []
    for s in (data.get("specials") or [])[:8]:
        if isinstance(s, dict) and str(s.get("title") or "").strip():
            ends = str(s.get("ends") or "").strip()[:10]
            specials.append({"id": f"c{secrets.token_hex(3)}", "title": no_em_dash(str(s["title"]).strip())[:80], "details": no_em_dash(str(s.get("details") or "").strip())[:300],
                             "ends": ends if re.match(r"^\d{4}-\d{2}-\d{2}$", ends) else ""})
    return {"facts": facts, "specials": specials, "notes": no_em_dash(" ".join(str(data.get("notes") or "").split()))[:1200],
            "hours_seen": no_em_dash(" ".join(str(data.get("hours_seen") or "").split()))[:400]}


async def _draft(store: dict, pages: list, business: bool = False) -> dict:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise RuntimeError("Jessi's brain is not configured on this server (EMERGENT_LLM_KEY).")
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    body = "\n\n".join(f"=== {p['title'] or p['url']} ({p['url']}) ===\n{p['text'][:PAGE_CHARS]}" for p in pages)[:42000]
    chat = LlmChat(api_key=api_key, session_id=f"crawl_{secrets.token_hex(4)}", system_message="You write precise JSON for a business knowledge base.").with_model(*CUSTOMER_TEXT_MODEL)
    prompt = (PROMPT_BUSINESS if business else PROMPT).format(name=store.get("name") or "the store", pages=body)
    out = await asyncio.wait_for(chat.send_message(UserMessage(text=prompt)), timeout=90)
    return _parse(out if isinstance(out, str) else str(out))


async def start(db, w: dict, url: str, user: dict, mode: Optional[str] = None) -> dict:
    url = _norm_url(url)
    if not re.match(r"^https?://[^/\s]+\.[a-z]{2,}", url, re.I):
        raise ValueError("That does not look like a website address.")
    running = await db[COLL].find_one({"widget_id": str(w["_id"]), "status": "running"})
    if running and (_now() - running["created_at"].replace(tzinfo=timezone.utc)).total_seconds() < 180:
        return public(running)
    doc = {"widget_id": str(w["_id"]), "store_id": w.get("store_id"), "url": url, "status": "running", "pages": [], "draft": None, "error": "",
           "mode": mode if mode in ("business", "dealership") else W.normalize_config(w)["kb"]["mode"], "created_by": str(user["_id"]), "created_at": _now(), "updated_at": _now()}
    res = await db[COLL].insert_one(doc)
    doc["_id"] = res.inserted_id
    return public(doc)


async def run(job_id: str):
    from routers.database import get_db
    db = get_db()
    job = await db[COLL].find_one({"_id": ObjectId(job_id)})
    if not job:
        return
    try:
        w = await db[W.COLL].find_one({"_id": ObjectId(job["widget_id"])})
        store = await W.store_of(db, w or {})
        business = (job.get("mode") or W.normalize_config(w or {})["kb"]["mode"]) == "business"
        pages = await fetch_site(job["url"], seeds=W.normalize_config(w or {})["kb"].get("extra_urls") or []) if business else await _fetch_pages(job["url"])
        await db[COLL].update_one({"_id": job["_id"]}, {"$set": {"pages": [{"url": p["url"], "title": p["title"], "chars": len(p["text"])} for p in pages], "updated_at": _now()}})
        if not pages or sum(len(p["text"]) for p in pages) < 300:
            raise RuntimeError("That site did not give me any readable text (it may block robots or be all images).")
        saved = await save_site_pages(db, w, pages) if business else 0
        draft = await _draft(store, pages, business)
        await db[COLL].update_one({"_id": job["_id"]}, {"$set": {"status": "done", "draft": draft, "site_pages_saved": saved, "updated_at": _now()}})
        logger.info(f"[Crawl] {job['url']}: {len(pages)} pages -> {len(draft['facts'])} facts, {len(draft['specials'])} specials, {saved} pages kept for answers")
    except Exception as e:
        logger.warning(f"[Crawl] {job.get('url')} failed: {e}")
        await db[COLL].update_one({"_id": job["_id"]}, {"$set": {"status": "failed", "error": no_em_dash(str(e))[:300], "updated_at": _now()}})


async def latest(db, w: dict) -> Optional[dict]:
    job = await db[COLL].find_one({"widget_id": str(w["_id"])}, sort=[("created_at", -1)])
    return public(job) if job else None


def public(job: dict) -> dict:
    return {"id": str(job["_id"]), "url": job.get("url"), "status": job.get("status"), "error": job.get("error") or "", "pages": job.get("pages") or [],
            "draft": job.get("draft"), "site_pages_saved": int(job.get("site_pages_saved") or 0),
            "created_at": job["created_at"].isoformat() if job.get("created_at") else None, "applied_at": job["applied_at"].isoformat() if job.get("applied_at") else None}


async def apply(db, w: dict, body: dict, user: dict) -> dict:
    """Keep what the manager ticked: facts -> store.va_facts, specials + notes -> widget.kb."""
    from services.va_prompt import _fact
    store = await W.store_of(db, w)
    have = {(f.get("text") or "").strip().lower() for f in store.get("va_facts") or []}
    added = []
    for t in (body.get("facts") or [])[:20]:
        t = " ".join(str(t).split())[:160]
        if len(t) >= 3 and t.lower() not in have:
            fact = _fact(t, user, "store")
            added.append(fact)
            have.add(t.lower())
    if added and w.get("store_id") and ObjectId.is_valid(str(w["store_id"])):
        await db.stores.update_one({"_id": ObjectId(w["store_id"])}, {"$push": {"va_facts": {"$each": added}}})
    cfg = W.normalize_config(w)
    kb = dict(cfg["kb"])
    titles = {s["title"].lower() for s in kb["specials"]}
    for s in (body.get("specials") or [])[:8]:
        if isinstance(s, dict) and str(s.get("title") or "").strip() and str(s["title"]).strip().lower() not in titles:
            kb["specials"].append({"id": str(s.get("id") or f"c{secrets.token_hex(3)}"), "title": str(s["title"]).strip()[:80], "details": str(s.get("details") or "").strip()[:300], "ends": str(s.get("ends") or "")[:10]})
    notes = " ".join(str(body.get("notes") or "").split())
    if notes and notes.lower() not in (kb.get("notes") or "").lower():
        kb["notes"] = ((kb.get("notes") or "").strip() + ("\n\n" if kb.get("notes") else "") + notes)[:2000]
    merged = W.normalize_config({**w, "kb": kb})
    await db[W.COLL].update_one({"_id": w["_id"]}, {"$set": {"kb": merged["kb"], "updated_at": _now()}})
    if body.get("job_id") and ObjectId.is_valid(str(body["job_id"])):
        await db[COLL].update_one({"_id": ObjectId(body["job_id"])}, {"$set": {"applied_at": _now()}})
    fresh = await db.stores.find_one({"_id": ObjectId(w["store_id"])}, {"va_facts": 1}) if w.get("store_id") and ObjectId.is_valid(str(w["store_id"])) else {}
    return {"facts": [{"id": f.get("id"), "text": f.get("text"), "added_by_name": f.get("added_by_name")} for f in (fresh or {}).get("va_facts") or [] if f.get("text")],
            "kb": merged["kb"], "added_facts": len(added)}
