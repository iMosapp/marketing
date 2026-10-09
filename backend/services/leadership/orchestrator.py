"""Mode B, Leadership Roundtable: a persisted state machine over one lt_roundtables document.
selected -> running(assessing -> challenging -> synthesizing) -> awaiting_decision -> decided; cancelled | failed | paused | interrupted are resumable or final.
The Chief of Staff is code; the model is called only to select participants, assess, challenge and synthesize. Nothing here writes to the Command Center."""
import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone

from services import command_center as cc
from services import command_center_ai as ai
from services.leadership import context, core, roster

logger = logging.getLogger(__name__)
RT, DECISIONS, REVIEWS = "lt_roundtables", "lt_decisions", "lt_reviews"
STEPS = ("assessing", "challenging", "synthesizing")
TIMEOUT = {"lt_select": 45, "lt_assess": 90, "lt_challenge": 90, "lt_synth": 130}
STALE_S = 240
AVG_CALL_USD = 0.02  # estimate: the measured Founder Advisor average ($0.0095/call) roughly doubled for the larger roundtable prompts
_tasks: dict = {}


def _now():
    return datetime.now(timezone.utc)


def _aware(dt):
    return dt.replace(tzinfo=timezone.utc) if isinstance(dt, datetime) and dt.tzinfo is None else dt


def pub(r: dict) -> dict:
    out = {k: (cc._iso(v) if isinstance(v, datetime) else v) for k, v in r.items() if k not in ("_id", "company_id")}
    out["id"] = str(r["_id"])
    for s, st in (out.get("steps") or {}).items():
        for k in ("started_at", "finished_at"):
            if isinstance(st.get(k), datetime):
                st[k] = st[k].isoformat()
    return out


def summary(r: dict) -> dict:
    return {"id": str(r["_id"]), "kind": "roundtable", "title": r.get("title") or ai.clean(r.get("question"), 90), "status": r["status"], "step": r.get("step"), "participants": [p["key"] for p in r.get("participants") or []],
            "created_at": cc._iso(r.get("created_at")), "updated_at": cc._iso(r.get("updated_at")), "cost_usd": r.get("cost_usd", 0), "dissent_count": len([d for d in r.get("dissent") or [] if not d.get("resolved")]), "decision_id": r.get("decision_id")}


async def list_roundtables(db, company_id: str) -> list:
    rows = await db[RT].find({"company_id": company_id}, {"question": 1, "title": 1, "status": 1, "step": 1, "participants": 1, "created_at": 1, "updated_at": 1, "cost_usd": 1, "dissent": 1, "decision_id": 1}).sort("updated_at", -1).to_list(100)
    return [summary(r) for r in rows]


async def get(db, company_id: str, rid: str) -> dict | None:
    oid = cc._oid(rid)
    return await db[RT].find_one({"_id": oid, "company_id": company_id}) if oid else None


def _unsupported(key: str, data: dict) -> list:
    """FACT-labelled sentences with no citation ([F3], [CC], [D2]) are flagged in code; this is the cheapest hallucination check there is."""
    out = []
    texts = [data.get("perspective") or ""] + [str(x) for x in (data.get("evidence") or [])]
    for t in texts:
        for s in re.split(r"(?<=[.!?])\s+", t):
            if "FACT" in s and not re.search(r"\[(F\d+|CC|D\d+)\]", s):
                out.append({"agent_key": key, "claim": ai.clean(s, 240)})
    return out[:6]


def estimate(n_participants: int) -> dict:
    calls = n_participants * 2 + 1
    return {"calls": calls, "usd": round(calls * AVG_CALL_USD, 2), "assumption": f"{calls} model calls at about ${AVG_CALL_USD:.2f} each (the Founder Advisor averaged $0.0095 per call; roundtable prompts are roughly twice as long). Actual cost is measured from provider token counts."}


# ───────────────────────── create: Chief of Staff selects the room ─────────────────────────
SELECT_FORMAT = ('Return JSON: {"restated": "the question restated as one decision the leadership team must inform", "participants": [{"key": "", "why": "one line"}], '
                 '"devil_advocate": "key of the participant best placed to argue against the likely majority (never strategic_advisor)", "clarifying_question": "one question for the founder ONLY if the request cannot be assessed at all, else empty"}. '
                 'Pick the minimum useful set: every executive whose department is materially affected, nobody else. The strategic_advisor always participates.')


async def create(db, company_id: str, me: dict, question: str, source: dict | None = None) -> dict:
    question = ai.clean(question, 3000)
    if not question:
        raise ValueError("Say or type the topic first.")
    await core.check_budget(db, company_id)
    dup = await db[RT].find_one({"company_id": company_id, "question": question, "status": {"$in": ["selected", "running"]}, "created_at": {"$gte": _now() - timedelta(minutes=10)}})
    if dup:
        return pub(dup)
    ros = [a for a in await roster.roster(db, company_id) if a["enabled"] and not a["is_orchestrator"]]
    cos = await roster.agent(db, company_id, "chief_of_staff")
    ctl = (await core.company(db, company_id))["controls"]
    comp = await context.compile(db, company_id, cos, question=question, include_docs=False)
    room = "\n".join(f"- {a['key']}: {a['title']} · {a['mission']}" for a in ros)
    data, usage = await ai.complete_json(db, "lt_select", comp["system"] + "\n\nAVAILABLE EXECUTIVES:\n" + room + "\n\n" + SELECT_FORMAT, [{"role": "user", "content": question}], max_tokens=900, tags={"company_id": company_id, "step": "selecting"}, timeout=TIMEOUT["lt_select"])
    by_key = {a["key"]: a for a in ros}
    picked = []
    for p in (data.get("participants") or []):
        k = str((p or {}).get("key") or "").strip()
        if k in by_key and k not in [x["key"] for x in picked]:
            picked.append({"key": k, "title": by_key[k]["title"], "short": by_key[k]["short"], "why": ai.clean((p or {}).get("why"), 200), "devil_advocate": False, "color": by_key[k].get("color")})
    if "strategic_advisor" in by_key and "strategic_advisor" not in [x["key"] for x in picked]:
        picked.insert(0, {"key": "strategic_advisor", "title": by_key["strategic_advisor"]["title"], "short": "Advisor", "why": "always participates", "devil_advocate": False, "color": by_key["strategic_advisor"].get("color")})
    picked = picked[: ctl["max_participants"]]
    _assign_devil(picked, str(data.get("devil_advocate") or ""), await db[RT].count_documents({"company_id": company_id}))
    now = _now()
    doc = {"company_id": company_id, "question": question, "restated": ai.clean(data.get("restated"), 400) or question, "clarifying_question": ai.clean(data.get("clarifying_question"), 300), "source": source or {}, "title": ai.clean(data.get("restated") or question, 90),
           "status": "selected", "step": None, "steps": {}, "participants": picked, "selection": {"usage": usage, "by": "chief_of_staff"}, "assessments": {}, "challenges": {}, "dissent": [], "unsupported": [], "brief": None,
           "estimate": estimate(len(picked)), "cost_usd": round(usage.get("approx_cost_usd", 0), 4), "decision_id": None, "cancel_requested": False, "heartbeat_at": now, "error": None, "modify_count": 0,
           "created_by": cc._who(me), "created_at": now, "updated_at": now}
    r = await db[RT].insert_one(doc)
    doc["_id"] = r.inserted_id
    await core.audit(db, company_id, me, "roundtable_created", {"kind": "roundtable", "id": str(r.inserted_id)}, after={"participants": [p["key"] for p in picked]})
    return pub(doc)


def _assign_devil(picked: list, suggested: str, rotation: int):
    cands = [p for p in picked if p["key"] != "strategic_advisor"]
    if not cands:
        return
    pick = next((p for p in cands if p["key"] == suggested), None) or cands[rotation % len(cands)]
    for p in picked:
        p["devil_advocate"] = p is pick


async def set_participants(db, company_id: str, rt: dict, keys: list) -> dict:
    if rt["status"] != "selected":
        raise ValueError("Participants can only change before the discussion starts")
    ros = {a["key"]: a for a in await roster.roster(db, company_id) if a["enabled"] and not a["is_orchestrator"]}
    ctl = (await core.company(db, company_id))["controls"]
    keep = {p["key"]: p for p in rt["participants"]}
    picked = []
    for k in keys:
        if k in ros and k not in [x["key"] for x in picked]:
            picked.append(keep.get(k) or {"key": k, "title": ros[k]["title"], "short": ros[k]["short"], "why": "added by the founder", "devil_advocate": False, "color": ros[k].get("color")})
    if "strategic_advisor" not in [x["key"] for x in picked] and "strategic_advisor" in ros:
        picked.insert(0, keep.get("strategic_advisor") or {"key": "strategic_advisor", "title": ros["strategic_advisor"]["title"], "short": "Advisor", "why": "always participates", "devil_advocate": False, "color": ros["strategic_advisor"].get("color")})
    if len(picked) < 2:
        raise ValueError("A roundtable needs at least two executives")
    if len(picked) > ctl["max_participants"]:
        raise ValueError(f"At most {ctl['max_participants']} executives per roundtable")
    if not any(p["devil_advocate"] for p in picked):
        _assign_devil(picked, "", await db[RT].count_documents({"company_id": company_id}))
    await db[RT].update_one({"_id": rt["_id"], "status": "selected"}, {"$set": {"participants": picked, "estimate": estimate(len(picked)), "updated_at": _now()}})
    return pub(await db[RT].find_one({"_id": rt["_id"]}))


# ───────────────────────── run: the state machine ─────────────────────────
async def start(db, company_id: str, rt: dict, me: dict) -> dict:
    await core.check_budget(db, company_id)
    r = await db[RT].update_one({"_id": rt["_id"], "status": "selected"}, {"$set": {"status": "running", "step": "assessing", "cancel_requested": False, "error": None, "heartbeat_at": _now(), "updated_at": _now()}})
    if r.modified_count:
        await core.audit(db, company_id, me, "roundtable_started", {"kind": "roundtable", "id": str(rt["_id"])})
        _spawn(db, rt["_id"])
    return pub(await db[RT].find_one({"_id": rt["_id"]}))


async def resume(db, company_id: str, rt: dict, me: dict) -> dict:
    """Retry from the current step: finished participant calls are kept, only missing or failed ones run again."""
    if rt["status"] not in ("failed", "paused", "interrupted"):
        raise ValueError("Only a failed, paused or interrupted roundtable can be resumed")
    await core.check_budget(db, company_id)
    r = await db[RT].update_one({"_id": rt["_id"], "status": rt["status"]}, {"$set": {"status": "running", "step": rt.get("step") or "assessing", "cancel_requested": False, "error": None, "heartbeat_at": _now(), "updated_at": _now()}})
    if r.modified_count:
        await core.audit(db, company_id, me, "roundtable_resumed", {"kind": "roundtable", "id": str(rt["_id"])})
        _spawn(db, rt["_id"])
    return pub(await db[RT].find_one({"_id": rt["_id"]}))


async def cancel(db, company_id: str, rt: dict, me: dict) -> dict:
    await db[RT].update_one({"_id": rt["_id"], "status": {"$in": ["selected", "running", "paused", "interrupted", "failed"]}}, {"$set": {"cancel_requested": True, "status": "cancelled", "updated_at": _now()}})
    await core.audit(db, company_id, me, "roundtable_cancelled", {"kind": "roundtable", "id": str(rt["_id"])})
    return pub(await db[RT].find_one({"_id": rt["_id"]}))


def _spawn(db, rid):
    t = _tasks.get(str(rid))
    if t and not t.done():
        return
    _tasks[str(rid)] = asyncio.create_task(_run(db, rid))


async def _alive(db, rid) -> dict | None:
    """Heartbeat + the two ways a run stops between calls: founder cancel and emergency stop. Returns the fresh doc or None when the run must end."""
    rt = await db[RT].find_one({"_id": rid})
    if not rt or rt.get("cancel_requested") or rt["status"] != "running":
        return None
    ctl = (await core.company(db, rt["company_id"]))["controls"]
    if ctl.get("stopped"):
        await db[RT].update_one({"_id": rid, "status": "running"}, {"$set": {"status": "paused", "error": "Emergency stop", "updated_at": _now()}})
        return None
    try:
        await core.check_budget(db, rt["company_id"])
    except ai.AdvisorBusy as e:
        await db[RT].update_one({"_id": rid, "status": "running"}, {"$set": {"status": "paused", "error": str(e)[:300], "updated_at": _now()}})
        return None
    await db[RT].update_one({"_id": rid}, {"$set": {"heartbeat_at": _now()}})
    return rt


async def _run(db, rid):
    try:
        for step in STEPS:
            rt = await _alive(db, rid)
            if not rt:
                return
            if STEPS.index(step) < STEPS.index(rt.get("step") or "assessing"):
                continue
            await db[RT].update_one({"_id": rid}, {"$set": {"step": step, f"steps.{step}.status": "running", f"steps.{step}.started_at": rt.get("steps", {}).get(step, {}).get("started_at") or _now(), "updated_at": _now()}})
            ok = await {"assessing": _assess_all, "challenging": _challenge_all, "synthesizing": _synthesize}[step](db, rt)
            if not ok:
                return
            await db[RT].update_one({"_id": rid}, {"$set": {f"steps.{step}.status": "done", f"steps.{step}.finished_at": _now(), "updated_at": _now()}})
        rt = await db[RT].find_one({"_id": rid})
        if rt and rt["status"] == "running":
            await _open_decision(db, rt)
    except Exception as e:  # noqa: BLE001 - the run must never die silently
        logger.exception("[Leadership] roundtable %s failed", rid)
        await db[RT].update_one({"_id": rid, "status": "running"}, {"$set": {"status": "failed", "error": str(e)[:300], "updated_at": _now()}})


def _peer_block(rt: dict, exclude: str) -> str:
    lines = []
    for p in rt["participants"]:
        a = (rt.get("assessments") or {}).get(p["key"]) or {}
        if p["key"] == exclude or a.get("status") != "ok":
            continue
        d = a["data"]
        lines.append(f"[{p['key']} · {p['title']} · confidence {d.get('confidence')}] recommendation: {d.get('recommendation')}\n  perspective: {d.get('perspective')}\n  assumptions: {'; '.join(d.get('assumptions') or [])}\n  risks: {'; '.join(d.get('risks') or [])}\n  dependencies: {'; '.join(d.get('dependencies') or [])}")
    return ai._block("peer_assessments", lines)


ASSESS_FORMAT = ('Give your INDEPENDENT assessment (you have not seen your peers). Return JSON: {"perspective": "three to six sentences from your department\'s view, with FACT/ASSUMPTION/RISK labels and citations", '
                 '"recommendation": "one clear recommendation in one or two sentences", "evidence": ["FACT: ... [F3]"], "assumptions": ["..."], "risks": ["..."], "dependencies": ["what must exist or happen first"], '
                 '"questions_for": [{"to": "cto|cpo|cro|coo|cfo|strategic_advisor", "question": ""}], "confidence": "low|medium|high", "limitations": ["knowledge you lack for this question"]}. '
                 'If your role has little to add, say so briefly in perspective and keep the other fields short. BE CONCISE: perspective at most 120 words; every list at most 5 items of one sentence each.')
DEVIL_RULES = ("\n\nDEVIL'S ADVOCATE DUTY: the Chief of Staff has assigned you to argue the strongest evidence-based case AGAINST the recommendation that is likely to prevail. Make substantive objections with consequences, "
               "not contrarian noise; where you cannot find an evidence-based objection, say so. Your real position is still recorded in position_change.")
CHALLENGE_FORMAT = ('Read your peers\' assessments. Return JSON: {"challenges": [{"to": "key", "claim": "the exact claim you challenge", "objection": "why it is wrong or unsupported", "evidence": "your evidence or the missing evidence", '
                    '"severity": "material|minor", "consequence": "the business consequence if they are wrong"}], "agreements": [{"with": "key", "on": "what you agree on"}], "position_change": "what you changed after reading peers, or none", '
                    '"unsupported_assumptions": ["key: the assumption"], "missing_dependencies": ["dependency nobody named"]}. Material disagreements must be surfaced, never smoothed over; do not invent disagreement either. '
                    'BE CONCISE: at most 4 challenges and 4 agreements; every field one or two sentences; lists at most 4 items.')


async def _call_each(db, rt: dict, field: str, kind: str, build):
    """Run one model call per participant in parallel; a failure is recorded on that participant only. Returns True when at least two participants succeeded."""
    rid = rt["_id"]
    pending = [p for p in rt["participants"] if ((rt.get(field) or {}).get(p["key"]) or {}).get("status") != "ok"]

    async def one(p):
        try:
            a = await roster.agent(db, rt["company_id"], p["key"])
            system, user_msg, max_tokens = await build(a, p)
            data, usage = await ai.complete_json(db, kind, system, [{"role": "user", "content": user_msg}], max_tokens=max_tokens, tags={"company_id": rt["company_id"], "roundtable_id": str(rid), "agent_key": p["key"], "step": field}, timeout=TIMEOUT[kind])
            inc = {"$inc": {"cost_usd": round(usage.get("approx_cost_usd", 0), 6)}}
            if not data:
                await db[RT].update_one({"_id": rid}, {"$set": {f"{field}.{p['key']}": {"status": "failed", "error": "no usable answer (the reply was not valid JSON)", "usage": usage, "at": _now()}, "heartbeat_at": _now()}, **inc})
                return
            await db[RT].update_one({"_id": rid}, {"$set": {f"{field}.{p['key']}": {"status": "ok", "data": _shape(field, data), "usage": usage, "truncated": bool(data.get("_truncated")), "at": _now()}, "heartbeat_at": _now()}, **inc})
        except (ai.AdvisorUnavailable, ai.AdvisorBusy, ValueError) as e:
            await db[RT].update_one({"_id": rid}, {"$set": {f"{field}.{p['key']}": {"status": "failed", "error": str(e)[:200], "at": _now()}, "heartbeat_at": _now()}})
    await asyncio.gather(*(one(p) for p in pending))
    fresh = await db[RT].find_one({"_id": rid})
    ok = [k for k, v in (fresh.get(field) or {}).items() if v.get("status") == "ok"]
    if len(ok) < 2:
        await db[RT].update_one({"_id": rid, "status": "running"}, {"$set": {"status": "failed", "error": f"Only {len(ok)} executive(s) answered during {field}; retry when the model is available.", "updated_at": _now()}})
        return False
    return True


def _lst(v, cap=300, n=10):
    return [ai.clean(x, cap) for x in v if ai.clean(x, cap)][:n] if isinstance(v, list) else []


def _shape(field: str, d: dict) -> dict:
    if field == "assessments":
        return {"perspective": ai.clean(d.get("perspective"), 2000), "recommendation": ai.clean(d.get("recommendation"), 500), "evidence": _lst(d.get("evidence")), "assumptions": _lst(d.get("assumptions")), "risks": _lst(d.get("risks")),
                "dependencies": _lst(d.get("dependencies")), "questions_for": [{"to": ai.clean(q.get("to"), 30), "question": ai.clean(q.get("question"), 300)} for q in (d.get("questions_for") or []) if isinstance(q, dict) and ai.clean(q.get("question"), 300)][:6],
                "confidence": d.get("confidence") if d.get("confidence") in ("low", "medium", "high") else "low", "limitations": _lst(d.get("limitations"))}
    return {"challenges": [{"to": ai.clean(c.get("to"), 30), "claim": ai.clean(c.get("claim"), 300), "objection": ai.clean(c.get("objection"), 500), "evidence": ai.clean(c.get("evidence"), 400), "severity": "material" if str(c.get("severity")).lower().startswith("mat") else "minor",
                            "consequence": ai.clean(c.get("consequence"), 300)} for c in (d.get("challenges") or []) if isinstance(c, dict) and ai.clean(c.get("claim"), 300)][:8],
            "agreements": [{"with": ai.clean(a.get("with"), 30), "on": ai.clean(a.get("on"), 300)} for a in (d.get("agreements") or []) if isinstance(a, dict) and ai.clean(a.get("on"), 300)][:8],
            "position_change": ai.clean(d.get("position_change"), 500), "unsupported_assumptions": _lst(d.get("unsupported_assumptions")), "missing_dependencies": _lst(d.get("missing_dependencies"))}


async def _assess_all(db, rt: dict) -> bool:
    async def build(a, p):
        comp = await context.compile(db, rt["company_id"], a, question=rt["question"])
        return comp["system"] + "\n\n" + ASSESS_FORMAT, f"ROUNDTABLE QUESTION: {rt['restated']}\n\nFounder's words: {rt['question']}", 2200
    ok = await _call_each(db, rt, "assessments", "lt_assess", build)
    if ok:
        fresh = await db[RT].find_one({"_id": rt["_id"]})
        uns = [u for k, v in (fresh.get("assessments") or {}).items() if v.get("status") == "ok" for u in _unsupported(k, v["data"])]
        await db[RT].update_one({"_id": rt["_id"]}, {"$set": {"unsupported": uns}})
    return ok


async def _challenge_all(db, rt: dict) -> bool:
    rt = await db[RT].find_one({"_id": rt["_id"]})
    present = [p for p in rt["participants"] if (rt["assessments"].get(p["key"]) or {}).get("status") == "ok"]
    rt_present = {**rt, "participants": present}

    async def build(a, p):
        comp = await context.compile(db, rt["company_id"], a, question=rt["question"], include_docs=False)
        own = rt["assessments"][p["key"]]["data"]
        sys = comp["system"] + (DEVIL_RULES if p.get("devil_advocate") else "") + "\n\n" + CHALLENGE_FORMAT
        user = f"ROUNDTABLE QUESTION: {rt['restated']}\n\nYOUR OWN ASSESSMENT: recommendation: {own['recommendation']}\n{own['perspective']}\n\n" + _peer_block(rt, p["key"])
        return sys, user, 2200
    ok = await _call_each(db, rt_present, "challenges", "lt_challenge", build)
    if ok:
        fresh = await db[RT].find_one({"_id": rt["_id"]})
        await db[RT].update_one({"_id": rt["_id"]}, {"$set": {"dissent": _dissent(fresh)}})
    return ok


def _dissent(rt: dict) -> list:
    """The register is built from the challenge data, so synthesis prose cannot drop a disagreement. The same claim challenged by several executives is one entry."""
    titles = {p["key"]: p["title"] for p in rt["participants"] if ((rt.get("assessments") or {}).get(p["key"]) or {}).get("status") == "ok"}
    devils = {p["key"] for p in rt["participants"] if p.get("devil_advocate")}
    recs = {k: (v.get("data") or {}).get("recommendation") for k, v in (rt.get("assessments") or {}).items() if v.get("status") == "ok"}
    merged: dict = {}
    for frm, ch in (rt.get("challenges") or {}).items():
        if ch.get("status") != "ok":
            continue
        for c in ch["data"]["challenges"]:
            if c["severity"] != "material" or c["to"] not in titles or c["to"] == frm:
                continue
            key = (c["to"], re.sub(r"[^a-z0-9]+", " ", c["claim"].lower())[:90].strip())
            d = merged.get(key)
            if d:
                if frm not in d["executives"]:
                    d["executives"].insert(len(d["executives"]) - 1, frm)
                    d["positions"].insert(len(d["positions"]) - 1, {"key": frm, "position": c["objection"]})
                d["raised_by_devil_advocate"] = d["raised_by_devil_advocate"] or frm in devils
                continue
            merged[key] = {"issue": c["claim"], "executives": [frm, c["to"]], "positions": [{"key": frm, "position": c["objection"]}, {"key": c["to"], "position": recs.get(c["to"]) or c["claim"]}],
                           "evidence": c["evidence"], "consequences": c["consequence"], "resolved": False, "how": "", "needs_founder": True, "raised_by_devil_advocate": frm in devils}
    return [{"id": f"d{i}", **d} for i, d in enumerate(list(merged.values())[:12], 1)]


SYNTH_FORMAT = ('Write the executive decision brief from the assessments, challenges and dissent register. Return JSON: {"title": "short title for the decision record", "opportunity": "the business opportunity or problem in two sentences", '
                '"alignment": "strategic alignment with the One Big Thing and active priorities, including the Strategic Advisor\'s view", "department_recommendations": [{"key": "", "summary": "one or two sentences"}], '
                '"agreements": ["..."], "disagreements": "plain summary of the material disagreements and why they matter", "technical": "technical requirements and dependencies", "financial": "financial considerations, with data status", '
                '"operational": "operational, onboarding and support implications", "commercial": "commercial considerations: buyer, price corridor, channel", "dependencies": ["..."], "risks": ["..."], "missing": ["information the company lacks"], '
                '"recommended_decision": "one clear recommendation (for example validate first / proceed with scope X / park)", "next_actions": [{"action": "", "owner_key": "cto|cpo|cro|coo|cfo|strategic_advisor|founder", "why": ""}], '
                '"decisions_required": [{"title": "", "detail": "what the founder is deciding and the options"}], "dissent_resolutions": [{"id": "d1", "resolved": false, "how": "why it is or is not resolved by the discussion"}]}. '
                'Preserve every material disagreement; never manufacture agreement. Where an executive did not answer, say the department is unassessed. '
                'BE CONCISE: every prose field at most 90 words; every list at most 6 items of one sentence; at most 6 next_actions and 4 decisions_required.')


async def _synthesize(db, rt: dict) -> bool:
    rt = await db[RT].find_one({"_id": rt["_id"]})
    cos = await roster.agent(db, rt["company_id"], "chief_of_staff")
    comp = await context.compile(db, rt["company_id"], cos, question=rt["question"], include_docs=False)
    parts = [f"ROUNDTABLE QUESTION: {rt['restated']}\nFounder's words: {rt['question']}", _peer_block({**rt, "participants": rt["participants"]}, exclude="")]
    chal = []
    for k, v in (rt.get("challenges") or {}).items():
        if v.get("status") == "ok":
            d = v["data"]
            chal.append(f"[{k}] position change: {d['position_change']}\n  challenges: " + " | ".join(f"to {c['to']}: {c['claim']} -> {c['objection']} ({c['severity']})" for c in d["challenges"]) + "\n  agreements: " + "; ".join(f"with {a['with']}: {a['on']}" for a in d["agreements"]))
    parts.append(ai._block("challenge_round", chal))
    parts.append(ai._block("dissent_register", [f"{d['id']}: {d['issue']} · {d['executives'][0]} vs {d['executives'][1]} · consequence: {d['consequences']}" for d in rt.get("dissent") or []]))
    missing = [f"{p['key']} did not answer ({(rt['assessments'].get(p['key']) or {}).get('error', 'no response')})" for p in rt["participants"] if (rt["assessments"].get(p["key"]) or {}).get("status") != "ok"]
    if missing:
        parts.append(ai._block("unassessed_departments", missing))
    if rt.get("founder_note"):
        parts.append(ai._block("founder_requested_changes", [rt["founder_note"]]))
    try:
        data, usage = await ai.complete_json(db, "lt_synth", comp["system"] + "\n\n" + SYNTH_FORMAT, [{"role": "user", "content": "\n\n".join(parts)}], max_tokens=3600, tags={"company_id": rt["company_id"], "roundtable_id": str(rt["_id"]), "agent_key": "chief_of_staff", "step": "synthesizing"}, timeout=TIMEOUT["lt_synth"])
    except (ai.AdvisorUnavailable, ai.AdvisorBusy) as e:
        await db[RT].update_one({"_id": rt["_id"], "status": "running"}, {"$set": {"status": "failed", "error": f"Synthesis failed: {e}"[:300], "updated_at": _now()}})
        return False
    if not data:
        await db[RT].update_one({"_id": rt["_id"], "status": "running"}, {"$set": {"status": "failed", "error": "Synthesis returned no usable brief", "updated_at": _now()}})
        return False
    valid = {p["key"] for p in rt["participants"]} | {"founder", "chief_of_staff"}
    brief = {"title": ai.clean(data.get("title"), 120) or rt["title"], "opportunity": ai.clean(data.get("opportunity"), 800), "alignment": ai.clean(data.get("alignment"), 1200),
             "department_recommendations": [{"key": ai.clean(x.get("key"), 30), "summary": ai.clean(x.get("summary"), 500)} for x in (data.get("department_recommendations") or []) if isinstance(x, dict) and ai.clean(x.get("summary"), 500)][:8],
             "agreements": _lst(data.get("agreements"), 300, 8), "disagreements": ai.clean(data.get("disagreements"), 1200), "technical": ai.clean(data.get("technical"), 1200), "financial": ai.clean(data.get("financial"), 1200),
             "operational": ai.clean(data.get("operational"), 1200), "commercial": ai.clean(data.get("commercial"), 1200), "dependencies": _lst(data.get("dependencies"), 300, 10), "risks": _lst(data.get("risks"), 300, 10), "missing": _lst(data.get("missing"), 300, 10),
             "recommended_decision": ai.clean(data.get("recommended_decision"), 800),
             "next_actions": [{"action": ai.clean(x.get("action"), 300), "owner_key": x.get("owner_key") if x.get("owner_key") in valid else "founder", "why": ai.clean(x.get("why"), 200)} for x in (data.get("next_actions") or []) if isinstance(x, dict) and ai.clean(x.get("action"), 300)][:10],
             "decisions_required": [{"title": ai.clean(x.get("title"), 200), "detail": ai.clean(x.get("detail"), 600)} for x in (data.get("decisions_required") or []) if isinstance(x, dict) and ai.clean(x.get("title"), 200)][:6],
             "unassessed": missing, "usage": usage, "truncated": bool(data.get("_truncated")), "generated_at": _now()}
    dissent = rt.get("dissent") or []
    res = {str(x.get("id")): x for x in (data.get("dissent_resolutions") or []) if isinstance(x, dict)}
    for d in dissent:
        r = res.get(d["id"])
        if r:
            d["resolved"] = bool(r.get("resolved"))
            d["how"] = ai.clean(r.get("how"), 400)
            d["needs_founder"] = not d["resolved"]
    await db[RT].update_one({"_id": rt["_id"]}, {"$set": {"brief": brief, "dissent": dissent, "title": brief["title"], "updated_at": _now()}, "$inc": {"cost_usd": round(usage.get("approx_cost_usd", 0), 6)}})
    return True


async def _open_decision(db, rt: dict):
    """The brief is ready: one decision record, pending the founder. Nothing else changes anywhere."""
    now = _now()
    did = rt.get("decision_id")
    if did:
        await db[DECISIONS].update_one({"_id": cc._oid(did)}, {"$set": {"status": "pending", "recommendation": rt["brief"]["recommended_decision"], "title": rt["brief"]["title"], "next_actions": rt["brief"]["next_actions"], "decisions_required": rt["brief"]["decisions_required"], "updated_at": now},
                                                                 "$push": {"history": {"at": now, "event": "re-synthesized after the founder requested changes"}}})
    else:
        d = {"company_id": rt["company_id"], "roundtable_id": str(rt["_id"]), "title": rt["brief"]["title"], "recommendation": rt["brief"]["recommended_decision"], "next_actions": rt["brief"]["next_actions"], "decisions_required": rt["brief"]["decisions_required"],
             "status": "pending", "founder": None, "history": [{"at": now, "event": "brief ready"}], "created_at": now, "updated_at": now}
        r = await db[DECISIONS].insert_one(d)
        did = str(r.inserted_id)
    await db[RT].update_one({"_id": rt["_id"], "status": "running"}, {"$set": {"status": "awaiting_decision", "step": "done", "decision_id": did, "updated_at": now}})


# ───────────────────────── decisions ─────────────────────────
ACTIONS = ("approve", "reject", "defer", "modify")


def pub_decision(d: dict) -> dict:
    out = {k: (cc._iso(v) if isinstance(v, datetime) else v) for k, v in d.items() if k not in ("_id", "company_id")}
    out["id"] = str(d["_id"])
    if out.get("founder") and isinstance(out["founder"].get("at"), datetime):
        out["founder"]["at"] = out["founder"]["at"].isoformat()
    for h in out.get("history") or []:
        if isinstance(h.get("at"), datetime):
            h["at"] = h["at"].isoformat()
    return out


async def decisions(db, company_id: str, status: str | None = None) -> list:
    q = {"company_id": company_id}
    if status:
        q["status"] = status
    return [pub_decision(d) async for d in db[DECISIONS].find(q).sort("created_at", -1)]


async def decide(db, company_id: str, did: str, me: dict, action: str, reason: str) -> dict:
    if action not in ACTIONS:
        raise ValueError("Unknown action")
    reason = ai.clean(reason, 1200)
    if action == "modify" and not reason:
        raise ValueError("Say what should change")
    d = await db[DECISIONS].find_one({"_id": cc._oid(did), "company_id": company_id})
    if not d:
        raise ValueError("Decision not found")
    if d["status"] not in ("pending", "deferred"):
        raise ValueError("This decision has already been made")
    rt = await db[RT].find_one({"_id": cc._oid(d["roundtable_id"])})
    if action == "modify" and rt and int(rt.get("modify_count") or 0) >= 1:
        raise ValueError("The brief was already re-synthesized once. Approve, reject or defer it, or convene a new roundtable.")
    if action == "modify":
        await core.check_budget(db, company_id)
    now = _now()
    status = {"approve": "approved", "reject": "rejected", "defer": "deferred", "modify": "modify_requested"}[action]
    r = await db[DECISIONS].update_one({"_id": d["_id"], "status": d["status"]}, {"$set": {"status": status, "founder": {"action": action, "reason": reason, "by": cc._who(me), "at": now}, "updated_at": now}, "$push": {"history": {"at": now, "event": f"founder: {action}", "reason": reason}}})
    if not r.modified_count:
        raise ValueError("This decision was just changed elsewhere; reload")
    await core.audit(db, company_id, me, f"decision_{action}", {"kind": "decision", "id": did}, after={"status": status}, reason=reason)
    if rt:
        if action == "modify":
            await db[RT].update_one({"_id": rt["_id"], "status": "awaiting_decision"}, {"$set": {"status": "running", "step": "synthesizing", "founder_note": reason, "cancel_requested": False, "heartbeat_at": now, "updated_at": now}, "$inc": {"modify_count": 1}})
            _spawn(db, rt["_id"])
        else:
            await db[RT].update_one({"_id": rt["_id"]}, {"$set": {"status": "decided", "updated_at": now}})
    return pub_decision(await db[DECISIONS].find_one({"_id": d["_id"]}))


# ───────────────────────── reaper (the only scheduled piece) ─────────────────────────
async def fail_interrupted(db, all_running: bool = False) -> int:
    """Stale heartbeat (poll time) or every running run (startup: the asyncio tasks died with the old process)."""
    q = {"status": "running"} if all_running else {"status": "running", "heartbeat_at": {"$lt": _now() - timedelta(seconds=STALE_S)}}
    r = await db[RT].update_many(q, {"$set": {"status": "interrupted", "error": "The server restarted or the run stalled; resume to continue from the current step.", "updated_at": _now()}})
    return r.modified_count


# ───────────────────────── Mode D lite: executive operating review ─────────────────────────
REVIEW_FORMAT = ('Return JSON: {"headline": "where the business stands in one sentence", "one_big_thing": "status in one line", "priorities": ["one line per ACTIVE priority, or a single line saying none is active"], '
                 '"roadmap": "progress and blocked milestones from the data only", "pending_decisions": ["one line each"], "wins": ["recent wins from the data"], "risks": ["important risks, with the fact they rest on"], '
                 '"missing_knowledge": ["what the company has not recorded that the team needs"], "next_actions": [{"action": "", "owner_key": "founder|cto|cpo|cro|coo|cfo|strategic_advisor", "why": ""}]}. Never invent due dates, numbers or results.')


async def review(db, company_id: str, me: dict) -> dict:
    await core.check_budget(db, company_id)
    cos = await roster.agent(db, company_id, "chief_of_staff")
    comp = await context.compile(db, company_id, cos, include_docs=False)
    pend = await decisions(db, company_id, "pending")
    recent = await db[RT].find({"company_id": company_id, "status": {"$in": ["awaiting_decision", "decided"]}}, {"title": 1, "status": 1, "dissent": 1, "brief.recommended_decision": 1}).sort("updated_at", -1).to_list(5)
    ros = await roster.roster(db, company_id)
    from services.leadership import knowledge
    snap = await knowledge.cc_snapshot(db)
    gaps = []
    for a in ros:
        if a["is_orchestrator"]:
            continue
        rd = await knowledge.readiness(db, company_id, a, snap)
        if rd["missing"]:
            gaps.append(f"{a['short']}: {rd['score']}% ready; missing {', '.join(m['label'] for m in rd['missing'][:3])}")
    blocks = [ai._block("pending_decisions", [f"- {d['title']}: {d['recommendation']}" for d in pend]), ai._block("recent_roundtables", [f"- {r.get('title')} [{r['status']}] · unresolved dissent {len([x for x in r.get('dissent') or [] if not x.get('resolved')])}" for r in recent]), ai._block("knowledge_readiness_gaps", gaps)]
    data, usage = await ai.complete_json(db, "lt_review", comp["system"] + "\n\n" + REVIEW_FORMAT, [{"role": "user", "content": "\n\n".join(blocks) + "\n\nProduce the operating review."}], max_tokens=1200, tags={"company_id": company_id, "agent_key": "chief_of_staff", "step": "review"}, timeout=80)
    valid = {a["key"] for a in ros} | {"founder"}
    out = {"headline": ai.clean(data.get("headline"), 400), "one_big_thing": ai.clean(data.get("one_big_thing"), 300), "priorities": _lst(data.get("priorities"), 300, 3), "roadmap": ai.clean(data.get("roadmap"), 800), "pending_decisions": _lst(data.get("pending_decisions"), 300, 8),
           "wins": _lst(data.get("wins"), 300, 6), "risks": _lst(data.get("risks"), 300, 8), "missing_knowledge": _lst(data.get("missing_knowledge"), 300, 8),
           "next_actions": [{"action": ai.clean(x.get("action"), 300), "owner_key": x.get("owner_key") if x.get("owner_key") in valid else "founder", "why": ai.clean(x.get("why"), 200)} for x in (data.get("next_actions") or []) if isinstance(x, dict) and ai.clean(x.get("action"), 300)][:8],
           "readiness_gaps": gaps, "facts_used": comp["facts"], "usage": usage, "generated_at": _now(), "company_id": company_id, "requested_by": cc._who(me)}
    await db[REVIEWS].insert_one(dict(out))
    out.pop("_id", None)
    out["generated_at"] = cc._iso(out["generated_at"])
    return out


async def latest_review(db, company_id: str) -> dict | None:
    r = await db[REVIEWS].find_one({"company_id": company_id}, sort=[("generated_at", -1)])
    if not r:
        return None
    r.pop("_id", None)
    r["generated_at"] = cc._iso(r["generated_at"])
    return r
