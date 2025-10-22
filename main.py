from flask import Flask, request, jsonify
from playwright.async_api import async_playwright
import asyncio
import os
import threading
import time
import requests
from urllib.parse import urlparse

app = Flask(__name__)

def get_retailer_domain(url):
    return urlparse(url).netloc.lower()

@app.route('/scrape-product', methods=['POST'])
def scrape_product():
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'error': 'Missing product URL'}), 400

    async def run_scraper():
        domain = get_retailer_domain(url)
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--disable-dev-shm-usage'])
            context = await browser.new_context(ignore_https_errors=True)
            page = await context.new_page()

            price = None
            image_url = None

            try:
                await page.goto(url, timeout=90000)
                await page.wait_for_load_state('networkidle')
                # give extra time for dynamic loading
                await page.wait_for_timeout(6000)

                # -------------------------
                # LOWE’S
                # -------------------------
                if "lowes.com" in domain:
                    ## update selector
                    try:
                        await page.wait_for_selector('div[data-testid="product-details-price"] span', timeout=15000)
                        el = await page.query_selector('div[data-testid="product-details-price"] span')
                        price = await el.inner_text() if el else None
                        print("[DEBUG] Lowe’s primary price selector found:", price)
                    except Exception as e:
                        print("[DEBUG] Lowe’s primary price selector failed:", e)
                        pass

                    if not price:
                        # fallback
                        dollar_span = await page.query_selector('span.item-price-dollar')
                        cent_div   = await page.query_selector('div.item-price-cent')
                        dollar = await dollar_span.inner_text() if dollar_span else ''
                        cent   = await cent_div.inner_text()   if cent_div else ''
                        if dollar:
                            price = f"${dollar}{cent}"
                        print("[DEBUG] Lowe’s fallback price:", price)

                    img = await page.query_selector('meta[property="og:image"]')
                    image_url = await img.get_attribute('content') if img else None
                    print("[DEBUG] Lowe’s image_url:", image_url)

                # -------------------------
                # HOME DEPOT
                # -------------------------
                elif "homedepot.com" in domain:
                    try:
                        await page.wait_for_selector('span.price__dollars', timeout=15000)
                        el = await page.query_selector('span.price__dollars')
                        cents_el = await page.query_selector('span.price__cents')
                        dollars = await el.inner_text() if el else None
                        cents   = await cents_el.inner_text() if cents_el else ''
                        if dollars:
                            price = f"${dollars}{cents}"
                        print("[DEBUG] Home Depot primary selector price:", price)
                    except Exception as e:
                        print("[DEBUG] Home Depot primary selector failed:", e)
                        pass

                    if not price:
                        el = await page.query_selector('meta[itemprop="price"]')
                        price = await el.get_attribute('content') if el else None
                        print("[DEBUG] Home Depot meta price fallback:", price)

                    img = await page.query_selector('meta[property="og:image"]')
                    image_url = await img.get_attribute('content') if img else None
                    print("[DEBUG] Home Depot image_url:", image_url)

                # -------------------------
                # AMAZON
                # -------------------------
                elif "amazon.com" in domain:
                    try:
                        await page.wait_for_selector('span.a-price span.a-offscreen', timeout=15000)
                        el = await page.query_selector('span.a-price span.a-offscreen')
                        price = await el.inner_text() if el else None
                        print("[DEBUG] Amazon primary selector price:", price)
                    except Exception as e:
                        print("[DEBUG] Amazon primary selector failed:", e)
                        pass

                    if not price:
                        for selector in ['#priceblock_ourprice', '#priceblock_dealprice', '#priceblock_saleprice']:
                            el = await page.query_selector(selector)
                            if el:
                                price = await el.inner_text()
                                print(f"[DEBUG] Amazon fallback {selector} price:", price)
                                break

                    img = await page.query_selector('#landingImage')
                    image_url = await img.get_attribute('src') if img else None
                    print("[DEBUG] Amazon image_url:", image_url)

                # -------------------------
                # WALMART
                # -------------------------
                elif "walmart.com" in domain:
                    try:
                        await page.wait_for_selector('span[itemprop="price"]', timeout=15000)
                        el = await page.query_selector('span[itemprop="price"]')
                        price = await el.inner_text() if el else None
                        print("[DEBUG] Walmart primary selector price:", price)
                    except Exception as e:
                        print("[DEBUG] Walmart primary selector failed:", e)
                        pass

                    if not price:
                        el = await page.query_selector('[data-automation-id="product-price"]')
                        price = await el.inner_text() if el else None
                        print("[DEBUG] Walmart fallback price:", price)

                    img = await page.query_selector('meta[property="og:image"]')
                    image_url = await img.get_attribute('content') if img else None
                    print("[DEBUG] Walmart image_url:", image_url)

                # -------------------------
                # GENERAL fallback
                # -------------------------
                if not image_url:
                    og_img = await page.query_selector('meta[property="og:image"]')
                    image_url = await og_img.get_attribute('content') if og_img else None
                    print("[DEBUG] General fallback image_url:", image_url)

                if not price:
                    meta_price = await page.query_selector('meta[itemprop="price"]')
                    price = await meta_price.get_attribute('content') if meta_price else None
                    print("[DEBUG] General fallback meta price:", price)

                await browser.close()
                return {
                    'image_url': image_url if image_url else 'Not found',
                    'price': price.strip() if price else 'Not found'
                }

            except Exception as e:
                await browser.close()
                return {'error': f'Scraping failed: {str(e)}'}

    try:
        result = asyncio.run(asyncio.wait_for(run_scraper(), timeout=120))
        return jsonify(result)
    except asyncio.TimeoutError:
        return jsonify({'error': 'Scraping timed out'}), 504

@app.route('/')
def home():
    return "Service is running"

def keep_alive():
    def ping():
        while True:
            try:
                requests.get("https://your-app-url.onrender.com")
                print("[INFO] Keep‑alive ping successful")
            except Exception as e:
                print(f"[WARNING] Keep‑alive ping failed: {e}")
            time.sleep(30)

    thread = threading.Thread(target=ping)
    thread.daemon = True
    thread.start()

keep_alive()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))