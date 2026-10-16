"""Jessi's automatic reply drafts follow the same-org rule (Oct 2026 hotfix): a teammate the thread is assigned to, or an unclaimed shared
inbox, never gets a draft built from the owner's private notes / memos / intelligence (the draft and its "why this reply" are shown to them).
The owner still does. In-process, fake LLM (zero spend), draft_only mode (nothing is sent). Reuses the same-org demo from
tests/test_same_org_rep_isolation.py and leaves it in place (collaborator scenario), like tests/test_t1_claim_hijack_406.py.
Run: cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && python -m pytest tests/test_ai_reply_private_context.py -q"""
import emergentintegrations.llm.chat as llm_chat
import pytest

import routers.ai_campaigns as ai_campaigns
from routers.ai_reply import queue_ai_reply
from routers.database import get_db
from tests import test_same_org_rep_isolation as t

PROMPTS: list = []


class FakeChat:
    def __init__(self, *a, **k):
        pass

    def with_model(self, *a):
        return self

    async def send_message(self, msg):
        PROMPTS.append(msg.text)
        return "Yes, it's still here. Want to come see it?"


async def fake_brief(user_id, contact_id, **kw):
    return {"ai_context": f"Notes: rides {t.SECRET}s, met at {t.EVENT}", "intel_rationale": f"He rides {t.SECRET}s"}


@pytest.fixture(scope="module", autouse=True)
def demo():
    t.run(t._wipe_leftovers())
    t.run(t._seed())
    yield
    t.run(get_db().ai_reply_queue.delete_many({"contact_id": t.S["ca"]}))
    t.scenario("collaborator")


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    monkeypatch.setattr(llm_chat, "LlmChat", FakeChat)
    monkeypatch.setattr(ai_campaigns, "get_contact_brief", fake_brief)
    PROMPTS.clear()


def _draft(scenario, assignee):
    t.scenario(scenario)
    doc = t.run(queue_ai_reply(contact_id=t.S["ca"], conversation_id=t.S["conv"], enrollment_id="conversation_direct", campaign_id="",
                               assigned_user_id=assignee, incoming_message="Thanks again for your help yesterday", ai_assist_mode="draft_only"))
    row = t.run(get_db().ai_reply_queue.find_one({"conversation_id": t.S["conv"]}, sort=[("_id", -1)])) or {}
    return doc, row


def test_owner_draft_uses_private_context():
    doc, row = _draft("none", t.S["uid"]["A"])
    assert PROMPTS and t.SECRET in PROMPTS[-1], "the owner's own draft should still know the relationship"
    assert row.get("intel_rationale") and t.SECRET in row["intel_rationale"]


@pytest.mark.parametrize("scenario,who", [("assigned", "A2"), ("inbox_unclaimed", None)])
def test_teammate_or_inbox_draft_never_reads_owner_private_data(scenario, who):
    doc, row = _draft(scenario, t.S["uid"][who] if who else None)
    assert PROMPTS, "a draft was generated"
    assert not any(t.SECRET in p or t.EVENT in p for p in PROMPTS), PROMPTS[-1][:400]
    assert not t.leaked(row.get("intel_rationale") or ""), row.get("intel_rationale")


def test_manager_draft_keeps_context():
    doc, row = _draft("assigned", t.S["uid"]["M"])
    assert PROMPTS and t.SECRET in PROMPTS[-1], "the owner's manager keeps access"
