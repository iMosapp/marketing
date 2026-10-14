"""Static audit of /api routes vs services.route_guard: which GET routes are NOT public and carry NO auth dependency of their own.
Those used to be reachable anonymously before hotfix 3 (old middleware let requests without X-User-ID through) and are now 401.
Run: cd /app/backend && set -a && . ./.env && set +a && python tests/route_audit.py [--all]"""
import inspect
import os
import re
import sys

sys.path.insert(0, "/app/backend")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
from fastapi.routing import APIRoute  # noqa: E402

from server import app  # noqa: E402
from services.route_guard import is_public  # noqa: E402

AUTH_HINTS = ("current_user", "verify_", "require_", "authorize", "x_user_id", "user_id", "caller", "admin", "token", "session", "scoped")


def dep_names(dependant, acc=None):
    acc = acc if acc is not None else []
    for d in dependant.dependencies:
        if d.call is not None:
            acc.append(getattr(d.call, "__name__", str(d.call)))
        dep_names(d, acc)
    return acc


def has_auth(route):
    names = dep_names(route.dependant)
    if any(h in n.lower() for n in names for h in ("current_user", "verify", "require", "authorize", "admin", "caller", "scoped", "owner", "manager")):
        return True
    params = [p.name for p in route.dependant.header_params] + [p.name for p in route.dependant.query_params]
    if any(p.lower() in ("x_user_id", "x-user-id", "authorization", "token", "key", "secret") for p in params):
        return True
    try:
        src = inspect.getsource(route.endpoint)
    except Exception:
        return False
    return bool(re.search(r"X-User-ID|x_user_id|get_current_user|verify_user_access|require_role|_verified_caller_id|request\.state\.caller_id|Authorization", src))


def main():
    show_all = "--all" in sys.argv
    rows = []
    for r in app.routes:
        if not isinstance(r, APIRoute) or not r.path.startswith("/api/"):
            continue
        for m in sorted(r.methods - {"HEAD", "OPTIONS"}):
            probe = re.sub(r"\{[^}]+\}", "0" * 24, r.path)
            probe2 = re.sub(r"\{[^}]+\}", "probe", r.path)
            public = is_public(m, probe) or is_public(m, probe2)
            if public:
                continue
            uid = "{user_id}" in r.path
            auth = has_auth(r)
            if show_all or (m == "GET" and not auth and not uid):
                rows.append((m, r.path, r.endpoint.__module__.replace("routers.", ""), "auth" if auth else "-", "uid" if uid else "-"))
    rows.sort(key=lambda x: (x[2], x[1]))
    for row in rows:
        print("  ".join(f"{c:<8}" if i == 0 else c for i, c in enumerate(row)))
    print(f"\n{len(rows)} routes")


if __name__ == "__main__":
    main()
