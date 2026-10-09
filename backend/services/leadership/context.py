"""Shared context compiler: the live Command Center (unchanged) + the executive's knowledge scope + Company Docs passages + organizational memory."""
from services import command_center as cc
from services import command_center_ai as ai
from services.leadership import knowledge, roster

DECISIONS, ROUNDTABLES = "lt_decisions", "lt_roundtables"


async def memory_block(db, company_id: str, limit: int = 5) -> str:
    """What the leadership team already decided or discussed: recent decisions with the founder's verdict, so executives do not re-litigate settled questions."""
    rows = await db[DECISIONS].find({"company_id": company_id}).sort("created_at", -1).to_list(limit)
    lines = [f"- {cc._iso(d.get('created_at'))[:10]} · {ai.clean(d.get('title'), 160)} · recommendation: {ai.clean(d.get('recommendation'), 200)} · founder: {d.get('status')}" + (f" ({ai.clean((d.get('founder') or {}).get('reason'), 160)})" if (d.get('founder') or {}).get('reason') else "") for d in rows]
    return ai._block("leadership_decisions_so_far", lines) if lines else ""


async def compile(db, company_id: str, agent: dict, question: str = "", include_docs: bool = True) -> dict:
    """Everything one executive sees besides the conversation: role prompt, Command Center, scoped knowledge, documents, memory, readiness limits."""
    ctx = await ai.assemble_context(db)
    kb, findex = await knowledge.block(db, company_id, agent["knowledge_domains"], "exec")
    docs, dindex = (await knowledge.doc_passages(db, question)) if include_docs and question else ("", {})
    mem = await memory_block(db, company_id)
    ready = await knowledge.readiness(db, company_id, agent)
    limits = ""
    if ready["missing"]:
        limits = "KNOWLEDGE LIMITS FOR YOUR ROLE: the company has not recorded " + "; ".join(m["label"].lower() for m in ready["missing"][:6]) + ". Say so where it matters and do not fill the gaps with guesses."
    system = roster.role_prompt(agent) + "\n\nCOMMAND CENTER (live, authoritative):\n" + ctx["text"] + "\n\n" + kb + ("\n\n" + docs if docs else "") + ("\n\n" + mem if mem else "") + ("\n\n" + limits if limits else "")
    return {"system": system, "facts": ctx["facts"], "fact_index": findex, "doc_index": dindex, "readiness": ready, "counts": ctx["counts"]}
