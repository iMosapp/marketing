"""Anonymous, read-only production smoke for the contact ownership hotfix (Oct 2026).
python tests/prod_smoke_contact_ownership.py [base_url] [expected_build]

Checks the live build label FIRST (exit 2 before any probe on a mismatch), then that the new and hardened routes refuse anonymous
callers. GET only; ids cannot exist; nothing is created. Then run the full earlier smoke: python tests/prod_smoke_hotfix3.py <base> <build>."""
import sys

from prod_smoke_hotfix3 import call, preflight

BASE_DEFAULT = "https://app.imonsocial.com"
BUILD = "2026-10-16.contact-ownership"
Z = "0" * 24
CHECKS = [
    ("/api/admin/contact-merge-assessment?confirm=COUNTS_ONLY", (401,)),
    ("/api/admin/contact-access-audit", (401,)),
    (f"/api/contacts/{Z}/{Z}/personal-details", (401,)),
    (f"/api/voice-notes/{Z}/{Z}", (401,)),
    (f"/api/intel/contacts/{Z}/facts", (401,)),
    (f"/api/contact-ask/{Z}", (401,)),
    (f"/api/contacts/{Z}/duplicates", (401,)),
    ("/api/memory/search", (401, 405)),
]

if __name__ == "__main__":
    import prod_smoke_hotfix3 as base
    base.BASE = (sys.argv[1] if len(sys.argv) > 1 else BASE_DEFAULT).rstrip("/")
    expected = sys.argv[2] if len(sys.argv) > 2 else BUILD
    ok, build = preflight(expected)
    if not ok:
        print(f"ABORT: live build is {build!r}, expected {expected!r}. Nothing probed.")
        sys.exit(2)
    bad = 0
    for path, accepted in CHECKS:
        st, _ = call("GET", path)
        good = st in accepted
        bad += not good
        print(f"{'OK ' if good else 'BAD'} {st} GET {path}")
    print(f"{len(CHECKS) - bad}/{len(CHECKS)} passed on {base.BASE} (build {build})")
    sys.exit(1 if bad else 0)
