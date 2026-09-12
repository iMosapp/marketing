"""Ask Jessi about the team: a manager's grounded chat over every active customer conversation in the store
(or one rep) for the last N days. Citations: [P{n}] = a customer thread, [C{n}] = a recorded call."""
import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from bson import ObjectId

from services.contact_ask import _dt, _fmt, _mmss, _parse, CITE_RE as _ONE_CITE_RE
from services.lead_flows import MANAGER_ROLES, user_store_id, store_reps
from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)

MODEL = ("openai", "gpt-5.2")
CHAR_BUDGET = 90000
CITE_RE = re.compile(r"\[([PC])(\d+)\]")
MAX_CONVS = 260


def _now():
    return datetime.now(timezone.utc)


def _ago(dt: Optional[datetime]) -> str:
    if not dt:
        return "n/a"
    s = int((_now() - dt).total_seconds())
    if s < 3600:
        return f"{max(1, s // 60)}m ago"
    if s < 86400:
        return f"{s // 3600}h ago"
    return f"{s // 86400}d ago"


async def scope_reps(db, me: dict, rep_id: Optional[str]) -> list:
    reps = await store_reps(db, user_store_id(me), me)
    reps = [r for r in reps if r.get("role") != "super_admin" or r["_id"] == str(me["_id"])]
    if rep_id:
        reps = [r for r in reps if r["_id"] == rep_id]
    return reps


async def build_team_record(db, me: dict, reps: list, days: int, tz: Optional[str]) -> dict:
    rep_ids = [r["_id"] for r in reps]
    rep_name = {r["_id"]: (r.get("name") or "Rep").split(" ")[0] for r in reps}
    cutoff = _now() - timedelta(days=days)
    store_id = user_store_id(me)
    inbox_ids = [str(i["_id"]) async for i in db.shared_inboxes.find({"store_id": store_id, "is_active": {"$ne": False}}, {"_id": 1})] if store_id else []
    ors = [{"user_id": {"$in": rep_ids}}, {"assigned_to": {"$in": rep_ids}}]
    if inbox_ids:
        ors.append({"inbox_id": {"$in": inbox_ids}})
    convs = await db.conversations.find({"$or": ors, "last_message_at": {"$gte": cutoff}, "status": {"$ne": "archived"}}).sort("last_message_at", -1).limit(MAX_CONVS).to_list(MAX_CONVS)
    conv_ids = [str(c["_id"]) for c in convs]

    # last customer + last rep message per conversation, plus recent customer lines for substance
    last_msgs: dict = {}
    async for row in db.messages.aggregate([
        {"$match": {"conversation_id": {"$in": conv_ids}, "type": {"$ne": "call_log"}, "content": {"$exists": True, "$ne": ""}}},
        {"$sort": {"timestamp": -1}},
        {"$group": {"_id": "$conversation_id", "msgs": {"$push": {"s": "$sender", "c": "$content", "t": "$timestamp", "ai": "$ai_generated"}}}},
        {"$project": {"msgs": {"$slice": ["$msgs", 6]}}},
    ]):
        last_msgs[row["_id"]] = row["msgs"]

    cites: dict = {}
    lines: list = []
    for i, c in enumerate(convs, 1):
        key = f"P{i}"
        cid = str(c["_id"])
        owner = c.get("assigned_to") or c.get("user_id")
        rep = rep_name.get(str(owner), "unassigned" if c.get("inbox_id") and not c.get("assigned_to") else "other rep")
        msgs = last_msgs.get(cid, [])
        cust = next((m for m in msgs if m.get("s") == "contact"), None)
        repm = next((m for m in msgs if m.get("s") in ("user", "ai")), None)
        waiting = cust and (not repm or (_dt(cust.get("t")) or _now()) > (_dt(repm.get("t")) or _now()))
        wait_txt = f"CUSTOMER WAITING {_ago(_dt(cust.get('t')))}" if waiting else ("answered" if cust else "no customer reply yet")
        recent = " | ".join(f"{'cust' if m.get('s') == 'contact' else 'Jessi' if (m.get('s') == 'ai' or m.get('ai')) else 'rep'}: {str(m.get('c') or '')[:160]}" for m in reversed(msgs[:4]))
        flags = []
        if c.get("is_internet_lead"):
            flags.append(f"internet lead{(' from ' + c['lead_source_name']) if c.get('lead_source_name') else ''}")
        if c.get("needs_assistance"):
            flags.append("needs rep")
        if c.get("status") == "closed":
            flags.append("closed")
        if c.get("ai_mode") == "auto_reply":
            flags.append("Jessi auto-reply on")
        lines.append(f"[{key}] {c.get('contact_name') or 'Unknown'} | rep {rep} | last activity {_ago(_dt(c.get('last_message_at')))} | {wait_txt}"
                     + (f" | {', '.join(flags)}" if flags else "") + (f"\n   recent: {recent}" if recent else ""))
        cites[key] = {"id": key, "kind": "thread", "label": f"{c.get('contact_name') or 'Thread'} · {rep}", "conversation_id": cid, "contact_id": c.get("contact_id"),
                      "rep": rep, "snippet": (cust or {}).get("c", "")[:140] if cust else ""}

    calls = await db.call_logs.find({"user_id": {"$in": rep_ids}, "timestamp": {"$gte": cutoff}}).sort("timestamp", -1).limit(120).to_list(120)
    evals = {e["call_sid"]: e for e in await db.call_evaluations.find({"call_sid": {"$in": [c.get("call_sid") for c in calls if c.get("call_sid")]}}, {"call_sid": 1, "score_pct": 1, "critical_misses": 1, "results": 1, "scorecard_name": 1}).to_list(200)}
    call_lines = []
    for i, c in enumerate(calls, 1):
        key = f"C{i}"
        ev = evals.get(c.get("call_sid"))
        missed = ""
        if ev and ev.get("critical_misses"):
            names = [r["text"] for r in ev.get("results") or [] if r["criterion_id"] in ev["critical_misses"]]
            missed = f" | MISSED CRITICAL: {'; '.join(names)}"
        score = f" | scorecard {ev.get('score_pct')}%" if ev and ev.get("score_pct") is not None else ""
        call_lines.append(f"[{key}] CALL {_fmt(c.get('timestamp'), tz)} rep {rep_name.get(str(c.get('user_id')), '?')} with {c.get('contact_name') or 'unknown'} {_mmss(int(c.get('duration_s') or 0))} {c.get('direction') or ''}{score}{missed}"
                          + (f"\n   summary: {c['ai_summary'][:400]}" if c.get("ai_summary") else ""))
        conv = await db.conversations.find_one({"contact_id": c.get("contact_id")}, {"_id": 1}, sort=[("last_message_at", -1)]) if c.get("contact_id") else None
        cites[key] = {"id": key, "kind": "call", "label": f"Call · {c.get('contact_name') or ''} · {_fmt(c.get('timestamp'), tz)}", "call_sid": c.get("call_sid"), "contact_id": c.get("contact_id"),
                      "has_recording": bool(c.get("recording_url") or c.get("recording_sid")),
                      "conversation_id": str(conv["_id"]) if conv else None, "rep": rep_name.get(str(c.get("user_id")), "?"), "snippet": (c.get("ai_summary") or "")[:140]}

    tasks = await db.tasks.find({"user_id": {"$in": rep_ids}, "$or": [{"completed": {"$ne": True}}, {"status": {"$ne": "completed"}}], "due_date": {"$lte": _now() + timedelta(days=3)}}).sort("due_date", 1).limit(60).to_list(60)
    task_lines = [f"- {rep_name.get(str(t.get('user_id')), '?')}: '{t.get('title')}' for {t.get('contact_name') or 'a customer'} due {_fmt(t.get('due_date'), tz)}{' OVERDUE' if _dt(t.get('due_date')) and _dt(t.get('due_date')) < _now() else ''}" for t in tasks]

    text_threads = "\n".join(lines)
    if len(text_threads) > CHAR_BUDGET:
        text_threads = text_threads[:CHAR_BUDGET] + "\n(more threads omitted for length)"
    stats = {"days": days, "reps": len(reps), "threads": len(convs), "waiting": sum(1 for l in lines if "CUSTOMER WAITING" in l), "calls": len(calls), "open_tasks": len(tasks)}
    return {"threads": text_threads, "calls": "\n".join(call_lines), "tasks": "\n".join(task_lines), "cites": cites, "stats": stats,
            "reps_line": ", ".join(rep_name.values()) or "no reps"}


def _system_prompt(record: dict, me_first: str, days: int) -> str:
    return (
        f"You are Jessi, the relationship assistant inside i'M On Social, helping sales manager {me_first} keep an eye on the team. "
        f"Below is every active customer conversation for the reps in scope ({record['reps_line']}) from the last {days} days, then recent recorded calls, then open tasks. "
        "Answer ONLY from this record.\n\n"
        "RULES:\n"
        "- Cite the threads or calls you rely on with their ids in square brackets exactly as written, e.g. [P12] or [C3], right after the sentence.\n"
        "- When asked 'who', list the customers with the rep's name and the reason, most urgent first. Prefer a tight bullet list.\n"
        "- 'Not followed up' / 'waiting' means the customer's last message has no rep or Jessi reply after it (marked CUSTOMER WAITING).\n"
        "- If the record does not contain the answer, say so plainly. Never invent customers, dates or quotes.\n"
        "- Plain dealership language, concise. Never use em dashes or en dashes.\n"
        "- After the answer, propose 2 or 3 short follow-up questions the manager could ask you next. No citations inside follow-ups.\n\n"
        "Respond with ONLY valid JSON: {\"answer\": \"...\", \"follow_ups\": [\"...\"]}\n\n"
        f"=== THREADS ({record['stats']['threads']}, {record['stats']['waiting']} with customer waiting) ===\n{record['threads'] or '(none)'}\n\n"
        f"=== RECORDED CALLS ({record['stats']['calls']}) ===\n{record['calls'] or '(none)'}\n\n"
        f"=== OPEN TASKS DUE SOON ===\n{record['tasks'] or '(none)'}"
    )


def extract_citations(answer: str, cites: dict) -> list:
    out, seen = [], set()
    for m in CITE_RE.finditer(answer):
        key = f"{m.group(1)}{m.group(2)}"
        if key in seen or key not in cites:
            continue
        seen.add(key)
        out.append({**cites[key], "token": m.group(0)})
    return out


async def ask_team(db, me: dict, reps: list, days: int, question: str, session: Optional[dict]) -> dict:
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not api_key:
        raise RuntimeError("EMERGENT_LLM_KEY not set")
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    record = await build_team_record(db, me, reps, days, me.get("timezone"))
    me_first = me.get("first_name") or (me.get("name") or "there").split(" ")[0]
    history = ""
    if session and session.get("messages"):
        history = "PREVIOUS TURNS (context):\n" + "\n".join(f"{'Manager' if t['role'] == 'user' else 'Jessi'}: {t['content'][:600]}" for t in session["messages"][-6:]) + "\n\n"
    chat = LlmChat(api_key=api_key, session_id=f"team-ask-{uuid.uuid4().hex[:8]}", system_message=_system_prompt(record, me_first, days)).with_model(*MODEL)
    resp = await asyncio.wait_for(chat.send_message(UserMessage(text=f"{history}QUESTION: {question.strip()[:1500]}")), timeout=90.0)
    text = resp if isinstance(resp, str) else getattr(resp, "text", "") or ""
    data = _parse(text)
    answer = no_em_dash(str(data.get("answer") or "")).strip()
    follow_ups = [CITE_RE.sub("", _ONE_CITE_RE.sub("", no_em_dash(str(f)))).replace("  ", " ").strip()[:140] for f in (data.get("follow_ups") or []) if str(f).strip()][:3]
    return {"answer": answer, "follow_ups": follow_ups, "citations": extract_citations(answer, record["cites"]), "stats": record["stats"]}


def team_starters(stats: dict, rep_first: Optional[str]) -> list:
    who = rep_first or "the team"
    out = [f"Who is waiting on a reply from {who} right now, longest first?",
           "Which customers mentioned a trade this week and have no appointment set?",
           f"What objections is {who} hearing most on calls?",
           "Which internet leads went quiet after the first reply?",
           "Any promises made to customers that don't have a task behind them?"]
    if stats.get("calls"):
        out.insert(2, "Summarize the recorded calls: what went well, what was missed")
    return out[:6]
