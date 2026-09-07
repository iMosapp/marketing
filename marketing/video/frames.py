"""Debug helper: capture a few frames per scene of a page (no audio). python frames.py welcome.html intro:500,3000,7500 next:4000,8000"""
import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).parent
OUT = Path("/tmp/wf")


async def main():
    page_file, shots = sys.argv[1], sys.argv[2:]
    OUT.mkdir(exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--force-device-scale-factor=1"])
        page = await browser.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
        page.on("console", lambda m: print("console:", m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: print("pageerror:", e))
        await page.goto(f"file://{ROOT}/{page_file}?ratio=9x16")
        await page.evaluate("window.ready")
        await page.wait_for_timeout(600)
        for s in shots:
            sid, times = s.split(":")
            await page.evaluate("([id, d]) => showScene(id, d)", [sid, 14000])
            await page.wait_for_timeout(150)
            for t in times.split(","):
                await page.evaluate("t => seek(t)", int(t))
                await page.screenshot(path=str(OUT / f"{sid}-{int(t):05d}.jpg"), type="jpeg", quality=60)
        await browser.close()
    print("ok", sorted(x.name for x in OUT.iterdir()))


asyncio.run(main())
