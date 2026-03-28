"""
Test production build served via SPA server.
The server properly handles SPA routing.
"""
import asyncio
from playwright.async_api import async_playwright

PROD_URL = "http://localhost:9002"

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        all_errors = []
        page_errors = []
        all_logs = []
        
        def handle_console(msg):
            text = msg.text
            level = msg.type
            all_logs.append(f"[{level}] {text}")
            if level == 'error' or ('Error' in text and level != 'log'):
                all_errors.append(f"[{level}] {text}")
                print(f"  CONSOLE: [{level}] {text[:300]}")
        
        def handle_pageerror(err):
            page_errors.append(str(err))
            print(f"  *** PAGE ERROR ***: {str(err)[:500]}")
        
        page.on("console", handle_console)
        page.on("pageerror", handle_pageerror)
        
        await page.set_viewport_size({"width": 1920, "height": 1080})
        
        print(f"Testing PRODUCTION build at {PROD_URL}")
        print("="*60)
        
        # Load app
        await page.goto(PROD_URL, wait_until="networkidle")
        await page.wait_for_timeout(3000)
        print(f"Initial URL: {page.url}")
        body = await page.evaluate("() => document.body.innerText.substring(0, 200)")
        print(f"Initial body: {body[:150]}")
        
        print(f"\nErrors on load: {all_errors}")
        print(f"Page errors on load: {page_errors}")
        
        # Take screenshot
        await page.screenshot(path=".screenshots/spa_initial.jpg", quality=40, full_page=False)
        
        all_errors.clear()
        page_errors.clear()
        
        # Navigate to login
        print("\n--- Login ---")
        await page.goto(f"{PROD_URL}/auth/login", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        print(f"URL: {page.url}")
        body = await page.evaluate("() => document.body.innerText.substring(0, 200)")
        print(f"Body: {body[:150]}")
        
        # Try to fill login form
        try:
            email_field = await page.wait_for_selector('input[type="email"]', timeout=3000)
            if email_field:
                await email_field.fill('forest@imosapp.com')
                await page.fill('input[type="password"]', 'Admin123!')
                await page.wait_for_timeout(300)
                await page.keyboard.press('Enter')
                await page.wait_for_timeout(4000)
                print(f"After login URL: {page.url}")
        except Exception as e:
            print(f"Login failed: {e}")
        
        print(f"Login errors: {all_errors}")
        all_errors.clear()
        page_errors.clear()
        
        # Check current page state
        body = await page.evaluate("() => document.body.innerText.substring(0, 200)")
        print(f"Post-login body: {body[:150]}")
        
        await page.screenshot(path=".screenshots/spa_home.jpg", quality=40, full_page=False)
        
        # Test navigating to contacts
        print("\n--- Contacts Tab ---")
        all_errors.clear()
        page_errors.clear()
        
        await page.goto(f"{PROD_URL}/contacts", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        print(f"URL: {page.url}")
        body = await page.evaluate("() => document.body.innerText.substring(0, 400)")
        print(f"Body: {body[:300]}")
        
        if 'something went wrong' in body.lower():
            print("*** ERROR BOUNDARY TRIGGERED ***")
        else:
            print("NO error boundary detected")
        
        print(f"Errors: {all_errors}")
        print(f"Page errors: {page_errors}")
        await page.screenshot(path=".screenshots/spa_contacts.jpg", quality=40, full_page=False)
        
        # Test activity
        print("\n--- Activity Tab ---")
        all_errors.clear()
        page_errors.clear()
        
        await page.goto(f"{PROD_URL}/activity", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        print(f"URL: {page.url}")
        body = await page.evaluate("() => document.body.innerText.substring(0, 400)")
        print(f"Body: {body[:300]}")
        
        if 'something went wrong' in body.lower():
            print("*** ERROR BOUNDARY TRIGGERED ***")
        else:
            print("NO error boundary detected")
        
        print(f"Errors: {all_errors}")
        print(f"Page errors: {page_errors}")
        await page.screenshot(path=".screenshots/spa_activity.jpg", quality=40, full_page=False)
        
        # Test inbox
        print("\n--- Inbox Tab ---")
        all_errors.clear()
        page_errors.clear()
        
        await page.goto(f"{PROD_URL}/inbox", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        print(f"URL: {page.url}")
        body = await page.evaluate("() => document.body.innerText.substring(0, 400)")
        print(f"Body: {body[:300]}")
        
        if 'something went wrong' in body.lower():
            print("*** ERROR BOUNDARY TRIGGERED ***")
        else:
            print("NO error boundary detected")
        
        print(f"Errors: {all_errors}")
        print(f"Page errors: {page_errors}")
        await page.screenshot(path=".screenshots/spa_inbox.jpg", quality=40, full_page=False)
        
        # Test more
        print("\n--- More/Hub Tab ---")
        all_errors.clear()
        page_errors.clear()
        
        await page.goto(f"{PROD_URL}/more", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        print(f"URL: {page.url}")
        body = await page.evaluate("() => document.body.innerText.substring(0, 400)")
        print(f"Body: {body[:300]}")
        
        if 'something went wrong' in body.lower():
            print("*** ERROR BOUNDARY TRIGGERED ***")
        else:
            print("NO error boundary detected")
        
        print(f"Errors: {all_errors}")
        print(f"Page errors: {page_errors}")
        await page.screenshot(path=".screenshots/spa_more.jpg", quality=40, full_page=False)
        
        print("\n=== All Console Messages ===")
        error_logs = [m for m in all_logs if '[error]' in m.lower() or 'Error' in m or 'TypeError' in m]
        for m in error_logs:
            print(f"  {m[:200]}")
        
        await browser.close()
        print("\nDone!")

asyncio.run(run())
