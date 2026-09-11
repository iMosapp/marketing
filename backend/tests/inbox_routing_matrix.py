"""Shared inbox routing matrix - exercises the Twilio webhook, lead intake, ownership actions and graduation
against throwaway store/users/inbox. No real SMS, LLM or push: all stubbed. Cleans up after itself.

Usage:  cd /app/backend && python tests/inbox_routing_matrix.py
"""
import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from bson import ObjectId

SMS, PUSHES = [], []
TAG = f"qa-inbox-{ObjectId()}"


class _FakeChat:
    def __init__(self, *a, **k): pass
    def with_model(self, *a, **k): return self
    async def send_message(self, *a, **k): return "Happy to help, what can I do for you?"


async def _fake_send_sms(to_phone, message, media_urls=None, from_phone=None, **k):
    SMS.append({"to": to_phone, "from": from_phone, "body": message})
    return {"success": True, "message_sid": f"SM{ObjectId()}", "mock": True}


async def _fake_push(user_id, title, body, link=None, icon=None, *a, **k):
    PUSHES.append({"user_id": str(user_id), "title": title, "body": body})
    return {"sent": 0}


async def main():
    import routers.database as rdb
    db = rdb.get_db()
    import emergentintegrations.llm.chat as llm
    llm.LlmChat = _FakeChat
    import routers.push_notifications as pn
    pn.send_push_to_user = _fake_push
    import services.twilio_service as ts
    ts.send_sms = _fake_send_sms
    import routers.twilio_webhooks as wh
    import routers.messages as msgs
    import routers.lead_intake as li
    from services import inboxes as ib
    from services.tag_workflows import apply_tag_workflows
    from models import MessageCreate

    now = datetime.utcnow()
    store_id = (await db.stores.insert_one({"name": "QA Inbox Store", "timezone": "America/Denver", "qa_tag": TAG, "created_at": now})).inserted_id
    sid = str(store_id)

    async def mk_user(name, number=None, role="user"):
        doc = {"name": name, "email": f"{name.lower().replace(' ', '')}-{TAG}@test.local", "role": role, "status": "active",
               "store_id": sid, "qa_tag": TAG, "created_at": now}
        if number:
            doc["twilio_number"] = number
        return str((await db.users.insert_one(doc)).inserted_id)

    A = await mk_user("Alice Rep", "+15005550101")
    B = await mk_user("Bob Rep")                       # no personal number
    C = await mk_user("Carl Rep", "+15005550102")      # not on the inbox
    M = await mk_user("Mia Manager", None, role="store_manager")
    users = {A: "Alice", B: "Bob", C: "Carl", M: "Mia"}
    SALES_NUM, SERVICE_NUM = "+15005550100", "+15005550110"
    sales_id = (await db.shared_inboxes.insert_one({
        "name": "Sales", "phone_number": SALES_NUM, "assigned_user_ids": [A, B], "store_id": sid, "routing": "jump_ball",
        "first_reply": "Thanks for texting {{lead_source}}, {{first_name}}! Someone will be right with you.",
        "ai_mode": "auto_reply", "after_close": "move_to_rep", "close_tag": "Sold", "is_active": True, "qa_tag": TAG, "created_at": now})).inserted_id
    service_id = (await db.shared_inboxes.insert_one({
        "name": "Service", "phone_number": SERVICE_NUM, "assigned_user_ids": [A, B], "store_id": sid, "routing": "round_robin",
        "first_reply": "", "ai_mode": "auto_reply", "after_close": "stay", "close_tag": "Sold", "is_active": True, "qa_tag": TAG, "created_at": now})).inserted_id
    sales_inbox = await db.shared_inboxes.find_one({"_id": sales_id})
    service_inbox = await db.shared_inboxes.find_one({"_id": service_id})
    # Carl's existing customer (texts Sales later; must stay on Carl's line)
    carl_contact = (await db.contacts.insert_one({"user_id": C, "store_id": sid, "first_name": "Kim", "last_name": "Known", "name": "Kim Known",
                                                  "phone": "+15005550012", "status": "active", "tags": [], "qa_tag": TAG, "created_at": now})).inserted_id
    carl_conv = (await db.conversations.insert_one({"user_id": C, "rep_phone": "+15005550102", "contact_id": str(carl_contact), "contact_phone": "+15005550012",
                                                    "contact_name": "Kim Known", "status": "active", "ai_mode": "off", "qa_tag": TAG,
                                                    "created_at": now, "last_message_at": now})).inserted_id

    results = []
    ok_all = False

    def check(name, cond, detail=""):
        results.append((name, bool(cond), detail))

    async def text_in(frm, to, body):
        SMS.clear(); PUSHES.clear()
        await wh.incoming_message(None, From=frm, To=to, Body=body, MessageSid=f"SM{ObjectId()}", NumMedia="0")
        await asyncio.sleep(0.8)          # fire-and-forget tasks (intake workflow, AI queue, pushes)

    async def conv_for(phone, rep_phone=None):
        q = {"contact_phone": phone}
        if rep_phone:
            q["rep_phone"] = rep_phone
        return await db.conversations.find_one(q, sort=[("last_message_at", -1)])

    async def cancel_queue(conv_id):
        n = await db.ai_reply_queue.count_documents({"conversation_id": conv_id, "status": "pending"})
        items = await db.ai_reply_queue.find({"conversation_id": conv_id, "status": "pending"}).to_list(10)
        await db.ai_reply_queue.update_many({"conversation_id": conv_id, "status": "pending"}, {"$set": {"status": "cancelled", "cancel_reason": "qa"}})
        return n, items

    def pushed(uid):
        return [p for p in PUSHES if p["user_id"] == uid]

    try:
        ok_all = await _run(db, locals())
    finally:
        await _cleanup(db, sid, users, sales_id, service_id, now)
    return ok_all


async def _run(db, L):
    # unpack the fixtures built in main()
    ib, wh, msgs, li, apply_tag_workflows, MessageCreate = L["ib"], L["wh"], L["msgs"], L["li"], L["apply_tag_workflows"], L["MessageCreate"]
    results, check, text_in, conv_for, cancel_queue, pushed = L["results"], L["check"], L["text_in"], L["conv_for"], L["cancel_queue"], L["pushed"]
    A, B, C, M, sid, sales_id, service_id, carl_conv = L["A"], L["B"], L["C"], L["M"], L["sid"], L["sales_id"], L["service_id"], L["carl_conv"]
    SALES_NUM, SERVICE_NUM, now = L["SALES_NUM"], L["SERVICE_NUM"], L["now"]

    # ── 1. New customer texts the Sales line -> unassigned inbox thread, first reply from the inbox number, both members pushed
    CUST1 = "+15005550011"
    await text_in(CUST1, SALES_NUM, "Hi, do you have any trucks?")
    c1 = await conv_for(CUST1)
    check("1a inbox thread created on the shared number", c1 and c1.get("rep_phone") == SALES_NUM and c1.get("inbox_id") == str(sales_id), str((c1 or {}).get("rep_phone")))
    check("1b thread is unassigned (jump ball)", c1 and not c1.get("assigned_to"), str((c1 or {}).get("assigned_to")))
    ct1 = await db.contacts.find_one({"_id": ObjectId(c1["contact_id"])}) if c1 else None
    check("1c contact belongs to the store until claimed", ct1 and str(ct1.get("user_id")) == sid, str((ct1 or {}).get("user_id")))
    check("1d customer's text stored on the thread", c1 and await db.messages.count_documents({"conversation_id": str(c1["_id"]), "sender": "contact"}) == 1)
    first_reply = [s for s in SMS if s["to"] == CUST1]
    check("1e first reply sent FROM the inbox number", first_reply and first_reply[0]["from"] == SALES_NUM and "Sales" in first_reply[0]["body"], str(first_reply))
    check("1f both members pushed, non-member not", pushed(A) and pushed(B) and not pushed(C), f"A={len(pushed(A))} B={len(pushed(B))} C={len(pushed(C))}")
    lead = await db.inbound_leads.find_one({"conversation_id": str(c1["_id"])}) if c1 else None
    check("1g inbound lead logged against the inbox's direct source", lead and lead.get("source_name") == "Sales")
    await db.inbound_leads.update_many({"qa": None, "phone": {"$in": [CUST1]}}, {"$set": {"status": "skipped", "skip_reason": "qa"}})

    # ── 2. Second text while unassigned -> Inbox VA answers from the inbox number, members get "tap to claim"
    await text_in(CUST1, SALES_NUM, "Looking for something under 40k")
    n_pending, items = await cancel_queue(str(c1["_id"]))
    check("2a Inbox VA queued a reply (nobody owns it yet)", n_pending >= 1, f"pending={n_pending}")
    check("2b VA reply goes out from the inbox number", items and items[0].get("rep_twilio_number") == SALES_NUM, str([(i.get("rep_twilio_number"), i.get("assigned_user_id")) for i in items]))
    check("2c VA reply has no rep attached", items and not items[0].get("assigned_user_id"))
    check("2d members pushed 'tap to claim'", pushed(A) and pushed(B) and any("claim" in p["body"].lower() for p in pushed(A)), str(pushed(A)))
    c1 = await conv_for(CUST1)
    check("2e still one thread, two customer messages", await db.messages.count_documents({"conversation_id": str(c1["_id"]), "sender": "contact"}) == 2)

    # ── 3. Claim by Alice (member)
    alice = await db.users.find_one({"_id": ObjectId(A)})
    bob = await db.users.find_one({"_id": ObjectId(B)})
    carl = await db.users.find_one({"_id": ObjectId(C)})
    mia = await db.users.find_one({"_id": ObjectId(M)})
    PUSHES.clear()
    try:
        await ib.assign_conversation(db, c1, carl, C)
        check("3a non-member cannot claim", False)
    except PermissionError:
        check("3a non-member cannot claim", True)
    res = await ib.assign_conversation(db, c1, alice, A)
    c1 = await conv_for(CUST1)
    ct1 = await db.contacts.find_one({"_id": ObjectId(c1["contact_id"])})
    check("3b Alice owns the thread, still on the inbox number", c1.get("assigned_to") == A and c1.get("user_id") == A and c1.get("rep_phone") == SALES_NUM)
    check("3c contact moved to Alice", str(ct1.get("user_id")) == A)
    check("3d system line + history written", await db.messages.count_documents({"conversation_id": str(c1["_id"]), "sender": "system"}) >= 1 and (c1.get("assignment_history") or [])[-1]["kind"] == "claim")
    check("3e Bob told 'Alice picked up' (quiet), Alice not pushed", pushed(B) and not pushed(A), str(PUSHES))

    # ── 4. Customer replies after claim -> lands in Alice's pipeline, same thread, Jessi speaks as Alice from the inbox number
    await text_in(CUST1, SALES_NUM, "Great, when can I come look?")
    c1b = await conv_for(CUST1)
    check("4a same thread, no duplicate", str(c1b["_id"]) == str(c1["_id"]) and await db.conversations.count_documents({"contact_phone": CUST1}) == 1)
    check("4b Alice pushed about the reply", pushed(A), str(PUSHES))
    n_pending, items = await cancel_queue(str(c1["_id"]))
    check("4c AI reply queued as Alice, from the inbox number", items and items[0].get("assigned_user_id") == A and items[0].get("rep_twilio_number") == SALES_NUM,
          str([(i.get("rep_twilio_number"), i.get("assigned_user_id"), i.get("requires_approval")) for i in items]))

    # ── 5. Alice replies from the app -> SMS leaves from the inbox number
    SMS.clear()
    await msgs.send_message(A, str(c1["_id"]), MessageCreate(conversation_id=str(c1["_id"]), content="Come by anytime after 3, I'm here till 8."))
    check("5a rep reply sent from the inbox number", SMS and SMS[-1]["from"] == SALES_NUM and SMS[-1]["to"] == CUST1, str(SMS))
    try:
        await msgs.send_message(C, str(c1["_id"]), MessageCreate(conversation_id=str(c1["_id"]), content="sneaky"))
        check("5b non-member cannot send on the thread", False)
    except Exception as e:
        check("5b non-member cannot send on the thread", getattr(e, "status_code", None) in (403, 404), str(e))

    # ── 6. Collaborator: Bob shared in; owner silent 15 min -> Bob nudged once
    await ib.set_collaborator(db, c1, alice, B, True)
    await db.conversations.update_one({"_id": c1["_id"]}, {"$set": {"last_message_from": "contact", "last_message_at": datetime.utcnow() - timedelta(minutes=16),
                                                                     "rep_last_replied_at": datetime.utcnow() - timedelta(minutes=30), "last_message": "hello?"}})
    PUSHES.clear()
    r1 = await ib.escalate_silent_owners()
    r2 = await ib.escalate_silent_owners()
    check("6a collaborator nudged once when owner silent 15 min", pushed(B) and len(pushed(B)) == 1 and r2["nudged"] == 0, f"{r1} {r2} {pushed(B)}")
    await db.conversations.update_one({"_id": c1["_id"]}, {"$set": {"rep_last_replied_at": datetime.utcnow()}})
    PUSHES.clear()
    r3 = await ib.escalate_silent_owners()
    check("6b no nudge once the owner replied", not pushed(B), str(r3))
    # customer texts while owner is on shift -> collaborator NOT pushed immediately (owner is)
    await text_in(CUST1, SALES_NUM, "still there?")
    await cancel_queue(str(c1["_id"]))
    check("6c collaborator not pushed while owner is on shift", pushed(A) and not any("waiting" in p["title"].lower() for p in pushed(B)), str(pushed(B)))

    # ── 7. Sold -> graduates to Alice's own number + bridge text; later texts to Sales route to Alice's line
    SMS.clear()
    await apply_tag_workflows(A, c1["contact_id"], ["Sold"], source="qa")
    c1 = await conv_for(CUST1)
    check("7a thread graduated to Alice's number", c1.get("graduated_at") and c1.get("rep_phone") == "+15005550101" and not c1.get("inbox_id"), str((c1.get("rep_phone"), c1.get("inbox_id"))))
    bridge = [s for s in SMS if s["to"] == CUST1]
    check("7b bridge text from Alice's number", bridge and bridge[0]["from"] == "+15005550101" and "Alice" in bridge[0]["body"], str(bridge))
    await text_in(CUST1, SALES_NUM, "Thanks Alice!")
    c1c = await conv_for(CUST1)
    check("7c text to the old Sales number lands in Alice's graduated thread", str(c1c["_id"]) == str(c1["_id"]) and await db.conversations.count_documents({"contact_phone": CUST1}) == 1,
          str(await db.conversations.count_documents({"contact_phone": CUST1})))
    await cancel_queue(str(c1["_id"]))

    # ── 8. Carl's known customer texts Sales -> stays in Carl's thread on Carl's line, no inbox lead
    await text_in("+15005550012", SALES_NUM, "Hey it's Kim")
    kim_convs = await db.conversations.find({"contact_phone": "+15005550012"}).to_list(10)
    check("8a known customer stays in Carl's existing thread", len(kim_convs) == 1 and str(kim_convs[0]["_id"]) == str(carl_conv) and not kim_convs[0].get("inbox_id"), str([(str(k['_id']), k.get('rep_phone'), k.get('inbox_id')) for k in kim_convs]))
    check("8b message stored in Carl's thread, Carl pushed, Sales team not", await db.messages.count_documents({"conversation_id": str(carl_conv), "sender": "contact"}) == 1 and pushed(C) and not pushed(A) and not pushed(B), str(PUSHES))
    check("8c no inbox lead minted for a known customer", await db.inbound_leads.count_documents({"phone": "+15005550012"}) == 0)

    # ── 9. Round robin inbox (Service): texts assign A then B; only the assignee is pushed
    await text_in("+15005550013", SERVICE_NUM, "Need an oil change")
    s1 = await conv_for("+15005550013")
    lead1 = await db.inbound_leads.find_one({"phone": "+15005550013"})
    check("9a round robin gave the first text to Alice", s1 and s1.get("assigned_to") == A and s1.get("inbox_id") == str(service_id) and s1.get("rep_phone") == SERVICE_NUM, str((s1 or {}).get("assigned_to")))
    check("9b contact owned by Alice", str((await db.contacts.find_one({"_id": ObjectId(s1["contact_id"])}) or {}).get("user_id")) == A)
    check("9c only Alice pushed for a routed lead", pushed(A) and not pushed(B), str(PUSHES))
    check("9d exactly one lead record (round robin advanced once)", lead1 is not None and await db.inbound_leads.count_documents({"phone": "+15005550013"}) == 1)
    await text_in("+15005550014", SERVICE_NUM, "Brakes squeaking")
    s2 = await conv_for("+15005550014")
    check("9e second text went to Bob", s2 and s2.get("assigned_to") == B, str((s2 or {}).get("assigned_to")))
    # customer 13 replies -> Alice's pipeline on the Service number
    await text_in("+15005550013", SERVICE_NUM, "Tomorrow work?")
    s1b = await conv_for("+15005550013")
    check("9f reply stays in Alice's Service thread", str(s1b["_id"]) == str(s1["_id"]) and pushed(A) and not pushed(B))
    await cancel_queue(str(s1["_id"])); await cancel_queue(str(s2["_id"]))
    # no first_reply configured -> the legacy AI first message is queued (not sent twice)
    check("9g no first reply configured -> AI first message queued for the scheduler", lead1 and lead1.get("status") == "queued" and lead1.get("draft_message"))
    await db.inbound_leads.update_many({"qa_cleanup": None, "phone": {"$in": ["+15005550013", "+15005550014"]}}, {"$set": {"status": "skipped", "skip_reason": "qa"}})

    # ── 10. A web-form lead source pointed at the Service inbox (legacy team_id) inherits members + routing + number
    src_id = (await db.lead_sources.insert_one({"name": "Service Web Form", "team_id": str(service_id), "store_id": sid, "assignment_method": "jump_ball",
                                                "intake_text": "Hi {{first_name}}, thanks for booking with {{lead_source}}!", "workflow_user_ids": [],
                                                "is_active": True, "qa_tag": TAG, "created_at": now})).inserted_id
    src = await db.lead_sources.find_one({"_id": src_id})
    SMS.clear(); PUSHES.clear()
    r = await li.process_inbound_lead({"first_name": "Web", "last_name": "Lead", "phone": "+15005550015", "comments": "book service"}, src, db)
    await asyncio.sleep(0.8)
    w = await db.conversations.find_one({"_id": ObjectId(r["conversation_id"])})
    check("10a form lead lives in the Service inbox on its number", w.get("inbox_id") == str(service_id) and w.get("rep_phone") == SERVICE_NUM, str((w.get("inbox_id"), w.get("rep_phone"))))
    check("10b inbox round robin applied (source said jump ball, inbox wins) -> Alice", w.get("assigned_to") == A, str(w.get("assigned_to")))
    intake = [s for s in SMS if s["to"] == "+15005550015"]
    check("10c intake text from the inbox number", intake and intake[0]["from"] == SERVICE_NUM, str(intake))
    check("10d routed lead: only Alice pushed, no team blast", pushed(A) and not pushed(B), str(PUSHES))
    await db.inbound_leads.update_many({"phone": "+15005550015"}, {"$set": {"status": "skipped", "skip_reason": "qa"}})

    # ── 11. Release + re-claim by Bob; manager assigns to Alice with a note
    s1 = await conv_for("+15005550013")
    PUSHES.clear()
    await ib.release_conversation(db, s1, alice, "Heading out, someone grab this")
    s1 = await conv_for("+15005550013")
    check("11a released back to the queue", not s1.get("assigned_to") and str(s1.get("user_id")) == sid and s1.get("handoff_note", {}).get("text", "").startswith("Heading"))
    check("11b contact back to the store", str((await db.contacts.find_one({"_id": ObjectId(s1["contact_id"])}) or {}).get("user_id")) == sid)
    check("11c teammates (not Alice) told it's up for grabs", pushed(B) and not pushed(A) and any("grabs" in p["title"].lower() for p in pushed(B)), str(PUSHES))
    try:
        await ib.release_conversation(db, s1, bob, "")
        check("11d cannot release an unowned thread as non-owner non-manager", False)
    except PermissionError:
        check("11d cannot release an unowned thread as non-owner non-manager", True)
    PUSHES.clear()
    await ib.assign_conversation(db, s1, mia, A, "Alice, this one knows you")
    s1 = await conv_for("+15005550013")
    check("11e manager assigned to Alice with note", s1.get("assigned_to") == A and (s1.get("assignment_history") or [])[-1]["note"].startswith("Alice"))
    check("11f Alice pushed 'handed to you'", pushed(A) and any("handed" in p["title"].lower() for p in pushed(A)), str(pushed(A)))
    try:
        await ib.assign_conversation(db, s1, bob, B)
        check("11g non-owner rep cannot steal an owned thread", False)
    except PermissionError:
        check("11g non-owner rep cannot steal an owned thread", True)

    # ── 12. Manager moves Bob's Service thread to Sales -> Sales number, unassigned, Sales team pushed
    s2 = await conv_for("+15005550014")
    PUSHES.clear()
    try:
        await ib.move_conversation(db, s2, bob, str(sales_id))
        check("12a only managers move threads", False)
    except PermissionError:
        check("12a only managers move threads", True)
    await ib.move_conversation(db, s2, mia, str(sales_id), note="Wants to buy, not service")
    s2 = await conv_for("+15005550014")
    check("12b moved to Sales on the Sales number, unassigned", s2.get("inbox_id") == str(sales_id) and s2.get("rep_phone") == SALES_NUM and not s2.get("assigned_to"))
    check("12c Sales members pushed about the moved thread", pushed(A) and pushed(B))
    await text_in("+15005550014", SALES_NUM, "Yes I want the blue one")
    s2b = await conv_for("+15005550014")
    check("12d customer reply to Sales lands in the moved thread", str(s2b["_id"]) == str(s2["_id"]) and await db.conversations.count_documents({"contact_phone": "+15005550014"}) == 1)
    await cancel_queue(str(s2["_id"]))

    # ── 13. "stay" inbox: Sold keeps the thread on the shared number
    s1 = await conv_for("+15005550013")
    SMS.clear()
    await apply_tag_workflows(A, s1["contact_id"], ["Sold"], source="qa")
    s1 = await conv_for("+15005550013")
    check("13a after_close=stay: thread keeps the Service number, tagged", s1.get("inbox_id") == str(service_id) and s1.get("rep_phone") == SERVICE_NUM and s1.get("closed_tag") == "Sold" and not s1.get("graduated_at"))
    check("13b no bridge text for a stay inbox", not [s for s in SMS if s["to"] == "+15005550013"])

    # ── 14. Manual graduate blocked when owner has no personal number
    await ib.assign_conversation(db, s1, mia, B, "")
    s1 = await conv_for("+15005550013")
    g = await ib.graduate_conversation(db, s1, actor_id=M)
    check("14a graduate refused when the owner has no personal line", g.get("success") is False)

    # ── 15. Visibility: Bob's list shows unassigned Sales threads + his own; Carl's does not
    msgs._conv_cache.clear()
    bob_list = await msgs.get_conversations(B)
    carl_list = await msgs.get_conversations(C)
    bob_ids = {c["_id"] for c in bob_list}
    check("15a member sees the unassigned Sales thread and the one assigned to him", str(s2["_id"]) in bob_ids and str(s1["_id"]) in bob_ids, f"{len(bob_list)}")
    check("15b unassigned rows are flagged for the claim button", any(c["_id"] == str(s2["_id"]) and c.get("is_unassigned") and c.get("inbox_name") == "Sales" for c in bob_list))
    check("15c non-member does not see inbox threads", not any(c.get("inbox_id") in (str(sales_id), str(service_id)) for c in carl_list))
    msgs._conv_cache.clear()

    # ── 16. STOP from an unknown number -> no lead, opt-out only
    await text_in("+15005550016", SALES_NUM, "STOP")
    check("16a STOP creates no lead or thread", await db.conversations.count_documents({"contact_phone": "+15005550016"}) == 0 and await db.inbound_leads.count_documents({"phone": "+15005550016"}) == 0)

    # ── 17. Personal-number routing untouched: text to Alice's own number behaves as before
    await text_in("+15005550017", "+15005550101", "Hi Alice")
    p = await conv_for("+15005550017")
    check("17a text to a rep's own number is a plain personal thread", p and str(p.get("user_id")) == A and not p.get("inbox_id") and p.get("rep_phone") == "+15005550101")
    await cancel_queue(str(p["_id"])) if p else None

    # ── Report ─────────────────────────────────────────────────────────────
    ok = sum(1 for r in results if r[1])
    for name, passed, detail in results:
        print(f"{'PASS' if passed else 'FAIL'}  {name}" + ("" if passed else f"   <- {detail}"))
    print(f"\n{ok}/{len(results)} passed")

    return ok == len(results)


async def _cleanup(db, sid, users, sales_id, service_id, now):
    phones = ["+15005550011", "+15005550012", "+15005550013", "+15005550014", "+15005550015", "+15005550016", "+15005550017"]
    TAGQ = {"$regex": "^qa-inbox-"}
    conv_ids = [str(c["_id"]) for c in await db.conversations.find({"contact_phone": {"$in": phones}}).to_list(50)]
    await db.messages.delete_many({"conversation_id": {"$in": conv_ids}})
    await db.ai_reply_queue.delete_many({"conversation_id": {"$in": conv_ids}})
    await db.notifications.delete_many({"$or": [{"conversation_id": {"$in": conv_ids}}, {"user_id": {"$in": list(users)}}]})
    await db.conversations.delete_many({"contact_phone": {"$in": phones}})
    await db.contacts.delete_many({"$or": [{"phone": {"$in": phones}}, {"qa_tag": TAG}]})
    await db.inbound_leads.delete_many({"phone": {"$in": phones}})
    await db.lead_deferred_actions.delete_many({"to": {"$in": phones}})
    await db.contact_events.delete_many({"user_id": {"$in": list(users) + [sid]}})
    await db.lead_call_jobs.delete_many({"conversation_id": {"$in": conv_ids}})
    old_inboxes = [str(i["_id"]) for i in await db.shared_inboxes.find({"qa_tag": TAGQ}, {"_id": 1}).to_list(50)]
    old_users = [str(u["_id"]) for u in await db.users.find({"qa_tag": TAGQ}, {"_id": 1}).to_list(50)]
    await db.notifications.delete_many({"user_id": {"$in": old_users}})
    await db.contact_events.delete_many({"user_id": {"$in": old_users}})
    await db.lead_sources.delete_many({"$or": [{"qa_tag": TAGQ}, {"inbox_id": {"$in": old_inboxes}}]})
    await db.shared_inboxes.delete_many({"qa_tag": TAGQ})
    await db.users.delete_many({"qa_tag": TAGQ})
    await db.stores.delete_many({"qa_tag": TAGQ})
    await db.contacts.delete_many({"qa_tag": TAGQ})
    await db.inbound_message_dedup.delete_many({"created_at": {"$gte": now - timedelta(minutes=5)}, "message_sid": {"$regex": "^SM[0-9a-f]{24}$"}})


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(main()) else 1)
