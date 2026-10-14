"""One-off migration: give a legacy live-API test module a real JWT session (forest, super admin) on every `requests.<verb>(` call
that carries no headers, and point its hard-coded TEST_USER_ID at the session user. Usage: python tests/_migrate_auth.py tests/test_x.py"""
import re
import sys
from pathlib import Path

HEADER = '''from tests.live_auth import Session as _Session
from tests import qa_creds as _qa
_ADMIN = _Session("forest@imosapp.com", _qa.password_for("forest@imosapp.com"))
AUTH_H = _ADMIN.headers
'''

for arg in sys.argv[1:]:
    p = Path(arg)
    s = p.read_text()
    if "AUTH_H" not in s:
        s = re.sub(r"(^import requests\n)", r"\1" + HEADER, s, count=1, flags=re.M)
    s = re.sub(r'^TEST_USER_ID\s*=\s*"[0-9a-f]{24}".*$', "TEST_USER_ID = _ADMIN.user_id", s, flags=re.M)

    def add_headers(m):
        call = m.group(0)
        return call if "headers=" in call else call[:-1] + (", headers=AUTH_H)" if not call.endswith("()") else "headers=AUTH_H)")

    # single-line calls
    s = re.sub(r"requests\.(get|post|put|patch|delete)\([^\n]*\)(?=\s*$)", add_headers, s, flags=re.M)
    # multi-line calls: insert after the opening paren
    s = re.sub(r"requests\.(get|post|put|patch|delete)\(\s*\n(\s+)", lambda m: f"requests.{m.group(1)}(\n{m.group(2)}headers=AUTH_H,\n{m.group(2)}", s)
    p.write_text(s)
    print("migrated", p)
