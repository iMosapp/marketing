"""Seed three contact files on Sarah Tester (Activation Tester's contact): a business card photo, a fleet quote PDF and a
driver's license photo (sensitive). Jessi reads each one (real LLM, ~15 s per file). Idempotent by `seed_key`.
Run: cd /app/backend && python tests/seed_contact_files_demo.py [--wipe]"""
import asyncio
import io
import os
import sys

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from PIL import Image, ImageDraw, ImageFont

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")

REP_EMAIL = "activation-tester@invalid.imonsocial.test"
CONTACT_ID = "6aa413008f0d53e3f2261853"
MARK = "contact_files_demo"


def _png(lines: list[str], size=(900, 520), bg=(250, 248, 240)) -> bytes:
    img = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(img)
    try:
        big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 44)
        small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
    except Exception:
        big = small = ImageFont.load_default()
    y = 60
    for i, line in enumerate(lines):
        d.text((60, y), line, fill=(20, 20, 20), font=big if i == 0 else small)
        y += 70 if i == 0 else 48
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _pdf(lines: list[str]) -> bytes:
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for i, line in enumerate(lines):
        page.insert_text((72, y), line, fontsize=18 if i == 0 else 12)
        y += 34 if i == 0 else 20
    return doc.tobytes()


FILES = [
    {"key": "marcus_card", "name": "marcus-card.png", "content_type": "image/png", "hint": "business_card",
     "data": lambda: _png(["Marcus Delgado", "Fleet Sales Manager", "Rocky Mountain Kubota", "(500) 555-0142", "marcus.delgado@invalid.imonsocial.test", "4410 S State St, Salt Lake City, UT 84107"])},
    {"key": "fleet_quote", "name": "fleet-quote.pdf", "content_type": "application/pdf", "hint": "document",
     "data": lambda: _pdf(["Kubota Fleet Quote - Sarah Tester", "Quote #Q-2026-0417    Date: September 18, 2026", "Prepared for: Sarah Tester, Rocky Mountain Kubota",
                            "", "2 x Kubota RTV-X1140 utility vehicles        $19,850.00 each", "1 x Kubota SVL75-3 compact track loader      $68,400.00",
                            "Hydraulic thumb attachment                    $2,150.00", "Delivery to Salt Lake City yard             $450.00",
                            "", "Subtotal: $110,700.00    Tax (7.25%): $8,025.75    Total: $118,725.75", "Trade-in considered: 2019 RTV-X900, 1,420 hours, est. $9,500",
                            "Valid through October 31, 2026. Financing at 0% for 48 months available on the SVL75-3."])},
    {"key": "license", "name": "license.png", "content_type": "image/png", "hint": "id_document",
     "data": lambda: _png(["UTAH DRIVER LICENSE", "TESTER, SARAH ANN", "DOB 04/12/1987   EXP 04/12/2030", "DL 7723-9910-5541   CLASS D", "1180 E 2100 S, SALT LAKE CITY, UT 84106"], bg=(222, 232, 245))},
]


async def main(wipe: bool):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    from services import contact_files as cf
    rep = await db.users.find_one({"email": REP_EMAIL}, {"_id": 1})
    assert rep, "activation-tester missing"
    uid = str(rep["_id"])
    if wipe:
        n = 0
        async for doc in db.contact_files.find({"seed_key": MARK, "deleted": {"$ne": True}}):
            await cf.destroy_file(db, doc, "seed_wipe"); n += 1
        print(f"wiped {n}")
        return
    for f in FILES:
        if await db.contact_files.find_one({"seed_key": MARK, "seed_item": f["key"], "deleted": {"$ne": True}}):
            print(f"exists: {f['name']}")
            continue
        doc = await cf.save_file(db, user_id=uid, contact_id=CONTACT_ID, name=f["name"], content_type=f["content_type"], data=f["data"](), hint=f["hint"])
        await db.contact_files.update_one({"_id": doc["_id"]}, {"$set": {"seed_key": MARK, "seed_item": f["key"]}})
        print(f"seeded: {f['name']} -> {doc.get('title') or '(no title)'} [{doc.get('scan_type')}] sensitive={doc.get('sensitive')}")


if __name__ == "__main__":
    asyncio.run(main("--wipe" in sys.argv))
