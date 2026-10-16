"""T1 iteration 406: route fuzzer for same-store rep isolation. Seeds the same-org demo (tests/test_same_org_rep_isolation helpers), then
calls EVERY GET route of the app as rep A2 with Walt's ids substituted into every path parameter (+ contact_id / user_id / q query args)
and reports any response containing the private markers 'Harley' / 'NADA'. Read-only GETs only (risky verbs skipped). Leaves the demo
seeded in the 'collaborator' scenario (same as tests/seed_same_org_demo.py). Run:
cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && PYTHONPATH=/app/backend python tests/t1_same_org_route_fuzz.py
"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import requests

from tests import test_same_org_rep_isolation as t

ROUTES = json.load(open("/tmp/routes.json"))
SKIP = re.compile(r"(send|call|dial|buy|provision|webhook|cron|stream|/ws|sse|export|twilio|stripe|checkout|run|trigger|backfill|sync|purge|reset|import|oauth|callback|/tts|audio|download)", re.I)


def subst(path, ids):
    def rep(m):
        n = m.group(1)
        return ids.get(n, ids["contact_id"])
    return re.sub(r"\{(\w+)(?::\w+)?\}", rep, path)


def main():
    t.run(t._wipe_leftovers())
    t.run(t._seed())
    for key in t.S["uid"]:
        r = requests.post(f"{t.BASE}/api/auth/login", json={"email": f"qa-sameorg-{key.lower()}@invalid.imonsocial.test", "password": t.PW}, timeout=30)
        assert r.status_code == 200, r.text
        t.S["tok"][key] = r.json()["token"]
    db = t.get_db()
    gets = sorted({p for m, p in ROUTES if m == "GET" and p.startswith("/api/") and not SKIP.search(p)})
    print("GET routes probed:", len(gets))
    leaks = {}
    for name in ("collaborator", "assigned", "inbox_unclaimed"):
        t.scenario(name)
        task = t.run(db.tasks.find_one({"contact_id": t.S["ca"]}))
        msg = t.run(db.messages.find_one({"contact_id": t.S["ca"]}))
        ids = {"user_id": t.S["uid"]["A2"], "contact_id": t.S["ca"], "cid": t.S["ca"], "conversation_id": t.S["conv"], "conv_id": t.S["conv"],
               "note_id": t.S["memo"], "file_id": t.S["file"], "fid": t.S["file"], "fact_id": t.S["fact"], "task_id": str(task["_id"]) if task else t.S["ca"],
               "message_id": str(msg["_id"]), "store_id": t.S["store"], "org_id": t.S["org"], "inbox_id": t.S["inbox"]}
        q = {"contact_id": t.S["ca"], "user_id": t.S["uid"]["A2"], "q": "Walt", "search": "Walt", "query": "Walt"}

        def probe(p):
            url = f"{t.BASE}{subst(p, ids)}"
            try:
                r = requests.get(url, params=q, headers={"Authorization": f"Bearer {t.S['tok']['A2']}"}, timeout=40)
                body = r.text
            except Exception as e:  # noqa: BLE001
                return p, -1, str(e)[:80]
            if "Harley" in body or "NADA" in body:
                return p, r.status_code, body[:300]
            return None

        with ThreadPoolExecutor(6) as ex:
            for res in ex.map(probe, gets):
                if res:
                    leaks.setdefault(res[0], []).append((name, res[1], res[2]))
        print(f"[{name}] cumulative leaking routes: {len(leaks)}")
    for p, v in leaks.items():
        print("LEAK", p, v[0][1], [x[0] for x in v], v[0][2].replace("\n", " ")[:250])
    t.scenario("collaborator")
    print("left seeded:", {"users": t.S["uid"], "walt": t.S["ca"], "conv": t.S["conv"], "memo": t.S["memo"], "file": t.S["file"], "fact": t.S["fact"]})
    json.dump({"uid": t.S["uid"], "tok": t.S["tok"], "ca": t.S["ca"], "conv": t.S["conv"], "memo": t.S["memo"], "file": t.S["file"], "fact": t.S["fact"],
               "store": t.S["store"], "inbox": t.S["inbox"]}, open("/tmp/iso_state.json", "w"))
    return 1 if leaks else 0


if __name__ == "__main__":
    sys.exit(main())
