"""Historical cross-organization merge assessment: STRICTLY READ-ONLY, COUNTS ONLY.

What it answers: did a contact merge (the retired startup phone consolidation, or a manual / Jessi merge) ever fold one tenant's contact
into another tenant's contact, and how many records of the first tenant now hang off the second tenant's contact?
A tenant is the owner's organization, or the user themself for accounts without an organization.

Safeguards (enforced in code, covered by tests/test_merge_assessment.py):
  * every query goes through ReadOnlyDB, which exposes only find / count_documents / aggregate and refuses $out / $merge stages;
  * projections carry ids and owner fields only, never names, phones, emails, notes, message bodies or transcripts;
  * the result holds integers and month keys only (no ids, no names); nothing is written anywhere (no DB row, no file);
  * every query has max_time_ms; pairs / ids are capped (CAP) and the result says when a cap was hit.
"""
import logging
import time
from collections import Counter

from bson import ObjectId

logger = logging.getLogger(__name__)

MAX_MS = 20000
CAP = 50000
# collections a merge re-points (union of the retired consolidation and services.duplicates.MIGRATE) + private relationship records
CHILD_COLLECTIONS = ("conversations", "messages", "contact_events", "campaign_enrollments", "campaign_pending_sends", "tasks", "notes", "call_logs",
                     "voice_notes", "contact_files", "contact_facts", "ai_reply_queue", "inbound_leads", "congrats_cards", "broadcast_messages")
_ALLOWED = {"find", "count_documents", "aggregate"}
_FORBIDDEN_STAGES = {"$out", "$merge"}


class ReadOnlyCollection:
    def __init__(self, coll):
        self._c = coll

    def find(self, query, projection):
        if not projection:
            raise PermissionError("merge assessment: a projection is required")
        return self._c.find(query, projection).max_time_ms(MAX_MS)

    async def count_documents(self, query):
        return await self._c.count_documents(query, maxTimeMS=MAX_MS)

    def aggregate(self, pipeline):
        if any(k in _FORBIDDEN_STAGES for stage in pipeline for k in stage):
            raise PermissionError("merge assessment: write stages are not allowed")
        return self._c.aggregate(pipeline, maxTimeMS=MAX_MS)

    def __getattr__(self, name):
        raise PermissionError(f"merge assessment is read-only ({name} refused)")


class ReadOnlyDB:
    def __init__(self, db):
        self._db = db

    def __getitem__(self, name) -> ReadOnlyCollection:
        return ReadOnlyCollection(self._db[name])

    def __getattr__(self, name) -> ReadOnlyCollection:
        if name.startswith("_"):
            raise AttributeError(name)
        return ReadOnlyCollection(self._db[name])


def _oids(ids):
    return [ObjectId(i) for i in ids if ObjectId.is_valid(str(i))]


async def _tenants(ro) -> dict:
    """owner id (user or store) -> tenant key. Users: their organization, else themselves. Stores: their organization."""
    out = {}
    async for u in ro.users.find({}, {"_id": 1, "organization_id": 1}):
        out[str(u["_id"])] = f"org:{u['organization_id']}" if u.get("organization_id") else f"user:{u['_id']}"
    async for s in ro.stores.find({}, {"_id": 1, "organization_id": 1}):
        out.setdefault(str(s["_id"]), f"org:{s['organization_id']}" if s.get("organization_id") else f"store:{s['_id']}")
    return out


def _kind(loser: dict) -> str:
    return "manual_or_jessi_merge" if loser.get("status") == "merged" else "startup_consolidation"


def _relation(lt, wt, lo, wo) -> str:
    if lo and lo == wo:
        return "same_owner"
    if not lt or not wt:
        return "owner_unknown"
    if lt == wt:
        return "same_tenant_other_owner"
    if lt.startswith("org:") and wt.startswith("org:"):
        return "cross_organization"
    return "cross_tenant_individual_account"


async def run(db) -> dict:
    t0 = time.monotonic()
    ro = ReadOnlyDB(db)
    tenants = await _tenants(ro)
    capped = []

    losers = await ro.contacts.find({"merged_into": {"$exists": True, "$nin": [None, ""]}},
                                    {"_id": 1, "user_id": 1, "merged_into": 1, "merged_at": 1, "updated_at": 1, "status": 1}).to_list(CAP + 1)
    if len(losers) > CAP:
        capped.append("merged_contacts")
        losers = losers[:CAP]
    winners = {str(w["_id"]): str(w.get("user_id") or "") for w in
               await ro.contacts.find({"_id": {"$in": _oids({str(x["merged_into"]) for x in losers})}}, {"_id": 1, "user_id": 1}).to_list(CAP)}

    by_relation, by_kind, cross_months, cross_kind = Counter(), Counter(), Counter(), Counter()
    cross_pairs = []
    missing_winner = 0
    for x in losers:
        wid = str(x["merged_into"])
        if wid not in winners:
            missing_winner += 1
            continue
        lo, wo = str(x.get("user_id") or ""), winners[wid]
        rel = _relation(tenants.get(lo), tenants.get(wo), lo, wo)
        by_relation[rel] += 1
        by_kind[_kind(x)] += 1
        if rel.startswith("cross_"):
            cross_pairs.append((wid, lo, tenants.get(lo), tenants.get(wo)))
            cross_kind[_kind(x)] += 1
            when = x.get("merged_at") or x.get("updated_at")
            cross_months[when.strftime("%Y-%m") if hasattr(when, "strftime") else "unknown"] += 1

    # rows written by the loser's owner that now hang off the other tenant's contact
    children = {}
    if cross_pairs:
        pair_set = {(w, lo) for w, lo, _, _ in cross_pairs}
        wids = list({w for w, _, _, _ in cross_pairs})
        los = list({lo for _, lo, _, _ in cross_pairs})
        for coll in CHILD_COLLECTIONS:
            n = 0
            async for g in ro[coll].aggregate([{"$match": {"contact_id": {"$in": wids}, "user_id": {"$in": los}}},
                                               {"$group": {"_id": {"c": "$contact_id", "u": "$user_id"}, "n": {"$sum": 1}}}]):
                if (str(g["_id"].get("c")), str(g["_id"].get("u"))) in pair_set:
                    n += g["n"]
            children[coll] = n
        conv_ids = [str(c["_id"]) async for c in ro.conversations.find({"contact_id": {"$in": wids}, "user_id": {"$in": los}}, {"_id": 1})]
        children["messages_in_those_conversations"] = await ro.messages.count_documents({"conversation_id": {"$in": conv_ids}}) if conv_ids else 0

    # today's state, independent of merge markers: conversations whose owner's tenant differs from their contact's owner's tenant
    convs = await ro.conversations.find({"contact_id": {"$exists": True, "$nin": [None, ""]}}, {"_id": 0, "user_id": 1, "contact_id": 1}).to_list(CAP + 1)
    if len(convs) > CAP:
        capped.append("conversations")
        convs = convs[:CAP]
    c_owner = {}
    ids = list({str(c["contact_id"]) for c in convs})
    for i in range(0, len(ids), 5000):
        async for c in ro.contacts.find({"_id": {"$in": _oids(ids[i:i + 5000])}}, {"_id": 1, "user_id": 1}):
            c_owner[str(c["_id"])] = str(c.get("user_id") or "")
    conv_cross = 0
    conv_cross_tenants = set()
    for c in convs:
        ct, ut = tenants.get(c_owner.get(str(c["contact_id"]), "")), tenants.get(str(c.get("user_id") or ""))
        if ct and ut and ct != ut:
            conv_cross += 1
            conv_cross_tenants.update((ct, ut))

    out = {
        "read_only": True, "counts_only": True,
        "merged_contacts_scanned": len(losers), "merged_into_missing_contact": missing_winner,
        "merges_by_kind": dict(by_kind), "merges_by_owner_relation": dict(by_relation),
        "cross_tenant_merges": len(cross_pairs), "cross_tenant_merges_by_kind": dict(cross_kind),
        "cross_tenant_merges_by_month": dict(sorted(cross_months.items())),
        "tenants_involved_in_cross_merges": len({t for _, _, a, b in cross_pairs for t in (a, b)}),
        "contacts_receiving_cross_merges": len({w for w, _, _, _ in cross_pairs}),
        "rows_from_loser_owner_on_other_tenant_contact": children,
        "conversations_scanned": len(convs), "conversations_owner_tenant_differs_from_contact_tenant": conv_cross,
        "tenants_involved_in_cross_conversations": len(conv_cross_tenants),
        "startup_consolidation_runs_recorded": 0, "startup_consolidation_last_run_month": None,
        "caps_hit": capped, "seconds": round(time.monotonic() - t0, 1),
    }
    lease = await ro.job_leases.find({"_id": "startup:consolidate_phone_contacts"}, {"_id": 0, "runs": 1, "claimed_at": 1}).to_list(1)
    if lease:
        out["startup_consolidation_runs_recorded"] = int(lease[0].get("runs") or 0)
        at = lease[0].get("claimed_at")
        out["startup_consolidation_last_run_month"] = at.strftime("%Y-%m") if hasattr(at, "strftime") else None
    logger.info(f"[MergeAssessment] done in {out['seconds']} s: {len(losers)} merged, {len(cross_pairs)} cross-tenant")
    return out
