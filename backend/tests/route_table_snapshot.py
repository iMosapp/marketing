"""Dump the app's full route table + OpenAPI schema so two builds can be diffed. Usage: python tests/route_table_snapshot.py out.json"""
import hashlib
import json
import sys

from fastapi.datastructures import DefaultPlaceholder
from fastapi.routing import APIRoute, APIWebSocketRoute

import server


def _cls(c):
    c = c.value if isinstance(c, DefaultPlaceholder) else c
    return f"{c.__module__}.{c.__qualname__}" if c else None


def _sig(r):
    ep = getattr(r, "endpoint", None)
    base = {"type": type(r).__name__, "path": getattr(r, "path", None), "name": getattr(r, "name", None),
            "endpoint": f"{ep.__module__}.{ep.__qualname__}" if ep else None}
    if isinstance(r, APIRoute):
        base.update(methods=sorted(r.methods), response_class=_cls(r.response_class), status_code=r.status_code,
                    response_model=repr(r.response_model), include_in_schema=r.include_in_schema, tags=list(r.tags or []),
                    dependencies=len(r.dependencies), deprecated=r.deprecated, operation_id=r.operation_id, unique_id=r.unique_id,
                    responses=sorted(map(str, (r.responses or {}).keys())), path_regex=r.path_regex.pattern,
                    params=sorted(p.name for p in r.dependant.query_params + r.dependant.path_params + r.dependant.body_params))
    elif isinstance(r, APIWebSocketRoute):
        base.update(path_regex=r.path_regex.pattern)
    else:
        base.update(methods=sorted(getattr(r, "methods", None) or []))
    return base


routes = [_sig(r) for r in server.app.routes]
try:
    schema = json.dumps(server.app.openapi(), sort_keys=True, default=str)
except Exception as e:  # the schema build already fails on a PyObjectId model; compare the failure too
    schema = f"openapi error: {type(e).__name__}: {e}"
out = {"count": len(routes), "routes": routes, "openapi_sha256": hashlib.sha256(schema.encode()).hexdigest(),
       "startup_handlers": [f"{h.__module__}.{h.__qualname__}" for h in server.app.router.on_startup],
       "shutdown_handlers": [f"{h.__module__}.{h.__qualname__}" for h in server.app.router.on_shutdown]}
json.dump(out, open(sys.argv[1], "w"), indent=1)
print(out["count"], "routes; openapi", out["openapi_sha256"][:16], "; startup", len(out["startup_handlers"]))
