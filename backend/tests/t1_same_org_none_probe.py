"""T1 iteration 406: in the 'none' scenario (A2 has NO thread on Walt) can A2 open a conversation / task on A's customer by body contact_id?"""
import json
import sys

import requests

from tests import test_same_org_rep_isolation as t

st = json.load(open("/tmp/iso_state.json"))
t.S.update(uid=st["uid"], tok=st["tok"], ca=st["ca"], store=st["store"], inbox=st["inbox"], cids=[st["ca"]])
async def _warm():
    await t.get_db().users.find_one({}, {"_id": 1})


t.run(_warm())
name = sys.argv[1] if len(sys.argv) > 1 else "none"
t.scenario(name)
A2, W = st["uid"]["A2"], st["ca"]
h = {"Authorization": f"Bearer {st['tok']['A2']}"}
for method, path, body in (("POST", f"/messages/conversations/{A2}", {"contact_id": W}), ("POST", f"/tasks/{A2}", {"title": "T1 probe", "contact_id": W, "type": "follow_up"})):
    r = requests.request(method, f"{t.BASE}/api{path}", json=body, headers=h, timeout=60)
    print(name, method, path.replace(A2, "{A2}"), r.status_code, ("LEAK " if "Harley" in r.text or "NADA" in r.text else "") + r.text[:160])
import os
from pymongo import MongoClient
convs = list(MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]].conversations.find({"contact_id": W}, {"user_id": 1}))
print("conversations on Walt now:", [(str(c["_id"]), c.get("user_id") == A2) for c in convs])
if len(sys.argv) > 2 and sys.argv[2] == "probe_send":
    pass
MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]].tasks.delete_many({"title": "T1 probe"})
t.scenario("collaborator")
st["conv"] = t.S["conv"]
json.dump(st, open("/tmp/iso_state.json", "w"))
print("restored collaborator scenario, conv", st["conv"])
