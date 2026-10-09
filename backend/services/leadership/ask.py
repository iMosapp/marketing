"""Mode A, Ask an Executive: threads on the existing cc_conversations collection (the Founder Advisor's history stays intact and appears under the Strategic Advisor).
A thread may hold several executives; the founder picks who answers each turn and can escalate the topic to a roundtable."""
from services import command_center as cc
from services import command_center_ai as ai
from services.leadership import context, core, roster

ADVISOR = "strategic_advisor"


def _pub(c: dict, full: bool = False) -> dict:
    out = ai._pub_convo(c, full)
    out["agent_keys"] = c.get("agent_keys") or [ADVISOR]
    out["kind"] = "thread"
    return out


async def list_threads(db, company_id: str) -> list:
    rows = await db[ai.CONVOS].find({"archived": {"$ne": True}, **core.scope(company_id)}, {"messages": {"$slice": -1}, "title": 1, "created_at": 1, "updated_at": 1, "archived": 1, "source": 1, "n": 1, "agent_keys": 1}).sort("updated_at", -1).to_list(100)
    out = []
    for c in rows:
        p = _pub(c)
        p["message_count"] = c.get("n", p["message_count"])
        out.append(p)
    return out


async def get_thread(db, company_id: str, cid: str) -> dict | None:
    oid = cc._oid(cid)
    return await db[ai.CONVOS].find_one({"_id": oid, **core.scope(company_id)}) if oid else None


async def create_thread(db, company_id: str, me: dict, agent_key: str = ADVISOR, title: str = "", source: str = "text") -> dict:
    a = await roster.agent(db, company_id, agent_key)
    if not a or a["is_orchestrator"]:
        raise ValueError("Pick an executive to talk to")
    if not a["enabled"]:
        raise ValueError(f"{a['title']} is switched off in the roster")
    doc = {"company_id": company_id, "agent_keys": [agent_key], "title": ai.clean(title, 80) or f"With the {a['short']}", "messages": [], "n": 0, "summary": "", "summary_upto": 0, "source": source, "archived": False,
           "created_by": cc._who(me), "created_at": ai._now(), "updated_at": ai._now()}
    r = await db[ai.CONVOS].insert_one(doc)
    doc["_id"] = r.inserted_id
    return _pub(doc, full=True)


async def add_participant(db, company_id: str, convo: dict, agent_key: str) -> dict:
    a = await roster.agent(db, company_id, agent_key)
    if not a or a["is_orchestrator"] or not a["enabled"]:
        raise ValueError("That executive is not available")
    await db[ai.CONVOS].update_one({"_id": convo["_id"]}, {"$addToSet": {"agent_keys": agent_key}, "$set": {"updated_at": ai._now()}})
    return _pub(await db[ai.CONVOS].find_one({"_id": convo["_id"]}), full=True)


ASK_FORMAT_EXTRA = ('Also include "bring_in": {"agent_key": "<cto|cpo|cro|coo|cfo|strategic_advisor>", "why": "one line"} ONLY when a material part of the answer belongs to another executive, else omit it. '
                    'Cite knowledge facts as [F<n>], Command Center data as [CC], document passages as [D<n>].')


async def turn(db, me: dict, convo: dict, text: str, voice: bool = False, agent_key: str | None = None) -> dict:
    """One turn answered by the chosen executive. The Strategic Advisor keeps the original Founder Advisor persona plus company knowledge."""
    company_id = convo.get("company_id") or core.DEFAULT_COMPANY
    keys = convo.get("agent_keys") or [ADVISOR]
    key = agent_key if agent_key in keys else keys[0]
    a = await roster.agent(db, company_id, key)
    if not a:
        raise ValueError("Unknown executive")
    budget = await core.check_budget(db, company_id)
    comp = await context.compile(db, company_id, a, question=text)
    system = comp["system"] + "\n\n" + ASK_FORMAT_EXTRA
    if len(keys) > 1:
        others = ", ".join(k for k in keys if k != key)
        system += f"\n\nThis thread also includes: {others}. Answer only as the {a['title']}; earlier replies labelled with other roles were theirs."
    out = await ai.chat_turn(db, me, convo, text, voice=voice, system=system, agent_key=key, tags={"company_id": company_id, "agent_key": key, "thread_id": str(convo["_id"])})
    out["conversation"] = _pub(await db[ai.CONVOS].find_one({"_id": convo["_id"]}), full=True)
    out["agent_key"] = key
    out["readiness"] = {"score": comp["readiness"]["score"], "level": comp["readiness"]["level"]}
    out["budget"] = budget
    return out


STARTERS = {
    "cto": ["What would it take to let a dealership set up Mystery Shops itself?", "Where is our biggest technical risk right now?", "What should we never build ourselves?"],
    "cpo": ["How should we package the three products for an equipment dealer?", "What is the smallest Mystery Shops offer that proves value?", "Which planned features should we cut?"],
    "cro": ["Who is the first buyer for Mystery Shops and what do we charge?", "How should a partner model with TracTru work?", "What is the fastest experiment to validate pricing?"],
    "coo": ["What has to be ready before our first paying dealership?", "How do we onboard a dealership without me doing it by hand?", "Where will support break first?"],
    "cfo": ["What does one phone mystery shop cost us to deliver?", "What price floor keeps a healthy margin on shops?", "What should our monthly AI budget be?"],
}


def starters(agent_key: str, ctx: dict) -> list:
    """Role-shaped starter questions; the Advisor keeps its data-shaped list."""
    return STARTERS.get(agent_key) or ai.suggested_questions(ctx)
