"""Capture the founder + pilot-owner screens for the Founder Acceptance Report (preview only)."""
import os, sys, time
from playwright.sync_api import sync_playwright

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ORG = "6acbea92a284f605698a9743"
OUT = os.path.dirname(os.path.abspath(__file__))
VIEW = {"width": 1280, "height": 900}
PHONE = {"width": 430, "height": 932}


def shot(page, name, full=False):
    path = os.path.join(OUT, f"{name}.png")
    page.screenshot(path=path, full_page=full)
    print("saved", name)


def login(page, email, password):
    page.goto(f"{BASE}/auth/login", wait_until="domcontentloaded")
    page.wait_for_selector('[data-testid="login-email-input"]', timeout=60000)
    page.fill('[data-testid="login-email-input"]', email)
    page.fill('[data-testid="login-password-input"]', password)
    page.click('[data-testid="login-button"]')
    page.wait_for_timeout(6000)
    print("logged in", email, "->", page.url)


def goto(page, path, wait_sel=None, settle=4000):
    page.goto(f"{BASE}{path}", wait_until="domcontentloaded")
    if wait_sel:
        try:
            page.wait_for_selector(wait_sel, timeout=30000)
        except Exception as e:
            print("WARN missing", wait_sel, "on", path, str(e)[:80])
    page.wait_for_timeout(settle)


def scroll_to(page, sel):
    try:
        page.locator(sel).first.scroll_into_view_if_needed(timeout=10000)
        page.wait_for_timeout(800)
        return True
    except Exception as e:
        print("WARN cannot scroll to", sel, str(e)[:80])
        return False


def founder(p):
    b = p.chromium.launch()
    ctx = b.new_context(viewport=VIEW)
    page = ctx.new_page()
    page.on("dialog", lambda d: d.accept())
    login(page, "forest@imosapp.com", "Admin123!")

    goto(page, "/admin/onboarding-hub", '[data-testid="hub-customers"]', 6000)
    scroll_to(page, f'[data-testid="hub-customer-{ORG}"]')
    shot(page, "01_founder_hub_customers")

    goto(page, f"/admin/customers/{ORG}", '[data-testid="customer-progress-card"]', 7000)
    shot(page, "02_founder_customer_page_top")
    if scroll_to(page, '[data-testid="billing-panel"]'):
        shot(page, "03_founder_billing_panel")
    if scroll_to(page, '[data-testid="customer-progress-card"]'):
        shot(page, "04_founder_progress_and_issues")
    if scroll_to(page, '[data-testid="customer-issues"]'):
        shot(page, "05_founder_questions_problems")
    shot(page, "06_founder_customer_page_full", full=True)

    goto(page, "/admin/bug-reports", None, 6000)
    shot(page, "07_founder_bug_reports_admin")

    goto(page, "/onboarding/new-account", '[data-testid="start-onboarding-btn"]', 5000)
    shot(page, "08_founder_new_customer_form")
    b.close()


def owner(p):
    b = p.chromium.launch()
    ctx = b.new_context(viewport=PHONE, device_scale_factor=2, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    page.on("dialog", lambda d: d.accept())
    login(page, "qa-accept-owner@invalid.imonsocial.test", "AcceptOwner123!")
    page.wait_for_timeout(3000)
    try:
        page.wait_for_selector('[data-testid="home-pilot"]', timeout=30000)
    except Exception:
        goto(page, "/home", '[data-testid="home-pilot"]', 5000)
    shot(page, "10_pilot_home_top")
    shot(page, "11_pilot_home_full", full=True)

    goto(page, "/more", '[data-testid="more-pilot"]', 5000)
    shot(page, "12_pilot_more_menu")

    goto(page, "/report-bug?from=home", '[data-testid="report-category-question"]', 5000)
    shot(page, "13_pilot_send_feedback")

    goto(page, "/settings/billing", '[data-testid="billing-me-card"]', 7000)
    shot(page, "14_pilot_owner_billing")

    goto(page, "/contacts", None, 6000)
    shot(page, "15_pilot_contacts_tab")

    goto(page, "/voice-memos", None, 6000)
    shot(page, "16_pilot_voice_memos")
    b.close()


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    with sync_playwright() as p:
        if which in ("all", "founder"):
            founder(p)
        if which in ("all", "owner"):
            owner(p)
    print("DONE")
