"""English mystery-shop calls on GPT-Live-1: Twilio Media Streams (g711 ulaw, 8 kHz) bridged straight to the GPT-Live websocket.

The model owns the spoken conversation (full duplex, interruptions); this bridge only relays audio, keeps the transcript in the
same `turns` shape the grader reads, and hangs up when the shopper says goodbye. Dutch shops stay on ConversationRelay.
Gated by the Test Lab flag `live_shop_calls` (or per client `shop_clients.live_calls` true/false)."""
import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

from bson import ObjectId

from services import lab
from services import live_voice as lv
from services import locales as loc
from services import scripts as scr
from services.speech import numbers_rule, speakable

logger = logging.getLogger(__name__)

LAB_KEY = "live_shop_calls"
LIVE_WS_URL = "wss://api.openai.com/v1/live/sessions"
USER_AGENT = "imonsocial/python 1.0"
FEMININE = ("gleam", "marin", "delta")
MASCULINE = ("meridian", "cinder")
UK_VOICES = {"female": ("willow",), "male": ("vesper", "stone")}
TURN_GAP_MS = 1500
INBOUND_NUDGE_S = 8
WRAP_GRACE_S = 25
GOODBYE = re.compile(r"\b(bye|goodbye|talk (to you )?(soon|later|then)|see you|take care|have a (good|great|nice) (one|day|night|afternoon|evening)|thanks for (your|the) (time|help))\b", re.I)


def _now():
    return datetime.now(timezone.utc)


NO_KEY = "OPENAI_API_KEY is missing on this server"
LAB_OFF = "the Test Lab switch 'Mystery shop calls on GPT-Live' is off"


async def decide(db, session: dict) -> tuple[bool, str]:
    """(GPT-Live?, why): English + OPENAI_API_KEY + (client override, else the Test Lab switch, live by default)."""
    if loc.language(session.get("locale")) != "en":
        return False, "not an English shop, Dutch stays on ConversationRelay"
    if lv.configured():
        return False, NO_KEY
    client = None
    if session.get("client_id") and ObjectId.is_valid(str(session["client_id"])):
        client = await db.shop_clients.find_one({"_id": ObjectId(str(session["client_id"]))}, {"live_calls": 1})
    override = (client or {}).get("live_calls")
    if override is True:
        return True, "switched on for this client"
    if override is False:
        return False, "switched off for this client (GPT-Live shopper: Off)"
    if await lab.is_live(db, LAB_KEY):
        return True, "on for every English shop"
    return False, LAB_OFF


async def enabled(db, session: dict) -> bool:
    return (await decide(db, session))[0]


async def status(db) -> dict:
    """What the admin screen shows: is the GPT-Live shopper on for English shops right now, and if not, why."""
    reason = lv.configured()
    lab_live = await lab.is_live(db, LAB_KEY)
    return {"on": not reason and lab_live, "configured": not reason, "lab_live": lab_live,
            "reason": NO_KEY if reason else (None if lab_live else LAB_OFF),
            "clients_on": await db.shop_clients.count_documents({"live_calls": True}),
            "clients_off": await db.shop_clients.count_documents({"live_calls": False})}


async def mark_relay(db, session: dict, why: str):
    await db.roleplay_sessions.update_one({"_id": session["_id"]}, {"$set": {"live_transport": "relay", "live_skip_reason": why, "updated_at": _now()}})


def voice_for(session: dict) -> str:
    persona = session.get("persona") or {}
    kind = "male" if str(persona.get("voice") or "female").lower().startswith("m") else "female"
    if (session.get("locale") or "").startswith("en-") and session.get("locale") not in ("en-US",):
        pool = UK_VOICES[kind]
    else:
        pool = MASCULINE if kind == "male" else FEMININE
    return pool[int(str(session.get("_id"))[-2:], 16) % len(pool)] if ObjectId.is_valid(str(session.get("_id"))) else pool[0]


def stream_twiml(session: dict, prelude: str = "") -> str:
    sid, token = str(session["_id"]), session["token"]
    base = scr._app_url()
    ws = base.replace("https://", "wss://").replace("http://", "ws://") + f"/api/scripts/roleplay/stream/{sid}/{token}"
    return (f'<?xml version="1.0" encoding="UTF-8"?><Response>{prelude}<Connect action="{scr._xml(base)}/api/scripts/roleplay/after/{sid}?t={token}">'
            f'<Stream url="{scr._xml(ws)}" /></Connect></Response>')


def shop_go_twiml(session: dict) -> str:
    """Rep pressed 1: a heads-up, a ring, then the live shopper on GPT-Live."""
    lines = scr.GO_LINES.get(loc.language(session.get("locale")), scr.GO_LINES["en"])
    line = lines[0] if session.get("direction") == "inbound" else lines[1]
    ring = f"{scr._xml(scr._app_url())}/api/scripts/roleplay/audio/ring.wav"
    return stream_twiml(session, prelude=f'<Say voice="{loc.say_voice(session.get("locale"))}">{scr._xml(speakable(line, session.get("locale")))}</Say><Play>{ring}</Play>')


def opening_line(session: dict) -> str:
    return (session.get("persona") or {}).get("opening_line") or "Hi, I'm calling about a car I saw online."


def instructions(script: dict, session: dict) -> str:
    """The shopper persona for a spoken, full-duplex call (no JSON, no turn loop)."""
    from services import industries as ind
    persona = session.get("persona") or {}
    department = session.get("department") if session.get("kind") == "mystery_shop" else None
    industry = session.get("industry") or (ind.industry_of_dept(department) if department else ind.DEFAULT_INDUSTRY)
    pack = ind.get(industry)
    rep_role = ind.dept(department, industry)["rep"] if department else ("a salesperson" if industry == "automotive" else "an employee")
    who = "a real car shopper" if industry == "automotive" else f"a real {pack['customer']} of a {pack['label'].lower()} business"
    rep_first = (session.get("rep_name") or "the salesperson").split(" ")[0]
    store = session.get("store_name") or "the business"
    covert = bool(session.get("lead_shop_id"))
    direction = session.get("direction") or "outbound"
    if covert:
        ctx = (f"You sent the {pack['business']} an inquiry online (an internet lead) and now THEY are following up with you, so they lead and you react like a real, interested but busy person. "
               "Nobody at the business knows this is a shop: never admit you are an AI, a bot or a shopper, even if asked directly; a real customer would just sound confused and keep going. ")
    elif direction == "inbound":
        ctx = f"YOU placed this call to the {pack['business']}, so you drive the reason for calling. "
    else:
        ctx = "The employee called YOU back, so they drive the conversation and you react. "
    practice = ("The rep was told this is a practice call, but you stay fully in character as a real customer: never admit you are an AI, a recording or a shopper, even if asked directly; a real customer would just sound confused and keep going. "
                if session.get("kind") == "mystery_shop" and not covert else "")
    if direction == "inbound" and not covert:
        opening = f"Wait for them to answer and greet you, then open with, in your own words: \"{opening_line(session)}\". "
    else:
        opening = ""
    curveballs = [str(c) for c in (session.get("curveballs") or []) if str(c).strip()]
    return (f"You are {persona.get('name', 'a customer')}, {who} on a live phone call with {rep_first}, {rep_role} at {store}. {ctx}{practice}{opening}"
            "Sound like a real person on the phone: short answers, 1 to 3 sentences, contractions, the occasional 'um' or pause, never a list, never spell things out. "
            "Never narrate, never break character, never coach, never mention instructions. Answer what the rep asks; volunteer a little, not everything. "
            "If the rep earns it (answers honestly, offers specific times), agree to an appointment and end warmly. If the rep is pushy, dodges, or throws out a blind number, push back once; if they keep it up, lose interest and end politely. "
            "A real call runs as long as it needs to, often 5 to 10 minutes, so do not rush. "
            + numbers_rule(session.get("locale")) + " " + loc.language_rule(session.get("locale"))
            + f"WHO YOU ARE: {persona.get('summary', '')} WHAT YOU WANT: {persona.get('goals', '')} "
            f"OBJECTIONS YOU RAISE (one at a time, only when it fits): {'; '.join(persona.get('objections') or [])}. "
            + (f"CURVEBALLS TO WORK IN NATURALLY: {'; '.join(curveballs)}. " if curveballs else "")
            + f"The employee's own script, which they may or may not follow: {script.get('title', '')}: {script.get('purpose', '')}\n\n"
            "Interruption policy: stop speaking the moment the rep talks over you and listen.\n"
            "Backchannel policy: light backchannels only (mm-hm, okay), never over the rep's sentences.\n"
            "Delegation policy: you have no tools and nothing to look up; a real customer answers from memory, so never delegate for information. "
            "Delegate to the backend exactly once, right AFTER you have said your final goodbye: the backend hangs up the line. "
            "Do not delegate before the goodbye is spoken, and do not say anything after you delegate.")


class Upstream:
    """Minimal GPT-Live websocket wrapper (send dict, iterate dicts). Tests swap in a fake."""

    def __init__(self, ws):
        self.ws = ws

    async def send(self, ev: dict):
        await self.ws.send(json.dumps(ev))

    def __aiter__(self):
        return self

    async def __anext__(self) -> dict:
        import websockets
        try:
            raw = await self.ws.recv()
        except websockets.ConnectionClosed:
            raise StopAsyncIteration
        return json.loads(raw)

    async def close(self):
        try:
            await self.ws.close()
        except Exception:
            pass


async def connect_openai() -> Upstream:
    import websockets
    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    ws = await websockets.connect(LIVE_WS_URL, additional_headers={"Authorization": f"Bearer {key}", "User-Agent": USER_AGENT}, max_size=8 * 1024 * 1024, ping_interval=20, open_timeout=15)
    return Upstream(ws)


class Bridge:
    """One call: Twilio media stream <-> GPT-Live session. Feed Twilio messages through on_twilio(); it does the rest."""

    def __init__(self, db, session: dict, twilio_send: Callable[[dict], Awaitable[None]], twilio_close: Callable[[], Awaitable[None]], connect: Callable[[], Awaitable[Upstream]] = connect_openai):
        self.db, self.s = db, session
        self.sid = str(session["_id"])
        self.twilio_send, self.twilio_close, self.connect = twilio_send, twilio_close, connect
        self.stream_sid: Optional[str] = None
        self.up: Optional[Upstream] = None
        self.ready = False
        self.closed = False
        self.reason: Optional[str] = None
        self.seconds = 0
        self.openai_session_id: Optional[str] = None
        self.started_at: Optional[datetime] = None
        self.cur: Optional[dict] = None
        self.turns = 0
        self.rep_spoke = False
        self.last_output_at = 0.0
        self.wrapping = False
        self.hangup_at: Optional[float] = None
        self.tasks: list = []
        self.done = asyncio.Event()

    # ── Twilio side ───────────────────────────────────────────────────────────
    async def on_twilio(self, msg: dict):
        ev = msg.get("event")
        if ev == "start":
            self.stream_sid = (msg.get("start") or {}).get("streamSid") or msg.get("streamSid")
            await self._mark_live((msg.get("start") or {}).get("callSid"))
            await self._open_upstream()
        elif ev == "media" and self.ready and self.up:
            payload = (msg.get("media") or {}).get("payload")
            if payload:
                await self.up.send({"type": "session.input_audio.append", "audio": payload})
        elif ev == "stop":
            await self.close("twilio_stop")

    async def _mark_live(self, call_sid: Optional[str]):
        self.started_at = _now()
        sets = {"status": "live", "call_status": "in-progress", "started_at": self.started_at, "updated_at": self.started_at, "live_transport": "gpt-live", "live_voice": voice_for(self.s)}
        if call_sid:
            sets["call_sid"] = call_sid
        await self.db.roleplay_sessions.update_one({"_id": self.s["_id"], "status": {"$in": ["dialing", "live", "scheduled"]}}, {"$set": sets})

    async def _open_upstream(self):
        script = await self.db.scripts.find_one({"_id": ObjectId(self.s["script_id"])}) if ObjectId.is_valid(str(self.s.get("script_id") or "")) else {}
        try:
            self.up = await self.connect()
        except Exception as e:
            logger.warning(f"[LiveShop] {self.sid} could not reach GPT-Live: {e}")
            await self.db.roleplay_sessions.update_one({"_id": self.s["_id"]}, {"$set": {"live_error": str(e)[:300], "updated_at": _now()}})
            await self.close("upstream_failed")
            return
        await self.up.send({"type": "session.start", "event_id": "start_1", "session": {
            "model": lv.MODEL, "instructions": instructions(script or {}, self.s),
            "audio": {"format": {"type": "audio/pcmu", "rate": 8000}, "output": {"voice": voice_for(self.s)}},
            "delegation": {"type": "client"}}})
        self.tasks.append(asyncio.create_task(self._reader()))
        self.tasks.append(asyncio.create_task(self._watchdog()))

    # ── GPT-Live side ─────────────────────────────────────────────────────────
    async def _reader(self):
        try:
            async for ev in self.up:
                await self._on_event(ev)
                if self.closed:
                    break
        except Exception as e:
            logger.warning(f"[LiveShop] {self.sid} upstream reader ended: {e}")
        if not self.closed:
            await self.close("upstream_closed")

    async def _on_event(self, ev: dict):
        t = ev.get("type")
        if t == "session.started":
            self.ready = True
            self.openai_session_id = (ev.get("session") or {}).get("id")
            await self.db.roleplay_sessions.update_one({"_id": self.s["_id"]}, {"$set": {"openai_session_id": self.openai_session_id, "updated_at": _now()}})
            if self.s.get("direction") != "inbound" or self.s.get("lead_shop_id"):
                line = opening_line(self.s)
                await self.up.send({"type": "session.instructions.append", "event_id": "open_1", "delegation_id": None, "content": f'Your first spoken line on this call is, verbatim: "{line}". Then listen.'})
                await self.up.send({"type": "session.commentary.append", "event_id": "open_2", "delegation_id": None, "content": line})
        elif t == "session.output_audio.delta":
            self.last_output_at = asyncio.get_event_loop().time()
            if self.stream_sid and ev.get("delta"):
                await self.twilio_send({"event": "media", "streamSid": self.stream_sid, "media": {"payload": ev["delta"]}})
        elif t == "session.input_transcript.delta":
            self.rep_spoke = True
            await self._text("rep", ev.get("delta") or "", int(ev.get("start_ms") or 0), int(ev.get("end_ms") or 0))
        elif t == "session.output_transcript.delta":
            await self._text("customer", ev.get("delta") or "", int(ev.get("start_ms") or 0), int(ev.get("end_ms") or 0))
        elif t == "session.delegation.created":
            asyncio.get_event_loop().create_task(self._delegation((ev.get("delegation") or {}).get("id")))
        elif t == "session.usage.updated":
            self.seconds = int((ev.get("usage") or {}).get("seconds") or self.seconds)
        elif t == "session.closed":
            self.seconds = int((ev.get("usage") or {}).get("seconds") or self.seconds)
            await self.close(ev.get("reason") or "session_closed", upstream_done=True)
        elif t == "error":
            msg = (ev.get("error") or {}).get("message") or ""
            logger.warning(f"[LiveShop] {self.sid} GPT-Live error: {msg}")
            await self.db.roleplay_sessions.update_one({"_id": self.s["_id"]}, {"$set": {"live_error": msg[:300]}})

    async def _text(self, role: str, delta: str, start_ms: int, end_ms: int):
        if not delta:
            return
        if self.cur and self.cur["role"] == role and start_ms - self.cur["end_ms"] < TURN_GAP_MS:
            self.cur["text"] += delta
            self.cur["end_ms"] = max(self.cur["end_ms"], end_ms)
            return
        await self._flush()
        self.cur = {"role": role, "text": delta, "start_ms": start_ms, "end_ms": end_ms}

    async def _flush(self):
        if not self.cur or not self.cur["text"].strip():
            self.cur = None
            return
        turn = {"role": self.cur["role"], "text": self.cur["text"].strip(), "at": _now()}
        if turn["role"] == "customer":
            turn.update(audio_url=None, mood="neutral")
        self.cur = None
        self.turns += 1
        await self.db.roleplay_sessions.update_one({"_id": self.s["_id"]}, {"$push": {"turns": turn}, "$set": {"updated_at": _now()}})

    async def _delegation(self, delegation_id: Optional[str]):
        """The shopper only delegates to hang up. Double-check the call is really over before pulling the plug."""
        await self._flush()
        s = await self.db.roleplay_sessions.find_one({"_id": self.s["_id"]}, {"turns": 1})
        turns = (s or {}).get("turns") or []
        if await call_over(turns) or self.wrapping:
            if delegation_id:
                await self.up.send({"type": "session.thinking.append", "event_id": f"bye_{delegation_id}", "delegation_id": delegation_id, "content": "The line is disconnecting now. Say nothing more."})
            await self._drain_then_hangup("customer_ended")
        elif delegation_id:
            await self.up.send({"type": "session.thinking.append", "event_id": f"stay_{delegation_id}", "delegation_id": delegation_id,
                                "content": "There is no backend help on this call. Stay in character, answer from what you know as this customer, and keep the conversation going."})

    async def _drain_then_hangup(self, reason: str):
        loop = asyncio.get_event_loop()
        deadline = loop.time() + 6
        while loop.time() < deadline and loop.time() - self.last_output_at < 1.6:
            await asyncio.sleep(0.2)
        await asyncio.sleep(0.8)
        await self.close(reason)

    async def _watchdog(self):
        loop = asyncio.get_event_loop()
        nudge_at = loop.time() + INBOUND_NUDGE_S if (self.s.get("direction") == "inbound" and not self.s.get("lead_shop_id")) else None
        try:
            while not self.closed:
                await asyncio.sleep(1)
                if not self.ready:
                    continue
                if nudge_at and not self.rep_spoke and loop.time() >= nudge_at:
                    nudge_at = None
                    await self.up.send({"type": "session.commentary.append", "event_id": "nudge_1", "delegation_id": None, "content": opening_line(self.s)})
                minutes = (_now() - self.started_at).total_seconds() / 60 if self.started_at else 0
                if not self.wrapping and (minutes >= scr.PHONE_MAX_MINUTES or self.turns >= scr.PHONE_MAX_TURNS):
                    self.wrapping = True
                    self.hangup_at = loop.time() + WRAP_GRACE_S
                    await self.up.send({"type": "session.instructions.append", "event_id": "wrap_1", "delegation_id": None,
                                        "content": "You are out of time. Wrap up in one sentence, say goodbye now, then delegate to the backend."})
                if self.hangup_at and loop.time() >= self.hangup_at:
                    await self.close("out_of_time")
        except asyncio.CancelledError:
            pass

    # ── teardown ──────────────────────────────────────────────────────────────
    async def close(self, reason: str, upstream_done: bool = False):
        if self.closed:
            return
        self.closed = True
        self.reason = reason
        await self._flush()
        for t in self.tasks:  # stop the reader first: only one coroutine may recv() while we drain for session.closed
            if t is not asyncio.current_task():
                t.cancel()
        if self.up and not upstream_done:
            try:
                await self.up.send({"type": "session.close"})
                try:
                    async with asyncio.timeout(4):
                        async for ev in self.up:
                            if ev.get("type") == "session.usage.updated":
                                self.seconds = int((ev.get("usage") or {}).get("seconds") or self.seconds)
                            if ev.get("type") == "session.closed":
                                self.seconds = int((ev.get("usage") or {}).get("seconds") or self.seconds)
                                break
                except (asyncio.TimeoutError, TimeoutError):
                    pass
            except Exception:
                pass
        if self.up:
            await self.up.close()
        await self.db.roleplay_sessions.update_one({"_id": self.s["_id"]}, {"$set": {"live_seconds": self.seconds, "live_cost_usd": round(self.seconds / 60 * lv.PRICE_PER_MIN, 4), "live_end_reason": reason, "updated_at": _now()}})
        if reason in ("customer_ended", "out_of_time"):
            await self.db.roleplay_sessions.update_one({"_id": self.s["_id"], "status": "live"}, {"$set": {"status": "ending"}})
        try:
            await self.twilio_close()
        except Exception:
            pass
        self.done.set()
        logger.info(f"[LiveShop] {self.sid} closed: {reason}, {self.seconds}s, {self.turns} turns")


async def call_over(turns: list) -> bool:
    """Did the shopper just end the call? Quick LLM read of the tail, regex fallback."""
    tail = [t for t in turns if t.get("text")][-8:]
    if not tail:
        return False
    last_customer = next((t["text"] for t in reversed(tail) if t.get("role") == "customer"), "")
    try:
        from services.scripts import _llm_json
        convo = "\n".join(f"{'CUSTOMER' if t.get('role') == 'customer' else 'REP'}: {t['text'][:300]}" for t in tail)
        data = await _llm_json("You read the tail of a phone call transcript and answer one question: has the conversation reached its end (goodbyes said, appointment or next step set and wrapped, or the customer declined for good)? Return ONLY JSON: {\"over\": true|false}", convo, timeout=12)
        if isinstance(data, dict) and "over" in data:
            return bool(data["over"])
    except Exception as e:
        logger.debug(f"[LiveShop] call_over LLM failed: {e}")
    return bool(GOODBYE.search(last_customer))
