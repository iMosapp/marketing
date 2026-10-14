"""Anonymous write-route probe: every POST/PUT/PATCH/DELETE route gets one request with NO credentials and an empty JSON body.
401/403 = the route refuses strangers. Anything else = the handler ran without identity (candidate for review).
Preview only (localhost:8001). Path params are filled with a QA user id / fake ids so the probe reaches the handler."""
import json
import os
import re
import sys

import requests

sys.path.insert(0, "/app/backend")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
from server import app  # noqa: E402
from fastapi.routing import APIRoute  # noqa: E402

BASE = os.environ.get("PROBE_BASE", "http://localhost:8001")
USER_ID = os.environ.get("PROBE_USER_ID", "6acda9de0a6d0d603d041575")
OID = "6acda9de0a6d0d603d04ffff"
PUBLIC = ("/api/webhooks/", "/api/public/", "/api/w/", "/api/card/", "/api/l/", "/api/p/", "/api/s/", "/api/review/", "/api/opt-in/",
          "/api/showcase/", "/api/congrats/", "/api/images/", "/api/health", "/api/email/webhook", "/api/ghl/webhook", "/api/chat/",
          "/api/widgets/", "/api/tracking/", "/api/seo/track-visit", "/api/nda/sign/", "/api/team-invite/", "/api/leads/test-adf",
          "/api/auth/login", "/api/auth/signup", "/api/auth/forgot-password", "/api/auth/activate", "/api/auth/logout", "/api/auth/refresh",
          "/api/scripts/roleplay/twiml", "/api/scripts/roleplay/gate", "/api/scripts/roleplay/host-after", "/api/scripts/roleplay/after",
          "/api/scripts/roleplay/status", "/api/scripts/roleplay/recording", "/api/interview/call/", "/api/onboarding-jessi/call/",
          "/api/subscriptions/w9/", "/api/crm/timeline/", "/api/demo-requests", "/api/push/log-error", "/api/errors/", "/api/appraisals/intake/")
SKIP_EXACT = {"/api/admin/twilio/numbers/purchase", "/api/admin/twilio/test-sms"}


def fill(path):
    def sub(m):
        name = m.group(1)
        if name in ("user_id",):
            return USER_ID
        if name in ("level",):
            return "user"
        if name in ("trigger_type",):
            return "birthday"
        if name in ("state", "key", "username", "token", "slug", "ref_code", "code", "tag_name", "number_sid", "sid", "call_sid"):
            return "probe"
        return OID
    return re.sub(r"\{([^}:]+)(?::[^}]*)?\}", sub, path)


def main():
    out = []
    for r in app.routes:
        if not isinstance(r, APIRoute):
            continue
        for m in sorted(r.methods - {"HEAD", "OPTIONS", "GET"}):
            if not r.path.startswith("/api/") or r.path.startswith(PUBLIC) or r.path in SKIP_EXACT:
                continue
            url = BASE + fill(r.path)
            try:
                resp = requests.request(m, url, json={}, timeout=20)
                code = resp.status_code
            except Exception as e:
                code = f"ERR {type(e).__name__}"
            out.append({"method": m, "path": r.path, "status": code, "module": r.endpoint.__module__})
    blocked = [o for o in out if o["status"] in (401, 403)]
    ran = [o for o in out if o["status"] not in (401, 403)]
    print(f"probed {len(out)} write routes: {len(blocked)} refuse strangers, {len(ran)} ran without identity")
    for o in sorted(ran, key=lambda o: (o["module"], o["path"])):
        print(f"  {o['status']!s:4} {o['method']:6} {o['path']}   [{o['module']}]")
    json.dump(out, open("/app/test_reports/anon_write_probe.json", "w"), indent=1)


if __name__ == "__main__":
    main()
