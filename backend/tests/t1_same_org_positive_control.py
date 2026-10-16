"""T1 iteration 406: positive control + targeted probes on the seeded same-org demo (/tmp/iso_state.json from t1_same_org_route_fuzz.py)."""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import requests

BASE = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
S = json.load(open("/tmp/iso_state.json"))
ROUTES = json.load(open("/tmp/routes.json"))
SKIP = re.compile(r"(send|call|dial|buy|provision|webhook|cron|stream|/ws|sse|export|twilio|stripe|checkout|run|trigger|backfill|sync|purge|reset|import|oauth|callback|/tts|audio|download)", re.I)
who = sys.argv[1] if len(sys.argv) > 1 else "A"
uid = S["uid"][who]
ids = {"user_id": uid, "contact_id": S["ca"], "cid": S["ca"], "conversation_id": S["conv"], "conv_id": S["conv"], "note_id": S["memo"], "file_id": S["file"],
       "fid": S["file"], "fact_id": S["fact"], "store_id": S["store"], "inbox_id": S["inbox"]}
gets = sorted({p for m, p in ROUTES if m == "GET" and p.startswith("/api/") and not SKIP.search(p)})
codes = {}


def probe(p):
    url = BASE + re.sub(r"\{(\w+)(?::\w+)?\}", lambda m: ids.get(m.group(1), S["ca"]), p)
    r = requests.get(url, params={"contact_id": S["ca"], "user_id": uid, "q": "Walt", "search": "Walt"}, headers={"Authorization": f"Bearer {S['tok'][who]}"}, timeout=40)
    return p, r.status_code, ("Harley" in r.text or "NADA" in r.text)


with ThreadPoolExecutor(6) as ex:
    res = list(ex.map(probe, gets))
for p, st, lk in res:
    codes[st] = codes.get(st, 0) + 1
print(who, "status histogram", codes)
print(who, "routes returning private markers:", [p for p, st, lk in res if lk])
