"""
Nightly dealer inventory feeds over SFTP (HomeNet, vAuto, Dealer.com, any CSV drop).
The dealer's inventory tool pushes a CSV to a Files.com (or any SFTP) folder; we pull the newest file,
map its columns, upsert vehicles by VIN / stock number and mark units that fell off the file as sold.
"""
import asyncio
import base64
import csv
import fnmatch
import hashlib
import io
import logging
import os
import re
import stat as _stat
import uuid
from datetime import datetime, timezone, timedelta

from bson import ObjectId
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

PROVIDERS = {
    "homenet": {"label": "HomeNet (Cox)", "form": "https://www.homenetauto.com/vfsr/",
                "how": "Dealer submits the HomeNet Export Request Form (dealer ID, destination 'i'M On Social', our SFTP host, username, password, folder and file name)."},
    "vauto": {"label": "vAuto (Cox)", "form": "",
              "how": "Dealer asks their vAuto rep for a 3rd-party inventory export to our SFTP host, username, password and folder. Nightly CSV."},
    "dealer_com": {"label": "Dealer.com", "form": "https://www.dealer.com/support/inventory/",
                   "how": "Dealer submits the Dealer.com 3rd Party Inventory Request form with our SFTP details."},
    "dealeron": {"label": "DealerOn / Dealer Inspire", "form": "",
                 "how": "Dealer asks their website provider's support for a third-party inventory feed to our SFTP details."},
    "other": {"label": "Other CSV feed", "form": "",
              "how": "Any tool that can drop a CSV on an SFTP folder nightly (Dealer Specialties, DealerCenter, Frazer, a Google Sheet export)."},
}

# CSV header (lowercased, stripped) -> our field
CSV_HEADER_ALIASES = {
    "year": "year", "yr": "year", "modelyear": "year", "model year": "year",
    "make": "make", "manufacturer": "make",
    "model": "model",
    "trim": "trim", "series": "trim", "trim level": "trim",
    "body": "body_type", "body type": "body_type", "body_type": "body_type", "body style": "body_type", "body_style": "body_type",
    "bodystyle": "body_type", "vehicle type": "body_type", "vehicletype": "body_type",
    "type": "condition", "condition": "condition", "new/used": "condition", "newused": "condition", "new used": "condition",
    "inventory type": "condition", "vehicle condition": "condition",
    "certified": "certified", "cpo": "certified",
    "color": "color", "colour": "color", "exterior color": "color", "ext color": "color", "exterior": "color", "extcolor": "color",
    "ext_color": "color", "exteriorcolor": "color", "exterior_color": "color",
    "interior color": "interior_color", "int color": "interior_color", "interiorcolor": "interior_color", "interior_color": "interior_color",
    "mileage": "mileage", "miles": "mileage", "odometer": "mileage",
    "price": "price", "list price": "price", "selling price": "price", "asking price": "price", "internet price": "price",
    "internetprice": "price", "sale price": "price", "saleprice": "price", "special price": "price", "sellingprice": "price",
    "listprice": "price", "retail price": "price",
    "msrp": "msrp",
    "stock": "stock_number", "stock#": "stock_number", "stock #": "stock_number", "stock number": "stock_number",
    "stock_number": "stock_number", "stocknumber": "stock_number", "stock no": "stock_number", "stockno": "stock_number",
    "vin": "vin",
    "status": "status",
    "name": "name", "title": "name", "vehicle": "name", "vehicle title": "name",
    "description": "description", "desc": "description", "notes": "description", "comments": "description",
    "dealer comments": "description", "options": "options", "features": "options", "equipment": "options",
    "imagelist": "images", "image list": "images", "image_list": "images", "images": "images", "image urls": "images",
    "image_urls": "images", "imageurls": "images", "photo urls": "images", "photo_urls": "images", "photourls": "images",
    "photos": "images", "pictures": "images", "picture urls": "images", "photo url": "images", "image url": "images",
    "main photo": "images", "primary image": "images", "photo": "images",
    "drivetrain": "drivetrain", "drive train": "drivetrain", "drive type": "drivetrain", "drive": "drivetrain", "drivetype": "drivetrain",
    "fuel": "fuel_type", "fuel type": "fuel_type", "fuel_type": "fuel_type", "fueltype": "fuel_type",
    "transmission": "transmission", "trans": "transmission",
    "engine": "engine", "engine description": "engine",
    "doors": "doors",
    "date in stock": "date_in_stock", "dateinstock": "date_in_stock", "date_in_stock": "date_in_stock", "inventory date": "date_in_stock",
    "dealer id": "dealer_id", "dealerid": "dealer_id", "dealer_id": "dealer_id",
}
# when several columns map to price, the first match in this list wins
PRICE_PRIORITY = ("internet price", "internetprice", "special price", "sale price", "saleprice", "selling price", "sellingprice",
                  "price", "asking price", "retail price", "list price", "listprice")

ATTR_FIELDS = ("year", "make", "model", "trim", "body_type", "condition", "certified", "color", "interior_color", "mileage",
               "stock_number", "vin", "drivetrain", "fuel_type", "transmission", "engine", "doors", "msrp", "date_in_stock", "options")


def _fernet() -> Fernet:
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET env var is not set")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("inventory-feed:" + secret).encode()).digest()))


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt((value or "").encode()).decode()


def decrypt_secret(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, Exception):
        return ""


def map_headers(fieldnames: list) -> dict:
    """CSV header -> our field, honouring price priority when several price columns exist."""
    header_map = {}
    price_cols = []
    for h in fieldnames or []:
        key = (h or "").strip().lower()
        field = CSV_HEADER_ALIASES.get(key)
        if not field:
            continue
        if field == "price":
            price_cols.append((key, h))
            continue
        header_map.setdefault(field, h)
    if price_cols:
        ranked = sorted(price_cols, key=lambda kh: PRICE_PRIORITY.index(kh[0]) if kh[0] in PRICE_PRIORITY else 99)
        header_map["price"] = ranked[0][1]
    return {h: f for f, h in header_map.items()}


def parse_inventory_csv(text: str, limit: int = 5000) -> tuple:
    """Returns (rows as our-field dicts, recognized fields, skipped count)."""
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return [], [], 0
    header_map = map_headers(reader.fieldnames)
    if not header_map:
        return [], [], 0
    rows = []
    for row in reader:
        rows.append({header_map[h]: (row.get(h) or "").strip() for h in header_map})
        if len(rows) >= limit:
            break
    return rows, sorted(set(header_map.values())), 0


def split_images(raw: str) -> list:
    if not raw:
        return []
    parts = re.split(r"[|;,\s]+", raw.strip())
    return [p for p in parts if p.lower().startswith("http")][:12]


def build_item(user_id: str, store_id, data: dict, source: str) -> dict | None:
    """One inventory doc from a mapped CSV / form row. Shared by manual CSV upload and SFTP feeds."""
    attributes = {}
    for f in ATTR_FIELDS:
        v = data.get(f)
        if v not in (None, ""):
            attributes[f] = str(v).strip()
    if attributes.get("mileage"):
        attributes["mileage"] = re.sub(r"[^\d]", "", attributes["mileage"]) or attributes["mileage"]
    name = (data.get("name") or "").strip()
    if not name:
        name = " ".join(str(attributes.get(f, "")).strip() for f in ("year", "make", "model", "trim") if attributes.get(f)).strip()
    if not name:
        return None
    price = None
    raw_price = data.get("price")
    if raw_price not in (None, ""):
        try:
            price = float(str(raw_price).replace("$", "").replace(",", "").strip())
        except Exception:
            price = None
    if price is not None and price <= 0:
        price = None
    status = (data.get("status") or "available").strip().lower() or "available"
    if status in ("in stock", "instock", "active", "live", "for sale"):
        status = "available"
    images = split_images(data.get("images", ""))
    now = datetime.now(timezone.utc)
    doc = {
        "external_id": f"{source}-{uuid.uuid4().hex[:12]}",
        "name": name,
        "category": "vehicle",
        "status": status,
        "price": price,
        "currency": "USD",
        "store_id": store_id,
        "created_by_user_id": user_id,
        "description": (data.get("description") or "").strip(),
        "attributes": attributes,
        "tags": [],
        "is_visible": True,
        "source_system": source,
        "created_at": now,
        "updated_at": now,
    }
    if images:
        doc["images"] = images
        doc["primary_image"] = images[0]
    return doc


# ── SFTP ──────────────────────────────────────────────────────────────────────

def _sftp_connect(feed: dict):
    import paramiko
    host = (feed.get("sftp_host") or "").strip()
    port = int(feed.get("sftp_port") or 22)
    user = (feed.get("sftp_username") or "").strip()
    password = decrypt_secret(feed.get("sftp_password_enc", ""))
    transport = paramiko.Transport((host, port))
    transport.banner_timeout = 20
    transport.connect(username=user, password=password)
    return transport, paramiko.SFTPClient.from_transport(transport)


def _list_files_sync(feed: dict) -> list:
    transport, sftp = _sftp_connect(feed)
    try:
        path = (feed.get("remote_path") or "/").strip() or "/"
        pattern = (feed.get("file_pattern") or "*.csv").strip() or "*.csv"
        out = []
        for a in sftp.listdir_attr(path):
            if _stat.S_ISDIR(a.st_mode or 0):
                continue
            if not fnmatch.fnmatch(a.filename.lower(), pattern.lower()):
                continue
            out.append({"name": a.filename, "size": int(a.st_size or 0), "mtime": int(a.st_mtime or 0),
                        "modified": datetime.fromtimestamp(a.st_mtime or 0, tz=timezone.utc).isoformat()})
        out.sort(key=lambda f: f["mtime"], reverse=True)
        return out
    finally:
        try:
            sftp.close()
        finally:
            transport.close()


def _download_sync(feed: dict, filename: str, max_bytes: int = 60 * 1024 * 1024) -> str:
    transport, sftp = _sftp_connect(feed)
    try:
        path = (feed.get("remote_path") or "/").rstrip("/")
        full = f"{path}/{filename}" if path else filename
        buf = io.BytesIO()
        with sftp.open(full, "rb") as fh:
            while True:
                chunk = fh.read(1024 * 1024)
                if not chunk:
                    break
                buf.write(chunk)
                if buf.tell() > max_bytes:
                    raise ValueError("Feed file larger than 60 MB")
        raw = buf.getvalue()
        try:
            return raw.decode("utf-8-sig")
        except Exception:
            return raw.decode("latin-1", errors="ignore")
    finally:
        try:
            sftp.close()
        finally:
            transport.close()


async def test_connection(feed: dict) -> dict:
    try:
        files = await asyncio.wait_for(asyncio.to_thread(_list_files_sync, feed), timeout=45)
        return {"ok": True, "files": files[:20], "file_count": len(files)}
    except Exception as e:
        return {"ok": False, "error": _friendly_error(e), "files": [], "file_count": 0}


def _friendly_error(e: Exception) -> str:
    msg = str(e) or e.__class__.__name__
    low = msg.lower()
    if "authentication" in low:
        return "SFTP login failed: check the username and password"
    if "no such file" in low or "not found" in low:
        return "Folder not found on the SFTP server: check the folder path"
    if "timed out" in low or "timeout" in low or isinstance(e, asyncio.TimeoutError):
        return "Could not reach the SFTP host (timed out): check the host and port"
    if "name or service not known" in low or "nodename" in low or "getaddrinfo" in low:
        return "SFTP host not found: check the host name"
    if "connection refused" in low:
        return "Connection refused: check the port (Files.com uses 22)"
    return msg[:300]


def feed_public(feed: dict) -> dict:
    d = {k: v for k, v in feed.items() if k not in ("sftp_password_enc", "_id")}
    d["id"] = str(feed["_id"])
    d["has_password"] = bool(feed.get("sftp_password_enc"))
    for k in ("created_at", "updated_at", "last_run_at", "last_success_at"):
        if isinstance(d.get(k), datetime):
            d[k] = d[k].isoformat()
    return d


# ── Sync ──────────────────────────────────────────────────────────────────────

def _key(attrs: dict) -> str | None:
    vin = (attrs.get("vin") or "").strip().upper()
    if len(vin) >= 11:
        return f"vin:{vin}"
    stock = (attrs.get("stock_number") or "").strip().upper()
    if stock:
        return f"stock:{stock}"
    return None


async def sync_feed(db, feed: dict, force: bool = False, triggered_by: str = "scheduler") -> dict:
    """Pull the newest matching file and upsert the store's inventory. Always records a run."""
    feed_id = str(feed["_id"])
    store_id = feed.get("store_id")
    started = datetime.now(timezone.utc)
    run = {"feed_id": feed_id, "store_id": store_id, "started_at": started, "triggered_by": triggered_by,
           "status": "error", "file_name": None, "units_seen": 0, "added": 0, "updated": 0, "marked_sold": 0, "skipped": 0, "error": None}
    try:
        files = await asyncio.wait_for(asyncio.to_thread(_list_files_sync, feed), timeout=60)
        if not files:
            raise FileNotFoundError(f"No files matching {feed.get('file_pattern') or '*.csv'} in {feed.get('remote_path') or '/'}")
        newest = files[0]
        last = feed.get("last_file") or {}
        if not force and last.get("name") == newest["name"] and last.get("mtime") == newest["mtime"] and last.get("size") == newest["size"]:
            run.update({"status": "no_new_file", "file_name": newest["name"]})
            await _finish_run(db, feed, run, newest)
            return run

        text = await asyncio.wait_for(asyncio.to_thread(_download_sync, feed, newest["name"]), timeout=180)
        rows, fields, _ = parse_inventory_csv(text)
        if not fields:
            raise ValueError("No recognized columns in the file. Expected headers like VIN, Stock, Year, Make, Model, Price, ImageList")
        if not rows:
            raise ValueError("The file has a header row but no vehicles")

        owner = feed.get("created_by", "")
        source = f"feed:{feed_id}"
        parsed = []
        for r in rows:
            item = build_item(owner, store_id, r, source)
            if not item:
                run["skipped"] += 1
                continue
            parsed.append(item)
        run["units_seen"] = len(parsed)

        keys = [k for k in (_key(p["attributes"]) for p in parsed) if k]
        vins = [k[4:] for k in keys if k.startswith("vin:")]
        stocks = [k[6:] for k in keys if k.startswith("stock:")]
        existing_q = {"store_id": store_id, "$or": []}
        if vins:
            existing_q["$or"].append({"attributes.vin": {"$in": vins}})
        if stocks:
            existing_q["$or"].append({"attributes.stock_number": {"$in": stocks}})
        existing = await db.inventory.find(existing_q).to_list(10000) if existing_q["$or"] else []
        by_key = {}
        for e in existing:
            attrs = e.get("attributes") or {}
            vin = (attrs.get("vin") or "").strip().upper()
            stock = (attrs.get("stock_number") or "").strip().upper()
            if vin:
                by_key.setdefault(f"vin:{vin}", e)
            if stock:
                by_key.setdefault(f"stock:{stock}", e)

        now = datetime.now(timezone.utc)
        inserts = []
        for p in parsed:
            k = _key(p["attributes"])
            hit = by_key.get(k) if k else None
            p["last_seen_at"] = now
            p["feed_id"] = feed_id
            if hit:
                sets = {"name": p["name"], "price": p["price"], "status": p["status"] if p["status"] != "available" else "available",
                        "attributes": {**(hit.get("attributes") or {}), **p["attributes"]}, "updated_at": now,
                        "last_seen_at": now, "feed_id": feed_id, "source_system": source, "is_visible": True}
                if p.get("description"):
                    sets["description"] = p["description"]
                if p.get("images"):
                    sets["images"] = p["images"]
                    sets["primary_image"] = p["images"][0]
                await db.inventory.update_one({"_id": hit["_id"]}, {"$set": sets})
                run["updated"] += 1
            else:
                inserts.append(p)
        if inserts:
            await db.inventory.insert_many(inserts)
            run["added"] = len(inserts)

        if feed.get("mark_missing_sold", True):
            res = await db.inventory.update_many(
                {"store_id": store_id, "feed_id": feed_id, "status": "available", "last_seen_at": {"$lt": started}},
                {"$set": {"status": "sold", "sold_at": now, "updated_at": now, "sold_reason": "dropped_off_feed"}})
            run["marked_sold"] = res.modified_count

        run.update({"status": "ok", "file_name": newest["name"], "fields": fields})
        await _finish_run(db, feed, run, newest)
        return run
    except Exception as e:
        run["error"] = _friendly_error(e)
        logger.warning(f"[InventoryFeed] {feed_id} failed: {e}")
        await _finish_run(db, feed, run, None)
        return run


async def _finish_run(db, feed: dict, run: dict, newest: dict | None):
    run["finished_at"] = datetime.now(timezone.utc)
    await db.inventory_feed_runs.insert_one(dict(run))
    sets = {"last_run_at": run["finished_at"], "last_status": run["status"], "last_error": run.get("error"),
            "last_counts": {k: run.get(k, 0) for k in ("units_seen", "added", "updated", "marked_sold", "skipped")}}
    if run["status"] in ("ok", "no_new_file") and newest:
        sets["last_file"] = {"name": newest["name"], "mtime": newest["mtime"], "size": newest["size"], "modified": newest["modified"]}
        sets["consecutive_failures"] = 0
        if run["status"] == "ok":
            sets["last_success_at"] = run["finished_at"]
    update = {"$set": sets}
    if run["status"] == "error":
        update["$inc"] = {"consecutive_failures": 1}
    await db.inventory_feeds.update_one({"_id": feed["_id"]}, update)
    fresh = await db.inventory_feeds.find_one({"_id": feed["_id"]})
    await _maybe_alert(db, fresh or feed, run)


async def _maybe_alert(db, feed: dict, run: dict):
    """Second failure in a row (or a feed with no new file for 3 days) raises one alert per day for the store admins."""
    failures = int(feed.get("consecutive_failures") or 0)
    stale = False
    last_ok = feed.get("last_success_at")
    if isinstance(last_ok, datetime) and datetime.now(timezone.utc) - last_ok > timedelta(days=3):
        stale = True
    if failures < 2 and not stale:
        return
    store_id = feed.get("store_id")
    admins = []
    if store_id:
        store_vals = [store_id, ObjectId(store_id)] if ObjectId.is_valid(str(store_id)) else [store_id]
        admins = [str(a["_id"]) for a in await db.users.find(
            {"store_id": {"$in": store_vals}, "role": {"$in": ["store_manager", "org_admin"]}}, {"_id": 1}).to_list(20)]
    if feed.get("created_by") and feed["created_by"] not in admins:
        admins.append(feed["created_by"])
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    label = PROVIDERS.get(feed.get("provider", "other"), PROVIDERS["other"])["label"]
    title = f"{label} inventory feed needs attention"
    body = run.get("error") or f"No new inventory file since {last_ok.strftime('%b %-d') if isinstance(last_ok, datetime) else 'setup'}."
    for uid in admins:
        idem = f"inventory_feed_issue_{feed['_id']}_{uid}_{today}"
        await db.notifications.update_one(
            {"idempotency_key": idem},
            {"$setOnInsert": {"user_id": uid, "type": "inventory_feed_issue", "title": title, "message": body,
                              "link": "/admin/inventory-feed", "feed_id": str(feed["_id"]), "idempotency_key": idem,
                              "read": False, "dismissed": False, "created_at": datetime.now(timezone.utc)}},
            upsert=True)


async def run_all_feeds(db) -> dict:
    feeds = await db.inventory_feeds.find({"enabled": {"$ne": False}}).to_list(500)
    summary = {"feeds": len(feeds), "ok": 0, "no_new_file": 0, "error": 0}
    for f in feeds:
        r = await sync_feed(db, f, force=False, triggered_by="scheduler")
        summary[r["status"]] = summary.get(r["status"], 0) + 1
    logger.info(f"[InventoryFeed] hourly sweep: {summary}")
    return summary
