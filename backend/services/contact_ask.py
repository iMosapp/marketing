"""Ask Jessi about a customer: a grounded chat over every touchpoint we hold for one contact
(texts, call transcripts, voice notes, events, tasks, saved intel). Answers cite the exact source
with ids like [T12] (text), [C3@4:12] (call at 4:12), [V2] (voice note), [E5] (event), [K1] (task)."""
import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)

SESS = "contact_ask_sessions"
from services.llm_models import CUSTOMER_TEXT_MODEL

MODEL = ("openai", "gpt-5.2")  # rep-facing Q&A; the draft the customer reads uses CUSTOMER_TEXT_MODEL
CHAR_BUDGET = 70000
CITE_RE = re.compile(r"\[([TCVEK])(\d+)(?:@(\d+(?::\d{2})?))?\]")

NOISY_EVENTS = {"sms_sent", "customer_reply", "ai_reply_sent", "auto_text_sent", "personal_sms", "creation", "setup", "test",
                "intelligence_extracted", "name_updated", "call_placed", "call_outbound", "outbound_call", "inbound_call",
                "lead_call_attempt", "campaign_removed", "new_contact", "new_contact_added", "voice_note", "note_added", "note_updated"}


def _now():
    return datetime.now(timezone.utc)


def _dt(v) -> Optional[datetime]:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _fmt(v, tz=None) -> str:
    d = _dt(v)
    if not d:
        return "unknown time"
    if tz:
        try:
            from zoneinfo import ZoneInfo
            d = d.astimezone(ZoneInfo(tz))
        except Exception:
            pass
    return d.strftime("%a %b %-d, %Y %-I:%M %p")


def _mmss(sec: float) -> str:
    s = int(sec or 0)
    return f"{s // 60}:{s % 60:02d}"


def _oid(v):
    return ObjectId(str(v)) if ObjectId.is_valid(str(v or "")) else None


# ---------------------------------------------------------------- record
async def build_record(db, contact: dict, tz: Optional[str] = None) -> dict:
    """Everything we know about this customer as numbered, citable lines + a citation index."""
    cid = str(contact["_id"])
    first = contact.get("first_name") or (contact.get("name") or "the customer").split(" ")[0]
    convs = await db.conversations.find({"contact_id": cid}, {"_id": 1, "inbox_id": 1, "user_id": 1, "lead_source_name": 1, "created_at": 1}).to_list(50)
    conv_ids = [str(c["_id"]) for c in convs]
    conv_inbox = {str(c["_id"]): c.get("inbox_id") for c in convs}

    msgs = await db.messages.find({"conversation_id": {"$in": conv_ids}, "type": {"$ne": "call_log"}}).sort("timestamp", 1).to_list(3000) if conv_ids else []
    calls = await db.call_logs.find({"contact_id": cid}).sort("timestamp", 1).to_list(200)
    voice = await db.voice_notes.find({"contact_id": cid}).sort("created_at", 1).to_list(200)
    events = await db.contact_events.find({"contact_id": cid, "event_type": {"$nin": list(NOISY_EVENTS)}}).sort("timestamp", -1).limit(120).to_list(120)
    tasks = await db.tasks.find({"contact_id": cid}).sort("created_at", -1).limit(30).to_list(30)
    intel = await db.contact_intel.find_one({"contact_id": cid}, sort=[("generated_at", -1)])
    evals = {e["call_sid"]: e for e in await db.call_evaluations.find({"contact_id": cid}, {"call_sid": 1, "score_pct": 1, "summary": 1, "coaching": 1, "critical_misses": 1, "scorecard_name": 1}).to_list(200)}
    rep_ids = {str(m.get("user_id")) for m in msgs if m.get("user_id")} | {str(c.get("user_id")) for c in calls if c.get("user_id")}
    reps = {str(u["_id"]): (u.get("first_name") or (u.get("name") or "Rep").split(" ")[0]) async for u in db.users.find({"_id": {"$in": [ObjectId(r) for r in rep_ids if ObjectId.is_valid(r)]}}, {"name": 1, "first_name": 1})} if rep_ids else {}

    cites: dict = {}
    items: list = []  # (datetime, text, kind)

    # texts
    n = 0
    for m in msgs:
        content = (m.get("content") or "").strip()
        if not content:
            continue
        if m.get("channel") == "email" and m.get("subject"):
            content = f"(subject: {m['subject']}) {content}"
        n += 1
        key = f"T{n}"
        sender = m.get("sender")
        who = first if sender == "contact" else "Jessi (AI)" if (sender == "ai" or m.get("ai_generated")) else f"Rep {reps.get(str(m.get('user_id')), '')}".strip() if sender == "user" else "System"
        chan = m.get("channel") or m.get("type") or "text"
        inbox_tag = " via shared inbox" if conv_inbox.get(str(m.get("conversation_id"))) else ""
        line = f"[{key}] {_fmt(m.get('timestamp') or m.get('created_at'), tz)} {chan}{inbox_tag} | {who}: {content[:1200]}"
        items.append((_dt(m.get("timestamp") or m.get("created_at")) or _now(), line, "T"))
        cites[key] = {"id": key, "kind": "text", "label": f"{who} · {_fmt(m.get('timestamp'), tz)}", "conversation_id": str(m.get("conversation_id")), "message_id": str(m["_id"]), "snippet": content[:140]}

    # calls (segments for the 6 most recent, summaries for the rest)
    recent_call_sids = {c.get("call_sid") for c in calls[-6:]}
    for i, c in enumerate(calls, 1):
        key = f"C{i}"
        when = c.get("timestamp") or c.get("created_at")
        dur = int(c.get("duration_s") or 0)
        head = f"[{key}] CALL {_fmt(when, tz)} {c.get('direction') or ''} {_mmss(dur)} with Rep {reps.get(str(c.get('user_id')), '')} outcome={c.get('outcome') or 'connected'}"
        parts = [head]
        if c.get("ai_summary"):
            parts.append(f"  summary: {c['ai_summary'][:900]}")
        ev = evals.get(c.get("call_sid"))
        if ev:
            parts.append(f"  scorecard: {ev.get('score_pct')}% on {ev.get('scorecard_name')}; {ev.get('summary', '')[:300]}")
        segs = c.get("transcript_segments") or []
        if c.get("call_sid") in recent_call_sids:
            if segs:
                for s in segs:
                    who = f"Rep" if s.get("role") == "rep" else first
                    parts.append(f"  [{key}@{_mmss(s.get('start') or 0)}] {who}: {(s.get('text') or '')[:600]}")
            elif c.get("transcript"):
                parts.append(f"  transcript: {c['transcript'][:6000]}")
        items.append((_dt(when) or _now(), "\n".join(parts), "C"))
        cites[key] = {"id": key, "kind": "call", "label": f"Call · {_fmt(when, tz)}", "call_sid": c.get("call_sid"), "conversation_id": None, "duration_s": dur,
                      "has_recording": bool(c.get("recording_url") or c.get("recording_sid")), "snippet": (c.get("ai_summary") or "")[:140]}

    for i, v in enumerate(voice, 1):
        key = f"V{i}"
        t = (v.get("transcript") or "").strip()
        if not t:
            continue
        convo = v.get("kind") == "conversation"
        who = f"Rep {reps.get(str(v.get('user_id')), '')}".strip()
        if convo:
            line = f"[{key}] IN-PERSON CONVERSATION recorded by {who} {_fmt(v.get('created_at'), tz)} ({_mmss(v.get('duration') or 0)})"
            if v.get("summary"):
                line += f"\n  summary: {v['summary'][:900]}"
            line += f"\n  transcript: {t[:8000]}"
        else:
            line = f"[{key}] VOICE NOTE by {who} {_fmt(v.get('created_at'), tz)} ({_mmss(v.get('duration') or 0)}): {t[:2000]}"
        items.append((_dt(v.get("created_at")) or _now(), line, "V"))
        cites[key] = {"id": key, "kind": "voice_note", "label": f"{'Recorded conversation' if convo else 'Voice note'} · {_fmt(v.get('created_at'), tz)}", "voice_note_id": str(v["_id"]),
                      "audio_url": v.get("audio_url"), "snippet": (v.get("summary") or t)[:140], "recorded_conversation": convo}

    for i, e in enumerate(reversed(events), 1):
        key = f"E{i}"
        title = e.get("title") or e.get("event_type", "").replace("_", " ")
        desc = (e.get("description") or e.get("content") or "").strip()
        line = f"[{key}] EVENT {_fmt(e.get('timestamp') or e.get('created_at'), tz)} {title}" + (f": {desc[:300]}" if desc else "")
        items.append((_dt(e.get("timestamp") or e.get("created_at")) or _now(), line, "E"))
        cites[key] = {"id": key, "kind": "event", "label": f"{title} · {_fmt(e.get('timestamp'), tz)}", "event_type": e.get("event_type"), "snippet": desc[:140]}

    for i, k in enumerate(reversed(tasks), 1):
        key = f"K{i}"
        status = "done" if k.get("completed") or k.get("status") == "completed" else "open"
        line = f"[{key}] TASK {status} {k.get('type') or ''} '{k.get('title')}' due {_fmt(k.get('due_date'), tz) if k.get('due_date') else 'no date'}" + (f": {(k.get('description') or '')[:200]}" if k.get("description") else "")
        items.append((_dt(k.get("due_date") or k.get("created_at")) or _now(), line, "K"))
        cites[key] = {"id": key, "kind": "task", "label": f"Task · {k.get('title')}", "task_id": str(k["_id"]), "completed": status == "done", "snippet": (k.get("description") or "")[:140]}

    items.sort(key=lambda x: x[0])

    # profile block
    pd = contact.get("personal_details") or {}
    profile = [f"CUSTOMER: {contact.get('name') or first} | phone {contact.get('phone') or 'n/a'} | email {contact.get('email') or 'n/a'} | tags {', '.join(contact.get('tags') or []) or 'none'} | added {_fmt(contact.get('created_at'), tz)}"]
    if isinstance(pd, dict) and pd:
        profile.append("PERSONAL DETAILS ON FILE: " + "; ".join(f"{k.replace('_', ' ')}: {v}" for k, v in pd.items() if v and isinstance(v, (str, int, float)))[:1500])
    if contact.get("notes"):
        profile.append(f"NOTES: {str(contact['notes'])[:1500]}")
    if intel and intel.get("summary"):
        profile.append(f"RELATIONSHIP INTEL (AI, {_fmt(intel.get('generated_at'), tz)}): {intel['summary'][:1500]}")
    convs_line = ", ".join(f"{'shared inbox' if c.get('inbox_id') else 'rep'} thread from {c.get('lead_source_name') or 'direct'}" for c in convs) or "no threads"
    profile.append(f"THREADS: {convs_line}")

    # budget: drop oldest text lines first until it fits
    lines = [t for _, t, _ in items]
    total = sum(len(l) for l in lines) + sum(len(p) for p in profile)
    if total > CHAR_BUDGET:
        keep = []
        dropped = 0
        for dt_, text, kind in reversed(items):
            if total <= CHAR_BUDGET or kind != "T":
                keep.append(text)
            else:
                total -= len(text)
                dropped += 1
        lines = list(reversed(keep))
        if dropped:
            lines.insert(0, f"(oldest {dropped} texts omitted for length)")

    stats = {"texts": n, "calls": len(calls), "voice_notes": len([v for v in voice if v.get("transcript") and v.get("kind") != "conversation"]),
             "conversations": len([v for v in voice if v.get("transcript") and v.get("kind") == "conversation"]), "events": len(events), "tasks": len(tasks),
             "first_touch": _fmt(items[0][0], tz) if items else None, "last_touch": _fmt(items[-1][0], tz) if items else None}
    return {"profile": "\n".join(profile), "timeline": "\n".join(lines), "cites": cites, "stats": stats, "first_name": first}


# ---------------------------------------------------------------- asking
def _system_prompt(record: dict, rep_first: str) -> str:
    return (
        f"You are Jessi, the relationship assistant inside i'M On Social, helping the rep {rep_first} with one customer, {record['first_name']}. "
        "You have the customer's COMPLETE touchpoint record below: profile, then a chronological timeline of texts, calls (with transcripts and timestamps), "
        "voice notes, events and tasks. Answer ONLY from this record.\n\n"
        "RULES:\n"
        "- Every factual claim must cite its source id in square brackets exactly as written in the record: [T12] for a text, [C3] for a call, "
        "[C3@4:12] for a specific moment in a call, [V2] voice note, [E5] event, [K1] task. Put the citation right after the sentence it supports.\n"
        "- If the record does not contain the answer, say so plainly in one sentence and suggest what to ask the customer. Never invent details.\n"
        "- Be concise and useful: short paragraphs or a tight bullet list, plain dealership language, no fluff. Quote the customer's exact words when it helps.\n"
        "- Dates: say them naturally (e.g. 'Tuesday Sep 9'). Refer to the rep as 'you'.\n"
        "- Never use em dashes or en dashes. Use commas or periods.\n"
        "- After the answer, propose 2 or 3 short follow-up questions the REP could ask you (Jessi) next about this customer, e.g. 'What did she say about financing?'. No citations inside follow-ups.\n\n"
        "Respond with ONLY valid JSON: {\"answer\": \"...\", \"follow_ups\": [\"...\", \"...\"]}\n\n"
        f"=== PROFILE ===\n{record['profile']}\n\n=== TIMELINE ({record['stats']['texts']} texts, {record['stats']['calls']} calls, "
        f"{record['stats']['voice_notes']} voice notes, {record['stats'].get('conversations', 0)} recorded in-person conversations) ===\n{record['timeline'] or '(no touchpoints yet)'}"
    )


def _parse(raw: str) -> dict:
    t = (raw or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t[3:]
        if t.endswith("```"):
            t = t[:-3]
        t = t.strip()
        if t.startswith("json"):
            t = t[4:].strip()
    try:
        d = json.loads(t)
        if isinstance(d, dict) and d.get("answer"):
            return d
    except json.JSONDecodeError:
        pass
    return {"answer": t, "follow_ups": []}


def extract_citations(answer: str, cites: dict) -> list:
    out, seen = [], set()
    for m in CITE_RE.finditer(answer):
        kind, num, at = m.group(1), m.group(2), m.group(3)
        key = f"{kind}{num}"
        base = cites.get(key)
        if not base:
            continue
        seek = None
        if at:
            seek = int(at.split(":")[0]) * 60 + int(at.split(":")[1]) if ":" in at else int(at)
        token = m.group(0)
        if token in seen:
            continue
        seen.add(token)
        out.append({**base, "token": token, "seek_seconds": seek})
    return out


async def ask(db, user: dict, contact: dict, question: str, session: Optional[dict]) -> dict:
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not api_key:
        raise RuntimeError("EMERGENT_LLM_KEY not set")
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    record = await build_record(db, contact, tz=user.get("timezone"))
    rep_first = user.get("first_name") or (user.get("name") or "there").split(" ")[0]
    history = ""
    if session and session.get("messages"):
        turns = session["messages"][-8:]
        history = "PREVIOUS TURNS IN THIS CHAT (for context):\n" + "\n".join(
            f"{'Rep' if t['role'] == 'user' else 'Jessi'}: {t['content'][:800]}" for t in turns) + "\n\n"
    chat = LlmChat(api_key=api_key, session_id=f"ask-{uuid.uuid4().hex[:10]}", system_message=_system_prompt(record, rep_first)).with_model(*MODEL)
    resp = await asyncio.wait_for(chat.send_message(UserMessage(text=f"{history}QUESTION: {question.strip()[:1500]}")), timeout=75.0)
    text = resp if isinstance(resp, str) else getattr(resp, "text", "") or ""
    data = _parse(text)
    answer = no_em_dash(str(data.get("answer") or "")).strip()
    follow_ups = [CITE_RE.sub("", no_em_dash(str(f))).replace("  ", " ").strip()[:140] for f in (data.get("follow_ups") or []) if str(f).strip()][:3]
    return {"answer": answer, "follow_ups": follow_ups, "citations": extract_citations(answer, record["cites"]), "stats": record["stats"]}


def starters(stats: dict, first: str) -> list:
    out = ["What's the next best step with " + first + "?", "Anything I promised and haven't done yet?"]
    if stats.get("calls"):
        out.insert(0, "Summarize our last call in three lines")
        out.append("Did " + first + " mention a trade, budget or timeline?")
    if stats.get("texts"):
        out.append("What has " + first + " asked that never got a clear answer?")
    if stats.get("conversations"):
        out.insert(0, "What did we agree on in the recorded conversation?")
    if stats.get("voice_notes"):
        out.append("What personal details have I captured?")
    out.append("Draft a text that picks up where we left off")
    return out[:6]


def serialize_session(s: dict) -> dict:
    return {"id": str(s["_id"]), "title": s.get("title") or "New chat", "created_at": s["created_at"].isoformat() if isinstance(s.get("created_at"), datetime) else s.get("created_at"),
            "updated_at": s["updated_at"].isoformat() if isinstance(s.get("updated_at"), datetime) else s.get("updated_at"), "message_count": len(s.get("messages") or []),
            "messages": [{**m, "created_at": m["created_at"].isoformat() if isinstance(m.get("created_at"), datetime) else m.get("created_at")} for m in (s.get("messages") or [])]}


async def draft_text(user: dict, contact: dict, answer: str, question: str = "") -> str:
    """Turn a Jessi answer into a short text the rep can send to the customer."""
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not api_key:
        raise RuntimeError("EMERGENT_LLM_KEY not set")
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    rep_first = user.get("first_name") or (user.get("name") or "").split(" ")[0]
    first = contact.get("first_name") or (contact.get("name") or "there").split(" ")[0]
    clean = CITE_RE.sub("", answer)
    chat = LlmChat(api_key=api_key, session_id=f"draft-{uuid.uuid4().hex[:8]}",
                   system_message=(f"You write text messages a car salesperson named {rep_first} sends to a customer named {first}. "
                                   "Given the salesperson's internal notes below, write ONE friendly, natural SMS to the customer that follows up on them: "
                                   "warm, specific, one clear next step or question, 1 to 3 sentences, under 300 characters, first person, no sign-off block, no hashtags, "
                                   "no internal jargon, never mention AI, transcripts, recordings or notes. Never use em dashes or en dashes. Return ONLY the text message.")).with_model(*CUSTOMER_TEXT_MODEL)
    resp = await asyncio.wait_for(chat.send_message(UserMessage(text=f"Rep's question: {question[:300]}\n\nInternal notes:\n{clean[:3000]}")), timeout=45.0)
    text = resp if isinstance(resp, str) else getattr(resp, "text", "") or ""
    return no_em_dash(text.strip().strip('"'))[:600]
