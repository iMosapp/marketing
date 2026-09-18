"""The onboarding interview on GPT-Live-1: same phone call (Twilio rings the rep, the inbound-only recording still feeds Voice ID),
but the line is bridged to GPT-Live so Jessi interviews in full duplex instead of the turn-by-turn ConversationRelay.
Steering happens out of band: after every answer a quick coverage read marks topics done and whispers what is left; the watchdog
paces the call; Jessi hangs up herself after the goodbye. Gated by the Test Lab flag `live_interview` (live by default) + OPENAI_API_KEY + English."""
import asyncio
import logging
from typing import Optional

from services import interview as iv
from services import lab
from services import live_shops as ls
from services import live_voice as lv
from services import locales as loc
from services.scripts import _app_url, _llm_json, _xml

logger = logging.getLogger(__name__)

LAB_KEY = "live_interview"
LAB_OFF = "the Test Lab switch 'Interview call on GPT-Live' is off"
STEER_DEBOUNCE_S = 1.2


async def decide(db, session: dict) -> tuple[bool, str]:
    if loc.language(session.get("locale")) != "en":
        return False, "not an English store, Dutch stays on ConversationRelay"
    if lv.configured():
        return False, ls.NO_KEY
    if await lab.is_live(db, LAB_KEY):
        return True, "on for every English interview"
    return False, LAB_OFF


async def twiml_for(db, session: dict) -> str:
    """The TwiML Twilio fetches when the rep picks up: GPT-Live stream when allowed, the classic relay otherwise (with the reason stamped)."""
    use_live, why = await decide(db, session)
    logger.info(f"[Interview] {session['_id']}: {'GPT-Live' if use_live else 'classic relay'} ({why})")
    if use_live:
        return stream_twiml(session)
    await db[iv.COLL].update_one({"_id": session["_id"]}, {"$set": {"live_transport": "relay", "live_skip_reason": why, "updated_at": iv._now()}})
    return iv.twiml(session)


def stream_twiml(session: dict) -> str:
    sid, token = str(session["_id"]), session["token"]
    base = _app_url()
    ws = base.replace("https://", "wss://").replace("http://", "ws://") + f"/api/interview/stream/{sid}/{token}"
    return (f'<?xml version="1.0" encoding="UTF-8"?><Response><Connect action="{_xml(base)}/api/interview/call/after/{sid}?t={token}">'
            f'<Stream url="{_xml(ws)}" /></Connect></Response>')


def instructions(s: dict) -> str:
    first = iv._first(s.get("rep_name")) or "the rep"
    from services import industries as ind
    business = ind.va(s.get("industry"))["business"]
    tops = "; ".join(f"{k}: {label}" for k, label in iv.topics(s.get("industry")))
    return (f"You are Jessi, the friendly onboarding host at I'm On Social, on a LIVE phone call interviewing {first}"
            f"{', ' + s['role_title'] if s.get('role_title') else ''} at {s.get('store_name') or 'their ' + business}. "
            "Purpose: learn who they really are so we can write their AI assistant's persona, their bio and their business card in THEIR voice. "
            f"You speak first: your opening, in your own words but with every fact kept: \"{iv.greeting(first)}\" "
            "STYLE: warm, curious, quick. React to what they just said in a few words (never repeat it back in full), then ask ONE question. "
            "One or two short spoken sentences, contractions, no lists, never say 'great question', never coach, never sell. "
            "If an answer is short, one gentle follow-up at most, then move on. If they ask what this is for, one sentence, then continue. "
            "If they say they need to go or ask to stop, thank them and wrap up right away. About five minutes total, one topic at a time.\n\n"
            f"TOPICS TO COVER, in whatever order feels natural (weave each into what they just said): {tops}.\n\n"
            "The backend listens along: it whispers which topics are covered and what is left, and tells you when time is up. Follow those notes without mentioning them.\n"
            "Interruption policy: stop speaking the moment the rep talks over you and listen.\n"
            "Backchannel policy: light backchannels only (mm-hm, okay), never over the rep's sentences.\n"
            "Delegation policy: you have no tools and nothing to look up, so never delegate for information. "
            "Delegate to the backend exactly once, right AFTER you have said your final goodbye: the backend hangs up the line. "
            "Do not delegate before the goodbye is spoken, and do not say anything after you delegate.")


class InterviewBridge(ls.Bridge):
    COLL = iv.COLL
    ASSISTANT_ROLE = "jessi"
    TAG = "LiveInterview"

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.steer_task: Optional[asyncio.Task] = None
        self.rep_turns = sum(1 for t in self.s.get("turns") or [] if t.get("role") == "rep")

    async def session_config(self) -> dict:
        cfg = await lv.get_config(self.db)
        return {"instructions": instructions(self.s), "voice": cfg["voice"]}

    async def _mark_live(self, call_sid: Optional[str]):
        self.started_at = iv._now()
        sets = {"status": "live", "call_status": "in-progress", "started_at": self.started_at, "updated_at": self.started_at, "live_transport": "gpt-live", "live_voice": self.cfg.get("voice")}
        if call_sid:
            sets["call_sid"] = call_sid
        await self.col.update_one({"_id": self.s["_id"], "status": {"$in": ["dialing", "live"]}}, {"$set": sets})

    async def on_started(self):
        line = iv.greeting(iv._first(self.s.get("rep_name")))
        await self.up.send({"type": "session.instructions.append", "event_id": "open_1", "delegation_id": None, "content": f'The rep just picked up. Speak first, now, in your own words with every fact kept: "{line}"'})
        await self.up.send({"type": "session.commentary.append", "event_id": "open_2", "delegation_id": None, "content": line})

    def decorate(self, turn: dict) -> dict:
        return turn

    async def after_flush(self, turn: dict):
        if turn["role"] != "rep":
            return
        self.rep_turns += 1
        if self.steer_task and not self.steer_task.done():
            self.steer_task.cancel()
        self.steer_task = asyncio.get_event_loop().create_task(self._steer())

    async def _steer(self):
        """Quick coverage read of the tail, then a whisper to Jessi: what is done, what is left, how much time."""
        try:
            await asyncio.sleep(STEER_DEBOUNCE_S)
            if self.closed or self.wrapping:
                return
            s = await self.col.find_one({"_id": self.s["_id"]}, {"turns": 1, "covered": 1, "industry": 1})
            if not s:
                return
            covered = set(s.get("covered") or [])
            tops = iv.topics(s.get("industry"))
            keys = {k for k, _ in tops}
            tail = "\n".join(f"{'JESSI' if t['role'] == 'jessi' else 'REP'}: {str(t.get('text') or '')[:400]}" for t in (s.get("turns") or [])[-8:])
            try:
                data = await _llm_json("You read the tail of an onboarding interview and list which topics the rep's answers have now fully covered. Topics: "
                                       + "; ".join(f"{k}: {label}" for k, label in tops) + ". Return ONLY JSON: {\"covered\": [topic keys]}", tail, timeout=12)
                new = [k for k in (data.get("covered") or []) if k in keys]
            except Exception as e:
                logger.debug(f"[LiveInterview] {self.sid} coverage read failed: {e}")
                new = []
            if new:
                covered |= set(new)
                await self.col.update_one({"_id": self.s["_id"]}, {"$addToSet": {"covered": {"$each": new}}, "$set": {"updated_at": iv._now()}})
            left = [label for k, label in tops if k not in covered]
            if self.closed or self.wrapping or not self.up:
                return
            if not left or self.rep_turns >= iv.MAX_REP_TURNS:
                await self.wrap_up("Every topic is covered. Do not ask anything new: thank them by name, tell them their assistant and card will be ready in the app in a minute, say goodbye, then delegate to the backend.")
                return
            minutes = self.minutes()
            pace = (f"You are {minutes:.0f} minutes in: ask at most one or two more of these, then wrap up warmly, say goodbye and delegate." if minutes >= iv.WRAP_AFTER_MINUTES
                    else f"You are {minutes:.0f} minutes in, relaxed pace, one question at a time.")
            await self.up.send({"type": "session.thinking.append", "event_id": f"steer_{self.rep_turns}", "delegation_id": None,
                                "content": f"Backend note: covered so far: {', '.join(sorted(covered)) or 'nothing yet'}. Still to cover: {'; '.join(left)}. {pace}"})
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"[LiveInterview] {self.sid} steer failed: {e}")

    async def _delegation(self, delegation_id: Optional[str]):
        await self._flush()
        s = await self.col.find_one({"_id": self.s["_id"]}, {"turns": 1})
        turns = [{"role": "customer" if t.get("role") == "jessi" else "rep", "text": t.get("text")} for t in (s or {}).get("turns") or []]
        if self.wrapping or await ls.call_over(turns):
            await self.hang_up(delegation_id, "customer_ended")
        elif delegation_id:
            await self.up.send({"type": "session.thinking.append", "event_id": f"stay_{delegation_id}", "delegation_id": delegation_id,
                                "content": "There is no backend help on this call and nothing to look up. Keep interviewing: react briefly and ask the next topic."})

    async def _watchdog(self):
        loop = asyncio.get_event_loop()
        try:
            while not self.closed:
                await asyncio.sleep(1)
                if not self.ready:
                    continue
                if not self.wrapping and self.minutes() >= iv.MAX_MINUTES:
                    await self.wrap_up("TIME IS UP. Do not ask anything new: thank them by name, tell them their assistant and card will be ready in the app in a minute, say goodbye now, then delegate to the backend.")
                if self.hangup_at and loop.time() >= self.hangup_at:
                    await self.close("out_of_time")
        except asyncio.CancelledError:
            pass

    async def close(self, reason: str, upstream_done: bool = False):
        if self.steer_task and not self.steer_task.done():
            self.steer_task.cancel()
        await super().close(reason, upstream_done)

