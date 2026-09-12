"""Live API smoke for Scripts & Practice: library, pdf (?t=), roleplay start -> 2 text turns -> end (graded), assignment create/list/cancel."""
import os
import sys
import time

import requests

API = os.environ.get("API_URL") or [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0]
API = API.rstrip("/") + "/api"


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    r.raise_for_status()
    d = r.json()
    return d.get("token") or d.get("access_token"), d["user"]


def main():
    rep_tok, rep = login("activation-tester@invalid.imonsocial.test", "NewPass123!")
    mgr_tok, mgr = login("qa-manager@invalid.imonsocial.test", "Manager123!")
    H = lambda t: {"Authorization": f"Bearer {t}"}

    lib = requests.get(f"{API}/scripts", headers=H(rep_tok), timeout=30).json()
    assert len(lib["scripts"]) >= 8 and lib["can_edit"] is False, lib.keys()
    script = next(s for s in lib["scripts"] if s["slug"] == "appointment_confirmation")
    print("library ok:", len(lib["scripts"]), "scripts; rep can_edit", lib["can_edit"])

    d = requests.get(f"{API}/scripts/{script['id']}", headers=H(rep_tok), timeout=30).json()
    assert "Activation" in d["preview"] or rep.get("name", "").split(" ")[0] in d["preview"], d["preview"][:80]
    print("detail preview merges rep name ok")

    r = requests.get(f"{API}/scripts/{script['id']}/pdf", params={"t": rep_tok}, timeout=60)
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/pdf") and r.content[:4] == b"%PDF", (r.status_code, r.headers)
    assert requests.get(f"{API}/scripts/{script['id']}/pdf", timeout=30).status_code == 401
    print("pdf ok:", len(r.content), "bytes; unauth 401 ok")

    # manager assigns to the rep with a curveball
    a = requests.post(f"{API}/scripts/mystery-shops", headers=H(mgr_tok), json={"script_id": script["id"], "rep_ids": [rep["_id"]], "curveballs": ["Her son can only come Saturday"], "note": "QA smoke"}, timeout=30)
    assert a.status_code == 200, a.text
    shop = a.json()
    lib2 = requests.get(f"{API}/scripts", headers=H(rep_tok), timeout=30).json()
    assert any(x["id"] == shop["id"] for x in lib2["my_assignments"]), lib2["my_assignments"]
    print("assignment created + visible to rep ok")

    t0 = time.time()
    s = requests.post(f"{API}/scripts/roleplay/start", headers=H(rep_tok), json={"script_id": script["id"], "assignment_id": shop["id"]}, timeout=90)
    assert s.status_code == 200, s.text
    sess = s.json()
    sid = sess["session_id"]
    print(f"start ok ({time.time()-t0:.1f}s):", sess["persona"]["name"], "->", sess["customer"]["text"], "| audio:", bool(sess["customer"]["audio_url"]))
    if sess["customer"]["audio_url"]:
        base = API[:-4]
        ar = requests.get(base + sess["customer"]["audio_url"], timeout=60)
        assert ar.status_code == 200 and len(ar.content) > 1000, (ar.status_code, len(ar.content))
        print("tts audio downloadable ok:", len(ar.content), "bytes")

    lines = [
        "Hi Janet, it's Alex at the dealership. Quick call to confirm we're still on for tomorrow at 10 to see the Enclave.",
        "Totally understand about your son. It's here and I'll hold it for you. Bring your license and the title on your trade. Would Saturday at 10 or 11 work better for both of you?",
    ]
    for ln in lines:
        t0 = time.time()
        r = requests.post(f"{API}/scripts/roleplay/{sid}/turn", headers=H(rep_tok), json={"text": ln}, timeout=120)
        assert r.status_code == 200, r.text
        out = r.json()
        print(f"turn ok ({time.time()-t0:.1f}s): customer -> {out['customer']['text'][:90]} | mood {out['customer']['mood']} | ended {out['ended']}")
        if out["ended"]:
            break

    t0 = time.time()
    e = requests.post(f"{API}/scripts/roleplay/{sid}/end", headers=H(rep_tok), timeout=180)
    assert e.status_code == 200, e.text
    res = e.json()
    print(f"end/grade ok ({time.time()-t0:.1f}s): score {res['score_pct']} card {res['scorecard_name']} adherence {res['adherence'].get('score_pct')} coaching {len(res['coaching'])}")
    assert res["evaluation_id"] and res["adherence"]["points"], res

    g = requests.get(f"{API}/scripts/roleplay/{sid}", headers=H(rep_tok), timeout=30).json()
    assert g["status"] == "completed" and g["result"]["evaluation_id"] == res["evaluation_id"] and len(g["turns"]) >= 3
    e2 = requests.post(f"{API}/scripts/roleplay/{sid}/end", headers=H(rep_tok), timeout=30).json()
    assert e2["evaluation_id"] == res["evaluation_id"], "second end should be idempotent"
    print("session get + idempotent end ok")

    shops = requests.get(f"{API}/scripts/mystery-shops/list", headers=H(mgr_tok), timeout=30).json()
    mine = next(x for x in shops["assignments"] if x["id"] == shop["id"])
    assert mine["completed"].get(rep["_id"], {}).get("session_id") == sid, mine["completed"]
    print("manager sees completion with score ok")

    # rep cannot assign; manager can cancel
    assert requests.post(f"{API}/scripts/mystery-shops", headers=H(rep_tok), json={"script_id": script["id"], "rep_ids": [rep["_id"]]}, timeout=30).status_code == 403
    assert requests.delete(f"{API}/scripts/mystery-shops/{shop['id']}", headers=H(mgr_tok), timeout=30).json()["cancelled"]
    print("rbac + cancel ok")

    # manager edit creates store copy, delete reverts
    up = requests.put(f"{API}/scripts/{script['id']}", headers=H(mgr_tok), json={"purpose": "QA edited purpose"}, timeout=30)
    assert up.status_code == 200 and up.json()["customized"] and up.json()["id"] != script["id"], up.text
    copy_id = up.json()["id"]
    lib3 = requests.get(f"{API}/scripts", headers=H(mgr_tok), timeout=30).json()
    assert sum(1 for x in lib3["scripts"] if x["slug"] == "appointment_confirmation") == 1 and next(x for x in lib3["scripts"] if x["slug"] == "appointment_confirmation")["customized"]
    assert requests.delete(f"{API}/scripts/{copy_id}", headers=H(mgr_tok), timeout=30).json()["reverts_to_default"]
    lib4 = requests.get(f"{API}/scripts", headers=H(mgr_tok), timeout=30).json()
    assert not next(x for x in lib4["scripts"] if x["slug"] == "appointment_confirmation")["customized"]
    print("store copy edit + revert ok")
    print("ALL OK")


if __name__ == "__main__":
    main()
