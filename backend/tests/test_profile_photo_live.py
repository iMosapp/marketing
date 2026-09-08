"""Live test: profile photo upload paths (multipart, chunked, bad file) + storage-outage inline fallback."""
import asyncio, base64, io, os, sys, uuid
import httpx
from PIL import Image
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
load_dotenv("/app/backend/.env")
API = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].splitlines()[0].strip() + "/api"


def ok(label, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + label + (f"  {str(extra)[:200]}" if extra else ""))
    if not cond:
        sys.exit(1)


def jpeg(px: int) -> bytes:
    img = Image.effect_noise((px, px), 60).convert("RGB")
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=92); return buf.getvalue()


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(f"{API}/auth/login", json={"email": "qa-manager@invalid.imonsocial.test", "password": "Manager123!"})
        tok = r.json()["token"]; uid = r.json()["user"].get("id") or r.json()["user"].get("_id")
        H = {"Authorization": f"Bearer {tok}"}
        before = await db.users.find_one({"_id": ObjectId(uid)}, {"photo_url": 1, "photo_path": 1, "photo_thumb_path": 1, "photo_avatar_path": 1})

        # 1) normal multipart (3000px iPhone-ish JPEG)
        big = jpeg(3000)
        r = await c.post(f"{API}/profile/{uid}/photo", headers=H, files={"file": ("profile.jpg", big, "image/jpeg")})
        ok(f"multipart upload {len(big)//1024}KB -> 200", r.status_code == 200 and r.json().get("success"), r.text[:200])
        ok("stored in object storage (paths, not inline)", r.json()["photo_url"].startswith("/api/images/") and not r.json().get("storage_fallback"))
        img = await c.get(API[:-4] + r.json()["avatar_url"])
        ok("avatar served", img.status_code == 200 and img.headers["content-type"].startswith("image/"), img.status_code)

        # 2) chunked path (what the app falls back to on 413 / dropped request)
        b64 = base64.b64encode(jpeg(2200)).decode()
        piece = 400_000; total = (len(b64) + piece - 1) // piece
        ok("chunk test uses multiple pieces", total >= 2, total)
        up = uuid.uuid4().hex[:12]; last = None
        for i in range(total):
            r = await c.post(f"{API}/profile/{uid}/photo/chunk", headers=H,
                             json={"upload_id": up, "index": i, "total": total, "data": b64[i * piece:(i + 1) * piece], "content_type": "image/jpeg"})
            ok(f"chunk {i+1}/{total} accepted", r.status_code == 200, r.text[:150])
            last = r.json()
            if i < total - 1:
                ok("intermediate chunk does not finalize", not last.get("photo_url") and last.get("received") == i + 1, last)
        ok("last chunk assembles + saves photo", last.get("success") and last.get("photo_url", "").startswith("/api/images/"), last)
        ok("chunks cleaned up", await db.photo_upload_chunks.count_documents({"upload_id": up}) == 0)
        u = await db.users.find_one({"_id": ObjectId(uid)}, {"photo_url": 1})
        ok("user doc updated by chunked upload", u["photo_url"] == last["photo_url"])

        # 3) garbage bytes -> clear message, not 'corrupted image file' mystery
        r = await c.post(f"{API}/profile/{uid}/photo", headers=H, files={"file": ("profile.jpg", b"\xff\xd8not really a jpeg" * 50, "image/jpeg")})
        ok("undecodable file -> 400 with friendly text", r.status_code == 400 and "couldn't be read" in r.json()["detail"], r.text[:150])
        r = await c.post(f"{API}/profile/{uid}/photo/chunk", headers=H, json={"upload_id": "x", "index": 5, "total": 2, "data": "AAAA"})
        ok("bad chunk index -> 400", r.status_code == 400)

        # 4) object storage outage -> inline fallback still saves
        from utils import image_storage as st
        from routers.profile import _save_profile_photo
        real = st.put_object
        def boom(*a, **k):
            raise ConnectionError("objstore down")
        st.put_object = boom
        try:
            res = await _save_profile_photo(db, uid, jpeg(1600), "image/jpeg")
        finally:
            st.put_object = real
        ok("storage outage -> photo still saved inline", res.get("storage_fallback") and res["photo_url"].startswith("data:image/webp;base64,"), {k: str(v)[:40] for k, v in res.items()})
        ok("inline fallback stays small even for worst-case noise (<160KB)", len(res["photo_url"]) < 160_000, len(res["photo_url"]))
        u = await db.users.find_one({"_id": ObjectId(uid)}, {"photo_url": 1, "photo_avatar_path": 1})
        ok("fallback cleared stale storage paths so resolvers use photo_url", u.get("photo_avatar_path") is None and u["photo_url"].startswith("data:"))

        # 5) stale storage key auto-recovers (401 once -> re-init -> retry)
        calls = {"n": 0}
        class R:
            def __init__(self, code): self.status_code = code
            def raise_for_status(self):
                if self.status_code >= 400: raise Exception(f"HTTP {self.status_code}")
            def json(self): return {"ok": True}
        def fake_put(url, headers=None, data=None, timeout=None):
            calls["n"] += 1
            return R(401) if calls["n"] == 1 else R(200)
        inits = {"n": 0}
        def fake_init():
            inits["n"] += 1; st.storage_key = f"key{inits['n']}"; return st.storage_key
        real_put_req, real_init = st.requests.put, st.init_storage
        st.requests.put, st.init_storage = fake_put, fake_init
        try:
            out = st.put_object("imos/test/x.webp", b"123", "image/webp")
        finally:
            st.requests.put, st.init_storage = real_put_req, real_init
        ok("401 from storage -> re-init + retry succeeds", out == {"ok": True} and calls["n"] == 2 and inits["n"] == 2, (calls, inits))

        # restore original photo fields
        await db.users.update_one({"_id": ObjectId(uid)}, {"$set": {k: before.get(k) for k in ("photo_url", "photo_path", "photo_thumb_path", "photo_avatar_path")}, "$unset": {"photo_storage_fallback": ""}})
        print("\nALL PASSED")


asyncio.run(main())
