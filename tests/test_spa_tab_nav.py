"""
Test production build with PROPER tab bar navigation (no direct URL).
Login first, then click tab bar links.
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
            if level == 'error':
                all_errors.append(f"[{level}] {text}")
                print(f"  CONSOLE ERROR: {text[:300]}")
            elif 'Error' in text or 'error' in text.lower():
                if level == 'warn':
                    print(f"  CONSOLE WARN: {text[:200]}")
        
        def handle_pageerror(err):
            page_errors.append(str(err))
            print(f"  *** PAGE ERROR ***: {str(err)[:500]}")
        
        page.on("console", handle_console)
        page.on("pageerror", handle_pageerror)
        
        await page.set_viewport_size({"width": 1920, "height": 1080})
        
        print(f"PRODUCTION BUILD - Tab Navigation Test")
        print(f"URL: {PROD_URL}")
        print("="*60)
        
        # Login
        await page.goto(PROD_URL, wait_until="networkidle")
        await page.wait_for_timeout(1000)
        
        email_input = await page.wait_for_selector('input[type="email"]', timeout=5000)
        await email_input.fill('forest@imosapp.com')
        await page.fill('input[type="password"]', 'Admin123!')
        await page.wait_for_timeout(300)
        await page.keyboard.press('Enter')
        await page.wait_for_timeout(3000)
        
        print(f"After login URL: {page.url}")
        body = await page.evaluate("() => document.body.innerText.substring(0, 200)")
        print(f"Home body: {body[:150]}")
        
        await page.screenshot(path=".screenshots/prod_login_success.jpg", quality=40, full_page=False)
        
        if 'home' not in page.url.lower() and 'touchpoint' not in page.url.lower():
            print("ERROR: Login may have failed!")
            return
        
        print("\nLogin successful! Now testing tab navigation...")
        all_errors.clear()
        page_errors.clear()
        
        # Find all tab bar links
        tab_links = await page.evaluate("""() => {
            const links = Array.from(document.querySelectorAll('a[role="tab"], [role="tablist"] a'));
            return links.map(l => ({
                href: l.href,
                text: l.textContent.trim().substring(0, 30),
                role: l.getAttribute('role')
            }));
        }""")
        print(f"\nFound {len(tab_links)} tab links:")
        for t in tab_links:
            print(f"  {t['text'][:25]} -> {t['href']}")
        
        # Click each tab
        tabs_to_test = ['contact', 'activity', 'inbox', 'more']
        
        for tab_keyword in tabs_to_test:
            print(f"\n{'='*50}")
            print(f"Testing tab: {tab_keyword}")
            print('='*50)
            
            all_errors.clear()
            page_errors.clear()
            
            # Find the tab link
            tab_link = None
            for t in tab_links:
                if tab_keyword in t['href'].lower():
                    tab_link = t['href']
                    break
            
            if tab_link:
                # Click via JavaScript navigation (avoid page reload)
                element = await page.query_selector(f'a[href*="{tab_keyword}"][role="tab"]')
                if element:
                    await element.click()
                    await page.wait_for_timeout(2000)
                    print(f"Clicked tab, URL: {page.url}")
                else:
                    # Try clicking by href
                    element = await page.query_selector(f'a[href*="{tab_keyword}"]')
                    if element:
                        await element.click()
                        await page.wait_for_timeout(2000)
                        print(f"Clicked link, URL: {page.url}")
                    else:
                        print(f"Could not find tab link for {tab_keyword}")
                        continue
            else:
                print(f"No tab link found for {tab_keyword}")
                continue
            
            body = await page.evaluate("() => document.body.innerText.substring(0, 400)")
            print(f"Body: {body[:300]}")
            
            if 'something went wrong' in body.lower():
                print("*** ERROR BOUNDARY TRIGGERED ***")
            else:
                print("NO error boundary")
            
            # Check for error elements
            err_text = await page.evaluate("""() => {
                const errEls = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
                return errEls.map(e => e.textContent.trim()).filter(t => t).join(' | ');
            }""")
            if err_text:
                print(f"Error elements: {err_text[:200]}")
            
            print(f"Console errors: {all_errors}")
            print(f"Page errors: {page_errors}")
            
            await page.screenshot(path=f".screenshots/prod_{tab_keyword}.jpg", quality=40, full_page=False)
        
        # Print ALL collected errors
        print("\n" + "="*60)
        print("ALL COLLECTED LOG MESSAGES")
        print("="*60)
        error_messages = [m for m in all_logs if '[error]' in m.lower()]
        print(f"Error messages: {len(error_messages)}")
        for m in error_messages:
            print(f"  {m[:300]}")
        
        print(f"\nPage errors: {len(page_errors)}")
        for e in page_errors:
            print(f"  {e[:300]}")
        
        await browser.close()
        print("\nTest complete!")

asyncio.run(run())
