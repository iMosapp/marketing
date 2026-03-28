"""
Test the PRODUCTION BUILD (static export) for tab crashes.
This is the key test - the dev server works but production crashes.
"""
import asyncio
from playwright.async_api import async_playwright

# Test the production build served locally
PROD_URL = "http://localhost:9001"
PROD_EMAIL = "forest@imosapp.com"
PROD_PASSWORD = "Admin123!"

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        all_errors = []
        page_errors = []
        
        def handle_console(msg):
            text = msg.text
            level = msg.type
            if level == 'error':
                all_errors.append(text)
                print(f"CONSOLE ERROR: {text[:300]}")
            elif level == 'warning' and ('Error' in text or 'error' in text.lower()):
                print(f"CONSOLE WARNING: {text[:200]}")
        
        def handle_pageerror(err):
            page_errors.append(str(err))
            print(f"*** PAGE ERROR ***: {str(err)[:400]}")
        
        page.on("console", handle_console)
        page.on("pageerror", handle_pageerror)
        
        await page.set_viewport_size({"width": 1920, "height": 1080})
        
        print("=== Testing PRODUCTION build ===")
        print(f"URL: {PROD_URL}")
        
        # Load the production build
        await page.goto(f"{PROD_URL}/auth/login", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        print(f"Current URL: {page.url}")
        
        # Check if we're on login page
        body = await page.evaluate("() => document.body.innerText.substring(0, 200)")
        print(f"Initial body: {body[:150]}")
        
        # Try to login
        try:
            await page.fill('input[type="email"]', PROD_EMAIL)
            await page.fill('input[type="password"]', PROD_PASSWORD)
            await page.wait_for_timeout(300)
            await page.keyboard.press('Enter')
            await page.wait_for_timeout(4000)
            print(f"After login URL: {page.url}")
        except Exception as e:
            print(f"Login failed: {e}")
        
        body = await page.evaluate("() => document.body.innerText.substring(0, 200)")
        print(f"After login body: {body[:150]}")
        print(f"Errors so far: {all_errors}")
        
        # Navigate to contacts tab
        print("\n=== Contacts tab ===")
        all_errors.clear()
        page_errors.clear()
        
        try:
            # Try tab bar click first
            contacts_link = await page.query_selector('a[role="tab"][href*="contact"]')
            if contacts_link:
                await contacts_link.click()
                await page.wait_for_timeout(2000)
            else:
                await page.goto(f"{PROD_URL}/contacts", wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)
            
            print(f"URL: {page.url}")
            body = await page.evaluate("() => document.body.innerText.substring(0, 300)")
            print(f"Body: {body[:200]}")
            
            # Check for error boundary
            error_text = await page.evaluate("""() => {
                const errEls = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
                return errEls.map(e => e.textContent).join(', ');
            }""")
            if error_text.strip():
                print(f"Error elements: {error_text[:300]}")
            
            if 'something went wrong' in body.lower():
                print("*** ERROR BOUNDARY TRIGGERED ***")
            else:
                print("OK - no error boundary")
        except Exception as e:
            print(f"Error: {e}")
        
        print(f"Console errors: {all_errors}")
        print(f"Page errors: {page_errors}")
        
        await page.screenshot(path=".screenshots/prod_contacts.jpg", quality=40, full_page=False)
        
        # Navigate to activity
        print("\n=== Activity tab ===")
        all_errors.clear()
        page_errors.clear()
        
        try:
            activity_link = await page.query_selector('a[role="tab"][href*="activity"]')
            if activity_link:
                await activity_link.click()
                await page.wait_for_timeout(2000)
            else:
                await page.goto(f"{PROD_URL}/activity", wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)
            
            print(f"URL: {page.url}")
            body = await page.evaluate("() => document.body.innerText.substring(0, 300)")
            print(f"Body: {body[:200]}")
            
            if 'something went wrong' in body.lower():
                print("*** ERROR BOUNDARY TRIGGERED ***")
            else:
                print("OK - no error boundary")
        except Exception as e:
            print(f"Error: {e}")
        
        print(f"Console errors: {all_errors}")
        print(f"Page errors: {page_errors}")
        
        await page.screenshot(path=".screenshots/prod_activity.jpg", quality=40, full_page=False)
        
        # Navigate to inbox
        print("\n=== Inbox tab ===")
        all_errors.clear()
        page_errors.clear()
        
        try:
            inbox_link = await page.query_selector('a[role="tab"][href*="inbox"]')
            if inbox_link:
                await inbox_link.click()
                await page.wait_for_timeout(2000)
            else:
                await page.goto(f"{PROD_URL}/inbox", wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)
            
            print(f"URL: {page.url}")
            body = await page.evaluate("() => document.body.innerText.substring(0, 300)")
            print(f"Body: {body[:200]}")
            
            if 'something went wrong' in body.lower():
                print("*** ERROR BOUNDARY TRIGGERED ***")
            else:
                print("OK - no error boundary")
        except Exception as e:
            print(f"Error: {e}")
        
        print(f"Console errors: {all_errors}")
        print(f"Page errors: {page_errors}")
        
        await page.screenshot(path=".screenshots/prod_inbox.jpg", quality=40, full_page=False)
        
        # Navigate to more
        print("\n=== More/Hub tab ===")
        all_errors.clear()
        page_errors.clear()
        
        try:
            more_link = await page.query_selector('a[role="tab"][href*="more"]')
            if more_link:
                await more_link.click()
                await page.wait_for_timeout(2000)
            else:
                await page.goto(f"{PROD_URL}/more", wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)
            
            print(f"URL: {page.url}")
            body = await page.evaluate("() => document.body.innerText.substring(0, 300)")
            print(f"Body: {body[:200]}")
            
            if 'something went wrong' in body.lower():
                print("*** ERROR BOUNDARY TRIGGERED ***")
            else:
                print("OK - no error boundary")
        except Exception as e:
            print(f"Error: {e}")
        
        print(f"Console errors: {all_errors}")
        print(f"Page errors: {page_errors}")
        
        await page.screenshot(path=".screenshots/prod_more.jpg", quality=40, full_page=False)
        
        print("\n=== Summary ===")
        print(f"Total page errors: {len(page_errors)}")
        for e in page_errors:
            print(f"  {e}")
        
        await browser.close()

asyncio.run(run())
