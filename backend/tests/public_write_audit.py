"""Public WRITE routes (per route_guard) and whether the handler source shows its own credential/signature check."""
import inspect
import os
import re
import sys

sys.path.insert(0, "/app/backend")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
from fastapi.routing import APIRoute  # noqa: E402

from server import app  # noqa: E402
from services.route_guard import is_public  # noqa: E402

PAT = re.compile(r"validat|verify|secret|signature|api_key|X-API-Key|token|rate_limit|ratelimit|captcha|get_current_user|caller_id|_require_auth", re.I)
rows = []
for r in app.routes:
    if not isinstance(r, APIRoute) or not r.path.startswith("/api/"):
        continue
    for m in sorted(r.methods - {"HEAD", "OPTIONS", "GET"}):
        probe = re.sub(r"\{[^}]+\}", "0" * 24, r.path)
        if not (is_public(m, probe) or is_public(m, re.sub(r"\{[^}]+\}", "probe", r.path))):
            continue
        try:
            src = inspect.getsource(r.endpoint)
        except Exception:
            src = ""
        rows.append((r.endpoint.__module__.replace("routers.", ""), m, r.path, "checks" if PAT.search(src) else "NO-CHECK"))
for row in sorted(rows):
    if "--all" in sys.argv or row[3] == "NO-CHECK":
        print(f"{row[3]:<9} {row[1]:<7} {row[2]:<70} {row[0]}")
print(len(rows), "public write routes")
