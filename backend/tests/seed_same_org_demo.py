"""Preview-only demo of same-store rep isolation for manual / UI checks. Seeds org "QA SameOrg Iso Org": reps A + A2, store manager M
(qa-sameorg-a|a2|m@invalid.imonsocial.test / SameOrgIso123!), shared inbox "QA SameOrg Sales", A's customer "Walt Sameorg" (private
notes, memo, file, fact mention "Harley" / "NADA") and one thread on Walt shared with A2 as a collaborator.
Run: cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && PYTHONPATH=/app/backend python tests/seed_same_org_demo.py [--wipe]
Note: tests/test_same_org_rep_isolation.py uses the same accounts and wipes them when it runs."""
import sys

from tests import test_same_org_rep_isolation as t

t.run(t._wipe_leftovers())
if "--wipe" in sys.argv:
    print("wiped")
    sys.exit(0)
t.run(t._seed())
t.scenario(sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in t.SCENARIOS else "collaborator")
print({"org": t.S["org"], "store": t.S["store"], "users": t.S["uid"], "contact_walt": t.S["ca"], "conversation": t.S["conv"], "inbox": t.S["inbox"]})
