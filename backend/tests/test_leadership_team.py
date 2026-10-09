"""AI Leadership Team Phase 1, in-process against a throwaway database with a scripted model.
Covers: the roundtable state machine end to end, independence of assessments, the code-built dissent register, partial failure + resume,
modify -> one re-synthesis -> approve, budget / emergency stop, company isolation, Ask an Executive turns, unsupported-claim detection and truncated-JSON repair.
Run alone (one asyncio loop for Motor): cd /app/backend && set -a && . ./.env && set +a && python -m pytest tests/test_leadership_team.py -q"""
import asyncio
import json
import os
import sys

import pytest
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, "/app/backend")
load_dotenv("/app/backend/.env")
from services import command_center as cc  # noqa: E402
from services import command_center_ai as ai  # noqa: E402
from services.leadership import ask, core, knowledge, roster  # noqa: E402
from services.leadership import orchestrator as rt  # noqa: E402

ME = {"_id": "000000000000000000000001", "name": "Test Founder", "first_name": "Test", "role": "super_admin", "is_owner": True}
TEST_DB = os.environ["DB_NAME"] + "_lt_test"
CO = core.DEFAULT_COMPANY
LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(LOOP)


def run(coro):
    return LOOP.run_until_complete(coro)


@pytest.fixture()
def db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"], io_loop=LOOP)
    d = client[TEST_DB]
    run(client.drop_database(TEST_DB))
    run(cc.seed(d, ME))
    run(roster.seed_templates(d))
    run(knowledge.seed(d, CO))
    yield d
    run(client.drop_database(TEST_DB))


def _role(system: str) -> str:
    for key, title in (("cto", "Title: Chief Technology Officer"), ("cfo", "Title: Chief Financial Officer"), ("cro", "Title: Chief Revenue Officer"), ("cpo", "Title: Chief Product Officer"), ("coo", "Title: Chief Operating Officer"), ("strategic_advisor", "Title: Strategic Advisor"), ("chief_of_staff", "Title: Chief of Staff")):
        if title in system:
            return key
    return "?"


class Scripted:
    """Stands in for ai.complete. Answers by call kind and role; `fail` names roles that must fail (once each unless `always`)."""
    def __init__(self, select=("cto", "cfo"), fail=(), always=False, challenge_material=(("cto", "cfo"),), on_assess=None):
        self.select, self.fail, self.always, self.material, self.on_assess = list(select), set(fail), always, list(challenge_material), on_assess
        self.calls = []

    async def __call__(self, db, kind, system, messages, json_mode=False, max_tokens=None, tags=None, timeout=None):
        role = _role(system)
        self.calls.append({"kind": kind, "role": role, "system": system, "user": messages[-1]["content"], "tags": tags})
        usage = {"prompt_tokens": 1000, "completion_tokens": 200}
        if role in self.fail and kind in ("lt_assess", "lt_challenge"):
            if not self.always:
                self.fail.discard(role)
            await ai._record(db, kind, False, 5, error="scripted failure", tags=tags)
            raise ai.AdvisorUnavailable("scripted failure")
        await ai._record(db, kind, True, 5, usage, tags=tags)
        if kind == "lt_select":
            out = {"restated": "Decide X", "participants": [{"key": k, "why": f"{k} matters"} for k in self.select], "devil_advocate": self.select[0], "clarifying_question": ""}
        elif kind == "lt_assess":
            if self.on_assess:
                await self.on_assess(db)
            out = {"perspective": f"FACT: the stack is FastAPI [F1]. From the {role} view this is feasible. FACT: we have ten customers.", "recommendation": f"{role}: do it in phases", "evidence": ["FACT: deployed [CC]"], "assumptions": ["price unknown"],
                   "risks": ["scope creep"], "dependencies": ["pricing decision"], "questions_for": [{"to": "cfo", "question": "margin?"}], "confidence": "medium", "limitations": ["no actuals"]}
        elif kind == "lt_challenge":
            assert "peer_assessments" in messages[-1]["content"], "challenge round must see the peers"
            ch = [{"to": to, "claim": f"{to}: do it in phases", "objection": "phases hide the real cost", "evidence": "none on record", "severity": "material", "consequence": "we underprice"} for frm, to in self.material if frm == role]
            ch += [{"to": "strategic_advisor", "claim": "minor point", "objection": "wording", "evidence": "", "severity": "minor", "consequence": ""}] if role != "strategic_advisor" else []
            out = {"challenges": ch, "agreements": [{"with": "cto", "on": "phasing"}], "position_change": "none", "unsupported_assumptions": [], "missing_dependencies": ["legal review"]}
        elif kind == "lt_synth":
            note = "WITH CHANGES" if "founder_requested_changes" in messages[-1]["content"] else "FIRST"
            out = {"title": f"Brief {note}", "opportunity": "opp", "alignment": "aligned", "department_recommendations": [{"key": "strategic_advisor", "summary": "careful"}, {"key": "cto", "summary": "phases"}], "agreements": ["phasing"],
                   "disagreements": "cost visibility", "technical": "t", "financial": "f", "operational": "o", "commercial": "c", "dependencies": ["pricing"], "risks": ["underpricing"], "missing": ["actuals"], "recommended_decision": "Validate first",
                   "next_actions": [{"action": "price it", "owner_key": "cfo", "why": "margin"}, {"action": "bogus owner", "owner_key": "ceo", "why": ""}], "decisions_required": [{"title": "Go or no go", "detail": "two options"}], "dissent_resolutions": [{"id": "d1", "resolved": False, "how": "needs the founder"}]}
        elif kind == "lt_review":
            out = {"headline": "steady", "one_big_thing": "x", "priorities": [], "roadmap": "r", "pending_decisions": [], "wins": [], "risks": [], "missing_knowledge": [], "next_actions": []}
        else:
            out = {"reply": f"FACT: stack is FastAPI [F1]. RECOMMENDATION: ask finance. (answered as {role})", "suggestions": [], "question": "", "bring_in": {"agent_key": "cfo", "why": "pricing is finance"}}
        return json.dumps(out), {**usage, "ms": 5, "approx_cost_usd": 0.001, "model": "fake"}


async def _convene_and_run(db, model, question="Should we do X?"):
    r = await rt.create(db, CO, ME, question)
    doc = await rt.get(db, CO, r["id"])
    await rt.start(db, CO, doc, ME)
    await rt._tasks[r["id"]]
    return await rt.get(db, CO, r["id"])


async def _cc_fingerprint(db):
    out = {}
    for c in (cc.BLUEPRINT, cc.PRIORITIES, cc.ROADMAP, cc.IDEAS, cc.NOTES):
        out[c] = [{k: v for k, v in d.items() if k != "_id"} for d in await db[c].find({}).sort("_id", 1).to_list(500)]
    return json.dumps(out, default=str, sort_keys=True)


def test_full_roundtable_builds_dissent_and_opens_a_decision(db, monkeypatch):
    model = Scripted(select=("cto", "cfo"))
    monkeypatch.setattr(ai, "complete", model)
    before = run(_cc_fingerprint(db))
    r = run(_convene_and_run(db, model))
    assert r["status"] == "awaiting_decision" and r["step"] == "done"
    keys = [p["key"] for p in r["participants"]]
    assert keys[0] == "strategic_advisor" and set(keys) == {"strategic_advisor", "cto", "cfo"}
    devils = [p["key"] for p in r["participants"] if p["devil_advocate"]]
    assert devils == ["cto"], "the Chief of Staff's suggestion is honoured and never the Advisor"
    assert all(r["steps"][s]["status"] == "done" for s in rt.STEPS)
    # independence: no assessment prompt ever saw a peer; every challenge prompt did; the devil's advocate got the duty text
    assess = [c for c in model.calls if c["kind"] == "lt_assess"]
    assert len(assess) == 3 and not any("peer_assessments" in c["user"] for c in assess)
    chal = [c for c in model.calls if c["kind"] == "lt_challenge"]
    assert len(chal) == 3 and all("peer_assessments" in c["user"] for c in chal)
    assert [c["role"] for c in chal if "DEVIL'S ADVOCATE DUTY" in c["system"]] == ["cto"]
    # the dissent register comes from the challenge data: one material cto -> cfo challenge, minor ones ignored, synthesis marked it unresolved
    assert len(r["dissent"]) == 1
    d = r["dissent"][0]
    assert d["executives"] == ["cto", "cfo"] and d["resolved"] is False and d["needs_founder"] is True and d["raised_by_devil_advocate"] is True and d["how"] == "needs the founder"
    # unsupported FACT claims (no [F..]/[CC]) are flagged per executive
    assert any(u["claim"].startswith("FACT: we have ten customers") for u in r["unsupported"]) and {u["agent_key"] for u in r["unsupported"]} == set(keys)
    # brief shaped, bogus owner falls back to the founder, Advisor's view present
    b = r["brief"]
    assert b["title"] == "Brief FIRST" and b["recommended_decision"] == "Validate first" and b["next_actions"][1]["owner_key"] == "founder" and b["unassessed"] == []
    # one pending decision record, cost measured from the fake usage (7 calls: 1 select + 3 + 3; synth adds 1 = 8 at 0.001)
    dec = run(db[rt.DECISIONS].find_one({"roundtable_id": str(r["_id"])}))
    assert dec and dec["status"] == "pending" and dec["recommendation"] == "Validate first"
    assert abs(r["cost_usd"] - 0.008) < 1e-6
    rows = run(db[ai.USAGE].find({"roundtable_id": str(r["_id"])}).to_list(50))
    assert len(rows) == 7 and all(x["company_id"] == CO for x in rows) and {x["kind"] for x in rows} == {"lt_assess", "lt_challenge", "lt_synth"}
    # nothing in the Command Center moved
    assert run(_cc_fingerprint(db)) == before
    # the roundtable list and the decision list read back
    lst = run(rt.list_roundtables(db, CO))
    assert lst[0]["dissent_count"] == 1 and lst[0]["status"] == "awaiting_decision"
    assert run(rt.decisions(db, CO, "pending"))[0]["title"] == "Brief FIRST"


def test_one_executive_failing_is_reported_not_hidden(db, monkeypatch):
    model = Scripted(select=("cto", "cfo"), fail=("cfo",), always=True)
    monkeypatch.setattr(ai, "complete", model)
    r = run(_convene_and_run(db, model))
    assert r["status"] == "awaiting_decision"
    assert r["assessments"]["cfo"]["status"] == "failed" and r["assessments"]["cto"]["status"] == "ok"
    assert "cfo" not in r["challenges"], "a participant with no assessment is not asked to challenge"
    assert r["brief"]["unassessed"] and r["brief"]["unassessed"][0].startswith("cfo did not answer")
    synth = [c for c in model.calls if c["kind"] == "lt_synth"][0]
    assert "unassessed_departments" in synth["user"]
    assert r["dissent"] == [], "a challenge aimed at an executive who never assessed cannot land in the register"


def test_failed_run_resumes_from_the_same_step_without_repeating_finished_calls(db, monkeypatch):
    model = Scripted(select=("cto", "cfo"), fail=("cto", "cfo"), always=True)
    monkeypatch.setattr(ai, "complete", model)
    r = run(_convene_and_run(db, model))
    assert r["status"] == "failed" and r["step"] == "assessing" and "Only 1 executive" in r["error"]
    assert r["assessments"]["strategic_advisor"]["status"] == "ok"
    n_before = len(model.calls)
    model.fail = set()
    run(rt.resume(db, CO, r, ME))
    run(rt._tasks[str(r["_id"])])
    r2 = run(rt.get(db, CO, str(r["_id"])))
    assert r2["status"] == "awaiting_decision"
    reran = [c["role"] for c in model.calls[n_before:] if c["kind"] == "lt_assess"]
    assert sorted(reran) == ["cfo", "cto"], "the Advisor's finished assessment was kept"
    audit = [a["action"] for a in run(core.audit_list(db, CO))]
    assert "roundtable_resumed" in audit and "roundtable_started" in audit and "roundtable_created" in audit
    with pytest.raises(ValueError):
        run(rt.resume(db, CO, r2, ME))


def test_modify_resynthesizes_once_then_the_founder_decides(db, monkeypatch):
    model = Scripted()
    monkeypatch.setattr(ai, "complete", model)
    r = run(_convene_and_run(db, model))
    did = r["decision_id"]
    with pytest.raises(ValueError):
        run(rt.decide(db, CO, did, ME, "modify", ""))
    d = run(rt.decide(db, CO, did, ME, "modify", "Add the partner angle"))
    assert d["status"] == "modify_requested"
    run(rt._tasks[str(r["_id"])])
    r2 = run(rt.get(db, CO, str(r["_id"])))
    assert r2["status"] == "awaiting_decision" and r2["modify_count"] == 1 and r2["brief"]["title"] == "Brief WITH CHANGES"
    synth_calls = [c for c in model.calls if c["kind"] == "lt_synth"]
    assert len(synth_calls) == 2 and "Add the partner angle" in synth_calls[-1]["user"]
    assert len([c for c in model.calls if c["kind"] == "lt_assess"]) == 3, "modify never re-runs the assessments"
    d2 = run(rt.decisions(db, CO))[0]
    assert d2["status"] == "pending" and any("re-synthesized" in h["event"] for h in d2["history"])
    with pytest.raises(ValueError, match="already re-synthesized"):
        run(rt.decide(db, CO, did, ME, "modify", "again"))
    d3 = run(rt.decide(db, CO, did, ME, "defer", "later"))
    assert d3["status"] == "deferred"
    d4 = run(rt.decide(db, CO, did, ME, "approve", "go"))
    assert d4["status"] == "approved" and d4["founder"]["action"] == "approve"
    assert run(rt.get(db, CO, str(r["_id"])))["status"] == "decided"
    with pytest.raises(ValueError, match="already been made"):
        run(rt.decide(db, CO, did, ME, "reject", ""))
    acts = [a["action"] for a in run(core.audit_list(db, CO))]
    assert acts[:3] == ["decision_approve", "decision_defer", "decision_modify"]


def test_budget_and_emergency_stop_refuse_new_work_and_pause_a_run(db, monkeypatch):
    model = Scripted()
    monkeypatch.setattr(ai, "complete", model)
    run(core.update_controls(db, CO, {"soft_usd": 0.0, "hard_usd": 0.0}, ME))
    with pytest.raises(ValueError):
        run(core.update_controls(db, CO, {"soft_usd": 5.0, "hard_usd": 1.0}, ME))
    # hard limit 0 with no spend yet: spent (0) >= hard (0) refuses
    with pytest.raises(ai.AdvisorBusy, match="hard limit"):
        run(rt.create(db, CO, ME, "anything"))
    run(core.update_controls(db, CO, {"soft_usd": 25.0, "hard_usd": 50.0, "stopped": True}, ME))
    with pytest.raises(ai.AdvisorBusy, match="Emergency stop"):
        run(rt.create(db, CO, ME, "anything"))
    run(core.update_controls(db, CO, {"stopped": False}, ME))

    async def stop_mid_run(d):
        await d[core.COMPANIES].update_one({"_id": CO}, {"$set": {"controls.stopped": True}})
    model.on_assess = stop_mid_run
    r = run(_convene_and_run(db, model))
    assert r["status"] == "paused" and r["error"] == "Emergency stop" and r["steps"]["assessing"]["status"] == "done" and "challenging" not in r["steps"]
    assert all(v["status"] == "ok" for v in r["assessments"].values()), "the step in flight finished; the next one never started"
    run(core.update_controls(db, CO, {"stopped": False}, ME))
    model.on_assess = None
    run(rt.resume(db, CO, r, ME))
    run(rt._tasks[str(r["_id"])])
    assert run(rt.get(db, CO, str(r["_id"])))["status"] == "awaiting_decision"
    u = run(core.usage(db, CO))
    assert u["last_24h"]["requests"] >= 7 and u["month_spend_usd"] > 0 and "lt_assess" in u["last_24h"]["by_kind"]


def test_company_isolation_on_every_leadership_record(db, monkeypatch):
    model = Scripted()
    monkeypatch.setattr(ai, "complete", model)
    r = run(_convene_and_run(db, model))
    rid = str(r["_id"])
    assert run(rt.get(db, "other_co", rid)) is None and run(rt.get(db, CO, rid)) is not None
    assert run(rt.list_roundtables(db, "other_co")) == [] and run(rt.decisions(db, "other_co")) == []
    with pytest.raises(ValueError, match="not found"):
        run(rt.decide(db, "other_co", r["decision_id"], ME, "approve", ""))
    t = run(ask.create_thread(db, CO, ME, "cto"))
    assert run(ask.get_thread(db, "other_co", t["id"])) is None and run(ask.get_thread(db, CO, t["id"])) is not None
    assert run(ask.list_threads(db, "other_co")) == []
    assert run(knowledge.list_facts(db, "other_co")) == [] and len(run(knowledge.list_facts(db, CO))) == len(knowledge.IMOS_SEED)
    assert run(core.audit_list(db, "other_co")) == [] and run(core.audit_list(db, CO))
    assert run(core.month_spend(db, "other_co")) == 0.0 and run(core.month_spend(db, CO)) > 0
    # legacy Advisor conversations (no company_id) belong to the default company and nobody else
    run(db[ai.CONVOS].insert_one({"title": "old advisor thread", "messages": [], "n": 0, "archived": False, "created_at": ai._now(), "updated_at": ai._now()}))
    assert any(x["title"] == "old advisor thread" and x["agent_keys"] == ["strategic_advisor"] for x in run(ask.list_threads(db, CO)))
    assert run(ask.list_threads(db, "other_co")) == []


def test_ask_an_executive_answers_in_role_and_records_usage(db, monkeypatch):
    model = Scripted()
    monkeypatch.setattr(ai, "complete", model)
    with pytest.raises(ValueError):
        run(ask.create_thread(db, CO, ME, "chief_of_staff"))
    run(roster.update_agent(db, CO, "coo", {"enabled": False}))
    with pytest.raises(ValueError, match="switched off"):
        run(ask.create_thread(db, CO, ME, "coo"))
    t = run(ask.create_thread(db, CO, ME, "cfo"))
    convo = run(ask.get_thread(db, CO, t["id"]))
    out = run(ask.turn(db, ME, convo, "What does a shop cost?"))
    assert out["agent_key"] == "cfo" and "answered as cfo" in out["reply"]
    call = model.calls[-1]
    assert call["kind"] == "lt_chat" and call["role"] == "cfo" and "company_knowledge" in call["system"] and "COMMAND CENTER" in call["system"] and "KNOWLEDGE LIMITS FOR YOUR ROLE" in call["system"]
    assert call["tags"] == {"company_id": CO, "agent_key": "cfo", "thread_id": t["id"]}
    msg = out["conversation"]["messages"][-1]
    assert msg["agent_key"] == "cfo" and msg["bring_in"] == {"agent_key": "cfo", "why": "pricing is finance"}
    assert out["readiness"]["level"] in ("low", "partial", "ready") and out["budget"]["hard"] == 50.0
    # bring the CTO in; the next turn can be answered by the CTO, earlier replies stay labelled
    run(ask.add_participant(db, CO, convo, "cto"))
    convo = run(ask.get_thread(db, CO, t["id"]))
    out2 = run(ask.turn(db, ME, convo, "And technically?", agent_key="cto"))
    assert out2["agent_key"] == "cto" and model.calls[-1]["role"] == "cto" and "This thread also includes: cfo" in model.calls[-1]["system"]
    assert [m.get("agent_key") for m in out2["conversation"]["messages"] if m["role"] != "founder"] == ["cfo", "cto"]
    rows = run(db[ai.USAGE].find({"kind": "lt_chat"}).to_list(10))
    assert len(rows) == 2 and all(x["company_id"] == CO for x in rows) and rows[0]["approx_cost_usd"] > 0
    # the advisor's own hourly limit ignores leadership calls
    assert run(ai.check_rate(db)) is None
    # readiness is rule based and moves when a fact is verified
    cfo = run(roster.agent(db, CO, "cfo"))
    before = run(knowledge.readiness(db, CO, cfo))["score"]
    f = next(x for x in run(knowledge.list_facts(db, CO)) if x["key"] == "commercial.pricing")
    run(knowledge.set_status(db, CO, f["id"], "verified", ME))
    assert run(knowledge.readiness(db, CO, cfo))["score"] > before


def test_unsupported_claims_json_repair_and_reaper(db):
    flagged = rt._unsupported("cto", {"perspective": "FACT: deployed [CC]. FACT: we have ten customers. ASSUMPTION: price.", "evidence": ["FACT: stack [F2]", "FACT: nothing cited"]})
    assert [f["claim"] for f in flagged] == ["FACT: we have ten customers.", "FACT: nothing cited"]
    cut = '{"challenges": [{"to": "cro", "claim": "x", "objection": "why", "severity": "material"}, {"to": "cpo", "claim": "trunc'
    d = ai._json(cut)
    assert d["_truncated"] is True and d["challenges"][0]["severity"] == "material"
    assert ai._json("not json at all") == {} and ai._json('```json\n{"a": 1}\n```') == {"a": 1}
    # the reaper: a running run with a stale heartbeat (or any running run at startup) becomes resumable
    run(db[rt.RT].insert_many([{"company_id": CO, "status": "running", "step": "assessing", "heartbeat_at": ai._now() - __import__("datetime").timedelta(seconds=rt.STALE_S + 5), "question": "a", "participants": []},
                                {"company_id": CO, "status": "running", "step": "challenging", "heartbeat_at": ai._now(), "question": "b", "participants": []}]))
    assert run(rt.fail_interrupted(db)) == 1
    assert run(rt.fail_interrupted(db, all_running=True)) == 1
    assert run(db[rt.RT].count_documents({"status": "interrupted"})) == 2


def test_memory_lane_export_and_morning_brief(db, monkeypatch):
    """Phase 1 follow-ups: Executive Memory Lane (code-built history), roundtable export (markdown + pdf) and the morning brief push (tick sends once per local day)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from bson import ObjectId

    import routers.push_notifications as pn
    from services.leadership import export, history, morning

    model = Scripted(select=("cto", "cfo"))
    monkeypatch.setattr(ai, "complete", model)
    before = run(_cc_fingerprint(db))
    r = run(_convene_and_run(db, model))
    dec = run(db[rt.DECISIONS].find_one({"roundtable_id": str(r["_id"])}))
    run(rt.decide(db, CO, str(dec["_id"]), ME, "approve", "go"))
    # memory lane: the cto (devil's advocate) raised the one material challenge against the cfo; the founder approved
    counts = run(history.counts(db, CO))
    assert counts["cto"] == {**counts["cto"], "roundtables": 1, "approved": 1, "dissents": 1, "open_dissents": 1, "devil_advocate": 1}
    assert "chief_of_staff" not in counts
    cfo = run(history.memory(db, CO, "cfo"))
    assert cfo["summary"]["roundtables"] == 1 and len(cfo["entries"]) == 1
    e = cfo["entries"][0]
    assert e["position"] == "cfo: do it in phases" and e["confidence"] == "medium" and e["decision"]["status"] == "approved" and e["decision"]["reason"] == "go"
    assert e["dissents"][0]["raised"] is False and e["challenged_on"] == 1 and e["challenges_raised"] == 0 and e["position_change"] == ""
    cto = run(history.memory(db, CO, "cto"))["entries"][0]
    assert cto["challenges_raised"] == 1 and cto["dissents"][0]["raised"] is True and cto["devil_advocate"] is True and cto["brief_recommendation"] == "Validate first"
    assert run(history.memory(db, CO, "coo")) == {"executive": "coo", "summary": history._zero(), "entries": []}
    # export: every section, the founder's verdict, the dissent register; the pdf renders from the same markdown
    fresh = run(rt.get(db, CO, str(r["_id"])))
    dec = run(db[rt.DECISIONS].find_one({"_id": dec["_id"]}))
    md = export.markdown(fresh, dec, "Test Co")
    for h in ("## The question", "## Decision", "## The room", "## Executive brief", "## Dissent register", "## Independent assessments", "## Challenge round", "## Claims labelled FACT without a citation", "## Record"):
        assert h in md, h
    assert "**Approved** by Test Founder" in md and "Founder's note: go" in md and "### D1: cfo: do it in phases" in md and "Test Co" in md and "devil's advocate" in md
    pdf = export.pdf(md)
    assert pdf[:5] == b"%PDF-" and len(pdf) > 2000
    assert export.filename(fresh, "pdf").startswith("roundtable-brief-first-")
    # morning brief: validation, settings, and the hourly tick that sends once per local day through the push helper
    pushes = []

    async def fake_push(uid, title, body, url="/", icon="flame", **kw):
        pushes.append({"uid": uid, "title": title, "body": body, "url": url})
        return 1
    monkeypatch.setattr(pn, "send_push_to_user", fake_push)
    with pytest.raises(ValueError):
        run(morning.update(db, CO, ME, {"hour": 25}))
    with pytest.raises(ValueError):
        run(morning.update(db, CO, ME, {"timezone": "Mars/Olympus"}))
    s = run(morning.update(db, CO, ME, {"enabled": True, "hour": 7, "timezone": "America/Denver"}))
    assert s["enabled"] is True and s["user_id"] == ME["_id"] and s["timezone"] == "America/Denver" and s["next_send"].endswith("07:05:00-06:00") or s["next_send"].endswith("07:05:00-07:00")
    now_h = datetime.now(ZoneInfo("America/Denver")).hour
    run(morning.update(db, CO, ME, {"hour": (now_h + 1) % 24}))
    out = run(morning.tick(db))
    assert out["checked"] == 1 and out["sent"] == 0 and "brief is at" in out["skipped"][0] and pushes == []
    run(morning.update(db, CO, ME, {"hour": now_h}))
    run(db.users.insert_one({"_id": ObjectId(ME["_id"]), "name": "Test Founder", "role": "super_admin"}))
    out = run(morning.tick(db))
    assert out["sent"] == 1 and len(pushes) == 1 and pushes[0] == {"uid": ME["_id"], "title": morning.TITLE, "body": "steady. One Big Thing: x.", "url": morning.LINK}
    s = run(morning.settings(db, CO))
    assert s["last_sent_day"] == datetime.now(ZoneInfo("America/Denver")).strftime("%Y-%m-%d") and s["last_pushed"] == 1 and s["last_headline"] == "steady" and s["last_error"] is None
    out = run(morning.tick(db))
    assert out["sent"] == 0 and "already sent today" in out["skipped"][0] and len(pushes) == 1
    assert run(db[rt.REVIEWS].count_documents({"source": "morning_brief:scheduled", "pushed": 1})) == 1
    assert morning.compose({"headline": "Steady [F1][CC]", "one_big_thing": "Launch [F2]", "pending_decisions": ["a", "b"], "next_actions": [{"action": "Price it [D1]"}]}) == "Steady. One Big Thing: Launch. 2 decisions waiting on you. First move: Price it."
    acts = [a["action"] for a in run(core.audit_list(db, CO))]
    assert "morning_brief_sent" in acts and "morning_brief_updated" in acts
    assert run(_cc_fingerprint(db)) == before, "the morning brief and the export never touch the Command Center"
