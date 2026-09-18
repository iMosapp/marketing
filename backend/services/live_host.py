"""Jessi hosts the rep's line on GPT-Live before a call goes through: on click-to-call she briefs the rep on who they are about to
call (name, vehicle, last thing they said, what the rep owes them, tags) and waits for "connect"; on a mystery shop she announces
the practice call (inbound or outbound, who is calling whom) and waits for "ready". Either way the rep can ask her questions first,
say "not now" to cancel, or press 1 / 2. When she is done the stream closes and Twilio continues to the action URL, which dials the
customer or rings the shopper. Same voice as Talk to Jessi (Voice Lab). Falls back to the classic <Say>/<Gather> gate when the
server has no OPENAI_API_KEY, the Test Lab switch is off, or the shop is not English."""
import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from bson import ObjectId

from services import lab
from services import live_shops as ls
from services import live_voice as lv
from services import locales as loc
from services import scripts as scr
from services.speech import numbers_rule, speakable
from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)

LAB_KEY = "live_host"
LAB_OFF = "the Test Lab switch 'Jessi hosts your calls' is off"
NUDGE_S = 18          # quiet after the brief -> one gentle nudge
MAX_QUIET_S = 45      # still nothing -> treated like an unanswered call
MAX_MIN = 3.0         # questions are fine, a briefing is not a meeting
DECIDED_CLOSE_S = 4   # Jessi said the handoff line but never delegated -> hand the call off anyway
GO = re.compile(r"\b(connect|ready|yes|yeah|yep|yup|go ahead|let'?s go|dial|do it|put (him|her|them) through|bring it|hit me|call (him|her|them)|i'?m good|sure|go|connect (him|her|them|me)|send it)\b", re.I)
LATER = re.compile(r"\b(not now|later|cancel|bad time|busy|hold off|never ?mind|skip( it)?|nope|no thanks|don'?t (call|connect|dial)|not (right )?now|stop)\b", re.I)
QUESTION = re.compile(r"\?|^\s*(what|when|who|where|why|how|did|does|do|is|are|was|has|have|any|tell me|remind me|which|can you|could you|say (that )?again|repeat)\b", re.I)
TAG_PRIORITY = ("hot", "vip", "sold", "referral", "repeat", "service")
CONNECT_LINE = "Connecting you now."
CANCEL_LINE = "No problem, I'll cancel it. Talk soon."
CLOSE_AFTER_REDIRECT_S = 3


def _now():
    return datetime.now(timezone.utc)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", str(text or "").lower()).strip()


def said_line(text: str, line: str) -> bool:
    """Did Jessi speak this handoff line (punctuation and case aside)?"""
    key = _norm(line)
    return bool(key) and key in _norm(text)


async def decide(db, kind: str, doc: dict) -> tuple[bool, str]:
    """(Jessi hosts?, why). kind 'call' = click-to-call rep leg, 'shop' = mystery shop announcement."""
    if kind == "shop" and loc.language(doc.get("locale")) != "en":
        return False, "not an English shop, Dutch keeps the classic announcement"
    reason = lv.configured()
    if reason:
        return False, ls.NO_KEY
    if await lab.is_live(db, LAB_KEY):
        return True, "Jessi hosts the line"
    return False, LAB_OFF


def _ws_base() -> str:
    return scr._app_url().replace("https://", "wss://").replace("http://", "ws://")


def after_url(kind: str, doc: dict) -> str:
    """Where the call goes once Jessi is done (plain URL, not XML-escaped)."""
    if kind == "call":
        return f"{scr._app_url()}/api/webhooks/twilio/call-bridge-host-after?pid={doc['_id']}&t={doc['token']}"
    return f"{scr._app_url()}/api/scripts/roleplay/host-after/{doc['_id']}?t={doc['token']}"


def _host_twiml(kind: str, doc: dict, ws_path: str) -> str:
    """<Connect action=after> with a <Redirect> to the same URL behind it: whichever way Twilio leaves the stream, the call continues."""
    after = scr._xml(after_url(kind, doc))
    return (f'<?xml version="1.0" encoding="UTF-8"?><Response><Connect action="{after}"><Stream url="{scr._xml(_ws_base())}{ws_path}" /></Connect>'
            f'<Redirect method="POST">{after}</Redirect></Response>')


def shop_twiml(session: dict) -> str:
    return _host_twiml("shop", session, f"/api/scripts/roleplay/host/{session['_id']}/{session['token']}")


def call_twiml(pending: dict) -> str:
    return _host_twiml("call", pending, f"/api/webhooks/twilio/call-host/{pending['_id']}/{pending['token']}")


async def redirect_call(call_sid: str, url: str) -> bool:
    """Move the live call to `url` through Twilio's REST API: Twilio fetches the TwiML right away and tears the stream down itself,
    so the handoff never depends on Twilio noticing our WebSocket close. False when there is no client or Twilio refuses."""
    import os
    sid, tok = os.environ.get("TWILIO_ACCOUNT_SID", ""), os.environ.get("TWILIO_AUTH_TOKEN", "")
    if not (call_sid and sid and tok):
        return False
    try:
        from twilio.rest import Client
        client = Client(sid, tok)
        await asyncio.to_thread(client.calls(call_sid).update, url=url, method="POST")
        return True
    except Exception as e:
        logger.warning(f"[LiveHost] redirect of {call_sid} failed, closing the stream instead: {e}")
        return False


# ── what Jessi knows going in ─────────────────────────────────────────────────
def _dt(v) -> Optional[datetime]:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, str):
        try:
            d = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def when_spoken(v, tz: ZoneInfo) -> str:
    d = _dt(v)
    if not d:
        return ""
    local, now = d.astimezone(tz), _now().astimezone(tz)
    days = (now.date() - local.date()).days
    if days <= 0:
        mins = max(0, int((now - local).total_seconds() // 60))
        return "just now" if mins < 2 else f"{mins} minutes ago" if mins < 90 else "earlier today"
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"on {local.strftime('%A')}"
    return f"on {local.strftime('%B')} {local.day}"


def _quote(text: str, n: int = 140) -> str:
    t = re.sub(r"\s+", " ", str(text or "")).strip().strip('"')
    return t if len(t) <= n else t[: n - 1].rsplit(" ", 1)[0] + "..."


async def _rep_tz(user_id: str) -> ZoneInfo:
    try:
        from routers.user_schedule import resolve_user_tz
        return ZoneInfo(await resolve_user_tz(str(user_id)))
    except Exception:
        return ZoneInfo("America/Denver")


async def call_brief(db, pending: dict) -> dict:
    """The click-to-call briefing: who, what they drive or want, the last thing they said or the rep noted, the open task, the tags that matter."""
    from services.live_actions import OPEN_TASK
    uid = str(pending.get("rep_user_id") or "")
    rep = await db.users.find_one({"_id": ObjectId(uid)}, {"name": 1, "first_name": 1}) if ObjectId.is_valid(uid) else None
    rep_first = (rep or {}).get("first_name") or ((rep or {}).get("name") or pending.get("rep_name") or "").split(" ")[0] or "there"
    tz = await _rep_tz(uid)
    contact = await db.contacts.find_one({"_id": ObjectId(str(pending["contact_id"]))}) if ObjectId.is_valid(str(pending.get("contact_id") or "")) else None
    phone = pending.get("customer_phone") or ""
    if not contact:
        who = f"the number ending in {phone[-4:]}" if phone else "the customer"
        return {"rep_first": rep_first, "customer_first": "them", "who": who, "facts": [], "opener": f"Hey {rep_first}, calling {who}. Say connect when you're ready, or not now to cancel.", "record": ""}
    name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip() or contact.get("name") or "the customer"
    first = contact.get("first_name") or name.split(" ")[0]
    cid = str(contact["_id"])
    facts = []
    vehicle = contact.get("vehicle") or contact.get("vehicle_interest") or (contact.get("personal_details") or {}).get("vehicle")
    if vehicle:
        facts.append(f"{'Drives' if contact.get('vehicle') else 'Looking at'} {vehicle}.")
    # the freshest thing they said or the rep noted
    convs = [str(c["_id"]) for c in await db.conversations.find({"contact_id": cid}, {"_id": 1}).to_list(20)]
    last_msg = await db.messages.find_one({"conversation_id": {"$in": convs}, "sender": "contact", "type": {"$ne": "call_log"}, "content": {"$nin": [None, ""]}}, sort=[("timestamp", -1)]) if convs else None
    last_memo = await db.voice_notes.find_one({"contact_id": cid, "$or": [{"summary": {"$nin": [None, ""]}}, {"transcript": {"$nin": [None, ""]}}]}, sort=[("created_at", -1)])
    said = []
    if last_msg:
        said.append((_dt(last_msg.get("timestamp") or last_msg.get("created_at")) or _now(), f"{when_spoken(last_msg.get('timestamp') or last_msg.get('created_at'), tz)} {first} texted: \"{_quote(last_msg.get('content'))}\"."))
    if last_memo:
        said.append((_dt(last_memo.get("created_at")) or _now(), f"Your note {when_spoken(last_memo.get('created_at'), tz)}: \"{_quote(last_memo.get('summary') or last_memo.get('transcript'))}\"."))
    if said:
        said.sort(key=lambda x: x[0], reverse=True)
        line = said[0][1].strip()
        facts.append(line[0].upper() + line[1:])
    elif contact.get("notes"):
        facts.append(f"Your note: \"{_quote(contact['notes'])}\".")
    task = await db.tasks.find_one({"user_id": uid, "contact_id": cid, "status": OPEN_TASK, "completed": {"$ne": True}}, sort=[("due_date", 1)])
    if task and task.get("title"):
        due = _dt(task.get("due_date"))
        when = ""
        if due:
            days = (due.astimezone(tz).date() - _now().astimezone(tz).date()).days
            when = ", overdue" if days < 0 else ", due today" if days == 0 else f", due {when_spoken(due, tz).replace('on ', '')}" if days < 7 else ""
        facts.append(f"You owe them: {_quote(task['title'], 90)}{when}.")
    tags = [t for t in (contact.get("tags") or []) if isinstance(t, str) and t.strip()]
    tags.sort(key=lambda t: next((i for i, p in enumerate(TAG_PRIORITY) if p in t.lower()), len(TAG_PRIORITY)))
    if tags:
        facts.append(f"Tagged {', '.join(tags[:3])}.")
    opener = f"Hey {rep_first}, calling {name}{f' about {vehicle}' if vehicle else ''}. " + " ".join(facts[1:] if vehicle else facts) + " Say connect when you're ready, or ask me anything first."
    return {"rep_first": rep_first, "customer_first": first, "who": name, "facts": facts, "opener": no_em_dash(re.sub(r"\s+", " ", opener)).strip(), "contact_id": cid, "rep_user_id": uid}


def shop_brief(session: dict) -> dict:
    first = (session.get("rep_name") or "").split(" ")[0] or "there"
    lines = scr.GO_LINES["en"]
    go_line = lines[0] if session.get("direction") == "inbound" else lines[1]
    later_line = "No problem, we'll try another time. Good luck out there." if session.get("demo") or session.get("manual") else "No problem, we'll call back in a couple of hours. Good luck out there."
    return {"rep_first": first, "opener": scr.shop_announcement(session), "go_line": go_line, "later_line": later_line,
            "direction": session.get("direction") or "inbound", "store": session.get("store_name") or "the store", "persona_first": ((session.get("persona") or {}).get("name") or "").split(" ")[0]}


# ── instructions ──────────────────────────────────────────────────────────────
STYLE = ("Sound like a sharp, warm assistant on the phone: contractions, one or two short sentences at a time, no lists, no filler, never say 'great question'. "
         "You are talking to the REP only; the customer is not on the line and never will be while you are. "
         "Interruption policy: stop speaking the moment the rep talks over you and listen. Backchannel policy: none. No em dashes. ")


def instructions(kind: str, brief: dict, cfg: dict) -> str:
    if kind == "call":
        facts = " ".join(brief.get("facts") or []) or "Nothing else on file."
        return (f"You are Jessi, {brief['rep_first']}'s assistant at I'm On Social, on the line with {brief['rep_first']} for a few seconds before their call to {brief['who']} goes through. "
                f"You speak first, right away: \"{brief['opener']}\" (your own words are fine, every fact kept, under 20 seconds). Then wait.\n"
                f"FACTS YOU HAVE: {facts}\n"
                f"WHAT HAPPENS NEXT: when the rep says connect, ready, yes, go, dial or presses 1: say exactly \"{CONNECT_LINE}\" and then delegate to the backend immediately; the backend dials {brief['customer_first']}. "
                f"When the rep says not now, later, cancel, skip or presses 2: say \"{CANCEL_LINE}\" and delegate immediately. "
                "When the rep asks something about the customer: answer from FACTS in one or two sentences, then ask 'ready to connect?'. If FACTS do not cover it, delegate; the backend whispers the answer to you, then you say it. "
                "Never make anything up about the customer. Never delegate for anything else. After you delegate, say nothing more.\n"
                + STYLE + numbers_rule("en-US"))
    return (f"You are Jessi from I'm On Social, calling {brief['rep_first']} with a practice call. You speak first, right away: \"{brief['opener']}\" (your own words are fine, every fact kept). Then wait.\n"
            f"WHAT HAPPENS NEXT: when the rep says ready, yes, go, okay or presses 1: say exactly \"{brief['go_line']}\" and then delegate to the backend immediately; the backend rings the {'customer' if brief['direction'] == 'inbound' else 'lead'} in. "
            f"When the rep says not now, later, busy or presses 2: say \"{brief['later_line']}\" and delegate immediately. "
            f"If the rep asks what the call is about: it is a {brief['direction']} practice call, graded on the store's scorecard, like a real customer; one sentence, then ask if they are ready. "
            "Never reveal who the customer will be, what they want, their objections or the scorecard items: the shopper is a surprise. Never delegate for anything else. After you delegate, say nothing more.\n"
            + STYLE + numbers_rule("en-US"))


FILLER = re.compile(r"^(?:(?:okay|ok|so|yeah|yes|yep|sure|right|cool|great|fine|good|well|oh|no|um|uh|alright|all right|hey|wait|wait wait|hold on|hang on|jessi|jessie|and|but|first|actually|quick question|one question|before that|real quick)[,.!]?\s+)+", re.I)
GREETING = re.compile(r"^(hello|hi|hey|yo|hello there|hi there|good (morning|afternoon|evening))(\s+(this is|it'?s)\s+\w+)?$", re.I)


def intent(text: str) -> str:
    """go | later | question | other, from what the rep just said."""
    t = " ".join((text or "").lower().split()).rstrip(".!")
    if not t or GREETING.match(t.rstrip("?")):
        return "other"
    words = t.split()
    if words[0].strip(",") in ("no", "nah", "nope") and len(words) <= 3:
        return "later"
    later, go = LATER.search(t), GO.search(t)
    if later and not (go and go.start() < later.start() and words[0] != "no"):
        return "later"
    core = FILLER.sub("", t) or t
    if QUESTION.search(core) and not (go and len(words) <= 3):
        return "question"
    return "go" if go else "other"


def describe(doc: dict) -> Optional[dict]:
    """What the app shows about the host leg of a call."""
    h = (doc or {}).get("host")
    if not isinstance(h, dict):
        return None
    return {"transport": h.get("transport"), "decision": h.get("decision"), "via": h.get("via"), "skip_reason": h.get("skip_reason"), "seconds": h.get("seconds"), "voice": h.get("voice")}


async def answer_question(db, brief: dict, question: str) -> str:
    """A spoken one-or-two-sentence answer about the customer from everything on file."""
    try:
        from services import contact_ask
        contact = await db.contacts.find_one({"_id": ObjectId(brief["contact_id"])}) if ObjectId.is_valid(str(brief.get("contact_id") or "")) else None
        if not contact:
            return "I have nothing else on file for them."
        rec = await contact_ask.build_record(db, contact)
        text = rec.get("text") if isinstance(rec, dict) else str(rec)
        lines = [l for l in str(text or "").split("\n") if l.strip()]
        record = "\n".join(lines[-80:])[-6000:]
        out = await scr._llm("You are Jessi, a sales rep's assistant, answering ONE spoken question about a customer right before the rep calls them. Use only the record below. "
                             "Answer in one or two short spoken sentences, plain words, dates as 'last Tuesday' style, no citations, no lists, no em dashes. If the record does not say, say so in one sentence.\n\nRECORD:\n" + record,
                             question, timeout=15)
        return no_em_dash(speakable(out.strip(), "en-US"))[:400] or "I have nothing on that."
    except Exception as e:
        logger.debug(f"[LiveHost] answer failed: {e}")
        return "I could not pull that up in time. Ready to connect?"


# ── the bridge ────────────────────────────────────────────────────────────────
class HostBridge(ls.Bridge):
    TURNS_FIELD = "host.turns"
    ASSISTANT_ROLE = "jessi"
    TAG = "LiveHost"

    def __init__(self, db, doc: dict, kind: str, twilio_send, twilio_close, connect=ls.connect_openai):
        super().__init__(db, doc, twilio_send, twilio_close, connect)
        self.kind = kind
        self.COLL = "pending_calls" if kind == "call" else "roleplay_sessions"
        self.brief: dict = {}
        self.decision: Optional[str] = None
        self.decided_at: Optional[float] = None
        self.nudged = False
        self.last_rep_at: Optional[float] = None
        self.call_sid: Optional[str] = None
        self.handed_off = False

    async def session_config(self) -> dict:
        cfg = await lv.get_config(self.db)
        self.brief = await call_brief(self.db, self.s) if self.kind == "call" else shop_brief(self.s)
        return {"instructions": instructions(self.kind, self.brief, cfg), "voice": cfg["voice"]}

    async def _mark_live(self, call_sid: Optional[str]):
        self.started_at = _now()
        self.call_sid = call_sid or self.s.get("call_sid")
        await self.col.update_one({"_id": self.s["_id"]}, {"$set": {"host.started_at": self.started_at, "host.voice": self.cfg.get("voice"), "host.transport": "gpt-live", "host.opener": self.brief.get("opener"), "host.call_sid": self.call_sid, "updated_at": self.started_at}})

    async def on_started(self):
        line = self.brief.get("opener") or ""
        await self.up.send({"type": "session.instructions.append", "event_id": "open_1", "delegation_id": None, "content": f'The rep just picked up. Speak first, now, in your own words with every fact kept: "{line}"'})
        await self.up.send({"type": "session.commentary.append", "event_id": "open_2", "delegation_id": None, "content": line})

    def decorate(self, turn: dict) -> dict:
        return turn

    def _lines(self) -> tuple[str, str]:
        if self.kind == "call":
            return CONNECT_LINE, CANCEL_LINE
        return self.brief.get("go_line") or "", self.brief.get("later_line") or ""

    async def after_flush(self, turn: dict):
        if turn["role"] == "rep":
            self.last_rep_at = asyncio.get_event_loop().time()
            what = intent(turn["text"])
            if what in ("go", "later") and not self.decision:
                await self._decide(what, "speech")
        elif not self.decision:
            # Jessi only speaks the handoff lines when the rep asked for them: her own words are the surest signal
            go_line, later_line = self._lines()
            if said_line(turn["text"], go_line):
                await self._decide("go", "jessi")
            elif said_line(turn["text"], later_line):
                await self._decide("later", "jessi")

    async def on_dtmf(self, digit: str):
        if digit == "1":
            await self._decide("go", "dtmf")
        elif digit == "2":
            await self._decide("later", "dtmf")

    async def _decide(self, choice: str, via: str):
        if self.decision:
            return
        self.decision = choice
        self.decided_at = asyncio.get_event_loop().time()
        await self.col.update_one({"_id": self.s["_id"]}, {"$set": {"host.decision": choice, "host.via": via, "host.decided_at": _now(), "updated_at": _now()}})
        line = (CONNECT_LINE if choice == "go" else CANCEL_LINE) if self.kind == "call" else (self.brief["go_line"] if choice == "go" else self.brief["later_line"])
        if via == "dtmf" and self.up:
            await self.up.send({"type": "session.instructions.append", "event_id": f"dtmf_{choice}", "delegation_id": None, "content": f'The rep pressed {"1" if choice == "go" else "2"}. Say exactly "{line}" now and delegate to the backend immediately after.'})
        logger.info(f"[LiveHost] {self.sid} {self.kind}: {choice} via {via}")

    async def _delegation(self, delegation_id: Optional[str]):
        await self._flush()
        if self.decision:
            await self.hang_up(delegation_id, self.decision)
            return
        doc = await self.col.find_one({"_id": self.s["_id"]}, {"host.turns": 1})
        turns = ((doc or {}).get("host") or {}).get("turns") or []
        last_rep = next((t.get("text") for t in reversed(turns) if t.get("role") == "rep"), "")
        what = intent(last_rep)
        if what in ("go", "later"):
            await self._decide(what, "speech")
            await self.hang_up(delegation_id, what)
        elif what == "question" and self.kind == "call":
            answer = await answer_question(self.db, self.brief, last_rep)
            await self.up.send({"type": "session.thinking.append", "event_id": f"ans_{delegation_id}", "delegation_id": delegation_id, "content": f"Backend answer, say it in your own words then ask if they are ready to connect: {answer}"})
        else:
            # always answer a delegation, or the model waits in silence
            await self.up.send({"type": "session.thinking.append", "event_id": f"stay_{delegation_id}", "delegation_id": delegation_id,
                                "content": "Nothing to look up here. " + ("Ask the rep if they are ready to connect, or if they want to cancel." if self.kind == "call" else "Ask the rep if they are ready, or if now is a bad time.")})

    async def _drain_then_hangup(self, reason: str):
        """Let Jessi finish the line, then hand the call to its next TwiML (REST redirect first, WebSocket close as the fallback)."""
        loop = asyncio.get_event_loop()
        deadline = loop.time() + 6
        while loop.time() < deadline and loop.time() - self.last_output_at < 1.6:
            await asyncio.sleep(0.2)
        await asyncio.sleep(0.8)
        await self._handoff(reason)

    async def _handoff(self, reason: str):
        if self.handed_off or self.closed:
            return
        self.handed_off = True
        moved = await redirect_call(self.call_sid or "", after_url(self.kind, self.s))
        await self.col.update_one({"_id": self.s["_id"]}, {"$set": {"host.handoff": "rest" if moved else "ws_close", "updated_at": _now()}})
        logger.info(f"[LiveHost] {self.sid} {self.kind}: handoff via {'REST redirect' if moved else 'stream close'} ({reason})")
        if moved:
            # Twilio is already fetching the next TwiML and will stop the stream; close ourselves shortly in case it does not
            self.tasks.append(asyncio.get_event_loop().create_task(self._close_later(reason)))
        else:
            await self.close(reason)

    async def _close_later(self, reason: str):
        try:
            await asyncio.sleep(CLOSE_AFTER_REDIRECT_S)
            await self.close(reason)
        except asyncio.CancelledError:
            pass

    async def _watchdog(self):
        loop = asyncio.get_event_loop()
        try:
            while not self.closed:
                await asyncio.sleep(0.5)
                if not self.ready:
                    continue
                now = loop.time()
                if self.decision and self.decided_at and now - self.decided_at >= DECIDED_CLOSE_S:
                    await self._handoff(self.decision)
                    continue
                quiet_since = max(self.last_rep_at or 0.0, self.last_output_at or 0.0)
                if quiet_since and not self.decision and not self.nudged and now - quiet_since >= NUDGE_S:
                    self.nudged = True
                    await self.up.send({"type": "session.commentary.append", "event_id": "nudge_1", "delegation_id": None,
                                        "content": "Ready when you are. Say connect, or not now." if self.kind == "call" else "Ready when you are. Say ready, or not now."})
                if quiet_since and not self.decision and now - quiet_since >= MAX_QUIET_S:
                    await self._decide("none", "silence")
                    await self._handoff("none")
                if not self.decision and self.minutes() >= MAX_MIN:
                    await self._decide("none", "timeout")
                    await self._handoff("none")
        except asyncio.CancelledError:
            pass

    async def _record_close(self, reason: str):
        if not self.decision:
            self.decision = "none"
            await self.col.update_one({"_id": self.s["_id"]}, {"$set": {"host.decision": "none", "host.via": reason}})
        await self.col.update_one({"_id": self.s["_id"]}, {"$set": {"host.seconds": self.seconds, "host.cost_usd": round(self.seconds / 60 * lv.PRICE_PER_MIN, 4), "host.end_reason": reason, "host.ended_at": _now(), "updated_at": _now()}})
