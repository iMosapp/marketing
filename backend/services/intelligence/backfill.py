"""Backfill: read-only inventory + dry run now (Phase 1A); batched, checkpointed, idempotent execute later (Phase 1B, gated by INTEL_BACKFILL_EXECUTE and an explicit confirm).
Legacy data never outranks newer verified facts: imported facts carry confidence medium, source import, and go through the same status engine."""
import json
import logging
import time
from collections import Counter
from datetime import timedelta
from typing import Optional

from bson import ObjectId

from services.intelligence import config, ingest, projection, state
from services.intelligence import facts as F
from services.intelligence import intent as I

logger = logging.getLogger(__name__)
RUNS = "intel_backfill_runs"
FIELDS = {"_id": 1, "user_id": 1, "store_id": 1, "first_name": 1, "last_name": 1, "purchase_history": 1, "personal_details": 1, "vehicle_interest": 1, "vehicle": 1,
          "hot_opportunity": 1, "hot_score": 1, "hot_last_at": 1, "created_at": 1, "updated_at": 1, "last_activity_at": 1, "status": 1, "occupation": 1, "employer": 1, "intel_projected_at": 1}
ACTIVE_LEGACY_DAYS = 60


def _pd_details(c: dict, titles: list) -> dict:
    pd = dict(c.get("personal_details") or {})
    for k in ("occupation", "employer"):
        if c.get(k) and not pd.get(k):
            pd[k] = c[k]
    # the mirror's vehicle_purchased is kept only when no sale record names that vehicle (the sale is the better source); it stays unconfirmed, never erased
    vp = str(pd.get("vehicle_purchased") or "").strip()
    if not vp or any(I.matches(vp, t) for t in titles):
        pd.pop("vehicle_purchased", None)
    return {k: v for k, v in pd.items() if k in ingest.MAP}


async def plan_contact(db, c: dict, settings: dict, now=None) -> list:
    now = now or F.now_utc()
    cid = str(c["_id"])
    facts = ingest.plan_purchases(c, c.get("purchase_history") or [])
    titles = [f["value"]["label"] for f in facts if f["key"] == "vehicle.purchase"]
    anchor = ingest._ts(c.get("updated_at")) or ingest._ts(c.get("created_at")) or now
    # legacy fields are imported once: after the projection has written them they are a view of the facts, not evidence
    legacy_ok = not c.get("intel_projected_at")
    if legacy_ok:
        facts += ingest.plan_extraction(c, _pd_details(c, titles), source_kind="import", source_ref="legacy:personal_details", occurred_at=anchor, recorded_at=anchor, precision="unknown", confidence="medium")
    vi = (c.get("vehicle_interest") or "").strip()
    if legacy_ok and vi and not any(I.matches(vi, t) for t in titles):
        at = ingest._ts(c.get("last_activity_at")) or anchor
        f = I.make(c, settings, key="vehicle.interest", domain="vehicle_interest", statement=f"Interested in {vi} (legacy field)", value={"label": vi}, occurred_at=at, recorded_at=anchor, precision="unknown",
                   source={"kind": "import", "ref": "legacy:vehicle_interest"}, confidence="medium")
        if (now - at).days > ACTIVE_LEGACY_DAYS:
            f.update({"status": "historical", "outcome": "went_quiet"})
        facts.append(f)
    async for lead in db.inbound_leads.find({"contact_id": cid}, {"vehicle_interest": 1, "vehicle_raw": 1, "comments": 1, "inquiry": 1, "source_name": 1, "received_at": 1, "created_at": 1, "conversation_id": 1}).sort("received_at", 1):
        f = ingest.plan_lead(c, lead, settings)
        if f:
            if (now - f["occurred_at"]).days > I.window_days(settings, f.get("category")):
                f.update({"status": "historical", "outcome": "went_quiet"})
            facts.append(f)
    hot_at = ingest._ts(c.get("hot_last_at"))
    if legacy_ok and c.get("hot_opportunity") and hot_at:
        f = I.make(c, settings, key="buying.signal", domain="buying_status", statement=f"Hot lead (score {c.get('hot_score') or '?'}/10, legacy flag)", value={"label": "hot lead", "score": c.get("hot_score")},
                   occurred_at=hot_at, recorded_at=hot_at, source={"kind": "import", "ref": "legacy:hot_opportunity"}, confidence="medium")
        if (now - hot_at).days > settings["intent_window_days"]:
            f.update({"status": "historical", "outcome": "went_quiet"})
        facts.append(f)
    try:
        from services.appraisals.core import V
        async for v in db[V].find({"contact_id": cid, "deleted": {"$ne": True}}, {"year": 1, "make": 1, "model": 1, "trim": 1, "vin": 1, "ownership_status": 1, "ownership_updated_at": 1, "ownership_updated_by": 1, "ownership_updated_by_name": 1, "created_at": 1}):
            label = " ".join(str(v.get(k) or "") for k in ("year", "make", "model", "trim")).strip() or (v.get("vin") or "vehicle")
            st = v.get("ownership_status") or "unknown"
            at = ingest._ts(v.get("ownership_updated_at")) or ingest._ts(v.get("created_at")) or anchor
            # a person set the status on the vehicle page -> verified; the default "owns" written when an appraisal is opened is only a system record
            actor = {"_id": v["ownership_updated_by"], "name": v.get("ownership_updated_by_name") or "rep"} if v.get("ownership_updated_by") else None
            src = {"kind": "appraisal", "ref": str(v["_id"])}
            if st == "owns" and not any(I.matches(label, t) for t in titles):
                facts.append(F.make(c, layer="state", domain="vehicle_owned", key="vehicle.owned", statement=f"Owns {label}" + ("" if actor else " (per appraisal record, not confirmed)"), value={"label": label},
                                    occurred_at=at, source=src, confidence="high" if actor else "medium", actor=actor, recorded_at=at))
            elif st in ("traded", "sold", "no_longer_owns"):
                facts.append(F.make(c, layer="history", domain="vehicle_owned", key="vehicle.disposed", statement=f"{label}: {st.replace('_', ' ')}", value={"label": label, "status": st}, occurred_at=at, source=src,
                                    confidence="high" if actor else "medium", actor=actor, recorded_at=at))
    except Exception as e:  # noqa: BLE001 - the appraisal module is optional for the plan
        logger.debug("[Backfill] vehicles skipped: %s", e)
    return facts


def _contacts_q(store_id: Optional[str]) -> dict:
    q: dict = {"status": {"$nin": ["merged", "purged"]}}
    if store_id:
        q["store_id"] = store_id
    return q


async def dry_run(db, *, store_id: Optional[str] = None, limit: Optional[int] = None, sample: int = 8, persist: bool = False) -> dict:
    """Read-only: counts what the backfill would write and how the legacy projection would differ from today's fields. Writes nothing unless persist=True (then the report is kept in intel_backfill_runs)."""
    now = F.now_utc()
    t0 = time.monotonic()
    settings_cache: dict = {}
    by_layer, by_key, by_status, by_source, by_store = Counter(), Counter(), Counter(), Counter(), {}
    scanned = with_facts = total = distinct = conflicts = projection_changes = 0
    samples, changed_fields = [], Counter()
    cur = db.contacts.find(_contacts_q(store_id), FIELDS).sort("_id", 1)
    if limit:
        cur = cur.limit(int(limit))
    async for c in cur:
        scanned += 1
        sid = str(c.get("store_id") or "")
        if sid not in settings_cache:
            settings_cache[sid] = await config.settings(db, sid or None)
        st_row = by_store.setdefault(sid or "(no store)", {"contacts": 0, "with_facts": 0, "facts_distinct": 0, "legacy_changes": 0})
        st_row["contacts"] += 1
        facts = await plan_contact(db, c, settings_cache[sid], now)
        if not facts:
            continue
        with_facts += 1
        st_row["with_facts"] += 1
        total += len(facts)
        seen: dict = {}
        distinct_here: set = set()
        for f in facts:
            distinct_here.add((f["key"], F.norm_value(f["value"])))
            by_layer[f["layer"]] += 1
            by_key[f["key"]] += 1
            by_status[f["status"]] += 1
            by_source[f["source"]["kind"]] += 1
            if f["key"] in F.SCALAR_KEYS and f["status"] == "current":
                seen.setdefault(f["key"], set()).add(F.norm_value(f["value"]))
        conflicts += sum(1 for v in seen.values() if len(v) > 1)
        distinct += len(distinct_here)
        st_row["facts_distinct"] += len(distinct_here)
        fake_state = _state_from_plan(c, facts, settings_cache[sid], now)
        sets = projection.plan(fake_state)
        diff = {k: v for k, v in sets.items() if _raw(_legacy_get(c, k)) != _raw(v)}
        if diff:
            projection_changes += 1
            st_row["legacy_changes"] += 1
            changed_fields.update(diff.keys())
        if len(samples) < sample:
            samples.append({"contact_id": str(c["_id"]), "name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip(), "facts": [{"key": f["key"], "status": f["status"], "occurred_at": F.iso(f["occurred_at"]), "statement": f["statement"][:100], "source": f["source"]["kind"]} for f in facts[:12]],
                            "projection_diff": {k: (str(_legacy_get(c, k))[:60], str(v)[:60]) for k, v in list(diff.items())[:6]}})
    report = {"contacts_scanned": scanned, "contacts_with_facts": with_facts, "facts_total": total, "facts_distinct": distinct, "repeat_evidence": total - distinct, "by_layer": dict(by_layer), "by_key": dict(by_key.most_common()), "by_status": dict(by_status),
              "by_source": dict(by_source), "scalar_conflicts": conflicts, "contacts_whose_legacy_fields_would_change": projection_changes, "legacy_fields_changed": dict(changed_fields.most_common()),
              "by_store": by_store, "existing_facts": await db[F.FACTS].count_documents({}), "samples": samples, "flags": config.flags(), "intent_window_days": config.DEFAULTS["intent_window_days"], "active_legacy_days": ACTIVE_LEGACY_DAYS,
              "processing_ms": int((time.monotonic() - t0) * 1000), "read_only": not persist, "writes_performed": ["intel_backfill_runs report"] if persist else []}
    rid = None
    if persist:
        rid = (await db[RUNS].insert_one({"mode": "dry_run", "store_id": store_id, "limit": limit, "started_at": now, "finished_at": F.now_utc(), "report": report})).inserted_id
    return {"run_id": str(rid) if rid else None, **report}


def _raw(v) -> str:
    """Exact-shape comparison (a list of strings vs a list of dicts is a change even when the labels match)."""
    return json.dumps(v, sort_keys=True, default=str)


def _legacy_get(c: dict, dotted: str):
    cur = c
    for part in dotted.split("."):
        cur = (cur or {}).get(part) if isinstance(cur, dict) else None
    return cur


def _state_from_plan(c: dict, facts: list, settings: dict, now) -> dict:
    """Shape the planned facts like state.build output so projection.plan can be reused without writing anything."""
    pub = [{**F.pub({**f, "_id": ObjectId()}), "label": (f["value"] or {}).get("label") if isinstance(f.get("value"), dict) else f["statement"]} for f in facts]
    intents = [{**p, **(I.phase({**f, "_id": None}, settings, now) or {})} for p, f in zip(pub, facts) if f["layer"] == "intent" and f["status"] == "current" and f["key"] != "buying.status"]
    intents.sort(key=lambda x: (x.get("last_signal_at") or x["occurred_at"], x["occurred_at"], x["recorded_at"]), reverse=True)
    return {"identity": [p for p, f in zip(pub, facts) if f["layer"] == "identity" and f["status"] == "current"], "current_state": [p for p, f in zip(pub, facts) if f["layer"] == "state" and f["status"] == "current"],
            "history": [], "active_intent": intents, "driving": intents[0] if intents and intents[0].get("phase") != "dormant" else None}


async def execute(db, *, confirm: str = "", store_id: Optional[str] = None, batch: int = 200, run_id: Optional[str] = None) -> dict:
    """Phase 1B only. Needs INTEL_BACKFILL_EXECUTE=true and confirm == "EXECUTE". Resumable: the run doc keeps the last contact id written."""
    if not config.backfill_execute_enabled() or confirm != "EXECUTE":
        raise PermissionError("Backfill execution is not enabled (Phase 1B needs INTEL_BACKFILL_EXECUTE=true and confirm=EXECUTE)")
    await F.ensure_indexes(db)
    now = F.now_utc()
    run = await db[RUNS].find_one({"_id": ObjectId(run_id)}) if run_id and ObjectId.is_valid(run_id) else None
    if not run:
        run = {"mode": "execute", "store_id": store_id, "started_at": now, "checkpoint": None, "written": 0, "reaffirmed": 0, "duplicates": 0, "contacts": 0, "finished_at": None}
        run["_id"] = (await db[RUNS].insert_one(run)).inserted_id
    q = _contacts_q(store_id)
    if run.get("checkpoint"):
        q["_id"] = {"$gt": ObjectId(run["checkpoint"])}
    settings_cache: dict = {}
    written = contacts = reaff = dups = 0
    async for c in db.contacts.find(q, FIELDS).sort("_id", 1).limit(int(batch)):
        sid = str(c.get("store_id") or "")
        if sid not in settings_cache:
            settings_cache[sid] = await config.settings(db, sid or None)
        res = await ingest.apply(db, await plan_contact(db, c, settings_cache[sid], now), sync=False)
        written += res["created"] + res["superseded"] + res["disputed"] + res["historical"]
        reaff += res["reaffirmed"]
        dups += res["duplicate"]
        contacts += 1
        if config.projection_enabled():
            await projection.project(db, c)
        await db[RUNS].update_one({"_id": run["_id"]}, {"$set": {"checkpoint": str(c["_id"])}, "$inc": {"written": written, "reaffirmed": reaff, "duplicates": dups, "contacts": 1}})
        written = reaff = dups = 0
    done = contacts < int(batch)
    if done:
        await db[RUNS].update_one({"_id": run["_id"]}, {"$set": {"finished_at": F.now_utc()}})
    r = await db[RUNS].find_one({"_id": run["_id"]})
    return {"run_id": str(run["_id"]), "contacts_this_batch": contacts, "contacts_total": r.get("contacts", 0), "facts_written_total": r.get("written", 0), "reaffirmed_total": r.get("reaffirmed", 0),
            "duplicates_total": r.get("duplicates", 0), "projection": config.projection_enabled(), "done": done, "checkpoint": r.get("checkpoint")}


async def runs(db, limit: int = 20) -> list:
    rows = await db[RUNS].find({}, {"report.samples": 0}).sort("started_at", -1).limit(limit).to_list(limit)
    return [{**r, "id": str(r["_id"]), "_id": None, "started_at": F.iso(r.get("started_at")), "finished_at": F.iso(r.get("finished_at"))} for r in rows]


def since(days: int):
    return F.now_utc() - timedelta(days=days)
