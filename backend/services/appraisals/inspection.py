"""AI Vehicle Inspection (MVP2). One pipeline for every photo and video on an appraisal, whoever supplied it:
media -> frames (video: extract, score, dedupe; photo: itself) -> Jessi classifies the area and lists visible issues
-> coverage, findings with evidence that points back to the original file and timestamp -> human confirm / dismiss / edit / add
-> condition report with an explained grade the manager can override. Nothing here needs the uploader to be a logged-in rep."""
import asyncio
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId

from services.appraisals import frames as fx
from services.appraisals.providers import vehicle_label
from services.contact_files import _for_vision, _parse_json
from services.llm_models import VISION_MODEL
from utils.image_storage import get_object, put_object

logger = logging.getLogger(__name__)

INS, FR, FD, M, A, ACT = "appraisal_inspections", "appraisal_frames", "appraisal_findings", "appraisal_media", "vehicle_appraisals", "appraisal_activity"
INSPECT_ROLES = ("exterior", "interior", "photo", "walkaround_video", "other", "odometer_photo")

AREAS = {"front": "Front", "driver_front": "Driver Front", "driver_side": "Driver Side", "driver_rear": "Driver Rear", "rear": "Rear", "passenger_rear": "Passenger Rear",
         "passenger_side": "Passenger Side", "passenger_front": "Passenger Front", "wheels": "Wheels", "windshield": "Windshield", "interior": "Interior",
         "dashboard": "Dashboard", "seats": "Seats"}
EXTERIOR = ["front", "driver_front", "driver_side", "driver_rear", "rear", "passenger_rear", "passenger_side", "passenger_front"]
GROUPS = {"exterior": EXTERIOR, "wheels": ["wheels"], "glass": ["windshield"], "interior": ["interior", "dashboard", "seats"]}
GROUP_LABELS = {"exterior": "Exterior", "wheels": "Wheels", "glass": "Glass", "interior": "Interior"}

CATEGORIES = {"body": "Body", "glass": "Glass", "wheels_tires": "Wheels / Tires", "interior": "Interior", "mechanical": "Mechanical"}
SUBTYPES = {"body": {"dent": "Dent", "scratch": "Scratches", "paint_damage": "Paint Damage", "bumper_damage": "Bumper Damage", "rust": "Rust", "broken_trim": "Broken Trim",
                     "mismatched_panel": "Mismatched Panel", "other": "Other Body Issue"},
            "glass": {"windshield_chip": "Windshield Chip", "windshield_crack": "Windshield Crack", "damaged_glass": "Damaged Glass", "other": "Other Glass Issue"},
            "wheels_tires": {"curb_rash": "Curb Rash", "wheel_damage": "Wheel Damage", "tire_wear": "Tire Wear", "tire_damage": "Tire Damage", "other": "Other Wheel/Tire Issue"},
            "interior": {"seat_damage": "Seat Damage", "stain": "Stain", "excessive_wear": "Excessive Wear", "damaged_trim": "Damaged Trim", "warning_light": "Dashboard Warning Light",
                         "odor": "Odor", "other": "Other Interior Issue"},
            # Mechanical issues are heard, not seen: they come from voice notes (rep or customer) or are added by hand, never from photos.
            "mechanical": {"ac_heat": "AC / Heat", "engine": "Engine", "transmission": "Transmission", "brakes": "Brakes", "suspension_steering": "Suspension / Steering",
                           "electrical": "Electrical", "noise_vibration": "Noise / Vibration", "fluid_leak": "Fluid Leak", "exhaust": "Exhaust", "check_engine_light": "Check Engine Light",
                           "other": "Other Mechanical Issue"}}
FRAMES_WAIT_S = 240  # how long a run waits for an upload-time extraction that is still working before extracting itself
SEVERITIES = {"minor": "Minor", "moderate": "Moderate", "major": "Major"}
CONFIDENCES = ("high", "medium", "low")
GRADES = {"very_good": "Very Good", "good": "Good", "fair": "Fair", "poor": "Poor"}
POINTS = {"minor": 1, "moderate": 2, "major": 4}
BATCH = 6
RUN_STALE = timedelta(minutes=15)


def _now():
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt


def _oid(s) -> Optional[ObjectId]:
    return ObjectId(s) if s and ObjectId.is_valid(str(s)) else None


def _name(u: dict) -> str:
    return (u.get("name") or f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip() or u.get("email") or "").strip()


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")[:60]


def _title(s: str) -> str:
    return " ".join(w.capitalize() for w in (s or "").replace("_", " ").split())


# ---------- Jessi (swappable so tests and the future customer link reuse everything else) ----------
SYSTEM = ("You are Jessi, a used-vehicle inspector helping a dealership appraiser. You receive numbered photos of ONE vehicle ({label}); some are frames from a walkaround "
          "video, some are individual photos. 1) For EVERY image say which part of the vehicle it mainly shows and whether it is usable (sharp, vehicle visible). "
          "2) List every VISIBLE condition issue. Reply with JSON only:\n"
          "{{\"frames\":[{{\"i\":1,\"areas\":[\"<primary area>\",\"<other clearly shown areas>\"],\"usable\":true}}],"
          "\"findings\":[{{\"images\":[1,3],\"category\":\"body|glass|wheels_tires|interior\",\"subtype\":\"<see list>\",\"location\":\"<snake_case e.g. passenger_rear_door, driver_front_wheel, rear_bumper, windshield, driver_seat>\","
          "\"location_label\":\"Passenger Rear Door\",\"severity\":\"minor|moderate|major\",\"confidence\":\"high|medium|low\",\"explanation\":\"one sentence: what you see and why you think so\"}}],"
          "\"impression\":\"one sentence overall\"}}\n"
          "Areas: front, driver_front, driver_side, driver_rear, rear, passenger_rear, passenger_side, passenger_front, wheels, windshield, interior, dashboard, seats, unknown.\n"
          "Subtypes - body: dent, scratch, paint_damage, bumper_damage, rust, broken_trim, mismatched_panel, other. glass: windshield_chip, windshield_crack, damaged_glass, other. "
          "wheels_tires: curb_rash, wheel_damage, tire_wear, tire_damage, other. interior: seat_damage, stain, excessive_wear, damaged_trim, warning_light (a lit dashboard warning lamp), other.\n"
          "Rules: report only what is visible; never estimate repair costs; reflections, shadows, dirt, water drops and dealer stickers are NOT damage - when unsure say confidence low; "
          "one finding per distinct issue, the same issue seen in several images is ONE finding listing all those images; a wheel close-up belongs to area wheels.")


async def vision_analyze(label: str, items: list) -> dict:
    """items: [{'i': 1, 'jpeg': bytes}] -> parsed JSON from the vision model."""
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise RuntimeError("Vision is not configured (EMERGENT_LLM_KEY missing)")
    from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
    chat = LlmChat(api_key=api_key, session_id=f"insp_{uuid.uuid4().hex[:8]}", system_message=SYSTEM.format(label=label or "a used vehicle")).with_model(*VISION_MODEL)
    text = "Images in order: " + ", ".join(f"Image {it['i']}" for it in items) + ". Classify every image and list visible issues."
    out = await asyncio.wait_for(chat.send_message(UserMessage(text=text, file_contents=[ImageContent(image_base64=_for_vision(it["jpeg"])) for it in items])), timeout=180)
    parsed = _parse_json(out)
    if not isinstance(parsed, dict) or "frames" not in parsed:
        raise RuntimeError("Jessi returned something I could not read")
    return parsed


ANALYZER = vision_analyze


# ---------- serializers ----------
def _img(p: Optional[str]) -> Optional[str]:
    return f"/api/images/{p}" if p else None


def public_frame(f: dict) -> dict:
    return {"id": str(f["_id"]), "media_id": f.get("media_id"), "media_name": f.get("media_name"), "media_kind": f.get("media_kind"), "media_source": f.get("media_source"),
            "timestamp_s": f.get("timestamp_s"), "timestamp_label": f.get("timestamp_label"), "areas": f.get("areas") or [], "usable": f.get("usable"),
            "sharpness": f.get("sharpness"), "url": _img(f.get("path")), "thumb_url": _img(f.get("thumb_path")), "created_at": f.get("created_at")}


def public_finding(d: dict, frames_by_id: dict) -> dict:
    ev = []
    for e in d.get("evidence") or []:
        f = frames_by_id.get(e.get("frame_id"))
        if f and not f.get("deleted"):
            ev.append({**e, "url": _img(f.get("path")), "thumb_url": _img(f.get("thumb_path")), "areas": f.get("areas") or []})
    cat, sub = d.get("category"), d.get("subtype")
    return {"id": str(d["_id"]), "category": cat, "category_label": CATEGORIES.get(cat, _title(cat)), "subtype": sub, "subtype_label": SUBTYPES.get(cat, {}).get(sub) or _title(sub),
            "location": d.get("location"), "location_label": d.get("location_label") or _title(d.get("location")), "severity": d.get("severity"), "severity_label": SEVERITIES.get(d.get("severity"), ""),
            "confidence": d.get("confidence"), "possible": d.get("confidence") == "low" and d.get("decision") == "pending", "explanation": d.get("explanation") or "",
            "origin": d.get("origin"), "decision": d.get("decision"), "decision_by_name": d.get("decision_by_name"), "decision_at": d.get("decision_at"),
            "voice_note_id": d.get("voice_note_id"), "spoken_by": d.get("spoken_by"), "quote": d.get("quote"),
            "recon_cost": d.get("recon_cost"), "recon_by_name": d.get("recon_by_name"), "recon_at": d.get("recon_at"),
            "edited": bool(d.get("edited")), "edited_by_name": d.get("edited_by_name"), "edited_at": d.get("edited_at"), "ai_original": d.get("ai_original"),
            "sources": sorted({e.get("media_source") for e in ev if e.get("media_source")}), "evidence": ev, "created_at": d.get("created_at"), "updated_at": d.get("updated_at")}


# ---------- lookups ----------
async def get_or_create(db, appr: dict) -> dict:
    ins = await db[INS].find_one({"appraisal_id": str(appr["_id"])})
    if ins:
        return ins
    now = _now()
    doc = {"_id": ObjectId(), "appraisal_id": str(appr["_id"]), "contact_id": appr.get("contact_id"), "vehicle_id": appr.get("vehicle_id"), "user_id": appr["user_id"],
           "store_id": appr.get("store_id"), "organization_id": appr.get("organization_id"), "status": "idle", "stage": None, "run_count": 0, "run_id": None, "last_error": None,
           "processed_media_ids": [], "coverage": None, "ai_overall": None, "ai_categories": None, "ai_reason": None, "ai_impression": None, "final_overall": None,
           "final_categories": None, "final_reason": None, "override": None, "prev_status": None, "started_at": None, "finished_at": None, "created_at": now, "updated_at": now}
    await db[INS].insert_one(doc)
    return doc


async def frames_for(db, ins: dict) -> list:
    return await db[FR].find({"inspection_id": str(ins["_id"]), "deleted": {"$ne": True}}).sort([("media_id", 1), ("timestamp_s", 1)]).to_list(500)


async def findings_for(db, ins: dict) -> list:
    return await db[FD].find({"inspection_id": str(ins["_id"]), "deleted": {"$ne": True}}).sort("created_at", 1).to_list(300)


async def _audit(db, appr: dict, actor: dict, action: str, detail: str = "", meta: Optional[dict] = None):
    await db[ACT].insert_one({"appraisal_id": str(appr["_id"]), "contact_id": appr.get("contact_id"), "store_id": appr.get("store_id"), "actor_id": str(actor.get("_id")),
                              "actor_name": _name(actor), "action": action, "detail": detail[:500], "from_status": None, "to_status": None, "meta": meta or {}, "created_at": _now()})


# ---------- run ----------
async def start_run(db, appr: dict, me: dict, background: bool = True) -> dict:
    ins = await get_or_create(db, appr)
    if ins.get("status") in ("queued", "processing") and ins.get("started_at") and _now() - _aware(ins["started_at"]) < RUN_STALE:
        raise ValueError("Jessi is already inspecting this vehicle")
    media = await db[M].find({"appraisal_id": str(appr["_id"]), "deleted": {"$ne": True}, "role": {"$in": list(INSPECT_ROLES)}}).to_list(200)
    if not media:
        raise ValueError("Add a walkaround video or some photos first")
    now = _now()
    run_id = uuid.uuid4().hex[:10]
    prev = appr.get("status") if appr.get("status") not in ("analyzing",) else (ins.get("prev_status") or "draft")
    await db[INS].update_one({"_id": ins["_id"]}, {"$set": {"status": "queued", "stage": "queued", "run_id": run_id, "last_error": None, "started_at": now, "finished_at": None,
                                                          "prev_status": prev, "updated_at": now}, "$inc": {"run_count": 1}})
    await db[A].update_one({"_id": appr["_id"]}, {"$set": {"status": "analyzing", "updated_at": now}})
    await _audit(db, appr, me, "inspection_started", f"{len(media)} file(s) · run {ins.get('run_count', 0) + 1}", {"run_id": run_id})
    if background:
        asyncio.create_task(run(db, str(ins["_id"]), me))
    else:
        await run(db, str(ins["_id"]), me)
    return await db[INS].find_one({"_id": ins["_id"]})


async def _stage(db, ins_id: ObjectId, stage: str, **extra):
    await db[INS].update_one({"_id": ins_id}, {"$set": {"stage": stage, "status": "processing", "updated_at": _now(), **extra}})


def _frame_doc(ins: dict, m: dict, *, path: str, thumb_path: Optional[str], t: Optional[float], label: Optional[str], sharp: Optional[float]) -> dict:
    return {"_id": ObjectId(), "inspection_id": str(ins["_id"]), "appraisal_id": ins["appraisal_id"], "user_id": ins["user_id"], "store_id": ins.get("store_id"),
            "media_id": str(m["_id"]), "media_name": m.get("name"), "media_kind": m.get("kind"), "media_source": m.get("source"), "media_uploaded_by": m.get("uploaded_by"),
            "timestamp_s": t, "timestamp_label": label, "path": path, "thumb_path": thumb_path, "sharpness": sharp, "areas": [], "usable": None, "created_at": _now()}


async def _extract_media(db, ins: dict, m: dict) -> int:
    """Video -> stored stills with timestamps; photo -> one frame that IS the photo. Provenance is copied onto every frame."""
    if m.get("kind") == "video":
        if not m.get("path") or m.get("original_available") is False:
            raise ValueError(f"The original of {m.get('name')} is no longer available to extract frames from")
        data, _ = await asyncio.to_thread(get_object, m["path"])
        res = await asyncio.to_thread(fx.extract, data, m["path"].rsplit(".", 1)[-1])
        docs = []
        for i, c in enumerate(res["frames"]):
            base = f"appraisals/{ins['user_id']}/{ins['appraisal_id']}/frames/{m['_id']}_{i:02d}"
            await asyncio.to_thread(put_object, f"{base}.jpg", c["jpeg"], "image/jpeg")
            await asyncio.to_thread(put_object, f"{base}_thumb.jpg", fx.thumb(c["jpeg"]), "image/jpeg")
            docs.append(_frame_doc(ins, m, path=f"{base}.jpg", thumb_path=f"{base}_thumb.jpg", t=round(c["t"], 2), label=c["label"], sharp=round(c["sharpness"], 1)))
        if docs:
            await db[FR].insert_many(docs)
        await db[M].update_one({"_id": m["_id"]}, {"$set": {"frame_count": len(docs), "video_quality": res["quality"], "duration": res["duration"],
                                                          "extraction": {k: res[k] for k in ("candidates", "sharp", "blurry_dropped", "duplicates_removed", "fps")}, "frames_extracted_at": _now()}})
        return len(docs)
    data, _ = await asyncio.to_thread(get_object, m["path"])
    sharp = await asyncio.to_thread(fx.sharpness, data)
    await db[FR].insert_one(_frame_doc(ins, m, path=m["path"], thumb_path=m.get("thumb_path"), t=None, label=None, sharp=round(sharp, 1)))
    await db[M].update_one({"_id": m["_id"]}, {"$set": {"frame_count": 1, "frames_extracted_at": _now()}})
    return 1


async def extract_frames(db, appr: dict, m: dict, actor: Optional[dict] = None, force: bool = False) -> int:
    """Upload time: pull the snapshots out of a walkaround video right away so they sit on the appraisal before anyone taps Analyze.
    The run reuses them. Failure is written on the media (frames_error) and never blocks the upload."""
    if m.get("kind") != "video":
        return 0
    fresh = await db[M].find_one({"_id": m["_id"], "deleted": {"$ne": True}})
    if not fresh or (fresh.get("frames_extracted_at") and not force):
        return int((fresh or {}).get("frame_count") or 0)
    if force:
        await db[FR].update_many({"media_id": str(m["_id"])}, {"$set": {"deleted": True, "deleted_at": _now()}})
        await db[INS].update_one({"appraisal_id": str(appr["_id"])}, {"$pull": {"processed_media_ids": str(m["_id"])}})
    await db[M].update_one({"_id": m["_id"]}, {"$set": {"frames_started_at": _now(), "frames_error": None}, "$unset": {"frames_extracted_at": ""}})
    ins = await get_or_create(db, appr)
    try:
        n = await _extract_media(db, ins, {**fresh, "frames_extracted_at": None})
        await _audit(db, appr, actor or {"_id": fresh.get("uploaded_by"), "name": fresh.get("uploaded_by_name")}, "snapshots_extracted",
                     f"{n} snapshot{'s' if n != 1 else ''} pulled from {fresh.get('name')}", {"media_id": str(m["_id"]), "count": n})
        return n
    except Exception as e:  # noqa: BLE001
        logger.error(f"[Inspection] snapshot extraction failed for {m['_id']}: {e}")
        await db[M].update_one({"_id": m["_id"]}, {"$set": {"frames_error": str(e)[:200], "frame_count": 0}})
        return 0


async def _ensure_frames(db, ins: dict, m: dict) -> int:
    """A run never extracts twice: frames already pulled at upload are reused, an extraction still working is waited for, anything else is extracted now."""
    deadline = _now() + timedelta(seconds=FRAMES_WAIT_S)
    cur = m
    while True:
        if cur.get("frames_extracted_at"):
            have = await db[FR].count_documents({"media_id": str(m["_id"]), "deleted": {"$ne": True}})
            if have:
                return have
            break
        started = _aware(cur.get("frames_started_at"))
        if not started or cur.get("frames_error") or _now() - started > timedelta(minutes=15) or _now() > deadline:
            break
        await asyncio.sleep(2)
        cur = await db[M].find_one({"_id": m["_id"]}) or cur
    await db[FR].update_many({"media_id": str(m["_id"]), "deleted": {"$ne": True}}, {"$set": {"deleted": True, "deleted_at": _now()}})
    await db[M].update_one({"_id": m["_id"]}, {"$set": {"frames_started_at": _now(), "frames_error": None}})
    return await _extract_media(db, ins, cur)


def _norm_finding(raw: dict, idx_to_frame: dict) -> Optional[dict]:
    cat = str(raw.get("category") or "").lower().strip()
    if cat not in CATEGORIES:
        return None
    sub = _slug(str(raw.get("subtype") or "other"))
    if sub not in SUBTYPES[cat]:
        sub = "other"
    sev = str(raw.get("severity") or "minor").lower()
    sev = sev if sev in SEVERITIES else "minor"
    conf = str(raw.get("confidence") or "low").lower()
    conf = conf if conf in CONFIDENCES else "low"
    loc = _slug(str(raw.get("location") or raw.get("location_label") or "unspecified")) or "unspecified"
    frs = [idx_to_frame[i] for i in (raw.get("images") or []) if i in idx_to_frame]
    return {"category": cat, "subtype": sub, "location": loc, "location_label": (str(raw.get("location_label") or "").strip() or _title(loc))[:80], "severity": sev,
            "confidence": conf, "explanation": str(raw.get("explanation") or "").strip()[:600], "frames": frs}


def _evidence(f: dict) -> dict:
    return {"frame_id": str(f["_id"]), "media_id": f.get("media_id"), "media_name": f.get("media_name"), "media_kind": f.get("media_kind"), "media_source": f.get("media_source"),
            "timestamp_s": f.get("timestamp_s"), "timestamp_label": f.get("timestamp_label")}


def _rank(order: tuple, value: str) -> int:
    return order.index(value) if value in order else 0


async def _analyze(db, ins: dict, appr: dict, frames: list) -> tuple:
    """Batches of frames through Jessi -> (merged findings by fingerprint, impressions). Also writes area/usable onto each frame."""
    label = vehicle_label(appr.get("vehicle") or {}) if appr.get("vehicle") else "a used vehicle"
    merged: dict = {}
    impressions = []
    for start in range(0, len(frames), BATCH):
        batch = frames[start:start + BATCH]
        items = []
        for n, f in enumerate(batch, 1):
            data, _ = await asyncio.to_thread(get_object, f["path"])
            items.append({"i": n, "jpeg": data})
        res = await ANALYZER(label, items)
        idx = {n: f for n, f in enumerate(batch, 1)}
        for fr in res.get("frames") or []:
            f = idx.get(fr.get("i")) if isinstance(fr, dict) else None
            if not f:
                continue
            areas = [a for a in (fr.get("areas") or ([fr["area"]] if fr.get("area") else [])) if a in AREAS]
            await db[FR].update_one({"_id": f["_id"]}, {"$set": {"areas": areas, "usable": bool(fr.get("usable", True)), "analyzed_at": _now()}})
            f["areas"], f["usable"] = areas, bool(fr.get("usable", True))
        for raw in res.get("findings") or []:
            nf = _norm_finding(raw, idx) if isinstance(raw, dict) else None
            if not nf:
                continue
            key = f"{nf['category']}|{nf['subtype']}|{nf['location']}"
            cur = merged.get(key)
            if not cur:
                merged[key] = nf
            else:
                cur["frames"] = cur["frames"] + [f for f in nf["frames"] if f["_id"] not in {x["_id"] for x in cur["frames"]}]
                if _rank(("minor", "moderate", "major"), nf["severity"]) > _rank(("minor", "moderate", "major"), cur["severity"]):
                    cur["severity"] = nf["severity"]
                if _rank(("low", "medium", "high"), nf["confidence"]) > _rank(("low", "medium", "high"), cur["confidence"]):
                    cur["confidence"], cur["explanation"] = nf["confidence"], nf["explanation"] or cur["explanation"]
        if res.get("impression"):
            impressions.append(str(res["impression"]).strip())
    return merged, impressions


async def _upsert_findings(db, ins: dict, merged: dict, run_id: str) -> dict:
    """Same issue seen again (retry, or a re-run after more media) updates the existing record; a human decision is never overwritten."""
    created = updated = kept = 0
    now = _now()
    for key, nf in merged.items():
        ev = [_evidence(f) for f in nf["frames"]]
        existing = await db[FD].find_one({"inspection_id": str(ins["_id"]), "fingerprint": key, "origin": "ai", "deleted": {"$ne": True}})
        if existing:
            have = {e["frame_id"] for e in existing.get("evidence") or []}
            new_ev = (existing.get("evidence") or []) + [e for e in ev if e["frame_id"] not in have]
            if existing.get("decision") == "pending" and not existing.get("edited"):
                await db[FD].update_one({"_id": existing["_id"]}, {"$set": {"severity": nf["severity"], "confidence": nf["confidence"], "explanation": nf["explanation"],
                                                                           "location_label": nf["location_label"], "evidence": new_ev, "run_id": run_id, "updated_at": now,
                                                                           "ai_original": {k: nf[k] for k in ("category", "subtype", "location", "location_label", "severity", "confidence", "explanation")}}})
                updated += 1
            else:
                await db[FD].update_one({"_id": existing["_id"]}, {"$set": {"evidence": new_ev, "updated_at": now}})
                kept += 1
            continue
        snap = {k: nf[k] for k in ("category", "subtype", "location", "location_label", "severity", "confidence", "explanation")}
        await db[FD].insert_one({"_id": ObjectId(), "inspection_id": str(ins["_id"]), "appraisal_id": ins["appraisal_id"], "user_id": ins["user_id"], "store_id": ins.get("store_id"),
                                 "fingerprint": key, "origin": "ai", "run_id": run_id, **snap, "ai_original": snap, "evidence": ev, "decision": "pending", "decision_by": None,
                                 "decision_by_name": None, "decision_at": None, "edited": False, "edit_history": [], "created_at": now, "updated_at": now})
        created += 1
    return {"created": created, "updated": updated, "kept": kept}


def coverage(frames: list) -> dict:
    """Per area and per group. Exterior angles want two usable looks, close-up areas one. Partial is allowed; missing is named."""
    counts = {a: 0 for a in AREAS}
    for f in frames:
        if f.get("usable") is False:
            continue
        for a in f.get("areas") or []:
            if a in counts:
                counts[a] += 1
    need = {a: (2 if a in EXTERIOR or a == "wheels" else 1) for a in AREAS}
    areas = {a: {"label": AREAS[a], "frames": counts[a], "status": "complete" if counts[a] >= need[a] else "partial" if counts[a] else "missing"} for a in AREAS}
    groups = {}
    for g, members in GROUPS.items():
        covered = [a for a in members if areas[a]["status"] != "missing"]
        complete = [a for a in members if areas[a]["status"] == "complete"]
        if g == "exterior":
            core_ok = all(areas[a]["status"] != "missing" for a in ("front", "rear", "driver_side", "passenger_side"))
            status = "complete" if len(covered) >= 6 and core_ok else "partial" if len(covered) >= 3 else "missing"
        else:
            status = "complete" if len(complete) == len(members) else "partial" if covered else "missing"
        groups[g] = {"label": GROUP_LABELS[g], "status": status, "missing": [AREAS[a] for a in members if areas[a]["status"] == "missing"],
                     "partial": [AREAS[a] for a in members if areas[a]["status"] == "partial"]}
    usable = sum(1 for f in frames if f.get("usable") is not False)
    return {"areas": areas, "groups": groups, "frames_total": len(frames), "frames_usable": usable,
            "missing": [AREAS[a] for a in AREAS if areas[a]["status"] == "missing"], "sufficient": groups["exterior"]["status"] != "missing"}


def _counts(findings: list, final: bool) -> dict:
    """Which findings weigh on a grade. AI grade: Jessi's medium/high calls. Final grade: what humans confirmed or added, plus medium/high calls nobody has reviewed yet."""
    per = {c: {"minor": 0, "moderate": 0, "major": 0, "points": 0, "items": []} for c in CATEGORIES}
    for d in findings:
        if d.get("decision") == "dismissed":
            continue
        if not final and d.get("origin") != "ai":
            continue
        if d.get("decision") == "pending" and d.get("confidence") == "low":
            continue
        if d.get("origin") == "voice" and d.get("decision") != "confirmed":
            continue  # heard, not seen: a voice finding weighs nothing until a human confirms it
        if not final and d.get("decision") != "pending" and d.get("origin") == "ai" and d.get("ai_original"):
            sev = d["ai_original"].get("severity", d.get("severity"))
        else:
            sev = d.get("severity") or "minor"
        c = per.get(d.get("category"))
        if c is None:
            continue
        c[sev] = c.get(sev, 0) + 1
        c["points"] += POINTS.get(sev, 1)
        c["items"].append(d)
    return per


def _grade_category(cat: str, c: dict) -> str:
    small = cat in ("wheels_tires", "glass")
    if c["major"] >= (1 if small else 2):
        return "poor"
    p = c["points"]
    if p == 0:
        return "very_good"
    if small:
        return "good" if p <= 1 else "fair" if p <= 3 else "poor"
    if c["major"]:
        return "fair"
    return "good" if p <= 3 else "fair" if p <= 6 else "poor"


def grade(findings: list, final: bool) -> dict:
    per = _counts(findings, final)
    cats = {c: _grade_category(c, per[c]) for c in CATEGORIES}
    total = per["body"]["points"] + per["interior"]["points"] + per["mechanical"]["points"] + 0.5 * (per["wheels_tires"]["points"] + per["glass"]["points"])
    overall = "very_good" if total == 0 else "good" if total <= 4 else "fair" if total <= 8 else "poor"
    majors = sum(per[c]["major"] for c in CATEGORIES)
    if majors and overall in ("very_good", "good"):
        overall = "fair"
    bits = []
    for c in CATEGORIES:
        n = per[c]
        if n["points"] == 0:
            bits.append(f"{CATEGORIES[c]}: no issues")
        else:
            parts = [f"{n[s]} {s}" for s in ("major", "moderate", "minor") if n[s]]
            bits.append(f"{CATEGORIES[c]}: {', '.join(parts)} ({GRADES[cats[c]]})")
    reason = (f"Overall {GRADES[overall]}. " + "; ".join(bits) + ". Minor counts 1, moderate 2, major 4; wheels and glass weigh half toward the overall"
              + ("; any major issue caps the overall at Fair" if majors else "") + ". Low-confidence findings are listed as possible issues and do not affect the grade until confirmed"
              + "; issues heard in voice notes count only once confirmed.")
    return {"overall": overall, "categories": cats, "reason": reason, "points": {c: per[c]["points"] for c in CATEGORIES}}


async def recompute(db, ins: dict) -> dict:
    """Final grade follows the humans; the AI grade stays as Jessi called it. An override wins until it is cleared."""
    findings = await findings_for(db, ins)
    g = grade(findings, final=True)
    upd = {"final_categories": g["categories"], "final_reason": g["reason"], "updated_at": _now()}
    upd["final_overall"] = (ins.get("override") or {}).get("overall") or g["overall"]
    upd["final_computed"] = g["overall"]
    await db[INS].update_one({"_id": ins["_id"]}, {"$set": upd})
    return await db[INS].find_one({"_id": ins["_id"]})


async def _org_retains(db, ins: dict) -> tuple:
    """Organization policy: (keep originals?, retention days). Falls back to the store's organization for users without one on their record."""
    org_id = ins.get("organization_id")
    if not org_id and ins.get("store_id"):
        st = await db.stores.find_one({"_id": _oid(ins["store_id"])}, {"organization_id": 1})
        org_id = (st or {}).get("organization_id")
    org = None
    if org_id:
        q = {"_id": _oid(org_id)} if _oid(org_id) else {"_id": org_id}
        org = await db.organizations.find_one(q, {"retain_original_inspection_video": 1, "inspection_video_retention_days": 1})
    retain = (org or {}).get("retain_original_inspection_video")
    days = int((org or {}).get("inspection_video_retention_days") or 365)
    return (True if retain is None else bool(retain)), days


def _destroy(path: Optional[str]):
    if path:
        put_object(path, b"\0", "application/octet-stream")


async def destroy_original(db, m: dict, reason: str):
    """Overwrite the original video in object storage (there is no delete). Frames, thumbnails and findings stay."""
    await asyncio.to_thread(_destroy, m.get("path"))
    await db[M].update_one({"_id": m["_id"]}, {"$set": {"original_available": False, "original_destroyed_at": _now(), "original_destroyed_reason": reason}})


async def run(db, ins_id: str, actor: dict):
    ins = await db[INS].find_one({"_id": ObjectId(ins_id)})
    appr = await db[A].find_one({"_id": ObjectId(ins["appraisal_id"])})
    run_id = ins.get("run_id")
    try:
        await _stage(db, ins["_id"], "extracting")
        media = await db[M].find({"appraisal_id": ins["appraisal_id"], "deleted": {"$ne": True}, "role": {"$in": list(INSPECT_ROLES)}}).sort("created_at", 1).to_list(200)
        done = set(ins.get("processed_media_ids") or [])
        for m in media:
            if str(m["_id"]) in done:
                continue
            await _ensure_frames(db, ins, m)
            await db[INS].update_one({"_id": ins["_id"]}, {"$addToSet": {"processed_media_ids": str(m["_id"])}})
        frames = await frames_for(db, ins)
        if not frames:
            raise ValueError("No usable frames came out of the media. Try a steadier video or clearer photos.")
        await _stage(db, ins["_id"], "inspecting", frames_total=len(frames))
        merged, impressions = await _analyze(db, ins, appr, frames)
        await _stage(db, ins["_id"], "scoring")
        frames = await frames_for(db, ins)
        cov = coverage(frames)
        stats = await _upsert_findings(db, ins, merged, run_id)
        findings = await findings_for(db, ins)
        ai = grade(findings, final=False)
        now = _now()
        poor = [m.get("name") for m in await db[M].find({"appraisal_id": ins["appraisal_id"], "deleted": {"$ne": True}, "video_quality": "poor"}).to_list(50)]
        await db[INS].update_one({"_id": ins["_id"]}, {"$set": {"status": "ready", "stage": "done", "coverage": cov, "ai_overall": ai["overall"], "ai_categories": ai["categories"],
                                                              "ai_reason": ai["reason"], "ai_impression": " ".join(impressions)[:600], "poor_quality_media": poor, "last_run": stats,
                                                              "finished_at": now, "report_generated_at": now, "last_error": None, "updated_at": now}})
        ins = await recompute(db, await db[INS].find_one({"_id": ins["_id"]}))
        prev_status = ins.get("prev_status") or "draft"
        await db[A].update_one({"_id": appr["_id"]}, {"$set": {"status": "ready" if prev_status in ("draft", "ready", "analyzing", "capturing") else prev_status, "updated_at": now}})
        await _audit(db, appr, actor, "inspection_completed", f"{len(frames)} frames · {stats['created']} new, {stats['updated']} updated findings · AI {GRADES[ai['overall']]}",
                     {"run_id": run_id, "coverage": {g: v["status"] for g, v in cov["groups"].items()}})
        try:
            from utils.activity_log import log_activity
            await log_activity(db, user_id=appr["user_id"], contact_id=appr["contact_id"], event_type="inspection_completed",
                               description=f"AI Vehicle Inspection: {GRADES[ai['overall']]} · {len(findings)} finding(s) on {vehicle_label(appr.get('vehicle') or {}) if appr.get('vehicle') else 'their trade'}",
                               metadata={"appraisal_id": str(appr["_id"]), "inspection_id": str(ins["_id"]), "overall": ai["overall"]})
        except Exception as e:
            logger.warning(f"[Inspection] feed event failed: {e}")
        retain, _ = await _org_retains(db, ins)
        if not retain:
            for m in media:
                if m.get("kind") == "video" and m.get("original_available") is not False and str(m["_id"]) in set((await db[INS].find_one({"_id": ins["_id"]})).get("processed_media_ids") or []):
                    await destroy_original(db, m, "org_retention_off")
    except Exception as e:
        logger.error(f"[Inspection] run {run_id} failed: {e}", exc_info=True)
        now = _now()
        await db[INS].update_one({"_id": ins["_id"]}, {"$set": {"status": "failed", "stage": "failed", "last_error": str(e)[:300], "finished_at": now, "updated_at": now}})
        await db[A].update_one({"_id": appr["_id"]}, {"$set": {"status": ins.get("prev_status") or "draft", "updated_at": now}})
        await _audit(db, appr, actor, "inspection_failed", str(e)[:200], {"run_id": run_id})


async def recover_interrupted(db) -> int:
    """Startup: a run that was queued/processing when the process stopped can never finish; mark it failed so the rep can retry."""
    now = _now()
    n = 0
    async for ins in db[INS].find({"status": {"$in": ["queued", "processing"]}}):
        await db[INS].update_one({"_id": ins["_id"]}, {"$set": {"status": "failed", "stage": "failed", "last_error": "Interrupted by a server restart — tap analyze to retry", "finished_at": now, "updated_at": now}})
        await db[A].update_one({"_id": _oid(ins["appraisal_id"]), "status": "analyzing"}, {"$set": {"status": ins.get("prev_status") or "draft", "updated_at": now}})
        n += 1
    if n:
        logger.warning(f"[Inspection] marked {n} interrupted run(s) failed")
    return n


async def purge_videos(db) -> int:
    """Daily: organizations that keep originals still have a retention window. Frames and findings are never touched."""
    n = 0
    async for m in db[M].find({"kind": "video", "deleted": {"$ne": True}, "original_available": {"$ne": False}, "frames_extracted_at": {"$ne": None}}):
        ins = await db[INS].find_one({"appraisal_id": m["appraisal_id"]}, {"organization_id": 1})
        if not ins:
            continue
        _, days = await _org_retains(db, ins)
        if _aware(m["created_at"]) < _now() - timedelta(days=days):
            await destroy_original(db, m, f"retention_{days}d")
            n += 1
    return n


# ---------- human review ----------
def _validate_fields(data: dict) -> dict:
    out = {}
    if "category" in data:
        if data["category"] not in CATEGORIES:
            raise ValueError("Unknown category")
        out["category"] = data["category"]
    if "subtype" in data:
        out["subtype"] = _slug(str(data["subtype"]))
    if "location" in data or "location_label" in data:
        label = str(data.get("location_label") or data.get("location") or "").strip()[:80]
        if not label:
            raise ValueError("Where on the vehicle?")
        out["location"], out["location_label"] = _slug(label) or "unspecified", label
    if "severity" in data:
        if data["severity"] not in SEVERITIES:
            raise ValueError("Severity must be minor, moderate or major")
        out["severity"] = data["severity"]
    if "explanation" in data:
        out["explanation"] = str(data["explanation"] or "").strip()[:600]
    return out


async def _evidence_from_ids(db, ins: dict, frame_ids: list) -> list:
    ids = [_oid(x) for x in (frame_ids or []) if _oid(x)]
    rows = await db[FR].find({"_id": {"$in": ids}, "inspection_id": str(ins["_id"]), "deleted": {"$ne": True}}).to_list(50) if ids else []
    return [_evidence(f) for f in rows]


async def add_finding(db, ins: dict, appr: dict, me: dict, data: dict) -> dict:
    fields = _validate_fields({**{"severity": "minor"}, **data})
    if "category" not in fields:
        raise ValueError("Pick a category")
    if fields.get("subtype") not in SUBTYPES[fields["category"]]:
        fields["subtype"] = "other"
    if "location" not in fields:
        raise ValueError("Where on the vehicle?")
    now = _now()
    doc = {"_id": ObjectId(), "inspection_id": str(ins["_id"]), "appraisal_id": ins["appraisal_id"], "user_id": ins["user_id"], "store_id": ins.get("store_id"),
           "fingerprint": f"human|{fields['category']}|{fields['subtype']}|{fields['location']}|{now.timestamp()}", "origin": "human", "run_id": None, **fields,
           "confidence": "high", "ai_original": None, "evidence": await _evidence_from_ids(db, ins, data.get("frame_ids") or []), "decision": "confirmed", "decision_by": str(me["_id"]),
           "decision_by_name": _name(me), "decision_at": now, "edited": False, "edit_history": [], "created_at": now, "updated_at": now}
    await db[FD].insert_one(doc)
    await _audit(db, appr, me, "finding_added", f"{doc['location_label']} · {SUBTYPES[doc['category']].get(doc['subtype'], doc['subtype'])} · {doc['severity']}", {"finding_id": str(doc["_id"])})
    await recompute(db, ins)
    return doc


async def edit_finding(db, ins: dict, appr: dict, me: dict, fid: str, data: dict) -> dict:
    d = await db[FD].find_one({"_id": _oid(fid), "inspection_id": str(ins["_id"]), "deleted": {"$ne": True}})
    if not d:
        raise ValueError("Finding not found")
    fields = _validate_fields(data)
    cat = fields.get("category", d["category"])
    if "subtype" in fields and fields["subtype"] not in SUBTYPES[cat]:
        fields["subtype"] = "other"
    if "category" in fields and "subtype" not in fields and d.get("subtype") not in SUBTYPES[cat]:
        fields["subtype"] = "other"
    if "frame_ids" in data:
        fields["evidence"] = await _evidence_from_ids(db, ins, data["frame_ids"])
    if not fields:
        return d
    now = _now()
    before = {k: d.get(k) for k in ("category", "subtype", "location", "location_label", "severity", "explanation")}
    await db[FD].update_one({"_id": d["_id"]}, {"$set": {**fields, "edited": True, "edited_by": str(me["_id"]), "edited_by_name": _name(me), "edited_at": now, "updated_at": now},
                                                "$push": {"edit_history": {"by": str(me["_id"]), "by_name": _name(me), "at": now, "before": before}}})
    await _audit(db, appr, me, "finding_edited", f"{d.get('location_label')} · " + ", ".join(f"{k}: {before.get(k)} → {v}" for k, v in fields.items() if k != "evidence" and before.get(k) != v), {"finding_id": fid})
    await recompute(db, ins)
    return await db[FD].find_one({"_id": d["_id"]})


async def decide(db, ins: dict, appr: dict, me: dict, fid: str, decision: str) -> dict:
    if decision not in ("confirmed", "dismissed", "pending"):
        raise ValueError("Decision must be confirmed, dismissed or pending")
    d = await db[FD].find_one({"_id": _oid(fid), "inspection_id": str(ins["_id"]), "deleted": {"$ne": True}})
    if not d:
        raise ValueError("Finding not found")
    now = _now()
    await db[FD].update_one({"_id": d["_id"]}, {"$set": {"decision": decision, "decision_by": str(me["_id"]) if decision != "pending" else None,
                                                         "decision_by_name": _name(me) if decision != "pending" else None, "decision_at": now if decision != "pending" else None, "updated_at": now}})
    await _audit(db, appr, me, f"finding_{decision}", f"{d.get('location_label')} · {SUBTYPES.get(d.get('category'), {}).get(d.get('subtype'), d.get('subtype'))}", {"finding_id": fid})
    await recompute(db, ins)
    return await db[FD].find_one({"_id": d["_id"]})


MAX_RECON_COST = 50_000


def finding_title(d: dict) -> str:
    label = d.get("location_label") or d.get("location") or CATEGORIES.get(d.get("category"), "")
    if label and ("_" in label or label.islower()):
        label = _title(label)
    return f"{label} · {SUBTYPES.get(d.get('category'), {}).get(d.get('subtype'), d.get('subtype'))}"


async def price_finding(db, appr: dict, me: dict, fid: str, amount: Optional[int]) -> dict:
    """Desk: a manager puts a dollar figure on a CONFIRMED finding (or clears it). The number then itemizes recon instead of the flat allowance."""
    d = await db[FD].find_one({"_id": _oid(fid), "appraisal_id": str(appr["_id"]), "deleted": {"$ne": True}})
    if not d:
        raise ValueError("Finding not found")
    if d.get("decision") != "confirmed":
        raise ValueError("Only confirmed findings can be priced. Confirm it first.")
    if amount is not None and not (0 <= int(amount) <= MAX_RECON_COST):
        raise ValueError(f"Recon cost must be between $0 and ${MAX_RECON_COST:,}")
    now = _now()
    upd = {"recon_cost": int(amount), "recon_by": str(me["_id"]), "recon_by_name": _name(me), "recon_at": now, "updated_at": now} if amount is not None \
        else {"recon_cost": None, "recon_by": None, "recon_by_name": None, "recon_at": None, "updated_at": now}
    await db[FD].update_one({"_id": d["_id"]}, {"$set": upd})
    await _audit(db, appr, me, "finding_priced" if amount is not None else "finding_price_cleared", f"{finding_title(d)}" + (f" · ${int(amount):,}" if amount is not None else " · price removed"),
                 {"finding_id": fid, "amount": amount})
    return await db[FD].find_one({"_id": d["_id"]})


async def recon_items(db, appr: dict) -> dict:
    """What the engine needs: every confirmed finding with a manager price, plus how many confirmed ones still have none."""
    rows = await db[FD].find({"appraisal_id": str(appr["_id"]), "decision": "confirmed", "deleted": {"$ne": True}}).sort("created_at", 1).to_list(200)
    items = [{"finding_id": str(d["_id"]), "label": finding_title(d), "amount": int(d["recon_cost"]), "severity": d.get("severity"), "category": d.get("category"), "by_name": d.get("recon_by_name")}
             for d in rows if d.get("recon_cost") is not None]
    return {"items": items, "unpriced": sum(1 for d in rows if d.get("recon_cost") is None), "confirmed": len(rows)}


async def override(db, ins: dict, appr: dict, me: dict, overall: Optional[str], reason: str) -> dict:
    if overall is not None and overall not in GRADES:
        raise ValueError("Grade must be very_good, good, fair or poor")
    if overall is not None and len((reason or "").strip()) < 3:
        raise ValueError("Say why you are changing the grade")
    now = _now()
    ov = {"overall": overall, "reason": (reason or "").strip()[:400], "by": str(me["_id"]), "by_name": _name(me), "at": now} if overall else None
    await db[INS].update_one({"_id": ins["_id"]}, {"$set": {"override": ov, "updated_at": now}})
    await _audit(db, appr, me, "condition_overridden" if ov else "condition_override_cleared", (f"{GRADES[overall]} · {ov['reason']}" if ov else ""), {})
    return await recompute(db, await db[INS].find_one({"_id": ins["_id"]}))


# ---------- read model ----------
def report(ins: dict, findings: list, frames_by_id: dict) -> Optional[dict]:
    if not ins.get("coverage") and not findings:
        return None
    pub = [public_finding(d, frames_by_id) for d in findings]
    confirmed = [f for f in pub if f["decision"] == "confirmed"]
    possible = [f for f in pub if f["decision"] == "pending" and f["confidence"] == "low"]
    pending = [f for f in pub if f["decision"] == "pending" and f["confidence"] != "low"]
    dismissed = [f for f in pub if f["decision"] == "dismissed"]
    ov = ins.get("override")
    return {"ai_overall": ins.get("ai_overall"), "ai_overall_label": GRADES.get(ins.get("ai_overall") or "", ""), "final_overall": ins.get("final_overall"),
            "final_overall_label": GRADES.get(ins.get("final_overall") or "", ""), "computed_overall": ins.get("final_computed"), "overridden": bool(ov), "override": ov,
            "categories": {c: {"label": CATEGORIES[c], "ai": (ins.get("ai_categories") or {}).get(c), "final": (ins.get("final_categories") or {}).get(c),
                               "final_label": GRADES.get((ins.get("final_categories") or {}).get(c) or "", "")} for c in CATEGORIES},
            "reason": ins.get("final_reason") or ins.get("ai_reason"), "ai_reason": ins.get("ai_reason"), "impression": ins.get("ai_impression"),
            "confirmed": confirmed, "possible": possible, "pending": pending, "dismissed_count": len(dismissed), "coverage": ins.get("coverage"),
            "poor_quality_media": ins.get("poor_quality_media") or [], "generated_at": ins.get("report_generated_at"), "status": ins.get("status")}


async def read(db, appr: dict) -> dict:
    ins = await get_or_create(db, appr)
    frames = await frames_for(db, ins)
    by_id = {str(f["_id"]): f for f in frames}
    findings = await findings_for(db, ins)
    return {"id": str(ins["_id"]), "status": ins.get("status"), "stage": ins.get("stage"), "run_count": ins.get("run_count") or 0, "last_error": ins.get("last_error"),
            "started_at": ins.get("started_at"), "finished_at": ins.get("finished_at"), "processed_media_ids": ins.get("processed_media_ids") or [],
            "frames": [public_frame(f) for f in frames], "findings": [public_finding(d, by_id) for d in findings], "coverage": ins.get("coverage"),
            "report": report(ins, findings, by_id), "areas": AREAS, "categories": CATEGORIES, "subtypes": SUBTYPES, "severities": SEVERITIES, "grades": GRADES}


async def summary(db, appr: dict) -> Optional[dict]:
    ins = await db[INS].find_one({"appraisal_id": str(appr["_id"])})
    if not ins:
        return None
    findings = await db[FD].find({"inspection_id": str(ins["_id"]), "deleted": {"$ne": True}}, {"decision": 1, "confidence": 1}).to_list(300)
    return {"status": ins.get("status"), "stage": ins.get("stage"), "final_overall": ins.get("final_overall"), "final_overall_label": GRADES.get(ins.get("final_overall") or "", ""),
            "ai_overall": ins.get("ai_overall"), "overridden": bool(ins.get("override")), "confirmed": sum(1 for d in findings if d.get("decision") == "confirmed"),
            "possible": sum(1 for d in findings if d.get("decision") == "pending" and d.get("confidence") == "low"),
            "pending": sum(1 for d in findings if d.get("decision") == "pending" and d.get("confidence") != "low"),
            "coverage": {g: v["status"] for g, v in ((ins.get("coverage") or {}).get("groups") or {}).items()}, "last_error": ins.get("last_error")}
