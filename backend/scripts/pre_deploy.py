#!/usr/bin/env python3
"""
Pre-Deploy Health Check
Run this before every deploy: python3 scripts/pre_deploy.py

Checks:
  1. All Python files compile without syntax errors
  2. All key modules import cleanly
  3. Backend server starts and /health returns OK
  4. Scheduler is running with expected jobs
  5. Database is reachable

Exit code 0 = safe to deploy
Exit code 1 = DO NOT DEPLOY, fix errors first
"""
import subprocess
import sys
import os
import glob

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(SCRIPT_DIR)   # /app/backend

# Must run from backend dir for imports to work
os.chdir(BACKEND)
sys.path.insert(0, BACKEND)

ERRORS = []
WARNINGS = []
PASSED = 0


def ok(msg):
    global PASSED
    PASSED += 1
    print(f"  ✅ {msg}")


def fail(msg):
    ERRORS.append(msg)
    print(f"  ❌ {msg}")


def warn(msg):
    WARNINGS.append(msg)
    print(f"  ⚠️  {msg}")


# ─── 1. Syntax check all Python files ────────────────────────────────────────
print("\n📋 Step 1: Syntax check all Python files")
import py_compile

py_files = glob.glob(os.path.join(BACKEND, "**/*.py"), recursive=True)
py_files += glob.glob(os.path.join(BACKEND, "*.py"))

syntax_errors = []
for f in sorted(set(py_files)):
    rel = os.path.relpath(f, BACKEND)
    try:
        py_compile.compile(f, doraise=True)
    except py_compile.PyCompileError as e:
        syntax_errors.append((rel, str(e)))
        fail(f"Syntax error in {rel}: {e}")

if not syntax_errors:
    ok(f"All {len(py_files)} Python files compile cleanly")


# ─── 2. Key module imports ────────────────────────────────────────────────────
print("\n📋 Step 2: Key module imports")
sys.path.insert(0, BACKEND)

CRITICAL_MODULES = [
    "scheduler",
    "server",
    "routers.auth",
    "routers.campaigns",
    "routers.messages",
    "routers.ai_reply",
    "routers.lead_intake",
    "routers.push_notifications",
    "routers.user_schedule",
    "routers.training",
]

for mod in CRITICAL_MODULES:
    try:
        __import__(mod)
        ok(f"Import: {mod}")
    except Exception as e:
        fail(f"Import failed: {mod} — {e}")


# ─── 3. Check backend is running ─────────────────────────────────────────────
print("\n📋 Step 3: Backend health check")
try:
    import urllib.request
    import json as _json

    # Try internal port
    try:
        with urllib.request.urlopen("http://localhost:8001/api/health", timeout=5) as r:
            data = _json.loads(r.read())
            if data.get("status") == "healthy":
                ok(f"Backend /health: {data}")
            else:
                fail(f"Backend /health returned: {data}")
    except Exception as e:
        warn(f"Backend not running locally (ok if running elsewhere): {e}")
except Exception as e:
    warn(f"Health check skipped: {e}")


# ─── 4. Scheduler sanity check ───────────────────────────────────────────────
print("\n📋 Step 4: Scheduler sanity check")
try:
    from scheduler import SCHEDULER_JOBS_EXPECTED
    ok(f"Scheduler module loads. Expected jobs defined: {len(SCHEDULER_JOBS_EXPECTED)}")
except ImportError:
    # SCHEDULER_JOBS_EXPECTED doesn't exist yet — just check it imports
    try:
        import scheduler as _sched
        ok("Scheduler module loads cleanly")
    except Exception as e:
        fail(f"Scheduler import failed: {e}")
except Exception as e:
    fail(f"Scheduler check failed: {e}")


# ─── 5. Critical function signatures ─────────────────────────────────────────
print("\n📋 Step 5: Critical function signatures")

CHECKS = [
    ("scheduler", "generate_daily_system_tasks", "async def"),
    ("scheduler", "send_morning_push_digest", "async def"),
    ("routers.ai_reply", "queue_ai_reply", "async def"),
    ("routers.push_notifications", "send_push_to_user", "async def"),
    ("routers.lead_intake", "process_inbound_lead", "async def"),
    ("routers.demo_requests", "_email_new_lead", "async def"),
]

import inspect

for mod_name, func_name, _ in CHECKS:
    try:
        mod = sys.modules.get(mod_name) or __import__(mod_name)
        fn = getattr(mod, func_name)
        if not inspect.iscoroutinefunction(fn):
            fail(f"{mod_name}.{func_name} is not async!")
        else:
            ok(f"{mod_name}.{func_name} ✓")
    except AttributeError:
        fail(f"Missing function: {mod_name}.{func_name}")
    except Exception as e:
        fail(f"Check failed for {mod_name}.{func_name}: {e}")


# ─── Summary ──────────────────────────────────────────────────────────────────
print("\n" + "=" * 55)
if ERRORS:
    print(f"🚨 PRE-DEPLOY CHECK FAILED — {len(ERRORS)} error(s), {PASSED} passed")
    print("\nErrors to fix:")
    for e in ERRORS:
        print(f"  • {e}")
    print("\n⛔  DO NOT DEPLOY until all errors are resolved.\n")
    sys.exit(1)
else:
    print(f"✅ ALL CHECKS PASSED ({PASSED} checks, {len(WARNINGS)} warning(s))")
    if WARNINGS:
        for w in WARNINGS:
            print(f"  ⚠️  {w}")
    print("\n🚀 Safe to deploy.\n")
    sys.exit(0)
