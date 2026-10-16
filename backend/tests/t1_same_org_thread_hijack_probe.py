"""T1 iteration 406: 'none' + 'inbox_claimed_by_owner' scenarios - can A2 act on A's own thread by conversation id? Walt's phone is swapped to a
Twilio test number (+15005550191) for the duration so no real-format number can ever be texted. Restores everything (collaborator scenario)."""
import json
import os
import sys

import requests
from bson import ObjectId
from pymongo import MongoClient

from tests import test_same_org_rep_isolation as t

st = json.load(open("/tmp/iso_state.json"))
t.S.update(uid=st["uid"], tok=st["tok"], ca=st["ca"], store=st["store"], inbox=st["inbox"], cids=[st["ca"]])
mdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


async def _warm():
    await t.get_db().users.find_one({}, {"_id": 1})


t.run(_warm())
A2, W = st["uid"]["A2"], st["ca"]
h = {"Authorization": f"Bearer {st['tok']['A2']}"}
old_phone = mdb.contacts.find_one({"_id": ObjectId(W)})["phone"]
mdb.contacts.update_one({"_id": ObjectId(W)}, {"$set": {"phone": "+15005550191"}})
try:
    for name in ("none", "inbox_claimed_by_owner"):
        t.scenario(name)
        conv = t.S["conv"]
        before = mdb.messages.count_documents({"conversation_id": conv})
        probes = [("GET", f"/messages/thread/{conv}", None), ("GET", f"/messages/conversation/{conv}/info", None),
                  ("POST", f"/messages/send/{A2}/{conv}", {"conversation_id": conv, "content": "T1 hijack probe", "channel": "sms"}),
                  ("POST", f"/messages/send/{A2}", {"conversation_id": conv, "content": "T1 hijack probe", "channel": "sms"}),
                  ("POST", f"/inboxes/conversations/{conv}/claim", {}), ("POST", f"/chat/claim/{conv}", {}),
                  ("POST", f"/lead-sources/claim/{conv}", {}), ("POST", f"/leads/queue/{A2}/reassign/{conv}", {"to_user_id": A2}),
                  ("POST", f"/messages/ai-suggest/{conv}", {})]
        for m, p, body in probes:
            r = requests.request(m, f"{t.BASE}/api{p}", json=body, headers=h, timeout=60)
            leak = "LEAK " if ("Harley" in r.text or "NADA" in r.text) else ""
            print(name, m, p.replace(conv, "{conv}").replace(A2, "{A2}"), r.status_code, leak + r.text[:110].replace("\n", " "))
        c = mdb.conversations.find_one({"_id": ObjectId(conv)})
        print(name, "messages added:", mdb.messages.count_documents({"conversation_id": conv}) - before, "| assigned_to:", c.get("assigned_to"), "| user_id is A:", c.get("user_id") == st["uid"]["A"])
finally:
    mdb.contacts.update_one({"_id": ObjectId(W)}, {"$set": {"phone": old_phone}})
    mdb.messages.delete_many({"content": "T1 hijack probe"})
    t.scenario("collaborator")
    st["conv"] = t.S["conv"]
    json.dump(st, open("/tmp/iso_state.json", "w"))
    print("restored collaborator; conv", st["conv"])
