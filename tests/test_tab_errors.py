"""
Thorough tab navigation test with proper tab bar interaction.
Captures ALL console errors with pageerror for crashed tabs.
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
        all_console = []
        page_errors = []
        
        def handle_console(msg):
            text = msg.text
            level = msg.type
            all_console.append(f"[{level}] {text}")
            # Print everything that looks like an error or warning
            if level == 'error' or 'Error' in text or 'not defined' in text or 'Cannot read' in text:
                print(f"CONSOLE {level.upper()}: {text}")
        
        def handle_pageerror(err):
            page_errors.append(str(err))
            print(f"*** PAGE ERROR ***: {err}")
        
        page.on("console", handle_console)
        page.on("pageerror", handle_pageerror)
        
        await page.set_viewport_size({"width": 1920, "height": 1080})
        
        print("STEP 1: Login")
        await page.goto(APP_URL, wait_until="networkidle")
        await page.wait_for_timeout(1000)
        
        await page.fill('input[type="email"]', EMAIL)
        await page.fill('input[type="password"]', PASSWORD)
        await page.wait_for_timeout(300)
        
        # Click Log In button
        btns = await page.query_selector_all('button')
        for btn in btns:
            text = await btn.text_content()
            if text and ('log in' in text.lower() or 'sign in' in text.lower()):
                await btn.click()
                print(f"Clicked: {text.strip()}")
                break
        
        await page.wait_for_timeout(3000)
        print(f"URL after login: {page.url}")
        
        # Take screenshot to see current state
        await page.screenshot(path=".screenshots/home_tab.jpg", quality=40, full_page=False)
        
        # Get all links/buttons to understand the navigation
        print("\nLooking for tab bar navigation items...")
        nav_elements = await page.evaluate("""() => {
            const elements = [];
            // Look for bottom tab bar
            const allLinks = document.querySelectorAll('a, [role="tab"], [aria-label]');
            allLinks.forEach(el => {
                if (el.href || el.getAttribute('role') === 'tab') {
                    elements.push({
                        tag: el.tagName,
                        href: el.href || '',
                        role: el.getAttribute('role') || '',
                        label: el.getAttribute('aria-label') || el.textContent.trim().substring(0, 30),
                        testid: el.getAttribute('data-testid') || ''
                    });
                }
            });
            return elements;
        }""")
        
        for el in nav_elements[:30]:  # show first 30 nav elements
            print(f"  {el['tag']} href={el['href'][:60]} label={el['label'][:30]} testid={el['testid']}")
        
        # Find the actual tab bar
        print("\nSearching for tab bar structure...")
        tab_info = await page.evaluate("""() => {
            // Try to find the bottom tab bar
            const allDivs = document.querySelectorAll('div, nav');
            const tabs = [];
            allDivs.forEach(div => {
                const text = div.textContent.trim();
                if (text.includes('Contacts') || text.includes('Activity') || text.includes('Inbox') || text.includes('More')) {
                    const rect = div.getBoundingClientRect();
                    if (rect.height < 100 && rect.width > 200) {  // Likely a tab bar
                        tabs.push({
                            class: div.className.substring(0, 60),
                            text: text.substring(0, 80),
                            y: rect.y,
                            height: rect.height,
                            width: rect.width
                        });
                    }
                }
            });
            return tabs.slice(0, 10);
        }""")
        
        for t in tab_info:
            print(f"  Possible tab: y={t['y']:.0f} h={t['height']:.0f} w={t['width']:.0f} text={t['text'][:60]}")
        
        # Try to find the tab bar buttons in the bottom navigation
        print("\nLooking for bottom nav buttons...")
        bottom_nav = await page.evaluate("""() => {
            // Expo Router typically renders a tab bar at the bottom
            const elements = [];
            // Look for elements at the bottom of the screen  
            const allClickable = document.querySelectorAll('[tabindex], a, button, [role="button"], [role="tab"]');
            allClickable.forEach(el => {
                const rect = el.getBoundingClientRect();
                const text = el.textContent.trim();
                if (rect.y > 900 || (text && 
                    (text.includes('Contact') || text.includes('Activity') || 
                     text.includes('Inbox') || text.includes('More') || text.includes('Home')))) {
                    elements.push({
                        tag: el.tagName,
                        text: text.substring(0, 30),
                        href: el.href || el.getAttribute('href') || '',
                        y: rect.y,
                        x: rect.x,
                        role: el.getAttribute('role') || ''
                    });
                }
            });
            return elements.slice(0, 20);
        }""")
        
        for el in bottom_nav:
            print(f"  {el['tag']} text={el['text'][:25]} href={el['href'][:50]} y={el['y']:.0f} role={el['role']}")
        
        print("\n--- Testing direct URL navigation ---")
        
        # Test each tab by direct URL navigation
        tabs_to_test = [
            ("Contacts", f"{APP_URL}/contacts"),
            ("Activity", f"{APP_URL}/activity"),
            ("Inbox", f"{APP_URL}/inbox"),
            ("More", f"{APP_URL}/more"),
        ]
        
        for tab_name, url in tabs_to_test:
            print(f"\n{'='*50}")
            print(f"Testing: {tab_name} -> {url}")
            print('='*50)
            
            # Clear error tracking
            tab_errors = []
            tab_page_errors = []
            
            def make_handlers(name, errors, perrors):
                def ch(msg):
                    t = msg.text
                    l = msg.type
                    if l == 'error' or 'Error' in t:
                        errors.append(f"[{l}] {t}")
                        print(f"  CONSOLE {l.upper()}: {t[:200]}")
                def pe(err):
                    perrors.append(str(err))
                    print(f"  *** PAGE ERROR ***: {str(err)[:300]}")
                return ch, pe
            
            ch, pe = make_handlers(tab_name, tab_errors, tab_page_errors)
            page.on("console", ch)
            page.on("pageerror", pe)
            
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)
            
            body_text = await page.evaluate("() => document.body.innerText.substring(0, 300)")
            print(f"  Body text: {body_text[:200]}")
            
            # Check for error boundary
            if 'something went wrong' in body_text.lower():
                print(f"  *** ERROR BOUNDARY TRIGGERED ***")
                # Get all error elements
                error_els = await page.evaluate("""() => {
                    const errEls = document.querySelectorAll('[class*="error"], [id*="error"]');
                    return Array.from(errEls).map(e => e.textContent.substring(0, 200));
                }""")
                for e in error_els:
                    if e.strip():
                        print(f"  Error element: {e}")
            
            print(f"  Console errors: {len(tab_errors)}")
            print(f"  Page errors: {len(tab_page_errors)}")
            
            page.remove_listener("console", ch)
            page.remove_listener("pageerror", pe)
        
        # Test back from a tab then navigate using tab bar
        print(f"\n{'='*50}")
        print("Testing tab bar click navigation from home")
        print('='*50)
        
        await page.goto(f"{APP_URL}/home", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        
        # Get all clickable elements
        clickable_info = await page.evaluate("""() => {
            const elements = [];
            const allClickable = Array.from(document.querySelectorAll('a, button, [role="button"], [role="tab"]'));
            allClickable.forEach(el => {
                const rect = el.getBoundingClientRect();
                const text = el.textContent.trim();
                elements.push({
                    tag: el.tagName,
                    text: text.substring(0, 25),
                    href: el.href || el.getAttribute('href') || '',
                    y: rect.y,
                    visible: rect.width > 0 && rect.height > 0
                });
            });
            return elements.filter(e => e.visible).slice(0, 50);
        }""")
        
        print("All visible clickable elements (first 50):")
        for el in clickable_info:
            if el['text'] or el['href']:
                print(f"  {el['tag']} text={el['text'][:25]!r} href={el['href'][:50]} y={el['y']:.0f}")
        
        await browser.close()
        
        print(f"\n{'='*60}")
        print("SUMMARY OF ALL CONSOLE MESSAGES")
        print('='*60)
        errors_found = [m for m in all_console if '[error]' in m.lower()]
        print(f"Total error messages: {len(errors_found)}")
        print(f"Total page errors: {len(page_errors)}")
        for e in errors_found:
            print(f"  {e}")
        for e in page_errors:
            print(f"  PAGE: {e}")

asyncio.run(run())
