"""Voice into findings: what a rep or customer SAYS about the car ("AC blows warm", "driver seat is torn") becomes a PENDING inspection finding the rep
confirms or dismisses, with the spoken words as its evidence. A voice finding never weighs on the condition grade until it is confirmed and is never a value."""
import asyncio
import logging
import os
import re
import uuid
from typing import Optional

from bson import ObjectId

from services.appraisals import inspection as insp
from services.appraisals.core import _now
from services.appraisals.providers import vehicle_label
from services.contact_files import _parse_json
from services.llm_models import CUSTOMER_TEXT_MODEL
from utils.text_sanitize import no_em_dash

logger = logging.getLogger(__name__)

MAX_PER_NOTE = 8
MIN_WORDS = 3
SYSTEM = ("You turn ONE spoken note about a used vehicle ({label}) at a car dealership into inspection findings. Reply with JSON only:\n"
          "{{\"findings\":[{{\"category\":\"body|glass|wheels_tires|interior|mechanical\",\"subtype\":\"<from the list>\",\"location\":\"<snake_case e.g. driver_seat, front_brakes, climate_control>\","
          "\"location_label\":\"Driver Seat\",\"severity\":\"minor|moderate|major\",\"confidence\":\"high|medium|low\",\"quote\":\"<the speaker's exact words that state this problem>\","
          "\"explanation\":\"<one short plain sentence>\"}}]}}\n"
          "Subtypes - body: dent, scratch, paint_damage, bumper_damage, rust, broken_trim, mismatched_panel, other. glass: windshield_chip, windshield_crack, damaged_glass, other. "
          "wheels_tires: curb_rash, wheel_damage, tire_wear, tire_damage, other. interior: seat_damage, stain, excessive_wear, damaged_trim, warning_light, odor, other. "
          "mechanical: ac_heat, engine, transmission, brakes, suspension_steering, electrical, noise_vibration, fluid_leak, exhaust, check_engine_light, other.\n"
          "Rules: one finding per distinct problem the speaker actually states. Positive statements (runs great, tires are new, clean inside), service history, accidents, number of keys, "
          "mileage, prices and what the customer wants are NOT findings. Never guess at problems that were not said. Severity from the words: works sometimes or cosmetic = minor, "
          "clearly needs work = moderate, does not work at all or unsafe = major. Confidence high when the speaker is direct, low when hedged (I think, maybe, might, not sure). "
          "If nothing is wrong, return {{\"findings\":[]}}.")


async def extract_llm(transcript: str, label: str) -> list:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        return []
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    chat = LlmChat(api_key=api_key, session_id=f"vfind_{uuid.uuid4().hex[:8]}", system_message=SYSTEM.format(label=label or "a used vehicle")).with_model(*CUSTOMER_TEXT_MODEL)
    out = await asyncio.wait_for(chat.send_message(UserMessage(text=f"Spoken note:\n\"{transcript}\"\n\nList the findings as JSON.")), timeout=40)
    parsed = _parse_json(out)
    return parsed.get("findings") if isinstance(parsed.get("findings"), list) else []


EXTRACTOR = extract_llm  # swapped in tests


def _words(s: str) -> list:
    return [w for w in re.findall(r"[a-z0-9']+", (s or "").lower()) if len(w) > 2]


def _said(quote: str, transcript: str) -> bool:
    """The quote has to come from the note: at least 60% of its real words appear in the transcript."""
    q, t = _words(quote), set(_words(transcript))
    return bool(q) and sum(1 for w in q if w in t) / len(q) >= 0.6


def _norm(raw: dict, transcript: str) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None
    cat = str(raw.get("category") or "").lower().strip()
    if cat not in insp.CATEGORIES:
        return None
    quote = no_em_dash(str(raw.get("quote") or "").strip())[:240]
    if not quote or not _said(quote, transcript):
        return None
    sub = insp._slug(str(raw.get("subtype") or "other"))
    sub = sub if sub in insp.SUBTYPES[cat] else "other"
    sev = str(raw.get("severity") or "minor").lower()
    conf = str(raw.get("confidence") or "medium").lower()
    label = (str(raw.get("location_label") or raw.get("location") or "").strip() or insp.CATEGORIES[cat])[:80]
    return {"category": cat, "subtype": sub, "location": insp._slug(label) or "unspecified", "location_label": insp._title(insp._slug(label)) if label.islower() else label,
            "severity": sev if sev in insp.SEVERITIES else "minor", "confidence": conf if conf in insp.CONFIDENCES else "medium",
            "explanation": no_em_dash(str(raw.get("explanation") or "").strip())[:600], "quote": quote}


async def add_from_transcript(db, appr: dict, note_id: str, transcript: str, by: str, actor: dict) -> list:
    """LLM reads the words, every stated problem becomes one pending voice finding. Returns the public findings (possibly empty). Never raises."""
    if len(_words(transcript)) < MIN_WORDS:
        return []
    try:
        raws = await EXTRACTOR(transcript, vehicle_label(appr.get("vehicle") or {}) if appr.get("vehicle") else "")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[VoiceFindings] extraction failed: {e}")
        return []
    ins = await insp.get_or_create(db, appr)
    now = _now()
    docs = []
    for i, raw in enumerate((raws or [])[:MAX_PER_NOTE]):
        nf = _norm(raw, transcript)
        if not nf:
            continue
        docs.append({"_id": ObjectId(), "inspection_id": str(ins["_id"]), "appraisal_id": ins["appraisal_id"], "user_id": ins["user_id"], "store_id": ins.get("store_id"),
                     "fingerprint": f"voice|{note_id}|{i}", "origin": "voice", "run_id": None, **nf, "voice_note_id": note_id, "spoken_by": by, "ai_original": None, "evidence": [],
                     "decision": "pending", "decision_by": None, "decision_by_name": None, "decision_at": None, "edited": False, "edit_history": [], "created_at": now, "updated_at": now})
    if not docs:
        return []
    await db[insp.FD].insert_many(docs)
    await insp._audit(db, appr, actor, "voice_findings_suggested", "; ".join(f"{d['location_label']} {insp.SUBTYPES[d['category']].get(d['subtype'], d['subtype'])} ({d['severity']})" for d in docs),
                      {"voice_note_id": note_id, "count": len(docs), "by": by})
    return [insp.public_finding(d, {}) for d in docs]


async def remove_for_note(db, appr: dict, note_id: str) -> int:
    """The clip is gone: its unreviewed suggestions go too. Anything the rep already confirmed stays as a human decision."""
    now = _now()
    r = await db[insp.FD].update_many({"appraisal_id": str(appr["_id"]), "origin": "voice", "voice_note_id": note_id, "decision": {"$ne": "confirmed"}, "deleted": {"$ne": True}},
                                      {"$set": {"deleted": True, "deleted_at": now, "updated_at": now}})
    if r.modified_count:
        ins = await db[insp.INS].find_one({"appraisal_id": str(appr["_id"])})
        if ins:
            await insp.recompute(db, ins)
    return r.modified_count
