"""Jessi reads appraisal photos: a VIN from a door-jamb label (barcode first, OCR second) and a mileage from an instrument cluster.
Nothing here is ever accepted silently; the workflow always asks the rep to confirm."""
import asyncio
import base64
import io
import json
import logging
import os
import re
import uuid
from typing import Optional

from services.contact_files import _normalize_image, _for_vision, _parse_json
from services.llm_models import VISION_MODEL
from utils import vin as vinlib

logger = logging.getLogger(__name__)

VIN_SYSTEM = ("You read the VIN from a photo of a vehicle's door-jamb label, dashboard plate, registration or insurance card. "
              "Reply with JSON only: {\"vin\": \"17 characters or empty\", \"confidence\": \"high|medium|low\", \"where\": \"short note on where you read it\"}. "
              "A VIN never contains the letters I, O or Q. Read character by character; if two characters are ambiguous, say confidence low.")
ODO_SYSTEM = ("You read the odometer from a photo of an instrument cluster or dashboard display. Reply with JSON only: "
              "{\"mileage\": integer or null, \"unit\": \"mi|km\", \"confidence\": \"high|medium|low\", \"trip_meter_visible\": true|false, \"note\": \"short\"}. "
              "The odometer is the total distance (usually 5 or 6 digits, often labelled ODO or with no label); do NOT return a trip meter (TRIP A/B, usually with a decimal). "
              "If you cannot tell the odometer from a trip value, set confidence low.")


async def _vision(system: str, prompt: str, jpeg: bytes) -> dict:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        return {}
    from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
    chat = LlmChat(api_key=api_key, session_id=f"appr_{uuid.uuid4().hex[:8]}", system_message=system).with_model(*VISION_MODEL)
    try:
        out = await asyncio.wait_for(chat.send_message(UserMessage(text=prompt, file_contents=[ImageContent(image_base64=_for_vision(jpeg))])), timeout=60)
    except Exception as e:
        logger.warning(f"[Appraisal] vision read failed: {e}")
        return {}
    return _parse_json(out)


def _barcodes(jpeg: bytes) -> list:
    try:
        import zxingcpp
        from PIL import Image
        img = Image.open(io.BytesIO(jpeg))
        fmts = zxingcpp.BarcodeFormat.Code39 | zxingcpp.BarcodeFormat.Code128 | zxingcpp.BarcodeFormat.DataMatrix | zxingcpp.BarcodeFormat.QRCode | zxingcpp.BarcodeFormat.PDF417
        return [r.text for r in zxingcpp.read_barcodes(img, formats=fmts, try_rotate=True, try_downscale=True) if r.text]
    except Exception as e:
        logger.warning(f"[Appraisal] barcode read failed: {e}")
        return []


async def vin_from_image(data: bytes) -> dict:
    """{vin, method: barcode|ocr|none, confidence, candidates, validation}."""
    jpeg, _, _ = await asyncio.to_thread(_normalize_image, data)
    texts = await asyncio.to_thread(_barcodes, jpeg)
    for t in texts:
        for cand in vinlib.candidates(t) or [vinlib.normalize(t)]:
            val = vinlib.validate(cand)
            if val["valid"]:
                return {"vin": val["vin"], "method": "barcode", "confidence": "high", "candidates": [val["vin"]], "validation": val}
    read = await _vision(VIN_SYSTEM, "Read the VIN in this photo.", jpeg)
    raw = str(read.get("vin") or "")
    cands = vinlib.candidates(raw)
    val = vinlib.validate(cands[0] if cands else raw)
    conf = str(read.get("confidence") or "low").lower()
    if val["valid"] and conf == "high" and val["checksum"] == "ok":
        confidence = "high"
    elif val["valid"]:
        confidence = "medium"
    else:
        confidence = "low"
    return {"vin": val["vin"] if val["vin"] else "", "method": "ocr" if raw else "none", "confidence": confidence, "candidates": cands or ([val["vin"]] if val["vin"] else []),
            "validation": val, "note": read.get("where") or ""}


async def odometer_from_image(data: bytes) -> dict:
    """{mileage, unit, confidence, note}. Kilometres are converted to miles and flagged."""
    jpeg, _, _ = await asyncio.to_thread(_normalize_image, data)
    read = await _vision(ODO_SYSTEM, "Read the odometer total in this photo.", jpeg)
    raw = read.get("mileage")
    try:
        miles: Optional[int] = int(re.sub(r"[^\d]", "", str(raw))) if raw not in (None, "") else None
    except ValueError:
        miles = None
    unit = str(read.get("unit") or "mi").lower()
    converted = False
    if miles is not None and unit.startswith("k"):
        miles, converted = round(miles * 0.621371), True
    if miles is not None and not (10 <= miles <= 1_500_000):
        miles = None
    conf = str(read.get("confidence") or "low").lower() if miles is not None else "low"
    if read.get("trip_meter_visible") and conf == "high":
        conf = "medium"
    note = read.get("note") or ""
    if converted:
        note = (note + " · shown in km, converted to miles").strip(" ·")
    return {"mileage": miles, "unit": "mi", "confidence": conf, "note": note}
