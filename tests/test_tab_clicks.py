"""
Browser test - click actual tab bar to check for errors.
"""
import asyncio
from playwright.async_api import async_playwright

APP_URL = "https://user-routing-issue.preview.emergentagent.com"

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        all_errors = []
        page_errors = []
        
        def handle_console(msg):
            if msg.type == 'error':
                all_errors.append(msg.text)
                print(f"CONSOLE ERROR: {msg.text}")
        
        def handle_pageerror(err):
            page_errors.append(str(err))
            print(f"PAGE ERROR: {str(err)}")
        
        page.on("console", handle_console)
        page.on("pageerror", handle_pageerror)
        
        await page.set_viewport_size({"width": 1920, "height": 1080})
        
        # Login
        await page.goto(APP_URL, wait_until="networkidle")
        await page.wait_for_timeout(1000)
        await page.fill('input[type="email"]', 'forest@imosapp.com')
        await page.fill('input[type="password"]', 'Admin123!')
        await page.wait_for_timeout(300)
        await page.keyboard.press('Enter')
        await page.wait_for_timeout(3000)
        print(f"After login URL: {page.url}")
        
        await page.screenshot(path=".screenshots/01_home.jpg", quality=40, full_page=False)
        all_errors.clear()
        
        # Click Contacts tab
        print("\n=== CONTACTS TAB ===")
        contacts_link = await page.query_selector('a[role="tab"][href*="contact"]')
        if contacts_link:
            await contacts_link.click()
            await page.wait_for_timeout(2000)
            print(f"URL: {page.url}")
            body = await page.evaluate("() => document.body.innerText.substring(0, 300)")
            print(f"Body: {body}")
            print(f"Error boundary: {'TRIGGERED' if 'something went wrong' in body.lower() else 'NO'}")
        else:
            print("Contacts tab link not found")
        await page.screenshot(path=".screenshots/02_contacts.jpg", quality=40, full_page=False)
        print(f"Errors: {all_errors}")
        all_errors.clear()
        
        # Click Activity tab
        print("\n=== ACTIVITY TAB ===")
        activity_link = await page.query_selector('a[role="tab"][href*="activity"]')
        if activity_link:
            await activity_link.click()
            await page.wait_for_timeout(2000)
            print(f"URL: {page.url}")
            body = await page.evaluate("() => document.body.innerText.substring(0, 300)")
            print(f"Body: {body}")
            print(f"Error boundary: {'TRIGGERED' if 'something went wrong' in body.lower() else 'NO'}")
        else:
            print("Activity tab link not found")
        await page.screenshot(path=".screenshots/03_activity.jpg", quality=40, full_page=False)
        print(f"Errors: {all_errors}")
        all_errors.clear()
        
        # Click Inbox tab
        print("\n=== INBOX TAB ===")
        inbox_link = await page.query_selector('a[role="tab"][href*="inbox"]')
        if inbox_link:
            await inbox_link.click()
            await page.wait_for_timeout(2000)
            print(f"URL: {page.url}")
            body = await page.evaluate("() => document.body.innerText.substring(0, 300)")
            print(f"Body: {body}")
            print(f"Error boundary: {'TRIGGERED' if 'something went wrong' in body.lower() else 'NO'}")
        else:
            print("Inbox tab link not found")
        await page.screenshot(path=".screenshots/04_inbox.jpg", quality=40, full_page=False)
        print(f"Errors: {all_errors}")
        all_errors.clear()
        
        # Click More/Hub tab
        print("\n=== MORE/HUB TAB ===")
        more_link = await page.query_selector('a[role="tab"][href*="more"]')
        if more_link:
            await more_link.click()
            await page.wait_for_timeout(2000)
            print(f"URL: {page.url}")
            body = await page.evaluate("() => document.body.innerText.substring(0, 300)")
            print(f"Body: {body}")
            print(f"Error boundary: {'TRIGGERED' if 'something went wrong' in body.lower() else 'NO'}")
        else:
            print("More/Hub tab link not found")
        await page.screenshot(path=".screenshots/05_more.jpg", quality=40, full_page=False)
        print(f"Errors: {all_errors}")
        all_errors.clear()
        
        print(f"\nTotal page errors: {page_errors}")
        await browser.close()

asyncio.run(run())
