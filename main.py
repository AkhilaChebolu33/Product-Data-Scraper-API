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
            context = await browser.new_context(
                ignore_https_errors=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/118.0.5993.118 Safari/537.36",
                viewport={"width": 1280, "height": 720}
            )
            page = await context.new_page()

            price = None
            image_url = None

            try:
                await page.goto(url, timeout=60000)
                await page.wait_for_load_state('networkidle')
                await page.wait_for_timeout(4000)

                # -------------------------
                # LOWE'S
                # -------------------------
                if "lowes.com" in domain:
                    try:
                        await page.wait_for_selector('div[data-testid="product-details-price"] span', timeout=15000)
                        el = await page.query_selector('div[data-testid="product-details-price"] span')
                        price = await el.inner_text() if el else None
                        print("[DEBUG] Lowe's price:", price)
                    except Exception as e:
                        print("[DEBUG] Lowe's price selector failed:", e)
                        pass

                    img = await page.query_selector('meta[property="og:image"]')
                    image_url = await img.get_attribute('content') if img else None
                    print("[DEBUG] Lowe's image URL:", image_url)

                # -------------------------
                # HOME DEPOT
                # -------------------------
                elif "homedepot.com" in domain:
                    try:
                        await page.wait_for_selector('span[data-automation-id="product-price"]', timeout=15000)
                        el = await page.query_selector('span[data-automation-id="product-price"]')
                        price = await el.inner_text() if el else None
                        print("[DEBUG] Home Depot price:", price)
                    except Exception as e:
                        print("[DEBUG] Home Depot price selector failed:", e)

                    img = await page.query_selector('meta[property="og:image"]')
                    image_url = await img.get_attribute('content') if img else None
                    print("[DEBUG] Home Depot image URL:", image_url)

                # -------------------------
                # AMAZON
                # -------------------------
                elif "amazon.com" in domain:
                    price_selectors = [
                        'span#corePriceDisplay_desktop_feature_div span.a-price span.a-offscreen',
                        'span.a-price span.a-offscreen',
                        '#priceblock_ourprice',
                        '#priceblock_dealprice',
                        '#priceblock_saleprice'
                    ]
                    for selector in price_selectors:
                        try:
                            await page.wait_for_selector(selector, timeout=8000)
                            el = await page.query_selector(selector)
                            if el:
                                price = await el.inner_text()
                                print(f"[DEBUG] Amazon price from {selector}:", price)
                                break
                        except Exception as e:
                            print(f"[DEBUG] Amazon selector {selector} failed:", e)
                            continue

                    img = await page.query_selector('img#landingImage')
                    if img:
                        image_url = await img.get_attribute('src')
                    else:
                        meta_img = await page.query_selector('meta[property="og:image"]')
                        image_url = await meta_img.get_attribute('content') if meta_img else None
                    print("[DEBUG] Amazon image_url:", image_url)

                # -------------------------
                # WALMART
                # -------------------------
                elif "walmart.com" in domain:
                    try:
                        await page.wait_for_selector('span[itemprop="price"]', timeout=15000)
                        el = await page.query_selector('span[itemprop="price"]')
                        price = await el.inner_text() if el else None
                        print("[DEBUG] Walmart primary price selector price:", price)
                    except Exception as e:
                        print("[DEBUG] Walmart primary selector failed:", e)

                    if not price:
                        el2 = await page.query_selector('span[data-automation-id="product-price"]')
                        price = await el2.inner_text() if el2 else None
                        print("[DEBUG] Walmart fallback price selector:", price)

                    img = await page.query_selector('meta[property="og:image"]')
                    image_url = await img.get_attribute('content') if img else None
                    print("[DEBUG] Walmart image_url:", image_url)

                # -------------------------
                # FALLBACK — OG IMAGE / META PRICE
                # -------------------------
                if not image_url:
                    og_img = await page.query_selector('meta[property="og:image"]')
                    image_url = await og_img.get_attribute('content') if og_img else None

                if not price:
                    meta_price = await page.query_selector('meta[itemprop="price"]')
                    price = await meta_price.get_attribute('content') if meta_price else None

                await browser.close()
                return {
                    'image_url': image_url or 'Not found',
                    'price': price.strip() if price else 'Not found'
                }

            except Exception as e:
                await browser.close()
                return {'error': f'Scraping failed: {str(e)}'}

    try:
        result = asyncio.run(asyncio.wait_for(run_scraper(), timeout=90))
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
                print("[INFO] Keep-alive ping successful")
            except Exception as e:
                print(f"[WARNING] Keep-alive ping failed: {e}")
            time.sleep(30)

    thread = threading.Thread(target=ping)
    thread.daemon = True
    thread.start()

keep_alive()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))