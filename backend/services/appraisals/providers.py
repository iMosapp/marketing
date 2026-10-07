"""Vehicle identity providers. The appraisal workflow only ever sees NormalizedVehicle dicts and the IDENTITY registry:
  VehicleIdentityProvider -> VINIdentityProvider (decoder: VINDecodeProvider -> NHTSAProvider)
                          -> PlateIdentityProvider (architected; needs a plate-to-VIN provider to be switched on)
Swap or add a provider here; nothing else in the module changes."""
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx

from utils import vin as vinlib

logger = logging.getLogger(__name__)
DECODE_CACHE_DAYS = 180
VEHICLE_FIELDS = ("vin", "year", "make", "model", "trim", "series", "body_class", "engine", "fuel", "drivetrain",
                  "manufacturer", "vehicle_type", "plant", "doors", "transmission")


class ProviderUnavailable(Exception):
    """The outside service failed or is not configured; the workflow falls back to manual entry."""


def empty_vehicle(vin: Optional[str] = None) -> dict:
    v = {k: None for k in VEHICLE_FIELDS}
    v.update({"vin": vin, "decoded_by": None, "decode_ok": False, "decode_message": ""})
    return v


def vehicle_label(v: dict) -> str:
    parts = [str(v.get("year") or ""), v.get("make") or "", v.get("model") or "", v.get("trim") or v.get("series") or ""]
    return " ".join(p for p in parts if p).strip() or (v.get("vin") or "Vehicle")


class VINDecodeProvider:
    name = "base"

    async def decode(self, vin: str) -> dict:
        raise NotImplementedError


class NHTSAProvider(VINDecodeProvider):
    """Free vPIC decoder. https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValuesExtended/{vin}?format=json"""
    name = "nhtsa_vpic"
    URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValuesExtended/{vin}?format=json"

    async def decode(self, vin: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=12) as cx:
                r = await cx.get(self.URL.format(vin=vin))
            r.raise_for_status()
            row = ((r.json() or {}).get("Results") or [{}])[0]
        except Exception as e:
            logger.warning(f"[VIN] NHTSA failed for {vin}: {e}")
            raise ProviderUnavailable("NHTSA did not answer. Enter the vehicle by hand.")
        return self.normalize(vin, row)

    @staticmethod
    def normalize(vin: str, row: dict) -> dict:
        g = lambda k: (row.get(k) or "").strip() or None
        v = empty_vehicle(vin)
        year = g("ModelYear")
        eng = " ".join(p for p in [
            f"{g('EngineCylinders')} cyl" if g("EngineCylinders") else "",
            f"{round(float(g('DisplacementL')), 1)}L" if g("DisplacementL") else "",
            f"{g('EngineHP')} hp" if g("EngineHP") else "",
            g("EngineModel") or ""] if p).strip() or None
        v.update({
            "year": int(year) if year and year.isdigit() else None, "make": (g("Make") or "").title() or None, "model": g("Model"),
            "trim": g("Trim") or g("Trim2"), "series": g("Series") or g("Series2"), "body_class": g("BodyClass"), "engine": eng,
            "fuel": g("FuelTypePrimary"), "drivetrain": g("DriveType"), "manufacturer": g("Manufacturer"), "vehicle_type": g("VehicleType"),
            "plant": ", ".join(p for p in [g("PlantCity"), g("PlantState"), g("PlantCountry")] if p) or None,
            "doors": g("Doors"), "transmission": g("TransmissionStyle"),
            "decoded_by": NHTSAProvider.name, "raw": {k: val for k, val in row.items() if val not in ("", None)},
        })
        code = g("ErrorCode") or "0"
        v["decode_ok"] = bool(v["make"] and v["model"]) and code.split(",")[0].strip() in ("0", "1", "6", "7", "8", "14")
        v["decode_message"] = g("ErrorText") if not v["decode_ok"] else ""
        return v


DECODER: VINDecodeProvider = NHTSAProvider()


async def decode_vin(db, vin: str) -> dict:
    """Cached decode (180 days). Raises ProviderUnavailable when the decoder is down and nothing is cached."""
    hit = await db.vin_decode_cache.find_one({"vin": vin, "provider": DECODER.name})
    if hit and hit.get("fetched_at") and hit["fetched_at"].replace(tzinfo=timezone.utc) > datetime.now(timezone.utc) - timedelta(days=DECODE_CACHE_DAYS):
        return hit["vehicle"]
    vehicle = await DECODER.decode(vin)
    await db.vin_decode_cache.update_one({"vin": vin, "provider": DECODER.name},
                                         {"$set": {"vehicle": vehicle, "fetched_at": datetime.now(timezone.utc)}}, upsert=True)
    return vehicle


class VehicleIdentityProvider:
    kind = "base"
    label = ""

    def configured(self) -> bool:
        return True

    async def identify(self, db, **inputs) -> dict:
        """Returns {"vin", "validation", "vehicle"}; vehicle may be a decode failure (decode_ok False) that the rep completes by hand."""
        raise NotImplementedError


class VINIdentityProvider(VehicleIdentityProvider):
    kind = "vin"
    label = "VIN"

    async def identify(self, db, vin: str = "", **_) -> dict:
        val = vinlib.validate(vin)
        if not val["valid"]:
            return {"vin": val["vin"], "validation": val, "vehicle": None}
        try:
            vehicle = await decode_vin(db, val["vin"])
        except ProviderUnavailable as e:
            vehicle = empty_vehicle(val["vin"])
            vehicle["decode_message"] = str(e)
        return {"vin": val["vin"], "validation": val, "vehicle": vehicle}


class PlateIdentityProvider(VehicleIdentityProvider):
    """Plate + state -> VIN. Needs a commercial plate-to-VIN provider; set PLATE_LOOKUP_PROVIDER when one is contracted."""
    kind = "plate"
    label = "License plate"

    def configured(self) -> bool:
        return bool(os.environ.get("PLATE_LOOKUP_PROVIDER"))

    async def identify(self, db, plate: str = "", state: str = "", **_) -> dict:
        raise ProviderUnavailable("License plate lookup is not switched on yet. Scan or type the VIN instead.")


IDENTITY = {p.kind: p for p in (VINIdentityProvider(), PlateIdentityProvider())}


def identity_options() -> list:
    return [{"kind": p.kind, "label": p.label, "available": p.configured()} for p in IDENTITY.values()]
