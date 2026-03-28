"""
Detailed tab content check with visible elements only.
"""
import asyncio
from playwright.async_api import async_playwright

PROD_URL = "http://localhost:9002"

async def get_visible_content(page):
    return await page.evaluate("""() => {
        // Get only visible text elements
        const walker = document.createTreeWalker(
            document.body,
            NodeFilter.SHOW_TEXT,
            {
                acceptNode: function(node) {
                    const parent = node.parentElement;
                    if (!parent) return NodeFilter.FILTER_REJECT;
                    const style = window.getComputedStyle(parent);
                    if (style.display === 'none' || style.visibility === 'hidden' || 
                        style.opacity === '0') return NodeFilter.FILTER_REJECT;
                    const rect = parent.getBoundingClientRect();
                    if (rect.width === 0 || rect.height === 0) return NodeFilter.FILTER_REJECT;
                    return NodeFilter.FILTER_ACCEPT;
                }
            }
        );
        
        let text = '';
        let node;
        while ((node = walker.nextNode())) {
            const t = node.textContent.trim();
            if (t) text += t + ' ';
        }
        return text.substring(0, 500);
    }""")

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
                print(f"  ERROR: {msg.text[:200]}")
        
        def handle_pageerror(err):
            page_errors.append(str(err))
            print(f"  *** PAGE ERROR ***: {str(err)[:400]}")
        
        page.on("console", handle_console)
        page.on("pageerror", handle_pageerror)
        
        await page.set_viewport_size({"width": 1920, "height": 1080})
        
        # Login
        print("Logging in...")
        await page.goto(PROD_URL, wait_until="networkidle")
        await page.wait_for_timeout(500)
        await page.fill('input[type="email"]', 'forest@imosapp.com')
        await page.fill('input[type="password"]', 'Admin123!')
        await page.keyboard.press('Enter')
        await page.wait_for_timeout(3000)
        
        if 'home' not in page.url:
            print(f"Login may have failed! URL: {page.url}")
            return
        
        print(f"Logged in! URL: {page.url}")
        
        # Test each tab with visible content
        tabs = [
            ('home', '/home'),
            ('contacts', '/contacts'),
            ('activity', '/activity'),
            ('inbox', '/inbox'),
            ('more', '/more'),
        ]
        
        results = {}
        
        for tab_name, tab_path in tabs:
            print(f"\n{'='*50}")
            print(f"Tab: {tab_name}")
            
            all_errors.clear()
            page_errors.clear()
            
            # Click the tab
            tab_link = await page.query_selector(f'a[href*="{tab_path}"]')
            if tab_link:
                await tab_link.click()
                await page.wait_for_timeout(2000)
            
            print(f"URL: {page.url}")
            
            # Get visible content
            visible = await get_visible_content(page)
            print(f"Visible content: {visible[:200]}")
            
            # Get screenshot
            await page.screenshot(path=f".screenshots/detail_{tab_name}.jpg", quality=40, full_page=False)
            
            # Check for crashes
            error_boundary = 'something went wrong' in visible.lower()
            
            results[tab_name] = {
                'url': page.url,
                'content': visible[:100],
                'error_boundary': error_boundary,
                'errors': list(all_errors),
                'page_errors': list(page_errors)
            }
            
            print(f"Error boundary: {error_boundary}")
            print(f"Console errors: {len(all_errors)}: {all_errors[:2]}")
            print(f"Page errors: {len(page_errors)}: {page_errors[:2]}")
        
        print("\n" + "="*60)
        print("FINAL RESULTS")
        print("="*60)
        for tab, r in results.items():
            status = "CRASH" if r['error_boundary'] else "OK"
            print(f"{tab}: {status}")
            if r['errors']:
                print(f"  Errors: {r['errors']}")
            if r['page_errors']:
                print(f"  Page errors: {r['page_errors']}")
        
        await browser.close()

asyncio.run(run())
