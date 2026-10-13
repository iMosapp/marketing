"""QA credentials for preview tests, read from the gitignored /app/memory/test_credentials.md (fallback: QA_PASSWORD_<EMAIL> env vars).
Nothing in this module or its callers holds a password literal."""
import os
import re

CREDS_PATH = "/app/memory/test_credentials.md"


def password_for(email: str) -> str:
    env = os.environ.get("QA_PASSWORD_" + re.sub(r"[^A-Za-z0-9]", "_", email).upper())
    if env:
        return env
    creds = open(CREDS_PATH).read()
    m = re.search(re.escape(email) + r"\s*/\s*([^\s*`]+)", creds) or re.search(re.escape(email) + r".*?\n- Password:\s*(\S+)", creds, re.S)
    if not m:
        raise RuntimeError(f"no password for {email} in {CREDS_PATH}")
    return m.group(1)


def account(email: str) -> dict:
    return {"email": email, "password": password_for(email)}
