"""
Test script to find the exact JavaScript error causing tab crashes.
Captures ALL browser console errors during navigation.
"""
import asyncio
from playwright.async_api import async_playwright

APP_URL = "https://user-routing-issue.preview.emergentagent.com"
EMAIL = "forest@imosapp.com"
PASSWORD = "Admin123!"

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Collect ALL console messages
        console_errors = []
        console_all = []
        page_errors = []
        
        def handle_console(msg):
            text = msg.text
            level = msg.type
            console_all.append(f"[{level}] {text}")
            if level in ('error', 'warning'):
                console_errors.append(f"[{level}] {text}")
                print(f"CONSOLE {level.upper()}: {text}")
        
        def handle_pageerror(err):
            page_errors.append(str(err))
            print(f"PAGE ERROR: {err}")
        
        page.on("console", handle_console)
        page.on("pageerror", handle_pageerror)
        
        await page.set_viewport_size({"width": 1920, "height": 1080})
        
        print(f"\n{'='*60}")
        print("STEP 1: Navigate to app")
        print('='*60)
        await page.goto(APP_URL, wait_until="networkidle")
        await page.wait_for_timeout(2000)
        print(f"URL: {page.url}")
        
        # Login
        print(f"\n{'='*60}")
        print("STEP 2: Login")
        print('='*60)
        try:
            await page.wait_for_selector('input[type="email"]', timeout=5000)
            await page.fill('input[type="email"]', EMAIL)
            await page.fill('input[type="password"]', PASSWORD)
            await page.wait_for_timeout(300)
            
            # Find and click submit button
            btns = await page.query_selector_all('button')
            for btn in btns:
                text = await btn.text_content()
                if text and ('sign' in text.lower() or 'login' in text.lower() or 'log in' in text.lower()):
                    await btn.click()
                    print(f"Clicked login button: {text}")
                    break
            else:
                # Try pressing Enter
                await page.keyboard.press('Enter')
                print("Pressed Enter to submit login")
            
            await page.wait_for_timeout(3000)
            print(f"After login URL: {page.url}")
        except Exception as e:
            print(f"Login error: {e}")
        
        await page.screenshot(path=".screenshots/step1_after_login.jpg", quality=40, full_page=False)
        
        # Print any errors so far
        print(f"\nErrors so far: {len(console_errors)}")
        for e in console_errors:
            print(f"  {e}")
        
        # Clear error lists for next navigation
        console_errors.clear()
        
        # Test Contacts tab
        print(f"\n{'='*60}")
        print("STEP 3: Navigate to Contacts tab")
        print('='*60)
        try:
            # Look for tab navigation
            await page.wait_for_timeout(1000)
            
            # Try clicking contacts tab
            contacts_tab = await page.query_selector('[data-testid*="contact"], a[href*="contact"], div:has-text("Contacts")')
            if contacts_tab:
                await contacts_tab.click(force=True)
                print("Clicked contacts tab via selector")
            else:
                # Try direct navigation
                await page.goto(f"{APP_URL}/(tabs)/contacts", wait_until="domcontentloaded")
                print("Navigated directly to contacts")
            
            await page.wait_for_timeout(2000)
            print(f"Contacts URL: {page.url}")
            
            # Check for error boundary
            error_boundary = await page.query_selector_all('[class*="error"], [id*="error"]')
            body_text = await page.evaluate("() => document.body.innerText.substring(0, 500)")
            print(f"Page body (first 500 chars): {body_text}")
            
            if 'Something went wrong' in body_text or 'something went wrong' in body_text.lower():
                print("*** ERROR BOUNDARY TRIGGERED on Contacts tab ***")
            
        except Exception as e:
            print(f"Contacts nav error: {e}")
        
        print(f"\nContacts tab errors ({len(console_errors)}):")
        for e in console_errors:
            print(f"  {e}")
        for e in page_errors:
            print(f"  PAGE: {e}")
        
        await page.screenshot(path=".screenshots/step2_contacts.jpg", quality=40, full_page=False)
        console_errors.clear()
        page_errors.clear()
        
        # Test Activity tab  
        print(f"\n{'='*60}")
        print("STEP 4: Navigate to Activity tab")
        print('='*60)
        try:
            activity_tab = await page.query_selector('[data-testid*="activity"], a[href*="activity"]')
            if activity_tab:
                await activity_tab.click(force=True)
            else:
                await page.goto(f"{APP_URL}/(tabs)/activity", wait_until="domcontentloaded")
            
            await page.wait_for_timeout(2000)
            print(f"Activity URL: {page.url}")
            body_text = await page.evaluate("() => document.body.innerText.substring(0, 500)")
            print(f"Page body: {body_text}")
            if 'Something went wrong' in body_text:
                print("*** ERROR BOUNDARY TRIGGERED on Activity tab ***")
        except Exception as e:
            print(f"Activity nav error: {e}")
        
        print(f"\nActivity tab errors ({len(console_errors)}):")
        for e in console_errors:
            print(f"  {e}")
        for e in page_errors:
            print(f"  PAGE: {e}")
        
        await page.screenshot(path=".screenshots/step3_activity.jpg", quality=40, full_page=False)
        console_errors.clear()
        page_errors.clear()
        
        # Test Inbox tab
        print(f"\n{'='*60}")
        print("STEP 5: Navigate to Inbox tab")
        print('='*60)
        try:
            inbox_tab = await page.query_selector('[data-testid*="inbox"], a[href*="inbox"]')
            if inbox_tab:
                await inbox_tab.click(force=True)
            else:
                await page.goto(f"{APP_URL}/(tabs)/inbox", wait_until="domcontentloaded")
            
            await page.wait_for_timeout(2000)
            print(f"Inbox URL: {page.url}")
            body_text = await page.evaluate("() => document.body.innerText.substring(0, 500)")
            print(f"Page body: {body_text}")
            if 'Something went wrong' in body_text:
                print("*** ERROR BOUNDARY TRIGGERED on Inbox tab ***")
        except Exception as e:
            print(f"Inbox nav error: {e}")
        
        print(f"\nInbox tab errors ({len(console_errors)}):")
        for e in console_errors:
            print(f"  {e}")
        for e in page_errors:
            print(f"  PAGE: {e}")
        
        await page.screenshot(path=".screenshots/step4_inbox.jpg", quality=40, full_page=False)
        console_errors.clear()
        page_errors.clear()
        
        # Test More tab
        print(f"\n{'='*60}")
        print("STEP 6: Navigate to More/Hub tab")
        print('='*60)
        try:
            more_tab = await page.query_selector('[data-testid*="more"], a[href*="more"]')
            if more_tab:
                await more_tab.click(force=True)
            else:
                await page.goto(f"{APP_URL}/(tabs)/more", wait_until="domcontentloaded")
            
            await page.wait_for_timeout(2000)
            print(f"More URL: {page.url}")
            body_text = await page.evaluate("() => document.body.innerText.substring(0, 500)")
            print(f"Page body: {body_text}")
            if 'Something went wrong' in body_text:
                print("*** ERROR BOUNDARY TRIGGERED on More tab ***")
        except Exception as e:
            print(f"More nav error: {e}")
        
        print(f"\nMore tab errors ({len(console_errors)}):")
        for e in console_errors:
            print(f"  {e}")
        for e in page_errors:
            print(f"  PAGE: {e}")
        
        await page.screenshot(path=".screenshots/step5_more.jpg", quality=40, full_page=False)
        console_errors.clear()
        page_errors.clear()
        
        # ALL console messages (for reference)
        print(f"\n{'='*60}")
        print(f"ALL CONSOLE MESSAGES ({len(console_all)} total)")
        print('='*60)
        for msg in console_all:
            if any(kw in msg for kw in ['Error', 'error', 'TypeError', 'ReferenceError', 
                                         'not defined', 'Cannot read', 'undefined', 
                                         'Module', 'Warning', 'warn']):
                print(f"  {msg}")
        
        await browser.close()

asyncio.run(run())
