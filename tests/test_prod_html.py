"""
Test the production build HTML files directly.
"""
import asyncio
from playwright.async_api import async_playwright

PROD_URL = "http://localhost:9001"

async def test_tab(page, tab_name, url, all_errors, page_errors):
    all_errors.clear()
    page_errors.clear()
    
    print(f"\n{'='*50}")
    print(f"Testing: {tab_name} -> {url}")
    print('='*50)
    
    await page.goto(url, wait_until="networkidle")
    await page.wait_for_timeout(3000)
    
    current_url = page.url
    print(f"URL: {current_url}")
    
    body = await page.evaluate("() => document.body.innerText.substring(0, 500)")
    print(f"Body: {body[:300]}")
    
    if 'something went wrong' in body.lower():
        print("*** ERROR BOUNDARY TRIGGERED ***")
    else:
        print("OK - no obvious error boundary")
    
    # Check for React error boundary specifically
    error_el = await page.query_selector_all('[class*="ErrorBoundary"], [class*="error-boundary"]')
    if error_el:
        print(f"Found error boundary elements: {len(error_el)}")
    
    # Check all error elements
    error_text = await page.evaluate("""() => {
        const errEls = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
        return errEls.map(e => e.textContent.trim()).filter(t => t).join(' | ');
    }""")
    if error_text:
        print(f"Error elements text: {error_text[:200]}")
    
    print(f"Console errors ({len(all_errors)}): {all_errors[:5]}")
    print(f"Page errors ({len(page_errors)}): {page_errors[:3]}")

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
                print(f"  CONSOLE ERROR: {msg.text[:200]}")
        
        def handle_pageerror(err):
            page_errors.append(str(err))
            print(f"  *** PAGE ERROR ***: {str(err)[:400]}")
        
        page.on("console", handle_console)
        page.on("pageerror", handle_pageerror)
        
        await page.set_viewport_size({"width": 1920, "height": 1080})
        
        # Test home.html
        await test_tab(page, "home.html (SHOULD WORK)", f"{PROD_URL}/home.html", all_errors, page_errors)
        await page.screenshot(path=".screenshots/prod_home_html.jpg", quality=40, full_page=False)
        
        # Test contacts.html 
        await test_tab(page, "contacts.html", f"{PROD_URL}/contacts.html", all_errors, page_errors)
        await page.screenshot(path=".screenshots/prod_contacts_html.jpg", quality=40, full_page=False)
        
        # Test activity.html
        await test_tab(page, "activity.html", f"{PROD_URL}/activity.html", all_errors, page_errors)
        await page.screenshot(path=".screenshots/prod_activity_html.jpg", quality=40, full_page=False)
        
        # Test inbox.html
        await test_tab(page, "inbox.html", f"{PROD_URL}/inbox.html", all_errors, page_errors)
        await page.screenshot(path=".screenshots/prod_inbox_html.jpg", quality=40, full_page=False)
        
        # Test more.html
        await test_tab(page, "more.html", f"{PROD_URL}/more.html", all_errors, page_errors)
        await page.screenshot(path=".screenshots/prod_more_html.jpg", quality=40, full_page=False)
        
        await browser.close()

asyncio.run(run())
