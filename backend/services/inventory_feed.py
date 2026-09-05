"""
Automatic dealer inventory feeds.
Two transports, one pipeline:
  - url:  a public HTTPS file the dealer already has (Facebook / Google vehicle catalog feed from HomeNet,
          Dealer.com, DealerOn..., or a Google Sheet published as CSV). Free, default.
  - sftp: the dealer's inventory tool drops a nightly CSV on an SFTP folder we own (SFTPGo box, SFTP To Go...).
We pull, map columns (CSV / TSV / XML), upsert vehicles by VIN or stock number, and mark units that fell off
the file as sold. Every pull is recorded as a run; repeated failures raise an alert for the store admins.
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
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

import httpx
from bson import ObjectId
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

PROVIDERS = {
    "homenet": {"label": "HomeNet (Cox)", "form": "https://www.homenetauto.com/vfsr/"},
    "vauto": {"label": "vAuto (Cox)", "form": ""},
    "dealer_com": {"label": "Dealer.com", "form": "https://www.dealer.com/support/inventory/"},
    "dealeron": {"label": "DealerOn / Dealer Inspire", "form": ""},
    "sheet": {"label": "Google Sheet", "form": ""},
    "other": {"label": "Other CSV / XML feed", "form": ""},
}

# lowercased header / xml tag -> our field
CSV_HEADER_ALIASES = {
    "year": "year", "yr": "year", "modelyear": "year", "model year": "year", "model_year": "year",
    "make": "make", "manufacturer": "make",
    "model": "model",
    "trim": "trim", "series": "trim", "trim level": "trim",
    "body": "body_type", "body type": "body_type", "body_type": "body_type", "body style": "body_type", "body_style": "body_type",
    "bodystyle": "body_type", "vehicle type": "body_type", "vehicletype": "body_type",
    "type": "condition", "condition": "condition", "new/used": "condition", "newused": "condition", "new used": "condition",
    "inventory type": "condition", "vehicle condition": "condition", "state_of_vehicle": "condition", "state of vehicle": "condition",
    "certified": "certified", "cpo": "certified",
    "color": "color", "colour": "color", "exterior color": "color", "ext color": "color", "exterior": "color", "extcolor": "color",
    "ext_color": "color", "exteriorcolor": "color", "exterior_color": "color",
    "interior color": "interior_color", "int color": "interior_color", "interiorcolor": "interior_color", "interior_color": "interior_color",
    "mileage": "mileage", "miles": "mileage", "odometer": "mileage",
    "price": "price", "list price": "price", "selling price": "price", "asking price": "price", "internet price": "price",
    "internetprice": "price", "sale price": "price", "saleprice": "price", "special price": "price", "sellingprice": "price",
    "listprice": "price", "retail price": "price", "sale_price": "price",
    "msrp": "msrp",
    "stock": "stock_number", "stock#": "stock_number", "stock #": "stock_number", "stock number": "stock_number",
    "stock_number": "stock_number", "stocknumber": "stock_number", "stock no": "stock_number", "stockno": "stock_number",
    "vehicle_id": "stock_number", "vehicle id": "stock_number", "id": "stock_number",
    "vin": "vin",
    "status": "status", "availability": "status",
    "name": "name", "title": "name", "vehicle": "name", "vehicle title": "name",
    "description": "description", "desc": "description", "notes": "description", "comments": "description",
    "dealer comments": "description", "options": "options", "features": "options", "equipment": "options",
    "imagelist": "images", "image list": "images", "image_list": "images", "images": "images", "image urls": "images",
    "image_urls": "images", "imageurls": "images", "photo urls": "images", "photo_urls": "images", "photourls": "images",
    "photos": "images", "pictures": "images", "picture urls": "images", "photo url": "images", "image url": "images",
    "main photo": "images", "primary image": "images", "photo": "images", "image": "images", "image_link": "images",
    "additional_image_link": "images", "image[0].url": "images",
    "url": "listing_url", "link": "listing_url", "vdp url": "listing_url", "vdp_url": "listing_url", "vehicle url": "listing_url",
    "drivetrain": "drivetrain", "drive train": "drivetrain", "drive type": "drivetrain", "drive": "drivetrain", "drivetype": "drivetrain",
    "fuel": "fuel_type", "fuel type": "fuel_type", "fuel_type": "fuel_type", "fueltype": "fuel_type",
    "transmission": "transmission", "trans": "transmission",
    "engine": "engine", "engine description": "engine",
    "doors": "doors",
    "date in stock": "date_in_stock", "dateinstock": "date_in_stock", "date_in_stock": "date_in_stock", "inventory date": "date_in_stock",
    "dealer id": "dealer_id", "dealerid": "dealer_id", "dealer_id": "dealer_id",
}
PRICE_PRIORITY = ("internet price", "internetprice", "special price", "sale price", "saleprice", "sale_price", "selling price",
                  "sellingprice", "price", "asking price", "retail price", "list price", "listprice")

ATTR_FIELDS = ("year", "make", "model", "trim", "body_type", "condition", "certified", "color", "interior_color", "mileage",
               "stock_number", "vin", "drivetrain", "fuel_type", "transmission", "engine", "doors", "msrp", "date_in_stock", "options")


# ── secrets ───────────────────────────────────────────────────────────────────

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


# ── parsing ───────────────────────────────────────────────────────────────────

def map_headers(fieldnames: list) -> dict:
    """header -> our field; when several price columns exist the most 'internet' one wins."""
    chosen = {}
    price_cols = []
    for h in fieldnames or []:
        key = (h or "").strip().lower()
        field = CSV_HEADER_ALIASES.get(key)
        if not field:
            continue
        if field == "price":
            price_cols.append((key, h))
            continue
        if field == "images":
            chosen.setdefault("images", [])
            chosen["images"].append(h)
            continue
        chosen.setdefault(field, h)
    if price_cols:
        ranked = sorted(price_cols, key=lambda kh: PRICE_PRIORITY.index(kh[0]) if kh[0] in PRICE_PRIORITY else 99)
        chosen["price"] = ranked[0][1]
    out = {}
    for field, h in chosen.items():
        if field == "images":
            for col in h:
                out[col] = "images"
        else:
            out[h] = field
    return out


def _sniff_delimiter(text: str) -> str:
    head = text[:5000]
    try:
        return csv.Sniffer().sniff(head, delimiters=",\t|;").delimiter
    except Exception:
        return "\t" if head.count("\t") > head.count(",") else ","


def parse_csv_text(text: str, limit: int = 5000) -> tuple:
    reader = csv.DictReader(io.StringIO(text), delimiter=_sniff_delimiter(text))
    if not reader.fieldnames:
        return [], []
    header_map = map_headers(reader.fieldnames)
    if not header_map:
        return [], []
    rows = []
    for row in reader:
        data = {}
        for h, f in header_map.items():
            v = (row.get(h) or "").strip()
            if not v:
                continue
            if f == "images":
                data["images"] = (data.get("images", "") + "|" + v).strip("|")
            else:
                data[f] = v
        rows.append(data)
        if len(rows) >= limit:
            break
    return rows, sorted(set(header_map.values()))


def _xml_text(el) -> str:
    """Leaf text, or for Facebook-style nested nodes (<mileage><value>..</value><unit>MI</unit></mileage>,
    <image><url>..</url></image>) the value/url child."""
    kids = list(el)
    if not kids:
        return (el.text or "").strip()
    for tag in ("url", "value", "amount"):
        for k in kids:
            if k.tag.split("}")[-1].lower() == tag and (k.text or "").strip():
                return k.text.strip()
    return (el.text or "").strip()


def _find_records(root) -> list:
    """The repeated vehicle nodes: <listings><listing>, <vehicles><vehicle>, <rss><channel><item>..."""
    from collections import Counter
    node_list = [root]
    for _ in range(5):
        children = [c for n in node_list for c in list(n)]
        recs = [c for c in children if len(list(c)) >= 3]
        if not recs:
            return []
        top = Counter(c.tag for c in recs).most_common(1)[0][0]
        group = [c for c in recs if c.tag == top]
        if len(group) == 1:
            inner = [g for g in list(group[0]) if len(list(g)) >= 3]
            if inner and (len(inner) >= 2 or len(list(group[0])) <= 3):
                node_list = group
                continue
        return group
    return []


def parse_xml_text(text: str, limit: int = 5000) -> tuple:
    try:
        root = ET.fromstring(text.encode("utf-8") if isinstance(text, str) else text)
    except ET.ParseError:
        return [], []
    items = _find_records(root)
    rows, fields = [], set()
    for it in items:
        data = {}
        for child in it:
            tag = child.tag.split("}")[-1].lower().replace("g:", "")
            field = CSV_HEADER_ALIASES.get(tag)
            if not field:
                continue
            val = _xml_text(child)
            if not val:
                continue
            if field == "images":
                data["images"] = (data.get("images", "") + "|" + val).strip("|")
            else:
                data.setdefault(field, val)
            fields.add(field)
        if data:
            rows.append(data)
        if len(rows) >= limit:
            break
    return rows, sorted(fields)


def parse_feed_text(text: str) -> tuple:
    """(rows, fields) for CSV / TSV / pipe or XML content."""
    stripped = (text or "").lstrip()
    if stripped.startswith("<"):
        return parse_xml_text(stripped)
    return parse_csv_text(text)


def parse_inventory_csv(text: str, limit: int = 5000) -> tuple:
    rows, fields = parse_csv_text(text, limit)
    return rows, fields, 0


def split_images(raw: str) -> list:
    if not raw:
        return []
    parts = re.split(r"[|;,\s]+", raw.strip())
    seen, out = set(), []
    for p in parts:
        if p.lower().startswith("http") and p not in seen:
            seen.add(p)
            out.append(p)
    return out[:12]


def _num(raw) -> float | None:
    if raw in (None, ""):
        return None
    m = re.search(r"\d[\d,]*(?:\.\d+)?", str(raw))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except Exception:
        return None


def build_item(user_id: str, store_id, data: dict, source: str) -> dict | None:
    """One inventory doc from a mapped row. Shared by manual CSV upload and automatic feeds."""
    attributes = {}
    for f in ATTR_FIELDS:
        v = data.get(f)
        if v not in (None, ""):
            attributes[f] = str(v).strip()
    if attributes.get("mileage"):
        n = _num(attributes["mileage"])
        attributes["mileage"] = str(int(n)) if n is not None else attributes["mileage"]
    if attributes.get("vin"):
        attributes["vin"] = attributes["vin"].upper()
    if attributes.get("condition"):
        c = attributes["condition"].lower()
        attributes["condition"] = "certified" if "cpo" in c or "certified" in c else ("new" if c.startswith("new") else ("used" if "used" in c else attributes["condition"]))
    name = (data.get("name") or "").strip()
    if not name:
        name = " ".join(str(attributes.get(f, "")).strip() for f in ("year", "make", "model", "trim") if attributes.get(f)).strip()
    if not name:
        return None
    price = _num(data.get("price"))
    if price is not None and price <= 0:
        price = None
    status = (data.get("status") or "available").strip().lower() or "available"
    if status in ("in stock", "instock", "active", "live", "for sale", "in_stock", "available"):
        status = "available"
    elif status in ("sold", "out of stock", "out_of_stock", "pending", "inactive"):
        status = "sold"
    else:
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
    if data.get("listing_url", "").startswith("http"):
        doc["listing_url"] = data["listing_url"]
    return doc


# ── transports ────────────────────────────────────────────────────────────────

def normalize_feed_url(url: str) -> str:
    """Accept a Google Sheet edit link and turn it into its CSV export."""
    u = (url or "").strip()
    m = re.match(r"https://docs\.google\.com/spreadsheets/d/([\w-]+)/(?:edit|view|htmlview)?.*?(?:gid=(\d+))?$", u)
    if m and "/export" not in u and "/pub" not in u:
        gid = m.group(2) or "0"
        return f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=csv&gid={gid}"
    return u


async def _fetch_url(feed: dict, max_bytes: int = 60 * 1024 * 1024) -> str:
    url = normalize_feed_url(feed.get("feed_url", ""))
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("Feed URL must start with http:// or https://")
    auth = None
    if feed.get("feed_auth_user"):
        auth = (feed["feed_auth_user"], decrypt_secret(feed.get("feed_auth_password_enc", "")))
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=20.0), follow_redirects=True,
                                 headers={"User-Agent": "iMOnSocial-InventoryFeed/1.0"}) as client:
        async with client.stream("GET", url, auth=auth) as resp:
            if resp.status_code >= 400:
                raise ValueError(f"Feed URL returned HTTP {resp.status_code}")
            buf = io.BytesIO()
            async for chunk in resp.aiter_bytes():
                buf.write(chunk)
                if buf.tell() > max_bytes:
                    raise ValueError("Feed file larger than 60 MB")
    raw = buf.getvalue()
    try:
        return raw.decode("utf-8-sig")
    except Exception:
        return raw.decode("latin-1", errors="ignore")


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


def _friendly_error(e: Exception) -> str:
    msg = str(e) or e.__class__.__name__
    low = msg.lower()
    if isinstance(e, asyncio.TimeoutError) or "timed out" in low or "timeout" in low:
        return "Timed out reaching the feed: check the host / URL"
    if "authentication" in low:
        return "SFTP login failed: check the username and password"
    if "no such file" in low or "not found" in low:
        return "Folder or file not found: check the folder path"
    if "name or service not known" in low or "nodename" in low or "getaddrinfo" in low or "name resolution" in low:
        return "Host not found: check the host name / URL"
    if "connection refused" in low:
        return "Connection refused: check the port (SFTP is usually 22)"
    if "http 401" in low or "http 403" in low:
        return "The feed URL refused access (401/403): it must be a public link, or add a username and password"
    if "http 404" in low:
        return "The feed URL returned 404: the link is wrong or expired"
    return msg[:300]


async def fetch_feed(feed: dict, force: bool = False) -> dict:
    """Get the newest content for either transport. Returns {text, file, changed}."""
    if (feed.get("transport") or "url") == "sftp":
        files = await asyncio.wait_for(asyncio.to_thread(_list_files_sync, feed), timeout=60)
        if not files:
            raise FileNotFoundError(f"No files matching {feed.get('file_pattern') or '*.csv'} in {feed.get('remote_path') or '/'}")
        newest = files[0]
        last = feed.get("last_file") or {}
        if not force and last.get("name") == newest["name"] and last.get("mtime") == newest["mtime"] and last.get("size") == newest["size"]:
            return {"text": None, "file": newest, "changed": False}
        text = await asyncio.wait_for(asyncio.to_thread(_download_sync, feed, newest["name"]), timeout=180)
        return {"text": text, "file": newest, "changed": True}
    text = await asyncio.wait_for(_fetch_url(feed), timeout=120)
    digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
    file = {"name": normalize_feed_url(feed.get("feed_url", "")).split("?")[0].rsplit("/", 1)[-1] or "feed", "size": len(text),
            "mtime": int(datetime.now(timezone.utc).timestamp()), "hash": digest, "modified": datetime.now(timezone.utc).isoformat()}
    if not force and (feed.get("last_file") or {}).get("hash") == digest:
        return {"text": None, "file": file, "changed": False}
    return {"text": text, "file": file, "changed": True}


async def test_connection(feed: dict) -> dict:
    """Reach the feed and show what we would import, without writing anything."""
    try:
        if (feed.get("transport") or "url") == "sftp":
            files = await asyncio.wait_for(asyncio.to_thread(_list_files_sync, feed), timeout=45)
            out = {"ok": True, "files": files[:20], "file_count": len(files)}
            if files:
                text = await asyncio.wait_for(asyncio.to_thread(_download_sync, feed, files[0]["name"]), timeout=120)
                rows, fields = parse_feed_text(text)
                out.update(_preview(rows, fields))
            return out
        text = await asyncio.wait_for(_fetch_url(feed), timeout=120)
        rows, fields = parse_feed_text(text)
        return {"ok": True, "files": [], "file_count": 1, **_preview(rows, fields)}
    except Exception as e:
        return {"ok": False, "error": _friendly_error(e), "files": [], "file_count": 0, "vehicles": 0, "fields": [], "sample": []}


def _preview(rows: list, fields: list) -> dict:
    sample = []
    for r in rows[:3]:
        it = build_item("", None, r, "preview")
        if it:
            sample.append({"name": it["name"], "price": it.get("price"), "photos": len(it.get("images") or []),
                           "vin": (it["attributes"].get("vin") or "")[-6:], "stock": it["attributes"].get("stock_number", "")})
    missing = [f for f in ("vin", "stock_number", "price", "images") if f not in fields]
    return {"vehicles": len(rows), "fields": fields, "sample": sample, "missing": missing,
            "warning": ("No VIN or stock number column: vehicles cannot be matched between pulls" if "vin" not in fields and "stock_number" not in fields else None)}


def feed_public(feed: dict) -> dict:
    d = {k: v for k, v in feed.items() if k not in ("sftp_password_enc", "feed_auth_password_enc", "_id")}
    d["id"] = str(feed["_id"])
    d["has_password"] = bool(feed.get("sftp_password_enc") or feed.get("feed_auth_password_enc"))
    d["provider_label"] = PROVIDERS.get(feed.get("provider", "other"), PROVIDERS["other"])["label"]
    for k in ("created_at", "updated_at", "last_run_at", "last_success_at"):
        if isinstance(d.get(k), datetime):
            d[k] = d[k].isoformat()
    return d


# ── sync ──────────────────────────────────────────────────────────────────────

def _key(attrs: dict) -> str | None:
    vin = (attrs.get("vin") or "").strip().upper()
    if len(vin) >= 11:
        return f"vin:{vin}"
    stock = (attrs.get("stock_number") or "").strip().upper()
    if stock:
        return f"stock:{stock}"
    return None


def _scope(feed: dict) -> dict:
    return {"store_id": feed["store_id"]} if feed.get("store_id") else {"created_by_user_id": feed.get("created_by", "")}


async def sync_feed(db, feed: dict, force: bool = False, triggered_by: str = "scheduler") -> dict:
    """Pull the newest content and upsert the store's inventory. Always records a run."""
    feed_id = str(feed["_id"])
    store_id = feed.get("store_id")
    started = datetime.now(timezone.utc)
    run = {"feed_id": feed_id, "store_id": store_id, "started_at": started, "triggered_by": triggered_by,
           "status": "error", "file_name": None, "units_seen": 0, "added": 0, "updated": 0, "marked_sold": 0, "skipped": 0, "error": None}
    try:
        got = await fetch_feed(feed, force=force)
        newest = got["file"]
        if not got["changed"]:
            run.update({"status": "no_change", "file_name": newest["name"]})
            await _finish_run(db, feed, run, newest)
            return run

        rows, fields = parse_feed_text(got["text"])
        if not fields:
            raise ValueError("No recognized columns. Expected headers like VIN, Stock, Year, Make, Model, Price, ImageList")
        if not rows:
            raise ValueError("The feed has a header but no vehicles")

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
        ors = []
        if vins:
            ors.append({"attributes.vin": {"$in": vins}})
        if stocks:
            ors.append({"attributes.stock_number": {"$in": stocks}})
        existing = await db.inventory.find({**_scope(feed), "$or": ors}).to_list(10000) if ors else []
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
        seen_ids = set()
        for p in parsed:
            k = _key(p["attributes"])
            hit = by_key.get(k) if k else None
            p["last_seen_at"] = now
            p["feed_id"] = feed_id
            if hit and hit["_id"] not in seen_ids:
                seen_ids.add(hit["_id"])
                sets = {"name": p["name"], "price": p["price"], "status": p["status"],
                        "attributes": {**(hit.get("attributes") or {}), **p["attributes"]}, "updated_at": now,
                        "last_seen_at": now, "feed_id": feed_id, "source_system": source, "is_visible": True}
                if p.get("description"):
                    sets["description"] = p["description"]
                if p.get("images"):
                    sets["images"] = p["images"]
                    sets["primary_image"] = p["images"][0]
                if p.get("listing_url"):
                    sets["listing_url"] = p["listing_url"]
                await db.inventory.update_one({"_id": hit["_id"]}, {"$set": sets})
                run["updated"] += 1
            elif not hit:
                inserts.append(p)
        if inserts:
            await db.inventory.insert_many(inserts)
            run["added"] = len(inserts)

        if feed.get("mark_missing_sold", True):
            res = await db.inventory.update_many(
                {**_scope(feed), "feed_id": feed_id, "status": "available", "last_seen_at": {"$lt": started}},
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
    if run["status"] in ("ok", "no_change") and newest:
        sets["last_file"] = newest
        sets["consecutive_failures"] = 0
        if run["status"] == "ok":
            sets["last_success_at"] = run["finished_at"]
    update = {"$set": sets}
    if run["status"] == "error":
        update["$inc"] = {"consecutive_failures": 1}
    await db.inventory_feeds.update_one({"_id": feed["_id"]}, update)
    fresh = await db.inventory_feeds.find_one({"_id": feed["_id"]})
    try:
        await _maybe_alert(db, fresh or feed, run)
    except Exception as e:
        logger.debug(f"[InventoryFeed] alert step failed: {e}")


async def _maybe_alert(db, feed: dict, run: dict):
    """Two failures in a row, or no successful pull for 3 days: one alert per day to the store admins."""
    failures = int(feed.get("consecutive_failures") or 0)
    last_ok = feed.get("last_success_at")
    if isinstance(last_ok, datetime) and last_ok.tzinfo is None:
        last_ok = last_ok.replace(tzinfo=timezone.utc)
    stale = isinstance(last_ok, datetime) and datetime.now(timezone.utc) - last_ok > timedelta(days=3)
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
    title = f"Fix the {label} inventory feed"
    body = run.get("error") or f"No new inventory since {last_ok.strftime('%b %-d') if isinstance(last_ok, datetime) else 'setup'}."
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
    summary = {"feeds": len(feeds), "ok": 0, "no_change": 0, "error": 0}
    for f in feeds:
        r = await sync_feed(db, f, force=False, triggered_by="scheduler")
        summary[r["status"]] = summary.get(r["status"], 0) + 1
    logger.info(f"[InventoryFeed] hourly sweep: {summary}")
    return summary
