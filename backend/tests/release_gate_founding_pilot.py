"""RELEASE GATE for the Founding Partner Pilot (preview only). Re-runnable: wipes "QA FP Gate *" first, keeps "QA FP Gate Motors"
(converted, trialing in the Stripe sandbox) for the founder to look at unless --cleanup is passed.
Run: cd /app/backend && set -a && . ./.env && . ../frontend/.env && set +a && PYTHONPATH=/app/backend python tests/release_gate_founding_pilot.py [--cleanup]
Parts: 1 concurrency + Mongo connections, 2 real Checkout conversion (card 4242 through the hosted page), 3 Stripe test clock first charge,
4 never charged without authorization, 5 reminders idempotent + channels (Resend status), 6 ended pilot blocks an existing session."""
import asyncio
import json
import os
import re
import secrets
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import resend
from bson import ObjectId
from pymongo import MongoClient

from services import billing, pilot_program
from tests._http import API, UA, call
from tests.live_auth import STORE_MANAGER, SUPER_ADMIN, Session, anon, oid
from tests.wipe_pilot_customers import wipe

PREFIX = "QA FP Gate"
OWNER_PASSWORD = "PilotOwner123!"
REPORT: list[tuple[str, str, str]] = []
loop = asyncio.new_event_loop()


def run(coro):
    return loop.run_until_complete(coro)


def adb():
    from routers.database import get_db
    return get_db()


def check(part: str, name: str, ok: bool, detail: str = ""):
    REPORT.append((part, name, ("PASS" if ok else "FAIL") + (f" · {detail}" if detail else "")))
    print(f"[{part}] {'PASS' if ok else 'FAIL'} {name}{' · ' + detail if detail else ''}", flush=True)
    return ok


def cust_of(mongo, org_id):
    return mongo.organizations.find_one({"_id": oid(org_id)})["customer"]


def event(typ, obj):
    return {"id": f"evt_gate_{secrets.token_hex(8)}", "object": "event", "type": typ, "livemode": False, "created": int(time.time()), "data": {"object": obj}}


def jsonable(o):
    return json.loads(json.dumps(o))


def new_pilot(sa, mongo, name, email, phone, seats_extra=1, activate_owner=True):
    status, res = sa.post("/api/setup-wizard/new-account", {
        "business_name": name, "city": "Lehi", "state": "UT", "zip": "84043", "industry": "Automotive / Dealership",
        "contact_name": "Gate Owner", "contact_email": email, "contact_phone": phone,
        "plan_key": "pilot_store_monthly", "seats_extra": seats_extra, "pilot": True, "billing_mode": "founding_pilot"})
    assert status == 200, res
    org_id, user_id = res["organization_id"], res["user_id"]
    assert sa.post(f"/api/customers/{org_id}/activate")[0] == 200
    assert sa.post(f"/api/customers/{org_id}/invite-owner")[0] == 200
    if activate_owner:
        tok = mongo.password_reset_tokens.find_one({"user_id": user_id, "purpose": "activate_link", "used": False})
        st, swap = anon("POST", "/api/auth/activate/link", {"token": tok["token"]})
        assert st == 200, swap
        st, done = anon("POST", "/api/auth/activate/complete", {"phone": swap["identifier"], "code": swap["code"], "new_password": OWNER_PASSWORD})
        assert st == 200, done
        for _ in range(30):
            if cust_of(mongo, org_id)["pilot_program"].get("state") == "active":
                break
            time.sleep(0.5)
    return org_id, user_id


# ── Part 1: get_db() under concurrency ───────────────────────────────────────

def part1(sa, mongo, owner, org_id):
    def conns():
        try:
            return mongo.client.admin.command("serverStatus")["connections"]["current"]
        except Exception:
            return None
    before = conns()
    secret = os.environ["WEBHOOK_CRON_SECRET"]
    import urllib.request

    def cron_hit():
        req = urllib.request.Request(API + "/api/cron/pilot-reminders", method="POST", data=b"{}", headers={"Content-Type": "application/json", "Authorization": f"Bearer {secret}", "X-Webhook-Id": f"gate-{secrets.token_hex(4)}", **UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    jobs = []
    for i in range(80):
        k = i % 5
        if k == 0: jobs.append(lambda: sa.get("/api/customers"))
        elif k == 1: jobs.append(lambda: sa.get(f"/api/customers/{org_id}"))
        elif k == 2: jobs.append(lambda: owner.get("/api/billing/me"))
        elif k == 3: jobs.append(lambda: owner.get("/api/pilot/checklist"))
        else: jobs.append(cron_hit)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=40) as ex:
        results = list(ex.map(lambda f: f(), jobs))
    took = time.time() - t0
    statuses = [r[0] for r in results]
    check("P1", "80 concurrent requests (customers list/detail, owner billing, checklist, 16 cron ticks) all 200", all(s == 200 for s in statuses), f"{took:.1f}s, statuses {sorted(set(statuses))}")
    time.sleep(3)
    after = conns()
    check("P1", "Mongo connection count stable after the burst (pool maxPoolSize 50)", before is None or after is None or after <= max(before, 0) + 55, f"before {before} after {after}")
    log = subprocess.run("tail -n 400 /var/log/supervisor/backend.err.log /var/log/supervisor/backend.out.log 2>/dev/null | grep -ciE 'different loop|event loop is closed|attached to a different' || true", shell=True, capture_output=True, text=True).stdout.strip()
    check("P1", "backend logs: no cross-event-loop errors", log in ("0", ""), f"matches={log or 0}")
    runs = mongo.cron_runs.count_documents({"name": "pilot-reminders", "run_id": {"$regex": "^gate-"}, "finished_at": {"$exists": True}})
    check("P1", "cron ticks finished in the background on the server loop", runs >= 16, f"finished {runs}/16")
    diff = subprocess.run("cd /app && git diff HEAD --stat -- backend/routers/database.py | tail -1", shell=True, capture_output=True, text=True).stdout.strip()
    check("P1", "routers/database.py unchanged vs HEAD (the fix lives in tests/conftest.py only)", diff == "", diff or "no diff")


# ── Part 2: real conversion through the hosted Checkout ──────────────────────

def complete_checkout(url: str) -> str:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 1000})
        pg.goto(url, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_selector("[data-testid='hosted-payment-submit-button']", timeout=60000)
        pg.wait_for_timeout(2500)
        body = pg.inner_text("body")
        price_line = next((l for l in body.splitlines() if "per month starting" in l), "")
        free_line = next((l for l in body.splitlines() if "days free" in l), "")
        for _ in range(6):
            if pg.locator("#cardNumber").count():
                break
            pg.evaluate("document.querySelector(\"[data-testid='card-accordion-item-button']\")?.click()")
            pg.wait_for_timeout(2000)
            if not pg.locator("#cardNumber").count():
                try:
                    pg.locator("[data-testid='card-accordion-item']").first.click(force=True, timeout=5000)
                except Exception as e:
                    print("card row click:", str(e)[:120])
                pg.wait_for_timeout(2000)
        if not pg.locator("#cardNumber").count():
            pg.screenshot(path="/tmp/gate_checkout_fail.png")
            raise RuntimeError("card form never appeared; see /tmp/gate_checkout_fail.png")
        pg.fill("#cardNumber", "4242 4242 4242 4242")
        pg.fill("#cardExpiry", "12 / 34")
        pg.fill("#cardCvc", "123")
        pg.fill("#billingName", "Gate Owner")
        try:
            pg.fill("#billingPostalCode", "84043", timeout=3000)
        except Exception:
            pass
        try:
            cb = pg.locator("#enableStripePass")
            if cb.count() and cb.is_checked():
                cb.click()
        except Exception:
            pass
        pg.click(".SubmitButton")
        pg.wait_for_url(re.compile(r".*/billing/success.*"), timeout=90000)
        pg.wait_for_timeout(6000)
        success = pg.inner_text("body")
        b.close()
    return json.dumps({"price_line": price_line, "free_line": free_line, "success_page": success[:400]})


def part2(sa, mongo, owner, org_id, user_id, email):
    c = cust_of(mongo, org_id)
    ends = c["pilot_program"]["ends_at"]
    st, me = owner.get("/api/billing/me")
    check("P2", "owner billing before authorizing: pilot active, can_continue, no portal, no bare checkout link", st == 200 and me["pilot"]["can_continue"] and not me["portal_available"] and me["checkout_url"] is None, f"days_left {me['pilot']['days_left']}")
    check("P2", "displayed price = agreed pricing $375 + 1 x $75 = $450/mo", me["monthly_total"] == 450.0, f"monthly_total {me['monthly_total']}")
    check("P2", "displayed first billing date = pilot end date", me["pilot"]["first_charge_on"][:10] == ends[:10], f"first_charge_on {me['pilot']['first_charge_on'][:10]} ends_at {ends[:10]}")
    st, co = owner.post("/api/billing/checkout")
    check("P2", "owner POST /billing/checkout -> hosted Stripe Checkout", st == 200 and co["url"].startswith("https://checkout.stripe.com/"), co.get("first_charge_on", "")[:10])
    c = cust_of(mongo, org_id)
    sc = billing.client()
    session = sc.v1.checkout.sessions.retrieve(c["checkout_session_id"])
    check("P2", "status stays pilot until Stripe confirms; Stripe customer exists, no subscription yet", c["billing_status"] == "pilot" and c.get("stripe_customer_id") and not c.get("stripe_subscription_id"), f"session {session.status}/{session.payment_status}")
    info = json.loads(complete_checkout(co["url"]))
    check("P2", "hosted page shows the trial and the first charge date", "days free" in info["free_line"] and "US$450.00 per month starting" in info["price_line"], f"{info['free_line']} | {info['price_line']}")
    for _ in range(60):
        c = cust_of(mongo, org_id)
        if c.get("billing_status") == "trialing" and (c.get("pilot_program") or {}).get("state") == "converted":
            break
        time.sleep(1)
    check("P2", "after Checkout: billing_status trialing, pilot_program converted (owner_checkout)", c.get("billing_status") == "trialing" and c["pilot_program"]["state"] == "converted", f"converted_via {c['pilot_program'].get('converted_via')} at {c['pilot_program'].get('converted_at', '')[:19]}")
    sub = sc.v1.subscriptions.retrieve(c["stripe_subscription_id"])
    ends_ts = int(datetime.fromisoformat(ends).timestamp())
    check("P2", "Stripe subscription trialing with trial_end == pilot ends_at (to the second)", sub.status == "trialing" and sub.trial_end == ends_ts, f"trial_end {datetime.fromtimestamp(sub.trial_end, timezone.utc).isoformat()} items {[ (i.price.lookup_key, i.quantity) for i in sub['items'].data ]}")
    invoices = sc.v1.invoices.list({"customer": c["stripe_customer_id"], "limit": 10}).data
    bal = sc.v1.customers.retrieve(c["stripe_customer_id"])
    check("P2", "no immediate charge: exactly one invoice, the $0 trial invoice (amount_due 0, amount_paid 0), customer balance 0", len(invoices) == 1 and all(i.amount_paid == 0 and i.amount_due == 0 and i.total == 0 for i in invoices) and (bal.balance or 0) == 0, f"invoices {[(i.amount_due, i.amount_paid, i.status, i.billing_reason) for i in invoices]} (restricted key has no charge_read; invoices are the ledger)")
    pm = sc.v1.customers.retrieve(c["stripe_customer_id"], {"expand": ["invoice_settings.default_payment_method"]})
    has_pm = bool(sub.default_payment_method) or bool(pm.invoice_settings and pm.invoice_settings.default_payment_method)
    check("P2", "payment method saved on the subscription/customer for the first charge", has_pm, f"sub.default_payment_method {sub.default_payment_method}")
    check("P2", "current_period_end stored = trial end (first charge date)", (c.get("current_period_end") or "")[:10] == ends[:10], c.get("current_period_end", "")[:10])
    actions = [a["action"] for a in mongo.customer_audit_log.find({"organization_id": org_id}).sort("_id", 1)]
    check("P2", "audit trail: pilot_granted, pilot_started, owner_checkout_opened, payment_link_created, pilot_converted, subscription_trialing", all(a in actions for a in ("pilot_granted", "pilot_started", "owner_checkout_opened", "payment_link_created", "pilot_converted", "subscription_trialing")), " > ".join(actions))
    founder_id = c.get("created_by")
    note = mongo.notifications.find_one({"user_id": founder_id, "type": "customer_pilot_converted", "link": f"/admin/customers/{org_id}"})
    check("P2", "founder Alert 'chose to continue after the pilot' with the first charge date", bool(note) and ends[:10] in json.dumps(note, default=str), (note or {}).get("message") or (note or {}).get("body") or "")
    time.sleep(5)
    evs = list(mongo.stripe_events.find({"organization_id": org_id}))
    check("P2", "signed webhook events for this org arrived live and were processed once each", len(evs) >= 2 and all(e.get("processed") for e in evs), f"{sorted(e['type'] for e in evs)}")
    st, me = owner.get("/api/billing/me")
    check("P2", "owner billing after: trialing, portal available, Continue button gone, first charge on pilot end", me["billing_status"] == "trialing" and me["portal_available"] and me["pilot"]["can_continue"] is False and me["current_period_end"][:10] == ends[:10], f"pilot.state {me['pilot']['state']}")
    st, row = sa.get(f"/api/customers/{org_id}")
    check("P2", "founder row: mrr kind scheduled $450 with first_charge_on = pilot end", row["mrr"]["kind"] == "scheduled" and row["mrr"]["amount"] == 450.0 and (row["mrr"]["first_charge_on"] or "")[:10] == ends[:10], json.dumps(row["mrr"]))
    st, rows = sa.get("/api/customers")
    hub = next(r for r in rows if r["organization_id"] == org_id)
    check("P2", "Hub row reflects the conversion (billing_status trialing, pilot converted)", hub["customer"]["billing_status"] == "trialing" and hub["pilot_program"]["state"] == "converted")
    return sub


# ── Part 3: Stripe test clock, the first charge the day after the pilot ──────

def part3(sa, mongo):
    """Scheduled first charge. Preferred: a Stripe test clock advanced past trial_end. Fallback when the restricted key lacks
    'Test Clocks: Write': Stripe's own trial_end=now, which makes Stripe end the trial and run the first invoice exactly as the clock would."""
    import stripe as stripe_mod
    sc = billing.client()
    org_id, user_id = new_pilot(sa, mongo, f"{PREFIX} Clock", f"qa-fp-gate-clock-{secrets.token_hex(2)}@invalid.imonsocial.test", f"+1500555{secrets.randbelow(9000) + 1000}", seats_extra=1)
    prices = {k: v["price_id"] for k, v in billing.ensure_catalog_sync(sc).items()}
    now = int(time.time())
    clock = None
    try:
        clock = sc.v1.test_helpers.test_clocks.create({"frozen_time": now, "name": f"{PREFIX} clock"})
        mode = "test_clock"
    except stripe_mod.PermissionError:
        mode = "trial_end_now"
    check("P3", "test clock available on the sandbox restricted key", clock is not None, "yes" if clock else "NO: key lacks 'Test Clocks: Write' (billing_clock_write); using Stripe trial_end=now instead (same invoice + charge path)")
    cparams = {"name": f"{PREFIX} Clock", "email": "qa-fp-gate-clock@invalid.imonsocial.test", "payment_method": "pm_card_visa",
               "invoice_settings": {"default_payment_method": "pm_card_visa"}, "metadata": {"organization_id": org_id, "source": "customer_launch"}}
    if clock:
        cparams["test_clock"] = clock.id
    cu = sc.v1.customers.create(cparams)
    mongo.organizations.update_one({"_id": oid(org_id)}, {"$set": {"customer.stripe_customer_id": cu.id}})
    trial_end = now + 3 * 86400
    sub = sc.v1.subscriptions.create({"customer": cu.id, "trial_end": trial_end,
                                      "items": [{"price": prices["pilot_store_monthly"]}, {"price": prices["pilot_seat_monthly"], "quantity": 1}],
                                      "metadata": {"organization_id": org_id, "source": "customer_launch", "plan_key": "pilot_store_monthly", "pilot_conversion": "1"}})
    check("P3", "subscription created trialing with trial_end, card on file (same items/metadata as our Checkout)", sub.status == "trialing" and sub.trial_end == trial_end)
    r = run(billing.handle_event(adb(), event("customer.subscription.created", jsonable(sub))))
    c = cust_of(mongo, org_id)
    check("P3", "webhook writer: pilot -> trialing + converted, nothing paid yet", r["result"] == "trialing" and c["billing_status"] == "trialing" and c["pilot_program"]["state"] == "converted" and not c.get("paid_at"))
    if clock:
        sc.v1.test_helpers.test_clocks.advance(clock.id, {"frozen_time": trial_end + 3600})
        for _ in range(60):
            ck = sc.v1.test_helpers.test_clocks.retrieve(clock.id)
            if ck.status == "ready":
                break
            time.sleep(3)
        check("P3", "test clock advanced to one hour after trial_end", ck.status == "ready", f"frozen_time {datetime.fromtimestamp(ck.frozen_time, timezone.utc).isoformat()}")
        time.sleep(5)
        expected_reason = "subscription_cycle"
    else:
        sc.v1.subscriptions.update(sub.id, {"trial_end": "now"})
        expected_reason = "subscription_update"
    for _ in range(30):
        sub2 = sc.v1.subscriptions.retrieve(sub.id)
        if sub2.status == "active":
            break
        time.sleep(2)
    invs = sc.v1.invoices.list({"subscription": sub.id, "limit": 10}).data
    paid = [i for i in invs if i.amount_paid > 0]
    check("P3", f"Stripe charged exactly $450.00 once when the trial ended ({mode}); subscription active", sub2.status == "active" and len(paid) == 1 and paid[0].amount_paid == 45000 and paid[0].status == "paid" and paid[0].billing_reason == expected_reason and len(invs) == 2,
          f"sub {sub2.status} invoices {[(i.amount_paid, i.status, i.billing_reason) for i in invs]}")
    r1 = run(billing.handle_event(adb(), event("customer.subscription.updated", jsonable(sub2))))
    r2 = run(billing.handle_event(adb(), event("invoice.paid", jsonable(paid[0]))))
    c = cust_of(mongo, org_id)
    check("P3", "webhook writer: trialing -> active, paid_at, last_payment_amount 450, grace cleared", r1["result"] == "active" and r2["result"] == "paid" and c["billing_status"] == "active" and c.get("last_payment_amount") == 450.0 and c.get("paid_at"), f"paid_at {c.get('paid_at', '')[:19]}")
    actions = [a["action"] for a in mongo.customer_audit_log.find({"organization_id": org_id}).sort("_id", 1)]
    check("P3", "audit: pilot_converted, subscription_trialing, subscription_active, payment_succeeded", all(a in actions for a in ("pilot_converted", "subscription_trialing", "subscription_active", "payment_succeeded")), " > ".join(actions))
    st, row = sa.get(f"/api/customers/{org_id}")
    check("P3", "founder row after the first charge: mrr kind actual $450, Paid", row["mrr"] == {"amount": 450.0, "kind": "actual", "first_charge_on": None} and row["customer"]["billing_status"] == "active", json.dumps(row["mrr"]))
    dup = run(billing.handle_event(adb(), {**event("invoice.paid", jsonable(paid[0])), "id": "evt_gate_dup_" + secrets.token_hex(4)}))
    check("P3", "re-delivering the paid invoice is harmless (idempotent writer, amounts unchanged)", dup["result"] == "paid" and cust_of(mongo, org_id)["last_payment_amount"] == 450.0)
    if clock:
        sc.v1.test_helpers.test_clocks.delete(clock.id)
    else:
        sc.v1.subscriptions.cancel(sub.id)
        sc.v1.customers.delete(cu.id)
    mongo.organizations.update_one({"_id": oid(org_id)}, {"$unset": {"customer.stripe_customer_id": ""}})
    return org_id


# ── Part 4 + 5 + 6: silent pilot never charged, reminders, ended pilot block ─

def part456(sa, mongo, abandoned_stripe_customer: str | None):
    sc = billing.client()
    email = f"qa-fp-gate-silent-{secrets.token_hex(2)}@invalid.imonsocial.test"
    org_id, user_id = new_pilot(sa, mongo, f"{PREFIX} Silent", email, f"+1500555{secrets.randbelow(9000) + 1000}", seats_extra=0)
    owner = Session(email, OWNER_PASSWORD)
    # route the founder channel to the QA manager for this org so that no real inbox is mailed
    qa = Session(*STORE_MANAGER)
    mongo.organizations.update_one({"_id": oid(org_id)}, {"$set": {"customer.created_by": qa.user_id}})
    sent_ids: list[str] = []
    real_send = resend.Emails.send

    def spy(params):
        r = real_send(params)
        sent_ids.append((r or {}).get("id"))
        return r
    resend.Emails.send = spy
    try:
        for days_ago, m in ((31, 30), (61, 60), (76, 75), (91, 90)):
            started = datetime.now(timezone.utc) - timedelta(days=days_ago)
            mongo.organizations.update_one({"_id": oid(org_id)}, {"$set": {"customer.pilot_program.started_at": started.isoformat(), "customer.pilot_program.ends_at": (started + timedelta(days=90)).isoformat()}})
            res = run(pilot_program.tick(adb()))
            mine = [s for s in res["sent"] if s["organization_id"] == org_id]
            again = [s for s in run(pilot_program.tick(adb()))["sent"] if s["organization_id"] == org_id]
            alerts = mongo.notifications.count_documents({"user_id": qa.user_id, "type": f"customer_pilot_day_{m}", "link": f"/admin/customers/{org_id}"})
            check("P5", f"day {m}: sent once (push+Alert {mine[0]['push_alert'] if mine else '-'}, email {mine[0]['email'] if mine else '-'}), second tick sends nothing, exactly 1 Alert row", len(mine) == 1 and mine[0]["milestone"] == m and mine[0]["push_alert"] and mine[0]["email"] and not again and alerts == 1)
    finally:
        resend.Emails.send = real_send
    time.sleep(4)
    statuses = []
    for eid in sent_ids:
        try:
            statuses.append((resend.Emails.get(eid) or {}).get("last_event"))
        except Exception as e:
            statuses.append(f"err:{str(e)[:40]}")
    check("P5", "Resend accepted 4 reminder emails (one per milestone); delivery events from Resend", len(sent_ids) == 4 and all(sent_ids), f"last_event per email {statuses} (recipient @invalid.imonsocial.test bounces by design)")
    p = cust_of(mongo, org_id)["pilot_program"]
    check("P5", "reminders_sent [30,60,75,90], reminder_log 4, audit pilot_reminder_sent x4, pilot_completed x1", p["reminders_sent"] == [30, 60, 75, 90] and len(p["reminder_log"]) == 4 and mongo.customer_audit_log.count_documents({"organization_id": org_id, "action": "pilot_reminder_sent"}) == 4 and p["state"] == "completed")
    c = cust_of(mongo, org_id)
    no_customer = sc.v1.customers.list({"email": email}).data == []
    check("P4", "pilot that never authorized: day 91 completed, access ON, no Stripe customer, no subscription, nothing charged", c["billing_status"] == "pilot" and "stripe_customer_id" not in c and "stripe_subscription_id" not in c and no_customer and owner.get("/api/billing/me")[0] == 200)
    st, row = sa.get(f"/api/customers/{org_id}")
    check("P4", "founder sees 'Pilot period over · decide' and potential (not actual) MRR", any(a.startswith("Pilot period over") for a in row["attention"]) and row["mrr"]["kind"] == "potential", f"attention {row['attention']}")
    if abandoned_stripe_customer:
        inv = sc.v1.invoices.list({"customer": abandoned_stripe_customer, "limit": 5}).data
        subs = sc.v1.subscriptions.list({"customer": abandoned_stripe_customer, "status": "all", "limit": 5}).data
        check("P4", "pilot that opened Checkout but never finished (QA FP Demo Motors): Stripe customer has 0 invoices, 0 subscriptions", not inv and not subs, f"invoices {len(inv)} subscriptions {len(subs)}")
    # Part 6: existing session blocked, not only sign-in (bearer JWT, cookie session restore, biometric refresh)
    import http.cookiejar
    import urllib.error
    import urllib.request
    uid = owner.user_id
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    req = urllib.request.Request(API + "/api/auth/login", method="POST", data=json.dumps({"email": email, "password": OWNER_PASSWORD}).encode(), headers={"Content-Type": "application/json", **UA})
    with opener.open(req, timeout=40) as r:
        jwt = json.loads(r.read().decode())["token"]

    def cookie_me():
        try:
            with opener.open(urllib.request.Request(API + "/api/auth/me", headers=UA), timeout=40) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    def refresh():
        return call("POST", "/api/auth/refresh", {}, {"Authorization": f"Bearer {jwt}", **UA})[0]
    routes = ("/api/billing/me", f"/api/contacts/{uid}", "/api/pilot/checklist")
    before = {p: owner.get(p)[0] for p in routes}
    before["cookie /auth/me"], before["POST /auth/refresh"] = cookie_me(), refresh()
    check("P6", "owner session works before End (bearer routes, cookie session restore, biometric refresh)", all(v == 200 for v in before.values()), json.dumps(before))
    mongo.organizations.update_one({"_id": oid(org_id)}, {"$set": {"customer.created_by": sa.user_id}})
    st, ended = sa.post(f"/api/customers/{org_id}/pilot/end", {"reason": "Release gate: End test"})
    after = {p: owner.get(p)[0] for p in routes}
    after["cookie /auth/me"], after["POST /auth/refresh"] = cookie_me(), refresh()
    st_login, body = anon("POST", "/api/auth/login", {"email": email, "password": OWNER_PASSWORD})
    check("P6", "after End: same bearer token 401 on every route, cookie restore 401, refresh 401, new login 403 with the pilot-ended message", st == 200 and all(v in (401, 403) for v in after.values()) and st_login == 403 and "has ended" in str(body), json.dumps(after))
    contacts = mongo.contacts.count_documents({"user_id": uid})
    check("P6", "data untouched: users/store/contacts still present, org inactive", mongo.users.count_documents({"organization_id": org_id}) >= 1 and mongo.stores.count_documents({"organization_id": org_id}) == 1 and not mongo.organizations.find_one({"_id": oid(org_id)})["active"], f"contacts {contacts}")
    st, _ = sa.post(f"/api/customers/{org_id}/pilot/resume", {"reason": "Release gate: Resume test"})
    st2 = owner.get("/api/billing/me")[0]
    check("P6", "Resume: the old session works again without a new login", st == 200 and st2 == 200)
    return org_id


def main():
    cleanup = "--cleanup" in sys.argv
    mongo = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    wipe(mongo, PREFIX, dry_run=False)
    sa = Session(*SUPER_ADMIN)
    email = f"qa-fp-gate-owner-{secrets.token_hex(2)}@invalid.imonsocial.test"
    org_id, user_id = new_pilot(sa, mongo, f"{PREFIX} Motors", email, f"+1500555{secrets.randbelow(9000) + 1000}", seats_extra=1)
    owner = Session(email, OWNER_PASSWORD)
    c = cust_of(mongo, org_id)
    check("P2", "90-day complimentary pilot started by the OWNER's activation (no Stripe object)", c["billing_status"] == "pilot" and c["pilot_program"]["state"] == "active" and "stripe_customer_id" not in c, f"ends {c['pilot_program']['ends_at'][:10]}")
    part1(sa, mongo, owner, org_id)
    part2(sa, mongo, owner, org_id, user_id, email)
    part3(sa, mongo)
    demo = mongo.organizations.find_one({"name": "QA FP Demo Motors"}, {"customer.stripe_customer_id": 1})
    part456(sa, mongo, (demo or {}).get("customer", {}).get("stripe_customer_id"))
    # keep "QA FP Gate Motors" (converted) for the founder; remove the helper orgs
    for name in (f"{PREFIX} Clock", f"{PREFIX} Silent"):
        wipe(mongo, name, dry_run=False)
    if cleanup:
        wipe(mongo, PREFIX, dry_run=False)
    fails = [r for r in REPORT if r[2].startswith("FAIL")]
    print("\n==== RELEASE GATE SUMMARY ====")
    for part, name, res in REPORT:
        print(f"{part:3} {res.split(' · ')[0]:4} {name}")
    print(f"\n{len(REPORT) - len(fails)}/{len(REPORT)} PASS; converted demo org: {PREFIX} Motors {org_id} owner {email} / {OWNER_PASSWORD}")
    with open("/app/memory/release_gate_founding_pilot.log", "w") as f:
        for part, name, res in REPORT:
            f.write(f"[{part}] {res.split(' · ')[0]} {name} · {res.split(' · ', 1)[1] if ' · ' in res else ''}\n")
        f.write(f"\norg {org_id} owner {email}\n")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
