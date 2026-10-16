"""Jessi builds campaigns: a couple of quick questions (who it is for, how long, what tone), then a drafted plan saved switched OFF
and opened on the rep's screen to edit; voice edits ("make text 2 shorter", "add a call on day 10") change the same draft.
Touches: text (sms), email, or call (a dated "call them" task for the rep with talking points; never sent to the customer)."""
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException

logger = logging.getLogger(__name__)

QUESTIONS = (
    ("audience", "Who is it for? For example anyone you tag Hot Opportunity, new leads, or customers after they buy."),
    ("length", "How long should it run, and roughly how many touches? Something like 3 weeks with 5 touches."),
    ("tone", "What tone: friendly and casual, straight to the point, or more polished?"),
)
YOU_PICK = re.compile(r"(?i)\b(you (pick|choose|decide)|whatever|up to you|doesn'?t matter|surprise me|your call|you tell me|default)\b")
GO_AHEAD = re.compile(r"(?i)\b(yes|yeah|yep|yup|sure|ok(ay)?|sounds (good|great)|go ahead|(just )?(build|make|draft|do) it( now)?|that'?s (fine|good|it)|perfect|good to go|let'?s go)\b")
PLACEHOLDER = re.compile(r"\[[^\]]{1,40}\]")
REP_NAME = re.compile(r"(?i)\[(rep|your|my|sales ?person|salesperson|agent)('?s)? ?(first )?name\]")
MAX_TOUCHES, MAX_DAY = 10, 365
CHANNELS = {"text": "sms", "sms": "sms", "email": "email", "call": "call"}

DRAFT_SYSTEM = """You write follow-up campaigns (drips) for a salesperson. Each touch is a text, an email, or a call (a reminder for the rep to phone, with talking points).
Return JSON: {"name": "<short plan name, 2-5 words>", "touches": [{"day": <int days after they join, first touch usually 0>, "channel": "text|email|call", "message": "<the text or email body, or the call talking points>", "goal": "<what this touch is for, 3-8 words>"}]}
Rules:
- Match the brief: who it is for, how long, how many touches, tone. Days ascending, within the length asked. 3 to 8 touches unless asked otherwise.
- Texts: under 300 characters, sound like a real person, start with {first_name}, one clear ask, no emojis, no links, no exclamation spam, never pushy.
- Emails: 2 to 4 short sentences, plain text, no subject line, no signature.
- Calls: one or two lines of talking points for the rep (not a script to the customer).
- {first_name} is the only placeholder. Never write bracket placeholders like [Rep Name], [need], [vehicle] or [link]: write around what you do not know. When the rep introduces themself, use the rep's first name given in the brief.
- Never invent prices, dates, inventory or promises. Mix channels only when it fits (mostly texts)."""

EDIT_SYSTEM = """You edit an existing follow-up campaign for a salesperson. You get the current plan as JSON and one change the rep asked for by voice.
Apply that change: adding a touch, removing one, moving one to another day, rewriting one or all of them, changing the tone, renaming the plan are all fine when asked.
Touch numbers count from 1 in the order given; "text 2" / "the second text" means the second touch whose channel is text. Touches the change does not mention stay exactly as they are (same day, channel, words).
Return JSON: {"name": "<plan name, unchanged unless asked>", "touches": [{"day": int, "channel": "text|email|call", "message": "...", "goal": "..."}], "summary": "<what you changed, under 15 words, past tense, e.g. Made text 2 shorter>", "understood": true|false}
Set understood false (and return the plan unchanged) when the change is unclear. Same writing rules: texts under 300 characters starting with {first_name}, no emojis, no links, never invent prices or promises.
{first_name} is the only placeholder: never write bracket placeholders like [Rep Name] or [need]; use the rep's first name given below when the rep introduces themself."""


def _fill(msg: str, rep_first: str) -> str:
    """Bracket placeholders the model slipped in: the rep's name becomes their first name, anything else is dropped."""
    msg = REP_NAME.sub(rep_first or "me", msg)
    msg = PLACEHOLDER.sub("", msg)
    return re.sub(r"\s+([,.!?])", r"\1", re.sub(r"\s+", " ", msg)).strip()


def _clean_touches(raw, rep_first: str = "") -> list:
    out = []
    for t in raw if isinstance(raw, list) else []:
        if not isinstance(t, dict):
            continue
        ch = CHANNELS.get(str(t.get("channel") or "text").lower().strip(), "sms")
        msg = _fill(str(t.get("message") or ""), rep_first)
        try:
            day = min(MAX_DAY, max(0, int(float(t.get("day") or 0))))
        except (TypeError, ValueError):
            day = 0
        if not msg and ch != "call":
            continue
        out.append({"day": day, "channel": ch, "message": msg[:600 if ch == "email" else 320], "goal": str(t.get("goal") or "").strip()[:80]})
    return sorted(out, key=lambda x: x["day"])[:MAX_TOUCHES]


def to_sequences(touches: list) -> list:
    return [{"step": i + 1, "action_type": "call" if t["channel"] == "call" else "message", "card_type": "", "message_template": t["message"],
             "delay_minutes": 0, "delay_hours": 0, "delay_days": t["day"], "delay_months": 0, "media_urls": [], "channel": t["channel"],
             "ai_generated": t["channel"] != "call", "step_context": t["goal"]} for i, t in enumerate(touches)]


def from_sequences(seqs: list) -> list:
    out = []
    for s in seqs or []:
        if s.get("action_type") == "send_card":
            ch = "card"
        else:
            ch = "call" if s.get("action_type") == "call" else ("email" if s.get("channel") == "email" else "text")
        days = int(s.get("delay_days") or 0) + int(s.get("delay_months") or 0) * 30
        out.append({"day": days, "channel": ch, "message": s.get("message_template") or "", "goal": s.get("step_context") or "", **({"card_type": s.get("card_type")} if ch == "card" else {})})
    return out


def _label(ch: str) -> str:
    return {"sms": "text", "email": "email", "call": "call", "card": "card"}.get(ch, "text")


def outline(touches: list) -> str:
    """'5 touches over 3 weeks: day 0 text, day 2 text, day 5 call, day 10 email and day 21 text.'"""
    if not touches:
        return "No touches yet."
    last = touches[-1]["day"]
    span = "the same day" if not last else (f"{last // 7} weeks" if last % 7 == 0 and last >= 14 else f"{last} days")
    parts = [f"day {t['day']} {_label(t['channel'])}" for t in touches]
    joined = parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"
    return f"{len(touches)} touch{'es' if len(touches) != 1 else ''} over {span}: {joined}."


async def _tag_name(user_id: str, spoken: str) -> tuple:
    """(tag to trigger on, whether it already exists): the rep's own tag name when it matches what they said."""
    from routers.tags import get_tags
    want = re.sub(r"(?i)\b(tag(ged)?|as|the|anyone|everyone|people|i|with)\b", " ", spoken or "")
    want = re.sub(r"\s+", " ", want).strip(" .,'\"")
    if not want:
        return "", False
    try:
        tags = [t.get("name") or "" for t in await get_tags(user_id)]
    except Exception:
        tags = []
    norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    for t in tags:
        if norm(t) == norm(want):
            return t, True
    from services.live_voice import _sim
    best = max(tags, key=lambda t: _sim(norm(t), norm(want)), default="")
    if best and _sim(norm(best), norm(want)) >= 0.86:
        return best, True
    return want.title(), False


def _first(user: dict) -> str:
    return (user.get("first_name") or (user.get("name") or "").split(" ")[0] or "").strip()


async def draft(brief: dict, rep_first: str = "") -> dict:
    from services.scripts import _llm_json
    b = {k: (brief.get(k) or "you pick") for k in ("goal", "audience", "length", "tone")}
    data = await _llm_json(DRAFT_SYSTEM, f"Brief: goal: {b['goal']}; who it is for: {b['audience']}; how long / how many touches: {b['length']}; tone: {b['tone']}; channels: {brief.get('channels') or 'mostly texts'}; the rep's first name: {rep_first or 'unknown'}.", timeout=60)
    touches = _clean_touches(data.get("touches"), rep_first)
    if not touches:
        raise RuntimeError("the draft came back empty")
    return {"name": re.sub(r"\s+", " ", str(data.get("name") or "New follow-up plan")).strip()[:60], "touches": touches}


async def create(db, user: dict, brief: dict) -> dict:
    """Draft and save the plan switched off (the rep turns it on after editing). Permission rules are the normal campaign ones."""
    from models import CampaignCreate
    from routers.campaigns import check_campaign_permission, create_campaign
    uid = str(user["_id"])
    perm = await check_campaign_permission(uid, "create")
    if not perm["allowed"]:
        raise HTTPException(status_code=403, detail=perm["reason"])
    tag, tag_exists = await _tag_name(uid, brief.get("trigger_tag") or "")
    plan = await draft(brief, _first(user))
    name = plan["name"]
    n = 2
    while await db.campaigns.find_one({"user_id": uid, "name": name, "type": "custom"}, {"_id": 1}):
        name = f"{plan['name'][:56]} {n}"
        n += 1
    c = await create_campaign(uid, CampaignCreate(name=name, type="custom", trigger_tag=tag, sequences=to_sequences(plan["touches"]), active=False,
                                                  delivery_mode="auto", ai_enabled=True, ai_assist_mode="auto_reply", scope="personal", ownership_level="user",
                                                  description=f"Built with Jessi: {brief.get('goal') or brief.get('audience') or ''}"[:200]))
    cid = str(getattr(c, "id", None) or (c.get("_id") if isinstance(c, dict) else ""))
    await db.campaigns.update_one({"_id": ObjectId(cid)}, {"$set": {"built_by": "jessi", "jessi_brief": {k: brief.get(k) for k in ("goal", "audience", "length", "tone", "trigger_tag")}, "jessi_updated_at": datetime.now(timezone.utc)}})
    logger.info(f"[CampaignBuilder] {uid} drafted '{name}' ({len(plan['touches'])} touches, tag '{tag}')")
    return {"id": cid, "name": name, "touches": plan["touches"], "tag": tag, "tag_exists": tag_exists}


async def find_draft(db, user: dict, spoken: str = "") -> Optional[dict]:
    """The plan a voice edit is about: the one named, else the newest plan Jessi built for this rep in the last day."""
    uid = str(user["_id"])
    if spoken.strip():
        from services.live_voice import _sim
        words = [w for w in re.findall(r"[a-z0-9]+", spoken.lower()) if len(w) > 2 and w not in ("campaign", "plan", "the", "and", "for", "drip")]
        best, score = None, 0.0
        async for c in db.campaigns.find({"user_id": uid}, {"name": 1, "active": 1, "sequences": 1, "trigger_tag": 1}):
            names = re.findall(r"[a-z0-9]+", (c.get("name") or "").lower())
            s = sum(max([_sim(w, n) for n in names] or [0]) for w in words) / max(1, len(words))
            if s > score:
                best, score = c, s
        if best and score >= 0.8:
            return best
    return await db.campaigns.find_one({"user_id": uid, "built_by": "jessi", "jessi_updated_at": {"$gte": datetime.now(timezone.utc) - timedelta(days=1)}},
                                       {"name": 1, "active": 1, "sequences": 1, "trigger_tag": 1}, sort=[("jessi_updated_at", -1)])


async def edit(db, user: dict, campaign: dict, change: str) -> dict:
    """Apply one spoken change to a plan that is still switched off. Cards in the plan are kept as they are."""
    from routers.campaigns import update_campaign
    from services.scripts import _llm_json
    import json
    if campaign.get("active"):
        raise HTTPException(status_code=409, detail=f"{campaign.get('name')} is on, so I will not change it by voice. Turn it off first or edit it on screen.")
    cur = from_sequences(campaign.get("sequences") or [])
    cards = [t for t in cur if t["channel"] == "card"]
    editable = [{**t, "channel": {"text": "text"}.get(t["channel"], t["channel"])} for t in cur if t["channel"] != "card"]
    data = await _llm_json(EDIT_SYSTEM, f"Current plan: {json.dumps({'name': campaign.get('name'), 'touches': editable})}\nChange asked: {change}\nThe rep's first name: {_first(user) or 'unknown'}", timeout=60)
    if data.get("understood") is False:
        return {"changed": False, "summary": "", "touches": cur}
    touches = _clean_touches(data.get("touches"), _first(user))
    if not touches:
        return {"changed": False, "summary": "", "touches": cur}
    seqs = to_sequences(touches)
    for c in cards:   # keep any card touch the rep added on screen, at its day
        seqs.append({"step": 0, "action_type": "send_card", "card_type": c.get("card_type") or "congrats", "message_template": c["message"], "delay_minutes": 0, "delay_hours": 0,
                     "delay_days": c["day"], "delay_months": 0, "media_urls": [], "channel": "sms", "ai_generated": False, "step_context": c["goal"]})
    seqs.sort(key=lambda s: s["delay_days"])
    for i, s in enumerate(seqs):
        s["step"] = i + 1
    name = re.sub(r"\s+", " ", str(data.get("name") or campaign.get("name") or "")).strip()[:60] or campaign.get("name")
    await update_campaign(str(user["_id"]), str(campaign["_id"]), {"name": name, "sequences": seqs})
    await db.campaigns.update_one({"_id": campaign["_id"]}, {"$set": {"jessi_updated_at": datetime.now(timezone.utc)}})
    return {"changed": True, "summary": str(data.get("summary") or "Updated the plan").strip()[:120], "touches": from_sequences(seqs), "name": name}
