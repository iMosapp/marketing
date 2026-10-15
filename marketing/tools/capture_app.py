"""Capture real app screens of the fictional marketing demo workspace (preview only).
Run: python /app/marketing/tools/capture_app.py home "marcus=contact/<id>|Full intel" voice-memos ...   (PNG 390x844 @2x -> /app/marketing/tools/shots/)"""
import asyncio
import os
import sys

from playwright.async_api import async_playwright

BASE = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0]
EMAIL, PASSWORD = "marketing-demo@invalid.imonsocial.test", "DemoShots123!"
OUT = "/app/marketing/tools/shots"


async def main(targets):
    os.makedirs(OUT, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, color_scheme="dark")
        page = await ctx.new_page()
        await page.goto(f"{BASE}/auth/login", wait_until="domcontentloaded")
        await page.wait_for_selector('[data-testid="login-email-input"]', timeout=60000)
        await page.fill('[data-testid="login-email-input"]', EMAIL)
        await page.fill('[data-testid="login-password-input"]', PASSWORD)
        await page.click('[data-testid="login-button"]')
        await page.wait_for_timeout(6000)
        uid = await page.evaluate("""() => { for (const k of Object.keys(localStorage)) { const v = localStorage.getItem(k) || '';
            const m = v.match(/"_id":"([a-f0-9]{24})"/); if (m) return m[1]; } return null; }""")
        print("uid", uid)
        if uid:
            await page.evaluate(f"""() => {{ localStorage.setItem('welcome_tour_v1_{uid}', '1'); localStorage.setItem('welcome_video_v1_{uid}', '1'); }}""")
        skip = page.locator('[data-testid="biometric-offer-skip"]')
        if await skip.count():
            await skip.first.click()
        for t in targets:
            name, _, path = t.partition("=")
            path, _, click = (path or name).partition("|")
            click, _, scroll = click.partition("|")
            await page.evaluate(f"() => {{ window.history.pushState({{}}, '', '/{path}'); window.dispatchEvent(new PopStateEvent('popstate')); }}")
            await page.wait_for_timeout(int(os.environ.get("WAIT", "7000")))
            if click:
                await page.get_by_text(click, exact=False).first.click()
                await page.wait_for_timeout(int(os.environ.get("CLICK_WAIT", "3000")))
            if scroll:
                await page.mouse.move(195, 600)
                await page.mouse.wheel(0, int(scroll))
                await page.wait_for_timeout(1500)
            await page.screenshot(path=f"{OUT}/{name.replace('/', '_')}.png")
            print("saved", name, page.url)
        await b.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or ["home"]))
