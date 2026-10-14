"""One reader for a customer thread, shared by every AI writer (auto-reply, Ask Jessi, check-in campaigns).

A rep has ONE text thread per customer, and everything lands in it: texts, Jessi's replies, web chat hand-offs, trade-link
events, lead markers, call logs. This module turns that pile into labelled dialogue (events are events, the site chat is a
site chat, the customer is the customer), groups it into topic EPISODES (a new one starts on a web chat hand-off, a trade
link, a new lead, or when the customer's own words move to a different subject), and tells the model what the person is
talking about RIGHT NOW versus earlier, separate topics."""
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

HISTORY = 40
DIVIDER_GAP_H = 6
KIND_LABEL = {"vehicle": "vehicle shopping", "trade_in": "a trade-in appraisal", "service": "service or repair", "software": "the software we sell",
              "billing": "billing or their account", "general": "a general question"}
INQUIRY_KIND = {"software_demo": "software", "vehicle": "vehicle", "general": "general"}
KEYWORDS = {
    "trade_in": ["trade", "trade-in", "appraisal", "appraise", "worth", "what would you give", "payoff", "pay off", "kbb", "offer on my"],
    "software": ["widget", "embed", "install", "plugin", "login", "log in", "subscription", "dashboard", "software", "demo of", "the app", "your app", "crm",
                 "integration", "my site", "my website", "our website", "wordpress", "snippet", "script", "chat bubble", "add this to"],
    "service": ["oil change", "service appointment", "repair", "brakes", "recall", "check engine", "tires", "maintenance", "warranty claim"],
    "billing": ["invoice", "billing", "my bill", "charged", "refund", "receipt", "card on file", "payment failed"],
    "vehicle": ["test drive", "in stock", "still available", "do you have", "msrp", "lease", "financing", "finance", "down payment", "monthly payment",
                "truck", "suv", "sedan", "miles on", "mileage", "what color", "trim", "4x4", "awd", "out the door", "sticker"],
}


@dataclass
class Episode:
    kind: str
    topic: str
    trigger: str
    started_at: datetime
    ended_at: datetime
    source: str = "text"
    ref: str = ""
    lines: list = field(default_factory=list)
    customer_texts: int = 0
    last_customer: str = ""

    def label(self) -> str:
        return self.topic or KIND_LABEL.get(self.kind, "a general question")


@dataclass
class ThreadView:
    episodes: list
    current: Optional[Episode]
    switched: bool = False
    forced: bool = False
    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def earlier(self) -> list:
        return [e for e in self.episodes if e is not self.current]

    def dialogue(self, max_chars: int = 3500) -> str:
        """Every episode in order, each under a dated header; the current one is marked so the model knows which thread of talk it is answering."""
        blocks = []
        for e in self.episodes:
            tag = "CURRENT TOPIC" if e is self.current else "earlier, separate topic"
            blocks.append(f"=== {_day(e.started_at)} · {e.label()} ({tag}) ===\n" + "\n".join(e.lines))
        text = "\n".join(blocks)
        if len(text) > max_chars:
            text = "[...older part of the thread trimmed...]\n" + text[-max_chars:]
        return text

    def topic_block(self) -> str:
        if not self.current:
            return ""
        cur = self.current
        since = f"since {_ago(cur.started_at, self.now)}" if not self.forced else "chosen by the rep"
        lines = [f"WHAT THE CUSTOMER IS TALKING ABOUT RIGHT NOW: {cur.label()} ({since}; started when {cur.trigger})."]
        earlier = self.earlier()
        if earlier:
            lines.append("EARLIER, SEPARATE TOPICS WITH THIS PERSON (background only; never mix them into this reply unless the customer brings them up):")
            for e in earlier[-4:]:
                lines.append(f"- {_day(e.started_at)}, {e.trigger}: {e.label()}")
        if self.forced:
            rule = (f"The rep chose this topic, so write about THIS topic even if the customer's latest message is about something else: pick up where it left off"
                    + (f" (their last words on it: \"{cur.last_customer[:160]}\")" if cur.last_customer else "") + " and move it forward with a concrete next step or answer.")
        elif self.switched:
            rule = "The customer just changed the subject: follow them to the new topic and leave the previous one alone."
        else:
            rule = "Answer the current topic only."
        if cur.kind == "software":
            rule += " This is about the software we sell, not a vehicle: never mention vehicles, trade-ins, test drives, inventory or financing."
        elif cur.kind == "trade_in":
            rule += " Talk about their trade-in and the appraisal; do not pitch other vehicles unless they ask."
        lines.append("RULE: " + rule)
        return "\n".join(lines)

    def summary(self) -> dict:
        cur = self.current
        return {"kind": cur.kind if cur else None, "label": cur.label() if cur else None, "since": cur.started_at.isoformat() if cur else None, "switched": self.switched, "forced": self.forced,
                "episodes": [{"kind": e.kind, "label": e.label(), "since": e.started_at.isoformat(), "current": e is cur} for e in self.episodes]}

    def inquiry_for_prompt(self, inquiry: Optional[dict]) -> Optional[dict]:
        """The lead's original inquiry block still applies only while the current topic IS that inquiry."""
        if not inquiry or not self.current or len(self.episodes) == 1:
            return inquiry
        return inquiry if INQUIRY_KIND.get(inquiry.get("kind") or "general", "general") == self.current.kind else None

    def force(self, kind: str, topic: str = "") -> "ThreadView":
        """The rep says what this reply is about (chip on the suggestion card)."""
        picks = [e for e in self.episodes if e.kind == kind]
        if picks:
            self.current = picks[-1]
        else:
            self.current = Episode(kind, topic or KIND_LABEL.get(kind, ""), "the rep chose this topic", self.now, self.now, source="rep")
            self.episodes.append(self.current)
        self.switched, self.forced = False, True
        return self


def classify(text: str) -> Optional[str]:
    """Cheap, deterministic topic guess from the customer's own words; None when nothing is specific enough."""
    t = f" {(text or '').lower()} "
    hits = {k: sum(1 for w in ws if w in t) for k, ws in KEYWORDS.items()}
    best = max(hits, key=hits.get)
    return best if hits[best] else None


def _utc(v) -> datetime:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _day(d: datetime) -> str:
    return d.strftime("%b %d").replace(" 0", " ")


def _clock(d: datetime) -> str:
    return d.strftime("%I:%M %p").lstrip("0")


def _ago(d: datetime, now: datetime) -> str:
    s = max(0, int((now - d).total_seconds()))
    if s < 90:
        return "a minute ago"
    if s < 3600:
        return f"{s // 60} minutes ago"
    if s < 86400 * 2:
        return f"{s // 3600} hours ago" if s < 86400 else "yesterday"
    return f"{s // 86400} days ago"


def _webchat_lines(m: dict, first: str) -> list:
    """The hand-off transcript is a conversation the customer had with the SITE assistant, not with the rep: render it as such."""
    content = m.get("content") or ""
    head, _, body = content.partition("\n\n")
    host = re.sub(r"^Web chat on\s+", "", head.split(" (")[0]).strip() or "the website"
    rows = [f"  [web chat on {host}, with the site assistant, before this text thread]"]
    for ln in [x for x in body.split("\n") if x.strip()][:14]:
        who, _, said = ln.partition(": ")
        who = f"{first} (on the site)" if who == "Visitor" else "Site assistant" if who == "Jessi" else who
        rows.append(f"  {who}: {said[:220]}" if said else f"  {ln[:220]}")
    return rows


def _line(m: dict, first: str, ts: datetime) -> Optional[str]:
    sender, typ = m.get("sender"), m.get("type")
    content = (m.get("content") or "").strip()
    if sender == "ai_draft" and m.get("status") != "sent":
        return None
    if typ == "webchat_transcript":
        return "\n".join(_webchat_lines(m, first))
    if sender == "system":
        return f"[event {_clock(ts)}] {content[:160]}" if content else None
    if m.get("channel") == "voice" or typ in ("call_log", "call_recorded"):
        return f"[call {_clock(ts)}] {content[:200]}" if content else None
    if sender in ("user", "ai", "ai_draft"):
        return f"Me: {content[:300]}" if content else ("Me: [sent a photo]" if m.get("media_urls") else None)
    photo = "[sent a photo you cannot see]" if (m.get("media_urls") or m.get("has_media")) else ""
    if not content:
        return f"{first}: {photo}" if photo else None
    return f"{first}: {photo + ' ' if photo else ''}{content[:300]}"


def _trigger(m: dict, first: str, vehicles: dict) -> Optional[tuple]:
    """(kind, topic, trigger, source, ref) when this message opens a new episode because something new reached the thread."""
    typ, kind = m.get("type"), m.get("kind") or ""
    if typ == "webchat_transcript":
        body = (m.get("content") or "").partition("\n\n")[2]
        visitor = [ln.partition(": ")[2] for ln in body.split("\n") if ln.startswith("Visitor: ")]
        asked = (visitor[0] if visitor else "").strip()
        head = (m.get("content") or "").split("\n")[0]
        host = re.sub(r"^Web chat on\s+", "", head.split(" (")[0]).strip() or "the website"
        k = classify(" ".join(visitor)) or "general"
        return k, f"web chat on {host}: {('asked ' + chr(34) + asked[:90] + chr(34)) if asked else 'they asked for a person'}", f"a web chat hand-off from {host}", "webchat", m.get("webchat_sid") or ""
    if m.get("appraisal_id") or kind.startswith("trade_link"):
        veh = vehicles.get(str(m.get("appraisal_id") or ""), "")
        who = "they opened the trade link" if kind == "trade_link_opened" else "I sent them the trade link" if kind == "trade_link" else "their trade-in appraisal"
        return "trade_in", f"trade-in appraisal of their {veh}" if veh else "their trade-in appraisal", who, "appraisal", str(m.get("appraisal_id") or "")
    if m.get("is_lead_marker"):
        what = (m.get("content") or "").partition(" · ")[2].strip()
        k = classify(what) or ("vehicle" if re.search(r"\b(19|20)\d{2}\b", what) else "general")
        return k, f"a new lead: {what[:100]}" if what else "a new lead", "a new lead from this customer", "lead", ""
    return None


def build(messages: list, first: str, inquiry: Optional[dict] = None, vehicles: Optional[dict] = None, now: Optional[datetime] = None) -> ThreadView:
    now = now or datetime.now(timezone.utc)
    vehicles = vehicles or {}
    first = (first or "Customer").split(" ")[0]
    episodes: list = []
    cur: Optional[Episode] = None
    prev_ts: Optional[datetime] = None
    switched = False

    def open_ep(kind, topic, trigger, ts, source="text", ref=""):
        nonlocal cur
        cur = Episode(kind, topic, trigger, ts, ts, source=source, ref=ref)
        episodes.append(cur)

    for m in sorted(messages, key=lambda x: _utc(x.get("timestamp") or x.get("created_at"))):
        ts = _utc(m.get("timestamp") or m.get("created_at"))
        line = _line(m, first, ts)
        trig = _trigger(m, first, vehicles)
        switched = False
        if trig:
            kind, topic, trigger, source, ref = trig
            if not (cur and cur.source == source and cur.ref == ref and cur.kind == kind):
                open_ep(kind, topic, trigger, ts, source, ref)
        elif cur is None:
            if inquiry:
                open_ep(INQUIRY_KIND.get(inquiry.get("kind") or "general", "general"), inquiry.get("topic") or "", f"their {inquiry.get('source_name') or 'lead form'} inquiry", ts, "lead")
            else:
                k = classify(m.get("content") or "") if m.get("sender") == "contact" else None
                open_ep(k or "general", f"{KIND_LABEL.get(k, 'a conversation')}: \"{(m.get('content') or '')[:80]}\"" if k else "", "they texted" if m.get("sender") == "contact" else "I texted them", ts)
        elif m.get("sender") == "contact" and m.get("type") != "webchat_transcript":
            k = classify(m.get("content") or "")
            if k and k != cur.kind:
                if cur.kind == "general" and cur.customer_texts <= 1:
                    cur.kind, cur.topic = k, f"{KIND_LABEL[k]}: \"{(m.get('content') or '')[:80]}\""
                else:
                    open_ep(k, f"{KIND_LABEL[k]}: \"{(m.get('content') or '')[:80]}\"", "their texts moved to a new subject", ts)
                    switched = True
        if line is None:
            prev_ts = ts
            continue
        if prev_ts and cur.lines and (ts - prev_ts).total_seconds() > DIVIDER_GAP_H * 3600:
            cur.lines.append(f"--- {_ago(prev_ts, ts).replace(' ago', '')} later, {_day(ts)} ---")
        cur.lines.append(line)
        cur.ended_at = ts
        if m.get("sender") == "contact":
            if m.get("type") == "webchat_transcript":
                asked = [ln.partition(": ")[2] for ln in (m.get("content") or "").split("\n") if ln.startswith("Visitor: ")]
                cur.last_customer = cur.last_customer or " / ".join(a.strip() for a in asked if a.strip())[:200]
            else:
                cur.customer_texts += 1
                cur.last_customer = (m.get("content") or "").strip()[:200] or cur.last_customer
        prev_ts = ts
    return ThreadView(episodes=episodes, current=cur, switched=switched, now=now)


async def load(db, conversation_id: str, first: str = "", inquiry: Optional[dict] = None, limit: int = HISTORY) -> ThreadView:
    if not conversation_id:
        return ThreadView(episodes=[], current=None)
    rows = await db.messages.find({"conversation_id": str(conversation_id)}).sort("timestamp", -1).limit(limit).to_list(limit)
    if not first:
        conv = await db.conversations.find_one({"_id": ObjectId(str(conversation_id))}, {"contact_name": 1}) if ObjectId.is_valid(str(conversation_id)) else None
        first = ((conv or {}).get("contact_name") or "").split(" ")[0]
    ids = {str(m.get("appraisal_id")) for m in rows if m.get("appraisal_id") and ObjectId.is_valid(str(m.get("appraisal_id")))}
    vehicles = {}
    if ids:
        from services.appraisals.providers import vehicle_label
        async for a in db.vehicle_appraisals.find({"_id": {"$in": [ObjectId(i) for i in ids]}}, {"vehicle": 1}):
            if a.get("vehicle"):
                vehicles[str(a["_id"])] = vehicle_label(a["vehicle"])
    return build(rows, first, inquiry, vehicles)
